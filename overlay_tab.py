"""
Cantio - Overlay Tab
Live overlay system: text, image, shape, ticker, countdown, clock, logo.
Each overlay is an OverlayItem that can be shown/hidden independently
on the Electron display.
"""
from __future__ import annotations

import uuid
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QStackedWidget, QFormLayout, QGroupBox,
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox,
    QColorDialog, QFileDialog, QMenu, QFrame, QScrollArea,
    QSizePolicy, QTextEdit, QMainWindow, QSplitter,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRect, QPoint, QRectF
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QBrush, QPainterPath, QPixmap
from translations import t

# ── Overlay types ─────────────────────────────────────────────────────────────

OVERLAY_TYPES = ["text", "image", "shape", "ticker", "countdown", "clock", "logo"]

OVERLAY_TYPE_ICONS = {
    "text":      "T",
    "image":     "🖼",
    "shape":     "◆",
    "ticker":    "📜",
    "countdown": "⏱",
    "clock":     "🕐",
    "logo":      "⭐",
}

_STYLE = """
QWidget { background: #181818; color: #e0e0e0; font-family: 'Segoe UI'; font-size: 12px; }
QListWidget {
    background: #141414; border: none; outline: none;
    padding: 2px 0;
}
QListWidget::item {
    padding: 8px 10px; border-radius: 4px; margin: 1px 4px;
}
QListWidget::item:hover  { background: #1e1e1e; }
QListWidget::item:selected { background: #1c3a5a; color: #e0e0e0; }
QPushButton {
    background: #232323; color: #e0e0e0;
    border: 1px solid #2c2c2c; border-radius: 5px;
    padding: 6px 12px; font-size: 11px;
}
QPushButton:hover { background: #2a2a2a; border-color: #3a3a3a; }
QPushButton:pressed { background: #1a1a1a; }
QGroupBox {
    border: 1px solid #222; border-radius: 5px;
    margin-top: 6px; padding: 10px 8px 8px 8px;
    color: #555; font-size: 10px; font-weight: 700; letter-spacing: 1px;
}
QGroupBox::title { subcontrol-origin: margin; left: 8px; color: #5294e2; }
QLabel { color: #ccc; }
QLineEdit, QTextEdit {
    background: #1c1c1c; color: #e0e0e0;
    border: 1px solid #262626; border-radius: 4px; padding: 5px 8px;
}
QLineEdit:focus, QTextEdit:focus { border-color: #5294e2; }
QComboBox, QSpinBox, QDoubleSpinBox {
    background: #1c1c1c; color: #e0e0e0;
    border: 1px solid #262626; border-radius: 4px; padding: 4px 8px;
}
QComboBox QAbstractItemView {
    background: #222; color: #e0e0e0;
    border: 1px solid #2e2e2e; selection-background-color: #1c3a5a;
}
QCheckBox { color: #e0e0e0; spacing: 6px; }
QCheckBox::indicator {
    width: 15px; height: 15px; border: 1px solid #333;
    border-radius: 3px; background: #1c1c1c;
}
QCheckBox::indicator:checked { background: #5294e2; border-color: #5294e2; }
"""


# ── OverlayItem ───────────────────────────────────────────────────────────────

class OverlayItem:
    """Data model for a single overlay element."""

    def __init__(
        self,
        name:     str  = "Overlay",
        otype:    str  = "text",
        visible:  bool = True,
        x: int = 0,   y: int = 0,
        width: int = 400, height: int = 100,
        z_index: int = 0,
        settings: Optional[dict] = None,
    ):
        self.id       = str(uuid.uuid4())[:8]
        self.name     = name
        self.type     = otype
        self.visible  = visible
        self.x        = x
        self.y        = y
        self.width    = width
        self.height   = height
        self.z_index  = z_index
        self.settings: dict = settings or {}

    def to_dict(self) -> dict:
        return {
            "id":       self.id,
            "name":     self.name,
            "type":     self.type,
            "visible":  self.visible,
            "x":        self.x,
            "y":        self.y,
            "width":    self.width,
            "height":   self.height,
            "z_index":  self.z_index,
            "settings": self.settings,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "OverlayItem":
        o = cls(
            name     = d.get("name",    "Overlay"),
            otype    = d.get("type",    "text"),
            visible  = d.get("visible", True),
            x        = d.get("x",       0),
            y        = d.get("y",       0),
            width    = d.get("width",   400),
            height   = d.get("height",  100),
            z_index  = d.get("z_index", 0),
            settings = d.get("settings", {}),
        )
        o.id = d.get("id", o.id)
        return o


# ── OverlayTab ────────────────────────────────────────────────────────────────

class OverlayTab(QWidget):
    """
    Full overlay management panel.
    Left: list of overlays with show/hide/add/delete controls.
    Right: type-specific editor (stacked).
    """

    overlay_updated = pyqtSignal(dict)   # emits overlay.to_dict() on change

    def __init__(self, parent_control=None, parent=None):
        super().__init__(parent)
        self._control   = parent_control
        self._overlays: list[OverlayItem] = []
        self._current:  Optional[OverlayItem] = None
        self.setStyleSheet(_STYLE)
        self._build_ui()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left panel ────────────────────────────────────────────────────────
        left = QFrame()
        left.setFixedWidth(220)
        left.setStyleSheet("QFrame { background: #131313; border-right: 1px solid #1e1e1e; }")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(6, 6, 6, 6)
        ll.setSpacing(4)

        hdr = QLabel(t("overlays").upper())
        hdr.setStyleSheet(
            "color: #5294e2; font-size: 10px; font-weight: 700; letter-spacing: 2px;"
            " padding: 2px 4px;"
        )
        ll.addWidget(hdr)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_list_select)
        ll.addWidget(self._list, 1)

        # Visibility buttons
        vis_row = QHBoxLayout()
        show_btn = QPushButton(f"👁 {t('show')}")
        show_btn.clicked.connect(self._show_selected)
        hide_btn = QPushButton(f"🙈 {t('hide')}")
        hide_btn.clicked.connect(self._hide_selected)
        for b in (show_btn, hide_btn):
            b.setStyleSheet(
                "QPushButton { padding: 5px 8px; font-size: 10px; }"
            )
            vis_row.addWidget(b)
        ll.addLayout(vis_row)

        # Add / Delete
        add_btn = QPushButton(t("add_overlay"))
        add_btn.setStyleSheet(
            "QPushButton { background: #18283a; color: #5294e2; border: 1px solid #1c3a5a; "
            "border-radius: 5px; padding: 7px 10px; font-size: 11px; }"
            "QPushButton:hover { background: #1c3a5a; color: #e0e0e0; }"
        )
        add_btn.clicked.connect(self._show_add_menu)
        ll.addWidget(add_btn)

        del_btn = QPushButton(f"🗑 {t('delete')}")
        del_btn.setStyleSheet(
            "QPushButton { color: #f44336; border-color: #2e1a1a; }"
            "QPushButton:hover { background: #251a1a; border-color: #f44336; }"
        )
        del_btn.clicked.connect(self._delete_selected)
        ll.addWidget(del_btn)

        edit_btn = QPushButton(f"🖌 {t('visual_editor')}")
        edit_btn.setStyleSheet(
            "QPushButton { background: #2a1a3a; color: #cba6f7; "
            "border: 1px solid #4a2a6a; border-radius: 5px; padding: 7px; }"
            "QPushButton:hover { background: #3a1a5a; color: #e0e0e0; }"
        )
        edit_btn.clicked.connect(self._open_visual_editor)
        ll.addWidget(edit_btn)

        root.addWidget(left)

        # ── Right panel (stacked editors) ─────────────────────────────────────
        right = QScrollArea()
        right.setWidgetResizable(True)
        right.setStyleSheet("QScrollArea { border: none; background: #181818; }")

        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: #181818;")

        # Placeholder
        self._placeholder = QLabel(t("select_overlay"))
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: #444; font-size: 12px;")
        self._stack.addWidget(self._placeholder)

        # Type editors — built lazily, indexed by type name
        self._editors: dict[str, QWidget] = {}
        for otype in OVERLAY_TYPES:
            editor = self._build_editor(otype)
            self._editors[otype] = editor
            self._stack.addWidget(editor)

        right.setWidget(self._stack)
        root.addWidget(right, 1)

    # ── Overlay list management ───────────────────────────────────────────────

    def _refresh_list(self):
        self._list.clear()
        for ov in self._overlays:
            icon  = OVERLAY_TYPE_ICONS.get(ov.type, "?")
            eye   = "👁" if ov.visible else "🙈"
            label = f"{eye}  {icon}  {ov.name}"
            item  = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, ov.id)
            self._list.addItem(item)

    def _on_list_select(self, row: int):
        if row < 0 or row >= len(self._overlays):
            self._stack.setCurrentWidget(self._placeholder)
            self._current = None
            return
        ov = self._overlays[row]
        self._current = ov
        self._load_editor(ov)
        editor = self._editors.get(ov.type, self._placeholder)
        self._stack.setCurrentWidget(editor)

    def _show_add_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #1e1e1e; color: #e0e0e0; border: 1px solid #333; padding: 2px; }"
            "QMenu::item { padding: 7px 20px; border-radius: 3px; }"
            "QMenu::item:selected { background: #1c3a5a; }"
        )
        for otype in OVERLAY_TYPES:
            icon  = OVERLAY_TYPE_ICONS.get(otype, "?")
            menu.addAction(f"{icon}  {otype.capitalize()}",
                           lambda checked=False, t=otype: self._add_overlay(t))
        menu.exec(self.mapToGlobal(self.sender().pos()))  # type: ignore[union-attr]

    def _add_overlay(self, otype: str):
        defaults = {
            "ticker":    {"ticker_in_effect": "slide_up",
                          "ticker_out_effect": "slide_down",
                          "ticker_speed": 80, "ticker_color": "#ffdd44"},
            "countdown": {"seconds": 60},
            "clock":     {"format": "HH:MM"},
            "text":      {"text": "Text overlay", "font_size": 48,
                          "color": "#ffffff"},
            "image":     {"path": ""},
            "shape":     {"shape": "rect", "color": "#5294e2", "opacity": 0.8},
            "logo":      {"path": ""},
        }
        ov = OverlayItem(
            name     = f"{otype.capitalize()} {len(self._overlays) + 1}",
            otype    = otype,
            settings = defaults.get(otype, {}),
        )
        self._overlays.append(ov)
        self._refresh_list()
        self._list.setCurrentRow(len(self._overlays) - 1)

    def _delete_selected(self):
        row = self._list.currentRow()
        if row < 0 or row >= len(self._overlays):
            return
        ov = self._overlays.pop(row)
        # Send hide command to display
        self._send_hide(ov)
        self._refresh_list()
        self._stack.setCurrentWidget(self._placeholder)
        self._current = None

    def _show_selected(self):
        if not self._current:
            return
        self._current.visible = True
        self._refresh_list()
        self._send_to_display(self._current)

    def _hide_selected(self):
        if not self._current:
            return
        self._current.visible = False
        self._refresh_list()
        self._send_hide(self._current)

    # ── Editors ───────────────────────────────────────────────────────────────

    def _build_editor(self, otype: str) -> QWidget:
        if otype == "text":    return self._editor_text()
        if otype == "image":   return self._editor_image()
        if otype == "shape":   return self._editor_shape()
        if otype == "ticker":  return self._editor_ticker()
        if otype == "countdown": return self._editor_countdown()
        if otype == "clock":   return self._editor_clock()
        if otype == "logo":    return self._editor_logo()
        return QLabel(f"{otype} editor")

    def _editor_wrap(self, title: str, inner: QWidget) -> QWidget:
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(12, 12, 12, 12)
        vl.setSpacing(10)
        hdr = QLabel(title)
        hdr.setStyleSheet(
            "color: #5294e2; font-size: 11px; font-weight: 700; letter-spacing: 2px;"
        )
        vl.addWidget(hdr)
        vl.addWidget(inner)

        # Common: position/size
        pos_grp = QGroupBox("POZIȚIE ȘI DIMENSIUNE")
        pf = QFormLayout(pos_grp)
        for attr, lbl in [("_e_x", "X:"), ("_e_y", "Y:"),
                           ("_e_w", "Lățime:"), ("_e_h", "Înălțime:"),
                           ("_e_z", "Z-index:")]:
            sb = QSpinBox()
            sb.setRange(-9999, 9999)
            setattr(w, attr, sb)
            pf.addRow(lbl, sb)
        vl.addWidget(pos_grp)

        # Send live button
        send_btn = QPushButton(t("send_live"))
        send_btn.setStyleSheet(
            "QPushButton { background: #1c3a1c; color: #4caf50; "
            "border: 1px solid #2a5a2a; border-radius: 5px; "
            "padding: 8px 14px; font-weight: 600; }"
            "QPushButton:hover { background: #2a4a2a; }"
        )
        send_btn.clicked.connect(self._on_send_live)
        vl.addWidget(send_btn)
        vl.addStretch()
        return w

    def _editor_text(self) -> QWidget:
        inner = QWidget()
        f = QFormLayout(inner)
        self._te_text = QTextEdit()
        self._te_text.setFixedHeight(80)
        f.addRow("Text:", self._te_text)
        self._te_font_size = QSpinBox()
        self._te_font_size.setRange(8, 200)
        self._te_font_size.setValue(48)
        f.addRow("Mărime:", self._te_font_size)
        self._te_color_btn = QPushButton("#ffffff")
        self._te_color_btn.setStyleSheet("background: #ffffff; color: #000;")
        self._te_color_btn.clicked.connect(
            lambda: self._pick_color(self._te_color_btn))
        f.addRow("Culoare:", self._te_color_btn)
        return self._editor_wrap("TEXT OVERLAY", inner)

    def _editor_image(self) -> QWidget:
        inner = QWidget()
        f = QFormLayout(inner)
        path_row = QHBoxLayout()
        self._img_path = QLineEdit()
        self._img_path.setPlaceholderText("Calea imaginii…")
        browse = QPushButton("Browse…")
        browse.setFixedWidth(70)
        browse.clicked.connect(lambda: self._pick_file(self._img_path))
        path_row.addWidget(self._img_path, 1)
        path_row.addWidget(browse)
        f.addRow("Imagine:", path_row)
        self._img_opacity = QDoubleSpinBox()
        self._img_opacity.setRange(0.0, 1.0)
        self._img_opacity.setSingleStep(0.05)
        self._img_opacity.setValue(1.0)
        f.addRow("Opacitate:", self._img_opacity)
        return self._editor_wrap("IMAGE OVERLAY", inner)

    def _editor_shape(self) -> QWidget:
        inner = QWidget()
        f = QFormLayout(inner)
        self._sh_type = QComboBox()
        self._sh_type.addItems(["rect", "circle", "triangle", "line"])
        f.addRow("Formă:", self._sh_type)
        self._sh_color_btn = QPushButton("#5294e2")
        self._sh_color_btn.setStyleSheet("background: #5294e2; color: #fff;")
        self._sh_color_btn.clicked.connect(
            lambda: self._pick_color(self._sh_color_btn))
        f.addRow("Culoare:", self._sh_color_btn)
        self._sh_opacity = QDoubleSpinBox()
        self._sh_opacity.setRange(0.0, 1.0)
        self._sh_opacity.setValue(0.8)
        self._sh_opacity.setSingleStep(0.05)
        f.addRow("Opacitate:", self._sh_opacity)
        return self._editor_wrap("SHAPE OVERLAY", inner)

    def _editor_ticker(self) -> QWidget:
        inner = QWidget()
        f = QFormLayout(inner)
        self._tick_text = QLineEdit()
        self._tick_text.setPlaceholderText("Textul tickerului…")
        f.addRow("Text:", self._tick_text)
        self._tick_speed = QSpinBox()
        self._tick_speed.setRange(10, 500)
        self._tick_speed.setValue(80)
        self._tick_speed.setSuffix(" px/s")
        f.addRow("Viteză:", self._tick_speed)
        self._tick_color_btn = QPushButton("#ffdd44")
        self._tick_color_btn.setStyleSheet("background: #ffdd44; color: #111;")
        self._tick_color_btn.clicked.connect(
            lambda: self._pick_color(self._tick_color_btn))
        f.addRow("Culoare text:", self._tick_color_btn)
        self._tick_in_effect = QComboBox()
        self._tick_in_effect.addItems(["slide_up", "fade", "instant"])
        f.addRow("Efect intrare:", self._tick_in_effect)
        self._tick_out_effect = QComboBox()
        self._tick_out_effect.addItems(["slide_down", "fade", "instant"])
        f.addRow("Efect ieșire:", self._tick_out_effect)
        self._tick_duration = QSpinBox()
        self._tick_duration.setRange(100, 2000)
        self._tick_duration.setValue(400)
        self._tick_duration.setSuffix(" ms")
        f.addRow("Durată efect:", self._tick_duration)
        # Stop ticker button
        stop_tick_btn = QPushButton("⏹ Oprește ticker")
        stop_tick_btn.clicked.connect(self._stop_ticker)
        f.addRow("", stop_tick_btn)
        return self._editor_wrap("TICKER OVERLAY", inner)

    def _editor_countdown(self) -> QWidget:
        inner = QWidget()
        f = QFormLayout(inner)
        self._cd_seconds = QSpinBox()
        self._cd_seconds.setRange(1, 86400)
        self._cd_seconds.setValue(60)
        self._cd_seconds.setSuffix(" s")
        f.addRow("Durată:", self._cd_seconds)
        self._cd_color_btn = QPushButton("#ffffff")
        self._cd_color_btn.setStyleSheet("background: #ffffff; color: #000;")
        self._cd_color_btn.clicked.connect(
            lambda: self._pick_color(self._cd_color_btn))
        f.addRow("Culoare:", self._cd_color_btn)
        stop_cd_btn = QPushButton("⏹ Oprește numărătoarea")
        stop_cd_btn.clicked.connect(self._stop_countdown)
        f.addRow("", stop_cd_btn)
        return self._editor_wrap("COUNTDOWN OVERLAY", inner)

    def _editor_clock(self) -> QWidget:
        inner = QWidget()
        f = QFormLayout(inner)
        self._cl_format = QComboBox()
        self._cl_format.addItems(["HH:MM", "HH:MM:SS", "12h"])
        f.addRow("Format:", self._cl_format)
        self._cl_active = QCheckBox("Afișează ceasul")
        self._cl_active.setChecked(True)
        f.addRow("", self._cl_active)
        return self._editor_wrap("CLOCK OVERLAY", inner)

    def _editor_logo(self) -> QWidget:
        inner = QWidget()
        f = QFormLayout(inner)
        logo_row = QHBoxLayout()
        self._logo_path = QLineEdit()
        self._logo_path.setPlaceholderText("Calea logo-ului…")
        browse = QPushButton("Browse…")
        browse.setFixedWidth(70)
        browse.clicked.connect(lambda: self._pick_file(self._logo_path))
        logo_row.addWidget(self._logo_path, 1)
        logo_row.addWidget(browse)
        f.addRow("Logo:", logo_row)
        clear_logo_btn = QPushButton("Șterge logo")
        clear_logo_btn.clicked.connect(self._clear_logo)
        f.addRow("", clear_logo_btn)
        return self._editor_wrap("LOGO OVERLAY", inner)

    # ── Load editor from OverlayItem ──────────────────────────────────────────

    def _load_editor(self, ov: OverlayItem):
        s = ov.settings
        try:
            editor = self._editors.get(ov.type)
            if editor is None:
                return
            if ov.type == "text":
                self._te_text.setPlainText(s.get("text", ""))
                self._te_font_size.setValue(int(s.get("font_size", 48)))
                self._te_color_btn.setText(s.get("color", "#ffffff"))
                self._te_color_btn.setStyleSheet(
                    f"background: {s.get('color', '#ffffff')}; "
                    f"color: {'#000' if self._is_light(s.get('color', '#ffffff')) else '#fff'};")
            elif ov.type == "ticker":
                self._tick_text.setText(s.get("text", ""))
                self._tick_speed.setValue(int(s.get("ticker_speed", 80)))
                ie = self._tick_in_effect.findText(s.get("ticker_in_effect", "slide_up"))
                if ie >= 0: self._tick_in_effect.setCurrentIndex(ie)
                oe = self._tick_out_effect.findText(s.get("ticker_out_effect", "slide_down"))
                if oe >= 0: self._tick_out_effect.setCurrentIndex(oe)
                self._tick_duration.setValue(int(s.get("ticker_duration", 400)))
            elif ov.type == "countdown":
                self._cd_seconds.setValue(int(s.get("seconds", 60)))
            elif ov.type == "image":
                self._img_path.setText(s.get("path", ""))
                self._img_opacity.setValue(float(s.get("opacity", 1.0)))
            elif ov.type == "logo":
                self._logo_path.setText(s.get("path", ""))
            elif ov.type == "shape":
                si = self._sh_type.findText(s.get("shape", "rect"))
                if si >= 0: self._sh_type.setCurrentIndex(si)
                self._sh_opacity.setValue(float(s.get("opacity", 0.8)))
            # Position/size
            editor._e_x.setValue(ov.x)
            editor._e_y.setValue(ov.y)
            editor._e_w.setValue(ov.width)
            editor._e_h.setValue(ov.height)
            editor._e_z.setValue(ov.z_index)
        except Exception:
            pass

    # ── Collect settings from editor ──────────────────────────────────────────

    def _collect_from_editor(self, ov: OverlayItem):
        try:
            editor = self._editors.get(ov.type)
            if editor is None:
                return
            ov.x        = editor._e_x.value()
            ov.y        = editor._e_y.value()
            ov.width    = editor._e_w.value()
            ov.height   = editor._e_h.value()
            ov.z_index  = editor._e_z.value()

            if ov.type == "text":
                ov.settings["text"]      = self._te_text.toPlainText()
                ov.settings["font_size"] = self._te_font_size.value()
                ov.settings["color"]     = self._te_color_btn.text()
            elif ov.type == "ticker":
                ov.settings["text"]               = self._tick_text.text()
                ov.settings["ticker_speed"]       = self._tick_speed.value()
                ov.settings["ticker_in_effect"]   = self._tick_in_effect.currentText()
                ov.settings["ticker_out_effect"]  = self._tick_out_effect.currentText()
                ov.settings["ticker_duration"]    = self._tick_duration.value()
            elif ov.type == "countdown":
                ov.settings["seconds"] = self._cd_seconds.value()
            elif ov.type == "image":
                ov.settings["path"]    = self._img_path.text()
                ov.settings["opacity"] = self._img_opacity.value()
            elif ov.type == "logo":
                ov.settings["path"] = self._logo_path.text()
            elif ov.type == "shape":
                ov.settings["shape"]   = self._sh_type.currentText()
                ov.settings["opacity"] = self._sh_opacity.value()
        except Exception:
            pass

    # ── Send to display ───────────────────────────────────────────────────────

    def _on_send_live(self):
        if not self._current:
            return
        self._collect_from_editor(self._current)
        self._current.visible = True
        self._refresh_list()
        self._send_to_display(self._current)

    def _send_to_display(self, ov: OverlayItem):
        if not self._control:
            return
        dws = getattr(self._control, "display_windows", [])
        s   = ov.settings

        for dw in dws:
            if ov.type == "ticker":
                if hasattr(dw, "show_ticker_advanced"):
                    dw.show_ticker_advanced(
                        text     = s.get("text", ""),
                        settings = {
                            "ticker_in_effect": s.get("ticker_in_effect", "slide_up"),
                            "ticker_out_effect": s.get("ticker_out_effect", "slide_down"),
                            "ticker_speed":     s.get("ticker_speed", 80),
                            "ticker_duration":  s.get("ticker_duration", 400),
                        },
                    )
                elif hasattr(dw, "set_ticker"):
                    dw.set_ticker(s.get("text", ""))

            elif ov.type == "clock":
                if hasattr(dw, "toggle_clock"):
                    dw.toggle_clock(self._cl_active.isChecked())

            elif ov.type == "countdown":
                if hasattr(dw, "start_countdown"):
                    dw.start_countdown(
                        seconds = s.get("seconds", 60),
                        color   = s.get("color"),
                    )

            elif ov.type == "logo":
                path = s.get("path", "")
                if path and hasattr(dw, "show_logo"):
                    dw.show_logo(QPixmap(path))

    def _send_hide(self, ov: OverlayItem):
        if not self._control:
            return
        dws = getattr(self._control, "display_windows", [])
        for dw in dws:
            if ov.type == "ticker":
                s = ov.settings
                if hasattr(dw, "hide_ticker_with_effect"):
                    dw.hide_ticker_with_effect({
                        "ticker_out_effect": s.get("ticker_out_effect", "slide_down"),
                        "ticker_duration":   s.get("ticker_duration", 400),
                    })
                elif hasattr(dw, "clear_ticker"):
                    dw.clear_ticker()
            elif ov.type == "clock":
                if hasattr(dw, "toggle_clock"):
                    dw.toggle_clock(False)
            elif ov.type == "countdown":
                if hasattr(dw, "stop_countdown"):
                    dw.stop_countdown()
            elif ov.type == "logo":
                if hasattr(dw, "hide_logo"):
                    dw.hide_logo()

    def _stop_ticker(self):
        if not self._control:
            return
        for dw in getattr(self._control, "display_windows", []):
            if hasattr(dw, "hide_ticker_with_effect"):
                dw.hide_ticker_with_effect({"ticker_out_effect": "slide_down"})
            elif hasattr(dw, "clear_ticker"):
                dw.clear_ticker()

    def _stop_countdown(self):
        if not self._control:
            return
        for dw in getattr(self._control, "display_windows", []):
            if hasattr(dw, "stop_countdown"):
                dw.stop_countdown()

    def _clear_logo(self):
        if not self._control:
            return
        for dw in getattr(self._control, "display_windows", []):
            if hasattr(dw, "hide_logo"):
                dw.hide_logo()
        self._logo_path.clear()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _pick_color(self, btn: QPushButton):
        cur = QColor(btn.text()) if QColor(btn.text()).isValid() else QColor("#ffffff")
        c   = QColorDialog.getColor(cur, self, "Alege culoarea")
        if c.isValid():
            btn.setText(c.name())
            light = self._is_light(c.name())
            btn.setStyleSheet(
                f"background: {c.name()}; color: {'#000' if light else '#fff'};"
            )

    @staticmethod
    def _is_light(hex_color: str) -> bool:
        try:
            c = QColor(hex_color)
            return (c.red() * 299 + c.green() * 587 + c.blue() * 114) / 1000 > 128
        except Exception:
            return False

    def _pick_file(self, line_edit: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selectează fișier", "",
            "Imagini (*.png *.jpg *.jpeg *.webp *.svg);;Toate fișierele (*)"
        )
        if path:
            line_edit.setText(path)

    def _open_visual_editor(self):
        """Open the full-screen visual overlay editor window."""
        editor = OverlayEditorWindow(
            overlays     = self._overlays,
            parent_tab   = self,
            parent       = self,
        )
        editor.overlays_changed.connect(self._on_editor_overlays_changed)
        editor.show()
        editor.raise_()

    def _on_editor_overlays_changed(self, overlays: list):
        self._overlays = overlays
        self._refresh_list()


# ── OverlayCanvas ─────────────────────────────────────────────────────────────

class OverlayCanvas(QWidget):
    """
    16:9 canvas widget. Renders all OverlayItems and allows:
    - Click to select
    - Drag to reposition
    - Visual bounding-box with resize handles
    """

    item_selected  = pyqtSignal(object)   # OverlayItem or None
    item_moved     = pyqtSignal(object)   # OverlayItem after move

    _HANDLE_SIZE   = 8
    _CANVAS_COLOR  = QColor("#0d0d0d")
    _SELECT_COLOR  = QColor("#5294e2")
    _HOVER_COLOR   = QColor("#5294e240")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._overlays: list[OverlayItem] = []
        self._selected: Optional[OverlayItem] = None
        self._drag_start: Optional[QPoint] = None
        self._drag_item_origin: tuple[int, int] = (0, 0)
        self.setMouseTracking(True)
        self.setMinimumSize(640, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_overlays(self, overlays: list[OverlayItem]):
        self._overlays = overlays
        self.update()

    def select_item(self, item: Optional[OverlayItem]):
        self._selected = item
        self.update()

    # ── Canvas geometry ───────────────────────────────────────────────────────

    def _canvas_rect(self) -> QRect:
        """16:9 rect centred in the widget."""
        w, h = self.width(), self.height()
        if w / h > 16 / 9:
            ch = h
            cw = int(ch * 16 / 9)
        else:
            cw = w
            ch = int(cw * 9 / 16)
        cx = (w - cw) // 2
        cy = (h - ch) // 2
        return QRect(cx, cy, cw, ch)

    def _to_canvas(self, x: int, y: int) -> tuple[float, float]:
        """Convert OverlayItem coords (1920×1080 space) to widget pixels."""
        cr = self._canvas_rect()
        return (cr.x() + x * cr.width() / 1920,
                cr.y() + y * cr.height() / 1080)

    def _to_item_space(self, px: int, py: int) -> tuple[int, int]:
        """Convert widget-pixel click to 1920×1080 design space."""
        cr = self._canvas_rect()
        if cr.width() == 0 or cr.height() == 0:
            return 0, 0
        return (int((px - cr.x()) * 1920 / cr.width()),
                int((py - cr.y()) * 1080 / cr.height()))

    def _item_rect_px(self, item: OverlayItem) -> QRect:
        """Bounding rect of an item in widget pixels."""
        cr  = self._canvas_rect()
        sx  = cr.width()  / 1920
        sy  = cr.height() / 1080
        x   = cr.x() + int(item.x * sx)
        y   = cr.y() + int(item.y * sy)
        w   = max(4, int(item.width  * sx))
        h   = max(4, int(item.height * sy))
        return QRect(x, y, w, h)

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        p.fillRect(self.rect(), QColor("#111111"))

        cr = self._canvas_rect()
        # Canvas area
        p.fillRect(cr, self._CANVAS_COLOR)
        # Canvas border
        p.setPen(QPen(QColor("#2e2e2e"), 1))
        p.drawRect(cr)

        # Grid lines (light)
        p.setPen(QPen(QColor("#1a1a1a"), 1))
        cols, rows = 8, 4
        for i in range(1, cols):
            gx = cr.x() + cr.width() * i // cols
            p.drawLine(gx, cr.y(), gx, cr.y() + cr.height())
        for i in range(1, rows):
            gy = cr.y() + cr.height() * i // rows
            p.drawLine(cr.x(), gy, cr.x() + cr.width(), gy)

        # Items
        for item in self._overlays:
            if not item.visible:
                p.setOpacity(0.3)
            else:
                p.setOpacity(1.0)
            r = self._item_rect_px(item)
            self._draw_item(p, item, r)

        p.setOpacity(1.0)

        # Selection overlay
        if self._selected:
            r = self._item_rect_px(self._selected)
            p.setPen(QPen(self._SELECT_COLOR, 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r)
            # Corner handles
            hs = self._HANDLE_SIZE
            for hx, hy in [
                (r.left(), r.top()), (r.right(), r.top()),
                (r.left(), r.bottom()), (r.right(), r.bottom()),
            ]:
                p.fillRect(QRect(hx - hs//2, hy - hs//2, hs, hs), self._SELECT_COLOR)

    def _draw_item(self, p: QPainter, item: OverlayItem, r: QRect):
        """Draw a simplified representation of the overlay item."""
        type_colors = {
            "text":      ("#1a3a5c", "#5294e2"),
            "image":     ("#1a3d1a", "#52c27a"),
            "shape":     ("#3d1a3d", "#c252e2"),
            "ticker":    ("#3d3a1a", "#e2c252"),
            "countdown": ("#3d1a1a", "#e25252"),
            "clock":     ("#1a2a3d", "#52a2e2"),
            "logo":      ("#2a2a1a", "#c2e252"),
        }
        bg_hex, border_hex = type_colors.get(item.type, ("#1a1a1a", "#444"))
        bg     = QColor(bg_hex)
        bg.setAlphaF(0.8)
        border = QColor(border_hex)

        path = QPainterPath()
        path.addRoundedRect(QRectF(r), 4, 4)
        p.fillPath(path, QBrush(bg))
        p.setPen(QPen(border, 1))
        p.drawPath(path)

        # Icon + name label
        icon  = OVERLAY_TYPE_ICONS.get(item.type, "?")
        label = f"{icon} {item.name}"
        p.setPen(QPen(QColor(border_hex)))
        font  = QFont("Segoe UI")
        font.setPixelSize(max(7, min(12, r.height() // 3)))
        p.setFont(font)
        p.drawText(r.adjusted(4, 4, -4, -4), Qt.AlignmentFlag.AlignTop, label)

    # ── Mouse interaction ─────────────────────────────────────────────────────

    def mousePressEvent(self, ev):
        if ev.button() != Qt.MouseButton.LeftButton:
            return
        pos = ev.position().toPoint() if hasattr(ev, 'position') else ev.pos()
        hit = self._hit_test(pos.x(), pos.y())
        self._selected = hit
        if hit:
            self._drag_start = pos
            self._drag_item_origin = (hit.x, hit.y)
        self.item_selected.emit(hit)
        self.update()

    def mouseMoveEvent(self, ev):
        if self._drag_start is None or self._selected is None:
            return
        pos = ev.position().toPoint() if hasattr(ev, 'position') else ev.pos()
        dx  = pos.x() - self._drag_start.x()
        dy  = pos.y() - self._drag_start.y()
        cr  = self._canvas_rect()
        if cr.width() == 0 or cr.height() == 0:
            return
        item_dx = int(dx * 1920 / cr.width())
        item_dy = int(dy * 1080 / cr.height())
        self._selected.x = max(0, min(1920, self._drag_item_origin[0] + item_dx))
        self._selected.y = max(0, min(1080, self._drag_item_origin[1] + item_dy))
        self.item_moved.emit(self._selected)
        self.update()

    def mouseReleaseEvent(self, _ev):
        self._drag_start = None

    def _hit_test(self, px: int, py: int) -> Optional[OverlayItem]:
        """Return the topmost item under (px, py), or None."""
        for item in reversed(self._overlays):
            if self._item_rect_px(item).contains(QPoint(px, py)):
                return item
        return None


# ── OverlayEditorWindow ───────────────────────────────────────────────────────

class OverlayEditorWindow(QMainWindow):
    """
    Full visual overlay editor.
    Left panel  : element list + add / delete buttons
    Centre      : OverlayCanvas (drag-to-position)
    Right panel : live property editor for the selected element
    """

    overlays_changed = pyqtSignal(list)   # emits list[OverlayItem]

    _STYLE = """
    QMainWindow, QWidget { background: #181818; color: #e0e0e0;
        font-family: 'Segoe UI'; font-size: 12px; }
    QListWidget { background: #131313; border: none; }
    QListWidget::item { padding: 8px 10px; border-radius: 4px; margin: 1px 4px; }
    QListWidget::item:hover    { background: #1e1e1e; }
    QListWidget::item:selected { background: #1c3a5a; }
    QPushButton {
        background: #232323; color: #e0e0e0;
        border: 1px solid #2c2c2c; border-radius: 5px;
        padding: 6px 12px; font-size: 11px;
    }
    QPushButton:hover { background: #2a2a2a; }
    QGroupBox {
        border: 1px solid #222; border-radius: 5px;
        margin-top: 6px; padding: 10px 8px 8px 8px;
        color: #555; font-size: 10px; font-weight: 700; letter-spacing: 1px;
    }
    QGroupBox::title { subcontrol-origin: margin; left: 8px; color: #5294e2; }
    QLabel { color: #ccc; }
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
        background: #1c1c1c; color: #e0e0e0;
        border: 1px solid #262626; border-radius: 4px; padding: 4px 8px;
    }
    QLineEdit:focus, QSpinBox:focus { border-color: #5294e2; }
    """

    def __init__(self, overlays: list[OverlayItem],
                 parent_tab: "OverlayTab" = None,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cantio — Editor Overlay vizual")
        self.setMinimumSize(1100, 660)
        self.setStyleSheet(self._STYLE)

        self._overlays: list[OverlayItem] = list(overlays)
        self._parent_tab = parent_tab
        self._selected: Optional[OverlayItem] = None

        self._build_ui()
        self._refresh_list()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        splitter.setChildrenCollapsible(False)
        self.setCentralWidget(splitter)

        # ── Left panel ────────────────────────────────────────────────────────
        left = QWidget()
        left.setFixedWidth(220)
        left.setStyleSheet("background: #131313; border-right: 1px solid #1e1e1e;")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(6, 8, 6, 8)
        ll.setSpacing(4)

        hdr = QLabel("ELEMENTE")
        hdr.setStyleSheet(
            "color:#5294e2; font-size:10px; font-weight:700; letter-spacing:2px; padding:2px 4px;"
        )
        ll.addWidget(hdr)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_list_select)
        ll.addWidget(self._list, 1)

        vis_row = QHBoxLayout()
        vis_row.setSpacing(4)
        show_btn = QPushButton("👁")
        show_btn.setToolTip("Afișează")
        show_btn.setFixedWidth(36)
        show_btn.clicked.connect(self._show_selected)
        hide_btn = QPushButton("🙈")
        hide_btn.setToolTip("Ascunde")
        hide_btn.setFixedWidth(36)
        hide_btn.clicked.connect(self._hide_selected)
        vis_row.addWidget(show_btn)
        vis_row.addWidget(hide_btn)
        vis_row.addStretch()
        ll.addLayout(vis_row)

        add_btn = QPushButton("+ Adaugă element")
        add_btn.setStyleSheet(
            "QPushButton { background: #18283a; color: #5294e2; "
            "border: 1px solid #1c3a5a; border-radius: 5px; padding: 7px; }"
            "QPushButton:hover { background: #1c3a5a; color: #e0e0e0; }"
        )
        add_btn.clicked.connect(self._show_add_menu)
        ll.addWidget(add_btn)

        del_btn = QPushButton("🗑 Șterge")
        del_btn.setStyleSheet(
            "QPushButton { color: #f44336; border-color: #2e1a1a; }"
            "QPushButton:hover { background: #251a1a; border-color: #f44336; }"
        )
        del_btn.clicked.connect(self._delete_selected)
        ll.addWidget(del_btn)

        splitter.addWidget(left)

        # ── Centre: canvas ────────────────────────────────────────────────────
        canvas_wrap = QWidget()
        cw_lay = QVBoxLayout(canvas_wrap)
        cw_lay.setContentsMargins(8, 8, 8, 8)
        cw_lay.setSpacing(4)

        canvas_hdr = QLabel("CANVAS  (1920 × 1080)")
        canvas_hdr.setStyleSheet(
            "color:#5294e2; font-size:10px; font-weight:700; letter-spacing:2px;"
        )
        cw_lay.addWidget(canvas_hdr)

        self._canvas = OverlayCanvas()
        self._canvas.set_overlays(self._overlays)
        self._canvas.item_selected.connect(self._on_canvas_select)
        self._canvas.item_moved.connect(self._on_item_moved)
        cw_lay.addWidget(self._canvas, 1)

        send_all_btn = QPushButton("📺 Trimite toate overlay-urile live")
        send_all_btn.setStyleSheet(
            "QPushButton { background: #1c3a1c; color: #4caf50; "
            "border: 1px solid #2a5a2a; border-radius: 5px; "
            "padding: 8px; font-weight: 600; }"
            "QPushButton:hover { background: #2a4a2a; }"
        )
        send_all_btn.clicked.connect(self._send_all_live)
        cw_lay.addWidget(send_all_btn)

        splitter.addWidget(canvas_wrap)

        # ── Right panel: property editor ──────────────────────────────────────
        self._props_scroll = QScrollArea()
        self._props_scroll.setWidgetResizable(True)
        self._props_scroll.setFixedWidth(280)
        self._props_scroll.setStyleSheet("QScrollArea { border: none; background: #161616; }")

        # Show initial placeholder (created fresh — never stored as self.xxx,
        # because QScrollArea takes ownership and Qt deletes the old widget when
        # setWidget() is called again, making any stored reference a dangling pointer)
        self._props_scroll.setWidget(self._make_props_placeholder())

        splitter.addWidget(self._props_scroll)
        splitter.setSizes([220, 600, 280])

    # ── List management ───────────────────────────────────────────────────────

    def _refresh_list(self):
        self._list.clear()
        for ov in self._overlays:
            eye   = "👁" if ov.visible else "🙈"
            icon  = OVERLAY_TYPE_ICONS.get(ov.type, "?")
            item  = QListWidgetItem(f"{eye} {icon}  {ov.name}")
            item.setData(Qt.ItemDataRole.UserRole, ov.id)
            self._list.addItem(item)

    def _on_list_select(self, row: int):
        if row < 0 or row >= len(self._overlays):
            self._selected = None
            self._canvas.select_item(None)
            self._show_props(None)
            return
        ov = self._overlays[row]
        self._selected = ov
        self._canvas.select_item(ov)
        self._show_props(ov)

    def _on_canvas_select(self, item: Optional[OverlayItem]):
        self._selected = item
        if item:
            idx = next((i for i, o in enumerate(self._overlays) if o is item), -1)
            if idx >= 0:
                self._list.blockSignals(True)
                self._list.setCurrentRow(idx)
                self._list.blockSignals(False)
        self._show_props(item)

    def _on_item_moved(self, item: OverlayItem):
        self._show_props(item)   # refresh coordinate spinboxes

    # ── Add / Delete ──────────────────────────────────────────────────────────

    def _show_add_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #1e1e1e; color: #e0e0e0; border: 1px solid #333; padding: 2px; }"
            "QMenu::item { padding: 7px 20px; border-radius: 3px; }"
            "QMenu::item:selected { background: #1c3a5a; }"
        )
        for otype in OVERLAY_TYPES:
            icon = OVERLAY_TYPE_ICONS.get(otype, "?")
            menu.addAction(
                f"{icon}  {otype.capitalize()}",
                lambda checked=False, t=otype: self._add_item(t)
            )
        btn = self.sender()
        if btn:
            menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _add_item(self, otype: str):
        defaults = {
            "ticker":    {"ticker_in_effect": "slide_up", "ticker_out_effect": "slide_down",
                          "ticker_speed": 80, "text": ""},
            "countdown": {"seconds": 60},
            "clock":     {"format": "HH:MM"},
            "text":      {"text": "Text overlay", "font_size": 48, "color": "#ffffff"},
            "image":     {"path": ""},
            "shape":     {"shape": "rect", "color": "#5294e2", "opacity": 0.8},
            "logo":      {"path": ""},
        }
        ov = OverlayItem(
            name=f"{otype.capitalize()} {len(self._overlays) + 1}",
            otype=otype,
            x=200, y=200, width=400, height=100,
            settings=defaults.get(otype, {}),
        )
        self._overlays.append(ov)
        self._canvas.set_overlays(self._overlays)
        self._refresh_list()
        self._list.setCurrentRow(len(self._overlays) - 1)
        self._emit_changed()

    def _delete_selected(self):
        row = self._list.currentRow()
        if row < 0 or row >= len(self._overlays):
            return
        self._overlays.pop(row)
        self._canvas.set_overlays(self._overlays)
        self._refresh_list()
        self._canvas.select_item(None)
        self._show_props(None)
        self._emit_changed()

    def _show_selected(self):
        if self._selected:
            self._selected.visible = True
            self._refresh_list()
            self._canvas.update()

    def _hide_selected(self):
        if self._selected:
            self._selected.visible = False
            self._refresh_list()
            self._canvas.update()

    # ── Property panel ────────────────────────────────────────────────────────

    def _make_props_placeholder(self) -> QLabel:
        """Create a fresh placeholder widget each time it is needed.

        QScrollArea takes ownership of whatever is passed to setWidget().
        Reusing a stored reference after setWidget() has replaced it with
        another widget is unsafe — Qt may have already deleted the C++ object,
        which causes RuntimeError: wrapped C/C++ object of type QLabel has been
        deleted.  Always create a new instance instead.
        """
        lbl = QLabel(
            "Selectează un element de pe canvas\npentru a-i edita proprietățile."
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #444; font-size: 11px;")
        return lbl

    def _show_props(self, item: Optional[OverlayItem]):
        # Detach the old widget so Qt doesn't delete it while we still hold a ref
        old = self._props_scroll.widget()
        if old is not None:
            old.setParent(None)

        if item is None:
            # Always create fresh — never reuse a previously managed widget
            self._props_scroll.setWidget(self._make_props_placeholder())
            return

        w = QWidget()
        w.setStyleSheet("background: #161616;")
        vl = QVBoxLayout(w)
        vl.setContentsMargins(12, 12, 12, 12)
        vl.setSpacing(10)

        # Header
        hdr = QLabel(f"{OVERLAY_TYPE_ICONS.get(item.type,'?')}  {item.name}")
        hdr.setStyleSheet(
            "color: #5294e2; font-size: 12px; font-weight: 700; background: transparent;"
        )
        vl.addWidget(hdr)

        # Name
        FL = QFormLayout
        name_grp = QGroupBox("GENERAL")
        nf = FL(name_grp)
        name_edit = QLineEdit(item.name)
        name_edit.textChanged.connect(lambda v: setattr(item, 'name', v) or
                                      self._refresh_list() or self._canvas.update())
        nf.addRow("Nume:", name_edit)
        vl.addWidget(name_grp)

        # Position + size
        pos_grp = QGroupBox("POZIȚIE ȘI DIMENSIUNE")
        pf = FL(pos_grp)

        def _spin(val, lo, hi, attr):
            sb = QSpinBox()
            sb.setRange(lo, hi)
            sb.setValue(val)
            sb.valueChanged.connect(lambda v, a=attr: (setattr(item, a, v),
                                                        self._canvas.update()))
            return sb

        pf.addRow("X:",         _spin(item.x,      0, 1920, 'x'))
        pf.addRow("Y:",         _spin(item.y,      0, 1080, 'y'))
        pf.addRow("Lățime:",    _spin(item.width,  4, 1920, 'width'))
        pf.addRow("Înălțime:",  _spin(item.height, 4, 1080, 'height'))
        pf.addRow("Z-index:",   _spin(item.z_index, 0, 99, 'z_index'))
        vl.addWidget(pos_grp)

        # Type-specific settings
        self._add_type_props(vl, item)

        # Apply / Send live
        apply_btn = QPushButton("📺 Trimite live")
        apply_btn.setStyleSheet(
            "QPushButton { background: #1c3a1c; color: #4caf50; "
            "border: 1px solid #2a5a2a; border-radius: 5px; "
            "padding: 8px; font-weight: 600; }"
            "QPushButton:hover { background: #2a4a2a; }"
        )
        apply_btn.clicked.connect(lambda: self._send_item_live(item))
        vl.addWidget(apply_btn)
        vl.addStretch()

        self._props_scroll.setWidget(w)

    def _add_type_props(self, layout: QVBoxLayout, item: OverlayItem):
        """Append type-specific property widgets."""
        s   = item.settings
        grp = QGroupBox(f"SETĂRI {item.type.upper()}")
        FL = QFormLayout
        fl  = FL(grp)

        def _str_field(key: str, label: str, placeholder: str = ""):
            edit = QLineEdit(str(s.get(key, '')))
            edit.setPlaceholderText(placeholder)
            edit.textChanged.connect(lambda v, k=key: s.update({k: v}))
            fl.addRow(label, edit)

        def _int_field(key: str, label: str, lo: int, hi: int, suffix: str = ""):
            sb = QSpinBox()
            sb.setRange(lo, hi)
            sb.setValue(int(s.get(key, 0)))
            sb.setSuffix(suffix)
            sb.valueChanged.connect(lambda v, k=key: s.update({k: v}))
            fl.addRow(label, sb)

        def _color_btn(key: str, label: str):
            color = str(s.get(key, '#ffffff'))
            btn   = QPushButton(color)
            btn.setStyleSheet(f"background:{color};color:{'#000' if _is_light(color) else '#fff'};")
            def _pick():
                from PyQt6.QtWidgets import QColorDialog
                c = QColorDialog.getColor(QColor(btn.text()), self)
                if c.isValid():
                    btn.setText(c.name())
                    lt = _is_light(c.name())
                    btn.setStyleSheet(
                        f"background:{c.name()};color:{'#000' if lt else '#fff'};"
                    )
                    s[key] = c.name()
            btn.clicked.connect(_pick)
            fl.addRow(label, btn)

        if item.type == "text":
            _str_field("text", "Text:")
            _int_field("font_size", "Mărime:", 8, 300, " px")
            _color_btn("color", "Culoare:")
        elif item.type == "ticker":
            _str_field("text", "Text:")
            _int_field("ticker_speed", "Viteză:", 10, 500, " px/s")
            _color_btn("ticker_color", "Culoare:")
        elif item.type == "countdown":
            _int_field("seconds", "Durată:", 1, 86400, " s")
            _color_btn("color", "Culoare:")
        elif item.type == "clock":
            fmt_cb = QComboBox()
            fmt_cb.addItems(["HH:MM", "HH:MM:SS", "12h"])
            idx = fmt_cb.findText(str(s.get("format", "HH:MM")))
            if idx >= 0:
                fmt_cb.setCurrentIndex(idx)
            fmt_cb.currentTextChanged.connect(lambda v: s.update({"format": v}))
            fl.addRow("Format:", fmt_cb)
        elif item.type in ("image", "logo"):
            path_row = QHBoxLayout()
            path_edit = QLineEdit(str(s.get("path", "")))
            path_edit.textChanged.connect(lambda v: s.update({"path": v}))
            browse = QPushButton("Browse…")
            browse.setFixedWidth(70)
            def _browse(edit=path_edit):
                p, _ = QFileDialog.getOpenFileName(
                    self, "Selectează fișier", "",
                    "Imagini (*.png *.jpg *.jpeg *.webp *.svg);;Toate (*)"
                )
                if p:
                    edit.setText(p)
            browse.clicked.connect(_browse)
            path_row.addWidget(path_edit, 1)
            path_row.addWidget(browse)
            fl.addRow("Fișier:", path_row)
        elif item.type == "shape":
            sh_cb = QComboBox()
            sh_cb.addItems(["rect", "circle", "triangle", "line"])
            si = sh_cb.findText(str(s.get("shape", "rect")))
            if si >= 0:
                sh_cb.setCurrentIndex(si)
            sh_cb.currentTextChanged.connect(lambda v: s.update({"shape": v}))
            fl.addRow("Formă:", sh_cb)
            _color_btn("color", "Culoare:")

        layout.addWidget(grp)

    # ── Send to display ───────────────────────────────────────────────────────

    def _send_item_live(self, item: OverlayItem):
        """Forward to parent_tab's send logic."""
        if self._parent_tab:
            item.visible = True
            self._parent_tab._send_to_display(item)
            self._refresh_list()
            self._canvas.update()

    def _send_all_live(self):
        if self._parent_tab:
            for ov in self._overlays:
                if ov.visible:
                    self._parent_tab._send_to_display(ov)

    # ── Emit changed ──────────────────────────────────────────────────────────

    def _emit_changed(self):
        self.overlays_changed.emit(list(self._overlays))

    def closeEvent(self, ev):
        self._emit_changed()
        super().closeEvent(ev)


# ── Helper ────────────────────────────────────────────────────────────────────

def _is_light(hex_color: str) -> bool:
    try:
        c = QColor(hex_color)
        return (c.red() * 299 + c.green() * 587 + c.blue() * 114) / 1000 > 128
    except Exception:
        return False
