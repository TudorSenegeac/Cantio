"""
Cantio – Bible Control Tab
Central-panel tab that receives verses from the sidebar Bible browser and
provides arrow-key navigation to advance/retreat through a chapter.
Supports dual-translation mode: shows two translations side-by-side.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget,
)

from translations import t


class BibleControlTab(QWidget):
    """
    Shows the verses of the currently-selected Bible chapter.
    Click a verse to send it live; ←/→ or ↑/↓ navigate; Enter sends live.
    """

    verse_sent_live = pyqtSignal(str, str)   # (text, reference)

    # ─────────────────────────────────────────────────────────────────────────

    def __init__(self, parent_control=None):
        super().__init__()
        self.parent_control = parent_control

        self._verses_data:   list[dict] = []
        self._book_name      = ""
        self._chapter        = 0
        self._dual_enabled   = False
        self._profile        = getattr(parent_control, "_profile_name",
                               getattr(parent_control, "_current_profile", "default"))

        self._build_ui()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._refresh_translations()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        _combo_style = (
            "QComboBox { background:#1e2030; color:#cdd6f4; border:1px solid #313244; "
            "border-radius:4px; padding:3px 6px; font-size:11px; }"
            "QComboBox::drop-down { border:none; }"
            "QComboBox QAbstractItemView { background:#1e2030; color:#cdd6f4; "
            "selection-background-color:#313244; }"
        )

        # ── Dual-translation row ──────────────────────────────────────────────
        dual_row = QHBoxLayout()
        dual_row.setSpacing(6)

        trans1_lbl = QLabel(t("bible_translation_1") + ":")
        trans1_lbl.setStyleSheet("color:#a6adc8; font-size:10px;")
        dual_row.addWidget(trans1_lbl)

        self._trans1_combo = QComboBox()
        self._trans1_combo.setStyleSheet(_combo_style)
        self._trans1_combo.setToolTip(t("bible_translation_1"))
        dual_row.addWidget(self._trans1_combo, 1)

        trans2_lbl = QLabel(t("bible_translation_2") + ":")
        trans2_lbl.setStyleSheet("color:#a6adc8; font-size:10px;")
        dual_row.addWidget(trans2_lbl)

        self._trans2_combo = QComboBox()
        self._trans2_combo.setStyleSheet(_combo_style)
        self._trans2_combo.setToolTip(t("bible_translation_2"))
        dual_row.addWidget(self._trans2_combo, 1)

        self._dual_check = QCheckBox(t("bible_dual"))
        self._dual_check.setStyleSheet("color:#89b4fa; font-size:10px;")
        self._dual_check.setChecked(False)
        self._dual_check.toggled.connect(self._on_dual_toggled)
        dual_row.addWidget(self._dual_check)
        layout.addLayout(dual_row)

        # ── Header row: title + Prev / Next ──────────────────────────────────
        header = QHBoxLayout()
        title_lbl = QLabel("📖 " + t("control_bible"))
        title_lbl.setStyleSheet(
            "color:#89dceb; font-size:13px; font-weight:bold;"
        )
        header.addWidget(title_lbl)

        self._ref_header = QLabel("")
        self._ref_header.setStyleSheet("color:#585b70; font-size:11px;")
        header.addWidget(self._ref_header, 1)

        self.prev_btn = QPushButton(t("bible_prev"))
        self.next_btn = QPushButton(t("bible_next"))
        for btn in (self.prev_btn, self.next_btn):
            btn.setStyleSheet(
                "QPushButton { background:#1e2030; color:#cdd6f4; "
                "border:1px solid #313244; border-radius:5px; padding:4px 10px; }"
                "QPushButton:hover { background:#313244; color:#cba6f7; }"
                "QPushButton:pressed { background:#181825; }"
            )
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.prev_btn.clicked.connect(self._prev_verse)
        self.next_btn.clicked.connect(self._next_verse)
        header.addWidget(self.prev_btn)
        header.addWidget(self.next_btn)
        layout.addLayout(header)

        # ── Verse list ────────────────────────────────────────────────────────
        self.verse_queue = QListWidget()
        self.verse_queue.setStyleSheet(
            "QListWidget { background:#1e1e2e; border:1px solid #313244; "
            "border-radius:6px; outline:none; }"
            "QListWidget::item { padding:6px 10px; color:#cdd6f4; "
            "border-bottom:1px solid #252536; }"
            "QListWidget::item:hover { background:#252536; }"
            "QListWidget::item:selected { background:#313244; color:#cba6f7; }"
        )
        self.verse_queue.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.verse_queue.itemClicked.connect(self._send_verse_live)
        layout.addWidget(self.verse_queue, 1)

        # ── Currently-live verse box ──────────────────────────────────────────
        current_group = QGroupBox(t("bible_current"))
        current_group.setStyleSheet(
            "QGroupBox { border:1px solid #313244; border-radius:6px; "
            "margin-top:8px; padding-top:6px; color:#a6adc8; font-size:11px; }"
            "QGroupBox::title { subcontrol-origin:margin; left:8px; }"
        )
        current_layout = QVBoxLayout(current_group)
        current_layout.setContentsMargins(8, 4, 8, 6)
        current_layout.setSpacing(3)

        self.current_verse_label = QLabel(t("bible_no_verse"))
        self.current_verse_label.setWordWrap(True)
        self.current_verse_label.setStyleSheet(
            "font-size:13px; color:#cdd6f4; padding:4px;"
        )
        current_layout.addWidget(self.current_verse_label)

        ref_row = QHBoxLayout()
        ref_row.setContentsMargins(0, 0, 0, 0)
        self.ref_label = QLabel("")
        self.ref_label.setStyleSheet("color:#89b4fa; font-size:12px;")
        ref_row.addWidget(self.ref_label)
        ref_row.addStretch()

        self._send_live_btn = QPushButton(t("bible_send_live"))
        self._send_live_btn.setStyleSheet(
            "QPushButton { background:#1c3a5a; color:#89b4fa; "
            "border:1px solid #2a5a8a; border-radius:5px; padding:4px 10px; }"
            "QPushButton:hover { background:#2a5a8a; color:#cdd6f4; }"
        )
        self._send_live_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._send_live_btn.clicked.connect(
            lambda: self._send_verse_live(self.verse_queue.currentItem())
        )
        ref_row.addWidget(self._send_live_btn)
        current_layout.addLayout(ref_row)
        layout.addWidget(current_group)

        # ── Keyboard hint ─────────────────────────────────────────────────────
        self._hint_label = QLabel(t("bible_kb_hint"))
        self._hint_label.setStyleSheet("color:#45475a; font-size:10px; padding:2px;")
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._hint_label)

    # ── Public API ────────────────────────────────────────────────────────────

    def load_chapter(
        self,
        book_name: str,
        chapter:   int,
        verses:    list[dict],
        selected_verse: int | None = None,
    ):
        """
        Called by control_window when a Bible chapter is loaded in the sidebar.
        `verses` is a list of dicts with at minimum {'verse': int, 'text': str}.
        """
        self.verse_queue.clear()
        self._verses_data = verses
        self._book_name   = book_name
        self._chapter     = chapter
        self._ref_header.setText(f"{book_name}  {chapter}")

        for v in verses:
            verse_num = v.get("verse", 0)
            text      = v.get("text",  "")
            item = QListWidgetItem(f"{verse_num}.  {text}")
            item.setData(Qt.ItemDataRole.UserRole, v)
            self.verse_queue.addItem(item)

        # Scroll to & select the requested verse
        if selected_verse is not None:
            for i in range(self.verse_queue.count()):
                it = self.verse_queue.item(i)
                v  = it.data(Qt.ItemDataRole.UserRole)
                if v.get("verse") == selected_verse:
                    self.verse_queue.setCurrentItem(it)
                    self.verse_queue.scrollToItem(it)
                    break
        elif self.verse_queue.count() > 0:
            self.verse_queue.setCurrentRow(0)

    def _on_verse_selected(self, verse_num: int):
        """
        Highlight (but do NOT send live) the given verse number in the list.
        Called from control_window when a verse is selected in the sidebar browser.
        """
        for i in range(self.verse_queue.count()):
            it = self.verse_queue.item(i)
            v  = it.data(Qt.ItemDataRole.UserRole)
            if v and v.get("verse") == verse_num:
                self.verse_queue.blockSignals(True)
                self.verse_queue.setCurrentItem(it)
                self.verse_queue.scrollToItem(it)
                self.verse_queue.blockSignals(False)
                break

    def _on_chapter_selected(self, book_name: str, chapter: int,
                              verses: list, selected_verse: int | None = None):
        """
        Load a chapter and optionally pre-select a verse.
        Convenience wrapper so control_window can call a single method to
        sync the Control Bible tab whenever the sidebar chapter changes.
        """
        self.load_chapter(book_name, chapter, verses, selected_verse)

    # ── Translation helpers ───────────────────────────────────────────────────

    def _refresh_translations(self):
        """Populate translation combos from the per-profile bible DB."""
        try:
            import database as db
            translations = db.get_available_translations(self._profile)
        except Exception:
            translations = []

        for combo in (self._trans1_combo, self._trans2_combo):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("— (default)", None)
            for tr in translations:
                combo.addItem(
                    f"{tr['name']} ({tr.get('abbreviation', '')})",
                    tr["id"]
                )
            combo.blockSignals(False)

    def refresh_ui_texts(self):
        """Update button/label texts after a language change."""
        self._send_live_btn.setText(t("bible_send_live"))
        self._hint_label.setText(t("bible_kb_hint"))
        self.prev_btn.setText(t("bible_prev"))
        self.next_btn.setText(t("bible_next"))

    def _on_dual_toggled(self, checked: bool):
        self._dual_enabled = checked
        self._trans2_combo.setEnabled(checked)

    def _get_verse_translation2(self, book_id: int, chapter: int, verse_num: int) -> str:
        """Return text of verse from secondary translation, or empty string."""
        trans_id = self._trans2_combo.currentData()
        if not trans_id:
            return ""
        try:
            import database as db
            verses = db.get_verses_for_translation(book_id, chapter, trans_id, self._profile)
            for v in verses:
                if v.get("verse") == verse_num:
                    return v.get("text", "")
        except Exception:
            pass
        return ""

    # ── Verse sending ─────────────────────────────────────────────────────────

    def _send_verse_live(self, item: QListWidgetItem | None):
        if item is None:
            return
        v = item.data(Qt.ItemDataRole.UserRole)
        if not v:
            return

        text      = v.get("text",  "")
        verse_num = v.get("verse", 0)
        book_id   = v.get("book_id", 0)
        ref       = f"{self._book_name} {self._chapter}:{verse_num}"

        # Dual translation mode
        if self._dual_enabled and self._trans2_combo.currentData():
            text2 = self._get_verse_translation2(book_id, self._chapter, verse_num)
            if text2:
                text = f"{text}\n\n── ── ── ──\n\n{text2}"

        self.current_verse_label.setText(text)
        self.ref_label.setText(ref)

        self.verse_sent_live.emit(text, ref)

        if self.parent_control and hasattr(
            self.parent_control, "_send_bible_verse_live"
        ):
            self.parent_control._send_bible_verse_live(text, ref)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _prev_verse(self):
        cur = self.verse_queue.currentRow()
        if cur > 0:
            self.verse_queue.setCurrentRow(cur - 1)
            self._send_verse_live(self.verse_queue.currentItem())

    def _next_verse(self):
        cur = self.verse_queue.currentRow()
        if cur < self.verse_queue.count() - 1:
            self.verse_queue.setCurrentRow(cur + 1)
            self._send_verse_live(self.verse_queue.currentItem())

    # ── Key navigation ────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Right, Qt.Key.Key_Down, Qt.Key.Key_Space):
            self._next_verse()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            self._prev_verse()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._send_verse_live(self.verse_queue.currentItem())
        else:
            super().keyPressEvent(event)
