"""
Cantio - Profile Password Dialog
Shown when switching to a password-protected profile.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton,
)
from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QFont


class ProfilePasswordDialog(QDialog):
    """Modal dialog that asks for a profile password before switching."""

    def __init__(self, profile: str, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.setWindowTitle("Profil Protejat")
        self.setModal(True)
        self.setFixedWidth(360)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint
        )
        self.setStyleSheet("""
            QDialog {
                background: #1e1e2e;
                color: #cdd6f4;
                border-radius: 10px;
            }
            QLabel { color: #cdd6f4; background: transparent; }
        """)
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(28, 28, 28, 24)

        # Icon
        icon_lbl = QLabel("🔒")
        icon_lbl.setFont(QFont("Segoe UI Emoji", 36))
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_lbl)

        # Title
        title = QLabel(
            f"Profilul «{self.profile}»\neste protejat cu parolă"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 13px; color: #cdd6f4;")
        layout.addWidget(title)

        # Password field
        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_input.setPlaceholderText("Introduceți parola…")
        self.pwd_input.setStyleSheet("""
            QLineEdit {
                background: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus { border-color: #cba6f7; }
        """)
        self.pwd_input.returnPressed.connect(self._verify)
        layout.addWidget(self.pwd_input)

        # Error label
        self.error_lbl = QLabel("")
        self.error_lbl.setStyleSheet("color: #f38ba8; font-size: 11px;")
        self.error_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.error_lbl)

        # Buttons
        btn_row = QHBoxLayout()

        cancel_btn = QPushButton("Anulează")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #313244; color: #cdd6f4;
                border: 1px solid #45475a; border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover { background: #45475a; }
        """)
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton("Intră ▶")
        ok_btn.setDefault(True)
        ok_btn.setStyleSheet("""
            QPushButton {
                background: #cba6f7; color: #1e1e2e;
                border: none; border-radius: 6px;
                padding: 8px 20px; font-weight: bold;
            }
            QPushButton:hover { background: #b794e6; }
        """)
        ok_btn.clicked.connect(self._verify)

        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    # ── Logic ─────────────────────────────────────────────────────────────────

    def _verify(self):
        from profile_security import check_password
        pwd = self.pwd_input.text()
        if check_password(self.profile, pwd):
            self.accept()
        else:
            self.error_lbl.setText("❌ Parolă incorectă! Încearcă din nou.")
            self.pwd_input.clear()
            self.pwd_input.setFocus()
            self._shake()

    def _shake(self):
        """Brief horizontal shake animation on wrong password."""
        origin = self.pos()
        offsets = [10, -10, 8, -8, 5, -5, 2, -2, 0]

        def _step(i: int = 0):
            if i < len(offsets):
                self.move(origin.x() + offsets[i], origin.y())
                QTimer.singleShot(28, lambda: _step(i + 1))
            else:
                self.move(origin)

        _step()
