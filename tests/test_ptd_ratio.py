"""One program-to-date profitability ratio, printed one way (2026-10-12).

True Sky's ARS divider read "2.1 : 1 revenue to fees, program to date" while its ARS Financial
Performance P&L read "2.2 : 1" in the Program to date column — from the same $2,026,429 of
revenue over $941,929 of fees (Aaron, 2026-10-12: "Profitability disagrees on True Sky between
ARS Financial Performance and the ARS segment slide").

The quotient is 2.1513. The extractor rounded it to 2.15 before storing it, and the divider then
formatted that to one decimal: f"{2.15:.1f}" is "2.1", because the float 2.15 is 2.1499...
The P&L formatted the unrounded quotient and said 2.2. Each slide was right by its own
arithmetic. The fix is one unrounded value and one formatter; the gate check reads the places
the deck states the ratio and fails when they disagree.
"""
import os
import sys

import pytest
from pptx import Presentation
from pptx.util import Inches

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(ROOT, "validation") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "validation"))

import revenue_guarantee_slide as RG   # noqa: E402
import validate_deck as V              # noqa: E402


def repo_file(name):
    return open(os.path.join(ROOT, name), encoding="utf-8").read()

TRUE_SKY_REVENUE, TRUE_SKY_FEES = 2026428.82, 941929.20


# ------------------------------------------------------------------ the trap, and the formatter
def test_rounding_twice_is_the_defect():
    q = TRUE_SKY_REVENUE / TRUE_SKY_FEES
    assert f"{round(q, 2):.1f}" == "2.1"           # what the divider printed
    assert f"{q:.1f}" == "2.2"                       # what the P&L printed


def test_one_formatter_on_the_unrounded_quotient_agrees_with_the_pnl():
    q = TRUE_SKY_REVENUE / TRUE_SKY_FEES
    assert RG.ratio_text(q) == "2.2 : 1" == RG.money(q, "ratio")
    assert RG.ratio_text(None) == "—"


def test_the_one_ratio_is_the_actuals_quotient_the_pnl_divides():
    """The golden deck's workbook has an Actuals tab summing to 3.4 : 1 and a roll-up of
    3.5 : 1; the divider printed the roll-up over a P&L that divided the Actuals. One value:
    the Actuals series when there is one, the roll-up when there is not."""
    from test_revenue_guarantee import base, months
    B = base(months(12, 10_000, 2_950), profitability=3.5, ltd_revenue=120_000, ltd_costs=-35_400)
    assert RG.ratio_of(B) == pytest.approx(120_000 / 35_400)             # Actuals, 3.39
    assert RG.ratio_text(RG.ratio_of(B)) == RG.money(RG.pnl(RG.guarantee(B))["rows"][-1][1][-1], "ratio") == "3.4 : 1"
    assert RG.ratio_of(base(profitability=3.5)) == 3.5                     # nothing else to read
    assert RG.ratio_of(base(ltd_revenue=70_000, ltd_costs=-35_000)) == pytest.approx(2.0)   # the roll-up


def test_the_extractors_no_longer_round_the_ratio():
    for name in ("build/ars_pipeline/extract_base_gen.py", "build/ars_pipeline/base_tab_extract.py"):
        src = repo_file(name)
        assert "profitability" in src
        # the two-decimal rounding of the quotient is gone from both
        assert "/ abs(out['ltd_costs']), 2)" not in src and '/abs(out["ltd_costs"]),2)' not in src


def test_the_divider_uses_the_pnl_formatter():
    src = repo_file("build/ars_pipeline/build_ars_gen.py")
    assert "prof = _ratio_text(_ratio_of(B))" in src
    assert "prof = f\"{B['profitability']:.1f} : 1\"" not in src


# ------------------------------------------------------------------ the gate check
def _deck(pnl_ptd="2.2 : 1", divider="2.1 : 1", prose="2.1 : 1", with_pnl=True, with_divider=True,
          with_prose=True):
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]
    if with_pnl:
        s = prs.slides.add_slide(blank)
        s.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(8), Inches(0.6)).text_frame.text = "ARS Financial Performance"
        rows = [["", "Sep 2026", "Year to date", "Program to date"],
                ["Incremental revenue", "$93,562", "$788,720", "$2,026,429"],
                ["Profitability", "3.3 : 1", "3.1 : 1", pnl_ptd]]
        tb = s.shapes.add_table(len(rows), 4, Inches(0.5), Inches(1.5), Inches(12), Inches(2)).table
        for i, r in enumerate(rows):
            for j, c in enumerate(r):
                tb.cell(i, j).text = c
    if with_divider:
        s = prs.slides.add_slide(blank)
        s.shapes.add_textbox(Inches(0.5), Inches(1.0), Inches(10), Inches(1)).text_frame.text = "Account Revenue Solution®"
        s.shapes.add_textbox(Inches(0.5), Inches(4.0), Inches(3), Inches(0.6)).text_frame.text = divider
        s.shapes.add_textbox(Inches(0.5), Inches(4.65), Inches(3), Inches(0.45)).text_frame.text = "revenue to fees, program to date"
        s.shapes.add_textbox(Inches(4.5), Inches(4.0), Inches(3), Inches(0.6)).text_frame.text = "$1.08M"
        s.shapes.add_textbox(Inches(4.5), Inches(4.65), Inches(3), Inches(0.45)).text_frame.text = "incremental profit, program to date"
    if with_prose:
        s = prs.slides.add_slide(blank)
        s.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(8), Inches(0.6)).text_frame.text = "ARS Program Overview"
        s.shapes.add_textbox(Inches(0.5), Inches(2), Inches(10), Inches(1)).text_frame.text = (
            f"•  Account Revenue Solution® has returned $1.08M in incremental profit "
            f"program-to-date — a {prose} profitability ratio.")
    return prs


def test_the_gate_reads_every_place_the_ratio_is_stated():
    got = V._ptd_ratio_statements(_deck())
    assert [(i, v) for i, _, v in got] == [(1, "2.2 : 1"), (2, "2.1 : 1"), (3, "2.1 : 1")]


def test_the_true_sky_deck_fails():
    f = V.ptd_ratio_findings(_deck())
    assert len(f) == 1 and f[0][0] == "FAIL"
    assert "2.2 : 1" in f[0][2] and "2.1 : 1" in f[0][2] and "ratio_text" in f[0][2]


def test_a_deck_that_agrees_passes():
    assert V.ptd_ratio_findings(_deck(pnl_ptd="2.2 : 1", divider="2.2 : 1", prose="2.2 : 1")) == []


def test_one_statement_is_nothing_to_compare():
    assert V.ptd_ratio_findings(_deck(with_divider=False, with_prose=False)) == []


def test_the_month_and_ytd_columns_are_not_mistaken_for_program_to_date():
    """The P&L's Sep 2026 column reads 3.3 : 1 and Year to date 3.1 : 1 on True Sky; only the
    last column is the program-to-date figure the other slides state."""
    got = [v for i, _, v in V._ptd_ratio_statements(_deck(with_divider=False, with_prose=False))]
    assert got == ["2.2 : 1"]


def test_the_check_is_wired_into_the_gate():
    src = repo_file("validation/validate_deck.py")
    assert "findings += ptd_ratio_findings(prs)" in src
