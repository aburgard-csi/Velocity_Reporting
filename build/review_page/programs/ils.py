#!/usr/bin/env python3
"""ils.py — the client's latest ILS Program Analysis review, as pages: the summary, fees and losses by month,
how accounts use the program, and how the client compares with its peers.

Reads `Build Artifacts/ils_analysis/review_packs/<id>_ils_review.json`, which `scripts/ils_review_pack.py` writes from
the review's PDF (Aaron, 2026-11-06: "build a LR page for Marine FCU using their last ILS analysis review"). Every figure
is a figure the review carries; the page derives only the differences (a percent change, points apart) and records each
as a derivation. The review is a finished document: this section is the review's figures as of its own date and data
through date, whatever period the page is opened for, and it says so.

The review's charts are pictures and are not on the page; its text tables are. The consultant's own commentary and the
opportunity analysis are quoted in the Sources panel, not restated as claims.
"""
import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))
if BUILD not in sys.path:
    sys.path.insert(0, BUILD)

import month_complete as MC                                  # noqa: E402
from review_page import blocks as B                          # noqa: E402
from review_page import packs as PK                          # noqa: E402
from review_page import trace as TR                          # noqa: E402
from review_page.trace import Pack                           # noqa: E402

KEY, LABEL = "ils", "ILS"
FIX = ("Save the client's ILS Program Analysis review as a PDF and run "
       "`python scripts/ils_review_pack.py \"<the review>.pdf\"` (the file name starts <id>-<yyyy.mm>-ILS-), then reload.")


def load(ctx):
    from review_page import ils_review_pack as R
    path = R.pack_path(ctx.client, ctx.root)
    data = PK.read_json(path, "the ILS review pack", FIX)
    return {"C": Pack(os.path.basename(str(path)), data, ctx.tracer, str(path)), "notes": {}, "deck": data.get("source_file")}


# ----------------------------------------------------------------- formatting
def _ym(ym):
    y, m = ym.split("-")
    return f"{MC._MON[int(m) - 1]} {y[2:]}"


def _ym_long(ym):
    y, m = ym.split("-")
    return f"{MC._MON[int(m) - 1]} {y}"


def _long_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def _fmt(v, kind):
    if v is None:
        return "—"
    if kind == "int":
        return B.f_int(v)
    if kind == "usd":
        return B.f_usd(v)
    if kind == "usd2":
        return f"${v:,.2f}"
    if kind == "pct":
        return f"{v:.1f}%"
    if kind == "pct2":
        return f"{v:.2f}%"
    if kind == "dec2":
        return f"{v:.2f}"
    return f"{v:.1f}"                                           # dec


def _vs(t, old, new, kind="usdk", tail="of the 12 months before"):
    """Where one figure stands against another, in neutral words: '21.9% below the $3.39M of the 12 months before', or
    'almost flat against ...' inside the +/-2% band. A rate is compared in points. It states where a figure stands, not why."""
    f = {"usdk": B.f_usdk, "int": B.f_int, "pct": lambda v: f"{v:.2f}%"}[kind]
    if kind == "pct":
        d = t.derive(round(new - old, 6), "points apart", old, new)
        if abs(d) < 0.005:
            return f"the same as the {f(old)} {tail}"
        return f"{abs(d):.2f} points {'above' if d > 0 else 'below'} the {f(old)} {tail}"
    pct = TR.change_pct(old, new)
    if pct is None:
        return "with no earlier figure to compare with"
    pct = t.derive(round(pct, 6), "percent change", old, new)
    if abs(pct) <= TR.BAND:
        return f"almost flat against the {f(old)} {tail}"
    return f"{abs(pct):.1f}% {'above' if pct > 0 else 'below'} the {f(old)} {tail}"


# ----------------------------------------------------------------- build
def build(ctx, p):
    t = ctx.tracer
    C = p["C"]
    name = C.get("client_name", default="The client")
    pages = C.get("pages") or {}
    review = C.get("review_date")
    src = C.get("source_file")
    inst = C.get("institution") or {}
    through = inst.get("data_through")
    stamp = f"the {_long_date(review)} review" if review else "the latest review"
    base_note = (f"These figures are from {stamp}" + (f", with data through {_long_date(through)}" if through else "") +
                 "; they do not change with the period the page is opened for. The review reports complete months only.")

    def fb(label, *keys):
        pg = ", ".join(f"page {pages[k]}" if not isinstance(pages[k], list) else "pages " + " and ".join(str(x) for x in pages[k])
                       for k in keys if k in pages)
        return [{"title": label, "text": f"Source: {src}, {pg}, read into {C.name}. Page numbers are the review's own."}]

    screens = []
    s1 = _summary(ctx, C, name, base_note, fb, pages)
    if s1:
        screens.append(s1)
    for fn in (_fees, _accounts, _peers):
        s = fn(ctx, C, name, base_note, fb, pages)
        if s:
            screens.append(s)
    if not screens:
        raise PK.PackMissing("the ILS review pack holds none of the tables the page shows", FIX)
    first = screens[0]
    summary = first.pop("_summary", None) or {"headline": first["headline"], "kpis": []}
    for s in screens[1:]:
        s.pop("_summary", None)
    summary["open"] = f"ils:{first['id']}"
    return {"screens": screens, "summary": summary, "client_name": name}


def _commentary_sources(C, pages):
    out = []
    pc = C.get("peer_comparison", "commentary")
    an = C.get("annual", "commentary")
    op = C.get("opportunity")
    if an:
        out.append({"title": f"Commentary in the review (page {pages.get('annual')})", "text": " • ".join(an)})
    if pc:
        out.append({"title": f"Commentary in the review (page {pages.get('peer_comparison')})", "text": " • ".join(pc)})
    if op:
        out.append({"title": f"Opportunity analysis, as presented (page {pages.get('opportunity')})", "text": " • ".join(op)})
    return out


def _summary(ctx, C, name, base_note, fb, pages):
    t = ctx.tracer
    if not (C.has("annual", "period1") and C.has("annual", "period2") and C.has("monthly", "period2")):
        return None
    p1, p2 = C.get("annual", "period1"), C.get("annual", "period2")
    m1, m2 = C.get("monthly", "period1"), C.get("monthly", "period2")
    first2, last2 = m2[0]["ym"], m2[-1]["ym"]
    first1, last1 = m1[0]["ym"], m1[-1]["ym"]
    inst = C.get("institution") or {}
    dda = inst.get("active_dda")
    vs_fees = _vs(t, p1["fees"], p2["fees"], "usdk")
    vs_cnt = _vs(t, p1["count"], p2["count"], "int")
    vs_def = _vs(t, p1["default_rt"], p2["default_rt"], "pct")
    items = [B.kpi(f"Collected fees, {_ym(first2)} to {_ym(last2)}", p2["fees"], "usd", hot=True, sub=vs_fees),
             B.kpi("Exception items, same 12 months", p2["count"], "int", sub=vs_cnt),
             B.kpi("Default rate, same 12 months", p2["default_rt"], "pct2", sub=vs_def)]
    if dda is not None:
        items.append(B.kpi("Active DDA accounts", dda, "int", sub=(f"Data through {_long_date(inst['data_through'])}" if inst.get("data_through") else None)))
    headline = (f"{name} collected {B.f_usdk(p2['fees'])} in fees in the 12 months to {_ym_long(last2)}, {vs_fees}. "
                f"Exception items were {B.f_int(p2['count'])}, {vs_cnt}.")
    notes = [base_note]

    cats = [_ym(r["ym"]) for r in m1 + m2]
    allm = m1 + m2

    def ser(key, nm, color):
        return {"name": nm, "values": [r[key] for r in allm], "color": color}
    chart = B.bars("ils-month", "By month", cats, [ser("fees", "Collected fees", "navy")], "usdk",
                   sub=f"{_ym(first1)} to {_ym(last2)}, the two 12-month periods the review compares",
                   metrics=[{"key": "fees", "label": "Collected fees", "fmt": "usdk", "series": [ser("fees", "Collected fees", "navy")]},
                            {"key": "count", "label": "Exception items", "fmt": "int", "series": [ser("count", "Exception items", "steel")]},
                            {"key": "default_rt", "label": "Default rate", "fmt": "pct2", "series": [ser("default_rt", "Default rate", "orange")]},
                            {"key": "loss_rt", "label": "Loss rate", "fmt": "pct1", "series": [ser("loss_rt", "Losses as a share of fees", "gold")]},
                            {"key": "fees_per_acct", "label": "Fees per account", "fmt": "usd", "series": [ser("fees_per_acct", "Fees per account with OD", "teal")]}])
    cols = [B.col("name", "Month"), B.col("count", "Items", "int"), B.col("default_rt", "Default rate", "pct2"),
            B.col("accts", "Accounts with OD", "int"), B.col("fees", "Collected fees", "usd"), B.col("per_day", "Fees per business day", "usd"),
            B.col("per_acct", "Fees per account", "usd"), B.col("losses", "Losses", "usd"), B.col("loss_rt", "Loss rate", "pct1")]
    rows = [{"name": _ym(r["ym"]), "count": r["count"], "default_rt": r["default_rt"], "accts": r["accts_with_od"], "fees": r["fees"],
             "per_day": r["fees_per_bizday"], "per_acct": r["fees_per_acct"], "losses": r["losses"], "loss_rt": r["loss_rt"]}
            for r in reversed(allm)]
    tbl = B.table("ils-month-table", "By month", cols, rows, sort={"key": None},
                  sub="Exception items, collected fees and losses in each complete month, newest first.")
    sources = fb("ILS review", "institution", "monthly", "annual") + _commentary_sources(C, pages)
    scr = B.screen("summary", "Program summary", f"ILS · Review of {_long_date(C.get('review_date'))}" if C.get("review_date") else "ILS · Review",
                   headline, [B.kpis(items), B.drill(chart, tbl)], PK.sources_for({}, ["ILS"], sources), notes)
    scr["_summary"] = {"headline": headline, "kpis": [dict(k, go="ils:summary") for k in items[:3]]}
    return scr


def _fees(ctx, C, name, base_note, fb, pages):
    t = ctx.tracer
    if not (C.has("annual", "period1") and C.has("annual", "period2")):
        return None
    p1, p2 = C.get("annual", "period1"), C.get("annual", "period2")
    m1, m2 = C.get("monthly", "period1"), C.get("monthly", "period2")
    l1 = f"{_ym(m1[0]['ym'])} to {_ym(m1[-1]['ym'])}"
    l2 = f"{_ym(m2[0]['ym'])} to {_ym(m2[-1]['ym'])}"
    spec = [("Exception items", "count", "int"), ("Cures", "cure", "int"), ("Default rate", "default_rt", "pct2"),
            ("Business days", "biz_days", "int"), ("Accounts with OD", "accts_with_od", "int"), ("Collected fees", "fees", "usd"),
            ("Fees per business day", "fees_per_bizday", "usd"), ("Fees per account", "fees_per_acct", "usd"),
            ("Losses", "losses", "usd"), ("Loss rate (losses as a share of fees)", "loss_rt", "pct")]
    rows = []
    for label, k, kind in spec:
        a, b = p1[k], p2[k]
        if kind in ("pct", "pct2"):
            d = t.derive(round(b - a, 6), "points apart", a, b)
            chg = "no change" if abs(d) < 0.005 else f"{d:+.2f} pts" if kind == "pct2" else f"{d:+.1f} pts"
        else:
            pct = TR.change_pct(a, b)
            if pct is None:
                chg = "—"
            else:
                pct = t.derive(round(pct, 6), "percent change", a, b)
                chg = "no change" if pct == 0 else "almost flat" if abs(pct) <= TR.BAND else f"{pct:+.1f}%"
        rows.append({"name": label, "p1": _fmt(a, kind), "p2": _fmt(b, kind), "chg": chg})
    cols = [B.col("name", "Measure"), B.col("p1", l1, None, "right"), B.col("p2", l2, None, "right"), B.col("chg", "Change", None, "right")]
    tbl = B.table("ils-annual", "The two periods side by side", cols, rows, search=False, sort={"key": None},
                  sub="Each measure over the 12 months, and how the later period stands against the earlier.")
    last6 = m2[-6:]
    first6 = m2[:6]
    loss_first = sum(r["losses"] for r in first6)
    fees_first = sum(r["fees"] for r in first6)
    loss_last = sum(r["losses"] for r in last6)
    fees_last = sum(r["fees"] for r in last6)
    lr_first = t.derive(round(100.0 * loss_first / fees_first, 6), "loss rate, first six months", *[r["losses"] for r in first6], *[r["fees"] for r in first6])
    lr_last = t.derive(round(100.0 * loss_last / fees_last, 6), "loss rate, last six months", *[r["losses"] for r in last6], *[r["fees"] for r in last6])
    headline = (f"Collected fees were {B.f_usdk(p2['fees'])} in {l2} against {B.f_usdk(p1['fees'])} in {l1}; exception items were "
                f"{B.f_int(p2['count'])} against {B.f_int(p1['count'])}. Losses were {B.f_usd(p2['losses'])} against {B.f_usd(p1['losses'])}, "
                f"{p2['loss_rt']:.1f}% of fees against {p1['loss_rt']:.1f}%.")
    items = [B.kpi(f"Loss rate, {_ym(first6[0]['ym'])} to {_ym(first6[-1]['ym'])}", lr_first, "pct1", sub="Losses as a share of collected fees"),
             B.kpi(f"Loss rate, {_ym(last6[0]['ym'])} to {_ym(last6[-1]['ym'])}", lr_last, "pct1", sub="Losses as a share of collected fees")]
    note_split = ("The loss rate is a month's losses as a share of that month's collected fees. It is shown for the first and the last six months "
                  "of the later period to give the direction within it.")
    sources = fb("ILS review", "monthly", "annual") + _commentary_sources(C, pages)
    return dict(B.screen("fees", "Fees and losses", "ILS · Two 12-month periods", headline, [B.kpis(items), tbl],
                         PK.sources_for({}, ["ILS"], sources), [base_note, note_split]), _summary=None)


_TIER_LABEL = {"Non-user": "Non-user", "6 items or fewer": "6 items or fewer", "7 to 23 items": "7 to 23 items", "Heavy user (24+ items)": "Heavy user (24 or more items)"}
_BAND_LABEL = {"ZERO DEPS": "No deposits", "<10k": "Under $10K", "10-25k": "$10K to $25K", "25-per.cap": "$25K to per capita",
               "per.cap-45k": "Per capita to $45K", "45-55k": "$45K to $55K", "55-65k": "$55K to $65K", "65-75k": "$65K to $75K",
               "75-85k": "$75K to $85K", "85-95k": "$85K to $95K", "95-105k": "$95K to $105K", "105-115k": "$105K to $115K", "115k+": "$115K and over"}


def _accounts(ctx, C, name, base_note, fb, pages):
    t = ctx.tracer
    if not C.has("utilization", "rows"):
        return None
    ut = C.get("utilization", "rows")
    tot = C.get("utilization", "total")
    nonuser, heavy = ut[0], ut[-1]
    headline = (f"{heavy['fees_pct']:.1f}% of fees come from the {heavy['accounts_pct']:.1f}% of accounts that are heavy users; "
                f"{nonuser['accounts_pct']:.1f}% of accounts are non-users.")
    c1 = B.bars("ils-util", "Share of accounts and share of fees", [_TIER_LABEL.get(r["tier"], r["tier"]) for r in ut],
                [{"name": "Share of accounts", "values": [r["accounts_pct"] for r in ut], "color": "navy"},
                 {"name": "Share of fees", "values": [r["fees_pct"] for r in ut], "color": "orange"}], "pct1",
                sub="By how many items an account has used the program, active accounts")
    cols = [B.col("name", "Use"), B.col("accts", "Accounts", "int"), B.col("acct_pct", "Share of accounts", "pct1"), B.col("rege", "Reg E opt-in", "pct1"),
            B.col("elig", "Eligible", "pct1"), B.col("dep", "Median 365-day deposits", "usd"), B.col("paid", "Paid", "pct1"),
            B.col("fees", "Fees, 365 days", "usd"), B.col("fees_pct", "Share of fees", "pct1")]
    rows = [{"name": _TIER_LABEL.get(r["tier"], r["tier"]), "accts": r["accounts"], "acct_pct": r["accounts_pct"], "rege": r["reg_e_pct"], "elig": r["eligible_pct"],
             "dep": r["deposits_365"], "paid": r["paid_pct"], "fees": r["fees_365"], "fees_pct": r["fees_pct"]} for r in ut]
    total = {"name": "All accounts", "accts": tot["accounts"], "acct_pct": tot["accounts_pct"], "rege": tot["reg_e_pct"], "elig": tot["eligible_pct"],
             "dep": tot["deposits_365"], "paid": tot["paid_pct"], "fees": tot["fees_365"], "fees_pct": tot["fees_pct"]}
    tbl = B.table("ils-util-table", "Account utilization", cols, rows, total=total, search=False, sort={"key": None})
    blocks = [B.drill(c1, tbl)]
    if C.has("mature", "rows"):
        mt = C.get("mature", "rows")
        mtot = C.get("mature", "total")
        c2 = B.bars("ils-mature", "Share of fees by a year of deposits", [_BAND_LABEL.get(r["band"], r["band"]) for r in mt],
                    [{"name": "Share of accounts", "values": [r["accounts_pct"] for r in mt], "color": "navy"},
                     {"name": "Share of fees", "values": [r["fees_pct"] for r in mt], "color": "orange"}], "pct1",
                    sub="Accounts open more than a year, by their deposits over the past year")
        cols2 = [B.col("name", "365-day deposits"), B.col("accts", "Accounts", "int"), B.col("acct_pct", "Share of accounts", "pct1"), B.col("rege", "Reg E opt-in", "pct1"),
                 B.col("elig", "Eligible", "pct1"), B.col("paid", "Paid", "pct1"), B.col("od", "Median paid OD", "usd"), B.col("fees", "Fees, 365 days", "usd"),
                 B.col("fees_pct", "Share of fees", "pct1")]
        rows2 = [{"name": _BAND_LABEL.get(r["band"], r["band"]), "accts": r["accounts"], "acct_pct": r["accounts_pct"], "rege": r["reg_e_pct"], "elig": r["eligible_pct"],
                  "paid": r["paid_pct"], "od": r["median_paid_od"], "fees": r["fees_365"], "fees_pct": r["fees_pct"]} for r in mt]
        total2 = {"name": "All accounts open over a year", "accts": mtot["accounts"], "acct_pct": mtot["accounts_pct"], "rege": mtot["reg_e_pct"], "elig": mtot["eligible_pct"],
                  "paid": mtot["paid_pct"], "od": mtot["median_paid_od"], "fees": mtot["fees_365"], "fees_pct": mtot["fees_pct"]}
        tbl2 = B.table("ils-mature-table", "Mature accounts", cols2, rows2, total=total2, search=False, sort={"key": None})
        blocks.append(B.drill(c2, tbl2))
    note = ("The fees on this screen are the review's FEES.365 for active accounts. They are a separate measure from the monthly collected fees on the previous screen, "
            "so the totals differ.")
    sources = fb("ILS review", "utilization", "mature")
    return dict(B.screen("accounts", "How accounts use it", "ILS · Account utilization", headline, blocks,
                         PK.sources_for({}, ["ILS"], sources), [base_note, note]), _summary=None)


_RISK_LABEL = {"BANK": "All banks", "CU": "All credit unions", "<= 1B": "Credit unions to $1B", "1B-2B": "Credit unions $1B to $2B",
               "2B-5B": "Credit unions $2B to $5B", "5B-10B": "Credit unions $5B to $10B", "10B+": "Credit unions over $10B"}


def _peers(ctx, C, name, base_note, fb, pages):
    t = ctx.tracer
    if not C.has("peer_comparison", "rows"):
        return None
    pc = C.get("peer_comparison")
    n_peers = pc["peer_count"]
    by = {r["code"]: r for r in pc["rows"]}
    rows = []
    for r in pc["rows"]:
        kind, c, pe = r["kind"], r["client"], r["peer"]
        if kind == "pct":
            d = t.derive(round(c - pe, 6), "points apart", c, pe)
            diff = "same" if abs(d) < 0.05 else f"{d:+.1f} pts"
        else:
            pct = TR.change_pct(pe, c)
            if pct is None:
                diff = "—"
            else:
                pct = t.derive(round(pct, 6), "percent apart", pe, c)
                diff = "almost the same" if abs(pct) <= TR.BAND else f"{abs(pct):.1f}% {'higher' if pct > 0 else 'lower'}"
        rows.append({"name": r["label"], "client": _fmt(c, kind), "peer": _fmt(pe, kind), "diff": diff})
    cols = [B.col("name", "Measure"), B.col("client", name, None, "right"), B.col("peer", f"Median of {n_peers} credit unions", None, "right"), B.col("diff", "Against the median", None, "right")]
    tbl = B.table("ils-peer", "Against the median of its peer set", cols, rows, search=False, sort={"key": None},
                  sub="Measures without a plain name keep the review's own code.")
    pick = [by[k] for k in ("MED.ELIG.PER", "MED.REGE.PER", "USR.CHGOFF.PER") if k in by]
    items = [B.kpi(r["label"], r["client"], "pct1", sub=f"Peer median {_fmt(r['peer'], 'pct')}") for r in pick]
    blocks = []
    if items:
        blocks.append(B.kpis(items))
    blocks.append(tbl)
    notes = [base_note]
    if C.has("risk", "global") and C.get("risk", "global"):
        risk = C.get("risk")
        rc = [B.col("name", "Group"), B.col("n", "Clients", "int"), B.col("active", "Active checking, median", "int"), B.col("od", "OD rate, median", "dec2"),
              B.col("default", "Default rate, median", "pct1"), B.col("income", "Fee income, median", "usd"), B.col("per", "Fees per account, median", "usd2"),
              B.col("loss", "Loss rate, median", "pct1")]

        def rr(r):
            return {"name": name if r["group"] == "this client" else _RISK_LABEL.get(r["group"], r["group"]), "n": r["n"], "active": r["active_checking"],
                    "od": r["od_rate"], "default": r["default_rt"], "income": r["fee_income"], "per": r["fees_per_acct"], "loss": r["loss_rt"]}
        blocks.append(B.table("ils-risk-all", "OD risk metrics: all Velocity clients", rc, [rr(r) for r in risk["global"]], search=False, sort={"key": None},
                              sub="Personal accounts. The client is one row among the groups."))
        if risk.get("by_asset_size"):
            blocks.append(B.table("ils-risk-size", "OD risk metrics: credit unions by asset size", rc, [rr(r) for r in risk["by_asset_size"]], search=False, sort={"key": None}))
        notes.append("The peer comparison and the risk tables use different peer sets, as the review gives them: the number of clients in each is in the tables.")
    headline = (f"{name}'s eligible share is {pick_val(by, 'MED.ELIG.PER')}% and its Reg E opt-in is {pick_val(by, 'MED.REGE.PER')}%, "
                f"against peer medians of {pick_peer(by, 'MED.ELIG.PER')}% and {pick_peer(by, 'MED.REGE.PER')}%; charge-offs are {pick_val(by, 'USR.CHGOFF.PER')}% of users against {pick_peer(by, 'USR.CHGOFF.PER')}%."
                if all(k in by for k in ("MED.ELIG.PER", "MED.REGE.PER", "USR.CHGOFF.PER")) else f"{name} against the median of {n_peers} credit union peers.")
    sources = fb("ILS review", "peer_comparison", "risk")
    return dict(B.screen("peers", "Against peers", "ILS · Peer comparison", headline, blocks, PK.sources_for({}, ["ILS"], sources), notes), _summary=None)


def pick_val(by, k):
    return f"{by[k]['client']:.1f}"


def pick_peer(by, k):
    return f"{by[k]['peer']:.1f}"
