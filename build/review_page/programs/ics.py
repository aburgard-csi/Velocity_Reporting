#!/usr/bin/env python3
"""ics.py — a thin ICS (Invitation Checking System) program: referrals and results by branch.

Reads the VIP sheet the ICS deck builder reads (`rpe_env.resolve_client_json(<id>, "ics")`). ICS
presents CURRENT results only (CLAUDE.md, 2026-08-28): the workbook-driven figures (ROI, revenue,
financial summary) appear only when the newest ICS workbook is for the deck's own period. This
screen set is therefore the referrals shape the deck falls back to — referrals, the trend, and
results by branch — and it says why the financial detail is absent.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))
if BUILD not in sys.path:
    sys.path.insert(0, BUILD)

import month_complete as MC                          # noqa: E402
from review_page import blocks as B                  # noqa: E402
from review_page import packs as PK                  # noqa: E402
from review_page.trace import Pack                   # noqa: E402

KEY, LABEL = "ics", "ICS"


def load(ctx):
    import rpe_env
    try:
        path = rpe_env.resolve_client_json(ctx.client, "ics")
    except (SystemExit, Exception) as e:
        raise PK.PackMissing(f"no VIP ICS sheet for {ctx.client}",
                             "Refresh the VIP sheets (the vip-rescan skill) so Inputs/VIP Data/ICS/ has this client.")
    data = json.loads(open(path, encoding="utf-8").read())
    d = PK.launcher_dir(ctx.client, ctx.period, ctx.root)
    deck = PK.find_deck(d, "ICS")
    return {"V": Pack(os.path.basename(str(path)), data, ctx.tracer, path),
            "notes": PK.deck_notes(deck) if deck else {}, "deck": deck.name if deck else None}


def _wb_period(meta):
    m = re.match(r"^\d{3,5}-(\d{4}\.\d{2})-", str((meta or {}).get("workbook") or ""))
    return m.group(1) if m else None


def build(ctx, p):
    t = ctx.tracer
    V = p["V"]
    name = V.get("meta", "client_name", default="The client")
    rf = V.get("referrals") or {}
    wb = _wb_period(V.data.get("meta"))
    notes = []
    if wb != ctx.period:
        notes.append(f"Financial detail (ROI, revenue, financial summary) is shown only with an ICS workbook for {ctx.period}; "
                     f"the newest on hand is {wb or 'none'}. The deck leaves it out for the same reason.")
    trend = rf.get("trend") or {}
    months, vals, goal = list(trend.get("months") or []), list(trend.get("referrals") or []), list(trend.get("goal") or [])
    mtd = rf.get("month_to_date") or {}
    if trend.get("partial_last") and months:
        notes.append(f"{MC.label(months[-1])} has {B.f_int(mtd.get('value'))} referrals so far; a month still in progress is left out of the trend.")
        months, vals, goal = months[:-1], vals[:-1], goal[:-1]
    prev = rf.get("previous_month") or {}
    items = [
        B.kpi("Referrals, program to date", rf.get("program_to_date"), "int", hot=True, sub=f"Since {MC.label(V.get('meta', 'program_start'))}" if V.get('meta', 'program_start') else None),
        B.kpi("Referrals, year to date", rf.get("year_to_date"), "int"),
        B.kpi(f"Referrals in {prev.get('label')}", prev.get("value"), "int",
              sub=f"{B.f_pct0(rf.get('prev_month_vs_goal_pct'))} of the monthly goal of {B.f_int(rf.get('monthly_goal'))}"),
    ]
    chart = B.bars("ics-trend", "Referrals by month against goal", months,
                   [{"name": "Referrals", "values": vals, "color": "navy"},
                    {"name": "Goal", "values": goal, "color": "steel"}], "int")
    headline = (f"{name} has {B.f_int(rf.get('program_to_date'))} ICS referrals to date and {B.f_int(rf.get('year_to_date'))} this year; "
                f"{prev.get('label')} brought {B.f_int(prev.get('value'))}, {B.f_pct0(rf.get('prev_month_vs_goal_pct'))} of the monthly goal.")
    meta = V.data.get("meta") or {}
    fb = [{"title": "ICS referrals", "text": f"Source: {meta.get('vip_source', 'VIP ICS Referral Data dashboard')}, pulled {meta.get('data_pull')}."}]
    s1 = B.screen("referrals", "Referrals", "ICS · Invitation Checking", headline, [B.kpis(items), chart],
                  PK.sources_for(p["notes"], ["Power of Referrals", "Referral Trend", "Referrals"], fb), notes)

    br = ((rf.get("by_branch") or {}).get("branches")) or []
    rows = []
    for b in br:
        goal_b = b.get("goal")
        pct = t.derive(100.0 * b["referrals"] / goal_b, "referrals over goal", b["referrals"], goal_b) if goal_b else None
        rows.append({"name": b["name"], "referrals": b["referrals"], "goal": goal_b, "pct": pct})
    rows.sort(key=lambda r: -(r["referrals"] or 0))
    cols = [B.col("name", "Branch"), B.col("referrals", "Referrals", "int"), B.col("goal", "Goal", "int"), B.col("pct", "% of goal", "pct0")]
    tbl = B.table("ics-branch-table", "Referrals by branch, year to date", cols, rows, sort={"key": "referrals", "dir": "desc"})
    ch = B.bars("ics-branch-chart", "Referrals by branch, year to date", [r["name"] for r in rows],
                [{"name": "Referrals", "values": [r["referrals"] for r in rows], "color": "navy"},
                 {"name": "Goal", "values": [r["goal"] for r in rows], "color": "steel"}], "int", horizontal=True)
    nb = len([r for r in rows if r["referrals"]])
    lead = rows[0] if rows else None
    h2 = (f"{lead['name']} leads with {B.f_int(lead['referrals'])} referrals this year." if lead else "Referrals by branch.")
    s2 = B.screen("branch", "Results by branch", "ICS · Year to date", h2, [B.drill(ch, tbl)],
                  PK.sources_for(p["notes"], ["Results by Branch"], fb), [])
    summary = {"headline": headline, "kpis": [dict(k, go="ics:referrals") for k in items[:3]], "open": "ics:referrals"}
    screens = [s1, s2]
    ps = _peers(ctx)
    if ps:
        screens.append(ps)
    return {"screens": screens, "summary": summary, "client_name": name}


def _peers(ctx):
    """'How you compare': the client against the other ICS clients, anonymously (review_page/peers.py)."""
    from review_page import peer_pool, peers
    try:
        coll = peer_pool.collect_ics(ctx)
    except Exception:
        return None
    return peers.peers_screen(ctx.tracer, "ICS", "ICS", coll, peer_pool.ICS_METRICS, trend="pct_goal", pull_dates=coll["pull"])
