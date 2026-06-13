"""
Cantio - Toast Notification System
Slide-in toasts anchored to the bottom-right of the main window.
Types: INFO (blue), WARNING (yellow), ERROR (red), SUCCESS (green)
Max 3 stacked, 4-second auto-dismiss, click to close.
"""
from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QApplication
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QRect, pyqtSignal
)
from PyQt6.QtGui import QPainter, QColor, QFont, QPainterPath

# ── Colour palette ──────────────────────────────────────────────────────────

_COLOURS = {
    "info":    {"bg": "#1a3a5c", "border": "#5294e2", "icon": "ℹ",  "fg": "#a8d4f5"},
    "warning": {"bg": "#3d2e00", "border": "#e2a252", "icon": "⚠",  "fg": "#f5c87a"},
    "error":   {"bg": "#3d0f0f", "border": "#e25252", "icon": "✕",  "fg": "#f5a8a8"},
    "success": {"bg": "#0f3d1a", "border": "#52e27a", "icon": "✓",  "fg": "#a8f5c0"},
}

_TOAST_W   = 360
_TOAST_H   = 64          # min height; grows with long text
_MARGIN    = 12          # gap between toasts and from window edge
_ANIM_MS   = 220
_LIFE_MS   = 4000        # auto-dismiss after 4 s


# ── Single toast widget ──────────────────────────────────────────────────────

class ToastWidget(QWidget):
    """One notification card. Emits `dismissed` when it wants to be removed."""

    dismissed = pyqtSignal(object)   # emits self

    def __init__(self, message: str, kind: str = "info", parent: QWidget | None = None):
        super().__init__(parent, Qt.WindowType.ToolTip |
                         Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._kind      = kind
        self._message   = message
        self._palette   = _COLOURS.get(kind, _COLOURS["info"])
        self._opacity   = 1.0
        self._dismissed = False

        self._build_ui()
        self.adjustSize()
        h = max(_TOAST_H, self.height())
        h = min(h, 90)          # cap so Qt never complains about geometry
        self.setFixedHeight(h)
        self.setFixedWidth(_TOAST_W)

        # Auto-dismiss timer
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._start_dismiss)
        self._timer.start(_LIFE_MS)

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 10, 12, 10)
        outer.setSpacing(10)

        icon_lbl = QLabel(self._palette["icon"])
        icon_lbl.setStyleSheet(
            f"color: {self._palette['border']}; font-size: 16px; "
            "background: transparent;"
        )
        icon_lbl.setFixedWidth(20)
        outer.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        msg_lbl = QLabel(self._message)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet(
            f"color: {self._palette['fg']}; font-size: 11px; "
            "background: transparent; font-family: 'Segoe UI';"
        )
        outer.addWidget(msg_lbl, 1)

        close_lbl = QLabel("×")
        close_lbl.setStyleSheet(
            "color: #555566; font-size: 16px; background: transparent;"
        )
        close_lbl.setFixedWidth(16)
        outer.addWidget(close_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

    # ── Paint background ─────────────────────────────────────────────────────

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._opacity)

        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 8, 8)

        p.fillPath(path, QColor(self._palette["bg"]))

        # left accent bar
        bar = QPainterPath()
        bar.addRoundedRect(0, 0, 4, self.height(), 2, 2)
        p.fillPath(bar, QColor(self._palette["border"]))

        # border
        p.setPen(QColor(self._palette["border"] + "66"))  # 40 % alpha
        p.drawPath(path)

    # ── Interaction ──────────────────────────────────────────────────────────

    def mousePressEvent(self, _event):
        self._dismiss_now()

    # ── Dismiss logic ────────────────────────────────────────────────────────

    def _start_dismiss(self):
        """Slide down then emit dismissed."""
        start_pos = self.pos()
        end_pos   = QPoint(start_pos.x(), start_pos.y() + 60)
        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(200)
        self._anim.setStartValue(start_pos)
        self._anim.setEndValue(end_pos)
        self._anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim.finished.connect(self.hide)
        self._anim.finished.connect(self._emit_dismissed)
        self._anim.start()

    def _dismiss_now(self):
        self._timer.stop()
        self._emit_dismissed()

    def _emit_dismissed(self):
        if self._dismissed:
            return
        self._dismissed = True
        self.dismissed.emit(self)
        self.hide()
        self.deleteLater()


# ── Toast manager ────────────────────────────────────────────────────────────

class ToastManager:
    """
    Attach to a QMainWindow. Call show(message, kind) to display a toast.
    Toasts stack vertically from the bottom-right, max 3 visible at once.
    """

    MAX_TOASTS = 3

    def __init__(self, parent: QWidget):
        self._parent  = parent
        self._toasts: list[ToastWidget] = []

    # ── Public API ───────────────────────────────────────────────────────────

    def info(self, message: str):
        self.show(message, "info")

    def warning(self, message: str):
        self.show(message, "warning")

    def error(self, message: str):
        self.show(message, "error")

    def success(self, message: str):
        self.show(message, "success")

    def show(self, message: str, kind: str = "info"):
        # Drop oldest if already at cap
        if len(self._toasts) >= self.MAX_TOASTS:
            oldest = self._toasts[0]
            oldest._dismiss_now()          # emits dismissed → _on_dismissed cleans list

        toast = ToastWidget(message, kind, parent=self._parent)
        toast.dismissed.connect(self._on_dismissed)
        self._toasts.append(toast)
        self._reposition(animate_new=toast)
        toast.show()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _on_dismissed(self, toast: ToastWidget):
        if toast in self._toasts:
            self._toasts.remove(toast)
        self._reposition()

    def _get_screen_geom(self):
        """Get the available geometry for the screen the parent window is on."""
        parent = self._parent
        if parent and hasattr(parent, 'screen') and callable(parent.screen):
            try:
                screen = parent.screen()
            except Exception:
                screen = None
        else:
            screen = None
        if not screen:
            screen = QApplication.primaryScreen()
        if screen:
            return screen.availableGeometry()
        # Fallback: use parent geometry
        return self._parent.geometry() if self._parent else QRect(0, 0, 1920, 1080)

    def _reposition(self, animate_new: ToastWidget | None = None):
        """Place all toasts bottom-right of parent's screen, stacked upward."""
        sg = self._get_screen_geom()

        right_x  = sg.right() - _TOAST_W - _MARGIN
        right_x  = max(right_x, sg.left())
        bottom_y = sg.bottom() - _MARGIN

        for toast in reversed(self._toasts):
            target_y = bottom_y - toast.height()
            target   = QPoint(right_x, target_y)
            bottom_y = target_y - _MARGIN

            if toast is animate_new:
                # Slide in from bottom
                start = QPoint(target.x(), target.y() + 60)
                toast.move(start)
                anim = QPropertyAnimation(toast, b"pos", toast)
                anim.setDuration(250)
                anim.setStartValue(start)
                anim.setEndValue(target)
                anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                anim.start()
            else:
                # Smooth shift existing toasts
                anim = QPropertyAnimation(toast, b"pos", toast)
                anim.setDuration(_ANIM_MS)
                anim.setStartValue(toast.pos())
                anim.setEndValue(target)
                anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                anim.start()


# ── Module-level convenience ──────────────────────────────────────────────────

_global_manager: ToastManager | None = None


def set_global_toast_manager(manager: ToastManager):
    """Register the application's ToastManager for module-level show_toast()."""
    global _global_manager
    _global_manager = manager


def show_toast(message: str, kind: str = "info"):
    """
    Show a toast via the registered global manager.
    Falls back to a floating ToastWidget if no manager is set.
    """
    if _global_manager is not None:
        _global_manager.show(message, kind)
    else:
        # Fallback: show a standalone toast bottom-right of the primary screen
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        toast = ToastWidget(message, kind, parent=None)
        if screen:
            sg = screen.availableGeometry()
            x = sg.right()  - toast.width()  - 20
            y = sg.bottom() - toast.height() - 20
            x = max(sg.left(), min(x, sg.right()  - toast.width()))
            y = max(sg.top(),  min(y, sg.bottom() - toast.height()))
            toast.move(x, y)
        toast.show()
