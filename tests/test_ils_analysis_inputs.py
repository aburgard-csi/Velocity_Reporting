"""ils_analysis_inputs: the naming convention for Inputs/ILS Analysis (Aaron, 2026-11-06).

A file goes to <id>/<yyyymmdd>/ and an extract is renamed <id>_<kind>_<yyyymmdd>.<ext> with a kind the ILS Program Analysis
builder finds; anything else sits under analysis/ with its name; nothing is overwritten; every move can be undone.
"""
import calendar
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "build"))
import ils_analysis_inputs as A                                  # noqa: E402

S = os.sep


@pytest.mark.parametrize("name,kind", [
    ("adjustments_20250924.csv", "adjustments"), ("Adjustments_20250924.csv", "adjustments"),
    ("Adjustment_20240101.csv", "adjustments"), ("adjustments.csv", "adjustments"),
    ("DataOps_20260810.csv", "dataops"), ("Data_Ops_20230101.csv", "dataops"), ("Dataops_20230101.csv", "dataops"),
    ("Data Ops Z Trend_20230101.csv", "ztrend"), ("1720_ztrend_20250101.csv", "ztrend"), ("zTrend_20250101.csv", "ztrend"),
    ("RefundHistory_20250101.csv", "refundhistory"), ("Z_Trend Pull Refund_20230101.csv", "refundhistory"),
    ("Refunds_20230101.csv", "refundhistory"), ("Refund_History_20230101.csv", "refundhistory"),
    ("debitdeclines_20250101.csv", "debitdeclines"), ("DebitDecline_20250606.csv", "debitdeclines"),
    ("debit_declines.csv", "debitdeclines"), ("1670_zaccounts_20261012.csv", "zaccounts"),
    ("1670_matrixval_20261012.txt", "matrixval"), ("1670_dbic_20261012.txt", "dbic"),
    ("cashpleaseloans_20230101.csv", "cashpleaseloans"), ("CPLoans.csv", "cashpleaseloans"),
    ("Pull_Loan_History_20230101.csv", "loanhistory"), ("branches.csv", "branches"), ("account_types.csv", "account_types"),
    ("returned_deposits.csv", "returned_deposits"),
])
def test_an_extract_name_reads_as_its_kind(name, kind):
    assert A.kind_of(name) == kind


@pytest.mark.parametrize("name", [
    "00_MASTER_ANALYSIS.xlsx", "204_Pcomp3.csv", "300_branch_report.csv", "c01.csv", "c01_XLS.xlsx",
    "Z-ACCOUNTS_PIVOT.xlsx", "Channel Data Analysis.xlsx", "Peer_FDIC.xlsx", "adjustments.xlsx", "Greylock .csv",
    "ILS and DS Client Review Summary.xlsx", "code_summary_ 1 .xlsx",
])
def test_anything_else_is_an_analysis_file(name):
    assert A.kind_of(name) is None


def test_every_kind_the_builder_finds_is_an_extract_kind():
    for k in ("zaccounts", "ztrend", "matrixval", "dbic", "debitdeclines", "refundhistory"):
        assert k in A.EXTRACT_KINDS


@pytest.mark.parametrize("text,ymd", [("DataPull_20260810", "20260810"), ("DataPull_2024.9.18", "20240918"),
                                      ("Data Pull 2017-07-13", "20170713"), ("2015_09_21 HillsBank", "20150921"),
                                      ("DataPull_202209", None), ("1245-2026.04-ILS-Data Pull", None), ("Standard", None)])
def test_dates(text, ymd):
    assert A.date_in(text) == ymd


def _touch(p, mtime=None):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x")
    if mtime:
        os.utime(p, (mtime, mtime))


def _tree(root):
    c = root / "1670"
    _touch(c / "DataPull_20260810" / "adjustments_20260810.csv")
    _touch(c / "DataPull_20260810" / "RefundHistory_20260810.csv")
    _touch(c / "DataPull_20260810" / "00_MASTER_ANALYSIS.xlsx")
    _touch(c / "DataPull_20250924" / "DataPull_20250924" / "Adjustments_20250924.csv")
    _touch(c / "DataPull_20250924" / "DataPull_20250924" / "PEER" / "p01.csv")
    _touch(c / "Standard" / "notes.txt")
    return c


def test_the_plan_puts_each_file_under_its_pull_and_names_extracts_by_the_convention(tmp_path):
    c = _tree(tmp_path)
    got = {str(m[0].relative_to(c)): str(m[1].relative_to(c)) for m in A.plan_client("1670", c)}
    assert got[S.join(["DataPull_20260810", "adjustments_20260810.csv"])] == S.join(["20260810", "1670_adjustments_20260810.csv"])
    assert got[S.join(["DataPull_20260810", "RefundHistory_20260810.csv"])] == S.join(["20260810", "1670_refundhistory_20260810.csv"])
    assert got[S.join(["DataPull_20260810", "00_MASTER_ANALYSIS.xlsx"])] == S.join(["20260810", "analysis", "00_MASTER_ANALYSIS.xlsx"])
    # a folder named twice is said once, and a subfolder is kept under analysis/
    assert got[S.join(["DataPull_20250924", "DataPull_20250924", "Adjustments_20250924.csv"])] == S.join(["20250924", "1670_adjustments_20250924.csv"])
    assert got[S.join(["DataPull_20250924", "DataPull_20250924", "PEER", "p01.csv"])] == S.join(["20250924", "analysis", "PEER", "p01.csv"])
    # a folder with no date is set aside, not guessed at
    assert got[S.join(["Standard", "notes.txt"])] == S.join(["_unplaced", "Standard", "notes.txt"])


def test_a_month_only_folder_keeps_the_month_and_is_not_given_a_day(tmp_path):
    c = tmp_path / "1111"
    _touch(c / "DataPull_202209" / "300_branch_report.csv")
    _touch(c / "2015_08 Redwood" / "adjustments.csv")
    got = {m[0].relative_to(c).parts[0]: m[1].relative_to(c).parts for m in A.plan_client("1111", c)}
    assert got["DataPull_202209"] == ("202209", "analysis", "300_branch_report.csv")
    assert got["2015_08 Redwood"] == ("201508", "1111_adjustments_201508.csv")
    assert A._is_pull_name("202209") and A._is_pull_name("20220930") and not A._is_pull_name("201522")


def test_a_folder_that_names_no_date_is_set_aside_not_guessed_at(tmp_path):
    c = tmp_path / "2222"
    _touch(c / "Standard" / "x.csv")
    (m,) = A.plan_client("2222", c)
    assert m[1].relative_to(c).parts[0] == "_unplaced"


def test_apply_moves_writes_an_undo_list_and_undo_restores(tmp_path):
    root = tmp_path / "ILS Analysis"
    c = _tree(root)
    rows = A.plan(root)
    manifest = A.write_manifest(rows, tmp_path / "m")
    A.apply(rows, say=lambda *_: None)
    assert (c / "20260810" / "1670_adjustments_20260810.csv").is_file()
    assert not (c / "DataPull_20260810").exists()                                           # emptied, so removed
    assert [r for r in A.plan(root) if r[2] is not None] == []                              # idempotent
    A.undo(manifest, say=lambda *_: None)
    assert (c / "DataPull_20260810" / "adjustments_20260810.csv").is_file()
    assert not (c / "20260810").exists()


def test_nothing_is_overwritten(tmp_path):
    c = tmp_path / "1670"
    _touch(c / "DataPull_20260810" / "adjustments_20260810.csv")
    _touch(c / "20260810" / "1670_adjustments_20260810.csv")
    rows = A.plan(tmp_path)
    assert any(r[2] is None and "already exists" in r[3] for r in rows)
    A.apply(rows, say=lambda *_: None)
    assert (c / "DataPull_20260810" / "adjustments_20260810.csv").is_file()


def test_two_files_that_would_land_on_one_name_are_not_moved_over_each_other(tmp_path):
    c = tmp_path / "1670"
    _touch(c / "DataPull_20260810" / "adjustments_20260810.csv")
    _touch(c / "DataPull_2026.8.10" / "Adjustments_20260810.csv")
    rows = A.plan(tmp_path)
    assert sum(1 for r in rows if r[2] is not None) == 1 and sum(1 for r in rows if r[2] is None) == 1


def test_a_month_folder_holding_one_dated_pull_takes_that_day(tmp_path):
    c = tmp_path / "1191"
    _touch(c / "DataPull_202304" / "DataPull_20230413" / "DataPull_20230413" / "ZAccounts.Trends_QuerySeparated" / "branches.csv")
    (m,) = A.plan_client("1191", c)
    assert m[1].relative_to(c).parts == ("20230413", "1191_branches_20230413.csv")


def test_a_file_already_under_a_pulls_analysis_folder_stays_an_analysis_file(tmp_path):
    c = tmp_path / "1531"
    _touch(c / "20260728" / "analysis" / "data_formatted" / "adjustments.csv")
    assert A.plan_client("1531", c) == []
