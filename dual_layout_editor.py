"""
Cantio - Dual Language Layout Editor
Visual 16:9 canvas with drag-and-drop zones for original + translated text.
Layout saved to settings.json under "dual_language_layout".
"""
from __future__ import annotations
import json

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QDoubleSpinBox, QColorDialog, QGroupBox,
    QFormLayout, QWidget, QSizePolicy, QFrame, QScrollArea,
)
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QFontMetrics

import database as db


_DEFAULT_LAYOUT = {
    "original": {
        "x": 0.0, "y": 0.0, "width": 1.0, "height": 0.55,
        "font_size": 48, "color": "#ffffff", "align": "center",
        "bg": "transparent", "padding": 20,
    },
    "translation": {
        "x": 0.0, "y": 0.58, "width": 1.0, "height": 0.38,
        "font_size": 32, "color": "#cccccc", "align": "center",
        "bg": "transparent", "padding": 16,
    },
}

_PRESETS = {
    "Original sus / Traducere jos": {
        "original":    {"x": 0.0, "y": 0.05, "width": 1.0, "height": 0.50},
        "translation": {"x": 0.0, "y": 0.58, "width": 1.0, "height": 0.37},
    },
    "Original jos / Traducere sus": {
        "original":    {"x": 0.0, "y": 0.55, "width": 1.0, "height": 0.40},
        "translation": {"x": 0.0, "y": 0.05, "width": 1.0, "height": 0.45},
    },
    "Original stânga / Traducere dreapta": {
        "original":    {"x": 0.02, "y": 0.1, "width": 0.46, "height": 0.80},
        "translation": {"x": 0.52, "y": 0.1, "width": 0.46, "height": 0.80},
    },
    "Traducere mică sub original": {
        "original":    {"x": 0.0, "y": 0.05, "width": 1.0, "height": 0.65},
        "translation": {"x": 0.05, "y": 0.73, "width": 0.90, "height": 0.22},
    },
    "Side by side": {
        "original":    {"x": 0.01, "y": 0.05, "width": 0.48, "height": 0.90},
        "translation": {"x": 0.51, "y": 0.05, "width": 0.48, "height": 0.90},
    },
}

_STYLE = """
QDialog, QWidget { background: #181818; color: #e0e0e0; font-family: 'Segoe UI'; }
QGroupBox {
    border: 1px solid #242424; border-radius: 5px;
    margin-top: 8px; padding: 10px 8px 8px 8px;
    color: #888; font-size: 10px;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; color: #5294e2; font-weight: 700; }
QLabel { color: #ccc; font-size: 12px; }
QPushButton {
    background: #232323; color: #e0e0e0; border: 1px solid #2c2c2c;
    border-radius: 5px; padding: 6px 14px;
}
QPushButton:hover { background: #2a2a2a; border-color: #3a3a3a; }
QSpinBox, QDoubleSpinBox, QComboBox {
    background: #1c1c1c; color: #e0e0e0; border: 1px solid #262626;
    border-radius: 4px; padding: 4px 6px;
}
"""


class _CanvasWidget(QWidget):
    """16:9 preview canvas with draggable original/translation zones."""

    zone_changed = pyqtSignal()

    def __init__(self, layout_data: dict, parent=None):
        super().__init__(parent)
        self.setMinimumSize(640, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._layout = layout_data
        self._dragging = None
        self._drag_offset = QPoint()
        self._selected = None
        self.setMouseTracking(True)

    def _canvas_rect(self) -> QRect:
        w, h = self.width(), self.height()
        asp = 16 / 9
        if w / h > asp:
            ch = h - 20
            cw = int(ch * asp)
        else:
            cw = w - 20
            ch = int(cw / asp)
        cx = (w - cw) // 2
        cy = (h - ch) // 2
        return QRect(cx, cy, cw, ch)

    def _zone_rect(self, zone_key: str) -> QRect:
        cr = self._canvas_rect()
        z = self._layout[zone_key]
        return QRect(
            cr.x() + int(z["x"] * cr.width()),
            cr.y() + int(z["y"] * cr.height()),
            int(z["width"] * cr.width()),
            int(z["height"] * cr.height()),
        )

    def _hit_test(self, pos: QPoint) -> str | None:
        for key in ("translation", "original"):
            if self._zone_rect(key).contains(pos):
                return key
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            key = self._hit_test(event.pos())
            if key:
                self._dragging = key
                self._selected = key
                zr = self._zone_rect(key)
                self._drag_offset = event.pos() - zr.topLeft()
                self.update()

    def mouseMoveEvent(self, event):
        if self._dragging:
            cr = self._canvas_rect()
            new_tl = event.pos() - self._drag_offset
            z = self._layout[self._dragging]
            nx = max(0.0, min(1.0 - z["width"], (new_tl.x() - cr.x()) / cr.width()))
            ny = max(0.0, min(1.0 - z["height"], (new_tl.y() - cr.y()) / cr.height()))
            z["x"] = round(nx, 3)
            z["y"] = round(ny, 3)
            self.update()
            self.zone_changed.emit()

    def mouseReleaseEvent(self, event):
        self._dragging = None

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cr = self._canvas_rect()

        # Black canvas background
        p.fillRect(cr, QColor("#000000"))
        p.setPen(QPen(QColor("#333"), 1))
        p.drawRect(cr)

        _zone_colors = {
            "original":    QColor(82, 148, 226, 80),
            "translation": QColor(76, 175, 80, 80),
        }
        _zone_border = {
            "original":    QColor(82, 148, 226),
            "translation": QColor(76, 175, 80),
        }
        _zone_labels = {
            "original":    "Original",
            "translation": "Traducere",
        }

        for key in ("original", "translation"):
            zr = self._zone_rect(key)
            p.fillRect(zr, _zone_colors[key])
            border_color = _zone_border[key]
            thickness = 2 if key == self._selected else 1
            p.setPen(QPen(border_color, thickness))
            p.drawRect(zr)

            p.setPen(QPen(QColor("#ffffff")))
            f = QFont("Segoe UI", 9, QFont.Weight.Bold)
            p.setFont(f)
            p.drawText(zr, Qt.AlignmentFlag.AlignCenter, _zone_labels[key])

        p.end()

    def apply_preset(self, preset: dict):
        for key in ("original", "translation"):
            if key in preset:
                self._layout[key].update(preset[key])
        self.update()
        self.zone_changed.emit()


class DualLayoutEditor(QDialog):
    """Dialog to configure the dual-language display layout."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📐 Editor afișare duală")
        self.setMinimumSize(900, 600)
        self.setStyleSheet(_STYLE)

        s = db.get_settings()
        saved = s.get("dual_language_layout")
        if saved and isinstance(saved, str):
            try:
                saved = json.loads(saved)
            except Exception:
                saved = None

        import copy
        self._layout = copy.deepcopy(saved or _DEFAULT_LAYOUT)
        for key in ("original", "translation"):
            if key not in self._layout:
                self._layout[key] = copy.deepcopy(_DEFAULT_LAYOUT[key])
            for k, v in _DEFAULT_LAYOUT[key].items():
                self._layout[key].setdefault(k, v)

        self._build_ui()

    def _build_ui(self):
        main = QHBoxLayout(self)
        main.setContentsMargins(10, 10, 10, 10)
        main.setSpacing(10)

        # ── Canvas ────────────────────────────────────────────────────────────
        left = QVBoxLayout()
        self._canvas = _CanvasWidget(self._layout)
        self._canvas.zone_changed.connect(self._sync_spinboxes)
        left.addWidget(self._canvas, 1)

        # Presets row
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))
        self._preset_combo = QComboBox()
        for name in _PRESETS:
            self._preset_combo.addItem(name)
        preset_row.addWidget(self._preset_combo, 1)
        apply_btn = QPushButton("Aplică")
        apply_btn.clicked.connect(self._apply_preset)
        preset_row.addWidget(apply_btn)
        left.addLayout(preset_row)

        main.addLayout(left, 1)

        # ── Settings panel ────────────────────────────────────────────────────
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setMaximumWidth(280)
        right_w = QWidget()
        right_l = QVBoxLayout(right_w)
        right_l.setSpacing(8)

        self._zone_widgets = {}
        for key, label in (("original", "Original"), ("translation", "Traducere")):
            grp = QGroupBox(label)
            form = QFormLayout(grp)
            form.setSpacing(6)

            widgets = {}

            x_sb = QDoubleSpinBox()
            x_sb.setRange(0.0, 1.0)
            x_sb.setSingleStep(0.01)
            x_sb.setDecimals(3)
            x_sb.setValue(self._layout[key]["x"])
            form.addRow("X:", x_sb)
            widgets["x"] = x_sb

            y_sb = QDoubleSpinBox()
            y_sb.setRange(0.0, 1.0)
            y_sb.setSingleStep(0.01)
            y_sb.setDecimals(3)
            y_sb.setValue(self._layout[key]["y"])
            form.addRow("Y:", y_sb)
            widgets["y"] = y_sb

            w_sb = QDoubleSpinBox()
            w_sb.setRange(0.01, 1.0)
            w_sb.setSingleStep(0.01)
            w_sb.setDecimals(3)
            w_sb.setValue(self._layout[key]["width"])
            form.addRow("Lățime:", w_sb)
            widgets["width"] = w_sb

            h_sb = QDoubleSpinBox()
            h_sb.setRange(0.01, 1.0)
            h_sb.setSingleStep(0.01)
            h_sb.setDecimals(3)
            h_sb.setValue(self._layout[key]["height"])
            form.addRow("Înălțime:", h_sb)
            widgets["height"] = h_sb

            fs_sb = QSpinBox()
            fs_sb.setRange(10, 200)
            fs_sb.setValue(self._layout[key]["font_size"])
            form.addRow("Font size:", fs_sb)
            widgets["font_size"] = fs_sb

            color_btn = QPushButton()
            color_btn.setFixedSize(48, 24)
            color_btn.setStyleSheet(
                f"background:{self._layout[key]['color']}; "
                "border:1px solid #555; border-radius:3px;"
            )
            color_btn.clicked.connect(
                lambda _, k=key, b=color_btn: self._pick_color(k, "color", b)
            )
            form.addRow("Culoare text:", color_btn)
            widgets["color_btn"] = color_btn

            align_cb = QComboBox()
            align_cb.addItems(["center", "left", "right"])
            align_cb.setCurrentText(self._layout[key].get("align", "center"))
            form.addRow("Aliniere:", align_cb)
            widgets["align"] = align_cb

            pad_sb = QSpinBox()
            pad_sb.setRange(0, 100)
            pad_sb.setValue(self._layout[key].get("padding", 16))
            form.addRow("Padding:", pad_sb)
            widgets["padding"] = pad_sb

            for field, sb in (("x", x_sb), ("y", y_sb),
                               ("width", w_sb), ("height", h_sb)):
                sb.valueChanged.connect(
                    lambda val, k=key, f=field: self._on_spinbox_changed(k, f, val)
                )

            right_l.addWidget(grp)
            self._zone_widgets[key] = widgets

        right_l.addStretch()
        right_scroll.setWidget(right_w)
        main.addWidget(right_scroll)

        # ── Bottom buttons ────────────────────────────────────────────────────
        btn_layout = QVBoxLayout()
        save_btn = QPushButton("💾 Salvează layout")
        save_btn.setStyleSheet(
            "QPushButton { background: #18283a; color: #5294e2; "
            "border: 1px solid #1c3a5a; border-radius: 5px; padding: 8px 18px; }"
            "QPushButton:hover { background: #1c3a5a; }"
        )
        save_btn.clicked.connect(self._save_layout)

        close_btn = QPushButton("Închide")
        close_btn.clicked.connect(self.accept)

        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        main.addLayout(btn_layout)

    def _pick_color(self, zone_key: str, field: str, btn: QPushButton):
        current = self._layout[zone_key].get(field, "#ffffff")
        c = QColorDialog.getColor(QColor(current), self, "Culoare text")
        if c.isValid():
            self._layout[zone_key][field] = c.name()
            btn.setStyleSheet(
                f"background:{c.name()}; border:1px solid #555; border-radius:3px;"
            )

    def _on_spinbox_changed(self, zone_key: str, field: str, val):
        self._layout[zone_key][field] = val
        self._canvas.update()

    def _sync_spinboxes(self):
        for key, widgets in self._zone_widgets.items():
            z = self._layout[key]
            for field in ("x", "y", "width", "height"):
                sb = widgets.get(field)
                if sb:
                    sb.blockSignals(True)
                    sb.setValue(z[field])
                    sb.blockSignals(False)

    def _apply_preset(self):
        name = self._preset_combo.currentText()
        preset = _PRESETS.get(name, {})
        self._canvas.apply_preset(preset)
        self._sync_spinboxes()

    def _save_layout(self):
        # Collect remaining fields from widgets
        for key, widgets in self._zone_widgets.items():
            z = self._layout[key]
            z["font_size"] = widgets["font_size"].value()
            z["align"] = widgets["align"].currentText()
            z["padding"] = widgets["padding"].value()

        s = db.get_settings()
        s["dual_language_layout"] = json.dumps(self._layout, ensure_ascii=False)
        db.save_settings(s)
        self.accept()

    def get_layout(self) -> dict:
        return self._layout
