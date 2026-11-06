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
import os
from PIL import Image

from pptx.util import Emu, Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE
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
            font=HEAD, anchor=MSO_ANCHOR.MIDDLE, name=None):
    """A word-wrapped text box. `lines` is a string or a list of paragraphs."""
    box = slide.shapes.add_textbox(Inches(L), Inches(T), Inches(W), Inches(H))
    if name:
        box.name = name
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


def widen_pill_to_text(sh, min_left=8.0, slack=0.05):
    """Widen the upper-right period pill leftward, right edge fixed, until its one line of text fits.

    The template's pill is 2.35 in wide, sized for "PTD · June 2026". The data month is swapped in
    afterwards, and "September" is the longest month name: "PTD · September 2026" needs 2.50 in of
    Montserrat 16 pt inside the 2.15 in the box holds, so it wrapped onto the title (2026.10, every
    ARS deck: the validation gate rejected 1075, 1204 and 1537). Width is measured with textfit, as
    the validator measures it. -> True when the pill was widened. A pill that would have to grow
    past `min_left` is left alone so the validator still reports it.
    """
    from textfit import text_width_in
    if not sh.has_text_frame or sh.left is None or sh.top is None or sh.width is None:
        return False
    if Emu(sh.top).inches >= 1.0 or Emu(sh.left).inches < 9.0 or Emu(sh.height).inches > 0.7:
        return False
    paras = [p for p in sh.text_frame.paragraphs if p.runs]
    if len(paras) != 1:
        return False
    runs = paras[0].runs
    text = "".join(r.text for r in runs).strip()
    pt = next((r.font.size.pt for r in runs if r.font.size), None)
    fam = next((r.font.name for r in runs if r.font.name), None)
    if not text or "\n" in text or not pt or not fam:
        return False
    tf = sh.text_frame
    margins = (Emu(tf.margin_left).inches or 0) + (Emu(tf.margin_right).inches or 0)
    need = text_width_in(text, pt, fam, bool(runs[0].font.bold)) + margins + slack
    if need <= Emu(sh.width).inches:
        return False
    right = Emu(sh.left + sh.width).inches
    if right - need < min_left:
        return False
    sh.left, sh.width = Inches(right - need), Inches(need)
    return True


# The label's shape name: restyle_fonts reads it and leaves that run at its own size instead of raising it
# to the 16 pt floor. Keep the string identical to restyle_fonts.SMALL_TILE_LABEL (tests pin it).
SMALL_TILE_LABEL = "KPI label (small)"


def drop_kpi_tile(slide, label, gap=0.27, left=0.56, right=12.77):
    """Remove the KPI tile whose label reads `label` and spread the remaining tiles evenly.

    A tile is an empty rounded rectangle with its value and label text boxes over it. Used when a
    figure has no denominator (Austin Bank has no ARS-eligible business accounts, so the Historical
    Take Rate on the Business slide was 0 / 0 and printed as 0.0%): the tile is hidden rather than
    showing a rate that is not a rate. -> True when a tile was removed.
    """
    def inches(v):
        return Emu(v).inches
    tiles = [sh for sh in slide.shapes
             if sh.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE and sh.has_text_frame
             and not sh.text_frame.text.strip() and inches(sh.height) < 1.6 and inches(sh.top) < 2.0]
    if not tiles:
        return False
    texts = [sh for sh in slide.shapes
             if sh.shape_type == MSO_SHAPE_TYPE.TEXT_BOX and sh.has_text_frame and sh.text_frame.text.strip()]

    def parts(tile):
        l, r = inches(tile.left), inches(tile.left + tile.width)
        t, b = inches(tile.top), inches(tile.top + tile.height)
        return [x for x in texts if l <= inches(x.left) + inches(x.width) / 2 <= r
                and t <= inches(x.top) + inches(x.height) / 2 <= b]
    doomed = next((tl for tl in tiles if any(x.text_frame.text.strip() == label for x in parts(tl))), None)
    if doomed is None:
        return False
    keep = sorted((tl for tl in tiles if tl is not doomed), key=lambda s: s.left)
    layout = [(tl, parts(tl)) for tl in keep]
    for x in parts(doomed) + [doomed]:
        x._element.getparent().remove(x._element)
    n = len(layout)
    if n:
        w = (right - left - gap * (n - 1)) / n
        for i, (tl, kids) in enumerate(layout):
            L = left + i * (w + gap)
            tl.left, tl.width = Inches(L), Inches(w)
            for x in kids:
                x.left, x.width = Inches(L + 0.05), Inches(w - 0.1)
    return True


def tile(slide, L, T, W, H, value, label, fill=NAVY, small_label=False):
    """A KPI tile: big value over a small label, on a rounded fill.

    `small_label` keeps the 12 pt label at 12 pt through restyle_fonts (Product Mix and Excluded Accounts,
    whose callout subtext has to match); every other tile's label is floored to 16 pt as before.
    """
    sp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                Inches(L), Inches(T), Inches(W), Inches(H))
    sp.fill.solid(); sp.fill.fore_color.rgb = fill; sp.line.fill.background()
    sp.shadow.inherit = False
    textbox(slide, L + 0.05, T + 0.14, W - 0.1, H * 0.5, value, 28, WHITE, True,
            PP_ALIGN.CENTER, HEAD, MSO_ANCHOR.MIDDLE)
    textbox(slide, L + 0.05, T + H * 0.60, W - 0.1, H * 0.34, label, 12, GREYB,
            False, PP_ALIGN.CENTER, BODY, MSO_ANCHOR.TOP, name=SMALL_TILE_LABEL if small_label else None)
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


# The Contact Us slide (STYLE.md §5): the Questions & Discussion slide's own full-bleed gradient with the white
# CSI logo, "Contact Us" under it and the contact details centred beneath, no card (Aaron, 2026-11-02: he chose
# this over a compact card and a wide card, after "too much space between the lines on the contact card").
# One contact in the middle, or two columns when the deck also carries a program contact (ICS). The geometry
# lives here so the shell's slide and the slides the ICS, MRPC and ARS builders draw cannot drift apart.
CONTACT_TITLE = "Contact Us"
CONTACT_FILL = "closing_fill.xml"        # the closing slide's gradient: build/assets/csi_brand/, nowhere else
CONTACT_LOGO_W, CONTACT_LOGO_TOP = 3.6, 0.75
CONTACT_TITLE_TOP, CONTACT_TITLE_PT = 2.55, 44
CONTACT_COL_W, CONTACT_COL_GAP = 5.2, 0.6
CONTACT_TOPS = {"name": 3.75, "role": 4.35, "phone": 5.0, "email": 5.42}     # the phone and email sit together
CONTACT_PT = {"name": 30, "role": 18, "phone": 20, "email": 18}              # the role is bold orange: large text
CONTACT_ICON_W, CONTACT_ICON_GAP = 0.22, 0.14
CONTACT_TAG_FILL, CONTACT_TAG_ICON = "Contact slide fill", "Contact icon"


def contact_card_note(contact):
    """The Contact Us slide's source line."""
    return f"Source: CSM Contacts.csv (managing CSM {contact['name']})."


def find_contact_slide(prs):
    """The deck's Contact Us slide, by TITLE, or None."""
    for s in prs.slides:
        if any(sh.has_text_frame and sh.text_frame.text.strip() == CONTACT_TITLE for sh in s.shapes):
            return s
    return None


def _contact_icon(slide, kind, cx, cy):
    """A small white line icon centred on (cx, cy) inches, drawn from plain shapes so it never needs a
    picture or a font: a phone (rounded outline with a home bar) or an envelope (outline and its flap)."""
    from pptx.enum.shapes import MSO_CONNECTOR

    def stroke(sh):
        sh.fill.background()
        sh.line.color.rgb = WHITE
        sh.line.width = Pt(1.5)
        sh.shadow.inherit = False
        sh.name = CONTACT_TAG_ICON
        return sh

    def line(x1, y1, x2, y2):
        c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
        c.line.color.rgb = WHITE
        c.line.width = Pt(1.5)
        c.name = CONTACT_TAG_ICON
        return c
    if kind == "phone":
        w, h = 0.15, 0.26
        body = stroke(slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(cx - w / 2), Inches(cy - h / 2),
                                             Inches(w), Inches(h)))
        body.adjustments[0] = 0.22
        line(cx - 0.03, cy + h / 2 - 0.05, cx + 0.03, cy + h / 2 - 0.05)
    else:
        w, h = 0.27, 0.19
        stroke(slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(cx - w / 2), Inches(cy - h / 2), Inches(w), Inches(h)))
        line(cx - w / 2, cy - h / 2, cx, cy + 0.01)
        line(cx, cy + 0.01, cx + w / 2, cy - h / 2)


def _clear_slide(slide):
    """Remove every shape and placeholder: the slide is redrawn whole."""
    for sh in list(slide.shapes):
        sh._element.getparent().remove(sh._element)


def draw_contact_slide(slide, contacts):
    """Redraw `slide` as the Contact Us slide for `contacts`; -> the slide.

    `contacts` are `rpe_env.csm_contact(...)` dicts (name, role, phone, email): the managing CSM first, then the
    program contact when the deck carries one (ICS). One or two fit. Whatever the slide held is removed first: the
    title, the gradient, the logo and the lines are all drawn here, so a shell's slide and a builder's own slide
    come out the same. Like the closing slide it carries no slide number and no data logo. A contact with no phone
    on file gets no phone row — not a blank, not a dash — and the email moves up into its place. Text is white,
    the role bold orange (large text: about 3.1:1 against the gradient at the second column, 3.6:1 or better at
    the first). Nothing is hardcoded: the lines are whatever the dicts hold.
    """
    import brand_art
    from textfit import fits_one_line, text_width_in
    contacts = list(contacts)
    if not 1 <= len(contacts) <= 2:
        raise SystemExit(f"Contact Us slide: one or two contacts fit, got {len(contacts)}.")
    _clear_slide(slide)
    brand_art.gradient_rect(slide, 0, 0, 13.333, 7.5, CONTACT_FILL, name=CONTACT_TAG_FILL)
    # the title FIRST among the text shapes: it is the slide's title for every lookup
    textbox(slide, 0.5, CONTACT_TITLE_TOP, 12.33, 0.9, CONTACT_TITLE, CONTACT_TITLE_PT, WHITE, True, font=HEAD,
            name="Contact title")
    brand_art.add_logo(slide, "white", (13.333 - CONTACT_LOGO_W) / 2, CONTACT_LOGO_TOP, CONTACT_LOGO_W)
    n, colw = len(contacts), CONTACT_COL_W
    x0 = (13.333 - (n * colw + (n - 1) * CONTACT_COL_GAP)) / 2
    for i, c in enumerate(contacts):
        x = x0 + i * (colw + CONTACT_COL_GAP)
        name_pt = CONTACT_PT["name"] if fits_one_line(c["name"], colw - 0.2, CONTACT_PT["name"], HEAD, True) else 22
        textbox(slide, x, CONTACT_TOPS["name"], colw, 0.6, c["name"], name_pt, WHITE, True, font=HEAD, name="Contact name")
        textbox(slide, x, CONTACT_TOPS["role"], colw, 0.4, c["role"], CONTACT_PT["role"], ORANGE, True, font=BODY,
                name="Contact role")
        y = CONTACT_TOPS["phone"]
        for field, kind in (("phone", "phone"), ("email", "mail")):
            if not c.get(field):
                continue
            pt = CONTACT_PT[field]
            tw = text_width_in(c[field], pt, BODY)
            # The TEXT is centred under the name (Aaron, 2026-11-06); the icon hangs off its left edge, so the
            # words, not the icon-and-words group, share the name's centre line.
            cx = x + colw / 2
            _contact_icon(slide, kind, cx - tw / 2 - CONTACT_ICON_GAP - CONTACT_ICON_W / 2, y + 0.2)
            box = textbox(slide, cx - (tw + 0.2) / 2, y, tw + 0.2, 0.4, c[field], pt, WHITE,
                          False, align=PP_ALIGN.CENTER, font=BODY, name="Contact " + field)
            box.text_frame.word_wrap = False      # an address is one line, whatever the renderer's metrics say
            y += CONTACT_TOPS["email"] - CONTACT_TOPS["phone"]
    return slide


def fill_contact_slide(slide, contact):
    """Redraw a SHELL's Contact Us slide with `contact` (rpe_env.csm_contact) and set its source note.

    The ARS, MRPC and CashPlease shells each carry a Contact Us slide whose card holds static text for one CSM,
    and that text shipped on every deck built from them; the slide is now drawn whole by `draw_contact_slide`,
    nothing of the shell's card kept.
    """
    draw_contact_slide(slide, [contact])
    slide.notes_slide.notes_text_frame.text = contact_card_note(contact)
    return slide


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


# ----------------------------------------------------------------- data-slide logo
DATA_LOGO_BOX = (11.28, 6.78, 1.70, 0.54)      # STYLE.md: bottom-right of every data slide


_LOGO_CACHE = {}


def data_logo(slide, client_id=None, assets_dir=None, lockup=None, box=DATA_LOGO_BOX):
    """The bottom-right mark on a data slide: the CLIENT's logo, else the lockup.

    The client's logo (Aaron, 2026-10-02). FITTED inside the box and centred in it, never
    stamped at the box's own size: client logos run 1.50 to 8.77 wide-to-tall and most
    would be stretched by a fixed 1.70 x 0.54. Cropped to the ink first, because the files
    carry white or transparent padding and fitting the raw canvas renders a right-sized box
    holding a tiny mark (rpe_env.trim_logo).

    `lockup` is the fallback for a client with no logo on file — a path or the image bytes.
    A missing logo is never an error: the slide is built without one.
    """
    import rpe_env as _R
    l, t, w, h = box
    path = None
    if client_id:
        key = (str(client_id), str(assets_dir))
        path = _LOGO_CACHE.get(key)
        if path is not None and not os.path.isfile(path):
            path = None
        if path is None:
            try:
                path = _R.client_logo(client_id)
                if path is not None and assets_dir:
                    path = _R.trim_logo(path, assets_dir)
                if path is not None:
                    _LOGO_CACHE[key] = path     # one build, one client: 40 slides were each re-reading and
                                                # re-trimming the same logo from the share (25 s on 1100)
            except Exception as e:              # an unreadable logo must not fail a build
                print(f"!! data logo: {client_id} ({type(e).__name__}: {e}) — using the lockup")
                path = None
    if path is not None:
        fit = _R.fit_box(path, w, h)
        if fit:
            fw, fh = fit
            return slide.shapes.add_picture(str(path), Inches(l + (w - fw) / 2),
                                            Inches(t + (h - fh) / 2), Inches(fw), Inches(fh))
    if lockup is None:
        return None
    src = lockup if isinstance(lockup, (bytes, bytearray)) else str(lockup)
    if isinstance(src, str) and not os.path.exists(src):
        return None
    if isinstance(src, (bytes, bytearray)):
        import io as _io
        src = _io.BytesIO(src)
    return slide.shapes.add_picture(src, Inches(l), Inches(t), Inches(w), Inches(h))
