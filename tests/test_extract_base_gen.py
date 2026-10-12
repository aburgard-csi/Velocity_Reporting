"""extract_base_gen — the MM extractor gets the same blank-month rule as the SM one.

It read each Key Trends month as `round(spend.get(m, 0) or 0, 2)` and the card count as
`(tot or 0) - (non or 0)`: a blank month became $0 spend and zero cardholders and would
chart as a collapse, silently. The SM extractor crashed on the same blank (1657) and was
fixed first; both now share base_guard.key_trends and base_guard.data_issue (Aaron,
2026-09-14: "fix the extract_base_gen zeroing too"). Synthetic workbooks, no client data.
"""
import datetime
import json
import os
import subprocess
import sys

import openpyxl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARS = os.path.join(REPO, "build", "ars_pipeline")
sys.path.insert(0, ARS)
import base_guard as G        # noqa: E402
import extract_base_gen as X  # noqa: E402

MONTHS = [datetime.datetime(2026, m, 1) for m in (6, 7, 8)]


def _mm_workbook(path, months, spend, accounts, non_card, n_months=51, ltd=1_000_000.0, cur=28_000.0):
    wb = openpyxl.Workbook()
    ef = wb.active
    ef.title = "Executive Financials MM"
    ef.cell(4, 2, "Union Financial"); ef.cell(6, 2, "August 2026 Data")
    ef.cell(7, 4, n_months); ef.cell(8, 4, 25)
    for r, label, d, f in ((14, "Total Incremental Revenue", cur, ltd),
                           (15, "Incremental Profit", cur * 0.7, ltd * 0.7),
                           (16, "Total Costs", -cur * 0.3, -ltd * 0.3)):
        ef.cell(r, 3, label); ef.cell(r, 4, d); ef.cell(r, 6, f); ef.cell(r, 7, f)
    amr = wb.create_sheet("All Months Rollup MM")
    amr.cell(9, 3, "Total Incremental Income")
    kt = wb.create_sheet("Key Trends MM")
    for j, label in enumerate(("Total Spend (millions)", "Total Accounts (000)", "Non Card Holding Accounts (000)")):
        kt.cell(9 + j, 3, label)
    for i, m in enumerate(months):
        amr.cell(8, 4 + i, m); amr.cell(9, 4 + i, 30_000.0)
        kt.cell(8, 4 + i, m)
        for j, series in enumerate((spend, accounts, non_card)):
            if series[i] is not None:
                kt.cell(9 + j, 4 + i, series[i])
    mr = wb.create_sheet("Mail Response Summary MM")
    mr.cell(9, 2, months[-1]); mr.cell(9, 3, 0.017); mr.cell(9, 4, 0.135)
    dco = wb.create_sheet("DCO MM")
    dco.cell(10, 3, "Eligible ARS Accounts"); dco.cell(10, 4, 10309)
    wb.save(path)
    return str(path)


def _run(wb, out):
    return subprocess.run([sys.executable, os.path.join(ARS, "extract_base_gen.py"), wb, str(out)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=dict(os.environ, PYTHONIOENCODING="utf-8"))


def test_a_blank_month_is_none_never_zero(tmp_path):
    p = _mm_workbook(tmp_path / "wb.xlsx", MONTHS, [12.9, None, 13.0], [11.0, 11.2, None], [0.7, 0.7, 0.7])
    out = X.extract(openpyxl.load_workbook(p, read_only=True, data_only=True))
    assert out["swipespend_36"] == [("Jun 2026", 12.9, 10300), ("Jul 2026", None, 10500),
                                    ("Aug 2026", 13.0, None)]
    assert out["key_trends_blank"] == ["Jul 2026", "Aug 2026"]


def test_blank_months_stop_the_run_as_a_possible_data_issue(tmp_path):
    p = _mm_workbook(tmp_path / "1204-2026.09-X-Workbook.xlsx", MONTHS, [12.9, None, 13.0],
                     [11.0, 11.2, 11.3], [0.7, 0.7, 0.7])
    out = tmp_path / "base.json"
    r = _run(p, out)
    assert r.returncode != 0 and "Traceback" not in r.stderr
    assert "POSSIBLE DATA ISSUE" in r.stderr and "1204-2026.09-X-Workbook.xlsx" in r.stderr and "Jul 2026" in r.stderr
    assert not out.exists(), "no base.json is written from a workbook with a gap"


def test_an_uncalculated_mm_workbook_is_named_as_such(tmp_path):
    p = _mm_workbook(tmp_path / "wb.xlsx", [datetime.datetime(2007, 9, 1)], [None], [None], [None],
                     n_months=1, ltd=0, cur=0)
    r = _run(p, tmp_path / "base.json")
    assert r.returncode != 0 and "Traceback" not in r.stderr
    assert "UNEVALUATED WORKBOOK" in r.stderr


def test_a_populated_mm_workbook_still_extracts_with_its_dco(tmp_path):
    p = _mm_workbook(tmp_path / "wb.xlsx", MONTHS, [12.9, 13.1, 13.0], [11.0, 11.2, 11.3], [0.7, 0.7, 0.7])
    out = tmp_path / "base.json"
    r = _run(p, out)
    assert r.returncode == 0, r.stderr
    base = json.loads(out.read_text(encoding="utf-8"))
    assert [s for _, s, _ in base["swipespend_36"]] == [12.9, 13.1, 13.0]
    assert base["key_trends_blank"] == [] and base["dco_eligible"] == 10309
    # Full precision, not two decimals: rounding here and again at print time put 2.1 : 1 on
    # one True Sky slide and 2.2 : 1 on the next (2026-10-12).
    assert abs(base["profitability"] - 1_000_000.0 / 300_000.0) < 1e-9


def test_the_last_labelled_dco_row_wins_as_it_always_did(tmp_path):
    """The rewrite returned the FIRST 'Eligible ARS Accounts' row and moved 1542 from
    11,275 to 13,044. The module-scope loop it replaced kept scanning; so does this."""
    p = _mm_workbook(tmp_path / "wb.xlsx", MONTHS, [12.9, 13.1, 13.0], [11.0, 11.2, 11.3], [0.7, 0.7, 0.7])
    wb = openpyxl.load_workbook(p)
    wb["DCO MM"].cell(20, 3, "Eligible ARS Accounts"); wb["DCO MM"].cell(20, 4, 9876)
    wb.save(p)
    assert X.dco_eligible(openpyxl.load_workbook(p, read_only=True, data_only=True)) == 9876


def test_both_extractors_share_one_definition():
    import base_tab_extract as T
    assert T.key_trends is G.key_trends and X.key_trends is G.key_trends
    assert T.data_issue is G.data_issue and X.data_issue is G.data_issue
    for f in ("base_tab_extract.py", "extract_base_gen.py"):
        src = open(os.path.join(ARS, f), encoding="utf-8").read()
        assert "or 0,2)" not in src and ".get(m,0)" not in src, f + " still defaults a blank month"
