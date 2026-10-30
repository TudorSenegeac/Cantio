# -*- coding: utf-8 -*-
"""
Cantio — fereastra „Ce e nou" (changelog la actualizare).

Se afișează o singură dată după ce utilizatorul instalează o versiune NOUĂ peste
una veche (prima pornire a versiunii noi). La prima instalare vreodată NU apare
(se afișează tutorialul). Urmărirea se face prin cache-ul db: „whatsnew_seen_version".
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QWidget, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl

# Linkuri sociale ale PLATFORMEI (de pe www.cantioapp.com).
_SOCIAL = [
    ("🌐  Website",   "https://www.cantioapp.com"),
    ("📘  Facebook",  "https://www.facebook.com/profile.php?id=61594870153654"),
    ("📸  Instagram", "https://www.instagram.com/cantiopresenter"),
    ("✈  Telegram",   "https://t.me/cantio_comunitate"),
]

# Changelog per versiune. Adaugă o intrare nouă sus la fiecare release.
_CHANGELOG = {
    "1.5.2": {
        "Nou": [
            "🎬 Overlay-uri peste ecranul live (ceas, text derulant, logo, forme) — stil FreeShow",
            "📱 Telefon (Remote) complet: previzualizare 1:1 cu proiectorul, Looks, Macros, Overlay-uri",
            "📖 Control Biblie din telefon — caută referința, navighează, vezi capitolul întreg",
            "✏️ Editezi strofele direct din telefon",
            "🎨 Fundaluri noi: Pagină de Biblie, gradienturi continue, efect Matrix",
            "🖌️ Casetă text liberă + fundal diferit per etichetă (strofă/refren) în Teme",
            "🌍 Traducere mult mai bună (DeepL) + 10 limbi gata offline (en, de, fr, hu, es, it, ru, uk, pl, pt)",
        ],
        "Îmbunătățit": [
            "🕐 Ceasul: apariție lină (fade) și auto-ascundere când versurile îl acoperă",
            "⚡ Consum GPU mult mai mic — nu mai supraîncălzește laptopul",
            "📑 Împărțire automată a slide-urilor pe N rânduri din temă",
        ],
        "Reparat": [
            "🖼️ Fundalul temei apare acum și pe proiector (nu doar în previzualizare)",
            "📐 Forma previzualizării se potrivește cu fereastra live fullscreen",
            "🎞️ Videoclipurile de fundal fără buclă pornesc de fiecare dată",
            "📖 Biblia: fără cuvinte sacre din setări + împărțire normală a textului",
            "➕ Zeci de alte corecții (YouTube, remote, titluri de ferestre, stabilitate)",
        ],
    },
}


class WhatsNewDialog(QDialog):
    def __init__(self, parent=None, version: str = "1.5.2"):
        super().__init__(parent)
        self.version = version
        self.setWindowTitle(f"Ce e nou — CantioPresenter v{version}")
        self.setMinimumSize(560, 620)
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("""
            QDialog { background: #1a1a2e; }
            QLabel  { color: #cdd6f4; }
            QScrollArea { border: none; background: transparent; }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(12)

        title = QLabel(f"🎉  Ce e nou în CantioPresenter v{self.version}")
        title.setStyleSheet("font-size: 19px; font-weight: 700; color: #cba6f7;")
        title.setWordWrap(True)
        root.addWidget(title)

        sub = QLabel("Mulțumim că folosești CantioPresenter! Iată ce s-a schimbat:")
        sub.setStyleSheet("color: #9399b2; font-size: 12px;")
        sub.setWordWrap(True)
        root.addWidget(sub)

        # Conținut scrollabil
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(2, 4, 8, 4)
        bl.setSpacing(14)

        data = _CHANGELOG.get(self.version, {})
        _colors = {"Nou": "#a6e3a1", "Îmbunătățit": "#89b4fa", "Reparat": "#f9e2af"}
        for section, items in data.items():
            h = QLabel(section)
            h.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {_colors.get(section, '#cba6f7')};")
            bl.addWidget(h)
            for it in items:
                row = QLabel(it)
                row.setWordWrap(True)
                row.setStyleSheet("font-size: 13px; color: #cdd6f4; padding-left: 4px;")
                bl.addWidget(row)
        bl.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # Separator
        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #313244; background:#313244; max-height:1px;")
        root.addWidget(line)

        # Social media
        soc_lbl = QLabel("Urmărește-ne pentru noutăți, sfaturi și ajutor:")
        soc_lbl.setStyleSheet("color: #9399b2; font-size: 12px;")
        root.addWidget(soc_lbl)
        soc_row = QHBoxLayout(); soc_row.setSpacing(8)
        for label, url in _SOCIAL:
            b = QPushButton(label)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                "QPushButton { background:#24243a; color:#cdd6f4; border:1px solid #313244;"
                " border-radius:6px; padding:8px 10px; font-size:12px; }"
                "QPushButton:hover { background:#313244; color:#cba6f7; }")
            b.clicked.connect(lambda _=False, u=url: QDesktopServices.openUrl(QUrl(u)))
            soc_row.addWidget(b)
        root.addLayout(soc_row)

        # Buton OK
        ok_row = QHBoxLayout(); ok_row.addStretch()
        ok = QPushButton("Super, hai să începem!  ✓")
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.setStyleSheet(
            "QPushButton { background:#5294e2; color:#fff; border:none; border-radius:6px;"
            " padding:9px 20px; font-weight:600; font-size:13px; }"
            "QPushButton:hover { background:#6aa5ec; }")
        ok.clicked.connect(self.accept)
        ok_row.addWidget(ok)
        root.addLayout(ok_row)


def maybe_show_whats_new(parent, version: str) -> bool:
    """Afișează „Ce e nou" DOAR dacă s-a trecut la o versiune nouă peste una veche.
    Returnează True dacă a fost afișată. La prima instalare vreodată nu apare."""
    try:
        import database as db
        cache = db.get_cache()
        seen = cache.get("whatsnew_seen_version")
        shown = False
        # Afișăm doar dacă exista o versiune anterioară ȘI diferă (deci update).
        if seen and seen != version and version in _CHANGELOG:
            try:
                WhatsNewDialog(parent, version).exec()
                shown = True
            except Exception as e:
                print(f"[WhatsNew] show failed: {e}")
        cache["whatsnew_seen_version"] = version
        db.save_cache(cache)
        return shown
    except Exception as e:
        print(f"[WhatsNew] check failed: {e}")
        return False
