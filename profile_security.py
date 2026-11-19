"""
Cantio - Profile Security
Password hashing + per-profile restriction storage.
"""
from __future__ import annotations
import hashlib
import json
import os

# ── Available restriction keys ────────────────────────────────────────────────

RESTRICTIONS: dict[str, str] = {
    "no_delete_songs":   "Nu poate șterge cântări",
    "no_edit_songs":     "Nu poate edita cântări",
    "no_import":         "Nu poate importa fișiere",
    "no_export":         "Nu poate exporta",
    "no_settings":       "Nu poate accesa Setări",
    "no_themes":         "Nu poate modifica Teme",
    "no_new_profile":    "Nu poate crea profile noi",
    "no_delete_profile": "Nu poate șterge profiluri",
    "no_bible_import":   "Nu poate importa Biblia",
    "read_only":         "Mod doar citire (nu poate salva)",
}

# ── Path helpers ──────────────────────────────────────────────────────────────

def _profile_dir(profile: str) -> str:
    return os.path.join(
        os.path.expanduser("~"), "Cantio", "profiles", profile
    )


def _config_path(profile: str) -> str:
    return os.path.join(_profile_dir(profile), "profile_config.json")


# ── Config I/O ────────────────────────────────────────────────────────────────

def load_profile_config(profile: str) -> dict:
    path = _config_path(profile)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "password_enabled": False,
        "password_hash":    None,
        "restrictions":     {},
    }


def save_profile_config(profile: str, config: dict) -> None:
    path = _config_path(profile)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


# ── Password management ───────────────────────────────────────────────────────

def set_password(profile: str, password: str) -> None:
    """Set (or clear if empty) the profile password."""
    config = load_profile_config(profile)
    if password:
        hashed = hashlib.sha256(password.encode("utf-8")).hexdigest()
        config["password_enabled"] = True
        config["password_hash"]    = hashed
    else:
        config["password_enabled"] = False
        config["password_hash"]    = None
    save_profile_config(profile, config)


def check_password(profile: str, password: str) -> bool:
    """Return True if *password* matches the stored hash (or no password set)."""
    config = load_profile_config(profile)
    stored = config.get("password_hash", "") or ""
    # Support both schema variants: explicit password_enabled flag (new) and
    # hash-only (legacy written by profile_manager.set_profile_password before fix)
    if not config.get("password_enabled") and not stored:
        return True
    entered = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return entered == stored


def has_password(profile: str) -> bool:
    """Return True if the profile is password-protected."""
    config = load_profile_config(profile)
    return bool(config.get("password_enabled") or config.get("password_hash"))


# ── Restrictions ──────────────────────────────────────────────────────────────

def get_restrictions(profile: str) -> dict:
    return load_profile_config(profile).get("restrictions", {})


def set_restrictions(profile: str, restrictions: dict) -> None:
    config = load_profile_config(profile)
    config["restrictions"] = restrictions
    save_profile_config(profile, config)


def check_restriction(profile: str, key: str) -> bool:
    """Return True if the action identified by *key* is RESTRICTED (forbidden)."""
    return bool(get_restrictions(profile).get(key, False))
