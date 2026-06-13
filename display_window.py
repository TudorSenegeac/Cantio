"""
Cantio - Display Window  (v4 — complet separat)
====================================================
Separare TOTALĂ faţă de SlideThumbnail şi PreviewWidget:

  DisplayCanvas  — randează totul în paintEvent() propriu.
                   Nu foloseşte LiveState, renderer.py, RenderEngine.
                   Nu este shared cu nimeni.

  DisplayWindow  — gestionează canvas, background, animaţii fereastră.
                   show_text() → canvas.show_text() direct.
                   API backward-compatible cu control_window.py existent.

Preview-ul (PreviewWidget) rămâne conectat la RenderEngine.preview_ready
şi la LiveState — complet separat de display.
"""
from __future__ import annotations

import json
import os
import time as _time
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QFontMetrics, QImage, QLinearGradient, QPen,
    QPainter, QPixmap,
)
from PyQt6.QtWidgets import QMainWindow, QWidget


# ── VideoFrameThread — import din media_engine dacă există ────────────────────

try:
    from media_engine import VideoDecodeThread as VideoFrameThread
    HAS_VIDEO_THREAD = True
except ImportError:
    VideoFrameThread  = None          # type: ignore[assignment,misc]
    HAS_VIDEO_THREAD  = False


# ── Backward-compat stubs (control_window le poate referenţia ca atribute) ───

class LyricsWidget:
    """Stub — randarea s-a mutat în DisplayCanvas."""
    def __init__(self, parent=None):
        self._opacity = 1.0

    @pyqtProperty(float)
    def opacity(self): return self._opacity

    @opacity.setter
    def opacity(self, val): self._opacity = val

    def set_text(self, text): pass
    def apply_settings(self, s): pass


class TickerBar:
    """Stub — ticker condus de DisplayCanvas."""
    def __init__(self, parent=None): pass
    def set_ticker(self, text, speed=2, color="#ffffff"): pass


class ClockOverlay:
    """Stub — ceas condus de DisplayCanvas."""
    def __init__(self, parent=None): pass
    def set_visible(self, visible, color="#ffffff", fmt="HH:MM:SS"): pass


class CountdownOverlay:
    """Stub — countdown condus de DisplayCanvas."""
    def __init__(self, parent=None): pass
    def start_countdown(self, seconds, color="#ffffff"): pass
    def stop_countdown(self): pass


# ── Durate tranziţii ──────────────────────────────────────────────────────────

_TRANSITION_DURATIONS: dict[str, int] = {
    "fade":       500,
    "crossfade":  350,
    "slide_left": 350,
    "zoom_in":    400,
}


# ════════════════════════════════════════════════════════════════════════════════
# DisplayCanvas — suprafaţă de randare, complet independentă
# ════════════════════════════════════════════════════════════════════════════════

class DisplayCanvas(QWidget):
    """
    Randează totul direct în paintEvent().
    Nu împarte niciun obiect / renderer cu SlideThumbnail sau PreviewWidget.
    Starea (text, background, tranziţie, overlay-uri) este PROPRIE.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

        # ── Stare proprie ─────────────────────────────────────────────────────
        self.settings:     dict            = {}
        self.lyrics_text:  str             = ""
        self._bg_pixmap:   QPixmap | None  = None
        self._video_frame                  = None   # numpy RGB array
        self._pres_pix:    QPixmap | None  = None   # slide prezentare
        self._show_pres:   bool            = False

        # Metadata copyright (setat din DisplayWindow.show_text)
        self._current_title:    str = ""
        self._current_author:   str = ""
        self._current_category: str = ""
        self._current_source:   str = ""

        # ── Tranziţie ─────────────────────────────────────────────────────────
        self._old_text:   str   = ""
        self._progress:   float = 1.0
        self._transition: str   = "crossfade"
        self._elapsed:    int   = 0
        self._duration:   int   = 350

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)          # ≈60 fps
        self._anim_timer.timeout.connect(self._anim_step)

        # ── Overlay-uri ───────────────────────────────────────────────────────
        self.ticker_text:    str   = ""
        self.ticker_active:  bool  = False
        self._ticker_x:      float = 0.0
        self._ticker_speed:  float = 2.5

        self.show_clock:      bool  = False
        self.show_timer:      bool  = False
        self._timer_seconds:  int   = 0
        self._timer_running:  bool  = False
        self._timer_start:    float = 0.0

        self.logo_active:   bool            = False
        self._logo_pixmap:  QPixmap | None  = None
        self.projector_off: bool            = False

        # Ticker timer (animaţie scroll)
        self._ticker_timer = QTimer(self)
        self._ticker_timer.setInterval(16)
        self._ticker_timer.timeout.connect(self._tick)
        self._ticker_timer.start()

        # Clock/timer refresh
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(500)
        self._clock_timer.timeout.connect(self.update)
        self._clock_timer.start()

    # ── Backward-compat stub (control_window._distribute_frame apelează asta) ─

    def set_frame(self, pixmap) -> None:
        """No-op — display-ul randează direct, nu mai foloseşte frame-uri din RenderEngine."""
        pass

    # Stubs suplimentare pentru compatibilitate cu cod vechi
    def set_bg(self, pixmap) -> None:            pass
    def set_new_pix(self, pixmap) -> None:       pass
    def begin_transition(self, *a, **kw) -> None: pass
    def end_transition(self) -> None:            pass
    def set_progress(self, p: float) -> None:    pass
    def anim_active(self) -> bool:               return 0.0 <= self._progress < 1.0
    def clear_text_cache(self) -> None:          pass
    def cache_text_pix(self, *a) -> None:        pass
    def get_cached_text(self, key) -> None:      return None  # type: ignore[return-value]
    def set_copyright_fn(self, fn) -> None:      pass
    def set_pres(self, pixmap, visible: bool) -> None:
        self._pres_pix   = pixmap
        self._show_pres  = visible
        self.update()

    # ── Setări ────────────────────────────────────────────────────────────────

    def apply_settings(self, s: dict) -> None:
        self.settings = s
        # Actualizează durata tranziţiei din setări
        self._duration = int(s.get("transition_duration", self._duration))
        self.update()

    # ── Background ────────────────────────────────────────────────────────────

    def set_bg_pixmap(self, pix: QPixmap | None) -> None:
        self._bg_pixmap   = pix
        self._video_frame = None
        self.update()

    def set_video_frame(self, frame) -> None:
        """Primeşte numpy RGB array din VideoFrameThread."""
        self._video_frame = frame
        self.update()

    # ── Text + tranziţie ──────────────────────────────────────────────────────

    def show_text(self, text: str) -> None:
        t = self.settings.get("transition", "crossfade")

        if t == "instant" or t not in _TRANSITION_DURATIONS:
            self._anim_timer.stop()
            self.lyrics_text = text
            self._progress   = 1.0
            self._old_text   = ""
            self.update()
            return

        self._anim_timer.stop()
        self._old_text    = self.lyrics_text
        self.lyrics_text  = text
        self._transition  = t
        # Durată din setări (prioritate) sau din tabelul implicit
        self._duration    = int(
            self.settings.get("transition_duration",
                               _TRANSITION_DURATIONS.get(t, 350))
        )
        self._progress    = 0.0
        self._elapsed     = 0
        self._anim_timer.start()

    def _anim_step(self) -> None:
        self._elapsed += 16
        p = min(self._elapsed / self._duration, 1.0)
        self._progress = 1.0 - (1.0 - p) ** 3   # OutCubic easing
        self.update()
        if p >= 1.0:
            self._anim_timer.stop()
            self._old_text = ""

    # ── Ticker ────────────────────────────────────────────────────────────────

    def _tick(self) -> None:
        if not (self.ticker_active and self.ticker_text):
            return
        self._ticker_x -= self._ticker_speed
        fm = QFontMetrics(QFont("Arial", 20, QFont.Weight.Bold))
        if self._ticker_x < -fm.horizontalAdvance(self.ticker_text):
            self._ticker_x = float(self.width())
        self.update()

    def show_ticker(self, text: str, speed: float = 2.5) -> None:
        self.ticker_text   = text
        self.ticker_active = bool(text)
        self._ticker_x     = float(self.width())
        self._ticker_speed = speed
        if not text:
            self.update()

    def hide_ticker(self) -> None:
        self.ticker_active = False
        self.ticker_text   = ""
        self.update()

    # ── Ceas / Cronometru ─────────────────────────────────────────────────────

    def toggle_clock(self, v: bool) -> None:
        self.show_clock = bool(v)
        self.update()

    def start_timer(self, seconds: int) -> None:
        self._timer_seconds = int(seconds)
        self._timer_start   = _time.monotonic()
        self._timer_running = True
        self.show_timer     = True
        self.update()

    def stop_timer(self) -> None:
        self._timer_running = False
        self.show_timer     = False
        self.update()

    # ── Logo ──────────────────────────────────────────────────────────────────

    def set_logo(self, pixmap: QPixmap | None, active: bool) -> None:
        self._logo_pixmap = pixmap
        self.logo_active  = bool(active)
        self.update()

    # ── Projector off ─────────────────────────────────────────────────────────

    def set_projector_off(self, v: bool) -> None:
        self.projector_off = bool(v)
        self.update()

    # ════════════════════════════════════════════════════════════════════════════
    # paintEvent — randare directă, fără shared state
    # ════════════════════════════════════════════════════════════════════════════

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w, h = self.width(), self.height()
        s    = self.settings

        # ── 1. Slide prezentare (prioritate maximă) ───────────────────────────
        if self._show_pres and self._pres_pix and not self._pres_pix.isNull():
            painter.drawPixmap(0, 0, self._pres_pix)
            self._draw_overlays(painter, w, h)
            painter.end()
            return

        # ── 2. Proiector oprit — negru total ──────────────────────────────────
        if self.projector_off:
            painter.fillRect(0, 0, w, h, QColor("#000000"))
            painter.end()
            return

        # ── 3. Background ─────────────────────────────────────────────────────
        painter.fillRect(0, 0, w, h, QColor(s.get("bg_color", "#000000")))

        if self._video_frame is not None:
            try:
                fr      = self._video_frame
                fh, fw  = fr.shape[:2]
                img     = QImage(fr.data, fw, fh, fw * 3, QImage.Format.Format_RGB888)
                op      = float(s.get("bg_opacity", 1.0))
                painter.setOpacity(op)
                painter.drawPixmap(0, 0, QPixmap.fromImage(img).scaled(
                    w, h,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.FastTransformation,
                ))
                painter.setOpacity(1.0)
            except Exception:
                pass
        elif self._bg_pixmap and not self._bg_pixmap.isNull():
            op = float(s.get("bg_opacity", 0.85))
            painter.setOpacity(op)
            painter.drawPixmap(0, 0, self._bg_pixmap.scaled(
                w, h,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.FastTransformation,
            ))
            painter.setOpacity(1.0)

        # ── 4. Logo screen ─────────────────────────────────────────────────────
        if self.logo_active and self._logo_pixmap and not self._logo_pixmap.isNull():
            painter.drawPixmap(0, 0, self._logo_pixmap.scaled(
                w, h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
            self._draw_overlays(painter, w, h)
            painter.end()
            return

        # ── 5. Text cu tranziţie ──────────────────────────────────────────────
        prog  = self._progress
        trans = self._transition

        if prog >= 1.0:
            # Fără animaţie — arată textul curent
            if self.lyrics_text:
                self._paint_text(painter, self.lyrics_text, w, h, 1.0)

        elif trans == "crossfade":
            if self._old_text:
                self._paint_text(painter, self._old_text,  w, h, 1.0 - prog)
            if self.lyrics_text:
                self._paint_text(painter, self.lyrics_text, w, h, prog)

        elif trans == "fade":
            if prog < 0.5:
                if self._old_text:
                    self._paint_text(painter, self._old_text,  w, h, 1.0 - prog * 2)
            else:
                if self.lyrics_text:
                    self._paint_text(painter, self.lyrics_text, w, h, (prog - 0.5) * 2)

        elif trans == "slide_left":
            dx = int(prog * w)
            if self._old_text:
                self._paint_text(painter, self._old_text,  w, h, 1.0, offset_x=-dx)
            if self.lyrics_text:
                self._paint_text(painter, self.lyrics_text, w, h, 1.0, offset_x=w - dx)

        elif trans == "zoom_in":
            cx, cy = w / 2.0, h / 2.0
            if self._old_text:
                sc = 1.0 + prog * 0.06
                painter.setOpacity(1.0 - prog)
                painter.save()
                painter.translate(cx, cy)
                painter.scale(sc, sc)
                painter.translate(-cx, -cy)
                self._paint_text(painter, self._old_text, w, h, 1.0)
                painter.restore()
            if self.lyrics_text:
                sc = 0.94 + prog * 0.06
                painter.setOpacity(prog)
                painter.save()
                painter.translate(cx, cy)
                painter.scale(sc, sc)
                painter.translate(-cx, -cy)
                self._paint_text(painter, self.lyrics_text, w, h, 1.0)
                painter.restore()
            painter.setOpacity(1.0)

        else:
            # Fallback
            if self.lyrics_text:
                self._paint_text(painter, self.lyrics_text, w, h, 1.0)

        # ── 6. Overlay-uri ────────────────────────────────────────────────────
        self._draw_overlays(painter, w, h)
        painter.end()

    # ── Randare text ──────────────────────────────────────────────────────────

    def _paint_text(
        self,
        painter:  QPainter,
        text:     str,
        w:        int,
        h:        int,
        opacity:  float,
        offset_x: int = 0,
        offset_y: int = 0,
    ) -> None:
        if not text:
            return

        s         = self.settings
        family    = s.get("font_family",    "Arial")
        size      = max(1, int(s.get("font_size",     48)))
        bold      = s.get("font_bold",      "true")  == "true"
        italic    = s.get("font_italic",    "false") == "true"
        text_col  = QColor(s.get("text_color",    "#ffffff"))
        out_col   = QColor(s.get("outline_color", "#000000"))
        outline_w = max(0, int(s.get("outline_width", 2)))
        shadow    = s.get("text_shadow",    "true")  == "true"
        lspacing  = float(s.get("line_spacing",    1.4))
        margin    = int(s.get("margin",     80))
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

        # Aliniere verticală
        if valign == "top":
            start_y = margin + fm.ascent()
        elif valign == "bottom":
            start_y = h - margin - total_h + fm.ascent()
        else:
            start_y = (h - total_h) // 2 + fm.ascent()
        start_y = max(margin + fm.ascent(), start_y)

        painter.setOpacity(opacity)

        for i, line in enumerate(wrapped):
            if not line:
                continue
            lw = fm.horizontalAdvance(line)
            if align == "left":
                x = margin + offset_x
            elif align == "right":
                x = w - margin - lw + offset_x
            else:
                x = (w - lw) // 2 + offset_x
            y = start_y + i * line_h + offset_y

            if shadow:
                painter.setPen(QColor(0, 0, 0, 180))
                painter.drawText(x + 3, y + 3, line)

            if outline_w > 0:
                pen = QPen(out_col)
                pen.setWidth(outline_w)
                painter.setPen(pen)
                for ddx in range(-outline_w, outline_w + 1):
                    for ddy in range(-outline_w, outline_w + 1):
                        if ddx or ddy:
                            painter.drawText(x + ddx, y + ddy, line)

            painter.setPen(text_col)
            painter.drawText(x, y, line)

        painter.setOpacity(1.0)

    # ── Overlay-uri ───────────────────────────────────────────────────────────

    def _draw_overlays(self, p: QPainter, w: int, h: int) -> None:
        s = self.settings

        # Ceas
        if self.show_clock:
            self._draw_corner_text(
                p, datetime.now().strftime("%H:%M:%S"), w, h, "top-right", "#ffffff"
            )

        # Cronometru
        if self.show_timer:
            elapsed   = int(_time.monotonic() - self._timer_start) if self._timer_running else 0
            remaining = max(0, self._timer_seconds - elapsed)
            m, sec    = divmod(remaining, 60)
            color     = "#ff5555" if remaining == 0 else "#a6e3a1"
            self._draw_corner_text(p, f"{m:02d}:{sec:02d}", w, h, "top-left", color)

        # Ticker
        if self.ticker_active and self.ticker_text:
            bar_h = 52
            y0    = h - bar_h
            grad  = QLinearGradient(0, y0, 0, h)
            grad.setColorAt(0, QColor(0,  0,  0,  190))
            grad.setColorAt(1, QColor(10, 5,  30, 240))
            p.fillRect(0, y0, w, bar_h, QBrush(grad))
            p.setPen(QPen(QColor("#cba6f7"), 2))
            p.drawLine(0, y0, w, y0)
            font = QFont("Arial", 20, QFont.Weight.Bold)
            p.setFont(font)
            fm   = QFontMetrics(font)
            ty   = y0 + (bar_h + fm.ascent() - fm.descent()) // 2
            p.setPen(QColor(0, 0, 0, 160))
            p.drawText(int(self._ticker_x) + 2, ty + 2, self.ticker_text)
            p.setPen(QColor("#f9e2af"))
            p.drawText(int(self._ticker_x), ty, self.ticker_text)

        # Copyright
        self._draw_copyright(p, w, h)

    def _draw_corner_text(
        self, p: QPainter, text: str, w: int, h: int, corner: str, color: str
    ) -> None:
        font = QFont("Consolas", 22, QFont.Weight.Bold)
        p.setFont(font)
        fm  = QFontMetrics(font)
        tw  = fm.horizontalAdvance(text)
        pad = 18
        if corner == "top-right":
            x, y = w - tw - pad, pad + fm.ascent()
        else:
            x, y = pad, pad + fm.ascent()
        p.setPen(QColor(0, 0, 0, 200))
        p.drawText(x + 2, y + 2, text)
        p.setPen(QColor(color))
        p.drawText(x, y, text)

    def _draw_copyright(self, p: QPainter, w: int, h: int) -> None:
        s      = self.settings
        cr_raw = s.get("copyright", "{}")
        try:
            cr = json.loads(cr_raw) if isinstance(cr_raw, str) else (cr_raw or {})
        except Exception:
            cr = {}
        if not cr.get("enabled", False):
            return

        mode = cr.get("mode", "title_author")
        if mode == "title":
            text = self._current_title
        elif mode == "author":
            text = self._current_author
        elif mode == "title_author":
            parts = []
            if self._current_title:
                parts.append(self._current_title)
            if self._current_author:
                parts.append(f"— {self._current_author}")
            text = "  ".join(parts)
        elif mode == "category":
            text = self._current_category
        elif mode == "source":
            text = self._current_source
        elif mode == "custom":
            text = cr.get("custom_text", "")
        else:
            text = self._current_title

        if not text:
            return

        font = QFont("Arial", max(8, int(cr.get("font_size", 12))))
        p.setFont(font)
        fm  = QFontMetrics(font)
        tw  = fm.horizontalAdvance(text)
        pad = 16
        pos = cr.get("position", "bottom_right")

        positions = {
            "bottom_right":  (w - tw - pad,   h - pad - 4),
            "bottom_left":   (pad,             h - pad - 4),
            "bottom_center": ((w - tw) // 2,   h - pad - 4),
            "top_right":     (w - tw - pad,    pad + fm.height()),
            "top_left":      (pad,             pad + fm.height()),
        }
        x, y = positions.get(pos, (w - tw - pad, h - pad - 4))

        op = float(cr.get("opacity", 0.4))
        p.setOpacity(op * 0.4)
        p.setPen(QColor(0, 0, 0))
        p.drawText(x + 1, y + 1, text)
        p.setOpacity(op)
        p.setPen(QColor(cr.get("color", "#ffffff")))
        p.drawText(x, y, text)
        p.setOpacity(1.0)


# ════════════════════════════════════════════════════════════════════════════════
# DisplayWindow — fereastră fullscreen, complet separată
# ════════════════════════════════════════════════════════════════════════════════

class DisplayWindow(QMainWindow):
    """
    Fereastră de proiecţie fullscreen.
    show_text() apelează direct canvas.show_text() — fără RenderEngine,
    fără LiveState, fără alte intermediare.
    """

    def __init__(
        self,
        screen   = None,
        settings = None,
        window_id: int  = 1,
        window_name: str | None = None,
        fullscreen:  bool = True,
    ):
        super().__init__()

        self.window_id        = window_id
        self.window_name      = window_name or f"Display {window_id}"
        self.settings         = settings or {}
        self._fullscreen_flag = fullscreen
        self._frozen          = False
        self._closing         = False
        self._transparent     = False
        self._in_presentation_mode = False
        self._video_thread    = None
        self._opening_anim    = None
        self._close_anim      = None

        self.setWindowTitle(f"Cantio — {self.window_name}")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )

        # ── Canvas PROPRIU — nu shared cu nimeni ──────────────────────────────
        self.canvas = DisplayCanvas(self)
        self.setCentralWidget(self.canvas)
        self.view = self.canvas   # alias backward-compat

        # Atribute stub pentru compat cu cod vechi care le referenţiază
        self.lyrics    = LyricsWidget()
        self.clock     = ClockOverlay()
        self.countdown = CountdownOverlay()
        self.ticker    = TickerBar()

        # Aplică setări şi background
        self.canvas.apply_settings(self.settings)
        self._apply_background()

        # Poziţionare pe ecran
        if screen:
            self.setGeometry(screen.geometry())

        # Start transparent — fadeIn în showEvent
        self.setWindowOpacity(0.0)
        if self._fullscreen_flag:
            self.showFullScreen()
        else:
            self.show()

    # ── Fade-in la deschidere ─────────────────────────────────────────────────

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not getattr(self, '_shown_once', False):
            self._shown_once = True
            anim = QPropertyAnimation(self, b"windowOpacity")
            anim.setDuration(500)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.start()
            self._opening_anim = anim   # referinţă — altfel GC

    # ── Setări ────────────────────────────────────────────────────────────────

    def apply_settings(self, s: dict) -> None:
        self.settings = s

        # Transparent / chroma-key window mode
        if s.get("bg_transparent") == "true":
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
            )
            self.show()
        else:
            # Restore normal window attributes if previously transparent
            cur_flags = self.windowFlags()
            if cur_flags & Qt.WindowType.FramelessWindowHint:
                self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
                self.setWindowFlags(
                    Qt.WindowType.Window
                    | Qt.WindowType.WindowStaysOnTopHint
                )
                self.show()

        self.canvas.apply_settings(s)
        self._apply_background()

    # ── Background (imagine statică sau video) ─────────────────────────────────

    def _apply_background(self) -> None:
        bg       = self.settings.get("bg_image",  "")
        bg_video = self.settings.get("bg_video",  "")

        # Opreşte thread video anterior
        if self._video_thread is not None:
            try:
                self._video_thread.stop()
            except Exception:
                pass
            self._video_thread = None

        # Alege sursa video
        video_src = ""
        if bg_video and os.path.exists(bg_video):
            video_src = bg_video
        elif bg:
            ext = os.path.splitext(bg)[1].lower()
            if ext in ('.mp4', '.mov', '.avi', '.mkv') and os.path.exists(bg):
                video_src = bg

        if video_src and HAS_VIDEO_THREAD and VideoFrameThread is not None:
            t = VideoFrameThread(video_src)
            t.frame_ready.connect(self.canvas.set_video_frame)
            t.start()
            self._video_thread = t
            self.canvas.set_bg_pixmap(None)
            return

        # Imagine statică
        if bg and os.path.exists(bg):
            ext = os.path.splitext(bg)[1].lower()
            if ext not in ('.mp4', '.mov', '.avi', '.mkv'):
                pix = QPixmap(bg)
                self.canvas.set_bg_pixmap(pix if not pix.isNull() else None)
                return

        self.canvas.set_bg_pixmap(None)

    # ── API principal ─────────────────────────────────────────────────────────

    def show_text(self, text: str, formatting=None, metadata=None) -> None:
        """
        Trimite text pe ecran.
        formatting şi metadata sunt acceptate (backward-compat) dar nu mai
        controlează randarea — DisplayCanvas foloseşte propriile setări.
        metadata este totuşi stocat pentru copyright overlay.
        """
        if self._frozen:
            return

        # Metadata copyright
        if metadata:
            self.canvas._current_title    = metadata.get("title",    "")
            self.canvas._current_author   = metadata.get("author",   "")
            self.canvas._current_category = metadata.get("category", "")
            self.canvas._current_source   = metadata.get("source",   "")

        # Ieşire din modul prezentare
        if self._in_presentation_mode:
            self._in_presentation_mode = False
            self.canvas.set_pres(None, False)

        # Sacred-words substitution
        s = self.settings
        if s.get("sacred_words_enabled", "false") == "true" and text:
            try:
                from text_utils import apply_sacred_caps
                words   = [w.strip() for w in s.get("sacred_words", "").split(",") if w.strip()]
                allcaps = s.get("sacred_words_allcaps", "false") == "true"
                text    = apply_sacred_caps(text, words, allcaps)
            except Exception:
                pass

        self.canvas.show_text(text)

    def black_screen(self) -> None:
        self.canvas.show_text("")

    def clear_screen(self) -> None:
        self.black_screen()

    def show_slide_image(self, pixmap: QPixmap) -> None:
        """Afişează un slide de prezentare ca imagine fullscreen."""
        if self._frozen:
            return
        self._in_presentation_mode = True
        w, h = self.width(), self.height()
        if w > 0 and h > 0:
            scaled = pixmap.scaled(
                w, h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.canvas.set_pres(scaled, True)

    # ── Freeze / Logo / Transparent ───────────────────────────────────────────

    def freeze_black(self) -> None:
        """Blochează complet ieşirea — ecran negru."""
        self._frozen = True
        self.canvas.set_projector_off(True)

    def unfreeze(self) -> None:
        """Reia operarea normală."""
        self._frozen = False
        self.canvas.set_projector_off(False)

    def is_frozen(self) -> bool:
        return self._frozen

    def show_logo(self, pixmap: QPixmap) -> None:
        if pixmap and not pixmap.isNull():
            self.canvas.set_logo(pixmap, True)

    def hide_logo(self) -> None:
        self.canvas.set_logo(None, False)

    def toggle_transparent(self) -> bool:
        """Toggle fundal transparent (OBS chroma-key)."""
        self._transparent = not self._transparent
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, self._transparent)
        self.canvas.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, self._transparent)
        return self._transparent

    def grab_frame(self) -> QPixmap:
        """Captează conţinutul curent ca pixmap (virtual camera / preview)."""
        return self.grab()

    # ── Ticker / Ceas / Countdown ─────────────────────────────────────────────

    def set_ticker(self, text: str, speed=2, color="#ffffff") -> None:
        if text:
            self.canvas.show_ticker(text, float(speed))
        else:
            self.canvas.hide_ticker()

    def toggle_clock(self, enabled: bool, color="#ffffff", fmt="HH:MM:SS") -> None:
        self.canvas.toggle_clock(bool(enabled))

    def start_countdown(self, seconds, color="#ffffff") -> None:
        self.canvas.start_timer(int(seconds))

    def stop_countdown(self) -> None:
        self.canvas.stop_timer()

    # ── Compatibilitate cu metode noi / viitoare ──────────────────────────────

    def render_text_to_pixmap(self, text, w, h, formatting=None) -> QPixmap:
        """Stub backward-compat — randarea e acum în DisplayCanvas.paintEvent."""
        pix = QPixmap(w, h)
        pix.fill(QColor("#000000"))
        return pix

    def render_bg_to_pixmap(self, w: int, h: int) -> QPixmap:
        """Stub backward-compat."""
        pix = QPixmap(w, h)
        pix.fill(QColor(self.settings.get("bg_color", "#000000")))
        return pix

    # ── Închidere ─────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        if self._closing:
            event.accept()
            return

        event.ignore()
        self._closing = True

        # Opreşte thread-ul video
        if self._video_thread is not None:
            try:
                self._video_thread.stop()
            except Exception:
                pass
            self._video_thread = None

        # Fade-out fereastra, apoi închide
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(400)
        anim.setStartValue(self.windowOpacity())
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        anim.finished.connect(self._do_close)
        anim.start()
        self._close_anim = anim   # referinţă — altfel GC

    def _do_close(self) -> None:
        self.close()
