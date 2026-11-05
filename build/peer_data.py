#!/usr/bin/env python3
"""peer_data.py — the per-client ICS, MRPC and CashPlease sections, read once.

Moved here from `scripts/refresh_performance_dashboard.py` on 2026-11-03 (a straight move; the dashboard imports them
back under their old names). The RPE Client Performance page reads them per client for its cross-client sections, and
Live Review's "How you compare" screens read the same rows for the peer pool, so the two cannot read a program's sheet
two ways.

  ics_section(cid, c)         the VIP ICS sheet: referrals, goal, trend (complete months), and the workbook's figures
  mrpc_section(cid, weekly)   the MRPCEnrollmentSummary weekly tab and the VIP MRPC sheet
  cp_section(cid, packs)      cp_extract's per-client pack
  complete_trend(trend)       an ICS trend without its month in progress

Import-safe: nothing runs at import and nothing is read until a function is called.
"""
import json
import os
import re
import sys

_BUILD = os.path.dirname(os.path.abspath(__file__))
for _p in (_BUILD, os.path.join(_BUILD, "mrpc_pipeline")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import rpe_env as R                                   # noqa: E402
from mrpc_weekly import complete_months               # noqa: E402


def wb_period(fn):
    m = re.search(r"-(20\d\d\.\d\d)-", fn or "")
    return m.group(1) if m else None


# Trend lines show complete months only (Aaron, 2026-09-14). A sparkline that ends on a
# half month reads as a fall-off: 2026.09's ICS trends ended on 13 days of September.
def complete_trend(trend):
    """The VIP ICS referral trend without its month-to-date point.

    VIP ends the trend with the month in progress and flags it `partial_last`; that last
    month is dropped from every parallel series. Year-to-date and program-to-date figures
    are VIP's own and are not touched.
    """
    if not isinstance(trend, dict) or not trend.get("partial_last"):
        return trend
    t = dict(trend)
    for k in ("months", "referrals", "goal"):
        if isinstance(t.get(k), list) and t[k]:
            t[k] = t[k][:-1]
    t["partial_last"] = False
    return t


def ics_section(cid, c):
    try:
        p = R.resolve_client_json(cid, "ics")
    except BaseException as e:
        return {"missing": str(e).splitlines()[0] if str(e) else "no VIP ICS sheet"}
    d = json.load(open(p, encoding="utf-8"))
    meta, ref = d.get("meta", {}), d.get("referrals", {})
    perf, fs = d.get("performance") or {}, d.get("financial_summary") or {}
    has_wb = bool(perf.get("roi")) and "ICS-REFERRALS" not in c["roster_programs"]
    ics = {
        "period": meta.get("period"), "data_pull": meta.get("data_pull"),
        "program_start": meta.get("program_start"),
        "workbook": meta.get("workbook"), "workbook_period": wb_period(meta.get("workbook")),
        "referrals_only": not has_wb,
        "ptd": ref.get("program_to_date"), "ytd": ref.get("year_to_date"),
        "prev_month": ref.get("previous_month"), "mtd": ref.get("month_to_date"),
        "monthly_goal": ref.get("monthly_goal"), "prev_vs_goal_pct": ref.get("prev_month_vs_goal_pct"),
        "trend": complete_trend(ref.get("trend")),
    }
    if has_wb:
        rev = d.get("revenue") or {}
        ics.update({
            "roi": perf.get("roi"), "ltv": perf.get("lifetime_value_per_account"),
            "annual_profit_per_account": perf.get("annual_profit_per_account"),
            "cost_per_account": perf.get("cost_per_account"),
            "payback_months": perf.get("payback_months"),
            "avg_life_years": perf.get("average_account_life_years"),
            "net_profit": fs.get("net_profit"), "ics_accounts": fs.get("ics_accounts"),
            "profit_contribution": fs.get("account_profit_contribution"),
            "program_expense": fs.get("total_program_expense"),
            "avg_balance": fs.get("average_balance"), "revenue_total": rev.get("total"),
        })
    return ics



# ------------------------------------------------------------------ MRPC
def mrpc_section(cid, weekly):
    m = {"weekly": weekly.client(cid)}
    try:
        p = R.resolve_client_json(cid, "mrpc")
        d = json.load(open(p, encoding="utf-8"))
        meta = d.get("meta", {})
        pv, rev = d.get("performance_vs_goal") or {}, d.get("revenue") or {}
        m.update({
            "period": meta.get("period"), "data_pull": meta.get("data_pull"),
            "key_metrics": d.get("key_metrics") or {},
            "goal_pct": pv.get("goal_pct"), "pct_of_goal": pv.get("pct_of_goal"),
            "goal_months": pv.get("months"), "goal_enrollments": pv.get("enrollments"),
            "goal_new_accounts": pv.get("new_accounts"),
            "revenue_ltd": rev.get("life_of_program"), "revenue_2025": rev.get("year_2025"),
        })
    except BaseException as ex:
        m["missing_vip"] = str(ex).splitlines()[0] if str(ex) else "no VIP MRPC sheet"
    return m



# ------------------------------------------------------------------ CashPlease
def cp_section(cid, packs):
    f = packs / f"{cid}_cashplease.json"
    if not f.exists():
        return {"missing": "no tab in the CashPlease workbook"}
    d = json.load(open(f, encoding="utf-8"))
    mt = d["metrics"]
    mon = complete_months(sorted(d["monthly"], key=lambda r: r["period_month"]),
                          d.get("report_generated"), key="period_month")[-24:]
    return {
        "file": d["source_file"], "report_generated": d["report_generated"],
        "cp_name": d["client_name"],
        "total_loans": mt["total_loans"], "total_principal": mt["total_principal"],
        "total_interest": mt["total_interest"], "active_loans": mt["active_loans"],
        "active_principal": mt["active_principal"], "avg_loan_size": mt["avg_loan_size"],
        "avg_interest_per_loan": mt["avg_interest_per_loan"],
        "charge_off_pct": mt["charge_off_pct"], "pct_overdue": mt["pct_loans_overdue"],
        "pct_charged_off": mt["pct_loans_charged_off"], "pct_paid_off": mt["pct_loans_paid_off"],
        "pct_active_accounts_with_loans": d["pct_active_accounts_with_loans"],
        "window_loans": mt["window_loans"], "window_months": mt["window_months"],
        "status": {k: v["loans"] for k, v in d["status"].items()},
        "monthly": [{"month": r["period_month"], "loans": r["loans"],
                     "principal": r["principal"], "interest": r["interest"]} for r in mon],
        "mtd": {"days": len(d["daily"]), "loans": sum(r["loans"] for r in d["daily"])},
    }
