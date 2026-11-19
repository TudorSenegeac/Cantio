# -*- coding: utf-8 -*-
"""
Cantio — branding „CantioPresenter" stilizat ca pe splash:
  „Cantio"   → Poppins (bold)
  „Presenter" → Kaushan Script
Oferă încărcarea fonturilor (idempotentă) + HTML gata de pus într-un QLabel.
"""
from __future__ import annotations
import os
import sys

_LOADED = False
_POPPINS = "Poppins"
_KAUSHAN = "Kaushan Script"


def _fonts_dir() -> str:
    # dev: lângă acest fișier; frozen: lângă exe / _internal.
    cands = []
    base = os.path.dirname(os.path.abspath(__file__))
    cands.append(os.path.join(base, "assets", "fonts"))
    if getattr(sys, "frozen", False):
        exe = os.path.dirname(sys.executable)
        cands.append(os.path.join(exe, "assets", "fonts"))
        cands.append(os.path.join(exe, "_internal", "assets", "fonts"))
        mei = getattr(sys, "_MEIPASS", None)
        if mei:
            cands.append(os.path.join(mei, "assets", "fonts"))
    for c in cands:
        if os.path.isdir(c):
            return c
    return cands[0]


def load_brand_fonts() -> None:
    """Încarcă Poppins Bold + Kaushan Script în QFontDatabase (o singură dată)."""
    global _LOADED
    if _LOADED:
        return
    try:
        from PyQt6.QtGui import QFontDatabase
        d = _fonts_dir()
        for fn in ("Poppins-Bold.ttf", "KaushanScript-Regular.ttf"):
            p = os.path.join(d, fn)
            if os.path.exists(p):
                QFontDatabase.addApplicationFont(p)
        _LOADED = True
    except Exception:
        pass


def brand_html(cantio_px: int = 20, presenter_px: int = 0,
               color: str = "#cdd6f4", color2: str = "") -> str:
    """HTML cu „Cantio" (Poppins bold) + „Presenter" (Kaushan Script).
    presenter_px=0 → derivat din cantio_px. color2 → culoare separată pt. „Presenter"."""
    load_brand_fonts()
    if presenter_px <= 0:
        presenter_px = int(cantio_px * 1.05)
    c2 = color2 or color
    return (
        f'<span style="font-family:\'{_POPPINS}\'; font-weight:700; '
        f'font-size:{cantio_px}px; color:{color};">Cantio</span>'
        f'<span style="font-family:\'{_KAUSHAN}\'; '
        f'font-size:{presenter_px}px; color:{c2};">Presenter</span>'
    )
