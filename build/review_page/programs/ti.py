#!/usr/bin/env python3
"""ti.py — the Transaction Intelligence screens that name a decision and a dollar figure.

Reads `ti_pack.json`, which the TI build writes (`Build Artifacts/launcher/<period>/<id>/ti/`; the ARS
lens). Nothing is recomputed: the figures are James Gilmore's v5 analyses as the cut ported them.
Seven of the cut's slides are on the page (the selection and why the rest are not:
`docs/LIVE-REVIEW-SELECTION.md`):

    competition  which institutions take our members' spend      needs the client's transaction files
    leakage      who else our members borrow from and insure with   needs the transaction files
    attrition    which branches lose accounts, and how many          ODD only
    at-risk      deposits behind accounts that look ready to leave   ODD only
    deposits     where deposit inflow is falling and idle             needs the client's deposits extract
    value        what a card and an opt-in earn a year               ODD only
    branch-gap   value per account by branch                         ODD only

A screen whose data was not in the build says so and says what to run: a client with no transaction files
(Marine FCU) gets the "run the TI build with the transaction files" state, never an empty chart.
The ICS lens is not on the page.
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

KEY, LABEL = "ti", "Transaction Intelligence"
HIDDEN = True


def load(ctx):
    d = PK.launcher_dir(ctx.client, ctx.period, ctx.root)
    fix = (f"Run the Transaction Intelligence build for {ctx.client} (CSM Sheila's Transaction Intelligence panel, or "
           f"`python scripts/ars_launcher.py build {ctx.client} --ti`). It reads the client's transaction files and takes "
           f"about 25 minutes; nothing here runs it. It writes ti_pack.json to Build Artifacts/launcher/{ctx.period}/{ctx.client}/ti/.")
    pack = PK.read_json(d / "ti" / "ti_pack.json", "the Transaction Intelligence pack (ti_pack.json)", fix)
    deck = PK.find_deck(d / "ti", "TI")
    return {"M": Pack("ti_pack.json", pack.get("metrics"), ctx.tracer, d / "ti" / "ti_pack.json"), "raw": pack,
            "names": PK.branch_names(d), "notes": PK.deck_notes(deck) if deck else {}, "deck": deck.name if deck else None}


def _fb(p, what):
    src = (p["raw"].get("sources") or {}).get("odd", "the client's ODD extract")
    return [{"title": "Transaction Intelligence", "text": f"Source: Transaction Intelligence pack ti_pack.json, {what}; ODD extract {src}. "
                                                         f"No TI deck was found beside the pack, so this line is composed from the pack."}]


def _src(p, needles, what):
    return PK.sources_for(p["notes"], needles, _fb(p, what))


def _nm(p, b):
    return PK.branch_label(p["names"], b)


def _needs(id, title, kicker, headline, what, fix):
    """A screen that cannot be drawn from this build: it says what is missing and what to run."""
    blk = {"t": "needs", "what": what, "fix": fix}
    return B.screen(id, title, kicker, headline, [blk], [], [])


def build(ctx, p):
    out = []
    for fn in (_competition, _leakage, _attrition, _at_risk, _deposits, _value, _branch_gap):
        s = fn(ctx, p)
        if s:
            out.append(s)
    return {"screens": out, "summary": None, "client_name": None}


def _has_txn(M):
    return bool(M.get("txn_rows")) and M.has("comp_institutions")


# ----------------------------------------------------------------- 5 · competition and leakage
def _competition(ctx, p):
    t, M = ctx.tracer, p["M"]
    cid = ctx.client
    fix = f"Run the TI build for {cid} with its transaction files in Inputs/Txn Files/{cid}/ (about 25 minutes)."
    if not _has_txn(M):
        return _needs("competition", "Where members spend elsewhere", "Competition · Share of wallet",
                      "Which competitors take our members' spend needs this client's transaction files.",
                      "The Transaction Intelligence build for this client did not read any transaction files, so there is no competitor spend to show.", fix)
    inst = M.get("comp_institutions") or []
    top = inst[:15]
    pct, n_with = M.get("comp_with_competitor_pct"), M.get("comp_with_competitor")
    dol = M.get("comp_competitor_dollars")
    cols = [B.col("name", "Institution"), B.col("tier", "Type"), B.col("accts", "Members paying it", "int"), B.col("pct", "% of members", "pct1"),
            B.col("dol", "Dollars", "usd"), B.col("dpa", "Per account", "usd"), B.col("new", "New, last 90 days", "int"), B.col("stop", "Stopped", "int")]
    rows = [{"name": r[0], "tier": r[1], "accts": r[2], "pct": r[3], "dol": r[5], "dpa": r[6], "new": r[8], "stop": r[9]} for r in inst]
    tbl = B.table("comp-table", "Institutions our members pay", cols, rows, sort={"key": "dol", "dir": "desc"},
                  sub="Transacting personal accounts that paid the institution in the window.")
    chart = B.bars("comp-chart", "Dollars our members paid competing institutions", [r["name"] for r in rows[:15]],
                   [{"name": "Dollars", "values": [r["dol"] for r in rows[:15]], "color": "navy"}], "usdk", horizontal=True,
                   metrics=[{"key": "dol", "label": "Dollars", "fmt": "usdk", "series": [{"name": "Dollars", "values": [r["dol"] for r in rows[:15]], "color": "navy"}]},
                            {"key": "acct", "label": "Members", "fmt": "int", "series": [{"name": "Members paying", "values": [r["accts"] for r in rows[:15]], "color": "steel"}]},
                            {"key": "new", "label": "New in 90 days", "fmt": "int", "series": [{"name": "New, last 90 days", "values": [r["new"] for r in rows[:15]], "color": "orange"}]}])
    lead = max(inst, key=lambda r: r[5])
    headline = (f"{B.f_pct1(pct)} of transacting personal accounts also pay a competing institution, {B.f_usdk(dol)} in the window; "
                f"{lead[0]} takes the most, {B.f_usdk(lead[5])}.")
    notes = ["Competitor names are the institutions found in the members' own transactions. Dollars are what members paid them, not their balances there."]
    return B.screen("competition", "Where members spend elsewhere", "Competition · Share of wallet", headline, [B.drill(chart, tbl)],
                    _src(p, ["Competition", "Competitor"], "competitor spend from the transaction files"), notes)


def _leakage(ctx, p):
    t, M = ctx.tracer, p["M"]
    cid = ctx.client
    fix = f"Run the TI build for {cid} with its transaction files in Inputs/Txn Files/{cid}/ (about 25 minutes)."
    if not (M.get("txn_rows") and M.has("fin_by_category")):
        return _needs("leakage", "Who else members borrow from", "Competition · Financial leakage",
                      "Where members borrow and insure outside the credit union needs this client's transaction files.",
                      "The Transaction Intelligence build for this client did not read any transaction files, so there are no payments to other lenders to show.", fix)
    cats = M.get("fin_by_category") or []
    cols = [B.col("name", "Category"), B.col("accts", "Members", "int"), B.col("pct", "% of members", "pct1"), B.col("dol", "Dollars", "usd"), B.col("dpa", "Per member", "usd")]
    rows = [{"name": r[0], "accts": r[1], "pct": r[2], "dol": r[4], "dpa": r[5]} for r in cats]
    tbl = B.table("leak-table", "Payments to other lenders and providers, by category", cols, rows, sort={"key": "dol", "dir": "desc"})
    chart = B.bars("leak-chart", "Dollars paid outside the credit union, by category", [r["name"] for r in rows],
                   [{"name": "Dollars", "values": [r["dol"] for r in rows], "color": "navy"}], "usdk", horizontal=True)
    pct, n, dol = M.get("fin_leaking_pct"), M.get("fin_leaking_accounts"), M.get("fin_leakage_dollars")
    top = max(rows, key=lambda r: r["dol"])
    headline = (f"{B.f_pct1(pct)} of transacting personal accounts ({B.f_int(n)}) paid {B.f_usdk(dol)} to lenders and providers outside the credit union; "
                f"{top['name']} is the largest, {B.f_usdk(top['dol'])}.")
    return B.screen("leakage", "Who else members borrow from", "Competition · Financial leakage", headline, [B.drill(chart, tbl)],
                    _src(p, ["Leakage", "Financial Services", "Where the money goes"], "payments to other lenders and providers"), [])


# ----------------------------------------------------------------- 6 · attrition and deposits
def _attrition(ctx, p):
    t, M = ctx.tracer, p["M"]
    br = M.get("attrition_by_branch") or []
    if not br:
        return None
    win = M.get("attrition_window") or []
    wlab = f"{MC.label(win[0])} to {MC.label(win[1])}" if len(win) == 2 else "the last 12 months"
    rows = [{"name": _nm(p, b[0]), "base": b[1], "closed": b[2], "rate": b[3]} for b in br]
    cols = [B.col("name", "Branch"), B.col("base", "Accounts at risk of closing", "int"), B.col("closed", "Closed", "int"), B.col("rate", "Attrition", "pct1")]
    tbl = B.table("attr-table", "Attrition by branch", cols, rows, sort={"key": "rate", "dir": "desc"},
                  sub=f"Accounts open at the start of {wlab} and how many closed.")
    chart = B.bars("attr-chart", "Share of accounts closed, by branch", [r["name"] for r in rows],
                   [{"name": "Attrition", "values": [r["rate"] for r in rows], "color": "orange"}], "pct1", horizontal=True,
                   metrics=[{"key": "rate", "label": "Rate", "fmt": "pct1", "series": [{"name": "Attrition", "values": [r["rate"] for r in rows], "color": "orange"}]},
                            {"key": "closed", "label": "Accounts closed", "fmt": "int", "series": [{"name": "Closed", "values": [r["closed"] for r in rows], "color": "navy"}]}])
    worst, best = M.get("attrition_branch_worst"), M.get("attrition_branch_best")
    rate, closed = M.get("attrition_rate"), M.get("attrition_closed")
    opened, net = M.get("attrition_opened"), M.get("attrition_net")
    kp = B.kpis([B.kpi("Accounts closed", closed, "int", sub=f"{B.f_pct1(rate)} of the book", hot=True),
                 B.kpi("Accounts opened", opened, "int", sub=f"In {wlab}"),
                 B.kpi("Net growth", net, "int", sub="Opened less closed")])
    headline = (f"{_nm(p, worst[0])} runs {B.f_pct1(worst[1])} attrition against {_nm(p, best[0])}'s {B.f_pct1(best[1])}; "
                f"the book closed {B.f_int(closed)} accounts ({B.f_pct1(rate)}) in {wlab}." if worst and best else
                f"The book closed {B.f_int(closed)} accounts ({B.f_pct1(rate)}) in {wlab}.")
    return B.screen("attrition", "Attrition by branch", "Attrition · Who is leaving", headline, [kp, B.drill(chart, tbl)],
                    _src(p, ["keeps attrition", "Attrition", "Who leaves"], "account closure by branch"), [])


def _at_risk(ctx, p):
    t, M = ctx.tracer, p["M"]
    if not M.has("stress_by_count"):
        return None
    sc = M.get("stress_by_count") or []
    cols = [B.col("name", "Stress conditions at once"), B.col("accts", "Accounts", "int"), B.col("pct", "% of book", "pct1"), B.col("dep", "Deposits", "usd")]
    rows = [{"name": ("None" if r[0] == 0 else f"{B.f_int(r[0])} condition" + ("" if r[0] == 1 else "s")), "accts": r[1], "pct": r[2], "dep": r[3]} for r in sc]
    tbl = B.table("risk-table", "Deposits by number of stress conditions", cols, rows, sort={"key": None},
                  sub="Each account is scored on the conditions the TI build can see in the ODD (falling balance, fading spend, overdrafts and others).")
    chart = B.bars("risk-chart", "Deposits by number of stress conditions", [r["name"] for r in rows],
                   [{"name": "Deposits", "values": [r["dep"] for r in rows], "color": "navy"}], "usdk",
                   metrics=[{"key": "dep", "label": "Deposits", "fmt": "usdk", "series": [{"name": "Deposits", "values": [r["dep"] for r in rows], "color": "navy"}]},
                            {"key": "acct", "label": "Accounts", "fmt": "int", "series": [{"name": "Accounts", "values": [r["accts"] for r in rows], "color": "steel"}]}])
    items = [B.kpi("Deposits behind accounts with a falling balance", M.get("flight_risk_deposits"), "usdk",
                   sub=f"{B.f_int(M.get('flight_risk_n'))} accounts over {B.f_usd(M.get('flight_risk_threshold'))}", hot=True),
             B.kpi("Deposits behind accounts with two or more stress conditions", M.get("stress_2plus_deposits"), "usdk",
                   sub=f"{B.f_int(M.get('stress_2plus_n'))} accounts"),
             B.kpi("Deposits in sleeping-giant accounts", M.get("sleeping_giants_deposits"), "usdk",
                   sub=f"{B.f_int(M.get('sleeping_giants_n'))} accounts, as the TI cut defines them")]
    headline = (f"{B.f_int(M.get('flight_risk_n'))} accounts holding {B.f_usdk(M.get('flight_risk_deposits'))} show a falling balance, and "
                f"{B.f_int(M.get('stress_2plus_n'))} carry two or more stress conditions at once, holding {B.f_usdk(M.get('stress_2plus_deposits'))}.")
    notes = ["The three groups overlap; their deposits are not additive. The balance-falling group is found from a balance proxy, not from deposits."]
    return B.screen("at-risk", "Deposits at risk", "Attrition · Who to call", headline, [B.kpis(items), B.drill(chart, tbl)],
                    _src(p, ["stressors at once", "Stresses across", "flight"], "accounts at risk of leaving"), notes)


def _deposits(ctx, p):
    t, M = ctx.tracer, p["M"]
    cid = ctx.client
    if not M.has("dep_inflow_health"):
        return _needs("deposits", "Where deposit inflow is falling", "Deposits · Inflow",
                      "Where deposit inflow is falling or idle needs this client's deposits extract.",
                      "The Transaction Intelligence build for this client did not read a deposits extract, so there is no inflow to show.",
                      f"Land the client's ILS deposits extract in Inputs/Deposits/ (one file, rolling 365 days), then run the TI build for {cid}.")
    health = M.get("dep_inflow_health") or []
    chart = B.bars("dep-chart", "Accounts by deposit inflow", [r[0] for r in health],
                   [{"name": "Accounts", "values": [r[1] for r in health], "color": "navy"}], "int")
    cols = [B.col("name", "Inflow"), B.col("accts", "Accounts", "int"), B.col("pct", "% of base", "pct1")]
    tbl = B.table("dep-table", "Accounts by deposit inflow", cols, [{"name": r[0], "accts": r[1], "pct": r[2]} for r in health], sort={"key": None})
    items = [B.kpi("Deposits in accounts where balance and inflow are both falling", M.get("dep_falling_and_slowing_dollars"), "usdk",
                   sub=f"{B.f_int(M.get('dep_falling_and_slowing_n'))} accounts", hot=True),
             B.kpi("Idle balances", M.get("dep_idle_dollars"), "usdk", sub=f"{B.f_int(M.get('dep_idle_n'))} accounts over {B.f_usd(M.get('dep_idle_balance_floor'))}, quiet {B.f_int(M.get('dep_idle_quiet_days'))} days"),
             B.kpi("Recurring income stopped", M.get("dep_stopped_n"), "int", sub=f"{B.f_pct1(M.get('dep_stopped_pct'))} of accounts")]
    headline = (f"{B.f_usdk(M.get('dep_falling_and_slowing_dollars'))} sits in {B.f_int(M.get('dep_falling_and_slowing_n'))} accounts where the balance "
                f"is falling and inflow is slowing; {B.f_int(M.get('dep_stopped_n'))} accounts lost a recurring credit.")
    return B.screen("deposits", "Where deposit inflow is falling", "Deposits · Inflow", headline, [B.kpis(items), B.drill(chart, tbl)],
                    _src(p, ["Balance falling and inflow slowing", "Deposits"], "deposit inflow"),
                    ["Inflow is from the deposits extract and spend from the ODD; cash, transfers and cheques are in neither, so this is a direction, not a balance."])


# ----------------------------------------------------------------- 7 · what it is worth
def _value(ctx, p):
    t, M = ctx.tracer, p["M"]
    if not M.has("value_per_card"):
        return None
    cur = B.bars("val-chart", "Revenue per account a year, with and without", ["Debit card", "Reg E opt-in"],
                 [{"name": "Without", "values": [M.get("value_debit_total_without"), M.get("value_rege_total_without")], "color": "steel"},
                  {"name": "With", "values": [M.get("value_debit_total_with"), M.get("value_rege_total_with")], "color": "navy"}], "usd",
                 sub="Interchange plus overdraft fees, per account, over 12 months.")
    pot = B.bars("val-pot", "What closing the gap is worth a year", ["Debit card", "Reg E opt-in"],
                 [{"name": "Earning now", "values": [M.get("value_debit_current_revenue"), M.get("value_rege_current_revenue")], "color": "navy"},
                  {"name": "If every eligible account had one", "values": [M.get("value_debit_pot_full"), M.get("value_rege_pot_full")], "color": "orange"}], "usdk")
    kp = B.kpis([B.kpi("A debit card is worth, a year", M.get("value_per_card"), "usd", hot=True, sub="Per account, interchange plus fees"),
                 B.kpi("A Reg E opt-in is worth, a year", M.get("value_per_optin"), "usd", sub="Per account"),
                 B.kpi("More revenue if every eligible account held a card", M.get("value_debit_pot_full"), "usdk", sub="A year, at today's rates")])
    headline = (f"A debit card is worth {B.f_usd(M.get('value_per_card'))} a year to the credit union and a Reg E opt-in {B.f_usd(M.get('value_per_optin'))}; "
                f"closing the card gap alone is worth {B.f_usdk(M.get('value_debit_pot_full'))} a year.")
    notes = ["The comparison is between accounts with and without the feature, not a controlled test; accounts that hold a card or opt in differ in other ways too."]
    return B.screen("value", "What a card and an opt-in earn", "What it is worth · Per account", headline, [kp, cur, pot],
                    _src(p, ["A card is worth", "Value"], "revenue per account with and without a card and opt-in"), notes)


def _branch_gap(ctx, p):
    t, M = ctx.tracer, p["M"]
    vb = M.get("value_by_branch") or []
    if not vb:
        return None
    rows = [{"name": _nm(p, r["group"]), "n": r["n"], "take": r["take_rate"], "value": r["value_per_acct"]} for r in vb]
    cols = [B.col("name", "Branch"), B.col("n", "Accounts", "int"), B.col("take", "Debit take", "pct1"), B.col("value", "Value per account a year", "usd")]
    tbl = B.table("gap-table", "Value per account, by branch", cols, rows, sort={"key": "value", "dir": "asc"},
                  sub="Interchange plus overdraft fees per account over 12 months.")
    chart = B.bars("gap-chart", "Value per account a year, by branch", [r["name"] for r in rows],
                   [{"name": "Value per account", "values": [r["value"] for r in rows], "color": "navy"}], "usd", horizontal=True)
    best, worst, spread = M.get("value_branch_best"), M.get("value_branch_worst"), M.get("value_branch_spread")
    pick = lambda x: x["group"] if isinstance(x, dict) else (x[0] if isinstance(x, list) else x)
    b_nm, w_nm = _nm(p, pick(best)), _nm(p, pick(worst))
    headline = (f"Account value runs {B.f_usd(spread)} a year from {w_nm} to {b_nm}; every branch is in the table."
                if spread else "Value per account by branch.")
    return B.screen("branch-gap", "Branch value gap", "What it is worth · By branch", headline, [B.drill(chart, tbl)],
                    _src(p, ["Closing the three widest branch gaps", "Branch gaps", "16 out-earns"], "value per account by branch"), [])
