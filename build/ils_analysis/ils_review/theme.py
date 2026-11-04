"""
House style and slide primitives for the ILS Program Analysis deck, on OUR styling.

PROVENANCE. The analysis team's `theme.py` laid every slide out for the CSI ILS template's
20.0 x 11.25 in canvas in Source Sans Pro. This version keeps the same function names and the
same *design-space* numbers (the slide modules ported beside it still say `T.CONTENT_TOP`,
`T.textbox(s, 0.60, y, 9.2, ...)`), and moves them onto the RPE canvas:

  * 13.333 x 7.5 in, the canvas `templates/STYLE.md` §4 describes;
  * the palette and type roles come from `build/brand.py` (Montserrat for the title, callouts,
    tiles and bands; Calibri for body text, table cells and captions), never re-declared here;
  * every shape is built through `build/shapes.py` where it has a primitive (textbox, pill,
    add_table style, shadow, data_logo).

How the move works. A coordinate handed to a primitive is a DESIGN-space inch value on the
old canvas. `X`, `Y`, `W`, `H` map it onto the RPE content band (x 0.50-12.83, y 1.65-6.75);
the x and y scales differ by a few percent on purpose, so the band fills the slide exactly.
Fonts are NOT scaled linearly: `pt()` turns an old size into a role-based RPE size with a
floor. Body text and bullets start at the STYLE.md 16 pt and step down only as far as the
box needs (never below 11); table cells are a declared dense-table exception at 10-11 pt;
chart text inside a picture is exempt, as in STYLE.md.

`restyle_fonts.py` is deliberately NOT run on this deck: it raises every run to 16 pt, which
overflows the dense tables. Fonts are assigned by role here, when each shape is made.
"""
from __future__ import annotations

import os
import sys

_BUILD = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _BUILD not in sys.path:
    sys.path.insert(0, _BUILD)

import brand                                              # noqa: E402
import shapes                                             # noqa: E402
from pptx.dml.color import RGBColor                       # noqa: E402
from pptx.enum.shapes import MSO_SHAPE                    # noqa: E402
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN           # noqa: E402
from pptx.util import Emu, Inches, Pt                     # noqa: E402

# ── design space (the analysis team's 20 x 11.25 canvas; kept so ported code reads the same) ──
SLIDE_W = 20.0
SLIDE_H = 11.25
MARGIN_L = 0.55
MARGIN_R = 0.55
CONTENT_W = SLIDE_W - MARGIN_L - MARGIN_R      # 18.9
CONTENT_TOP = 2.12
CONTENT_BOTTOM = 9.60
CONTENT_H = CONTENT_BOTTOM - CONTENT_TOP       # 7.48
FOOTER_X = 3.15

# ── real space: the RPE canvas and its content band (STYLE.md §4) ───────────────────────────
REAL_W, REAL_H = 13.333, 7.5
REAL_L, REAL_R = 0.50, 12.833
REAL_TOP, REAL_BOTTOM = 1.70, 6.72
SX = (REAL_R - REAL_L) / CONTENT_W
SY = (REAL_BOTTOM - REAL_TOP) / CONTENT_H


def X(x):
    """Design x -> real x (inches)."""
    return REAL_L + (x - MARGIN_L) * SX


def Y(y):
    """Design y -> real y (inches)."""
    return REAL_TOP + (y - CONTENT_TOP) * SY


def W(w):
    return w * SX


def H(h):
    return h * SY


def pt(size, floor=11.0):
    """An old design size -> an RPE size by role. Not a linear scale: 15 pt on a 20 in canvas
    is about 10 pt on 13.33, which is the dense-table size; body text is handled by `bullets`
    and the title/subtitle by `Deck.content`, which start from the STYLE.md sizes."""
    return max(floor, round(size * 0.72 * 2) / 2)


_TABLE_FLOOR = [10.0]


def table_pt(size):
    """Table cells: the declared dense-table exception, 10 to 12 pt (8 pt for the matrix tables with
    30+ rows, which cannot fit at 10: STYLE.md section 9 lets a table drop as far as 7.5)."""
    return min(12.0, max(_TABLE_FLOOR[0], round(size * 0.72 * 2) / 2))


# ── layout names kept for diffability with the analysis team's code (unused on our shell) ──
LAYOUT_CONTENT = "BLANK"
LAYOUT_DIVIDER = "BLANK"
LAYOUT_COVER = "BLANK"
LAYOUT_PLAIN = "BLANK"

# ── palette: every name is a brand.py value ─────────────────────────────────────────────────
NAVY = brand.NAVY_RGB
NAVY_DEEP = brand.NAVY_RGB
ORANGE = brand.ORANGE_RGB
WHITE = brand.WHITE_RGB
SUBTLE = brand.TICK_RGB                       # subtitle / selection grey
MUTED = brand.TICK_RGB                        # footnote grey (brand.MUTED is an axis spine, too pale for text)
DARK = brand.NAVY_RGB                         # table body ink (shapes.add_table uses navy)
LIGHT = brand.LABEL_RGB
PALE = brand.LABEL_RGB
BAND = brand.ROWALT_RGB                       # alternating table row
RULE = brand.GRID_RGB                         # hairlines and gridlines
CARD_BG = brand.ROWALT_RGB

_hex = brand._rgb
TEAL = _hex(brand.TEAL)
STEEL = _hex(brand.STEEL)
STEEL_SOFT = _hex(brand.STEEL_SOFT)
SLATE = _hex(brand.SLATE)
GOLD = _hex(brand.GOLD)
GRAY = _hex(brand.MUTED)
# Semantic colours for good / bad. The brand has no green; the palette's own TEAL carries
# "favourable" and the brand red carries "unfavourable", so a chart never reaches for a hex.
GREEN = TEAL
RED = _hex(brand.CSI_RED)
BLUE_1 = brand.NAVY_RGB
BLUE_2 = _hex(brand.CSI_LIGHT_BLUE)
PURPLE = SLATE
CORAL = brand.ORANGE_RGB

SERIES_COLORS = [NAVY, ORANGE, TEAL, SLATE, STEEL, GOLD, STEEL_SOFT]

KNOWN_TYPE_COLORS = {
    "Business": TEAL,
    "Personal": NAVY,
    "Second Chance": SLATE,
}
EXTRA_COLORS = [GOLD, STEEL, STEEL_SOFT, SLATE, ORANGE, GRAY]

HEAD = brand.HEAD
BODY = brand.BODY
FONT = BODY                    # the old name for "the deck's face" is body text
FONT_FALLBACK = BODY

# Matplotlib-side equivalents (hex) so rendered images match native shapes.
HEX = {
    "navy": brand.NAVY, "orange": brand.ORANGE, "subtle": brand.TICK, "muted": brand.TICK,
    "grid": brand.GRID, "band": brand.ROWALT, "teal": brand.TEAL, "purple": brand.SLATE,
    "green": brand.TEAL, "red": brand.CSI_RED, "gray": brand.MUTED, "blue": brand.NAVY,
    "coral": brand.ORANGE, "bg": brand.WHITE, "steel": brand.STEEL, "steel_soft": brand.STEEL_SOFT,
    "label": brand.LABEL, "gold": brand.GOLD, "slate": brand.SLATE,
}

# Standard confidentiality notice. The CSI template's cover carried it; our cover does not, so
# it goes in the speaker notes of the cover slide (and is still available to a caller).
CONFIDENTIALITY_NOTICE = (
    "This document constitutes the confidential and proprietary information "
    "(and includes trade secrets) of CSI and Velocity Solutions, LLC and/or its "
    "legal subsidiaries and affiliates. Any distribution, disclosure or forwarding "
    "of this presentation to any individual or entity not expressly authorized in "
    "writing by Velocity Solutions to receive this presentation is expressly "
    "prohibited.  In the event of any unauthorized distribution, disclosure or "
    "forwarding of this presentation or software design, appropriate remedies will "
    "be pursued by CSI."
)


# ═════════════════════════════ small utilities ══════════════════════════════
def hex_rgb(value):
    """'#00274C' (or '00274C') -> RGBColor, for palettes shared with matplotlib."""
    s = str(value).lstrip("#")
    return RGBColor(int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def assign_type_colors(types):
    """Stable colour per account type, familiar names first."""
    out, pool = {}, list(EXTRA_COLORS)
    for t in types:
        out[t] = KNOWN_TYPE_COLORS.get(t) or (pool.pop(0) if pool else NAVY)
    return out


def _set_run(run, text, size, *, bold=False, color=DARK, font=BODY, italic=False):
    run.text = str(text)
    f = run.font
    f.size = Pt(size)
    f.bold = bold
    f.italic = italic
    f.color.rgb = color
    f.name = font
    return run


def textbox(slide, x, y, w, h, text, size, *, bold=False, color=DARK,
            align=PP_ALIGN.LEFT, wrap=True, font=BODY, anchor=None,
            line_spacing=None, italic=False, floor=11.0, raw=False):
    """A plain textbox, in DESIGN coordinates (`raw=True` takes real inches).

    `text` may be a string or a list of (text, kwargs) runs. `size` is a design size and goes
    through `pt()`; with `raw=True` it is a real point size.
    """
    if not raw:
        x, y, w, h = X(x), Y(y), W(w), H(h)
        size = pt(size, floor)
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.margin_left = tf.margin_right = Emu(0)
    tf.margin_top = tf.margin_bottom = Emu(0)
    if anchor is not None:
        tf.vertical_anchor = anchor
    p = tf.paragraphs[0]
    p.alignment = align
    if line_spacing:
        p.line_spacing = line_spacing
    if isinstance(text, str):
        _set_run(p.add_run(), text, size, bold=bold, color=color, font=font, italic=italic)
    else:
        for chunk in text:
            if isinstance(chunk, tuple):
                t, kw = chunk
            else:
                t, kw = chunk, {}
            sz = kw.get("size", size)
            sz = sz if raw else pt(sz, floor)
            _set_run(p.add_run(), t, sz, bold=kw.get("bold", bold),
                     color=kw.get("color", color), font=font, italic=kw.get("italic", italic))
    return tb


def fit_text_size(items, w, h, size, *, min_size=11.0, line_spacing=1.12,
                  space_after=5, bullet_chars=3):
    """Largest size <= `size` at which `items` still fit a w x h box (REAL inches and points).

    PowerPoint's own autofit only applies when the file is opened and edited, so a generated
    overlong block silently runs off the slide. This estimates wrapped height and steps the size
    down until it fits. The 0.5 em average character width is deliberately conservative.
    """
    texts = [str(i[0] if isinstance(i, tuple) else i) for i in items]
    texts = [t for t in texts if t.strip()]
    if not texts:
        return size
    s = float(size)
    while s > min_size:
        chars_per_line = max(12, int(w * 144 / s))
        lines = sum(max(1, -(-(len(t) + bullet_chars) // chars_per_line)) for t in texts)
        needed = (lines * s * line_spacing + len(texts) * space_after) / 72.0
        if needed <= h:
            return round(s, 1)
        s -= 0.5
    return round(min_size, 1)


def bullets(slide, x, y, w, h, items, size=16, *, color=DARK, bullet_color=ORANGE,
            line_spacing=1.12, space_after=5, bold_first=False, autofit=True):
    """A bulleted textbox in design coordinates. Items are strings or (text, indent_level).

    Starts at the STYLE.md 16 pt and shrinks only until the text fits the box (not below 11).
    The old `size` argument is ignored for that reason: it described a 20 in canvas.
    """
    rx, ry, rw, rh = X(x), Y(y), W(w), H(h)
    real = fit_text_size(items, rw, rh, 16.0, line_spacing=line_spacing,
                         space_after=space_after, min_size=11.0) if autofit else 16.0
    tb = slide.shapes.add_textbox(Inches(rx), Inches(ry), Inches(rw), Inches(rh))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Emu(0)
    tf.margin_top = tf.margin_bottom = Emu(0)
    first = True
    for item in items:
        level = 0
        if isinstance(item, tuple):
            item, level = item
        if not str(item).strip():
            continue
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.line_spacing = line_spacing
        p.space_after = Pt(space_after)
        _set_run(p.add_run(), "▪  " if level == 0 else "–  ",
                 real, bold=True, color=bullet_color if level == 0 else GRAY)
        _set_run(p.add_run(), item, real - (0.5 if level else 0),
                 bold=bold_first and level == 0, color=color)
    return tb


def rect(slide, x, y, w, h, fill, *, line=None, line_w=0.75):
    sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(X(x)), Inches(Y(y)),
                                Inches(W(w)), Inches(H(h)))
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
        sh.line.width = Pt(line_w)
    sh.shadow.inherit = False
    return sh


def band_label(slide, x, y, w, text, *, h=0.50, bg=NAVY, fg=WHITE, size=16):
    """A navy section strip above a table or a bullet block (STYLE.md §9 'section bars')."""
    sh = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(X(x)), Inches(Y(y)),
                                Inches(W(w)), Inches(max(0.36, H(h))))
    sh.fill.solid()
    sh.fill.fore_color.rgb = bg
    sh.line.fill.background()
    sh.shadow.inherit = False
    tf = sh.text_frame
    tf.margin_left = Inches(0.14)
    tf.margin_right = Inches(0.10)
    tf.margin_top = tf.margin_bottom = Emu(0)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    _set_run(p.add_run(), text, 14, bold=True, color=fg, font=HEAD)
    return sh


def note(slide, x, y, w, text, size=13, color=MUTED, italic=True):
    return textbox(slide, x, y, w, 0.4, text, size, color=color, italic=italic)


def footnote(slide, text, size=12.5, color=MUTED):
    """A caveat line under the content band, kept clear of the data logo at the lower right."""
    return textbox(slide, FOOTER_X, CONTENT_BOTTOM + 0.04, 12.0, 0.60, text, 12,
                   color=color, italic=True)


# ═════════════════════════════ the Deck object ══════════════════════════════
class Deck:
    """Owns the Presentation plus the per-client metadata every builder needs.

    Slides are appended in build order. `sources` is the Source line written to each slide's
    speaker notes (STYLE.md §4: selection on the slide, source in the notes); a builder sets
    `deck.source = "..."` for what it is about to make, or passes `source=` per slide.
    """

    def __init__(self, shell, client, date_str, *, client_id="", footer_label="ILS Program Analysis",
                 footer_extra="", types=None, codes=None, colors=None, source=""):
        self.template = shell
        self.prs = shell.prs
        self.client = client
        self.client_id = str(client_id or "")
        self.date_str = date_str
        self.footer_label = footer_label
        self.footer_extra = footer_extra
        self.types = list(types or [])
        self.codes = dict(codes or {})
        self.colors = dict(colors or {})
        self.relabel_mrpc = False
        self.generated = []          # slides this run created, in build order
        self._section = None
        self.source = source         # default Source line for the slides being built
        self.pill_text = ""          # the "As of" pill on every content slide
        self.numbered = []           # content slides, in build order: they get a number and the data logo
        self.chart_dir = ""          # where chart PNGs and their sidecars are written (set by build.py)
        self.sidecars = []           # one dict per figure, written as figures_index.json
        self.ref = {}                # hand-built-deck reference figures for the parity checks

    # ── terminology ────────────────────────────────────────────────────────
    def term(self, s):
        """Optionally relabel 'MRPC' as 'CashPlease' in display text."""
        import re
        if not self.relabel_mrpc or "MRPC" not in str(s):
            return s
        out = str(s).replace("MRPC", "CashPlease")
        return re.sub(r"CashPlease(?:\s+CashPlease)+", "CashPlease", out)

    # ── slide creation ─────────────────────────────────────────────────────
    def _add(self, section):
        slide = self.template.add_slide()
        self.template.tag(slide, section)
        self.generated.append(slide)
        return slide

    def set_notes(self, slide, source=None, extra=None):
        src = source or self.source
        lines = []
        if src:
            lines.append(src if src.lower().startswith("source") else f"Source: {src}")
        if extra:
            lines.append(extra)
        if lines:
            slide.notes_slide.notes_text_frame.text = "\n".join(lines)

    def content(self, title, subtitle=None, *, section=None, footer=True, rule=True,
                source=None, pill=True):
        """A content slide in the STYLE.md §4 anatomy: title, selection subtitle, period pill."""
        from textfit import fits_one_line
        slide = self._add(section or self._section)
        pill_w = 2.55 if (pill and self.pill_text) else 0.0
        title_w = shapes_title_width(pill_w)
        size = 28
        while size > 18 and not fits_one_line(title, title_w - 0.1, size, HEAD, True):
            size -= 2
        shapes.textbox(slide, 0.50, 0.28, title_w, 0.62, title, size, NAVY, True, PP_ALIGN.LEFT, HEAD,
                       MSO_ANCHOR.TOP, name="Slide title")
        if pill and self.pill_text:
            shapes.pill(slide, self.pill_text, L=REAL_R - 2.55, T=0.34, W=2.55, H=0.5)
        if subtitle:
            sub_pt = 16
            if not fits_one_line(subtitle, 12.2, sub_pt, BODY):
                sub_pt = 14
            shapes.textbox(slide, 0.50, 0.92, 12.33, 0.70, subtitle, sub_pt, SUBTLE, False,
                           PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP, name="Selection subtitle")
        self.set_notes(slide, source)
        self.numbered.append(slide)
        return slide

    def divider(self, title, eyebrow=None, blurb=None, *, section=None, source=None):
        """A section divider drawn by `cover_divider.draw_divider` (the brand template's)."""
        import cover_divider
        slide = self._add(section or self._section)
        text = blurb or eyebrow or ""
        if blurb and eyebrow:
            text = f"{eyebrow}  ·  {blurb}"
        cover_divider.draw_divider(slide, title.replace("\n", " "), text[:150])
        self.set_notes(slide, source or f"Source: section divider for {self.client} (no data).")
        return slide

    def cover(self, headline, sub, tagline=None, *, section=None):
        """A part-title slide; the deck cover itself is `Shell.draw_cover` (build.py)."""
        slide = self._add(section or self._section)
        import cover_divider
        cover_divider.draw_divider(slide, headline.replace("\n", " "), sub)
        return slide

    def footer(self, slide):          # the RPE anatomy carries no footer line; kept for callers
        return None

    # ── tables ─────────────────────────────────────────────────────────────
    def table(self, slide, x, y, w, col_widths, n_rows, *, row_h=0.46, header_h=0.54):
        """Add a table sized to `col_widths` (design inches, scaled to fit `w`)."""
        total = float(sum(col_widths)) or 1.0
        rw = W(w)
        widths = [c / total * rw for c in col_widths]
        rh, rhead = H(row_h), H(header_h)
        small = rh < 0.205
        _TABLE_FLOOR[0] = 8.0 if small else 10.0
        rh = max(rh, 0.165 if small else 0.21)
        rhead = max(rhead, 0.24 if small else 0.26)
        h = rhead + rh * max(0, n_rows - 1)
        gf = slide.shapes.add_table(n_rows, len(col_widths), Inches(X(x)), Inches(Y(y)),
                                    Inches(rw), Inches(h))
        tbl = gf.table
        for i, cw in enumerate(widths):
            tbl.columns[i].width = Inches(cw)
        tbl.rows[0].height = Inches(rhead)
        for r in range(1, n_rows):
            tbl.rows[r].height = Inches(rh)
        _plain_table_style(tbl)
        return tbl


def shapes_title_width(pill_w):
    return (REAL_R - REAL_L) - (pill_w + 0.2 if pill_w else 0.0)


def _plain_table_style(tbl):
    """Turn off first-row/banding emphasis so explicit cell fills read cleanly."""
    el = tbl._tbl.tblPr
    for attr in ("firstRow", "bandRow", "firstCol", "bandCol", "lastRow", "lastCol"):
        el.set(attr, "0")


# ── cell helpers (shapes.add_table's look: navy header, white/ROWALT rows, Calibri cells) ──
def cell(c, text, size=15, *, bold=False, align=PP_ALIGN.CENTER, color=DARK,
         bg=None, wrap=True, italic=False):
    tf = c.text_frame
    tf.word_wrap = wrap
    tf.margin_left = tf.margin_right = Pt(4)
    tf.margin_top = tf.margin_bottom = Pt(1.5)
    p = tf.paragraphs[0]
    p.alignment = align
    _set_run(p.add_run(), text, table_pt(size), bold=bold, color=color, italic=italic, font=BODY)
    c.vertical_anchor = MSO_ANCHOR.MIDDLE
    c.fill.solid()
    c.fill.fore_color.rgb = bg if bg is not None else WHITE
    return c


def head_cell(c, text, size=15, *, bg=NAVY, fg=WHITE, align=PP_ALIGN.CENTER):
    return cell(c, text, size, bold=True, color=fg, bg=bg, align=align)


def zebra(row_index):
    """Alternating row fill: ROWALT on even rows, white on odd ones (shapes.add_table's order)."""
    return BAND if row_index % 2 == 0 else None


def fill_table(tbl, headers, rows, *, size=15, head_size=15, align=None,
               head_bg=NAVY, cell_color=None):
    """Fill a table from a header list and a list of row lists.

    `align`      per-column alignment list (defaults: first col left, rest centre)
    `cell_color` optional fn(row_idx, col_idx, value) -> RGBColor or None
    """
    n_cols = len(headers)
    if align is None:
        align = [PP_ALIGN.LEFT] + [PP_ALIGN.CENTER] * (n_cols - 1)
    for j, htext in enumerate(headers):
        head_cell(tbl.cell(0, j), htext, head_size, bg=head_bg,
                  align=align[j] if j < len(align) else PP_ALIGN.CENTER)
    for i, row in enumerate(rows):
        bg = zebra(i)
        for j in range(n_cols):
            v = row[j] if j < len(row) else ""
            col = cell_color(i, j, v) if cell_color else None
            cell(tbl.cell(i + 1, j), v, size, bg=bg, color=col or DARK,
                 align=align[j] if j < len(align) else PP_ALIGN.CENTER)
    return tbl


# ── KPI cards: the RPE tile (navy, Montserrat value, Calibri label) ─────────────────────
def kpi_cards(slide, x, y, w, h, cards, *, gap=0.28, accent=NAVY):
    """Row of stat tiles: each card is (value, label, sub) — sub may be None."""
    n = max(1, len(cards))
    cw = (w - gap * (n - 1)) / n
    for i, c in enumerate(cards):
        value, label = c[0], c[1]
        sub = c[2] if len(c) > 2 else None
        cx = x + i * (cw + gap)
        tile = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(X(cx)), Inches(Y(y)),
                                      Inches(W(cw)), Inches(H(h)))
        tile.fill.solid()
        tile.fill.fore_color.rgb = NAVY
        tile.line.fill.background()
        shapes.shadow(tile)
        rx, ry, rw, rh = X(cx) + 0.06, Y(y), W(cw) - 0.12, H(h)
        shapes.textbox(slide, rx, ry + rh * 0.05, rw, rh * 0.34, value, 28, WHITE, True,
                       PP_ALIGN.CENTER, HEAD, MSO_ANCHOR.MIDDLE)
        shapes.textbox(slide, rx, ry + rh * 0.40, rw, rh * 0.28, label, 12, WHITE, True,
                       PP_ALIGN.CENTER, BODY, MSO_ANCHOR.TOP)
        if sub:
            shapes.textbox(slide, rx, ry + rh * 0.70, rw, rh * 0.28, sub, 11, brand.LABEL_RGB,
                           False, PP_ALIGN.CENTER, BODY, MSO_ANCHOR.TOP,
                           name=shapes.SMALL_TILE_LABEL)


def band_real(slide, L, T, W, text, h=0.40):
    """A navy section bar in REAL inches (the new slides are drawn on the RPE canvas directly)."""
    sh = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(L), Inches(T), Inches(W), Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = NAVY
    sh.line.fill.background()
    sh.shadow.inherit = False
    tf = sh.text_frame
    tf.margin_left = Inches(0.14)
    tf.margin_right = Inches(0.10)
    tf.margin_top = tf.margin_bottom = Emu(0)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    _set_run(p.add_run(), text, 14, bold=True, color=WHITE, font=HEAD)
    return sh


def bullets_real(slide, L, T, W, H, items, *, size=16.0, min_size=11.0, color=DARK):
    """A bulleted text box in REAL inches, 16 pt stepping down only as far as the box needs."""
    real = fit_text_size(items, W, H, size, line_spacing=1.12, space_after=5, min_size=min_size)
    tb = slide.shapes.add_textbox(Inches(L), Inches(T), Inches(W), Inches(H))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Emu(0)
    tf.margin_top = tf.margin_bottom = Emu(0)
    first = True
    for item in items:
        if not str(item).strip():
            continue
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.line_spacing = 1.12
        p.space_after = Pt(5)
        _set_run(p.add_run(), "▪  ", real, bold=True, color=ORANGE)
        _set_run(p.add_run(), item, real, color=color)
    return tb


def two_column_text(slide, y, left_title, left_items, right_title, right_items, *,
                    size=16, h=None):
    """Two headed bullet columns filling the content band."""
    h = h or (CONTENT_BOTTOM - y)
    cw = (CONTENT_W - 0.9) / 2
    for i, (t, items) in enumerate(((left_title, left_items), (right_title, right_items))):
        cx = MARGIN_L + i * (cw + 0.9)
        band_label(slide, cx, y, cw, t)
        bullets(slide, cx + 0.06, y + 0.70, cw - 0.12, h - 0.76, items, size)


def image(slide, path, x, y, w, h):
    """Place an image centred in the (x, y, w, h) design box, preserving aspect ratio."""
    from PIL import Image
    rx, ry, rw, rh = X(x), Y(y), W(w), H(h)
    with Image.open(path) as im:
        iw, ih = im.size
    ar = iw / ih
    if ar >= rw / rh:
        dw, dh = rw, rw / ar
    else:
        dh, dw = rh, rh * ar
    return slide.shapes.add_picture(path, Inches(rx + (rw - dw) / 2), Inches(ry + (rh - dh) / 2),
                                    Inches(dw), Inches(dh))


def image_real(slide, path, left, top, max_w, max_h):
    """Place an image in a REAL-inch box (the new slides are drawn in real coordinates)."""
    return shapes.fit_picture(slide, path, left, top, max_w, max_h)
