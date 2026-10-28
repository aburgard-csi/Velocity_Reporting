# Ported from v5 02-Scripts/ars/deck/build.py at 7ba1e63. Logic unchanged; edits: the import of core.layout from kickoff/_v5/, and ORANGE read from RPE's brand (the same value; tests/test_brand_single_source.py). Here because the kickoff deck's deckkit facade imports it.
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

import shutil
from dataclasses import dataclass
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

from . import charts
from . import (attrition_slides, deposit_slides, formaudit, headlines, migration_slides,
               labels, polish, txn_slides)
from . import register as provenance
from ils_pipeline.kickoff._v5.core import layout
import brand

_HEADLINES = headlines

NAVY = RGBColor(0x00, 0x27, 0x4C)
ORANGE = brand.ORANGE_RGB
GREY = RGBColor(0x5A, 0x66, 0x70)
TINT = RGBColor(0x9D, 0xB8, 0xD2)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN_D = RGBColor(0x1E, 0x6E, 0x5E)   # semantic good (tiles, issue #41)
RED_D = RGBColor(0xC0, 0x39, 0x2B)     # semantic weak

HEAD_FONT = "Montserrat"
BODY_FONT = "Calibri"

SLIDE_W = 13.333
SLIDE_H = 7.5

# One grid for every slide (DESIGN/ spec): a single left margin and right
# edge, a rail floor, and separated kicker / footer bands.
SPINE_W = 0.85                             # the v4 navy identity spine
MARGIN_L = 1.18                            # body content clears the spine
RIGHT_EDGE = 12.71
CONTENT_W = RIGHT_EDGE - MARGIN_L          # 12.09
RAIL_BOTTOM = 6.62
RAIL_LEFT = 10.15                          # where _rail's tiles begin
RAIL_GUTTER = 0.28                         # clear air between chart and tiles
KICKER_RULE_Y = 6.78                       # text band 6.84-7.14
FOOTER_Y = 7.18
FOOTER_L = 0.91                            # right of the spine
DIVIDER_L = 1.0

# The 20-slide main path (DESIGN/deck-gallery.html, approved 2026-08-21).
# Entries are the stable topic labels (slide() fallbacks). Every OTHER
# tracked slide still builds -- it just moves behind the Appendix divider.
# Cover, agenda, exec one-pager, scorecard, takeaways, lists and the
# closer never demote. Edit this tuple like config.
# Main chapters in FINAL (post-reorder) order. One list drives the agenda
# AND the divider numerals so the two can never disagree. Chapters whose
# content lives in the appendix (Eligibility, New account profile) carry
# no numeral.
CHAPTER_ORDER = (
    "Campaign performance",
    "Debit card performance",
    "Reg E review",
    "Transaction intelligence",
)

MAIN_PATH = (
    # James's presented 1441 cut (issue #17, 2026-08-21): campaigns tell
    # the whole story first; economics detail lives in the appendix
    "The campaign hero",
    # the deferral slide follows the executive financial slide whenever a
    # tracker exists (James, 2026-08-22); no tracker -> skip-reported
    "The 2:1 guarantee",
    "Program reach",
    "Response and reach by offer",
    "Per-offer summary",
    # the legacy two-slide pair -- summary, then that mailer's spend and
    # swipe trajectory -- for the most recent mailing WITH DATA. Every
    # other mailer's pair stays in the Offer detail appendix
    # (James, 2026-08-24, issue #80)
    "The most recent mailer",
    "The most recent mailer trajectory",
    # the swipe-segment combo chart for the same wave, a different cut
    # (James, 2026-08-24)
    "The most recent offer",
    "Ladder and NU conversion by offer",
    "Lift by response segment",
    "Depth of engagement \u2014 repeat responders",
    "Organic versus program activation",
    "Debit card take rate",
    "Who does not carry a card",
    "Tier movement by response status",
    "Take rate by branch",
    "Branch scorecard",
    "Where branches diverge",
    "What deposits look like",
    "Who is paid here",
    "Who stopped being paid here",
    "When money last arrived",
    "Where the deposits sit",
    "Balance falling and inflow slowing",
    "What kind of income",
    "Tax refunds",
    "Who overdrafts, by how they are paid",
    "Who banks here first",
    "What arrives against what leaves",
    "Reg E opt-in",
    "Reg E opt-in by branch",
    "What a card and an opt-in earn",
    "Where the money goes",
    "Who competes for our members",
    "Where the outflow goes",
)

LAYOUT_BLANK = 0
LAYOUT_TITLE = 1
LAYOUT_SECTION = 3
LAYOUT_TITLE_ONLY = 6


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


def _slidenum(slide, left, top, width, height, size=9, bold=False,
              color=GREY, font=None, align=PP_ALIGN.LEFT):
    """A NATIVE slide-number field: PowerPoint renders the slide's live
    position, so deleting slides renumbers the deck by itself (James,
    2026-08-24 -- baked-in numbers forced manual renumbering)."""
    import uuid
    from lxml import etree
    box = slide.shapes.add_textbox(Inches(left), Inches(top),
                                   Inches(width), Inches(height))
    frame = box.text_frame
    frame.word_wrap = False
    para = frame.paragraphs[0]
    para.alignment = align
    a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    rgb = f"{color:06X}" if isinstance(color, int) else str(color)
    fld = etree.fromstring(
        f'<a:fld xmlns:a="{a}" id="{{{str(uuid.uuid4()).upper()}}}" '
        f'type="slidenum">'
        f'<a:rPr lang="en-US" sz="{int(size * 100)}" b="{int(bool(bold))}">'
        f'<a:solidFill><a:srgbClr val="{rgb}"/></a:solidFill>'
        f'<a:latin typeface="{font or BODY_FONT}"/></a:rPr>'
        f'<a:t>1</a:t></a:fld>')
    para._p.append(fld)
    return box


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


def _responses_caption(m, n) -> str:
    """The two drops between responses_total and reach_total, named.

    responses_total counts response EVENTS across the whole file -- an
    account that answered two offers counts twice. reach_total counts unique
    ACCOUNTS among the currently eligible. Captioning the first with the
    second made one tile carry two populations and two units, and four
    figures on the response story stopped reconciling (#86).
    """
    whole = m.get("reach_total_whole_file")
    if whole:
        return (f"response events; {whole:,} accounts, "
                f"{n('reach_total'):,} still eligible")
    return f"response events; {n('reach_total'):,} unique eligible accounts"


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


def _kpi_flat(slide, left, top, width, label, value, note=None):
    """A boxless KPI: label / value / note as plain text. James dropped
    the card boxes on the before/after slide (issue #28) -- the numbers
    carry themselves."""
    _text(slide, left, top, width, 0.28, label, size=11, bold=True,
          color=GREY, font=HEAD_FONT)
    _text(slide, left, top + 0.28, width, 0.5, value, size=20, bold=True,
          font=HEAD_FONT)
    if note:
        _text(slide, left, top + 0.80, width, 0.28, note, size=10, color=GREY)


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


def _tile(slide, left, top, width, value, label, note=None, rule=NAVY):
    """Dashboard stat tile (James, issue #41): a colored top rule, the
    number, its base label, a note. No box -- the rule carries the state."""
    from pptx.enum.shapes import MSO_SHAPE
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left),
                                 Inches(top), Inches(width), Inches(0.035))
    bar.fill.solid(); bar.fill.fore_color.rgb = rule
    bar.line.fill.background(); bar.shadow.inherit = False
    _text(slide, left, top + 0.10, width, 0.55, value, size=26, bold=True,
          font=HEAD_FONT, color=rule if rule in (RED_D, GREEN_D) else NAVY)
    _text(slide, left, top + 0.68, width, 0.28, label, size=12, bold=True)
    if note:
        _text(slide, left, top + 0.96, width, 0.28, note, size=10, color=GREY)


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


def _row_budget(top, rows_wanted, row_h=0.34, bottom=RAIL_BOTTOM):
    """How many body rows fit between `top` and the kicker band. Dense
    tables truncate to this with a 'top N of M shown' note instead of
    auto-growing into the footer."""
    return max(2, min(rows_wanted, int((bottom - top - 0.1) / row_h) - 1))


def _money(v) -> str:
    from .labels import money
    return money(v)


def _kicker(slide, _text_unused=None):
    """v4 identity pass: the bottom orange rule is retired -- the spine's
    wedge foot carries the accent now (mockup deck-12-preview-v5,
    approved 7-8/10). Kept as a no-op so slide builders stay unchanged;
    the so-what prose was already gone (James, issue #17)."""
    return


def _spine(slide, number, chapter=None):
    """The v4 identity spine on a content slide: full-height navy bar,
    white slot numeral, rotated chapter kicker (reads upward, letter-
    spaced), orange wedge foot. Drawn in the final pass, when the
    slide's deck position is known."""
    from pptx.enum.shapes import MSO_SHAPE
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0),
                                 Inches(SPINE_W), Inches(SLIDE_H))
    bar.fill.solid()
    bar.fill.fore_color.rgb = NAVY
    bar.line.fill.background()
    bar.shadow.inherit = False
    _slidenum(slide, 0, 0.14, SPINE_W, 0.5, size=24, bold=True,
              color="FFFFFF", align=PP_ALIGN.CENTER)
    if chapter:
        kick = _text(slide, SPINE_W / 2 - 1.4, 5.18, 2.8, 0.32,
                     str(chapter).upper(), size=8, bold=True, color=TINT,
                     align=PP_ALIGN.CENTER, wrap=False)
        kick.rotation = 270
        for para in kick.text_frame.paragraphs:
            for run in para.runs:
                run._r.get_or_add_rPr().set("spc", "300")
    _wedge(slide, [(0, SLIDE_H), (SPINE_W, SLIDE_H),
                   (SPINE_W, SLIDE_H - 0.52)], ORANGE)


SCORECARD_CAP = 9


def _scorecard_tally(card, cap: int = SCORECARD_CAP):
    """Count only the chips the slide actually paints (#71).

    The headline read its counts off the whole scorecard while the table
    rendered `cap` rows, and a grey row paints no chip at all -- so the
    promise ran ahead of the slide twice over. Returns (counts, rendered).
    """
    shown = list(card[:cap])
    counts = {"green": 0, "amber": 0, "red": 0}
    for row in shown:
        rag = str(row[5]).lower().strip() if len(row) > 5 else ""
        if rag in counts:
            counts[rag] += 1
    return counts, shown


def _reorder_to_appendix(prs, placed, main_path, chapter_divs):
    """Move tracked slides whose topic label is off the main path -- and
    any pre-Appendix chapter divider left with no main-path slides --
    behind the Appendix divider, preserving their relative order.
    Pure _sldIdLst element moves; relationships untouched."""
    slides = list(prs.slides)
    pos = {id(sl): i for i, sl in enumerate(slides)}
    appendix = next((sl for sl, t in chapter_divs if t == "Appendix"), None)
    appendix_pos = pos[id(appendix)] if appendix is not None else len(slides)

    demote: set[int] = set()
    kept_chapters: set[str] = set()
    entries = [e for e in placed if e["kind"] == "slide" and e.get("tracked")]
    ids = [e["tracked"] for e in entries]
    dupes = {t for t in ids if ids.count(t) > 1}
    if dupes:
        raise ValueError(f"duplicate tracked slide ids: {sorted(dupes)}")
    chapter_of: dict[int, str] = {}
    current = None
    for e in placed:
        if e["kind"] == "chapter":
            current = e["title"]
        elif e["kind"] == "slide":
            chapter_of[id(e["sl"])] = current
    for e in entries:
        if pos.get(id(e["sl"]), appendix_pos) >= appendix_pos:
            continue
        if e["tracked"] in main_path:
            kept_chapters.add(chapter_of.get(id(e["sl"])))
        else:
            demote.add(id(e["sl"]))
    for sl, title in chapter_divs:
        if title == "Appendix" or pos.get(id(sl), appendix_pos) >= appendix_pos:
            continue
        has_untracked = any(e["kind"] == "slide" and not e.get("tracked")
                            and chapter_of.get(id(e["sl"])) == title
                            for e in placed)
        if title not in kept_chapters and not has_untracked:
            demote.add(id(sl))

    sldIdLst = prs.slides._sldIdLst
    for i, el in enumerate(list(sldIdLst)):
        if id(slides[i]) in demote:
            sldIdLst.remove(el)
            sldIdLst.append(el)
    return demote


def _one_flow_cut(prs, placed, chapter_divs, main_path):
    """dividers:false -- the one-flow deck (James's 12-slide structure,
    #62). Chapter dividers are DELETED (the Appendix divider survives)
    and the kept main-path slides re-sequence into the manifest's exact
    order, directly after the cover: "main_path is in order" becomes
    literally true instead of filter-only."""
    rel_id = ("{http://schemas.openxmlformats.org/officeDocument/2006/"
              "relationships}id")
    slides = list(prs.slides)
    sldIdLst = prs.slides._sldIdLst
    # only MAIN-zone dividers go; the Appendix divider and the appendix's
    # own organizers (Offer detail, Transaction detail, ...) survive
    pos0 = {id(sl): i for i, sl in enumerate(slides)}
    apx = next((sl for sl, t in chapter_divs if t == "Appendix"), None)
    apx_pos = (pos0[id(apx)] if apx is not None and id(apx) in pos0
               else len(slides))
    doomed = {id(sl) for sl, t in chapter_divs
              if t != "Appendix" and pos0.get(id(sl), apx_pos) < apx_pos}
    for i, el in enumerate(list(sldIdLst)):
        if id(slides[i]) in doomed:
            prs.part.drop_rel(el.get(rel_id))
            sldIdLst.remove(el)
    placed[:] = [e for e in placed if id(e["sl"]) not in doomed]

    slides = list(prs.slides)
    pos = {id(sl): i for i, sl in enumerate(slides)}
    appendix = next((sl for sl, t in chapter_divs if t == "Appendix"), None)
    appendix_pos = (pos[id(appendix)]
                    if appendix is not None and id(appendix) in pos
                    else len(slides))
    by_tracked = {e["tracked"]: e["sl"] for e in placed
                  if e["kind"] == "slide" and e.get("tracked")}
    ordered = [by_tracked[t] for t in main_path
               if t in by_tracked
               and pos.get(id(by_tracked[t]), len(slides)) < appendix_pos]
    if not ordered:
        return
    elements = {id(slides[i]): el for i, el in enumerate(list(sldIdLst))}
    for sl in ordered:
        sldIdLst.remove(elements[id(sl)])
    for offset, sl in enumerate(ordered):        # anchor: after the cover
        sldIdLst.insert(1 + offset, elements[id(sl)])


MANIFEST_PATH = Path(__file__).resolve().parents[3] / "0_Config" / "deck_manifest.json"


def _load_manifest(warn, cut: str | None = None):
    """James's control surface (issue #17: 'i want some control over
    that'): 0_Config/deck_manifest.json overrides the built-in cut.

      main_path  -- tracked slide ids, in order; anything off the list
                    moves to the appendix (the standard demotion)
      exclude    -- tracked slide ids DELETED from the deck entirely
      chapters   -- main chapter titles, in order (numbering + agenda)
      cuts       -- named audiences; each may override any key above

    A named cut is manifest selection and nothing else -- one build, one set
    of numbers, a different set of slides promoted (#62). "The deck is too
    much but we can pair and slice"; this is the slicing. An id that is
    normally appendix simply appears in a cut's main_path, which promotes it.

    Unknown ids warn but never break the build. No file = the built-in
    MAIN_PATH / CHAPTER_ORDER."""
    if not MANIFEST_PATH.is_file():
        return None
    import json as _json
    try:
        mf = _json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        warn(f"deck_manifest.json unreadable ({type(exc).__name__}: {exc}); "
             f"using the built-in cut")
        return None
    if cut:
        mf = apply_cut(mf, cut, warn)
    return mf


def apply_cut(manifest: dict, cut: str, warn) -> dict:
    """The named cut's keys laid over the base manifest.

    Kept separate from the file read so the selection is testable without a
    manifest on disk.
    """
    cuts = manifest.get("cuts") or {}
    chosen = cuts.get(cut)
    if chosen is None:
        named = sorted(k for k in cuts if not k.startswith("_"))
        warn(f"deck cut {cut!r} is not in the manifest; using the standard "
             f"cut. Named cuts: {named}")
        return manifest
    merged = dict(manifest)
    for key, value in chosen.items():
        if not key.startswith("_"):
            merged[key] = value
    merged["_cut"] = cut
    return merged


def _remove_excluded(prs, placed, exclude: set):
    """Delete excluded tracked slides from the deck -- part and rel too."""
    doomed = {id(e["sl"]) for e in placed
              if e["kind"] == "slide" and e.get("tracked") in exclude}
    if not doomed:
        return
    slides = list(prs.slides)
    sldIdLst = prs.slides._sldIdLst
    rel_id = ("{http://schemas.openxmlformats.org/officeDocument/2006/"
              "relationships}id")
    for i, el in enumerate(list(sldIdLst)):
        if id(slides[i]) in doomed:
            prs.part.drop_rel(el.get(rel_id))
            sldIdLst.remove(el)
    placed[:] = [e for e in placed if id(e["sl"]) not in doomed]


def build(result, template: Path, out: Path,
          charts_dir: Path | None = None, dry_run: bool = False,
          cut: str | None = None) -> DeckResult:
    """Generate the ODD deck from an AnalysisResult."""
    if not result.metrics:
        raise ValueError("no metrics on the result; run the analysis first")
    # provenance (register.py): every key read is logged and handed to the
    # slide under construction; headline reads are captured exactly
    ledger = provenance.ReadLedger()
    m = ledger.add(provenance.TracedMetrics(result.metrics, source="ODD metrics"))
    placed: list = []         # dicts: sl/kind/title/sub/computed/tracked
    _prev_slide = lambda: next((e for e in reversed(placed)   # noqa: E731
                                if e["kind"] == "slide"), None)
    headlines = provenance.trace_headlines(
        _HEADLINES, m, on_unconsumed=lambda i: ledger.declined_from(_prev_slide, i))

    charts_dir = Path(charts_dir or out.parent / "charts")
    charts_dir.mkdir(parents=True, exist_ok=True)
    made, skipped = [], []

    prs = Presentation(str(template))
    # Keep the theme, masters and fonts; drop the demo content.
    #
    # Removing the sldId entry alone leaves the slide PART in the package,
    # so python-pptx then writes new slides under names that already exist
    # and the file carries both. Drop the relationship as well, which is
    # what actually detaches the part.
    xml_slides = prs.slides._sldIdLst
    rel_id = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    for sld in list(xml_slides):
        prs.part.drop_rel(sld.get(rel_id))
        xml_slides.remove(sld)

    def new(layout=LAYOUT_BLANK):
        slide = prs.slides.add_slide(prs.slide_layouts[layout])
        _strip_placeholders(slide)
        return slide

    client = f"{result.client_id} {result.client_name or ''}".strip()
    period = result.period
    data_month = m.get("data_month", "")

    # ---- 1. cover ------------------------------------------------------
    s = new(LAYOUT_BLANK)
    _text(s, 0.9, 2.5, 11.5, 1.0, "Account Revenue Solution", size=40,
          bold=True, font=HEAD_FONT)
    _text(s, 0.95, 3.6, 11.5, 0.6, client, size=24, color=ORANGE,
          font=HEAD_FONT)
    _text(s, 0.95, 4.3, 11.5, 0.5,
          f"Performance review  |  Data through {data_month}", size=15,
          color=GREY)

    def chart(name, fn, *a, **kw):
        target = charts_dir / f"{name}.png"
        # register (provenance): recorded even on a dry run, so the
        # chart -> file line exists before any chart is drawn
        if placed and placed[-1]["kind"] == "slide":
            try:
                rel = target.relative_to(out.parent).as_posix()
            except ValueError:
                rel = str(target)
            placed[-1]["charts"].append({"name": name,
                                         "fn": provenance.chart_label(fn),
                                         "file": rel})
        ledger.chart_seen()
        if dry_run:
            return None
        try:
            path = fn(*a, target, **kw)
            made.append(path)
            # form census (T3, review-trends.md): the chart fn that drew
            # the slide being built -- register() always precedes chart()
            if placed and placed[-1]["kind"] == "slide":
                placed[-1]["forms"].append(fn.__name__)
            return path
        except Exception as exc:
            # name the line, not just the type: "(IndexError)" sent a
            # whole run's worth of guessing to an issue (#245)
            import traceback as _tb
            frames = _tb.extract_tb(exc.__traceback__)
            where = (f" at {Path(frames[-1].filename).name}:{frames[-1].lineno}"
                     if frames else "")
            skipped.append(f"{name} chart ({type(exc).__name__}: {exc}{where})")
            return None

    story: list = []          # ("skipped", title, reason, False) entries only
    chapter_divs: list = []   # (slide_obj, title)

    no_footer: list = []      # slide objects that never carry a footer

    _chapter_now = [None]     # chapter identity, stamped at registration

    def register(sl, kind, title, sub=None, computed=True, tracked=False):
        if kind == "chapter":
            _chapter_now[0] = title
        entry = {"sl": sl, "kind": kind, "title": title, "sub": sub,
                 "computed": computed, "tracked": tracked,
                 "chapter": title if kind == "chapter" else _chapter_now[0],
                 "forms": [], "charts": []}
        ledger.assign(_prev_slide(), entry if kind == "slide" else None,
                      headlines.take(), m)
        placed.append(entry)

    def divider(title, subtitle=None):
        num = (chapter_order.index(title) + 1
               if title in chapter_order else None)
        sl = _divider(prs, new, title, number=num)
        chapter_divs.append((sl, title))
        no_footer.append(sl)
        register(sl, "chapter", title)
        return sl

    def slide(pair, fallback):
        sl = new()
        register(sl, "slide", pair[0] if pair else fallback,
                 pair[1] if pair and len(pair) > 1 else None,
                 bool(pair), tracked=fallback)
        return sl, _headed(sl, pair, fallback)

    def skip(title, *keys, reason=None):
        """A slide whose guard failed. Record the gap so the storyboard's
        'Not rendered' section shows what is absent and why, instead of the
        slide silently not existing."""
        reason = reason or ("missing " + ", ".join(keys))
        ledger.skip_seen(_prev_slide())
        story.append(("skipped", title, reason, False))
        skipped.append(f"{title} ({reason})")

    def n(key, default=0):
        return m.get(key, default) or default

    # The transaction chapter's metrics, read once: the agenda, the exec
    # one-pager and the chapter itself all need to know whether they exist.
    txn_t = None
    txn_path = out.parent / "txn_metrics.json"
    if txn_path.exists():
        try:
            import json as _json
            txn_t = ledger.add(provenance.TracedMetrics(
                _json.loads(txn_path.read_text(encoding="utf-8")),
                source="txn_metrics.json"))
        except Exception as exc:
            skipped.append(f"transaction chapter ({type(exc).__name__}: {exc})")

    # the effective main-chapter list for THIS deck: txn drops out when its
    # metrics are absent, and numbering stays gap-free. The deck manifest
    # (0_Config/deck_manifest.json) overrides both the chapter list and,
    # later, the main path -- James's control surface.
    manifest = _load_manifest(lambda msg: result.warn(msg), cut) or {}
    _CH_RENAMES = {"What the campaigns earned": "Campaign performance"}
    chapter_source = [_CH_RENAMES.get(c, c) for c in
                      (manifest.get("chapters") or CHAPTER_ORDER)]
    known_ch = set(CHAPTER_ORDER)
    bad_ch = [c for c in chapter_source if c not in known_ch]
    if bad_ch:
        result.warn(f"deck_manifest chapters not recognised (check "
                    f"spelling): {bad_ch}; known: {sorted(known_ch)}")
        chapter_source = CHAPTER_ORDER
    chapter_order = [c for c in chapter_source
                     if c != "Transaction intelligence"
                     or (txn_t and txn_t.get("fin_by_category"))]

    # ============ 3. agenda (from the chapters actually built) ===========
    # a one-flow deck (dividers:false, #62) carries no agenda slide
    if manifest.get("dividers", True):
        s = new()
        register(s, "slide", "Agenda")
        _title(s, "Agenda")
        chapters = list(chapter_order) + ["Appendix: supporting detail"]
        for idx, label in enumerate(chapters):
            _text(s, 1.3, 1.75 + idx * 0.74, 1.0, 0.6, f"{idx+1:02d}",
                  size=24, bold=True, color=ORANGE, font=HEAD_FONT)
            _text(s, 2.35, 1.83 + idx * 0.74, 9.5, 0.6, label, size=18,
                  color=NAVY, font=HEAD_FONT)

    # ============ CHAPTER 1 =============================================
    divider("Eligibility and the base",
            "who the program can reach, and how the funnel narrows")

    s, top = slide(headlines.population(m), "Eligible population")
    right = _rail(s, [
        ("Accounts", f"{n('n_total'):,}", "on file"),
        ("Eligible", f"{n('n_eligible'):,}", f"{n('eligibility_rate')}%"),
        ("Personal", f"{n('n_eligible_personal'):,}", "of eligible"),
        ("Business", f"{n('n_eligible_business'):,}", "of eligible"),
    ], top=top)
    path = chart("funnel", charts.funnel, m.get("eligibility_funnel") or [])
    if path:
        _chart_left(s, path, top, right)

    tiers = m.get("swipe_tier") or []
    if tiers:
        s, top = slide(headlines.swipe_usage(m), "Debit usage by swipe tier")
        total = m.get("swipe_tier_total") or [0, 0, 0, 0]
        nonuser = next((r for r in tiers if r[0] in ("Non-user", "No card")), None)
        right = _rail(s, [
            ("Cardholders", f"{n('n_eligible_with_debit'):,}", "of eligible"),
            ("Window", " ".join(m.get("swipe_window", [])[-1:]), "3-month avg"),
            ("Monthly spend", _money(total[1]), "across all tiers"),
        ], top=top)
        path = chart("tiers", charts.tier_bars, tiers)
        if path:
            _chart_left(s, path, top, right)

    else:
        skip("Debit usage by swipe tier", "swipe_tier")

    ticket = m.get("ticket_by_tier") or []
    if ticket:
        s, top = slide(headlines.ticket(m), "Average ticket by swipe tier")
        hi, lo = m.get("ticket_highest"), m.get("ticket_lowest")
        items = [("Blended", _money(m.get("ticket_blended")), "per swipe")]
        if hi: items.append(("Top tier", _money(hi[1]), str(hi[0])))
        if lo: items.append(("Bottom tier", _money(lo[1]), str(lo[0])))
        right = _rail(s, items, top=top)
        path = chart("ticket", charts.ticket_bars, ticket,
                     m.get("ticket_blended", 0))
        if path:
            _chart_left(s, path, top, right)

    else:
        skip("Average ticket by swipe tier", "ticket_by_tier")

    # ============ CHAPTER 2: mailer =====================================
    divider("Campaign performance",
             "who responds, what it moves, and what it costs to get")

    # ============ 1b. the campaign hero (DESIGN/ spec) ===================
    # The earned-dollars opener: hero number, response sparkline, four
    # icon-tagged tiles, control-honest kicker.
    hero_pair = headlines.hero(m)
    if hero_pair:
        s, top = slide(hero_pair, "The campaign hero")
        # the oversized hero number (DESIGN/ spec) -- profit when the
        # workbook is present, the held-spend figure otherwise
        if (m.get("gt_deferred_balance") or 0) > 1 \
                and m.get("gt_state") != "clear":
            big = _money((m.get("gt_revenue_ltd") or 0)
                         - (m.get("gt_paid_ltd") or 0))
            big_note = "earned over fees paid (2:1 guarantee, deferral tracker)"
        elif m.get("wb_profit_ltd") is not None:
            big, big_note = _money(m["wb_profit_ltd"]), \
                "program profit, life to date (ARS Workbook)"
        elif m.get("counterfactual_gap_total") is not None:
            big, big_note = _money(m["counterfactual_gap_total"]), \
                "spend held above the no-mail line"
        else:
            big, big_note = _money(m.get("ba_lift_net")), \
                "per responder-month over control"
        _text(s, MARGIN_L, top - 0.05, 5.4, 1.1, big, size=54, bold=True,
              font=HEAD_FONT, color=NAVY)
        _text(s, MARGIN_L + 0.06, top + 0.98, 5.4, 0.35, big_note,
              size=12, color=GREY)
        camp = [c for c in (m.get("campaign_rates") or []) if c[3] is not None]
        if camp:
            path = chart("hero_spark", charts.line_series,
                         [[str(c[0]), c[3]] for c in camp],
                         ylabel="response %", pct=True)
            if path:
                _fit_picture(s, path, 6.3, top - 0.05,
                             max_w=RIGHT_EDGE - 6.3, max_h=2.4)
        tiles = [
            ("mailing", "Responses", f"{n('responses_total'):,}",
             _responses_caption(m, n))
            if m.get("responses_total") else None,
            ("lift", "Lift vs control",
             f"{_money(m['ba_lift_net'])}/mo", "difference-in-differences")
            if m.get("ba_lift_net") is not None else None,
            ("shield", "Retention edge",
             f"{labels.signed(n('attrition_mailer_lift_pp'), '.1f')} pts",
             "responders close less")
            if m.get("attrition_mailer_lift_pp") is not None else None,
        ]
        tiles = [t for t in tiles if t][:4]
        nt = max(len(tiles), 1)
        kw = (CONTENT_W - 0.2 * (nt - 1)) / nt
        strip_top = top + 2.75
        for i, (kind, label, value, note) in enumerate(tiles):
            x = MARGIN_L + i * (kw + 0.2)
            _kpi(s, x, strip_top, kw, label, value, note,
                 accent=ORANGE if i == 0 else NAVY)
            if not dry_run:
                try:
                    ic = charts.icon(kind, charts_dir / f"icon_{kind}.png")
                    _fit_picture(s, ic, x + 0.1, strip_top + 0.08,
                                 max_w=0.32, max_h=0.32)
                except Exception:
                    pass
        _text(s, MARGIN_L + 0.02, 6.44, CONTENT_W, 0.3,
              "Where the control fell, the mailing's work was arresting "
                   "a decline \u2014 reported that way, every time.", size=9.5, color=GREY)
        _kicker(s)
    elif m.get("wb_found"):
        # the booked slot stayed empty on a client that HAS a workbook --
        # name the file, because the fix is on the file, not in the deck
        skip("The campaign hero",
             reason=(f"the booked frame is empty: workbook "
                     f"{m['wb_found']} did not read this run"))
    else:
        skip("The campaign hero", "counterfactual_gap_total")

    # ---- the 2:1 guarantee, right after the executive financial slide
    # (James, 2026-08-22) -- renders only when a tracker exists ----------
    gtm = m.get("gt_months") or []
    if gtm:
        s, top = slide(headlines.guarantee(m), "The 2:1 guarantee")
        kw = (CONTENT_W - 0.9) / 4
        state = str(m.get("gt_state", "")).replace("-", " ")
        tiles = [(_money(m.get("gt_deferred_balance")), "Deferred balance",
                  "forgiven at contract end", RED_D
                  if m.get("gt_state") == "in-guarantee" else NAVY),
                 (_money(m.get("gt_paid_ltd")), "Fees paid",
                  f"of {_money(m.get('gt_charges_ltd'))} billed", NAVY),
                 (f"{m.get('gt_ratio_latest', 0):.2f}x",
                  "Revenue vs billing, latest",
                  "guarantee releases at 2.00x", NAVY),
                 (state.title() or "-", "Status",
                  f"through {m.get('gt_latest_month', '')}",
                  GREEN_D if m.get("gt_state") == "clear" else NAVY)]
        for i, (value, label, note, rule) in enumerate(tiles):
            _tile(s, MARGIN_L + i * (kw + 0.3), top + 0.05, kw, value, label,
                  note, rule=rule)
        rows = [["Month", "Revenue", "Charges", "Paid", "Deferred",
                 "Running"]]
        for mth, rev, charges, paid, deferred, running in gtm[-9:]:
            rows.append([mth, _money(rev), _money(charges), _money(paid),
                         _money(deferred), _money(running)])
        _table(s, rows, MARGIN_L, top + 1.55, CONTENT_W,
               col_widths=[2.1, 2.0, 2.0, 2.0, 2.0, 1.9], size=10)
        _text(s, MARGIN_L + 0.02, 6.42, CONTENT_W, 0.3,
              f"Source: {m.get('gt_source', 'deferral tracker')}. While "
              f"revenue runs under 2x the charges the client pays half of "
              f"revenue; the rest defers, draws down above the mark, and "
              f"is forgiven at contract end.", size=9.5, color=GREY)
        _kicker(s)
    else:
        skip("The 2:1 guarantee", "gt_months (run with a deferral tracker present)")

    # ---- reach: how much of the base the program has touched ------------
    if m.get("reach_total") is not None and m.get("reach") is not None:
        # metric-first layout (James, issue #43 note on this slide): a
        # symmetric grid of the numbers with a brief line under each,
        # no chart competing with them
        s, top = slide(headlines.program_reach(m), "Program reach")
        tiles = [
            (f"{n('n_eligible'):,}", "Eligible accounts",
             "the base the program can reach", NAVY)
            if n("n_eligible") else None,
            (f"{n('n_ever_mailed'):,}", "Ever mailed",
             f"{100 * n('n_ever_mailed') / n('n_eligible'):.0f}% of eligible"
             if n("n_eligible") else "offered at least once", NAVY)
            if n("n_ever_mailed") else None,
            (f"{n('reach_total'):,}", "Responded",
             f"unique accounts, {str(m.get('reach_base') or 'eligible').lower()}",
             ORANGE),
            (f"{n('reach')}%", "Reach",
             f"of {str(m.get('reach_base') or 'eligible').lower()}", NAVY),
            (f"{n('reach_of_mailed')}%", "Of mailed",
             "ever responded", NAVY)
            if m.get("reach_of_mailed") is not None else None,
            (f"{n('reach_perml'):,.0f}", "Per offer",
             "new responders on average", NAVY)
            if m.get("reach_perml") is not None else None,
        ]
        tiles = [t for t in tiles if t][:6]
        cols = 3
        kw = (CONTENT_W - 0.6 * (cols - 1)) / cols
        for i, (value, label, note, rule) in enumerate(tiles):
            r_, c_ = divmod(i, cols)
            _tile(s, MARGIN_L + c_ * (kw + 0.6), top + 0.25 + r_ * 1.85,
                  kw, value, label, note, rule=rule)
        if m.get("responder_spend_share_pct") is not None:
            _text(s, MARGIN_L + 0.02, 6.42, CONTENT_W, 0.3,
                  f"Responders carry {n('responder_spend_share_pct')}% of "
                  f"card spend from "
                  f"{n('responder_share_of_eligible_pct', n('reach')):.0f}% "
                  f"of accounts.", size=10.5, color=GREY)
        _kicker(s)
    else:
        skip("Program reach", "reach")

    # ---- response rate and cumulative reach, one combo (issue #43) ------
    campaigns = m.get("campaign_rates") or []
    if campaigns:
        pair = headlines.waves(m)
        if pair:
            pair = (pair[0], "columns are each offer's response rate; the "
                             "line is cumulative reach of the eligible base")
        s, top = slide(pair, "Response and reach by offer")
        items = []
        best, worst = m.get("resprate_best"), m.get("resprate_worst")
        items.append(("Latest", f"{n('latest_resprate')}%",
                      str(m.get("latest_mailing", ""))))
        items.append(("Mean", f"{n('resprate_mean')}%", "all offers"))
        if best:
            items.append(("Highest", f"{best[1]:.1f}%", str(best[0])))
        if worst:
            items.append(("Lowest", f"{worst[1]:.1f}%", str(worst[0])))
        right = _rail(s, items, top=top)
        cum = [[r[0], r[2]] for r in (m.get("reach_cumulative") or [])]
        path = chart("resp_reach", charts.response_reach_combo,
                     [[c[0], c[3]] for c in campaigns if c[3] is not None],
                     cum)
        if path:
            _chart_left(s, path, top, right)
    else:
        skip("Response and reach by offer", "campaign_rates")

    # ---- per-offer summary: one table, response AND spend (issue #43:
    # James merged the per-mailer summary and the before/after slide) ----
    ba_by = {str(e["month"]): e for e in (m.get("before_after") or [])}
    if campaigns:
        pair = headlines.before_after(m) or headlines.per_mailer(m)
        s, top = slide(pair, "Per-offer summary")
        in_flight = m.get("in_flight_mailings") or []
        wbw = {str(w[0]): w for w in (m.get("wb_waves") or [])}
        has_wb = bool(wbw)
        has_ba = bool(ba_by)
        hdr = ["Offer", "Mailed", "Resp", "Response"]
        if has_ba:
            hdr += ["Resp $/mo", "Ctrl $/mo"]
        if has_wb:
            hdr += ["Rev to date"]
        rows = [hdr]
        for tag, mailed, resp, rate in campaigns[-7:]:
            row = [str(tag), f"{mailed:,}", f"{resp:,}", f"{rate}%"]
            if has_ba:
                e = ba_by.get(str(tag))
                row += ([f"{_money(e['resp_pre'])} \u2192 {_money(e['resp_post'])}",
                         f"{_money(e['ctrl_pre'])} \u2192 {_money(e['ctrl_post'])}"]
                        if e else ["\u2013", "\u2013"])
            if has_wb:
                w = wbw.get(str(tag))
                row += [_money(w[3]) if w and w[3] is not None else "\u2013"]
            rows.append(row)
        # totals across ALL completed offers -- the visible tie to the
        # workbook's program responder count
        t_mailed = sum(c[1] for c in campaigns)
        t_resp = sum(c[2] for c in campaigns)
        total_row = ["All offers", f"{t_mailed:,}", f"{t_resp:,}",
                     f"{(100 * t_resp / t_mailed):.1f}%" if t_mailed else "\u2013"]
        if has_ba:
            total_row += ["\u2013", "\u2013"]
        if has_wb:
            total_row += ["\u2013"]
        rows.append(total_row)
        ncol = len(hdr)
        widths = {4: [3.0, 3.0, 3.0, 3.1],
                  6: [1.9, 1.9, 1.7, 1.7, 2.5, 2.4],
                  5: [2.4, 2.4, 2.3, 2.3, 2.7],
                  7: [1.5, 1.5, 1.4, 1.4, 2.3, 2.3, 1.7]}
        _table(s, rows, MARGIN_L, top + 0.1, CONTENT_W,
               col_widths=widths.get(ncol), size=10.5)
        tbl_bottom = top + 0.1 + 0.34 * len(rows)
        note = (f"latest {min(7, len(campaigns))} of {len(campaigns)} "
                f"completed offers; spend is six months before each offer "
                f"against three after")
        if in_flight:
            note += f"; in flight: {', '.join(str(t) for t in in_flight[-2:])}"
        if has_wb:
            note += (". Rev to date is the wave's own To Date column in "
                     "the workbook, life of the offer")
        _text(s, MARGIN_L + 0.02, tbl_bottom + 0.08, CONTENT_W, 0.3,
              note + ".", size=9.5, color=GREY)
        kpis = []
        if m.get("ba_lift_net") is not None:
            kpis.append(("Net lift", f"{_money(m['ba_lift_net'])}/mo",
                         "vs control"))
        if m.get("ba_lift_pct") is not None:
            kpis.append(("Lift", f"{n('ba_lift_pct')}%", "responder spend"))
        if m.get("ba_spend_before") is not None:
            kpis.append(("Responders",
                         f"{_money(m['ba_spend_before'])} \u2192 "
                         f"{_money(m.get('ba_spend_after'))}", "pre to post"))
        if m.get("ba_control_before") is not None:
            kpis.append(("Control",
                         f"{_money(m['ba_control_before'])} \u2192 "
                         f"{_money(m.get('ba_control_after'))}", "pre to post"))
        if kpis:
            kw = (CONTENT_W - 0.3 * (len(kpis) - 1)) / len(kpis)
            k_top = max(tbl_bottom + 0.55, 5.15)
            for i, (label, value, note_) in enumerate(kpis):
                _kpi_flat(s, MARGIN_L + i * (kw + 0.3), k_top, kw,
                          label, value, note_)
            _text(s, MARGIN_L, min(k_top + 1.18, 6.44), CONTENT_W, 0.3,
                  "Responders are accounts that met an offer's goal; control "
                  "is mailed non-responders. Net lift is the responders' "
                  "pre-to-post change less the control's, per month.",
                  size=10, color=GREY)
        _kicker(s)
    else:
        skip("Per-offer summary", "campaign_rates")

    # ---- the response ladder and NU conversion, wave by wave ------------
    lw = m.get("ladder_by_wave") or []
    if lw:
        s, top = slide(headlines.ladder_waves(m),
                       "Ladder and NU conversion by offer")
        items = []
        moves = dict(m.get("ladder_movement") or [])
        if moves:
            items.append(("Moved up", f"{moves.get('Up', 0):,}",
                          "repeat responses"))
            items.append(("Same / down",
                          f"{moves.get('Same', 0):,} / {moves.get('Down', 0):,}",
                          "repeat responses"))
        if m.get("ladder_repeat_pct") is not None:
            items.append(("Repeat share", f"{n('ladder_repeat_pct')}%",
                          "of all responses"))
        if m.get("nu_conversion_pct") is not None:
            items.append(("NU conversion", f"{n('nu_conversion_pct')}%",
                          f"{m.get('nu_converted_ever', 0):,} of "
                          f"{m.get('nu_partial_ever', 0):,} partials"))
        right = _rail(s, items, top=top)
        path = chart("ladder_waves", charts.grouped_bars,
                     [str(r["wave"]) for r in lw[-10:]],
                     [r["first_time"] for r in lw[-10:]],
                     [r["repeat"] for r in lw[-10:]],
                     "first-time", "repeat")
        if path:
            _chart_left(s, path, top, right)
        _text(s, MARGIN_L + 0.02, 6.44, CONTENT_W, 0.3,
              "Movement is judged against each account's best prior "
                   "tier, so 'up' is real progression, not noise.", size=9.5, color=GREY)
        _kicker(s)
    else:
        skip("Ladder and NU conversion by offer", "ladder_by_wave")

    # ---- segment economics, pooled across waves -------------------------
    seg = [r for r in (m.get("segment_summary") or [])
           if r.get("did") is not None]
    if seg:
        s, top = slide(headlines.segment_traj(m), "Segment trajectories")
        items = []
        sbest = max(seg, key=lambda r: r.get("did_per_1000_mailed") or 0)
        items.append(("Best segment", str(sbest["segment"]),
                      f"{_money(sbest.get('did_per_1000_mailed'))}/1,000 mailed"))
        arrested = [r for r in seg if (r.get("did_from_control_pct") or 0) > 0]
        if arrested:
            worst_c = max(arrested,
                          key=lambda r: r.get("did_from_control_pct") or 0)
            items.append(("From control fall",
                          f"{worst_c['did_from_control_pct']:.0f}%",
                          f"of {worst_c['segment']}'s DiD"))
        if m.get("segment_ic_rate"):
            items.append(("IC rate", f"{m['segment_ic_rate']}",
                          "applied to DiD"))
        right = _rail(s, items, top=top)
        rows = [["Segment", "Offered", "Resp", "Resp d/mo", "Ctrl d/mo",
                 "DiD/mo", "$/1,000"]]
        for r in sorted(seg,
                        key=lambda r: -(r.get("did_per_1000_mailed") or 0))[:9]:
            rows.append([str(r["segment"]), f"{r.get('offered_n', 0):,}",
                         f"{r.get('response_rate', 0):.1f}%",
                         _money(r.get("resp_delta")), _money(r.get("non_delta")),
                         _money(r.get("did")),
                         _money(r.get("did_per_1000_mailed"))])
        _table(s, rows, MARGIN_L, top + 0.1, right - MARGIN_L - 0.25,
               col_widths=[1.3, 1.15, 1.05, 1.35, 1.35, 1.2, 1.5], size=10)
        _text(s, MARGIN_L + 0.02, 6.42, CONTENT_W, 0.3,
              "Incremental frame: interchange only, net of control; where "
              "the control fell, part of each DiD is decline arrested. Not "
              "comparable to the workbook's booked revenue: see Revenue "
              "frames.", size=9.5, color=GREY)
        _kicker(s)
    else:
        skip("Segment trajectories", "segment_summary")

    # ---- the penalty box: a rule audit, rendered only when broken -------
    pbv = m.get("penalty_box_violations")
    if pbv:
        s, top = slide(headlines.penalty(m), "The penalty box")
        items = [("Violations", f"{pbv:,}",
                  f"within {m.get('penalty_box_waves', 0)} mailers")]
        right = _rail(s, items, top=top)
        rows = [["Tier", "Same-tier repeats"]]
        for tier, cnt in (m.get("penalty_box_by_tier") or [])[:8]:
            rows.append([str(tier), f"{cnt:,}"])
        _table(s, rows, MARGIN_L, top + 0.1, right - MARGIN_L - 0.25,
               col_widths=[4.0, 4.0], size=10.5)
        _text(s, MARGIN_L + 0.02, 6.44, CONTENT_W, 0.3,
              "The program forbids repeating a tier this soon; a "
                   "non-zero count is a suppression gap, not a finding "
                   "about customers.", size=9.5, color=GREY)
        _kicker(s)
    elif pbv == 0:
        skip("The penalty box",
             reason="penalty_box_violations 0 -- rule held")
    else:
        skip("The penalty box", "penalty_box_violations")

    # ---- what a responder is worth, group by group ----------------------
    vr = m.get("value_by_response") or []
    if vr:
        s, top = slide(headlines.responder_value(m),
                       "What a responder is worth")
        items = []
        if m.get("value_responder_premium") is not None:
            items.append(("Responder premium",
                          _money(m["value_responder_premium"]),
                          "per account/yr, carded"))
        if m.get("value_responder_premium_ic") is not None:
            items.append(("From interchange",
                          _money(m["value_responder_premium_ic"]),
                          "of the premium"))
        if m.get("value_responder_premium_nsf") is not None:
            items.append(("From NSF/OD",
                          _money(m["value_responder_premium_nsf"]),
                          "of the premium"))
        if m.get("value_carded_portfolio_per_acct") is not None:
            items.append(("Carded book",
                          _money(m["value_carded_portfolio_per_acct"]),
                          "per account/yr"))
        right = _rail(s, items, top=top)
        carded_by = {r["group"]: r
                     for r in (m.get("value_by_response_carded") or [])}
        rows = [["Group", "Accounts", "Card take", "Value/acct",
                 "Carded only"]]
        for r in vr:
            c = carded_by.get(r["group"])
            rows.append([str(r["group"]), f"{r['n']:,}",
                         f"{r['take_rate']:.0f}%",
                         _money(r["value_per_acct"]),
                         _money(c["value_per_acct"]) if c else "-"])
        _table(s, rows, MARGIN_L, top + 0.1, right - MARGIN_L - 0.25,
               col_widths=[2.3, 1.5, 1.45, 1.7, 2.0], size=10.5)
        _text(s, MARGIN_L + 0.02, 6.44, CONTENT_W, 0.3,
              "Base: eligible personal accounts. The carded column "
                   "holds penetration at 100%, so what is left of the gap "
                   "is behaviour, not card ownership.", size=9.5, color=GREY)
        _kicker(s)
    else:
        skip("What a responder is worth", "value_by_response")

    # ---- spend against the no-program line ------------------------------
    cf_a = m.get("counterfactual_actual") or []
    cf_w = m.get("counterfactual_without") or []
    if cf_a and cf_w:
        s, top = slide(headlines.counterfactual(m), "The counterfactual")
        items = []
        if m.get("counterfactual_gap_latest") is not None:
            items.append(("Latest month",
                          _money(m["counterfactual_gap_latest"]),
                          "above the line"))
        if m.get("counterfactual_gap_total") is not None:
            items.append(("Cumulative", _money(m["counterfactual_gap_total"]),
                          "across the window"))
        if m.get("counterfactual_ic_total") is not None:
            items.append(("Interchange", _money(m["counterfactual_ic_total"]),
                          "earned on the gap"))
        right = _rail(s, items, top=top)
        gap_rows = [[a[0], a[1] - w[1]] for a, w in zip(cf_a, cf_w)]
        path = chart("counterfactual", charts.line_series, gap_rows,
                     ylabel="$ above the no-program line",
                     highlight_zero=True)
        if path:
            _chart_left(s, path, top, right)
        _text(s, MARGIN_L + 0.02, 6.44, CONTENT_W, 0.3,
              "The line is responders' own pre-spend moved by the "
                   "control's trajectory -- a DiD view, not a before/after.", size=9.5, color=GREY)
        _kicker(s)
    else:
        skip("The counterfactual", "counterfactual_actual")

    segs = m.get("segment_summary") or []
    if segs:
        s, top = slide(headlines.segments(m), "Which offer earns its postage")
        path = chart("segments", charts.segment_efficiency, segs)
        if path:
            _picture(s, path, top=top + 0.05, max_h=7.0 - top)

    else:
        skip("Which offer earns its postage", "segment_summary")

    if m.get("dot_n"):
        s, top = slide(headlines.dot_ask(m), "Transaction increase over the ask")
        # "At +40" lives on the segment slide (its own column and the
        # headline); its rail spot carries the #39 beat rate when measured
        beat_tile = (("Beat prior high", f"{n('dot_beat_high_pct'):.0f}%",
                      "set a new personal high")
                     if m.get("dot_beat_high_pct") is not None
                     else ("At +40", f"{n('dot_tail40'):,}", "or more"))
        right = _rail(s, [
            ("Responders", f"{n('dot_n'):,}", "measured"),
            ("Mean", labels.signed(n('dot_mean'), '.1f'),
             "swipes above prior"),
            ("Median", labels.signed(n('dot_median'), '.1f'),
             "swipes above prior"),
            beat_tile,
            ("Fell", f"{n('dot_fell_n'):,}", "below own baseline")
            if m.get("dot_fell_n") is not None else None,
        ], top=top)
        path = chart("overask", charts.histogram, m.get("dot_hist") or [],
                     mean=m.get("dot_mean"), median=m.get("dot_median"))
        if path:
            _chart_left(s, path, top, right)

    # ---- who delivers the lift: the same cut per response tier ----------
    seg = m.get("dot_by_segment") or []
    if seg:
        s, top = slide(headlines.dot_segments(m), "Lift by response segment")
        rows = [["Tier", "Pairs", "Mean lift", "Median", "% increased",
                 "At +40", "Beat prior high"]]
        for r in seg[:6]:
            beat = (f"{r[6]:.0f}%" if len(r) > 6 and r[6] is not None
                    else "n/a")
            rows.append([str(r[0]), f"{r[1]:,}", f"{r[2]:+.1f}",
                         f"{r[3]:+.1f}", f"{r[4]:.0f}%", f"{r[5]:,}", beat])
        _table(s, rows, MARGIN_L, top + 0.15, 11.9,
               col_widths=[1.9, 1.5, 1.7, 1.5, 1.8, 1.5, 2.0], size=11)
        _text(s, MARGIN_L + 0.02, top + 0.15 + 0.34 * len(rows) + 0.25,
              10.5, 0.4,
              "Lift is each account's swipes over its own prior run rate; "
              "tier is the goal the response achieved. Beat prior high: "
              "share of pairs whose post-mail months set a new personal "
              "swipe high.",
              size=10.5, color=GREY)
    else:
        skip("Lift by response segment", "dot_by_segment")

    if m.get("depth"):
        # metric-first (James, issue #43): the numbers across the top in
        # the clean tile grid, the donut centered below them
        s, top = slide(None, "Depth of engagement — repeat responders")
        d = m["depth"]
        tiles = [(f"{d[0]:,}", "Responded once", "took exactly one offer",
                  NAVY),
                 (f"{d[1]:,}", "Responded twice", "came back for a second",
                  NAVY),
                 (f"{d[2]:,}", "Three or more", "the habitual responders",
                  NAVY),
                 (f"{n('depth_repeat_pct')}%", "Repeat rate",
                  "of all responders", ORANGE)]
        kw = (CONTENT_W - 0.9) / 4
        for i, (value, label, note, rule) in enumerate(tiles):
            _tile(s, MARGIN_L + i * (kw + 0.3), top + 0.05, kw, value,
                  label, note, rule=rule)
        path = chart("depth", charts.donut,
                     [["Once", d[0]], ["Twice", d[1]], ["3 or more", d[2]]],
                     center_value=f"{n('depth_repeat_pct')}%",
                     center_label="responded again")
        if path:
            _fit_picture(s, path, 2.9, top + 1.6, max_w=7.4,
                         max_h=6.6 - (top + 1.6))
        _kicker(s)





    # ---- first swipes: onboarding, mail, or on their own ----------------
    if m.get("activation_l12m_n") is not None and             m.get("activation_existing_n") is not None:
        s, top = slide(headlines.activation_split(m),
                       "Organic versus program activation")
        tiles = [(f"{n('activation_l12m_n'):,}", "First swipes",
                  "last 12 months", NAVY)]
        if m.get("activation_program_pct") is not None:
            tiles.append((f"{n('activation_program_pct'):.0f}%",
                          "Program share", "of existing activations",
                          ORANGE))
        if m.get("activation_organic_n") is not None:
            tiles.append((f"{n('activation_organic_n'):,}", "Organic",
                          "swiped without ever being mailed", NAVY))
        kw = (CONTENT_W - 0.6 * (len(tiles) - 1)) / max(len(tiles), 1)
        for i, (value, label, note, rule) in enumerate(tiles):
            _tile(s, MARGIN_L + i * (kw + 0.6), top + 0.05, kw, value,
                  label, note, rule=rule)
        bars = [["New accounts", m.get("activation_new_account_n")],
                ["Mailed, then swiped", m.get("activation_program_n")],
                ["Organic", m.get("activation_organic_n")]]
        bars = [b for b in bars if b[1]]
        if bars:
            path = chart("activation", charts.composition, bars,
                         highlight="Mailed, then swiped")
            if path:
                _fit_picture(s, path, MARGIN_L, top + 1.75,
                             max_w=CONTENT_W, max_h=6.5 - (top + 1.75))
        _kicker(s)
    else:
        skip("Organic versus program activation", "activation_l12m_n")


    offsets = m.get("cohort_offsets") or []
    indexed = m.get("cohort_indexed") or {}
    if offsets and indexed:
        s, top = slide(headlines.cohort(m), "What a response does to spend")
        # ---- James's lines (#62): the legacy combo, pooled + extended --
        seg_det = m.get("cohort_seg_detail") or {}
        if seg_det.get("segments"):
            sc_pair = headlines.seg_combo(m)
            s2, top2 = slide(sc_pair, "Behavior by segment around the offer")
            path2 = chart("seg_combo", charts.combo_lines, seg_det)
            if path2:
                _fit_picture(s2, path2, MARGIN_L, top2 + 0.05,
                             max_w=CONTENT_W, max_h=6.35 - (top2 + 0.05))
            _kicker(s2)
        else:
            skip("Behavior by segment around the offer", "cohort_seg_detail")

        # ---- the comps: responders vs control, spend by response tier --
        tiers_tr = m.get("cohort_spend_by_tier") or {}
        big = {t: s for t, s in tiers_tr.items()
               if (m.get("cohort_tier_n") or {}).get(t, 0) >= 50}
        tr_pair = headlines.trajectory(m, "spend")
        if big and tr_pair:
            s2, top2 = slide(tr_pair, "Responders versus control around the offer")
            ctrl = (m.get("cohort_spend") or {}).get("mailed_nonresp")
            path2 = chart("traj_spend", charts.trajectory_lines,
                          m.get("cohort_offsets") or [], big, ctrl,
                          ylabel="$ per account per month")
            if path2:
                _fit_picture(s2, path2, MARGIN_L, top2 + 0.1,
                             max_w=CONTENT_W, max_h=6.3 - (top2 + 0.1))
            bases = ", ".join(f"{t} {n_:,}" for t, n_ in sorted(
                (m.get("cohort_tier_n") or {}).items()) if t in big)
            _text(s2, MARGIN_L + 0.02, 6.5, CONTENT_W, 0.28,
                  f"Responder pairs per tier: {bases}; tiers under 50 "
                  f"pairs pooled out; control = mailed non-responders",
                  size=9.5, color=GREY)
            _kicker(s2)
        else:
            skip("Responders versus control around the offer",
                 "cohort_spend_by_tier")

        path = chart("cohort", charts.cohort_trajectory, offsets, indexed,
                     indexed=True)
        if path:
            _picture(s, path, top=top + 0.05, max_h=7.0 - top)

    if m.get("sustained_index"):
        s, top = slide(headlines.sustained(m), "Sustained responder activity")
        above = m.get("sustained_months_above")
        right = _rail(s, [
            ("Months above", f"{above}", "of 12 tracked"),
            ("At +6", f"{dict(m['sustained_index']).get(6, 0):+.0f}%",
             "vs own baseline"),
            ("At +12", f"{dict(m['sustained_index']).get(12, 0):+.0f}%",
             "vs own baseline"),
        ], top=top)
        path = chart("sustained", charts.line_series,
                     [[f"+{r[0]}", r[1]] for r in m["sustained_index"]],
                     ylabel="vs pre-mail baseline", pct=True,
                     highlight_zero=True)
        if path:
            _chart_left(s, path, top, right)

    if m.get("ladder_repeat") is not None:
        s, top = slide(None, "First-time versus repeat responders")
        mv = dict(m.get("ladder_movement") or [])
        right = _rail(s, [
            ("First-time", f"{n('ladder_first_time'):,}", "offers 2 onward"),
            ("Repeat", f"{n('ladder_repeat'):,}", f"{n('ladder_repeat_pct')}%"),
            ("Moved up", f"{mv.get('Up', 0):,}", "vs prior peak"),
            ("Moved down", f"{mv.get('Down', 0):,}", "vs prior peak"),
        ], top=top)
        path = chart("ladder", charts.tier_bars,
                     [["Moved up", mv.get("Up", 0)],
                      ["Same tier", mv.get("Same", 0)],
                      ["Moved down", mv.get("Down", 0)]])
        if path:
            _chart_left(s, path, top, right)

    if m.get("nu_partial_ever"):
        s, top = slide(None, "Do partial responders convert?")
        right = _rail(s, [
            ("Ever NU 1-4", f"{n('nu_partial_ever'):,}", "fell short"),
            ("Converted", f"{n('nu_converted_ever'):,}",
             f"{n('nu_conversion_pct')}%"),
            ("Never", f"{n('nu_never_converted'):,}", "still short"),
        ], top=top)
        path = chart("nuconv", charts.tier_bars,
                     [["Converted to NU 5+ or TH", n("nu_converted_ever")],
                      ["Never converted", n("nu_never_converted")]])
        if path:
            _chart_left(s, path, top, right)

    # Age and balance were twin slides: the same grouped-bar form, the same
    # rail, back to back. One slide, two panels (#53 P1).
    ages = m.get("age") or []
    bal_profile = m.get("balance_profile") or []
    if ages or bal_profile:
        s, top = slide(headlines.age_balance_profile(m),
                       "Who responds — age and balance")
        items = []
        if ages:
            items += [("Under 25", f"{n('age_u25_rate')}%", "respond"),
                      ("65 plus", f"{n('age_o65_rate')}%", "respond")]
        if bal_profile:
            items += [("Responder", _money(m.get("bal_resp_med")), "median balance"),
                      ("Non-responder", _money(m.get("bal_non_med")),
                       "median balance")]
        right = _rail(s, items, top=top)
        path = chart("resp_profile", charts.profile_twins, ages, bal_profile)
        if path:
            _chart_left(s, path, top, right)

    # ---- the responder in one column, the non-responder in the next -----
    prof = m.get("responder_profile") or {}
    prof_rows = {k: v for k, v in prof.items()
                 if not k.startswith("_") and isinstance(v, list)
                 and len(v) == 2}
    if prof_rows:
        s, top = slide(headlines.responder_profile(m),
                       "Who responds — the profile")
        items = []
        if m.get("depth_repeat_pct") is not None:
            items.append(("Repeat responders", f"{n('depth_repeat_pct')}%",
                          "responded 2+ times"))
        grouping = m.get("response_grouping") or {}
        if grouping:
            top_grp = max(grouping.items(), key=lambda kv: kv[1])
            items.append(("Largest group", labels.clip(top_grp[0], 16),
                          f"{top_grp[1]:,} responders"))
        right = _rail(s, items, top=top) if items else 12.35
        heads = {"balance_median": ("Median balance", _money),
                 "holder_age_median": ("Median holder age",
                                       lambda v: f"{v:.0f}"),
                 "debit_pct": ("Carry a debit card",
                               lambda v: f"{v:.0f}%"),
                 "spend_per_mo": ("Debit spend / month",
                                  lambda v: f"{_money(v)}/mo")}
        cols = [str(c).capitalize()
                for c in (prof.get("_columns")
                          or ["responders", "non-responders"])]
        rows = [[""] + cols[:2]]
        for key, pair in prof_rows.items():
            label, fmt = heads.get(key, (key.replace("_", " "), str))
            rows.append([label, fmt(pair[0]), fmt(pair[1])])
        table_w = min(right - MARGIN_L - 0.25, 7.2)
        _table(s, rows, MARGIN_L, top + 0.1, table_w,
               col_widths=[2.8, 2.2, 2.2], size=10.5)
        raa = m.get("response_account_age") or []
        if raa:
            y = top + 0.1 + 0.32 * len(rows) + 0.2
            path = chart("resp_acct_age", charts.grouped_bars,
                         [r[0] for r in raa], [r[1] for r in raa],
                         [r[2] for r in raa], "mailed", "responded")
            if path:
                _chart_left(s, path, y, right, max_h=7.0 - y - 0.3)
    else:
        skip("Who responds — the profile", "responder_profile")

    # ============ CHAPTER 3: debit card =================================
    divider("Debit card performance",
             "penetration, where it lags, and what a card is worth")

    # ---- the operational dashboard that opens the chapter (issue #41) ---
    td_pair = headlines.take_dashboard(m)
    if td_pair:
        s, top = slide(td_pair, "Debit card take rate")
        kw = (CONTENT_W - 0.9) / 4
        n_elig = n("n_eligible")
        tiles = [(f"{n('dctr_overall'):.1f}%", "Overall, eligible",
                  f"{n_elig:,} accounts", NAVY),
                 (f"{n('dctr_l12m'):.1f}%", "Last 12 months",
                  f"{n('dctr_l12m_vs_hist_pp'):+.1f} pts vs book",
                  GREEN_D if n("dctr_l12m_vs_hist_pp") >= 0 else RED_D),
                 (f"{n('dctr_personal'):.1f}%", "Eligible personal",
                  f"{n('n_dctr_personal'):,} accounts", NAVY),
                 (f"{n('dctr_business'):.1f}%", "Eligible business",
                  f"{abs(n('dctr_business') - n('dctr_overall')):.1f} pts "
                  f"{'below' if n('dctr_business') < n('dctr_overall') else 'above'} book",
                  RED_D if n("dctr_business") < n("dctr_overall") - 10 else NAVY)]
        for i, (value, label, note, rule) in enumerate(tiles):
            _tile(s, MARGIN_L + i * (kw + 0.3), top + 0.05, kw, value, label,
                  note, rule=rule)
        bal = [r for r in (m.get("dctr_balance") or []) if r[1]]
        if bal:
            _text(s, MARGIN_L, top + 1.45, CONTENT_W, 0.28,
                  "Take rate by account balance", size=12, bold=True,
                  font=HEAD_FONT)
            path = chart("take_dash_balance", charts.rate_bars, bal)
            if path:
                _fit_picture(s, path, MARGIN_L, top + 1.78,
                             max_w=CONTENT_W, max_h=6.55 - (top + 1.78))
        spread = m.get("dctr_branch_spread_pp")
        base_note = f"Base: {n_elig:,} eligible accounts."
        if spread is not None and m.get("dctr_branch_best"):
            b, w = m["dctr_branch_best"], m["dctr_branch_worst"]
            base_note += (f" Branch spread runs {spread:.1f} pts, "
                          f"{b[0]} {b[1]:.1f}% to {w[0]} {w[1]:.1f}%.")
        _text(s, MARGIN_L + 0.02, 6.55, CONTENT_W, 0.28, base_note,
              size=9.5, color=GREY)
        _kicker(s)
    else:
        skip("Debit card take rate", "dctr_overall + dctr_l12m")

    # ---- Operational KPIs: slot 5 of James's 12-slide cut (#62) ---------
    ok_pair = headlines.ops_kpis(m)
    take_rows_j = {r[0]: r for r in (m.get("take_branch") or [])}
    rege_rows_j = {r[0]: r for r in (m.get("rege_branch") or [])}
    ops_join = [[b, int(take_rows_j[b][2]), float(take_rows_j[b][3]),
                 float(rege_rows_j[b][3])]
                for b in take_rows_j if b in rege_rows_j
                and take_rows_j[b][3] is not None
                and rege_rows_j[b][3] is not None]
    if ok_pair and ops_join:
        s, top = slide(ok_pair, "Operational KPIs")
        kw = (CONTENT_W - 0.9) / 4
        tiles = [(f"{n('dctr_overall'):.1f}%", "Take rate, overall",
                  f"of {n('n_eligible'):,} eligible", NAVY),
                 (f"{n('dctr_l12m'):.1f}%", "Take rate, last 12 mo",
                  f"{n('dctr_l12m_vs_hist_pp'):+.1f} pts vs book",
                  GREEN_D if n("dctr_l12m_vs_hist_pp") >= 0 else RED_D),
                 (f"{n('rege_pct'):.1f}%", "Reg E opt-in, overall",
                  f"of {n('rege_pool'):,} elig. personal w/debit", NAVY),
                 (f"{n('rege_pct_of_elected'):.1f}%", "Reg E, of electors",
                  "excludes the never-asked pool", NAVY)]
        for i, (value, label, note, rule) in enumerate(tiles):
            _tile(s, MARGIN_L + i * (kw + 0.3), top + 0.05, kw, value,
                  label, note, rule=rule)
        ops_join.sort(key=lambda r: -r[1])
        shown = ops_join[:8]
        path = chart("ops_kpis", charts.ops_kpi_columns, shown,
                     float(n("dctr_overall")), float(n("rege_pct")))
        if path:
            _fit_picture(s, path, MARGIN_L, top + 1.5,
                         max_w=CONTENT_W, max_h=6.35 - (top + 1.5))
        cov = (f"largest {len(shown)} of {len(ops_join)} branches by "
               f"eligible accounts; " if len(ops_join) > len(shown) else "")
        _text(s, MARGIN_L + 0.02, 6.5, CONTENT_W, 0.28,
              cov + "counts under each branch; full per-branch charts in "
              "the appendix", size=9.5, color=GREY)
        _kicker(s)
    else:
        skip("Operational KPIs", "take_branch", "rege_branch")

    # ---- who is left without a card (issue #41 added slide) -------------
    nc_pair = headlines.no_card(m)
    if nc_pair:
        s, top = slide(nc_pair, "Who does not carry a card")
        holder = [r for r in (m.get("dctr_holder_age") or []) if r[1]]
        tenure = [r for r in (m.get("dctr_account_age") or []) if r[1]]
        half = (CONTENT_W - 0.5) / 2
        if holder:
            _text(s, MARGIN_L, top + 0.05, half, 0.28,
                  "Take rate by holder age", size=12, bold=True,
                  font=HEAD_FONT)
            path = chart("nocard_holder", charts.rate_bars, holder)
            if path:
                _fit_picture(s, path, MARGIN_L, top + 0.38, max_w=half,
                             max_h=6.4 - (top + 0.38))
        if tenure:
            tx = MARGIN_L + half + 0.5
            _text(s, tx, top + 0.05, half, 0.28,
                  "Take rate by account tenure", size=12, bold=True,
                  font=HEAD_FONT)
            path = chart("nocard_tenure", charts.rate_bars, tenure)
            if path:
                _fit_picture(s, path, tx, top + 0.38, max_w=half,
                             max_h=6.4 - (top + 0.38))
        _text(s, MARGIN_L + 0.02, 6.5, CONTENT_W, 0.28,
              "Counts under each column are the band's eligible accounts; "
              "holders without a parseable age are excluded from age cuts.",
              size=9.5, color=GREY)
        _kicker(s)
    else:
        skip("Who does not carry a card", "dctr_holder_age / dctr_account_age")

    # ---- tier movement by response status (issue #41 image spec) --------
    tm_pair = headlines.tier_movement(m)
    if tm_pair:
        s, top = slide(tm_pair, "Tier movement by response status")
        path = chart("tier_movement", charts.stacked_movement,
                     m.get("mig_by_group") or [])
        if path:
            _picture(s, path, top=top + 0.15, max_h=6.4 - top)
        _text(s, MARGIN_L + 0.02, 6.5, CONTENT_W, 0.28,
              "Movement compares each account's swipe tier in its first "
              "and latest window on file; bases differ by group and are "
              "printed on each bar.", size=9.5, color=GREY)
        _kicker(s)
    else:
        skip("Tier movement by response status", "mig_by_group")

    branches = m.get("take_branch") or []
    if branches:
        s, top = slide(headlines.take_rate(m), "Take rate by branch")
        # James (issue #41): more branches, and the account base under
        # each column
        path = chart("branch", charts.branch_bars, branches,
                     m.get("dctr_overall", 0), top=20, show_n=True)
        if path:
            _picture(s, path, top=top + 0.05, max_h=6.35 - top)
        _text(s, MARGIN_L + 0.02, 6.44, CONTENT_W, 0.3,
              "Take rate = share of each branch's eligible accounts holding "
              "a debit card; the count beside each name is that base.",
              size=9.5, color=GREY)
        _kicker(s)

    else:
        skip("Take rate by branch", "take_branch")

    # ---- the same take rate, month by month -----------------------------
    matrix = m.get("dctr_branch_monthly") or []
    tags = m.get("dctr_monthly_months") or []
    if matrix and tags:
        s, top = slide(headlines.branch_month(m),
                       "Take rate by branch and month")
        cell_w = round((12.1 - 2.6) / max(1, len(tags)), 2)
        rows = [["Branch", "Accts"] + [str(t) for t in tags]]
        for r in matrix[:_row_budget(top, 8)]:
            rows.append([labels.clip(r[0], 14), f"{r[1]:,}"] +
                        [f"{v:.0f}" if v is not None else "–"
                         for v in r[2:]])
        totals = m.get("dctr_monthly_totals") or []
        if totals:
            rows.append(["All branches", ""] +
                        [f"{v:.0f}" if v is not None else "–"
                         for v in totals])
        raw_by_cell = {}
        base_by_col = {c + 2: (totals[c] if c < len(totals) else None)
                       for c in range(len(tags))} if totals else {}
        for ri, r in enumerate(matrix[:_row_budget(top, 8)], start=1):
            for ci, v in enumerate(r[2:], start=2):
                raw_by_cell[(ri, ci)] = v

        def _heat(r, c):
            v = raw_by_cell.get((r, c))
            base = base_by_col.get(c)
            if v is None or base is None:
                return None
            if v >= base + 3:
                return NAVY
            if v >= base - 1:
                return RGBColor(0x7B, 0x9B, 0xB8)
            if v >= base - 6:
                return RGBColor(0xCF, 0xDB, 0xE8)
            return BAND_FILL

        _table(s, rows, MARGIN_L, top + 0.1, 12.1,
               col_widths=[1.7, 0.9] + [cell_w] * len(tags), size=9.5,
               cell_fill=_heat)
        _text(s, MARGIN_L + 0.02, top + 0.1 + 0.32 * len(rows) + 0.08, 11.8, 0.3,
              "new-account take rate (%) vs the all-branch month: dark = above, "
              "pale = behind; largest branches by new accounts",
              size=10, color=GREY)
    else:
        skip("Take rate by branch and month", "dctr_branch_monthly")

    summary = m.get("dctr_summary") or []
    if summary:
        s, top = slide(headlines.take_by_base(m), "Take rate by base")
        right = _rail(s, [
            ("Personal", f"{n('dctr_personal')}%", "eligible personal"),
            ("Business", f"{n('dctr_business')}%", "eligible business"),
            ("Last 12 mo", f"{n('dctr_l12m')}%", "newly opened"),
            ("vs history", f"{n('dctr_l12m_vs_hist_pp'):+.1f} pts", "trend"),
        ], top=top)
        path = chart("dctr_base", charts.tier_bars,
                     [[r[0], r[4]] for r in summary], value_idx=1,
                     share=False, fmt="{:.0f}%")
        if path:
            _chart_left(s, path, top, right)

    else:
        skip("Take rate by base", "dctr_summary")

    leak_rows = m.get("dctr_leaks") or []
    if leak_rows:
        s, top = slide(headlines.leaks(m), "Where cards do not follow volume")
        path = chart("leaks", charts.leak_bars, leak_rows, unit="cards")
        if path:
            _picture(s, path, top=top + 0.05, max_h=7.0 - top)

    else:
        skip("Where cards do not follow volume", "dctr_leaks")

    if m.get("spend_swipe_series"):
        s, top = slide(headlines.spend_trend(m), "Overall debit swipes and spend")
        right = _rail(s, [
            ("Spend YoY", f"{n('spend_yoy_pct'):+.1f}%", "vs same month"),
            ("Swipes YoY", f"{n('swipes_yoy_pct'):+.1f}%", "vs same month"),
        ], top=top)
        path = chart("spendswipe", charts.dual_series, m["spend_swipe_series"])
        if path:
            _chart_left(s, path, top, right)

    if m.get("nsf_series"):
        s, top = slide(headlines.nsf_trend(m), "NSF and overdraft activity")
        right = _rail(s, [
            ("Items", f"{n('nsf_last_items'):,}", "latest month"),
            ("Accounts", f"{n('nsf_last_accts'):,}", "with activity"),
            ("Year on year", f"{n('nsf_yoy'):+.0f}%", "items"),
        ], top=top)
        path = chart("nsf", charts.line_series,
                     [[r[0], r[1]] for r in m["nsf_series"]], ylabel="items")
        if path:
            _chart_left(s, path, top, right)

    # ---- value per account, branch by branch ----------------------------
    vb = m.get("value_by_branch") or []
    if len(vb) >= 2:
        s, top = slide(headlines.branch_value(m), "Value per account by branch")
        items = []
        vbest, vworst = m.get("value_branch_best"), m.get("value_branch_worst")
        if vbest:
            items.append(("Top branch", _money(vbest["value_per_acct"]),
                          labels.clip(vbest["group"], 16)))
        if vworst:
            items.append(("Bottom branch", _money(vworst["value_per_acct"]),
                          labels.clip(vworst["group"], 16)))
        if m.get("value_branch_spread") is not None:
            items.append(("Spread", _money(m["value_branch_spread"]),
                          "per account/yr"))
        if m.get("value_branch_penetration_share") is not None:
            items.append(("From cards",
                          f"{n('value_branch_penetration_share'):.0f}%",
                          "of the spread"))
        # James (issue #41): larger chart -- full width, no rail; the
        # revenue qualified and the head count under each column
        path = chart("value_branch", charts.branch_bars,
                     [[r["group"], None, r["n"], r["value_per_acct"]]
                      for r in vb],
                     m.get("value_portfolio_per_acct") or 0, fmt="${:,.0f}",
                     top=16, show_n=True)
        if path:
            _picture(s, path, top=top + 0.05, max_h=6.35 - top)
        qual = ("Value = interchange plus NSF/OD fee revenue per eligible "
                "account per year; counts under each column are the "
                "branch's eligible accounts")
        for label, key in (("Spread", "value_branch_spread"),):
            if m.get(key) is not None:
                qual += (f". Spread {_money(m[key])}/acct")
        if m.get("value_branch_penetration_share") is not None:
            qual += (f"; {n('value_branch_penetration_share'):.0f}% of it "
                     f"follows card penetration")
        _text(s, MARGIN_L + 0.02, 6.5, CONTENT_W, 0.28, qual + ".",
              size=9.5, color=GREY)
        _kicker(s)
    else:
        skip("Value per account by branch", "value_by_branch")

    # ---- the value ladder: tenure on the way up, potential at the top ---
    va = m.get("value_by_account_age") or []
    if len(va) >= 2:
        s, top = slide(headlines.value_ladder(m), "The value ladder")
        items = []
        step = m.get("value_age_biggest_step")
        if step:
            items.append(("Biggest step", _money(step["step"]),
                          f"{step['from']} → {step['to']}"))
        if m.get("value_per_card") is not None:
            items.append(("Per card", _money(m["value_per_card"]),
                          "per account/yr"))
        if m.get("value_per_optin") is not None:
            items.append(("Per opt-in", _money(m["value_per_optin"]),
                          "per account/yr"))
        if m.get("value_debit_pot_hist") is not None and                 m.get("value_debit_pot_full") is not None:
            items.append(("Cards potential", _money(m["value_debit_pot_hist"]),
                          f"{_money(m['value_debit_pot_full'])} at full"))
        if m.get("value_rege_pot_elected") is not None and                 m.get("value_rege_pot_full") is not None:
            items.append(("Reg E potential",
                          _money(m["value_rege_pot_elected"]),
                          f"{_money(m['value_rege_pot_full'])} at full"))
        right = _rail(s, items, top=top)
        path = chart("value_ladder", charts.grouped_bars,
                     [str(r["group"]) for r in va],
                     [r["rev_with"] for r in va],
                     [r["rev_without"] for r in va],
                     "with card", "without card", fmt="${:,.0f}")
        if path:
            _chart_left(s, path, top, right)
        _text(s, MARGIN_L + 0.02, 6.44, CONTENT_W, 0.3,
              "Value climbs with tenure (base: eligible accounts per tenure "
              "band); the rail prices what closing "
                   "the card and opt-in gaps is worth.", size=9.5, color=GREY)
        _kicker(s)
    else:
        skip("The value ladder", "value_by_account_age")

    # ---- where the closures cluster -------------------------------------
    ab = m.get("attrition_by_branch") or []
    if ab:
        s, top = slide(headlines.attrition_branch(m), "Attrition by branch")
        items = []
        if m.get("attrition_rate") is not None:
            items.append(("Book closure", f"{n('attrition_rate')}%",
                          "12-month window"))
        aworst = m.get("attrition_branch_worst")
        abest = m.get("attrition_branch_best")
        if aworst:
            items.append(("Highest", f"{aworst[1]:.1f}%",
                          f"{aworst[0]}, {aworst[2]:,} at risk"))
        if abest:
            items.append(("Lowest", f"{abest[1]:.1f}%",
                          f"{abest[0]}, {abest[2]:,} at risk"))
        right = _rail(s, items, top=top)
        path = chart("attrition_branch", charts.branch_bars, ab,
                     m.get("attrition_rate") or 0.0)
        if path:
            _chart_left(s, path, top, right)
        _text(s, MARGIN_L + 0.02, 6.44, CONTENT_W, 0.3,
              "Bar is the closure rate; the figure inside is closures. "
                   "Small branches swing hard -- the headline rates 150+ "
                   "at-risk only.", size=9.5, color=GREY)
        _kicker(s)
    else:
        skip("Attrition by branch", "attrition_by_branch")

    # ---- the attrition pair: how much warning, how many warnings --------
    # Every chapter above reports one signal well. These two ask how far ahead
    # a closure was visible, and how many signals land on the SAME account.
    _helpers = {"slide": slide, "table": _table, "rail": _rail,
                "chart": chart, "picture": _picture, "charts": charts,
                "MARGIN_L": MARGIN_L}
    _life_skip = attrition_slides.months_of_warning(_helpers, m)
    if _life_skip:
        skip(_life_skip, "life_decline")

    _stress_skip = attrition_slides.concurrent_stressors(_helpers, m)
    if _stress_skip:
        skip(_stress_skip, "stress_by_count")

    # ---- the cohort table and the cuts that stopped in metrics.json (#245)
    _cohort_skip = attrition_slides.cohort_survival(_helpers, m)
    if _cohort_skip:
        skip(_cohort_skip, "attrition_cohort_survival")
    _cluster_skip = attrition_slides.product_and_hazard(_helpers, m)
    if _cluster_skip:
        skip(_cluster_skip, "attrition_by_product")
    _risk_skip = attrition_slides.where_the_risk_sits(_helpers, m)
    if _risk_skip:
        skip(_risk_skip, "retention_axes")

    # ---- deposit behaviour ----------------------------------------------
    # The descriptive portrait first: every deposit figure after it is a share
    # or a rate, and a reader who has not been told the size of the thing
    # cannot judge whether 3.6% is large. Section A's integrity numbers are
    # deliberately absent -- they gate these slides rather than appear on them,
    # exactly as extract_check's do.
    for _fn, _key in ((deposit_slides.deposit_overview, "dep_book_monthly"),
                      (deposit_slides.recurring_credits, "dep_cadence_mix"),
                      (deposit_slides.credits_stopped, "dep_stopped_n"),
                      (deposit_slides.deposit_milestones, "dep_quiet_bands"),
                      (deposit_slides.deposit_spread, "dep_distribution"),
                      (deposit_slides.falling_and_slowing,
                       "dep_falling_and_slowing_n"),
                      (deposit_slides.income_shape, "dep_volatility_bands"),
                      (deposit_slides.tax_refunds, "dep_refund_n"),
                      (deposit_slides.overdraft_and_income,
                       "dep_od_by_rhythm"),
                      (deposit_slides.deposit_primacy, "dep_primacy_n"),
                      (deposit_slides.inflow_against_outflow,
                       "dep_vs_card_spend")):
        _dep_skip = _fn(_helpers, m)
        if _dep_skip:
            skip(_dep_skip, _key)

    # ---- does the programme keep what it opens? -------------------------
    # Attrition had no idea ICS existed until this cut. Reported per
    # ACCOUNT-YEAR at risk, not as a raw share: a programme that opened most
    # of its accounts recently is exposed for less of the window, and a raw
    # closure rate flatters it for being young.
    al = m.get("attrition_by_lens") or []
    if len(al) >= 3:
        book = next((r for r in al if r[0] == "all"), None)
        book_rate = book[6] if book and book[6] is not None else 0.0
        named = [r for r in al if r[0] != "all" and r[6] is not None]
        ics_row = next((r for r in al if r[0] == "ics"), None)
        gap = m.get("attrition_ics_vs_book_pp")

        if ics_row and gap is not None:
            better = "below" if gap < 0 else "above"
            head = (f"ICS accounts close {abs(gap):.1f} points {better} the "
                    f"book, at {ics_row[6]:.1f}% a year")
        else:
            head = "Who leaves, by group"
        s, top = slide(
            (head, "closures per account-year at risk, so a group that opened "
                   "recently is not flattered by its short exposure; dashed "
                   "line is the book"),
            "Attrition by group")
        items = [("Book", f"{book_rate:.1f}%", "per account-year")]
        if ics_row:
            items.append(("ICS", f"{ics_row[6]:.1f}%",
                          f"{ics_row[2]:,} at risk"))
        worst = max(named, key=lambda r: r[6]) if named else None
        if worst:
            items.append(("Highest", f"{worst[6]:.1f}%",
                          f"{worst[1]}, {worst[2]:,} at risk"))
        right = _rail(s, items, top=top)
        rows = [[r[1], r[2], r[3], r[6]] for r in named]
        path = chart("attrition_lens", charts.branch_bars, rows, book_rate)
        if path:
            _chart_left(s, path, top, right)
        _text(s, MARGIN_L + 0.02, 6.44, CONTENT_W, 0.3,
              "Groups overlap -- an account can be a responder and an ICS "
              "account at once, so these do not sum to the book.",
              size=9.5, color=GREY)
        _kicker(s)
    else:
        skip("Attrition by group", "attrition_by_lens")

    # ---- branch scorecard: the chapter on one table ---------------------
    sc_rows = m.get("syn_branch_scorecard") or []
    sc_cols = m.get("syn_branch_columns") or []
    if sc_rows and sc_cols:
        s, top = slide(headlines.branch_scorecard(m), "Branch scorecard")
        heads = {"branch": "Branch", "eligible": "Eligible",
                 "take_rate": "Take rate", "rege_pct": "Reg E",
                 "value_per_acct": "Value/acct", "closure_rate": "Closures",
                 "first_year_close_pct": "1st-yr close"}

        def sc_cell(col, v):
            if v is None:
                return "-"
            if col == "branch":
                return labels.clip(v, 18)
            if col == "eligible":
                return f"{v:,}"
            if col == "value_per_acct":
                return _money(v)
            return f"{v:.1f}%"

        rows = [[heads.get(c, c.replace("_", " ")) for c in sc_cols]]
        # James (issue #41): top 15 when there are more than 20 branches,
        # otherwise every branch that fits; coverage stated in the source
        want = 15 if len(sc_rows) > 20 else len(sc_rows)
        shown = sorted(sc_rows, key=lambda r: -(r[1] or 0))[
            :_row_budget(top, want, row_h=0.30)]
        for r in shown:
            rows.append([sc_cell(c, v) for c, v in zip(sc_cols, r)])
        _table(s, rows, MARGIN_L, top + 0.1, CONTENT_W,
               col_widths=[2.5, 1.55, 1.6, 1.45, 1.7, 1.6, 1.7][:len(sc_cols)],
               size=9.5)
        if len(sc_rows) > len(shown):
            _text(s, MARGIN_L + 0.02, top + 0.1 + 0.30 * len(rows) + 0.08,
                  CONTENT_W - 0.3, 0.3,
                  f"Source: largest {len(shown)} of {len(sc_rows)} branches "
                  f"by eligible accounts; full list in metrics.json. Take "
                  f"rate and Reg E are shares of each branch's eligible "
                  f"base; closures are the 12-month window.",
                  size=9.5, color=GREY)
    else:
        skip("Branch scorecard", "syn_branch_scorecard")

    # ---- branches strong on cards, weak on Reg E ------------------------
    div = m.get("branch_divergence") or []
    if div:
        s, top = slide(headlines.divergence(m), "Where branches diverge")
        items = []
        if m.get("dctr_overall") is not None:
            items.append(("Book take rate", f"{n('dctr_overall')}%", "cards"))
        if m.get("rege_pct") is not None:
            items.append(("Book opt-in", f"{n('rege_pct')}%", "Reg E"))
        right = _rail(s, items, top=top)
        # paired gap bars off one zero line (James, issue #43): each
        # branch's card gap and Reg E gap vs the book, side by side
        path = chart("diverge", charts.gap_pairs,
                     [[name, size, d_gap, r_gap]
                      for name, size, dctr, rege, d_gap, r_gap in div])
        if path:
            _chart_left(s, path, top, right)
        _text(s, MARGIN_L + 0.02, 6.5, 9.4, 0.28,
              "Points vs the book rate, on each branch's eligible base; "
              "branches that sell the card but "
              "miss the opt-in point to a process gap, not a customer one.",
              size=9.5, color=GREY)
        _kicker(s)
    else:
        skip("Where branches diverge", "branch_divergence")


    # ============ CHAPTER 4: Reg E ======================================
    divider("Reg E review",
             "opt-in coverage, and the accounts that were never asked")

    if m.get("rege_pool"):
        # James's dashboard (issue #41): four tiles, each naming its
        # denominator; the election split; the lag pockets, boxless and
        # spaced, with a line saying what a lag means.
        s, top = slide(headlines.rege_dashboard(m), "Reg E opt-in")
        never = int(n("rege_no") + n("rege_default"))
        never_pct = round(100 * never / n("rege_pool"), 1) if n("rege_pool") else 0
        kw = (CONTENT_W - 0.9) / 4
        l12_up = n("rege_l12m_vs_hist_pp") >= 0
        tiles = [(f"{n('rege_pct')}%", "Opt-in, all base",
                  f"{n('rege_in'):,} of {n('rege_pool'):,}", NAVY),
                 (f"{n('rege_pct_of_elected')}%", "Opt-in, of electors",
                  "excludes the never-asked pool", NAVY),
                 (f"{n('rege_l12m_pct')}%", "Opt-in, last 12 months",
                  f"{n('rege_l12m_vs_hist_pp'):+.1f} pts vs historical",
                  GREEN_D if l12_up else RED_D),
                 (f"{never:,}", "No election on file",
                  f"{never_pct}% of the base", RED_D)]
        for i, (value, label, note, rule) in enumerate(tiles):
            _tile(s, MARGIN_L + i * (kw + 0.3), top + 0.05, kw, value, label,
                  note, rule=rule)
        donut = chart("rege_split", charts.rege_split, n("rege_in"),
                      n("rege_out"), n("rege_default"), n("rege_no"))
        if donut:
            _fit_picture(s, donut, MARGIN_L, top + 1.35,
                         max_w=CONTENT_W, max_h=4.85 - (top + 1.35))
        # the lag pockets: lowest opt-in by tenure, holder age, product,
        # branch -- each with its base so the size of the fix is visible
        pockets = []
        def _low(rows, min_n=200):
            rows = [r for r in rows or [] if (r[1] or 0) >= min_n]
            return min(rows, key=lambda r: r[3]) if rows else None
        r = _low(m.get("rege_account_age"))
        if r: pockets.append((f"{r[0]} tenure", r[3], r[1]))
        r = _low(m.get("rege_holder_age"))
        if r: pockets.append((f"Holders {r[0]}", r[3], r[1]))
        r = _low(m.get("rege_product"))
        if r: pockets.append((f"{labels.clip(r[0], 18)}", r[3], r[1]))
        r = _low([[b[0], b[2], b[1], b[3]]
                  for b in (m.get("rege_branch") or [])])
        if r: pockets.append((f"{labels.clip(r[0], 16)} branch", r[3], r[1]))
        if pockets:
            lag_top = 4.95
            _text(s, MARGIN_L, lag_top, CONTENT_W, 0.26,
                  "WHERE OPT-IN LAGS", size=11, bold=True, color=ORANGE,
                  font=HEAD_FONT)
            pk = (CONTENT_W - 0.9) / max(len(pockets), 1)
            for i, (label, rate_v, n_v) in enumerate(pockets[:4]):
                _kpi_flat(s, MARGIN_L + i * (pk + 0.3), lag_top + 0.32, pk,
                          label, f"{rate_v:.1f}%", f"{n_v:,} accounts")
            _text(s, MARGIN_L + 0.02, 6.44, CONTENT_W, 0.28,
                  f"A lag is a pocket running below the portfolio "
                  f"{n('rege_pct')}% opt-in.", size=9.5, color=GREY)
        _kicker(s)
    else:
        skip("Reg E opt-in", "rege_pool")

    vintage = m.get("rege_vintage") or []
    if len(vintage) >= 3:
        s, top = slide(headlines.rege_vintage(m), "Reg E opt-in by account vintage")
        first, last = vintage[0], vintage[-1]
        right = _rail(s, [
            (str(first[0]), f"{first[-1]:.0f}%", "opt-in"),
            (str(last[0]), f"{last[-1]:.0f}%", "opt-in"),
            ("24-mo trend",
             labels.signed(n('rege_trend_slope_pp_per_mo'), '.2f'), "pts/mo"),
        ], top=top)
        path = chart("vintage", charts.vintage_line, vintage[-9:],
                     m.get("rege_pct", 0))
        if path:
            _chart_left(s, path, top, right)
        _text(s, MARGIN_L + 0.02, 6.44, 9.4, 0.3,
              "Base: eligible personal cardholders OPENED in each vintage; "
              "the reference line is the whole-book opt-in.",
              size=9.5, color=GREY)
        _kicker(s)

    rege_branch = m.get("rege_branch") or []
    if rege_branch:
        s, top = slide(headlines.rege_by_branch(m), "Reg E opt-in by branch")
        best, worst = m.get("rege_branch_best"), m.get("rege_branch_worst")
        items = [("Portfolio", f"{n('rege_pct')}%", "opt-in")]
        if best: items.append(("Top branch", f"{best[1]}%", labels.clip(best[0], 16)))
        if worst: items.append(("Bottom branch", f"{worst[1]}%", labels.clip(worst[0], 16)))
        right = _rail(s, items, top=top)
        # James (issue #41): more branches
        rows = [[r[0], r[1], r[2], r[3]] for r in rege_branch[:20]]
        path = chart("rege_branch", charts.branch_bars, rows,
                     m.get("rege_pct", 0), top=20, show_n=True)
        if path:
            _chart_left(s, path, top, right)
        _text(s, MARGIN_L + 0.02, 6.44, 9.4, 0.3,
              "Base: each branch's eligible personal cardholders (count "
              "beside the name); the line is the whole-book opt-in.",
              size=9.5, color=GREY)
        _kicker(s)

    if m.get("value_debit_delta") is not None:
        s, top = slide(headlines.value(m), "What a card and an opt-in earn")
        _kpi(s, MARGIN_L + 0.1, top + 0.1, 5.9, "Value of a debit card",
             _money(m.get("value_debit_delta")),
             f"per account per year  |  {n('value_debit_n_without'):,} "
             f"eligible accounts without one")
        _kpi(s, 6.95, top + 0.1, 5.9, "Value of a Reg E opt-in",
             _money(m.get("value_rege_delta")),
             f"per account per year  |  {n('value_rege_n_without'):,} "
             f"not opted in", accent=ORANGE)
        # James (issue #41): the conversion math, spelled out as an
        # equation -- pool x conversion = new cards, priced at the value
        # per card; the opt-in follow-on underneath
        without = n("value_debit_n_without")
        conv = n("take_new_pct")
        if without and conv and m.get("value_debit_delta") is not None:
            new_cards = int(round(without * conv / 100))
            annual = int(round(new_cards * m["value_debit_delta"]))
            cm_top = top + 2.15
            _text(s, MARGIN_L + 0.1, cm_top, 4.0, 0.26, "CONVERSION MATH", size=11,
                  bold=True, color=ORANGE, font=HEAD_FONT)
            cells = [(f"{without:,}", "eligible accounts with no debit card"),
                     (f"{conv:.0f}%", "conversion rate on new accounts"),
                     (f"{_money(annual)}", f"annual value from "
                      f"{new_cards:,} new cards")]
            cw = 3.5
            xs = [0.92, 5.09, 9.26]
            for (value, label), x in zip(cells, xs):
                _text(s, x, cm_top + 0.55, cw, 0.55, value, size=30,
                      bold=True, font=HEAD_FONT)
                _text(s, x, cm_top + 1.15, cw, 0.5, label, size=11,
                      color=GREY)
            _text(s, 4.42, cm_top + 0.58, 0.5, 0.5, "\u00d7", size=26,
                  bold=True, color=ORANGE, font=HEAD_FONT)
            _text(s, 8.59, cm_top + 0.58, 0.5, 0.5, "=", size=26,
                  bold=True, color=ORANGE, font=HEAD_FONT)
            if m.get("value_rege_delta") is not None and n("rege_pct"):
                add = int(round(new_cards * n("rege_pct") / 100
                                * m["value_rege_delta"]))
                _text(s, MARGIN_L + 0.3, cm_top + 1.95, CONTENT_W - 0.3, 0.3,
                      f"An additional {_money(add)} a year if "
                      f"{n('rege_pct')}% of those {new_cards:,} new cards "
                      f"also opt in.", size=12, bold=True)
        _kicker(s)
    else:
        skip("What a card and an opt-in earn", "value_debit_delta")


    if m.get("od_eligible_n"):
        s, top = slide(headlines.od_limit(m), "Overdraft limits")
        if m.get("od_eligibility_informative"):
            items = [("OD-eligible", f"{n('od_eligible_n'):,}",
                      f"{n('od_eligible_pct')}% of eligible"),
                     ("With a limit", f"{n('od_with_limit_n'):,}",
                      f"{n('od_with_limit_pct')}% of OD-eligible")]
        else:
            items = [("With a limit", f"{n('od_with_limit_n'):,}",
                      f"{n('od_with_limit_pct_of_eligible')}% of eligible"),
                     ("Mean limit", _money(n("od_limit_mean")),
                      f"median {_money(n('od_limit_median'))}")]
        if m.get("od_rege_base"):
            items += [("Opted in", f"{n('od_optin_pct')}%",
                       f"of {n('od_rege_base'):,} cardholders"),
                      ("Not opted in", f"{n('od_eligible_not_optin_n'):,}",
                       "OD-eligible cardholders")]
        right = _rail(s, items, top=top)
        tiers = m.get("od_limit_values") or []
        if tiers:
            rows_c = [[_money(a), c] for a, c, p in tiers]
            if m.get("od_limit_other_n"):
                rows_c.append(["Other", m["od_limit_other_n"]])
            path = chart("od_limit_tiers", charts.tier_bars, rows_c)
            if path:
                _chart_left(s, path, top, right, max_h=4.4)
        if m.get("od_fee_revenue_l12m") is not None and m.get("od_rege_base"):
            _text(s, MARGIN_L + 0.02, 6.44, CONTENT_W, 0.3,
                  f"Opted-in accounts drive {n('od_fee_optin_share_pct'):.0f}% of the "
                       f"{_money(m['od_fee_revenue_l12m'])} in 12-month NSF/OD fee revenue "
                       f"({n('od_items_per_acct_optin'):.1f} vs "
                       f"{n('od_items_per_acct_not_optin'):.1f} items per account).", size=9.5, color=GREY)
            _kicker(s)

    if m.get("mig_base"):
        s, top = slide(headlines.migration(m), "Swipe-tier migration")
        right = _rail(s, [
            ("Moved up", f"{n('mig_up_pct')}%", f"{n('mig_up_n'):,} accounts"),
            ("Same tier", f"{n('mig_same_pct')}%", ""),
            ("Moved down", f"{n('mig_down_pct')}%", f"{n('mig_down_n'):,} accounts"),
            ("Started swiping", f"{n('mig_entered_use_n'):,}",
             f"{n('mig_entered_use_pct')}% of non-users then"),
        ], top=top)
        y = top + 0.1
        groups = {r[0]: r for r in (m.get("mig_by_group") or [])}
        if "Responder" in groups and "Mailed non-responder" in groups:
            _text(s, MARGIN_L + 0.02, 6.44, CONTENT_W, 0.3,
                  f"Responders moved up at {groups['Responder'][2]:.0f}% against "
                       f"{groups['Mailed non-responder'][2]:.0f}% for mailed non-responders "
                       f"\u2014 the program moves usage, not just cards.", size=9.5, color=GREY)
            _kicker(s)
        dist_first, dist_latest = m.get("mig_dist_first") or [], m.get("mig_dist_latest") or []
        if dist_first and dist_latest:
            path = chart("migration", charts.grouped_bars,
                         [r[0] for r in dist_first],
                         [r[2] for r in dist_first], [r[2] for r in dist_latest],
                         m.get("mig_first", "then"), m.get("mig_latest", "now"),
                         fmt="{:.0f}%")
            if path:
                _chart_left(s, path, y, right, max_h=7.0 - y - 0.3)

    else:
        skip("Swipe-tier migration", "mig_base")
    _matrix_skip = migration_slides.tier_matrix(
        {"slide": slide, "table": _table, "rail": _rail, "MARGIN_L": MARGIN_L}, m)
    if _matrix_skip:
        skip(_matrix_skip, "mig_matrix")

    # ============ transaction intelligence (when a txn run exists) ========
    if txn_t is not None:
        try:
            helpers = {"new": new, "slide": slide, "chart": chart,
                       "divider": lambda _p, _n, ti, su=None: divider(ti, su),
                       "rail": _rail, "table": _table, "kpi": _kpi, "text": _text,
                       "chart_left": _chart_left, "money": _money, "kicker": _kicker,
                       "MARGIN_L": MARGIN_L, "RIGHT_EDGE": RIGHT_EDGE,
                       "row_budget": _row_budget, "fit_picture": _fit_picture,
                       "NAVY": NAVY, "ORANGE": ORANGE, "GREY": GREY,
                       "CONTENT_W": CONTENT_W}
            skipped.extend(txn_slides.add_chapter(prs, helpers, txn_t, charts_dir))
            _txn_helpers = helpers
        except Exception as exc:
            skipped.append(f"transaction chapter ({type(exc).__name__}: {exc})")

    # ============ scorecard (synthesis) ================================
    # chapter stamp: synthesis slides are SUMMARY (v5 mockup kicker),
    # never whatever chapter happened to close above them
    _chapter_now[0] = "Summary"
    card = m.get("syn_scorecard") or []
    if card:
        counts, card_shown = _scorecard_tally(card)
        s = new()
        register(s, "slide", "Scorecard", tracked="Scorecard")
        _title(s, f"Scorecard: {counts['green']} green, "
                  f"{counts['amber']} amber, {counts['red']} red",
               "each metric against its own comparator, never an absolute threshold")
        rows = [["", "Metric", "Value", "Against", "Delta"]]
        rag_by_row = {}
        _RAG_FILL = {"green": RGBColor(0x2A, 0x9D, 0x8F),
                     "amber": RGBColor(0xE9, 0xA1, 0x3B),
                     "red": RGBColor(0xC0, 0x39, 0x2B)}
        for metric, value, unit, comparator, delta, rag in card_shown:
            rag_by_row[len(rows)] = _RAG_FILL.get(rag)     # grey -> None
            rows.append(["", metric,
                         f"{value}{unit if unit in ('%', 'pts') else ' ' + unit}",
                         labels.clip(comparator, 44), "" if delta is None else f"{delta:+.1f}"])
        _table(s, rows, MARGIN_L, 1.8, 11.9,
               col_widths=[0.5, 3.9, 1.6, 4.6, 1.3], size=10.5,
               cell_fill=lambda r, c: rag_by_row.get(r) if c == 0 else None)
        note = labels.coverage_note(len(card_shown), len(card), "metrics")
        body_y = 1.8 + 0.32 * len(rows) + 0.3
        if note:
            _text(s, MARGIN_L + 0.16, body_y, CONTENT_W - 0.3, 0.4,
                  note, size=11, color=GREY)
            body_y += 0.34
        points = m.get("syn_talking_points") or []
        if points:
            _text(s, MARGIN_L + 0.16, body_y, CONTENT_W - 0.3, 1.6,
                  "\n".join(f"- {p}" for p in points[:3]), size=12.5, color=NAVY)

    # ---- program P&L by wave: the ARS Workbook, finally on a slide ------
    if m.get("wb_profit_ltd") is not None or m.get("wb_waves"):
        s, top = slide(headlines.pnl(m), "Program P&L by offer")
        kw = (CONTENT_W - 0.6) / 4
        if (m.get("gt_deferred_balance") or 0) > 1 \
                and m.get("gt_state") != "clear":
            # guarantee math (issue #42): what the client actually pays,
            # only while a balance is LIVE -- a cleared guarantee reverts
            # to the workbook's billed economics
            tiles = [("Earned over fees paid",
                      _money((m.get("gt_revenue_ltd") or 0)
                             - (m.get("gt_paid_ltd") or 0)),
                      "guarantee math, to date"),
                     ("Program revenue", _money(m.get("gt_revenue_ltd")),
                      "deferral tracker, to date"),
                     ("Fees paid", _money(m.get("gt_paid_ltd")),
                      f"of {_money(m.get('gt_charges_ltd'))} billed"),
                     ("Deferred", _money(m.get("gt_deferred_balance")),
                      "forgiven at contract end")]
        else:
            tiles = [("Program profit", _money(m.get("wb_profit_ltd")),
                      "life to date"),
                     ("Program revenue", _money(m.get("wb_revenue_ltd")),
                      "life to date"),
                     ("Program fees", _money(abs(m.get("wb_costs_ltd") or 0)),
                      "life to date"),
                     ("This month", _money(m.get("wb_profit_month")),
                      f"of {_money(m.get('wb_revenue_month'))} revenue")]
        for i, (label, value, note) in enumerate(tiles):
            _kpi(s, MARGIN_L + i * (kw + 0.2), top + 0.05, kw, label, value,
                 note, accent=ORANGE if i == 0 else NAVY)
        waves = m.get("wb_waves") or []
        if waves:
            t_top = top + 1.95
            rows = [["Offer", "Mailed", "Response", "Rev to date"]]
            shown = waves[-_row_budget(t_top, 10):]
            # rows carry 5 fields since goal_met_responders was added;
            # *_ tolerates both that and any older 4-field metrics.json
            for tag, mailed, resp, cum, *_ in shown:
                rows.append([str(tag),
                             f"{mailed:,}" if mailed is not None else "-",
                             f"{resp}%" if resp is not None else "-",
                             _money(cum)])
            _table(s, rows, MARGIN_L, t_top, 8.6,
                   col_widths=[2.0, 2.2, 2.1, 2.3], size=10.5)
            if len(waves) > len(shown):
                _text(s, MARGIN_L + 0.02, t_top + 0.32 * len(rows) + 0.06,
                      8.4, 0.28, f"latest {len(shown)} of {len(waves)} offers",
                      size=10, color=GREY)
        _text(s, MARGIN_L + 0.02, 6.42, CONTENT_W, 0.3,
              f"Booked frame: {m.get('wb_source', 'ARS Workbook')}, the "
              f"program's own ledger, gross and all revenue types. Rev "
              f"to date is the wave's own To Date column, life of the "
              f"offer. Not comparable to DiD estimates: see Revenue "
              f"frames.", size=9.5, color=GREY)
        _kicker(s)
    else:
        skip("Program P&L by offer", "wb_waves (run with an ARS Workbook present)")

    # ---- the rollup matrix on a slide (issue #85) ----------------------
    # Two views of one table: what the month is made of, and how long an
    # offer keeps paying. Booked frame throughout -- these never blend
    # with the DiD estimate; the bridge slide is Revenue frames.
    wave_rows = m.get("wb_wave_revenue") or []
    wb_src = m.get("wb_source", "ARS Workbook")
    if len(wave_rows) >= 2:
        s, top = slide(headlines.wave_mix(m),
                       "Where the month's revenue came from")
        path = chart("wave_composition", charts.wave_composition, wave_rows)
        if path:
            _fit_picture(s, path, MARGIN_L, top + 0.1,
                         max_w=CONTENT_W, max_h=6.3 - (top + 0.1))
        _text(s, MARGIN_L + 0.02, 6.42, CONTENT_W, 0.3,
              f"Booked frame: {wb_src}, All Months Rollup. Each column is "
              f"that month's revenue split by every offer that earned in "
              f"it, oldest pale at the base to newest dark on top. Not "
              f"comparable to DiD estimates: see Revenue frames.",
              size=9.5, color=GREY)
        _kicker(s)

        s, top = slide(headlines.wave_totals(m),
                       "What each offer has earned")
        path = chart("wave_totals", charts.wave_totals, wave_rows)
        if path:
            _fit_picture(s, path, MARGIN_L, top + 0.1,
                         max_w=CONTENT_W, max_h=6.3 - (top + 0.1))
        _text(s, MARGIN_L + 0.02, 6.42, CONTENT_W, 0.3,
              f"Booked frame: {wb_src}, All Months Rollup — each column "
              f"is one offer, banded by the month that earned it, and the "
              f"total ties to Rev to date on Program P&L by offer. Offers "
              f"are not the same age: the months each has had ride under "
              f"its label. Not comparable to DiD estimates: see Revenue "
              f"frames.", size=9.5, color=GREY)
        _kicker(s)
    else:
        skip("Where the month's revenue came from",
             "wb_wave_revenue (run with an ARS Workbook present)")
        skip("What each offer has earned",
             "wb_wave_revenue (run with an ARS Workbook present)")

    # ---- the two revenue frames, bridged (issue #40) --------------------
    rf_pair = headlines.revenue_frames(m)
    if rf_pair:
        s, top = slide(rf_pair, "Revenue frames")
        ic_rate = m.get("segment_ic_rate")
        panel_w = (CONTENT_W - 0.9) / 2
        rx = MARGIN_L + panel_w + 0.9
        _text(s, MARGIN_L, top + 0.05, panel_w, 0.28,
              "BOOKED: ARS WORKBOOK LEDGER", size=11, bold=True, color=ORANGE,
              font=HEAD_FONT)
        _kpi_flat(s, MARGIN_L, top + 0.42, panel_w, "Program revenue",
                  _money(m.get("wb_revenue_ltd")), "life to date, gross")
        _kpi_flat(s, MARGIN_L, top + 1.62, panel_w, "Program profit",
                  _money(m.get("wb_profit_ltd")),
                  f"after {_money(abs(m.get('wb_costs_ltd') or 0))} fees")
        _text(s, MARGIN_L, top + 2.85, panel_w, 0.6,
              "All revenue types on goal-met responders, including NSF/OD "
              "fee income; includes spend the control would have produced.",
              size=10, color=GREY)
        _text(s, rx, top + 0.05, panel_w, 0.28,
              "INCREMENTAL: DiD ESTIMATE", size=11, bold=True, color=ORANGE,
              font=HEAD_FONT)
        _kpi_flat(s, rx, top + 0.42, panel_w, "Lift per responder",
                  f"{_money(m['ba_lift_net'])}/mo", "spend, net of control")
        if ic_rate:
            _kpi_flat(s, rx, top + 1.62, panel_w, "As interchange",
                      f"{_money(m['ba_lift_net'] * ic_rate)}/mo",
                      f"at IC rate {ic_rate}")
        _text(s, rx, top + 2.85, panel_w, 0.6,
              "Interchange only, a monthly run rate around each offer; "
              "credits nothing the control also did.",
              size=10, color=GREY)
        wedge_top = min(top + 3.55, 5.15)
        _text(s, MARGIN_L, wedge_top, CONTENT_W, 0.28,
              "Why they never tie", size=12, bold=True, font=HEAD_FONT)
        for i, line in enumerate([
                "Fee income sits only in the booked frame; DiD converts "
                "spend lift to interchange alone.",
                "Booked is gross; DiD subtracts the control, and part of "
                "each lift is decline arrested.",
                "Booked accumulates over the window; DiD is a run rate, "
                "and lift decays.",
                "Per-1,000-mailed pools every mailed account across "
                "offers; the ledger counts goal-met responders per offer."]):
            _text(s, MARGIN_L + 0.15, wedge_top + 0.32 + i * 0.30,
                  CONTENT_W - 0.3, 0.26, f"\u00b7  {line}", size=10.5,
                  color=GREY)
        _kicker(s)
    else:
        skip("Revenue frames", "wb_revenue_ltd + ba_lift_net")


    # ---- the workbook rate card (Lift Matrix MM) ------------------------
    # Booked frame: the workbook's own segment x band card, quoted for the
    # window it is good for. The unit comes from the sheet's caption, never
    # from us -- a workbook that changes its basis must not silently
    # relabel this slide.
    lift_pair = headlines.lift_matrix(m)
    if lift_pair:
        s, top = slide(lift_pair, "What an account earns as it climbs")
        wb_src = m.get("wb_source", "ARS Workbook")
        path = chart("lift_matrix", charts.lift_matrix_heat,
                     {"cols": m["wb_lift_cols"], "rows": m["wb_lift_rows"],
                      "money": "$" in str(m.get("wb_lift_caption") or "$")})
        if path:
            _fit_picture(s, path, MARGIN_L, top + 0.1,
                         max_w=CONTENT_W, max_h=6.3 - (top + 0.1))
        caption = m.get("wb_lift_caption")
        unit = (f'the sheet states the figure as "{caption}"' if caption
                else "the sheet states no unit, so the figures are shown "
                     "as the workbook carries them")
        window = (f", {m['wb_lift_window']}" if m.get("wb_lift_window")
                  else "")
        stale = (f" The sheet's data month is "
                 f"{m.get('wb_lift_data_month')}, past the window's end: "
                 f"these rates are stale, not current."
                 if m.get("wb_lift_stale") else "")
        _text(s, MARGIN_L + 0.02, 6.42, CONTENT_W, 0.3,
              f"Booked frame: {wb_src}, Lift Matrix MM{window}. Each row is "
              f"the band an account started in, each column the band it "
              f"reached; {unit}.{stale}", size=9.5, color=GREY)
        _kicker(s)
    elif m.get("wb_found"):
        skip("What an account earns as it climbs",
             reason=(f"the booked frame is empty: workbook "
                     f"{m['wb_found']} gave up no Lift Matrix MM"))
    else:
        skip("What an account earns as it climbs", "wb_lift_rows")

    # ---- the revenue cascade: the economics on one line of sight --------
    casc = m.get("syn_cascade") or []
    if casc:
        s, top = slide(headlines.cascade(m), "The revenue cascade")
        rows = [["Step", "Value", "Unit", "How it is derived"]]
        for step_label, value, unit, note in casc[:8]:
            shown = _money(value) if "$" in str(unit) else f"{value:,}"
            rows.append([str(step_label), shown, str(unit),
                         str(note or "")])
        _table(s, rows, MARGIN_L, top + 0.15, CONTENT_W,
               col_widths=[w * CONTENT_W / 11.9 for w in (4.6, 1.5, 1.6, 4.2)],
               size=10.5)
        _text(s, MARGIN_L + 0.02, 6.44, CONTENT_W, 0.3,
              "Each step is the section's own number -- nothing on "
                   "this slide is recomputed.", size=9.5, color=GREY)
        _kicker(s)
    else:
        skip("The revenue cascade", "syn_cascade")

    # ============ CHAPTER: takeaways ==================================
    # James, 2026-08-22: no computed headline here -- the dollar-total
    # claim ("Three measured opportunities total $X") is dropped, and the
    # old "next quarter's three moves" framing stays retired. The slide
    # carries the plain title; the items speak for themselves.
    nxt = ("Key takeaways",
           "the book's top measured opportunities, sized from its own "
           "rates; each carries its base and its list")
    s = new()
    register(s, "slide", nxt[0] if nxt else "Key takeaways",
             tracked="Key takeaways",
             computed=bool(nxt))
    _title(s, nxt[0] if nxt else "Key takeaways",
           nxt[1] if nxt else None)
    items = []
    # Synthesis ranks every priced gap; take the top three revenue items.
    for o in [o for o in (m.get("syn_opportunities") or []) if o.get("kind") == "revenue"][:3]:
        label = o["label"]
        short = ("Cards" if label.startswith("Cards") else
                 "Debit leaks" if "debit leaks" in label else
                 "Business gap" if "Business" in label else
                 "Reg E opt-ins" if "Reg E opt-ins" in label else
                 "Reg E elections" if "elections" in label else
                 "Reg E leaks" if "Reg E leaks" in label else
                 "Reactivation" if "reactivat" in label else labels.clip(label, 18))
        items.append((short, o["value"], f"{o['n']:,} accounts"))
    if not items:
        if m.get("value_debit_pot_l12m"):
            items.append(("Cards", m["value_debit_pot_l12m"],
                          f"{n('value_debit_n_without'):,} eligible without one"))
        if m.get("rege_default_value"):
            opp = m.get("rege_default_opportunity", {})
            items.append(("Reg E elections", m["rege_default_value"],
                          f"{opp.get('n', 0):,} never asked"))
        if m.get("dctr_leak_value"):
            items.append(("Branch gaps", m["dctr_leak_value"],
                          f"{n('dctr_leak_total'):,} cards in the three widest"))
    for idx, (label, value, note) in enumerate(items[:3]):
        _kpi(s, MARGIN_L + idx * ((CONTENT_W - 0.4) / 3 + 0.2), 2.2,
             (CONTENT_W - 0.4) / 3, label, _money(value), note,
             accent=NAVY if idx == 0 else ORANGE)
    top_opp = next(iter(m.get("syn_opportunities") or []), None)
    if top_opp:
        _text(s, MARGIN_L + 0.02, 6.44, CONTENT_W, 0.3,
              f"First move: {top_opp['label']}: "
                   f"{_money(top_opp['value'])} a year across "
                   f"{top_opp['n']:,} accounts.", size=9.5, color=GREY)
        _kicker(s)
    _text(s, MARGIN_L, 6.15, CONTENT_W, 0.5,
          "Figures derive from the overdraft data dump; rates divide by a "
          "stated base; mailing results are measured against mailed "
          "non-responders.",
          size=10, color=GREY)

    # ---- the deliverable: call-ready lists for the client's team ----------
    lists_dir = out.parent / "lists"
    csvs = sorted(lists_dir.glob("*.csv")) if lists_dir.is_dir() else []
    if csvs:
        counts = []
        for c in csvs:
            try:
                with open(c, encoding="utf-8", errors="replace") as fh:
                    rows = max(sum(1 for _ in fh) - 1, 0)
            except OSError:
                rows = None
            counts.append((c.stem.replace("_", " "), rows))
        total_rows = sum(r for _, r in counts if r)
        s = new()
        _title(s, f"{total_rows:,} accounts across {len(counts)} call-ready lists, "
                  f"for your team",
               "CSV action lists with account attributes, next to this deck; "
               "the institution decides who to contact and how \u2014 this kit never "
               "sends outreach")
        y = 2.0
        shown = counts[:10]
        for name, rows_ in shown:
            _text(s, 1.0, y, 8.0, 0.45, f"\u2014  {name}", size=14, color=NAVY)
            _text(s, 9.2, y, 2.6, 0.45,
                  f"{rows_:,} accounts" if rows_ is not None else "-",
                  size=14, color=NAVY)
            y += 0.46
        # the title counts every list; say so when the slide shows fewer (#71)
        note = labels.coverage_note(len(shown), len(counts), "lists")
        if note:
            _text(s, 1.0, y + 0.12, 8.0, 0.4,
                  f"{note}; every list ships as a CSV beside this deck",
                  size=11, color=GREY)

    s = _divider(prs, new, "Questions and discussion",
                 "every number on these slides is reproducible from the "
                 "data dump")
    no_footer.append(s)

    # ============ APPENDIX ==============================================
    divider("Appendix", "supporting detail")

    # ---- offer detail: the combo lines, one slide per offer -------------
    # (client-requested depth: per-segment swipes + spend around each
    # mailing; segments are the ODD's own '{tag} Segmentation')
    ms = m.get("mailer_summary") or {}
    rd_all = m.get("mailer_resp_detail") or {}
    # "most recent with data" = the newest wave that can carry the whole
    # pair; fall back to the newest wave with a summary alone
    paired = [t for t in ms if t in rd_all]
    latest_pair = (paired or list(ms))[-1] if ms else None

    if latest_pair:
        d = ms[latest_pair]
        s = new()
        register(s, "slide", "The most recent mailer",
                 tracked="The most recent mailer")
        _title(s, f"{latest_pair} reached {d['mailed']:,} accounts and "
                  f"{d['responded']:,} responded \u2014 {d['rate']:.1f}%",
               "response share and rate by challenge tier, and who the "
               "responders were")
        path = chart(f"mailsum_{latest_pair}", charts.mailer_summary_panel, d)
        if path:
            _fit_picture(s, path, MARGIN_L, 1.55, max_w=CONTENT_W, max_h=4.85)
        _kicker(s)
    else:
        skip("The most recent mailer", "mailer_summary")

    if latest_pair and latest_pair in rd_all:
        rd = rd_all[latest_pair]
        s = new()
        register(s, "slide", "The most recent mailer trajectory",
                 tracked="The most recent mailer trajectory")
        nseg = len(rd["segments"])
        _title(s, f"{latest_pair}: responders versus their own segment",
               f"{nseg} challenge segment{'s' if nseg != 1 else ''}; spend "
               f"(top) and swipes (bottom) per account, every month after "
               f"the mail the file carries")
        path = chart(f"mailtraj_{latest_pair}", charts.segment_resp_grid, rd)
        if path:
            _fit_picture(s, path, MARGIN_L, 1.55, max_w=CONTENT_W, max_h=4.85)
        _kicker(s)
    else:
        skip("The most recent mailer trajectory", "mailer_resp_detail")

    md = m.get("mailer_detail") or {}
    # ---- the most recent offer (James, 2026-08-22: "add the most
    # recent mail") -- the latest completed wave's legacy combo, its own
    # stable slide id so the manifest can carry it in the main path
    if md:
        last_tag = list(md)[-1]
        d_last = md[last_tag]
        s = new()
        n_mailed_l = sum(d_last["counts"].values())
        register(s, "slide", "The most recent offer",
                 tracked="The most recent offer")
        _title(s, f"The most recent offer: {last_tag} reached "
                  f"{n_mailed_l:,} accounts",
               "swipes (top) and spend (bottom) per mailed account by "
               "segment; the mail month is the orange line")
        path = chart("combo_latest", charts.combo_lines, d_last)
        if path:
            _fit_picture(s, path, MARGIN_L, 1.55, max_w=CONTENT_W,
                         max_h=4.85)
        _kicker(s)
    else:
        skip("The most recent offer", "mailer_detail")
    appendix_tags = [t for t in ms if t != latest_pair]
    if appendix_tags or md:
        divider("Offer detail")
        # Newest first. The reader opens Offer detail looking for the most
        # recent mailing, and should not scroll a year back to reach it.
        # Render order only -- mailer_summary still WALKS waves oldest-first,
        # because its ladder history (first-time vs repeat, moved-up) is
        # measured against what came before.
        #
        # One block per offer (#53 P3): its summary, its behaviour by
        # segment, its responders against their segment. Three forms in
        # rotation, everything about one mailing on adjacent slides, and the
        # responders picture drawn once -- it was drawn twice per mailer
        # under two titles, byte for byte the same (#231).
        summary_tags = appendix_tags[-12:]
        detail_tags = list(md)[-12:]
        ordered = list(dict.fromkeys(list(ms) + list(md)))
        for tag in reversed(ordered):
            if tag in summary_tags:
                d = ms[tag]
                s = new()
                register(s, "slide", f"Mailer {tag} summary")
                _title(s, f"{tag} mailer summary",
                       f"{d['mailed']:,} mailed, {d['responded']:,} responded "
                       f"\u2014 {d['rate']:.1f}%")
                path = chart(f"mailsum_{tag}", charts.mailer_summary_panel, d)
                if path:
                    _fit_picture(s, path, MARGIN_L, 1.55,
                                 max_w=CONTENT_W, max_h=5.5)
            if tag not in detail_tags:
                continue
            d = md[tag]
            s = new()
            register(s, "slide", f"Offer {tag} by segment")
            n_mailed = sum(d["counts"].values())
            _title(s, f"{tag}: swipes and spend by segment",
                   f"{n_mailed:,} mailed accounts with a segment call; "
                   f"lines are per-account monthly averages")
            path = chart(f"combo_{tag}", charts.combo_lines, d)
            if path:
                _fit_picture(s, path, MARGIN_L, 1.55,
                             max_w=CONTENT_W, max_h=5.5)
            rd = rd_all.get(tag)
            if rd:
                s = new()
                register(s, "slide",
                         f"{tag}: responders versus their segment")
                nseg = len(rd["segments"])
                _title(s, f"{tag}: responders versus their own segment",
                       f"{nseg} challenge segment{'s' if nseg != 1 else ''}, "
                       f"each responder group against its segment's "
                       f"non-responders; spend (top) and swipes (bottom) "
                       f"per account")
                path = chart(f"resp_{tag}", charts.segment_resp_grid, rd)
                if path:
                    _fit_picture(s, path, MARGIN_L, 1.55,
                                 max_w=CONTENT_W, max_h=5.5)

    # The "Transaction detail" appendix was ten table slides. Every one of
    # them is now a chart in the chapter itself, so there is nothing left to
    # demote -- see txn_slides.add_chapter and the approved catalog at
    # lab/DESIGN/report-mockups/slides-txn-suite.html.

    # ============ ICS chapter (when the source lists stamped the book) ====
    if m.get("ics_cmp_bases"):
        try:
            from . import ics_slides
            skipped.extend(ics_slides.add_chapter(prs, {
                "new": new, "slide": slide, "chart": chart,
                "divider": lambda _p, _n, ti, su=None: divider(ti, su),
                "rail": _rail, "table": _table, "kpi": _kpi, "text": _text,
                "chart_left": _chart_left, "money": _money,
                "kicker": _kicker, "fit_picture": _fit_picture,
                "MARGIN_L": MARGIN_L, "RIGHT_EDGE": RIGHT_EDGE,
                "CONTENT_W": CONTENT_W}, m, charts_dir, txn=txn_t))
        except Exception as exc:
            skipped.append(f"ICS chapter ({type(exc).__name__}: {exc})")

    if m.get("new_total"):
        divider("New account profile",
                 f"opened {' to '.join(m.get('new_window', []))}")

        products = m.get("new_products") or []
        if products:
            s, top = slide(None, "New accounts by product")
            right = _rail(s, [
                ("Opened", f"{n('new_total'):,}", "last 12 months"),
                ("Still open", f"{n('new_stillopen_pct')}%", "of those"),
                ("Checking", f"{n('new_checking_pct')}%", "of new accounts"),
            ], top=top)
            path = chart("newprod", charts.tier_bars,
                         [[labels.clip(p[0], 18), p[1]] for p in products[:8]])
            if path:
                _chart_left(s, path, top, right)

        if m.get("new_chk_avgbal") is not None:
            s, top = slide(None, "New checking balances versus the book")
            right = _rail(s, [
                ("New", _money(m.get("new_chk_avgbal")), "average balance"),
                ("Book", _money(m.get("open_chk_avgbal")), "average balance"),
                ("Funded", f"{n('new_chk_funded_pct')}%", "above zero"),
            ], top=top)
            # one comparison, two numbers: a connector shows the gap; two
            # bars made the reader measure it (#53 P2)
            new_bal, book_bal = m.get("new_chk_avgbal", 0), m.get("open_chk_avgbal", 0)
            path = chart("newbal", charts.dumbbell,
                         [["Average checking balance", new_bal, book_bal,
                           "opened last 12 months vs all eligible checking"]],
                         "new", "existing book", value_fmt="${:,.0f}",
                         delta_fmt="{:+,.0f}",
                         delta_color=charts.GREEN if new_bal >= book_bal
                         else charts.ORANGE,
                         height=charts.FIG_H_RAIL * 0.5)
            if path:
                _chart_left(s, path, top, right)

        if m.get("new_chk_debit_pct") is not None:
            s, top = slide(headlines.new_debit_gap(m), "Debit penetration — new versus book")
            right = _rail(s, [
                ("New checking", f"{n('new_chk_debit_pct')}%", "hold a card"),
                ("Existing book", f"{n('open_chk_debit_pct')}%", "hold a card"),
                ("Gap", f"{n('debit_pen_gap'):+.1f} pts", "new vs book"),
            ], top=top)
            # a share of a hundred, twice: the waffle shows how many in a
            # hundred hold a card, which two bars of a percentage do not (#53 P2)
            path = chart("newpen", charts.waffle,
                         [("New checking", m.get("new_chk_debit_pct", 0),
                           "opened last 12 months"),
                          ("Existing book", m.get("open_chk_debit_pct", 0),
                           "all eligible checking")])
            if path:
                _chart_left(s, path, top, right)

        if m.get("new_active_pct") is not None:
            s, top = slide(None, "Card usage — new versus existing book")
            right = _rail(s, [
                ("New active", f"{n('new_active_pct')}%",
                 str(m.get("activity_month", ""))),
                ("Book active", f"{n('book_active_pct')}%",
                 str(m.get("activity_month", ""))),
                ("Ever swiped", f"{n('new_ever_swiped_pct')}%", "of new cards"),
            ], top=top)
            path = chart("newuse", charts.grouped_bars,
                         ["Active this month", "Spend per active"],
                         [m.get("new_active_pct", 0), m.get("new_spend_active", 0)],
                         [m.get("book_active_pct", 0), m.get("book_spend_active", 0)],
                         "new", "book")
            if path:
                _chart_left(s, path, top, right)

        if m.get("new_swipe_seg"):
            s, top = slide(None, "New-account debit adoption by swipe tier")
            right = _rail(s, [
                ("New cards", f"{n('new_card_n'):,}", "issued"),
                ("Monthly user", f"{n('new_swipe_monthly_pct')}%",
                 "1+ swipe/month"),
                ("Heavy", f"{n('new_swipe_heavy_pct')}%", "26+ per month"),
            ], top=top)
            path = chart("newseg", charts.tier_bars,
                         [[r[0], r[1]] for r in m["new_swipe_seg"]])
            if path:
                _chart_left(s, path, top, right)

    if m.get("openings"):
        s, top = slide(headlines.growth(m), "Account growth — openings versus closures")
        right = _rail(s, [
            ("Opened", f"{n('open_24'):,}", "24 months"),
            ("Closed", f"{n('close_24'):,}", "24 months"),
            ("Net", f"{n('net_24'):+,}", "24 months"),
        ], top=top)
        path = chart("growth", charts.openings_chart, m["openings"])
        if path:
            _chart_left(s, path, top, right)

    if m.get("survival"):
        s, top = slide(None, "Account retention — survival by tenure")
        items = [("1 year", f"{n('ret_1yr')}%", "still open")]
        if m.get("ret_3yr"):
            items.append(("3 years", f"{n('ret_3yr')}%", "still open"))
        if m.get("median_closed_life"):
            items.append(("Median life", f"{n('median_closed_life')} yr",
                          "of closed accounts"))
        right = _rail(s, items, top=top)
        path = chart("survival", charts.line_series, m["survival"],
                     ylabel="still open", pct=True)
        if path:
            _chart_left(s, path, top, right)

    if m.get("firstyear_close_gap_pp") is not None:
        s, top = slide(headlines.firstyear_close(m), "First-year closure by early card use")
        right = _rail(s, [
            ("Used the card", f"{n('firstyear_close_used_pct')}%", "closed"),
            ("Did not", f"{n('firstyear_close_not_used_pct')}%", "closed"),
            ("Gap", f"{n('firstyear_close_gap_pp'):+.1f} pts", "difference"),
        ], top=top)
        path = chart("firstyear", charts.grouped_bars, ["First-year closure"],
                     [m.get("firstyear_close_used_pct", 0)],
                     [m.get("firstyear_close_not_used_pct", 0)],
                     "used card early", "did not", fmt="{:,.1f}%")
        if path:
            _chart_left(s, path, top, right)

    health_rows = m.get("retention_health") or []
    if health_rows:
        s, top = slide(headlines.health(m), "Account health")
        path = chart("health", charts.health_bars, health_rows)
        if path:
            _picture(s, path, top=top + 0.05, max_h=7.0 - top)

    out.parent.mkdir(parents=True, exist_ok=True)

    # ---- the editorial cut: off-manifest slides move to the Appendix ------
    try:
        # old slide ids in an existing manifest resolve to their merged
        # successors (issue #43) instead of warning as typos
        _SLIDE_RENAMES = {
            "Program reach \u2014 cumulative responders": "Response and reach by offer",
            "Response rate by mailing": "Response and reach by offer",
            "Per-mailer summary": "Per-offer summary",
            "Before and after each mailing": "Per-offer summary",
        }
        main_path = [_SLIDE_RENAMES.get(t, t) for t in
                     (manifest.get("main_path") or MAIN_PATH)]
        main_path = list(dict.fromkeys(main_path))      # dedupe, keep order
        exclude = {_SLIDE_RENAMES.get(t, t)
                   for t in (manifest.get("exclude") or [])}
        built_ids = {e["tracked"] for e in placed
                     if e["kind"] == "slide" and e.get("tracked")}
        if manifest.get("promote_appendix"):
            # The "deep" cut: every tracked slide onto the main path, so
            # nothing is demoted. Manifest order first, then the rest in the
            # order they were built, so the reading order stays the one the
            # sections chose. exclude still applies below.
            seen = set(main_path)
            main_path = main_path + [
                e["tracked"] for e in placed
                if e["kind"] == "slide" and e.get("tracked")
                and e["tracked"] not in seen and not seen.add(e["tracked"])]
        unknown = [t for t in list(main_path) + sorted(exclude)
                   if t not in set(MAIN_PATH) | built_ids]
        if unknown:
            try:
                result.warn(f"deck_manifest slide ids not built this run "
                            f"(typo, or the section declined): {unknown}")
            except Exception:
                pass          # a warn channel failure never voids the cut
        if exclude:
            _remove_excluded(prs, placed, exclude)
        _reorder_to_appendix(prs, placed,
                             [t for t in main_path if t not in exclude],
                             chapter_divs)
        if manifest.get("dividers", True) is False:
            _one_flow_cut(prs, placed, chapter_divs,
                          [t for t in main_path if t not in exclude])
    except Exception as exc:
        skipped.append(f"editorial cut skipped ({type(exc).__name__}: {exc})")

    # ---- footers: number + context on every slide after the cover ---------
    no_footer_objs = {id(sl) for sl in no_footer}
    div_positions = []
    final = list(prs.slides)
    fpos = {id(sl): i for i, sl in enumerate(final)}
    for sl, ti in chapter_divs:
        if id(sl) in fpos:
            div_positions.append((fpos[id(sl)], ti))
    div_positions.sort()
    # chapter per content slide: the registration-time stamp (survives the
    # one-flow cut deleting divider slides -- #66); the spine kicker's and
    # footer tag's one source of truth
    chap_by_slide = {id(e["sl"]): e.get("chapter")
                     for e in placed if e["kind"] == "slide"}
    for idx, sl in enumerate(final, start=1):
        if idx == 1 or id(sl) in no_footer_objs:
            # a grey footer on full-bleed navy is an invisible smudge --
            # dividers and the closer carry no footer (numbering counts them)
            continue
        try:
            _spine(sl, idx, chap_by_slide.get(id(sl)))
        except Exception:
            pass
        try:
            _text(sl, FOOTER_L, FOOTER_Y, 8.6, 0.26,
                  f"{client}  \u00b7  Source: overdraft data dump, {data_month} "
                  f"\u00b7  CSI ARS pipeline", size=9, color=GREY)
            _slidenum(sl, 12.35, FOOTER_Y, 0.7, 0.26, size=9,
                      color="5A6670", align=PP_ALIGN.RIGHT)
            chap = chap_by_slide.get(id(sl))
            if chap:
                _text(sl, 8.95, FOOTER_Y, 3.3, 0.26, chap.upper(),
                      size=8.5, color=GREY, align=PP_ALIGN.RIGHT)
        except Exception:
            pass

    # ---- storyboard: the dot-dash editorial view, in FINAL order ----------
    try:
        by_obj = {id(e["sl"]): e for e in placed}
        lines = [f"# Storyboard \u2014 {client}, data through {data_month}", ""]
        for sl in final:
            e = by_obj.get(id(sl))
            if e is None:
                continue
            if e["kind"] == "chapter":
                lines.append(f"\n\u2014 {e['title']}"
                             + (f"  ({e['sub']})" if e["sub"] else ""))
            else:
                flag = "" if e["computed"] else "   [TOPIC LABEL]"
                lines.append(f"  \u00b7 {e['title']}{flag}")
        gaps = [(ti, su) for kind, ti, su, _c in story if kind == "skipped"]
        if gaps:
            lines.append("\n\u2014 Not rendered")
            for ti, su in gaps:
                lines.append(f"  \u00b7 {ti} \u2014 {su}")
        sb = out.parent / "storyboard.md"
        sb.write_text("\n".join(lines), encoding="utf-8")
    except Exception:
        sb = None

    # ---- slide register: the provenance view, in FINAL order ---------------
    try:
        ledger.assign(_prev_slide(), None, None, m)   # reads after the last slide
        reg_gaps = [(ti, su) for kind, ti, su, _c in story if kind == "skipped"]
        reg_main = [t for t in (manifest.get("main_path") or MAIN_PATH)]
        reg_path = provenance.write(provenance.rows(
            final, placed, reg_gaps, reg_main,
            client=client, data_month=data_month), out.parent)
    except Exception as exc:
        skipped.append(f"slide register ({type(exc).__name__}: {exc})")
        reg_path = None

    from ..core.env import save_pptx
    out = save_pptx(prs, out, warn=None)
    return DeckResult(path=out, slides=len(prs.slides), charts=len(made),
                      skipped=skipped, storyboard=sb, register=reg_path,
                      form_census=formaudit.census(final, placed))
