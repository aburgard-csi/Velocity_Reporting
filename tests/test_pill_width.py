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


def test_drop_kpi_tile_removes_the_tile_and_spreads_the_rest():
    from pptx import Presentation
    from pptx.util import Emu
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    for i, (v, l) in enumerate([("53.2%", "12-Mo Take Rate"), ("0.0%", "Historical Take Rate"),
                                ("2,090", "Eligible Accounts"), ("978", "No Debit Card")]):
        SH.tile(slide, 0.56 + i * 3.12, 1.30, 2.85, 1.05, v, l)
    assert SH.drop_kpi_tile(slide, "Historical Take Rate") is True
    texts = [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame]
    assert "Historical Take Rate" not in texts and "0.0%" not in texts
    tiles = sorted((sh for sh in slide.shapes if sh.has_text_frame and not sh.text_frame.text.strip()),
                   key=lambda s: s.left)
    assert len(tiles) == 3
    lefts = [Emu(t.left).inches for t in tiles]
    widths = {round(Emu(t.width).inches, 3) for t in tiles}
    assert len(widths) == 1
    assert lefts[0] == pytest.approx(0.56, abs=0.01)
    assert Emu(tiles[-1].left + tiles[-1].width).inches == pytest.approx(12.77, abs=0.01)
    assert lefts[1] - lefts[0] == pytest.approx(lefts[2] - lefts[1], abs=0.01)
    # each value and label stays centred over its own tile
    for tile in tiles:
        centre = Emu(tile.left + tile.width // 2).inches
        over = [sh for sh in slide.shapes if sh.has_text_frame and sh.text_frame.text.strip()
                and abs(Emu(sh.left + sh.width // 2).inches - centre) < 0.01]
        assert len(over) == 2


def test_drop_kpi_tile_does_nothing_when_the_label_is_absent():
    from pptx import Presentation
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    SH.tile(slide, 0.56, 1.30, 2.85, 1.05, "53.2%", "12-Mo Take Rate")
    assert SH.drop_kpi_tile(slide, "Historical Take Rate") is False
    assert sum(1 for sh in slide.shapes if sh.has_text_frame and not sh.text_frame.text.strip()) == 1