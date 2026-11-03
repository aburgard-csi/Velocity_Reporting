"""The Contact Us card carries the Questions & Discussion slide's gradient (Aaron, 2026-11-02).

"Add this gradient to the contact card." The closing slide is drawn from build/assets/csi_brand/closing_fill.xml
(the brand template's radial gradient, 00274C to 035B95); the card that follows it is filled from the same file by
`shapes.contact_card_fill`, so the stops live in one place. The shell's static card (`fill_contact_card`) and the
cards the ICS, MRPC and ARS builders draw themselves all go through it.

Every contact is synthetic.
"""
import os

import pytest
from lxml import etree
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from pptx.util import Inches

import shapes

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLOSING_FILL = os.path.join(REPO, "build", "assets", "csi_brand", "closing_fill.xml")
CONTACT = {"name": "Pat Cell", "role": "Client Service Manager", "phone": "555-010-0002", "email": "pat.cell@example.com"}


def _stops(grad):
    return sorted((int(gs.get("pos")), gs[0].get("val")) for gs in grad.iter(qn("a:gs")))


def _card(slide):
    return next(sh for sh in slide.shapes if sh.shape_type == 1 and sh.width > Inches(4) and sh.height > Inches(2.5))


def test_the_stops_are_the_closing_slides():
    grad = etree.parse(CLOSING_FILL).getroot()
    assert _stops(grad) == [(37000, "00274C"), (100000, "035B95")]          # navy to CSI light blue
    assert grad.find(qn("a:path")).get("path") == "circle"                  # radial, focus at the top-left


@pytest.mark.parametrize("template", ["ars_template.pptx", "mrpc_template.pptx", "cashplease_template.pptx"])
def test_a_shell_card_is_filled_with_it(template):
    prs = Presentation(os.path.join(REPO, "templates", template))
    slide = shapes.find_contact_slide(prs)
    shapes.fill_contact_card(slide, CONTACT)
    spPr = _card(slide)._element.spPr
    assert not spPr.findall(qn("a:solidFill")), "the navy fill survived beside the gradient"
    grads = spPr.findall(qn("a:gradFill"))
    assert len(grads) == 1
    assert _stops(grads[0]) == _stops(etree.parse(CLOSING_FILL).getroot())
    order = [etree.QName(e).localname for e in spPr]
    assert order.index("prstGeom") < order.index("gradFill") < order.index("ln")      # where DrawingML wants it
    assert spPr.find(qn("a:prstGeom")).get("prst") == "roundRect"                      # corners kept
    assert len(spPr.findall(qn("a:effectLst"))) == 1                                   # the one drop shadow kept


def test_a_card_a_builder_draws_is_filled_too():
    prs = Presentation(os.path.join(REPO, "templates", "ars_template.pptx"))
    slide = prs.slides.add_slide(prs.slide_layouts[-1])
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1), Inches(2), Inches(5.6), Inches(3.55))
    card.fill.solid()
    card.line.fill.background()
    shapes.contact_card_fill(card)
    spPr = card._element.spPr
    assert not spPr.findall(qn("a:solidFill")) and len(spPr.findall(qn("a:gradFill"))) == 1
    order = [etree.QName(e).localname for e in spPr]
    assert order.index("prstGeom") < order.index("gradFill") < order.index("ln")


@pytest.mark.parametrize("path", ["build/ics_pipeline/build_ics_gen.py", "build/mrpc_pipeline/build_mrpc_gen.py",
                                  "build/ars_pipeline/build_ars_gen.py"])
def test_every_builder_that_draws_a_card_uses_the_helper(path):
    src = open(os.path.join(REPO, path), encoding="utf-8").read()
    assert "contact_card_fill" in src or "_ccf" in src, f"{path} draws a Contact Us card with its own fill"


def test_the_role_line_stays_readable_on_the_gradient():
    """The orange role line is the weakest text on the card. It sits left of centre, where the gradient is still
    close to navy; measured on the render, its right end is about 62% of the way to the far corner."""
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    def lum(rgb):
        r, g, b = rgb
        return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)

    def ratio(a, b):
        hi, lo = sorted((lum(a), lum(b)), reverse=True)
        return (hi + 0.05) / (lo + 0.05)
    navy, blue, orange, white = (0x00, 0x27, 0x4C), (0x03, 0x5B, 0x95), (0xF1, 0x5D, 0x22), (255, 255, 255)
    t = (0.62 - 0.37) / (1 - 0.37)
    there = tuple(round(navy[i] + t * (blue[i] - navy[i])) for i in range(3))
    assert ratio(orange, there) >= 3.0          # large-text / non-text floor; solid navy gave 4.5
    assert ratio(white, blue) >= 7.0            # white lines at the lightest corner of the card
