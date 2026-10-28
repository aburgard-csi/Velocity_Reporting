# Ported from v5 02-Scripts/ars/deck/build.py at 7ba1e63. Logic unchanged; only what deckkit's PGL surface reaches (the slide helpers, grid, colours, DeckResult); the import of the ARS slide modules keeps polish only, and core.layout is ils_pipeline.core.layout.
"""Build an ODD-only deck.

Deliberately NOT `build_ars_gen.py`. That assembler swaps numbers into a
populated demo deck and hard-requires 12 keys from `base.json`, which is
extracted from the ARS Workbook -- and the Workbook is maintained by hand from
a second file. Anything depending on it inherits that manual step.

Everything here comes from the ODD, so a deck can be produced the moment the
data lands. The template supplies the theme, masters and fonts, so branding
matches; the slides are generated rather than swapped.

Workbook-dependent content (program revenue, profit, LTD financials) is out of
scope by design and noted on the closing slide, so its absence is explicit
rather than silently missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

from . import polish
from ils_pipeline.core import layout

NAVY = RGBColor(0x00, 0x27, 0x4C)
import brand
ORANGE = brand.ORANGE_RGB       # v5 wrote the same orange as a literal; RPE keeps colour in brand.py
GREY = RGBColor(0x5A, 0x66, 0x70)
TINT = RGBColor(0x9D, 0xB8, 0xD2)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
RED_D = RGBColor(0xC0, 0x39, 0x2B)     # semantic weak

HEAD_FONT = "Montserrat"
BODY_FONT = "Calibri"

SLIDE_W = 13.333
SLIDE_H = 7.5

MARGIN_L = 1.18                            # body content clears the spine
RIGHT_EDGE = 12.71
CONTENT_W = RIGHT_EDGE - MARGIN_L          # 12.09
RAIL_BOTTOM = 6.62
RAIL_LEFT = 10.15                          # where _rail's tiles begin
RAIL_GUTTER = 0.28                         # clear air between chart and tiles
DIVIDER_L = 1.0

LAYOUT_BLANK = 0
@dataclass
class DeckResult:
    path: Path
    slides: int
    charts: int
    skipped: list
    storyboard: Path | None = None
    form_census: list | None = None    # formaudit.census rows, final order
    register: Path | None = None       # slide_register.md (+ .json beside it)


def _strip_placeholders(slide) -> None:
    """Remove unfilled layout placeholders so PowerPoint shows no prompts."""
    for ph in list(slide.placeholders):
        if not (ph.has_text_frame and ph.text_frame.text.strip()):
            ph._element.getparent().remove(ph._element)


def _text(slide, left, top, width, height, text, size=14, bold=False,
          color=NAVY, font=BODY_FONT, align=PP_ALIGN.LEFT, wrap=True):
    box = slide.shapes.add_textbox(Inches(left), Inches(top),
                                   Inches(width), Inches(height))
    frame = box.text_frame
    frame.word_wrap = wrap
    para = frame.paragraphs[0]
    para.alignment = align
    run = para.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = font
    run.font.color.rgb = color
    return box


HEADLINE_MAX = 90


def _fit_headline(title, subtitle=None):
    """Over-cap titles split at a CLAUSE boundary (em dash, comma) with
    the tail moving to the subtitle. A single-clause title past the cap
    keeps whole and wraps to two lines -- a word-boundary cut amputates
    the finding ('...to other institutions\' financial', #68)."""
    if len(title) > HEADLINE_MAX:
        cut = title.rfind(" \u2014 ", 0, HEADLINE_MAX)
        if cut < 30:
            cut = title.rfind(", ", 30, HEADLINE_MAX)
        if cut >= 30:
            tail = title[cut:].lstrip(" \u2014,")
            title = title[:cut].rstrip()
            subtitle = tail if not subtitle else f"{tail} \u2014 {subtitle}"
    return title, subtitle


def _title(slide, title, subtitle=None):
    """Action title. Wraps to two lines if the finding needs them; past
    ~90 chars the explanatory clause moves into the subtitle instead of
    colliding with the content below."""
    title, subtitle = _fit_headline(title, subtitle)
    title = polish.title(title)
    subtitle = polish.sub(subtitle, title)
    size, lines = polish.title_fit(title)
    # the box is sized for the lines the text will ACTUALLY take -- the
    # old <62-chars-fits-30pt rule made 53-61-char titles wrap into the
    # subtitle (James, #17)
    height = 0.8 if lines == 1 else 1.05
    _text(slide, MARGIN_L, 0.32, CONTENT_W, height, title, size=size, bold=True,
          font=HEAD_FONT)
    if subtitle:
        _text(slide, MARGIN_L, 0.32 + height + 0.02, CONTENT_W, 0.5, subtitle,
              size=13.5, color=GREY)


def _headed(slide, pair, fallback):
    """Apply a generated headline, or the plain label if there is none."""
    if pair:
        _title(slide, pair[0], pair[1])
        return 1.72 if polish.title_fit(polish.title(pair[0]))[1] == 1 else 1.95
    _title(slide, fallback)
    return 1.55


LOGO_PATH = layout.LOGO   # one spelling for every static asset (#210)


def _logo(slide, dark_bg=False):
    """Brand mark, top-right, from core.layout.LOGO. A missing file is a
    no-op here and a failure in tests/test_layout.py, never an invented asset."""
    if not LOGO_PATH.exists():
        return
    _fit_picture(slide, LOGO_PATH, RIGHT_EDGE - 1.35, 0.28,
                 max_w=1.35, max_h=0.55)


def _wedge(slide, points, color):
    """A filled corner wedge (the divider motif's angle bands)."""
    fb = slide.shapes.build_freeform(points[0][0], points[0][1],
                                     scale=914400)   # local units are inches
    fb.add_line_segments(list(points[1:]), close=True)
    shape = fb.convert_to_shape()
    # pin the frame to the intended bbox -- freeform origin quirks
    # otherwise push the frame past the slide edge
    xs = [x for x, _y in points]
    ys = [y for _x, y in points]
    shape.left = Inches(min(xs))
    shape.top = Inches(min(ys))
    shape.width = Inches(max(xs) - min(xs))
    shape.height = Inches(max(ys) - min(ys))
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    shape.shadow.inherit = False
    return shape


def _divider(prs, new, title, subtitle=None, number=None):
    """Chapter break as a designed object (DESIGN/ spec): full-bleed navy,
    corner angle bands, oversized chapter numeral, orange rule, logo slot.
    Subtitles are retired (James, #17: filler prose) -- the numeral and
    the chapter name carry the slide."""
    subtitle = None
    from pptx.enum.shapes import MSO_SHAPE
    slide = new(LAYOUT_BLANK)
    band = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0),
                                  Inches(SLIDE_W), Inches(SLIDE_H))
    band.fill.solid()
    band.fill.fore_color.rgb = NAVY
    band.line.fill.background()
    band.shadow.inherit = False
    try:
        _wedge(slide, [(SLIDE_W, 0), (SLIDE_W, SLIDE_H), (9.3, SLIDE_H)],
               RGBColor(0x0B, 0x3A, 0x66))
        _wedge(slide, [(SLIDE_W, 2.33), (SLIDE_W, SLIDE_H), (11.0, SLIDE_H)],
               ORANGE)
    except Exception:
        pass
    if number:
        _text(slide, DIVIDER_L - 0.06, 0.55, 4.0, 2.6, f"{number:02d}",
              size=110, bold=True, color=RGBColor(0x12, 0x40, 0x6E),
              font=HEAD_FONT)
    rule = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(DIVIDER_L),
                                  Inches(2.62), Inches(4.5), Inches(0.045))
    rule.fill.solid()
    rule.fill.fore_color.rgb = ORANGE
    rule.line.fill.background()
    rule.shadow.inherit = False
    _text(slide, DIVIDER_L, 3.05, 11.3, 1.0, title, size=40, bold=True,
          color=WHITE, font=HEAD_FONT)
    if subtitle:
        _text(slide, DIVIDER_L + 0.05, 4.15, 11.3, 0.6, subtitle, size=16,
              color=RGBColor(0xC8, 0xD4, 0xE2))
    _logo(slide, dark_bg=True)
    return slide


def _rail(slide, items, top=1.75, left=RAIL_LEFT, width=2.55):
    """Callout tiles down the right edge, chart takes the rest. Four tiles
    at full height; a fifth compresses the stack instead of vanishing."""
    from pptx.enum.shapes import MSO_SHAPE
    n = min(len(items), 5)
    # solve the stack so it always ends above RAIL_BOTTOM: shrink the gap
    # first, then the tiles themselves (0.92 floor)
    tile_h = 1.22 if n <= 4 else 1.02
    while tile_h > 0.92 and \
            top + (n - 1) * (tile_h + 0.04) + tile_h > RAIL_BOTTOM:
        tile_h = round(tile_h - 0.10, 2)
    step = max(min(tile_h + 0.14,
                   (RAIL_BOTTOM - top - tile_h) / max(n - 1, 1)),
               tile_h + 0.04)
    compact = tile_h < 1.12
    y = top
    for label, value, note in items[:5]:
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                      Inches(left), Inches(y),
                                      Inches(width), Inches(tile_h))
        card.fill.solid()
        card.fill.fore_color.rgb = NAVY
        card.line.color.rgb = WHITE
        card.line.width = Pt(1.5)
        card.shadow.inherit = False
        card.text_frame.text = ""
        _text(slide, left + 0.08, y + 0.06, width - 0.16, 0.26, label,
              size=10.5, bold=True, color=WHITE, font=HEAD_FONT,
              align=PP_ALIGN.CENTER)
        _text(slide, left + 0.08, y + (0.3 if compact else 0.36), width - 0.16, 0.5, value,
              size=19 if compact else 21, bold=True, color=WHITE, font=HEAD_FONT,
              align=PP_ALIGN.CENTER)
        if note:
            _text(slide, left + 0.08, y + (0.72 if compact else 0.88), width - 0.16, 0.28, note,
                  size=9, color=WHITE, align=PP_ALIGN.CENTER)
        y += step
    return left - 0.25


def _fit_picture(slide, image: Path, left, top, max_w, max_h):
    """The one way a picture lands on a slide: both dimensions constrained,
    native aspect kept, clamped to the content grid. Never place by height
    alone -- a wide PNG walks off the slide (the Reg E bug)."""
    from PIL import Image
    with Image.open(image) as img:
        w, h = img.size
    aspect = w / h
    max_w = min(max_w, RIGHT_EDGE - left)
    height = min(max_h, SLIDE_H - top - 0.4, max_w / aspect)
    width = height * aspect
    slide.shapes.add_picture(str(image), Inches(left), Inches(top),
                             Inches(width), Inches(height))
    return width, height


def _chart_left(slide, image: Path, top, right_edge, max_h=4.9):
    """Place a chart in the space left of the callout rail."""
    _fit_picture(slide, image, MARGIN_L, top,
                 max_w=right_edge - MARGIN_L, max_h=max_h)


def _kpi(slide, left, top, width, label, value, note=None, accent=NAVY):
    from pptx.enum.shapes import MSO_SHAPE
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                  Inches(left), Inches(top),
                                  Inches(width), Inches(1.65))
    card.fill.solid()
    card.fill.fore_color.rgb = accent
    card.line.color.rgb = WHITE
    card.line.width = Pt(2)
    card.text_frame.text = ""
    card.shadow.inherit = False

    _text(slide, left + 0.1, top + 0.12, width - 0.2, 0.3, label, size=12,
          bold=True, color=WHITE, font=HEAD_FONT, align=PP_ALIGN.CENTER)
    _text(slide, left + 0.1, top + 0.48, width - 0.2, 0.66, value, size=28,
          bold=True, color=WHITE, font=HEAD_FONT, align=PP_ALIGN.CENTER)
    if note:
        _text(slide, left + 0.1, top + 1.20, width - 0.2, 0.34, note, size=10.5,
              color=WHITE, align=PP_ALIGN.CENTER)


def _rule(slide, left, top, width, color=None, weight=0.02):
    """A horizontal rule. The house divider between two zones of one slide --
    the same device _tile uses above a number, at slide scale."""
    from pptx.enum.shapes import MSO_SHAPE
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left),
                                 Inches(top), Inches(width), Inches(weight))
    bar.fill.solid()
    bar.fill.fore_color.rgb = color or TINT
    bar.line.fill.background()
    bar.shadow.inherit = False
    return top + weight


def _picture(slide, image: Path, top=1.75, max_h=5.0, rail=False):
    """Centered within the CONTENT field (right of the spine), never the
    full slide -- a full-slide center puts wide charts under the spine.

    `rail=True` when the slide also carries _rail: the field then stops
    before the tiles instead of running under them. It centred across the
    whole content field regardless, so any chart wider than about nine
    inches printed underneath the callouts -- "chart and data callouts
    overlap", four times in one review (James, 2026-09-09).
    """
    from PIL import Image
    with Image.open(image) as img:
        w, h = img.size
    field = (RAIL_LEFT - RAIL_GUTTER - MARGIN_L) if rail else CONTENT_W
    aspect = w / h
    height = min(max_h, field / aspect)
    width = height * aspect
    if width > field:
        width = field
        height = width / aspect
    _fit_picture(slide, image, MARGIN_L + (field - width) / 2, top,
                 max_w=width, max_h=height)
    return top + height


BAND_FILL = RGBColor(0xF2, 0xF5, 0xF8)
BORDER_CLR = "D5DCE4"
_DARK_FILLS = {"00274C", "7B9BB8", "2A9D8F", "E9A13B", "C0392B"}


def _cell_bottom_border(cell):
    """0.5pt horizontal rule under a cell (a:lnB). Horizontal borders only
    -- the house look; verticals stay open."""
    from pptx.oxml.ns import qn
    tcPr = cell._tc.get_or_add_tcPr()
    for el in tcPr.findall(qn("a:lnB")):
        tcPr.remove(el)
    ln = tcPr.makeelement(qn("a:lnB"), {"w": "6350", "cap": "flat"})
    fill = ln.makeelement(qn("a:solidFill"), {})
    fill.append(fill.makeelement(qn("a:srgbClr"), {"val": BORDER_CLR}))
    ln.append(fill)
    tcPr.insert(0, ln)


def _table(slide, rows, left, top, width, col_widths=None, size=11,
           header=True, cell_fill=None):
    """House table: navy header, white/soft-blue banded body, horizontal
    borders, right-aligned numerics (col > 0). The built-in PowerPoint
    style ('Medium Style 2 - Accent 1', theme blue) is switched OFF --
    every color on the table is set here. cell_fill(r, c) may return an
    RGBColor to paint one cell (RAG chips, heat maps); dark fills flip the
    text white."""
    n_rows, n_cols = len(rows), len(rows[0])
    height = 0.32 * n_rows
    shape = slide.shapes.add_table(n_rows, n_cols, Inches(left), Inches(top),
                                   Inches(width), Inches(height))
    table = shape.table
    table.first_row = False
    table.horz_banding = False
    if col_widths:
        for i, cw in enumerate(col_widths):
            table.columns[i].width = Inches(cw)
    for r, row in enumerate(rows):
        table.rows[r].height = Inches(0.3)
        for c, value in enumerate(row):
            cell = table.cell(r, c)
            cell.margin_top = Inches(0.02)
            cell.margin_bottom = Inches(0.02)
            cell.margin_left = Inches(0.06)
            cell.margin_right = Inches(0.06)
            is_header = header and r == 0
            fill = None if is_header else (cell_fill(r, c) if cell_fill else None)
            cell.fill.solid()
            if is_header:
                cell.fill.fore_color.rgb = NAVY
            elif fill is not None:
                cell.fill.fore_color.rgb = fill
            elif r % 2 == 0:
                cell.fill.fore_color.rgb = BAND_FILL
            else:
                cell.fill.fore_color.rgb = WHITE
            _cell_bottom_border(cell)
            cell.text = str(value)
            para = cell.text_frame.paragraphs[0]
            para.alignment = PP_ALIGN.LEFT if c == 0 else PP_ALIGN.RIGHT
            dark = is_header or (fill is not None and str(fill) in _DARK_FILLS)
            for run in para.runs:
                run.font.size = Pt(size)
                run.font.name = BODY_FONT
                run.font.bold = is_header
                run.font.color.rgb = WHITE if dark else NAVY
    return shape


def _kicker(slide, _text_unused=None):
    """v4 identity pass: the bottom orange rule is retired -- the spine's
    wedge foot carries the accent now (mockup deck-12-preview-v5,
    approved 7-8/10). Kept as a no-op so slide builders stay unchanged;
    the so-what prose was already gone (James, issue #17)."""
    return

