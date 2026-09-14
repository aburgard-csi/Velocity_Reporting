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

# Which deck supplies the shared shell — cover, Executive Summit, agenda — plus
# Questions & Contact. It used to be ARS, always, and `--ars` was required.
#
# CashPlease made that untenable: 1632 WesBanco and 1734 Altamaha are ICS + CashPlease
# and have no ARS at all, so requiring ARS meant they could have no combined deck
# (Aaron, 2026-09-01). Nothing had to move out of the ARS deck to fix it — every program
# deck already builds its own cover/Summit/agenda/Q&A/Contact and `section_slides()`
# drops them when that deck becomes a section. So this is a precedence rule, and the
# first program present supplies the shell.
#
# MRPC is last because it is the one deck with NO agenda and no Summit slide (12 slides:
# content, then Questions and Contact), so it cannot supply a shell. It only reaches the
# front of this list for an MRPC-only deck, which is not a combined deck at all.
BASE_PRECEDENCE = ("ARS", "ICS", "CP", "MRPC")
_ARG = {"ARS": "ars", "ICS": "ics", "MRPC": "mrpc", "CP": "cashplease"}

def _args():
    import argparse
    ap = argparse.ArgumentParser(description="Assemble a combined multi-product Executive Review.")
    ap.add_argument("--ars", help="ARS deck. Supplies the shared shell, Questions/Contact "
                                  "and the Appendix when present — but is no longer required")
    ap.add_argument("--ics")
    ap.add_argument("--mrpc")
    ap.add_argument("--cashplease", help="CashPlease deck")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    given = [p for p in BASE_PRECEDENCE if getattr(a, _ARG[p])]
    if len(given) < 2:
        ap.error("a combined deck needs at least two of --ars / --ics / --mrpc / --cashplease")
    return a


# Parsed inside main(), not at import. At module scope this made
# `import assemble_combined` call argparse and exit the process with
# SystemExit(2), so the pure helpers below could not be unit-tested at all —
# which is why the highest-risk file in the repo, downstream of all three
# pipelines, had every one of its four regressions found in a delivered deck.
_A = None
ARS = ICS = MRPC = OUT = None


def _init_args():
    global _A, ARS, ICS, MRPC, CP, OUT
    _A = _args()
    ARS, ICS, MRPC, CP, OUT = _A.ars, _A.ics, _A.mrpc, _A.cashplease, _A.out
    return _A

# The ARS section ends at "ARS Key Takeaways"; everything after it is the closing
# block (Q&A, Contact) plus the Appendix. This was the fixed index 30, which is only
# right while the ARS deck is exactly 47 slides. Adding the Excluded Accounts and Reg E
# by Branch slides made it 49, and the boundary then cut two slides early: "Reg E Opt-In
# by Account Vintage" and "ARS Key Takeaways" were pushed AFTER the ICS section
# (Aaron, 2026-08-28). Resolve by TITLE — CLAUDE.md: never by index.
ARS_HEAD_FALLBACK = 30
ARS_SECTION_END_TITLE = "ARS Key Takeaways"


def _ars_head(prs):
    """Index of the first slide AFTER the ARS section, resolved by title."""
    for i, sl in enumerate(prs.slides, 1):
        for sh in sl.shapes:
            if (sh.has_text_frame
                    and sh.text_frame.text.strip().startswith(ARS_SECTION_END_TITLE)):
                return i
    print(f"!! assemble_combined: '{ARS_SECTION_END_TITLE}' not found in the ARS deck — "
          f"falling back to the fixed index {ARS_HEAD_FALLBACK}. If the ARS deck has "
          f"changed length this WILL misplace slides; check the section order.")
    return ARS_HEAD_FALLBACK

CLOSING_TITLE = "Questions & Discussion"


def _head_end(prs, base):
    """Index of the last slide of the BASE program's own section.

    ARS keeps its own resolver, unchanged: its section ends at "ARS Key Takeaways" and
    the Appendix sits after Contact, so the boundary is not simply "before Questions".
    Every other base ends its section where the closing block starts. Both are resolved
    by TITLE — never by index (CLAUDE.md).
    """
    if base == "ARS":
        return _ars_head(prs)
    for i, sl in enumerate(prs.slides, 1):
        title = next((sh.text_frame.text.strip().splitlines()[0] for sh in sl.shapes
                      if sh.has_text_frame and sh.text_frame.text.strip()), "")
        if title.startswith(CLOSING_TITLE):
            return i - 1
    raise SystemExit(f"the {base} deck has no '{CLOSING_TITLE}' slide, so it cannot "
                     f"supply the closing block for a combined deck.")


def _slide_by_title(prs, prefix, what):
    """The one slide whose title starts with `prefix`.

    The agenda used to be taken as `slides[2]`. That is true of an ARS deck and false of
    an ICS one, whose agenda is slide 4 — the divider sits at 3. A non-ARS base would
    have rewritten the divider as an agenda.
    """
    for sl in prs.slides:
        title = next((sh.text_frame.text.strip().splitlines()[0] for sh in sl.shapes
                      if sh.has_text_frame and sh.text_frame.text.strip()), "")
        if title.startswith(prefix):
            return sl
    raise SystemExit(f"no {what} slide found in the base deck (looked for a title "
                     f"starting {prefix!r}).")


# Slides dropped from a program deck when it becomes a SECTION of the combined deck: the
# combined deck carries exactly one cover, Summit, agenda, Q&A and Contact, all from ARS.
# Selected by exclusion rather than by fixed index — a program deck's length is not fixed
# (an ICS deck with no workbook yet is 13 slides, not 28), and CLAUDE.md's rule is to
# resolve slides by meaning, never by position.
SECTION_DROP_TITLES = ("Agenda", "Questions & Discussion", "Contact Us")


def _slide_text(sl):
    return " ".join(sh.text_frame.text for sh in sl.shapes if sh.has_text_frame).lower()


def _is_cover(sl):
    """The program cover — the only slide carrying the 'Executive Review' line."""
    return "executive review" in _slide_text(sl)


def _is_summit(sl, n):
    """The Executive Summit slide.

    ARS carries it as text; ICS carries it as a full-bleed image with no text at
    all. Both sit in the opening block, so an untitled slide in the first three
    is the image form. MRPC has NO summit slide.
    """
    t = _slide_text(sl)
    if "executive summit" in t or "summit is complimentary" in t:
        return True
    return n <= 3 and not t.strip()


def section_slides(slides):
    """Indices (1-based) of the slides that form this program's section.

    Resolved by MEANING, not position (CLAUDE.md rule). This used to drop
    indices 1 and 2 outright on the assumption that every deck opens with
    cover + Executive Summit. ARS and ICS do; MRPC does NOT — its divider sits
    at index 2, so the positional rule silently deleted the MRPC divider and the
    combined deck ran from the ICS section straight into MRPC content with no
    section break at all (Aaron, 2026-08-29).

    The cover and the divider share a title, which is why position was reached
    for — but they are distinguishable: the cover carries the "Executive Review"
    line and the divider carries the program's benefits line.
    """
    keep = []
    for n, s in enumerate(slides, 1):
        if _is_cover(s) or _is_summit(s, n):
            continue
        title = next((sh.text_frame.text.strip().split("\n")[0]
                      for sh in s.shapes
                      if sh.has_text_frame and sh.text_frame.text.strip()), "")
        if title.startswith(SECTION_DROP_TITLES):
            continue
        keep.append(n)
    return keep

# Canonical combined shell text (from templates/multi-product_reference_deck.pptx). Only the
# programs actually present are listed — STYLE.md: the title slide names the included products,
# so a two-program client must not advertise a section the deck does not contain.
PRODUCT_NAME = {"ARS": "Account Revenue Solution®",
                "ICS": "Invitation Checking® System",
                "MRPC": "MyRewards Premium Cards®",
                "CP": "CashPlease®"}
AGENDA_DETAIL = {"ARS": "Program performance, mailing insights, debit card & Reg E review",
                 "ICS": "Referral trend, account value, ROI & financial results",
                 "MRPC": "Enrollments, channel mix, retention & revenue",
                 "CP": "Loan volume, portfolio status & peer comparison"}

# A referrals-only ICS build has no account-value, ROI or financial slides at all, so the
# combined agenda must not name them — the same rule the ICS deck's own agenda follows
# (Aaron, 2026-08-28). Detected from the slides actually copied, not from a flag, so the
# agenda can never describe a section the deck does not contain.
AGENDA_DETAIL_ICS_REFERRALS = "Referral trend, results by branch & VIP resources"
ICS_WORKBOOK_TITLES = ("Performance of ICS Accounts", "ICS Revenue",
                       "ICS Financial Summary", "Value of ICS")


def _ics_is_referrals_only(slides):
    for sl in slides:
        for sh in sl.shapes:
            if sh.has_text_frame:
                t = sh.text_frame.text.strip()
                if any(t.startswith(x) for x in ICS_WORKBOOK_TITLES):
                    return False
    return True


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
def set_title_products(slide, programs):
    """Title slide lists exactly the included products (templates/STYLE.md)."""
    product_lines = [PRODUCT_NAME[p] for p in programs]
    for sh in slide.shapes:
        if not sh.has_text_frame:
            continue
        # The base deck's cover carries ITS OWN product name — "Invitation Checking®
        # System" on an ICS base, "CashPlease®" on a CashPlease one. Matching only the
        # ARS string found nothing and the deck shipped unlabelled.
        if not any(n.rstrip("®") in sh.text_frame.text for n in PRODUCT_NAME.values()):
            continue
        tf = sh.text_frame
        p0 = tf.paragraphs[0]
        run = p0.runs[0]
        run.text = product_lines[0]
        for r in p0.runs[1:]:
            r.text = ""
        for extra in tf.paragraphs[1:]:
            extra._p.getparent().remove(extra._p)
        for line in product_lines[1:]:
            np = copy.deepcopy(p0._p)
            p0._p.getparent().append(np)
            from pptx.text.text import _Paragraph
            par = _Paragraph(np, tf)
            par.runs[0].text = line
            for r in par.runs[1:]:
                r.text = ""
        _fit_product_lines(sh, len(product_lines))
        return True
    return False


def _fit_product_lines(shape, n_lines):
    """Shrink the cover's product lines ONLY when they cannot fit the box at their own size.

    The shell's product box is 2.0" deep at 40pt, which seats three products - every
    combined deck until 2026-09-14. Marine FCU's ARS-ICS-MRPC-CP cover was the first with
    four: the lines ran about 2.7" deep and drew over the client name beneath them, and
    the gate failed it. Two- and three-product covers keep exactly the template's 40pt,
    so no existing deck changes.
    """
    import math
    from pptx.util import Emu, Pt
    runs = [r for p in shape.text_frame.paragraphs for r in p.runs]
    size = next((r.font.size.pt for r in runs if r.font.size), None)
    if not size or shape.height is None:
        return
    box = Emu(shape.height).pt
    if n_lines * size * 1.2 <= box:          # 3 x 40pt x 1.2 = 144pt = the 2.0" box exactly
        return
    new = math.floor(box / (n_lines * 1.25))  # a little looser than the fit test, for glyph ascent
    for r in runs:
        r.font.size = Pt(new)


ROW_TOKENS = tuple(str(i) for i in range(1, 10))


def _badge_of(slide, numbox):
    """The decorative circle under a row's number.

    Each badge is TWO stacked shapes: an AUTO_SHAPE carrying no text and the number
    drawn on top of it. The circle has to travel with its row, or re-spacing leaves it
    behind as an orphan bullet — the Wellworth 1549 defect, in a new place.
    """
    tol = Emu(20000)
    for sh in slide.shapes:
        if sh is numbox or sh.top is None or sh.left is None:
            continue
        if sh.has_text_frame and sh.text_frame.text.strip():
            continue
        if abs(sh.top - numbox.top) < tol and abs(sh.left - numbox.left) < tol:
            return sh
    return None


def _clone(slide, shape):
    el = copy.deepcopy(shape._element)
    shape._element.getparent().append(el)
    return slide.shapes[-1]


def set_agenda(slide, programs, detail_overrides=None):
    """Rewrite the agenda in place for however many programs the deck carries.

    The grid used to be a FIXED four rows — three programs plus Questions & Discussion —
    and anything else raised. CashPlease is a fourth product (Aaron, 2026-09-01), so five
    rows are needed, and the template's four cannot simply be appended to: row five at
    the template's 1.25" pitch lands at 6.60", where its heading runs under the logo at
    6.78" and its detail line falls off the slide.

    So rows are laid out INSIDE the band the template already defines — first row top to
    last row top — with the pitch divided by however many rows are in use. At four rows
    or fewer the pitch is unchanged and the geometry is byte-identical to before, which
    is what keeps every existing ARS / ICS / MRPC agenda exactly as it shipped.

    Matched positionally: the boxes are taken in document order rather than by their
    current text, which differs between the ARS deck and the reference."""
    # The slide-number box is excluded by GEOMETRY, not by its text: on this deck it reads
    # "3", which is indistinguishable from the agenda's own row numbers.
    boxes = [sh for sh in slide.shapes
             if sh.has_text_frame and sh.text_frame.text.strip()
             and sh.text_frame.text.strip() != "Agenda"
             and not _is_numbox(sh)]
    rows, i = [], 0
    while i < len(boxes):
        t = boxes[i].text_frame.text.strip()
        if t in ROW_TOKENS:
            head = boxes[i + 1] if i + 1 < len(boxes) else None
            det = boxes[i + 2] if i + 2 < len(boxes) else None
            if det is not None and det.text_frame.text.strip() in ROW_TOKENS:
                det = None
            rows.append((boxes[i], head, det))
            i += 2 if det is None else 3
        else:
            i += 1
    if len(rows) < 2:
        raise SystemExit(f"agenda grid: found {len(rows)} rows, need at least 2 — "
                         f"template changed")

    # The band and the row's internal offsets, read from the template rather than named
    # as constants, so re-styling the agenda slide does not silently break this.
    first_top, last_top = rows[0][0].top, rows[-1][0].top
    src_num, src_head, src_det = next((r for r in rows if r[2] is not None), rows[0])
    d_head = src_head.top - src_num.top if src_head is not None else 0
    d_det = src_det.top - src_num.top if src_det is not None else 0

    # The template's own pitch. It is KEPT whenever the deck fits the grid, so a two- or
    # four-row agenda lands on exactly the coordinates it always has; only a deck that
    # needs more rows than the template provides is re-spaced.
    grid_n = len(rows)
    grid_pitch = (last_top - first_top) / (grid_n - 1) if grid_n > 1 else 0

    needed = len(programs) + 1
    while len(rows) < needed:
        numbox = _clone(slide, src_num)
        head = _clone(slide, src_head) if src_head is not None else None
        det = _clone(slide, src_det) if src_det is not None else None
        badge = _badge_of(slide, src_num)
        if badge is not None:
            _clone(slide, badge)
        rows.append((numbox, head, det))

    used = rows[:needed]
    pitch = (grid_pitch if needed <= grid_n
             else (last_top - first_top) / (len(used) - 1))
    for i, (numbox, head, det) in enumerate(used):
        top = int(first_top + i * pitch)
        badge = _badge_of(slide, numbox)
        if badge is not None:
            badge.top = top
            badge.left = numbox.left
        numbox.top = top
        if head is not None:
            head.top = int(top + d_head)
        if det is not None:
            det.top = int(top + d_det)

    detail = dict(AGENDA_DETAIL)
    detail.update(detail_overrides or {})
    agenda = [(str(i + 1), PRODUCT_NAME[p], detail[p]) for i, p in enumerate(programs)]
    agenda.append((str(len(programs) + 1), "Questions & Discussion", None))

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

    # A detail box is added or removed to match the row, never left empty. The template's
    # grid has a detail line on rows 1-3 and none on row 4, because row 4 was always
    # Questions & Discussion. With a fourth product that assumption breaks: the product
    # lands on the detail-less row and loses its line, while Questions inherits a box and
    # renders an empty one under it.
    for (numbox, head, det), (n, title, detail) in zip(rows, agenda):
        _settext(numbox, n)
        if head is not None:
            _settext(head, title)
        if detail:
            if det is None and src_det is not None:
                det = _clone(slide, src_det)
                det.left, det.top = src_det.left, int(numbox.top + d_det)
            if det is not None:
                _settext(det, detail)
        elif det is not None:
            det._element.getparent().remove(det._element)

    # A two-program deck uses 3 of the grid's 4 rows. Remove the leftovers outright rather
    # than blanking them: an empty numbered row reads as a section that failed to render.
    for numbox, head, det in rows[len(agenda):]:
        for shape in (numbox, head, det):
            if shape is not None:
                shape._element.getparent().remove(shape._element)

    # Each row's badge is TWO stacked shapes: a decorative circle carrying no text, and the
    # number drawn on top of it. The scan above only sees shapes WITH text, so removing row
    # 4 left its empty circle behind as an orphan bullet (Wellworth 1549, Aaron 2026-08-27).
    # Clear anything left in the badge column below the last row the deck actually uses.
    kept = rows[:len(agenda)]
    if kept:
        ref = kept[0][0]
        last_top = max(r[0].top for r in kept)
        tol = Emu(60000)                      # ~0.065in
        for shape in list(slide.shapes):
            if None in (shape.top, shape.left, shape.width):
                continue
            if shape.top <= last_top + tol:
                continue
            if abs(shape.left - ref.left) < tol and abs(shape.width - ref.width) < tol:
                shape._element.getparent().remove(shape._element)
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
def merge_figure_sidecars(out_path, section_paths):
    """Carry each section deck's figure sidecar onto the combined deck.

    `build_ars_gen` names its sidecar after the deck IT wrote — the ARS
    component — but for a multi-product client that component is an
    intermediate and the deck that ships is this one. validate_deck looks for a
    sidecar named after the deck in front of it, so without this the FAIL-grade
    figure check silently did not run on any combined deck (Aaron, 2026-08-29).

    Measures are prefixed with their program. Two programs using the same
    measure name is coincidence, not identity — pooling them unprefixed would
    invent a conflict between unrelated figures. Within a program the check is
    unchanged.

    Returns the sidecar path, or None when no section carried one.
    """
    try:
        from figures import FigureLog, find_sidecar, sidecar_path
    except Exception:
        return None
    merged = FigureLog()
    for prog, path in section_paths:
        if not path:
            continue
        src = find_sidecar(path)
        if not src:
            continue
        try:
            log = FigureLog.load(src)
        except Exception:
            continue
        for row in log.rows:
            r = dict(row)
            r["measure"] = f"{prog}:{r['measure']}"
            merged.rows.append(r)
    if not merged.rows:
        return None
    return merged.dump(sidecar_path(out_path))


def main():
    _init_args()
    paths = {"ARS": ARS, "ICS": ICS, "MRPC": MRPC, "CP": CP}
    programs = [p for p in BASE_PRECEDENCE if paths[p]]
    base = programs[0]

    prs = Presentation(paths[base])
    n_base = len(prs.slides._sldIdLst)
    base_head = _head_end(prs, base)
    # Name the title the boundary was resolved BY, not just the number. The log is the
    # only place a silent fall back to the fixed index would show up, and a test asserts
    # the title appears here for exactly that reason.
    boundary = ARS_SECTION_END_TITLE if base == "ARS" else CLOSING_TITLE
    print(f"{base} deck supplies the shell: {n_base} slides; section ends at "
          f"{base_head} (by title, '{boundary}'), "
          f"closing block = {n_base - base_head}")

    sources = {}
    for prog in programs[1:]:
        sl = list(Presentation(paths[prog]).slides)
        sources[prog] = (sl, section_slides(sl))
    print(f"programs: {'+'.join(programs)}")

    # ICS financials are QUARTERLY (CLAUDE.md cadence): between workbooks an ICS build carries
    # the previous workbook's financial sections forward unchanged, so the ICS section of a
    # combined deck can legitimately report an older month than ARS/MRPC. That is not an error
    # and must not be "corrected" — the per-slide source notes name the workbook and period,
    # which is what keeps a carried-forward figure auditable. It IS worth seeing, so report
    # each section's period rather than silently presenting one reporting month for all.
    def _period(slides):
        return next((sh.text_frame.text.strip().split("•")[-1].strip()
                     for sh in slides[0].shapes
                     if sh.has_text_frame and "•" in sh.text_frame.text), "?")
    periods = {base: _period(list(prs.slides))}
    for prog, src in sources.items():
        periods[prog] = _period(src[0])
    for prog in programs:
        print(f"  {prog} section period: {periods[prog]}")
    if len(set(periods.values())) > 1:
        print(f"  note: sections report different months {periods} — expected when ICS is "
              f"carrying a prior workbook forward; source notes keep it auditable")

    added, counts = 0, []
    for prog in programs[1:]:
        src, keep = sources[prog]
        for n in keep:
            copy_slide(src[n - 1], prs)
        added += len(keep)
        counts.append(f"{len(keep)} {prog}")
    print(f"copied {added} slides ({' + '.join(counts)})")

    # Reorder: base head, then the copied sections, then the base's closing block.
    lst = prs.slides._sldIdLst
    els = list(lst)
    assert len(els) == n_base + added, "slide count drifted during copy"
    head, tail, new = els[:base_head], els[base_head:n_base], els[n_base:]
    for el in els:
        lst.remove(el)
    for el in head + new + tail:
        lst.append(el)
    assert len(list(lst)) == len(els), "reorder changed the slide count"
    assert len({id(e) for e in lst}) == len(els), "a slide is referenced twice"

    slides = list(prs.slides)
    if not set_title_products(slides[0], programs):
        raise SystemExit("MISS: title slide product line not found — cannot label the deck")
    _overrides = {}
    if sources.get("ICS") and _ics_is_referrals_only(sources["ICS"][0]):
        _overrides["ICS"] = AGENDA_DETAIL_ICS_REFERRALS
        print("  ICS section is referrals-only — agenda detail adjusted so it does not "
              "name account value, ROI or financial results")
    set_agenda(_slide_by_title(prs, "Agenda", "agenda"), programs, _overrides)
    renumber(prs)

    import fit_layout
    fit_layout.fit(prs)
    prs.save(OUT)
    print(f"built {OUT} -> {len(prs.slides._sldIdLst)} slides")
    _sc = merge_figure_sidecars(OUT, [("ARS", ARS), ("ICS", ICS), ("MRPC", MRPC)])
    if _sc:
        print(f"figures -> {os.path.basename(_sc)}")


# Guarded so the module can be IMPORTED for its pure helpers (section_slides,
# _ics_is_referrals_only, the agenda vocabularies) without argparse exiting the
# process. Unguarded, `import assemble_combined` died with SystemExit(2), which
# is why this file — the highest-risk one in the repo, sitting downstream of all
# three pipelines — had no unit tests.
if __name__ == "__main__":
    main()
