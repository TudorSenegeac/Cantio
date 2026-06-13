"""
Cantio — Cross-platform path helpers
All code should import paths from here instead of building
them inline with os.path.expanduser("~").

Platform layout
---------------
Windows : %USERPROFILE%/Cantio/
macOS   : ~/Library/Application Support/Cantio/
Linux   : ~/.local/share/Cantio/
"""
from __future__ import annotations

import os
import sys


def get_app_dir() -> str:
    """Absolute path to the directory that contains main.py / this file."""
    return os.path.dirname(os.path.abspath(__file__))


def get_data_dir():
    import os, sys, shutil

    if sys.platform == 'darwin':
        base = os.path.expanduser("~/Library/Application Support")
    elif sys.platform == 'win32':
        base = os.path.expanduser("~")
    else:
        base = os.path.expanduser("~/.local/share")

    new_dir = os.path.join(base, "Cantio")
    old_dir = os.path.join(base, "GlorifyPro")

    if not os.path.exists(new_dir) and os.path.exists(old_dir):
        try:
            shutil.copytree(old_dir, new_dir)
            print("[Cantio] Date migrate din GlorifyPro!")
        except Exception as e:
            print(f"[Cantio] Migrare esuat: {e}")

    os.makedirs(new_dir, exist_ok=True)
    return new_dir


def get_profiles_dir() -> str:
    """Root folder that holds all profile sub-directories."""
    d = os.path.join(get_data_dir(), "profiles")
    os.makedirs(d, exist_ok=True)
    return d


def get_profile_dir(profile: str = "default") -> str:
    """Data directory for a single profile."""
    d = os.path.join(get_profiles_dir(), profile)
    os.makedirs(d, exist_ok=True)
    return d


def get_logs_dir() -> str:
    """Directory for application log files."""
    d = os.path.join(get_data_dir(), "logs")
    os.makedirs(d, exist_ok=True)
    return d


def get_cache_dir() -> str:
    """General cache directory (media cache etc.)."""
    d = os.path.join(get_data_dir(), "cache")
    os.makedirs(d, exist_ok=True)
    return d

