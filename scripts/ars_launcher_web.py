#!/usr/bin/env python3
"""CSM Sheila, the Smart Helper for Executive Insights, Layouts & Analytics — the browser front end for ars_launcher (named 2026-09-16; it was ARS Deck Builder, then briefly WILL).

    python scripts/ars_launcher_web.py [--port 0] [--no-open]

Aaron, 2026-09-15: "would it be possible to run Build ARS Deck CLI.bat in an application or browser?"
A browser cannot start a program by itself, so `ARS Deck Builder GUI.bat` starts this small server on
127.0.0.1 and opens the page. The page lists every client with a deck to build — the clients.md roster in
any program mix and the standalone CashPlease module clients (Aaron, 2026-10-13) — runs the same checks as
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
from concurrent.futures import ThreadPoolExecutor
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
import slide_votes as SV      # noqa: E402
import slide_review_ui        # noqa: E402
import ils_ui                 # noqa: E402

TOKEN = secrets.token_urlsafe(24)
# The largest body any POST reads. The biggest real one, the Lift Matrix rates, is a few KB.
MAX_POST_BYTES = 1_000_000
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
# Share calls run this many at a time when the server warms up. Every stat on the share is a network round
# trip (20-150 ms, and far worse on a bad day), so waiting on four at once is close to four times faster.
PREWARM_WORKERS = 4


def prewarm_lift():
    import build_month as BM
    _lift_state["started"] = True
    try:
        period = current_period()
        roster, _ = BM.read_roster()
        mm = [cid for cid, _, path, progs in roster if "ARS" in progs and path == "MM"] if period else []

        def one(cid):
            try:
                checks = L.lift_checks(cid, period, roster)
            except Exception:
                return
            _lift[cid] = L.STOP if any(l == L.STOP for l, _ in checks) else L.OK
        with ThreadPoolExecutor(PREWARM_WORKERS) as ex:
            list(ex.map(one, mm))
    finally:
        _lift_state["done"] = True


def prewarm():
    """Background warm-up when the builder starts: the client list, Lift Matrix tags, then every client's status."""
    import build_month as BM
    refresh_clients()
    prewarm_lift()
    doc = _clients.get("doc") or {}
    ids = [c["id"] for c in doc.get("clients", [])] or [cid for cid, *_ in BM.read_roster()[0]]

    def one(cid):
        try:
            status_doc(cid)
        except (Exception, SystemExit):
            pass
    with ThreadPoolExecutor(PREWARM_WORKERS) as ex:
        list(ex.map(one, ids))


# ------------------------------------------------------------------ share caches (this process only)
# Aaron, 2026-09-17: "work on ways to make Sheila's GUI refresh faster." The data root is a network share where
# every stat, listing or open is a round trip, and one client's checks made hundreds of them — many asking the
# same thing again (is the share reachable, which report folders exist, the VIP manifest, the cycle period).
# Inside this server those answers are kept for SHARE_TTL seconds. The build itself runs `ars_launcher.py
# build` as a separate process, which never sees these caches: its pre-build checks are always read fresh.
# "Check again" (fresh=1) bypasses them too.
SHARE_TTL = 60
_share_cache = {}
_share_lock = threading.Lock()
_bypass = threading.local()
_installed = []


def _ttl(fn, seconds):
    """`fn` with its answers kept for `seconds` per argument list. Exceptions are never kept."""
    def cached(*a, **kw):
        try:
            key = (fn.__module__, fn.__qualname__, a, tuple(sorted(kw.items())))
            hash(key)
        except TypeError:
            return fn(*a, **kw)
        if not getattr(_bypass, "on", False):
            with _share_lock:
                hit = _share_cache.get(key)
            if hit and time.monotonic() - hit[0] < seconds:
                return hit[1]
        val = fn(*a, **kw)
        with _share_lock:
            _share_cache[key] = (time.monotonic(), val)
        return val
    cached.__wrapped__ = fn
    return cached


def _share_targets():
    import build_month as BM    # noqa: F401  (deck_status imports it; load it first, as the launcher does)
    import deck_status as DS
    return [(R, "data_root"), (R, "report_dirs"), (R, "vip_data"), (R, "vip_manifest"), (R, "csm_list_file"),
            (DS, "_reachable"), (DS, "odd_reachable"), (DS, "_oddd_month_dirs"), (DS, "_source_reports"),
            (DS, "_mtime"), (DS, "_same_file"),
            (L, "cycle_period"), (L, "csm_list_row"),
            # the Transaction Intelligence check lists Inputs/Txn Files/<id>/ (2026-10-23)
            (R, "txn_files")]


def install_share_caches(seconds=None):
    """Keep the share answers above for `seconds` (default SHARE_TTL) in this process. Idempotent."""
    if _installed:
        return
    for mod, name in _share_targets():
        orig = getattr(mod, name)
        _installed.append((mod, name, orig))
        setattr(mod, name, _ttl(orig, SHARE_TTL if seconds is None else seconds))
    _installed.append((L, "_window", L._window))
    L._window = _sheila_window


def uninstall_share_caches():
    while _installed:
        mod, name, orig = _installed.pop()
        setattr(mod, name, orig)
    with _share_lock:
        _share_cache.clear()


class _fresh_reads:
    """Within this block, on this thread, the share caches are read past (and refilled)."""
    def __init__(self, on=True):
        self.on = on

    def __enter__(self):
        self.prev = getattr(_bypass, "on", False)
        _bypass.on = self.prev or self.on

    def __exit__(self, *exc):
        _bypass.on = self.prev


# ------------------------------------------------------------------ data for the page
# The list is served from memory and refreshed behind the page (Aaron, 2026-09-17). Building it reads the CSM
# list, every CSM folder in Outputs and each client's last launcher result over the share —
# 10 s on a good day, 110 s measured on a bad one — so a request never waits for it once a list exists. A
# list older than CLIENTS_TTL, or invalidated by a finished build, is served as it is while a fresh one is
# built in the background; the page shows its age and asks again. What this server knows live — builds it
# ran (Building, Queued, Error, the deck a finished build put in Outputs) and Lift Matrix tags — is laid over
# the stored list on every request, so those never wait for the refresh.
CLIENTS_TTL = 60
RESULT_NAME = "_launcher_result.json"
PERIOD_CHOICES = 12          # how many past cycles the period menu offers

# The cycle being worked on. None means "today's", which advances on the 1st; a CSM can point
# Sheila at an earlier one to look at, or rebuild, a month that is already finished (Aaron,
# 2026-10-02: "make it so you can click the date and select previous cycles"). One selection
# per server, not per browser tab: Sheila is a localhost tool one person uses at a time, and
# "which cycle am I working in" is a property of that work, not of a tab.
_selected = {"period": None}


def current_period():
    return _selected["period"] or L.cycle_period()


def available_periods(n=PERIOD_CHOICES):
    """The cycles the menu offers: this month, then every earlier one this pipeline has
    anything for — a deck in Outputs or an ARS workbook in Inputs — newest first.

    Months with nothing behind them are left out: offering a cycle that cannot be read or
    built is an invitation to a blank page.
    """
    now = L.cycle_period()
    seen = {now}
    for d in R.output_decks("*-*-*.pptx"):
        m = re.search(r"-(\d{4}\.\d{2})-", d.name)
        if m:
            seen.add(m.group(1))
    for f in R.report_files("*-*Workbook*.xlsx"):
        if "invitation checking" in f.name.lower():
            continue
        m = re.match(r"^\d+-(\d{4}\.\d{2})-", f.name)
        if m:
            seen.add(m.group(1))
    out = sorted((p for p in seen if p <= now), reverse=True)[:n]
    return out if out else [now]


def select_period(period):
    """Point Sheila at a cycle. None (or today's) goes back to following the calendar."""
    if period is not None:
        if not re.fullmatch(r"20\d\d\.(0[1-9]|1[0-2])", period or ""):
            raise ValueError("a cycle is YYYY.MM, like 2026.09")
        if period > L.cycle_period():
            raise ValueError("that cycle has not started yet")
    with _clients_lock:
        same = (_selected["period"] or L.cycle_period()) == (period or L.cycle_period())
        _selected["period"] = None if period == L.cycle_period() else period
    if not same:
        # Everything cached is about the old cycle: its decks, its checks.
        with _status_lock:
            for cid in list(_status_cache) + list(_status_gen):
                forget_status_locked(cid)
        with _clients_lock:
            _clients["doc"] = None
            _clients["at"] = 0.0
        invalidate_clients()
        # ...and warm the new one the way startup does. Without this the first click on each
        # client after a cycle change costs the full check again: 3.4 s against this share,
        # where a warmed one answers in 5 ms.
        threading.Thread(target=lambda: _swallow(prewarm), daemon=True).start()
    return current_period()
_clients = {"doc": None, "at": 0.0, "gen": 0, "clean_gen": -1, "busy": None, "error": None}
_clients_lock = threading.Lock()


covered_programs = L.covered_programs


def compute_clients():
    """Every client with a deck to build — the clients.md roster (ARS, ICS, MRPC, in any mix) and the
    standalone CashPlease module clients (Aaron, 2026-10-13) — with their CSM, products,
    deck in Outputs and last build failure."""
    import build_month as BM
    period = current_period()
    roster, _ = BM.read_roster()
    rows = {}
    p = R.csm_list_file()
    if p and p.is_file():
        with open(p, encoding="utf-8-sig", newline="") as fh:
            rows = {r.get("client_id", "").strip(): r for r in csv.DictReader(fh)}
    decks, ti_decks, comp_decks = {}, {}, {}
    for d in (R.output_decks(f"*-{period}-*.pptx") if period else []):
        # A Transaction Intelligence deck is a separate presentation (2026-10-23): it is never the
        # period's RPE deck, so it gets its own chip and never the "In Outputs" one.
        # An ARS Companion deck is a separate presentation too (2026-10-27): its own chip, never "In Outputs".
        (ti_decks if L.is_ti_deck(d.name) else comp_decks if L.is_companion_deck(d.name)
         else decks).setdefault(d.name.split("-", 1)[0], []).append(d)
    try:
        cp_rows = {r["client_id"]: r for r in getattr(BM, "read_cashplease_roster", lambda: [])()}
    except SystemExit:                      # no CashPlease roster table: nothing ships CP
        cp_rows = {}
    entries = {r[0]: r for r in roster}
    for cid, cp in cp_rows.items():          # standalone module clients are on the CashPlease roster alone
        if cid not in entries and L.standalone_cp(cp):
            entries[cid] = L.client_entry(cid, roster, cp)
    for cid in ils_ui.ils_runs.landed_clients():  # on ILS alone: their ILS cards are on the client page (2026-10-28)
        if cid not in entries:
            entries[cid] = (cid, rows.get(cid, {}).get("client_name") or cid, None, [])
    results = launcher_results(period, list(entries)) if period else {}
    out = []
    for cid, (_, name, path, progs) in entries.items():
        row = rows.get(cid, {})
        cp = cp_rows.get(cid)
        res = results.get(cid, (None, None))
        out.append({
            "id": cid,
            # clients.md's name, as on the deck; the CSM List's can carry a filename flag.
            "name": name or row.get("client_name"),
            "csm": row.get("csm") or (cp or {}).get("csm") or "Unassigned",
            "programs": progs,
            # The products the client's deck covers, and the rest of their Velocity products, for the
            # pills after the name (Aaron, 2026-10-13: "ID which products are covered for each client").
            "covered": covered_programs(progs, cp),
            "products": [p.strip() for p in (row.get("products") or "").split(";") if p.strip()],
            "path": path,
            # When the launcher last put this client's deck in Outputs ("YYYY-MM-DD HH:MM"), for the
            # list's "built today" note (Aaron, 2026-10-13).
            "built_at": (res[0] or {}).get("finished") if (res[0] or {}).get("delivered") else None,
            "decks": sorted(d.name for d in decks.get(cid, [])),
            "ti_decks": sorted(d.name for d in ti_decks.get(cid, [])),
            "companion_decks": sorted(d.name for d in comp_decks.get(cid, [])),
            "lift_expired": "ARS" in progs and _lift.get(cid) == L.STOP,
            "error": bool(period) and last_build_failed(cid, period, decks.get(cid, []), result=res),
            "result_written": res[1],
        })
    out.sort(key=lambda c: (c["csm"], (c["name"] or "").lower()))
    return {"period": period, "clients": out,
            "periods": available_periods(), "cycle_now": L.cycle_period(),
            "lift_pending": _lift_state["started"] and not _lift_state["done"]}


def refresh_clients(fresh=False):
    """Rebuild the stored list now. One refresh at a time: a caller arriving while one runs waits for it.

    Returns the exception that stopped it, or None. A client whose decks or last build changed has
    its cached status dropped, so a deck built elsewhere is re-checked on its next view.
    """
    claim = _claim_refresh()
    if claim is None:
        with _clients_lock:
            busy = _clients["busy"]
        if busy is not None:
            busy.wait()
        with _clients_lock:
            return _clients["error"]
    return _run_refresh(claim, fresh)


def _claim_refresh():
    """(event, generation) when this caller now owns the refresh, or None when one is already running."""
    with _clients_lock:
        if _clients["busy"] is not None:
            return None
        _clients["busy"] = threading.Event()
        return _clients["busy"], _clients["gen"]


def _run_refresh(claim, fresh):
    busy, gen = claim
    err = None
    try:
        with _fresh_reads(fresh):
            doc = compute_clients()
        with _clients_lock:
            old = _clients["doc"]
        if old and old.get("period") and not doc.get("period"):
            # Workbooks do not vanish from Inputs between two refreshes a minute apart; the share failed to list
            # them. Keep the list that had a period, and say the update failed, rather than blank every row.
            raise OSError("no ARS workbooks could be listed in Inputs (share not answering?)")
        with _clients_lock:
            _clients.update(doc=doc, at=time.time(), clean_gen=gen, error=None)
        if old and old.get("period") == doc.get("period"):
            before = {c["id"]: _signature(c) for c in old["clients"]}
            for c in doc["clients"]:
                if before.get(c["id"]) != _signature(c):
                    forget_status(c["id"])
        elif old:
            with _status_lock:
                for cid in list(_status_cache):
                    forget_status_locked(cid)
    except (Exception, SystemExit) as e:
        err = e
        with _clients_lock:
            _clients["error"] = e
    finally:
        with _clients_lock:
            _clients["busy"] = None
        busy.set()
    return err


def _signature(c):
    return (tuple(c.get("decks") or ()), c.get("error"), c.get("result_written"))


def _refresh_clients_later(fresh=False):
    """Start a refresh behind the page, unless one is running. Claimed before the thread starts, so the
    response that asked for it already says `refreshing`."""
    claim = _claim_refresh()
    if claim is not None:
        threading.Thread(target=_run_refresh, args=(claim, fresh), daemon=True).start()


def invalidate_clients():
    """Something the list shows has changed (a build finished): serve the stored list, and rebuild it now."""
    with _clients_lock:
        _clients["gen"] += 1
        have = _clients["doc"] is not None
    if have:        # nothing stored yet: the first request builds it
        _refresh_clients_later()


def clients_doc(fresh=False):
    """The list for the page: the stored one at once, refreshed in the background when old or asked for.

    Only the very first request waits, because there is nothing to show before it.
    """
    with _clients_lock:
        have = _clients["doc"] is not None
    if not have:
        err = refresh_clients(fresh)
        with _clients_lock:
            have = _clients["doc"] is not None
        if not have:
            raise err if err else OSError("the client list could not be read")
    else:
        with _clients_lock:
            stale = (_clients["clean_gen"] != _clients["gen"] or time.time() - _clients["at"] >= CLIENTS_TTL)
        if fresh or stale:
            _refresh_clients_later(fresh)
    _renew_statuses_later()
    return _served_clients()


STOP_LABELS = [          # the launcher's stop lines, shortened for a list chip (first match wins)
    ("ODD extract", "ODD extract"), ("ARS workbook", "ARS workbook"), ("DCO", "DCO"),
    ("Lift Matrix", "Lift Matrix"), ("Not an ARS client", "not an ARS client"), ("Not a ", "product list"),
    ("clients.md", "clients.md"), ("is not in Client CSM List", "CSM list"), ("ships a combined", "combined deck"),
    ("No program has the data", "no data"), ("No other program", "no data"), ("VPN", "VPN"),
]


def stop_label(checks):
    """A few words naming the first stop in a status's checks, for the list's Blocked chip."""
    for k in checks:
        if (k.get("level") if isinstance(k, dict) else k[0]) != L.STOP:
            continue
        text = k.get("text") if isinstance(k, dict) else k[1]
        for needle, label in STOP_LABELS:
            if needle in text:
                return label
        head = text.split(":")[0].strip()
        return head if 0 < len(head) <= 32 else "see checks"
    return None


def _served_clients():
    with _clients_lock:
        doc, at, refreshing, err = _clients["doc"], _clients["at"], _clients["busy"] is not None, _clients["error"]
    with _jobs_lock:
        jobs = dict(_jobs)
    with _status_lock:
        checked = dict(_status_cache)
    period = doc["period"]
    now = time.time()
    clients = []
    for c in doc["clients"]:
        c = dict(c)
        c.pop("result_written", None)
        c["lift_expired"] = "ARS" in (c.get("programs") or []) and _lift.get(c["id"]) == L.STOP
        # "Ready": the stored status says every pre-build check passes (a deck already in Outputs is "ask",
        # a missing input is "stop"). Only a status for the cycle on screen, and not older than STATUS_TTL,
        # counts: an old "ready" must not read as one now. "Blocked" is the same status saying stop, with
        # the first stop's subject so the list says what is missing (Aaron, 2026-10-13: "more status options").
        hit = checked.get(c["id"])
        current = bool(hit and now - hit[0] < STATUS_TTL and hit[1].get("period") == period)
        c["checked"] = current            # no current status yet: the list says "Checking…" (Aaron, 2026-10-13)
        c["ready"] = current and hit[1].get("state") == "ready"
        c["blocked"] = stop_label(hit[1].get("checks") or []) if current and hit[1].get("state") == "stop" else None
        job = jobs.get(c["id"])
        if job:
            # A build this server ran is known now, not at the next refresh.
            c["error"] = job.done and bool(job.code)
            deck = job.deck_name() if job.done and not job.code else None
            if (deck and period and deck.startswith(f"{c['id']}-{period}-")
                    and deck not in c["decks"]):
                c["decks"] = sorted(c["decks"] + [deck])
            if deck and job.finished:
                c["built_at"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(job.finished))
        clients.append(c)
    return {"period": period, "clients": clients,
            # The cycle menu rides with the stored list, built by compute_clients. NOT computed
            # here: this is the hot path — every poll of the page serves through it — and
            # available_periods() lists Outputs and Inputs, which is seconds of share reads.
            # A list built before the menu existed simply offers the cycle it is about.
            "periods": doc.get("periods") or [period],
            "cycle_now": doc.get("cycle_now") or period,
            "lift_pending": _lift_state["started"] and not _lift_state["done"],
            "age_seconds": max(0, round(time.time() - at)), "refreshing": refreshing,
            "refresh_error": f"{type(err).__name__}: {err}" if err else None}


def launcher_dir(period):
    return R.build_artifacts() / "launcher" / period


_results = {}
_results_lock = threading.Lock()


def result_record(path):
    """(record, written) of a launcher result file, or (None, None) when it is absent or unreadable.

    The file is re-read only when its size or modification time changed since the last read. A share that
    fails to answer (anything but "not there") gives the last record read rather than none, so one dropped
    call does not make the list's Error pill blink off and on.
    """
    with _results_lock:
        hit = _results.get(str(path))
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return None, None
    except OSError:
        return (hit[1], hit[2]) if hit else (None, None)
    key = (st.st_mtime_ns, st.st_size)
    if hit and hit[0] == key:
        return hit[1], hit[2]
    try:
        rec = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, None
    except (OSError, ValueError):     # includes a record caught half written
        return (hit[1], hit[2]) if hit else (None, None)
    if not isinstance(rec, dict):
        return None, None
    with _results_lock:
        _results[str(path)] = (key, rec, st.st_mtime)
    return rec, st.st_mtime


def launcher_results(period, cids):
    """{cid: (record, written)} for these clients' last launcher builds in `period`.

    One listing of the period folder finds which clients have a build at all; only those are read, several at
    a time. If the folder cannot be listed, every client is read on its own rather than reported as no build.
    """
    base = launcher_dir(period)
    try:
        with os.scandir(base) as it:
            have = {e.name for e in it if e.is_dir()}
        want = [c for c in cids if c in have]
    except FileNotFoundError:
        want = []
    except OSError:
        want = list(cids)
    out = {c: (None, None) for c in cids}
    if want:
        with ThreadPoolExecutor(min(8, len(want))) as ex:
            out.update(zip(want, ex.map(lambda c: result_record(base / c / RESULT_NAME), want)))
    return out


def last_build_failed(cid, period, decks=(), result=None):
    """Did this client's last build for `period` fail? Drives the list's red "Error <period>" pill.

    A build this server ran decides it while it is remembered: still running or queued is not an
    error, and a finished one failed when it exited non-zero. Otherwise the launcher's own record
    (`_launcher_result.json`) decides: a build that was not put in Outputs failed — unless a deck
    for the period reached Outputs after that record was written, by any route. `result` is the
    (record, written) pair when the caller has already read it.
    """
    with _jobs_lock:
        job = _jobs.get(cid)
    if job:
        return job.done and bool(job.code)
    rec, written = result if result is not None else result_record(launcher_dir(period) / cid / RESULT_NAME)
    if rec is None:
        return False
    if rec.get("delivered") or rec.get("clean"):     # "clean": the pre-2026-09-15 staging record
        return False
    newest = 0
    for d in decks:
        try:
            newest = max(newest, Path(d).stat().st_mtime)
        except OSError:
            continue
    return newest <= written


# Each client's status is kept for STATUS_TTL seconds (Aaron, 2026-09-15: "can we speed up the UI by caching
# information?"). A check reads the shares and the workbook (about 3-6s); served from here it is instant.
# "Check again" asks for a fresh one, a finished build drops its client's entry, and every client is checked
# once in the background when the builder starts. The pre-build checks in `ars_launcher.py build` itself
# are never cached.
#
# 2026-09-17: a status older than STATUS_TTL is no longer re-read while the page waits (5 s on a good day,
# 58 s observed). The page gets the stored one at once, marked `refreshing`, with its Build buttons held
# until the fresh one arrives — so an old "ready" can never be built from while a STOP may be on its way.
# A client whose list row changed (a deck built from anywhere) has its entry dropped.
STATUS_TTL = 600
_status_cache = {}
_status_lock = threading.Lock()
_status_gen = {}       # cid -> bumped by forget_status, so a check that started before it is not stored
_status_busy = {}      # cid -> Event while a non-fresh check for that client runs


def _check_status(cid, fresh=False):
    """Run the client's checks and store them. A non-fresh check already running for the client is joined."""
    if not fresh:
        with _status_lock:
            busy = _status_busy.get(cid)
            mine = busy is None
            if mine:
                busy = _status_busy[cid] = threading.Event()
        if not mine:
            busy.wait()
            with _status_lock:
                hit = _status_cache.get(cid)
            if hit:
                return hit
            return _check_status(cid, fresh=True)
    try:
        with _status_lock:
            gen = _status_gen.get(cid, 0)
        started_for = current_period()
        with _fresh_reads(fresh):
            doc = compute_status(cid)
            hit = (time.time(), doc)        # stamped when the check finished: on a slow share it can take minutes
        with _status_lock:
            if _status_gen.get(cid, 0) == gen and started_for == current_period():
                _status_cache[cid] = hit
        return hit
    finally:
        if not fresh:
            with _status_lock:
                _status_busy.pop(cid, None)
            busy.set()


def _check_status_later(cid):
    with _status_lock:
        if cid in _status_busy:
            return
    threading.Thread(target=lambda: _swallow(_check_status, cid), daemon=True).start()


def _swallow(fn, *a):
    try:
        fn(*a)
    except (Exception, SystemExit):
        pass


# A stored status expires after STATUS_TTL, and the list reads an expired one as "Checking…". The start-up
# warm-up checks every client once, so ten minutes later every client with no deck in Outputs said
# "Checking…" and stayed that way until somebody opened it (Aaron, 2026-10-29: "Max's accounts are getting
# stuck on Checking"). While a page is open, each list request now renews, behind the page, the statuses
# that are missing or past STATUS_RENEW of their life, one pass at a time. Only main() turns it on, as with
# the share caches: a test that calls clients_doc must never start real checks.
STATUS_RENEW = 0.7
_renew = {"on": False, "busy": False}


def _renew_statuses_later():
    if not _renew["on"]:
        return
    with _status_lock:
        if _renew["busy"]:
            return
        _renew["busy"] = True
    threading.Thread(target=_renew_statuses, daemon=True).start()


def _renew_statuses():
    try:
        with _clients_lock:
            doc = _clients["doc"]
        if not doc:
            return
        period, now = doc.get("period"), time.time()
        with _status_lock:
            stored = dict(_status_cache)
        due = [c["id"] for c in doc["clients"]
               if not (c["id"] in stored and now - stored[c["id"]][0] < STATUS_TTL * STATUS_RENEW
                       and stored[c["id"]][1].get("period") == period)]
        with ThreadPoolExecutor(PREWARM_WORKERS) as ex:
            list(ex.map(lambda cid: _swallow(_check_status, cid), due))
    finally:
        with _status_lock:
            _renew["busy"] = False


def status_doc(cid, fresh=False, background=False):
    """The client's status, from the cache unless it is older than STATUS_TTL or `fresh` is asked for.

    With `background` (the page's own requests), an entry older than STATUS_TTL is returned as it is, marked
    `refreshing`, while it is re-read behind the page; without it the re-read is waited for.
    """
    with _status_lock:
        hit = _status_cache.get(cid)
    refreshing = False
    if fresh or not hit:
        hit = _check_status(cid, fresh=fresh)
    elif time.time() - hit[0] >= STATUS_TTL:
        if background:
            _check_status_later(cid)
            refreshing = True
        else:
            hit = _check_status(cid)
    out = dict(hit[1])
    out["age_seconds"] = round(time.time() - hit[0])
    with _status_lock:
        out["refreshing"] = refreshing or cid in _status_busy
    out["job"] = job_doc(cid)
    return out


def forget_status(cid):
    with _status_lock:
        forget_status_locked(cid)


def forget_status_locked(cid):
    _status_cache.pop(cid, None)
    _status_gen[cid] = _status_gen.get(cid, 0) + 1


def compute_status(cid):
    """ars_launcher's own checks for one client, plus its last launcher build."""
    import build_month as BM
    period = current_period()
    row = L.csm_list_row(cid)
    if not period:
        return {"client": cid, "state": "stop", "period": None,
                "checks": [{"level": L.STOP, "text": "No ARS workbooks are in Inputs at all, so there is no period to build."}]}
    roster, _ = BM.read_roster()
    cp_row = L.cp_roster_row(cid)
    entry = L.client_entry(cid, roster, cp_row)
    has_ars = bool(entry and "ARS" in entry[3])
    # For an ARS client up to two builds are on offer (Aaron, 2026-09-16): ARS only, and a combined deck
    # with every other clients.md program whose data is on hand. The checks are the combined-build rules;
    # whether the ARS-only build is allowed (not for Aaron's multi-program clients) is decided separately.
    # A client with no ARS has one build: every program with data (Aaron, 2026-10-13).
    checks = L.all_checks(cid, period, row, roster, combined=True, cp_row=cp_row)
    avail = L.program_availability(cid, period, entry[3]) if entry else {}
    extra = L.combined_programs(avail)
    if has_ars:
        checks = [(l, m) for l, m in checks if not m.startswith("No other program has the data")]
    multi = bool(entry and len(entry[3]) > 1)
    ars_only = has_ars and not (multi and row and row.get("csm") == L.AARON)
    if has_ars and not ars_only and not extra:
        checks.append((L.STOP, "This client ships a combined deck, but no other program has its data this period."))
    lift = [l for l, m in checks if m.startswith("Lift Matrix")]
    if lift:
        _lift[cid] = L.STOP if L.STOP in lift else L.OK
    state = "stop" if any(l == L.STOP for l, _ in checks) else "ask" if any(l == L.ASK for l, _ in checks) else "ready"
    res = R.build_artifacts() / "launcher" / period / cid / "_launcher_result.json"
    last = json.loads(res.read_text(encoding="utf-8")) if res.exists() else None
    # The Transaction Intelligence block (Aaron, 2026-10-23): a separate presentation with its own
    # checks and button, for ARS clients. A failure in its checks never costs the RPE status.
    ti = None
    if has_ars:
        try:
            ti = L.ti_status(cid, period, row, roster)
        except (Exception, SystemExit) as e:          # noqa: BLE001 — shown, never raised
            ti = {"checks": [{"level": L.STOP, "text": f"The Transaction Intelligence checks could not run "
                                                        f"({type(e).__name__}: {e})"}],
                  "state": "stop", "last": None, "decks": []}
    # The ARS Companion block (Aaron, 2026-10-27): James's analysis slides as a deck of their own, with its
    # own checks and button, for ARS clients. Like the TI block, a failure here never costs the RPE status.
    companion = None
    if has_ars:
        try:
            companion = L.companion_status(cid, period, row, roster)
        except (Exception, SystemExit) as e:          # noqa: BLE001 — shown, never raised
            companion = {"checks": [{"level": L.STOP, "text": f"The ARS Companion checks could not run "
                                                              f"({type(e).__name__}: {e})"}],
                         "state": "stop", "last": None, "decks": []}
    return {"client": cid, "name": (entry[1] if entry else None) or row.get("client_name"),
            "csm": row.get("csm") or (cp_row or {}).get("csm"), "period": period,
            "state": state, "checks": [{"level": l, "text": m} for l, m in checks], "last": last,
            "builds": builds_on_offer(entry[3] if entry else ["ARS"], avail, ars_only, has_ars),
            "ti": ti, "companion": companion}


def builds_on_offer(progs, avail, ars_only, has_ars):
    """What the page's buttons offer. ARS client: `base` is the plain build (ARS, plus CashPlease for a
    client who ships it as a section; Aaron, 2026-10-12) and `combined` adds the other programs with
    data. No ARS: one build, every program with data, under `combined`; `base` names the whole deck."""
    extra = L.combined_programs(avail)
    if has_ars:
        return {"ars_only": ars_only, "has_ars": True,
                "base": L.build_programs(progs, avail, False),
                "combined": ["ARS"] + extra if extra else None,
                "left_out": {p: why for p, (ok, why) in avail.items() if not ok}}
    return {"ars_only": False, "has_ars": False,
            "base": L.covered_programs(progs),
            "combined": extra or None,
            "left_out": {p: why for p, (ok, why) in avail.items() if not ok}}


# ------------------------------------------------------------------ build jobs
def build_cmd(cid, rebuild, combined=False, period=None, ti=False, companion=False, deck_only=False):
    """The child process is told WHICH cycle. Without it a build started while an earlier
    cycle is selected would quietly build today's instead — the launcher defaults to the
    calendar month, and the page would show the result under the month on screen."""
    return ([sys.executable, str(HERE / "ars_launcher.py"), "build", cid,
             "--period", period or current_period()]
            + (["--rebuild"] if rebuild else []) + (["--combined"] if combined else [])
            + (["--ti"] if ti else []) + (["--companion"] if companion else [])
            + (["--deck-only"] if deck_only else []))


# One build at a time on this PC, whichever front door started it (James Gilmore, 2026-10-30): Sheila's
# page and Sheila in Claude each keep their own queue, so the turn is taken with a lock file both see.
# The OS drops the lock when its holder exits, so a crashed build never leaves it held.
BUILD_LOCK = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("TMPDIR") or "/tmp") / "RPE" / "build.lock"


def _take_build_lock(job):
    BUILD_LOCK.parent.mkdir(parents=True, exist_ok=True)
    fh = open(BUILD_LOCK, "a+b")
    said = False
    while True:
        try:
            if os.name == "nt":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fh
        except OSError:
            if not said:
                job.lines.append("  [..]   Waiting for another build on this PC to finish")
                said = True
            time.sleep(2)


def _drop_build_lock(fh):
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass
    fh.close()


class Job:
    def __init__(self, cid, rebuild, combined=False, period=None, ti=False, companion=False, deck_only=False):
        self.cid, self.rebuild, self.combined, self.ti = cid, rebuild, combined, ti
        self.companion, self.deck_only = companion, deck_only
        # Pinned at queue time: a job waiting behind two others must build the cycle it was
        # asked for, not whichever one happens to be on screen when it starts.
        self.period = period or current_period()
        self.lines, self.done, self.code = [], False, None
        self.queued_at = time.time()
        self.started = None          # set when it leaves the queue
        self.finished = None

    def run(self):
        self.started = time.time()
        # COLUMNS keeps ars_launcher.say from wrapping a long Outputs path across two lines.
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1", COLUMNS="1000")
        lock = None
        try:
            # `ti` is passed only for a Transaction Intelligence job: the tests stub build_cmd with the
            # four-argument shape, and a fifth argument errored every stubbed job (2026-10-26).
            extra = {**({"ti": True} if self.ti else {}), **({"companion": True} if self.companion else {}),
                     **({"deck_only": True} if self.deck_only else {})}
            cmd = build_cmd(self.cid, self.rebuild, self.combined, self.period, **extra)
            lock = _take_build_lock(self)
            proc = subprocess.Popen(cmd,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                                    env=env, cwd=str(REPO))
            for line in proc.stdout:
                self.lines.append(line.rstrip("\r\n"))
            self.code = proc.wait()
        except OSError as e:
            self.lines.append(f"  [STOP] The build could not start: {e}")
            self.code = 1
        finally:
            if lock is not None:
                _drop_build_lock(lock)
        self.finished = time.time()
        forget_status(self.cid)     # the deck in Outputs and the last-build line have changed
        self.done = True
        invalidate_clients()        # and the list: rebuilt behind the page, this job laid over it meanwhile

    def deck(self):
        return next((m.group(1) for m in map(DECK_RX.search, list(self.lines)) if m), None)

    def deck_name(self):
        d = self.deck()
        return re.split(r"[\\/]", d)[-1] if d else None

    def to_json(self):
        deck = self.deck()
        waiting = [j for j in list(_queue) if not j.started]
        position = waiting.index(self) + 1 if self in waiting else None
        running = next((j.cid for j in list(_jobs.values()) if j.started and not j.done), None)
        return {"client": self.cid, "rebuild": self.rebuild, "combined": self.combined, "ti": self.ti,
                "companion": self.companion, "deck_only": self.deck_only, "lines": self.lines, "done": self.done,
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


def start_build(cid, rebuild, combined=False, ti=False, companion=False, deck_only=False):
    """Queue a build; it starts at once when nothing else is building. Returns (http status, body)."""
    with _jobs_lock:
        cur = _jobs.get(cid)
        if cur and not cur.done:
            where = "building" if cur.started else f"queued #{[j for j in _queue if not j.started].index(cur) + 1}"
            return 409, {"error": f"{cid} is already {where}."}
        job = Job(cid, rebuild, combined, ti=ti, companion=companion, deck_only=deck_only)
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


# ------------------------------------------------------------------ change log
# The page links the change log and shows the last five updates (Aaron, 2026-09-16: "Add a link to the change
# log at the top of Sheila's page, and show the last 5 updates"). CHANGELOG.md is released beside the code.
CHANGELOG = REPO / "CHANGELOG.md"
VERSION_FILE = REPO / "VERSION"


def app_version(path=None):
    """Sheila's version, the first line of the VERSION file at the root of the code (Aaron, 2026-10-26:
    "VERSION file in Sheila's header, start at 2.0"). It is bumped by hand, in the commit that adds a
    major feature; release_launcher.ps1 copies it with the code, so a released copy and the PC's local
    copy of it carry the same file. A copy without one (an old release) shows no version, not a guess."""
    try:
        text = Path(path or VERSION_FILE).read_text(encoding="utf-8-sig").strip()
    except OSError:
        return ""
    first = text.splitlines()[0].strip() if text else ""
    return first if re.fullmatch(r"\d+(\.\d+){1,2}", first) else ""
_ENTRY_RX = re.compile(r"^###\s+(\d{4}-\d{2}-\d{2})\s+[—-]+\s+(.+?)\s*$")


def _plain(md):
    """Markdown inline marks stripped for a one-line summary."""
    t = re.sub(r"`([^`]*)`", r"\1", md)
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    return re.sub(r"\s+", " ", t).strip()


# Sheila shows what changed, not the request behind it (Aaron, 2026-09-25: "rewrite the change log shown in
# Sheila to show a summary of what was updated, not my verbatim instructions"). CHANGELOG.md keeps both: each
# entry leads with a `Summary:` line, then the request as asked, then the detail. Sheila shows the summary,
# leaves out a paragraph that is the quoted request, and drops inline attributions such as "(Aaron, 2026-09-17)".
_QUOTE_PARA_RX = re.compile(r'^Aaron(?:[ ,][^:"]{0,60})?:\s*["\u201c]')
_ATTRIB_RX = re.compile(r'\s*\((?:Aaron\b[^()]*|["\u201c][^()]*?["\u201d])\)')
# A quote inside a sentence: '(Aaron: "...")' whole; ', Aaron: "..."' leaving the sentence's own full stop;
# or 'Aaron: "...".' standing as a sentence of its own, full stop and all.
_Q = r'["\u201c][^"\u201d]*["\u201d]'
_WHO = r'\bAaron(?:,\s*[^:"()]{0,40})?:\s*'
_INLINE_QUOTE_RX = re.compile(r'\s*\(' + _WHO + _Q + r'\)'
                              r'|,\s*' + _WHO + _Q
                              + r'|(?<![,\w])\s*' + _WHO + _Q + r'\.?')
SUMMARY_PREFIX = "Summary:"


def _for_sheila(text):
    """A line of the change log as Sheila shows it: inline attributions and quoted asides removed."""
    return re.sub(r"\s{2,}", " ", _ATTRIB_RX.sub("", _INLINE_QUOTE_RX.sub("", text))).strip()


def _entry_summary(paras):
    """The entry's `Summary:` line, else its first paragraph that is not the quoted request."""
    for p in paras:
        if p.startswith(SUMMARY_PREFIX):
            return p[len(SUMMARY_PREFIX):].strip()
    return next((p for p in paras if not _QUOTE_PARA_RX.match(p)), "")


def changelog_entries(n=5, path=None):
    """The newest `n` dated entries of CHANGELOG.md (newest first): [{date, title, summary, anchor}].

    summary is the entry's Summary line (else its first paragraph that is not the quoted request) as
    plain text, cut at 260 characters; anchor matches the heading id on /changelog.
    """
    try:
        lines = Path(path or CHANGELOG).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out, i = [], 0
    while i < len(lines) and len(out) < n:
        m = _ENTRY_RX.match(lines[i])
        if not m:
            i += 1
            continue
        j, paras, cur = i + 1, [], []
        while j < len(lines) and not lines[j].startswith("#"):
            if lines[j].strip():
                cur.append(lines[j].strip())
            elif cur:
                paras.append(" ".join(cur))
                cur = []
            j += 1
        if cur:
            paras.append(" ".join(cur))
        s = _plain(_for_sheila(_entry_summary(paras)))
        out.append({"date": m.group(1), "title": _plain(m.group(2)),
                    "summary": s[:260].rstrip() + ("\u2026" if len(s) > 260 else ""), "anchor": f"e{len(out)}"})
        i = j
    return out


def _md_inline(text):
    import html as _h
    t = _h.escape(text)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    return t


def release_stamp(path=None):
    """The RELEASE.txt line beside the change log, or None in a working copy.

    release_launcher.ps1 writes RELEASE.txt into Tools\\RPE with the code and CHANGELOG.md, so
    in a released copy the stamp names exactly the release every entry on the page is in. A
    checkout has no RELEASE.txt and says so."""
    try:
        text = (Path(path or CHANGELOG).parent / "RELEASE.txt").read_text(encoding="utf-8-sig").strip()
    except OSError:
        return None
    return text.splitlines()[0].strip() if text else None


def _version_html():
    """The header's version chip, or nothing when this copy has no VERSION file."""
    v = app_version()
    # app_version() only returns digits and dots, so there is nothing to escape.
    return f'<span class="ver" id="ver" title="CSM Sheila version">v{v}</span>' if v else ""


def changelog_page(path=None):
    """CHANGELOG.md as a readable page: headings, paragraphs, lists, bold and code.

    The page says which release it belongs to (Aaron, 2026-10-12: entries showed under
    "Unreleased" in Sheila, which only ever runs a released copy — the heading was a convention
    nothing updated). Everything on the page is in the release the banner names."""
    try:
        lines = Path(path or CHANGELOG).read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = ["The change log is not available in this copy."]
    stamp = release_stamp(path)
    body, para, items, n = [], [], [], 0
    if stamp:
        body.append('<p class="rel">Every change below is in this release: <b>' + _md_inline(stamp) + "</b></p>")
    else:
        body.append('<p class="rel">Working copy, not a release: the newest entries here may not have '
                    "reached the CSMs yet. A released copy names its release on this line.</p>")

    def flush():
        if para:
            text = " ".join(para)
            if text.startswith(SUMMARY_PREFIX):
                body.append('<p class="sum">' + _md_inline(_for_sheila(text[len(SUMMARY_PREFIX):])) + "</p>")
            elif not _QUOTE_PARA_RX.match(text):
                body.append("<p>" + _md_inline(_for_sheila(text)) + "</p>")
            para.clear()
        if items:
            body.append("<ul>" + "".join("<li>" + _md_inline(_for_sheila(i)) + "</li>" for i in items) + "</ul>")
            items.clear()
    for ln in lines:
        s = ln.rstrip()
        h = re.match(r"^(#{1,4})\s+(.*)$", s)
        if h:
            flush()
            lvl = len(h.group(1))
            ident = ""
            if lvl == 3 and _ENTRY_RX.match(s):
                ident = f' id="e{n}"'
                n += 1
            body.append(f"<h{lvl}{ident}>{_md_inline(_for_sheila(h.group(2)))}</h{lvl}>")
        elif re.match(r"^\s*[-*]\s+", s):
            if para:
                flush()
            items.append(re.sub(r"^\s*[-*]\s+", "", s))
        elif s.startswith("  ") and items:
            items[-1] += " " + s.strip()
        elif s.strip() in ("", "---"):
            flush()
        elif s.startswith(">"):
            para.append(s.lstrip("> "))
        else:
            if items:
                flush()
            para.append(s.strip())
    flush()
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>CSM Sheila · Change log</title><style>"
            "body{margin:0;background:#F4F6F9;color:#0E1B2A;font:15.5px/1.55 'Segoe UI',Arial,sans-serif}"
            "header{background:#00274C;color:#fff;padding:14px 24px;font-weight:700;font-size:19px}"
            "main{max-width:900px;margin:0 auto;padding:10px 20px 60px}"
            "h1{font-size:24px}h2{font-size:20px;margin-top:34px;border-bottom:2px solid #F15D22;padding-bottom:4px}"
            "h3{font-size:17px;margin:28px 0 6px;color:#00274C}p.sum{font-weight:600;background:#E9EFF6;border-left:3px solid #F15D22;padding:6px 10px;border-radius:4px}code{background:#EDF1F5;padding:1px 4px;border-radius:3px;font-size:.9em}"
            "p.rel{margin:14px 0 0;padding:8px 12px;border-radius:6px;background:#E3EEE7;color:#1E4D33;font-size:14px}"
            "@media (prefers-color-scheme: dark){body{background:#0B1520;color:#E6ECF2}h3{color:#8FB4DA}code{background:#182A3A}p.sum{background:#16283A}p.rel{background:#15301F;color:#BFE3C9}}"
            "</style></head><body><header>CSM Sheila · Change log</header><main>"
            + "\n".join(body) + "</main></body></html>")


def reveal_deck(cid, period, name):
    """Show one of a client's decks for the period in File Explorer, by its file name — the client page's
    "open the deck" link (2026-10-28), which knows names, not paths."""
    if not CID_RX.match(cid) or not re.fullmatch(r"\d{4}\.\d{2}", period):
        return 400, {"error": "not a client number and period"}
    try:
        hits = [p for p in R.output_decks(f"{cid}-{period}-*.pptx") if p.name == name]
    except (OSError, SystemExit):
        return 403, {"error": "Outputs is not reachable."}
    if not hits:
        return 404, {"error": f"{name} is not in Outputs any more."}
    return reveal(str(hits[0]))


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


# ------------------------------------------------------------------ Lift Matrix (Aaron, 2026-09-25)
# "Add functionality to Sheila to build client Lift Matrix for ARS" and "create a tab in Sheila showing the lift
# matrices across clients, and the current calculated lift matrix." The valuation is build/ars_pipeline/
# lift_values.py; nothing here decides a number. Reading an ODD takes 5-60 s, so each client's scan runs once in
# the background (one at a time, so a "calculate all" does not flood the share) and its segment figures are kept
# in Build Artifacts/lift_values/<id>.json against that ODD landing. The rates are applied per request, so
# editing them never re-reads the extract.
_lm_lock = threading.Lock()
_lm_scans = {}                     # cid -> {"state": "queued"|"scanning"|"error", "error"}
_lm_pool = ThreadPoolExecutor(1)
_lm_overview = {"doc": None, "at": 0.0, "busy": False}
# Each workbook's read_workbook(), kept in Build Artifacts/lift_values/workbooks.json against that file's size
# and modified time (Aaron, 2026-09-25: "only rescan workbook lift matrix values if the file has changed since the
# last scan"). A read is 0.4-2 s over the share and the overview needs ~40 of them, so a restart, or another CSM's
# Sheila, reads only the workbooks that changed. It lives beside the scans on the share, shared by every copy.
_lm_books = {}                     # path -> {"mtime", "size", "version", "data"}
_lm_books_lock = threading.Lock()
_lm_books_loaded = []
WORKBOOK_CACHE = "workbooks.json"
LIFT_TTL = 300
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _lv():
    p = str(REPO / "build" / "ars_pipeline")
    if p not in sys.path:
        sys.path.insert(0, p)
    import lift_values
    return lift_values


_lift_dir_made = set()


def _lift_dir():
    d = R.build_artifacts() / "lift_values"
    if str(d) not in _lift_dir_made:       # a mkdir on the share is a round trip; the overview asked 39 times
        d.mkdir(parents=True, exist_ok=True)
        _lift_dir_made.add(str(d))
    return d


def _odd_path(cid):
    return R.inputs() / "ODDD" / f"{cid}_ODDD.zip"


def _odd_key(cid):
    st = os.stat(_odd_path(cid))
    return {"odd": str(_odd_path(cid)), "mtime": st.st_mtime_ns, "size": st.st_size, "version": _lv().SCAN_VERSION}


def lift_cached_scan(cid):
    """The stored scan when it was made from the ODD now in Inputs, else None."""
    p = _lift_dir() / f"{cid}.json"
    if not p.is_file():
        return None
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
        return doc["scan"] if doc.get("key") == _odd_key(cid) else None
    except (OSError, ValueError, KeyError):
        return None


def _run_scan(cid):
    with _lm_lock:
        _lm_scans[cid] = {"state": "scanning"}
    try:
        key = _odd_key(cid)
        scan = _lv().scan(str(_odd_path(cid)))
        (_lift_dir() / f"{cid}.json").write_text(json.dumps({"key": key, "scan": scan, "at": time.time()}),
                                                  encoding="utf-8")
        with _lm_lock:
            _lm_scans.pop(cid, None)
            _lm_overview["at"] = 0.0          # the overview's calculated row is due
    except (Exception, SystemExit) as e:
        with _lm_lock:
            _lm_scans[cid] = {"state": "error", "error": str(e) or type(e).__name__}


def lift_queue_scan(cid, force=False):
    """Queue a scan unless one is queued or running, or (without `force`) a current one is stored."""
    with _lm_lock:
        if _lm_scans.get(cid, {}).get("state") in ("queued", "scanning"):
            return
    if not force and lift_cached_scan(cid) is not None:
        return
    with _lm_lock:
        _lm_scans[cid] = {"state": "queued"}
    _lm_pool.submit(_run_scan, cid)


def _lift_workbook(cid):
    """(path, read_workbook()) for the client's newest ARS workbook in Inputs, or (None, None)."""
    import build_month as BM
    per = L.newest_workbook_period(cid)
    wbs = BM.ars_workbook(R.report_dirs(), cid, per) if per else []
    if not wbs:
        return None, None
    path = wbs[-1]
    return path, _cached_workbook(path)


def _cached_workbook(path):
    """read_workbook(path), from the stored read when the file's size and modified time are unchanged."""
    path = str(path)
    st = os.stat(path)
    want = {"mtime": st.st_mtime_ns, "size": st.st_size, "version": _lv().WORKBOOK_VERSION}
    with _lm_books_lock:
        if not _lm_books_loaded:
            _lm_books.update(_load_workbook_cache())
            _lm_books_loaded.append(True)
        hit = _lm_books.get(path)
    if hit and all(hit.get(k) == v for k, v in want.items()):
        return hit["data"]
    data = _lv().read_workbook(path)             # new or changed since the last read
    with _lm_books_lock:
        _lm_books[path] = dict(want, data=data)
    _save_workbook_cache(path, _lm_books[path])
    return data


def _sheila_window(path):
    """ars_launcher._window for this server: the Lift Matrix window from the stored workbook read, so a client's
    status check does not open the workbook a second time with openpyxl (2.9 s cold, measured 2026-09-25)."""
    return _cached_workbook(path)["window"]


def _load_workbook_cache():
    try:
        doc = json.loads((_lift_dir() / WORKBOOK_CACHE).read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_workbook_cache(path, entry):
    """Merge one entry into the stored file. Another Sheila may be writing it too, so the file is re-read
    first and replaced whole; a write that fails only means that workbook is read again next time."""
    try:
        with _lm_books_lock:
            doc = _load_workbook_cache()
            doc[path] = entry
            tmp = _lift_dir() / f"{WORKBOOK_CACHE}.{os.getpid()}.part"
            tmp.write_text(json.dumps(doc), encoding="utf-8")
            os.replace(tmp, _lift_dir() / WORKBOOK_CACHE)
    except OSError:
        pass


def _roster_entry(cid):
    import build_month as BM
    return next((r for r in BM.read_roster()[0] if r[0] == cid), None)


def lift_rates(body, defaults):
    """The rates and the outlier cap from a request, each falling back to its default. ValueError on a bad one."""
    def num(k, lo, hi):
        v = body.get(k)
        if v in (None, ""):
            return defaults.get(k)
        v = float(v)
        if not lo <= v <= hi:
            raise ValueError(f"{k} {v} is outside {lo}-{hi}")
        return v
    winsor = num("winsor", 0.0, 1.0)
    if winsor not in _lv().WINSOR_OPTIONS:
        raise ValueError(f"outlier cap {winsor} is not one of {_lv().WINSOR_OPTIONS}")
    return {"ic_rate": num("ic_rate", 0.0, 0.05), "nsf_fee": num("nsf_fee", 0.0, 200.0),
            "collection": num("collection", 0.0, 1.0), "winsor": winsor}


def lift_client_doc(cid, body=None):
    """One client's current Lift Matrix (from its workbook) and the calculated one, at the rates in `body`
    (defaults when absent). Starts the ODD scan when there is no current one."""
    LV = _lv()
    entry = _roster_entry(cid)
    row = L.csm_list_row(cid)
    doc = {"client": cid, "name": (entry[1] if entry else None) or row.get("client_name"),
           "csm": row.get("csm"), "path": entry[2] if entry else None, "period": current_period()}
    try:
        wb_path, wb = _lift_workbook(cid)
    except Exception as e:                  # an unreadable workbook is reported, never guessed at
        wb_path, wb = None, None
        doc["workbook_error"] = f"{type(e).__name__}: {e}"
    doc["workbook"] = os.path.basename(wb_path) if wb_path else None
    doc["current"] = wb["matrix"] if wb else None
    assumptions = wb["assumptions"] if wb else {}
    if doc["path"] == "SM":
        # Aaron, 2026-09-25: SM clients are on the model that does not use the Lift Matrix. Shown, never built.
        doc["scan_state"] = "sm"
        return doc
    if not _odd_path(cid).is_file():
        doc["scan_state"] = "no-odd"
        return doc
    scan = lift_cached_scan(cid)
    if scan is None:
        lift_queue_scan(cid)
        with _lm_lock:
            st = dict(_lm_scans.get(cid) or {"state": "queued"})
        doc["scan_state"], doc["scan_error"] = st["state"], st.get("error")
        return doc
    doc["scan_state"] = "ready"
    defaults = LV.default_rates(scan, assumptions)
    rates = lift_rates(body or {}, defaults)
    doc.update(defaults=defaults, rates=rates,
               scan={k: v for k, v in scan.items() if k not in ("segments", "by_cap")},
               segments=scan["by_cap"][LV.cap_key(rates["winsor"])],
               winsor_options=[{"value": p, "label": LV.cap_label(p)} for p in LV.WINSOR_OPTIONS])
    if rates["nsf_fee"] is not None:
        doc["calculated"] = LV.values(scan, rates["ic_rate"], rates["nsf_fee"], rates["collection"],
                                      rates["winsor"])
    if doc["period"] and doc["name"]:
        doc["file_name"] = LV.out_name(cid, doc["period"], doc["name"])
        ap = _export_path(cid, doc["period"])
        try:
            rec = json.loads(ap.read_text(encoding="utf-8")) if ap.is_file() else None
        except (OSError, ValueError):
            rec = None
        if rec and rec.get("odd") == _odd_key(cid):
            doc["exported"] = {"rates": rec.get("rates"), "at": rec.get("exported_at"), "by": rec.get("exported_by")}
    return doc


def _lift_ready(cid, body):
    """(doc, None) when the calculated matrix can be exported at these rates, else (None, (code, error))."""
    doc = lift_client_doc(cid, body)
    if doc.get("scan_state") == "sm":
        return None, (400, {"error": "This client is on the SM model, which does not use a Lift Matrix."})
    if doc.get("scan_state") != "ready":
        return None, (409, {"error": "The ODD is still being read. Try again in a moment."})
    if "calculated" not in doc:
        return None, (400, {"error": "Enter the client's NSF/OD fee first."})
    if not doc.get("period") or not doc.get("name"):
        return None, (400, {"error": "No cycle period or client name, so the file cannot be named."})
    return doc, None


def _export_path(cid, period):
    return _lift_dir() / f"{cid}-{period}-exported.json"


def lift_export(cid, body):
    """Record the calculated matrix as exported at these rates, just before its download (Aaron, 2026-09-25:
    "Instead of Approve this matrix, use Export this matrix"; it was an approval step). The record — rates,
    the ODD landing, the values — is kept in Build Artifacts, and the download is only served for exactly
    what was recorded."""
    doc, err = _lift_ready(cid, body)
    if err:
        return err
    rec = {k: doc.get(k) for k in ("client", "name", "period", "workbook", "rates", "defaults", "scan", "calculated")}
    rec.update(odd=_odd_key(cid), exported_at=time.strftime("%Y-%m-%d %H:%M:%S"),
               exported_by=os.environ.get("USERNAME") or os.environ.get("USER") or "")
    _export_path(cid, doc["period"]).write_text(json.dumps(rec, indent=1), encoding="utf-8")
    return 200, {"ok": True, "exported_at": rec["exported_at"], "file_name": doc["file_name"]}


def lift_download(cid, body):
    """(code, xlsx bytes | error, file name). Refused unless the matrix was exported at these very rates
    from the ODD that is in Inputs now — the page records the export and downloads in one click."""
    import io
    doc, err = _lift_ready(cid, body)
    if err:
        return err[0], err[1], None
    p = _export_path(cid, doc["period"])
    rec = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
    if not rec or rec.get("rates") != doc["rates"] or rec.get("odd") != _odd_key(cid):
        return 409, {"error": "Export the matrix at these rates first."}, None
    buf = io.BytesIO()
    _lv().write_xlsx(doc["calculated"], buf)
    return 200, buf.getvalue(), doc["file_name"]


def compute_lift_overview():
    """Every ARS client's current workbook Lift Matrix, and the calculated one at default rates where the
    ODD has been read."""
    import build_month as BM
    LV = _lv()
    roster, _ = BM.read_roster()
    rows = {}
    p = R.csm_list_file()
    if p and p.is_file():
        with open(p, encoding="utf-8-sig", newline="") as fh:
            rows = {r.get("client_id", "").strip(): r for r in csv.DictReader(fh)}

    def one(entry):
        cid, name, path, _ = entry
        c = {"id": cid, "name": name or rows.get(cid, {}).get("client_name"),
             "csm": rows.get(cid, {}).get("csm") or "Unassigned", "path": path}
        try:
            wb_path, wb = _lift_workbook(cid)
        except Exception as e:
            wb_path, wb = None, None
            c["error"] = f"{type(e).__name__}"
        m = wb["matrix"] if wb else None
        c["workbook"] = os.path.basename(wb_path) if wb_path else None
        if m:
            c.update(window=m["window"], data_date=m["data_date"], expired=m["data_past_end"],
                     current={s: (m["segments"].get(s) or {}).get("dda") for s in ["NH"] + LV.SEGMENTS})
        try:
            scan = lift_cached_scan(cid) if path == "MM" and _odd_path(cid).is_file() else None
        except OSError:
            scan = None
        if scan:
            d = LV.default_rates(scan, wb["assumptions"] if wb else {})
            if d["nsf_fee"] is not None:
                v = LV.values(scan, d["ic_rate"], d["nsf_fee"], d["collection"], d["winsor"])
                c["calculated"] = {r["segment"]: r["dda"] for r in v["segments"]}
        return c

    ars = [r for r in roster if "ARS" in r[3]]
    with ThreadPoolExecutor(PREWARM_WORKERS) as ex:
        out = list(ex.map(one, ars))
    out.sort(key=lambda c: (c["csm"], (c["name"] or "").lower()))
    return {"period": current_period(), "segments": ["NH"] + LV.SEGMENTS, "clients": out}


def _refresh_lift_overview():
    try:
        doc = compute_lift_overview()
        with _lm_lock:
            _lm_overview.update(doc=doc, at=time.time())
    finally:
        with _lm_lock:
            _lm_overview["busy"] = False


def lift_overview_doc():
    """Served from memory; rebuilt in the background when older than LIFT_TTL or after a save/scan."""
    with _lm_lock:
        doc, at, busy = _lm_overview["doc"], _lm_overview["at"], _lm_overview["busy"]
        scans = {k: v["state"] for k, v in _lm_scans.items()}
        start = not busy and (doc is None or time.time() - at >= LIFT_TTL)
        if start:
            _lm_overview["busy"] = True
    if start:
        threading.Thread(target=_refresh_lift_overview, daemon=True).start()
    return {"doc": doc, "refreshing": busy or start, "scans": scans,
            "age_seconds": round(time.time() - at) if doc else None}


def lift_scan_all():
    """Queue an ODD scan for every MM ARS client whose ODD is in Inputs and has no current scan. SM clients
    do not use a Lift Matrix."""
    import build_month as BM
    n = 0
    for cid, _, path, progs in BM.read_roster()[0]:
        if "ARS" in progs and path == "MM" and _odd_path(cid).is_file() and lift_cached_scan(cid) is None:
            lift_queue_scan(cid)
            n += 1
    with _lm_lock:
        _lm_overview["at"] = 0.0
    return 200, {"queued": n}


# ------------------------------------------------------------------ data issues and code sheets (Aaron, 2026-09-25)
# "build a new tab into Sheila with the data issues identified for each client" and "create a link on the individual
# client pages that links to the code sheet saved in the inputs folder". Nothing here finds an issue: the Data Issues
# tab shows what two existing checks already wrote, each with its own date, because they refresh on different days.
#   Build Artifacts/issue_pages/gaps.json       the issue pages' per-client list (severity, program, issue, fix)
#   Build Artifacts/perf_dashboard/dataset.json the morning dashboard's checks: codes the client's code tables do not
#                                               map (perf_actions), Lift Matrix flags, and what could not be checked
#   Build Artifacts/issue_pages/odd_findings.json what the ODD and Workbook Issues page finds beyond gaps.json: the
#                                               Personal/Business and Mail Flag scans, the trial run, the Lift Matrix
#                                               date window (Aaron, 2026-10-02: "the refresh for data issues should
#                                               also refresh what's shown in Sheila")
SEVERITY_ORDER = {"blocker": 0, "decision": 1, "gap": 2, "warning": 3}
CODE_SHEET_EXTS = (".xls", ".xlsx", ".xlsm")
_CODE_STAMP_RX = re.compile(r"-(\d{6}_\d{6})-")
_issues_cache = {"key": None, "doc": None}


def _read_json(p):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


_code_sheets = {"key": None, "map": {}}


def code_sheets_by_client():
    """{client id: newest code sheet Path} from Inputs/Code Sheets (newest by the data team's stamp, else mtime).
    Listed again only when the folder changes: a file saved, replaced or removed there changes its modified time."""
    d = R.inputs() / R.INPUT_KIND_DIRS["Code sheets"]
    if not d.is_dir():
        return {}
    key = d.stat().st_mtime_ns
    if _code_sheets["key"] == key:
        return _code_sheets["map"]
    best = {}
    for p in d.iterdir():
        m = re.match(r"^(\d{3,5})-", p.name)
        if not m or p.name.startswith("~$") or p.suffix.lower() not in CODE_SHEET_EXTS:
            continue
        s = _CODE_STAMP_RX.search(p.name)
        rank = (s.group(1), 0.0) if s else ("", p.stat().st_mtime)     # a stamped name needs no stat
        if m.group(1) not in best or rank > best[m.group(1)][0]:
            best[m.group(1)] = (rank, p)
    _code_sheets.update(key=key, map={cid: p for cid, (_, p) in best.items()})
    return _code_sheets["map"]


def code_sheet(cid):
    return code_sheets_by_client().get(cid)


def open_code_sheet(cid, action):
    """Open the client's newest code sheet in its program, or show it in File Explorer. Only a file in
    Inputs/Code Sheets named for this client can be opened; the path never comes from the page."""
    p = code_sheet(cid)
    if not p:
        return 404, {"error": f"No code sheet for {cid} in Inputs/Code Sheets."}
    if action == "reveal":
        subprocess.Popen(["explorer", "/select,", str(p)])
    else:
        os.startfile(str(p))                 # noqa: S606 — a file this server found, by client id
    return 200, {"ok": True, "file": p.name}


_reports = {"doc": None, "at": 0.0}
REPORTS_TTL = 30          # the share is the only reader and writer; a short cache is plenty


def invalidate_reports():
    _reports["doc"], _reports["at"] = None, 0.0


def reports_doc():
    """Reported issues for the Reported tab: the queue on the share, plus the GitHub state
    the last sync cached. Never calls gh — this runs on a CSM's machine."""
    import time as _t
    if _reports["doc"] is not None and _t.time() - _reports["at"] < REPORTS_TTL:
        return _reports["doc"]
    try:
        import issue_reports as IR
        doc = IR.view()
    except Exception as e:
        doc = {"error": f"{type(e).__name__}: {e}", "rows": [], "fetched_at": None, "queued": 0}
    _reports["doc"], _reports["at"] = doc, _t.time()
    return doc


def issues_doc():
    """Every client's data issues from all three sources, grouped by client. Re-read only when a file changes."""
    ba = R.build_artifacts()
    gp, dp = ba / "issue_pages" / "gaps.json", ba / "perf_dashboard" / "dataset.json"
    op = ba / "issue_pages" / "odd_findings.json"
    key = tuple((str(p), p.stat().st_mtime_ns if p.is_file() else None) for p in (gp, dp, op))
    if _issues_cache["key"] == key:
        doc = _issues_cache["doc"]
    else:
        gaps, ds, odd = _read_json(gp) or {}, _read_json(dp) or {}, _read_json(op) or {}
        clients = {}

        def entry(cid, name, csm):
            e = clients.setdefault(cid, {"id": cid, "name": name, "csm": csm or "Unassigned", "issues": [],
                                         "codes": [], "lift_matrix": None, "unchecked": []})
            e["name"] = e["name"] or name
            if csm and e["csm"] == "Unassigned":
                e["csm"] = csm
            return e
        for c in gaps.get("clients", []):
            entry(c["id"], c.get("name"), c.get("csm"))
        for i in gaps.get("issues", []):
            entry(i["id"], i.get("name"), i.get("csm"))["issues"].append(
                {k: i.get(k) for k in ("severity", "program", "issue", "fix")})
        for c in ds.get("clients", []):
            e = entry(c["id"], c.get("name"), c.get("csm"))
            a = c.get("actions") or {}
            e["codes"] = [{k: x.get(k) for k in ("label", "values", "no_table", "eligibility")}
                          for x in a.get("codes", [])]
            e["lift_matrix"], e["unchecked"] = a.get("lift_matrix"), a.get("unchecked") or []
        for f in odd.get("findings", []):
            e = entry(f["id"], f.get("name"), f.get("csm"))
            if f.get("src") == "lift_window" and e["lift_matrix"]:
                continue                     # the dashboard's Lift Matrix flag already says it
            i = {k: f.get(k) for k in ("severity", "program", "issue", "fix")}
            if i not in e["issues"]:
                e["issues"].append(i)
        for e in clients.values():
            e["issues"].sort(key=lambda i: (SEVERITY_ORDER.get(i["severity"], 9), i.get("program") or ""))
            e["count"] = len(e["issues"]) + len(e["codes"]) + (1 if e["lift_matrix"] else 0)
        doc = {"clients": sorted(clients.values(), key=lambda e: (e["csm"], (e["name"] or "").lower())),
               "sources": {"issue_pages": (gaps.get("summary") or {}).get("generated"),
                           "dashboard": ds.get("generated")}}
        _issues_cache.update(key=key, doc=doc)
    sheets, done, wbs = code_sheets_by_client(), _load_done(), workbooks_by_client()
    out = dict(doc, clients=[dict(_with_marks(e, done, wbs),
                                  code_sheet=sheets[e["id"]].name if e["id"] in sheets else None)
                             for e in doc["clients"]])
    return out


# ------------------------------------------------------------------ marking an issue complete (Aaron, 2026-09-28)
# "on the Data Issues tab, I'd like to option to mark those items complete. They should stay marked complete until
# we see a new workbook for that client, and then the status can be evaluated." A mark records the client's newest
# workbooks at that moment (ARS workbook, MRPCPM analysis, ICS workbook); while those are unchanged the item stays
# complete, and when any of them is replaced by a newer file the item comes back, saying when it was marked and which
# workbook arrived since. Marks live on the share beside the issue pages' data, so every copy of Sheila sees them.
WORKBOOK_KINDS = ("Workbook", "MRPCPM", "ICS workbook")
DONE_FILE = "done.json"
_wb_names = {"key": None, "map": {}}
_done_cache = {"key": None, "doc": {}}


def issue_key(cid, kind, *parts):
    """A stable id for one item: the client, what kind of item, and its own text. New wording is a new item."""
    import hashlib
    raw = "\x1f".join([cid, kind] + [str(p or "") for p in parts])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def workbooks_by_client():
    """{client id: sorted newest workbook file name per kind}, from the three workbook folders in Inputs.
    Listed again only when a folder changes."""
    dirs = [R.inputs() / R.INPUT_KIND_DIRS[k] for k in WORKBOOK_KINDS]
    key = tuple(d.stat().st_mtime_ns if d.is_dir() else None for d in dirs)
    if _wb_names["key"] == key:
        return _wb_names["map"]
    best = {}
    for kind, d in zip(WORKBOOK_KINDS, dirs):
        if not d.is_dir():
            continue
        for p in d.iterdir():
            m = re.match(r"^(\d{3,5})-(\d{4}\.\d{2})-", p.name)
            if not m or p.name.startswith("~$") or p.suffix.lower() not in (".xlsx", ".xlsm", ".xls"):
                continue
            k = (m.group(1), kind)
            if k not in best or (m.group(2), p.name) > best[k]:
                best[k] = (m.group(2), p.name)
    out = {}
    for (cid, _kind), (_per, name) in best.items():
        out.setdefault(cid, []).append(name)
    _wb_names.update(key=key, map={cid: sorted(v) for cid, v in out.items()})
    return _wb_names["map"]


def _done_path():
    d = R.build_artifacts() / "issue_pages"
    d.mkdir(parents=True, exist_ok=True)
    return d / DONE_FILE


def _load_done():
    p = _done_path()
    try:
        key = p.stat().st_mtime_ns
    except OSError:
        return {}
    if _done_cache["key"] != key:
        _done_cache.update(key=key, doc=_read_json(p) or {})
    return _done_cache["doc"]


def _items(e):
    """(key, short text) for every item of one client, as the page lists them."""
    cid = e["id"]
    for i in e["issues"]:
        yield issue_key(cid, "issue", i.get("program"), i.get("issue")), f"{i.get('program') or ''} {i.get('issue') or ''}".strip()
    for c in e["codes"]:
        vals = sorted(str(v.get("value")) for v in (c.get("values") or []))
        yield issue_key(cid, "codes", c.get("label"), *vals), f"{c.get('label')}: {', '.join(vals)}"
    if e.get("lift_matrix"):
        lm = e["lift_matrix"]
        yield issue_key(cid, "lift", lm.get("flag"), lm.get("workbook")), f"Lift Matrix flagged \"{lm.get('flag')}\""


def _with_marks(e, done, wbs):
    """One client's entry with each item's key and state: open, complete, or reopened by a newer workbook."""
    e = dict(e, issues=[dict(i) for i in e["issues"]], codes=[dict(c) for c in e["codes"]],
             lift_matrix=dict(e["lift_matrix"]) if e.get("lift_matrix") else None)
    now = wbs.get(e["id"], [])
    targets = e["issues"] + e["codes"] + ([e["lift_matrix"]] if e["lift_matrix"] else [])
    open_n = done_n = 0
    for item, (key, _text) in zip(targets, _items(e)):
        item["key"] = key
        rec = done.get(key)
        if rec and rec.get("workbooks") == now:
            item["done"] = {"by": rec.get("by"), "at": rec.get("at")}
            done_n += 1
        else:
            if rec:     # marked, but a workbook has changed since: evaluate it again
                item["reopened"] = {"by": rec.get("by"), "at": rec.get("at"),
                                    "new": [w for w in now if w not in (rec.get("workbooks") or [])]}
            open_n += 1
    e["count"], e["done_count"] = open_n, done_n
    return e


def mark_issue(cid, key, done):
    """Mark one item complete (or not). The key must be one of this client's current items."""
    d = issues_doc()
    e = next((x for x in d["clients"] if x["id"] == cid), None)
    items = dict(_items(e)) if e else {}
    if key not in items:
        return 404, {"error": "That item is not on this client's list any more. Reload the page."}
    with _lm_books_lock:
        doc = dict(_read_json(_done_path()) or {})
        if done:
            doc[key] = {"client": cid, "item": items[key],
                        "by": os.environ.get("USERNAME") or os.environ.get("USER") or "",
                        "at": time.strftime("%Y-%m-%d %H:%M"),
                        "workbooks": workbooks_by_client().get(cid, [])}
        else:
            doc.pop(key, None)
        tmp = _done_path().with_name(f"{DONE_FILE}.{os.getpid()}.part")
        tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        os.replace(tmp, _done_path())
        _done_cache.update(key=None)
    return 200, {"ok": True}


# ------------------------------------------------------------------ Slide Review (Aaron, 2026-10-27, 2026-10-28)
# "an evaluation process for all of the decks so the CSM can vote whether to keep or delete a slide, or to add it
# to an appendix." Then: not tied to a client. A CSM opens Sheila and a deck side by side and elects on the PROGRAM's
# slide list (ARS, ICS, MRPC, CashPlease, Transaction Intelligence, ARS Companion); the Summary is per program. The
# list is read from the newest decks of that program in Outputs. The record (one JSON file per vote under
# Build Artifacts/slide_votes/) and the counting are in slide_votes.py; the tab's page is in slide_review_ui.py.
# The lists are the build process, not the decks (Aaron, 2026-10-29: "the decks all carry the same slides,
# because they're all built using the same processes. We shouldn't need to scan the decks"): each program's
# slides come from build/slide_inventory.py -- the template shell with the slides its builder adds, the
# Transaction Intelligence register, the Companion's view titles -- read from the repo in well under a
# second and never from Outputs. Nothing here touches the share.
import slide_inventory as SI


def votes_program_slides(program):
    """The program's slides to elect on: [{n, title, source, key, deck}], in deck order."""
    return [{"n": r["n"], "title": r["title"], "source": r["source"],
             "key": program + "|" + SV.norm_title(r["title"]), "deck": r["source"]}
            for r in SI.inventory().get(program, [])]


def votes_programs_doc():
    me = SV.whoami()
    votes = SV.read_votes()
    progs = []
    for prog in SV.PROGRAMS:
        slides = votes_program_slides(prog)
        held = SV.mine(votes, me, prog)
        progs.append({"id": prog, "label": SV.PROGRAM_LABEL[prog], "slides": len(slides),
                      "voted": sum(1 for s in slides if (held.get(s["key"]) or {}).get("vote")),
                      "starred": sum(1 for s in slides if (held.get(s["key"]) or {}).get("star"))})
    return {"period": current_period(), "me": me, "programs": progs,
            "from": "the templates and the builders, the same slides for every client"}


def votes_program_doc(program):
    if program not in SV.PROGRAMS:
        return 400, {"error": "not a program"}
    me = SV.whoami()
    held = SV.mine(SV.read_votes(), me, program)
    slides = []
    for s in votes_program_slides(program):
        h = held.get(s["key"])
        slides.append(dict(s, mine=({"vote": h.get("vote", ""), "star": bool(h.get("star")),
                                    "comment": h.get("comment", "")} if h else None)))
    return 200, {"program": program, "label": SV.PROGRAM_LABEL[program], "me": me, "period": current_period(),
                 "slides": slides}


def votes_vote(body):
    """Record one vote, a star, or both. The slide named must be a slide of the program's list now.

    The page sends the slide's whole state (vote, star, comment), so a star click keeps the vote and the reverse."""
    program = str(body.get("program", "")).strip()
    try:
        v = SV.check_vote(program, body.get("slide"), body.get("title"), body.get("vote"), body.get("comment"),
                          bool(body.get("star")))
    except SV.VoteError as e:
        return 400, {"error": str(e)}
    match = next((s for s in votes_program_slides(program) if s["title"] == v["title"]), None)
    if match is None:
        return 409, {"error": "The decks were rebuilt since the page loaded. Open the program again."}
    doc = SV.write_vote(program, match["n"], v["title"], v["vote"], v["comment"], v["star"],
                        deck=match["deck"], client_name="the client")
    return 200, {"ok": True, "vote": doc["vote"], "star": doc["star"], "at": doc["at"]}


def votes_summary_doc(program=""):
    votes = SV.read_votes()
    cur = SV.latest(votes)
    return {"rows": SV.aggregate(votes, program or None), "votes": len([v for v in cur if v.get("vote")]),
            "stars": len([v for v in cur if v.get("star")]), "voters": len({v["voter"] for v in cur}),
            "programs": [{"id": p, "label": SV.PROGRAM_LABEL[p]} for p in SV.PROGRAMS]}


def votes_route(handler, path, params):
    """GET /api/votes/<what>: the tab's reads. (The one POST, /api/votes/vote, is routed in do_POST.)"""
    program = params.get("program", "") if params.get("program", "") in SV.PROGRAMS else ""
    if path == "/api/votes/programs":
        return handler._send(200, votes_programs_doc())
    if path == "/api/votes/program":
        return handler._send(*votes_program_doc(str(params.get("program", ""))))
    if path == "/api/votes/summary":
        return handler._send(200, votes_summary_doc(program))
    if path == "/api/votes/export":
        import datetime as _dt
        csv_text = SV.summary_csv(SV.aggregate(SV.read_votes(), program or None))
        return handler._send(200, csv_text.encode("utf-8"), "text/csv; charset=utf-8",
                             filename=f"slide-votes-{_dt.date.today().isoformat()}.csv")
    return handler._send(404, {"error": "not found"})


# ------------------------------------------------------------------ HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "ARSDeckBuilder"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8", filename=None):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        if filename:
            from urllib.parse import quote
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(filename)}")
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
            return self._send(200, PAGE.replace("__TOKEN__", TOKEN).replace("__VERSION__", _version_html()).encode("utf-8"), "text/html; charset=utf-8")
        if u.path == "/changelog":
            return self._send(200, changelog_page().encode("utf-8"), "text/html; charset=utf-8")
        if not self._api_ok():
            return self._send(403, {"error": "forbidden"})
        q = parse_qs(u.query)
        cid = (q.get("client") or [""])[0].strip()
        try:
            if u.path == "/api/clients":
                fresh = (q.get("fresh") or [""])[0] == "1"
                return self._send(200, clients_doc(fresh=True) if fresh else clients_doc())
            if u.path == "/api/queue":
                return self._send(200, queue_doc())
            if u.path == "/api/changelog":
                return self._send(200, {"entries": changelog_entries(5)})
            if u.path in ("/api/status", "/api/job"):
                if not CID_RX.match(cid):
                    return self._send(400, {"error": "not a client number"})
                if u.path == "/api/status":
                    return self._send(200, status_doc(cid, fresh=(q.get("fresh") or [""])[0] == "1", background=True))
                return self._send(200, job_doc(cid) or {})
            if u.path == "/api/issues":
                return self._send(200, issues_doc())
            if u.path == "/api/reports":
                return self._send(200, reports_doc())
            if u.path.startswith("/api/votes/"):
                return votes_route(self, u.path, {k: v[0] for k, v in q.items()})
            if u.path.startswith("/api/ils/"):
                return ils_ui.get(self, u.path, {k: v[0] for k, v in q.items()})
            if u.path == "/api/lift/overview":
                return self._send(200, lift_overview_doc())
            if u.path == "/api/lift/client":
                if not CID_RX.match(cid):
                    return self._send(400, {"error": "not a client number"})
                return self._send(200, lift_client_doc(cid, {k: v[0] for k, v in q.items()}))
        except (OSError, SystemExit, ValueError, KeyError) as e:
            return self._send(500, {"error": f"{type(e).__name__}: {e}"})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        # Read the body BEFORE refusing (2026-10-02). Answering 403 and closing with the body
        # still unread makes Windows reset the connection, so the caller got
        # ConnectionAbortedError instead of the 403 -- 28 in 2,000 tokenless POSTs, 127 with a
        # 100 KB body, and the occasional failure of test_the_api_refuses_a_call_without_the_token
        # under a loaded full run. Capped, so a refused caller cannot make the server read without
        # limit.
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if n < 0 or n > MAX_POST_BYTES:
            self.close_connection = True
            return self._send(413 if n > 0 else 400, {"error": "bad request"})
        raw = self.rfile.read(n) if n else b""
        if not self._api_ok():
            return self._send(403, {"error": "forbidden"})
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            return self._send(400, {"error": "bad request"})
        path = urlparse(self.path).path
        if path == "/api/build":
            cid = str(body.get("client", "")).strip()
            if not CID_RX.match(cid):
                return self._send(400, {"error": "not a client number"})
            return self._send(*start_build(cid, bool(body.get("rebuild")), bool(body.get("combined")),
                                           bool(body.get("ti")),
                                           **({"companion": True} if body.get("companion") else {})))
        if path == "/api/cycle":
            want = body.get("period")
            try:
                now = select_period(str(want).strip() if want else None)
            except ValueError as e:
                return self._send(400, {"error": str(e)})
            return self._send(200, {"period": now, "periods": available_periods(),
                                    "cycle_now": L.cycle_period()})
        if path == "/api/votes/vote":
            return self._send(*votes_vote(body))
        if path.startswith("/api/ils/"):
            return ils_ui.post(self, path, body)
        if path == "/api/reveal":
            if body.get("deck"):
                return self._send(*reveal_deck(str(body.get("client", "")), str(body.get("period", "")),
                                               str(body.get("deck", ""))))
            return self._send(*reveal(str(body.get("path", ""))))
        if path in ("/api/lift/export", "/api/lift/download", "/api/lift/rescan"):
            cid = str(body.get("client", "")).strip()
            if not CID_RX.match(cid):
                return self._send(400, {"error": "not a client number"})
            try:
                if path == "/api/lift/rescan":
                    lift_queue_scan(cid, force=True)
                    return self._send(200, {"ok": True})
                if path == "/api/lift/download":
                    code, data, name = lift_download(cid, body)
                    if code != 200:
                        return self._send(code, data)
                    return self._send(200, data, XLSX, filename=name)
                return self._send(*lift_export(cid, body))
            except ValueError as e:
                return self._send(400, {"error": str(e)})
            except (OSError, SystemExit, KeyError) as e:
                return self._send(500, {"error": f"{type(e).__name__}: {e}"})
        if path == "/api/issues/mark":
            cid, key = str(body.get("client", "")).strip(), str(body.get("key", "")).strip()
            if not CID_RX.match(cid) or not re.fullmatch(r"[0-9a-f]{16}", key):
                return self._send(400, {"error": "bad request"})
            try:
                return self._send(*mark_issue(cid, key, bool(body.get("done"))))
            except OSError as e:
                return self._send(500, {"error": f"{type(e).__name__}: {e}"})
        if path == "/api/report":
            title = str(body.get("title", "")).strip()
            if not title:
                return self._send(400, {"error": "a report needs a title"})
            if len(title) > 200 or len(str(body.get("body", ""))) > 8000:
                return self._send(400, {"error": "report too long"})
            cid = str(body.get("client", "")).strip()
            if cid and not CID_RX.match(cid):
                return self._send(400, {"error": "bad client"})
            try:
                import issue_reports as IR
                rec = IR.queue(title, str(body.get("body", "")), client_id=cid or None,
                               page=str(body.get("page", ""))[:80] or None)
                invalidate_reports()
                return self._send(200, {"ok": True, "id": rec["id"]})
            except Exception as e:
                return self._send(500, {"error": f"{type(e).__name__}: {e}"})

        if path == "/api/code-sheet":
            cid = str(body.get("client", "")).strip()
            if not CID_RX.match(cid):
                return self._send(400, {"error": "not a client number"})
            try:
                return self._send(*open_code_sheet(cid, "reveal" if body.get("action") == "reveal" else "open"))
            except OSError as e:
                return self._send(500, {"error": f"{type(e).__name__}: {e}"})
        if path == "/api/lift/scan-all":
            return self._send(*lift_scan_all())
        return self._send(404, {"error": "not found"})


def make_server(port=0):
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main(argv=None):
    ap = argparse.ArgumentParser(description="CSM Sheila, the Smart Helper for Executive Insights, Layouts & Analytics: the browser front end for ars_launcher.")
    ap.add_argument("--port", type=int, default=0, help="default: any free port")
    ap.add_argument("--no-open", action="store_true", help="don't open a browser")
    a = ap.parse_args(argv)
    srv = make_server(a.port)
    install_share_caches()
    _renew["on"] = True
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
<title>CSM Sheila</title>
<style>
:root{
  --navy:#00274C; --orange:#F15D22; --teal:#0E9F8C; --gold:#D9A21B; --ground:#F4F6F9; --surface:#FFFFFF; --soft:#EDF1F5;
  --ink:#0E1B2A; --ink2:#566370; --ink3:#566370; --rule:#D8DEE5;
  --ok:#1E7F4F; --ok-bg:#E4F3EB; --warn:#9A6212; --warn-bg:#FBF0DC; --sent:#245C8C; --sent-bg:#E6EEF6;
  --stop:#B42318; --stop-bg:#FCE9E7; --focus:#F15D22; --sel:#E9EFF6;
  --dot-ars:#00274C;
  /* The light on the chips and small buttons (Aaron, 2026-10-28): a highlight along the top edge, shade
     along the bottom and a line where the chip meets the page, each softer in the dark. */
  --hi:rgba(255,255,255,.6); --lo:rgba(0,0,0,.08); --touch:rgba(0,0,0,.14);
  --build:#B4500E; --build-bg:#FDE8DA;
}
@media (prefers-color-scheme: dark){:root{
  --ground:#0B1520; --surface:#12202D; --soft:#182A3A; --ink:#E6ECF2; --ink2:#A7B4C1; --ink3:#A7B4C1; --rule:#26384A;
  --ok:#57C98F; --ok-bg:#12302A; --warn:#E6B45C; --warn-bg:#33270F; --sent:#8FB4DA; --sent-bg:#16283A;
  --stop:#F08579; --stop-bg:#3A1C1A; --sel:#1B3044;
  /* The ARS dot is brand navy, which vanishes on the navy-black ground (Aaron, 2026-10-15:
     "the ARS dot is too hard to see in dark mode"); steel blue here, the same blue the links use. */
  --dot-ars:#8FB4DA;
  --hi:rgba(255,255,255,.09); --lo:rgba(0,0,0,.35); --touch:rgba(0,0,0,.5);
  --build:#F7A86B; --build-bg:#3A2412;
}}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font:15px/1.45 "Segoe UI",Calibri,Arial,sans-serif}
header.top{background:var(--navy);color:#fff;padding:14px 24px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
header.top h1{margin:0;font-size:19px;font-weight:700;letter-spacing:.01em}
header.top h1 .ver{margin-left:10px;font-size:12.5px;font-weight:600;opacity:.8;letter-spacing:0}
header.top .news{margin-left:auto;position:relative}
header.top .news summary{cursor:pointer;list-style:none;font-weight:600;font-size:13.5px;padding:5px 12px;border:1px solid rgba(255,255,255,.45);border-radius:999px}
header.top .news summary::-webkit-details-marker{display:none}
header.top .news[open] summary{background:rgba(255,255,255,.12)}
header.top .newsbox{position:absolute;right:0;top:36px;z-index:20;width:min(460px,92vw);background:var(--surface);color:var(--ink);border:1px solid var(--rule);border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,.25);padding:12px 14px;max-height:70vh;overflow:auto}
header.top .newsbox ol{list-style:none;margin:0;padding:0;display:grid;gap:10px}
header.top .newsbox li a{color:var(--ink);text-decoration:none;display:block}
header.top .newsbox li a:hover b{text-decoration:underline}
header.top .newsbox .d{color:var(--ink3);font-size:12px;font-variant-numeric:tabular-nums}
header.top .newsbox .s{color:var(--ink2);font-size:12.5px;display:block;margin-top:2px}
header.top .newsbox .all{display:inline-block;margin-top:10px;font-weight:600;color:var(--sent)}
header.top .loglink{color:#fff;font-size:13.5px;font-weight:600;text-decoration:underline}
header.top .period{margin-left:0;background:var(--orange);color:#fff;font-weight:700;font-size:12.5px;letter-spacing:.04em;padding:5px 12px;border-radius:999px;border:0;cursor:pointer;font-family:inherit;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.3),inset 0 -2px 0 rgba(0,0,0,.22),0 1px 2px rgba(0,0,0,.35),0 4px 12px rgba(241,93,34,.42);
  transition:box-shadow .12s ease,transform .12s ease,filter .12s ease}
header.top .period:hover{filter:brightness(1.06)}
header.top .period:active{transform:translateY(1px);box-shadow:inset 0 2px 4px rgba(0,0,0,.3)}
header.top .period:focus-visible{outline:2px solid #fff;outline-offset:2px}
header.top .period .caret{font-size:10px;opacity:.85;margin-left:5px}
.cycles{position:absolute;top:46px;right:18px;z-index:40;background:var(--surface);border:1px solid var(--rule);
  border-radius:10px;box-shadow:0 10px 26px rgba(0,0,0,.18);padding:6px;min-width:190px}
.cycles h4{margin:4px 8px 6px;font:700 11px/1 "Segoe UI",Arial,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--ink2)}
.cycles button{display:block;width:100%;text-align:left;font:600 13.5px/1.2 "Segoe UI",Arial,sans-serif;
  border:0;background:none;color:var(--ink);padding:7px 9px;border-radius:7px;cursor:pointer}
.cycles button:hover{background:var(--soft)}
.cycles button[aria-current="true"]{background:var(--navy);color:#fff}
.cycles .now{font-weight:400;opacity:.75;font-size:12px}
.app{display:grid;grid-template-columns:minmax(260px,330px) minmax(0,1fr);gap:18px;max-width:1240px;margin:18px auto;padding:0 18px}
@media (max-width:820px){.app{grid-template-columns:1fr}}
aside,main{background:var(--surface);border:1px solid var(--rule);border-radius:10px}
aside{display:flex;flex-direction:column;max-height:calc(100vh - 100px);min-height:420px}
.filters{padding:14px;display:grid;gap:8px;border-bottom:1px solid var(--rule)}
label.small{font-size:11.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--ink3)}
input,select{font:inherit;color:var(--ink);background:var(--surface);border:1px solid var(--rule);border-radius:7px;padding:7px 9px;width:100%}
input:focus-visible,select:focus-visible,button:focus-visible{outline:2px solid var(--focus);outline-offset:2px}
.list{overflow:auto;padding:6px}
.client{display:grid;grid-template-columns:3.4em 1fr auto;gap:2px 8px;width:100%;text-align:left;font:inherit;color:inherit;background:none;border:0;border-top:1px solid var(--rule);border-radius:0;padding:8px 9px;cursor:pointer}
.grouphead + .client,.legend + .client{border-top:0}
.client:hover{background:var(--soft)}
.client[aria-current="true"]{background:var(--sel)}
.client .id{font-family:Consolas,monospace;font-size:13px;color:var(--ink2);padding-top:1px}
.client .nm{font-weight:600}
.client .meta{grid-column:2/4;display:flex;gap:6px;flex-wrap:wrap;font-size:12px;color:var(--ink2)}
.client .meta:empty{display:none}
/* Option B (Aaron, 2026-10-13): four dots in a fixed order, ARS · ICS · MRPC · CP, in their own right-hand
   column; filled when the program is in this client's deck, grey when not. The legend sits at the top of the list. */
.pdots{grid-column:3;grid-row:1;display:inline-flex;gap:4px;align-items:center;padding-top:5px}
.pdot{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--rule);border:0}
.pdot.ars{background:var(--dot-ars)} .pdot.ics{background:var(--orange)} .pdot.mrpc{background:var(--teal)} .pdot.cp{background:var(--gold)}
.legend{display:flex;gap:12px;align-items:center;font-size:11px;color:var(--ink2);padding:6px 9px 4px}
.legend .pdot{margin-right:4px;vertical-align:-1px}
.chip.blocked{background:var(--stop-bg);color:var(--stop)}
.grouphead{font-size:11.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--ink3);padding:12px 9px 4px}
/* The status chips carry the same light as the buttons, scaled to their size: every chip is a tint with
   the page-level highlight and shade. Building and Error were solid fills until 2026-10-28 (Aaron: "some
   dark, some light"); they are tints like the rest now, orange and red. */
.chip{display:inline-block;font-size:11.5px;font-weight:600;padding:1px 7px;border-radius:999px;background:var(--soft);color:var(--ink2);white-space:nowrap;
  box-shadow:inset 0 1px 0 var(--hi),inset 0 -1px 0 var(--lo),0 1px 1px var(--touch)}
.chip.out{background:var(--ok-bg);color:var(--ok)}
.chip.stop{background:var(--stop-bg);color:var(--stop)} .chip.ready{background:var(--ok-bg);color:var(--ok)}
.chip.queue{background:var(--warn-bg);color:var(--warn)}
.chip.building{background:var(--build-bg);color:var(--build)}
.chip.error{background:var(--stop-bg);color:var(--stop)}
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
.btns{display:flex;flex-wrap:wrap;gap:8px}
/* The action buttons are lit, not flat (Aaron, 2026-10-27): toned down the same day: the glow was too strong. A highlight
   along the top edge, shade along the bottom, a line where it meets the page, and a glow in its own
   colour; pressing it drops the highlight for an inset shade and moves it down a pixel. */
button.primary{font:600 15px/1 "Segoe UI",Arial,sans-serif;background:var(--navy);color:#fff;border:0;border-radius:8px;padding:11px 16px;cursor:pointer;
  --glow:rgba(0,39,76,.16);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.16),inset 0 -1px 0 rgba(0,0,0,.16),0 1px 2px rgba(0,0,0,.22),0 2px 6px var(--glow);
  transition:box-shadow .12s ease,transform .12s ease,filter .12s ease}
button.primary:hover{filter:brightness(1.08)}
button.primary:active{transform:translateY(1px);box-shadow:inset 0 2px 4px rgba(0,0,0,.32),0 1px 1px rgba(0,0,0,.2)}
button.primary.warn{background:var(--orange);--glow:rgba(241,93,34,.18)}
button.primary:disabled{background:var(--ink3);cursor:not-allowed;box-shadow:none;transform:none;filter:none}
@media (prefers-reduced-motion:reduce){button.primary,header.top .period,.tabs button,.chipbtn{transition:none}}
button.link{font:inherit;background:none;border:0;color:var(--sent);text-decoration:underline;cursor:pointer;padding:0}
.progress{margin-top:20px}
.progress .notes{margin:6px 0 4px;padding-left:18px;font-size:13.5px;color:var(--ink2)} .progress .notes .warn{color:var(--warn)}
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
.last{margin-top:18px;color:var(--ink2);font-size:14px}
/* The client page cards (2026-10-28): one per presentation, the passed checks folded away. */
.card{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:12px 16px;margin-top:10px}
.card.stopcard{border-color:var(--stop)}
.cardhead{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:flex-start;justify-content:space-between}
.cardhead h3{margin:0;font-size:15.5px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.cardhead .mix{font-weight:500;color:var(--ink2);font-size:13px}
.card .act{display:grid;gap:4px;justify-items:end;margin-left:auto} .card .act .why{font-size:11.5px;color:var(--ink3)}
.card .fact{margin:6px 0 0;font-size:13.5px;color:var(--ink2)} .card .fact b{color:var(--ink);font-weight:600}
.card .checks{margin-top:8px}
.card .fold{margin-top:6px;font-size:12.5px;color:var(--ink3)} .card .fold summary{cursor:pointer}
.card .fold .checks{margin-top:6px;font-size:13.5px;color:var(--ink2)}
.card .small{margin:4px 0 0;font-size:12.5px;color:var(--ink3)} .card .progress{margin-top:12px}
.cards-note{font-size:12.5px;color:var(--ink3);margin-top:12px;max-width:70ch}
button.quiet{font:600 14px/1 "Segoe UI",Arial,sans-serif;background:var(--soft);color:var(--ink);border:1px solid var(--rule);border-radius:8px;padding:10px 14px;cursor:pointer;
  box-shadow:inset 0 1px 0 var(--hi),inset 0 -1px 0 var(--lo),0 1px 2px var(--touch)}
button.quiet:active{transform:translateY(1px);box-shadow:inset 0 1px 3px rgba(0,0,0,.18)}
.ti{margin-top:26px;padding-top:16px;border-top:1px solid var(--rule)}
.ti .tihead{margin:0 0 10px;font-size:16px} .ti .tihead .sub{font-weight:400;margin-left:8px}
.note{color:var(--ink2);font-size:13px;margin-top:14px}
.err{color:var(--stop)}
.asof{margin:2px 0 0;font-size:12px;color:var(--ink3)} .asof .link{font-size:12px}
/* The tabs sit in a rail recessed into the header; the selected tab is raised out of it with the same
   shade, touch line and glow as the buttons, and presses in like them. */
.tabs{display:flex;gap:4px;background:rgba(0,0,0,.16);border-radius:999px;padding:3px;
  box-shadow:inset 0 1px 2px rgba(0,0,0,.35),inset 0 -1px 0 rgba(255,255,255,.08)}
.tabs button{font:600 13.5px/1 "Segoe UI",Arial,sans-serif;color:#fff;background:none;border:0;border-radius:999px;padding:6px 14px;cursor:pointer;
  transition:background .12s ease,box-shadow .12s ease,transform .12s ease}
.tabs button:hover{background:rgba(255,255,255,.12)}
.tabs button:active{transform:translateY(1px)}
.tabs button[aria-selected="true"]{background:#fff;color:var(--navy);
  box-shadow:inset 0 -2px 0 rgba(0,39,76,.14),0 1px 2px rgba(0,0,0,.35),0 4px 12px rgba(0,0,0,.28)}
.tabs button[aria-selected="true"]:active{box-shadow:inset 0 2px 4px rgba(0,0,0,.18)}
.lmwrap{overflow-x:auto;margin-top:10px}
.app.wide{max-width:1640px;grid-template-columns:minmax(220px,270px) minmax(0,1fr)}
@media (max-width:820px){.app.wide{grid-template-columns:1fr}}
table.lm{border-collapse:collapse;font-size:13.5px;font-variant-numeric:tabular-nums;width:100%}
table.lm th,table.lm td{padding:5px 7px;border-bottom:1px solid var(--rule);text-align:right;white-space:nowrap}
table.lm th{font-size:11.5px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--ink3);background:var(--soft)}
table.lm th:first-child,table.lm td:first-child,table.lm td.l{text-align:left}
table.lm tr.calc td{color:var(--sent)} table.lm tr.grp td{border-bottom:0}
table.lm tr.pick{cursor:pointer} table.lm tr.pick:hover td{background:var(--soft)}
table.lm td.up{color:var(--ok)} table.lm td.down{color:var(--stop)}
table.lm.rep th,table.lm.rep td{text-align:left;vertical-align:top}
table.lm.rep td:nth-child(3){white-space:normal;overflow-wrap:anywhere;width:60%}
.rates{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:6px 0 14px}
.rates label{display:grid;gap:4px;font-size:13px;font-weight:600}
.rates .src{font-weight:400;font-size:12px;color:var(--ink3)}
.rates .fld{display:flex;align-items:center;gap:6px} .rates .fld span{color:var(--ink2);font-size:13px}
.panel{margin-top:18px} .panel h3{font-size:13px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--ink3);margin:0 0 6px}
.grids{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:16px}
.gridbox h4{margin:0 0 4px;font-size:13.5px;color:var(--ink2)}
.recalc{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:-4px 0 6px}
#lm-out.stale{opacity:.45}
.icard{border:1px solid var(--rule);border-radius:8px;padding:10px 14px;margin:10px 0}
.icard li.irow{grid-template-columns:4.2em 1fr auto}
.icard .imark{align-self:center;white-space:nowrap}
.icard li.idone > span:nth-child(2){color:var(--ink3)}
.ihead{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:baseline;margin-bottom:8px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px}
.reportbtn{margin-left:10px;background:transparent;border:1px solid rgba(255,255,255,.5);color:#fff;
  border-radius:6px;padding:5px 11px;font:600 12.5px/1 inherit;cursor:pointer}
.reportbtn:hover{background:rgba(255,255,255,.14)}
dialog.report{border:0;border-radius:10px;padding:0;max-width:560px;width:92vw;box-shadow:0 18px 50px rgba(0,0,0,.3)}
dialog.report::backdrop{background:rgba(10,20,32,.45)}
dialog.report form{padding:20px 22px 18px;display:grid;gap:12px}
dialog.report h3{margin:0;font-size:17px;color:var(--navy)}
dialog.report label{display:grid;gap:4px;font-size:13px;color:var(--ink2)}
dialog.report input[type=text],dialog.report textarea{font:14px/1.5 inherit;padding:8px 10px;
  border:1px solid var(--rule);border-radius:6px;width:100%;box-sizing:border-box}
dialog.report textarea{min-height:110px;resize:vertical}
dialog.report .row{display:flex;gap:8px;justify-content:flex-end;align-items:center}
dialog.report .hint{font-size:12.5px;color:var(--ink2);margin-right:auto;max-width:44ch}
.rep-state{display:inline-block;font:600 11.5px/1 inherit;padding:4px 7px;border-radius:4px;color:#fff}
.rep-open{background:#1d7a46}.rep-closed{background:#5a6670}.rep-queued{background:#9a6400}
.chipbtn{font:600 12.5px/1 "Segoe UI",Arial,sans-serif;border:1px solid var(--rule);background:var(--surface);color:var(--ink2);border-radius:999px;padding:6px 11px;cursor:pointer;
  box-shadow:inset 0 1px 0 var(--hi),inset 0 -1px 0 var(--lo),0 1px 2px var(--touch);
  transition:box-shadow .12s ease,transform .12s ease,border-color .12s ease}
.chipbtn:hover{border-color:var(--ink3)}
.chipbtn:active{transform:translateY(1px);box-shadow:inset 0 1px 3px rgba(0,0,0,.18)}
.chipbtn[aria-pressed="true"]{background:var(--navy);color:#fff;border-color:var(--navy);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.3),inset 0 -2px 0 rgba(0,0,0,.24),0 1px 2px rgba(0,0,0,.35),0 4px 12px rgba(0,39,76,.38)}
.chipbtn[aria-pressed="true"]:active{box-shadow:inset 0 2px 4px rgba(0,0,0,.32)}
.method{font-size:13px;color:var(--ink2);margin:6px 0 0;padding-left:18px;display:grid;gap:3px}
/* the client links row, identical on every tab */
.clientlinks{margin:-6px 0 12px;font-size:13px;color:var(--ink2)}
.ihead .clientlinks{margin:0}
</style>
</head>
<body>
<header class="top"><h1>CSM Sheila__VERSION__</h1><nav class="tabs" role="tablist" aria-label="View"><button role="tab" id="tab-decks" aria-selected="true">Decks</button><button role="tab" id="tab-lift" aria-selected="false">Lift Matrix</button><button role="tab" id="tab-issues" aria-selected="false">Data Issues</button><button role="tab" id="tab-reported" aria-selected="false">Feedback</button></nav><button type="button" class="reportbtn" id="reportbtn" title="Report a problem with Sheila or a deck">Report an issue</button><details class="news" id="news"><summary>What's new</summary><div class="newsbox"><ol id="newslist"><li class="small">Loading…</li></ol><a class="all" href="/changelog" target="_blank" rel="noopener">Full change log</a></div></details><a class="loglink" href="/changelog" target="_blank" rel="noopener">Change log</a><button type="button" class="period" id="period" aria-haspopup="true" aria-expanded="false">Loading…</button></header>
<dialog class="report" id="repdlg"><form method="dialog" id="repform">
  <h3>Report an issue</h3>
  <label>What is wrong?<input type="text" id="reptitle" maxlength="200" required
    placeholder="e.g. Lift Matrix tab is slow for 1549"></label>
  <label>Any detail that would help fix it<textarea id="repbody" maxlength="8000"
    placeholder="What you did, what happened, what you expected. A client number helps."></textarea></label>
  <div class="row">
    <span class="hint" id="rephint">Saved to the share now; it reaches GitHub on the next sync.</span>
    <button type="button" class="link" id="repcancel">Cancel</button>
    <button type="submit" class="primary" id="repsend">Report it</button>
  </div>
</form></dialog>
<div class="app">
  <aside aria-label="Clients">
    <div class="filters">
      <label class="small" for="csm">CSM</label>
      <select id="csm"><option value="">All CSMs</option></select>
      <label class="small" for="q">Find a client</label>
      <input id="q" type="search" placeholder="Name or number" autocomplete="off">
      <p class="asof" id="asof" aria-live="polite"></p>
    </div>
    <div class="list" id="list" role="list"></div>
  </aside>
  <main id="main" aria-live="polite">
    <div class="empty">
      <h2>Pick a client</h2>
      <p>Choose a client on the left to see whether their deck can be built this cycle.</p>
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
let CLIENTS = [], PERIOD = null, current = null, poller = null, armed = false, statusTimer = null, HOLD = false;
let PERIODS = [], CYCLE_NOW = null;

function paintPeriod() {
  const b = $("#period");
  if (!b) return;
  const back = PERIOD && CYCLE_NOW && PERIOD !== CYCLE_NOW;
  b.innerHTML = (PERIOD ? "Cycle " + esc(PERIOD) : "No period") + (back ? ' <span class="caret">◂ past</span>' : ' <span class="caret">▾</span>');
  b.title = back ? "Looking at a finished cycle. Click to go back to " + CYCLE_NOW : "Click to look at an earlier cycle";
}

function closeCycles() {
  const m = $("#cycles");
  if (m) m.remove();
  const b = $("#period");
  if (b) b.setAttribute("aria-expanded", "false");
}

async function pickCycle(period) {
  closeCycles();
  const b = $("#period");
  if (b) b.textContent = "Loading…";
  try {
    const {body} = await api("/api/cycle", {method: "POST", body: JSON.stringify({period})});
    PERIOD = body.period; PERIODS = body.periods || PERIODS; CYCLE_NOW = body.cycle_now || CYCLE_NOW;
    paintPeriod();
    // Re-draw the tab rather than poking at one element: the open client's checks, the lift
    // overview and the issue list were all about the other cycle. (It read an id named
    // "detail" that this page does not have, so every cycle change threw after switching.)
    await loadClients(true);
    setMode(MODE);
  } catch (e) {
    paintPeriod();
    alert("Could not change cycle: " + e.message);
  }
}

function openCycles() {
  if ($("#cycles")) return closeCycles();
  const list = PERIODS.length ? PERIODS : (PERIOD ? [PERIOD] : []);
  const menu = document.createElement("div");
  menu.className = "cycles"; menu.id = "cycles";
  menu.innerHTML = '<h4>Cycle</h4>' + list.map(p =>
    `<button type="button" data-cycle="${esc(p)}" aria-current="${p === PERIOD}">${esc(p)}` +
    (p === CYCLE_NOW ? ' <span class="now">· this month</span>' : "") + "</button>").join("");
  document.body.appendChild(menu);
  $("#period").setAttribute("aria-expanded", "true");
  menu.addEventListener("click", ev => {
    const b = ev.target.closest("button[data-cycle]");
    if (b) pickCycle(b.dataset.cycle);
  });
  setTimeout(() => document.addEventListener("click", function off(ev) {
    if (!ev.target.closest("#cycles") && ev.target.id !== "period") { closeCycles(); document.removeEventListener("click", off); }
  }), 0);
  document.addEventListener("keydown", function esc(ev) {
    if (ev.key === "Escape") { closeCycles(); $("#period").focus(); document.removeEventListener("keydown", esc); }
  });
}
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

// Four dots after each client, fixed order ARS · ICS · MRPC · CP (Aaron, 2026-10-13, option B): filled when
// the program is in this client's deck, grey when not, so every row has the same shape and nothing wraps.
// The client's other Velocity products are on the client page, not in the list.
const DOT_ORDER = ["ARS", "ICS", "MRPC", "CP"], DOT_NAME = {ARS: "ARS", ICS: "ICS", MRPC: "MRPC", CP: "CashPlease"};
function dots(c) {
  const covered = new Set(c.covered || []);
  const title = DOT_ORDER.filter(p => covered.has(p)).map(p => DOT_NAME[p]).join(" · ") || "no program";
  // "pdot", not "dot": the build-progress steps already use .dot (12px, 2px border), and the program dots
  // picked that border up the first time (Aaron, 2026-10-13: "the dots worked without the border").
  return `<span class="pdots" title="${esc(title)}">` +
    DOT_ORDER.map(p => `<span class="pdot${covered.has(p) ? " " + p.toLowerCase() : ""}"></span>`).join("") + `</span>`;
}
const LEGEND = `<div class="legend">` + DOT_ORDER.map(p => `<span><span class="pdot ${p.toLowerCase()}"></span>${DOT_NAME[p]}</span>`).join("") + `</div>`;

function renderList() {
  const csm = $("#csm").value, q = $("#q").value.trim().toLowerCase();
  const shown = CLIENTS.filter(c => (!csm || c.csm === csm) && (!q || c.id.includes(q) || (c.name || "").toLowerCase().includes(q)));
  let html = "", last = null;
  for (const c of shown) {
    if (!csm && c.csm !== last) { html += `<div class="grouphead">${esc(c.csm)}</div>`; last = c.csm; }
    const place = QUEUE.queued.indexOf(c.id);
    const idle = QUEUE.building !== c.id && place < 0;
    const d = new Date(), today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    const builtToday = c.built_at && c.built_at.slice(0, 10) === today ? c.built_at.slice(11, 16) : "";
    const quiet = idle && !c.error && !c.lift_expired && !c.decks.length;
    const chips = [QUEUE.building === c.id ? `<span class="chip building">Building</span>` : "",
                   place >= 0 ? `<span class="chip queue">Queued #${place + 1}</span>` : "",
                   c.error && idle ? `<span class="chip error">Error ${esc(PERIOD || "")}</span>` : "",
                   c.ready && quiet ? `<span class="chip ready">Ready</span>` : "",
                   c.blocked && idle && !c.lift_expired && !c.decks.length
                     ? `<span class="chip blocked" title="The checks stop here; open the client to see why">Blocked · ${esc(c.blocked)}</span>` : "",
                   !c.checked && !c.ready && !c.blocked && quiet ? `<span class="chip" title="This month's checks have not run for this client yet">Checking…</span>` : "",
                   c.lift_expired ? `<span class="chip stop">Lift Matrix expired</span>` : "",
                   c.decks.length ? `<span class="chip out">In Outputs ${esc(PERIOD || "")}${builtToday ? " · built " + esc(builtToday) : ""}</span>` : "",
                   (c.ti_decks || []).length ? `<span class="chip out" title="Transaction Intelligence decks, a separate presentation">TI in Outputs</span>` : "",
                   (c.companion_decks || []).length ? `<span class="chip out" title="The ARS Companion deck, a separate presentation">Companion in Outputs</span>` : ""].join("");
    html += `<button class="client" role="listitem" data-id="${esc(c.id)}" aria-current="${current === c.id}">
      <span class="id">${esc(c.id)}</span><span class="nm">${esc(c.name)}</span>${dots(c)}<span class="meta">${chips}</span></button>`;
  }
  $("#list").innerHTML = html ? LEGEND + html : `<p class="note" style="padding:10px">No clients match.</p>`;
}

// The list is served from the server's memory and rebuilt behind it (2026-09-17). The page shows the last
// list it had at once (sessionStorage, labelled as saved), then the server's, with its age.
const LIST_KEY = "sheila-clients";
let clientsTimer = null;

function ago(sec) { return sec == null ? "" : sec < 60 ? "just now" : sec < 3600 ? Math.round(sec / 60) + " min ago" : Math.round(sec / 3600) + " h ago"; }

function applyClients(body, saved) {
  CLIENTS = body.clients || []; PERIOD = body.period;
  if (body.periods) PERIODS = body.periods;
  if (body.cycle_now) CYCLE_NOW = body.cycle_now;
  paintPeriod();
  const csms = [...new Set(CLIENTS.map(c => c.csm))];
  const keep = $("#csm").value;
  $("#csm").innerHTML = `<option value="">All CSMs</option>` + csms.map(c => `<option>${esc(c)}</option>`).join("");
  const want = $("#csm").dataset.touched ? keep : (recall("ars-builder-csm") || keep);
  if (want && csms.includes(want)) $("#csm").value = want;
  renderList();
  let note;
  if (saved) note = "Saved list from earlier. Updating…";
  else if (body.refreshing) note = `List as of ${ago(body.age_seconds)}. Updating…`;
  else note = `List as of ${ago(body.age_seconds)} · <button class="link" id="relist">Refresh</button>`;
  if (!saved && body.refresh_error) note += ` <span class="err">Last update failed: ${esc(body.refresh_error)}</span>`;
  $("#asof").innerHTML = note;
  const rl = $("#relist"); if (rl) rl.addEventListener("click", () => loadClients(true));
}

async function loadClients(fresh) {
  clearTimeout(clientsTimer);
  let wait = 60000;
  try {
    const {body} = await api("/api/clients" + (fresh ? "?fresh=1" : ""));
    applyClients(body, false);
    try { sessionStorage.setItem(LIST_KEY, JSON.stringify(body)); } catch (e) {}
    // Still being rebuilt, or Lift Matrix dates still being read in the background: ask again shortly.
    wait = (body.refreshing || fresh) ? 2500 : body.lift_pending ? 8000 : 60000;
  } catch (e) {
    $("#list").innerHTML = `<p class="err" style="padding:10px">Couldn't load clients: ${esc(e.message)}. Check the VPN and reload.</p>`;
    wait = 15000;
  } finally {
    clearTimeout(clientsTimer);
    clientsTimer = setTimeout(() => loadClients(), wait);
  }
}

const LEVEL = {ok: ["ok", "ok"], warn: ["warn", "!!"], ask: ["ask", "built"], stop: ["stop", "stop"]};

async function select(id, fresh) {
  current = id; armed = false; clearInterval(poller); clearTimeout(statusTimer); renderList();
  const c = CLIENTS.find(x => x.id === id) || {id};
  $("#main").innerHTML = `<div class="head"><h2>${esc(c.name || id)}</h2><span class="sub">${esc(id)} · ${esc(c.csm || "")}</span></div><p class="note">Checking the client and this month's data…</p>`;
  try {
    const {body} = await api("/api/status?client=" + encodeURIComponent(id) + (fresh ? "&fresh=1" : ""));
    if (current !== id) return;
    renderStatus(body);
    if (body.job && !body.job.done) follow(id);
    else if (body.job) renderJob(body.job);
    if (body.refreshing) statusTimer = setTimeout(() => recheckQuietly(id), 2000);
  } catch (e) {
    $("#main").innerHTML += `<p class="err">Couldn't check ${esc(id)}: ${esc(e.message)}</p>`;
  }
}

// A stored status older than ten minutes is shown at once while the server checks again; the Build buttons
// wait for the fresh one, which replaces it here without clearing the page.
async function recheckQuietly(id) {
  try {
    const {body} = await api("/api/status?client=" + encodeURIComponent(id));
    if (current !== id) return;
    if (body.refreshing) { statusTimer = setTimeout(() => recheckQuietly(id), 2000); return; }
    if (poller && body.job && !body.job.done) return;     // a build started meanwhile owns the panel
    renderStatus(body);
    if (body.job) renderJob(body.job);
  } catch (e) { statusTimer = setTimeout(() => recheckQuietly(id), 5000); }
}

// The client page is cards, one per presentation (Aaron, 2026-10-28: "hard to follow because there's so
// much text"): the Executive Review, and for an ARS client the Transaction Intelligence cut and the ARS
// Companion. A card says each thing once — a state chip, one line on the last build, the checks that need
// attention with the passed ones folded away, and a short button with its consequence under it. The three
// panels used to state "in Outputs" three times each (a BUILT row, a verdict box and a last-build line).
function deckCard(o) {
  const k = o.key || "";
  const rows = (o.checks || []).map(c => ({...c, cls: LEVEL[c.level] || ["step", c.level]}));
  const needs = r => r.level === "stop" || r.level === "warn";
  const shown = rows.filter(needs), folded = rows.filter(r => !needs(r));
  const li = r => `<li><span class="tag ${r.cls[0]}">${r.cls[1]}</span><span>${esc(r.text)}</span></li>`;
  const visible = shown.length ? `<ul class="checks">${shown.map(li).join("")}</ul>` : "";
  const fold = folded.length ? `<details class="fold"><summary>${folded.length}${shown.length ? " other" : ""} check${folded.length === 1 ? "" : "s"} passed</summary><ul class="checks">${folded.map(li).join("")}</ul></details>` : "";
  const decks = o.decks || [];
  const state = o.state === "stop" ? `<span class="chip stop">Can't build yet</span>`
    : decks.length ? `<span class="chip out">In Outputs</span>` : `<span class="chip ready">Ready to build</span>`;
  // One link per deck: Transaction Intelligence makes a deck per lens, so a client on both gets two files.
  const lens = n => { const m = n.match(/-TI-(ARS|ICS)-/); return m ? `the ${m[1]} lens` : n; };
  const open = decks.map(n => `<button class="link" data-reveal="${esc(n)}">${decks.length > 1 ? "open " + esc(lens(n)) : "open the deck"}</button>`).join(" · ");
  const l = o.last;
  let fact = "";
  if (l && l.delivered) fact = `Built <b>${esc(l.finished)}</b> by ${esc(l.by)} · ${esc(l.result)}`;
  else if (l) fact = `<span class="err">Last build ${esc(l.finished)} by ${esc(l.by)} was not put in Outputs: ${esc(l.result)}</span>`;
  else if (decks.length) fact = `${decks.length === 1 ? "Deck" : "Decks"} in Outputs`;
  if (open) fact += (fact ? " · " : "") + open;
  const why = o.state === "stop" ? "" : `<span class="why">${o.state === "ask" ? `replaces the ${decks.length > 1 ? "decks" : "deck"} in Outputs` : "goes to Outputs when it passes validation"}</span>`;
  // The ids are written out in full so the page test can see each one is created (test_every_element...).
  const jobBox = {"": '<div id="job"></div>', ti: '<div id="jobti"></div>', comp: '<div id="jobcomp"></div>'}[k];
  const recheck = {"": '<button class="quiet" id="recheck">', ti: '<button class="quiet" id="tirecheck">', comp: '<button class="quiet" id="comprecheck">'}[k];
  const act = o.state === "stop" ? `${recheck}Check again</button>` : o.buttons;
  return `<section class="card${o.state === "stop" ? " stopcard" : ""}" id="${o.id}">
    <div class="cardhead"><h3>${esc(o.title)}${o.mix ? ` <span class="mix">${esc(o.mix)}</span>` : ""} ${state}</h3><div class="act">${act}${why}</div></div>
    ${fact ? `<p class="fact">${fact}</p>` : ""}${o.note || ""}${visible}${fold}${jobBox}</section>`;
}

function renderStatus(s) {
  const c = CLIENTS.find(x => x.id === s.client) || {};
  // The last build failed: the list shows the red Error pill, and the button offers the retry.
  const failed = c.error || (s.job && s.job.done && s.job.code);
  // Up to two builds (Aaron, 2026-09-16): ARS only, and a combined deck with every other program whose
  // data is on hand. Aaron's multi-program clients get only the combined one.
  const b = s.builds || {ars_only: true, has_ars: true, base: ["ARS"], combined: null, left_out: {}};
  const combo = b.combined ? b.combined.join(" + ") : "";
  // The plain build is ARS, or ARS + CP for a client whose CashPlease slides ship as a section
  // (Aaron, 2026-10-12): the button says which, so "ARS only" never hides a CashPlease section.
  // A client with no ARS has one build, every program with data (Aaron, 2026-10-13).
  const noArs = b.has_ars === false;
  const baseList = b.base && b.base.length ? b.base : ["ARS"];
  const plain = baseList.join(" + ");
  const base = baseList.length > 1 ? plain : "ARS only";
  const leftOut = Object.entries(b.left_out || {}).map(([p, why]) => `${p} left out: ${why}`).join(" · ");
  // When the plain build and the combined build carry the same programs (1585: ARS + CP, no ICS or MRPC), the two
  // buttons would build the identical deck: show one (Aaron, 2026-10-28, "These buttons should be ... the current
  // labels are unclear").
  const sameDeck = !!b.combined && b.ars_only && baseList.join("+") === b.combined.join("+");
  // Two builds on offer name themselves; one build is just "Build", and the card's subtitle says what it makes.
  const two = b.ars_only && !!b.combined && !sameDeck;
  const btns = (ask) => {
    const cls = ask ? "primary warn" : "primary", verb = failed ? (ask ? "Retry rebuild" : "Retry build") : (ask ? "Rebuild" : "Build");
    let h = "";
    if (b.ars_only) h += `<button class="${cls}" id="go">${verb}${two ? " " + esc(base) : ""}</button>`;
    if (b.combined && !sameDeck) h += `<button class="${cls}" id="go2">${verb}${two ? " combined" : ""}</button>`;
    return `<span class="btns">${h}</span>`;
  };
  const mix = noArs ? (b.combined && b.combined.length < baseList.length ? `${plain}; the build carries ${combo}` : b.combined ? combo : plain)
    : sameDeck ? `${plain}, one deck` : two ? `${base}, or combined (${combo})` : b.combined ? `${combo}, combined` : plain;
  const note = (leftOut ? `<p class="small">${esc(leftOut)}</p>` : "") + (failed ? `<p class="small err">The last build failed; see why below.</p>` : "");
  const age = s.age_seconds == null ? "" : (s.age_seconds < 60 ? "checked just now" : `checked ${Math.round(s.age_seconds / 60)} min ago`) + (s.refreshing ? ", checking again…" : "");
  const review = deckCard({key: "", id: "rpepanel", title: "Executive Review", mix, state: s.state, checks: s.checks, last: s.last,
                           decks: c.decks || [],
                           buttons: btns(s.state === "ask"), note});
  const aside = (s.ti || s.companion)
    ? `<p class="cards-note">${s.ti ? "Transaction Intelligence" : ""}${s.ti && s.companion ? " and " : ""}${s.companion ? "the ARS Companion" : ""} ${s.ti && s.companion ? "are separate presentations" : "is a separate presentation"} filed beside the Executive Review; building one never changes another.</p>`
    : "";
  $("#main").innerHTML = `<div class="head"><h2>${esc(s.name || c.name || s.client)}</h2><span class="sub">${esc(s.client)} · ${esc(s.csm || c.csm || "")} · ${esc(s.period || "")}</span>
      <span class="sub" style="margin-left:auto">${esc(age)} · <button class="link" id="refresh">Check again</button></span></div>
    <p class="note clientlinks" id="clientlinks">&nbsp;</p>${review}${tiPanel(s)}${companionPanel(s)}${aside}`;
  clientLinks(s.client, "decks");
  for (const el of document.querySelectorAll("#main [data-reveal]")) el.addEventListener("click", async () => {
    try { await api("/api/reveal", {method: "POST", body: JSON.stringify({client: s.client, period: s.period, deck: el.dataset.reveal})}); }
    catch (e) { el.insertAdjacentHTML("afterend", ` <span class="err">${esc(e.message)}</span>`); }
  });
  const go = $("#go"); if (go) go.addEventListener("click", () => build(s, false));
  const go2 = $("#go2"); if (go2) go2.addEventListener("click", () => build(s, true));
  const goti = $("#goti"); if (goti) goti.addEventListener("click", () => buildTI(s));
  const gocomp = $("#gocomp"); if (gocomp) gocomp.addEventListener("click", () => buildComp(s));
  const recomp = $("#comprecheck"); if (recomp) recomp.addEventListener("click", () => select(s.client, true));
  const re = $("#recheck"); if (re) re.addEventListener("click", () => select(s.client, true));
  const reti = $("#tirecheck"); if (reti) reti.addEventListener("click", () => select(s.client, true));
  const rf = $("#refresh"); if (rf) rf.addEventListener("click", () => select(s.client, true));
  HOLD = !!s.refreshing;
  if (HOLD) for (const b of [go, go2, goti, gocomp]) if (b) { b.disabled = true; b.title = "Waiting for the fresh check"; }
}

// The Transaction Intelligence panel (Aaron, 2026-10-23): a SEPARATE presentation from the approved
// Executive Review, with its own checks and its own button. Only an ARS client carries one.
function tiPanel(s) {
  const t = s.ti;
  if (!t) return "";
  const failed = t.last && !t.last.delivered;
  const buttons = `<span class="btns"><button class="primary${t.state === "ask" ? " warn" : ""}" id="goti">${t.state === "ask" ? "Rebuild" : failed ? "Retry" : "Build"}</button></span>`;
  return deckCard({key: "ti", id: "tipanel", title: "Transaction Intelligence", mix: "one deck per lens", state: t.state, checks: t.checks,
                   last: t.last, decks: t.decks || [], buttons});
}

async function buildTI(s) {
  const go = $("#goti"), others = [$("#go"), $("#go2")].filter(Boolean);
  if (s.ti.state === "ask" && armed !== "ti") { armed = "ti"; go.textContent = "Yes, rebuild the Transaction Intelligence decks"; return; }
  go.disabled = true; go.textContent = "Starting…";
  for (const b of others) b.disabled = true;
  try {
    const {status, body} = await api("/api/build", {method: "POST", body: JSON.stringify({client: s.client, rebuild: s.ti.state === "ask", ti: true})});
    if (status === 409) { go.disabled = false; for (const b of others) b.disabled = false; go.textContent = "Try again"; ($("#jobti") || $("#job")).innerHTML = `<p class="err">${esc(body.error)}</p>`; return; }
    go.textContent = body.queued ? `Queued #${body.queued}` : "Building…";
    pollQueue();
    follow(s.client);
  } catch (e) { go.disabled = false; for (const b of others) b.disabled = false; go.textContent = "Try again"; ($("#jobti") || $("#job")).innerHTML = `<p class="err">${esc(e.message)}</p>`; }
}

// The ARS Companion panel (Aaron, 2026-10-27): James Gilmore's analysis slides as a deck of their own, a SEPARATE
// presentation from the approved Executive Review, with its own checks and its own button. ARS clients only.
function companionPanel(s) {
  const t = s.companion;
  if (!t) return "";
  const failed = t.last && !t.last.delivered;
  const buttons = `<span class="btns"><button class="primary${t.state === "ask" ? " warn" : ""}" id="gocomp">${t.state === "ask" ? "Rebuild" : failed ? "Retry" : "Build"}</button></span>`;
  return deckCard({key: "comp", id: "comppanel", title: "ARS Companion", mix: "James's analysis slides", state: t.state, checks: t.checks,
                   last: t.last, decks: t.decks || [], buttons});
}

async function buildComp(s) {
  const go = $("#gocomp"), others = [$("#go"), $("#go2"), $("#goti")].filter(Boolean);
  if (s.companion.state === "ask" && armed !== "companion") { armed = "companion"; go.textContent = "Yes, rebuild the ARS Companion deck"; return; }
  go.disabled = true; go.textContent = "Starting…";
  for (const b of others) b.disabled = true;
  try {
    const {status, body} = await api("/api/build", {method: "POST", body: JSON.stringify({client: s.client, rebuild: s.companion.state === "ask", companion: true})});
    if (status === 409) { go.disabled = false; for (const b of others) b.disabled = false; go.textContent = "Try again"; ($("#jobcomp") || $("#job")).innerHTML = `<p class="err">${esc(body.error)}</p>`; return; }
    go.textContent = body.queued ? `Queued #${body.queued}` : "Building…";
    pollQueue();
    follow(s.client);
  } catch (e) { go.disabled = false; for (const b of others) b.disabled = false; go.textContent = "Try again"; ($("#jobcomp") || $("#job")).innerHTML = `<p class="err">${esc(e.message)}</p>`; }
}

async function build(s, combined) {
  const go = $(combined ? "#go2" : "#go"), other = $(combined ? "#go" : "#go2");
  const kind = combined ? "combined" : "ars";
  const baseName = (s.builds && s.builds.base && s.builds.base.length > 1) ? s.builds.base.join(" + ") : "ARS only";
  const noArs = s.builds && s.builds.has_ars === false;
  if (s.state === "ask" && armed !== kind) { armed = kind; go.textContent = combined ? (noArs ? `Yes, rebuild ${s.builds.combined.join(" + ")}` : "Yes, rebuild the combined deck") : `Yes, rebuild ${baseName}`; return; }
  go.disabled = true; go.textContent = "Starting…";
  if (other) other.disabled = true;
  try {
    const {status, body} = await api("/api/build", {method: "POST", body: JSON.stringify({client: s.client, rebuild: s.state === "ask", combined})});
    if (status === 409) { go.disabled = false; if (other) other.disabled = false; go.textContent = "Try again"; $("#job").innerHTML = `<p class="err">${esc(body.error)}</p>`; return; }
    go.textContent = body.queued ? `Queued #${body.queued}` : "Building…";
    pollQueue();
    follow(s.client);
  } catch (e) { go.disabled = false; if (other) other.disabled = false; go.textContent = "Try again"; $("#job").innerHTML = `<p class="err">${esc(e.message)}</p>`; }
}

function follow(id) {
  clearInterval(poller);
  const tick = async () => {
    try {
      const {body} = await api("/api/job?client=" + encodeURIComponent(id));
      if (current !== id) return clearInterval(poller);
      renderJob(body);
      if (body.done) { clearInterval(poller); loadClients(); recheckQuietly(id); }   // the buttons and verdicts were drawn before the build: draw them again
    } catch (e) {}
  };
  tick(); poller = setInterval(tick, 1500);
}


function renderJob(j) {
  if (!j || !j.lines) return;
  // One build per client at a time, whichever kind: every button waits while it runs.
  const go = $(j.ti ? "#goti" : j.companion ? "#gocomp" : j.combined ? "#go2" : "#go");
  const others = ["#go", "#go2", "#goti", "#gocomp"].map($).filter(b => b && b !== go);
  if (go && !j.done) { go.disabled = true; for (const b of others) b.disabled = true; go.textContent = j.queued ? `Queued #${j.queued}` : "Building…"; }
  else if (go && j.code && !HOLD) { go.disabled = false; for (const b of others) b.disabled = false; go.textContent = (j.rebuild ? "Retry rebuild" : "Retry build") + (j.ti ? " (Transaction Intelligence)" : j.companion ? " (ARS Companion)" : j.combined ? " (combined)" : ""); }
  const steps = [], marks = [];
  for (const line of j.lines) {
    const m = line.match(/^\s*\[(ok|!!|built|STOP|\.\.)\]\s+(.*)$/);
    if (!m) continue;
    if (m[1] === "..") { const sm = m[2].match(/^(.*?)\s+\((\d+) min\)$/); steps.push({name: sm ? sm[1] : m[2], min: sm ? sm[2] : ""}); }
    else if (steps.length) marks.push({level: m[1], text: m[2]});
  }
  const mins = Math.floor(j.seconds / 60), secs = String(j.seconds % 60).padStart(2, "0");
  let html = `<div class="progress"><h3>${j.ti ? "Transaction Intelligence build" : j.companion ? "ARS Companion build" : j.combined ? "Combined build" : "Build"}${j.rebuild ? " (rebuild)" : ""} ·${j.queued ? "queued #" + j.queued : mins + ":" + secs}</h3><ul class="steps">`;
  if (j.queued) html += `<li><span class="dot"></span><span>Queued #${j.queued}. It starts on its own when ${j.queued > 1 ? "the builds ahead of it finish" : `the build for ${esc(j.after || "another client")} finishes`}. Keep CSM Sheila's black window open.</span></li>`;
  steps.forEach((st, i) => { const done = j.done || i < steps.length - 1;
    html += `<li><span class="dot ${done ? "done" : "now"}"></span><span>${esc(st.name)}</span><span class="t">${st.min !== "" ? esc(st.min) + " min" : ""}</span></li>`; });
  if (!steps.length && !j.done && !j.queued) html += `<li><span class="dot now"></span><span>Starting the build…</span></li>`;
  html += `</ul>`;
  // The launcher's own lines after the first step (the validation result, a warning, where the deck went).
  // They used to be visible only in a raw log box under the steps; now they are part of the result.
  const notes = marks.filter(x => x.level !== "STOP");
  const notesHtml = notes.length ? `<ul class="notes">${notes.map(x => `<li${x.level === "!!" ? ' class="warn"' : ""}>${esc(x.text)}</li>`).join("")}</ul>` : "";
  const stop = marks.find(x => x.level === "STOP") || (j.done && j.code ? {text: [...j.lines].reverse().find(l => l.trim()) || "The build stopped."} : null);
  if (j.done && !j.code && j.deck) {
    const name = j.deck.split(/[\\/]/).pop();
    html += `<div class="result good"><h3>Done. The ${j.ti ? "Transaction Intelligence decks are" : j.companion ? "ARS Companion deck is" : "deck is"} in Outputs.</h3><p class="mono">${esc(name)}</p>
      ${notesHtml}<p>Review it, save it as a PDF and email it as usual.</p>
      <p><button class="link" id="reveal">Show it in File Explorer</button></p></div>`;
  } else if (j.done) {
    html += `<div class="result bad"><h3>Not put in Outputs.</h3><p>${esc(stop ? stop.text : "The build stopped.")}</p>${notesHtml}
      <p>If it's not clear what to do, send Aaron the client number.</p></div>`;
  }
  html += `</div>`;
  // A Transaction Intelligence build shows its progress inside the Transaction Intelligence panel at the
  // bottom of the client page; every other build shows it above the "last build" line, as before.
  const box = (j.ti && $("#jobti")) || (j.companion && $("#jobcomp")) || $("#job");
  for (const o of [$("#job"), $("#jobti"), $("#jobcomp")]) if (o && o !== box) o.innerHTML = "";
  box.innerHTML = html;
  const rv = $("#reveal");
  if (rv) rv.addEventListener("click", async () => { try { await api("/api/reveal", {method: "POST", body: JSON.stringify({path: j.deck})}); } catch (e) { rv.insertAdjacentHTML("afterend", ` <span class="err">${esc(e.message)}</span>`); } });
}

// ------------------------------------------------------------------ Lift Matrix (Aaron, 2026-09-25)
// Every ARS client's current matrix (from its workbook) and the one calculated from its ODD. The numbers come
// from the server (build/ars_pipeline/lift_values.py); this page only shows them and passes the three rates.
let MODE = "decks", liftTimer = null, liftReq = 0;
const SEGS = ["NH", "NU", "1-5", "6-10", "11-15", "16-20", "21-25", "26 Plus"];
const money = v => v == null ? "–" : (v < 0 ? "−$" : "$") + Math.abs(Number(v)).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
const pct = (v, d = 1) => v == null ? "–" : (100 * v).toFixed(d) + "%";

function setMode(m, focus) {
  MODE = m; clearTimeout(liftTimer); clearInterval(poller); clearTimeout(statusTimer);
  document.querySelector(".app").classList.toggle("wide", m === "lift" || m === "issues" || m === "reported");
  for (const t of ["decks", "lift", "issues", "reported"]) $("#tab-" + t).setAttribute("aria-selected", m === t);
  current = null; renderList();
  // `focus` means "open this tab ON that client" — the links row hands the same client from
  // one tab to the next, so every tab has to honour it, not just Data Issues.
  if (m === "lift") focus ? liftSelect(focus) : liftOverview();
  else if (m === "reported") reportedView();
  else if (m === "issues") issuesView(focus);
  else if (focus) select(focus);
  else $("#main").innerHTML = `<div class="empty"><h2>Pick a client</h2><p>Choose a client on the left to see whether their deck can be built for ${esc(PERIOD || "this cycle")}.</p></div>`;
}

// ---- reporting an issue -------------------------------------------------------
// The report is QUEUED to the share. Sheila never talks to GitHub: it runs on each CSM's
// machine and the repo is private, so there are no credentials here by design. The hint
// says so, because an issue nobody can see yet should not look filed.
function openReport() {
  const d = $("#repdlg");
  $("#reptitle").value = ""; $("#repbody").value = "";
  $("#rephint").textContent = "Saved to the share now; it reaches GitHub on the next sync.";
  $("#repsend").disabled = false;
  d.showModal(); $("#reptitle").focus();
}

async function sendReport(ev) {
  ev.preventDefault();
  const title = $("#reptitle").value.trim();
  if (!title) return;
  $("#repsend").disabled = true;
  $("#rephint").textContent = "Saving…";
  try {
    await api("/api/report", {method: "POST", body: JSON.stringify({
      title, body: $("#repbody").value, client: current || "", page: MODE})});
    $("#repdlg").close();
    if (MODE === "reported") reportedView();
  } catch (e) {
    $("#rephint").textContent = "Couldn't save it: " + e.message;
    $("#repsend").disabled = false;
  }
}

async function reportedView() {
  current = null; renderList();
  $("#main").innerHTML = `<div class="head"><h2>Feedback</h2></div><p class="note">Reading the reports…</p>`;
  let body;
  try { ({body} = await api("/api/reports")); } catch (e) {
    $("#main").innerHTML = `<p class="err">Couldn't read the reports: ${esc(e.message)}</p>`; return;
  }
  if (MODE !== "reported") return;
  const rows = body.rows || [];
  const when = body.fetched_at ? body.fetched_at.replace("T", " ") : "never";
  const q = body.queued || 0;
  const cells = rows.map(r => {
    const st = r.state === "open" ? "rep-open" : r.state === "closed" ? "rep-closed" : "rep-queued";
    const num = r.number
      ? `<a href="${esc(r.url || "#")}" target="_blank" rel="noopener">#${r.number}</a>`
      : "—";
    return `<tr><td>${num}</td><td><span class="rep-state ${st}">${esc(r.state || "")}</span></td>
      <td><b>${esc(r.title || "")}</b>${r.body ? `<div class="small">${esc(r.body).slice(0, 200)}</div>` : ""}</td>
      <td>${esc(r.client_id || "")}</td><td class="small">${esc(r.reporter || "")}</td>
      <td class="small">${esc((r.created || "").replace("T", " ").slice(0, 16))}</td></tr>`;
  }).join("");
  $("#main").innerHTML = `<div class="head"><h2>Feedback</h2>
      <span class="sub">${rows.length} report${rows.length === 1 ? "" : "s"}${q ? ` · ${q} not yet filed` : ""}</span>
      <span class="sub" style="margin-left:auto">GitHub state as of ${esc(when)}</span></div>
    ${body.error ? `<p class="err">${esc(body.error)}</p>` : ""}
    <p class="note">Anyone can report an issue with the button at the top right. A report is
      saved to the share straight away and filed on GitHub by the next sync, so
      <b>queued</b> means it is recorded but not yet on GitHub.</p>
    ${rows.length ? `<table class="lm rep"><thead><tr><th>Issue</th><th>State</th><th>What</th>
      <th>Client</th><th>By</th><th>Reported</th></tr></thead><tbody>${cells}</tbody></table>`
      : `<p class="note">Nothing reported yet.</p>`}`;
}

async function liftOverview() {
  clearTimeout(liftTimer); current = null; renderList();
  let body;
  try { ({body} = await api("/api/lift/overview")); } catch (e) { $("#main").innerHTML = `<p class="err">Couldn't read the Lift Matrices: ${esc(e.message)}</p>`; return; }
  if (MODE !== "lift" || current) return;
  const d = body.doc, scanning = Object.values(body.scans || {}).filter(x => x === "queued" || x === "scanning").length;
  if (!d) { $("#main").innerHTML = `<div class="head"><h2>Lift Matrices</h2></div><p class="note">Reading every ARS client's workbook. This takes about a minute the first time.</p>`; liftTimer = setTimeout(liftOverview, 3000); return; }
  const csm = $("#csm").value;
  const rows = d.clients.filter(c => !csm || c.csm === csm).map(c => {
    const st = c.current ? (c.expired ? `<span class="chip stop">Expired</span>` : `<span class="chip out">Current</span>`) : `<span class="chip">${c.path === "SM" ? "SM model: no Lift Matrix" : c.workbook ? "No matrix in the workbook" : "No workbook"}</span>`;
    const cur = SEGS.map(s => `<td>${c.current ? money(c.current[s]) : ""}</td>`).join("");
    const calc = c.calculated ? `<tr class="calc pick" data-id="${esc(c.id)}"><td class="l"></td><td class="l">Calculated</td><td class="l"></td>${SEGS.map(s => `<td>${money(c.calculated[s])}</td>`).join("")}</tr>` : "";
    return `<tr class="pick${calc ? " grp" : ""}" data-id="${esc(c.id)}"><td class="l"><b>${esc(c.name)}</b> <span class="sub">${esc(c.id)}</span></td><td class="l">${c.current ? "Workbook" : ""}</td>
      <td class="l">${st}${c.window ? `<br><span class="sub" style="font-size:12px">${esc(c.window)}</span>` : ""}</td>${cur}</tr>${calc}`;
  }).join("");
  const age = body.refreshing ? "Updating…" : `As of ${ago(body.age_seconds)}`;
  $("#main").innerHTML = `<div class="head"><h2>Lift Matrices</h2><span class="sub">DDA value per account per month, by swipe segment · ${esc(age)}</span>
      <span class="sub" style="margin-left:auto"><button class="link" id="lmall">Calculate every MM client from its ODD</button></span></div>
    <p class="note" style="margin-top:0">Workbook rows are the matrix each client's newest ARS workbook carries. Calculated rows use the client's own rates and appear once its ODD has been read${scanning ? ` (${scanning} being read now)` : ""}. Pick a client to compare the full matrices, change the values and export the file for Bradford.</p>
    <div class="lmwrap"><table class="lm"><thead><tr><th>Client</th><th></th><th>Matrix</th>${SEGS.map(s => `<th>${esc(s)}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div>`;
  $("#main").querySelectorAll("tr.pick").forEach(tr => tr.addEventListener("click", () => liftSelect(tr.dataset.id)));
  $("#lmall").addEventListener("click", async () => {
    try { const {body: b} = await api("/api/lift/scan-all", {method: "POST", body: "{}"}); $("#lmall").textContent = `${b.queued} queued. The table fills in as each one finishes.`; }
    catch (e) { $("#lmall").insertAdjacentHTML("afterend", ` <span class="err">${esc(e.message)}</span>`); }
  });
  liftTimer = setTimeout(liftOverview, body.refreshing || scanning ? 5000 : 60000);
}

function liftQuery(id) {
  const q = new URLSearchParams({client: id});
  const bp = $("#lm-ic"), fee = $("#lm-fee"), col = $("#lm-col");
  if (bp && bp.value !== "") q.set("ic_rate", String(Number(bp.value) / 10000));
  if (fee && fee.value !== "") q.set("nsf_fee", fee.value);
  if (col && col.value !== "") q.set("collection", String(Number(col.value) / 100));
  const cap = $("#lm-cap");
  if (cap) q.set("winsor", cap.value);
  return q.toString();
}

// keep = the rates were edited: re-read the figures at the typed rates and redraw below the fields only,
// so the field being typed in keeps its focus.
async function liftSelect(id, keep) {
  clearTimeout(liftTimer); current = id; renderList();
  const c = CLIENTS.find(x => x.id === id) || {id};
  if (!keep) $("#main").innerHTML = `<div class="head"><h2>${esc(c.name || id)}</h2><span class="sub">${esc(id)}</span></div><p class="note">Reading the workbook and the ODD…</p>`;
  const n = ++liftReq;
  let d;
  try { ({body: d} = await api("/api/lift/client?" + (keep ? liftQuery(id) : "client=" + encodeURIComponent(id)))); }
  catch (e) {
    if (n !== liftReq) return;
    const box = $("#lm-out");
    if (box) box.innerHTML = `<p class="err">${esc(e.message)}</p>`; else $("#main").insertAdjacentHTML("beforeend", `<p class="err">${esc(e.message)}</p>`);
    return;
  }
  if (n !== liftReq || current !== id || MODE !== "lift") return;
  if (keep && $("#lm-out") && d.scan_state === "ready") {
    $("#lm-out").innerHTML = liftBody(d); $("#lm-out").classList.remove("stale"); $("#lmstale").textContent = "";
    wireSave(d); return;
  }
  liftRender(d);
}

function liftRender(d) {
  const head = `<div class="head"><h2>${esc(d.name || d.client)}</h2><span class="sub">${esc(d.client)} · ${esc(d.csm || "")} · ${esc(d.period || "")}</span>
    <span class="sub" style="margin-left:auto"><button class="link" id="lmback">All clients</button></span></div>`;
  const cur = d.current ? `Current matrix: ${esc(d.current.window)} (${d.current.data_past_end ? "expired" : "data " + esc(d.current.data_date)}) in ${esc(d.workbook)}.`
    : d.workbook ? `${esc(d.workbook)} carries no Lift Matrix (SM).` : d.workbook_error ? `The workbook could not be read: ${esc(d.workbook_error)}` : "No ARS workbook in Inputs.";
  let html = head + `<p class="note clientlinks" id="clientlinks">&nbsp;</p><p class="note" style="margin-top:0">${cur}</p>`;
  if (d.scan_state === "sm") html += `<p class="note">${esc(d.name || d.client)} is on the SM model, which does not use a Lift Matrix.</p>`;
  else if (d.scan_state === "no-odd") html += `<p class="err">No ODD extract for ${esc(d.client)} in Inputs, so nothing can be calculated.</p>`;
  else if (d.scan_state !== "ready") {
    html += d.scan_state === "error" ? `<p class="err">Reading the ODD stopped: ${esc(d.scan_error)}</p><button class="primary" id="lmre">Try again</button>`
      : `<p class="note"><span class="dot now" style="display:inline-block;vertical-align:middle"></span> Reading the ODD (${esc(d.scan_state)}). This takes up to a minute.</p>`;
    if (d.scan_state !== "error") liftTimer = setTimeout(() => liftSelect(d.client), 3000);
  } else {
    const df = d.defaults, r = d.rates;
    html += `<div class="rates">
      <label>Interchange rate<span class="fld"><input id="lm-ic" type="number" step="0.5" min="0" max="500" value="${+(r.ic_rate * 10000).toFixed(2)}"><span>BP</span></span><span class="src">${esc(df.ic_source)}</span></label>
      <label>NSF/OD fee<span class="fld"><span>$</span><input id="lm-fee" type="number" step="0.01" min="0" max="200" value="${r.nsf_fee ?? ""}" placeholder="Enter the fee"></span><span class="src">${esc(df.nsf_source)}</span></label>
      <label>OD collection rate<span class="fld"><input id="lm-col" type="number" step="1" min="0" max="100" value="${+(r.collection * 100).toFixed(1)}"><span>%</span></span><span class="src">${esc(df.collection_source)}</span></label>
      <label>Outlier cap<span class="fld"><select id="lm-cap">${d.winsor_options.map(o => `<option value="${o.value}"${o.value === r.winsor ? " selected" : ""}>${esc(o.label)}</option>`).join("")}</select></span><span class="src">${esc(df.winsor_source)}</span></label>
    </div><p class="recalc"><button class="primary" id="lmcalc">Recalculate</button> <span id="lmstale" class="note"></span> <button class="link" id="lmreset">Reset to the defaults</button></p><div id="lm-out">${liftBody(d)}</div>`;
  }
  $("#main").innerHTML = html;
  clientLinks(d.client, "lift");
  $("#lmback").addEventListener("click", liftOverview);
  const re = $("#lmre"); if (re) re.addEventListener("click", async () => { await api("/api/lift/rescan", {method: "POST", body: JSON.stringify({client: d.client})}); liftSelect(d.client); });
  if (d.scan_state !== "ready") return;
  // Aaron, 2026-09-25: "we need an option to recalculate when the variables are changed". A change marks the
  // figures below out of date and holds Export until Recalculate (or Enter) applies it, so a matrix is never
  // exported at values other than the ones on screen.
  const stale = () => {
    $("#lm-out").classList.add("stale");
    $("#lmstale").textContent = "The figures below are for the previous values. Recalculate to update them.";
    for (const b of ["#lmok", "#lmdl"]) { const x = $(b); if (x) { x.disabled = true; x.title = "Recalculate first"; } }
  };
  const recalc = () => liftSelect(d.client, true);
  for (const el of ["#lm-ic", "#lm-fee", "#lm-col", "#lm-cap"]) {
    $(el).addEventListener(el === "#lm-cap" ? "change" : "input", stale);
    $(el).addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); recalc(); } });
  }
  $("#lmcalc").addEventListener("click", recalc);
  $("#lmreset").addEventListener("click", () => liftSelect(d.client));
  wireSave(d);
}

// Current (the workbook's) and new (calculated) side by side (Aaron, 2026-09-25): each segment's DDA value in
// both, the change, and the step from the segment before it; then both lift grids.
function liftBody(d) {
  const segs = d.segments, calc = d.calculated, cur = d.current || {}, curSeg = cur.segments || {}, curGrid = cur.grid || {};
  const bySeg = calc ? Object.fromEntries(calc.segments.map(x => [x.segment, x])) : {};
  const newV = s => { const c = bySeg[s]; return c ? c.dda : null; };
  const curV = s => curSeg[s] ? curSeg[s].dda : null;
  const signed = v => v == null ? "" : (v > 0 ? "+" : "") + money(v);
  const cls = v => v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : "";
  const step = (f, i) => i < 2 || f(SEGS[i]) == null || f(SEGS[i - 1]) == null ? null : f(SEGS[i]) - f(SEGS[i - 1]);
  const rows = SEGS.map((s, i) => {
    const g = segs[s], nv = newV(s), cv = curV(s), dlt = nv != null && cv != null ? nv - cv : null;
    const cd = curSeg[s] && curSeg[s].dist != null ? pct(curSeg[s].dist) : "–";
    return `<tr><td class="l"><b>${esc(s)}</b></td><td>${g ? g.n.toLocaleString() : ""}</td>
      <td>${cd}</td><td>${pct(g.dist)}</td>
      <td>${money(cv)}</td><td><b>${money(nv)}</b></td><td class="${cls(dlt)}">${signed(dlt)}</td>
      <td>${signed(step(curV, i))}</td><td>${signed(step(newV, i))}</td></tr>`;
  }).join("");
  const seg = `<div class="panel"><h3>Revenue segmentation: current and new</h3><div class="lmwrap"><table class="lm">
    <thead><tr><th rowspan="2">Segment</th><th rowspan="2">Accounts</th><th colspan="2">Distribution</th><th colspan="3">DDA value</th><th colspan="2">Step from the segment before</th></tr>
    <tr><th>Current</th><th>New</th><th>Current</th><th>New</th><th>Change</th><th>Current</th><th>New</th></tr></thead><tbody>${rows}</tbody></table></div>
    <p class="note">Current is the matrix in ${esc(d.workbook || "the workbook")}${cur.window ? " (" + esc(cur.window) + ")" : ""}. A step is a segment's DDA value less the one above it.</p></div>`;
  const detail = `<details class="log"><summary>How each new value is made up</summary><div class="lmwrap"><table class="lm"><thead><tr><th>Segment</th><th>Avg spend / mo</th><th>NSF/OD items / mo</th><th>Interchange</th><th>NSF/OD</th><th>DDA value</th></tr></thead><tbody>${
    SEGS.map(s => { const g = segs[s], c = bySeg[s]; return `<tr><td class="l"><b>${esc(s)}</b></td><td>${money(g.spend)}</td><td>${g.items.toFixed(3)}</td><td>${c ? money(c.interchange) : ""}</td><td>${c ? money(c.nsf) : ""}</td><td>${c ? money(c.dda) : ""}</td></tr>`; }).join("")
  }</tbody></table></div></details>`;
  if (!calc) return seg + `<p class="err">Enter the client's NSF/OD fee to calculate the new matrix.</p>`;
  const cols = SEGS.slice(2), bases = SEGS.slice(1, 6);
  const grid = (title, get, compare) => `<div class="gridbox"><h4>${title}</h4><table class="lm"><thead><tr><th>Baseline</th>${cols.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${
    bases.map(b => `<tr><td class="l"><b>${esc(b)}</b></td>${cols.map(c => {
      const v = get(b, c); if (v == null) return "<td></td>";
      const was = compare ? compare(b, c) : null;
      return `<td class="${was == null ? "" : cls(Math.round((v - was) * 100))}"${was == null ? "" : ` title="Current ${money(was)}"`}>${money(v)}</td>`;
    }).join("")}</tr>`).join("")}</tbody></table></div>`;
  const curGet = (b, c) => (curGrid[b] || {})[c] ?? null, newGet = (b, c) => calc.matrix[b][c] ?? null;
  const grids = `<div class="panel"><h3>Monthly incremental revenue lift</h3><div class="grids">
    ${grid("Current" + (cur.window ? " · " + esc(cur.window) : ""), curGet)}${grid("New", newGet, Object.keys(curGrid).length ? curGet : null)}</div>
    <p class="note">New cells are green where they are above the current matrix and red where they are below. Hover a cell for the current value.</p></div>`;
  const sc = d.scan, fee = sc.fee;
  const feeLine = fee ? (fee.values.length ? `NSF/OD fee in the ODD (${esc(fee.columns.join(", "))}): ${fee.values.map(x => `${money(x.fee)} on ${pct(x.share, 0)} of items`).join(", ")}. The most common is the default.` : `The ODD has ${esc(fee.columns.join(", "))} but no fee on any NSF/OD item, so the fee comes from the workbook.`)
    : `This ODD carries no NSF/OD fee column (Fees1), so NSF/OD is valued as the monthly OD item count × the fee.`;
  const method = `<div class="panel"><h3>How it was calculated</h3><ul class="method">
    <li>${sc.population.toLocaleString()} ARS-eligible accounts, consumer and business: ${sc.card_holders.toLocaleString()} with a debit card in the seven swipe segments (${(sc.counts.consumer || 0).toLocaleString()} consumer, ${(sc.counts.business || 0).toLocaleString()} business${sc.counts["business? blank"] ? ", " + sc.counts["business? blank"].toLocaleString() + " with Business? blank" : ""}) and ${(segs.NH ? segs.NH.n : 0).toLocaleString()} without one in NH. The distribution is of all of them.</li>
    <li>Swipes, spend and NSF/OD items averaged over ${esc(sc.window_label)} (${sc.window.length} complete months), from ${esc(sc.source_file)}.${sc.excluded_months ? " " + esc(sc.excluded_months) : ""}</li>
    <li>Segment: average swipes per month, rounded down into its band.</li>
    <li>Outliers: ${d.rates.winsor >= 1 ? "no cap on spend or NSF/OD items" : `each account's spend and NSF/OD items are capped at the ${+(d.rates.winsor * 100).toFixed(1)}th percentile of its segment`}. 26 Plus is valued on its accounts averaging 26 to ${25 + sc.top_band} swipes; its distribution counts all of them.</li>
    <li>DDA value = interchange rate × spend + NSF/OD fee × items × collection rate. Lift = DDA of the new segment − DDA of the baseline.</li>
    <li>NH: ${bySeg.NH && bySeg.NH.from_nu ? "this client has no eligible account without a debit card, so NH carries NU's value" : `the ${(segs.NH ? segs.NH.n : 0).toLocaleString()} eligible accounts with no debit card, valued on their own spend and NSF/OD items`}.</li>
    <li>${feeLine}</li></ul></div>`;
  const done = d.exported && JSON.stringify(d.exported.rates) === JSON.stringify(d.rates);
  const exp = done
    ? `<div class="verdict ready"><p><b>Exported</b> ${esc(d.exported.at)}${d.exported.by ? " by " + esc(d.exported.by) : ""} at these values as <span class="mono">${esc(d.file_name)}</span>. Email it to Bradford to have it loaded.</p><span class="btns"><button class="primary" id="lmdl">Download again</button></span></div>`
    : `<div class="verdict ask"><p><b>Review the new matrix against the current one, then export it.</b> Export this matrix downloads <span class="mono">${esc(d.file_name)}</span>, the Excel file for Bradford.${d.exported ? " The last export was at different values." : ""}</p><span class="btns"><button class="primary" id="lmok">Export this matrix</button></span></div>`;
  return seg + detail + grids + exp + `<div id="lmmsg"></div>` + method;
}

function liftRatesBody(d) {
  const q = new URLSearchParams(liftQuery(d.client)), body = {client: d.client};
  for (const k of ["ic_rate", "nsf_fee", "collection", "winsor"]) if (q.has(k)) body[k] = q.get(k);
  return body;
}

async function liftDownload(d) {
  const r = await fetch("/api/lift/download", {method: "POST", headers: {"X-Token": TOKEN, "Content-Type": "application/json"}, body: JSON.stringify(liftRatesBody(d))});
  if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.error || "HTTP " + r.status); }
  const url = URL.createObjectURL(await r.blob()), a = document.createElement("a");
  a.href = url; a.download = d.file_name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

// Export this matrix: record what is exported, then download it — one click (Aaron, 2026-09-25).
function wireSave(d) {
  const ok = $("#lmok"), dl = $("#lmdl");
  if (ok) ok.addEventListener("click", async () => {
    ok.disabled = true; ok.textContent = "Exporting…";
    try {
      const {status, body: r} = await api("/api/lift/export", {method: "POST", body: JSON.stringify(liftRatesBody(d))});
      if (status !== 200) throw new Error(r.error || "not exported");
      await liftDownload(d);
      await liftSelect(d.client, true);
      const m = $("#lmmsg"); if (m) m.innerHTML = `<p class="note">Downloaded <span class="mono">${esc(d.file_name)}</span> to your Downloads folder.</p>`;
    } catch (e) { ok.disabled = false; ok.textContent = "Try again"; $("#lmmsg").innerHTML = `<p class="err">${esc(e.message)}</p>`; }
  });
  if (dl) dl.addEventListener("click", async () => {
    dl.disabled = true;
    try {
      await liftDownload(d);
      $("#lmmsg").innerHTML = `<p class="note">Downloaded <span class="mono">${esc(d.file_name)}</span> to your Downloads folder.</p>`;
    } catch (e) { $("#lmmsg").innerHTML = `<p class="err">${esc(e.message)}</p>`; }
    dl.disabled = false;
  });
}

$("#tab-decks").addEventListener("click", () => setMode("decks"));
$("#period").addEventListener("click", openCycles);
$("#tab-lift").addEventListener("click", () => setMode("lift"));
$("#tab-issues").addEventListener("click", () => setMode("issues"));
$("#tab-reported").addEventListener("click", () => setMode("reported"));
$("#reportbtn").addEventListener("click", openReport);
$("#repform").addEventListener("submit", sendReport);
$("#repcancel").addEventListener("click", () => $("#repdlg").close());
// ------------------------------------------------------------------ Data Issues (Aaron, 2026-09-25)
// Each client's data issues from the issue pages and the morning dashboard's checks, with a link to its code sheet.
let ISSUES = null, ISSUES_AT = 0, SEV = "";
const SEV_TAG = {blocker: ["stop", "blocker"], decision: ["ask", "decision"], gap: ["warn", "gap"], warning: ["step", "warning"]};

async function loadIssues(fresh) {
  if (ISSUES && !fresh && Date.now() - ISSUES_AT < 60000) return ISSUES;
  const {body} = await api("/api/issues"); ISSUES = body; ISSUES_AT = Date.now(); return ISSUES;
}

function codeSheetLinks(cid, name) {
  return name ? `<button class="link" data-cs="${esc(cid)}" title="${esc(name)}">Open code sheet</button> · <button class="link" data-csr="${esc(cid)}">Show it in File Explorer</button>`
              : `<span class="sub">No code sheet in Inputs/Code Sheets</span>`;
}

// The one links row under a client's name, on every tab (Aaron, 2026-10-02: "I like this row
// of links on the Lift Matrix tab. Make that consistent across the tabs."). It always reads
// the same way — the code sheet first, then where else this client can be looked at — and the
// tab you are already on is left out rather than linking to itself.
function linksRowHTML(cid, codeSheet, issueCount, here) {
  const parts = [codeSheetLinks(cid, codeSheet)];
  if (here !== "decks") parts.push(`<button class="link" data-goto="decks" data-client="${esc(cid)}">Deck checks</button>`);
  if (here !== "lift") parts.push(`<button class="link" data-goto="lift" data-client="${esc(cid)}">Lift Matrix</button>`);
  if (here !== "issues") {
    const n = issueCount || 0;
    parts.push(`<button class="link" data-goto="issues" data-client="${esc(cid)}">${n ? n + " data issue" + (n === 1 ? "" : "s") : "No data issues"}</button>`);
  }
  return parts.join(" · ");
}

// The links row under a client's name on the Decks and Lift Matrix pages.
async function clientLinks(cid, here) {
  const box = $("#clientlinks"); if (!box) return;
  try {
    const d = await loadIssues(), e = (d.clients || []).find(x => x.id === cid);
    if ($("#clientlinks") !== box) return;
    box.innerHTML = linksRowHTML(cid, e && e.code_sheet, e ? e.count : 0, here || MODE);
  } catch (err) { box.innerHTML = `<span class="err">Couldn't read the data issues: ${esc(err.message)}</span>`; }
}

// Marking an item complete (Aaron, 2026-09-28): it stays complete until a newer workbook lands for the client, then
// comes back with the date it was marked and the workbook that arrived since.
function issueRow(e, item, tag, body) {
  if (SEV === "done" ? !item.done : !!item.done) return "";
  const btn = item.done
    ? `<button class="link" data-mark="${esc(item.key)}" data-client="${esc(e.id)}" data-done="0">Undo</button>`
    : `<button class="chipbtn" data-mark="${esc(item.key)}" data-client="${esc(e.id)}" data-done="1">Mark complete</button>`;
  const state = item.done
    ? `<br><span class="sub">Marked complete ${esc(item.done.at)}${item.done.by ? " by " + esc(item.done.by) : ""}. It stays complete until a new workbook arrives for this client.</span>`
    : item.reopened
      ? `<br><span class="sub" style="color:var(--warn)">Marked complete ${esc(item.reopened.at)}${item.reopened.by ? " by " + esc(item.reopened.by) : ""}; a new workbook has arrived since${item.reopened.new && item.reopened.new.length ? " (" + esc(item.reopened.new.join(", ")) + ")" : ""}. Check it again.</span>`
      : "";
  return `<li class="irow${item.done ? " idone" : ""}">${tag}<span>${body}${state}</span><span class="imark">${btn}</span></li>`;
}

function issueCard(e) {
  const rows = [];
  for (const i of e.issues) {
    if (SEV && SEV !== "done" && SEV !== i.severity) continue;
    const [cls, lab] = SEV_TAG[i.severity] || ["step", i.severity];
    rows.push(issueRow(e, i, `<span class="tag ${cls}">${esc(lab)}</span>`,
      `<b>${esc(i.program || "")}</b> ${esc(i.issue)}${i.fix ? `<br><span class="sub">Fix: ${esc(i.fix)}</span>` : ""}`));
  }
  if (!SEV || SEV === "codes" || SEV === "done") {
    if (e.lift_matrix) rows.push(issueRow(e, e.lift_matrix, `<span class="tag stop">lift</span>`,
      `<b>ARS</b> Lift Matrix flagged "${esc(e.lift_matrix.flag)}" in ${esc(e.lift_matrix.workbook)}<br><span class="sub">Fix: create a new Lift Matrix (the Lift Matrix tab), then send it to Bradford</span>`));
    for (const c of e.codes) {
      const vals = (c.values || []).map(v => `${esc(v.value)}${v.desc ? " (" + esc(v.desc) + ")" : ""}: ${(v.accounts || 0).toLocaleString()} account${v.accounts === 1 ? "" : "s"}${v.open != null ? ", " + v.open.toLocaleString() + " open" : ""}`).join("; ");
      rows.push(issueRow(e, c, `<span class="tag warn">codes</span>`,
        `<b>ARS</b> ${esc(c.label)}${c.eligibility ? " (decides eligibility)" : ""}: ${vals}${c.no_table ? " <span class=\"sub\">(no code table for this kind)</span>" : ""}<br><span class="sub">Fix: correct the client's code sheet</span>`));
    }
  }
  if (!rows.some(Boolean)) return "";
  const unchecked = !SEV && e.unchecked.length ? `<p class="sub" style="margin:6px 0 0">Not checked: ${esc(e.unchecked.join("; "))}</p>` : "";
  return `<section class="icard" id="issue-${esc(e.id)}"><div class="ihead"><b>${esc(e.name || e.id)}</b> <span class="sub">${esc(e.id)} · ${esc(e.csm)}</span>
    <span class="sub clientlinks" style="margin-left:auto">${linksRowHTML(e.id, e.code_sheet, e.count, "issues")}</span></div><ul class="checks">${rows.join("")}</ul>${unchecked}</section>`;
}

async function issuesView(focus) {
  current = focus || null; renderList();
  if (!ISSUES) $("#main").innerHTML = `<div class="head"><h2>Data Issues</h2></div><p class="note">Reading the data issues…</p>`;
  let d;
  try { d = await loadIssues(); } catch (e) { $("#main").innerHTML = `<p class="err">Couldn't read the data issues: ${esc(e.message)}</p>`; return; }
  if (MODE !== "issues") return;
  const csm = $("#csm").value, q = $("#q").value.trim().toLowerCase();
  const shown = d.clients.filter(e => (focus ? e.id === focus : (!csm || e.csm === csm) && (!q || e.id.includes(q) || (e.name || "").toLowerCase().includes(q))));
  const cards = shown.map(issueCard).filter(Boolean);
  const open = x => x && !x.done;
  const count = k => shown.reduce((n, e) => n + (k === "done" ? (e.done_count || 0)
    : k === "codes" ? e.codes.filter(open).length + (open(e.lift_matrix) ? 1 : 0)
    : e.issues.filter(i => open(i) && i.severity === k).length), 0);
  const chip = (k, lab) => `<button class="chipbtn" data-sev="${k}" aria-pressed="${SEV === k}">${lab} ${k ? count(k) : ""}</button>`;
  const src = d.sources || {};
  $("#main").innerHTML = `<div class="head"><h2>Data Issues</h2><span class="sub">${focus ? esc((shown[0] || {}).name || focus) + " · " : ""}${shown.length} client${shown.length === 1 ? "" : "s"}</span>
      <span class="sub" style="margin-left:auto">${focus ? `<button class="link" id="iall">All clients</button>` : ""}</span></div>
    <div class="chips">${chip("", "All")}${chip("blocker", "Blockers")}${chip("decision", "Decisions")}${chip("gap", "Gaps")}${chip("warning", "Warnings")}${chip("codes", "Codes and Lift Matrix")}${chip("done", "Completed")}</div>
    <p class="note" style="margin-top:6px">Issue list as of ${esc(src.issue_pages || "never")} (the ODD and Workbook Issues and CSM Data Gaps pages). Code and Lift Matrix checks as of ${esc(src.dashboard || "never")} (the morning dashboard refresh).</p>
    ${cards.join("") || `<p class="note">${SEV === "done" ? "Nothing marked complete" : "No open data issues" + (SEV ? " of this kind" : "")} for ${focus ? "this client" : "these clients"}.</p>`}`;
  $("#main").querySelectorAll("[data-sev]").forEach(b => b.addEventListener("click", () => { SEV = b.dataset.sev; issuesView(focus); }));
  const ia = $("#iall"); if (ia) ia.addEventListener("click", () => issuesView());
  $("#main").querySelectorAll("[data-mark]").forEach(b => b.addEventListener("click", async () => {
    b.disabled = true; b.textContent = "Saving…";      // the mark is written to the share, a few seconds
    try {
      await api("/api/issues/mark", {method: "POST", body: JSON.stringify({client: b.dataset.client, key: b.dataset.mark, done: b.dataset.done === "1"})});
      await loadIssues(true); issuesView(focus);
    } catch (err) { b.disabled = false; b.insertAdjacentHTML("afterend", ` <span class="err">${esc(err.message)}</span>`); }
  }));
}

// Code sheet and issue links work wherever they are drawn.
document.addEventListener("click", async ev => {
  const go = ev.target.closest("[data-goto]");
  if (go) return setMode(go.dataset.goto, go.dataset.client);
  const cs = ev.target.closest("[data-cs],[data-csr]");
  if (cs) {
    const cid = cs.dataset.cs || cs.dataset.csr;
    try { await api("/api/code-sheet", {method: "POST", body: JSON.stringify({client: cid, action: cs.dataset.csr ? "reveal" : "open"})}); }
    catch (e) { cs.insertAdjacentHTML("afterend", ` <span class="err">${esc(e.message)}</span>`); }
  }
});


$("#list").addEventListener("click", e => { const b = e.target.closest(".client"); if (b) (MODE === "lift" ? liftSelect : MODE === "issues" ? issuesView : select)(b.dataset.id); });
$("#csm").addEventListener("change", () => { $("#csm").dataset.touched = "1"; store("ars-builder-csm", $("#csm").value); renderList(); if (MODE === "lift" && !current) liftOverview(); if (MODE === "issues" && !current) issuesView(); });
$("#q").addEventListener("input", () => { renderList(); if (MODE === "issues" && !current) issuesView(); });
(function showSaved() {
  try { const saved = JSON.parse(sessionStorage.getItem(LIST_KEY) || "null"); if (saved && saved.clients) applyClients(saved, true); } catch (e) {}
})();
loadClients();
pollQueue(); setInterval(pollQueue, 3000);
document.addEventListener("click", e => { const n = $("#news"); if (n && n.open && !n.contains(e.target)) n.open = false; });
// The last five change-log entries in the header (Aaron, 2026-09-16).
(async function loadNews() {
  try {
    const {body} = await api("/api/changelog");
    const items = (body.entries || []).map(e => `<li><a href="/changelog#${esc(e.anchor)}" target="_blank" rel="noopener"><span class="d">${esc(e.date)}</span><br><b>${esc(e.title)}</b><span class="s">${esc(e.summary)}</span></a></li>`);
    $("#newslist").innerHTML = items.join("") || `<li class="small">No entries yet.</li>`;
  } catch (e) { $("#newslist").innerHTML = `<li class="small">The change log could not be read.</li>`; }
})();
</script>
</body>
</html>
"""

PAGE = slide_review_ui.install(PAGE)
PAGE = ils_ui.install(PAGE)


if __name__ == "__main__":
    sys.exit(main())
