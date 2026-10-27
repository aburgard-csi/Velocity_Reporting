"""The validator's "N of M" rule counts whole numbers only (Austin Bank's Transaction
Intelligence deck, 2026-10-26: "mean breadth 2.15 of 4" was read as "15 of 4")."""
import os
import sys

from pptx import Presentation
from pptx.util import Inches

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validation"))
import validate_deck as V                                        # noqa: E402


def _deck(*sentences):
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    for i, text in enumerate(sentences):
        s.shapes.add_textbox(Inches(1), Inches(1 + i), Inches(8), Inches(0.5)).text_frame.text = text
    return prs


def _counts(prs):
    return [m for lvl, idx, m in V.text_rule_findings(prs) if "impossible count" in m]


def test_a_decimal_before_of_is_not_a_count():
    assert _counts(_deck("27% touch us through a single channel: mean breadth 2.15 of 4")) == []
    assert _counts(_deck("3 of 4.5 branches")) == []


def test_a_sub_count_over_its_total_still_fails():
    assert _counts(_deck("15 of 4 branches responded")) == ["impossible count: 15 of 4 (sub-count exceeds total)"]
    assert _counts(_deck("1,250 of 4,000 accounts")) == []
    # a full stop after the total is not a decimal: this backtracked to "2247 of 6" on the templates
    assert _counts(_deck("elected to extend overdraft access: 2,247 of 6,192.")) == []
    assert _counts(_deck("7 of 6.")) == ["impossible count: 7 of 6 (sub-count exceeds total)"]
