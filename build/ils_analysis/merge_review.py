"""Assemble Dannemora FCU's ILS review: the ILS Program Analysis deck (built without its matrix section), plus
  - the ILS prep build's Program Detail and Published Fee Schedule slides, after the Program Performance divider;
  - the ILS prep build's Matrix Parameters / Overrides slides, after the Appendix divider;
  - the CashPlease module's section (divider and content slides), before Thank You / Questions.
Slides are only ever ADDED, then moved (never deleted), so no partname is reused (CLAUDE.md).

    python merge_deck.py <ils.pptx> <prep.pptx> <cp.pptx> <out.pptx>
"""
import copy
import io
import sys

from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.opc.constants import RELATIONSHIP_TYPE as RT

REPO = sys.argv[5] if len(sys.argv) > 5 else None
if REPO:
    sys.path[:0] = [REPO + r"\build"]
import shapes  # noqa: E402

ils_p, prep_p, cp_p, out_p = sys.argv[1:5]
ils, prep, cp = Presentation(ils_p), Presentation(prep_p), Presentation(cp_p)


def title(sl):
    for sh in sl.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            return sh.text_frame.text.strip().split("\n")[0]
    return ""


def layout(prs, name):
    for m in prs.slide_masters:
        for lay in m.slide_layouts:
            if lay.name == name:
                return lay
    for m in prs.slide_masters:
        for lay in m.slide_layouts:
            if lay.name.lower() in ("blank", "BLANK".lower()):
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


def move_after(prs, slides, anchor_title, before=False):
    lst = prs.slides._sldIdLst
    ids = {s.slide_id: e for e in lst for s in prs.slides if int(e.get("id")) == s.slide_id}
    anchor = next(s for s in prs.slides if title(s).startswith(anchor_title))
    a_el = next(e for e in lst if int(e.get("id")) == anchor.slide_id)
    pos = list(lst).index(a_el) + (0 if before else 1)
    els = [next(e for e in lst if int(e.get("id")) == s.slide_id) for s in slides]
    for e in els:
        lst.remove(e)
    for k, e in enumerate(els):
        lst.insert(pos + k, e)


prep_titles = [title(s) for s in prep.slides]
detail = [s for s in prep.slides if title(s).startswith(("Program Detail", "Published Fee Schedule"))]
matrix = [s for s in prep.slides if title(s).startswith(("Matrix Parameters", "Matrix Overrides"))]
cp_from = next(i for i, s in enumerate(cp.slides) if i > 0 and title(s).startswith("CashPlease"))   # the section divider
cp_sec = [s for i, s in enumerate(cp.slides) if i >= cp_from and not title(s).startswith(("Questions", "Contact Us"))]

new_detail = [copy_slide(s, ils) for s in detail]
new_matrix = [copy_slide(s, ils) for s in matrix]
new_cp = [copy_slide(s, ils) for s in cp_sec]
move_after(ils, new_detail, "Program Performance")
move_after(ils, new_matrix, "Appendix and Matrix Validation")
move_after(ils, new_cp, "Thank You", before=True)
def renumber_existing(prs):
    """Update the page numbers the slides already carry; never add one. The prep slides are designed without a
    number (a number added there sat on the last talking point), and the dividers have none."""
    from pptx.util import Inches
    for n, s in enumerate(prs.slides, 1):
        for sh in s.shapes:
            if (sh.has_text_frame and sh.top is not None and sh.top > Inches(6.8) and sh.left is not None
                    and sh.left < Inches(1.2)):
                t = sh.text_frame.text.strip()
                if t.isdigit() and sh.text_frame.paragraphs[0].runs:
                    sh.text_frame.paragraphs[0].runs[0].text = str(n)
                    break


renumber_existing(ils)
ils.save(out_p)
print(f"added {len(new_detail)} program-detail, {len(new_matrix)} matrix, {len(new_cp)} CashPlease slides -> "
      f"{len(ils.slides)} slides")
for i, s in enumerate(ils.slides, 1):
    print(i, "|", title(s)[:70])
