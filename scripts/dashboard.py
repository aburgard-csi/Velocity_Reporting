#!/usr/bin/env python3
"""
dashboard.py — the delivery dashboard: data readiness, builds, and what still
needs sending. Runs locally; nothing is published.

    python3 scripts/dashboard.py [--period 2026.09] [--port 8787] [--no-source]

Then open http://127.0.0.1:8787/ (the Browser pane in Claude Code will do).

Why a server and not a static page. Marking a deck sent has to WRITE, and the
record lives in `Build Artifacts/deliveries.json` on Drive (Aaron, 2026-08-31)
so it is the same fact on every machine and needs no commit. A file:// page
cannot write there. This is the smallest thing that can: stdlib `http.server`,
bound to 127.0.0.1, no dependencies, no external calls.

It is a VIEW over `deck_status.collect()` and adds no facts of its own. Anything
it shows about readiness is computed there, so the dashboard and a terminal run
of `deck_status.py` cannot disagree.

Binding: loopback only. The delivery log is not public, and this exposes a write
endpoint — it has no business listening on a LAN interface.
"""
import argparse
import datetime as _dt
import html
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "build"))
sys.path.insert(0, os.path.join(REPO, "scripts"))

import deck_status as DS                                          # noqa: E402
from brand import (NAVY, ORANGE, TICK, ROWALT, GRID, MUTED)       # noqa: E402

USE_SOURCE = True


def periods(n=8):
    """This month back n-1, newest first. The cycle runs monthly, so the period
    list is derivable — there is no need for anyone to type one."""
    out, d = [], _dt.date.today().replace(day=1)
    for _ in range(n):
        out.append("%04d.%02d" % (d.year, d.month))
        d = (d - _dt.timedelta(days=1)).replace(day=1)
    return out


# --------------------------------------------------------------------- render
CSS = """
*{box-sizing:border-box}
body{margin:0;background:#F4F7FA;color:#1B2733;
     font:14px/1.45 "Segoe UI",Calibri,system-ui,sans-serif}
a{color:%(navy)s}
header{background:%(navy)s;color:#fff;padding:16px 22px;
       display:flex;align-items:center;gap:18px;flex-wrap:wrap}
header h1{margin:0;font-size:17px;font-weight:600;letter-spacing:.2px}
header .sp{flex:1}
select,button{font:inherit}
select{padding:5px 8px;border-radius:5px;border:1px solid #ffffff44;
       background:#ffffff14;color:#fff}
select option{color:#1B2733}
.btn{padding:6px 13px;border-radius:5px;border:1px solid transparent;
     background:%(orange)s;color:#fff;cursor:pointer;font-weight:600}
.btn:hover{filter:brightness(1.07)}
.btn.ghost{background:#ffffff1a;border-color:#ffffff55;color:#fff}
.btn.small{padding:4px 10px;font-size:12.5px}
.btn.undo,.btn.quiet{background:transparent;border-color:%(muted)s;color:%(tick)s;
                     font-weight:500}
.btn.quiet:hover,.btn.undo:hover{background:#fff;border-color:%(tick)s;filter:none}
.wrap{padding:20px 22px 60px}
.banner{padding:10px 14px;border-radius:6px;margin-bottom:16px;font-weight:500}
.banner.warn{background:#FFF4E5;border:1px solid #F3C892;color:#7A4E10}
.banner.info{background:#EAF1F8;border:1px solid #C3D6E8;color:#204060}
.tiles{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:18px}
.tile{background:#fff;border:1px solid %(grid)s;border-radius:8px;
      padding:12px 16px;min-width:118px;box-shadow:0 1px 2px #00274c0d}
.tile .n{font-size:25px;font-weight:700;color:%(navy)s;line-height:1.1}
.tile .l{font-size:11.5px;text-transform:uppercase;letter-spacing:.6px;
         color:%(tick)s;margin-top:3px}
.tile.act .n{color:%(orange)s}
table{width:100%%;border-collapse:collapse;background:#fff;
      border:1px solid %(grid)s;border-radius:8px;overflow:hidden}
th{background:%(navy)s;color:#fff;text-align:left;padding:9px 11px;
   font-size:11.5px;text-transform:uppercase;letter-spacing:.5px;font-weight:600}
td{padding:9px 11px;border-top:1px solid %(grid)s;vertical-align:top}
tr:nth-child(even) td{background:%(rowalt)s}
.cid{font-weight:700;color:%(navy)s}
.tag{font-size:11px;color:%(tick)s}
.chips{display:flex;gap:5px;flex-wrap:wrap}
.chip{font-size:11px;padding:2px 7px;border-radius:10px;border:1px solid;
      white-space:nowrap;cursor:default}
.ok{background:#E7F5EC;border-color:#A9D9BC;color:#1C6A3A}
.no{background:#FDECEC;border-color:#F0B3B3;color:#A02020}
.st{background:#FFF4E5;border-color:#F3C892;color:#8A5A12}
.un{background:#EFEFEF;border-color:#D5D5D5;color:#666}
.na{background:#F7F9FB;border-color:#E2E8EF;color:#8A97A3}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%%;margin-right:5px}
.sent{color:#1C6A3A;font-weight:600}
.tosend{color:%(orange)s;font-weight:600}
.muted{color:%(tick)s}
.foot{margin-top:16px;font-size:12px;color:%(tick)s}
code{background:#EEF2F7;padding:1px 5px;border-radius:3px;font-size:12px}
""" % {"navy": NAVY, "orange": ORANGE, "tick": TICK, "rowalt": ROWALT,
       "grid": GRID, "muted": MUTED}

_CHIP_CLASS = {DS.PRESENT: "ok", DS.MISSING: "no", DS.STALE: "st",
               DS.UNKNOWN: "un", DS.NA: "na"}


def chip(row):
    """One input, coloured by the state of the copy the BUILDERS read (Drive).

    The source column is shown in the tooltip rather than as a second chip: what
    matters at a glance is whether the build can run, and source only explains
    why it cannot.
    """
    d, s = row["drive"], row["src"]
    cls = _CHIP_CLASS.get(d["state"], "un")
    note = ""
    # The ICS workbook is the one input whose absence is not a gap: without one
    # for this period the section builds referrals-only, which is a valid deck.
    # Colouring it red like a real blocker would send Aaron chasing a file that
    # is not late and may not be coming.
    if row["input"] == DS.OPTIONAL_INPUT and d["state"] != DS.PRESENT:
        cls = "na"
        note = "\nNot a blocker: without one, the ICS section builds referrals-only."
    tip = "%s\nDrive: %s (%s)\nSource: %s (%s)%s" % (
        row["input"], d["state"], d["detail"] or "-",
        s["state"], s["detail"] or "-", note)
    return '<span class="chip %s" title="%s">%s</span>' % (
        cls, html.escape(tip), html.escape(row["input"]))


def render(doc):
    p = doc["period"]
    cs = doc["clients"]
    ready = sum(1 for c in cs if c["ready"])
    built = sum(1 for c in cs if c["built"])
    sent = sum(1 for c in cs if c["sent"])
    tosend = sum(1 for c in cs if c["built"] and not c["sent"])

    opts = "".join(
        '<option value="%s"%s>%s</option>' % (x, " selected" if x == p else "", x)
        for x in periods())

    if not doc["source_checked"]:
        banner = ('<div class="banner info">Source shares were skipped '
                  '(<code>--no-source</code>). Readiness reflects Drive only, so a file '
                  'the data team has landed but nobody has copied looks the same as one '
                  'that never arrived.</div>')
    elif not doc["source_reachable"]:
        banner = ('<div class="banner warn"><b>Not on the CSI VPN.</b> The source shares '
                  'are unreachable, so &ldquo;has the data team landed it?&rdquo; is '
                  '<b>unknown</b>, not answered. Drive columns below are still accurate. '
                  'Connect the VPN and refresh to see what has landed.</div>')
    else:
        banner = ""

    rows = []
    for c in cs:
        chips = "".join(chip(r) for r in c["inputs"])
        b = c["built"]
        bcell = ('<span class="muted" title="%s">%s</span>'
                 % (html.escape(b["file"]), b["built"])) if b \
            else '<span class="muted">&mdash;</span>'

        if c["sent"]:
            s = c["sent"]
            scell = ('<span class="sent">&#10003; %s</span> '
                     '<button class="btn small undo" data-id="%s" data-act="unsent">'
                     'undo</button>' % (html.escape(s.get("sent_at", "")), c["id"]))
        else:
            # An unbuilt deck can still be marked sent — a deck delivered by some
            # other route must be recordable — but it is not the expected action,
            # so it does not get the loud button. Only a built-and-unsent deck is
            # actually waiting on Aaron.
            if b:
                scell = ('<button class="btn small" data-id="%s" '
                         'data-act="sent">Mark sent</button>' % c["id"])
            else:
                scell = ('<span class="muted" title="No deck in Outputs/ for this '
                         'period">not built</span> '
                         '<button class="btn small quiet" data-id="%s" data-act="sent" '
                         'title="Record this as sent even though no deck is in '
                         'Outputs/">mark sent anyway</button>' % c["id"])

        state = ('<span class="tosend">needs sending</span>' if b and not c["sent"]
                 else ('<span class="sent">done</span>' if c["sent"]
                       else ('<span class="muted">ready to build</span>' if c["ready"]
                             else '<span class="muted">waiting on data</span>')))

        rows.append(
            "<tr><td><span class='cid'>%s</span><br><span class='tag'>%s</span></td>"
            "<td>%s<br><span class='tag'>%s</span></td>"
            "<td><div class='chips'>%s</div></td>"
            "<td>%s</td><td>%s</td></tr>"
            % (c["id"], html.escape(c["tag"]), html.escape(c["name"]),
               state, chips, bcell, scell))

    excluded = ""
    if doc["not_built"]:
        excluded = ("<div class='foot'><b>Not on the build list</b> (per clients.md): "
                    + "; ".join("%s %s &mdash; %s"
                                % (x["id"], html.escape(x["name"]), html.escape(x["why"]))
                                for x in doc["not_built"]) + "</div>")

    return """<!doctype html><html><head><meta charset="utf-8">
<title>RPE Delivery Dashboard %(p)s</title><style>%(css)s</style></head><body>
<header>
  <h1>RPE Delivery Dashboard</h1>
  <select id="period">%(opts)s</select>
  <button class="btn ghost" id="refresh">Refresh</button>
  <span class="sp"></span>
  <span style="font-size:12px;opacity:.85">as of %(gen)s</span>
</header>
<div class="wrap">
%(banner)s
<div class="tiles">
  <div class="tile"><div class="n">%(n)d</div><div class="l">Clients</div></div>
  <div class="tile"><div class="n">%(ready)d</div><div class="l">Data ready</div></div>
  <div class="tile"><div class="n">%(built)d</div><div class="l">Built</div></div>
  <div class="tile act"><div class="n">%(tosend)d</div><div class="l">Need sending</div></div>
  <div class="tile"><div class="n">%(sent)d</div><div class="l">Sent</div></div>
</div>
<table>
<thead><tr><th>Client</th><th>Name / state</th><th>Data readiness</th>
<th>Built</th><th>Sent</th></tr></thead>
<tbody>%(rows)s</tbody></table>
%(excluded)s
<div class="foot">Sent state: <code>%(log)s</code>.
Readiness is computed by <code>scripts/deck_status.py</code>; this page only displays it.
Hover any chip for its Drive and source detail.</div>
</div>
<script>
const period = () => document.getElementById('period').value;
function go(){ location.search = '?period=' + encodeURIComponent(period()); }
document.getElementById('period').onchange = go;
document.getElementById('refresh').onclick = go;
document.querySelectorAll('button[data-act]').forEach(b => {
  b.onclick = async () => {
    b.disabled = true;
    const r = await fetch('/api/' + b.dataset.act, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id: b.dataset.id, period: period()})
    });
    if (!r.ok) { alert('Could not save: ' + await r.text()); b.disabled = false; return; }
    go();
  };
});
</script></body></html>""" % {
        "p": p, "css": CSS, "opts": opts, "gen": doc["generated"], "banner": banner,
        "n": len(cs), "ready": ready, "built": built, "sent": sent, "tosend": tosend,
        "rows": "".join(rows), "excluded": excluded,
        "log": html.escape(doc["deliveries_file"])}


# --------------------------------------------------------------------- server
class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _period(self):
        q = self.path.split("?", 1)[1] if "?" in self.path else ""
        for part in q.split("&"):
            if part.startswith("period="):
                from urllib.parse import unquote
                p = unquote(part[7:])
                if DS._period_ok(p):
                    return p
        return DEFAULT_PERIOD

    def do_GET(self):
        route = self.path.split("?", 1)[0]
        if route in ("/", "/index.html"):
            try:
                doc = DS.collect(self._period(), use_source=USE_SOURCE)
            except SystemExit as e:
                return self._send(500, "<pre>%s</pre>" % html.escape(str(e)))
            return self._send(200, render(doc))
        if route == "/api/status":
            doc = DS.collect(self._period(), use_source=USE_SOURCE)
            return self._send(200, json.dumps(doc, indent=1),
                              "application/json; charset=utf-8")
        self._send(404, "not found", "text/plain; charset=utf-8")

    def do_POST(self):
        route = self.path.split("?", 1)[0]
        if route not in ("/api/sent", "/api/unsent"):
            return self._send(404, "not found", "text/plain; charset=utf-8")
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            cid, period = str(body.get("id", "")), str(body.get("period", ""))
            if not cid or not DS._period_ok(period):
                raise ValueError("id and period (YYYY.MM) are required")
            # The roster is the authority on who exists. Without this a typo or a
            # stale tab writes a delivery record for a client that is not on the
            # list, and the log quietly stops matching reality.
            known = {c for c, _n, _m, _p in DS.read_roster()[0]}
            if cid not in known:
                raise ValueError("%s is not an active client in clients.md" % cid)
            if route == "/api/sent":
                DS.mark_sent(cid, period, by=os.environ.get("USERNAME", ""))
            else:
                DS.clear_sent(cid, period)
        except Exception as e:                                    # noqa: BLE001
            return self._send(400, str(e), "text/plain; charset=utf-8")
        self._send(200, json.dumps({"ok": True}), "application/json; charset=utf-8")

    def log_message(self, fmt, *a):
        pass                       # the access log is noise for a one-user tool


def main():
    global USE_SOURCE, DEFAULT_PERIOD
    ap = argparse.ArgumentParser(description="RPE delivery dashboard (local).")
    ap.add_argument("--period", default=periods()[0])
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--no-source", action="store_true",
                    help="skip the CSI shares (Drive only, faster)")
    ap.add_argument("--open", action="store_true", help="open a browser")
    a = ap.parse_args()
    if not DS._period_ok(a.period):
        raise SystemExit("period must be YYYY.MM, got %r" % a.period)
    USE_SOURCE = not a.no_source
    DEFAULT_PERIOD = a.period

    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    url = "http://127.0.0.1:%d/?period=%s" % (a.port, a.period)
    print("RPE delivery dashboard  ->  " + url)
    print("sent log: " + DS.deliveries_path())
    print("Ctrl+C to stop.")
    if a.open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


DEFAULT_PERIOD = periods()[0]

if __name__ == "__main__":
    main()
