"""
Cantio - Keyboard Shortcuts Registry
Centralizes all shortcut definitions and provides a help dialog.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QHBoxLayout, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

# ── Shortcut definitions ───────────────────────────────────────────────────────
# (group, description, shortcut_display, shortcut_key_for_tooltip)
SHORTCUTS = [
    ("Navigare slide-uri", "Slide următor + trimite live", "→  /  ↓", "→"),
    ("Navigare slide-uri", "Slide anterior + trimite live", "←  /  ↑", "←"),
    ("Navigare slide-uri", "GO LIVE (slide curent)", "Space", "Space"),
    ("Navigare slide-uri", "Black Screen", "Escape", "Esc"),
    ("Ferestre", "Toggle fereastră live (display)", "Ctrl+P", "Ctrl+P"),
    ("Ferestre", "Toggle Stage Monitor", "Ctrl+Shift+P", "Ctrl+Shift+P"),
    ("Ferestre", "Toggle Transparent / Chroma-key", "Ctrl+Shift+T", "Ctrl+Shift+T"),
    ("Ferestre", "Fullscreen display (toggle)", "F11", "F11"),
    ("Ferestre", "Deschide display rapid", "F5", "F5"),
    ("Serviciu", "Salvează serviciu curent", "Ctrl+S", "Ctrl+S"),
    ("Serviciu", "Deschide serviciu (.gps)", "Ctrl+O", "Ctrl+O"),
    ("Serviciu", "Serviciu nou (șterge lista)", "Ctrl+N", "Ctrl+N"),
    ("Aplicație", "Focus căutare cântări", "Ctrl+F", "Ctrl+F"),
    ("Aplicație", "Deschide Import Manager", "Ctrl+I", "Ctrl+I"),
]


def tooltip_for(description: str) -> str:
    """Return tooltip string with shortcut appended, e.g. 'GO LIVE  [Space]'."""
    for _, desc, _, key in SHORTCUTS:
        if desc == description:
            return f"{description}  [{key}]"
    return description


# ── Help Dialog ────────────────────────────────────────────────────────────────

class ShortcutsDialog(QDialog):
    def __init__(self, parent=None, app_style: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts — Cantio")
        self.setMinimumSize(560, 480)
        if app_style:
            self.setStyleSheet(app_style)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        title = QLabel("KEYBOARD SHORTCUTS")
        title.setStyleSheet(
            "color: #5294e2; font-size: 11px; font-weight: 700; letter-spacing: 2px;"
        )
        layout.addWidget(title)

        table = QTableWidget(len(SHORTCUTS), 3)
        table.setHorizontalHeaderLabels(["Grup", "Acțiune", "Scurtătură"])
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setStyleSheet(
            "QTableWidget { background: #141414; border: none; color: #e0e0e0; "
            "alternate-background-color: #181818; gridline-color: #1e1e1e; }"
            "QTableWidget::item { padding: 6px 10px; border: none; }"
            "QTableWidget::item:selected { background: #1c3a5a; color: #e0e0e0; }"
            "QHeaderView::section { background: #0f0f0f; color: #5294e2; "
            "font-size: 10px; font-weight: 700; letter-spacing: 1px; "
            "padding: 6px 10px; border: none; border-bottom: 1px solid #1e1e1e; }"
        )

        groups_seen = {}
        group_colors = {
            "Navigare slide-uri": "#5294e2",
            "Ferestre": "#52b452",
            "Serviciu": "#e2a252",
            "Aplicație": "#e252a2",
        }

        for row, (group, desc, shortcut, _) in enumerate(SHORTCUTS):
            # Group cell
            g_item = QTableWidgetItem(group)
            color = group_colors.get(group, "#888888")
            g_item.setForeground(QColor(color))
            g_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            if group in groups_seen:
                g_item.setText("")  # Collapse repeated group names
            else:
                groups_seen[group] = True
            table.setItem(row, 0, g_item)

            # Description cell
            d_item = QTableWidgetItem(desc)
            d_item.setForeground(QColor("#cccccc"))
            table.setItem(row, 1, d_item)

            # Shortcut cell
            s_item = QTableWidgetItem(shortcut)
            s_item.setForeground(QColor("#5294e2"))
            s_item.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            s_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 2, s_item)

            table.setRowHeight(row, 30)

        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(table, 1)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background: #1e1e1e;")
        layout.addWidget(divider)

        note = QLabel(
            "Scurtăturile de navigare funcționează când cursorul nu e într-un câmp text."
        )
        note.setStyleSheet("color: #555; font-size: 10px;")
        layout.addWidget(note)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Închide")
        close_btn.setStyleSheet(
            "QPushButton { background: #232323; color: #e0e0e0; border: 1px solid #2c2c2c; "
            "border-radius: 5px; padding: 8px 24px; font-size: 12px; }"
            "QPushButton:hover { background: #2a2a2a; }"
        )
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
