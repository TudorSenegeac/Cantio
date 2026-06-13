"""
Cantio - Presentation Editor (Advanced)
QGraphicsScene/View-based slide editor.
Supports: Text, Image, Shape (rect/ellipse/line), elements
with drag-move, resize handles, per-element animations,
slide background, undo/redo, slide panel, properties panel.
"""
from __future__ import annotations

import os
import json
import copy
import math

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QScrollArea,
    QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox, QColorDialog,
    QFileDialog, QMessageBox, QComboBox, QCheckBox, QFrame,
    QToolBar, QSizePolicy, QInputDialog, QDialog, QDialogButtonBox,
    QTabWidget, QTextEdit, QGraphicsScene, QGraphicsView, QGraphicsItem,
    QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsTextItem,
    QGraphicsPixmapItem, QGraphicsLineItem, QApplication, QSlider,
    QGroupBox, QScrollBar, QStackedWidget, QToolButton,
)
from PyQt6.QtCore import (
    Qt, QSize, QRect, QPoint, QPointF, QRectF, QSizeF,
    pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve,
)
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPixmap, QPen, QBrush,
    QFontMetrics, QLinearGradient, QRadialGradient,
    QImage, QAction, QKeySequence, QCursor, QTransform,
    QTextCursor, QTextCharFormat, QTextBlockFormat,
)

# ── Constants ─────────────────────────────────────────────────────────────────

CANVAS_W, CANVAS_H = 1920, 1080   # logical canvas size
HANDLE_SIZE = 10
MAX_UNDO = 50

ET_TEXT    = "text"
ET_IMAGE   = "image"
ET_RECT    = "rect"
ET_ELLIPSE = "ellipse"
ET_LINE    = "line"

_ENTRANCES = ["none", "fade_in", "slide_left", "slide_right",
              "slide_up", "slide_down", "zoom_in", "bounce"]

_STYLE = """
QMainWindow, QWidget { background:#181818; color:#e0e0e0;
    font-family:'Segoe UI',sans-serif; font-size:12px; }
QPushButton { background:#232323; color:#e0e0e0; border:1px solid #2c2c2c;
    border-radius:4px; padding:5px 10px; }
QPushButton:hover { background:#2a2a2a; border-color:#3a3a3a; }
QPushButton:checked { background:#1a3a5c; border-color:#5294e2; color:#5294e2; }
QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox,QTextEdit {
    background:#1c1c1c; color:#e0e0e0; border:1px solid #262626;
    border-radius:4px; padding:4px 6px; }
QLineEdit:focus,QSpinBox:focus { border-color:#5294e2; }
QListWidget { background:#141414; color:#e0e0e0; border:none; }
QListWidget::item { padding:6px 8px; border-radius:3px; margin:1px 2px; }
QListWidget::item:hover { background:#1e1e1e; }
QListWidget::item:selected { background:#1c3a5a; }
QLabel { color:#cccccc; }
QToolBar { background:#0f0f0f; border-bottom:1px solid #1c1c1c;
    padding:2px 4px; spacing:3px; }
QGraphicsView { border:none; background:#111; }
QScrollArea { border:none; }
QGroupBox { border:1px solid #2a2a2a; border-radius:4px;
    margin-top:8px; padding-top:4px; font-size:11px; color:#888; }
QGroupBox::title { subcontrol-origin:margin; left:8px; }
"""


# ══════════════════════════════════════════════════════════════════════════════
# Element helpers
# ══════════════════════════════════════════════════════════════════════════════

def _default_element(kind: str) -> dict:
    base = {
        "type": kind, "x": 200, "y": 200, "w": 400, "h": 100,
        "z": 0, "locked": False, "visible": True,
        "animation": {"entrance": "none", "delay": 0, "duration": 500},
    }
    if kind == ET_TEXT:
        base.update({"text": "Text nou", "font": "Segoe UI", "font_size": 48,
                     "bold": False, "italic": False, "underline": False,
                     "color": "#ffffff", "align": "center",
                     "bg_color": "", "border_color": ""})
    elif kind == ET_IMAGE:
        base.update({"path": "", "opacity": 1.0, "border_radius": 0})
    elif kind == ET_RECT:
        base.update({"fill": "#5294e2", "border_color": "#ffffff",
                     "border_width": 2, "opacity": 1.0, "border_radius": 0})
    elif kind == ET_ELLIPSE:
        base.update({"fill": "#a6e3a1", "border_color": "#ffffff",
                     "border_width": 2, "opacity": 1.0})
    elif kind == ET_LINE:
        base.update({"color": "#ffffff", "line_width": 3,
                     "w": 400, "h": 0})
    return base


def _default_slide() -> dict:
    return {
        "bg_color": "#000000",
        "bg_image": "",
        "bg_gradient": None,
        "elements": [],
        "transition": "fade",
        "transition_ms": 300,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Resize Handle
# ══════════════════════════════════════════════════════════════════════════════

class ResizeHandle(QGraphicsRectItem):
    """Small square handle on corners/edges of a selected element."""

    CURSORS = {
        "tl": Qt.CursorShape.SizeFDiagCursor,
        "tr": Qt.CursorShape.SizeBDiagCursor,
        "bl": Qt.CursorShape.SizeBDiagCursor,
        "br": Qt.CursorShape.SizeFDiagCursor,
        "t":  Qt.CursorShape.SizeVerCursor,
        "b":  Qt.CursorShape.SizeVerCursor,
        "l":  Qt.CursorShape.SizeHorCursor,
        "r":  Qt.CursorShape.SizeHorCursor,
    }

    def __init__(self, pos_key: str, parent):
        s = HANDLE_SIZE
        super().__init__(-s // 2, -s // 2, s, s, parent)
        self.pos_key = pos_key
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setBrush(QBrush(QColor("#5294e2")))
        self.setPen(QPen(QColor("#ffffff"), 1))
        self.setCursor(QCursor(self.CURSORS.get(pos_key, Qt.CursorShape.SizeAllCursor)))
        self.setZValue(9999)

    def mousePressEvent(self, e):
        e.accept()

    def mouseMoveEvent(self, e):
        parent = self.parentItem()
        if parent and hasattr(parent, '_resize_by_handle'):
            delta = e.pos() - e.lastPos()
            parent._resize_by_handle(self.pos_key, delta)

    def mouseReleaseEvent(self, e):
        parent = self.parentItem()
        if parent and hasattr(parent, '_on_resize_done'):
            parent._on_resize_done()
        e.accept()


# ══════════════════════════════════════════════════════════════════════════════
# Base Element Item
# ══════════════════════════════════════════════════════════════════════════════

class BaseElement(QGraphicsItem):
    """Common behaviour for all slide elements."""

    def __init__(self, data: dict, scene_ref):
        super().__init__()
        self.data = data
        self.scene_ref = scene_ref   # weak reference to PresentationScene
        self._handles: dict[str, ResizeHandle] = {}
        self._selected_locally = False

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setPos(data["x"], data["y"])
        self.setZValue(data.get("z", 0))
        self.setVisible(data.get("visible", True))
        self.setOpacity(float(data.get("opacity", 1.0)))
        self._build_handles()

    def _build_handles(self):
        hs = ["tl", "t", "tr", "l", "r", "bl", "b", "br"]
        for key in hs:
            h = ResizeHandle(key, self)
            h.hide()
            self._handles[key] = h
        self._update_handle_positions()

    def _update_handle_positions(self):
        w, h = self.data["w"], self.data["h"]
        positions = {
            "tl": QPointF(0,     0),
            "t":  QPointF(w/2,   0),
            "tr": QPointF(w,     0),
            "l":  QPointF(0,     h/2),
            "r":  QPointF(w,     h/2),
            "bl": QPointF(0,     h),
            "b":  QPointF(w/2,   h),
            "br": QPointF(w,     h),
        }
        for key, pos in positions.items():
            if key in self._handles:
                self._handles[key].setPos(pos)

    def set_selected_state(self, sel: bool):
        self._selected_locally = sel
        for h in self._handles.values():
            h.setVisible(sel and not self.data.get("locked"))
        self.update()

    def boundingRect(self):
        return QRectF(0, 0, self.data["w"], self.data["h"])

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.data["x"] = int(self.pos().x())
            self.data["y"] = int(self.pos().y())
            if self.scene_ref and hasattr(self.scene_ref, '_on_element_changed'):
                self.scene_ref._on_element_changed()
        return super().itemChange(change, value)

    def _resize_by_handle(self, key: str, delta: QPointF):
        dx, dy = delta.x(), delta.y()
        x, y, w, h = self.data["x"], self.data["y"], self.data["w"], self.data["h"]
        if "l" in key:
            x += dx; w -= dx
        if "r" in key:
            w += dx
        if "t" in key:
            y += dy; h -= dy
        if "b" in key:
            h += dy
        w = max(20, w)
        h = max(20, h)
        self.data.update({"x": int(x), "y": int(y), "w": int(w), "h": int(h)})
        self.setPos(x, y)
        self.prepareGeometryChange()
        self._update_handle_positions()
        self.update()

    def _on_resize_done(self):
        if self.scene_ref and hasattr(self.scene_ref, '_on_element_changed'):
            self.scene_ref._on_element_changed()

    def contextMenuEvent(self, e):
        from PyQt6.QtWidgets import QMenu
        menu = QMenu()
        menu.addAction("🗑 Șterge", lambda: self._delete_self())
        menu.addAction("🔝 Aduce în față", lambda: self._bring_forward())
        menu.addAction("🔙 Trimite în spate", lambda: self._send_back())
        locked = self.data.get("locked", False)
        menu.addAction("🔓 Deblochează" if locked else "🔒 Blochează",
                       lambda: self._toggle_lock())
        menu.exec(e.screenPos())

    def _delete_self(self):
        if self.scene():
            self.scene().removeItem(self)
            if self.scene_ref:
                self.scene_ref._on_element_deleted(self.data)

    def _bring_forward(self):
        self.data["z"] = self.data.get("z", 0) + 1
        self.setZValue(self.data["z"])

    def _send_back(self):
        self.data["z"] = self.data.get("z", 0) - 1
        self.setZValue(self.data["z"])

    def _toggle_lock(self):
        self.data["locked"] = not self.data.get("locked", False)
        locked = self.data["locked"]
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not locked)
        for h in self._handles.values():
            h.setVisible(self._selected_locally and not locked)


# ══════════════════════════════════════════════════════════════════════════════
# Concrete Element Types
# ══════════════════════════════════════════════════════════════════════════════

class TextElement(BaseElement):
    def __init__(self, data, scene_ref):
        super().__init__(data, scene_ref)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)

    def paint(self, p, option, widget=None):
        d = self.data
        w, h = d["w"], d["h"]
        # Background
        bg = d.get("bg_color", "")
        if bg:
            p.fillRect(QRectF(0, 0, w, h), QColor(bg))
        # Border
        bc = d.get("border_color", "")
        if bc:
            p.setPen(QPen(QColor(bc), 2))
            p.drawRect(QRectF(0, 0, w, h))
        # Text
        font = QFont(d.get("font", "Segoe UI"), int(d.get("font_size", 48)))
        font.setBold(d.get("bold", False))
        font.setItalic(d.get("italic", False))
        font.setUnderline(d.get("underline", False))
        p.setFont(font)
        p.setPen(QColor(d.get("color", "#ffffff")))
        align_map = {
            "left":   Qt.AlignmentFlag.AlignLeft,
            "center": Qt.AlignmentFlag.AlignHCenter,
            "right":  Qt.AlignmentFlag.AlignRight,
        }
        align = align_map.get(d.get("align", "center"), Qt.AlignmentFlag.AlignHCenter)
        flags = align | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap
        p.drawText(QRectF(4, 4, w - 8, h - 8), flags, d.get("text", ""))
        # Selection outline
        if self._selected_locally:
            p.setPen(QPen(QColor("#5294e2"), 2, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(0, 0, w, h))

    def mouseDoubleClickEvent(self, e):
        """Inline text edit via QInputDialog."""
        text, ok = QInputDialog.getMultiLineText(
            None, "Editare text", "Text:", self.data.get("text", "")
        )
        if ok:
            self.data["text"] = text
            self.update()
            if self.scene_ref:
                self.scene_ref._on_element_changed()


class ImageElement(BaseElement):
    def __init__(self, data, scene_ref):
        super().__init__(data, scene_ref)
        self._pixmap: QPixmap | None = None
        self._load_pixmap()

    def _load_pixmap(self):
        path = self.data.get("path", "")
        if path and os.path.exists(path):
            self._pixmap = QPixmap(path)
        else:
            self._pixmap = None

    def paint(self, p, option, widget=None):
        d = self.data
        w, h = d["w"], d["h"]
        p.setOpacity(float(d.get("opacity", 1.0)))
        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                int(w), int(h),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            ox = (w - scaled.width()) / 2
            oy = (h - scaled.height()) / 2
            p.drawPixmap(int(ox), int(oy), scaled)
        else:
            p.fillRect(QRectF(0, 0, w, h), QColor("#333333"))
            p.setPen(QColor("#888888"))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "🖼 Imagine\n(fără cale)")
        p.setOpacity(1.0)
        if self._selected_locally:
            p.setPen(QPen(QColor("#5294e2"), 2, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(0, 0, w, h))


class ShapeElement(BaseElement):
    def paint(self, p, option, widget=None):
        d = self.data
        w, h = d["w"], d["h"]
        kind = d["type"]
        fill = QColor(d.get("fill", "#5294e2"))
        border_color = QColor(d.get("border_color", "#ffffff"))
        border_w = int(d.get("border_width", 2))
        p.setOpacity(float(d.get("opacity", 1.0)))
        p.setBrush(QBrush(fill))
        p.setPen(QPen(border_color, border_w))
        if kind == ET_RECT:
            r = int(d.get("border_radius", 0))
            if r > 0:
                p.drawRoundedRect(QRectF(0, 0, w, h), r, r)
            else:
                p.drawRect(QRectF(0, 0, w, h))
        elif kind == ET_ELLIPSE:
            p.drawEllipse(QRectF(0, 0, w, h))
        elif kind == ET_LINE:
            p.setPen(QPen(QColor(d.get("color", "#ffffff")), int(d.get("line_width", 3))))
            p.drawLine(QPointF(0, 0), QPointF(w, h))
        p.setOpacity(1.0)
        if self._selected_locally:
            p.setPen(QPen(QColor("#5294e2"), 2, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(0, 0, w, h))


def _make_element(data: dict, scene_ref) -> BaseElement:
    kind = data.get("type")
    if kind == ET_TEXT:
        return TextElement(data, scene_ref)
    if kind == ET_IMAGE:
        return ImageElement(data, scene_ref)
    return ShapeElement(data, scene_ref)


# ══════════════════════════════════════════════════════════════════════════════
# Presentation Scene
# ══════════════════════════════════════════════════════════════════════════════

class PresentationScene(QGraphicsScene):
    element_selected = pyqtSignal(dict)   # emitted when an element is selected
    element_changed  = pyqtSignal()       # any geometry / property change
    selection_cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(0, 0, CANVAS_W, CANVAS_H, parent)
        self._slide_data: dict = _default_slide()
        self._items: list[BaseElement] = []
        self._selected_item: BaseElement | None = None
        self._bg_rect = None
        self._draw_background()

    # ── Background ────────────────────────────────────────────────────────────

    def _draw_background(self):
        if self._bg_rect:
            self.removeItem(self._bg_rect)
        d = self._slide_data
        bg_color = QColor(d.get("bg_color", "#000000"))
        self._bg_rect = self.addRect(
            0, 0, CANVAS_W, CANVAS_H,
            QPen(Qt.PenStyle.NoPen), QBrush(bg_color)
        )
        self._bg_rect.setZValue(-1000)

        # Background image
        bg_image = d.get("bg_image", "")
        if bg_image and os.path.exists(bg_image):
            pix = QPixmap(bg_image).scaled(
                CANVAS_W, CANVAS_H,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            pix_item = self.addPixmap(pix)
            pix_item.setZValue(-999)

    # ── Load slide data ───────────────────────────────────────────────────────

    def load_slide(self, slide_data: dict):
        self.clear()
        self._items.clear()
        self._selected_item = None
        self._bg_rect = None
        self._slide_data = slide_data
        self._draw_background()
        for el in slide_data.get("elements", []):
            item = _make_element(el, self)
            self.addItem(item)
            self._items.append(item)

    def get_slide_data(self) -> dict:
        return self._slide_data

    # ── Selection ─────────────────────────────────────────────────────────────

    def _deselect_all(self):
        for it in self._items:
            it.set_selected_state(False)
        self._selected_item = None

    def _select_item(self, item: BaseElement):
        self._deselect_all()
        self._selected_item = item
        item.set_selected_state(True)
        self.element_selected.emit(item.data)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            items_at = [it for it in self.items(e.scenePos())
                        if isinstance(it, BaseElement)]
            if items_at:
                self._select_item(items_at[0])
            else:
                self._deselect_all()
                self.selection_cleared.emit()
        super().mousePressEvent(e)

    # ── Element add ───────────────────────────────────────────────────────────

    def add_element(self, kind: str) -> BaseElement:
        d = _default_element(kind)
        # Place at centre of canvas
        d["x"] = (CANVAS_W - d["w"]) // 2
        d["y"] = (CANVAS_H - d["h"]) // 2
        self._slide_data.setdefault("elements", []).append(d)
        item = _make_element(d, self)
        self.addItem(item)
        self._items.append(item)
        self._select_item(item)
        return item

    # ── Element lifecycle ─────────────────────────────────────────────────────

    def _on_element_changed(self):
        self.element_changed.emit()

    def _on_element_deleted(self, data: dict):
        elements = self._slide_data.get("elements", [])
        if data in elements:
            elements.remove(data)
        self._items = [it for it in self._items if it.data is not data]
        if self._selected_item and self._selected_item.data is data:
            self._selected_item = None
            self.selection_cleared.emit()
        self.element_changed.emit()

    # ── Ordering ──────────────────────────────────────────────────────────────

    def delete_selected(self):
        if self._selected_item:
            self._selected_item._delete_self()

    def bring_forward(self):
        if self._selected_item:
            self._selected_item._bring_forward()

    def send_back(self):
        if self._selected_item:
            self._selected_item._send_back()

    # ── Thumbnail ─────────────────────────────────────────────────────────────

    def render_thumbnail(self, w: int, h: int) -> QPixmap:
        pix = QPixmap(w, h)
        pix.fill(QColor(self._slide_data.get("bg_color", "#000000")))
        p = QPainter(pix)
        self.render(p, QRectF(0, 0, w, h), QRectF(0, 0, CANVAS_W, CANVAS_H))
        p.end()
        return pix


# ══════════════════════════════════════════════════════════════════════════════
# Slide View
# ══════════════════════════════════════════════════════════════════════════════

class SlideView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self._zoom = 1.0

    def fit_to_view(self):
        self.fitInView(
            QRectF(0, 0, CANVAS_W, CANVAS_H),
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        self._zoom = self.transform().m11()

    def wheelEvent(self, e):
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
            self._zoom *= factor
            self._zoom = max(0.1, min(self._zoom, 8.0))
            self.setTransform(QTransform().scale(self._zoom, self._zoom))
        else:
            super().wheelEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.fit_to_view()


# ══════════════════════════════════════════════════════════════════════════════
# Properties Panel
# ══════════════════════════════════════════════════════════════════════════════

class PropertiesPanel(QWidget):
    """Right panel — shows element properties based on selection."""

    changed = pyqtSignal(dict)   # emits updated data dict

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: dict | None = None
        self._blocking = False

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        self._no_sel_lbl = QLabel("Selectează un element\npentru a edita proprietățile")
        self._no_sel_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_sel_lbl.setStyleSheet("color:#555; font-size:12px;")
        root.addWidget(self._no_sel_lbl)

        self._stack = QStackedWidget()
        root.addWidget(self._stack, 1)

        # Page 0 — empty
        self._stack.addWidget(QWidget())

        # Page 1 — common + type-specific
        self._prop_widget = QWidget()
        prop_layout = QVBoxLayout(self._prop_widget)
        prop_layout.setContentsMargins(0, 0, 0, 0)
        prop_layout.setSpacing(6)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(self._prop_widget)
        self._stack.addWidget(self._scroll)

        self._form = QFormLayout()
        self._form.setSpacing(6)
        self._form.setContentsMargins(0, 0, 0, 0)
        prop_layout.addLayout(self._form)
        prop_layout.addStretch()

        self.clear_selection()

    # ── API ───────────────────────────────────────────────────────────────────

    def clear_selection(self):
        self._data = None
        self._no_sel_lbl.show()
        self._stack.setCurrentIndex(0)

    def load_element(self, data: dict):
        self._data = data
        self._no_sel_lbl.hide()
        self._stack.setCurrentIndex(1)
        self._rebuild_form(data)

    def _rebuild_form(self, d: dict):
        # Clear existing form rows
        while self._form.rowCount():
            self._form.removeRow(0)

        kind = d.get("type")
        self._add_row("Tip", QLabel(kind.upper() if kind else ""))

        # Position / size
        self._add_spinbox("X", "x", d, 0, CANVAS_W)
        self._add_spinbox("Y", "y", d, 0, CANVAS_H)
        self._add_spinbox("Lățime", "w", d, 20, CANVAS_W)
        self._add_spinbox("Înălțime", "h", d, 20, CANVAS_H)

        if kind == ET_TEXT:
            self._add_lineedit("Text", "text", d)
            self._add_spinbox("Font size", "font_size", d, 8, 400)
            self._add_color_btn("Culoare text", "color", d)
            self._add_checkbox("Bold", "bold", d)
            self._add_checkbox("Italic", "italic", d)
            self._add_checkbox("Subliniat", "underline", d)
            align_combo = QComboBox()
            for a in ["left", "center", "right"]:
                align_combo.addItem(a)
            align_combo.setCurrentText(d.get("align", "center"))
            align_combo.currentTextChanged.connect(
                lambda v: self._set("align", v))
            self._add_row("Aliniere", align_combo)
            self._add_color_btn("Fundal text", "bg_color", d, allow_empty=True)

        elif kind == ET_IMAGE:
            path_btn = QPushButton("📁 Alege imagine…")
            path_btn.clicked.connect(self._pick_image)
            self._add_row("Fișier", path_btn)
            self._add_dbl_spinbox("Opacitate", "opacity", d, 0.0, 1.0)

        elif kind in (ET_RECT, ET_ELLIPSE):
            self._add_color_btn("Culoare umplere", "fill", d)
            self._add_color_btn("Culoare contur", "border_color", d)
            self._add_spinbox("Grosime contur", "border_width", d, 0, 20)
            self._add_dbl_spinbox("Opacitate", "opacity", d, 0.0, 1.0)
            if kind == ET_RECT:
                self._add_spinbox("Colțuri rotunde", "border_radius", d, 0, 100)

        elif kind == ET_LINE:
            self._add_color_btn("Culoare linie", "color", d)
            self._add_spinbox("Grosime", "line_width", d, 1, 30)

        # Animation section
        self._add_section("Animație intrare")
        anim = d.setdefault("animation", {})
        ent_combo = QComboBox()
        for e in _ENTRANCES:
            ent_combo.addItem(e)
        ent_combo.setCurrentText(anim.get("entrance", "none"))
        ent_combo.currentTextChanged.connect(
            lambda v: self._set_anim("entrance", v))
        self._add_row("Efect", ent_combo)
        self._add_spinbox_anim("Delay (ms)", "delay", anim, 0, 5000)
        self._add_spinbox_anim("Durată (ms)", "duration", anim, 100, 3000)

    # ── Form helpers ──────────────────────────────────────────────────────────

    def _add_row(self, label: str, widget: QWidget):
        lbl = QLabel(label)
        lbl.setStyleSheet("color:#aaa; font-size:11px;")
        self._form.addRow(lbl, widget)

    def _add_section(self, title: str):
        sep = QLabel(f"── {title} ──")
        sep.setStyleSheet("color:#5294e2; font-size:10px; font-weight:700; letter-spacing:1px;")
        self._form.addRow(sep)

    def _add_lineedit(self, label, key, d):
        w = QLineEdit(str(d.get(key, "")))
        w.textChanged.connect(lambda v: self._set(key, v))
        self._add_row(label, w)

    def _add_spinbox(self, label, key, d, mn, mx):
        w = QSpinBox()
        w.setRange(mn, mx)
        w.setValue(int(d.get(key, 0)))
        w.valueChanged.connect(lambda v: self._set(key, v))
        self._add_row(label, w)

    def _add_spinbox_anim(self, label, key, d, mn, mx):
        w = QSpinBox()
        w.setRange(mn, mx)
        w.setValue(int(d.get(key, 0)))
        w.valueChanged.connect(lambda v: self._set_anim(key, v))
        self._add_row(label, w)

    def _add_dbl_spinbox(self, label, key, d, mn, mx):
        w = QDoubleSpinBox()
        w.setRange(mn, mx)
        w.setSingleStep(0.1)
        w.setValue(float(d.get(key, 1.0)))
        w.valueChanged.connect(lambda v: self._set(key, round(v, 2)))
        self._add_row(label, w)

    def _add_color_btn(self, label, key, d, allow_empty=False):
        current = d.get(key, "")
        btn = QPushButton()
        btn.setFixedHeight(26)
        if current:
            btn.setStyleSheet(f"background:{current}; border:1px solid #444; border-radius:3px;")
            btn.setText("")
        else:
            btn.setText("(fără)")

        def pick():
            col = QColorDialog.getColor(
                QColor(current) if current else QColor("#ffffff"), None, label
            )
            if col.isValid():
                new_color = col.name()
                self._set(key, new_color)
                btn.setStyleSheet(
                    f"background:{new_color}; border:1px solid #444; border-radius:3px;"
                )
                btn.setText("")

        btn.clicked.connect(pick)
        self._add_row(label, btn)

    def _add_checkbox(self, label, key, d):
        cb = QCheckBox()
        cb.setChecked(bool(d.get(key, False)))
        cb.toggled.connect(lambda v: self._set(key, v))
        self._add_row(label, cb)

    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Alege imagine", "",
            "Imagini (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
        )
        if path and self._data:
            self._data["path"] = path
            self.changed.emit(self._data)

    def _set(self, key, value):
        if self._data is not None:
            self._data[key] = value
            self.changed.emit(self._data)

    def _set_anim(self, key, value):
        if self._data is not None:
            self._data.setdefault("animation", {})[key] = value
            self.changed.emit(self._data)


# ══════════════════════════════════════════════════════════════════════════════
# Slide List Panel
# ══════════════════════════════════════════════════════════════════════════════

class SlideListPanel(QWidget):
    slide_selected = pyqtSignal(int)
    slide_added    = pyqtSignal()
    slide_deleted  = pyqtSignal(int)
    slide_duplicated = pyqtSignal(int)

    THUMB_W, THUMB_H = 160, 90

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(190)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        hdr = QLabel("SLIDE-URI")
        hdr.setStyleSheet("color:#5294e2; font-size:10px; font-weight:700; letter-spacing:2px;")
        layout.addWidget(hdr)

        self._list = QListWidget()
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._list.setSpacing(2)
        self._list.currentRowChanged.connect(self.slide_selected)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self._list, 1)

        add_btn = QPushButton("➕ Slide nou")
        add_btn.clicked.connect(self.slide_added)
        layout.addWidget(add_btn)

    def populate(self, slides: list[dict], current: int = 0):
        self._list.blockSignals(True)
        self._list.clear()
        for i, s in enumerate(slides):
            item = QListWidgetItem(f"Slide {i + 1}")
            bg = s.get("bg_color", "#000000")
            item.setBackground(QColor(bg))
            item.setForeground(QColor("#e0e0e0"))
            self._list.addItem(item)
        self._list.blockSignals(False)
        if 0 <= current < self._list.count():
            self._list.setCurrentRow(current)

    def update_thumbnail(self, idx: int, pix: QPixmap):
        item = self._list.item(idx)
        if item:
            item.setIcon(pix.scaled(
                self.THUMB_W, self.THUMB_H,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
            self._list.setIconSize(QSize(self.THUMB_W, self.THUMB_H))

    def _context_menu(self, pos):
        from PyQt6.QtWidgets import QMenu
        idx = self._list.currentRow()
        menu = QMenu(self)
        menu.addAction("🗑 Șterge", lambda: self.slide_deleted.emit(idx))
        menu.addAction("📋 Duplică", lambda: self.slide_duplicated.emit(idx))
        menu.exec(self._list.mapToGlobal(pos))


# ══════════════════════════════════════════════════════════════════════════════
# Background Dialog
# ══════════════════════════════════════════════════════════════════════════════

class BackgroundDialog(QDialog):
    def __init__(self, slide_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fundal Slide")
        self.setFixedSize(400, 220)
        self.setStyleSheet(_STYLE)
        self.slide_data = slide_data

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Solid color
        self._color_btn = QPushButton()
        self._color_btn.setFixedHeight(28)
        bg = slide_data.get("bg_color", "#000000")
        self._color_btn.setStyleSheet(f"background:{bg}; border:1px solid #444; border-radius:3px;")
        self._color_btn.clicked.connect(self._pick_color)
        form.addRow("Culoare:", self._color_btn)

        # Background image
        self._img_edit = QLineEdit(slide_data.get("bg_image", ""))
        form.addRow("Imagine:", self._img_edit)
        img_btn = QPushButton("📁…")
        img_btn.setFixedWidth(36)
        img_btn.clicked.connect(self._pick_image)
        row = QHBoxLayout()
        row.addWidget(self._img_edit)
        row.addWidget(img_btn)
        form.addRow("", row)

        layout.addLayout(form)
        layout.addStretch()

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._apply)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _pick_color(self):
        col = QColorDialog.getColor(
            QColor(self.slide_data.get("bg_color", "#000000")), self
        )
        if col.isValid():
            self.slide_data["bg_color"] = col.name()
            self._color_btn.setStyleSheet(
                f"background:{col.name()}; border:1px solid #444; border-radius:3px;"
            )

    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Alege imagine fundal", "",
            "Imagini (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if path:
            self._img_edit.setText(path)

    def _apply(self):
        self.slide_data["bg_image"] = self._img_edit.text().strip()
        self.accept()


# ══════════════════════════════════════════════════════════════════════════════
# Main Presentation Editor Window
# ══════════════════════════════════════════════════════════════════════════════

class PresentationEditor(QMainWindow):
    """Full presentation editor — QGraphicsScene based."""

    # Emitted after a successful save: (pres_id, title, slides)
    saved = pyqtSignal(int, str, list)

    def __init__(self,
                 pres_id: int | None = None,
                 title: str = "",
                 slides: list | None = None,
                 parent=None):
        super().__init__(parent)
        self.setMinimumSize(1280, 720)
        self.setStyleSheet(_STYLE)

        self._pres_id = pres_id
        # Pre-populate from caller if provided (open existing); else blank slide
        if slides:
            raw = slides
            self._slides = json.loads(raw) if isinstance(raw, str) else list(raw)
        else:
            self._slides = [_default_slide()]

        # Window title
        if title:
            self._presentation_title = title
            self.setWindowTitle(f"Cantio — Editor Prezentări — {title}")
        else:
            self._presentation_title = "Prezentare nouă"
            self.setWindowTitle("Cantio — Editor Prezentări")

        self._current_slide = 0
        self._undo_stack: list[list[dict]] = []   # list of slide-list snapshots
        self._redo_stack: list[list[dict]] = []
        self._modified = False
        self._interactive_tutorial = None

        self._scene = PresentationScene()
        self._scene.element_selected.connect(self._on_element_selected)
        self._scene.element_changed.connect(self._on_element_changed)
        self._scene.selection_cleared.connect(self._on_selection_cleared)

        self._build_ui()
        self._load_presentation()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Main toolbar
        tb = QToolBar("Elemente", self)
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        self.addToolBar(tb)
        self._build_toolbar(tb)

        # Central area
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Left: slide list
        self._slide_panel = SlideListPanel()
        self._slide_panel.slide_selected.connect(self._switch_slide)
        self._slide_panel.slide_added.connect(self._add_slide)
        self._slide_panel.slide_deleted.connect(self._delete_slide)
        self._slide_panel.slide_duplicated.connect(self._duplicate_slide)
        root.addWidget(self._slide_panel)

        # Centre: canvas
        self._view = SlideView(self._scene)
        root.addWidget(self._view, 1)

        # Right: properties
        self._props = PropertiesPanel()
        self._props.setFixedWidth(260)
        self._props.changed.connect(self._on_props_changed)
        root.addWidget(self._props)

        self._update_slide_panel()

    def _build_toolbar(self, tb: QToolBar):
        _S = ("QPushButton { background:#1c1c1c; color:#ccc; border:1px solid #2a2a2a; "
              "border-radius:4px; padding:5px 10px; }"
              "QPushButton:hover { background:#252525; color:#fff; }"
              "QPushButton:checked { background:#1a3a5c; color:#5294e2; border-color:#5294e2; }")

        def _btn(label, slot, tip=""):
            b = QPushButton(label)
            b.setToolTip(tip)
            b.setStyleSheet(_S)
            b.clicked.connect(slot)
            tb.addWidget(b)
            return b

        _btn("💾 Salvează",  self._save,          "Ctrl+S")
        _btn("📤 Export",    self._export_json,    "Export JSON")
        _btn("📥 Import",    self._import_json,    "Import JSON")
        tb.addSeparator()

        _btn("T Text",     lambda: self._add_element(ET_TEXT),    "Adaugă text")
        _btn("□ Drept.",   lambda: self._add_element(ET_RECT),    "Adaugă dreptunghi")
        _btn("○ Elipsă",   lambda: self._add_element(ET_ELLIPSE), "Adaugă elipsă")
        _btn("— Linie",    lambda: self._add_element(ET_LINE),    "Adaugă linie")
        _btn("🖼 Imagine",  lambda: self._add_image_element(),    "Adaugă imagine")
        tb.addSeparator()

        _btn("↑ Înainte",  self._scene.bring_forward, "Aduce elementul în față")
        _btn("↓ Înapoi",   self._scene.send_back,     "Trimite elementul în spate")
        _btn("🗑 Șterge",   self._scene.delete_selected, "Șterge elementul selectat")
        tb.addSeparator()

        _btn("🖼 Fundal",   self._edit_background,   "Setează fundalul slide-ului")
        tb.addSeparator()

        _btn("↩ Undo",     self._undo,  "Ctrl+Z")
        _btn("↪ Redo",     self._redo,  "Ctrl+Y")

        # Zoom label
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        self._zoom_lbl = QLabel("Zoom: 100%")
        self._zoom_lbl.setStyleSheet("color:#555; font-size:11px; padding-right:10px;")
        tb.addWidget(self._zoom_lbl)

        # Keyboard shortcuts
        from PyQt6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._save)
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self._undo)
        QShortcut(QKeySequence("Ctrl+Y"), self).activated.connect(self._redo)
        QShortcut(QKeySequence("Delete"), self).activated.connect(
            self._scene.delete_selected)

    # ── Slide management ──────────────────────────────────────────────────────

    def _switch_slide(self, idx: int):
        if idx < 0 or idx >= len(self._slides):
            return
        # Save current scene state back to slide
        self._push_snapshot()
        self._current_slide = idx
        self._scene.load_slide(self._slides[idx])
        self._props.clear_selection()

    def _add_slide(self):
        self._push_snapshot()
        new_s = _default_slide()
        self._slides.insert(self._current_slide + 1, new_s)
        self._current_slide += 1
        self._update_slide_panel()
        self._scene.load_slide(new_s)

    def _delete_slide(self, idx: int):
        if len(self._slides) <= 1:
            QMessageBox.information(self, "Info", "Trebuie să existe cel puțin un slide.")
            return
        self._push_snapshot()
        self._slides.pop(idx)
        self._current_slide = max(0, min(self._current_slide, len(self._slides) - 1))
        self._update_slide_panel()
        self._scene.load_slide(self._slides[self._current_slide])

    def _duplicate_slide(self, idx: int):
        if 0 <= idx < len(self._slides):
            self._push_snapshot()
            dup = copy.deepcopy(self._slides[idx])
            self._slides.insert(idx + 1, dup)
            self._update_slide_panel()

    def _update_slide_panel(self):
        self._slide_panel.populate(self._slides, self._current_slide)
        # Update thumbnail for current slide
        QTimer.singleShot(50, self._refresh_thumbnail)

    def _refresh_thumbnail(self):
        try:
            pix = self._scene.render_thumbnail(160, 90)
            self._slide_panel.update_thumbnail(self._current_slide, pix)
        except Exception:
            pass

    # ── Element operations ────────────────────────────────────────────────────

    def _add_element(self, kind: str):
        self._push_snapshot()
        self._scene.add_element(kind)
        self._modified = True

    def _add_image_element(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Alege imagine", "",
            "Imagini (*.png *.jpg *.jpeg *.bmp *.gif *.webp)"
        )
        if path:
            self._push_snapshot()
            item = self._scene.add_element(ET_IMAGE)
            item.data["path"] = path
            item._load_pixmap()
            item.update()
            self._modified = True

    def _on_element_selected(self, data: dict):
        self._props.load_element(data)

    def _on_element_changed(self):
        self._modified = True
        self._refresh_thumbnail()

    def _on_selection_cleared(self):
        self._props.clear_selection()

    def _on_props_changed(self, data: dict):
        # Refresh the scene item (find it and update)
        self._modified = True
        for item in self._scene._items:
            if item.data is data:
                item.prepareGeometryChange()
                item._update_handle_positions()
                item.setPos(data.get("x", 0), data.get("y", 0))
                item.setOpacity(float(data.get("opacity", 1.0)))
                # Reload pixmap for image elements
                if isinstance(item, ImageElement):
                    item._load_pixmap()
                item.update()
                break
        self._refresh_thumbnail()

    # ── Background ────────────────────────────────────────────────────────────

    def _edit_background(self):
        dlg = BackgroundDialog(self._slides[self._current_slide], self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._scene.load_slide(self._slides[self._current_slide])
            self._modified = True

    # ── Undo / Redo ───────────────────────────────────────────────────────────

    def _push_snapshot(self):
        snap = copy.deepcopy(self._slides)
        self._undo_stack.append(snap)
        if len(self._undo_stack) > MAX_UNDO:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _undo(self):
        if not self._undo_stack:
            return
        self._redo_stack.append(copy.deepcopy(self._slides))
        self._slides = self._undo_stack.pop()
        self._current_slide = min(self._current_slide, len(self._slides) - 1)
        self._update_slide_panel()
        self._scene.load_slide(self._slides[self._current_slide])

    def _redo(self):
        if not self._redo_stack:
            return
        self._undo_stack.append(copy.deepcopy(self._slides))
        self._slides = self._redo_stack.pop()
        self._current_slide = min(self._current_slide, len(self._slides) - 1)
        self._update_slide_panel()
        self._scene.load_slide(self._slides[self._current_slide])

    # ── Save / Load ───────────────────────────────────────────────────────────

    def _load_presentation(self):
        if self._pres_id is None:
            self._scene.load_slide(self._slides[0])
            return
        try:
            import database as db
            pres = db.get_presentation(self._pres_id)
            if pres:
                self.setWindowTitle(f"Cantio — {pres.get('title', 'Prezentare')}")
                raw = pres.get("slides", pres.get("slides_json", []))
                slides = json.loads(raw) if isinstance(raw, str) else raw
                if slides:
                    self._slides = slides
                    self._current_slide = 0
                    self._update_slide_panel()
                    self._scene.load_slide(self._slides[0])
        except Exception as e:
            print(f"[PRES EDITOR] Load error: {e}")

    def _save(self):
        try:
            import database as db
            if self._pres_id is None:
                title, ok = QInputDialog.getText(
                    self, "Salvează", "Titlu prezentare:",
                    text=self._presentation_title,
                )
                if not ok or not title.strip():
                    return
                title = title.strip()
                self._pres_id = db.add_presentation(title, self._slides)
                self._presentation_title = title
                self.setWindowTitle(f"Cantio — Editor Prezentări — {title}")
            else:
                pres = db.get_presentation(self._pres_id)
                title = pres.get("title", self._presentation_title) if pres else self._presentation_title
                db.update_presentation(self._pres_id, title, self._slides)
                self._presentation_title = title
            self._modified = False
            self.saved.emit(self._pres_id, self._presentation_title, self._slides)
            try:
                from toast_notifications import show_toast
                show_toast("✅ Prezentare salvată", "success")
            except Exception:
                pass
        except Exception as e:
            QMessageBox.critical(self, "Eroare", f"Salvare eșuată:\n{e}")

    def _export_json(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export prezentare", "prezentare.json",
            "JSON (*.json)"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"slides": self._slides}, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "Export", f"Salvat în:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Eroare", str(e))

    def _import_json(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import prezentare", "", "JSON (*.json)"
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                slides = data.get("slides", data if isinstance(data, list) else [])
                if slides:
                    self._push_snapshot()
                    self._slides = slides
                    self._current_slide = 0
                    self._update_slide_panel()
                    self._scene.load_slide(self._slides[0])
            except Exception as e:
                QMessageBox.critical(self, "Eroare import", str(e))

    def closeEvent(self, event):
        if self._modified:
            r = QMessageBox.question(
                self, "Modificări nesalvate",
                "Prezentarea are modificări nesalvate. Salvați înainte de a închide?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel,
            )
            if r == QMessageBox.StandardButton.Save:
                self._save()
            elif r == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        event.accept()


# ── Backward-compat alias (old code imports PresentationEditorWindow) ─────────

PresentationEditorWindow = PresentationEditor


# ── Slide renderer helper used by display + service manager ───────────────────

def render_slide_to_pixmap(slide_data: dict, w: int, h: int) -> QPixmap:
    """Render a slide dict to a QPixmap of size w×h."""
    pix = QPixmap(w, h)
    pix.fill(QColor(slide_data.get("bg_color", "#000000")))
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    bg_image = slide_data.get("bg_image", "")
    if bg_image and os.path.exists(bg_image):
        bg_pix = QPixmap(bg_image).scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        opacity = float(slide_data.get("bg_opacity", 0.8))
        p.setOpacity(opacity)
        p.drawPixmap(0, 0, bg_pix)
        p.setOpacity(1.0)

    # Scale factor from 1920x1080 logical to actual output size
    sx = w / CANVAS_W
    sy = h / CANVAS_H

    for el in slide_data.get("elements", []):
        if not el.get("visible", True):
            continue
        kind = el.get("type")
        ex = int(el.get("x", 0) * sx)
        ey = int(el.get("y", 0) * sy)
        ew = int(el.get("w", 100) * sx)
        eh = int(el.get("h", 40) * sy)
        p.setOpacity(float(el.get("opacity", 1.0)))

        if kind == ET_TEXT:
            font = QFont(el.get("font", "Segoe UI"),
                         max(1, int(el.get("font_size", 48) * sx)))
            font.setBold(el.get("bold", False))
            font.setItalic(el.get("italic", False))
            p.setFont(font)
            p.setPen(QColor(el.get("color", "#ffffff")))
            align_map = {
                "left":   Qt.AlignmentFlag.AlignLeft,
                "center": Qt.AlignmentFlag.AlignHCenter,
                "right":  Qt.AlignmentFlag.AlignRight,
            }
            align = align_map.get(el.get("align", "center"),
                                   Qt.AlignmentFlag.AlignHCenter)
            flags = align | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap
            p.drawText(QRect(ex, ey, ew, eh), flags, el.get("text", ""))

        elif kind == ET_IMAGE:
            path = el.get("path", "")
            if path and os.path.exists(path):
                img_pix = QPixmap(path).scaled(
                    ew, eh,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                p.drawPixmap(ex, ey, img_pix)

        elif kind in (ET_RECT, ET_ELLIPSE):
            fill = QColor(el.get("fill", "#5294e2"))
            bc = QColor(el.get("border_color", "#ffffff"))
            bw = max(1, int(el.get("border_width", 2) * sx))
            p.setBrush(QBrush(fill))
            p.setPen(QPen(bc, bw))
            if kind == ET_RECT:
                r = int(el.get("border_radius", 0) * sx)
                if r > 0:
                    p.drawRoundedRect(QRect(ex, ey, ew, eh), r, r)
                else:
                    p.drawRect(QRect(ex, ey, ew, eh))
            else:
                p.drawEllipse(QRect(ex, ey, ew, eh))

        elif kind == ET_LINE:
            lw = max(1, int(el.get("line_width", 3) * sx))
            p.setPen(QPen(QColor(el.get("color", "#ffffff")), lw))
            p.drawLine(ex, ey, ex + ew, ey + eh)

        p.setOpacity(1.0)

    p.end()
    return pix
