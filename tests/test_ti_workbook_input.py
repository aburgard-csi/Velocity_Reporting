"""The client's ARS Workbook for the cut (build/ars_pipeline/ti/workbook_input.py).

Found in RPE's inputs the way the ARS build finds it (never the Invitation Checking workbook); read
with v5's reader; and, as v5's run did, its current Interchange Rate and NSF Fee fill a client
config that leaves them blank, while a config value that disagrees wins and is said.
"""
import pytest

from ti import workbook_input
from test_ti_workbook import _make_wb


@pytest.fixture
def root(tmp_path, monkeypatch):
    for d in ("Inputs/ARS Workbooks", "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir(parents=True)
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    return tmp_path


def test_the_ars_workbook_is_found_never_the_invitation_checking_one(root):
    d = root / "Inputs/ARS Workbooks"
    _make_wb(d / "1776-2026.10-CoastHills CU-Invitation Checking Workbook v1.7.1.xlsx")
    _make_wb(d / "1776-2026.10-CoastHills CU-Workbook_v2_1_0.xlsx")
    _make_wb(d / "1776-2026.09-CoastHills CU-Workbook_v2_1_0.xlsx")
    assert workbook_input.find("1776", "2026.10").name == "1776-2026.10-CoastHills CU-Workbook_v2_1_0.xlsx"
    assert workbook_input.find("1776", "2026.08") is None


def test_blank_rates_are_filled_from_the_workbook_and_set_ones_win(root):
    _make_wb(root / "Inputs/ARS Workbooks" / "1776-2026.10-CoastHills CU-Workbook_v2_1_0.xlsx")
    said = []
    cfg, wb = workbook_input.attach({"NSF_OD_Fee": "35"}, "1776", "2026.10", said.append)
    assert wb["wb_found"] == "1776-2026.10-CoastHills CU-Workbook_v2_1_0.xlsx"
    assert wb["wb_ic_rate"] == 0.0065 and cfg["ICRate"] == "0.0065"
    assert cfg["NSF_OD_Fee"] == "35", "a set config value wins"
    assert any("NSF_OD_Fee mismatch" in s for s in said)


def test_no_workbook_is_stated_and_changes_nothing(root):
    said = []
    cfg, wb = workbook_input.attach({"ICRate": ""}, "1776", "2026.10", said.append)
    assert wb == {} and cfg == {"ICRate": ""}
    assert "no ARS Workbook in Inputs for 1776 2026.10" in said[0]
