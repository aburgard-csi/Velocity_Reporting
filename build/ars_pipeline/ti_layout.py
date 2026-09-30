#!/usr/bin/env python3
"""
ti_layout.py — the drawing primitives the ported v5 transaction chapter is drawn with, all on
Aaron's geometry (STYLE.md, shapes.py, combined_insight_slides.py) and measured against his
16pt floor with his textfit, so nothing lands on the slide that restyle_fonts would later wrap.

    rail_tiles(s, items, top, scope, record)  v5's (label, value, note) rail as Aaron's tiles
    caption_fit(text, width)                  the lines a caption needs at 16pt Calibri
    section_slide(prs, like, title, subtitle) a chapter divider cloned from a template section slide
    picture_left(s, png, top, right_edge, max_h)  a chart in the content box, aspect kept
    set_text(shape, text)                     replace a shape's text, keeping its formatting
"""
import copy
import io
import math
import os
import sys

from PIL import Image
from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(_HERE, os.pardir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import shapes as SH                                                               # noqa: E402
from brand import BODY, HEAD, NAVY_RGB, ORANGE_RGB, WHITE_RGB, LABEL_RGB          # noqa: E402
from textfit import text_width_in                                                 # noqa: E402

# Aaron's content grid for a data slide (combined_insight_slides / ti_slides on main).
MARGIN_L = 0.5
RIGHT_EDGE = 12.71            # the v5 constant the chapters read; same as Aaron's content edge
CHART_TOP = 1.72              # below the 16pt selection line
CHART_BOTTOM = 5.85           # above the caption band
CAPTION_TOP, CAPTION_H = 5.95, 0.95
CAPTION_W_RAIL, CAPTION_W_FULL = 8.75, 10.6
TILE_L, TILE_W = 9.5, 3.3     # the tile column of the TI slides on main
RAIL_EDGE = TILE_L - 0.25     # what a chart beside the rail must stop at
RAIL_TOP, RAIL_BOTTOM = 1.72, 6.9
BOX_MARGINS = 0.2             # python-pptx default insets, left + right
FLOOR_PT = 16                 # restyle_fonts.MIN
LINE_FACTOR = 1.22            # validate_deck's line height per point
MAX_TILES = 5
# (tile height, value pt, value box h, label box h, gap) for a stack of n tiles from RAIL_TOP
_STACK = {4: (1.2, 28, 0.5, 0.6, 0.1), 5: (0.98, 22, 0.38, 0.54, 0.06)}


def _line_in(pt):
    return pt / 72.0 * LINE_FACTOR


def lines_needed(text, width_in, pt=FLOOR_PT, family=BODY, bold=False):
    """Greedy word wrap against the bundled TTF: the lines PowerPoint will use."""
    usable = width_in - BOX_MARGINS
    if usable <= 0:
        return 99
    lines, cur = 1, ""
    for word in str(text).split():
        trial = f"{cur} {word}".strip()
        if text_width_in(trial, pt, family, bold) <= usable:
            cur = trial
        elif cur:
            lines += 1
            cur = word
        else:
            cur = word
    return lines


def box_holds(height_in, pt=FLOOR_PT):
    return max(1, int(height_in / _line_in(pt) + 0.15))


def caption_fit(text, width_in):
    """(lines needed, lines the caption band holds) at the floor."""
    return lines_needed(text, width_in), box_holds(CAPTION_H)


def _value_pt(value, start_pt, width_in):
    for pt in (start_pt, 24, 22):
        if pt <= start_pt and text_width_in(str(value), pt, HEAD, True) <= width_in - BOX_MARGINS:
            return pt
    return 22


def _tile(s, top, tile_h, value, value_pt, value_h, label_h, lines, fill):
    sp = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(TILE_L), Inches(top),
                            Inches(TILE_W), Inches(tile_h))
    sp.fill.solid(); sp.fill.fore_color.rgb = fill; sp.line.fill.background()
    sp.shadow.inherit = False
    SH.textbox(s, TILE_L + 0.05, top + 0.04, TILE_W - 0.1, value_h, str(value), value_pt, WHITE_RGB,
               True, PP_ALIGN.CENTER, HEAD, MSO_ANCHOR.MIDDLE)
    SH.textbox(s, TILE_L + 0.05, top + 0.04 + value_h, TILE_W - 0.1, label_h, lines, FLOOR_PT, LABEL_RGB,
               False, PP_ALIGN.CENTER, BODY, MSO_ANCHOR.TOP)
    SH.shadow(sp)


def rail_tiles(s, items, top=RAIL_TOP, scope=None, record=None):
    """v5's callout rail — (label, value, note) triples — as Aaron's tiles, first one orange.

    Every line is measured at the 16pt floor before it is written: a label that fits one line
    keeps its note on the second; a label that needs both lines sends its note to the notes; a
    label that fits neither is clipped visibly and given in full in the notes. Returns
    (right edge for the chart, [detail sentences for the speaker note]).
    """
    items = list(items)[:MAX_TILES]
    n = len(items)
    tile_h, value_pt, value_h, label_h, gap = _STACK[5 if n > 4 else 4]
    holds = box_holds(label_h)
    usable_w = TILE_W - 0.1
    detail, y = [], top
    for i, (label, value, note) in enumerate(items):
        label, note = str(label), (str(note) if note else "")
        need = lines_needed(label, usable_w)
        if need > holds:
            shown = label
            while lines_needed(shown + "…", usable_w) > holds and len(shown) > 4:
                shown = shown[:-2].rstrip()
            lines = [shown + "…"]
            detail.append(f"{label}: {value}" + (f" ({note})" if note else ""))
        elif note and need + lines_needed(note, usable_w) <= holds:
            lines = [label, note]
        else:
            lines = [label]
            if note:
                detail.append(f"{label}: {value} ({note})")
        pt = _value_pt(value, value_pt, usable_w)
        _tile(s, y, tile_h, value, pt, value_h, label_h, lines, ORANGE_RGB if i == 0 else NAVY_RGB)
        if record:
            record(f"TI {scope}: {label}" if scope else f"TI: {label}", value, s)
        y += tile_h + gap
    return RAIL_EDGE, detail


def picture_left(s, png, top, right_edge, max_h=4.9):
    """The chart in the content box: left at the margin, both dimensions constrained, aspect
    kept (Aaron's fit_picture rule — a picture placed by width alone walks off the slide)."""
    right_edge = RIGHT_EDGE if right_edge >= RIGHT_EDGE else min(right_edge, RAIL_EDGE)
    max_w = right_edge - MARGIN_L
    max_h = min(max_h, CHART_BOTTOM - top)
    with Image.open(png) as im:
        pw, ph = im.size
    scale = min(max_w / pw, max_h / ph)
    w, h = pw * scale, ph * scale
    s.shapes.add_picture(str(png), Inches(MARGIN_L), Inches(top), Inches(w), Inches(h))
    return w, h


def set_text(sh, text):
    """Replace a shape's text in its first run, dropping the rest; formatting survives."""
    tf = sh.text_frame
    p0 = tf.paragraphs[0]
    runs = p0.runs
    if not runs:
        p0.add_run()
        runs = p0.runs
    runs[0].text = text
    for r in runs[1:]:
        r._r.getparent().remove(r._r)
    for p in list(tf.paragraphs)[1:]:
        p._p.getparent().remove(p._p)


def section_slide(prs, like, title, subtitle):
    """A chapter divider that IS the template's section slide (band, chip, 52pt title, 22pt
    subtitle, top-left logo), with the two texts swapped. The branding pass recognises it by
    the ≥44pt title and the top-left logo and treats it as a section: no slide number."""
    s = SH.blank_slide(prs, like)
    pictures = []
    for sh in like.shapes:
        if sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
            pictures.append(sh)
        else:
            s.shapes._spTree.append(copy.deepcopy(sh._element))
    for sh in pictures:
        s.shapes.add_picture(io.BytesIO(sh.image.blob), sh.left, sh.top, sh.width, sh.height)
    boxes = [sh for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip()]
    boxes.sort(key=lambda sh: -max((r.font.size.pt for p in sh.text_frame.paragraphs
                                    for r in p.runs if r.font.size), default=0))
    if len(boxes) < 2:
        raise RuntimeError("section slide to clone has no title and subtitle boxes")
    set_text(boxes[0], title)
    set_text(boxes[1], subtitle)
    return s


def move_before(prs, slide, target):
    """Reorder by slide OBJECT, not title — two chapter titles can share a prefix."""
    lst = prs.slides._sldIdLst
    src = SH.sldid_of(prs, slide)
    lst.remove(src)
    SH.sldid_of(prs, target).addprevious(src)


def est_caption_bottom(text, width_in, top=CAPTION_TOP, pt=FLOOR_PT):
    """validate_deck.geometry_findings' own estimate of where a bottom caption ends."""
    est_lines = max(1, math.ceil(len(text) * 0.0066 * pt / max(0.5, width_in)))
    return top + 0.08 + est_lines * 0.0163 * pt
