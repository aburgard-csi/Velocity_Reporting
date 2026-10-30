"""Key Performance Metrics page: one 8.5 x 11 Executive Summit sheet per attendee, on the 2026 CSI brand template.

usage: python kpm_page.py <spec.json> <out.pptx>

The spec is plain JSON (see SKILL.md, "Spec"): name, id, an optional band of four tiles and a chart picture, and sections of
bullets, with the page notes naming every source. The template's "Designed Header with Content" layout is rescaled to portrait;
theme fonts and colours are inherited from assets/brand.pptx.

Layout switches a spec may carry: "measure" (count wrapped lines with the bundled Montserrat), "accurate" (use the rendered line
pitch, so the gaps between sections come out equal), "bottom" (inches: where content must end) and "min_gap".
"""
import io
import json
import math
import os
import sys

from PIL import Image, ImageChops
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from lxml import etree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir, os.pardir))
BRAND = os.path.join(HERE, "assets", "brand.pptx")
NAVY = RGBColor(0x00, 0x27, 0x4C)
BLUE = RGBColor(0x03, 0x5B, 0x95)
ORANGE = RGBColor(0xF1, 0x5D, 0x22)
GREY = RGBColor(0xEF, 0xEF, 0xEF)
WHITE = RGBColor(255, 255, 255)
LEFT, WIDTH = 0.5, 7.5
TOP, BOTTOM = 2.15, 9.62


def run(p, text, size, bold=False, color=NAVY):
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.color.rgb = color
    return r


def lines_needed(text, size, width_in):
    cpl = width_in * 72 / (size * 0.63)
    return max(1, math.ceil(len(text) / cpl))


sys.path.insert(0, os.path.join(REPO, "build"))
import textfit  # measures with the bundled Montserrat, so a line count is real, not guessed


def measured_lines(text, size, width_in):
    """Greedy word wrap at the measured width of the bundled Montserrat."""
    lines, cur = 1, ""
    for w in text.split():
        cand = (cur + " " + w).strip()
        if cur and textfit.text_width_in(cand, size, "Montserrat", False) > width_in * 0.97:
            lines += 1
            cur = w
        else:
            cur = cand
    return lines


def set_box(shape, l, t, w, h):
    shape.left, shape.top, shape.width, shape.height = Inches(l), Inches(t), Inches(w), Inches(h)


def find_logo(spec):
    """spec["logo"], else <RPE_DATA_ROOT>/Inputs/Logos/<id>.png|jpg (resolved through rpe_env, never hardcoded), else None."""
    if spec.get("logo") and os.path.exists(spec["logo"]):
        return spec["logo"]
    try:
        import rpe_env
        folder = rpe_env.inputs() / "Logos"
    except (SystemExit, Exception):
        return None
    for ext in ("png", "jpg"):
        cand = folder / ("%s.%s" % (spec["id"], ext))
        if cand.exists():
            return str(cand)
    return None


def contact_line(spec):
    """The client's managing CSM, from CSM Contacts.csv through rpe_env (never another CSM's card): spec["contact"] overrides it."""
    if spec.get("contact"):
        return spec["contact"]
    import rpe_env
    c = rpe_env.csm_contact(spec["id"])   # stops with a plain sentence if the client has no CSM or the CSM has no row
    return "For more information, contact your Client Service Manager, %s, %s" % (c["name"], c["email"])


def build(spec, out):
    prs = Presentation(BRAND)
    prs.slide_width, prs.slide_height = Inches(8.5), Inches(11)
    # drop the template's sample slides (keep the package: theme, master, layouts)
    sldIdLst = prs.slides._sldIdLst
    for sldId in list(sldIdLst):
        prs.part.drop_rel(sldId.rId)
        sldIdLst.remove(sldId)
    lay = [l for l in prs.slide_layouts if l.name == "Designed Header with Content"][0]
    for sh in list(lay.shapes):  # footer logo / Confidential / page number are replaced below
        if sh.name in ("Picture 25", "TextBox 1", "TextBox 2"):
            sh._element.getparent().remove(sh._element)
    for sh in lay.shapes:  # rescale this layout to portrait
        n = sh.name
        if n == "Freeform 33":
            set_box(sh, 0, -0.03, 8.5, 2.0)
        elif n == "Freeform 32":
            set_box(sh, 6.47, 0.03, 2.03, 1.06)
        elif n == "Picture 25":
            set_box(sh, 0.5, 10.28, 0.9, 0.52)
        elif n == "TextBox 1":
            set_box(sh, 5.9, 10.5, 1.3, 0.25)
        elif n == "TextBox 2":
            set_box(sh, 7.5, 10.5, 0.5, 0.25)
        elif sh.is_placeholder and "Title" in n:
            set_box(sh, 0.5, 0.35, 5.6, 1.3)
        elif sh.is_placeholder:
            set_box(sh, 0.5, 2.2, 7.5, 7.0)
    s = prs.slides.add_slide(lay)
    for ph in list(s.placeholders):
        if ph.placeholder_format.type is not None and "TITLE" not in str(ph.placeholder_format.type):
            ph._element.getparent().remove(ph._element)
    title = s.shapes.title
    set_box(title, 0.5, 0.35, 5.6, 1.3)
    tf = title.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.text = ""
    p = tf.paragraphs[0]
    run(p, spec["name"], 30 if len(spec["name"]) < 14 else 26, True, WHITE)
    p2 = tf.add_paragraph()
    run(p2, "Key Performance Metrics", 11, True, WHITE)
    p3 = tf.add_paragraph()
    run(p3, "Fort Lauderdale Executive Summit", 9, False, WHITE)

    # client logo on a white badge, top right
    logo_path = find_logo(spec)
    im = None
    if logo_path:
        im = Image.open(logo_path).convert("RGBA")
        flat = Image.alpha_composite(Image.new("RGBA", im.size, (255, 255, 255, 255)), im).convert("RGB")
        box = ImageChops.difference(flat, Image.new("RGB", im.size, (255, 255, 255))).point(lambda v: 255 if v > 12 else 0).getbbox()
        if box:
            im = im.crop(box)
    badge = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(5.85), Inches(0.42), Inches(2.15), Inches(0.95))
    badge.fill.solid(); badge.fill.fore_color.rgb = WHITE; badge.line.fill.background(); badge.shadow.inherit = False
    badge.adjustments[0] = 0.12
    badge.line.color.rgb = NAVY; badge.line.width = Pt(1.25)  # a thin border so the badge does not vanish on the white page
    if im is not None:
        buf = io.BytesIO(); im.save(buf, "PNG"); buf.seek(0)
        bw, bh = 1.85, 0.7
        w, h = im.size
        k = min(bw / w, bh / h)
        s.shapes.add_picture(buf, Inches(5.85 + (2.15 - w * k) / 2), Inches(0.42 + (0.95 - h * k) / 2), Inches(w * k), Inches(h * k))
    else:
        print("WARNING: no logo found for %s; the badge is empty" % spec.get("id"))

    secs = spec["sections"]
    band = spec.get("band")
    BAND_CH = 1.55
    band_h = (0.5 + BAND_CH + 0.2) if band else 0.0

    def heading(y, title_, chip):
        tb = s.shapes.add_textbox(Inches(LEFT), Inches(y), Inches(5.2), Inches(0.38))
        t = tb.text_frame
        t.margin_left = t.margin_top = t.margin_bottom = 0
        t.vertical_anchor = MSO_ANCHOR.MIDDLE
        pp = t.paragraphs[0]
        if "|" in title_:
            a, m, c = title_.split("|")
            run(pp, a, 15, True, BLUE); run(pp, m, 15, True, BLUE); run(pp, c, 15, True, BLUE)
        else:
            run(pp, title_, 15, True, BLUE)
        if chip:
            ch = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(5.5), Inches(y + 0.04), Inches(2.5), Inches(0.3))
            ch.fill.solid(); ch.fill.fore_color.rgb = NAVY; ch.line.fill.background(); ch.shadow.inherit = False
            ch.adjustments[0] = 0.5
            ct = ch.text_frame
            ct.margin_left = ct.margin_right = Inches(0.04); ct.margin_top = ct.margin_bottom = 0
            ct.vertical_anchor = MSO_ANCHOR.MIDDLE
            cp = ct.paragraphs[0]; cp.alignment = PP_ALIGN.CENTER
            run(cp, chip, 9.5, True, WHITE)
        rule = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(LEFT), Inches(y + 0.4), Inches(WIDTH), Inches(0.02))
        rule.fill.solid(); rule.fill.fore_color.rgb = ORANGE; rule.line.fill.background(); rule.shadow.inherit = False

    if band:
        heading(TOP, band["title"], band.get("chip"))
        tiles = band["tiles"]
        tw, gp = 1.8, 0.12
        rows = math.ceil(len(tiles) / 2)
        th = (BAND_CH - gp * (rows - 1)) / rows
        for i, (val, lab) in enumerate(tiles):
            r_, c_ = divmod(i, 2)
            rect = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(LEFT + c_ * (tw + gp)), Inches(TOP + 0.52 + r_ * (th + gp)), Inches(tw), Inches(th))
            rect.fill.solid(); rect.fill.fore_color.rgb = ORANGE if i == 0 else GREY
            rect.line.fill.background(); rect.shadow.inherit = False
            t = rect.text_frame
            t.word_wrap = True
            t.margin_left = t.margin_right = Inches(0.05); t.margin_top = t.margin_bottom = Inches(0.02)
            t.vertical_anchor = MSO_ANCHOR.MIDDLE
            p1 = t.paragraphs[0]; p1.alignment = PP_ALIGN.CENTER
            run(p1, val, 15 if len(val) > 8 else 17, True, WHITE if i == 0 else NAVY)
            p2 = t.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
            run(p2, lab, 7.5, False, WHITE if i == 0 else NAVY)
        if band.get("chart"):
            cw = WIDTH - 2 * tw - gp - 0.15
            s.shapes.add_picture(band["chart"], Inches(LEFT + WIDTH - cw), Inches(TOP + 0.52), Inches(cw), Inches(BAND_CH))

    def chart_box(x):
        """(width, height) in inches of a section's own chart picture, or None. "chart_w" sets the width (default 3.4)."""
        if not x.get("chart"):
            return None
        cw = x.get("chart_w", 3.4)
        w, h = Image.open(x["chart"]).size
        return cw, cw * h / w

    def text_w(x):
        cb = chart_box(x)
        return WIDTH - (cb[0] + 0.15) if cb else WIDTH

    def sec_h(x, size):
        hh = 0.42
        for b in x["bullets"]:
            lh, pad = (1.12, 0.045) if spec.get("accurate") else (1.42, 0.07)  # rendered line pitch and 3pt space after, as seen
            hh += (measured_lines(b, size, text_w(x) - 0.25) if spec.get("measure") else lines_needed(b, size, text_w(x) - 0.3)) * size * lh / 72 + pad
        cb = chart_box(x)
        if cb:
            hh = max(hh, 0.42 + cb[1] + 0.06)
        return hh + 0.1

    avail = spec.get("bottom", BOTTOM) - TOP - band_h
    for size in (11.5, 11, 10.5, 10, 9.5):
        total = sum(sec_h(x, size) for x in secs)
        if total + 0.1 * len(secs) <= avail:
            break
    gap = max(spec.get("min_gap", 0.0), min(0.3, (avail - total) / max(1, len(secs))))
    y = TOP + band_h
    for x in secs:
        heading(y, x["title"], x.get("chip"))
        cb = chart_box(x)
        if cb:   # a chart beside this section's bullets, on the right
            s.shapes.add_picture(x["chart"], Inches(LEFT + WIDTH - cb[0]), Inches(y + 0.48), Inches(cb[0]), Inches(cb[1]))
        bb = s.shapes.add_textbox(Inches(LEFT), Inches(y + 0.48), Inches(text_w(x)), Inches(sec_h(x, size) - 0.42))
        t = bb.text_frame
        t.word_wrap = True
        t.margin_left = t.margin_right = t.margin_top = t.margin_bottom = 0
        for i, b in enumerate(x["bullets"]):
            pp = t.paragraphs[0] if i == 0 else t.add_paragraph()
            pPr = pp._p.get_or_add_pPr()
            pPr.set("marL", "228600"); pPr.set("indent", "-228600")
            bc = etree.SubElement(pPr, qn("a:buClr")); sc = etree.SubElement(bc, qn("a:srgbClr")); sc.set("val", "F15D22")
            bf = etree.SubElement(pPr, qn("a:buFont")); bf.set("typeface", "Arial")
            bu = etree.SubElement(pPr, qn("a:buChar")); bu.set("char", "•")
            pp.space_after = Pt(3)
            run(pp, b, size, False, NAVY)
        y += sec_h(x, size) + gap

    # CSI | Velocity lockup, bottom left
    s.shapes.add_picture(os.path.join(REPO, "build", "assets", "logo.png"), Inches(0.5), Inches(10.22), Inches(2.3), Inches(0.73))

    # contact line
    ct = s.shapes.add_textbox(Inches(LEFT), Inches(10.0), Inches(WIDTH), Inches(0.3))
    t = ct.text_frame
    t.word_wrap = True
    t.margin_left = t.margin_right = 0
    pp = t.paragraphs[0]
    pp.alignment = PP_ALIGN.CENTER
    run(pp, contact_line(spec), 9, True, BLUE)

    if len(spec.get("notes", "")) < 150:
        raise SystemExit("The page notes must name the file, tab and period behind every figure; they are missing or too short.")
    s.notes_slide.notes_text_frame.text = spec.get("notes", "")
    prs.save(out)
    return out


if __name__ == "__main__":
    print(build(json.load(open(sys.argv[1], encoding="utf-8")), sys.argv[2]))
