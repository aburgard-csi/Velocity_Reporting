"""TEST BRANCH layout for the take rate and Reg E opt-in slides (Aaron, 2026-09-17).

"make the take rate charts larger like on the take rate and reg e by branch slide. shift the
balance of the slide on the take rate slides if needed, then apply the same to the Reg E slides";
"the callout boxes perhaps could be shorter"; "remove the subtitle selection text on those slides
to free up space".

Runs only with RPE_JAMES_SLIDES=1, after slide_geometry.apply and before fit_layout, so the
monthly build and the template baseline are unchanged. The selection sentence is not lost: it
moves to the top of the slide's notes (STYLE.md keeps the selection on record).

  12-Month Eligible Take Rate (Personal, Business)
      tiles 1.30-2.35 (was 1.75-3.20), chart full width 0.5-12.8 x 2.60-6.30, caption 6.36
  Reg E Opt-In (All Personal, Opened in Last 12 Months)
      donut + legend + sentence in one band 1.30-3.05, chart full width 0.5-12.8 x 3.20-6.30,
      caption 6.36

The PNGs are rendered at these boxes' aspect (charts_gen DIM, build_ars_gen biz chart) so
nothing stretches: CHART_DIMS below is the one place the sizes live.
"""
from pptx.util import Emu, Inches
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN

# (left, top, width, height) in inches, and the pixel size the renderer uses (200 px/in)
TAKE_CHART = (0.5, 2.60, 12.3, 3.70)
REGE_CHART = (0.5, 3.20, 12.3, 3.10)
CHART_DIMS = {"take": (2460, 740), "rege": (2460, 620)}
CAPTION_TOP = 6.36


def _in(v):
    return Emu(v).inches if v is not None else 0.0


def _title(sl):
    for sh in sl.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            return sh.text_frame.text.strip().split("\n")[0]
    return ""


def _move_selection_to_notes(sl):
    for sh in list(sl.shapes):
        if sh.has_text_frame and sh.text_frame.text.strip().startswith("Selection:") and _in(sh.top) < 1.7:
            sel = sh.text_frame.text.strip()
            tf = sl.notes_slide.notes_text_frame
            if sel not in tf.text:
                tf.text = (sel + " " + tf.text).strip()
            sh._element.getparent().remove(sh._element)


def _big_pics(sl, minw):
    return [sh for sh in sl.shapes if sh.shape_type == MSO_SHAPE_TYPE.PICTURE and _in(sh.width) > minw]


def _place(sh, box):
    sh.left, sh.top, sh.width, sh.height = (Inches(v) for v in box)


def _caption(sl, starts):
    for sh in sl.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip().lower().startswith(starts):
            _place(sh, (0.5, CAPTION_TOP, 12.3, 0.45))
            for pa in sh.text_frame.paragraphs:
                pa.alignment = PP_ALIGN.CENTER


def _take_rate(sl):
    _move_selection_to_notes(sl)
    tiles = sorted([sh for sh in sl.shapes if sh.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE
                    and 1.6 < _in(sh.top) < 1.9 and _in(sh.width) > 2.0], key=lambda s: s.left)
    for rect in tiles:
        rect.top, rect.height = Inches(1.30), Inches(1.05)
        inside = sorted([sh for sh in sl.shapes if sh.has_text_frame and sh.text_frame.text.strip()
                         and abs(_in(sh.left) - _in(rect.left) - 0.05) < 0.02 and 1.8 < _in(sh.top) < 2.8],
                        key=lambda s: s.top)
        if len(inside) == 2:
            inside[0].top, inside[0].height = Inches(1.34), Inches(0.60)
            inside[1].top, inside[1].height = Inches(1.86), Inches(0.42)
    for pic in _big_pics(sl, 6.0):
        _place(pic, TAKE_CHART)
    _caption(sl, "take rate by branch")


def _rege(sl):
    _move_selection_to_notes(sl)
    donut = [sh for sh in _big_pics(sl, 2.0) if abs(_in(sh.width) - _in(sh.height)) < 0.2 and _in(sh.width) < 4]
    for d in donut:
        _place(d, (0.55, 1.28, 1.80, 1.80))
    rows = sorted([sh for sh in sl.shapes if sh.has_text_frame
                   and sh.text_frame.text.strip() in ("Opted In", "Opted Out", "No Election (default)")],
                  key=lambda s: s.top)
    chips = sorted([sh for sh in sl.shapes if sh.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE
                    and _in(sh.width) < 0.5 and 4.0 < _in(sh.top) < 6.6], key=lambda s: s.top)
    for j, sh in enumerate(rows):
        _place(sh, (2.92, 1.55 + j * 0.42, 2.4, 0.32))
    for j, sh in enumerate(chips[:3]):
        _place(sh, (2.60, 1.57 + j * 0.42, 0.22, 0.22))
    for sh in sl.shapes:
        tx = sh.text_frame.text.strip() if sh.has_text_frame else ""
        if tx and len(tx) > 40 and not tx.lower().startswith("opt-in rate by branch") and _in(sh.top) > 4.5 and _in(sh.left) < 1.6:
            _place(sh, (5.55, 1.40, 7.25, 1.55))
    for pic in _big_pics(sl, 6.0):
        _place(pic, REGE_CHART)
    _caption(sl, "opt-in rate by branch")


def apply(prs):
    for sl in prs.slides:
        t = _title(sl)
        if t.startswith("12-Month Eligible Take Rate"):
            _take_rate(sl)
        elif t.startswith("Reg E Opt-In") and ("All Personal" in t or "Opened in Last 12" in t):
            _rege(sl)
