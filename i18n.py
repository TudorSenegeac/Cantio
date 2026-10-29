# -*- coding: utf-8 -*-
"""
Cantio — Sistem de traducere automată (i18n)
===========================================
Cantio e scris în română. Multe texte sunt direct în cod (nu prin cheile din
translations.py), de aceea la schimbarea limbii rămâneau netraduse.

Acest modul traduce TOT ce se vede — butoane, etichete, meniuri, tab-uri,
titluri, tooltip-uri, placeholder-e — parcurgând arborele de widget-uri și
înlocuind textul românesc cu traducerea în limba activă.

Cum funcționează:
  • Memorie de traducere (TM): un cache pe disc per limbă
    (~/Cantio/i18n/<lang>.json) {text_romanesc: traducere}.
  • Se pre-populează din traducerile îngrijite din translations.py (acelea au
    prioritate și merg offline din prima).
  • Textele lipsă se completează ONLINE (Google Translate, fără cheie) pe un fir
    separat și se salvează în cache → data viitoare merg OFFLINE.
  • Până vine traducerea, se afișează textul românesc (fallback), apoi UI-ul se
    reîmprospătează.

Pentru texte dinamice (mesaje/toasturi) folosește `T("text romanesc")`.
"""

import json
import os
import re
import sys
import threading
import urllib.request
import urllib.parse

from PyQt6.QtWidgets import (
    QWidget, QLabel, QAbstractButton, QGroupBox, QLineEdit, QTextEdit,
    QPlainTextEdit, QTabWidget,
)
from PyQt6.QtGui import QAction

try:
    from translations import TRANSLATIONS, get_language
except Exception:  # pragma: no cover
    TRANSLATIONS = {"ro": {}}
    def get_language():
        return "ro"

SOURCE_LANG = "ro"
# Cache editabil per-utilizator (completat la rulare).
_DIR = os.path.join(os.path.expanduser("~"), "Cantio", "i18n")
# Pachete de limbă LIVRATE cu aplicația (langpacks/<lang>.json) — oferă traduceri
# OFFLINE gata de folosit la instalare, fără internet. Căutăm în mai multe locuri
# (sursă + build împachetat cu PyInstaller).
def _find_bundled_dir() -> str:
    cands = []
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        cands.append(os.path.join(exe_dir, "langpacks"))
        cands.append(os.path.join(exe_dir, "_internal", "langpacks"))
        mei = getattr(sys, "_MEIPASS", None)
        if mei:
            cands.append(os.path.join(mei, "langpacks"))
    cands.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "langpacks"))
    cands.append(os.path.join(os.getcwd(), "langpacks"))
    for c in cands:
        if os.path.isdir(c):
            return c
    return cands[-1]

_BUNDLED_DIR = _find_bundled_dir()
_ENDPOINT = "https://translate.googleapis.com/translate_a/single"

_tm: dict = {}            # lang -> {src: translated}
_lock = threading.Lock()


# ── Reguli: ce merită tradus (sarim peste date dinamice) ─────────────────────
_RATIO_RE = re.compile(r"\d+\s*[/:]\s*\d+")
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{3,8}$")

def _should_translate(s: str) -> bool:
    if not s or not s.strip():
        return False
    if len(s) > 240:
        return False
    t = s.strip()
    if _HEX_RE.match(t):
        return False                       # culori #ffffff
    if sum(1 for c in s if c.isalpha()) < 2:
        return False                       # doar cifre/simboluri/emoji
    if _RATIO_RE.search(s):
        return False                       # "3/10", "12:30" etc.
    if "\\" in s or s.startswith("http") or s.startswith("~/"):
        return False                       # căi / URL-uri
    if "{" in s and "}" in s:
        return False                       # format strings / CSS / JSON
    if t.startswith("#") and " " not in t:
        return False                       # #tag fără spațiu
    return True


# ── Memorie de traducere (cache pe disc + seed din translations.py) ──────────
def _cache_file(lang: str) -> str:
    return os.path.join(_DIR, f"{lang}.json")

def _load_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
    except Exception:
        pass
    return {}

def _ensure(lang: str):
    if lang in _tm:
        return
    tm = {}
    # 1) pachet livrat cu aplicatia (OFFLINE, la instalare)
    tm.update(_load_json(os.path.join(_BUNDLED_DIR, f"{lang}.json")))
    # 2) cache-ul utilizatorului (completat la rulare) suprascrie pachetul livrat
    tm.update(_load_json(_cache_file(lang)))
    # 3) Seed din traducerile ingrijite (au prioritate -> suprascriu cache-ul masina)
    try:
        ro = TRANSLATIONS.get("ro", {})
        tgt = TRANSLATIONS.get(lang, {})
        for key, ro_val in ro.items():
            tv = tgt.get(key)
            if ro_val and tv and tv != ro_val:
                tm[str(ro_val)] = str(tv)
    except Exception:
        pass
    _tm[lang] = tm

def _save(lang: str):
    try:
        os.makedirs(_DIR, exist_ok=True)
        with open(_cache_file(lang), "w", encoding="utf-8") as f:
            json.dump(_tm.get(lang, {}), f, ensure_ascii=False, indent=0)
    except Exception:
        pass


def write_active_lang(lang: str = None):
    """Scrie limba activă într-un fișier, ca ferestrele Electron (editor fundal)
    să știe în ce limbă să traducă DOM-ul (display-electron/i18n.js îl citește)."""
    try:
        lang = lang or get_language()
        os.makedirs(_DIR, exist_ok=True)
        with open(os.path.join(_DIR, "_active_lang.txt"), "w", encoding="utf-8") as f:
            f.write(str(lang or "ro"))
    except Exception:
        pass


def translate(text: str, lang: str = None) -> str:
    """Traducere sincronă din cache; dacă lipsește, întoarce textul românesc."""
    if text is None:
        return text
    lang = lang or get_language()
    if lang == SOURCE_LANG:
        return text
    _ensure(lang)
    return _tm[lang].get(text, _tm[lang].get(text.strip(), text))


# Alias scurt pentru texte dinamice din cod (toasturi, mesaje).
def T(text: str) -> str:
    return translate(text)


# ── Traducere online (Google, fără cheie) ────────────────────────────────────
def _online(lines: list, tl: str):
    """Traduce o listă de linii; întoarce listă de aceeași lungime sau None."""
    q = "\n".join(lines)
    url = _ENDPOINT + "?" + urllib.parse.urlencode(
        {"client": "gtx", "sl": SOURCE_LANG, "tl": tl, "dt": "t", "q": q})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))
    full = "".join(seg[0] for seg in data[0] if seg and seg[0])
    out = full.split("\n")
    return out if len(out) == len(lines) else None


def fill_missing_async(texts, lang: str, on_done=None):
    """Completează online traducerile lipsă (pe un fir separat), apoi salvează
    cache-ul și cheamă on_done(changed: bool). Nicio excepție nu iese afară."""
    def work():
        try:
            _ensure(lang)
            seen = []
            for t in texts:
                if (t and t not in seen and _should_translate(t)
                        and t not in _tm[lang]):
                    seen.append(t)
            if not seen:
                if on_done:
                    on_done(False)
                return
            changed = False
            batch = [m for m in seen if "\n" not in m]
            singles = [m for m in seen if "\n" in m]
            CHUNK = 40
            for i in range(0, len(batch), CHUNK):
                chunk = batch[i:i + CHUNK]
                try:
                    res = _online(chunk, lang)
                except Exception:
                    res = None
                if res and len(res) == len(chunk):
                    with _lock:
                        for src, tr in zip(chunk, res):
                            _tm[lang][src] = (tr.strip() or src)
                    changed = True
                else:
                    # Batch-ul a eșuat (Google a schimbat numărul de linii) —
                    # traducem fiecare șir SEPARAT ca să nu pierdem tot chunk-ul
                    # și să evităm alinierea greșită (traducere pusă la altă cheie).
                    for m in chunk:
                        try:
                            r1 = _online([m], lang)
                        except Exception:
                            r1 = None
                        if r1:
                            with _lock:
                                _tm[lang][m] = (r1[0].strip() or m)
                            changed = True
            for m in singles:
                try:
                    res = _online([m], lang)
                    if res:
                        with _lock:
                            _tm[lang][m] = res[0] or m
                        changed = True
                except Exception:
                    pass
            if changed:
                _save(lang)
            if on_done:
                on_done(changed)
        except Exception:
            if on_done:
                on_done(False)
    threading.Thread(target=work, daemon=True).start()


# ── Parcurgerea arborelui de widget-uri ──────────────────────────────────────
def _apply(obj, key: str, getter, setter, collect: list):
    """Memorează textul-sursă (o dată), apoi setează traducerea lui."""
    prop = "_i18n_" + key
    stored = obj.property(prop)
    if isinstance(stored, str) and stored:
        src = stored
    else:
        src = getter() or ""
        if not src:
            return
        obj.setProperty(prop, src)
    collect.append(src)
    try:
        setter(translate(src))
    except Exception:
        pass


def _translate_one(w, collect):
    # Tooltip pentru orice widget
    try:
        if w.toolTip():
            _apply(w, "tip", w.toolTip, w.setToolTip, collect)
    except Exception:
        pass
    if isinstance(w, QLabel):
        _apply(w, "text", w.text, w.setText, collect)
    elif isinstance(w, QAbstractButton):
        _apply(w, "text", w.text, w.setText, collect)
    elif isinstance(w, QGroupBox):
        _apply(w, "title", w.title, w.setTitle, collect)
    elif isinstance(w, (QLineEdit, QTextEdit, QPlainTextEdit)):
        try:
            if w.placeholderText():
                _apply(w, "ph", w.placeholderText, w.setPlaceholderText, collect)
        except Exception:
            pass
    elif isinstance(w, QTabWidget):
        for i in range(w.count()):
            _apply_indexed(w, f"tab{i}",
                           lambda i=i: w.tabText(i),
                           lambda v, i=i: w.setTabText(i, v), collect)


def _apply_indexed(obj, key, getter, setter, collect):
    prop = "_i18n_" + key
    stored = obj.property(prop)
    if isinstance(stored, str) and stored:
        src = stored
    else:
        src = getter() or ""
        if not src:
            return
        obj.setProperty(prop, src)
    collect.append(src)
    try:
        setter(translate(src))
    except Exception:
        pass


def retranslate_tree(root) -> list:
    """Traduce tot arborele `root` în limba activă. Întoarce lista textelor-sursă
    întâlnite (ca să poată fi completate online cele lipsă)."""
    collect = []
    if root is None:
        return collect
    # Titlul ferestrei
    try:
        if root.windowTitle():
            _apply(root, "wtitle", root.windowTitle, root.setWindowTitle, collect)
    except Exception:
        pass
    # Widget-uri
    try:
        widgets = root.findChildren(QWidget)
    except Exception:
        widgets = []
    for w in widgets:
        try:
            _translate_one(w, collect)
        except Exception:
            pass
    # Acțiuni (meniuri)
    try:
        actions = root.findChildren(QAction)
    except Exception:
        actions = []
    for a in actions:
        try:
            if a.text():
                _apply(a, "text", a.text, a.setText, collect)
            if a.toolTip() and a.toolTip() != a.text():
                _apply(a, "tip", a.toolTip, a.setToolTip, collect)
        except Exception:
            pass
    return collect
