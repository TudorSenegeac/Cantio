"""
Cantio - Theme Editor
Provides: generate_theme_preview, ThemeCard, ThemesGrid,
          NewThemeDialog, ThemeVisualEditor, ThemeCanvas
"""
from __future__ import annotations

import os

from translations import t

# Slide transition effects — must match TRANSITION_TYPES in display.js
TRANSITIONS = [
    "instant", "fade", "crossfade", "fade_black", "fade_white", "dissolve",
    "slide_left", "slide_right", "slide_up", "slide_down",
    "push_left", "push_right", "push_up", "push_down",
    "reveal_left", "reveal_right", "reveal_up", "reveal_down",
    "wipe_left", "wipe_right", "wipe_up", "wipe_down", "wipe_diag",
    "zoom_in", "zoom_out", "iris_open", "iris_close",
    "flip_h", "flip_v", "spin", "squeeze_h", "squeeze_v",
    "bars_v", "bars_h", "checkerboard", "morph", "blur",
]

# Glyph per transition so operators can tell at a glance what each one does.
_TRANS_GLYPH = {
    "instant": "⚡", "fade": "▒", "crossfade": "▒", "fade_black": "◼",
    "fade_white": "◻", "dissolve": "▓", "blur": "░", "morph": "✦",
    "slide_left": "←", "slide_right": "→", "slide_up": "↑", "slide_down": "↓",
    "push_left": "⇐", "push_right": "⇒", "push_up": "⇑", "push_down": "⇓",
    "reveal_left": "◀", "reveal_right": "▶", "reveal_up": "▲", "reveal_down": "▼",
    "wipe_left": "◧", "wipe_right": "◨", "wipe_up": "⬒", "wipe_down": "⬓", "wipe_diag": "◪",
    "zoom_in": "⊕", "zoom_out": "⊖", "iris_open": "◯", "iris_close": "⊙",
    "flip_h": "⇋", "flip_v": "⇅", "spin": "↻", "squeeze_h": "⇔", "squeeze_v": "⇕",
    "bars_v": "▥", "bars_h": "▤", "checkerboard": "▦",
}


def transition_icon(name):
    """Return a small QIcon glyph for a transition (kept separate from the item
    text so combo currentText() still returns the raw transition name)."""
    from PyQt6.QtGui import QPixmap, QPainter, QColor, QIcon, QFont
    from PyQt6.QtCore import Qt as _Qt
    g = _TRANS_GLYPH.get(name, "•")
    pm = QPixmap(18, 18)
    pm.fill(_Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setPen(QColor("#89b4fa"))
    f = QFont(); f.setPointSize(11); p.setFont(f)
    p.drawText(pm.rect(), _Qt.AlignmentFlag.AlignCenter, g)
    p.end()
    return QIcon(pm)


def populate_transition_combo(combo, names):
    """Fill a QComboBox with transition names + their glyph icons."""
    for n in names:
        combo.addItem(transition_icon(n), n)

from PyQt6.QtCore import (
    Qt, QMimeData, QPoint, QRect, QRectF, QTimer, pyqtSignal, QThread,
)
from PyQt6.QtGui import (
    QBrush, QColor, QDrag, QFont, QFontMetrics,
    QImage, QLinearGradient, QPainter, QPainterPath, QPen,
    QPixmap, QRadialGradient,
)
from PyQt6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFormLayout, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton,
    QRadioButton, QScrollArea, QSizePolicy, QSlider, QSpinBox,
    QStackedWidget, QTabWidget, QVBoxLayout, QWidget, QFontComboBox,
)

try:
    from settings_dialog import ColorButton
except Exception:
    class ColorButton(QPushButton):           # type: ignore[no-redef]
        colorChanged = pyqtSignal(str)

        def __init__(self, color: str = "#000000", parent=None):
            super().__init__(parent)
            self._color = color
            self.setText(color)
            self.clicked.connect(self._pick)

        def color(self) -> str:
            return self._color

        def set_color(self, c: str):
            self._color = c
            self.setText(c)

        def _pick(self):
            from PyQt6.QtWidgets import QColorDialog
            c = QColorDialog.getColor(QColor(self._color), self)
            if c.isValid():
                self._color = c.name()
                self.setText(c.name())
                self.colorChanged.emit(self._color)


class CollapsibleSection(QWidget):
    """Collapsible panel with a coloured header button and a QFormLayout body."""

    def __init__(self, title: str, color: str = "#cba6f7",
                 collapsed: bool = False, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 2)
        layout.setSpacing(0)

        arrow = "▶" if collapsed else "▼"
        self._btn = QPushButton(f"{arrow}  {title}")
        self._btn.setStyleSheet(f"""
            QPushButton {{
                background: #252536;
                color: {color};
                border: none;
                border-left: 3px solid {color};
                padding: 7px 10px;
                font-weight: bold;
                font-size: 11px;
                text-align: left;
            }}
            QPushButton:hover {{ background: #313244; }}
        """)
        self._btn.clicked.connect(self._toggle)
        layout.addWidget(self._btn)

        self._body = QWidget()
        self._body.setStyleSheet(
            "background:#1e1e2e;"
            "border-left:2px solid #313244;"
            "margin-left:4px;padding:2px;"
        )
        self._body_layout = QFormLayout(self._body)
        self._body_layout.setContentsMargins(8, 6, 8, 8)
        self._body_layout.setSpacing(6)
        self._body_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._body.setVisible(not collapsed)
        layout.addWidget(self._body)

    def _toggle(self):
        vis = not self._body.isVisible()
        self._body.setVisible(vis)
        raw = self._btn.text()
        # replace first char (▼ or ▶)
        title = raw[2:] if len(raw) > 2 else raw
        self._btn.setText(f"{'▼' if vis else '▶'} {title}")

    def addRow(self, label, widget):
        self._body_layout.addRow(label, widget)

    def addWidget(self, widget):
        self._body_layout.addRow(widget)

    def addLayout(self, layout):
        w = QWidget()
        w.setLayout(layout)
        self._body_layout.addRow(w)


STYLE = """
QWidget          { background:#1e1e2e; color:#cdd6f4; font-size:12px; }
QGroupBox        { border:1px solid #313244; border-radius:6px;
                   margin-top:8px; padding-top:8px; color:#a6adc8; }
QGroupBox::title { subcontrol-origin:margin; left:8px; }
QLabel           { color:#cdd6f4; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background:#313244; border:1px solid #45475a;
    border-radius:4px; padding:4px; color:#cdd6f4; }
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border-color:#cba6f7; }
QPushButton {
    background:#313244; color:#cdd6f4;
    border:1px solid #45475a; border-radius:6px; padding:6px 12px; }
QPushButton:hover   { background:#45475a; color:#cba6f7; }
QPushButton:pressed { background:#181825; }
QTabWidget::pane    { border:1px solid #313244; border-radius:4px; }
QTabBar::tab        { background:#181825; color:#6c7086;
                      padding:6px 14px; border-radius:4px 4px 0 0; }
QTabBar::tab:selected { background:#313244; color:#cdd6f4; }
QScrollArea         { border:none; }
QRadioButton, QCheckBox { color:#cdd6f4; spacing:6px; }
QDialogButtonBox QPushButton { min-width:100px; }
QSlider::groove:horizontal  { background:#313244; height:4px; border-radius:2px; }
QSlider::handle:horizontal  { background:#cba6f7; width:12px; height:12px;
                               margin:-4px 0; border-radius:6px; }
"""


# ── generate_theme_preview ─────────────────────────────────────────────────────

def generate_theme_preview(theme: dict, output_path: str) -> str:
    """Generează PNG preview pentru temă și îl salvează pe disc.
    Folosește QImage (thread-safe) — nu ține nimic în RAM după salvare."""

    aspect = theme.get("aspect_ratio", "16:9")
    if aspect == "4:3":
        w, h = 320, 240
    elif aspect == "21:9":
        w, h = 320, 137
    else:
        w, h = 320, 180

    img = QImage(w, h, QImage.Format.Format_RGB32)

    bg      = theme.get("background", {})
    bg_type = bg.get("type", "color")

    if bg_type == "transparent":
        img.fill(QColor("#888888").rgb())
    elif bg_type == "gradient":
        img.fill(QColor(bg.get("grad_color1", "#000033")).rgb())
    else:
        img.fill(QColor(bg.get("color", "#000000")).rgb())

    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    # Gradient
    if bg_type == "gradient":
        c1   = QColor(bg.get("grad_color1", "#000033"))
        c2   = QColor(bg.get("grad_color2", "#000000"))
        gdir = bg.get("grad_dir", "Sus→Jos")
        if gdir == "Radial":
            grad = QRadialGradient(w / 2, h / 2, max(w, h) / 2)
        elif "Stânga" in gdir or "Left" in gdir:
            grad = QLinearGradient(0, 0, w, 0)
        elif "Diagonal" in gdir:
            grad = QLinearGradient(0, 0, w, h)
        else:
            grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, c1)
        grad.setColorAt(1, c2)
        painter.fillRect(0, 0, w, h, QBrush(grad))

    # Background image (QImage — thread-safe, no QPixmap)
    bg_img_path = bg.get("image", "")
    if bg_img_path and os.path.exists(bg_img_path):
        bg_img = QImage(bg_img_path)
        if not bg_img.isNull():
            op = float(bg.get("opacity", 0.85))
            painter.setOpacity(op)
            scaled = bg_img.scaled(
                w, h,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            painter.drawImage(0, 0, scaled)
            painter.setOpacity(1.0)

    # Checkerboard for transparent
    if bg_type == "transparent":
        csz = 16
        for cy in range(0, h, csz):
            for cx in range(0, w, csz):
                color = QColor("#aaaaaa") if (cx // csz + cy // csz) % 2 == 0 \
                        else QColor("#888888")
                painter.fillRect(cx, cy, csz, csz, color)

    # Text
    t      = theme.get("text", {})
    l      = theme.get("layout", {})
    t_type = theme.get("type", "songs")
    scale  = w / 1920.0

    family = t.get("font_family", "Arial")
    size   = max(8, int(int(t.get("font_size", 48)) * scale))
    bold   = t.get("font_bold", "true") == "true"
    italic = t.get("font_italic", "false") == "true"
    color  = QColor(t.get("text_color", "#ffffff"))
    align_name = t.get("text_align", "center")
    uppercase  = t.get("uppercase", "false") == "true"

    font = QFont(family, size)
    font.setBold(bold)
    font.setItalic(italic)
    painter.setFont(font)
    painter.setPen(color)

    # Centered demo text — matches the live renderer (verse & lyrics both centered)
    if t_type == "bible":
        demo_lines = ["Fiindcă Dumnezeu", "aşa a iubit lumea..."]
    else:
        demo_lines = ["Doamne, Tu ești", "lumina mea"]
    if uppercase:
        demo_lines = [ln.upper() for ln in demo_lines]

    fm  = QFontMetrics(font)
    lh  = int(fm.height() * float(t.get("line_spacing", 1.4)))
    total_h = lh * len(demo_lines)
    start_y = (h - total_h) // 2 + fm.ascent()
    try:
        _raw_m = float(l.get("margin", 0.06))
    except (TypeError, ValueError):
        _raw_m = 0.06
    margin_px = max(4, int(round(min(w, h) * _raw_m) if _raw_m < 2
                           else _raw_m * scale))

    halign = (Qt.AlignmentFlag.AlignLeft if align_name == "left"
              else Qt.AlignmentFlag.AlignRight if align_name == "right"
              else Qt.AlignmentFlag.AlignHCenter)
    for i, line in enumerate(demo_lines):
        ly = start_y + i * lh
        if t.get("text_shadow", "true") == "true":
            so = max(1, int(2 * scale))
            painter.setPen(QColor(0, 0, 0, 160))
            painter.drawText(QRect(margin_px + so, ly - fm.ascent() + so,
                                   w - margin_px * 2, fm.height()),
                             halign, line)
        painter.setPen(color)
        painter.drawText(QRect(margin_px, ly - fm.ascent(),
                               w - margin_px * 2, fm.height()),
                         halign, line)

    # Bible reference (bottom-right corner)
    if t_type == "bible":
        ref_cfg   = l.get("reference", {})
        ref_size  = max(6, int(int(ref_cfg.get("size",
                       l.get("ref_font_size", 24))) * scale))
        ref_color = QColor(ref_cfg.get("color", l.get("ref_color", "#aaaaaa")))
        ref_font  = QFont(family, ref_size)
        ref_font.setBold(bool(ref_cfg.get("bold", False)))
        ref_font.setItalic(bool(ref_cfg.get("italic", True)))
        painter.setFont(ref_font)
        painter.setPen(ref_color)
        painter.drawText(QRect(0, 0, w - margin_px, h - margin_px // 2),
                         Qt.AlignmentFlag.AlignRight |
                         Qt.AlignmentFlag.AlignBottom, "Ioan 3:16")

    # Border
    painter.setPen(QPen(QColor("#45475a"), 1))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(0, 0, w - 1, h - 1)

    painter.end()

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    img.save(output_path, "PNG")

    del painter
    del img
    return output_path


# ── ThemeCard ──────────────────────────────────────────────────────────────────

class ThemeCard(QWidget):
    clicked        = pyqtSignal(str)
    double_clicked = pyqtSignal(str)

    def __init__(self, theme_name: str, preview_path: str | None = None,
                 is_active: bool = False, parent=None):
        super().__init__(parent)
        self.theme_name = theme_name
        self.is_active  = is_active
        self._selected  = False
        self.setFixedSize(170, 130)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build_ui(preview_path)

    def _build_ui(self, preview_path: str | None):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Preview image
        self.preview_label = QLabel()
        self.preview_label.setFixedSize(162, 91)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet(
            "border:1px solid #45475a; border-radius:4px; background:#0a0a14;")
        self._load_preview(preview_path)
        layout.addWidget(self.preview_label)

        # Theme name
        name_label = QLabel(self.theme_name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet(
            "font-size:11px; color:#cdd6f4; background:transparent;")
        name_label.setWordWrap(True)
        name_label.setMaximumHeight(30)
        layout.addWidget(name_label)

        # Active badge
        if self.is_active:
            badge = QLabel("★ Default")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                "font-size:9px; color:#f9e2af; background:transparent;")
            layout.addWidget(badge)

        self._update_style()

    def _load_preview(self, preview_path: str | None):
        if preview_path and os.path.exists(preview_path):
            pix = QPixmap(preview_path)
            if not pix.isNull():
                self.preview_label.setPixmap(
                    pix.scaled(162, 91,
                               Qt.AspectRatioMode.IgnoreAspectRatio,
                               Qt.TransformationMode.SmoothTransformation))
                del pix
                return
        self.preview_label.setText("No Preview")
        self.preview_label.setStyleSheet(
            "border:1px solid #45475a; border-radius:4px; background:#0a0a14;"
            "color:#45475a; font-size:10px;")

    def reload_preview(self, preview_path: str | None):
        self._load_preview(preview_path)
        self.preview_label.update()

    def set_selected(self, selected: bool):
        self._selected = selected
        self._update_style()

    def _update_style(self):
        if self._selected:
            self.setStyleSheet(
                "ThemeCard { background:#313244; border:2px solid #cba6f7;"
                " border-radius:8px; }")
        else:
            self.setStyleSheet(
                "ThemeCard { background:#181825; border:1px solid #313244;"
                " border-radius:8px; }"
                "ThemeCard:hover { background:#252536;"
                " border:1px solid #45475a; }")
        self.update()

    # ── Events ────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.theme_name)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit(self.theme_name)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(f"CANTIO_THEME:{self.theme_name}")
            drag.setMimeData(mime)
            pix = QPixmap(220, 36)
            pix.fill(QColor("#313244"))
            p = QPainter(pix)
            p.setPen(QColor("#cba6f7"))
            p.setFont(QFont("Segoe UI", 10))
            p.drawText(10, 24, f"🎨 {self.theme_name}")
            p.end()
            drag.setPixmap(pix)
            drag.setHotSpot(QPoint(110, 18))
            drag.exec(Qt.DropAction.CopyAction)

    def contextMenuEvent(self, event):
        parent = self.parent()
        while parent:
            if hasattr(parent, "_card_context_menu"):
                parent._card_context_menu(self.theme_name, event)
                return
            parent = parent.parent()


# ── ThemesGrid ─────────────────────────────────────────────────────────────────

class ThemesGrid(QScrollArea):
    theme_selected       = pyqtSignal(str)
    theme_double_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(
            "QScrollArea { background:#141420; border:none; }")

        self._container = QWidget()
        self._container.setStyleSheet("background:#141420;")
        self._grid = QGridLayout(self._container)
        self._grid.setSpacing(8)
        self._grid.setContentsMargins(8, 8, 8, 8)
        self._grid.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setWidget(self._container)

        self._cards: dict[str, ThemeCard] = {}
        self._selected: str | None = None

    # ── Public API ────────────────────────────────────────────────────────────

    def populate(self, themes_data: dict, active_name: str,
                 preview_dir: str):
        """Populează gridul cu carduri — șterge cardurile vechi."""
        for card in self._cards.values():
            self._grid.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        cols = max(1, (self.viewport().width() - 16) // 186)
        row = col = 0

        for name, _theme in themes_data.items():
            safe = name.replace("/", "_").replace("\\", "_")
            preview_path = os.path.join(preview_dir, f"{safe}.png")

            card = ThemeCard(
                name,
                preview_path=preview_path,
                is_active=(name == active_name),
            )
            card.clicked.connect(self._on_card_clicked)
            card.double_clicked.connect(self.theme_double_clicked)
            self._grid.addWidget(card, row, col)
            self._cards[name] = card

            col += 1
            if col >= cols:
                col = 0
                row += 1

        if self._cards:
            if self._selected and self._selected in self._cards:
                self._select(self._selected, emit=False)
            else:
                self._select(next(iter(self._cards)), emit=False)

    def selected_name(self) -> str | None:
        return self._selected

    # ── Internals ─────────────────────────────────────────────────────────────

    def _on_card_clicked(self, name: str):
        self._select(name)
        self.theme_selected.emit(name)

    def _select(self, name: str, emit: bool = True):
        if self._selected and self._selected in self._cards:
            self._cards[self._selected].set_selected(False)
        self._selected = name
        if name in self._cards:
            self._cards[name].set_selected(True)
            self.ensureWidgetVisible(self._cards[name])

    def _card_context_menu(self, theme_name: str, event):
        """Deleghează meniu contextual la ThemesTab (parcurge ierarhia)."""
        parent = self.parent()
        while parent:
            if hasattr(parent, "_context_menu_for"):
                parent._context_menu_for(theme_name, event)
                return
            parent = parent.parent()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(100, self._relayout)

    def _relayout(self):
        if not self._cards:
            return
        cols  = max(1, (self.viewport().width() - 16) // 186)
        items = list(self._cards.items())
        for i, (_, card) in enumerate(items):
            self._grid.addWidget(card, i // cols, i % cols)


# ── NewThemeDialog ─────────────────────────────────────────────────────────────

class NewThemeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("new_theme_dialog"))
        self.setMinimumWidth(540)
        self.setStyleSheet(STYLE)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Name
        layout.addWidget(QLabel(t("theme_name") + ":"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(t("theme_name_placeholder"))
        layout.addWidget(self.name_edit)

        # Type
        type_group = QGroupBox(t("theme_type"))
        type_l = QHBoxLayout(type_group)
        self.r_songs = QRadioButton(f"🎵 {t('theme_songs')}")
        self.r_bible = QRadioButton(f"📖 {t('theme_bible')}")
        self.r_both  = QRadioButton(t("both"))
        self.r_songs.setChecked(True)
        for r in (self.r_songs, self.r_bible, self.r_both):
            type_l.addWidget(r)
        layout.addWidget(type_group)

        # Resolution
        res_group  = QGroupBox(t("projector_resolution"))
        res_layout = QVBoxLayout(res_group)

        resolutions = [
            ("🖥 Full HD",    "1920×1080", 1920, 1080, "16:9",  True),
            ("📺 HD",         "1280×720",  1280,  720, "16:9",  False),
            ("📽 4K",         "3840×2160", 3840, 2160, "16:9",  False),
            ("📊 XGA",        "1024×768",  1024,  768, "4:3",   False),
            ("📊 SXGA",       "1400×1050", 1400, 1050, "4:3",   False),
            ("🖥 WXGA",       "1280×800",  1280,  800, "16:10", False),
            ("🎬 Ultrawide",  "2560×1080", 2560, 1080, "21:9",  False),
        ]

        res_grid = QGridLayout()
        res_grid.setSpacing(6)
        self._res_btns = QButtonGroup(self)

        for i, (name, res_str, rw, rh, aspect, default) in \
                enumerate(resolutions):
            btn = QPushButton(f"{name}\n{res_str}\n({aspect})")
            btn.setCheckable(True)
            btn.setChecked(default)
            btn.setProperty("res_w", rw)
            btn.setProperty("res_h", rh)
            btn.setProperty("aspect", aspect)
            btn.setFixedSize(120, 70)
            btn.setStyleSheet("""
                QPushButton {
                    background:#313244; color:#cdd6f4;
                    border:1px solid #45475a; border-radius:6px;
                    font-size:11px; }
                QPushButton:checked {
                    background:#45475a; border:2px solid #cba6f7;
                    color:#cba6f7; }
                QPushButton:hover { background:#3d3d50; }
            """)
            self._res_btns.addButton(btn, i)
            res_grid.addWidget(btn, i // 4, i % 4)

        custom_row = QHBoxLayout()
        self.custom_w = QSpinBox()
        self.custom_w.setRange(640, 7680)
        self.custom_w.setValue(1920)
        self.custom_h = QSpinBox()
        self.custom_h.setRange(480, 4320)
        self.custom_h.setValue(1080)
        custom_row.addWidget(QLabel(t("custom") + ":"))
        custom_row.addWidget(self.custom_w)
        custom_row.addWidget(QLabel("×"))
        custom_row.addWidget(self.custom_h)
        custom_row.addStretch()

        res_layout.addLayout(res_grid)
        res_layout.addLayout(custom_row)
        layout.addWidget(res_group)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        ok_btn = btns.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setText(t("create_and_open_editor"))
        btns.accepted.connect(self._validate_and_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _validate_and_accept(self):
        if not self.name_edit.text().strip():
            self.name_edit.setStyleSheet(
                "border:2px solid #f38ba8; border-radius:4px;")
            self.name_edit.setFocus()
            return
        self.accept()

    def get_name(self) -> str:
        return self.name_edit.text().strip()

    def get_type(self) -> str:
        if self.r_bible.isChecked(): return "bible"
        if self.r_both.isChecked():  return "both"
        return "songs"

    def get_resolution(self) -> tuple[int, int]:
        btn = self._res_btns.checkedButton()
        if btn:
            return btn.property("res_w"), btn.property("res_h")
        return self.custom_w.value(), self.custom_h.value()

    def get_aspect(self) -> str:
        btn = self._res_btns.checkedButton()
        if btn:
            return btn.property("aspect")
        rw, rh = self.get_resolution()
        ratio = rw / rh
        if abs(ratio - 16 / 9)  < 0.1: return "16:9"
        if abs(ratio - 4 / 3)   < 0.1: return "4:3"
        if abs(ratio - 16 / 10) < 0.1: return "16:10"
        return f"{rw}:{rh}"


# ── MultiColorPicker ───────────────────────────────────────────────────────────

class MultiColorPicker(QWidget):
    """Dynamic list of color buttons for animated gradient colors."""
    colorsChanged = pyqtSignal(list)

    _DEFAULT_COLORS = ['#1a237e', '#6a1b9a', '#0d47a1']

    def __init__(self, parent=None):
        super().__init__(parent)
        self._colors: list[str] = list(self._DEFAULT_COLORS)
        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(4)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self._btn_layout = QVBoxLayout()
        self._layout.addLayout(self._btn_layout)

        btn_row = QHBoxLayout()
        add_btn = QPushButton(t("add_color"))
        add_btn.clicked.connect(self._add_color)
        btn_row.addWidget(add_btn)
        self._layout.addLayout(btn_row)

        self._rebuild()

    def _rebuild(self):
        while self._btn_layout.count():
            item = self._btn_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, c in enumerate(self._colors):
            row = QHBoxLayout()
            row_w = QWidget()
            row_w.setLayout(row)
            cb = ColorButton(c)
            cb.colorChanged.connect(lambda col, idx=i: self._on_color(idx, col))
            row.addWidget(cb, 1)
            del_btn = QPushButton("✕")
            del_btn.setFixedWidth(26)
            del_btn.clicked.connect(lambda _, idx=i: self._del_color(idx))
            row.addWidget(del_btn)
            self._btn_layout.addWidget(row_w)

    def _add_color(self):
        self._colors.append('#ffffff')
        self._rebuild()
        self.colorsChanged.emit(self._colors)

    def _del_color(self, idx: int):
        if len(self._colors) > 1:
            self._colors.pop(idx)
            self._rebuild()
            self.colorsChanged.emit(self._colors)

    def _on_color(self, idx: int, col: str):
        if 0 <= idx < len(self._colors):
            self._colors[idx] = col
        self.colorsChanged.emit(self._colors)

    def colors(self) -> list[str]:
        return list(self._colors)

    def set_colors(self, cols: list):
        self._colors = list(cols)
        self._rebuild()


# ── ThemeVisualEditor ──────────────────────────────────────────────────────────

class ThemeVisualEditor(QMainWindow):
    """Editor vizual pentru teme — canvas 1:1 cu ecranul proiectorului."""

    theme_saved = pyqtSignal(str, dict)

    def __init__(self, theme_name: str, theme_data: dict,
                 preview_dir: str, parent=None):
        super().__init__(parent)
        self.theme_name  = theme_name
        self.theme_data  = dict(theme_data)
        self.preview_dir = preview_dir

        res          = theme_data.get("resolution", {})
        self.res_w   = res.get("width",  1920)
        self.res_h   = res.get("height", 1080)
        self.aspect  = theme_data.get("aspect_ratio", "16:9")

        self.setWindowTitle(
            f"{t('theme_editor_title')} — {theme_name}  ({self.res_w}×{self.res_h})")
        self.setMinimumSize(1100, 700)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setStyleSheet(STYLE)

        self._build_ui()
        self._load_theme()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # ── Build all property widgets first (creates self.p_xxx etc.) ────────
        # Store as self.xxx so the container QWidget is NOT garbage-collected.
        # If it were a plain local variable, Python GC would delete it after
        # _build_ui() returns, which causes Qt to delete all child widgets even
        # though Python still holds self.p_ref_bg_enabled etc. references.
        self._text_props_w   = self._build_text_props()
        self._bg_props_w     = self._build_bg_props()
        self._layout_props_w = self._build_layout_props()
        self._overlay_props_w = self._build_overlay_props()

        # ── LEFT: scrollable collapsible panel ────────────────────────────────
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFixedWidth(320)
        left_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setStyleSheet(
            "QScrollArea{border:none;background:#181825;}")

        container = QWidget()
        container.setStyleSheet("background:#181825;")
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(4)

        # ── SECȚIUNEA TEXT ────────────────────────────────────────────────────
        s_text = CollapsibleSection("✏ Text", "#89b4fa", collapsed=False)
        s_text.addRow("Font:", self.p_font)
        s_text.addRow("Mărime:", self.p_size)
        style_row = QHBoxLayout()
        style_row.addWidget(self.p_bold)
        style_row.addWidget(self.p_italic)
        style_row.addWidget(self.p_uppercase)
        s_text.addLayout(style_row)
        s_text.addRow("Culoare:", self.p_color)
        shadow_row2 = QHBoxLayout()
        shadow_row2.addWidget(self.p_shadow)
        shadow_row2.addWidget(self.p_shadow_color)
        s_text.addLayout(shadow_row2)
        outline_row2 = QHBoxLayout()
        outline_row2.addWidget(self.p_outline_w)
        outline_row2.addWidget(self.p_outline_color)
        s_text.addRow("Outline:", outline_row2)
        s_text.addRow("Spațiere:", self.p_spacing)
        align_row2 = QHBoxLayout()
        align_row2.addWidget(self.p_align_left)
        align_row2.addWidget(self.p_align_center)
        align_row2.addWidget(self.p_align_right)
        s_text.addRow("Aliniere:", align_row2)
        vbox.addWidget(s_text)

        # ── SECȚIUNEA STILURI SPECIALE (ecou + cascadă) ───────────────────────
        s_fx = CollapsibleSection("✨ Stiluri speciale", "#f9e2af", collapsed=False)
        # Echo
        s_fx.addWidget(QLabel("— TEXT ECOU (text mare în spate) —"))
        s_fx.addRow("Activat:", self.p_echo_enabled)
        s_fx.addRow("Scară:", self.p_echo_scale)
        s_fx.addRow("Opacitate:", self.p_echo_opacity)
        s_fx.addRow("Culoare:", self.p_echo_color)
        # Cascade
        s_fx.addWidget(QLabel("— MOD CASCADĂ (text repetat, centru evidențiat) —"))
        s_fx.addRow("Activat:", self.p_casc_enabled)
        s_fx.addRow("Copii:", self.p_casc_lines)
        s_fx.addRow("Spațiere:", self.p_casc_gap)
        s_fx.addRow("Culoare centru:", self.p_casc_hl_color)
        s_fx.addRow("Opac. secundare:", self.p_casc_dim_opacity)
        s_fx.addRow("Glow centru:", self.p_casc_glow)
        # Chaotic movement
        s_fx.addWidget(QLabel("— MIȘCARE HAOTICĂ (wow la concert) —"))
        s_fx.addRow("Activat:", self.p_chaos_enabled)
        s_fx.addRow("Amplitudine:", self.p_chaos_amp)
        s_fx.addRow("Viteză:", self.p_chaos_speed)
        # Gradient / animated text colour
        s_fx.addWidget(QLabel("— CULOARE TEXT (gradient / animat) —"))
        s_fx.addRow("Tip:", self.p_tcolor_type)
        s_fx.addRow("De la:", self.p_tgrad_from)
        s_fx.addRow("La:", self.p_tgrad_to)
        # Neon glow
        s_fx.addWidget(QLabel("— GLOW NEON —"))
        s_fx.addRow("Activat:", self.p_glow_enabled)
        s_fx.addRow("Culoare:", self.p_glow_color)
        s_fx.addRow("Mărime:", self.p_glow_size)
        vbox.addWidget(s_fx)

        # ── SECȚIUNEA CUVINTELE LUI ISUS ──────────────────────────────────────
        s_jesus = CollapsibleSection(
            "✝ Cuvintele lui Isus", "#f38ba8", collapsed=True)
        s_jesus.addRow("Activat:", self.p_jesus_enabled)
        s_jesus.addRow("Culoare:", self.p_jesus_color)
        jesus_style = QHBoxLayout()
        jesus_style.addWidget(self.p_jesus_bold)
        jesus_style.addWidget(self.p_jesus_italic)
        s_jesus.addRow("Stil:", jesus_style)
        s_jesus.addRow("Offset:", self.p_jesus_size_offset)
        vbox.addWidget(s_jesus)

        # ── SECȚIUNEA REFERINȚĂ BIBLIE ────────────────────────────────────────
        s_ref = CollapsibleSection(
            "📖 Referință Biblie", "#89dceb", collapsed=True)
        s_ref.addRow("Font:", self.p_ref_font)
        s_ref.addRow("Mărime:", self.p_ref_size)
        ref_style = QHBoxLayout()
        ref_style.addWidget(self.p_ref_bold)
        ref_style.addWidget(self.p_ref_italic)
        ref_style.addWidget(self.p_ref_uppercase)
        s_ref.addRow("Stil:", ref_style)
        s_ref.addRow("Culoare:", self.p_ref_color)
        s_ref.addRow("BG color:", self.p_ref_bg_color)
        s_ref.addRow("Padding:", self.p_ref_padding)
        s_ref.addRow("Format:", self.p_ref_format)
        vbox.addWidget(s_ref)

        # ── SECȚIUNEA FUNDAL TEXT ─────────────────────────────────────────────
        s_textbg = CollapsibleSection(
            "🎨 Fundal Text", "#cba6f7", collapsed=True)
        s_textbg.addRow("Activat:", self.p_textbox_enabled)
        s_textbg.addRow("Culoare:", self.p_textbox_color)
        s_textbg.addRow("Opacitate:", self.p_textbox_opacity)
        pad_row2 = QHBoxLayout()
        pad_row2.addWidget(QLabel("H:"))
        pad_row2.addWidget(self.p_textbox_pad_h)
        pad_row2.addWidget(QLabel("V:"))
        pad_row2.addWidget(self.p_textbox_pad_v)
        s_textbg.addRow("Padding:", pad_row2)
        s_textbg.addRow("Rază colț:", self.p_textbox_radius)
        s_textbg.addRow("Mod:", self.p_textbox_fit)
        s_textbg.addRow("Stil:", self.p_textbox_style)
        s_textbg.addRow("Culoare 2:", self.p_textbox_color2)
        vbox.addWidget(s_textbg)

        # ── SECȚIUNEA FUNDAL ──────────────────────────────────────────────────
        s_bg = CollapsibleSection("🖼 Fundal", "#a6e3a1", collapsed=True)
        s_bg.addWidget(self._bg_props_w)
        vbox.addWidget(s_bg)

        # ── SECȚIUNEA LAYOUT ──────────────────────────────────────────────────
        s_layout = CollapsibleSection("📐 Layout", "#fab387", collapsed=True)
        s_layout.addWidget(self._layout_props_w)
        vbox.addWidget(s_layout)

        # ── SECȚIUNEA OVERLAY ─────────────────────────────────────────────────
        s_overlay = CollapsibleSection("⚙ Overlay", "#94e2d5", collapsed=True)
        s_overlay.addWidget(self._overlay_props_w)
        vbox.addWidget(s_overlay)

        vbox.addStretch()
        left_scroll.setWidget(container)

        # Buttons (below scroll)
        left_wrapper = QWidget()
        left_wrapper.setFixedWidth(320)
        lw_lay = QVBoxLayout(left_wrapper)
        lw_lay.setContentsMargins(0, 0, 0, 0)
        lw_lay.setSpacing(4)
        lw_lay.addWidget(left_scroll, 1)

        btn_row = QHBoxLayout()
        preview_btn = QPushButton(t("preview_btn"))
        preview_btn.clicked.connect(self._update_canvas)

        save_btn = QPushButton(t("save_theme"))
        save_btn.setStyleSheet(
            "background:#a6e3a1; color:#1e1e2e; font-weight:bold;"
            "border:none; border-radius:6px; padding:8px;")
        save_btn.clicked.connect(self._save_theme)

        btn_row.addWidget(preview_btn)
        btn_row.addWidget(save_btn, 1)
        lw_lay.addLayout(btn_row)
        main_layout.addWidget(left_wrapper)

        # CENTER: canvas
        canvas_container = QWidget()
        canvas_container.setStyleSheet("background:#0a0a14;")
        canvas_l = QVBoxLayout(canvas_container)
        canvas_l.setContentsMargins(16, 16, 16, 16)

        res_lbl = QLabel(
            f"Canvas: {self.res_w}×{self.res_h}  ({self.aspect})")
        res_lbl.setStyleSheet("color:#6c7086; font-size:11px;")
        res_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        canvas_l.addWidget(res_lbl)

        self.canvas = ThemeCanvas(
            res_w=self.res_w, res_h=self.res_h,
            theme_data=self.theme_data)
        canvas_l.addWidget(self.canvas, 1)
        main_layout.addWidget(canvas_container, 1)

    # ── Property tabs ─────────────────────────────────────────────────────────

    def _build_text_props(self):
        w    = QWidget()
        form = QFormLayout(w)
        form.setSpacing(6)

        self.p_font = QFontComboBox()
        self.p_font.currentFontChanged.connect(self._update_canvas)
        form.addRow("Font:", self.p_font)

        self.p_size = QSpinBox()
        self.p_size.setRange(12, 200)
        self.p_size.setValue(48)
        self.p_size.valueChanged.connect(self._update_canvas)
        form.addRow("Mărime:", self.p_size)

        style_row = QHBoxLayout()
        self.p_bold      = QCheckBox("B")
        self.p_bold.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.p_italic    = QCheckBox("I")
        self.p_italic.setFont(QFont("Arial", 10, QFont.Weight.Normal, True))
        self.p_uppercase = QCheckBox("AA")
        for cb in (self.p_bold, self.p_italic, self.p_uppercase):
            cb.stateChanged.connect(self._update_canvas)
            style_row.addWidget(cb)
        form.addRow("Stil:", style_row)

        self.p_color = ColorButton("#ffffff")
        self.p_color.colorChanged.connect(self._update_canvas)
        form.addRow("Culoare:", self.p_color)

        shadow_row = QHBoxLayout()
        self.p_shadow = QCheckBox("Umbră text")
        self.p_shadow.setChecked(True)
        self.p_shadow.stateChanged.connect(self._update_canvas)
        shadow_row.addWidget(self.p_shadow)
        self.p_shadow_color = ColorButton("#000000")
        self.p_shadow_color.colorChanged.connect(self._update_canvas)
        shadow_row.addWidget(self.p_shadow_color)
        form.addRow("Shadow:", shadow_row)

        outline_row = QHBoxLayout()
        self.p_outline_w = QSpinBox()
        self.p_outline_w.setRange(0, 10)
        self.p_outline_w.setValue(2)
        self.p_outline_w.valueChanged.connect(self._update_canvas)
        self.p_outline_color = ColorButton("#000000")
        self.p_outline_color.colorChanged.connect(self._update_canvas)
        outline_row.addWidget(self.p_outline_w)
        outline_row.addWidget(self.p_outline_color)
        form.addRow("Outline:", outline_row)

        self.p_spacing = QDoubleSpinBox()
        self.p_spacing.setRange(1.0, 3.0)
        self.p_spacing.setSingleStep(0.1)
        self.p_spacing.setValue(1.4)
        self.p_spacing.valueChanged.connect(self._update_canvas)
        form.addRow("Spațiere:", self.p_spacing)

        # Alignment buttons
        align_row = QHBoxLayout()
        self.p_align_left   = QPushButton(t("align_left"))
        self.p_align_center = QPushButton(t("align_center"))
        self.p_align_right  = QPushButton(t("align_right"))
        self.p_align_center.setCheckable(True)
        self.p_align_center.setChecked(True)
        _align_grp = QButtonGroup(self)
        for _ab in (self.p_align_left, self.p_align_center, self.p_align_right):
            _ab.setCheckable(True)
            _align_grp.addButton(_ab)
            _ab.toggled.connect(self._update_canvas)
            _ab.setStyleSheet("padding:4px 8px; font-size:10px;")
            align_row.addWidget(_ab)
        self.p_align_center.setChecked(True)
        form.addRow("Aliniere:", align_row)

        # ── Jesus Words group ─────────────────────────────────────────────────
        jesus_grp = QGroupBox("Cuvintele lui Isus")
        jf = QFormLayout(jesus_grp)
        jf.setSpacing(5)

        self.p_jesus_enabled = QCheckBox("Activat")
        self.p_jesus_enabled.stateChanged.connect(self._update_canvas)
        jf.addRow("", self.p_jesus_enabled)

        self.p_jesus_color = ColorButton("#ff6b6b")
        self.p_jesus_color.colorChanged.connect(self._update_canvas)
        jf.addRow("Culoare:", self.p_jesus_color)

        jstyle_row = QHBoxLayout()
        self.p_jesus_bold   = QCheckBox("Bold")
        self.p_jesus_italic = QCheckBox("Italic")
        self.p_jesus_italic.setChecked(True)
        for cb in (self.p_jesus_bold, self.p_jesus_italic):
            cb.stateChanged.connect(self._update_canvas)
            jstyle_row.addWidget(cb)
        jstyle_row.addStretch()
        jf.addRow("Stil:", jstyle_row)

        self.p_jesus_size_offset = QSpinBox()
        self.p_jesus_size_offset.setRange(-20, 20)
        self.p_jesus_size_offset.setValue(0)
        self.p_jesus_size_offset.setSuffix(" px")
        self.p_jesus_size_offset.valueChanged.connect(self._update_canvas)
        jf.addRow("Offset mărime:", self.p_jesus_size_offset)

        form.addRow(jesus_grp)

        # ── Advanced Bible reference group ────────────────────────────────────
        ref_grp = QGroupBox("Referință Biblie avansată")
        rf = QFormLayout(ref_grp)
        rf.setSpacing(5)

        self.p_ref_font = QFontComboBox()
        self.p_ref_font.currentFontChanged.connect(self._update_canvas)
        rf.addRow("Font:", self.p_ref_font)

        self.p_ref_size = QSpinBox()
        self.p_ref_size.setRange(8, 80)
        self.p_ref_size.setValue(24)
        self.p_ref_size.valueChanged.connect(self._update_canvas)
        rf.addRow("Mărime:", self.p_ref_size)

        ref_style_row = QHBoxLayout()
        self.p_ref_bold   = QCheckBox("Bold")
        self.p_ref_italic = QCheckBox("Italic")
        for cb in (self.p_ref_bold, self.p_ref_italic):
            cb.stateChanged.connect(self._update_canvas)
            ref_style_row.addWidget(cb)
        ref_style_row.addStretch()
        rf.addRow("Stil:", ref_style_row)

        self.p_ref_color = ColorButton("#aaaaaa")
        self.p_ref_color.colorChanged.connect(self._update_canvas)
        rf.addRow("Culoare text:", self.p_ref_color)

        self.p_ref_bg_enabled = QCheckBox("Fundal referință")
        self.p_ref_bg_enabled.stateChanged.connect(self._update_canvas)
        rf.addRow("", self.p_ref_bg_enabled)

        self.p_ref_bg_color = ColorButton("#99000000")
        self.p_ref_bg_color.colorChanged.connect(self._update_canvas)
        rf.addRow("Culoare fundal:", self.p_ref_bg_color)

        self.p_ref_padding = QSpinBox()
        self.p_ref_padding.setRange(0, 40)
        self.p_ref_padding.setValue(8)
        self.p_ref_padding.setSuffix(" px")
        rf.addRow("Padding:", self.p_ref_padding)

        self.p_ref_uppercase = QCheckBox("Majuscule")
        self.p_ref_uppercase.stateChanged.connect(self._update_canvas)
        rf.addRow("", self.p_ref_uppercase)

        ref_show_row = QHBoxLayout()
        self.p_ref_show_book    = QCheckBox("Carte")
        self.p_ref_show_chapter = QCheckBox("Capitol")
        self.p_ref_show_verse   = QCheckBox("Verset")
        for cb in (self.p_ref_show_book, self.p_ref_show_chapter, self.p_ref_show_verse):
            cb.setChecked(True)
            cb.stateChanged.connect(self._update_canvas)
            ref_show_row.addWidget(cb)
        ref_show_row.addStretch()
        rf.addRow("Afișează:", ref_show_row)

        self.p_ref_format = QComboBox()
        self.p_ref_format.addItems([
            "Ioan 3:16",
            "Ioan 3,16",
            "Jn 3:16",
            "3:16 Ioan",
            "Ioan 3:16",
        ])
        self.p_ref_format.currentIndexChanged.connect(self._update_canvas)
        rf.addRow("Format:", self.p_ref_format)

        form.addRow(ref_grp)

        # ── Text Box Background ────────────────────────────────────────────────
        tb_grp = QGroupBox("Fundal text (FreeShow-style)")
        tb_grp.setCheckable(False)
        tf = QFormLayout(tb_grp)
        tf.setSpacing(4)

        self.p_textbox_enabled = QCheckBox("Activat")
        self.p_textbox_enabled.stateChanged.connect(self._update_canvas)
        tf.addRow("", self.p_textbox_enabled)

        self.p_textbox_color = ColorButton("#000000")
        self.p_textbox_color.colorChanged.connect(self._update_canvas)
        tf.addRow("Culoare:", self.p_textbox_color)

        self.p_textbox_opacity = QSlider(Qt.Orientation.Horizontal)
        self.p_textbox_opacity.setRange(0, 100)
        self.p_textbox_opacity.setValue(60)
        self.p_textbox_opacity.valueChanged.connect(self._update_canvas)
        tf.addRow("Opacitate:", self.p_textbox_opacity)

        pad_row = QHBoxLayout()
        self.p_textbox_pad_h = QSpinBox(); self.p_textbox_pad_h.setRange(0, 80)
        self.p_textbox_pad_h.setValue(20); self.p_textbox_pad_h.setSuffix(" px")
        self.p_textbox_pad_h.valueChanged.connect(self._update_canvas)
        self.p_textbox_pad_v = QSpinBox(); self.p_textbox_pad_v.setRange(0, 80)
        self.p_textbox_pad_v.setValue(12); self.p_textbox_pad_v.setSuffix(" px")
        self.p_textbox_pad_v.valueChanged.connect(self._update_canvas)
        pad_row.addWidget(QLabel("H:")); pad_row.addWidget(self.p_textbox_pad_h)
        pad_row.addWidget(QLabel("V:")); pad_row.addWidget(self.p_textbox_pad_v)
        tf.addRow("Padding:", pad_row)

        self.p_textbox_radius = QSpinBox(); self.p_textbox_radius.setRange(0, 50)
        self.p_textbox_radius.setValue(8); self.p_textbox_radius.setSuffix(" px")
        self.p_textbox_radius.valueChanged.connect(self._update_canvas)
        tf.addRow("Rază colț:", self.p_textbox_radius)

        self.p_textbox_fit = QComboBox()
        self.p_textbox_fit.addItems(["Per linie", "Bloc complet", "Lățime completă"])
        self.p_textbox_fit.currentIndexChanged.connect(self._update_canvas)
        tf.addRow("Fit:", self.p_textbox_fit)

        self.p_textbox_style = QComboBox()
        self.p_textbox_style.addItems(
            ["solid", "gradient", "outline", "frosted", "shadow", "underline", "sketch"])
        self.p_textbox_style.currentIndexChanged.connect(self._update_canvas)
        tf.addRow("Stil:", self.p_textbox_style)

        self.p_textbox_color2 = ColorButton("#1a1a1a")
        self.p_textbox_color2.colorChanged.connect(self._update_canvas)
        tf.addRow("Culoare 2:", self.p_textbox_color2)

        form.addRow(tb_grp)

        # ── Echo: big faint text behind (concert "ghost lyric" look) ──────────
        echo_grp = QGroupBox("Text ecou (text mare în spate)")
        ef = QFormLayout(echo_grp)
        ef.setSpacing(4)
        self.p_echo_enabled = QCheckBox("Activat")
        self.p_echo_enabled.stateChanged.connect(self._update_canvas)
        ef.addRow("", self.p_echo_enabled)
        self.p_echo_scale = QDoubleSpinBox()
        self.p_echo_scale.setRange(1.2, 5.0); self.p_echo_scale.setSingleStep(0.1)
        self.p_echo_scale.setValue(2.2)
        self.p_echo_scale.valueChanged.connect(self._update_canvas)
        ef.addRow("Scară:", self.p_echo_scale)
        self.p_echo_opacity = QSlider(Qt.Orientation.Horizontal)
        self.p_echo_opacity.setRange(2, 60); self.p_echo_opacity.setValue(12)
        self.p_echo_opacity.valueChanged.connect(self._update_canvas)
        ef.addRow("Opacitate:", self.p_echo_opacity)
        self.p_echo_color = ColorButton("#ffffff")
        self.p_echo_color.colorChanged.connect(self._update_canvas)
        ef.addRow("Culoare:", self.p_echo_color)
        form.addRow(echo_grp)

        # ── Cascade: text repeated, centre highlighted (concert look, photo 2) ─
        casc_grp = QGroupBox("Mod cascadă (text repetat, linie centrală evidențiată)")
        cf = QFormLayout(casc_grp)
        cf.setSpacing(4)
        self.p_casc_enabled = QCheckBox("Activat")
        self.p_casc_enabled.stateChanged.connect(self._update_canvas)
        cf.addRow("", self.p_casc_enabled)
        self.p_casc_lines = QSpinBox()
        self.p_casc_lines.setRange(3, 9); self.p_casc_lines.setSingleStep(2)
        self.p_casc_lines.setValue(5)
        self.p_casc_lines.valueChanged.connect(self._update_canvas)
        cf.addRow("Copii:", self.p_casc_lines)
        self.p_casc_gap = QDoubleSpinBox()
        self.p_casc_gap.setRange(0.8, 2.5); self.p_casc_gap.setSingleStep(0.05)
        self.p_casc_gap.setValue(1.15)
        self.p_casc_gap.valueChanged.connect(self._update_canvas)
        cf.addRow("Spațiere:", self.p_casc_gap)
        self.p_casc_hl_color = ColorButton("#ffffff")
        self.p_casc_hl_color.colorChanged.connect(self._update_canvas)
        cf.addRow("Culoare centru:", self.p_casc_hl_color)
        self.p_casc_dim_opacity = QSlider(Qt.Orientation.Horizontal)
        self.p_casc_dim_opacity.setRange(5, 80); self.p_casc_dim_opacity.setValue(30)
        self.p_casc_dim_opacity.valueChanged.connect(self._update_canvas)
        cf.addRow("Opac. secundare:", self.p_casc_dim_opacity)
        self.p_casc_glow = QCheckBox("Glow pe centru")
        self.p_casc_glow.stateChanged.connect(self._update_canvas)
        cf.addRow("", self.p_casc_glow)
        form.addRow(casc_grp)

        # ── Extra "wow" widgets (added to the Stiluri speciale section) ───────
        self.p_chaos_enabled = QCheckBox("Activat")
        self.p_chaos_enabled.stateChanged.connect(self._update_canvas)
        self.p_chaos_amp = QDoubleSpinBox()
        self.p_chaos_amp.setRange(0.0, 0.2); self.p_chaos_amp.setSingleStep(0.005)
        self.p_chaos_amp.setValue(0.04); self.p_chaos_amp.setDecimals(3)
        self.p_chaos_amp.valueChanged.connect(self._update_canvas)
        self.p_chaos_speed = QDoubleSpinBox()
        self.p_chaos_speed.setRange(0.1, 4.0); self.p_chaos_speed.setSingleStep(0.1)
        self.p_chaos_speed.setValue(1.0)
        self.p_chaos_speed.valueChanged.connect(self._update_canvas)

        self.p_tcolor_type = QComboBox()
        self.p_tcolor_type.addItems(["solid", "gradient", "animated"])
        self.p_tcolor_type.currentIndexChanged.connect(self._update_canvas)
        self.p_tgrad_from = ColorButton("#ffffff")
        self.p_tgrad_from.colorChanged.connect(self._update_canvas)
        self.p_tgrad_to = ColorButton("#9ec5ff")
        self.p_tgrad_to.colorChanged.connect(self._update_canvas)

        self.p_glow_enabled = QCheckBox("Activat")
        self.p_glow_enabled.stateChanged.connect(self._update_canvas)
        self.p_glow_color = ColorButton("#5294e2")
        self.p_glow_color.colorChanged.connect(self._update_canvas)
        self.p_glow_size = QSpinBox()
        self.p_glow_size.setRange(2, 80); self.p_glow_size.setValue(26)
        self.p_glow_size.valueChanged.connect(self._update_canvas)

        return w

    def _build_bg_props(self):
        w      = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(6)

        layout.addWidget(QLabel(t("background") + ":"))
        self.bg_type_combo = QComboBox()
        self.bg_type_combo.addItems([
            t("solid_color"),               # 0
            t("gradient"),                  # 1
            t("image"),                     # 2
            t("video"),                     # 3
            t("camera"),                    # 4
            t("camera_gradient"),           # 5
            t("transparent"),               # 6
            f"🌊 {t('animated_gradient')}", # 7
            "🎨 Fundal animat (custom)",    # 8
        ])
        self.bg_type_combo.currentIndexChanged.connect(self._on_bg_type)
        layout.addWidget(self.bg_type_combo)

        self.bg_stack = QStackedWidget()

        # 0: Solid color
        cw = QWidget(); cl = QFormLayout(cw)
        self.bg_color = ColorButton("#000000")
        self.bg_color.colorChanged.connect(self._update_canvas)
        cl.addRow("Culoare:", self.bg_color)
        self.bg_stack.addWidget(cw)

        # 1: Gradient
        gw = QWidget(); gl = QFormLayout(gw)
        self.bg_gc1  = ColorButton("#000033")
        self.bg_gc2  = ColorButton("#000000")
        self.bg_gdir = QComboBox()
        self.bg_gdir.addItems(
            ["Sus→Jos", "Stânga→Dreapta", "Diagonal", "Radial"])
        for w_ in (self.bg_gc1, self.bg_gc2):
            w_.colorChanged.connect(self._update_canvas)
        self.bg_gdir.currentIndexChanged.connect(self._update_canvas)
        gl.addRow("Culoare 1:", self.bg_gc1)
        gl.addRow("Culoare 2:", self.bg_gc2)
        gl.addRow("Direcție:",  self.bg_gdir)
        self.bg_stack.addWidget(gw)

        # 2: Image
        iw = QWidget(); il = QFormLayout(iw)
        img_row = QHBoxLayout()
        self.bg_img_path = QLabel(t("none_selected"))
        self.bg_img_path.setStyleSheet("color:#6c7086; font-size:10px;")
        img_browse = QPushButton("…"); img_browse.setFixedWidth(30)
        img_browse.clicked.connect(self._browse_bg_img)
        img_row.addWidget(self.bg_img_path, 1)
        img_row.addWidget(img_browse)
        il.addRow("Fișier:", img_row)
        self.bg_img_op = QSlider(Qt.Orientation.Horizontal)
        self.bg_img_op.setRange(0, 100); self.bg_img_op.setValue(85)
        self.bg_img_op.valueChanged.connect(self._update_canvas)
        il.addRow("Opacitate:", self.bg_img_op)
        self.bg_stack.addWidget(iw)

        # 3: Video
        vw = QWidget(); vl = QFormLayout(vw)
        vid_row = QHBoxLayout()
        self.bg_vid_path = QLabel(t("no_video"))
        self.bg_vid_path.setStyleSheet("color:#6c7086; font-size:10px;")
        vid_browse = QPushButton("…"); vid_browse.setFixedWidth(30)
        vid_browse.clicked.connect(self._browse_bg_vid)
        vid_row.addWidget(self.bg_vid_path, 1)
        vid_row.addWidget(vid_browse)
        vl.addRow("Fișier:", vid_row)
        self.bg_stack.addWidget(vw)

        # 4: Cameră — the camera is chosen globally in Media → Feeds, so the theme
        # just says "use the camera" (no per-theme picker / OpenCV probing here).
        camw = QWidget(); caml = QFormLayout(camw)
        self.bg_cam_combo = QComboBox(); self.bg_cam_combo.hide()  # kept for save/load compat
        cam_info = QLabel("📷 Fundalul folosește camera activă.\n"
                          "Alege sau schimbă camera din: Media → Feeds.")
        cam_info.setWordWrap(True)
        cam_info.setStyleSheet("color:#9399b2; font-size:11px;")
        self.bg_cam_op = QSlider(Qt.Orientation.Horizontal)
        self.bg_cam_op.setRange(0, 100); self.bg_cam_op.setValue(100)
        self.bg_cam_op.valueChanged.connect(self._update_canvas)
        caml.addRow("", cam_info)
        caml.addRow("Opacitate:", self.bg_cam_op)
        self.bg_stack.addWidget(camw)

        # 5: Gradient + Cameră (camera still chosen in Media → Feeds)
        gcamw = QWidget(); gcaml = QFormLayout(gcamw)
        self.bg_gcam_combo = QComboBox(); self.bg_gcam_combo.hide()  # kept for compat
        gcam_info = QLabel("📷 Folosește camera activă din Media → Feeds.")
        gcam_info.setWordWrap(True)
        gcam_info.setStyleSheet("color:#9399b2; font-size:11px;")
        self.bg_gcam_color  = ColorButton("#000033")
        self.bg_gcam_color.colorChanged.connect(self._update_canvas)
        self.bg_gcam_op = QSlider(Qt.Orientation.Horizontal)
        self.bg_gcam_op.setRange(0, 100); self.bg_gcam_op.setValue(50)
        self.bg_gcam_op.valueChanged.connect(self._update_canvas)
        self.bg_gcam_dir = QComboBox()
        self.bg_gcam_dir.addItems(["Radial", "Sus→Jos", "Stânga→Dreapta"])
        self.bg_gcam_dir.currentIndexChanged.connect(self._update_canvas)
        gcaml.addRow("", gcam_info)
        gcaml.addRow("Culoare gradient:", self.bg_gcam_color)
        gcaml.addRow("Intensitate:", self.bg_gcam_op)
        gcaml.addRow("Direcție:", self.bg_gcam_dir)
        self.bg_stack.addWidget(gcamw)

        # 6: Transparent
        tw = QWidget(); tl = QVBoxLayout(tw)
        tl.addWidget(QLabel(t("transparent_bg_hint")))
        self.bg_stack.addWidget(tw)

        # 7: Animated Gradient
        agw = QWidget(); agl = QFormLayout(agw)
        self.bg_anim_colors = MultiColorPicker()
        self.bg_anim_colors.colorsChanged.connect(self._update_canvas)
        agl.addRow("Culori:", self.bg_anim_colors)

        self.bg_anim_speed = QDoubleSpinBox()
        self.bg_anim_speed.setRange(0.05, 5.0)
        self.bg_anim_speed.setSingleStep(0.05)
        self.bg_anim_speed.setValue(0.5)
        self.bg_anim_speed.valueChanged.connect(self._update_canvas)
        agl.addRow("Viteză:", self.bg_anim_speed)

        self.bg_stack.addWidget(agw)

        # 8: Custom animated background (from the Fundal tab)
        fw = QWidget(); fl = QFormLayout(fw)
        self.bg_fundal_combo = QComboBox()
        self._reload_fundal_list()
        self.bg_fundal_combo.currentIndexChanged.connect(self._update_canvas)
        refresh_fundal = QPushButton("🔄 Reîncarcă lista")
        refresh_fundal.clicked.connect(self._reload_fundal_list)
        fl.addRow("Fundal:", self.bg_fundal_combo)
        fl.addRow("", refresh_fundal)
        hint = QLabel("Fundalurile se creează în tab Media → Fundal.")
        hint.setStyleSheet("color:#6c7086; font-size:10px;")
        fl.addRow(hint)
        self.bg_stack.addWidget(fw)

        layout.addWidget(self.bg_stack, 1)
        return w

    def _fundal_dir(self) -> str:
        # Per-profile — must match media_tab._bg_dir() and background-editor.js
        # _bgFolder(), otherwise in-app backgrounds don't show up in this list.
        import os
        try:
            import database as _db
            prof = _db.get_active_profile() or "Default"
        except Exception:
            prof = "Default"
        base = os.path.join(os.path.expanduser("~"), "Cantio",
                            "profiles", prof, "backgrounds")
        os.makedirs(base, exist_ok=True)
        # One-time migration of any legacy global backgrounds into the active
        # profile (same guard as media_tab, safe if it already ran there).
        legacy = os.path.join(os.path.expanduser("~"), "Cantio", "backgrounds")
        try:
            if os.path.isdir(legacy) and not os.listdir(base):
                import shutil
                for fn in os.listdir(legacy):
                    src = os.path.join(legacy, fn)
                    if os.path.isfile(src):
                        try: shutil.move(src, os.path.join(base, fn))
                        except Exception: pass
        except Exception:
            pass
        return base

    def _reload_fundal_list(self):
        import os, json as _json
        if not hasattr(self, "bg_fundal_combo"):
            return
        cur = self.bg_fundal_combo.currentData()
        self.bg_fundal_combo.blockSignals(True)
        self.bg_fundal_combo.clear()
        self.bg_fundal_combo.addItem("— Niciunul —", "")
        try:
            for fn in sorted(os.listdir(self._fundal_dir())):
                if not fn.lower().endswith(".json"):
                    continue
                path = os.path.join(self._fundal_dir(), fn)
                name = fn[:-5]
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        name = _json.load(f).get("name", name)
                except Exception:
                    pass
                self.bg_fundal_combo.addItem(f"🎨 {name}", path)
        except Exception:
            pass
        if cur:
            i = self.bg_fundal_combo.findData(cur)
            if i >= 0:
                self.bg_fundal_combo.setCurrentIndex(i)
        self.bg_fundal_combo.blockSignals(False)

    def _detect_cameras(self):
        """Detect video input devices and populate the camera combo (slot 4)."""
        try:
            import cv2
            self.bg_cam_combo.clear()
            found = 0
            for i in range(5):
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    self.bg_cam_combo.addItem(f"Cameră {i}", str(i))
                    cap.release()
                    found += 1
            try:
                from toast_notifications import show_toast
                if found:
                    show_toast(f"✅ {found} camere detectate", "success")
                else:
                    show_toast("Nu s-au detectat camere", "warning")
            except Exception:
                pass
        except ImportError:
            try:
                from toast_notifications import show_toast
                show_toast("opencv-python lipsește — pip install opencv-python", "warning")
            except Exception:
                pass

    def _detect_cameras_for_gcam(self):
        """Detect video input devices and populate the gradient+camera combo (slot 5)."""
        try:
            import cv2
            self.bg_gcam_combo.clear()
            found = 0
            for i in range(5):
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    self.bg_gcam_combo.addItem(f"Cameră {i}", str(i))
                    cap.release()
                    found += 1
            try:
                from toast_notifications import show_toast
                if found:
                    show_toast(f"✅ {found} camere detectate", "success")
                else:
                    show_toast("Nu s-au detectat camere", "warning")
            except Exception:
                pass
        except ImportError:
            try:
                from toast_notifications import show_toast
                show_toast("opencv-python lipsește — pip install opencv-python", "warning")
            except Exception:
                pass

    def _build_layout_props(self):
        w    = QWidget()
        form = QFormLayout(w)
        form.setSpacing(6)

        self.l_margin = QSpinBox()
        self.l_margin.setRange(0, 400); self.l_margin.setValue(80)
        self.l_margin.valueChanged.connect(self._update_canvas)
        form.addRow("Margine:", self.l_margin)

        self.l_valign = QComboBox()
        self.l_valign.addItems(["Sus", "Centru", "Jos"])
        self.l_valign.setCurrentIndex(1)
        self.l_valign.currentIndexChanged.connect(self._update_canvas)
        form.addRow("V-Align:", self.l_valign)

        if self.theme_data.get("type") in ("bible", "both"):
            bg = QGroupBox("Zone Biblie")
            bf = QFormLayout(bg)

            def _sb(val: int) -> QSpinBox:
                sb = QSpinBox()
                sb.setRange(0, 100); sb.setSuffix("%"); sb.setValue(val)
                sb.valueChanged.connect(self._update_canvas)
                return sb

            self.l_vx = _sb(10); self.l_vy = _sb(20)
            self.l_vw = _sb(80); self.l_vh = _sb(50)
            self.l_rx = _sb(60); self.l_ry = _sb(75)
            self.l_rw = _sb(35); self.l_rh = _sb(15)

            for lbl, sb in [
                ("Verset X%:", self.l_vx), ("Verset Y%:", self.l_vy),
                ("Verset W%:", self.l_vw), ("Verset H%:", self.l_vh),
                ("Ref X%:",    self.l_rx), ("Ref Y%:",    self.l_ry),
                ("Ref W%:",    self.l_rw), ("Ref H%:",    self.l_rh),
            ]:
                bf.addRow(lbl, sb)

            self.l_ref_size = QSpinBox()
            self.l_ref_size.setRange(8, 80); self.l_ref_size.setValue(24)
            self.l_ref_size.valueChanged.connect(self._update_canvas)
            bf.addRow("Ref size:", self.l_ref_size)

            self.l_ref_color = ColorButton("#aaaaaa")
            self.l_ref_color.colorChanged.connect(self._update_canvas)
            bf.addRow("Ref color:", self.l_ref_color)

            form.addRow(bg)

        return w

    def _build_overlay_props(self):
        w    = QWidget()
        form = QFormLayout(w)
        form.setSpacing(6)

        self.o_transition = QComboBox()
        populate_transition_combo(self.o_transition, TRANSITIONS)
        self.o_transition.setCurrentText("fade")
        self.o_transition.currentIndexChanged.connect(self._update_canvas)
        form.addRow("Tranziție:", self.o_transition)

        self.o_duration = QSpinBox()
        self.o_duration.setRange(50, 2000)
        self.o_duration.setValue(350)
        self.o_duration.setSuffix(" ms")
        form.addRow("Durată:", self.o_duration)

        return w

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_bg_type(self, idx: int):
        self.bg_stack.setCurrentIndex(idx)
        self._update_canvas()

    def _browse_bg_img(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Imagine fundal", "",
            "Imagini (*.jpg *.jpeg *.png *.webp)")
        if path:
            self.bg_img_path.setText(path)
            self._update_canvas()

    def _browse_bg_vid(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Video fundal", "",
            "Video (*.mp4 *.mov *.avi *.mkv)")
        if path:
            self.bg_vid_path.setText(path)
            self._update_canvas()

    def _collect_theme(self) -> dict:
        d = dict(self.theme_data)

        _align = ("left"   if getattr(self, "p_align_left",   None) and self.p_align_left.isChecked()
                  else "right" if getattr(self, "p_align_right",  None) and self.p_align_right.isChecked()
                  else "center")
        d["text"] = {
            "font_family":    self.p_font.currentFont().family(),
            "font_size":      str(self.p_size.value()),
            "font_bold":      "true" if self.p_bold.isChecked()      else "false",
            "font_italic":    "true" if self.p_italic.isChecked()    else "false",
            "uppercase":      "true" if self.p_uppercase.isChecked() else "false",
            "text_color":     self.p_color.color(),
            "text_shadow":    "true" if self.p_shadow.isChecked()    else "false",
            "shadow_color":   getattr(self.p_shadow_color, 'color', lambda: "#000000")(),
            "outline_width":  str(self.p_outline_w.value()),
            "outline_color":  self.p_outline_color.color(),
            "line_spacing":   str(self.p_spacing.value()),
            "text_align":     _align,
            "echo_enabled":   "true" if self.p_echo_enabled.isChecked() else "false",
            "echo_scale":     str(self.p_echo_scale.value()),
            "echo_opacity":   str(self.p_echo_opacity.value() / 100.0),
            "echo_color":     self.p_echo_color.color(),
            "cascade_enabled":     "true" if self.p_casc_enabled.isChecked() else "false",
            "cascade_lines":       str(self.p_casc_lines.value()),
            "cascade_gap":         str(self.p_casc_gap.value()),
            "cascade_hl_color":    self.p_casc_hl_color.color(),
            "cascade_dim_opacity": str(self.p_casc_dim_opacity.value() / 100.0),
            "cascade_glow":        "true" if self.p_casc_glow.isChecked() else "false",
            "chaos_enabled":  "true" if self.p_chaos_enabled.isChecked() else "false",
            "chaos_amp":      str(self.p_chaos_amp.value()),
            "chaos_speed":    str(self.p_chaos_speed.value()),
            "color_type":     self.p_tcolor_type.currentText(),
            "grad_from":      self.p_tgrad_from.color(),
            "grad_to":        self.p_tgrad_to.color(),
            "glow_enabled":   "true" if self.p_glow_enabled.isChecked() else "false",
            "glow_color":     self.p_glow_color.color(),
            "glow_size":      str(self.p_glow_size.value()),
        }

        # Jesus Words styling
        d["jesus_words"] = {
            "enabled":     self.p_jesus_enabled.isChecked(),
            "color":       self.p_jesus_color.color(),
            "italic":      self.p_jesus_italic.isChecked(),
            "bold":        self.p_jesus_bold.isChecked(),
            "size_offset": self.p_jesus_size_offset.value(),
        }

        # Text box background settings
        tb_fit_map = {0: "per_line", 1: "full_block", 2: "full_width"}
        d["text_box"] = {
            "enabled":   self.p_textbox_enabled.isChecked(),
            "color":     self.p_textbox_color.color(),
            "opacity":   self.p_textbox_opacity.value() / 100.0,
            "padding_h": self.p_textbox_pad_h.value(),
            "padding_v": self.p_textbox_pad_v.value(),
            "radius":    self.p_textbox_radius.value(),
            "fit":       tb_fit_map.get(self.p_textbox_fit.currentIndex(), "per_line"),
            "style":     self.p_textbox_style.currentText(),
            "color2":    self.p_textbox_color2.color(),
        }

        bg_types = ["color", "gradient", "image", "video", "camera", "camera_gradient",
                    "transparent", "animated_gradient", "fundal"]
        bg_idx   = self.bg_type_combo.currentIndex()
        bg_type  = bg_types[min(bg_idx, len(bg_types) - 1)]

        d["background"] = {
            "type":        bg_type,
            "color":       self.bg_color.color(),
            "image":       self.bg_img_path.text() if bg_type == "image" else "",
            "video":       self.bg_vid_path.text() if bg_type == "video" else "",
            "opacity":     str(self.bg_img_op.value() / 100.0),
            "grad_color1": self.bg_gc1.color(),
            "grad_color2": self.bg_gc2.color(),
            "grad_dir":    self.bg_gdir.currentText(),
        }

        # Camera background
        if bg_type == "camera":
            cam_id = self.bg_cam_combo.currentData()
            d["background"]["camera_id"] = str(cam_id) if cam_id is not None else "0"
            d["background"]["opacity"]   = str(self.bg_cam_op.value() / 100.0)

        # Gradient + Camera background
        elif bg_type == "camera_gradient":
            gcam_id = self.bg_gcam_combo.currentData()
            d["background"]["camera_id"]    = str(gcam_id) if gcam_id is not None else "0"
            d["background"]["grad_color"]   = self.bg_gcam_color.color()
            d["background"]["grad_opacity"] = str(self.bg_gcam_op.value() / 100.0)
            d["background"]["grad_dir"]     = self.bg_gcam_dir.currentText()

        # Animated gradient
        elif bg_type == "animated_gradient":
            d["background"]["anim_colors"] = self.bg_anim_colors.colors()
            d["background"]["anim_speed"]  = str(self.bg_anim_speed.value())

        # Custom animated background (from the Fundal tab)
        elif bg_type == "fundal":
            d["background"]["fundal_file"] = self.bg_fundal_combo.currentData() or ""

        d["layout"] = {
            "margin": str(self.l_margin.value()),
            "valign": self.l_valign.currentText(),
            "reference": {
                "font":         self.p_ref_font.currentFont().family(),
                "size":         self.p_ref_size.value(),
                "bold":         self.p_ref_bold.isChecked(),
                "italic":       self.p_ref_italic.isChecked(),
                "color":        self.p_ref_color.color(),
                "bg_enabled":   self.p_ref_bg_enabled.isChecked(),
                "bg_color":     self.p_ref_bg_color.color(),
                "padding":      self.p_ref_padding.value(),
                "uppercase":    self.p_ref_uppercase.isChecked(),
                "show_book":    self.p_ref_show_book.isChecked(),
                "show_chapter": self.p_ref_show_chapter.isChecked(),
                "show_verse":   self.p_ref_show_verse.isChecked(),
                "format":       self.p_ref_format.currentIndex(),
            },
        }
        if hasattr(self, "l_vx"):
            d["layout"]["verse_zone"] = {
                "x": self.l_vx.value(), "y": self.l_vy.value(),
                "w": self.l_vw.value(), "h": self.l_vh.value(),
            }
            d["layout"]["ref_zone"] = {
                "x": self.l_rx.value(), "y": self.l_ry.value(),
                "w": self.l_rw.value(), "h": self.l_rh.value(),
            }
            d["layout"]["ref_font_size"] = self.l_ref_size.value()
            d["layout"]["ref_color"]     = self.l_ref_color.color()

        d["advanced"] = {
            "transition":          self.o_transition.currentText(),
            "transition_duration": str(self.o_duration.value()),
        }
        return d

    def _update_canvas(self):
        self.canvas.update_theme(self._collect_theme())

    def _save_theme(self):
        self.theme_saved.emit(self.theme_name, self._collect_theme())

    def _load_theme(self):
        t  = self.theme_data.get("text",       {})
        bg = self.theme_data.get("background", {})
        a  = self.theme_data.get("advanced",   {})
        l  = self.theme_data.get("layout",     {})

        if t.get("font_family"):
            self.p_font.setCurrentFont(QFont(t["font_family"]))
        try:
            if t.get("font_size"):    self.p_size.setValue(int(t["font_size"]))
        except (ValueError, TypeError): pass
        self.p_bold.setChecked(t.get("font_bold")    == "true")
        self.p_italic.setChecked(t.get("font_italic") == "true")
        self.p_uppercase.setChecked(t.get("uppercase") == "true")
        self.p_echo_enabled.setChecked(t.get("echo_enabled") == "true")
        try:
            if t.get("echo_scale"):   self.p_echo_scale.setValue(float(t["echo_scale"]))
            if t.get("echo_opacity"): self.p_echo_opacity.setValue(int(float(t["echo_opacity"]) * 100))
        except (ValueError, TypeError): pass
        if t.get("echo_color"): self.p_echo_color.set_color(t["echo_color"])
        self.p_casc_enabled.setChecked(t.get("cascade_enabled") == "true")
        self.p_casc_glow.setChecked(t.get("cascade_glow") == "true")
        try:
            if t.get("cascade_lines"):       self.p_casc_lines.setValue(int(t["cascade_lines"]))
            if t.get("cascade_gap"):         self.p_casc_gap.setValue(float(t["cascade_gap"]))
            if t.get("cascade_dim_opacity"): self.p_casc_dim_opacity.setValue(int(float(t["cascade_dim_opacity"]) * 100))
        except (ValueError, TypeError): pass
        if t.get("cascade_hl_color"): self.p_casc_hl_color.set_color(t["cascade_hl_color"])
        self.p_chaos_enabled.setChecked(t.get("chaos_enabled") == "true")
        self.p_glow_enabled.setChecked(t.get("glow_enabled") == "true")
        try:
            if t.get("chaos_amp"):   self.p_chaos_amp.setValue(float(t["chaos_amp"]))
            if t.get("chaos_speed"): self.p_chaos_speed.setValue(float(t["chaos_speed"]))
            if t.get("glow_size"):   self.p_glow_size.setValue(int(float(t["glow_size"])))
        except (ValueError, TypeError): pass
        if t.get("color_type"): self.p_tcolor_type.setCurrentText(t["color_type"])
        if t.get("grad_from"):  self.p_tgrad_from.set_color(t["grad_from"])
        if t.get("grad_to"):    self.p_tgrad_to.set_color(t["grad_to"])
        if t.get("glow_color"): self.p_glow_color.set_color(t["glow_color"])
        self.p_shadow.setChecked(t.get("text_shadow", "true") == "true")
        if t.get("text_color"):    self.p_color.set_color(t["text_color"])
        if t.get("outline_color"): self.p_outline_color.set_color(t["outline_color"])
        try:
            if t.get("outline_width"): self.p_outline_w.setValue(int(t["outline_width"]))
            if t.get("line_spacing"):  self.p_spacing.setValue(float(t["line_spacing"]))
        except (ValueError, TypeError): pass

        # Jesus Words
        jw = self.theme_data.get("jesus_words", {})
        self.p_jesus_enabled.setChecked(bool(jw.get("enabled", False)))
        if jw.get("color"):        self.p_jesus_color.set_color(jw["color"])
        self.p_jesus_italic.setChecked(bool(jw.get("italic", True)))
        self.p_jesus_bold.setChecked(bool(jw.get("bold", False)))
        try:
            if jw.get("size_offset") is not None:
                self.p_jesus_size_offset.setValue(int(jw["size_offset"]))
        except (ValueError, TypeError): pass

        # Advanced Bible reference
        ref = self.theme_data.get("layout", {}).get("reference", {})
        if ref.get("font"):         self.p_ref_font.setCurrentFont(QFont(ref["font"]))
        try:
            if ref.get("size"):     self.p_ref_size.setValue(int(ref["size"]))
        except (ValueError, TypeError): pass
        self.p_ref_bold.setChecked(bool(ref.get("bold", False)))
        self.p_ref_italic.setChecked(bool(ref.get("italic", False)))
        if ref.get("color"):        self.p_ref_color.set_color(ref["color"])
        self.p_ref_bg_enabled.setChecked(bool(ref.get("bg_enabled", False)))
        if ref.get("bg_color"):     self.p_ref_bg_color.set_color(ref["bg_color"])
        try:
            if ref.get("padding") is not None:
                self.p_ref_padding.setValue(int(ref["padding"]))
        except (ValueError, TypeError): pass
        self.p_ref_uppercase.setChecked(bool(ref.get("uppercase", False)))
        self.p_ref_show_book.setChecked(bool(ref.get("show_book", True)))
        self.p_ref_show_chapter.setChecked(bool(ref.get("show_chapter", True)))
        self.p_ref_show_verse.setChecked(bool(ref.get("show_verse", True)))
        try:
            if ref.get("format") is not None:
                self.p_ref_format.setCurrentIndex(int(ref["format"]))
        except (ValueError, TypeError): pass

        # Text box settings
        tb = self.theme_data.get("text_box", {})
        self.p_textbox_enabled.setChecked(bool(tb.get("enabled", False)))
        if tb.get("color"):  self.p_textbox_color.set_color(tb["color"])
        try:
            if tb.get("opacity") is not None:
                self.p_textbox_opacity.setValue(int(float(tb["opacity"]) * 100))
            if tb.get("padding_h") is not None:
                self.p_textbox_pad_h.setValue(int(tb["padding_h"]))
            if tb.get("padding_v") is not None:
                self.p_textbox_pad_v.setValue(int(tb["padding_v"]))
            if tb.get("radius") is not None:
                self.p_textbox_radius.setValue(int(tb["radius"]))
        except (ValueError, TypeError): pass
        fit_rmap = {"per_line": 0, "full_block": 1, "full_width": 2}
        if tb.get("fit"): self.p_textbox_fit.setCurrentIndex(fit_rmap.get(tb["fit"], 0))
        if tb.get("style"):  self.p_textbox_style.setCurrentText(tb["style"])
        if tb.get("color2"): self.p_textbox_color2.set_color(tb["color2"])

        bg_map = {"color": 0, "gradient": 1, "image": 2,
                  "video": 3, "camera": 4, "camera_gradient": 5,
                  "transparent": 6, "animated_gradient": 7, "fundal": 8}
        self.bg_type_combo.setCurrentIndex(
            bg_map.get(bg.get("type", "color"), 0))
        if bg.get("fundal_file") and hasattr(self, "bg_fundal_combo"):
            i = self.bg_fundal_combo.findData(bg["fundal_file"])
            if i >= 0:
                self.bg_fundal_combo.setCurrentIndex(i)
        if bg.get("color"):       self.bg_color.set_color(bg["color"])
        if bg.get("image"):       self.bg_img_path.setText(bg["image"])
        if bg.get("grad_color1"): self.bg_gc1.set_color(bg["grad_color1"])
        if bg.get("grad_color2"): self.bg_gc2.set_color(bg["grad_color2"])
        if bg.get("grad_dir"):    self.bg_gdir.setCurrentText(bg["grad_dir"])
        try:
            if bg.get("opacity"):
                self.bg_img_op.setValue(int(float(bg["opacity"]) * 100))
        except (ValueError, TypeError): pass
        # Animated gradient
        if bg.get("anim_colors"): self.bg_anim_colors.set_colors(bg["anim_colors"])
        try:
            if bg.get("anim_speed"): self.bg_anim_speed.setValue(float(bg["anim_speed"]))
        except (ValueError, TypeError): pass

        if a.get("transition"):
            self.o_transition.setCurrentText(a["transition"])
        try:
            if a.get("transition_duration"):
                self.o_duration.setValue(int(a["transition_duration"]))
        except (ValueError, TypeError): pass

        try:
            if l.get("margin"):  self.l_margin.setValue(int(l["margin"]))
        except (ValueError, TypeError): pass
        if hasattr(self, "l_vx"):
            vz = l.get("verse_zone", {})
            if vz:
                self.l_vx.setValue(vz.get("x", 10)); self.l_vy.setValue(vz.get("y", 20))
                self.l_vw.setValue(vz.get("w", 80)); self.l_vh.setValue(vz.get("h", 50))
            rz = l.get("ref_zone", {})
            if rz:
                self.l_rx.setValue(rz.get("x", 60)); self.l_ry.setValue(rz.get("y", 75))
                self.l_rw.setValue(rz.get("w", 35)); self.l_rh.setValue(rz.get("h", 15))
            try:
                if l.get("ref_font_size"):
                    self.l_ref_size.setValue(int(l["ref_font_size"]))
            except (ValueError, TypeError): pass
            if l.get("ref_color"): self.l_ref_color.set_color(l["ref_color"])

        self._update_canvas()


# ── ThemeCanvas ────────────────────────────────────────────────────────────────

class ThemeCanvas(QWidget):
    """Canvas 1:1 cu ecranul proiectorului — scalat să încapă în editor."""

    def __init__(self, res_w: int = 1920, res_h: int = 1080,
                 theme_data: dict | None = None, parent=None):
        super().__init__(parent)
        self.res_w      = res_w
        self.res_h      = res_h
        self.theme_data = theme_data or {}
        self.setMinimumSize(400, 225)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding)
        # Repaint timer for live effects in the preview (chaos / animated colour)
        self._fx_timer = QTimer(self)
        self._fx_timer.setInterval(33)   # ~30 fps
        self._fx_timer.timeout.connect(self.update)

    @staticmethod
    def _mix_qcolor(a: QColor, b: QColor, t: float) -> QColor:
        return QColor(
            int(a.red()   + (b.red()   - a.red())   * t),
            int(a.green() + (b.green() - a.green()) * t),
            int(a.blue()  + (b.blue()  - a.blue())  * t),
        )

    def update_theme(self, theme_data: dict):
        self.theme_data = theme_data
        tx = theme_data.get("text", {})
        live_fx = (tx.get("chaos_enabled") == "true"
                   or tx.get("color_type") == "animated"
                   or theme_data.get("background", {}).get("type") == "animated_gradient")
        if live_fx and not self._fx_timer.isActive():
            self._fx_timer.start()
        elif not live_fx and self._fx_timer.isActive():
            self._fx_timer.stop()
        self.update()

    def _scale(self) -> float:
        return min(self.width() / self.res_w, self.height() / self.res_h)

    def _canvas_rect(self) -> tuple[int, int, int, int, float]:
        s  = self._scale()
        cw = int(self.res_w * s)
        ch = int(self.res_h * s)
        x  = (self.width()  - cw) // 2
        y  = (self.height() - ch) // 2
        return x, y, cw, ch, s

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w = self.width()
        h = self.height()
        painter.fillRect(0, 0, w, h, QColor("#0a0a14"))

        x, y, cw, ch, scale = self._canvas_rect()

        # ── Draw the whole slide in real projector coordinates (W×H) and let
        #    the painter transform scale it down. This makes every number
        #    (font size, margin, padding…) identical to display.js. ──────────
        W, H = self.res_w, self.res_h
        painter.save()
        painter.setClipRect(x, y, cw, ch)
        painter.translate(x, y)
        painter.scale(scale, scale)

        theme   = self.theme_data
        bg      = theme.get("background", {})
        t       = theme.get("text",       {})
        l       = theme.get("layout",     {})
        t_type  = theme.get("type", "songs")

        self._paint_background(painter, bg, W, H)

        if t_type == "bible":
            verse = ("Fiindcă Dumnezeu așa a iubit lumea, "
                     "că a dat pe singurul Lui Fiu...")
            self._paint_text_block(painter, t, l, verse, W, H)
            self._paint_reference(painter, l, W, H)
        else:
            song = "Doamne, Tu ești lumina mea\nȘi mântuirea mea"
            self._paint_text_block(painter, t, l, song, W, H)

        painter.restore()

        # ── Canvas border + resolution label (widget space) ──────────────────
        painter.setPen(QPen(QColor("#45475a"), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(x, y, cw, ch)
        painter.setPen(QColor("#6c7086"))
        painter.setFont(QFont("Arial", 9))
        painter.drawText(x, y + ch + 14, f"{self.res_w}×{self.res_h}")

        painter.end()

    # ── Background (mirrors display.js drawFrame background block) ──────────────

    def _paint_background(self, painter: QPainter, bg: dict, W: int, H: int):
        bg_type = bg.get("type", "color")

        if bg_type == "transparent":
            csz = 64
            for cy in range(0, H, csz):
                for cx in range(0, W, csz):
                    col = QColor("#888888") if (cx // csz + cy // csz) % 2 == 0 \
                          else QColor("#666666")
                    painter.fillRect(cx, cy, csz, csz, col)
            return

        if bg_type == "gradient" or bg_type == "camera_gradient":
            c1   = QColor(bg.get("grad_color1", bg.get("grad_color", "#000033")))
            c2   = QColor(bg.get("grad_color2", "#000000"))
            gdir = bg.get("grad_dir", "Sus→Jos")
            if gdir == "Radial":
                grad = QRadialGradient(W / 2, H / 2, max(W, H) / 2)
            elif "Stânga" in gdir or "Left" in gdir:
                grad = QLinearGradient(0, 0, W, 0)
            elif "Diagonal" in gdir:
                grad = QLinearGradient(0, 0, W, H)
            else:
                grad = QLinearGradient(0, 0, 0, H)
            grad.setColorAt(0, c1)
            grad.setColorAt(1, c2)
            if bg_type == "camera_gradient":
                # camera feed is a live element; show dark base then gradient overlay
                painter.fillRect(0, 0, W, H, QColor("#101015"))
                painter.setOpacity(float(bg.get("grad_opacity", 0.5)))
                painter.fillRect(0, 0, W, H, QBrush(grad))
                painter.setOpacity(1.0)
                self._paint_source_badge(painter, "📷  CAMERĂ + GRADIENT", W, H)
            else:
                painter.fillRect(0, 0, W, H, QBrush(grad))
            return

        if bg_type == "animated_gradient":
            self._paint_animated_gradient(painter, bg, W, H)
            return

        if bg_type in ("video", "camera"):
            painter.fillRect(0, 0, W, H, QColor("#0c0c12"))
            label = "▶  VIDEO" if bg_type == "video" else "📷  CAMERĂ"
            extra = bg.get("video", "") if bg_type == "video" else ""
            self._paint_source_badge(painter, label, W, H, sub=os.path.basename(extra))
            return

        # Solid color (+ optional image overlay)
        painter.fillRect(0, 0, W, H, QColor(bg.get("color", "#000000")))
        bg_img = bg.get("image", "")
        if bg_img and os.path.exists(bg_img):
            pix = QPixmap(bg_img)
            if not pix.isNull():
                painter.setOpacity(float(bg.get("opacity", 0.85)))
                painter.drawPixmap(
                    0, 0,
                    pix.scaled(W, H,
                               Qt.AspectRatioMode.IgnoreAspectRatio,
                               Qt.TransformationMode.SmoothTransformation))
                painter.setOpacity(1.0)

    def _paint_animated_gradient(self, painter: QPainter, bg: dict, W: int, H: int):
        """Static snapshot of the animated multi-radial gradient (mirrors
        display.js renderAnimatedGradient at a fixed phase)."""
        import math
        colors = bg.get("anim_colors") or ['#1a237e', '#6a1b9a', '#0d47a1']
        painter.fillRect(0, 0, W, H, QColor("#000000"))
        painter.save()
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_Screen)
        n = max(1, len(colors))
        for idx, col in enumerate(colors):
            phase = idx * (math.pi * 2 / n)
            cx = W * (0.3 + 0.4 * math.sin(phase * 0.7))
            cy = H * (0.3 + 0.4 * math.cos(phase * 0.5))
            radius = max(W, H) * (0.4 + 0.2 * math.sin(phase * 1.3))
            grad = QRadialGradient(cx, cy, max(1.0, radius))
            c = QColor(col)
            grad.setColorAt(0, c)
            transparent = QColor(c); transparent.setAlpha(0)
            grad.setColorAt(1, transparent)
            painter.fillRect(0, 0, W, H, QBrush(grad))
        painter.restore()

    def _paint_source_badge(self, painter: QPainter, text: str,
                            W: int, H: int, sub: str = ""):
        painter.save()
        f = QFont("Segoe UI", int(H * 0.05)); f.setBold(True)
        painter.setFont(f)
        painter.setPen(QColor(255, 255, 255, 60))
        painter.drawText(QRect(0, 0, W, H),
                         Qt.AlignmentFlag.AlignCenter, text)
        if sub:
            f2 = QFont("Segoe UI", int(H * 0.026)); painter.setFont(f2)
            painter.setPen(QColor(255, 255, 255, 45))
            painter.drawText(QRect(0, int(H * 0.56), W, int(H * 0.1)),
                             Qt.AlignmentFlag.AlignHCenter |
                             Qt.AlignmentFlag.AlignTop, sub)
        painter.restore()

    # ── Helpers shared with the live renderer (display.js parity) ───────────────

    @staticmethod
    def _resolve_margin(raw, W: int, H: int) -> int:
        try:
            rawf = float(raw)
        except (TypeError, ValueError):
            rawf = 0.06
        return round(min(W, H) * rawf) if rawf < 2 else int(rawf)

    @staticmethod
    def _smart_wrap(raw_line: str, max_w: float, fm: QFontMetrics) -> list[str]:
        """Balanced word-wrap — port of display.js smartWordWrap."""
        if not raw_line or not raw_line.strip():
            return [raw_line or ""]
        tokens = raw_line.split()
        if len(tokens) <= 1:
            return [raw_line]
        full = " ".join(tokens)
        if fm.horizontalAdvance(full) <= max_w:
            return [full]

        best_split, best_score = None, float("inf")
        for i in range(1, len(tokens)):
            l1 = " ".join(tokens[:i])
            l2 = " ".join(tokens[i:])
            w1 = fm.horizontalAdvance(l1)
            if w1 > max_w:
                continue
            w2 = fm.horizontalAdvance(l2)
            penalty = 0
            if i == 1:                 penalty += 2000
            if len(tokens) - i == 1:   penalty += 2000
            if w2 > max_w:             penalty += 1000
            last = tokens[i - 1]
            if   last.endswith(","): penalty -= 800
            elif last.endswith(";"): penalty -= 600
            elif last.endswith(":"): penalty -= 400
            score = abs(w1 - w2) + penalty
            if score < best_score:
                best_score, best_split = score, i

        if best_split is None:
            best_split = max(1, len(tokens) // 2)
        l1 = " ".join(tokens[:best_split])
        l2 = " ".join(tokens[best_split:])
        result = [l1]
        if fm.horizontalAdvance(l2) > max_w:
            result.extend(ThemeCanvas._smart_wrap(l2, max_w, fm))
        else:
            result.append(l2)
        return result

    def _paint_text_block(self, painter: QPainter, t: dict, l: dict,
                          demo_text: str, W: int, H: int):
        """Port of display.js drawText — centered, auto-shrink, align, valign,
        outline, shadow and FreeShow text-box background."""
        family   = t.get("font_family", "Arial")
        size     = int(t.get("font_size", 48))
        bold     = t.get("font_bold",   "true") == "true"
        italic   = t.get("font_italic", "false") == "true"
        color    = QColor(t.get("text_color", "#ffffff"))
        shadow   = t.get("text_shadow", "true") != "false"
        shadow_c = QColor(t.get("shadow_color", "#000000"))
        out_w    = int(t.get("outline_width", 0) or 0)
        out_c    = QColor(t.get("outline_color", "#000000"))
        lsp      = float(t.get("line_spacing", 1.4))
        margin   = self._resolve_margin(l.get("margin", 0.06), W, H)
        uppercase = t.get("uppercase", "false") == "true"

        display_text = demo_text.upper() if uppercase else demo_text
        max_w = W - margin * 2
        max_h = H - margin * 2

        # ── Auto-shrink loop (mirror of the JS while loop) ───────────────────
        cur = size
        lines: list[str] = []
        line_h = 0.0
        total_h = 0.0
        while cur >= 10:
            font = QFont(family); font.setPixelSize(cur)
            font.setBold(bold); font.setItalic(italic)
            fm = QFontMetrics(font)
            lines = []
            for raw in display_text.split("\n"):
                if not raw.strip():
                    lines.append("")
                    continue
                for wl in self._smart_wrap(raw, max_w, fm):
                    if fm.horizontalAdvance(wl) <= max_w:
                        lines.append(wl)
                    else:
                        part = ""
                        for chx in wl:
                            if fm.horizontalAdvance(part + chx) > max_w:
                                if part:
                                    lines.append(part)
                                part = chx
                            else:
                                part += chx
                        if part:
                            lines.append(part)
            line_h = cur * lsp
            total_h = line_h * len(lines)
            max_line_w = max((fm.horizontalAdvance(x) for x in lines), default=0)
            if total_h <= max_h and max_line_w <= max_w:
                break
            cur -= 2

        font = QFont(family); font.setPixelSize(cur)
        font.setBold(bold); font.setItalic(italic)
        fm = QFontMetrics(font)
        painter.setFont(font)

        # ── Vertical alignment ───────────────────────────────────────────────
        valign = l.get("valign", "Centru")
        v = str(valign).lower()
        if v in ("sus", "top"):
            start_y = margin + cur * 0.85
        elif v in ("jos", "bottom"):
            start_y = H - margin - total_h + cur * 0.85
        else:
            start_y = (H - total_h) / 2 + cur * 0.85

        # ── Horizontal alignment ──────────────────────────────────────────────
        align = t.get("text_align", "center")
        if align == "left":
            base_x = margin
        elif align == "right":
            base_x = W - margin
        else:
            base_x = W / 2

        # ── Echo: big faint text behind (concert "ghost lyric" look) ──────────
        if t.get("echo_enabled") == "true":
            try:
                escale = float(t.get("echo_scale", 2.2))
                eop    = float(t.get("echo_opacity", 0.12))
            except (ValueError, TypeError):
                escale, eop = 2.2, 0.12
            efs = max(8, int(cur * escale))
            efont = QFont(family); efont.setPixelSize(efs)
            efont.setBold(bold); efont.setItalic(italic)
            efm = QFontMetrics(efont)
            ec = QColor(t.get("echo_color", color.name()))
            ec.setAlphaF(max(0.0, min(1.0, eop)))
            elh = efs * 1.05
            ey0 = H / 2 - ((len(lines) - 1) * elh) / 2
            painter.save()
            painter.setFont(efont)
            for i, line in enumerate(lines):
                if not line:
                    continue
                ew = efm.horizontalAdvance(line)
                epath = QPainterPath()
                epath.addText(float((W - ew) / 2),
                              float(ey0 + i * elh + efm.ascent() / 2),
                              efont, line)
                painter.fillPath(epath, ec)
            painter.restore()

        # ── Cascade mode (repeated text, centre highlighted) ──────────────────
        if t.get("cascade_enabled") == "true":
            self._paint_cascade(painter, t, lines, family, bold, italic,
                                cur, line_h, W, H)
            return

        # ── Text box background ───────────────────────────────────────────────
        tb = self.theme_data.get("text_box", {})
        if tb.get("enabled"):
            self._paint_text_box(painter, tb, lines, fm, line_h, start_y,
                                 cur, align, base_x, W)

        # ── Chaotic movement (animated via the editor's repaint timer) ────────
        chaos_dx = chaos_dy = 0.0
        if t.get("chaos_enabled") == "true":
            import math, time
            ct = time.monotonic()
            amp = float(t.get("chaos_amp", 0.04) or 0.04) * min(W, H)
            csp = float(t.get("chaos_speed", 1.0) or 1.0)
            chaos_dx = (math.sin(ct * csp * 1.7) + math.sin(ct * csp * 3.3)) * amp * 0.5
            chaos_dy = (math.cos(ct * csp * 1.3) + math.sin(ct * csp * 2.1)) * amp * 0.5

        # Text fill: solid / gradient / animated
        ctype = t.get("color_type", "solid")

        def _fill_for(ly_top, ly_bot):
            if ctype not in ("gradient", "animated"):
                return color
            frm = QColor(t.get("grad_from", "#ffffff"))
            to  = QColor(t.get("grad_to", "#9ec5ff"))
            if ctype == "animated":
                import time as _t2
                k = (1 + __import__("math").sin(_t2.monotonic() * 0.6)) / 2
                frm, to = self._mix_qcolor(frm, to, k), self._mix_qcolor(to, frm, k)
            g = QLinearGradient(0, ly_top, 0, ly_bot)
            g.setColorAt(0, frm); g.setColorAt(1, to)
            return QBrush(g)

        painter.save()
        if chaos_dx or chaos_dy:
            painter.translate(chaos_dx, chaos_dy)
        for i, line in enumerate(lines):
            if not line:
                continue
            lw = fm.horizontalAdvance(line)
            if align == "left":
                lx = base_x
            elif align == "right":
                lx = base_x - lw
            else:
                lx = base_x - lw / 2
            ly = start_y + i * line_h

            path = QPainterPath()
            path.addText(float(lx), float(ly), font, line)

            if shadow:
                painter.save()
                sc = QColor(shadow_c); sc.setAlpha(217)
                painter.translate(3, 3)
                painter.fillPath(path, sc)
                painter.restore()

            if out_w > 0:
                pen = QPen(out_c, out_w * 2)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.strokePath(path, pen)

            painter.fillPath(path, _fill_for(ly - cur * 0.85, ly + cur * 0.2))
        painter.restore()

    def _paint_cascade(self, painter, t, lines, family, bold, italic,
                       size, line_h, W, H):
        """Mirror of display.js _drawCascadeText — repeated text, centre line bright."""
        try:
            copies = max(3, int(t.get("cascade_lines", 5)))
            gap    = float(t.get("cascade_gap", 1.15))
            dim_op = float(t.get("cascade_dim_opacity", 0.30))
        except (ValueError, TypeError):
            copies, gap, dim_op = 5, 1.15, 0.30
        hl_color  = QColor(t.get("cascade_hl_color", "#ffffff"))
        dim_color = QColor(t.get("cascade_dim_color", t.get("text_color", "#ffffff")))
        glow      = t.get("cascade_glow") == "true"
        half      = copies // 2
        block_h   = max(1, len(lines)) * line_h
        copy_gap  = block_h * gap

        for c in range(-half, half + 1):
            dist = abs(c)
            is_center = (c == 0)
            op = 1.0 if is_center else dim_op * (1 - dist / (half + 1))
            if op <= 0.01:
                continue
            sc = 1.0 if is_center else (1 - dist * 0.05)
            fs = max(8, int(size * sc))
            font = QFont(family); font.setPixelSize(fs)
            font.setBold(bold); font.setItalic(italic)
            fm2 = QFontMetrics(font)
            col = QColor(hl_color if is_center else dim_color)
            col.setAlphaF(max(0.0, min(1.0, op)))
            clh = line_h * sc
            cy  = H / 2 + c * copy_gap
            y0  = cy - ((len(lines) - 1) * clh) / 2 + fs * 0.34
            painter.save()
            painter.setFont(font)
            for i, line in enumerate(lines):
                if not line:
                    continue
                lw = fm2.horizontalAdvance(line)
                path = QPainterPath()
                path.addText(float((W - lw) / 2), float(y0 + i * clh), font, line)
                painter.fillPath(path, col)
            painter.restore()

    def _paint_box_rect(self, painter, x, y, w, h, radius, style, color, color2, opacity):
        """Paint one text-box rect in the chosen style (mirrors display.js)."""
        painter.save()
        painter.setOpacity(opacity)
        rect = QRectF(x, y, w, h)
        if style == "gradient":
            g = QLinearGradient(x, y, x, y + h)
            g.setColorAt(0, color); g.setColorAt(1, color2)
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QBrush(g))
            painter.drawRoundedRect(rect, radius, radius)
        elif style == "outline":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(color, max(2, h * 0.045)))
            painter.drawRoundedRect(rect, radius, radius)
        elif style == "frosted":
            painter.setOpacity(opacity * 0.5)
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QBrush(color))
            painter.drawRoundedRect(rect, radius, radius)
            painter.setOpacity(opacity * 0.9)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(255, 255, 255, 90), max(1, h * 0.02)))
            painter.drawRoundedRect(rect, radius, radius)
        elif style == "shadow":
            sh = QColor(0, 0, 0, 140)
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QBrush(sh))
            painter.drawRoundedRect(QRectF(x, y + h * 0.06, w, h), radius, radius)
            painter.setBrush(QBrush(color))
            painter.drawRoundedRect(rect, radius, radius)
        elif style == "underline":
            bh = max(3, h * 0.10)
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QBrush(color))
            painter.drawRoundedRect(QRectF(x, y + h - bh, w, bh), bh / 2, bh / 2)
        elif style == "sketch":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            pen = QPen(color, max(2, h * 0.04))
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawRoundedRect(rect, radius, radius)
            painter.setOpacity(opacity * 0.6)
            painter.drawRoundedRect(QRectF(x + 2.5, y - 2, w, h), radius + 3, radius + 3)
        else:  # solid
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QBrush(color))
            painter.drawRoundedRect(rect, radius, radius)
        painter.restore()

    def _paint_text_box(self, painter, tb, lines, fm, line_h, start_y,
                        cur, align, base_x, W):
        """Port of display.js drawTextBox (with styles)."""
        box_color  = QColor(tb.get("color", "#000000"))
        box_color2 = QColor(tb.get("color2", "#1a1a1a"))
        opacity    = float(tb.get("opacity", 0.6))
        pad_h      = int(tb.get("padding_h", 20))
        pad_v      = int(tb.get("padding_v", 12))
        radius     = int(tb.get("radius", 8))
        fit        = tb.get("fit", "per_line")
        style      = tb.get("style", "solid")

        def paint(x, y, w, h, r):
            self._paint_box_rect(painter, x, y, w, h, r, style,
                                 box_color, box_color2, opacity)

        real_lines = [ln for ln in lines if ln]
        if fit == "full_block":
            max_lw = max((fm.horizontalAdvance(ln) for ln in real_lines), default=0)
            if align == "left":
                bx = base_x - pad_h
            elif align == "right":
                bx = base_x - max_lw - pad_h
            else:
                bx = base_x - max_lw / 2 - pad_h
            by = start_y - cur * 0.85 - pad_v
            paint(bx, by, max_lw + pad_h * 2, line_h * len(real_lines) + pad_v * 2, radius)
        elif fit == "full_width":
            for i, line in enumerate(lines):
                if not line:
                    continue
                by = start_y + i * line_h - cur * 0.85 - pad_v
                paint(0, by, W, cur + pad_v * 2, 0)
        else:  # per_line
            for i, line in enumerate(lines):
                if not line:
                    continue
                lw = fm.horizontalAdvance(line)
                if align == "left":
                    bx = base_x - pad_h
                elif align == "right":
                    bx = base_x - lw - pad_h
                else:
                    bx = base_x - lw / 2 - pad_h
                by = start_y + i * line_h - cur * 0.85 - pad_v
                paint(bx, by, lw + pad_h * 2, cur + pad_v * 2, radius)

    def _paint_reference(self, painter: QPainter, l: dict, W: int, H: int):
        """Port of display.js drawReference (+ advanced styling)."""
        ref_cfg = l.get("reference", {})
        family  = (self.theme_data.get("text", {}).get("font_family")
                   or "Arial")
        size    = int(ref_cfg.get("size", l.get("ref_font_size", 24)) or 24)
        color   = QColor(ref_cfg.get("color", l.get("ref_color", "#aaaaaa")))
        bold    = bool(ref_cfg.get("bold", False))
        italic  = bool(ref_cfg.get("italic", False))
        upper   = bool(ref_cfg.get("uppercase", False))

        # Build demo reference text honoring show flags & format
        show_b = ref_cfg.get("show_book", True)
        show_c = ref_cfg.get("show_chapter", True)
        show_v = ref_cfg.get("show_verse", True)
        fmt    = int(ref_cfg.get("format", 0) or 0)
        book, chap, vers = "Ioan", "3", "16"
        sep = "," if fmt == 1 else ":"
        cv = ""
        if show_c:
            cv = chap
            if show_v:
                cv += sep + vers
        elif show_v:
            cv = vers
        if fmt == 2:
            book = "Jn"
        if fmt == 3:  # "3:16 Ioan"
            ref_text = (cv + (" " + book if show_b else "")).strip()
        else:
            ref_text = ((book + " " if show_b else "") + cv).strip()
        if upper:
            ref_text = ref_text.upper()
        if not ref_text:
            ref_text = "Ioan 3:16"

        font = QFont(family); font.setPixelSize(max(6, size))
        font.setBold(bold); font.setItalic(italic)
        painter.setFont(font)
        fm = QFontMetrics(font)
        margin = self._resolve_margin(l.get("margin", 0.06), W, H)

        rz = l.get("ref_zone")
        tw = fm.horizontalAdvance(ref_text)
        th = fm.height()

        if rz and isinstance(rz, dict):
            rx = rz.get("x", 60) / 100 * W
            ry = rz.get("y", 75) / 100 * H
            rw = rz.get("w", 35) / 100 * W
            rh = rz.get("h", 15) / 100 * H
            tx = rx + rw - tw            # right aligned
            ty = ry + rh / 2 + fm.ascent() / 2 - fm.descent() / 2
        else:
            tx = W - margin - tw
            ty = H - margin

        # Optional background box behind reference
        if ref_cfg.get("bg_enabled"):
            pad = int(ref_cfg.get("padding", 8))
            bg_c = QColor(ref_cfg.get("bg_color", "#99000000"))
            painter.save()
            painter.setBrush(QBrush(bg_c))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(
                QRectF(tx - pad, ty - fm.ascent() - pad,
                       tw + pad * 2, th + pad * 2), 6, 6)
            painter.restore()

        # Shadow + text
        path = QPainterPath()
        path.addText(float(tx), float(ty), font, ref_text)
        painter.save()
        sc = QColor(0, 0, 0, 200)
        painter.translate(2, 2)
        painter.fillPath(path, sc)
        painter.restore()
        painter.fillPath(path, color)
