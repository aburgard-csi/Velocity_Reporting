#!/usr/bin/env python3
"""
ars_layout.py — the drawing primitives James's v5 ODD deck body (engine/deck/ars_deck.py) calls,
implemented on Aaron's grid with Aaron's shapes. The v5 body is verbatim; this is where its
`_text`, `_table`, `_kpi`, `_tile`, `_rail`, `_picture` land as his textbox, table, tile and
picture, every line measured at the 16pt floor before it is written.

Rules the primitives keep for the body:
  * a text run is never under 16pt; a box grows to the lines its text needs at the floor and
    is clamped above the slide-number band; a small-type footnote at the foot of the slide
    goes to the speaker note instead (there is no room for it at 16pt);
  * a table is Aaron's add_table at 16pt rows, cut to the rows that fit above the band, the
    cut stated in the note;
  * a KPI card or stat tile is Aaron's tile, its value recorded in the figure sidecar under
    the slide's own title (the same label means different populations on different v5 slides);
  * a picture keeps its aspect and stops at the tile rail; the identity spine, kicker and
    footer are Aaron's branding pass's job and draw nothing here.
"""
import os
import sys

from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(_HERE, os.pardir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import figures as _figs                                                          # noqa: E402
import shapes as SH                                                              # noqa: E402
import ti_layout as L                                                            # noqa: E402
from chapter_base import house_words                                             # noqa: E402
from brand import (BODY, HEAD, NAVY_RGB, ORANGE_RGB, WHITE_RGB, TICK_RGB, TEAL,  # noqa: E402
                   LABEL_RGB, ROWALT_RGB, _rgb)

# ---- the v5 names, Aaron's values --------------------------------------------------------
MARGIN_L = L.MARGIN_L
RIGHT_EDGE = L.RIGHT_EDGE
CONTENT_W = RIGHT_EDGE - MARGIN_L
RAIL_LEFT = L.TILE_L
RAIL_BOTTOM = L.RAIL_BOTTOM
RAIL_GUTTER = 0.25
SLIDE_W, SLIDE_H = 13.333, 7.5
NAVY, ORANGE, GREY, WHITE = NAVY_RGB, ORANGE_RGB, TICK_RGB, WHITE_RGB
TINT = _rgb("#9DB8D2")
GREEN_D, RED_D = _rgb(TEAL), ORANGE_RGB       # v5 semantic good / weak, in Aaron's palette
HEAD_FONT, BODY_FONT = HEAD, BODY
BAND_FILL = ROWALT_RGB
FLOOR = L.FLOOR_PT
BOTTOM = 6.95                                # above Aaron's slide-number band (7.05)
LOGO_BOTTOM = L.RAIL_BOTTOM                  # and, past LOGO_LEFT, above his data-slide logo
FOOTNOTE_TOP, FOOTNOTE_PT = 6.2, 11.5        # a v5 footnote: small type at the foot
ROW_H = 0.36                                 # a 16pt table row
TILE_H = 1.25                                # Aaron's KPI tile
_DARK_FILLS = {"00274C", "7B9BB8", "2A9D8F", "E9A13B", "C0392B", "F47A29", "0D9488"}


def _slide_title(slide):
    return _figs.slide_title(slide) or "slide"


# Where each slide's tables end once their rows are sized for 16pt: the v5 body positions
# what follows a table from ITS 0.3in rows, so anything placed inside the grown table is
# pushed below it.
_TABLE_SPANS = {}


# Every box the primitives drew on a slide. A new box that would land on one of them is
# moved down until it clears (v5 stacked its elements at its own type sizes; at the 16pt
# floor they are taller). Rules are not boxes: text sits on them by design.
_BOXES = {}


def _overlaps(box, left, top, width, height):
    l0, t0, r0, b0 = box[:4]
    return left < r0 - 0.05 and left + width > l0 + 0.05 and top < b0 - 0.05 and top + height > t0 + 0.05


def _settle(slide, left, top, width, height, shape=None, text=None):
    boxes = _BOXES.setdefault(id(slide), [])
    moved = True
    while moved:
        moved = False
        for box in boxes:
            if _overlaps(box, left, top, width, height):
                top, moved = box[3] + 0.04, True
    boxes.append([left, top, left + width, top + height, shape, text])
    return top


def _yield_text(slide, left, top, width, height):
    """A card that has no room below the text in its way: that text (v5's small type) goes to
    the note and the card keeps its place. Returns True when something yielded."""
    boxes = _BOXES.get(id(slide), [])
    for box in list(boxes):
        if box[4] is not None and box[5] and _overlaps(box, left, top, width, height):
            L.note(slide, box[5])
            box[4]._element.getparent().remove(box[4]._element)
            boxes.remove(box)
            return True
    return False


def _clear_tables(slide, top):
    """v5 stacked what follows a table from ITS row height; shift by how much the table grew
    at 16pt so the stack keeps its own spacing."""
    for t0, v5_bottom, bottom in _TABLE_SPANS.get(id(slide), []):
        if top >= t0 - 0.05 and bottom > v5_bottom:
            top += bottom - v5_bottom
    return top


def _text(slide, left, top, width, height, text, size=14, bold=False,
          color=NAVY, font=BODY_FONT, align=PP_ALIGN.LEFT, wrap=True):
    """v5 `_text` on Aaron's floor. Small type at the foot of the slide is a footnote and goes
    to the note; everything else is drawn at max(size, 16) in a box grown to its lines."""
    text = house_words(str(text))
    if top >= FOOTNOTE_TOP and size <= FOOTNOTE_PT:
        L.note(slide, text)
        return None
    top = _clear_tables(slide, top)
    pt = max(size, FLOOR)
    lines = L.lines_for(text, width, pt, font, bold)
    need_h = lines * L._line_in(pt) + 0.1
    height = max(height, need_h)
    top = _settle(slide, left, top, width, height)
    if top >= BOTTOM - 0.2:
        L.note(slide, text)
        _BOXES[id(slide)].pop()
        return None
    if top + height > BOTTOM:
        height = max(BOTTOM - top, L._line_in(pt) + 0.1)
        if need_h > height:
            L.note(slide, f"Text clipped on the slide, in full: {text}")
    box = SH.textbox(slide, left, top, width, height, text, pt, color, bold, align, font,
                     MSO_ANCHOR.TOP)
    _BOXES[id(slide)][-1][4:] = [box, text]
    return box


def _pack(label, note, width, holds):
    """[label] or [label, note] as the tile's label lines, measured; what does not fit is
    returned as the detail sentence."""
    label, note = house_words(str(label)), (house_words(str(note)) if note else "")
    need = L.lines_for(label, width)
    if need > holds:
        shown = label
        while L.lines_for(shown + "…", width) > holds and len(shown) > 4:
            shown = shown[:-2].rstrip()
        return [shown + "…"], f"{label}" + (f" ({note})" if note else "")
    if note and need + L.lines_for(note, width) <= holds:
        return [label, note], None
    return [label], (note or None)


def _card(slide, left, top, width, value, label, note, fill, height=TILE_H):
    value = str(value)
    top = _clear_tables(slide, top)
    top = _settle(slide, left, top, width, height)
    bottom = LOGO_BOTTOM if left + width > L.LOGO_LEFT else BOTTOM
    if top + height > bottom:
        # no room below what is in the way: the card takes the lowest spot that fits, and any
        # small text there (v5's footnotes) yields to the note
        _BOXES[id(slide)].pop()
        cand = max(L.CHART_TOP, bottom - height)
        while _yield_text(slide, left, cand, width, height):
            pass
        top = _settle(slide, left, cand, width, height)
        if top + height > bottom:
            _BOXES[id(slide)].pop()
            top = cand
            _BOXES[id(slide)].append([left, top, left + width, top + height, None, None])
            L.note(slide, "No room at 16pt: a tile sits over the content above it; review this slide.")
    value_h, label_h = 0.52, height - 0.52 - 0.08
    holds = L.box_holds(label_h)
    lines, detail = _pack(label, note, width - 0.1, holds)
    pt = L._value_pt(value, 28, width - 0.1)
    sp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top),
                                Inches(width), Inches(height))
    sp.fill.solid(); sp.fill.fore_color.rgb = fill; sp.line.fill.background()
    sp.shadow.inherit = False
    SH.textbox(slide, left + 0.05, top + 0.04, width - 0.1, value_h, value, pt, WHITE, True,
               PP_ALIGN.CENTER, HEAD, MSO_ANCHOR.MIDDLE)
    SH.textbox(slide, left + 0.05, top + 0.04 + value_h, width - 0.1, label_h, lines, FLOOR,
               LABEL_RGB, False, PP_ALIGN.CENTER, BODY, MSO_ANCHOR.TOP)
    SH.shadow(sp)
    _figs.log.record(f"{_slide_title(slide)} · {label}", value, slide)
    if detail:
        L.note(slide, f"{label}: {value} ({detail})" if detail != label else f"{label}: {value}")
    return sp


def _kpi(slide, left, top, width, label, value, note=None, accent=NAVY):
    return _card(slide, left, top, width, value, label, note, accent)


def _kpi_flat(slide, left, top, width, label, value, note=None):
    return _card(slide, left, top, width, value, label, note, NAVY)


def _tile(slide, left, top, width, value, label, note=None, rule=NAVY):
    return _card(slide, left, top, width, value, label, note, rule)


def _rule(slide, left, top, width, color=None, weight=0.02):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top),
                                 Inches(width), Inches(weight))
    bar.fill.solid(); bar.fill.fore_color.rgb = color or TINT
    bar.line.fill.background(); bar.shadow.inherit = False
    return top + weight


def _table(slide, rows, left, top, width, col_widths=None, size=11, header=True,
           cell_fill=None):
    """Aaron's table at 16pt rows, cut to what fits above the band (the cut goes to the note).
    cell_fill(r, c) -> RGBColor paints one cell (RAG chips, heat maps); dark fills flip the
    text white, as v5 did."""
    rows = [[house_words(str(v)) for v in r] for r in rows]
    v5_bottom = top + 0.32 * len(rows)           # where v5 put the table's foot
    fit = max(2, int((BOTTOM - top) / ROW_H))
    if len(rows) > fit:
        dropped = len(rows) - fit
        rows = rows[:fit]
        L.note(slide, f"Table cut to the {fit - (1 if header else 0)} rows that fit at 16pt; "
                      f"{dropped} more in the evidence tables.")
    n_cols = len(rows[0])
    colw = list(col_widths) if col_widths and len(col_widths) >= n_cols else [1] * n_cols
    colw = colw[:n_cols]
    scale = width / (sum(colw) or 1)
    # rows sized for the lines their widest cell needs at 16pt, so the table's real bottom
    # is known here and not only in PowerPoint
    heights = []
    for r in rows:
        lines = max(L.lines_for(str(v), cw * scale - 0.18, FLOOR, BODY, header and r is rows[0])
                    for v, cw in zip(r, colw))
        heights.append(max(ROW_H, lines * L._line_in(FLOOR) + 0.14))
    while len(rows) > 2 and top + sum(heights) > BOTTOM:
        rows.pop(); heights.pop()
        L.note(slide, "One more row cut because its text wraps at 16pt.")
    gf = SH.add_table(slide, left, top, width, sum(heights), rows, colw, header=header, fs=FLOOR)
    tb = gf.table
    for r, hgt in enumerate(heights):
        tb.rows[r].height = Inches(hgt)
    _TABLE_SPANS.setdefault(id(slide), []).append((top, v5_bottom, top + sum(heights)))
    _BOXES.setdefault(id(slide), []).append([left, top, left + width, top + sum(heights), None, None])
    for r in range(len(rows)):
        for c in range(n_cols):
            cell = tb.cell(r, c)
            if c:
                cell.text_frame.paragraphs[0].alignment = PP_ALIGN.RIGHT
            fill = cell_fill(r, c) if (cell_fill and not (header and r == 0)) else None
            if fill is not None:
                cell.fill.solid(); cell.fill.fore_color.rgb = fill
                if str(fill) in _DARK_FILLS:
                    for run in cell.text_frame.paragraphs[0].runs:
                        run.font.color.rgb = WHITE
    return gf


def _row_budget(top, rows_wanted, row_h=ROW_H, bottom=RAIL_BOTTOM):
    return max(2, min(rows_wanted, int((bottom - top - 0.1) / row_h) - 1))


def _fit_picture(slide, image, left, top, max_w, max_h):
    """Both dimensions constrained, aspect kept, clamped to the content edge."""
    from PIL import Image
    with Image.open(image) as img:
        w, h = img.size
    max_w = min(max_w, RIGHT_EDGE - left)
    # a chart (anything wide) stops at the caption band; an icon or sparkline keeps its box
    max_h = min(max_h, (L.CHART_BOTTOM if max_w > 3.0 and top < L.CHART_BOTTOM else BOTTOM) - top)
    scale = min(max_w / w, max_h / h)
    width, height = w * scale, h * scale
    slide.shapes.add_picture(str(image), Inches(left), Inches(top), Inches(width), Inches(height))
    _BOXES.setdefault(id(slide), []).append([left, top, left + width, top + height, None, None])
    return width, height


def _picture(slide, image, top=1.75, max_h=5.0, rail=False):
    w, h = L.picture_left(slide, image, top, L.RAIL_EDGE if rail else RIGHT_EDGE, max_h)
    _BOXES.setdefault(id(slide), []).append([MARGIN_L, top, MARGIN_L + w, top + h, None, None])
    return top + h


def _chart_left(slide, image, top, right_edge, max_h=4.9):
    w, h = L.picture_left(slide, image, top, right_edge, max_h)
    _BOXES.setdefault(id(slide), []).append([MARGIN_L, top, MARGIN_L + w, top + h, None, None])


def _rail(slide, items, top=1.75, left=RAIL_LEFT, width=2.55):
    items = [(house_words(str(a)), b, house_words(str(c)) if c else c) for a, b, c in items]
    right, detail = L.rail_tiles(slide, items, top=L.RAIL_TOP, scope=_slide_title(slide),
                                 record=_figs.log.record)
    for d in detail:
        L.note(slide, d)
    return right


def _kicker(slide, _text_unused=None):
    """v5's bottom band; Aaron's branding pass owns the foot of the slide."""


def _spine(slide, number, chapter=None):
    """v5's identity spine; not part of Aaron's deck."""
