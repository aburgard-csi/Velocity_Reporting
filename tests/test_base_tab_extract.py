"""base_tab_extract — a blank Key Trends month is a possible data issue, not a crash or a zero.

1657 Marine Credit Union's 2026.09 workbook crashed the SM extractor at
`round(spend.get(m, 0), 2)`: a blank cell came back as None, not the default. The crash
came before the unevaluated-workbook guard, so the dashboard showed a traceback instead
of the real problem — the workbook was never calculated (Aaron, 2026-09-14: "that should
be called out as a possible data issue"). These build small synthetic workbooks; no
client data.
"""
import datetime
import json
import os
import subprocess
import sys

import openpyxl
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARS = os.path.join(REPO, "build", "ars_pipeline")
sys.path.insert(0, ARS)
import base_tab_extract as E  # noqa: E402


def _workbook(path, months, spend, accounts, non_card, n_months=96, ltd=1_000_000.0, cur=10_000.0):
    """The four base tabs the extractor reads, with Key Trends over `months`."""
    wb = openpyxl.Workbook()
    ef = wb.active
    ef.title = "Executive Financials"
    ef.cell(4, 2, "Union Financial")
    ef.cell(6, 2, "August 2026 Data")
    ef.cell(7, 4, n_months)
    ef.cell(8, 4, 12)
    for r, label, d, f in ((14, "Total Incremental Revenue", cur, ltd),
                           (15, "Incremental Profit", cur * 0.8, ltd * 0.8),
                           (16, "Total Costs", -cur * 0.2, -ltd * 0.2)):
        ef.cell(r, 3, label); ef.cell(r, 4, d); ef.cell(r, 6, f); ef.cell(r, 7, f)
    for title, labels in (("All Months Rollup", ("Total Interchange Revenue", "Total NSF Revenue")),
                          ("Key Trends", ("Total Spend (millions)", "Total Accounts (000)",
                                          "Non Card Holding Accounts (000)"))):
        ws = wb.create_sheet(title)
        for i, m in enumerate(months):
            ws.cell(8, 4 + i, m)
        for j, label in enumerate(labels):
            ws.cell(9 + j, 3, label)
    amr = wb["All Months Rollup"]
    for i in range(len(months)):
        amr.cell(9, 4 + i, 1000.0); amr.cell(10, 4 + i, 500.0)
    kt = wb["Key Trends"]
    for i in range(len(months)):
        for j, series in enumerate((spend, accounts, non_card)):
            if series[i] is not None:
                kt.cell(9 + j, 4 + i, series[i])
    mr = wb.create_sheet("Mail Response Summary")
    mr.cell(9, 2, months[-1]); mr.cell(9, 4, 0.03); mr.cell(9, 6, 0.15)
    wb.save(path)
    return str(path)


MONTHS = [datetime.datetime(2026, m, 1) for m in (6, 7, 8)]


def _run(path):
    return subprocess.run([sys.executable, os.path.join(ARS, "base_tab_extract.py"), path],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=dict(os.environ, PYTHONIOENCODING="utf-8"))


def test_a_blank_month_extracts_as_none_never_zero(tmp_path):
    p = _workbook(tmp_path / "wb.xlsx", MONTHS, [8.1, None, 8.4], [40.0, 41.0, None], [5.0, 5.0, 5.0])
    out = E.extract(openpyxl.load_workbook(p, read_only=True, data_only=True))
    assert out["swipespend_36"] == [("Jun 2026", 8.1, 35000), ("Jul 2026", None, 36000),
                                    ("Aug 2026", 8.4, None)]
    assert out["key_trends_blank"] == ["Jul 2026", "Aug 2026"]


def test_blank_months_are_called_out_as_a_possible_data_issue(tmp_path):
    p = _workbook(tmp_path / "1657-2026.09-X-Workbook.xlsx", MONTHS, [8.1, None, 8.4],
                  [40.0, 41.0, 42.0], [5.0, 5.0, 5.0])
    r = _run(p)
    assert r.returncode != 0
    assert "Traceback" not in r.stderr, "a data gap must not surface as a crash"
    assert "POSSIBLE DATA ISSUE" in r.stderr
    assert "1657-2026.09-X-Workbook.xlsx" in r.stderr and "Jul 2026" in r.stderr
    assert r.stdout.strip() == "", "nothing is extracted from a workbook with a gap"


def test_an_uncalculated_template_is_named_as_such_not_a_crash(tmp_path):
    """1657's actual shape: one month, Sep 2007 (the template's date), every cell blank."""
    p = _workbook(tmp_path / "1657-2026.09-Marine Credit Union-Workbook_v2_1_0.xlsx",
                  [datetime.datetime(2007, 9, 1)], [None], [None], [None], n_months=1, ltd=0, cur=0)
    r = _run(p)
    assert r.returncode != 0
    assert "Traceback" not in r.stderr
    assert "UNEVALUATED WORKBOOK" in r.stderr and "Excel" in r.stderr


def test_a_populated_workbook_still_extracts(tmp_path):
    p = _workbook(tmp_path / "wb.xlsx", MONTHS, [8.1, 8.2, 8.4], [40.0, 41.0, 42.0], [5.0, 5.0, 5.0])
    r = _run(p)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["key_trends_blank"] == []
    assert [s for _, s, _ in out["swipespend_36"]] == [8.1, 8.2, 8.4]
    assert out["profitability"] == 5.0


def test_importing_does_not_run_the_extractor():
    """Import-safe, so extract() is testable — the hazard CLAUDE.md names for metrics_gen."""
    assert callable(E.extract) and callable(E.main) and callable(E.data_issue)
