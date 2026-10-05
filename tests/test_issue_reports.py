"""Issues reported from CSM Sheila (Aaron, 2026-10-02).

Sheila runs on each CSM's machine from the share and the repo is PRIVATE, so a token in
the released copy would be readable by anyone who can reach Tools\\RPE. There is none: the
button queues to the share and a sync, run where gh is authenticated, files the queue and
caches the issue list back for the view.

What matters here is that no path through this module reaches GitHub except `sync`, that a
report which fails to file is kept rather than lost, and that a re-run never files the same
report twice.
"""
import json

import pytest

import issue_reports as IR


@pytest.fixture(autouse=True)
def on_a_scratch_share(tmp_path, monkeypatch):
    """Point the module's share folder at a temp dir, and make gh unreachable by default."""
    monkeypatch.setattr(IR, "reports_dir", lambda create=True: tmp_path)
    monkeypatch.setattr(IR, "cache_path", lambda: tmp_path / "issues.json")

    def no_gh(args, check=True):
        raise AssertionError(f"this path must not call gh: {args}")
    monkeypatch.setattr(IR, "_gh", no_gh)
    return tmp_path


# ------------------------------------------------------------------ the queue
def test_reporting_never_touches_github(on_a_scratch_share):
    """The button runs on a machine with no credentials, no gh and maybe no VPN."""
    rec = IR.queue("Lift Matrix is slow for 1549", "It took a minute.", client_id="1549")
    assert rec["status"] == "queued" and rec["issue"] is None
    assert (on_a_scratch_share / f"{rec['id']}.json").exists()
    assert IR.view()["rows"][0]["state"] == "queued"      # view reads the share only


def test_a_report_needs_a_title():
    with pytest.raises(ValueError):
        IR.queue("   ", "body only")


def test_an_unreadable_report_is_shown_not_dropped(on_a_scratch_share):
    IR.queue("a good one")
    (on_a_scratch_share / "20260101T000000-broken.json").write_text("{not json", encoding="utf-8")
    states = {r["state"] for r in IR.view()["rows"]}
    assert "damaged" in states and "queued" in states


# ------------------------------------------------------------------ sync
def _fake_gh(calls, created="https://github.com/o/r/issues/7", issues=()):
    def gh(args, check=True):
        calls.append(args)
        if args[:2] == ["label", "list"]:
            return json.dumps([{"name": IR.LABEL}])
        if args[:2] == ["issue", "create"]:
            return created + "\n"
        if args[:2] == ["issue", "list"]:
            return json.dumps(list(issues))
        return ""
    return gh


def test_sync_files_the_queue_and_records_the_number(monkeypatch):
    calls = []
    monkeypatch.setattr(IR, "_gh", _fake_gh(
        calls, issues=[{"number": 7, "title": "x", "state": "OPEN", "url": "u"}]))
    rec = IR.queue("something is wrong")
    res = IR.sync()
    assert res["filed"] == [(rec["id"], 7)] and not res["failed"]
    assert IR.load_reports()[0]["issue"]["number"] == 7
    assert IR.view()["rows"][0]["state"] == "open"        # GitHub's state, not "filed"


def test_a_second_sync_files_nothing_twice(monkeypatch):
    calls = []
    monkeypatch.setattr(IR, "_gh", _fake_gh(calls))
    IR.queue("once only")
    IR.sync()
    created = sum(1 for c in calls if c[:2] == ["issue", "create"])
    IR.sync()
    assert sum(1 for c in calls if c[:2] == ["issue", "create"]) == created == 1


def test_a_report_that_cannot_be_filed_stays_queued(monkeypatch):
    """Losing someone's report because GitHub was unreachable is the one unacceptable
    outcome: it is the only copy, and the person who wrote it has moved on."""
    def gh(args, check=True):
        if args[:2] == ["label", "list"]:
            return json.dumps([{"name": IR.LABEL}])
        raise RuntimeError("could not connect")
    monkeypatch.setattr(IR, "_gh", gh)
    rec = IR.queue("keep me")
    res = IR.sync()
    assert res["failed"] and not res["filed"]
    assert IR.load_reports()[0]["status"] == "queued"
    assert IR.view()["rows"][0]["state"] == "queued"


def test_a_missing_label_does_not_stop_the_report_being_filed(monkeypatch):
    """The first real report failed with "'sheila' not found": a fresh repo has no such
    label. It is a filter, not the point — the issue is filed either way."""
    seen = []

    def gh(args, check=True):
        seen.append(args)
        if args[:2] == ["label", "list"]:
            return json.dumps([])
        if args[:2] == ["label", "create"]:
            raise RuntimeError("refused")
        if args[:2] == ["issue", "create"]:
            assert "--label" not in args, "must not insist on a label it could not create"
            return "https://github.com/o/r/issues/9\n"
        if args[:2] == ["issue", "list"]:
            assert "--label" not in args
            return "[]"
        return ""
    monkeypatch.setattr(IR, "_gh", gh)
    IR.queue("file me anyway")
    assert IR.sync()["filed"] == [(IR.load_reports()[0]["id"], 9)]


def test_an_issue_filed_by_hand_still_shows_in_the_view(monkeypatch):
    """Someone files one on GitHub directly, or from another machine. It is shown, not
    hidden, or the view would quietly disagree with the repo."""
    monkeypatch.setattr(IR, "_gh", _fake_gh(
        [], issues=[{"number": 3, "title": "filed by hand", "state": "OPEN", "url": "u",
                     "createdAt": "2026-10-01T00:00:00Z"}]))
    IR.sync()
    titles = {r["title"] for r in IR.view()["rows"]}
    assert "filed by hand" in titles


def test_closed_issues_sort_below_the_rest(monkeypatch):
    monkeypatch.setattr(IR, "_gh", _fake_gh(
        [], issues=[{"number": 1, "title": "done", "state": "CLOSED", "url": "u"},
                    {"number": 2, "title": "live", "state": "OPEN", "url": "u"}]))
    IR.sync()
    IR.queue("not yet filed")
    states = [r["state"] for r in IR.view()["rows"]]
    assert states[-1] == "closed", states


# ------------------------------------------------------------------ the 08:00 run
def test_the_morning_step_never_raises(monkeypatch):
    """It runs inside the scheduled task, beside the mail step and for the same reason: a
    step that reaches off the machine must not take the share check's findings with it.

    gh missing, no internet, a damaged report — the morning says so and the reports stay
    queued, which is what queueing them is for (Aaron, 2026-10-05)."""
    import watch_sources as W

    def boom(*a, **k):
        raise RuntimeError("gh is not on PATH")
    monkeypatch.setattr(IR, "sync", boom)
    monkeypatch.setattr(IR, "load_reports", lambda: [{"status": "queued", "id": "x"}])
    text = W.issues_step(dry_run=False)
    assert "SKIPPED" in text and "stay queued" in text
    assert "Reported issues" in text


def test_the_morning_step_files_and_says_what_it_filed(monkeypatch):
    import watch_sources as W
    monkeypatch.setattr(IR, "load_reports", lambda: [{"status": "queued", "id": "r1"}])
    monkeypatch.setattr(IR, "sync", lambda: {"filed": [("r1", 42)], "failed": [],
                                             "issues": 3, "list_error": None})
    text = W.issues_step(dry_run=False)
    assert "#42" in text and "r1" in text


def test_the_morning_step_keeps_a_report_it_could_not_file(monkeypatch):
    import watch_sources as W
    monkeypatch.setattr(IR, "load_reports", lambda: [{"status": "queued", "id": "r2"}])
    monkeypatch.setattr(IR, "sync", lambda: {"filed": [], "failed": [("r2", "no network")],
                                             "issues": 0, "list_error": None})
    text = W.issues_step(dry_run=False)
    assert "NOT filed" in text and "still queued" in text


def test_a_dry_run_files_nothing(monkeypatch):
    import watch_sources as W

    def no(*a, **k):
        raise AssertionError("--dry-run must not file anything")
    monkeypatch.setattr(IR, "sync", no)
    monkeypatch.setattr(IR, "load_reports", lambda: [{"status": "queued", "id": "r3"}])
    assert "nothing was filed" in W.issues_step(dry_run=True)
