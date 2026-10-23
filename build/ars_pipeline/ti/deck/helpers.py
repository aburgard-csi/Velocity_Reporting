"""
helpers.py — the helper bundle v5's slide builders draw through (`h` in their signatures),
re-implemented on RPE's slide anatomy so a ported builder keeps its v5 call shape.

v5 (`ars/deck/build.py`) laid content right of a navy spine at 1.18in; RPE slides carry the
title top-left at 0.6in with the period pill beside it, the client's logo bottom-right and the
slide number bottom-left (templates/STYLE.md). The grid constants below are RPE's, and the
builders read them from `h`, so their arithmetic lands on this grid unchanged.

Two RPE rules v5 did not have are kept here, once, for every ported slide:
  * every slide gets speaker notes with a Source line naming the client (CLAUDE.md);
  * a slide v5 would have DECLINED for missing data is not dropped: `declined()` draws it
    with the sentence saying why (CLAUDE.md: never drop slides automatically).
"""
from pathlib import Path

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

import brand
from ti import frame
from ti.deck import labels, polish

NAVY, ORANGE, GREY, WHITE = brand.NAVY_RGB, brand.ORANGE_RGB, brand.TICK_RGB, brand.WHITE_RGB
HEAD_FONT, BODY_FONT = brand.HEAD, brand.BODY

SLIDE_W, SLIDE_H = 13.333, 7.5
MARGIN_L = 0.6
RIGHT_EDGE = 12.73
CONTENT_W = RIGHT_EDGE - MARGIN_L
TITLE_W = 9.4                     # the title stops short of the period pill (10.15in)
RAIL_LEFT = RIGHT_EDGE - 2.55
RAIL_GUTTER = 0.28
RAIL_BOTTOM = 6.62                # clear of the logo band (6.78in)
CONTENT_FLOOR = 6.72
HEADLINE_MAX = 90
V5_TITLE_W = 12.09                # the width polish.title_fit's line budgets were written for


def _fit(text):
    """(size, lines) for a title in RPE's narrower title box: polish.title_fit on the length
    the text would have at v5's width, so a title that wraps here is sized as wrapping."""
    return polish.title_fit("x" * round(len(text) * V5_TITLE_W / TITLE_W))
BAND_FILL = brand._rgb(brand.ROWALT)
BORDER_CLR = brand.GRID.lstrip("#")
_DARK_FILLS = {"00274C"}


def _text(slide, left, top, width, height, text, size=14, bold=False,
          color=NAVY, font=BODY_FONT, align=PP_ALIGN.LEFT, wrap=True):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.name = font
    r.font.color.rgb = color
    return box


def _fit_headline(title, subtitle=None):
    """v5's rule: a title past ~90 characters splits at a clause, the tail joining the subtitle."""
    if len(title) > HEADLINE_MAX:
        cut = title.rfind(" — ", 0, HEADLINE_MAX)
        if cut < 30:
            cut = title.rfind(", ", 30, HEADLINE_MAX)
        if cut >= 30:
            tail = title[cut:].lstrip(" —,")
            title = title[:cut].rstrip()
            subtitle = tail if not subtitle else f"{tail} — {subtitle}"
    return title, subtitle


def _title(slide, title, subtitle=None):
    title, subtitle = _fit_headline(title, subtitle)
    title = polish.title(title)
    subtitle = polish.sub(subtitle, title)
    size, lines = _fit(title)
    height = 0.8 if lines == 1 else 1.05
    _text(slide, MARGIN_L, 0.32, TITLE_W, height, title, size=size, bold=True, font=HEAD_FONT)
    if subtitle:
        _text(slide, MARGIN_L, 0.32 + height + 0.02, TITLE_W, 0.5, subtitle, size=13.5, color=GREY)
    return title


def _fit_picture(slide, image, left, top, max_w, max_h):
    """Both dimensions constrained, aspect kept, clamped to the content grid (v5's rule)."""
    from PIL import Image
    with Image.open(image) as img:
        w, h = img.size
    aspect = w / h
    max_w = min(max_w, RIGHT_EDGE - left)
    height = min(max_h, CONTENT_FLOOR - top, max_w / aspect)
    width = height * aspect
    slide.shapes.add_picture(str(image), Inches(left), Inches(top), Inches(width), Inches(height))
    return width, height


def _chart_left(slide, image, top, right_edge, max_h=4.9):
    _fit_picture(slide, image, MARGIN_L, top, max_w=right_edge - MARGIN_L, max_h=max_h)


def _picture(slide, image, top=1.75, max_h=5.0, rail=False):
    from PIL import Image
    with Image.open(image) as img:
        w, h = img.size
    field = (RAIL_LEFT - RAIL_GUTTER - MARGIN_L) if rail else CONTENT_W
    aspect = w / h
    height = min(max_h, field / aspect)
    width = height * aspect
    if width > field:
        width, height = field, field / aspect
    _fit_picture(slide, image, MARGIN_L + (field - width) / 2, top, max_w=width, max_h=height)
    return top + height


def _rail(slide, items, top=1.75, left=RAIL_LEFT, width=2.55):
    """Callout tiles down the right edge (v5's stack arithmetic, RPE's floor)."""
    n = min(len(items), 5)
    tile_h = 1.22 if n <= 4 else 1.02
    while tile_h > 0.92 and top + (n - 1) * (tile_h + 0.04) + tile_h > RAIL_BOTTOM:
        tile_h = round(tile_h - 0.10, 2)
    step = max(min(tile_h + 0.14, (RAIL_BOTTOM - top - tile_h) / max(n - 1, 1)), tile_h + 0.04)
    compact = tile_h < 1.12
    y = top
    for label, value, note in items[:5]:
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(y),
                                      Inches(width), Inches(tile_h))
        card.fill.solid()
        card.fill.fore_color.rgb = NAVY
        card.line.color.rgb = WHITE
        card.line.width = Pt(1.5)
        card.shadow.inherit = False
        card.text_frame.text = ""
        _text(slide, left + 0.08, y + 0.06, width - 0.16, 0.26, label, size=10.5, bold=True,
              color=WHITE, font=HEAD_FONT, align=PP_ALIGN.CENTER)
        _text(slide, left + 0.08, y + (0.3 if compact else 0.36), width - 0.16, 0.5, value,
              size=19 if compact else 21, bold=True, color=WHITE, font=HEAD_FONT, align=PP_ALIGN.CENTER)
        if note:
            _text(slide, left + 0.08, y + (0.72 if compact else 0.88), width - 0.16, 0.28, note,
                  size=9, color=WHITE, align=PP_ALIGN.CENTER)
        y += step
    return left - 0.25


def _kpi(slide, left, top, width, label, value, note=None, accent=NAVY):
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top),
                                  Inches(width), Inches(1.65))
    card.fill.solid()
    card.fill.fore_color.rgb = accent
    card.line.color.rgb = WHITE
    card.line.width = Pt(2)
    card.text_frame.text = ""
    card.shadow.inherit = False
    _text(slide, left + 0.1, top + 0.12, width - 0.2, 0.3, label, size=12, bold=True,
          color=WHITE, font=HEAD_FONT, align=PP_ALIGN.CENTER)
    _text(slide, left + 0.1, top + 0.48, width - 0.2, 0.66, value, size=28, bold=True,
          color=WHITE, font=HEAD_FONT, align=PP_ALIGN.CENTER)
    if note:
        _text(slide, left + 0.1, top + 1.20, width - 0.2, 0.34, note, size=10.5,
              color=WHITE, align=PP_ALIGN.CENTER)


def _cell_bottom_border(cell):
    tcPr = cell._tc.get_or_add_tcPr()
    for el in tcPr.findall(qn("a:lnB")):
        tcPr.remove(el)
    ln = tcPr.makeelement(qn("a:lnB"), {"w": "6350", "cap": "flat"})
    fill = ln.makeelement(qn("a:solidFill"), {})
    fill.append(fill.makeelement(qn("a:srgbClr"), {"val": BORDER_CLR}))
    ln.append(fill)
    tcPr.insert(0, ln)


def _table(slide, rows, left, top, width, col_widths=None, size=11, header=True, cell_fill=None):
    """v5's house table: navy header, banded body, horizontal rules, numbers right-aligned."""
    n_rows, n_cols = len(rows), len(rows[0])
    shape = slide.shapes.add_table(n_rows, n_cols, Inches(left), Inches(top),
                                   Inches(width), Inches(0.32 * n_rows))
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
            cell.margin_top = cell.margin_bottom = Inches(0.02)
            cell.margin_left = cell.margin_right = Inches(0.06)
            is_header = header and r == 0
            fill = None if is_header else (cell_fill(r, c) if cell_fill else None)
            cell.fill.solid()
            if is_header:
                cell.fill.fore_color.rgb = NAVY
            elif fill is not None:
                cell.fill.fore_color.rgb = fill
            else:
                cell.fill.fore_color.rgb = BAND_FILL if r % 2 == 0 else WHITE
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
    return max(2, min(rows_wanted, int((bottom - top - 0.1) / row_h) - 1))


def _kicker(_slide, _text_unused=None):
    return None


class Deck:
    """One chapter's drawing context: the helpers, the charts folder, and what it declined."""

    def __init__(self, ctx, chapter_source, charts_dir):
        self.ctx = ctx
        self.source = chapter_source
        self.charts_dir = Path(charts_dir)
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        self.slides = []
        self.declines = []

    def _note(self, slide, title):
        p = self.ctx.pack
        frame.notes(slide, f"Source: {self.source} for client {p['client_id']} {p['client_name']} "
                           f"({p['sources']['odd']}). {self.ctx.lens.label}. Slide: {title}. "
                           f"Computed by the analysis ported from the ARS v5 engine (ti/PORTING.md).")

    def new(self, *_layout):
        s = frame.numbered(frame.new_slide(self.ctx.prs))
        self.slides.append(s)
        return s

    def slide(self, pair, fallback):
        s = self.new()
        title = _title(s, pair[0], pair[1] if len(pair) > 1 else None) if pair else _title(s, fallback)
        from shapes import pill
        pill(s, self.ctx.pill, L=10.15, W=2.70)
        frame.logo(s, self.ctx.pack["client_id"], self.ctx.art_dir)
        self._note(s, title)
        if pair:
            return s, 1.72 if _fit(polish.title(pair[0]))[1] == 1 else 1.95
        return s, 1.55

    def declined(self, title, reason):
        """The slide v5 would have left out, drawn with the sentence saying why."""
        s, top = self.slide(None, title)
        _text(s, MARGIN_L, top + 0.4, CONTENT_W, 1.2,
              f"Not shown for this client: {reason}.", size=18, color=GREY)
        self.declines.append((title, reason))
        return s

    def chart(self, name, fn, *a, **kw):
        target = self.charts_dir / f"{name}.png"
        try:
            return fn(*a, target, **kw)
        except Exception as exc:
            self.declines.append((name, f"chart failed ({type(exc).__name__}: {exc})"))
            return None

    def run(self, builders, titles, *args):
        """Call each v5 builder as `b(h, *args)`; a builder that declines (returns its reason,
        or raises) becomes a stated slide under its own title. Returns the slides made."""
        h = self.helpers()
        for b in builders:
            name = getattr(b, "__name__", "slide")
            try:
                why = b(h, *args)
            except Exception as exc:
                why = f"it could not be computed ({type(exc).__name__}: {exc})"
            if why:
                self.declined(titles.get(name, name.replace("_", " ").capitalize()), why)
        return list(self.slides)

    def helpers(self):
        return {"new": self.new, "slide": self.slide, "chart": self.chart,
                "divider": lambda *_a, **_k: None, "rail": _rail, "table": _table,
                "kpi": _kpi, "text": _text, "chart_left": _chart_left, "picture": _picture,
                "fit_picture": _fit_picture, "money": labels.money, "kicker": _kicker,
                "row_budget": _row_budget, "charts": __import__("ti.deck.charts", fromlist=["x"]),
                "MARGIN_L": MARGIN_L, "RIGHT_EDGE": RIGHT_EDGE, "CONTENT_W": CONTENT_W,
                "NAVY": NAVY, "ORANGE": ORANGE, "GREY": GREY}
