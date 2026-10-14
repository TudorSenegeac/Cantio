# -*- coding: utf-8 -*-
"""
Cantio — Notificări
===================
Sistem simplu de anunțuri către utilizatori (versiuni noi, baze de date noi,
mesaje de la echipă) FĂRĂ backend: aplicația descarcă periodic un fișier JSON
publicat de dezvoltator și afișează anunțurile noi.

Pentru a trimite o notificare, editezi `notifications.json` în repo
(https://github.com/TudorSenegeac/Cantio) și faci commit — toți utilizatorii
o văd la următoarea pornire / verificare.

Format notifications.json:
{
  "notifications": [
    {
      "id": "2026-10-15-db-noua",        # unic (obligatoriu)
      "title": "Bază de date nouă",
      "body": "A apărut o colecție nouă de cântări. Descarc-o din...",
      "date": "2026-10-15",
      "type": "update",                   # info | update | db | warning
      "url": "https://cantioapp.com/..."  # optional (buton 'Deschide')
    }
  ]
}

Anunțurile citite se rețin local (cache 'seen_notifications'), ca să nu
reapară. Cererea de rețea rulează pe un fir separat (urllib, fără dependințe).
"""

import json
import urllib.request
import urllib.error

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QWidget, QFrame,
)

NOTIF_URL = "https://raw.githubusercontent.com/TudorSenegeac/Cantio/main/notifications.json"

_TYPE_META = {
    "info":    ("ℹ️", "#89b4fa"),
    "update":  ("⬆️", "#a6e3a1"),
    "db":      ("📚", "#f9e2af"),
    "warning": ("⚠️", "#f38ba8"),
}


class NotificationsFetcher(QThread):
    """Descarcă notifications.json pe un fir separat."""
    done = pyqtSignal(list)   # list[dict]

    def __init__(self, url: str = NOTIF_URL, parent=None):
        super().__init__(parent)
        self._url = url

    def run(self):
        try:
            req = urllib.request.Request(
                self._url, headers={"User-Agent": "Cantio-Notifications",
                                    "Cache-Control": "no-cache"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8", "replace")
            data = json.loads(raw)
            items = data.get("notifications", []) if isinstance(data, dict) else data
            out = []
            if isinstance(items, list):
                for it in items:
                    if isinstance(it, dict) and it.get("id") and it.get("title"):
                        out.append(it)
            self.done.emit(out)
        except Exception:
            self.done.emit([])


class NotificationsDialog(QDialog):
    def __init__(self, parent, notifications: list, seen_ids: set):
        super().__init__(parent)
        self._notifs = notifications or []
        self._seen = set(seen_ids or set())
        self.setWindowTitle("🔔 Notificări")
        self.setMinimumSize(460, 420)
        self.resize(480, 460)
        self.setStyleSheet(
            "QDialog { background:#181818; color:#e0e0e0; font-family:'Segoe UI'; }"
            "QLabel { color:#e0e0e0; }"
            "QPushButton { background:#2a2a2a; color:#e0e0e0; border:1px solid #3a3a3a;"
            " border-radius:5px; padding:6px 12px; } QPushButton:hover { background:#343434; }"
        )
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        head = QHBoxLayout()
        title = QLabel("🔔 Notificări")
        title.setStyleSheet("font-size:16px; font-weight:600; color:#cba6f7;")
        head.addWidget(title)
        head.addStretch()
        mark_btn = QPushButton("Marchează toate citite")
        mark_btn.clicked.connect(self._mark_all_read)
        head.addWidget(mark_btn)
        root.addLayout(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; }")
        container = QWidget()
        self._vbox = QVBoxLayout(container)
        self._vbox.setSpacing(8)
        self._vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        if not self._notifs:
            empty = QLabel("Nu există notificări.")
            empty.setStyleSheet("color:#666; padding:30px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._vbox.addWidget(empty)
        else:
            for n in self._notifs:
                self._vbox.addWidget(self._make_card(n))

    def _make_card(self, n: dict) -> QWidget:
        icon, color = _TYPE_META.get(str(n.get("type", "info")), _TYPE_META["info"])
        is_new = n.get("id") not in self._seen
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background:#1e1e1e; border:1px solid "
            f"{'#3a3350' if is_new else '#262626'}; border-radius:8px; }}")
        v = QVBoxLayout(card)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(4)

        top = QHBoxLayout()
        htxt = f"{icon}  {n.get('title', '')}"
        hl = QLabel(htxt)
        hl.setStyleSheet(f"font-weight:600; font-size:13px; color:{color};")
        top.addWidget(hl)
        top.addStretch()
        if is_new:
            badge = QLabel("NOU")
            badge.setStyleSheet(
                "background:#cba6f7; color:#1a1a1a; border-radius:3px; "
                "padding:1px 6px; font-size:9px; font-weight:700;")
            top.addWidget(badge)
        date_lbl = QLabel(str(n.get("date", "")))
        date_lbl.setStyleSheet("color:#666; font-size:10px;")
        top.addWidget(date_lbl)
        v.addLayout(top)

        body = QLabel(str(n.get("body", "")))
        body.setWordWrap(True)
        body.setStyleSheet("color:#c0c0c0; font-size:12px;")
        v.addWidget(body)

        url = n.get("url")
        if url:
            row = QHBoxLayout()
            row.addStretch()
            open_btn = QPushButton("Deschide")
            open_btn.clicked.connect(lambda _=False, u=url: self._open_url(u))
            row.addWidget(open_btn)
            v.addLayout(row)
        return card

    def _open_url(self, url: str):
        try:
            from PyQt6.QtGui import QDesktopServices
            from PyQt6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl(url))
        except Exception:
            pass

    def _mark_all_read(self):
        self._seen = {n.get("id") for n in self._notifs if n.get("id")}
        self.accept()

    def seen_ids(self) -> set:
        return self._seen

    def showEvent(self, event):
        super().showEvent(event)
        # Centrează fereastra pe ecranul părinte (sau ecranul principal).
        try:
            from PyQt6.QtWidgets import QApplication
            parent = self.parent()
            if parent is not None and parent.window().isVisible():
                geo = parent.window().frameGeometry()
            else:
                geo = QApplication.primaryScreen().availableGeometry()
            fg = self.frameGeometry()
            fg.moveCenter(geo.center())
            self.move(fg.topLeft())
        except Exception:
            pass
