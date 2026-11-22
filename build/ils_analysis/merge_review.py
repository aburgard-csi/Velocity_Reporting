"""Assemble a client's ILS review from the ILS Program Analysis deck (built without its own matrix section) and:

  - the ILS prep build's slides (recap, matrix updates, tickets, client and industry update, program detail, fee
    schedule) as HIDDEN slides right after the cover: context for the presenter, not shown in a slide show and not
    printed (Aaron, 2026-11-20: "Build the ILS prep slides as hidden slides at the front of the deck so they don't
    print or show when we display, but they will give us context");
  - the prep build's Matrix Parameters / Matrix Overrides slides, VISIBLE, at the start of the risk analysis for each
    account type ("I like the matrix slides at the beginning of the risk analysis for personal or business"): before
    the first Scoring Summary slide of that type, or after the Appendix divider when the deck has no risk analysis
    for it (an account type with no notices in the window builds none);
  - optionally the CashPlease module's section (divider and content slides), before Thank You.

Slides are only ever ADDED, then moved (never deleted), so no partname is reused (CLAUDE.md). Page numbers are
renumbered over the visible slides only, so the shown deck runs 1, 2, 3 with the hidden context slides skipped.

    python merge_review.py <ils.pptx> --prep <prep.pptx> [--cp <cp.pptx>] --out <out.pptx> [--repo <checkout>]
"""
import argparse
import copy
import io
import os
import sys

from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.util import Inches

MATRIX_TITLES = ("Matrix Parameters", "Matrix Overrides")
RISK_TITLES = ("scoring summary",)             # the first slide of each account type's risk analysis
APPENDIX_DIVIDER = "Appendix and Matrix Validation"


def title(sl):
    for sh in sl.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            return sh.text_frame.text.strip().split("\n")[0]
    return ""


def text(sl):
    return " ".join(sh.text_frame.text for sh in sl.shapes if sh.has_text_frame)


def is_hidden(sl):
    return sl._element.get("show") == "0"


def hide(sl):
    sl._element.set("show", "0")


def layout(prs, name):
    for m in prs.slide_masters:
        for lay in m.slide_layouts:
            if lay.name == name:
                return lay
    for m in prs.slide_masters:
        for lay in m.slide_layouts:
            if lay.name.lower() == "blank":
                return lay
    return prs.slide_layouts[len(prs.slide_layouts) - 1]


def copy_slide(src, dst_prs):
    """build/assemble_combined.copy_slide, plus external hyperlinks re-created in the destination."""
    dst = dst_prs.slides.add_slide(layout(dst_prs, src.slide_layout.name))
    for sh in list(dst.shapes):
        sh._element.getparent().remove(sh._element)
    for el in list(src.shapes._spTree):
        if el.tag in (qn("p:nvGrpSpPr"), qn("p:grpSpPr")):
            continue
        dst.shapes._spTree.append(copy.deepcopy(el))
    for blip in dst.shapes._spTree.iter(qn("a:blip")):
        rid = blip.get(qn("r:embed"))
        if rid:
            _part, new = dst.part.get_or_add_image_part(io.BytesIO(src.part.related_part(rid).blob))
            blip.set(qn("r:embed"), new)
    for tag in ("a:hlinkClick", "a:hlinkHover"):
        for h in dst.shapes._spTree.iter(qn(tag)):
            rid = h.get(qn("r:id"))
            if rid and rid in src.part.rels and src.part.rels[rid].is_external:
                h.set(qn("r:id"), dst.part.relate_to(src.part.rels[rid].target_ref, RT.HYPERLINK, is_external=True))
            elif rid:
                h.attrib.pop(qn("r:id"), None)
    if src.has_notes_slide and src.notes_slide.notes_text_frame.text.strip():
        dst.notes_slide.notes_text_frame.text = src.notes_slide.notes_text_frame.text
    return dst


def _el(prs, slide):
    return next(e for e in prs.slides._sldIdLst if int(e.get("id")) == slide.slide_id)


def move_to(prs, slides, pos):
    """Move `slides` (in order) so the first sits at index `pos` of the deck as it stands without them."""
    lst = prs.slides._sldIdLst
    els = [_el(prs, s) for s in slides]
    for e in els:
        lst.remove(e)
    for k, e in enumerate(els):
        lst.insert(pos + k, e)


def index_of(prs, slide):
    return list(prs.slides._sldIdLst).index(_el(prs, slide))


def account_type(sl):
    """Personal or Business when the slide names exactly one of them (any case: the analysis deck writes "Open
    personal accounts", the prep build "Personal Accounts"), else None."""
    t = text(sl).lower()
    bus, per = "business" in t, "personal" in t
    if bus and not per:
        return "Business"
    if per and not bus:
        return "Personal"
    return None


def risk_anchor(prs, acct, exclude):
    """The first visible Scoring Summary slide of this account type, or None."""
    for s in prs.slides:
        if s.slide_id in exclude or is_hidden(s):
            continue
        if title(s).lower().startswith(RISK_TITLES) and account_type(s) == acct:
            return s
    return None


def renumber_visible(prs):
    """Update the page numbers the slides already carry, counting visible slides only; never add one."""
    n = 0
    for s in prs.slides:
        if is_hidden(s):
            continue
        n += 1
        for sh in s.shapes:
            if (sh.has_text_frame and sh.top is not None and sh.top > Inches(6.8) and sh.left is not None
                    and sh.left < Inches(1.2)):
                t = sh.text_frame.text.strip()
                if t.isdigit() and sh.text_frame.paragraphs[0].runs:
                    sh.text_frame.paragraphs[0].runs[0].text = str(n)
                    break


def merge(ils_p, prep_p, out_p, cp_p=None):
    ils, prep = Presentation(ils_p), Presentation(prep_p)
    matrix = [s for s in prep.slides if title(s).startswith(MATRIX_TITLES)]
    context = [s for s in prep.slides if not title(s).startswith(MATRIX_TITLES)]

    # hidden context slides right after the cover
    new_context = [copy_slide(s, ils) for s in context]
    for s in new_context:
        hide(s)
    move_to(ils, new_context, 1)

    # visible matrix slides at the start of each account type's risk analysis
    placed = {}
    added = {s.slide_id for s in new_context}
    for acct in ("Personal", "Business"):
        mine = [s for s in matrix if account_type(s) == acct]
        if not mine:
            continue
        new = [copy_slide(s, ils) for s in mine]
        added |= {s.slide_id for s in new}
        anchor = risk_anchor(ils, acct, added)
        if anchor is not None:
            move_to(ils, new, index_of(ils, anchor))
            placed[acct] = f"before '{title(anchor)}'"
        else:
            div = next((s for s in ils.slides if title(s).startswith(APPENDIX_DIVIDER)), None)
            move_to(ils, new, index_of(ils, div) + 1 if div is not None else len(ils.slides._sldIdLst))
            placed[acct] = "after the Appendix divider (no risk analysis for this account type)"

    new_cp = []
    if cp_p:
        cp = Presentation(cp_p)
        start = next(i for i, s in enumerate(cp.slides) if i > 0 and title(s).startswith("CashPlease"))
        sec = [s for i, s in enumerate(cp.slides) if i >= start and not title(s).startswith(("Questions", "Contact Us"))]
        new_cp = [copy_slide(s, ils) for s in sec]
        thanks = next(s for s in ils.slides if title(s).startswith("Thank You"))
        move_to(ils, new_cp, index_of(ils, thanks))

    renumber_visible(ils)
    ils.save(out_p)
    return {"hidden": len(new_context), "matrix": placed, "cashplease": len(new_cp), "slides": len(ils.slides),
            "visible": sum(1 for s in ils.slides if not is_hidden(s))}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("ils")
    ap.add_argument("--prep", required=True)
    ap.add_argument("--cp")
    ap.add_argument("--out", required=True)
    ap.add_argument("--repo", help="checkout whose build/ holds shapes.py (unused; kept for the old call form)")
    a = ap.parse_args(argv)
    if os.path.abspath(a.out) == os.path.abspath(a.ils):
        ap.error("--out must differ from the input deck")
    r = merge(a.ils, a.prep, a.out, a.cp)
    print(f"{r['hidden']} hidden prep slide(s) after the cover; matrix: {r['matrix']}; {r['cashplease']} CashPlease "
          f"slide(s); {r['visible']} visible of {r['slides']} slides -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
