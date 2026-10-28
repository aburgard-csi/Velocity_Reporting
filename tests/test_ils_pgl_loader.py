"""The ILS pre-go-live extract (build/ils_pipeline/pgl_input.py, pre_go_live/loader.py).

v5's loader tests (v5 tests/test_pgl_setup.py, the loader block) on the RPE input folder
`Inputs/ILS PGL/<id>/`, plus the RPE-side lookup: one folder per client, never scanned.
"""
import pandas as pd
import pytest

import rpe_env
from ils_pipeline import pgl_input
from ils_pipeline.pre_go_live import loader

CSV_HEADER = ("AcctNo,Personal_Business,Eligible_For_Scoring,OD Status Code (from Core),"
              "Initial OD Limit (from Core),OD Limit (from ILS),Account Status Code,"
              "Reg-E Opt-In Value,Open Date,Last Update,UpOrDown from Initial OD Limit,"
              "Rolling 12 Month NSFOD Items,Rolling 12 Month NSFOD Fees,"
              "Deposit Count Last 33 days,Deleted")

ROWS = [
    # acct, seg, elig, od_code, init_limit, ils_limit, status, rege, open, update, updown, items, fees, depcnt, deleted
    "001,PERSONAL,NULL,003,600,700,O,Y,7/16/2021,8/6/2026,Score100Plus,3,81,5,NULL",
    "002,PERSONAL,NULL,003,600,0,O,N,1/2/2020,8/6/2026,ScoreLess100,0,0,2,NULL",
    "003,PERSONAL,NULL,005,0,400,O,,3/4/2019,8/6/2026,Same,12,324,0,NULL",
    "004,BUSINESS,NULL,000,600,600,O,N,5/6/2018,8/6/2026,Same,1,27,9,NULL",
    "005,PERSONAL,NULL,003,600.0,NULL,C,Y,9/9/2017,8/6/2026,Unknown,NULL,NULL,1,8/1/2026",
    "006,PERSONAL,NULL,000,0,0,O,Y,2/2/2022,8/6/2026,Same,2,54,3,NULL",
]


def write_extract(root, name, rows=None):
    d = root / "Inputs" / "ILS PGL" / "1737"
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text("﻿" + CSV_HEADER + "\n" + "\n".join(rows or ROWS) + "\n", encoding="utf-8")
    return p


@pytest.fixture
def root(tmp_path, monkeypatch):
    for d in ("Inputs", "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir(parents=True)
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    write_extract(tmp_path, "1737_TxNat_PreGL_20260705.csv", ROWS[:2])   # older, fewer rows
    write_extract(tmp_path, "1737_TxNat_PreGL_20260807.csv")
    return tmp_path


# ---- v5's loader tests ------------------------------------------------------

def test_loader_picks_newest_by_filename_date(root):
    found = pgl_input.find_extract("1737")
    assert found.path.name == "1737_TxNat_PreGL_20260807.csv"
    assert found.date.strftime("%Y%m%d") == "20260807"
    assert [p.name for p in found.others] == ["1737_TxNat_PreGL_20260705.csv"]


def test_loader_standardizes_types(root):
    df, warns = loader.load(pgl_input.find_extract("1737").path)
    assert list(df["OD Status Code (from Core)"][:2]) == ["003", "003"]   # leading zeros survive
    assert df["Initial OD Limit (from Core)"].dtype.kind == "f"
    assert pd.isna(df["OD Limit (from ILS)"]).iloc[4]                      # literal NULL -> NaN
    assert df["Open Date"].dtype.kind == "M"
    assert pd.isna(df["Reg-E Opt-In Value"]).iloc[2]                       # blank -> NA
    assert df["AcctNo"].iloc[4] == "005"
    assert any("15 columns found" in w for w in warns)                     # short of 1737's 42, stated


def test_loader_missing_folder(root):
    with pytest.raises(FileNotFoundError, match="ILS PGL"):
        pgl_input.find_extract("9999")


# ---- RPE side -----------------------------------------------------------------

def test_a_client_reads_only_its_own_folder(root):
    write_extract(root, "1737_TxNat_PreGL_20260807.csv")
    other = root / "Inputs" / "ILS PGL" / "17370"
    other.mkdir()
    (other / "17370_Other_PreGL_20991231.csv").write_text(CSV_HEADER + "\n", encoding="utf-8")
    assert pgl_input.find_extract("1737").path.parent.name == "1737"


def test_the_folder_is_never_scanned_or_created(root):
    assert "ILS PGL" in rpe_env.NOT_SCANNED_KINDS
    assert "ILS PGL" not in rpe_env._scanned_dirnames()
    pgl_input.folder("4242")
    assert not (root / "Inputs" / "ILS PGL" / "4242").exists()
