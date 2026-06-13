"""
Cantio - Media Tab
Local media browser, camera feeds, and cloud media library.
Subtabs: Local (folder browser), Feeds (live cameras), Cloud (GitHub).
"""
import os
import json
import time
import threading
import urllib.request
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton,
    QLabel, QScrollArea, QGridLayout, QFileDialog, QProgressBar,
    QSizePolicy, QFrame, QMenu,
)
from PyQt6.QtCore import Qt, QSize, QTimer, QUrl, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QColor, QFont, QPainter, QPen

from lazy_imports import cv2_available as _cv2_available
HAS_CV2 = _cv2_available()

def _cv2():
    """Lazy cv2 access — imported only when camera tab is used."""
    from lazy_imports import get_cv2
    return get_cv2()

GITHUB_USER   = "TudorSenegeac"
GITHUB_REPO   = "cantio-media"
GITHUB_BRANCH = "main"

CLOUD_BASE_URL  = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}/"
GITHUB_API_URL  = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/git/trees/{GITHUB_BRANCH}?recursive=1"
MEDIA_CACHE_DIR = os.path.join(os.path.expanduser("~"), "Cantio", "media_cache")

_SUPPORTED_IMAGES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
_SUPPORTED_VIDEOS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}

_CLOUD_CACHE_TTL = 3600  # 1 hour


class CameraThread(QThread):
    """Decodează frames de la o cameră în background şi le emite ca numpy RGB."""

    frame_ready = pyqtSignal(object)   # numpy RGB array (h, w, 3) uint8

    def __init__(self, camera_idx: int = 0, parent=None):
        super().__init__(parent)
        self.camera_idx = camera_idx
        self._running   = True

    def run(self) -> None:
        import time as _t
        cv2 = _cv2()
        if cv2 is None:
            return
        cap = cv2.VideoCapture(self.camera_idx)
        if not cap.isOpened():
            return
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        frame_time = 1.0 / 30.0
        try:
            while self._running:
                t0 = _t.time()
                ret, frame = cap.read()
                if not ret:
                    _t.sleep(0.1)
                    continue
                frame = cv2.resize(frame, (1920, 1080),
                                   interpolation=cv2.INTER_LINEAR)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.frame_ready.emit(frame)
                sleep_t = frame_time - (_t.time() - t0)
                if sleep_t > 0:
                    _t.sleep(sleep_t)
        finally:
            cap.release()

    def stop(self) -> None:
        self._running = False
        self.quit()
        self.wait(2000)


class CloudFetchThread(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        try:
            import requests
            api_url = (
                f"https://api.github.com/repos/"
                f"{GITHUB_USER}/{GITHUB_REPO}/"
                f"git/trees/{GITHUB_BRANCH}"
                f"?recursive=1"
            )
            r = requests.get(api_url, timeout=10)
            r.raise_for_status()
            data = r.json()
            items = [
                item for item in data.get("tree", [])
                if item.get("type") == "blob"
                and any(
                    item.get("path", "").lower().endswith(ext)
                    for ext in [
                        ".jpg", ".jpeg", ".png",
                        ".webp", ".gif",
                        ".mp4", ".mov",
                    ]
                )
            ]
            self.finished.emit(items)
        except Exception as e:
            self.error.emit(str(e))


_DARK_SS = (
    "QWidget { background: #181818; color: #e0e0e0; font-family: 'Segoe UI'; }"
    "QPushButton { background: #1c1c1c; color: #bbb; border: 1px solid #2a2a2a; "
    "border-radius: 4px; padding: 4px 10px; font-size: 11px; }"
    "QPushButton:hover { background: #252525; color: #fff; }"
    "QScrollArea { border: none; background: #111; }"
    "QLabel { color: #ccc; }"
)


# ── CameraDetectThread ────────────────────────────────────────────────────────

class CameraDetectThread(QThread):
    """
    Non-blocking camera detection thread.
    Emits camera_found(cam_idx, frame_or_None) for each live camera,
    then detection_done(total_count) when finished.
    """
    camera_found   = pyqtSignal(int, object)   # cam_idx, first frame (ndarray or None)
    detection_done = pyqtSignal(int)           # total cameras found

    MAX_CAMERAS = 8

    def run(self):
        count = 0
        for i in range(self.MAX_CAMERAS):
            if not HAS_CV2:
                break
            try:
                cap = _cv2().VideoCapture(i)
                if cap.isOpened():
                    ret, frame = cap.read()
                    cap.release()
                    self.camera_found.emit(i, frame if ret else None)
                    count += 1
                else:
                    cap.release()
            except Exception:
                pass
        self.detection_done.emit(count)


# ── CameraCard ────────────────────────────────────────────────────────────────

class CameraCard(QFrame):
    """
    A 180×130 card showing a camera preview frame + name + "🖥 Background" button.
    Emits clicked(cam_idx) when the background button is pressed.
    """
    clicked = pyqtSignal(int)

    _CARD_W = 180
    _CARD_H = 130
    _PREV_W = 172
    _PREV_H = 97

    def __init__(self, cam_idx: int, parent=None):
        super().__init__(parent)
        self.cam_idx    = cam_idx
        self._cap       = None
        self._timer     = None
        self.setFixedSize(self._CARD_W, self._CARD_H)
        self.setStyleSheet(
            "QFrame { background: #1a1a1a; border: 1px solid #2a2a2a; "
            "border-radius: 6px; }"
            "QFrame:hover { border-color: #5294e2; }"
        )
        self._build_ui()
        self._start_preview()

    def _build_ui(self):
        vl = QVBoxLayout(self)
        vl.setContentsMargins(4, 4, 4, 4)
        vl.setSpacing(3)

        self._prev_lbl = QLabel("📷")
        self._prev_lbl.setFixedSize(self._PREV_W, self._PREV_H)
        self._prev_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._prev_lbl.setStyleSheet(
            "background: #0d0d0d; border-radius: 3px; "
            "color: #555; font-size: 28px;"
        )
        vl.addWidget(self._prev_lbl)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        name_lbl = QLabel(f"Camera {self.cam_idx}")
        name_lbl.setStyleSheet(
            "color: #aaa; font-size: 10px; background: transparent; border: none;"
        )
        bottom.addWidget(name_lbl, 1)

        bg_btn = QPushButton("🖥")
        bg_btn.setFixedSize(26, 22)
        bg_btn.setToolTip("Setează ca background")
        bg_btn.setStyleSheet(
            "QPushButton { background: #1c3a5a; color: #5294e2; border: none; "
            "border-radius: 3px; font-size: 12px; }"
            "QPushButton:hover { background: #5294e2; color: #fff; }"
        )
        bg_btn.clicked.connect(lambda: self.clicked.emit(self.cam_idx))
        bottom.addWidget(bg_btn)
        vl.addLayout(bottom)

    def _start_preview(self):
        if not HAS_CV2:
            return
        try:
            self._cap = _cv2().VideoCapture(self.cam_idx)
            if not self._cap.isOpened():
                self._cap = None
                return
            self._timer = QTimer(self)
            self._timer.setInterval(200)   # 5 fps preview
            self._timer.timeout.connect(self._grab_frame)
            self._timer.start()
        except Exception:
            self._cap = None

    def _grab_frame(self):
        if not self._cap or not self._cap.isOpened():
            return
        ret, frame = self._cap.read()
        if not ret:
            return
        try:
            frame_rgb = _cv2().cvtColor(frame, _cv2().COLOR_BGR2RGB)
            h, w = frame_rgb.shape[:2]
            q_img = QImage(frame_rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
            pix = QPixmap.fromImage(q_img).scaled(
                self._PREV_W, self._PREV_H,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.FastTransformation,
            )
            # Centre-crop
            x = (pix.width()  - self._PREV_W) // 2
            y = (pix.height() - self._PREV_H) // 2
            self._prev_lbl.setPixmap(pix.copy(x, y, self._PREV_W, self._PREV_H))
        except Exception:
            pass

    def stop(self):
        if self._timer:
            self._timer.stop()
            self._timer = None
        if self._cap:
            self._cap.release()
            self._cap = None

    def closeEvent(self, event):
        self.stop()
        super().closeEvent(event)


# ── CameraFeedGrid ────────────────────────────────────────────────────────────

class CameraFeedGrid(QScrollArea):
    """
    Scrollable grid of CameraCard widgets — one per detected camera.
    Emits camera_selected(cam_idx) when a card's background button is pressed.
    """
    camera_selected = pyqtSignal(int)

    _COLS = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea { border: none; background: #111; }")

        self._cards: list[CameraCard] = []
        self._container = QWidget()
        self._container.setStyleSheet("background: #111;")
        self._grid = QGridLayout(self._container)
        self._grid.setContentsMargins(8, 8, 8, 8)
        self._grid.setSpacing(8)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self._hint_lbl = QLabel(
            "Apasă «🔍 Detectează camere» pentru a găsi camerele conectate"
        )
        self._hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint_lbl.setStyleSheet("color: #444; font-size: 12px; padding: 30px;")
        self._grid.addWidget(self._hint_lbl, 0, 0, 1, self._COLS)

        self.setWidget(self._container)

    def populate(self, camera_indices: list[int]):
        """Clear existing cards and create new CameraCard for each index."""
        # Stop and remove old cards
        for card in self._cards:
            card.stop()
            card.deleteLater()
        self._cards.clear()

        # Clear layout
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        if not camera_indices:
            lbl = QLabel("Nu au fost detectate camere conectate.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #f44336; font-size: 12px; padding: 30px;")
            self._grid.addWidget(lbl, 0, 0, 1, self._COLS)
            return

        for pos, idx in enumerate(camera_indices):
            card = CameraCard(idx, self._container)
            card.clicked.connect(self.camera_selected)
            self._cards.append(card)
            row, col = divmod(pos, self._COLS)
            self._grid.addWidget(card, row, col)

    def refresh_cameras(self):
        """Non-blocking camera detection — shows loading, adds cards one by one."""
        if not HAS_CV2:
            return

        # Stop existing cards
        for card in self._cards:
            card.stop()
            card.deleteLater()
        self._cards.clear()
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        loading_lbl = QLabel("🔍 Detectez camere…")
        loading_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_lbl.setStyleSheet("color: #888; font-size: 12px; padding: 30px;")
        self._grid.addWidget(loading_lbl, 0, 0, 1, self._COLS)
        self._loading_lbl = loading_lbl

        self._detect_thread = CameraDetectThread(self._container)
        self._detect_thread.camera_found.connect(self._on_camera_found)
        self._detect_thread.detection_done.connect(self._on_detection_done)
        self._detect_thread.start()
        self._found_count = 0

    def _on_camera_found(self, cam_idx: int, _frame):
        """Add a CameraCard immediately when a camera is found."""
        # Remove loading label on first camera
        if self._found_count == 0:
            if hasattr(self, '_loading_lbl') and self._loading_lbl:
                self._grid.removeWidget(self._loading_lbl)
                self._loading_lbl.deleteLater()
                self._loading_lbl = None

        card = CameraCard(cam_idx, self._container)
        card.clicked.connect(self.camera_selected)
        self._cards.append(card)
        row, col = divmod(self._found_count, self._COLS)
        self._grid.addWidget(card, row, col)
        self._found_count += 1

    def _on_detection_done(self, total: int):
        """Called when thread finishes. Show 'no cameras' if none found."""
        if total == 0:
            if hasattr(self, '_loading_lbl') and self._loading_lbl:
                self._loading_lbl.setText("Nu au fost detectate camere conectate.")
                self._loading_lbl.setStyleSheet(
                    "color: #f44336; font-size: 12px; padding: 30px;")
            else:
                lbl = QLabel("Nu au fost detectate camere conectate.")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setStyleSheet("color: #f44336; font-size: 12px; padding: 30px;")
                self._grid.addWidget(lbl, 0, 0, 1, self._COLS)

    def stop_all(self):
        for card in self._cards:
            card.stop()


class MediaTab(QWidget):
    def __init__(self, control_window=None, parent=None):
        super().__init__(parent)
        self._control = control_window
        self._folder = ""
        self._cam_caps: dict    = {}
        self._cam_timers: dict  = {}
        self._camera_thread     = None   # CameraThread pentru live

        os.makedirs(MEDIA_CACHE_DIR, exist_ok=True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._subtabs = QTabWidget()
        self._subtabs.setDocumentMode(True)
        self._subtabs.setStyleSheet(
            "QTabBar::tab { padding: 5px 14px; font-size: 11px; color: #666; "
            "border: none; border-bottom: 2px solid transparent; }"
            "QTabBar::tab:selected { color: #e0e0e0; border-bottom: 2px solid #5294e2; }"
            "QTabBar::tab:hover { color: #aaa; }"
            "QTabWidget::pane { border: none; }"
        )
        self._subtabs.addTab(self._build_local_tab(),  "💻 Local")
        self._subtabs.addTab(self._build_feeds_tab(),  "📷 Feeds")
        self._subtabs.addTab(self._build_cloud_tab(),  "☁ Cloud")
        layout.addWidget(self._subtabs)

    # ── HELPERS ───────────────────────────────────────────────────────────────

    def _accent_btn(self, text: str) -> QPushButton:
        b = QPushButton(text)
        b.setStyleSheet(
            "QPushButton { background: #18283a; color: #5294e2; border: 1px solid #1c3a5a; "
            "border-radius: 4px; padding: 5px 12px; font-size: 11px; }"
            "QPushButton:hover { background: #1c3a5a; color: #e0e0e0; }"
        )
        return b

    def _section_lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #5294e2; font-size: 10px; font-weight: 700; letter-spacing: 2px;"
        )
        return lbl

    def _run_bg(self, fn, on_done, on_error):
        """Run fn() in a daemon thread; call on_done(result) or on_error(msg) on main thread."""
        def _worker():
            try:
                res = fn()
                QTimer.singleShot(0, lambda: on_done(res))
            except Exception as e:
                QTimer.singleShot(0, lambda: on_error(str(e)))
        threading.Thread(target=_worker, daemon=True).start()

    # ── SET BACKGROUND (shared) ───────────────────────────────────────────────

    def _set_as_background(self, path: str):
        ext = Path(path).suffix.lower()
        if ext in _SUPPORTED_IMAGES:
            pix = QPixmap(path)
            if pix.isNull():
                return
            # Actualizează LiveState pentru preview / consumers vechi
            try:
                from live_state import get_state
                state = get_state()
                state.bg_pixmap       = pix
                state.bg_video_frame  = None
                state.notify()
            except Exception:
                pass
            if self._control:
                for dw in self._control.display_windows:
                    dw.settings["bg_image"] = path
                    dw.settings["bg_video"] = ""
                    dw._apply_background()
        elif ext in _SUPPORTED_VIDEOS:
            if self._control:
                for dw in self._control.display_windows:
                    dw.settings["bg_video"] = path
                    dw.settings["bg_image"] = ""
                    dw._apply_background()

        # Load into mini player (images + videos)
        if self._control and hasattr(self._control, "mini_player"):
            if ext in _SUPPORTED_IMAGES or ext in _SUPPORTED_VIDEOS:
                self._control.mini_player.load_file(path)

    def _send_image_live(self, path: str):
        ext = Path(path).suffix.lower()
        if ext not in _SUPPORTED_IMAGES:
            return
        pix = QPixmap(path)
        if pix.isNull() or not self._control:
            return
        for dw in self._control.display_windows:
            dw.show_slide_image(pix)

    # ═══════════════════════════════════════════════════════════════════════════
    # LOCAL TAB
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_local_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: #181818;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Top bar
        top = QHBoxLayout()
        self._folder_lbl = QLabel("Niciun folder selectat")
        self._folder_lbl.setStyleSheet("color: #555; font-size: 11px;")
        top.addWidget(self._folder_lbl, 1)

        btn = self._accent_btn("📁 Selectează folder")
        btn.clicked.connect(self._select_folder)
        top.addWidget(btn)
        layout.addLayout(top)

        # Grid
        self._local_scroll = QScrollArea()
        self._local_scroll.setWidgetResizable(True)
        self._local_scroll.setStyleSheet("QScrollArea { border: none; background: #111; }")

        self._grid_container = QWidget()
        self._grid_container.setStyleSheet("background: #111;")
        self._media_grid = QGridLayout(self._grid_container)
        self._media_grid.setContentsMargins(8, 8, 8, 8)
        self._media_grid.setSpacing(6)
        self._media_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self._local_empty_lbl = QLabel("Selectează un folder cu imagini sau videoclipuri")
        self._local_empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._local_empty_lbl.setStyleSheet("color: #444; font-size: 12px; padding: 30px;")
        self._media_grid.addWidget(self._local_empty_lbl, 0, 0)

        self._local_scroll.setWidget(self._grid_container)
        layout.addWidget(self._local_scroll, 1)

        QTimer.singleShot(0, self._restore_last_folder)
        return w

    def _restore_last_folder(self):
        try:
            import database as db
            last = db.get_cache().get("media_last_folder", "")
            if last and os.path.isdir(last):
                self._load_folder(last)
        except Exception:
            pass

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Selectează folderul cu media", self._folder or ""
        )
        if not folder:
            return
        self._load_folder(folder)
        try:
            import database as db
            c = db.get_cache()
            c["media_last_folder"] = folder
            db.save_cache(c)
        except Exception:
            pass

    def _load_folder(self, folder: str):
        self._folder = folder
        self._folder_lbl.setText(os.path.basename(folder))
        self._folder_lbl.setStyleSheet("color: #aaa; font-size: 11px;")

        while self._media_grid.count():
            item = self._media_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        files = []
        try:
            for fn in sorted(os.listdir(folder)):
                ext = Path(fn).suffix.lower()
                if ext in _SUPPORTED_IMAGES or ext in _SUPPORTED_VIDEOS:
                    files.append(os.path.join(folder, fn))
        except Exception:
            pass

        if not files:
            lbl = QLabel("Niciun fișier media găsit în acest folder")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #444; font-size: 12px; padding: 30px;")
            self._media_grid.addWidget(lbl, 0, 0)
            return

        cols = 4
        for idx, path in enumerate(files):
            thumb = self._make_media_thumb(path)
            self._media_grid.addWidget(thumb, idx // cols, idx % cols)

    def _make_media_thumb(self, path: str) -> QWidget:
        w = QWidget()
        w.setFixedSize(108, 96)
        w.setStyleSheet(
            "QWidget { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 5px; }"
            "QWidget:hover { border-color: #5294e2; background: #1e1e1e; }"
        )
        w.setCursor(Qt.CursorShape.PointingHandCursor)

        vl = QVBoxLayout(w)
        vl.setContentsMargins(3, 3, 3, 3)
        vl.setSpacing(2)

        img_lbl = QLabel()
        img_lbl.setFixedSize(102, 60)
        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_lbl.setStyleSheet("background: #0d0d0d; border-radius: 3px;")

        ext = Path(path).suffix.lower()
        if ext in _SUPPORTED_IMAGES:
            pix = QPixmap(path)
            if not pix.isNull():
                pix = pix.scaled(
                    102, 60,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = (pix.width() - 102) // 2
                y = (pix.height() - 60) // 2
                img_lbl.setPixmap(pix.copy(x, y, 102, 60))
            else:
                img_lbl.setText("🖼")
        else:
            img_lbl.setText("🎬")
            img_lbl.setStyleSheet(
                "background: #0d0d0d; border-radius: 3px; "
                "color: #888; font-size: 22px;"
            )
        vl.addWidget(img_lbl)

        name = Path(path).name
        short = (name[:14] + "…") if len(name) > 14 else name
        name_lbl = QLabel(short)
        name_lbl.setStyleSheet("color: #777; font-size: 9px;")
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vl.addWidget(name_lbl)

        w.mousePressEvent = lambda e, p=path: (
            self._set_as_background(p)
            if e.button() == Qt.MouseButton.LeftButton else None
        )
        w.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        w.customContextMenuRequested.connect(
            lambda pos, p=path: self._show_media_menu(p, w.mapToGlobal(pos))
        )
        return w

    def _show_media_menu(self, path: str, gpos):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #1e1e1e; color: #e0e0e0; border: 1px solid #333; padding: 2px; }"
            "QMenu::item { padding: 6px 20px; border-radius: 3px; }"
            "QMenu::item:selected { background: #1c3a5a; }"
        )
        menu.addAction("🖼  Setează ca background",
                       lambda: self._set_as_background(path))
        menu.addAction("📺  Trimite live ca imagine",
                       lambda: self._send_image_live(path))
        menu.exec(gpos)

    # ═══════════════════════════════════════════════════════════════════════════
    # FEEDS TAB (cameras) — CameraFeedGrid
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_feeds_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: #181818;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        if not HAS_CV2:
            lbl = QLabel(
                "OpenCV nu este instalat.\n\n"
                "Rulează în terminal:\n"
                "pip install opencv-python\n\n"
                "Apoi repornește aplicația."
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                "color: #f44336; font-size: 12px; padding: 20px; line-height: 1.6;"
            )
            layout.addWidget(lbl)
            layout.addStretch()
            return w

        # Header row
        top = QHBoxLayout()
        top.addWidget(self._section_lbl("CAMERE"))
        top.addStretch()

        detect_btn = QPushButton("🔍 Detectează camere")
        detect_btn.setStyleSheet(
            "QPushButton { background: #18283a; color: #5294e2; border: 1px solid #1c3a5a; "
            "border-radius: 4px; padding: 4px 10px; font-size: 11px; }"
            "QPushButton:hover { background: #1c3a5a; color: #e0e0e0; }"
        )
        detect_btn.clicked.connect(self._detect_cameras_grid)
        top.addWidget(detect_btn)

        stop_btn = QPushButton("⏹ Oprește feed")
        stop_btn.setStyleSheet(
            "QPushButton { background: #2a1a1a; color: #f44336; border: 1px solid #3a2020; "
            "border-radius: 4px; padding: 4px 10px; font-size: 11px; }"
            "QPushButton:hover { background: #3a2020; }"
        )
        stop_btn.clicked.connect(self._stop_all_cameras)
        top.addWidget(stop_btn)
        layout.addLayout(top)

        # CameraFeedGrid
        self._cam_feed_grid = CameraFeedGrid(self)
        self._cam_feed_grid.camera_selected.connect(self._on_camera_card_selected)
        layout.addWidget(self._cam_feed_grid, 1)

        return w

    def _detect_cameras_grid(self):
        """Detect cameras non-blocking and populate CameraFeedGrid."""
        self._stop_all_cameras()
        self._cam_feed_grid.refresh_cameras()

    def _on_camera_card_selected(self, cam_idx: int):
        """Handle CameraCard 'set as background' click."""
        if self._control:
            for dw in self._control.display_windows:
                if hasattr(dw, 'settings'):
                    dw.settings["bg_type"]  = "camera"
                    dw.settings["bg_image"] = str(cam_idx)
                    if hasattr(dw, '_apply_background'):
                        dw._apply_background()
        # Also push via Electron display if available
        if self._control and hasattr(self._control, 'electron_display'):
            s = {"bg_type": "camera", "bg_image": str(cam_idx)}
            try:
                self._control.electron_display.apply_settings(s)
            except Exception:
                pass
        # Start the live CameraThread for fullscreen streaming
        self._start_camera_live_grid(cam_idx)

    def _start_camera_live_grid(self, cam_idx: int):
        """Start CameraThread and push frames to display."""
        if self._camera_thread is not None:
            self._camera_thread.stop()
            self._camera_thread = None

        if not HAS_CV2:
            return
        # Verify camera is accessible
        cap_test = _cv2().VideoCapture(cam_idx)
        if not cap_test.isOpened():
            cap_test.release()
            return
        cap_test.release()

        self._camera_thread = CameraThread(cam_idx)
        self._camera_thread.frame_ready.connect(self._on_camera_frame)
        self._camera_thread.start()

    def _on_camera_frame(self, frame) -> None:
        """Primeşte frame numpy RGB şi îl trimite direct la toate DisplayCanvas-urile."""
        if self._control:
            for dw in self._control.display_windows:
                if hasattr(dw, 'canvas'):
                    dw.canvas.set_video_frame(frame)

    def _stop_camera(self) -> None:
        """Opreşte CameraThread şi resetează background la negru pe toate display-urile."""
        if self._camera_thread is not None:
            self._camera_thread.stop()
            self._camera_thread = None
        if self._control:
            for dw in self._control.display_windows:
                if hasattr(dw, 'canvas'):
                    dw.canvas.set_video_frame(None)

    def _push_camera_frame(self, cap):
        """Legacy — folosit de preview timers. Nu mai este folosit pentru live."""
        if not cap.isOpened():
            return
        ret, frame = cap.read()
        if not ret:
            return
        frame_rgb = _cv2().cvtColor(frame, _cv2().COLOR_BGR2RGB)
        h, w = frame_rgb.shape[:2]
        raw = frame_rgb.tobytes()
        q_img = QImage(raw, w, h, w * 3, QImage.Format.Format_RGB888)
        try:
            from live_state import get_state
            state = get_state()
            state.bg_video_frame = q_img.copy()
            state.notify()
        except Exception:
            pass

    def _stop_all_cameras(self):
        """Opreşte toate camerele (CameraThread + preview timers)."""
        # Opreşte CameraThread live
        if self._camera_thread is not None:
            self._camera_thread.stop()
            self._camera_thread = None

        # Opreşte preview timers
        for timer in self._cam_timers.values():
            if timer:
                timer.stop()
        self._cam_timers.clear()
        for cap in self._cam_caps.values():
            if cap:
                cap.release()
        self._cam_caps.clear()

        # Resetează frame video la toate display-urile
        if self._control:
            for dw in self._control.display_windows:
                if hasattr(dw, 'canvas'):
                    dw.canvas.set_video_frame(None)

        # Curăţă şi LiveState (pentru preview / consumers vechi)
        try:
            from live_state import get_state
            state = get_state()
            state.bg_video_frame = None
            state.notify()
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════════
    # CLOUD TAB
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_cloud_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: #181818;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        top = QHBoxLayout()
        top.addWidget(self._section_lbl("CLOUD MEDIA — CANTIO"))
        top.addStretch()

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setStyleSheet(
            "QPushButton { background: #1c1c1c; color: #aaa; border: 1px solid #2a2a2a; "
            "border-radius: 4px; padding: 4px 10px; font-size: 11px; }"
            "QPushButton:hover { background: #252525; }"
        )
        refresh_btn.clicked.connect(self._load_cloud_index)
        top.addWidget(refresh_btn)
        layout.addLayout(top)

        self._cloud_status_lbl = QLabel("Apasă Refresh pentru a încărca lista cloud")
        self._cloud_status_lbl.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self._cloud_status_lbl)

        self._cloud_progress = QProgressBar()
        self._cloud_progress.setRange(0, 0)  # indeterminate spinner
        self._cloud_progress.setFixedHeight(4)
        self._cloud_progress.setStyleSheet(
            "QProgressBar { background: #111; border: none; }"
            "QProgressBar::chunk { background: #5294e2; }"
        )
        self._cloud_progress.setVisible(False)
        layout.addWidget(self._cloud_progress)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #111; }")

        self._cloud_container = QWidget()
        self._cloud_container.setStyleSheet("background: #111;")
        self._cloud_layout = QVBoxLayout(self._cloud_container)
        self._cloud_layout.setContentsMargins(4, 4, 4, 4)
        self._cloud_layout.setSpacing(6)
        self._cloud_layout.addStretch()

        scroll.setWidget(self._cloud_container)
        layout.addWidget(scroll, 1)

        self._cloud_fetch_thread = None
        return w

    def _get_cloud_cache(self):
        try:
            import database as db
            c = db.get_cache()
            cached = c.get("cloud_index_cache", {})
            ts = cached.get("timestamp", 0)
            if time.time() - ts < _CLOUD_CACHE_TTL and cached.get("items"):
                return cached["items"]
        except Exception:
            pass
        return None

    def _save_cloud_cache(self, items: list):
        try:
            import database as db
            c = db.get_cache()
            c["cloud_index_cache"] = {"timestamp": time.time(), "items": items}
            db.save_cache(c)
        except Exception:
            pass

    def _load_cloud_index(self):
        # Check 1-hour cache first
        cached = self._get_cloud_cache()
        if cached is not None:
            self._cloud_status_lbl.setText(f"Cache local — {len(cached)} fișiere (< 1h)")
            self._cloud_status_lbl.setStyleSheet("color: #4caf50; font-size: 11px;")
            self._render_cloud_items(cached)
            return

        self._cloud_status_lbl.setText("Se descarcă indexul din cloud…")
        self._cloud_status_lbl.setStyleSheet("color: #aaa; font-size: 11px;")
        self._cloud_progress.setVisible(True)

        while self._cloud_layout.count() > 1:
            item = self._cloud_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Stop previous thread if running
        if self._cloud_fetch_thread and self._cloud_fetch_thread.isRunning():
            self._cloud_fetch_thread.quit()

        self._cloud_fetch_thread = CloudFetchThread()
        self._cloud_fetch_thread.finished.connect(self._on_cloud_fetch_done)
        self._cloud_fetch_thread.error.connect(self._on_cloud_fetch_error)
        self._cloud_fetch_thread.start()

    def _on_cloud_fetch_done(self, items: list):
        self._cloud_progress.setVisible(False)
        self._save_cloud_cache(items)
        self._cloud_status_lbl.setText(f"GitHub — {len(items)} fișiere disponibile")
        self._cloud_status_lbl.setStyleSheet("color: #4caf50; font-size: 11px;")
        self._render_cloud_items(items)

    def _on_cloud_fetch_error(self, msg: str):
        self._cloud_progress.setVisible(False)
        self._cloud_status_lbl.setText(f"Eroare: {msg}")
        self._cloud_status_lbl.setStyleSheet("color: #f44336; font-size: 11px;")

    def _render_cloud_items(self, items: list):
        while self._cloud_layout.count() > 1:
            item = self._cloud_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for raw in items:
            path = raw.get("path", "")
            ext = Path(path).suffix.lower()
            is_video = ext in _SUPPORTED_VIDEOS
            item = {
                "name": os.path.basename(path),
                "file": path,
                "type": "video" if is_video else "image",
                "size": "",
            }
            row_w = self._make_cloud_item_row(item)
            self._cloud_layout.insertWidget(self._cloud_layout.count() - 1, row_w)

    def _render_cloud_index(self, data: dict):
        """Legacy — kept for backward compat; not called in normal flow."""
        cats = data.get("categories", [])
        total = sum(len(c.get("items", [])) for c in cats)
        ver = data.get("version", "?")
        self._cloud_status_lbl.setText(f"Index v{ver} — {total} fișiere disponibile")
        self._cloud_status_lbl.setStyleSheet("color: #4caf50; font-size: 11px;")
        for cat in cats:
            for item in cat.get("items", []):
                row_w = self._make_cloud_item_row(item)
                self._cloud_layout.insertWidget(self._cloud_layout.count() - 1, row_w)

    def _make_cloud_item_row(self, item: dict) -> QWidget:
        file_name = os.path.basename(item.get("file", ""))
        cached_path = os.path.join(MEDIA_CACHE_DIR, file_name)
        is_cached = os.path.exists(cached_path)

        w = QWidget()
        w.setStyleSheet("QWidget { background: #1a1a1a; border-radius: 4px; }")
        rl = QHBoxLayout(w)
        rl.setContentsMargins(10, 6, 10, 6)
        rl.setSpacing(8)

        icon_lbl = QLabel("🖼" if item.get("type") == "image" else "🎬")
        icon_lbl.setFixedWidth(20)
        icon_lbl.setStyleSheet("font-size: 14px; background: transparent;")
        rl.addWidget(icon_lbl)

        info = QVBoxLayout()
        name_lbl = QLabel(item.get("name", ""))
        name_lbl.setStyleSheet("color: #e0e0e0; font-size: 11px; background: transparent;")
        info.addWidget(name_lbl)
        size_lbl = QLabel(item.get("size", ""))
        size_lbl.setStyleSheet("color: #555; font-size: 10px; background: transparent;")
        info.addWidget(size_lbl)
        rl.addLayout(info, 1)

        status_lbl = QLabel("✅ Descărcat" if is_cached else "☁ În cloud")
        status_lbl.setStyleSheet(
            f"color: {'#4caf50' if is_cached else '#555'}; font-size: 10px; background: transparent;"
        )
        rl.addWidget(status_lbl)

        dl_btn = QPushButton("📺 Folosește" if is_cached else "⬇ Descarcă")
        dl_btn.setStyleSheet(
            "QPushButton { background: #18283a; color: #5294e2; border: 1px solid #1c3a5a; "
            "border-radius: 4px; padding: 4px 10px; font-size: 11px; }"
            "QPushButton:hover { background: #1c3a5a; }"
            "QPushButton:disabled { color: #333; border-color: #1a1a1a; }"
        )
        dl_btn.clicked.connect(
            lambda checked, i=item, sl=status_lbl, db=dl_btn:
            self._download_or_use(i, sl, db)
        )
        rl.addWidget(dl_btn)

        if is_cached:
            del_btn = QPushButton("🗑")
            del_btn.setFixedWidth(28)
            del_btn.setStyleSheet(
                "QPushButton { background: #2a1a1a; color: #f44336; border: 1px solid #3a2020; "
                "border-radius: 4px; padding: 4px; font-size: 11px; }"
                "QPushButton:hover { background: #3a2020; }"
            )
            del_btn.clicked.connect(
                lambda checked, p=cached_path, sl=status_lbl, db=dl_btn:
                self._delete_cache(p, sl, db)
            )
            rl.addWidget(del_btn)

        return w

    def _download_or_use(self, item: dict, status_lbl: QLabel, dl_btn: QPushButton):
        file_name = os.path.basename(item.get("file", ""))
        cached_path = os.path.join(MEDIA_CACHE_DIR, file_name)

        if os.path.exists(cached_path):
            self._set_as_background(cached_path)
            return

        url = CLOUD_BASE_URL + item.get("file", "")
        status_lbl.setText("Descarcă…")
        status_lbl.setStyleSheet("color: #e2a252; font-size: 10px; background: transparent;")
        dl_btn.setEnabled(False)

        def _download():
            req = urllib.request.Request(url, headers={"User-Agent": "Cantio/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            with open(cached_path, "wb") as f:
                f.write(data)
            return cached_path

        def _done(path):
            status_lbl.setText("✅ Descărcat")
            status_lbl.setStyleSheet("color: #4caf50; font-size: 10px; background: transparent;")
            dl_btn.setText("📺 Folosește")
            dl_btn.setEnabled(True)
            self._set_as_background(path)

        def _err(msg):
            status_lbl.setText("Eroare la descărcare!")
            status_lbl.setStyleSheet("color: #f44336; font-size: 10px; background: transparent;")
            dl_btn.setEnabled(True)

        self._run_bg(_download, _done, _err)

    def _delete_cache(self, path: str, status_lbl: QLabel, dl_btn: QPushButton):
        try:
            os.remove(path)
            status_lbl.setText("☁ În cloud")
            status_lbl.setStyleSheet("color: #555; font-size: 10px; background: transparent;")
            dl_btn.setText("⬇ Descarcă")
        except Exception:
            pass

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._stop_all_cameras()
        super().closeEvent(event)
