"""Live Review opened from CSM Sheila (prototype; Aaron, 2026-11-06).

The server runs inside Sheila's own process on a thread, never as a queued build, so a CSM presenting for an hour does
not hold the PC's build lock. These tests pin: the readiness block (file presence only, never a model build), the
routes' validation, one server per client that a repeat Open reuses and Stop ends, the audit still refusing an untraced
figure, ILS held back whether or not this build of Live Review has it, and that a peer comparison reaching the browser
through Sheila carries no other client's name.

Every pack is synthetic (an invented client 9999 and invented peers); nothing reads the share.
"""
import http.client
import json
import os
import sys
import time

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "scripts"), os.path.join(REPO, "build"), os.path.join(REPO, "build", "ars_pipeline")]

import live_review_ui as LU                                   # noqa: E402
from review_page import registry                              # noqa: E402

from test_live_review import CID, PERIOD, make_pack           # noqa: E402
from test_live_review_peers import PEER_IDS, PEER_NAMES       # noqa: E402


@pytest.fixture
def root(tmp_path, monkeypatch):
    """A pipeline root with an empty Inputs/ and Outputs/ and a Build Artifacts/ that holds client 9999's ARS pack."""
    for d in ("Inputs", "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir()
    make_pack(tmp_path / "Build Artifacts")
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    yield tmp_path
    LU.stop_all()


def wait_for(cid, states, seconds=60):
    end = time.time() + seconds
    while time.time() < end:
        d = LU.state_doc(cid)
        if d["state"] in states:
            return d
        time.sleep(0.1)
    raise AssertionError("still %s after %ss" % (LU.state_doc(cid)["state"], seconds))


def get(url, path="/", token=None, host=None):
    port = int(url.rstrip("/").rsplit(":", 1)[1])
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {}
    if token:
        headers["X-Token"] = token
    if host:
        headers["Host"] = host
    c.request("GET", path, headers=headers)
    r = c.getresponse()
    data = r.read()
    c.close()
    return r.status, data


# ----------------------------------------------------------------- readiness
def test_readiness_is_file_presence_and_names_what_is_missing(root):
    st = LU.status(CID, PERIOD, ["ARS", "ICS"])
    assert st["state"] == "ready" and st["programs"] == ["ARS"]
    text = " ".join(c["text"] for c in st["checks"])
    assert "ARS: the 2026.10 deck build's data pack is on hand" in text
    assert "ICS: no VIP sheet" in text                      # a program with no data is named, not a failure


def test_nothing_on_hand_is_a_stop_that_says_so(root):
    st = LU.status("9998", PERIOD, ["ARS"])
    assert st["state"] == "stop" and st["programs"] == []
    assert st["checks"][0]["level"] == "stop" and "nothing to present" in st["checks"][0]["text"]


def test_an_id_that_is_not_a_client_number_cannot_build_a_path(root):
    with pytest.raises(ValueError):
        LU.status("../x", PERIOD, ["ARS"])


# ----------------------------------------------------------------- routes
class Handler:
    def __init__(self):
        self.sent = None

    def _send(self, code, body, *a, **k):
        self.sent = (code, body)


@pytest.mark.parametrize("path,body", [
    ("/api/live/open", {"client": "../x", "period": "2026.10"}),
    ("/api/live/open", {"client": "9999", "period": "tomorrow"}),
    ("/api/live/open", {"client": "", "period": "2026.10"}),
    ("/api/live/stop", {"client": "abc"}),
])
def test_routes_refuse_what_is_not_an_id_or_a_period(path, body):
    h = Handler()
    LU.post(h, path, body)
    assert h.sent[0] == 400


def test_get_state_validates_the_client_and_unknown_routes_are_404():
    h = Handler()
    LU.get(h, "/api/live/state", {"client": "nope"})
    assert h.sent[0] == 400
    LU.get(h, "/api/live/other", {"client": "9999"})
    assert h.sent[0] == 404
    LU.post(h, "/api/live/other", {"client": "9999"})
    assert h.sent[0] == 404


def test_sheila_serves_the_routes_behind_its_token():
    src = open(os.path.join(REPO, "scripts", "ars_launcher_web.py"), encoding="utf-8").read()
    assert src.count('startswith("/api/live/")') == 2       # one GET, one POST, both after the token check
    assert "review_page" not in src                          # Sheila reaches it only through live_review_ui


# ----------------------------------------------------------------- the server
def test_open_serves_the_page_reuses_it_and_stop_ends_it(root):
    opened = []
    code, doc = LU.open_page(CID, PERIOD, opener=opened.append)
    assert code == 202 and doc["state"] == "starting"
    ready = wait_for(CID, {"ready", "failed"})
    assert ready["state"] == "ready", ready
    url = ready["url"]
    assert url.startswith("http://127.0.0.1:") and opened == [url]        # opened server-side, in this PC's browser
    status, page = get(url)
    assert status == 200 and b"Live Review" in page
    assert get(url, "/api/model")[0] == 403                               # no token, no data
    assert get(url, "/", host="evil.example")[0] == 403                   # a name other than 127.0.0.1 is refused

    code2, doc2 = LU.open_page(CID, PERIOD, opener=opened.append)         # a second Open reuses the server
    assert code2 == 200 and doc2["url"] == url and opened == [url, url]

    h = Handler()
    LU.post(h, "/api/live/stop", {"client": CID})
    assert h.sent == (200, {"stopped": True, "client": CID, "state": "idle"})
    assert LU.state_doc(CID)["state"] == "idle"
    with pytest.raises(OSError):
        get(url)


def test_a_figure_that_does_not_trace_is_never_served(root, monkeypatch):
    monkeypatch.setattr(registry, "audit", lambda model, t: ["number not in any pack or derivation: 1.0 at x"])
    LU.open_page(CID, PERIOD, opener=lambda u: pytest.fail("opened a page that failed its audit"))
    d = wait_for(CID, {"ready", "failed"})
    assert d["state"] == "failed" and d["url"] is None
    assert "do not trace" in d["error"] and d["problems"] == ["number not in any pack or derivation: 1.0 at x"]


def test_a_crash_building_the_model_is_shown_not_raised(root, monkeypatch):
    def boom(*a, **k):
        raise OSError("the share went away")
    monkeypatch.setattr(registry, "build_model", boom)
    LU.open_page(CID, PERIOD, opener=lambda u: None)
    d = wait_for(CID, {"ready", "failed"})
    assert d["state"] == "failed" and "the share went away" in d["error"]


def test_a_period_change_replaces_the_servers_and_the_number_is_capped(root, monkeypatch):
    def fake(s, opener):
        s.state, s.url = "ready", "http://127.0.0.1:1/"
    monkeypatch.setattr(LU, "_work", fake)
    monkeypatch.setattr(LU, "MAX_OPEN", 2)
    for cid in ("1001", "1002", "1003"):
        LU.open_page(cid, PERIOD, opener=lambda u: None)
        time.sleep(0.01)
    assert LU.state_doc("1001")["state"] == "idle"                        # the oldest made room
    assert LU.state_doc("1002")["state"] == "ready" and LU.state_doc("1003")["state"] == "ready"
    LU.open_page("1003", "2026.09", opener=lambda u: None)                # another period starts afresh, one entry per client
    assert LU.state_doc("1003")["period"] == "2026.09" and len(LU._sessions) == 2


def test_ils_is_held_back_whether_or_not_this_build_has_it(monkeypatch):
    assert "ils" not in LU.programs()
    monkeypatch.setattr(registry, "REGISTRY", registry.REGISTRY + [("ils", "ILS", "ils")])
    assert "ils" not in LU.programs() and "ars" in LU.programs()


def test_it_never_takes_the_build_lock_or_queues_a_job():
    src = open(os.path.join(REPO, "scripts", "live_review_ui.py"), encoding="utf-8").read()
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    body = code.split('"""', 2)[2]                                          # past the module docstring
    for needle in ("build.lock", "_take_build_lock", "subprocess", "Popen", "start_build", "Outputs", "deliveries.json"):
        assert needle not in body, needle


# ----------------------------------------------------------------- peers through Sheila: client numbers, never names
def test_peer_comparisons_reach_the_browser_with_no_other_clients_name(root):
    packs = root / "Build Artifacts" / "cashplease" / "packs"
    packs.mkdir(parents=True)

    def pack(cid, name, per_1k):
        months = [{"period_month": f"2026-{m:02d}", "loans": 100 + m, "principal": 40000.0 + m, "interest": 1000.0 + m,
                   "funded": 90, "paid_off": 10, "overdue": 0, "charged_off": 0} for m in range(1, 10)]
        return {"client_id": cid, "client_name": name, "source_file": "CashPleaseSummaryV1_261012_090000.xlsx", "dda_sent": None,
                "report_generated": "10/12/2026 8:57:13 AM", "charge_off_pct": 0.04, "cancelled": None,
                "status": {"Funded": {"principal": 1.0, "interest": 1.0, "loans": 50}, "Paid Off": {"principal": 9.0, "interest": 2.0, "loans": 500}},
                "total": {"principal": 10.0, "interest": 3.0, "loans": 550}, "monthly": months,
                "metrics": {"total_loans": 550, "total_principal": 10.0, "active_loans": 50, "active_principal": 1.0, "avg_loan_size": 40.0,
                            "pct_loans_overdue": 0.01, "peer_comparable": True, "loans_per_1k_dda": per_1k, "dda_accounts": 1000,
                            "window_loans": 1200}}
    (packs / f"{CID}_cashplease.json").write_text(json.dumps(pack(CID, "Test Bank", 40.0)), encoding="utf-8")
    for i, (cid, nm) in enumerate(zip(PEER_IDS[:6], PEER_NAMES[:6])):
        (packs / f"{cid}_cashplease.json").write_text(json.dumps(pack(cid, nm, 20.0 + 3 * i)), encoding="utf-8")
    LU.open_page(CID, PERIOD, opener=lambda u: None)
    d = wait_for(CID, {"ready", "failed"})
    assert d["state"] == "ready", d
    status, page = get(d["url"])
    text = page.decode("utf-8")
    assert status == 200 and "Zephyrville" not in text and all(nm not in text for nm in PEER_NAMES[:6])
    assert PEER_IDS[0] in text                                              # the client number is what a peer dot carries
