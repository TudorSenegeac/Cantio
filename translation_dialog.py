"""
Cantio - Translation Dialog
Translate song lyrics using deep-translator (GoogleTranslator, free, no API key).
Saves translations per-language in the songs DB.
"""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTextEdit, QProgressBar, QSplitter, QWidget,
    QDialogButtonBox, QMessageBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont


_LANGUAGES = [
    ("ro", "Română"),
    ("en", "English"),
    ("de", "Deutsch"),
    ("fr", "Français"),
    ("hu", "Magyar"),
    ("es", "Español"),
    ("it", "Italiano"),
    ("pt", "Português"),
    ("ru", "Русский"),
    ("uk", "Українська"),
    ("pl", "Polski"),
    ("cs", "Čeština"),
    ("sk", "Slovenčina"),
    ("bg", "Български"),
    ("sr", "Српски"),
    ("hr", "Hrvatski"),
]


def translate_text_smart(text: str, target_lang: str) -> str:
    """Translate *text* line-by-line, preserving slide structure.

    Each non-empty line is translated individually so the display layout
    (line breaks, slide separators) is preserved exactly.  Empty lines
    (which separate slides) are passed through unchanged.
    """
    from deep_translator import GoogleTranslator
    translator = GoogleTranslator(source="auto", target=target_lang)
    result_lines: list[str] = []
    for line in text.splitlines():
        if line.strip():
            translated = translator.translate(line)
            result_lines.append(translated if translated else line)
        else:
            result_lines.append("")
    return "\n".join(result_lines)


class _TranslateThread(QThread):
    finished = pyqtSignal(str)
    progress = pyqtSignal(int, int)   # (done, total) non-empty lines
    error    = pyqtSignal(str)

    def __init__(self, text: str, target_lang: str, parent=None):
        super().__init__(parent)
        self._text   = text
        self._target = target_lang

    def run(self):
        try:
            from deep_translator import GoogleTranslator
            translator  = GoogleTranslator(source="auto", target=self._target)
            all_lines   = self._text.splitlines()
            non_empty   = [l for l in all_lines if l.strip()]
            total       = max(1, len(non_empty))
            done        = 0

            result_lines: list[str] = []
            for line in all_lines:
                if line.strip():
                    tr = translator.translate(line)
                    result_lines.append(tr if tr else line)
                    done += 1
                    self.progress.emit(done, total)
                else:
                    result_lines.append("")

            self.finished.emit("\n".join(result_lines))
        except Exception as e:
            self.error.emit(str(e))


_DIALOG_STYLE = """
QDialog, QWidget { background: #181818; color: #e0e0e0; font-family: 'Segoe UI'; }
QTextEdit {
    background: #1c1c1c; color: #e0e0e0; border: 1px solid #262626;
    border-radius: 4px; padding: 8px; font-size: 12px;
}
QComboBox {
    background: #1c1c1c; color: #e0e0e0; border: 1px solid #262626;
    border-radius: 4px; padding: 5px 8px;
}
QComboBox QAbstractItemView { background: #222; color: #e0e0e0; border: 1px solid #2e2e2e; }
QPushButton {
    background: #232323; color: #e0e0e0; border: 1px solid #2c2c2c;
    border-radius: 5px; padding: 7px 14px; font-size: 12px;
}
QPushButton:hover { background: #2a2a2a; border-color: #3a3a3a; }
QPushButton:pressed { background: #1a1a1a; }
QPushButton:disabled { color: #444; border-color: #1e1e1e; }
QLabel { color: #ccc; }
QProgressBar {
    background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 3px; height: 6px;
}
QProgressBar::chunk { background: #5294e2; border-radius: 3px; }
QSplitter::handle { background: #2a2a2a; }
"""


class TranslationDialog(QDialog):
    """Dialog for translating a song's lyrics with preview and DB save."""

    def __init__(self, song_text: str, song_id: int | None = None,
                 existing_translations: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🌐 Traducere cântare")
        self.setMinimumSize(800, 560)
        self.setStyleSheet(_DIALOG_STYLE)

        self._song_text = song_text
        self._song_id = song_id
        self._existing = existing_translations or {}
        self._thread: _TranslateThread | None = None
        self._translated_text = ""

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 10)
        layout.setSpacing(8)

        # ── Language row ──────────────────────────────────────────────────────
        lang_row = QHBoxLayout()

        lang_row.addWidget(QLabel("Traduce în:"))
        self._lang_combo = QComboBox()
        for code, name in _LANGUAGES:
            self._lang_combo.addItem(name, code)
        lang_row.addWidget(self._lang_combo)

        self._translate_btn = QPushButton("🔄 Traduce")
        self._translate_btn.setStyleSheet(
            "QPushButton { background: #18283a; color: #5294e2; "
            "border: 1px solid #1c3a5a; border-radius: 5px; padding: 7px 18px; }"
            "QPushButton:hover { background: #1c3a5a; color: #e0e0e0; }"
        )
        self._translate_btn.clicked.connect(self._start_translate)
        lang_row.addWidget(self._translate_btn)

        lang_row.addStretch()

        self._existing_lbl = QLabel("")
        self._existing_lbl.setStyleSheet("color: #4caf50; font-size: 11px;")
        lang_row.addWidget(self._existing_lbl)
        layout.addLayout(lang_row)

        # ── Progress bar ──────────────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(6)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # ── Split view: original | translated ─────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        orig_w = QWidget()
        orig_l = QVBoxLayout(orig_w)
        orig_l.setContentsMargins(0, 0, 4, 0)
        orig_hdr = QLabel("ORIGINAL")
        orig_hdr.setStyleSheet(
            "color: #5294e2; font-size: 10px; font-weight: 700; "
            "letter-spacing: 2px; padding: 2px 0;"
        )
        orig_l.addWidget(orig_hdr)
        self._orig_view = QTextEdit()
        self._orig_view.setReadOnly(True)
        self._orig_view.setPlainText(self._song_text)
        self._orig_view.setFont(QFont("Consolas", max(1, 10)))
        orig_l.addWidget(self._orig_view)

        trans_w = QWidget()
        trans_l = QVBoxLayout(trans_w)
        trans_l.setContentsMargins(4, 0, 0, 0)
        trans_hdr = QLabel("TRADUCERE")
        trans_hdr.setStyleSheet(
            "color: #5294e2; font-size: 10px; font-weight: 700; "
            "letter-spacing: 2px; padding: 2px 0;"
        )
        trans_l.addWidget(trans_hdr)
        self._trans_view = QTextEdit()
        self._trans_view.setFont(QFont("Consolas", max(1, 10)))
        self._trans_view.setPlaceholderText("Traducerea va apărea aici…")
        trans_l.addWidget(self._trans_view)

        splitter.addWidget(orig_w)
        splitter.addWidget(trans_w)
        splitter.setSizes([400, 400])
        layout.addWidget(splitter, 1)

        # ── Status label ──────────────────────────────────────────────────────
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._status_lbl)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()

        self._save_btn = QPushButton("✅ Salvează traducerea")
        self._save_btn.setEnabled(False)
        self._save_btn.setStyleSheet(
            "QPushButton { background: #1c3a1c; color: #4caf50; "
            "border: 1px solid #2a5a2a; border-radius: 5px; padding: 7px 18px; }"
            "QPushButton:hover { background: #2a4a2a; }"
            "QPushButton:disabled { color: #333; border-color: #1a1a1a; }"
        )
        self._save_btn.clicked.connect(self._save_translation)
        btn_row.addWidget(self._save_btn)

        # Connect signal and trigger initial state AFTER all widgets are created
        self._lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        self._on_lang_changed()

        dual_btn = QPushButton("📐 Configurează afișare duală")
        dual_btn.clicked.connect(self._open_dual_layout)
        btn_row.addWidget(dual_btn)

        btn_row.addStretch()

        close_btn = QPushButton("Închide")
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _on_lang_changed(self):
        if not hasattr(self, '_trans_view') or not hasattr(self, '_save_btn'):
            return
        code = self._lang_combo.currentData()
        if code and code in self._existing:
            self._existing_lbl.setText("✅ Traducere existentă în DB")
            self._trans_view.setPlainText(self._existing[code])
            self._translated_text = self._existing[code]
            self._save_btn.setEnabled(True)
        else:
            self._existing_lbl.setText("")
            self._trans_view.setPlainText("")
            self._translated_text = ""
            self._save_btn.setEnabled(False)

    def _start_translate(self):
        code = self._lang_combo.currentData()
        if not code:
            return
        self._translate_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status_lbl.setText("Se traduce…")

        self._progress.setRange(0, 0)   # indeterminate until first progress signal
        self._thread = _TranslateThread(self._song_text, code, self)
        self._thread.finished.connect(self._on_translate_done)
        self._thread.progress.connect(self._on_translate_progress)
        self._thread.error.connect(self._on_translate_error)
        self._thread.start()

    def _on_translate_progress(self, done: int, total: int):
        if self._progress.maximum() != total:
            self._progress.setRange(0, total)
        self._progress.setValue(done)
        self._status_lbl.setText(f"Se traduce… {done}/{total} linii")

    def _on_translate_done(self, text: str):
        self._progress.setVisible(False)
        self._translate_btn.setEnabled(True)
        self._translated_text = text
        self._trans_view.setPlainText(text)
        self._save_btn.setEnabled(bool(self._song_id))
        lang_name = self._lang_combo.currentText()
        self._status_lbl.setText(f"Traducere în {lang_name} completă.")

    def _on_translate_error(self, msg: str):
        self._progress.setVisible(False)
        self._translate_btn.setEnabled(True)
        self._status_lbl.setText(f"Eroare: {msg}")
        self._status_lbl.setStyleSheet("color: #f44336; font-size: 11px;")

    def _save_translation(self):
        if not self._song_id or not self._translated_text:
            return
        code = self._lang_combo.currentData()
        text = self._trans_view.toPlainText().strip()
        if not text:
            return
        try:
            import database as db
            db.save_song_translation(self._song_id, code, text)
            self._existing[code] = text
            lang_name = self._lang_combo.currentText()
            self._status_lbl.setText(
                f"✅ Traducerea în {lang_name} salvată în baza de date."
            )
            self._status_lbl.setStyleSheet("color: #4caf50; font-size: 11px;")
            self._existing_lbl.setText("✅ Traducere existentă în DB")
        except Exception as e:
            QMessageBox.critical(self, "Eroare", str(e))

    def _open_dual_layout(self):
        try:
            from dual_layout_editor import DualLayoutEditor
            dlg = DualLayoutEditor(parent=self)
            dlg.exec()
        except Exception as e:
            QMessageBox.information(self, "Info", str(e))

    def get_translated_text(self) -> str:
        return self._trans_view.toPlainText().strip()

    def get_target_lang(self) -> str:
        return self._lang_combo.currentData() or "en"
