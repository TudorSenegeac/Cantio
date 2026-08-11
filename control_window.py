"""
Cantio - Control Window
FreeShow-inspired operator interface.
Includes: category filter, operator notes, auto-advance, DB export/import/PDF,
Bible keyword search, Supabase cloud, Stage Monitor, improved UI.
"""
import os
import json
import functools
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QListWidget, QListWidgetItem, QListView, QLabel, QLineEdit,
    QTextEdit, QComboBox, QTabWidget, QFileDialog, QMessageBox,
    QFormLayout, QDialog, QDialogButtonBox, QTreeWidget, QTreeWidgetItem,
    QFrame, QScrollArea, QApplication, QStatusBar, QToolBar, QSizePolicy,
    QGridLayout, QGroupBox, QSpinBox, QCheckBox, QInputDialog, QSpacerItem,
    QProgressDialog, QStyledItemDelegate, QStyle, QColorDialog, QRadioButton,
)
from PyQt6.QtCore import (Qt, QSize, pyqtSignal, QTimer, QRect, QPoint, QSizeF, QRectF,
                           QAbstractListModel, QModelIndex, QPointF)
from PyQt6.QtGui import (
    QFont, QIcon, QAction, QColor, QPainter, QFontMetrics, QPen,
    QLinearGradient, QBrush, QPixmap, QShortcut, QKeySequence,
    QTextCharFormat, QTextBlockFormat, QTextDocument, QTextCursor,
)

import logging
logger = logging.getLogger("cantio.control")

import database as db
try:
    from display_window import DisplayWindow   # kept for legacy; Electron is primary renderer
except ImportError:
    DisplayWindow = None  # type: ignore
from preview_widget import PreviewWidget
from settings_dialog import SettingsDialog
from importer import import_file
import profile_manager as pm
import service_manager as sm
import remote_server as rs
import keyboard_shortcuts as ks
from toast_notifications import ToastManager, set_global_toast_manager
from live_state import get_state
from translations import t
from render_engine import RenderEngine
from media_engine import MediaEngine
from db_thread import async_db


# ── Global Stylesheet (FreeShow-inspired dark theme) ─────────────────────────

APP_STYLE = """
QMainWindow, QWidget {
    background-color: #181818;
    color: #e0e0e0;
    font-family: 'Segoe UI', sans-serif;
    font-size: 12px;
}
QSplitter { background: #111111; }
QSplitter::handle { background: #1e1e1e; }
QSplitter::handle:horizontal { width: 2px; }
QSplitter::handle:vertical { height: 2px; }
QSplitter::handle:hover { background: #5294e2; }

QScrollBar:vertical {
    background: #141414; width: 6px; border: none; margin: 0;
}
QScrollBar::handle:vertical {
    background: #2e2e2e; border-radius: 3px; min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: #3e3e3e; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #141414; height: 6px; border: none; margin: 0;
}
QScrollBar::handle:horizontal {
    background: #2e2e2e; border-radius: 3px; min-width: 20px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

QTabWidget::pane { border: none; background: #1a1a1a; }
QTabBar { background: #0f0f0f; }
QTabBar::tab {
    background: #0f0f0f; color: #666666; padding: 8px 18px;
    border: none; border-bottom: 2px solid transparent;
    font-size: 12px; font-weight: 500; min-width: 60px;
}
QTabBar::tab:selected {
    color: #e0e0e0; border-bottom: 2px solid #5294e2;
    background: #181818;
}
QTabBar::tab:hover { color: #aaaaaa; background: #141414; }

QLineEdit, QTextEdit, QPlainTextEdit {
    background: #1c1c1c; color: #e0e0e0;
    border: 1px solid #262626; border-radius: 5px; padding: 6px 8px;
    selection-background-color: #1a3a5c;
}
QLineEdit:focus, QTextEdit:focus { border-color: #5294e2; }
QLineEdit::placeholder { color: #444444; }

QListWidget, QTreeWidget {
    background: #141414; color: #e0e0e0;
    border: none; outline: none; padding: 2px 0;
}
QListWidget::item {
    padding: 7px 12px; border-radius: 4px; margin: 1px 4px;
    border: none;
}
QListWidget::item:hover { background: #1e1e1e; color: #ffffff; }
QListWidget::item:selected {
    background: #1c3a5a; color: #e8e8e8; border: none;
}
QTreeWidget::item { padding: 4px 8px; }
QTreeWidget::item:hover { background: #1e1e1e; }
QTreeWidget::item:selected { background: #1c3a5a; }

QPushButton {
    background: #232323; color: #e0e0e0;
    border: 1px solid #2c2c2c; border-radius: 5px;
    padding: 7px 14px; font-size: 12px; font-weight: 500;
}
QPushButton:hover { background: #2a2a2a; border-color: #3a3a3a; }
QPushButton:pressed { background: #1a1a1a; }
QPushButton:checked { background: #1a3a5c; border-color: #5294e2; color: #5294e2; }
QPushButton:disabled { color: #444; border-color: #1e1e1e; background: #191919; }

QPushButton#go_live {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #3a7a3d,stop:1 #2d6a30);
    color: #ffffff; border: 1px solid #4a8a4d;
    font-size: 14px; font-weight: 700; border-radius: 6px; padding: 12px 20px;
    letter-spacing: 1px;
}
QPushButton#go_live:hover {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #4a8a4d,stop:1 #3a7a3d);
}
QPushButton#go_live:pressed { background: #245227; }

QPushButton#black_btn {
    background: #1c1c1c; color: #f44336;
    border: 1px solid #2e1a1a; border-radius: 6px;
    font-weight: 600; padding: 8px 14px;
}
QPushButton#black_btn:hover { background: #251a1a; border-color: #f44336; }

QPushButton#nav_btn {
    background: #1c1c1c; color: #aaaaaa; border: 1px solid #262626;
    border-radius: 5px; padding: 7px; font-size: 14px;
}
QPushButton#nav_btn:hover { background: #232323; color: #e0e0e0; }
QPushButton#nav_btn:disabled { color: #333; background: #161616; }

QComboBox {
    background: #1c1c1c; color: #e0e0e0;
    border: 1px solid #262626; border-radius: 4px; padding: 5px 8px;
}
QComboBox:focus { border-color: #5294e2; }
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView {
    background: #222222; color: #e0e0e0;
    border: 1px solid #2e2e2e; selection-background-color: #1c3a5a;
}

QGroupBox {
    border: 1px solid #222222; border-radius: 6px;
    margin-top: 6px; padding: 10px 8px 8px 8px;
    color: #555555; font-size: 10px; font-weight: 700;
    letter-spacing: 1px;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 10px;
    color: #5294e2; font-weight: 700;
    font-size: 10px; text-transform: uppercase;
}

QLabel { color: #cccccc; }
QLabel#section_lbl { color: #5294e2; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
QLabel#muted { color: #555555; font-size: 11px; }
QLabel#notes_lbl { color: #ccaa44; font-size: 10px; font-weight: 700; letter-spacing: 1px; }

QStatusBar { background: #0f0f0f; color: #555555; border-top: 1px solid #1e1e1e; }
QStatusBar::item { border: none; }

QToolBar {
    background: #0f0f0f; border-bottom: 1px solid #1c1c1c;
    padding: 4px 8px; spacing: 4px;
}
QToolBar::separator { background: #242424; width: 1px; margin: 4px 4px; }

QScrollArea { border: none; }

QFrame#divider { background: #1e1e1e; max-height: 1px; min-height: 1px; }
QFrame#side_panel { background: #131313; border-right: 1px solid #1e1e1e; }
QFrame#center_panel { background: #181818; }
QFrame#right_panel { background: #131313; border-left: 1px solid #1e1e1e; }
"""


# ── Thumbnail size presets ────────────────────────────────────────────────────

THUMB_SIZES = {
    "XS": (120, 68),
    "S":  (168, 94),
    "M":  (220, 124),
    "L":  (300, 169),
    "XL": (400, 225),
}
_THUMB_SIZE_ORDER = ["XS", "S", "M", "L", "XL"]


# ── Performance detection ─────────────────────────────────────────────────────

def detect_performance() -> str:
    """
    Detect hardware tier using psutil (RAM + CPU count) when available,
    then cross-check with a QPixmap render benchmark.
    Returns 'low', 'medium', or 'high'.
    """
    # ── psutil hardware check ─────────────────────────────────────────────────
    try:
        from lazy_imports import get_psutil
        psutil = get_psutil()
        ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        cpu_count = psutil.cpu_count(logical=False) or psutil.cpu_count() or 2
        if ram_gb < 6 or cpu_count <= 2:
            hw_level = "low"
        elif ram_gb < 12 or cpu_count <= 4:
            hw_level = "medium"
        else:
            hw_level = "high"
    except Exception:
        hw_level = "medium"

    # ── QPainter render benchmark ─────────────────────────────────────────────
    import time
    from PyQt6.QtGui import QPixmap, QPainter, QColor
    try:
        start = time.perf_counter()
        pix = QPixmap(1920, 1080)
        painter = QPainter(pix)
        painter.fillRect(0, 0, 1920, 1080, QColor("#000000"))
        painter.end()
        elapsed = time.perf_counter() - start
        if elapsed > 0.05:
            render_level = "low"
        elif elapsed > 0.02:
            render_level = "medium"
        else:
            render_level = "high"
    except Exception:
        render_level = hw_level

    # Return the worse of the two assessments
    _order = {"low": 0, "medium": 1, "high": 2}
    return min(hw_level, render_level, key=lambda x: _order[x])


# ── Songs list model (virtual / paginated) ────────────────────────────────────

class SongsModel(QAbstractListModel):
    """
    Virtual list model — only (id, title, author) in RAM.
    Slides are never loaded here; loaded on demand via get_song().
    Uses FTS5 search when available, falls back to LIKE otherwise.
    """
    _AUTHOR_ROLE = Qt.ItemDataRole.UserRole + 1
    PAGE_SIZE = 200

    def __init__(self, parent=None):
        super().__init__(parent)
        self._songs: list[dict] = []
        self._total: int = 0
        self._search: str = ""
        self._category: str = ""
        # Debounce timer — 250ms after last keystroke
        self._load_timer = QTimer()
        self._load_timer.setSingleShot(True)
        self._load_timer.setInterval(250)
        self._load_timer.timeout.connect(self._do_load)

    # ── Qt model interface ────────────────────────────────────────────────────

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._songs)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._songs):
            return None
        song = self._songs[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return song["title"]
        if role == Qt.ItemDataRole.UserRole:
            return song["id"]
        if role == self._AUTHOR_ROLE:
            return song.get("author", "")
        if role == Qt.ItemDataRole.ToolTipRole:
            return (f"Autor: {song.get('author') or '–'}\n"
                    f"Categorie: {song.get('category') or '–'}")
        return None

    # ── Drag support ──────────────────────────────────────────────────────────

    def flags(self, index: QModelIndex):
        base = super().flags(index)
        if index.isValid():
            return base | Qt.ItemFlag.ItemIsDragEnabled
        return base

    def mimeTypes(self):
        return ["application/x-glorify-song-id"]

    def mimeData(self, indexes):
        from PyQt6.QtCore import QMimeData, QByteArray
        md = QMimeData()
        if indexes:
            song_id = self.data(indexes[0], Qt.ItemDataRole.UserRole)
            if song_id is not None:
                md.setData("application/x-glorify-song-id",
                           QByteArray(str(song_id).encode()))
        return md

    # ── Data management ───────────────────────────────────────────────────────

    def search(self, query: str):
        """Called from textChanged — debounces 250ms before hitting DB."""
        self._search = query
        self._load_timer.start()

    def load_page(self, search: str = "", category: str = ""):
        """Immediate load (category filter, initial load, library refresh)."""
        self._search = search
        self._category = category
        self._do_load()

    def _do_load(self):
        query = self._search.strip()
        try:
            if query:
                rows = db.search_songs_fast(
                    query, limit=self.PAGE_SIZE, category=self._category
                )
            else:
                rows = db.get_songs_titles_only(
                    limit=self.PAGE_SIZE, offset=0, category=self._category
                )
            print(f"[MODEL] Loaded {len(rows)} songs for query='{query}'")
            self.beginResetModel()
            self._songs = rows
            self._total = len(rows) if query else db.get_songs_count(
                search="", category=self._category
            )
            self.endResetModel()
        except Exception as e:
            print(f"[MODEL] Load error: {e}")
            # Do NOT clear the list on error — keep showing old results
            self.layoutChanged.emit()

    def load_more(self):
        """Append next page — called at scroll 85%."""
        if self._search:        # FTS already returns 200 best matches
            return
        if len(self._songs) >= self._total:
            return
        more = db.get_songs_titles_only(
            limit=self.PAGE_SIZE, offset=len(self._songs),
            search="", category=self._category
        )
        if not more:
            return
        first = len(self._songs)
        last = first + len(more) - 1
        self.beginInsertRows(QModelIndex(), first, last)
        self._songs.extend(more)
        self.endInsertRows()

    @property
    def total(self) -> int:
        return self._total


# ── Song list delegate ────────────────────────────────────────────────────────

class SongDelegate(QStyledItemDelegate):
    """
    Draws title + author in each row.
    Two-line layout when author present, one-line otherwise.
    Uses setUniformItemSizes=False so row heights can vary.
    """
    _AUTHOR_ROLE = Qt.ItemDataRole.UserRole + 1

    def paint(self, painter, option, index):
        painter.save()
        rect = option.rect
        selected = bool(option.state & QStyle.StateFlag.State_Selected)

        # Background
        bg = QColor("#1c3a5a") if selected else (
            QColor("#1a1a1a") if bool(option.state & QStyle.StateFlag.State_MouseOver)
            else QColor("#131313")
        )
        painter.fillRect(rect, bg)

        title  = index.data(Qt.ItemDataRole.DisplayRole) or ""
        author = index.data(self._AUTHOR_ROLE) or ""

        title_color  = QColor("#e0e0e0") if selected else QColor("#cccccc")
        author_color = QColor("#aaaaaa") if selected else QColor("#666666")

        # Title
        painter.setPen(title_color)
        painter.setFont(QFont("Segoe UI", 10))
        title_rect = rect.adjusted(10, 4, -6, -14 if author else -4)
        painter.drawText(
            title_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            title
        )
        # Author (smaller, below)
        if author:
            painter.setPen(author_color)
            painter.setFont(QFont("Segoe UI", 8))
            author_rect = rect.adjusted(10, rect.height() - 16, -6, -2)
            painter.drawText(
                author_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                author
            )

        painter.restore()

    def sizeHint(self, option, index):
        author = index.data(self._AUTHOR_ROLE)
        return QSize(option.rect.width(), 40 if author else 28)


# ── Slide Thumbnail ───────────────────────────────────────────────────────────

# ── Uppercase Dialog ──────────────────────────────────────────────────────────

class UppercaseDialog(QDialog):
    """Dialog for converting song lyrics to uppercase."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Uppercase cântări")
        self.setMinimumWidth(380)
        self.setStyleSheet(
            "QDialog { background:#181818; color:#e0e0e0; }"
            "QLabel { color:#e0e0e0; }"
            "QRadioButton { color:#e0e0e0; padding:4px; }"
            "QComboBox { background:#1c1c1c; color:#e0e0e0; border:1px solid #333; "
            "border-radius:4px; padding:4px; }"
        )
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Fă toate literele MARI pentru:"))

        self.all_radio = QRadioButton("Toate cântările din bibliotecă")
        self.cat_radio = QRadioButton("Cântările dintr-o categorie")
        self.sel_radio = QRadioButton("Cântarea selectată curent")
        self.all_radio.setChecked(True)
        layout.addWidget(self.all_radio)
        layout.addWidget(self.cat_radio)
        layout.addWidget(self.sel_radio)

        self.cat_combo = QComboBox()
        self.cat_combo.setEnabled(False)
        try:
            self.cat_combo.addItems(db.get_all_categories())
        except Exception:
            pass
        self.cat_radio.toggled.connect(self.cat_combo.setEnabled)
        layout.addWidget(self.cat_combo)

        warn = QLabel("⚠ Atenție: acțiunea nu poate fi anulată!\nFă backup înainte.")
        warn.setStyleSheet("color:#f38ba8; font-size:11px;")
        layout.addWidget(warn)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_params(self) -> dict:
        if self.all_radio.isChecked():
            return {"mode": "all"}
        elif self.cat_radio.isChecked():
            return {"mode": "category", "category": self.cat_combo.currentText()}
        else:
            return {"mode": "selected"}


# ── Split Lines Dialog ────────────────────────────────────────────────────────

class SplitLinesDialog(QDialog):
    """Dialog for splitting song slides by a fixed number of lines."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Împarte slide-uri pe rânduri")
        self.setMinimumWidth(400)
        self.setStyleSheet(
            "QDialog { background:#181818; color:#e0e0e0; }"
            "QLabel { color:#e0e0e0; }"
            "QSpinBox { background:#1c1c1c; color:#e0e0e0; border:1px solid #333; "
            "border-radius:4px; padding:4px; }"
            "QRadioButton { color:#e0e0e0; padding:4px; }"
            "QComboBox { background:#1c1c1c; color:#e0e0e0; border:1px solid #333; "
            "border-radius:4px; padding:4px; }"
        )
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Câte rânduri pe slide?"))

        lines_row = QHBoxLayout()
        self.lines_spin = QSpinBox()
        self.lines_spin.setRange(1, 20)
        self.lines_spin.setValue(4)
        lines_row.addWidget(QLabel("Rânduri per slide:"))
        lines_row.addWidget(self.lines_spin)
        lines_row.addStretch()
        layout.addLayout(lines_row)

        preview_label = QLabel("Exemplu:")
        preview_label.setStyleSheet("color:#6c7086; font-size:11px;")
        layout.addWidget(preview_label)

        self.preview_text = QLabel()
        self.preview_text.setStyleSheet(
            "background:#181825; padding:8px; border-radius:6px;"
            " color:#cdd6f4; font-family:Consolas; font-size:11px;"
        )
        layout.addWidget(self.preview_text)
        self.lines_spin.valueChanged.connect(self._update_preview)
        self._update_preview(4)

        layout.addWidget(QLabel("Aplică pentru:"))
        self.all_radio = QRadioButton("Toate cântările")
        self.cat_radio = QRadioButton("O categorie")
        self.sel_radio = QRadioButton("Cântarea selectată")
        self.all_radio.setChecked(True)
        layout.addWidget(self.all_radio)
        layout.addWidget(self.cat_radio)
        layout.addWidget(self.sel_radio)

        self.cat_combo = QComboBox()
        self.cat_combo.setEnabled(False)
        try:
            self.cat_combo.addItems(db.get_all_categories())
        except Exception:
            pass
        self.cat_radio.toggled.connect(self.cat_combo.setEnabled)
        layout.addWidget(self.cat_combo)

        warn = QLabel("⚠ Acțiunea modifică permanent structura slide-urilor!")
        warn.setStyleSheet("color:#f38ba8; font-size:11px;")
        layout.addWidget(warn)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _update_preview(self, n: int):
        lines = [f"Rând {i + 1}" for i in range(n * 2)]
        chunks = [
            "\n".join(lines[i:i + n])
            for i in range(0, len(lines), n)
        ]
        self.preview_text.setText("\n─────────\n".join(chunks))

    def get_params(self) -> dict:
        mode = (
            "all"      if self.all_radio.isChecked() else
            "category" if self.cat_radio.isChecked() else
            "selected"
        )
        return {
            "lines":    self.lines_spin.value(),
            "mode":     mode,
            "category": self.cat_combo.currentText(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Auto-label helper: assigns a section name to a plain-text slide
# based on common keyword heuristics when no explicit label exists.

_LABEL_KEYWORDS = {
    "refren": "Refren", "chorus": "Refren",
    "bridge": "Bridge", "intro": "Intro", "outro": "Outro",
    "verse": "Strofa", "strofă": "Strofa", "strofa": "Strofa",
    "hallelujah": "Hallelujah", "alleluja": "Hallelujah",
    "coda": "Coda", "tag": "Tag", "pre": "Pre-Chorus",
}


def _auto_slide_label(text: str, index: int, total: int) -> str:
    """
    Heuristically assign a label to a plain-text slide.
    Returns a short label string (e.g. "Refren", "Strofa 1") or "".
    """
    if not text:
        return ""
    first_line = text.split("\n")[0].strip().lower()
    for kw, label in _LABEL_KEYWORDS.items():
        if first_line.startswith(kw):
            return label
    # Generic numbered label for multi-slide songs
    if total > 1:
        return f"S{index + 1}"
    return ""


# ─────────────────────────────────────────────────────────────────────────────

class SlideThumbnail(QWidget):
    """Mini 16:9 preview of a slide, FreeShow-style."""

    clicked = pyqtSignal(int)
    double_clicked = pyqtSignal(int)
    context_action = pyqtSignal(str, int)   # (action_name, slide_index)
    # Default size (used as fallback); actual size set via thumb_w/thumb_h args
    THUMB_W = 168
    THUMB_H = 94

    def __init__(self, text, index, settings=None, parent=None,
                 thumb_w=168, thumb_h=94, label="", label_color=""):
        super().__init__(parent)
        # Support dict-format slides: {"text": "...", "label": "...", "label_color": "..."}
        if isinstance(text, dict):
            self.slide_text  = text.get("text", "")
            self.label       = text.get("label", label)
            self.label_color = text.get("label_color", label_color) or label_color
        else:
            self.slide_text  = text
            self.label       = label
            self.label_color = label_color
        self.slide_index = index
        self.settings = settings or {}
        self._selected = False
        self._sel_active = True    # True = blue (slides have focus), False = grey
        self._hovered = False
        self.thumb_w = thumb_w
        self.thumb_h = thumb_h
        # Pixmap cache — render once, reuse until mark_dirty()
        self._cached_pixmap = None
        self._dirty = True
        self._wysiwyg_pix = None      # WYSIWYG override (bg-engine render)
        self._checker_bg  = False     # show a transparency checkerboard as bg
        self.setFixedSize(self.thumb_w, self.thumb_h + 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        # Never take focus — prevent stealing the caret from the lyrics editor
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def set_selected(self, val):
        if self._selected != val:
            self._selected = val
            self.mark_dirty()

    def set_selection_active(self, active: bool):
        """Blue (active) when the slides panel has focus; grey (inactive) when
        focus moved to the song/service list — a visual cue that keyboard slide
        navigation targets the slides only while this is blue."""
        active = bool(active)
        if self._sel_active != active:
            self._sel_active = active
            if self._selected:      # only the selected thumb shows the colour
                self.mark_dirty()

    def _sel_color(self):
        return QColor("#5294e2") if self._sel_active else QColor("#585863")

    def mark_dirty(self):
        """Invalidate cached pixmap; schedules a repaint."""
        self._cached_pixmap = None
        self._dirty = True
        self.update()

    def update_settings(self, settings):
        self.settings = settings
        self.mark_dirty()

    def set_wysiwyg(self, pixmap):
        """Display a real (Electron bg-engine) render instead of the Qt drawing."""
        self._wysiwyg_pix = pixmap
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Clicking a slide moves the operator's attention to the slides — focus
            # handling (leaving the editor so Page Up/Down navigate slides) is done
            # in _select_slide. We deliberately do NOT restore the editor caret here.
            self.clicked.emit(self.slide_index)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.slide_index)

    def contextMenuEvent(self, event):
        from PyQt6.QtWidgets import QMenu, QWidgetAction
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #1e1e1e; color: #e0e0e0; border: 1px solid #333; "
            "padding: 2px; font-size: 12px; }"
            "QMenu::item { padding: 6px 20px 6px 12px; border-radius: 3px; }"
            "QMenu::item:selected { background: #1c3a5a; color: #fff; }"
            "QMenu::separator { background: #333; height: 1px; margin: 3px 0; }"
        )
        idx = self.slide_index
        menu.addAction("⬆  Mută sus",   lambda: self.context_action.emit("move_up",    idx))
        menu.addAction("⬇  Mută jos",   lambda: self.context_action.emit("move_down",  idx))
        menu.addAction("⏫  La început", lambda: self.context_action.emit("move_first", idx))
        menu.addAction("⏬  La sfârșit", lambda: self.context_action.emit("move_last",  idx))
        menu.addSeparator()
        menu.addAction("❏  Duplică",    lambda: self.context_action.emit("duplicate",  idx))
        menu.addSeparator()
        menu.addAction("🏷  Schimbă eticheta", lambda: self._change_label())
        menu.addSeparator()

        # QAction nu suportă setStyleSheet — folosim QWidgetAction cu QLabel roșu
        del_lbl = QLabel("✕  Șterge slide")
        del_lbl.setStyleSheet(
            "color: #f44336; padding: 6px 20px 6px 12px; font-size: 12px;"
        )
        del_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        wa_del = QWidgetAction(menu)
        wa_del.setDefaultWidget(del_lbl)
        wa_del.triggered.connect(lambda checked=False: self.context_action.emit("delete", idx))
        menu.addAction(wa_del)

        menu.exec(event.globalPos())

    def _change_label(self):
        """Show a small dialog to change this slide's section label."""
        predefined = [
            "Strofa 1", "Strofa 2", "Strofa 3", "Strofa 4",
            "Strofa 5", "Strofa 6", "Refren", "Cor",
            "Bridge", "Pre-Refren", "Intro", "Outro", "Pod", "Final",
        ]
        current_idx = 0
        try:
            current_idx = predefined.index(self.label)
        except ValueError:
            pass

        from PyQt6.QtWidgets import QInputDialog
        label, ok = QInputDialog.getItem(
            self, "Schimbă eticheta",
            "Selectează sau scrie eticheta slide-ului:",
            predefined, current_idx, True,
        )
        if ok and label:
            self.label = label.strip()
            try:
                import database as _db
                self.label_color = _db.get_label_color(self.label)
            except Exception:
                pass
            self.mark_dirty()
            self.context_action.emit("label_changed", self.slide_index)

    def enterEvent(self, event):
        self._hovered = True
        self.mark_dirty()

    def leaveEvent(self, event):
        self._hovered = False
        self.mark_dirty()

    def paintEvent(self, event):
        # WYSIWYG override: draw the real Electron bg-engine render (scaled to
        # the slide area), then the selection border + label bar on top.
        if self._wysiwyg_pix is not None and not self._wysiwyg_pix.isNull():
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            p.drawPixmap(0, 0, self._wysiwyg_pix.scaled(
                self.thumb_w, self.thumb_h,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
            if self._selected:
                pen = p.pen(); pen.setColor(self._sel_color()); pen.setWidth(3); p.setPen(pen)
                p.drawRect(1, 1, self.thumb_w - 2, self.thumb_h - 2)
            if self.label:
                p.fillRect(0, self.thumb_h, self.thumb_w, 22, QColor("#141414"))
                p.setPen(QColor(self.label_color or "#888888"))
                f = p.font(); f.setPointSize(8); p.setFont(f)
                p.drawText(6, self.thumb_h + 15, str(self.label))
            p.end()
            return
        # Serve from cache when nothing has changed
        if not self._dirty and self._cached_pixmap is not None:
            p = QPainter(self)
            p.drawPixmap(0, 0, self._cached_pixmap)
            p.end()
            return

        dpr = max(1.0, self.devicePixelRatio())
        SS  = 3          # render at 3× then scale → sharp text + HiDPI-correct
        tw, th = self.thumb_w, self.thumb_h
        tw3  = tw * SS
        th3  = th * SS
        bar3 = 22 * SS

        # ── Off-screen 3× surface ─────────────────────────────────────────────
        ss_pix = QPixmap(tw3, th3 + bar3)
        p = QPainter(ss_pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        thumb      = QRect(0, 0, tw3, th3)
        label_rect = QRect(0, th3, tw3, bar3)

        s = self.settings

        # ── Background ────────────────────────────────────────────────────────
        bg_type = str(s.get("bg_type", "color") or "color")
        if self._checker_bg:
            # Transparency checkerboard — shows the slide "on transparent" so the
            # operator can judge overlays/keying (does NOT affect the live output).
            cell = 8 * SS
            lightc = QColor("#3a3a44"); darkc = QColor("#23232a")
            ny = (th3 // cell) + 1
            nx = (tw3 // cell) + 1
            for gy in range(ny):
                for gx in range(nx):
                    p.fillRect(gx * cell, gy * cell, cell, cell,
                               lightc if (gx + gy) % 2 == 0 else darkc)
        elif bg_type == "gradient":
            c1   = QColor(str(s.get("bg_grad_c1", s.get("bg_color", "#000033")) or "#000033"))
            c2   = QColor(str(s.get("bg_grad_c2", "#000000") or "#000000"))
            dir_ = str(s.get("bg_grad_dir", "Sus→Jos") or "Sus→Jos")
            if dir_ in ("Stânga→Dreapta", "Left→Right"):
                grad = QLinearGradient(QPointF(0, 0), QPointF(tw3, 0))
            elif dir_ in ("Diagonală", "Diagonal"):
                grad = QLinearGradient(QPointF(0, 0), QPointF(tw3, th3))
            else:
                grad = QLinearGradient(QPointF(0, 0), QPointF(0, th3))
            grad.setColorAt(0, c1)
            grad.setColorAt(1, c2)
            p.fillRect(thumb, grad)
        else:
            p.fillRect(thumb, QColor(str(s.get("bg_color", "#000000") or "#000000")))

        # Hover gradient overlay
        if self._hovered and not self._selected:
            hov = QLinearGradient(0, 0, 0, th3)
            hov.setColorAt(0, QColor(255, 255, 255, 8))
            hov.setColorAt(1, QColor(255, 255, 255, 0))
            p.fillRect(thumb, hov)

        # ── Section label badge (top-left) ────────────────────────────────────
        if self.label:
            lbl_color = QColor(self.label_color or "#6c7086")
            lbl_font  = QFont("Segoe UI", 7 * SS, QFont.Weight.Bold)
            p.setFont(lbl_font)
            fm_lbl = p.fontMetrics()
            pad    = 4 * SS
            lbl_w  = fm_lbl.horizontalAdvance(self.label) + pad * 2
            lbl_h  = 14 * SS
            badge  = QRect(4 * SS, 4 * SS, lbl_w, lbl_h)
            p.setBrush(QBrush(lbl_color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(badge, 3 * SS, 3 * SS)
            p.setPen(QColor("#1e1e2e"))
            p.drawText(badge, Qt.AlignmentFlag.AlignCenter, self.label)

        # ── Slide text ────────────────────────────────────────────────────────
        if self.slide_text:
            scale3      = tw3 / 1920.0
            base_size   = max(1, int(s.get("font_size", 48) or 48))
            font_family = s.get("font_family", "Arial")
            font_bold   = s.get("font_bold",   "true") == "true"
            font_italic = s.get("font_italic", "false") == "true"
            margin3     = max(2 * SS, int(int(s.get("margin", 60)) * scale3))
            avail_w3    = tw3 - 2 * margin3
            avail_h3    = th3 - 2 * margin3

            _html_slide = (self.slide_text.lstrip().startswith("<!DOCTYPE")
                           or self.slide_text.lstrip().startswith("<html"))

            if _html_slide:
                doc = QTextDocument()
                fsize3 = max(1, int(base_size * scale3))
                base_f = QFont(font_family, fsize3)
                base_f.setBold(font_bold)
                base_f.setItalic(font_italic)
                doc.setDefaultFont(base_f)
                doc.setDefaultStyleSheet(
                    f"body {{ color: {s.get('text_color', '#ffffff')}; }}"
                    "p { margin: 0; padding: 0; }"
                )
                doc.setPageSize(QSizeF(avail_w3, avail_h3))
                doc.setHtml(self.slide_text)
                doc_h  = doc.size().height()
                y_off3 = max(margin3, (th3 - int(doc_h)) // 2)
                p.save()
                p.setClipRect(QRect(margin3, margin3, avail_w3, avail_h3))
                p.translate(margin3, y_off3)
                doc.drawContents(p, QRectF(0, 0, avail_w3, avail_h3))
                p.restore()
            else:
                from preview_widget import render_text_on_painter
                render_text_on_painter(p, self.slide_text, tw3, th3, s, scale3)

        # ── Label bar ─────────────────────────────────────────────────────────
        if self._selected:
            bar_color = QColor("#1a3355" if self._sel_active else "#2b2b33")
        else:
            bar_color = QColor("#161616")
        p.fillRect(label_rect, bar_color)

        # Number badge
        badge_color = self._sel_color() if self._selected else QColor("#2a2a2a")
        badge_rect  = QRect(4 * SS, th3 + 4 * SS, 22 * SS, 14 * SS)
        p.setBrush(QBrush(badge_color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(badge_rect, 3 * SS, 3 * SS)

        p.setPen(QColor("#ffffff") if self._selected else QColor("#888888"))
        num_font = QFont("Segoe UI", 7 * SS, QFont.Weight.Bold)
        p.setFont(num_font)
        p.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, str(self.slide_index + 1))

        # Preview text in label bar
        p.setPen(QColor("#cccccc") if self._selected else QColor("#555555"))
        text_font = QFont("Segoe UI", 7 * SS)
        p.setFont(text_font)
        preview = self.slide_text.replace("\n", " ")[:28]
        if len(self.slide_text.replace("\n", " ")) > 28:
            preview += "…"
        p.drawText(
            QRect(30 * SS, th3 + 4 * SS, (tw - 34) * SS, 14 * SS),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            preview
        )

        # Border
        if self._selected:
            pen = QPen(self._sel_color())
            pen.setWidth(2 * SS)
        elif self._hovered:
            pen = QPen(QColor("#3a3a3a"))
            pen.setWidth(SS)
        else:
            pen = QPen(QColor("#222222"))
            pen.setWidth(SS)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(pen)
        p.drawRect(0, 0, tw3 - SS, th3 + bar3 - SS)

        p.end()
        self._dirty = False

        # Scale 3× surface → physical pixels (handles any DPI correctly)
        w_phy = max(1, int(self.width()  * dpr))
        h_phy = max(1, int(self.height() * dpr))
        self._cached_pixmap = ss_pix.scaled(
            w_phy, h_phy,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._cached_pixmap.setDevicePixelRatio(dpr)

        screen_p = QPainter(self)
        screen_p.drawPixmap(0, 0, self._cached_pixmap)
        screen_p.end()


# ── Smart Paste ───────────────────────────────────────────────────────────────

import re as _re

# Patterns that mark the start of a new stanza/section
_STANZA_PATTERNS = _re.compile(
    r"^\s*("
    r"\d+\s*[.)]\s"             # "1. " "2) "
    r"|Strofa\s+\d+"            # "Strofa 1"
    r"|R\s*[:.]\s*"             # "R: " "R." "R :"
    r"|Ref\s*[:.]\s*"           # "Ref: " "Ref."
    r"|Refren\s*[:.]*\s*"       # "Refren:" "Refren"
    r"|REFREN\s*"               # "REFREN"
    r"|Chorus\s*[:.]\s*"        # "Chorus:"
    r"|/[:.]\s*"                # "/:" "/ :"
    r"|Pod\s*[:.]\s*"           # "Pod:"
    r"|Bridge\s*[:.]\s*"        # "Bridge:"
    r"|Pre-refren\s*[:.]\s*"    # "Pre-refren:"
    r")",
    _re.IGNORECASE
)


def _smart_reformat(text: str, remove_numbers: bool = False,
                    remove_markers: bool = False,
                    split_long: bool = True) -> str:
    """
    Reformat pasted lyrics:
    1. Insert blank line before each stanza/refrain marker.
    2. Optionally split long lines at comma/semicolon.
    3. Optionally strip stanza numbers and refrain markers.
    4. Normalize whitespace.
    """
    lines = [ln.rstrip() for ln in text.splitlines()]
    out = []
    for ln in lines:
        stripped = ln.strip()
        if not stripped:
            out.append("")
            continue

        # Insert blank line before marker (if previous non-empty line isn't blank)
        if _STANZA_PATTERNS.match(stripped):
            if out and out[-1].strip():
                out.append("")

        # Optionally remove stanza numbers ("1. ", "2) ")
        if remove_numbers:
            stripped = _re.sub(r"^\d+\s*[.)]\s*", "", stripped)

        # Optionally remove refrain markers
        if remove_markers:
            stripped = _re.sub(
                r"^(R\s*[:.]\s*|Ref\s*[:.]\s*|Refren\s*[:.]*\s*|REFREN\s*"
                r"|Chorus\s*[:.]\s*|/[:.]\s*|Pod\s*[:.]\s*|Bridge\s*[:.]\s*"
                r"|Pre-refren\s*[:.]\s*)",
                "", stripped, flags=_re.IGNORECASE
            ).strip()

        # Normalize multiple spaces
        stripped = _re.sub(r"  +", " ", stripped)

        # Split long lines at natural break points
        if split_long and len(stripped) > 80:
            segments = []
            current = ""
            for part in _re.split(r"([,;]\s*)", stripped):
                if len(current) + len(part) <= 55 or not current:
                    current += part
                else:
                    if current.strip():
                        segments.append(current.strip())
                    current = part
            if current.strip():
                segments.append(current.strip())
            out.extend(segments)
        else:
            out.append(stripped)

    # Collapse triple+ blank lines to double
    result = _re.sub(r"\n{3,}", "\n\n", "\n".join(out))
    return result.strip()


def _detect_stanzas(text: str) -> int:
    """Count likely stanzas in text (blank-line-separated blocks)."""
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    return len(blocks)


class SmartPasteDialog(QDialog):
    """
    Advanced smart paste dialog — detects stanza markers, shows before/after preview,
    offers cleanup options.
    """

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Smart Paste — Formatare versuri")
        self.setMinimumSize(680, 520)
        self.setStyleSheet(APP_STYLE)
        self.processed_text = text
        self._raw = text

        # Load saved preference
        settings = db.get_settings()
        self._skip_dialog = settings.get("smart_paste_skip", "false") == "true"

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        hdr = QLabel("SMART PASTE — FORMATARE AUTOMATĂ VERSURI")
        hdr.setStyleSheet("color: #5294e2; font-size: 10px; font-weight: 700; letter-spacing: 2px;")
        layout.addWidget(hdr)

        # Stats line
        lines_n = len([l for l in text.splitlines() if l.strip()])
        markers = len(_STANZA_PATTERNS.findall(text))
        self._info_lbl = QLabel(
            f"Text lipit: {lines_n} linii detectate"
            + (f", {markers} markeri de strofă/refren" if markers else "") + "."
        )
        self._info_lbl.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(self._info_lbl)

        # Options row
        opts_frame = QFrame()
        opts_frame.setStyleSheet("background: #131313; border-radius: 6px; padding: 6px;")
        opts_lay = QHBoxLayout(opts_frame)
        opts_lay.setContentsMargins(10, 6, 10, 6)
        opts_lay.setSpacing(14)

        self._chk_remove_nums = QCheckBox("Elimină nr. strofă (1. 2.)")
        self._chk_remove_markers = QCheckBox("Elimină markeri refren (R: Ref:)")
        self._chk_split_long = QCheckBox("Împarte linii lungi (>80 car.)")
        self._chk_split_long.setChecked(True)

        for cb in (self._chk_remove_nums, self._chk_remove_markers, self._chk_split_long):
            cb.setStyleSheet(
                "QCheckBox { color: #aaa; font-size: 11px; }"
                "QCheckBox::indicator { width: 14px; height: 14px; "
                "border: 1px solid #333; border-radius: 3px; background: #1c1c1c; }"
                "QCheckBox::indicator:checked { background: #5294e2; border-color: #5294e2; }"
            )
            cb.toggled.connect(self._update_preview)
            opts_lay.addWidget(cb)
        opts_lay.addStretch()
        layout.addWidget(opts_frame)

        # Side-by-side preview
        preview_row = QHBoxLayout()
        preview_row.setSpacing(10)

        left_col = QVBoxLayout()
        left_lbl = QLabel("ORIGINAL")
        left_lbl.setStyleSheet("color: #555; font-size: 10px; font-weight: 700; letter-spacing: 1px;")
        left_col.addWidget(left_lbl)
        self._orig_edit = QTextEdit()
        self._orig_edit.setReadOnly(True)
        self._orig_edit.setFont(QFont("Consolas", 9))
        self._orig_edit.setStyleSheet(
            "QTextEdit { background: #111; color: #666; border: 1px solid #1e1e1e; "
            "border-radius: 4px; padding: 6px; }"
        )
        self._orig_edit.setPlainText(text)
        left_col.addWidget(self._orig_edit)
        preview_row.addLayout(left_col)

        right_col = QVBoxLayout()
        right_lbl = QLabel("REFORMATAT")
        right_lbl.setStyleSheet("color: #5294e2; font-size: 10px; font-weight: 700; letter-spacing: 1px;")
        right_col.addWidget(right_lbl)
        self._new_edit = QTextEdit()
        self._new_edit.setReadOnly(True)
        self._new_edit.setFont(QFont("Consolas", 9))
        self._new_edit.setStyleSheet(
            "QTextEdit { background: #0d1520; color: #cccccc; border: 1px solid #1c3a5a; "
            "border-radius: 4px; padding: 6px; }"
        )
        right_col.addWidget(self._new_edit)
        preview_row.addLayout(right_col)
        layout.addLayout(preview_row, 1)

        # "Don't ask again" checkbox
        self._chk_skip = QCheckBox("Nu mai întreba (folosește reformatat automat)")
        self._chk_skip.setStyleSheet(
            "QCheckBox { color: #555; font-size: 10px; }"
            "QCheckBox::indicator { width: 12px; height: 12px; "
            "border: 1px solid #333; border-radius: 2px; background: #1c1c1c; }"
            "QCheckBox::indicator:checked { background: #5294e2; border-color: #5294e2; }"
        )
        layout.addWidget(self._chk_skip)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        self._use_orig_btn = QPushButton("Păstrează original")
        self._use_orig_btn.setStyleSheet(
            "QPushButton { background: #1c1c1c; color: #aaa; border: 1px solid #252525; "
            "border-radius: 5px; padding: 8px 20px; }"
            "QPushButton:hover { background: #222; color: #e0e0e0; }"
        )
        self._use_orig_btn.clicked.connect(self._use_original)
        btn_row.addWidget(self._use_orig_btn)

        self._use_fmt_btn = QPushButton("✓  Folosește reformatat")
        self._use_fmt_btn.setStyleSheet(
            "QPushButton { background: #5294e2; color: #fff; border: none; "
            "border-radius: 5px; padding: 8px 20px; font-weight: 600; }"
            "QPushButton:hover { background: #6ba5f0; }"
        )
        self._use_fmt_btn.clicked.connect(self._use_formatted)
        btn_row.addWidget(self._use_fmt_btn)
        layout.addLayout(btn_row)

        self._update_preview()

    def _update_preview(self):
        reformatted = _smart_reformat(
            self._raw,
            remove_numbers=self._chk_remove_nums.isChecked(),
            remove_markers=self._chk_remove_markers.isChecked(),
            split_long=self._chk_split_long.isChecked(),
        )
        self._new_edit.setPlainText(reformatted)
        stanzas = _detect_stanzas(reformatted)
        self._info_lbl.setText(
            self._info_lbl.text().split("→")[0].rstrip()
            + f"  →  {stanzas} strofă/slide{'uri' if stanzas != 1 else ''} după reformatare"
        )

    def _use_original(self):
        self.processed_text = self._raw
        self._save_pref()
        self.accept()

    def _use_formatted(self):
        self.processed_text = self._new_edit.toPlainText()
        self._save_pref()
        self.accept()

    def _save_pref(self):
        if self._chk_skip.isChecked():
            db.save_setting("smart_paste_skip", "true")


class SmartTextEdit(QTextEdit):
    """
    QTextEdit that detects structured lyrics on paste and offers smart reformatting.
    Handles patterns from resurse-crestine.ro and similar sources.
    """

    def insertFromMimeData(self, source):
        if source.hasText():
            text = source.text()
            non_empty = [l for l in text.splitlines() if l.strip()]
            has_blank_lines = "\n\n" in text
            has_markers = bool(_STANZA_PATTERNS.search(text))

            # Check "don't ask again" preference
            settings = db.get_settings()
            skip = settings.get("smart_paste_skip", "false") == "true"

            should_dialog = (
                not has_blank_lines and len(non_empty) > 3
            ) or has_markers

            if should_dialog:
                if skip:
                    # Auto-apply reformatting silently
                    reformatted = _smart_reformat(text)
                    self.textCursor().insertText(reformatted)
                    return
                dlg = SmartPasteDialog(text, self)
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    self.textCursor().insertText(dlg.processed_text)
                    return
        super().insertFromMimeData(source)


# ── Dynamic presentation generator dialog ──────────────────────────────────────

class DynamicGenDialog(QDialog):
    """Collect a title, genre, lyrics and an audio source for a dynamic,
    audio-reactive presentation."""

    GENRES = ["Worship / Închinare", "Rock", "Pop", "Jazz", "Hip-Hop",
              "Electronic", "Clasic", "Gospel", "Folk", "Ambient"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚡ Prezentare dinamică (BETA)")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        _beta = QLabel("⚠ Funcție BETA — auto-avansul și alinierea pe voce sunt "
                       "experimentale; verifică rezultatul înainte de serviciu.")
        _beta.setStyleSheet("color:#f9e2af; font-size:10px; background:#2a2410; "
                            "border:1px solid #4a4020; border-radius:4px; padding:6px;")
        _beta.setWordWrap(True)
        lay.addWidget(_beta)
        form = QFormLayout()

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Titlul melodiei")
        form.addRow("Titlu", self.title_edit)

        self.genre_combo = QComboBox()
        self.genre_combo.addItems(self.GENRES)
        form.addRow("Gen", self.genre_combo)
        lay.addLayout(form)

        lay.addWidget(QLabel("Versuri (un slide per paragraf — linie goală între ele):"))
        self.lyrics_edit = QTextEdit()
        self.lyrics_edit.setAcceptRichText(False)
        self.lyrics_edit.setPlaceholderText(
            "Strofa 1 rândul 1\nStrofa 1 rândul 2\n\nStrofa 2 rândul 1\n…")
        self.lyrics_edit.setMinimumHeight(180)
        lay.addWidget(self.lyrics_edit)

        arow = QHBoxLayout()
        self.audio_edit = QLineEdit()
        self.audio_edit.setPlaceholderText("Fișier MP3/WAV  sau  URL YouTube")
        browse = QPushButton("📁 Alege MP3…")
        browse.clicked.connect(self._browse)
        arow.addWidget(QLabel("Audio"))
        arow.addWidget(self.audio_edit, 1)
        arow.addWidget(browse)
        lay.addLayout(arow)

        self.reveal_chk = QCheckBox("Afișează versurile cuvânt cu cuvânt (pe ritm)")
        self.reveal_chk.setChecked(True)
        lay.addWidget(self.reveal_chk)

        self.align_chk = QCheckBox("🎯 Aliniere AI a versurilor cu vocea (Whisper) — mai lent, mai precis")
        self.align_chk.setChecked(False)
        lay.addWidget(self.align_chk)

        self.create_only_chk = QCheckBox("📄 Doar creează prezentarea (fără audio & auto-avans) — o conduci manual")
        self.create_only_chk.setChecked(False)
        lay.addWidget(self.create_only_chk)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("⚡ Generează & rulează")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Alege fișierul audio", "",
            "Audio (*.mp3 *.wav *.ogg *.m4a *.flac)")
        if path:
            self.audio_edit.setText(path)

    def get_data(self):
        return {
            "title":  self.title_edit.text().strip() or "Prezentare dinamică",
            "genre":  self.genre_combo.currentText(),
            "lyrics": self.lyrics_edit.toPlainText(),
            "audio":  self.audio_edit.text().strip(),
            "reveal": self.reveal_chk.isChecked(),
            "align":  self.align_chk.isChecked(),
            "create_only": self.create_only_chk.isChecked(),
        }


# ── Song Editor Dialog ────────────────────────────────────────────────────────

class SongEditorDialog(QDialog):
    def __init__(self, parent=None, song=None):
        super().__init__(parent)
        self.setWindowTitle(t("edit_song") if song else t("new_song"))
        self.setMinimumSize(700, 580)
        self.setStyleSheet(APP_STYLE)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        header_text = (
            f"{t('edit_song')}: {song.get('title','')}" if song
            else t("new_song")
        )
        header = QLabel(header_text)
        header.setObjectName("section_lbl")
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(8)
        self.title_edit = QLineEdit(song["title"] if song else "")
        self.title_edit.setPlaceholderText(t("song_title_placeholder"))
        self.author_edit = QLineEdit(song.get("author", "") if song else "")
        self.author_edit.setPlaceholderText(t("author") + "…")
        self.category_edit = QComboBox()
        self.category_edit.setEditable(True)
        for cat in db.BUILTIN_CATEGORIES[1:]:
            self.category_edit.addItem(cat)
        if song:
            cat = song.get("category", "General")
            idx = self.category_edit.findText(cat)
            if idx >= 0:
                self.category_edit.setCurrentIndex(idx)
            else:
                self.category_edit.setCurrentText(cat)
        self.lang_combo = QComboBox()
        for lang in ["ro", "el", "cu", "en", "fr", "de", "hu", "es", "pt"]:
            self.lang_combo.addItem(lang)
        if song:
            idx = self.lang_combo.findText(song.get("language", "ro"))
            if idx >= 0:
                self.lang_combo.setCurrentIndex(idx)
        form.addRow(t("title") + " *", self.title_edit)
        form.addRow(t("author"), self.author_edit)
        form.addRow(t("category"), self.category_edit)
        form.addRow(t("language"), self.lang_combo)
        layout.addLayout(form)

        notes_lbl = QLabel(t("operator_notes"))
        notes_lbl.setObjectName("notes_lbl")
        layout.addWidget(notes_lbl)
        self.notes_edit = QTextEdit()
        self.notes_edit.setFont(QFont("Segoe UI", 10))
        self.notes_edit.setFixedHeight(60)
        self.notes_edit.setPlaceholderText(t("operator_notes") + "…")
        self.notes_edit.setStyleSheet(
            "QTextEdit { background: #1a1a0a; border: 1px solid #3a3010; "
            "border-radius: 4px; color: #ccaa44; padding: 5px; }"
        )
        if song:
            self.notes_edit.setPlainText(song.get("notes", ""))
        layout.addWidget(self.notes_edit)

        hint = QLabel(t("lyrics_editor") + ":")
        hint.setObjectName("muted")
        layout.addWidget(hint)

        self.content_edit = QTextEdit()
        self.content_edit.setFont(QFont("Consolas", 11))
        self.content_edit.setPlaceholderText(
            "Strofa 1 linia 1\nStrofa 1 linia 2\n\nStrofa 2 linia 1\nStrofa 2 linia 2"
        )
        if song:
            self.content_edit.setPlainText(song["content"])
        layout.addWidget(self.content_edit, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        save_btn.setText(t("save"))
        cancel_btn.setText(t("cancel"))
        save_btn.setStyleSheet(
            "QPushButton { background: #5294e2; color: #fff; border: none; "
            "border-radius: 5px; padding: 7px 20px; font-weight: 600; }"
            "QPushButton:hover { background: #6ba5f0; }"
        )
        layout.addWidget(buttons)

    def get_data(self):
        content = self.content_edit.toPlainText()
        slides = [b.strip() for b in content.split("\n\n") if b.strip()]
        return {
            "title": self.title_edit.text().strip(),
            "author": self.author_edit.text().strip(),
            "category": self.category_edit.currentText().strip(),
            "language": self.lang_combo.currentText(),
            "content": content,
            "slides": slides,
            "notes": self.notes_edit.toPlainText().strip(),
        }


# ── Slides placeholder (shown when no song is loaded) ────────────────────────

class SlidesPlaceholder(QWidget):
    """Friendly empty-state shown in the slides panel when nothing is loaded."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: #181818;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 40, 24, 40)
        layout.setSpacing(12)
        layout.addStretch(2)

        logo_lbl = QLabel("✦")
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        logo_lbl.setStyleSheet("color: #cba6f7; font-size: 42px; background: transparent;")
        layout.addWidget(logo_lbl)

        title_lbl = QLabel("Cantio")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        title_lbl.setStyleSheet(
            "color: #e0e0e0; font-size: 18px; font-weight: 700; background: transparent;"
        )
        layout.addWidget(title_lbl)

        sub_lbl = QLabel("Selectează o cântare din listă pentru a începe")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        sub_lbl.setWordWrap(True)
        sub_lbl.setStyleSheet("color: #555566; font-size: 11px; background: transparent;")
        layout.addWidget(sub_lbl)

        layout.addSpacing(20)

        for hint in [
            "💡 Dublu-click pe o cântare → editare",
            "⌨  Ctrl+F → caută rapid",
            "📺 Click pe un slide → trimite live",
            "⚙  F4 → setări temă",
        ]:
            h = QLabel(hint)
            h.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            h.setStyleSheet("color: #404055; font-size: 10px; background: transparent;")
            layout.addWidget(h)

        layout.addStretch(3)


# ── Slide list view delegate ──────────────────────────────────────────────────

class SlideListDelegate(QStyledItemDelegate):
    """
    Custom delegate for the list-view mode of the slide panel.
    Each item shows:
      • A slide number badge on the left (bold, accent colour)
      • The FULL text of the slide with word-wrap (monospaced font)
      • A subtle separator line at the bottom
    The row height auto-adjusts to the number of lines in the slide text.
    """

    _LINE_H   = 20      # pixels per text line
    _PADDING  = 12      # top + bottom padding inside row
    _NUM_W    = 32      # width reserved for the slide number column

    @staticmethod
    def _safe_text(index):
        """Coerce model data to a plain string. Slides may be stored as dicts
        ({'text': ...}) when they carry labels, or as lists — never assume str."""
        data = index.data(Qt.ItemDataRole.UserRole)
        if isinstance(data, dict):
            return str(data.get("text", "") or "")
        if isinstance(data, (list, tuple)):
            return "\n".join(str(x) for x in data)
        return str(data) if data is not None else ""

    def sizeHint(self, option, index):
        text = self._safe_text(index)
        lines = max(1, text.count("\n") + 1)
        return QSize(option.rect.width(),
                     max(44, lines * self._LINE_H + self._PADDING * 2))

    def paint(self, painter, option, index):
        painter.save()

        text    = self._safe_text(index)
        num     = index.data(Qt.ItemDataRole.UserRole + 1)
        num_str = str(num) if num is not None else ""

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered  = bool(option.state & QStyle.StateFlag.State_MouseOver)

        # ── Background ────────────────────────────────────────────────────────
        if selected:
            painter.fillRect(option.rect, QColor("#1c3a5a"))
        elif hovered:
            painter.fillRect(option.rect, QColor("#1e1e1e"))
        else:
            painter.fillRect(option.rect, QColor("#141414"))

        r = option.rect
        pad = self._PADDING

        # ── Slide number badge ────────────────────────────────────────────────
        badge_rect = QRect(r.left() + 6, r.top() + pad, 22, 14)
        badge_color = QColor("#5294e2") if selected else QColor("#2a2a2a")
        painter.setBrush(QBrush(badge_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(badge_rect, 3, 3)

        num_font = QFont("Segoe UI", 7, QFont.Weight.Bold)
        painter.setFont(num_font)
        painter.setPen(QColor("#ffffff") if selected else QColor("#888888"))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, num_str)

        # ── Full slide text ───────────────────────────────────────────────────
        text_rect = QRect(
            r.left() + self._NUM_W,
            r.top() + pad,
            r.width() - self._NUM_W - 8,
            r.height() - pad * 2,
        )
        text_font = QFont("Consolas", 9)
        painter.setFont(text_font)
        painter.setPen(QColor("#e0e0e0") if selected else QColor("#cccccc"))
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            text,
        )

        # ── Bottom separator ──────────────────────────────────────────────────
        sep_pen = QPen(QColor("#1e1e1e"))
        sep_pen.setWidth(1)
        painter.setPen(sep_pen)
        painter.drawLine(r.left(), r.bottom(), r.right(), r.bottom())

        painter.restore()


# ── Import Category Dialog ────────────────────────────────────────────────────

class _ImportCategoryDialog(QDialog):
    """Dialog shown before importing songs — lets user pick/create a category."""

    _DEFAULT_CATS = [
        "General", "Imnuri", "Psalmi", "Colinde", "Copii",
        "Tineret", "Laudă și Închinare", "Rugăciune", "Speciale",
    ]

    def __init__(self, songs_count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Cântări")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        info = QLabel(f"Se vor importa <b>{songs_count}</b> cântări.\nSelectează categoria/genul:")
        info.setStyleSheet("color:#cdd6f4;")
        layout.addWidget(info)

        layout.addWidget(QLabel("Categorie / Gen:"))
        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        try:
            db_cats = db.get_all_categories()
        except Exception:
            db_cats = []
        all_cats = list(dict.fromkeys(self._DEFAULT_CATS + db_cats))
        self.category_combo.addItems(all_cats)
        layout.addWidget(self.category_combo)

        self.keep_original = QCheckBox("Păstrează categoria din fișier (dacă există)")
        self.keep_original.setChecked(True)
        self.keep_original.setStyleSheet("color:#cdd6f4;")
        layout.addWidget(self.keep_original)

        new_row = QHBoxLayout()
        new_row.addWidget(QLabel("Sau creează categorie nouă:"))
        self.new_cat_edit = QLineEdit()
        self.new_cat_edit.setPlaceholderText("Nume categorie nouă...")
        new_row.addWidget(self.new_cat_edit)
        layout.addLayout(new_row)

        self.preview_label = QLabel()
        self.preview_label.setStyleSheet("color:#a6e3a1; font-weight:bold;")
        layout.addWidget(self.preview_label)
        self._update_preview()

        self.category_combo.currentTextChanged.connect(self._update_preview)
        self.new_cat_edit.textChanged.connect(self._update_preview)
        self.keep_original.stateChanged.connect(self._update_preview)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _update_preview(self):
        cat = self.get_category()
        if self.keep_original.isChecked():
            self.preview_label.setText(f"Categorie din fișier sau: {cat}")
        else:
            self.preview_label.setText(f"Toate în: {cat}")

    def get_category(self) -> str:
        new = self.new_cat_edit.text().strip()
        return new if new else self.category_combo.currentText()

    def use_original_category(self) -> bool:
        return self.keep_original.isChecked()


# ── Mini Video Player ────────────────────────────────────────────────────────

class MiniVideoPlayer(QWidget):
    """Compact media player embedded below the right-panel controls."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(170)
        self._current_file = None
        self._is_image = False
        self.parent_control = None   # set by caller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Title
        self.title_label = QLabel("🎬 Media Player")
        self.title_label.setStyleSheet(
            "color:#cba6f7; font-size:11px; font-weight:bold;"
        )
        layout.addWidget(self.title_label)

        # Try to set up real player; fall back silently if not available
        self._player_ok = False
        try:
            from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
            from PyQt6.QtMultimediaWidgets import QVideoWidget

            self._video_widget = QVideoWidget()
            self._video_widget.setMinimumHeight(120)
            self._video_widget.setStyleSheet("background:#000000; border-radius:6px;")
            layout.addWidget(self._video_widget)

            self.player = QMediaPlayer()
            self._audio = QAudioOutput()
            self._audio.setVolume(0.7)
            self.player.setAudioOutput(self._audio)
            self.player.setVideoOutput(self._video_widget)
            self.player.positionChanged.connect(self._update_progress)
            self.player.playbackStateChanged.connect(self._on_playback_state)
            self.player.mediaStatusChanged.connect(self._on_media_status)
            self._player_ok = True
        except Exception:
            no_lbl = QLabel("(Video not available — PyQt6-Qt6-Multimedia missing)")
            no_lbl.setStyleSheet("color:#585b70; font-size:10px;")
            no_lbl.setWordWrap(True)
            layout.addWidget(no_lbl)

        # Controls row
        from PyQt6.QtWidgets import QSlider
        ctrl = QHBoxLayout()
        ctrl.setSpacing(4)

        self._play_btn = QPushButton("▶")
        self._play_btn.setFixedWidth(30)
        self._play_btn.clicked.connect(self._toggle_play)
        ctrl.addWidget(self._play_btn)

        self._stop_btn = QPushButton("⏹")
        self._stop_btn.setFixedWidth(30)
        self._stop_btn.clicked.connect(self._stop)
        ctrl.addWidget(self._stop_btn)

        self._progress = QSlider(Qt.Orientation.Horizontal)
        self._progress.setRange(0, 1000)
        self._progress.sliderMoved.connect(self._seek)
        ctrl.addWidget(self._progress, 1)

        self._vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(70)
        self._vol_slider.setFixedWidth(55)
        self._vol_slider.setToolTip("Volum")
        self._vol_slider.valueChanged.connect(self._set_volume)
        ctrl.addWidget(self._vol_slider)

        layout.addLayout(ctrl)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        self._send_btn = QPushButton("📺 Send Live")
        self._send_btn.setStyleSheet(
            "QPushButton{background:#313244;color:#a6e3a1;"
            "border:1px solid #a6e3a1;border-radius:5px;"
            "padding:4px 8px;font-size:11px;}"
            "QPushButton:hover{background:#3d3f5a;}"
        )
        self._send_btn.clicked.connect(self._send_to_live)
        btn_row.addWidget(self._send_btn)

        self._loop_btn = QPushButton("🔁 Loop")
        self._loop_btn.setCheckable(True)
        self._loop_btn.setStyleSheet(
            "QPushButton{background:#313244;color:#cdd6f4;"
            "border:1px solid #45475a;border-radius:5px;"
            "padding:4px 8px;font-size:11px;}"
            "QPushButton:checked{background:#45475a;color:#cba6f7;"
            "border-color:#cba6f7;}"
        )
        btn_row.addWidget(self._loop_btn)

        layout.addLayout(btn_row)
        self.setVisible(False)  # hidden until a file is loaded

    # ── Public API ────────────────────────────────────────────────────────────

    def mouseDoubleClickEvent(self, event):
        # Double-click the player → hide it and return to the slides.
        if self.parent_control and hasattr(self.parent_control, "hide_media_player"):
            self.parent_control.hide_media_player()
        else:
            super().mouseDoubleClickEvent(event)

    def load_file(self, filepath: str):
        import os
        self._current_file = filepath
        self._is_image = False
        ext = os.path.splitext(filepath)[1].lower()
        name = os.path.basename(filepath)

        if ext in (".mp4", ".mov", ".avi", ".mkv", ".webm"):
            if self._player_ok:
                from PyQt6.QtCore import QUrl
                self.player.setSource(QUrl.fromLocalFile(filepath))
                self.player.play()
                self._play_btn.setText("⏸")
            self.title_label.setText(f"🎬 {name}")
            self.setVisible(True)
        elif ext in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
            self._is_image = True
            self.title_label.setText(f"🖼 {name}")
            self.setVisible(True)

    def stop_and_hide(self):
        if self._player_ok:
            self.player.stop()
        self.setVisible(False)
        self._current_file = None

    # ── Internal slots ────────────────────────────────────────────────────────

    def _toggle_play(self):
        if not self._player_ok:
            return
        from PyQt6.QtMultimedia import QMediaPlayer
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self._play_btn.setText("▶")
        else:
            self.player.play()
            self._play_btn.setText("⏸")

    def _stop(self):
        if self._player_ok:
            self.player.stop()
        self._play_btn.setText("▶")

    def _seek(self, value):
        if not self._player_ok:
            return
        dur = self.player.duration()
        if dur > 0:
            self.player.setPosition(int(value * dur / 1000))

    def _set_volume(self, value):
        if self._player_ok:
            self._audio.setVolume(value / 100.0)

    def _update_progress(self, position):
        if not self._player_ok:
            return
        dur = self.player.duration()
        if dur > 0:
            self._progress.setValue(int(position * 1000 / dur))

    def _on_playback_state(self, state):
        if not self._player_ok:
            return
        from PyQt6.QtMultimedia import QMediaPlayer
        if state == QMediaPlayer.PlaybackState.StoppedState:
            self._play_btn.setText("▶")

    def _on_media_status(self, status):
        if not self._player_ok:
            return
        from PyQt6.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.MediaStatus.EndOfMedia \
                and self._loop_btn.isChecked():
            self.player.setPosition(0)
            self.player.play()

    def _send_to_live(self):
        if not self._current_file or not self.parent_control:
            return
        import os
        ext = os.path.splitext(self._current_file)[1].lower()
        s = dict(self.parent_control.settings)
        if ext in (".mp4", ".mov", ".avi", ".mkv", ".webm"):
            s["bg_video"] = self._current_file
            s["bg_image"] = ""
        else:
            s["bg_image"] = self._current_file
            s["bg_video"] = ""
        for dw in getattr(self.parent_control, "display_windows", []):
            dw.apply_settings(s)
        try:
            from toast_notifications import show_toast
            show_toast("📺 Media trimisă ca background!", "success")
        except Exception:
            pass


# ── Bible verse list with drag-MIME support ───────────────────────────────────

class _BibleVerseList(QListWidget):
    """QListWidget that encodes verse dict in a custom MIME type for drag & drop."""

    def mimeTypes(self):
        return ["application/x-glorify-verse"]

    def mimeData(self, items):
        import json as _json
        from PyQt6.QtCore import QMimeData, QByteArray
        md = QMimeData()
        if items:
            v = items[0].data(Qt.ItemDataRole.UserRole)
            if v:
                md.setData(
                    "application/x-glorify-verse",
                    QByteArray(_json.dumps(v, ensure_ascii=False).encode()),
                )
        return md


# ── Focus protection decorator ────────────────────────────────────────────────

def _protect_editor_focus(fn):
    """Decorator: if the lyrics editor had focus before the call, restore it
    afterwards via a zero-delay timer so that thumbnail clicks and slide
    rebuilds never steal the caret from the lyrics editor."""
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        has_ed = hasattr(self, 'editor') and self.editor is not None
        had_focus = has_ed and self.editor.hasFocus()
        result = fn(self, *args, **kwargs)
        if had_focus:
            QTimer.singleShot(0, self.editor.setFocus)
        return result
    return wrapper


# ── Control Window ────────────────────────────────────────────────────────────

class ControlWindow(QMainWindow):
    # Emitted (from the WS thread) when the Electron preview reports its HWND;
    # connected queued → embedding runs on the GUI thread.
    _preview_hwnd_received = pyqtSignal(int)
    # Emitted when a dynamic presentation auto-advances (follow in the UI).
    _dynamic_slide_received = pyqtSignal(int)
    # Emitted when a WYSIWYG thumbnail render is ready (req_id, data_url).
    _thumb_ready = pyqtSignal(str, str)
    # Emitted from the MIDI listener thread with a key like "note:60" / "cc:1".
    _midi_received = pyqtSignal(str)
    # YouTube audio download (background thread → GUI thread).
    _dyn_audio_ready = pyqtSignal(str)     # local audio file path
    _dyn_audio_error = pyqtSignal(str)
    _dyn_pip_done    = pyqtSignal(bool, str)
    _dyn_align_done  = pyqtSignal(object)   # list[float] start times, or None

    def __init__(self, profile_name="Default"):
        super().__init__()
        self._preview_hwnd_received.connect(self._embed_preview_hwnd)
        self._dynamic_slide_received.connect(self._on_dynamic_slide)
        self._thumb_ready.connect(self._on_thumb_ready)
        self._midi_received.connect(self._on_midi_event)
        self._midi_running = False
        self._midi_learn_cb = None
        self._midi_cc_armed = {}   # per-CC hysteresis so a fader/knob fires ONCE
                                   # per up-sweep (like a button), not continuously
        self._wysiwyg_token = 0
        self._dyn_audio_ready.connect(self._on_dyn_audio_ready)
        self._dyn_audio_error.connect(self._on_dyn_audio_error)
        self._dyn_pip_done.connect(self._on_dyn_pip_done)
        self._dyn_align_done.connect(self._on_dyn_align_done)
        self._embed_container = None
        self._dynamic_active = False
        self._profile_name = profile_name
        # Expose the active profile to the standalone bg-editor process (which
        # can't call Python) so its background picker reads the right profile dir.
        try:
            import os as _os
            _pf = _os.path.join(_os.path.expanduser("~"), "Cantio", ".active_profile")
            _os.makedirs(_os.path.dirname(_pf), exist_ok=True)
            with open(_pf, "w", encoding="utf-8") as _f:
                _f.write(profile_name)
        except Exception:
            pass
        self.settings = db.get_settings()
        self._thumb_size_key = self.settings.get("thumb_size", "S")
        self._perf_level = detect_performance()   # 'low' / 'medium' / 'high'
        self._perf_mode = (
            self.settings.get("performance_mode", "false") == "true"
        )
        self.display_windows: list = []
        self.current_slides: list[str] = []
        self.current_slide_idx = -1
        self.current_song_id = None
        self.current_song_notes = ""
        self._current_song_formatting = None   # per-song formatting dict or None
        self._editor_modified = False          # True only after explicit toolbar action
        self._thumbnails: list[SlideThumbnail] = []
        self._current_metadata: dict | None = None   # copyright / metadata overlay
        self._is_live = False
        # True once the operator has EXPLICITLY picked a slide (click/arrows/GO LIVE).
        # A freshly opened Display stays black until this is armed — but a slide
        # selected BEFORE opening still shows, because we don't reset it on open.
        self._live_armed = False
        self._slide_just_selected = False
        self._is_frozen = False
        self._logo_pixmap = None
        self._stage_editor = None
        self._slide_view_mode = "grid"
        self._pres_editor = None
        self._in_pres_mode = False
        self._pres_pixmaps = []
        self._pres_slides_data: list[dict] = []   # raw slide dicts for current presentation
        self._service_items: list[dict] = []
        self._service_path: str = ""
        self._remote_running = False
        self._live_preview_active = False
        self._service_modified = False
        self._warnings_count = 0
        self._dual_lang_active = False
        self._dual_lang_target = "en"
        self._display_configs: list[dict] = db.get_display_configs()
        self._send_target_idx: int = -1  # -1 = all, ≥0 = specific window index
        self._display_aspect: float = 16 / 9   # updated when display opens/closes

        # ── Auto-save: 2-second debounce + per-session modification tracking ──
        # _modified_songs tracks songs edited this session:
        #   {song_id: {'title': str, 'old_content': str, 'modified_at': datetime}}
        self._modified_songs: dict = {}
        self._autosave_debounce = QTimer(self)
        self._autosave_debounce.setInterval(2000)   # 2 s after last keystroke
        self._autosave_debounce.setSingleShot(True)
        self._autosave_debounce.timeout.connect(self._do_autosave)

        self.setWindowTitle(f"Cantio — {profile_name}")
        self.setMinimumSize(1240, 760)
        self.setStyleSheet(APP_STYLE)

        self._build_menubar()
        self._build_toolbar()
        self._build_ui()
        self._build_statusbar()
        self._load_library()
        self._setup_shortcuts()

        # Track focus so the selected slide shows blue (active) when the slides
        # panel drives the keyboard, and grey (inactive) once focus moves to the
        # song or service list — so the operator always knows what Page Up/Down hit.
        try:
            QApplication.instance().focusChanged.connect(self._on_focus_changed)
        except Exception:
            pass

        # Toast notification manager (must be created after window is built)
        self._toasts = ToastManager(self)
        set_global_toast_manager(self._toasts)

        # Electron display companion process (optional; falls back to PyQt DisplayWindow)
        try:
            from electron_display import ElectronDisplayManager
            self.electron_display = ElectronDisplayManager()
            self.electron_display.start()
            self.electron_display.set_preview_hwnd_callback(
                lambda h: self._preview_hwnd_received.emit(int(h)))
            self.electron_display.set_dynamic_slide_callback(
                lambda i: self._dynamic_slide_received.emit(int(i)))
            self.electron_display.set_thumb_callback(
                lambda i, u: self._thumb_ready.emit(str(i), str(u)))
        except Exception as _ederr:
            self.electron_display = None
            logger.debug("[Electron] not available: %s", _ederr)

        # Restore saved window state (geometry, splitters, last service, etc.)
        # Deferred 250 ms so the window has been shown and fully laid out
        # before setSizes() is called (QTimer(0) fires too early on first run).
        self._state_restored = False
        QTimer.singleShot(250, self._restore_window_state)
        QTimer.singleShot(300, self._init_preview_aspect)
        QTimer.singleShot(500, self._check_tutorial)
        QTimer.singleShot(800, self._check_startup_profile)
        QTimer.singleShot(1500, self._check_reindex)
        # Operator preview defaults to the embedded HD (Electron) view
        QTimer.singleShot(1800, self._auto_enable_hd_preview)

        # Live pulse timer
        self._live_timer = QTimer(self)
        self._live_timer.timeout.connect(self._pulse_live)
        self._live_pulse_state = True

        # Auto-advance timer
        self._auto_timer = QTimer(self)
        self._auto_timer.timeout.connect(self._auto_advance)

        # Per-slide timing record / playback
        self._timing_rec_active  = False
        self._timing_play_active = False
        self._timing_last_ts     = None
        self._slide_timings      = {}     # str(song_id) → [seconds, ...]
        self._rec_play_timer = QTimer(self)
        self._rec_play_timer.setSingleShot(True)
        self._rec_play_timer.timeout.connect(self._recorded_advance_tick)

        # Remote command polling timer
        self._remote_timer = QTimer(self)
        self._remote_timer.timeout.connect(self._poll_remote_commands)

        # (live-preview grab removed — renderer-based preview is used instead)

        # ── Render + Media engines ─────────────────────────────────────────────
        # RenderEngine runs on its own QThread (HighPriority) so rendering
        # never blocks the UI event loop.
        # MediaEngine decodes video in a second background thread via OpenCV.
        self.render_engine = RenderEngine(self)
        self.media_engine  = MediaEngine(self)

        _Q = Qt.ConnectionType.QueuedConnection

        # Video numpy arrays: MediaEngine → RenderEngine (queued, thread-safe)
        self.media_engine.frame_ready.connect(
            self.render_engine.set_video_frame, _Q)

        # Full frames (1920×1080) from render thread → distribute to displays
        self.render_engine.frame_ready.connect(
            self._distribute_frame, _Q)

        # Preview frames (320×180) → PreviewWidget
        # (also wired again after _build_ui creates self.preview)
        # self.render_engine.preview_ready → connected in _build_ui tail

        # Push initial settings into the render engine
        self.render_engine.set_settings(self.settings)
        # start() is a no-op in v2 (thread starts in RenderEngine.__init__)

    # ── Menu Bar ─────────────────────────────────────────────────────────────

    def _build_menubar(self):
        from PyQt6.QtWidgets import QMenuBar
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl

        _MB_STYLE = """
        QMenuBar {
            background: #181825; color: #cdd6f4;
            border-bottom: 1px solid #313244; padding: 2px;
            font-size: 12px;
        }
        QMenuBar::item { padding: 4px 12px; border-radius: 4px; }
        QMenuBar::item:selected { background: #313244; color: #cba6f7; }
        QMenu {
            background: #1e1e2e; color: #cdd6f4;
            border: 1px solid #45475a; border-radius: 6px; padding: 4px;
        }
        QMenu::item { padding: 6px 24px 6px 12px; border-radius: 4px; }
        QMenu::item:selected { background: #313244; color: #cba6f7; }
        QMenu::separator { height: 1px; background: #313244; margin: 4px 8px; }
        """

        menubar = self.menuBar()
        menubar.setStyleSheet(_MB_STYLE)

        def _act(label, slot, shortcut=None):
            a = QAction(label, self)
            if shortcut:
                a.setShortcut(shortcut)
            if slot:
                a.triggered.connect(slot)
            return a

        # ── 1. Fișier ─────────────────────────────────────────────────────────
        m_file = menubar.addMenu("📁 Fișier")
        m_file.addAction(_act("Import Cântări",      self._open_import_manager, "Ctrl+I"))
        m_file.addAction(_act("Import Biblie",       lambda: self._open_import_manager()))
        m_file.addSeparator()
        m_file.addAction(_act("Gestionare Categorii", self._open_category_manager))
        m_file.addSeparator()
        m_file.addAction(_act("Export DB",  self._export_db))
        m_file.addAction(_act("Import DB",  self._import_db))
        m_file.addAction(_act("Export PDF", self._export_pdf))
        m_file.addSeparator()
        m_file.addAction(_act("Ieșire", self.close, "Alt+F4"))

        # ── 2. Serviciu ───────────────────────────────────────────────────────
        m_svc = menubar.addMenu("📋 Serviciu")
        m_svc.addAction(_act("Serviciu Nou",       self._new_service,  "Ctrl+N"))
        m_svc.addAction(_act("Deschide Serviciu",  self._open_service, "Ctrl+O"))
        m_svc.addAction(_act("Salvează Serviciu",  self._save_service, "Ctrl+S"))
        m_svc.addAction(_act("Salvează ca…",       self._save_service_as))
        m_svc.addSeparator()
        # Recent services submenu
        self._m_recent = m_svc.addMenu("Servicii recente →")
        self._refresh_recent_menu()
        m_svc.addSeparator()
        m_svc.addAction(_act("Închide Serviciu", self._clear_service))

        # ── 3. Remote ─────────────────────────────────────────────────────────
        m_rem = menubar.addMenu("📱 Remote")
        self._act_remote_start = _act("Pornește Server Remote", self._toggle_remote)
        self._act_remote_stop  = _act("Oprește Server Remote",  self._toggle_remote)
        m_rem.addAction(self._act_remote_start)
        m_rem.addAction(self._act_remote_stop)
        m_rem.addSeparator()
        m_rem.addAction(_act("Afișează QR Code",  self._show_qr_code))
        m_rem.addAction(_act("Copiază adresa IP", self._copy_ip))

        # ── 4. Live ───────────────────────────────────────────────────────────
        m_live = menubar.addMenu("📺 Live")
        m_live.addAction(_act("GO LIVE",        self._go_live,      "Space"))
        m_live.addAction(_act("Ecran Negru",    self._black_screen, "Escape"))
        m_live.addSeparator()
        m_live.addAction(_act("Deschide Display",  self._open_display))
        m_live.addAction(_act("Închide Display",   self._close_display))
        m_live.addSeparator()
        m_live.addAction(_act("Deschide Stage Monitor", self._open_stage_monitor, "Ctrl+Shift+P"))
        m_live.addAction(_act("Închide Stage Monitor",  self._close_stage_monitor))
        m_live.addSeparator()
        m_live.addAction(_act("Mod Transparent",  self._toggle_transparent,  "Ctrl+Shift+T"))
        m_live.addAction(_act("Virtual Camera",   self._toggle_virtual_cam))

        # ── 5. Ajutor ─────────────────────────────────────────────────────────
        m_help = menubar.addMenu("❓ Ajutor")
        m_help.addAction(_act("Despre Cantio",    self._show_about))
        m_help.addAction(_act("Scurtături Tastatură", self._show_shortcuts))
        m_help.addAction(_act("Tutorial",             self._show_tutorial))
        m_help.addSeparator()
        m_help.addAction(_act("Ajutor Online", lambda: QDesktopServices.openUrl(
            QUrl("https://cantioapp.com/helpdesk")
        )))

    def _refresh_recent_menu(self):
        """Populate the Recent Services submenu."""
        if not hasattr(self, '_m_recent'):
            return
        self._m_recent.clear()
        try:
            cache = db.get_cache()
            recent = cache.get("recent_services", [])
            for path in recent[:5]:
                p = path
                self._m_recent.addAction(
                    QAction(os.path.basename(p), self,
                            triggered=lambda checked=False, _p=p: self._open_service_path(_p))
                )
            if not recent:
                a = QAction("(niciun serviciu recent)", self)
                a.setEnabled(False)
                self._m_recent.addAction(a)
        except Exception:
            pass

    def _save_service_as(self):
        """Save current service with a new filename."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvează Serviciu ca…", "", "Cantio Service (*.gps)"
        )
        if path:
            self._service_path = path
            self._save_service()

    def _show_qr_code(self):
        """Show QR code with remote server IP."""
        try:
            import remote_server as rs
            ip = rs.get_local_ip()
            port = getattr(rs, 'PORT', 5000)
            url = f"http://{ip}:{port}"
            try:
                import qrcode
                from PyQt6.QtGui import QPixmap as QP
                img = qrcode.make(url)
                import tempfile, os as _os
                tmp = tempfile.mktemp(suffix=".png")
                img.save(tmp)
                pix = QP(tmp)
                _os.unlink(tmp)
                dlg = QDialog(self)
                dlg.setWindowTitle("QR Code Remote")
                dlg.setFixedSize(280, 320)
                v = QVBoxLayout(dlg)
                lbl = QLabel()
                lbl.setPixmap(pix.scaledToWidth(240, Qt.TransformationMode.SmoothTransformation))
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                v.addWidget(lbl)
                v.addWidget(QLabel(url, alignment=Qt.AlignmentFlag.AlignCenter))
                dlg.exec()
            except ImportError:
                QMessageBox.information(self, "QR Code", f"Server la:\n{url}\n\n(instalează qrcode pentru cod QR)")
        except Exception as e:
            QMessageBox.warning(self, "QR Code", f"Serverul remote nu rulează.\n{e}")

    def _copy_ip(self):
        try:
            import remote_server as rs
            ip = rs.get_local_ip()
            port = getattr(rs, 'PORT', 5000)
            QApplication.clipboard().setText(f"http://{ip}:{port}")
            try:
                from toast_notifications import show_toast
                show_toast(f"📋 Copiat: http://{ip}:{port}", "success")
            except Exception:
                pass
        except Exception as e:
            QMessageBox.warning(self, "IP", f"Nu s-a putut obține IP-ul.\n{e}")

    def _open_service_path(self, path: str):
        if os.path.exists(path):
            self._service_path = path
            try:
                items = sm.load_service(path)
                self._on_service_loaded(items)
            except Exception as e:
                QMessageBox.warning(self, "Eroare", f"Nu s-a putut deschide serviciul:\n{e}")

    def _close_display(self):
        for dw in list(self.display_windows):
            dw.close()

    def _close_stage_monitor(self):
        if self._stage_editor:
            try:
                self._stage_editor.close()
            except Exception:
                pass

    def _show_tutorial(self):
        """Launch the interactive tutorial overlay."""
        if not hasattr(self, '_interactive_tutorial') or self._interactive_tutorial is None:
            from tutorial_dialog import InteractiveTutorial
            self._interactive_tutorial = InteractiveTutorial(self)
        self._interactive_tutorial.start()

    def _check_tutorial(self):
        """Show tutorial on first launch (after a short delay so UI is fully painted)."""
        try:
            cache = db.get_cache()
            if not cache.get("tutorial_shown", False):
                QTimer.singleShot(800, self._show_tutorial)
        except Exception as e:
            print(f"[TUTORIAL] check failed: {e}")

    def _check_reindex(self):
        """
        If FTS5 index is out-of-sync with songs table, notify the user once
        and trigger a background reindex.
        """
        try:
            if not db.needs_reindex():
                return
            cache = db.get_cache()
            if cache.get("reindex_notified"):
                # Already notified — still reindex silently in background
                import threading
                threading.Thread(target=db.reindex_fts5, daemon=True).start()
                return
            # First time: notify + reindex
            cache["reindex_notified"] = True
            db.save_cache(cache)
            try:
                from toast_notifications import show_toast
                show_toast(
                    "🔄 Baza de date actualizată. Reindexare automată…",
                    "info",
                )
            except Exception:
                pass
            import threading
            threading.Thread(target=db.reindex_fts5, daemon=True).start()
        except Exception as e:
            print(f"[REINDEX] check failed: {e}")

    # ── Toolbar ───────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        tb = QToolBar("Main", self)
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        self.addToolBar(tb)

        _S_NORMAL = (
            "QPushButton { background: #1a1a1a; color: #cccccc; border: 1px solid #232323; "
            "border-radius: 4px; padding: 5px 11px; }"
            "QPushButton:hover { background: #222222; color: #e0e0e0; border-color: #333; }"
        )

        def _tb_btn(label, slot, tip="", style=None):
            b = QPushButton(label)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            b.setStyleSheet(style or _S_NORMAL)
            tb.addWidget(b)
            return b

        # ── Logo / Name ────────────────────────────────────────────────────
        name_lbl = QLabel("  Cantio  ")
        name_lbl.setStyleSheet(
            "color: #5294e2; font-weight: 700; font-size: 14px; "
            "letter-spacing: 1px; padding: 0 6px;"
        )
        tb.addWidget(name_lbl)

        self._profile_btn = QPushButton(f"👤 {self._profile_name}")
        self._profile_btn.setToolTip("Schimbă profilul activ")
        self._profile_btn.clicked.connect(self._change_profile)
        self._profile_btn.setStyleSheet(
            "QPushButton { background: #1a2a1a; color: #88cc88; border: 1px solid #224422; "
            "border-radius: 4px; padding: 5px 10px; font-size: 11px; }"
            "QPushButton:hover { background: #1e341e; border-color: #4a8a4a; }"
        )
        tb.addWidget(self._profile_btn)
        tb.addSeparator()

        # ── New Song ──────────────────────────────────────────────────────
        _tb_btn(f"➕ {t('new_song')}", self._new_song, f"{t('new_song')}")

        # ── Dynamic presentation generator (audio-reactive) ────────────────
        _tb_btn(t("btn_dynamic"), self._open_dynamic_generator,
                "Generează o prezentare dinamică dintr-un MP3 (fundal reactiv la muzică) — BETA",
                style=("QPushButton { background: #2a1a3a; color: #c89bf0; "
                       "border: 1px solid #3a2a5a; border-radius: 4px; padding: 5px 11px; }"
                       "QPushButton:hover { background: #34204a; color: #e0c8ff; }"))
        tb.addSeparator()

        # ── Look (active theme, switchable live like ProPresenter) ─────────
        look_lbl = QLabel("  🎨")
        look_lbl.setToolTip("Look — tema activă aplicată live pe tot")
        look_lbl.setStyleSheet("font-size: 13px;")
        tb.addWidget(look_lbl)
        self._look_combo = QComboBox()
        self._look_combo.setToolTip("Look — schimbă tema activă live, cu un click")
        self._look_combo.setStyleSheet(
            "QComboBox { background:#151515; color:#c89bf0; border:1px solid #3a2a5a; "
            "border-radius:4px; padding:4px 8px; font-size:11px; min-width:120px; }"
            "QComboBox::drop-down { border:none; }")
        self._look_combo.currentIndexChanged.connect(self._on_look_selected)
        tb.addWidget(self._look_combo)
        QTimer.singleShot(600, self._refresh_look_combo)

        # ── Expandable spacer — pushes Display / Stage / Settings right ───
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        # ── Display / Stage ────────────────────────────────────────────────
        self._display_btn = QPushButton(f"📺 {t('display')}")
        self._display_btn.setToolTip(f"{t('display')}  [Ctrl+P]")
        self._display_btn.clicked.connect(self._toggle_display)
        self._display_btn.setStyleSheet(self._btn_style_closed())
        tb.addWidget(self._display_btn)

        self._stage_btn = QPushButton(f"🎭 {t('stage')}")
        self._stage_btn.setToolTip(f"{t('stage_monitor')}  [Ctrl+Shift+P]  •  Click dreapta = Stage Editor")
        self._stage_btn.clicked.connect(self._open_stage_monitor)
        self._stage_btn.setStyleSheet(self._btn_style_closed())
        self._stage_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._stage_btn.customContextMenuRequested.connect(self._open_stage_editor)
        tb.addWidget(self._stage_btn)
        tb.addSeparator()

        # ── Send-to target selector ────────────────────────────────────────
        send_lbl = QLabel(f"  {t('send_to')}")
        send_lbl.setStyleSheet("color: #555; font-size: 11px;")
        tb.addWidget(send_lbl)
        self._send_combo = QComboBox()
        self._send_combo.setToolTip(t("send_to"))
        self._send_combo.setStyleSheet(
            "QComboBox { background:#151515; color:#aaa; border:1px solid #252525; "
            "border-radius:4px; padding:4px 8px; font-size:11px; min-width:130px; }"
            "QComboBox::drop-down { border:none; }"
        )
        self._send_combo.addItem(t("all_displays"), -1)
        self._send_combo.currentIndexChanged.connect(self._on_send_target_changed)
        tb.addWidget(self._send_combo)
        tb.addSeparator()

        # ── Settings (stays in toolbar for quick access) ───────────────────
        _tb_btn(f"⚙ {t('settings')}", self._open_settings, t("settings"))

        # Keep stub references for code that checks these attrs
        self._transparent_btn = QPushButton()
        self._transparent_btn.setVisible(False)
        self._vcam_btn = QPushButton()
        self._vcam_btn.setVisible(False)
        self._remote_btn = QPushButton()
        self._remote_btn.setVisible(False)

    # ── Main UI ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        self._main_splitter = splitter
        root.addWidget(splitter)

        left_frame = QFrame()
        left_frame.setObjectName("side_panel")
        # No max width + a low min → the operator can drag the splitter freely.
        left_frame.setMinimumWidth(150)
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        left_layout.addWidget(self._build_left_panel())
        splitter.addWidget(left_frame)

        center_frame = QFrame()
        center_frame.setObjectName("center_panel")
        center_layout = QVBoxLayout(center_frame)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        center_layout.addWidget(self._build_center_panel())
        splitter.addWidget(center_frame)

        right_frame = QFrame()
        right_frame.setObjectName("right_panel")
        # No max width + a low min → the operator can drag the splitter freely.
        right_frame.setMinimumWidth(160)
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self._build_right_panel())
        splitter.addWidget(right_frame)

        splitter.setSizes([265, 640, 305])

    # ── Left Panel ────────────────────────────────────────────────────────────

    def _build_left_panel(self):
        w = QWidget()
        w.setStyleSheet("background: #131313;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Vertical splitter: SERVICIU (~35%) on top, Tabs (~65%) on bottom
        self._left_splitter = QSplitter(Qt.Orientation.Vertical)
        self._left_splitter.setHandleWidth(3)

        # Top: Service panel
        self._left_splitter.addWidget(self._build_service_panel())

        # Bottom: Songs / Bible / Slides tabs
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(self._build_library_tab(), t("songs"))
        tabs.addTab(self._build_bible_tab(), t("bible"))
        tabs.addTab(self._build_presentations_tab(), f"📊 {t('slides')}")
        self._left_tabs = tabs
        self._left_splitter.addWidget(tabs)
        # Tab sync: selecting Bible in sidebar → switch center to Control Bible
        self._left_tabs.currentChanged.connect(self._on_left_tab_changed)

        # Default proportions: ~35% service / ~65% tabs
        self._left_splitter.setSizes([230, 430])

        layout.addWidget(self._left_splitter)
        return w

    def _build_library_tab(self):
        w = QWidget()
        w.setStyleSheet("background: #131313;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)

        # Category filter
        self.cat_combo = QComboBox()
        self.cat_combo.setStyleSheet(
            "QComboBox { background: #1a1a1a; border: 1px solid #222; "
            "border-radius: 4px; padding: 4px 8px; color: #aaa; font-size: 11px; }"
            "QComboBox:focus { border-color: #5294e2; }"
        )
        self.cat_combo.currentIndexChanged.connect(self._on_cat_filter)
        self._refresh_categories()
        layout.addWidget(self.cat_combo)

        # Search with debounce — avoids querying DB on every keystroke
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(t("search_songs"))
        self.search_edit.setStyleSheet(
            "QLineEdit { background: #1a1a1a; border: 1px solid #222; "
            "border-radius: 4px; padding: 6px 10px; color: #e0e0e0; }"
            "QLineEdit:focus { border-color: #5294e2; }"
        )
        # Debounce wired inside SongsModel._load_timer (250ms)
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        srow = QHBoxLayout(); srow.setSpacing(4)
        srow.addWidget(self.search_edit, 1)
        self._smart_btn = QPushButton("⚡ Smart")
        self._smart_btn.setToolTip("Smart Playlists — filtre salvate (categorie + căutare)")
        self._smart_btn.setStyleSheet(
            "QPushButton { background:#1a1a24; color:#c89bf0; border:1px solid #2e2440; "
            "border-radius:4px; padding:6px 10px; font-size:11px; }"
            "QPushButton:hover { background:#241a34; color:#e0c8ff; }")
        self._smart_btn.clicked.connect(self._show_smart_menu)
        srow.addWidget(self._smart_btn)
        layout.addLayout(srow)

        # Paginated virtual list — only (id, title, author) in RAM; no slides
        self.songs_model = SongsModel()
        self.song_list = QListView()
        self.song_list.setModel(self.songs_model)
        self.song_list.setItemDelegate(SongDelegate())
        self.song_list.setUniformItemSizes(False)
        from PyQt6.QtWidgets import QAbstractItemView
        self.song_list.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.song_list.setStyleSheet(
            "QListView { background: #131313; border: none; outline: none; }"
            "QListView::item { border-radius: 2px; }"
        )
        self.song_list.doubleClicked.connect(self._load_song_by_index)
        self.song_list.clicked.connect(self._preview_song_by_index)
        # Right-click context menu (move to category, etc.)
        self.song_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.song_list.customContextMenuRequested.connect(self._song_context_menu)
        # Drag to service list
        from PyQt6.QtWidgets import QAbstractItemView
        self.song_list.setDragEnabled(True)
        self.song_list.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.song_list.setDefaultDropAction(Qt.DropAction.CopyAction)
        # Infinite scroll — load next page when near the bottom
        self.song_list.verticalScrollBar().valueChanged.connect(self._on_song_list_scroll)
        layout.addWidget(self.song_list, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        edit_btn = QPushButton(t("edit"))
        edit_btn.setStyleSheet(
            "QPushButton { background: #1c1c1c; color: #aaa; border: 1px solid #252525; "
            "border-radius: 4px; padding: 5px 10px; font-size: 11px; }"
            "QPushButton:hover { background: #222; color: #e0e0e0; }"
        )
        edit_btn.clicked.connect(self._edit_song)
        del_btn = QPushButton(t("delete"))
        del_btn.setStyleSheet(
            "QPushButton { background: #1c1c1c; color: #f44336; border: 1px solid #221414; "
            "border-radius: 4px; padding: 5px 10px; font-size: 11px; }"
            "QPushButton:hover { background: #221414; border-color: #f44336; }"
        )
        del_btn.clicked.connect(self._delete_song)
        add_pl_btn = QPushButton(f"+ {t('service')}")
        add_pl_btn.setStyleSheet(
            "QPushButton { background: #18283a; color: #5294e2; border: 1px solid #1c3a5a; "
            "border-radius: 4px; padding: 5px 10px; font-size: 11px; }"
            "QPushButton:hover { background: #1c3a5a; }"
        )
        add_pl_btn.clicked.connect(self._add_to_playlist)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(del_btn)
        btn_row.addWidget(add_pl_btn)
        layout.addLayout(btn_row)
        return w

    def _refresh_categories(self):
        self.cat_combo.blockSignals(True)
        self.cat_combo.clear()
        for cat in db.get_categories():
            self.cat_combo.addItem(cat)
        self.cat_combo.blockSignals(False)

    def _build_bible_tab(self):
        w = QWidget()
        w.setStyleSheet("background: #131313;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        if not db.has_bible():
            lbl = QLabel("No Bible loaded.\n\nImport a .bib file via ⬆ Import.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #444444; padding: 30px; font-size: 12px; line-height: 1.6;")
            layout.addWidget(lbl)
            self.bible_placeholder = lbl
            self.book_combo = QComboBox()
            self.chapter_combo = QComboBox()
            self.verse_combo = QComboBox()
            self.verse_list = QListWidget()
            self.book_combo.hide()
            self.chapter_combo.hide()
            self.verse_combo.hide()
            self.verse_list.hide()
            # Bible search (hidden until bible loaded)
            self.bible_search_edit = QLineEdit()
            self.bible_search_edit.hide()
            self.bible_search_results = QListWidget()
            self.bible_search_results.hide()
        else:
            self.bible_placeholder = None
            self._init_bible_controls(layout)
        return w

    def _init_bible_controls(self, layout=None):
        if layout is None:
            return

        self.book_combo = QComboBox()
        self.chapter_combo = QComboBox()
        # verse_list kept as hidden stub so legacy helper methods don't crash
        self.verse_list = _BibleVerseList()
        self.verse_list.hide()

        combo_style = (
            "QComboBox { background: #1a1a1a; border: 1px solid #222; "
            "border-radius: 4px; padding: 5px 8px; color: #e0e0e0; }"
            "QComboBox:focus { border-color: #5294e2; }"
            "QComboBox QAbstractItemView { background: #222; color: #e0e0e0; "
            "selection-background-color: #1c3a5a; border: 1px solid #2e2e2e; }"
        )
        self.book_combo.setStyleSheet(combo_style)
        self.chapter_combo.setStyleSheet(combo_style)

        books = db.get_bible_books()
        for b in books:
            self.book_combo.addItem(b["name"], b["id"])

        self.book_combo.currentIndexChanged.connect(self._load_chapters)
        self.chapter_combo.currentIndexChanged.connect(self._load_verses)

        # ── Quick reference bar (e.g. "Ioan 3:16", "Ps 23") ─────────────────
        quick_ref_lbl = QLabel(t("quick_reference").upper())
        quick_ref_lbl.setObjectName("section_lbl")
        layout.addWidget(quick_ref_lbl)

        quick_row = QHBoxLayout()
        quick_row.setSpacing(4)
        self.bible_quick_edit = QLineEdit()
        self.bible_quick_edit.setPlaceholderText("Ex: In 3:16  sau  Ps 23  sau  1Cor 13:4…")
        self.bible_quick_edit.setStyleSheet(
            "QLineEdit { background: #1a1a2a; border: 1px solid #2a2a4a; "
            "border-radius: 4px; padding: 5px 8px; color: #e0e0e0; font-size: 11px; }"
            "QLineEdit:focus { border-color: #5294e2; }"
        )
        self.bible_quick_edit.returnPressed.connect(self._bible_quick_search)
        quick_row.addWidget(self.bible_quick_edit, 1)
        quick_go_btn = QPushButton("↗")
        quick_go_btn.setFixedWidth(28)
        quick_go_btn.setToolTip("Navighează la referință")
        quick_go_btn.setStyleSheet(
            "QPushButton { background: #1a2a3a; color: #5294e2; border: 1px solid #1c3a5a; "
            "border-radius: 4px; padding: 4px; font-size: 14px; }"
            "QPushButton:hover { background: #1c3a5a; }"
        )
        quick_go_btn.clicked.connect(self._bible_quick_search)
        quick_row.addWidget(quick_go_btn)
        layout.addLayout(quick_row)

        # Bible keyword search
        search_lbl = QLabel(t("search_bible").upper())
        search_lbl.setObjectName("section_lbl")
        layout.addWidget(search_lbl)

        bible_search_row = QHBoxLayout()
        self.bible_search_edit = QLineEdit()
        self.bible_search_edit.setPlaceholderText("Search keyword in all verses…")
        self.bible_search_edit.returnPressed.connect(self._search_bible)
        self.bible_search_edit.setStyleSheet(
            "QLineEdit { background: #1a1a1a; border: 1px solid #222; "
            "border-radius: 4px; padding: 5px 8px; color: #e0e0e0; font-size: 11px; }"
            "QLineEdit:focus { border-color: #5294e2; }"
        )
        bible_search_btn = QPushButton("🔍")
        bible_search_btn.setFixedWidth(32)
        bible_search_btn.setStyleSheet(
            "QPushButton { background: #1a2a3a; color: #5294e2; border: 1px solid #1c3a5a; "
            "border-radius: 4px; padding: 5px; font-size: 13px; }"
            "QPushButton:hover { background: #1c3a5a; }"
        )
        bible_search_btn.clicked.connect(self._search_bible)
        bible_search_row.addWidget(self.bible_search_edit)
        bible_search_row.addWidget(bible_search_btn)
        layout.addLayout(bible_search_row)

        self.bible_search_results = QListWidget()
        self.bible_search_results.setFixedHeight(100)
        self.bible_search_results.hide()
        self.bible_search_results.setStyleSheet(
            "QListWidget { background: #0f1f0f; border: 1px solid #1a3a1a; border-radius: 3px; }"
            "QListWidget::item { padding: 4px 8px; color: #88cc88; font-size: 11px; }"
            "QListWidget::item:hover { background: #1a2a1a; }"
            "QListWidget::item:selected { background: #1c3a1c; }"
        )
        self.bible_search_results.itemDoubleClicked.connect(self._send_search_verse)
        self.bible_search_results.itemClicked.connect(self._preview_search_verse)
        layout.addWidget(self.bible_search_results)

        book_lbl = QLabel("CARTE")
        book_lbl.setObjectName("section_lbl")
        layout.addWidget(book_lbl)
        layout.addWidget(self.book_combo)

        chap_lbl = QLabel("CAPITOL")
        chap_lbl.setObjectName("section_lbl")
        layout.addWidget(chap_lbl)
        layout.addWidget(self.chapter_combo)

        # ── Verse selector ────────────────────────────────────────────────────
        verset_lbl = QLabel("VERSET")
        verset_lbl.setObjectName("section_lbl")
        layout.addWidget(verset_lbl)

        self.verse_combo = QComboBox()
        self.verse_combo.setStyleSheet(combo_style)
        self.verse_combo.addItem("— Selectează capitol mai întâi —", None)
        self.verse_combo.currentIndexChanged.connect(self._on_verse_combo_selected)
        layout.addWidget(self.verse_combo)

        hint_lbl = QLabel("→ Click pe verset pentru a-l trimite la Control Bible")
        hint_lbl.setStyleSheet("color:#444; font-size:10px; padding:4px;")
        hint_lbl.setWordWrap(True)
        layout.addWidget(hint_lbl)

        layout.addStretch(1)

        self._load_chapters()

    def _build_playlist_tab(self):
        w = QWidget()
        w.setStyleSheet("background: #131313;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        hdr = QLabel(t("service_order"))
        hdr.setObjectName("section_lbl")
        layout.addWidget(hdr)

        self.playlist_list = QListWidget()
        self.playlist_list.setStyleSheet(
            "QListWidget { background: #131313; border: none; }"
            "QListWidget::item { padding: 9px 10px; border-radius: 4px; "
            "margin: 1px 2px; color: #cccccc; }"
            "QListWidget::item:hover { background: #1c1c1c; }"
            "QListWidget::item:selected { background: #1c3a5a; color: #e0e0e0; }"
        )
        self.playlist_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.playlist_list.itemDoubleClicked.connect(self._load_playlist_item)
        layout.addWidget(self.playlist_list, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        rm_btn = QPushButton(t("remove"))
        rm_btn.setStyleSheet(
            "QPushButton { background: #1c1c1c; color: #f44336; border: 1px solid #221414; "
            "border-radius: 4px; padding: 5px 10px; font-size: 11px; }"
            "QPushButton:hover { background: #221414; border-color: #f44336; }"
        )
        rm_btn.clicked.connect(self._remove_from_playlist)
        clear_btn = QPushButton(t("clear_all"))
        clear_btn.setStyleSheet(
            "QPushButton { background: #1c1c1c; color: #888; border: 1px solid #242424; "
            "border-radius: 4px; padding: 5px 10px; font-size: 11px; }"
            "QPushButton:hover { background: #222; color: #e0e0e0; }"
        )
        clear_btn.clicked.connect(self._clear_playlist)
        btn_row.addWidget(rm_btn)
        btn_row.addWidget(clear_btn)
        layout.addLayout(btn_row)
        return w

    # ── Center Panel ──────────────────────────────────────────────────────────

    def _build_center_panel(self):
        w = QWidget()
        root_layout = QVBoxLayout(w)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Song slides + editor (fills the entire center panel) ─────────
        bottom_w = QWidget()
        layout = QVBoxLayout(bottom_w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Song title bar
        title_bar = QWidget()
        title_bar.setFixedHeight(48)
        title_bar.setStyleSheet("background: #131313; border-bottom: 1px solid #1e1e1e;")
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(12, 6, 12, 6)
        tb_layout.setSpacing(8)

        self.song_title_edit = QLineEdit()
        self.song_title_edit.setPlaceholderText(t("song_title_placeholder"))
        self.song_title_edit.setStyleSheet(
            "QLineEdit { background: #1a1a1a; border: 1px solid #222; "
            "border-radius: 4px; padding: 5px 10px; color: #e0e0e0; "
            "font-size: 13px; font-weight: 500; }"
            "QLineEdit:focus { border-color: #5294e2; }"
        )
        tb_layout.addWidget(self.song_title_edit, 1)

        self.save_btn = QPushButton(t("save"))
        self.save_btn.setStyleSheet(
            "QPushButton { background: #18283a; color: #5294e2; border: 1px solid #1c3a5a; "
            "border-radius: 4px; padding: 6px 16px; font-weight: 600; }"
            "QPushButton:hover { background: #1c3a5a; color: #e0e0e0; }"
        )
        self.save_btn.clicked.connect(self._save_current_song)
        tb_layout.addWidget(self.save_btn)

        self.new_slide_btn = QPushButton(t("new_slide"))
        self.new_slide_btn.setStyleSheet(
            "QPushButton { background: #1c1c1c; color: #888; border: 1px solid #242424; "
            "border-radius: 4px; padding: 6px 12px; font-size: 11px; }"
            "QPushButton:hover { background: #222; color: #e0e0e0; }"
        )
        self.new_slide_btn.clicked.connect(self._new_slide)
        tb_layout.addWidget(self.new_slide_btn)

        self.adv_editor_btn = QPushButton("🎬 Editor avansat")
        self.adv_editor_btn.setToolTip(
            "Deschide editorul vizual avansat (Electron) pentru această cântare")
        self.adv_editor_btn.setStyleSheet(
            "QPushButton { background: #2a1a3a; color: #c89bf0; border: 1px solid #3a2a5a; "
            "border-radius: 4px; padding: 6px 12px; font-size: 11px; }"
            "QPushButton:hover { background: #3a2a5a; color: #fff; }"
        )
        self.adv_editor_btn.clicked.connect(self._open_advanced_editor)
        tb_layout.addWidget(self.adv_editor_btn)
        layout.addWidget(title_bar)

        # Operator notes bar (hidden by default)
        self.notes_bar = QWidget()
        self.notes_bar.setStyleSheet(
            "background: #1a1a0a; border-bottom: 1px solid #3a3010;"
        )
        notes_bar_layout = QHBoxLayout(self.notes_bar)
        notes_bar_layout.setContentsMargins(12, 4, 12, 4)
        notes_bar_layout.setSpacing(8)
        notes_icon = QLabel("📝")
        notes_icon.setFixedWidth(20)
        notes_bar_layout.addWidget(notes_icon)
        notes_hdr = QLabel("OPERATOR NOTES")
        notes_hdr.setObjectName("notes_lbl")
        notes_hdr.setFixedWidth(130)
        notes_bar_layout.addWidget(notes_hdr)
        self.notes_display = QLabel()
        self.notes_display.setStyleSheet("color: #ccaa44; font-size: 11px;")
        self.notes_display.setWordWrap(True)
        notes_bar_layout.addWidget(self.notes_display, 1)
        self.notes_bar.hide()
        layout.addWidget(self.notes_bar)

        # Slides count bar
        slides_area_lbl = QWidget()
        slides_area_lbl.setFixedHeight(28)
        slides_area_lbl.setStyleSheet("background: #161616; border-bottom: 1px solid #1e1e1e;")
        sal_layout = QHBoxLayout(slides_area_lbl)
        sal_layout.setContentsMargins(12, 4, 12, 4)
        self._slide_count_lbl = QLabel(t("no_slides"))
        self._slide_count_lbl.setObjectName("section_lbl")
        sal_layout.addWidget(self._slide_count_lbl)
        sal_layout.addStretch()

        # Auto-advance toggle in slides bar
        self._auto_lbl = QLabel()
        self._auto_lbl.setStyleSheet("color: #555; font-size: 10px;")
        sal_layout.addWidget(self._auto_lbl)

        # Thumbnail size controls
        _size_btn_style = (
            "QPushButton { background: #1c1c1c; color: #888; border: 1px solid #262626; "
            "border-radius: 3px; font-size: 12px; font-weight: 700; padding: 0; }"
            "QPushButton:hover { background: #252525; color: #e0e0e0; }"
            "QPushButton:pressed { background: #1a2a3a; color: #5294e2; }"
        )
        sal_layout.addWidget(QLabel("▣ "))
        self._thumb_minus_btn = QPushButton("−")
        self._thumb_minus_btn.setFixedSize(20, 20)
        self._thumb_minus_btn.setStyleSheet(_size_btn_style)
        self._thumb_minus_btn.setToolTip(t("thumb_shrink"))
        self._thumb_minus_btn.clicked.connect(lambda: self._change_thumb_size(-1))
        sal_layout.addWidget(self._thumb_minus_btn)

        self._thumb_size_lbl = QLabel(self._thumb_size_key)
        self._thumb_size_lbl.setFixedWidth(26)
        self._thumb_size_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb_size_lbl.setStyleSheet("color: #5294e2; font-size: 10px; font-weight: 700;")
        sal_layout.addWidget(self._thumb_size_lbl)

        self._thumb_plus_btn = QPushButton("+")
        self._thumb_plus_btn.setFixedSize(20, 20)
        self._thumb_plus_btn.setStyleSheet(_size_btn_style)
        self._thumb_plus_btn.setToolTip(t("thumb_grow"))
        self._thumb_plus_btn.clicked.connect(lambda: self._change_thumb_size(+1))
        sal_layout.addWidget(self._thumb_plus_btn)

        # View toggle
        self._view_toggle_btn = QPushButton("☰")
        self._view_toggle_btn.setToolTip("Toggle grid / list view")
        self._view_toggle_btn.setFixedSize(24, 20)
        self._view_toggle_btn.setStyleSheet(
            "QPushButton { background: #1c1c1c; color: #666; border: 1px solid #222; "
            "border-radius: 3px; font-size: 12px; padding: 0; }"
            "QPushButton:hover { color: #e0e0e0; }"
        )
        self._view_toggle_btn.clicked.connect(self._toggle_slide_view)
        sal_layout.addWidget(self._view_toggle_btn)

        # Reorder button
        self._reorder_btn = QPushButton("⇅")
        self._reorder_btn.setToolTip("Reordonează slide-urile (drag & drop)")
        self._reorder_btn.setFixedSize(24, 20)
        self._reorder_btn.setStyleSheet(
            "QPushButton { background: #1c1c1c; color: #666; border: 1px solid #222; "
            "border-radius: 3px; font-size: 12px; padding: 0; }"
            "QPushButton:hover { color: #e0e0e0; }"
        )
        self._reorder_btn.clicked.connect(self._reorder_slides_dialog)
        sal_layout.addWidget(self._reorder_btn)

        # Transparent thumbnails toggle (preview-only, does NOT affect live)
        self._thumbs_transparent = False
        self._thumb_transp_btn = QPushButton("◧")
        self._thumb_transp_btn.setToolTip(
            "Fundal thumbnail în carouri (transparență) — doar aici, nu afectează live-ul")
        self._thumb_transp_btn.setCheckable(True)
        self._thumb_transp_btn.setFixedSize(24, 20)
        self._thumb_transp_btn.setStyleSheet(
            "QPushButton { background: #1c1c1c; color: #666; border: 1px solid #222; "
            "border-radius: 3px; font-size: 12px; padding: 0; }"
            "QPushButton:hover { color: #e0e0e0; }"
            "QPushButton:checked { background: #18283a; color: #5294e2; border-color: #1c3a5a; }"
        )
        self._thumb_transp_btn.clicked.connect(self._toggle_thumb_transparency)
        sal_layout.addWidget(self._thumb_transp_btn)

        # Arrange slides on rows by label (Strofa 1, Strofa 2…) — keeps order
        self._slides_by_label = False
        self._slides_label_btn = QPushButton("🏷")
        self._slides_label_btn.setToolTip(
            "Aranjează slide-urile pe rânduri după etichetă (nu schimbă ordinea)")
        self._slides_label_btn.setCheckable(True)
        self._slides_label_btn.setFixedSize(24, 20)
        self._slides_label_btn.setStyleSheet(
            "QPushButton { background: #1c1c1c; color: #666; border: 1px solid #222; "
            "border-radius: 3px; font-size: 11px; padding: 0; }"
            "QPushButton:hover { color: #e0e0e0; }"
            "QPushButton:checked { background: #18283a; color: #5294e2; border-color: #1c3a5a; }"
        )
        self._slides_label_btn.clicked.connect(self._toggle_slides_by_label)
        sal_layout.addWidget(self._slides_label_btn)

        # ── Arrangement selector (Vers/Refren sequence, like ProPresenter) ─────
        self._active_arrangement = None
        self._song_base_slides = []
        self._applying_arrangement = False
        self._arrangement_combo = QComboBox()
        self._arrangement_combo.setToolTip(
            "Aranjament — ordinea strofelor (Vers/Refren…). Schimbă rapid ordinea live.")
        self._arrangement_combo.setFixedHeight(20)
        self._arrangement_combo.setStyleSheet(
            "QComboBox { background:#151515; color:#aaa; border:1px solid #252525; "
            "border-radius:3px; padding:1px 6px; font-size:10px; min-width:96px; }"
            "QComboBox::drop-down { border:none; }")
        self._arrangement_combo.addItem("Aranjament: Original")
        self._arrangement_combo.currentIndexChanged.connect(self._on_arrangement_selected)
        sal_layout.addWidget(self._arrangement_combo)

        self._arrangement_edit_btn = QPushButton("✎")
        self._arrangement_edit_btn.setToolTip("Editează aranjamentele (secvențe de strofe)")
        self._arrangement_edit_btn.setFixedSize(24, 20)
        self._arrangement_edit_btn.setStyleSheet(
            "QPushButton { background: #1c1c1c; color: #666; border: 1px solid #222; "
            "border-radius: 3px; font-size: 11px; padding: 0; }"
            "QPushButton:hover { color: #e0e0e0; }")
        self._arrangement_edit_btn.clicked.connect(self._edit_arrangements)
        sal_layout.addWidget(self._arrangement_edit_btn)

        # Record per-slide timing (how long each slide stays)
        self._rec_btn = QPushButton("⏺")
        self._rec_btn.setToolTip("Înregistrează cât stă fiecare slide (auto-avans pe timpi)")
        self._rec_btn.setCheckable(True)
        self._rec_btn.setFixedSize(24, 20)
        self._rec_btn.setStyleSheet(
            "QPushButton { background: #1c1c1c; color: #888; border: 1px solid #222; "
            "border-radius: 3px; font-size: 11px; padding: 0; }"
            "QPushButton:hover { color: #e0e0e0; }"
            "QPushButton:checked { background: #3a1010; color: #ff5555; border-color: #5a2020; }"
        )
        self._rec_btn.clicked.connect(self._toggle_timing_record)
        sal_layout.addWidget(self._rec_btn)

        # Play recorded timing (auto-advance using recorded per-slide durations)
        self._rec_play_btn = QPushButton("⏵")
        self._rec_play_btn.setToolTip("Redă auto-avansul înregistrat (timpi per slide)")
        self._rec_play_btn.setCheckable(True)
        self._rec_play_btn.setFixedSize(24, 20)
        self._rec_play_btn.setStyleSheet(
            "QPushButton { background: #1c1c1c; color: #888; border: 1px solid #222; "
            "border-radius: 3px; font-size: 11px; padding: 0; }"
            "QPushButton:hover { color: #e0e0e0; }"
            "QPushButton:checked { background: #103a18; color: #5aff8a; border-color: #205a30; }"
        )
        self._rec_play_btn.clicked.connect(self._toggle_timing_play)
        sal_layout.addWidget(self._rec_play_btn)

        layout.addWidget(slides_area_lbl)

        from PyQt6.QtWidgets import QStackedWidget
        self._slides_stack = QStackedWidget()

        # Grid view (page 0)
        self.slides_scroll = QScrollArea()
        self.slides_scroll.setWidgetResizable(True)
        self.slides_scroll.setStyleSheet("QScrollArea { border: none; background: #181818; }")
        self.slides_container = QWidget()
        self.slides_container.setStyleSheet("background: #181818;")
        self.slides_grid = QGridLayout(self.slides_container)
        self.slides_grid.setContentsMargins(12, 12, 12, 12)
        self.slides_grid.setSpacing(8)
        self.slides_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.slides_scroll.setWidget(self.slides_container)
        self.slides_container.installEventFilter(self)
        self.slides_container.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.slides_scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._slides_stack.addWidget(self.slides_scroll)

        # List view (page 1)
        self._slide_list_widget = QListWidget()
        self._slide_list_widget.setStyleSheet(
            "QListWidget { background: #141414; border: none; }"
            "QListWidget::item { padding: 8px 12px; border-radius: 4px; "
            "margin: 2px 4px; color: #ccc; border-bottom: 1px solid #1e1e1e; }"
            "QListWidget::item:hover { background: #1c1c1c; }"
            "QListWidget::item:selected { background: #1c3a5a; color: #e0e0e0; }"
        )
        self._slide_list_widget.itemClicked.connect(
            lambda item: self._send_slide_to_live(self._slide_list_widget.row(item))
        )
        self._slides_stack.addWidget(self._slide_list_widget)

        # Placeholder page (page 2) — shown when no song is selected
        self._slides_placeholder = SlidesPlaceholder()
        self._slides_stack.addWidget(self._slides_placeholder)
        self._slides_stack.setCurrentIndex(2)   # start with placeholder

        # ── Splitter: slides area (top) / lyrics editor (bottom) ─────────────
        self._center_splitter = QSplitter(Qt.Orientation.Vertical)
        self._center_splitter.setHandleWidth(3)
        self._center_splitter.setChildrenCollapsible(True)

        # Top pane: the stacked slides widget
        slides_pane = QWidget()
        slides_pane.setMinimumHeight(80)
        sp_layout = QVBoxLayout(slides_pane)
        sp_layout.setContentsMargins(0, 0, 0, 0)
        sp_layout.setSpacing(0)
        sp_layout.addWidget(self._slides_stack)
        self._center_splitter.addWidget(slides_pane)

        # Bottom pane: editor header + editor
        editor_pane = QWidget()
        editor_pane.setMinimumHeight(32)
        ep_layout = QVBoxLayout(editor_pane)
        ep_layout.setContentsMargins(0, 0, 0, 0)
        ep_layout.setSpacing(0)

        editor_header = QWidget()
        editor_header.setFixedHeight(32)
        editor_header.setStyleSheet("background: #131313; border-top: 1px solid #1e1e1e;")
        eh_layout = QHBoxLayout(editor_header)
        eh_layout.setContentsMargins(12, 4, 12, 4)
        editor_lbl = QLabel(t("lyrics_editor").upper())
        editor_lbl.setObjectName("section_lbl")
        eh_layout.addWidget(editor_lbl)
        eh_layout.addStretch()
        hint_lbl = QLabel(t("blank_line_hint"))
        hint_lbl.setObjectName("muted")
        eh_layout.addWidget(hint_lbl)

        # Auto-save status indicator (● modificat / ✅ salvat / empty)
        self._save_indicator = QLabel("")
        self._save_indicator.setStyleSheet(
            "color: #6c7086; font-size: 10px; padding: 0 4px;"
        )
        eh_layout.addWidget(self._save_indicator)

        # Collapse / expand button
        self._editor_collapse_btn = QPushButton("▼")
        self._editor_collapse_btn.setFixedSize(22, 18)
        self._editor_collapse_btn.setToolTip("Collapse / expand lyrics editor")
        self._editor_collapse_btn.setStyleSheet(
            "QPushButton { background: #1c1c1c; color: #666; border: 1px solid #222; "
            "border-radius: 3px; font-size: 10px; padding: 0; }"
            "QPushButton:hover { color: #e0e0e0; }"
        )
        self._editor_collapse_btn.clicked.connect(self._toggle_editor_panel)
        eh_layout.addWidget(self._editor_collapse_btn)
        ep_layout.addWidget(editor_header)

        # ── Rich-text formatting toolbar ──────────────────────────────────────
        rt_toolbar = QWidget()
        rt_toolbar.setFixedHeight(30)
        rt_toolbar.setStyleSheet("background: #111; border-bottom: 1px solid #222;")
        rt_tb_layout = QHBoxLayout(rt_toolbar)
        rt_tb_layout.setContentsMargins(6, 2, 6, 2)
        rt_tb_layout.setSpacing(2)

        _btn_ss = (
            "QPushButton { background: #1c1c1c; color: #bbb; border: 1px solid #2a2a2a; "
            "border-radius: 3px; font-size: 11px; padding: 0; }"
            "QPushButton:hover { color: #fff; background: #252525; }"
            "QPushButton:checked { background: #1c3a5a; color: #5294e2; "
            "border-color: #2a5080; }"
        )

        def _fmt_btn(text, tip, checkable=False):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setCheckable(checkable)
            b.setFixedSize(22, 22)
            b.setStyleSheet(_btn_ss)
            return b

        _bold_font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        self._fmt_bold_btn = _fmt_btn("B", "Bold (Ctrl+B)", checkable=True)
        self._fmt_bold_btn.setFont(_bold_font)
        self._fmt_bold_btn.clicked.connect(self._fmt_toggle_bold)
        rt_tb_layout.addWidget(self._fmt_bold_btn)

        _ital_font = QFont("Segoe UI", 9)
        _ital_font.setItalic(True)
        self._fmt_italic_btn = _fmt_btn("I", "Italic (Ctrl+I)", checkable=True)
        self._fmt_italic_btn.setFont(_ital_font)
        self._fmt_italic_btn.clicked.connect(self._fmt_toggle_italic)
        rt_tb_layout.addWidget(self._fmt_italic_btn)

        _uline_font = QFont("Segoe UI", 9)
        _uline_font.setUnderline(True)
        self._fmt_underline_btn = _fmt_btn("U", "Underline (Ctrl+U)", checkable=True)
        self._fmt_underline_btn.setFont(_uline_font)
        self._fmt_underline_btn.clicked.connect(self._fmt_toggle_underline)
        rt_tb_layout.addWidget(self._fmt_underline_btn)

        self._fmt_strike_btn = _fmt_btn("S̶", "Strikethrough", checkable=True)
        self._fmt_strike_btn.clicked.connect(self._fmt_toggle_strike)
        rt_tb_layout.addWidget(self._fmt_strike_btn)

        _sep_style = "QFrame { color: #333; max-width: 1px; min-width: 1px; margin: 2px 3px; }"
        def _vsep():
            s = QFrame(); s.setFrameShape(QFrame.Shape.VLine)
            s.setStyleSheet(_sep_style); return s

        rt_tb_layout.addWidget(_vsep())

        # Font size
        self._fmt_size_spin = QSpinBox()
        self._fmt_size_spin.setRange(8, 120)
        self._fmt_size_spin.setValue(24)
        self._fmt_size_spin.setFixedSize(54, 22)
        self._fmt_size_spin.setToolTip("Font size (pt)")
        self._fmt_size_spin.setStyleSheet(
            "QSpinBox { background: #1c1c1c; color: #ccc; border: 1px solid #2a2a2a; "
            "border-radius: 3px; font-size: 10px; padding-left: 2px; }"
            "QSpinBox::up-button, QSpinBox::down-button { width: 14px; }"
        )
        self._fmt_size_spin.valueChanged.connect(self._fmt_set_size)
        rt_tb_layout.addWidget(self._fmt_size_spin)

        rt_tb_layout.addWidget(_vsep())

        # Text color
        self._fmt_color_btn = _fmt_btn("A", "Text color")
        self._fmt_color_btn._color = QColor("#ffffff")
        self._fmt_color_btn.clicked.connect(self._fmt_pick_color)
        rt_tb_layout.addWidget(self._fmt_color_btn)

        rt_tb_layout.addWidget(_vsep())

        # Alignment
        self._fmt_align_btns = []
        for sym, tip, align in [
            ("◧", "Align left",   Qt.AlignmentFlag.AlignLeft),
            ("▬", "Align center", Qt.AlignmentFlag.AlignHCenter),
            ("◨", "Align right",  Qt.AlignmentFlag.AlignRight),
        ]:
            b = _fmt_btn(sym, tip, checkable=True)
            b._align = align
            b.clicked.connect(lambda checked, _b=b: self._fmt_set_align(_b._align))
            rt_tb_layout.addWidget(b)
            self._fmt_align_btns.append(b)
        self._fmt_align_btns[1].setChecked(True)   # center default

        rt_tb_layout.addWidget(_vsep())

        undo_btn = _fmt_btn("↩", "Undo (Ctrl+Z)")
        undo_btn.clicked.connect(lambda: self.editor.undo())
        rt_tb_layout.addWidget(undo_btn)

        redo_btn = _fmt_btn("↪", "Redo (Ctrl+Y)")
        redo_btn.clicked.connect(lambda: self.editor.redo())
        rt_tb_layout.addWidget(redo_btn)

        clear_fmt_btn = _fmt_btn("✕", "Clear formatting")
        clear_fmt_btn.clicked.connect(self._fmt_clear_formatting)
        rt_tb_layout.addWidget(clear_fmt_btn)

        rt_tb_layout.addStretch()

        translate_btn = _fmt_btn("🌐", "Traducere cântare")
        translate_btn.setToolTip("Traduce cântarea în altă limbă")
        translate_btn.setStyleSheet(
            "QPushButton { background: #18283a; color: #5294e2; border: 1px solid #1c3a5a; "
            "border-radius: 3px; font-size: 13px; padding: 2px 6px; }"
            "QPushButton:hover { background: #1c3a5a; color: #e0e0e0; }"
        )
        translate_btn.clicked.connect(self._open_translation_dialog)
        rt_tb_layout.addWidget(translate_btn)
        ep_layout.addWidget(rt_toolbar)

        # ── Formatting status bar ──────────────────────────────────────────────
        _fsb = QWidget()
        _fsb.setFixedHeight(20)
        _fsb.setStyleSheet("background: #0e0e0e; border-bottom: 1px solid #1a1a1a;")
        _fsb_layout = QHBoxLayout(_fsb)
        _fsb_layout.setContentsMargins(10, 1, 6, 1)
        _fsb_layout.setSpacing(6)
        self._fmt_status_lbl = QLabel("Foloseste setarile globale")
        self._fmt_status_lbl.setStyleSheet("color: #3a3a3a; font-size: 10px;")
        _fsb_layout.addWidget(self._fmt_status_lbl)
        _fsb_layout.addStretch()
        self._fmt_reset_btn = QPushButton("Reseteaza la global")
        self._fmt_reset_btn.setFixedHeight(16)
        self._fmt_reset_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #5294e2; border: none; "
            "font-size: 10px; padding: 0 4px; }"
            "QPushButton:hover { color: #79b3ff; }"
        )
        self._fmt_reset_btn.setVisible(False)
        self._fmt_reset_btn.clicked.connect(self._reset_song_formatting)
        _fsb_layout.addWidget(self._fmt_reset_btn)
        ep_layout.addWidget(_fsb)

        # ── Lyrics editor ─────────────────────────────────────────────────────
        self.editor = SmartTextEdit()
        self.editor.setAcceptRichText(True)
        self.editor.setFont(QFont("Consolas", 10))
        self.editor.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.editor.setPlaceholderText(
            "Type or paste lyrics here. Separate slides with a blank line.\n\n"
            "Example:\nDoamne, Tu ești lumina mea\nȘi mântuirea mea\n\nDe cine mă voi teme?"
        )
        self.editor.setMinimumHeight(60)
        self.editor.setStyleSheet(
            "QTextEdit { background: #131313; color: #e0e0e0; border: none; "
            "padding: 10px 14px; font-size: 11px; }"
        )
        self.editor.cursorPositionChanged.connect(self._on_cursor_pos_changed)
        self.editor.textChanged.connect(self._on_editor_changed)
        ep_layout.addWidget(self.editor, 1)

        # Word / slide counter
        self._word_count_lbl = QLabel("0 cuvinte  •  0 slide-uri")
        self._word_count_lbl.setStyleSheet(
            "color: #3a3a3a; font-size: 10px; padding: 1px 12px;"
        )
        self._word_count_lbl.setFixedHeight(16)
        ep_layout.addWidget(self._word_count_lbl)
        # Wrap editor + Media + Browser into a tab widget
        self._center_tab_widget = QTabWidget()
        self._center_tab_widget.setDocumentMode(True)
        self._center_tab_widget.setStyleSheet(
            "QTabWidget::pane { border: none; background: #131313; }"
            "QTabBar { background: #0a0a0a; }"
            "QTabBar::tab { background: #0a0a0a; color: #555; padding: 5px 14px; "
            "border: none; border-bottom: 2px solid transparent; font-size: 11px; }"
            "QTabBar::tab:selected { color: #e0e0e0; border-bottom: 2px solid #5294e2; "
            "background: #131313; }"
            "QTabBar::tab:hover { color: #aaa; background: #111; }"
        )
        self._center_tab_widget.addTab(editor_pane, t("tab_lyrics_lbl"))

        try:
            from media_tab import MediaTab
            self._media_tab = MediaTab(self)
            self._center_tab_widget.addTab(self._media_tab, t("tab_media_lbl"))
        except Exception:
            pass

        # Online tab removed — use File ▸ Import for online songs

        try:
            from themes_tab import ThemesTab
            self._themes_tab = ThemesTab(self)
            self._themes_tab_ref = self._themes_tab
            self._center_tab_widget.addTab(self._themes_tab, t("tab_themes_lbl"))
        except Exception as _e:
            print(f"[THEMES TAB] init failed: {_e}")

        try:
            from bible_control_tab import BibleControlTab
            self._bible_control_tab = BibleControlTab(self)
            self._center_tab_widget.addTab(
                self._bible_control_tab, "📖 Control Bible")
        except Exception as _e:
            self._bible_control_tab = None
            print(f"[BIBLE CONTROL TAB] init failed: {_e}")

        # Tab-ul "Overlay" avansat a fost DEZACTIVAT în 1.5.2: cauza un crash brusc
        # al aplicației (segfault la nivel Qt/C++, fără excepție Python în log).
        # Funcțiile de overlay (ticker, logo, ceas) rămân disponibile în panoul din
        # dreapta și în tab-ul Overlay-uri din Setări. overlay_tab.py e păstrat în
        # repo pentru o eventuală reactivare după ce crash-ul e diagnosticat.
        self._overlay_tab = None

        # ── Tab sync: Left Biblie ↔ Center Control Bible ──────────────────────
        self._center_tab_widget.currentChanged.connect(
            self._on_center_tab_changed)

        self._center_splitter.addWidget(self._center_tab_widget)

        # Default proportions: ~57% slides / ~43% editor+tabs
        self._center_splitter.setSizes([400, 300])
        layout.addWidget(self._center_splitter, 1)

        root_layout.addWidget(bottom_w)
        return w

    # ── Service Panel (center-top) ────────────────────────────────────────────

    def _build_service_panel(self):
        w = QWidget()
        w.setStyleSheet("background: #0f1318;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar with save/open buttons
        hdr = QWidget()
        hdr.setFixedHeight(36)
        hdr.setStyleSheet("background: #0a0d10; border-bottom: 1px solid #1a2030;")
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(10, 4, 10, 4)
        hdr_layout.setSpacing(6)

        svc_lbl = QLabel("SERVICIU")
        svc_lbl.setObjectName("section_lbl")
        hdr_layout.addWidget(svc_lbl)
        hdr_layout.addStretch()

        for text, slot, tip in [
            ("💾", self._save_service, "Save service (.gps)"),
            ("📂", self._open_service, "Open service (.gps)"),
            ("✕", self._clear_service, "Clear service"),
        ]:
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setFixedSize(26, 26)
            b.setStyleSheet(
                "QPushButton { background: #141a20; color: #888; border: 1px solid #1e2530; "
                "border-radius: 4px; font-size: 12px; padding: 0; }"
                "QPushButton:hover { background: #1c2530; color: #e0e0e0; }"
            )
            b.clicked.connect(slot)
            hdr_layout.addWidget(b)

        layout.addWidget(hdr)

        # Service list
        self._service_list = QListWidget()
        self._service_list.setStyleSheet(
            "QListWidget { background: #0f1318; border: none; }"
            "QListWidget::item { padding: 8px 12px; border-radius: 4px; "
            "margin: 1px 4px; color: #cccccc; border-bottom: 1px solid #181e28; }"
            "QListWidget::item:hover { background: #141a22; color: #fff; }"
            "QListWidget::item:selected { background: #1c3a5a; color: #e0e0e0; }"
        )
        self._service_list.setDragDropMode(QListWidget.DragDropMode.DragDrop)
        self._service_list.setAcceptDrops(True)
        self._service_list.setSpacing(1)
        self._service_list.itemDoubleClicked.connect(self._load_service_item)
        self._service_list.itemClicked.connect(self._preview_service_item)

        # ── Custom dropEvent — handles external song/verse drops + internal reorder
        _win = self
        _svc_list = self._service_list

        def _service_drop_event(e):
            import json as _json
            mime = e.mimeData()
            if mime.hasFormat("application/x-glorify-song-id"):
                raw = bytes(mime.data("application/x-glorify-song-id")).decode()
                try:
                    song_id = int(raw)
                    e.acceptProposedAction()
                    _win._add_song_id_to_service(song_id)
                except (ValueError, Exception):
                    pass
            elif mime.hasFormat("application/x-glorify-verse"):
                raw = bytes(mime.data("application/x-glorify-verse")).decode()
                try:
                    v = _json.loads(raw)
                    e.acceptProposedAction()
                    _win._add_verse_to_service(v)
                except (ValueError, Exception):
                    pass
            elif mime.hasText() and mime.text().startswith("CANTIO_BG:"):
                bg_path = mime.text()[len("CANTIO_BG:"):]
                e.acceptProposedAction()
                _win._add_background_to_service(bg_path)
            elif mime.hasText() and mime.text().startswith("CANTIO_THEME:"):
                theme_name = mime.text()[len("CANTIO_THEME:"):]
                # Find which service item the drop landed on
                drop_pos = e.position().toPoint() if hasattr(e, 'position') else e.pos()
                target_item = _svc_list.itemAt(drop_pos)
                if target_item is not None:
                    svc_idx = target_item.data(Qt.ItemDataRole.UserRole)
                    e.acceptProposedAction()
                    _win._assign_theme_to_service_item(svc_idx, theme_name)
                else:
                    e.ignore()
            else:
                # Internal reorder — let Qt handle the visual move, then sync
                QListWidget.dropEvent(_svc_list, e)
                _win._sync_service_items_from_list()

        self._service_list.dropEvent = _service_drop_event

        layout.addWidget(self._service_list, 1)

        # Button row
        btn_row = QWidget()
        btn_row.setStyleSheet("background: #0a0d10; border-top: 1px solid #1a2030;")
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(8, 4, 8, 4)
        btn_layout.setSpacing(4)

        for text, slot in [
            (t("add"), self._add_selected_to_service),
            ("▲", self._service_move_up),
            ("▼", self._service_move_down),
            (t("remove"), self._service_remove_item),
        ]:
            b = QPushButton(text)
            b.setStyleSheet(
                "QPushButton { background: #141a20; color: #aaa; border: 1px solid #1e2530; "
                "border-radius: 4px; padding: 4px 8px; font-size: 11px; }"
                "QPushButton:hover { background: #1c2530; color: #e0e0e0; }"
            )
            b.clicked.connect(slot)
            btn_layout.addWidget(b)

        layout.addWidget(btn_row)
        return w

    # ── Right Panel ───────────────────────────────────────────────────────────

    def _build_right_panel(self):
        w = QWidget()
        w.setStyleSheet("background: #131313;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Preview header
        prev_hdr = QWidget()
        prev_hdr.setFixedHeight(32)
        prev_hdr.setStyleSheet("background: #0f0f0f; border-bottom: 1px solid #1e1e1e;")
        ph_layout = QHBoxLayout(prev_hdr)
        ph_layout.setContentsMargins(12, 0, 12, 0)
        ph_lbl = QLabel(t("output_preview").upper())
        ph_lbl.setObjectName("section_lbl")
        ph_layout.addWidget(ph_lbl)
        ph_layout.addStretch()
        self._live_dot = QLabel("●")
        self._live_dot.setStyleSheet("color: #2a2a2a; font-size: 14px;")
        self._live_dot.setToolTip(t("live_indicator"))
        ph_layout.addWidget(self._live_dot)
        layout.addWidget(prev_hdr)

        # Preview
        self._preview_wrap = QWidget()
        self._preview_wrap.setStyleSheet("background: #0f0f0f; padding: 8px;")
        pw_layout = QVBoxLayout(self._preview_wrap)
        pw_layout.setContentsMargins(10, 8, 10, 8)
        self._preview_pw_layout = pw_layout
        self.preview = PreviewWidget()
        self.preview.apply_settings(self.settings)
        pw_layout.addWidget(self.preview)
        layout.addWidget(self._preview_wrap)

        # Wire RenderEngine → PreviewWidget now that both exist.
        # QueuedConnection ensures update_preview runs on the main thread even
        # though preview_ready is emitted from the render thread.
        if hasattr(self, 'render_engine'):
            _Q = Qt.ConnectionType.QueuedConnection
            self.render_engine.preview_ready.connect(self.preview.update_preview, _Q)

        d = QFrame()
        d.setObjectName("divider")
        layout.addWidget(d)

        # Controls scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #131313; }")

        ctrl_widget = QWidget()
        ctrl_widget.setStyleSheet("background: #131313;")
        ctrl_layout = QVBoxLayout(ctrl_widget)
        ctrl_layout.setContentsMargins(12, 12, 12, 12)
        ctrl_layout.setSpacing(8)

        # Dual language toggle
        self._dual_lang_btn = QPushButton(f"🌐 {t('dual_language')}")
        self._dual_lang_btn.setCheckable(True)
        self._dual_lang_btn.setToolTip(
            "Afișează textul original + traducerea simultan pe proiector"
        )
        self._dual_lang_btn.setStyleSheet(
            "QPushButton { background: #1a1a2a; color: #666; border: 1px solid #222; "
            "border-radius: 4px; padding: 5px 10px; font-size: 11px; }"
            "QPushButton:hover { background: #222240; color: #aaa; }"
            "QPushButton:checked { background: #18203a; color: #7ab0ff; "
            "border-color: #2a3a6a; }"
        )
        self._dual_lang_btn.toggled.connect(self._toggle_dual_lang)
        ctrl_layout.addWidget(self._dual_lang_btn)

        # GO LIVE
        self.go_live_btn = QPushButton(f"▶  {t('go_live')}")
        self.go_live_btn.setObjectName("go_live")
        self.go_live_btn.clicked.connect(self._go_live)
        ctrl_layout.addWidget(self.go_live_btn)

        # BLACK SCREEN
        self.black_btn = QPushButton(f"⬛  {t('black_screen')}")
        self.black_btn.setObjectName("black_btn")
        self.black_btn.clicked.connect(self._black_screen)
        ctrl_layout.addWidget(self.black_btn)

        # CLEAR TEXT button
        self._clear_text_btn = QPushButton(f"⬜ {t('clear_text')}")
        self._clear_text_btn.setToolTip(t("clear_text"))
        self._clear_text_btn.setStyleSheet(
            "QPushButton { background: #1a1a2e; color: #a0a0c0; border: 1px solid #2a2a4a; "
            "border-radius: 5px; padding: 8px 10px; font-size: 11px; font-weight: 600; }"
            "QPushButton:hover { background: #22223a; border-color: #5a5a8a; color: #cdd6f4; }"
            "QPushButton:pressed { background: #111122; }"
        )
        self._clear_text_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._clear_text_btn.clicked.connect(self._clear_text)
        ctrl_layout.addWidget(self._clear_text_btn)

        # FREEZE / LOGO row
        freeze_logo_row = QHBoxLayout()
        freeze_logo_row.setSpacing(6)

        self._freeze_btn = QPushButton(f"❄ {t('freeze')}")
        self._freeze_btn.setToolTip(t("freeze"))
        self._freeze_btn.setCheckable(True)
        self._freeze_btn.clicked.connect(self._toggle_freeze)
        self._freeze_btn.setStyleSheet(
            "QPushButton { background: #2a1a0a; color: #ff8833; border: 1px solid #3a2a1a; "
            "border-radius: 5px; padding: 8px 10px; font-size: 11px; font-weight: 600; }"
            "QPushButton:hover { background: #381e0a; border-color: #ff6633; }"
            "QPushButton:checked { background: #8b3000; color: #fff; border-color: #ff4400; }"
        )
        freeze_logo_row.addWidget(self._freeze_btn)

        self._logo_btn = QPushButton(f"🏛 {t('logo')}")
        self._logo_btn.setToolTip("Show/hide logo image on display")
        self._logo_btn.setCheckable(True)
        self._logo_btn.clicked.connect(self._toggle_logo)
        self._logo_btn.setStyleSheet(
            "QPushButton { background: #1a1a3a; color: #8888ff; border: 1px solid #2a2a5a; "
            "border-radius: 5px; padding: 8px 10px; font-size: 11px; font-weight: 600; }"
            "QPushButton:hover { background: #222260; border-color: #6666cc; }"
            "QPushButton:checked { background: #2a2a7a; color: #aaaaff; border-color: #5555cc; }"
        )
        freeze_logo_row.addWidget(self._logo_btn)
        ctrl_layout.addLayout(freeze_logo_row)

        # Preview panel toggle (renderer-based — no frame-grab needed)
        preview_row = QHBoxLayout()
        preview_row.setSpacing(6)
        self._livepreview_btn = QPushButton(f"👁 {t('preview')}")
        self._livepreview_btn.setCheckable(True)
        self._livepreview_btn.setChecked(True)
        self._livepreview_btn.setToolTip("Arată / ascunde panoul de previzualizare")
        self._livepreview_btn.clicked.connect(self._toggle_live_preview)
        self._livepreview_btn.setStyleSheet(
            "QPushButton { background: #1a1a1a; color: #888; border: 1px solid #222; "
            "border-radius: 4px; padding: 6px 10px; font-size: 11px; }"
            "QPushButton:hover { background: #222; color: #e0e0e0; }"
            "QPushButton:checked { background: #18283a; color: #5294e2; border-color: #1c3a5a; }"
        )
        preview_row.addWidget(self._livepreview_btn)

        # Electron operator preview (WYSIWYG — same renderer as the projector)
        self._electron_preview_on = False
        self._electron_preview_btn = QPushButton("🖥 Preview HD")
        self._electron_preview_btn.setCheckable(True)
        self._electron_preview_btn.setToolTip(
            "Preview identic cu proiectorul (fereastră Electron) — merge și cu live-ul închis")
        self._electron_preview_btn.clicked.connect(self._toggle_electron_preview)
        self._electron_preview_btn.setStyleSheet(
            "QPushButton { background: #1a1a1a; color: #888; border: 1px solid #222; "
            "border-radius: 4px; padding: 6px 10px; font-size: 11px; }"
            "QPushButton:hover { background: #222; color: #e0e0e0; }"
            "QPushButton:checked { background: #2a1a3a; color: #c89bf0; border-color: #3a2a5a; }"
        )
        preview_row.addWidget(self._electron_preview_btn)
        ctrl_layout.addLayout(preview_row)

        # Prev / Next
        nav = QHBoxLayout()
        nav.setSpacing(6)
        self.prev_btn = QPushButton(f"◀ {t('prev')}")
        self.next_btn = QPushButton(f"{t('next')} ▶")
        self.prev_btn.setObjectName("nav_btn")
        self.next_btn.setObjectName("nav_btn")
        self.prev_btn.clicked.connect(self._prev_slide)
        self.next_btn.clicked.connect(self._next_slide)
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.next_btn)
        ctrl_layout.addLayout(nav)

        sep = QFrame()
        sep.setObjectName("divider")
        sep.setFixedHeight(1)
        ctrl_layout.addWidget(sep)

        # Auto-advance
        auto_lbl = QLabel(t("auto_advance").upper())
        auto_lbl.setObjectName("section_lbl")
        ctrl_layout.addWidget(auto_lbl)

        auto_row = QHBoxLayout()
        self.auto_check = QCheckBox(t("every"))
        self.auto_check.setStyleSheet("QCheckBox { color: #aaa; }"
                                       "QCheckBox::indicator { width: 14px; height: 14px; "
                                       "border: 1px solid #333; border-radius: 3px; background: #1c1c1c; }"
                                       "QCheckBox::indicator:checked { background: #5294e2; border-color: #5294e2; }")
        self.auto_check.toggled.connect(self._toggle_auto_advance)
        self.auto_spin = QSpinBox()
        self.auto_spin.setRange(1, 120)
        self.auto_spin.setValue(int(self.settings.get("auto_advance_seconds", 5)))
        self.auto_spin.setSuffix("s")
        self.auto_spin.setFixedWidth(64)
        self.auto_spin.setStyleSheet(
            "QSpinBox { background: #1a1a1a; color: #e0e0e0; border: 1px solid #222; "
            "border-radius: 4px; padding: 4px 6px; font-size: 11px; }"
        )
        self.auto_spin.valueChanged.connect(self._on_auto_spin_changed)
        auto_row.addWidget(self.auto_check)
        auto_row.addWidget(self.auto_spin)
        auto_row.addStretch()
        ctrl_layout.addLayout(auto_row)

        sep2 = QFrame()
        sep2.setObjectName("divider")
        sep2.setFixedHeight(1)
        ctrl_layout.addWidget(sep2)

        # Overlays
        ovl_lbl = QLabel(t("overlays").upper())
        ovl_lbl.setObjectName("section_lbl")
        ctrl_layout.addWidget(ovl_lbl)

        # Ticker
        ticker_row = QHBoxLayout()
        self.ticker_input = QLineEdit()
        self.ticker_input.setPlaceholderText(t("alert_ticker"))
        self.ticker_input.setToolTip(
            "Token-uri: {time} {time_s} {date} {slide} {total} {next} {title}")
        self.ticker_input.setStyleSheet(
            "QLineEdit { background: #1a1a1a; border: 1px solid #222; "
            "border-radius: 4px; padding: 5px 8px; color: #e0e0e0; font-size: 11px; }"
            "QLineEdit:focus { border-color: #5294e2; }"
        )
        self.ticker_btn = QPushButton(t("send"))
        self.ticker_btn.setStyleSheet(
            "QPushButton { background: #18283a; color: #5294e2; border: 1px solid #1c3a5a; "
            "border-radius: 4px; padding: 5px 10px; font-size: 11px; }"
            "QPushButton:hover { background: #1c3a5a; }"
        )
        self.ticker_btn.clicked.connect(self._send_ticker)
        self.ticker_clear_btn = QPushButton("✕")
        self.ticker_clear_btn.setFixedWidth(28)
        self.ticker_clear_btn.setStyleSheet(
            "QPushButton { background: #1c1c1c; color: #888; border: 1px solid #222; "
            "border-radius: 4px; padding: 5px; font-size: 11px; }"
            "QPushButton:hover { background: #222; }"
        )
        self.ticker_clear_btn.clicked.connect(self._clear_ticker)
        ticker_row.addWidget(self.ticker_input, 1)
        ticker_row.addWidget(self.ticker_btn)
        ticker_row.addWidget(self.ticker_clear_btn)
        ctrl_layout.addLayout(ticker_row)

        # Clock + Countdown
        clock_row = QHBoxLayout()
        clock_row.setSpacing(6)
        self.clock_btn = QPushButton(f"🕐 {t('clock')}")
        self.clock_btn.setCheckable(True)
        self.clock_btn.clicked.connect(self._toggle_clock)
        self.clock_btn.setStyleSheet(
            "QPushButton { background: #1c1c1c; color: #888; border: 1px solid #222; "
            "border-radius: 4px; padding: 6px 10px; font-size: 11px; }"
            "QPushButton:hover { background: #222; color: #e0e0e0; }"
            "QPushButton:checked { background: #18283a; color: #5294e2; border-color: #1c3a5a; }"
        )
        clock_row.addWidget(self.clock_btn)

        self.countdown_spin = QSpinBox()
        self.countdown_spin.setRange(10, 7200)
        self.countdown_spin.setValue(300)
        self.countdown_spin.setSuffix("s")
        self.countdown_spin.setFixedWidth(72)
        self.countdown_spin.setStyleSheet(
            "QSpinBox { background: #1a1a1a; color: #e0e0e0; border: 1px solid #222; "
            "border-radius: 4px; padding: 5px 6px; font-size: 11px; }"
        )
        self.countdown_go_btn = QPushButton(f"⏱ {t('start')}")
        self.countdown_go_btn.clicked.connect(self._start_countdown)
        self.countdown_go_btn.setStyleSheet(
            "QPushButton { background: #1c1c1c; color: #888; border: 1px solid #222; "
            "border-radius: 4px; padding: 6px 10px; font-size: 11px; }"
            "QPushButton:hover { background: #222; color: #e0e0e0; }"
        )
        clock_row.addWidget(self.countdown_spin)
        clock_row.addWidget(self.countdown_go_btn)
        ctrl_layout.addLayout(clock_row)

        ctrl_layout.addStretch()
        scroll.setWidget(ctrl_widget)

        # ── Two tabs under the preview: Controale + Mixer ─────────────────
        from PyQt6.QtWidgets import QTabWidget
        self._right_tabs = QTabWidget()
        self._right_tabs.setStyleSheet(
            "QTabWidget::pane { border: none; }"
            "QTabBar::tab { background: #161616; color: #777; padding: 6px 14px; "
            "font-size: 11px; border: none; border-bottom: 2px solid transparent; }"
            "QTabBar::tab:selected { color: #e0e0e0; border-bottom: 2px solid #5294e2; }"
            "QTabBar::tab:hover { color: #aaa; }"
        )
        self._right_tabs.addTab(scroll, t("tab_controls_lbl"))
        self._right_tabs.addTab(self._build_layers_tab(), t("tab_layers_lbl"))
        self._right_tabs.addTab(self._build_macros_tab(), t("tab_macros_lbl"))
        self._right_tabs.addTab(self._build_mixer_tab(), t("tab_mixer_lbl"))
        layout.addWidget(self._right_tabs, 1)

        # ── Media player now lives IN the slides area (added to _slides_stack as a
        # page below); no longer docked bottom-right. Created here for ordering. ──
        self.mini_player = MiniVideoPlayer()
        self.mini_player.parent_control = self
        self._media_player_page = self._slides_stack.addWidget(self.mini_player)

        return w

    # ── Output Layers tab (ProPresenter-style independent layer control) ────────

    def _build_layers_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: #131313;")
        root = QVBoxLayout(w)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(8)
        hint = QLabel(t("layers_hint"))
        hint.setStyleSheet("color: #666; font-size: 10px;")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self._layer_btns = {}

        def _layer_row(key, icon, label, default_on=True, is_black=False):
            b = QPushButton(f"{icon}  {label}")
            b.setCheckable(True)
            b.setChecked(default_on)
            b.setMinimumHeight(38)
            on_border = "#c04a4a" if is_black else "#3a8a4a"
            on_bg = "#2a1414" if is_black else "#14240f"
            on_col = "#ff8a8a" if is_black else "#8fe08f"
            b.setStyleSheet(
                "QPushButton { text-align:left; padding:6px 12px; font-size:12px; "
                "background:#1a1a1a; color:#888; border:1px solid #262626; border-radius:6px; }"
                "QPushButton:hover { color:#ccc; }"
                f"QPushButton:checked {{ background:{on_bg}; color:{on_col}; "
                f"border-color:{on_border}; }}")
            b.toggled.connect(lambda on, k=key: self._toggle_output_layer(k, on))
            root.addWidget(b)
            self._layer_btns[key] = b
            return b

        _layer_row("bg",    "🖼", "Fundal (Media)")
        _layer_row("text",  "🔤", "Text (Slide)")
        _layer_row("logo",  "🏛", "Logo", default_on=False)
        _layer_row("black", "⬛", "Black (master)", default_on=False, is_black=True)

        root.addSpacing(6)
        ov_btn = QPushButton("🎭  Ascunde toate overlay-urile")
        ov_btn.setMinimumHeight(32)
        ov_btn.setStyleSheet(
            "QPushButton { text-align:left; padding:6px 12px; font-size:11px; "
            "background:#1a1a1a; color:#999; border:1px solid #262626; border-radius:6px; }"
            "QPushButton:hover { color:#e0e0e0; background:#222; }")
        ov_btn.clicked.connect(self._hide_all_overlays)
        root.addWidget(ov_btn)

        root.addStretch()
        return w

    def _toggle_output_layer(self, target, checked):
        """Show/hide an output layer independently (ProPresenter Output Layers)."""
        if target == "black":
            self._send_dim("black", 1.0 if checked else 0.0)
        elif target == "logo":
            if hasattr(self, "_logo_btn"):
                self._logo_btn.blockSignals(True)
                self._logo_btn.setChecked(checked)
                self._logo_btn.blockSignals(False)
            self._toggle_logo(checked)
        else:  # bg, text — visible => dim 0, hidden => dim 1
            self._send_dim(target, 0.0 if checked else 1.0)

    def _hide_all_overlays(self):
        """Clear every overlay layer (ticker / clock / timer) at once."""
        for fn in ("_clear_ticker", "_stop_ticker"):
            f = getattr(self, fn, None)
            if callable(f):
                try: f()
                except Exception: pass
        mgr = getattr(self, "electron_display", None)
        if mgr is not None:
            for m in ("hide_ticker", "stop_timer", "hide_ticker_with_effect"):
                fn = getattr(mgr, m, None)
                if callable(fn):
                    try: fn()
                    except Exception: pass
        try: self._toasts.info("🎭 Overlay-uri ascunse")
        except Exception: pass

    # ── Macros (one click → many actions, ProPresenter-style) ───────────────────
    MACRO_ACTIONS = [
        ("look",          "🎨 Look (temă)"),        # value = theme name
        ("text_on",       "🔤 Arată text"),
        ("text_off",      "🔤 Ascunde text"),
        ("bg_on",         "🖼 Arată fundal"),
        ("bg_off",        "🖼 Ascunde fundal"),
        ("black_on",      "⬛ Black on"),
        ("black_off",     "⬛ Black off"),
        ("logo_on",       "🏛 Logo on"),
        ("logo_off",      "🏛 Logo off"),
        ("go_live",       "🔴 Go Live (slide curent)"),
        ("next",          "▶ Slide următor"),
        ("prev",          "◀ Slide anterior"),
        ("freeze",        "❄ Freeze"),
        ("unfreeze",      "🔓 Unfreeze"),
        ("hide_overlays", "🎭 Ascunde overlays"),
        ("wait",          "⏱ Așteaptă (ms)"),        # value = ms
    ]

    def _macros_path(self):
        import os
        d = os.path.join(os.path.expanduser("~"), "Cantio")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "macros.json")

    def _load_macros(self):
        import os, json as _json
        p = self._macros_path()
        if not os.path.exists(p):
            return []
        try:
            with open(p, encoding="utf-8") as f:
                data = _json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_macros(self, macros):
        import json as _json
        try:
            with open(self._macros_path(), "w", encoding="utf-8") as f:
                _json.dump(macros, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _macro_action_label(self, a):
        base = dict(self.MACRO_ACTIONS).get(a.get("type"), a.get("type", "?"))
        if a.get("type") == "look":
            return f"{base}: {a.get('value', '(fără)')}"
        if a.get("type") == "wait":
            return f"{base}: {a.get('value', 0)} ms"
        return base

    def _lset(self, key, on):
        """Set an output-layer toggle (keeps the Layere tab buttons in sync)."""
        b = getattr(self, "_layer_btns", {}).get(key)
        if b is not None:
            b.setChecked(on)
        else:
            self._toggle_output_layer(key, on)

    def _exec_macro_action(self, a):
        t = a.get("type"); v = a.get("value")
        if   t == "look":        self._apply_look(v or None)
        elif t == "text_on":     self._lset("text", True)
        elif t == "text_off":    self._lset("text", False)
        elif t == "bg_on":       self._lset("bg", True)
        elif t == "bg_off":      self._lset("bg", False)
        elif t == "black_on":    self._lset("black", True)
        elif t == "black_off":   self._lset("black", False)
        elif t == "logo_on":     self._lset("logo", True)
        elif t == "logo_off":    self._lset("logo", False)
        elif t == "go_live":     self._go_live()
        elif t == "next":        self._next_slide()
        elif t == "prev":        self._prev_slide()
        elif t == "freeze":      self._toggle_freeze(True)
        elif t == "unfreeze":    self._toggle_freeze(False)
        elif t == "hide_overlays": self._hide_all_overlays()

    def _run_macro(self, macro):
        actions = list(macro.get("actions", []))

        def step(i):
            if i >= len(actions):
                return
            a = actions[i]
            if a.get("type") == "wait":
                QTimer.singleShot(max(0, int(a.get("value") or 0)), lambda: step(i + 1))
            else:
                try: self._exec_macro_action(a)
                except Exception as e: logger.debug("[Macro] action error: %s", e)
                QTimer.singleShot(0, lambda: step(i + 1))
        step(0)
        try: self._toasts.info(f"⚙ Macro: {macro.get('name', '')}")
        except Exception: pass

    # ── MIDI control (map notes/CC to actions & macros) ─────────────────────
    def _midi_map_path(self):
        import os
        d = os.path.join(os.path.expanduser("~"), "Cantio")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "midi_map.json")

    def _load_midi_map(self):
        import os, json as _json
        p = self._midi_map_path()
        if not os.path.exists(p):
            return {}
        try:
            with open(p, encoding="utf-8") as f:
                d = _json.load(f)
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    def _save_midi_map(self, m):
        import json as _json
        try:
            with open(self._midi_map_path(), "w", encoding="utf-8") as f:
                _json.dump(m, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _toggle_midi(self, on):
        if on:
            self._start_midi()
        else:
            self._stop_midi()

    def _start_midi(self):
        try:
            import mido  # noqa: F401
        except ImportError:
            r = QMessageBox.question(
                self, "MIDI", "Pentru MIDI e nevoie de pachetele mido + python-rtmidi.\n\n"
                "Le instalez acum?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes)
            if r == QMessageBox.StandardButton.Yes:
                import sys, subprocess, threading
                def work():
                    try:
                        subprocess.check_call([sys.executable, "-m", "pip", "install",
                                               "mido", "python-rtmidi"])
                        self._dyn_pip_done.emit(True, "__midi__")
                    except Exception as e:
                        self._dyn_pip_done.emit(False, "__midi__" + str(e))
                threading.Thread(target=work, daemon=True).start()
                try: self._toasts.info("Se instalează suportul MIDI…")
                except Exception: pass
            if hasattr(self, "_midi_btn"):
                self._midi_btn.blockSignals(True); self._midi_btn.setChecked(False)
                self._midi_btn.blockSignals(False)
            return
        import mido, threading
        try:
            ports = mido.get_input_names()
        except Exception as e:
            ports = []
            logger.debug("[MIDI] get_input_names: %s", e)
        if not ports:
            try: self._toasts.warning("Niciun dispozitiv MIDI găsit.")
            except Exception: pass
            if hasattr(self, "_midi_btn"):
                self._midi_btn.blockSignals(True); self._midi_btn.setChecked(False)
                self._midi_btn.blockSignals(False)
            return
        self._midi_running = True
        self._midi_thread = threading.Thread(
            target=self._midi_loop, args=(ports[0],), daemon=True)
        self._midi_thread.start()
        try: self._toasts.success(f"🎹 MIDI activ: {ports[0]}")
        except Exception: pass

    def _stop_midi(self):
        self._midi_running = False
        try: self._toasts.info("🎹 MIDI oprit")
        except Exception: pass

    def _midi_loop(self, port_name):
        import time
        try:
            import mido
            with mido.open_input(port_name) as port:
                while self._midi_running:
                    for msg in port.iter_pending():
                        key = None
                        if msg.type == "note_on" and getattr(msg, "velocity", 0) > 0:
                            key = f"note:{msg.note}"
                        elif msg.type == "control_change":
                            ctrl = msg.control
                            val  = getattr(msg, "value", 0)
                            if self._midi_learn_cb is not None:
                                # LEARN mode: capture on any noticeable movement so
                                # faders/knobs/buttons are all easy to teach.
                                if val > 0:
                                    key = f"cc:{ctrl}"
                            else:
                                # Normal mode: faders/knobs stream many values. Fire
                                # the mapped action ONCE when the control sweeps up
                                # past a threshold, re-arming only after it drops back
                                # low — so a fader behaves like a button (also handles
                                # CC buttons that send 127 on press / 0 on release).
                                if val >= 64:
                                    if self._midi_cc_armed.get(ctrl, True):
                                        self._midi_cc_armed[ctrl] = False
                                        key = f"cc:{ctrl}"
                                elif val <= 20:
                                    self._midi_cc_armed[ctrl] = True
                        if key:
                            self._midi_received.emit(key)
                    time.sleep(0.005)
        except Exception as e:
            logger.debug("[MIDI] loop error: %s", e)

    def _on_midi_event(self, key):
        # Learn mode: capture this key for the mapping dialog
        cb = getattr(self, "_midi_learn_cb", None)
        if cb:
            self._midi_learn_cb = None
            try: cb(key)
            except Exception: pass
            return
        action = self._load_midi_map().get(key)
        if action:
            self._run_midi_action(action)

    def _run_midi_action(self, action):
        if action.startswith("macro:"):
            name = action[6:]
            for m in self._load_macros():
                if m.get("name") == name:
                    self._run_macro(m); return
        elif action.startswith("look:"):
            self._apply_look(action[5:] or None)
        elif action == "next":     self._next_slide()
        elif action == "prev":     self._prev_slide()
        elif action == "go_live":  self._go_live()
        elif action == "black_toggle":
            b = getattr(self, "_layer_btns", {}).get("black")
            if b: b.setChecked(not b.isChecked())
        else:
            try: self._exec_macro_action({"type": action})
            except Exception: pass

    def _midi_action_choices(self):
        """(value, label) list of everything a MIDI key can trigger."""
        base = [("next", "▶ Slide următor"), ("prev", "◀ Slide anterior"),
                ("go_live", "🔴 Go Live"), ("black_toggle", "⬛ Black on/off"),
                ("text_off", "🔤 Ascunde text"), ("text_on", "🔤 Arată text"),
                ("hide_overlays", "🎭 Ascunde overlays"), ("freeze", "❄ Freeze"),
                ("unfreeze", "🔓 Unfreeze")]
        for m in self._load_macros():
            n = m.get("name", "")
            if n: base.append((f"macro:{n}", f"⚙ Macro: {n}"))
        for n in self._theme_names():
            base.append((f"look:{n}", f"🎨 Look: {n}"))
        return base

    def _edit_midi_map(self):
        from PyQt6.QtWidgets import QListWidget, QComboBox
        mp = self._load_midi_map()
        dlg = QDialog(self)
        dlg.setWindowTitle("🎹 Mapare MIDI")
        dlg.setMinimumSize(460, 380)
        dlg.setStyleSheet(
            "QDialog{background:#181818;color:#e0e0e0;}"
            "QListWidget{background:#131313;border:1px solid #2a2a2a;color:#e0e0e0;border-radius:4px;}"
            "QListWidget::item{padding:6px 8px;}QListWidget::item:selected{background:#1c3a5a;}"
            "QPushButton{background:#1c1c1c;color:#bbb;border:1px solid #2a2a2a;border-radius:4px;padding:5px 10px;}"
            "QPushButton:hover{background:#252525;color:#fff;}"
            "QComboBox{background:#151515;color:#ddd;border:1px solid #2a2a2a;border-radius:4px;padding:4px 8px;}")
        root = QVBoxLayout(dlg)
        info = QLabel("Apasă «Învață», apoi o tastă/buton pe controllerul MIDI, apoi alege acțiunea.")
        info.setStyleSheet("color:#888; font-size:10px;"); info.setWordWrap(True)
        root.addWidget(info)
        lst = QListWidget(); root.addWidget(lst, 1)
        choices = self._midi_action_choices()
        cd = dict(choices)

        def refresh():
            lst.clear()
            for k, act in mp.items():
                lst.addItem(f"{k}  →  {cd.get(act, act)}")

        refresh()
        row = QHBoxLayout()
        learn = QPushButton("🎹 Învață tastă")
        act_combo = QComboBox()
        for v, lbl in choices:
            act_combo.addItem(lbl, v)
        rm = QPushButton("🗑")
        row.addWidget(learn); row.addWidget(act_combo, 1); row.addWidget(rm)
        root.addLayout(row)
        pending = {"key": None}

        def on_learn():
            if not self._midi_running:
                self._toasts.warning("Activează MIDI întâi."); return
            learn.setText("… apasă tasta MIDI")
            def got(key):
                pending["key"] = key
                act = act_combo.currentData()
                mp[key] = act
                refresh()
                learn.setText("🎹 Învață tastă")
            self._midi_learn_cb = got
        learn.clicked.connect(on_learn)

        def do_rm():
            i = lst.currentRow()
            if 0 <= i < len(mp):
                k = list(mp.keys())[i]; del mp[k]; refresh()
        rm.clicked.connect(do_rm)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                              | QDialogButtonBox.StandardButton.Cancel)
        root.addWidget(bb); bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._save_midi_map(mp)
        self._midi_learn_cb = None

    def _build_macros_tab(self) -> QWidget:
        from PyQt6.QtWidgets import QScrollArea
        w = QWidget()
        w.setStyleSheet("background: #131313;")
        root = QVBoxLayout(w)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        hint = QLabel(t("macros_hint"))
        hint.setStyleSheet("color: #666; font-size: 10px;")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self._macros_container = QWidget()
        self._macros_vbox = QVBoxLayout(self._macros_container)
        self._macros_vbox.setContentsMargins(0, 0, 0, 0)
        self._macros_vbox.setSpacing(6)
        sc = QScrollArea(); sc.setWidgetResizable(True); sc.setFrameShape(QFrame.Shape.NoFrame)
        sc.setWidget(self._macros_container)
        root.addWidget(sc, 1)

        edit_btn = QPushButton("✎  Gestionează macros")
        edit_btn.setStyleSheet(
            "QPushButton { padding:6px 12px; font-size:11px; background:#1a1a1a; color:#bbb; "
            "border:1px solid #262626; border-radius:6px; }"
            "QPushButton:hover { color:#fff; background:#222; }")
        edit_btn.clicked.connect(self._edit_macros)
        root.addWidget(edit_btn)

        self._refresh_macros_bar()
        return w

    def _refresh_macros_bar(self):
        box = getattr(self, "_macros_vbox", None)
        if box is None:
            return
        while box.count():
            it = box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        macros = self._load_macros()
        if not macros:
            empty = QLabel("Niciun macro. Apasă «Gestionează macros».")
            empty.setStyleSheet("color:#555; font-size:10px; padding:8px 2px;")
            box.addWidget(empty)
            return
        for m in macros:
            b = QPushButton(f"⚙  {m.get('name', 'Macro')}")
            b.setMinimumHeight(34)
            b.setStyleSheet(
                "QPushButton { text-align:left; padding:6px 12px; font-size:12px; "
                "background:#1a1a24; color:#c89bf0; border:1px solid #2e2440; border-radius:6px; }"
                "QPushButton:hover { background:#241a34; color:#e0c8ff; }")
            b.clicked.connect(lambda _=False, mm=m: self._run_macro(mm))
            box.addWidget(b)

    def _edit_macros(self):
        from PyQt6.QtWidgets import (QListWidget, QListWidgetItem, QComboBox,
                                     QSpinBox, QInputDialog, QLineEdit)
        macros = self._load_macros()
        dlg = QDialog(self)
        dlg.setWindowTitle("⚙ Macros")
        dlg.setMinimumSize(640, 460)
        dlg.setStyleSheet(
            "QDialog{background:#181818;color:#e0e0e0;}"
            "QListWidget{background:#131313;border:1px solid #2a2a2a;color:#e0e0e0;"
            "font-size:12px;border-radius:4px;}QListWidget::item{padding:5px 8px;}"
            "QListWidget::item:selected{background:#2a1a3a;}"
            "QPushButton{background:#1c1c1c;color:#bbb;border:1px solid #2a2a2a;"
            "border-radius:4px;padding:5px 10px;}QPushButton:hover{background:#252525;color:#fff;}"
            "QComboBox,QSpinBox,QLineEdit{background:#151515;color:#ddd;border:1px solid #2a2a2a;"
            "border-radius:4px;padding:4px 8px;}")
        root = QHBoxLayout(dlg)

        # Left: macro list
        left = QVBoxLayout()
        left.addWidget(QLabel("Macros"))
        mlist = QListWidget()
        for m in macros:
            mlist.addItem(m.get("name", "Macro"))
        left.addWidget(mlist, 1)
        lrow = QHBoxLayout()
        newm = QPushButton("＋"); delm = QPushButton("🗑")
        lrow.addWidget(newm); lrow.addWidget(delm)
        left.addLayout(lrow)
        root.addLayout(left, 1)

        # Right: selected macro's actions
        right = QVBoxLayout()
        name_edit = QLineEdit(); name_edit.setPlaceholderText("Nume macro")
        right.addWidget(name_edit)
        right.addWidget(QLabel("Acțiuni (în ordine):"))
        alist = QListWidget()
        right.addWidget(alist, 1)

        addrow = QHBoxLayout()
        type_combo = QComboBox()
        for key, lbl in self.MACRO_ACTIONS:
            type_combo.addItem(lbl, key)
        look_combo = QComboBox()
        for n in self._theme_names():
            look_combo.addItem(n)
        wait_spin = QSpinBox(); wait_spin.setRange(0, 60000); wait_spin.setSingleStep(100)
        wait_spin.setValue(500); wait_spin.setSuffix(" ms")
        add_btn = QPushButton("→ Adaugă")
        addrow.addWidget(type_combo, 2); addrow.addWidget(look_combo, 1)
        addrow.addWidget(wait_spin, 1); addrow.addWidget(add_btn)
        right.addLayout(addrow)

        arow = QHBoxLayout()
        up = QPushButton("↑"); down = QPushButton("↓"); rm = QPushButton("✕")
        for b in (up, down, rm): arow.addWidget(b)
        right.addLayout(arow)
        root.addLayout(right, 2)

        state = {"m": [dict(x) for x in macros], "cur": -1}

        def sync_value_widgets():
            key = type_combo.currentData()
            look_combo.setVisible(key == "look")
            wait_spin.setVisible(key == "wait")
        type_combo.currentIndexChanged.connect(lambda _: sync_value_widgets())
        sync_value_widgets()

        def load_actions():
            alist.clear()
            if 0 <= state["cur"] < len(state["m"]):
                for a in state["m"][state["cur"]].get("actions", []):
                    alist.addItem(self._macro_action_label(a))

        def select_macro(i):
            state["cur"] = i
            if 0 <= i < len(state["m"]):
                name_edit.setText(state["m"][i].get("name", ""))
            else:
                name_edit.setText("")
            load_actions()
        mlist.currentRowChanged.connect(select_macro)

        def do_new():
            name, ok = QInputDialog.getText(dlg, "Macro nou", "Nume:")
            name = (name or "").strip()
            if ok and name:
                state["m"].append({"name": name, "actions": []})
                mlist.addItem(name); mlist.setCurrentRow(mlist.count() - 1)
        newm.clicked.connect(do_new)

        def do_delm():
            i = mlist.currentRow()
            if 0 <= i < len(state["m"]):
                del state["m"][i]; mlist.takeItem(i)
                state["cur"] = -1; load_actions()
        delm.clicked.connect(do_delm)

        def do_add():
            if not (0 <= state["cur"] < len(state["m"])):
                self._toasts.warning("Creează/alege un macro întâi."); return
            key = type_combo.currentData()
            a = {"type": key}
            if key == "look":  a["value"] = look_combo.currentText()
            if key == "wait":  a["value"] = wait_spin.value()
            state["m"][state["cur"]].setdefault("actions", []).append(a)
            load_actions()
        add_btn.clicked.connect(do_add)

        def _move(delta):
            i = alist.currentRow()
            if not (0 <= state["cur"] < len(state["m"])): return
            acts = state["m"][state["cur"]]["actions"]
            j = i + delta
            if 0 <= i < len(acts) and 0 <= j < len(acts):
                acts[i], acts[j] = acts[j], acts[i]; load_actions(); alist.setCurrentRow(j)
        up.clicked.connect(lambda: _move(-1)); down.clicked.connect(lambda: _move(1))

        def do_rm():
            i = alist.currentRow()
            if 0 <= state["cur"] < len(state["m"]):
                acts = state["m"][state["cur"]]["actions"]
                if 0 <= i < len(acts):
                    del acts[i]; load_actions()
        rm.clicked.connect(do_rm)

        def on_name_changed():
            if 0 <= state["cur"] < len(state["m"]):
                nm = name_edit.text().strip()
                if nm:
                    state["m"][state["cur"]]["name"] = nm
                    mlist.item(state["cur"]).setText(nm)
        name_edit.editingFinished.connect(on_name_changed)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                              | QDialogButtonBox.StandardButton.Cancel)
        right.addWidget(bb)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)
        if state["m"]:
            mlist.setCurrentRow(0)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            on_name_changed()
            clean = [m for m in state["m"] if m.get("name") and m.get("actions")]
            self._save_macros(clean)
            self._refresh_macros_bar()

    # ── Mixer tab (MIDI-style manual faders) ────────────────────────────────────

    def _build_mixer_tab(self) -> QWidget:
        from PyQt6.QtWidgets import QSlider
        w = QWidget()
        w.setStyleSheet("background: #131313;")
        root = QVBoxLayout(w)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        hint = QLabel("Manete manuale — trage cât de încet vrei.")
        hint.setStyleSheet("color: #666; font-size: 10px;")
        root.addWidget(hint)

        faders = QHBoxLayout()
        faders.setSpacing(10)

        def _fader(label, on_change, color="#5294e2", init=0):
            col = QVBoxLayout()
            col.setSpacing(4)
            s = QSlider(Qt.Orientation.Vertical)
            s.setRange(0, 100)
            s.setValue(init)
            s.setFixedHeight(180)
            s.setStyleSheet(
                "QSlider::groove:vertical { background: #1c1c1c; width: 8px; border-radius: 4px; }"
                f"QSlider::sub-page:vertical {{ background: #222; border-radius: 4px; }}"
                f"QSlider::add-page:vertical {{ background: {color}; border-radius: 4px; }}"
                f"QSlider::handle:vertical {{ background: #e0e0e0; height: 18px; "
                "margin: 0 -5px; border-radius: 4px; }"
            )
            s.valueChanged.connect(on_change)
            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            lbl.setStyleSheet("color: #aaa; font-size: 10px;")
            col.addWidget(s, 0, Qt.AlignmentFlag.AlignHCenter)
            col.addWidget(lbl)
            faders.addLayout(col)
            return s

        # Black / Clear Text / Logo = live dimmers (value 0..1)
        self._mix_black = _fader("Black",  lambda v: self._send_dim("black", v / 100.0), "#000000")
        self._mix_text  = _fader("Clear\nText", lambda v: self._send_dim("text", v / 100.0), "#888")
        self._mix_logo  = _fader("Logo",   lambda v: self._send_dim("logo", v / 100.0), "#8888ff")

        # Next-slide = manual T-bar scrub (drag to crossfade to the next slide)
        self._mix_next = _fader("Next\nslide", self._manual_step, "#5aff8a")
        self._mix_next.sliderPressed.connect(self._manual_begin)
        self._mix_next.sliderReleased.connect(self._manual_release)
        root.addLayout(faders)

        # Transition speed (duration)
        sep = QFrame(); sep.setObjectName("divider"); sep.setFixedHeight(1)
        root.addWidget(sep)
        sp_row = QHBoxLayout()
        sp_row.addWidget(QLabel("Viteză tranziție:"))
        self._mix_speed = QSlider(Qt.Orientation.Horizontal)
        self._mix_speed.setRange(100, 3000)
        self._mix_speed.setValue(int(self.settings.get("transition_duration", 400)))
        self._mix_speed.valueChanged.connect(self._on_mix_speed)
        self._mix_speed_lbl = QLabel(f"{self._mix_speed.value()} ms")
        self._mix_speed_lbl.setStyleSheet("color: #5294e2; font-size: 11px;")
        self._mix_speed_lbl.setFixedWidth(60)
        sp_row.addWidget(self._mix_speed, 1)
        sp_row.addWidget(self._mix_speed_lbl)
        root.addLayout(sp_row)

        # Background transition effect
        bt_row = QHBoxLayout()
        bt_row.addWidget(QLabel("Efect între fundaluri:"))
        self._mix_bg_fx = QComboBox()
        try:
            import theme_editor as _te
            _te.populate_transition_combo(
                self._mix_bg_fx, [x for x in _te.TRANSITIONS if x != "instant"])
        except Exception:
            self._mix_bg_fx.addItems(["fade", "crossfade", "slide_left", "zoom_in"])
        self._mix_bg_fx.setCurrentText(self.settings.get("bg_transition", "fade"))
        self._mix_bg_fx.currentTextChanged.connect(self._on_mix_bg_fx)
        bt_row.addWidget(self._mix_bg_fx, 1)
        root.addLayout(bt_row)

        # Quick reset
        reset = QPushButton("↺ Resetează manetele")
        reset.setStyleSheet(
            "QPushButton { background: #1c1c1c; color: #888; border: 1px solid #222; "
            "border-radius: 4px; padding: 6px 10px; font-size: 11px; }"
            "QPushButton:hover { background: #222; color: #e0e0e0; }"
        )
        reset.clicked.connect(self._reset_mixer)
        root.addWidget(reset)

        # ── MIDI control ──────────────────────────────────────────────────
        midi_lbl = QLabel("🎹 MIDI")
        midi_lbl.setStyleSheet("color:#888; font-size:11px; margin-top:6px;")
        root.addWidget(midi_lbl)
        midi_row = QHBoxLayout()
        self._midi_btn = QPushButton("Activează MIDI")
        self._midi_btn.setCheckable(True)
        self._midi_btn.setStyleSheet(
            "QPushButton { background:#1a1a1a; color:#888; border:1px solid #262626; "
            "border-radius:4px; padding:6px 10px; font-size:11px; }"
            "QPushButton:hover { color:#ccc; }"
            "QPushButton:checked { background:#14240f; color:#8fe08f; border-color:#3a8a4a; }")
        self._midi_btn.toggled.connect(self._toggle_midi)
        midi_map_btn = QPushButton("Mapează…")
        midi_map_btn.setStyleSheet(
            "QPushButton { background:#1c1c1c; color:#bbb; border:1px solid #262626; "
            "border-radius:4px; padding:6px 10px; font-size:11px; }"
            "QPushButton:hover { background:#222; color:#fff; }")
        midi_map_btn.clicked.connect(self._edit_midi_map)
        midi_row.addWidget(self._midi_btn, 1); midi_row.addWidget(midi_map_btn)
        root.addLayout(midi_row)

        # ── Audio Bin ─────────────────────────────────────────────────────
        abin_btn = QPushButton("🎵 Audio Bin (muzică de fundal)")
        abin_btn.setStyleSheet(
            "QPushButton { background:#1a1a24; color:#c89bf0; border:1px solid #2e2440; "
            "border-radius:4px; padding:7px 10px; font-size:11px; margin-top:6px; }"
            "QPushButton:hover { background:#241a34; color:#e0c8ff; }")
        abin_btn.clicked.connect(self._open_audio_bin)
        root.addWidget(abin_btn)

        root.addStretch()
        return w

    # ── Audio Bin (background music playlists) ──────────────────────────────
    def _audio_bin_path(self):
        import os
        d = os.path.join(os.path.expanduser("~"), "Cantio")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "audio_bin.json")

    def _load_audio_bin(self):
        import os, json as _json
        p = self._audio_bin_path()
        if not os.path.exists(p):
            return []
        try:
            with open(p, encoding="utf-8") as f:
                d = _json.load(f)
            return d if isinstance(d, list) else []
        except Exception:
            return []

    def _save_audio_bin(self, items):
        import json as _json
        try:
            with open(self._audio_bin_path(), "w", encoding="utf-8") as f:
                _json.dump(items, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _audio_target_wid(self):
        if self.display_windows:
            return getattr(self.display_windows[0], "window_id", 1)
        if not getattr(self, "_electron_preview_on", False):
            self._auto_enable_hd_preview()
        return -1

    def _open_audio_bin(self):
        import os
        from PyQt6.QtWidgets import QListWidget, QSlider, QCheckBox
        mgr = getattr(self, "electron_display", None)
        if mgr is None:
            QMessageBox.warning(self, "Indisponibil", "Subsistemul Electron nu e disponibil.")
            return
        if hasattr(mgr, "is_running") and not mgr.is_running():
            mgr.start()
        items = self._load_audio_bin()
        dlg = QDialog(self)
        dlg.setWindowTitle("🎵 Audio Bin")
        dlg.setMinimumSize(460, 400)
        dlg.setStyleSheet(
            "QDialog{background:#181818;color:#e0e0e0;}"
            "QListWidget{background:#131313;border:1px solid #2a2a2a;color:#e0e0e0;border-radius:4px;}"
            "QListWidget::item{padding:6px 8px;}QListWidget::item:selected{background:#2a1a3a;}"
            "QPushButton{background:#1c1c1c;color:#bbb;border:1px solid #2a2a2a;border-radius:4px;padding:6px 12px;}"
            "QPushButton:hover{background:#252525;color:#fff;}"
            "QCheckBox{color:#bbb;}")
        root = QVBoxLayout(dlg)
        lst = QListWidget()
        for it in items:
            lst.addItem(os.path.basename(it))
        root.addWidget(lst, 1)

        frow = QHBoxLayout()
        add_b = QPushButton("＋ Adaugă"); rm_b = QPushButton("🗑")
        frow.addWidget(add_b); frow.addWidget(rm_b); frow.addStretch()
        root.addLayout(frow)

        prow = QHBoxLayout()
        play_b = QPushButton("▶ Redă"); pause_b = QPushButton("⏸"); stop_b = QPushButton("⏹")
        loop_c = QCheckBox("Loop"); loop_c.setChecked(True)
        prow.addWidget(play_b); prow.addWidget(pause_b); prow.addWidget(stop_b); prow.addWidget(loop_c)
        root.addLayout(prow)

        vol = QSlider(Qt.Orientation.Horizontal); vol.setRange(0, 100); vol.setValue(80)
        root.addWidget(QLabel("Volum")); root.addWidget(vol)

        wid = self._audio_target_wid()

        def do_add():
            paths, _ = QFileDialog.getOpenFileNames(
                dlg, "Adaugă audio", "", "Audio (*.mp3 *.wav *.ogg *.m4a *.flac)")
            for p in paths:
                items.append(p); lst.addItem(os.path.basename(p))
            self._save_audio_bin(items)
        add_b.clicked.connect(do_add)

        def do_rm():
            i = lst.currentRow()
            if 0 <= i < len(items):
                del items[i]; lst.takeItem(i); self._save_audio_bin(items)
        rm_b.clicked.connect(do_rm)

        def do_play():
            i = lst.currentRow()
            if 0 <= i < len(items):
                mgr.audio_bin_play(items[i], loop_c.isChecked(), wid)
                mgr.audio_bin_volume(vol.value() / 100.0, wid)
        play_b.clicked.connect(do_play)
        lst.itemDoubleClicked.connect(lambda _: do_play())
        pause_b.clicked.connect(lambda: mgr.audio_bin_pause(wid))
        stop_b.clicked.connect(lambda: mgr.audio_bin_stop(wid))
        vol.valueChanged.connect(lambda v: mgr.audio_bin_volume(v / 100.0, wid))

        # Keep playing after closing the dialog (background music).
        dlg.exec()

    def _send_dim(self, target: str, value: float):
        for dw in self.display_windows:
            if hasattr(dw, "dim"):
                try:
                    dw.dim(target, value)
                except Exception:
                    pass
        m = self._preview_mgr()
        if m is not None:
            try: m.dim(target, value, -1)
            except Exception: pass

    # ── Manual next-slide scrub (T-bar) ─────────────────────────────────────────

    def _manual_begin(self):
        """Operator grabbed the Next-slide fader → prep the next slide for scrubbing."""
        self._manual_next_idx = None
        if self._in_pres_mode:
            return
        nxt = self.current_slide_idx + 1
        if not (0 <= nxt < len(self.current_slides)):
            return
        slide = self.current_slides[nxt]
        text = slide.get("text", "") if isinstance(slide, dict) else str(slide)
        trans = self.settings.get("transition", "fade")
        self._manual_next_idx = nxt
        for dw in self.display_windows:
            if hasattr(dw, "manual_prep"):
                try: dw.manual_prep(text, trans)
                except Exception: pass
        m = self._preview_mgr()
        if m is not None:
            try: m.manual_prep(text, trans, -1)
            except Exception: pass

    def _manual_step(self, v: int):
        if getattr(self, "_manual_next_idx", None) is None:
            return
        for dw in self.display_windows:
            if hasattr(dw, "manual_set"):
                try: dw.manual_set(v / 100.0)
                except Exception: pass
        m = self._preview_mgr()
        if m is not None:
            try: m.manual_set(v / 100.0, -1)
            except Exception: pass

    def _manual_release(self):
        if getattr(self, "_manual_next_idx", None) is None:
            self._mix_next.setValue(0)
            return
        commit = self._mix_next.value() >= 90
        for dw in self.display_windows:
            if hasattr(dw, "manual_end"):
                try: dw.manual_end(commit)
                except Exception: pass
        m = self._preview_mgr()
        if m is not None:
            try: m.manual_end(commit, -1)
            except Exception: pass
        if commit:
            # Display already shows the next slide — sync app state without re-sending
            self._select_slide(self._manual_next_idx)
            self._push_remote_state()
        self._manual_next_idx = None
        self._mix_next.setValue(0)

    def _on_mix_speed(self, ms: int):
        self.settings["transition_duration"] = ms
        if hasattr(self, "_mix_speed_lbl"):
            self._mix_speed_lbl.setText(f"{ms} ms")
        try:
            db.save_setting("transition_duration", str(ms))
        except Exception:
            pass

    def _on_mix_bg_fx(self, fx: str):
        self.settings["bg_transition"] = fx
        try:
            db.save_setting("bg_transition", fx)
        except Exception:
            pass

    def _reset_mixer(self):
        for s in (getattr(self, "_mix_black", None), getattr(self, "_mix_text", None),
                  getattr(self, "_mix_logo", None)):
            if s is not None:
                s.setValue(0)

    # ── Status Bar ────────────────────────────────────────────────────────────

    def _build_statusbar(self):
        self.status = QStatusBar()
        self.status.setStyleSheet(
            "QStatusBar { background: #0f0f0f; color: #555555; "
            "border-top: 1px solid #1c1c1c; font-size: 11px; padding: 0 8px; }"
        )
        self.setStatusBar(self.status)

        # LIVE indicator dot in status bar (mirrors the panel dot)
        self._status_live_dot = QLabel("●")
        self._status_live_dot.setStyleSheet("color: #2a2a2a; font-size: 14px;")
        self._status_live_dot.setToolTip(t("live_indicator"))
        self.status.addWidget(self._status_live_dot)

        self._status_song_lbl = QLabel(t("no_song_loaded"))
        self._status_song_lbl.setStyleSheet("color: #666666;")
        self.status.addWidget(self._status_song_lbl)
        self.status.addWidget(self._make_status_sep())

        self._status_display_lbl = QLabel(t("no_display_open"))
        self._status_display_lbl.setStyleSheet("color: #444444;")
        self.status.addWidget(self._status_display_lbl)
        self.status.addWidget(self._make_status_sep())

        # Stage monitor indicator
        self._status_stage_lbl = QLabel("")
        self._status_stage_lbl.setStyleSheet("color: #444444;")
        self._status_stage_lbl.setToolTip(t("stage_monitor"))
        self.status.addWidget(self._status_stage_lbl)

        # Display-mode indicator
        self._status_mode_sep = self._make_status_sep()
        self.status.addWidget(self._status_mode_sep)
        _dm = self.settings.get("display_mode", "settings")
        _mode_text = "🎨 Teme active" if _dm == "themes" else "⚙ Setări globale"
        self._status_mode_lbl = QLabel(_mode_text)
        self._status_mode_lbl.setStyleSheet(
            "color: #c9a0dc;" if _dm == "themes" else "color: #555555;"
        )
        self._status_mode_lbl.setToolTip("Mod afișare — schimbă din Setări → Display")
        self.status.addWidget(self._status_mode_lbl)

        # Unsaved service marker (permanent — right side)
        self._status_unsaved_lbl = QLabel("")
        self._status_unsaved_lbl.setStyleSheet("color: #e2a252; font-weight: 700;")
        self._status_unsaved_lbl.setToolTip(t("unsaved_changes"))
        self.status.addPermanentWidget(self._status_unsaved_lbl)

        self.status.addPermanentWidget(self._make_status_sep())

        # Warnings count label (clickable)
        self._status_warn_lbl = QLabel("")
        self._status_warn_lbl.setStyleSheet("color: #555555;")
        self._status_warn_lbl.setToolTip("Avertismente active — click pentru detalii")
        self._status_warn_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self._status_warn_lbl.mousePressEvent = lambda _: self._show_warnings_summary()
        self.status.addPermanentWidget(self._status_warn_lbl)

        self.status.addPermanentWidget(self._make_status_sep())

        self._status_slide_lbl = QLabel("")
        self._status_slide_lbl.setStyleSheet("color: #555555;")
        self.status.addPermanentWidget(self._status_slide_lbl)

        # Performance mode indicator (permanent, right side)
        self._status_perf_lbl = QLabel("")
        self._status_perf_lbl.setStyleSheet(
            "color: #e2a252; font-size: 11px; font-weight: 700;"
        )
        self._status_perf_lbl.setToolTip(
            "Mod Performanță Scăzută activ — tranziții reduse, FPS limitat.\n"
            "Dezactivează din Setări → Performanță."
        )
        self._status_perf_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self._status_perf_lbl.mousePressEvent = lambda _: self._toggle_performance_mode()
        self.status.addPermanentWidget(self._status_perf_lbl)
        self._refresh_perf_indicator()

    def _make_status_sep(self):
        sep = QLabel(" │ ")
        sep.setStyleSheet("color: #242424;")
        return sep

    def _update_status(self, song_msg=None, display_msg=None, slide_msg=None,
                        stage_msg=None):
        if song_msg is not None:
            self._status_song_lbl.setText(song_msg)
        if display_msg is not None:
            self._status_display_lbl.setText(display_msg)
        if slide_msg is not None:
            self._status_slide_lbl.setText(slide_msg)
        if stage_msg is not None:
            self._status_stage_lbl.setText(stage_msg)

    def _mark_service_modified(self, modified: bool = True):
        """Set/clear the unsaved-service marker in the status bar."""
        self._service_modified = modified
        self._status_unsaved_lbl.setText(t("unsaved_service") if modified else "")

    def _increment_warnings(self, delta: int = 1):
        """Track warning count for the status bar indicator."""
        self._warnings_count = max(0, self._warnings_count + delta)
        if self._warnings_count > 0:
            self._status_warn_lbl.setText(
                f"⚠ {self._warnings_count} avertisment{'e' if self._warnings_count != 1 else ''}"
            )
            self._status_warn_lbl.setStyleSheet("color: #e2a252; font-weight: 600;")
        else:
            self._status_warn_lbl.setText("")
            self._status_warn_lbl.setStyleSheet("color: #555555;")

    # ── Performance mode ──────────────────────────────────────────────────────

    def _refresh_perf_indicator(self):
        if self._perf_mode:
            self._status_perf_lbl.setText("⚡ Mod performanță")
        elif self._perf_level == "low":
            self._status_perf_lbl.setText(f"⚡ Hardware: Slab")
            self._status_perf_lbl.setToolTip(
                "Hardware detectat ca slab (RAM < 6 GB sau CPU ≤ 2 nuclee).\n"
                "Click pentru a activa Modul Performanță."
            )
        else:
            lvl_ro = {"medium": "Mediu", "high": "Bun"}.get(self._perf_level, "")
            self._status_perf_lbl.setText(f"✓ Hardware: {lvl_ro}" if lvl_ro else "")

    def _toggle_performance_mode(self):
        """Toggle low-performance mode on/off (click on status bar indicator)."""
        self._perf_mode = not self._perf_mode
        db.save_setting("performance_mode", "true" if self._perf_mode else "false")
        self.settings["performance_mode"] = "true" if self._perf_mode else "false"
        self._refresh_perf_indicator()
        # Propagate to all open display windows
        for dw in self.display_windows:
            dw.apply_settings(self.settings)
        if self._perf_mode:
            self._toasts.info("⚡ Mod performanță activat — tranziții reduse, FPS 30.")
        else:
            self._toasts.info("Mod performanță dezactivat — tranziții complete, FPS 60.")

    def _show_warnings_summary(self):
        """Show a brief summary dialog when the warnings count label is clicked."""
        QMessageBox.information(
            self, "Avertismente recente",
            "Există avertismente nesoluționate afișate ca toast-uri.\n"
            "Verifică zona din dreapta-jos a ferestrei.\n\n"
            "Numărul se resetează la repornire."
        )

    def _pulse_live(self):
        self._live_pulse_state = not self._live_pulse_state
        color = "#4CAF50" if self._live_pulse_state else "#2d4a2d"
        self._live_dot.setStyleSheet(f"color: {color}; font-size: 14px;")
        self._status_live_dot.setStyleSheet(f"color: {color}; font-size: 14px;")

    # ── Library ───────────────────────────────────────────────────────────────

    def _load_library(self):
        """Load first page of songs into the virtual model."""
        cat = self.cat_combo.currentText() if hasattr(self, 'cat_combo') else "All"
        search = self.search_edit.text() if hasattr(self, 'search_edit') else ""
        category = cat if cat != "All" else ""
        self.songs_model.load_page(search=search, category=category)
        self._remote_songs_dirty = True   # remote song-list cache needs refresh
        total = db.get_songs_count()
        self._update_status(
            song_msg=f"{total} cântări în bibliotecă"
        )
        self._load_playlist_list()
        self._refresh_categories()

    def _on_search_text_changed(self, text: str):
        """Wire search_edit.textChanged → model debounce + category."""
        cat = self.cat_combo.currentText() if hasattr(self, 'cat_combo') else "All"
        self.songs_model._category = cat if cat != "All" else ""
        self.songs_model.search(text)

    def _do_search(self):
        """Immediate search — used by category filter."""
        cat = self.cat_combo.currentText() if hasattr(self, 'cat_combo') else "All"
        search = self.search_edit.text() if hasattr(self, 'search_edit') else ""
        self.songs_model.load_page(
            search=search,
            category=cat if cat != "All" else ""
        )

    def _search_songs(self, query):
        """Legacy slot — delegates to model debounce."""
        self._on_search_text_changed(query)

    def _on_cat_filter(self):
        self._do_search()

    # ── Smart Playlists (saved category + search filters) ───────────────────
    def _smart_playlists_path(self):
        import os
        d = os.path.join(os.path.expanduser("~"), "Cantio")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "smart_playlists.json")

    def _load_smart_playlists(self):
        import os, json as _json
        p = self._smart_playlists_path()
        if not os.path.exists(p):
            return []
        try:
            with open(p, encoding="utf-8") as f:
                d = _json.load(f)
            return d if isinstance(d, list) else []
        except Exception:
            return []

    def _save_smart_playlists(self, sps):
        import json as _json
        try:
            with open(self._smart_playlists_path(), "w", encoding="utf-8") as f:
                _json.dump(sps, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _apply_smart_playlist(self, sp):
        cat = sp.get("category", "") or "All"
        if hasattr(self, "cat_combo"):
            i = self.cat_combo.findText(cat)
            self.cat_combo.blockSignals(True)
            self.cat_combo.setCurrentIndex(i if i >= 0 else 0)
            self.cat_combo.blockSignals(False)
        if hasattr(self, "search_edit"):
            self.search_edit.setText(sp.get("query", ""))   # triggers reload
        self._do_search()
        try: self._toasts.info(f"⚡ {sp.get('name', 'Smart')}")
        except Exception: pass

    def _show_smart_menu(self):
        from PyQt6.QtWidgets import QMenu
        m = QMenu(self)
        sps = self._load_smart_playlists()
        for sp in sps:
            m.addAction(f"⚡ {sp.get('name', 'Smart')}",
                        lambda _=False, s=sp: self._apply_smart_playlist(s))
        if sps:
            m.addSeparator()
        m.addAction("＋ Salvează filtrul curent…", self._save_current_as_smart)
        m.addAction("✎ Gestionează…", self._edit_smart_playlists)
        m.exec(self._smart_btn.mapToGlobal(self._smart_btn.rect().bottomLeft()))

    def _save_current_as_smart(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Smart Playlist", "Nume:")
        name = (name or "").strip()
        if not (ok and name):
            return
        sps = self._load_smart_playlists()
        cat = self.cat_combo.currentText() if hasattr(self, "cat_combo") else "All"
        query = self.search_edit.text().strip() if hasattr(self, "search_edit") else ""
        sps = [s for s in sps if s.get("name") != name]
        sps.append({"name": name, "category": cat, "query": query})
        self._save_smart_playlists(sps)
        try: self._toasts.success(f"⚡ Smart Playlist «{name}» salvat")
        except Exception: pass

    def _edit_smart_playlists(self):
        from PyQt6.QtWidgets import QListWidget, QLineEdit, QComboBox
        sps = self._load_smart_playlists()
        dlg = QDialog(self)
        dlg.setWindowTitle("⚡ Smart Playlists")
        dlg.setMinimumSize(480, 380)
        dlg.setStyleSheet(
            "QDialog{background:#181818;color:#e0e0e0;}"
            "QListWidget{background:#131313;border:1px solid #2a2a2a;color:#e0e0e0;border-radius:4px;}"
            "QListWidget::item{padding:6px 8px;}QListWidget::item:selected{background:#2a1a3a;}"
            "QPushButton{background:#1c1c1c;color:#bbb;border:1px solid #2a2a2a;border-radius:4px;padding:5px 10px;}"
            "QPushButton:hover{background:#252525;color:#fff;}"
            "QLineEdit,QComboBox{background:#151515;color:#ddd;border:1px solid #2a2a2a;border-radius:4px;padding:5px 8px;}")
        root = QHBoxLayout(dlg)
        left = QVBoxLayout()
        lst = QListWidget()
        for s in sps:
            lst.addItem(s.get("name", "Smart"))
        left.addWidget(lst, 1)
        lrow = QHBoxLayout()
        newb = QPushButton("＋"); delb = QPushButton("🗑")
        lrow.addWidget(newb); lrow.addWidget(delb); left.addLayout(lrow)
        root.addLayout(left, 1)

        right = QVBoxLayout()
        right.addWidget(QLabel("Nume")); name_e = QLineEdit(); right.addWidget(name_e)
        right.addWidget(QLabel("Categorie")); cat_c = QComboBox()
        cat_c.addItem("All")
        try: cat_c.addItems([c for c in db.get_all_categories() if c != "All"])
        except Exception: pass
        right.addWidget(cat_c)
        right.addWidget(QLabel("Căutare (text)")); q_e = QLineEdit(); right.addWidget(q_e)
        right.addStretch()
        root.addLayout(right, 1)

        state = {"m": [dict(x) for x in sps], "cur": -1}

        def load_sel(i):
            state["cur"] = i
            if 0 <= i < len(state["m"]):
                s = state["m"][i]
                name_e.setText(s.get("name", "")); q_e.setText(s.get("query", ""))
                j = cat_c.findText(s.get("category", "All")); cat_c.setCurrentIndex(max(0, j))
        lst.currentRowChanged.connect(load_sel)

        def commit_fields():
            if 0 <= state["cur"] < len(state["m"]):
                state["m"][state["cur"]] = {
                    "name": name_e.text().strip() or "Smart",
                    "category": cat_c.currentText(), "query": q_e.text().strip()}
                lst.item(state["cur"]).setText(state["m"][state["cur"]]["name"])
        for wdg in (name_e, q_e):
            wdg.editingFinished.connect(commit_fields)
        cat_c.currentIndexChanged.connect(lambda _: commit_fields())

        def do_new():
            state["m"].append({"name": "Nou", "category": "All", "query": ""})
            lst.addItem("Nou"); lst.setCurrentRow(lst.count() - 1)
        newb.clicked.connect(do_new)

        def do_del():
            i = lst.currentRow()
            if 0 <= i < len(state["m"]):
                del state["m"][i]; lst.takeItem(i); state["cur"] = -1
        delb.clicked.connect(do_del)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                              | QDialogButtonBox.StandardButton.Cancel)
        right.addWidget(bb); bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)
        if sps: lst.setCurrentRow(0)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            commit_fields()
            self._save_smart_playlists([s for s in state["m"] if s.get("name")])

    def _on_song_list_scroll(self, value):
        """Load next page when scroll bar reaches 85% of maximum."""
        sb = self.song_list.verticalScrollBar()
        if sb.maximum() > 0 and value > sb.maximum() * 0.85:
            self.songs_model.load_more()

    # ── Song list item selection ──────────────────────────────────────────────

    def _preview_song_by_index(self, qidx: QModelIndex):
        song_id = self.songs_model.data(qidx, Qt.ItemDataRole.UserRole)
        if song_id is None:
            return
        slides = db.get_song_slides_only(song_id)
        if slides:
            self.preview.update_text(slides[0])

    def _load_song_by_index(self, qidx: QModelIndex):
        song_id = self.songs_model.data(qidx, Qt.ItemDataRole.UserRole)
        if song_id is None:
            return
        self._load_song_by_id(song_id)

    # Legacy adapter — called from QListWidgetItem signals in playlist_list etc.
    def _preview_song(self, item):
        song_id = item.data(Qt.ItemDataRole.UserRole)
        slides = db.get_song_slides_only(song_id)
        if slides:
            self.preview.update_text(slides[0])

    def _load_song(self, item):
        song_id = item.data(Qt.ItemDataRole.UserRole)
        self._load_song_by_id(song_id)

    def _load_song_by_id(self, song_id):
        """Core song-load logic (used by both QListView index and QListWidgetItem)."""
        import gc
        # A new song's default slide isn't an explicit pick → if a Display is
        # (re)opened now it should stay black until the operator chooses a slide.
        self._live_armed = False
        # Release previous song thumbnails before loading new ones
        self.current_slides = []
        self._thumbnails.clear()
        gc.collect()

        song = db.get_song(song_id)
        if not song:
            return
        self._in_pres_mode = False
        self._pres_pixmaps = []

        # Read last-used slide for this song BEFORE _set_slides() resets it to 0
        if not hasattr(self, '_last_slide_per_song'):
            self._last_slide_per_song: dict[str, int] = {}
        _restore_idx = self._last_slide_per_song.get(str(song_id), 0)

        self.current_song_id = song_id
        self.current_song_notes = song.get("notes", "")
        self._current_metadata = {
            "title":    song.get("title", ""),
            "author":   song.get("author", ""),
            "category": song.get("category", ""),
            "source":   song.get("notes", ""),
        }
        self.song_title_edit.setText(song["title"])
        self._load_content_to_editor(song["content"])
        # Show section labels ([Strofa 1]/[Refren]…) in the editor — auto-generated
        # when the song has none. Only for plain-text songs (HTML formatting kept).
        _c = (song.get("content", "") or "").strip()
        _is_plain = not (_c.startswith("<!DOCTYPE") or _c.startswith("<html"))
        self._load_slides_to_editor_with_labels(song["slides"], auto=_is_plain)
        self._set_slides(song["slides"])
        # Restore last-viewed slide for this song (overrides the _select_slide(0)
        # call inside _set_slides so the user returns to where they left off).
        if _restore_idx > 0 and _restore_idx < len(song["slides"]):
            self._select_slide(_restore_idx)
        self._update_word_counter()
        # Per-song formatting
        self._current_song_formatting = song.get("formatting")
        self._editor_modified = False
        self._init_toolbar_from_formatting()
        self._update_fmt_status_label()
        self._update_notes_bar(song.get("notes", ""))
        self._update_status(
            song_msg=f"{song['title']}",
            slide_msg=f"{len(song['slides'])} slide{'s' if len(song['slides']) != 1 else ''}"
        )

        # Apply theme to preview + thumbnails so they match the live display
        _preview_s = self._get_preview_settings(song_id)
        self.preview.apply_settings(_preview_s)
        self._refresh_thumbnails_with_theme(song_id)

        # Capture base slides + apply any saved active arrangement for this song
        self._init_song_arrangements()

    def _get_preview_settings(self, song_id=None) -> dict:
        """Return the resolved settings for preview / thumbnails (identical to live)."""
        return self._resolve_settings(
            source=getattr(self, "_current_source", "songs"),
            song_id=song_id if song_id is not None else self.current_song_id,
        )

    def _refresh_thumbnails_with_theme(self, song_id=None):
        """Re-apply theme settings to all visible thumbnails."""
        s = self._get_preview_settings(song_id)
        for thumb in self._thumbnails:
            if hasattr(thumb, "update_settings"):
                thumb.update_settings(s)
            elif hasattr(thumb, "apply_settings"):
                thumb.apply_settings(s)

    def _apply_current_song_theme_live(self):
        """Re-resolve the current song's theme and push it to preview, thumbnails
        and any live display — so assigning/switching a per-song theme changes the
        background immediately (with the theme's transition on the live output)."""
        s = self._resolve_settings(source="songs", song_id=self.current_song_id)
        try: self.preview.apply_settings(s)
        except Exception: pass
        self._refresh_thumbnails_with_theme(self.current_song_id)
        # Only touch the live output when it's actually showing content.
        if self.display_windows and getattr(self, "_live_armed", False):
            for dw in self.display_windows:
                try: dw.apply_settings(s)
                except Exception: pass

    # ── Media player in the slides area (double-click a media item) ─────────────
    def toggle_media_player(self, path: str):
        """Show the media player in place of the slides (loading `path`), or hide it
        if it is already showing that file → back to the thumbnails/list."""
        page = getattr(self, "_media_player_page", None)
        if page is None:
            return
        showing = self._slides_stack.currentIndex() == page
        same    = getattr(self.mini_player, "_current_file", None) == path
        if showing and same:
            self.hide_media_player()
        else:
            try: self.mini_player.load_file(path)
            except Exception: pass
            self._slides_stack.setCurrentIndex(page)

    def hide_media_player(self):
        """Stop the player and return the slides area to the grid/list view."""
        page = getattr(self, "_media_player_page", None)
        if page is None:
            return
        try: self.mini_player._stop()
        except Exception: pass
        self._slides_stack.setCurrentIndex(
            1 if getattr(self, "_slide_view_mode", "grid") == "list" else 0)

    def _update_notes_bar(self, notes):
        self.current_song_notes = notes
        if notes.strip():
            self.notes_display.setText(notes)
            self.notes_bar.show()
        else:
            self.notes_bar.hide()
        self._push_stage_state()

    def _open_advanced_editor(self):
        """Open the Electron multi-slide visual editor for the current song.
        Builds a rich-slides JSON (one slide per text slide) on first open."""
        import os, json as _json, uuid

        slides = list(getattr(self, "current_slides", []) or [])
        title  = (self.song_title_edit.text().strip()
                  if hasattr(self, "song_title_edit") else "") or "Cantare"
        if not slides:
            slides = [""]

        d = os.path.join(os.path.expanduser("~"), "Cantio", "song_slides")
        os.makedirs(d, exist_ok=True)
        key = str(self.current_song_id) if getattr(self, "current_song_id", None) \
            else "".join(c for c in title if c.isalnum() or c in " -_").strip() or "cantare"
        path = os.path.join(d, f"{key}.json")

        if not os.path.exists(path):
            fmt = {"w": 1920, "h": 1080}

            def _uid():
                return "l" + uuid.uuid4().hex[:8]

            def _grad():
                return {"id": _uid(), "type": "gradient", "visible": True, "opacity": 1,
                        "x": 0.5, "y": 0.5, "w": 1, "h": 1,
                        "gradientType": "linear", "angle": 135,
                        "stops": [{"pos": 0, "color": "#1a237e"},
                                  {"pos": 1, "color": "#0d47a1"}],
                        "animate": {"mode": "none", "speed": 0.4}}

            def _text(txt):
                return {"id": _uid(), "type": "text", "text": self._plain_slide(txt),
                        "role": "lyrics",
                        "font": "Montserrat", "size": 96, "bold": True,
                        "align": "center", "color": "#ffffff",
                        "x": 0.5, "y": 0.5, "w": 0.82, "h": 0.4,
                        "opacity": 1, "visible": True}

            doc = {"name": title, "format": fmt,
                   "slides": [{"format": dict(fmt), "layers": [_grad(), _text(s)]}
                              for s in slides]}
            try:
                with open(path, "w", encoding="utf-8") as f:
                    _json.dump(doc, f, ensure_ascii=False, indent=2)
            except Exception as e:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Eroare", f"Nu am putut crea proiectul:\n{e}")
                return
        else:
            # Project already exists → refresh its lyrics from the main editor so
            # edits there show up when (re)opening the advanced editor.
            self._sync_lyrics_into_project(path, slides)

        # Watch the project so inline text edits in the advanced editor flow back
        # into the main lyrics editor when it is saved.
        self._watch_rich_project(path)

        mgr = getattr(self, "electron_display", None)
        if mgr is None:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Editor indisponibil",
                                "Subsistemul Electron nu este disponibil.")
            return
        try:
            if hasattr(mgr, "open_bg_editor_process"):
                if not mgr.open_bg_editor_process(path):
                    if hasattr(mgr, "is_running") and not mgr.is_running():
                        mgr.start()
                    mgr.open_bg_editor(path)
            else:
                if hasattr(mgr, "is_running") and not mgr.is_running():
                    mgr.start()
                mgr.open_bg_editor(path)
            try:
                self._toasts.info("🎬 Se deschide editorul avansat…")
            except Exception:
                pass
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Eroare", f"Nu am putut deschide editorul:\n{e}")

    # ── Advanced editor ↔ main lyrics editor text sync ───────────────────────
    def _plain_slide(self, s) -> str:
        """Return plain-text lyrics for a slide (strips any HTML markup)."""
        import re, html as _html
        if not isinstance(s, str):
            s = str(s) if s is not None else ""
        if "<" in s and ">" in s:
            s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
            s = re.sub(r"</p\s*>", "\n", s, flags=re.I)
            s = re.sub(r"<[^>]+>", "", s)
            s = _html.unescape(s)
        return s.strip()

    def _lyrics_layer(self, layers):
        """The lyrics text layer of a slide: prefer role=='lyrics', else first text."""
        return (next((L for L in layers if L.get("role") == "lyrics"), None)
                or next((L for L in layers if L.get("type") == "text"), None))

    def _sync_lyrics_into_project(self, path, slides):
        """main → advanced: write current lyrics into the project's lyrics layers
        (design preserved). Adds/removes slides so the count matches."""
        import json as _json, uuid, os
        try:
            with open(path, "r", encoding="utf-8") as f:
                doc = _json.load(f)
        except Exception:
            return
        pslides = doc.get("slides")
        if not isinstance(pslides, list):
            return
        fmt = doc.get("format", {"w": 1920, "h": 1080})
        texts = [self._plain_slide(s) for s in (slides or [])]

        def _uid(): return "l" + uuid.uuid4().hex[:8]
        def _grad():
            return {"id": _uid(), "type": "gradient", "visible": True, "opacity": 1,
                    "x": 0.5, "y": 0.5, "w": 1, "h": 1, "gradientType": "linear",
                    "angle": 135, "stops": [{"pos": 0, "color": "#1a237e"},
                                            {"pos": 1, "color": "#0d47a1"}],
                    "animate": {"mode": "none", "speed": 0.4}}
        def _lyr(txt):
            return {"id": _uid(), "type": "text", "text": txt, "role": "lyrics",
                    "font": "Montserrat", "size": 96, "bold": True, "align": "center",
                    "color": "#ffffff", "x": 0.5, "y": 0.5, "w": 0.82, "h": 0.4,
                    "opacity": 1, "visible": True}

        changed = False
        for i, txt in enumerate(texts):
            if i < len(pslides):
                layers = pslides[i].setdefault("layers", [])
                lyr = self._lyrics_layer(layers)
                if lyr is not None:
                    if lyr.get("text") != txt:
                        lyr["text"] = txt; changed = True
                else:
                    layers.append(_lyr(txt)); changed = True
            else:
                pslides.append({"format": dict(fmt), "layers": [_grad(), _lyr(txt)]})
                changed = True
        if texts and len(pslides) > len(texts):
            del pslides[len(texts):]; changed = True

        if changed:
            try:
                self._rich_writing = True
                with open(path, "w", encoding="utf-8") as f:
                    _json.dump(doc, f, ensure_ascii=False, indent=2)
                self._rich_cache_path = None   # force live/preview reload
            except Exception:
                pass
            finally:
                QTimer.singleShot(900, lambda: setattr(self, "_rich_writing", False))

    def _watch_rich_project(self, path):
        from PyQt6.QtCore import QFileSystemWatcher
        if getattr(self, "_rich_watcher", None) is None:
            self._rich_watcher = QFileSystemWatcher(self)
            self._rich_watcher.fileChanged.connect(self._on_rich_project_changed)
        if path not in self._rich_watcher.files():
            self._rich_watcher.addPath(path)

    def _on_rich_project_changed(self, path):
        if getattr(self, "_rich_writing", False):
            return
        # Debounce + re-add (some saves replace the file, dropping the watch).
        QTimer.singleShot(200, lambda: self._sync_lyrics_from_project(path))

    def _sync_lyrics_from_project(self, path):
        """advanced → main: pull lyrics text from the saved project into the main
        editor + slides (only for the current song; guarded against write loops)."""
        import json as _json, os
        if hasattr(self, "_rich_watcher") and os.path.exists(path) \
                and path not in self._rich_watcher.files():
            self._rich_watcher.addPath(path)          # keep watching
        if path != self._rich_project_path():
            return                                    # not the current song
        try:
            with open(path, "r", encoding="utf-8") as f:
                doc = _json.load(f)
        except Exception:
            return
        pslides = doc.get("slides")
        if not isinstance(pslides, list):
            return
        new_texts = []
        for s in pslides:
            lyr = self._lyrics_layer(s.get("layers", []))
            new_texts.append((lyr.get("text", "") if lyr else "").strip())
        cur = [self._plain_slide(s) for s in (self.current_slides or [])]
        if new_texts == cur or not any(new_texts):
            return                                    # nothing changed
        self.editor.blockSignals(True)
        self.editor.setPlainText("\n\n".join(new_texts))
        self.editor.blockSignals(False)
        if self.current_song_id:
            try:
                _fmt = (self._current_song_formatting
                        if self._current_song_formatting and
                           self._current_song_formatting.get("use_custom") else None)
                db.update_song(self.current_song_id,
                               self.song_title_edit.text().strip(),
                               self.editor.toHtml(), new_texts,
                               notes=getattr(self, "current_song_notes", ""),
                               formatting=_fmt)
            except Exception:
                pass
        self._set_slides(new_texts)
        self._rich_cache_path = None
        try:
            self._toasts.info("📝 Versuri sincronizate din editorul avansat")
        except Exception:
            pass

    # ── Dynamic presentation generator (audio-reactive) ─────────────────────
    DYN_GENRE_STYLES = {
        "Rock":     {"stops": [("#000000", 0), ("#4a0d0d", 0.5), ("#1a0505", 0.85), ("#000000", 1)],
                     "angle": 135, "gmode": "pulse", "particles": "embers",
                     "pcolor": "#ff5722", "pcolor2": "#ffca28", "text": "#ffffff",
                     "text_in": "zoom_blur", "font": "Oswald", "vignette": 0.6},
        "Pop":      {"stops": [("#ff4f9d", 0), ("#a12ff0", 0.55), ("#5b1fb0", 1)], "angle": 120, "gmode": "flow",
                     "particles": "sparks", "pcolor": "#ffffff", "pcolor2": "#ffd27f", "text": "#ffffff",
                     "text_in": "pop", "font": "Poppins", "vignette": 0.35},
        "Jazz":     {"stops": [("#140b26", 0), ("#4a2c5a", 0.5), ("#1c1030", 1)], "angle": 110, "gmode": "flow",
                     "particles": "bokeh", "pcolor": "#ffd27f", "pcolor2": "#c89bf0", "text": "#ffe9b0",
                     "text_in": "rise", "font": "Playfair Display", "vignette": 0.5},
        "Hip-Hop":  {"stops": [("#050505", 0), ("#141428", 0.6), ("#000000", 1)], "angle": 90, "gmode": "shift",
                     "particles": "sparks", "pcolor": "#00e5ff", "pcolor2": "#ff00aa", "text": "#ffffff",
                     "text_in": "slide_blur_left", "font": "Bebas Neue", "vignette": 0.55},
        "Electronic": {"stops": [("#02001a", 0), ("#0a2a6a", 0.5), ("#000814", 1)], "angle": 130, "gmode": "aurora",
                     "particles": "sparks", "pcolor": "#00ffd5", "pcolor2": "#7b2ff7", "text": "#eafcff",
                     "text_in": "zoom_blur", "font": "Russo One", "vignette": 0.5},
        "Clasic":   {"stops": [("#0b1226", 0), ("#26345a", 0.6), ("#0b1020", 1)], "angle": 100, "gmode": "none",
                     "particles": None, "text": "#f0e6c8",
                     "text_in": "fade", "font": "Merriweather", "vignette": 0.45},
        "Gospel":   {"stops": [("#1a0d00", 0), ("#5a3000", 0.5), ("#120800", 1)], "angle": 120, "gmode": "flow",
                     "particles": "bokeh", "pcolor": "#ffd27f", "pcolor2": "#ffae42", "text": "#fff3d6",
                     "text_in": "rise", "font": "Merriweather", "vignette": 0.5},
        "Folk":     {"stops": [("#0e2416", 0), ("#2c5a3a", 0.6), ("#0c1c12", 1)], "angle": 115, "gmode": "flow",
                     "particles": "fog", "pcolor": "#d9f0c8", "text": "#ffffff",
                     "text_in": "fade", "font": "Lora", "vignette": 0.4},
        "Ambient":  {"stops": [("#02090f", 0), ("#0a3a4a", 0.6), ("#020a10", 1)], "angle": 125, "gmode": "aurora",
                     "particles": "fog", "pcolor": "#7fe0ff", "text": "#eafcff",
                     "text_in": "fade", "font": "Quicksand", "vignette": 0.45},
        "Worship / Închinare": {"stops": [("#08152e", 0), ("#1d4e7a", 0.5), ("#081020", 1)],
                     "angle": 120, "gmode": "flow", "particles": "bokeh",
                     "pcolor": "#ffe9b0", "pcolor2": "#9ec5ff", "text": "#ffffff",
                     "text_in": "rise", "font": "Montserrat", "vignette": 0.5},
    }

    # Cinematic slide-to-slide transitions + per-slide text entrances per genre
    # (cycled by slide index so consecutive slides don't look identical).
    DYN_TRANSITIONS = {
        "Rock":       ["zoom_in", "wipe_left", "slide_left", "zoom_out"],
        "Pop":        ["slide_left", "slide_right", "zoom_in", "wipe_up"],
        "Jazz":       ["fade", "iris_open", "zoom_out", "fade"],
        "Hip-Hop":    ["slide_left", "wipe_right", "push_left", "zoom_in"],
        "Electronic": ["zoom_in", "iris_close", "wipe_down", "zoom_out"],
        "Clasic":     ["fade", "iris_open", "fade", "fade"],
        "Gospel":     ["fade", "zoom_in", "iris_open", "fade"],
        "Folk":       ["fade", "slide_up", "fade", "wipe_up"],
        "Ambient":    ["fade", "iris_open", "zoom_out", "fade"],
        "Worship / Închinare": ["fade", "zoom_in", "iris_open", "fade"],
    }
    DYN_TEXT_INS = {
        "Rock":       ["zoom_blur", "glitch", "zoom_blur", "slide_blur_left"],
        "Pop":        ["pop", "rise", "zoom_in", "pop"],
        "Jazz":       ["rise", "fade", "rise", "zoom_out"],
        "Hip-Hop":    ["slide_blur_left", "glitch", "slide_blur_right", "zoom_blur"],
        "Electronic": ["zoom_blur", "glitch", "zoom_blur", "flip_x"],
        "Clasic":     ["fade", "rise", "fade", "rise"],
        "Gospel":     ["rise", "fade", "rise", "zoom_in"],
        "Folk":       ["fade", "rise", "fade", "rise"],
        "Ambient":    ["fade", "fade", "rise", "fade"],
        "Worship / Închinare": ["rise", "fade", "zoom_in", "rise"],
    }

    def _dyn_style(self, genre):
        return self.DYN_GENRE_STYLES.get(genre, self.DYN_GENRE_STYLES["Worship / Închinare"])

    def _build_dynamic_slide(self, text, style, reveal, index=0, genre=""):
        import uuid
        def _u(): return "l" + uuid.uuid4().hex[:8]
        trans   = self.DYN_TRANSITIONS.get(genre, ["fade", "zoom_in", "iris_open", "fade"])
        text_in = self.DYN_TEXT_INS.get(genre, [style.get("text_in", "rise")] * 4)
        # Slight per-slide gradient rotation so the background isn't static.
        angle = style.get("angle", 120) + ((index * 9) % 26 - 13)
        layers = [{
            "id": _u(), "type": "gradient", "visible": True, "opacity": 1,
            "x": 0.5, "y": 0.5, "w": 1, "h": 1, "gradientType": "linear",
            "angle": angle,
            "stops": [{"pos": p, "color": c} for (c, p) in style["stops"]],
            "animate": {"mode": style.get("gmode", "flow"), "speed": 0.5},
            "entrance": {"type": "fade", "duration": 700, "delay": 0},
            "exit": {"type": "fade", "duration": 500, "delay": 0},
        }]
        if style.get("particles"):
            layers.append({
                "id": _u(), "type": "particles", "visible": True, "opacity": 0.9,
                "x": 0.5, "y": 0.5, "w": 1, "h": 1, "preset": style["particles"],
                "count": 160, "color": style.get("pcolor", "#ffd27f"),
                "color2": style.get("pcolor2", "#ff7043"), "speed": 1.0, "size": 1.0,
                "react": {"enabled": True, "src": "bass", "amount": 1.0},
                "entrance": {"type": "fade", "duration": 800, "delay": 100},
            })
        # Cinematic vignette: darkened edges focus the eye on the lyrics.
        vig = style.get("vignette", 0.5)
        if vig > 0:
            layers.append({
                "id": _u(), "type": "gradient", "visible": True, "opacity": 1,
                "x": 0.5, "y": 0.5, "w": 1, "h": 1, "gradientType": "radial",
                "angle": 90,
                "stops": [{"pos": 0.0, "color": "rgba(0,0,0,0)"},
                          {"pos": 0.62, "color": "rgba(0,0,0,0)"},
                          {"pos": 1.0, "color": f"rgba(0,0,0,{vig})"}],
                "animate": {"mode": "none", "speed": 0.4},
            })
        layers.append({
            "id": _u(), "type": "text", "text": self._plain_slide(text), "role": "lyrics",
            "font": style.get("font", "Montserrat"), "size": 100, "bold": True, "align": "center",
            "colorType": "solid", "color": style.get("text", "#ffffff"),
            "x": 0.5, "y": 0.5, "w": 0.84, "h": 0.42, "opacity": 1, "visible": True,
            "letterSpacing": 1,
            "reveal": bool(reveal),
            "react": {"enabled": True, "src": "bass", "target": "glow",
                      "amount": 1.0, "shake": True, "shakeAmt": 14},
            "shadow": {"enabled": True, "color": "#000000", "blur": 32, "x": 0, "y": 8},
            "entrance": {"type": text_in[index % len(text_in)], "duration": 650, "delay": 180},
            "exit": {"type": "fade", "duration": 420, "delay": 0},
        })
        return {"format": {"w": 1920, "h": 1080},
                "_transition": trans[index % len(trans)], "layers": layers}

    def _generate_dynamic_slides(self, data):
        import re
        lyrics = data.get("lyrics", "")
        blocks = [b.strip() for b in re.split(r"\n\s*\n", lyrics) if b.strip()]
        if not blocks:
            blocks = [l for l in lyrics.splitlines() if l.strip()]
        if not blocks:
            blocks = [data.get("title", "Prezentare")]
        style = self._dyn_style(data.get("genre", ""))
        genre = data.get("genre", "")
        return [self._build_dynamic_slide(b, style, data.get("reveal", True), i, genre)
                for i, b in enumerate(blocks)]

    def _dynamic_dir(self):
        import os
        d = os.path.join(os.path.expanduser("~"), "Cantio", "dynamic")
        os.makedirs(d, exist_ok=True)
        return d

    def _dynamic_sidecar(self, song_id):
        import os
        if not song_id:
            return None
        p = os.path.join(self._dynamic_dir(), f"{song_id}.json")
        return p if os.path.exists(p) else None

    def _run_saved_dynamic(self, song_id):
        import json as _json, os
        meta_path = os.path.join(self._dynamic_dir(), f"{song_id}.json")
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = _json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Eroare", f"Nu pot citi prezentarea:\n{e}")
            return
        audio = meta.get("audio", "")
        if not (audio and os.path.exists(audio)):
            QMessageBox.warning(self, "Audio lipsă",
                                f"Fișierul audio nu mai există:\n{audio}")
            return
        # Prefer the editable rich project's slides so advanced-editor edits apply.
        slides = None
        rich = self._rich_project_file(song_id)
        if os.path.exists(rich):
            try:
                with open(rich, encoding="utf-8") as f:
                    rd = _json.load(f)
                if isinstance(rd.get("slides"), list):
                    slides = rd["slides"]
            except Exception:
                pass
        if not slides:
            slides = meta.get("slides", [])
            # Migrate older presentations (metadata-only) to a rich project so the
            # design renders live and is editable from now on.
            if slides and not os.path.exists(rich):
                try:
                    with open(rich, "w", encoding="utf-8") as f:
                        _json.dump({"name": "⚡ " + meta.get("title", ""),
                                    "format": {"w": 1920, "h": 1080}, "slides": slides},
                                   f, ensure_ascii=False, indent=2)
                    self._rich_cache_path = None
                except Exception:
                    pass
        self._run_dynamic(slides, audio, meta.get("reveal", True),
                          meta.get("title", "Dinamic"))

    def _open_dynamic_generator(self):
        import os
        # If the loaded song already has a saved dynamic presentation, offer to
        # just run it (re-run from the Cântări tab) instead of regenerating.
        sidecar = self._dynamic_sidecar(getattr(self, "current_song_id", None))
        if sidecar:
            box = QMessageBox(self)
            box.setWindowTitle("Prezentare dinamică")
            box.setText("Această cântare are deja o prezentare dinamică salvată.")
            run_b = box.addButton("⚡ Rulează", QMessageBox.ButtonRole.AcceptRole)
            box.addButton("➕ Creează alta", QMessageBox.ButtonRole.ActionRole)
            box.addButton(QMessageBox.StandardButton.Cancel)
            box.exec()
            clicked = box.clickedButton()
            if clicked is run_b:
                self._run_saved_dynamic(self.current_song_id)
                return
            if clicked is None or box.buttonRole(clicked) == QMessageBox.ButtonRole.RejectRole:
                return
            # else: fall through to create a new one
        dlg = DynamicGenDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.get_data()
        audio = data["audio"]
        # "Create only" → build & save the presentation, don't play; audio is
        # optional here (kept as metadata so it can be run later from Cântări).
        if data.get("create_only"):
            self._finish_dynamic_generation(data, audio)
            return
        if not audio:
            QMessageBox.warning(self, "Audio lipsă",
                                "Alege un fișier MP3 sau lipește un URL YouTube.\n"
                                "(Sau bifează «Doar creează» ca s-o faci fără audio.)")
            return
        low = audio.lower()
        if low.startswith(("http://", "https://")) or "youtu" in low:
            self._fetch_youtube_audio(data)        # downloads → _finish_dynamic_generation
            return
        if not os.path.exists(audio):
            QMessageBox.warning(self, "Fișier inexistent",
                                f"Nu găsesc fișierul audio:\n{audio}")
            return
        self._finish_dynamic_generation(data, audio)

    def _finish_dynamic_generation(self, data, audio_path):
        """Build the dynamic presentation, save it (song + rich project), run it."""
        data = dict(data); data["audio"] = audio_path
        slides = self._generate_dynamic_slides(data)
        lyric_texts = self._dyn_slide_texts(slides)
        song_id = None
        try:
            song_id = db.add_song("⚡ " + data["title"], data["lyrics"], lyric_texts,
                                   category="Dinamic")
        except Exception as e:
            logger.debug("[Dynamic] add_song failed: %s", e)
        # Slides → rich project (renders live with its design + editable in the
        # advanced editor); audio/genre/reveal → dynamic-metadata sidecar.
        self._save_dynamic_project(song_id, data, slides, audio_path)
        if song_id:
            try: self._load_library()
            except Exception: pass
        if data.get("create_only"):
            try:
                self._toasts.success(
                    f"📄 «{data['title']}» a fost creată în Cântări (⚡). "
                    "O găsești în listă și o conduci manual sau o rulezi cu ⚡ Dinamic.")
            except Exception:
                pass
            return
        if data.get("align"):
            self._align_then_run(slides, audio_path, data["reveal"], data["title"], lyric_texts)
        else:
            self._run_dynamic(slides, audio_path, data["reveal"], data["title"])

    # ── Real audio alignment (Whisper forced-alignment, best-effort) ────────
    def _align_then_run(self, slides, audio, reveal, title, slide_texts):
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            r = QMessageBox.question(
                self, "Aliniere AI",
                "Alinierea automată folosește faster-whisper (descarcă un model AI, ~0.5 GB, "
                "prima dată mai durează).\n\nÎl instalez acum? (Nu → folosesc timing proporțional)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if r == QMessageBox.StandardButton.Yes:
                self._pending_align = (slides, audio, reveal, title, slide_texts)
                self._install_whisper_then()
            else:
                self._run_dynamic(slides, audio, reveal, title)
            return
        import threading
        from PyQt6.QtWidgets import QProgressDialog
        self._pending_align = (slides, audio, reveal, title, slide_texts)
        self._dyn_progress = QProgressDialog(
            "Se aliniază versurile cu vocea (AI)…\nPoate dura un minut.", None, 0, 0, self)
        self._dyn_progress.setWindowTitle("⚡ Aliniere")
        self._dyn_progress.setCancelButton(None)
        self._dyn_progress.show()

        def work():
            times = None
            try:
                times = self._align_lyrics_to_audio(audio, slide_texts)
            except Exception as e:
                logger.debug("[Align] failed: %s", e)
            self._dyn_align_done.emit(times)
        threading.Thread(target=work, daemon=True).start()

    def _install_whisper_then(self):
        import sys, subprocess, threading
        from PyQt6.QtWidgets import QProgressDialog
        self._dyn_progress = QProgressDialog("Se instalează faster-whisper…", None, 0, 0, self)
        self._dyn_progress.setWindowTitle("⚡ Aliniere")
        self._dyn_progress.setCancelButton(None)
        self._dyn_progress.show()
        self._dyn_pip_mode = "whisper"

        def work():
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "faster-whisper"])
                self._dyn_pip_done.emit(True, "")
            except Exception as e:
                self._dyn_pip_done.emit(False, str(e))
        threading.Thread(target=work, daemon=True).start()

    def _on_dyn_align_done(self, times):
        if getattr(self, "_dyn_progress", None):
            self._dyn_progress.close(); self._dyn_progress = None
        pend = getattr(self, "_pending_align", None)
        if not pend:
            return
        slides, audio, reveal, title, _ = pend
        self._pending_align = None
        if times and len(times) == len(slides):
            try: self._toasts.success("🎯 Versuri aliniate cu vocea")
            except Exception: pass
            self._run_dynamic(slides, audio, reveal, title, times=times)
        else:
            try: self._toasts.info("Aliniere indisponibilă — folosesc timing proporțional")
            except Exception: pass
            self._run_dynamic(slides, audio, reveal, title)

    def _align_lyrics_to_audio(self, audio_path, slide_texts):
        """Forced-align the known lyrics to the audio with faster-whisper.
        Returns a list of per-slide start times (seconds), or None on failure."""
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            return None
        import re, unicodedata

        def norm(w):
            w = unicodedata.normalize("NFKD", str(w)).encode("ascii", "ignore").decode()
            return re.sub(r"[^a-z0-9]", "", w.lower())

        try:
            # CPU int8 — reliable everywhere. device="auto"/"cuda" needs the
            # CUDA cuBLAS DLLs which most machines lack (crash at encode time).
            model = WhisperModel("small", device="cpu", compute_type="int8")
            segments, _info = model.transcribe(audio_path, word_timestamps=True, language="ro")
            rec = []   # (time, normword)
            for seg in segments:
                words = getattr(seg, "words", None)
                if words:
                    for w in words:
                        nw = norm(w.word)
                        if nw:
                            rec.append((float(w.start), nw))
                else:
                    nw = norm(seg.text)
                    if nw:
                        rec.append((float(seg.start), nw))
        except Exception as e:
            logger.debug("[Align] transcribe failed: %s", e)
            return None
        if not rec:
            return None

        # Lyric words with their slide index
        lyr = []
        for i, txt in enumerate(slide_texts):
            for w in re.split(r"\s+", txt or ""):
                nw = norm(w)
                if nw:
                    lyr.append((i, nw))
        if not lyr:
            return None

        # Greedy two-pointer alignment with a small lookahead window
        n = len(slide_texts)
        times = [None] * n
        j, WIN, last_slide = 0, 14, -1
        for (sidx, lw) in lyr:
            found = -1
            for k in range(j, min(len(rec), j + WIN)):
                rw = rec[k][1]
                if rw == lw or (len(lw) > 3 and (rw.startswith(lw[:4]) or lw.startswith(rw[:4]))):
                    found = k
                    break
            if found >= 0:
                j = found + 1
                if sidx != last_slide and times[sidx] is None:
                    times[sidx] = rec[found][0]
                    last_slide = sidx

        # Build anchors → interpolate missing slide times, keep monotonic
        if times[0] is None:
            times[0] = 0.0
        known = [(i, t) for i, t in enumerate(times) if t is not None]
        if not known:
            return None
        for a in range(len(known) - 1):
            i0, t0 = known[a]; i1, t1 = known[a + 1]
            for i in range(i0 + 1, i1):
                times[i] = t0 + (t1 - t0) * (i - i0) / (i1 - i0)
        iL, tL = known[-1]
        if iL < n - 1:
            gap = (tL - times[0]) / max(1, iL) if iL > 0 else 5.0
            for i in range(iL + 1, n):
                times[i] = tL + gap * (i - iL)
        # enforce monotonic non-decreasing
        for i in range(1, n):
            if times[i] is None or times[i] < times[i - 1]:
                times[i] = times[i - 1]
        return times

    # ── YouTube → audio (yt-dlp, background download, no ffmpeg needed) ──────
    def _fetch_youtube_audio(self, data):
        try:
            import yt_dlp  # noqa: F401
        except ImportError:
            r = QMessageBox.question(
                self, "yt-dlp lipsește",
                "Pentru a folosi un URL YouTube e nevoie de pachetul yt-dlp.\n\n"
                "Îl instalez acum? (o singură dată)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes)
            if r == QMessageBox.StandardButton.Yes:
                self._install_ytdlp_then(data)
            return
        import os, threading
        from PyQt6.QtWidgets import QProgressDialog
        url = data["audio"]
        dest_dir = os.path.join(self._dynamic_dir(), "audio")
        os.makedirs(dest_dir, exist_ok=True)
        self._pending_dyn_data = dict(data)
        self._dyn_cancel = False
        self._dyn_progress = QProgressDialog(
            "Se descarcă audio din YouTube…", "Anulează", 0, 0, self)
        self._dyn_progress.setWindowTitle("⚡ Dinamic")
        self._dyn_progress.setMinimumDuration(0)
        self._dyn_progress.canceled.connect(lambda: setattr(self, "_dyn_cancel", True))
        self._dyn_progress.show()

        def work():
            try:
                import yt_dlp
                def _hook(d):
                    if getattr(self, "_dyn_cancel", False):
                        raise Exception("cancelled")
                opts = {
                    "format": "bestaudio[ext=m4a]/bestaudio/best",
                    "outtmpl": os.path.join(dest_dir, "%(id)s.%(ext)s"),
                    "quiet": True, "no_warnings": True, "noplaylist": True,
                    "progress_hooks": [_hook],
                }
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    path = ydl.prepare_filename(info)
                if getattr(self, "_dyn_cancel", False):
                    return
                self._pending_dyn_title = info.get("title")
                self._dyn_audio_ready.emit(path)
            except Exception as e:
                if not getattr(self, "_dyn_cancel", False):
                    self._dyn_audio_error.emit(str(e))
        threading.Thread(target=work, daemon=True).start()

    def _install_ytdlp_then(self, data):
        import sys, subprocess, threading
        from PyQt6.QtWidgets import QProgressDialog
        self._dyn_pip_mode = "ytdlp"
        self._pending_dyn_data = dict(data)
        self._dyn_progress = QProgressDialog("Se instalează yt-dlp…", None, 0, 0, self)
        self._dyn_progress.setWindowTitle("⚡ Dinamic")
        self._dyn_progress.setCancelButton(None)
        self._dyn_progress.show()

        def work():
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "yt-dlp"])
                self._dyn_pip_done.emit(True, "")
            except Exception as e:
                self._dyn_pip_done.emit(False, str(e))
        threading.Thread(target=work, daemon=True).start()

    def _on_dyn_pip_done(self, ok, err):
        if getattr(self, "_dyn_progress", None):
            self._dyn_progress.close(); self._dyn_progress = None
        # MIDI support install (marker passed via the err field)
        if isinstance(err, str) and err.startswith("__midi__"):
            if ok:
                try: self._toasts.success("🎹 Suport MIDI instalat")
                except Exception: pass
                self._start_midi()
                if hasattr(self, "_midi_btn"):
                    self._midi_btn.blockSignals(True)
                    self._midi_btn.setChecked(self._midi_running)
                    self._midi_btn.blockSignals(False)
            else:
                QMessageBox.warning(self, "MIDI",
                                    "Nu am putut instala suportul MIDI:\n" + err[8:])
            return
        mode = getattr(self, "_dyn_pip_mode", "ytdlp")
        self._dyn_pip_mode = "ytdlp"
        if mode == "whisper":
            pend = getattr(self, "_pending_align", None)
            if ok and pend:
                self._align_then_run(*pend)
            else:
                if pend:
                    s, a, r, t, _ = pend
                    self._pending_align = None
                    self._run_dynamic(s, a, r, t)   # fallback: proportional timing
                if not ok:
                    QMessageBox.warning(self, "Instalare eșuată",
                                        f"Nu am putut instala faster-whisper:\n{err}")
            return
        if ok:
            self._fetch_youtube_audio(getattr(self, "_pending_dyn_data", {}))
        else:
            QMessageBox.warning(self, "Instalare eșuată",
                                f"Nu am putut instala yt-dlp:\n{err}\n\n"
                                "Instalează manual: pip install yt-dlp")

    def _on_dyn_audio_ready(self, path):
        if getattr(self, "_dyn_progress", None):
            self._dyn_progress.close(); self._dyn_progress = None
        if getattr(self, "_dyn_cancel", False):
            return
        import os
        data = getattr(self, "_pending_dyn_data", None)
        if not data:
            return
        ttl = getattr(self, "_pending_dyn_title", None)
        if ttl and (not data.get("title") or data["title"] == "Prezentare dinamică"):
            data = dict(data); data["title"] = ttl
        if not (path and os.path.exists(path)):
            QMessageBox.warning(self, "Eroare", "Descărcarea audio a eșuat.")
            return
        self._finish_dynamic_generation(data, path)

    def _on_dyn_audio_error(self, msg):
        if getattr(self, "_dyn_progress", None):
            self._dyn_progress.close(); self._dyn_progress = None
        QMessageBox.warning(self, "Eroare YouTube",
                            f"Nu am putut descărca audio:\n{msg}")

    def _rich_project_file(self, song_id):
        import os
        d = os.path.join(os.path.expanduser("~"), "Cantio", "song_slides")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, f"{song_id}.json")

    def _save_dynamic_project(self, song_id, data, slides, audio):
        import os, json as _json
        key = str(song_id) if song_id else (
            "".join(c for c in data["title"] if c.isalnum() or c in " -_").strip() or "dinamic")
        # Rich project so the dynamic design renders live AND opens in the
        # advanced editor (same multi-slide bg-engine format).
        if song_id:
            try:
                with open(self._rich_project_file(song_id), "w", encoding="utf-8") as f:
                    _json.dump({"name": "⚡ " + data["title"],
                                "format": {"w": 1920, "h": 1080}, "slides": slides},
                               f, ensure_ascii=False, indent=2)
                self._rich_cache_path = None
            except Exception as e:
                logger.debug("[Dynamic] rich save failed: %s", e)
        # Metadata (audio/genre/reveal) + slides fallback for unsaved songs.
        try:
            with open(os.path.join(self._dynamic_dir(), f"{key}.json"), "w", encoding="utf-8") as f:
                _json.dump({"title": data["title"], "genre": data["genre"],
                            "audio": audio, "reveal": data["reveal"],
                            "song_id": song_id, "slides": slides},
                           f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _run_dynamic(self, slides, audio, reveal, title, times=None):
        mgr = getattr(self, "electron_display", None)
        if mgr is None:
            QMessageBox.warning(self, "Indisponibil",
                                "Subsistemul Electron nu este disponibil.")
            return
        if hasattr(mgr, "is_running") and not mgr.is_running():
            mgr.start()
        if self.display_windows:
            wid = getattr(self.display_windows[0], "window_id", 1)
        else:
            if not getattr(self, "_electron_preview_on", False):
                self._auto_enable_hd_preview()
            wid = -1
        self._dynamic_wid = wid
        self._dynamic_n = len(slides)
        self._dynamic_active = True
        # Show the lyric slides in the thumbnail strip so the operator can follow
        # and intervene (click a slide → seek the audio there).
        texts = self._dyn_slide_texts(slides)
        try:
            self._set_slides(texts)
            self._select_slide_silent(0)
        except Exception:
            pass
        # Text-proportional timing weights (longer verses linger longer).
        weights = [max(1, len(t.split())) for t in texts]
        _times = times if (times and len(times) == len(slides)) else None
        QTimer.singleShot(400, lambda: mgr.dynamic_play(
            slides, audio, reveal, "fade", wid, weights, _times))
        self._open_dynamic_controls(title)
        try:
            self._toasts.success("⚡ Prezentare dinamică pornită — click pe un slide pentru a sincroniza")
        except Exception:
            pass

    def _dyn_slide_texts(self, slides):
        out = []
        for s in slides:
            lyr = self._lyrics_layer(s.get("layers", []))
            out.append((lyr.get("text", "") if lyr else "").strip())
        return out

    def _on_dynamic_slide(self, idx: int):
        """A dynamic presentation auto-advanced — follow it in the thumbnail strip."""
        if getattr(self, "_dynamic_active", False) and 0 <= idx < len(self.current_slides):
            self._select_slide_silent(idx)

    def _open_dynamic_controls(self, title):
        from PyQt6.QtWidgets import QSlider
        if getattr(self, "_dyn_ctrl", None) is not None:
            try: self._dyn_ctrl.close()
            except Exception: pass
        mgr = self.electron_display
        wid = getattr(self, "_dynamic_wid", 0)
        dlg = QDialog(self)
        dlg.setWindowTitle(f"⚡ {title}")
        dlg.setMinimumWidth(320)
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel(f"🎵 {title}"))
        row = QHBoxLayout()
        self._dyn_playing = True
        play_btn = QPushButton("⏸ Pauză")

        def _toggle():
            self._dyn_playing = not self._dyn_playing
            if self._dyn_playing:
                mgr.audio_resume(wid); play_btn.setText("⏸ Pauză")
            else:
                mgr.audio_pause(wid); play_btn.setText("▶ Redă")
        play_btn.clicked.connect(_toggle)
        stop_btn = QPushButton("⏹ Stop")

        def _stop():
            self._dynamic_active = False
            try: mgr.dynamic_stop(wid)
            except Exception: pass
            dlg.close()
        stop_btn.clicked.connect(_stop)
        row.addWidget(play_btn); row.addWidget(stop_btn)
        v.addLayout(row)

        vol = QSlider(Qt.Orientation.Horizontal)
        vol.setRange(0, 100); vol.setValue(100)
        vol.valueChanged.connect(lambda val: mgr.audio_volume(val / 100.0, wid))
        v.addWidget(QLabel("Volum"))
        v.addWidget(vol)

        hint = QLabel("Click pe un slide din listă = sari acolo (sincronizare manuală)")
        hint.setStyleSheet("color:#6c7086;font-size:10px;")
        hint.setWordWrap(True)
        v.addWidget(hint)

        def _on_finish(_):
            self._dynamic_active = False
            try: mgr.dynamic_stop(wid)
            except Exception: pass
        dlg.finished.connect(_on_finish)
        self._dyn_ctrl = dlg
        dlg.show()

    def _new_song(self):
        dlg = SongEditorDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            if not data["title"]:
                return
            song_id = db.add_song(**{k: v for k, v in data.items()})
            self._load_library()
            if song_id:
                reply = QMessageBox.question(
                    self, "Adaugă la serviciu",
                    f"Cântarea «{data['title']}» a fost salvată.\n\n"
                    "Adaugi automat la serviciul curent?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self._add_song_id_to_service(song_id)

    def _current_song_list_id(self):
        """Return the song_id of the currently selected item in song_list (QListView)."""
        idx = self.song_list.currentIndex()
        if not idx.isValid():
            return None
        return self.songs_model.data(idx, Qt.ItemDataRole.UserRole)

    def _edit_song(self):
        song_id = self._current_song_list_id()
        if song_id is None:
            return
        song = db.get_song(song_id)
        dlg = SongEditorDialog(self, song)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            db.update_song(song_id, **{k: v for k, v in data.items()})
            self._load_library()
            if self.current_song_id == song_id:
                self._load_content_to_editor(data["content"])
                self._set_slides(data["slides"])
                self._update_word_counter()
                self._update_notes_bar(data.get("notes", ""))

    def _delete_song(self):
        song_id = self._current_song_list_id()
        if song_id is None:
            return
        idx = self.song_list.currentIndex()
        name = self.songs_model.data(idx, Qt.ItemDataRole.DisplayRole) or ""
        if QMessageBox.question(self, t("delete_song"),
                t("delete_confirm").format(name=name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            db.delete_song(song_id)
            self._load_library()

    # ── Song context menu (right-click) ───────────────────────────────────────

    def _song_context_menu(self, pos):
        """Right-click on song_list → context menu with category move."""
        from PyQt6.QtWidgets import QMenu, QInputDialog
        idx = self.song_list.indexAt(pos)
        if not idx.isValid():
            return
        song_id = self.songs_model.data(idx, Qt.ItemDataRole.UserRole)
        if song_id is None:
            return
        song = db.get_song(song_id)
        if not song:
            return

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#1a1a2a; color:#cdd6f4; border:1px solid #313244; "
            "border-radius:6px; padding:4px; } "
            "QMenu::item { padding:6px 20px; border-radius:3px; } "
            "QMenu::item:selected { background:#313244; } "
            "QMenu::separator { background:#313244; height:1px; margin:4px 8px; }"
        )

        menu.addAction("✏️ Editează", self._edit_song)
        menu.addAction("🗑️ Șterge", self._delete_song)
        menu.addAction(f"+ {t('service')}", self._add_to_playlist)
        menu.addSeparator()

        # ── Move to category sub-menu ──────────────────────────────────────
        move_menu = menu.addMenu("📁 Mută în categorie")
        move_menu.setStyleSheet(menu.styleSheet())

        _DEFAULT_CATS = [
            "General", "Imnuri", "Psalmi", "Colinde", "Copii",
            "Tineret", "Laudă și Închinare", "Rugăciune", "Speciale",
        ]
        try:
            db_cats = db.get_all_categories()
        except Exception:
            db_cats = []
        all_cats = list(dict.fromkeys(_DEFAULT_CATS + db_cats))
        current_cat = song.get("category", "General") or "General"

        for cat in all_cats:
            prefix = "✓  " if cat == current_cat else "     "
            action = move_menu.addAction(f"{prefix}{cat}")
            if cat != current_cat:
                action.triggered.connect(
                    lambda checked=False, c=cat, sid=song_id:
                    self._move_song_to_category(sid, c)
                )
            else:
                action.setEnabled(False)

        move_menu.addSeparator()
        new_cat_action = move_menu.addAction("➕ Categorie nouă…")
        new_cat_action.triggered.connect(
            lambda checked=False, sid=song_id: self._move_to_new_category(sid)
        )

        menu.exec(self.song_list.mapToGlobal(pos))

    def _move_song_to_category(self, song_id: int, category: str):
        song = db.get_song(song_id)
        if not song:
            return
        db.update_song(
            song_id,
            song["title"],
            song.get("content", ""),
            song.get("slides", []),
            song.get("author", ""),
            category,
            song.get("language", "ro"),
            notes=song.get("notes", ""),
            formatting=song.get("formatting"),
        )
        self._load_library()
        self._refresh_categories()
        try:
            from toast_notifications import show_toast
            show_toast(f"✅ Mutată în «{category}»", "success")
        except Exception:
            pass

    def _move_to_new_category(self, song_id: int):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, "Categorie nouă", "Introduceți numele noii categorii:"
        )
        if ok and name.strip():
            self._move_song_to_category(song_id, name.strip())
            self._refresh_categories()

    # ── Bible quick reference search ──────────────────────────────────────────

    @staticmethod
    def parse_bible_reference(query: str):
        """
        Parse a quick Bible reference such as "Ioan 3:16", "Ps 23", "1Cor 13 4".
        Returns (book_name_str, chapter_int, verse_int_or_None) or None if unparseable.
        """
        import re
        abbreviations = {
            'fac': 'Facerea', 'gen': 'Facerea', 'ies': 'Ieșirea', 'ex': 'Ieșirea',
            'lev': 'Leviticul', 'num': 'Numeri', 'dt': 'Deuteronomul', 'ios': 'Iosua',
            'jud': 'Judecători', 'rut': 'Rut',
            '1sam': '1 Samuel', '2sam': '2 Samuel',
            '1imp': '1 Împărați', '2imp': '2 Împărați',
            '1cr': '1 Cronici', '2cr': '2 Cronici',
            'ezr': 'Ezra', 'neh': 'Neemia', 'est': 'Estera',
            'iov': 'Iov', 'job': 'Iov',
            'ps': 'Psalmii', 'psalm': 'Psalmii', 'psalmul': 'Psalmii',
            'prov': 'Proverbele', 'pr': 'Proverbele',
            'ecl': 'Eclesiastul', 'cnt': 'Cântarea Cântărilor',
            'is': 'Isaia', 'isa': 'Isaia', 'ier': 'Ieremia',
            'plang': 'Plângerile', 'iez': 'Ezechiel', 'ez': 'Ezechiel',
            'dan': 'Daniel', 'os': 'Osea', 'ioel': 'Ioel', 'am': 'Amos',
            'ob': 'Obadia', 'ion': 'Iona', 'mi': 'Mica', 'nah': 'Naum',
            'hab': 'Habacuc', 'tef': 'Țefania', 'hag': 'Hagai',
            'zah': 'Zaharia', 'mal': 'Maleahi',
            'mt': 'Matei', 'mat': 'Matei', 'mc': 'Marcu', 'mar': 'Marcu',
            'lc': 'Luca', 'luca': 'Luca', 'in': 'Ioan', 'ioan': 'Ioan',
            'joan': 'Ioan', 'jn': 'Ioan', 'matei': 'Matei', 'marcu': 'Marcu',
            'romani': 'Romani', 'psalmi': 'Psalmii', 'facere': 'Facerea',
            'apocalipsa': 'Apocalipsa',
            'fap': 'Faptele Apostolilor', 'fa': 'Faptele Apostolilor',
            'acts': 'Faptele Apostolilor', 'rom': 'Romani',
            '1cor': '1 Corinteni', '2cor': '2 Corinteni',
            'gal': 'Galateni', 'ef': 'Efeseni', 'eph': 'Efeseni',
            'fil': 'Filipeni', 'ph': 'Filipeni', 'col': 'Coloseni',
            '1tes': '1 Tesaloniceni', '2tes': '2 Tesaloniceni',
            '1tim': '1 Timotei', '2tim': '2 Timotei',
            'tit': 'Tit', 'flm': 'Filimon', 'evr': 'Evrei', 'heb': 'Evrei',
            'iac': 'Iacov', 'jas': 'Iacov',
            '1pt': '1 Petru', '2pt': '2 Petru',
            '1in': '1 Ioan', '2in': '2 Ioan', '3in': '3 Ioan',
            'iuda': 'Iuda', 'apoc': 'Apocalipsa', 'rev': 'Apocalipsa', 'ap': 'Apocalipsa',
        }
        q = re.sub(r'[:\,]', ' ', query.strip().lower())
        q = re.sub(r'\s+', ' ', q).strip()
        tokens = q.split()
        if not tokens:
            return None

        # Detect books with numeric prefix: "1 cor 13 4"
        if tokens[0] in ('1', '2', '3') and len(tokens) > 1:
            book_key = tokens[0] + tokens[1]
            rest = tokens[2:]
        else:
            book_key = tokens[0]
            rest = tokens[1:]

        book_name = abbreviations.get(book_key)
        glued = ""      # digits stuck to the abbreviation, e.g. "ps23" → "23"
        if not book_name:
            # Longest abbreviation first so "1cor13" matches "1cor" not "1".
            for abbr, name in sorted(abbreviations.items(), key=lambda kv: -len(kv[0])):
                if book_key.startswith(abbr):
                    book_name = name
                    tail = book_key[len(abbr):]
                    if tail.isdigit():
                        glued = tail            # chapter was glued to the book
                    break
        if not book_name:
            try:
                import re as _re
                m = _re.match(r'^([a-zăâîșț ]+?)(\d+)$', book_key)
                core = m.group(1) if m else book_key
                if m:
                    glued = m.group(2)
                books = db.get_bible_books()
                for b in books:
                    if (core in b['name'].lower() or
                            b['name'].lower().startswith(core)):
                        book_name = b['name']
                        break
            except Exception:
                pass
        if not book_name:
            return None

        # If the chapter was glued to the book (ps23), the remaining tokens are
        # the verse; otherwise rest = [chapter, verse].
        chapter = None
        verse = None
        if glued:
            chapter = int(glued)
            if rest:
                try: verse = int(rest[0])
                except ValueError: pass
        else:
            if rest:
                try: chapter = int(rest[0])
                except ValueError: return None
            if len(rest) >= 2:
                try: verse = int(rest[1])
                except ValueError: pass

        return (book_name, chapter, verse)

    def _bible_quick_search(self):
        query = self.bible_quick_edit.text().strip()
        if not query:
            return
        result = self.parse_bible_reference(query)
        if not result:
            try:
                from toast_notifications import show_toast
                show_toast("Format: Ps 23:1  sau  Ioan 3 16  sau  1Cor 13:4", "warning")
            except Exception:
                pass
            return
        book_name, chapter, verse = result
        self._navigate_to_verse(book_name, chapter, verse)

    def _select_bible_verse(self, verse):
        """Select a verse in the verse list/combo (called deferred after the
        chapter's verses have loaded)."""
        if hasattr(self, 'verse_list'):
            for i in range(self.verse_list.count()):
                item = self.verse_list.item(i)
                v = item.data(Qt.ItemDataRole.UserRole)
                if v and v.get('verse') == verse:
                    self.verse_list.setCurrentItem(item)
                    self.verse_list.scrollToItem(item)
                    self._preview_verse(item)
                    break
        if hasattr(self, 'verse_combo'):
            for i in range(self.verse_combo.count()):
                v_data = self.verse_combo.itemData(i)
                if v_data and v_data.get('verse') == verse:
                    self.verse_combo.setCurrentIndex(i)
                    break

    def _navigate_to_verse(self, book_name: str, chapter, verse):
        """Navigate the Bible panel to the given book/chapter/verse."""
        if not hasattr(self, 'book_combo'):
            return
        # Find book
        for i in range(self.book_combo.count()):
            if book_name.lower() in self.book_combo.itemText(i).lower():
                self.book_combo.setCurrentIndex(i)
                break
        if chapter is not None and hasattr(self, 'chapter_combo'):
            for i in range(self.chapter_combo.count()):
                if self.chapter_combo.itemData(i) == chapter:
                    self.chapter_combo.setCurrentIndex(i)
                    break
        # Verse selection is DEFERRED: changing the chapter reloads the verse
        # list (possibly async), so select the verse a beat later or it's missed.
        if verse is not None:
            QTimer.singleShot(150, lambda v=verse: self._select_bible_verse(v))
        # Switch to Bible tab in left panel
        try:
            if hasattr(self, '_left_tabs'):
                for i in range(self._left_tabs.count()):
                    if 'bible' in self._left_tabs.tabText(i).lower() or '📖' in self._left_tabs.tabText(i):
                        self._left_tabs.setCurrentIndex(i)
                        break
        except Exception:
            pass

    def _autosave_song(self):
        """Silent best-effort save used by closeEvent — no dialogs."""
        if not self.current_song_id:
            return
        title = self.song_title_edit.text().strip()
        plain = self.editor.toPlainText().strip()
        if not title or not plain:
            return
        content = self.editor.toHtml()
        slides = self._editor_get_slides_html()
        _fmt = (self._current_song_formatting
                if self._current_song_formatting and
                   self._current_song_formatting.get("use_custom") else None)
        db.update_song(self.current_song_id, title, content, slides,
                       notes=self.current_song_notes, formatting=_fmt)

    def _save_current_song(self):
        title = self.song_title_edit.text().strip()
        content = self.editor.toPlainText().strip()   # plain text used for validation only

        # ── Validation 1: missing title ───────────────────────────────────────
        if not title:
            reply = QMessageBox.question(
                self, "Titlu lipsă",
                "Cântarea nu are titlu.\n\nDorești să continui fără titlu?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self.song_title_edit.setFocus()
                return
            title = "(fără titlu)"
            self.song_title_edit.setText(title)

        # ── Validation 2: empty content ───────────────────────────────────────
        if not content:
            QMessageBox.warning(
                self, "Conținut gol",
                "Cântarea nu conține text.\nAdaugă cel puțin un slide înainte de salvare.",
            )
            self.editor.setFocus()
            return

        # ── Validation 3: too short (<10 words) ──────────────────────────────
        word_count = len(content.split())
        if word_count < 10:
            reply = QMessageBox.question(
                self, "Cântare prea scurtă",
                f"Textul are doar {word_count} cuvinte. Ești sigur că vrei să salvezi?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # ── Validation 4: no slide separation (no blank lines) ───────────────
        slides = [b.strip() for b in content.split("\n\n") if b.strip()]
        if len(slides) <= 1 and content.count("\n") >= 4:
            reply = QMessageBox.question(
                self, "Fără separare slide-uri",
                "Nu au fost detectate linii goale care să separe slide-urile.\n\n"
                "Vrei să împarți automat textul în slide-uri (la fiecare 4 rânduri)?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return
            if reply == QMessageBox.StandardButton.Yes:
                lines = [l for l in content.splitlines()]
                chunks, chunk = [], []
                for ln in lines:
                    chunk.append(ln)
                    if len(chunk) >= 4:
                        chunks.append("\n".join(chunk))
                        chunk = []
                if chunk:
                    chunks.append("\n".join(chunk))
                content = "\n\n".join(chunks)
                self.editor.blockSignals(True)
                self.editor.setPlainText(content)
                self.editor.blockSignals(False)
                slides = [b.strip() for b in content.split("\n\n") if b.strip()]

        # ── Validation 5: duplicate title ────────────────────────────────────
        if not self.current_song_id:
            existing = db.search_songs(title)
            dupes = [s for s in existing if s["title"].lower() == title.lower()]
            if dupes:
                reply = QMessageBox.question(
                    self, "Titlu duplicat",
                    f"Există deja o cântare cu titlul «{title}».\n\n"
                    "Ce vrei să faci?",
                    QMessageBox.StandardButton.Yes        # Suprascrie
                    | QMessageBox.StandardButton.No       # Salvează ca nouă (diferit)
                    | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Cancel,
                )
                if reply == QMessageBox.StandardButton.Cancel:
                    return
                if reply == QMessageBox.StandardButton.Yes:
                    # Overwrite the existing song
                    self.current_song_id = dupes[0]["id"]
                # No → fall through and save as new (leave current_song_id = None)

        # ── Save ──────────────────────────────────────────────────────────────
        # Store rich HTML as the canonical content; slides as HTML fragments
        html_content = self.editor.toHtml()
        html_slides = self._editor_get_slides_html()
        if not html_slides:
            html_slides = slides   # fallback: the plain-text split computed earlier
        _fmt = (self._current_song_formatting
                if self._current_song_formatting and
                   self._current_song_formatting.get("use_custom") else None)
        # Capture current slide idx before the reload resets it to 0
        _pre_save_slide_idx = max(0, getattr(self, 'current_slide_idx', 0))
        _pre_save_song_id   = self.current_song_id

        _was_new = not bool(self.current_song_id)
        if self.current_song_id:
            db.update_song(self.current_song_id, title, html_content, html_slides,
                           notes=self.current_song_notes, formatting=_fmt)
        else:
            self.current_song_id = db.add_song(title, html_content, html_slides,
                                               formatting=_fmt)
        _saved_id = self.current_song_id

        # Pre-seed the last-slide dict so _load_song_by_id() restores position
        if _saved_id and _pre_save_slide_idx > 0:
            if not hasattr(self, '_last_slide_per_song'):
                self._last_slide_per_song: dict[str, int] = {}
            self._last_slide_per_song[str(_saved_id)] = _pre_save_slide_idx

        self._load_library()
        # Auto-select the saved / newly created song in the list
        if _saved_id:
            QTimer.singleShot(150, lambda sid=_saved_id: self._select_song_in_list(sid))
        self._update_status(song_msg=f"Saved: {title}")
        self._toasts.success(f"Cântarea «{title}» a fost salvată.")
        # Offer to add to service when creating a new song
        if _was_new and _saved_id:
            reply = QMessageBox.question(
                self, "Adaugă la serviciu",
                f"Cântarea «{title}» a fost salvată.\n\n"
                "Adaugi automat la serviciul curent?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._add_song_id_to_service(_saved_id)

    # ── Editor helpers ────────────────────────────────────────────────────────

    def _load_content_to_editor(self, content: str):
        """Load song content (HTML or plain text) into the editor without triggering signals."""
        self.editor.blockSignals(True)
        if content.strip().startswith("<!DOCTYPE") or content.strip().startswith("<html"):
            self.editor.setHtml(content)
        else:
            self.editor.setPlainText(content)
        self.editor.blockSignals(False)

    def _load_slides_to_editor_with_labels(self, slides: list, auto: bool = False):
        """
        Load slides as plain text with [Label] markers so the editor shows (and
        lets you edit) section headings. With auto=True, labels are generated for
        plain-text songs that have none (detected Refren/Cor… else Strofa N).
        """
        if not slides:
            return
        has_labels = any(isinstance(s, dict) and s.get("label") for s in slides)
        if not has_labels and not auto:
            return
        lines: list[str] = []
        strofa_n = 0
        for s in slides:
            if isinstance(s, dict):
                label = s.get("label", "")
                text  = s.get("text", "")
            else:
                label = ""
                text  = str(s)
            if not label and auto:
                first = (text or "").strip().split("\n")[0].lower()
                det = None
                for kw, lab in _LABEL_KEYWORDS.items():
                    if first.startswith(kw):
                        det = lab; break
                if det:
                    label = det
                else:
                    strofa_n += 1
                    label = f"Strofa {strofa_n}"
            if label:
                lines.append(f"[{label}]")
            lines.append(text)
            lines.append("")   # blank separator
        self.editor.blockSignals(True)
        self.editor.setPlainText("\n".join(lines))
        self.editor.blockSignals(False)

    def _parse_editor_text(self, raw: str) -> list[dict]:
        """
        Parse plain-text editor content that may contain [Label] markers.
        Returns a list of {'text': ..., 'label': ...} dicts.
        Falls back to blank-line splitting when no markers are present.
        """
        slides: list[dict] = []
        current_label = ""
        current_lines: list[str] = []

        def _flush():
            text = "\n".join(current_lines).strip()
            if text:
                slides.append({"text": text, "label": current_label})

        for line in raw.split("\n"):
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                # Section marker: flush previous block then start new
                _flush()
                current_lines = []
                current_label = stripped[1:-1]
            elif stripped == "" and current_lines:
                _flush()
                current_lines = []
                current_label = ""
            elif stripped:
                current_lines.append(line)

        _flush()
        return slides

    def _editor_get_slides_html(self) -> list:
        """
        Extract per-slide HTML fragments from the rich text editor.
        Qt marks empty paragraphs with '-qt-paragraph-type:empty' in the style
        attribute, which we use as the slide boundary.
        Falls back to plain-text \n\n splitting if regex can't find the pattern.
        """
        import re as _re2
        plain = self.editor.toPlainText()
        if not plain.strip():
            return []

        # Section labels present ([Strofa 1]/[Refren]…) → return {text,label} dict
        # slides. This STRIPS the label lines from the slide text (so they never
        # show on the projector) while preserving the labels for thumbnails/editor.
        if _re2.search(r'(?m)^\s*\[[^\]\n]+\]\s*$', plain):
            return self._parse_editor_text(plain)

        # If the user hasn't explicitly touched the formatting toolbar and the
        # song has no saved custom formatting, return plain text slides so that
        # the projector uses global settings instead of QTextEdit's default font.
        _has_custom_fmt = bool(
            self._current_song_formatting and
            self._current_song_formatting.get("use_custom")
        )
        if not self._editor_modified and not _has_custom_fmt:
            return [s.strip() for s in plain.split("\n\n") if s.strip()]

        full_html = self.editor.toHtml()

        # Extract <head> inner content (contains font/style info)
        head_m = _re2.search(r'<head>(.*?)</head>', full_html, _re2.DOTALL)
        head_inner = head_m.group(1) if head_m else ''

        # Extract <body> attributes and content
        body_m = _re2.search(r'<body([^>]*)>(.*?)</body>', full_html, _re2.DOTALL)
        if not body_m:
            # Fallback: plain text
            return [s.strip() for s in plain.split("\n\n") if s.strip()]

        body_attrs = body_m.group(1)
        body_content = body_m.group(2)

        # Split on Qt's empty-paragraph marker (slide break = blank line in editor)
        parts = _re2.split(
            r'<p\s[^>]*-qt-paragraph-type:empty[^>]*>\s*(?:<br\s*/?>)?\s*</p>',
            body_content,
        )

        # Build per-slide HTML documents
        prefix = (
            '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" '
            '"http://www.w3.org/TR/REC-html40/strict.dtd">\n'
            f'<html><head>{head_inner}</head>'
            f'<body{body_attrs}>'
        )
        suffix = '</body></html>'

        slides = []
        for part in parts:
            part = part.strip()
            if part:
                slides.append(prefix + part + suffix)

        # Fallback if regex found nothing (e.g. a brand-new single-slide document)
        if not slides and plain.strip():
            slides = [full_html]

        return slides

    def _update_word_counter(self):
        """Update the word / slide counter label below the editor."""
        plain = self.editor.toPlainText()
        words = len(plain.split()) if plain.strip() else 0
        slide_count = len([b for b in plain.split("\n\n") if b.strip()])
        if hasattr(self, '_word_count_lbl'):
            self._word_count_lbl.setText(
                f"{words} cuvint{'e' if words != 1 else ''}  •  "
                f"{slide_count} slide{'-uri' if slide_count != 1 else ''}"
            )

    # ── Rich-text formatting actions ──────────────────────────────────────────

    def _fmt_toggle_bold(self):
        fmt = QTextCharFormat()
        is_bold = self.editor.fontWeight() == QFont.Weight.Bold
        weight = QFont.Weight.Normal if is_bold else QFont.Weight.Bold
        fmt.setFontWeight(weight)
        self.editor.mergeCurrentCharFormat(fmt)
        self._mark_song_as_custom_formatting(font_bold=(weight == QFont.Weight.Bold))
        self.editor.setFocus()

    def _fmt_toggle_italic(self):
        new_val = not self.editor.fontItalic()
        fmt = QTextCharFormat()
        fmt.setFontItalic(new_val)
        self.editor.mergeCurrentCharFormat(fmt)
        self._mark_song_as_custom_formatting(font_italic=new_val)
        self.editor.setFocus()

    def _fmt_toggle_underline(self):
        fmt = QTextCharFormat()
        fmt.setFontUnderline(not self.editor.fontUnderline())
        self.editor.mergeCurrentCharFormat(fmt)
        self._mark_song_as_custom_formatting()  # underline is char-only; still mark custom
        self.editor.setFocus()

    def _fmt_toggle_strike(self):
        fmt = self.editor.currentCharFormat()
        fmt.setFontStrikeOut(not fmt.fontStrikeOut())
        self.editor.mergeCurrentCharFormat(fmt)
        self._mark_song_as_custom_formatting()
        self.editor.setFocus()

    def _fmt_set_size(self, size: int):
        if size < 1:
            return
        fmt = QTextCharFormat()
        fmt.setFontPointSize(float(size))
        self.editor.mergeCurrentCharFormat(fmt)
        self._mark_song_as_custom_formatting(font_size=size)
        self.editor.setFocus()

    def _fmt_pick_color(self):
        current = getattr(self._fmt_color_btn, '_color', QColor("#ffffff"))
        color = QColorDialog.getColor(current, self, "Text color",
                                      QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            self._fmt_color_btn._color = color
            # Update button indicator swatch
            self._fmt_color_btn.setStyleSheet(
                self._fmt_color_btn.styleSheet().split("border-bottom")[0] +
                f"border-bottom: 3px solid {color.name()};"
            )
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            self.editor.mergeCurrentCharFormat(fmt)
            self._mark_song_as_custom_formatting(text_color=color.name())
        self.editor.setFocus()

    def _fmt_set_align(self, alignment):
        self.editor.setAlignment(alignment)
        for btn in self._fmt_align_btns:
            btn.setChecked(btn._align == alignment)
        _align_name = {
            Qt.AlignmentFlag.AlignLeft:    "left",
            Qt.AlignmentFlag.AlignHCenter: "center",
            Qt.AlignmentFlag.AlignRight:   "right",
        }.get(alignment, "center")
        self._mark_song_as_custom_formatting(text_align=_align_name)
        self.editor.setFocus()

    def _fmt_clear_formatting(self):
        """Remove all character formatting from the selection (or current paragraph)."""
        cursor = self.editor.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Normal)
        fmt.setFontItalic(False)
        fmt.setFontUnderline(False)
        fmt.setFontStrikeOut(False)
        fmt.setForeground(QColor("#e0e0e0"))
        cursor.mergeCharFormat(fmt)
        self.editor.mergeCurrentCharFormat(fmt)
        self.editor.setFocus()

    def _on_cursor_pos_changed(self):
        """Sync toolbar button states with the character format at cursor."""
        if not hasattr(self, '_fmt_bold_btn'):
            return
        fmt = self.editor.currentCharFormat()
        self._fmt_bold_btn.setChecked(fmt.fontWeight() >= QFont.Weight.Bold)
        self._fmt_italic_btn.setChecked(fmt.fontItalic())
        self._fmt_underline_btn.setChecked(fmt.fontUnderline())
        self._fmt_strike_btn.setChecked(fmt.fontStrikeOut())
        size = int(fmt.fontPointSize()) if fmt.fontPointSize() > 0 else 24
        self._fmt_size_spin.blockSignals(True)
        self._fmt_size_spin.setValue(size)
        self._fmt_size_spin.blockSignals(False)
        # Alignment
        align = self.editor.alignment()
        for btn in self._fmt_align_btns:
            btn.setChecked(btn._align == align)

    # ── Per-song formatting helpers ───────────────────────────────────────────

    def _update_fmt_status_label(self):
        """Refresh the formatting-status bar below the rich-text toolbar."""
        if not hasattr(self, '_fmt_status_lbl'):
            return
        has_custom = bool(
            (self._current_song_formatting and
             self._current_song_formatting.get("use_custom"))
            or getattr(self, '_editor_modified', False)
        )
        if has_custom:
            self._fmt_status_lbl.setText("Formatare personalizata  ✏")
            self._fmt_status_lbl.setStyleSheet("color: #5294e2; font-size: 10px;")
            self._fmt_reset_btn.setVisible(True)
        else:
            self._fmt_status_lbl.setText("Foloseste setarile globale  ⚙")
            self._fmt_status_lbl.setStyleSheet("color: #3a3a3a; font-size: 10px;")
            self._fmt_reset_btn.setVisible(False)

    def _mark_song_as_custom_formatting(self, **overrides):
        """
        Called by any toolbar formatting action.
        Ensures _current_song_formatting exists with use_custom=True and
        merges any key=value pairs into it (e.g. font_bold=True, font_size=48).
        """
        self._editor_modified = True
        if self._current_song_formatting is None:
            # Seed the dict from current global settings
            s = self.settings
            self._current_song_formatting = {
                "use_custom":   True,
                "font_family":  s.get("font_family",  "Arial"),
                "font_size":    int(s.get("font_size",    48)),
                "font_bold":    s.get("font_bold",    "true")  == "true",
                "font_italic":  s.get("font_italic",  "false") == "true",
                "text_color":   s.get("text_color",   "#ffffff"),
                "text_align":   s.get("text_align",   "center"),
                "line_spacing": float(s.get("line_spacing", 1.4)),
                "outline_width":int(s.get("outline_width",  2)),
                "outline_color":s.get("outline_color", "#000000"),
                "text_shadow":  s.get("text_shadow",  "true") == "true",
            }
        else:
            self._current_song_formatting["use_custom"] = True
        for k, v in overrides.items():
            self._current_song_formatting[k] = v
        self._update_fmt_status_label()

    def _reset_song_formatting(self):
        """Delete custom formatting and revert to global settings."""
        reply = QMessageBox.question(
            self, "Reseteaza formatarea",
            "Stergi formatarea personalizata a acestei cantari?\n\n"
            "Cantarea va folosi setarile globale.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._current_song_formatting = None
        self._editor_modified = False
        self._update_fmt_status_label()
        self._init_toolbar_from_formatting()
        # Persist immediately if a song is loaded
        if self.current_song_id:
            song = db.get_song(self.current_song_id)
            if song:
                db.update_song(
                    self.current_song_id, song["title"],
                    self.editor.toHtml(), self.current_slides,
                    notes=self.current_song_notes, formatting=None,
                )
        self._toasts.info("Formatarea personalizata a fost resetata.")

    def _init_toolbar_from_formatting(self):
        """
        Set toolbar button states from the current song formatting
        (or fall back to global settings when no custom formatting is set).
        """
        if not hasattr(self, '_fmt_bold_btn'):
            return
        s   = self.settings
        fmt = self._current_song_formatting or {}

        def _bval(key, global_key, default):
            v = fmt.get(key, s.get(global_key, default))
            return (v == "true") if isinstance(v, str) else bool(v)

        bold    = _bval("font_bold",   "font_bold",   True)
        italic  = _bval("font_italic", "font_italic", False)

        size_raw = fmt.get("font_size", s.get("font_size", 48))
        try:
            size = int(size_raw)
        except (TypeError, ValueError):
            size = 48

        color_s = fmt.get("text_color", s.get("text_color", "#ffffff"))
        align_s = fmt.get("text_align", s.get("text_align", "center"))

        self._fmt_bold_btn.setChecked(bold)
        self._fmt_italic_btn.setChecked(italic)

        self._fmt_size_spin.blockSignals(True)
        self._fmt_size_spin.setValue(size)
        self._fmt_size_spin.blockSignals(False)

        if hasattr(self._fmt_color_btn, '_color'):
            self._fmt_color_btn._color = QColor(color_s)

        align_map = {
            "left":   Qt.AlignmentFlag.AlignLeft,
            "center": Qt.AlignmentFlag.AlignHCenter,
            "right":  Qt.AlignmentFlag.AlignRight,
        }
        target_align = align_map.get(align_s, Qt.AlignmentFlag.AlignHCenter)
        for btn in self._fmt_align_btns:
            btn.setChecked(btn._align == target_align)

    # ── Slide reorder ─────────────────────────────────────────────────────────

    def _on_slide_context_action(self, action: str, idx: int):
        """Handle context-menu actions from SlideThumbnail."""
        slides = list(self.current_slides)
        n = len(slides)
        if not (0 <= idx < n):
            return

        if action == "move_up" and idx > 0:
            slides[idx], slides[idx - 1] = slides[idx - 1], slides[idx]
            new_idx = idx - 1
        elif action == "move_down" and idx < n - 1:
            slides[idx], slides[idx + 1] = slides[idx + 1], slides[idx]
            new_idx = idx + 1
        elif action == "move_first":
            slide = slides.pop(idx)
            slides.insert(0, slide)
            new_idx = 0
        elif action == "move_last":
            slide = slides.pop(idx)
            slides.append(slide)
            new_idx = len(slides) - 1
        elif action == "duplicate":
            slides.insert(idx + 1, slides[idx])
            new_idx = idx + 1
        elif action == "delete":
            if n == 1:
                self._toasts.warning("Nu poți șterge singurul slide.")
                return
            slides.pop(idx)
            new_idx = max(0, idx - 1)
        else:
            return

        self._apply_reordered_slides(slides, new_idx)

    def _apply_reordered_slides(self, slides: list, select_idx: int = 0):
        """Commit a new slide order: update editor, thumbnails, and DB."""
        import re as _re3

        # Rebuild editor content from the new slide order
        self.editor.blockSignals(True)
        first_html = slides[0] if slides else ""
        if first_html.lstrip().startswith("<!DOCTYPE") or first_html.lstrip().startswith("<html"):
            # HTML slides: extract body fragments and rejoin with empty-paragraph separators
            head_m = _re3.search(r'<head>(.*?)</head>', first_html, _re3.DOTALL)
            head_inner = head_m.group(1) if head_m else ''
            body_attr_m = _re3.search(r'<body([^>]*)>', first_html)
            body_attrs = body_attr_m.group(1) if body_attr_m else ''

            # Extract body content from each slide
            bodies = []
            empty_para = '<p style="-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><br /></p>'
            for sl in slides:
                bm = _re3.search(r'<body[^>]*>(.*?)</body>', sl, _re3.DOTALL)
                bodies.append(bm.group(1).strip() if bm else sl)

            combined = empty_para.join(bodies)
            new_html = (
                '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" '
                '"http://www.w3.org/TR/REC-html40/strict.dtd">\n'
                f'<html><head>{head_inner}</head>'
                f'<body{body_attrs}>{combined}</body></html>'
            )
            self.editor.setHtml(new_html)
        else:
            # Plain text slides: join with \n\n
            self.editor.setPlainText("\n\n".join(slides))
        self.editor.blockSignals(False)

        self._set_slides(slides)
        self._select_slide(max(0, min(select_idx, len(slides) - 1)))
        self._update_word_counter()

        # Persist to DB if a song is loaded
        if self.current_song_id:
            title = self.song_title_edit.text().strip() or "(fără titlu)"
            html_content = self.editor.toHtml()
            _fmt = (self._current_song_formatting
                    if self._current_song_formatting and
                       self._current_song_formatting.get("use_custom") else None)
            db.update_song(self.current_song_id, title, html_content, slides,
                           notes=self.current_song_notes, formatting=_fmt)
            self._toasts.info("Ordinea slide-urilor a fost salvată.")

    def _reorder_slides_dialog(self):
        """Open a drag-and-drop dialog for reordering slides."""
        if not self.current_slides:
            self._toasts.warning("Nu există slide-uri de reordonat.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("⇅  Reordonează slide-uri")
        dlg.setMinimumSize(420, 380)
        dlg.setStyleSheet(
            "QDialog { background: #181818; color: #e0e0e0; }"
            "QListWidget { background: #131313; border: 1px solid #2a2a2a; "
            "color: #e0e0e0; font-size: 12px; border-radius: 4px; }"
            "QListWidget::item { padding: 8px 10px; border-bottom: 1px solid #1e1e1e; }"
            "QListWidget::item:selected { background: #1c3a5a; }"
            "QPushButton { background: #1c1c1c; color: #bbb; border: 1px solid #2a2a2a; "
            "border-radius: 4px; padding: 5px 14px; }"
            "QPushButton:hover { background: #252525; color: #fff; }"
        )

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        lbl = QLabel("Trage slide-urile pentru a le reordona, sau folosește butoanele ↑ ↓")
        lbl.setStyleSheet("color: #888; font-size: 11px;")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        lw = QListWidget()
        lw.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        lw.setDefaultDropAction(Qt.DropAction.MoveAction)
        lw.setAlternatingRowColors(False)

        from PyQt6.QtGui import QTextDocument as _TDoc
        for i, slide in enumerate(self.current_slides):
            # Show plain text preview
            if slide.strip().startswith("<!DOCTYPE") or slide.strip().startswith("<html"):
                tmp = _TDoc(); tmp.setHtml(slide)
                preview = tmp.toPlainText()
            else:
                preview = slide
            first_line = preview.strip().splitlines()[0][:60] if preview.strip() else "(gol)"
            item = QListWidgetItem(f"  {i + 1}.  {first_line}")
            item.setData(Qt.ItemDataRole.UserRole, i)   # original index
            lw.addItem(item)

        layout.addWidget(lw, 1)

        # Up / Down buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        up_btn = QPushButton("↑ Sus")
        dn_btn = QPushButton("↓ Jos")

        def _move(delta):
            row = lw.currentRow()
            if row < 0:
                return
            new_row = row + delta
            if not (0 <= new_row < lw.count()):
                return
            item = lw.takeItem(row)
            lw.insertItem(new_row, item)
            lw.setCurrentRow(new_row)

        up_btn.clicked.connect(lambda: _move(-1))
        dn_btn.clicked.connect(lambda: _move(+1))
        btn_row.addWidget(up_btn)
        btn_row.addWidget(dn_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # OK / Cancel
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        btns.setStyleSheet(
            "QPushButton { min-width: 80px; }"
            "QPushButton[text='OK'] { background: #1c3a5a; color: #5294e2; "
            "border-color: #2a5080; }"
        )
        layout.addWidget(btns)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            # Rebuild slide list from current list order
            new_slides = []
            for i in range(lw.count()):
                orig_idx = lw.item(i).data(Qt.ItemDataRole.UserRole)
                new_slides.append(self.current_slides[orig_idx])
            self._apply_reordered_slides(new_slides, 0)

    # ── Slides ────────────────────────────────────────────────────────────────

    def _on_editor_changed(self):
        # ── FIX: preserve active slide so editing never jumps back to slide 1 ──
        # Capture index BEFORE _set_slides() resets it.
        keep_idx = max(0, self.current_slide_idx)

        slides = self._editor_get_slides_html()
        self._set_slides(slides)
        self._update_word_counter()

        # Silently restore the previously active slide (clamped to valid range).
        # QTimer.singleShot(0) fires after _set_slides / _select_slide(0) settle.
        if slides and keep_idx > 0:
            restore = min(keep_idx, len(slides) - 1)
            QTimer.singleShot(0, lambda _i=restore: self._select_slide_silent(_i))

        # ── Auto-save: track modification + restart 2-second debounce ─────────
        if self.current_song_id is not None:
            self._track_song_modification()
            self._autosave_debounce.start()   # restarts timer on every keystroke

    @_protect_editor_focus
    def _set_slides(self, slides):
        self.current_slides = slides
        # Track the "source" slide list for arrangements. When slides change for
        # a real reason (song load / text edit) — not an arrangement view — this
        # becomes the new base and the arrangement view resets to Original.
        if not getattr(self, "_applying_arrangement", False):
            self._song_base_slides = list(slides)
            self._active_arrangement = None
            cmb = getattr(self, "_arrangement_combo", None)
            if cmb is not None and cmb.count() and cmb.currentIndex() != 0:
                cmb.blockSignals(True)
                cmb.setCurrentIndex(0)
                cmb.blockSignals(False)
        self._thumbnails.clear()

        while self.slides_grid.count():
            item = self.slides_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        tw_base, _ = THUMB_SIZES.get(self._thumb_size_key, THUMB_SIZES["S"])
        tw = tw_base
        # Use the detected display aspect ratio for thumbnail height
        th = max(40, int(tw / self._display_aspect))
        avail_w = self.slides_container.width() or 500
        cols = max(1, (avail_w - 24) // (tw + 8))

        _theme_s = self._resolve_settings()
        by_label = getattr(self, "_slides_by_label", False)
        transp   = getattr(self, "_thumbs_transparent", False)
        _row = 0
        _col = 0
        _prev_label = None
        for i, slide in enumerate(slides):
            # Auto-assign a label when the slide is a plain string (no label yet)
            if isinstance(slide, str) and not isinstance(slide, dict):
                slide_for_thumb = slide
                auto_label = _auto_slide_label(slide, i, len(slides))
                thumb = SlideThumbnail(
                    slide_for_thumb, i, _theme_s,
                    thumb_w=tw, thumb_h=th,
                    label=auto_label,
                )
            else:
                thumb = SlideThumbnail(slide, i, _theme_s, thumb_w=tw, thumb_h=th)
            thumb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            thumb.clicked.connect(self._send_slide_to_live)
            thumb.double_clicked.connect(self._edit_slide_at)
            thumb.context_action.connect(self._on_slide_context_action)
            if transp:
                thumb._checker_bg = True   # transparency-checkerboard background
            self._thumbnails.append(thumb)
            if by_label:
                # One row per label group (Strofa 1, Refren…). Order preserved.
                lbl = getattr(thumb, "label", "") or ""
                if _prev_label is not None and lbl != _prev_label:
                    _row += 1
                    _col = 0
                self.slides_grid.addWidget(thumb, _row, _col)
                _col += 1
                _prev_label = lbl
            else:
                self.slides_grid.addWidget(thumb, i // cols, i % cols)

        # ── List view — full text via custom delegate ─────────────────────────
        self._slide_list_widget.clear()
        for i, slide in enumerate(slides):
            item = QListWidgetItem()          # delegate does all painting
            item.setData(Qt.ItemDataRole.UserRole,
                         self._slide_text(slide))               # full text (never a dict)
            item.setData(Qt.ItemDataRole.UserRole + 1, i + 1)   # 1-based number
            self._slide_list_widget.addItem(item)

        # Install delegate once (idempotent)
        if not isinstance(self._slide_list_widget.itemDelegate(), SlideListDelegate):
            self._slide_list_widget.setItemDelegate(SlideListDelegate(self._slide_list_widget))
            self._slide_list_widget.setStyleSheet(
                "QListWidget { background: #141414; border: none; outline: none; }"
                "QListWidget::item { border: none; }"
            )

        count = len(slides)
        self._slide_count_lbl.setText(
            f"{count} SLIDE{'S' if count != 1 else ''}" if count else "NO SLIDES"
        )
        self._update_status(
            slide_msg=f"{count} slide{'s' if count != 1 else ''}" if count else ""
        )

        if slides:
            # Show grid (0) or list (1) based on current mode
            self._slides_stack.setCurrentIndex(
                1 if self._slide_view_mode == "list" else 0
            )
            self._select_slide(0)
            # WYSIWYG thumbnails for rich/dynamic songs (no-op otherwise). Slight
            # delay so the Electron renderer is ready and the grid is laid out.
            QTimer.singleShot(150, self._request_wysiwyg_thumbs)
        else:
            # Show placeholder when no slides loaded
            self._slides_stack.setCurrentIndex(2)
            self.preview.update_text("")

    # ── WYSIWYG thumbnails (real bg-engine renders for rich/dynamic songs) ───
    def _request_wysiwyg_thumbs(self):
        """For songs with a rich project (advanced/dynamic), render each slide's
        real bg-engine design as its thumbnail via the running Electron renderer.
        No-op for normal songs (keeps the cheap Qt thumbnails)."""
        import os, json as _json
        mgr = getattr(self, "electron_display", None)
        if mgr is None or not hasattr(mgr, "render_thumb"):
            return
        path = self._rich_project_path()
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                slides = (_json.load(f) or {}).get("slides")
        except Exception:
            return
        if not isinstance(slides, list) or not slides:
            return
        tw_base, _ = THUMB_SIZES.get(self._thumb_size_key, THUMB_SIZES["S"])
        th = max(24, int(tw_base / (getattr(self, "_display_aspect", 16 / 9) or (16 / 9))))
        self._wysiwyg_token += 1
        token = self._wysiwyg_token
        for idx in range(min(len(slides), len(self._thumbnails))):
            try:
                mgr.render_thumb(slides[idx], tw_base, th, f"{token}:{idx}", 0)
            except Exception:
                pass

    def _on_thumb_ready(self, req_id, data_url):
        try:
            token_s, idx_s = req_id.split(":", 1)
            token, idx = int(token_s), int(idx_s)
        except Exception:
            return
        if token != getattr(self, "_wysiwyg_token", -1):
            return                                   # stale (song/view changed)
        if not (data_url and 0 <= idx < len(self._thumbnails)):
            return
        try:
            import base64
            b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
            raw = base64.b64decode(b64)
            pix = QPixmap()
            if pix.loadFromData(raw, "PNG"):
                self._thumbnails[idx].set_wysiwyg(pix)
        except Exception:
            pass

    # ── Arrangements (verse/chorus sequences, ProPresenter-style) ────────────
    def _slide_text(self, slide):
        return slide.get("text", "") if isinstance(slide, dict) else str(slide)

    def _slide_group_label(self, slide, idx, total):
        """Canonical group label for a slide. Uses the explicit section label
        (from [Label] markers / dict slides) so 'Strofa 1' and 'Strofa 2' stay
        distinct and a repeated 'Refren' reuses the same group. Slides without an
        explicit label each become their own group (S1, S2, …)."""
        if isinstance(slide, dict) and slide.get("label"):
            return str(slide["label"]).strip()
        return f"S{idx + 1}"

    def _song_groups(self, slides):
        """Return (ordered_unique_labels, {label: [slides]}). Consecutive slides
        with the same label form a group; the FIRST occurrence of each label
        defines that group's content (so a repeated 'Refren' reuses slide 1's)."""
        order, groups, cur = [], {}, None
        total = len(slides)
        for i, s in enumerate(slides):
            lbl = self._slide_group_label(s, i, total)
            if lbl != cur:
                cur = lbl
                if lbl not in groups:      # first occurrence defines the group
                    groups[lbl] = []
                    order.append(lbl)
                    _collecting = lbl
                else:
                    _collecting = None      # a later re-use → don't overwrite
            if _collecting:
                groups[_collecting].append(s)
        return order, groups

    def _arrangements_path(self, song_id):
        import os
        d = os.path.join(os.path.expanduser("~"), "Cantio", "arrangements")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, f"{song_id}.json")

    def _load_arrangements(self):
        """Load {name: [labels]} + active name for the current song."""
        import os, json as _json
        sid = getattr(self, "current_song_id", None)
        if not sid:
            return {}, None
        p = self._arrangements_path(sid)
        if not os.path.exists(p):
            return {}, None
        try:
            with open(p, encoding="utf-8") as f:
                doc = _json.load(f)
            return doc.get("arrangements", {}) or {}, doc.get("active")
        except Exception:
            return {}, None

    def _save_arrangements(self, arrangements, active):
        import json as _json
        sid = getattr(self, "current_song_id", None)
        if not sid:
            return
        try:
            with open(self._arrangements_path(sid), "w", encoding="utf-8") as f:
                _json.dump({"arrangements": arrangements, "active": active},
                           f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _refresh_arrangement_combo(self, select=None):
        cmb = getattr(self, "_arrangement_combo", None)
        if cmb is None:
            return
        arrangements, _ = self._load_arrangements()
        cmb.blockSignals(True)
        cmb.clear()
        cmb.addItem("Aranjament: Original")
        for name in arrangements.keys():
            cmb.addItem(f"⇅ {name}")
        if select:
            for i in range(cmb.count()):
                if cmb.itemText(i) == f"⇅ {select}":
                    cmb.setCurrentIndex(i); break
        cmb.blockSignals(False)

    def _on_arrangement_selected(self, idx):
        if idx <= 0:
            self._apply_arrangement(None)
        else:
            name = self._arrangement_combo.itemText(idx).replace("⇅ ", "", 1)
            self._apply_arrangement(name)

    def _apply_arrangement(self, name):
        """Rebuild current_slides from the base slides in the arrangement's order.
        name=None → original order."""
        base = getattr(self, "_song_base_slides", None) or list(self.current_slides)
        if not name:
            self._active_arrangement = None
            arrangements, _ = self._load_arrangements()
            self._save_arrangements(arrangements, None)
            self._applying_arrangement = True
            self._set_slides(list(base))
            self._applying_arrangement = False
            self._song_base_slides = list(base)
            return
        arrangements, _ = self._load_arrangements()
        seq = arrangements.get(name)
        if not seq:
            return
        _order, groups = self._song_groups(base)
        new_slides = []
        for lbl in seq:
            new_slides.extend(groups.get(lbl, []))
        if not new_slides:
            self._toasts.warning("Aranjamentul nu se potrivește cu strofele actuale.")
            return
        self._active_arrangement = name
        self._save_arrangements(arrangements, name)
        self._applying_arrangement = True
        self._set_slides(new_slides)
        self._applying_arrangement = False
        self._song_base_slides = list(base)   # keep base intact
        try:
            self._toasts.info(f"⇅ Aranjament: {name}")
        except Exception:
            pass

    def _init_song_arrangements(self):
        """Called after a song loads: capture base, populate combo, apply active."""
        self._song_base_slides = list(self.current_slides)
        arrangements, active = self._load_arrangements()
        self._refresh_arrangement_combo(select=active if active in arrangements else None)
        if active and active in arrangements:
            self._apply_arrangement(active)

    def _edit_arrangements(self):
        """Dialog to build/edit named arrangements from the song's groups."""
        from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QInputDialog
        if not getattr(self, "current_song_id", None):
            self._toasts.warning("Încarcă o cântare mai întâi.")
            return
        base = getattr(self, "_song_base_slides", None) or list(self.current_slides)
        order, groups = self._song_groups(base)
        if not order:
            self._toasts.warning("Cântarea nu are strofe de aranjat.")
            return
        arrangements, active = self._load_arrangements()

        dlg = QDialog(self)
        dlg.setWindowTitle("⇅ Aranjamente")
        dlg.setMinimumSize(560, 440)
        dlg.setStyleSheet(
            "QDialog{background:#181818;color:#e0e0e0;}"
            "QListWidget{background:#131313;border:1px solid #2a2a2a;color:#e0e0e0;"
            "font-size:12px;border-radius:4px;}"
            "QListWidget::item{padding:6px 8px;}"
            "QListWidget::item:selected{background:#1c3a5a;}"
            "QPushButton{background:#1c1c1c;color:#bbb;border:1px solid #2a2a2a;"
            "border-radius:4px;padding:5px 10px;}QPushButton:hover{background:#252525;color:#fff;}"
            "QComboBox{background:#151515;color:#ddd;border:1px solid #2a2a2a;"
            "border-radius:4px;padding:4px 8px;}")
        root = QVBoxLayout(dlg)

        top = QHBoxLayout()
        top.addWidget(QLabel("Aranjament:"))
        arr_combo = QComboBox()
        arr_combo.addItem("— nou —")
        for n in arrangements.keys():
            arr_combo.addItem(n)
        top.addWidget(arr_combo, 1)
        new_btn = QPushButton("＋ Nou"); del_btn = QPushButton("🗑 Șterge")
        top.addWidget(new_btn); top.addWidget(del_btn)
        root.addLayout(top)

        cols = QHBoxLayout()
        left = QVBoxLayout(); right = QVBoxLayout()
        left.addWidget(QLabel("Strofe disponibile"))
        avail = QListWidget()
        for lbl in order:
            avail.addItem(QListWidgetItem(f"{lbl}  ({len(groups[lbl])} slide)"))
        left.addWidget(avail)
        add_btn = QPushButton("→ Adaugă în secvență")
        left.addWidget(add_btn)
        cols.addLayout(left, 1)

        right.addWidget(QLabel("Secvența aranjamentului"))
        seqw = QListWidget()
        right.addWidget(seqw)
        seq_btns = QHBoxLayout()
        up_btn = QPushButton("↑"); down_btn = QPushButton("↓"); rm_btn = QPushButton("✕")
        for b in (up_btn, down_btn, rm_btn): seq_btns.addWidget(b)
        right.addLayout(seq_btns)
        cols.addLayout(right, 1)
        root.addLayout(cols)

        state = {"arr": dict(arrangements), "cur": None}

        def load_seq(name):
            seqw.clear()
            for lbl in state["arr"].get(name, []):
                seqw.addItem(lbl)

        def _lbl_of(avail_item_text):
            return avail_item_text.rsplit("  (", 1)[0]

        def on_arr_changed(i):
            name = arr_combo.itemText(i)
            state["cur"] = None if i == 0 else name
            load_seq(state["cur"])
        arr_combo.currentIndexChanged.connect(on_arr_changed)

        def do_new():
            name, ok = QInputDialog.getText(dlg, "Aranjament nou", "Nume:")
            name = (name or "").strip()
            if ok and name and name not in state["arr"]:
                state["arr"][name] = []
                arr_combo.addItem(name)
                arr_combo.setCurrentIndex(arr_combo.count() - 1)
        new_btn.clicked.connect(do_new)

        def do_del():
            if state["cur"] and state["cur"] in state["arr"]:
                del state["arr"][state["cur"]]
                idx = arr_combo.currentIndex()
                arr_combo.removeItem(idx)
                arr_combo.setCurrentIndex(0)
        del_btn.clicked.connect(do_del)

        def do_add():
            if not state["cur"]:
                self._toasts.warning("Creează sau alege un aranjament întâi."); return
            it = avail.currentItem()
            if not it: return
            lbl = _lbl_of(it.text())
            state["arr"][state["cur"]].append(lbl)
            seqw.addItem(lbl)
        add_btn.clicked.connect(do_add)
        avail.itemDoubleClicked.connect(lambda _: do_add())

        def move(delta):
            r = seqw.currentRow()
            if r < 0 or not state["cur"]: return
            seq = state["arr"][state["cur"]]
            nr = r + delta
            if 0 <= nr < len(seq):
                seq[r], seq[nr] = seq[nr], seq[r]
                load_seq(state["cur"]); seqw.setCurrentRow(nr)
        up_btn.clicked.connect(lambda: move(-1))
        down_btn.clicked.connect(lambda: move(1))

        def do_rm():
            r = seqw.currentRow()
            if r >= 0 and state["cur"]:
                del state["arr"][state["cur"]][r]
                load_seq(state["cur"]); seqw.setCurrentRow(min(r, seqw.count() - 1))
        rm_btn.clicked.connect(do_rm)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                              | QDialogButtonBox.StandardButton.Cancel)
        root.addWidget(bb)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)

        if arrangements:
            arr_combo.setCurrentIndex(1)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # drop empty arrangements
            clean = {k: v for k, v in state["arr"].items() if v}
            self._save_arrangements(clean, self._active_arrangement
                                    if self._active_arrangement in clean else None)
            self._refresh_arrangement_combo(select=self._active_arrangement
                                            if self._active_arrangement in clean else None)

    def _select_slide(self, idx):
        self.current_slide_idx = idx
        # Remember which slide was last viewed for this song so we can restore
        # it when the song is reloaded (e.g. after editing or switching songs).
        if self.current_song_id is not None:
            if not hasattr(self, '_last_slide_per_song'):
                self._last_slide_per_song: dict[str, int] = {}
            self._last_slide_per_song[str(self.current_song_id)] = idx
        for thumb in self._thumbnails:
            thumb.set_selected(thumb.slide_index == idx)
        if 0 <= idx < len(self.current_slides):
            self.preview.update_text(self._slide_text(self.current_slides[idx]))
        if 0 <= idx < len(self._thumbnails):
            self.slides_scroll.ensureWidgetVisible(self._thumbnails[idx])
        # Sync list view selection
        self._slide_list_widget.blockSignals(True)
        self._slide_list_widget.setCurrentRow(idx)
        self._slide_list_widget.blockSignals(False)
        self._push_stage_state()
        # Selecting a slide makes the slides the active target → blue selection.
        self._set_slides_selection_active(True)
        # Take keyboard focus AWAY from the lyrics editor so Page Up/Down and the
        # arrow keys navigate slides (handled in keyPressEvent) instead of moving
        # the text caret. Clearing focus routes key events to the main window.
        fw = QApplication.focusWidget()
        from PyQt6.QtWidgets import QLineEdit as _QLE, QTextEdit as _QTE, QPlainTextEdit as _QPTE
        if isinstance(fw, (_QLE, _QTE, _QPTE)):
            fw.clearFocus()
        # Ignore the brief focus churn that follows so the selection stays blue.
        self._slide_just_selected = True
        QTimer.singleShot(120, lambda: setattr(self, "_slide_just_selected", False))
        self.activateWindow()

    def _select_slide_silent(self, idx: int):
        """Select a slide by index WITHOUT calling setFocus() or activateWindow().
        Used by _on_editor_changed() so typing in the editor never loses the caret."""
        if not (0 <= idx < len(self.current_slides)):
            return
        self.current_slide_idx = idx
        for thumb in self._thumbnails:
            thumb.set_selected(thumb.slide_index == idx)
        slide = self.current_slides[idx]
        text = slide.get("text", slide) if isinstance(slide, dict) else str(slide)
        self.preview.update_text(text)
        if 0 <= idx < len(self._thumbnails):
            self.slides_scroll.ensureWidgetVisible(self._thumbnails[idx])
        self._slide_list_widget.blockSignals(True)
        self._slide_list_widget.setCurrentRow(idx)
        self._slide_list_widget.blockSignals(False)

    # ── Slide-selection focus state (blue = active, grey = inactive) ────────────
    @staticmethod
    def _widget_is_in(w, container):
        """True if w is container or a descendant of it."""
        if container is None or w is None:
            return False
        while w is not None:
            if w is container:
                return True
            w = w.parentWidget()
        return False

    def _set_slides_selection_active(self, active: bool):
        for thumb in getattr(self, "_thumbnails", []):
            try: thumb.set_selection_active(active)
            except Exception: pass

    def _on_focus_changed(self, old, new):
        """Slide selection is blue only while the slides are the active target.
        Selecting a slide sets it active; focus landing on ANY other control (live
        buttons like Clear Text / Black, lists, editor, combos) greys it out."""
        if new is None or new is self:
            return   # main window itself (e.g. right after selecting a slide)
        # A slide was just selected → ignore the brief focus churn (the caret is
        # restored to the editor) so the selection stays blue.
        if getattr(self, "_slide_just_selected", False):
            return
        # Focus inside the slides area (thumbnail grid / list view) keeps it active.
        if self._widget_is_in(new, getattr(self, "_slides_stack", None)):
            return
        # Anywhere else → the slides are no longer the active target.
        self._set_slides_selection_active(False)

    def _track_song_modification(self):
        """Record that the current song has been modified (captures old_content once)."""
        song_id = self.current_song_id
        if song_id is None:
            return
        if song_id not in self._modified_songs:
            # First modification this session — capture original from DB
            try:
                original = db.get_song(song_id)
                old_content = original.get("content", "") if original else ""
                title = original.get("title", "") if original else (
                    self.song_title_edit.text().strip()
                )
            except Exception:
                old_content = ""
                title = self.song_title_edit.text().strip()
            self._modified_songs[song_id] = {
                "title": title,
                "old_content": old_content,
            }
        self._show_modified_indicator(True)

    def _do_autosave(self):
        """Called by the 2-second debounce timer — silently saves current song."""
        if not self.current_song_id:
            return
        try:
            plain = self.editor.toPlainText().strip()
            if not plain:
                return
            content = self.editor.toHtml()
            slides  = self._editor_get_slides_html()
            db.update_song_content(self.current_song_id, content, slides)
            self.current_slides = slides   # keep in-memory copy in sync
            title = self._modified_songs.get(
                self.current_song_id, {}
            ).get("title", "") or self.song_title_edit.text().strip()
            print(f"[AutoSave] Salvat: {title!r} (id={self.current_song_id})")
            self._show_modified_indicator(False, saved=True)
        except Exception as e:
            print(f"[AutoSave] Eroare: {e}")

    def _show_modified_indicator(self, modified: bool, saved: bool = False):
        """Update the tiny status label in the editor header bar."""
        if not hasattr(self, "_save_indicator"):
            return
        if saved:
            self._save_indicator.setText("✅ salvat")
            self._save_indicator.setStyleSheet(
                "color: #a6e3a1; font-size: 10px; padding: 0 4px;"
            )
            QTimer.singleShot(
                2000,
                lambda: self._save_indicator.setText("") if hasattr(self, "_save_indicator") else None,
            )
        elif modified:
            self._save_indicator.setText("● modificat")
            self._save_indicator.setStyleSheet(
                "color: #f9e2af; font-size: 10px; padding: 0 4px;"
            )
        else:
            self._save_indicator.setText("")
            self._save_indicator.setStyleSheet(
                "color: #6c7086; font-size: 10px; padding: 0 4px;"
            )

    def _get_active_theme_settings(self, song_id=None, source="songs") -> dict | None:
        """
        Return a merged-settings dict for the active theme, or None if
        display_mode != "themes" or no theme is configured.

        Priority:
          1. Per-song theme (service item has a "theme" key matching current song)
          2. Per-category theme (from themes.json category_themes)
          3. Type default ("songs_active" / "bible_active")
        """
        _look = (self.settings.get("active_look") or "").strip()
        if not _look and self.settings.get("display_mode", "settings") != "themes":
            return None
        try:
            import json, os
            profiles_dir = os.path.join(os.path.expanduser("~"), "Cantio", "profiles")
            themes_path = os.path.join(profiles_dir, self._profile_name, "themes.json")
            if not os.path.exists(themes_path):
                return None
            with open(themes_path, "r", encoding="utf-8") as f:
                themes_data = json.load(f)

            theme_list = themes_data.get("list", {})

            # Priority 0: active LOOK (global override)
            if _look and _look in theme_list:
                return self._theme_to_settings(theme_list[_look])
            if self.settings.get("display_mode", "settings") != "themes":
                return None

            # 1) Per-song theme from service items
            theme_name = None
            if song_id is not None:
                for item in self._service_items:
                    if item.get("song_id") == song_id and item.get("theme"):
                        theme_name = item["theme"]
                        break

            # 2) Per-category theme
            if not theme_name and song_id is not None:
                try:
                    import db
                    song = db.get_song(song_id)
                    if song:
                        cat = song.get("category", "")
                        theme_name = themes_data.get("category_themes", {}).get(cat)
                except Exception:
                    pass

            # 3) Type default
            if not theme_name:
                key = "songs_active" if source == "songs" else "bible_active"
                theme_name = themes_data.get(key)

            if not theme_name or theme_name not in theme_list:
                return None

            theme = theme_list[theme_name]
            return self._theme_to_settings(theme)
        except Exception as _e:
            print(f"[THEME] _get_active_theme_settings error: {_e}")
            return None

    # ── Looks (live-switchable active theme, ProPresenter-style) ─────────────
    def _theme_names(self):
        import os, json
        try:
            p = self._get_themes_path()
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    return list((json.load(f).get("list") or {}).keys())
        except Exception:
            pass
        return []

    def _refresh_look_combo(self):
        cmb = getattr(self, "_look_combo", None)
        if cmb is None:
            return
        names = self._theme_names()
        active = (self.settings.get("active_look") or "").strip()
        cmb.blockSignals(True)
        cmb.clear()
        cmb.addItem("Look: (fără)")
        for n in names:
            cmb.addItem(n)
        if active and active in names:
            cmb.setCurrentIndex(names.index(active) + 1)
        cmb.blockSignals(False)

    def _on_look_selected(self, idx):
        if idx <= 0:
            self._apply_look(None)
        else:
            self._apply_look(self._look_combo.itemText(idx))

    def _apply_look(self, name):
        """Set the global active Look (theme) and re-render everything live."""
        self.settings["active_look"] = name or ""
        try:
            db.save_setting("active_look", name or "")
        except Exception:
            pass
        # Re-render thumbnails + preview + live with the new look
        try:
            self._refresh_thumbnails_with_theme(getattr(self, "current_song_id", None))
        except Exception:
            pass
        try:
            s = self._get_preview_settings(getattr(self, "current_song_id", None))
            self.preview.apply_settings(s)
        except Exception:
            pass
        if self.display_windows and self.current_slide_idx >= 0:
            self._go_live()                      # re-push current slide, new theme
        elif getattr(self, "_electron_preview_on", False):
            self._push_preview()
        try:
            self._toasts.info(f"🎨 Look: {name}" if name else "🎨 Look dezactivat")
        except Exception:
            pass

    # ── Theme helpers ─────────────────────────────────────────────────────────

    def _get_themes_path(self) -> str:
        """Return the themes.json path for the active profile."""
        import os
        profile = getattr(self, "_profile_name",
                          getattr(self, "_current_profile", "default"))
        return os.path.join(
            os.path.expanduser("~"), "Cantio", "profiles",
            profile, "themes.json")

    def _send_background_live(self, path: str):
        """Load a custom background (.json from the Fundal tab) and show it live."""
        import os, json as _json
        try:
            with open(path, "r", encoding="utf-8") as f:
                doc = _json.load(f)
        except Exception as e:
            try: self._toasts.error(f"Fundal invalid: {e}")
            except Exception: pass
            return
        self._active_bg_path = path
        self._bg_from_theme = False   # manually sent → persists across slides
        _bgfx = self.settings.get("bg_transition", "fade")
        for dw in self.display_windows:
            if hasattr(dw, "show_background"):
                try:
                    dw.show_background(doc, _bgfx)
                except Exception:
                    pass
        # Projector closed but operator preview open → mirror to the preview
        # (live windows would otherwise auto-mirror via main.js).
        if not self.display_windows and getattr(self, "_electron_preview_on", False):
            mgr = getattr(self, "electron_display", None)
            if mgr is not None:
                try:
                    mgr.show_background(doc, -1, _bgfx)
                    self._preview_bg_active = True
                except Exception:
                    pass
        # Operator preview: show the static thumbnail behind the lyrics
        try:
            from live_state import get_state
            from PyQt6.QtGui import QPixmap
            jpg = path[:-5] + ".jpg"
            if os.path.exists(jpg):
                pix = QPixmap(jpg)
                st = get_state()
                st.bg_pixmap = pix if not pix.isNull() else None
                st.notify()
        except Exception:
            pass
        try:
            self._toasts.success("🎨 Fundal trimis live")
        except Exception:
            pass

    def _clear_background_live(self):
        self._active_bg_path = None
        for dw in self.display_windows:
            if hasattr(dw, "clear_background"):
                try:
                    dw.clear_background()
                except Exception:
                    pass
        self._preview_cmd("clear_background")
        self._preview_bg_active = False

    def _send_web_live(self, url: str):
        """Show an online page (e.g. YouTube) full-screen on the live output."""
        if not url:
            return
        self._live_armed = True
        for dw in self.display_windows:
            if hasattr(dw, "show_web"):
                try: dw.show_web(url)
                except Exception: pass
        # Projector closed but operator preview open → mirror to the preview
        # (live windows otherwise auto-mirror via main.js).
        if not self.display_windows and getattr(self, "_electron_preview_on", False):
            mgr = getattr(self, "electron_display", None)
            if mgr is not None:
                try: mgr._enqueue({"type": "show_web", "url": url, "window_id": -1})
                except Exception: pass
        try: self._toasts.success("🌐 Link trimis live")
        except Exception: pass

    def _stop_web_live(self):
        for dw in self.display_windows:
            if hasattr(dw, "hide_web"):
                try: dw.hide_web()
                except Exception: pass
        mgr = getattr(self, "electron_display", None)
        if mgr is not None:
            try: mgr._enqueue({"type": "hide_web", "window_id": -1})
            except Exception: pass

    def _preview_mgr(self):
        """Return the Electron manager to mirror a live command to the operator
        preview (window_id = -1) when the projector window is closed but the
        preview is on. With a live window open, main.js already mirrors
        everything, so this returns None then (no double-send)."""
        if self.display_windows or not getattr(self, "_electron_preview_on", False):
            return None
        return getattr(self, "electron_display", None)

    def _preview_cmd(self, fn_name: str):
        """Mirror a no-arg live command (black/clear/freeze/clear_background) to
        the preview when the projector is closed but the preview is on."""
        m = self._preview_mgr()
        if m is None:
            return
        fn = getattr(m, fn_name, None)
        if fn:
            try:
                fn(-1)
            except Exception:
                pass

    def _auto_enable_hd_preview(self):
        """Enable the embedded HD (Electron) preview by default at startup. The
        old PyQt preview stays only as a silent fallback if embedding fails."""
        if getattr(self, "electron_display", None) is None:
            return
        if getattr(self, "_electron_preview_on", False):
            return
        try:
            self._electron_preview_btn.setChecked(True)
        except Exception:
            pass
        self._toggle_electron_preview(True)

    def _toggle_electron_preview(self, checked: bool):
        """Toggle the embedded Electron operator-preview (replaces the PyQt one)."""
        self._electron_preview_on = checked
        mgr = getattr(self, "electron_display", None)
        if mgr is None:
            self._electron_preview_btn.setChecked(False)
            self._electron_preview_on = False
            try: self._toasts.warning("Subsistemul Electron nu este disponibil.")
            except Exception: pass
            return
        if checked:
            if hasattr(mgr, "is_running") and not mgr.is_running():
                mgr.start()
            mgr.open_preview()   # → reports HWND → _embed_preview_hwnd() embeds it
            QTimer.singleShot(900, self._push_preview)   # seed content
            try: self._toasts.info("🖥 Preview HD — se încarcă…")
            except Exception: pass
        else:
            self._unembed_preview()
            mgr.close_preview()

    def _embed_preview_hwnd(self, hwnd: int):
        """Embed the Electron preview window's native HWND into the preview panel,
        replacing the old PyQt preview. Runs on the GUI thread (queued signal)."""
        if not getattr(self, "_electron_preview_on", False) or not hwnd:
            return
        if getattr(self, "_embed_container", None) is not None:
            return   # already embedded
        try:
            from PyQt6.QtGui import QWindow
            from PyQt6.QtWidgets import QWidget
            foreign = QWindow.fromWinId(hwnd)
            if foreign is None:
                return
            from PyQt6.QtWidgets import QSizePolicy
            container = QWidget.createWindowContainer(foreign, self._preview_wrap)
            container.setMinimumSize(80, 45)
            container.setSizePolicy(QSizePolicy.Policy.Expanding,
                                    QSizePolicy.Policy.Expanding)
            # Hide the old PyQt preview and put the embedded view in its place.
            self._preview_pw_layout.removeWidget(self.preview)
            self.preview.hide()
            self._preview_pw_layout.addWidget(container)
            self._embed_container = container
            self._embed_foreign = foreign
            # _preview_wrap drives a 16:9 height from its width; container fills it.
            self._preview_wrap.installEventFilter(self)
            self._fit_embed()
            # Seed content now that the preview window is loaded (no need to
            # open/close the live window first).
            self._push_preview()
            QTimer.singleShot(400,  self._push_preview)
            QTimer.singleShot(1200, self._push_preview)
        except Exception as e:
            logger.debug("[Electron] preview embed failed: %s", e)
            try: self._toasts.warning("Încorporarea preview-ului a eșuat (fallback).")
            except Exception: pass

    def _fit_embed(self):
        """Lock the preview panel to the projector's aspect ratio (drive height
        from width). The embedded view fills it and CSS-scales the 1920×1080
        canvas, so it always matches the live output proportionally."""
        if getattr(self, "_embed_container", None) is None:
            return
        aspect = getattr(self, "_display_aspect", 16 / 9) or (16 / 9)
        w = self._preview_wrap.width()
        if w <= 0:
            return
        # 20px horizontal + 16px vertical for padding/margins around the view
        h = int((w - 20) / aspect) + 16
        self._preview_wrap.setFixedHeight(max(60, h))

    def _unembed_preview(self):
        """Remove the embedded Electron preview and restore the PyQt preview."""
        c = getattr(self, "_embed_container", None)
        if c is not None:
            try:
                self._preview_pw_layout.removeWidget(c)
                c.setParent(None)
                c.deleteLater()
            except Exception:
                pass
            self._embed_container = None
            self._embed_foreign = None
        try:
            # Unlock the panel height that the embed locked
            self._preview_wrap.setMinimumHeight(0)
            self._preview_wrap.setMaximumHeight(16777215)
            self._preview_pw_layout.addWidget(self.preview)
            self.preview.show()
        except Exception:
            pass

    def _push_preview(self):
        """Send the current slide to the Electron preview (used to seed it and to
        keep it live when no projector window is open)."""
        if not getattr(self, "_electron_preview_on", False):
            return
        mgr = getattr(self, "electron_display", None)
        if mgr is None:
            return
        idx = self.current_slide_idx
        if not (0 <= idx < len(self.current_slides)):
            return
        s = self._resolve_settings(
            source=getattr(self, "_current_source", "songs"),
            song_id=self.current_song_id)
        # window_id = -1 → main.js sends ONLY to the preview window (no live
        # window uses that id), so this never disturbs the projector output.
        PW = -1
        try:
            mgr.apply_settings(s, PW)
            bgfx = s.get("bg_transition", "fade")
            rich = self._rich_project_path()
            if rich and getattr(self, "_rich_cache", None) and \
                    isinstance(self._rich_cache.get("slides"), list) and \
                    0 <= idx < len(self._rich_cache["slides"]):
                mgr.show_background(self._rich_cache["slides"][idx], PW, bgfx)
                self._preview_bg_active = True
                mgr.show_text("", {}, PW,
                              s.get("transition", "fade"),
                              int(s.get("transition_duration", 400)),
                              self._current_metadata)
            else:
                # Custom (bg-engine) backgrounds are normally sent only to live
                # windows; mirror them to the preview too so the background shows
                # even with no projector window open. Gradient/solid/image come
                # from apply_settings (body CSS) and need no extra message.
                bg_doc = self._resolve_preview_bg(s)
                if bg_doc is not None:
                    mgr.show_background(bg_doc, PW, bgfx)
                    self._preview_bg_active = True
                elif getattr(self, "_preview_bg_active", False):
                    mgr.clear_background(PW)
                    self._preview_bg_active = False
                slide = self.current_slides[idx]
                text = slide.get("text", "") if isinstance(slide, dict) else str(slide)
                mgr.show_text(text, {}, PW,
                              s.get("transition", "fade"),
                              int(s.get("transition_duration", 400)),
                              self._current_metadata)
        except Exception:
            pass

    def _resolve_preview_bg(self, s: dict):
        """Return the bg-engine doc for the active custom background (manually
        sent, or a theme 'fundal'), or None when the background is a plain
        gradient/solid/image handled by settings."""
        import os, json as _json
        path = getattr(self, "_active_bg_path", None)
        if not (path and os.path.exists(path)):
            path = s.get("bg_fundal_file", "") if s.get("bg_type") == "fundal" else None
        if not (path and os.path.exists(path)):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return _json.load(f)
        except Exception:
            return None

    def _rich_project_path(self):
        """Path to the current song's advanced (rich-slides) project, or None."""
        import os
        sid = getattr(self, "current_song_id", None)
        if not sid:
            return None
        p = os.path.join(os.path.expanduser("~"), "Cantio", "song_slides", f"{sid}.json")
        return p if os.path.exists(p) else None

    def _send_rich_slide_live(self, idx: int) -> bool:
        """If the current song has an advanced project, send slide `idx` live as a
        custom background (full design incl. its own text). Returns True if used."""
        import os, json as _json
        path = self._rich_project_path()
        if not path:
            return False
        try:
            mtime = os.path.getmtime(path)
        except Exception:
            return False
        if (getattr(self, "_rich_cache_path", None) != path
                or getattr(self, "_rich_cache_mtime", None) != mtime):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._rich_cache = _json.load(f)
                self._rich_cache_path = path
                self._rich_cache_mtime = mtime
            except Exception:
                self._rich_cache = None
                self._rich_cache_path = None
                return False
        doc = getattr(self, "_rich_cache", None)
        slides = doc.get("slides") if isinstance(doc, dict) else None
        if not isinstance(slides, list) or not (0 <= idx < len(slides)):
            return False
        self._active_bg_path = path
        _bgfx = self.settings.get("bg_transition", "fade")
        for dw in self.display_windows:
            if hasattr(dw, "show_background"):
                try:
                    dw.show_background(slides[idx], _bgfx)
                except Exception:
                    pass
        return True

    def _apply_custom_bg_from_settings(self, s: dict):
        """If the resolved (theme) settings request a custom 'fundal' background,
        send it live; otherwise clear any active custom background."""
        import os
        if s.get("bg_type") == "fundal":
            f = s.get("bg_fundal_file", "")
            if f and os.path.exists(f):
                if getattr(self, "_active_bg_path", None) != f:
                    self._send_background_live(f)
                self._bg_from_theme = True
                return
        # Only clear a theme-driven background; a manually-sent one persists.
        if getattr(self, "_active_bg_path", None) and getattr(self, "_bg_from_theme", False):
            self._clear_background_live()

    def _theme_to_settings(self, theme: dict) -> dict:
        """
        Convert a themes.json theme dict into a flat settings dict compatible
        with display.js / ElectronDisplayProxy.apply_settings().
        Merges over the current global settings so unrelated keys are preserved.
        """
        merged = dict(self.settings)

        t  = theme.get("text",       {})
        bg = theme.get("background", {})
        l  = theme.get("layout",     {})
        a  = theme.get("advanced",   {})

        # ── Text ──────────────────────────────────────────────────────────────
        if t.get("font_family"):  merged["font_family"]   = t["font_family"]
        if t.get("font_size"):    merged["font_size"]     = str(t["font_size"])
        if t.get("font_bold") is not None:
            merged["font_bold"]   = t["font_bold"]
        if t.get("font_italic") is not None:
            merged["font_italic"] = t["font_italic"]
        if t.get("text_color"):   merged["text_color"]    = t["text_color"]
        if t.get("text_shadow") is not None:
            merged["text_shadow"] = t["text_shadow"]
        if t.get("outline_width") is not None:
            merged["outline_width"] = str(t["outline_width"])
        if t.get("outline_color"):
            merged["outline_color"] = t["outline_color"]
        if t.get("line_spacing"):
            merged["line_spacing"] = str(t["line_spacing"])
        if t.get("uppercase") is not None:
            merged["uppercase"]   = t["uppercase"]
        if t.get("text_align"):
            merged["text_align"]  = t["text_align"]
        # Echo (big faint text behind)
        if t.get("echo_enabled") is not None:
            merged["text_echo"]         = t["echo_enabled"]
        if t.get("echo_scale"):
            merged["text_echo_scale"]   = str(t["echo_scale"])
        if t.get("echo_opacity"):
            merged["text_echo_opacity"] = str(t["echo_opacity"])
        if t.get("echo_color"):
            merged["text_echo_color"]   = t["echo_color"]
        # Cascade (repeated text, centre highlighted)
        if t.get("cascade_enabled") is not None:
            merged["text_cascade"]        = t["cascade_enabled"]
        if t.get("cascade_lines"):
            merged["cascade_lines"]       = str(t["cascade_lines"])
        if t.get("cascade_gap"):
            merged["cascade_gap"]         = str(t["cascade_gap"])
        if t.get("cascade_hl_color"):
            merged["cascade_hl_color"]    = t["cascade_hl_color"]
        if t.get("cascade_dim_opacity"):
            merged["cascade_dim_opacity"] = str(t["cascade_dim_opacity"])
        if t.get("cascade_glow") is not None:
            merged["cascade_glow"]        = t["cascade_glow"]
        # Chaotic movement
        if t.get("chaos_enabled") is not None:
            merged["text_chaos"]       = t["chaos_enabled"]
        if t.get("chaos_amp"):
            merged["text_chaos_amp"]   = str(t["chaos_amp"])
        if t.get("chaos_speed"):
            merged["text_chaos_speed"] = str(t["chaos_speed"])
        # Gradient / animated text colour
        if t.get("color_type"):
            merged["text_color_type"]  = t["color_type"]
        if t.get("grad_from"):
            merged["text_grad_from"]   = t["grad_from"]
        if t.get("grad_to"):
            merged["text_grad_to"]     = t["grad_to"]
        # Neon glow
        if t.get("glow_enabled") is not None:
            merged["text_glow"]        = t["glow_enabled"]
        if t.get("glow_color"):
            merged["text_glow_color"]  = t["glow_color"]
        if t.get("glow_size"):
            merged["text_glow_size"]   = str(t["glow_size"])
        if t.get("shadow_color"):
            merged["shadow_color"] = t["shadow_color"]

        # ── Text box background (FreeShow-style) ────────────────────────────────
        tb = theme.get("text_box", {})
        if tb:
            merged["text_box_enabled"]   = bool(tb.get("enabled", False))
            merged["text_box_color"]     = tb.get("color", "#000000")
            merged["text_box_opacity"]   = float(tb.get("opacity", 0.6))
            merged["text_box_padding_h"] = int(tb.get("padding_h", 20))
            merged["text_box_padding_v"] = int(tb.get("padding_v", 12))
            merged["text_box_radius"]    = int(tb.get("radius", 8))
            merged["text_box_fit"]       = tb.get("fit", "per_line")
            merged["text_box_style"]     = tb.get("style", "solid")
            merged["text_box_color2"]    = tb.get("color2", "#1a1a1a")

        # ── Words of Jesus styling ──────────────────────────────────────────────
        jw = theme.get("jesus_words", {})
        if jw:
            merged["jesus_enabled"]     = bool(jw.get("enabled", False))
            merged["jesus_color"]       = jw.get("color", "#ff6b6b")
            merged["jesus_bold"]        = bool(jw.get("bold", False))
            merged["jesus_italic"]      = bool(jw.get("italic", True))
            merged["jesus_size_offset"] = int(jw.get("size_offset", 0))

        # ── Background ────────────────────────────────────────────────────────
        bg_type = bg.get("type", "color")
        merged["bg_type"] = bg_type

        if bg_type == "color":
            if bg.get("color"): merged["bg_color"] = bg["color"]
            merged["bg_image"] = ""
            merged["bg_video"] = ""
            merged["bg_transparent"] = "false"

        elif bg_type == "gradient":
            merged["bg_grad_c1"]  = bg.get("grad_c1",
                                    bg.get("grad_color1", "#000033"))
            merged["bg_grad_c2"]  = bg.get("grad_c2",
                                    bg.get("grad_color2", "#000000"))
            merged["bg_grad_dir"] = bg.get("grad_dir", "Sus→Jos")
            merged["bg_image"] = ""
            merged["bg_transparent"] = "false"

        elif bg_type == "image":
            merged["bg_image"]   = bg.get("image", bg.get("path", ""))
            merged["bg_opacity"] = str(bg.get("opacity", 0.85))
            merged["bg_video"]   = ""
            merged["bg_transparent"] = "false"

        elif bg_type == "video":
            merged["bg_image"]   = bg.get("video",
                                   bg.get("image", bg.get("path", "")))
            merged["bg_opacity"] = str(bg.get("opacity", 1.0))
            merged["bg_type"]    = "video"
            merged["bg_transparent"] = "false"

        elif bg_type == "camera":
            merged["bg_type"]  = "camera"
            # Which camera is chosen globally in Media → Feeds, not per-theme.
            merged["bg_image"] = str(self.settings.get("feeds_camera", "0"))
            merged["bg_transparent"] = "false"

        elif bg_type == "camera_gradient":
            merged["bg_type"]       = "camera_gradient"
            merged["bg_image"]      = str(self.settings.get("feeds_camera", "0"))
            merged["bg_grad_c1"]    = bg.get("grad_color", "#000033")
            merged["bg_grad_dir"]   = bg.get("grad_dir", "Radial")
            merged["bg_grad_opacity"] = str(bg.get("grad_opacity", 0.5))
            merged["bg_transparent"] = "false"

        elif bg_type == "animated_gradient":
            merged["bg_type"]          = "animated_gradient"
            merged["anim_grad_colors"] = bg.get("anim_colors",
                                          ['#1a237e', '#6a1b9a', '#0d47a1'])
            merged["anim_grad_speed"]  = str(bg.get("anim_speed", 0.5))
            merged["bg_image"] = ""
            merged["bg_video"] = ""
            merged["bg_transparent"] = "false"

        elif bg_type == "transparent":
            merged["bg_transparent"] = "true"
            merged["bg_color"]  = "#00000000"
            merged["bg_image"]  = ""
            merged["bg_video"]  = ""

        elif bg_type == "fundal":
            merged["bg_type"]         = "fundal"
            merged["bg_fundal_file"]  = bg.get("fundal_file", "")

        # ── Layout ────────────────────────────────────────────────────────────
        if l.get("margin"):
            merged["margin"]       = str(l["margin"])
        if l.get("valign"):
            merged["text_valign"]  = l["valign"]
        if l.get("verse_zone"):
            merged["bible_verse_zone"] = l["verse_zone"]
        if l.get("ref_zone"):
            merged["bible_ref_zone"]   = l["ref_zone"]
        if l.get("ref_font_size"):
            merged["ref_font_size"]    = l["ref_font_size"]
        if l.get("ref_color"):
            merged["ref_color"]        = l["ref_color"]

        # ── Advanced Bible reference styling ────────────────────────────────────
        ref = l.get("reference", {})
        if ref:
            if ref.get("size"):    merged["ref_font_size"] = ref["size"]
            if ref.get("color"):   merged["ref_color"]     = ref["color"]
            merged["ref_bold"]      = bool(ref.get("bold", False))
            merged["ref_italic"]    = bool(ref.get("italic", False))
            merged["ref_uppercase"] = bool(ref.get("uppercase", False))
            merged["ref_bg_enabled"]= bool(ref.get("bg_enabled", False))
            merged["ref_bg_color"]  = ref.get("bg_color", "#99000000")
            merged["ref_padding"]   = int(ref.get("padding", 8))
            merged["ref_format"]    = int(ref.get("format", 0))
            merged["ref_show_book"]    = bool(ref.get("show_book", True))
            merged["ref_show_chapter"] = bool(ref.get("show_chapter", True))
            merged["ref_show_verse"]   = bool(ref.get("show_verse", True))

        # ── Advanced ──────────────────────────────────────────────────────────
        if a.get("transition"):
            merged["transition"]          = a["transition"]
        if a.get("transition_duration"):
            merged["transition_duration"] = str(a["transition_duration"])

        merged["source"] = theme.get("type", "songs")
        return merged

    def _resolve_settings(self, source: str = "songs",
                           song_id=None) -> dict:
        """
        Return the correct settings dict for the active display mode.
        - display_mode == "settings"  → global self.settings
        - display_mode == "themes"    → theme merged over self.settings
        """
        import os, json
        look = (self.settings.get("active_look") or "").strip()
        themes_mode = self.settings.get("display_mode", "settings") == "themes"
        if not look and not themes_mode:
            return dict(self.settings)
        try:
            themes_path = self._get_themes_path()
            if not os.path.exists(themes_path):
                return dict(self.settings)
            with open(themes_path, "r", encoding="utf-8") as f:
                themes = json.load(f)
            theme_list  = themes.get("list", {})
            cat_themes  = themes.get("category_themes", {})
            song_themes = themes.get("song_themes", {})

            # Priority 0: active LOOK — a global override applied live to
            # everything (songs + bible), trumping per-song/category/default.
            if look and look in theme_list:
                return self._theme_to_settings(theme_list[look])
            if not themes_mode:
                return dict(self.settings)

            # Priority 1: per-song theme from service items
            theme_name = None
            if song_id is not None:
                theme_name = song_themes.get(str(song_id))
                if not theme_name:
                    for item in self._service_items:
                        if item.get("song_id") == song_id and item.get("theme"):
                            theme_name = item["theme"]
                            break

            # Priority 2: per-category theme
            if not theme_name and song_id is not None and source == "songs":
                try:
                    song = db.get_song(song_id)
                    if song:
                        cat = song.get("category", "")
                        theme_name = cat_themes.get(cat)
                except Exception:
                    pass

            # Priority 3: type default
            if not theme_name:
                key = "songs_active" if source == "songs" else "bible_active"
                theme_name = themes.get(key, "")

            if not theme_name or theme_name not in theme_list:
                return dict(self.settings)
            return self._theme_to_settings(theme_list[theme_name])
        except Exception as _e:
            print(f"[THEME] _resolve_settings error: {_e}")
            return dict(self.settings)

    @_protect_editor_focus
    def _send_slide_to_live(self, idx: int):
        """
        Central navigation function — selects a slide by index and pushes it
        to the display window if one is open.  All navigation paths (thumbnail
        click, list click, arrow keys, prev/next buttons) funnel through here
        so that _go_live() is called exactly once per user action.
        """
        if not (0 <= idx < len(self.current_slides)):
            return
        # Explicit operator choice → a Display opened from now on shows this slide.
        self._live_armed = True
        # During a dynamic presentation, clicking a slide SEEKS the audio there
        # (operator intervention) instead of pushing a static slide.
        if getattr(self, "_dynamic_active", False):
            mgr = getattr(self, "electron_display", None)
            n = max(1, getattr(self, "_dynamic_n", len(self.current_slides)))
            if mgr is not None:
                try: mgr.audio_seek(idx / n, getattr(self, "_dynamic_wid", 0))
                except Exception: pass
            self._select_slide_silent(idx)
            return
        self._record_slide_change(idx)
        self._select_slide(idx)
        if self.display_windows:
            self._go_live()
        elif getattr(self, "_electron_preview_on", False):
            self._push_preview()   # keep the Electron preview live with no projector
        self._schedule_recorded_advance(idx)
        self._push_remote_state()

    # ── Per-slide timing: record / playback ─────────────────────────────────────

    def _timings_for_song(self):
        return self._slide_timings.get(str(self.current_song_id), [])

    def _toggle_timing_record(self, checked: bool):
        import time
        self._timing_rec_active = checked
        if checked:
            # Playback and record are mutually exclusive
            if self._timing_play_active:
                self._rec_play_btn.setChecked(False)
                self._toggle_timing_play(False)
            n = len(self.current_slides)
            self._slide_timings[str(self.current_song_id)] = [None] * n
            self._timing_last_ts = time.monotonic()
            try: self._toasts.info("⏺ Înregistrez timpii — schimbă slide-urile normal.")
            except Exception: pass
        else:
            # Finalize the currently-shown slide's duration
            self._record_slide_change(None)
            self._timing_last_ts = None
            self._persist_timings()
            try: self._toasts.success("⏺ Timpi salvați — apasă ⏵ pentru redare.")
            except Exception: pass

    def _record_slide_change(self, new_idx):
        """Log how long the previously-shown slide stayed (while recording)."""
        import time
        if not self._timing_rec_active or self._timing_last_ts is None:
            return
        now = time.monotonic()
        dur = max(0.5, now - self._timing_last_ts)
        timings = self._slide_timings.setdefault(str(self.current_song_id), [])
        prev = self.current_slide_idx
        while len(timings) <= prev:
            timings.append(None)
        if 0 <= prev < len(timings):
            timings[prev] = round(dur, 1)
        self._timing_last_ts = now

    def _persist_timings(self):
        try:
            c = db.get_cache()
            store = c.get("slide_timings", {})
            store[str(self.current_song_id)] = self._slide_timings.get(
                str(self.current_song_id), [])
            c["slide_timings"] = store
            db.save_cache(c)
        except Exception:
            pass

    def _load_timings(self):
        try:
            c = db.get_cache()
            store = c.get("slide_timings", {})
            t = store.get(str(self.current_song_id))
            if t:
                self._slide_timings[str(self.current_song_id)] = list(t)
                return True
        except Exception:
            pass
        return bool(self._slide_timings.get(str(self.current_song_id)))

    def _toggle_timing_play(self, checked: bool):
        self._timing_play_active = checked
        if checked:
            if self._timing_rec_active:
                self._rec_btn.setChecked(False)
                self._toggle_timing_record(False)
            if not self._load_timings():
                self._rec_play_btn.setChecked(False)
                self._timing_play_active = False
                try: self._toasts.warning("Niciun timp înregistrat pentru această cântare.")
                except Exception: pass
                return
            try: self._toasts.info("⏵ Auto-avans pe timpi înregistrați.")
            except Exception: pass
            # Schedule from the current slide
            self._schedule_recorded_advance(self.current_slide_idx)
        else:
            self._rec_play_timer.stop()

    def _schedule_recorded_advance(self, idx):
        if not self._timing_play_active or not self._is_live:
            return
        timings = self._timings_for_song()
        if 0 <= idx < len(timings) and timings[idx]:
            self._rec_play_timer.start(int(float(timings[idx]) * 1000))
        else:
            self._rec_play_timer.stop()

    def _recorded_advance_tick(self):
        if not self._timing_play_active or not self._is_live:
            return
        if self.current_slide_idx < len(self.current_slides) - 1:
            self._next_slide()   # funnels through _send_slide_to_live → reschedules
        else:
            self._rec_play_timer.stop()
            self._rec_play_btn.setChecked(False)
            self._timing_play_active = False

    def _edit_slide_at(self, idx):
        """Double-click: focus the editor at the start of that slide's text."""
        if 0 <= idx < len(self.current_slides):
            content = self.editor.toPlainText()
            slides = [b.strip() for b in content.split("\n\n") if b.strip()]
            if 0 <= idx < len(slides):
                target = slides[idx]
                cursor = self.editor.document().find(target)
                if not cursor.isNull():
                    self.editor.setTextCursor(cursor)
                    self.editor.setFocus()

    def _new_slide(self):
        current = self.editor.toPlainText().rstrip()
        self.editor.setPlainText(current + "\n\n" if current else "")
        cursor = self.editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    # ── Display ───────────────────────────────────────────────────────────────

    def _go_live(self):
        if self._is_frozen:
            self._toasts.warning("Proiectorul este oprit (Freeze). Apasă 🔓 Unfreeze.")
            return
        if not self.display_windows:
            self._toasts.info("Se deschide displayul…")
            self._open_display()
            if not self.display_windows:
                return   # user cancelled (e.g. no secondary monitor)
        if self.current_slide_idx < 0:
            self._toasts.warning("Nu există slide selectat.")
            return
        self._live_armed = True   # explicit go-live → Display shows content
        targets = self._target_windows()
        if self._in_pres_mode and self._pres_slides_data:
            idx = self.current_slide_idx
            if 0 <= idx < len(self._pres_slides_data):
                self._select_pres_slide(idx)
                total = len(self._pres_slides_data)
                self._update_status(
                    slide_msg=f"Slide {idx + 1}/{total}")
        elif self.current_slides:
            text = self._slide_text(self.current_slides[self.current_slide_idx])
            if not text.strip():
                self._toasts.warning("Slide gol — nu există text de afișat.")
                self._increment_warnings()
            elif len(text) > 200:
                self._toasts.warning(
                    f"Slide lung ({len(text)} caractere). "
                    "Consideră împărțirea în mai multe slide-uri."
                )
                self._increment_warnings()
            # Dual language: prepend/append translation if active
            if self._dual_lang_active and self.current_song_id:
                text = self._build_dual_lang_text(text)

            # Build per-song formatting payload (only when use_custom=True)
            _live_fmt = None
            if (self._current_song_formatting and
                    self._current_song_formatting.get("use_custom")):
                _live_fmt = dict(self._current_song_formatting)
                _live_fmt["_slide_idx"] = self.current_slide_idx

            # Resolve settings: theme (if active) merged over globals
            _live_settings = self._resolve_settings(
                source="songs", song_id=self.current_song_id
            )
            _rich = self._send_rich_slide_live(self.current_slide_idx)
            if not _rich:
                self._apply_custom_bg_from_settings(_live_settings)
            for dw in targets:
                dw.apply_settings(_live_settings)
                dw.show_text("" if _rich else text, _live_fmt,
                             metadata=self._current_metadata)
            # Push metadata into LiveState so preview copyright overlay works
            from live_state import get_state as _gs
            _gs()._metadata = dict(self._current_metadata or {})
            # Sync render engine so preview shows same text
            self.render_engine.set_text(text, _live_fmt)
            self._is_live = True
            if not self._live_timer.isActive():
                self._live_timer.start(600)
            total = len(self.current_slides)
            target_name = (
                f" → {self.display_windows[self._send_target_idx].window_name}"
                if 0 <= self._send_target_idx < len(self.display_windows) else ""
            )
            self._update_status(slide_msg=f"Slide {self.current_slide_idx + 1}/{total}{target_name}")
            self._push_stage_state()
        else:
            self._toasts.warning("Nu există slide-uri de afișat.")
        self._push_remote_state()

    def _distribute_frame(self, pixmap) -> None:
        """
        Slot — receives a QPixmap from RenderEngine.frame_ready (kept for
        backward compatibility and preview purposes only).
        DisplayCanvas.set_frame() is a no-op in v4: display windows render
        independently via show_text() → canvas.show_text() → paintEvent().
        RenderEngine frames are consumed only by PreviewWidget (preview_ready).
        """
        for dw in self.display_windows:
            if hasattr(dw, 'canvas'):
                dw.canvas.set_frame(pixmap)   # no-op in v4 DisplayCanvas

    def _black_screen(self):
        self._set_slides_selection_active(False)   # live command → slides not the target
        for dw in self.display_windows:
            dw.black_screen()
        self._preview_cmd("black_screen")
        # Clear render engine text so preview shows empty frame
        self.render_engine.set_text("", None)
        # Clear LiveState so preview (all paths) also goes dark
        from live_state import get_state as _gs
        _gs().current_text = ""
        _gs()._metadata    = {}
        _gs().notify()
        self._is_live = False
        self._live_timer.stop()
        self._auto_timer.stop()
        self.auto_check.setChecked(False)
        self._live_dot.setStyleSheet("color: #2a2a2a; font-size: 14px;")
        self._status_live_dot.setStyleSheet("color: #2a2a2a; font-size: 14px;")
        self._update_status(slide_msg="Black screen")
        self._auto_lbl.setText("")
        self._push_remote_state()

    def _prev_slide(self):
        if self.current_slide_idx > 0:
            self._send_slide_to_live(self.current_slide_idx - 1)

    def _next_slide(self):
        if self.current_slide_idx < len(self.current_slides) - 1:
            self._send_slide_to_live(self.current_slide_idx + 1)

    # ── Send-target helpers ───────────────────────────────────────────────────

    def _on_send_target_changed(self, _idx):
        self._send_target_idx = self._send_combo.currentData()

    def _update_send_combo(self):
        """Rebuild the Send-to dropdown from the open display windows."""
        self._send_combo.blockSignals(True)
        self._send_combo.clear()
        self._send_combo.addItem(t("all_displays"), -1)
        for i, dw in enumerate(self.display_windows):
            self._send_combo.addItem(dw.window_name, i)
        self._send_combo.blockSignals(False)
        self._send_target_idx = -1

    def _target_windows(self) -> list:
        """Return the list of display windows that should receive GO LIVE content."""
        if self._send_target_idx < 0:
            return list(self.display_windows)
        if 0 <= self._send_target_idx < len(self.display_windows):
            return [self.display_windows[self._send_target_idx]]
        return list(self.display_windows)

    # ── Display open/close ────────────────────────────────────────────────────

    def _is_bible_mode(self) -> bool:
        """Return True when the sidebar has the Bible tab active."""
        try:
            idx = self._left_tabs.currentIndex()
            t = self._left_tabs.tabText(idx)
            return "ibli" in t or "ible" in t
        except Exception:
            return False

    def _open_display(self):
        """Open all active configured display windows."""
        screens = QApplication.screens()
        configs = db.get_display_configs()
        active_configs = [c for c in configs if c.get("active", True)]

        if not active_configs:
            active_configs = [{"name": "Display", "screen": 1,
                               "fullscreen": True, "active": True, "settings": {}}]

        # Check secondary monitor availability (logică primary/secondary)
        _primary_scr    = QApplication.primaryScreen()
        _secondary_scrs = [s for s in screens if s is not _primary_scr]
        any_needs_secondary = any(c.get("screen", 1) > len(_secondary_scrs)
                                  for c in active_configs)
        if not _secondary_scrs and any_needs_secondary:
            reply = QMessageBox.question(
                self, "Monitor secundar lipsă",
                "Nu a fost detectat un monitor secundar.\n\n"
                "Ferestrele display configurate necesită un ecran suplimentar.\n"
                "Continui oricum pe monitorul principal?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        for cfg in active_configs:
            screen_idx = cfg.get("screen", 1)
            # Primary/secondary logic — consistent cu Electron's openDisplay()
            # screen_idx 1 → primul ecran secundar; 2 → al doilea etc.
            if screen_idx > 0 and _secondary_scrs:
                screen = _secondary_scrs[min(screen_idx - 1, len(_secondary_scrs) - 1)]
            else:
                screen = screens[min(screen_idx, len(screens) - 1)]
            # Merge global settings with per-window overrides
            merged = dict(self.settings)
            merged.update(cfg.get("settings", {}))
            window_id   = len(self.display_windows) + 1
            window_name = cfg.get("name", f"Display {window_id}")

            # ── Electron renderer — cu fallback la DisplayWindow nativ ──────
            _ed = getattr(self, "electron_display", None)
            if _ed is not None and _ed.is_running():
                try:
                    from electron_display import ElectronDisplayProxy
                    merged["_screen_index"] = screen_idx
                    dw = ElectronDisplayProxy(
                        _ed,
                        window_id        = window_id,
                        window_name      = window_name,
                        initial_settings = merged,
                    )
                    dw.show()
                    _ed.open_display(
                        screen_index = screen_idx,
                        window_id    = window_id,
                        window_name  = window_name,
                    )
                except Exception as _ep:
                    logger.warning("[Electron] proxy creation failed (%s); skipping display", _ep)
                    continue
            elif DisplayWindow is not None:
                # Fallback: fereastră nativă PyQt6 când Electron nu e disponibil
                logger.warning(
                    "[Display] Electron nu rulează — folosesc DisplayWindow nativ pentru '%s'",
                    window_name)
                try:
                    dw = DisplayWindow(
                        screen      = screen,
                        settings    = merged,
                        window_id   = window_id,
                        window_name = window_name,
                        fullscreen  = cfg.get("fullscreen", True),
                    )
                    dw.show()
                except Exception as _ep:
                    logger.error("[Display] DisplayWindow creation failed: %s", _ep)
                    continue
            else:
                logger.error(
                    "[Display] Nu e disponibil niciun renderer pentru '%s' "
                    "(Electron oprit, DisplayWindow lipsă)", window_name)
                continue

            # Register window_ready callback so content appears as soon as
            # Electron finishes loading — no fixed delay needed.
            # Skip in Bible mode: _send_bible_verse_live registers its own callback.
            _ed_ref = getattr(self, "electron_display", None)
            if (_ed_ref is not None and not self._is_bible_mode()
                    and self.current_slide_idx >= 0 and self.current_slides):
                _capture_idx      = self.current_slide_idx
                _capture_slides   = list(self.current_slides)
                _capture_settings = self._resolve_settings(
                    source="songs", song_id=self.current_song_id)
                _capture_fmt      = None
                if (self._current_song_formatting and
                        self._current_song_formatting.get("use_custom")):
                    _capture_fmt = dict(self._current_song_formatting)
                _capture_meta = dict(self._current_metadata or {})
                _capture_wid  = window_id

                def _on_window_ready(
                    mgr=_ed_ref, sett=_capture_settings, fmt=_capture_fmt,
                    meta=_capture_meta, wid=_capture_wid,
                ):
                    # The Display stays BLACK until the operator explicitly picks a
                    # slide (self._live_armed). A slide chosen BEFORE opening still
                    # shows, because _live_armed isn't reset on open.
                    if not getattr(self, "_live_armed", False):
                        mgr._enqueue({"type": "black", "window_id": wid})
                        return
                    # Use the CURRENTLY selected slide at fire time (not a stale
                    # captured index) so opening the display shows exactly the
                    # slide the operator picked — never jumps back to slide 1.
                    idx = self.current_slide_idx
                    slides = self.current_slides
                    if 0 <= idx < len(slides):
                        txt = self._slide_text(slides[idx]) if hasattr(self, "_slide_text") else str(slides[idx])
                        if txt.strip():
                            mgr._enqueue({"type": "settings", "window_id": wid,
                                          "settings": sett})
                            mgr._enqueue({
                                "type": "show_text", "window_id": wid,
                                "text": txt, "format": fmt or {},
                                "transition": "none", "transition_duration": 0,
                                "metadata": meta,
                            })

                _ed_ref.set_window_ready_callback(window_id, _on_window_ready)

            self.display_windows.append(dw)

        n = len(self.display_windows)
        self._update_status(display_msg=f"{n} display{'s' if n != 1 else ''} open")
        self._update_send_combo()
        self._update_btn_states()
        # Detect screen aspect ratio and update preview + thumbnails
        QTimer.singleShot(100, self._apply_aspect_ratio)
        QTimer.singleShot(150, self._update_preview_aspect)
        # The Electron display needs a moment to land on its target monitor before
        # its real screen geometry is readable — re-detect once it has settled so
        # the HD preview + thumbnails match a non-16:9 projector/TV correctly.
        QTimer.singleShot(700, self._apply_aspect_ratio)
        QTimer.singleShot(1400, self._apply_aspect_ratio)
        # Fallback: push slide after 800 ms in case window_ready was missed.
        # Skip in Bible mode (bible content is handled by _send_bible_verse_live).
        if self.current_slide_idx >= 0 and not self._is_bible_mode():
            QTimer.singleShot(800, self._push_initial_slide)
        # Notify remote clients that a display is now open
        self._push_remote_state()

    def _close_all_displays(self):
        for dw in self.display_windows:
            dw.close()
        self.display_windows.clear()
        self._is_live = False
        self._live_armed = False   # next open starts black until a slide is picked
        self._live_timer.stop()
        self._auto_timer.stop()
        self.auto_check.setChecked(False)
        self._live_dot.setStyleSheet("color: #2a2a2a; font-size: 14px;")
        self._status_live_dot.setStyleSheet("color: #2a2a2a; font-size: 14px;")
        self._update_status(display_msg="No display open")
        self._update_send_combo()
        self._update_btn_states()
        # Revert to default 16:9 when all displays close
        self._display_aspect = 16 / 9
        if hasattr(self, 'preview'):
            self.preview.set_aspect_ratio(16 / 9)

    def _push_initial_slide(self):
        """Push the selected slide content to newly-opened displays WITHOUT going live.

        Called either via window_ready callback (immediate) or a fallback timer (800 ms).
        Does NOT set _is_live, does NOT start the live timer — operator still presses
        Space/GO LIVE to actually start the session.
        """
        if not self.display_windows or self._is_frozen:
            return
        # Display stays black until the operator explicitly picks a slide.
        if not getattr(self, "_live_armed", False):
            return
        if self._is_bible_mode():
            return
        if self.current_slide_idx < 0 or not self.current_slides:
            return
        text = self._slide_text(self.current_slides[self.current_slide_idx])
        if not text.strip():
            return

        _live_fmt = None
        if (self._current_song_formatting and
                self._current_song_formatting.get("use_custom")):
            _live_fmt = dict(self._current_song_formatting)
            _live_fmt["_slide_idx"] = self.current_slide_idx

        _live_settings = self._resolve_settings(
            source="songs", song_id=self.current_song_id)

        _rich = self._send_rich_slide_live(self.current_slide_idx)
        if not _rich:
            self._apply_custom_bg_from_settings(_live_settings)
        for dw in self.display_windows:
            dw.apply_settings(_live_settings)
            dw.show_text("" if _rich else text, _live_fmt,
                         metadata=self._current_metadata)

    # ── Auto-advance ──────────────────────────────────────────────────────────

    def _toggle_auto_advance(self, checked):
        if checked:
            secs = self.auto_spin.value()
            self._auto_timer.start(secs * 1000)
            self._auto_lbl.setText(f"Auto /{secs}s")
            self._auto_lbl.setStyleSheet("color: #5294e2; font-size: 10px; font-weight: 600;")
        else:
            self._auto_timer.stop()
            self._auto_lbl.setText("")

    def _on_auto_spin_changed(self, val):
        if self.auto_check.isChecked():
            self._auto_timer.setInterval(val * 1000)
            self._auto_lbl.setText(f"Auto /{val}s")
        db.save_setting("auto_advance_seconds", str(val))

    def _auto_advance(self):
        if not self._is_live or not self.current_slides:
            return
        if self.current_slide_idx < len(self.current_slides) - 1:
            self._next_slide()
        else:
            # End of song — stop auto-advance
            self._auto_timer.stop()
            self.auto_check.setChecked(False)
            self._auto_lbl.setText("")

    # ── Stage monitor ─────────────────────────────────────────────────────────

    def _open_stage_monitor(self):
        from stage_monitor import StageEditorWindow
        if self._stage_editor is None or not self._stage_editor.isVisible():
            self._stage_editor = StageEditorWindow(parent=None)
            self._stage_editor.show()
            self._update_status(stage_msg="Stage: activ")
        else:
            self._stage_editor.raise_()
        self._push_stage_state()
        self._update_btn_states()

    def _open_stage_editor(self, _pos=None):
        """Right-click on Stage button — open the stage layout editor directly."""
        from stage_monitor import StageEditorWindow
        if self._stage_editor is None or not self._stage_editor.isVisible():
            self._stage_editor = StageEditorWindow(parent=None)
            self._stage_editor.show()
        # Switch to the editor tab / raise it
        self._stage_editor.raise_()
        self._stage_editor.activateWindow()
        # Try to navigate to the properties/editor tab if available
        try:
            if hasattr(self._stage_editor, '_tabs'):
                self._stage_editor._tabs.setCurrentIndex(1)
        except Exception:
            pass
        self._update_btn_states()

    def _push_stage_state(self):
        if self._stage_editor is None:
            return
        current = self._slide_text(self.current_slides[self.current_slide_idx]) if (
            0 <= self.current_slide_idx < len(self.current_slides)
        ) else ""
        next_text = self._slide_text(self.current_slides[self.current_slide_idx + 1]) if (
            0 <= self.current_slide_idx + 1 < len(self.current_slides)
        ) else ""
        self._stage_editor.update_state(current, next_text, self.current_song_notes)

    # ── Overlay Controls ──────────────────────────────────────────────────────

    @staticmethod
    def _hex_opacity_to_rgba(hex_color: str, opacity_pct: int) -> str:
        try:
            h = hex_color.lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return f"rgba({r},{g},{b},{round(opacity_pct/100.0,2)})"
        except Exception:
            return hex_color

    def _expand_tokens(self, text: str) -> str:
        """Replace dynamic tokens in messages/ticker (ProPresenter-style):
        {time} {time_s} {date} {slide} {total} {next} {title}."""
        if not text or "{" not in text:
            return text
        import datetime
        now = datetime.datetime.now()
        idx = getattr(self, "current_slide_idx", 0)
        slides = getattr(self, "current_slides", []) or []
        total = len(slides)

        def _first_line(s):
            t = self._slide_text(s) if hasattr(self, "_slide_text") else (
                s.get("text", "") if isinstance(s, dict) else str(s))
            return (t or "").strip().split("\n")[0]

        nxt = _first_line(slides[idx + 1]) if 0 <= idx + 1 < total else ""
        title = self.song_title_edit.text().strip() if hasattr(self, "song_title_edit") else ""
        tokens = {
            "{time}":   now.strftime("%H:%M"),
            "{time_s}": now.strftime("%H:%M:%S"),
            "{date}":   now.strftime("%d.%m.%Y"),
            "{slide}":  str(idx + 1 if total else 0),
            "{total}":  str(total),
            "{next}":   nxt,
            "{title}":  title,
        }
        for k, v in tokens.items():
            text = text.replace(k, v)
        return text

    def _send_ticker(self):
        text = self._expand_tokens(self.ticker_input.text().strip())
        if not text:
            return
        # Read from overlays JSON (saved by OverlaySettingsWidget) with fallback
        try:
            ov_raw = self.settings.get("overlays", "{}")
            ov = json.loads(ov_raw) if isinstance(ov_raw, str) else (ov_raw or {})
            tk = ov.get("ticker", {})
        except Exception:
            tk = {}

        bg_hex = tk.get("bg_color", "#000000") or "#000000"
        if len(bg_hex) > 7:
            bg_hex = bg_hex[:7]
        bg_opacity = int(tk.get("bg_opacity", 85))
        bg_rgba = self._hex_opacity_to_rgba(bg_hex, bg_opacity)

        ticker_settings = {
            "speed":          float(tk.get("speed") or self.settings.get("ticker_speed", 3)),
            "font_size":      int(tk.get("font_size") or self.settings.get("ticker_font_size", 22)),
            "font_family":    tk.get("font_family") or self.settings.get("ticker_font_family", "Arial"),
            "text_color":     tk.get("color") or self.settings.get("ticker_color", "#f9e2af"),
            "bg_color":       bg_rgba,
            "bar_height":     int(tk.get("height") or self.settings.get("ticker_height", 52)),
            "position":       tk.get("position") or self.settings.get("ticker_position", "bottom"),
            "animation":      tk.get("animation", "scroll_left"),
            "bold":           bool(tk.get("bold", False)),
            "italic":         bool(tk.get("italic", False)),
            "ticker_in_effect":  self.settings.get("ticker_in_effect", "slide_up"),
            "ticker_out_effect": self.settings.get("ticker_out_effect", "slide_down"),
            "ticker_duration":   int(self.settings.get("ticker_anim_duration", 400)),
        }
        for dw in self.display_windows:
            if hasattr(dw, "show_ticker_advanced"):
                dw.show_ticker_advanced(text, ticker_settings)
            else:
                dw.set_ticker(text, ticker_settings=ticker_settings)
        self._update_status(slide_msg="Ticker active")

    def _clear_ticker(self):
        self.ticker_input.clear()
        for dw in self.display_windows:
            dw.set_ticker("")

    def _toggle_clock(self, checked):
        # Read from overlays JSON (saved by OverlaySettingsWidget) with fallback to flat keys
        try:
            ov_raw = self.settings.get("overlays", "{}")
            ov = json.loads(ov_raw) if isinstance(ov_raw, str) else (ov_raw or {})
            ck = ov.get("clock", {})
        except Exception:
            ck = {}

        fmt = ck.get("format") or self.settings.get("clock_format", "HH:MM:SS")
        clock_settings = {
            "clock_format":  fmt,
            "format_24h":    "AM/PM" not in fmt,
            "show_seconds":  "SS" in fmt,
            "color":         ck.get("color")      or self.settings.get("clock_color",      "#ffffff"),
            "font_size":     int(ck.get("font_size") or self.settings.get("clock_font_size",   22)),
            "font_family":   ck.get("font_family") or self.settings.get("clock_font_family", "Consolas"),
            "position":      ck.get("position")   or self.settings.get("clock_position",   "top_right"),
            "bg_enabled":    ck.get("bg", "transparent") not in ("transparent", None, ""),
            "bg_color":      ck.get("bg_color")   or self.settings.get("clock_bg_color",   "rgba(0,0,0,0.5)"),
            "shadow":        ck.get("shadow", True),
            "bold":          ck.get("bold", True),
        }
        # Custom drag-positioned clock (from ClockPositionPicker)
        if ck.get("x_pct") is not None and ck.get("y_pct") is not None:
            clock_settings["position"] = "custom"
            clock_settings["x_pct"]   = float(ck["x_pct"])
            clock_settings["y_pct"]   = float(ck["y_pct"])

        for dw in self.display_windows:
            dw.toggle_clock(checked, clock_settings)

    def _start_countdown(self):
        secs = self.countdown_spin.value()
        color = self.settings.get("countdown_color", "#ffffff")
        for dw in self.display_windows:
            dw.start_countdown(secs, color)

    # ── Playlist ──────────────────────────────────────────────────────────────

    def _load_playlist_list(self):
        if not hasattr(self, 'playlist_list'):
            return
        self.playlist_list.clear()
        items = db.get_playlist()
        for i, entry in enumerate(items, 1):
            item = QListWidgetItem(f"{i}. {entry['title']}")
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.playlist_list.addItem(item)

    def _add_to_playlist(self):
        song_id = self._current_song_list_id()
        if song_id is None:
            return
        db.add_to_playlist(song_id)
        self._load_playlist_list()
        # Also add to center-panel service list
        self._add_selected_to_service()

    def _remove_from_playlist(self):
        sel = self.playlist_list.currentItem()
        if not sel:
            return
        entry = sel.data(Qt.ItemDataRole.UserRole)
        db.remove_from_playlist(entry["id"])
        self._load_playlist_list()

    def _clear_playlist(self):
        if QMessageBox.question(self, "Clear Service", "Clear the entire service order?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            db.clear_playlist()
            self._load_playlist_list()

    def _load_playlist_item(self, item):
        entry = item.data(Qt.ItemDataRole.UserRole)
        song = db.get_song(entry["song_id"])
        if not song:
            return
        self.current_song_id = entry["song_id"]
        self._current_metadata = {
            "title":    song.get("title", ""),
            "author":   song.get("author", ""),
            "category": song.get("category", ""),
            "source":   song.get("notes", ""),
        }
        self.song_title_edit.setText(song["title"])
        self._load_content_to_editor(song["content"])
        self._set_slides(song["slides"])
        self._update_word_counter()
        self._current_song_formatting = song.get("formatting")
        self._editor_modified = False
        self._init_toolbar_from_formatting()
        self._update_fmt_status_label()
        self._update_notes_bar(song.get("notes", ""))
        self._update_status(song_msg=song["title"])

    # ── Import ────────────────────────────────────────────────────────────────

    def _import_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import File", "",
            "All Supported (*.txt *.docx *.pdf *.json *.xml *.vpc *.ewsx *.db *.bib);;"
            "Text (*.txt);;Word (*.docx);;PDF (*.pdf);;"
            "VideoPsalm (*.json *.xml *.vpc);;EasyWorship (*.ewsx *.db);;BibleShow (*.bib)"
        )
        if not path:
            return
        try:
            result = import_file(path)
            if result["type"] == "songs":
                songs = result["data"]
                if not songs:
                    QMessageBox.warning(self, "Import", "0 cântări găsite în fișier.")
                    return

                # ── Ask user which category to assign ────────────────────────
                dlg = _ImportCategoryDialog(len(songs), self)
                if dlg.exec() != QDialog.DialogCode.Accepted:
                    return
                default_cat = dlg.get_category()
                use_original = dlg.use_original_category()

                imported = errors = duplicates = 0
                for s in songs:
                    try:
                        # Decide category
                        if use_original and s.get("category") \
                                and s["category"] not in ("", "General"):
                            cat = s["category"]
                        else:
                            cat = default_cat

                        # Skip duplicates
                        if db.find_song_by_title(s["title"]):
                            duplicates += 1
                            continue

                        db.add_song(
                            s["title"], s["content"], s["slides"],
                            s.get("author", ""), cat, s.get("language", "ro")
                        )
                        imported += 1
                    except Exception as e_song:
                        errors += 1
                        print(f"[Import] {e_song}")

                self._load_library()

                msg = f"✅ Importate {imported} cântări"
                if duplicates:
                    msg += f"  |  ⚠ {duplicates} duplicate omise"
                if errors:
                    msg += f"  |  ❌ {errors} erori"
                QMessageBox.information(self, "Import Complete", msg)

            elif result["type"] == "bible":
                data = result["data"]
                db.import_bible_data(data["books"], data["verses"])
                QMessageBox.information(
                    self, "Bible Imported",
                    f"Imported {len(data['books'])} books, {len(data['verses'])} verses."
                )
                self._refresh_bible_tab()
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))

    def _refresh_bible_tab(self):
        for child in self.centralWidget().findChildren(QTabWidget):
            if child.count() >= 3:
                bible_widget = child.widget(1)
                layout = bible_widget.layout()
                while layout.count():
                    item = layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                self.bible_placeholder = None
                self._init_bible_controls(layout)
                break

    # ── Bible ─────────────────────────────────────────────────────────────────

    def _load_chapters(self):
        if not hasattr(self, 'book_combo') or self.book_combo.isHidden():
            return
        book_id = self.book_combo.currentData()
        if book_id is None:
            return
        self.chapter_combo.blockSignals(True)
        self.chapter_combo.clear()
        for ch in db.get_chapters(book_id):
            self.chapter_combo.addItem(f"Chapter {ch}", ch)
        self.chapter_combo.blockSignals(False)
        self._load_verses()

    def _load_verses(self):
        if not hasattr(self, 'book_combo') or self.book_combo.isHidden():
            return
        book_id = self.book_combo.currentData()
        chapter = self.chapter_combo.currentData()
        if book_id is None or chapter is None:
            return

        verses = db.get_verses(book_id, chapter)

        # Keep verse_list in sync (even though it's hidden) so _send_verse still works
        if hasattr(self, "verse_list"):
            self.verse_list.clear()
            for v in verses:
                item = QListWidgetItem(f"{v['verse']}  {v['text']}")
                item.setData(Qt.ItemDataRole.UserRole, v)
                self.verse_list.addItem(item)

        # ── Populate verse combo ───────────────────────────────────────────────
        if hasattr(self, "verse_combo"):
            self.verse_combo.blockSignals(True)
            self.verse_combo.clear()
            self.verse_combo.addItem("Toate versetele →", None)
            for v in verses:
                verse_num  = v.get("verse", 0)
                text_prev  = v.get("text", "")
                # Truncate preview to 50 chars so the combo stays readable
                if len(text_prev) > 50:
                    text_prev = text_prev[:50] + "…"
                self.verse_combo.addItem(f"{verse_num}.  {text_prev}", v)
            self.verse_combo.blockSignals(False)

        # Push to BibleControlTab
        if getattr(self, "_bible_control_tab", None) is not None:
            book_name = self.book_combo.currentText()
            self._bible_control_tab.load_chapter(book_name, chapter, verses)

        # Auto-switch center panel to Control Bible
        if hasattr(self, "_center_tab_widget"):
            for i in range(self._center_tab_widget.count()):
                tab_text = self._center_tab_widget.tabText(i)
                if "Bible" in tab_text or "iblie" in tab_text or "Control" in tab_text:
                    self._center_tab_widget.setCurrentIndex(i)
                    break

    def _on_verse_combo_selected(self, idx: int):
        """Verse combo selection — jump to the verse in BibleControlTab."""
        if idx <= 0 or not hasattr(self, 'verse_combo'):
            return
        verse_data = self.verse_combo.itemData(idx)
        if not verse_data:
            return
        verse_num = verse_data.get("verse", 0)

        # Select the verse in BibleControlTab's verse list
        bt = getattr(self, "_bible_control_tab", None)
        if bt is not None and hasattr(bt, "verse_queue"):
            for i in range(bt.verse_queue.count()):
                item = bt.verse_queue.item(i)
                v = item.data(Qt.ItemDataRole.UserRole)
                if v and v.get("verse") == verse_num:
                    bt.verse_queue.setCurrentItem(item)
                    bt.verse_queue.scrollToItem(item)
                    break

        # Switch center panel to Control Bible
        if hasattr(self, "_center_tab_widget"):
            for i in range(self._center_tab_widget.count()):
                tab_text = self._center_tab_widget.tabText(i)
                if "Bible" in tab_text or "iblie" in tab_text or "Control" in tab_text:
                    self._center_tab_widget.setCurrentIndex(i)
                    break

    def _preview_verse(self, item):
        v = item.data(Qt.ItemDataRole.UserRole)
        book_name = self.book_combo.currentText()
        chapter = self.chapter_combo.currentData()
        text = f"{v['text']}\n\n{book_name} {chapter}:{v['verse']}"
        self.preview.update_text(text)

    def _send_verse(self):
        item = self.verse_list.currentItem()
        if not item:
            return
        v = item.data(Qt.ItemDataRole.UserRole)
        book_name = self.book_combo.currentText()
        chapter = self.chapter_combo.currentData()
        text = f"{v['text']}\n\n{book_name} {chapter}:{v['verse']}"
        self._send_text_live(text, f"{book_name} {chapter}:{v['verse']}")

    def _send_bible_verse_live(self, text: str, ref: str):
        """Send a Bible verse to all display windows with the active bible theme."""
        # Resolve settings with bible theme
        live_settings = self._resolve_settings(source="bible")
        live_settings["source"] = "bible"
        if ref:
            live_settings["bible_reference"] = ref
        metadata = {"reference": ref, "source": "bible"}

        if not self.display_windows:
            self._open_display()
            # Apply the Bible theme's custom background (fundal) too — otherwise a
            # freshly-opened display shows the verse without its background.
            try: self._apply_custom_bg_from_settings(live_settings)
            except Exception: pass
            # Register a window_ready callback so the Bible verse is pushed as soon
            # as Electron is ready (the generic song callback is skipped in bible mode).
            _ed_ref = getattr(self, "electron_display", None)
            if _ed_ref is not None and self.display_windows:
                _c_text = text
                _c_sett = dict(live_settings)
                _c_meta = dict(metadata)
                for _i in range(len(self.display_windows)):
                    _c_wid = _i + 1
                    def _on_bible_ready(mgr=_ed_ref, wid=_c_wid,
                                        txt=_c_text, sett=_c_sett, meta=_c_meta):
                        mgr._enqueue({"type": "settings", "window_id": wid, "settings": sett})
                        mgr._enqueue({"type": "show_text", "window_id": wid,
                                      "text": txt, "format": {}, "transition": "none",
                                      "transition_duration": 0, "metadata": meta})
                    _ed_ref.set_window_ready_callback(_c_wid, _on_bible_ready)
        else:
            targets = self._target_windows()
            self._apply_custom_bg_from_settings(live_settings)
            for dw in targets:
                dw.apply_settings(live_settings)
                dw.show_text(text, metadata=metadata)

        # Update preview (do NOT overwrite song slides — bible verses are separate)
        self.preview.update_text(text)
        self.preview.apply_settings(live_settings)
        self.render_engine.set_text(text, None)

        has_display = bool(self.display_windows)
        self._is_live = has_display
        if has_display and not self._live_timer.isActive():
            self._live_timer.start(600)
        self._update_status(song_msg=ref or "Bible")
        self._push_stage_state()
        self._push_remote_state()

    # ── Tab sync helpers ──────────────────────────────────────────────────────

    def _apply_bible_splitter(self):
        """Rise the center splitter to give more space to the Control Bible panel."""
        self._songs_splitter_sizes = self._center_splitter.sizes()
        total = sum(self._songs_splitter_sizes) or 700
        self._center_splitter.setSizes([int(total * 0.25), int(total * 0.75)])

    def _restore_songs_splitter(self):
        """Restore center splitter to songs-mode proportions."""
        saved = getattr(self, '_songs_splitter_sizes', None)
        if saved and len(saved) == 2 and sum(saved) > 0:
            self._center_splitter.setSizes(saved)
        else:
            self._center_splitter.setSizes([400, 300])

    def _on_left_tab_changed(self, idx: int):
        """Sync center panel and splitter when sidebar tab changes."""
        try:
            tab_text = self._left_tabs.tabText(idx)
        except Exception:
            return
        is_bible = "ibli" in tab_text or "ible" in tab_text
        if is_bible:
            # Activate Control Bible in center panel
            for i in range(self._center_tab_widget.count()):
                ct = self._center_tab_widget.tabText(i)
                if "Bible" in ct or "iblie" in ct:
                    self._center_tab_widget.blockSignals(True)
                    self._center_tab_widget.setCurrentIndex(i)
                    self._center_tab_widget.blockSignals(False)
                    if getattr(self, "_bible_control_tab", None):
                        self._bible_control_tab.setFocus()
                    break
            self._apply_bible_splitter()
        else:
            # Switch center back to last songs-mode tab (default: Editor)
            saved_idx = getattr(self, '_songs_center_tab_idx', 0)
            self._center_tab_widget.blockSignals(True)
            self._center_tab_widget.setCurrentIndex(saved_idx)
            self._center_tab_widget.blockSignals(False)
            self._restore_songs_splitter()

    def _on_center_tab_changed(self, idx: int):
        """When center switches to/from Control Bible, sync sidebar."""
        try:
            tab_text = self._center_tab_widget.tabText(idx)
        except Exception:
            return
        is_bible_center = "Bible" in tab_text or "iblie" in tab_text
        if is_bible_center:
            for i in range(self._left_tabs.count()):
                lt = self._left_tabs.tabText(i)
                if "ibli" in lt or "ible" in lt:
                    self._left_tabs.blockSignals(True)
                    self._left_tabs.setCurrentIndex(i)
                    self._left_tabs.blockSignals(False)
                    break
            if getattr(self, "_bible_control_tab", None):
                self._bible_control_tab.setFocus()
        else:
            # Remember this as the songs-mode center tab index
            self._songs_center_tab_idx = idx

    def _search_bible(self):
        query = self.bible_search_edit.text().strip()
        if not query:
            self.bible_search_results.hide()
            return
        results = db.search_bible_text(query, limit=50)
        self.bible_search_results.clear()
        if results:
            self.bible_search_results.show()
            for r in results:
                ref = f"{r['book_name']} {r['chapter']}:{r['verse']}"
                preview = r['text'][:60] + ("…" if len(r['text']) > 60 else "")
                item = QListWidgetItem(f"{ref}  —  {preview}")
                item.setData(Qt.ItemDataRole.UserRole, r)
                self.bible_search_results.addItem(item)
        else:
            item = QListWidgetItem("No results found")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.bible_search_results.addItem(item)
            self.bible_search_results.show()

    def _preview_search_verse(self, item):
        r = item.data(Qt.ItemDataRole.UserRole)
        if not r:
            return
        text = f"{r['text']}\n\n{r['book_name']} {r['chapter']}:{r['verse']}"
        self.preview.update_text(text)

    def _send_search_verse(self, item):
        r = item.data(Qt.ItemDataRole.UserRole)
        if not r:
            return
        ref = f"{r['book_name']} {r['chapter']}:{r['verse']}"
        text = f"{r['text']}\n\n{ref}"
        self._send_text_live(text, ref)

    def _select_song_in_list(self, song_id: int):
        """Find and select a song by id in the current songs_model view."""
        from PyQt6.QtWidgets import QAbstractItemView
        model = self.songs_model
        for i in range(model.rowCount()):
            idx = model.index(i, 0)
            sid = model.data(idx, Qt.ItemDataRole.UserRole)
            if sid == song_id:
                self.song_list.setCurrentIndex(idx)
                self.song_list.scrollTo(
                    idx, QAbstractItemView.ScrollHint.PositionAtCenter)
                self._load_song_by_index(idx)
                return
        # Not in current page — search by title
        song = db.get_song(song_id)
        if not song:
            return
        title = song.get("title", "")
        if hasattr(self, "search_edit") and title:
            self.search_edit.setText(title)
            self._do_search(title)
            QTimer.singleShot(200, lambda sid=song_id: self._select_after_search(sid))

    def _select_after_search(self, song_id: int):
        """Second-pass selection after a search has been triggered."""
        from PyQt6.QtWidgets import QAbstractItemView
        model = self.songs_model
        for i in range(model.rowCount()):
            idx = model.index(i, 0)
            sid = model.data(idx, Qt.ItemDataRole.UserRole)
            if sid == song_id:
                self.song_list.setCurrentIndex(idx)
                self.song_list.scrollTo(
                    idx, QAbstractItemView.ScrollHint.PositionAtCenter)
                self._load_song_by_index(idx)
                return

    def _send_text_live(self, text, status_label=""):
        self.current_slides = [text]
        self.current_slide_idx = 0
        self.preview.update_text(text)
        if self.display_windows:
            for dw in self.display_windows:
                dw.show_text(text)
            self._is_live = True
            if not self._live_timer.isActive():
                self._live_timer.start(600)
        if status_label:
            self._update_status(song_msg=status_label)
        self._push_stage_state()

    # ── DB Export/Import/PDF ──────────────────────────────────────────────────

    def _export_db(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Database", "cantio_backup.json",
            "JSON (*.json)"
        )
        if not path:
            return
        try:
            count = db.export_db_json(path)
            QMessageBox.information(self, "Export Complete",
                f"Database exported successfully.\n{count} songs saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _import_db(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Database", "", "JSON (*.json)"
        )
        if not path:
            return
        reply = QMessageBox.question(
            self, "Import Mode",
            "Merge with existing library?\n\n"
            "Yes = Merge (update existing, add new)\n"
            "No = Skip duplicates (add new only)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No |
            QMessageBox.StandardButton.Cancel
        )
        if reply == QMessageBox.StandardButton.Cancel:
            return
        merge = (reply == QMessageBox.StandardButton.Yes)
        try:
            count = db.import_db_json(path, merge=merge)
            self._load_library()
            QMessageBox.information(self, "Import Complete",
                f"Imported {count} song{'s' if count != 1 else ''} from database.")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))

    def _export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Service Order", "service_order.pdf", "PDF (*.pdf)"
        )
        if not path:
            return
        try:
            count = db.export_playlist_pdf(path)
            QMessageBox.information(self, "PDF Exported",
                f"Service order exported ({count} items):\n{path}")
        except ImportError:
            # Try to install reportlab
            reply = QMessageBox.question(
                self, "Install reportlab?",
                "reportlab is not installed. Install it now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                import subprocess, sys
                subprocess.check_call([sys.executable, "-m", "pip", "install", "reportlab"])
                count = db.export_playlist_pdf(path)
                QMessageBox.information(self, "PDF Exported",
                    f"Service order exported ({count} items):\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    # ── Uppercase Songs ───────────────────────────────────────────────────────

    def _uppercase_songs(self):
        from toast_notifications import show_toast
        dlg = UppercaseDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        params = dlg.get_params()
        mode = params["mode"]
        try:
            if mode == "all":
                count = db.uppercase_songs()
            elif mode == "category":
                count = db.uppercase_songs(category=params["category"])
            else:
                if not self.current_song_id:
                    show_toast("Nicio cântare selectată", "warning")
                    return
                count = db.uppercase_songs(song_ids=[self.current_song_id])

            # Refresh UI
            if hasattr(self, "songs_model"):
                self.songs_model.load_page(0)
            if self.current_song_id:
                song = db.get_song(self.current_song_id)
                if song:
                    self._set_slides(song["slides"])
            show_toast(f"✅ {count} cântări actualizate (uppercase)", "success")
        except Exception as e:
            QMessageBox.critical(self, "Eroare", str(e))

    # ── Split Slides by Lines ─────────────────────────────────────────────────

    def _split_slides_by_lines(self):
        from toast_notifications import show_toast
        dlg = SplitLinesDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        params = dlg.get_params()
        mode   = params["mode"]
        n      = params["lines"]
        try:
            if mode == "all":
                count = db.split_songs_by_lines(n)
            elif mode == "category":
                count = db.split_songs_by_lines(n, category=params["category"])
            else:
                if not self.current_song_id:
                    show_toast("Nicio cântare selectată", "warning")
                    return
                count = db.split_songs_by_lines(n, song_ids=[self.current_song_id])

            # Refresh UI
            if hasattr(self, "songs_model"):
                self.songs_model.load_page(0)
            if self.current_song_id:
                song = db.get_song(self.current_song_id)
                if song:
                    self._set_slides(song["slides"])
            show_toast(f"✅ {count} cântări împărțite la {n} rânduri/slide", "success")
        except Exception as e:
            QMessageBox.critical(self, "Eroare", str(e))

    # ── Profile management ────────────────────────────────────────────────────

    # ── Restriction enforcement ───────────────────────────────────────────────

    def _check_restriction(self, key: str) -> bool:
        """
        Check if the action *key* is permitted for the active profile.
        Returns True if PERMITTED, False if restricted (shows toast and returns False).
        """
        try:
            from profile_security import check_restriction
            profile = getattr(self, "_profile_name", "default")
            if check_restriction(profile, key):
                messages = {
                    "no_delete_songs":
                        "Nu ai voie să ștergi cântări\nîn acest profil!",
                    "no_edit_songs":
                        "Nu ai voie să editezi cântări\nîn acest profil!",
                    "no_import":
                        "Importul nu este permis\nîn acest profil!",
                    "no_settings":
                        "Setările nu sunt accesibile\nîn acest profil!",
                    "no_themes":
                        "Temele nu pot fi modificate\nîn acest profil!",
                    "no_export":
                        "Exportul nu este permis\nîn acest profil!",
                    "no_bible_import":
                        "Importul Bibliei nu este permis\nîn acest profil!",
                    "read_only":
                        "Profilul este în modul\ndoar citire!",
                }
                msg = messages.get(key, "Acțiunea nu este permisă\nîn acest profil!")
                try:
                    from toast_notifications import show_toast
                    show_toast(msg, "warning")
                except Exception:
                    pass
                return False
        except Exception:
            pass
        return True

    def _check_startup_profile(self):
        """If the startup profile is password-protected, prompt immediately."""
        try:
            from profile_security import has_password
            if not has_password(self._profile_name):
                return
            from profile_password_dialog import ProfilePasswordDialog
            pwd_dlg = ProfilePasswordDialog(self._profile_name, self)
            if pwd_dlg.exec() == QDialog.DialogCode.Accepted:
                return
            # Wrong / cancelled — fall back to Default
            self._toasts.warning("Acces refuzat! Profil schimbat la Default.")
            fallback = "Default"
            self._profile_name = fallback
            pm.create_profile(fallback)
            db.set_active_profile(fallback)
            db.init_db()
            self.settings = db.get_settings()
            self.preview.apply_settings(self.settings)
            self.setWindowTitle(f"Cantio — {fallback}")
            self._profile_btn.setText(f"👤 {fallback}")
            self._load_library()
        except Exception as _pe:
            print(f"[PROFILE] startup check error: {_pe}")

    def _change_profile(self):
        dlg = pm.ProfileSelectDialog(self)
        dlg.exec()
        new_profile = dlg.selected_profile
        if not new_profile or new_profile == self._profile_name:
            return

        # ── Password check ────────────────────────────────────────────────────
        try:
            from profile_security import has_password
            if has_password(new_profile):
                from profile_password_dialog import ProfilePasswordDialog
                pwd_dlg = ProfilePasswordDialog(new_profile, self)
                if pwd_dlg.exec() != QDialog.DialogCode.Accepted:
                    self._toasts.warning("Acces refuzat!")
                    return
        except Exception as _pe:
            print(f"[PROFILE] password check error: {_pe}")
        # Save current state, then RESTART the whole app for the new profile so
        # everything (Bible tab visibility, themes, backgrounds, DB) initialises
        # cleanly — no leftover state from the previous profile.
        try: self._save_current_song()
        except Exception: pass
        self._restart_with_profile(new_profile)

    def _restart_with_profile(self, profile: str):
        """Relaunch Cantio directly into `profile` (writes a pending-profile flag
        the next instance reads, then restarts this process)."""
        import os, sys
        from PyQt6.QtCore import QProcess
        try:
            flag = os.path.join(os.path.expanduser("~"), "Cantio", ".pending_profile")
            os.makedirs(os.path.dirname(flag), exist_ok=True)
            with open(flag, "w", encoding="utf-8") as f:
                f.write(profile)
        except Exception as e:
            logger.debug("[Profile] pending flag write failed: %s", e)
        # Clean shutdown of displays + Electron before relaunching
        try: self._close_all_displays()
        except Exception: pass
        try:
            mgr = getattr(self, "electron_display", None)
            if mgr is not None:
                if hasattr(mgr, "close_all"): mgr.close_all()
                if hasattr(mgr, "stop"): mgr.stop()
        except Exception: pass
        self._restarting = True
        if getattr(sys, "frozen", False):
            QProcess.startDetached(sys.executable, sys.argv[1:])
        else:
            QProcess.startDetached(sys.executable, sys.argv)
        QApplication.quit()

    # ── Button state ──────────────────────────────────────────────────────────

    def _btn_style_closed(self):
        return (
            "QPushButton { background: #1a1a1a; color: #cccccc; border: 1px solid #232323; "
            "border-radius: 4px; padding: 5px 12px; }"
            "QPushButton:hover { background: #222222; color: #e0e0e0; border-color: #333; }"
        )

    def _btn_style_open(self):
        return (
            "QPushButton { background: #1a3a1a; color: #66cc66; border: 1px solid #2a5a2a; "
            "border-radius: 4px; padding: 5px 12px; font-weight: 600; }"
            "QPushButton:hover { background: #1e4a1e; border-color: #4a8a4a; }"
        )

    def _update_btn_states(self):
        display_open = bool(self.display_windows)
        stage_open = self._stage_editor is not None and self._stage_editor.isVisible()

        self._display_btn.setStyleSheet(
            self._btn_style_open() if display_open else self._btn_style_closed()
        )
        self._display_btn.setText(
            f"📺 Display ●  ({len(self.display_windows)})" if display_open else "📺 Display  ○"
        )
        self._display_btn.setToolTip(
            ("Închide display  [Ctrl+P]" if display_open else "Deschide display  [Ctrl+P]")
        )

        self._stage_btn.setStyleSheet(
            self._btn_style_open() if stage_open else self._btn_style_closed()
        )
        self._stage_btn.setText("🎭 Stage  ●" if stage_open else "🎭 Stage  ○")

        self._remote_btn.setStyleSheet(
            self._btn_style_open() if self._remote_running else self._btn_style_closed()
        )
        self._remote_btn.setText("📱 Remote  ●" if self._remote_running else "📱 Remote")

    # ── Keyboard shortcuts ────────────────────────────────────────────────────

    def _setup_shortcuts(self):
        def _sc(key_str, slot):
            s = QShortcut(QKeySequence(key_str), self)
            s.activated.connect(slot)
            return s

        # App-level shortcuts (Ctrl+key — safe, no editor conflict)
        _sc("Ctrl+P",            self._toggle_display)
        _sc("Ctrl+Shift+P",      self._open_stage_monitor)
        _sc("Ctrl+Shift+T",      self._toggle_transparent)
        _sc("F11",               self._fullscreen_display)
        _sc("Ctrl+S",            self._save_service)
        _sc("Ctrl+O",            self._open_service)
        _sc("Ctrl+N",            self._new_service)
        _sc("Ctrl+F",            self._focus_search)
        _sc("Ctrl+I",            self._open_import_manager)
        _sc("F5",                self._open_display)   # quick-open display (any focus)

        # Escape: black screen — always active (editor doesn't use Escape specially)
        _sc("Escape",            self._black_screen)

        # Note: arrow keys and Space are handled in keyPressEvent (defined below)
        # so they respect editor focus (editor must keep normal cursor movement).

    def _toggle_display(self):
        if self.display_windows:
            self._close_all_displays()
        else:
            self._open_display()

    def _fullscreen_display(self):
        for dw in self.display_windows:
            if dw.isFullScreen():
                dw.showNormal()
            else:
                dw.showFullScreen()

    def _focus_search(self):
        if hasattr(self, 'search_edit'):
            self.search_edit.setFocus()
            self.search_edit.selectAll()

    def _new_service(self):
        """Clear service list (with confirmation)."""
        self._clear_service()

    def _open_import_manager(self):
        from import_manager import ImportManagerWindow
        dlg = ImportManagerWindow(
            parent=self,
            service_items=self._service_items,
            profile_name=self._profile_name
        )
        dlg.songs_imported.connect(self._load_library)
        dlg.bible_imported.connect(self._refresh_bible_tab)
        dlg.service_loaded.connect(self._on_service_loaded)
        dlg.exec()

    def _open_category_manager(self):
        from category_manager import CategoryManagerDialog
        dlg = CategoryManagerDialog(parent=self)
        dlg.categories_changed.connect(self._on_categories_changed)
        dlg.exec()

    def _on_categories_changed(self):
        """Reload the category filter and song library after DB edits."""
        self._refresh_categories()
        self._load_library()

    def _on_service_loaded(self, items: list):
        self._service_items = items
        self._refresh_service_list()
        self._update_status(song_msg=f"Serviciu importat: {len(items)} items")

    def _on_online_send_live(self, slides: list, title: str, author: str):
        """Handle 'Trimite Live' from Online Songs tab."""
        if not slides:
            return
        self.current_slides = slides
        self.current_slide_idx = 0
        self.current_song_id = None
        self._current_metadata = {"title": title, "author": author, "category": "Online", "source": "resursecrestine.ro"}
        self.song_title_edit.setText(title or "Online")
        self._set_slides(slides)
        if self.display_windows:
            self._go_live()
        else:
            self._open_display()
            if self.display_windows:
                self._go_live()

    def _on_online_import(self, song_dict: dict):
        """Refresh library after an online song is imported."""
        self._load_library()
        self._refresh_categories()

    def _show_shortcuts(self):
        dlg = ks.ShortcutsDialog(self, app_style=APP_STYLE)
        dlg.exec()

    def _show_about(self):
        from about_dialog import AboutDialog
        dlg = AboutDialog(self)
        dlg.exec()

    # ── Slide view toggle ─────────────────────────────────────────────────────

    def _toggle_slide_view(self):
        if self._slide_view_mode == "grid":
            self._slide_view_mode = "list"
            self._view_toggle_btn.setText("⊞")
            self._view_toggle_btn.setToolTip("Switch to grid view")
            # Only switch if a song is loaded (otherwise keep placeholder visible)
            if self.current_slides:
                self._slides_stack.setCurrentIndex(1)
        else:
            self._slide_view_mode = "grid"
            self._view_toggle_btn.setText("☰")
            self._view_toggle_btn.setToolTip("Switch to list view")
            if self.current_slides:
                self._slides_stack.setCurrentIndex(0)

    # ── Editor panel collapse / expand (Task 4) ───────────────────────────────

    def _toggle_editor_panel(self):
        """Collapse or expand the lyrics editor section in the center splitter."""
        sizes = self._center_splitter.sizes()
        total = sum(sizes)
        if sizes[1] > 10:
            # Collapse — remember current size for later restore
            self._editor_saved_size = sizes[1]
            self._center_splitter.setSizes([total, 0])
            self._editor_collapse_btn.setText("▲")
        else:
            # Expand to saved size or default 30 %
            saved = getattr(self, '_editor_saved_size', max(120, int(total * 0.30)))
            self._center_splitter.setSizes([total - saved, saved])
            self._editor_collapse_btn.setText("▼")

    # ── Aspect ratio detection & propagation (Task 2) ─────────────────────────

    def _detect_aspect_ratio(self) -> float:
        """
        Detect the aspect ratio of the first open display window's screen.
        Falls back to settings key 'display_aspect' then 16:9.
        Common ratios: 16/9=1.777, 4/3=1.333, 16/10=1.6, 21/9=2.333
        """
        # Use the robust screen-size getter (handles Electron proxies, whose
        # .screen() is unreliable, by falling back to the non-primary monitor).
        try:
            sw, sh = self._get_display_screen_size()
            if sw > 0 and sh > 0:
                return sw / sh
        except Exception:
            pass
        # Fallback: settings key or 16:9
        try:
            return float(self.settings.get("display_aspect", 16 / 9))
        except (ValueError, TypeError):
            return 16 / 9

    def _apply_aspect_ratio(self, ratio: float = 0.0):
        """Push a new aspect ratio to the preview widget and refresh thumbnails."""
        if ratio <= 0:
            ratio = self._detect_aspect_ratio()
        self._display_aspect = ratio
        # Update preview widget
        if hasattr(self, 'preview'):
            self.preview.set_aspect_ratio(ratio)
        # Update render engine display & preview sizes based on actual geometry
        if self.display_windows:
            dw = self.display_windows[0]
            dw_w = dw.width()  if dw.width()  > 0 else 1920
            dw_h = dw.height() if dw.height() > 0 else 1080
            self.render_engine.set_display_size(dw_w, dw_h)
        if hasattr(self, 'preview'):
            pw = self.preview.width()
            ph = self.preview.height()
            if pw > 0 and ph > 0:
                self.render_engine.set_preview_size(pw, ph)
        # Reshape the embedded Electron HD preview to the new aspect (it reads
        # self._display_aspect to drive its height from its width).
        if getattr(self, "_embed_container", None) is not None:
            try: self._fit_embed()
            except Exception: pass
        # Rebuild thumbnails with new ratio — but PRESERVE the operator's selected
        # slide (_set_slides always re-selects slide 0). Without this, opening the
        # Display re-lays-out the thumbnails and would reset the selection to slide 1.
        if self.current_slides:
            _keep = self.current_slide_idx
            self._set_slides(self.current_slides)
            if 0 <= _keep < len(self.current_slides):
                self._select_slide_silent(_keep)

    def _get_display_screen_size(self) -> tuple[int, int]:
        """Return (width, height) of the display screen in pixels.

        Checks open display windows first; falls back to QScreen geometry
        for the secondary monitor, then to 1920×1080.
        """
        # 1. Open Electron display window
        if self.display_windows:
            try:
                dw = self.display_windows[0]
                scr = dw.screen()
                if scr:
                    g = scr.geometry()
                    if g.width() > 0 and g.height() > 0:
                        return g.width(), g.height()
            except Exception:
                pass

        # 2. Non-primary screen (the projector/TV)
        from PyQt6.QtWidgets import QApplication
        screens = QApplication.screens()
        for scr in screens:
            if scr is not QApplication.primaryScreen():
                g = scr.geometry()
                if g.width() > 0 and g.height() > 0:
                    return g.width(), g.height()

        # 3. Settings override
        try:
            aspect_str = self.settings.get("display_aspect", "")
            if aspect_str:
                # No explicit w/h in settings — return 1920 with calculated h
                a = float(aspect_str)
                if a > 0:
                    return 1920, max(1, round(1920 / a))
        except (ValueError, TypeError, AttributeError):
            pass

        # 4. Default 1920×1080
        return 1920, 1080

    def _update_preview_aspect(self) -> None:
        """Update preview widget resolution/aspect from the actual display screen."""
        sw, sh = self._get_display_screen_size()
        if hasattr(self, 'preview'):
            self.preview.set_target_resolution(sw, sh)

    def _init_preview_aspect(self) -> None:
        """Called once at startup (300 ms after window is shown)."""
        self._update_preview_aspect()

    # ── Presentations tab ─────────────────────────────────────────────────────

    def _build_presentations_tab(self):
        w = QWidget()
        w.setStyleSheet("background: #131313;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        hdr = QLabel("PRESENTATIONS")
        hdr.setObjectName("section_lbl")
        layout.addWidget(hdr)

        self._pres_list = QListWidget()
        self._pres_list.setStyleSheet(
            "QListWidget { background: #131313; border: none; }"
            "QListWidget::item { padding: 8px 10px; border-radius: 4px; "
            "margin: 1px 2px; color: #cccccc; }"
            "QListWidget::item:hover { background: #1c1c1c; }"
            "QListWidget::item:selected { background: #1c3a5a; color: #e0e0e0; }"
        )
        self._pres_list.itemDoubleClicked.connect(self._open_presentation)
        layout.addWidget(self._pres_list, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        new_p = QPushButton("+ New")
        edit_p = QPushButton("Edit")
        load_p = QPushButton("▶ Load")
        del_p = QPushButton("Delete")
        for b, s in [
            (new_p, "#18283a"), (edit_p, "#1c1c1c"), (load_p, "#183818"), (del_p, "#1c1c1c")
        ]:
            b.setStyleSheet(
                f"QPushButton {{ background: {s}; color: {'#5294e2' if s=='#18283a' else '#5aaa5a' if s=='#183818' else '#aaa'}; "
                f"border: 1px solid #222; border-radius: 4px; padding: 5px 8px; font-size: 11px; }}"
                f"QPushButton:hover {{ background: #222; color: #e0e0e0; }}"
            )
            btn_row.addWidget(b)
        del_p.setStyleSheet(
            "QPushButton { background: #1c1c1c; color: #f44336; border: 1px solid #221414; "
            "border-radius: 4px; padding: 5px 8px; font-size: 11px; }"
            "QPushButton:hover { background: #221414; border-color: #f44336; }"
        )
        new_p.clicked.connect(self._new_presentation)
        edit_p.clicked.connect(self._open_presentation)
        load_p.clicked.connect(self._load_presentation_to_live)
        del_p.clicked.connect(self._delete_presentation)
        layout.addLayout(btn_row)

        self._load_presentations_list()
        return w

    def _load_presentations_list(self):
        if not hasattr(self, '_pres_list'):
            return
        self._pres_list.clear()
        for p in db.get_all_presentations():
            n = len(p["slides"])
            item = QListWidgetItem(f"{p['title']}  ({n} slide{'s' if n != 1 else ''})")
            item.setData(Qt.ItemDataRole.UserRole, p["id"])
            self._pres_list.addItem(item)

    def _new_presentation(self):
        name, ok = QInputDialog.getText(self, "New Presentation", "Presentation title:")
        if not ok or not name.strip():
            return
        from presentation_editor import PresentationEditorWindow
        self._pres_editor = PresentationEditorWindow(title=name.strip(), parent=None)
        self._pres_editor.saved.connect(lambda pid, t, s: self._load_presentations_list())
        self._pres_editor.show()

    def _open_presentation(self):
        item = self._pres_list.currentItem()
        if not item:
            return
        pres_id = item.data(Qt.ItemDataRole.UserRole)
        pres = db.get_presentation(pres_id)
        if not pres:
            return
        from presentation_editor import PresentationEditorWindow
        self._pres_editor = PresentationEditorWindow(
            pres_id=pres["id"],
            title=pres["title"],
            slides=pres["slides"],
            parent=None
        )
        self._pres_editor.saved.connect(lambda pid, t, s: self._load_presentations_list())
        self._pres_editor.show()

    def _load_presentation_to_live(self):
        item = self._pres_list.currentItem()
        if not item:
            return
        pres_id = item.data(Qt.ItemDataRole.UserRole)
        pres = db.get_presentation(pres_id)
        if not pres or not pres["slides"]:
            QMessageBox.information(self, "Empty", "This presentation has no slides.")
            return
        self._in_pres_mode = True
        self._pres_slides_data = pres["slides"]
        self.current_slides = [f"[Slide {i+1}]" for i in range(len(pres["slides"]))]
        self.current_song_id = None
        self.song_title_edit.setText(pres["title"])
        self._set_slides_pres(pres["slides"])
        self._update_status(song_msg=f"Prezentare: {pres['title']}")

    def _set_slides_pres(self, slides):
        """Set slide view for presentation pixmap slides."""
        from presentation_editor import render_slide_to_pixmap
        self._thumbnails.clear()
        while self.slides_grid.count():
            item = self.slides_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._slide_list_widget.clear()

        tw, th = THUMB_SIZES.get(self._thumb_size_key, THUMB_SIZES["S"])
        avail_w = self.slides_container.width() or 500
        cols = max(1, (avail_w - 24) // (tw + 8))

        for i, slide_data in enumerate(slides):
            pix = render_slide_to_pixmap(slide_data, tw, th)
            thumb = SlideThumbnail(f"[Slide {i+1}]", i, self.settings, thumb_w=tw, thumb_h=th)
            thumb._pres_pixmap = pix
            thumb._orig_paint = thumb.paintEvent

            def make_pres_paint(t, p):
                def pres_paint(event):
                    painter = QPainter(t)
                    painter.drawPixmap(0, 0, p.scaled(
                        t.thumb_w, t.thumb_h,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    ))
                    if t._selected:
                        pen = QPen(QColor("#5294e2"))
                        pen.setWidth(2)
                        painter.setPen(pen)
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        painter.drawRect(0, 0, t.thumb_w - 1, t.thumb_h + 22 - 1)
                    painter.end()
                return pres_paint

            thumb.paintEvent = make_pres_paint(thumb, pix)
            thumb.clicked.connect(self._select_pres_slide)
            self._thumbnails.append(thumb)
            self.slides_grid.addWidget(thumb, i // cols, i % cols)

            item = QListWidgetItem(f"  {i + 1}.  Slide {i + 1}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self._slide_list_widget.addItem(item)

        count = len(slides)
        self._slide_count_lbl.setText(
            f"{count} SLIDE{'S' if count != 1 else ''}" if count else "NO SLIDES"
        )
        if slides:
            self._select_pres_slide(0)

    def _select_pres_slide(self, idx):
        self.current_slide_idx = idx
        for thumb in self._thumbnails:
            thumb.set_selected(thumb.slide_index == idx)
        slides = getattr(self, '_pres_slides_data', [])
        if not slides or idx < 0 or idx >= len(slides):
            return
        slide = slides[idx]
        # Preview: render thumbnail for state
        try:
            from presentation_editor import render_slide_to_pixmap
            pix = render_slide_to_pixmap(slide, 320, 180)
            get_state().set_bg(pixmap=pix)
            get_state().set_text("")
        except Exception:
            pass
        # Live display: send JSON slide data via WebSocket
        if self.display_windows:
            ed = getattr(self, 'electron_display', None)
            if ed is not None:
                for i, dw in enumerate(self.display_windows):
                    wid = i + 1
                    ed._enqueue({
                        "type":          "show_presentation_slide",
                        "window_id":     wid,
                        "slide":         slide,
                        "transition":    slide.get("transition", "fade"),
                        "transition_ms": slide.get("transition_ms", 400),
                    })
            self._is_live = True
            if not self._live_timer.isActive():
                self._live_timer.start(600)

    def _delete_presentation(self):
        item = self._pres_list.currentItem()
        if not item:
            return
        pres_id = item.data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(
            self, "Delete Presentation", "Delete this presentation?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            db.delete_presentation(pres_id)
            self._load_presentations_list()

    # ── Service panel (center-top) methods ────────────────────────────────────

    def _add_selected_to_service(self):
        """Add the currently selected library song to the service list."""
        song_id = self._current_song_list_id()
        if song_id is None:
            return
        self._add_song_id_to_service(song_id)

    def _add_song_id_to_service(self, song_id: int):
        """Add a song by its DB id to the service list (used by button and drag & drop)."""
        song = db.get_song(song_id)
        if not song:
            return
        entry = {
            "type": "song",
            "title": song["title"],
            "slides": song["slides"],
            "notes": song.get("notes", ""),
            "song_id": song_id,
        }
        self._service_items.append(entry)
        self._refresh_service_list()
        self._mark_service_modified(True)

    def _add_verse_to_service(self, v: dict):
        """Add a single Bible verse (from drag & drop) as a service entry."""
        book = v.get("book_name", "")
        ch   = v.get("chapter", "")
        verse_num = v.get("verse", "")
        text = v.get("text", "")
        if not book and hasattr(self, "book_combo"):
            book = self.book_combo.currentText()
        if not ch and hasattr(self, "chapter_combo"):
            ch = self.chapter_combo.currentData()
        ref = f"{book} {ch}:{verse_num}" if book else str(verse_num)
        slide_text = f"{text}\n\n{ref}" if text else ref
        entry = {
            "type": "bible",
            "title": ref,
            "slides": [slide_text],
            "notes": "",
        }
        self._service_items.append(entry)
        self._refresh_service_list()
        self._mark_service_modified(True)

    def _assign_theme_to_service_item(self, svc_idx: int, theme_name: str):
        """Assign a theme (by name) to a service item — shows a badge on the entry."""
        if not (0 <= svc_idx < len(self._service_items)):
            return
        self._service_items[svc_idx]["theme"] = theme_name
        self._refresh_service_list()
        self._mark_service_modified(True)
        try:
            self._toasts.info(f'🎨 Temă "{theme_name}" aplicată pe "{self._service_items[svc_idx]["title"]}"')
        except Exception:
            pass

    def _add_background_to_service(self, bg_path: str):
        """Add a custom background as a service item (drag from the Fundal tab)."""
        import os, json as _json
        if not bg_path or not os.path.exists(bg_path):
            return
        name = os.path.basename(bg_path)[:-5]
        try:
            with open(bg_path, "r", encoding="utf-8") as f:
                name = _json.load(f).get("name", name)
        except Exception:
            pass
        self._service_items.append({
            "type": "background", "bg_path": bg_path,
            "title": name, "slides": [],
        })
        self._refresh_service_list()
        self._mark_service_modified(True)
        try:
            self._toasts.success(f'🎨 Fundal "{name}" adăugat în serviciu')
        except Exception:
            pass

    def _sync_service_items_from_list(self):
        """After internal drag reorder in the service QListWidget, sync _service_items."""
        if not hasattr(self, "_service_list") or not hasattr(self, "_service_items"):
            return
        old_items = list(self._service_items)
        new_items = []
        for i in range(self._service_list.count()):
            idx = self._service_list.item(i).data(Qt.ItemDataRole.UserRole)
            if isinstance(idx, int) and 0 <= idx < len(old_items):
                new_items.append(old_items[idx])
        if new_items:
            self._service_items = new_items
            self._refresh_service_list()
            self._mark_service_modified(True)

    def _refresh_service_list(self):
        if not hasattr(self, '_service_list'):
            return
        self._service_list.clear()
        for i, it in enumerate(self._service_items):
            if it.get("type") == "background":
                text = f"{i + 1}.  🎨 {it.get('title', 'Fundal')}  (fundal)"
            else:
                n = len(it.get("slides", []))
                theme_badge = f"  🎨{it['theme']}" if it.get("theme") else ""
                text = f"{i + 1}.  {it['title']}  ({n} slide{'s' if n != 1 else ''}){theme_badge}"
            lw_item = QListWidgetItem(text)
            lw_item.setData(Qt.ItemDataRole.UserRole, i)
            self._service_list.addItem(lw_item)
        self._push_remote_state()

    def _preview_service_item(self, item):
        idx = item.data(Qt.ItemDataRole.UserRole)
        if 0 <= idx < len(self._service_items):
            entry = self._service_items[idx]
            slides = entry.get("slides", [])
            if slides:
                self.preview.update_text(slides[0])

    def _load_service_item(self, item):
        idx = item.data(Qt.ItemDataRole.UserRole)
        if not (0 <= idx < len(self._service_items)):
            return
        entry = self._service_items[idx]
        if entry.get("type") == "background":
            self._send_background_live(entry.get("bg_path", ""))
            return
        song_id = entry.get("song_id")
        if song_id:
            song = db.get_song(song_id)
            if song:
                self._in_pres_mode = False
                self._pres_pixmaps = []
                self.current_song_id = song_id
                self.current_song_notes = song.get("notes", "")
                self.song_title_edit.setText(song["title"])
                self._load_content_to_editor(song["content"])
                self._set_slides(song["slides"])
                self._update_word_counter()
                self._current_song_formatting = song.get("formatting")
                self._init_toolbar_from_formatting()
                self._update_fmt_status_label()
                self._update_notes_bar(song.get("notes", ""))
                self._update_status(song_msg=song["title"])
                # Apply theme to preview + thumbnails so they match the live
                # display (same as loading from the library/search list).
                _preview_s = self._get_preview_settings(song_id)
                self.preview.apply_settings(_preview_s)
                self._refresh_thumbnails_with_theme(song_id)
                return
        # Fallback: load slides directly from service entry
        self._in_pres_mode = False
        self.current_song_id = None
        self.song_title_edit.setText(entry.get("title", ""))
        slides = entry.get("slides", [])
        content = "\n\n".join(slides)
        self.editor.blockSignals(True)
        self.editor.setPlainText(content)
        self.editor.blockSignals(False)
        self._set_slides(slides)
        self._update_notes_bar(entry.get("notes", ""))
        # Apply theme to preview so it matches the live display
        _preview_s = self._get_preview_settings(None)
        self.preview.apply_settings(_preview_s)
        self._refresh_thumbnails_with_theme(None)

    def _service_move_up(self):
        item = self._service_list.currentItem()
        if not item:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx <= 0:
            return
        self._service_items[idx - 1], self._service_items[idx] = (
            self._service_items[idx], self._service_items[idx - 1]
        )
        self._refresh_service_list()
        self._service_list.setCurrentRow(idx - 1)
        self._mark_service_modified(True)

    def _service_move_down(self):
        item = self._service_list.currentItem()
        if not item:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx >= len(self._service_items) - 1:
            return
        self._service_items[idx], self._service_items[idx + 1] = (
            self._service_items[idx + 1], self._service_items[idx]
        )
        self._refresh_service_list()
        self._service_list.setCurrentRow(idx + 1)
        self._mark_service_modified(True)

    def _service_remove_item(self):
        item = self._service_list.currentItem()
        if not item:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        if 0 <= idx < len(self._service_items):
            self._service_items.pop(idx)
            self._refresh_service_list()
            self._mark_service_modified(True)

    def _clear_service(self):
        if self._service_items and QMessageBox.question(
            self, "Clear Service", "Ștergi tot serviciul?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        self._service_items.clear()
        self._service_path = ""
        self._refresh_service_list()
        self._mark_service_modified(False)

    # ── Service file save/load ────────────────────────────────────────────────

    def _save_service(self):
        if not self._service_items:
            QMessageBox.information(self, "Serviciu gol", "Adaugă cântece la serviciu înainte de salvare.")
            return
        default = self._service_path or "serviciu.gps"
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvează Serviciu", default, "Cantio Service (*.gps)"
        )
        if not path:
            return
        try:
            count = sm.save_service(path, self._service_items, self._profile_name)
            self._service_path = path
            self._mark_service_modified(False)
            self._update_status(song_msg=f"Serviciu salvat: {os.path.basename(path)} ({count} items)")
            self._toasts.success(f"Serviciu salvat: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Eroare", str(e))

    def _open_service(self):
        start = self._service_path or ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Deschide Serviciu", start, "Cantio Service (*.gps)"
        )
        if not path:
            return
        try:
            result = sm.load_service(path)
            self._service_items = result["items"]
            self._service_path = path
            self._refresh_service_list()
            meta = result.get("metadata", {})
            self._update_status(
                song_msg=f"Serviciu: {os.path.basename(path)} — {meta.get('item_count', '?')} items"
            )
            self._mark_service_modified(False)

            # Check for songs missing from the local DB
            missing = []
            for item in self._service_items:
                if item.get("type", "song") == "song":
                    song_id = item.get("song_id")
                    if song_id and not db.get_song(song_id):
                        missing.append(item.get("title", f"ID {song_id}"))
            if missing:
                missing_list = "\n".join(f"  • {t}" for t in missing[:10])
                if len(missing) > 10:
                    missing_list += f"\n  … și alte {len(missing) - 10}"
                QMessageBox.warning(
                    self, "Cântări lipsă din baza de date",
                    f"Următoarele cântări din serviciu nu au fost găsite în baza de date locală:\n\n"
                    f"{missing_list}\n\n"
                    "Ele vor apărea în serviciu, dar nu pot fi afișate pe display.\n"
                    "Importă cântările lipsă sau sincronizează din cloud.",
                )
                self._increment_warnings(len(missing))
        except Exception as e:
            QMessageBox.critical(self, "Eroare", str(e))

    # ── Freeze / Logo / Transparent / Virtual Cam / Remote ────────────────────

    def _clear_text(self):
        """Clear text from all displays without affecting background."""
        self._set_slides_selection_active(False)   # live command → slides not the target
        for dw in self.display_windows:
            if hasattr(dw, "clear_text"):
                dw.clear_text()
            else:
                dw.black_screen()
        self._preview_cmd("clear_text")
        # Sync preview
        if hasattr(self, "preview"):
            self.preview.update_text("")
        from live_state import get_state
        get_state().current_text = ""
        get_state().notify()
        self._update_status(slide_msg="Text cleared")

    def _toggle_freeze(self, checked):
        self._set_slides_selection_active(False)   # live command → slides not the target
        self._is_frozen = checked
        for dw in self.display_windows:
            if checked:
                if hasattr(dw, "freeze_display"):
                    dw.freeze_display()
                else:
                    dw.freeze_black()
            else:
                if hasattr(dw, "unfreeze_display"):
                    dw.unfreeze_display()
                else:
                    dw.unfreeze()
        self._preview_cmd("freeze_display" if checked else "unfreeze_display")
        # Sync preview freeze state
        if hasattr(self, "preview"):
            if checked:
                self.preview.freeze()
            else:
                self.preview.unfreeze()
        self._freeze_btn.setText(f"🔓 {t('unfreeze')}" if checked else f"❄ {t('freeze')}")
        if checked:
            self._is_live = False
            self._live_timer.stop()
            self._live_dot.setStyleSheet("color: #f44336; font-size: 14px;")
            self._status_live_dot.setStyleSheet("color: #f44336; font-size: 14px;")
            self._update_status(slide_msg="FREEZE — display locked")
            self._toasts.warning("Proiectorul este oprit (Freeze). Apasă 🔓 Unfreeze pentru a continua.")
            self._increment_warnings()
        else:
            self._live_dot.setStyleSheet("color: #2a2a2a; font-size: 14px;")
            self._status_live_dot.setStyleSheet("color: #2a2a2a; font-size: 14px;")
            self._increment_warnings(-1)
            self._update_status(slide_msg="")
        self._push_remote_state()

    def _toggle_logo(self, checked):
        self._set_slides_selection_active(False)   # live command → slides not the target
        if checked:
            if self._logo_pixmap is None:
                path, _ = QFileDialog.getOpenFileName(
                    self, "Logo Image", "",
                    "Images (*.png *.jpg *.jpeg *.bmp *.svg)"
                )
                if not path:
                    self._logo_btn.setChecked(False)
                    return
                self._logo_pixmap = QPixmap(path)
                self._logo_file = path
            for dw in self.display_windows:
                dw.show_logo(self._logo_pixmap)
            m = self._preview_mgr()
            if m is not None and getattr(self, "_logo_file", None):
                try: m.show_logo(self._logo_file, -1)
                except Exception: pass
        else:
            for dw in self.display_windows:
                dw.hide_logo()
            m = self._preview_mgr()
            if m is not None:
                try: m.show_logo(None, -1)
                except Exception: pass

    def _toggle_transparent(self):
        if not self.display_windows:
            QMessageBox.information(self, "Display", "Deschide displayul mai întâi.")
            return
        new_state = self.display_windows[0].toggle_transparent()
        for dw in self.display_windows[1:]:
            dw.toggle_transparent()
        self._transparent_btn.setStyleSheet(
            self._btn_style_open() if new_state else self._btn_style_closed()
        )
        self._transparent_btn.setText(
            "🔲 Opac" if new_state else "🔲 Transparent"
        )

    def _toggle_virtual_cam(self):
        try:
            import pyvirtualcam
        except ImportError:
            reply = QMessageBox.question(
                self, "Install pyvirtualcam?",
                "pyvirtualcam nu este instalat. Instalezi acum?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                import subprocess, sys
                subprocess.check_call([sys.executable, "-m", "pip", "install", "pyvirtualcam"])
                QMessageBox.information(self, "OK", "Restartați aplicația pentru a folosi virtual cam.")
            return
        # Virtual cam output is handled via grab_frame → pyvirtualcam in a thread
        QMessageBox.information(self, "Virtual Cam", "Virtual Cam output via OBS Virtual Camera.\nFuncționalitate în dezvoltare.")

    def _toggle_remote(self):
        if self._remote_running:
            rs.stop_server()
            self._remote_running = False
            self._remote_timer.stop()
            self._update_btn_states()
            self._update_status(slide_msg="Remote oprit")
            return

        port = int(self.settings.get("remote_port", 5050))
        result = rs.start_server(self, port)

        if result is False:
            # Flask not installed — offer to install
            reply = QMessageBox.question(
                self, "Install Flask?",
                "Flask nu este instalat.\n\n"
                "Instalezi acum?\n"
                "  pip install flask flask-socketio qrcode[pil] Pillow",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                import subprocess
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install",
                    "flask", "flask-socketio", "qrcode[pil]", "Pillow",
                ])
                QMessageBox.information(
                    self, "OK",
                    "Pachetele au fost instalate.\n"
                    "Restartați aplicația și porniți Remote din nou.")
            return

        url, qr_b64 = result
        self._remote_running = True
        self._remote_songs_dirty = True   # build the remote song-list cache
        self._remote_timer.start(100)     # snappy: poll 10×/s (coalesced)
        self._remote_url = url
        self._update_btn_states()
        self._push_remote_state()
        self._show_remote_qr(url, qr_b64)

    def _show_remote_qr(self, url: str, qr_b64: str = ""):
        dlg = QDialog(self)
        dlg.setWindowTitle("Cantio Remote Control")
        dlg.setMinimumSize(360, 360)
        dlg.setStyleSheet(APP_STYLE)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)

        info = QLabel(f"📱  Accesează de pe telefon sau tabletă:\n\n{url}")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setWordWrap(True)
        info.setStyleSheet(
            "color: #cba6f7; font-size: 13px; font-weight: 600; "
            "background: #1e1e2e; border-radius: 6px; padding: 10px;"
        )
        lay.addWidget(info)

        hint = QLabel("Deschide link-ul sau scanează QR-ul de mai jos:")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #888; font-size: 11px;")
        lay.addWidget(hint)

        # QR code image
        qr_lbl = QLabel()
        qr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_lbl.setFixedSize(220, 220)
        loaded = False

        # 1. Try the pre-generated base64 QR from remote_server
        if qr_b64:
            try:
                import base64 as _b64
                data = _b64.b64decode(qr_b64)
                pix = QPixmap()
                pix.loadFromData(data)
                qr_lbl.setPixmap(pix.scaled(
                    220, 220, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
                loaded = True
            except Exception:
                pass

        # 2. Fallback: generate inline
        if not loaded:
            try:
                import qrcode
                from io import BytesIO
                qr = qrcode.make(url)
                buf = BytesIO()
                qr.save(buf, format="PNG")
                pix = QPixmap()
                pix.loadFromData(buf.getvalue())
                qr_lbl.setPixmap(pix.scaled(
                    220, 220, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
                loaded = True
            except ImportError:
                pass

        if not loaded:
            qr_lbl.setText(f"📱 Deschide în browser:\n{url}")
            qr_lbl.setStyleSheet("color: #888; font-size: 11px;")
        lay.addWidget(qr_lbl)

        ok = QPushButton("✓  OK")
        ok.clicked.connect(dlg.accept)
        ok.setStyleSheet(
            "QPushButton { background: #5294e2; color: #fff; border: none; "
            "border-radius: 5px; padding: 8px 20px; font-weight: 600; }"
            "QPushButton:hover { background: #6ba5f0; }"
        )
        lay.addWidget(ok)
        dlg.exec()

    def _poll_remote_commands(self):
        """Qt-side polling: drains + COALESCES commands from remote web clients.
        Rapid taps (next/prev spam) are collapsed into a single net move so we
        never flood Electron; a re-entrancy guard stops nested processing when a
        command opens a modal dialog."""
        if getattr(self, "_remote_processing", False):
            return
        self._remote_processing = True
        try:
            cmds = []
            while True:
                c = rs.pop_command()
                if c is None:
                    break
                cmds.append(c)
                if len(cmds) >= 200:      # safety cap against a runaway client
                    break
            if not cmds:
                return

            # Coalesce navigation spam + keep only the last explicit slide pick.
            nav_delta = 0
            last_idx = None
            others = []
            for c in cmds:
                a = c.get("action", "")
                if a in ("next", "next_slide"):
                    nav_delta += 1
                elif a in ("prev", "prev_slide"):
                    nav_delta -= 1
                elif a == "go_live" and c.get("idx") is not None:
                    last_idx = int(c.get("idx"))
                else:
                    others.append(c)

            # Execute non-nav commands once each (dedupe idempotent toggles).
            _dedupe = {"black", "black_screen", "clear_text", "freeze", "unfreeze",
                       "open_display", "close_display", "hide_ticker", "logo"}
            seen = set()
            for c in others:
                a = c.get("action", "")
                if a in _dedupe:
                    if a in seen:
                        continue
                    seen.add(a)
                self._exec_remote_command(c)

            # Apply coalesced navigation last (explicit pick wins over delta).
            if last_idx is not None:
                self._send_slide_to_live(last_idx)
            elif nav_delta and self.current_slides:
                target = max(0, min(len(self.current_slides) - 1,
                                    self.current_slide_idx + nav_delta))
                self._send_slide_to_live(target)

            self._push_remote_state()
        finally:
            self._remote_processing = False

    def _exec_remote_command(self, cmd):
        """Execute a single remote command (extracted so polling can coalesce)."""
        action = cmd.get("action", "")
        if True:
            if action == "go_live":
                idx = cmd.get("idx", self.current_slide_idx)
                self._send_slide_to_live(idx)

            elif action in ("black", "black_screen"):
                self._black_screen()

            elif action == "clear_text":
                self._clear_text()

            elif action == "freeze":
                if not self._is_frozen:
                    self._freeze_btn.setChecked(True)
                    self._toggle_freeze(True)

            elif action == "unfreeze":
                if self._is_frozen:
                    self._freeze_btn.setChecked(False)
                    self._toggle_freeze(False)

            elif action == "logo":
                checked = not self._logo_btn.isChecked()
                self._logo_btn.setChecked(checked)
                self._toggle_logo(checked)

            elif action in ("prev", "prev_slide"):
                self._prev_slide()

            elif action in ("next", "next_slide"):
                self._next_slide()

            elif action == "open_display":
                self._open_display()

            elif action == "close_display":
                self._close_display()

            elif action == "ticker":
                text = cmd.get("text", "")
                self.ticker_input.setText(text)
                if text:
                    self._send_ticker()
                else:
                    self._clear_ticker()

            elif action == "hide_ticker":
                self._clear_ticker()

            elif action == "countdown_start":
                self._start_countdown()

            elif action == "countdown_stop":
                for dw in self.display_windows:
                    if hasattr(dw, "stop_countdown"):
                        dw.stop_countdown()

            elif action in ("load_song", "select_song"):
                song_id = cmd.get("song_id")
                if song_id:
                    self._load_song_by_id(song_id)

            elif action in ("service_select", "select_service_item"):
                idx = cmd.get("index", cmd.get("idx", 0))
                self._select_service_item(idx)

    def _select_service_item(self, idx: int):
        """Load service item at *idx* from the remote — same as double-click in UI."""
        if not hasattr(self, "_service_list"):
            return
        if 0 <= idx < self._service_list.count():
            lw_item = self._service_list.item(idx)
            if lw_item:
                self._service_list.setCurrentRow(idx)
                self._load_service_item(lw_item)

    def _push_remote_state(self):
        if not self._remote_running:
            return

        # Current slide text (may be a dict or a plain string)
        raw = (self.current_slides[self.current_slide_idx]
               if 0 <= self.current_slide_idx < len(self.current_slides)
               else "")
        current_text = raw.get("text", raw) if isinstance(raw, dict) else str(raw)

        # Slides list for the remote slides tab
        slides_payload = []
        for i, s in enumerate(self.current_slides):
            text  = s.get("text",  s) if isinstance(s, dict) else str(s)
            label = s.get("label", "") if isinstance(s, dict) else ""
            slides_payload.append({"idx": i, "text": text, "label": label})

        # Current song info
        current_song = None
        if self.current_song_id:
            try:
                song = db.get_song(self.current_song_id)
                if song:
                    current_song = {
                        "id":     song["id"],
                        "title":  song["title"],
                        "author": song.get("author", ""),
                    }
            except Exception:
                pass

        # Service items
        svc_items = []
        if hasattr(self, "_service_items"):
            for it in self._service_items:
                if isinstance(it, dict):
                    svc_items.append({
                        "title":       it.get("title", ""),
                        "slide_count": len(it.get("slides", [])),
                        "type":        it.get("type", "song"),
                    })

        # Song list — CACHED (rebuilt only when the library changes, not on every
        # navigation) so remote commands stay snappy and don't hammer the DB.
        if getattr(self, "_remote_songs_dirty", True):
            try:
                songs = db.get_all_songs()
                self._remote_song_list = [{"id": s["id"], "title": s["title"]}
                                          for s in songs[:300]]
            except Exception:
                self._remote_song_list = []
            self._remote_songs_dirty = False
        song_list = getattr(self, "_remote_song_list", [])

        # Theme colours so the phone's live preview approximates the projector.
        try:
            _ts = self._resolve_settings(
                source=("bible" if self._is_bible_mode() else "songs"),
                song_id=self.current_song_id)
            theme_bg   = _ts.get("bg_color", "#000000") or "#000000"
            theme_text = _ts.get("text_color", "#ffffff") or "#ffffff"
        except Exception:
            theme_bg, theme_text = "#000000", "#ffffff"

        rs.update_state(
            theme_bg=theme_bg,
            theme_text=theme_text,
            live_text=current_text,
            current_text=current_text,
            current_title=self.song_title_edit.text(),
            slide_index=max(0, self.current_slide_idx),
            slide_count=len(self.current_slides),
            slides=slides_payload,
            current_song=current_song,
            is_live=self._is_live,
            is_frozen=self._is_frozen,
            display_open=bool(self.display_windows),
            ticker=self.ticker_input.text() if hasattr(self, "ticker_input") else "",
            service_items=svc_items,
            service_index=(self._service_list.currentRow()
                           if hasattr(self, "_service_list") else -1),
            song_list=song_list,
        )

        # Broadcast to all connected WebSocket clients
        rs.notify_state_change()

    # ── Dual Language ─────────────────────────────────────────────────────────

    def _toggle_dual_lang(self, checked: bool):
        self._dual_lang_active = checked
        if checked:
            self._toasts.info("Dual Language activat. Traducerea apare sub text.")

    def _open_translation_dialog(self):
        text = self.editor.toPlainText().strip()
        if not text:
            self._toasts.warning("Editorul este gol — adaugă text înainte de traducere.")
            return
        existing = {}
        if self.current_song_id:
            try:
                existing = db.get_song_translations(self.current_song_id)
            except Exception:
                pass
        from translation_dialog import TranslationDialog
        dlg = TranslationDialog(
            song_text=text,
            song_id=self.current_song_id,
            existing_translations=existing,
            parent=self,
        )
        dlg.exec()
        self._dual_lang_target = dlg.get_target_lang()

    def _build_dual_lang_text(self, original: str) -> str:
        """Append translation for current slide index below the original text."""
        try:
            translations = db.get_song_translations(self.current_song_id)
            full_tr = translations.get(self._dual_lang_target, "")
            if not full_tr:
                return original
            tr_slides = [s.strip() for s in full_tr.split("\n\n") if s.strip()]
            idx = self.current_slide_idx
            if 0 <= idx < len(tr_slides):
                return original + "\n\n─────────────────\n\n" + tr_slides[idx]
            return original
        except Exception:
            return original

    def _toggle_live_preview(self, checked: bool):
        """Toggle visibility of the renderer-based preview panel."""
        if hasattr(self, '_preview_wrap'):
            self._preview_wrap.setVisible(checked)

    def _grab_live_preview(self):
        """No-op — frame-grab replaced by renderer-based PreviewWidget."""
        pass

    # ── Thumbnail size ─────────────────────────────────────────────────────────

    def _change_thumb_size(self, delta: int):
        idx = _THUMB_SIZE_ORDER.index(self._thumb_size_key)
        idx = max(0, min(len(_THUMB_SIZE_ORDER) - 1, idx + delta))
        new_key = _THUMB_SIZE_ORDER[idx]
        if new_key == self._thumb_size_key:
            return
        self._thumb_size_key = new_key
        self._thumb_size_lbl.setText(new_key)
        db.save_setting("thumb_size", new_key)
        # Rebuild current slides with new size
        if self._in_pres_mode and self._pres_slides_data:
            self._set_slides_pres(self._pres_slides_data)
        else:
            self._set_slides(self.current_slides)

    def _rebuild_current_slides(self):
        """Re-run the slide grid build (after a view-mode toggle)."""
        if self._in_pres_mode and self._pres_slides_data:
            self._set_slides_pres(self._pres_slides_data)
        else:
            self._set_slides(self.current_slides)

    def _toggle_thumb_transparency(self, checked: bool):
        self._thumbs_transparent = checked
        self._rebuild_current_slides()

    def _toggle_slides_by_label(self, checked: bool):
        self._slides_by_label = checked
        self._rebuild_current_slides()

    def _reflow_thumbnails(self):
        """Redistribute existing thumbnails in grid when container width changes."""
        if not self._thumbnails:
            return
        tw, _ = THUMB_SIZES.get(self._thumb_size_key, THUMB_SIZES["S"])
        avail_w = self.slides_container.width()
        if avail_w <= 0:
            return
        cols = max(1, (avail_w - 24) // (tw + 8))
        # Remove without deleting widgets
        while self.slides_grid.count():
            self.slides_grid.takeAt(0)
        if getattr(self, "_slides_by_label", False):
            # One row per label group — order preserved, independent of width
            row = col = 0
            prev = None
            for thumb in self._thumbnails:
                lbl = getattr(thumb, "label", "") or ""
                if prev is not None and lbl != prev:
                    row += 1; col = 0
                self.slides_grid.addWidget(thumb, row, col)
                col += 1; prev = lbl
        else:
            for i, thumb in enumerate(self._thumbnails):
                self.slides_grid.addWidget(thumb, i // cols, i % cols)

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj is self.slides_container and event.type() == QEvent.Type.Resize:
            self._reflow_thumbnails()
        elif obj is getattr(self, "_preview_wrap", None) and \
                event.type() == QEvent.Type.Resize and \
                getattr(self, "_embed_container", None) is not None:
            self._fit_embed()
        return super().eventFilter(obj, event)

    # ── Language refresh ──────────────────────────────────────────────────────

    def _on_language_changed(self, lang: str):
        """Called when the user changes the UI language in settings. Restarts so
        the ENTIRE UI (menubar, tabs, editors, all dialogs) rebuilds in the new
        language — far more reliable than live-retranslating hundreds of widgets."""
        from translations import set_language
        set_language(lang)
        try:
            db.save_setting("language", lang)
        except Exception:
            pass
        self._refresh_all_ui_texts()   # immediate partial refresh (before restart)
        r = QMessageBox.question(
            self, "Limbă / Language",
            "Schimbarea limbii repornește aplicația pentru a traduce tot.\n"
            "Changing the language restarts the app to translate everything.\n\n"
            "Continui acum? / Restart now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes)
        if r == QMessageBox.StandardButton.Yes:
            self._restart_with_profile(self._profile_name)

    def _refresh_all_ui_texts(self):
        """Update visible UI text labels after a language change (no restart needed)."""
        from translations import t
        # Main action buttons
        for attr, key in [
            ("go_live_btn",  "go_live"),
            ("black_btn",    "black_screen"),
            ("clear_btn",    "clear_text"),
            ("freeze_btn",   "freeze"),
            ("logo_btn",     "logo"),
            ("prev_btn",     "anterior"),
            ("next_btn",     "urmator"),
        ]:
            w = getattr(self, attr, None)
            if w is not None:
                try:
                    w.setText(t(key))
                except Exception:
                    pass
        # Preview label
        for attr, key in [
            ("preview_label", "preview_output"),
            ("live_dot",      "live"),
        ]:
            w = getattr(self, attr, None)
            if w is not None:
                try:
                    w.setText(t(key))
                except Exception:
                    pass
        # Refresh Bible Control Tab labels if present
        try:
            if hasattr(self, "_bible_control_tab"):
                self._bible_control_tab.refresh_ui_texts()
        except Exception:
            pass
        self.update()

    # ── Settings ──────────────────────────────────────────────────────────────

    def _open_settings(self):
        dlg = SettingsDialog(self, self.settings)
        dlg.settingsChanged.connect(self._apply_settings)
        dlg.exec()

    def _apply_settings(self, s):
        new_lang = s.get("language", "ro")
        old_lang = self.settings.get("language", "ro") if hasattr(self, 'settings') else "ro"
        if new_lang != old_lang:
            self._on_language_changed(new_lang)
        self.settings = s
        self.preview.apply_settings(s)
        self._update_preview_aspect()

        # Push updated settings into the render engine (clears text cache, adjusts FPS)
        self.render_engine.set_settings(s)

        # Push background image into render engine
        import os as _os
        bg_image = s.get("bg_image", "")
        if bg_image and _os.path.exists(bg_image):
            from PyQt6.QtGui import QPixmap as _QPixmap
            _pix = _QPixmap(bg_image)
            self.render_engine.set_bg(_pix if not _pix.isNull() else None)
        else:
            self.render_engine.set_bg(None)

        # Video background: hand off to MediaEngine (cv2 path) if available
        bg_video = s.get("bg_video", "")
        if bg_video and _os.path.exists(bg_video):
            self.media_engine.play(bg_video)
            # Wire back-pressure: RenderEngine notifies VideoDecodeThread
            # when it has consumed each frame, so frames never pile up.
            self.render_engine.set_video_source(self.media_engine)
        else:
            self.media_engine.stop()
            self.render_engine.set_video_source(None)
            self.render_engine.clear_video_frame()

        # Reload display configs (they may have been updated in settings dialog)
        self._display_configs = db.get_display_configs()
        # Apply settings to each open display window (merged with its per-window overrides)
        configs = self._display_configs
        for i, dw in enumerate(self.display_windows):
            # Find matching config by window_name
            cfg = next((c for c in configs if c.get("name") == dw.window_name), None)
            merged = dict(s)
            if cfg:
                merged.update(cfg.get("settings", {}))
            dw.apply_settings(merged)
        for thumb in self._thumbnails:
            thumb.update_settings(s)

        # Update display-mode indicator in status bar
        if hasattr(self, "_status_mode_lbl"):
            _dm = s.get("display_mode", "settings")
            _mode_text = "🎨 Teme active" if _dm == "themes" else "⚙ Setări globale"
            self._status_mode_lbl.setText(_mode_text)
            self._status_mode_lbl.setStyleSheet(
                "color: #c9a0dc;" if _dm == "themes" else "color: #555555;"
            )

        # In themes mode: if something is already live, retransmit with the
        # resolved theme so the active display immediately picks up theme changes.
        if s.get("display_mode") == "themes" and self._is_live and self.display_windows:
            try:
                _src  = getattr(self, "_current_source", "songs")
                _sid  = self.current_song_id
                _live = self._resolve_settings(source=_src, song_id=_sid)
                for dw in self._target_windows():
                    dw.apply_settings(_live)
            except Exception:
                pass

    # ── Keyboard ──────────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()
        focused = QApplication.focusWidget()

        # Let text inputs handle their own keys (except Escape)
        if isinstance(focused, (QLineEdit, QTextEdit)):
            if key == Qt.Key.Key_Escape:
                self._black_screen()
            else:
                super().keyPressEvent(event)
            return

        if key in (Qt.Key.Key_Space, Qt.Key.Key_Return):
            self._go_live()
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_Down, Qt.Key.Key_PageDown):
            # Next slide + send live
            if self.current_slide_idx < len(self.current_slides) - 1:
                self._select_slide(self.current_slide_idx + 1)
                if self._is_live or self.display_windows:
                    self._go_live()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Up, Qt.Key.Key_PageUp):
            # Prev slide + send live
            if self.current_slide_idx > 0:
                self._select_slide(self.current_slide_idx - 1)
                if self._is_live or self.display_windows:
                    self._go_live()
        elif key == Qt.Key.Key_Escape:
            self._black_screen()
        elif key == Qt.Key.Key_F5:
            self._open_display()
        else:
            super().keyPressEvent(event)

    def changeEvent(self, event):
        """Pause non-critical background tasks when window is minimized."""
        from PyQt6.QtCore import QEvent
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized():
                self._pause_background_tasks()
            else:
                self._resume_background_tasks()

    def _pause_background_tasks(self):
        """
        Pause timers and threads that don't need to run when minimized.
        Live projector display is NOT paused — it stays active.
        """
        # Pause live preview widget repaints (saves CPU)
        if hasattr(self, 'preview'):
            from live_state import get_state
            get_state().remove_observer(self.preview.update)
        # Pause songs model debounce
        if hasattr(self, 'songs_model'):
            self.songs_model._load_timer.stop()
        # Pause auto-advance if running
        if hasattr(self, '_auto_advance_timer') and self._auto_advance_timer.isActive():
            self._auto_advance_was_running = True
            self._auto_advance_timer.stop()
        else:
            self._auto_advance_was_running = False

    def _resume_background_tasks(self):
        """Restart tasks that were paused on minimize."""
        if hasattr(self, 'preview'):
            from live_state import get_state
            state = get_state()
            if self.preview.update not in state._observers:
                state.add_observer(self.preview.update)
            self.preview.update()
        if hasattr(self, '_auto_advance_was_running') and self._auto_advance_was_running:
            if hasattr(self, '_auto_advance_timer'):
                self._auto_advance_timer.start()

    def closeEvent(self, event):
        # Warn about unsaved service
        if self._service_modified and self._service_items:
            reply = QMessageBox.question(
                self, "Serviciu nesalvat",
                "Serviciul curent are modificări nesalvate.\n\n"
                "Vrei să salvezi înainte să închizi?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if reply == QMessageBox.StandardButton.Save:
                self._save_service()
                if self._service_modified:
                    # Save was cancelled or failed — abort close
                    event.ignore()
                    return

        # ── Auto-save: flush any pending debounce changes immediately ─────────
        if hasattr(self, "_autosave_debounce") and self._autosave_debounce.isActive():
            self._autosave_debounce.stop()
            self._do_autosave()

        # ── Unsaved-songs dialog ───────────────────────────────────────────────
        # Only show when there are truly unsaved songs (modified_songs that still
        # differ from DB).  In practice this only triggers if the user quits
        # within milliseconds of a change before auto-save had a chance to run.
        if self._modified_songs:
            self._show_unsaved_songs_dialog(event)
            if not event.isAccepted():
                return

        # ── Save window state ─────────────────────────────────────────────────
        self._save_window_state()

        self._autosave_song()
        self._close_all_displays()
        if self._stage_editor:
            self._stage_editor.close()
        if self._remote_running:
            rs.stop_server()
        self._remote_timer.stop()
        if hasattr(self, '_preview_timer') and self._preview_timer is not None:
            self._preview_timer.stop()
        self._live_timer.stop()

        # Stop render + media engines
        self.render_engine.stop()
        self.media_engine.stop()

        # Stop Electron companion display process
        if getattr(self, "electron_display", None) is not None:
            try:
                self.electron_display.stop()
            except Exception:
                pass

        # Stop all cameras in media tab if open
        for i in range(self._left_tabs.count()):
            w = self._left_tabs.widget(i)
            if hasattr(w, '_stop_all_cameras'):
                w._stop_all_cameras()

        # Stop all remaining QTimers
        for timer in self.findChildren(QTimer):
            timer.stop()

        event.accept()
        QApplication.instance().quit()

    def _show_unsaved_songs_dialog(self, event):
        """
        Shows a dialog listing songs modified during this session.
        Called from closeEvent only when _modified_songs is non-empty.
        Sets event.accept() / event.ignore() appropriately.
        """
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel,
            QListWidget, QListWidgetItem, QPushButton,
        )
        from datetime import datetime

        # Filter to only songs that still differ from their saved version
        # (auto-save may already have saved them — compare DB vs in-memory)
        unsaved_ids = list(self._modified_songs.keys())
        if not unsaved_ids:
            event.accept()
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Cântări modificate în această sesiune")
        dlg.setMinimumWidth(440)
        dlg.setMinimumHeight(280)
        dlg.setStyleSheet(APP_STYLE)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)
        layout.setContentsMargins(18, 16, 18, 16)

        title_lbl = QLabel(
            "💾 Aceste cântări au fost salvate automat în această sesiune:"
        )
        title_lbl.setStyleSheet("font-size: 12px; color: #cdd6f4;")
        title_lbl.setWordWrap(True)
        layout.addWidget(title_lbl)

        song_list = QListWidget()
        song_list.setStyleSheet(
            "QListWidget { background: #1e1e2e; border: 1px solid #313244; "
            "border-radius: 5px; }"
            "QListWidget::item { padding: 6px 10px; color: #cdd6f4; }"
            "QListWidget::item:alternate { background: #181825; }"
        )
        song_list.setAlternatingRowColors(True)
        for sid, info in self._modified_songs.items():
            QListWidgetItem(f"  {info.get('title', f'ID {sid}')}", song_list)
        layout.addWidget(song_list, 1)

        info_lbl = QLabel(
            "✅ Auto-save a salvat automat toate modificările.\n"
            "Închiderea este sigură."
        )
        info_lbl.setStyleSheet("color: #a6e3a1; font-size: 10px;")
        layout.addWidget(info_lbl)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Anulează")
        cancel_btn.setStyleSheet(
            "QPushButton { background: #313244; color: #cdd6f4; "
            "border: 1px solid #45475a; border-radius: 5px; padding: 6px 16px; }"
            "QPushButton:hover { background: #45475a; }"
        )
        close_btn = QPushButton("✓  Închide")
        close_btn.setDefault(True)
        close_btn.setStyleSheet(
            "QPushButton { background: #a6e3a1; color: #1e1e2e; border: none; "
            "border-radius: 5px; padding: 6px 18px; font-weight: bold; }"
            "QPushButton:hover { background: #94d49b; }"
        )

        def on_close(checked=False):
            dlg.accept()
            event.accept()

        def on_cancel(checked=False):
            dlg.reject()
            event.ignore()

        cancel_btn.clicked.connect(on_cancel)
        close_btn.clicked.connect(on_close)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dlg.exec()

    def _save_window_state(self):
        """Persist window geometry, splitter positions, tab states to cache.json."""
        try:
            screens = QApplication.screens()
            # Find which monitor the window center is on
            monitor_idx = 0
            cx, cy = self.geometry().center().x(), self.geometry().center().y()
            for i, scr in enumerate(screens):
                if scr.geometry().contains(cx, cy):
                    monitor_idx = i
                    break

            stage_geom = {}
            if self._stage_editor and self._stage_editor.isVisible():
                sg = self._stage_editor.geometry()
                stage_geom = {"x": sg.x(), "y": sg.y(),
                              "width": sg.width(), "height": sg.height()}

            state = {
                "maximized":       self.isMaximized(),
                "fullscreen":      self.isFullScreen(),
                "x":               self.geometry().x(),
                "y":               self.geometry().y(),
                "width":           self.geometry().width(),
                "height":          self.geometry().height(),
                "monitor_index":   monitor_idx,
                "splitter_sizes":         self._main_splitter.sizes(),
                "left_splitter_sizes":   self._left_splitter.sizes(),
                "center_splitter_sizes": self._center_splitter.sizes(),
                "active_tab":            self._left_tabs.currentIndex(),
                "thumbnail_size":  self._thumb_size_key,
                "slide_view":      self._slide_view_mode,
                "last_service":    self._service_path,
                "displays_were_open": len(self.display_windows) > 0,
                "stage_was_open":  bool(self._stage_editor and self._stage_editor.isVisible()),
                "stage_geometry":  stage_geom,
            }
            db.save_window_state(state)
        except Exception:
            pass   # never crash on state save

    def _restore_window_state(self):
        """Restore window geometry, splitters, tabs from cache.json."""
        try:
            state = db.get_window_state() or {}

            # Geometry
            if state.get("maximized"):
                self.showMaximized()
            elif state.get("fullscreen"):
                self.showFullScreen()
            elif "x" in state and "width" in state:
                self.setGeometry(
                    state["x"], state["y"],
                    state["width"], state["height"]
                )

            # Main horizontal splitter — default [265, 640, 305]
            sizes = state.get("splitter_sizes", [265, 640, 305])
            if isinstance(sizes, list) and len(sizes) == 3:
                self._main_splitter.setSizes(sizes)

            # Left vertical splitter (Service / Tabs) — default [230, 430]
            sizes = state.get("left_splitter_sizes", [230, 430])
            if isinstance(sizes, list) and len(sizes) == 2:
                self._left_splitter.setSizes(sizes)

            # Center vertical splitter (slides / editor) — default [400, 300]
            sizes = state.get("center_splitter_sizes", [400, 300])
            if isinstance(sizes, list) and len(sizes) == 2:
                self._center_splitter.setSizes(sizes)
                # Sync the collapse button icon
                if hasattr(self, '_editor_collapse_btn'):
                    self._editor_collapse_btn.setText(
                        "▲" if sizes[1] <= 10 else "▼"
                    )

            # Left tabs
            if "active_tab" in state:
                self._left_tabs.setCurrentIndex(int(state["active_tab"]))

            # Thumbnail size
            if "thumbnail_size" in state:
                key = state["thumbnail_size"]
                if key in THUMB_SIZES:
                    self._thumb_size_key = key
                    if hasattr(self, '_thumb_size_lbl'):
                        self._thumb_size_lbl.setText(key)

            # Slide view mode
            if "slide_view" in state:
                self._slide_view_mode = state["slide_view"]

            # Stage monitor
            if state.get("stage_was_open"):
                QTimer.singleShot(400, self._open_stage_monitor)
                sg = state.get("stage_geometry", {})
                if sg and self._stage_editor:
                    self._stage_editor.setGeometry(
                        sg.get("x", 100), sg.get("y", 100),
                        sg.get("width", 800), sg.get("height", 600)
                    )

            # Displays
            if state.get("displays_were_open"):
                QTimer.singleShot(600, self._open_display)

            # Toast: offer to reopen last service
            last_svc = state.get("last_service", "")
            if last_svc and os.path.exists(last_svc):
                import os as _os
                svc_name = _os.path.basename(last_svc)
                QTimer.singleShot(1200, lambda: self._offer_reopen_service(last_svc, svc_name))

        except Exception:
            pass   # never crash on state restore

    def _offer_reopen_service(self, path: str, name: str):
        """Show a dialog offering to reopen the last service file."""
        reply = QMessageBox.question(
            self, "Redeschide serviciu",
            f"Ultimul serviciu utilizat:\n\n  📁  {name}\n\n"
            "Dorești să îl redeschizi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                import service_manager as _sm
                result = _sm.load_service(path)
                self._service_items = result["items"]
                self._service_path = path
                self._refresh_service_list()
                self._mark_service_modified(False)
                meta = result.get("metadata", {})
                self._update_status(
                    song_msg=f"Serviciu: {name} — {meta.get('item_count', '?')} items"
                )
                self._toasts.success(f"Serviciu redeschis: {name}")
            except Exception as e:
                QMessageBox.critical(self, "Eroare", str(e))
