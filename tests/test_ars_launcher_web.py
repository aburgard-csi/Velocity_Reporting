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