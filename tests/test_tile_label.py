"""The KPI callout subtext matches on Product Mix and Excluded Accounts (2026.10).

Product Mix is a "dense" slide, so restyle_fonts left its tile labels at 12 pt; Excluded Accounts is not, so
the same labels were floored to 16 pt and the two slides read differently. Both now keep the smaller 12 pt.
"""
import os
import tempfile

from pptx import Presentation

import restyle_fonts as RF
import shapes as SH


def test_the_two_modules_agree_on_the_label_name():
    assert SH.SMALL_TILE_LABEL == RF.SMALL_TILE_LABEL


def _deck_with(small):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    SH.tile(slide, 0.56, 1.66, 2.85, 1.28, "116,381", "Accounts excl. closed", small_label=small)
    path = os.path.join(tempfile.mkdtemp(), "t.pptx")
    prs.save(path)
    RF.restyle(path)
    out = Presentation(path)
    return [r.font.size.pt for sh in out.slides[0].shapes if sh.has_text_frame
            for p in sh.text_frame.paragraphs for r in p.runs if r.text == "Accounts excl. closed"]


def test_a_small_label_keeps_12_pt_through_restyle():
    assert _deck_with(True) == [12.0]


def test_other_tile_labels_are_still_floored_to_16_pt():
    assert _deck_with(False) == [16.0]


def test_both_slides_ask_for_the_small_label():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for mod in ("product_mix_slide.py", "excluded_accounts_slide.py"):
        src = open(os.path.join(root, "build", "ars_pipeline", mod), encoding="utf-8").read()
        assert "small_label=True" in src, mod