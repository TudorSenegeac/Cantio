# -*- coding: utf-8 -*-
"""
CantioPresenter — Fereastră de bun venit (prima pornire)
==============================================
La prima pornire, întreabă utilizatorul dacă vrea să se aboneze la noutăți
(newsletter). E-mailul se trimite GRATUIT prin FormSubmit (fără server, fără
credențiale) pe adresa CantioPresenter, de unde poți construi lista de abonați.

Nu apare decât o singură dată (marcat în cache).
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QCheckBox,
)

try:
    from feedback_dialog import _SendWorker, FEEDBACK_EMAIL
except Exception:  # pragma: no cover
    _SendWorker = None
    FEEDBACK_EMAIL = "cantioapp@gmail.com"


def _brevo_configured() -> bool:
    try:
        import database as db
        return bool((db.get_settings().get("brevo_api_key", "") or "").strip())
    except Exception:
        return False


def _brevo_add_contact(email: str, church: str = ""):
    """Adaugă abonatul în lista Brevo (newsletter), dacă e configurată o cheie API.
    Rulează pe un fir separat; nicio eroare nu iese afară."""
    try:
        import database as db, json, urllib.request
        s = db.get_settings()
        key = (s.get("brevo_api_key", "") or "").strip()
        if not key or not email:
            return
        body = {"email": email, "updateEnabled": True}
        if church:
            body["attributes"] = {"CHURCH": church}
        list_id = (s.get("brevo_list_id", "") or "").strip()
        if list_id:
            try:
                body["listIds"] = [int(list_id)]
            except Exception:
                pass
        req = urllib.request.Request(
            "https://api.brevo.com/v3/contacts",
            data=json.dumps(body).encode("utf-8"),
            headers={"api-key": key, "Content-Type": "application/json",
                     "accept": "application/json"})
        urllib.request.urlopen(req, timeout=15)
    except Exception:
        pass

_STYLE = """
QDialog { background:#181818; color:#e6e6ea; font-family:'Segoe UI'; font-size:13px; }
QLabel#title { font-size:20px; font-weight:700; color:#cba6f7; }
QLabel#sub   { color:#9a9aa5; font-size:12px; }
QLabel#status{ font-size:12px; }
QLineEdit { background:#232323; color:#e0e0e0; border:1px solid #333; border-radius:7px; padding:9px 11px; }
QLineEdit:focus { border-color:#7c5cff; }
QCheckBox { color:#cdd6f4; }
QPushButton { background:#2a2a2a; color:#e0e0e0; border:1px solid #3a3a3a; border-radius:7px; padding:9px 16px; }
QPushButton:hover { background:#343434; }
QPushButton#go { background:#7c5cff; color:#fff; border:none; font-weight:600; }
QPushButton#go:hover { background:#8a6cff; }
QPushButton#go:disabled { background:#3a3550; color:#999; }
"""


class WelcomeDialog(QDialog):
    def __init__(self, parent=None, app_version: str = "1.5.2"):
        super().__init__(parent)
        self._app_version = app_version
        self._worker = None
        self.setWindowTitle("Bun venit în CantioPresenter")
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setStyleSheet(_STYLE)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(10)

        title = QLabel("🎉 Bun venit în CantioPresenter!")
        title.setObjectName("title")
        root.addWidget(title)

        sub = QLabel(
            "Mulțumim că folosești CantioPresenter — software gratuit de proiecție pentru biserici.\n"
            "Lasă-ne e-mailul tău ca să primești vești despre versiuni noi, cântări și funcții. "
            "Fără spam, te poți dezabona oricând."
        )
        sub.setObjectName("sub")
        sub.setWordWrap(True)
        root.addWidget(sub)

        self._email = QLineEdit()
        self._email.setPlaceholderText("adresa-ta@email.com")
        root.addWidget(self._email)

        self._church = QLineEdit()
        self._church.setPlaceholderText("Biserica / numele tău (opțional)")
        root.addWidget(self._church)

        self._status = QLabel("")
        self._status.setObjectName("status")
        self._status.setWordWrap(True)
        self._status.setVisible(False)
        root.addWidget(self._status)

        btns = QHBoxLayout()
        self._later_btn = QPushButton("Mai târziu")
        self._later_btn.clicked.connect(self.reject)
        btns.addWidget(self._later_btn)
        btns.addStretch(1)
        self._go_btn = QPushButton("Abonează-mă")
        self._go_btn.setObjectName("go")
        self._go_btn.setDefault(True)
        self._go_btn.clicked.connect(self._subscribe)
        btns.addWidget(self._go_btn)
        root.addLayout(btns)

    def _set_status(self, text, color="#9a9aa5"):
        self._status.setText(text)
        self._status.setStyleSheet(f"color:{color};")
        self._status.setVisible(bool(text))

    def _subscribe(self):
        email = self._email.text().strip()
        if "@" not in email or "." not in email.split("@")[-1]:
            self._set_status("Introdu o adresă de e-mail validă.", "#f38ba8")
            self._email.setFocus()
            return
        # Dacă e configurat Brevo (serviciu de newsletter), adaugă abonatul în listă
        # ca administratorul să poată trimite campanii către toți. Rulează în fundal.
        try:
            import threading
            threading.Thread(target=_brevo_add_contact,
                             args=(email, self._church.text().strip()),
                             daemon=True).start()
        except Exception:
            pass
        if _SendWorker is None:
            # Fără FormSubmit, dar dacă Brevo e configurat tot am abonat utilizatorul.
            if _brevo_configured():
                self._on_done(True, "")
                return
            self._set_status("Nu pot trimite acum. Încearcă mai târziu.", "#f38ba8")
            return
        payload = {
            "_subject": "[CantioPresenter Newsletter] Înscriere nouă",
            "_template": "table",
            "_captcha": "false",
            "Email": email,
            "Biserica": self._church.text().strip() or "—",
            "Versiune_CantioPresenter": self._app_version,
            "email": email,   # Reply-To
        }
        self._go_btn.setEnabled(False)
        self._later_btn.setEnabled(False)
        self._set_status("Se trimite… (poate dura câteva secunde)", "#89b4fa")
        self._worker = _SendWorker(payload, self)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok, message):
        self._later_btn.setEnabled(True)
        if ok:
            self._set_status("✓ Mulțumim! Te-ai abonat la noutățile CantioPresenter.", "#a6e3a1")
            self._go_btn.setText("Gata ✓")
            self._email.setReadOnly(True)
            self._church.setReadOnly(True)
            self._later_btn.setText("Închide")
        elif message == "__ACTIVATION__":
            self._go_btn.setEnabled(True)
            self._set_status(
                "Serviciul se activează (pas unic). Încearcă din nou în câteva minute.",
                "#f9e2af")
        else:
            self._go_btn.setEnabled(True)
            self._set_status(
                "Nu am putut trimite: " + (message or "eroare necunoscută") +
                f"\nPoți scrie direct la {FEEDBACK_EMAIL}.", "#f38ba8")
