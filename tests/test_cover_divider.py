"""The shared cover and section divider (build/cover_divider.py, 2026-10-02).

What is pinned is what the rest of the pipeline reads off these two slides, not their
look: the cover is still found by its "Executive Review" line and still yields the client
and month; the first text shape is still the title; nothing drops below the 16 pt floor;
no shadow is drawn; the combiner can replace the product chips and draw the track.
"""
import os
import sys

import pytest
from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.util import Inches

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "build"))
sys.path.insert(0, os.path.join(REPO, "validation"))
import assemble_combined as AC  # noqa: E402
import cover_divider as CD  # noqa: E402
import validate_deck as vd  # noqa: E402


def _prs():
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    return prs


def _slide(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def _runs(slide):
    return [r for sh in slide.shapes if sh.has_text_frame
            for p in sh.text_frame.paragraphs for r in p.runs]


# --- cover ---------------------------------------------------------------------
def test_cover_is_recognised_and_yields_client_and_month():
    prs = _prs(); s = _slide(prs)
    CD.draw_cover(s, [CD.PRODUCT_ARS, CD.PRODUCT_ICS], "Marine FCU", "September 2026")
    assert AC._is_cover(s)
    assert vd._cover_client_and_month(prs) == ("Marine FCU", "September 2026")
    assert CD.slide_title(s) == CD.PRODUCT_ARS, "the first chip is the slide's title"


def test_cover_period_is_read_the_way_the_combiner_reads_it():
    prs = _prs(); s = _slide(prs)
    CD.draw_cover(s, [CD.PRODUCT_CP], "Marine FCU", "September 2026")
    period = next(sh.text_frame.text.strip().split("•")[-1].strip()
                  for sh in s.shapes if sh.has_text_frame and "•" in sh.text_frame.text)
    assert period == "September 2026"


def test_four_products_wrap_to_a_second_row_of_chips():
    prs = _prs(); s = _slide(prs)
    CD.draw_cover(s, [CD.PRODUCT_ARS, CD.PRODUCT_ICS, CD.PRODUCT_MRPC, CD.PRODUCT_CP], "Marine FCU", "September 2026")
    chips = [sh for sh in s.shapes if sh.name == CD.TAG_COVER_CHIP]
    assert len(chips) == 4
    rows = {round(sh.top / 914400, 2) for sh in chips}
    assert len(rows) == 2, "four chips do not fit one row at 16 pt"
    assert all(sh.left + sh.width <= Inches(13.333 - 0.5) + 1 for sh in chips)


def test_combiner_replaces_the_chips_and_keeps_them_first():
    prs = _prs(); s = _slide(prs)
    CD.draw_cover(s, [CD.PRODUCT_ARS], "Marine FCU", "September 2026")
    assert AC.set_title_products(s, ["ARS", "ICS", "CP"])
    chips = [sh.text_frame.text for sh in s.shapes if sh.name == CD.TAG_COVER_CHIP]
    assert chips == [AC.PRODUCT_NAME["ARS"], AC.PRODUCT_NAME["ICS"], AC.PRODUCT_NAME["CP"]]
    assert CD.slide_title(s) == AC.PRODUCT_NAME["ARS"]
    assert vd._cover_client_and_month(prs) == ("Marine FCU", "September 2026")


def test_cover_is_fullbleed_so_it_carries_no_number():
    prs = _prs(); s = _slide(prs)
    CD.draw_cover(s, [CD.PRODUCT_ARS], "Marine FCU", "September 2026")
    assert CD._is_fullbleed(s)


# --- divider -------------------------------------------------------------------
def test_divider_title_comes_first_and_is_not_a_cover():
    prs = _prs(); s = _slide(prs)
    CD.draw_divider(s, CD.PRODUCT_ARS, "Mailings · Debit Card · Reg E",
                    stats=[("5.4 : 1", "revenue to fees, program to date"), ("$8.80M", "profit")])
    assert CD.slide_title(s) == CD.PRODUCT_ARS
    assert not AC._is_cover(s)
    assert CD.is_divider(s) and CD.is_new_divider(s)
    assert 1 in AC.section_slides([s]), "a divider survives section_slides"


def test_standalone_divider_has_no_track_and_combined_one_does():
    prs = _prs(); s = _slide(prs)
    CD.draw_divider(s, CD.PRODUCT_ICS, "Referrals")
    assert not any(sh.name == CD.TAG_TRACK for sh in s.shapes)
    assert CD.set_divider_track(s, [CD.PRODUCT_ARS, CD.PRODUCT_ICS, CD.PRODUCT_CP], CD.PRODUCT_ICS)
    labels = [sh.text_frame.text for sh in s.shapes if sh.name == CD.TAG_TRACK and sh.has_text_frame
              and sh.text_frame.text.strip()]
    assert labels == ["ARS", "ICS", "CASHPLEASE"]
    # redrawing replaces rather than stacks
    CD.set_divider_track(s, [CD.PRODUCT_ARS, CD.PRODUCT_ICS], CD.PRODUCT_ICS)
    labels = [sh.text_frame.text for sh in s.shapes if sh.name == CD.TAG_TRACK and sh.has_text_frame
              and sh.text_frame.text.strip()]
    assert labels == ["ARS", "ICS"]


def test_combiner_tracks_only_program_dividers():
    prs = _prs()
    a = _slide(prs); CD.draw_divider(a, CD.PRODUCT_ARS, "Mailings · Debit Card · Reg E")
    sub = _slide(prs); CD.draw_divider(sub, "Mailing Insights", "ARS Direct Mail Performance")
    m = _slide(prs); CD.draw_divider(m, CD.PRODUCT_MRPC, "Enrollments · Retention · Revenue")
    assert AC.set_divider_tracks(prs, ["ARS", "MRPC"]) == 2
    assert not any(sh.name == CD.TAG_TRACK for sh in sub.shapes), "a sub-section divider gets no track"


def test_redraw_in_place_keeps_a_swapped_second_line():
    prs = _prs(); s = _slide(prs)
    CD.draw_divider(s, "New Account Profile", "Personal accounts opened Sep 2025 through Aug 2026")
    CD.redraw_divider_in_place(s)
    texts = [sh.text_frame.text for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip()]
    assert texts[0] == "New Account Profile"
    assert "Sep 2025 through Aug 2026" in " ".join(texts)


# --- the rules both slides keep ----------------------------------------------------
@pytest.mark.parametrize("draw", [
    lambda s: CD.draw_cover(s, [CD.PRODUCT_ARS, CD.PRODUCT_ICS, CD.PRODUCT_MRPC, CD.PRODUCT_CP], "Marine FCU", "September 2026"),
    lambda s: CD.draw_divider(s, CD.PRODUCT_MRPC, "Enrollments · Retention · Revenue",
                              stats=[("7,942", "enrollments, program to date"), ("93", "enrollments in Sep 2026"),
                                     ("1,293", "enrollments, last 12 months")],
                              programs=[CD.PRODUCT_ARS, CD.PRODUCT_MRPC], current=CD.PRODUCT_MRPC),
])
def test_no_run_below_the_floor_and_no_shadow(draw):
    prs = _prs(); s = _slide(prs)
    draw(s)
    assert all(r.font.size.pt >= 16 for r in _runs(s))
    assert not s._element.xpath(".//a:outerShdw"), "no drop shadow on the cover or a divider"


def test_both_slides_pass_the_validators_geometry_and_collision_rules(tmp_path):
    prs = _prs()
    CD.draw_cover(_slide(prs), [CD.PRODUCT_ARS, CD.PRODUCT_ICS, CD.PRODUCT_MRPC, CD.PRODUCT_CP], "Marine FCU", "September 2026")
    CD.draw_divider(_slide(prs), CD.PRODUCT_ARS, "Mailings · Debit Card · Reg E",
                    stats=[("5.4 : 1", "revenue to fees, program to date"), ("$8.80M", "incremental profit, program to date"),
                           ("12.1%", "response to the Jul 2026 mailing")],
                    programs=[CD.PRODUCT_ARS, CD.PRODUCT_ICS, CD.PRODUCT_MRPC, CD.PRODUCT_CP], current=CD.PRODUCT_ARS)
    path = str(tmp_path / "cd.pptx"); prs.save(path); prs = Presentation(path)
    fails = [f for f in vd.geometry_findings(prs) + vd.text_collision_findings(prs)
             + vd.single_line_overflow_findings(prs) if f[0] == "FAIL"]
    assert fails == []
