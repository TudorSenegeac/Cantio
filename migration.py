"""
Cantio - Migration Helper
Detects old database formats from earlier versions and migrates them
to the current per-profile layout under ~/Cantio/profiles/<name>/.

Old layouts detected:
  - v1: ~/Cantio/cantio.db          (monolithic, pre-profile)
  - v2: ~/Cantio/profiles/<p>/songs.db  (separate songs + settings split)

Migration copies the old file(s) to the current profile directory and lets
init_db() handle the schema upgrade.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path


# ── Candidate locations for old databases ─────────────────────────────────────

def _old_db_candidates() -> list[Path]:
    base = Path.home() / "Cantio"
    candidates: list[Path] = []
    # v1 monolithic
    mono = base / "cantio.db"
    if mono.exists():
        candidates.append(mono)
    # v2 split (songs only, settings were in a separate file)
    for entry in (base / "profiles").glob("*/songs.db"):
        candidates.append(entry)
    return candidates


def check_and_migrate(profile: str) -> str | None:
    """
    Check for legacy databases. Returns the old file path if one was found
    and migration is needed, None otherwise.
    """
    profile_dir = Path.home() / "Cantio" / "profiles" / profile
    target_db   = profile_dir / "cantio.db"

    if target_db.exists():
        return None   # already migrated or up to date

    for old_path in _old_db_candidates():
        # Skip if it IS in the current profile dir already
        if old_path.parent.resolve() == profile_dir.resolve():
            continue
        try:
            # Quick sanity check: is it a valid SQLite file with a 'songs' table?
            conn = sqlite3.connect(str(old_path))
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            conn.close()
            if "songs" in tables:
                return str(old_path)
        except Exception:
            continue
    return None


def run_migration(old_path: str, profile: str,
                  progress_cb=None) -> bool:
    """
    Copy *old_path* into the current profile directory as cantio.db.
    Returns True on success.
    progress_cb(int) receives values 0-100.
    """
    profile_dir = Path.home() / "Cantio" / "profiles" / profile
    profile_dir.mkdir(parents=True, exist_ok=True)
    target = profile_dir / "cantio.db"

    try:
        if progress_cb:
            progress_cb(10)

        src_size = os.path.getsize(old_path)
        copied   = 0
        buf_size = 256 * 1024  # 256 KB

        with open(old_path, "rb") as src, open(str(target), "wb") as dst:
            while True:
                chunk = src.read(buf_size)
                if not chunk:
                    break
                dst.write(chunk)
                copied += len(chunk)
                if progress_cb and src_size > 0:
                    progress_cb(10 + int(85 * copied / src_size))

        if progress_cb:
            progress_cb(100)
        return True
    except Exception as exc:
        print(f"[MIGRATION] error: {exc}")
        # Clean up partial copy
        if target.exists():
            try:
                target.unlink()
            except Exception:
                pass
        return False


# ── Qt dialog ─────────────────────────────────────────────────────────────────

def show_migration_dialog(old_path: str, profile: str, parent=None) -> bool:
    """
    Ask the user whether to migrate, show progress, return True if migration
    completed (or user skipped), False if user cancelled.
    """
    try:
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QLabel, QProgressBar,
            QPushButton, QHBoxLayout, QApplication,
        )
        from PyQt6.QtCore import Qt, QTimer
    except ImportError:
        # Headless / missing Qt — skip silently
        return True

    old_name = os.path.basename(old_path)
    old_dir  = os.path.dirname(old_path)

    class MigrationDialog(QDialog):
        def __init__(self):
            super().__init__(parent)
            self.setWindowTitle("Cantio — Migrare bază de date")
            self.setFixedSize(460, 240)
            self.setStyleSheet("""
                QDialog { background: #181818; color: #e0e0e0; }
                QLabel  { color: #e0e0e0; font-size: 12px; }
                QPushButton {
                    background: #232323; color: #e0e0e0;
                    border: 1px solid #333; border-radius: 5px;
                    padding: 7px 18px; font-size: 12px;
                }
                QPushButton:hover { background: #2a2a2a; }
                QProgressBar {
                    background: #1c1c1c; border: 1px solid #2e2e2e;
                    border-radius: 4px; height: 14px; text-align: center;
                    color: #ccc; font-size: 10px;
                }
                QProgressBar::chunk { background: #5294e2; border-radius: 3px; }
            """)
            self._success = False

            lay = QVBoxLayout(self)
            lay.setContentsMargins(20, 20, 20, 20)
            lay.setSpacing(12)

            icon_lbl = QLabel("📦")
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            icon_lbl.setStyleSheet("font-size: 32px; background: transparent;")
            lay.addWidget(icon_lbl)

            info = QLabel(
                f"A fost găsită o bază de date dintr-o versiune anterioară:\n"
                f"<b>{old_name}</b> în {old_dir}\n\n"
                f"Dorești să o migrezi în profilul curent <b>{profile}</b>?"
            )
            info.setWordWrap(True)
            info.setTextFormat(Qt.TextFormat.RichText)
            info.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            lay.addWidget(info)

            self._progress = QProgressBar()
            self._progress.setRange(0, 100)
            self._progress.hide()
            lay.addWidget(self._progress)

            self._status_lbl = QLabel("")
            self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            self._status_lbl.setStyleSheet(
                "color: #888; font-size: 10px; background: transparent;"
            )
            lay.addWidget(self._status_lbl)

            btn_row = QHBoxLayout()
            btn_row.setSpacing(10)
            skip_btn = QPushButton("Sari peste")
            skip_btn.clicked.connect(self._skip)
            self._migrate_btn = QPushButton("✓ Migrează")
            self._migrate_btn.setStyleSheet(
                "QPushButton { background: #18283a; color: #5294e2; "
                "border: 1px solid #1c3a5a; border-radius: 5px; "
                "padding: 7px 18px; font-weight: 600; }"
                "QPushButton:hover { background: #1c3a5a; color: #e0e0e0; }"
            )
            self._migrate_btn.clicked.connect(self._do_migrate)
            btn_row.addStretch()
            btn_row.addWidget(skip_btn)
            btn_row.addWidget(self._migrate_btn)
            btn_row.addStretch()
            lay.addLayout(btn_row)

        def _skip(self):
            self._success = True   # user consciously skipped — don't block launch
            self.accept()

        def _do_migrate(self):
            self._migrate_btn.setEnabled(False)
            self._progress.show()
            self._status_lbl.setText("Se copiază…")

            # Run migration in-thread (file copy is fast enough for most DBs)
            def _prog(v):
                self._progress.setValue(v)
                QApplication.processEvents()

            ok = run_migration(old_path, profile, progress_cb=_prog)
            if ok:
                self._status_lbl.setText("Migrare finalizată!")
                self._success = True
                QTimer.singleShot(800, self.accept)
            else:
                self._status_lbl.setText("Eroare la migrare — continuăm fără.")
                self._success = True
                QTimer.singleShot(1500, self.accept)

    dlg = MigrationDialog()
    dlg.exec()
    return dlg._success
