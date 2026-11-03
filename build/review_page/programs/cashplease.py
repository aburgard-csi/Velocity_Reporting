#!/usr/bin/env python3
"""cashplease.py — a thin CashPlease program: loan summary and volume by month.

Reads what the CashPlease deck reads: `cp_extract`'s per-client pack,
`Build Artifacts/cashplease/packs/<id>_cashplease.json` (from the newest CashPleaseSummary weekly and
the weekly ILS DDA count). CashPlease is weekly and always uses the newest weekly, so its date can
be later than the other programs' (CLAUDE.md); the page prints it. A loan-per-DDA rate appears only
when a DDA count exists; otherwise the page says why and shows no zero.
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

KEY, LABEL = "cashplease", "CashPlease"


def load(ctx):
    import rpe_env
    root = ctx.root or rpe_env.build_artifacts()
    path = os.path.join(str(root), "cashplease", "packs", f"{ctx.client}_cashplease.json")
    data = PK.read_json(path, "the CashPlease pack",
                        "Run `python scripts/build_cashplease.py --only %s` (it writes the pack with the newest weekly) "
                        "or build the client's deck in CSM Sheila." % ctx.client)
    d = PK.launcher_dir(ctx.client, ctx.period, ctx.root)
    deck = PK.find_deck(d, "CP")
    return {"C": Pack(os.path.basename(path), data, ctx.tracer, path),
            "notes": PK.deck_notes(deck) if deck else {}, "deck": deck.name if deck else None}


def _pm(period_month):
    y, m = period_month.split("-")
    return f"{MC._MON[int(m) - 1]} {y[2:]}"


def _pm_long(period_month):
    y, m = period_month.split("-")
    return f"{MC._MON[int(m) - 1]} {y}"


def build(ctx, p):
    t = ctx.tracer
    C = p["C"]
    m = C.get("metrics") or {}
    gen = C.get("report_generated")
    name = C.get("client_name", default="The client")
    fb = [{"title": "CashPlease", "text": f"Source: {C.get('source_file')}, report generated {gen}; "
                                          f"DDA count sent {C.get('dda_sent')}."}]
    st = C.get("status") or {}
    items = [
        B.kpi("Loans, program to date", m.get("total_loans"), "int", hot=True,
              sub=f"{B.f_usd(m.get('total_principal'))} lent"),
        B.kpi("Funded loans outstanding", m.get("active_loans"), "int", sub=f"{B.f_usd(m.get('active_principal'))} principal"),
        B.kpi("Average loan", m.get("avg_loan_size"), "usd"),
        B.kpi("Charged off", C.get("charge_off_pct"), "frac1", sub="Of loans, as the weekly reports it"),
    ]
    if m.get("loans_per_1k_dda") is not None:
        items.append(B.kpi("Loans per 1,000 DDAs, last 12 months", m.get("loans_per_1k_dda"), "dec1",
                           sub=f"{B.f_int(m.get('window_loans'))} loans on {B.f_int(m.get('dda_accounts'))} DDA accounts"))
    status_rows = [{"name": k, "loans": v["loans"], "principal": v["principal"], "interest": v["interest"]}
                   for k, v in st.items() if v.get("loans")]
    tot = C.get("total") or {}
    cols = [B.col("name", "Status"), B.col("loans", "Loans", "int"), B.col("principal", "Principal", "usd"),
            B.col("interest", "Interest", "usd")]
    stbl = B.table("cp-status", "Loans by status", cols, status_rows,
                   total={"name": "All loans", "loans": tot.get("loans"), "principal": tot.get("principal"), "interest": tot.get("interest")},
                   search=False, sort={"key": None})
    notes = []
    if m.get("loans_per_1k_dda") is None and m.get("dda_missing_reason"):
        notes.append(f"Loans per 1,000 DDAs is not shown: {m['dda_missing_reason']}.")
    headline = (f"{name} has made {B.f_int(m.get('total_loans'))} CashPlease loans to date, "
                f"{B.f_usd(m.get('total_principal'))} in principal; {B.f_int(m.get('active_loans'))} are funded and outstanding.")
    s1 = B.screen("summary", "Loan summary", "CashPlease · Weekly", headline, [B.kpis(items), stbl],
                  PK.sources_for(p["notes"], ["CashPlease"], fb), notes)

    mon = list(C.get("monthly") or [])                       # newest first
    mon = [r for r in mon if r.get("period_month")]
    mon.sort(key=lambda r: r["period_month"])
    as_of = MC.report_date(gen)
    ended = [r for r in mon if MC.month_ended(r["period_month"], as_of) is not False]
    toks = [r["period_month"] for r in ended]
    keep, excl = usable_series(toks, [r["loans"] for r in ended], as_of=as_of, measure="CashPlease loans")
    ended = [r for r, k in zip(ended, keep) if k]
    shown = ended[-18:]
    ch = B.bars("cp-volume", "Loans by month", [_pm(r["period_month"]) for r in shown],
                [{"name": "Loans", "values": [r["loans"] for r in shown], "color": "navy"}], "int",
                metrics=[{"key": "loans", "label": "Loans", "fmt": "int",
                          "series": [{"name": "Loans", "values": [r["loans"] for r in shown], "color": "navy"}]},
                         {"key": "principal", "label": "Principal", "fmt": "usdk",
                          "series": [{"name": "Principal", "values": [r["principal"] for r in shown], "color": "steel"}]}])
    cols2 = [B.col("name", "Month"), B.col("loans", "Loans", "int"), B.col("principal", "Principal", "usd"),
             B.col("interest", "Interest", "usd"), B.col("funded", "Funded", "int"), B.col("paid_off", "Paid off", "int"),
             B.col("overdue", "Overdue", "int"), B.col("charged_off", "Charged off", "int")]
    rows = [{"name": _pm(r["period_month"]), "loans": r["loans"], "principal": r["principal"], "interest": r["interest"],
             "funded": r["funded"], "paid_off": r["paid_off"], "overdue": r["overdue"], "charged_off": r["charged_off"]}
            for r in reversed(ended[-24:])]
    tbl = B.table("cp-month-table", "Loans by month", cols2, rows, sort={"key": None},
                  sub="Loans booked in each complete month and where they stand now.")
    s = left_out_text(excl, "CashPlease loans")
    n2 = [s] if s else []
    last = shown[-1] if shown else None
    h2 = (f"{B.f_int(last['loans'])} loans were made in {_pm_long(last['period_month'])}, {B.f_usd(last['principal'])} in principal."
          if last else "Loans by month.")
    s2 = B.screen("volume", "Volume by month", "CashPlease · Loans", h2, [B.drill(ch, tbl)],
                  PK.sources_for(p["notes"], ["CashPlease"], fb), n2)
    summary = {"headline": headline, "kpis": [dict(k, go="cashplease:summary") for k in items[:3]], "open": "cashplease:summary"}
    return {"screens": [s1, s2], "summary": summary, "client_name": name}
