"""The ILS Review card in CSM Sheila (scripts/ils_review_runs.py; Aaron, 2026-11-24): readiness from what the landing
step leaves in Inputs/ILS Analysis, the run with the builder and validator stubbed, delivery to Outputs/<CSM>/ILS/ at
0 FAIL only, the prep deck matched by client number, the page's card, and Sheila in Claude. Synthetic data only."""
import json
import sys
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO), str(REPO / "scripts"), str(REPO / "build")]
import ils_review_runs as RR  # noqa: E402
import ils_runs  # noqa: E402
import rpe_env as R  # noqa: E402

CID, PULL = "7001", "20261101"
REVIEW = (date.today() + timedelta(days=20)).isoformat()
SNAP = "fi_id,fi_name,review_date,tentative_date,pull_by,status,csm,consultant\n"


@pytest.fixture
def root(tmp_path, monkeypatch):
    for d in ("Inputs", "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir()
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("TI_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv(RR.PREP_ENV, str(tmp_path / "no prep folder"))
    (tmp_path / "Client CSM List.csv").write_text(
        "client_id,client_name,csm,products\n7001,Harbor FCU,A Csm,ILS\n7002,Bay Bank,B Csm,ILS\n", encoding="utf-8")
    (tmp_path / "CSM Contacts.csv").write_text(
        "csm,title,cell,office,email\nA Csm,Client Service Manager,5550001111,,a.csm@example.com\n"
        "C Consultant,ILS Consultant,5550002222,,c.consultant@example.com\n", encoding="utf-8")
    monkeypatch.setattr(R, "_csm_cache", {})
    monkeypatch.setattr(R, "_contacts_cache", {})
    return tmp_path


def _ils(root):
    return root / "Inputs" / "ILS Analysis"


def _schedule(root, rows):
    d = _ils(root) / "_schedule"
    d.mkdir(parents=True, exist_ok=True)
    (d / "current_scheduled_analysis.csv").write_text(SNAP + "".join(r + "\n" for r in rows), encoding="utf-8")


def _pulls(root, clients):
    (_ils(root) / "_schedule" / "pulls.json").write_text(
        json.dumps({"written": "2026-11-24T08:20:00", "schedule": {}, "clients": clients}), encoding="utf-8")


def _land(root, cid=CID, pull=PULL, kinds=("zaccounts", "ztrend")):
    d = _ils(root) / cid / pull
    d.mkdir(parents=True, exist_ok=True)
    for k in kinds:
        name = f"{cid}_{k}_{pull}.csv"
        with zipfile.ZipFile(d / (name + ".zip"), "w") as z:
            z.writestr(name, "acct,bal\n1,2\n")


def _entry(current=True, pull=PULL, **kw):
    e = {"name": "Harbor FCU", "review_date": REVIEW, "pull": pull, "current": current, "problem": None,
         "differs": [], "landed_kinds": ["zaccounts", "ztrend"],
         "reason": "pulled 20261101, 20 days before the review" if current else "an earlier review's data"}
    e.update(kw)
    return e


def _ready(root, consultant="C Consultant"):
    _schedule(root, [f"7001,7001 - Harbor FCU,{REVIEW},,,Data Ready,A Csm,{consultant}"])
    _pulls(root, {CID: _entry()})
    _land(root)


# ------------------------------------------------------------------ readiness
def test_off_the_share_is_unknown_never_ready(tmp_path, monkeypatch):
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path / "not there"))
    d = RR.readiness(CID)
    assert d["state"] == "unknown" and "VPN" in d["why"]


def test_no_schedule_landed_yet_is_waiting(root):
    d = RR.readiness(CID)
    assert d["state"] == "waiting" and "landing step" in d["why"]


def test_a_client_off_the_schedule_is_not_scheduled(root):
    _schedule(root, [f"7002,Bay Bank,{REVIEW},,,Confirmed,B Csm,"])
    assert RR.readiness(CID)["state"] == "not_scheduled"
    assert set(RR.scheduled_clients()) == {"7002"}


def test_no_pulls_record_and_a_client_not_reached_are_waiting(root):
    _schedule(root, [f"7001,Harbor FCU,{REVIEW},,,Confirmed,A Csm,"])
    assert RR.readiness(CID)["state"] == "waiting"
    _pulls(root, {"7002": _entry()})
    d = RR.readiness(CID)
    assert d["state"] == "waiting" and "not reached this client" in d["why"]


def test_an_earlier_reviews_pull_is_waiting_with_both_dates(root):
    _schedule(root, [f"7001,Harbor FCU,{REVIEW},,,Confirmed,A Csm,"])
    _pulls(root, {CID: _entry(current=False, pull="20260601")})
    _land(root, pull="20260601")
    d = RR.readiness(CID)
    assert d["state"] == "waiting" and "waiting for this review's data pull" in d["why"].lower()
    assert "20260601" in d["why"] and REVIEW in d["why"]


def test_no_zaccounts_on_hand_is_blocked_whatever_pulls_json_says(root):
    _schedule(root, [f"7001,Harbor FCU,{REVIEW},,,Confirmed,A Csm,"])
    _pulls(root, {CID: _entry()})
    _land(root, kinds=("ztrend",))
    d = RR.readiness(CID)
    assert d["state"] == "blocked" and "ZAccounts" in d["why"]


def test_current_with_zaccounts_is_ready_and_says_what_is_missing(root):
    _schedule(root, [f"7001,7001 - Harbor FCU,{REVIEW},,,Data Ready,A Csm,C Consultant"])
    _pulls(root, {CID: _entry()})
    _land(root, kinds=("zaccounts",))
    d = RR.readiness(CID)
    assert d["state"] == "ready" and d["pull"] == PULL and d["review_date"] == REVIEW and d["name"] == "Harbor FCU"
    text = " ".join(c["text"] for c in d["checks"])
    assert "No ZTrend" in text and "No peer metrics" in text and "no industry file" in text.lower()
    assert d["consultant"] == "C Consultant"
    assert str(root / "Outputs" / "A Csm" / "ILS") in text


def test_peer_metrics_and_the_cycles_industry_file_are_reported(root):
    _ready(root)
    base = root / "Build Artifacts" / "ils_analysis"
    (base / "peers").mkdir(parents=True)
    (base / "peers" / "ils_peer_metrics.csv").write_text("client_id,accttype\n", encoding="utf-8")
    (base / "standard").mkdir(parents=True)
    (base / "standard" / "industry_2020-01.json").write_text("{}", encoding="utf-8")
    text = " ".join(c["text"] for c in RR.readiness(CID)["checks"])
    assert "Peer metrics: 1 table(s)" in text and "the deck uses the newest on hand, industry_2020-01.json" in text


def test_the_consultant_card(root):
    assert RR.consultant_card(CID, "C Consultant")[0]["email"] == "c.consultant@example.com"
    assert RR.consultant_card(CID, "A Csm")[0] is None                   # the client's CSM: one card, not two
    assert RR.consultant_card(CID, "Nobody Listed")[0] is None
    assert RR.consultant_card(CID, "")[0] is None


# ------------------------------------------------------------------ the prep deck
def test_the_prep_deck_is_matched_by_client_number_not_period(root, monkeypatch):
    prep = root / "prep"
    prep.mkdir()
    for n in ("7001-2026.12-ILS-Harbor FCU Prep Slides.pptx", "7001-2027.01-ILS-Harbor FCU Prep Slides v2.pptx",
              "70011-2027.05-ILS-Other Prep Slides.pptx", "~$7001-2027.06-ILS-Harbor FCU Prep Slides.pptx",
              "7002-2027.04-ILS-Bay Bank Prep Slides.pptx", "7001-2027.03-ILS-Harbor FCU ILS Analysis.pptx"):
        (prep / n).write_bytes(b"x")
    assert RR.prep_deck(CID) is None                                    # the setting names no folder: no button
    monkeypatch.setenv(RR.PREP_ENV, str(prep))                          # read on every call
    p = RR.prep_deck(CID)
    assert p["name"] == "7001-2027.01-ILS-Harbor FCU Prep Slides v2.pptx" and p["period"] == "2027.01"
    _ready(root)
    assert RR.review_doc(CID)["prep"]["name"] == p["name"]
    assert RR.prep_deck("7003") is None


# ------------------------------------------------------------------ the run
def _stub_builder(calls, sections_seen):
    from pptx import Presentation

    def run(cmd, cwd, say=print):
        calls.append((list(cmd), Path(cwd)))
        if "--out" in cmd:                                               # merge_review
            out = Path(cmd[cmd.index("--out") + 1])
            out.write_bytes(Path(cmd[2]).read_bytes())
            return 0, ["7 hidden prep slide(s) after the cover; 30 visible of 37 slides -> " + str(out)]
        out_dir = Path(cmd[cmd.index("--out-dir") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        if "--sections" in cmd:
            sections_seen.append(cmd[cmd.index("--sections") + 1].split(","))
        deck = out_dir / f"{CID}-2026.11-ILS-Harbor FCU ILS Analysis.pptx"
        Presentation().save(str(deck))
        return 0, ["Building section: x", "  ! The deck has 61 slides, over the 50-slide limit; name fewer sections.",
                   f"Saved: {deck}", "Done — 50 generated slide(s) in a 61-slide deck.",
                   "1 section(s) reported an error; see the Data Notes slide.", "Deck checks: 0 FAIL, 1 REVIEW.",
                   "  REVIEW slide 9 (x): column 'y' is zero in every row", str(deck)]
    return run


def test_the_run_builds_validates_and_delivers_to_the_csms_ils_folder(root, monkeypatch):
    _ready(root)
    calls, secs = [], []
    monkeypatch.setattr(RR, "run_streamed", _stub_builder(calls, secs))
    monkeypatch.setattr(RR, "validate", lambda deck, say=print: (True, "0 FAIL, 4 REVIEW", []))
    out = RR.run_review({"client": CID, "client_name": "Harbor FCU"}, say=lambda s: None)
    dest = root / "Outputs" / "A Csm" / "ILS" / f"{CID}-2026.11-ILS-ANL-Harbor FCU ILS Analysis.pptx"
    assert out["ok"] and out["delivered"] and out["deck"] == str(dest) and dest.is_file()
    assert out["folder"] == str(root / "Build Artifacts" / "ils" / "review" / CID / PULL)
    assert out["verdict"] == "0 FAIL, 4 REVIEW"
    assert any("over the 50-slide limit" in n for n in out["notes"])
    assert any("reported an error" in n for n in out["notes"]) and any(n.startswith("Deck checks") for n in out["notes"])
    cmd, cwd = calls[0]
    assert cwd == RR.BUILDER_DIR and cmd[1:3] == ["-m", "ils_review.cli"] and "--sections" not in cmd
    assert cmd[cmd.index("--consultant") + 1] == "C Consultant|ILS Consultant|555-000-2222|c.consultant@example.com"
    staged = Path(cmd[cmd.index("--from-folder") + 1])
    assert staged == root / "cache" / "ils_review" / CID / PULL
    assert (staged / f"{CID}_zaccounts_{PULL}.csv").read_text() == "acct,bal\n1,2\n"    # unzipped for the builder
    # a second build replaces the deck in Outputs and archives the first, never deleting it
    RR.run_review({"client": CID, "client_name": "Harbor FCU"}, say=lambda s: None)
    assert len(list((dest.parent / "_Archive").glob("*(superseded *).pptx"))) == 1 and dest.is_file()
    assert RR.review_doc(CID)["decks"]["analysis"]["name"] == dest.name
    # nothing in the CSM's own folder for the ARS readers to take as the client's RPE deck
    assert R.output_decks(f"{CID}-*.pptx") == []


def test_a_deck_from_an_earlier_reviews_pull_does_not_make_the_card_read_as_done(root):
    _ready(root)                                                        # this review's pull is 2026.11
    ils = root / "Outputs" / "A Csm" / "ILS"
    ils.mkdir(parents=True)
    (ils / f"{CID}-2026.05-ILS-ANL-Harbor FCU ILS Analysis.pptx").write_bytes(b"x")
    d = RR.review_doc(CID)["decks"]
    assert d["analysis"]["name"].startswith(f"{CID}-2026.05-") and d["analysis"]["current"] is False
    (ils / f"{CID}-2026.11-ILS-ANL-Harbor FCU ILS Analysis.pptx").write_bytes(b"y")
    assert RR.review_doc(CID)["decks"]["analysis"]["current"] is True
    import sheila_hub as H
    card = H.PAGE[H.PAGE.index("function ilsReviewCard()"):H.PAGE.index("function ilsReviewJobHtml(j)")]
    assert "(d.analysis && d.analysis.current)" in card and "an earlier review's " in card


def test_a_deck_that_fails_validation_stays_in_build_artifacts(root, monkeypatch):
    _ready(root)
    monkeypatch.setattr(RR, "run_streamed", _stub_builder([], []))
    monkeypatch.setattr(RR, "validate", lambda deck, say=print: (False, "2 FAIL, 4 REVIEW", ["[FAIL] slide 3 x"]))
    out = RR.run_review({"client": CID}, say=lambda s: None)
    assert not out["ok"] and not out["delivered"] and "2 FAIL" in out["error"] and "[FAIL] slide 3" in out["error"]
    assert Path(out["deck"]).is_file() and "Build Artifacts" in out["deck"]
    assert not (root / "Outputs" / "A Csm" / "ILS").exists()


def test_a_client_that_is_not_ready_is_not_built(root, monkeypatch):
    monkeypatch.setattr(RR, "run_streamed", lambda *a, **k: pytest.fail("built a client that is not ready"))
    out = RR.run_review({"client": CID}, say=lambda s: None)
    assert not out["ok"] and "landing step" in out["error"]


def test_with_prep_the_matrix_section_is_left_out_and_the_merged_deck_is_delivered(root, monkeypatch):
    _ready(root)
    prep = root / "prep"
    prep.mkdir()
    (prep / "7001-2027.01-ILS-Harbor FCU Prep Slides.pptx").write_bytes(b"x")
    monkeypatch.setenv(RR.PREP_ENV, str(prep))
    calls, secs = [], []
    monkeypatch.setattr(RR, "run_streamed", _stub_builder(calls, secs))
    monkeypatch.setattr(RR, "validate", lambda deck, say=print: (True, "0 FAIL, 4 REVIEW", []))
    out = RR.run_review({"client": CID, "client_name": "Harbor FCU", "merge_prep": True}, say=lambda s: None)
    assert out["ok"] and out["prep"] == "7001-2027.01-ILS-Harbor FCU Prep Slides.pptx"
    assert out["deck"].endswith(f"{CID}-2026.11-ILS-REV-Harbor FCU ILS Review.pptx")
    assert secs and "matrix" not in secs[0] and "kpi_rollup" in secs[0] and "comm_strategies" in secs[0]
    merge_cmd = calls[1][0]
    assert merge_cmd[1] == str(RR.MERGE_TOOL) and merge_cmd[merge_cmd.index("--prep") + 1].endswith("Prep Slides.pptx")
    assert "with_prep" in out["folder"]
    assert any("hidden prep slide" in n for n in out["notes"])


def test_the_validator_gate_fails_closed(root, monkeypatch, tmp_path):
    deck = tmp_path / "d.pptx"
    deck.write_bytes(b"x")

    class Run:
        def __init__(self, code, out):
            self.returncode, self.stdout, self.stderr = code, out, ""
    for code, text, want in ((0, "  0 FAIL, 3 REVIEW\n", True), (1, "  0 FAIL, 3 REVIEW\n", False),
                             (1, "[FAIL] slide 2 x\n  1 FAIL, 0 REVIEW\n", False), (0, "Traceback ...\n", False)):
        monkeypatch.setattr(RR.subprocess, "run", lambda *a, _r=Run(code, text), **k: _r)
        assert RR.validate(deck, say=lambda s: None)[0] is want, (code, text)
    assert (tmp_path / "d.pptx.validation.txt").is_file()


def test_the_builders_default_sections_less_the_matrix():
    secs = RR.default_sections_without_matrix()
    assert "matrix" not in secs and {"kpi_rollup", "data_notes", "comm_strategies"} <= set(secs)


def test_staging_keeps_one_pull_per_client_in_the_cache(root):
    _ready(root)
    old = root / "cache" / "ils_review" / CID / "20250101"
    old.mkdir(parents=True)
    (old / "f.csv").write_text("x")
    d = RR.stage_pull(CID, PULL, say=lambda s: None)
    assert d == root / "cache" / "ils_review" / CID / PULL and (d / f"{CID}_ztrend_{PULL}.csv").is_file()
    assert not old.exists()
    import local_cache
    assert CID in local_cache.clients(root / "cache")                  # inside the cache's size and age limits


# ------------------------------------------------------------------ Sheila's routes and list
def test_the_route_refuses_a_review_that_is_not_ready_or_has_no_prep(root, monkeypatch):
    code, doc = ils_runs.start({"kind": "review", "client": CID})
    assert code == 409 and "landing step" in doc["error"]
    _ready(root)
    assert ils_runs.start({"kind": "review", "client": CID, "merge_prep": True})[0] == 409
    started = []
    monkeypatch.setattr(ils_runs.threading, "Thread", lambda target, daemon: type("T", (), {"start": lambda s: started.append(1)})())
    code, doc = ils_runs.start({"kind": "review", "client": CID, "client_name": "Harbor FCU"})
    assert code == 200 and started and doc["job"]["kind"] == "review" and doc["job"]["step"] == 2
    assert ils_runs.job_doc("review", CID)["merge_prep"] is False
    ils_runs._jobs.pop(("review", CID), None)


def test_the_client_doc_carries_the_review_card_and_the_list_carries_scheduled_clients(root):
    _ready(root)
    d = ils_runs.client_doc(CID)
    assert d["review"]["state"] == "ready" and set(d["kinds"]) == {"pgl", "kickoff"}
    assert ils_runs.scheduled_clients() == {CID: {"name": "Harbor FCU", "csm": "A Csm"}}


def test_the_page_draws_the_review_card_outside_the_fold():
    import sheila_hub as H
    page = H.PAGE
    assert "Coming soon" not in page
    draw = page[page.index("function ilsDraw()"):page.index("function ilsReviewCard()")]
    assert "box.innerHTML = ilsReviewCard() + `<details class=\"ilsfold\"" in draw
    card = page[page.index("function ilsReviewCard()"):page.index("function ilsReviewJobHtml(j)")]
    assert 'data-ilsreview="plain"' in card and 'data-ilsreview="prep"' in card and "r.prep ?" in card
    assert 'r.state === "not_scheduled"' in card and 'id="ilsjobreview"' in card
    assert "Show in File Explorer" in page and '"/api/ils/run"' in page and 'kind: "review"' in page


# ------------------------------------------------------------------ Sheila in Claude
def test_sheila_in_claude_speaks_the_review_card(root, monkeypatch):
    from sheila_mcp import actions
    _ready(root)
    text = "\n".join(actions.review_lines(RR.review_doc(CID)))
    assert "ILS Review: ready" in text and f"data pull {PULL}" in text and 'kind="review"' in text
    monkeypatch.setattr(actions, "find_client", lambda c: ({"id": CID, "name": "Harbor FCU"}, None))
    monkeypatch.setattr(ils_runs, "start", lambda body: (409, {"error": "not ready (waiting)"}))
    r = actions.ils_run(CID, "review", merge_prep=True)
    assert r["answer"].startswith("Not started: not ready")
    assert actions.ils_run(CID, "nope")["answer"] == "kind is pgl, kickoff or review."


# --- the client list's state for a client on ILS alone (2026-11-24: they all read Blocked before) ---------------------
def _web():
    import ars_launcher_web as W
    return W


@pytest.mark.parametrize("state,ready,blocked", [("ready", True, None), ("waiting", False, "waiting for ILS data"),
                                                  ("blocked", False, "ILS data problem"), ("unknown", False, None)])
def test_an_ils_only_clients_list_state_comes_from_the_review_card(monkeypatch, state, ready, blocked):
    W = _web()
    monkeypatch.setattr(RR, "readiness", lambda cid: {"state": state, "pull": PULL})
    monkeypatch.setattr(RR, "_decks_in_outputs", lambda cid, pull=None: {"analysis": None, "review": None})
    st = W.ils_list_state(CID, True)
    assert (st["ready"], st["blocked"]) == (ready, blocked)
    assert st["checked"] == (state != "unknown")                 # the share unreadable reads as not checked, never Ready


def test_this_reviews_deck_in_outputs_reads_in_outputs_and_an_earlier_one_does_not(monkeypatch):
    W = _web()
    monkeypatch.setattr(RR, "readiness", lambda cid: {"state": "ready", "pull": PULL})
    monkeypatch.setattr(RR, "_decks_in_outputs", lambda cid, pull=None: {
        "analysis": {"name": "7001-2026.11-ILS-ANL-Harbor FCU ILS Analysis.pptx", "current": True},
        "review": {"name": "7001-2026.05-ILS-REV-Harbor FCU ILS Review.pptx", "current": False}})
    assert W.ils_list_state(CID, True)["decks"] == ["7001-2026.11-ILS-ANL-Harbor FCU ILS Analysis.pptx"]


def test_a_pre_go_live_client_with_no_review_scheduled_is_not_blocked(monkeypatch):
    W = _web()
    monkeypatch.setattr(RR, "readiness", lambda cid: pytest.fail("no readiness read for an unscheduled client"))
    st = W.ils_list_state(CID, False)
    assert st["blocked"] is None and not st["ready"] and st["note"] == "ILS"


def test_a_readiness_error_never_breaks_the_list_or_reads_ready(monkeypatch):
    W = _web()

    def boom(cid):
        raise RuntimeError("synthetic")
    monkeypatch.setattr(RR, "readiness", boom)
    st = W.ils_list_state(CID, True)
    assert st == {"checked": False, "ready": False, "blocked": None, "note": None, "decks": [], "state": "unknown",
                  "review_date": None, "review_status": None, "pull": None}


def test_the_served_list_uses_the_ils_state_not_the_rpe_stop(monkeypatch):
    """An RPE status saying stop (every ILS-only client's) must not reach the list for a client on ILS alone."""
    import time
    W = _web()
    row = {"id": CID, "name": "Harbor FCU", "csm": "A Csm", "programs": [], "decks": [], "ils_only": True,
           "ils": {"checked": True, "ready": True, "blocked": None, "note": None, "decks": []}}
    monkeypatch.setitem(W._clients, "doc", {"period": "2026.11", "clients": [row]})
    monkeypatch.setattr(W, "_status_cache", {CID: (time.time(), {"period": "2026.11", "state": "stop",
                                                                   "checks": [{"level": W.L.STOP, "text": "No program"}]})})
    monkeypatch.setattr(W, "_jobs", {})
    served = W._served_clients()
    c = (served["clients"] if isinstance(served, dict) else served)[0]
    assert c["ready"] is True and c["blocked"] is None and c["checked"] is True
    assert c["ils"]["ready"] is True, "the ILS Decks tab reads the block itself (2026-11-25)"


def test_the_page_reads_an_ils_only_clients_state_from_its_ils_block():
    """2026-11-25: a client on ILS alone is on ILS Decks, whose state is ilsKind's; RPE Decks' kindOf no longer reads it."""
    src = (REPO / "scripts" / "sheila_hub.py").read_text(encoding="utf-8")
    kind_of = src[src.index("function kindOf(c)"):src.index("function ilsKind(c)")]
    assert "ils_decks" not in kind_of and "ils_note" not in kind_of
    assert "const rowKind = c => c.ils_only ? ilsKind(c)" in src