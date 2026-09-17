"""validate_deck.table_label_fit_findings: a wrapped row label that pushes a table off the slide
FAILs (Aaron, 2026-09-17, after branch names reached the take-rate-by-branch table)."""
import os
import sys

from pptx import Presentation
from pptx.util import Inches, Pt

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "validation"))
import validate_deck as V  # noqa: E402


def deck(first_col_in, labels, top=2.8):
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    s = prs.slides.add_slide(prs.slide_layouts[6])
    t = s.shapes.add_table(len(labels), 3, Inches(0.5), Inches(top), Inches(12.3), Inches(0.4 * len(labels))).table
    t.columns[0].width = Inches(first_col_in)
    for i, lab in enumerate(labels):
        t.rows[i].height = Inches(0.4)
        cell = t.cell(i, 0)
        cell.text = lab
        for r in cell.text_frame.paragraphs[0].runs:
            r.font.size = Pt(16)
            r.font.bold = True
    return prs


NAMES = ["North Chicago", "Waukegan", "Country Club Hills", "Member Contact Center", "Leaders Network",
         "Chicago Galewood", "Chicago Douglas", "Chicago Uptown", "Zion", "Total (all branches)"]


def test_names_in_a_number_sized_column_fail():
    f = V.table_label_fit_findings(deck(1.41, NAMES))
    assert f and f[0][0] == "FAIL" and "wraps" in f[0][2]


def test_a_column_wide_enough_passes():
    assert V.table_label_fit_findings(deck(2.60, NAMES)) == []


def test_a_wrap_that_still_fits_the_slide_passes():
    assert V.table_label_fit_findings(deck(1.41, NAMES[:3], top=2.0)) == []


def test_the_rule_is_registered():
    assert V.table_label_fit_findings in V.RULES
