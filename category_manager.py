"""
Cantio - Category Manager Dialog
Rename, delete, merge, and move songs between categories.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QInputDialog, QMessageBox,
    QComboBox, QFrame, QSplitter, QWidget, QSizePolicy,
)
from PyQt6.QtGui import QColor, QFont

import database as db


_STYLE = """
QDialog          { background: #131313; color: #e0e0e0; }
QLabel           { color: #e0e0e0; background: transparent; }
QListWidget      { background: #1a1a1a; border: 1px solid #2c2c2c;
                   color: #e0e0e0; outline: none; }
QListWidget::item                { padding: 6px 10px; border: none; }
QListWidget::item:selected       { background: #1c3a5a; color: #ffffff; }
QListWidget::item:hover          { background: #222222; }
QPushButton {
    background: #232323; color: #e0e0e0; border: 1px solid #2c2c2c;
    border-radius: 5px; padding: 6px 14px; font-size: 11px;
}
QPushButton:hover    { background: #2a2a2a; border-color: #3a3a3a; }
QPushButton:disabled { color: #555; border-color: #222; }
QPushButton#danger   { color: #e06060; border-color: #5a2020; }
QPushButton#danger:hover { background: #2a1818; border-color: #7a2020; }
QPushButton#primary  { background: #1c3a5a; color: #5294e2; border-color: #2a5a8a; }
QPushButton#primary:hover { background: #1e4a6e; }
QComboBox {
    background: #1e1e1e; color: #e0e0e0; border: 1px solid #2c2c2c;
    border-radius: 4px; padding: 4px 8px;
}
QComboBox QAbstractItemView { background: #1e1e1e; color: #e0e0e0; }
QFrame#sep { background: #2c2c2c; }
QSplitter::handle { background: #2c2c2c; width: 1px; }
"""


class CategoryManagerDialog(QDialog):
    categories_changed = pyqtSignal()   # emitted whenever the DB is modified

    def __init__(self, parent=None, app_style: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Gestionare Categorii — Cantio")
        self.setMinimumSize(760, 500)
        self.setStyleSheet(app_style or _STYLE)
        self._counts:    dict[str, int] = {}
        self._builtins:  set[str]       = set()
        self._build_ui()
        self._refresh_categories()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        title = QLabel("GESTIONARE CATEGORII")
        title.setStyleSheet(
            "color: #5294e2; font-size: 10px; font-weight: 700; letter-spacing: 2px;"
        )
        root.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left: category list ───────────────────────────────────────────────
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(6)

        lbl_cat = QLabel("Categorii")
        lbl_cat.setStyleSheet("color: #888; font-size: 10px; font-weight: 700;")
        lv.addWidget(lbl_cat)

        self._cat_list = QListWidget()
        self._cat_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._cat_list.currentItemChanged.connect(self._on_category_selected)
        lv.addWidget(self._cat_list, 1)

        btn_row_l = QHBoxLayout()
        btn_row_l.setSpacing(4)

        self._rename_btn = QPushButton("Redenumire")
        self._rename_btn.setEnabled(False)
        self._rename_btn.clicked.connect(self._rename_category)
        btn_row_l.addWidget(self._rename_btn)

        self._delete_btn = QPushButton("Ștergere")
        self._delete_btn.setObjectName("danger")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._delete_category)
        btn_row_l.addWidget(self._delete_btn)

        lv.addLayout(btn_row_l)

        self._merge_btn = QPushButton("Combină cu...")
        self._merge_btn.setEnabled(False)
        self._merge_btn.clicked.connect(self._merge_category)
        lv.addWidget(self._merge_btn)

        splitter.addWidget(left)

        # ── Right: songs in selected category ────────────────────────────────
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(6)

        self._songs_header = QLabel("Cântece")
        self._songs_header.setStyleSheet("color: #888; font-size: 10px; font-weight: 700;")
        rv.addWidget(self._songs_header)

        self._song_list = QListWidget()
        self._song_list.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection
        )
        self._song_list.itemSelectionChanged.connect(self._on_song_selection_changed)
        rv.addWidget(self._song_list, 1)

        btn_row_r = QHBoxLayout()
        btn_row_r.setSpacing(6)

        move_lbl = QLabel("Mută selecția →")
        move_lbl.setStyleSheet("color: #888; font-size: 11px;")
        btn_row_r.addWidget(move_lbl)

        self._move_target = QComboBox()
        self._move_target.setMinimumWidth(160)
        btn_row_r.addWidget(self._move_target)

        self._move_btn = QPushButton("Mută")
        self._move_btn.setObjectName("primary")
        self._move_btn.setEnabled(False)
        self._move_btn.clicked.connect(self._move_songs)
        btn_row_r.addWidget(self._move_btn)

        btn_row_r.addStretch()
        rv.addLayout(btn_row_r)

        splitter.addWidget(right)
        splitter.setSizes([240, 480])
        root.addWidget(splitter, 1)

        # ── Bottom ────────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setObjectName("sep")
        sep.setFixedHeight(1)
        root.addWidget(sep)

        bot = QHBoxLayout()
        bot.addStretch()
        close_btn = QPushButton("Închide")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        bot.addWidget(close_btn)
        root.addLayout(bot)

    # ── Data helpers ──────────────────────────────────────────────────────────

    def _refresh_categories(self, select: str | None = None):
        self._counts   = db.get_category_counts()
        builtin_list   = db.get_builtin_categories()
        self._builtins = set(builtin_list)

        # Merge DB categories with builtins (builtins may have 0 songs)
        all_cats: dict[str, int] = dict(self._counts)
        for b in builtin_list:
            all_cats.setdefault(b, 0)

        self._cat_list.blockSignals(True)
        self._cat_list.clear()
        for cat, cnt in sorted(all_cats.items(), key=lambda x: x[0].lower()):
            is_builtin = cat in self._builtins
            label = f"{'★ ' if is_builtin else ''}{cat}  ({cnt})"
            item  = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, cat)
            if is_builtin:
                item.setForeground(QColor("#5294e2"))
            self._cat_list.addItem(item)
        self._cat_list.blockSignals(False)

        # Re-select previous or requested category
        target = select or ""
        for i in range(self._cat_list.count()):
            it = self._cat_list.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == target:
                self._cat_list.setCurrentItem(it)
                break
        else:
            if self._cat_list.count():
                self._cat_list.setCurrentRow(0)

        self._refresh_move_target()

    def _refresh_move_target(self):
        current_cat = self._current_category()
        self._move_target.blockSignals(True)
        self._move_target.clear()
        all_cats = sorted((set(self._counts) | self._builtins) - {current_cat}, key=str.lower)
        for cat in all_cats:
            self._move_target.addItem(cat)
        self._move_target.addItem("+ Categorie nouă…")
        self._move_target.blockSignals(False)

    def _refresh_songs(self):
        cat = self._current_category()
        self._song_list.clear()
        if not cat:
            self._songs_header.setText("Cântece")
            return
        songs = db.get_songs_in_category(cat)
        cnt = len(songs)
        self._songs_header.setText(
            f"Cântece în «{cat}»  —  {cnt} {'cântec' if cnt == 1 else 'cântece'}"
        )
        for s in songs:
            item = QListWidgetItem(s["title"])
            item.setData(Qt.ItemDataRole.UserRole, s["id"])
            self._song_list.addItem(item)

    def _current_category(self) -> str:
        item = self._cat_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else ""

    def _selected_song_ids(self) -> list[int]:
        return [
            it.data(Qt.ItemDataRole.UserRole)
            for it in self._song_list.selectedItems()
        ]

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_category_selected(self):
        has = bool(self._current_category())
        self._rename_btn.setEnabled(has)
        self._delete_btn.setEnabled(has)
        self._merge_btn.setEnabled(has and self._cat_list.count() > 1)
        self._refresh_songs()
        self._refresh_move_target()
        self._move_btn.setEnabled(False)

    def _on_song_selection_changed(self):
        has_songs = bool(self._selected_song_ids())
        has_target = self._move_target.count() > 0
        self._move_btn.setEnabled(has_songs and has_target)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _rename_category(self):
        old = self._current_category()
        if not old:
            return
        new, ok = QInputDialog.getText(
            self, "Redenumire categorie",
            f"Noul nume pentru «{old}»:", text=old
        )
        if not ok or not new.strip() or new.strip() == old:
            return
        new = new.strip()
        all_known = set(self._counts) | self._builtins
        if new in all_known and new != old:
            reply = QMessageBox.question(
                self, "Categorie existentă",
                f"Categoria «{new}» există deja.\n"
                f"Cântecele din «{old}» vor fi mutate în «{new}».\nContinui?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        db.rename_category(old, new)
        # If it was a builtin, update the builtins list too
        if old in self._builtins:
            bl = db.get_builtin_categories()
            if old in bl:
                bl[bl.index(old)] = new
            db.set_builtin_categories(bl)
        self.categories_changed.emit()
        self._refresh_categories(select=new)

    def _delete_category(self):
        cat = self._current_category()
        if not cat:
            return
        cnt = self._counts.get(cat, 0)

        # Choose destination for songs (if any)
        all_known = sorted((set(self._counts) | self._builtins) - {cat}, key=str.lower)
        if cnt > 0:
            dest_choices = ["General"] + [o for o in all_known if o != "General"]
            dest, ok = QInputDialog.getItem(
                self, "Șterge categorie",
                f"Mută cele {cnt} cântece din «{cat}» în:",
                dest_choices,
                editable=False,
            )
            if not ok:
                return
        else:
            dest = "General"
            action = "și elimina din lista de categorii" if cat in self._builtins else "și șterge categoria"
            reply = QMessageBox.question(
                self, "Șterge categorie",
                f"Elimini categoria «{cat}» {action}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        if cnt > 0:
            db.delete_category(cat, dest)
        # If it's a builtin, remove it from the builtins list
        if cat in self._builtins:
            bl = db.get_builtin_categories()
            if cat in bl:
                bl.remove(cat)
            db.set_builtin_categories(bl)
        self.categories_changed.emit()
        self._refresh_categories(select=dest)

    def _merge_category(self):
        cat = self._current_category()
        if not cat:
            return
        others = sorted((set(self._counts) | self._builtins) - {cat}, key=str.lower)
        if not others:
            return
        target, ok = QInputDialog.getItem(
            self, "Combină categorii",
            f"Combină «{cat}» cu:",
            others,
            editable=False,
        )
        if not ok:
            return
        cnt = self._counts.get(cat, 0)
        reply = QMessageBox.question(
            self, "Confirmare",
            f"Mută cele {cnt} cântece din «{cat}» în «{target}»\n"
            f"și elimini categoria «{cat}»?\nAceastă acțiune nu poate fi anulată.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        db.rename_category(cat, target)
        if cat in self._builtins:
            bl = db.get_builtin_categories()
            if cat in bl:
                bl.remove(cat)
            db.set_builtin_categories(bl)
        self.categories_changed.emit()
        self._refresh_categories(select=target)

    def _move_songs(self):
        ids = self._selected_song_ids()
        if not ids:
            return
        target_text = self._move_target.currentText()

        if target_text == "+ Categorie nouă…":
            new_cat, ok = QInputDialog.getText(
                self, "Categorie nouă", "Numele noii categorii:"
            )
            if not ok or not new_cat.strip():
                return
            target_text = new_cat.strip()

        db.move_songs_to_category(ids, target_text)
        self.categories_changed.emit()
        current_cat = self._current_category()
        # Refresh counts and re-select the same category
        self._counts = db.get_category_counts()
        self._refresh_categories(select=current_cat)
