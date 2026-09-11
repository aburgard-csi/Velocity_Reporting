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
    """The Summit slide: `Inputs/Summit/summit_slide.pptx` if present,
    else the copy committed here.

    This one asset is replaced by hand before each Summit — Ft. Lauderdale is
    next — by whoever prepares it, who should not need a commit to ship it. So
    The pipeline copy wins when a file is there.

    Everything else stays in the repo on purpose. Fonts are committed precisely
    so both machines render identically and cannot drift; the template shells are
    versioned build inputs whose geometry qa_all diffs against a baseline every
    run. Moving those to a streamed network folder would trade the two properties
    this pipeline is built on — fast and identical everywhere — for a consistency
    it already has.
    """
    try:
        from rpe_env import inputs
        shared = inputs() / "Summit" / "summit_slide.pptx"
        if shared.is_file():
            return str(shared)
    except (Exception, SystemExit):
        # SystemExit, not just Exception: rpe_env RAISES SystemExit when
        # RPE_DATA_ROOT is unset or its tree is missing, and SystemExit does not
        # inherit from Exception. Catching only Exception let an OPTIONAL lookup
        # kill the build on a machine that had never configured RPE_DATA_ROOT.
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


_RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _rebind_rels(el, src_part, dst_part):
    """Point every r:embed / r:link inside `el` at a copy living in `dst_part`.

    A cloned <p:pic> carries the SOURCE deck's relationship id. Dropped into
    another deck that id means a different part or nothing at all, and the deck
    opens with a red X where the logo was. Walks descendants, not just the
    element itself: the Summit slide's event photos sit inside a <p:grpSp>.
    """
    for node in el.iter():
        for attr in ("embed", "link"):
            key = "{%s}%s" % (_RNS, attr)
            rid = node.get(key)
            if not rid or rid not in src_part.rels:
                continue
            rel = src_part.rels[rid]
            if rel.is_external:
                node.set(key, dst_part.relate_to(rel.target_ref, rel.reltype, is_external=True))
                continue
            # Re-add the image from its BYTES, never by relating to the source
            # Part object. A Part carries its own partname: relating the asset's
            # /ppt/media/image2.png into a deck that already has one writes the
            # zip entry TWICE ("Duplicate name: ppt/media/image2.png"), which is
            # the malformed-package failure that made the 2026.08 ICS decks
            # unopenable while every lint rule passed. get_or_add_image_part
            # assigns a free partname and dedupes identical images by hash.
            if rel.reltype.endswith("/image"):
                _img, new_rid = dst_part.get_or_add_image_part(BytesIO(rel.target_part.blob))
                node.set(key, new_rid)
            else:
                node.set(key, dst_part.relate_to(rel.target_part, rel.reltype))


def _blank_after_title(prs):
    """A new empty slide at index 1. Slides are ADDED then reordered, never
    deleted — freeing a partname makes python-pptx hand that number to a later
    slide and the package ends up referencing parts twice (CLAUDE.md; the defect
    behind the unopenable 2026.08 ICS decks)."""
    lay = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[-1]
    new = prs.slides.add_slide(lay)
    for sh in list(new.shapes):
        sh._element.getparent().remove(sh._element)
    lst = prs.slides._sldIdLst
    sid = list(lst)[-1]
    lst.remove(sid)
    lst.insert(1, sid)
    return new


def _is_summit(slide, prs):
    """Either shape of the slide: the text one, or the full-bleed picture that
    ICS and MRPC decks carried until 2026-09-11."""
    for sh in slide.shapes:
        if sh.has_text_frame and ("Executive Summit" in sh.text_frame.text
                                  or "About the Summit" in sh.text_frame.text):
            return True
    pics = [sh for sh in slide.shapes if sh.shape_type == 13]
    return (len(pics) == 1 and pics[0].width is not None
            and pics[0].width >= prs.slide_width * 0.98
            and not any(sh.has_text_frame and sh.text_frame.text.strip() for sh in slide.shapes))


def insert_summit_after_title(prs, asset=None):
    """Put the Summit slide at index 1, cloned from `build/assets/summit_slide.pptx`.

    **It used to stamp a flat JPG** (`assets/Velocity Executive Summit.jpg`) —
    a picture of the slide — so ICS and MRPC decks got an image while ARS and
    CashPlease carried the real one from their template shells. Two renderings of
    one slide, and replacing the Summit meant replacing both: the .pptx AND a
    re-exported image, which needs PowerPoint or LibreOffice and so could not be
    done from the pipeline at all (Aaron, 2026-09-11). Every deck now clones the
    same .pptx, which is also the file `summit_date()` reads, so the slide on the
    page and the date the build derives cannot disagree.

    Replaces the CONTENT of an existing Summit slide in place when there is one —
    it does not delete the slide. Returns True when a Summit slide is present
    afterwards, and is safe to run twice: the second run rewrites the same
    content.
    """
    src_prs = Presentation(asset or ASSET)
    src = _summit_slide(src_prs) or (src_prs.slides[0] if len(src_prs.slides._sldIdLst) else None)
    if src is None:
        return False

    dst = next((s for s in prs.slides if _is_summit(s, prs)), None)
    if dst is None:
        dst = _blank_after_title(prs)
    else:
        lst = prs.slides._sldIdLst
        ids = list(lst)
        cur = ids[list(prs.slides).index(dst)]
        if ids.index(cur) != 1:
            lst.remove(cur)
            lst.insert(1, cur)

    for sh in list(dst.shapes):
        sh._element.getparent().remove(sh._element)

    # The asset's background comes from its LAYOUT, not the slide, and the clone
    # lands on a different deck's layout. Carrying it over explicitly means the
    # slide does not depend on which layout it happens to sit on.
    src_csld = src._element.find(qn("p:cSld"))
    dst_csld = dst._element.find(qn("p:cSld"))
    bg = src_csld.find(qn("p:bg"))
    if bg is None:
        bg = src.slide_layout._element.find(qn("p:cSld")).find(qn("p:bg"))
    old_bg = dst_csld.find(qn("p:bg"))
    if old_bg is not None:
        dst_csld.remove(old_bg)
    if bg is not None:
        new_bg = copy.deepcopy(bg)
        _rebind_rels(new_bg, src.slide_layout.part if src_csld.find(qn("p:bg")) is None else src.part,
                     dst.part)
        dst_csld.insert(0, new_bg)

    spTree = dst.shapes._spTree
    for sh in src.shapes:
        el = copy.deepcopy(sh._element)
        _rebind_rels(el, src.part, dst.part)
        spTree.append(el)

    # Source note, like every other slide (CLAUDE.md: no slide ships without one).
    # It is not optional here: while the slide was a flat picture it carried no text,
    # so the validator's data-slide rule never reached it — the moment it became the
    # real slide, all six ICS-only and MRPC-only decks failed on a missing note
    # (2026-09-11). The ARS shells had their own line calling it "standard ARS
    # Executive Review front matter", which stopped being true when every program
    # started cloning the same file. One slide, one note.
    where = next((sh.text_frame.text.strip() for sh in dst.shapes
                  if sh.has_text_frame and _SUMMIT_DATE_RE.search(
                      " ".join(sh.text_frame.text.split()))), "")
    dst.notes_slide.notes_text_frame.text = (
        "Source — Executive Summit slide, build/assets/summit_slide.pptx"
        + (" (%s)" % " ".join(where.split()) if where else "")
        + ". Standing front matter, identical in every deck; carries no client data.")
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
