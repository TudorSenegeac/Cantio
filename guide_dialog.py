# -*- coding: utf-8 -*-
"""
Cantio — Ghid rapid în 10 pași (mini-prezentare „cum se folosește corect").
Se deschide din meniul Ajutor. Navigare Înapoi / Înainte, cu indicator de pas.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl

_SLIDES = [
    ("👋", "Bun venit în CantioPresenter",
     "Ecranul are 3 zone:\n\n"
     "• <b>Stânga — Serviciu & Bibliotecă</b>: lista de cântări și ordinea slujbei\n"
     "• <b>Centru — Editor & Slide-uri</b>: versurile și slide-urile cântării\n"
     "• <b>Dreapta — Previzualizare & Controale</b>: ce apare pe proiector + butoane\n\n"
     "Hai să vedem cum le folosești, pas cu pas. 🚀"),
    ("🔎", "1. Găsește o cântare",
     "În <b>Bibliotecă</b> (stânga jos) ai toate cântările.\n\n"
     "• Scrie în bara de căutare — merge cu sau fără diacritice\n"
     "• <b>Click simplu</b> = selectezi și previzualizezi\n"
     "• <b>Dublu-click</b> = deschizi în editor ca să modifici\n"
     "• <b>Click dreapta</b> = opțiuni (mută în categorie, fundal pe secțiuni…)"),
    ("📋", "2. Pregătește serviciul",
     "Adaugă cântările în ordinea slujbei:\n\n"
     "• Selectează o cântare → <b>+ Serviciu</b>\n"
     "• Reordonează cu săgețile ▲ ▼ sau trage elementele\n"
     "• Adaugă și versete din Biblie\n"
     "• <b>Ctrl+S</b> salvezi serviciul • <b>Ctrl+O</b> îl redeschizi"),
    ("📺", "3. Deschide proiectorul",
     "Conectează proiectorul/TV-ul, apoi:\n\n"
     "• Apasă <b>📺 Display</b> (sus-dreapta) — pornește fereastra live\n"
     "• Ecranul se alege din <b>Setări</b> (dacă ai mai multe monitoare)\n"
     "• Fereastra live rămâne neagră până trimiți un slide"),
    ("▶", "4. Trimite versuri live",
     "• <b>Click pe un slide</b> = îl trimiți direct pe proiector\n"
     "• <b>GO LIVE</b> = trimite slide-ul selectat\n"
     "• Navighează cu <b>◀ ▶</b> sau săgețile de pe tastatură\n\n"
     "Scurtături: <b>Space</b> = GO LIVE • <b>Escape</b> = Ecran negru"),
    ("🎨", "5. Teme, fundaluri & text",
     "În tab-ul <b>Teme</b> alegi cum arată textul pe ecran:\n\n"
     "• Font, culoare, aliniere, fundal (culoare / imagine / fundal animat)\n"
     "• <b>Casetă text liberă</b> — poziționezi textul oriunde\n"
     "• <b>Fundal per etichetă</b> — alt fundal la strofă vs. refren\n"
     "• Un <b>Look</b> activ schimbă instant tema pe toate cântările"),
    ("📖", "6. Biblia",
     "Tab-ul <b>Control Bible</b>:\n\n"
     "• Scrie o referință (ex. Ioan 3:16) sau caută un cuvânt\n"
     "• Vezi tot capitolul; click pe verset = îl trimiți live\n"
     "• Navighează cu ◀ ▶ între versete\n"
     "• Poți evidenția o parte din verset pe ecran"),
    ("🎬", "7. Overlay-uri & ceas",
     "Elemente afișate PESTE versuri (ca în FreeShow):\n\n"
     "• <b>Ceas</b> — colț, cu apariție lină; se ascunde când textul îl acoperă\n"
     "• <b>Ticker</b> — text derulant (anunțuri)\n"
     "• <b>Overlay-uri</b> — logo, text, forme, create în editorul de fundaluri\n"
     "• Le pornești/oprești din panoul dreapta sau din telefon"),
    ("📱", "8. Controlează de pe telefon",
     "Apasă <b>Remote</b> (meniul de sus) → apare un cod QR.\n\n"
     "• Scanează-l cu telefonul (pe aceeași rețea Wi-Fi)\n"
     "• De pe telefon: GO LIVE, slide-uri, Biblie, Looks, Macros, ceas\n"
     "• Vezi o <b>previzualizare 1:1</b> cu proiectorul\n"
     "• Poți chiar edita strofele din telefon"),
    ("✅", "Gata — ești pregătit!",
     "Ai văzut tot ce trebuie ca să conduci o slujbă. 🎉\n\n"
     "Ajutor: <b>cantioapp.com/helpdesk</b> • <b>Ajutor → Tutorial</b> interactiv\n\n"
     "📣 Urmărește-ne pentru noutăți și sfaturi:\n"
     "📘 Facebook   📸 Instagram   ✈ Telegram   🌐 www.cantioapp.com\n\n"
     "Mult succes la servicii! 🙏"),
]

_SOCIAL = [
    ("🌐 Website", "https://www.cantioapp.com"),
    ("📘 Facebook", "https://www.facebook.com/profile.php?id=61594870153654"),
    ("📸 Instagram", "https://www.instagram.com/cantiopresenter"),
    ("✈ Telegram", "https://t.me/cantio_comunitate"),
]


class GuideDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ghid rapid — CantioPresenter")
        self.setMinimumSize(560, 520)
        self._i = 0
        self._build_ui()
        self._show_slide()

    def _build_ui(self):
        self.setStyleSheet("QDialog { background:#1a1a2e; } QLabel { color:#cdd6f4; }")
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 18)
        root.setSpacing(12)

        self._icon = QLabel(); self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setStyleSheet("font-size: 52px;")
        root.addWidget(self._icon)

        self._title = QLabel(); self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setWordWrap(True)
        self._title.setStyleSheet("font-size: 19px; font-weight: 700; color: #cba6f7;")
        root.addWidget(self._title)

        self._body = QLabel(); self._body.setWordWrap(True)
        self._body.setTextFormat(Qt.TextFormat.RichText)
        self._body.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._body.setStyleSheet("font-size: 13px; color: #cdd6f4; line-height: 150%;")
        self._body.setMinimumHeight(220)
        root.addWidget(self._body, 1)

        # Social (vizibil doar pe ultimul slide)
        self._soc_row = QHBoxLayout(); self._soc_row.setSpacing(8)
        self._soc_widgets = []
        for label, url in _SOCIAL:
            b = QPushButton(label); b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                "QPushButton { background:#24243a; color:#cdd6f4; border:1px solid #313244;"
                " border-radius:6px; padding:6px 8px; font-size:11px; }"
                "QPushButton:hover { background:#313244; color:#cba6f7; }")
            b.clicked.connect(lambda _=False, u=url: QDesktopServices.openUrl(QUrl(u)))
            self._soc_row.addWidget(b); self._soc_widgets.append(b)
        root.addLayout(self._soc_row)

        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color:#313244; background:#313244; max-height:1px;")
        root.addWidget(line)

        # Navigare
        nav = QHBoxLayout()
        self._dots = QLabel(); self._dots.setStyleSheet("color:#6c7086; font-size:12px;")
        nav.addWidget(self._dots); nav.addStretch()
        self._back = QPushButton("◀ Înapoi"); self._back.clicked.connect(self._prev)
        self._back.setStyleSheet(
            "QPushButton { background:#24243a; color:#cdd6f4; border:1px solid #313244;"
            " border-radius:6px; padding:8px 16px; } QPushButton:disabled { color:#45475a; }")
        nav.addWidget(self._back)
        self._next = QPushButton("Înainte ▶"); self._next.clicked.connect(self._nextStep)
        self._next.setStyleSheet(
            "QPushButton { background:#5294e2; color:#fff; border:none; border-radius:6px;"
            " padding:8px 18px; font-weight:600; } QPushButton:hover { background:#6aa5ec; }")
        nav.addWidget(self._next)
        root.addLayout(nav)

    def _show_slide(self):
        icon, title, body = _SLIDES[self._i]
        self._icon.setText(icon)
        self._title.setText(title)
        self._body.setText(body.replace("\n", "<br>"))
        self._dots.setText(f"Pasul {self._i + 1} din {len(_SLIDES)}")
        self._back.setEnabled(self._i > 0)
        is_last = self._i == len(_SLIDES) - 1
        self._next.setText("Gata ✓" if is_last else "Înainte ▶")
        for w in self._soc_widgets:
            w.setVisible(is_last)

    def _prev(self):
        if self._i > 0:
            self._i -= 1; self._show_slide()

    def _nextStep(self):
        if self._i < len(_SLIDES) - 1:
            self._i += 1; self._show_slide()
        else:
            self.accept()
