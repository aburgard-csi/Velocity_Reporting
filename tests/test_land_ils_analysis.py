"""land_ils_analysis / ils_analysis_landed: the ILS analysts' newest data pulls landed in Inputs/ILS Analysis (Aaron, 2026-11-24).

Pinned here: which schedule rows count, when a pull is current, which pull is the newest and which of its files land, the
canonical zipped name, verify-then-rename, never overwriting, a zip the share will not keep landed raw, the soft budget,
nothing written by a dry run or with a source down, the reader taking raw or zipped files, stage(), and the watch's listing.
Synthetic data only: invented client numbers (7001...) and names.
"""
import json
import os
import re
import zipfile
from datetime import date
from pathlib import Path

import pytest

import deck_status as DS
import ils_analysis_inputs as IA
import ils_analysis_landed as L
import land_ils_analysis as LA
import rpe_env
import watch_sources as W

TODAY = date(2026, 11, 24)
REPO = Path(__file__).resolve().parent.parent
HEADER = "fi_id,fi_name,go_live,tentative_date,review_date,slides_by,status,csm,consultant\n"


def _write(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode("utf-8"))                         # no newline translation: sizes are compared
    return p


def _zip(p, members):
    p.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in members.items():
            z.writestr(name, text)
    return p


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A data root, a fake analysis share and a schedule."""
    data = tmp_path / "data"
    for d in ("Inputs", "Outputs", "Build Artifacts"):
        (data / d).mkdir(parents=True)
    monkeypatch.setenv("RPE_DATA_ROOT", str(data))
    src = tmp_path / "share"
    a = src / "Harbor FCU_7001"
    _write(a / "DataPull_202508" / "Zaccounts_20250801.csv", "old\n")
    _write(a / "DataPull_202508" / "Ztrend_20250801.csv", "old\n")
    p = a / "DataPull_20261103"
    _write(p / "Zaccounts_20261103.csv", "acctid,items365\n" + "1,2\n" * 50)
    _write(p / "Ztrend_20261103.csv", "acctid,notice\n" + "1,x\n" * 200)
    _write(p / "MatrixVal_20261103.txt", "matrix\n")
    _write(p / "DBIC_20261103.txt", "dbic\n")
    _write(p / "Weird_20261103.csv", "unknown\n")
    _write(p / "ILS Program Analysis - Harbor.pptm", "deck")
    _write(p / "uncleaned data" / "Zaccounts.csv", "not read\n")
    b = src / "Lakeside - 7002"
    _zip(b / "DataPull_202611" / "7002_DataPull_20261110.zip",
         {"DataPull_20261110/zaccount.csv": "a\n" * 30, "DataPull_20261110/zt.csv": "b\n" * 40,
          "DataPull_20261110/dd.csv": "c\n" * 10})
    _write(src / "Twin Bank_7003" / "DataPull_20261101" / "Zaccounts_20261101.csv", "x\n")
    _write(src / "Twin_7003" / "DataPull_20261101" / "Zaccounts_20261101.csv", "x\n")
    _write(src / "Old Mill_7004" / "DataPull_20250301" / "Zaccounts_20250301.csv", "z\n")
    _write(src / "Old Mill_7004" / "DataPull_20250301" / "Ztrend_20250301.csv", "z\n")
    _write(src / "Notes_7005.xlsx", "a stray file at the root is not a client folder")
    sched = _write(tmp_path / "schedule.csv", HEADER + "\n".join([
        "7001,Harbor FCU,1/1/2020,,12/10/2026,12/3/2026,Data Ready,A CSM,A Consultant",
        "7001,Harbor FCU,1/1/2020,,6/1/2025,5/25/2025,Slides Ready,A CSM,A Consultant",
        "7002,Lakeside Bank,,,12/1/2026,,\"Confirmed, Scheduled, Support Needed\",A CSM,A Consultant",
        "7003,Twin Bank,,,12/5/2026,,Data Ready,A CSM,A Consultant",
        "7004,Old Mill CU,,,3/1/2026,,\"Unconfirmed, Scheduled Review OVERDUE\",A CSM,A Consultant",
        "7006,Far Off Bank,,,6/1/2027,,Tentative Review Date,A CSM,A Consultant",
        "7007,Gone Bank,,,12/2/2026,,CANCELLED,A CSM,A Consultant",
    ]) + "\n")
    return {"data": data, "dest": data / "Inputs" / "ILS Analysis", "src": src, "schedule": sched}


def _run(world, **kw):
    lines = []
    rc = LA.run(source=str(world["src"]), schedule=str(world["schedule"]), today=TODAY, say=lines.append, **kw)
    return rc, "\n".join(lines)


# ── the convention ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("name,kind", [
    ("za.csv", "zaccounts"), ("zt.csv", "ztrend"), ("dd.csv", "debitdeclines"), ("zaccount.csv", "zaccounts"),
    ("Zaccount_20251205.csv", "zaccounts"), ("Declines_20240507.csv", "debitdeclines"), ("Matrix_20250113.txt", "matrixval"),
    ("7001_za.csv", "zaccounts"),
])
def test_the_short_names_pull_folders_use_read_as_their_kind(name, kind):
    assert IA.kind_of(name) == kind


@pytest.mark.parametrize("name", ["outliers_za.csv", "ubs_zt_365.csv", "DataIntegrity_20251107.txt", "zap.csv", "matrix.xlsx"])
def test_an_alias_is_the_whole_stem_never_a_substring(name):
    assert IA.kind_of(name) is None


def test_a_landed_zip_keeps_its_place_under_the_rename_tool(tmp_path):
    d = tmp_path / "7001" / "20261103"
    _zip(d / "7001_zaccounts_20261103.csv.zip", {"7001_zaccounts_20261103.csv": "a\n"})
    assert IA.plan_client("7001", tmp_path / "7001") == []
    assert IA.target("7001", ["DataPull_x", "Zaccounts.csv.zip"], "202611")[0] == ["202611", "7001_zaccounts_202611.csv.zip"]


def test_the_folder_is_a_registered_input_kind_that_is_never_scanned():
    assert rpe_env.INPUT_KIND_DIRS["ILS analysis"] == "ILS Analysis" == IA.SUBDIR
    assert "ILS analysis" in rpe_env.NOT_SCANNED_KINDS
    assert "ILS Analysis" not in rpe_env._scanned_dirnames()


def test_one_analysis_share_root_for_the_landing_and_the_peer_pull():
    """peer_pull.py names the share too; its folder is another session's, so the two are pinned equal here."""
    src = (REPO / "build" / "ils_analysis" / "ils_review" / "peer_pull.py").read_text(encoding="utf-8")
    m = re.search(r'^ANALYSIS_ROOT = r"(.+)"$', src, re.M)
    assert m and m.group(1) == DS._DEFAULT_SRC_ILS_ANALYSIS


# ── the schedule ─────────────────────────────────────────────────────────────
def test_the_schedule_is_upcoming_reviews_and_overdue_ones(world):
    scope = L.in_scope(L.read_schedule(world["schedule"]), TODAY)
    assert list(scope) == ["7004", "7002", "7003", "7001"]          # overdue first (earliest date), then by review date
    assert scope["7001"]["review_date"] == "2026-12-10"            # the upcoming row, not the old one
    assert "7006" not in scope                                     # past the horizon: no current pull can exist yet
    assert "7007" not in scope                                     # cancelled


def test_an_upcoming_review_wins_over_an_overdue_one():
    rows = [{"fi_id": "7001", "review_date": "2026-03-01", "status": "Unconfirmed, Scheduled Review OVERDUE"},
            {"fi_id": "7001", "review_date": "2026-12-09", "status": "Confirmed"}]
    assert L.in_scope(rows, TODAY)["7001"]["review_date"] == "2026-12-09"


def test_the_live_workbook_reads_like_the_csv_and_keeps_only_the_columns_used(tmp_path):
    import openpyxl
    from datetime import datetime
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["fi_id", "fi_name", "review_date", "request_date", "slides_by", "pull_by", "status", "csm",
               "technical_contact", "notes"])
    ws.append([7001, "7001 - Harbor FCU", datetime(2026, 12, 10), None, None, datetime(2026, 11, 19), "Data Ready", "A CSM",
               "someone@example.com", "a note"])
    p = tmp_path / "s.xlsx"
    wb.save(p)
    rows = L.read_schedule(p)
    assert rows == [{"fi_id": "7001", "fi_name": "7001 - Harbor FCU", "review_date": "2026-12-10", "tentative_date": "",
                     "pull_by": "2026-11-19", "status": "Data Ready", "csm": "A CSM"}]
    assert "example.com" not in L.snapshot_text(rows)


def test_a_schedule_without_the_columns_it_needs_is_refused(tmp_path):
    with pytest.raises(ValueError):
        L.read_schedule(_write(tmp_path / "s.csv", "fi_id,fi_name\n7001,x\n"))


@pytest.mark.parametrize("pull,current", [
    ("20261103", True), ("20261011", True), ("20261010", False), ("20261215", True), ("202611", True), ("202609", False),
    (None, False),
])
def test_a_pull_is_current_within_60_days_before_the_review(pull, current):
    assert L.judge(pull, {"review_date": "2026-12-10", "status": "Data Ready"})[0] is current


def test_the_watch_reads_a_month_only_stamp_as_the_month_s_end():
    row = {"review_date": "2026-12-04", "status": "Slides Ready"}
    assert L.judge("202610", row)[0] is False and L.judge("202610", row, month_end=True)[0] is True
    assert L.pull_day("202602", month_end=True) == date(2026, 2, 28)


def test_the_stale_reason_says_why():
    ok, why = L.judge("20250301", {"review_date": "2026-03-01", "status": "OVERDUE"})
    assert not ok and "365 days before" in why and "earlier review" in why


# ── the share ────────────────────────────────────────────────────────────────
def test_client_folders_are_folders_and_two_matches_are_not_guessed(world):
    f = LA.client_folders(world["src"])
    assert "7005" not in f
    r = LA.resolve("7003", f["7003"], world["src"])
    assert "2 folders" in r["problem"] and "not guessed" in r["problem"]


def test_the_newest_pull_and_its_extracts(world):
    f = LA.client_folders(world["src"])
    r = LA.resolve("7001", f["7001"], world["src"])
    assert r["pull"] == "20261103" and r["pull_name"] == "DataPull_20261103"
    assert sorted(r["extracts"]) == ["7001_dbic_20261103.txt", "7001_matrixval_20261103.txt",
                                     "7001_zaccounts_20261103.csv", "7001_ztrend_20261103.csv"]
    assert r["unrecognised"] == ["Weird_20261103.csv"] and r["missing"] == []
    assert any("uncleaned data" in n for n in r["notes"])


def test_a_month_folder_holding_a_pull_zip_takes_the_zip_s_day(world):
    f = LA.client_folders(world["src"])
    r = LA.resolve("7002", f["7002"], world["src"])
    assert r["pull"] == "20261110"
    assert sorted(r["extracts"]) == ["7002_debitdeclines_20261110.csv", "7002_zaccounts_20261110.csv",
                                     "7002_ztrend_20261110.csv"]


# ── landing ──────────────────────────────────────────────────────────────────
def test_a_dry_run_writes_nothing(world):
    rc, out = _run(world)
    assert rc == 0 and "dry run" in out
    assert not world["dest"].exists()
    assert not (world["data"] / "Build Artifacts" / "ils_analysis" / LA.LANDINGS_NAME).exists()


def test_apply_lands_each_extract_zipped_under_its_canonical_name(world):
    rc, out = _run(world, apply=True)
    assert rc == 0, out
    z = world["dest"] / "7001" / "20261103" / "7001_zaccounts_20261103.csv.zip"
    with zipfile.ZipFile(z) as zf:
        assert zf.namelist() == ["7001_zaccounts_20261103.csv"]
        assert zf.read("7001_zaccounts_20261103.csv").decode() == "acctid,items365\n" + "1,2\n" * 50
    assert not list(world["dest"].rglob("*.part"))
    assert not list(world["dest"].rglob("*.pptm")) and not list(world["dest"].rglob("Weird*"))
    assert sorted(L.landed_files("7002", "20261110", world["dest"])) == ["debitdeclines", "zaccounts", "ztrend"]
    log = json.loads((world["data"] / "Build Artifacts" / "ils_analysis" / LA.LANDINGS_NAME).read_text())
    assert {r["status"] for r in log} == {"landed"} and len(log) == 4 + 3 + 2


def test_a_second_run_lands_nothing(world):
    _run(world, apply=True)
    rc, out = _run(world, apply=True)
    assert rc == 0 and "0 file(s) to land" in out


def test_a_differing_file_is_reported_and_never_overwritten(world):
    d = world["dest"] / "7001" / "20261103"
    _write(d / "7001_dbic_20261103.txt", "a different landing\n")
    rc, out = _run(world, apply=True)
    assert "differs (left alone): 7001/20261103/7001_dbic_20261103.txt" in out
    assert (d / "7001_dbic_20261103.txt").read_text() == "a different landing\n"
    assert not (d / "7001_dbic_20261103.txt.zip").exists()


def test_a_raw_file_on_hand_at_the_same_size_counts_as_landed(world):
    d = world["dest"] / "7001" / "20261103"
    _write(d / "7001_dbic_20261103.txt", "dbic\n")
    rc, out = _run(world, apply=True)
    assert not (d / "7001_dbic_20261103.txt.zip").exists()
    assert L.landed_files("7001", "20261103", world["dest"])["dbic"].name == "7001_dbic_20261103.txt"


def test_a_zip_the_share_removes_is_landed_raw(world, monkeypatch):
    real = os.replace

    def agent(src, dst):                                      # the security agent deletes the zip once it has its name
        real(src, dst)
        if str(dst).endswith(".zip"):
            os.remove(dst)
    monkeypatch.setattr(LA.os, "replace", agent)
    rc, out = _run(world, apply=True, clients=["7001"])
    assert rc == 0, out
    d = world["dest"] / "7001" / "20261103"
    assert (d / "7001_zaccounts_20261103.csv").read_text() == "acctid,items365\n" + "1,2\n" * 50
    assert "landed raw" in out


def test_a_source_that_does_not_read_back_fails_that_file_only(world, monkeypatch):
    def bad_check(*a, **k):
        raise ValueError("member decompresses to the wrong CRC")
    monkeypatch.setattr(LA, "_check", bad_check)
    rc, out = _run(world, apply=True, clients=["7004"])
    assert rc == 1 and "FAILED" in out
    assert not list(world["dest"].rglob("*.zip")) and not list(world["dest"].rglob("*.part"))


def test_the_budget_stops_between_files_and_says_what_is_left(world):
    rc, out = _run(world, apply=True, budget_minutes=-1)
    assert rc == 0 and "left for the next run" in out
    assert not list(world["dest"].rglob("*.zip"))


def test_smallest_files_land_first(world):
    resolved = {c: LA.resolve(c, LA.client_folders(world["src"])[c], world["src"]) for c in ("7001", "7002")}
    wanted, _ = LA.plan(resolved, world["dest"])
    sizes = [i["file"]["size"] for i in wanted]
    assert sizes == sorted(sizes)


@pytest.mark.parametrize("which", ["schedule", "src"])
def test_a_source_that_cannot_be_reached_writes_nothing(world, which):
    world[which] = world[which].parent / "missing"
    rc, out = _run(world, apply=True)
    assert rc == 2 and "cannot be" in out
    assert not world["dest"].exists()


def test_the_status_file_judges_each_scheduled_client(world):
    _run(world, apply=True)
    doc = L.pulls_status(world["dest"])
    c = doc["clients"]
    assert c["7001"]["current"] is True and c["7001"]["landed_kinds"] == ["dbic", "matrixval", "zaccounts", "ztrend"]
    assert c["7004"]["current"] is False and "earlier review" in c["7004"]["reason"]
    assert c["7003"]["current"] is False and "not guessed" in c["7003"]["problem"]
    assert doc["schedule"]["rows"] == 7 and doc["schedule"]["in_scope"] == 4


def test_a_run_for_one_client_keeps_every_other_client_s_status(world):
    _run(world, apply=True)
    _run(world, apply=True, clients=["7002"])
    assert sorted(L.pulls_status(world["dest"])["clients"]) == ["7001", "7002", "7003", "7004"]


def test_a_differing_file_is_not_counted_as_landed(world):
    d = world["dest"] / "7001" / "20261103"
    _write(d / "7001_dbic_20261103.txt", "a different landing\n")
    _run(world, apply=True)
    c = L.pulls_status(world["dest"])["clients"]["7001"]
    assert c["differs"] == ["7001_dbic_20261103.txt"] and "dbic" not in c["landed_kinds"]


def test_a_current_pull_lands_before_any_stale_one(world):
    f = LA.client_folders(world["src"])
    resolved = {c: LA.resolve(c, f[c], world["src"]) for c in ("7001", "7004")}
    wanted, _ = LA.plan(resolved, world["dest"], first={"7001"})
    order = [i["client"] for i in wanted]
    assert order == ["7001"] * 4 + ["7004"] * 2                 # though every 7004 file is smaller than every 7001 file
    assert max(i["file"]["size"] for i in wanted[4:]) < min(i["file"]["size"] for i in wanted[:4])


def test_a_zip_gone_by_the_end_of_the_run_is_landed_raw(world, monkeypatch):
    real = LA.record

    def agent_later(results, path):                         # the zip vanishes some time after its check passed
        for r in results:
            if r["status"] == "landed" and r["name"].startswith("7004_zaccounts"):
                os.remove(world["dest"] / r["client"] / r["pull"] / (r["name"] + ".zip"))
        real(results, path)
    monkeypatch.setattr(LA, "record", agent_later)
    rc, out = _run(world, apply=True, clients=["7004"])
    assert rc == 0, out
    assert (world["dest"] / "7004" / "20250301" / "7004_zaccounts_20250301.csv").read_bytes() == b"z\n"
    assert "gone by the end of the run" in out


def test_a_file_too_large_for_any_budgeted_run_is_not_started(world, monkeypatch):
    monkeypatch.setattr(LA, "ZIP_MB_PER_S", 1e-9)
    rc, out = _run(world, apply=True, clients=["7004"], budget_minutes=1)
    assert rc == 0 and "too large for a 1-minute run" in out
    assert not list(world["dest"].rglob("*.zip"))


def test_staged_files_are_what_the_review_builder_finds(world, tmp_path):
    """The contract PR 2 relies on: stage() output handed to `ils_review.cli --from-folder` finds the extracts."""
    import sys
    sys.path.insert(0, str(REPO / "build" / "ils_analysis"))
    from ils_review.cli import find_inputs
    _run(world, apply=True, clients=["7001", "7002"])
    for client, pull in (("7001", "20261103"), ("7002", "20261110")):
        out = tmp_path / f"stage_{client}"
        L.stage(client, pull, out, base=world["dest"])
        found = find_inputs(str(out))
        assert found["zaccounts_path"].endswith(f"{client}_zaccounts_{pull}.csv")
        assert found["ztrend_path"].endswith(f"{client}_ztrend_{pull}.csv")
    assert find_inputs(str(tmp_path / "stage_7002"))["declines_path"].endswith("7002_debitdeclines_20261110.csv")
    assert find_inputs(str(tmp_path / "stage_7001"))["dbic_path"].endswith("7001_dbic_20261103.txt")


def test_current_only_lands_only_current_pulls(world):
    rc, out = _run(world, apply=True, current_only=True)
    assert rc == 0
    assert not (world["dest"] / "7004").exists() and (world["dest"] / "7001").exists()


def test_the_schedule_snapshot_is_replaced_only_when_it_changes(world):
    _run(world, apply=True)
    d = L.schedule_dir(world["dest"])
    meta = json.loads((d / L.SNAPSHOT_META).read_text())
    first = meta["changed_at"]
    assert [r["fi_id"] for r in L.snapshot_rows(world["dest"])][:2] == ["7001", "7001"]
    assert L.write_snapshot(L.read_schedule(world["schedule"]), world["schedule"], base=world["dest"]) is False
    assert json.loads((d / L.SNAPSHOT_META).read_text())["changed_at"] == first
    rows = L.read_schedule(world["schedule"])[:2]
    assert L.write_snapshot(rows, world["schedule"], base=world["dest"]) is True
    assert [r["fi_id"] for r in L.scheduled(TODAY, base=world["dest"])] == ["7001"]


# ── reading what landed ──────────────────────────────────────────────────────
def test_landed_files_take_raw_or_zipped_and_prefer_raw(tmp_path):
    d = tmp_path / "7001" / "20261103"
    _zip(d / "7001_zaccounts_20261103.csv.zip", {"7001_zaccounts_20261103.csv": "z\n"})
    _write(d / "7001_ztrend_20261103.csv", "t\n")
    _zip(d / "7001_ztrend_20261103.csv.zip", {"7001_ztrend_20261103.csv": "t\n"})
    _write(d / "analysis.txt", "no kind")
    got = L.landed_files("7001", "20261103", tmp_path)
    assert got == {"zaccounts": d / "7001_zaccounts_20261103.csv.zip", "ztrend": d / "7001_ztrend_20261103.csv"}


def test_stage_writes_the_extracts_unzipped_and_skips_what_is_staged(tmp_path):
    d = tmp_path / "in" / "7001" / "20261103"
    _zip(d / "7001_zaccounts_20261103.csv.zip", {"7001_zaccounts_20261103.csv": "z\n" * 5})
    _write(d / "7001_dbic_20261103.txt", "dbic\n")
    out = tmp_path / "stage"
    got = L.stage("7001", "20261103", out, base=tmp_path / "in")
    assert sorted(p.name for p in got.values()) == ["7001_dbic_20261103.txt", "7001_zaccounts_20261103.csv"]
    assert (out / "7001_zaccounts_20261103.csv").read_text() == "z\n" * 5
    stamp = (out / "7001_zaccounts_20261103.csv").stat().st_mtime_ns
    os.utime(out / "7001_zaccounts_20261103.csv", ns=(stamp - 10 ** 9, stamp - 10 ** 9))
    L.stage("7001", "20261103", out, base=tmp_path / "in")
    assert (out / "7001_zaccounts_20261103.csv").stat().st_mtime_ns == stamp - 10 ** 9      # left as it was
    assert not list(out.glob("*.part"))


# ── the morning watch ────────────────────────────────────────────────────────
def test_the_watch_lists_new_pulls_against_its_own_state(world, tmp_path):
    state = tmp_path / "watch_state.json"
    kw = dict(state_path=state, source=str(world["src"]), schedule=str(world["schedule"]), today=TODAY)
    first = "\n".join(LA.watch(**kw))
    assert "baseline" in first and "7004" in first and "Waiting for a current pull" in first
    assert "2 folders match" in first
    _write(world["src"] / "Old Mill_7004" / "DataPull_20261120" / "Zaccounts_20261120.csv", "new\n")
    second = "\n".join(LA.watch(**kw))
    assert "7004: new pull `DataPull_20261120`" in second
    assert "land_ils_analysis.py --apply" in second
    third = "\n".join(LA.watch(**kw))
    assert "no new pulls" in third


def test_a_client_new_to_the_schedule_is_not_a_new_pull(world, tmp_path):
    state = tmp_path / "watch_state.json"
    LA.watch(state_path=state, source=str(world["src"]), schedule=str(world["schedule"]), today=TODAY)
    doc = json.loads(state.read_text())
    del doc["clients"]["7001"]                                 # 7001 was not on the schedule last time
    state.write_text(json.dumps(doc))
    out = "\n".join(LA.watch(state_path=state, source=str(world["src"]), schedule=str(world["schedule"]), today=TODAY))
    assert "no new pulls" in out and "7001" in json.loads(state.read_text())["clients"]


def test_the_watch_keeps_its_state_when_the_server_is_down(world, tmp_path):
    state = tmp_path / "watch_state.json"
    LA.watch(state_path=state, source=str(world["src"]), schedule=str(world["schedule"]), today=TODAY)
    before = state.read_text()
    out = "\n".join(LA.watch(state_path=state, source=str(tmp_path / "down"), schedule=str(world["schedule"]), today=TODAY))
    assert "unreachable" in out and state.read_text() == before


def test_a_dry_run_watch_saves_no_state(world, tmp_path):
    state = tmp_path / "watch_state.json"
    LA.watch(state_path=state, source=str(world["src"]), schedule=str(world["schedule"]), today=TODAY, dry_run=True)
    assert not state.exists()


def test_the_watch_step_never_fails_the_watch(monkeypatch):
    def boom(**kw):
        raise RuntimeError("server gone")
    monkeypatch.setattr(LA, "watch", boom)
    assert "SKIPPED: RuntimeError: server gone" in W.ils_analysis_step()


def test_the_watch_never_adds_the_analysis_server_to_its_reachability_check():
    import inspect
    assert "ILS" not in inspect.getsource(W.reachable)


def test_the_morning_task_passes_it_and_the_landing_has_its_own_task():
    watch = (REPO / "scripts" / "watch_sources.py").read_text(encoding="utf-8")
    task = (REPO / "scripts" / "register_watch_task.ps1").read_text(encoding="utf-8")
    assert '"--ils-analysis"' in watch and "land_ils_analysis.watch(" in watch
    assert '$TaskArgs += " --ils-analysis"' in task
    assert "land_ils_analysis" not in "".join(l for l in task.splitlines() if l.strip().startswith("$TaskArgs ="))
    own = (REPO / "scripts" / "register_ils_landing_task.ps1").read_text(encoding="utf-8")
    assert '"RPE ILS Analysis Landing"' in own and "--apply" in own and "-Minutes 50" in own and "-Unregister" in own
