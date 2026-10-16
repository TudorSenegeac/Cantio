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
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QStackedWidget, QMessageBox, QMenu,
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
        root.setSpacing(8)

        title = QLabel("📖 Biblii importate")
        title.setStyleSheet("font-size:15px; font-weight:600; color:#cba6f7;")
        root.addWidget(title)

        hint = QLabel("Click dreapta pe o versiune pentru comenzi "
                      "(principală / a doua limbă / șterge).")
        hint.setStyleSheet("color:#8a8a95; font-size:11px;")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self._list = QListWidget()
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_menu)
        self._list.setStyleSheet(
            "QListWidget { background:#1e1e1e; border:1px solid #2a2a2a; border-radius:6px; }"
            "QListWidget::item { padding:10px 12px; border-bottom:1px solid #262626; }"
            "QListWidget::item:selected { background:#313244; color:#cba6f7; }"
        )
        root.addWidget(self._list, 1)

        legend = QLabel("⭐ principală    ②  a doua limbă (duală)")
        legend.setStyleSheet("color:#6c7086; font-size:11px;")
        root.addWidget(legend)

    # ── Data ──────────────────────────────────────────────────────────────
    def _saved(self):
        """(primary_id, secondary_id, dual) din settings (int sau None)."""
        try:
            s = db.get_settings()
            def _i(v):
                return int(v) if v not in (None, "", "None") else None
            pid = _i(s.get("bible_primary_translation"))
            sid = _i(s.get("bible_secondary_translation"))
            dual = str(s.get("bible_dual_enabled", "false")) == "true"
            return pid, sid, dual
        except Exception:
            return None, None, False

    def refresh(self):
        prof = self._profile()
        try:
            trans = db.get_available_translations(prof)
        except Exception:
            trans = []
        pid, sid, dual = self._saved()
        self._list.clear()
        if not trans:
            it = QListWidgetItem("(nicio biblie importată — folosește Fișier → Import Biblie)")
            it.setFlags(Qt.ItemFlag.NoItemFlags)
            it.setForeground(Qt.GlobalColor.gray)
            self._list.addItem(it)
            return
        for tr in trans:
            name = f"{tr['name']}  ({tr.get('abbreviation', '')})"
            badges = []
            if pid == tr["id"]:
                badges.append("⭐")
            if dual and sid == tr["id"]:
                badges.append("②")
            label = (("  ".join(badges) + "   ") if badges else "") + name
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, tr["id"])
            self._list.addItem(it)

    # ── Context menu (click dreapta) ──────────────────────────────────────
    def _show_menu(self, pos):
        it = self._list.itemAt(pos)
        if it is None or it.data(Qt.ItemDataRole.UserRole) is None:
            return
        tid = int(it.data(Qt.ItemDataRole.UserRole))
        pid, sid, dual = self._saved()

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#1e1e1e; color:#e0e0e0; border:1px solid #333; }"
            "QMenu::item { padding:7px 18px; } "
            "QMenu::item:selected { background:#313244; color:#cba6f7; }")

        act_primary = QAction("⭐ Afișează ca principală", self)
        act_primary.setEnabled(pid != tid)
        act_primary.triggered.connect(lambda: self._set_primary(tid))
        menu.addAction(act_primary)

        act_second = QAction("②  Afișează ca a doua limbă (duală)", self)
        act_second.setEnabled(pid != tid)   # nu poate fi si principala si secundara
        act_second.triggered.connect(lambda: self._set_secondary(tid))
        menu.addAction(act_second)

        if dual and (sid is not None or pid is not None):
            act_off = QAction("✖ Oprește a doua limbă", self)
            act_off.triggered.connect(self._clear_dual)
            menu.addAction(act_off)

        menu.addSeparator()
        act_del = QAction("🗑 Șterge biblia", self)
        act_del.triggered.connect(lambda: self._delete(tid, it.text()))
        menu.addAction(act_del)

        menu.exec(self._list.mapToGlobal(pos))

    # ── Acțiuni ───────────────────────────────────────────────────────────
    def _apply(self, pid, sid, dual):
        try:
            db.save_setting("bible_primary_translation", "" if pid is None else str(pid))
            db.save_setting("bible_secondary_translation", "" if sid is None else str(sid))
            db.save_setting("bible_dual_enabled", "true" if dual else "false")
        except Exception:
            pass
        bct = getattr(self._ctrl, "_bible_control_tab", None)
        if bct is not None and hasattr(bct, "set_translations"):
            try:
                bct.set_translations(pid, sid, dual)
            except Exception:
                pass
        self.refresh()

    def _set_primary(self, tid):
        pid, sid, dual = self._saved()
        if sid == tid:          # era secundara -> eliberam secundara
            sid = None
            dual = False
        self._apply(tid, sid, dual)
        self._toast(f"Principală setată.")

    def _set_secondary(self, tid):
        pid, sid, dual = self._saved()
        if pid is None:
            self._toast("Alege întâi o traducere principală.", ok=False)
            return
        self._apply(pid, tid, True)
        self._toast("A doua limbă (duală) setată.")

    def _clear_dual(self):
        pid, sid, dual = self._saved()
        self._apply(pid, None, False)
        self._toast("A doua limbă oprită.")

    def _delete(self, tid, label):
        if QMessageBox.question(
            self, "Șterge biblia",
            f"Ștergi definitiv „{label}”?\nVersetele acestei traduceri vor fi eliminate.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        db.delete_translation(int(tid), self._profile())
        # Curata referintele daca stergem una activa
        pid, sid, dual = self._saved()
        if pid == tid:
            pid = None
        if sid == tid:
            sid = None; dual = False
        self._apply(pid, sid, dual)

    def _toast(self, msg, ok=True):
        try:
            if ok:
                self._ctrl._toasts.success(msg)
            else:
                self._ctrl._toasts.warning(msg)
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
