# -*- coding: utf-8 -*-
"""
Cantio — Tab „Mai multe…”
=========================
Un tab general cu o listă în stânga și conținutul elementului selectat în
dreapta. Pentru început, lista conține doar „Biblii” — managerul bibliilor
importate: le vezi, le ștergi, alegi care se afișează (principală) și, pentru
traducere duală, cu care se împerechează (secundară).

(Pe viitor: aici putem adăuga „Biblii de descărcat”, resurse etc.)
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QStackedWidget, QPushButton, QComboBox, QCheckBox, QMessageBox, QFrame,
)

import database as db


class _BibleManager(QWidget):
    """Managerul bibliilor importate pentru profilul curent."""

    def __init__(self, parent_control):
        super().__init__()
        self._ctrl = parent_control
        self._build_ui()
        self.refresh()

    def _profile(self) -> str:
        try:
            return (getattr(self._ctrl, "_profile_name", None)
                    or db.get_active_profile() or "Default")
        except Exception:
            return "Default"

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        title = QLabel("📖 Biblii importate")
        title.setStyleSheet("font-size:15px; font-weight:600; color:#cba6f7;")
        root.addWidget(title)

        self._list = QListWidget()
        self._list.setStyleSheet(
            "QListWidget { background:#1e1e1e; border:1px solid #2a2a2a; border-radius:6px; }"
            "QListWidget::item { padding:8px 10px; border-bottom:1px solid #262626; }"
            "QListWidget::item:selected { background:#313244; color:#cba6f7; }"
        )
        root.addWidget(self._list, 1)

        del_row = QHBoxLayout()
        self._del_btn = QPushButton("🗑 Șterge biblia selectată")
        self._del_btn.setStyleSheet(
            "QPushButton { background:#2a1a1a; color:#f38ba8; border:1px solid #3a2020; "
            "border-radius:5px; padding:7px 14px; } QPushButton:hover { background:#3a2020; }")
        self._del_btn.clicked.connect(self._delete_selected)
        del_row.addWidget(self._del_btn)
        del_row.addStretch()
        root.addLayout(del_row)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#2a2a2a;")
        root.addWidget(sep)

        # ── Ce se afișează ────────────────────────────────────────────────────
        disp = QLabel("Ce se afișează")
        disp.setStyleSheet("font-size:13px; font-weight:600; color:#cdd6f4;")
        root.addWidget(disp)

        prim_row = QHBoxLayout()
        prim_row.addWidget(QLabel("Principală:"))
        self._primary = QComboBox()
        self._primary.setMinimumWidth(220)
        prim_row.addWidget(self._primary)
        prim_row.addStretch()
        root.addLayout(prim_row)

        self._dual = QCheckBox("Traducere duală (afișează două traduceri simultan)")
        self._dual.toggled.connect(lambda v: self._secondary.setEnabled(v))
        root.addWidget(self._dual)

        sec_row = QHBoxLayout()
        sec_row.addWidget(QLabel("Secundară:"))
        self._secondary = QComboBox()
        self._secondary.setMinimumWidth(220)
        self._secondary.setEnabled(False)
        sec_row.addWidget(self._secondary)
        sec_row.addStretch()
        root.addLayout(sec_row)

        apply_row = QHBoxLayout()
        apply_row.addStretch()
        self._apply_btn = QPushButton("✓ Aplică")
        self._apply_btn.setStyleSheet(
            "QPushButton { background:#5294e2; color:#fff; border:none; border-radius:5px; "
            "padding:7px 18px; font-weight:600; } QPushButton:hover { background:#6ba5f0; }")
        self._apply_btn.clicked.connect(self._apply_selection)
        apply_row.addWidget(self._apply_btn)
        root.addLayout(apply_row)

        for c in (self._primary, self._secondary):
            c.setStyleSheet(
                "QComboBox { background:#1a1a1a; color:#e0e0e0; border:1px solid #2a2a2a; "
                "border-radius:4px; padding:5px 8px; }")

    # ── Data ──────────────────────────────────────────────────────────────
    def refresh(self):
        prof = self._profile()
        try:
            trans = db.get_available_translations(prof)
        except Exception:
            trans = []
        self._list.clear()
        self._primary.blockSignals(True); self._secondary.blockSignals(True)
        self._primary.clear(); self._secondary.clear()
        self._secondary.addItem("— (niciuna)", None)
        for tr in trans:
            label = f"{tr['name']}  ({tr.get('abbreviation', '')})"
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, tr["id"])
            self._list.addItem(it)
            self._primary.addItem(label, tr["id"])
            self._secondary.addItem(label, tr["id"])
        if not trans:
            self._list.addItem(QListWidgetItem("(nicio biblie importată — folosește Fișier → Import Biblie)"))
        # Restore saved selection
        try:
            s = db.get_settings()
            pid = s.get("bible_primary_translation")
            sid = s.get("bible_secondary_translation")
            dual = str(s.get("bible_dual_enabled", "false")) == "true"
            if pid not in (None, "", "None"):
                i = self._primary.findData(int(pid))
                if i >= 0:
                    self._primary.setCurrentIndex(i)
            self._dual.setChecked(dual)
            self._secondary.setEnabled(dual)
            if sid not in (None, "", "None"):
                i = self._secondary.findData(int(sid))
                if i >= 0:
                    self._secondary.setCurrentIndex(i)
        except Exception:
            pass
        self._primary.blockSignals(False); self._secondary.blockSignals(False)

    def _delete_selected(self):
        it = self._list.currentItem()
        tid = it.data(Qt.ItemDataRole.UserRole) if it else None
        if tid is None:
            return
        if QMessageBox.question(
            self, "Șterge biblia",
            f"Ștergi definitiv „{it.text()}”?\nVersetele acestei traduceri vor fi eliminate.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        db.delete_translation(int(tid), self._profile())
        self.refresh()

    def _apply_selection(self):
        pid = self._primary.currentData()
        sid = self._secondary.currentData() if self._dual.isChecked() else None
        try:
            db.save_setting("bible_primary_translation", "" if pid is None else str(pid))
            db.save_setting("bible_secondary_translation", "" if sid is None else str(sid))
            db.save_setting("bible_dual_enabled", "true" if self._dual.isChecked() else "false")
        except Exception:
            pass
        # Sincronizeaza tab-ul Control Bible daca exista.
        bct = getattr(self._ctrl, "_bible_control_tab", None)
        if bct is not None and hasattr(bct, "set_translations"):
            try:
                bct.set_translations(pid, sid, self._dual.isChecked())
            except Exception:
                pass
        try:
            self._ctrl._toasts.success("Setări biblii aplicate.")
        except Exception:
            pass


class MoreTab(QWidget):
    """Lista stânga + conținut dreapta. Momentan: Biblii."""

    def __init__(self, parent_control=None, parent=None):
        super().__init__(parent)
        self._ctrl = parent_control
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._nav = QListWidget()
        self._nav.setFixedWidth(180)
        self._nav.setStyleSheet(
            "QListWidget { background:#161616; border:none; border-right:1px solid #262626; }"
            "QListWidget::item { padding:12px 14px; color:#bbb; }"
            "QListWidget::item:selected { background:#1e1e1e; color:#cba6f7; "
            "border-left:3px solid #cba6f7; }"
        )
        root.addWidget(self._nav)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background:#131313;")
        root.addWidget(self._stack, 1)

        # Element: Biblii
        self._bible_mgr = _BibleManager(parent_control)
        self._add_section("📖 Biblii", self._bible_mgr)

        self._nav.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._nav.setCurrentRow(0)

    def _add_section(self, name: str, widget: QWidget):
        self._nav.addItem(QListWidgetItem(name))
        self._stack.addWidget(widget)

    def refresh(self):
        try:
            self._bible_mgr.refresh()
        except Exception:
            pass
