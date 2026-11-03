#!/usr/bin/env python3
"""mrpc.py — a thin MRPC (MyRewards Premium Cards) program: program status and enrollments by month.

Reads what the MRPC deck's "Program to Date" and "Current Program Status" slides read: Bradford
Sanders' MRPCEnrollmentSummary weekly, through `mrpc_weekly.MrpcWeekly().client(<id>)` and
`status_slides.figures(w)`. The weekly lists enrollments per COMPLETE month (mrpc_weekly applies
`month_complete`), and the monthly series is checked again here for a collapse in the middle.
VIP's revenue figures are not shown (they are being corrected upstream).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))
for _p in (BUILD, os.path.join(BUILD, "mrpc_pipeline")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import month_complete as MC                                  # noqa: E402
from review_page import blocks as B                          # noqa: E402
from review_page import packs as PK                          # noqa: E402
from review_page.common import usable_series, left_out_text  # noqa: E402
from review_page.trace import Pack                           # noqa: E402

KEY, LABEL = "mrpc", "MRPC"
_CACHE = {}


def _weekly():
    if "w" not in _CACHE:
        import mrpc_weekly
        _CACHE["w"] = mrpc_weekly.MrpcWeekly()
    return _CACHE["w"]


def load(ctx):
    import status_slides
    wk = _weekly()
    if not wk.path:
        raise PK.PackMissing("no MRPCEnrollmentSummary weekly on hand",
                             "Run the morning source check (watch_sources.py --copy --mail) so the weekly lands in Inputs/MRPC Analyses/.")
    w = wk.client(ctx.client)
    if w is None:
        raise PK.PackMissing(f"{ctx.client} has no tab in {wk.name}",
                             "The weekly carries only clients that have MRPC; check the client's programs in clients.md.")
    f = status_slides.figures(w)
    d = PK.launcher_dir(ctx.client, ctx.period, ctx.root)
    deck = PK.find_deck(d, "MRPC")
    return {"F": Pack("MRPC weekly figures", f, ctx.tracer), "W": Pack(w["file"], w, ctx.tracer),
            "notes": PK.deck_notes(deck) if deck else {}, "deck": deck.name if deck else None, "w": w}


def _mon(ym):
    y, m = ym.split("-")
    return f"{MC._MON[int(m) - 1]} {y[2:]}"


def _mon_long(ym):
    y, m = ym.split("-")
    return f"{MC._MON[int(m) - 1]} {y}"


def build(ctx, p):
    t = ctx.tracer
    F, W = p["F"], p["W"]
    w = p["w"]
    gen = w.get("report_generated")
    fb = [{"title": "MRPC", "text": f"Source: MRPC Enrollment Summary weekly {w['file']}, tab '{w['tab']}', generated {gen}."}]
    tiers = F.get("tiers") or []
    buckets = [b for b in (F.get("buckets") or []) if b[1] is not None]
    items = [
        B.kpi("Active cardholders", F.get("active_cardholders"), "int", hot=True,
              sub=f"{B.f_pct1(F.get('still_active_pct'))} of the {B.f_int(F.get('cardholders'))} ever enrolled"),
        B.kpi("Cardholders ever enrolled", F.get("cardholders"), "int", sub=f"{B.f_int(F.get('accounts'))} accounts"),
        B.kpi("Enrolled in the last 12 months", F.get("enrolled_12"), "int",
              sub=(f"{MC.label(F.get('window')[0])} to {MC.label(F.get('window')[1])}" if F.get("window") else None)),
        B.kpi("Take rate, active accounts", F.get("take_rate_active"), "pct1", sub="As the weekly reports it"),
    ]
    tier_ch = B.bars("mrpc-tiers", "Cardholders ever enrolled, by tier", [x[0] for x in tiers],
                     [{"name": "Cardholders", "values": [x[1] for x in tiers], "color": "navy"}], "int")
    bk_ch = B.bars("mrpc-buckets", "Cardholders by days since enrollment", [x[0] for x in buckets],
                   [{"name": "Cardholders", "values": [x[1] for x in buckets], "color": "steel"}], "int")
    headline = (f"{B.f_int(F.get('active_cardholders'))} of the {B.f_int(F.get('cardholders'))} MyRewards Premium cardholders "
                f"ever enrolled are active, {B.f_pct1(F.get('still_active_pct'))}.")
    s1 = B.screen("status", "Program status", "MRPC · From the weekly", headline, [B.kpis(items), tier_ch, bk_ch],
                  PK.sources_for(p["notes"], ["Program to Date", "Current Program Status"], fb), [])

    mon = W.get("monthly") or []
    toks = [r["month"] for r in mon]
    tot = [r["platinum"] + r["gold"] + r["business"] for r in mon]
    for r, v in zip(mon, tot):
        t.derive(v, "enrollments in the month: platinum + gold + business", r["platinum"])
    keep, excl = usable_series(toks, tot, as_of=MC.report_date(gen), measure="MRPC enrollments")
    mon = [r for r, k in zip(mon, keep) if k]
    shown = mon[-18:]
    cats = [_mon(r["month"]) for r in shown]
    ch = B.bars("mrpc-enroll", "Enrollments by month", cats,
                [{"name": "Platinum", "values": [r["platinum"] for r in shown], "color": "navy"},
                 {"name": "Gold", "values": [r["gold"] for r in shown], "color": "orange"}], "int", stacked=True)
    cols = [B.col("name", "Month"), B.col("platinum", "Platinum", "int"), B.col("gold", "Gold", "int"),
            B.col("total", "Total", "int"), B.col("branch", "Branch", "int"), B.col("online", "Online", "int"),
            B.col("phone", "Phone", "int"), B.col("new", "New accounts", "int"), B.col("existing", "Existing accounts", "int")]
    rows = []
    for r in reversed(mon[-24:]):
        rows.append({"name": _mon(r["month"]), "platinum": r["platinum"], "gold": r["gold"],
                     "total": t.derive(r["platinum"] + r["gold"] + r["business"], "month total", r["platinum"]),
                     "branch": r["web_branch"], "online": r["web_enduser"], "phone": r["phone"],
                     "new": r["new"], "existing": r["existing"]})
    tbl = B.table("mrpc-month-table", "Enrollments by month and channel", cols, rows, sort={"key": None},
                  sub="Cardholders enrolled in each complete month, by tier, channel and whether the account is new.")
    last = shown[-1] if shown else None
    notes = []
    s = left_out_text(excl, "MRPC enrollments")
    if s:
        notes.append(s)
    h2 = (f"{B.f_int(last['platinum'] + last['gold'] + last['business'])} cardholders enrolled in {_mon_long(last['month'])}, the last complete month."
          if last else "Enrollments by month.")
    s2 = B.screen("enrollments", "Enrollments", "MRPC · By month", h2, [B.drill(ch, tbl)],
                  PK.sources_for(p["notes"], ["Enrollments", "Program to Date"], fb), notes)
    summary = {"headline": headline, "kpis": [dict(k, go="mrpc:status") for k in items[:3]], "open": "mrpc:status"}
    return {"screens": [s1, s2], "summary": summary, "client_name": (w.get("tab") or "").split("-", 1)[-1] or None}
