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


class PeerCtx:
    """What a collector needs to know, for a caller that is not a Live Review page (an Executive Review deck build):
    the client, the period ("yyyy.mm"), the Build Artifacts folder (None -> rpe_env.build_artifacts()), `own` (the client's
    own packs when the build holds them already: {"metrics": ..., "base": ..., "cashplease": ...}) and `ics_dir` (a folder of
    ICS workbooks other than Inputs/ICS Workbooks, for a test). A Live Review `Ctx` has client, period and root, which is all
    the collectors read when `own` and `ics_dir` are absent."""

    def __init__(self, client, period=None, root=None, own=None, ics_dir=None):
        self.client, self.period, self.root, self.own, self.ics_dir = str(client), period, root, own, ics_dir


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
    # Revenue per account per month by source, from the ICS workbooks (Aaron, 2026-11-03): the ICS deck's own arithmetic
    # (peer_tables.ics_revenue), every client with a workbook. The client's figure is shown only when its workbook is for
    # the period (the deck's own rule: no carried-forward financials); a peer's workbook may be up to
    # PT.ICS_MAX_AGE_MONTHS older, and the comparison says which months the workbooks carry.
    rev_months = []
    try:
        import peer_tables as PT
        me_id = str(ctx.client)
        cache = PT.cache_dir(ctx.root) if getattr(ctx, "root", None) else None
        for cid, e in PT.ics_revenue_rows(folder=getattr(ctx, "ics_dir", None), cache=cache).items():
            if cid == me_id:
                if ctx.period and e["period"] != ctx.period:
                    continue
            elif ctx.period and (PT.months_between(e["period"], ctx.period) or 0) > PT.ICS_MAX_AGE_MONTHS:
                continue
            vals = {k: v for k, v in e["vals"].items() if k.startswith("rev_")}
            rows.setdefault(cid, {"point": {}, "series": {}})["point"].update(vals)
            if e.get("month"):
                rev_months.append(e["month"] + "-01")
    except (OSError, ValueError, KeyError, SystemExit):
        pass
    pulls.extend(rev_months)
    mine, peers = _split(rows, str(ctx.client))
    return {"n_pool": len(peers), "me": mine, "peers": peers, "pull": _span(pulls)}


ICS_METRICS = [
    {"key": "pct_goal", "label": "Referrals as a share of the monthly goal", "fmt": "pct0", "higher": True, "month": True},
    {"key": "per_1k", "label": "Referrals per 1,000 DDAs", "fmt": "dec1", "higher": True, "month": True},
    {"key": "rev_total", "label": "Revenue per account per month, all sources", "fmt": "usd2", "higher": True, "month": False},
    {"key": "rev_interchange", "label": "Interchange revenue per account per month", "fmt": "usd2", "higher": True, "month": False},
    {"key": "rev_nsf_od", "label": "NSF/OD and other fee revenue per account per month", "fmt": "usd2", "higher": True, "month": False},
    {"key": "rev_spread", "label": "Spread revenue per account per month", "fmt": "usd2", "higher": True, "month": False},
]


# ----------------------------------------------------------------- REMS
REMS_MIN_RESPONSES = 10          # a month with fewer responses than this is too small for a rate to mean anything
REMS_WINDOW = 12                 # the headline comparison pools this many complete months (REMS volumes are tens a month)
REMS_MIN_WINDOW = 30             # ... and needs this many responses in them
REMS_DEMO = {"999"}              # Union Financial Bank, the demo client: in the query's result, never a client or a peer


def _recent_months(as_of, k):
    """The `k` calendar months before the month `as_of` falls in ("YYYY-MM"), the complete ones."""
    out = []
    y, m = as_of.year, as_of.month
    for i in range(1, k + 1):
        yy, mm = divmod(y * 12 + (m - 1) - i, 12)
        out.append("%04d-%02d" % (yy, mm + 1))
    return out


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
            if cid in REMS_DEMO:
                continue
            ent = rows.setdefault(cid, {"name": r.get("client_name") or None, "months": {}})
            ent["months"]["%04d-%02d" % (y, mo)] = (n, o)
    return rows, as_of, os.path.basename(path)


def collect_rems(ctx):
    rows, as_of, fname = rems_rows(ctx)
    out = {}
    recent6, window = _recent_months(as_of, 6), _recent_months(as_of, REMS_WINDOW)
    for cid, ent in rows.items():
        mo = ent["months"]
        if not any(mo.get(m, (0, 0))[0] > 0 for m in recent6):
            continue                                          # no responses in the last six complete calendar months: not a current client
        ended = sorted(m for m in mo if MC.month_ended(m, as_of) is not False)
        series = {_label(m): 100.0 * mo[m][1] / mo[m][0] for m in ended[-24:] if mo[m][0] >= REMS_MIN_RESPONSES}
        n = sum(mo.get(m, (0, 0))[0] for m in window)
        o = sum(mo.get(m, (0, 0))[1] for m in window)
        point = {"pct_opt_in_12": 100.0 * o / n} if n >= REMS_MIN_WINDOW else {}
        out[cid] = {"point": point, "series": {"pct_opt_in": series}}
    mine, peers = _split(out, str(ctx.client))
    return {"n_pool": len(peers), "me": mine, "peers": peers, "pull": str(as_of) if as_of else None}


REMS_METRICS = [
    {"key": "pct_opt_in_12", "label": "Opt-in rate, last 12 months", "fmt": "pct1", "higher": True, "month": False},
    {"key": "pct_opt_in", "label": "Opt-in rate by month", "fmt": "pct1", "higher": True, "month": True},
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
def _cp_row(d):
    """(row, report date) for one client's CashPlease pack, or (None, None) when it is cancelled, has no loans or none in
    the last six complete months."""
    if d.get("cancelled") or not (d.get("total") or {}).get("loans"):
        return None, None
    gen = MC.report_date(d.get("report_generated"))
    mon = [r for r in (d.get("monthly") or []) if r.get("period_month") and MC.month_ended(r["period_month"], gen) is not False]
    mon.sort(key=lambda r: r["period_month"])
    if not any(r["loans"] for r in mon[-6:]):
        return None, None                                     # no loans in the last six complete months: not current
    mt = d.get("metrics") or {}
    point = {}
    if mt.get("peer_comparable") and mt.get("loans_per_1k_dda") is not None:
        point["per_1k"] = float(mt["loans_per_1k_dda"])
    if mt.get("pct_loans_overdue") is not None:
        point["overdue"] = 100.0 * mt["pct_loans_overdue"]
    if d.get("charge_off_pct") is not None and not charge_off_unreported(d):
        point["charge_off"] = 100.0 * d["charge_off_pct"]
    # Program to date, as the CashPlease deck's own cohort slide states them (Aaron, 2026-11-03: "anything else ... a head
    # of retail banking would want benchmarked"): the size of a loan, the interest it earns, and how many are paid off.
    if mt.get("avg_loan_size") is not None:
        point["avg_loan"] = float(mt["avg_loan_size"])
    if mt.get("avg_interest_per_loan") is not None:
        point["avg_interest"] = float(mt["avg_interest_per_loan"])
    if mt.get("pct_loans_paid_off") is not None:
        point["paid_off"] = 100.0 * mt["pct_loans_paid_off"]
    dda = mt.get("dda_accounts")
    series = {}
    if dda:
        series["per_1k_month"] = {_label(r["period_month"]): 1000.0 * r["loans"] / dda for r in mon[-24:]}
    return {"point": point, "series": series}, gen


def charge_off_unreported(d):
    """True when a pack's charge-off rate reads as NOT REPORTED rather than as no losses: exactly 0.0% on at least
    CP_ZERO_CHARGE_OFF_MIN_LOANS loans booked (Aaron, 2026-11-24: "Leave out of charge-off peers")."""
    co = d.get("charge_off_pct")
    loans = (d.get("total") or {}).get("loans") or (d.get("metrics") or {}).get("total_loans") or 0
    return co is not None and float(co) == 0.0 and loans >= CP_ZERO_CHARGE_OFF_MIN_LOANS


# A charge-off rate of exactly 0.0% on this many loans booked or more is taken as NOT REPORTED (Aaron, 2026-11-24): that
# client is left out of the CHARGE-OFF comparison only, and still counted for loans per 1,000 DDAs and every other measure.
# On the 11/15/2026 weekly a third of the current clients read exactly 0.0%, several of them on thousands of loans.
# At the program's typical charge-off of about 3% a book of 500 loans would expect some 15 charge-offs, so a true zero there
# is not credible; under 500 a zero is left in as reported. Any comparison that states the count says why they are out.
CP_ZERO_CHARGE_OFF_MIN_LOANS = 500
CP_ZERO_CHARGE_OFF_WHY = (f"a charge-off rate of exactly 0.0% on {CP_ZERO_CHARGE_OFF_MIN_LOANS:,} or more loans booked is "
                          "taken as not reported, not as no losses")


def cp_packs_dir(root=None):
    """The folder of CashPlease packs (`<Build Artifacts>/cashplease/packs`, or under `root`)."""
    import rpe_env
    return os.path.join(str(root or rpe_env.build_artifacts()), "cashplease", "packs")


def cashplease_current(packs_dir):
    """{client id: (pack, row, report date)} for every CURRENT client's pack in `packs_dir` (`_cp_row`: not cancelled, a loan
    in the last six complete months). The one currency rule, shared by the decks, Live Review and the performance dashboard,
    whose packs live in its own work folder."""
    out = {}
    try:
        entries = sorted((e for e in os.scandir(str(packs_dir)) if e.name.endswith("_cashplease.json")), key=lambda e: e.name)
    except OSError:
        return out
    for e in entries:
        cid = e.name.split("_")[0]
        d = _pack_json(e)
        if d is None:
            continue
        row, gen = _cp_row(d)
        if row is not None:
            out[cid] = (d, row, gen)
    return out


_PACKS = {}


def _pack_json(entry):
    """A pack read once per change (its size and modified time, from the directory listing): Sheila in Claude is a
    long-running process and the packs sit on the share, where reading some 75 of them costs seconds every question.
    A copy is returned, so no caller can change the cached one."""
    import copy
    try:
        st = entry.stat()
    except OSError:
        return None
    key = (st.st_mtime_ns, st.st_size)
    hit = _PACKS.get(entry.path)
    if hit is None or hit[0] != key:
        try:
            hit = (key, json.loads(open(entry.path, encoding="utf-8").read()))
        except (OSError, ValueError):
            return None
        _PACKS[entry.path] = hit
    return copy.deepcopy(hit[1])


def cashplease_book(current):
    """The CashPlease BOOK, pooled over the current clients `cashplease_current` returned: totals divided by totals
    (cp_extract's formulas, which summed over every tab reproduce the workbook's rollup). INTERNAL ONLY (Aaron, 2026-11-24:
    "D: median, pooled internal"): the performance dashboard and Sheila's cashplease_portfolio show it labelled "CashPlease
    book, pooled"; anything a client sees is the median (`cashplease_medians`, peer_compare). A few large books dominate a
    pooled rate, so it is not "the typical client". Rates and averages only, so no client's volume leaves the function.
    The charge-off % is a value each tab REPORTS and no weighting of the clients' values reproduces the rollup's, so it is
    None: stated as absent, never approximated. None when there is no current client."""
    packs = [d for d, _row, _gen in current.values()]
    loans = sum((d.get("total") or {}).get("loans") or 0 for d in packs)
    if not loans:
        return None
    principal = sum(d["total"].get("principal") or 0 for d in packs)
    interest = sum(d["total"].get("interest") or 0 for d in packs)

    def share(status):
        return sum(((d.get("status") or {}).get(status) or {}).get("loans") or 0 for d in packs) / loans

    inc = [d for d in packs if (d.get("metrics") or {}).get("peer_comparable")]
    dda = sum(d["metrics"]["dda_accounts"] for d in inc)
    win = sum(d["metrics"]["window_loans"] for d in inc)
    return {"cohort": "CashPlease book, pooled", "cohort_clients": len(packs),
            "avg_loan_size": principal / loans, "avg_interest_per_loan": interest / loans,
            "pct_loans_overdue": share("Overdue"), "pct_loans_charged_off": share("Charged Off"),
            "pct_loans_paid_off": share("Paid Off"), "charge_off_pct": None, "pct_active_accounts_with_loans": None,
            "cohort_dda_clients": len(inc), "loans_per_1k_dda": (win / dda * 1000) if dda else None}


def cashplease_medians(current):
    """{metric key: {"median", "n"}} over every current client, for a page that shows the median client beside the pooled
    book (the dashboard). The same rows and exclusions as `collect_cashplease` (a charge-off of 0.0% on a large book is
    left out), and peer_compare's quantile; values in peer_pool's units (percent for a rate). Medians and counts only: no
    client's own figure leaves the function. A measure with fewer than peer_compare.MIN_PEERS clients is left out."""
    import peer_compare as PC
    out = {}
    for spec in CP_METRICS:
        if spec.get("month"):
            continue
        vals = [row["point"][spec["key"]] for _d, row, _gen in current.values() if row["point"].get(spec["key"]) is not None]
        if len(vals) >= PC.MIN_PEERS:
            out[spec["key"]] = {"median": PC.quantile(vals, 0.5), "n": len(vals)}
    n_out = sum(1 for d, _row, _gen in current.values() if charge_off_unreported(d))
    if n_out:
        out.setdefault("charge_off", {})["left_out"] = n_out
    return out


def collect_cashplease(ctx):
    cur = cashplease_current(cp_packs_dir(ctx.root))
    packs = {cid: d for cid, (d, _row, _gen) in cur.items()}
    rows = {cid: row for cid, (_d, row, _gen) in cur.items()}
    pulls = [str(gen or "") for _d, _row, gen in cur.values()]
    me = str(ctx.client)
    own = (getattr(ctx, "own", None) or {}).get("cashplease")      # the pack the deck was built from, when the build holds it
    if own:
        row, gen = _cp_row(own)
        if row is not None:
            rows[me], packs[me] = row, own
    mine, peers = _split(rows, me)
    out = {"n_pool": len(peers), "me": mine, "peers": peers, "pull": _span(pulls)}
    n_out = sum(1 for p in peers if charge_off_unreported(packs.get(p["id"]) or {}))
    if n_out or (me in packs and charge_off_unreported(packs[me])):
        out["figures"] = [CP_ZERO_CHARGE_OFF_MIN_LOANS, 0.0]                 # what the notes state, for Live Review's tracer
    if n_out:
        out["excluded"] = {"charge_off": n_out}
        out["figures"].append(n_out)
        out["metric_notes"] = {"charge_off": [
            f"Charge-off rate: {n_out} other client{'s' if n_out != 1 else ''} left out of this comparison only, because "
            f"{CP_ZERO_CHARGE_OFF_WHY}; they are still counted for every other measure."]}
    if me in packs and charge_off_unreported(packs[me]):
        loans = (packs[me].get("total") or {}).get("loans") or 0
        out["reasons"] = {"charge_off": f"not compared: this client's charge-off rate reads 0.0% on {loans:,} loans booked, and "
                                        f"{CP_ZERO_CHARGE_OFF_WHY}"}
        out["figures"].append(loans)
    return out


CP_METRICS = [
    {"key": "per_1k", "label": "Loans per 1,000 DDAs, last 12 months", "fmt": "dec1", "higher": True, "month": False},
    {"key": "per_1k_month", "label": "Monthly loans per 1,000 DDAs", "fmt": "dec1", "higher": True, "month": True},
    {"key": "overdue", "label": "Share of loans overdue", "fmt": "pct1", "higher": False, "month": False},
    {"key": "charge_off", "label": "Charge-off rate", "fmt": "pct1", "higher": False, "month": False},
    {"key": "avg_loan", "label": "Average loan size, program to date", "fmt": "usd", "higher": None, "month": False},
    {"key": "avg_interest", "label": "Average interest per loan, program to date", "fmt": "usd2", "higher": True, "month": False},
    {"key": "paid_off", "label": "Share of loans paid off, program to date", "fmt": "pct1", "higher": True, "month": False},
]


# ----------------------------------------------------------------- ARS
def collect_ars(ctx):
    """ARS peers from the data packs every deck build leaves in Build Artifacts/launcher/<period>/<id>/ (peer_tables.py):
    the deck's own response rate, responder before/after, tier movement, swipes and spend per eligible account, Reg E, take
    rate, retention and active cards. A peer's snapshot figures count only when its pack reads the same activity month as
    the client's (the same extract month); its by-mailing response rate is month-keyed and aligned by `align_month`."""
    import peer_tables as PT
    import rpe_env
    root = ctx.root or rpe_env.build_artifacts()
    me_id = str(ctx.client)
    rows = PT.ars_rows(root, ctx.period)
    own = getattr(ctx, "own", None) or {}
    if own.get("metrics"):
        rows[me_id] = PT.ars_metrics(own["metrics"], own.get("base"))
    mine = rows.get(me_id) or {"point": {}, "series": {}, "activity": None, "rev_month": None}
    peers = []
    for cid, r in rows.items():
        if cid == me_id:
            continue
        point = dict(r["point"])
        if mine.get("activity") and r["activity"] != mine["activity"]:
            point = {}                                        # a pack from another extract month is not current for a snapshot
        if mine.get("rev_month") and r.get("rev_month") != mine["rev_month"]:
            point.pop("rev_per_1k", None)
        peers.append({"id": cid, "point": point, "series": r["series"]})
    mine = {"point": mine["point"], "series": mine["series"]}
    return {"n_pool": len(peers), "me": mine, "peers": peers,
            "pull": _span([str(r.get("pack_period") or "").replace(".", "-") + "-01" for r in rows.values() if r.get("pack_period")])}


# ARS peers are compared ONLY on what the client controls (Aaron, 2026-11-22: "For ARS peer comparisons, don't compare
# program results. Compare things the customer controls, like Reg E, account growth, debit card take rate."). The program's
# own results (response rates, responder spend, tier movement, card usage, ARS revenue) are never ranked against other
# clients; peer_tables.ars_metrics still reads them for the figures that use them directly.
ARS_METRICS = [
    {"key": "rege_pct", "label": "Reg E opt-in, open personal accounts", "fmt": "pct1", "higher": True, "month": False},
    {"key": "rege_new_pct", "label": "Reg E opt-in, accounts opened in the last 12 months", "fmt": "pct1", "higher": True, "month": False},
    {"key": "take_all", "label": "Debit card take rate, eligible accounts", "fmt": "pct1", "higher": True, "month": False},
    {"key": "take_new_pct", "label": "Debit card take rate, new accounts", "fmt": "pct1", "higher": True, "month": False},
    {"key": "acct_growth", "label": "Account growth, last 12 months", "fmt": "pct1", "higher": True, "month": False},
    {"key": "ret_1yr", "label": "One-year account retention", "fmt": "pct1", "higher": True, "month": False},
]
# Program results: never compared with other clients (kept so a test can say so).
ARS_PROGRAM_RESULTS = ("resp_12m", "resp_rate", "spend_gain", "spend_after", "moved_up", "swipes_per_acct", "spend_per_acct",
                       "active_cards", "rev_per_1k")


# ----------------------------------------------------------------- the registry a deck reads
PROGRAMS = {
    "ARS": (collect_ars, ARS_METRICS, "ARS"),
    "ICS": (collect_ics, ICS_METRICS, "ICS"),
    "MRPC": (collect_mrpc, MRPC_METRICS, "MRPC"),
    "CP": (collect_cashplease, CP_METRICS, "CashPlease"),
    "REMS": (collect_rems, REMS_METRICS, "REMS"),
}
