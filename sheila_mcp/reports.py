"""Client reports Sheila answers from the share alone (James Gilmore, 2026-10-30: the CashPlease report and
portfolio, peer compare, the one-pager, and the client brief and prep "need to be in there").

These were James's v5 tools, reading his OneDrive checkout. Here they read what the RPE builds already
leave on M:\\CSM_Reporting, so every CSM gets the same answer:
  CashPlease   Build Artifacts\\cashplease\\packs\\<id>_cashplease.json (+ index.json), from the newest
               CashPleaseSummary export in Inputs\\CashPlease; a client is compared with the MEDIAN of the other
               current CashPlease clients, the deck's own comparison (peer_compare.for_deck); the pooled book total
               is internal and only cashplease_portfolio states it (Aaron, 2026-11-24: "D: median, pooled internal")
  peers        Build Artifacts\\launcher\\<period>\\<id>\\metrics.json across clients, the figures each
               client's deck was built from, compared by the deck's own code (peer_compare.for_deck("ARS"), at the
               client's newest build period; Aaron, 2026-11-24: "A: use the deck's code")
  everything   Build Artifacts\\perf_dashboard\\dataset.json (programs, revenue, readiness, decks)
Notes, tasks, calendar and mail are each CSM's own Microsoft 365, not Sheila's: the brief says so and
leaves them to the CSM's Microsoft 365 connector in Claude.
"""
import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor

import rpe_env as R

from .core import find_client, label, reply

MIN_PEERS = 5          # the deck's minimum (peer_compare.MIN_PEERS): a measure with fewer peers is not compared
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


CP_ROWS = [  # (label, metric key on the pack, peer_pool key (None: not compared), format, higher is better)
    ("Loans, all time", "total_loans", None, "n", None),
    ("Loans, last 12 months", "window_loans", None, "n", None),
    ("Loans per 1,000 checking accounts (12 mo)", "loans_per_1k_dda", "per_1k", "r", True),
    ("Average loan", "avg_loan_size", "avg_loan", "$", None),
    ("Interest per loan", "avg_interest_per_loan", "avg_interest", "$", True),
    ("Charge-off rate (dollars)", "charge_off_pct", "charge_off", "%", False),
    ("Loans charged off", "pct_loans_charged_off", None, "%", False),
    ("Loans overdue now", "pct_loans_overdue", "overdue", "%", False),
    ("Loans paid off", "pct_loans_paid_off", "paid_off", "%", True),
]
CP_RATES = {"charge_off", "overdue", "paid_off"}   # peer_pool states these in percent; the pack in fractions


def _fmt(v, f):
    if v is None:
        return "n/a"
    return {"n": f"{v:,.0f}", "r": f"{v:.1f}", "$": f"${v:,.0f}", "%": pct(v, nd=2)}[f]


def cp_median(cid):
    """The client's CashPlease comparison exactly as its deck states it (Aaron, 2026-11-24: "D: median, pooled
    internal"): `peer_compare.for_deck("CP", ...)`, the median of the other current CashPlease clients, the client's rank,
    the 5-peer minimum, a rate's gap in points, and a 0.0% charge-off on a large book left out of charge-off. None when the
    packs could not be read."""
    import peer_compare as PC
    try:
        return PC.for_deck("CP", cid, root=_ba())
    except Exception:
        return None


def cashplease_report(client):
    """One institution's CashPlease: volume, loss and repayment against the median of the other current CashPlease
    clients (the deck's comparison), the last six months, and anything the pack flags."""
    import peer_compare as PC
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
    ev = cp_median(cid)
    items = {it["spec"]["key"]: it for it in (ev or {}).get("items") or []}
    name = p.get("client_name") or (c or {}).get("name")
    lines = [f"{cid} {name}: CashPlease, from {p.get('source_file')} (report {p.get('report_generated')})."]
    if p.get("cancelled"):
        lines.append(f"Cancelled: {p['cancelled']}.")
    lines.append(f"{'':44}{'Client':>12}{'Median':>12}{'Rank':>14}")
    rows, said = [], []
    for lab, k, pk, f, better in CP_ROWS:
        v = m.get(k)
        it = items.get(pk) if pk else None
        med = rank = None
        if it:
            cc = it["c"]
            med = cc["median"] / 100.0 if pk in CP_RATES else cc["median"]
            rank = f"{PC.ordinal(cc['rank'])} of {cc['total']}"
            said.append(f"  {lab}: {PC.relation_phrase(cc, PC.formatter(it['spec']['fmt']))}; "
                        f"median of {cc['n']} other current clients, middle half {PC.formatter(it['spec']['fmt'])(cc['q1'])} "
                        f"to {PC.formatter(it['spec']['fmt'])(cc['q3'])}.")
        rows.append({"measure": lab, "client": v, "median": med, "peers": it["c"]["n"] if it else None,
                     "rank": it["c"]["rank"] if it else None, "of": it["c"]["total"] if it else None,
                     "relation": PC.relation_phrase(it["c"], PC.formatter(it["spec"]["fmt"])) if it else None,
                     "higher_is_better": better})
        lines.append(f"{lab:44}{_fmt(v, f):>12}{_fmt(med, f) if it else '':>12}{rank or '':>14}")
    lines += ["Against the median (the deck's wording):"] + (said or ["  nothing: too few other current clients have a figure."])
    if ev is None:
        lines.append("The other clients' figures could not be read, so nothing is compared.")
    else:
        for x in ev.get("left") or []:
            if any(x.startswith(s["label"] + ":") for s in _cp_specs() if s["key"] in {r[2] for r in CP_ROWS if r[2]}):
                lines.append(f"Not compared: {x}.")
        for it in items.values():
            lines.extend(n for n in it.get("notes") or [] if "left out of this comparison" in n)
    if m.get("dda_missing_reason"):
        lines.append(f"No loans-per-DDA rate: {m['dda_missing_reason']}.")
    elif m.get("dda_stale_days") and m["dda_stale_days"] > 120:
        lines.append(f"The checking-account count is {m['dda_stale_days']} days old ({m.get('dda_last_updated')}).")
    months = [x for x in p.get("monthly") or [] if x.get("period_month")]
    months = sorted(months, key=lambda x: x["period_month"])[-6:]
    if months:
        lines.append("Last six months (loans, principal, charged off): " + "; ".join(
            f"{x['period_month']} {x.get('loans', 0)}, {money(x.get('principal'))}, {x.get('charged_off', 0)}" for x in months))
    lines.append(f"Median = the median of the other current CashPlease clients with a figure ({(ev or {}).get('n_pool', 0)} "
                 "other current clients in the weekly), the same comparison as the deck's How You Compare and Peer Comparison "
                 "slides. The pooled book total is internal: ask for the CashPlease portfolio.")
    return reply("\n".join(lines), client=cid, name=name, rows=rows, monthly=months,
                 source=p.get("source_file"), report_generated=p.get("report_generated"))


def _cp_specs():
    from review_page import peer_pool as PP
    return PP.CP_METRICS


def cashplease_portfolio():
    """Every CashPlease institution in the current export: totals, the book's loss and repayment, and who
    leads and trails on loans per 1,000 checking accounts. Internal: the pooled book figures here are never what a
    client is compared with (that is the median, cashplease_report)."""
    from review_page import peer_pool as PP
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
    book = None
    try:
        book = PP.cashplease_book(PP.cashplease_current(_cp_dir()))
    except Exception:
        book = None
    if book:
        lines.append(f"CashPlease book, pooled (internal only; a client is compared with the median, never this), over "
                     f"{book['cohort_clients']} current clients: "
                     + (f"{book['loans_per_1k_dda']:.1f} loans per 1,000 checking accounts ({book['cohort_dda_clients']} "
                        f"clients with a count and 12 months); " if book.get("loans_per_1k_dda") is not None else "")
                     + f"average loan {money(book['avg_loan_size'])}; overdue {pct(book['pct_loans_overdue'], nd=2)}; "
                       f"loans charged off {pct(book['pct_loans_charged_off'], nd=2)}; paid off {pct(book['pct_loans_paid_off'], nd=2)}.")
    if rated:
        lines.append("Most loans per 1,000 checking accounts: " + "; ".join(
            f"{p['client_id']} {p['client_name']} {p['metrics']['loans_per_1k_dda']:.1f}" for p in rated[:5]))
        lines.append("Fewest: " + "; ".join(
            f"{p['client_id']} {p['client_name']} {p['metrics']['loans_per_1k_dda']:.1f}" for p in rated[-5:]))
    for f in idx.get("flags") or []:
        lines.append(f"Note: {f}")
    return reply("\n".join(lines), institutions=len(live), cancelled=len(packs) - len(live),
                 loans=tot("total_loans"), principal=principal, charged_off=co, book_pooled=book,
                 ranking=[{"id": p["client_id"], "name": p["client_name"],
                           "loans_per_1k_dda": p["metrics"]["loans_per_1k_dda"]} for p in rated])


# ------------------------------------------------------------------ peers
# The ARS comparison is the DECK's (Aaron, 2026-11-24: "A: use the deck's code"): `peer_compare.for_deck("ARS", client,
# period=<the client's newest launcher pack period>)`, so Sheila says exactly what the client's How You Compare slides say
# (median, middle half, rank, n, the +/-2% wording with a rate's gap in points, the 5-peer minimum, the client not in its
# own pool). The period is passed explicitly: asked with no period, the pool is the one at the client's own newest build,
# never "today's newest pack per client", which shrinks as other clients rebuild for the next month.
# Only what the CLIENT controls is compared (Aaron, 2026-11-22): peer_pool.ARS_METRICS.
KPI_ALIASES = {  # the keys this tool took before 2026-11-24, still accepted
    "debit_take": "take_all", "debit_take_new": "take_new_pct", "rege": "rege_pct", "rege_new": "rege_new_pct",
    "account_growth": "acct_growth", "retention_1yr": "ret_1yr",
}
RETIRED_KPIS = {"debit_on_checking", "retention_3yr"}   # not deck measures: the deck never ranks them


def _ars_specs():
    from review_page import peer_pool as PP
    return PP.ARS_METRICS


def kpi_keys():
    return [m["key"] for m in _ars_specs()]


def _periods():
    base = _ba() / "launcher"
    try:
        return sorted((d.name for d in os.scandir(base) if d.is_dir() and re.fullmatch(r"\d{4}\.\d{2}", d.name)),
                      reverse=True)
    except OSError:
        return []


def _metrics(period, cid):
    return _json(_ba() / "launcher" / period / cid / "metrics.json")


def _client_period(cid, period=None):
    """The newest period this client has deck figures for (or the one asked for), and those figures."""
    for p in ([period] if period else _periods()):
        m = _metrics(p, cid)
        if m:
            return p, m
    return None, None


def compare(cid, kpis=None, period=None):
    """(period, the deck's evaluation, rows) for the client's ARS measures, at its newest build period (or the one asked
    for). Each row: kpi, label, value, and when compared rank, of, n, median, p25, p75, vs_median (points), relation
    (the deck's words) and sentence; a measure the deck leaves out carries `left` (why) instead."""
    import peer_compare as PC
    period, mine = _client_period(cid, period)
    if not mine:
        return None, None, []
    keys = kpis or kpi_keys()
    # The client's own packs, as the deck build passes them (its own row then needs no mailing summary to be read).
    own = {"metrics": mine, "base": _json(_ba() / "launcher" / period / cid / "base.json")}
    ev = PC.for_deck("ARS", cid, period=period, root=_ba(), keys=keys, own=own)
    items = {it["spec"]["key"]: it for it in ev.get("items") or []}
    specs = {m["key"]: m for m in _ars_specs()}
    out = []
    for key in keys:
        spec = specs[key]
        it = items.get(key)
        if it is None:
            why = next((x.split(":", 1)[1].strip() for x in ev.get("left") or [] if x.startswith(spec["label"] + ":")),
                       "not compared")
            out.append({"kpi": key, "label": spec["label"], "value": None, "left": why})
            continue
        c = it["c"]
        f = PC.formatter(spec["fmt"])
        out.append({"kpi": key, "label": spec["label"], "value": c["client"], "rank": c["rank"], "of": c["total"],
                    "n": c["n"], "median": c["median"], "p25": c["q1"], "p75": c["q3"],
                    "vs_median": c["client"] - c["median"], "relation": PC.relation_phrase(c, f),
                    "sentence": it["sentence"]})
    return period, ev, out


def _want(kpis):
    """(keys, unknown, retired) from the tool's kpis text."""
    raw = [k.strip() for k in re.split(r"[,\s]+", kpis or "") if k.strip()]
    keys, bad, gone = [], [], []
    for k in raw:
        k2 = KPI_ALIASES.get(k, k)
        if k in RETIRED_KPIS:
            gone.append(k)
        elif k2 in kpi_keys():
            if k2 not in keys:
                keys.append(k2)
        else:
            bad.append(k)
    return keys, bad, gone


def peer_compare(client, kpis="", period=""):
    """How a client's ARS figures compare with the other ARS clients, exactly as the client's deck says it."""
    import peer_compare as PC
    c, why = find_client(client)
    if why:
        return reply(why)
    want, bad, gone = _want(kpis)
    if bad:
        return reply(f"Unknown measure(s): {', '.join(bad)}. Available: {', '.join(kpi_keys())}.")
    if gone and not want:
        return reply(f"{', '.join(gone)} {'is' if len(gone) == 1 else 'are'} not compared with other clients: the deck's "
                     f"ARS comparison covers {', '.join(kpi_keys())}.")
    per, ev, rows = compare(c["id"], want or None, period or None)
    if not per:
        return reply(f"{label(c)} has no ARS deck figures on the share yet (no launcher build), so there is "
                     "nothing to compare.", client=c["id"])
    n_pool = (ev or {}).get("n_pool", 0)
    lines = [f"{label(c)} against the other ARS clients, as its {per} deck compares them "
             f"({n_pool} other clients with a deck at or before {per}; each measure needs {PC.MIN_PEERS} with a current figure):"]
    if gone:
        lines.append(f"  ({', '.join(gone)}: not compared with other clients, so left out.)")
    for r in rows:
        if r["value"] is None:
            lines.append(f"  {r['label']}: not compared ({r['left']}).")
            continue
        f = PC.formatter(next(m["fmt"] for m in _ars_specs() if m["key"] == r["kpi"]))
        lines.append(f"  {r['sentence']} Middle half {f(r['p25'])} to {f(r['p75'])}; n = {r['n']}.")
    if ev and ev.get("unavailable"):
        lines.append(ev["unavailable"])
    quotable = any(r["value"] is not None for r in rows)
    return reply("\n".join(lines), client=c["id"], period=per, peers=n_pool, quotable=quotable, rows=rows)


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
    per, _ev, rows = compare(cid)
    points = []
    if per:
        import peer_tables as PT
        pp, prior = _prior(cid, per)
        prior_point = PT.ars_metrics(prior)["point"] if prior else {}
        higher_of = {m["key"]: m["higher"] for m in _ars_specs()}
        for r in rows:
            v = r.get("value")
            if v is None:
                continue
            higher = higher_of[r["kpi"]]
            pv = prior_point.get(r["kpi"])
            if pv is not None and ((v > pv) if higher else (v < pv)) and abs(v - pv) >= 1:
                points.append({"label": r["label"], "value": v, "frame": f"up from {pv:.1f}% in {pp}", "gain": abs(v - pv)})
            elif r.get("n", 0) >= MIN_PEERS and r.get("vs_median", 0) * (1 if higher else -1) >= 2:
                points.append({"label": r["label"], "value": v,
                               "frame": f"{r['relation']}; rank {r['rank']} of {r['of']}", "gain": abs(r["vs_median"])})
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
        co = next((it for it in (cp_median(cid) or {}).get("items") or [] if it["spec"]["key"] == "charge_off"), None)
        lines.append(f"CashPlease: {m.get('total_loans', 0):,} loans, {m.get('window_loans', 0):,} in 12 months, "
                     f"charge-off {pct(m.get('charge_off_pct'), nd=2)}"
                     + (f" (median of {co['c']['n']} other current clients {co['c']['median']:.1f}%)." if co
                        else " (not compared with other clients)."))
    decks = d.get("decks") or c.get("decks") or []
    lines.append(f"This cycle: {', '.join(decks) if decks else 'no deck in Outputs yet'}.")
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
    else:
        todo.append("The deck is in Outputs: review it (\"what needs my review\") before the call.")
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
