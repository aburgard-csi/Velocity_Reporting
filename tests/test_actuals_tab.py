"""Reading the ARS workbook's Actuals tab (Aaron, 2026-09-22).

The tab is the program's month-by-month P&L and comes in three shapes in one workbook —
`Actuals MM`, `Actuals SM` and plain `Actuals` — whose COST ROWS DIFFER: an MM client is
billed a respondent fee, an SM client carries spot mailings, points and a program fee. Only
the two totals rows are relied on, because those exist in every shape; the cost lines between them
are carried under the sheet's own labels for the Revenue Guarantee P&L (2026-10-02).

Synthetic workbooks; no client data.
"""
import datetime
import os

import openpyxl
import pytest

import actuals_tab as A

MONTHS = [datetime.datetime(2026, m, 1) for m in range(1, 7)]
REV = [100, 200, 300, 400, 500, 600]
COST = [-60, -70, -80, -90, -100, -110]


def workbook(path, sheet, cost_rows=("Respondent Fee",), rev=REV, cost=COST,
             total_col=True, generated="9/9/2026 1:37:40 PM", months=MONTHS,
             rev_label="Total Marginal Revenues", cost_label="Total Cost", line_values=None):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    ws.cell(4, 2, "Union Financial"); ws.cell(5, 2, "Actuals")
    ws.cell(6, 2, "August 2026 Data"); ws.cell(8, 2, "Actual Monthly Results")
    for j, m in enumerate(months):
        ws.cell(8, 4 + j, m)
    ws.cell(11, 3, rev_label)
    for j, v in enumerate(rev):
        if v is not None:
            ws.cell(11, 4 + j, v)
    if total_col:
        ws.cell(11, 4 + len(months), sum(v for v in rev if v is not None))
    ws.cell(12, 2, "Costs")
    r = 13
    for lab in cost_rows:
        ws.cell(r, 3, lab)
        for j, v in enumerate((line_values or {}).get(lab, [])):
            ws.cell(r, 4 + j, v)
        r += 1
    ws.cell(r, 3, cost_label)
    for j, v in enumerate(cost):
        if v is not None:
            ws.cell(r, 4 + j, v)
    if generated:
        ws.cell(r + 2, 3, f"Report Generated: {generated}")
    wb.save(path)
    return str(path)


def test_it_reads_the_months_with_cost_as_a_positive(tmp_path):
    p = workbook(tmp_path / "mm.xlsx", "Actuals MM")
    out = A.read(p, mm=True)
    assert out["available"] is True and out["sheet"] == "Actuals MM"
    assert out["months"][0] == ["Jan 2026", 100.0, 60.0]
    assert out["revenue"] == 2100.0
    assert out["cost"] == 510.0            # the sheet carries these negative
    assert out["window"] == ["Jan 2026", "Jun 2026"]


def test_the_sm_shape_reads_the_same_two_rows(tmp_path):
    """Different cost rows, same totals rows — which is why only those two are read."""
    p = workbook(tmp_path / "sm.xlsx", "Actuals",
                 cost_rows=("Spot Mailings", "Ongoing Usage Points", "Program Fee"))
    out = A.read(p, mm=False)
    assert out["available"] is True and out["sheet"] == "Actuals"
    assert (out["revenue"], out["cost"]) == (2100.0, 510.0)


def test_the_cost_lines_are_carried_under_the_sheets_own_labels(tmp_path):
    """The P&L on the Revenue Guarantee slide itemises cost (Aaron, 2026-10-02). Each line is
    positive like Total Cost, a discount (positive in the sheet) reads as a negative cost, and
    a line with no figures at all is not carried."""
    p = workbook(tmp_path / "sm.xlsx", "Actuals",
                 cost_rows=("Spot Mailings", "Program Fee", "Multi-Product Discount", "Unused"),
                 line_values={"Spot Mailings": [-10] * 6, "Program Fee": [-50] * 6,
                              "Multi-Product Discount": [5, 0, 0, 0, 0, 0]})
    out = A.read(p, mm=False)
    assert out["lines"] == [["Spot Mailings", [10.0] * 6], ["Program Fee", [50.0] * 6],
                            ["Multi-Product Discount", [-5.0, 0.0, 0.0, 0.0, 0.0, 0.0]]]


def test_an_mm_client_is_never_read_off_the_sm_tab(tmp_path):
    """The workbook carries all three tabs. Falling back to the plain one for an MM client
    would report the other revenue model's figures, which is the whole point of the split."""
    p = workbook(tmp_path / "smonly.xlsx", "Actuals")
    out = A.read(p, mm=True)
    assert out["available"] is False
    assert "Actuals MM" in out["reason"]


def test_a_month_with_no_figures_is_skipped_not_zeroed(tmp_path):
    p = workbook(tmp_path / "gap.xlsx", "Actuals MM",
                 rev=[100, None, 300, 400, 500, 600], cost=[-60, None, -80, -90, -100, -110])
    out = A.read(p, mm=True)
    assert [m[0] for m in out["months"]] == ["Jan 2026", "Mar 2026", "Apr 2026", "May 2026",
                                             "Jun 2026"]
    assert out["revenue"] == 1900.0


def test_the_total_column_is_carried_as_a_cross_check_not_as_the_answer(tmp_path):
    """A total that disagrees with its own months is worth seeing; the figure the slide
    draws is always the sum of the months."""
    p = workbook(tmp_path / "tot.xlsx", "Actuals MM")
    wb = openpyxl.load_workbook(p)
    ws = wb["Actuals MM"]
    ws.cell(11, 4 + len(MONTHS), 9999)          # a total column that does not reconcile
    wb.save(p)
    out = A.read(p, mm=True)
    assert out["revenue"] == 2100.0
    assert out["total_column"] == 9999.0


def test_the_report_generated_stamp_is_carried(tmp_path):
    p = workbook(tmp_path / "gen.xlsx", "Actuals MM")
    assert A.read(p, mm=True)["generated"] == "9/9/2026"


@pytest.mark.parametrize("kw, wants", [
    (dict(rev_label="Marginal Revenues"), "Total Marginal Revenues"),
    (dict(cost_label="Costs"), "Total Cost"),
])
def test_a_missing_row_is_named_rather_than_guessed(tmp_path, kw, wants):
    p = workbook(tmp_path / "missing.xlsx", "Actuals MM", **kw)
    out = A.read(p, mm=True)
    assert out["available"] is False
    assert wants in out["reason"]


def test_a_sheet_with_no_month_columns_says_so(tmp_path):
    p = workbook(tmp_path / "nomonths.xlsx", "Actuals MM", months=MONTHS[:2])
    out = A.read(p, mm=True)
    assert out["available"] is False and "month columns" in out["reason"]


def test_a_missing_workbook_is_stated(tmp_path):
    out = A.read(str(tmp_path / "nope.xlsx"), mm=True)
    assert out["available"] is False and "no ARS workbook" in out["reason"]


def test_both_extractors_carry_it_into_base_json():
    """The slide reads base.json, not the workbook — the extractors are the only things in
    this pipeline that open one."""
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name, call in (("extract_base_gen.py", "actuals_tab.read(wb, mm=True)"),
                       ("base_tab_extract.py", "actuals_tab.read(wb, mm=False)")):
        src = open(os.path.join(here, "build", "ars_pipeline", name), encoding="utf-8").read()
        assert call in src, name
