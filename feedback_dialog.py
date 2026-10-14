# -*- coding: utf-8 -*-
"""
Cantio — Dialog Feedback
========================
Permite utilizatorului să trimită feedback (bug / sugestie / întrebare)
direct din aplicație către cantioapp@gmail.com.

Trimiterea se face printr-un serviciu gratuit de forwardare (FormSubmit.co)
folosind endpoint-ul AJAX, deci:
  • nu necesită un client de email configurat pe calculator;
  • nu necesită parole/credențiale în codul sursă (sigur pentru un repo public).

La PRIMA trimitere, FormSubmit trimite un email de activare pe adresa
cantioapp@gmail.com — trebuie apăsat link-ul din acel email o singură dată;
după aceea toate mesajele ajung normal.

Cererea de rețea rulează pe un fir separat (QThread) ca să nu înghețe UI-ul,
folosind doar urllib din biblioteca standard (fără dependințe noi).
"""

import json
import platform
import urllib.request
import urllib.error

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QTextEdit, QPushButton, QWidget,
)

# Adresa pe care se primește feedback-ul. Expusă doar prin serviciul de
# forwardare — poate fi schimbată aici fără alte modificări.
FEEDBACK_EMAIL = "cantioapp@gmail.com"
FORMSUBMIT_URL = "https://formsubmit.co/ajax/" + FEEDBACK_EMAIL

_DIALOG_STYLE = """
QDialog { background-color: #181818; color: #e0e0e0;
          font-family: 'Segoe UI', sans-serif; font-size: 13px; }
QLabel  { color: #e0e0e0; }
QLabel#title  { font-size: 18px; font-weight: 600; color: #cba6f7; }
QLabel#sub    { color: #9a9a9a; font-size: 12px; }
QLabel#status { font-size: 12px; }
QLineEdit, QComboBox, QTextEdit {
    background: #232323; color: #e0e0e0; border: 1px solid #333;
    border-radius: 6px; padding: 7px 9px; selection-background-color: #5294e2;
}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus { border: 1px solid #5294e2; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: #232323; color: #e0e0e0; selection-background-color: #313244;
    border: 1px solid #333; outline: none;
}
QPushButton {
    background: #2a2a2a; color: #e0e0e0; border: 1px solid #3a3a3a;
    border-radius: 6px; padding: 8px 18px;
}
QPushButton:hover { background: #343434; }
QPushButton#send {
    background: #7c5cff; color: white; border: none; font-weight: 600;
}
QPushButton#send:hover   { background: #8a6cff; }
QPushButton#send:disabled{ background: #3a3550; color: #9a9a9a; }
"""


class _SendWorker(QThread):
    """Trimite payload-ul către FormSubmit pe un fir separat."""
    done = pyqtSignal(bool, str)   # (succes, mesaj)

    def __init__(self, payload: dict, parent=None):
        super().__init__(parent)
        self._payload = payload

    def run(self):
        try:
            data = json.dumps(self._payload).encode("utf-8")
            req = urllib.request.Request(
                FORMSUBMIT_URL, data=data, method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "Cantio-Feedback",
                },
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8", "replace")
            try:
                obj = json.loads(raw)
            except Exception:
                obj = {}
            ok = str(obj.get("success", "")).lower() == "true"
            if ok:
                self.done.emit(True, "")
            else:
                msg = obj.get("message", "Serviciul de trimitere a refuzat mesajul.")
                self.done.emit(False, str(msg))
        except urllib.error.URLError as e:
            self.done.emit(False, f"Fără conexiune la internet? ({e.reason})")
        except Exception as e:  # pragma: no cover - defensiv
            self.done.emit(False, str(e))


class FeedbackDialog(QDialog):
    """Pagina de feedback din meniul Ajutor."""

    def __init__(self, parent=None, app_version: str = "1.5.2"):
        super().__init__(parent)
        self._app_version = app_version
        self._worker = None
        self.setWindowTitle("Trimite Feedback — Cantio")
        self.setModal(True)
        self.setMinimumWidth(480)
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(12)

        title = QLabel("💬 Trimite Feedback")
        title.setObjectName("title")
        root.addWidget(title)

        sub = QLabel(
            "Spune-ne ce funcționează, ce nu, sau ce ai vrea să adăugăm. "
            "Mesajul ajunge direct la echipa Cantio."
        )
        sub.setObjectName("sub")
        sub.setWordWrap(True)
        root.addWidget(sub)

        # Tip feedback
        root.addWidget(self._lbl("Tip"))
        self._cat = QComboBox()
        self._cat.addItems([
            "🐞 Problemă / Bug",
            "💡 Sugestie / Idee",
            "❓ Întrebare",
            "💬 Altceva",
        ])
        root.addWidget(self._cat)

        # Nume + email (opționale) pe un rând
        row = QHBoxLayout()
        row.setSpacing(10)
        col1 = QVBoxLayout()
        col1.addWidget(self._lbl("Numele tău (opțional)"))
        self._name = QLineEdit()
        self._name.setPlaceholderText("ex: Biserica Harul")
        col1.addWidget(self._name)
        col2 = QVBoxLayout()
        col2.addWidget(self._lbl("Email pentru răspuns (opțional)"))
        self._email = QLineEdit()
        self._email.setPlaceholderText("ca să-ți putem răspunde")
        col2.addWidget(self._email)
        w1, w2 = QWidget(), QWidget()
        w1.setLayout(col1); w2.setLayout(col2)
        row.addWidget(w1); row.addWidget(w2)
        root.addLayout(row)

        # Mesaj
        root.addWidget(self._lbl("Mesaj"))
        self._msg = QTextEdit()
        self._msg.setPlaceholderText("Scrie aici feedback-ul tău…")
        self._msg.setMinimumHeight(130)
        root.addWidget(self._msg)

        # Status
        self._status = QLabel("")
        self._status.setObjectName("status")
        self._status.setWordWrap(True)
        self._status.setVisible(False)
        root.addWidget(self._status)

        # Butoane
        btns = QHBoxLayout()
        btns.addStretch(1)
        self._cancel_btn = QPushButton("Închide")
        self._cancel_btn.clicked.connect(self.reject)
        self._send_btn = QPushButton("Trimite")
        self._send_btn.setObjectName("send")
        self._send_btn.setDefault(True)
        self._send_btn.clicked.connect(self._on_send)
        btns.addWidget(self._cancel_btn)
        btns.addWidget(self._send_btn)
        root.addLayout(btns)

        self._msg.setFocus()

    @staticmethod
    def _lbl(text: str) -> QLabel:
        lbl = QLabel(text)
        return lbl

    # ── Trimitere ───────────────────────────────────────────────────────────
    def _set_status(self, text: str, color: str = "#9a9a9a"):
        self._status.setText(text)
        self._status.setStyleSheet(f"color: {color};")
        self._status.setVisible(bool(text))

    def _on_send(self):
        text = self._msg.toPlainText().strip()
        if len(text) < 3:
            self._set_status("Scrie te rog un mesaj înainte de a trimite.", "#f38ba8")
            self._msg.setFocus()
            return

        email = self._email.text().strip()
        name = self._name.text().strip()
        category = self._cat.currentText()

        try:
            os_info = f"{platform.system()} {platform.release()}"
        except Exception:
            os_info = "necunoscut"

        payload = {
            "_subject": f"[Cantio Feedback] {category}",
            "_template": "table",
            "_captcha": "false",
            "Tip": category,
            "Nume": name or "—",
            "Email_raspuns": email or "—",
            "Mesaj": text,
            "Versiune_Cantio": self._app_version,
            "Sistem": os_info,
        }
        # FormSubmit folosește câmpul 'email' ca Reply-To, dacă e valid.
        if email:
            payload["email"] = email

        self._send_btn.setEnabled(False)
        self._cancel_btn.setEnabled(False)
        self._set_status("Se trimite…", "#89b4fa")

        self._worker = _SendWorker(payload, self)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str):
        self._cancel_btn.setEnabled(True)
        if ok:
            self._set_status(
                "✓ Mulțumim! Feedback-ul tău a fost trimis.", "#a6e3a1")
            self._send_btn.setText("Trimis ✓")
            self._msg.setReadOnly(True)
            self._name.setReadOnly(True)
            self._email.setReadOnly(True)
            self._cancel_btn.setText("Închide")
        else:
            self._send_btn.setEnabled(True)
            self._set_status(
                "Nu am putut trimite: " + (message or "eroare necunoscută") +
                f"\nPoți scrie direct la {FEEDBACK_EMAIL}.", "#f38ba8")
