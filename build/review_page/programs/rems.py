#!/usr/bin/env python3
"""rems.py — Reg E Management Solution (REMS): responses and opt-ins by month, and how the client compares.

Reads the result of `sql/rems_responses_report.sql` (one row per client per month: responses, opt-ins and the opt-in
rate), saved by a person as `Inputs/REMS/rems_responses <YYYY-MM-DD>.csv` (Aaron, 2026-11-03: "add a section for Reg E
Management Solution (REMS)"). The query runs against the MRDB / SRDB databases, which Claude cannot reach, so until
that file is saved the program says what to run, and a client with no REMS rows in it is not shown the section.

The file holds every client, so the same read feeds the peer comparison (`peer_pool.collect_rems`).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))
if BUILD not in sys.path:
    sys.path.insert(0, BUILD)

import month_complete as MC                                  # noqa: E402
from review_page import blocks as B                          # noqa: E402
from review_page import packs as PK                          # noqa: E402
from review_page.common import usable_series, left_out_text  # noqa: E402
from review_page.trace import Pack                           # noqa: E402

KEY, LABEL = "rems", "REMS"
FIX = ("Run sql/rems_responses_report.sql against the SRDB server and save its result as "
       "Inputs/REMS/rems_responses <YYYY-MM-DD>.csv (the CSV with the client_id, response_year, response_month, "
       "num_responses, num_opt_in and pct_opt_in columns), then reload.")


def load(ctx):
    from review_page import peer_pool
    rows, as_of, fname = peer_pool.rems_rows(ctx)
    if not fname:
        raise PK.PackMissing("the REMS responses file is not in Inputs/REMS", FIX)
    mine = rows.get(str(ctx.client))
    if not mine or not mine["months"]:
        raise PK.PackMissing(f"client {ctx.client} has no REMS responses in {fname}",
                             "The client is not on REMS, or the query's corporation filter left it out: check it in the file.")
    months = sorted(mine["months"])
    ended = [m for m in months if MC.month_ended(m, as_of) is not False]
    monthly = []
    for m in ended:
        r, o = mine["months"][m]
        monthly.append({"period_month": m, "responses": r, "opt_ins": o,
                        "opt_in_rate": (o / r) if r else None, "opt_in_pct": (100.0 * o / r) if r else None})
    tr = sum(x["responses"] for x in monthly)
    to = sum(x["opt_ins"] for x in monthly)
    total = {"responses": tr, "opt_ins": to, "opt_in_rate": (to / tr) if tr else None, "opt_in_pct": (100.0 * to / tr) if tr else None}
    data = {"client_name": mine.get("name") or f"Client {ctx.client}", "source_file": fname, "as_of": str(as_of) if as_of else None,
            "monthly": monthly, "total": total, "latest": monthly[-1] if monthly else None}
    return {"C": Pack(fname, data, ctx.tracer, None), "notes": {}, "deck": None}


def _pm(period_month):
    y, m = period_month.split("-")
    return f"{MC._MON[int(m) - 1]} {y[2:]}"


def _pm_long(period_month):
    y, m = period_month.split("-")
    return f"{MC._MON[int(m) - 1]} {y}"


def build(ctx, p):
    C = p["C"]
    name = C.get("client_name", default="The client")
    fb = [{"title": "REMS", "text": (f"Source: {C.get('source_file')}, the result of sql/rems_responses_report.sql, read {C.get('as_of')}. "
                                     "A response is one record of the REMS opt-in table and an opt-in is a response whose opt-in "
                                     "status is yes; counts are by the month of the response, complete months only.")}]
    mon = list(C.get("monthly") or [])
    toks = [r["period_month"] for r in mon]
    as_of = MC.report_date(C.get("as_of")) if C.get("as_of") else None
    keep, excl = usable_series(toks, [r["responses"] for r in mon], as_of=as_of, measure="REMS responses")
    shown_all = [r for r, k in zip(mon, keep) if k]
    shown = shown_all[-18:]
    last = shown_all[-1] if shown_all else None
    tot = C.get("total") or {}
    items = [B.kpi("Responses, program to date", tot.get("responses"), "int", hot=True, sub=f"{B.f_int(tot.get('opt_ins'))} opted in"),
             B.kpi("Opt-in rate, program to date", tot.get("opt_in_rate"), "frac1", sub="Opt-ins over responses")]
    if last:
        items += [B.kpi(f"Responses, {_pm_long(last['period_month'])}", last["responses"], "int", sub=f"{B.f_int(last['opt_ins'])} opted in"),
                  B.kpi(f"Opt-in rate, {_pm_long(last['period_month'])}", last["opt_in_rate"], "frac1")]
    chart = B.bars("rems-month", "Responses by month", [_pm(r["period_month"]) for r in shown],
                   [{"name": "Responses", "values": [r["responses"] for r in shown], "color": "navy"}], "int",
                   metrics=[{"key": "responses", "label": "Responses", "fmt": "int",
                             "series": [{"name": "Responses", "values": [r["responses"] for r in shown], "color": "navy"}]},
                            {"key": "opt_ins", "label": "Opt-ins", "fmt": "int",
                             "series": [{"name": "Opt-ins", "values": [r["opt_ins"] for r in shown], "color": "steel"}]},
                            {"key": "rate", "label": "Opt-in rate", "fmt": "frac1",
                             "series": [{"name": "Opt-in rate", "values": [r["opt_in_rate"] for r in shown], "color": "orange"}]}])
    cols = [B.col("name", "Month"), B.col("responses", "Responses", "int"), B.col("opt_ins", "Opt-ins", "int"),
            B.col("rate", "Opt-in rate", "frac1")]
    rows = [{"name": _pm(r["period_month"]), "responses": r["responses"], "opt_ins": r["opt_ins"], "rate": r["opt_in_rate"]}
            for r in reversed(shown_all[-24:])]
    tbl = B.table("rems-month-table", "Responses by month", cols, rows, sort={"key": None},
                  sub="Responses to the Reg E opt-in request in each complete month, and how many opted in.")
    notes = []
    s = left_out_text(excl, "REMS responses")
    if s:
        notes.append(s)
    if last:
        headline = (f"{name} drew {B.f_int(last['responses'])} Reg E Management Solution responses in {_pm_long(last['period_month'])}; "
                    f"{last['opt_in_pct']:.1f}% opted in.")
    else:
        headline = f"{name} has {B.f_int(tot.get('responses'))} Reg E Management Solution responses to date, {B.f_int(tot.get('opt_ins'))} of them opt-ins."
    s1 = B.screen("summary", "REMS responses", "REMS · By month", headline, [B.kpis(items), B.drill(chart, tbl)],
                  PK.sources_for(p["notes"], ["REMS"], fb), notes)
    summary = {"headline": headline, "kpis": [dict(k, go="rems:summary") for k in items[:3]], "open": "rems:summary"}
    screens = [s1]
    ps = _peers(ctx)
    if ps:
        screens.append(ps)
    return {"screens": screens, "summary": summary, "client_name": name}


def _peers(ctx):
    """'How you compare': the client against the other REMS clients (review_page/peers.py)."""
    from review_page import peer_pool, peers
    try:
        coll = peer_pool.collect_rems(ctx)
    except Exception:
        return None
    return peers.peers_screen(ctx.tracer, "REMS", "REMS", coll, peer_pool.REMS_METRICS, trend="pct_opt_in", pull_dates=coll["pull"])
