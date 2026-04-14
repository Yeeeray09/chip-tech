"""
renderer.py — Converts slide data into 1080x1080 PNG images using Pillow.
Design: dark tech hook/CTA slides, light content slides, colored keywords,
gradient top bar, CHIP mascot, logo bottom-left.
"""

import logging
import os
import re
import textwrap
import urllib.request
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from generator import CarouselContent, Slide

log = logging.getLogger(__name__)

# ── Canvas ───────────────────────────────────────────────────────────────────
SIZE          = (1080, 1080)
BG_COLOR      = (247, 250, 248)      # #F7FAF8 neutral light (content slides)

# ── Brand colors ─────────────────────────────────────────────────────────────
GREEN         = (0, 217, 111)        # #00D96F
BLUE          = (0, 153, 255)        # #0099FF
DARK          = (20, 20, 30)
DARK_BG_TOP   = (10, 26, 15)         # #0a1a0f
DARK_BG_BOT   = (13, 40, 24)         # #0d2818
BAR_COLORS    = [GREEN, BLUE, GREEN, BLUE, GREEN, BLUE]  # one per slide (kept for color param)

# ── Layout constants ──────────────────────────────────────────────────────────
TOP_BAR_H     = 18
MARGIN        = 72
MASCOT_SIZE   = (180, 180)
LOGO_SIZE     = (56, 56)

# Individual mascot image per mood (filenames as provided in assets/)
MOOD_FILES: dict[str, str] = {
    "happy":   "chip-happy.png",
    "excited": "chip-excited.png",
    "angry":   "chip-angry.png",
    "confused":"chip-confused.png",
}
MOOD_FALLBACK = "chip-normal.png"

# Mood → badge label
MOOD_BADGE: dict[str, str] = {
    "angry":   "ESCÁNDALO",
    "excited": "NOVEDAD",
    "happy":   "BUENAS NOTICIAS",
    "confused":"CURIOSO",
}
MOOD_BADGE_DEFAULT = "TECH NEWS"

# ── Font sizes ────────────────────────────────────────────────────────────────
TITLE_SIZE    = 68
TEXT_SIZE     = 34
SOURCE_SIZE   = 28
LOGO_TEXT_SZ  = 34

ASSETS_DIR    = Path(__file__).parent / "assets"
FONTS_DIR     = ASSETS_DIR / "fonts"
OUTPUT_DIR    = Path(__file__).parent / "output"

# ── Poppins font files ────────────────────────────────────────────────────────
_POPPINS_URLS: dict[str, str] = {
    "Poppins-Regular.ttf":  "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Regular.ttf",
    "Poppins-Bold.ttf":     "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Bold.ttf",
    "Poppins-SemiBold.ttf": "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-SemiBold.ttf",
}


def _ensure_poppins() -> None:
    """Download missing Poppins font files from Google Fonts on first run."""
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    for filename, url in _POPPINS_URLS.items():
        dest = FONTS_DIR / filename
        if dest.exists():
            continue
        log.info("Downloading font %s …", filename)
        try:
            urllib.request.urlretrieve(url, dest)
            log.info("  Saved → %s", dest)
        except Exception as exc:
            log.warning("Could not download %s: %s", filename, exc)


# Download on module load (runs once; subsequent imports are instant)
_ensure_poppins()


def _load_font(size: int, bold: bool = False, semibold: bool = False) -> ImageFont.FreeTypeFont:
    """Load a Poppins variant from assets/fonts/, with system-font fallback."""
    if semibold:
        preferred = FONTS_DIR / "Poppins-SemiBold.ttf"
    elif bold:
        preferred = FONTS_DIR / "Poppins-Bold.ttf"
    else:
        preferred = FONTS_DIR / "Poppins-Regular.ttf"

    if preferred.exists():
        return ImageFont.truetype(str(preferred), size)

    # Fallback: other Poppins variants already downloaded
    for fallback in FONTS_DIR.glob("Poppins-*.ttf"):
        try:
            return ImageFont.truetype(str(fallback), size)
        except Exception:
            continue

    # Last resort: system fonts
    system_candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in system_candidates:
        if os.path.exists(path):
            log.warning("Poppins not available, using system font: %s", path)
            return ImageFont.truetype(path, size)

    log.warning("No TrueType font found, using PIL default")
    return ImageFont.load_default()


# ── Background helpers ────────────────────────────────────────────────────────

def _draw_dark_tech_bg(draw: ImageDraw.Draw) -> None:
    """Fill with a dark vertical gradient (#0a1a0f → #0d2818) + subtle circuit-grid."""
    r1, g1, b1 = DARK_BG_TOP
    r2, g2, b2 = DARK_BG_BOT
    for y in range(SIZE[1]):
        t = y / SIZE[1]
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        draw.line([(0, y), (SIZE[0] - 1, y)], fill=(r, g, b))

    grid_color = (25, 58, 38)
    grid_step  = 80
    for x in range(0, SIZE[0], grid_step):
        draw.line([(x, 0), (x, SIZE[1] - 1)], fill=grid_color, width=1)
    for y in range(0, SIZE[1], grid_step):
        draw.line([(0, y), (SIZE[0] - 1, y)], fill=grid_color, width=1)


def _draw_gradient_bar(draw: ImageDraw.Draw) -> None:
    """Draw top bar as a horizontal GREEN → BLUE gradient."""
    r1, g1, b1 = GREEN
    r2, g2, b2 = BLUE
    for x in range(SIZE[0]):
        t = x / SIZE[0]
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        draw.line([(x, 0), (x, TOP_BAR_H - 1)], fill=(r, g, b))


def _draw_dot_pattern(draw: ImageDraw.Draw) -> None:
    """Draw a very subtle dot grid on the light content-slide background."""
    dot_color = (215, 225, 218)
    dot_step  = 36
    dot_r     = 2
    for x in range(dot_step, SIZE[0], dot_step):
        for y in range(dot_step, SIZE[1], dot_step):
            draw.ellipse(
                [(x - dot_r, y - dot_r), (x + dot_r, y + dot_r)],
                fill=dot_color,
            )


# ── Hook-slide helpers ────────────────────────────────────────────────────────

def _draw_mood_badge(draw: ImageDraw.Draw, mood: str) -> None:
    """Draw a category badge top-left on the dark background."""
    label = MOOD_BADGE.get(mood, MOOD_BADGE_DEFAULT)
    font  = _load_font(24, semibold=True)

    pad_x, pad_y = 18, 10
    tw  = int(draw.textlength(label, font=font))
    bx  = MARGIN
    by  = 52
    bw  = tw + pad_x * 2
    bh  = 24 + pad_y * 2

    draw.rounded_rectangle(
        [(bx, by), (bx + bw, by + bh)],
        radius=6,
        fill=(20, 55, 35),
        outline=(0, 160, 70),
        width=2,
    )
    draw.text((bx + pad_x, by + pad_y), label, font=font, fill=GREEN)


def _draw_centered_rich_title(draw: ImageDraw.Draw, title: str, y_start: int) -> None:
    """Render hook title centered; **keywords** in GREEN/BLUE, plain text in white."""
    font   = _load_font(80, bold=True)
    title  = _strip_emoji(title)
    tokens = _tokenize(title)

    words: list[tuple[str, bool]] = []
    for chunk, is_kw in tokens:
        for word in chunk.split():
            words.append((word, is_kw))
    words = _merge_trailing_punctuation(words)

    max_width = SIZE[0] - MARGIN * 2
    space_w   = draw.textlength(" ", font=font)
    line_h    = int(80 * 1.25)

    # Word-wrap into lines
    lines: list[list[tuple[str, bool]]] = []
    current_line: list[tuple[str, bool]] = []
    current_width: float = 0.0

    for word, is_kw in words:
        w     = draw.textlength(word, font=font)
        extra = space_w if current_line else 0.0
        if current_width + extra + w > max_width and current_line:
            lines.append(current_line)
            current_line  = [(word, is_kw)]
            current_width = w
        else:
            current_line.append((word, is_kw))
            current_width += extra + w

    if current_line:
        lines.append(current_line)

    # Vertically center in the usable area (below badge, above mascot/handle)
    block_h  = len(lines) * line_h
    area_end = SIZE[1] - 200
    y = y_start + max(0, (area_end - y_start - block_h) // 2)

    kw_colors = [GREEN, BLUE]
    kw_idx    = 0

    for line_words in lines:
        total_w = sum(draw.textlength(w, font=font) for w, _ in line_words)
        if len(line_words) > 1:
            total_w += space_w * (len(line_words) - 1)
        x = (SIZE[0] - total_w) // 2

        for word, is_kw in line_words:
            if is_kw:
                color   = kw_colors[kw_idx % len(kw_colors)]
                kw_idx += 1
            else:
                color = (255, 255, 255)
            ww = draw.textlength(word, font=font)
            draw.text((x, y), word, font=font, fill=color)
            x += ww + space_w

        y += line_h


# ── Shared text utilities ─────────────────────────────────────────────────────

def _strip_emoji(text: str) -> str:
    """Remove characters outside the Basic Multilingual Plane (> U+FFFF)."""
    return "".join(ch for ch in text if ord(ch) <= 0xFFFF)


def _fix_punctuation(text: str) -> str:
    """Remove spaces before commas and periods: 'word , next' → 'word, next'."""
    return re.sub(r"\s+([,.])", r"\1", text)


def _merge_trailing_punctuation(words: list[tuple[str, bool]]) -> list[tuple[str, bool]]:
    """
    Attach leading punctuation tokens (', ' or '.') to the preceding word so
    they are never rendered with a preceding space.
    E.g. [('tech', True), ('.', False)] → [('tech.', True)]
    """
    result: list[tuple[str, bool]] = []
    for word, is_kw in words:
        if word in (",", ".") and result:
            prev_word, prev_kw = result[-1]
            result[-1] = (prev_word + word, prev_kw)
        else:
            result.append((word, is_kw))
    return result


def _draw_source_tag(draw: ImageDraw.Draw, source: str, color: tuple) -> None:
    font = _load_font(SOURCE_SIZE)
    text = f"• {source.upper()}"
    draw.text((MARGIN, TOP_BAR_H + 24), text, font=font, fill=color)


def _draw_title(draw: ImageDraw.Draw, title: str) -> int:
    """Returns the y-coordinate after the title block."""
    font = _load_font(TITLE_SIZE, bold=True)
    wrapped = textwrap.fill(_strip_emoji(title), width=20)
    y = TOP_BAR_H + 80
    draw.text((MARGIN, y), wrapped, font=font, fill=DARK)
    # Estimate height: count lines × line height
    lines = wrapped.count("\n") + 1
    return y + lines * int(TITLE_SIZE * 1.25) + 24


def _tokenize(text: str) -> list[tuple[str, bool]]:
    """Split text into (token, is_keyword) pairs based on **..** markers."""
    tokens = []
    parts = re.split(r"(\*\*[^*]+\*\*)", text)
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            tokens.append((part[2:-2], True))
        else:
            tokens.append((part, False))
    return tokens


def _measure_rich_text(
    draw: ImageDraw.Draw,
    words: list[tuple[str, bool]],
    max_width: int,
) -> int:
    """Return the total pixel height of the wrapped word list."""
    font_regular = _load_font(TEXT_SIZE)
    font_bold    = _load_font(TEXT_SIZE, semibold=True)
    space_w      = draw.textlength(" ", font=font_regular)
    line_h       = int(TEXT_SIZE * 1.6)
    x            = MARGIN
    lines        = 1

    for word, is_kw in words:
        font = font_bold if is_kw else font_regular
        w    = draw.textlength(word, font=font)
        if x + w > MARGIN + max_width and x != MARGIN:
            lines += 1
            x = MARGIN
        x += w + space_w

    return lines * line_h


def _draw_rich_text(
    draw: ImageDraw.Draw,
    text: str,
    y_start: int,
    y_end: int,
    keyword_colors: list[tuple],
    max_width: int,
) -> None:
    """Render text with colored keyword tokens, vertically centered in [y_start, y_end]."""
    font_regular = _load_font(TEXT_SIZE)
    font_bold    = _load_font(TEXT_SIZE, semibold=True)
    color_cycle  = keyword_colors
    kw_idx       = 0
    line_h       = int(TEXT_SIZE * 1.6)

    tokens = _tokenize(_fix_punctuation(_strip_emoji(text)))

    words: list[tuple[str, bool]] = []
    for chunk, is_kw in tokens:
        for word in chunk.split():
            words.append((word, is_kw))
    words = _merge_trailing_punctuation(words)

    text_h  = _measure_rich_text(draw, words, max_width)
    area_h  = y_end - y_start
    y_offset = max(0, (area_h - text_h) // 2)

    x, y    = MARGIN, y_start + y_offset
    space_w = draw.textlength(" ", font=font_regular)

    for word, is_kw in words:
        font  = font_bold if is_kw else font_regular
        color = color_cycle[kw_idx % len(color_cycle)] if is_kw else DARK
        if is_kw:
            kw_idx += 1

        w = draw.textlength(word, font=font)

        if x + w > MARGIN + max_width and x != MARGIN:
            x  = MARGIN
            y += line_h

        draw.text((x, y), word, font=font, fill=color)
        x += w + space_w


# ── Asset helpers ─────────────────────────────────────────────────────────────

def _load_asset(filename: str) -> Image.Image | None:
    """
    Open an asset file and return it as an RGBA image.
    Handles palettes (P/PA mode) and other exotic modes before converting,
    which avoids Pillow's 'bad transparency mask' error on indexed PNGs.
    Returns None if the file does not exist or cannot be opened.
    """
    path = ASSETS_DIR / filename
    if not path.exists():
        log.debug("Asset not found: %s — skipping", path)
        return None
    try:
        img = Image.open(path)
        img.load()  # force decode so errors surface here, not later
        # Palette images must be converted before RGBA to preserve transparency
        if img.mode in ("P", "PA"):
            img = img.convert("RGBA")
        elif img.mode != "RGBA":
            img = img.convert("RGBA")
        return img
    except Exception as exc:
        log.warning("Could not open asset '%s': %s", filename, exc)
        return None


def _remove_white_bg(img: Image.Image, tolerance: int = 15, border: int = 10) -> Image.Image:
    """
    Make near-white pixels transparent only within `border` pixels of each edge.
    Interior whites (eyes, details) are left completely untouched.
    """
    img = img.convert("RGBA")
    pixels = img.load()
    w, h = img.size

    for y in range(h):
        for x in range(w):
            if x < border or x >= w - border or y < border or y >= h - border:
                r, g, b, a = pixels[x, y]
                if r >= 255 - tolerance and g >= 255 - tolerance and b >= 255 - tolerance:
                    pixels[x, y] = (r, g, b, 0)

    return img


def _draw_mascot(img: Image.Image, mood: str = "happy") -> None:
    filename = MOOD_FILES.get(mood, MOOD_FALLBACK)
    face = _load_asset(filename)
    if face is None:
        log.debug("Mood asset '%s' missing, trying fallback '%s'", filename, MOOD_FALLBACK)
        face = _load_asset(MOOD_FALLBACK)
    if face is None:
        return
    try:
        face = face.resize(MASCOT_SIZE, Image.LANCZOS)
        x = SIZE[0] - MASCOT_SIZE[0] - MARGIN // 2
        y = SIZE[1] - MASCOT_SIZE[1] - 80
        img.paste(face, (x, y), face)
        log.debug("  Mascot '%s' drawn at (%d, %d)", filename, x, y)
    except Exception as exc:
        log.warning("Could not draw mascot: %s", exc)


def _draw_logo(draw: ImageDraw.Draw, img: Image.Image, color: tuple) -> None:
    """Draw the chip-logo.png + '@chipitech' text bottom-left."""
    bx, by = MARGIN, SIZE[1] - 80

    logo = _load_asset("chip-logo.png")
    if logo is not None:
        try:
            logo = logo.resize(LOGO_SIZE, Image.LANCZOS)
            img.paste(logo, (bx, by - LOGO_SIZE[1] // 2), logo)
            bx += LOGO_SIZE[0] + 14
        except Exception as exc:
            log.warning("Could not paste logo: %s", exc)
            logo = None  # fall through to drawn fallback

    if logo is None:
        # Draw a colored circle with 'C'
        r = LOGO_SIZE[0] // 2
        cx, cy = bx + r, by
        draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=color)
        font_c = _load_font(28, bold=True)
        draw.text((cx - 9, cy - 16), "C", font=font_c, fill=(255, 255, 255))
        bx += LOGO_SIZE[0] + 14

    font_handle = _load_font(LOGO_TEXT_SZ, bold=True)
    draw.text((bx, by - LOGO_TEXT_SZ // 2), "@chipitech", font=font_handle, fill=DARK)


def _draw_source_credit(draw: ImageDraw.Draw, source: str) -> None:
    """Draw 'Fuente: [source]' in small gray text above the logo row (last slide only)."""
    font = _load_font(20)
    draw.text((MARGIN, SIZE[1] - 148), f"Fuente: {source}", font=font, fill=(136, 136, 136))


# ── Slide renderers ───────────────────────────────────────────────────────────

def _render_hook_slide(
    img: Image.Image,
    draw: ImageDraw.Draw,
    slide: Slide,
    mood: str,
    hook_color_idx: int = 0,
) -> None:
    """Slide 1: dark tech background, mood badge, centered rich title, @chipitech."""
    _draw_dark_tech_bg(draw)
    _draw_mood_badge(draw, mood)
    _draw_centered_rich_title(draw, slide.title, y_start=160)

    # @chipitech bottom-left, muted white on dark background
    font_handle = _load_font(LOGO_TEXT_SZ, bold=True)
    draw.text((MARGIN, SIZE[1] - 80), "@chipitech", font=font_handle, fill=(110, 150, 125))


def _render_cta_slide(img: Image.Image, draw: ImageDraw.Draw, slide: Slide, mood: str) -> None:
    """CTA slide: dark tech background, CHIP mascot top-center, white text, @chipitech."""
    _draw_dark_tech_bg(draw)

    # CHIP excited mascot — centered horizontally, upper area
    mascot_size = (220, 220)
    mascot = _load_asset("chip-excited.png")
    if mascot is not None:
        try:
            mascot = mascot.resize(mascot_size, Image.LANCZOS)
            mx = (SIZE[0] - mascot_size[0]) // 2
            my = 140
            img.paste(mascot, (mx, my), mascot)
        except Exception as exc:
            log.warning("Could not draw CTA mascot: %s", exc)

    y = 140 + mascot_size[1] + 60

    # "¿Te gustó?" — bold white, centered
    font_title = _load_font(72, bold=True)
    text1 = "¿Te gustó?"
    w1 = draw.textlength(text1, font=font_title)
    draw.text(((SIZE[0] - w1) // 2, y), text1, font=font_title, fill=(255, 255, 255))
    y += int(72 * 1.3)

    # "Síguenos para más noticias tech" — "Síguenos" in GREEN, rest in white
    font_body = _load_font(52, bold=True)
    line2_words = [
        ("Síguenos", True),
        ("para", False),
        ("más", False),
        ("noticias", False),
        ("tech", False),
    ]
    space_w = draw.textlength(" ", font=font_body)
    total_w = (
        sum(draw.textlength(w, font=font_body) for w, _ in line2_words)
        + space_w * (len(line2_words) - 1)
    )
    x = int((SIZE[0] - total_w) // 2)
    for word, is_green in line2_words:
        color = GREEN if is_green else (255, 255, 255)
        ww = draw.textlength(word, font=font_body)
        draw.text((x, y), word, font=font_body, fill=color)
        x += int(ww + space_w)

    # @chipitech — centered, muted white
    font_handle = _load_font(32)
    handle = "@chipitech"
    hw = draw.textlength(handle, font=font_handle)
    draw.text(((SIZE[0] - hw) // 2, SIZE[1] - 80), handle, font=font_handle, fill=(110, 150, 125))


def _render_content_slide(
    img: Image.Image,
    draw: ImageDraw.Draw,
    slide: Slide,
    total_slides: int,
    source: str,
    color: tuple,
) -> None:
    """Slides 2+: dot pattern, gradient bar, source tag, title, separator, body text."""
    _draw_dot_pattern(draw)
    _draw_gradient_bar(draw)
    _draw_source_tag(draw, source, color)
    y = _draw_title(draw, slide.title)

    separator_y = y - 10
    draw.line([(MARGIN, separator_y), (SIZE[0] - MARGIN, separator_y)], fill=color, width=3)
    y += 10

    _draw_rich_text(
        draw,
        slide.text,
        y_start=y,
        y_end=SIZE[1] - 120,
        keyword_colors=[GREEN, BLUE],
        max_width=SIZE[0] - MARGIN * 2 - MASCOT_SIZE[0] - 20,
    )

    if slide.slide_number == total_slides:
        _draw_source_credit(draw, source)


def render_slide(
    slide: Slide,
    total_slides: int,
    source: str,
    output_path: Path,
    mood: str = "happy",
    hook_color_idx: int = 0,
) -> Path:
    """Render a single slide to PNG and return its path."""
    color = BAR_COLORS[(slide.slide_number - 1) % len(BAR_COLORS)]

    img  = Image.new("RGB", SIZE, BG_COLOR)
    draw = ImageDraw.Draw(img)

    if slide.is_cta:
        _render_cta_slide(img, draw, slide, mood)
        # CTA handles its own branding; skip logo row and mascot
    elif slide.slide_number == 1:
        _render_hook_slide(img, draw, slide, mood, hook_color_idx)
        _draw_mascot(img, mood)
        # Hook slide handles its own @chipitech in dark style; no _draw_logo
    else:
        _render_content_slide(img, draw, slide, total_slides, source, color)
        _draw_mascot(img, mood)
        _draw_logo(draw, img, color)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG", optimize=False)
    log.info("  Saved slide %d → %s", slide.slide_number, output_path)
    return output_path


def render_carousel(carousel: CarouselContent, run_id: str) -> list[Path]:
    """Render all slides for a carousel. Returns list of output PNG paths."""
    paths: list[Path] = []
    source          = carousel.article.source
    mood            = carousel.mood
    hook_color_idx  = carousel.hook_color_idx

    for slide in carousel.slides:
        fname = OUTPUT_DIR / run_id / f"slide_{slide.slide_number:02d}.png"
        path  = render_slide(slide, len(carousel.slides), source, fname, mood, hook_color_idx)
        paths.append(path)

    return paths
