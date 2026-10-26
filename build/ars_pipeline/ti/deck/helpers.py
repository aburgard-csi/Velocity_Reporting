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
import math
import re
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
# Tables sit left of the tile rail, clear of the logo (bottom right); their floor is the slide
# number's band (bottom left, from 7.05in).
TABLE_FLOOR = 7.0
TABLE_MIN_ROW_H = 0.18            # a tightened table row never goes below this
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


def _wrap(text, width, pt, family=BODY_FONT, bold=False):
    """`text` broken into the lines it renders as in `width` inches (RPE's glyph measure)."""
    from textfit import text_width_in
    lines, cur = [], ""
    for word in str(text).split():
        trial = f"{cur} {word}".strip()
        if cur and text_width_in(trial, pt, family, bold) > width - 0.20:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + ([cur] if cur else [])


def _fit_subtitle(text, width):
    """(text, size, lines) for a subtitle held to two lines: 13.5pt, else 12pt, else 12pt cut
    at the end of the second line. v5's box held one line; a longer subtitle ran under the chart."""
    from textfit import text_width_in
    for pt in (13.5, 12):
        lines = _wrap(text, width, pt)
        if len(lines) <= 2:
            return text, pt, len(lines)
    lines = _wrap(text, width, 12)
    second = lines[1]
    while len(second) > 4 and text_width_in(second + "…", 12, BODY_FONT, False) > width - 0.20:
        second = second[:-1].rstrip()
    return f"{lines[0]} {second}…", 12, 2


def _title(slide, title, subtitle=None):
    """Draw the headline and subtitle; return (title, bottom) - where the text actually ends."""
    title, subtitle = _fit_headline(title, subtitle)
    title = polish.title(title)
    subtitle = polish.sub(subtitle, title)
    size, lines = _fit(title)
    height = 0.8 if lines == 1 else 1.05
    _text(slide, MARGIN_L, 0.32, TITLE_W, height, title, size=size, bold=True, font=HEAD_FONT)
    bottom = 0.32 + height
    if subtitle:
        subtitle, pt, n = _fit_subtitle(subtitle, TITLE_W)
        sub_h = 0.32 if n == 1 else 0.58
        _text(slide, MARGIN_L, bottom + 0.02, TITLE_W, sub_h, subtitle, size=pt, color=GREY)
        bottom += 0.02 + sub_h
    return title, bottom


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


INSET = 0.20                      # a text box's own left + right inset, which the validator allows for


def _fit_pt(text, width, sizes, family=HEAD_FONT, bold=True):
    """The largest of `sizes` at which `text` renders on one line in `width` inches (RPE's own
    glyph measure, build/textfit.py), else the smallest."""
    from textfit import text_width_in
    for pt in sizes:
        if text_width_in(str(text), pt, family, bold) <= width - INSET:
            return pt
    return sizes[-1]


def _rail(slide, items, top=1.75, left=RAIL_LEFT, width=2.55):
    """Callout tiles down the right edge (v5's stack arithmetic, RPE's floor). Unlike v5, every
    line is sized to the tile: the label, value and note each step down until they fit on one
    line, the value box ends where the note begins, and a note too long for one line gets two
    when the tile has the room (RPE's validator fails a wrapped one-line box)."""
    n = min(len(items), 5)
    tile_h = 1.22 if n <= 4 else 1.02
    while tile_h > 0.92 and top + (n - 1) * (tile_h + 0.04) + tile_h > RAIL_BOTTOM:
        tile_h = round(tile_h - 0.10, 2)
    # at the smallest tile the stack may still run past the floor (a two-line subtitle pushes
    # the content down): start the stack higher, never into the logo band. The rail column is
    # clear of the title block, so it may rise to 1.0in.
    top = max(1.0, min(top, RAIL_BOTTOM - (n - 1) * (tile_h + 0.04) - tile_h))
    step = max(min(tile_h + 0.14, (RAIL_BOTTOM - top - tile_h) / max(n - 1, 1)), tile_h + 0.04)
    compact = tile_h < 1.12
    inner = width - 0.16
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
        _text(slide, left + 0.08, y + 0.06, inner, 0.26, label,
              size=_fit_pt(label, inner, (10.5, 9.5, 8.5, 8)), bold=True,
              color=WHITE, font=HEAD_FONT, align=PP_ALIGN.CENTER)
        # The value and its note are ONE text box, two paragraphs, starting at the value. As two
        # boxes, the lowest tile's note sat below 5.5in, where fit_layout treats a box as a bottom
        # caption and lifts it - onto the value. One box starts high enough to be left alone, and
        # a value and note in one frame cannot collide.
        v_top = y + (0.28 if compact else 0.36)
        box = _text(slide, left + 0.08, v_top, inner, y + tile_h - 0.04 - v_top, value,
                    size=_fit_pt(value, inner, (19, 17, 15, 13, 12) if compact else (21, 19, 17, 15, 13, 12)),
                    bold=True, color=WHITE, font=HEAD_FONT, align=PP_ALIGN.CENTER)
        if note:
            from textfit import text_width_in
            pt = _fit_pt(note, inner, (9, 8.5, 8, 7.5), BODY_FONT, False)
            if text_width_in(str(note), pt, BODY_FONT, False) > inner - INSET and compact:
                # a short tile has room for one note line: keep what fits, never overflow
                while len(note) > 8 and text_width_in(note + "…", pt, BODY_FONT, False) > inner - INSET:
                    note = note[:-1].rstrip()
                note = note + "…"
            para = box.text_frame.add_paragraph()
            para.alignment = PP_ALIGN.CENTER
            para.space_before = Pt(2)
            r = para.add_run()
            r.text = str(note)
            r.font.size = Pt(pt)
            r.font.name = BODY_FONT
            r.font.color.rgb = WHITE
        y += step
    return left - 0.25


KPI_H = 1.65
KPI_MIN_H = 1.1


def _kpi(slide, left, top, width, label, value, note=None, accent=NAVY):
    """v5's KPI card. RPE: a card that would run past CONTENT_FLOOR is drawn compact in the room
    left (never under KPI_MIN_H), label, value and note scaled with it. A full card placed low ran
    to 7.15in, and fit_layout then re-parked its note over its value as a bottom caption (1615's
    ICS quality slide, 2026-10-23)."""
    h = KPI_H if top + KPI_H <= CONTENT_FLOOR else max(KPI_MIN_H, CONTENT_FLOOR - top)
    k = h / KPI_H
    note_pt = round(10.5 * max(k, 0.85), 1)
    # a note that wraps needs its lines' height inside the card; the value box gives it up, so
    # nothing is left for fit_layout to re-park over the value (1776's ICS habits slide, 2026-10-23)
    # and fit_layout's own estimate (0.105in a character, 0.26in a line, done by 6.92in) must not
    # find it too low either, or it is moved down into the logo zone and then lifted onto the value
    note_top = top + 1.20 * k
    if note:
        lines = len(_wrap(note, width - 0.2, note_pt))
        fit_lines = max(1, math.ceil(len(note) * 0.105 / (width - 0.2)))
        note_top = min(note_top, top + h - 0.04 - lines * note_pt * 1.2 / 72 - 0.04,
                       7.00 - 0.08 - 0.26 * fit_lines)
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top),
                                  Inches(width), Inches(h))
    card.fill.solid()
    card.fill.fore_color.rgb = accent
    card.line.color.rgb = WHITE
    card.line.width = Pt(2)
    card.text_frame.text = ""
    card.shadow.inherit = False
    _text(slide, left + 0.1, top + 0.12 * k, width - 0.2, 0.3 * k, label, size=round(12 * max(k, 0.85), 1),
          bold=True, color=WHITE, font=HEAD_FONT, align=PP_ALIGN.CENTER)
    _text(slide, left + 0.1, top + 0.48 * k, width - 0.2, min(0.66 * k, note_top - top - 0.48 * k), value,
          size=round(28 * k), bold=True, color=WHITE, font=HEAD_FONT, align=PP_ALIGN.CENTER)
    if note:
        _text(slide, left + 0.1, note_top, width - 0.2, top + h - 0.04 - note_top, note,
              size=note_pt, color=WHITE, align=PP_ALIGN.CENTER)


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
    """v5's house table: navy header, banded body, horizontal rules, numbers right-aligned.

    RPE: a table that would run past TABLE_FLOOR (above the slide number) tightens its rows, down
    to TABLE_MIN_ROW_H, with the font scaled to match, rather than running off the slide or dropping
    rows. v5's slides had the same arithmetic and no check for it (1615's closure-hazard table
    under a two-line headline ended at 7.65in on a 7.5in slide, 2026-10-23)."""
    n_rows, n_cols = len(rows), len(rows[0])
    row_h = 0.3
    room = TABLE_FLOOR - top
    if n_rows * row_h > room:
        row_h = max(TABLE_MIN_ROW_H, room / n_rows)
        size = max(7, round(size * row_h / 0.3, 1))
    shape = slide.shapes.add_table(n_rows, n_cols, Inches(left), Inches(top),
                                   Inches(width), Inches(row_h * n_rows))
    table = shape.table
    table.first_row = False
    table.horz_banding = False
    if col_widths:
        for i, cw in enumerate(col_widths):
            table.columns[i].width = Inches(cw)
    for r, row in enumerate(rows):
        table.rows[r].height = Inches(row_h)
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
        self.topics = {}          # id(slide) -> v5's topic label (the slide() fallback)

    def _note(self, slide, title):
        p = self.ctx.pack
        frame.notes(slide, f"Source: {self.source} for client {p['client_id']} {p['client_name']} "
                           f"({p['sources']['odd']}). {self.ctx.lens.label}. Slide: {title}. "
                           f"Computed by the analysis ported from the ARS v5 engine (ti/PORTING.md).")

    def new(self, *_layout):
        s = frame.new_slide(self.ctx.prs)
        self.slides.append(s)
        return s

    def slide(self, pair, fallback):
        s = self.new()
        self.topics[id(s)] = fallback
        title, bottom = (_title(s, pair[0], pair[1] if len(pair) > 1 else None) if pair
                         else _title(s, fallback))
        # numbered AFTER the title: the first text shape is a slide's title (CLAUDE.md, by-title lookups)
        frame.numbered(s)
        from shapes import pill
        pill(s, self.ctx.pill, L=10.15, W=2.70)
        frame.logo(s, self.ctx.pack["client_id"], self.ctx.art_dir)
        self._note(s, title)
        if pair:
            v5_top = 1.72 if _fit(polish.title(pair[0]))[1] == 1 else 1.95
        else:
            v5_top = 1.55
        # content starts below wherever the headline block actually ends (a two-line subtitle
        # pushes it down; v5 assumed one)
        return s, max(v5_top, round(bottom + 0.10, 2))

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

    def _singulars(self):
        """v5 printed "1 accounts" when a count came out at one; RPE's validator fails that."""
        import re
        rx = re.compile(r"\b1 (account|member|institution|competitor|merchant|client|provider)s\b")
        for s in self.slides:
            for sh in s.shapes:
                frames = [sh.text_frame] if sh.has_text_frame else []
                if getattr(sh, "has_table", False) and sh.has_table:
                    frames += [c.text_frame for row in sh.table.rows for c in row.cells]
                for tf in frames:
                    for para in tf.paragraphs:
                        for r in para.runs:
                            if rx.search(r.text):
                                r.text = rx.sub(r"1 \1", r.text)

    _HOUSE = {"lift": "gain", "lifts": "gains", "lifted": "raised"}

    def _house_words(self):
        """RPE's house style bans "lift" and "lifted" (validate_deck BANNED, CLAUDE.md writing style),
        which v5's campaign slides use for the difference-in-differences gain ("responder lift minus
        control", "mean lift"). The word changes, never a figure; a Lift Matrix slide keeps its name,
        as the validator allows."""
        import re
        rx = re.compile(r"\b(lift|lifts|lifted)\b", re.I)

        def swap(mo):
            word = self._HOUSE[mo.group(0).lower()]
            return word.capitalize() if mo.group(0)[0].isupper() else word

        for s in self.slides:
            frames = []
            for sh in s.shapes:
                frames += [sh.text_frame] if sh.has_text_frame else []
                if getattr(sh, "has_table", False) and sh.has_table:
                    frames += [c.text_frame for row in sh.table.rows for c in row.cells]
            if any("lift matrix" in tf.text.lower() for tf in frames):
                continue
            for tf in frames:
                for para in tf.paragraphs:
                    for r in para.runs:
                        if rx.search(r.text):
                            r.text = rx.sub(swap, r.text)

    def run(self, builders, titles, *args):
        """Call each v5 builder as `b(h, *args)`; a builder that declines (returns its reason,
        or raises) becomes a stated slide under its own title. Returns the slides made.

        Some v5 builders decline by returning None without drawing ("When the card gets used" and
        "Recurring payments on the card" with no data); v5 dropped those silently. Here a builder
        that drew nothing is stated too, so no slide ever goes missing without a sentence."""
        h = self.helpers()
        for b in builders:
            name = getattr(b, "__name__", "slide")
            drawn = len(self.slides)
            try:
                why = b(h, *args)
            except Exception as exc:
                why = f"it could not be computed ({type(exc).__name__}: {exc})"
            if not why and len(self.slides) == drawn:
                why = "the figures it needs are not in this client's files"
            if why:
                title = titles.get(name, name.replace("_", " ").capitalize())
                # v5 often words a decline as "<label> (<reason>)", the label being the slide's own
                # title or close to it ("Lose and leak together" on "Where we lose and where we
                # leak"); the title is already on the slide, so only the reason is stated
                m = re.fullmatch(r"[^()]+ \((.+)\)", why.strip())
                if m and not why.startswith("it could not be computed"):
                    why = m.group(1)
                self.declined(title, why)
        self._singulars()
        self._house_words()
        return list(self.slides)

    def helpers(self):
        return {"new": self.new, "slide": self.slide, "chart": self.chart,
                "declined": self.declined, "title": _title,
                "divider": lambda *_a, **_k: None, "rail": _rail, "table": _table,
                "kpi": _kpi, "text": _text, "chart_left": _chart_left, "picture": _picture,
                "fit_picture": _fit_picture, "money": labels.money, "kicker": _kicker,
                "row_budget": _row_budget, "charts": __import__("ti.deck.charts", fromlist=["x"]),
                "MARGIN_L": MARGIN_L, "RIGHT_EDGE": RIGHT_EDGE, "CONTENT_W": CONTENT_W,
                "NAVY": NAVY, "ORANGE": ORANGE, "GREY": GREY}
