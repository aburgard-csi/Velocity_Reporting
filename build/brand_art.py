"""The CSI brand template's art, placed on a slide: the title band, the sunrise wedge, the gradient fills and the
two logos (Sept. 2026 template; lifted out of it by scripts/extract_brand_art.py into assets/csi_brand/).

Used by cover_divider.py to draw the cover, the dividers and the closing slide. Nothing here reads the .potx.
Import-safe: nothing runs at import, the assets are read when asked for.
"""
import copy
import os

from lxml import etree
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches

ART = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "csi_brand")
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
LOGO_DARK = os.path.join(ART, "csi_logo_dark.png")       # navy lettering, for the white title slide
LOGO_WHITE = os.path.join(ART, "csi_logo_white.png")     # white lettering, coloured mark: the closing slide
LOGO_MONO = os.path.join(ART, "csi_logo_mono.png")       # all white: the divider, over the orange wedge


def _xml(name):
    with open(os.path.join(ART, name), "rb") as fh:
        return etree.fromstring(fh.read())


def add_freeform(slide, filename, name=None):
    """A copy of one of the template's freeform shapes, with literal colours, on top of `slide`."""
    sp = _xml(filename)
    sp.find(".//{%s}cNvPr" % P).set("id", str(slide.shapes._next_shape_id))
    if name:
        sp.find(".//{%s}cNvPr" % P).set("name", name)
    slide.shapes._spTree.append(sp)
    return sp


def gradient_rect(slide, x, y, w, h, filename, name=None):
    """A rectangle (a plain auto shape, so the pipeline still reads it as the full-bleed background)
    filled with one of the template's gradients."""
    sp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sp.line.fill.background()
    sp.shadow.inherit = False
    sp.fill.background()
    spPr = sp._element.spPr
    old = spPr.find("{%s}noFill" % A)
    grad = _xml(filename)
    spPr.replace(old, copy.deepcopy(grad))
    if name:
        sp.name = name
    return sp


def add_logo(slide, which, x, y, w):
    """The CSI logo, `w` inches wide at (x, y). The picture has transparent padding, as in the template."""
    path = {"dark": LOGO_DARK, "white": LOGO_WHITE, "mono": LOGO_MONO}[which]
    return slide.shapes.add_picture(path, Inches(x), Inches(y), width=Inches(w))
