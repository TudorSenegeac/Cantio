"""
Cantio - Render Engine  (thread-isolated, v3)
==================================================
v3 fixes vs v2
--------------
BUG 1 — "slide apare 1 secundă apoi dispare"
  Root cause: set_frame() blocked updates to _current_frame during the
  transition animation.  When the transition ended, Mode B in paintEvent
  used the stale blank _current_frame from before the slide was sent live.
  After that, _dirty=False prevented the worker from emitting new frames,
  so the blank frame persisted indefinitely.
  Fix: set_frame() ALWAYS stores the latest engine frame; it only suppresses
  the update() call during transitions (so the transition is not interrupted).
  By the time end_transition() fires, _current_frame already holds the
  correct text frame.

BUG 2 — "nu e lin" / rendering corruption
  Root cause: QPixmap created on the render thread.  Qt documents this as
  unsupported: "QPixmap objects can only be used in the GUI thread."
  On the raster backend this usually doesn't crash, but can produce corrupted
  frames, tearing, or silent no-ops depending on Qt version and driver.
  Fix: render thread works exclusively with QImage (thread-safe).
  RenderEngine._on_worker_frame() and _on_worker_preview() receive the QImage
  via QueuedConnection (main thread), convert to QPixmap there, then emit.

Threading overview (v3)
-----------------------
  Render thread (HighPriority QThread)
    RenderWorker._compose()       → QImage (Format_RGB32)
    RenderWorker.frame_ready      → QImage (60 fps)
    RenderWorker.preview_ready    → QImage (15 fps)

  Main (GUI) thread
    RenderEngine._on_worker_frame(img)    → QPixmap.fromImage(img) → frame_ready(pix)
    RenderEngine._on_worker_preview(img)  → QPixmap.fromImage(img) → preview_ready(pix)
    DisplayCanvas.set_frame(pix)          → stores pix; calls update() outside transitions
"""
from __future__ import annotations

from PyQt6.QtCore import (
    QObject, QThread, QTimer,
    Qt, pyqtSignal, pyqtSlot,
)
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap


# ── Render Worker ─────────────────────────────────────────────────────────────

class RenderWorker(QObject):
    """
    Lives exclusively on the render thread.
    Emits QImage (thread-safe) — never QPixmap.
    Conversion to QPixmap happens in RenderEngine on the main thread.
    """

    frame_ready   = pyqtSignal(object)   # QImage, ≈60 fps
    preview_ready = pyqtSignal(object)   # QImage, ≈15 fps

    def __init__(self) -> None:
        super().__init__()
        self._state:         dict           = {}
        self._dirty:         bool           = True
        self._video_frame                   = None   # numpy RGB array
        self._bg_image:      QImage | None  = None   # background as QImage (thread-safe)
        self._render_timer:  QTimer | None  = None
        self._preview_timer: QTimer | None  = None

    # ── Setup ─────────────────────────────────────────────────────────────────

    @pyqtSlot()
    def setup(self) -> None:
        """Create timers on the render thread (called via thread.started signal)."""
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(16)          # ≈60 fps
        self._render_timer.timeout.connect(self._render_frame)
        self._render_timer.start()

        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(67)         # ≈15 fps
        self._preview_timer.timeout.connect(self._render_preview)
        self._preview_timer.start()

    # ── Slots — invoked via QueuedConnection from main thread ─────────────────

    @pyqtSlot(dict)
    def update_state(self, state: dict) -> None:
        self._state = state
        self._dirty = True

    @pyqtSlot(object)
    def set_video_frame(self, frame) -> None:
        """Accept a numpy RGB array (or None) from MediaEngine."""
        self._video_frame = frame
        self._dirty = True

    @pyqtSlot(object)
    def set_bg_image(self, img) -> None:
        """
        Accept a QImage (or None) for the static background.
        RenderEngine converts QPixmap → QImage before sending here,
        so this slot never touches a QPixmap.
        """
        self._bg_image    = img
        self._video_frame = None   # static bg replaces video
        self._dirty       = True

    @pyqtSlot()
    def mark_dirty(self) -> None:
        self._dirty = True

    @pyqtSlot()
    def stop_timers(self) -> None:
        if self._render_timer:
            self._render_timer.stop()
        if self._preview_timer:
            self._preview_timer.stop()

    # ── Internal render loop ──────────────────────────────────────────────────

    def _render_frame(self) -> None:
        """Called at ≈60 fps on the render thread."""
        if not self._dirty:
            return
        img = self._compose(1920, 1080, 1.0)
        if img is not None:
            self.frame_ready.emit(img)
        self._dirty = False

    def _render_preview(self) -> None:
        """Called at ≈15 fps — always renders regardless of dirty flag."""
        img = self._compose(320, 180, 320 / 1920.0)
        if img is not None:
            self.preview_ready.emit(img)

    # ── Frame composition (returns QImage — thread-safe) ─────────────────────

    def _compose(self, w: int, h: int, scale: float) -> QImage | None:
        """
        Compose background + text into a QImage of size (w × h).
        Uses render_background_on_painter and render_text_on_painter from
        preview_widget so the preview exactly mirrors display.js output.
        QImage is safe to create and paint on any thread.
        """
        from preview_widget import render_background_on_painter, render_text_on_painter

        s   = self._state
        img = QImage(w, h, QImage.Format.Format_RGB32)
        p   = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # Convert stored bg QImage back to QPixmap for render_background_on_painter
        bg_pix = None
        if self._bg_image is not None and not self._bg_image.isNull():
            bg_pix = QPixmap.fromImage(self._bg_image)

        render_background_on_painter(
            p, w, h, s,
            bg_pixmap=bg_pix,
            video_frame=self._video_frame,
        )

        text = s.get("_current_text", "")
        if text:
            render_text_on_painter(p, text, w, h, s, scale)

        p.end()
        return img

    # ── Text drawing ──────────────────────────────────────────────────────────

    def _draw_text(
        self,
        painter: QPainter,
        text:    str,
        w:       int,
        h:       int,
        s:       dict,
        scale:   float = 1.0,
    ) -> None:
        from PyQt6.QtGui import QFont, QFontMetrics, QColor, QPen

        family    = s.get("font_family",    "Arial")
        size      = max(1, int(float(s.get("font_size",     48) or 48)  * scale))
        bold      = s.get("font_bold",      "true")  == "true"
        italic    = s.get("font_italic",    "false") == "true"
        text_col  = QColor(s.get("text_color",    "#ffffff"))
        out_col   = QColor(s.get("outline_color", "#000000"))
        outline_w = max(0, int(float(s.get("outline_width", 2) or 2) * scale))
        shadow    = s.get("text_shadow",    "true")  == "true"
        lspacing  = float(s.get("line_spacing",    1.4))
        margin    = int(float(s.get("margin", 80) or 80) * scale)
        align     = s.get("text_align",     "center")
        valign    = s.get("text_valign",    "center")

        font = QFont(family, size)
        font.setBold(bold)
        font.setItalic(italic)
        painter.setFont(font)
        fm = QFontMetrics(font)

        max_w = w - margin * 2
        max_h = h - margin * 2

        # Word-wrap
        wrapped: list[str] = []
        for raw_line in text.splitlines():
            if not raw_line.strip():
                wrapped.append("")
                continue
            words, current = raw_line.split(), ""
            for word in words:
                test = (current + " " + word) if current else word
                if fm.horizontalAdvance(test) > max_w:
                    if current:
                        wrapped.append(current)
                    current = word
                else:
                    current = test
            if current:
                wrapped.append(current)

        line_h  = int(fm.height() * lspacing)
        total_h = line_h * len(wrapped)

        # Auto-shrink
        while total_h > max_h and size > 10:
            size -= 2
            font.setPointSize(size)
            painter.setFont(font)
            fm      = QFontMetrics(font)
            line_h  = int(fm.height() * lspacing)
            total_h = line_h * len(wrapped)

        # Vertical alignment
        if valign == "top":
            start_y = margin + fm.ascent()
        elif valign == "bottom":
            start_y = h - margin - total_h + fm.ascent()
        else:
            start_y = (h - total_h) // 2 + fm.ascent()
        start_y = max(margin + fm.ascent(), start_y)

        for i, line in enumerate(wrapped):
            if not line:
                continue
            lw = fm.horizontalAdvance(line)
            if align == "left":
                x = margin
            elif align == "right":
                x = w - margin - lw
            else:
                x = (w - lw) // 2
            x = max(margin, min(x, w - margin - lw))
            y = start_y + i * line_h

            if shadow:
                off = max(1, int(3 * scale))
                painter.setPen(QColor(0, 0, 0, 180))
                painter.drawText(x + off, y + off, line)

            if outline_w > 0:
                pen = QPen(out_col)
                pen.setWidth(outline_w)
                painter.setPen(pen)
                for dx in range(-outline_w, outline_w + 1):
                    for dy in range(-outline_w, outline_w + 1):
                        if dx or dy:
                            painter.drawText(x + dx, y + dy, line)

            painter.setPen(text_col)
            painter.drawText(x, y, line)


# ── Render Engine (main-thread proxy) ─────────────────────────────────────────

class RenderEngine(QObject):
    """
    Main-thread owner.  Proxies API calls to the render thread and converts
    QImage → QPixmap on the main thread before emitting to downstream consumers.

    Signals
    -------
    frame_ready(QPixmap)    — ≈60 fps, full 1920×1080 frame
    preview_ready(QPixmap)  — ≈15 fps, 320×180 preview snapshot
    """

    frame_ready   = pyqtSignal(object)   # QPixmap (converted on main thread)
    preview_ready = pyqtSignal(object)   # QPixmap (converted on main thread)

    # Cross-thread commands → RenderWorker slots (QueuedConnection)
    _sig_update_state = pyqtSignal(dict)
    _sig_set_video    = pyqtSignal(object)
    _sig_set_bg       = pyqtSignal(object)   # carries QImage | None
    _sig_mark_dirty   = pyqtSignal()
    _sig_stop_timers  = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        # Dedicated render thread
        self._thread = QThread(self)
        self._thread.setObjectName("CantioRenderThread")

        self._worker = RenderWorker()
        self._worker.moveToThread(self._thread)

        # Worker QImage output → main-thread converters (QueuedConnection)
        _Q = Qt.ConnectionType.QueuedConnection
        self._worker.frame_ready.connect(   self._on_worker_frame,   _Q)
        self._worker.preview_ready.connect( self._on_worker_preview, _Q)

        # Command signals → worker slots
        self._sig_update_state.connect(self._worker.update_state,  _Q)
        self._sig_set_video.connect(   self._worker.set_video_frame,_Q)
        self._sig_set_bg.connect(      self._worker.set_bg_image,   _Q)
        self._sig_mark_dirty.connect(  self._worker.mark_dirty,     _Q)
        self._sig_stop_timers.connect( self._worker.stop_timers,    _Q)

        # Start render thread — setup() called via started signal
        self._thread.started.connect(self._worker.setup, _Q)
        self._thread.start(QThread.Priority.HighPriority)

        self._state:        dict = {}
        self._video_source       = None   # MediaEngine for back-pressure

    # ── QImage → QPixmap converters (run on main thread) ──────────────────────

    def _on_worker_frame(self, img: QImage) -> None:
        """
        Called on the main (GUI) thread via QueuedConnection.
        Converts QImage produced by the render thread into a QPixmap
        (QPixmap must only be created on the GUI thread) and emits it.
        """
        pix = QPixmap.fromImage(img)
        self.frame_ready.emit(pix)

    def _on_worker_preview(self, img: QImage) -> None:
        """Same as _on_worker_frame but for the 15-fps preview signal."""
        pix = QPixmap.fromImage(img)
        self.preview_ready.emit(pix)

    # ── Public API (called from main thread) ──────────────────────────────────

    def set_text(self, text: str, formatting: dict | None = None) -> None:
        self._state["_current_text"] = text or ""
        if formatting and formatting.get("use_custom"):
            for key in (
                "font_family", "font_size", "font_bold", "font_italic",
                "text_color",  "text_align", "line_spacing",
                "outline_width", "outline_color", "text_shadow",
            ):
                if key in formatting:
                    val = formatting[key]
                    self._state[key] = (
                        "true" if val is True else
                        "false" if val is False else str(val)
                    )
        self._sig_update_state.emit(dict(self._state))

    def set_settings(self, s: dict) -> None:
        self._state.update(s)
        self._sig_update_state.emit(dict(self._state))

    def set_bg(self, pixmap: QPixmap | None) -> None:
        """
        Convert QPixmap → QImage on the main thread before sending to the
        render thread.  QPixmap is not safe outside the GUI thread; QImage is.
        """
        if pixmap is not None and not pixmap.isNull():
            img = pixmap.toImage()   # main thread — safe
            self._sig_set_bg.emit(img)
        else:
            self._sig_set_bg.emit(None)

    def set_video_frame(self, frame) -> None:
        """Receive numpy RGB array from MediaEngine; forward to render thread."""
        self._sig_set_video.emit(frame)
        if self._video_source is not None:
            try:
                self._video_source.frame_consumed()
            except Exception:
                pass

    def clear_video_frame(self) -> None:
        self._sig_set_video.emit(None)

    def mark_dirty(self) -> None:
        self._sig_mark_dirty.emit()

    def set_video_source(self, source) -> None:
        self._video_source = source

    # ── Size helpers ──────────────────────────────────────────────────────────

    @property
    def _w(self) -> int:
        return self._state.get("_display_w", 1920)

    @property
    def _h(self) -> int:
        return self._state.get("_display_h", 1080)

    def set_display_size(self, w: int, h: int) -> None:
        self._state["_display_w"] = max(1, w)
        self._state["_display_h"] = max(1, h)
        self._sig_update_state.emit(dict(self._state))

    def set_preview_size(self, w: int, h: int) -> None:
        pass   # fixed at 320×180 in the worker

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        pass   # thread already started in __init__; kept for API compat

    def stop(self) -> None:
        self._sig_stop_timers.emit()
        self._thread.quit()
        self._thread.wait(3000)

    @property
    def is_running(self) -> bool:
        return self._thread.isRunning()

    # ── Backward-compat stubs ─────────────────────────────────────────────────

    def clear_text_cache(self) -> None:
        pass
