#!/usr/bin/env python3
"""Shared font-role post-processor — run last on every finished deck (all programs).

Font policy (Aaron, 2026-07-13):
  * Headings (slide titles) .................... Montserrat
  * Callout / KPI / pill / chip / badge boxes .. Montserrat
  * Subheadings, body text, table cells,
    captions, footnotes, page numbers ......... Calibri
  * Charts (rendered images) ................... Carlito/Calibri (set in the chart renderers)

Also floors explicit run sizes at 16 pt, with two exceptions (STYLE.md "Type"):
  * dense tables that cannot fit their fixed content at 16 — slides titled
    "2026 New Releases", "Product Mix", "Program Results by Month Opened",
    "Program Results by Opening Year", "Referred Accounts by Product" (the `dense` tuple in restyle());
  * the branch-detail tables in the Appendix ("Appendix: Take Rate by Branch", "Appendix: Reg E
    Opt-In by Branch", "Appendix: Reg E New Accounts by Branch"; `BRANCH_DETAIL_TABLE`): 15
    branches a page do not fit at 16 pt, so they stay at 12 pt; the slide's other text keeps
    the floor;
  * MRPC decks, which keep a deliberate 10-15 pt hierarchy (see _is_mrpc).
The Executive Summit slide is never touched at all.

Role is inferred so it works on both code-built and cloned/template slides:
  - AUTO_SHAPE with text -> callout/chip/badge -> Montserrat.
  - Title placeholder -> Montserrat; subtitle placeholder -> Calibri.
  - Any other text box: heading (Montserrat) if its largest run is >=22 pt, or if it
    has inherited size and sits at the very top of the slide; otherwise Calibri.
  - Tables -> Calibri.
  - Groups are recursed.

Usage:  python3 restyle_fonts.py <deck.pptx> [more.pptx ...]
"""
import sys
from pptx import Presentation
from pptx.util import Pt, Emu
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN  # noqa (kept for callers that import this module)

try:
    from pptx.enum.shapes import PP_PLACEHOLDER
except Exception:  # older python-pptx
    PP_PLACEHOLDER = None

from brand import HEAD, BODY
MIN = 16
# The Appendix branch-detail tables (branch_appendix_slides) stay at their own size, found by the
# table's shape name rather than by slide title or row count.
BRANCH_DETAIL_TABLE = "Branch Detail Table"
HEAD_SIZE = 22      # runs at/above this are treated as headings


def _title(slide):
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            return sh.text_frame.text.strip().split("\n")[0]
    return ""


def _runs(tf):
    return [r for p in tf.paragraphs for r in p.runs]


def _apply(runs, name, floor=True):
    for r in runs:
        # A Montserrat WEIGHT ("Montserrat ExtraBold", "Montserrat SemiBold") is still the
        # heading face: the cover and dividers (build/cover_divider.py) set one on purpose,
        # and flattening it to "Montserrat" would quietly change their look (2026-10-02).
        if not (name == HEAD and (r.font.name or "").startswith(HEAD)):
            r.font.name = name
        if floor and r.font.size is not None and r.font.size.pt < MIN:
            r.font.size = Pt(MIN)


def _is_title_ph(sh):
    if PP_PLACEHOLDER is None or not sh.is_placeholder:
        return None
    try:
        t = sh.placeholder_format.type
    except Exception:
        return None
    if t in (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE, PP_PLACEHOLDER.VERTICAL_TITLE):
        return True
    if t == PP_PLACEHOLDER.SUBTITLE:
        return False
    return None


# The KPI label under the figure on Product Mix and Excluded Accounts stays at its own 12 pt so the callout
# subtext matches on both slides (build/shapes.py SMALL_TILE_LABEL; tests pin that the two agree).
SMALL_TILE_LABEL = "KPI label (small)"


def _restyle_shape(sh, floor):
    if sh.name == SMALL_TILE_LABEL:
        floor = False
    # recurse groups
    if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
        for c in sh.shapes:
            _restyle_shape(c, floor)
        return
    if sh.has_table:
        for row in sh.table.rows:
            for c in row.cells:
                _apply(_runs(c.text_frame), BODY, floor=floor)
        return
    if not sh.has_text_frame:
        return
    rs = _runs(sh.text_frame)
    if not rs:
        return
    if sh.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE:
        name = HEAD                      # callout / pill / chip / badge / card
    else:
        ph = _is_title_ph(sh)
        if ph is True:
            name = HEAD
        elif ph is False:
            name = BODY
        else:
            mx = max((r.font.size.pt for r in rs if r.font.size is not None), default=0)
            top = Emu(sh.top).inches if sh.top is not None else 99
            words = len("".join(r.text for r in rs).split())
            if words >= 12:
                name = BODY          # long prose is body text, never a heading (even if large)
            else:
                name = HEAD if (mx >= HEAD_SIZE or (mx == 0 and top < 1.3)) else BODY
    _apply(rs, name, floor=floor)


def _is_summit(slide):
    """The Executive Summit slide keeps its own dense typography — never restyle it."""
    for sh in slide.shapes:
        if sh.has_text_frame:
            t = sh.text_frame.text
            if "Executive Summit" in t or "About the Summit" in t:
                return True
    return False


def _is_mrpc(prs):
    """MRPC decks carry a deliberate 10-15 pt size hierarchy (footnotes, tier
    sublabels, KPI labels, panel headings, date pill). Flooring those at 16 pt
    flattens the hierarchy and collides bottom captions with the page number, so
    MRPC decks keep their template sizes (names are still set by role). Detected by
    content so it works regardless of filename."""
    for s in prs.slides:
        for sh in s.shapes:
            if sh.has_text_frame:
                t = sh.text_frame.text
                if "MyRewards Premium Cards" in t or "MRPC" in t:
                    return True
    return False


def _strip_empty_placeholders(slide):
    """Remove unfilled layout placeholders so PowerPoint doesn't show
    'Click to add title / text' prompts in edit view. Filled placeholders are kept."""
    for ph in list(slide.placeholders):
        if not (ph.has_text_frame and ph.text_frame.text.strip()):
            ph._element.getparent().remove(ph._element)

def restyle(path):
    prs = Presentation(path)
    mrpc = _is_mrpc(prs)                    # MRPC keeps its deliberate 10-15pt hierarchy
    for s in prs.slides:
        _strip_empty_placeholders(s)
        if _is_summit(s):
            continue                       # slide owns its fonts + spacing; leave untouched
        dense = _title(s).startswith(("2026 New Releases", "Product Mix",
                                      "Program Results by Month Opened",
                                      "Program Results by Opening Year",
                                      "Referred Accounts by Product"))
        for sh in s.shapes:
            tdense = sh.has_table and sh.name == BRANCH_DETAIL_TABLE
            _restyle_shape(sh, floor=not dense and not tdense and not mrpc)
    prs.save(path)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        restyle(p)
        print("restyled", p)
