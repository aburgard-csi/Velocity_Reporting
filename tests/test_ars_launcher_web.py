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
    monkeypatch.setattr(W, "status_doc", lambda cid: {"client": cid, "state": "ready", "checks": []})
    W._jobs.clear()
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
    monkeypatch.setattr(W, "build_cmd", lambda cid, rebuild: [sys.executable, "-c", script])
    status, data = call(server, "POST", "/api/build", {"client": "1441"})
    assert status == 202
    assert call(server, "POST", "/api/build", {"client": "1453"})[0] == 409, "a second build must wait"
    for _ in range(100):
        job = json.loads(call(server, "GET", "/api/job?client=1441")[1])
        if job.get("done"):
            break
        time.sleep(0.1)
    assert job["done"] and job["code"] == 0
    assert any("Reading the ODD extract" in l for l in job["lines"])
    assert job["deck"] == deck


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
