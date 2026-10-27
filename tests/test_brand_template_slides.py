"""The cover, dividers and closing slide in the CSI brand template's style (Sept. 2026).

The look was checked by rendering decks through PowerPoint; what is pinned here is what broke or could break the
pipeline: the chips must sit ABOVE the band (the combiner re-places them, and putting them straight after the
background hid them behind it), the closing slide keeps the title and the client line the validator reads, and
every slide still opens with a full-bleed plain rectangle the layout passes recognise.
"""
import os
import sys

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "build"))
import brand_art  # noqa: E402
import cover_divider as CD  # noqa: E402


def _prs():
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    return prs


def _slide(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def _order(slide):
    return [sh.name for sh in slide.shapes]


def test_every_art_file_is_checked_in_and_the_mono_logo_is_all_white():
    from PIL import Image
    for f in ("title_band.xml", "title_wedge.xml", "divider_wedge.xml", "divider_fill.xml", "closing_fill.xml",
              "csi_logo_dark.png", "csi_logo_white.png", "csi_logo_mono.png"):
        assert os.path.getsize(os.path.join(brand_art.ART, f)) > 0, f
    im = Image.open(brand_art.LOGO_MONO).convert("RGBA")
    visible = [im.getpixel((x, y)) for x in range(0, im.width, 61) for y in range(0, im.height, 61)]
    visible = [p for p in visible if p[3] > 200]
    assert visible and all(p[:3] == (255, 255, 255) for p in visible)


def test_the_art_carries_literal_colours_not_theme_colours():
    """The shells' theme is the stock Office one, where accent2..5 mean other colours."""
    for f in ("title_band.xml", "title_wedge.xml", "divider_wedge.xml", "divider_fill.xml", "closing_fill.xml"):
        xml = open(os.path.join(brand_art.ART, f), encoding="utf-8").read()
        assert "schemeClr" not in xml, f
        assert "creationId" not in xml and "userDrawn" not in xml, f


def test_the_cover_starts_with_a_plain_fullbleed_rectangle_and_the_chips_sit_above_the_band():
    prs = _prs(); s = _slide(prs)
    CD.draw_cover(s, [CD.PRODUCT_ARS, CD.PRODUCT_ICS], "Marine FCU", "September 2026")
    first = s.shapes[0]
    assert first.name == CD.TAG_COVER and first.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE
    assert Emu(first.width).inches > 12.5 and Emu(first.height).inches > 6.5
    order = _order(s)
    assert order.index("csi:band") < order.index(CD.TAG_COVER_CHIP) and order.index("csi:wedge") < order.index(CD.TAG_COVER_CHIP)


def test_the_combiner_putting_the_chips_back_keeps_them_above_the_band():
    """The bug the first render showed: chips re-inserted right after the background were hidden behind the band."""
    prs = _prs(); s = _slide(prs)
    CD.draw_cover(s, [CD.PRODUCT_ARS], "Marine FCU", "September 2026")
    assert CD.set_cover_products(s, [CD.PRODUCT_ARS, CD.PRODUCT_ICS, CD.PRODUCT_MRPC])
    order = _order(s)
    chips = [i for i, n in enumerate(order) if n == CD.TAG_COVER_CHIP]
    assert len(chips) == 3
    assert min(chips) > order.index("csi:band") and min(chips) > order.index("csi:wedge")
    assert CD.slide_title(s) == CD.PRODUCT_ARS, "the first text shape is still the first chip"


def test_the_divider_background_is_a_gradient_rectangle():
    prs = _prs(); s = _slide(prs)
    CD.draw_divider(s, CD.PRODUCT_ARS, "Mailings", stats=[("3.9 : 1", "ratio")])
    bg = s.shapes[0]
    assert bg.name == CD.TAG_DIVIDER and bg.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE
    assert bg._element.spPr.find(qn("a:gradFill")) is not None
    assert CD.is_new_divider(s) and CD.slide_title(s) == CD.PRODUCT_ARS


def _shell_closing(prs, line="Marine FCU  •  September 2026"):
    s = _slide(prs)
    for i, text in enumerate(("Questions & Discussion", line) if line else ("Questions & Discussion",)):
        box = s.shapes.add_textbox(Inches(1), Inches(2 + i), Inches(8), Inches(1))
        box.text_frame.text = text
    return s


def test_the_closing_slide_keeps_its_title_and_the_clients_line():
    prs = _prs(); s = _shell_closing(prs)
    assert CD.redraw_closing_in_place(s)
    texts = [p.text for sh in s.shapes if sh.has_text_frame for p in sh.text_frame.paragraphs if p.text.strip()]
    assert texts[0] == "Questions & Discussion" and "Marine FCU  •  September 2026" in texts
    assert CD.slide_title(s) == "Questions & Discussion"
    first = s.shapes[0]
    assert first.name == CD.TAG_CLOSING and Emu(first.width).inches > 12.5
    assert first._element.spPr.find(qn("a:gradFill")) is not None
    assert not CD.is_divider(s), "a closing slide is never mistaken for a section divider"


def test_the_closing_redraw_runs_once_and_guesses_nothing():
    prs = _prs(); s = _shell_closing(prs)
    assert CD.restyle_closing(prs) is True
    n = len(s.shapes)
    assert CD.restyle_closing(prs) is False and len(s.shapes) == n          # already drawn: left alone
    bare = _shell_closing(_prs(), line=None)
    before = [sh.text_frame.text for sh in bare.shapes if sh.has_text_frame]
    assert CD.redraw_closing_in_place(bare) is False                         # no client line: nothing is invented
    assert [sh.text_frame.text for sh in bare.shapes if sh.has_text_frame] == before


def test_nothing_on_the_new_slides_is_below_the_floor_or_shadowed():
    prs = _prs()
    cover, div, close = _slide(prs), _slide(prs), _shell_closing(prs)
    CD.draw_cover(cover, [CD.PRODUCT_ARS, CD.PRODUCT_ICS, CD.PRODUCT_MRPC, CD.PRODUCT_CP], "Marine FCU", "September 2026")
    CD.draw_divider(div, CD.PRODUCT_ICS, "Referrals", stats=[("47,324", "referrals")],
                    programs=[CD.PRODUCT_ARS, CD.PRODUCT_ICS], current=CD.PRODUCT_ICS)
    CD.redraw_closing_in_place(close)
    for s in (cover, div, close):
        for sh in s.shapes:
            if sh.has_text_frame:
                for p in sh.text_frame.paragraphs:
                    for r in p.runs:
                        assert r.font.size.pt >= CD.MIN_PT, (r.text, r.font.size.pt)
            assert "outerShdw" not in sh._element.xml, sh.name


def test_a_long_client_name_steps_the_cover_title_down_to_fit_two_lines():
    assert CD._cover_pt("Marine FCU") == 60
    long_name = "Altamaha Bank and Trust Company of the Greater Southeastern Region"
    assert 36 <= CD._cover_pt(long_name) < 60
