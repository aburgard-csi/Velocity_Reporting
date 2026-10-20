"""land_txn_files — the transaction members of the CSM folders' ODD extracts land in
Inputs/Txn Files/<id>/ as one zip per file (James, issue #23; Aaron, 2026-10-20).

The ODD member is never landed, a file on hand is never landed twice, a copy at another size
is reported and left alone, and the source extract is never touched.
"""
import os
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build"))
import land_txn_files as L                                       # noqa: E402
import rpe_env as R                                              # noqa: E402

ODD = "1001-2026-10-Union Financial-ODD  (Oct23 forward) (100126_120000)_V2_1_1.csv"
TXN = "1001_55_[2026.10.01][08.00.00]_monthlytran.csv"
ODD2 = "1002-2026-10-Second Bank-ODD  (Oct23 forward) (100226_090000)_V2_1_1.csv"
TXN2 = "1002_77_[2026.10.02][09.00.00]_debit_card_trans-09302026.txt"
MASTER = "1001_56_[2026.10.01][08.00.00]_monthly_account_data.csv"
# the data team's banner line, as the exports carry it; 1001's transaction file has one,
# 1002's (a hand-combined file) has none
BODY = (b"1001|10/1/2026 8:00:00 AM|September 2026|55|Monthly Transaction File -- ARS|6.0.6.0\n"
        b"acct,amt\n" + b"1,2.50\n" * 4000)
RAW2 = b"acct,amt\n" + b"2,3.00\n" * 8000              # 1002: no banner line
MASTER_BODY = (b"1001|10/1/2026 8:00:00 AM|September 2026|56|Monthly Account Data - Master File|6.0.6.0\n"
               b"acct,name\n1,A\n")


@pytest.fixture
def share(tmp_path):
    """One CSM root with an October folder: 1001's zipped extract (ODD + transaction member,
    plus an empty member) and 1002's unzipped folder (ODD csv + transaction txt)."""
    root = tmp_path / "share" / "Aburgard" / "ODDD"
    month = root / "2026.10 Oct"
    month.mkdir(parents=True)
    with zipfile.ZipFile(month / "1001_ODDD.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(ODD, "acct,elig\n1,Y\n")
        z.writestr(TXN, BODY)
        z.writestr(MASTER, MASTER_BODY)
        z.writestr("1001_55_empty.csv", b"")
    d = month / "1002_ODDD"
    d.mkdir()
    (d / ODD2).write_text("acct,elig\n2,Y\n")
    (d / TXN2).write_bytes(RAW2)
    (d / "1002_77_half.txt.part").write_bytes(b"x")
    return f"Aaron Burgard={root}"


def test_the_transaction_members_land_and_the_odd_member_does_not(share, tmp_path):
    dest = tmp_path / "Txn Files"
    rc = L.main(["--source", share, "--root", str(dest), "--since", "2026.10",
                 "--log", str(tmp_path / "log.json")])
    assert rc == 0
    landed = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*.zip"))
    assert landed == [f"1001/{TXN}.zip", f"1002/{TXN2}.zip"]
    with zipfile.ZipFile(dest / "1001" / (TXN + ".zip")) as z:
        assert z.namelist() == [TXN]
        assert z.read(TXN) == BODY
    with zipfile.ZipFile(dest / "1002" / (TXN2 + ".zip")) as z:
        assert z.read(TXN2) == RAW2
    # the readers see them, and nothing else
    assert [p.name for p in R.txn_files(root=dest)] == [TXN + ".zip", TXN2 + ".zip"]
    # the source extract is whole
    month = Path(share.split("=", 1)[1]) / "2026.10 Oct"
    with zipfile.ZipFile(month / "1001_ODDD.zip") as z:
        assert sorted(z.namelist()) == sorted([ODD, TXN, MASTER, "1001_55_empty.csv"])
    assert (month / "1002_ODDD" / TXN2).is_file()


def test_a_member_whose_banner_is_not_a_transaction_file_is_reported_not_landed(share, tmp_path, capsys):
    """1121's September extract carried its DDA master file beside the ODD (2026-10-20)."""
    rows = L.sources("2026.10", share)
    types = {r["name"]: r["ftype"] for r in rows}
    assert types[TXN] == "Monthly Transaction File -- ARS"
    assert types[MASTER] == "Monthly Account Data - Master File"
    assert types[TXN2] is None                      # no banner: the folder rule stands
    wanted, skipped = L.plan(rows, tmp_path / "Txn Files")
    assert MASTER not in [r["name"] for r in wanted]
    assert (MASTER, "not a transaction file: Monthly Account Data - Master File") in [
        (r["name"], why) for r, why in skipped]
    L.main(["--source", share, "--root", str(tmp_path / "Txn Files"), "--since", "2026.10",
            "--log", str(tmp_path / "log.json")])
    assert "not a transaction file: Monthly Account Data - Master File: 1001" in capsys.readouterr().out
    assert not (tmp_path / "Txn Files" / "1001" / (MASTER + ".zip")).exists()


def test_the_banner_is_read_only_when_it_has_the_export_shape():
    assert L.banner_type(b"1403|10/1/2026 9:01:49 AM||12087|Monthly Transaction File|1.0.0.0\r\nx") == "Monthly Transaction File"
    assert L.banner_type(b"Transaction Date\tDDA Account\n") is None
    assert L.banner_type(b"") is None
    assert L.is_transaction(None) and L.is_transaction("Monthly Transaction File -- ARS")
    assert L.is_transaction("Monthly Tran File")            # 1555's banner (2026-10-20)
    assert not L.is_transaction("Monthly Account Data - Master File")


def test_a_file_the_share_refuses_zipped_is_kept_raw(share, tmp_path, monkeypatch, capsys):
    """The share's security agent empties some clients' transaction files the moment the zip
    closes (1815, 2026-10-20); the file is then kept raw, which the readers take as well."""
    real = L.os.path.getsize
    monkeypatch.setattr(L.os.path, "getsize",
                        lambda p: 0 if str(p).endswith(TXN + ".zip.part") else real(p))
    dest = tmp_path / "Txn Files"
    rc = L.main(["--source", share, "--root", str(dest), "--since", "2026.10", "--log", str(tmp_path / "log.json")])
    assert rc == 0
    assert (dest / "1001" / TXN).read_bytes() == BODY
    assert not (dest / "1001" / (TXN + ".zip")).exists()
    assert (dest / "1002" / (TXN2 + ".zip")).is_file()          # the other still lands zipped
    assert list(dest.rglob("*.part")) == []
    assert "landed raw 1001/" in capsys.readouterr().out
    # on hand now, so a rerun lands nothing
    wanted, _ = L.plan(L.sources("2026.10", share), dest)
    assert wanted == []


def test_a_rerun_lands_nothing_and_a_raw_copy_counts_as_on_hand(share, tmp_path, capsys):
    dest = tmp_path / "Txn Files"
    L.main(["--source", share, "--root", str(dest), "--since", "2026.10", "--log", str(tmp_path / "log.json")])
    # 1002's zip is replaced by the raw file (the moment before zip_txn_files runs)
    (dest / "1002" / (TXN2 + ".zip")).unlink()
    (dest / "1002" / TXN2).write_bytes(RAW2)
    rows = L.sources("2026.10", share)
    wanted, skipped = L.plan(rows, dest)
    assert wanted == []
    assert sorted(why for _, why in skipped if why == "on hand") == ["on hand", "on hand"]


def test_a_copy_at_another_size_is_reported_not_overwritten(share, tmp_path, capsys):
    dest = tmp_path / "Txn Files" / "1001"
    dest.mkdir(parents=True)
    stale = dest / (TXN + ".zip")
    with zipfile.ZipFile(stale, "w") as z:
        z.writestr(TXN, b"older, shorter")
    before = stale.read_bytes()
    rc = L.main(["--source", share, "--root", str(tmp_path / "Txn Files"), "--since", "2026.10",
                 "--log", str(tmp_path / "log.json")])
    assert rc == 0
    assert stale.read_bytes() == before
    out = capsys.readouterr().out
    assert f"differs: 1001 {TXN}" in out


def test_the_same_file_in_two_csm_folders_lands_once(share, tmp_path):
    # a handover: the second CSM's folder holds the same extract
    first = Path(share.split("=", 1)[1])
    second = tmp_path / "share" / "JamesG" / "OD Data Dumps" / "2026.10 Oct"
    second.mkdir(parents=True)
    (second / "1001_ODDD.zip").write_bytes((first / "2026.10 Oct" / "1001_ODDD.zip").read_bytes())
    spec = f"{share};James Gilmore={second.parent}"
    rows = L.sources("2026.10", spec)
    assert sum(r["name"] == TXN for r in rows) == 2
    wanted, skipped = L.plan(rows, tmp_path / "Txn Files")
    assert [r["name"] for r in wanted].count(TXN) == 1
    assert any(why == "same file already planned" for _, why in skipped)


def test_an_older_month_folder_is_left_alone(share, tmp_path):
    root = Path(share.split("=", 1)[1])
    old = root / "2026.08 Aug"
    old.mkdir()
    with zipfile.ZipFile(old / "1003_ODDD.zip", "w") as z:
        z.writestr("1003_1_[2026.08.01][08.00.00]_monthlytran.csv", b"old")
    rows = L.sources("2026.09", share)
    assert {r["client"] for r in rows} == {"1001", "1002"}
    assert {r["client"] for r in L.sources("2026.08", share)} == {"1001", "1002", "1003"}


def test_the_default_window_is_last_month():
    import datetime as dt
    assert L.default_since(dt.date(2026, 10, 20)) == "2026.09"
    assert L.default_since(dt.date(2026, 1, 3)) == "2025.12"


def test_a_failed_landing_leaves_no_part_file(share, tmp_path, monkeypatch):
    dest = tmp_path / "Txn Files"
    monkeypatch.setattr(L, "_check", lambda *a, **k: (_ for _ in ()).throw(ValueError("bad")))
    rc = L.main(["--source", share, "--root", str(dest), "--since", "2026.10", "--log", str(tmp_path / "log.json")])
    assert rc == 1
    assert list(dest.rglob("*.part")) == [] and list(dest.rglob("*.zip")) == []
