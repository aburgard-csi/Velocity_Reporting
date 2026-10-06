"""The upper-right period pill widens to its text (2026.10).

The template pill is 2.35 in wide, sized for "PTD · June 2026". "September" is the longest month, and
"PTD · September 2026" wrapped onto the slide title: the validation gate rejected the 2026.10 ARS
decks for 1075, 1204 and 1537 on it.
"""
import pytest
from pptx import Presentation
from pptx.util import Emu, Inches, Pt

import shapes as SH
from textfit import text_width_in


def _pill(text):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    sp = SH.pill(slide, text)
    sp.text_frame.paragraphs[0].runs[0].font.size = Pt(16)
    return sp


def test_a_long_month_widens_the_pill_with_its_right_edge_fixed():
    sp = _pill("PTD · September 2026")
    right = Emu(sp.left + sp.width).inches
    assert SH.widen_pill_to_text(sp) is True
    assert Emu(sp.left + sp.width).inches == pytest.approx(right, abs=0.001)
    margins = Emu(sp.text_frame.margin_left).inches + Emu(sp.text_frame.margin_right).inches
    assert Emu(sp.width).inches >= text_width_in("PTD · September 2026", 16, "Montserrat", True) + margins


def test_a_short_month_is_left_alone():
    sp = _pill("PTD · June 2026")
    before = (sp.left, sp.width)
    assert SH.widen_pill_to_text(sp) is False
    assert (sp.left, sp.width) == before


def test_a_shape_that_is_not_a_pill_is_left_alone():
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = SH.pill(slide, "PTD · September 2026", L=2.0, T=3.0)       # not in the upper-right corner
    box.text_frame.paragraphs[0].runs[0].font.size = Pt(16)
    assert SH.widen_pill_to_text(box) is False
