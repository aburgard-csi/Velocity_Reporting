#!/usr/bin/env python3
"""ars.py — the ARS Executive Review as screens, read from the pack a deck build leaves behind.

Reads `Build Artifacts/launcher/<period>/<id>/`: `metrics.json` (metrics_gen: the ODD), `base.json`
(the workbook's financials), `lift.json` (the Lift Matrix) and `oddd/oddd_metrics.json`. The P&L, the
profitability ratio and the Lift Matrix example are the DECK'S OWN functions
(`revenue_guarantee_slide.guarantee` / `pnl` / `ratio_text`, `render_lift.example_move`), so the page
and the deck cannot state different figures. Every number goes through the Tracer.

Screens (each mirrors deck slides, whose notes are its Sources):
    summary  financial  lift  mailings  take  rege  usage
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))
ARS_PIPE = os.path.join(BUILD, "ars_pipeline")
for _p in (BUILD, ARS_PIPE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import month_complete as MC                                   # noqa: E402
from review_page import blocks as B                           # noqa: E402
from review_page import packs as PK                           # noqa: E402
from review_page.common import usable_series, left_out_text, parse_date   # noqa: E402
from review_page.trace import Pack, movement, change_pct      # noqa: E402

KEY, LABEL = "ars", "ARS"


# ----------------------------------------------------------------- load
def load(ctx):
    d = PK.launcher_dir(ctx.client, ctx.period, ctx.root)
    fix = PK.build_hint(ctx.client, ctx.period)
    t = ctx.tracer
    m = PK.read_json(d / "metrics.json", "the metrics pack (metrics.json)", fix)
    b = PK.read_json(d / "base.json", "the workbook pack (base.json)", fix)
    lift = oddd = None
    try:
        lift = PK.read_json(d / "lift.json", "the Lift Matrix pack (lift.json)", fix)
    except PK.PackMissing:
        pass
    try:
        oddd = PK.read_json(d / "oddd" / "oddd_metrics.json", "the ODD pack", fix)
    except PK.PackMissing:
        pass
    deck = PK.find_deck(d, "ARS")
    return {"M": Pack("metrics.json", m, t, d / "metrics.json"),
            "B": Pack("base.json", b, t, d / "base.json"),
            "L": Pack("lift.json", lift, t, d / "lift.json") if lift else None,
            "O": Pack("oddd_metrics.json", oddd, t) if oddd else None,
            "notes": PK.deck_notes(deck) if deck else {},
            "deck": deck.name if deck else None, "dir": d}


# ----------------------------------------------------------------- helpers
def _src(p, needles, fallback_text, title):
    return PK.sources_for(p["notes"], needles, [{"title": title, "text": fallback_text}])


def _fallback(p, what):
    m = p["M"].data
    odd = (p["O"].data.get("source_file") if p["O"] else None) or "the client's ODD extract"
    return (f"Source: {what}. ODD extract {odd}; ARS workbook figures from base.json "
            f"({p['B'].data.get('data_label', '')}). No deck was found beside the pack, so this line is "
            f"composed from the pack rather than copied from a slide's notes.")


def _name(p):
    return p["B"].get("client") or "The client"


def _share(t, part, whole, label):
    if not whole:
        return None
    return t.derive(100.0 * part / whole, label, part, whole)


def _round_cat(cats):
    return [str(c) for c in cats]


# ----------------------------------------------------------------- screens
def build(ctx, p):
    t = ctx.tracer
    M, Bp, L, O = p["M"], p["B"], p["L"], p["O"]
    name = _name(p)
    import revenue_guarantee_slide as RG
    base = Bp.data
    # let the ledger know every figure the deck's own P&L functions are about to combine
    Bp.get("actuals")
    for k in ("ltd_revenue", "ltd_costs", "cur_revenue", "cur_costs", "cur_profit", "ltd_profit",
              "profitability", "months", "mailings", "monthly_rev_last12", "swipespend_36"):
        Bp.get(k)
    g = RG.guarantee(base)
    ratio = RG.ratio_of(base)
    if ratio is not None:
        t.derive(ratio, "revenue_guarantee_slide.ratio_of(base.json): revenue / cost over the Actuals months",
                 Bp.get("ltd_revenue"))
    screens = []
    screens.append(_summary(ctx, p, g, ratio, RG))
    screens.append(_financial(ctx, p, g, ratio, RG))
    if L is not None:
        screens.append(_lift(ctx, p))
    screens.append(_mailings(ctx, p))
    screens.append(_take(ctx, p))
    screens.append(_rege(ctx, p))
    screens.append(_usage(ctx, p))
    ps = _peers(ctx, p)
    if ps:
        screens.append(ps)
    s0 = screens[0]
    summary = {"headline": s0["headline"],
               "kpis": [dict(k, go="ars:summary") for k in s0["blocks"][0]["items"][:3]],
               "open": "ars:summary"}
    return {"screens": screens, "summary": summary, "client_name": name}


def _peers(ctx, p):
    """'How you compare': the client against the other ARS clients, anonymously (review_page/peers.py). The client's own
    figures are read from the packs this page already holds, the peers' from the packs their own builds left."""
    from review_page import peer_pool, peers
    try:
        pc = peer_pool.PeerCtx(ctx.client, ctx.period, ctx.root, own={"metrics": p["M"].data, "base": p["B"].data})
        coll = peer_pool.collect_ars(pc)
    except Exception:
        return None
    return peers.peers_screen(ctx.tracer, "ARS", "ARS", coll, peer_pool.ARS_METRICS, pull_dates=coll["pull"],
                              extra_notes=["Response rate is the deck's: responders over offers sent to personal accounts. Responder spend compares "
                                           "the 3 months before a mailing with the 6 months after, and only packs built on those windows count."])


def _summary(ctx, p, g, ratio, RG):
    t = ctx.tracer
    M, Bp, O = p["M"], p["B"], p["O"]
    name = _name(p)
    ltd_profit = Bp.get("ltd_profit")
    month = Bp.get("data_label", default="")
    month = month.replace(" Data", "")
    elig = O.get("funnel", "eligible") if O else None
    if elig is None:
        elig = M.get("n_eligible")
    last12 = Bp.get("monthly_rev_last12") or []
    rows, res = MC.complete_rows(last12, 1, "monthly incremental revenue", min_volume=0)
    left = MC.excluded_months(res)
    mood = []
    items = [
        B.kpi("Profitability, program to date", ratio, "ratio", sub="Revenue over cost since launch", hot=True),
        B.kpi("Incremental profit, program to date", ltd_profit, "usd",
              sub=f"{B.f_usd(Bp.get('ltd_revenue'))} revenue, {B.f_usd(abs(Bp.get('ltd_costs')))} cost"),
        B.kpi(f"Revenue, {month}", Bp.get("cur_revenue"), "usd",
              sub=f"{B.f_usd(Bp.get('cur_profit'))} profit that month"),
        B.kpi("Debit take rate, whole book", M.get("take_hist_pct"), "pct1",
              sub=f"{B.f_pct1(M.get('take_new_pct'))} on accounts opened in the last 12 months", go="ars:take"),
        B.kpi("Reg E opt-in, personal accounts", M.get("rege_pct"), "pct1",
              sub=f"{B.f_pct1(M.get('rege_new_pct'))} on accounts opened in the last 12 months", go="ars:rege"),
        B.kpi(f"Latest mailing, {M.get('latest_mailing')}", M.get("latest_resprate"), "pct1",
              sub=f"{B.f_int(M.get('latest_responders'))} of {B.f_int(M.get('latest_mailed'))} offers answered", go="ars:mailings"),
    ]
    if elig:
        items.append(B.kpi("ARS-eligible accounts", elig, "int", sub="Open accounts the program can reach"))
    chart = B.bars("rev12", "Incremental revenue by month, last 12 months",
                   [r[0] for r in rows], [{"name": "Incremental revenue", "values": [r[1] for r in rows], "color": "navy"}],
                   "usdk", highlight=len(rows) - 1 if rows else None)
    headline = (f"{name}'s ARS program has returned {B.f_usd(ltd_profit)} in incremental profit to date, "
                f"a {RG.ratio_text(ratio)} profitability ratio.")
    notes = [f"{left_s}" for left_s in ([f"{', '.join(left)} left out of the monthly chart as incomplete."] if left else [])]
    srcs = _src(p, ["Program Overview", "ARS Key Takeaways"], _fallback(p, "program overview"), "Program Overview")
    return B.screen("summary", "Summary", "ARS · Program overview", headline, [B.kpis(items), chart], srcs, notes)


def _financial(ctx, p, g, ratio, RG):
    t = ctx.tracer
    Bp = p["B"]
    name = _name(p)
    pn = RG.pnl(g)
    for _l, vals, _k in pn["rows"]:
        for v in vals:
            if isinstance(v, (int, float)):
                t.derive(v, "revenue_guarantee_slide.pnl(): an Actuals column sum", Bp.get("ltd_revenue"))
    cols = [B.col("label", "")] + [B.col(f"c{i}", c, "usd") for i, c in enumerate(pn["columns"])]
    rows = []
    for label, vals, kind in pn["rows"]:
        r = {"label": label, "kind": kind, "fmt": "ratio" if kind == "ratio" else "usd"}
        for i, v in enumerate(vals):
            r[f"c{i}"] = v
        rows.append(r)
    tbl = B.table("pnl", "Program P&L", cols, rows, search=False, key="label", kind="pnl",
                  sub="Incremental revenue less the program's cost lines, from the workbook's Actuals tab. Costs in parentheses.")
    months = g["months"]
    shown = months[-15:]
    chart = B.bars("pnl-chart", "Revenue and cost by month", [m[0] for m in shown],
                   [{"name": "Incremental revenue", "values": [m[1] for m in shown], "color": "navy"},
                    {"name": "Cost", "values": [m[2] for m in shown], "color": "steel"}], "usdk")
    notes = []
    if g.get("left_out"):
        notes.append(f"{', '.join(g['left_out'])} left out of the run rate as incomplete.")
    if pn.get("dropped"):
        notes.append(f"Cost lines at zero for the whole program are not shown: {', '.join(pn['dropped'])}.")
    bridges = []
    for i, c in enumerate(pn["columns"]):                      # revenue, less each cost line, is the profit: one bridge per column of the P&L
        rev = profit = tot = None
        lines = []
        for label, vals, kind in pn["rows"]:
            v = vals[i] if i < len(vals) else None
            if v is None:
                continue
            if kind == "revenue":
                rev = {"label": label, "value": v, "kind": "total"}
            elif kind == "line":
                lines.append({"label": label, "value": t.derive(-v, "a P&L cost line drawn as a step down", v), "kind": "delta"})
            elif kind == "total":
                tot = {"label": label, "value": t.derive(-v, "the P&L total cost drawn as a step down", v), "kind": "delta"}
            elif kind == "profit":
                profit = {"label": label, "value": v, "kind": "total"}
        if rev and profit:
            bridges.append({"key": f"c{i}", "label": c, "steps": [rev] + (lines or ([tot] if tot else [])) + [profit]})
    bridge = B.waterfall("pnl-bridge", "From revenue to profit", bridges, "usdk",
                         sub="Incremental revenue less each cost line is the program's incremental profit.") if bridges else None
    first = B.variants("pnl-view", "Chart", [{"key": "month", "label": "By month", "blocks": [chart]},
                                              {"key": "bridge", "label": "Profit bridge", "blocks": [bridge]}]) if bridge else chart
    blocks = [B.kpis([
        B.kpi("Profitability, program to date", ratio, "ratio", hot=True,
              sub="Guaranteed minimum is 2 : 1"),
        B.kpi("Incremental revenue", g["revenue"], "usd", sub="Program to date"),
        B.kpi("Total cost", g["cost"], "usd", sub="Program to date"),
    ]), first, tbl]
    if g.get("met") and g.get("surplus") is not None:
        t.derive(g["minimum"], "revenue_guarantee_slide.guarantee: 2 x program cost", g["cost"])
        t.derive(g["surplus"], "revenue_guarantee_slide.guarantee: revenue less the guaranteed minimum", g["revenue"])
        headline = (f"Revenue is {RG.ratio_text(ratio)} cost, {B.f_usdk(g['surplus'])} above the "
                    f"{B.f_usdk(g['minimum'])} the 2 : 1 guaranteed minimum calls for.")
    elif g.get("gap") is not None:
        t.derive(g["minimum"], "revenue_guarantee_slide.guarantee: 2 x program cost", g["cost"])
        t.derive(g["gap"], "revenue_guarantee_slide.guarantee: guaranteed minimum less revenue", g["cost"])
        headline = (f"Revenue is {RG.ratio_text(ratio)} cost; it is {B.f_usdk(g['gap'])} short of the "
                    f"{B.f_usdk(g['minimum'])} the 2 : 1 guaranteed minimum calls for.")
    else:
        headline = f"{name}'s program P&L, from the workbook's Actuals tab."
    srcs = _src(p, ["ARS Financial Performance", "Revenue Guarantee", "Program Overview"],
                _fallback(p, "workbook Actuals tab"), "ARS Financial Performance")
    return B.screen("financial", "Financial performance", "ARS · Program P&L", headline, blocks, srcs, notes)


def _lift(ctx, p):
    t = ctx.tracer
    L = p["L"]
    import render_lift as RL
    data = L.data
    rows, cols = L.get("matrix_rows"), L.get("matrix_cols")
    L.get("revseg")
    tiers = RL.tiers(data)
    ex = RL.example_move(data)
    from_l, to_l, add = RL.tier_label(ex[0]), RL.tier_label(ex[1]), ex[4]
    rev = {n: (d, v) for n, d, v in data["revseg"]}
    ex_from_val, ex_to_val = rev[ex[0]][1], rev[ex[1]][1]
    mvalues = [[r[1 + j] if isinstance(r[1 + j], (int, float)) else None for j in range(len(cols))] for r in rows]
    mat = B.matrix("lift", "Monthly value added by moving up a tier",
                   [RL.tier_label(r[0]) for r in rows], [RL.tier_label(c) for c in cols], mvalues, "usd2",
                   sub="Starting tier down the side, tier now across the top. A dash is a move that cannot happen.")
    ch = B.bars("lift-value", "Monthly value per card account, by swipe tier",
                [RL.tier_label(n) for n, _d, _v in tiers],
                [{"name": "Value per account a month", "values": [v for _n, _d, v in tiers], "color": "navy"}], "usd2",
                horizontal=False,
                metrics=[{"key": "value", "label": "Value a month", "fmt": "usd2",
                          "series": [{"name": "Value per account a month", "values": [v for _n, _d, v in tiers], "color": "navy"}]},
                         {"key": "share", "label": "Share of card accounts", "fmt": "frac1",
                          "series": [{"name": "Share of card accounts", "values": [d for _n, d, _v in tiers], "color": "orange"}]}])
    headline = (f"A {from_l} account (${ex_from_val:,.2f} a month) that moves to {to_l} "
                f"(${ex_to_val:,.2f} a month) adds ${add:,.2f} a month.")
    notes = []
    if L.get("in_window") is False or L.get("data_past_end"):
        notes.append("The workbook's Lift Matrix window does not cover the data month; check the matrix before presenting.")
    srcs = _src(p, ["ARS Revenue Lift Matrix"], _fallback(p, "ARS workbook, Lift Matrix MM tab"), "ARS Revenue Lift Matrix")
    return B.screen("lift", "Lift Matrix", "ARS · Revenue by swipe tier", headline, [mat, ch], srcs, notes)


def _mailings(ctx, p):
    t = ctx.tracer
    M = p["M"]
    ms = M.get("mail_summary") or []
    tot = M.get("mail_summary_total") or []
    chron = list(reversed(ms))
    ch = B.bars("mail-rate", "Response rate by mailing", [r[0] for r in chron],
                [{"name": "Overall", "values": [r[5] for r in chron], "color": "navy"},
                 {"name": "Non-User 5+ offer", "values": [r[3] for r in chron], "color": "orange"},
                 {"name": "Threshold offers", "values": [r[4] for r in chron], "color": "steel"}], "pct1",
                metrics=[{"key": "all", "label": "Overall", "fmt": "pct1",
                          "series": [{"name": "Overall", "values": [r[5] for r in chron], "color": "navy"}]},
                         {"key": "offers", "label": "By offer", "fmt": "pct1",
                          "series": [{"name": "Non-User 5+ offer", "values": [r[3] for r in chron], "color": "orange"},
                                     {"name": "Threshold offers", "values": [r[4] for r in chron], "color": "steel"}]},
                         {"key": "resp", "label": "Responders", "fmt": "int",
                          "series": [{"name": "Responders", "values": [r[2] for r in chron], "color": "navy"}]}])
    cols = [B.col("name", "Mailing"), B.col("mailed", "Offers mailed", "int"), B.col("resp", "Responders", "int"),
            B.col("nu", "Non-User 5+ rate", "pct1"), B.col("th", "Threshold rate", "pct1"), B.col("rate", "Response rate", "pct1")]
    rows = [{"name": r[0], "mailed": r[1], "resp": r[2], "nu": r[3], "th": r[4], "rate": r[5]} for r in ms]
    total = None
    if len(tot) == 5:
        total = {"name": f"Last {len(ms)} mailings", "mailed": tot[0], "resp": tot[1], "nu": tot[2], "th": tot[3], "rate": tot[4]}
        t.derive(len(ms), "count of mailings in mail_summary", *[])
    tbl = B.table("mail", "Mailing response", cols, rows, total=total, search=False, sort={"key": None})
    mv = M.get("movement") or []
    mvch = B.bars("mail-move", f"What responders did after the {M.get('latest_mailing')} mailing",
                  [m[0] for m in mv], [{"name": "Responders", "values": [m[1] for m in mv], "color": "navy"}], "int")
    inprog = M.get("mail_in_progress") or []
    notes = []
    for lab, n in inprog:
        notes.append(f"The {lab} mailing ({B.f_int(n)} offers) is in progress; no response is measured yet and it is not in any rate.")
    headline = (f"The {M.get('latest_mailing')} mailing drew a {B.f_pct1(M.get('latest_resprate'))} response "
                f"({B.f_int(M.get('latest_responders'))} of {B.f_int(M.get('latest_mailed'))}), against "
                f"{B.f_pct1(tot[4])} across the last {len(ms)} mailings." if len(tot) == 5 else
                f"The {M.get('latest_mailing')} mailing reached {B.f_int(M.get('latest_mailed'))} accounts.")
    srcs = _src(p, ["Mailing Response Summary", "ARS Response", "Mailing Response Ranking"],
                _fallback(p, "ODD mailing and response fields"), "Mailing Response Summary")
    return B.screen("mailings", "Mailings", "ARS · Offers and response", headline, [ch, mvch, tbl], srcs, notes)


def _branch_note(t, listed_total, pool, what):
    if pool and listed_total is not None and pool > listed_total:
        rest = t.derive(pool - listed_total, f"{what}: pool less listed branches", pool, listed_total)
        return (f"{B.f_int(rest)} of the {B.f_int(pool)} accounts sit at branches with too few accounts to list, "
                f"as on the deck's branch slides.")
    return None


def _take(ctx, p):
    t = ctx.tracer
    M = p["M"]
    tb = M.get("take_branch") or []
    mon = M.get("take_branch_monthly") or []
    months = M.get("take_months") or []
    M.get("take_col_totals")
    by_month = {r[0]: r[1:1 + len(months)] for r in mon}
    cols = [B.col("name", "Branch"), B.col("cards", "New cards", "int"), B.col("elig", "New eligible accounts", "int"),
            B.col("pct", "Take rate", "pct0")] + [B.col(f"m{i}", f"{m} cards", "int") for i, m in enumerate(months)]
    rows = []
    for br, cards, elig, pct in tb:
        r = {"name": br, "cards": cards, "elig": elig, "pct": pct}
        for i, v in enumerate(by_month.get(br, [])):
            r[f"m{i}"] = v
        rows.append(r)
    lc = sum(r[1] for r in tb)
    le = sum(r[2] for r in tb)
    total = None
    if tb:
        t.derive(lc, "sum of listed branches' new cards", *[x[1] for x in tb][:1])
        t.derive(le, "sum of listed branches' new eligible accounts", *[x[2] for x in tb][:1])
        tp = _share(t, lc, le, "listed branches' take rate")
        total = {"name": "Listed branches", "cards": lc, "elig": le, "pct": tp}
        for i, v in enumerate(M.get("take_col_totals") or []):
            total[f"m{i}"] = v
    tbl = B.table("take-table", "Debit card take rate by branch", cols, rows, total=total, sort={"key": "elig", "dir": "desc"},
                  sub="Accounts opened in the last 12 months that are eligible for ARS; a branch is listed once it has enough of them.")
    cats = [r[0] for r in tb]
    chart = B.bars("take-chart", "Debit card take rate by branch", cats,
                   [{"name": "Take rate", "values": [r[3] for r in tb], "color": "navy"}], "pct0", horizontal=True,
                   metrics=[{"key": "pct", "label": "Take rate", "fmt": "pct0",
                             "series": [{"name": "Take rate", "values": [r[3] for r in tb], "color": "navy"}]},
                            {"key": "elig", "label": "New accounts", "fmt": "int",
                             "series": [{"name": "New eligible accounts", "values": [r[2] for r in tb], "color": "steel"},
                                        {"name": "With a debit card", "values": [r[1] for r in tb], "color": "navy"}]}])
    note = _branch_note(t, le, M.get("take_new_total"), "take rate")
    tn, th = M.get("take_new_pct"), M.get("take_hist_pct")
    same = abs(tn - th) < 0.05
    headline = (f"{B.f_pct1(tn)} of the {B.f_int(M.get('take_new_total'))} accounts opened in the last 12 months "
                f"hold a debit card, " + (f"the same as across the whole book ({B.f_pct1(th)})." if same
                                          else f"against {B.f_pct1(th)} across the whole book."))
    srcs = _src(p, ["Take Rate by Branch", "Debit Card Review", "Take Rate"],
                _fallback(p, "ODD debit take rate by branch"), "12-Month Take Rate by Branch")
    return B.screen("take", "Debit take rate", "ARS · By branch", headline, [B.drill(chart, tbl)], srcs,
                    [n for n in [note] if n])


def _rege(ctx, p):
    t = ctx.tracer
    M = p["M"]
    win = M.get("rege_new_window") or []
    bt = M.get("rege_branch_table") or []
    bt_tot = M.get("rege_branch_table_total") or []
    cols_n = [B.col("name", "Branch"), B.col("in", "Opted in", "int"), B.col("out", "Opted out", "int"),
              B.col("none", "No election", "int"), B.col("total", "Accounts", "int"), B.col("pct", "Opt-in rate", "pct0")]
    rows_n = [{"name": r[0], "in": r[1], "out": r[2], "none": r[3], "total": r[4], "pct": r[5]} for r in bt]
    tot_n = None
    if len(bt_tot) == 4:
        tot_n = {"name": "Listed branches", "in": bt_tot[0], "out": bt_tot[1], "none": bt_tot[2], "total": bt_tot[3],
                 "pct": _share(t, bt_tot[0], bt_tot[3], "listed branches' Reg E opt-in rate")}
    tbl_n = B.table("rege-new-table", "Reg E by branch, accounts opened in the last 12 months", cols_n, rows_n,
                    total=tot_n, sort={"key": "pct", "dir": "desc"},
                    sub="Personal accounts with a debit card, opened in the window and still open.")
    ch_n = B.bars("rege-new-chart", "Reg E opt-in rate by branch", [r[0] for r in bt],
                  [{"name": "Opt-in rate", "values": [r[5] for r in bt], "color": "navy"}], "pct0", horizontal=True,
                  metrics=[{"key": "pct", "label": "Opt-in rate", "fmt": "pct0",
                            "series": [{"name": "Opt-in rate", "values": [r[5] for r in bt], "color": "navy"}]},
                           {"key": "count", "label": "Opted in and out", "fmt": "int",
                            "series": [{"name": "Opted in", "values": [r[1] for r in bt], "color": "navy"},
                                       {"name": "Opted out", "values": [r[2] for r in bt], "color": "steel"}]}])
    al = M.get("rege_branch") or []
    rows_a = []
    for br, inn, tot_, pct in al:
        rows_a.append({"name": br, "in": inn, "out": t.derive(tot_ - inn, "accounts less opted in", tot_, inn),
                       "total": tot_, "pct": pct})
    cols_a = [B.col("name", "Branch"), B.col("in", "Opted in", "int"), B.col("out", "Not opted in", "int"),
              B.col("total", "Accounts", "int"), B.col("pct", "Opt-in rate", "pct0")]
    tot_a = None
    if al:
        si = t.derive(sum(r[1] for r in al), "listed branches' opted in", al[0][1])
        st = t.derive(sum(r[2] for r in al), "listed branches' accounts", al[0][2])
        tot_a = {"name": "Listed branches", "in": si, "out": t.derive(st - si, "listed not opted in", st, si),
                 "total": st, "pct": _share(t, si, st, "listed branches' opt-in rate")}
    tbl_a = B.table("rege-all-table", "Reg E by branch, all open personal accounts with a debit card", cols_a, rows_a,
                    total=tot_a, sort={"key": "pct", "dir": "desc"},
                    sub="Opt-in status as of the data month (point in time).")
    ch_a = B.bars("rege-all-chart", "Reg E opt-in rate by branch", [r[0] for r in al],
                  [{"name": "Opt-in rate", "values": [r[3] for r in al], "color": "navy"}], "pct0", horizontal=True)
    window = f"from {win[0]} to {win[1]}" if len(win) >= 2 else "in the last 12 months"
    notes = []
    n1 = _branch_note(t, tot_n["total"] if tot_n else None, M.get("rege_new_pool"), "Reg E (new)")
    if n1:
        notes.append(n1)
    v = B.variants("rege-cohort", "Accounts", [
        {"key": "new", "label": f"Opened {window}", "blocks": [B.drill(ch_n, tbl_n)]},
        {"key": "all", "label": "All open personal accounts", "blocks": [B.drill(ch_a, tbl_a)]}])
    headline = (f"{B.f_pct1(M.get('rege_new_pct'))} of personal accounts opened {window} opted in to Reg E, "
                f"against {B.f_pct1(M.get('rege_pct'))} of all open personal accounts with a debit card.")
    srcs = _src(p, ["Reg E Opt-In by Branch", "Reg E Review", "Reg E Opt-In"],
                _fallback(p, "ODD Reg E opt-in by branch"), "Reg E Opt-In by Branch")
    return B.screen("rege", "Reg E opt-in", "ARS · By branch", headline, [v], srcs, notes)


def _usage(ctx, p):
    t = ctx.tracer
    M, Bp = p["M"], p["B"]
    st = M.get("swipe_tier") or []
    tt = M.get("swipe_tier_total") or []
    w3 = M.get("w3_label")
    cols = [B.col("name", "Swipe tier"), B.col("accts", "Accounts", "int"), B.col("acctp", "% of accounts", "pct1"),
            B.col("swipes", "Swipes", "int"), B.col("spend", "Spend", "usd"), B.col("spendp", "% of spend", "pct1"),
            B.col("nsf", "NSF/OD items", "int")]
    rows = []
    for seg, a, sw, sp, ns in st:
        rows.append({"name": seg, "accts": a, "acctp": _share(t, a, tt[0], "tier share of accounts"), "swipes": sw,
                     "spend": sp, "spendp": _share(t, sp, tt[2], "tier share of spend"), "nsf": ns})
    total = {"name": "All accounts", "accts": tt[0], "acctp": 100.0, "swipes": tt[1], "spend": tt[2], "spendp": 100.0, "nsf": tt[3]} if len(tt) == 4 else None
    if total:
        t.see(100.0)
    tbl = B.table("usage-table", "Debit use by swipe tier", cols, rows, total=total, search=False, sort={"key": None},
                  sub=f"Accounts, swipes, spend and NSF/OD items by monthly swipe tier, over {w3}." if w3 else "Accounts, swipes, spend and NSF/OD items by monthly swipe tier.")
    ch = B.bars("usage-chart", "Spend by swipe tier", [r[0] for r in st],
                [{"name": "Spend", "values": [r[3] for r in st], "color": "navy"}], "usdk",
                metrics=[{"key": "spend", "label": "Spend", "fmt": "usdk",
                          "series": [{"name": "Spend", "values": [r[3] for r in st], "color": "navy"}]},
                         {"key": "accts", "label": "Accounts", "fmt": "int",
                          "series": [{"name": "Accounts", "values": [r[1] for r in st], "color": "steel"}]},
                         {"key": "nsf", "label": "NSF/OD items", "fmt": "int",
                          "series": [{"name": "NSF/OD items", "values": [r[4] for r in st], "color": "orange"}]}])
    # NSF/OD over time, complete months only
    series = M.get("nsf_series") or []
    toks = [r[0] for r in series]
    items = [r[1] for r in series]
    as_of = parse_date((M.get("month_completeness") or {}).get("pull_date"))
    keep, excl = usable_series(toks, items, as_of=as_of, measure="NSF/OD items")
    pts = [(tok, v) for tok, v, k in zip(toks, items, keep) if k]
    # the line keeps the calendar: a left-out month is a gap, not a zero
    line_vals = [(v if k else None) for v, k in zip(items, keep)]
    ln = B.line("nsf-line", "NSF/OD items by month", toks,
                [{"name": "NSF/OD items", "values": line_vals, "color": "orange"}], "int",
                sub="A month left out as incomplete is a gap in the line.")
    # year to date against the prior year to date; every month of both windows must be usable
    yoy_sent = None
    cur_year = toks[-1].split()[-1] if toks else None
    ok_months = {tok: v for tok, v, k in zip(toks, items, keep) if k}
    if toks and cur_year:
        last_tok = [tk for tk, k in zip(toks, keep) if k][-1] if any(keep) else None
        if last_tok:
            mon_names = [tk.split()[0] for tk in toks if tk.split()[-1] == last_tok.split()[-1]]
            upto = mon_names[: mon_names.index(last_tok.split()[0]) + 1]
            yr = int(last_tok.split()[-1])
            cur_t = [f"{m} {yr}" for m in upto]
            pri_t = [f"{m} {yr - 1}" for m in upto]
            def _find(lbl):
                m, y = lbl.split()
                return next((tk for tk in toks if tk.split()[0] == m and (tk.split()[-1] in (str(y), str(y)[-2:]))), None)
            cur_k = [_find(x) for x in cur_t]
            pri_k = [_find(x) for x in pri_t]
            window = f"{upto[0]}–{upto[-1]} {str(yr - 1)[-2:]} → {upto[0]}–{upto[-1]} {str(yr)[-2:]}"
            if not all(cur_k + pri_k):
                yoy_sent = ("NSF/OD items year to date against last year reads n/a: the series does not carry every "
                            "month of both windows.")
            elif not all(k in ok_months for k in cur_k + pri_k):
                yoy_sent = ("NSF/OD items year to date against last year reads n/a: a month in one of the two "
                            "windows is left out as incomplete.")
            else:
                a = t.derive(sum(ok_months[k] for k in pri_k), "NSF/OD items, prior year to date", *[ok_months[pri_k[0]]])
                b = t.derive(sum(ok_months[k] for k in cur_k), "NSF/OD items, current year to date", *[ok_months[cur_k[0]]])
                pc = change_pct(a, b)
                t.derive(pc, "year-to-date change", a, b)
                yoy_sent = movement("NSF/OD items year to date", a, b, B.f_int)
    notes = []
    s = left_out_text(excl, "NSF/OD activity")
    if s:
        notes.append(s)
    if yoy_sent:
        notes.append(yoy_sent)
    spend_rows, sres = MC.complete_rows(Bp.get("swipespend_36") or [], 1, "$M debit spend", min_volume=0)
    sp_ln = B.line("spend-line", "Debit spend by month ($ millions, workbook Key Trends)", [r[0] for r in spend_rows],
                   [{"name": "Debit spend ($M)", "values": [r[1] for r in spend_rows], "color": "navy"}], "dec1")
    sl = MC.excluded_months(sres)
    if sl:
        notes.append(f"{', '.join(sl)} left out of the spend line as incomplete.")
    heavy = rows[-1] if rows else None
    headline = (f"Accounts in the {rows[-1]['name']} swipe tier are {B.f_pct1(rows[-1]['acctp'])} of accounts "
                f"and {B.f_pct1(rows[-1]['spendp'])} of spend." if rows and len(tt) == 4 else "Debit use by swipe tier.")
    srcs = _src(p, ["Debit Usage Segmentation", "Overall Debit Swipes", "NSF/OD Activity"],
                _fallback(p, "ODD swipes, spend and NSF/OD by tier and month"), "Debit Usage Segmentation by Swipe Tier")
    return B.screen("usage", "Debit use and NSF/OD", "ARS · Swipes, spend, overdraft", headline,
                    [ch, tbl, ln, sp_ln], srcs, notes)
