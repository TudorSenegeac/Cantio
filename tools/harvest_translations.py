# -*- coding: utf-8 -*-
"""
Harvest + pre-translate — generează pachetele de limbă OFFLINE pentru Cantio.
=============================================================================
Scanează fișierele .py după textele de interfață (string-uri pasate la setText,
QLabel(...), QPushButton(...), setWindowTitle, setToolTip, addTab, QMessageBox
etc.), le traduce în limbile țintă (Google, fără cheie) și scrie
langpacks/<lang>.json — care se livrează cu aplicația, deci limbile apar gata
traduse OFFLINE la instalare.

Rulează din rădăcina repo-ului:
    python tools/harvest_translations.py en de fr hu
(fără argumente -> en de fr hu).

Re-rulabil: păstrează traducerile existente din langpacks și completează doar ce
lipsește (textele noi apărute în cod).
"""

import ast
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import i18n  # noqa: E402  (folosim _online + _should_translate + _load_json)

LANGPACKS = os.path.join(ROOT, "langpacks")

# Apeluri UI ale căror argumente-string sunt text de interfață.
_UI_CALLS = {
    "setText", "setToolTip", "setWindowTitle", "setPlaceholderText", "setTitle",
    "setStatusTip", "setWhatsThis", "addTab", "insertTab", "setTabText",
    "showMessage", "information", "warning", "critical", "question", "about",
    "setLabelText",
    # wrappere custom din Cantio (primul arg = text)
    "_act", "_fmt_btn", "_accent_btn", "_section_lbl", "addAction",
}
_UI_CTORS = {
    "QLabel", "QPushButton", "QCheckBox", "QRadioButton", "QGroupBox",
    "QAction", "QToolButton", "QMenu", "QCommandLinkButton",
}
_UI_KW = {"text", "title", "toolTip", "placeholderText", "label"}


def _call_name(node: ast.Call) -> str:
    f = node.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return ""


def harvest_file(path: str, out: set):
    try:
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=path)
    except Exception:
        return
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        take_positional = (name in _UI_CALLS) or (name in _UI_CTORS)
        if take_positional:
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    out.add(arg.value)
        for kw in node.keywords:
            if kw.arg in _UI_KW and isinstance(kw.value, ast.Constant) \
                    and isinstance(kw.value.value, str):
                out.add(kw.value.value)


def harvest_all() -> list:
    strings = set()
    # 1) textele din cod
    for dirpath, dirs, files in os.walk(ROOT):
        if any(skip in dirpath for skip in (os.sep + ".git", os.sep + "langpacks",
                                            os.sep + "node_modules", os.sep + "build",
                                            os.sep + "dist")):
            continue
        for fn in files:
            if fn.endswith(".py"):
                harvest_file(os.path.join(dirpath, fn), strings)
    # 2) toate valorile romanesti din translations.py
    try:
        from translations import TRANSLATIONS
        for v in TRANSLATIONS.get("ro", {}).values():
            if isinstance(v, str):
                strings.add(v)
    except Exception:
        pass
    # filtrare: doar ce merită tradus
    kept = [s for s in strings if i18n._should_translate(s)]
    kept.sort()
    return kept


def build_lang(lang: str, strings: list):
    out_path = os.path.join(LANGPACKS, f"{lang}.json")
    existing = i18n._load_json(out_path)
    missing = [s for s in strings if s not in existing and "\n" not in s]
    singles = [s for s in strings if s not in existing and "\n" in s]
    print(f"[{lang}] total={len(strings)}  existente={len(existing)}  de_tradus={len(missing)+len(singles)}")
    CHUNK = 40
    done = 0
    for i in range(0, len(missing), CHUNK):
        chunk = missing[i:i + CHUNK]
        res = None
        for attempt in range(3):
            try:
                res = i18n._online(chunk, lang)
                if res:
                    break
            except Exception:
                pass
            time.sleep(1.5)
        if res:
            for src, tr in zip(chunk, res):
                existing[src] = (tr.strip() or src)
            done += len(chunk)
            print(f"[{lang}] {done}/{len(missing)}")
        else:
            print(f"[{lang}] chunk esuat la {i} — sar peste")
        time.sleep(0.3)
    for s in singles:
        try:
            r = i18n._online([s], lang)
            if r:
                existing[s] = r[0] or s
        except Exception:
            pass
    os.makedirs(LANGPACKS, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(existing.items())), f, ensure_ascii=False, indent=0)
    print(f"[{lang}] scris {out_path} ({len(existing)} intrări)")


def main():
    langs = sys.argv[1:] or ["en", "de", "fr", "hu"]
    strings = harvest_all()
    print(f"Texte UI adunate: {len(strings)}")
    for lang in langs:
        build_lang(lang, strings)
    print("GATA.")


if __name__ == "__main__":
    main()
