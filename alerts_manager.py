# -*- coding: utf-8 -*-
"""
Cantio — Manager Alerte
=======================
Fereastră (deschisă din butonul ⚠ din toolbar) unde operatorul creează,
editează și salvează alerte (mesaje text), apoi le afișează live ca ticker
derulant jos. O alertă poate avea un număr de derulări după care se închide
singură, sau se închide manual cu „Ascunde”.

Alertele se salvează per-profil în ~/Cantio/profiles/<profil>/alerts.json.

Dialogul NU trimite el însuși spre display — primește două funcții de la
control_window: on_show(text, opts) și on_hide(), ca să rămână decuplat.
"""

import json
import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QSpinBox, QPushButton, QListWidget, QListWidgetItem, QWidget,
    QColorDialog, QMessageBox, QFormLayout,
)

_STYLE = """
QDialog { background:#181818; color:#e0e0e0; font-family:'Segoe UI'; font-size:12px; }
QLabel { color:#cdd6f4; }
QLineEdit, QTextEdit, QSpinBox {
    background:#232323; color:#e0e0e0; border:1px solid #333; border-radius:5px; padding:6px; }
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus { border-color:#5294e2; }
QListWidget { background:#1e1e1e; border:1px solid #2a2a2a; border-radius:6px; outline:none; }
QListWidget::item { padding:7px 10px; border-bottom:1px solid #262626; }
QListWidget::item:selected { background:#313244; color:#f9e2af; }
QPushButton { background:#2a2a2a; color:#e0e0e0; border:1px solid #3a3a3a;
              border-radius:5px; padding:6px 12px; }
QPushButton:hover { background:#343434; }
QPushButton#show { background:#c9a227; color:#1a1a1a; border:none; font-weight:700; }
QPushButton#show:hover { background:#dbb436; }
QPushButton#hide { background:#3a2020; color:#f38ba8; border:1px solid #5a3030; }
QPushButton#hide:hover { background:#4a2828; }
"""


class AlertsDialog(QDialog):
    def __init__(self, parent, profile_dir, on_show, on_hide):
        super().__init__(parent)
        self._dir = profile_dir
        self._on_show = on_show
        self._on_hide = on_hide
        self._alerts = []          # list[dict]
        self._color = "#f9e2af"
        self.setWindowTitle("⚠ Alerte")
        self.setMinimumSize(640, 440)
        self.setStyleSheet(_STYLE)
        self._build_ui()
        self._load()
        self._refresh_list()

    def _path(self) -> str:
        try:
            os.makedirs(self._dir, exist_ok=True)
        except Exception:
            pass
        return os.path.join(self._dir, "alerts.json")

    # ── UI ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        # Left: list + add/delete
        left = QVBoxLayout()
        left.setSpacing(6)
        left.addWidget(QLabel("Alerte salvate"))
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        left.addWidget(self._list, 1)
        lb = QHBoxLayout()
        new_btn = QPushButton("＋ Nouă")
        new_btn.clicked.connect(self._new_alert)
        del_btn = QPushButton("🗑")
        del_btn.setFixedWidth(40)
        del_btn.clicked.connect(self._delete_alert)
        lb.addWidget(new_btn); lb.addWidget(del_btn)
        left.addLayout(lb)
        lw = QWidget(); lw.setLayout(left); lw.setFixedWidth(230)
        root.addWidget(lw)

        # Right: editor + actions
        right = QVBoxLayout()
        right.setSpacing(10)
        form = QFormLayout()
        form.setSpacing(8)
        self._name = QLineEdit()
        self._name.setPlaceholderText("ex: Copiii la clasă")
        form.addRow("Nume:", self._name)
        self._text = QTextEdit()
        self._text.setPlaceholderText("Textul alertei care se derulează pe ecran…")
        self._text.setMinimumHeight(90)
        form.addRow("Text:", self._text)

        self._repeats = QSpinBox()
        self._repeats.setRange(0, 999)
        self._repeats.setValue(3)
        self._repeats.setSuffix(" derulări (0 = continuu)")
        form.addRow("Repetări:", self._repeats)

        self._speed = QSpinBox()
        self._speed.setRange(1, 10)
        self._speed.setValue(3)
        form.addRow("Viteză (1–10):", self._speed)

        color_row = QHBoxLayout()
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(54, 26)
        self._color_btn.clicked.connect(self._pick_color)
        self._apply_color_btn()
        color_row.addWidget(self._color_btn)
        color_row.addStretch()
        cw = QWidget(); cw.setLayout(color_row)
        form.addRow("Culoare text:", cw)
        right.addLayout(form)

        save_row = QHBoxLayout()
        save_btn = QPushButton("💾 Salvează alerta")
        save_btn.clicked.connect(self._save_current)
        save_row.addWidget(save_btn)
        save_row.addStretch()
        right.addLayout(save_row)

        right.addStretch(1)

        actions = QHBoxLayout()
        self._show_btn = QPushButton("▶ Afișează live")
        self._show_btn.setObjectName("show")
        self._show_btn.clicked.connect(self._show_live)
        self._hide_btn = QPushButton("■ Ascunde")
        self._hide_btn.setObjectName("hide")
        self._hide_btn.clicked.connect(self._hide_live)
        actions.addWidget(self._show_btn, 1)
        actions.addWidget(self._hide_btn, 1)
        right.addLayout(actions)

        rw = QWidget(); rw.setLayout(right)
        root.addWidget(rw, 1)

    def _apply_color_btn(self):
        self._color_btn.setStyleSheet(
            f"background:{self._color}; border:1px solid #555; border-radius:5px;")

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self._color), self, "Culoare text alertă")
        if c.isValid():
            self._color = c.name()
            self._apply_color_btn()

    # ── Persistence ─────────────────────────────────────────────────────────
    def _load(self):
        try:
            with open(self._path(), encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._alerts = [a for a in data if isinstance(a, dict)]
        except Exception:
            self._alerts = []

    def _save(self):
        try:
            with open(self._path(), "w", encoding="utf-8") as f:
                json.dump(self._alerts, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "Eroare", f"Nu am putut salva alertele:\n{e}")

    def _refresh_list(self):
        self._list.blockSignals(True)
        self._list.clear()
        for a in self._alerts:
            it = QListWidgetItem(a.get("name") or (a.get("text", "")[:24] or "(fără nume)"))
            self._list.addItem(it)
        self._list.blockSignals(False)

    # ── Form <-> data ─────────────────────────────────────────────────────
    def _on_select(self, row: int):
        if row < 0 or row >= len(self._alerts):
            return
        a = self._alerts[row]
        self._name.setText(a.get("name", ""))
        self._text.setPlainText(a.get("text", ""))
        self._repeats.setValue(int(a.get("repeats", 3)))
        self._speed.setValue(int(a.get("speed", 3)))
        self._color = a.get("color", "#f9e2af")
        self._apply_color_btn()

    def _form_data(self) -> dict:
        return {
            "name":    self._name.text().strip(),
            "text":    self._text.toPlainText().strip(),
            "repeats": self._repeats.value(),
            "speed":   self._speed.value(),
            "color":   self._color,
        }

    def _new_alert(self):
        self._list.clearSelection()
        self._list.setCurrentRow(-1)
        self._name.clear(); self._text.clear()
        self._repeats.setValue(3); self._speed.setValue(3)
        self._color = "#f9e2af"; self._apply_color_btn()
        self._name.setFocus()

    def _save_current(self):
        data = self._form_data()
        if not data["text"]:
            QMessageBox.information(self, "Alertă goală", "Scrie un text pentru alertă.")
            return
        if not data["name"]:
            data["name"] = data["text"][:24]
        row = self._list.currentRow()
        if 0 <= row < len(self._alerts):
            self._alerts[row] = data
        else:
            self._alerts.append(data)
            row = len(self._alerts) - 1
        self._save()
        self._refresh_list()
        self._list.setCurrentRow(row)

    def _delete_alert(self):
        row = self._list.currentRow()
        if not (0 <= row < len(self._alerts)):
            return
        if QMessageBox.question(
            self, "Șterge alerta", "Ștergi alerta selectată?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        del self._alerts[row]
        self._save()
        self._refresh_list()
        self._new_alert()

    # ── Live ────────────────────────────────────────────────────────────────
    def _show_live(self):
        data = self._form_data()
        if not data["text"]:
            QMessageBox.information(self, "Alertă goală", "Scrie un text pentru alertă.")
            return
        try:
            self._on_show(data["text"], {
                "repeats": data["repeats"],
                "speed":   data["speed"],
                "color":   data["color"],
            })
        except Exception as e:
            QMessageBox.warning(self, "Eroare", str(e))

    def _hide_live(self):
        try:
            self._on_hide()
        except Exception:
            pass
