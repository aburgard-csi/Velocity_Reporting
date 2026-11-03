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
    mine, peers = _split(rows, str(ctx.client))
    return {"n_pool": len(peers), "me": mine, "peers": peers, "pull": _span(pulls)}


ICS_METRICS = [
    {"key": "pct_goal", "label": "Referrals as a share of the monthly goal", "fmt": "pct0", "higher": True, "month": True},
    {"key": "per_1k", "label": "Referrals per 1,000 DDAs", "fmt": "dec1", "higher": True, "month": True},
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
    for cid in sorted(ids):
        point, series = {}, {}
        w = wk.client(cid) if cid in wk.tabs else None
        if w is not None:
            mon = w.get("monthly") or []
            recent = mon[-6:]
            if not any((r["platinum"] + r["gold"] + r["business"]) > 0 for r in recent):
                continue                                      # the program has gone quiet: not a current peer
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


MRPC_METRICS = [
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
