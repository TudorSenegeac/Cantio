"""
Cantio - Lazy Imports
Heavy modules imported only when first used — reduces startup time 3×.

Usage:
    from lazy_imports import get_cv2
    cv2 = get_cv2()          # imported on first call, cached thereafter
"""
from __future__ import annotations

_cv2 = None
_flask = None
_deep_translator = None
_fitz = None
_docx = None
_psutil = None
_reportlab = None


def get_cv2():
    """Return cv2 module, importing it lazily on first call."""
    global _cv2
    if _cv2 is None:
        import os
        # Suppress obsensor/UVC errors that OpenCV logs at import time
        os.environ.setdefault("OPENCV_LOG_LEVEL", "SILENT")
        os.environ.setdefault("OPENCV_VIDEOIO_DEBUG", "0")
        import cv2 as _mod
        try:
            _mod.setLogLevel(0)   # 0 = SILENT
        except Exception:
            pass
        _cv2 = _mod
    return _cv2


def get_flask():
    """Return flask module, importing it lazily on first call."""
    global _flask
    if _flask is None:
        import flask as _mod
        _flask = _mod
    return _flask


def get_translator():
    """Return GoogleTranslator class from deep_translator."""
    global _deep_translator
    if _deep_translator is None:
        from deep_translator import GoogleTranslator
        _deep_translator = GoogleTranslator
    return _deep_translator


def get_fitz():
    """Return PyMuPDF (fitz) module."""
    global _fitz
    if _fitz is None:
        import fitz as _mod
        _fitz = _mod
    return _fitz


def get_docx():
    """Return python-docx module."""
    global _docx
    if _docx is None:
        import docx as _mod
        _docx = _mod
    return _docx


def get_psutil():
    """Return psutil module."""
    global _psutil
    if _psutil is None:
        import psutil as _mod
        _psutil = _mod
    return _psutil


def get_reportlab_canvas():
    """Return reportlab.pdfgen.canvas module."""
    global _reportlab
    if _reportlab is None:
        from reportlab.pdfgen import canvas as _mod
        _reportlab = _mod
    return _reportlab


def cv2_available() -> bool:
    try:
        get_cv2()
        return True
    except ImportError:
        return False


def psutil_available() -> bool:
    try:
        get_psutil()
        return True
    except ImportError:
        return False
