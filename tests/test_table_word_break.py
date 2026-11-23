"""validate_deck.table_word_break_findings: a single word wider than its table cell breaks mid-word and FAILs
(Aaron, 2026-11-16, Dannemora FCU's eligibility table: "Open/Activ" over "e")."""
import os
import sys

from pptx import Presentation
from pptx.util import Inches, Pt

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "validation"))
sys.path.insert(0, os.path.join(REPO, "build"))
import validate_deck as V  # noqa: E402


def deck(col_in, text, size=14, bold=True):
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    s = prs.slides.add_slide(prs.slide_layouts[6])
    t = s.shapes.add_table(2, 2, Inches(0.5), Inches(2.0), Inches(col_in + 2.0), Inches(0.8)).table
    t.columns[0].width = Inches(2.0)
    t.columns[1].width = Inches(col_in)
    cell = t.cell(0, 1)
    cell.text = text
    for r in cell.text_frame.paragraphs[0].runs:
        r.font.size = Pt(size)
        r.font.bold = bold
    return prs


def test_a_word_wider_than_its_column_fails():
    f = V.table_word_break_findings(deck(0.95, "Open/Active"))
    assert f and f[0][0] == "FAIL" and "Open/Active" in f[0][2]


def test_words_that_wrap_at_a_space_pass():
    assert V.table_word_break_findings(deck(0.95, "Open or Active")) == []


def test_a_wide_enough_column_passes():
    assert V.table_word_break_findings(deck(1.6, "Open/Active")) == []


def test_the_rule_is_registered():
    assert V.table_word_break_findings in V.RULES
    assert V.table_growth_overlap_findings in V.RULES


def grown_deck(text, bar_top):
    """A one-column table at 2.0" with two 0.3" rows, and a bar drawn at `bar_top` below it."""
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    s = prs.slides.add_slide(prs.slide_layouts[6])
    t = s.shapes.add_table(2, 1, Inches(0.5), Inches(2.0), Inches(1.2), Inches(0.6)).table
    for i in range(2):
        t.rows[i].height = Inches(0.3)
    cell = t.cell(1, 0)
    cell.text = text
    for r in cell.text_frame.paragraphs[0].runs:
        r.font.size = Pt(12)
    s.shapes.add_shape(1, Inches(0.5), Inches(bar_top), Inches(3.0), Inches(0.4))
    return prs


def test_a_table_grown_into_the_bar_below_fails():
    # Dannemora's appendix: a wrapped return pushed the last overrides under the Trend Settings bar
    f = V.table_growth_overlap_findings(grown_deck("minus Outstanding Loan Amount and more words", 2.65))
    assert f and f[0][0] == "FAIL"


def test_a_table_that_does_not_wrap_passes():
    assert V.table_growth_overlap_findings(grown_deck("$100", 2.65)) == []
