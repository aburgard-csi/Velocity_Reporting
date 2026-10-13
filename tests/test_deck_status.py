"""deck_status — readiness, staleness and the delivery log.

The rules pinned here are the ones that decide whether a build is allowed to run
on data that looks fine and is not:

  * A Inputs/ ODD extract is only current if the SOURCE says so. It is overwritten
    in place as `<id>_ODDD.zip` with no period in the name, so last month's file
    sits at the same path under the same name. Calling that "present" is how a
    deck ships a month of the wrong numbers and passes every check, because
    month-old figures are internally consistent.
  * ...but a byte-identical copy is NOT stale. Google Inputs/ stores mtime to whole
    seconds while the SMB share keeps sub-second, so a straight copy reads ~0.9s
    older on Inputs/. A strict comparison flagged 1075's 2026.08 extract
    (229,507,542 bytes, same second) as a previous month's.
  * A damaged delivery log is not an empty one. Reading it as "nothing sent"
    would invite sending a client the same deck twice.
"""
import json
import os
import time

import pytest

import deck_status as DS


# ------------------------------------------------------------------ periods
@pytest.mark.parametrize("p,ok", [
    ("2026.09", True), ("2026.1", False), ("26.09", False),
    ("2026-09", False), ("", False), ("2026.13", True),   # month range is not ours to police
])
def test_period_shape(p, ok):
    assert bool(DS._period_ok(p)) is ok


# ------------------------------------------------------------------ ODD state
def _dirs(tmp_path):
    reports = tmp_path / "reports"; reports.mkdir()
    oddd = tmp_path / "oddd"; oddd.mkdir()
    return str(reports), oddd


def _odd_row(rows):
    return next(r for r in rows if r["input"] == "ODD extract")


def test_odd_absent_from_drive_is_missing(tmp_path, monkeypatch):
    reports, oddd = _dirs(tmp_path)
    monkeypatch.setattr(DS, "_oddd_month_dirs", lambda p, spec=None: [])
    rows = DS.requirements("1038", ["ARS"], "2026.09", reports, oddd, [], True)
    assert _odd_row(rows)["local"]["state"] == DS.MISSING


def test_odd_on_drive_with_no_source_extract_is_stale(tmp_path, monkeypatch):
    """The case that matters: Inputs/ has a file, but no extract for THIS period
    has landed, so what Inputs/ holds is a previous month's."""
    reports, oddd = _dirs(tmp_path)
    (oddd / "1038_ODDD.zip").write_bytes(b"august")
    monkeypatch.setattr(DS, "_oddd_month_dirs", lambda p, spec=None: [])
    row = _odd_row(DS.requirements("1038", ["ARS"], "2026.09", reports, oddd, [], True))
    assert row["local"]["state"] == DS.STALE
    assert "2026.09" in row["local"]["detail"]


def test_a_copy_the_watch_recorded_for_this_period_is_present_after_the_source_file_goes(tmp_path, monkeypatch):
    """1539 Marine's 2026.10 extract landed 2026-10-06, the watch copied it, and the file was
    taken back off the share by 2026-10-13: the copy read as "previous month" though it was
    October's (Aaron, 2026-10-13). The watch's landing record vouches for it when the size matches."""
    reports, oddd = _dirs(tmp_path)
    held = oddd / "1539_ODDD.zip"
    held.write_bytes(b"october-extract")
    monkeypatch.setattr(DS, "_oddd_month_dirs", lambda p, spec=None: [])
    monkeypatch.setattr(DS, "watch_landing", lambda cid, period: {"size": len(b"october-extract"), "mtime": 1791291657.0})
    row = _odd_row(DS.requirements("1539", ["ARS"], "2026.10", reports, oddd, [], True))
    assert row["local"]["state"] == DS.PRESENT and "since removed from the share" in row["local"]["detail"]
    # A record of a different file (another size) vouches for nothing.
    monkeypatch.setattr(DS, "watch_landing", lambda cid, period: {"size": 999, "mtime": 1791291657.0})
    assert _odd_row(DS.requirements("1539", ["ARS"], "2026.10", reports, oddd, [], True))["local"]["state"] == DS.STALE
    # And no record at all is the stale case it always was.
    monkeypatch.setattr(DS, "watch_landing", lambda cid, period: None)
    assert _odd_row(DS.requirements("1539", ["ARS"], "2026.10", reports, oddd, [], True))["local"]["state"] == DS.STALE


def test_watch_landing_reads_the_inventory_by_client_and_period(tmp_path, monkeypatch):
    import watch_sources as W
    inv = {"files": {
        "a": {"kind": "ODDD", "client": "1539", "period": "2026.09", "size": 10, "mtime": 1.0},
        "b": {"kind": "ODDD", "client": "1539", "period": "2026.10", "size": 20, "mtime": 2.0},
        "c": {"kind": "DCO", "client": "1539", "period": "2026.10", "size": 30, "mtime": 3.0},
        "d": {"kind": "ODDD", "client": "1075", "period": "2026.10", "size": 40, "mtime": 4.0}}}
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(W, "read_state", lambda path=None: inv)
    assert DS.watch_landing("1539", "2026.10")["size"] == 20
    assert DS.watch_landing("1539", "2026.08") is None
    monkeypatch.setattr(W, "read_state", lambda path=None: (_ for _ in ()).throw(SystemExit("damaged")))
    assert DS.watch_landing("1539", "2026.10") is None      # a damaged inventory vouches for nothing


def test_identical_copy_is_not_stale(tmp_path, monkeypatch):
    """Same bytes => same extract, whatever the filesystems say about mtime."""
    reports, oddd = _dirs(tmp_path)
    src = tmp_path / "src"; src.mkdir()
    (src / "1038_ODDD.zip").write_bytes(b"same-bytes")
    held = oddd / "1038_ODDD.zip"
    held.write_bytes(b"same-bytes")
    # Inputs/ reads ~1s OLDER than source, exactly as Google Inputs/ vs SMB does.
    s = os.path.getmtime(src / "1038_ODDD.zip")
    os.utime(held, (s - 1.0, s - 1.0))
    monkeypatch.setattr(DS, "_oddd_month_dirs", lambda p, spec=None: [("Aaron Burgard", str(src))])
    row = _odd_row(DS.requirements("1038", ["ARS"], "2026.09", reports, oddd, [], True))
    assert row["local"]["state"] == DS.PRESENT, row["local"]


def test_genuinely_older_drive_copy_is_stale(tmp_path, monkeypatch):
    reports, oddd = _dirs(tmp_path)
    src = tmp_path / "src"; src.mkdir()
    (src / "1038_ODDD.zip").write_bytes(b"september-extract")
    held = oddd / "1038_ODDD.zip"
    held.write_bytes(b"august")                      # different size AND older
    s = os.path.getmtime(src / "1038_ODDD.zip")
    os.utime(held, (s - 86400, s - 86400))
    monkeypatch.setattr(DS, "_oddd_month_dirs", lambda p, spec=None: [("Aaron Burgard", str(src))])
    row = _odd_row(DS.requirements("1038", ["ARS"], "2026.09", reports, oddd, [], True))
    assert row["local"]["state"] == DS.STALE


def test_off_vpn_is_unknown_not_missing(tmp_path, monkeypatch):
    """Off VPN the source cannot be consulted. Reporting that as 'not landed'
    would show a full cycle of gaps that may not exist."""
    reports, oddd = _dirs(tmp_path)
    (oddd / "1038_ODDD.zip").write_bytes(b"whatever")
    rows = DS.requirements("1038", ["ARS"], "2026.09", reports, oddd, [], False)
    for r in rows:
        assert r["src"]["state"] == DS.UNKNOWN, r["input"]
    assert _odd_row(rows)["local"]["state"] == DS.UNKNOWN


# ------------------------------------------------------------------ optional
def test_missing_ics_workbook_does_not_block(tmp_path, monkeypatch):
    """Without a workbook for the period the ICS section builds referrals-only,
    which is a valid deck — not a gap to chase."""
    reports, oddd = _dirs(tmp_path)
    monkeypatch.setattr(DS, "_vip_sheet", lambda cid, prog: DS._stat(DS.PRESENT, "x", "local"))
    rows = DS.requirements("1509", ["ICS"], "2026.09", reports, oddd, [], True)
    wb = next(r for r in rows if r["input"] == DS.OPTIONAL_INPUT)
    assert wb["local"]["state"] == DS.MISSING
    assert wb["src"]["state"] == DS.NA          # arrives by email, never at source
    blocked = [r["input"] for r in rows
               if r["local"]["state"] in (DS.MISSING, DS.STALE)
               and r["input"] != DS.OPTIONAL_INPUT]
    assert blocked == []


# ------------------------------------------------------------------ deliveries
@pytest.fixture
def log(tmp_path, monkeypatch):
    monkeypatch.setattr(DS.R, "build_artifacts", lambda: tmp_path)
    return tmp_path / "deliveries.json"


def test_absent_log_reads_as_nothing_sent(log):
    assert DS.read_deliveries()["sent"] == {}


def test_mark_and_clear_round_trip(log):
    DS.mark_sent("1075", "2026.08", by="tester")
    rec = json.loads(log.read_text(encoding="utf-8"))["sent"]["1075|2026.08"]
    assert rec["client_id"] == "1075" and rec["period"] == "2026.08"
    assert rec["sent_at"] and rec["by"] == "tester"
    DS.clear_sent("1075", "2026.08")
    assert DS.read_deliveries()["sent"] == {}


def test_a_corrupt_log_refuses_rather_than_reporting_nothing_sent(log):
    log.write_text("{not json", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        DS.read_deliveries()
    assert "unreadable" in str(e.value)


def test_a_log_without_sent_is_refused(log):
    log.write_text('{"version": 1}', encoding="utf-8")
    with pytest.raises(SystemExit):
        DS.read_deliveries()


def test_write_is_atomic_and_leaves_no_tmp(log):
    DS.mark_sent("1038", "2026.08")
    assert log.exists()
    assert not list(log.parent.glob("*.tmp"))


# ------------------------------------------------------------------ roster
def test_the_dashboard_uses_the_same_roster_as_the_builder():
    """One answer to 'who gets a deck'. A second list would drift from
    clients.md, which is the whole reason that file exists."""
    from build_month import read_roster
    assert DS.read_roster is read_roster
    active, _skipped = read_roster()
    assert active, "clients.md parsed to an empty roster"


def test_source_reports_lists_every_account_manager_folder_without_a_stat_per_file(tmp_path, monkeypatch):
    """One listing per folder (2026-09-17): an isfile() per landed file was a share round trip each."""
    period = tmp_path / "2026.09"
    for rel in ("Aaron Burgard/1038-2026.09-Sugar River-Workbook.xlsx", "James Gilmore/1441-2026.09-DCO.xlsx",
                "James Gilmore/.hidden.xlsx", "loose-file.xlsx"):
        (period / rel).parent.mkdir(parents=True, exist_ok=True)
        (period / rel).write_bytes(b"x")
    (period / "James Gilmore" / "a folder").mkdir()
    monkeypatch.setattr(DS, "SRC_REPORTS", str(tmp_path))
    monkeypatch.setattr(DS.os.path, "isfile", lambda p: pytest.fail("no isfile per file"))
    got = sorted(os.path.relpath(f, period).replace(os.sep, "/") for f in DS._source_reports("2026.09"))
    assert got == ["Aaron Burgard/1038-2026.09-Sugar River-Workbook.xlsx", "James Gilmore/1441-2026.09-DCO.xlsx"]
    assert DS._source_reports("2026.10") == []
