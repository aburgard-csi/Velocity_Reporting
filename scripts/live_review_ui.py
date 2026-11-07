"""
live_review_ui.py: Live Review opened from a client's page in CSM Sheila (prototype; Aaron, 2026-11-06:
"let other CSMs create these", "include peer comparisons with the client number only", "LR stays in prototype status").

Live Review (scripts/live_review.py) presents a client's review from a web page. It is a VIEW of the packs a deck
build left in `Build Artifacts/launcher/<period>/<id>/` and of the sheets the other deck builders read: it builds no
deck, writes nothing to Outputs and touches no delivery record. Until now it was started by hand from a checkout.
Here Sheila starts it for the CSM at the PC, opens it in their browser and stops it on request.

Why it is NOT a build job. A build is queued, takes the PC's build lock and runs once; a CSM presenting a review
holds the page open for an hour. Taking the lock would stop every build on that PC meanwhile. So the server runs
inside Sheila's own process, on a daemon thread of its own, and dies with Sheila: no long-lived child process, no
pipe to drain (CLAUDE.md, **Mail**: the endpoint agent relaunches a child python and a pipe to it can hang).

Building the page's model reads the share (every program's pack and the peer pool) and takes minutes on a slow
link, so `open_page` returns at once and a worker builds it. The card polls `/api/live/state` until it is ready,
failed (the audit's problems, in words) or stopped.

Rules kept from live_review.py, not loosened here:
  * Every figure must trace to a pack. The server refuses to serve a model the audit fails (no `--allow-untraced`).
  * Served on 127.0.0.1 only, with a per-server random token and a Host check (live_review.make_handler).
  * A peer is a dot whose hover gives its client number and nothing else; fewer than five peers is stated, not shown.
  * ILS is NOT offered here yet (its section reads a finished review PDF that not every CSM can see): the program list
    is every registry key but `ils`, whether or not that program is in this build of Live Review.

The routes (`get`, `post`) and the readiness block (`status`) are this module's; the card is sheila_hub_live.py.
"""
import atexit
import re
import threading
import time
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
CID_RX = re.compile(r"^\d{3,5}$")
PERIOD_RX = re.compile(r"^\d{4}\.\d{2}$")
OK, ASK, STOP = "ok", "ask", "stop"          # the same words ars_launcher uses for a check's level
MAX_OPEN = 4                                  # servers kept at once; opening one more stops the oldest
EXCLUDED_PROGRAMS = ("ils",)                  # not offered from Sheila yet (see the module docstring)

_lock = threading.Lock()
_sessions = {}                                # client id -> Session


def _live():
    """live_review, imported on first use: it puts build/ on sys.path and pulls in review_page."""
    import live_review
    return live_review


def programs():
    """Every Live Review program Sheila offers: the registry's, less the ones held back."""
    from review_page import registry
    return [key for key, _label, _module in registry.REGISTRY if key not in EXCLUDED_PROGRAMS]


class Session:
    """One client's Live Review server in this Sheila: starting, then ready (a URL) or failed (why)."""

    def __init__(self, cid, period):
        self.cid, self.period = cid, period
        self.state = "starting"               # starting | ready | failed
        self.url = None
        self.error = None
        self.problems = []
        self.started = time.time()
        self.ready_at = None
        self.srv = None
        self.thread = None

    def doc(self):
        return {"client": self.cid, "period": self.period, "state": self.state, "url": self.url,
                "error": self.error, "problems": self.problems[:20],
                "seconds": round((self.ready_at or time.time()) - self.started)}


def _stop_locked(cid):
    s = _sessions.pop(cid, None)
    if s is None:
        return False
    srv, s.srv = s.srv, None
    s.state = "stopped"
    if srv is not None:
        try:
            srv.shutdown()
            srv.server_close()
        except OSError:
            pass
    return True


def stop(cid):
    with _lock:
        return _stop_locked(cid)


def stop_all():
    with _lock:
        for cid in list(_sessions):
            _stop_locked(cid)


atexit.register(stop_all)


def _work(s, opener):
    """Build the model, then serve it. Runs on its own thread; every way out leaves the session in a final state."""
    try:
        import secrets
        lr = _live()
        svc = lr.Service(s.cid, s.period, programs=programs(), allow_untraced=False)
        try:
            svc.rebuild()
        except ValueError as e:                # the audit refused: say which figures, not just that it did
            s.problems, s.error = list(svc.problems), str(e)
            s.state = "failed"
            return
        token = secrets.token_urlsafe(24)
        srv = lr.make_server(svc, token, 0)
        url = "http://127.0.0.1:%d/" % srv.server_address[1]
        with _lock:
            if _sessions.get(s.cid) is not s:  # stopped while it was being built
                srv.server_close()
                return
            s.srv, s.url, s.state, s.ready_at = srv, url, "ready", time.time()
        t = threading.Thread(target=srv.serve_forever, name="live-review-" + s.cid, daemon=True)
        s.thread = t
        t.start()
        try:
            opener(url)
        except Exception:                      # noqa: BLE001  (the card still shows the link)
            pass
    except (Exception, SystemExit) as e:       # noqa: BLE001  (shown on the card, never raised into Sheila)
        s.error = "%s: %s" % (type(e).__name__, e) if not isinstance(e, SystemExit) else str(e)
        s.state = "failed"


def open_page(cid, period, opener=webbrowser.open):
    """Start (or reuse) the client's Live Review and open it in the browser. Returns (http status, doc)."""
    if not CID_RX.match(str(cid)):
        return 400, {"error": "not a client number"}
    if not PERIOD_RX.match(str(period)):
        return 400, {"error": "not a period (yyyy.mm)"}
    with _lock:
        cur = _sessions.get(cid)
        if cur is not None and cur.period == period and cur.state in ("starting", "ready"):
            doc = cur.doc()
            if cur.state == "ready":           # already running: bring the page back to the front
                try:
                    opener(cur.url)
                except Exception:              # noqa: BLE001
                    pass
            return 200, doc
        if cur is not None:                    # another period, or one that failed: start afresh
            _stop_locked(cid)
        while len(_sessions) >= MAX_OPEN:      # keep the number of servers small: drop the oldest
            oldest = min(_sessions.values(), key=lambda x: x.started)
            _stop_locked(oldest.cid)
        s = Session(cid, period)
        _sessions[cid] = s
        threading.Thread(target=_work, args=(s, opener), name="live-review-build-" + cid, daemon=True).start()
        return 202, s.doc()


def state_doc(cid):
    with _lock:
        s = _sessions.get(cid)
        return s.doc() if s else {"client": cid, "state": "idle"}


# ------------------------------------------------------------------ readiness
def status(cid, period, programs_of_client):
    """What the client's card shows before Open is pressed, from file presence only (no model is built: this
    sits in the status Sheila keeps for ten minutes). `programs_of_client` is the roster's list, e.g. ["ARS","ICS"].

    Returns {"state": "ready"|"stop", "checks": [{"level", "text"}], "programs": [...]}: the page is worth opening
    when at least one program has a pack; a program with none is named, and the page itself greys it with what to run."""
    import rpe_env as R
    from review_page import packs as PK
    progs = [p.upper() for p in (programs_of_client or [])] or ["ARS"]
    checks, have = [], []
    if "ARS" in progs:
        folder = PK.launcher_dir(cid, period)
        if (folder / "metrics.json").is_file():
            have.append("ARS")
            checks.append({"level": OK, "text": "ARS: the %s deck build's data pack is on hand." % period})
        else:
            checks.append({"level": ASK, "text": "ARS: no data pack for %s. Build the %s ARS deck first; the ARS part of the "
                                                  "page will say so until then." % (period, period)})
    for prog in ("ICS", "MRPC"):
        if prog in progs:
            try:
                R.resolve_client_json(cid, prog.lower())
                have.append(prog)
                checks.append({"level": OK, "text": "%s: the VIP sheet is on hand." % prog})
            except (SystemExit, OSError, ValueError):
                checks.append({"level": ASK, "text": "%s: no VIP sheet for this client." % prog})
    if "CP" in progs or "CASHPLEASE" in progs:
        pack = R.build_artifacts() / "cashplease" / "packs" / ("%s_cashplease.json" % cid)
        if pack.is_file():
            have.append("CP")
            checks.append({"level": OK, "text": "CashPlease: the pack is on hand."})
        else:
            checks.append({"level": ASK, "text": "CashPlease: no pack yet for this client."})
    state = "ready" if have else "stop"
    if not have:
        checks.insert(0, {"level": STOP, "text": "No program has data for %s yet, so there is nothing to present." % period})
    return {"state": state, "checks": checks, "programs": have}


# ------------------------------------------------------------------ routes
def get(handler, path, params):
    """GET /api/live/state?client=."""
    cid = params.get("client", "")
    if not CID_RX.match(cid):
        return handler._send(400, {"error": "not a client number"})
    if path == "/api/live/state":
        return handler._send(200, state_doc(cid))
    return handler._send(404, {"error": "not found"})


def post(handler, path, body):
    """POST /api/live/open (client, period) and /api/live/stop (client)."""
    cid = str(body.get("client", "")).strip()
    if path == "/api/live/open":
        code, doc = open_page(cid, str(body.get("period", "")).strip())
        return handler._send(code, doc)
    if path == "/api/live/stop":
        if not CID_RX.match(cid):
            return handler._send(400, {"error": "not a client number"})
        return handler._send(200, {"stopped": stop(cid), "client": cid, "state": "idle"})
    return handler._send(404, {"error": "not found"})
