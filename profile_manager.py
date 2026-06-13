"""
Cantio - Profile Manager
Profile creation, selection, deletion, renaming, legacy DB migration,
password protection, and per-profile restrictions.
"""
import os
import json
import shutil
import hashlib

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QInputDialog, QMessageBox, QLineEdit,
    QFormLayout, QGroupBox, QCheckBox, QDialogButtonBox, QTabWidget,
    QWidget, QScrollArea,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from translations import t

PROFILES_DIR = os.path.join(os.path.expanduser("~"), "Cantio", "profiles")
LAST_PROFILE_FILE = os.path.join(os.path.expanduser("~"), "Cantio", "last_profile.json")
LEGACY_DB = os.path.join(os.path.expanduser("~"), "Cantio", "cantio.db")


def list_profiles():
    os.makedirs(PROFILES_DIR, exist_ok=True)
    try:
        return sorted(
            d for d in os.listdir(PROFILES_DIR)
            if os.path.isdir(os.path.join(PROFILES_DIR, d))
        )
    except Exception:
        return []


def profile_db_path(name):
    return os.path.join(PROFILES_DIR, name, "cantio.db")


def create_profile(name):
    path = os.path.join(PROFILES_DIR, name)
    os.makedirs(path, exist_ok=True)
    return path


def delete_profile(name):
    path = os.path.join(PROFILES_DIR, name)
    if os.path.isdir(path):
        shutil.rmtree(path)


def rename_profile(old_name, new_name):
    old_path = os.path.join(PROFILES_DIR, old_name)
    new_path = os.path.join(PROFILES_DIR, new_name)
    os.rename(old_path, new_path)


def get_last_profile():
    try:
        with open(LAST_PROFILE_FILE, "r") as f:
            return json.load(f).get("last_profile", "")
    except Exception:
        return ""


def save_last_profile(name):
    os.makedirs(os.path.dirname(LAST_PROFILE_FILE), exist_ok=True)
    with open(LAST_PROFILE_FILE, "w") as f:
        json.dump({"last_profile": name}, f)


def has_legacy_db():
    return os.path.exists(LEGACY_DB)


def migrate_legacy_to_profile(profile_name):
    """Copy legacy single DB to the given profile directory."""
    create_profile(profile_name)
    dest = profile_db_path(profile_name)
    if os.path.exists(LEGACY_DB) and not os.path.exists(dest):
        shutil.copy2(LEGACY_DB, dest)


# ── Password / restrictions helpers ──────────────────────────────────────────

def _profile_config_path(name: str) -> str:
    return os.path.join(PROFILES_DIR, name, "profile_config.json")


def _load_profile_config(name: str) -> dict:
    try:
        with open(_profile_config_path(name), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_profile_config(name: str, cfg: dict):
    path = _profile_config_path(name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def set_profile_password(profile: str, password: str):
    """Set (or clear if empty) a password for the given profile."""
    cfg = _load_profile_config(profile)
    if password:
        cfg["password_hash"]    = _hash_password(password)
        cfg["password_enabled"] = True
    else:
        cfg.pop("password_hash", None)
        cfg["password_enabled"] = False
    _save_profile_config(profile, cfg)


def check_profile_password(profile: str, password: str) -> bool:
    """Return True if *password* matches the stored hash (or no password set)."""
    cfg = _load_profile_config(profile)
    stored = cfg.get("password_hash")
    if not stored:
        return True        # no password → always OK
    return _hash_password(password) == stored


def profile_has_password(profile: str) -> bool:
    """Return True if the profile has a password set."""
    cfg = _load_profile_config(profile)
    return bool(cfg.get("password_hash"))


def get_profile_restrictions(profile: str) -> dict:
    """Return the restrictions dict for the given profile."""
    cfg = _load_profile_config(profile)
    return cfg.get("restrictions", {})


def set_profile_restrictions(profile: str, restrictions: dict):
    """Save restrictions for the given profile."""
    cfg = _load_profile_config(profile)
    cfg["restrictions"] = restrictions
    _save_profile_config(profile, cfg)


# ── Dialog style ──────────────────────────────────────────────────────────────

_STYLE = """
QDialog, QWidget {
    background-color: #181818;
    color: #e0e0e0;
    font-family: 'Segoe UI', sans-serif;
    font-size: 12px;
}
QListWidget {
    background: #141414;
    color: #e0e0e0;
    border: 1px solid #222;
    border-radius: 6px;
    padding: 4px;
    outline: none;
}
QListWidget::item { padding: 12px 14px; border-radius: 5px; margin: 2px; }
QListWidget::item:hover { background: #1e1e1e; }
QListWidget::item:selected { background: #1c3a5a; color: #e0e0e0; }
QPushButton {
    background: #232323; color: #e0e0e0;
    border: 1px solid #2c2c2c; border-radius: 5px;
    padding: 8px 16px; font-size: 12px;
}
QPushButton:hover { background: #2a2a2a; border-color: #3a3a3a; }
QPushButton:disabled { color: #444; }
QLabel { color: #cccccc; }
"""


class ProfileSelectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Cantio — {t('select_profile')}")
        self.setMinimumSize(440, 520)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.setStyleSheet(_STYLE)
        self.selected_profile = None
        self._build_ui()
        self._refresh_list()
        self._check_migration()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(14)

        logo = QLabel("Cantio")
        logo.setStyleSheet(
            "color: #5294e2; font-size: 26px; font-weight: 700; letter-spacing: 2px;"
        )
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)

        sub = QLabel(t("select_profile_to_continue"))
        sub.setStyleSheet("color: #555; font-size: 11px;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

        self.profile_list = QListWidget()
        self.profile_list.setFont(QFont("Segoe UI", 12))
        self.profile_list.itemDoubleClicked.connect(self._open_profile)
        layout.addWidget(self.profile_list, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self.create_btn = QPushButton(f"+ {t('new')}")
        self.rename_btn = QPushButton(t("rename"))
        self.delete_btn = QPushButton(t("delete"))
        self.delete_btn.setStyleSheet(
            "QPushButton { color: #f44336; border-color: #2e1a1a; }"
            "QPushButton:hover { background: #251a1a; border-color: #f44336; }"
        )
        for b in (self.create_btn, self.rename_btn, self.delete_btn):
            btn_row.addWidget(b)
        self.create_btn.clicked.connect(self._create_profile)
        self.rename_btn.clicked.connect(self._rename_profile)
        self.delete_btn.clicked.connect(self._delete_profile)
        layout.addLayout(btn_row)

        self.open_btn = QPushButton(f"{t('open_profile')}  →")
        self.open_btn.setStyleSheet(
            "QPushButton { background: #5294e2; color: #fff; border: none; "
            "border-radius: 6px; padding: 14px 20px; font-size: 13px; font-weight: 700; }"
            "QPushButton:hover { background: #6ba5f0; }"
        )
        self.open_btn.clicked.connect(self._open_profile)
        layout.addWidget(self.open_btn)

    def _refresh_list(self):
        self.profile_list.clear()
        last = get_last_profile()
        profiles = list_profiles()
        select_row = 0
        for i, name in enumerate(profiles):
            item = QListWidgetItem(f"  {name}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            if name == last:
                item.setForeground(QColor("#5294e2"))
                item.setText(f"  {name}   ★")
                select_row = i
            self.profile_list.addItem(item)
        if profiles:
            self.profile_list.setCurrentRow(select_row)

    def _check_migration(self):
        if has_legacy_db() and not list_profiles():
            reply = QMessageBox.question(
                self, "Migrate Existing Data",
                "An existing Cantio database was found.\n\n"
                "Import it into a new profile called 'Default'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                migrate_legacy_to_profile("Default")
                self._refresh_list()

    def _create_profile(self):
        name, ok = QInputDialog.getText(self, "New Profile", "Profile name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        if name in list_profiles():
            QMessageBox.warning(self, "Name Taken", f"Profile '{name}' already exists.")
            return
        create_profile(name)
        self._refresh_list()
        for i in range(self.profile_list.count()):
            if self.profile_list.item(i).data(Qt.ItemDataRole.UserRole) == name:
                self.profile_list.setCurrentRow(i)
                break

    def _rename_profile(self):
        item = self.profile_list.currentItem()
        if not item:
            return
        old_name = item.data(Qt.ItemDataRole.UserRole)
        new_name, ok = QInputDialog.getText(
            self, "Rename Profile", "New name:", text=old_name
        )
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return
        new_name = new_name.strip()
        if new_name in list_profiles():
            QMessageBox.warning(self, "Name Taken", f"Profile '{new_name}' already exists.")
            return
        rename_profile(old_name, new_name)
        if get_last_profile() == old_name:
            save_last_profile(new_name)
        self._refresh_list()

    def _delete_profile(self):
        item = self.profile_list.currentItem()
        if not item:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(
            self, "Delete Profile",
            f"Permanently delete profile '{name}' and ALL its data?\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            delete_profile(name)
            self._refresh_list()

    def _open_profile(self):
        item = self.profile_list.currentItem()
        if not item:
            if self.profile_list.count() == 0:
                create_profile("Default")
                self._refresh_list()
                self.profile_list.setCurrentRow(0)
                item = self.profile_list.currentItem()
                if not item:
                    return
            else:
                return
        name = item.data(Qt.ItemDataRole.UserRole)
        save_last_profile(name)
        self.selected_profile = name
        self.accept()

    def exec(self):
        result = super().exec()
        if result != QDialog.DialogCode.Accepted or not self.selected_profile:
            profiles = list_profiles()
            if not profiles:
                create_profile("Default")
                self.selected_profile = "Default"
            elif not self.selected_profile:
                self.selected_profile = get_last_profile() or profiles[0]
        return result


# ── ProfilePasswordDialog ─────────────────────────────────────────────────────

class ProfilePasswordDialog(QDialog):
    """
    Ask the user for the profile password.
    Returns Accepted only if password matches (or no password is set).
    """

    def __init__(self, profile_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Parolă profil — {profile_name}")
        self.setMinimumWidth(340)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.setStyleSheet(_STYLE)
        self._profile = profile_name
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(12)

        icon_lbl = QLabel("🔒")
        icon_lbl.setStyleSheet("font-size: 32px;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_lbl)

        msg = QLabel(f"Profilul «{self._profile}» este protejat.\nIntroduceți parola:")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setWordWrap(True)
        layout.addWidget(msg)

        self._pw_edit = QLineEdit()
        self._pw_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw_edit.setPlaceholderText("Parolă…")
        self._pw_edit.returnPressed.connect(self._check)
        layout.addWidget(self._pw_edit)

        self._err_lbl = QLabel("")
        self._err_lbl.setStyleSheet("color: #f44336; font-size: 11px;")
        self._err_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._err_lbl)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._check)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _check(self):
        pw = self._pw_edit.text()
        if check_profile_password(self._profile, pw):
            self.accept()
        else:
            self._err_lbl.setText("❌ Parolă incorectă. Încearcă din nou.")
            self._pw_edit.clear()
            self._pw_edit.setFocus()


# ── ProfileSettingsTab ────────────────────────────────────────────────────────

_RESTRICTION_LABELS = {
    "no_delete_songs": "Nu poate șterge cântări",
    "no_import":       "Nu poate importa fișiere",
    "no_settings":     "Nu poate modifica setările",
    "no_themes":       "Nu poate edita temele",
    "no_new_profile":  "Nu poate crea profiluri noi",
}


class ProfileSettingsTab(QWidget):
    """
    Embedded widget (for use inside a QTabWidget) that manages
    password and restrictions for one profile.
    """

    def __init__(self, profile_name: str, parent=None):
        super().__init__(parent)
        self._profile = profile_name
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # ── Password ──────────────────────────────────────────────────────────
        pw_grp = QGroupBox("Parolă profil")
        pf = QFormLayout(pw_grp)

        self._cur_pw_edit = QLineEdit()
        self._cur_pw_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._cur_pw_edit.setPlaceholderText("Parolă curentă (dacă există)…")
        pf.addRow("Parolă curentă:", self._cur_pw_edit)

        self._new_pw_edit = QLineEdit()
        self._new_pw_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._new_pw_edit.setPlaceholderText("Parolă nouă…")
        pf.addRow("Parolă nouă:", self._new_pw_edit)

        self._confirm_pw_edit = QLineEdit()
        self._confirm_pw_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_pw_edit.setPlaceholderText("Confirmă parola…")
        pf.addRow("Confirmă:", self._confirm_pw_edit)

        pw_hint = QLabel("Lasă goale ambele câmpuri pentru a șterge parola.")
        pw_hint.setStyleSheet("color:#666; font-size:11px;")
        pw_hint.setWordWrap(True)
        pf.addRow("", pw_hint)

        set_pw_btn = QPushButton("Setează parola")
        set_pw_btn.clicked.connect(self._set_password)
        pf.addRow("", set_pw_btn)

        self._pw_status_lbl = QLabel("")
        self._pw_status_lbl.setStyleSheet("font-size:11px;")
        pf.addRow("", self._pw_status_lbl)

        layout.addWidget(pw_grp)

        # ── Restrictions ──────────────────────────────────────────────────────
        rest_grp = QGroupBox("Restricții profil")
        rf = QVBoxLayout(rest_grp)

        self._restriction_checks: dict[str, QCheckBox] = {}
        for key, label in _RESTRICTION_LABELS.items():
            cb = QCheckBox(label)
            self._restriction_checks[key] = cb
            rf.addWidget(cb)

        save_rest_btn = QPushButton("Salvează restricțiile")
        save_rest_btn.clicked.connect(self._save_restrictions)
        rf.addWidget(save_rest_btn)

        self._rest_status_lbl = QLabel("")
        self._rest_status_lbl.setStyleSheet("font-size:11px;")
        rf.addWidget(self._rest_status_lbl)

        layout.addWidget(rest_grp)
        layout.addStretch()

    def _load(self):
        restrictions = get_profile_restrictions(self._profile)
        for key, cb in self._restriction_checks.items():
            cb.setChecked(bool(restrictions.get(key, False)))

    def _set_password(self):
        cur  = self._cur_pw_edit.text()
        new1 = self._new_pw_edit.text()
        new2 = self._confirm_pw_edit.text()

        # Verify current password (if one exists)
        if profile_has_password(self._profile):
            if not check_profile_password(self._profile, cur):
                self._pw_status_lbl.setText("❌ Parola curentă este incorectă.")
                self._pw_status_lbl.setStyleSheet("color:#f44336; font-size:11px;")
                return

        if new1 or new2:
            if new1 != new2:
                self._pw_status_lbl.setText("❌ Parola nouă nu coincide.")
                self._pw_status_lbl.setStyleSheet("color:#f44336; font-size:11px;")
                return
            if len(new1) < 4:
                self._pw_status_lbl.setText("❌ Parola trebuie să aibă cel puțin 4 caractere.")
                self._pw_status_lbl.setStyleSheet("color:#f44336; font-size:11px;")
                return

        set_profile_password(self._profile, new1)
        self._cur_pw_edit.clear()
        self._new_pw_edit.clear()
        self._confirm_pw_edit.clear()
        if new1:
            self._pw_status_lbl.setText("✅ Parola a fost setată.")
        else:
            self._pw_status_lbl.setText("✅ Parola a fost eliminată.")
        self._pw_status_lbl.setStyleSheet("color:#66cc66; font-size:11px;")

    def _save_restrictions(self):
        restrictions = {
            key: cb.isChecked()
            for key, cb in self._restriction_checks.items()
        }
        set_profile_restrictions(self._profile, restrictions)
        self._rest_status_lbl.setText("✅ Restricții salvate.")
        self._rest_status_lbl.setStyleSheet("color:#66cc66; font-size:11px;")
