"""
bible_panel.py — backwards-compatibility shim.
The Bible panel logic lives in bible_control_tab.py.
All public symbols are re-exported from there.
"""
from bible_control_tab import *            # noqa: F401, F403
from bible_control_tab import BibleControlTab  # noqa: F401

# Alias so old code that imports BiblePanel still works
BiblePanel = BibleControlTab
