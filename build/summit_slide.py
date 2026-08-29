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

_REPO_ASSET = os.path.join(os.path.dirname(__file__), "assets", "summit_slide.pptx")


def _asset():
    """The Summit slide: `Inputs/Summit/summit_slide.pptx` on Drive if present,
    else the copy committed here.

    This one asset is replaced by hand before each Summit — Ft. Lauderdale is
    next — by whoever prepares it, who should not need a commit to ship it. So
    Drive wins when a file is there.

    Everything else stays in the repo on purpose. Fonts are committed precisely
    so both machines render identically and cannot drift; the template shells are
    versioned build inputs whose geometry qa_all diffs against a baseline every
    run. Moving those to a streamed Drive folder would trade the two properties
    this pipeline is built on — fast and identical everywhere — for a consistency
    it already has.
    """
    try:
        from rpe_env import inputs
        drive = inputs() / "Summit" / "summit_slide.pptx"
        if drive.is_file():
            return str(drive)
    except (Exception, SystemExit):
        # SystemExit, not just Exception: rpe_env RAISES SystemExit when
        # RPE_DATA_ROOT is unset or its tree is missing, and SystemExit does not
        # inherit from Exception. Catching only Exception let an OPTIONAL lookup
        # kill the build on a machine that had never configured Drive.
        pass
    return _REPO_ASSET


ASSET = _asset()
SHAPE_TAGS = {qn('p:sp'), qn('p:pic'), qn('p:graphicFrame'), qn('p:grpSp'), qn('p:cxnSp')}


# Month names spelled out OR abbreviated, with or without a trailing dot. The
# slide has always spelled them out, but it is replaced by hand before each
# Summit and the next one is a different design — a format the parser silently
# misses would fall back to the previous Summit's date, which is worse than
# failing.
_MON_ALT = ("Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
            "Jul(?:y)?|Aug(?:ust)?|Sep(?:t)?(?:ember)?|Oct(?:ober)?|"
            "Nov(?:ember)?|Dec(?:ember)?")
_SUMMIT_DATE_RE = re.compile(
    rf"\b({_MON_ALT})\.?\s+(\d{{1,2}})\s*(?:[-–—]\s*"
    rf"(?:(?:{_MON_ALT})\.?\s*)?\d{{1,2}})?\s*,\s*(\d{{4}})", re.I)

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
                idx = next((i for i, name in enumerate(_MONTHS)
                            if name.lower().startswith(month.lower()[:3])), None)
                if idx is None:
                    continue
                return datetime.date(year, idx + 1, day)
    return None


def summit_period(asset=ASSET, warn_if_past=True):
    """The Summit month as `YYYY.MM`, or None. Aug 31-Sep 1 2026 -> '2026.08'.

    Warns when the Summit it names has already happened. The slide is printed
    ahead of each Summit and not revised until the next one — the August 2026
    slides went to print 2026-08-29 and the asset will keep saying August until
    the November Summit materials land (Aaron, 2026-08-29). So a build falling
    back to this AFTER the Summit is reading a stale date, and should be told.

    The clock is used only to raise the warning, never to derive the value —
    deriving a reporting month from `date.today()` is the bug this fallback
    replaced.
    """
    d = summit_date(asset)
    if not d:
        return None
    if warn_if_past and d < datetime.date.today():
        print(f"!! summit_slide: {asset} still names the {d:%B %Y} Summit, which has "
              f"passed. If you are building for a later Summit, refresh the slide or "
              f"pass the period explicitly (RPE_PERIOD=YYYY.MM).", file=sys.stderr)
    return f"{d.year:04d}.{d.month:02d}"


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
