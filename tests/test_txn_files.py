"""Transaction files are stored zipped and read through rpe_env (Aaron, 2026-09-17).

`Inputs/Txn Files/<id>/` held about 48 GB of raw text read over the share. Each file is now
`<name>.zip` beside where it was; `rpe_env.txn_files` / `open_txn` read either form, so a
reader never has to know which one it got.
"""
import os
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build"), str(REPO / "scripts")]
import rpe_env as R  # noqa: E402
import zip_txn_files as Z  # noqa: E402

BODY = b"acct,date,amount\r\n" + b"".join(b"%d,2026-08-%02d,%d.25\r\n" % (i, i % 28 + 1, i) for i in range(5000))


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "Txn Files"
    (r / "1441" / "2026" / "output_txn").mkdir(parents=True)
    (r / "1441" / "1441_16286_[2026.09.02][16.59.26]_debit card transaction monthly.csv").write_bytes(BODY)
    (r / "1562").mkdir()
    (r / "1562" / "1562_19776_[2026.09.01][09.52.33]_velocity.ars.transactions").write_bytes(BODY[:900])
    (r / "1441" / "2026" / "output_txn" / "1441_TXN_Analysis.xlsx").write_bytes(b"not a txn file")
    (r / "1100").mkdir()
    (r / "1100" / "1100_507_combined.txt").write_bytes(b"")
    old = 1_756_000_000
    for p in r.rglob("*"):
        if p.is_file():
            os.utime(p, (old, old))
    return r


def test_txn_is_a_kind_the_watcher_never_scans():
    assert R.INPUT_KIND_DIRS["Txn"] == "Txn Files"
    assert "Txn" in R.NOT_SCANNED_KINDS


def test_plan_skips_analysis_output_and_empty_files(root):
    names = sorted(p.name for p in Z.plan(root))
    assert names == ["1441_16286_[2026.09.02][16.59.26]_debit card transaction monthly.csv",
                     "1562_19776_[2026.09.01][09.52.33]_velocity.ars.transactions"]
    assert [p.name for p in Z.plan(root, {"1562"})] == [names[1]]


def test_zipping_replaces_the_original_with_a_verified_zip(root):
    src = next(p for p in Z.plan(root) if p.suffix == ".csv")
    mtime = src.stat().st_mtime
    r = Z.zip_one(src)
    assert r["status"] == "zipped", r
    z = src.with_name(src.name + ".zip")
    assert not src.exists() and z.is_file()
    assert not src.with_name(src.name + ".zip.part").exists()
    assert z.stat().st_mtime == mtime
    assert r["zip_size"] < r["size"]
    with zipfile.ZipFile(z) as zf:
        assert zf.namelist() == [src.name] and zf.read(src.name) == BODY


def test_a_rerun_finds_nothing_left(root):
    for p in Z.plan(root):
        assert Z.zip_one(p)["status"] == "zipped"
    assert Z.plan(root) == []
    assert Z.main(["--root", str(root)]) == 0


def test_an_interrupted_run_is_finished_not_rewritten(root):
    src = next(p for p in Z.plan(root) if p.suffix == ".csv")
    Z.zip_one(src)
    z = src.with_name(src.name + ".zip")
    src.write_bytes(BODY)                       # the original came back beside its zip
    os.utime(src, (1_756_000_000, 1_756_000_000))
    stamp = z.stat().st_mtime_ns
    assert Z.plan(root) and src in Z.plan(root)
    assert Z.zip_one(src)["status"] == "zipped"
    assert not src.exists() and z.stat().st_mtime_ns == stamp


def test_a_zip_that_does_not_match_its_original_keeps_the_original(root):
    src = next(p for p in Z.plan(root) if p.suffix == ".csv")
    z = src.with_name(src.name + ".zip")
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr(src.name, BODY[:-10])
    r = Z.zip_one(src)
    assert r["status"] == "FAILED" and src.read_bytes() == BODY


def test_an_emptied_zip_is_reported_and_the_original_kept(root, monkeypatch):
    """The CSI share emptied four of 404 zips as they were closed (2026-09-17). Every byte
    reached the handle; the file was 0 bytes the moment it was closed. The file stays raw."""
    src = next(p for p in Z.plan(root) if p.suffix == ".csv")
    real = os.path.getsize
    monkeypatch.setattr(Z.os.path, "getsize", lambda p: 0 if str(p).endswith(".part") else real(p))
    r = Z.zip_one(src)
    assert r["status"] == "FAILED" and "discarded the archive" in r["error"]
    assert src.read_bytes() == BODY and not src.with_name(src.name + ".zip").exists()


def test_open_txn_reads_either_form_the_same(root):
    raw = root / "1562" / "1562_19776_[2026.09.01][09.52.33]_velocity.ars.transactions"
    with R.open_txn(raw) as fh:
        before = fh.read()
    with R.open_txn(raw, "r") as fh:
        text = fh.read()
    Z.zip_one(raw)
    assert not raw.exists()
    with R.open_txn(raw) as fh:                  # the pre-zip name still opens
        assert fh.read() == before
    with R.open_txn(raw.with_name(raw.name + ".zip"), "r") as fh:
        assert fh.read() == text
    assert "\r\n" in text                        # newlines untranslated, as the csv module wants


def test_txn_files_lists_one_entry_per_file(root):
    before = R.txn_files(root=root)
    for p in Z.plan(root):
        Z.zip_one(p)
    after = R.txn_files(root=root)
    assert len(before) == len(after) == 2
    assert all(p.suffix == ".zip" for p in after)
    assert [p.name for p in R.txn_files("1562", root=root)] == [
        "1562_19776_[2026.09.01][09.52.33]_velocity.ars.transactions.zip"]
    assert R.txn_files("9999", root=root) == []


def test_open_txn_refuses_writes_and_multi_member_zips(tmp_path):
    with pytest.raises(ValueError):
        R.open_txn(tmp_path / "x.csv", "w")
    z = tmp_path / "two.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.csv", "1")
        zf.writestr("b.csv", "2")
    with pytest.raises(ValueError):
        R.open_txn(z)
