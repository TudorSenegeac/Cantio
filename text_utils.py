"""
Cantio - Text Utilities
Word-wrap helper and sacred-word auto-capitalization.
"""
import re
from PyQt6.QtGui import QFont, QFontMetrics

DEFAULT_SACRED_WORDS = [
    "Jesus", "Isus", "Iisus", "God", "Dumnezeu", "Hristos", "Christ",
    "Domnul", "Holy Spirit", "Duhul Sfânt", "Emanuel", "Tatăl", "Fiul",
    "Mesia", "Aleluia", "Amin",
]


def apply_sacred_caps(text: str, words: list[str], allcaps: bool = False) -> str:
    """Replace occurrences of sacred words (case-insensitive) with their canonical form."""
    for word in words:
        if not word.strip():
            continue
        replacement = word.upper() if allcaps else word
        pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
        text = pattern.sub(replacement, text)
    return text


def _wrap_line(line: str, fm: QFontMetrics, max_width: int) -> list[str]:
    """Word-wrap a single line so each piece fits within max_width."""
    if fm.horizontalAdvance(line) <= max_width:
        return [line]
    words = line.split()
    if not words:
        return [line]
    result = []
    current = ""
    for word in words:
        test = (current + " " + word).strip() if current else word
        if fm.horizontalAdvance(test) <= max_width:
            current = test
        else:
            if current:
                result.append(current)
            # If a single word is wider than max_width, still append it (no infinite loop)
            current = word
    if current:
        result.append(current)
    return result if result else [line]


def wrap_text_to_fit(
    text: str,
    font_family: str,
    font_size: int,
    font_bold: bool,
    font_italic: bool,
    line_spacing: float,
    max_width: int,
    max_height: int,
    min_font_size: int = 16,
) -> tuple[list[str], int, QFont, QFontMetrics]:
    """
    Word-wrap `text` and shrink font until all lines fit within max_width × max_height.
    Returns (wrapped_lines, final_size, font, fm).
    """
    raw_lines = text.splitlines()

    for size in range(font_size, min_font_size - 1, -1):
        font = QFont(font_family, size)
        font.setBold(font_bold)
        font.setItalic(font_italic)
        fm = QFontMetrics(font)
        line_h = int(fm.height() * line_spacing)

        wrapped = []
        for raw in raw_lines:
            wrapped.extend(_wrap_line(raw, fm, max_width))

        total_h = line_h * len(wrapped)
        max_w = max((fm.horizontalAdvance(ln) for ln in wrapped), default=0)

        if total_h <= max_height and max_w <= max_width:
            return wrapped, size, font, fm

    # Minimum size fallback — wrap at min size
    font = QFont(font_family, min_font_size)
    font.setBold(font_bold)
    font.setItalic(font_italic)
    fm = QFontMetrics(font)
    wrapped = []
    for raw in raw_lines:
        wrapped.extend(_wrap_line(raw, fm, max_width))
    return wrapped, min_font_size, font, fm
