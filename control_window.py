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
        self._hovered = False
        self.thumb_w = thumb_w
        self.thumb_h = thumb_h
        # Pixmap cache — render once, reuse until mark_dirty()
        self._cached_pixmap = None
        self._dirty = True
        self.setFixedSize(self.thumb_w, self.thumb_h + 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        # Never take focus — prevent stealing the caret from the lyrics editor
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def set_selected(self, val):
        if self._selected != val:
            self._selected = val
            self.mark_dirty()

    def mark_dirty(self):
        """Invalidate cached pixmap; schedules a repaint."""
        self._cached_pixmap = None
        self._dirty = True
        self.update()

    def update_settings(self, settings):
        self.settings = settings
        self.mark_dirty()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Save whatever widget had focus (typically the lyrics editor) so we
            # can restore it after the click handler runs.  This prevents the
            # thumbnail from stealing the caret while the user is typing.
            prev_focus = QApplication.focusWidget()
            self.clicked.emit(self.slide_index)
            if prev_focus is not None and prev_focus is not self:
                QTimer.singleShot(0, prev_focus.setFocus)

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
        if bg_type == "gradient":
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
        bar_color = QColor("#1a3355" if self._selected else "#161616")
        p.fillRect(label_rect, bar_color)

        # Number badge
        badge_color = QColor("#5294e2") if self._selected else QColor("#2a2a2a")
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
            pen = QPen(QColor("#5294e2"))
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

    def sizeHint(self, option, index):
        text = index.data(Qt.ItemDataRole.UserRole) or ""
        lines = max(1, text.count("\n") + 1)
        return QSize(option.rect.width(),
                     max(44, lines * self._LINE_H + self._PADDING * 2))

    def paint(self, painter, option, index):
        painter.save()

        text    = index.data(Qt.ItemDataRole.UserRole) or ""
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
    def __init__(self, profile_name="Default"):
        super().__init__()
        self._profile_name = profile_name
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

        # Toast notification manager (must be created after window is built)
        self._toasts = ToastManager(self)
        set_global_toast_manager(self._toasts)

        # Electron display companion process (optional; falls back to PyQt DisplayWindow)
        try:
            from electron_display import ElectronDisplayManager
            self.electron_display = ElectronDisplayManager()
            self.electron_display.start()
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

        # Live pulse timer
        self._live_timer = QTimer(self)
        self._live_timer.timeout.connect(self._pulse_live)
        self._live_pulse_state = True

        # Auto-advance timer
        self._auto_timer = QTimer(self)
        self._auto_timer.timeout.connect(self._auto_advance)

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
        left_frame.setMinimumWidth(235)
        left_frame.setMaximumWidth(320)
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
        right_frame.setMinimumWidth(275)
        right_frame.setMaximumWidth(350)
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
        layout.addWidget(self.search_edit)

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
        self._center_tab_widget.addTab(editor_pane, "📝 Editor Versuri")

        try:
            from media_tab import MediaTab
            self._media_tab = MediaTab(self)
            self._center_tab_widget.addTab(self._media_tab, "🖼 Media")
        except Exception:
            pass

        # Online tab removed — use File ▸ Import for online songs

        try:
            from themes_tab import ThemesTab
            self._themes_tab = ThemesTab(self)
            self._themes_tab_ref = self._themes_tab
            self._center_tab_widget.addTab(self._themes_tab, "🎨 Teme")
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

        try:
            from overlay_tab import OverlayTab
            self._overlay_tab = OverlayTab(parent_control=self)
            self._center_tab_widget.addTab(self._overlay_tab, "🎭 Overlay")
        except Exception as _e:
            self._overlay_tab = None
            print(f"[OVERLAY TAB] init failed: {_e}")

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
        layout.addWidget(scroll, 1)

        # ── Mini video player (hidden until media is selected) ─────────────
        self.mini_player = MiniVideoPlayer()
        self.mini_player.parent_control = self
        layout.addWidget(self.mini_player)

        return w

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
        # Also populate [Label] markers in the editor for dict-format slides
        self._load_slides_to_editor_with_labels(song["slides"])
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

    def _update_notes_bar(self, notes):
        self.current_song_notes = notes
        if notes.strip():
            self.notes_display.setText(notes)
            self.notes_bar.show()
        else:
            self.notes_bar.hide()
        self._push_stage_state()

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
            'lc': 'Luca', 'luca': 'Luca', 'in': 'Ioan', 'joan': 'Ioan', 'jn': 'Ioan',
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
        if not book_name:
            for abbr, name in abbreviations.items():
                if book_key.startswith(abbr):
                    book_name = name
                    break
        if not book_name:
            try:
                books = db.get_bible_books()
                for b in books:
                    if (book_key in b['name'].lower() or
                            b['name'].lower().startswith(book_key)):
                        book_name = b['name']
                        break
            except Exception:
                pass
        if not book_name:
            return None

        chapter = None
        verse = None
        if rest:
            try:
                chapter = int(rest[0])
            except ValueError:
                return None
        if len(rest) >= 2:
            try:
                verse = int(rest[1])
            except ValueError:
                pass

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
        if verse is not None and hasattr(self, 'verse_list'):
            for i in range(self.verse_list.count()):
                item = self.verse_list.item(i)
                v = item.data(Qt.ItemDataRole.UserRole)
                if v and v.get('verse') == verse:
                    self.verse_list.setCurrentItem(item)
                    self.verse_list.scrollToItem(item)
                    self._preview_verse(item)
                    break
        # Sync verse combo to the target verse number
        if verse is not None and hasattr(self, 'verse_combo'):
            for i in range(self.verse_combo.count()):
                v_data = self.verse_combo.itemData(i)
                if v_data and v_data.get('verse') == verse:
                    self.verse_combo.blockSignals(True)
                    self.verse_combo.setCurrentIndex(i)
                    self.verse_combo.blockSignals(False)
                    break
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

    def _load_slides_to_editor_with_labels(self, slides: list):
        """
        Load slides as plain text with [Label] markers so the editor
        shows section headings visually.  Only used for plain-text songs
        that have dict slides with label data.
        """
        if not slides:
            return
        # Only apply if at least one slide has a label
        has_labels = any(
            isinstance(s, dict) and s.get("label")
            for s in slides
        )
        if not has_labels:
            return
        lines: list[str] = []
        for s in slides:
            if isinstance(s, dict):
                label = s.get("label", "")
                text  = s.get("text", "")
            else:
                label = ""
                text  = str(s)
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
            self._thumbnails.append(thumb)
            self.slides_grid.addWidget(thumb, i // cols, i % cols)

        # ── List view — full text via custom delegate ─────────────────────────
        self._slide_list_widget.clear()
        for i, slide in enumerate(slides):
            item = QListWidgetItem()          # delegate does all painting
            item.setData(Qt.ItemDataRole.UserRole, slide)       # full text
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
        else:
            # Show placeholder when no slides loaded
            self._slides_stack.setCurrentIndex(2)
            self.preview.update_text("")

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
            self.preview.update_text(self.current_slides[idx])
        if 0 <= idx < len(self._thumbnails):
            self.slides_scroll.ensureWidgetVisible(self._thumbnails[idx])
        # Sync list view selection
        self._slide_list_widget.blockSignals(True)
        self._slide_list_widget.setCurrentRow(idx)
        self._slide_list_widget.blockSignals(False)
        self._push_stage_state()
        # Return keyboard focus to the main window so arrow keys work immediately
        self.setFocus()
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
        if self.settings.get("display_mode", "settings") != "themes":
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

    # ── Theme helpers ─────────────────────────────────────────────────────────

    def _get_themes_path(self) -> str:
        """Return the themes.json path for the active profile."""
        import os
        profile = getattr(self, "_profile_name",
                          getattr(self, "_current_profile", "default"))
        return os.path.join(
            os.path.expanduser("~"), "Cantio", "profiles",
            profile, "themes.json")

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
            merged["bg_image"] = str(bg.get("camera_id", "0"))
            merged["bg_transparent"] = "false"

        elif bg_type == "transparent":
            merged["bg_transparent"] = "true"
            merged["bg_color"]  = "#00000000"
            merged["bg_image"]  = ""
            merged["bg_video"]  = ""

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
        if self.settings.get("display_mode", "settings") != "themes":
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
        self._select_slide(idx)
        if self.display_windows:
            self._go_live()
        self._push_remote_state()

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
        targets = self._target_windows()
        if self._in_pres_mode and self._pres_pixmaps:
            if self.current_slide_idx < len(self._pres_pixmaps):
                for dw in targets:
                    dw.show_slide_image(self._pres_pixmaps[self.current_slide_idx])
                self._is_live = True
                if not self._live_timer.isActive():
                    self._live_timer.start(600)
                total = len(self._pres_pixmaps)
                self._update_status(slide_msg=f"Slide {self.current_slide_idx + 1}/{total}")
        elif self.current_slides:
            text = self.current_slides[self.current_slide_idx]
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
            for dw in targets:
                dw.apply_settings(_live_settings)
                dw.show_text(text, _live_fmt, metadata=self._current_metadata)
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
        for dw in self.display_windows:
            dw.black_screen()
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

            self.display_windows.append(dw)

        n = len(self.display_windows)
        self._update_status(display_msg=f"{n} display{'s' if n != 1 else ''} open")
        self._update_send_combo()
        self._update_btn_states()
        # Detect screen aspect ratio and update preview + thumbnails
        QTimer.singleShot(100, self._apply_aspect_ratio)
        QTimer.singleShot(150, self._update_preview_aspect)
        # Push current slide after display finishes loading (1.5 s grace period)
        if self.current_slide_idx >= 0:
            QTimer.singleShot(1500, self._send_current_slide_on_open)
        # Notify remote clients that a display is now open
        self._push_remote_state()

    def _close_all_displays(self):
        for dw in self.display_windows:
            dw.close()
        self.display_windows.clear()
        self._is_live = False
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

    def _send_current_slide_on_open(self):
        """
        Push the currently-selected slide to freshly-opened displays.
        Called 1.5 s after _open_display() so Electron has time to finish loading.
        """
        if not self.display_windows or self._is_frozen:
            return
        if self.current_slide_idx < 0:
            return
        # Re-use the GO LIVE path (handles presentation mode, dual-lang, formatting, etc.)
        self._go_live()

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
        current = self.current_slides[self.current_slide_idx] if (
            0 <= self.current_slide_idx < len(self.current_slides)
        ) else ""
        next_text = self.current_slides[self.current_slide_idx + 1] if (
            0 <= self.current_slide_idx + 1 < len(self.current_slides)
        ) else ""
        self._stage_editor.update_state(current, next_text, self.current_song_notes)

    # ── Overlay Controls ──────────────────────────────────────────────────────

    def _send_ticker(self):
        text = self.ticker_input.text().strip()
        if not text:
            return
        ticker_settings = {
            "speed":          float(self.settings.get("ticker_speed",        3)),
            "font_size":      int(self.settings.get("ticker_font_size",      22)),
            "font_family":    self.settings.get("ticker_font_family",        "Arial"),
            "text_color":     self.settings.get("ticker_color",              "#f9e2af"),
            "bg_color":       self.settings.get("ticker_bg_color",           "rgba(0,0,0,0.85)"),
            "bar_height":     int(self.settings.get("ticker_height",         52)),
            "position":       self.settings.get("ticker_position",           "bottom"),
            "ticker_in_effect":  self.settings.get("ticker_in_effect",       "slide_up"),
            "ticker_out_effect": self.settings.get("ticker_out_effect",      "slide_down"),
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
        # Build clock settings from global settings (with sensible defaults)
        clock_fmt   = self.settings.get("clock_format", "HH:MM:SS")
        clock_settings = {
            "clock_format":  clock_fmt,
            "format_24h":    clock_fmt != "12h",
            "show_seconds":  clock_fmt == "HH:MM:SS",
            "color":         self.settings.get("clock_color",      "#ffffff"),
            "font_size":     int(self.settings.get("clock_font_size",   22)),
            "font_family":   self.settings.get("clock_font_family", "Consolas"),
            "position":      self.settings.get("clock_position",   "top_right"),
            "bg_enabled":    self.settings.get("clock_bg_enabled",  "false") == "true",
            "bg_color":      self.settings.get("clock_bg_color",   "rgba(0,0,0,0.5)"),
        }
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

        targets = self._target_windows() if self.display_windows else []
        for dw in targets:
            dw.apply_settings(live_settings)
            dw.show_text(text, metadata=metadata)

        # Update preview (do NOT overwrite song slides — bible verses are separate)
        self.preview.update_text(text)
        self.preview.apply_settings(live_settings)
        self.render_engine.set_text(text, None)

        self._is_live = bool(targets)
        if targets and not self._live_timer.isActive():
            self._live_timer.start(600)
        self._update_status(song_msg=ref or "Bible")
        self._push_stage_state()
        self._push_remote_state()

    # ── Tab sync helpers ──────────────────────────────────────────────────────

    def _on_left_tab_changed(self, idx: int):
        """When the sidebar switches to the Bible tab, switch center to Control Bible."""
        try:
            tab_text = self._left_tabs.tabText(idx)
        except Exception:
            return
        if "ibli" not in tab_text and "ible" not in tab_text:
            return
        # Find and activate the Control Bible center tab
        for i in range(self._center_tab_widget.count()):
            if "Bible" in self._center_tab_widget.tabText(i) or \
               "iblie" in self._center_tab_widget.tabText(i):
                self._center_tab_widget.blockSignals(True)
                self._center_tab_widget.setCurrentIndex(i)
                self._center_tab_widget.blockSignals(False)
                break

    def _on_center_tab_changed(self, idx: int):
        """When center switches to Control Bible, switch sidebar to Bible."""
        try:
            tab_text = self._center_tab_widget.tabText(idx)
        except Exception:
            return
        if "Bible" not in tab_text and "iblie" not in tab_text:
            return
        for i in range(self._left_tabs.count()):
            lt = self._left_tabs.tabText(i)
            if "ibli" in lt or "ible" in lt:
                self._left_tabs.blockSignals(True)
                self._left_tabs.setCurrentIndex(i)
                self._left_tabs.blockSignals(False)
                break
        # Give focus to the tab so arrow keys work immediately
        if getattr(self, "_bible_control_tab", None):
            self._bible_control_tab.setFocus()

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
        # Save current state
        self._save_current_song()
        self._close_all_displays()
        if self._stage_editor:
            self._stage_editor.close()
            self._stage_editor = None
        # Switch profile
        self._profile_name = new_profile
        pm.create_profile(new_profile)
        db.set_active_profile(new_profile)
        db.init_db()
        self.settings = db.get_settings()
        self.preview.apply_settings(self.settings)
        self.setWindowTitle(f"Cantio — {new_profile}")
        self._profile_btn.setText(f"👤 {new_profile}")
        # Reload UI
        self.current_slides = []
        self.current_slide_idx = -1
        self.current_song_id = None
        self.current_song_notes = ""
        self.song_title_edit.clear()
        self.editor.clear()
        self._set_slides([])
        self._load_library()
        self._load_presentations_list()
        self._update_status(
            song_msg=f"Profile: {new_profile}",
            display_msg="No display open"
        )

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
        if self.display_windows:
            try:
                dw = self.display_windows[0]
                scr = dw.screen()
                if scr:
                    g = scr.geometry()
                    if g.height() > 0:
                        return g.width() / g.height()
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
        # Rebuild thumbnails with new ratio
        if self.current_slides:
            self._set_slides(self.current_slides)

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
        from presentation_editor import render_slide_to_pixmap
        # Store rendered pixmaps and load as a slide set
        self._pres_pixmaps = [
            render_slide_to_pixmap(s, 1920, 1080)
            for s in pres["slides"]
        ]
        self._in_pres_mode = True
        self._pres_slides_data = pres["slides"]
        # Show as thumbnails in center panel (reuse current_slides with placeholder text)
        self.current_slides = [f"[Slide {i+1}]" for i in range(len(pres["slides"]))]
        self.current_song_id = None
        self.song_title_edit.setText(pres["title"])
        self._set_slides_pres(pres["slides"])
        self._update_status(song_msg=f"Presentation: {pres['title']}")

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
        if hasattr(self, '_pres_pixmaps') and 0 <= idx < len(self._pres_pixmaps):
            # Show preview pixmap via shared state
            get_state().set_bg(pixmap=self._pres_pixmaps[idx])
            get_state().set_text("")
        if self.display_windows and hasattr(self, '_pres_pixmaps'):
            for dw in self.display_windows:
                dw.show_slide_image(self._pres_pixmaps[idx])
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
        for dw in self.display_windows:
            if hasattr(dw, "clear_text"):
                dw.clear_text()
            else:
                dw.black_screen()
        # Sync preview
        if hasattr(self, "preview"):
            self.preview.update_text("")
        from live_state import get_state
        get_state().current_text = ""
        get_state().notify()
        self._update_status(slide_msg="Text cleared")

    def _toggle_freeze(self, checked):
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
            for dw in self.display_windows:
                dw.show_logo(self._logo_pixmap)
        else:
            for dw in self.display_windows:
                dw.hide_logo()

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
        self._remote_timer.start(300)
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
        """Qt-side polling: drains commands queued by remote web clients."""
        changed = False
        while True:
            cmd = rs.pop_command()
            if cmd is None:
                break
            changed = True
            action = cmd.get("action", "")

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

        if changed:
            self._push_remote_state()

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

        # Song list (lightweight, first 300)
        try:
            songs = db.get_all_songs()
            song_list = [{"id": s["id"], "title": s["title"]} for s in songs[:300]]
        except Exception:
            song_list = []

        rs.update_state(
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
        for i, thumb in enumerate(self._thumbnails):
            self.slides_grid.addWidget(thumb, i // cols, i % cols)

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj is self.slides_container and event.type() == QEvent.Type.Resize:
            self._reflow_thumbnails()
        return super().eventFilter(obj, event)

    # ── Language refresh ──────────────────────────────────────────────────────

    def _on_language_changed(self, lang: str):
        """Called when the user changes the UI language in settings."""
        from translations import set_language
        set_language(lang)
        self._refresh_all_ui_texts()

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
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_Down):
            # Next slide + send live
            if self.current_slide_idx < len(self.current_slides) - 1:
                self._select_slide(self.current_slide_idx + 1)
                if self._is_live or self.display_windows:
                    self._go_live()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Up):
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
