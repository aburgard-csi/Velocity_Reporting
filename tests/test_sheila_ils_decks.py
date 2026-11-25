"""RPE Decks and ILS Decks in CSM Sheila's sidebar (Aaron, 2026-11-25: "We'll need to view ILS only clients in Sheila
now. On the left side bar change Decks to RPE Decks, add another entry for ILS Decks").

The client list carries an `ils` block for every ILS client (on the review schedule, with pre-go-live or kickoff inputs
landed, or on the clients.md ILS roster); a client on ILS alone is `ils_only` and left out of RPE Decks; the page's ILS
Decks tab reads the block. Synthetic clients and CSMs only.
"""
import json
import sys
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO), str(REPO / "scripts"), str(REPO / "build")]
import ars_launcher_web as W  # noqa: E402
import build_month as BM  # noqa: E402
import ils_review_runs as RR  # noqa: E402
import rpe_env as R  # noqa: E402
import sheila_hub as H  # noqa: E402

REVIEW = (date.today() + timedelta(days=20)).isoformat()
PULL = "20261101"
ROSTER = "\n".join([
    "## Active clients", "", "| ID | Client | Path | ARS | ICS | MRPC | Deck |", "| --- | --- | --- | --- | --- | --- | --- |",
    "| 7101 | Alpine Bank | SM | yes | — | — | ARS |",
    "| 7104 | Dune FCU | SM | yes | — | — | ARS |", "",
    "## ILS roster — which clients are on ILS", "",
    "| ID | Client | CSM | Other Velocity products |", "| --- | --- | --- | --- |",
    "| 7104 | Dune FCU | A Csm | ARS |",
    "| 7105 | Elm Bank | A Csm | — |", "",
    "## Status changes", ""])


@pytest.fixture
def root(tmp_path, monkeypatch):
    """Five synthetic clients: 7101 RPE only, 7102 ILS only and ready, 7103 ILS only with a pre-go-live extract landed
    (another CSM's), 7104 on both and waiting for its pull, 7105 on the ILS roster alone and in no CSM List."""
    for d in ("Inputs", "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir()
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("TI_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv(RR.PREP_ENV, str(tmp_path / "no prep folder"))
    (tmp_path / "Client CSM List.csv").write_text(
        "client_id,client_name,csm,products\n7101,Alpine Bank,A Csm,ARS\n7102,Birch CU,A Csm,ILS\n"
        "7103,Cedar Bank,B Csm,ILS\n7104,Dune FCU,A Csm,ARS;ILS\n", encoding="utf-8")
    (tmp_path / "CSM Contacts.csv").write_text("csm,title,cell,office,email\nA Csm,CSM,5550001111,,a.csm@example.com\n",
                                               encoding="utf-8")
    monkeypatch.setattr(R, "_csm_cache", {})
    monkeypatch.setattr(R, "_contacts_cache", {})
    md = tmp_path / "clients.md"
    md.write_text(ROSTER, encoding="utf-8")
    real_roster, real_ils = BM.read_roster, BM.read_ils_roster
    monkeypatch.setattr(BM, "read_roster", lambda path=None: real_roster(str(md)))
    monkeypatch.setattr(BM, "read_ils_roster", lambda path=None: real_ils(str(md)))
    monkeypatch.setattr(BM, "read_cashplease_roster", lambda path=None: [])
    ils = tmp_path / "Inputs" / "ILS Analysis"
    (ils / "_schedule").mkdir(parents=True)
    (ils / "_schedule" / "current_scheduled_analysis.csv").write_text(
        "fi_id,fi_name,review_date,tentative_date,pull_by,status,csm,consultant\n"
        f"7102,7102 - Birch CU,{REVIEW},,,Data Ready,A Csm,\n7104,Dune FCU,{REVIEW},,,Confirmed,A Csm,\n", encoding="utf-8")
    (ils / "_schedule" / "pulls.json").write_text(json.dumps({"written": "2026-11-24T08:20:00", "schedule": {}, "clients": {
        "7102": {"name": "Birch CU", "review_date": REVIEW, "pull": PULL, "current": True, "problem": None, "differs": [],
                 "landed_kinds": ["zaccounts", "ztrend"], "reason": "pulled 20 days before the review"}}}), encoding="utf-8")
    pull = ils / "7102" / PULL
    pull.mkdir(parents=True)
    for k in ("zaccounts", "ztrend"):
        with zipfile.ZipFile(pull / f"7102_{k}_{PULL}.csv.zip", "w") as z:
            z.writestr(f"7102_{k}_{PULL}.csv", "acct,bal\n1,2\n")
    (tmp_path / "Inputs" / "ILS PGL" / "7103").mkdir(parents=True)
    monkeypatch.setattr(W, "_selected", {"period": None})
    return tmp_path


def served(monkeypatch, doc):
    monkeypatch.setitem(W._clients, "doc", doc)
    monkeypatch.setattr(W, "_status_cache", {})
    monkeypatch.setattr(W, "_jobs", {})
    return {c["id"]: c for c in W._served_clients()["clients"]}


# ------------------------------------------------------------------ the lists
def test_rpe_decks_leave_out_ils_only_clients_and_ils_decks_list_every_ils_client(root, monkeypatch):
    rows = served(monkeypatch, W.compute_clients())
    rpe = {cid for cid, c in rows.items() if not c["ils_only"]}
    ils = {cid for cid, c in rows.items() if c.get("ils")}
    assert rpe == {"7101", "7104"}, "RPE Decks: an RPE program only"
    assert ils == {"7102", "7103", "7104", "7105"}, "scheduled, landed and roster clients"
    assert {cid for cid, c in rows.items() if c["ils_only"]} == {"7102", "7103", "7105"}
    assert "ils" not in rows["7101"]
    # a client on both keeps its RPE state untouched by the ILS one
    assert rows["7104"]["ils"]["state"] == "waiting" and rows["7104"]["ils"]["rpe"] is True and rows["7104"]["programs"] == ["ARS"]


def test_each_ils_row_carries_what_the_tab_shows(root, monkeypatch):
    rows = served(monkeypatch, W.compute_clients())
    b = rows["7102"]["ils"]
    assert (b["state"], b["ready"], b["review_date"], b["review_status"], b["pull"]) == ("ready", True, REVIEW, "Data Ready", PULL)
    assert b["scheduled"] and not b["roster"] and b["landed"] == []
    assert rows["7103"]["ils"]["landed"] == ["pgl"] and rows["7103"]["ils"]["state"] == "not_scheduled"
    assert rows["7105"]["ils"]["roster"] and rows["7105"]["name"] == "Elm Bank"
    assert rows["7105"]["csm"] == "A Csm", "a roster client's CSM comes from the ILS roster when the CSM List lacks it"


def test_the_csm_filter_is_the_rpe_lists(root, monkeypatch):
    """The page filters both lists on the one CSM select, by the row's `csm`."""
    rows = served(monkeypatch, W.compute_clients())
    mine = {cid for cid, c in rows.items() if c.get("ils") and c["csm"] == "A Csm"}
    assert mine == {"7102", "7104", "7105"} and {cid for cid, c in rows.items() if c.get("ils") and c["csm"] == "B Csm"} == {"7103"}
    page = H.PAGE
    base = page[page.index("function base()"):page.index("function listed()")]
    assert '$("#csm").value' in base and "c.csm === csm" in base and "c.ils" in base


def test_the_badge_counts_ready_reviews_with_no_deck_for_this_review(root, monkeypatch):
    from sheila_mcp import core
    rows = served(monkeypatch, W.compute_clients())
    ready = [cid for cid, c in rows.items() if c.get("ils") and c["csm"] == "A Csm" and core.ils_word(c["ils"]) == "ready to build"]
    assert ready == ["7102"]
    rows["7102"]["ils"]["decks"] = ["7102-2026.11-ILS-ANL-Birch CU ILS Analysis.pptx"]
    assert core.ils_word(rows["7102"]["ils"]) == "in Outputs"
    badge = H.PAGE[H.PAGE.index("function paintIlsBadge()"):]
    assert 'ilsKind(c).k === "ready"' in badge[:600] and "(!csm || c.csm === csm)" in badge[:600]


def test_an_unreadable_share_reads_every_ils_row_as_not_checked_never_ready(root, monkeypatch):
    monkeypatch.setattr(RR, "share_readable", lambda: False)
    monkeypatch.setattr(RR, "readiness", lambda cid: pytest.fail("nothing is read off a share that cannot be read"))
    out = W.ils_clients({})
    assert set(out) == {"7104", "7105"}, "the roster is clients.md's, so its rows are still listed"
    for e in out.values():
        st = e["state"]
        assert st["checked"] is False and st["ready"] is False and st["state"] == "unknown"


def test_a_failing_readiness_reads_not_checked(root, monkeypatch):
    def boom(cid):
        raise RuntimeError("synthetic")
    monkeypatch.setattr(RR, "readiness", boom)
    rows = served(monkeypatch, W.compute_clients())
    assert rows["7102"]["ils"]["checked"] is False and rows["7102"]["ready"] is False


def test_ils_list_rows_takes_the_csm_list_then_the_roster_then_the_schedule():
    rows = W.ils_list_rows({"7201": {"name": "Sched Name", "csm": "S Csm"}, "7202": {"name": "Only Sched", "csm": "S Csm"}},
                           {"7203": ["kickoff", "pgl"]},
                           [{"client_id": "7201", "client_name": "Roster Name", "csm": "R Csm"}],
                           {"7201": {"client_name": "List Name", "csm": "L Csm"}})
    assert list(rows) == ["7201", "7202", "7203"]
    assert (rows["7201"]["name"], rows["7201"]["csm"]) == ("List Name", "L Csm")
    assert (rows["7202"]["name"], rows["7202"]["csm"]) == ("Only Sched", "S Csm")
    assert rows["7203"] == {"name": "7203", "csm": "", "scheduled": False, "landed": ["kickoff", "pgl"], "roster": False}


def test_landed_by_kind_names_each_kind_a_client_has(root):
    import ils_runs
    (root / "Inputs" / "ILS Kickoff" / "7103").mkdir(parents=True)
    (root / "Inputs" / "ILS PGL" / "7106_Fir Bank_PGL_20261101.zip").write_bytes(b"")
    assert ils_runs.landed_by_kind() == {"7103": ["kickoff", "pgl"], "7106": ["pgl"]}
    assert ils_runs.landed_clients() == {"7103", "7106"}


def test_an_ils_only_client_is_never_given_rpe_checks_in_the_background(monkeypatch):
    doc = {"period": "2026.11", "clients": [{"id": "7101", "ils_only": False}, {"id": "7102", "ils_only": True}]}
    monkeypatch.setitem(W._clients, "doc", doc)
    monkeypatch.setattr(W, "_status_cache", {})
    checked = []
    monkeypatch.setattr(W, "_check_status", lambda cid: checked.append(cid))
    W._renew_statuses()
    assert checked == ["7101"]


# ------------------------------------------------------------------ the page
def test_the_sidebar_has_rpe_decks_and_ils_decks_with_their_addresses():
    page = H.PAGE
    side = page[page.index('<nav class="nav" aria-label="Views">'):page.index("</nav>")]
    assert ">RPE Decks<" in side and ">ILS Decks<" in side and ">Decks<" not in side
    assert side.index('data-tab="decks" href="#"') < side.index('data-tab="ils" href="#ils"') < side.index('data-tab="lift"'), "ILS Decks right below RPE Decks"
    assert 'id="b-ils"' in side
    bar = page[page.index('<nav class="tabbar"'):]
    bar = bar[:bar.index("</nav>")]
    assert 'data-tab="ils" href="#ils"' in bar and ">RPE</a>" in bar and ">ILS</a>" in bar
    assert 'decks: "RPE Decks", ils: "ILS Decks"' in page and "<h1>RPE Decks</h1>" in page
    assert page.count('id="v-ils"') == 1 and 'registerTab("ils"' in page and "sheila_hub_ilsdecks" in H.TAB_MODULES
    assert '"G then S for ILS Decks' in page or "G then S for ILS Decks" in page


def test_rpe_decks_list_tiles_overview_and_badge_count_rpe_clients_only():
    page = H.PAGE
    assert "const rpeClients = () => CLIENTS.filter(c => !c.ils_only);" in page
    for fn, nxt in (("function visible()", "function running()"), ("function renderKpis()", "function renderList()"),
                    ("function renderOverview()", "// ------------------------------------------------------------ client detail")):
        body = page[page.index(fn):page.index(nxt)]
        assert "rpeClients()" in body and "CLIENTS.filter" not in body, fn


def test_the_ils_state_mapping_never_reads_ready_when_not_checked():
    page = H.PAGE
    k = page[page.index("function ilsKind(c)"):page.index("const rowKind")]
    assert k.index("if (!s.checked)") < k.index('s.state === "ready"'), "not checked is decided first"
    assert '(s.decks || []).length ? {k: "outputs"' in k, "this review's deck in Outputs is In Outputs, not Ready"
    for label in ("Blocked · waiting for ILS data", "Blocked · ILS data problem", "No review scheduled", "Not checked"):
        assert label in k


def test_an_ils_only_clients_page_leads_with_the_ils_cards():
    page = H.PAGE
    d = page[page.index("function renderDetail()"):page.index("// ------------------------------------------------------------ building")]
    assert 'c.ils_only ? `<div id="ilscards"></div>' in d
    assert "TABS[TAB].closed" in page and 'appendChild(d)' in page and '$("#il-host")' in page


def test_a_row_opens_the_client_page_in_the_tab_and_the_address_names_it():
    page = H.PAGE
    m = page[page.index("// ------------------------------------------------------------ ILS Decks"):]
    assert "setTabParams({client: id})" in m and "openClient(id)" in m and "tr[data-ilid]" in m


# ------------------------------------------------------------------ Sheila in Claude
def test_sheila_in_claude_says_which_list_a_client_is_on(monkeypatch):
    from sheila_mcp import core
    rows = [{"id": "7101", "name": "Alpine Bank", "csm": "A Csm", "covered": ["ARS"], "ils_only": False},
            {"id": "7102", "name": "Birch CU", "csm": "A Csm", "covered": [], "ils_only": True,
             "ils": {"checked": True, "state": "ready", "decks": [], "review_date": REVIEW}},
            {"id": "7104", "name": "Dune FCU", "csm": "A Csm", "covered": ["ARS"], "ils_only": False,
             "ils": {"checked": False, "state": "unknown"}}]
    monkeypatch.setattr(core, "all_clients", lambda: {"period": "2026.11", "clients": rows})
    monkeypatch.setattr(core.who, "resolve_csm", lambda csm: "A Csm")
    monkeypatch.setattr(core, "web", lambda: W)
    lists = {c["id"]: c["list"] for c in core.clients("me")["data"]["clients"]}
    assert lists == {"7101": "RPE Decks", "7102": "ILS Decks", "7104": "RPE Decks and ILS Decks"}
    r = core.my_month("me", check=False)
    flat = [x["id"] for g in r["data"]["groups"].values() for x in g]
    assert "7102" not in flat and sorted(flat) == ["7101", "7104"], "a client on ILS alone is not in the RPE groups"
    ils = {x["id"]: x["review"] for x in r["data"]["ils"]}
    assert ils == {"7102": "ready to build", "7104": "not checked"}
    assert "ILS Decks (2)" in r["answer"]
