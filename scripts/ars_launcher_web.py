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
import ils_ui                 # noqa: E402
import live_review_ui         # noqa: E402
import sheila_hub              # noqa: E402

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
    # The Live Review block (Aaron, 2026-11-06; prototype): the page a CSM presents a review from, read from the
    # packs a deck build left. File presence only, and like TI and the Companion a failure here never costs the
    # RPE status.
    live = None
    try:
        live = live_review_ui.status(cid, period, entry[3] if entry else ["ARS"])
    except (Exception, SystemExit) as e:              # noqa: BLE001 — shown, never raised
        live = {"state": "stop", "programs": [],
                "checks": [{"level": L.STOP, "text": f"The Live Review checks could not run ({type(e).__name__}: {e})"}]}
    return {"client": cid, "name": (entry[1] if entry else None) or row.get("client_name"),
            "csm": row.get("csm") or (cp_row or {}).get("csm"), "period": period,
            "state": state, "checks": [{"level": l, "text": m} for l, m in checks], "last": last,
            "builds": builds_on_offer(entry[3] if entry else ["ARS"], avail, ars_only, has_ars),
            "ti": ti, "companion": companion, "live": live}


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
            "<title>CSM Sheila · Change log</title>" + sheila_hub.FAVICON + "<style>" + CHANGELOG_CSS + "</style></head><body>"
            "<header><a class=\"home\" href=\"/\">" + sheila_hub.MARK_SVG + "<b>CSM Sheila</b></a><span>Change log</span>"
            "<a class=\"back\" href=\"/\">Back to Sheila</a></header><main>"
            + "\n".join(body) + "</main></body></html>")


# The change log page wears the Hub's colours in both themes, so it reads as part of Sheila (Aaron, 2026-11-02).
CHANGELOG_CSS = (
    ":root{--ground:#EDF1F7;--sheet:#FFFFFF;--fill:#E4EAF3;--line:#C6D1E0;--ink:#0B132B;--muted:#4A5C75;--link:#15627E;--mf:#1C2541;--mb:#15627E}"
    "@media (prefers-color-scheme:dark){:root{--ground:#0B132B;--sheet:#141D38;--fill:#28344F;--line:#3A506B;--ink:#EEF3FA;--muted:#A3B3C9;--link:#5BC0DE;--mf:#EEF3FA;--mb:#5FB3C9}}"
    "*{box-sizing:border-box}body{margin:0;background:var(--ground);color:var(--ink);font:15.5px/1.55 'Segoe UI Variable Text','Segoe UI',Calibri,sans-serif}"
    "header{display:flex;align-items:center;gap:14px;max-width:900px;margin:0 auto;padding:16px 20px 6px}"
    "header .home{display:flex;align-items:center;gap:10px;color:var(--ink);text-decoration:none;font-size:17px}"
    "header .home svg{width:36px;height:36px}header .mf{fill:var(--mf)}header .mb{fill:var(--mb)}"
    "header span{color:var(--muted)}header .back{margin-left:auto;color:var(--link)}"
    "main{max-width:900px;margin:0 auto;padding:10px 20px 60px}"
    "h1{font-size:24px}h2{font-size:20px;margin-top:34px;padding-bottom:4px;border-bottom:1px solid var(--line)}"
    "h3{font-size:17px;margin:28px 0 6px}h3:target{outline:2px solid var(--link);outline-offset:4px;border-radius:6px}"
    "p.sum{font-weight:600;background:var(--fill);padding:8px 12px;border-radius:12px}"
    "code{background:var(--fill);padding:1px 5px;border-radius:5px;font-size:.9em}a{color:var(--link)}"
    "p.rel{margin:14px 0 0;padding:8px 12px;border-radius:12px;background:var(--sheet);border:1px solid var(--line);color:var(--muted);font-size:14px}"
    "@media (max-width:600px){header{flex-wrap:wrap}}"
)


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
# Build Artifacts/slide_votes/) and the counting are in slide_votes.py; the tab's page is sheila_hub_votes.py.
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
            "stars": len([v for v in cur if v.get("star")]), "voters": len({v["voter"] for v in cur if SV.has_state(v)}),
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
            return self._send(200, sheila_hub.page(TOKEN, app_version(), sheila_hub.who_am_i()).encode("utf-8"), "text/html; charset=utf-8")
        if u.path == "/hub":                  # the preview's old address
            self.send_response(302)
            self.send_header("Location", "/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
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
            if u.path.startswith("/api/live/"):
                return live_review_ui.get(self, u.path, {k: v[0] for k, v in q.items()})
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
        if path.startswith("/api/live/"):
            return live_review_ui.post(self, path, body)
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


def tidy(say=None):
    """Sheila cleans up after herself (Aaron, 2026-11-03: "my harddrive is nearly full. make sure sheila cleans up after
    herself"): build scratch a crashed build left in the temp folder, and the Transaction Intelligence cache beyond its
    size and age limits (build/local_cache.py). Returns the bytes freed; never raises, a locked file is skipped."""
    say = say or (lambda m: print(" " + m, flush=True))
    freed = 0
    try:
        _swept, f = R.sweep_temp()
        freed += f or 0
    except Exception as e:
        say(f"could not clear old build scratch: {e}")
    try:
        import local_cache
        r = local_cache.trim_ti_cache(log=say)
        freed += r["freed"]
    except Exception as e:
        say(f"could not trim the Transaction Intelligence cache: {e}")
    if freed:
        say(f"cleaned up {freed / 1e9:.1f} GB of old local files")
    return freed


def main(argv=None):
    ap = argparse.ArgumentParser(description="CSM Sheila, the Smart Helper for Executive Insights, Layouts & Analytics: the browser front end for ars_launcher.")
    ap.add_argument("--port", type=int, default=0, help="default: any free port")
    ap.add_argument("--no-open", action="store_true", help="don't open a browser")
    ap.add_argument("--tidy", action="store_true", help="clean up old local build scratch and cache, then exit")
    a = ap.parse_args(argv)
    if a.tidy:
        tidy()
        return 0
    threading.Thread(target=tidy, daemon=True).start()          # while she starts, not before the page
    srv = make_server(a.port)
    install_share_caches()
    _renew["on"] = True
    sheila_hub.who_am_i()           # once, here, so the first page does not wait on the share
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


if __name__ == "__main__":
    sys.exit(main())
