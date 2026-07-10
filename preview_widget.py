"""
Cantio - Preview Widget
Live miniature preview of the display output.

Rendering pipeline (priority order):
1. frozen pixmap  — after freeze() is called, canvas is locked
2. engine push    — RenderEngine.preview_ready → update_preview(pixmap)
3. internal       — _draw_frame() mirrors display.js drawFrame() exactly
"""
from __future__ import annotations

import os
from translations import t
from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtCore import Qt, QSize, QRect, QPointF, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QFont, QColor, QPen, QPixmap, QBrush,
    QLinearGradient, QRadialGradient, QPainterPath, QFontMetrics,
)


# ─────────────────────────────────────────────────────────────────────────────
#  Smart word-wrap helper
# ─────────────────────────────────────────────────────────────────────────────

def smart_word_wrap(text_line: str, max_width: int, fm: "QFontMetrics",
                    min_words: int = 2) -> list[str]:
    """
    Balanced word-wrap:
    1. Never leaves a single word alone on a line.
    2. Treats hyphenated words (e.g. "de-al") as atomic tokens — never breaks mid-hyphen.
    3. Prefers splitting at punctuation (,  ;  :).
    4. Otherwise minimises line-width difference between the two halves.
    """
    import re
    if not text_line or not text_line.strip():
        return [text_line or '']

    # Tokenise — each run of non-whitespace (including hyphens) is ONE token.
    tokens = re.findall(r'\S+', text_line)
    if not tokens:
        return [text_line]
    if len(tokens) == 1:
        return [text_line]

    full = ' '.join(tokens)
    if fm.horizontalAdvance(full) <= max_width:
        return [full]

    best_split = None
    best_score = float('inf')

    for i in range(1, len(tokens)):
        line1 = ' '.join(tokens[:i])
        line2 = ' '.join(tokens[i:])
        w1 = fm.horizontalAdvance(line1)

        # Skip if first line overflows
        if w1 > max_width:
            continue

        w2   = fm.horizontalAdvance(line2)
        penalty = 0

        # Penalise single-word lines heavily
        if i == 1:
            penalty += 2000
        if len(tokens) - i == 1:
            penalty += 2000

        # Penalise if second line would still overflow (recursive wrap will handle it,
        # but we prefer cleaner splits)
        if w2 > max_width:
            penalty += 1000

        # Reward splitting after punctuation
        last_tok = tokens[i - 1]
        if last_tok.endswith(','):
            penalty -= 800
        elif last_tok.endswith(';'):
            penalty -= 600
        elif last_tok.endswith(':'):
            penalty -= 400

        # Prefer balanced widths
        score = abs(w1 - w2) + penalty
        if score < best_score:
            best_score = score
            best_split = i

    if best_split is None:
        best_split = max(1, len(tokens) // 2)

    line1 = ' '.join(tokens[:best_split])
    line2 = ' '.join(tokens[best_split:])

    result = [line1]
    if fm.horizontalAdvance(line2) > max_width:
        result.extend(smart_word_wrap(line2, max_width, fm, min_words))
    else:
        result.append(line2)
    return result


# ─────────────────────────────────────────────────────────────────────────────
#  Module-level renderer — shared by PreviewWidget AND SlideThumbnail
# ─────────────────────────────────────────────────────────────────────────────

def render_text_on_painter(
    p: QPainter,
    text: str,
    w: int,
    h: int,
    s: dict,
    scale: float | None = None,
) -> None:
    """
    Draw *text* onto painter *p* at canvas size (w × h) using settings *s*.

    Mirrors display.js ``drawText()`` exactly:
    - word-wrap + auto font-shrink loop until text fits max_w × max_h
    - top / center / bottom vertical alignment
    - left / center / right horizontal alignment
    - text outline (strokePath ≈ canvas strokeText, round-joined)
    - drop shadow at 3 × scale px offset

    Parameters
    ----------
    scale : float or None
        Scaling factor from 1920-px design space to actual canvas pixels.
        Pass ``w / 1920.0`` for the preview widget, ``thumb_w / 1920.0`` for
        thumbnails.  Defaults to ``w / 1920.0`` when *None*.
    """
    if not text or not text.strip():
        return
    if scale is None:
        scale = w / 1920.0

    # ── Settings (same keys as display.js) ───────────────────────────────────
    size_raw  = int(s.get("font_size", 48) or 48)
    bold      = s.get("font_bold",   "true")  in ("true", True)
    italic    = s.get("font_italic", "false") in ("true", True)
    family    = str(s.get("font_family", "Arial") or "Arial")
    color     = QColor(str(s.get("text_color", "#ffffff") or "#ffffff"))
    shadow    = s.get("text_shadow", "true") not in ("false", False)
    out_w_raw = max(0, int(s.get("outline_width", 2) or 0))
    out_c     = QColor(str(s.get("outline_color", "#000000") or "#000000"))
    lsp       = float(s.get("line_spacing", 1.4) or 1.4)
    uppercase = s.get("uppercase", "false") in ("true", True)
    valign    = str(s.get("text_valign", s.get("valign", "center")) or "center")
    align_str = str(s.get("text_align", "center") or "center")

    # Margin: < 2 → fraction of min(w, h);  ≥ 2 → 1920-space pixels → scaled
    raw_margin = float(s.get("margin", 0.06) or 0.06)
    if raw_margin < 2:
        margin = round(min(w, h) * raw_margin)
    else:
        margin = int(raw_margin * scale)

    display_text = text.upper() if uppercase else text
    max_w = w - margin * 2
    max_h = h - margin * 2
    if max_w <= 0 or max_h <= 0:
        return

    # ── Font size: settings store PIXELS (like Canvas 2D font_size) ─────────
    # Scale from 1920-space to canvas pixels, then convert px→pt for QFont.
    # At 96 dpi: 1 px = 0.75 pt  →  size_pt = size_px * 0.75
    current_size_px = max(8, round(size_raw * scale))
    min_size_px     = max(6, round(10 * scale))
    shrink_step_px  = max(1, round(2 * scale))

    lines:   list[str] = []
    line_h:  int       = current_size_px
    total_h: int       = current_size_px

    # ── Shrink-to-fit loop (mirrors display.js while loop) ───────────────────
    while current_size_px >= min_size_px:
        # Use setPixelSize() so QFont renders exactly `current_size_px` pixels tall,
        # matching Canvas 2D font-size pixels in display.js exactly.
        font = QFont(family)
        font.setPixelSize(max(4, int(current_size_px)))
        font.setBold(bold)
        font.setItalic(italic)
        fm = QFontMetrics(font)   # fm.horizontalAdvance() returns pixels ✓

        lines = []
        for raw_line in display_text.split('\n'):
            if not raw_line.strip():
                lines.append('')
                continue
            # Use smart_word_wrap for balanced line lengths
            wrapped = smart_word_wrap(raw_line, max_w, fm)
            # If any single word is wider than max_w, char-split as fallback
            for wl in wrapped:
                if fm.horizontalAdvance(wl) <= max_w:
                    lines.append(wl)
                else:
                    part = ''
                    for ch in wl:
                        if fm.horizontalAdvance(part + ch) > max_w:
                            if part:
                                lines.append(part)
                            part = ch
                        else:
                            part += ch
                    if part:
                        lines.append(part)

        # Line height mirrors display.js: lineH = currentSize * lsp (pixel size)
        line_h  = round(current_size_px * lsp)
        total_h = line_h * len(lines)
        max_line_w = max((fm.horizontalAdvance(ln) for ln in lines if ln), default=0)
        if total_h <= max_h and max_line_w <= max_w:
            break
        current_size_px -= shrink_step_px

    if not lines:
        return

    font = QFont(family)
    font.setPixelSize(max(4, int(current_size_px)))
    font.setBold(bold)
    font.setItalic(italic)
    p.setFont(font)
    fm = QFontMetrics(font)

    # ── Vertical start Y: mirrors display.js currentSize * 0.85 (pixel size) ─
    ascent_off = round(current_size_px * 0.85)
    if valign == 'top':
        start_y = margin + ascent_off
    elif valign == 'bottom':
        start_y = h - margin - total_h + ascent_off
    else:                             # center (default)
        start_y = (h - total_h) // 2 + ascent_off

    # ── Horizontal base X ─────────────────────────────────────────────────────
    if align_str == 'left':
        base_x = margin
    elif align_str == 'right':
        base_x = w - margin
    else:                             # center
        base_x = w // 2

    # Outline width: out_w_raw is in 1920-space pixels → scale to canvas pixels
    out_w_scaled = max(0.5, out_w_raw * 2.0 * scale)

    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # ── Text box background (FreeShow-style) ──────────────────────────────────
    tb = s.get("text_box", {}) if isinstance(s.get("text_box"), dict) else {}
    if s.get("text_box_enabled") is True or s.get("text_box_enabled") == "true" \
            or tb.get("enabled"):
        render_text_box_on_painter(
            p, lines, line_h, start_y, w, h, s, scale, align_str, base_x,
            current_size_px, fm,
        )

    for i, line in enumerate(lines):
        if not line:
            continue
        y   = start_y + i * line_h
        lw  = fm.horizontalAdvance(line)
        if align_str == 'left':
            x = base_x
        elif align_str == 'right':
            x = base_x - lw
        else:
            x = base_x - lw // 2

        # ── Outline (QPainterPath ≈ canvas strokeText, drawn first) ──────────
        if out_w_raw > 0:
            path = QPainterPath()
            path.addText(QPointF(float(x), float(y)), font, line)
            pen = QPen(out_c, out_w_scaled)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.strokePath(path, pen)

        # ── Shadow ────────────────────────────────────────────────────────────
        if shadow:
            shadow_off = max(1, round(3 * scale))
            p.setPen(QColor(0, 0, 0, 217))   # rgba(0,0,0,0.85)
            p.drawText(x + shadow_off, y + shadow_off, line)

        # ── Main fill ─────────────────────────────────────────────────────────
        p.setPen(color)
        p.drawText(x, y, line)

    p.restore()


def render_text_box_on_painter(
    p: QPainter,
    lines: list,
    line_h: int,
    start_y: int,
    w: int,
    h: int,
    s: dict,
    scale: float,
    align_str: str,
    base_x: int,
    cur_size_px: int,
    fm: QFontMetrics,
) -> None:
    """Draw the text-box background behind each line (multiple styles)."""
    tb = s.get("text_box") if isinstance(s.get("text_box"), dict) else {}
    box_color  = QColor(str(tb.get("color", s.get("text_box_color", "#000000")) or "#000000"))
    box_color2 = QColor(str(tb.get("color2", s.get("text_box_color2", "#1a1a1a")) or "#1a1a1a"))
    opacity    = float(tb.get("opacity", s.get("text_box_opacity", 0.6)) or 0.6)
    pad_h      = int(tb.get("padding_h", s.get("text_box_padding_h", 20)) or 20)
    pad_v      = int(tb.get("padding_v", s.get("text_box_padding_v", 12)) or 12)
    radius     = int(tb.get("radius", s.get("text_box_radius", 8)) or 8)
    fit        = str(tb.get("fit", s.get("text_box_fit", "per_line")) or "per_line")
    style      = str(tb.get("style", s.get("text_box_style", "solid")) or "solid")
    ascent = round(cur_size_px * 0.85)

    def paint(x, y, bw, bh, r):
        _paint_box_rect_pw(p, x, y, bw, bh, r, style, box_color, box_color2, opacity)

    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    if fit == 'full_block':
        max_lw = max((fm.horizontalAdvance(ln) for ln in lines if ln), default=0)
        bx = (base_x - pad_h if align_str == 'left'
              else base_x - max_lw - pad_h if align_str == 'right'
              else base_x - max_lw // 2 - pad_h)
        by = start_y - ascent - pad_v
        paint(bx, by, max_lw + pad_h * 2, line_h * len(lines) + pad_v * 2, radius)
    elif fit == 'full_width':
        for i, line in enumerate(lines):
            if not line:
                continue
            by = start_y + i * line_h - ascent - pad_v
            paint(0, by, w, cur_size_px + pad_v * 2, 0)
    else:  # per_line
        for i, line in enumerate(lines):
            if not line:
                continue
            lw = fm.horizontalAdvance(line)
            bx = (base_x - pad_h if align_str == 'left'
                  else base_x - lw - pad_h if align_str == 'right'
                  else base_x - lw // 2 - pad_h)
            by = start_y + i * line_h - ascent - pad_v
            paint(bx, by, lw + pad_h * 2, cur_size_px + pad_v * 2, radius)
    p.restore()


def _paint_box_rect_pw(p, x, y, w, h, radius, style, color, color2, opacity):
    """Paint one text-box rect in the chosen style (operator preview)."""
    from PyQt6.QtCore import QRectF
    p.save()
    p.setOpacity(opacity)
    rect = QRectF(float(x), float(y), float(w), float(h))
    if style == "gradient":
        g = QLinearGradient(x, y, x, y + h)
        g.setColorAt(0, color); g.setColorAt(1, color2)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g))
        p.drawRoundedRect(rect, radius, radius)
    elif style == "outline":
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(color, max(2.0, h * 0.045)))
        p.drawRoundedRect(rect, radius, radius)
    elif style == "frosted":
        p.setOpacity(opacity * 0.5)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(color))
        p.drawRoundedRect(rect, radius, radius)
        p.setOpacity(opacity * 0.9)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 90), max(1.0, h * 0.02)))
        p.drawRoundedRect(rect, radius, radius)
    elif style == "shadow":
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor(0, 0, 0, 140)))
        p.drawRoundedRect(QRectF(float(x), float(y + h * 0.06), float(w), float(h)), radius, radius)
        p.setBrush(QBrush(color)); p.drawRoundedRect(rect, radius, radius)
    elif style == "underline":
        bh = max(3.0, h * 0.10)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(color))
        p.drawRoundedRect(QRectF(float(x), float(y + h - bh), float(w), float(bh)), bh / 2, bh / 2)
    elif style == "sketch":
        p.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(color, max(2.0, h * 0.04)); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen); p.drawRoundedRect(rect, radius, radius)
        p.setOpacity(opacity * 0.6)
        p.drawRoundedRect(QRectF(float(x + 2.5), float(y - 2), float(w), float(h)),
                          radius + 3, radius + 3)
    else:  # solid
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(color))
        p.drawRoundedRect(rect, radius, radius)
    p.restore()


def _blit_video_frame(p: QPainter, frame, w: int, h: int,
                      opacity: float = 1.0) -> bool:
    """Draw a downscaled RGB numpy frame as a cover-scaled background.
    Returns True on success."""
    try:
        from PyQt6.QtGui import QImage
        fh, fw = frame.shape[:2]
        img = QImage(frame.data, fw, fh, fw * 3, QImage.Format.Format_RGB888)
        pm  = QPixmap.fromImage(img).scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        ox = (w - pm.width())  // 2
        oy = (h - pm.height()) // 2
        p.setOpacity(max(0.0, min(1.0, opacity)))
        p.drawPixmap(ox, oy, pm)
        p.setOpacity(1.0)
        return True
    except Exception:
        return False


def render_animated_gradient_on_painter(p: QPainter, w: int, h: int,
                                        colors: list, phase: float) -> None:
    """Animated multi-radial gradient — mirrors display.js renderAnimatedGradient.
    `phase` is accumulated time (seconds × speed)."""
    import math
    from PyQt6.QtGui import QPainter as _QP
    if not colors:
        colors = ['#1a237e', '#6a1b9a', '#0d47a1']
    p.fillRect(0, 0, w, h, QColor("#000000"))
    p.save()
    p.setCompositionMode(_QP.CompositionMode.CompositionMode_Screen)
    n = max(1, len(colors))
    for idx, col in enumerate(colors):
        ph = phase + idx * (math.pi * 2 / n)
        cx = w * (0.3 + 0.4 * math.sin(ph * 0.7))
        cy = h * (0.3 + 0.4 * math.cos(ph * 0.5))
        radius = max(w, h) * (0.4 + 0.2 * math.sin(ph * 1.3))
        grad = QRadialGradient(cx, cy, max(1.0, radius))
        c0 = QColor(str(col))
        c1 = QColor(str(col)); c1.setAlpha(0)
        grad.setColorAt(0, c0)
        grad.setColorAt(1, c1)
        p.fillRect(0, 0, w, h, QBrush(grad))
    p.restore()


def render_background_on_painter(
    p: QPainter,
    w: int,
    h: int,
    s: dict,
    bg_pixmap: "QPixmap | None" = None,
    video_frame=None,
    anim_phase: "float | None" = None,
) -> None:
    """
    Draw the background onto painter *p* at canvas size (w × h) using settings *s*.
    Handles: color, gradient, animated_gradient, transparent, image, video.
    Exported at module level so ThemeCanvas and SlideThumbnail can reuse it.
    """
    bg_type  = str(s.get("bg_type", "color") or "color")
    bg_color = QColor(str(s.get("bg_color", "#000000") or "#000000"))

    # Always start with solid base
    p.fillRect(0, 0, w, h, bg_color)

    if bg_type == "gradient":
        c1   = QColor(str(s.get("bg_grad_c1", s.get("bg_color", "#000033"))))
        c2   = QColor(str(s.get("bg_grad_c2", "#000000")))
        dir_ = str(s.get("bg_grad_dir", "Sus→Jos") or "Sus→Jos")
        if "Radial" in dir_:
            grad: "QLinearGradient | QRadialGradient" = QRadialGradient(w / 2, h / 2, max(w, h) / 2)
        elif "Stânga" in dir_ or "Dreapta" in dir_:
            grad = QLinearGradient(0, 0, w, 0)
            if "Dreapta" in dir_:
                c1, c2 = c2, c1
        elif "Diagonal" in dir_:
            grad = QLinearGradient(0, 0, w, h)
        else:
            grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, c1)
        grad.setColorAt(1, c2)
        p.fillRect(0, 0, w, h, QBrush(grad))
        return

    if bg_type == "animated_gradient":
        # key sent by control_window is `anim_grad_colors`; fall back to legacy
        colors_raw = s.get("anim_grad_colors",
                     s.get("bg_colors",
                     s.get("anim_colors", ["#000033", "#0066aa"])))
        if not isinstance(colors_raw, list) or len(colors_raw) < 2:
            colors_raw = ["#000033", "#0066aa"]
        if anim_phase is not None:
            # Live animated rendering (moving radials, like the projector)
            speed = float(s.get("anim_grad_speed", 0.5) or 0.5)
            render_animated_gradient_on_painter(
                p, w, h, colors_raw, anim_phase * speed)
        else:
            # Static snapshot (thumbnails / theme cards)
            grad_a = QLinearGradient(0, 0, w, h)
            for idx, c in enumerate(colors_raw):
                pos = idx / max(1, len(colors_raw) - 1)
                grad_a.setColorAt(pos, QColor(str(c)))
            p.fillRect(0, 0, w, h, QBrush(grad_a))
        return

    if bg_type == "transparent":
        cs = max(6, min(w, h) // 30)
        for row in range(0, h, cs):
            for col in range(0, w, cs):
                light = (row // cs + col // cs) % 2 == 0
                p.fillRect(col, row, cs, cs,
                           QColor("#888888" if light else "#666666"))
        return

    # Camera (live frame from the background feed thread when available).
    # For camera_gradient also paint the tinted gradient overlay so it matches
    # what the projector shows on top of the camera feed.
    if bg_type in ("camera", "camera_gradient"):
        has_frame = video_frame is not None and _blit_video_frame(
            p, video_frame, w, h, float(s.get("bg_opacity", 1.0) or 1.0))
        if not has_frame:
            p.fillRect(0, 0, w, h, QColor("#0c0c12"))
        if bg_type == "camera_gradient":
            gc  = QColor(str(s.get("bg_grad_c1", "#000033")))
            op  = float(s.get("bg_grad_opacity", 0.5) or 0.5)
            dir_ = str(s.get("bg_grad_dir", "Radial") or "Radial")
            if "Stânga" in dir_ or "Dreapta" in dir_:
                grad_c = QLinearGradient(0, 0, w, 0)
            elif "Sus" in dir_ or "Jos" in dir_:
                grad_c = QLinearGradient(0, 0, 0, h)
            else:
                grad_c = QRadialGradient(w / 2, h / 2, max(w, h) / 2)
            c0 = QColor(gc); c0.setAlphaF(max(0.0, min(1.0, op)))
            c1 = QColor(gc); c1.setAlpha(0)
            grad_c.setColorAt(0, c0)
            grad_c.setColorAt(1, c1)
            p.fillRect(0, 0, w, h, QBrush(grad_c))
        if not has_frame:
            p.setPen(QColor("#6c7086"))
            _f = QFont("Arial")
            _f.setPixelSize(max(8, int(min(w, h) * 0.09)))
            p.setFont(_f)
            p.drawText(QRect(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "📷")
        return

    # Image / video
    bg_path = str(s.get("bg_image", "") or "")

    # Live video frame from the feed thread → cover-scale it
    if video_frame is not None:
        if _blit_video_frame(p, video_frame, w, h,
                             float(s.get("bg_opacity", 1.0) or 1.0)):
            return

    if bg_path and os.path.exists(bg_path):
        ext = bg_path.rsplit(".", 1)[-1].lower()
        is_video = ext in {"mp4", "mov", "avi", "mkv", "webm"}
        if is_video:
            # No frame yet (feed still opening) → placeholder
            p.fillRect(0, 0, w, h, QColor("#0d0d1a"))
            p.setPen(QColor("#6c7086"))
            _f = QFont("Arial")
            _f.setPixelSize(max(8, int(min(w, h) * 0.08)))
            p.setFont(_f)
            p.drawText(QRect(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "🎬 Video")
        else:
            pix = QPixmap(bg_path)
            if not pix.isNull():
                op = float(s.get("bg_opacity", 0.85) or 0.85)
                p.setOpacity(op)
                p.drawPixmap(0, 0, pix.scaled(
                    w, h,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                ))
                p.setOpacity(1.0)
        return

    if bg_pixmap and not bg_pixmap.isNull():
        op = float(s.get("bg_opacity", 0.85) or 0.85)
        p.setOpacity(op)
        p.drawPixmap(0, 0, bg_pixmap.scaled(
            w, h,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        ))
        p.setOpacity(1.0)


def _draw_reference_on_painter(
    p:     QPainter,
    ref:   str,
    w:     int,
    h:     int,
    s:     dict,
    scale: float,
) -> None:
    """Mirrors display.js drawReference() — italic ref text bottom-right."""
    if not ref or not ref.strip():
        return
    family      = str(s.get("font_family", "Arial") or "Arial")
    ref_size_px = max(6, round(int(s.get("ref_font_size", 24) or 24) * scale))
    ref_size_pt = max(5, int(ref_size_px * 0.75))
    ref_color   = QColor(str(s.get("ref_color", "#aaaaaa") or "#aaaaaa"))
    raw_margin  = float(s.get("margin", 0.06) or 0.06)
    margin = round(min(w, h) * raw_margin) if raw_margin < 2 else int(raw_margin * scale)

    font = QFont(family, ref_size_pt)
    font.setItalic(True)
    fm = QFontMetrics(font)

    ref_w = fm.horizontalAdvance(ref)
    x = w - margin - ref_w
    y = h - margin

    p.save()
    p.setFont(font)
    # Shadow
    p.setPen(QColor(0, 0, 0, 204))   # rgba(0,0,0,0.8)
    p.drawText(x + 2, y + 2, ref)
    # Text
    p.setPen(ref_color)
    p.drawText(x, y, ref)
    p.restore()


def _draw_copyright_on_painter(
    p:     QPainter,
    s:     dict,
    meta:  dict,
    w:     int,
    h:     int,
    scale: float,
) -> None:
    """
    Render the copyright / watermark overlay as configured in the overlay settings tab.
    `s["copyright"]` is a JSON string with keys: enabled, mode, custom_text,
    position, font_size, color, opacity.
    `meta` is the current song's metadata dict (title/author/category/source).
    """
    import json
    raw = s.get("copyright", "{}")
    try:
        cr = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except Exception:
        return
    if not cr.get("enabled"):
        return

    mode = cr.get("mode", "title_author")
    if mode == "title_author":
        parts = [v for v in [meta.get("title", ""), meta.get("author", "")] if v]
        text  = " — ".join(parts)
    elif mode == "title":
        text = meta.get("title", "")
    elif mode == "author":
        text = meta.get("author", "")
    elif mode == "category":
        text = meta.get("category", "")
    elif mode == "source":
        text = meta.get("source", "")
    elif mode == "custom":
        text = cr.get("custom_text", "")
    else:
        text = ""

    if not text:
        return

    font_size_pt = int(cr.get("font_size", 12))
    color_str    = cr.get("color",   "#ffffff")
    opacity      = float(cr.get("opacity", 0.4))
    position     = cr.get("position", "bottom_right")

    font = QFont("Segoe UI", max(6, round(font_size_pt * scale * 1.5)))
    font.setItalic(True)
    fm = QFontMetrics(font)
    tw = fm.horizontalAdvance(text)
    th = fm.height()
    pad = max(4, round(8 * scale))

    margin = max(4, round(12 * scale))
    if "right" in position:
        x = w - tw - margin
    elif "center" in position:
        x = (w - tw) // 2
    else:
        x = margin
    if "top" in position:
        y = margin
    else:
        y = h - th - margin

    p.save()
    p.setOpacity(opacity)
    p.fillRect(x - pad // 2, y - 2, tw + pad, th + 4, QColor(0, 0, 0, 120))
    p.setFont(font)
    p.setPen(QColor(color_str))
    p.drawText(x, y + fm.ascent(), text)
    p.setOpacity(1.0)
    p.restore()


# ─────────────────────────────────────────────────────────────────────────────
#  Background video / camera feed (decodes off the UI thread)
# ─────────────────────────────────────────────────────────────────────────────

class _VideoFeedThread(QThread):
    """Decodes a video file or camera in a background thread and emits
    downscaled RGB frames, so the operator preview never blocks the UI thread.

    Frames are capped in size and rate to keep CPU usage low.
    """
    frame_ready = pyqtSignal(object)

    def __init__(self, source, is_camera: bool,
                 max_w: int = 480, fps: int = 20, parent=None):
        super().__init__(parent)
        self._source    = source
        self._is_camera = is_camera
        self._max_w     = max(160, int(max_w))
        self._interval  = 1.0 / max(1, fps)
        self._running   = True

    def run(self):
        try:
            import cv2, numpy as np, time
        except Exception:
            return
        cap = None
        try:
            if self._is_camera:
                idx = int(self._source) if str(self._source).isdigit() else 0
                cap = cv2.VideoCapture(idx)
            else:
                cap = cv2.VideoCapture(str(self._source))
            if cap is None or not cap.isOpened():
                return

            while self._running:
                t0 = time.monotonic()
                ok, frame = cap.read()
                if not ok or frame is None:
                    if self._is_camera:
                        break                                   # camera lost
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)         # loop video file
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        break

                fh, fw = frame.shape[:2]
                if fw > self._max_w:
                    nh = max(1, int(fh * self._max_w / fw))
                    frame = cv2.resize(frame, (self._max_w, nh),
                                       interpolation=cv2.INTER_AREA)
                rgb = np.ascontiguousarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                if self._running:
                    self.frame_ready.emit(rgb)

                sleep = self._interval - (time.monotonic() - t0)
                if sleep > 0:
                    time.sleep(sleep)
        except Exception:
            pass
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass

    def request_stop(self):
        """Ask the thread to finish — returns immediately (non-blocking)."""
        self._running = False

    def stop(self):
        """Stop and block until the thread exits (use only off the hot path)."""
        self._running = False
        self.wait(1500)


# ─────────────────────────────────────────────────────────────────────────────
#  PreviewWidget
# ─────────────────────────────────────────────────────────────────────────────

class PreviewWidget(QWidget):
    """
    Live preview miniature.  Rendering priority:

    1. ``freeze()`` was called → show ``_frozen_pixmap`` (true visual freeze)
    2. RenderEngine pushed a pixmap via ``update_preview()``
    3. Internal ``_draw_frame()`` that mirrors display.js drawFrame()
    """

    ASPECT = 16 / 9

    def __init__(self, parent=None):
        super().__init__(parent)
        self._aspect = self.ASPECT
        self.setMinimumSize(240, 135)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # RenderEngine push-mode pixmap
        self._engine_pixmap: QPixmap | None = None

        # Freeze state
        self._frozen         = False
        self._frozen_pixmap: QPixmap | None = None

        # Settings / text for internal renderer (kept in sync with LiveState)
        self._settings_ref: dict = {}
        self._current_text: str  = ''
        self._current_ref:  str  = ''
        self._bg_pixmap:    QPixmap | None = None

        # Target display resolution (updated from actual screen size)
        self._target_w: int = 1920
        self._target_h: int = 1080

        # ── Animated-gradient ticker (drives continuous repaint) ──────────────
        self._anim_phase: float = 0.0
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(33)          # ~30 fps
        self._anim_timer.timeout.connect(self._on_anim_tick)

        # ── Async video / camera feed (decoded on a background thread) ────────
        self._video_frame = None
        self._feed: "_VideoFeedThread | None" = None
        self._feed_source: str | None = None
        self._retiring: list = []          # feeds shutting down (kept alive til done)
        try:
            from PyQt6.QtWidgets import QApplication
            _app = QApplication.instance()
            if _app is not None:
                _app.aboutToQuit.connect(self._shutdown_feeds)
        except Exception:
            pass

        # Subscribe to LiveState for fallback rendering
        from live_state import get_state
        get_state().add_observer(self._on_state_changed)

    # ── Async video / camera feed management ──────────────────────────────────

    def _feed_key(self, s: dict) -> str | None:
        bt = str(s.get("bg_type", "") or "")
        if bt in ("video", "camera", "camera_gradient"):
            return f"{bt}:{s.get('bg_image', '')}"
        return None

    def _sync_video_feed(self, s: dict) -> None:
        """Start/stop the background decode thread when the source changes."""
        key = self._feed_key(s)
        if key == self._feed_source:
            return
        self._stop_feed()
        self._feed_source = key
        self._video_frame = None
        if not key:
            return
        bt     = str(s.get("bg_type", "") or "")
        src    = s.get("bg_image", "")
        is_cam = bt in ("camera", "camera_gradient")
        if not is_cam and not (src and os.path.exists(str(src))):
            return                                   # video file missing
        try:
            self._feed = _VideoFeedThread(
                src, is_cam, max_w=max(320, (self.width() or 320)))
            self._feed.frame_ready.connect(self._on_video_frame)
            self._feed.start()
        except Exception:
            self._feed = None

    def _on_video_frame(self, frame) -> None:
        self._video_frame = frame
        if self._engine_pixmap is None:          # internal renderer is active
            self.update()

    # ── Animated gradient ticker ──────────────────────────────────────────────

    def _sync_anim_timer(self, s: dict) -> None:
        is_anim = str(s.get("bg_type", "") or "") == "animated_gradient"
        if is_anim and self._engine_pixmap is None:
            if not self._anim_timer.isActive():
                self._anim_timer.start()
        elif self._anim_timer.isActive():
            self._anim_timer.stop()

    def _on_anim_tick(self) -> None:
        self._anim_phase += 0.033
        if self._engine_pixmap is None and not self._frozen:
            self.update()

    def _stop_feed(self) -> None:
        """Signal the active feed to stop WITHOUT blocking the UI thread.
        The thread finishes on its own; we keep a reference until then so it
        isn't garbage-collected mid-run (which would crash)."""
        f = self._feed
        self._feed = None
        if f is None:
            return
        try:
            f.frame_ready.disconnect(self._on_video_frame)
        except Exception:
            pass
        f.request_stop()                     # non-blocking
        self._retiring.append(f)
        def _cleanup(_f=f):
            if _f in self._retiring:
                self._retiring.remove(_f)
        f.finished.connect(_cleanup)

    def _shutdown_feeds(self) -> None:
        """Called on app quit — stop everything and wait briefly (safe to block)."""
        self._stop_feed()
        for f in list(self._retiring):
            try:
                f.request_stop()
                f.wait(800)
            except Exception:
                pass
        self._retiring.clear()

    # ── RenderEngine push-mode API ────────────────────────────────────────────

    def update_preview(self, pixmap: QPixmap) -> None:
        """Slot — called by RenderEngine.preview_ready(pixmap)."""
        self._engine_pixmap = pixmap
        self.update()  # always update — even while frozen (operator sees live feed)

    def detach_engine(self) -> None:
        """Revert to internal renderer (e.g. if RenderEngine is stopped)."""
        self._engine_pixmap = None
        self.update()

    # ── Freeze API ────────────────────────────────────────────────────────────

    def freeze(self) -> None:
        """
        Show freeze indicator (orange border).
        The preview continues to update live so the operator can navigate ahead.
        """
        self._frozen = True
        self.update()

    def unfreeze(self) -> None:
        """Resume live rendering."""
        self._frozen        = False
        self._frozen_pixmap = None
        self.update()

    def is_frozen(self) -> bool:
        return self._frozen

    # ── Live indicator API ────────────────────────────────────────────────────

    def set_live(self, is_live: bool) -> None:
        from live_state import get_state
        state = get_state()
        if is_live != getattr(state, "_preview_is_live_override", None):
            state._preview_is_live_override = is_live
            self.update()

    # ── Backward-compat API ───────────────────────────────────────────────────

    def apply_settings(self, s: dict) -> None:
        """Push settings into LiveState AND load bg_pixmap from path."""
        from live_state import get_state
        state = get_state()
        state.settings = s
        self._settings_ref = s
        bg_image = s.get("bg_image", "")
        if bg_image and os.path.exists(str(bg_image)):
            pix = QPixmap(str(bg_image))
            state.bg_pixmap = pix if not pix.isNull() else None
            self._bg_pixmap = state.bg_pixmap
        else:
            state.bg_pixmap = None
            self._bg_pixmap = None
        state.notify()

    def update_text(self, text: str) -> None:
        """Push text into LiveState."""
        from live_state import get_state
        state = get_state()
        state.current_text = text
        self._current_text = text
        state.notify()

    # ── Aspect ratio API ──────────────────────────────────────────────────────

    def set_aspect_ratio(self, ratio: float) -> None:
        if ratio and ratio > 0:
            self._aspect = ratio
            self.updateGeometry()
            w = self.width()
            if w > 0:
                h = max(1, int(w / self._aspect))
                if h != self.height():
                    self.setFixedHeight(h)
            self.update()

    def set_target_resolution(self, width: int, height: int) -> None:
        """Update the reference resolution used for font-size scaling.

        Call this whenever the display screen dimensions change so that
        ``_draw_frame()`` uses the correct ``scale = preview_w / target_w``
        ratio instead of the hardcoded 1920 default.
        """
        if width > 0 and height > 0:
            self._target_w = width
            self._target_h = height
            # Keep aspect ratio in sync with actual display dimensions
            self.set_aspect_ratio(width / height)
            self.update()

    # ── LiveState observer ────────────────────────────────────────────────────

    def _on_state_changed(self) -> None:
        from live_state import get_state
        state = get_state()
        s = state.settings or self._settings_ref or {}
        # Keep the background video/camera feed + animation ticker in sync
        self._sync_video_feed(s)
        self._sync_anim_timer(s)
        if self._frozen or self._engine_pixmap is not None:
            return
        self.update()

    # ── Size management ───────────────────────────────────────────────────────

    def sizeHint(self):
        return QSize(320, 180)

    def resizeEvent(self, event):
        w = self.width()
        h = max(1, int(w / self._aspect))
        if h != self.height():
            self.setFixedHeight(h)

    # ── Internal renderer ─────────────────────────────────────────────────────

    def _render_to_pixmap(self) -> QPixmap:
        """Render current frame to an off-screen pixmap (for freeze snapshot)."""
        w = max(1, self.width())
        h = max(1, self.height())
        pix = QPixmap(w, h)
        pix.fill(Qt.GlobalColor.black)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self._draw_frame(p, w, h)
        p.end()
        return pix

    def _draw_frame(self, p: QPainter, w: int, h: int) -> None:
        """
        Mirrors display.js drawFrame() step-by-step:
        background → projector-off → black → text → bible ref → logo
        """
        from live_state import get_state
        state = get_state()
        s     = state.settings or self._settings_ref or {}
        scale = w / max(1, self._target_w)

        # ── Projector-off ──────────────────────────────────────────────────────
        if state.projector_off:
            p.fillRect(0, 0, w, h, QColor("#000000"))
            p.setPen(QColor("#333333"))
            f = QFont("Arial")
            f.setPixelSize(max(8, round(28 * scale)))
            f.setBold(True)
            p.setFont(f)
            p.drawText(QRect(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "PROJECTOR OFF")
            return

        # ── Background (shared renderer) ──────────────────────────────────────
        bg_pix = state.bg_pixmap or self._bg_pixmap
        render_background_on_painter(p, w, h, s, bg_pixmap=bg_pix,
                                     video_frame=self._video_frame,
                                     anim_phase=self._anim_phase)

        # ── Text ──────────────────────────────────────────────────────────────
        text = state.current_text or self._current_text or ""
        if text and text.strip():
            render_text_on_painter(p, text, w, h, s, scale)

        # ── Bible reference (bottom-right) ────────────────────────────────────
        is_bible = (
            (s.get("source") == "bible" or
             getattr(state, "metadata", {}).get("source") == "bible")
            if hasattr(state, "metadata") else s.get("source") == "bible"
        )
        if is_bible:
            ref = (getattr(state, "metadata", {}).get("reference", "")
                   if hasattr(state, "metadata") else "")
            ref = ref or s.get("bible_reference", "") or self._current_ref
            if ref:
                _draw_reference_on_painter(p, ref, w, h, s, scale)

        # ── Overlays: logo + clock + ticker + copyright watermark ─────────────
        self._draw_overlays(p, w, h, state, scale)

    def _draw_overlays(self, p: QPainter, w: int, h: int, state, scale: float) -> None:
        """Draw logo / clock / ticker / copyright on top of a RenderEngine frame."""
        import time, datetime

        # Logo
        if state.logo_active and state.logo_pixmap and not state.logo_pixmap.isNull():
            max_logo_w = round(w * 0.15)
            max_logo_h = round(h * 0.12)
            logo_scaled = state.logo_pixmap.scaled(
                max_logo_w, max_logo_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            pad = round(h * 0.02)
            p.setOpacity(0.85)
            p.drawPixmap(pad, pad, logo_scaled)
            p.setOpacity(1.0)

        # Clock
        if state.show_clock:
            now = datetime.datetime.now()
            fmt = state.clock_fmt or "HH:MM:SS"
            if fmt == "HH:MM:SS":
                clock_str = now.strftime("%H:%M:%S")
            elif fmt == "HH:MM":
                clock_str = now.strftime("%H:%M")
            else:
                clock_str = now.strftime("%I:%M %p")
            f = QFont("Consolas")
            f.setPixelSize(max(8, round(22 * scale)))
            f.setBold(True)
            p.setFont(f)
            fm = QFontMetrics(f)
            cw = fm.horizontalAdvance(clock_str)
            ch = fm.height()
            pad = round(h * 0.025)
            p.fillRect(w - cw - pad * 2 - 2, pad - 2, cw + pad * 2, ch + 4,
                       QColor(0, 0, 0, 160))
            p.setPen(QColor(state.clock_color or "#ffffff"))
            p.drawText(w - cw - pad - 2, pad + fm.ascent(), clock_str)

        # Ticker (show static text — no scroll animation in preview)
        if state.ticker_active and state.ticker_text:
            f = QFont("Arial")
            f.setPixelSize(max(7, round(18 * scale)))
            p.setFont(f)
            fm = QFontMetrics(f)
            th = fm.height() + round(4 * scale)
            p.fillRect(0, h - th, w, th, QColor(0, 0, 0, 200))
            p.setPen(QColor("#f9e2af"))
            p.drawText(
                QRect(round(6 * scale), h - th, w - round(12 * scale), th),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                state.ticker_text,
            )

        # Copyright / metadata watermark
        s = state.settings or {}
        _draw_copyright_on_painter(p, s, getattr(state, "_metadata", {}), w, h, scale)

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        from live_state import get_state
        state = get_state()
        w = self.width()
        h = self.height()
        scale = w / max(1, self._target_w)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # ── Priority 1: RenderEngine push-mode (always live, even while frozen) ──
        if self._engine_pixmap and not self._engine_pixmap.isNull():
            painter.drawPixmap(0, 0, self._engine_pixmap.scaled(
                w, h,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
            # Draw overlays not included in RenderEngine frame
            self._draw_overlays(painter, w, h, state, scale)

        # ── Priority 2: Internal renderer (mirrors display.js) ────────────────
        else:
            self._draw_frame(painter, w, h)

        # ── Status indicator: LIVE border + label ─────────────────────────────
        _override = getattr(state, "_preview_is_live_override", None)
        if _override is not None:
            is_live = _override
        else:
            is_live = bool(state.current_text) and not state.projector_off

        if is_live:
            border_color = QColor("#4caf50")
            label_text   = "● LIVE"
            label_color  = QColor("#4caf50")
        else:
            border_color = QColor("#2a2a2a")
            label_text   = "◎ PREVIEW"
            label_color  = QColor("#555555")

        # Frozen indicator overrides border colour
        if self._frozen:
            border_color = QColor("#ff8833")
            label_text   = "❄ FREEZE"
            label_color  = QColor("#ff8833")

        pen = QPen(border_color, 2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(1, 1, w - 2, h - 2)

        label_font = QFont("Segoe UI", max(6, int(8 * scale + 0.5)), QFont.Weight.Bold)
        painter.setFont(label_font)
        fm = painter.fontMetrics()
        lw_px = fm.horizontalAdvance(label_text)
        lh_px = fm.height()
        pad   = max(3, int(4 * scale))
        pill_w = lw_px + pad * 2
        pill_h = lh_px + pad
        pill_x = w - pill_w - 4
        pill_y = h - pill_h - 4
        painter.fillRect(pill_x, pill_y, pill_w, pill_h, QColor(0, 0, 0, 160))
        painter.setPen(label_color)
        painter.drawText(
            QRect(pill_x, pill_y, pill_w, pill_h),
            Qt.AlignmentFlag.AlignCenter, label_text,
        )

        # Placeholder when no output
        if not state.current_text and not state.logo_active:
            painter.setPen(QColor(60, 60, 60))
            f = QFont("Segoe UI", max(6, int(9 * scale + 0.5)))
            painter.setFont(f)
            painter.drawText(
                QRect(0, 0, w, h),
                Qt.AlignmentFlag.AlignCenter, t("no_output"),
            )

        painter.end()
