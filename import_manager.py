"""
Cantio - Import Manager
Unified import dialog with tabs for Songs, Bible, Service.
Provides progress feedback and an import log.
"""
import os
import json
from datetime import datetime
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QPushButton, QLabel, QProgressBar, QTextEdit, QFileDialog,
    QMessageBox, QFrame, QGridLayout, QSizePolicy, QGroupBox,
    QListWidget, QListWidgetItem, QSplitter
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QIcon

import database as db
from translations import t


# ── Import history ─────────────────────────────────────────────────────────────

_HISTORY_PATH = os.path.join(os.path.expanduser("~"), "Cantio", "import_history.json")
_MAX_HISTORY = 50


def _load_history():
    if not os.path.exists(_HISTORY_PATH):
        return []
    try:
        with open(_HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_history_entry(entry: dict):
    history = _load_history()
    history.insert(0, entry)
    history = history[:_MAX_HISTORY]
    try:
        os.makedirs(os.path.dirname(_HISTORY_PATH), exist_ok=True)
        with open(_HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ── Worker thread for background import ───────────────────────────────────────

class ImportWorker(QThread):
    progress = pyqtSignal(int, int, str)     # current, total, message
    finished = pyqtSignal(dict)              # {"imported": N, "errors": N, "log": [...]}
    error = pyqtSignal(str)

    def __init__(self, import_func, filepath, extra_args=None):
        super().__init__()
        self.import_func = import_func
        self.filepath = filepath
        self.extra_args = extra_args or {}

    def run(self):
        log = []
        imported = 0
        errors = 0
        try:
            from importer import import_file, import_easyworship7_db
            basename = os.path.basename(self.filepath)
            self.progress.emit(0, 1, f"Se importă {basename}…")

            if self.extra_args.get("vp_json"):
                from importer import import_videopsalm_json
                songs = import_videopsalm_json(self.filepath)
                result = {"type": "songs", "data": songs}
            elif self.extra_args.get("ew7_rtf"):
                # New rowid-based RTF importer (Songs.db + SongWords.db / 'word' table)
                from importer import import_easyworship7
                def prog_cb(cur, tot):
                    self.progress.emit(cur, tot, f"Importând cântare {cur}/{tot}…")
                words_db = self.extra_args.get("words_db", "")
                songs = import_easyworship7(
                    self.filepath, words_db, progress_callback=prog_cb
                )
                result = {"type": "songs", "data": songs}
            elif self.extra_args.get("ew7_twofile"):
                from importer import import_easyworship7_twofile
                def prog_cb(cur, tot):
                    self.progress.emit(cur, tot, f"Importând cântare {cur}/{tot}…")
                words_db = self.extra_args.get("words_db", "")
                songs = import_easyworship7_twofile(
                    self.filepath, words_db, progress_callback=prog_cb
                )
                result = {"type": "songs", "data": songs}
            elif self.extra_args.get("ew7"):
                def prog_cb(cur, tot):
                    self.progress.emit(cur, tot, f"Importând cântare {cur}/{tot}…")
                songs = import_easyworship7_db(self.filepath, progress_callback=prog_cb)
                result = {"type": "songs", "data": songs}
            else:
                result = import_file(self.filepath)

            if result["type"] == "songs":
                songs = result["data"]
                total = len(songs)
                for i, s in enumerate(songs):
                    try:
                        db.add_song(
                            s["title"], s["content"], s["slides"],
                            s.get("author", ""), s.get("category", "General"),
                            s.get("language", "ro")
                        )
                        imported += 1
                        log.append(f"✓  {s['title']}")
                    except Exception as e:
                        errors += 1
                        log.append(f"✗  {s['title']}: {e}")
                    if i % 10 == 0:
                        self.progress.emit(i + 1, total, f"Se importă cântare {i + 1}/{total}…")

            elif result["type"] == "bible":
                data = result["data"]
                self.progress.emit(0, 1, "Se importă Biblia…")
                db.import_bible_data(data["books"], data["verses"])
                imported = len(data["books"])
                log.append(f"✓  {len(data['books'])} cărți, {len(data['verses'])} versete importate")

            self.progress.emit(imported, imported, "Import complet")
            self.finished.emit({
                "type": result["type"],
                "imported": imported,
                "errors": errors,
                "log": log,
            })

        except Exception as e:
            self.error.emit(str(e))


# ── Shared stylesheet ──────────────────────────────────────────────────────────

_STYLE = """
QDialog, QWidget { background: #181818; color: #e0e0e0;
    font-family: 'Segoe UI', sans-serif; font-size: 12px; }
QTabWidget::pane { border: none; background: #1a1a1a; }
QTabBar { background: #0f0f0f; }
QTabBar::tab { background: #0f0f0f; color: #666; padding: 8px 16px;
    border: none; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: #e0e0e0; border-bottom-color: #5294e2; background: #181818; }
QTabBar::tab:hover { color: #aaa; background: #141414; }
QPushButton { background: #232323; color: #e0e0e0;
    border: 1px solid #2c2c2c; border-radius: 5px;
    padding: 7px 14px; font-size: 12px; }
QPushButton:hover { background: #2a2a2a; border-color: #3a3a3a; }
QPushButton:pressed { background: #1a1a1a; }
QPushButton:disabled { color: #444; border-color: #1e1e1e; }
QListWidget { background: #141414; color: #e0e0e0; border: none; }
QListWidget::item { padding: 6px 10px; }
QListWidget::item:hover { background: #1e1e1e; }
QListWidget::item:selected { background: #1c3a5a; }
QTextEdit { background: #121212; color: #888; border: 1px solid #222;
    border-radius: 4px; padding: 8px; font-family: Consolas; font-size: 11px; }
QProgressBar { background: #141414; border: 1px solid #1e1e1e;
    border-radius: 4px; height: 8px; text-align: center; }
QProgressBar::chunk { background: #5294e2; border-radius: 3px; }
QFrame#div { background: #1e1e1e; max-height: 1px; min-height: 1px; }
QLabel#section { color: #5294e2; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
"""


def _fmt_btn(icon: str, label: str, desc: str = "") -> QPushButton:
    """Create a large format button for the import tabs."""
    b = QPushButton()
    b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    b.setFixedHeight(64)
    b.setText(f"{icon}  {label}")
    b.setToolTip(desc)
    b.setStyleSheet(
        "QPushButton { background: #1a1a1a; color: #cccccc; "
        "border: 1px solid #242424; border-radius: 6px; "
        "padding: 10px 16px; font-size: 13px; text-align: left; }"
        "QPushButton:hover { background: #1e1e1e; border-color: #5294e2; color: #fff; }"
        "QPushButton:pressed { background: #141414; }"
    )
    if desc:
        sub = QLabel(desc, b)
        sub.setStyleSheet("color: #555; font-size: 10px;")
        sub.move(48, 36)
    return b


# ── Import Manager Dialog ──────────────────────────────────────────────────────

class ImportManagerWindow(QDialog):
    songs_imported = pyqtSignal()
    bible_imported = pyqtSignal()
    service_loaded = pyqtSignal(list)       # list of service items

    def __init__(self, parent=None, service_items=None, profile_name="Default"):
        super().__init__(parent)
        self.setWindowTitle(f"{t('import')} — Cantio")
        self.setMinimumSize(680, 560)
        self.setStyleSheet(_STYLE)
        self._service_items = service_items or []
        self._profile_name = profile_name
        self._worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(44)
        hdr.setStyleSheet("background: #0f0f0f; border-bottom: 1px solid #1e1e1e;")
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(16, 0, 16, 0)
        title_lbl = QLabel("📥  IMPORT MANAGER")
        title_lbl.setStyleSheet("color: #5294e2; font-size: 13px; font-weight: 700; letter-spacing: 1px;")
        hdr_lay.addWidget(title_lbl)
        hdr_lay.addStretch()
        hist_btn = QPushButton("📋 Istoric")
        hist_btn.setFixedHeight(28)
        hist_btn.setStyleSheet(
            "QPushButton { background: #141414; color: #888; border: 1px solid #1e1e1e; "
            "border-radius: 4px; padding: 4px 10px; font-size: 11px; }"
            "QPushButton:hover { color: #e0e0e0; }"
        )
        hist_btn.clicked.connect(self._show_history)
        hdr_lay.addWidget(hist_btn)
        layout.addWidget(hdr)

        # Main splitter: tabs on left, log on right
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        splitter.setStyleSheet("QSplitter::handle { background: #1e1e1e; }")

        # Tabs
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.addTab(self._build_songs_tab(), "🎵  Cântări")
        self._tabs.addTab(self._build_bible_tab(), "📖  Biblie")
        self._tabs.addTab(self._build_service_tab(), "📋  Serviciu")
        splitter.addWidget(self._tabs)

        # Right panel: progress + log
        right = QWidget()
        right.setMinimumWidth(240)
        right.setMaximumWidth(300)
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(12, 12, 12, 12)
        right_lay.setSpacing(8)

        log_lbl = QLabel("LOG IMPORT")
        log_lbl.setObjectName("section")
        right_lay.addWidget(log_lbl)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setPlaceholderText("Rezultatele importului apar aici…")
        right_lay.addWidget(self._log, 1)

        self._progress_lbl = QLabel("Aștept…")
        self._progress_lbl.setStyleSheet("color: #555; font-size: 10px;")
        right_lay.addWidget(self._progress_lbl)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.hide()
        right_lay.addWidget(self._progress)

        divider = QFrame()
        divider.setObjectName("div")
        right_lay.addWidget(divider)

        clear_btn = QPushButton(t("clear"))
        clear_btn.setStyleSheet(
            "QPushButton { background: #141414; color: #555; border: 1px solid #1e1e1e; "
            "border-radius: 4px; padding: 5px 10px; font-size: 11px; }"
            "QPushButton:hover { color: #e0e0e0; }"
        )
        clear_btn.clicked.connect(self._log.clear)
        right_lay.addWidget(clear_btn)

        splitter.addWidget(right)
        splitter.setSizes([420, 240])
        layout.addWidget(splitter, 1)

        # Bottom bar
        bottom = QWidget()
        bottom.setFixedHeight(44)
        bottom.setStyleSheet("background: #0f0f0f; border-top: 1px solid #1e1e1e;")
        bot_lay = QHBoxLayout(bottom)
        bot_lay.setContentsMargins(16, 0, 16, 0)
        self._status_lbl = QLabel("Gata pentru import")
        self._status_lbl.setStyleSheet("color: #555; font-size: 11px;")
        bot_lay.addWidget(self._status_lbl, 1)
        close_btn = QPushButton(t("close"))
        close_btn.setFixedHeight(30)
        close_btn.clicked.connect(self.reject)
        bot_lay.addWidget(close_btn)
        layout.addWidget(bottom)

    # ── Songs tab ─────────────────────────────────────────────────────────────

    def _build_songs_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)

        info = QLabel("Selectează formatul fișierului de importat:")
        info.setStyleSheet("color: #666; font-size: 11px;")
        lay.addWidget(info)

        formats = [
            ("📄", "Text / Word / PDF", ".txt .docx .pdf",
             "Text Files (*.txt);;Word Documents (*.docx);;PDF (*.pdf)"),
            ("🎵", "VideoPsalm XML (.xml)", ".xml",
             "VideoPsalm XML (*.xml)"),
            ("🎵", t("import_vp_json"), ".json",
             "VideoPsalm JSON (*.json)"),
            ("⛪", "EasyWorship 6 (.db)", ".db .ewsx",
             "EasyWorship 6 (*.db *.ewsx)"),
            ("⛪", t("import_ew7"), ".db",
             "EasyWorship 7 Songs.db (*.db)"),
            ("📁", "Folder (importă toate fișierele)", "",
             ""),
        ]

        for icon, label, ext_hint, filt in formats:
            b = _fmt_btn(icon, label, ext_hint)
            if label.startswith("Folder"):
                b.clicked.connect(self._import_folder)
            elif label == t("import_ew7") or "EasyWorship 7" in label:
                b.clicked.connect(self._import_easyworship7_ui)
            elif label == t("import_vp_json") or "VideoPsalm JSON" in label:
                b.clicked.connect(self._import_videopsalm_json_ui)
            elif "VideoPsalm" in label:
                b.clicked.connect(lambda _, f=filt: self._start_import(f))
            else:
                b.clicked.connect(lambda _, f=filt: self._start_import(f))
            lay.addWidget(b)

        lay.addStretch()
        return w

    # ── Bible tab ──────────────────────────────────────────────────────────────

    def _build_bible_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)

        info = QLabel("Importă o Biblie pentru afișaj versete:")
        info.setStyleSheet("color: #666; font-size: 11px;")
        lay.addWidget(info)

        formats = [
            ("📖", "BibleShow (.bib)", ".bib",
             "BibleShow Bible (*.bib)"),
            ("📖", "XML Bible format", ".xml",
             "XML Bible (*.xml)"),
            ("📖", "Text Bible format", ".txt",
             "Text Bible (*.txt)"),
        ]

        for icon, label, ext_hint, filt in formats:
            b = _fmt_btn(icon, label, ext_hint)
            b.clicked.connect(lambda _, f=filt: self._start_import(f))
            lay.addWidget(b)

        lay.addStretch()
        return w

    # ── Service tab ───────────────────────────────────────────────────────────

    def _build_service_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)

        info = QLabel("Importă un serviciu în lista de serviciu:")
        info.setStyleSheet("color: #666; font-size: 11px;")
        lay.addWidget(info)

        b1 = _fmt_btn("📋", "Import serviciu Cantio (.gps)", ".gps")
        b1.clicked.connect(self._import_service_gps)
        lay.addWidget(b1)

        b2 = _fmt_btn("📋", "Import din EasyWorship Schedule", ".db .ewsx")
        b2.clicked.connect(self._import_ew_schedule)
        lay.addWidget(b2)

        lay.addStretch()
        return w

    # ── Import logic ──────────────────────────────────────────────────────────

    def _import_videopsalm_json_ui(self):
        """Import VideoPsalm JSON (.json) with non-standard unquoted-key format."""
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "Import activ", "Un import este deja în desfășurare.")
            return

        path, _ = QFileDialog.getOpenFileName(
            self,
            t("import_vp_json") + " — Selectează fișierul",
            "",
            "VideoPsalm JSON (*.json);;All Files (*)",
        )
        if not path:
            return

        self._progress.show()
        self._progress.setValue(0)
        self._log_msg(f"Import VideoPsalm JSON: {os.path.basename(path)}", "#5294e2")
        self._status_lbl.setText("Se importă VideoPsalm JSON…")

        from importer import import_file
        self._worker = ImportWorker(
            import_file, path,
            extra_args={"vp_json": True},
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _vpc_info_dialog(self):
        """
        VideoPsalm .vpc files are AES-encrypted with a non-public key.
        We cannot open them — show an informational message instead.
        """
        QMessageBox.information(
            self,
            "VideoPsalm (.vpc) — Format criptat",
            "Fișierele .vpc exportate din VideoPsalm sunt criptate cu AES.\n\n"
            "Parola de decriptare nu este publică și nu poate fi dedusă,\n"
            "deci Cantio nu poate citi aceste fișiere direct.\n\n"
            "Alternativă:\n"
            "  • Deschide VideoPsalm → Export → XML sau JSON\n"
            "  • Importă fișierul XML / JSON rezultat în Cantio.",
        )

    def _import_easyworship7_ui(self):
        """
        EasyWorship 7 stochează cântările în două fișiere separate:
          • Songs.db     — titluri, autori, copyright
          • SongsWords.db — textul strofelor (RTF)
        Cerem utilizatorului să selecteze ambele fișiere, în ordine.
        """
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "Import activ", "Un import este deja în desfășurare.")
            return

        songs_path, _ = QFileDialog.getOpenFileName(
            self,
            "EasyWorship 7 — Selectează Songs.db",
            "",
            "EasyWorship 7 Songs DB (Songs.db *.db)",
        )
        if not songs_path:
            return

        words_path, _ = QFileDialog.getOpenFileName(
            self,
            "EasyWorship 7 — Selectează SongsWords.db",
            os.path.dirname(songs_path),
            "EasyWorship 7 Words DB (SongsWords.db *.db)",
        )
        if not words_path:
            return

        self._progress.show()
        self._progress.setValue(0)
        name_s = os.path.basename(songs_path)
        name_w = os.path.basename(words_path)
        self._log_msg(f"Importând EasyWorship 7: {name_s} + {name_w}", "#5294e2")
        self._status_lbl.setText("Se importă EasyWorship 7 (2 fișiere)…")

        from importer import import_file
        self._worker = ImportWorker(
            import_file,
            songs_path,
            extra_args={"ew7_rtf": True, "words_db": words_path},
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _start_import(self, file_filter: str, ew7: bool = False):
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "Import activ", "Un import este deja în desfășurare.")
            return

        title = "Selectează fișierul de importat"
        path, _ = QFileDialog.getOpenFileName(self, title, "", file_filter)
        if not path:
            return

        self._run_worker(path, ew7=ew7)

    def _import_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Selectează folderul de importat")
        if not folder:
            return

        # Collect all supported files
        supported = {".txt", ".docx", ".pdf", ".json", ".xml", ".vpc", ".ewsx", ".db"}
        files = [
            os.path.join(folder, f) for f in os.listdir(folder)
            if os.path.splitext(f)[1].lower() in supported
        ]
        if not files:
            QMessageBox.information(self, "Folder gol", "Nu am găsit fișiere suportate în folderul ales.")
            return

        self._log_msg(f"Folderul selectat: {folder}", "#5294e2")
        self._log_msg(f"Fișiere găsite: {len(files)}", "#888")
        self._status_lbl.setText(f"Importând {len(files)} fișiere…")

        total_imported = 0
        for i, filepath in enumerate(files):
            try:
                from importer import import_file
                result = import_file(filepath)
                if result["type"] == "songs":
                    for s in result["data"]:
                        db.add_song(
                            s["title"], s["content"], s["slides"],
                            s.get("author", ""), s.get("category", "General"),
                            s.get("language", "ro")
                        )
                        total_imported += 1
                    self._log_msg(
                        f"✓  {os.path.basename(filepath)} → {len(result['data'])} cântări", "#66cc66"
                    )
            except Exception as e:
                self._log_msg(f"✗  {os.path.basename(filepath)}: {e}", "#f44336")
            self._progress.setValue(int((i + 1) / len(files) * 100))

        _save_history_entry({
            "ts": datetime.now().isoformat(timespec="seconds"),
            "path": folder,
            "type": "folder",
            "imported": total_imported,
        })
        self._status_lbl.setText(f"Import complet: {total_imported} cântări adăugate")
        self.songs_imported.emit()

    def _import_service_gps(self):
        import service_manager as sm
        path, _ = QFileDialog.getOpenFileName(
            self, "Deschide serviciu .gps", "", "Cantio Service (*.gps)"
        )
        if not path:
            return
        try:
            result = sm.load_service(path)
            self.service_loaded.emit(result["items"])
            self._log_msg(
                f"✓  Serviciu importat: {len(result['items'])} items din {os.path.basename(path)}", "#66cc66"
            )
            self._status_lbl.setText(f"Serviciu importat: {len(result['items'])} items")
        except Exception as e:
            self._log_msg(f"✗  Eroare: {e}", "#f44336")
            QMessageBox.critical(self, "Eroare", str(e))

    def _import_ew_schedule(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "EasyWorship Schedule", "",
            "EasyWorship (*.db *.ewsx)"
        )
        if not path:
            return
        self._log_msg("Import EasyWorship Schedule → în dezvoltare.", "#888")

    def _run_worker(self, filepath: str, ew7: bool = False):
        from importer import import_file
        self._progress.show()
        self._progress.setValue(0)
        self._log_msg(f"Importând: {os.path.basename(filepath)}", "#5294e2")
        self._status_lbl.setText(f"Se importă {os.path.basename(filepath)}…")

        self._worker = ImportWorker(import_file, filepath, extra_args={"ew7": ew7})
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, current: int, total: int, msg: str):
        if total > 0:
            self._progress.setValue(int(current / total * 100))
        self._progress_lbl.setText(msg)
        self._status_lbl.setText(msg)

    def _on_finished(self, result: dict):
        self._progress.hide()
        imported = result["imported"]
        errors = result["errors"]
        duplicates = result.get("duplicates", 0)
        rtype = result.get("type", "songs")
        label = "cântări" if rtype == "songs" else "cărți"

        for line in result.get("log", []):
            color = "#66cc66" if line.startswith("✓") else "#f44336"
            self._log_msg(line, color)

        # ── 0 imported ───────────────────────────────────────────────────────
        if imported == 0:
            if duplicates:
                msg = (
                    f"Nicio {label[:-1]} importată.\n\n"
                    f"Toate cele {duplicates} intrări existau deja în baza de date "
                    f"(duplicate ignorate)."
                )
            elif errors:
                msg = (
                    f"Nicio {label[:-1]} importată.\n\n"
                    f"Au fost {errors} erori la procesarea fișierului. "
                    f"Verificați jurnalul de mai jos."
                )
            else:
                msg = f"Nicio {label[:-1]} importată. Fișierul poate fi gol sau într-un format nesuportat."
            QMessageBox.warning(self, "Import fără rezultat", msg)
            self._log_msg(f"⚠  {msg.splitlines()[0]}", "#e2a252")
        # ── Partial import ───────────────────────────────────────────────────
        elif errors:
            msg = (
                f"Import parțial: {imported} {label} importate, {errors} erori.\n\n"
                "Verificați jurnalul pentru detalii."
            )
            QMessageBox.warning(self, "Import parțial", msg)
        # ── Duplicates present but some imported ─────────────────────────────
        elif duplicates:
            QMessageBox.information(
                self, "Import cu duplicate",
                f"Import complet: {imported} {label} importate.\n"
                f"{duplicates} duplicate au fost ignorate (existau deja).",
            )

        summary = f"✅  Import complet: {imported} {label}"
        if errors:
            summary += f", {errors} erori"
        if duplicates:
            summary += f", {duplicates} duplicate ignorate"
        self._log_msg(summary, "#66cc66" if not errors else "#e2a252")
        self._status_lbl.setText(summary)
        self._progress_lbl.setText("")

        _save_history_entry({
            "ts": datetime.now().isoformat(timespec="seconds"),
            "path": self._worker.filepath if self._worker else "",
            "type": rtype,
            "imported": imported,
            "errors": errors,
        })

        if rtype == "songs":
            self.songs_imported.emit()
        elif rtype == "bible":
            self.bible_imported.emit()

    def _on_error(self, msg: str):
        self._progress.hide()
        self._log_msg(f"✗  Eroare: {msg}", "#f44336")
        self._status_lbl.setText("Import eșuat")

        # Detect likely corrupt-file errors
        lower = msg.lower()
        if any(kw in lower for kw in ("invalid", "corrupt", "decode", "json", "xml",
                                       "zip", "unexpected", "cannot read")):
            QMessageBox.critical(
                self, "Fișier corupt sau invalid",
                f"Fișierul nu a putut fi citit:\n\n{msg}\n\n"
                "Verificați că fișierul nu este corupt și că este în formatul corect\n"
                "(OpenLyrics XML, EasyWorship, ProPresenter, ZIP cu fișiere .xml, etc.).",
            )
        else:
            QMessageBox.critical(self, "Eroare la import", msg)

    def _log_msg(self, text: str, color: str = "#888"):
        self._log.append(f'<span style="color:{color}">{text}</span>')

    # ── History dialog ────────────────────────────────────────────────────────

    def _show_history(self):
        history = _load_history()
        dlg = QDialog(self)
        dlg.setWindowTitle("Istoric importuri")
        dlg.setMinimumSize(480, 360)
        dlg.setStyleSheet(_STYLE)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)

        lbl = QLabel("ULTIMELE IMPORTURI")
        lbl.setObjectName("section")
        lay.addWidget(lbl)

        lw = QListWidget()
        for entry in history:
            ts = entry.get("ts", "")[:16].replace("T", " ")
            path = os.path.basename(entry.get("path", ""))
            rtype = entry.get("type", "")
            n = entry.get("imported", 0)
            err = entry.get("errors", 0)
            text = f"{ts}  ·  {path}  ·  {n} importate"
            if err:
                text += f"  ({err} erori)"
            item = QListWidgetItem(text)
            item.setForeground(QColor("#cccccc" if not err else "#e2a252"))
            lw.addItem(item)
        if not history:
            lw.addItem(QListWidgetItem("Nu există importuri anterioare."))
        lay.addWidget(lw, 1)

        close = QPushButton("Închide")
        close.clicked.connect(dlg.accept)
        lay.addWidget(close)
        dlg.exec()
