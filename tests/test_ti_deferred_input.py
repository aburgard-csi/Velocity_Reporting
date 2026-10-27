"""The client's 2:1 deferral tracker for the cut (build/ars_pipeline/ti/deferred_input.py).

Found in Inputs/Deferred Billing by the client id as a whole number, wherever it sits in the name
(some names lead with a revision date), never by another id that contains it; read with v5's reader;
and checked the way v5's run checked it: a missing tracker, a stale one, the guarantee's state and a
tracker that disagrees with the workbook are all said, never passed silently.
"""
import pytest

from ti import deferred_input
from test_ti_guarantee import GOOD, _tracker


@pytest.fixture
def folder(tmp_path, monkeypatch):
    for d in ("Inputs/Deferred Billing", "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir(parents=True)
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    return tmp_path / "Inputs/Deferred Billing"


def test_the_client_id_is_matched_whole_wherever_it_sits(folder):
    _tracker(folder / "020525 Revised 1453 Connex Credit Union Deferred expense tracking.xlsx", GOOD)
    _tracker(folder / "14530 Other Deferred expense tracking.xlsx", GOOD)
    _tracker(folder / "~$1453 Connex Deferred expense tracking.xlsx", GOOD)
    assert deferred_input.find("1453").name.startswith("020525 Revised 1453 Connex")
    assert deferred_input.find("1776") is None


def test_a_missing_tracker_is_said_and_adds_nothing(folder):
    said = []
    assert deferred_input.attach("1776", said.append) == {}
    assert "no 2:1 guarantee deferral tracker in Inputs/Deferred Billing for 1776" in said[0]


def test_a_tracker_is_read_and_its_state_and_staleness_are_said(folder):
    _tracker(folder / "1441 FNB Alaska ARS Deferred expense tracking.xlsx", GOOD)
    said = []
    gt = deferred_input.attach("1441", said.append)
    assert gt["gt_latest_month"] == "2025-10" and gt["gt_state"] != "clear"
    deferred_input.review(gt, {}, "2026-04", said.append)
    assert any("6 months behind the data" in s for s in said), said
    assert any("deferred through 2025-10" in s for s in said), said


def test_a_month_the_workbook_disagrees_on_is_said(folder):
    _tracker(folder / "1441 FNB Alaska ARS Deferred expense tracking.xlsx", GOOD)
    gt = deferred_input.attach("1441", lambda _m: None)
    said = []
    deferred_input.review(gt, {"wb_monthly": [["2025-09", 25000.0], ["2025-10", 14100.0]]}, "2025-10", said.append)
    rec = [s for s in said if s.startswith("guarantee reconciliation")]
    assert len(rec) == 1 and "2025-09" in rec[0], rec
