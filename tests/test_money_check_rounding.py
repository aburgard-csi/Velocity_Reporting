"""The data-vs-deck money check accepts a one-dollar rounding difference (2026.10).

Rally CU's P&L states program-to-date revenue as the sum of its own rounded lines, $35,733,424, while the
extract's unrounded total is 35,733,424.51 (= $35,733,425). The same figure two correct ways was a FAIL.
"""
import os
import sys

from pptx import Presentation
from pptx.util import Inches

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "validation"))
import validate_deck as V                                         # noqa: E402


def deck_saying(text):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(1))
    box.text_frame.text = text
    return prs


def fails(text, extract):
    return [f for f in V.extract_findings(deck_saying(text), extract) if f[0] == "FAIL"]


def test_a_dollar_below_the_extracts_rounding_passes():
    assert not fails("Program to date $35,733,424", {"ltd_revenue": 35733424.506})


def test_the_exact_rounding_still_passes():
    assert not fails("Program to date $35,733,425", {"ltd_revenue": 35733424.506})


def test_a_dollar_above_passes_too():
    assert not fails("Program to date $35,733,426", {"ltd_revenue": 35733424.506})


def test_two_dollars_off_still_fails():
    out = fails("Program to date $35,733,422", {"ltd_revenue": 35733424.506})
    assert out and "ltd_revenue" in out[0][2]


def test_a_missing_figure_still_fails():
    assert fails("Program to date", {"ltd_revenue": 35733424.506})