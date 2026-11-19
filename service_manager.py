"""
Cantio - Service Manager
Handles saving/loading service orders as .gps files (ZIP archives).
.gps format:
  service.json  - ordered list of songs/slides with title, slides, notes
  metadata.json - date, profile, app version
"""
import os
import json
import zipfile
from datetime import datetime

# Recent-files store
_RECENT_PATH = os.path.join(os.path.expanduser("~"), "Cantio", "recent_services.json")
_MAX_RECENT = 5


# ── Recent files ──────────────────────────────────────────────────────────────

def get_recent_files() -> list[str]:
    """Return list of recent .gps file paths (most recent first)."""
    if not os.path.exists(_RECENT_PATH):
        return []
    try:
        with open(_RECENT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [p for p in data if os.path.exists(p)]
    except Exception:
        return []


def add_recent_file(path: str):
    """Prepend path to recent list, keep last _MAX_RECENT."""
    recent = get_recent_files()
    path = os.path.abspath(path)
    if path in recent:
        recent.remove(path)
    recent.insert(0, path)
    recent = recent[:_MAX_RECENT]
    try:
        os.makedirs(os.path.dirname(_RECENT_PATH), exist_ok=True)
        with open(_RECENT_PATH, "w", encoding="utf-8") as f:
            json.dump(recent, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def remove_recent_file(path: str):
    """Remove a specific path from recent list (e.g. if file was deleted)."""
    recent = get_recent_files()
    path = os.path.abspath(path)
    if path in recent:
        recent.remove(path)
    try:
        with open(_RECENT_PATH, "w", encoding="utf-8") as f:
            json.dump(recent, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ── Save / Load ───────────────────────────────────────────────────────────────

def save_service(path: str, items: list[dict], profile_name: str = "Default") -> int:
    """
    Save service order to a .gps file.

    items: list of dicts with keys:
        type        - "song" | "bible" | "text"
        title       - display title
        slides      - list[str] slide texts
        notes       - operator notes string
        song_id     - int or None
        order       - int position (set automatically)

    Returns count of items saved.
    """
    service_items = []
    for i, item in enumerate(items):
        service_items.append({
            "order": i,
            "type": item.get("type", "song"),
            "title": item.get("title", ""),
            "slides": item.get("slides", []),
            "notes": item.get("notes", ""),
            "song_id": item.get("song_id"),
        })

    metadata = {
        "app": "Cantio",
        "version": "2.0.0",
        "profile": profile_name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "item_count": len(service_items),
    }

    if not path.endswith(".gps"):
        path += ".gps"

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("service.json", json.dumps(service_items, ensure_ascii=False, indent=2))
        zf.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))

    add_recent_file(path)
    return len(service_items)


def load_service(path: str) -> dict:
    """
    Load a .gps service file.

    Returns dict:
        items    - list of item dicts (same schema as save_service input)
        metadata - metadata dict
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Service file not found: {path}")

    with zipfile.ZipFile(path, "r") as zf:
        names = zf.namelist()
        if "service.json" not in names:
            raise ValueError("Invalid .gps file: missing service.json")
        items = json.loads(zf.read("service.json").decode("utf-8"))
        metadata = {}
        if "metadata.json" in names:
            metadata = json.loads(zf.read("metadata.json").decode("utf-8"))

    # Sort by order field
    items.sort(key=lambda x: x.get("order", 0))
    add_recent_file(path)
    return {"items": items, "metadata": metadata}


# ── Windows Registry file association ─────────────────────────────────────────

def register_file_association(exe_path: str = None) -> bool:
    """
    Register .gps extension with Windows Registry so double-clicking opens Cantio.
    exe_path: path to the Python launcher or compiled exe. Defaults to sys.executable.
    Returns True on success, False if not on Windows or insufficient permissions.
    """
    import sys
    import platform
    if platform.system() != "Windows":
        return False
    if exe_path is None:
        exe_path = sys.executable

    try:
        import winreg

        # HKCR\.gps -> "Cantio.Service"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.gps") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Cantio.Service")

        # HKCR\Cantio.Service
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Classes\Cantio.Service") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Cantio Service File")

        # Default icon
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Classes\Cantio.Service\DefaultIcon") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f"{exe_path},0")

        # Open command
        main_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
        cmd = f'"{exe_path}" "{main_py}" "%1"'
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Classes\Cantio.Service\shell\open\command") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, cmd)

        return True
    except Exception:
        return False


def unregister_file_association() -> bool:
    """Remove .gps registry entries."""
    import platform
    if platform.system() != "Windows":
        return False
    try:
        import winreg

        def _del_tree(root, path):
            try:
                with winreg.OpenKey(root, path, 0, winreg.KEY_ALL_ACCESS) as key:
                    while True:
                        try:
                            subkey = winreg.EnumKey(key, 0)
                            _del_tree(root, f"{path}\\{subkey}")
                        except OSError:
                            break
                winreg.DeleteKey(root, path)
            except FileNotFoundError:
                pass

        _del_tree(winreg.HKEY_CURRENT_USER, r"Software\Classes\Cantio.Service")
        _del_tree(winreg.HKEY_CURRENT_USER, r"Software\Classes\.gps")
        return True
    except Exception:
        return False
