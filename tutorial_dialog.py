"""
Cantio - Tutorial
Provides two modes:
  • TutorialDialog   — legacy modal dialog (used for "Tutorial" menu item fallback)
  • InteractiveTutorial — overlay-based interactive tour on the main window
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QCheckBox, QFrame, QWidget, QApplication,
)
from PyQt6.QtCore import Qt, QObject, QTimer, QPoint, QRect, pyqtSignal
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPen, QFontMetrics,
)


# ══════════════════════════════════════════════════════════════════════════════
# Legacy TutorialDialog (kept for backward compatibility)
# ══════════════════════════════════════════════════════════════════════════════

_STEPS = [
    {
        "icon":  "👋",
        "title": "Bun venit în Cantio!",
        "text": (
            "Cantio este un software profesional de afișare versuri\n"
            "pentru servicii religioase și prezentări.\n\n"
            "Acest tutorial îți va arăta funcțiile principale\n"
            "în câțiva pași simpli."
        ),
    },
    {
        "icon":  "📚",
        "title": "Biblioteca de Cântări",
        "text": (
            "• <b>Click simplu</b> pe o cântare = selectează și previzualizează\n"
            "• <b>Dublu-click</b> = încarcă în editorul central\n"
            "• Butonul <b>Import</b> (meniu Fișier) — importă .txt, .pptx, .docx\n"
            "• Caută cu sau fără diacritice — funcționează ambele\n"
            "• Filtrează pe categorie din meniu drop-down"
        ),
    },
    {
        "icon":  "📋",
        "title": "Serviciul",
        "text": (
            "• Adaugă cântări din bibliotecă cu butonul <b>+ Serviciu</b>\n"
            "• Reordonează trăgând elementele (drag & drop)\n"
            "• Trage direct din bibliotecă în serviciu\n"
            "• Salvează serviciul ca fișier <b>.gps</b> (Ctrl+S)\n"
            "• Deschide servicii salvate cu Ctrl+O"
        ),
    },
    {
        "icon":  "📺",
        "title": "Fereastra Live",
        "text": (
            "• Butonul <b>📺 Display</b> — pornește/oprește proiectorul\n"
            "• Butonul <b>▶ GO LIVE</b> — trimite slide-ul curent\n"
            "• Click pe thumbnail = trimite direct acel slide\n"
            "• <b>◀ ▶</b> — navighează între slide-uri\n"
            "• <b>Space</b> = GO LIVE  •  <b>Escape</b> = Ecran negru\n"
            "• <b>Ctrl+P</b> = deschide/închide display"
        ),
    },
    {
        "icon":  "⚙",
        "title": "Setări Display",
        "text": (
            "• <b>Font</b>, culoare text, fundal solid sau imagine\n"
            "• <b>Tranziții</b>: fade, crossfade, slide, zoom\n"
            "• <b>Overlay-uri</b>: ceas live, timer countdown, ticker\n"
            "• <b>Copyright</b> / watermark cu titlul sau autorul cântării\n"
            "• Deschide Settings din meniu ⚙ sau butonul din toolbar"
        ),
    },
    {
        "icon":  "🎨",
        "title": "Teme & Looks",
        "text": (
            "• Tab <b>🎨 Teme</b> — creează teme (culori, fundal, efecte text:\n"
            "  ecou, cascadă, gradient, glow, haotic)\n"
            "• Setează o temă implicită sau <b>pe categorie</b>\n"
            "• <b>🎨 Look</b> (toolbar) — schimbă tema activă <b>live, cu un click</b>\n"
            "  pe tot ce e afișat (cântări + Biblie)"
        ),
    },
    {
        "icon":  "🖼",
        "title": "Fundaluri & Editor avansat",
        "text": (
            "• Tab <b>🖼 Media</b> ▸ <b>Fundal</b> — fundaluri animate (gradient,\n"
            "  particule, forme, imagini, video, ceas)\n"
            "• Butonul <b>Editor avansat</b> pe o cântare — design multi-slide\n"
            "  (text real editabil, fundal per slide, tranziții de concert)\n"
            "• Butonul <b>🎨 Fundal</b> din editor — alege un fundal salvat"
        ),
    },
    {
        "icon":  "🎚",
        "title": "Mixer, Layere & Macros",
        "text": (
            "• Tab <b>🧱 Layere</b> — aprinde/stinge <b>independent</b> fundalul,\n"
            "  textul, logo-ul, Black (fundalul rămâne când stingi textul)\n"
            "• Tab <b>🎚 Mixer</b> — manete manuale, tranziție fundal, <b>Audio Bin</b>,\n"
            "  <b>MIDI</b> (mapează un controller la acțiuni)\n"
            "• Tab <b>⚙ Macros</b> — un click = mai multe acțiuni în ordine"
        ),
    },
    {
        "icon":  "⚡",
        "title": "Prezentări dinamice (BETA)",
        "text": (
            "• Butonul <b>⚡ Dinamic</b> (toolbar) — dintr-un MP3 + versuri\n"
            "  generează o prezentare cu <b>fundal reactiv la muzică</b>\n"
            "• Versurile apar cuvânt-cu-cuvânt, slide-urile se schimbă automat\n"
            "• ⚠ <b>Funcție BETA</b> — verifică rezultatul înainte de serviciu\n"
            "• Se salvează în Cântări cu semn ⚡ și e editabilă"
        ),
    },
    {
        "icon":  "📖",
        "title": "Biblie & Telecomandă",
        "text": (
            "• Tab <b>Biblie</b> — caută rapid: <b>„ps23 3\"</b>, <b>„Ioan 3:16\"</b>\n"
            "• Layout referință: sus/jos, verset care nu acoperă referința\n"
            "• <b>Aranjamente</b> — reordonează strofele (Refren/Strofă) live\n"
            "• <b>Remote</b> — scanează QR-ul și controlezi de pe telefon"
        ),
    },
    {
        "icon":  "✅",
        "title": "Ești gata!",
        "text": (
            "Cantio este acum configurat și gata de utilizare.\n\n"
            "📖 Ajutor online:\n"
            "<a style='color:#5294e2;' href='https://cantioapp.com/helpdesk'>"
            "cantioapp.com/helpdesk</a>\n\n"
            "Creat cu ❤ de <b>Senegeac Tudor</b>"
        ),
    },
]


class TutorialDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tutorial Cantio")
        self.setFixedSize(640, 480)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog { background: #11111b; color: #cdd6f4; }
            QLabel  { background: transparent; color: #cdd6f4; }
            QPushButton {
                background: #313244; color: #cdd6f4;
                border: 1px solid #45475a; border-radius: 6px;
                padding: 8px 22px; font-size: 12px;
            }
            QPushButton:hover { background: #45475a; }
            QPushButton#next_btn {
                background: #5294e2; color: #fff; border: none; font-weight: 700;
            }
            QPushButton#next_btn:hover { background: #6ba5f0; }
            QPushButton#done_btn {
                background: #a6e3a1; color: #1e1e2e; border: none; font-weight: 700;
            }
            QPushButton#done_btn:hover { background: #b9efb4; }
            QCheckBox { color: #585b70; font-size: 11px; }
            QCheckBox::indicator {
                width: 14px; height: 14px; border: 1px solid #45475a;
                border-radius: 3px; background: #1e1e2e;
            }
            QCheckBox::indicator:checked { background: #5294e2; border-color: #5294e2; }
        """)

        self._step = 0
        self._total = len(_STEPS)

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 24)
        root.setSpacing(16)

        dots_row = QHBoxLayout()
        dots_row.setSpacing(8)
        dots_row.addStretch()
        self._dot_labels: list[QLabel] = []
        for i in range(self._total):
            dot = QLabel("●")
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._dot_labels.append(dot)
            dots_row.addWidget(dot)
        dots_row.addStretch()
        root.addLayout(dots_row)

        self._icon_lbl = QLabel()
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_lbl.setFont(QFont("Segoe UI Emoji", 48))
        root.addWidget(self._icon_lbl)

        self._title_lbl = QLabel()
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_lbl.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self._title_lbl.setStyleSheet("color:#cba6f7; background:transparent;")
        root.addWidget(self._title_lbl)

        self._body_lbl = QLabel()
        self._body_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._body_lbl.setWordWrap(True)
        self._body_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._body_lbl.setOpenExternalLinks(True)
        self._body_lbl.setStyleSheet(
            "color:#cdd6f4; font-size:13px; line-height:1.6; background:transparent;"
        )
        root.addWidget(self._body_lbl, 1)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#313244;")
        root.addWidget(sep)

        bottom = QHBoxLayout()
        bottom.setSpacing(10)
        self._skip_chk = QCheckBox("Nu mai arăta la pornire")
        bottom.addWidget(self._skip_chk)
        bottom.addStretch()
        self._back_btn = QPushButton("◀ Înapoi")
        self._back_btn.clicked.connect(self._go_back)
        bottom.addWidget(self._back_btn)
        self._next_btn = QPushButton("Înainte ▶")
        self._next_btn.setObjectName("next_btn")
        self._next_btn.clicked.connect(self._go_next)
        bottom.addWidget(self._next_btn)
        root.addLayout(bottom)

        self._update_step()

    def _go_back(self):
        if self._step > 0:
            self._step -= 1
            self._update_step()

    def _go_next(self):
        if self._step < self._total - 1:
            self._step += 1
            self._update_step()
        else:
            self._finish()

    def _finish(self):
        if self._skip_chk.isChecked():
            self._save_shown()
        self.accept()

    def _save_shown(self):
        try:
            import database as db
            cache = db.get_cache()
            cache["tutorial_shown"] = True
            db.save_cache(cache)
        except Exception as e:
            print(f"[TUTORIAL] Could not save tutorial_shown: {e}")

    def _update_step(self):
        step = _STEPS[self._step]
        self._icon_lbl.setText(step["icon"])
        self._title_lbl.setText(step["title"])
        body = step["text"].replace("\n", "<br>").replace("•", "&#8226;")
        self._body_lbl.setText(body)
        for i, dot in enumerate(self._dot_labels):
            if i < self._step:
                dot.setStyleSheet("color:#45475a; font-size:10px;")
            elif i == self._step:
                dot.setStyleSheet("color:#cba6f7; font-size:14px;")
            else:
                dot.setStyleSheet("color:#313244; font-size:10px;")
        self._back_btn.setEnabled(self._step > 0)
        is_last = (self._step == self._total - 1)
        if is_last:
            self._next_btn.setText("✅ Începe!")
            self._next_btn.setObjectName("done_btn")
        else:
            self._next_btn.setText("Înainte ▶")
            self._next_btn.setObjectName("next_btn")
        self._next_btn.style().unpolish(self._next_btn)
        self._next_btn.style().polish(self._next_btn)


# ══════════════════════════════════════════════════════════════════════════════
# Interactive Tutorial — overlay on the main window
# ══════════════════════════════════════════════════════════════════════════════

class TutorialStep:
    def __init__(self, title, description,
                 target_widget=None, target_attr=None,
                 action=None,
                 tooltip_pos="bottom", highlight_color="#cba6f7"):
        self.title = title
        self.description = description
        self.target_widget = target_widget   # direct QWidget reference (optional)
        self.target_attr   = target_attr     # attribute name on main window (optional)
        self.action        = action          # side-effect to run when step is shown
        self.tooltip_pos   = tooltip_pos
        self.highlight_color = highlight_color


class TutorialOverlay(QWidget):
    """Semi-transparent overlay that highlights a widget and shows a tooltip."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setGeometry(parent.rect())
        self._highlight_rect: QRect | None = None
        self._highlight_color = "#cba6f7"
        self._tooltip_lines: list[str] = []
        self._tooltip_pos = "bottom"

    # ── API ───────────────────────────────────────────────────────────────────

    def set_highlight(self, widget: QWidget | None, color="#cba6f7",
                      tooltip="", tooltip_pos="bottom"):
        if widget:
            try:
                pos = widget.mapTo(self.parent(), QPoint(0, 0))
                self._highlight_rect = QRect(
                    pos.x() - 4, pos.y() - 4,
                    widget.width() + 8, widget.height() + 8,
                )
            except Exception:
                self._highlight_rect = None
        else:
            self._highlight_rect = None
        self._highlight_color = color
        self._tooltip_pos = tooltip_pos
        self._tooltip_lines = self._wrap_text(tooltip, 300)
        self.update()

    def _wrap_text(self, text: str, max_px: int) -> list[str]:
        font = QFont("Segoe UI", 11)
        fm = QFontMetrics(font)
        lines: list[str] = []
        for paragraph in text.split("\n"):
            words = paragraph.split()
            current = ""
            for word in words:
                test = (current + " " + word).strip()
                if fm.horizontalAdvance(test) > max_px and current:
                    lines.append(current)
                    current = word
                else:
                    current = test
            if current:
                lines.append(current)
            if not words:
                lines.append("")
        return lines

    # ── Painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        r = self._highlight_rect

        if r:
            p.setBrush(QColor(0, 0, 0, 150))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(0, 0, w, r.top())
            p.drawRect(0, r.bottom(), w, h - r.bottom())
            p.drawRect(0, r.top(), r.left(), r.height())
            p.drawRect(r.right(), r.top(), w - r.right(), r.height())

            pen = QPen(QColor(self._highlight_color), 3)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r, 8, 8)

            p.setOpacity(0.3)
            glow = QPen(QColor(self._highlight_color), 7)
            p.setPen(glow)
            p.drawRoundedRect(r.adjusted(-5, -5, 5, 5), 11, 11)
            p.setOpacity(1.0)
        else:
            p.setBrush(QColor(0, 0, 0, 80))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(0, 0, w, h)

        if self._tooltip_lines and r:
            self._draw_tooltip(p, r, w, h)

        p.end()

    def _draw_tooltip(self, p, target: QRect, w, h):
        lines = self._tooltip_lines
        if not lines:
            return

        font = QFont("Segoe UI", 11)
        p.setFont(font)
        fm = p.fontMetrics()
        padding = 14
        line_h = fm.height() + 4

        box_w = min(max((fm.horizontalAdvance(l) for l in lines), default=80) + padding * 2, 340)
        box_h = len(lines) * line_h + padding * 2

        pos = self._tooltip_pos
        cx = target.center().x()
        cy = target.center().y()
        gap = 16

        if pos == "bottom":
            bx, by = cx - box_w // 2, target.bottom() + gap
        elif pos == "top":
            bx, by = cx - box_w // 2, target.top() - box_h - gap
        elif pos == "right":
            bx, by = target.right() + gap, cy - box_h // 2
        else:
            bx, by = target.left() - box_w - gap, cy - box_h // 2

        bx = max(8, min(bx, w - box_w - 8))
        by = max(8, min(by, h - box_h - 8))
        box = QRect(bx, by, box_w, box_h)

        p.setBrush(QColor(0, 0, 0, 70))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(box.adjusted(3, 3, 3, 3), 10, 10)

        p.setBrush(QColor("#1e1e2e"))
        pen = QPen(QColor(self._highlight_color), 2)
        p.setPen(pen)
        p.drawRoundedRect(box, 10, 10)

        p.setPen(QColor("#cdd6f4"))
        for i, line in enumerate(lines):
            p.drawText(bx + padding, by + padding + i * line_h + fm.ascent(), line)


# ── Draggable nav panel ───────────────────────────────────────────────────────

class DraggableNavWidget(QWidget):
    """Tutorial navigation panel that can be dragged by the user."""

    def __init__(self, parent):
        super().__init__(parent)
        self._drag_pos: QPoint | None = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            # Clamp to parent bounds
            par = self.parent()
            if par:
                new_pos.setX(max(0, min(new_pos.x(), par.width() - self.width())))
                new_pos.setY(max(0, min(new_pos.y(), par.height() - self.height())))
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()


# ── Main interactive tutorial ─────────────────────────────────────────────────

class InteractiveTutorial(QObject):
    """Interactive step-by-step tour that overlays the main window."""

    finished = pyqtSignal()

    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window
        self.overlay = TutorialOverlay(main_window)
        self.overlay.hide()
        self._step = 0
        self._nav_widget: DraggableNavWidget | None = None
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(900)
        self._pulse_timer.timeout.connect(lambda: self.overlay.update())
        self._demo_dialog = None   # any non-modal demo dialog open during tutorial
        self._type_timer: QTimer | None = None
        self._steps = self._build_steps()

    # ── Steps ─────────────────────────────────────────────────────────────────

    def _build_steps(self):
        return [

            # PAS 0 — Bun venit
            TutorialStep(
                "👋 Bun venit în Cantio!",
                "Acesta este un tur interactiv care\n"
                "îți arată cum să folosești aplicația\n"
                "pas cu pas.\n\n"
                "💡 Poți trage acest panou oriunde\n"
                "   pe ecran dacă acoperă ceva.\n\n"
                "Apasă Înainte pentru a începe! 🚀",
                target_widget=None,
            ),

            # PAS 1 — Biblioteca
            TutorialStep(
                "📚 Biblioteca de cântări",
                "Aici sunt toate cântările tale\n"
                "organizate pe categorii.\n\n"
                "✔ Click simplu = selectează cântarea\n"
                "✔ Dublu-click = editează cântarea\n"
                "✔ Click dreapta = opțiuni extra\n"
                "✔ Caută după titlu sau versuri",
                target_attr="song_list",
                tooltip_pos="right",
            ),

            # PAS 2 — Căutare
            TutorialStep(
                "🔍 Caută cântări rapid",
                "Tastează orice în bara de căutare.\n\n"
                "✔ Funcționează cu sau fără diacritice\n"
                "   Ex: 'stergarul' → 'Ștergarul'\n"
                "✔ Caută după titlu SAU versuri\n"
                "✔ Rezultatele apar instant",
                target_attr="search_edit",
                tooltip_pos="right",
                action="demo_search",
            ),

            # PAS 3 — Adaugă cântare nouă (DEMO LIVE)
            TutorialStep(
                "➕ Demo: Adaugă o cântare nouă",
                "Urmărește cum se adaugă o cântare!\n\n"
                "Se deschide fereastra de adăugare\n"
                "și se completează automat un exemplu.\n\n"
                "✔ Titlul cântării\n"
                "✔ Versurile separate prin linie goală\n"
                "   → fiecare bloc = un slide separat\n\n"
                "Apasă Cancel în fereastra demo\n"
                "sau Înainte pentru a continua.",
                target_widget=None,
                tooltip_pos="bottom",
                action="demo_add_song",
            ),

            # PAS 4 — Editor versuri
            TutorialStep(
                "✏ Editorul de versuri",
                "Editorul este zona principală de lucru.\n\n"
                "✔ Scrie sau lipește versurile aici\n"
                "✔ Separă strofele cu o linie goală\n"
                "   → fiecare strofă = un slide\n\n"
                "✔ Formatare text:\n"
                "   B = Bold  |  I = Italic\n"
                "   U = Subliniat  |  A = Culoare\n\n"
                "💡 Textul continuu de pe internet\n"
                "   se împarte automat în strofe!",
                target_attr="editor",
                tooltip_pos="top",
                action="demo_editor",
            ),

            # PAS 5 — Slide-uri
            TutorialStep(
                "🖼 Slide-urile cântării",
                "Fiecare strofă devine un slide.\n\n"
                "✔ Click pe slide = selectează\n"
                "✔ Click = trimite LIVE\n"
                "   (dacă fereastra e deschisă)\n\n"
                "✔ Schimbă grila: XS / S / M / L / XL\n"
                "✔ Comută Grid ↔ Listă\n\n"
                "⌨ Săgeți tastatură = slide anterior/următor",
                target_attr="slides_container",
                tooltip_pos="top",
            ),

            # PAS 6 — Serviciu
            TutorialStep(
                "📋 Serviciul de azi",
                "Serviciul este lista cântărilor\n"
                "pentru serviciul de azi.\n\n"
                "Cum adaugi cântări în serviciu:\n"
                "✔ Trage cu mouse-ul din bibliotecă\n"
                "✔ SAU selectează + apasă '+ Adaugă'\n"
                "✔ SAU click dreapta → 'Adaugă în serviciu'\n\n"
                "✔ Reordonează cu ▲ ▼\n"
                "✔ Salvează cu Ctrl+S ca fișier .gps",
                target_attr="_service_list",
                tooltip_pos="right",
                action="demo_service",
            ),

            # PAS 7 — Deschide display
            TutorialStep(
                "📺 Deschide fereastra live",
                "Acum deschidem fereastra pe proiector!\n\n"
                "✔ Apasă butonul 'Display' din\n"
                "   colțul dreapta sus al toolbar-ului\n"
                "✔ SAU apasă Ctrl+P\n\n"
                "Fereastra se deschide fullscreen pe\n"
                "monitorul selectat în Setări → Display.\n\n"
                "💡 Dacă ai un singur monitor,\n"
                "   o poți muta pe proiector manual.",
                target_attr="_display_btn",
                tooltip_pos="bottom",
                action="highlight_display",
            ),

            # PAS 8 — GO LIVE
            TutorialStep(
                "▶ Trimite pe proiector!",
                "Acum poți trimite versurile live!\n\n"
                "Metode de trimitere:\n"
                "✔ Click pe thumbnail = trimite direct\n"
                "✔ Buton GO LIVE = trimite slide curent\n"
                "✔ Space = GO LIVE rapid\n\n"
                "Navigare slide-uri:\n"
                "✔ Săgeată Dreapta/Jos = următor\n"
                "✔ Săgeată Stânga/Sus = anterior\n"
                "✔ Escape = Ecran negru\n\n"
                "💡 Preview-ul arată EXACT ce vede publicul!",
                target_attr="go_live_btn",
                tooltip_pos="left",
                action="highlight_go_live",
            ),

            # PAS 9 — Preview
            TutorialStep(
                "👁 Preview Output",
                "Previzualizarea din dreapta sus\n"
                "este identică cu ce apare pe proiector.\n\n"
                "✔ Se actualizează în timp real\n"
                "✔ Arată fontul, culorile și fundalul\n"
                "   exact cum le-ai setat\n"
                "✔ Bordura verde = output activ\n\n"
                "💡 Verifică mereu preview-ul\n"
                "   înainte să trimiți live!",
                target_attr="preview",
                tooltip_pos="left",
            ),

            # PAS 10 — Setări
            TutorialStep(
                "⚙ Personalizează aspectul",
                "Din Setări poți personaliza totul:\n\n"
                "✔ Font, mărime, culoare text\n"
                "✔ Fundal: culoare, imagine sau video\n"
                "✔ Tranziții: Instant, Fade, Crossfade,\n"
                "   Slide, Zoom\n"
                "✔ Overlay-uri: Ceas, Timer, Ticker\n"
                "✔ Copyright cu titlul/autorul cântării\n"
                "✔ Limbă interfață (RO/EN/DE/FR/HU)\n\n"
                "💡 Modificările se aplică instant!",
                target_widget=None,
                tooltip_pos="bottom",
                action="highlight_settings",
            ),

            # PAS 11 — Scurtături
            TutorialStep(
                "⌨ Scurtături esențiale",
                "Cele mai importante scurtături:\n\n"
                "Space ............ GO LIVE\n"
                "Escape ........... Ecran negru\n"
                "→ / ↓ ........... Slide următor\n"
                "← / ↑ ........... Slide anterior\n"
                "Ctrl+P ........... Display ON/OFF\n"
                "Ctrl+S ........... Salvează serviciu\n"
                "Ctrl+O ........... Deschide serviciu\n"
                "Ctrl+F ........... Caută cântări\n"
                "Ctrl+I ........... Import\n\n"
                "💡 Vezi toate scurtăturile în\n"
                "   Ajutor → Scurtături Tastatură",
                target_widget=None,
            ),

            # PAS 12 — Final
            TutorialStep(
                "✅ Ești gata să folosești Cantio!",
                "Ai parcurs tot tutorialul! 🎉\n\n"
                "Resurse utile:\n"
                "✔ Ajutor online:\n"
                "   cantioapp.com/helpdesk\n"
                "✔ Tutorial din nou:\n"
                "   Ajutor → Tutorial\n"
                "✔ Scurtături:\n"
                "   Ajutor → Scurtături Tastatură\n\n"
                "Mult succes la servicii! 🙏\n\n"
                "— Creat cu ❤ de Senegeac Tudor",
                target_widget=None,
            ),
        ]

    # ── Control ───────────────────────────────────────────────────────────────

    def start(self):
        self.overlay.show()
        self.overlay.raise_()
        self.overlay.resize(self.mw.size())
        self._step = 0
        self._create_nav()
        self._show_step(0)
        self._pulse_timer.start()

    def stop(self):
        self._pulse_timer.stop()
        self.overlay.hide()
        if self._nav_widget:
            self._nav_widget.hide()
            self._nav_widget.deleteLater()
            self._nav_widget = None
        self._close_demo_dialog()
        try:
            import database as db
            cache = db.get_cache()
            cache["tutorial_shown"] = True
            db.save_cache(cache)
        except Exception:
            pass
        self.finished.emit()

    def _close_demo_dialog(self):
        if self._demo_dialog is not None:
            try:
                self._demo_dialog.reject()
            except Exception:
                pass
            self._demo_dialog = None
        if self._type_timer is not None:
            self._type_timer.stop()
            self._type_timer = None

    # ── Navigation widget ─────────────────────────────────────────────────────

    def _create_nav(self):
        self._nav_widget = DraggableNavWidget(self.mw)
        self._nav_widget.setStyleSheet("""
            QWidget {
                background: #1e1e2e;
                border: 1px solid #45475a;
                border-radius: 12px;
            }
            QLabel { background: transparent; border: none; }
        """)
        self._nav_widget.setFixedWidth(380)
        # Cursor hint so user knows it's draggable
        self._nav_widget.setCursor(Qt.CursorShape.SizeAllCursor)

        layout = QVBoxLayout(self._nav_widget)
        layout.setContentsMargins(20, 12, 20, 16)
        layout.setSpacing(10)

        # Drag handle hint
        handle_lbl = QLabel("⠿ — Trage pentru a muta panoul")
        handle_lbl.setStyleSheet(
            "font-size:10px; color:#585b70; background:transparent; border:none;"
        )
        handle_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(handle_lbl)

        # Progress dots
        dots_row = QHBoxLayout()
        dots_row.addStretch()
        self._dots: list[QLabel] = []
        for i in range(len(self._steps)):
            dot = QLabel("●")
            dot.setStyleSheet("color:#45475a; font-size:9px; background:transparent; border:none;")
            self._dots.append(dot)
            dots_row.addWidget(dot)
        dots_row.addStretch()
        layout.addLayout(dots_row)

        self._nav_title = QLabel()
        self._nav_title.setStyleSheet(
            "font-size:15px; font-weight:bold; color:#cba6f7; background:transparent; border:none;"
        )
        self._nav_title.setWordWrap(True)
        layout.addWidget(self._nav_title)

        self._nav_desc = QLabel()
        self._nav_desc.setStyleSheet(
            "font-size:12px; color:#cdd6f4; background:transparent; border:none;"
        )
        self._nav_desc.setWordWrap(True)
        self._nav_desc.setMinimumHeight(80)
        layout.addWidget(self._nav_desc)

        # Step counter
        self._step_counter = QLabel()
        self._step_counter.setStyleSheet(
            "font-size:10px; color:#585b70; background:transparent; border:none;"
        )
        self._step_counter.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._step_counter)

        btn_row = QHBoxLayout()

        self._skip_btn = QPushButton("✕ Închide")
        self._skip_btn.setStyleSheet("""
            QPushButton { background:transparent; color:#6c7086; border:none;
                          padding:6px; font-size:11px; }
            QPushButton:hover { color:#f38ba8; }
        """)
        self._skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._skip_btn.clicked.connect(self.stop)

        self._back_btn = QPushButton("◀")
        self._back_btn.setFixedWidth(40)
        self._back_btn.setStyleSheet("""
            QPushButton { background:#313244; color:#cdd6f4; border:1px solid #45475a;
                          border-radius:6px; padding:6px; }
            QPushButton:hover { background:#45475a; }
        """)
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.clicked.connect(self._prev_step)

        self._next_btn = QPushButton("Înainte ▶")
        self._next_btn.setStyleSheet("""
            QPushButton { background:#a6e3a1; color:#1e1e2e; border:none;
                          border-radius:6px; padding:6px 16px; font-weight:bold; }
            QPushButton:hover { background:#94e2a0; }
        """)
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_btn.clicked.connect(self._next_step)

        btn_row.addWidget(self._skip_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._back_btn)
        btn_row.addWidget(self._next_btn)
        layout.addLayout(btn_row)

        self._nav_widget.show()
        self._position_nav()

    def _position_nav(self, avoid_rect: QRect | None = None):
        """Place nav in bottom-right, or move away from a conflicting highlighted rect."""
        if not self._nav_widget:
            return
        self._nav_widget.adjustSize()
        mw_w = self.mw.width()
        mw_h = self.mw.height()
        nw = self._nav_widget.width()
        nh = self._nav_widget.height()

        # Default: bottom-right
        x = mw_w - nw - 20
        y = mw_h - nh - 20

        if avoid_rect:
            nav_rect = QRect(x, y, nw, nh)
            if nav_rect.intersects(avoid_rect.adjusted(-20, -20, 20, 20)):
                # Try bottom-left
                x2, y2 = 20, mw_h - nh - 20
                nav_rect2 = QRect(x2, y2, nw, nh)
                if not nav_rect2.intersects(avoid_rect.adjusted(-20, -20, 20, 20)):
                    x, y = x2, y2
                else:
                    # Try top-right
                    x3, y3 = mw_w - nw - 20, 20
                    nav_rect3 = QRect(x3, y3, nw, nh)
                    if not nav_rect3.intersects(avoid_rect.adjusted(-20, -20, 20, 20)):
                        x, y = x3, y3

        self._nav_widget.move(x, y)
        self._nav_widget.raise_()

    def _show_step(self, idx: int):
        step = self._steps[idx]

        for i, dot in enumerate(self._dots):
            color = "#cba6f7" if i == idx else ("#45475a" if i > idx else "#585b70")
            size = "11px" if i == idx else "9px"
            dot.setStyleSheet(
                f"color:{color}; font-size:{size}; background:transparent; border:none;"
            )

        self._nav_title.setText(step.title)
        self._nav_desc.setText(step.description)
        self._step_counter.setText(f"Pas {idx + 1} din {len(self._steps)}")

        self._back_btn.setEnabled(idx > 0)
        is_last = idx == len(self._steps) - 1
        self._next_btn.setText("✅ Închide!" if is_last else "Înainte ▶")

        target = step.target_widget
        if target is None and step.target_attr:
            target = getattr(self.mw, step.target_attr, None)

        self.overlay.set_highlight(
            target,
            step.highlight_color,
            step.description,
            step.tooltip_pos,
        )

        # Compute highlighted rect to avoid with nav panel
        avoid = None
        if target:
            try:
                pos = target.mapTo(self.mw, QPoint(0, 0))
                avoid = QRect(pos.x(), pos.y(), target.width(), target.height())
            except Exception:
                pass
        self._position_nav(avoid_rect=avoid)

        if step.action:
            QTimer.singleShot(
                400,
                lambda a=step.action: self._execute_action(a),
            )

    def _next_step(self):
        self._close_demo_dialog()
        if self._step >= len(self._steps) - 1:
            self.stop()
            return
        self._step += 1
        self._show_step(self._step)

    def _prev_step(self):
        self._close_demo_dialog()
        if self._step > 0:
            self._step -= 1
            self._show_step(self._step)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _execute_action(self, action: str):
        mw = self.mw
        if not action:
            return

        if action == "demo_search":
            if hasattr(mw, "search_edit"):
                mw.search_edit.setFocus()
                mw.search_edit.selectAll()

        elif action == "demo_add_song":
            self._run_add_song_demo()

        elif action == "demo_editor":
            if hasattr(mw, "editor"):
                mw.editor.setFocus()

        elif action == "demo_service":
            if hasattr(mw, "_service_list"):
                self._flash_widget(mw._service_list)

        elif action == "highlight_display":
            if hasattr(mw, "_display_btn"):
                self._flash_widget(mw._display_btn)

        elif action == "highlight_go_live":
            if hasattr(mw, "go_live_btn"):
                self._flash_widget(mw.go_live_btn)

        elif action == "highlight_settings":
            for attr in ("_settings_btn", "settings_btn", "_settings_action"):
                w = getattr(mw, attr, None)
                if w and hasattr(w, "setStyleSheet"):
                    self._flash_widget(w)
                    break

    # ── Demo: add song ────────────────────────────────────────────────────────

    def _run_add_song_demo(self):
        """Open SongEditorDialog non-modally and auto-type a demo song."""
        try:
            from control_window import SongEditorDialog
        except ImportError:
            return

        self._close_demo_dialog()

        dlg = SongEditorDialog(self.mw)
        dlg.setWindowModality(Qt.WindowModality.NonModal)
        dlg.setWindowTitle("➕ Demo — Cântare Nouă")
        dlg.show()

        # Position dialog in view (center of main window)
        mw_geo = self.mw.geometry()
        dlg.move(
            mw_geo.x() + (mw_geo.width() - dlg.width()) // 2,
            mw_geo.y() + (mw_geo.height() - dlg.height()) // 2,
        )

        self._demo_dialog = dlg
        self._demo_typing_chars: list[tuple[str, str]] = []
        # Build sequence: (field, text)
        title_text = "Harul Tău — Demo Tutorial"
        lyrics_text = (
            "Harul Tău e mai mare\n"
            "Decât orice greșeală\n"
            "Iubirea Ta mă ține\n"
            "Și mă face întreg\n"
            "\n"
            "Refren:\n"
            "Doamne, îți mulțumesc\n"
            "Pentru harul Tău cel mare\n"
            "Care schimbă inima\n"
            "Și aduce libertate"
        )
        self._demo_title_text = title_text
        self._demo_lyrics_text = lyrics_text
        self._demo_phase = "title"
        self._demo_char_idx = 0

        dlg.title_edit.clear()
        dlg.content_edit.clear()
        dlg.title_edit.setFocus()

        self._type_timer = QTimer(self)
        self._type_timer.setInterval(45)
        self._type_timer.timeout.connect(self._demo_type_next_char)
        self._type_timer.start()

    def _demo_type_next_char(self):
        dlg = self._demo_dialog
        if dlg is None or not dlg.isVisible():
            if self._type_timer:
                self._type_timer.stop()
            return

        if self._demo_phase == "title":
            text = self._demo_title_text
            if self._demo_char_idx < len(text):
                dlg.title_edit.setText(text[: self._demo_char_idx + 1])
                self._demo_char_idx += 1
            else:
                # Switch to lyrics after a short pause
                self._demo_phase = "pause"
                self._demo_char_idx = 0
                if self._type_timer:
                    self._type_timer.setInterval(600)

        elif self._demo_phase == "pause":
            dlg.content_edit.setFocus()
            self._demo_phase = "lyrics"
            self._demo_char_idx = 0
            if self._type_timer:
                self._type_timer.setInterval(30)

        elif self._demo_phase == "lyrics":
            text = self._demo_lyrics_text
            if self._demo_char_idx < len(text):
                dlg.content_edit.setPlainText(text[: self._demo_char_idx + 1])
                # Keep cursor at end
                cursor = dlg.content_edit.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                dlg.content_edit.setTextCursor(cursor)
                self._demo_char_idx += 1
            else:
                # Done typing — stop timer
                if self._type_timer:
                    self._type_timer.stop()
                    self._type_timer = None

    # ── Flash animation ───────────────────────────────────────────────────────

    def _flash_widget(self, widget, times: int = 4):
        if not widget:
            return
        if hasattr(self, "_flash_timer") and self._flash_timer.isActive():
            self._flash_timer.stop()
            try:
                old_w = getattr(self, "_flash_widget_ref", None)
                if old_w:
                    old_w.setStyleSheet(getattr(self, "_flash_original", ""))
            except Exception:
                pass

        self._flash_original = widget.styleSheet()
        self._flash_style = self._flash_original + \
            " border: 2px solid #cba6f7 !important;"
        self._flash_widget_ref = widget
        self._flash_count = 0
        self._flash_times = times * 2

        self._flash_timer = QTimer(self)
        self._flash_timer.setInterval(200)
        self._flash_timer.timeout.connect(self._do_flash)
        self._flash_timer.start()

    def _do_flash(self):
        w = getattr(self, "_flash_widget_ref", None)
        if not w:
            self._flash_timer.stop()
            return
        try:
            if self._flash_count % 2 == 0:
                w.setStyleSheet(self._flash_style)
            else:
                w.setStyleSheet(self._flash_original)
            self._flash_count += 1
            if self._flash_count >= self._flash_times:
                self._flash_timer.stop()
                w.setStyleSheet(self._flash_original)
        except Exception:
            self._flash_timer.stop()
