#!/usr/bin/env python3
"""Will this string fit on one line in that box? Measured, not estimated.

Box geometry is not glyph geometry (CLAUDE.md rule 2). Two things make eyeballing it wrong:

  * **The font is not the one the builder asked for.** The ICS "Billed Expense for 46,195
    Accounts" label is written as Calibri 14pt, but `enforce_min_font` floors every run at
    16pt and the font-role pass rewrites it to Montserrat. Montserrat is much wider: that
    string is 3.10in in Calibri and 3.80in in Montserrat, against 3.70in of usable box. It
    wrapped onto the value beneath it.
  * **LibreOffice will not show you.** It substitutes a narrower face, so the render looked
    clean while PowerPoint wrapped it (CLAUDE.md rule 1).

So measure with the repo's bundled TTFs, at the size the run will ACTUALLY render at, and
subtract the text frame's internal margins.
"""
from __future__ import annotations

import os

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "fonts")

# python-pptx text frames default to 0.1in left and right.
DEFAULT_MARGINS_IN = 0.2

_FONTS = {
    ("Montserrat", False): "Montserrat/static/Montserrat-Regular.ttf",
    ("Montserrat", True): "Montserrat/static/Montserrat-SemiBold.ttf",
    ("Calibri", False): "Carlito/Carlito-Regular.ttf",      # Carlito is metric-compatible
    ("Calibri", True): "Carlito/Carlito-Bold.ttf",
    ("Carlito", False): "Carlito/Carlito-Regular.ttf",
    ("Carlito", True): "Carlito/Carlito-Bold.ttf",
}

_DPI = 96
_cache: dict = {}


def _font(family: str, bold: bool):
    key = (family, bool(bold))
    if key in _cache:
        return _cache[key]
    rel = _FONTS.get(key) or _FONTS.get((family, False))
    path = os.path.join(FONT_DIR, rel) if rel else None
    obj = None
    if path and os.path.exists(path):
        try:
            from PIL import ImageFont
            obj = (ImageFont, path)
        except Exception:
            obj = None
    _cache[key] = obj
    return obj


def text_width_in(text: str, pt: float, family: str = "Montserrat", bold: bool = False) -> float:
    """Rendered width of `text` in inches. Falls back to a wide-ish estimate if the TTF
    is unavailable — erring toward "too wide" so a guard shortens rather than overflows."""
    f = _font(family, bold)
    if f is None:
        return len(text) * (pt / 72.0) * 0.60
    ImageFont, path = f
    try:
        font = ImageFont.truetype(path, int(round(pt * _DPI / 72.0)))
        return font.getlength(text) / _DPI
    except Exception:
        return len(text) * (pt / 72.0) * 0.60


def fits_one_line(text: str, width_in: float, pt: float, family: str = "Montserrat",
                  bold: bool = False, min_pt: float | None = None,
                  margins_in: float = DEFAULT_MARGINS_IN) -> bool:
    """True when `text` fits on ONE line inside a `width_in` box.

    `min_pt` is the floor a later pass will raise the run to (ICS decks enforce 16pt), so
    pass it whenever the deck has one — measuring the nominal size understates the width.
    """
    eff = max(pt, min_pt) if min_pt else pt
    return text_width_in(text, eff, family, bold) <= (width_in - margins_in)


if __name__ == "__main__":
    import sys
    txt = sys.argv[1] if len(sys.argv) > 1 else "Billed Expense for 46,195 Accounts"
    for fam in ("Montserrat", "Calibri"):
        for pt in (14, 16):
            print(f"  {fam:11} {pt}pt  {text_width_in(txt, pt, fam):.2f}in")
