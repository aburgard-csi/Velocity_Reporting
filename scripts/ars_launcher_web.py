#!/usr/bin/env python3
"""CSM Sheila, the Smart Helper for Executive Insights, Layouts & Analytics — the browser front end for ars_launcher (named 2026-09-16; it was ARS Deck Builder, then briefly WILL).

    python scripts/ars_launcher_web.py [--port 0] [--no-open]

Aaron, 2026-09-15: "would it be possible to run Build ARS Deck.bat in an application or browser?"
A browser cannot start a program by itself, so `ARS Deck Builder GUI.bat` starts this small server on
127.0.0.1 and opens the page. The page lists the clients.md ARS clients, runs the same checks as
`ars_launcher.py status`, and starts `ars_launcher.py build` as a child process, showing its step
lines as they arrive. Every rule, the build and the delivery to Outputs stay in ars_launcher —
nothing here decides anything. Closing the console window stops the server.

Only this PC can reach it, and only the page it served can use it: every API call must carry the
random token baked into that page and name 127.0.0.1 or localhost as its Host, so another web page
open in the same browser cannot start a build through localhost.
"""
import argparse
import csv
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
for _p in (REPO / "build", HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import rpe_env as R           # noqa: E402
import ars_launcher as L      # noqa: E402

TOKEN = secrets.token_urlsafe(24)
CID_RX = re.compile(r"^\d{3,5}$")
DECK_RX = re.compile(r"(?:In Outputs:|already identical to this build:)\s*(.+?\.pptx)")
LINE_RX = re.compile(r"^\s*\[(ok|!!|built|STOP|\.\.)\]\s+(.*)$")

_jobs = {}
_jobs_lock = threading.Lock()
# Lift Matrix state per MM client for the list's "Lift Matrix expired" tag. Reading 30-odd workbooks
# over the share takes a minute, so it runs once in the background when the builder starts and the
# page re-asks until it is done; the pre-build check itself is always read fresh.
_lift = {}
_lift_state = {"started": False, "done": False}


def prewarm_lift():
    import build_month as BM
    _lift_state["started"] = True
    try:
        period = L.cycle_period()
        roster, _ = BM.read_roster()
        for cid, _, path, progs in roster:
            if "ARS" not in progs or path != "MM" or not period:
                continue
            try:
                checks = L.lift_checks(cid, period, roster)
            except Exception:
                continue
            _lift[cid] = L.STOP if any(l == L.STOP for l, _ in checks) else L.OK
    finally:
        _lift_state["done"] = True


def prewarm():
    """Background warm-up when the builder starts: Lift Matrix tags for the list, then every client's status."""
    import build_month as BM
    prewarm_lift()
    for cid, _, _, progs in BM.read_roster()[0]:
        if "ARS" in progs:
            try:
                status_doc(cid)
            except Exception:
                continue


# ------------------------------------------------------------------ data for the page
def clients_doc():
    """The clients.md ARS clients, with their CSM, products, sent state and deck in Outputs."""
    import build_month as BM
    import deck_status as DS
    period = L.cycle_period()
    roster, _ = BM.read_roster()
    ars = {r[0]: r for r in roster if "ARS" in r[3]}
    rows = {}
    p = R.csm_list_file()
    if p and p.is_file():
        with open(p, encoding="utf-8-sig", newline="") as fh:
            rows = {r.get("client_id", "").strip(): r for r in csv.DictReader(fh)}
    sent = DS.read_deliveries()["sent"] if period else {}
    decks = {}
    for d in (R.output_decks(f"*-{period}-*ARS*.pptx") if period else []):
        decks.setdefault(d.name.split("-", 1)[0], []).append(d)
    out = []
    for cid, (_, name, path, progs) in ars.items():
        row = rows.get(cid, {})
        s = sent.get(f"{cid}|{period}")
        out.append({
            "id": cid,
            # clients.md's name, as on the deck; the CSM List's can carry a filename flag.
            "name": name or row.get("client_name"),
            "csm": row.get("csm") or "Unassigned",
            "programs": progs,
            "path": path,
            "sent": (s.get("sent_at") if isinstance(s, dict) else s) or None,
            "decks": sorted(d.name for d in decks.get(cid, [])),
            "lift_expired": _lift.get(cid) == L.STOP,
            "error": bool(period) and last_build_failed(cid, period, decks.get(cid, [])),
        })
    out.sort(key=lambda c: (c["csm"], (c["name"] or "").lower()))
    return {"period": period, "clients": out,
            "lift_pending": _lift_state["started"] and not _lift_state["done"]}


def last_build_failed(cid, period, decks=()):
    """Did this client's last build for `period` fail? Drives the list's red "Error <period>" pill.

    A build this server ran decides it while it is remembered: still running or queued is not an
    error, and a finished one failed when it exited non-zero. Otherwise the launcher's own record
    (`_launcher_result.json`) decides: a build that was not put in Outputs failed — unless a deck
    for the period reached Outputs after that record was written, by any route.
    """
    with _jobs_lock:
        job = _jobs.get(cid)
    if job:
        return job.done and bool(job.code)
    res = R.build_artifacts() / "launcher" / period / cid / "_launcher_result.json"
    try:
        rec = json.loads(res.read_text(encoding="utf-8"))
        written = res.stat().st_mtime
    except (OSError, ValueError):
        return False
    if rec.get("delivered") or rec.get("clean"):     # "clean": the pre-2026-09-15 staging record
        return False
    newest = max((Path(d).stat().st_mtime for d in decks if Path(d).exists()), default=0)
    return newest <= written


# Each client's status is kept for STATUS_TTL seconds (Aaron, 2026-09-15: "can we speed up the UI by caching
# information?"). A check reads the shares and the workbook (about 3-6s); served from here it is instant.
# "Check again" asks for a fresh one, a finished build drops its client's entry, and every client is checked
# once in the background when the builder starts. The pre-build checks in `ars_launcher.py build` itself
# are never cached.
STATUS_TTL = 600
_status_cache = {}
_status_lock = threading.Lock()


def status_doc(cid, fresh=False):
    """The client's status, from the cache unless it is older than STATUS_TTL or `fresh` is asked for."""
    with _status_lock:
        hit = _status_cache.get(cid)
    if fresh or not hit or time.time() - hit[0] >= STATUS_TTL:
        doc = compute_status(cid)
        hit = (time.time(), doc)
        with _status_lock:
            _status_cache[cid] = hit
    out = dict(hit[1])
    out["age_seconds"] = round(time.time() - hit[0])
    out["job"] = job_doc(cid)
    return out


def forget_status(cid):
    with _status_lock:
        _status_cache.pop(cid, None)


def compute_status(cid):
    """ars_launcher's own checks for one client, plus its last launcher build."""
    import build_month as BM
    import deck_status as DS
    period = L.cycle_period()
    row = L.csm_list_row(cid)
    if not period:
        return {"client": cid, "state": "stop", "period": None,
                "checks": [{"level": L.STOP, "text": "No ARS workbooks are in Inputs at all, so there is no period to build."}]}
    roster, _ = BM.read_roster()
    sent = DS.read_deliveries()["sent"]
    checks = L.all_checks(cid, period, row, roster, sent)
    lift = [l for l, m in checks if m.startswith("Lift Matrix")]
    if lift:
        _lift[cid] = L.STOP if L.STOP in lift else L.OK
    state = "stop" if any(l == L.STOP for l, _ in checks) else "ask" if any(l == L.ASK for l, _ in checks) else "ready"
    res = R.build_artifacts() / "launcher" / period / cid / "_launcher_result.json"
    last = json.loads(res.read_text(encoding="utf-8")) if res.exists() else None
    entry = next((r for r in roster if r[0] == cid), None)
    return {"client": cid, "name": (entry[1] if entry else None) or row.get("client_name"), "csm": row.get("csm"), "period": period,
            "state": state, "checks": [{"level": l, "text": m} for l, m in checks], "last": last}


# ------------------------------------------------------------------ build jobs
def build_cmd(cid, rebuild):
    return [sys.executable, str(HERE / "ars_launcher.py"), "build", cid] + (["--rebuild"] if rebuild else [])


class Job:
    def __init__(self, cid, rebuild):
        self.cid, self.rebuild = cid, rebuild
        self.lines, self.done, self.code = [], False, None
        self.queued_at = time.time()
        self.started = None          # set when it leaves the queue
        self.finished = None

    def run(self):
        self.started = time.time()
        # COLUMNS keeps ars_launcher.say from wrapping a long Outputs path across two lines.
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1", COLUMNS="1000")
        try:
            proc = subprocess.Popen(build_cmd(self.cid, self.rebuild), stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                                    env=env, cwd=str(REPO))
            for line in proc.stdout:
                self.lines.append(line.rstrip("\r\n"))
            self.code = proc.wait()
        except OSError as e:
            self.lines.append(f"  [STOP] The build could not start: {e}")
            self.code = 1
        self.finished = time.time()
        self.done = True
        forget_status(self.cid)     # the deck in Outputs and the last-build line have changed

    def to_json(self):
        deck = next((m.group(1) for m in map(DECK_RX.search, self.lines) if m), None)
        waiting = [j for j in list(_queue) if not j.started]
        position = waiting.index(self) + 1 if self in waiting else None
        running = next((j.cid for j in list(_jobs.values()) if j.started and not j.done), None)
        return {"client": self.cid, "rebuild": self.rebuild, "lines": self.lines, "done": self.done,
                "code": self.code, "deck": deck, "queued": position, "after": running if position else None,
                "seconds": round((self.finished or time.time()) - self.started) if self.started else 0}


def job_doc(cid):
    with _jobs_lock:
        j = _jobs.get(cid)
    return j.to_json() if j else None


# Builds run one at a time — two at once would fight over the share and the CPU. A build asked for while
# another runs waits in this queue, first in first out, and the list shows its place (Aaron, 2026-09-16:
# a second build used to be refused with "Start the next one when it finishes").
_queue = []
_worker = {"thread": None}


def _drain():
    while True:
        with _jobs_lock:
            if not _queue:
                _worker["thread"] = None
                return
            job = _queue[0]
        try:
            job.run()
        finally:
            with _jobs_lock:
                _queue.remove(job)


def start_build(cid, rebuild):
    """Queue a build; it starts at once when nothing else is building. Returns (http status, body)."""
    with _jobs_lock:
        cur = _jobs.get(cid)
        if cur and not cur.done:
            where = "building" if cur.started else f"queued #{[j for j in _queue if not j.started].index(cur) + 1}"
            return 409, {"error": f"{cid} is already {where}."}
        job = Job(cid, rebuild)
        _jobs[cid] = job
        _queue.append(job)
        if _worker["thread"] is None:
            _worker["thread"] = threading.Thread(target=_drain, daemon=True)
            _worker["thread"].start()
    return 202, job.to_json()


def queue_doc():
    """What is building and what waits, in order — cheap enough for the list to poll."""
    with _jobs_lock:
        queue = list(_queue)
    return {"building": next((j.cid for j in queue if j.started and not j.done), None),
            "queued": [j.cid for j in queue if not j.started]}


def reveal(path):
    """Show a deck in File Explorer — only a file under Outputs."""
    try:
        p = Path(path).resolve()
        out = R.outputs().resolve()
    except (OSError, SystemExit):
        return 403, {"error": "Outputs is not reachable."}
    if out not in p.parents or not p.is_file():
        return 403, {"error": "Only a deck in Outputs can be shown."}
    subprocess.Popen(["explorer", "/select,", str(p)])
    return 200, {"ok": True}


# ------------------------------------------------------------------ HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "ARSDeckBuilder"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _host_ok(self):
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        return host in ("127.0.0.1", "localhost")

    def _api_ok(self):
        return self._host_ok() and secrets.compare_digest(self.headers.get("X-Token") or "", TOKEN)

    def do_GET(self):
        u = urlparse(self.path)
        if not self._host_ok():
            return self._send(403, {"error": "forbidden"})
        if u.path == "/":
            return self._send(200, PAGE.replace("__TOKEN__", TOKEN).encode("utf-8"), "text/html; charset=utf-8")
        if not self._api_ok():
            return self._send(403, {"error": "forbidden"})
        q = parse_qs(u.query)
        cid = (q.get("client") or [""])[0].strip()
        try:
            if u.path == "/api/clients":
                return self._send(200, clients_doc())
            if u.path == "/api/queue":
                return self._send(200, queue_doc())
            if u.path in ("/api/status", "/api/job"):
                if not CID_RX.match(cid):
                    return self._send(400, {"error": "not a client number"})
                if u.path == "/api/status":
                    return self._send(200, status_doc(cid, fresh=(q.get("fresh") or [""])[0] == "1"))
                return self._send(200, job_doc(cid) or {})
        except (OSError, SystemExit, ValueError, KeyError) as e:
            return self._send(500, {"error": f"{type(e).__name__}: {e}"})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._api_ok():
            return self._send(403, {"error": "forbidden"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0) or 0) or b"{}")
        except ValueError:
            return self._send(400, {"error": "bad request"})
        path = urlparse(self.path).path
        if path == "/api/build":
            cid = str(body.get("client", "")).strip()
            if not CID_RX.match(cid):
                return self._send(400, {"error": "not a client number"})
            return self._send(*start_build(cid, bool(body.get("rebuild"))))
        if path == "/api/reveal":
            return self._send(*reveal(str(body.get("path", ""))))
        return self._send(404, {"error": "not found"})


def make_server(port=0):
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main(argv=None):
    ap = argparse.ArgumentParser(description="CSM Sheila, the Smart Helper for Executive Insights, Layouts & Analytics: the browser front end for ars_launcher.")
    ap.add_argument("--port", type=int, default=0, help="default: any free port")
    ap.add_argument("--no-open", action="store_true", help="don't open a browser")
    a = ap.parse_args(argv)
    srv = make_server(a.port)
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"\n CSM Sheila is running at {url}")
    print(" Keep this window open while you build. Close it when you're done.\n", flush=True)
    threading.Thread(target=prewarm, daemon=True).start()
    if not a.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CSM Sheila · Smart Helper for Executive Insights, Layouts &amp; Analytics</title>
<style>
:root{
  --navy:#00274C; --orange:#F47A29; --ground:#F4F6F9; --surface:#FFFFFF; --soft:#EDF1F5;
  --ink:#0E1B2A; --ink2:#566370; --ink3:#8793A0; --rule:#D8DEE5;
  --ok:#1E7F4F; --ok-bg:#E4F3EB; --warn:#9A6212; --warn-bg:#FBF0DC; --sent:#245C8C; --sent-bg:#E6EEF6;
  --stop:#B42318; --stop-bg:#FCE9E7; --focus:#F47A29; --sel:#E9EFF6;
}
@media (prefers-color-scheme: dark){:root{
  --ground:#0B1520; --surface:#12202D; --soft:#182A3A; --ink:#E6ECF2; --ink2:#A7B4C1; --ink3:#788796; --rule:#26384A;
  --ok:#57C98F; --ok-bg:#12302A; --warn:#E6B45C; --warn-bg:#33270F; --sent:#8FB4DA; --sent-bg:#16283A;
  --stop:#F08579; --stop-bg:#3A1C1A; --sel:#1B3044;
}}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font:15px/1.45 "Segoe UI",Calibri,Arial,sans-serif}
header.top{background:var(--navy);color:#fff;padding:14px 24px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
header.top h1{margin:0;font-size:19px;font-weight:700;letter-spacing:.01em}
header.top .period{margin-left:auto;background:var(--orange);color:#fff;font-weight:700;font-size:12.5px;letter-spacing:.04em;padding:5px 12px;border-radius:999px}
.app{display:grid;grid-template-columns:minmax(260px,330px) minmax(0,1fr);gap:18px;max-width:1240px;margin:18px auto;padding:0 18px}
@media (max-width:820px){.app{grid-template-columns:1fr}}
aside,main{background:var(--surface);border:1px solid var(--rule);border-radius:10px}
aside{display:flex;flex-direction:column;max-height:calc(100vh - 100px);min-height:420px}
.filters{padding:14px;display:grid;gap:8px;border-bottom:1px solid var(--rule)}
label.small{font-size:11.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--ink3)}
input,select{font:inherit;color:var(--ink);background:var(--surface);border:1px solid var(--rule);border-radius:7px;padding:7px 9px;width:100%}
input:focus-visible,select:focus-visible,button:focus-visible{outline:2px solid var(--focus);outline-offset:2px}
.list{overflow:auto;padding:6px}
.client{display:grid;grid-template-columns:3.4em 1fr;gap:2px 8px;width:100%;text-align:left;font:inherit;color:inherit;background:none;border:0;border-radius:7px;padding:8px 9px;cursor:pointer}
.client:hover{background:var(--soft)}
.client[aria-current="true"]{background:var(--sel)}
.client .id{font-family:Consolas,monospace;font-size:13px;color:var(--ink2);padding-top:1px}
.client .nm{font-weight:600}
.client .meta{grid-column:2;display:flex;gap:6px;flex-wrap:wrap;font-size:12px;color:var(--ink2)}
.grouphead{font-size:11.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--ink3);padding:12px 9px 4px}
.chip{display:inline-block;font-size:11.5px;font-weight:600;padding:1px 7px;border-radius:999px;background:var(--soft);color:var(--ink2);white-space:nowrap}
.chip.sent{background:var(--sent-bg);color:var(--sent)} .chip.out{background:var(--ok-bg);color:var(--ok)}
.chip.stop{background:var(--stop-bg);color:var(--stop)}
.chip.queue{background:var(--warn-bg);color:var(--warn)} .chip.building{background:var(--orange);color:#fff}
.chip.error{background:#C62828;color:#fff}
main{padding:22px 24px;min-height:420px}
.empty{color:var(--ink2);max-width:60ch}
.empty h2{color:var(--ink);font-size:18px;margin:0 0 6px}
.empty ol{padding-left:20px;margin:8px 0 0;display:grid;gap:4px}
.head{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 14px;border-bottom:1px solid var(--rule);padding-bottom:12px;margin-bottom:14px}
.head h2{margin:0;font-size:22px;text-wrap:balance}
.head .sub{color:var(--ink2)}
.checks{list-style:none;margin:0;padding:0;display:grid;gap:6px}
.checks li{display:grid;grid-template-columns:4.2em 1fr;gap:10px;align-items:start}
.tag{font:700 11px/1 Consolas,monospace;text-align:center;padding:5px 0;border-radius:5px;text-transform:uppercase}
.tag.ok{background:var(--ok-bg);color:var(--ok)} .tag.warn{background:var(--warn-bg);color:var(--warn)}
.tag.ask{background:var(--sent-bg);color:var(--sent)} .tag.stop{background:var(--stop-bg);color:var(--stop)}
.tag.step{background:var(--soft);color:var(--ink2)}
.verdict{margin:18px 0 0;padding:12px 14px;border-radius:8px;border:1px solid var(--rule);display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center}
.verdict.ready{background:var(--ok-bg);border-color:transparent} .verdict.ask{background:var(--sent-bg);border-color:transparent}
.verdict.stop{background:var(--stop-bg);border-color:transparent}
.verdict p{margin:0;flex:1;min-width:220px}
button.primary{font:600 15px/1 "Segoe UI",Arial,sans-serif;background:var(--navy);color:#fff;border:0;border-radius:8px;padding:11px 16px;cursor:pointer}
button.primary.warn{background:var(--orange)}
button.primary:disabled{background:var(--ink3);cursor:not-allowed}
button.link{font:inherit;background:none;border:0;color:var(--sent);text-decoration:underline;cursor:pointer;padding:0}
.progress{margin-top:20px}
.progress h3,.last h3{font-size:13px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--ink3);margin:0 0 8px}
.steps{list-style:none;margin:0;padding:0;display:grid;gap:5px}
.steps li{display:flex;gap:10px;align-items:center}
.dot{width:12px;height:12px;border-radius:50%;flex:none;border:2px solid var(--ink3)}
.dot.done{background:var(--ok);border-color:var(--ok)}
.dot.now{border-color:var(--orange);border-top-color:transparent;animation:spin .9s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
@media (prefers-reduced-motion:reduce){.dot.now{animation:none;background:var(--orange)}}
.steps .t{color:var(--ink3);font-size:12.5px;margin-left:auto;font-variant-numeric:tabular-nums}
.result{margin-top:16px;padding:14px;border-radius:8px}
.result.good{background:var(--ok-bg)} .result.bad{background:var(--stop-bg)}
.result h3{margin:0 0 4px;font-size:16px;text-transform:none;letter-spacing:0;color:var(--ink)}
.result p{margin:4px 0}
.mono{font-family:Consolas,monospace;font-size:13px;word-break:break-all}
details.log{margin-top:14px} details.log summary{cursor:pointer;color:var(--ink2);font-size:13px;width:max-content}
.term{margin-top:8px;border-radius:8px;overflow:hidden;background:#0C0C0C;border:1px solid #2B2B2B;box-shadow:0 6px 18px rgba(0,0,0,.25)}
.term .bar{display:flex;align-items:center;gap:8px;height:32px;padding-left:12px;background:#1F1F1F;color:#CCCCCC;font:12px/1 "Segoe UI",Arial,sans-serif}
.term .bar .ttl{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.term .bar .ctl{display:flex;height:100%} .term .bar .ctl span{width:42px;display:grid;place-items:center;color:#9D9D9D}
.term pre{margin:0;padding:10px 14px 14px;color:#CCCCCC;font:13px/1.45 "Cascadia Mono",Consolas,"Courier New",monospace;max-height:340px;overflow:auto;white-space:pre-wrap;word-break:break-word}
.term .g{color:#16C60C} .term .y{color:#F9F1A5} .term .r{color:#E74856} .term .c{color:#61D6D6} .term .b{color:#3B78FF}
.term .cursor{animation:blink 1s steps(1) infinite} @keyframes blink{50%{opacity:0}}
@media (prefers-reduced-motion:reduce){.term .cursor{animation:none}}
.last{margin-top:18px;color:var(--ink2);font-size:14px}
.note{color:var(--ink2);font-size:13px;margin-top:14px}
.err{color:var(--stop)}
</style>
</head>
<body>
<header class="top"><h1>CSM Sheila <span style="font-weight:400;opacity:.8">· Smart Helper for Executive Insights, Layouts &amp; Analytics</span></h1><span class="period" id="period">Loading…</span></header>
<div class="app">
  <aside aria-label="Clients">
    <div class="filters">
      <label class="small" for="csm">CSM</label>
      <select id="csm"><option value="">All CSMs</option></select>
      <label class="small" for="q">Find a client</label>
      <input id="q" type="search" placeholder="Name or number" autocomplete="off">
    </div>
    <div class="list" id="list" role="list"></div>
  </aside>
  <main id="main" aria-live="polite">
    <div class="empty">
      <h2>Pick a client</h2>
      <p>Choose a client on the left to see whether their ARS deck can be built this month.</p>
      <ol>
        <li>The checks run first: ARS product, clients.md, and this month's ODD extract and workbook.</li>
        <li>Build takes 3 to 15 minutes and shows each step as it goes.</li>
        <li>A deck that passes validation goes straight to your folder in Outputs. Review it, save it as a PDF and email it as usual.</li>
      </ol>
      <p class="note">Keep CSM Sheila's black window open while you build.</p>
    </div>
  </main>
</div>
<script>
const TOKEN = "__TOKEN__";
const STEP_ORDER = ["Reading the ARS workbook","Reading the ARS workbook and DCO","Reading the Lift Matrix","Reading the ODD extract","Computing the ODD metrics","Drawing the charts","Assembling the deck","Validating the deck"];
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let CLIENTS = [], PERIOD = null, current = null, poller = null, armed = false;
let QUEUE = {building: null, queued: []};

// What is building and what waits. Cheap, so the list keeps it current every few seconds; when a
// build finishes the client list is re-read so its "In Outputs" chip appears.
async function pollQueue() {
  try {
    const {body} = await api("/api/queue");
    const before = QUEUE;
    QUEUE = {building: body.building || null, queued: body.queued || []};
    if (JSON.stringify(before) !== JSON.stringify(QUEUE)) {
      if (before.building && before.building !== QUEUE.building) loadClients(); else renderList();
    }
  } catch (e) {}
}

async function api(path, opts = {}) {
  const r = await fetch(path, {...opts, headers: {"X-Token": TOKEN, "Content-Type": "application/json", ...(opts.headers || {})}});
  const body = await r.json().catch(() => ({}));
  if (!r.ok && r.status !== 409) throw new Error(body.error || ("HTTP " + r.status));
  return {status: r.status, body};
}
function store(k, v) { try { v === undefined ? localStorage.getItem(k) : localStorage.setItem(k, v); } catch (e) {} }
function recall(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }

function shortDate(d) { if (!d) return ""; const x = new Date(d + "T12:00:00"); return isNaN(x) ? d : x.toLocaleDateString(undefined, {month: "short", day: "numeric"}); }

function renderList() {
  const csm = $("#csm").value, q = $("#q").value.trim().toLowerCase();
  const shown = CLIENTS.filter(c => (!csm || c.csm === csm) && (!q || c.id.includes(q) || (c.name || "").toLowerCase().includes(q)));
  let html = "", last = null;
  for (const c of shown) {
    if (!csm && c.csm !== last) { html += `<div class="grouphead">${esc(c.csm)}</div>`; last = c.csm; }
    // No "Sent" chip: only Aaron records sends, and other CSMs have nowhere to mark theirs (2026-09-15).
    const place = QUEUE.queued.indexOf(c.id);
    const chips = [QUEUE.building === c.id ? `<span class="chip building">Building</span>` : "",
                   place >= 0 ? `<span class="chip queue">Queued #${place + 1}</span>` : "",
                   c.error && QUEUE.building !== c.id && place < 0 ? `<span class="chip error">Error ${esc(PERIOD || "")}</span>` : "",
                   c.lift_expired ? `<span class="chip stop">Lift Matrix expired</span>` : "",
                   c.decks.length ? `<span class="chip out">In Outputs ${esc(PERIOD || "")}</span>` : ""].join("");
    html += `<button class="client" role="listitem" data-id="${esc(c.id)}" aria-current="${current === c.id}">
      <span class="id">${esc(c.id)}</span><span class="nm">${esc(c.name)}</span><span class="meta">${chips}</span></button>`;
  }
  $("#list").innerHTML = html || `<p class="note" style="padding:10px">No clients match.</p>`;
}

async function loadClients() {
  try {
    const {body} = await api("/api/clients");
    CLIENTS = body.clients; PERIOD = body.period;
    $("#period").textContent = PERIOD ? "Cycle " + PERIOD : "No period";
    const csms = [...new Set(CLIENTS.map(c => c.csm))];
    $("#csm").innerHTML = `<option value="">All CSMs</option>` + csms.map(c => `<option>${esc(c)}</option>`).join("");
    const saved = recall("ars-builder-csm"); if (saved && csms.includes(saved) && !$("#csm").dataset.touched) $("#csm").value = saved;
    renderList();
    // Lift Matrix dates are still being read in the background: ask again shortly.
    if (body.lift_pending) setTimeout(loadClients, 8000);
  } catch (e) {
    $("#list").innerHTML = `<p class="err" style="padding:10px">Couldn't load clients: ${esc(e.message)}. Check the VPN and reload.</p>`;
  }
}

const LEVEL = {ok: ["ok", "ok"], warn: ["warn", "!!"], ask: ["ask", "built"], stop: ["stop", "stop"]};

async function select(id, fresh) {
  current = id; armed = false; clearInterval(poller); renderList();
  const c = CLIENTS.find(x => x.id === id) || {id};
  $("#main").innerHTML = `<div class="head"><h2>${esc(c.name || id)}</h2><span class="sub">${esc(id)} · ${esc(c.csm || "")}</span></div><p class="note">Checking the client and this month's data…</p>`;
  try {
    const {body} = await api("/api/status?client=" + encodeURIComponent(id) + (fresh ? "&fresh=1" : ""));
    if (current !== id) return;
    renderStatus(body);
    if (body.job && !body.job.done) follow(id);
    else if (body.job) renderJob(body.job);
  } catch (e) {
    $("#main").innerHTML += `<p class="err">Couldn't check ${esc(id)}: ${esc(e.message)}</p>`;
  }
}

function renderStatus(s) {
  const c = CLIENTS.find(x => x.id === s.client) || {};
  const checks = s.checks.map(k => { const [cls, label] = LEVEL[k.level] || ["step", k.level];
    return `<li><span class="tag ${cls}">${label}</span><span>${esc(k.text)}</span></li>`; }).join("");
  // The last build failed: the list shows the red Error pill, and the button offers the retry.
  const failed = c.error || (s.job && s.job.done && s.job.code);
  const failNote = failed ? ` <span class="err">The last build failed; see why below.</span>` : "";
  let verdict;
  if (s.state === "ready") verdict = `<div class="verdict ready"><p><b>Ready to build.</b> The deck goes to Outputs when it passes validation.${failNote}</p><button class="primary" id="go">${failed ? "Retry build" : "Build and put in Outputs"}</button></div>`;
  else if (s.state === "ask") verdict = `<div class="verdict ask"><p><b>This month's deck is already in Outputs.</b> Rebuild only if something changed, such as a formatting fix or a corrected input.${failNote}</p><button class="primary warn" id="go">${failed ? "Retry rebuild" : "Rebuild and replace the one in Outputs"}</button></div>`;
  else verdict = `<div class="verdict stop"><p><b>Can't build yet.</b> Fix the items marked STOP, then check again.</p><button class="primary" id="recheck">Check again</button></div>`;
  const last = s.last ? `<div class="last"><h3>Last build from this tool</h3>${esc(s.last.finished)} by ${esc(s.last.by)}: ${esc(s.last.result)}${s.last.delivered ? " · in Outputs" : " · not in Outputs"}</div>` : "";
  const age = s.age_seconds == null ? "" : s.age_seconds < 60 ? "checked just now" : `checked ${Math.round(s.age_seconds / 60)} min ago`;
  $("#main").innerHTML = `<div class="head"><h2>${esc(s.name || c.name || s.client)}</h2><span class="sub">${esc(s.client)} · ${esc(s.csm || c.csm || "")} · ${esc(s.period || "")}</span>
      <span class="sub" style="margin-left:auto">${esc(age)} · <button class="link" id="refresh">Check again</button></span></div>
    <ul class="checks">${checks}</ul>${verdict}<div id="job"></div>${last}`;
  const go = $("#go"); if (go) go.addEventListener("click", () => build(s));
  const re = $("#recheck"); if (re) re.addEventListener("click", () => select(s.client, true));
  const rf = $("#refresh"); if (rf) rf.addEventListener("click", () => select(s.client, true));
}

async function build(s) {
  const go = $("#go");
  if (s.state === "ask" && !armed) { armed = true; go.textContent = "Yes, rebuild it"; return; }
  go.disabled = true; go.textContent = "Starting…";
  try {
    const {status, body} = await api("/api/build", {method: "POST", body: JSON.stringify({client: s.client, rebuild: s.state === "ask"})});
    if (status === 409) { go.disabled = false; go.textContent = "Try again"; $("#job").innerHTML = `<p class="err">${esc(body.error)}</p>`; return; }
    go.textContent = body.queued ? `Queued #${body.queued}` : "Building…";
    pollQueue();
    follow(s.client);
  } catch (e) { go.disabled = false; go.textContent = "Try again"; $("#job").innerHTML = `<p class="err">${esc(e.message)}</p>`; }
}

function follow(id) {
  clearInterval(poller);
  const tick = async () => {
    try {
      const {body} = await api("/api/job?client=" + encodeURIComponent(id));
      if (current !== id) return clearInterval(poller);
      renderJob(body);
      if (body.done) { clearInterval(poller); loadClients(); }
    } catch (e) {}
  };
  tick(); poller = setInterval(tick, 1500);
}

let logOpen = false;
const TERM_CLS = {ok: "g", "!!": "y", built: "b", STOP: "r", "..": "c"};
function termLine(l) {
  const m = l.match(/^(\s*)\[(ok|!!|built|STOP|\.\.)\](.*)$/);
  return m ? `${esc(m[1])}<span class="${TERM_CLS[m[2]]}">[${esc(m[2])}]</span>${esc(m[3])}` : esc(l);
}

function renderJob(j) {
  if (!j || !j.lines) return;
  const go = $("#go");
  if (go && !j.done) { go.disabled = true; go.textContent = j.queued ? `Queued #${j.queued}` : "Building…"; }
  else if (go && j.code) { go.disabled = false; go.textContent = j.rebuild ? "Retry rebuild" : "Retry build"; }
  const steps = [], marks = [];
  for (const line of j.lines) {
    const m = line.match(/^\s*\[(ok|!!|built|STOP|\.\.)\]\s+(.*)$/);
    if (!m) continue;
    if (m[1] === "..") { const sm = m[2].match(/^(.*?)\s+\((\d+) min\)$/); steps.push({name: sm ? sm[1] : m[2], min: sm ? sm[2] : ""}); }
    else if (steps.length) marks.push({level: m[1], text: m[2]});
  }
  const mins = Math.floor(j.seconds / 60), secs = String(j.seconds % 60).padStart(2, "0");
  let html = `<div class="progress"><h3>Build${j.rebuild ? " (rebuild)" : ""} · ${j.queued ? "queued #" + j.queued : mins + ":" + secs}</h3><ul class="steps">`;
  if (j.queued) html += `<li><span class="dot"></span><span>Queued #${j.queued}. It starts on its own when ${j.queued > 1 ? "the builds ahead of it finish" : `the build for ${esc(j.after || "another client")} finishes`}. Keep CSM Sheila's black window open.</span></li>`;
  steps.forEach((st, i) => { const done = j.done || i < steps.length - 1;
    html += `<li><span class="dot ${done ? "done" : "now"}"></span><span>${esc(st.name)}</span><span class="t">${st.min !== "" ? esc(st.min) + " min" : ""}</span></li>`; });
  if (!steps.length && !j.done && !j.queued) html += `<li><span class="dot now"></span><span>Starting the build…</span></li>`;
  html += `</ul>`;
  const stop = marks.find(x => x.level === "STOP") || (j.done && j.code ? {text: [...j.lines].reverse().find(l => l.trim()) || "The build stopped."} : null);
  if (j.done && !j.code && j.deck) {
    const name = j.deck.split(/[\\/]/).pop();
    html += `<div class="result good"><h3>Done. The deck is in Outputs.</h3><p class="mono">${esc(name)}</p>
      <p>Review it, save it as a PDF and email it as usual.</p>
      <p><button class="link" id="reveal">Show it in File Explorer</button></p></div>`;
  } else if (j.done) {
    html += `<div class="result bad"><h3>Not put in Outputs.</h3><p>${esc(stop ? stop.text : "The build stopped.")}</p>
      <p>If it's not clear what to do, send Aaron the client number.</p></div>`;
  }
  html += `</div>`;
  // The output panel is built once per build and only its text is updated after that. Rebuilding it
  // on every poll (every 1.5 s) closed it again as soon as someone opened it.
  const box = $("#job");
  if (!box.querySelector("#jobview")) {
    box.innerHTML = `<div id="jobview"></div><details class="log" id="log"${logOpen ? " open" : ""}><summary>Full output</summary>
      <div class="term"><div class="bar"><span class="ttl">CSM Sheila: build ${esc(current || "")}</span><span class="ctl" aria-hidden="true"><span>&#x2014;</span><span>&#x2610;</span><span>&#x2715;</span></span></div>
      <pre id="termtext" tabindex="0"></pre></div></details>`;
    $("#log").addEventListener("toggle", () => { logOpen = $("#log").open; });
  }
  $("#jobview").innerHTML = html;
  const pre = $("#termtext"), key = j.lines.length + ":" + j.done;
  if (pre.dataset.key !== key) {
    const atBottom = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 8;
    pre.innerHTML = j.lines.map(termLine).join("\n") + (j.done ? "" : `\n<span class="cursor">&#x2588;</span>`);
    pre.dataset.key = key;
    if (atBottom) pre.scrollTop = pre.scrollHeight;
  }
  const rv = $("#reveal");
  if (rv) rv.addEventListener("click", async () => { try { await api("/api/reveal", {method: "POST", body: JSON.stringify({path: j.deck})}); } catch (e) { rv.insertAdjacentHTML("afterend", ` <span class="err">${esc(e.message)}</span>`); } });
}

$("#list").addEventListener("click", e => { const b = e.target.closest(".client"); if (b) select(b.dataset.id); });
$("#csm").addEventListener("change", () => { store("ars-builder-csm", $("#csm").value); renderList(); });
$("#q").addEventListener("input", renderList);
loadClients();
pollQueue(); setInterval(pollQueue, 3000);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    sys.exit(main())
