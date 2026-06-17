"""
electron_display.py
Manages the companion Electron display process and provides an
ElectronDisplayProxy that is API-compatible with DisplayWindow so
all existing `for dw in self.display_windows:` loops work unchanged.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── WebSocket client (optional dep) ──────────────────────────────────────────
try:
    import websocket  # pip install websocket-client
    _WS_OK = True
except ImportError:
    _WS_OK = False
    logger.warning("[ElectronDisplay] websocket-client not installed; Electron display unavailable")

_ELECTRON_PORT = 7432
_RECONNECT_DELAY = 2.0   # seconds between reconnect attempts
_PING_INTERVAL   = 10.0  # seconds


# ─────────────────────────────────────────────────────────────────────────────
#  ElectronDisplayManager
# ─────────────────────────────────────────────────────────────────────────────

class ElectronDisplayManager:
    """
    Launches the Electron subprocess and maintains a WebSocket connection.
    Thread-safe: all sends are enqueued and dispatched by a writer thread.
    """

    def __init__(self, electron_dir: Optional[str] = None):
        # Rezolvare automată cale: dev → __file__, compilat PyInstaller → sys.executable
        self._electron_dir   = electron_dir or self._get_electron_dir()
        self._proc: Optional[subprocess.Popen] = None
        self._ws:   Optional["websocket.WebSocketApp"] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._send_q: queue.Queue = queue.Queue()
        self._writer_thread: Optional[threading.Thread] = None
        self._connected   = threading.Event()
        self._running     = False
        self._lock        = threading.Lock()
        self._pending: list[Dict] = []   # cmds queued before connection
        self._window_ids: set = set()    # track open window IDs
        self._screen_width  = 1920       # updated by open_display()
        self._screen_height = 1080
        self._window_ready_callbacks: Dict[int, Any] = {}  # window_id → one-shot callable

    # ── Path resolution (dev + PyInstaller) ─────────────────────────────────

    def _get_electron_dir(self) -> "Optional[str]":
        """
        Găsește calea corectă către display-electron/ atât în development cât
        și după compilare cu PyInstaller (sys.frozen = True).
        """
        # ── Compiled cu PyInstaller ──────────────────────────────────────────
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)

            # Prioritate 1: lângă .exe (onedir mode — cazul normal)
            electron_dir = os.path.join(exe_dir, 'display-electron')
            if os.path.exists(electron_dir):
                print(f"[Display] Dir (exe): {electron_dir}")
                return electron_dir

            # Prioritate 2: sys._MEIPASS (onefile mode)
            if hasattr(sys, '_MEIPASS'):
                meipass_dir = os.path.join(sys._MEIPASS, 'display-electron')
                if os.path.exists(meipass_dir):
                    print(f"[Display] Dir (MEIPASS): {meipass_dir}")
                    return meipass_dir

            # Prioritate 3: fallback-uri suplimentare
            for subfolder in ('display-electron',
                              '_internal/display-electron',
                              '../display-electron'):
                path = os.path.join(exe_dir, subfolder)
                if os.path.exists(path):
                    print(f"[Display] Dir (fallback): {path}")
                    return path

            print("[Display] ❌ Nu găsesc display-electron/!")
            print(f"[Display] exe_dir: {exe_dir}")
            try:
                print(f"[Display] Conținut: {os.listdir(exe_dir)}")
            except Exception:
                pass
            return None

        # ── Development mode — calea relativă la fișierul .py ────────────────
        base = os.path.dirname(os.path.abspath(__file__))
        electron_dir = os.path.join(base, 'display-electron')
        if os.path.exists(electron_dir):
            print(f"[Display] Dir (dev): {electron_dir}")
            return electron_dir

        # Fallback: caută în folderele parent (max 3 niveluri)
        for i in range(3):
            base = os.path.dirname(base)
            path = os.path.join(base, 'display-electron')
            if os.path.exists(path):
                print(f"[Display] Dir (parent {i}): {path}")
                return path

        print("[Display] ❌ display-electron negăsit!")
        return None

    def _get_npx_command(self) -> "tuple[Optional[str], Optional[str]]":
        """
        Găsește executabilul electron sau npx.
        Returnează (exe_path, electron_dir) sau (None, electron_dir) dacă nu găsit.
        """
        import shutil as _shutil
        electron_dir = self._electron_dir or self._get_electron_dir()
        if not electron_dir:
            return None, None

        # Calea locală din node_modules (preferată — fără dependență de PATH)
        if sys.platform == 'win32':
            electron_bin = os.path.join(electron_dir, 'node_modules', '.bin', 'electron.cmd')
            npx_cmd = 'npx.cmd'
        else:
            electron_bin = os.path.join(electron_dir, 'node_modules', '.bin', 'electron')
            npx_cmd = 'npx'

        if os.path.exists(electron_bin):
            print(f"[Display] Electron bin: {electron_bin}")
            return electron_bin, electron_dir

        # Fallback 1: npx din PATH
        npx_path = _shutil.which(npx_cmd)
        if npx_path:
            print(f"[Display] npx: {npx_path}")
            return npx_path, electron_dir

        # Fallback 2: npm root -g
        try:
            result = subprocess.run(
                ['npm', 'root', '-g'],
                capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                npm_root = result.stdout.strip()
                electron_global = os.path.join(
                    npm_root, '.bin',
                    'electron.cmd' if sys.platform == 'win32' else 'electron')
                if os.path.exists(electron_global):
                    print(f"[Display] Electron global: {electron_global}")
                    return electron_global, electron_dir
        except Exception:
            pass

        print("[Display] ❌ Electron/npx negăsit!")
        return None, electron_dir

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        """Launch Electron process and WebSocket connection.

        Prioritate lansare:
          1. CantioDisplay compilat cu electron-packager (standalone, fără Node.js)
          2. node_modules/electron/dist/electron[.exe]  (binary direct)
          3. Fallback: _launch_electron() → node_modules/.bin/electron.cmd / npx
        """
        if not _WS_OK:
            logger.error("[ElectronDisplay] Cannot start: websocket-client missing")
            return False

        self._running = True

        mode, exe_path = self._get_electron_executable()

        if mode == 'compiled':
            # Executabil standalone compilat cu electron-packager
            cmd = [exe_path]
            cwd = os.path.dirname(exe_path)
            print(f"[Display] Mod: compiled | {exe_path}")

        elif mode == 'source':
            # Electron binary din node_modules/electron/dist/ cu main.js în cwd
            electron_dir = self._electron_dir or self._get_electron_dir()
            cmd = [exe_path, '.']
            cwd = electron_dir
            print(f"[Display] Mod: source | {exe_path} . (cwd={cwd})")

        else:
            # Fallback final: electron.cmd din node_modules/.bin/ sau npx
            print("[Display] Mod: fallback (electron.cmd / npx)")
            self._launch_electron()
            self._start_ws_thread()
            self._start_writer_thread()
            return True

        try:
            if sys.platform == 'win32':
                _si = subprocess.STARTUPINFO()
                _si.dwFlags    |= subprocess.STARTF_USESHOWWINDOW
                _si.wShowWindow = subprocess.SW_HIDE
                self._proc = subprocess.Popen(
                    cmd,
                    cwd=cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    startupinfo=_si,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                self._proc = subprocess.Popen(
                    cmd,
                    cwd=cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                )

            print(f"[Display] PID: {self._proc.pid}")
            logger.info("[ElectronDisplay] Electron started (pid=%d, mode=%s)",
                        self._proc.pid, mode)

            threading.Thread(target=self._read_electron_output,
                             daemon=True, name="electron-stdout").start()
            threading.Thread(target=self._read_electron_errors,
                             daemon=True, name="electron-stderr").start()

            time.sleep(2)
            poll = self._proc.poll()
            if poll is not None:
                print(f"[Display] ❌ Electron s-a oprit cu cod: {poll}")
                logger.error("[ElectronDisplay] Electron exited immediately (code=%d)", poll)
            else:
                print("[Display] ✅ Electron rulează!")

        except FileNotFoundError:
            print(f"[Display] ❌ '{cmd[0]}' negăsit!")
            logger.error("[ElectronDisplay] electron not found: %s", cmd[0])
        except Exception as e:
            print(f"[Display] ❌ Eroare la pornire: {e}")
            logger.error("[ElectronDisplay] Failed to start Electron: %s", e)

        self._start_ws_thread()
        self._start_writer_thread()
        return True

    def stop(self):
        """Gracefully shut down Electron and close WebSocket."""
        self._running = False
        try:
            self._send_now({"type": "quit"})
        except Exception:
            pass
        if self._ws:
            try: self._ws.close()
            except Exception: pass
        if self._proc and self._proc.poll() is None:
            try: self._proc.terminate()
            except Exception: pass
        logger.info("[ElectronDisplay] stopped")

    def is_running(self) -> bool:
        """True as soon as the Electron process is alive (WS may still be connecting)."""
        return (self._running
                and self._proc is not None
                and self._proc.poll() is None)

    def is_connected(self) -> bool:
        """True when the WebSocket connection to the Electron process is active."""
        return self._connected.is_set()

    # ── Display commands (enqueue) ────────────────────────────────────────────

    def open_display(self, screen_index: int = 0, window_id: int = 0,
                     window_name: str = "Cantio Display"):
        # Captează dimensiunile ecranului pentru metodele de geometrie Qt-compat.
        # Folosește aceeași logică primary/secondary ca main.js openDisplay():
        #   screen_index 0 → primul ecran secundar (non-primary)
        #   screen_index 1 → primul ecran secundar (1-based)
        #   fallback       → indexare directă în lista de ecrane
        try:
            from PyQt6.QtWidgets import QApplication
            screens   = QApplication.screens()
            primary   = QApplication.primaryScreen()
            secondary = [s for s in screens if s is not primary]

            if screen_index == 0 and secondary:
                target_scr = secondary[0]
            elif screen_index > 0 and screen_index <= len(secondary):
                target_scr = secondary[screen_index - 1]
            elif screen_index < len(screens):
                target_scr = screens[screen_index]
            elif screens:
                target_scr = screens[-1]
            else:
                target_scr = None

            if target_scr:
                g = target_scr.geometry()
                self._screen_width  = g.width()
                self._screen_height = g.height()
                print(f"[Display] open_display: screen_index={screen_index} → "
                      f"{self._screen_width}×{self._screen_height} "
                      f"@ ({g.x()},{g.y()})")
        except Exception:
            pass
        self._window_ids.add(window_id)
        self._enqueue({"type": "open",
                       "window_id": window_id,
                       "screen_index": screen_index,
                       "window_name": window_name})

    def close_display(self, window_id: int = 0):
        self._window_ids.discard(window_id)
        self._enqueue({"type": "close", "window_id": window_id})

    def close_all(self):
        self._window_ids.clear()
        self._enqueue({"type": "close", "window_id": None})

    def show_text(self, text: str, fmt: Dict, window_id: int = 0,
                  transition: str = "fade", transition_duration: int = 400,
                  metadata: Optional[Dict] = None):
        self._enqueue({
            "type": "show_text",
            "window_id": window_id,
            "text": text,
            "format": fmt,
            "transition": transition,
            "transition_duration": transition_duration,
            "metadata": metadata or {},
        })

    def black_screen(self, window_id: int = 0):
        self._enqueue({"type": "black", "window_id": window_id})

    def apply_settings(self, settings: Dict, window_id: int = 0):
        self._enqueue({"type": "settings", "window_id": window_id, "settings": settings})

    def show_ticker(self, text: str, settings: Optional[Dict] = None,
                    window_id: int = 0):
        self._enqueue({
            "type":     "ticker",
            "window_id": window_id,
            "text":     text,
            "settings": settings or {},
        })

    def hide_ticker(self, window_id: int = 0):
        self._enqueue({"type": "hide_ticker", "window_id": window_id})

    def show_ticker_advanced(self, text: str, settings: Optional[Dict] = None,
                             window_id: int = 0):
        """Show ticker with in-effect animation (slide_up / fade / instant)."""
        self._enqueue({
            "type":      "ticker_advanced",
            "window_id": window_id,
            "text":      text,
            "settings":  settings or {},
        })

    def hide_ticker_with_effect(self, settings: Optional[Dict] = None,
                                window_id: int = 0):
        """Hide ticker with out-effect animation (slide_down / fade / instant)."""
        self._enqueue({
            "type":      "hide_ticker_effect",
            "window_id": window_id,
            "settings":  settings or {},
        })

    def start_timer(self, seconds: int, window_id: int = 0):
        self._enqueue({"type": "timer", "window_id": window_id, "seconds": seconds})

    def stop_timer(self, window_id: int = 0):
        self._enqueue({"type": "stop_timer", "window_id": window_id})

    def toggle_clock(self, active: bool, settings: Optional[Dict] = None,
                     window_id: int = 0):
        self._enqueue({
            "type":     "clock",
            "window_id": window_id,
            "active":   active,
            "settings": settings or {},
        })

    def show_logo(self, path: str, window_id: int = 0):
        self._enqueue({"type": "logo", "window_id": window_id, "path": path})

    def projector_off(self, window_id: int = 0):
        self._enqueue({"type": "projector_off", "window_id": window_id})

    def clear_text(self, window_id: int = 0):
        """Clear text + metadata without affecting background."""
        self._enqueue({"type": "clear_text", "window_id": window_id})

    def freeze_display(self, window_id: int = 0):
        """True visual freeze — Electron halts all rendering, canvas stays as-is."""
        self._enqueue({"type": "freeze", "window_id": window_id})

    def unfreeze_display(self, window_id: int = 0):
        """Resume live rendering after freeze_display()."""
        self._enqueue({"type": "unfreeze", "window_id": window_id})

    def ping(self) -> bool:
        """Synchronous ping – returns True if Electron responds within 2 s."""
        if not self._connected.is_set():
            return False
        try:
            self._send_now({"type": "ping"})
            return True
        except Exception:
            return False

    def get_screens(self) -> list:
        """Returns screen list synchronously (best-effort, may be stale)."""
        return getattr(self, "_last_screens", [])

    # ── Qt widget-compat geometry methods ─────────────────────────────────────
    # These allow code that calls dw.width(), dw.screen(), etc. to work
    # even when dw is an ElectronDisplayManager / ElectronDisplayProxy.

    def width(self) -> int:
        """Width of the projector screen."""
        return self._screen_width or 1920

    def height(self) -> int:
        """Height of the projector screen."""
        return self._screen_height or 1080

    def size(self):
        from PyQt6.QtCore import QSize
        return QSize(self.width(), self.height())

    def rect(self):
        from PyQt6.QtCore import QRect
        return QRect(0, 0, self.width(), self.height())

    def geometry(self):
        from PyQt6.QtCore import QRect
        return QRect(0, 0, self.width(), self.height())

    def frameGeometry(self):
        return self.geometry()

    def pos(self):
        from PyQt6.QtCore import QPoint
        return QPoint(0, 0)

    def isVisible(self) -> bool:
        return self._connected.is_set() and len(self._window_ids) > 0

    def isFullScreen(self) -> bool:
        return True

    def showNormal(self):
        pass  # window mode managed by Electron

    def showFullScreen(self):
        pass  # always fullscreen in Electron

    def screen(self):
        """Return the QScreen for the configured display, or None."""
        try:
            from PyQt6.QtWidgets import QApplication
            screens = QApplication.screens()
            return screens[0] if screens else None
        except Exception:
            return None

    def winId(self):
        return 0

    def devicePixelRatio(self) -> float:
        try:
            scr = self.screen()
            return scr.devicePixelRatio() if scr else 1.0
        except Exception:
            return 1.0

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_electron_executable(self) -> "tuple[Optional[str], Optional[str]]":
        """
        Detectează executabilul Electron disponibil.

        Prioritate:
          1. CantioDisplay compilat cu electron-packager — standalone, fără Node.js
             Win32  : <base>/CantioDisplay/CantioDisplay.exe
             macOS  : <base>/CantioDisplay/CantioDisplay.app/Contents/MacOS/CantioDisplay
             Linux  : <base>/CantioDisplay/CantioDisplay
          2. Electron binary din node_modules/electron/dist/ — necesită Node.js instalat
             Win32  : <electron_dir>/node_modules/electron/dist/electron.exe
             macOS/L: <electron_dir>/node_modules/electron/dist/electron

        Returns:
          ('compiled', exe_path) — executabil standalone compilat
          ('source',   bin_path) — electron binary din node_modules
          (None,       None)     — niciuna găsită; start() va folosi fallback
        """
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.abspath(__file__))

        # ── 1. Executabil compilat cu electron-packager ──────────────────────
        if sys.platform == 'win32':
            compiled = os.path.join(base, 'CantioDisplay', 'CantioDisplay.exe')
        elif sys.platform == 'darwin':
            compiled = os.path.join(
                base, 'CantioDisplay', 'CantioDisplay.app',
                'Contents', 'MacOS', 'CantioDisplay')
        else:
            compiled = os.path.join(base, 'CantioDisplay', 'CantioDisplay')

        if os.path.exists(compiled):
            print(f"[Display] Executabil compilat: {compiled}")
            return 'compiled', compiled

        # ── 2. Electron binary din node_modules/electron/dist/ ───────────────
        electron_dir = self._electron_dir or self._get_electron_dir()
        if electron_dir:
            if sys.platform == 'win32':
                electron_bin = os.path.join(
                    electron_dir, 'node_modules', 'electron', 'dist', 'electron.exe')
            else:
                electron_bin = os.path.join(
                    electron_dir, 'node_modules', 'electron', 'dist', 'electron')

            if os.path.exists(electron_bin):
                print(f"[Display] Electron bin (dist): {electron_bin}")
                return 'source', electron_bin

        print("[Display] ❌ Niciun executabil Electron găsit (compiled + dist)!")
        return None, None

    def _launch_electron(self):
        """Start the Electron process via npm/npx."""
        # Re-rezolvă calea dacă nu a fost determinată la __init__
        if not self._electron_dir:
            self._electron_dir = self._get_electron_dir()

        print(f"[Display] Cale: {self._electron_dir}")
        print(f"[Display] Există: {os.path.isdir(self._electron_dir) if self._electron_dir else False}")

        if not self._electron_dir or not os.path.isdir(self._electron_dir):
            print("[Display] ❌ display-electron/ lipsește!")
            logger.error("[ElectronDisplay] display-electron dir not found: %s", self._electron_dir)
            return

        # Verifică fișierele cheie
        for f in ("main.js", "display.html", "display.js", "package.json"):
            path = os.path.join(self._electron_dir, f)
            ok = os.path.exists(path)
            print(f"[Display] {f}: {'✅' if ok else '❌ LIPSĂ'}")

        # Verifică node_modules
        nm = os.path.join(self._electron_dir, "node_modules")
        nm_ok = os.path.isdir(nm)
        print(f"[Display] node_modules: {'✅' if nm_ok else '❌ LIPSĂ — rulează npm install'}")
        if not nm_ok:
            logger.warning("[ElectronDisplay] node_modules missing – run npm install in %s",
                           self._electron_dir)

        # Găsește executabilul electron prin helper (node_modules local sau npx)
        electron_exe, _ = self._get_npx_command()
        if not electron_exe:
            print("[Display] ❌ Electron/npx negăsit — Node.js instalat?")
            return

        if 'electron' in os.path.basename(electron_exe).lower():
            args = [electron_exe, "."]
        else:
            args = [electron_exe, "electron", "."]

        print(f"[Display] Pornesc: {' '.join(args)}")

        try:
            # Windows: ascunde complet fereastra de consolă (BUG-FIX: terminal negru gol)
            if sys.platform == 'win32':
                _si = subprocess.STARTUPINFO()
                _si.dwFlags    |= subprocess.STARTF_USESHOWWINDOW
                _si.wShowWindow = subprocess.SW_HIDE
                self._proc = subprocess.Popen(
                    args,
                    cwd=self._electron_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    startupinfo=_si,
                    creationflags=(
                        subprocess.CREATE_NO_WINDOW |
                        subprocess.DETACHED_PROCESS
                    ),
                )
            else:
                self._proc = subprocess.Popen(
                    args,
                    cwd=self._electron_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                )
            print(f"[Display] PID: {self._proc.pid}")
            logger.info("[ElectronDisplay] Electron started (pid=%d)", self._proc.pid)

            # Pornește thread-urile de citire output
            threading.Thread(target=self._read_electron_output,
                             daemon=True, name="electron-stdout").start()
            threading.Thread(target=self._read_electron_errors,
                             daemon=True, name="electron-stderr").start()

            # Verifică după 2s dacă procesul mai rulează
            time.sleep(2)
            poll = self._proc.poll()
            if poll is not None:
                print(f"[Display] ❌ Electron s-a oprit cu cod: {poll}")
                logger.error("[ElectronDisplay] Electron exited immediately with code %d", poll)
            else:
                print("[Display] ✅ Electron rulează!")

        except FileNotFoundError:
            print(f"[Display] ❌ '{args[0]}' negăsit — Node.js instalat?")
            logger.error("[ElectronDisplay] electron/npx not found – is Node.js installed?")
        except Exception as e:
            print(f"[Display] ❌ Eroare la pornire: {e}")
            logger.error("[ElectronDisplay] Failed to start Electron: %s", e)

    def _read_electron_output(self):
        """Citește și afișează stdout-ul Electron în timp real (thread daemon)."""
        try:
            for line in self._proc.stdout:
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    print(f"[Electron] {text}")
        except Exception:
            pass

    def _read_electron_errors(self):
        """Citește și afișează stderr-ul Electron în timp real (thread daemon)."""
        try:
            for line in self._proc.stderr:
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    print(f"[Electron ERR] {text}")
        except Exception:
            pass

    def _start_ws_thread(self):
        self._ws_thread = threading.Thread(target=self._ws_loop, daemon=True, name="electron-ws")
        self._ws_thread.start()

    def _ws_loop(self):
        """Reconnecting WebSocket loop."""
        url = f"ws://127.0.0.1:{_ELECTRON_PORT}"
        # Give Electron a moment to start its WS server
        time.sleep(1.5)
        while self._running:
            try:
                self._ws = websocket.WebSocketApp(
                    url,
                    on_open    = self._on_ws_open,
                    on_message = self._on_ws_message,
                    on_error   = self._on_ws_error,
                    on_close   = self._on_ws_close,
                )
                self._ws.run_forever(ping_interval=_PING_INTERVAL, ping_timeout=5)
            except Exception as e:
                logger.debug("[ElectronDisplay] WS error: %s", e)
            if self._running:
                time.sleep(_RECONNECT_DELAY)

    def _on_ws_open(self, ws):
        logger.info("[ElectronDisplay] WebSocket connected")
        self._connected.set()
        # Flush any pending commands
        with self._lock:
            pending = list(self._pending)
            self._pending.clear()
        for cmd in pending:
            try: ws.send(json.dumps(cmd))
            except Exception: pass

    def set_window_ready_callback(self, window_id: int, callback) -> None:
        """Register a one-shot callback fired when Electron reports window_ready."""
        self._window_ready_callbacks[window_id] = callback

    def _on_ws_message(self, ws, raw):
        try:
            msg = json.loads(raw)
        except Exception:
            return
        mtype = msg.get("type")
        if mtype == "screens":
            self._last_screens = msg.get("screens", [])
        elif mtype == "ready":
            self._last_screens = msg.get("screens", [])
            logger.info("[ElectronDisplay] ready, %d screen(s)", len(self._last_screens))
        elif mtype == "window_ready":
            wid = msg.get("window_id")
            cb = self._window_ready_callbacks.pop(wid, None)
            if cb:
                try:
                    cb()
                except Exception as e:
                    logger.debug("[ElectronDisplay] window_ready callback error: %s", e)

    def _on_ws_error(self, ws, error):
        logger.debug("[ElectronDisplay] WS error: %s", error)

    def _on_ws_close(self, ws, code, reason):
        logger.info("[ElectronDisplay] WS closed (%s %s)", code, reason)
        self._connected.clear()
        # If still supposed to be running, schedule a process-level restart check
        if self._running:
            t = threading.Timer(2.0, self._restart)
            t.daemon = True
            t.start()

    def _restart(self):
        """Relaunch Electron if the process has died. The WS loop reconnects automatically."""
        if not self._running:
            return
        if self._proc is not None and self._proc.poll() is None:
            # Process still alive – WS loop will reconnect on its own
            return
        logger.info("[ElectronDisplay] Repornesc Electron automat...")
        self._launch_electron()

    def _start_writer_thread(self):
        self._writer_thread = threading.Thread(
            target=self._writer_loop, daemon=True, name="electron-writer")
        self._writer_thread.start()

    def _writer_loop(self):
        while self._running:
            try:
                cmd = self._send_q.get(timeout=1.0)
            except queue.Empty:
                continue
            if not self._connected.wait(timeout=5.0):
                # Still not connected – keep in pending
                with self._lock:
                    self._pending.append(cmd)
                continue
            try:
                if self._ws:
                    self._ws.send(json.dumps(cmd))
            except Exception as e:
                logger.debug("[ElectronDisplay] send failed: %s", e)
                with self._lock:
                    self._pending.append(cmd)

    def _enqueue(self, cmd: Dict):
        if not self._running:
            return
        if not self._connected.is_set():
            with self._lock:
                self._pending.append(cmd)
        else:
            self._send_q.put(cmd)

    def _send_now(self, cmd: Dict):
        if self._ws:
            self._ws.send(json.dumps(cmd))

    def diagnose(self):
        """Rulează diagnostic complet și afișează în consolă (util la depanare)."""
        print("=" * 50)
        print("[Display] DIAGNOSTIC")
        print("=" * 50)
        print(f"frozen:     {getattr(sys, 'frozen', False)}")
        print(f"executable: {sys.executable}")

        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            print(f"exe_dir:    {exe_dir}")
            print("Conținut exe_dir:")
            try:
                for f in sorted(os.listdir(exe_dir)):
                    print(f"  {f}")
            except Exception as e:
                print(f"  Eroare: {e}")

        electron_dir = self._get_electron_dir()
        print(f"\nelectron_dir: {electron_dir}")

        if electron_dir:
            print("Conținut electron_dir:")
            try:
                for f in sorted(os.listdir(electron_dir)):
                    print(f"  {f}")
            except Exception as e:
                print(f"  Eroare: {e}")
            nm = os.path.join(electron_dir, 'node_modules')
            print(f"node_modules există: {os.path.exists(nm)}")
            if os.path.exists(nm):
                try:
                    packages = [p for p in os.listdir(nm) if not p.startswith('.')]
                    print(f"node_modules packages ({len(packages)}): "
                          f"{', '.join(packages[:10])}{'...' if len(packages) > 10 else ''}")
                except Exception:
                    pass

        electron_exe, _ = self._get_npx_command()
        print(f"\nelectron_exe: {electron_exe}")
        print(f"ws_connected: {self._connected.is_set()}")
        print(f"proc_running: {self._proc is not None and self._proc.poll() is None}")
        print("=" * 50)


# ─────────────────────────────────────────────────────────────────────────────
#  ElectronDisplayProxy
#  Drop-in replacement for DisplayWindow – same public API
# ─────────────────────────────────────────────────────────────────────────────

class ElectronDisplayProxy:
    """
    Wraps ElectronDisplayManager and exposes the same interface as DisplayWindow
    so all existing `for dw in self.display_windows:` loops work unchanged.
    """

    def __init__(
        self,
        manager: ElectronDisplayManager,
        window_id: int = 0,
        window_name: str = "Cantio Display",
        initial_settings: Optional[Dict] = None,
    ):
        self._mgr         = manager
        self._window_id   = window_id
        self._window_name = window_name
        self.settings     = dict(initial_settings or {})
        self._current_settings = self.settings  # alias kept for compat
        self._clock_on    = False
        self._frozen      = False
        self._transparent = False
        self._logo_path: Optional[str] = None
        self._tmp_logo:  Optional[str] = None   # temp file for QPixmap logos
        self._tmp_slide:  Optional[str] = None  # temp file for show_slide_image

        # Compat attributes that ControlWindow reads
        self.window_name  = window_name
        self.is_open      = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def show(self):
        """Open the Electron window (called after construction)."""
        self._mgr.open_display(
            screen_index = self.settings.get("_screen_index", 0),
            window_id    = self._window_id,
            window_name  = self._window_name,
        )
        self.is_open = True
        # Push initial settings
        if self.settings:
            self._mgr.apply_settings(self.settings, self._window_id)

    def close(self):
        self._mgr.close_display(self._window_id)
        self.is_open = False
        # Clean up temp files
        for tmp in (self._tmp_logo, self._tmp_slide):
            if tmp and os.path.exists(tmp):
                try: os.remove(tmp)
                except Exception: pass

    def isVisible(self) -> bool:
        return self.is_open

    # ── DisplayWindow-compatible API ──────────────────────────────────────────

    def show_text(self, text: str, fmt: Optional[Dict] = None, metadata: Optional[Dict] = None):
        if self._frozen:
            return
        self._mgr.show_text(
            text       = text,
            fmt        = fmt or {},
            window_id  = self._window_id,
            transition = self.settings.get("transition", "fade"),
            transition_duration = int(self.settings.get("transition_duration", 400)),
            metadata   = metadata,
        )

    def black_screen(self):
        self._mgr.black_screen(self._window_id)

    def clear(self):
        self.black_screen()

    def apply_settings(self, s: Dict):
        self.settings = dict(s)
        self._current_settings = self.settings
        self._mgr.apply_settings(s, self._window_id)
        # Handle transparent flag
        if s.get("bg_transparent") == "true":
            self._mgr._enqueue({"type": "transparent", "window_id": self._window_id})

    def _apply_background(self):
        """Re-push current settings so Electron re-applies background (image/video/color)."""
        self._mgr.apply_settings(self.settings, self._window_id)

    def set_ticker(self, text: str, speed=None, color=None,
                   ticker_settings: Optional[Dict] = None):
        if text:
            # Build ticker settings from explicit args + any extras passed in
            ts = dict(ticker_settings or {})
            if speed is not None: ts["speed"] = speed
            if color is not None: ts["text_color"] = color
            self._mgr.show_ticker(text, ts or None, self._window_id)
        else:
            self._mgr.hide_ticker(self._window_id)

    def clear_ticker(self):
        self._mgr.hide_ticker(self._window_id)

    def show_ticker_advanced(self, text: str, settings: Optional[Dict] = None):
        """Show ticker with slide-up (or other) animation effect."""
        self._mgr.show_ticker_advanced(text, settings or {}, self._window_id)

    def hide_ticker_with_effect(self, settings: Optional[Dict] = None):
        """Hide ticker with slide-down (or other) animation effect."""
        self._mgr.hide_ticker_with_effect(settings or {}, self._window_id)

    def toggle_clock(self, active: Optional[bool] = None,
                     clock_settings: Optional[Dict] = None):
        if active is None:
            self._clock_on = not self._clock_on
        else:
            self._clock_on = active
        self._mgr.toggle_clock(self._clock_on, clock_settings or {}, self._window_id)

    def start_countdown(self, seconds: int, color=None):
        if color is not None:
            patch = dict(self.settings)
            patch["countdown_color"] = color
            self._mgr.apply_settings(patch, self._window_id)
        self._mgr.start_timer(seconds, self._window_id)

    def stop_countdown(self):
        self._mgr.stop_timer(self._window_id)

    def clear_text(self):
        """
        Clear text and metadata from the display without touching the background.
        Mirrors display.js 'clear_text' handler.
        """
        self._mgr._enqueue({"type": "clear_text", "window_id": self._window_id})

    def freeze_display(self):
        """
        True visual freeze — Electron halts all rendering, canvas stays as-is.
        Does NOT go black (unlike freeze_black).
        """
        self._frozen = True
        self._mgr._enqueue({"type": "freeze", "window_id": self._window_id})

    def unfreeze_display(self):
        """Resume live rendering after freeze_display()."""
        self._frozen = False
        self._mgr._enqueue({"type": "unfreeze", "window_id": self._window_id})

    def freeze_black(self):
        self._frozen = True
        self._mgr.black_screen(self._window_id)

    def unfreeze(self):
        self._frozen = False
        # Also send unfreeze in case freeze_display() was used
        self._mgr._enqueue({"type": "unfreeze", "window_id": self._window_id})

    def show_logo(self, pixmap_or_path=None):
        """Accept either a file path (str) or a QPixmap."""
        if pixmap_or_path is None:
            return
        if isinstance(pixmap_or_path, str):
            path = pixmap_or_path
        else:
            # It's a QPixmap – save to temp PNG
            try:
                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                tmp.close()
                pixmap_or_path.save(tmp.name, "PNG")
                path = tmp.name
                if self._tmp_logo and os.path.exists(self._tmp_logo):
                    try: os.remove(self._tmp_logo)
                    except Exception: pass
                self._tmp_logo = tmp.name
            except Exception as e:
                logger.error("[ElectronProxy] show_logo pixmap save failed: %s", e)
                return
        self._logo_path = path
        self._mgr.show_logo(path, self._window_id)

    def hide_logo(self):
        self._logo_path = None
        self._mgr._enqueue({"type": "logo", "window_id": self._window_id, "path": None})

    def projector_off(self):
        self._mgr.projector_off(self._window_id)

    def show_slide_image(self, pixmap_or_path=None):
        """
        Display a still image (QPixmap or file path) fullscreen.
        Saves QPixmap to a temp PNG then sends as bg_type='image'.
        """
        if pixmap_or_path is None:
            return
        if isinstance(pixmap_or_path, str):
            path = pixmap_or_path
        else:
            try:
                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                tmp.close()
                pixmap_or_path.save(tmp.name, "PNG")
                path = tmp.name
                # Clean up previous slide temp
                if self._tmp_slide and os.path.exists(self._tmp_slide):
                    try: os.remove(self._tmp_slide)
                    except Exception: pass
                self._tmp_slide = tmp.name
            except Exception as e:
                logger.error("[ElectronProxy] show_slide_image save failed: %s", e)
                return
        # Send as dedicated slide_image command (handled in display.js)
        self._mgr._enqueue({
            "type":      "slide_image",
            "window_id": self._window_id,
            "path":      path,
        })

    def toggle_transparent(self) -> bool:
        """Toggle transparent mode. Returns new state (True = transparent on)."""
        self._transparent = not self._transparent
        patch = dict(self.settings)
        patch["bg_transparent"] = "true" if self._transparent else "false"
        self.settings = patch
        self._mgr.apply_settings(patch, self._window_id)
        if self._transparent:
            self._mgr._enqueue({"type": "transparent", "window_id": self._window_id})
        return self._transparent

    # ── Qt widget-compat geometry methods ─────────────────────────────────────
    # Delegates to the real QScreen for the configured screen index so that
    # control_window.py callers (dw.width(), dw.screen(), etc.) work correctly.

    def _qt_screen(self):
        """Return the QScreen matching this proxy's configured screen index."""
        try:
            from PyQt6.QtWidgets import QApplication
            screens = QApplication.screens()
            idx = self.settings.get("_screen_index", 0)
            if screens:
                return screens[min(int(idx), len(screens) - 1)]
        except Exception:
            pass
        return None

    def width(self) -> int:
        scr = self._qt_screen()
        if scr:
            return scr.geometry().width()
        return self._mgr.width()

    def height(self) -> int:
        scr = self._qt_screen()
        if scr:
            return scr.geometry().height()
        return self._mgr.height()

    def size(self):
        from PyQt6.QtCore import QSize
        return QSize(self.width(), self.height())

    def rect(self):
        from PyQt6.QtCore import QRect
        return QRect(0, 0, self.width(), self.height())

    def geometry(self):
        from PyQt6.QtCore import QRect
        return QRect(0, 0, self.width(), self.height())

    def frameGeometry(self):
        return self.geometry()

    def pos(self):
        from PyQt6.QtCore import QPoint
        scr = self._qt_screen()
        if scr:
            g = scr.geometry()
            return QPoint(g.x(), g.y())
        return QPoint(0, 0)

    def isFullScreen(self) -> bool:
        return True

    def showNormal(self):
        pass  # window mode managed by Electron

    def showFullScreen(self):
        pass  # always fullscreen in Electron

    def screen(self):
        """Return the QScreen for this proxy's configured screen index."""
        return self._qt_screen()

    def winId(self):
        return 0

    def devicePixelRatio(self) -> float:
        try:
            scr = self._qt_screen()
            return scr.devicePixelRatio() if scr else 1.0
        except Exception:
            return 1.0

    # ── Compat stubs ──────────────────────────────────────────────────────────

    def set_geometry(self, *_):
        pass  # managed by Electron

    def move(self, *_):
        pass

    def resize(self, *_):
        pass

    def raise_(self):
        pass

    def activateWindow(self):
        pass

    def destroyed(self):
        pass  # Qt signal compat – not wired

    def setWindowTitle(self, title: str):
        self._window_name = title
