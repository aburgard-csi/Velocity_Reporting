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
    """Two fake share roots with one period populated, plus a fake local Inputs/."""
    oddd = tmp_path / "oddd"; reports = tmp_path / "reports"; held = tmp_path / "local"
    (oddd / "2026.09 Sep").mkdir(parents=True)
    (reports / "2026.09" / "Aaron Burgard").mkdir(parents=True)
    (held / "ODDD").mkdir(parents=True)
    (held / "ARS & MRPC Reports").mkdir(parents=True)
    monkeypatch.setattr(W, "SRC_ODDD", str(oddd))
    monkeypatch.setattr(W, "SRC_REPORTS", str(reports))
    monkeypatch.setattr(W, "_inputs_dir", lambda: str(held))
    return oddd, reports, held


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


# ------------------------------------------------------------------ held
def test_drive_copy_state(shares):
    oddd, reports, held = shares
    _land(oddd, "2026.09 Sep", "1038_ODDD.zip", size=10)
    _land(held, "ODDD", "1038_ODDD.zip", size=10)                 # same bytes -> copied
    _land(oddd, "2026.09 Sep", "1075_ODDD.zip", size=30)
    _land(held, "ODDD", "1075_ODDD.zip", size=25)                 # last month's -> differs
    _land(reports, "2026.09", "Aaron Burgard", "1038-2026.09-Sugar River-DCO v2_2.xlsx")
    r = W.check(["2026.09"], previous=None)
    by = {v["name"]: v["local"] for v in r["inventory"].values()}
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
    assert "1 of these are for roster clients and not yet in Inputs" in text
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


# ------------------------------------------------------------------ copy step
def _inv(*recs):
    return {r["name"] + r.get("period", ""): r for r in recs}


def _rec(kind, client, period, held, name=None, path=None, size=10):
    return {"kind": kind, "client": client, "period": period, "local": held,
            "name": name or ("%s_ODDD.zip" % client if kind == W.ODDD
                             else "%s-%s-X-%s.xlsx" % (client, period, kind)),
            "path": path or "src", "size": size}


def test_copy_plan_is_roster_only_and_skips_what_drive_already_has(tmp_path):
    inv = _inv(
        _rec(W.DCO, "1038", "2026.09", "not copied"),
        _rec(W.WORKBOOK, "1038", "2026.09", "copied"),           # already there
        _rec(W.MRPCPM, "1075", "2026.09", "differs"),             # re-landed
        _rec(W.DCO, "9999", "2026.09", "not copied"),             # not on the roster
        _rec(W.OTHER, "1038", "2026.09", "not copied", name="notes.pdf"),
    )
    plan = W.copy_plan(inv, {"1038", "1075"}, str(tmp_path))
    names = sorted(r["name"] for r, _ in plan)
    assert names == ["1038-2026.09-X-DCO.xlsx", "1075-2026.09-X-MRPCPM.xlsx"]
    dests = {r["name"]: d for r, d in plan}
    assert dests["1038-2026.09-X-DCO.xlsx"] == str(tmp_path / "DCOs" / "1038-2026.09-X-DCO.xlsx")
    assert dests["1075-2026.09-X-MRPCPM.xlsx"] == str(
        tmp_path / "MRPC Analyses" / "1075-2026.09-X-MRPCPM.xlsx")


def test_copy_plan_never_copies_an_older_odd_over_a_newer_one(tmp_path):
    # Inputs/ holds this month's extract; last month's at source now "differs".
    inv = _inv(
        _rec(W.ODDD, "1075", "2026.08", "differs"),
        _rec(W.ODDD, "1075", "2026.09", "copied"),
    )
    assert W.copy_plan(inv, {"1075"}, str(tmp_path)) == []
    # Inputs/ holds last month's: this month's is the one and only candidate.
    inv = _inv(
        _rec(W.ODDD, "1075", "2026.08", "copied"),
        _rec(W.ODDD, "1075", "2026.09", "differs"),
    )
    plan = W.copy_plan(inv, {"1075"}, str(tmp_path))
    assert [(r["period"], d) for r, d in plan] == [
        ("2026.09", str(tmp_path / "ODDD" / "1075_ODDD.zip"))]


def test_copy_plan_without_drive_is_empty():
    assert W.copy_plan(_inv(_rec(W.DCO, "1038", "2026.09", "not copied")), {"1038"}, None) == []


def test_apply_copies_writes_verifies_and_overwrites(tmp_path):
    src = tmp_path / "src.xlsx"; src.write_bytes(b"new" * 5)
    dest = tmp_path / "local" / "DCOs" / "1038-2026.09-X-DCO.xlsx"
    dest.parent.mkdir(parents=True); dest.write_bytes(b"old")
    rec = _rec(W.DCO, "1038", "2026.09", "differs", path=str(src), size=15)
    out = W.apply_copies([(rec, str(dest))])
    assert out[0][2] == "copied" and rec["local"] == "copied"
    assert dest.read_bytes() == b"new" * 5
    assert not (tmp_path / "local" / "ARS & MRPC Reports" / "1038-2026.09-X-DCO.xlsx.part").exists()


def test_apply_copies_reports_a_failure_instead_of_raising(tmp_path):
    rec = _rec(W.DCO, "1038", "2026.09", "not copied", path=str(tmp_path / "missing.xlsx"))
    out = W.apply_copies([(rec, str(tmp_path / "d" / "x.xlsx"))])
    assert out[0][2].startswith("FAILED")
    assert rec["local"] == "not copied"


def test_copy_flag_copies_only_when_not_dry_run(shares, tmp_path, monkeypatch, capsys):
    oddd, reports, held = shares
    _land(reports, "2026.09", "Aaron Burgard", "1038-2026.09-Sugar River-DCO v2_2.xlsx")
    monkeypatch.setattr(W.R, "build_artifacts", lambda: tmp_path / "ba")
    (tmp_path / "ba").mkdir()
    monkeypatch.setattr(W, "_roster", lambda: {"1038": "Sugar River Bank"})
    dest = held / "DCOs" / "1038-2026.09-Sugar River-DCO v2_2.xlsx"

    assert W.main(["--period", "2026.09", "--copy", "--dry-run"]) == 0
    assert "Would copy into Inputs (1)" in capsys.readouterr().out
    assert not dest.exists()

    assert W.main(["--period", "2026.09", "--copy"]) == 0
    out = capsys.readouterr().out
    assert dest.exists() and "Copied into Inputs (1)" in out and "Copied 1 into Inputs." in out


# ------------------------------------------------------------------ prune step
def test_prune_keeps_the_newest_period_per_client_and_kind():
    names = [
        "1038-2026.07-Sugar River-DCO v2_2.xlsx",
        "1038-2026.08-Sugar River-DCO v2_2.xlsx",
        "1038-2026.09-Sugar River-DCO v2_2.xlsx",
        "1038-2026.08-Sugar River-Workbook_v2_1_0.xlsx",          # only workbook: kept
        "1537-2026.08-FNBT Chickasha-Workbook_v2_1_0.xlsx",
        "1537-2026.09-Brooks Bank-Workbook_v2_1_0.xlsx",          # renamed client, same id+kind
        "1537-2026.06-FNBT Chickasha-Invitation Checking Workbook v1.7.1-DM.xlsx",  # only ICS wb
        "1075-2026.08-MRPC-Austin-MRPCPM_Analysis_v10.xlsx",
        "1075-2026.09-MRPC-Austin-MRPCPM_Analysis_v10.xlsx",
        "~$1075-2026.09-MRPC-Austin-MRPCPM_Analysis_v10.xlsx",   # lock file
        "Austin ICS Charts 2026.xlsx",                             # unpatterned: never
        "1121_temp_ODD_completion_260904_164836.xlsx",             # 'other': never
    ]
    plan = W.prune_plan(names)
    assert plan == [
        ("1038-2026.07-Sugar River-DCO v2_2.xlsx", "1038-2026.09-Sugar River-DCO v2_2.xlsx"),
        ("1038-2026.08-Sugar River-DCO v2_2.xlsx", "1038-2026.09-Sugar River-DCO v2_2.xlsx"),
        ("1075-2026.08-MRPC-Austin-MRPCPM_Analysis_v10.xlsx", "1075-2026.09-MRPC-Austin-MRPCPM_Analysis_v10.xlsx"),
        ("1537-2026.08-FNBT Chickasha-Workbook_v2_1_0.xlsx", "1537-2026.09-Brooks Bank-Workbook_v2_1_0.xlsx"),
    ]


def test_prune_keeps_the_newest_weekly_by_stamp():
    names = ["260830_072636-MRPCEnrollmentSummary_v3_13.xlsx",
             "260906_044753-MRPCEnrollmentSummary_v3_13.xlsx",
             "CashPleaseSummaryV1_260830_072636.xlsx",
             "CashPleaseSummaryV1_260906_063545.xlsx",
             "CashPleaseSummaryV1_260906_063545 - Copy.xlsx"]
    plan = W.prune_plan(names)
    # Same stamp twice (a file and its "- Copy") is ambiguous: neither is pruned.
    assert [o for o, _ in plan] == ["260830_072636-MRPCEnrollmentSummary_v3_13.xlsx",
                                    "CashPleaseSummaryV1_260830_072636.xlsx"]


def test_prune_never_plans_against_an_only_file():
    assert W.prune_plan(["1174-2026.07-PointBank-DCO v2_2.xlsx",
                         "1632-2026.07-WesBanco-Invitation Checking Workbook v1.7.1.xlsx"]) == []


def test_apply_prune_removes_only_when_the_newer_file_is_real(tmp_path):
    (tmp_path / "old.xlsx").write_bytes(b"o"); (tmp_path / "new.xlsx").write_bytes(b"n")
    (tmp_path / "old2.xlsx").write_bytes(b"o"); (tmp_path / "empty.xlsx").write_bytes(b"")
    (tmp_path / "old3.xlsx").write_bytes(b"o")
    out = W.apply_prune(str(tmp_path), [("old.xlsx", "new.xlsx"), ("old2.xlsx", "empty.xlsx"),
                                        ("old3.xlsx", "gone.xlsx")])
    assert [o[2] for o in out][0] == "removed"
    assert out[1][2].startswith("FAILED") and out[2][2].startswith("FAILED")
    assert not (tmp_path / "old.xlsx").exists()
    assert (tmp_path / "old2.xlsx").exists() and (tmp_path / "old3.xlsx").exists()


def test_prune_flag_reports_and_deletes(shares, tmp_path, monkeypatch, capsys):
    oddd, reports, held = shares
    rep = held / "ARS & MRPC Reports"
    _land(rep, "1038-2026.08-Sugar River-DCO v2_2.xlsx")
    _land(rep, "1038-2026.09-Sugar River-DCO v2_2.xlsx")
    monkeypatch.setattr(W.R, "build_artifacts", lambda: tmp_path / "ba"); (tmp_path / "ba").mkdir()
    monkeypatch.setattr(W, "_roster", lambda: {"1038": "Sugar River Bank"})

    assert W.main(["--period", "2026.09", "--prune", "--dry-run"]) == 0
    assert "Would remove superseded inputs (1)" in capsys.readouterr().out
    assert (rep / "1038-2026.08-Sugar River-DCO v2_2.xlsx").exists()

    assert W.main(["--period", "2026.09", "--prune"]) == 0
    out = capsys.readouterr().out
    assert "Removed superseded inputs (1)" in out and "Removed 1 superseded." in out
    assert not (rep / "1038-2026.08-Sugar River-DCO v2_2.xlsx").exists()
    assert (rep / "1038-2026.09-Sugar River-DCO v2_2.xlsx").exists()


def test_a_drive_copy_changed_after_landing_is_not_overwritten(tmp_path):
    # Same name, different bytes, Inputs/ written AFTER the source landed: that is a
    # deliberate change (a workbook recalculated in Excel), not a re-landing.
    src = tmp_path / "src.xlsx"; src.write_bytes(b"raw" * 4)
    dest = tmp_path / "local" / "ARS & MRPC Reports" / "1539-2026.08-Marine FCU-Workbook_v2_1_0.xlsx"
    dest.parent.mkdir(parents=True); dest.write_bytes(b"recalculated")
    st = src.stat(); os.utime(str(src), (st.st_atime, st.st_mtime - 3600))    # landed an hour before
    rec = _rec(W.WORKBOOK, "1539", "2026.08", "differs", name=dest.name, path=str(src), size=12)
    rec["mtime"] = os.path.getmtime(str(src))
    assert W.copy_plan(_inv(rec), {"1539"}, str(tmp_path / "local")) == []
    # ...but a genuine re-landing (source newer) is copied.
    os.utime(str(src), (st.st_atime, os.path.getmtime(str(dest)) + 3600))
    rec["mtime"] = os.path.getmtime(str(src))
    assert len(W.copy_plan(_inv(rec), {"1539"}, str(tmp_path / "local"))) == 1


def test_copy_plan_takes_only_the_newest_period_per_client_and_kind(tmp_path):
    # Last month's DCO is still on the share; this month's supersedes it. Copying
    # the old one would have --prune delete it again the same run, daily.
    inv = _inv(
        _rec(W.DCO, "1539", "2026.08", "not copied"),
        _rec(W.DCO, "1539", "2026.09", "not copied"),
        _rec(W.WORKBOOK, "1539", "2026.08", "not copied"),        # no September workbook: still newest
    )
    plan = W.copy_plan(inv, {"1539"}, str(tmp_path))
    assert sorted((r["kind"], r["period"]) for r, _ in plan) == [(W.DCO, "2026.09"), (W.WORKBOOK, "2026.08")]


def test_copy_plan_skips_when_drive_already_holds_a_newer_period(tmp_path):
    rep = tmp_path / "ARS & MRPC Reports"; rep.mkdir()
    _land(rep, "1539-2026.09-Marine FCU-DCO v2_2.xlsx")
    inv = _inv(_rec(W.DCO, "1539", "2026.08", "not copied"))     # the share's newest is older
    assert W.copy_plan(inv, {"1539"}, str(tmp_path)) == []
