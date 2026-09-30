"""The 2:1 guarantee deferral tracker reaches the engine (2026-09-30).

James's rule (v5 issues #42/#43): when the tracker exists its math IS the client's economics;
when it does not, the workbook's billed figures stand and the run says so. The reader was
ported on 2026-09-18 but nothing called it, and Inputs had no folder for the file, so no
gt_* figure was ever produced on the branch.
"""
import datetime as dt
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build" / "ars_pipeline"), str(REPO / "build")]
import rpe_env  # noqa: E402
import run_analysis as RA  # noqa: E402


def _tracker(path, months=3):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["1441 FNB Alaska - 2:1 Guarantee Deferral Tracker"])
    ws.append(["Month", "Revenue", "Charges", "Paid", "Deferred", "Running balance"])
    running = 0.0
    for k in range(months):
        rev, charges = 10000.0, 6000.0
        paid = rev / 2          # half of revenue: the guarantee math
        deferred = charges - paid
        running += deferred
        ws.append([dt.date(2026, 1 + k, 1), rev, charges, paid, deferred, running])
    wb.save(path)
    return path


def test_the_input_kind_exists_and_the_workbook_scanner_leaves_it_alone():
    assert rpe_env.INPUT_KIND_DIRS["Guarantee"] == "Guarantee Trackers"
    assert "Guarantee" in rpe_env.NOT_SCANNED_KINDS


def test_find_tracker_takes_the_newest_name_and_ignores_excel_lock_stubs(tmp_path):
    (tmp_path / "1441 Deferred 2026-07.xlsx").write_bytes(b"x")
    (tmp_path / "1441 Deferred 2026-08.xlsx").write_bytes(b"x")
    (tmp_path / "~$1441 Deferred 2026-09.xlsx").write_bytes(b"x")
    (tmp_path / "1615 Deferred 2026-09.xlsx").write_bytes(b"x")
    assert RA.find_tracker("1441", root=tmp_path).name == "1441 Deferred 2026-08.xlsx"
    assert RA.find_tracker("9999", root=tmp_path) is None
    assert RA.find_tracker("1441", root=tmp_path / "missing") is None


def test_a_present_tracker_puts_gt_figures_in_the_metrics(odd_csv, tmp_path):
    pytest.importorskip("pandas")
    trk = _tracker(tmp_path / "1441 Deferred.xlsx")
    r = RA.run(odd_csv, "1441", "2026.08", out_dir=tmp_path / "out", txn=False, tables=None, tracker=trk)
    m = r.metrics
    assert m["gt_months_n"] == 3 and m["gt_deferred_balance"] == pytest.approx(3000.0)
    assert m["gt_state"] and m["gt_latest_month"] == "2026-03"
    assert not [w for w in r.warnings if "deferral tracker" in w and "!=" in w], r.warnings


def test_an_absent_tracker_is_said_and_no_gt_figure_is_invented(odd_csv, tmp_path, monkeypatch):
    pytest.importorskip("pandas")
    monkeypatch.setattr(RA, "find_tracker", lambda cid, root=None: None)
    r = RA.run(odd_csv, "1441", "2026.08", out_dir=tmp_path / "out", txn=False, tables=None)
    assert not [k for k in r.metrics if k.startswith("gt_")]
    assert any("no 2:1 guarantee deferral tracker" in w for w in r.warnings)
