"""The client's deposits extract for the cut (build/ars_pipeline/ti/deposits_input.py).

A client only ever gets its own file (v5 at a491b5c gave 1776 the only file on disk, 1100's, and
joined 0%); the newest of its own files wins; the CSV is staged out of its zip once; a file that
parses to nothing is stated, never attached.
"""
import os
import zipfile

import pytest

from ti import deposits_input

CSV = ("hashed_account,deposit_date,deposit_amount\n"
       "AAA111,2026-01-05,1200.00\nAAA111,2026-02-05,1200.00\nBBB222,2026-01-20,300.50\n")


@pytest.fixture
def root(tmp_path, monkeypatch):
    for d in ("Inputs/Deposits", "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir(parents=True)
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("TI_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path


def _zip(root, name, body, when=(2026, 10, 5, 8, 0, 0)):
    p = root / "Inputs/Deposits" / f"{name}.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr(zipfile.ZipInfo(f"{name}.csv", date_time=when), body)
    return p


def test_only_the_clients_own_file_is_taken(root):
    _zip(root, "1100_RallyCU_ILSDeposits_2026.10", CSV)
    _zip(root, "11001_Other_ILSDeposits_2026.10", CSV)
    said = []
    cfg = deposits_input.attach({}, "1776", said.append)
    assert "_deposit_raw" not in cfg and "no file for client 1776" in said[0]
    assert [p.name for p in deposits_input.own_files("1100")] == ["1100_RallyCU_ILSDeposits_2026.10.zip"]


def test_the_file_is_mapped_staged_once_and_attached(root):
    z = _zip(root, "1615_CapeCod_ILSDeposits_2026.10", CSV)
    cfg = deposits_input.attach({"ClientID": "1615"}, "1615", lambda _m: None)
    raw = cfg["_deposit_raw"]
    assert len(raw) == 3 and set(raw["acct"]) == {"AAA111", "BBB222"}
    assert cfg["_deposit_source"] == z.name and "3 rows, 2 accounts" in cfg["_deposit_shape"]
    staged = deposits_input.stage(z, "1615")
    first = os.stat(staged).st_mtime
    assert deposits_input.stage(z, "1615") == staged and os.stat(staged).st_mtime == first


def test_the_newest_own_file_wins(root):
    old = _zip(root, "1615_CapeCod_ILSDeposits_2026.09", CSV)
    new = _zip(root, "1615_CapeCod_ILSDeposits_2026.10", CSV)
    os.utime(old, (1_700_000_000, 1_700_000_000))
    assert deposits_input.own_files("1615")[-1] == new


def test_a_file_that_parses_to_nothing_is_stated(root):
    _zip(root, "1615_CapeCod_ILSDeposits_2026.10", "who,what\n1,2\n")
    said = []
    cfg = deposits_input.attach({}, "1615", said.append)
    assert "_deposit_raw" not in cfg and any("parsed to 0 rows" in s for s in said)


def test_deposit_days_outside_the_window_are_left_out(root):
    import pandas as pd
    _zip(root, "1615_Test_ILSDeposits_2026.03", CSV)
    said = []
    cfg = deposits_input.attach({}, "1615", said.append,
                                bounds=(pd.Timestamp("2026-01-01"), pd.Timestamp("2026-02-01")))
    assert len(cfg["_deposit_raw"]) == 2                      # the two January days
    assert any("1 deposit row(s) outside Jan 2026 to Jan 2026 left out (1 after" in m for m in said)
