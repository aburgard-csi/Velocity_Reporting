#!/usr/bin/env python3
"""
perf_overview.py — the Client overview figures on the performance page, from each client's ODD.

Aaron, 2026-09-14: for every client, open checking accounts (total, business, personal), the
3-month average of personal swipes per month, the 3-month average of NSF/OD items per month,
and personal openings and closings over 12 months.

Every definition is the deck's, read through `build/ars_pipeline/odd_rows`:

  open                 status_class(Stat Desc, Stat Code) != "closed" — the Product Mix slide's
                       "Excl. Closed" book, so these totals match that slide
  business / personal  Business? == "Yes" / "No". A blank is neither; it counts in the total only
  swipes               Sig # + PIN # count on PERSONAL accounts over the extract's last three
                       months, divided by three
  NSF/OD               the MTD item count (items, never dollars) on EVERY account over the same
                       three months, divided by three
  openings / closings  personal accounts whose Date Opened / Date Closed falls in the twelve months
                       ending with the snapshot month — metrics_gen's openings-vs-closures rule,
                       over 12 months instead of 24

**The snapshot month is read from the extract, never assumed.** `Inputs/ODDD/<id>_ODDD.zip`
carries no period in its name and is overwritten in place, so each result names the month it
describes: the newest `<Mon><yy> Sig #` column. The page tags a row whose month is older than
the cycle's.

Reading 83 extracts (3.9 GB) over the share is slow, so each result is cached in
`<cache>/<id>.json` keyed on the zip's size and modification time, and only a changed extract
is read again.
"""
import csv
import datetime
import io
import json
import os
import re
import sys
import time
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for _p in (REPO / "build", REPO / "build" / "ars_pipeline"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import rpe_env as R                                              # noqa: E402
from odd_rows import accessors, status_class                     # noqa: E402

OVERVIEW_VERSION = "1"      # bump when a definition changes, so cached results are recomputed
_SIG_RX = re.compile(r"^([A-Z][a-z]{2}\d{2}) Sig #$")
_DATE_FORMATS = ("%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%y")   # metrics_gen.parsed


def odd_member(zf):
    """The ODD extract inside a zip. Some zips also carry the monthly transaction file as a
    second CSV (1038, 1549): pick by name ("-odd" or "_v2_"), else the largest CSV — the rule
    metrics_gen._linesrc uses."""
    csvs = [n for n in zf.namelist() if n.lower().endswith(".csv")]
    if not csvs:
        raise ValueError("no .csv inside the zip")
    named = [n for n in csvs if "-odd" in n.lower() or "_v2_" in n.lower()]
    return named[0] if named else max(csvs, key=lambda n: zf.getinfo(n).file_size)


def _month_start(d, back):
    y, m = d.year, d.month - back
    while m <= 0:
        m += 12
        y -= 1
    return datetime.datetime(y, m, 1)


def read_overview(path):
    """The overview figures for one ODD extract (a .zip or a plain .csv)."""
    csv.field_size_limit(10 ** 7)
    zf = zipfile.ZipFile(path) if str(path).lower().endswith(".zip") else None
    try:
        member = odd_member(zf) if zf else os.path.basename(str(path))
        raw = zf.open(member) if zf else open(path, "rb")
        with io.TextIOWrapper(raw, encoding="latin-1", errors="replace", newline="") as fh:
            rows = csv.reader(line.replace("\x00", "") for line in fh)
            hdr = None
            for k, row in enumerate(rows):
                if hdr is None:
                    if any(c.strip() == "Acct ID" for c in row):
                        hdr = [h.strip() for h in row]
                        state = _setup(hdr)
                    elif k > 25:
                        raise ValueError("no 'Acct ID' header row in the first 25 lines")
                    continue
                if "".join(row).strip():
                    _tally(state, row)
    finally:
        if zf:
            zf.close()
    if hdr is None:
        raise ValueError("no header row")
    return _result(state, member)


def _setup(hdr):
    months = sorted({m.group(1) for m in map(_SIG_RX.match, hdr) if m},
                    key=lambda t: datetime.datetime.strptime(t, "%b%y"))
    if not months:
        raise ValueError('no "<Mon><yy> Sig #" columns in the extract')
    latest = datetime.datetime.strptime(months[-1], "%b%y")
    now = _month_start(latest, -1) - datetime.timedelta(days=1)     # last day of the snapshot month
    H = {h: i for i, h in enumerate(hdr)}
    return {
        "odd": accessors(H), "months": months, "w3": months[-3:],
        "latest": latest, "now": now, "start12": _month_start(latest, 11),
        "i_desc": H.get("Stat Desc"), "i_code": H.get("Stat Code"),
        "status": {}, "dates": {},
        "rows": 0, "open": 0, "biz": 0, "per": 0, "sw": 0.0, "nsf": 0.0, "opened": 0, "closed": 0,
    }


def _cell(row, i):
    return row[i].strip() if i is not None and i < len(row) else ""


def _date(state, value):
    cache = state["dates"]
    if value in cache:
        return cache[value]
    out = None
    for fmt in _DATE_FORMATS:
        try:
            out = datetime.datetime.strptime(value, fmt)
            break
        except ValueError:
            pass
    cache[value] = out
    return out


def _tally(s, row):
    odd = s["odd"]
    s["rows"] += 1
    key = (_cell(row, s["i_desc"]), _cell(row, s["i_code"]))
    cls = s["status"].get(key)
    if cls is None:                          # a few dozen distinct pairs, looked up per row
        cls = s["status"][key] = status_class(*key)
    personal = odd.personal(row)
    if cls != "closed":
        s["open"] += 1
        if odd.business(row):
            s["biz"] += 1
        elif personal:
            s["per"] += 1
    for m in s["w3"]:
        s["nsf"] += odd.nsf(row, m)
    if personal:
        for m in s["w3"]:
            s["sw"] += odd.swipes(row, m)
        do = _date(s, odd.g(row, "Date Opened"))
        dc = _date(s, odd.g(row, "Date Closed"))
        if do and s["start12"] <= do <= s["now"]:
            s["opened"] += 1
        if dc and s["start12"] <= dc <= s["now"]:
            s["closed"] += 1


def _label(t):
    return datetime.datetime.strptime(t, "%b%y").strftime("%b %Y")


def _result(s, member):
    n3 = len(s["w3"])
    return {
        "file": member, "month": s["months"][-1], "month_label": _label(s["months"][-1]),
        "w3_label": "%s to %s" % (_label(s["w3"][0]), _label(s["w3"][-1])),
        "window12": [s["start12"].strftime("%b %Y"), s["latest"].strftime("%b %Y")],
        "accounts": s["rows"],
        "open_total": s["open"], "open_business": s["biz"], "open_personal": s["per"],
        "open_other": s["open"] - s["biz"] - s["per"],
        "personal_swipes_3mo_avg": round(s["sw"] / n3),
        "swipes_per_open_personal": round(s["sw"] / n3 / s["per"], 1) if s["per"] else None,
        "nsf_items_3mo_avg": round(s["nsf"] / n3),
        "personal_opened_12": s["opened"], "personal_closed_12": s["closed"],
    }


def odd_path(cid):
    """`Inputs/ODDD/<id>_ODDD.zip`, through rpe_env's kind folders."""
    return R.inputs() / R.INPUT_KIND_DIRS["ODDD"] / ("%s_ODDD.zip" % cid)


def client_overviews(cids, cache_dir, log=print, path_for=odd_path):
    """{id: overview, or {"missing": reason}} for each client, cached per extract."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out, read, took = {}, 0, time.time()
    for cid in cids:
        p = Path(path_for(cid))
        try:
            st = p.stat()
        except OSError:
            out[cid] = {"missing": "no ODD extract in Inputs"}
            continue
        sig = "%s:%d:%d" % (OVERVIEW_VERSION, st.st_size, int(st.st_mtime))
        cp = cache_dir / ("%s.json" % cid)
        try:
            hit = json.loads(cp.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            hit = None
        if isinstance(hit, dict) and hit.get("sig") == sig:
            out[cid] = hit["overview"]
            continue
        t0 = time.time()
        try:
            ov = read_overview(p)
        except Exception as e:                   # one bad extract never fails the page
            ov = {"missing": "ODD extract could not be read: %s" % (str(e)[:160] or type(e).__name__)}
        read += 1
        log("overview: %s read %s (%.0f MB) in %.0fs" % (cid, p.name, st.st_size / 1e6, time.time() - t0))
        tmp = cp.with_suffix(".json.part")
        tmp.write_text(json.dumps({"sig": sig, "overview": ov}), encoding="utf-8")
        tmp.replace(cp)
        out[cid] = ov
    log("overview: %d clients, %d extracts read, %d from cache, %.0fs"
        % (len(out), read, sum(1 for v in out.values() if "missing" not in v) - read, time.time() - took))
    return out
