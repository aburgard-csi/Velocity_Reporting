"""The ARS Profit & Loss slide (Aaron, 2026-10-02).

"i wanted a P&L slide that makes it easier to see the full financial picture."

ARS Financial Performance showed Marine FCU $144,999 of revenue and $144,999 of profit
for August — identical, because August carried no respondent fee — and nothing on the
slide said so. These tests pin the two things that makes checkable: the P&L is on EVERY
ARS deck, not only the under-3:1 clients, and it appears exactly once in a deck.
"""
import re

import pytest

import pnl_slide as PS
import revenue_guarantee_slide as RG
from test_revenue_guarantee import lined, months

BUILDER = "build/ars_pipeline/build_ars_gen.py"


def g_of(n=18, rev=10_000, cost=3_000, lines=None):
    return RG.guarantee(lined(months(n, rev, cost),
                              lines if lines is not None else [["Program Fee", [float(cost)] * n]]))


# ------------------------------------------------------------------ on every deck
def test_the_pnl_slide_is_not_gated_on_profitability(repo_file):
    """The guarantee slide is gated at 3 : 1; this one is not.

    Marine FCU is at 5.36 : 1, so under the guarantee slide's rule it gets no financial
    detail beyond four tiles — which is the gap this slide was asked for.
    """
    src = repo_file(BUILDER)
    call = re.search(r"pnl_slide\.add_pnl_slide\(", src)
    assert call, "build_ars_gen does not add the P&L slide"
    # The 400 characters before the call must not make it conditional.
    before = src[max(0, call.start() - 400):call.start()]
    assert "should_build" not in before.split("import pnl_slide")[-1]
    assert "RPE_JAMES_SLIDES" not in before.split("import pnl_slide")[-1]


def test_the_guarantee_slide_no_longer_tabulates_the_pnl(repo_file):
    """One deck, one P&L. A client under 3 : 1 gets both slides."""
    src = repo_file("build/ars_pipeline/revenue_guarantee_slide.py")
    # That function's body only: everything up to the next top-level def, so a helper
    # defined after it is not read as part of the slide.
    body = re.split(r"\ndef ", src.split("def add_revenue_guarantee_slide")[1])[0]
    assert "_add_table" not in body, "the guarantee slide still draws a table"
    assert "pnl(g)" not in body, "the guarantee slide still builds the P&L"


# ------------------------------------------------------------------ what it says
def test_a_month_with_no_cost_gets_no_sentence_about_it():
    """Aaron, 2026-10-02: "remove the line about carried no program cost".

    It was there on the reasoning that identical revenue and profit look like an error.
    The table already shows the $0 cost line and the chart shows that month as a bar with
    no orange in it, so the sentence was the deck saying it a third time — and it cost the
    chart below it the height it needed.
    """
    rows = months(13, 10_000, 3_000)
    rows[-1][2] = 0.0
    g = RG.guarantee(lined(rows, [["Program Fee", [3_000.0] * 12 + [0.0]]]))
    cap = PS.caption(RG.pnl(g), g)
    assert "carried no program cost" not in cap
    assert cap == "", cap


def test_cost_lines_the_program_never_carried_are_named_in_the_notes():
    """Named where an auditor looks, not on the face.

    They were on the face first and cost the caption a second line, which cost the chart
    under it the height it needs to run the full width of the slide. The caption keeps the
    one thing a reader cannot work out from the table.
    """
    g = g_of(lines=[["Program Fee", [3_000.0] * 18], ["Consulting Fee / Other", [0.0] * 18]])
    P = RG.pnl(g)
    assert P["dropped"] == ["Consulting Fee / Other"]
    notes = PS.notes_text(P, g, {}, "wb.xlsx", "Actuals MM", "August 2026")
    assert "Consulting Fee / Other" in notes
    assert "Consulting Fee / Other" not in PS.caption(P, g)


def test_a_left_out_month_is_still_stated_and_fits_one_line():
    """The one caption that survives. A month left out as incomplete is stated nowhere else
    on the slide, and CLAUDE.md requires it said (never silently dropped). One line, because
    the chart below is sized from what the caption leaves."""
    from textfit import text_width_in
    g = g_of()
    g["left_out"] = "Sep 2026"
    cap = PS.caption(RG.pnl(g), g)
    assert "Sep 2026 is left out" in cap
    usable = PS.TEXT_W - 0.2 - 0.45          # box, margins, the Carlito/Calibri wrap slack
    assert text_width_in(cap, PS.TEXT_PT, "Calibri", False) <= usable, cap


def test_the_chart_is_sized_from_the_room_the_caption_leaves():
    """Rendered at the height it will occupy, so it always runs the full width.

    A constant height left white space under a captionless slide, and shrank the chart off
    the table's left edge when the caption ran to two lines.
    """
    assert PS.CHART_MIN_H < PS.CHART_MAX_H
    assert PS.CHART_L + PS.CHART_W <= 13.333
    assert PS.CHART_FLOOR <= 6.78            # clear of the logo band


def test_the_notes_name_the_actuals_tab_and_the_columns():
    g = g_of()
    P = RG.pnl(g)
    notes = PS.notes_text(P, g, {}, "1539-2026.09-Marine FCU-Workbook_v2_1_0.xlsx",
                          "Actuals MM", "August 2026")
    assert "Actuals tab" in notes
    assert "1539-2026.09-Marine FCU-Workbook_v2_1_0.xlsx" in notes
    assert "Year to date" in notes and "Program to date" in notes
    assert "complete month" in notes


# ------------------------------------------------------------------ geometry
def test_the_table_spans_the_slide_without_running_off_it():
    """Three columns do not fit beside the guarantee callouts, which is why this slide
    exists separately. The widths must still add up to the table's own width."""
    assert PS.LABEL_W + 3 * PS.COL_W == pytest.approx(PS.TABLE_W)
    assert PS.TABLE_L + PS.TABLE_W <= 13.333


@pytest.fixture
def repo_file():
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def read(rel):
        with open(os.path.join(root, rel.replace("/", os.sep)), encoding="utf-8") as fh:
            return fh.read()
    return read
