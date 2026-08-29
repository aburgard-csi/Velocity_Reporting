#!/usr/bin/env python3
"""
shapes.py — the deck's shape primitives, shared by every pipeline.

These eight helpers used to live in `ars_pipeline/product_mix_slide.py` — a
module about ONE SLIDE — and four other ARS modules imported them from there.
ICS and MRPC could not reasonably reach them, so they had no equivalents, which
is why their layout fixes kept arriving as one-off per-deck commits instead of
as changes to a contract (CLAUDE.md rule 2).

Nothing here is ARS-specific. Every function takes a slide and geometry in
inches and applies the STYLE.md contract: Montserrat for headings/callouts/
tiles/pills, Calibri for body and table cells, navy fills with white text,
alternating pale rows, the standard callout drop shadow.

Public names are unprefixed. The old underscore names are kept as aliases so the
existing `from product_mix_slide import _tb, _tile, ...` call sites keep working
during the migration.
"""
from PIL import Image

from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from pptx.oxml import parse_xml

from brand import (
    NAVY_RGB as NAVY, ORANGE_RGB as ORANGE, WHITE_RGB as WHITE,
    LABEL_RGB as GREYB, TICK_RGB as GREYT, ROWALT_RGB as ROWALT,
    HEAD, BODY,
)

# standard callout / pill drop shadow (STYLE.md)
_SHADOW_XML = ('<a:effectLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
               '<a:outerShdw blurRad="63500" dist="38100" dir="5400000" rotWithShape="0">'
               '<a:srgbClr val="000000"><a:alpha val="28000"/></a:srgbClr>'
               '</a:outerShdw></a:effectLst>')


def shadow(shape):
    spPr = shape._element.spPr
    for e in spPr.findall(qn('a:effectLst')):
        spPr.remove(e)
    spPr.append(parse_xml(_SHADOW_XML))


def textbox(slide, L, T, W, H, lines, size, color, bold, align=PP_ALIGN.CENTER,
            font=HEAD, anchor=MSO_ANCHOR.MIDDLE):
    """A word-wrapped text box. `lines` is a string or a list of paragraphs."""
    box = slide.shapes.add_textbox(Inches(L), Inches(T), Inches(W), Inches(H))
    tf = box.text_frame; tf.word_wrap = True; tf.vertical_anchor = anchor
    if isinstance(lines, str):
        lines = [lines]
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run(); r.text = ln
        r.font.size = Pt(size); r.font.bold = bold; r.font.name = font
        r.font.color.rgb = color
    return box


def pill(slide, t, L=10.5, T=0.34, W=2.35, H=0.5):
    """The upper-right period/date pill. Carries the standard drop shadow."""
    sp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                Inches(L), Inches(T), Inches(W), Inches(H))
    sp.fill.solid(); sp.fill.fore_color.rgb = ORANGE; sp.line.fill.background()
    tf = sp.text_frame; tf.word_wrap = True; p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = t
    r.font.size = Pt(12); r.font.bold = True; r.font.name = HEAD
    r.font.color.rgb = WHITE
    shadow(sp)
    return sp


def tile(slide, L, T, W, H, value, label, fill=NAVY):
    """A KPI tile: big value over a small label, on a rounded fill."""
    sp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                Inches(L), Inches(T), Inches(W), Inches(H))
    sp.fill.solid(); sp.fill.fore_color.rgb = fill; sp.line.fill.background()
    sp.shadow.inherit = False
    textbox(slide, L + 0.05, T + 0.14, W - 0.1, H * 0.5, value, 28, WHITE, True,
            PP_ALIGN.CENTER, HEAD, MSO_ANCHOR.MIDDLE)
    textbox(slide, L + 0.05, T + H * 0.60, W - 0.1, H * 0.34, label, 12, GREYB,
            False, PP_ALIGN.CENTER, BODY, MSO_ANCHOR.TOP)
    return sp


def add_table(slide, L, T, W, H, data, colw, highlight=(), header=True, fs=10):
    """Navy header, alternating pale rows, orange highlight rows."""
    rows = len(data); cols = len(data[0])
    gf = slide.shapes.add_table(rows, cols, Inches(L), Inches(T), Inches(W), Inches(H))
    tb = gf.table; tb.first_row = False; tb.horz_banding = False
    tot = sum(colw)
    for j, wd in enumerate(colw):
        tb.columns[j].width = Inches(W * wd / tot)
    for i, row in enumerate(data):
        tb.rows[i].height = Inches(H / rows)
        for j, val in enumerate(row):
            c = tb.cell(i, j)
            c.margin_top = Pt(2); c.margin_bottom = Pt(2)
            c.margin_left = Pt(5); c.margin_right = Pt(4)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = c.text_frame; tf.word_wrap = True; p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER
            r = p.add_run(); r.text = str(val); r.font.name = BODY; r.font.size = Pt(fs)
            if header and i == 0:
                c.fill.solid(); c.fill.fore_color.rgb = NAVY
                r.font.color.rgb = WHITE; r.font.bold = True
            elif i in highlight:
                c.fill.solid(); c.fill.fore_color.rgb = ORANGE
                r.font.color.rgb = WHITE; r.font.bold = True
            else:
                c.fill.solid(); c.fill.fore_color.rgb = (WHITE if i % 2 else ROWALT)
                r.font.color.rgb = NAVY
    return gf


def fit_picture(slide, path, L, T, maxW, maxH):
    """Place an image scaled to fit inside (maxW x maxH), centred horizontally.

    A chart added by width alone runs off the slide when the saved aspect is
    taller than assumed, so the box is enforced from the file's real pixel
    dimensions. Returns the bottom edge in inches, for placing a caption under it.
    """
    with Image.open(path) as im:
        pw, ph = im.size
    scale = min(maxW / pw, maxH / ph)
    w, h = pw * scale, ph * scale
    slide.shapes.add_picture(path, Inches(L + (maxW - w) / 2), Inches(T),
                             Inches(w), Inches(h))
    return T + h


# ----------------------------------------------------------------- slide plumbing
def blank_slide(prs, template_slide):
    """Add a slide on template_slide's layout, stripped of all shapes."""
    s = prs.slides.add_slide(template_slide.slide_layout)
    for sh in list(s.shapes):
        sh._element.getparent().remove(sh._element)
    return s


def slide_title(slide):
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip():
            return sh.text_frame.text.strip()
    return ""


def sldid_of(prs, slide):
    for el in prs.slides._sldIdLst:
        rId = el.get(qn("r:id"))
        if prs.part.related_part(rId) is slide.part:
            return el
    return None


def move_before(prs, slide, before_title):
    lst = prs.slides._sldIdLst
    target = None
    for s in prs.slides:
        if slide_title(s).startswith(before_title) and s is not slide:
            target = s; break
    if target is None:
        return False
    src = sldid_of(prs, slide)
    tgt = sldid_of(prs, target)
    if src is None or tgt is None:
        return False
    lst.remove(src)
    tgt.addprevious(src)
    return True


def renumber(prs):
    """Final page-number pass (mirrors build.py)."""
    for n, s in enumerate(prs.slides, 1):
        found = None
        for sh in s.shapes:
            if (sh.has_text_frame and sh.top is not None and sh.top > Inches(6.8)
                    and sh.left is not None and sh.left < Inches(1.2)):
                txt = sh.text_frame.text.strip()
                if txt.isdigit() or txt in ("‹#›", ""):
                    found = sh; break
        if found and found.text_frame.paragraphs[0].runs:
            found.text_frame.paragraphs[0].runs[0].text = str(n)
        elif n > 1 and found is None:
            textbox(s, 0.45, 7.04, 0.7, 0.32, str(n), 11, NAVY, True,
                    PP_ALIGN.LEFT, BODY, MSO_ANCHOR.MIDDLE)


# Aliases for the pre-promotion call sites.
_shadow = shadow
_tb = textbox
_pill = pill
_tile = tile
_add_table = add_table
_blank_slide = blank_slide
_slide_title = slide_title
_sldid_of = sldid_of
_move_before = move_before
_renumber = renumber
