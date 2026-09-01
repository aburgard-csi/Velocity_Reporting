#!/usr/bin/env python3
"""
ics_workbook_extract.py — populate an ICS client JSON's workbook sections from
the Invitation Checking workbook.

The per-client data sheets carry VIP referral data (monthly) but their workbook
sections (performance / revenue / financial_summary / monthly_detail / benchmark)
are refreshed quarterly, by hand, when a new workbook lands. This does that step.

Method, verified field-for-field against the known-good 1705 sheet:
  * "Monthly Detail" carries a column per program month PLUS summary columns.
    Sum ONLY the columns whose header row (14) holds a real date — summing the
    row blindly double-counts the summary columns (~2x every figure).
  * revenue components  = rows Spread on Deposits / Interchange Income /
    NSF-OD Fees / Other Fees; total = Account Profit Contribution.
  * total_program_expense = "Total Expense"; net_profit = "Profit Contribution
    to Date".
  * average_balance = per-cohort average balance WEIGHTED by accounts opened
    (the simple mean is wrong: 1106.19 vs the correct 1203.36).
  * performance      = "Value of ICS Accts".
  * benchmark        = "Life of Account Data" open/close table.

Usage:
  python3 ics_workbook_extract.py <workbook.xlsx> <client_json> [--write]

Without --write it prints the sections and, when the JSON already carries
populated sections, diffs against them (the 1705 validation path).
"""
import argparse
import datetime
import json
import os
import sys
import warnings

import openpyxl

warnings.filterwarnings("ignore")

CONTACTS = [
    {"name": "Aaron Burgard", "role": "Client Service Manager",
     "phone": "910-617-1984", "email": "aaron.burgard@csiweb.com"},
    {"name": "Cindy Draper",
     "role": "Strategist and Program Manager for Invitation Checking® System",
     "phone": "910-386-8287", "email": "cindy.draper@csiweb.com"},
]


def _label(ws, r, maxc=4):
    for c in range(1, maxc + 1):
        v = ws.cell(r, c).value
        if isinstance(v, str) and v.strip():
            return v.strip(), c
    return None, None


def _find_row(ws, needle, r1=1, r2=60):
    n = needle.lower()
    for r in range(r1, r2 + 1):
        lab, _ = _label(ws, r)
        if lab and lab.lower().startswith(n):
            return r
    return None


def _value_after(ws, r, from_col=1, maxc=10):
    """First numeric cell to the right of the label on row r."""
    for c in range(from_col, maxc + 1):
        v = ws.cell(r, c).value
        if isinstance(v, (int, float)):
            return v
    return None


def month_cols(ws, header_row=14):
    return [c for c in range(1, ws.max_column + 1)
            if isinstance(ws.cell(header_row, c).value, datetime.datetime)]


def extract(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    md = wb["Monthly Detail"]
    cols = month_cols(md) or month_cols(md, 7)
    if not cols:
        raise SystemExit("ERROR: no dated month columns in 'Monthly Detail'")
    hdr_row = 14 if isinstance(md.cell(14, cols[0]).value, datetime.datetime) else 7
    months = [md.cell(hdr_row, c).value for c in cols]

    def row_of(name, r1=8, r2=40):
        return _find_row(md, name, r1, r2)

    def series(r):
        return [md.cell(r, c).value if isinstance(md.cell(r, c).value, (int, float))
                else 0 for c in cols]

    def total(r):
        return round(sum(series(r)), 2) if r else 0.0

    r_open = row_of("Accounts Opened via Invitation")
    r_cum = row_of("Cumulative From Invitation")
    r_bal = row_of("Average Balance per Account")
    r_profit = row_of("Account Profit Contribution")
    r_exp = row_of("Total Expense", 20, 45)
    r_net = row_of("Profit Contribution to Date", 20, 50)

    # The revenue component rows differ per client in BOTH label and position:
    # 1705 has NSF/OD Fees + Other Fees; 1075 has NSF Fees + Service Charges;
    # 1537 adds Other Charges and shifts every later row down one. So take every
    # labelled row between "Incremental Revenue" and "Account Profit
    # Contribution" and fold it into the four buckets the deck reports.
    r_inc = row_of("Incremental Revenue")
    buckets = {"Spread on Deposits": 0.0, "Interchange Income": 0.0,
               "NSF / OD Fees": 0.0, "Other Fees": 0.0}
    comp_rows = {}
    if r_inc and r_profit:
        for r in range(r_inc + 1, r_profit):
            lab, _ = _label(md, r)
            if not lab:
                continue
            low = lab.lower()
            if "spread" in low:
                key = "Spread on Deposits"
            elif "interchange" in low:
                key = "Interchange Income"
            elif "nsf" in low:
                key = "NSF / OD Fees"
            else:                      # Other Fees / Service Charges / Other Charges
                key = "Other Fees"
            buckets[key] += total(r)
            comp_rows.setdefault(key, []).append(lab)
    r_spread = row_of("Spread on Deposits")
    r_inter = row_of("Interchange Income")
    r_nsf = next((r for r in range(r_inc + 1, r_profit)
                  if (_label(md, r)[0] or "").lower().startswith("nsf")), None) \
        if (r_inc and r_profit) else None

    revenue = {
        "scope": "ICS-originated checking accounts; revenue program-to-date",
        "components": [{"name": k, "amount": round(v, 2)}
                       for k, v in buckets.items()],
        "total": total(r_profit),
        "_component_rows": comp_rows,
    }

    # ---- Value of ICS Accts -> performance
    va = wb["Value of ICS Accts"]

    def va_num(name):
        r = _find_row(va, name, 1, 30)
        return _value_after(va, r) if r else None

    apc = va_num("Actual Annual Profit Contribution") or 0
    cost = va_num("ICS Cost per Acquired Account") or 0
    life_ind = va_num("Average Life of Account In") or 0
    life_ics = va_num("Life of ICS Accounts") or 0
    pct_added = va_num("% Added Life of ICS Account") or 0
    roi_wb = va_num("Return on Investment")
    accounts = va_num("Accounts Opened via Invitation") or 0

    performance = {
        "roi": round(roi_wb, 2) if isinstance(roi_wb, (int, float)) else 0,
        "annual_profit_per_account": round(apc, 2),
        "average_account_life_years": round(life_ind, 2),
        "lifetime_value_per_account": round(apc * life_ics, 2),
        "cost_per_account": round(cost, 2),
        "payback_months": round(cost / apc * 12) if apc else 0,
        "life_of_ics_account_years": round(life_ics, 2),
        "pct_added_life": round(pct_added, 4),
    }

    # ---- weighted average balance
    bal = series(r_bal) if r_bal else []
    acc = series(r_open) if r_open else []
    den = sum(acc) or 1
    avg_balance = round(sum(b * a for b, a in zip(bal, acc)) / den, 2)

    financial_summary = {
        "account_profit_contribution": revenue["total"],
        "total_program_expense": total(r_exp),
        "net_profit": total(r_net),
        "present_value_new_accounts": 0,
        "ics_accounts": int(accounts),
        "average_balance": avg_balance,
        "roi": performance["roi"],
    }

    # ---- monthly detail: last 9 cohorts
    n = min(9, len(cols))
    tail = cols[-n:]

    def tser(r):
        if not r:
            return [0] * len(tail)
        return [round(md.cell(r, c).value, 2)
                if isinstance(md.cell(r, c).value, (int, float)) else 0
                for c in tail]

    def tser_other(rows):
        """Other-fee rows vary per client — sum whichever exist."""
        acc = [0] * len(tail)
        for r in rows or []:
            for i, v in enumerate(tser(r)):
                acc[i] = round(acc[i] + v, 2)
        return acc

    other_rows = []
    if r_inc and r_profit:
        for r in range(r_inc + 1, r_profit):
            lab, _ = _label(md, r)
            low = (lab or "").lower()
            if lab and not any(k in low for k in ("spread", "interchange", "nsf")):
                other_rows.append(r)

    monthly_detail = {
        "_note": ("Last %d opening-month cohorts. Revenue-only per cohort; "
                  "per-account-per-month = cohort revenue / accounts opened / "
                  "months open." % n),
        "months": [md.cell(hdr_row, c).value.strftime("%b %y") for c in tail],
        # The axis token beside the prose label. The chart renderers read this;
        # they never slice "months" ("Jul 26" was being cut to a bare "Jul" on
        # the per-account grid, on a series that spans a year boundary).
        "axis_months": [md.cell(hdr_row, c).value.strftime("%b%y") for c in tail],
        "accounts_opened": [int(x) for x in tser(r_open)],
        "cumulative_accounts": [int(x) for x in tser(r_cum)],
        "avg_balance": tser(r_bal),
        "interchange": tser(r_inter),
        "nsf_od": tser(r_nsf),
        "spread": tser(r_spread),
        "other_fees": tser_other(other_rows),
        "profit_contribution": tser(r_profit),
    }

    # ---- Life of Account Data -> benchmark
    lo = wb["Life of Account Data"]
    ptd = _find_row(lo, "Program to Date", 10, 20)
    l12 = _find_row(lo, "Last 12 Months", 10, 20)

    def lrow(r):
        return [lo.cell(r, c).value for c in range(1, 9)]

    non_open = non_closed = non_rate = ics_open = ics_rate12 = 0
    if ptd:
        v = [x for x in lrow(ptd) if isinstance(x, (int, float))]
        if len(v) >= 6:
            non_open, non_closed, non_rate, ics_open = v[0], v[1], v[2], v[3]
    if l12:
        v = [x for x in lrow(l12) if isinstance(x, (int, float))]
        if len(v) >= 6:
            ics_rate12 = v[5]

    tot_open = (non_open or 0) + (ics_open or 0)
    benchmark = {
        "non_ics_close_rate_pct": round((non_rate or 0) * 100, 1),
        "metrics": [
            {"label": "% of Total Openings",
             "velocity_avg": 29,
             "client": round(100 * (ics_open or 0) / tot_open) if tot_open else 0,
             "fmt": "pct0"},
            {"label": "Lifetime Value", "velocity_avg": 1828,
             "client": round(performance["lifetime_value_per_account"]),
             "fmt": "usd0"},
            # velocity_avg = the ICS close rate over the last 12 months; client =
            # this client's non-ICS close rate program-to-date. Reproduces 1705
            # (6.7 vs 21.0) — confirm the intended pairing with Aaron.
            {"label": "12 M Close Rate",
             "velocity_avg": round((ics_rate12 or 0) * 100, 1),
             "client": round((non_rate or 0) * 100, 1),
             "fmt": "pct1", "lower_is_better": True},
            {"label": "Average Life of Account",
             "velocity_avg": performance["average_account_life_years"],
             "client": performance["life_of_ics_account_years"],
             "fmt": "years"},
        ],
    }

    wb.close()
    return {"performance": performance, "revenue": revenue,
            "financial_summary": financial_summary,
            "monthly_detail": monthly_detail, "benchmark": benchmark,
            "contacts": CONTACTS,
            "mystery_shop": {"include": False, "_status": "skip"}}


def diff(new, old, path=""):
    out = []
    if isinstance(old, dict) and isinstance(new, dict):
        for k in sorted(set(old) | set(new)):
            if k.startswith("_"):
                continue
            out += diff(new.get(k), old.get(k), f"{path}.{k}")
    elif isinstance(old, list) and isinstance(new, list):
        if len(old) != len(new):
            out.append(f"{path}: len {len(new)} vs {len(old)}")
        else:
            for i, (a, b) in enumerate(zip(new, old)):
                out += diff(a, b, f"{path}[{i}]")
    else:
        if isinstance(old, (int, float)) and isinstance(new, (int, float)):
            if abs(new - old) > max(0.02, abs(old) * 0.001):
                out.append(f"{path}: {new} vs {old}")
        elif old != new and old is not None:
            out.append(f"{path}: {new!r} vs {old!r}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workbook")
    ap.add_argument("client_json")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    sections = extract(a.workbook)
    data = json.load(open(a.client_json))

    populated = [k for k in sections if data.get(k)]
    if populated:
        print(f"validating against populated sections: {', '.join(populated)}")
        bad = []
        for k in populated:
            bad += diff(sections[k], data[k], k)
        print("  DIFFS:" if bad else "  all fields match")
        for b in bad:
            print("   ", b)

    if a.write:
        data.update(sections)
        meta = data.setdefault("meta", {})
        meta["workbook"] = os.path.basename(a.workbook)
        json.dump(data, open(a.client_json, "w"), indent=1, ensure_ascii=False)
        print(f"  wrote {a.client_json}")
    else:
        print(json.dumps(sections, indent=1)[:1200])


if __name__ == "__main__":
    main()
