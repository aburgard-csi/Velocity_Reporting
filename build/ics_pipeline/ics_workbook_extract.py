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
import re
import sys
import warnings

import openpyxl

warnings.filterwarnings("ignore")

# Velocity's program-wide 12-month close rate, the benchmark the client's own ICS
# rate is shown against on the Comparisons slide. A CONSTANT, like the 29% of
# openings and $1,828 lifetime value beside it — all three are read off the
# template's "Velocity Clients' Average" column and none is computed per client.
#
# It used to be filled with the client's OWN ICS close rate, which made the row
# compare a client against themselves. That went unnoticed because the first
# client it was checked against, CoastLife 1705, happened to have a 6.7% ICS rate
# — identical to this benchmark, so the column looked right.
VELOCITY_CLOSE_RATE_12M_PCT = 6.7

# No contact list here. The workbook sections used to carry a standing `contacts` card that
# named one CSM for every client; the Contact Us card is now the client's managing CSM, looked
# up at build time by rpe_env.csm_contact (Aaron, 2026-09-16), and build_ics_gen ignores any
# `contacts` a sheet still carries.


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

    # Program start = the FIRST month that opened an account via invitation
    # (Aaron, 2026-09-01). `build_ics_gen` needs it to decide whether a programme
    # is inside its first two years, in which case Present Value uses the 6.9-year
    # Velocity life rather than the client's own modelled life. No client sheet
    # has ever carried the field, so that rule had never once fired: every client
    # fell through to "assume mature" and was valued on their modelled life —
    # 11.58 years on 1537. Derived here because Monthly Detail is the programme's
    # own record and needs no second source.
    # Computed HERE, not in the return: the workbook is opened read_only and is
    # closed before extract() returns, so a lazy read at return time raises
    # "ZIP archive that was already closed".
    program_start = None
    if r_open:
        for _m, _v in zip(months, series(r_open)):
            if _v and isinstance(_m, datetime.datetime):
                program_start = _m.strftime("%Y-%m")
                break
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
    # The workbook's own Present Value ("Present Value of New ICS Accounts @ 3%") and its
    # per-account figure: the deck carries these and the workbook's ROI rather than a
    # recalculation (Aaron, 2026-10-13, "Carry the workbook's ROI figures"). A VIP pull has
    # neither, and build_ics_gen falls back to the recalculation for it, stated in the notes.
    pv_total_wb = va_num("Present Value of New ICS Accounts")
    pv_per_wb = va_num("Present Value Per Account")

    performance = {
        "roi": round(roi_wb, 2) if isinstance(roi_wb, (int, float)) else 0,
        "annual_profit_per_account": round(apc, 2),
        "average_account_life_years": round(life_ind, 2),
        "lifetime_value_per_account": round(apc * life_ics, 2),
        "cost_per_account": round(cost, 2),
        "payback_months": round(cost / apc * 12) if apc else 0,
        "life_of_ics_account_years": round(life_ics, 2),
        "pct_added_life": round(pct_added, 4),
        "present_value_per_account": round(pv_per_wb, 2) if isinstance(pv_per_wb, (int, float)) else 0,
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
        "present_value_new_accounts": round(pv_total_wb, 2) if isinstance(pv_total_wb, (int, float)) else 0,
        "ics_accounts": int(accounts),
        "average_balance": avg_balance,
        "roi": performance["roi"],
    }

    # ---- monthly detail: the newest 12 cohorts (Aaron, 2026-10-13; nine until then)
    n = min(12, len(cols))
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

    # The whole tab, every cohort column, for the deck's ICS appendix (Aaron, 2026-10-13:
    # "Add the full monthly detail to an ICS appendix"). Same rows as the nine-cohort block
    # plus the expense and profit-to-date rows; one column per opening-month cohort.
    def fser(r):
        return [round(md.cell(r, c).value, 2) if isinstance(md.cell(r, c).value, (int, float)) else 0
                for c in cols]

    def fser_other(rows_):
        acc_ = [0] * len(cols)
        for r in rows_ or []:
            for i, v in enumerate(fser(r)):
                acc_[i] = round(acc_[i] + v, 2)
        return acc_

    other_rows_all = []
    if r_inc and r_profit:
        for r in range(r_inc + 1, r_profit):
            lab, _ = _label(md, r)
            low = (lab or "").lower()
            if lab and not any(k in low for k in ("spread", "interchange", "nsf")):
                other_rows_all.append(r)
    monthly_detail_full = {
        "_note": ("The full 'Monthly Detail' tab: one column per opening-month cohort, each cohort's "
                  "figures life to date. Rendered as the ICS appendix."),
        "months": [m.strftime("%b %y") for m in months],
        "accounts_opened": [int(x) for x in fser(r_open)],
        "cumulative_accounts": [int(x) for x in fser(r_cum)],
        "avg_balance": fser(r_bal),
        "spread": fser(r_spread),
        "interchange": fser(r_inter),
        "nsf_od": fser(r_nsf),
        "other_fees": fser_other(other_rows_all),
        "profit_contribution": fser(r_profit),
        "total_expense": fser(r_exp),
        "profit_to_date": fser(r_net),
    }

    monthly_detail = {
        "_note": ("Last %d opening-month cohorts. Revenue-only per cohort; "
                  "per-account-per-month = cohort revenue / accounts opened / "
                  "months open." % n),
        "months": [md.cell(hdr_row, c).value.strftime("%b %y") for c in tail],
        "accounts_opened": [int(x) for x in tser(r_open)],
        "cumulative_accounts": [int(x) for x in tser(r_cum)],
        "avg_balance": tser(r_bal),
        "interchange": tser(r_inter),
        "nsf_od": tser(r_nsf),
        "spread": tser(r_spread),
        "other_fees": tser_other(other_rows),
        "profit_contribution": tser(r_profit),
        # The workbook's expense per cohort (its "Total Expense" row, the referral fee), for the
        # Program Results by Month Opened table in place of a constant amortization row (2026-10-13).
        "total_expense": tser(r_exp),
    }

    # ---- Life of Account Data -> benchmark
    lo = wb["Life of Account Data"]
    # PROGRAM TO DATE for every life-of-account metric (Aaron, 2026-10-13: "Program-to-date
    # everywhere", after Cindy's "YTD ONLY" on KEMBA's Comparisons). This reverses the
    # 2026-09-01 choice of the Last 12 Months row, made because program-to-date close rates
    # (51.66% non-ICS on Austin against 6.45% over the last year) are not comparable with a
    # 12-month figure — so the Velocity close-rate average, a 12-month benchmark, is named as
    # such in the notes. A workbook with no Program to Date row falls back to Last 12 Months,
    # and `window` says which row the figures came from.
    r_ptd = _find_row(lo, "Program to Date", 10, 20)
    l12 = _find_row(lo, "Last 12 Months", 10, 20)
    r_win = r_ptd or l12
    if not r_win:
        # Every life-of-account metric comes from this one row, so losing it is not a
        # degraded result, it is no result. Without this the six values stay 0 and the deck
        # ships a 0.0% close rate and 0% of openings — figures a reader cannot tell from real
        # ones. Missing source data is stated, never zeroed (CLAUDE.md).
        raise SystemExit("ERROR: no 'Program to Date' or 'Last 12 Months' row in 'Life of Account "
                         "Data' (searched rows 10-20) — refusing to emit zeroed life-of-account metrics")
    window = "program-to-date" if r_ptd else "12-month"

    def lrow(r):
        return [lo.cell(r, c).value for c in range(1, 9)]

    # 'Life of Account Data' columns B..G, per the sheet's own header row:
    #   B Non-ICS Opened | C Non-ICS Closed | D Non-ICS Closed RATE
    #   E ICS Opened     | F ICS Closed     | G ICS Closed RATE
    non_open12 = non_closed12 = non_rate12 = 0
    ics_open12 = ics_closed12 = ics_rate12 = 0
    v = [x for x in lrow(r_win) if isinstance(x, (int, float))]
    if len(v) >= 6:
        (non_open12, non_closed12, non_rate12,
         ics_open12, ics_closed12, ics_rate12) = v[0], v[1], v[2], v[3], v[4], v[5]

    tot_open = (non_open12 or 0) + (ics_open12 or 0)
    benchmark = {
        "window": window,
        # The footnote names the window this figure carries; it used to be handed the
        # program-to-date figure under a 12-month label (Marine 1539: 35.5% where the
        # 12-month rate was 10.4%). Whatever the window, label and figure now agree.
        "non_ics_close_rate_pct": round((non_rate12 or 0) * 100, 1),
        "metrics": [
            {"label": "% of Total Openings",
             "velocity_avg": 29,
             "client": round(100 * (ics_open12 or 0) / tot_open) if tot_open else 0,
             "fmt": "pct0"},
            {"label": "Lifetime Value", "velocity_avg": 1828,
             "client": round(performance["lifetime_value_per_account"]),
             "fmt": "usd0"},
            # The client column is this client's ICS accounts only (Aaron,
            # 2026-09-01); the non-ICS rate belongs in the footnote and nowhere
            # else. It used to be inverted: `client` carried the NON-ICS
            # program-to-date rate while the client's own ICS rate sat in the
            # Velocity-average column, so the row compared the client against
            # themselves and labelled neither side correctly.
            {"label": "Close Rate" if r_ptd else "12 M Close Rate",
             "velocity_avg": VELOCITY_CLOSE_RATE_12M_PCT,
             "client": round((ics_rate12 or 0) * 100, 1),
             "fmt": "pct1", "lower_is_better": True},
            {"label": "Average Life of Account",
             "velocity_avg": performance["average_account_life_years"],
             "client": performance["life_of_ics_account_years"],
             "fmt": "years"},
        ],
    }

    # The data month the tab names ("August 2026 Data"), else the last month column: the month
    # the workbook-driven slides are stamped with when the workbook is older than the deck.
    workbook_month = None
    for r in range(1, hdr_row):
        for c in range(1, 8):
            v = md.cell(r, c).value
            if isinstance(v, str):
                mm = re.match(r"^\s*([A-Z][a-z]+ \d{4}) Data\s*$", v)
                if mm:
                    workbook_month = mm.group(1)
    if not workbook_month and months:
        workbook_month = months[-1].strftime("%B %Y")

    wb.close()
    return {"_program_start": program_start, "_workbook_month": workbook_month,
            "performance": performance, "revenue": revenue,
            "financial_summary": financial_summary,
            "monthly_detail": monthly_detail, "monthly_detail_full": monthly_detail_full,
            "benchmark": benchmark,
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
    program_start = sections.pop("_program_start", None)
    workbook_month = sections.pop("_workbook_month", None)
    data = json.load(open(a.client_json, encoding="utf-8"))

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
        # The extractor has no mystery-shop figures; its placeholder must never replace a block
        # the sheet carries, nor be added to a sheet that has none (Rosedale 1738, 2026-10-15:
        # the re-extract wrote {"include": false, "_status": "skip"} over nothing, harmless
        # that time, and would have erased a real block from a VIP pull).
        if sections.get("mystery_shop", {}).get("_status") == "skip":
            sections.pop("mystery_shop")
        data.update(sections)
        meta = data.setdefault("meta", {})
        meta["workbook"] = os.path.basename(a.workbook)
        if program_start:
            meta["program_start"] = program_start
        if workbook_month:
            meta["workbook_month"] = workbook_month
        json.dump(data, open(a.client_json, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print(f"  wrote {a.client_json}")
    else:
        print(json.dumps(sections, indent=1)[:1200])


if __name__ == "__main__":
    main()
