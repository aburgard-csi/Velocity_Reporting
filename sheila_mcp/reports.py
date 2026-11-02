"""Client reports Sheila answers from the share alone (James Gilmore, 2026-10-30: the CashPlease report and
portfolio, peer compare, the one-pager, and the client brief and prep "need to be in there").

These were James's v5 tools, reading his OneDrive checkout. Here they read what the RPE builds already
leave on M:\\CSM_Reporting, so every CSM gets the same answer:
  CashPlease   Build Artifacts\\cashplease\\packs\\<id>_cashplease.json (+ index.json), from the newest
               CashPleaseSummary export in Inputs\\CashPlease; peers are the pack's "all CashPlease clients"
               cohort and the dashboard's "current clients" cohort
  peers        Build Artifacts\\launcher\\<period>\\<id>\\metrics.json across clients, the figures each
               client's deck was built from
  everything   Build Artifacts\\perf_dashboard\\dataset.json (programs, revenue, readiness, decks, sent)
Notes, tasks, calendar and mail are each CSM's own Microsoft 365, not Sheila's: the brief says so and
leaves them to the CSM's Microsoft 365 connector in Claude.
"""
import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from statistics import median

import rpe_env as R

from .core import find_client, label, reply

MIN_PEERS = 5          # fewer than this and a rank is shown as a count, never as a percentile
_cache = {}
_cache_lock = threading.Lock()


def _json(path):
    """A JSON file, re-read only when it changes on the share. None when it is absent or unreadable."""
    p = str(path)
    try:
        st = os.stat(p)
    except OSError:
        return None
    key = (st.st_mtime_ns, st.st_size)
    with _cache_lock:
        hit = _cache.get(p)
    if hit and hit[0] == key:
        return hit[1]
    try:
        with open(p, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return hit[1] if hit else None
    with _cache_lock:
        _cache[p] = (key, doc)
    return doc


def _ba():
    return R.build_artifacts()


def dataset():
    return _json(_ba() / "perf_dashboard" / "dataset.json") or {"clients": []}


def ds_client(cid):
    return next((c for c in dataset().get("clients", []) if c.get("id") == cid), None)


def pct(x, frac=True, nd=1):
    if x is None:
        return "n/a"
    return f"{x * 100 if frac else x:.{nd}f}%"


def money(x):
    if x is None:
        return "n/a"
    return f"${x:,.0f}"


# ------------------------------------------------------------------ CashPlease
def _cp_dir():
    return _ba() / "cashplease" / "packs"


def cp_pack(cid):
    return _json(_cp_dir() / f"{cid}_cashplease.json")


CP_ROWS = [  # (label, metric key, peer key, format, higher is better)
    ("Loans, all time", "total_loans", None, "n", None),
    ("Loans, last 12 months", "window_loans", None, "n", None),
    ("Loans per 1,000 checking accounts (12 mo)", "loans_per_1k_dda", "loans_per_1k_dda", "r", True),
    ("Average loan", "avg_loan_size", "avg_loan_size", "$", None),
    ("Interest per loan", "avg_interest_per_loan", "avg_interest_per_loan", "$", True),
    ("Charge-off rate (dollars)", "charge_off_pct", "charge_off_pct", "%", False),
    ("Loans charged off", "pct_loans_charged_off", "pct_loans_charged_off", "%", False),
    ("Loans overdue now", "pct_loans_overdue", "pct_loans_overdue", "%", False),
    ("Loans paid off", "pct_loans_paid_off", "pct_loans_paid_off", "%", True),
]


def _fmt(v, f):
    if v is None:
        return "n/a"
    return {"n": f"{v:,.0f}", "r": f"{v:.1f}", "$": f"${v:,.0f}", "%": pct(v, nd=2)}[f]


def cashplease_report(client):
    """One institution's CashPlease: volume, loss and repayment against all CashPlease clients and the current
    cohort, the last six months, and anything the pack flags."""
    c, why = find_client(client)
    cid = c["id"] if c else str(client).strip()
    if why and not re.fullmatch(r"\d{3,5}", cid):
        return reply(why)
    p = cp_pack(cid)
    if not p:
        idx = _json(_cp_dir() / "index.json") or {}
        return reply(f"{label(c) if c else cid} has no CashPlease pack. The current export "
                     f"({idx.get('source_file', 'none found')}) has no tab for it, or the CashPlease build has not "
                     "run since it landed in Inputs\\CashPlease.", client=cid)
    m = p.get("metrics") or {}
    allp = m.get("peer") or {}
    cur = dataset().get("cp_peer") or {}
    name = p.get("client_name") or (c or {}).get("name")
    lines = [f"{cid} {name}: CashPlease, from {p.get('source_file')} (report {p.get('report_generated')})."]
    if p.get("cancelled"):
        lines.append(f"Cancelled: {p['cancelled']}.")
    lines.append(f"{'':44}{'Client':>12}{'All CP':>12}{'Current':>12}")
    rows = []
    for lab, k, pk, f, better in CP_ROWS:
        v = m.get(k)
        a = allp.get(pk) if pk else None
        cu = cur.get(pk) if pk else None
        rows.append({"measure": lab, "client": v, "all_cp": a, "current_cp": cu, "higher_is_better": better})
        lines.append(f"{lab:44}{_fmt(v, f):>12}{_fmt(a, f) if pk else '':>12}{_fmt(cu, f) if pk else '':>12}")
    if m.get("dda_missing_reason"):
        lines.append(f"No loans-per-DDA rate: {m['dda_missing_reason']}.")
    elif m.get("dda_stale_days") and m["dda_stale_days"] > 120:
        lines.append(f"The checking-account count is {m['dda_stale_days']} days old ({m.get('dda_last_updated')}).")
    months = [x for x in p.get("monthly") or [] if x.get("period_month")]
    months = sorted(months, key=lambda x: x["period_month"])[-6:]
    if months:
        lines.append("Last six months (loans, principal, charged off): " + "; ".join(
            f"{x['period_month']} {x.get('loans', 0)}, {money(x.get('principal'))}, {x.get('charged_off', 0)}" for x in months))
    lines.append(f"All CP = {allp.get('cohort', 'all CashPlease clients')} ({allp.get('cohort_tabs')} tabs); "
                 f"Current = {cur.get('cohort', 'current clients')} ({cur.get('cohort_clients')}).")
    return reply("\n".join(lines), client=cid, name=name, rows=rows, monthly=months,
                 source=p.get("source_file"), report_generated=p.get("report_generated"))


def cashplease_portfolio():
    """Every CashPlease institution in the current export: totals, the book's loss and repayment, and who
    leads and trails on loans per 1,000 checking accounts."""
    idx = _json(_cp_dir() / "index.json")
    if not idx:
        return reply("No CashPlease packs on the share: the CashPlease build has not run.")
    ids = [x["client_id"] for x in idx.get("clients") or []]
    with ThreadPoolExecutor(8) as ex:
        packs = [p for p in ex.map(cp_pack, ids) if p]
    live = [p for p in packs if not p.get("cancelled")]
    tot = lambda k: sum((p.get("metrics") or {}).get(k) or 0 for p in live)
    principal = tot("total_principal")
    co = sum(((p.get("status") or {}).get("Charged Off") or {}).get("principal") or 0 for p in live)
    rated = sorted((p for p in live if (p.get("metrics") or {}).get("loans_per_1k_dda") is not None),
                   key=lambda p: p["metrics"]["loans_per_1k_dda"], reverse=True)
    lines = [f"CashPlease book, from {idx.get('source_file')} (report {idx.get('report_generated')}):",
             f"  {len(live)} institutions live, {len(packs) - len(live)} cancelled.",
             f"  {tot('total_loans'):,.0f} loans, {money(principal)} lent; {tot('window_loans'):,.0f} loans in the last 12 months.",
             f"  Charged off: {money(co)} of principal ({pct(co / principal if principal else None, nd=2)}).",
             f"  Active now: {tot('active_loans'):,.0f} loans, {money(tot('active_principal'))}."]
    if rated:
        lines.append("Most loans per 1,000 checking accounts: " + "; ".join(
            f"{p['client_id']} {p['client_name']} {p['metrics']['loans_per_1k_dda']:.1f}" for p in rated[:5]))
        lines.append("Fewest: " + "; ".join(
            f"{p['client_id']} {p['client_name']} {p['metrics']['loans_per_1k_dda']:.1f}" for p in rated[-5:]))
    for f in idx.get("flags") or []:
        lines.append(f"Note: {f}")
    return reply("\n".join(lines), institutions=len(live), cancelled=len(packs) - len(live),
                 loans=tot("total_loans"), principal=principal, charged_off=co,
                 ranking=[{"id": p["client_id"], "name": p["client_name"],
                           "loans_per_1k_dda": p["metrics"]["loans_per_1k_dda"]} for p in rated])


# ------------------------------------------------------------------ peers
# The figures each client's ARS deck was built from (Build Artifacts\launcher\<period>\<id>\metrics.json).
# Every rate here is already a percent (84.0 means 84%).
KPIS = {
    "debit_take": ("Debit card take rate", "overall_take", True),
    "debit_take_new": ("Debit take rate, new accounts", "take_new_pct", True),
    "rege": ("Reg E opt-in", "rege_pct", True),
    "rege_new": ("Reg E opt-in, new accounts", "rege_new_pct", True),
    "response": ("Latest mailer response rate", "latest_resprate", True),
    "repeat": ("Responders who responded again", "depth_repeat_pct", True),
    "active_new": ("New accounts swiping monthly", "new_active_pct", True),
    "active_book": ("Book swiping monthly", "book_active_pct", True),
    "debit_on_checking": ("Open checking with a debit card", "open_chk_debit_pct", True),
    "retention_1yr": ("Accounts still open after 1 year", "ret_1yr", True),
    "retention_3yr": ("Accounts still open after 3 years", "ret_3yr", True),
}
DEFAULT_KPIS = ["debit_take", "rege", "response", "active_book", "retention_1yr"]


def _periods():
    base = _ba() / "launcher"
    try:
        return sorted((d.name for d in os.scandir(base) if d.is_dir() and re.fullmatch(r"\d{4}\.\d{2}", d.name)),
                      reverse=True)
    except OSError:
        return []


def _metrics(period, cid):
    return _json(_ba() / "launcher" / period / cid / "metrics.json")


def peer_set(period):
    """{client id: metrics} for every client whose deck was built for this period."""
    base = _ba() / "launcher" / period
    try:
        ids = [d.name for d in os.scandir(base) if d.is_dir() and re.fullmatch(r"\d{3,5}", d.name)]
    except OSError:
        return {}
    with ThreadPoolExecutor(8) as ex:
        got = dict(zip(ids, ex.map(lambda i: _metrics(period, i), ids)))
    return {k: v for k, v in got.items() if v}


def _standing(value, values, higher):
    vals = sorted(v for v in values if isinstance(v, (int, float)))
    n = len(vals)
    if value is None or not n:
        return None
    better = sum(1 for v in vals if (v > value if higher else v < value))
    q = lambda f: vals[min(n - 1, int(round(f * (n - 1))))]
    return {"rank": better + 1, "of": n, "median": median(vals), "p25": q(0.25), "p75": q(0.75),
            "percentile": round(100 * sum(1 for v in vals if v < value) / max(1, n - 1)) if n > 1 else None,
            "vs_median": value - median(vals)}


def _client_period(cid, period=None):
    """The newest period this client has deck figures for (or the one asked for), and those figures."""
    for p in ([period] if period else _periods()):
        m = _metrics(p, cid)
        if m:
            return p, m
    return None, None


def compare(cid, kpis=None, period=None):
    period, mine = _client_period(cid, period)
    if not mine:
        return None, None, []
    peers = peer_set(period)
    out = []
    for key in kpis or DEFAULT_KPIS:
        lab, field, higher = KPIS[key]
        v = mine.get(field)
        st = _standing(v, [m.get(field) for m in peers.values()], higher)
        out.append({"kpi": key, "label": lab, "value": v, **(st or {})})
    return period, peers, out


def peer_compare(client, kpis="", period=""):
    """How a client's ARS figures rank against every client whose deck was built the same cycle."""
    c, why = find_client(client)
    if why:
        return reply(why)
    want = [k.strip() for k in re.split(r"[,\s]+", kpis or "") if k.strip()] or None
    bad = [k for k in want or [] if k not in KPIS]
    if bad:
        return reply(f"Unknown measure(s): {', '.join(bad)}. Available: {', '.join(KPIS)}.")
    per, peers, rows = compare(c["id"], want, period or None)
    if not per:
        return reply(f"{label(c)} has no ARS deck figures on the share yet (no launcher build), so there is "
                     "nothing to compare.", client=c["id"])
    n = len(peers)
    lines = [f"{label(c)} against {n} clients whose ARS deck was built for {per}"
             + ("" if n >= MIN_PEERS else f" (fewer than {MIN_PEERS}: ranks only, not percentiles)") + ":"]
    for r in rows:
        if r["value"] is None:
            lines.append(f"  {r['label']}: not in this client's figures.")
            continue
        s = f"  {r['label']}: {r['value']:.1f}%, rank {r['rank']} of {r['of']}, median {r['median']:.1f}%"
        if n >= MIN_PEERS:
            s += f" (middle half {r['p25']:.1f}% to {r['p75']:.1f}%)"
        lines.append(s + f", {'+' if r['vs_median'] >= 0 else ''}{r['vs_median']:.1f} pts vs median.")
    return reply("\n".join(lines), client=c["id"], period=per, peers=n, quotable=n >= MIN_PEERS, rows=rows)


# ------------------------------------------------------------------ one-pager
def _prior(cid, period):
    for p in _periods():
        if p < period:
            m = _metrics(p, cid)
            if m:
                return p, m
    return None, None


def one_pager(client):
    """One page on a client: who they are, what we deliver, and up to three points worth saying, each one
    beating the client's own prior cycle or the peer median."""
    c, why = find_client(client)
    if why:
        return reply(why)
    cid = c["id"]
    d = ds_client(cid) or {}
    per, peers, rows = compare(cid, list(KPIS))
    points = []
    if per:
        pp, prior = _prior(cid, per)
        for r in rows:
            v = r.get("value")
            if v is None:
                continue
            higher = KPIS[r["kpi"]][2]
            pv = (prior or {}).get(KPIS[r["kpi"]][1])
            if pv is not None and ((v > pv) if higher else (v < pv)) and abs(v - pv) >= 1:
                points.append({"label": r["label"], "value": v, "frame": f"up from {pv:.1f}% in {pp}", "gain": abs(v - pv)})
            elif r.get("of", 0) >= MIN_PEERS and r.get("vs_median", 0) * (1 if higher else -1) >= 2:
                points.append({"label": r["label"], "value": v,
                               "frame": f"rank {r['rank']} of {r['of']}, median {r['median']:.1f}%", "gain": abs(r["vs_median"])})
        points = sorted(points, key=lambda x: -x["gain"])[:3]
    a = d.get("ars") or {}
    lines = [f"{label(c)}: {c.get('csm')}'s client. Programs: {', '.join(c.get('covered') or d.get('programs') or []) or 'none on the roster'}."]
    if c.get("products"):
        lines.append("Velocity products: " + ", ".join(c["products"]) + ".")
    if a.get("months_live"):
        lines.append(f"ARS: {a['months_live']} months live, {a.get('mailings')} mailings; revenue {money(a.get('ltd_revenue'))} to date, "
                     f"profit {money(a.get('ltd_profit'))}, {a.get('profitability', 0):.1f}x return; last 12 months {money(a.get('rev12_sum'))}.")
        lm = a.get("latest_mailing") or {}
        if lm:
            lines.append(f"Latest mailer ({lm.get('month')}): {lm.get('mailed', 0):,.0f} mailed, {lm.get('responders', 0):,.0f} responded, {lm.get('response_rate')}%.")
    if points:
        lines.append("Worth saying:")
        lines += [f"  {p['label']}: {p['value']:.1f}% ({p['frame']})" for p in points]
    elif per:
        lines.append("Nothing beats this client's prior cycle or the peer median by enough to lead with this cycle.")
    p = cp_pack(cid)
    if p and p.get("metrics"):
        m = p["metrics"]
        lines.append(f"CashPlease: {m.get('total_loans', 0):,} loans, {m.get('window_loans', 0):,} in 12 months, "
                     f"charge-off {pct(m.get('charge_off_pct'), nd=2)} (all CP {pct((m.get('peer') or {}).get('charge_off_pct'), nd=2)}).")
    decks = d.get("decks") or c.get("decks") or []
    lines.append(f"This cycle: {', '.join(decks) if decks else 'no deck in Outputs yet'}"
                 + (f"; sent {d.get('sent') or c.get('sent')}" if (d.get('sent') or c.get('sent')) else "") + ".")
    return reply("\n".join(lines), client=cid, period=per, points=points, programs=d.get("programs"), ars=a)


# ------------------------------------------------------------------ brief and prep
def client_brief(client):
    """Everything Sheila knows about a client, for a call or a meeting."""
    from . import actions, core
    c, why = find_client(client)
    if why:
        return reply(why)
    cid = c["id"]
    d = ds_client(cid) or {}
    page = one_pager(cid)
    lines = [page["answer"]]
    ready = d.get("readiness") or {}
    if ready:
        lines.append("Inputs for this cycle: " + "; ".join(
            f"{i.get('program')} {i.get('input')} {i.get('state')} ({i.get('detail')})" for i in ready.get("inputs") or [])
            + (f". Blocked on: {', '.join(ready['blocked_on'])}." if ready.get("blocked_on") else "."))
    for key, title in (("ics", "ICS"), ("mrpc", "MRPC")):
        blk = d.get(key) or {}
        if blk.get("missing"):
            lines.append(f"{title}: {blk['missing']}")
        elif key == "mrpc" and blk.get("weekly"):
            w = blk["weekly"]
            lines.append(f"MRPC: {w.get('all_mrpc_accounts', 0):,} enrolled accounts, take rate {pct(w.get('take_rate_all'))} "
                         f"(active {pct(w.get('take_rate_active'))}), from {w.get('file')}.")
        elif blk:
            lines.append(f"{title}: on the dashboard (see its deck for detail).")
    if c.get("ti_decks"):
        lines.append("Transaction Intelligence deck in Outputs: " + ", ".join(c["ti_decks"]) + ".")
    issues = core.data_issues(cid)
    if issues["data"].get("clients"):
        n = sum(len(e.get("issues") or []) + len(e.get("codes") or []) + (1 if e.get("lift_matrix") else 0)
                for e in issues["data"]["clients"])
        lines.append(f"{n} open data issue(s); ask for \"data issues for {cid}\" for each one and its fix.")
    if "ILS" in (c.get("products") or []):
        lines.append(actions.ils_status(cid)["answer"])
    lines.append("Not from Sheila: notes, tasks, calendar and email live in the CSM's own Microsoft 365. "
                 "If their Microsoft 365 connector is on in Claude, look there for the last meeting and recent mail.")
    return reply("\n".join(lines), client=cid, dashboard=d, one_pager=page["data"])


def client_prepare(client):
    """A meeting-prep sheet: the brief, then what to raise and what to fix before the call."""
    c, why = find_client(client)
    if why:
        return reply(why)
    b = client_brief(c["id"])
    d = b["data"].get("dashboard") or {}
    todo = []
    if not (d.get("decks") or c.get("decks")):
        todo.append("No deck in Outputs for this cycle: ask Sheila for its status, then build it.")
    elif not (d.get("sent") or c.get("sent")):
        todo.append("The deck is built but not marked sent: review it (\"what needs my review\") before the call.")
    if c.get("error"):
        todo.append("The last build failed: ask for the client's status to see why.")
    blocked = (d.get("readiness") or {}).get("blocked_on")
    if blocked:
        todo.append("Inputs missing for this cycle: " + ", ".join(blocked) + ".")
    pts = (b["data"].get("one_pager") or {}).get("points") or []
    raise_ = [f"{p['label']} at {p['value']:.1f}% ({p['frame']})" for p in pts]
    lines = [b["answer"], "", "Before the call:"] + [f"  - {t}" for t in todo or ["Nothing outstanding on Sheila's side."]]
    lines += ["To raise:"] + [f"  - {r}" for r in raise_ or ["No standout figure this cycle; lead with the program's results to date."]]
    return reply("\n".join(lines), client=c["id"], before_the_call=todo, to_raise=raise_)
