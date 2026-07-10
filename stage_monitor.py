"""
Cantio - Stage Monitor
Visual drag-and-drop stage display editor + fullscreen output window.
Inspired by ProPresenter Stage Display.

Widget types: CURRENT_SLIDE, NEXT_SLIDE, CLOCK, TIMER, NOTES, CUSTOM_TEXT, IMAGE
"""
import os
import json
import uuid
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QComboBox, QCheckBox, QColorDialog,
    QFontComboBox, QSpinBox, QDoubleSpinBox, QFileDialog,
    QApplication, QScrollArea, QFrame, QGroupBox, QFormLayout,
    QLineEdit, QTextEdit, QDialog, QDialogButtonBox, QSizePolicy,
    QToolBar, QStatusBar, QMessageBox, QSlider
)
from PyQt6.QtCore import Qt, QRect, QPoint, QSize, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QFont, QColor, QFontMetrics, QPen, QBrush,
    QPixmap, QCursor, QAction
)

import database as db
from translations import t


# ── Widget type constants ─────────────────────────────────────────────────────

WT_CURRENT_SLIDE = "CURRENT_SLIDE"
WT_NEXT_SLIDE    = "NEXT_SLIDE"
WT_CLOCK         = "CLOCK"
WT_TIMER         = "TIMER"
WT_NOTES         = "NOTES"
WT_CUSTOM_TEXT   = "CUSTOM_TEXT"
WT_IMAGE         = "IMAGE"

WIDGET_LABELS = {
    WT_CURRENT_SLIDE: "Current Slide",
    WT_NEXT_SLIDE:    "Next Slide",
    WT_CLOCK:         "Clock",
    WT_TIMER:         "Timer",
    WT_NOTES:         "Operator Notes",
    WT_CUSTOM_TEXT:   "Custom Text",
    WT_IMAGE:         "Image",
}

WIDGET_ICONS = {
    WT_CURRENT_SLIDE: "▶",
    WT_NEXT_SLIDE:    "⏭",
    WT_CLOCK:         "🕐",
    WT_TIMER:         "⏱",
    WT_NOTES:         "📝",
    WT_CUSTOM_TEXT:   "T",
    WT_IMAGE:         "🖼",
}

STAGE_STYLE = """
QMainWindow, QWidget { background-color: #141414; color: #e0e0e0;
    font-family: 'Segoe UI', sans-serif; font-size: 12px; }
QSplitter::handle { background: #222; }
QSplitter::handle:horizontal { width: 2px; }
QGroupBox { border: 1px solid #2a2a2a; border-radius: 5px;
    margin-top: 6px; padding: 10px 8px 8px 8px;
    color: #5294e2; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px;
    color: #5294e2; font-weight: 700; font-size: 10px; }
QLabel { color: #cccccc; }
QLineEdit, QTextEdit { background: #1e1e1e; color: #e0e0e0;
    border: 1px solid #2c2c2c; border-radius: 4px; padding: 5px; }
QLineEdit:focus, QTextEdit:focus { border-color: #5294e2; }
QPushButton { background: #252525; color: #e0e0e0; border: 1px solid #333;
    border-radius: 4px; padding: 6px 12px; }
QPushButton:hover { background: #2e2e2e; border-color: #444; }
QPushButton:pressed { background: #1e1e1e; }
QComboBox, QSpinBox, QDoubleSpinBox, QFontComboBox {
    background: #1e1e1e; color: #e0e0e0; border: 1px solid #2c2c2c;
    border-radius: 4px; padding: 4px 8px; }
QComboBox QAbstractItemView { background: #252525; color: #e0e0e0;
    border: 1px solid #333; selection-background-color: #1c3a5a; }
QScrollArea { border: none; }
QToolBar { background: #111; border-bottom: 1px solid #222;
    padding: 4px; spacing: 4px; }
QStatusBar { background: #111; color: #555; border-top: 1px solid #1e1e1e; }
QCheckBox { color: #e0e0e0; }
QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid #3a3a3a;
    border-radius: 3px; background: #1e1e1e; }
QCheckBox::indicator:checked { background: #5294e2; border-color: #5294e2; }
QSlider::groove:horizontal { background: #2c2c2c; height: 4px; border-radius: 2px; }
QSlider::handle:horizontal { background: #5294e2; width: 12px; height: 12px;
    border-radius: 6px; margin: -4px 0; }
QSlider::sub-page:horizontal { background: #5294e2; border-radius: 2px; }
"""


# ── Default widget factory ────────────────────────────────────────────────────

def make_widget(wtype, x=0.05, y=0.05, w=0.45, h=0.25):
    return {
        "id": str(uuid.uuid4()),
        "type": wtype,
        "x": x, "y": y, "w": w, "h": h,
        "font_family": "Segoe UI",
        "font_size": 36,
        "font_color": "#ffffff",
        "font_bold": True,
        "font_italic": False,
        "bg_color": "#000000",
        "bg_opacity": 0.55,
        "text_align": "center",
        "valign": "center",
        "text": "",
        "image_path": "",
        "border_color": "#333333",
        "visible": True,
        "label_prefix": True,
    }


# ── State container passed to rendering ──────────────────────────────────────

class StageState:
    def __init__(self):
        self.current_text = ""
        self.next_text = ""
        self.notes = ""
        self.timer_remaining = 0
        self.timer_running = False


# ── Shared rendering logic ────────────────────────────────────────────────────

def get_widget_display_text(widget, state: StageState):
    """Return the text to display for a given widget type."""
    wtype = widget["type"]
    if wtype == WT_CURRENT_SLIDE:
        return state.current_text or "— no slide —"
    elif wtype == WT_NEXT_SLIDE:
        prefix = "NEXT:\n" if widget.get("label_prefix") else ""
        return prefix + (state.next_text or "—")
    elif wtype == WT_CLOCK:
        return datetime.now().strftime("%H:%M:%S")
    elif wtype == WT_TIMER:
        rem = state.timer_remaining
        m, s = divmod(max(0, rem), 60)
        return f"{m:02d}:{s:02d}"
    elif wtype == WT_NOTES:
        prefix = "NOTES:\n" if widget.get("label_prefix") else ""
        return prefix + (state.notes or "—")
    elif wtype == WT_CUSTOM_TEXT:
        return widget.get("text", "")
    elif wtype == WT_IMAGE:
        return ""
    return ""


def render_stage_widget(painter, widget, canvas_w, canvas_h, state: StageState, selected=False):
    """Render one stage widget onto the painter at canvas coordinates."""
    if not widget.get("visible", True):
        return

    px = int(widget["x"] * canvas_w)
    py = int(widget["y"] * canvas_h)
    pw = max(20, int(widget["w"] * canvas_w))
    ph = max(20, int(widget["h"] * canvas_h))
    rect = QRect(px, py, pw, ph)

    # Background
    bg = QColor(widget.get("bg_color", "#000000"))
    bg.setAlphaF(float(widget.get("bg_opacity", 0.55)))
    painter.fillRect(rect, bg)

    wtype = widget["type"]

    if wtype == WT_IMAGE:
        path = widget.get("image_path", "")
        if path and os.path.exists(path):
            pix = QPixmap(path).scaled(
                pw, ph,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            off_x = px + (pw - pix.width()) // 2
            off_y = py + (ph - pix.height()) // 2
            painter.drawPixmap(off_x, off_y, pix)
        else:
            painter.setPen(QColor("#555"))
            painter.setFont(QFont("Segoe UI", max(8, pw // 10)))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "🖼 Image\n(no path)")
    else:
        text = get_widget_display_text(widget, state)
        if text:
            _draw_widget_text(painter, widget, rect, text, wtype, state)

    # Border
    if selected:
        pen = QPen(QColor("#5294e2"))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)
        # Draw resize handles at corners
        _draw_resize_handles(painter, rect)
    else:
        pen = QPen(QColor(widget.get("border_color", "#333333")))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)

    # Type label (editor only hint)
    label_font = QFont("Segoe UI", max(6, pw // 20))
    painter.setFont(label_font)
    painter.setPen(QColor("#5294e2" if selected else "#444"))
    icon = WIDGET_ICONS.get(wtype, "?")
    lbl = WIDGET_LABELS.get(wtype, wtype)
    painter.drawText(px + 4, py + 14, f"{icon} {lbl}")


def _draw_widget_text(painter, widget, rect, text, wtype, state):
    font_family = widget.get("font_family", "Segoe UI")
    font_size = max(1, int(widget.get("font_size", 36) or 36))
    font_bold = widget.get("font_bold", True)
    font_italic = widget.get("font_italic", False)
    font_color = widget.get("font_color", "#ffffff")
    text_align = widget.get("text_align", "center")
    valign = widget.get("valign", "center")

    # Timer turns red when < 30s
    if wtype == WT_TIMER and state.timer_remaining < 30 and state.timer_running:
        font_color = "#f44336"

    padding = 6
    inner = rect.adjusted(padding, 18, -padding, -padding)  # top offset for type label

    # Auto-fit font size within inner rect
    lines = text.splitlines()
    avail_w = inner.width()
    avail_h = inner.height()
    fitted_size = font_size

    for size in range(font_size, 7, -1):
        font = QFont(font_family, size)
        font.setBold(font_bold)
        font.setItalic(font_italic)
        fm = QFontMetrics(font)
        lh = int(fm.height() * 1.2)
        th = lh * len(lines)
        mw = max((fm.horizontalAdvance(l) for l in lines), default=0)
        if th <= avail_h and mw <= avail_w:
            fitted_size = size
            break

    font = QFont(font_family, fitted_size)
    font.setBold(font_bold)
    font.setItalic(font_italic)
    painter.setFont(font)

    fm = QFontMetrics(font)
    lh = int(fm.height() * 1.2)
    total_h = lh * len(lines)

    h_flag = {
        "left": Qt.AlignmentFlag.AlignLeft,
        "right": Qt.AlignmentFlag.AlignRight,
    }.get(text_align, Qt.AlignmentFlag.AlignHCenter)

    if valign == "top":
        start_y = inner.top() + fm.ascent()
    elif valign == "bottom":
        start_y = inner.bottom() - total_h + fm.ascent()
    else:
        start_y = inner.top() + (inner.height() - total_h) // 2 + fm.ascent()

    painter.setPen(QColor(font_color))

    for i, line in enumerate(lines):
        lw = fm.horizontalAdvance(line)
        if text_align == "left":
            x = inner.left()
        elif text_align == "right":
            x = inner.right() - lw
        else:
            x = inner.left() + (inner.width() - lw) // 2
        y = start_y + i * lh
        # Shadow
        painter.setPen(QColor(0, 0, 0, 120))
        painter.drawText(x + 1, y + 1, line)
        painter.setPen(QColor(font_color))
        painter.drawText(x, y, line)


HANDLE_SIZE = 8


def _draw_resize_handles(painter, rect):
    painter.setBrush(QBrush(QColor("#5294e2")))
    painter.setPen(Qt.PenStyle.NoPen)
    corners = [
        QRect(rect.left() - HANDLE_SIZE // 2, rect.top() - HANDLE_SIZE // 2, HANDLE_SIZE, HANDLE_SIZE),
        QRect(rect.right() - HANDLE_SIZE // 2, rect.top() - HANDLE_SIZE // 2, HANDLE_SIZE, HANDLE_SIZE),
        QRect(rect.left() - HANDLE_SIZE // 2, rect.bottom() - HANDLE_SIZE // 2, HANDLE_SIZE, HANDLE_SIZE),
        QRect(rect.right() - HANDLE_SIZE // 2, rect.bottom() - HANDLE_SIZE // 2, HANDLE_SIZE, HANDLE_SIZE),
    ]
    for c in corners:
        painter.drawRect(c)


def _corner_hit(rect, pos, canvas_w, canvas_h, widget):
    """Return corner index (0=TL,1=TR,2=BL,3=BR) if pos is near a corner, else -1."""
    px = int(widget["x"] * canvas_w)
    py = int(widget["y"] * canvas_h)
    pw = int(widget["w"] * canvas_w)
    ph = int(widget["h"] * canvas_h)
    corners = [
        QPoint(px, py), QPoint(px + pw, py),
        QPoint(px, py + ph), QPoint(px + pw, py + ph)
    ]
    for i, c in enumerate(corners):
        if abs(pos.x() - c.x()) <= HANDLE_SIZE + 2 and abs(pos.y() - c.y()) <= HANDLE_SIZE + 2:
            return i
    return -1


# ── Stage canvas (editor) ─────────────────────────────────────────────────────

class StageCanvas(QWidget):
    """Editable canvas: shows widgets, handles drag/resize/select."""

    selectionChanged = pyqtSignal(object)   # emits selected widget dict or None
    layoutChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.widgets: list[dict] = []
        self.state = StageState()
        self._selected_id = None
        self._drag_mode = None  # None | "move" | "resize_TL" etc.
        self._drag_start_pos = None
        self._drag_start_widget = None
        self._corner_drag = -1
        self.setMouseTracking(True)
        self.setMinimumSize(400, 225)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Clock refresh
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self.update)
        self._clock_timer.start(1000)

    def set_widgets(self, widgets):
        self.widgets = widgets
        self.update()

    def update_state(self, current_text, next_text, notes,
                     timer_remaining=0, timer_running=False):
        self.state.current_text = current_text
        self.state.next_text = next_text
        self.state.notes = notes
        self.state.timer_remaining = timer_remaining
        self.state.timer_running = timer_running
        self.update()

    def selected_widget(self):
        if self._selected_id is None:
            return None
        for w in self.widgets:
            if w["id"] == self._selected_id:
                return w
        return None

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        cw, ch = self.width(), self.height()

        # Dark background with subtle grid
        p.fillRect(0, 0, cw, ch, QColor("#0d0d0d"))
        p.setPen(QPen(QColor("#1a1a1a"), 1))
        step = 40
        for x in range(0, cw, step):
            p.drawLine(x, 0, x, ch)
        for y in range(0, ch, step):
            p.drawLine(0, y, cw, y)

        # Screen outline
        p.setPen(QPen(QColor("#2a2a2a"), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(0, 0, cw - 1, ch - 1)

        for widget in self.widgets:
            selected = (widget["id"] == self._selected_id)
            render_stage_widget(p, widget, cw, ch, self.state, selected)

        # "No widgets" hint
        if not self.widgets:
            p.setPen(QColor("#333"))
            p.setFont(QFont("Segoe UI", 13))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "Click an 'Add Widget' button to start\nbuilding your stage layout")

        p.end()

    def _widget_at(self, pos):
        """Return topmost widget under pos, or None."""
        cw, ch = self.width(), self.height()
        for widget in reversed(self.widgets):
            px = int(widget["x"] * cw)
            py = int(widget["y"] * ch)
            pw = int(widget["w"] * cw)
            ph = int(widget["h"] * ch)
            if QRect(px, py, pw, ph).contains(pos):
                return widget
        return None

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.pos()
        cw, ch = self.width(), self.height()

        # Check resize handles on selected widget first
        sel = self.selected_widget()
        if sel:
            corner = _corner_hit(None, pos, cw, ch, sel)
            if corner >= 0:
                self._drag_mode = f"resize_{corner}"
                self._drag_start_pos = pos
                self._drag_start_widget = {**sel}
                return

        # Check hit on any widget
        hit = self._widget_at(pos)
        if hit:
            self._selected_id = hit["id"]
            self._drag_mode = "move"
            self._drag_start_pos = pos
            self._drag_start_widget = {**hit}
            self.selectionChanged.emit(hit)
        else:
            self._selected_id = None
            self._drag_mode = None
            self.selectionChanged.emit(None)
        self.update()

    def mouseMoveEvent(self, event):
        if self._drag_mode is None or self._drag_start_pos is None:
            self._update_cursor(event.pos())
            return

        cw, ch = self.width(), self.height()
        dx = (event.pos().x() - self._drag_start_pos.x()) / cw
        dy = (event.pos().y() - self._drag_start_pos.y()) / ch

        sel = self.selected_widget()
        if sel is None:
            return

        sw = self._drag_start_widget

        if self._drag_mode == "move":
            new_x = max(0.0, min(0.95, sw["x"] + dx))
            new_y = max(0.0, min(0.95, sw["y"] + dy))
            sel["x"] = new_x
            sel["y"] = new_y
        elif self._drag_mode.startswith("resize_"):
            corner = int(self._drag_mode.split("_")[1])
            if corner == 0:  # TL
                sel["x"] = max(0, min(sw["x"] + sw["w"] - 0.05, sw["x"] + dx))
                sel["y"] = max(0, min(sw["y"] + sw["h"] - 0.05, sw["y"] + dy))
                sel["w"] = max(0.05, sw["w"] - dx)
                sel["h"] = max(0.05, sw["h"] - dy)
            elif corner == 1:  # TR
                sel["y"] = max(0, min(sw["y"] + sw["h"] - 0.05, sw["y"] + dy))
                sel["w"] = max(0.05, sw["w"] + dx)
                sel["h"] = max(0.05, sw["h"] - dy)
            elif corner == 2:  # BL
                sel["x"] = max(0, min(sw["x"] + sw["w"] - 0.05, sw["x"] + dx))
                sel["w"] = max(0.05, sw["w"] - dx)
                sel["h"] = max(0.05, sw["h"] + dy)
            elif corner == 3:  # BR
                sel["w"] = max(0.05, sw["w"] + dx)
                sel["h"] = max(0.05, sw["h"] + dy)

        self.layoutChanged.emit()
        self.update()

    def mouseReleaseEvent(self, event):
        self._drag_mode = None
        self._drag_start_pos = None
        self._drag_start_widget = None

    def _update_cursor(self, pos):
        cw, ch = self.width(), self.height()
        sel = self.selected_widget()
        if sel and _corner_hit(None, pos, cw, ch, sel) >= 0:
            self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
        elif self._widget_at(pos):
            self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))


# ── Widget Properties Panel ───────────────────────────────────────────────────

class WidgetPropertiesPanel(QWidget):
    """Right panel: edit properties of selected stage widget."""

    propertiesChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._widget = None
        self._build_ui()
        self.setEnabled(False)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        hdr = QLabel("WIDGET PROPERTIES")
        hdr.setStyleSheet("color: #5294e2; font-size: 10px; font-weight: 700; letter-spacing: 2px;")
        layout.addWidget(hdr)

        # Font group
        font_group = QGroupBox("Font")
        ff = QFormLayout(font_group)
        self.font_combo = QFontComboBox()
        self.font_combo.currentFontChanged.connect(self._on_change)
        ff.addRow("Family:", self.font_combo)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 200)
        self.font_size_spin.setValue(36)
        self.font_size_spin.valueChanged.connect(self._on_change)
        ff.addRow("Size:", self.font_size_spin)

        style_row = QHBoxLayout()
        self.bold_check = QCheckBox("Bold")
        self.italic_check = QCheckBox("Italic")
        self.bold_check.stateChanged.connect(self._on_change)
        self.italic_check.stateChanged.connect(self._on_change)
        style_row.addWidget(self.bold_check)
        style_row.addWidget(self.italic_check)
        style_row.addStretch()
        ff.addRow("Style:", style_row)
        layout.addWidget(font_group)

        # Colors group
        color_group = QGroupBox("Colors")
        cf = QFormLayout(color_group)

        self.text_color_btn = QPushButton()
        self.text_color_btn.setFixedSize(48, 26)
        self.text_color_btn.clicked.connect(self._pick_text_color)
        cf.addRow("Text:", self.text_color_btn)

        bg_row = QHBoxLayout()
        self.bg_color_btn = QPushButton()
        self.bg_color_btn.setFixedSize(48, 26)
        self.bg_color_btn.clicked.connect(self._pick_bg_color)
        self.bg_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.bg_opacity_slider.setRange(0, 100)
        self.bg_opacity_slider.setValue(55)
        self.bg_opacity_slider.valueChanged.connect(self._on_change)
        bg_row.addWidget(self.bg_color_btn)
        bg_row.addWidget(self.bg_opacity_slider)
        cf.addRow("Background:", bg_row)
        layout.addWidget(color_group)

        # Alignment group
        align_group = QGroupBox("Alignment")
        af = QFormLayout(align_group)
        self.h_align_combo = QComboBox()
        self.h_align_combo.addItems(["center", "left", "right"])
        self.h_align_combo.currentIndexChanged.connect(self._on_change)
        af.addRow("Horizontal:", self.h_align_combo)

        self.v_align_combo = QComboBox()
        self.v_align_combo.addItems(["center", "top", "bottom"])
        self.v_align_combo.currentIndexChanged.connect(self._on_change)
        af.addRow("Vertical:", self.v_align_combo)
        layout.addWidget(align_group)

        # Custom text / image path
        content_group = QGroupBox("Content")
        conf = QVBoxLayout(content_group)
        self.custom_text_edit = QTextEdit()
        self.custom_text_edit.setFixedHeight(70)
        self.custom_text_edit.setPlaceholderText("Custom text…")
        self.custom_text_edit.textChanged.connect(self._on_change)
        conf.addWidget(QLabel("Custom text:"))
        conf.addWidget(self.custom_text_edit)

        img_row = QHBoxLayout()
        self.image_path_label = QLabel("—")
        self.image_path_label.setStyleSheet("color: #666; font-size: 10px;")
        img_browse_btn = QPushButton("Browse…")
        img_browse_btn.setFixedWidth(70)
        img_browse_btn.clicked.connect(self._pick_image)
        img_row.addWidget(self.image_path_label, 1)
        img_row.addWidget(img_browse_btn)
        conf.addLayout(img_row)
        layout.addWidget(content_group)

        # Visibility
        self.visible_check = QCheckBox("Widget visible")
        self.visible_check.setChecked(True)
        self.visible_check.stateChanged.connect(self._on_change)
        layout.addWidget(self.visible_check)

        # Label prefix
        self.prefix_check = QCheckBox("Show type prefix (NEXT: / NOTES:)")
        self.prefix_check.setChecked(True)
        self.prefix_check.stateChanged.connect(self._on_change)
        layout.addWidget(self.prefix_check)

        layout.addStretch()

        # Delete button
        del_btn = QPushButton("🗑 Delete Widget")
        del_btn.setStyleSheet(
            "QPushButton { background: #1e1e1e; color: #f44336; border: 1px solid #2a1a1a; "
            "border-radius: 4px; padding: 6px; }"
            "QPushButton:hover { background: #2a1a1a; border-color: #f44336; }"
        )
        del_btn.clicked.connect(self._delete_widget)
        layout.addWidget(del_btn)

        self._updating = False

    def load_widget(self, widget):
        self._widget = widget
        if widget is None:
            self.setEnabled(False)
            return
        self.setEnabled(True)
        self._updating = True

        from PyQt6.QtGui import QFont as QF
        self.font_combo.setCurrentFont(QF(widget.get("font_family", "Segoe UI")))
        self.font_size_spin.setValue(int(widget.get("font_size", 36)))
        self.bold_check.setChecked(bool(widget.get("font_bold", True)))
        self.italic_check.setChecked(bool(widget.get("font_italic", False)))
        self._set_btn_color(self.text_color_btn, widget.get("font_color", "#ffffff"))
        self._set_btn_color(self.bg_color_btn, widget.get("bg_color", "#000000"))
        self.bg_opacity_slider.setValue(int(float(widget.get("bg_opacity", 0.55)) * 100))
        hi = self.h_align_combo.findText(widget.get("text_align", "center"))
        if hi >= 0:
            self.h_align_combo.setCurrentIndex(hi)
        vi = self.v_align_combo.findText(widget.get("valign", "center"))
        if vi >= 0:
            self.v_align_combo.setCurrentIndex(vi)
        self.custom_text_edit.blockSignals(True)
        self.custom_text_edit.setPlainText(widget.get("text", ""))
        self.custom_text_edit.blockSignals(False)
        self.image_path_label.setText(widget.get("image_path", "") or "—")
        self.visible_check.setChecked(bool(widget.get("visible", True)))
        self.prefix_check.setChecked(bool(widget.get("label_prefix", True)))

        # Show/hide content fields based on type
        wtype = widget.get("type", "")
        self.custom_text_edit.setEnabled(wtype == WT_CUSTOM_TEXT)

        self._updating = False

    def _set_btn_color(self, btn, color):
        btn.setStyleSheet(
            f"background-color: {color}; border: 1px solid #555; border-radius: 3px;"
        )
        btn._color = color

    def _pick_text_color(self):
        c = QColorDialog.getColor(QColor(getattr(self.text_color_btn, "_color", "#ffffff")), self)
        if c.isValid() and self._widget:
            self._set_btn_color(self.text_color_btn, c.name())
            self._widget["font_color"] = c.name()
            self.propertiesChanged.emit()

    def _pick_bg_color(self):
        c = QColorDialog.getColor(QColor(getattr(self.bg_color_btn, "_color", "#000000")), self)
        if c.isValid() and self._widget:
            self._set_btn_color(self.bg_color_btn, c.name())
            self._widget["bg_color"] = c.name()
            self.propertiesChanged.emit()

    def _pick_image(self):
        if not self._widget:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if path:
            self._widget["image_path"] = path
            self.image_path_label.setText(path)
            self.propertiesChanged.emit()

    def _delete_widget(self):
        if self._widget:
            self._widget["_delete"] = True
            self.propertiesChanged.emit()

    def _on_change(self):
        if self._updating or self._widget is None:
            return
        self._widget["font_family"] = self.font_combo.currentFont().family()
        self._widget["font_size"] = self.font_size_spin.value()
        self._widget["font_bold"] = self.bold_check.isChecked()
        self._widget["font_italic"] = self.italic_check.isChecked()
        self._widget["bg_opacity"] = self.bg_opacity_slider.value() / 100.0
        self._widget["text_align"] = self.h_align_combo.currentText()
        self._widget["valign"] = self.v_align_combo.currentText()
        self._widget["text"] = self.custom_text_edit.toPlainText()
        self._widget["visible"] = self.visible_check.isChecked()
        self._widget["label_prefix"] = self.prefix_check.isChecked()
        self.propertiesChanged.emit()


# ── Stage Output Window ───────────────────────────────────────────────────────

class StageOutputWindow(QMainWindow):
    """Fullscreen output window shown on the confidence monitor / stage display."""

    def __init__(self, screen=None, parent=None):
        super().__init__(parent)
        self.widgets: list[dict] = []
        self.state = StageState()
        self.setWindowTitle("Cantio — Stage Display")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self._canvas = QWidget(self)
        self._canvas.setStyleSheet("background: #000;")
        self.setCentralWidget(self._canvas)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._canvas.update)
        self._timer.start(1000)

        if screen:
            self.setGeometry(screen.geometry())
        self.showFullScreen()

        # Override paint
        self._canvas.paintEvent = self._paint_output

    def _paint_output(self, event):
        p = QPainter(self._canvas)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        cw, ch = self._canvas.width(), self._canvas.height()
        p.fillRect(0, 0, cw, ch, QColor("#000000"))
        for widget in self.widgets:
            render_stage_widget(p, widget, cw, ch, self.state, selected=False)
        p.end()

    def set_widgets(self, widgets):
        self.widgets = [w for w in widgets if not w.get("_delete")]
        self._canvas.update()

    def update_state(self, current_text, next_text, notes,
                     timer_remaining=0, timer_running=False):
        self.state.current_text = current_text
        self.state.next_text = next_text
        self.state.notes = notes
        self.state.timer_remaining = timer_remaining
        self.state.timer_running = timer_running
        self._canvas.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()


# ── Stage Editor Window ───────────────────────────────────────────────────────

class StageEditorWindow(QMainWindow):
    """
    Full stage monitor editor.
    Left: toolbox, Center: canvas, Right: properties panel.
    """

    stateUpdateRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Cantio — {t('stage_monitor')}")
        self.setMinimumSize(1100, 650)
        self.setStyleSheet(STAGE_STYLE)

        self._output_window: StageOutputWindow | None = None
        self._settings = db.get_settings()

        self._build_toolbar()
        self._build_ui()
        self._refresh_layout_combo()
        # Apply the saved active named layout if there is one, else the default.
        _active = self._settings.get("stage_active_layout", "")
        _layouts = self._named_layouts()
        if _active and _active in _layouts:
            self.canvas.set_widgets(_layouts[_active])
        else:
            self._load_layout()

    # ── Toolbar ───────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        tb = QToolBar("Stage", self)
        tb.setMovable(False)
        self.addToolBar(tb)

        def tbtn(label, slot, accent=False):
            b = QPushButton(label)
            b.clicked.connect(slot)
            if accent:
                b.setStyleSheet(
                    "QPushButton { background: #2d6a30; color: #fff; border: none; "
                    "border-radius: 4px; padding: 5px 14px; font-weight: 600; }"
                    "QPushButton:hover { background: #357a38; }"
                )
            else:
                b.setStyleSheet(
                    "QPushButton { background: #1e1e1e; color: #ccc; border: 1px solid #2a2a2a; "
                    "border-radius: 4px; padding: 5px 12px; }"
                    "QPushButton:hover { background: #252525; color: #e0e0e0; }"
                )
            tb.addWidget(b)
            return b

        name_lbl = QLabel("  Stage Monitor  ")
        name_lbl.setStyleSheet("color: #5294e2; font-weight: 700; font-size: 13px; padding: 0 8px;")
        tb.addWidget(name_lbl)
        tb.addSeparator()

        tbtn(f"💾 {t('save')}", self._save_layout)
        tbtn(f"📂 {t('open_service')}", self._load_layout_file)
        tb.addSeparator()

        # Named layouts (switchable live, ProPresenter-style)
        from PyQt6.QtWidgets import QComboBox
        lay_lbl = QLabel("  Layout: ")
        lay_lbl.setStyleSheet("color:#888; font-size:11px;")
        tb.addWidget(lay_lbl)
        self._layout_combo = QComboBox()
        self._layout_combo.setStyleSheet(
            "QComboBox { background:#151515; color:#ddd; border:1px solid #262626; "
            "border-radius:4px; padding:4px 8px; font-size:11px; min-width:120px; }")
        self._layout_combo.currentIndexChanged.connect(self._on_layout_combo)
        tb.addWidget(self._layout_combo)
        tbtn("💾+ Salvează ca…", self._save_layout_as)
        tb.addSeparator()
        tbtn(f"🗑 {t('clear_all')}", self._clear_all)
        tb.addSeparator()

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        tbtn(f"📺 {t('stage_monitor')}", self._open_output, accent=True)
        tbtn(f"✕ {t('close')}", self._close_output)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        # Left: Widget toolbox
        left = self._build_toolbox()
        left.setMinimumWidth(160)
        left.setMaximumWidth(200)
        splitter.addWidget(left)

        # Center: Canvas
        self.canvas = StageCanvas()
        self.canvas.selectionChanged.connect(self._on_selection_changed)
        self.canvas.layoutChanged.connect(self._on_layout_changed)
        splitter.addWidget(self.canvas)

        # Right: Properties
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        self.props_panel = WidgetPropertiesPanel()
        self.props_panel.propertiesChanged.connect(self._on_props_changed)
        right_scroll.setWidget(self.props_panel)
        right_scroll.setMinimumWidth(230)
        right_scroll.setMaximumWidth(280)
        splitter.addWidget(right_scroll)

        splitter.setSizes([180, 640, 260])

        # Status bar
        self.status = QStatusBar()
        self.status.setStyleSheet(
            "QStatusBar { background: #111; color: #555; border-top: 1px solid #1e1e1e; }"
        )
        self.setStatusBar(self.status)
        self.status.showMessage("Stage Editor ready — add widgets to build your layout")

    def _build_toolbox(self):
        w = QWidget()
        w.setStyleSheet("background: #111;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(6, 8, 6, 8)
        layout.setSpacing(4)

        hdr = QLabel("ADD WIDGETS")
        hdr.setStyleSheet("color: #5294e2; font-size: 10px; font-weight: 700; "
                          "letter-spacing: 2px; padding: 4px 0;")
        layout.addWidget(hdr)

        for wtype, label in WIDGET_LABELS.items():
            icon = WIDGET_ICONS[wtype]
            btn = QPushButton(f"{icon}  {label}")
            btn.setStyleSheet(
                "QPushButton { background: #1a1a1a; color: #ccc; border: 1px solid #222; "
                "border-radius: 4px; padding: 7px 8px; text-align: left; }"
                "QPushButton:hover { background: #222; color: #e0e0e0; border-color: #5294e2; }"
            )
            btn.clicked.connect(lambda _, t=wtype: self._add_widget(t))
            layout.addWidget(btn)

        layout.addStretch()

        # Screen selector for output
        sep = QFrame()
        sep.setStyleSheet("background: #222; max-height: 1px; min-height: 1px;")
        layout.addWidget(sep)

        layout.addWidget(QLabel("Stage output screen:"))
        self.screen_combo = QComboBox()
        for i, scr in enumerate(QApplication.screens()):
            g = scr.geometry()
            self.screen_combo.addItem(f"Screen {i+1} ({g.width()}×{g.height()})", i)
        # Default to screen 2 if available
        scr_idx = int(self._settings.get("stage_screen", 1))
        if scr_idx < self.screen_combo.count():
            self.screen_combo.setCurrentIndex(scr_idx)
        layout.addWidget(self.screen_combo)

        return w

    # ── Widget management ─────────────────────────────────────────────────────

    def _add_widget(self, wtype):
        # Stagger default positions
        offset = len(self.canvas.widgets) * 0.03
        defaults = {
            WT_CURRENT_SLIDE: (0.03, 0.05, 0.6, 0.4),
            WT_NEXT_SLIDE:    (0.03, 0.5, 0.45, 0.2),
            WT_CLOCK:         (0.7, 0.04, 0.27, 0.1),
            WT_TIMER:         (0.7, 0.16, 0.27, 0.1),
            WT_NOTES:         (0.03, 0.72, 0.6, 0.2),
            WT_CUSTOM_TEXT:   (0.3, 0.3, 0.4, 0.15),
            WT_IMAGE:         (0.7, 0.3, 0.27, 0.4),
        }
        x, y, ww, wh = defaults.get(wtype, (0.05 + offset, 0.05 + offset, 0.4, 0.2))
        widget = make_widget(wtype, x, y, ww, wh)
        self.canvas.widgets.append(widget)
        self.canvas._selected_id = widget["id"]
        self.canvas.selectionChanged.emit(widget)
        self.canvas.update()
        self._sync_output()
        self.status.showMessage(f"Added {WIDGET_LABELS[wtype]} widget")

    def _on_selection_changed(self, widget):
        self.props_panel.load_widget(widget)

    def _on_layout_changed(self):
        self._sync_output()

    def _on_props_changed(self):
        # Check for deletion flag
        self.canvas.widgets = [w for w in self.canvas.widgets if not w.get("_delete")]
        self.canvas._selected_id = None
        self.props_panel.load_widget(None)
        self.canvas.update()
        self._sync_output()

    def _sync_output(self):
        if self._output_window:
            self._output_window.set_widgets(self.canvas.widgets)

    # ── Output window ─────────────────────────────────────────────────────────

    def _open_output(self):
        if self._output_window and not self._output_window.isHidden():
            self._output_window.raise_()
            return
        screens = QApplication.screens()
        idx = self.screen_combo.currentData() or 0
        screen = screens[min(idx, len(screens) - 1)]
        self._output_window = StageOutputWindow(screen=screen, parent=None)
        self._output_window.set_widgets(self.canvas.widgets)
        self._output_window.show()
        self.status.showMessage(f"Stage output opened on Screen {idx + 1}")

    def _close_output(self):
        if self._output_window:
            self._output_window.close()
            self._output_window = None
        self.status.showMessage("Stage output closed")

    # ── State updates from ControlWindow ──────────────────────────────────────

    def update_state(self, current_text, next_text, notes,
                     timer_remaining=0, timer_running=False):
        self.canvas.update_state(current_text, next_text, notes,
                                 timer_remaining, timer_running)
        if self._output_window:
            self._output_window.update_state(current_text, next_text, notes,
                                             timer_remaining, timer_running)

    # ── Layout save/load ──────────────────────────────────────────────────────

    def _current_widgets_data(self):
        return [{k: v for k, v in w.items() if not k.startswith("_")}
                for w in self.canvas.widgets]

    def _named_layouts(self):
        try:
            d = json.loads(self._settings.get("stage_layouts", "{}") or "{}")
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    def _save_named_layouts(self, layouts):
        s = json.dumps(layouts)
        db.save_setting("stage_layouts", s)
        self._settings["stage_layouts"] = s

    def _refresh_layout_combo(self):
        cmb = getattr(self, "_layout_combo", None)
        if cmb is None:
            return
        layouts = self._named_layouts()
        active = self._settings.get("stage_active_layout", "")
        cmb.blockSignals(True)
        cmb.clear()
        cmb.addItem("(implicit)")
        for n in layouts.keys():
            cmb.addItem(n)
        if active and active in layouts:
            cmb.setCurrentIndex(list(layouts.keys()).index(active) + 1)
        cmb.blockSignals(False)

    def _on_layout_combo(self, i):
        if i <= 0:
            db.save_setting("stage_active_layout", "")
            self._settings["stage_active_layout"] = ""
            self._load_layout()
            return
        name = self._layout_combo.itemText(i)
        layouts = self._named_layouts()
        if name in layouts:
            self.canvas.set_widgets(layouts[name])
            self._sync_output()
            db.save_setting("stage_active_layout", name)
            self._settings["stage_active_layout"] = name
            self.status.showMessage(f"Layout: {name}")

    def _save_layout_as(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Salvează layout", "Nume layout:")
        name = (name or "").strip()
        if not (ok and name):
            return
        layouts = self._named_layouts()
        layouts[name] = self._current_widgets_data()
        self._save_named_layouts(layouts)
        db.save_setting("stage_active_layout", name)
        self._settings["stage_active_layout"] = name
        self._refresh_layout_combo()
        self.status.showMessage(f"Layout «{name}» salvat")

    def _save_layout(self):
        layout_data = self._current_widgets_data()
        active = self._settings.get("stage_active_layout", "")
        if active:
            layouts = self._named_layouts()
            layouts[active] = layout_data
            self._save_named_layouts(layouts)
            self.status.showMessage(f"Layout «{active}» salvat ({len(layout_data)} widgets)")
        else:
            db.save_setting("stage_layout", json.dumps(layout_data))
            self.status.showMessage(f"Layout saved ({len(layout_data)} widgets)")

    def _load_layout(self):
        raw = self._settings.get("stage_layout", "[]")
        try:
            widgets = json.loads(raw)
            if isinstance(widgets, list):
                self.canvas.set_widgets(widgets)
                self.status.showMessage(f"Layout loaded ({len(widgets)} widgets)")
        except Exception:
            pass

    def _load_layout_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Stage Layout", "", "JSON (*.json)"
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    widgets = json.load(f)
                self.canvas.set_widgets(widgets)
                self._sync_output()
                self.status.showMessage(f"Layout loaded: {os.path.basename(path)}")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _clear_all(self):
        if QMessageBox.question(self, "Clear Layout", "Remove all widgets?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self.canvas.widgets.clear()
            self.canvas._selected_id = None
            self.props_panel.load_widget(None)
            self.canvas.update()
            self._sync_output()

    def closeEvent(self, event):
        self._save_layout()
        self._close_output()
        event.accept()
