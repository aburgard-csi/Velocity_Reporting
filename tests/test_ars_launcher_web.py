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
    monkeypatch.setattr(W, "build_cmd", lambda cid, rebuild, combined=False: [sys.executable, "-c", script])
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
    monkeypatch.setattr(W, "build_cmd", lambda cid, rebuild, combined=False: [sys.executable, "-c", script, cid])
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
