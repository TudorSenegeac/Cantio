"""
Cantio - About Dialog
Logo header, 4 tabs (Despre, Licență GPL-3.0, Termeni și Condiții, Credite),
GitHub / website / close buttons.
"""
from __future__ import annotations
import os
import webbrowser

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QTabWidget, QWidget,
    QScrollArea, QTextBrowser,
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QPixmap, QFont, QDesktopServices

_HERE = os.path.dirname(os.path.abspath(__file__))

_GPL3 = """\
                    GNU GENERAL PUBLIC LICENSE
                       Version 3, 29 June 2007

 Copyright (C) 2007 Free Software Foundation, Inc.
 <https://fsf.org/>
 Everyone is permitted to copy and distribute verbatim copies
 of this license document, but changing it is not allowed.

                            Preamble

  The GNU General Public License is a free, copyleft license for
software and other kinds of works.

  [... textul complet al GPL-3.0 este inclus în fișierul LICENSE
  distribuit cu codul-sursă al proiectului ...]

  You should have received a copy of the GNU General Public License
  along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

_TERMS = """\
TERMENI ȘI CONDIȚII DE UTILIZARE

1. ACCEPTUL TERMENILOR
   Prin utilizarea Cantio acceptați în totalitate termenii și
   condițiile prezentate în acest document.

2. UTILIZARE PERMISĂ
   Cantio este destinat exclusiv utilizării în context religios,
   eclesial și nonprofit. Orice utilizare comercială este interzisă
   fără acordul scris al autorilor.

3. REDISTRIBUIRE
   Redistribuirea este permisă sub termenii GPL-3.0, cu condiția
   păstrării acestui aviz de drepturi de autor.

4. FĂRĂ GARANȚIE
   Programul este furnizat „ca atare", fără nicio garanție expresă
   sau implicită de funcționare sau adecvare unui scop anume.

5. CONTRIBUȚII
   Contribuțiile la proiect sunt binevenite pe GitHub și sunt supuse
   acelorași termeni GPL-3.0.

6. CONTACT
   tudor.senegeac@gmail.com | https://github.com/TudorSenegeac/Cantio
"""

_CREDITS = """\
CREDITE ȘI MULȚUMIRI

Dezvoltator principal
  Tudor Senegeac — @TudorSenegeac

Biblioteci open-source utilizate
  • PyQt6       — Qt for Python (GPL-3.0 / Commercial)
  • Electron    — Cross-platform desktop apps (MIT)
  • Node.js     — JavaScript runtime (MIT)
  • OpenCV (cv2)— Computer vision library (Apache-2.0)
  • SQLite3     — Embedded database (public domain)
  • requests    — HTTP library (Apache-2.0)

Design inspirat din
  • FreeShow — open-source presentation software
  • ProPresenter, EasyWorship

Mulțumiri speciale
  Comunității Creștine care a testat și susținut proiectul,
  familiei și tuturor celor care au crezut în viziunea Cantio.

„Cântați Domnului o cântare nouă!" — Psalmul 96:1
"""


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Despre Cantio")
        self.setFixedSize(520, 560)
        self.setStyleSheet("""
            QDialog          { background: #11111b; color: #cdd6f4; }
            QLabel           { color: #cdd6f4; background: transparent; }
            QFrame#sep       { background: #313244; }
            QTabWidget::pane { border: none; background: #11111b; }
            QTabBar::tab {
                background: #1e1e2e; color: #6c7086;
                padding: 6px 14px; border: none;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected {
                color: #cba6f7;
                border-bottom: 2px solid #cba6f7;
            }
            QTabBar::tab:hover { color: #cdd6f4; }
            QTextBrowser {
                background: #1e1e2e; color: #cdd6f4;
                border: none; font-family: "Consolas", monospace; font-size: 12px;
            }
            QPushButton {
                background: #313244; color: #cdd6f4;
                border: 1px solid #45475a; border-radius: 6px;
                padding: 6px 20px; font-size: 12px;
            }
            QPushButton:hover { background: #45475a; border-color: #585b70; }
            QPushButton#close_btn {
                background: #a6e3a1; color: #1e1e2e;
                border: none; font-weight: bold;
            }
            QPushButton#close_btn:hover { background: #94e2d5; }
        """)
        self._build_ui()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        vl = QVBoxLayout(self)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        # ── Header ─────────────────────────────────────────────────────────────
        header = QFrame()
        header.setFixedHeight(130)
        header.setStyleSheet("background: #1e1e2e;")
        header_l = QHBoxLayout(header)
        header_l.setContentsMargins(20, 12, 20, 12)
        header_l.setSpacing(16)

        # Logo
        logo_lbl = QLabel()
        logo_lbl.setFixedSize(90, 90)
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        splash = os.path.join(_HERE, "GPSPLASH-cutout.png")
        if os.path.isfile(splash):
            pix = QPixmap(splash).scaled(
                90, 90,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo_lbl.setPixmap(pix)
        else:
            logo_lbl.setText("🎵")
            logo_lbl.setStyleSheet("font-size: 48px;")
        header_l.addWidget(logo_lbl)

        # Title block
        title_v = QVBoxLayout()
        title_v.setSpacing(2)

        name_lbl = QLabel("Cantio")
        name_lbl.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        name_lbl.setStyleSheet("color: #cba6f7;")
        title_v.addWidget(name_lbl)

        ver_lbl = QLabel("Versiunea 1.5.1 Stable")
        ver_lbl.setStyleSheet("color: #6c7086; font-size: 12px;")
        title_v.addWidget(ver_lbl)

        tag_lbl = QLabel("Software prezentare versuri pentru servicii religioase")
        tag_lbl.setStyleSheet("color: #a6adc8; font-size: 11px;")
        title_v.addWidget(tag_lbl)

        title_v.addStretch()
        header_l.addLayout(title_v, 1)

        vl.addWidget(header)

        # ── Separator ─────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setObjectName("sep")
        sep.setFixedHeight(1)
        vl.addWidget(sep)

        # ── Tabs ──────────────────────────────────────────────────────────────
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(self._tab_despre(),  "ℹ Despre")
        tabs.addTab(self._tab_license(), "📄 Licență")
        tabs.addTab(self._tab_terms(),   "📋 Termeni")
        tabs.addTab(self._tab_credits(), "🙏 Credite")
        vl.addWidget(tabs, 1)

        # ── Bottom buttons ─────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(16, 10, 16, 14)
        btn_row.setSpacing(8)

        gh_btn = QPushButton("⭐ GitHub")
        gh_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com/TudorSenegeac/Cantio")))
        btn_row.addWidget(gh_btn)

        web_btn = QPushButton("🌐 cantioapp.com")
        web_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://cantioapp.com")))
        btn_row.addWidget(web_btn)

        btn_row.addStretch()

        close_btn = QPushButton("Închide")
        close_btn.setObjectName("close_btn")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        vl.addLayout(btn_row)

    # ── Tab helpers ────────────────────────────────────────────────────────────

    def _tab_despre(self) -> QWidget:
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(16, 12, 16, 12)
        vl.setSpacing(8)

        tb = QTextBrowser()
        tb.setOpenExternalLinks(True)
        tb.setHtml("""
        <html><body style="font-family: 'Segoe UI', sans-serif;
                           color: #cdd6f4; background: #1e1e2e; font-size: 13px;">
        <p><b style="color:#cba6f7;">Cantio</b> este un software modern de prezentare
        destinat <b>bisericilor, corurilor și congregațiilor creștine</b>.</p>

        <p>Conceput să simplifice afișarea versetelor biblice, imnurilor și prezentărilor
        de serviciu pe ecrane multiple, Cantio combină un editor intuitiv cu un
        motor de randare Electron de înaltă calitate.</p>

        <h4 style="color:#89b4fa;">Funcționalități principale</h4>
        <ul>
          <li>🎵 Biblioteca de cântece cu acorduri și diapozitive auto-split</li>
          <li>📖 Versete biblice (multiple traduceri) cu randare live</li>
          <li>🎨 Editor de teme cu gradient, imagine, cameră și gradient animat</li>
          <li>📺 Suport multi-display cu tranziții și ticker</li>
          <li>🎭 Sistem de overlay-uri (logo, ceas, numărătoare, ticker avansat)</li>
          <li>📊 Import PowerPoint, imagini, video</li>
          <li>☁ Backup cloud și gestionare profile</li>
        </ul>

        <p style="color:#6c7086; font-size: 11px;">
        © 2024-2026 Senegeac Tudor · Licențiat sub GPL-3.0<br>
        <a href="https://github.com/TudorSenegeac/Cantio"
           style="color:#89b4fa;">github.com/TudorSenegeac/Cantio</a>
        </p>
        </body></html>
        """)
        vl.addWidget(tb)
        return w

    def _tab_license(self) -> QWidget:
        return self._text_tab(_GPL3)

    def _tab_terms(self) -> QWidget:
        return self._text_tab(_TERMS)

    def _tab_credits(self) -> QWidget:
        return self._text_tab(_CREDITS)

    @staticmethod
    def _text_tab(text: str) -> QWidget:
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        tb = QTextBrowser()
        tb.setPlainText(text)
        vl.addWidget(tb)
        return w
