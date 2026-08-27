#!/usr/bin/env python3
"""Assemble a combined ARS + ICS + MRPC Executive Review from the three finished
per-program decks.

Target order is the canonical combined reference (templates/multi-product_reference_deck.pptx,
79 slides) — see templates/TEMPLATES.md:

    1-3    shared shell: Title, About the Summit, Agenda      (from the ARS deck, adapted)
    4-30   ARS section: divider .. ARS Key Takeaways          (ARS deck 4-30)
    31-53  ICS section: divider, content, education/reference (ICS deck 3, 5-26)
    54-62  MRPC section: divider .. MRPC Key Metrics          (MRPC deck 3-11)
    63-64  Questions & Discussion, Contact Us                 (ARS deck 31-32)
    65-79  ARS Appendix                                       (ARS deck 33-47)

Each program deck's own title / Summit / agenda / Q&A / Contact slides are dropped so the
combined deck carries exactly one of each.

WHY THIS IS WRITTEN THE WAY IT IS — slides are only ever ADDED to the base package and then
REORDERED; nothing is deleted. Removing slides frees their partnames, python-pptx hands those
freed numbers to slides added afterwards, and parts end up referenced twice in sldIdLst. That
is the defect that shipped seven 2026.08 ICS decks which validated at 0 FAIL and would not
open in LibreOffice (see the comment in build/ics_pipeline/build_ics_gen.py and CLAUDE.md
rule 3). Package integrity is re-checked by validation/qa_all.py after this runs.

Usage:
    assemble_combined.py <ars.pptx> <ics.pptx> <mrpc.pptx> <out.pptx>
"""
import copy, io, os, sys

from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE

# Self-locating: this file lives in build/, next to the shared post-processors it imports
# (fit_layout). Never hardcode a machine path here — see build/rpe_env.py.
BUILDDIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BUILDDIR)

ARS, ICS, MRPC, OUT = sys.argv[1:5]

# Sections to lift out of each program deck (1-based, inclusive), mirroring the reference.
ICS_KEEP = [3] + list(range(5, 27))    # divider + content + education/reference; drops ICS agenda
MRPC_KEEP = list(range(3, 12))         # divider .. MRPC Key Metrics
ARS_HEAD = 30                          # ARS deck slides 1..30 stay ahead of the ICS section

# Canonical combined shell text (from templates/multi-product_reference_deck.pptx).
PRODUCT_LINES = ["Account Revenue Solution®",
                 "Invitation Checking® System",
                 "MyRewards Premium Cards®"]
AGENDA = [("1", "Account Revenue Solution®",
           "Program performance, mailing insights, debit card & Reg E review"),
          ("2", "Invitation Checking® System",
           "Referral trend, account value, ROI & financial results"),
          ("3", "MyRewards Premium Cards®",
           "Enrollments, channel mix, retention & revenue"),
          ("4", "Questions & Discussion", None)]


# ---------------------------------------------------------------- cross-package slide copy
def _layout_by_name(prs, name):
    """Match the source layout by name. All three decks descend from one reference deck, so
    the layout sets are identical; falling back to BLANK would silently drop the inherited
    formatting that placeholder shapes rely on."""
    for master in prs.slide_masters:
        for lay in master.slide_layouts:
            if lay.name == name:
                return lay
    for master in prs.slide_masters:
        for lay in master.slide_layouts:
            if lay.name == "BLANK":
                return lay
    raise SystemExit(f"no layout {name!r} and no BLANK fallback in the target package")


def copy_slide(src, dst_prs):
    """Append a deep copy of `src` to `dst_prs` and return the new slide."""
    dst = dst_prs.slides.add_slide(_layout_by_name(dst_prs, src.slide_layout.name))

    # add_slide() materializes the layout's placeholders; the source spTree carries its own
    # copies of everything, so clear them first or every placeholder appears twice.
    for sh in list(dst.shapes):
        sh._element.getparent().remove(sh._element)

    for el in list(src.shapes._spTree):
        if el.tag in (qn("p:nvGrpSpPr"), qn("p:grpSpPr")):
            continue                      # group properties belong to the destination spTree
        dst.shapes._spTree.append(copy.deepcopy(el))

    # Re-embed every image into the destination package and remap its r:embed. Copying the
    # XML alone leaves rIds pointing at relationships that do not exist here.
    for blip in dst.shapes._spTree.iter(qn("a:blip")):
        rid = blip.get(qn("r:embed"))
        if not rid:
            continue
        blob = src.part.related_part(rid).blob
        _part, new_rid = dst.part.get_or_add_image_part(io.BytesIO(blob))
        blip.set(qn("r:embed"), new_rid)

    # Speaker notes are a hard requirement (CLAUDE.md: every slide names its data source).
    if src.has_notes_slide:
        txt = src.notes_slide.notes_text_frame.text
        if txt.strip():
            dst.notes_slide.notes_text_frame.text = txt
    return dst


# ---------------------------------------------------------------- shell adaptation
def set_title_products(slide):
    """Title slide lists exactly the included products (templates/STYLE.md)."""
    for sh in slide.shapes:
        if not sh.has_text_frame:
            continue
        if "Account Revenue Solution" not in sh.text_frame.text:
            continue
        tf = sh.text_frame
        p0 = tf.paragraphs[0]
        run = p0.runs[0]
        run.text = PRODUCT_LINES[0]
        for r in p0.runs[1:]:
            r.text = ""
        for extra in tf.paragraphs[1:]:
            extra._p.getparent().remove(extra._p)
        for line in PRODUCT_LINES[1:]:
            np = copy.deepcopy(p0._p)
            p0._p.getparent().append(np)
            from pptx.text.text import _Paragraph
            par = _Paragraph(np, tf)
            par.runs[0].text = line
            for r in par.runs[1:]:
                r.text = ""
        return True
    return False


def set_agenda(slide):
    """Rewrite the ARS-only agenda into the three-program agenda, in place.

    Matched positionally: the agenda is a fixed 4-row grid of (number, heading, detail)
    text boxes, so the boxes are taken in document order rather than by their current text
    (which differs between the ARS deck and the reference)."""
    # The slide-number box is excluded by GEOMETRY, not by its text: on this deck it reads
    # "3", which is indistinguishable from the agenda's own row numbers.
    boxes = [sh for sh in slide.shapes
             if sh.has_text_frame and sh.text_frame.text.strip()
             and sh.text_frame.text.strip() != "Agenda"
             and not _is_numbox(sh)]
    rows, i = [], 0
    while i < len(boxes):
        t = boxes[i].text_frame.text.strip()
        if t in ("1", "2", "3", "4"):
            head = boxes[i + 1] if i + 1 < len(boxes) else None
            det = boxes[i + 2] if i + 2 < len(boxes) else None
            if det is not None and det.text_frame.text.strip() in ("1", "2", "3", "4"):
                det = None
            rows.append((boxes[i], head, det))
            i += 2 if det is None else 3
        else:
            i += 1
    if len(rows) != 4:
        raise SystemExit(f"agenda grid: expected 4 rows, found {len(rows)} — template changed")

    def _settext(shape, text):
        tf = shape.text_frame
        p = tf.paragraphs[0]
        if not p.runs:
            p.add_run()
        p.runs[0].text = text
        for r in p.runs[1:]:
            r.text = ""
        for extra in tf.paragraphs[1:]:
            extra._p.getparent().remove(extra._p)

    for (numbox, head, det), (n, title, detail) in zip(rows, AGENDA):
        _settext(numbox, n)
        if head is not None:
            _settext(head, title)
        if det is not None:
            _settext(det, detail if detail else "")
    return True


# ---------------------------------------------------------------- branding / renumber
# Mirrors the final branding pass in build/ars_pipeline/build_ars_gen.py (STYLE.md geometry,
# Aaron 2026-07-24): Calibri 10pt bold navy bottom-left; no number on title / Summit /
# section-heading slides. Logos are already correct on every source slide, so only the
# numbers are redone here.
NUM_LTWH = (0.45, 7.05, 0.70, 0.30)
NUM_PT = 10
NAVY = RGBColor(0x00, 0x27, 0x4C)


def _emi(v):
    return Emu(v).inches if v is not None else None


def _is_numbox(sh):
    if not sh.has_text_frame or None in (sh.left, sh.top, sh.width):
        return False
    return (sh.text_frame.text.strip().isdigit()
            and _emi(sh.top) > 6.5 and _emi(sh.left) < 1.7 and _emi(sh.width) < 1.4)


def _bigfont(sl):
    return max([(r.font.size.pt if r.font.size else 0)
                for sh in sl.shapes if sh.has_text_frame
                for p in sh.text_frame.paragraphs for r in p.runs] + [0])


def _is_logo_pic(sh):
    if sh.shape_type != MSO_SHAPE_TYPE.PICTURE:
        return False
    return (_emi(sh.width) or 9) < 3.15 and (_emi(sh.height) or 9) < 1.2


def _has_topleft_logo(sl):
    return any(_is_logo_pic(sh) and (_emi(sh.left) or 9) < 2.0 and (_emi(sh.top) or 9) < 2.0
               for sh in sl.shapes)


def renumber(prs):
    """Renumber sequentially, preserving each slide's own numbered/unnumbered status.

    Which slides carry a number is decided by the per-program builders (STYLE.md: none on
    title / Summit / section headings) and every source slide arrives here already branded,
    numbox included. So the source's own decision is the authority.

    Do NOT re-derive it from a font-size heuristic: ">=44pt means section heading" is true
    for the ARS deck but strips the number off four legitimately-numbered data slides —
    ICS "The Power of Referrals" and "ICS Financial Summary" (44pt), MRPC "Card Portfolio"
    and "Key Metrics" (46pt), all of which carry 44pt+ KPI text.
    """
    slides = list(prs.slides)
    had = [any(_is_numbox(sh) for sh in s.shapes) for s in slides]
    for i, sl in enumerate(slides):
        for sh in list(sl.shapes):
            if _is_numbox(sh):
                sh._element.getparent().remove(sh._element)
        if not had[i]:
            continue
        tb = sl.shapes.add_textbox(*[Inches(v) for v in NUM_LTWH])
        r = tb.text_frame.paragraphs[0].add_run()
        r.text = str(i + 1)
        r.font.name = "Calibri"
        r.font.size = Pt(NUM_PT)
        r.font.bold = True
        r.font.color.rgb = NAVY


# ---------------------------------------------------------------- assemble
def main():
    prs = Presentation(ARS)
    n_ars = len(prs.slides._sldIdLst)
    if n_ars != 47:
        print(f"note: ARS deck has {n_ars} slides (expected 47) — section split still uses "
              f"the first {ARS_HEAD} slides and the remainder as closing+appendix")

    src_ics = list(Presentation(ICS).slides)
    src_mrpc = list(Presentation(MRPC).slides)

    # ICS financials are QUARTERLY (CLAUDE.md cadence): between workbooks an ICS build carries
    # the previous workbook's financial sections forward unchanged, so the ICS section of a
    # combined deck can legitimately report an older month than ARS/MRPC. That is not an error
    # and must not be "corrected" — the per-slide source notes name the workbook and period,
    # which is what keeps a carried-forward figure auditable. It IS worth seeing, so report
    # each section's period rather than silently presenting one reporting month for all three.
    for label, slides in (("ARS", list(prs.slides)), ("ICS", src_ics), ("MRPC", src_mrpc)):
        per = next((sh.text_frame.text.strip().split("•")[-1].strip()
                    for sh in slides[0].shapes
                    if sh.has_text_frame and "•" in sh.text_frame.text), "?")
        print(f"  {label} section period: {per}")

    added = 0
    for n in ICS_KEEP:
        copy_slide(src_ics[n - 1], prs)
        added += 1
    for n in MRPC_KEEP:
        copy_slide(src_mrpc[n - 1], prs)
        added += 1
    print(f"copied {added} slides ({len(ICS_KEEP)} ICS + {len(MRPC_KEEP)} MRPC)")

    # Reorder: ARS head, then the copied sections, then the ARS closing + appendix.
    lst = prs.slides._sldIdLst
    els = list(lst)
    assert len(els) == n_ars + added, "slide count drifted during copy"
    head, tail, new = els[:ARS_HEAD], els[ARS_HEAD:n_ars], els[n_ars:]
    for el in els:
        lst.remove(el)
    for el in head + new + tail:
        lst.append(el)
    assert len(list(lst)) == len(els), "reorder changed the slide count"
    assert len({id(e) for e in lst}) == len(els), "a slide is referenced twice"

    slides = list(prs.slides)
    if not set_title_products(slides[0]):
        raise SystemExit("MISS: title slide product line not found — cannot label the deck")
    set_agenda(slides[2])
    renumber(prs)

    import fit_layout
    fit_layout.fit(prs)
    prs.save(OUT)
    print(f"built {OUT} -> {len(prs.slides._sldIdLst)} slides")


main()
