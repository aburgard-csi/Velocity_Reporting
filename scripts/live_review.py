#!/usr/bin/env python3
"""live_review.py — present a client's Executive Review from a web page (prototype, Aaron 2026-11-02).

    python scripts/live_review.py 1539 --period 2026.10            # serve it and open the page
    python scripts/live_review.py 1539 --period 2026.10 --check    # build the view model, audit it, print, exit

The page is a VIEW of the data pack a deck build left in `Build Artifacts/launcher/<period>/<id>/`
(and of the sheets the ICS, MRPC and CashPlease builders read). It builds nothing, writes nothing to
Outputs, and touches no delivery record. If the pack is missing it says what to run.

Served the way CSM Sheila is: 127.0.0.1 only, a random token baked into the page for every API call
(`X-Token`), and a Host header that must name 127.0.0.1 or localhost (a page on another name that
resolves to 127.0.0.1 is refused). Sheila's handler is bound to Sheila's module-level token, so this
mirrors the same checks in its own small handler rather than importing Sheila's page, queue and
build machinery.

NOT part of Sheila's page or the CSM release: run by hand.
"""
import argparse
import datetime
import json
import os
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "build"))

from review_page import registry                      # noqa: E402
from review_page.page import FONT_FILES, render_page   # noqa: E402


class Service:
    """The model, built on demand and kept; a rebuild that fails leaves the last good model."""

    def __init__(self, client, period, root=None, programs=None, allow_untraced=False):
        self.client, self.period, self.root, self.programs = client, period, root, programs
        self.allow_untraced = allow_untraced
        self._lock = threading.Lock()
        self.model = None
        self.problems = []

    def rebuild(self):
        with self._lock:
            model, _tracer, problems = registry.build_model(self.client, self.period, self.root, self.programs)
            if problems and not self.allow_untraced:
                self.problems = problems
                raise ValueError("%d figure(s) on the page do not trace to the data pack: %s"
                                 % (len(problems), "; ".join(problems[:3])))
            self.model, self.problems = model, problems
            return model

    def get(self):
        with self._lock:
            m = self.model
        return m if m is not None else self.rebuild()


def make_handler(service, token):
    class Handler(BaseHTTPRequestHandler):
        server_version = "LiveReview"

        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json; charset=utf-8", cache="no-store"):
            data = body if isinstance(body, bytes) else json.dumps(body, default=str).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _host_ok(self):
            host = (self.headers.get("Host") or "").split(":")[0].lower()
            return host in ("127.0.0.1", "localhost")

        def _api_ok(self):
            return self._host_ok() and secrets.compare_digest(self.headers.get("X-Token") or "", token)

        def do_GET(self):
            u = urlparse(self.path)
            if not self._host_ok():
                return self._send(403, {"error": "forbidden"})
            if u.path == "/":
                try:
                    model = service.get()
                except Exception as e:
                    return self._send(500, ("<h1>Live review could not start</h1><pre>%s</pre>" % _esc(str(e))).encode("utf-8"),
                                      "text/html; charset=utf-8")
                return self._send(200, render_page(model, token).encode("utf-8"), "text/html; charset=utf-8")
            if u.path.startswith("/fonts/"):
                f = FONT_FILES.get(u.path[len("/fonts/"):])
                if f is None or not f.is_file():
                    return self._send(404, {"error": "not found"})
                return self._send(200, f.read_bytes(), "font/ttf", cache="public, max-age=86400")
            if not self._api_ok():
                return self._send(403, {"error": "forbidden"})
            if u.path == "/api/model":
                try:
                    return self._send(200, service.rebuild())
                except Exception as e:
                    return self._send(500, {"error": "%s: %s" % (type(e).__name__, e)})
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            # Read the body BEFORE refusing: answering 403 with the body unread makes Windows reset the
            # connection (the lesson Sheila's handler records). Capped so a refused caller cannot make
            # the server read without limit.
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                n = -1
            if 0 < n <= 1_000_000:
                self.rfile.read(n)
            return self._send(403 if not self._api_ok() else 405, {"error": "forbidden" if not self._api_ok() else "no writes here"})

    return Handler


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def make_server(service, token, port=0):
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(service, token))


def default_period():
    d = datetime.date.today()
    return "%d.%02d" % (d.year, d.month)


def summarize(model, problems):
    lines = ["%s %s, %s" % (model["client"]["id"], model["client"]["name"], model["month"])]
    for e in model["programs"]:
        lines.append("  %-11s %-8s %s" % (e["label"], e["state"], ", ".join(s["id"] for s in e["screens"]) or (e["note"] or "")))
        if e.get("fix"):
            lines.append("              fix: %s" % e["fix"])
    lines.append("  traceability: %s" % ("every figure traces to a pack" if not problems else "%d PROBLEM(S)" % len(problems)))
    lines += ["    - " + p for p in problems[:20]]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Present a client's Executive Review from a web page.")
    ap.add_argument("client", help="client number, e.g. 1539")
    ap.add_argument("--period", default=None, help="yyyy.mm (default: this month)")
    ap.add_argument("--port", type=int, default=0, help="default: any free port")
    ap.add_argument("--programs", default=None, help="comma list of ars,ics,mrpc,cashplease (default: all)")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--check", action="store_true", help="build and audit the view model, print it, and exit")
    ap.add_argument("--allow-untraced", action="store_true", help="serve even when the audit finds a figure with no pack behind it")
    ap.add_argument("--dump", default=None, help="write the view model JSON here (with --check)")
    a = ap.parse_args(argv)
    period = a.period or default_period()
    programs = [p.strip() for p in a.programs.split(",")] if a.programs else None
    svc = Service(a.client, period, programs=programs, allow_untraced=a.allow_untraced or a.check)
    print("Reading the data pack for %s, %s (the share needs the VPN off site)..." % (a.client, period), flush=True)
    try:
        model = svc.rebuild()
    except Exception as e:
        print("Could not build the page: %s: %s" % (type(e).__name__, e), file=sys.stderr)
        return 2
    print(summarize(model, svc.problems), flush=True)
    if a.dump:
        Path(a.dump).write_text(json.dumps(model, default=str, indent=1), encoding="utf-8")
    if a.check:
        return 1 if svc.problems else 0
    if svc.problems and not a.allow_untraced:
        return 1
    token = secrets.token_urlsafe(24)
    srv = make_server(svc, token, a.port)
    url = "http://127.0.0.1:%d/" % srv.server_address[1]
    print("\n Live review is running at %s\n Keep this window open while you present. Ctrl+C to stop.\n" % url, flush=True)
    if not a.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
