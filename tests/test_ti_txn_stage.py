"""Staging the zipped transaction files for v5's loader (build/ars_pipeline/ti/txn_stage.py).

Only files inside the window are copied out; a second build copies nothing (the share is read
once per file); the staged copy carries the zip entry's own date, so the loader's parquet cache
key is stable; a file that leaves the window leaves staging; the share copy is never touched.
"""
import zipfile

import pandas as pd
import pytest

from ti import txn_stage

BANNER = "Monthly Transaction File|1100|2026-08-05\n"
ROW = "2026-07-{d:02d}\tACCT{a}\tSIG\t-12.50\tSTORE {a}\t5411\tM1\tY\t\t\t\t\n"


def _zip(folder, name, body, when=(2026, 8, 5, 7, 16, 16)):
    z = folder / f"{name}.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr(zipfile.ZipInfo(name, date_time=when), body)
    return z


@pytest.fixture
def root(tmp_path, monkeypatch):
    for d in ("Inputs/Txn Files/1100", "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir(parents=True)
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("TI_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path


def test_only_the_window_is_staged_once_with_the_entry_date(root):
    src = root / "Inputs/Txn Files/1100"
    body = BANNER + "".join(ROW.format(d=d, a=d) for d in range(1, 6))
    _zip(src, "1100_31004_[2026.08.05][07.16.16]_monthly_transactions_file.txt", body)
    _zip(src, "1100_31004_[2025.01.05][07.16.16]_monthly_transactions_file.txt", body, (2025, 1, 5, 0, 0, 0))
    _zip(src, "1100_ILSDeposits_2026.08.txt", body)
    said = []
    anchor = pd.Timestamp("2026-07-31")
    d = txn_stage.stage("1100", 12, anchor, said.append)
    staged = sorted(p.name for p in d.iterdir())
    assert staged == ["1100_31004_[2026.08.05][07.16.16]_monthly_transactions_file.txt"]
    assert len(said) == 1
    f = d / staged[0]
    assert pd.Timestamp(f.stat().st_mtime, unit="s").year == 2026
    txn_stage.stage("1100", 12, anchor, said.append)
    assert len(said) == 1, "a second build reads nothing from the share"
    assert sorted(p.name for p in src.iterdir())[0].endswith(".zip"), "the share copy is untouched"


def test_a_file_that_leaves_the_window_leaves_staging(root):
    src = root / "Inputs/Txn Files/1100"
    body = BANNER + ROW.format(d=1, a=1)
    _zip(src, "1100_31004_[2026.08.05][07.16.16]_monthly_transactions_file.txt", body)
    txn_stage.stage("1100", 12, pd.Timestamp("2026-07-31"), lambda _m: None)
    d = txn_stage.stage("1100", 12, pd.Timestamp("2027-12-31"), lambda _m: None)
    assert list(d.iterdir()) == []
