"""
Cantio — Overlays tab.

Overlays are transparent, click-through output layers (ticker / clock / icons /
shapes / text) edited in the FULL background editor and shown live on a chosen
screen, INDEPENDENT of the main live window. Several can be live at once.

Each overlay is a bg-engine design (.json) in
    ~/Cantio/profiles/<profile>/overlays/<name>.json
Its target screen is stored per-overlay in the db setting `overlay_screens`
(a JSON dict name -> screen index). Live overlays are tracked in-memory.
"""
from __future__ import annotations
import os
import json

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QComboBox, QInputDialog, QMessageBox, QApplication,
)
from PyQt6.QtCore import Qt

import database as db


def _overlays_dir() -> str:
    prof = "default"
    try:
        prof = db.get_active_profile() or "default"
    except Exception:
        pass
    d = os.path.join(os.path.expanduser("~"), "Cantio", "profiles", prof, "overlays")
    os.makedirs(d, exist_ok=True)
    return d


def _safe_name(name: str) -> str:
    s = "".join(c for c in str(name) if c.isalnum() or c in " -_").strip()
    return s or "overlay"


class OverlaysTab(QWidget):
    def __init__(self, parent_control=None, parent=None):
        super().__init__(parent)
        self._control = parent_control
        self._live_overlays: set[str] = set()   # names currently shown live
        self._build_ui()
        self._refresh_list()

    # ── UI ─────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.setStyleSheet("background:#181818;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        top = QHBoxLayout()
        lbl = QLabel("OVERLAY-URI")
        lbl.setStyleSheet("color:#888; font-size:11px; font-weight:bold;")
        top.addWidget(lbl)
        top.addStretch()
        new_btn = QPushButton("＋ Overlay nou")
        new_btn.setStyleSheet(
            "QPushButton { background:#18283a; color:#5294e2; border:1px solid #1c3a5a;"
            " border-radius:4px; padding:5px 12px; font-size:11px; }"
            "QPushButton:hover { background:#1c3a5a; color:#e0e0e0; }")
        new_btn.clicked.connect(self._new_overlay)
        top.addWidget(new_btn)
        layout.addLayout(top)

        info = QLabel("Dublu-click = editează (editor de fundaluri) • «Trimite live» = "
                      "afișează PESTE fereastra live (ceas, ticker, text, logo…). "
                      "Mai multe pot fi active simultan.")
        info.setStyleSheet("color:#666; font-size:10px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        self._list = QListWidget()
        self._list.setStyleSheet(
            "QListWidget { background:#141414; border:1px solid #2a2a2a; border-radius:4px;"
            " color:#ddd; } QListWidget::item { padding:8px; }"
            " QListWidget::item:selected { background:#1c3a5a; }")
        self._list.itemDoubleClicked.connect(lambda it: self._edit_overlay(it.data(Qt.ItemDataRole.UserRole)))
        self._list.currentRowChanged.connect(self._on_selection)
        layout.addWidget(self._list, 1)

        # Opțiune per overlay: auto-ascundere când se suprapune cu textul slide-ului
        from PyQt6.QtWidgets import QCheckBox
        self._hide_chk = QCheckBox("Ascunde automat când se suprapune cu textul de pe slide")
        self._hide_chk.setStyleSheet("color:#bbb; font-size:11px;")
        self._hide_chk.toggled.connect(self._on_hide_toggled)
        layout.addWidget(self._hide_chk)

        brow = QHBoxLayout()
        self._send_btn = QPushButton("📺 Trimite live")
        self._send_btn.setStyleSheet(
            "QPushButton { background:#1c3a2a; color:#a6e3a1; border:1px solid #2a5a3a;"
            " border-radius:4px; padding:6px 12px; font-size:11px; }"
            "QPushButton:hover { background:#1f4a30; }")
        self._send_btn.clicked.connect(self._toggle_selected_live)
        brow.addWidget(self._send_btn, 1)
        edit_btn = QPushButton("✏ Editează")
        edit_btn.setStyleSheet(
            "QPushButton { background:#1c1c1c; color:#aaa; border:1px solid #2a2a2a;"
            " border-radius:4px; padding:6px 10px; font-size:11px; }"
            "QPushButton:hover { background:#252525; }")
        edit_btn.clicked.connect(self._edit_selected)
        brow.addWidget(edit_btn)
        del_btn = QPushButton("🗑")
        del_btn.setFixedWidth(34)
        del_btn.setStyleSheet(
            "QPushButton { background:#2a1a1a; color:#f44336; border:1px solid #3a2020;"
            " border-radius:4px; padding:6px; } QPushButton:hover { background:#3a2020; }")
        del_btn.clicked.connect(self._delete_selected)
        brow.addWidget(del_btn)
        layout.addLayout(brow)

    # ── Data ───────────────────────────────────────────────────────────────────
    def _list_overlays(self) -> list:
        try:
            return sorted(f[:-5] for f in os.listdir(_overlays_dir()) if f.lower().endswith(".json"))
        except Exception:
            return []

    def _overlay_path(self, name: str) -> str:
        return os.path.join(_overlays_dir(), f"{_safe_name(name)}.json")

    def _hideontext_map(self) -> dict:
        try:
            return json.loads(db.get_settings().get("overlay_hideontext", "{}") or "{}")
        except Exception:
            return {}

    def _save_hideontext_map(self, m: dict):
        try:
            db.save_setting("overlay_hideontext", json.dumps(m))
        except Exception:
            pass

    def _refresh_list(self):
        self._list.clear()
        for name in self._list_overlays():
            live = "🔴 " if name in self._live_overlays else "⚫ "
            it = QListWidgetItem(live + name)
            it.setData(Qt.ItemDataRole.UserRole, name)
            self._list.addItem(it)
        self._update_send_btn()

    def _selected_name(self):
        it = self._list.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _on_selection(self, _row):
        name = self._selected_name()
        if not name:
            return
        self._hide_chk.blockSignals(True)
        self._hide_chk.setChecked(bool(self._hideontext_map().get(name, False)))
        self._hide_chk.blockSignals(False)
        self._update_send_btn()

    def _update_send_btn(self):
        name = self._selected_name()
        live = name in self._live_overlays if name else False
        self._send_btn.setText("⏹ Oprește" if live else "📺 Trimite live")

    def _on_hide_toggled(self, on: bool):
        name = self._selected_name()
        if not name:
            return
        m = self._hideontext_map()
        m[name] = bool(on)
        self._save_hideontext_map(m)
        # Dacă e live, re-trimite setul ca să se aplice imediat.
        if name in self._live_overlays:
            self._push_live_overlays()

    # ── CRUD ───────────────────────────────────────────────────────────────────
    def _new_overlay(self):
        name, ok = QInputDialog.getText(self, "Overlay nou", "Nume overlay:")
        if not (ok and name.strip()):
            return
        name = name.strip()
        path = self._overlay_path(name)
        if not os.path.exists(path):
            # Empty transparent design — the user adds ticker/clock/icons in the editor.
            design = {"name": name, "format": {"w": 1920, "h": 1080},
                      "slides": [{"format": {"w": 1920, "h": 1080}, "layers": []}]}
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(design, f, ensure_ascii=False, indent=2)
            except Exception as e:
                QMessageBox.critical(self, "Eroare", f"Nu am putut crea overlay-ul:\n{e}")
                return
        self._refresh_list()
        self._edit_overlay(name)

    def _edit_overlay(self, name):
        if not name:
            return
        mgr = getattr(self._control, "electron_display", None) if self._control else None
        if mgr is None or not hasattr(mgr, "open_bg_editor"):
            QMessageBox.warning(self, "Overlay", "Editorul (Electron) nu este disponibil.")
            return
        mgr.open_bg_editor(self._overlay_path(name))

    def _edit_selected(self):
        self._edit_overlay(self._selected_name())

    def _delete_selected(self):
        name = self._selected_name()
        if not name:
            return
        if QMessageBox.question(self, "Șterge overlay", f"Ștergi overlay-ul «{name}»?") \
                != QMessageBox.StandardButton.Yes:
            return
        if name in self._live_overlays:
            self._stop_overlay_live(name)
        try:
            os.remove(self._overlay_path(name))
        except Exception:
            pass
        self._refresh_list()

    # ── Live ───────────────────────────────────────────────────────────────────
    def _toggle_selected_live(self):
        name = self._selected_name()
        if not name:
            return
        if name in self._live_overlays:
            self._stop_overlay_live(name)
        else:
            self._send_overlay_live(name)
        self._refresh_list()

    def _load_design(self, name):
        try:
            with open(self._overlay_path(name), encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _overlay_doc(self, name) -> dict | None:
        """Întoarce doc-ul bg-engine (layerele) pentru un overlay salvat."""
        design = self._load_design(name)
        if design is None:
            return None
        # Un design salvat în editor are slides[0].layers; acceptăm și {layers:[]}.
        if isinstance(design.get("layers"), list):
            return {"layers": design["layers"]}
        slide = (design.get("slides") or [{}])[0]
        return {"layers": slide.get("layers", [])}

    def _push_live_overlays(self):
        """Compune TOATE overlay-urile active și le trimite peste fereastra live."""
        mgr = getattr(self._control, "electron_display", None) if self._control else None
        if mgr is None or not hasattr(mgr, "set_overlays"):
            return
        hmap = self._hideontext_map()
        payload = []
        for name in self._live_overlays:
            doc = self._overlay_doc(name)
            if doc is None:
                continue
            payload.append({
                "id": _safe_name(name),
                "name": name,
                "doc": doc,
                "hideOnText": bool(hmap.get(name, False)),
            })
        try:
            mgr.set_overlays(payload)
        except Exception:
            pass

    def _send_overlay_live(self, name, restart=False):
        self._live_overlays.add(name)
        self._push_live_overlays()

    def _stop_overlay_live(self, name):
        self._live_overlays.discard(name)
        self._push_live_overlays()

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_list()   # pick up overlays saved in the editor
        # Reaplică overlay-urile active (preia modificările făcute în editor).
        if self._live_overlays:
            self._push_live_overlays()
