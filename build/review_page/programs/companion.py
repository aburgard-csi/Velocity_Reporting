#!/usr/bin/env python3
"""companion.py — the ARS Companion views worth putting in front of a head of retail banking.

Reads `combined_insights.json`, which the ARS Companion build writes beside its deck
(`Build Artifacts/launcher/<period>/<id>/companion/<id>/`). Nothing is recomputed here: the figures
are `combined_insights.compute`'s own, so the page and the Companion deck cannot disagree. Six of the
thirty-eight Companion views are on the page (the selection, and why the others are not, is
`docs/LIVE-REVIEW-SELECTION.md`):

    waves        where the revenue came from, by mailing        (Revenue by Mailing, Where This Month's Revenue Came From)
    offers       what a thousand offers return, by mailing      (Revenue per 1,000 Offers)
    response     what a response is worth against a control     (Responders vs Mailed Non-Responders, What a Response Is Worth)
    scorecard    branch by branch: take, Reg E, closures        (Branch Scorecard, Take Rate and Reg E Opt-In by Branch)
    migration    who moved up and down a swipe tier             (Swipe Tier Migration)
    five-points  what five points of take and Reg E would earn  (What Five Points Would Be Worth)

A client with no Companion build is a greyed program that says to run it.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))
if BUILD not in sys.path:
    sys.path.insert(0, BUILD)

import month_complete as MC                                    # noqa: E402
from review_page import blocks as B                            # noqa: E402
from review_page import packs as PK                            # noqa: E402
from review_page.trace import Pack                             # noqa: E402

KEY, LABEL = "analysis", "ARS analysis"
HIDDEN = True            # its screens are reached through the storyline, not a switcher tab of their own


def load(ctx):
    d = PK.launcher_dir(ctx.client, ctx.period, ctx.root)
    cdir = d / "companion" / str(ctx.client)
    fix = (f"Build the ARS Companion for {ctx.client} in CSM Sheila (its ARS Companion panel), or run "
           f"`python scripts/ars_launcher.py build {ctx.client} --companion`; it writes combined_insights.json "
           f"to Build Artifacts/launcher/{ctx.period}/{ctx.client}/companion/{ctx.client}/. Nothing here builds it.")
    ci = PK.read_json(cdir / "combined_insights.json", "the ARS analysis pack (combined_insights.json)", fix)
    deck = PK.find_deck(cdir, "COMP")
    names = PK.branch_names(d)
    ti = PK.read_optional_json(d / "ti" / "ti_pack.json")
    return {"C": Pack("combined_insights.json", ci, ctx.tracer, cdir / "combined_insights.json"),
            "T": Pack("ti_pack.json", (ti or {}).get("metrics"), ctx.tracer) if ti else None,
            "names": names, "notes": PK.deck_notes(deck) if deck else {}, "deck": deck.name if deck else None}


def _fb(p, what):
    return [{"title": "ARS Companion", "text": f"Source: ARS Companion pack combined_insights.json for {what} "
                                                 f"(ODD extract, pull {p['C'].get('latest_label', default='')} data month; computed by "
                                                 f"combined_insights.compute). No Companion deck was found beside the pack, so this line is "
                                                 f"composed from the pack."}]


def _src(p, needles, what):
    return PK.sources_for(p["notes"], needles, _fb(p, what))


def _nm(p, b):
    return PK.branch_label(p["names"], b)


def build(ctx, p):
    C = p["C"]
    screens = []
    for fn in (_waves, _offers, _response, _scorecard, _migration, _five):
        s = fn(ctx, p)
        if s:
            screens.append(s)
    return {"screens": screens, "summary": None, "client_name": None}


# ----------------------------------------------------------------- 2 · where the revenue comes from
def _waves(ctx, p):
    t, C = ctx.tracer, p["C"]
    if not C.get("wave_revenue", "available"):
        return None
    waves = C.get("wave_revenue", "waves") or []
    latest = C.get("wave_revenue", "by_mailing_latest") or []
    total = C.get("wave_revenue", "latest_total")
    lab = C.get("wave_revenue", "latest_month_label")
    last = waves[-12:]
    to_date = B.bars("wave-todate", "Revenue booked to date, by mailing", [w["m"] for w in last],
                     [{"name": "Revenue to date", "values": [w["revenue"] for w in last], "color": "navy"}], "usdk",
                     sub="The twelve most recent mailings; every mailing is in the table.")
    big = sorted(latest, key=lambda x: -x[1])[:12]
    month = B.bars("wave-month", f"Where {lab} revenue came from", [x[0] for x in big],
                   [{"name": "Revenue in the month", "values": [x[1] for x in big], "color": "navy"}], "usdk",
                   sub="Booked revenue in the month by the mailing it traces to: the twelve largest mailings.",
                   drill=None)
    rows = []
    for w in waves:
        rows.append({"name": w["m"], "revenue": w["revenue"], "months": w["months"],
                     "permonth": t.derive(w["revenue"] / w["months"], "revenue over months live", w["revenue"], w["months"]) if w["months"] else None})
    tbl = B.table("wave-table", "Revenue by mailing, program to date",
                  [B.col("name", "Mailing"), B.col("revenue", "Revenue to date", "usd"), B.col("months", "Months live", "int"),
                   B.col("permonth", "Revenue a month", "usd")], list(reversed(rows)), total=None, sort={"key": None},
                  sub="Booked revenue from the workbook's mailing sheets.")
    chart = dict(to_date, drill={"table": "wave-table"})
    v = B.variants("wave-view", "Show", [
        {"key": "month", "label": f"{lab}", "blocks": [month, tbl]},
        {"key": "todate", "label": "To date", "blocks": [{"t": "drill", "chart": chart, "table": tbl}]}])
    top = max(latest, key=lambda x: x[1]) if latest else None
    n = t.derive(len(latest), "count of mailings that paid in the month") if latest else 0
    headline = (f"{lab} revenue came from {n} mailings; the {top[0]} mailing brought the most, {B.f_usd(top[1])} of {B.f_usd(total)}."
                if top else f"Revenue by mailing, through {lab}.")
    return B.screen("waves", "Where the revenue comes from", "Revenue · By mailing", headline, [v],
                    _src(p, ["Where This Month's Revenue Came From", "Revenue by Mailing", "Revenue Build by Mailing"], "revenue by mailing"), [])


def _offers(ctx, p):
    t, C = ctx.tracer, p["C"]
    if not C.get("offer_efficiency", "available"):
        return None
    ms = C.get("offer_efficiency", "mailings") or []
    if not ms:
        return None
    rows = [{"name": m["month"], "offers": m["offers"], "revenue": m["revenue"], "months": m["months"],
             "per1k": m["per_1k"], "per1kmo": m["per_1k_month"]} for m in ms]
    cols = [B.col("name", "Mailing"), B.col("offers", "Offers mailed", "int"), B.col("revenue", "Revenue", "usd"),
            B.col("months", "Months live", "int"), B.col("per1k", "Per 1,000 offers", "usd"), B.col("per1kmo", "Per 1,000 a month", "usd")]
    tbl = B.table("offer-table", "Revenue per 1,000 offers, by mailing", cols, list(reversed(rows)), sort={"key": None},
                  sub="Booked revenue over offers mailed. A mailing's revenue builds with its age, so compare the per-month column across ages.")
    chart = B.bars("offer-chart", "Revenue per 1,000 offers a month, by mailing", [r["name"] for r in rows],
                   [{"name": "Per 1,000 offers a month", "values": [r["per1kmo"] for r in rows], "color": "navy"}], "usd",
                   metrics=[{"key": "mo", "label": "A month", "fmt": "usd", "series": [{"name": "Per 1,000 offers a month", "values": [r["per1kmo"] for r in rows], "color": "navy"}]},
                            {"key": "td", "label": "To date", "fmt": "usdk", "series": [{"name": "Per 1,000 offers", "values": [r["per1k"] for r in rows], "color": "steel"}]}])
    recent = rows[-12:]
    best = max(recent, key=lambda r: r["per1kmo"])
    worst = min(recent, key=lambda r: r["per1kmo"])
    headline = (f"Per 1,000 offers a month, the {best['name']} mailing returned {B.f_usd(best['per1kmo'])}; "
                f"the {worst['name']} mailing returned {B.f_usd(worst['per1kmo'])}.")
    return B.screen("offers", "What 1,000 offers return", "Revenue · Offer efficiency", headline, [B.drill(chart, tbl)],
                    _src(p, ["Revenue per 1,000 Offers", "Offer Segments per 1,000"], "revenue per 1,000 offers"),
                    ["Compared across the twelve most recent mailings."])


def _response(ctx, p):
    t, C = ctx.tracer, p["C"]
    if not C.get("responder_control", "available"):
        return None
    r, c = C.get("responder_control", "responders"), C.get("responder_control", "control")
    did = C.get("responder_control", "did")
    bm, am = C.get("responder_control", "before_months"), C.get("responder_control", "after_months")
    chart = B.bars("resp-chart", "Monthly debit spend per account, before and after a mailing", ["Responders", "Mailed, no response"],
                   [{"name": "Before", "values": [r["before"], c["before"]], "color": "steel"},
                    {"name": "After", "values": [r["after"], c["after"]], "color": "navy"}], "usd")
    if abs(c["change_pct"]) <= 2:
        ctl = f"stayed almost flat ({B.f_usd(c['before'])} to {B.f_usd(c['after'])})"
    elif c["change_pct"] > 0:
        ctl = f"rose {B.f_pct1(c['change_pct'])} ({B.f_usd(c['before'])} to {B.f_usd(c['after'])})"
    else:
        ctl = f"fell {B.f_pct1(abs(c['change_pct']))} ({B.f_usd(c['before'])} to {B.f_usd(c['after'])})"
    headline = (f"Responders' monthly debit spend rose {B.f_pct1(r['change_pct'])} ({B.f_usd(r['before'])} to {B.f_usd(r['after'])}) "
                f"while the control {ctl}: a net {B.f_usd(did)} a month per account.")
    blocks = [chart]
    rows = C.get("responder_by_tier", "rows") or []
    if rows:
        cols = [B.col("name", "Swipe tier before the mailing"), B.col("responders", "Responders", "int"), B.col("control", "Control accounts", "int"),
                B.col("rb", "Responders before", "usd"), B.col("ra", "Responders after", "usd"),
                B.col("cb", "Control before", "usd"), B.col("ca", "Control after", "usd")]
        trs = [{"name": x["tier"], "responders": x["responders"], "control": x["control"], "rb": x.get("resp_before"), "ra": x.get("resp_after"),
                "cb": x.get("control_before"), "ca": x.get("control_after")} for x in rows]
        tbl = B.table("resp-tier-table", "The same comparison by swipe tier", cols, trs, sort={"key": None},
                      sub="Mailed accounts that responded against mailed accounts that did not, in the same tier.")
        blocks = [chart, tbl]
    note = (f"Spend is measured {bm} months before and {am} months after each mailing; the control is accounts mailed the same offer "
            f"that did not respond. A difference between the groups is an association, not proof of cause.")
    return B.screen("response", "What a response is worth", "Revenue · Response against a control", headline, blocks,
                    _src(p, ["Responders vs Mailed Non-Responders", "What a Response Is Worth", "Responders vs Their Own Segment"], "responders against a control"), [note])


# ----------------------------------------------------------------- 3 · branch performance
def _scorecard(ctx, p):
    t, C = ctx.tracer, p["C"]
    br = C.get("branch_kpis", "branches") or []
    if not br:
        return None
    tot = C.get("branch_kpis", "total") or {}
    oth = C.get("branch_kpis", "other") or {}
    win = C.get("branch_kpis", "closure_window") or []
    rows = [{"name": _nm(p, b["branch"]), "elig": b["eligible"], "take": b["take"], "rege": b["rege"], "closed": b["closed12"], "first": b["first_year"]} for b in br]
    cols = [B.col("name", "Branch"), B.col("elig", "Eligible accounts", "int"), B.col("take", "Debit take", "pct1"),
            B.col("rege", "Reg E opt-in", "pct1"), B.col("closed", "Closed, last 12 months", "pct1"), B.col("first", "Closed in first year", "pct1")]
    total = {"name": "Whole book", "elig": tot.get("eligible"), "take": tot.get("take"), "rege": tot.get("rege"),
             "closed": tot.get("closed12"), "first": tot.get("first_year")} if tot else None
    tbl = B.table("score-table", "Branch scorecard", cols, rows, total=total, sort={"key": "rege", "dir": "asc"},
                  sub="Open personal accounts eligible for ARS. Closure is over the last 12 months; first-year closure is accounts opened two years ago.")
    ser = lambda k, color: [{"name": k[1], "values": [r[k[0]] for r in rows], "color": color}]
    chart = B.bars("score-chart", "Reg E opt-in by branch", [r["name"] for r in rows], ser(("rege", "Reg E opt-in"), "navy"), "pct1", horizontal=True,
                   metrics=[{"key": "rege", "label": "Reg E opt-in", "fmt": "pct1", "series": ser(("rege", "Reg E opt-in"), "navy")},
                            {"key": "take", "label": "Debit take", "fmt": "pct1", "series": ser(("take", "Debit take"), "steel")},
                            {"key": "closed", "label": "Closed", "fmt": "pct1", "series": ser(("closed", "Closed in 12 months"), "orange")},
                            {"key": "first", "label": "First-year closure", "fmt": "pct1", "series": ser(("first", "Closed in first year"), "orange")}])
    lo = min(rows, key=lambda r: r["rege"])
    hi = max(rows, key=lambda r: r["rege"])
    headline = (f"Reg E opt-in runs from {B.f_pct1(lo['rege'])} at {lo['name']} to {B.f_pct1(hi['rege'])} at {hi['name']}, "
                f"against {B.f_pct1(tot['rege'])} for the book.") if tot else f"Branch by branch: take, Reg E and closures."
    notes = []
    if oth.get("branch"):
        notes.append(f"{p['C'].get('branch_kpis', 'other_count')} smaller branches are rolled up in the deck's Branch Scorecard and are left out here.")
    quad = B.scatter("score-quadrant", "Branches: debit take against Reg E opt-in", [{"name": r["name"], "x": r["take"], "y": r["rege"], "size": r["elig"]} for r in rows],
                     "Debit take", "Reg E opt-in", "pct1", "pct1", sub="Each branch sized by its eligible accounts; the shaded corner is below the median on both.",
                     slabel="eligible accounts")
    main = B.variants("score-view", "View", [{"key": "bars", "label": "By branch", "blocks": [B.drill(chart, tbl)]},
                                             {"key": "quadrant", "label": "Take and Reg E", "blocks": [quad]}]) if len(rows) >= 4 else B.drill(chart, tbl)
    return B.screen("scorecard", "Branch scorecard", "Branches · Who to coach", headline, [main],
                    _src(p, ["Branch Scorecard", "Take Rate and Reg E Opt-In by Branch", "Where Reg E Opt-In Lags"], "branch performance"), notes)


# ----------------------------------------------------------------- 4 · member behavior
def _migration(ctx, p):
    t, C = ctx.tracer, p["C"]
    if not C.get("tier_migration", "available"):
        return None
    tiers = C.get("tier_migration", "tiers")
    mx = C.get("tier_migration", "matrix")
    up, down, same = C.get("tier_migration", "moved_up"), C.get("tier_migration", "moved_down"), C.get("tier_migration", "same")
    span = C.get("tier_migration", "span")
    pu, pd = C.get("tier_migration", "pct_up"), C.get("tier_migration", "pct_down")
    then, now = C.get("tier_migration", "then_window"), C.get("tier_migration", "now_window")
    vals = [[x for x in r[1:]] for r in mx]
    mat = B.matrix("mig", "Where accounts started and where they are now", [r[0] for r in mx], tiers, vals, "int",
                   sub=f"Card-holding accounts. Swipe tier a year ago ({then[0]} to {then[1]}) down the side, tier now ({now[0]} to {now[1]}) across the top.")
    mv = B.bars("mig-move", "Accounts by direction", ["Moved up", "Same tier", "Moved down"],
                [{"name": "Accounts", "values": [up, same, down], "color": "navy"}], "int")
    headline = f"{B.f_pct1(pu)} of card-holding accounts moved up a swipe tier in {span} months and {B.f_pct1(pd)} moved down."
    return B.screen("migration", "Swipe tier migration", "Member behavior · Tier movement", headline, [mat, mv],
                    _src(p, ["Swipe Tier Migration", "Tier Movement by Response"], "swipe tier migration"), [])


# ----------------------------------------------------------------- 7 · what it is worth next
def _five(ctx, p):
    t, C = ctx.tracer, p["C"]
    if not C.get("sizing", "available"):
        return None
    pts = C.get("sizing", "points")
    ta, ty = C.get("sizing", "take_accounts"), C.get("sizing", "take_annual")
    ra, th = C.get("sizing", "rege_accounts"), C.get("sizing", "take_headroom")
    now = C.get("sizing", "take_now")
    pcm = C.get("sizing", "per_card_month")
    items = [B.kpi(f"{B.f_int(pts)} more points of debit take", ta, "int", sub="Cards", hot=True),
             B.kpi("Interchange a year", ty, "usd", sub=f"At ${pcm:.2f} a card a month"),
             B.kpi(f"{B.f_int(pts)} more points of Reg E opt-in", ra, "int", sub="Opt-ins")]
    blocks = [B.kpis(items)]
    sentence = f"Five points of debit take is {B.f_int(ta)} more cards and {B.f_usdk(ty)} a year; five points of Reg E opt-in is {B.f_int(ra)} more opt-ins."
    T = p.get("T")
    if T is not None and T.has("value_per_optin"):
        vo = T.get("value_per_optin")
        dol = t.derive(ra * vo, "Reg E opt-ins times the annual value of an opt-in", ra, vo)
        items.append(B.kpi("Reg E value a year", dol, "usdk", sub=f"At {B.f_usd(vo)} per opt-in a year"))
        sentence = (f"Five points of debit take is {B.f_int(ta)} more cards and {B.f_usdk(ty)} a year; five points of Reg E opt-in is "
                    f"{B.f_int(ra)} more opt-ins and {B.f_usdk(dol)} a year.")
    chart = B.bars("five-chart", "Where the book stands", ["Debit take", "Reg E opt-in"],
                   [{"name": "Now", "values": [now, C.get("sizing", "rege_now")], "color": "navy"}], "pct1")
    blocks.append(chart)
    notes = [f"Debit take is already {B.f_pct1(now)}, so the headroom is {B.f_pct1(th)} points; Reg E opt-in has far more room."]
    return B.screen("five-points", "What five points would be worth", "What it is worth · Sizing", sentence, blocks,
                    _src(p, ["What Five Points Would Be Worth", "What a Card and an Opt-In Earn"], "sizing five points"), notes)
