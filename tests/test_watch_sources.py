"""watch_sources — the daily "what landed on the CSI shares" check.

The rules pinned here are the ones that decide whether the report is trusted:

  * The first run is a baseline, not sixty pieces of news.
  * Off VPN the shares are unknown, not empty: the saved inventory is left
    alone, or the next check would call every file on the share "new".
  * A file is classified by the naming the builders already rely on, and an
    unrecognised name is still reported (as `other`), never dropped.
  * Only the scanned periods are diffed. An older period's entries are carried
    forward, not reported as "gone" because nobody looked at that folder.
"""
import datetime as dt
import json
import os
import time

import pytest

import watch_sources as W


# ------------------------------------------------------------------ periods
@pytest.mark.parametrize("today,expect", [
    (dt.date(2026, 9, 8), ["2026.09", "2026.08"]),
    (dt.date(2026, 1, 5), ["2026.01", "2025.12"]),
    (dt.date(2026, 3, 31), ["2026.03", "2026.02"]),
])
def test_periods_are_this_month_and_last(today, expect):
    assert W.periods_to_watch(today) == expect


# ------------------------------------------------------------------ classify
@pytest.mark.parametrize("name,share,kind,client", [
    ("1038-2026.09-Sugar River-DCO v2_2.xlsx", "reports", W.DCO, "1038"),
    ("1038-2026.09-Sugar River-Workbook_v2_1_0.xlsx", "reports", W.WORKBOOK, "1038"),
    ("1075-2026.09-MRPC-Austin-MRPCPM_Analysis_v10.xlsx", "reports", W.MRPCPM, "1075"),
    ("1509-2026.09-Texas Bay-Invitation Checking Workbook.xlsx", "reports", W.ICS_WB, "1509"),
    ("1521 Firstmark CU VEL ILS Cloud Amendment Mar 2025.pdf", "reports", W.OTHER, None),
    ("1539_ODDD.zip", "oddd", W.ODDD, "1539"),
    ("notes.txt", "oddd", W.OTHER, None),
])
def test_classify_by_filename(tmp_path, name, share, kind, client):
    folder = tmp_path / ("2026.09 Sep" if share == "oddd" else "2026.09")
    folder.mkdir()
    rec = W.classify(str(folder / name), share)
    assert rec["kind"] == kind
    assert rec["client"] == client
    assert rec["period"] == "2026.09"


def test_ics_workbook_is_not_an_ars_workbook(tmp_path):
    # "Invitation Checking ... Workbook" contains "workbook"; the ICS test must win.
    rec = W.classify(str(tmp_path / "1509-2026.09-X-Invitation Checking Workbook.xlsx"), "reports")
    assert rec["kind"] == W.ICS_WB


def test_office_lock_files_are_ignored(tmp_path):
    assert W.classify(str(tmp_path / "~$1075-2026.09-MRPC-Austin-MRPCPM_Analysis_v10.xlsx"),
                      "reports") is None


def test_odd_period_comes_from_the_month_folder(tmp_path):
    rec = W.classify(str(tmp_path / "2026.08 Aug" / "1075_ODDD.zip"), "oddd")
    assert rec["period"] == "2026.08"


# ------------------------------------------------------------------ shares
@pytest.fixture
def shares(tmp_path, monkeypatch):
    """Two fake share roots with one period populated, plus a fake Drive Inputs/."""
    oddd = tmp_path / "oddd"; reports = tmp_path / "reports"; drive = tmp_path / "drive"
    (oddd / "2026.09 Sep").mkdir(parents=True)
    (reports / "2026.09" / "Aaron Burgard").mkdir(parents=True)
    (drive / "ODDD").mkdir(parents=True)
    (drive / "ARS & MRPC Reports").mkdir(parents=True)
    monkeypatch.setattr(W, "SRC_ODDD", str(oddd))
    monkeypatch.setattr(W, "SRC_REPORTS", str(reports))
    monkeypatch.setattr(W, "_inputs_dir", lambda: str(drive))
    return oddd, reports, drive


def _land(root, *parts, size=10):
    p = root.joinpath(*parts)
    p.write_bytes(b"x" * size)
    return p


def test_first_run_is_a_baseline(shares):
    oddd, reports, _ = shares
    _land(oddd, "2026.09 Sep", "1038_ODDD.zip")
    _land(reports, "2026.09", "Aaron Burgard", "1038-2026.09-Sugar River-DCO v2_2.xlsx")
    r = W.check(["2026.09"], previous=None)
    assert r["reachable"] and r["baseline"]
    assert r["new"] == [] and r["changed"] == [] and r["gone"] == []
    assert len(r["inventory"]) == 2
    assert len(r["next_state"]["files"]) == 2


def test_second_run_reports_only_what_changed(shares):
    oddd, reports, _ = shares
    _land(oddd, "2026.09 Sep", "1038_ODDD.zip")
    dco = _land(reports, "2026.09", "Aaron Burgard", "1038-2026.09-Sugar River-DCO v2_2.xlsx")
    first = W.check(["2026.09"], previous=None)["next_state"]

    _land(reports, "2026.09", "Aaron Burgard", "1038-2026.09-Sugar River-Workbook_v2_1_0.xlsx")
    dco.write_bytes(b"y" * 20)                         # re-landed: same name, new bytes
    r = W.check(["2026.09"], previous=first)
    assert not r["baseline"]
    assert [x["kind"] for x in r["new"]] == [W.WORKBOOK]
    assert [x["kind"] for x in r["changed"]] == [W.DCO]
    assert r["changed"][0]["old_size"] == 10 and r["changed"][0]["size"] == 20
    assert r["gone"] == []


def test_a_removed_file_is_reported_gone(shares):
    oddd, _, _ = shares
    z = _land(oddd, "2026.09 Sep", "1038_ODDD.zip")
    first = W.check(["2026.09"], previous=None)["next_state"]
    z.unlink()
    r = W.check(["2026.09"], previous=first)
    assert [x["name"] for x in r["gone"]] == ["1038_ODDD.zip"]
    assert r["next_state"]["files"] == {}


def test_unscanned_periods_are_carried_forward_not_gone(shares):
    oddd, _, _ = shares
    (oddd / "2026.08 Aug").mkdir()
    _land(oddd, "2026.08 Aug", "1075_ODDD.zip")
    _land(oddd, "2026.09 Sep", "1038_ODDD.zip")
    first = W.check(["2026.09", "2026.08"], previous=None)["next_state"]
    assert len(first["files"]) == 2

    r = W.check(["2026.09"], previous=first)       # August not looked at this time
    assert r["gone"] == [] and r["new"] == []
    kept = {v["name"] for v in r["next_state"]["files"].values()}
    assert kept == {"1075_ODDD.zip", "1038_ODDD.zip"}


def test_same_landing_within_mtime_tolerance_is_not_a_change(shares):
    oddd, _, _ = shares
    z = _land(oddd, "2026.09 Sep", "1038_ODDD.zip")
    first = W.check(["2026.09"], previous=None)["next_state"]
    st = z.stat()
    os.utime(str(z), (st.st_atime, st.st_mtime + 0.9))     # sub-second wobble
    r = W.check(["2026.09"], previous=first)
    assert r["changed"] == []


# ------------------------------------------------------------------ drive
def test_drive_copy_state(shares):
    oddd, reports, drive = shares
    _land(oddd, "2026.09 Sep", "1038_ODDD.zip", size=10)
    _land(drive, "ODDD", "1038_ODDD.zip", size=10)                 # same bytes -> copied
    _land(oddd, "2026.09 Sep", "1075_ODDD.zip", size=30)
    _land(drive, "ODDD", "1075_ODDD.zip", size=25)                 # last month's -> differs
    _land(reports, "2026.09", "Aaron Burgard", "1038-2026.09-Sugar River-DCO v2_2.xlsx")
    r = W.check(["2026.09"], previous=None)
    by = {v["name"]: v["drive"] for v in r["inventory"].values()}
    assert by["1038_ODDD.zip"] == "copied"
    assert by["1075_ODDD.zip"] == "differs"
    assert by["1038-2026.09-Sugar River-DCO v2_2.xlsx"] == "not copied"


# ------------------------------------------------------------------ off VPN
def test_unreachable_share_leaves_the_inventory_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(W, "SRC_ODDD", str(tmp_path / "nope"))
    monkeypatch.setattr(W, "SRC_REPORTS", str(tmp_path / "nope2"))
    previous = {"version": 1, "checked": "2026-09-07 08:00",
                "files": {"k": {"name": "1038_ODDD.zip", "period": "2026.09",
                                "size": 1, "mtime": 1.0, "kind": W.ODDD, "client": "1038"}}}
    r = W.check(["2026.09"], previous=previous)
    assert r["reachable"] is False
    assert r["next_state"] is previous
    assert r["new"] == [] and r["gone"] == []
    assert "not reachable" in W.render(r, {})
    assert W.summary_line(r, {}).startswith("Shares not reachable")


def test_main_exits_2_off_vpn_and_saves_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(W, "SRC_ODDD", str(tmp_path / "nope"))
    monkeypatch.setattr(W, "SRC_REPORTS", str(tmp_path / "nope2"))
    monkeypatch.setattr(W.R, "build_artifacts", lambda: tmp_path)
    assert W.main(["--period", "2026.09"]) == 2
    assert not (tmp_path / W.STATE_NAME).exists()
    assert (tmp_path / W.LOG_NAME).exists()        # the failure is still logged


# ------------------------------------------------------------------ state
def test_damaged_inventory_is_refused_not_emptied(tmp_path):
    p = tmp_path / "source_watch.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(SystemExit):
        W.read_state(str(p))
    p.write_text(json.dumps({"version": 1}), encoding="utf-8")
    with pytest.raises(SystemExit):
        W.read_state(str(p))


def test_state_round_trips(tmp_path, shares):
    oddd, _, _ = shares
    _land(oddd, "2026.09 Sep", "1038_ODDD.zip")
    doc = W.check(["2026.09"], previous=None)["next_state"]
    p = W.write_state(doc, str(tmp_path / "s.json"))
    assert W.read_state(p)["files"] == doc["files"]


# ------------------------------------------------------------------ report
def test_report_puts_roster_clients_first_and_names_the_copy_list(shares):
    oddd, reports, _ = shares
    first = W.check(["2026.09"], previous=None)["next_state"]
    _land(oddd, "2026.09 Sep", "9999_ODDD.zip")                     # not on the roster
    _land(reports, "2026.09", "Aaron Burgard", "1038-2026.09-Sugar River-DCO v2_2.xlsx")
    r = W.check(["2026.09"], previous=first)
    text = W.render(r, {"1038": "Sugar River Bank"})
    assert text.index("Roster clients (1)") < text.index("Other account managers' clients (1)")
    assert "1 of these are for roster clients and not yet current on Drive" in text
    assert "Sugar River Bank" in text
    line = W.summary_line(r, {"1038": "Sugar River Bank"})
    assert line.startswith("2 new") and "roster: 1 DCO" in line


def test_quiet_day_says_so(shares):
    oddd, _, _ = shares
    _land(oddd, "2026.09 Sep", "1038_ODDD.zip")
    first = W.check(["2026.09"], previous=None)["next_state"]
    r = W.check(["2026.09"], previous=first)
    assert "Nothing new" in W.render(r, {})
    assert W.summary_line(r, {}) == "Nothing new on the CSI shares."
