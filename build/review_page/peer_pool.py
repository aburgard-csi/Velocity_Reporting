#!/usr/bin/env python3
"""peer_pool.py — read the other clients on a program, once, and hand back values with the client number and nothing else.

The rows are the ones the performance dashboard reads (`build/peer_data.py`: `ics_section`, `mrpc_section`,
`cp_section`, the MRPCEnrollmentSummary weekly, the CashPlease packs). Each `collect_*` returns

    {"n_pool": other clients on the program at all,
     "me":    {"point": {metric: value}, "series": {metric: {"Sep 2026": value}}},
     "peers": [ {"id": "1234", "point": ..., "series": ...} per other client — in no particular order; the client number
                (Aaron, 2026-11-03: the hover on a peer dot says which client it is) and NO name, logo or CSM ],
     "pull":  "2026-10-27 to 2026-10-27"}

so nothing downstream can name a peer; the number is all it can say. Metrics are normalised the way each program's own deck states them: ICS referrals as a
percent of the monthly goal (and per 1,000 DDAs where the DDA count is known), MRPC enrollments as a percent of goal, the
share of cardholders still active and the take rate among active accounts, CashPlease loans per 1,000 DDAs with the ILS DDA
count, and the share of loans overdue and charged off. MRPC revenue is not compared: VIP's revenue is known stale
(2026-10-06).

Month-based series use month labels ("Sep 2026"); a month still in progress is not in any series.

Import-safe: nothing is read until a collector is called.
"""
import datetime
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.abspath(os.path.join(HERE, os.pardir))
if BUILD not in sys.path:
    sys.path.insert(0, BUILD)

import month_complete as MC                                  # noqa: E402

_ID_RX = re.compile(r"^(\d{3,5})-")


def _label(m):
    return MC.label(m)


def _vip_ids(program):
    import rpe_env
    root = rpe_env.inputs() / "VIP Data" / program
    ids = []
    for p in sorted(glob.glob(str(root / "*"))):
        m = _ID_RX.match(os.path.basename(p))
        if m:
            ids.append(m.group(1))
    return ids


def _dda(ctx):
    """{client id: DDA accounts} from the ILS DDA count, where it has one (the CashPlease denominator)."""
    import rpe_env
    root = ctx.root or rpe_env.build_artifacts()
    try:
        d = json.loads(open(os.path.join(str(root), "cashplease", "dda_counts.json"), encoding="utf-8").read())
    except (OSError, ValueError):
        return {}
    return {str(k): v.get("dda_accounts") for k, v in (d.get("clients") or {}).items() if v.get("dda_accounts")}


_REFS = {}


def referrals_by_month():
    """({client id: {"YYYY-MM": referrals}}, newest issue date "YYYY-MM-DD") from the ALL-clients ICS referrals file
    (Inputs/ICS Referrals/ics_referrals.csv, which the morning source check keeps merged). It holds one row per referral
    for every Velocity ICS client, where the VIP sheets cover only the clients a CSM has pulled (Aaron, 2026-11-03: "use all
    peers"). ({}, None) when the file is not there, so the VIP-only comparison stands."""
    import csv
    import rpe_env
    try:
        path = rpe_env.input_dir("ICS referrals", create=False) / "ics_referrals.csv"
        st = path.stat()
    except (OSError, ValueError, KeyError):
        return {}, None
    key = (str(path), st.st_mtime, st.st_size)
    if _REFS.get("key") == key:
        return _REFS["value"]
    by, newest = {}, ""
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            d = (r.get("issue_date") or "")[:10]
            cid = (r.get("client_id") or "").strip()
            if len(d) < 7 or not cid:
                continue
            by.setdefault(cid, {})
            by[cid][d[:7]] = by[cid].get(d[:7], 0) + 1
            if d > newest:
                newest = d
    value = (by, newest or None)
    _REFS.clear()
    _REFS.update(key=key, value=value)
    return value


def _ics_per_1k(refs, newest, dda, last=24, current=6):
    """{client id: {"Sep 2026": referrals per 1,000 DDAs}} for every client with a DDA count and a referral in the last
    `current` complete months. The month the file was last pulled in is in progress and is left out."""
    if not refs or not newest:
        return {}
    cut = newest[:7]
    y, mo = int(cut[:4]), int(cut[5:7])
    recent = set()                                            # the `current` calendar months before the month the file was pulled in
    for k in range(1, current + 1):
        yy, mm = divmod(y * 12 + (mo - 1) - k, 12)
        recent.add("%04d-%02d" % (yy, mm + 1))
    out = {}
    for cid, months in refs.items():
        if not dda.get(cid):
            continue
        if not any(months.get(m) for m in recent):
            continue                                          # no referrals in the last six complete months: not a current peer
        done = sorted(m for m in months if m < cut)
        out[cid] = {_label(m): 1000.0 * months[m] / dda[cid] for m in done[-last:]}
    return out


def _span(dates):
    ds = sorted(d for d in dates if d)
    return f"{ds[0]} to {ds[-1]}" if ds else None


def _split(rows, me):
    """({me row} or an empty one, [peer rows, each carrying its client number as "id"])"""
    mine = rows.get(me) or {"point": {}, "series": {}}
    return mine, [dict(r, id=str(cid)) for cid, r in rows.items() if cid != me]


# ----------------------------------------------------------------- ICS
def collect_ics(ctx):
    import peer_data as PD
    dda = _dda(ctx)
    rows, pulls = {}, []
    for cid in _vip_ids("ICS"):
        s = PD.ics_section(cid, {"roster_programs": []})
        if s.get("missing"):
            continue
        tr = s.get("trend") or {}
        months, refs, goals = tr.get("months") or [], tr.get("referrals") or [], tr.get("goal") or []
        goal_pct, per1k = {}, {}
        for m, r, g in zip(months, refs, goals):
            if r is None:
                continue
            if g:
                goal_pct[_label(m)] = 100.0 * r / g
            if dda.get(cid):
                per1k[_label(m)] = 1000.0 * r / dda[cid]
        rows[cid] = {"point": {}, "series": {"pct_goal": goal_pct, "per_1k": per1k}}
        pulls.append(s.get("data_pull"))
    # Referrals per 1,000 DDAs from the all-clients referrals file, for EVERY client with a DDA count: one source for
    # the client and all its peers (the VIP trend and the detail export count a little differently), and far more peers
    # than the VIP sheets carry. The share of goal stays VIP-only: goals are not in the all-clients file.
    refs, newest = referrals_by_month()
    for cid, series in _ics_per_1k(refs, newest, dda).items():
        rows.setdefault(cid, {"point": {}, "series": {}})["series"]["per_1k"] = series
    if newest:
        pulls.append(newest)
    mine, peers = _split(rows, str(ctx.client))
    return {"n_pool": len(peers), "me": mine, "peers": peers, "pull": _span(pulls)}


ICS_METRICS = [
    {"key": "pct_goal", "label": "Referrals as a share of the monthly goal", "fmt": "pct0", "higher": True, "month": True},
    {"key": "per_1k", "label": "Referrals per 1,000 DDAs", "fmt": "dec1", "higher": True, "month": True},
]


# ----------------------------------------------------------------- REMS
REMS_MIN_RESPONSES = 10          # a month with fewer responses than this is too small for a rate to mean anything


def rems_rows(ctx):
    """({client id: {"name", "months": {"YYYY-MM": (responses, opt-ins)}}}, as_of, file name) from the newest
    `rems_responses*.csv` the REMS query's result was saved as (Inputs/REMS, or `<ctx.root>/rems` for a test). The file holds
    every client. ({}, None, None) when there is none. `as_of` is the date in the file name, else the file's own date."""
    import csv
    import datetime
    import re
    import rpe_env
    from pathlib import Path
    base = Path(ctx.root) / "rems" if getattr(ctx, "root", None) else rpe_env.input_dir("REMS", create=False)
    files = sorted(glob.glob(str(base / "rems_responses*.csv")), key=os.path.getmtime)
    if not files:
        return {}, None, None
    path = files[-1]
    m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(path))
    as_of = datetime.date.fromisoformat(m.group(1)) if m else datetime.date.fromtimestamp(os.path.getmtime(path))
    rows = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
            try:
                cid, y, mo = r["client_id"], int(float(r["response_year"])), int(float(r["response_month"]))
                n, o = float(r["num_responses"]), float(r["num_opt_in"])
            except (KeyError, ValueError):
                continue
            ent = rows.setdefault(cid, {"name": r.get("client_name") or None, "months": {}})
            ent["months"]["%04d-%02d" % (y, mo)] = (n, o)
    return rows, as_of, os.path.basename(path)


def collect_rems(ctx):
    rows, as_of, fname = rems_rows(ctx)
    out = {}
    for cid, ent in rows.items():
        ended = sorted(m for m in ent["months"] if MC.month_ended(m, as_of) is not False)
        if not ended or not any(ent["months"][m][0] > 0 for m in ended[-6:]):
            continue                                          # no responses in the last six complete months: not a current client
        series = {_label(m): 100.0 * ent["months"][m][1] / ent["months"][m][0] for m in ended[-24:]
                  if ent["months"][m][0] >= REMS_MIN_RESPONSES}
        out[cid] = {"point": {}, "series": {"pct_opt_in": series}}
    mine, peers = _split(out, str(ctx.client))
    return {"n_pool": len(peers), "me": mine, "peers": peers, "pull": str(as_of) if as_of else None}


REMS_METRICS = [
    {"key": "pct_opt_in", "label": "Opt-in rate", "fmt": "pct1", "higher": True, "month": True},
]


# ----------------------------------------------------------------- MRPC
_WEEKLY = {}


def _weekly():
    if "w" not in _WEEKLY:
        from mrpc_weekly import MrpcWeekly
        _WEEKLY["w"] = MrpcWeekly()
    return _WEEKLY["w"]


def collect_mrpc(ctx):
    import peer_data as PD
    import rpe_env
    wk = _weekly()
    rows, pulls = {}, []
    ids = set(wk.tabs) | set(_vip_ids("MRPC"))
    # The weekly covers every MRPC client (the VIP sheets only the few a CSM pulled), so the comparison that needs no goal is
    # enrollments per 1,000 debit-card accounts, from the weekly alone (Aaron, 2026-11-03: "we must have more than 6 MRPC
    # clients"). The months are those the weekly itself carries: the newest month any client has ends the window.
    newest = max((r["month"] for c in wk.tabs for r in (wk.client(c).get("monthly") or [])), default=None)
    recent6 = _months_back(newest, 6) if newest else []
    window = _months_back(newest, MRPC_WINDOW) if newest else []
    for cid in sorted(ids):
        point, series = {}, {}
        w = wk.client(cid) if cid in wk.tabs else None
        if w is not None:
            mon = w.get("monthly") or []
            by_month = {r["month"]: r["platinum"] + r["gold"] + r["business"] for r in mon}
            if not any(by_month.get(m, 0) > 0 for m in recent6):
                continue                                      # no enrollments in the last six months the weekly carries: not a current peer
            owd = w.get("open_with_debit")
            if owd:
                series["enroll_per_1k"] = {_label(m): 1000.0 * n / owd for m, n in sorted(by_month.items())[-24:]}
                n12 = sum(by_month.get(m, 0) for m in window)
                if n12 >= MRPC_MIN_WINDOW:
                    point["enroll_12_per_1k"] = 1000.0 * n12 / owd
            ev, ac = w.get("all_cardholders"), w.get("active_cardholders")
            if ev and ac is not None:
                point["still_active"] = 100.0 * ac / ev
            if w.get("take_rate_active") is not None:
                point["take_active"] = 100.0 * w["take_rate_active"]
            pulls.append(str(MC.report_date(w.get("report_generated")) or ""))
        try:
            v = PD.mrpc_section(cid, wk)
        except BaseException:
            v = {}
        pv, pg = v.get("goal_months") or [], v.get("pct_of_goal") or []
        if pv and pg:
            series["pct_goal"] = {_label(m): float(x) for m, x in zip(pv, pg) if x is not None}
        if point or series:
            rows[cid] = {"point": point, "series": series}
    mine, peers = _split(rows, str(ctx.client))
    return {"n_pool": len(peers), "me": mine, "peers": peers, "pull": _span(pulls)}


MRPC_WINDOW = 12                 # months pooled for the headline comparison
MRPC_MIN_WINDOW = 10             # enrollments needed in them to be compared


def _months_back(newest, k):
    """The `k` months ending at `newest` ("YYYY-MM"), newest included."""
    y, m = int(newest[:4]), int(newest[5:7])
    out = []
    for i in range(k):
        yy, mm = divmod(y * 12 + (m - 1) - i, 12)
        out.append("%04d-%02d" % (yy, mm + 1))
    return out


MRPC_METRICS = [
    {"key": "enroll_12_per_1k", "label": "Enrollments per 1,000 debit-card accounts, last 12 months", "fmt": "dec1", "higher": True, "month": False},
    {"key": "enroll_per_1k", "label": "Monthly enrollments per 1,000 debit-card accounts", "fmt": "dec1", "higher": True, "month": True},
    {"key": "pct_goal", "label": "Enrollments as a share of goal", "fmt": "pct0", "higher": True, "month": True},
    {"key": "still_active", "label": "Cardholders still active", "fmt": "pct1", "higher": True, "month": False},
    {"key": "take_active", "label": "Take rate among active accounts", "fmt": "pct1", "higher": True, "month": False},
]


# ----------------------------------------------------------------- CashPlease
def collect_cashplease(ctx):
    import rpe_env
    root = ctx.root or rpe_env.build_artifacts()
    rows, pulls = {}, []
    for f in sorted(glob.glob(os.path.join(str(root), "cashplease", "packs", "*_cashplease.json"))):
        cid = os.path.basename(f).split("_")[0]
        try:
            d = json.loads(open(f, encoding="utf-8").read())
        except (OSError, ValueError):
            continue
        if d.get("cancelled") or not (d.get("total") or {}).get("loans"):
            continue
        gen = MC.report_date(d.get("report_generated"))
        mon = [r for r in (d.get("monthly") or []) if r.get("period_month") and MC.month_ended(r["period_month"], gen) is not False]
        mon.sort(key=lambda r: r["period_month"])
        if not any(r["loans"] for r in mon[-6:]):
            continue                                          # no loans in the last six complete months: not current
        mt = d.get("metrics") or {}
        point = {}
        if mt.get("peer_comparable") and mt.get("loans_per_1k_dda") is not None:
            point["per_1k"] = float(mt["loans_per_1k_dda"])
        if mt.get("pct_loans_overdue") is not None:
            point["overdue"] = 100.0 * mt["pct_loans_overdue"]
        if d.get("charge_off_pct") is not None:
            point["charge_off"] = 100.0 * d["charge_off_pct"]
        dda = mt.get("dda_accounts")
        series = {}
        if dda:
            series["per_1k_month"] = {_label(r["period_month"]): 1000.0 * r["loans"] / dda for r in mon[-24:]}
        rows[cid] = {"point": point, "series": series}
        pulls.append(str(gen or ""))
    mine, peers = _split(rows, str(ctx.client))
    return {"n_pool": len(peers), "me": mine, "peers": peers, "pull": _span(pulls)}


CP_METRICS = [
    {"key": "per_1k", "label": "Loans per 1,000 DDAs, last 12 months", "fmt": "dec1", "higher": True, "month": False},
    {"key": "per_1k_month", "label": "Monthly loans per 1,000 DDAs", "fmt": "dec1", "higher": True, "month": True},
    {"key": "overdue", "label": "Share of loans overdue", "fmt": "pct1", "higher": False, "month": False},
    {"key": "charge_off", "label": "Charge-off rate", "fmt": "pct1", "higher": False, "month": False},
]
