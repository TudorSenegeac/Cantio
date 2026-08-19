"""
Cantio - Themes Tab
Grid de carduri cu previzualizări PNG pentru teme de afișare.
Suportă drag-and-drop al temei pe cântare din serviciu.
"""
from __future__ import annotations

import copy
import json
import os

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QInputDialog,
    QLabel, QMenu, QMessageBox, QPushButton, QRadioButton, QSlider,
    QSpinBox, QSplitter, QStackedWidget, QTabWidget,
    QVBoxLayout, QWidget, QFontComboBox, QListWidget, QListWidgetItem,
)

import database as db
from settings_dialog import ColorButton
from translations import t
from preview_widget import PreviewWidget

try:
    from theme_editor import (
        NewThemeDialog, ThemeVisualEditor,
        ThemeCard, ThemesGrid, generate_theme_preview,
    )
    _THEME_EDITOR_OK = True
except Exception as _te:
    print(f"[THEMES] theme_editor import failed: {_te}")
    _THEME_EDITOR_OK = False
    NewThemeDialog = ThemeVisualEditor = None          # type: ignore[assignment,misc]
    ThemeCard = ThemesGrid = generate_theme_preview = None  # type: ignore[assignment,misc]

try:
    from toast_notifications import show_toast
except Exception:
    def show_toast(msg, kind="info"):
        print(f"[TOAST] {msg}")


# ── ThemesTab ──────────────────────────────────────────────────────────────────

class ThemesTab(QWidget):
    theme_applied = pyqtSignal(str, str)   # (theme_name, type)
    _theme_saved_sig = pyqtSignal(str)     # Electron theme editor saved (name)

    def __init__(self, parent_control=None):
        super().__init__()
        self.parent_control   = parent_control
        self._current_theme   = None
        self._current_type    = "songs"
        self._preview_threads: list[QThread] = []
        self._build_ui()
        self._refresh_grid()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setStyleSheet(
            "QSplitter::handle { background:#252535; width:4px; }")

        # ── LEFT: grid panel ──────────────────────────────────────────────────
        left   = QWidget()
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 0, 0)
        left_l.setSpacing(4)
        left.setMinimumWidth(190)

        type_row = QHBoxLayout()
        self.type_songs_btn = QPushButton(f"🎵 {t('theme_songs')}")
        self.type_songs_btn.setCheckable(True)
        self.type_songs_btn.setChecked(True)
        self.type_bible_btn = QPushButton(f"📖 {t('theme_bible')}")
        self.type_bible_btn.setCheckable(True)
        self.type_stage_btn = QPushButton("🎭 Stage")
        self.type_stage_btn.setCheckable(True)
        for btn in (self.type_songs_btn, self.type_bible_btn, self.type_stage_btn):
            btn.setStyleSheet(
                "QPushButton { background:#1e1e2e; color:#888; border:1px solid #333;"
                "border-radius:4px; padding:4px 8px; }"
                "QPushButton:checked { background:#1c3a5a; color:#89dceb; "
                "border-color:#5294e2; }"
                "QPushButton:hover { color:#cdd6f4; }")
        self.type_songs_btn.clicked.connect(lambda: self._switch_type("songs"))
        self.type_bible_btn.clicked.connect(lambda: self._switch_type("bible"))
        self.type_stage_btn.clicked.connect(lambda: self._switch_type("stage"))
        type_row.addWidget(self.type_songs_btn)
        type_row.addWidget(self.type_bible_btn)
        type_row.addWidget(self.type_stage_btn)
        left_l.addLayout(type_row)

        # Content stack: theme grid (songs/bible) + stage-arrangements list.
        self._grid_stack = QStackedWidget()
        if _THEME_EDITOR_OK and ThemesGrid is not None:
            self.themes_grid = ThemesGrid()
            self.themes_grid.theme_selected.connect(
                self._on_theme_selected_by_name)
            self.themes_grid.theme_double_clicked.connect(
                self._open_visual_editor)
            self._grid_stack.addWidget(self.themes_grid)
        else:
            self.themes_grid = None
            self._grid_stack.addWidget(
                QLabel("⚠ theme_editor.py nu a putut fi încărcat."))
        # Stage arrangements list (double-click = edit; ★ = default)
        self._stage_list = QListWidget()
        self._stage_list.setStyleSheet(
            "QListWidget { background:#181825; border:1px solid #313244; border-radius:6px;"
            " color:#cdd6f4; } QListWidget::item { padding:8px; }"
            " QListWidget::item:selected { background:#1c3a5a; }")
        self._stage_list.itemDoubleClicked.connect(self._open_stage_arrangement)
        self._grid_stack.addWidget(self._stage_list)
        left_l.addWidget(self._grid_stack, 1)

        # Buttons
        btn_row = QHBoxLayout()
        add_icon = "＋"
        add_cb   = self._on_add_clicked
        for icon, cb in [(add_icon, add_cb),
                         ("⧉", self._duplicate_theme_selected),
                         ("🗑", self._delete_theme_selected)]:
            b = QPushButton(icon)
            b.setFixedWidth(32)
            b.setStyleSheet(
                "QPushButton { background:#1e1e2e; color:#888; border:1px solid #333;"
                "border-radius:4px; font-size:13px; }"
                "QPushButton:hover { background:#252535; color:#cdd6f4; }")
            b.clicked.connect(cb)
            btn_row.addWidget(b)
        btn_row.addStretch()

        save_btn = QPushButton(f"💾 {t('save')}")
        save_btn.setStyleSheet(
            "QPushButton { background:#1c3a2a; color:#a6e3a1; border:1px solid #2a5a3a;"
            "border-radius:4px; padding:4px 8px; }"
            "QPushButton:hover { background:#1f4a30; }")
        save_btn.clicked.connect(self.save_current_theme)
        btn_row.addWidget(save_btn)
        left_l.addLayout(btn_row)

        main_splitter.addWidget(left)

        # ── RIGHT: preview + quick actions ───────────────────────────────────
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(8)

        # Selected theme title
        self.selected_title = QLabel("—")
        self.selected_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selected_title.setStyleSheet(
            "color:#cdd6f4; font-size:14px; font-weight:bold; padding:6px;")
        self.selected_title.setWordWrap(True)
        right_layout.addWidget(self.selected_title)

        right_layout.addStretch(1)

        # Primary buttons: Edit / Set Default
        _btn_top = QHBoxLayout()

        self.edit_btn = QPushButton(t("theme_edit"))
        self.edit_btn.setStyleSheet("""
            QPushButton { background:#313244; color:#cdd6f4;
                border:1px solid #45475a; border-radius:6px;
                padding:8px 16px; font-size:12px; }
            QPushButton:hover { background:#45475a; }
        """)
        self.edit_btn.clicked.connect(self._edit_selected_theme)

        self.apply_btn = QPushButton(t("theme_set_default"))
        self.apply_btn.setStyleSheet("""
            QPushButton { background:#a6e3a1; color:#1e1e2e; border:none;
                border-radius:6px; padding:8px 16px;
                font-weight:bold; font-size:12px; }
            QPushButton:hover { background:#94d49b; }
        """)
        self.apply_btn.clicked.connect(self._apply_selected_theme)

        _btn_top.addWidget(self.edit_btn, 1)
        _btn_top.addWidget(self.apply_btn, 1)
        right_layout.addLayout(_btn_top)

        # Secondary buttons: Duplicate / Delete
        _btn_bot = QHBoxLayout()

        _dup_btn = QPushButton(t("theme_duplicate"))
        _dup_btn.setStyleSheet("""
            QPushButton { background:#313244; color:#cdd6f4;
                border:1px solid #45475a; border-radius:6px;
                padding:6px 12px; }
            QPushButton:hover { background:#45475a; }
        """)
        _dup_btn.clicked.connect(self._duplicate_selected)

        _del_btn = QPushButton(t("theme_delete"))
        _del_btn.setStyleSheet("""
            QPushButton { background:transparent; color:#f38ba8;
                border:1px solid #f38ba8; border-radius:6px;
                padding:6px 12px; }
            QPushButton:hover { background:#f38ba822; }
        """)
        _del_btn.clicked.connect(self._delete_selected)

        _btn_bot.addWidget(_dup_btn)
        _btn_bot.addStretch()
        _btn_bot.addWidget(_del_btn)
        right_layout.addLayout(_btn_bot)

        right_layout.addStretch()
        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([220, 380])

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.addWidget(main_splitter)

    # ── Text tab ─────────────────────────────────────────────────────────────

    def _build_text_tab(self):
        w    = QWidget()
        form = QFormLayout(w)
        form.setSpacing(8)

        self.t_font = QFontComboBox()
        self.t_font.currentFontChanged.connect(self._preview_update)
        form.addRow("Font:", self.t_font)

        self.t_size = QSpinBox()
        self.t_size.setRange(12, 200); self.t_size.setValue(48)
        self.t_size.valueChanged.connect(self._preview_update)
        form.addRow("Mărime:", self.t_size)

        style_row = QHBoxLayout()
        self.t_bold      = QCheckBox("Bold")
        self.t_italic    = QCheckBox("Italic")
        self.t_uppercase = QCheckBox("UPPERCASE")
        for c in (self.t_bold, self.t_italic, self.t_uppercase):
            c.stateChanged.connect(self._preview_update)
            style_row.addWidget(c)
        form.addRow("Stil:", style_row)

        self.t_color = ColorButton("#ffffff")
        self.t_color.colorChanged.connect(self._preview_update)
        form.addRow("Culoare:", self.t_color)

        shadow_row = QHBoxLayout()
        self.t_shadow       = QCheckBox("Shadow")
        self.t_shadow_color = ColorButton("#000000")
        shadow_row.addWidget(self.t_shadow)
        shadow_row.addWidget(self.t_shadow_color)
        form.addRow("Shadow:", shadow_row)

        outline_row = QHBoxLayout()
        self.t_outline_w     = QSpinBox()
        self.t_outline_w.setRange(0, 10)
        self.t_outline_color = ColorButton("#000000")
        outline_row.addWidget(self.t_outline_w)
        outline_row.addWidget(self.t_outline_color)
        form.addRow("Outline:", outline_row)

        self.t_spacing = QDoubleSpinBox()
        self.t_spacing.setRange(1.0, 3.0)
        self.t_spacing.setSingleStep(0.1)
        self.t_spacing.setValue(1.4)
        form.addRow("Line spacing:", self.t_spacing)

        align_row = QHBoxLayout()
        self.t_align_left   = QPushButton("←")
        self.t_align_center = QPushButton("↔")
        self.t_align_right  = QPushButton("→")
        for b in (self.t_align_left, self.t_align_center, self.t_align_right):
            b.setCheckable(True); b.setFixedWidth(40)
            align_row.addWidget(b)
        self.t_align_center.setChecked(True)
        align_row.addStretch()
        form.addRow("Aliniere:", align_row)

        split_row = QHBoxLayout()
        self.t_split_enabled = QCheckBox("Împarte la")
        self.t_split_lines   = QSpinBox()
        self.t_split_lines.setRange(1, 20)
        self.t_split_lines.setValue(4)
        self.t_split_lines.setSuffix(" rânduri")
        split_row.addWidget(self.t_split_enabled)
        split_row.addWidget(self.t_split_lines)
        split_row.addStretch()
        form.addRow("Split:", split_row)

        return w

    # ── Background tab ────────────────────────────────────────────────────────

    def _build_bg_tab(self):
        w      = QWidget()
        layout = QVBoxLayout(w)

        type_group = QGroupBox("Tip fundal")
        type_l     = QVBoxLayout(type_group)

        self.bg_color_radio       = QRadioButton("Culoare solidă")
        self.bg_gradient_radio    = QRadioButton("Gradient")
        self.bg_image_radio       = QRadioButton("Imagine")
        self.bg_video_radio       = QRadioButton("Video")
        self.bg_camera_radio      = QRadioButton("Cameră")
        self.bg_transparent_radio = QRadioButton("Transparent (OBS/streaming)")
        self.bg_color_radio.setChecked(True)

        for r in (self.bg_color_radio, self.bg_gradient_radio,
                  self.bg_image_radio,  self.bg_video_radio,
                  self.bg_camera_radio, self.bg_transparent_radio):
            type_l.addWidget(r)
            r.toggled.connect(self._on_bg_type_changed)
        layout.addWidget(type_group)

        self.bg_stack = QStackedWidget()

        # 0: Culoare
        cw = QWidget(); cl = QFormLayout(cw)
        self.bg_color_btn = ColorButton("#000000")
        self.bg_color_btn.colorChanged.connect(self._preview_update)
        cl.addRow("Culoare:", self.bg_color_btn)
        self.bg_stack.addWidget(cw)

        # 1: Gradient
        gw = QWidget(); gl = QFormLayout(gw)
        self.bg_grad_color1 = ColorButton("#000033")
        self.bg_grad_color2 = ColorButton("#000000")
        self.bg_grad_dir    = QComboBox()
        self.bg_grad_dir.addItems(
            ["Sus → Jos", "Stânga → Dreapta", "Diagonal", "Radial"])
        gl.addRow("Culoare 1:", self.bg_grad_color1)
        gl.addRow("Culoare 2:", self.bg_grad_color2)
        gl.addRow("Direcție:",   self.bg_grad_dir)
        self.bg_stack.addWidget(gw)

        # 2: Imagine
        iw = QWidget(); il = QFormLayout(iw)
        img_row = QHBoxLayout()
        self.bg_img_label = QLabel("Niciuna")
        self.bg_img_label.setStyleSheet("color:#6c7086; font-size:11px;")
        bg_browse = QPushButton("Browse…")
        bg_browse.clicked.connect(self._browse_bg_image)
        img_row.addWidget(self.bg_img_label, 1); img_row.addWidget(bg_browse)
        il.addRow("Fișier:", img_row)
        self.bg_img_opacity = QSlider(Qt.Orientation.Horizontal)
        self.bg_img_opacity.setRange(0, 100); self.bg_img_opacity.setValue(85)
        il.addRow("Opacitate:", self.bg_img_opacity)
        self.bg_stack.addWidget(iw)

        # 3: Video
        vw = QWidget(); vl = QFormLayout(vw)
        vid_row = QHBoxLayout()
        self.bg_vid_label = QLabel("Niciun video")
        self.bg_vid_label.setStyleSheet("color:#6c7086; font-size:11px;")
        vid_browse = QPushButton("Browse…")
        vid_browse.clicked.connect(self._browse_bg_video)
        vid_row.addWidget(self.bg_vid_label, 1); vid_row.addWidget(vid_browse)
        vl.addRow("Fișier:", vid_row)
        self.bg_vid_opacity = QSlider(Qt.Orientation.Horizontal)
        self.bg_vid_opacity.setRange(0, 100); self.bg_vid_opacity.setValue(100)
        vl.addRow("Opacitate:", self.bg_vid_opacity)
        self.bg_stack.addWidget(vw)

        # 4: Cameră — camera itself is chosen globally in Media → Feeds, so the
        # theme just says "use the camera". No per-theme camera picker here.
        camw = QWidget(); caml = QVBoxLayout(camw)
        cam_info = QLabel("📷 Fundalul folosește camera activă.\n\n"
                          "Alege sau schimbă camera din:\nMedia → Feeds.")
        cam_info.setStyleSheet("color:#9aa; font-size:11px;")
        cam_info.setWordWrap(True)
        caml.addWidget(cam_info)
        caml.addStretch()
        # Kept for backward-compat with code that references it (hidden, unused).
        self.bg_cam_combo = QComboBox(); self.bg_cam_combo.hide()
        self.bg_stack.addWidget(camw)

        # 5: Transparent
        tw = QWidget(); tl = QVBoxLayout(tw)
        tinfo = QLabel(
            "Fereastra live va fi complet transparentă — se vede desktopul.\n\n"
            "Util pentru:\n• OBS cu Window Capture\n"
            "• Streaming cu overlay\n• Chroma key")
        tinfo.setStyleSheet("color:#cdd6f4; font-size:12px;")
        tl.addWidget(tinfo); tl.addStretch()
        self.bg_stack.addWidget(tw)

        layout.addWidget(self.bg_stack)
        return w

    # ── Layout tab ────────────────────────────────────────────────────────────

    def _build_layout_tab(self):
        w      = QWidget()
        layout = QVBoxLayout(w)

        splitter  = QSplitter(Qt.Orientation.Horizontal)
        editor_w  = QWidget()
        form      = QFormLayout(editor_w)

        self.l_margin = QSpinBox()
        self.l_margin.setRange(0, 400); self.l_margin.setValue(80)
        form.addRow("Margine (px):", self.l_margin)

        self.l_valign = QComboBox()
        self.l_valign.addItems(["Sus", "Centru", "Jos"])
        self.l_valign.setCurrentIndex(1)
        form.addRow("Aliniere verticală:", self.l_valign)

        self.bible_zone_group = QGroupBox(
            "Zone Biblie (doar pt teme Biblie)")
        self.bible_zone_group.setVisible(self._current_type == "bible")
        bf = QFormLayout(self.bible_zone_group)

        def _sp(rng_max, suffix, val):
            sb = QSpinBox()
            sb.setRange(0, rng_max); sb.setSuffix(suffix); sb.setValue(val)
            return sb

        self.l_verse_x = _sp(100, "%", 10); self.l_verse_y = _sp(100, "%", 20)
        self.l_verse_w = _sp(100, "%", 80); self.l_verse_h = _sp(100, "%", 50)
        vp = QHBoxLayout()
        for lbl, sp in [("X:", self.l_verse_x), ("Y:", self.l_verse_y),
                        ("W:", self.l_verse_w), ("H:", self.l_verse_h)]:
            vp.addWidget(QLabel(lbl)); vp.addWidget(sp)
        bf.addRow("Verset:", vp)

        self.l_ref_x = _sp(100, "%", 60); self.l_ref_y = _sp(100, "%", 75)
        self.l_ref_w = _sp(100, "%", 30); self.l_ref_h = _sp(50,  "%", 15)
        rp = QHBoxLayout()
        for lbl, sp in [("X:", self.l_ref_x), ("Y:", self.l_ref_y),
                        ("W:", self.l_ref_w), ("H:", self.l_ref_h)]:
            rp.addWidget(QLabel(lbl)); rp.addWidget(sp)
        bf.addRow("Referință:", rp)

        self.l_ref_size  = QSpinBox()
        self.l_ref_size.setRange(8, 80); self.l_ref_size.setValue(24)
        self.l_ref_color = ColorButton("#aaaaaa")
        bf.addRow("Font referință:", self.l_ref_size)
        bf.addRow("Culoare referință:", self.l_ref_color)

        form.addRow(self.bible_zone_group)
        splitter.addWidget(editor_w)

        self.layout_preview = PreviewWidget()
        self.layout_preview.setMinimumWidth(220)
        splitter.addWidget(self.layout_preview)
        splitter.setSizes([280, 220])

        layout.addWidget(splitter)
        return w

    # ── Advanced tab ──────────────────────────────────────────────────────────

    def _build_advanced_tab(self):
        w    = QWidget()
        form = QFormLayout(w)
        form.setSpacing(8)

        self.a_transition = QComboBox()
        self.a_transition.addItems(
            ["instant", "fade", "crossfade", "slide_left", "zoom_in"])
        self.a_transition.setCurrentIndex(2)
        form.addRow("Tranziție:", self.a_transition)

        self.a_duration = QSpinBox()
        self.a_duration.setRange(50, 2000)
        self.a_duration.setValue(350)
        self.a_duration.setSuffix(" ms")
        form.addRow("Durată tranziție:", self.a_duration)

        cr_group = QGroupBox("Copyright")
        crf      = QFormLayout(cr_group)
        self.a_cr_enabled = QCheckBox("Afișează copyright")
        self.a_cr_mode    = QComboBox()
        self.a_cr_mode.addItems(["Titlu", "Autor", "Titlu + Autor",
                                  "Categorie", "Sursă", "Text custom"])
        self.a_cr_pos     = QComboBox()
        self.a_cr_pos.addItems(["Dreapta jos", "Stânga jos", "Centru jos",
                                 "Dreapta sus", "Stânga sus"])
        self.a_cr_opacity = QSlider(Qt.Orientation.Horizontal)
        self.a_cr_opacity.setRange(10, 100); self.a_cr_opacity.setValue(40)
        crf.addRow("",           self.a_cr_enabled)
        crf.addRow("Conținut:",  self.a_cr_mode)
        crf.addRow("Poziție:",   self.a_cr_pos)
        crf.addRow("Opacitate:", self.a_cr_opacity)
        form.addRow(cr_group)

        return w

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _on_bg_type_changed(self):
        for i, r in enumerate([self.bg_color_radio, self.bg_gradient_radio,
                                self.bg_image_radio, self.bg_video_radio,
                                self.bg_camera_radio, self.bg_transparent_radio]):
            if r.isChecked():
                self.bg_stack.setCurrentIndex(i)
                break
        self._preview_update()

    def _detect_cameras(self):
        try:
            import cv2
            self.bg_cam_combo.clear()
            for i in range(5):
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    self.bg_cam_combo.addItem(f"Cameră {i}", i)
                    cap.release()
            if self.bg_cam_combo.count() == 0:
                show_toast("Nu s-au găsit camere", "warning")
        except ImportError:
            show_toast("opencv-python lipsește — pip install opencv-python",
                       "warning")

    def _browse_bg_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selectează imagine", "",
            "Imagini (*.jpg *.jpeg *.png *.webp *.bmp)")
        if path:
            self.bg_img_label.setText(path)
            self._preview_update()

    def _browse_bg_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selectează video", "",
            "Video (*.mp4 *.mov *.avi *.mkv *.webm)")
        if path:
            self.bg_vid_label.setText(path)
            self._preview_update()

    def _preview_update(self):
        if hasattr(self, "layout_preview"):
            s = self._collect_theme_settings()
            self.layout_preview.apply_settings(s)
            self.layout_preview.update_text(
                "Doamne, Tu ești lumina mea\nȘi mântuirea mea")

    def _collect_theme_settings(self) -> dict:
        s: dict = {}
        try:
            s["font_family"]  = self.t_font.currentFont().family()
            s["font_size"]    = str(self.t_size.value())
            s["font_bold"]    = "true" if self.t_bold.isChecked()    else "false"
            s["font_italic"]  = "true" if self.t_italic.isChecked()  else "false"
            s["text_color"]   = self.t_color.color()
            s["text_shadow"]  = "true" if self.t_shadow.isChecked()  else "false"
            s["outline_width"]= str(self.t_outline_w.value())
            s["outline_color"]= self.t_outline_color.color()
            s["line_spacing"] = str(self.t_spacing.value())
            s["margin"]       = str(self.l_margin.value())
            s["transition"]   = self.a_transition.currentText()
            s["transition_duration"] = str(self.a_duration.value())

            bg_idx   = self.bg_stack.currentIndex()
            bg_types = ["color", "gradient", "image", "video", "camera", "transparent"]
            s["bg_type"] = bg_types[bg_idx]
            if bg_idx == 0:
                s["bg_color"] = self.bg_color_btn.color()
            elif bg_idx == 2:
                s["bg_image"]   = self.bg_img_label.text()
                s["bg_opacity"] = str(self.bg_img_opacity.value() / 100.0)
            elif bg_idx == 3:
                s["bg_video"]   = self.bg_vid_label.text()
                s["bg_opacity"] = str(self.bg_vid_opacity.value() / 100.0)
            elif bg_idx == 5:
                s["bg_transparent"] = "true"
                s["bg_color"]       = "#00000000"
        except Exception:
            pass
        return s

    # ── Themes persistence ─────────────────────────────────────────────────────

    def _themes_path(self) -> str:
        profile = getattr(self.parent_control, "_profile_name",
                  getattr(self.parent_control, "_current_profile", "default"))
        profile_dir = os.path.join(
            os.path.expanduser("~"), "Cantio", "profiles", profile)
        return os.path.join(profile_dir, "themes.json")

    def _load_themes(self) -> dict:
        path = self._themes_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "songs_active": "Default Cântări",
            "bible_active": "Default Biblie",
            "category_themes": {},
            "list": {
                "Default Cântări": {
                    "type": "songs",
                    "text": {}, "background": {"type": "color", "color": "#000000"},
                    "layout": {}, "advanced": {},
                },
                "Default Biblie": {
                    "type": "bible",
                    "text": {}, "background": {"type": "color", "color": "#000033"},
                    "layout": {
                        "verse_zone": {"x": 10, "y": 15, "w": 80, "h": 55},
                        "ref_zone":   {"x": 60, "y": 75, "w": 35, "h": 15},
                        "ref_font_size": 24, "ref_color": "#aaaaaa",
                    },
                    "advanced": {},
                },
            },
        }

    def _save_themes(self, themes: dict):
        path = self._themes_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(themes, f, ensure_ascii=False, indent=2)

    # ── Grid helpers ──────────────────────────────────────────────────────────

    def _preview_dir(self) -> str:
        profile = getattr(self.parent_control, "_profile_name",
                  getattr(self.parent_control, "_current_profile", "default"))
        d = os.path.join(
            os.path.expanduser("~"), "Cantio", "profiles",
            profile, "theme_previews")
        os.makedirs(d, exist_ok=True)
        return d

    def _refresh_grid(self):
        """Repopulează gridul cu temele filtrare pe tipul curent."""
        if self.themes_grid is None:
            return
        themes  = self._load_themes()
        active  = themes.get(f"{self._current_type}_active", "")
        filtered = {
            k: v for k, v in themes["list"].items()
            if v.get("type") in (self._current_type, "both")
        }
        self.themes_grid.populate(filtered, active, self._preview_dir())

    # backward-compat aliases
    def _load_themes_list(self):
        self._refresh_grid()

    def _refresh_list(self):
        self._refresh_grid()

    # ── Type switch ───────────────────────────────────────────────────────────

    def _switch_type(self, t_type: str):
        self._current_type = t_type
        self.type_songs_btn.setChecked(t_type == "songs")
        self.type_bible_btn.setChecked(t_type == "bible")
        if hasattr(self, "type_stage_btn"):
            self.type_stage_btn.setChecked(t_type == "stage")
        if hasattr(self, "bible_zone_group"):
            self.bible_zone_group.setVisible(t_type == "bible")
        if t_type == "stage":
            self._grid_stack.setCurrentIndex(1)
            self._refresh_stage_list()
        else:
            self._grid_stack.setCurrentIndex(0)
            self._refresh_grid()

    # ── Stage arrangements (layouts for the confidence-monitor window) ─────────
    def _stage_layouts(self) -> dict:
        try:
            return json.loads(db.get_settings().get("stage_layouts", "{}") or "{}")
        except Exception:
            return {}

    def _refresh_stage_list(self):
        if not hasattr(self, "_stage_list"):
            return
        self._stage_list.clear()
        try:
            active = db.get_settings().get("stage_active_layout", "")
        except Exception:
            active = ""
        for name in self._stage_layouts().keys():
            it = QListWidgetItem(("★  " if name == active else "🎭  ") + name)
            it.setData(Qt.ItemDataRole.UserRole, name)
            self._stage_list.addItem(it)
        if not self._stage_list.count():
            hint = QListWidgetItem("(niciun aranjament — apasă ＋ ca să creezi)")
            hint.setFlags(Qt.ItemFlag.NoItemFlags)
            self._stage_list.addItem(hint)

    def _open_stage_arrangement(self, item=None):
        name = item.data(Qt.ItemDataRole.UserRole) if item else None
        self._open_stage_editor(name)

    def _open_stage_editor(self, name=None):
        from stage_monitor import StageEditorWindow
        win = getattr(self, "_stage_editor_win", None)
        if win is None or not win.isVisible():
            self._stage_editor_win = StageEditorWindow(parent=None)
            win = self._stage_editor_win
        win.show(); win.raise_(); win.activateWindow()
        if name:
            try:
                layouts = self._stage_layouts()
                if name in layouts and hasattr(win, "canvas"):
                    win.canvas.set_widgets(layouts[name])
            except Exception:
                pass
        QTimer.singleShot(400, self._refresh_stage_list)

    def _new_stage_arrangement(self):
        self._open_stage_editor(None)

    def _on_add_clicked(self):
        if getattr(self, "_current_type", "") == "stage":
            self._new_stage_arrangement()
        elif _THEME_EDITOR_OK:
            self._new_theme_with_dialog()
        else:
            self._new_theme()

    def _set_stage_default(self):
        it = self._stage_list.currentItem()
        if not it or not it.data(Qt.ItemDataRole.UserRole):
            show_toast("Selectează un aranjament", "warning"); return
        name = it.data(Qt.ItemDataRole.UserRole)
        db.save_setting("stage_active_layout", name)
        self._refresh_stage_list()
        show_toast(f"★ Stage default: {name}", "success")

    def _delete_stage_arrangement(self):
        it = self._stage_list.currentItem()
        if not it or not it.data(Qt.ItemDataRole.UserRole):
            return
        name = it.data(Qt.ItemDataRole.UserRole)
        layouts = self._stage_layouts()
        layouts.pop(name, None)
        db.save_setting("stage_layouts", json.dumps(layouts))
        self._refresh_stage_list()

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def _new_theme(self):
        """Fallback: creare temă simplă fără dialog avansat."""
        name, ok = QInputDialog.getText(self, "Temă nouă", "Nume temă:")
        if ok and name.strip():
            themes = self._load_themes()
            themes["list"][name.strip()] = {
                "type": self._current_type,
                "text": {}, "background": {"type": "color", "color": "#000000"},
                "layout": {}, "advanced": {},
            }
            self._save_themes(themes)
            self._refresh_grid()

    def _new_theme_with_dialog(self):
        """Deschide NewThemeDialog → creează tema → deschide editorul vizual."""
        if NewThemeDialog is None:
            self._new_theme()
            return

        dlg = NewThemeDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        name   = dlg.get_name()
        t_type = dlg.get_type()
        aspect = dlg.get_aspect()
        res_w, res_h = dlg.get_resolution()

        if not name:
            return

        themes = self._load_themes()
        themes["list"][name] = {
            "type":         t_type,
            "aspect_ratio": aspect,
            "resolution":   {"width": res_w, "height": res_h},
            "text":         {},
            "background":   {"type": "color", "color": "#000000"},
            "layout":       {},
            "advanced":     {},
        }
        self._save_themes(themes)
        self._regenerate_preview(name)
        self._refresh_grid()
        self._open_visual_editor(name)

    def _duplicate_theme(self, name: str):
        new_name, ok = QInputDialog.getText(
            self, "Duplică temă", "Nume temă nouă:", text=f"{name} (copie)")
        if ok and new_name.strip():
            themes = self._load_themes()
            themes["list"][new_name.strip()] = copy.deepcopy(
                themes["list"].get(name, {}))
            self._save_themes(themes)
            self._refresh_grid()

    def _duplicate_theme_selected(self):
        name = self.themes_grid.selected_name() if self.themes_grid else None
        if name:
            self._duplicate_theme(name)

    def _rename_theme(self, name: str):
        new_name, ok = QInputDialog.getText(
            self, "Redenumește", "Nume nou:", text=name)
        if ok and new_name.strip():
            themes = self._load_themes()
            if name in themes["list"]:
                themes["list"][new_name.strip()] = themes["list"].pop(name)
                for key in ("songs_active", "bible_active"):
                    if themes.get(key) == name:
                        themes[key] = new_name.strip()
                self._save_themes(themes)
                self._refresh_grid()

    def _delete_theme(self, name: str):
        if QMessageBox.question(
            self, "Șterge", f"Ștergi tema '{name}'?"
        ) == QMessageBox.StandardButton.Yes:
            themes = self._load_themes()
            themes["list"].pop(name, None)
            self._save_themes(themes)
            # Remove preview PNG
            safe = name.replace("/", "_").replace("\\", "_")
            preview = os.path.join(self._preview_dir(), f"{safe}.png")
            try:
                if os.path.exists(preview):
                    os.remove(preview)
            except Exception:
                pass
            self._refresh_grid()

    def _delete_theme_selected(self):
        if getattr(self, "_current_type", "") == "stage":
            self._delete_stage_arrangement(); return
        name = self.themes_grid.selected_name() if self.themes_grid else None
        if name:
            self._delete_theme(name)

    def _set_default(self, theme_name: str):
        themes = self._load_themes()
        t_type = themes["list"].get(theme_name, {}).get("type", "songs")
        if t_type in ("songs", "both"):
            themes["songs_active"] = theme_name
        if t_type in ("bible", "both"):
            themes["bible_active"] = theme_name
        self._save_themes(themes)
        self._refresh_grid()
        show_toast(f"★ '{theme_name}' default", "success")

    def _set_for_category(self, theme_name: str, category: str):
        themes = self._load_themes()
        themes.setdefault("category_themes", {})[category] = theme_name
        self._save_themes(themes)
        show_toast(f"✅ '{theme_name}' → {category}", "success")

    def _set_for_song(self, theme_name: str):
        """Save the theme as the CURRENT song's theme (song_themes[song_id]) and
        apply it live. Switching to another song then auto-uses that song's theme,
        falling back to its category default (unless it too has its own theme)."""
        pc = self.parent_control
        song_id = getattr(pc, "current_song_id", None) if pc else None
        if song_id is None:
            show_toast("Încarcă o cântare mai întâi", "warning")
            return
        themes = self._load_themes()
        themes.setdefault("song_themes", {})[str(song_id)] = theme_name
        self._save_themes(themes)
        # Per-song themes only resolve in "themes" mode — turn it on so it takes effect.
        try:
            if pc.settings.get("display_mode") != "themes":
                pc.settings["display_mode"] = "themes"
                import database as _db
                _db.save_setting("display_mode", "themes")
        except Exception:
            pass
        # Apply to preview + thumbnails + any live display immediately.
        try: pc._apply_current_song_theme_live()
        except Exception: pass
        title = ""
        try: title = (pc._current_metadata or {}).get("title", "")
        except Exception: pass
        show_toast(f"🎵 '{theme_name}' → «{title or 'cântarea curentă'}»", "success")

    # ── Context menus ─────────────────────────────────────────────────────────

    def _context_menu_for(self, theme_name: str, event):
        """Context menu trigerat de ThemeCard.contextMenuEvent."""
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#313244; color:#cdd6f4;"
            "border:1px solid #45475a; border-radius:6px; padding:4px; }"
            "QMenu::item { padding:6px 20px; border-radius:4px; }"
            "QMenu::item:selected { background:#45475a; }")

        menu.addAction("✏ Editează").triggered.connect(
            lambda: self._open_visual_editor(theme_name))
        menu.addAction("📋 Duplică").triggered.connect(
            lambda: self._duplicate_theme(theme_name))
        menu.addAction("✏ Redenumește").triggered.connect(
            lambda: self._rename_theme(theme_name))
        menu.addSeparator()
        # Per-song assignment (only meaningful when a song is loaded)
        song_title = ""
        try:
            song_title = (self.parent_control._current_metadata or {}).get("title", "")
        except Exception:
            pass
        if getattr(self.parent_control, "current_song_id", None) is not None:
            label = f"🎵 Aplică pe «{song_title}»" if song_title else "🎵 Aplică pe cântarea curentă"
            menu.addAction(label).triggered.connect(
                lambda: self._set_for_song(theme_name))
        menu.addAction("★ Setează ca default").triggered.connect(
            lambda: self._set_default(theme_name))

        genre_menu = menu.addMenu("📁 Setează pentru categorie")
        try:
            categories = db.get_all_categories()
        except Exception:
            categories = []
        default_cats = ["General", "Imnuri", "Psalmi", "Colinde",
                        "Copii", "Tineret", "Laudă și Închinare",
                        "Rugăciune", "Speciale"]
        all_cats = list(dict.fromkeys(default_cats + list(categories)))
        for cat in all_cats:
            genre_menu.addAction(f"📁 {cat}").triggered.connect(
                lambda checked, c=cat, t=theme_name:
                    self._set_for_category(t, c))

        menu.addSeparator()
        menu.addAction("🗑 Șterge").triggered.connect(
            lambda: self._delete_theme(theme_name))

        try:
            menu.exec(event.globalPos())
        except AttributeError:
            menu.exec(event.globalPosition().toPoint())

    # Legacy context menu (kept for backward compat — not wired)
    def _context_menu(self, pos: QPoint):
        pass

    # ── Selection / load ──────────────────────────────────────────────────────

    def _on_theme_selected_by_name(self, name: str):
        """Slot: card clicked în ThemesGrid — update title label."""
        self._current_theme = name
        self.selected_title.setText(name)

    def _select_theme_by_name(self, name: str):
        self._current_theme = name
        if self.themes_grid:
            self.themes_grid._select(name)
        themes = self._load_themes()
        self._load_theme_to_ui(themes["list"].get(name, {}))

    def _on_theme_selected(self, item):
        """Legacy — kept for backward compat (not connected in new UI)."""
        try:
            name = item.data(Qt.ItemDataRole.UserRole)
            self._on_theme_selected_by_name(name)
        except Exception:
            pass

    def _load_theme_to_ui(self, theme: dict):
        t  = theme.get("text",       {})
        bg = theme.get("background", {})
        a  = theme.get("advanced",   {})
        l  = theme.get("layout",     {})

        if t.get("font_family"):
            self.t_font.setCurrentFont(QFont(t["font_family"]))
        if t.get("font_size"):
            try: self.t_size.setValue(int(t["font_size"]))
            except (ValueError, TypeError): pass
        self.t_bold.setChecked(t.get("font_bold")    == "true")
        self.t_italic.setChecked(t.get("font_italic") == "true")
        self.t_uppercase.setChecked(t.get("uppercase") == "true")
        if t.get("text_color"):
            self.t_color.set_color(t["text_color"])

        bg_type = bg.get("type", "color")
        bg_map  = {"color": 0, "gradient": 1, "image": 2,
                   "video": 3, "camera": 4, "transparent": 5}
        idx = bg_map.get(bg_type, 0)
        for i, r in enumerate([self.bg_color_radio, self.bg_gradient_radio,
                                self.bg_image_radio, self.bg_video_radio,
                                self.bg_camera_radio, self.bg_transparent_radio]):
            r.setChecked(i == idx)
        self.bg_stack.setCurrentIndex(idx)
        if bg.get("color"):  self.bg_color_btn.set_color(bg["color"])
        if bg.get("image"):  self.bg_img_label.setText(bg["image"])
        if bg.get("opacity"):
            try:
                self.bg_img_opacity.setValue(
                    int(float(bg["opacity"]) * 100))
            except (ValueError, TypeError): pass

        if a.get("transition"):
            self.a_transition.setCurrentText(a["transition"])
        if a.get("transition_duration"):
            try: self.a_duration.setValue(int(a["transition_duration"]))
            except (ValueError, TypeError): pass

        vz = l.get("verse_zone", {})
        if vz:
            self.l_verse_x.setValue(vz.get("x", 10))
            self.l_verse_y.setValue(vz.get("y", 20))
            self.l_verse_w.setValue(vz.get("w", 80))
            self.l_verse_h.setValue(vz.get("h", 50))
        rz = l.get("ref_zone", {})
        if rz:
            self.l_ref_x.setValue(rz.get("x", 60))
            self.l_ref_y.setValue(rz.get("y", 75))
            self.l_ref_w.setValue(rz.get("w", 30))
            self.l_ref_h.setValue(rz.get("h", 15))
        if l.get("ref_font_size"):
            try: self.l_ref_size.setValue(int(l["ref_font_size"]))
            except (ValueError, TypeError): pass
        if l.get("ref_color"):
            self.l_ref_color.set_color(l["ref_color"])

    # ── Visual editor ─────────────────────────────────────────────────────────

    def _open_visual_editor(self, theme_name: str):
        """Open the FULL ELECTRON theme editor (live render + sample text). Falls
        back to the old PyQt editor only if the Electron subsystem is unavailable."""
        themes = self._load_themes()
        theme  = themes["list"].get(theme_name, {})
        mgr = getattr(self.parent_control, "electron_display", None) if self.parent_control else None
        if mgr is not None and hasattr(mgr, "open_theme_editor"):
            if not getattr(self, "_theme_saved_wired", False):
                try:
                    mgr.set_theme_saved_callback(
                        lambda name: self._theme_saved_sig.emit(name))
                    self._theme_saved_sig.connect(self._merge_saved_theme)
                    self._theme_saved_wired = True
                except Exception:
                    pass
            mgr.open_theme_editor(theme_name, theme)
            return
        # Fallback: legacy PyQt editor
        if ThemeVisualEditor is None:
            show_toast("Editorul de teme indisponibil", "warning")
            return
        editor = ThemeVisualEditor(
            theme_name=theme_name, theme_data=theme,
            preview_dir=self._preview_dir(), parent=self)
        editor.theme_saved.connect(self._on_theme_saved)
        editor.show()

    def _merge_saved_theme(self, name: str):
        """Electron theme editor saved → read the temp file and merge into themes.json
        (preserving any keys the editor didn't touch)."""
        import os, tempfile
        d = os.path.join(tempfile.gettempdir(), "cantio")
        safe = "".join(c for c in str(name) if c.isalnum() or c in " -_").strip() or "tema"
        path = os.path.join(d, f"theme_edit_{safe}.json")
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            data = raw.get("theme", {}) or {}
        except Exception:
            return
        themes = self._load_themes()
        old = themes["list"].get(name, {}) or {}
        for k, v in data.items():          # merge sub-sections, preserve the rest
            if isinstance(v, dict) and isinstance(old.get(k), dict):
                old[k].update(v)
            else:
                old[k] = v
        themes["list"][name] = old
        self._save_themes(themes)
        self._refresh_grid()
        try:
            show_toast(f"🎨 Temă salvată: {name}", "success")
        except Exception:
            pass

    def _on_theme_saved(self, name: str, data: dict):
        themes = self._load_themes()
        themes["list"][name] = data
        self._save_themes(themes)
        self._regenerate_preview(name)
        show_toast(f"✅ Tema '{name}' salvată", "success")

    # ── Preview generation ────────────────────────────────────────────────────

    def _regenerate_preview(self, theme_name: str):
        """Generează PNG preview pe thread secundar."""
        if generate_theme_preview is None:
            return
        themes = self._load_themes()
        theme  = themes["list"].get(theme_name, {})
        safe   = theme_name.replace("/", "_").replace("\\", "_")
        path   = os.path.join(self._preview_dir(), f"{safe}.png")

        class _PreviewThread(QThread):
            done = pyqtSignal(str)

            def __init__(self_, t, p):
                super().__init__()
                self_._theme = t
                self_._path  = p

            def run(self_):
                try:
                    generate_theme_preview(self_._theme, self_._path)
                    self_.done.emit(theme_name)
                except Exception as e:
                    print(f"[Preview] {e}")

        thread = _PreviewThread(theme, path)
        thread.done.connect(self._refresh_card)
        thread.start()
        self._preview_threads.append(thread)
        # Prune finished threads
        self._preview_threads = [t for t in self._preview_threads
                                  if t.isRunning()]

    def _refresh_card(self, theme_name: str):
        """Reîncarcă gridul după regenerarea unui preview."""
        self._refresh_grid()

    # ── Right-panel action methods ────────────────────────────────────────────

    def _edit_selected_theme(self):
        """Open ThemeVisualEditor for the selected theme (or create new if none)."""
        if not self._current_theme:
            self._new_theme_with_dialog()
            return
        self._open_visual_editor(self._current_theme)

    def _apply_selected_theme(self):
        """Apply the selected theme. If a song is loaded, assign it to THAT song
        (per-song theme); otherwise set it as the global default for its type."""
        if getattr(self, "_current_type", "") == "stage":
            self._set_stage_default(); return
        name = self._current_theme
        if not name:
            show_toast("Selectează o temă mai întâi", "warning")
            return
        if getattr(self.parent_control, "current_song_id", None) is not None:
            self._set_for_song(name)
        else:
            self._set_default(name)

    def _duplicate_selected(self):
        """Duplicate the selected theme."""
        name = self._current_theme
        if not name:
            show_toast("Selectează o temă mai întâi", "warning")
            return
        self._duplicate_theme(name)

    def _delete_selected(self):
        """Delete the selected theme with confirmation."""
        name = self._current_theme
        if not name:
            return
        if QMessageBox.question(
            self, "Șterge temă",
            f"Ștergi tema '{name}'?\nAcțiunea nu poate fi anulată!",
        ) == QMessageBox.StandardButton.Yes:
            themes = self._load_themes()
            themes["list"].pop(name, None)
            if themes.get("songs_active") == name:
                themes["songs_active"] = ""
            if themes.get("bible_active") == name:
                themes["bible_active"] = ""
            self._save_themes(themes)
            safe = name.replace("/", "_").replace("\\", "_")
            preview = os.path.join(self._preview_dir(), f"{safe}.png")
            try:
                if os.path.exists(preview):
                    os.remove(preview)
            except Exception:
                pass
            self._current_theme = None
            self._refresh_grid()
            if hasattr(self, "selected_title"):
                self.selected_title.setText("—")
            show_toast(f"🗑 '{name}' ștearsă", "info")

    # ── Safe no-ops for the removed inline editor ─────────────────────────────

    def _preview_update(self):
        """No-op: inline property editor removed; preview updates on card select."""
        pass

    def _collect_theme_settings(self) -> dict:
        """No-op: returns current global settings as fallback."""
        return {}

    # ── Save (now handled by ThemeVisualEditor; kept as no-op) ──────────────

    def save_current_theme(self):
        """No-op: saving is now done through ✏ Editează → ThemeVisualEditor."""
        show_toast("Folosește ✏ Editează pentru a salva modificările temei.", "info")
