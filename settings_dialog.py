"""
Cantio - Settings Dialog
Display appearance, overlays, screen assignment, Supabase cloud, auto-advance.
"""
import os
import sys
import json
import threading
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QColorDialog, QFileDialog, QGroupBox, QSlider, QFontComboBox,
    QDialogButtonBox, QTabWidget, QWidget, QLineEdit, QScrollArea,
    QFrame, QApplication, QProgressBar, QListWidget, QListWidgetItem,
    QMessageBox, QTextEdit, QSplitter, QStackedWidget, QRadioButton,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QColor, QFont
import database as db
from preview_widget import PreviewWidget
from translations import t, available_languages, get_language


DIALOG_STYLE = """
QDialog, QWidget { background: #181818; color: #e0e0e0; font-family: 'Segoe UI'; }
QTabWidget::pane { border: 1px solid #242424; background: #1c1c1c; }
QTabBar { background: #111; }
QTabBar::tab {
    background: #111; color: #888; padding: 8px 18px;
    border: none; border-bottom: 2px solid transparent; font-size: 12px;
}
QTabBar::tab:selected { color: #e0e0e0; border-bottom: 2px solid #5294e2; background: #1c1c1c; }
QTabBar::tab:hover { color: #cccccc; background: #161616; }
QGroupBox {
    border: 1px solid #242424; border-radius: 6px;
    margin-top: 8px; padding: 12px 10px 10px 10px;
    color: #888; font-size: 10px; font-weight: 600; letter-spacing: 1px;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 10px; color: #5294e2;
    font-weight: 700; font-size: 10px; text-transform: uppercase;
}
QLabel { color: #cccccc; font-size: 12px; }
QLabel#section_lbl { color: #5294e2; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
QLineEdit, QTextEdit {
    background: #1c1c1c; color: #e0e0e0; border: 1px solid #262626;
    border-radius: 4px; padding: 5px 8px;
}
QLineEdit:focus, QTextEdit:focus { border-color: #5294e2; }
QComboBox, QSpinBox, QDoubleSpinBox, QFontComboBox {
    background: #1c1c1c; color: #e0e0e0; border: 1px solid #262626;
    border-radius: 4px; padding: 5px 8px;
}
QComboBox QAbstractItemView {
    background: #222; color: #e0e0e0; border: 1px solid #2e2e2e;
    selection-background-color: #1a3a5c;
}
QPushButton {
    background: #232323; color: #e0e0e0; border: 1px solid #2e2e2e;
    border-radius: 5px; padding: 6px 14px; font-size: 12px;
}
QPushButton:hover { background: #2a2a2a; border-color: #3a3a3a; }
QPushButton:pressed { background: #1a1a1a; }
QCheckBox { color: #e0e0e0; spacing: 6px; font-size: 12px; }
QCheckBox::indicator {
    width: 16px; height: 16px; border: 1px solid #333;
    border-radius: 3px; background: #1c1c1c;
}
QCheckBox::indicator:checked { background: #5294e2; border-color: #5294e2; }
QSlider::groove:horizontal { background: #2a2a2a; height: 4px; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #5294e2; width: 14px; height: 14px;
    border-radius: 7px; margin: -5px 0;
}
QSlider::sub-page:horizontal { background: #5294e2; border-radius: 2px; }
QScrollArea { border: none; }
QDialogButtonBox QPushButton { min-width: 80px; }
QProgressBar {
    background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 4px; height: 16px;
    text-align: center; color: #e0e0e0; font-size: 11px;
}
QProgressBar::chunk { background: #5294e2; border-radius: 3px; }
QListWidget { background: #1a1a1a; border: 1px solid #242424; border-radius: 4px; }
QListWidget::item { padding: 5px 8px; color: #ccc; }
QListWidget::item:hover { background: #222; }
QListWidget::item:selected { background: #1c3a5a; }
"""


class ColorButton(QPushButton):
    colorChanged = pyqtSignal(str)

    def __init__(self, color="#ffffff", parent=None):
        super().__init__(parent)
        self._color = color
        self._update_style()
        self.setFixedSize(48, 28)
        self.clicked.connect(self._pick)

    def _update_style(self):
        self.setStyleSheet(
            f"background-color: {self._color}; border: 1px solid #555; "
            f"border-radius: 4px; padding: 0;"
        )

    def _pick(self):
        c = QColorDialog.getColor(QColor(self._color), self, "Pick Color")
        if c.isValid():
            self._color = c.name()
            self._update_style()
            self.colorChanged.emit(self._color)

    def color(self):
        return self._color

    def set_color(self, c):
        self._color = c
        self._update_style()


class WindowPerSettingsDialog(QDialog):
    """
    Compact settings dialog for a single display window.
    Shows only the per-window overrides (text, color, background, transition).
    Fields left at global defaults are stored as empty and not applied per-window.
    """

    def __init__(self, parent=None, window_settings=None, global_settings=None):
        super().__init__(parent)
        self.setWindowTitle(t("settings"))
        self.setMinimumSize(540, 560)
        self.setStyleSheet(DIALOG_STYLE)
        self._global = dict(global_settings or db.get_settings())
        # Merge: start from global, apply per-window overrides
        merged = dict(self._global)
        merged.update(window_settings or {})
        self.result_settings: dict = {}
        self._build_ui(merged)

    def _build_ui(self, s):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        info = QLabel(
            "Setările de mai jos suprascriu setările globale DOAR pentru această fereastră.\n"
            "Lasă câmpurile neschimbate pentru a folosi valorile globale."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(info)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form_l = QVBoxLayout(inner)
        form_l.setSpacing(12)

        # ── Font ──────────────────────────────────────────────────────────────
        font_grp = QGroupBox(t("font"))
        ff = QFormLayout(font_grp)
        self.pw_font_combo = QFontComboBox()
        self.pw_font_combo.setCurrentFont(QFont(s.get("font_family", "Arial")))
        ff.addRow(t("font_family") + ":", self.pw_font_combo)

        self.pw_font_size = QSpinBox()
        self.pw_font_size.setRange(12, 200)
        self.pw_font_size.setValue(int(s.get("font_size", 48)))
        ff.addRow(t("size_pt") + ":", self.pw_font_size)

        style_row = QHBoxLayout()
        self.pw_bold = QCheckBox("Bold")
        self.pw_bold.setChecked(s.get("font_bold", "true") == "true")
        self.pw_italic = QCheckBox("Italic")
        self.pw_italic.setChecked(s.get("font_italic", "false") == "true")
        style_row.addWidget(self.pw_bold)
        style_row.addWidget(self.pw_italic)
        style_row.addStretch()
        ff.addRow(t("style") + ":", style_row)
        form_l.addWidget(font_grp)

        # ── Colors ────────────────────────────────────────────────────────────
        col_grp = QGroupBox(t("colors"))
        cf = QFormLayout(col_grp)
        self.pw_text_color = ColorButton(s.get("text_color", "#ffffff"))
        cf.addRow(t("text_color") + ":", self.pw_text_color)
        self.pw_outline_color = ColorButton(s.get("outline_color", "#000000"))
        self.pw_outline_width = QSpinBox()
        self.pw_outline_width.setRange(0, 10)
        self.pw_outline_width.setValue(int(s.get("outline_width", 2)))
        oc_row = QHBoxLayout()
        oc_row.addWidget(self.pw_outline_color)
        oc_row.addSpacing(8)
        oc_row.addWidget(QLabel(t("outline_width") + ":"))
        oc_row.addWidget(self.pw_outline_width)
        oc_row.addStretch()
        cf.addRow(t("outline") + ":", oc_row)
        self.pw_bg_color = ColorButton(s.get("bg_color", "#000000"))
        cf.addRow(t("solid_color") + ":", self.pw_bg_color)
        form_l.addWidget(col_grp)

        # ── Background image ──────────────────────────────────────────────────
        bg_grp = QGroupBox(t("background"))
        bgf = QFormLayout(bg_grp)
        img_row = QHBoxLayout()
        self.pw_bg_img = QLabel(s.get("bg_image", "") or "None")
        self.pw_bg_img.setStyleSheet("color:#666; font-size:11px;")
        img_browse = QPushButton(t("browse") + "…")
        img_browse.setFixedWidth(90)
        img_browse.clicked.connect(self._pick_image)
        img_clear = QPushButton(t("clear"))
        img_clear.setFixedWidth(70)
        img_clear.clicked.connect(lambda: self.pw_bg_img.setText("None"))
        img_row.addWidget(self.pw_bg_img, 1)
        img_row.addWidget(img_browse)
        img_row.addWidget(img_clear)
        bgf.addRow(t("image") + ":", img_row)
        self.pw_bg_opacity = QSlider(Qt.Orientation.Horizontal)
        self.pw_bg_opacity.setRange(0, 100)
        self.pw_bg_opacity.setValue(int(float(s.get("bg_opacity", 0.5)) * 100))
        bgf.addRow(t("opacity") + ":", self.pw_bg_opacity)
        form_l.addWidget(bg_grp)

        # ── Layout ────────────────────────────────────────────────────────────
        lay_grp = QGroupBox("Aspect text")
        lf = QFormLayout(lay_grp)
        self.pw_margin = QSpinBox()
        self.pw_margin.setRange(0, 400)
        self.pw_margin.setValue(int(s.get("margin", 60)))
        lf.addRow("Margine (px):", self.pw_margin)
        self.pw_line_spacing = QDoubleSpinBox()
        self.pw_line_spacing.setRange(1.0, 3.0)
        self.pw_line_spacing.setSingleStep(0.1)
        self.pw_line_spacing.setDecimals(1)
        self.pw_line_spacing.setValue(float(s.get("line_spacing", 1.4)))
        lf.addRow("Spațiere linii:", self.pw_line_spacing)
        self.pw_transition = QComboBox()
        self.pw_transition.addItems([
            "fade", "crossfade", "slide_left", "zoom_in", "instant"
        ])
        tidx = self.pw_transition.findText(s.get("transition", "fade"))
        if tidx >= 0:
            self.pw_transition.setCurrentIndex(tidx)
        lf.addRow("Tranziție:", self.pw_transition)

        self.pw_halign = QComboBox()
        self.pw_halign.addItems(["center", "left", "right"])
        hi = self.pw_halign.findText(s.get("text_align", "center"))
        if hi >= 0:
            self.pw_halign.setCurrentIndex(hi)
        lf.addRow("Aliniere H:", self.pw_halign)

        self.pw_valign = QComboBox()
        self.pw_valign.addItems(["center", "top", "bottom"])
        vi = self.pw_valign.findText(s.get("text_valign", "center"))
        if vi >= 0:
            self.pw_valign.setCurrentIndex(vi)
        lf.addRow("Aliniere V:", self.pw_valign)
        form_l.addWidget(lay_grp)

        # ── Overlays ──────────────────────────────────────────────────────────
        ov_grp = QGroupBox("Overlay-uri")
        ov_f = QFormLayout(ov_grp)
        self.pw_clock = QCheckBox("Afișează ceas")
        self.pw_clock.setChecked(s.get("clock_enabled", "false") == "true")
        ov_f.addRow("Ceas:", self.pw_clock)
        self.pw_ticker = QCheckBox("Afișează ticker")
        self.pw_ticker.setChecked(s.get("ticker_enabled", "false") == "true")
        ov_f.addRow("Ticker:", self.pw_ticker)
        form_l.addWidget(ov_grp)

        form_l.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)

        # Preview
        prev_lbl = QLabel("PREVIEW")
        prev_lbl.setObjectName("section_lbl")
        layout.addWidget(prev_lbl)
        self._preview = PreviewWidget()
        self._preview.apply_settings(s)
        self._preview.update_text("Doamne, Tu ești lumina mea\nȘi mântuirea mea")
        self._preview.setFixedHeight(120)
        layout.addWidget(self._preview)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._collect_and_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selectează imagine", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if path:
            self.pw_bg_img.setText(path)

    def _collect_and_accept(self):
        self.result_settings = {
            "font_family":    self.pw_font_combo.currentFont().family(),
            "font_size":      str(self.pw_font_size.value()),
            "font_bold":      "true" if self.pw_bold.isChecked() else "false",
            "font_italic":    "true" if self.pw_italic.isChecked() else "false",
            "text_color":     self.pw_text_color.color(),
            "outline_color":  self.pw_outline_color.color(),
            "outline_width":  str(self.pw_outline_width.value()),
            "bg_color":       self.pw_bg_color.color(),
            "bg_image":       self.pw_bg_img.text() if self.pw_bg_img.text() != "None" else "",
            "bg_opacity":     str(self.pw_bg_opacity.value() / 100.0),
            "margin":         str(self.pw_margin.value()),
            "line_spacing":   str(self.pw_line_spacing.value()),
            "transition":     self.pw_transition.currentText(),
            "text_align":     self.pw_halign.currentText(),
            "text_valign":    self.pw_valign.currentText(),
            "clock_enabled":  "true" if self.pw_clock.isChecked() else "false",
            "ticker_enabled": "true" if self.pw_ticker.isChecked() else "false",
        }
        self.accept()


class SettingsDialog(QDialog):
    settingsChanged = pyqtSignal(dict)

    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self.setWindowTitle(f"Cantio — {t('settings')}")
        self.setMinimumSize(860, 680)
        self.setStyleSheet(DIALOG_STYLE)
        self.s = current_settings or db.get_settings()
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Horizontal splitter: tabs (left) | preview (right) ────────────────
        h_splitter = QSplitter(Qt.Orientation.Horizontal)
        h_splitter.setHandleWidth(2)
        h_splitter.setChildrenCollapsible(False)

        # Left side: tabs in a scroll area
        tabs = QTabWidget()
        tabs.addTab(self._tab_display(), t("display"))
        tabs.addTab(self._tab_text(), t("text"))
        tabs.addTab(self._tab_overlays(), t("overlays"))
        tabs.addTab(self._tab_windows(), "🖥 Ferestre")
        tabs.addTab(self._tab_interface(), f"🌐 {t('interface_language')}")
        tabs.addTab(self._tab_supabase(), "Cloud ☁")
        tabs.addTab(self._tab_cloud_backup(), "💾 Backup")
        tabs.addTab(self._tab_database(), "🗄 Baza de date")
        tabs.addTab(self._tab_security(), "🔒 Securitate")
        tabs.setMinimumWidth(380)
        h_splitter.addWidget(tabs)

        # Right side: live preview panel
        preview_panel = QFrame()
        preview_panel.setMinimumWidth(260)
        preview_panel.setStyleSheet(
            "QFrame { background: #111; border-left: 1px solid #1e1e1e; }"
        )
        pf_layout = QVBoxLayout(preview_panel)
        pf_layout.setContentsMargins(12, 12, 12, 12)
        pf_layout.setSpacing(8)

        prev_lbl = QLabel("PREVIEW")
        prev_lbl.setObjectName("section_lbl")
        prev_lbl.setStyleSheet(
            "color: #5294e2; font-size: 10px; font-weight: 700; letter-spacing: 2px;"
        )
        pf_layout.addWidget(prev_lbl)

        self.preview = PreviewWidget()
        self.preview.apply_settings(self.s)
        self.preview.update_text("Doamne, Tu ești lumina mea\nȘi mântuirea mea")
        self.preview.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        pf_layout.addWidget(self.preview, 1)

        # Sample text selector
        sample_combo = QComboBox()
        sample_combo.addItems([
            "Doamne, Tu ești lumina mea\nȘi mântuirea mea",
            "Aleluia! Slavă Celui\nCare a murit și-a înviat",
            "Isuse, Isuse\nNume mai presus de orice nume",
            "Sfânt, sfânt, sfânt\nEste Domnul Dumnezeu Atotputernic",
        ])
        sample_combo.setStyleSheet(
            "QComboBox { background: #1c1c1c; color: #888; font-size: 10px; "
            "border: 1px solid #222; border-radius: 4px; padding: 3px 6px; }"
        )
        sample_combo.currentTextChanged.connect(
            lambda txt: self.preview.update_text(txt)
        )
        pf_layout.addWidget(sample_combo)

        h_splitter.addWidget(preview_panel)
        h_splitter.setSizes([520, 300])

        layout.addWidget(h_splitter, 1)

        # Buttons row (below splitter, full width)
        btn_frame = QFrame()
        btn_frame.setStyleSheet("QFrame { background: #111; border-top: 1px solid #222; }")
        bf_layout = QHBoxLayout(btn_frame)
        bf_layout.setContentsMargins(12, 8, 12, 8)
        bf_layout.addStretch()
        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton(f"✓  {t('save')}")
        ok_btn.setStyleSheet(
            "QPushButton { background: #5294e2; color: #fff; border: none; "
            "border-radius: 5px; padding: 7px 20px; font-weight: 600; }"
            "QPushButton:hover { background: #6ba5f0; }"
        )
        ok_btn.clicked.connect(self._accept)
        bf_layout.addWidget(cancel_btn)
        bf_layout.addWidget(ok_btn)
        layout.addWidget(btn_frame)

    def _scrollable(self, inner_widget):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner_widget)
        return scroll

    def _tab_display(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # ── Mod personalizare afișare ─────────────────────────────────────────
        mode_group = QGroupBox("Mod personalizare afișare")
        mode_layout = QVBoxLayout(mode_group)

        self.mode_settings_radio = QRadioButton("⚙ Setări globale (clasic)")
        self.mode_themes_radio   = QRadioButton("🎨 Teme personalizate")
        mode_layout.addWidget(self.mode_settings_radio)
        mode_layout.addWidget(self.mode_themes_radio)

        hint = QLabel(
            "Setări globale = font, culoare etc. din Settings se aplică la toate.\n"
            "Teme = personalizare avansată per gen, cântare sau tip (cântări/biblie)."
        )
        hint.setStyleSheet("color:#6c7086; font-size:11px;")
        hint.setWordWrap(True)
        mode_layout.addWidget(hint)
        layout.addWidget(mode_group)

        # Screen selection
        screen_group = QGroupBox(t("monitor_screen"))
        sf = QFormLayout(screen_group)
        self.screen_combo = QComboBox()
        for i, scr in enumerate(QApplication.screens()):
            g = scr.geometry()
            self.screen_combo.addItem(f"Screen {i+1}: {scr.name()} ({g.width()}×{g.height()})", i)
        sf.addRow(t("display_on"), self.screen_combo)

        # Which screen the Stage (confidence-monitor) window opens on.
        self.stage_screen_combo = QComboBox()
        for i, scr in enumerate(QApplication.screens()):
            g = scr.geometry()
            self.stage_screen_combo.addItem(
                f"Screen {i+1}: {scr.name()} ({g.width()}×{g.height()})", i)
        sf.addRow("Fereastra Stage pe:", self.stage_screen_combo)

        # Custom resolution for the live / stage windows (windowed, not fullscreen).
        self.custom_res_check = QCheckBox("Rezoluție custom (fereastră, nu fullscreen)")
        sf.addRow("", self.custom_res_check)
        _res_row = QHBoxLayout()
        self.custom_res_w = QSpinBox(); self.custom_res_w.setRange(320, 7680); self.custom_res_w.setValue(1920)
        self.custom_res_w.setSuffix(" px")
        self.custom_res_h = QSpinBox(); self.custom_res_h.setRange(240, 4320); self.custom_res_h.setValue(1080)
        self.custom_res_h.setSuffix(" px")
        _res_row.addWidget(self.custom_res_w); _res_row.addWidget(QLabel("×")); _res_row.addWidget(self.custom_res_h)
        _res_row.addStretch()
        sf.addRow("Rezoluție:", _res_row)
        self.custom_res_check.toggled.connect(
            lambda on: (self.custom_res_w.setEnabled(on), self.custom_res_h.setEnabled(on)))
        self.custom_res_w.setEnabled(False); self.custom_res_h.setEnabled(False)

        layout.addWidget(screen_group)

        # Background
        bg_group = QGroupBox(t("background"))
        bgf = QFormLayout(bg_group)

        self.bg_color_btn = ColorButton()
        self.bg_color_btn.colorChanged.connect(self._preview_update)
        bgf.addRow(t("solid_color") + ":", self.bg_color_btn)

        img_row = QHBoxLayout()
        self.bg_img_label = QLabel("None")
        self.bg_img_label.setStyleSheet("color: #666; font-size: 11px;")
        self.bg_img_label.setWordWrap(True)
        img_browse = QPushButton(t("browse") + "…")
        img_browse.clicked.connect(self._pick_bg_image)
        img_browse.setFixedWidth(90)
        img_clear = QPushButton(t("clear"))
        img_clear.clicked.connect(self._clear_bg_image)
        img_clear.setFixedWidth(70)
        img_row.addWidget(self.bg_img_label, 1)
        img_row.addWidget(img_browse)
        img_row.addWidget(img_clear)
        bgf.addRow(t("image") + ":", img_row)

        self.bg_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.bg_opacity_slider.setRange(0, 100)
        self.bg_opacity_slider.valueChanged.connect(self._preview_update)
        bgf.addRow(t("image_opacity") + ":", self.bg_opacity_slider)

        vid_row = QHBoxLayout()
        self.bg_vid_label = QLabel("None")
        self.bg_vid_label.setStyleSheet("color: #666; font-size: 11px;")
        vid_browse = QPushButton(t("browse") + "…")
        vid_browse.clicked.connect(self._pick_bg_video)
        vid_browse.setFixedWidth(90)
        vid_clear = QPushButton(t("clear"))
        vid_clear.clicked.connect(self._clear_bg_video)
        vid_clear.setFixedWidth(70)
        vid_row.addWidget(self.bg_vid_label, 1)
        vid_row.addWidget(vid_browse)
        vid_row.addWidget(vid_clear)
        bgf.addRow(t("video_file") + ":", vid_row)

        layout.addWidget(bg_group)

        # Transition
        trans_group = QGroupBox(t("transition"))
        tf = QFormLayout(trans_group)
        self.transition_combo = QComboBox()
        self.transition_combo.addItems([
            "fade", "crossfade", "fade_black", "fade_white", "dissolve",
            "slide_left", "slide_right", "slide_up", "slide_down",
            "push_left", "push_right", "push_up", "push_down",
            "reveal_left", "reveal_right", "reveal_up", "reveal_down",
            "wipe_left", "wipe_right", "wipe_up", "wipe_down", "wipe_diag",
            "zoom_in", "zoom_out", "iris_open", "iris_close",
            "flip_h", "flip_v", "spin", "squeeze_h", "squeeze_v",
            "bars_v", "bars_h", "checkerboard", "blur", "instant",
        ])
        tf.addRow(t("effect") + ":", self.transition_combo)

        self.transition_duration = QSpinBox()
        self.transition_duration.setRange(50, 2000)
        self.transition_duration.setValue(350)
        self.transition_duration.setSingleStep(50)
        self.transition_duration.setSuffix(" ms")
        self.transition_duration.setToolTip(
            "50 ms = aproape instant\n"
            "350 ms = implicit\n"
            "1000 ms = lent"
        )
        tf.addRow(t("duration") + ":", self.transition_duration)

        layout.addWidget(trans_group)

        layout.addStretch()
        return self._scrollable(w)

    def _tab_text(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        font_group = QGroupBox(t("font"))
        ff = QFormLayout(font_group)
        self.font_combo = QFontComboBox()
        self.font_combo.currentFontChanged.connect(self._preview_update)
        ff.addRow(t("font_family") + ":", self.font_combo)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(12, 200)
        self.font_size_spin.valueChanged.connect(self._preview_update)
        ff.addRow(t("size_pt") + ":", self.font_size_spin)

        style_row = QHBoxLayout()
        self.bold_check = QCheckBox("Bold")
        self.italic_check = QCheckBox("Italic")
        self.bold_check.stateChanged.connect(self._preview_update)
        self.italic_check.stateChanged.connect(self._preview_update)
        style_row.addWidget(self.bold_check)
        style_row.addWidget(self.italic_check)
        style_row.addStretch()
        ff.addRow(t("style") + ":", style_row)
        layout.addWidget(font_group)

        color_group = QGroupBox(t("color_effects"))
        cf = QFormLayout(color_group)

        self.text_color_btn = ColorButton("#ffffff")
        self.text_color_btn.colorChanged.connect(self._preview_update)
        cf.addRow(t("text_color") + ":", self.text_color_btn)

        shadow_row = QHBoxLayout()
        self.shadow_check = QCheckBox(t("drop_shadow"))
        self.shadow_check.stateChanged.connect(self._preview_update)
        shadow_row.addWidget(self.shadow_check)
        shadow_row.addStretch()
        cf.addRow(t("shadow") + ":", shadow_row)

        outline_row = QHBoxLayout()
        self.outline_color_btn = ColorButton("#000000")
        self.outline_color_btn.colorChanged.connect(self._preview_update)
        self.outline_spin = QSpinBox()
        self.outline_spin.setRange(0, 10)
        self.outline_spin.setFixedWidth(60)
        self.outline_spin.valueChanged.connect(self._preview_update)
        outline_row.addWidget(QLabel(t("color") + ":"))
        outline_row.addWidget(self.outline_color_btn)
        outline_row.addSpacing(10)
        outline_row.addWidget(QLabel(t("outline_width") + ":"))
        outline_row.addWidget(self.outline_spin)
        outline_row.addStretch()
        cf.addRow(t("outline") + ":", outline_row)

        self.line_spacing_spin = QDoubleSpinBox()
        self.line_spacing_spin.setRange(1.0, 3.0)
        self.line_spacing_spin.setSingleStep(0.1)
        self.line_spacing_spin.setDecimals(1)
        self.line_spacing_spin.valueChanged.connect(self._preview_update)
        cf.addRow(t("line_spacing") + ":", self.line_spacing_spin)

        self.margin_spin = QSpinBox()
        self.margin_spin.setRange(0, 400)
        self.margin_spin.valueChanged.connect(self._preview_update)
        cf.addRow(t("margin") + " (px):", self.margin_spin)
        layout.addWidget(color_group)

        align_group = QGroupBox(t("alignment"))
        af = QFormLayout(align_group)
        self.h_align_combo = QComboBox()
        self.h_align_combo.addItems(["center", "left", "right"])
        self.h_align_combo.currentIndexChanged.connect(self._preview_update)
        af.addRow(t("horizontal") + ":", self.h_align_combo)

        self.v_align_combo = QComboBox()
        self.v_align_combo.addItems(["center", "top", "bottom"])
        self.v_align_combo.currentIndexChanged.connect(self._preview_update)
        af.addRow(t("vertical") + ":", self.v_align_combo)
        layout.addWidget(align_group)

        # Sacred words auto-capitalization
        sacred_group = QGroupBox("Cuvinte cu majuscule automate")
        sg = QVBoxLayout(sacred_group)

        self.sacred_enabled = QCheckBox("Activează capitalizare automată pentru cuvinte sacre")
        sg.addWidget(self.sacred_enabled)

        self.sacred_allcaps = QCheckBox("MAJUSCULE COMPLETE (ex: ISUS, ALELUIA)")
        sg.addWidget(self.sacred_allcaps)

        sg.addWidget(QLabel("Listă cuvinte (câte unul pe linie sau despărțite prin virgulă):"))
        self.sacred_words_edit = QTextEdit()
        self.sacred_words_edit.setFixedHeight(120)
        self.sacred_words_edit.setPlaceholderText("Jesus\nIsus\nDumnezeu\n...")
        sg.addWidget(self.sacred_words_edit)

        reset_btn = QPushButton("Resetează la valorile implicite")
        reset_btn.setFixedWidth(220)
        reset_btn.clicked.connect(self._reset_sacred_words)
        sg.addWidget(reset_btn)

        layout.addWidget(sacred_group)

        layout.addStretch()
        return self._scrollable(w)

    def _tab_overlays(self):
        s = self.s
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Ticker
        ticker_group = QGroupBox(t("ticker_section"))
        tg = QVBoxLayout(ticker_group)
        self.ticker_enabled = QCheckBox(t("ticker_enable"))
        tg.addWidget(self.ticker_enabled)
        tf = QFormLayout()
        self.ticker_text = QLineEdit()
        self.ticker_text.setPlaceholderText("Text ticker…")
        tf.addRow(t("text") + ":", self.ticker_text)
        self.ticker_color_btn = ColorButton("#ffffff")
        tf.addRow(t("text_color") + ":", self.ticker_color_btn)
        self.ticker_speed = QSpinBox()
        self.ticker_speed.setRange(1, 10)
        self.ticker_speed.setValue(2)
        tf.addRow(t("ticker_speed") + ":", self.ticker_speed)
        tg.addLayout(tf)
        layout.addWidget(ticker_group)

        # Clock
        clock_group = QGroupBox(t("live_clock"))
        cg = QVBoxLayout(clock_group)
        self.clock_enabled = QCheckBox(t("clock_enable"))
        cg.addWidget(self.clock_enabled)
        cf = QFormLayout()
        self.clock_color_btn = ColorButton("#ffffff")
        cf.addRow(t("clock_color") + ":", self.clock_color_btn)
        self.clock_format = QComboBox()
        self.clock_format.addItems(["HH:MM:SS", "HH:MM", "12h"])
        cf.addRow(t("clock_format") + ":", self.clock_format)
        cg.addLayout(cf)
        layout.addWidget(clock_group)

        # Countdown
        countdown_group = QGroupBox(t("countdown_section"))
        dg = QVBoxLayout(countdown_group)
        self.countdown_enabled = QCheckBox(t("countdown_enable"))
        dg.addWidget(self.countdown_enabled)
        df = QFormLayout()
        self.countdown_seconds = QSpinBox()
        self.countdown_seconds.setRange(10, 7200)
        self.countdown_seconds.setSuffix(" s")
        self.countdown_seconds.setValue(300)
        df.addRow(t("duration") + ":", self.countdown_seconds)
        self.countdown_color_btn = ColorButton("#ffffff")
        df.addRow(t("countdown_color") + ":", self.countdown_color_btn)
        dg.addLayout(df)
        layout.addWidget(countdown_group)

        # ── Copyright / Watermark ─────────────────────────────────────────────
        cr_group = QGroupBox("Copyright / Watermark")
        crf = QVBoxLayout(cr_group)

        self.cr_enabled = QCheckBox("Afișează copyright pe ecranul Live")
        crf.addWidget(self.cr_enabled)

        cr_form = QFormLayout()
        cr_form.setSpacing(6)

        self.cr_mode = QComboBox()
        self.cr_mode.addItems([
            "title_author — Titlu — Autor",
            "title — Doar titlul",
            "author — Doar autorul",
            "category — Categoria",
            "source — Sursa (resursecrestine.ro)",
            "custom — Text personalizat",
        ])
        cr_form.addRow("Conținut:", self.cr_mode)

        self.cr_custom = QLineEdit()
        self.cr_custom.setPlaceholderText("Text watermark personalizat…")
        cr_form.addRow("Text custom:", self.cr_custom)

        self.cr_position = QComboBox()
        self.cr_position.addItems([
            "bottom_right — Dreapta-jos",
            "bottom_left — Stânga-jos",
            "bottom_center — Centru-jos",
            "top_right — Dreapta-sus",
            "top_left — Stânga-sus",
        ])
        cr_form.addRow("Poziție:", self.cr_position)

        cr_size_row = QHBoxLayout()
        self.cr_font_size = QSpinBox()
        self.cr_font_size.setRange(8, 36)
        self.cr_font_size.setValue(12)
        self.cr_font_size.setSuffix(" pt")
        self.cr_font_size.setFixedWidth(80)
        cr_size_row.addWidget(self.cr_font_size)
        cr_size_row.addStretch()
        cr_form.addRow("Dimensiune font:", cr_size_row)

        self.cr_color = ColorButton("#ffffff")
        cr_form.addRow("Culoare text:", self.cr_color)

        self.cr_opacity = QSlider(Qt.Orientation.Horizontal)
        self.cr_opacity.setRange(5, 100)
        self.cr_opacity.setValue(40)
        cr_form.addRow("Opacitate (5–100%):", self.cr_opacity)

        crf.addLayout(cr_form)
        layout.addWidget(cr_group)

        # ── Bible reference style (displayed when sending Bible verses) ───────
        br_group = QGroupBox("Stil referință Biblică (Mod Setări)")
        brf = QFormLayout(br_group)
        brf.setSpacing(6)

        br_lbl = QLabel(
            "Aceste setări controlează cum apare referința (ex: Ioan 3:16) pe ecranul live\n"
            "când modul de afișare este Setări (nu teme)."
        )
        br_lbl.setWordWrap(True)
        br_lbl.setStyleSheet("color: #888; font-size: 10px;")
        brf.addRow(br_lbl)

        self.br_font_size = QSpinBox()
        self.br_font_size.setRange(8, 60)
        self.br_font_size.setValue(int(s.get("ref_font_size", 24)))
        brf.addRow("Dimensiune font:", self.br_font_size)

        self.br_color = ColorButton(s.get("ref_color", "#aaaaaa"))
        brf.addRow("Culoare:", self.br_color)

        self.br_italic = QCheckBox("Italic")
        self.br_italic.setChecked(s.get("ref_italic", "true") == "true")
        brf.addRow("Stil:", self.br_italic)

        self.br_position = QComboBox()
        self.br_position.addItems([
            "Dreapta-jos (verset sus)",
            "Stânga-jos (verset sus)",
            "Centru-jos (verset sus)",
            "Dreapta-sus (verset jos)",
            "Stânga-sus (verset jos)",
            "Centru-sus (verset jos)",
        ])
        _br_pos_map = {
            "bottom_right": 0, "bottom_left": 1, "bottom_center": 2,
            "top_right": 3, "top_left": 4, "top_center": 5,
        }
        self.br_position.setCurrentIndex(_br_pos_map.get(s.get("ref_position", "bottom_right"), 0))
        brf.addRow("Layout Biblie:", self.br_position)

        layout.addWidget(br_group)

        # ── Advanced overlay personalization ──────────────────────────────────
        adv_lbl = QLabel("PERSONALIZARE AVANSATĂ OVERLAY-URI")
        adv_lbl.setObjectName("section_lbl")
        layout.addWidget(adv_lbl)

        from overlay_settings import OverlaySettingsWidget
        self._overlay_adv = OverlaySettingsWidget(self.s)
        layout.addWidget(self._overlay_adv)

        layout.addStretch()
        return self._scrollable(w)

    # ── Windows tab ───────────────────────────────────────────────────────────

    def _tab_windows(self):
        """Tab: manager ferestre display configurabile."""
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        hdr = QLabel("MANAGER FERESTRE DISPLAY")
        hdr.setObjectName("section_lbl")
        outer.addWidget(hdr)

        sub = QLabel(
            "Configurează ferestrele live independente. Fiecare poate rula pe un ecran diferit "
            "și poate avea font, culori și fundal proprii."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #888; font-size: 11px;")
        outer.addWidget(sub)

        # ── Two-pane layout ───────────────────────────────────────────────────
        h_layout = QHBoxLayout()
        h_layout.setSpacing(12)

        # Left pane — window list
        list_w = QWidget()
        list_w.setFixedWidth(210)
        list_l = QVBoxLayout(list_w)
        list_l.setContentsMargins(0, 0, 0, 0)
        list_l.setSpacing(6)

        list_lbl = QLabel("Ferestre configurate:")
        list_lbl.setStyleSheet("color: #888; font-size: 11px;")
        list_l.addWidget(list_lbl)

        self._win_list = QListWidget()
        self._win_list.setStyleSheet(
            "QListWidget { background: #111; border: 1px solid #252525; border-radius:4px; }"
            "QListWidget::item { padding:7px 8px; color:#ccc; }"
            "QListWidget::item:selected { background:#1c3a5a; color:#fff; }"
        )
        self._win_list.currentRowChanged.connect(self._on_win_select)
        list_l.addWidget(self._win_list, 1)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("＋ Adaugă")
        add_btn.clicked.connect(self._add_window_config)
        del_btn = QPushButton("🗑")
        del_btn.setFixedWidth(32)
        del_btn.setToolTip("Șterge fereastra selectată")
        del_btn.clicked.connect(self._del_window_config)
        btn_row.addWidget(add_btn, 1)
        btn_row.addWidget(del_btn)
        list_l.addLayout(btn_row)

        h_layout.addWidget(list_w)

        # Right pane — config form (shown only when a window is selected)
        self._win_detail = QWidget()
        detail_l = QVBoxLayout(self._win_detail)
        detail_l.setContentsMargins(0, 0, 0, 0)
        detail_l.setSpacing(10)

        no_sel_lbl = QLabel("← Selectează sau adaugă o fereastră")
        no_sel_lbl.setStyleSheet("color: #555; font-size: 12px;")
        no_sel_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Stacked: index 0 = "no selection" placeholder, index 1 = form
        self._win_stack = QStackedWidget()
        self._win_stack.addWidget(no_sel_lbl)

        form_container = QWidget()
        form_l = QFormLayout(form_container)
        form_l.setSpacing(10)

        self.win_name_edit = QLineEdit()
        self.win_name_edit.setPlaceholderText("ex: Proiector Principal")
        self.win_name_edit.textChanged.connect(self._sync_win_config)
        form_l.addRow("Nume:", self.win_name_edit)

        self.win_screen_combo = QComboBox()
        screens = QApplication.screens()
        for i, scr in enumerate(screens):
            g = scr.geometry()
            self.win_screen_combo.addItem(
                f"Screen {i}: {scr.name()} ({g.width()}×{g.height()})", i
            )
        self.win_screen_combo.currentIndexChanged.connect(self._sync_win_config)
        form_l.addRow("Ecran:", self.win_screen_combo)

        self.win_fullscreen_chk = QCheckBox("Fullscreen (recomandat pentru proiectare)")
        self.win_fullscreen_chk.setChecked(True)
        self.win_fullscreen_chk.stateChanged.connect(self._sync_win_config)
        form_l.addRow("", self.win_fullscreen_chk)

        self.win_active_chk = QCheckBox("Activă — pornește automat la start")
        self.win_active_chk.setChecked(True)
        self.win_active_chk.stateChanged.connect(self._sync_win_config)
        form_l.addRow("", self.win_active_chk)

        ind_btn = QPushButton("⚙ Setări individuale text/culori…")
        ind_btn.setStyleSheet(
            "QPushButton { background:#1a2a3a; color:#5294e2; border:1px solid #1c3a5a; "
            "border-radius:4px; padding:6px 12px; font-weight:600; }"
            "QPushButton:hover { background:#1c3a5a; color:#e0e0e0; }"
        )
        ind_btn.clicked.connect(self._open_win_per_settings)
        form_l.addRow("", ind_btn)

        # Mini preview
        prev_lbl2 = QLabel("Preview fereastră:")
        prev_lbl2.setStyleSheet("color:#888; font-size:11px;")
        form_l.addRow("", prev_lbl2)
        self._win_preview = PreviewWidget()
        self._win_preview.setFixedHeight(110)
        self._win_preview.apply_settings(self.s)
        self._win_preview.update_text("Doamne, Tu ești lumina mea")
        form_l.addRow("", self._win_preview)

        self._win_stack.addWidget(form_container)
        detail_l.addWidget(self._win_stack, 1)
        h_layout.addWidget(self._win_detail, 1)
        outer.addLayout(h_layout, 1)

        # Load configs
        self._window_configs = db.get_display_configs()
        self._win_syncing = False   # re-entrancy guard
        self._populate_win_list()

        return self._scrollable(w)

    def _populate_win_list(self):
        self._win_list.clear()
        for i, cfg in enumerate(self._window_configs):
            label = cfg.get("name", f"Fereastră {i+1}")
            active = "✓" if cfg.get("active", True) else "○"
            fs = "FS" if cfg.get("fullscreen", True) else "WIN"
            item = QListWidgetItem(f"{active}  {label}  [{fs}]")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self._win_list.addItem(item)
        if self._win_list.count() > 0:
            self._win_list.setCurrentRow(0)

    def _on_win_select(self, row):
        if row < 0 or row >= len(self._window_configs):
            self._win_stack.setCurrentIndex(0)
            return
        self._win_stack.setCurrentIndex(1)
        cfg = self._window_configs[row]
        self._win_syncing = True
        self.win_name_edit.setText(cfg.get("name", ""))
        scr_idx = cfg.get("screen", 1)
        sc = self.win_screen_combo
        for i in range(sc.count()):
            if sc.itemData(i) == scr_idx:
                sc.setCurrentIndex(i)
                break
        self.win_fullscreen_chk.setChecked(cfg.get("fullscreen", True))
        self.win_active_chk.setChecked(cfg.get("active", True))
        self._win_syncing = False
        # Update preview with this window's settings
        merged = dict(self.s)
        merged.update(cfg.get("settings", {}))
        self._win_preview.apply_settings(merged)
        self._win_preview.update_text("Doamne, Tu ești lumina mea")

    def _sync_win_config(self):
        """Write form values back to the current config dict."""
        if self._win_syncing:
            return
        row = self._win_list.currentRow()
        if row < 0 or row >= len(self._window_configs):
            return
        cfg = self._window_configs[row]
        cfg["name"] = self.win_name_edit.text() or f"Fereastră {row + 1}"
        cfg["screen"] = self.win_screen_combo.currentData() or 0
        cfg["fullscreen"] = self.win_fullscreen_chk.isChecked()
        cfg["active"] = self.win_active_chk.isChecked()
        # Refresh list label
        label = cfg["name"]
        active = "✓" if cfg["active"] else "○"
        fs = "FS" if cfg["fullscreen"] else "WIN"
        self._win_list.item(row).setText(f"{active}  {label}  [{fs}]")

    def _add_window_config(self):
        new_cfg = {
            "name": f"Fereastră {len(self._window_configs) + 1}",
            "screen": 1,
            "fullscreen": True,
            "active": True,
            "settings": {},
        }
        self._window_configs.append(new_cfg)
        self._populate_win_list()
        self._win_list.setCurrentRow(len(self._window_configs) - 1)

    def _del_window_config(self):
        row = self._win_list.currentRow()
        if row < 0 or row >= len(self._window_configs):
            return
        if len(self._window_configs) <= 1:
            QMessageBox.warning(
                self, "Cel puțin o fereastră",
                "Trebuie să existe cel puțin o fereastră configurată."
            )
            return
        name = self._window_configs[row].get("name", "")
        if QMessageBox.question(
            self, "Șterge fereastră",
            f"Ștergi configurația «{name}»?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self._window_configs.pop(row)
            self._populate_win_list()

    def _open_win_per_settings(self):
        row = self._win_list.currentRow()
        if row < 0 or row >= len(self._window_configs):
            return
        cfg = self._window_configs[row]
        dlg = WindowPerSettingsDialog(
            parent=self,
            window_settings=cfg.get("settings", {}),
            global_settings=self.s,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            cfg["settings"] = dlg.result_settings
            # Refresh mini preview
            merged = dict(self.s)
            merged.update(cfg["settings"])
            self._win_preview.apply_settings(merged)
            self._win_preview.update_text("Doamne, Tu ești lumina mea")

    # ── Interface / Language tab ──────────────────────────────────────────────

    def _tab_interface(self):
        """Tab: interface language selection."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        lang_group = QGroupBox(t("interface_language"))
        lg = QFormLayout(lang_group)

        self.lang_combo = QComboBox()
        langs = available_languages()
        for code, name in langs.items():
            self.lang_combo.addItem(name, code)
        # Select current language
        current = self.s.get("language", get_language())
        idx = self.lang_combo.findData(current)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)

        lg.addRow(t("interface_language") + ":", self.lang_combo)

        restart_lbl = QLabel(f"ℹ  {t('restart_required')}")
        restart_lbl.setStyleSheet("color: #ccaa44; font-size: 11px;")
        restart_lbl.setWordWrap(True)
        lg.addRow("", restart_lbl)

        layout.addWidget(lang_group)
        layout.addStretch()
        return self._scrollable(w)

    # ── Supabase tab ──────────────────────────────────────────────────────────

    def _tab_supabase(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Connection settings
        conn_group = QGroupBox("Supabase Connection")
        cf = QFormLayout(conn_group)

        self.supa_url = QLineEdit()
        self.supa_url.setPlaceholderText("https://xxxx.supabase.co")
        cf.addRow("Project URL:", self.supa_url)

        self.supa_key = QLineEdit()
        self.supa_key.setPlaceholderText("eyJ…  (anon/public key)")
        self.supa_key.setEchoMode(QLineEdit.EchoMode.Password)
        cf.addRow("Anon Key:", self.supa_key)

        self.supa_bucket = QLineEdit()
        self.supa_bucket.setPlaceholderText("cantio-media")
        cf.addRow("Bucket:", self.supa_bucket)

        test_btn = QPushButton("🔌 Test Connection")
        test_btn.setStyleSheet(
            "QPushButton { background: #18283a; color: #5294e2; border: 1px solid #1c3a5a; "
            "border-radius: 4px; padding: 6px 14px; font-weight: 500; }"
            "QPushButton:hover { background: #1c3a5a; }"
        )
        test_btn.clicked.connect(self._test_supabase)
        cf.addRow("", test_btn)

        self.supa_status_lbl = QLabel("")
        self.supa_status_lbl.setStyleSheet("color: #666; font-size: 11px;")
        self.supa_status_lbl.setWordWrap(True)
        cf.addRow("Status:", self.supa_status_lbl)

        layout.addWidget(conn_group)

        # Upload media
        upload_group = QGroupBox("Upload Media to Cloud")
        ug = QVBoxLayout(upload_group)

        upload_row = QHBoxLayout()
        self.upload_path_lbl = QLabel("No file selected")
        self.upload_path_lbl.setStyleSheet("color: #666; font-size: 11px;")
        browse_upload_btn = QPushButton("Browse…")
        browse_upload_btn.setFixedWidth(80)
        browse_upload_btn.clicked.connect(self._browse_upload)
        upload_row.addWidget(self.upload_path_lbl, 1)
        upload_row.addWidget(browse_upload_btn)
        ug.addLayout(upload_row)

        self.upload_progress = QProgressBar()
        self.upload_progress.setValue(0)
        self.upload_progress.hide()
        ug.addWidget(self.upload_progress)

        upload_btn = QPushButton("⬆ Upload")
        upload_btn.setStyleSheet(
            "QPushButton { background: #5294e2; color: #fff; border: none; "
            "border-radius: 4px; padding: 6px 14px; font-weight: 600; }"
            "QPushButton:hover { background: #6ba5f0; }"
        )
        upload_btn.clicked.connect(self._upload_file)
        ug.addWidget(upload_btn)

        layout.addWidget(upload_group)

        # Cloud media browser
        browser_group = QGroupBox("Cloud Media Browser")
        bg = QVBoxLayout(browser_group)

        refresh_btn = QPushButton("🔄 Refresh Cloud Files")
        refresh_btn.clicked.connect(self._refresh_cloud_files)
        bg.addWidget(refresh_btn)

        self.cloud_list = QListWidget()
        self.cloud_list.setFixedHeight(120)
        bg.addWidget(self.cloud_list)

        cloud_btn_row = QHBoxLayout()
        use_bg_btn = QPushButton("Set as Background")
        use_bg_btn.setStyleSheet(
            "QPushButton { background: #1a2a1a; color: #66bb66; border: 1px solid #2a4a2a; "
            "border-radius: 4px; padding: 5px 12px; font-size: 11px; }"
            "QPushButton:hover { background: #1e341e; }"
        )
        use_bg_btn.clicked.connect(self._use_cloud_as_bg)
        self.cloud_dl_progress = QProgressBar()
        self.cloud_dl_progress.setValue(0)
        self.cloud_dl_progress.hide()
        cloud_btn_row.addWidget(use_bg_btn)
        cloud_btn_row.addWidget(self.cloud_dl_progress, 1)
        bg.addLayout(cloud_btn_row)

        layout.addWidget(browser_group)

        layout.addStretch()
        return self._scrollable(w)

    # ── Cloud actions ─────────────────────────────────────────────────────────

    def _get_supabase_params(self):
        url = self.supa_url.text().strip()
        key = self.supa_key.text().strip()
        bucket = self.supa_bucket.text().strip() or "cantio-media"
        return url, key, bucket

    def _test_supabase(self):
        import cloud_manager
        url, key, bucket = self._get_supabase_params()
        if not url or not key:
            self.supa_status_lbl.setText("⚠ Enter URL and key first.")
            self.supa_status_lbl.setStyleSheet("color: #ccaa44; font-size: 11px;")
            return
        ok, msg = cloud_manager.test_connection(url, key, bucket)
        if ok:
            self.supa_status_lbl.setText(f"✓ {msg}")
            self.supa_status_lbl.setStyleSheet("color: #66cc66; font-size: 11px;")
        else:
            self.supa_status_lbl.setText(f"✗ {msg}")
            self.supa_status_lbl.setStyleSheet("color: #f44336; font-size: 11px;")

    def _browse_upload(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select File to Upload", "",
            "Media (*.png *.jpg *.jpeg *.webp *.bmp *.mp4 *.mov *.avi *.mkv *.webm)"
        )
        if path:
            self.upload_path_lbl.setText(path)

    def _upload_file(self):
        import cloud_manager
        local_path = self.upload_path_lbl.text()
        if not local_path or local_path == "No file selected" or not os.path.exists(local_path):
            QMessageBox.warning(self, "No File", "Please select a file to upload first.")
            return
        url, key, bucket = self._get_supabase_params()
        if not url or not key:
            QMessageBox.warning(self, "Config Missing", "Enter Supabase URL and key first.")
            return

        self.upload_progress.show()
        self.upload_progress.setValue(0)

        def progress(sent, total):
            if total > 0:
                self.upload_progress.setValue(int(sent / total * 100))

        def do_upload():
            try:
                fname = cloud_manager.upload_file(url, key, bucket, local_path, progress_cb=progress)
                self.supa_status_lbl.setText(f"✓ Uploaded: {fname}")
                self.supa_status_lbl.setStyleSheet("color: #66cc66; font-size: 11px;")
                self._refresh_cloud_files()
            except Exception as e:
                self.supa_status_lbl.setText(f"✗ Upload failed: {e}")
                self.supa_status_lbl.setStyleSheet("color: #f44336; font-size: 11px;")

        t = threading.Thread(target=do_upload, daemon=True)
        t.start()

    def _refresh_cloud_files(self):
        import cloud_manager
        url, key, bucket = self._get_supabase_params()
        if not url or not key:
            return
        try:
            files = cloud_manager.list_files(url, key, bucket)
            self.cloud_list.clear()
            for f in files:
                name = f.get("name", str(f))
                item = QListWidgetItem(name)
                item.setData(Qt.ItemDataRole.UserRole, name)
                self.cloud_list.addItem(item)
            self.supa_status_lbl.setText(f"✓ {len(files)} file(s) in bucket")
            self.supa_status_lbl.setStyleSheet("color: #66cc66; font-size: 11px;")
        except Exception as e:
            self.supa_status_lbl.setText(f"✗ {e}")
            self.supa_status_lbl.setStyleSheet("color: #f44336; font-size: 11px;")

    def _use_cloud_as_bg(self):
        import cloud_manager
        item = self.cloud_list.currentItem()
        if not item:
            return
        filename = item.data(Qt.ItemDataRole.UserRole)
        url, key, bucket = self._get_supabase_params()
        if not url or not key:
            return

        self.cloud_dl_progress.show()
        self.cloud_dl_progress.setValue(0)

        def progress(dl, total):
            if total > 0:
                self.cloud_dl_progress.setValue(int(dl / total * 100))

        def do_download():
            try:
                local_path = cloud_manager.download_file(url, key, bucket, filename, progress)
                # Set as background
                if cloud_manager.is_image(filename):
                    self.bg_img_label.setText(local_path)
                    self._preview_update()
                    self.supa_status_lbl.setText(f"✓ Image set as background: {filename}")
                elif cloud_manager.is_video(filename):
                    self.bg_vid_label.setText(local_path)
                    self.supa_status_lbl.setText(f"✓ Video set as background: {filename}")
                self.supa_status_lbl.setStyleSheet("color: #66cc66; font-size: 11px;")
            except Exception as e:
                self.supa_status_lbl.setText(f"✗ Download failed: {e}")
                self.supa_status_lbl.setStyleSheet("color: #f44336; font-size: 11px;")

        t = threading.Thread(target=do_download, daemon=True)
        t.start()

    # ── Cloud Backup tab ──────────────────────────────────────────────────────

    def _tab_cloud_backup(self):
        """Tab: local/cloud backup and restore."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # ── Provider ──────────────────────────────────────────────────────────
        prov_grp = QGroupBox("Furnizor backup")
        pf = QVBoxLayout(prov_grp)
        self._bk_none_radio   = QRadioButton("Dezactivat")
        self._bk_folder_radio = QRadioButton("📁 Folder local")
        self._bk_gdrive_radio = QRadioButton("Google Drive")
        self._bk_dropbox_radio = QRadioButton("Dropbox")
        self._bk_onedrive_radio = QRadioButton("OneDrive")
        self._bk_none_radio.setChecked(True)
        for rb in (self._bk_none_radio, self._bk_folder_radio,
                   self._bk_gdrive_radio, self._bk_dropbox_radio,
                   self._bk_onedrive_radio):
            pf.addWidget(rb)

        folder_row = QHBoxLayout()
        self._bk_folder_lbl = QLabel("Niciun folder selectat")
        self._bk_folder_lbl.setStyleSheet("color:#666; font-size:11px;")
        bk_browse = QPushButton("Browse…")
        bk_browse.setFixedWidth(70)
        bk_browse.clicked.connect(self._bk_pick_folder)
        folder_row.addWidget(self._bk_folder_lbl, 1)
        folder_row.addWidget(bk_browse)
        pf.addLayout(folder_row)
        layout.addWidget(prov_grp)

        # ── Auto-backup ───────────────────────────────────────────────────────
        auto_grp = QGroupBox("Auto-backup")
        af = QFormLayout(auto_grp)
        self._bk_auto_chk = QCheckBox("Activează auto-backup")
        af.addRow("", self._bk_auto_chk)
        self._bk_freq_combo = QComboBox()
        self._bk_freq_combo.addItems(["La fiecare pornire", "Zilnic", "Săptămânal"])
        af.addRow("Frecvență:", self._bk_freq_combo)
        self._bk_keep_spin = QSpinBox()
        self._bk_keep_spin.setRange(1, 30)
        self._bk_keep_spin.setValue(5)
        self._bk_keep_spin.setSuffix(" backup-uri")
        af.addRow("Păstrează:", self._bk_keep_spin)
        layout.addWidget(auto_grp)

        # ── What to backup ────────────────────────────────────────────────────
        what_grp = QGroupBox("Ce se salvează")
        wf = QVBoxLayout(what_grp)
        self._bk_songs_chk    = QCheckBox("Cântări și baze de date")
        self._bk_bible_chk    = QCheckBox("Bible DB")
        self._bk_settings_chk = QCheckBox("Setări")
        self._bk_services_chk = QCheckBox("Servicii salvate")
        self._bk_media_chk    = QCheckBox("Fișiere media cache")
        for cb in (self._bk_songs_chk, self._bk_bible_chk,
                   self._bk_settings_chk, self._bk_services_chk):
            cb.setChecked(True)
            wf.addWidget(cb)
        self._bk_media_chk.setChecked(False)
        wf.addWidget(self._bk_media_chk)
        layout.addWidget(what_grp)

        # ── Action buttons ────────────────────────────────────────────────────
        act_grp = QGroupBox("Acțiuni")
        acf = QVBoxLayout(act_grp)

        self._bk_status_lbl = QLabel("")
        self._bk_status_lbl.setWordWrap(True)
        self._bk_status_lbl.setStyleSheet("color:#888; font-size:11px;")
        acf.addWidget(self._bk_status_lbl)

        btn_row = QHBoxLayout()
        backup_now_btn = QPushButton("📦 Backup Acum")
        backup_now_btn.setStyleSheet(
            "QPushButton { background:#1a3a1a; color:#66cc66; border:1px solid #2a5a2a; "
            "border-radius:5px; padding:8px 16px; font-weight:600; }"
            "QPushButton:hover { background:#1e4a1e; }"
        )
        backup_now_btn.clicked.connect(self._do_backup_now)

        restore_btn = QPushButton("⬆ Restaurează")
        restore_btn.setStyleSheet(
            "QPushButton { background:#1a1a3a; color:#5294e2; border:1px solid #1c3a5a; "
            "border-radius:5px; padding:8px 16px; font-weight:600; }"
            "QPushButton:hover { background:#1e1e4a; }"
        )
        restore_btn.clicked.connect(self._do_restore)

        btn_row.addWidget(backup_now_btn)
        btn_row.addWidget(restore_btn)
        btn_row.addStretch()
        acf.addLayout(btn_row)

        open_backups_btn = QPushButton("📁 Deschide folder backup-uri")
        open_backups_btn.clicked.connect(self._open_backup_folder)
        acf.addWidget(open_backups_btn)

        layout.addWidget(act_grp)
        layout.addStretch()
        return self._scrollable(w)

    def _bk_pick_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Selectează folder backup", "")
        if folder:
            self._bk_folder_lbl.setText(folder)
            self._bk_folder_radio.setChecked(True)

    def _get_backup_root(self) -> str:
        """Return the backup destination directory."""
        if self._bk_folder_radio.isChecked():
            folder = self._bk_folder_lbl.text()
            if folder and folder != "Niciun folder selectat" and os.path.isdir(folder):
                return folder
        try:
            from paths import get_data_dir
            return os.path.join(get_data_dir(), "backups")
        except ImportError:
            return os.path.join(os.path.expanduser("~"), "Cantio", "backups")

    def _do_backup_now(self):
        """Perform an immediate backup of selected data."""
        import shutil, datetime
        try:
            from paths import get_profiles_dir
            profiles_dir = get_profiles_dir()
        except ImportError:
            profiles_dir = os.path.join(os.path.expanduser("~"), "Cantio", "profiles")

        backup_root = self._get_backup_root()
        os.makedirs(backup_root, exist_ok=True)

        stamp   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dest    = os.path.join(backup_root, f"backup_{stamp}")
        os.makedirs(dest, exist_ok=True)

        backed_up = []
        errors    = []

        try:
            if self._bk_songs_chk.isChecked() and os.path.isdir(profiles_dir):
                shutil.copytree(profiles_dir,
                                os.path.join(dest, "profiles"),
                                dirs_exist_ok=True)
                backed_up.append("Profiluri")
        except Exception as e:
            errors.append(f"Profiluri: {e}")

        # Write backup manifest
        import json as _json
        manifest = {
            "stamp":      stamp,
            "backed_up":  backed_up,
            "errors":     [str(e) for e in errors],
            "version":    "1.0",
        }
        try:
            with open(os.path.join(dest, "backup_info.json"), "w", encoding="utf-8") as f:
                _json.dump(manifest, f, indent=2)
        except Exception:
            pass

        # Prune old backups
        keep = self._bk_keep_spin.value()
        try:
            all_bk = sorted(
                [d for d in os.listdir(backup_root)
                 if d.startswith("backup_") and
                 os.path.isdir(os.path.join(backup_root, d))]
            )
            while len(all_bk) > keep:
                shutil.rmtree(os.path.join(backup_root, all_bk.pop(0)),
                              ignore_errors=True)
        except Exception:
            pass

        if errors:
            self._bk_status_lbl.setText(
                f"⚠ Backup parțial în {dest}\n" + "\n".join(errors))
            self._bk_status_lbl.setStyleSheet("color:#ccaa44; font-size:11px;")
        else:
            self._bk_status_lbl.setText(
                f"✅ Backup realizat: {dest}\n"
                f"Componente: {', '.join(backed_up) or 'nimic selectat'}")
            self._bk_status_lbl.setStyleSheet("color:#66cc66; font-size:11px;")

    def _do_restore(self):
        """Let user pick a backup folder and restore from it."""
        import shutil
        backup_root = self._get_backup_root()
        folder = QFileDialog.getExistingDirectory(
            self, "Selectează backup-ul de restaurat", backup_root
        )
        if not folder:
            return

        # Validate
        manifest_path = os.path.join(folder, "backup_info.json")
        if not os.path.exists(manifest_path):
            QMessageBox.warning(
                self, "Backup invalid",
                "Folderul selectat nu conține un backup Cantio valid\n"
                "(lipsește backup_info.json)."
            )
            return

        reply = QMessageBox.question(
            self, "Confirmare restaurare",
            f"Restaurezi backup-ul din:\n{folder}\n\n"
            "Datele curente vor fi suprascrise. Continui?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            from paths import get_profiles_dir
            profiles_dir = get_profiles_dir()
        except ImportError:
            profiles_dir = os.path.join(os.path.expanduser("~"), "Cantio", "profiles")

        errors = []
        src_profiles = os.path.join(folder, "profiles")
        if os.path.isdir(src_profiles):
            try:
                shutil.copytree(src_profiles, profiles_dir, dirs_exist_ok=True)
            except Exception as e:
                errors.append(str(e))

        if errors:
            self._bk_status_lbl.setText("⚠ Restaurare parțială:\n" + "\n".join(errors))
            self._bk_status_lbl.setStyleSheet("color:#ccaa44; font-size:11px;")
        else:
            self._bk_status_lbl.setText("✅ Restaurare completă. Repornește Cantio.")
            self._bk_status_lbl.setStyleSheet("color:#66cc66; font-size:11px;")

    def _open_backup_folder(self):
        folder = self._get_backup_root()
        os.makedirs(folder, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(folder)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", folder])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", folder])
        except Exception:
            QMessageBox.information(self, "Backup folder", folder)

    # ── Database / Logs tab ───────────────────────────────────────────────────

    def _tab_database(self):
        """Tab: FTS5 reindex + log folder."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # ── FTS5 reindex ──────────────────────────────────────────────────────
        fts_group = QGroupBox("Căutare rapidă (FTS5)")
        fg = QVBoxLayout(fts_group)

        fts_info = QLabel(
            "Indexul FTS5 accelerează căutările la sub 10ms chiar și pentru\n"
            "22.000+ cântări. Reindexează dacă rezultatele căutării par incomplete."
        )
        fts_info.setWordWrap(True)
        fts_info.setStyleSheet("color:#888; font-size:11px;")
        fg.addWidget(fts_info)

        reindex_row = QHBoxLayout()
        self._reindex_btn = QPushButton("🔄 Reindexează cântări (FTS5)")
        self._reindex_btn.setStyleSheet(
            "QPushButton { background:#18283a; color:#5294e2; border:1px solid #1c3a5a; "
            "border-radius:5px; padding:8px 16px; font-weight:600; font-size:12px; }"
            "QPushButton:hover { background:#1c3a5a; color:#fff; }"
        )
        self._reindex_btn.clicked.connect(self._do_reindex)
        reindex_row.addWidget(self._reindex_btn)
        reindex_row.addStretch()
        fg.addLayout(reindex_row)

        self._reindex_status = QLabel("")
        self._reindex_status.setStyleSheet("color:#666; font-size:11px;")
        fg.addWidget(self._reindex_status)

        layout.addWidget(fts_group)

        # ── Log files ─────────────────────────────────────────────────────────
        log_group = QGroupBox("Fișiere jurnal (logs)")
        lg = QVBoxLayout(log_group)

        log_info = QLabel(
            "Cantio salvează un jurnal zilnic în:\n"
            "~/Cantio/logs/\n"
            "Ultimele 7 fișiere sunt păstrate automat."
        )
        log_info.setWordWrap(True)
        log_info.setStyleSheet("color:#888; font-size:11px;")
        lg.addWidget(log_info)

        log_btn_row = QHBoxLayout()
        open_log_btn = QPushButton("📋 Deschide folder log-uri")
        open_log_btn.setStyleSheet(
            "QPushButton { background:#232323; color:#e0e0e0; border:1px solid #2e2e2e; "
            "border-radius:5px; padding:8px 16px; font-size:12px; }"
            "QPushButton:hover { background:#2a2a2a; }"
        )
        open_log_btn.clicked.connect(self._open_log_folder)
        log_btn_row.addWidget(open_log_btn)
        log_btn_row.addStretch()
        lg.addLayout(log_btn_row)

        layout.addWidget(log_group)

        # ── Migration from older Cantio versions ───────────────────────────
        mig_group = QGroupBox("📦 Import date din versiuni vechi")
        mg = QVBoxLayout(mig_group)

        mig_info = QLabel(
            "Dacă ai folosit o versiune mai veche de Cantio, poți importa\n"
            "cântările salvate în baza de date din vechea instalare."
        )
        mig_info.setWordWrap(True)
        mig_info.setStyleSheet("color:#888; font-size:11px;")
        mg.addWidget(mig_info)

        mig_btn_row = QHBoxLayout()

        detect_btn = QPushButton("🔍 Detectează Date Vechi")
        detect_btn.setStyleSheet(
            "QPushButton { background:#18283a; color:#5294e2; border:1px solid #1c3a5a;"
            " border-radius:5px; padding:8px 16px; font-weight:600; font-size:12px; }"
            "QPushButton:hover { background:#1c3a5a; color:#fff; }"
        )
        detect_btn.clicked.connect(self._detect_old_db)
        mig_btn_row.addWidget(detect_btn)

        manual_btn = QPushButton("📁 Import Manual Folder Profil")
        manual_btn.setStyleSheet(
            "QPushButton { background:#232323; color:#e0e0e0; border:1px solid #2e2e2e;"
            " border-radius:5px; padding:8px 16px; font-size:12px; }"
            "QPushButton:hover { background:#2a2a2a; }"
        )
        manual_btn.clicked.connect(self._manual_import_db)
        mig_btn_row.addWidget(manual_btn)

        mig_btn_row.addStretch()
        mg.addLayout(mig_btn_row)

        self._mig_status = QLabel("")
        self._mig_status.setWordWrap(True)
        self._mig_status.setStyleSheet("color:#888; font-size:11px;")
        mg.addWidget(self._mig_status)

        layout.addWidget(mig_group)
        layout.addStretch()
        return self._scrollable(w)

    def _detect_old_db(self):
        """Auto-detect and offer to migrate a legacy Cantio database."""
        try:
            from migration import check_and_migrate, show_migration_dialog
            import database as db_mod
            profile = db_mod.get_active_profile() or "Default"
            old_path = check_and_migrate(profile)
            if old_path:
                self._mig_status.setText(f"✅ Găsit: {old_path}")
                self._mig_status.setStyleSheet("color:#4caf50; font-size:11px;")
                show_migration_dialog(old_path, profile, parent=self)
            else:
                self._mig_status.setText("ℹ Nu s-a găsit nicio bază de date veche.")
                self._mig_status.setStyleSheet("color:#888; font-size:11px;")
        except Exception as e:
            self._mig_status.setText(f"⚠ Eroare: {e}")
            self._mig_status.setStyleSheet("color:#f38ba8; font-size:11px;")

    def _manual_import_db(self):
        """Let the user pick a .db file manually and trigger migration."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Selectează baza de date veche", "", "SQLite DB (*.db);;Toate fișierele (*)"
        )
        if not path:
            return
        try:
            from migration import show_migration_dialog
            import database as db_mod
            profile = db_mod.get_active_profile() or "Default"
            self._mig_status.setText(f"Import din: {path}")
            self._mig_status.setStyleSheet("color:#ccaa44; font-size:11px;")
            show_migration_dialog(path, profile, parent=self)
            self._mig_status.setText("✅ Import finalizat.")
            self._mig_status.setStyleSheet("color:#4caf50; font-size:11px;")
        except Exception as e:
            self._mig_status.setText(f"⚠ Eroare: {e}")
            self._mig_status.setStyleSheet("color:#f38ba8; font-size:11px;")

    def _do_reindex(self):
        """Run FTS5 reindex in a background thread and update status label."""
        self._reindex_btn.setEnabled(False)
        self._reindex_status.setText("⏳ Reindexare în curs…")
        self._reindex_status.setStyleSheet("color:#ccaa44; font-size:11px;")

        import threading

        def _worker():
            count = db.reindex_fts5()
            # Update UI from main thread
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._on_reindex_done(count))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_reindex_done(self, count: int):
        self._reindex_btn.setEnabled(True)
        if count > 0:
            self._reindex_status.setText(f"✅ Reindexate {count} cântări")
            self._reindex_status.setStyleSheet("color:#66cc66; font-size:11px;")
            try:
                from toast_notifications import show_toast
                show_toast(f"✅ Reindexate {count} cântări", "success")
            except Exception:
                pass
        else:
            self._reindex_status.setText("⚠ Reindexare eșuată sau DB goală")
            self._reindex_status.setStyleSheet("color:#f38ba8; font-size:11px;")

    def _open_log_folder(self):
        """Open the log directory in the system file manager."""
        from logger import LOG_DIR
        import os
        os.makedirs(LOG_DIR, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(LOG_DIR)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", LOG_DIR])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", LOG_DIR])
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Log folder", str(LOG_DIR))

    # ── Security / Profile tab ────────────────────────────────────────────────

    def _tab_security(self) -> QWidget:
        """Tab: profile password + restriction management."""
        try:
            current_profile = db.get_active_profile() or "default"
        except Exception:
            current_profile = "default"
        return ProfileSecurityTab(current_profile)

    # ── Values load/collect ───────────────────────────────────────────────────

    def _load_values(self):
        s = self.s
        # Display tab
        # Mod afișare
        if s.get("display_mode", "settings") == "themes":
            self.mode_themes_radio.setChecked(True)
        else:
            self.mode_settings_radio.setChecked(True)

        self.bg_color_btn.set_color(s.get("bg_color", "#000000"))
        img = s.get("bg_image", "")
        self.bg_img_label.setText(img if img else "None")
        self.bg_opacity_slider.setValue(int(float(s.get("bg_opacity", 0.5)) * 100))
        vid = s.get("bg_video", "")
        self.bg_vid_label.setText(vid if vid else "None")

        idx = self.transition_combo.findText(s.get("transition", "fade"))
        if idx >= 0:
            self.transition_combo.setCurrentIndex(idx)
        self.transition_duration.setValue(int(s.get("transition_duration", 350)))

        scr_idx = int(s.get("display_screen", 1))
        self.screen_combo.setCurrentIndex(min(scr_idx, self.screen_combo.count() - 1))
        try:
            st_idx = int(s.get("stage_screen", 0))
            self.stage_screen_combo.setCurrentIndex(
                min(st_idx, self.stage_screen_combo.count() - 1))
        except Exception:
            pass
        _cr = str(s.get("custom_resolution", "false")) == "true"
        self.custom_res_check.setChecked(_cr)
        self.custom_res_w.setEnabled(_cr); self.custom_res_h.setEnabled(_cr)
        try: self.custom_res_w.setValue(int(s.get("custom_res_w", 1920)))
        except Exception: pass
        try: self.custom_res_h.setValue(int(s.get("custom_res_h", 1080)))
        except Exception: pass

        # Text tab
        from PyQt6.QtGui import QFont as QF
        self.font_combo.setCurrentFont(QF(s.get("font_family", "Arial")))
        self.font_size_spin.setValue(int(s.get("font_size", 48)))
        self.bold_check.setChecked(s.get("font_bold", "true") == "true")
        self.italic_check.setChecked(s.get("font_italic", "false") == "true")
        self.text_color_btn.set_color(s.get("text_color", "#ffffff"))
        self.shadow_check.setChecked(s.get("text_shadow", "true") == "true")
        self.outline_color_btn.set_color(s.get("outline_color", "#000000"))
        self.outline_spin.setValue(int(s.get("outline_width", 2)))
        self.line_spacing_spin.setValue(float(s.get("line_spacing", 1.4)))
        self.margin_spin.setValue(int(s.get("margin", 60)))

        hi = self.h_align_combo.findText(s.get("text_align", "center"))
        if hi >= 0:
            self.h_align_combo.setCurrentIndex(hi)
        vi = self.v_align_combo.findText(s.get("text_valign", "center"))
        if vi >= 0:
            self.v_align_combo.setCurrentIndex(vi)

        # Overlays tab
        self.ticker_enabled.setChecked(s.get("ticker_enabled", "false") == "true")
        self.ticker_text.setText(s.get("ticker_text", ""))
        self.ticker_color_btn.set_color(s.get("ticker_color", "#ffffff"))
        self.ticker_speed.setValue(int(s.get("ticker_speed", 2)))
        self.clock_enabled.setChecked(s.get("clock_enabled", "false") == "true")
        self.clock_color_btn.set_color(s.get("clock_color", "#ffffff"))
        ci = self.clock_format.findText(s.get("clock_format", "HH:MM:SS"))
        if ci >= 0:
            self.clock_format.setCurrentIndex(ci)
        self.countdown_enabled.setChecked(s.get("countdown_enabled", "false") == "true")
        self.countdown_seconds.setValue(int(s.get("countdown_seconds", 300)))
        self.countdown_color_btn.set_color(s.get("countdown_color", "#ffffff"))

        # Sacred words tab (Text tab section)
        self.sacred_enabled.setChecked(s.get("sacred_words_enabled", "false") == "true")
        self.sacred_allcaps.setChecked(s.get("sacred_words_allcaps", "false") == "true")
        raw = s.get("sacred_words", "")
        if not raw:
            from text_utils import DEFAULT_SACRED_WORDS
            raw = ",".join(DEFAULT_SACRED_WORDS)
        self.sacred_words_edit.setPlainText("\n".join(w.strip() for w in raw.split(",") if w.strip()))

        # Copyright overlay tab
        try:
            cr_raw = s.get("copyright", "{}")
            cr = json.loads(cr_raw) if isinstance(cr_raw, str) else (cr_raw or {})
        except Exception:
            cr = {}
        if hasattr(self, 'cr_enabled'):
            self.cr_enabled.setChecked(bool(cr.get("enabled", False)))
            # mode
            mode_map = {
                "title_author": 0, "title": 1, "author": 2,
                "category": 3, "source": 4, "custom": 5,
            }
            self.cr_mode.setCurrentIndex(mode_map.get(cr.get("mode", "title_author"), 0))
            self.cr_custom.setText(cr.get("custom_text", ""))
            pos_map = {
                "bottom_right": 0, "bottom_left": 1, "bottom_center": 2,
                "top_right": 3, "top_left": 4,
            }
            self.cr_position.setCurrentIndex(pos_map.get(cr.get("position", "bottom_right"), 0))
            self.cr_font_size.setValue(int(cr.get("font_size", 12)))
            self.cr_color.set_color(cr.get("color", "#ffffff"))
            self.cr_opacity.setValue(int(float(cr.get("opacity", 0.4)) * 100))

        # Supabase tab
        self.supa_url.setText(s.get("supabase_url", ""))
        self.supa_key.setText(s.get("supabase_key", ""))
        self.supa_bucket.setText(s.get("supabase_bucket", "cantio-media"))

        # Interface tab — language
        if hasattr(self, 'lang_combo'):
            current_lang = s.get("language", get_language())
            idx = self.lang_combo.findData(current_lang)
            if idx >= 0:
                self.lang_combo.setCurrentIndex(idx)

    def _collect(self):
        return {
            "display_mode": "themes" if self.mode_themes_radio.isChecked() else "settings",
            "display_screen": str(self.screen_combo.currentData()),
            "stage_screen": str(self.stage_screen_combo.currentData()),
            "custom_resolution": "true" if self.custom_res_check.isChecked() else "false",
            "custom_res_w": str(self.custom_res_w.value()),
            "custom_res_h": str(self.custom_res_h.value()),
            "bg_color": self.bg_color_btn.color(),
            "bg_image": self.bg_img_label.text() if self.bg_img_label.text() != "None" else "",
            "bg_opacity": str(self.bg_opacity_slider.value() / 100.0),
            "bg_video": self.bg_vid_label.text() if self.bg_vid_label.text() != "None" else "",
            "transition": self.transition_combo.currentText(),
            "transition_duration": str(self.transition_duration.value()),
            "font_family": self.font_combo.currentFont().family(),
            "font_size": str(self.font_size_spin.value()),
            "font_bold": "true" if self.bold_check.isChecked() else "false",
            "font_italic": "true" if self.italic_check.isChecked() else "false",
            "text_color": self.text_color_btn.color(),
            "text_shadow": "true" if self.shadow_check.isChecked() else "false",
            "outline_color": self.outline_color_btn.color(),
            "outline_width": str(self.outline_spin.value()),
            "line_spacing": str(self.line_spacing_spin.value()),
            "margin": str(self.margin_spin.value()),
            "text_align": self.h_align_combo.currentText(),
            "text_valign": self.v_align_combo.currentText(),
            "ticker_enabled": "true" if self.ticker_enabled.isChecked() else "false",
            "ticker_text": self.ticker_text.text(),
            "ticker_color": self.ticker_color_btn.color(),
            "ticker_speed": str(self.ticker_speed.value()),
            "clock_enabled": "true" if self.clock_enabled.isChecked() else "false",
            "clock_color": self.clock_color_btn.color(),
            "clock_format": self.clock_format.currentText(),
            "countdown_enabled": "true" if self.countdown_enabled.isChecked() else "false",
            "countdown_seconds": str(self.countdown_seconds.value()),
            "countdown_color": self.countdown_color_btn.color(),
            "overlays": json.dumps(
                self._overlay_adv.collect()
                if hasattr(self, '_overlay_adv') else {},
                ensure_ascii=False,
            ),
            "supabase_url": self.supa_url.text().strip(),
            "supabase_key": self.supa_key.text().strip(),
            "supabase_bucket": self.supa_bucket.text().strip() or "cantio-media",
            "sacred_words_enabled": "true" if self.sacred_enabled.isChecked() else "false",
            "sacred_words_allcaps": "true" if self.sacred_allcaps.isChecked() else "false",
            "sacred_words": self._get_sacred_words_str(),
            "language": self.lang_combo.currentData() if hasattr(self, 'lang_combo') else get_language(),
            "copyright": self._collect_copyright(),
            "ref_font_size":  str(self.br_font_size.value()) if hasattr(self, 'br_font_size') else "24",
            "ref_color":      self.br_color.color()          if hasattr(self, 'br_color')     else "#aaaaaa",
            "ref_italic":     "true" if (hasattr(self, 'br_italic') and self.br_italic.isChecked()) else "false",
            "ref_position":   ["bottom_right", "bottom_left", "bottom_center", "top_right", "top_left", "top_center"][
                               self.br_position.currentIndex()] if hasattr(self, 'br_position') else "bottom_right",
        }

    def _collect_copyright(self) -> str:
        """Return copyright settings serialised as JSON string."""
        if not hasattr(self, 'cr_enabled'):
            return "{}"
        mode_keys = ["title_author", "title", "author", "category", "source", "custom"]
        pos_keys  = ["bottom_right", "bottom_left", "bottom_center", "top_right", "top_left"]
        d = {
            "enabled":     self.cr_enabled.isChecked(),
            "mode":        mode_keys[min(self.cr_mode.currentIndex(), len(mode_keys) - 1)],
            "custom_text": self.cr_custom.text().strip(),
            "position":    pos_keys[min(self.cr_position.currentIndex(), len(pos_keys) - 1)],
            "font_size":   self.cr_font_size.value(),
            "color":       self.cr_color.color(),
            "opacity":     round(self.cr_opacity.value() / 100.0, 2),
        }
        return json.dumps(d, ensure_ascii=False)

    def _get_sacred_words_str(self) -> str:
        raw = self.sacred_words_edit.toPlainText()
        words = [w.strip() for line in raw.splitlines() for w in line.split(",") if w.strip()]
        return ",".join(words)

    def _reset_sacred_words(self):
        from text_utils import DEFAULT_SACRED_WORDS
        self.sacred_words_edit.setPlainText("\n".join(DEFAULT_SACRED_WORDS))

    def _preview_update(self):
        s = self._collect()
        self.preview.apply_settings(s)
        self.preview.update_text("Doamne, Tu ești lumina mea\nȘi mântuirea mea")

    def _pick_bg_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Background Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp *.tiff)"
        )
        if path:
            self.bg_img_label.setText(path)
            self._preview_update()

    def _clear_bg_image(self):
        self.bg_img_label.setText("None")
        self._preview_update()

    def _pick_bg_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Background Video", "",
            "Video (*.mp4 *.mov *.avi *.mkv *.webm)"
        )
        if path:
            self.bg_vid_label.setText(path)

    def _clear_bg_video(self):
        self.bg_vid_label.setText("None")

    def _accept(self):
        settings = self._collect()

        warnings = []

        # ── Font size < 24 px ─────────────────────────────────────────────────
        try:
            font_size = int(settings.get("font_size", 48))
            if font_size < 24:
                warnings.append(
                    f"⚠  Dimensiunea fontului ({font_size}px) este prea mică pentru un display live.\n"
                    "   Se recomandă cel puțin 24px (optim: 48–72px)."
                )
        except ValueError:
            pass

        # ── Low text/background contrast ─────────────────────────────────────
        try:
            text_hex = settings.get("text_color", "#ffffff").lstrip("#")
            bg_hex   = settings.get("bg_color", "#000000").lstrip("#")
            if len(text_hex) == 6 and len(bg_hex) == 6:
                def _luminance(hex6):
                    r, g, b = (int(hex6[i:i+2], 16) / 255 for i in (0, 2, 4))
                    vals = []
                    for c in (r, g, b):
                        vals.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
                    return 0.2126 * vals[0] + 0.7152 * vals[1] + 0.0722 * vals[2]
                lum_text = _luminance(text_hex)
                lum_bg   = _luminance(bg_hex)
                lighter  = max(lum_text, lum_bg)
                darker   = min(lum_text, lum_bg)
                ratio    = (lighter + 0.05) / (darker + 0.05)
                if ratio < 3.0:
                    warnings.append(
                        f"⚠  Contrastul text/fundal este scăzut (raport {ratio:.1f}:1).\n"
                        "   Se recomandă un raport de cel puțin 4.5:1 pentru lizibilitate."
                    )
        except Exception:
            pass

        if warnings:
            warn_text = "\n\n".join(warnings)
            reply = QMessageBox.warning(
                self, "Avertismente setări",
                f"{warn_text}\n\nVrei să salvezi oricum?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Check if language changed
        old_lang = self.s.get("language", get_language())
        new_lang = settings.get("language", old_lang)
        lang_changed = new_lang != old_lang

        db.save_settings(settings)
        # Also persist display window configurations
        if hasattr(self, '_window_configs'):
            db.save_display_configs(self._window_configs)
        self.settingsChanged.emit(settings)

        if lang_changed:
            QMessageBox.information(
                self, t("interface_language"),
                t("restart_required")
            )

        self.accept()


# ── ProfileSecurityTab ────────────────────────────────────────────────────────

class ProfileSecurityTab(QWidget):
    """
    Security tab widget — manages password + restrictions for the active profile.
    Embedded inside SettingsDialog as the 🔒 Securitate tab.
    """

    def __init__(self, current_profile: str, parent=None):
        super().__init__(parent)
        self.profile = current_profile
        self._build_ui()
        self._load_config()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(16, 14, 16, 14)

        # Info
        info_lbl = QLabel(f"Profil curent: <b>{self.profile}</b>")
        info_lbl.setStyleSheet("color: #cba6f7; font-size: 13px;")
        layout.addWidget(info_lbl)

        # ── Password section ───────────────────────────────────────────────────
        pwd_group = QGroupBox("🔒 PAROLĂ PROFIL")
        pwd_layout = QFormLayout(pwd_group)
        pwd_layout.setSpacing(8)

        self.pwd_status = QLabel("Status: Fără parolă")
        self.pwd_status.setStyleSheet("color: #6c7086; font-size: 11px;")
        pwd_layout.addRow("Status:", self.pwd_status)

        self.pwd_new = QLineEdit()
        self.pwd_new.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_new.setPlaceholderText("Parolă nouă (minim 4 caractere)")
        pwd_layout.addRow("Parolă nouă:", self.pwd_new)

        self.pwd_confirm = QLineEdit()
        self.pwd_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_confirm.setPlaceholderText("Confirmă parola")
        pwd_layout.addRow("Confirmă:", self.pwd_confirm)

        pwd_btn_row = QHBoxLayout()
        set_pwd_btn = QPushButton("🔒 Setează Parola")
        set_pwd_btn.setStyleSheet(
            "background:#cba6f7;color:#1e1e2e;font-weight:bold;"
            "border:none;border-radius:6px;padding:6px 14px;")
        set_pwd_btn.clicked.connect(self._set_password)

        remove_pwd_btn = QPushButton("🔓 Elimină Parola")
        remove_pwd_btn.setStyleSheet(
            "background:#313244;color:#f38ba8;"
            "border:1px solid #f38ba8;border-radius:6px;padding:6px 14px;")
        remove_pwd_btn.clicked.connect(self._remove_password)

        pwd_btn_row.addWidget(set_pwd_btn)
        pwd_btn_row.addWidget(remove_pwd_btn)
        pwd_btn_row.addStretch()
        pwd_layout.addRow(pwd_btn_row)
        layout.addWidget(pwd_group)

        # ── Restrictions section ───────────────────────────────────────────────
        restr_group = QGroupBox("🚫 RESTRICȚII UTILIZATOR")
        restr_layout = QVBoxLayout(restr_group)
        restr_layout.setSpacing(6)

        desc = QLabel(
            "Restricțiile limitează ce poate face utilizatorul în acest profil.\n"
            "Util pentru profiluri partajate sau de prezentare.")
        desc.setStyleSheet("color: #6c7086; font-size: 10px;")
        desc.setWordWrap(True)
        restr_layout.addWidget(desc)

        try:
            from profile_security import RESTRICTIONS
            restriction_items = list(RESTRICTIONS.items())
        except Exception:
            restriction_items = []

        self.restriction_checks: dict[str, QCheckBox] = {}
        for key, label in restriction_items:
            cb = QCheckBox(label)
            cb.setStyleSheet("color: #cdd6f4; font-size: 11px;")
            self.restriction_checks[key] = cb
            restr_layout.addWidget(cb)

        save_restr_btn = QPushButton("💾 Salvează Restricții")
        save_restr_btn.setStyleSheet(
            "background:#a6e3a1;color:#1e1e2e;font-weight:bold;"
            "border:none;border-radius:6px;padding:6px 14px;margin-top:8px;")
        save_restr_btn.clicked.connect(self._save_restrictions)
        restr_layout.addWidget(save_restr_btn)

        layout.addWidget(restr_group)
        layout.addStretch()

    # ── Load / save ────────────────────────────────────────────────────────────

    def _load_config(self):
        try:
            from profile_security import has_password, get_restrictions
            if has_password(self.profile):
                self.pwd_status.setText("Status: ✅ Parolă activă")
                self.pwd_status.setStyleSheet("color: #a6e3a1; font-size: 11px;")
            else:
                self.pwd_status.setText("Status: Fără parolă")
                self.pwd_status.setStyleSheet("color: #6c7086; font-size: 11px;")

            restrictions = get_restrictions(self.profile)
            for key, cb in self.restriction_checks.items():
                cb.setChecked(bool(restrictions.get(key, False)))
        except Exception:
            pass

    def _set_password(self):
        try:
            from toast_notifications import show_toast
        except Exception:
            def show_toast(msg, kind="info"): pass

        pwd     = self.pwd_new.text()
        confirm = self.pwd_confirm.text()

        if len(pwd) < 4:
            show_toast("Parola trebuie să aibă\nminim 4 caractere!", "warning")
            return
        if pwd != confirm:
            show_toast("Parolele nu coincid!", "warning")
            self.pwd_confirm.clear()
            self.pwd_confirm.setFocus()
            return

        try:
            from profile_security import set_password
            set_password(self.profile, pwd)
            self.pwd_new.clear()
            self.pwd_confirm.clear()
            self._load_config()
            show_toast(f"✅ Parolă setată pentru profilul '{self.profile}'!", "success")
        except Exception as e:
            show_toast(f"Eroare: {e}", "error")

    def _remove_password(self):
        try:
            from toast_notifications import show_toast
        except Exception:
            def show_toast(msg, kind="info"): pass

        try:
            from profile_security import has_password, set_password
            if not has_password(self.profile):
                show_toast("Profilul nu are parolă!", "info")
                return

            from profile_password_dialog import ProfilePasswordDialog
            from PyQt6.QtWidgets import QDialog
            dlg = ProfilePasswordDialog(self.profile, self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return

            set_password(self.profile, "")
            self._load_config()
            show_toast("🔓 Parola eliminată!", "success")
        except Exception as e:
            show_toast(f"Eroare: {e}", "error")

    def _save_restrictions(self):
        try:
            from toast_notifications import show_toast
        except Exception:
            def show_toast(msg, kind="info"): pass

        try:
            from profile_security import set_restrictions
            restrictions = {k: cb.isChecked() for k, cb in self.restriction_checks.items()}
            set_restrictions(self.profile, restrictions)
            show_toast("✅ Restricții salvate!", "success")
        except Exception as e:
            show_toast(f"Eroare: {e}", "error")
