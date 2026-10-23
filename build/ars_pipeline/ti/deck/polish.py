# Ported from ARS v5 02-Scripts/ars/deck/polish.py at a491b5c (James Gilmore); logic unchanged.
"""Deterministic copy polish for the deck (James, issue #17).

Three jobs, all rule-based so the output is reproducible:
- typography: no em dashes (first split -> colon, later -> comma),
  single spaces, no trailing periods
- casing: subtitles open with a capital, interior casing untouched
  (NSF/OD, Reg E, month tags survive)
- restraint: a subtitle that only restates its headline is dropped --
  a sub earns its line by adding a source, a base, or a definition

Also owns title fitting: the estimated (size, lines) for a headline so
the layout reserves the height the text will actually take. The old
rule assumed anything under 62 chars fit one line at 30pt; at 30pt a
12-inch box fits about 52, and the 53-61 band wrapped into the
subtitle. That bleed is this module's founding bug.
"""

from __future__ import annotations

import re

# chars that fit on one line of the content width, by font size --
# conservative estimates for the bold display face. Calibrated to the
# POST-SPINE content width (11.53in, v4 grid): the old 12.09in numbers
# let 50-52-char titles claim one 30pt line and wrap into the subtitle
# (M4 sweep, slides 5/16/36/39/66/75).
_CHARS_PER_LINE = {30: 49, 25: 62}

_STOPWORDS = frozenset(
    "a an and are at by for from in is it of on or per the to vs with "
    "their its our your this that as versus against".split())


def _normalize(text: str) -> str:
    # No em dashes anywhere in deck copy (James, issue #28): the first
    # split becomes a colon, any further ones read as commas.
    text = re.sub(r"\s*--\s*", " — ", text)
    text = text.replace(" — ", ": ", 1).replace(" — ", ", ")
    text = text.replace("\u2014", "-")
    text = re.sub(r"\s+", " ", text).strip()
    return text.rstrip(".").rstrip()


def title(text: str) -> str:
    """Typographic cleanup only -- a headline's words are the analyst's."""
    return _normalize(text)


def _content_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9][a-z0-9/&'-]*", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def sub(text: str | None, title_text: str) -> str | None:
    """Polish a subtitle; return None when it should not render at all."""
    if not text or not str(text).strip():
        return None
    out = _normalize(str(text))
    if not out:
        return None
    # restraint: drop a sub that adds nothing the headline didn't say.
    # 'new' means content words (incl. numbers) absent from the title.
    new = _content_words(out) - _content_words(title_text)
    if len(new) < 2:
        return None
    # sentence case: first letter up, everything else untouched
    return out[0].upper() + out[1:]


def title_fit(text: str) -> tuple[int, int]:
    """(font_size, lines) the layout must reserve for this headline."""
    n = len(text)
    if n <= _CHARS_PER_LINE[30]:
        return 30, 1
    if n <= _CHARS_PER_LINE[25]:
        return 25, 1
    return 25, 2
