# -*- coding: utf-8 -*-
"""
Cantio — „seed" pentru temele și fundalurile LIVRATE cu aplicația.

La pornire, adaugă temele/fundalurile gata-făcute în profilul activ, FĂRĂ a le
suprascrie pe cele create de utilizator și fără a le re-adăuga pe cele pe care
utilizatorul le-a șters (urmărim ce s-a semănat deja, per profil, în cache).

Așa, la update, apar temele/fundalurile noi PE LÂNGĂ cele făcute în versiunea
veche (nu se pierde nimic).
"""
from __future__ import annotations
import os
import sys
import json
import shutil


def _bundled_dir() -> str:
    cands = []
    base = os.path.dirname(os.path.abspath(__file__))
    cands.append(os.path.join(base, "assets"))
    if getattr(sys, "frozen", False):
        exe = os.path.dirname(sys.executable)
        cands.append(os.path.join(exe, "assets"))
        cands.append(os.path.join(exe, "_internal", "assets"))
        mei = getattr(sys, "_MEIPASS", None)
        if mei:
            cands.append(os.path.join(mei, "assets"))
    for c in cands:
        if os.path.isdir(c):
            return c
    return cands[0]


def _profile_dir(profile: str) -> str:
    return os.path.join(os.path.expanduser("~"), "Cantio", "profiles", profile)


def seed_bundled_assets(profile: str) -> None:
    """Adaugă fundalurile + temele livrate în profilul `profile` (o singură dată
    per element, per profil). Nu suprascrie nimic creat de utilizator."""
    if not profile:
        return
    try:
        import database as db
    except Exception:
        return
    base = _bundled_dir()
    try:
        cache = db.get_cache()
    except Exception:
        cache = {}
    all_seeded = cache.get("seeded_bundled", {})
    if not isinstance(all_seeded, dict):
        all_seeded = {}
    seeded = set(all_seeded.get(profile, []) or [])
    changed = False

    # ── Fundaluri (fișiere .json copiate în profiles/<p>/backgrounds) ───────────
    bg_src = os.path.join(base, "backgrounds")
    bg_dst = os.path.join(_profile_dir(profile), "backgrounds")
    if os.path.isdir(bg_src):
        try:
            os.makedirs(bg_dst, exist_ok=True)
        except Exception:
            pass
        for fn in sorted(os.listdir(bg_src)):
            if not fn.lower().endswith(".json"):
                continue
            marker = "bg:" + fn
            if marker in seeded:
                continue   # deja semănat (chiar dacă userul l-a șters)
            dst = os.path.join(bg_dst, fn)
            try:
                if not os.path.exists(dst):   # nu suprascrie unul cu același nume
                    shutil.copy2(os.path.join(bg_src, fn), dst)
                seeded.add(marker)
                changed = True
            except Exception:
                pass

    # ── Teme (intrări în profiles/<p>/themes.json → "list") ─────────────────────
    themes_src = os.path.join(base, "themes.json")
    if os.path.exists(themes_src):
        try:
            with open(themes_src, encoding="utf-8") as f:
                bundled_themes = json.load(f)
        except Exception:
            bundled_themes = {}
        tp = os.path.join(_profile_dir(profile), "themes.json")
        try:
            with open(tp, encoding="utf-8") as f:
                themes = json.load(f)
        except Exception:
            themes = {}
        lst = themes.setdefault("list", {})
        touched = False
        for name, entry in bundled_themes.items():
            marker = "theme:" + name
            if marker in seeded:
                continue
            if name not in lst:          # nu suprascrie o temă a userului
                lst[name] = entry
                touched = True
            seeded.add(marker)
            changed = True
        if touched:
            try:
                os.makedirs(os.path.dirname(tp), exist_ok=True)
                with open(tp, "w", encoding="utf-8") as f:
                    json.dump(themes, f, ensure_ascii=False, indent=1)
            except Exception:
                pass

    if changed:
        all_seeded[profile] = sorted(seeded)
        cache["seeded_bundled"] = all_seeded
        try:
            db.save_cache(cache)
        except Exception:
            pass
