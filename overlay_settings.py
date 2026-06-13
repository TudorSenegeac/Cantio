"""
Cantio - Overlay Settings Widget
Personalizare avansată pentru Ticker, Ceas și Timer.
Embeddable as a QWidget inside SettingsDialog's Overlays tab.
"""
from __future__ import annotations
import json

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QGroupBox,
    QFormLayout, QLabel, QPushButton, QCheckBox, QComboBox,
    QSpinBox, QDoubleSpinBox, QSlider, QColorDialog, QSizePolicy,
    QFileDialog, QLineEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont


_OVERLAY_DEFAULTS = {
    "ticker": {
        "font_family": "Segoe UI",
        "font_size": 14,
        "bold": False,
        "italic": False,
        "color": "#ffffff",
        "bg_color": "#000000cc",
        "bg_opacity": 85,
        "height": 40,
        "position": "bottom",
        "speed": 3,
        "prefix": "",
        "separator": "  ◆  ",
        "animation": "scroll_left",
        "border_color": "#333333",
        "border_width": 0,
    },
    "clock": {
        "font_family": "Segoe UI",
        "font_size": 16,
        "bold": True,
        "color": "#ffffff",
        "format": "HH:MM:SS",
        "show_date": False,
        "position": "top_right",
        "bg": "transparent",
        "padding": 8,
        "border_radius": 4,
        "shadow": True,
        "size_pct": 8,
    },
    "timer": {
        "font_family": "Segoe UI",
        "font_size": 32,
        "bold": True,
        "color": "#ffffff",
        "warning_color": "#ff8800",
        "finished_color": "#f44336",
        "flash_at_zero": True,
        "sound_at_zero": "none",
        "sound_file": "",
        "format": "MM:SS",
        "position": "center_top",
        "bg": "transparent",
        "finished_msg": "",
        "count_up": False,
    },
}


class _ColorButton(QPushButton):
    colorChanged = pyqtSignal(str)

    def __init__(self, color="#ffffff", parent=None):
        super().__init__(parent)
        self._color = color
        self._refresh()
        self.setFixedSize(52, 26)
        self.clicked.connect(self._pick)

    def _refresh(self):
        self.setStyleSheet(
            f"background:{self._color}; border:1px solid #555; border-radius:3px; padding:0;"
        )

    def _pick(self):
        c = QColorDialog.getColor(QColor(self._color), self)
        if c.isValid():
            self._color = c.name()
            self._refresh()
            self.colorChanged.emit(self._color)

    def color(self): return self._color

    def set_color(self, c):
        self._color = c
        self._refresh()


class OverlaySettingsWidget(QWidget):
    """Full overlay settings panel — embed inside a QDialog tab."""

    changed = pyqtSignal(dict)  # emitted when any value changes

    def __init__(self, current_settings: dict | None = None, parent=None):
        super().__init__(parent)
        self._s = dict(current_settings or {})
        raw = self._s.get("overlays")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = {}
        self._overlays = raw if isinstance(raw, dict) else {}
        for key, defaults in _OVERLAY_DEFAULTS.items():
            if key not in self._overlays:
                self._overlays[key] = {}
            for k, v in defaults.items():
                self._overlays[key].setdefault(k, v)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(self._build_ticker_tab(), "📢 Ticker")
        tabs.addTab(self._build_clock_tab(), "🕐 Ceas")
        tabs.addTab(self._build_timer_tab(), "⏱ Timer")
        layout.addWidget(tabs)

        preview_btn = QPushButton("👁 Previzualizează overlays")
        preview_btn.setStyleSheet(
            "QPushButton { background: #18283a; color: #5294e2; "
            "border: 1px solid #1c3a5a; border-radius: 5px; padding: 8px 18px; }"
            "QPushButton:hover { background: #1c3a5a; }"
        )
        preview_btn.clicked.connect(self._show_preview)
        layout.addWidget(preview_btn)

    # ── Ticker tab ────────────────────────────────────────────────────────────

    def _build_ticker_tab(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)

        tk = self._overlays["ticker"]

        grp_font = QGroupBox("Font")
        ff = QFormLayout(grp_font)

        from PyQt6.QtWidgets import QFontComboBox
        self._tk_font = QFontComboBox()
        self._tk_font.setCurrentFont(QFont(tk["font_family"]))
        ff.addRow("Familie:", self._tk_font)

        self._tk_size = QSpinBox()
        self._tk_size.setRange(8, 72)
        self._tk_size.setValue(tk["font_size"])
        ff.addRow("Size:", self._tk_size)

        row_style = QHBoxLayout()
        self._tk_bold = QCheckBox("Bold")
        self._tk_bold.setChecked(tk["bold"])
        self._tk_italic = QCheckBox("Italic")
        self._tk_italic.setChecked(tk["italic"])
        row_style.addWidget(self._tk_bold)
        row_style.addWidget(self._tk_italic)
        row_style.addStretch()
        ff.addRow("Stil:", row_style)
        l.addWidget(grp_font)

        grp_colors = QGroupBox("Culori")
        cf = QFormLayout(grp_colors)
        self._tk_color = _ColorButton(tk["color"])
        cf.addRow("Culoare text:", self._tk_color)
        self._tk_bg = _ColorButton(tk.get("bg_color", "#000000cc")[:7])
        cf.addRow("Fundal bar:", self._tk_bg)
        self._tk_opacity = QSlider(Qt.Orientation.Horizontal)
        self._tk_opacity.setRange(0, 100)
        self._tk_opacity.setValue(tk["bg_opacity"])
        cf.addRow("Opacitate fundal (%):", self._tk_opacity)
        l.addWidget(grp_colors)

        grp_layout = QGroupBox("Aspect")
        lf = QFormLayout(grp_layout)
        self._tk_height = QSpinBox()
        self._tk_height.setRange(30, 100)
        self._tk_height.setValue(tk["height"])
        lf.addRow("Înălțime (px):", self._tk_height)

        self._tk_pos = QComboBox()
        self._tk_pos.addItems(["bottom", "top"])
        self._tk_pos.setCurrentText(tk["position"])
        lf.addRow("Poziție:", self._tk_pos)

        self._tk_speed = QSpinBox()
        self._tk_speed.setRange(1, 10)
        self._tk_speed.setValue(tk["speed"])
        lf.addRow("Viteză:", self._tk_speed)

        self._tk_prefix = QLineEdit(tk["prefix"])
        lf.addRow("Prefix:", self._tk_prefix)

        self._tk_sep = QLineEdit(tk["separator"])
        lf.addRow("Separator:", self._tk_sep)

        self._tk_anim = QComboBox()
        self._tk_anim.addItems(["scroll_left", "scroll_right", "fade", "blink"])
        self._tk_anim.setCurrentText(tk["animation"])
        lf.addRow("Animație:", self._tk_anim)

        self._tk_border_color = _ColorButton(tk["border_color"])
        lf.addRow("Culoare bordură:", self._tk_border_color)
        self._tk_border_w = QSpinBox()
        self._tk_border_w.setRange(0, 5)
        self._tk_border_w.setValue(tk["border_width"])
        lf.addRow("Grosime bordură:", self._tk_border_w)

        l.addWidget(grp_layout)
        l.addStretch()
        return w

    # ── Clock tab ─────────────────────────────────────────────────────────────

    def _build_clock_tab(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)

        ck = self._overlays["clock"]

        grp_font = QGroupBox("Font")
        ff = QFormLayout(grp_font)
        from PyQt6.QtWidgets import QFontComboBox
        self._ck_font = QFontComboBox()
        self._ck_font.setCurrentFont(QFont(ck["font_family"]))
        ff.addRow("Familie:", self._ck_font)
        self._ck_size = QSpinBox()
        self._ck_size.setRange(8, 120)
        self._ck_size.setValue(ck["font_size"])
        ff.addRow("Size:", self._ck_size)
        self._ck_bold = QCheckBox("Bold")
        self._ck_bold.setChecked(ck["bold"])
        ff.addRow("", self._ck_bold)
        l.addWidget(grp_font)

        grp_format = QGroupBox("Format și aspect")
        gf = QFormLayout(grp_format)
        self._ck_color = _ColorButton(ck["color"])
        gf.addRow("Culoare:", self._ck_color)

        self._ck_format = QComboBox()
        self._ck_format.addItems([
            "HH:MM:SS", "HH:MM", "hh:MM AM/PM", "HH:MM:SS + Data",
        ])
        self._ck_format.setCurrentText(ck["format"])
        gf.addRow("Format timp:", self._ck_format)

        self._ck_show_date = QCheckBox("Afișează și data")
        self._ck_show_date.setChecked(ck["show_date"])
        gf.addRow("", self._ck_show_date)

        self._ck_pos = QComboBox()
        self._ck_pos.addItems([
            "top_right", "top_left", "bottom_right", "bottom_left",
            "center_top", "center_bottom",
        ])
        self._ck_pos.setCurrentText(ck["position"])
        gf.addRow("Poziție:", self._ck_pos)

        self._ck_padding = QSpinBox()
        self._ck_padding.setRange(0, 40)
        self._ck_padding.setValue(ck["padding"])
        gf.addRow("Padding:", self._ck_padding)

        self._ck_radius = QSpinBox()
        self._ck_radius.setRange(0, 20)
        self._ck_radius.setValue(ck["border_radius"])
        gf.addRow("Border radius:", self._ck_radius)

        self._ck_shadow = QCheckBox("Shadow")
        self._ck_shadow.setChecked(ck["shadow"])
        gf.addRow("", self._ck_shadow)

        self._ck_size_pct = QSpinBox()
        self._ck_size_pct.setRange(5, 20)
        self._ck_size_pct.setValue(ck["size_pct"])
        self._ck_size_pct.setSuffix("%")
        gf.addRow("Dimensiune relativă:", self._ck_size_pct)

        l.addWidget(grp_format)
        l.addStretch()
        return w

    # ── Timer tab ─────────────────────────────────────────────────────────────

    def _build_timer_tab(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)

        tm = self._overlays["timer"]

        grp_font = QGroupBox("Font")
        ff = QFormLayout(grp_font)
        from PyQt6.QtWidgets import QFontComboBox
        self._tm_font = QFontComboBox()
        self._tm_font.setCurrentFont(QFont(tm["font_family"]))
        ff.addRow("Familie:", self._tm_font)
        self._tm_size = QSpinBox()
        self._tm_size.setRange(12, 200)
        self._tm_size.setValue(tm["font_size"])
        ff.addRow("Size:", self._tm_size)
        self._tm_bold = QCheckBox("Bold")
        self._tm_bold.setChecked(tm["bold"])
        ff.addRow("", self._tm_bold)
        l.addWidget(grp_font)

        grp_colors = QGroupBox("Culori și comportament")
        cf = QFormLayout(grp_colors)
        self._tm_color = _ColorButton(tm["color"])
        cf.addRow("Culoare normal:", self._tm_color)
        self._tm_warn_color = _ColorButton(tm["warning_color"])
        cf.addRow("Culoare < 30s:", self._tm_warn_color)
        self._tm_fin_color = _ColorButton(tm["finished_color"])
        cf.addRow("Culoare la 0:", self._tm_fin_color)

        self._tm_flash = QCheckBox("Flash/blink la 0")
        self._tm_flash.setChecked(tm["flash_at_zero"])
        cf.addRow("", self._tm_flash)

        self._tm_sound = QComboBox()
        self._tm_sound.addItems(["none", "beep", "custom"])
        self._tm_sound.setCurrentText(tm["sound_at_zero"])
        cf.addRow("Sunet la 0:", self._tm_sound)

        sound_row = QHBoxLayout()
        self._tm_sound_file = QLineEdit(tm["sound_file"])
        self._tm_sound_file.setPlaceholderText("Fișier .wav/.mp3 (opțional)")
        sound_browse = QPushButton("Browse…")
        sound_browse.setFixedWidth(70)
        sound_browse.clicked.connect(self._pick_sound_file)
        sound_row.addWidget(self._tm_sound_file)
        sound_row.addWidget(sound_browse)
        cf.addRow("Fișier sunet:", sound_row)

        self._tm_format = QComboBox()
        self._tm_format.addItems(["MM:SS", "SS", "MM:SS.ms"])
        self._tm_format.setCurrentText(tm["format"])
        cf.addRow("Format:", self._tm_format)

        self._tm_pos = QComboBox()
        self._tm_pos.addItems([
            "center_top", "top_right", "top_left",
            "bottom_right", "bottom_left", "center_bottom",
        ])
        self._tm_pos.setCurrentText(tm["position"])
        cf.addRow("Poziție:", self._tm_pos)

        self._tm_finished_msg = QLineEdit(tm["finished_msg"])
        self._tm_finished_msg.setPlaceholderText('ex: "TIMP EXPIRAT!"')
        cf.addRow("Mesaj la final:", self._tm_finished_msg)

        self._tm_count_up = QCheckBox("Numără în sus (stopwatch)")
        self._tm_count_up.setChecked(tm["count_up"])
        cf.addRow("", self._tm_count_up)

        l.addWidget(grp_colors)

        # Preset buttons
        grp_presets = QGroupBox("Preset-uri rapide")
        pr = QHBoxLayout(grp_presets)
        for label_sec in (("1 min", 60), ("3 min", 180), ("5 min", 300),
                           ("10 min", 600), ("15 min", 900), ("30 min", 1800)):
            lbl, sec = label_sec
            btn = QPushButton(lbl)
            btn.setFixedWidth(56)
            btn.clicked.connect(lambda _, s=sec: self._set_timer_preset(s))
            pr.addWidget(btn)
        pr.addStretch()
        l.addWidget(grp_presets)
        l.addStretch()
        return w

    def _pick_sound_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selectează fișier sunet", "",
            "Audio (*.wav *.mp3)"
        )
        if path:
            self._tm_sound_file.setText(path)

    def _set_timer_preset(self, seconds: int):
        self.changed.emit({"_timer_preset_seconds": seconds})

    def _show_preview(self):
        """Open a simple 16:9 preview window showing overlay demo."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel
        dlg = QDialog(self)
        dlg.setWindowTitle("Previzualizare Overlays")
        dlg.setMinimumSize(640, 360)
        dlg.setStyleSheet("background:#000;")
        l = QVBoxLayout(dlg)
        lbl = QLabel(
            "Preview overlays\n\n"
            "🕐  23:45:01\n\n"
            "⏱  05:00\n\n"
            "📢  Ticker text derulant  ◆  Ticker text derulant  ◆"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color:#fff; font-size:16px;")
        l.addWidget(lbl)
        dlg.exec()

    def collect(self) -> dict:
        """Return updated overlays dict from current widget values."""
        tk = self._overlays["ticker"]
        tk["font_family"] = self._tk_font.currentFont().family()
        tk["font_size"] = self._tk_size.value()
        tk["bold"] = self._tk_bold.isChecked()
        tk["italic"] = self._tk_italic.isChecked()
        tk["color"] = self._tk_color.color()
        tk["bg_color"] = self._tk_bg.color()
        tk["bg_opacity"] = self._tk_opacity.value()
        tk["height"] = self._tk_height.value()
        tk["position"] = self._tk_pos.currentText()
        tk["speed"] = self._tk_speed.value()
        tk["prefix"] = self._tk_prefix.text()
        tk["separator"] = self._tk_sep.text()
        tk["animation"] = self._tk_anim.currentText()
        tk["border_color"] = self._tk_border_color.color()
        tk["border_width"] = self._tk_border_w.value()

        ck = self._overlays["clock"]
        ck["font_family"] = self._ck_font.currentFont().family()
        ck["font_size"] = self._ck_size.value()
        ck["bold"] = self._ck_bold.isChecked()
        ck["color"] = self._ck_color.color()
        ck["format"] = self._ck_format.currentText()
        ck["show_date"] = self._ck_show_date.isChecked()
        ck["position"] = self._ck_pos.currentText()
        ck["padding"] = self._ck_padding.value()
        ck["border_radius"] = self._ck_radius.value()
        ck["shadow"] = self._ck_shadow.isChecked()
        ck["size_pct"] = self._ck_size_pct.value()

        tm = self._overlays["timer"]
        tm["font_family"] = self._tm_font.currentFont().family()
        tm["font_size"] = self._tm_size.value()
        tm["bold"] = self._tm_bold.isChecked()
        tm["color"] = self._tm_color.color()
        tm["warning_color"] = self._tm_warn_color.color()
        tm["finished_color"] = self._tm_fin_color.color()
        tm["flash_at_zero"] = self._tm_flash.isChecked()
        tm["sound_at_zero"] = self._tm_sound.currentText()
        tm["sound_file"] = self._tm_sound_file.text()
        tm["format"] = self._tm_format.currentText()
        tm["position"] = self._tm_pos.currentText()
        tm["finished_msg"] = self._tm_finished_msg.text()
        tm["count_up"] = self._tm_count_up.isChecked()

        return {
            "ticker": dict(tk),
            "clock": dict(ck),
            "timer": dict(tm),
        }
