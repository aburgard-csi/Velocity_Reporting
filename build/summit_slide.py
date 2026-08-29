#!/usr/bin/env python3
"""Executive Summit slide — shared asset + helpers (all results decks).

Every results deck (ARS / ICS / MRPC) carries the Velocity Solutions Executive Summit
slide immediately after the title slide. This slide keeps its own dense typography
(Montserrat / Montserrat SemiBold / Montserrat Medium at 9-14 pt, tight spacing) and is
NEVER touched by build/restyle_fonts.py.

The pristine slide lives in `build/assets/summit_slide.pptx` (trimmed from the Sugar River v20
base template). Two helpers:

  insert_summit_after_title(prs)  — clone the Summit slide into `prs` at index 1.
  restore_summit_fonts(prs)       — copy the pristine run fonts/sizes back onto a Summit
                                    slide already present in `prs` (used to undo an
                                    accidental restyle).

Usage (CLI): python3 summit_slide.py insert  <deck.pptx> [deck2 ...]
             python3 summit_slide.py restore <deck.pptx> [deck2 ...]
"""
import datetime, os, re, sys, copy
from io import BytesIO
from pptx import Presentation
from pptx.util import Pt
from pptx.oxml.ns import qn

ASSET = os.path.join(os.path.dirname(__file__), "assets", "summit_slide.pptx")
SHAPE_TAGS = {qn('p:sp'), qn('p:pic'), qn('p:graphicFrame'), qn('p:grpSp'), qn('p:cxnSp')}


_SUMMIT_DATE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+(\d{1,2})\s*(?:[-–—]\s*"
    r"(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December)?\s*\d{1,2})?\s*,\s*(\d{4})")

_MONTHS = ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]


def summit_date(asset=ASSET):
    """The Executive Summit's START date, read from the shared Summit slide.

    The decks are prepared FOR the Summit, so the Summit's month is the month
    they are presented in — which is what STYLE.md:85 means by the reporting
    month, as opposed to the data month on the period pills (STYLE.md:44).

    Read from `build/assets/summit_slide.pptx` rather than hardcoded, so it
    moves when the Summit slide does. The asset currently reads
    "Boston, MA  August 31-September 1, 2026"; a range takes its START.

    Returns a date, or None when the slide carries no parseable date — callers
    decide whether that is fatal.
    """
    try:
        prs = Presentation(asset)
    except Exception:
        return None
    for slide in prs.slides:
        for sh in slide.shapes:
            if not sh.has_text_frame:
                continue
            m = _SUMMIT_DATE_RE.search(" ".join(sh.text_frame.text.split()))
            if m:
                month, day, year = m.group(1), int(m.group(2)), int(m.group(3))
                return datetime.date(year, _MONTHS.index(month) + 1, day)
    return None


def summit_period(asset=ASSET):
    """The Summit month as `YYYY.MM`, or None. Aug 31-Sep 1 2026 -> '2026.08'."""
    d = summit_date(asset)
    return f"{d.year:04d}.{d.month:02d}" if d else None


def _summit_slide(prs):
    for s in prs.slides:
        for sh in s.shapes:
            if sh.has_text_frame and ("Executive Summit" in sh.text_frame.text
                                      or "About the Summit" in sh.text_frame.text):
                return s
    return None


def _shape_key(sh):
    return sh.text_frame.text.strip() if sh.has_text_frame else None


def restore_summit_fonts(prs):
    """Copy run font.name/size from the pristine asset onto prs's Summit slide.
    Matches shapes by their text (content is identical; only fonts were altered)."""
    src = _summit_slide(Presentation(ASSET))
    dst = _summit_slide(prs)
    if src is None or dst is None:
        return False
    srcmap = {}
    for sh in src.shapes:
        k = _shape_key(sh)
        if k:
            srcmap.setdefault(k, sh)
    for sh in dst.shapes:
        k = _shape_key(sh)
        if k not in srcmap:
            continue
        sruns = [r for p in srcmap[k].text_frame.paragraphs for r in p.runs]
        druns = [r for p in sh.text_frame.paragraphs for r in p.runs]
        for dr, sr in zip(druns, sruns):
            dr.font.name = sr.font.name
            dr.font.size = sr.font.size
    return True


def insert_summit_after_title(prs):
    """Insert the Velocity Executive Summit slide (full-bleed image from
    build/assets/Velocity Executive Summit.jpg) at index 1, right after the title.
    The slide is picture-only and carries NO page number. Idempotent: if a
    full-bleed summit picture is already at index 1 it is a no-op."""
    img = os.path.join(os.path.dirname(__file__), "assets", "Velocity Executive Summit.jpg")
    # no-op guard: index 1 already a single full-bleed picture
    ids = list(prs.slides._sldIdLst)
    if len(ids) > 1:
        s1 = prs.slides[1]
        pics = [sh for sh in s1.shapes if sh.shape_type == 13]
        if len(pics) == 1 and pics[0].width is not None and pics[0].width >= prs.slide_width * 0.98 \
           and not any(sh.has_text_frame and sh.text_frame.text.strip() for sh in s1.shapes):
            return False
    lay = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[-1]
    new = prs.slides.add_slide(lay)
    for sh in list(new.shapes):
        sh._element.getparent().remove(sh._element)
    new.shapes.add_picture(img, 0, 0, width=prs.slide_width, height=prs.slide_height)
    lst = prs.slides._sldIdLst
    sid = list(lst)[-1]
    lst.remove(sid)
    lst.insert(1, sid)
    return True

if __name__ == "__main__":
    mode = sys.argv[1]
    for path in sys.argv[2:]:
        prs = Presentation(path)
        if mode == "insert":
            ok = insert_summit_after_title(prs)
        elif mode == "restore":
            ok = restore_summit_fonts(prs)
        else:
            raise SystemExit("mode must be 'insert' or 'restore'")
        prs.save(path)
        print(f"{mode}: {'done' if ok else 'no-op'}  {os.path.basename(path)}")
