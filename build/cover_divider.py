#!/usr/bin/env python3
"""
cover_divider.py — the cover and the section dividers, drawn the same way by every program
(Aaron, 2026-10-02: "move the section dividers and title slides into main", from the
redesign prototype in prototype/ and docs/STYLE-PROPOSAL-2026-10-02.md).

Cover (navy, left-aligned): the client's own logo on a white card top-left, the reporting
month at 84 pt, the client name in orange with the "Executive Review  •  <month>" line
under it, the included products as outline chips, the CSI | Velocity lockup bottom-right.

Section divider (navy, left-aligned): the section name at 52 pt, the
benefits line in orange, up to three headline figures for the section at 40 pt, and — in a
combined deck only — a progress track along the bottom naming every program in the deck
with the current one in orange. The lockup sits top-right.

What the rest of the pipeline relies on, and what this module keeps true:
  * the cover is still the one slide whose text carries "Executive Review"
    (assemble_combined._is_cover), and its client + month are still readable from one
    text frame holding "<client>" then "Executive Review  •  <month>"
    (validate_deck._cover_client_and_month, assemble_combined._period);
  * the FIRST text shape on each slide is still its title — the product name on the
    cover (the first chip), the section name on a divider — so every by-title lookup,
    section_slides() and the tests keep working;
  * a full-bleed navy rectangle is still the first shape, which is how fit_layout and the
    ARS branding pass recognise a cover or divider and leave it un-numbered;
  * no drop shadows, and no run below the 16 pt floor (restyle_fonts.MIN), so nothing on
    these slides depends on an exemption.

Shapes this module draws are NAMED (TAG_*), so the combiner can replace the product chips
and redraw the progress track on a slide it did not build.
"""
import os
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

import brand

try:
    from textfit import text_width_in
except Exception:                                  # pragma: no cover
    text_width_in = None

BUILD = os.path.dirname(os.path.abspath(__file__))
LOCKUP_PNG = os.path.join(BUILD, "assets", "logo.png")

SLIDE_W, SLIDE_H = 13.333, 7.5
MARGIN, GUTTER, NCOL = 0.5, 0.2, 12
COLW = (SLIDE_W - 2 * MARGIN - (NCOL - 1) * GUTTER) / NCOL

HERO = "Montserrat ExtraBold"
HEAD = "Montserrat SemiBold"
KICK = "Montserrat"
BODY = "Calibri"
MIN_PT = 16                     # restyle_fonts.MIN — nothing here goes below it

PRODUCT_ARS = "Account Revenue Solution®"
PRODUCT_ICS = "Invitation Checking® System"
PRODUCT_MRPC = "MyRewards Premium Cards®"
PRODUCT_CP = "CashPlease®"
TRACK_LABEL = {PRODUCT_ARS: "ARS", PRODUCT_ICS: "ICS", PRODUCT_MRPC: "MRPC", PRODUCT_CP: "CashPlease"}

TAG_COVER = "rpe:cover"
TAG_COVER_CHIP = "rpe:cover:chip"
TAG_DIVIDER = "rpe:divider"
TAG_TRACK = "rpe:divider:track"

CHIP_Y, CHIP_H, CHIP_GAP, CHIP_PAD = 5.45, 0.42, 0.15, 0.5
TRACK_Y = 6.5


def _rgb(hx):
    return RGBColor.from_string(hx.lstrip("#"))


def span(c0, n):
    """x, w in inches for grid columns c0 .. c0+n-1 (12 columns, 0.5" margins)."""
    return MARGIN + c0 * (COLW + GUTTER), n * COLW + (n - 1) * GUTTER


# ---------------------------------------------------------------- primitives
def _clear(slide):
    for sh in list(slide.shapes):
        sh._element.getparent().remove(sh._element)


def _rect(slide, x, y, w, h, fill, radius=0.0, name=None, line=None):
    kind = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    sp = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    if radius:
        sp.adjustments[0] = min(0.5, radius / min(w, h))
    if fill:
        sp.fill.solid(); sp.fill.fore_color.rgb = _rgb(fill)
    else:
        sp.fill.background()
    if line:
        sp.line.color.rgb = _rgb(line); sp.line.width = Pt(1.0)
    else:
        sp.line.fill.background()
    sp.shadow.inherit = False
    if name:
        sp.name = name
    return sp


def _text(slide, x, y, w, h, paras, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
          name=None, autoshape=False, wrap=True, radius=0.0):
    """A text frame. `paras` is a list of (text, pt, font, color_hex, bold).

    `autoshape=True` draws the text in a no-fill rectangle (rounded when `radius` is
    given): build/restyle_fonts assigns Montserrat to every autoshape with text, so a
    kicker or chip keeps its face.
    """
    if autoshape:
        box = _rect(slide, x, y, w, h, None, radius=radius, name=name)
    else:
        box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        if name:
            box.name = name
    tf = box.text_frame
    tf.word_wrap = wrap
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    for i, (txt, pt, font, color, bold) in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run()
        r.text = txt
        r.font.name = font
        r.font.size = Pt(max(MIN_PT, pt))
        r.font.bold = bold
        r.font.color.rgb = _rgb(color)
    return box


def _lockup(slide, x, y, w):
    """The CSI | Velocity lockup on a white card (the lockup is dark-on-transparent)."""
    h = w * 158 / 498
    _rect(slide, x - 0.1, y - 0.08, w + 0.2, h + 0.16, brand.WHITE, radius=0.08)
    if os.path.exists(LOCKUP_PNG):
        slide.shapes.add_picture(LOCKUP_PNG, Inches(x), Inches(y), width=Inches(w))


def _width(text, pt, bold=True):
    if text_width_in is None:
        return len(text) * pt / 72 * 0.62
    return text_width_in(text, pt, "Montserrat", bold) * 1.04     # ExtraBold runs a little wider


def slide_title(slide):
    """First line of the first text shape — the convention every by-title lookup uses."""
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            return sh.text_frame.text.strip().splitlines()[0]
    return ""


def _notes(slide, text):
    if text:
        slide.notes_slide.notes_text_frame.text = text


# ---------------------------------------------------------------- client logo
def client_logo_for(client_id, out_dir):
    """The client's trimmed logo as a path, or None. Never raises: a missing or
    unreadable logo degrades to a cover without one (rpe_env.client_logo's contract)."""
    if not out_dir:
        return None
    try:
        import rpe_env
        src = rpe_env.client_logo(client_id)
        if not src:
            return None
        os.makedirs(str(out_dir), exist_ok=True)
        return str(rpe_env.trim_logo(src, out_dir))
    except Exception:
        return None


# ---------------------------------------------------------------- cover
def _chips(slide, products, y=CHIP_Y):
    """Outline chips, one per product, wrapping to a second row when four will not fit."""
    x, row_y = MARGIN, y
    for name in products:
        w = _width(name, MIN_PT) + CHIP_PAD
        if x > MARGIN and x + w > SLIDE_W - MARGIN:
            x, row_y = MARGIN, row_y + CHIP_H + 0.12
        chip = _text(slide, x, row_y, w, CHIP_H, [(name, MIN_PT, KICK, brand.WHITE, True)],
                     align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, name=TAG_COVER_CHIP,
                     autoshape=True, radius=CHIP_H / 2)
        chip.line.color.rgb = _rgb(brand.LABEL); chip.line.width = Pt(1.0)
        x += w + CHIP_GAP


def draw_cover(slide, products, client, month, client_logo=None, note=None):
    """Redraw `slide` as the cover. `products` are full product names, in section order;
    `month` is the reporting month ("September 2026"), which appears once at 84 pt and
    once in the "Executive Review  •  <month>" line the validator and combiner read."""
    _clear(slide)
    _rect(slide, 0, 0, SLIDE_W, SLIDE_H, brand.NAVY, name=TAG_COVER)
    # chips first: the first text shape is the slide's title, and the shell's cover led
    # with the product name too
    _chips(slide, list(products))
    _text(slide, MARGIN, 2.5, SLIDE_W - 2 * MARGIN, 1.5, [(month, 84, HERO, brand.WHITE, False)],
          anchor=MSO_ANCHOR.BOTTOM, wrap=False)
    _text(slide, MARGIN, 4.15, SLIDE_W - 2 * MARGIN, 1.1,
          [(client, 32, HEAD, brand.ORANGE, False),
           (f"Executive Review  •  {month}", 18, KICK, brand.LABEL, False)])
    if client_logo and os.path.exists(client_logo):
        try:
            import rpe_env
            fit = rpe_env.fit_box(client_logo, 2.5, 0.7)
        except Exception:
            fit = None
        if fit:
            lw, lh = fit
            _rect(slide, MARGIN, 0.5, 2.9, 1.0, brand.WHITE, radius=0.1)
            slide.shapes.add_picture(client_logo, Inches(MARGIN + (2.9 - lw) / 2),
                                     Inches(0.5 + (1.0 - lh) / 2), width=Inches(lw))
    _lockup(slide, SLIDE_W - MARGIN - 1.6, 6.45, 1.6)
    _notes(slide, note)
    return slide


def is_new_cover(slide):
    return any(sh.name in (TAG_COVER, TAG_COVER_CHIP) for sh in slide.shapes)


def set_cover_products(slide, products):
    """Replace the cover's chips with exactly these products (the combiner's job)."""
    if not is_new_cover(slide):
        return False
    for sh in list(slide.shapes):
        if sh.name == TAG_COVER_CHIP:
            sh._element.getparent().remove(sh._element)
    # keep the chips the FIRST text shapes: insert them right after the background
    before = list(slide.shapes._spTree)
    _chips(slide, list(products))
    added = [el for el in slide.shapes._spTree if el not in before]
    bg = next((sh._element for sh in slide.shapes if sh.name == TAG_COVER), None)
    if bg is not None:
        tree = slide.shapes._spTree
        pos = list(tree).index(bg) + 1
        for el in added:
            tree.remove(el)
            tree.insert(pos, el)
            pos += 1
    return True


# ---------------------------------------------------------------- divider
def _title_pt(title, max_w=SLIDE_W - 2 * MARGIN - 0.2):
    pt = 52
    while pt > 36 and _width(title, pt) > max_w:
        pt -= 4
    return pt


def draw_divider(slide, title, benefits, stats=(), programs=None, current=None, note=None):
    """Redraw `slide` as a section divider.

    `stats` is up to three (value, label) pairs — the section's headline figures, as
    already-formatted strings. `programs` is the deck's product list (full names, in
    order) and `current` the one this divider opens; both are None in a standalone deck,
    where a one-item track would say nothing.
    """
    _clear(slide)
    _rect(slide, 0, 0, SLIDE_W, SLIDE_H, brand.NAVY, name=TAG_DIVIDER)
    # title FIRST (it is the slide's title for every lookup), then the furniture
    _text(slide, MARGIN, 1.15, SLIDE_W - 2 * MARGIN, 1.0, [(title, _title_pt(title), HERO, brand.WHITE, False)],
          anchor=MSO_ANCHOR.BOTTOM, wrap=False)
    # No "SECTION" kicker (Aaron, 2026-10-02): the slide IS the section, full-bleed navy
    # with the name at 52 pt, so a label above it saying so is a word spent on nothing.
    if benefits:
        # an autoshape so a later restyle_fonts pass (the ARS builder runs one after the
        # branding pass) keeps it in Montserrat rather than re-fonting an 18 pt line as body
        _text(slide, MARGIN, 2.3, SLIDE_W - 2 * MARGIN, 0.5, [(benefits, 18, HEAD, brand.ORANGE, False)],
              anchor=MSO_ANCHOR.MIDDLE, autoshape=True)
    for i, (value, label) in enumerate(list(stats)[:3]):
        x, w = span(i * 4, 4)
        _text(slide, x, 3.7, w, 0.9, [(str(value), 40, HERO, brand.WHITE, False)], anchor=MSO_ANCHOR.BOTTOM, wrap=False)
        _text(slide, x, 4.65, w, 0.45, [(str(label), MIN_PT, BODY, brand.LABEL, False)])
    _lockup(slide, SLIDE_W - MARGIN - 1.1, 0.42, 1.1)
    if programs and current:
        set_divider_track(slide, programs, current)
    _notes(slide, note)
    return slide


def is_new_divider(slide):
    return any(sh.name == TAG_DIVIDER for sh in slide.shapes)


def set_divider_track(slide, programs, current):
    """Draw (or redraw) the progress track: every program in the deck, the current one in
    orange. Removed outright when the deck holds one program."""
    for sh in list(slide.shapes):
        if sh.name == TAG_TRACK:
            sh._element.getparent().remove(sh._element)
    programs = list(programs)
    if len(programs) < 2 or current not in programs:
        return False
    x0, w = MARGIN, SLIDE_W - 2 * MARGIN
    seg = w / len(programs)
    _rect(slide, x0, TRACK_Y + 0.42, w, 0.02, brand.SLATE, name=TAG_TRACK)
    for i, p in enumerate(programs):
        on = p == current
        _text(slide, x0 + i * seg, TRACK_Y, seg - 0.1, 0.36,
              [(TRACK_LABEL.get(p, p).upper(), MIN_PT, KICK, brand.ORANGE if on else brand.STEEL_SOFT, True)],
              anchor=MSO_ANCHOR.MIDDLE, name=TAG_TRACK, autoshape=True)
        if on:
            _rect(slide, x0 + i * seg, TRACK_Y + 0.40, seg - 0.1, 0.05, brand.ORANGE, name=TAG_TRACK)
    return True


# ---------------------------------------------------------------- recognising the shell's own
def _is_fullbleed(slide):
    return any(sh.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE and sh.width is not None
               and Emu(sh.width).inches > 12.5 and Emu(sh.height).inches > 6.5 for sh in slide.shapes)


def _max_pt(slide):
    return max([r.font.size.pt for sh in slide.shapes if sh.has_text_frame
                for p in sh.text_frame.paragraphs for r in p.runs if r.font.size] + [0])


def is_divider(slide):
    """A shell divider (full-bleed, 44 pt+ title) that is neither the cover nor the
    Questions closer — the slides the ARS builder redraws in place."""
    if not _is_fullbleed(slide) or _max_pt(slide) < 44:
        return False
    text = " ".join(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame).lower()
    if "executive review" in text:
        return False
    return not slide_title(slide).startswith("Questions")


def redraw_divider_in_place(slide, stats=(), programs=None, current=None):
    """Redraw a shell divider keeping its own title and second line (which the builder
    may already have swapped — the ARS New Account Profile divider carries a period)."""
    texts = [sh.text_frame.text.strip() for sh in slide.shapes
             if sh.has_text_frame and sh.text_frame.text.strip()
             and sh.text_frame.text.strip() != "SECTION"]      # our own kicker, when redrawn twice
    title = texts[0].splitlines()[0] if texts else ""
    benefits = texts[1].splitlines()[0] if len(texts) > 1 else ""
    return draw_divider(slide, title, benefits, stats=stats, programs=programs, current=current)
