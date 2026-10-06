"""The browser front end for ars_launcher: who may call it, and that a build job reports back (2026-09-15)."""
import http.client
import json
import os
import sys
import threading
import time

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "scripts"), os.path.join(REPO, "build")]
import ars_launcher_web as W  # noqa: E402

CLIENTS_DOC = W.clients_doc   # the real one, before the server fixture replaces it


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setattr(W, "clients_doc", lambda: {"period": "2026.09", "clients": [{"id": "1441", "name": "FNB Alaska"}]})
    monkeypatch.setattr(W, "compute_status", lambda cid: {"client": cid, "state": "ready", "checks": []})
    W._jobs.clear()
    W._queue.clear()
    W._status_cache.clear()
    srv = W.make_server(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1]
    srv.shutdown()
    W._jobs.clear()


def call(port, method, path, body=None, token=True, host=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Token"] = W.TOKEN
    if host:
        headers["Host"] = host
    c.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
    r = c.getresponse()
    data = r.read()
    c.close()
    return r.status, data


def test_the_page_carries_its_token(server):
    status, data = call(server, "GET", "/", token=False)
    assert status == 200 and W.TOKEN.encode() in data


def test_the_api_refuses_a_call_without_the_token(server):
    assert call(server, "GET", "/api/clients", token=False)[0] == 403
    assert call(server, "POST", "/api/build", {"client": "1441"}, token=False)[0] == 403
    assert call(server, "GET", "/api/clients")[0] == 200


def test_a_refused_post_is_answered_not_reset(server):
    """A POST refused for want of the token used to be answered before its body was read, and
    Windows reset the connection: ConnectionAbortedError instead of 403, in about 6% of calls
    with a 100 KB body, and now and then in the test above under a loaded full run
    (2026-10-02). The server reads the body first now."""
    body = {"client": "1441", "pad": "x" * 100_000}
    assert {call(server, "POST", "/api/build", body, token=False)[0] for _ in range(300)} == {403}


def test_a_post_over_the_size_cap_is_refused(server):
    c = http.client.HTTPConnection("127.0.0.1", server, timeout=10)
    c.putrequest("POST", "/api/build")
    c.putheader("Content-Length", str(W.MAX_POST_BYTES + 1))
    c.putheader("X-Token", W.TOKEN)
    c.endheaders()
    assert c.getresponse().status == 413
    c.close()


def test_the_api_refuses_a_foreign_host_header(server):
    # DNS rebinding: a page on another name resolving to 127.0.0.1 still sends its own Host.
    assert call(server, "GET", "/api/clients", host="evil.example:80")[0] == 403
    assert call(server, "GET", "/", token=False, host="evil.example")[0] == 403


def test_a_bad_client_number_is_rejected(server):
    assert call(server, "GET", "/api/status?client=abc")[0] == 400
    assert call(server, "POST", "/api/build", {"client": "1441; del"})[0] == 400


def test_a_build_job_streams_its_lines_and_names_the_deck(server, monkeypatch):
    deck = r"\\srv\CSM_Reporting\Outputs\James Gilmore\1441-2026.09-ARS-FNB Alaska ARS Results.pptx"
    script = ("import time\n"
              "print('  [..]   Reading the ODD extract  (0 min)', flush=True)\n"
              "time.sleep(0.3)\n"
              f"print('  [ok]   In Outputs: {deck.replace(chr(92), chr(92) * 2)} (1 older file(s) archived, none deleted)')\n")
    monkeypatch.setattr(W, "build_cmd", lambda cid, rebuild, combined=False, period=None: [sys.executable, "-c", script])
    status, data = call(server, "POST", "/api/build", {"client": "1441"})
    assert status == 202
    for _ in range(100):
        job = json.loads(call(server, "GET", "/api/job?client=1441")[1])
        if job.get("done"):
            break
        time.sleep(0.1)
    assert job["done"] and job["code"] == 0
    assert any("Reading the ODD extract" in l for l in job["lines"])
    assert job["deck"] == deck


def test_a_second_build_queues_behind_the_running_one(server, monkeypatch):
    """Builds run one at a time; the next waits its turn instead of being refused (2026-09-16)."""
    script = "import time, sys\ntime.sleep(0.6)\nprint('  [ok]   built', sys.argv[1], flush=True)\n"
    monkeypatch.setattr(W, "build_cmd", lambda cid, rebuild, combined=False, period=None: [sys.executable, "-c", script, cid])
    assert call(server, "POST", "/api/build", {"client": "1441"})[0] == 202
    status, data = call(server, "POST", "/api/build", {"client": "1453"})
    assert status == 202 and json.loads(data)["queued"] == 1
    third = json.loads(call(server, "POST", "/api/build", {"client": "1487"})[1])
    assert third["queued"] == 2
    assert call(server, "POST", "/api/build", {"client": "1453"})[0] == 409, "a client already queued is not queued twice"
    q = json.loads(call(server, "GET", "/api/queue")[1])
    assert q["queued"] == ["1453", "1487"] and q["building"] in ("1441", None)
    for _ in range(100):
        jobs = [json.loads(call(server, "GET", f"/api/job?client={c}")[1]) for c in ("1441", "1453", "1487")]
        if all(j.get("done") for j in jobs):
            break
        time.sleep(0.1)
    assert all(j["done"] and j["code"] == 0 for j in jobs)
    first_end = [W._jobs[c] for c in ("1441", "1453", "1487")]
    assert first_end[0].finished <= first_end[1].started and first_end[1].finished <= first_end[2].started, "one at a time, in order"
    assert json.loads(call(server, "GET", "/api/queue")[1]) == {"building": None, "queued": []}


def test_the_error_pill_follows_the_last_build(tmp_path, monkeypatch):
    """Red "Error <period>" in the list: the last build was not put in Outputs (2026-09-16)."""
    monkeypatch.setattr(W.R, "build_artifacts", lambda: tmp_path)
    W._jobs.clear()
    rec = tmp_path / "launcher" / "2026.09" / "1121" / "_launcher_result.json"
    assert not W.last_build_failed("1121", "2026.09"), "no build yet is not an error"
    rec.parent.mkdir(parents=True)
    rec.write_text(json.dumps({"result": "stopped at metrics_gen", "delivered": False}), encoding="utf-8")
    assert W.last_build_failed("1121", "2026.09")
    deck = tmp_path / "1121-2026.09-ARS-Timberland Bank ARS Results.pptx"
    deck.write_bytes(b"x")
    os.utime(deck, (rec.stat().st_mtime + 60,) * 2)
    assert not W.last_build_failed("1121", "2026.09", [deck]), "a deck that reached Outputs later clears it"
    rec.write_text(json.dumps({"result": "0 FAIL", "delivered": True}), encoding="utf-8")
    assert not W.last_build_failed("1121", "2026.09")
    job = W.Job("1121", False)
    W._jobs["1121"] = job
    assert not W.last_build_failed("1121", "2026.09"), "queued or running is not an error"
    job.done, job.code = True, 1
    assert W.last_build_failed("1121", "2026.09"), "a remembered failed job wins over the record"
    W._jobs.clear()


def test_a_status_is_served_from_the_cache_until_fresh_is_asked_or_a_build_finishes(monkeypatch):
    calls = []
    monkeypatch.setattr(W, "compute_status", lambda cid: calls.append(cid) or {"client": cid, "state": "ready", "checks": []})
    W._status_cache.clear()
    W._jobs.clear()
    W.status_doc("1441")
    second = W.status_doc("1441")
    assert calls == ["1441"] and second["age_seconds"] >= 0 and "job" in second
    W.status_doc("1441", fresh=True)
    assert calls == ["1441", "1441"], "Check again must re-read"
    W.forget_status("1441")
    W.status_doc("1441")
    assert len(calls) == 3, "a finished build drops the cached status"
    monkeypatch.setattr(W, "STATUS_TTL", 0)
    W.status_doc("1441")
    assert len(calls) == 4, "an entry older than the TTL is re-read"
    W._status_cache.clear()


def test_reveal_only_opens_a_deck_under_outputs(tmp_path, monkeypatch):
    out = tmp_path / "Outputs"
    (out / "James Gilmore").mkdir(parents=True)
    deck = out / "James Gilmore" / "1441-2026.09-ARS-FNB Alaska ARS Results.pptx"
    deck.write_bytes(b"x")
    outside = tmp_path / "secret.txt"
    outside.write_bytes(b"x")
    monkeypatch.setattr(W.R, "outputs", lambda: out)
    opened = []
    monkeypatch.setattr(W.subprocess, "Popen", lambda args, **kw: opened.append(args))
    assert W.reveal(str(outside))[0] == 403
    assert W.reveal(str(out / ".." / "secret.txt"))[0] == 403
    assert W.reveal(str(deck))[0] == 200 and opened


def test_the_combined_button_runs_the_launcher_with_combined():
    """The second button (Aaron, 2026-09-16) builds ARS plus every other program with its data."""
    assert W.build_cmd("1776", False, True)[-1] == "--combined"
    assert "--combined" not in W.build_cmd("1776", True)
    # every build names its cycle, so a past-cycle rebuild cannot land under this month
    assert "--period" in W.build_cmd("1776", False)
    job = W.Job("1776", False, True)
    assert job.to_json()["combined"] is True

def test_the_changelog_shows_the_newest_five_entries(tmp_path):
    """Header "What's new" and the /changelog page (Aaron, 2026-09-16)."""
    md = tmp_path / "CHANGELOG.md"
    md.write_text("# Changelog\n\n## Unreleased\n\n"
                  + "".join(f"### 2026-09-{d:02d} — Entry **{d}**\n\nFirst `para` {d}.\nstill first.\n\nSecond para.\n\n"
                            for d in range(20, 13, -1)), encoding="utf-8")
    e = W.changelog_entries(5, md)
    assert [x["date"] for x in e] == ["2026-09-20", "2026-09-19", "2026-09-18", "2026-09-17", "2026-09-16"]
    assert e[0]["title"] == "Entry 20" and e[0]["summary"] == "First para 20. still first." and e[0]["anchor"] == "e0"
    page = W.changelog_page(md)
    assert '<h3 id="e0">' in page and "<code>para</code>" in page and "<b>20</b>" in page


def test_the_changelog_page_is_served_without_the_token(server):
    status, data = call(server, "GET", "/changelog", token=False)
    assert status == 200 and b"Change log" in data
    assert call(server, "GET", "/api/changelog", token=False)[0] == 403
    status, data = call(server, "GET", "/api/changelog")
    assert status == 200 and len(json.loads(data)["entries"]) <= 5


# ------------------------------------------------------------------ faster refresh (Aaron, 2026-09-17)
def wait_for(cond, seconds=5):
    end = time.time() + seconds
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


@pytest.fixture
def clean_state():
    def reset():
        W._jobs.clear()
        W._queue.clear()
        W._status_cache.clear()
        W._status_gen.clear()
        W._status_busy.clear()
        W._results.clear()
        W._clients.update(doc=None, at=0.0, gen=0, clean_gen=-1, busy=None, error=None)
    reset()
    yield
    wait_for(lambda: W._clients["busy"] is None and not W._status_busy)
    reset()


def listing(period="2026.09", decks=(), error=False, sent=None):
    return {"period": period, "lift_pending": False, "clients": [
        {"id": "1441", "name": "FNB Alaska", "csm": "James Gilmore", "programs": ["ARS"], "path": "MM",
         "sent": sent, "decks": list(decks), "lift_expired": False, "error": error, "result_written": None}]}


def test_the_list_is_served_from_memory_and_rebuilt_behind_the_page(clean_state, monkeypatch):
    gate = threading.Event()
    docs = [listing(), listing(decks=["1441-2026.09-ARS-FNB Alaska ARS Results.pptx"])]
    calls = []

    def compute():
        calls.append(1)
        if len(calls) > 1:
            gate.wait(5)
        return docs[min(len(calls), 2) - 1]
    monkeypatch.setattr(W, "compute_clients", compute)
    first = W.clients_doc()
    assert len(calls) == 1 and first["refreshing"] is False and first["age_seconds"] == 0
    assert "result_written" not in first["clients"][0]
    W.clients_doc()
    assert len(calls) == 1, "a list younger than CLIENTS_TTL is not rebuilt"
    monkeypatch.setattr(W, "CLIENTS_TTL", 0)
    t0 = time.time()
    served = W.clients_doc()
    assert time.time() - t0 < 1, "an old list is served at once, not waited for"
    assert served["refreshing"] is True and served["clients"][0]["decks"] == []
    gate.set()
    assert wait_for(lambda: W._clients["busy"] is None)
    assert len(calls) == 2
    monkeypatch.setattr(W, "CLIENTS_TTL", 600)
    assert W.clients_doc()["clients"][0]["decks"] == ["1441-2026.09-ARS-FNB Alaska ARS Results.pptx"]


def test_the_list_marks_a_client_ready_only_from_a_current_ready_status(clean_state, monkeypatch):
    monkeypatch.setattr(W, "compute_clients", lambda: listing())
    now = time.time()
    status = lambda state, period="2026.09": {"client": "1441", "state": state, "period": period}
    for stored, want in [((now, status("ready")), True),
                         ((now, status("ask")), False),      # a deck is already in Outputs
                         ((now, status("stop")), False),
                         ((now, status("ready", "2026.08")), False),   # another cycle
                         ((now - W.STATUS_TTL - 1, status("ready")), False),   # an old "ready"
                         (None, False)]:
        W._status_cache.clear()
        if stored:
            W._status_cache["1441"] = stored
        assert W.clients_doc()["clients"][0]["ready"] is want, stored


def test_a_finished_build_shows_in_the_list_before_the_refresh(clean_state, monkeypatch):
    """Error and In Outputs follow this server's own builds live; the stored list is rebuilt after."""
    calls = []
    monkeypatch.setattr(W, "compute_clients", lambda: calls.append(1) or listing(error=True))
    W.clients_doc()
    job = W.Job("1441", False)
    W._jobs["1441"] = job
    assert W.clients_doc()["clients"][0]["error"] is False, "queued or running is not an error"
    job.lines = [r"  [ok]   In Outputs: \\srv\Outputs\James Gilmore\1441-2026.09-ARS-FNB Alaska ARS Results.pptx"]
    job.done, job.code = True, 0
    row = W.clients_doc()["clients"][0]
    assert row["error"] is False and row["decks"] == ["1441-2026.09-ARS-FNB Alaska ARS Results.pptx"]
    W.invalidate_clients()
    assert wait_for(lambda: len(calls) == 2), "a finished build rebuilds the stored list"
    job.code = 1
    job.lines = ["  [STOP] Validation: 2 FAIL"]
    row = W.clients_doc()["clients"][0]
    assert row["error"] is True and row["decks"] == []


def test_a_changed_list_row_drops_that_clients_cached_status(clean_state, monkeypatch):
    """A deck built, or a send recorded, from anywhere else is re-checked on the client's next view."""
    docs = iter([listing(), listing(sent="2026-09-17")])
    monkeypatch.setattr(W, "compute_clients", lambda: next(docs))
    W.refresh_clients()
    W._status_cache["1441"] = (time.time(), {"client": "1441", "state": "ready", "checks": []})
    W._status_cache["1453"] = (time.time(), {"client": "1453", "state": "ready", "checks": []})
    W.refresh_clients()
    assert "1441" not in W._status_cache and "1453" in W._status_cache


def test_the_first_list_waits_and_a_failed_refresh_keeps_the_last_list(clean_state, monkeypatch):
    def fail(e):
        def f():
            raise e
        return f
    monkeypatch.setattr(W, "compute_clients", fail(SystemExit("RPE_DATA_ROOT is not set")))
    with pytest.raises(SystemExit):
        W.clients_doc()
    monkeypatch.setattr(W, "compute_clients", lambda: listing())
    assert W.clients_doc()["clients"][0]["id"] == "1441"
    monkeypatch.setattr(W, "compute_clients", fail(OSError("share gone")))
    W.refresh_clients()
    doc = W.clients_doc()
    assert doc["clients"] and "share gone" in doc["refresh_error"], "a failed refresh keeps the last list and says so"
    monkeypatch.setattr(W, "compute_clients", lambda: listing(period=None))
    W.refresh_clients()
    doc = W.clients_doc()
    assert doc["period"] == "2026.09" and "no ARS workbooks" in doc["refresh_error"], "a period that vanishes is a failed read"


def test_an_old_status_is_shown_at_once_with_its_build_buttons_held(clean_state, monkeypatch):
    gate = threading.Event()
    states = iter(["ready", "stop"])

    def compute(cid):
        state = next(states)
        if state == "stop":
            gate.wait(5)
        return {"client": cid, "state": state, "checks": []}
    monkeypatch.setattr(W, "compute_status", compute)
    assert W.status_doc("1441", background=True)["refreshing"] is False
    monkeypatch.setattr(W, "STATUS_TTL", 0)
    t0 = time.time()
    old = W.status_doc("1441", background=True)
    assert time.time() - t0 < 1 and old["state"] == "ready" and old["refreshing"] is True
    assert W.status_doc("1441", background=True)["refreshing"] is True, "one re-check at a time"
    gate.set()
    assert wait_for(lambda: not W._status_busy)
    monkeypatch.setattr(W, "STATUS_TTL", 600)
    new = W.status_doc("1441", background=True)
    assert new["state"] == "stop" and new["refreshing"] is False
    assert "if (HOLD) for (const b of [go, go2])" in W.PAGE, "the page holds the Build buttons meanwhile"


def test_a_check_that_started_before_a_build_finished_is_not_stored(clean_state, monkeypatch):
    gate, started = threading.Event(), threading.Event()

    def compute(cid):
        started.set()
        gate.wait(5)
        return {"client": cid, "state": "ready", "checks": []}
    monkeypatch.setattr(W, "compute_status", compute)
    t = threading.Thread(target=W.status_doc, args=("1441",))
    t.start()
    assert started.wait(5)
    W.forget_status("1441")          # what Job.run does when the build finishes
    gate.set()
    t.join(5)
    assert "1441" not in W._status_cache


def test_the_launcher_results_are_read_once_until_they_change(tmp_path, monkeypatch, clean_state):
    monkeypatch.setattr(W.R, "build_artifacts", lambda: tmp_path)
    base = tmp_path / "launcher" / "2026.09"
    (base / "1121").mkdir(parents=True)
    rec = base / "1121" / W.RESULT_NAME
    rec.write_text(json.dumps({"result": "stopped", "delivered": False}), encoding="utf-8")
    reads = []
    real = W.Path.read_text
    monkeypatch.setattr(W.Path, "read_text", lambda self, *a, **kw: reads.append(self.name) or real(self, *a, **kw))
    got = W.launcher_results("2026.09", ["1121", "1441"])
    assert got["1441"] == (None, None), "a client with no launcher folder is not read at all"
    assert got["1121"][0]["delivered"] is False and reads == [W.RESULT_NAME]
    assert W.last_build_failed("1121", "2026.09", result=got["1121"])
    W.launcher_results("2026.09", ["1121", "1441"])
    assert len(reads) == 1, "an unchanged record is not read again"
    rec.write_text(json.dumps({"result": "0 FAIL", "delivered": True}), encoding="utf-8")
    again = W.launcher_results("2026.09", ["1121"])["1121"]
    assert again[0]["delivered"] is True and len(reads) == 2
    assert not W.last_build_failed("1121", "2026.09", result=again)
    assert W.launcher_results("2026.10", ["1121"]) == {"1121": (None, None)}, "no folder for the period"
    real_stat = W.os.stat

    def dropped(p, *a, **kw):
        if str(p) == str(rec):
            raise OSError(64, "The specified network name is no longer available")
        return real_stat(p, *a, **kw)
    monkeypatch.setattr(W.os, "stat", dropped)
    assert W.result_record(rec)[0]["delivered"] is True, "a dropped share call keeps the last record read"
    monkeypatch.setattr(W.os, "stat", real_stat)
    rec.unlink()
    assert W.result_record(rec) == (None, None), "a record that is gone is gone"


def test_share_answers_are_kept_briefly_and_check_again_reads_past_them():
    calls = []

    def probe(path):
        calls.append(path)
        return len(calls)
    cached = W._ttl(probe, 60)
    assert cached("x") == 1 and cached("x") == 1 and cached("y") == 2
    with W._fresh_reads():
        assert cached("x") == 3, "fresh reads go to the share"
    assert cached("x") == 3, "and refill what they read"
    assert W._ttl(probe, 0)("x") == 4, "an answer older than its TTL is read again"
    fails = []

    def boom():
        fails.append(1)
        raise OSError("share")
    flaky = W._ttl(boom, 60)
    for _ in range(2):
        with pytest.raises(OSError):
            flaky()
    assert len(fails) == 2, "a failure is never kept"
    W.uninstall_share_caches()


def test_the_share_caches_live_only_in_the_web_server():
    """Installed by main(); a build runs `ars_launcher.py build` as its own process, which never sees them."""
    import deck_status as DS
    before = (W.R.vip_manifest, DS.odd_reachable, W.L.cycle_period)
    W.install_share_caches()
    try:
        W.install_share_caches()
        assert W.R.vip_manifest.__wrapped__ is before[0] and W.L.cycle_period.__wrapped__ is before[2]
        assert not hasattr(W.R.vip_manifest.__wrapped__, "__wrapped__"), "installed once"
    finally:
        W.uninstall_share_caches()
    assert (W.R.vip_manifest, DS.odd_reachable, W.L.cycle_period) == before
    assert "install_share_caches" in W.main.__code__.co_names
    assert W.build_cmd("1441", False)[1].endswith("ars_launcher.py"), "builds are a separate process"


def test_a_slow_list_rebuild_never_holds_up_the_page(server, monkeypatch, clean_state):
    gate = threading.Event()
    monkeypatch.setattr(W, "clients_doc", CLIENTS_DOC)
    calls = []

    def compute():
        calls.append(1)
        if len(calls) > 1:
            gate.wait(5)
        return listing()
    monkeypatch.setattr(W, "compute_clients", compute)
    assert call(server, "GET", "/api/clients")[0] == 200
    t0 = time.time()
    status, data = call(server, "GET", "/api/clients?fresh=1")
    assert status == 200 and json.loads(data)["refreshing"] is True
    assert call(server, "GET", "/api/queue")[0] == 200
    assert json.loads(call(server, "GET", "/api/clients")[1])["refreshing"] is True
    assert time.time() - t0 < 2, "served while the rebuild waits on the share"
    gate.set()

def test_the_changelog_shows_what_changed_not_the_request(tmp_path):
    """Aaron, 2026-09-25: "rewrite the change log shown in Sheila to show a summary of what was updated,
    not my verbatim instructions." CHANGELOG.md keeps the request; Sheila shows the Summary line."""
    md = tmp_path / "CHANGELOG.md"
    md.write_text(
        "# Changelog\n\n## Unreleased\n\n"
        "### 2026-09-25 — With a summary\n\nSummary: The Lift Matrix tab opens faster.\n\n"
        'Aaron: "only rescan workbook lift matrix values if the file has changed."\n\n'
        "Each read is stored (Aaron, 2026-09-25) and reused, Aaron: \"make it fast\". Done.\n\n"
        "### 2026-09-24 — Without one\n\n"
        'Aaron, 2026-09-24: "fix the thing."\n\nThe thing was fixed (Aaron: "thanks (really)") today.\n\n',
        encoding="utf-8")
    e = W.changelog_entries(5, md)
    assert e[0]["summary"] == "The Lift Matrix tab opens faster."
    assert e[1]["summary"].startswith("The thing was fixed") and "Aaron" not in e[1]["summary"]
    page = W.changelog_page(md)
    assert '<p class="sum">The Lift Matrix tab opens faster.</p>' in page
    assert "only rescan" not in page and "fix the thing" not in page and "make it fast" not in page
    assert "Each read is stored and reused. Done." in page
    assert "Aaron" not in page.split("<main>", 1)[1]


# ---------------------------------------------- the cycle advances on the 1st, 2026-10-02
def test_the_cycle_is_this_calendar_month():
    """Aaron, 2026-10-02: "sheila needs to auto-advance the cycle on the 1st, so today's
    should show october". It used to be the newest ARS workbook period in Inputs, so on
    2026-10-02 — with no October workbook landed yet — the page still read 2026.09."""
    import datetime as dt
    assert W.L.cycle_period(dt.date(2026, 10, 1)) == "2026.10"
    assert W.L.cycle_period(dt.date(2026, 9, 30)) == "2026.09"
    assert W.L.cycle_period(dt.date(2026, 12, 31)) == "2026.12"
    assert W.L.cycle_period() == dt.date.today().strftime("%Y.%m")


def test_the_menu_offers_this_month_and_the_cycles_with_something_behind_them(monkeypatch, tmp_path):
    """Months with no deck and no workbook are left out: offering a cycle that cannot be read
    or built is an invitation to a blank page."""
    monkeypatch.setattr(W.L, "cycle_period", lambda *a: "2026.10")
    decks = [tmp_path / "1038-2026.09-ARS-Sugar River Bank ARS Results.pptx",
             tmp_path / "1075-2026.07-ARS-ICS-MRPC-Austin Bank Results.pptx"]
    books = [tmp_path / "1038-2026.08-Sugar River-Workbook_v2_1_0.xlsx",
             tmp_path / "1705-2026.09-CoastLife-Invitation Checking Workbook.xlsx"]
    monkeypatch.setattr(W.R, "output_decks", lambda pat: decks)
    monkeypatch.setattr(W.R, "report_files", lambda pat: books)
    assert W.available_periods() == ["2026.10", "2026.09", "2026.08", "2026.07"]
    assert W.available_periods(n=2) == ["2026.10", "2026.09"]


def test_a_future_cycle_and_a_nonsense_one_are_refused(monkeypatch):
    monkeypatch.setattr(W.L, "cycle_period", lambda *a: "2026.10")
    for bad in ("2026.11", "2027.01"):
        with pytest.raises(ValueError, match="has not started"):
            W.select_period(bad)
    for bad in ("nonsense", "2026-09", "2026.13", "26.09"):
        with pytest.raises(ValueError, match="YYYY.MM"):
            W.select_period(bad)
    assert W.current_period() == "2026.10"


def test_selecting_a_past_cycle_sticks_and_releases(monkeypatch):
    monkeypatch.setattr(W.L, "cycle_period", lambda *a: "2026.10")
    try:
        assert W.select_period("2026.09") == "2026.09"
        assert W.current_period() == "2026.09"
        # choosing this month again is "follow the calendar", not a pin to October
        assert W.select_period("2026.10") == "2026.10"
        assert W._selected["period"] is None
        W.select_period("2026.08")
        assert W.select_period(None) == "2026.10"
    finally:
        W._selected["period"] = None


def test_a_build_names_the_cycle_on_screen(monkeypatch):
    """Without --period the child defaults to the calendar month, so a build started while
    an earlier cycle is selected would quietly build a different month from the one the page
    is showing."""
    monkeypatch.setattr(W.L, "cycle_period", lambda *a: "2026.10")
    try:
        W.select_period("2026.09")
        cmd = W.build_cmd("1038", False)
        assert cmd[-2:] == ["--period", "2026.09"]
        assert W.build_cmd("1038", True, True)[-4:] == ["--period", "2026.09", "--rebuild", "--combined"]
    finally:
        W._selected["period"] = None


def test_a_queued_job_keeps_the_cycle_it_was_asked_for(monkeypatch):
    """A job waiting behind two others must build the cycle it was queued for, not whichever
    one happens to be on screen when it starts."""
    monkeypatch.setattr(W.L, "cycle_period", lambda *a: "2026.10")
    try:
        W.select_period("2026.09")
        job = W.Job("1038", False)
        W.select_period("2026.10")
        assert job.period == "2026.09"
        assert W.build_cmd(job.cid, job.rebuild, job.combined, job.period)[-1] == "2026.09"
    finally:
        W._selected["period"] = None


def test_changing_cycle_drops_what_was_cached_about_the_old_one(monkeypatch):
    monkeypatch.setattr(W.L, "cycle_period", lambda *a: "2026.10")
    try:
        W._status_cache["1038"] = {"at": 0, "doc": {"period": "2026.10"}}
        W._clients["doc"] = {"period": "2026.10", "clients": []}
        W.select_period("2026.09")
        assert "1038" not in W._status_cache
        assert W._clients["doc"] is None
    finally:
        W._selected["period"] = None
        W._status_cache.clear()
        W._clients["doc"] = None


def test_the_list_carries_the_menu_for_the_page(monkeypatch):
    monkeypatch.setattr(W.L, "cycle_period", lambda *a: "2026.10")
    monkeypatch.setattr(W, "available_periods", lambda *a, **k: ["2026.10", "2026.09"])
    monkeypatch.setattr(W.R, "output_decks", lambda pat: [])
    monkeypatch.setattr(W.R, "csm_list_file", lambda: None)
    monkeypatch.setattr(W, "launcher_results", lambda period, cids: {})

    class _BM:
        @staticmethod
        def read_roster():
            return ([("1038", "Sugar River Bank", "SM", ["ARS"])], [])

    class _DS:
        @staticmethod
        def read_deliveries():
            return {"sent": {}}

    monkeypatch.setitem(__import__("sys").modules, "build_month", _BM)
    monkeypatch.setitem(__import__("sys").modules, "deck_status", _DS)
    doc = W.compute_clients()
    assert doc["period"] == "2026.10"
    assert doc["periods"] == ["2026.10", "2026.09"]
    assert doc["cycle_now"] == "2026.10"


def test_a_check_that_finishes_after_a_cycle_change_is_not_stored(monkeypatch):
    """A check already in flight when the cycle changes finishes against the OLD cycle. Stored,
    it would read as the new cycle's answer — the one stale figure a CSM has no way to spot."""
    monkeypatch.setattr(W.L, "cycle_period", lambda *a: "2026.10")
    try:
        W._selected["period"] = None

        def slow(cid):
            W._selected["period"] = "2026.09"      # the cycle moves while this check runs
            return {"client": cid, "period": "2026.10", "state": "ready", "checks": []}

        monkeypatch.setattr(W, "compute_status", slow)
        W._check_status("1038", fresh=True)
        assert "1038" not in W._status_cache
    finally:
        W._selected["period"] = None
        W._status_cache.clear()


def test_changing_cycle_warms_the_new_one(monkeypatch):
    """Without this the first click on each client after a cycle change pays the full check
    again — 3.4 s against the share, where a warmed one answers in 5 ms."""
    monkeypatch.setattr(W.L, "cycle_period", lambda *a: "2026.10")
    started = []
    monkeypatch.setattr(W, "prewarm", lambda: started.append(W.current_period()))
    try:
        W.select_period("2026.09")
        for _ in range(50):
            if started:
                break
            time.sleep(0.05)
        assert started == ["2026.09"]
    finally:
        W._selected["period"] = None


def test_serving_the_list_never_touches_the_share(monkeypatch):
    """_served_clients runs on every poll of the page. Listing Outputs and Inputs for the cycle
    menu there cost seconds of share reads per request — the menu belongs to the stored list,
    which is rebuilt in the background."""
    monkeypatch.setattr(W, "available_periods", lambda *a, **k: pytest.fail("served the list off the share"))
    with W._clients_lock:
        W._clients["doc"] = {"period": "2026.10", "clients": [], "periods": ["2026.10", "2026.09"],
                             "cycle_now": "2026.10"}
        W._clients["at"] = time.time()
    try:
        doc = W._served_clients()
        assert doc["periods"] == ["2026.10", "2026.09"] and doc["cycle_now"] == "2026.10"
        # a list stored before the menu existed falls back to its own cycle, still no share read
        with W._clients_lock:
            W._clients["doc"] = {"period": "2026.08", "clients": []}
        assert W._served_clients()["periods"] == ["2026.08"]
    finally:
        with W._clients_lock:
            W._clients["doc"] = None


def test_every_element_the_page_script_asks_for_exists():
    """$("#detail") was an id this page does not have, so every cycle change threw
    "Cannot set properties of null" after the switch had already happened (Aaron, 2026-10-02).
    Nothing in Python could see it: the page is a string, and the id was only ever read at
    runtime. Collect the ids the script asks for by name and check each one is written
    somewhere in the page — in the static HTML or by the script itself."""
    import re
    page = W.PAGE
    have = set(re.findall(r'id="([A-Za-z][\w-]*)"', page))        # static and script-built alike
    have |= set(re.findall(r'\.id = "([A-Za-z][\w-]*)"', page))     # ...and ids set as a property
    asked = set(re.findall(r'\$\("#([A-Za-z][\w-]*)"\)', page))
    asked |= set(re.findall(r'querySelector\("#([A-Za-z][\w-]*)"\)', page))
    missing = sorted(asked - have)
    assert not missing, f"the page script reads ids that are never created: {missing}"


def test_the_cycle_code_calls_nothing_it_never_defines():
    """The id check caught $("#detail"); the very next run of the same code threw
    "load is not defined", because the function is called loadClients (Aaron, 2026-10-02).
    Both are the same mistake — a name that only resolves when a CSM clicks.

    Scoped to the cycle functions rather than the whole script: a regex cannot tell a call
    from CSS or an object key, and a check that cries wolf over the other 2,000 lines would
    be switched off within a week. These are the functions that were wrong twice.
    """
    import re
    page = W.PAGE
    defined = set(re.findall(r'function\s+([A-Za-z_]\w*)\s*\(', page))
    defined |= set(re.findall(r'(?:const|let|var)\s+([A-Za-z_]\w*)\s*=\s*(?:async\s*)?(?:\(|function)', page))
    allowed = defined | {"fetch", "alert", "setTimeout", "clearTimeout", "encodeURIComponent",
                         "JSON", "Date", "Math", "Object", "Array", "String", "Number"}
    missing = {}
    for name in ("pickCycle", "openCycles", "closeCycles", "paintPeriod"):
        m = re.search(r"function %s\(.*?\n\}" % name, page, re.S)
        assert m, f"{name} is no longer in the page"
        body = m.group(0)
        called = set(re.findall(r'(?<![.\w$"])([a-z][A-Za-z0-9_]*)\s*\(', body))
        unknown = sorted(called - allowed - {"if", "for", "while", "catch", "return", "await",
                                             "function", "switch"})
        if unknown:
            missing[name] = unknown
    assert not missing, f"the cycle code calls names it never defines: {missing}"
