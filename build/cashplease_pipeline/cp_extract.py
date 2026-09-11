#!/usr/bin/env python3
"""
cp_extract.py — CashPlease weekly workbook -> per-client data packs.

Input is the `CashPleaseSummaryV1_<yymmdd>_<hhmmss>.xlsx` Bradford Sanders emails
weekly ("CashPlease Summary"). It carries one `All Clients Summary - Loans` rollup
tab plus one tab per client, all on an identical layout:

    B2   'CashPlease Loan Summary'
    B4   'All Clients Rollup'            <- literal on EVERY tab, client or not
    B6   'Report Generated: <m/d/yyyy h:mm:ss AM>'
    L8   Percentage of Active Accounts with Loans   (fraction)
    L9   Charge Off %                               (fraction)
    B11  'Loans By Status' header; J/K/L = Principal / Interest / # of Loans
    B12..B18  Pending Processing Funded 'Paid Off' Overdue 'Charged Off' Closed
    B19  'TOTAL '
    B21  time-series header; rows 22+ are the series, oldest last.
         A label ending '*' is a MONTH ROLL-UP; an unsuffixed label is a single
         day in the current (partial) month. The last row is the '* - Month
         roll-up' footnote, not data.

B4 says "All Clients Rollup" on every tab, so a client's identity comes from the
SHEET NAME only, which Excel caps at 31 characters — '1539-Marine Federal Credit Uni'
is truncated mid-word. Truncated names are resolved through NAME_OVERRIDES and
anything still truncated is flagged rather than printed onto a slide.

The peer benchmark is the `All Clients Summary - Loans` tab: the all-accounts
cohort across every CashPlease client (Aaron, 2026-09-01). The two percentages are
taken as reported — neither is derivable from the tab's own totals (WesBanco's
charge-off 11.3721% is neither 736,572/7,398,045 nor 1,244/11,869) — and the money
ratios are computed from the rollup totals.

Usage:
    python cp_extract.py <workbook.xlsx> <out_dir>
"""
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

import openpyxl

ROLLUP_SHEET = "All Clients Summary - Loans"
STATUSES = ["Pending", "Processing", "Funded", "Paid Off",
            "Overdue", "Charged Off", "Closed"]

# Sheet names are capped at 31 chars by Excel. Full delivery names, keyed by client
# id, for every tab whose sheet name is truncated. Sourced from the Obsidian client
# folders and the weekly ILS Program Review schedule.
NAME_OVERRIDES = {
    "1838": "American Eagle Financial Credit Union",
    "1803": "First Source Federal Credit Union",
    "1138": "Arizona Federal Credit Union",
    "1790": "Jonestown Bank and Trust",
    "1445": "First National Bank of Pennsylvania",
    "1750": "All In Federal Credit Union",
    "1472": "Springs Valley Bank & Trust",
    "1734": "Altamaha Bank and Trust Company",
    "1741": "Del-One Federal Credit Union",
    "1164": "First Federal Savings Bank",
    "1671": "Pasadena Federal Credit Union",
    "1729": "First Family Federal Credit Union",
    "1690": "United Heritage Credit Union",
    "1585": "First Community Bank of Tennessee",
    "1217": "Pioneer Federal Credit Union",
    "1748": "Clearview Federal Credit Union",
    "1539": "Marine Federal Credit Union",
    "1049": "First National Bank and Trust",
    "1776": "CoastHills Credit Union",
    "1524": "Peninsula Community FCU",
    "1632": "WesBanco Bank, Inc.",
    # These three land exactly on the 30-char cap but are complete names, not cuts.
    # They are listed so the truncation check has an answer rather than a warning.
    "1711": "Coosa Valley Credit Union",
    "1526": "Clark County Credit Union",
    "1512": "Citizens National Bank TN",
}

# Tabs that are not deliverable clients.
SKIP_IDS = {
    "114301",   # 'enterpoints akoub micro' — internal test tab, not a client
}

# Programs confirmed cancelled — data still lands in the workbook (CLAUDE.md: a file
# is evidence a program WAS running, never proof it still is).
CANCELLED = {
    "1658": "CashPlease cancelled (Aaron, 2026-09-01)",
}


def _num(v):
    """Workbook numerics arrive as int, float or None; money cells are never text."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", "").replace("$", "").strip())
    except ValueError:
        return 0.0


def split_sheet_name(name):
    """'1632-WesBanco Bank, Inc.' -> ('1632', 'WesBanco Bank, Inc.', truncated?)."""
    m = re.match(r"^(\d+)-(.*)$", name.strip())
    if not m:
        return None, name.strip(), False
    cid, raw = m.group(1), m.group(2).strip()
    # The generator caps sheet names at 30 characters. A name landing exactly on the
    # cap is USUALLY cut mid-word, but not always — 'Coosa Valley Credit Union' and
    # 'Clark County Credit Union' fit exactly. Length alone cannot tell them apart, so
    # every 30-char name needs a NAME_OVERRIDES entry; the flag is what forces one.
    truncated = len(name) == 30 and cid not in NAME_OVERRIDES
    return cid, NAME_OVERRIDES.get(cid, raw), truncated


def read_sheet(ws):
    """Pull the fixed-layout block out of one tab."""
    gen = str(ws["B6"].value or "")
    gen = gen.replace("Report Generated:", "").strip()

    status = {}
    for i, label in enumerate(STATUSES):
        r = 12 + i
        status[label] = {
            "principal": _num(ws.cell(r, 10).value),
            "interest": _num(ws.cell(r, 11).value),
            "loans": int(_num(ws.cell(r, 12).value)),
        }
    total = {
        "principal": _num(ws.cell(19, 10).value),
        "interest": _num(ws.cell(19, 11).value),
        "loans": int(_num(ws.cell(19, 12).value)),
    }

    daily, monthly = [], []
    for r in range(22, ws.max_row + 1):
        label = ws.cell(r, 2).value
        if label is None:
            continue
        label = str(label).strip()
        if label.startswith("*") or "roll-up" in label.lower():
            continue                      # the '* - Month roll-up' footnote
        raw = label.rstrip("*")
        row = {
            "period": raw,
            # `periods.mon_yy` — the one axis-label helper — parses 'YYYY-MM' but not
            # the 'YYYY-MM-DD' month-ends this workbook writes, and it returns what it
            # cannot parse UNCHANGED, so axes silently drew '2026-07-31'. Normalising
            # here is deliberate: teaching the shared parser to read YYYY-MM-DD as a
            # month would collapse every genuine daily axis in the other pipelines to
            # one label. Only this extractor knows these rows are month roll-ups.
            "period_month": raw[:7] if re.match(r"^\d{4}-\d{2}-\d{2}$", raw) else raw,
            "loans": int(_num(ws.cell(r, 12).value)),
            "principal": _num(ws.cell(r, 10).value),
            "interest": _num(ws.cell(r, 11).value),
            "funded": int(_num(ws.cell(r, 5).value)),
            "paid_off": int(_num(ws.cell(r, 6).value)),
            "overdue": int(_num(ws.cell(r, 7).value)),
            "charged_off": int(_num(ws.cell(r, 9).value)),
        }
        (monthly if label.endswith("*") else daily).append(row)

    return {
        "report_generated": gen,
        "pct_active_accounts_with_loans": _num(ws["L8"].value),
        "charge_off_pct": _num(ws["L9"].value),
        "status": status,
        "total": total,
        "daily": daily,       # current partial month, newest first
        "monthly": monthly,   # completed months, newest first
    }


def loans_in_window(pack, months=12):
    """Loans booked over the most recent completed months, and the window used.

    Program-to-date volume cannot be compared between clients: a client three years
    live outsells one three months live no matter how either is performing. A fixed
    trailing window is comparable — for anyone who has been live long enough to fill
    it. Clients who have not are reported over the window they actually have, and the
    window is returned so the deck can say which, and can keep a short-tenure client
    out of a peer comparison it would lose on tenure alone.
    """
    rows = pack["monthly"][:months]          # newest first
    return sum(r["loans"] for r in rows), len(rows)


def peer_pack(roll, cohort_tabs, tab_loan_sum):
    """Peer benchmark from the all-accounts cohort — every CashPlease client.

    The two percentages are reported values, not derivations. The money ratios come
    from the cohort's own totals so they are reproducible from the same tab.

    The rollup is the sum of EVERY tab in the workbook — verified here, not assumed.
    That includes tabs this pipeline does not build a deck for: the `enterpoints`
    internal test tab and any client whose program has been cancelled. So the cohort
    is described by its tab count, never by a client count derived from the filtered
    roster; those two numbers are not the same and printing one for the other would
    put a figure on a slide that nothing in the workbook supports.
    """
    tot = roll["total"]
    loans = tot["loans"] or 1
    return {
        "cohort": "All Velocity CashPlease clients",
        "cohort_tabs": cohort_tabs,
        "cohort_reconciles": tab_loan_sum == tot["loans"],
        "pct_active_accounts_with_loans": roll["pct_active_accounts_with_loans"],
        "charge_off_pct": roll["charge_off_pct"],
        "avg_loan_size": tot["principal"] / loans,
        "avg_interest_per_loan": tot["interest"] / loans,
        "total_loans": tot["loans"],
        "total_principal": tot["principal"],
        "pct_loans_overdue": roll["status"]["Overdue"]["loans"] / loans,
        "pct_loans_charged_off": roll["status"]["Charged Off"]["loans"] / loans,
        "pct_loans_paid_off": roll["status"]["Paid Off"]["loans"] / loans,
    }


def client_metrics(pack, dda_rec):
    """Derived per-client figures.

    Note what is NOT here: the workbook's `Percentage of Active Accounts with Loans`
    (L8). It is kept on the pack for audit but is never put on a slide, because an
    account can take more than one CashPlease loan, so a loan count over an account
    base cannot be read as the SHARE OF ACCOUNTS that borrowed (Aaron, 2026-09-01) —
    and the workbook does not say what its denominator is. In its place is a rate
    this pipeline computes and can define: loans booked over DDA accounts, per 1,000.
    That is a volume rate, not a penetration rate, and it is labelled as one.
    """
    tot = pack["total"]
    loans = tot["loans"] or 1
    st = pack["status"]
    win_loans, win_months = loans_in_window(pack, 12)

    m = {
        "total_loans": tot["loans"],
        "total_principal": tot["principal"],
        "total_interest": tot["interest"],
        "active_loans": st["Funded"]["loans"],
        "active_principal": st["Funded"]["principal"],
        "avg_loan_size": tot["principal"] / loans,
        "avg_interest_per_loan": tot["interest"] / loans,
        "charge_off_pct": pack["charge_off_pct"],
        "pct_loans_overdue": st["Overdue"]["loans"] / loans,
        "pct_loans_charged_off": st["Charged Off"]["loans"] / loans,
        "pct_loans_paid_off": st["Paid Off"]["loans"] / loans,
        "window_loans": win_loans,
        "window_months": win_months,
        # Populated only when a DDA count exists. Absent means unknown, not zero.
        "dda_accounts": None,
        "dda_last_updated": None,
        "dda_stale_days": None,
        "loans_per_1k_dda": None,
        "dda_missing_reason": None,
        "peer_comparable": False,
    }
    if not dda_rec:
        m["dda_missing_reason"] = (
            "no DDA count for this client in the ILS Management Server report — "
            "either they are not on ILS or their count came through as NULL")
        return m

    m["dda_accounts"] = dda_rec["dda_accounts"]
    m["dda_last_updated"] = dda_rec.get("last_updated")
    # How far the denominator trails the numerator. The DDA report carries a per-client
    # import date and some run months behind — 1044 Trustmark was still 2026-04-09 in
    # the 2026-08-27 send. A rate built on a stale base is not wrong, but the deck has
    # to be able to say how stale.
    try:
        gen = datetime.strptime(pack["report_generated"].split()[0], "%m/%d/%Y").date()
        upd = date.fromisoformat(m["dda_last_updated"])
        m["dda_stale_days"] = (gen - upd).days
    except (ValueError, IndexError, TypeError):
        m["dda_stale_days"] = None
    if dda_rec["dda_accounts"] > 0:
        m["loans_per_1k_dda"] = win_loans / dda_rec["dda_accounts"] * 1000
    # Only a filled 12-month window is comparable against the cohort; a client five
    # months live would lose the comparison on tenure, not on performance.
    m["peer_comparable"] = bool(m["loans_per_1k_dda"] is not None and win_months >= 12)
    return m


def main():
    if len(sys.argv) not in (3, 4):
        raise SystemExit(__doc__.strip())
    wb_path, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    dda = {"sent": None, "clients": {}, "null_counts": []}
    if len(sys.argv) == 4:
        dda = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.load_workbook(wb_path, data_only=True)
    if ROLLUP_SHEET not in wb.sheetnames:
        raise SystemExit(f"no {ROLLUP_SHEET!r} tab in {wb_path.name} — wrong workbook?")

    roll = read_sheet(wb[ROLLUP_SHEET])

    # Reconcile the rollup against the tabs before anything is built on it.
    client_tabs = [n for n in wb.sheetnames if n != ROLLUP_SHEET]
    tab_loan_sum = sum(int(_num(wb[n].cell(19, 12).value)) for n in client_tabs)
    peer = peer_pack(roll, len(client_tabs), tab_loan_sum)

    index, flags, records = [], [], []
    if not peer["cohort_reconciles"]:
        flags.append(f"rollup TOTAL ({roll['total']['loans']:,} loans) does not equal "
                     f"the sum of the {len(client_tabs)} client tabs "
                     f"({tab_loan_sum:,}) — peer figures may not be the cohort they "
                     f"claim to be; check the workbook before delivering")
    for name in wb.sheetnames:
        if name == ROLLUP_SHEET:
            continue
        cid, client, truncated = split_sheet_name(name)
        if cid is None:
            flags.append(f"{name!r}: sheet name carries no client id — skipped")
            continue
        if cid in SKIP_IDS:
            continue
        pack = read_sheet(wb[name])
        if pack["total"]["loans"] == 0:
            flags.append(f"{cid} {client}: no loans in the workbook — no deck built")
            continue
        if truncated:
            flags.append(f"{cid}: sheet name {name!r} is truncated and has no "
                         f"NAME_OVERRIDES entry — add one before delivering")
        rec = {
            "client_id": cid,
            "client_name": client,
            "sheet_name": name,
            "source_file": wb_path.name,
            "dda_source": dda.get("source_file"),
            "dda_sent": dda.get("sent"),
            "name_truncated": truncated,
            "cancelled": CANCELLED.get(cid),
            **pack,
            "metrics": client_metrics(pack, dda["clients"].get(cid)),
        }
        records.append(rec)
        index.append({
            "client_id": cid,
            "client_name": client,
            "loans": pack["total"]["loans"],
            "cancelled": CANCELLED.get(cid),
        })

    # ---- second pass: the cohort rate, built ONLY from clients that can be in it.
    # Summing 12-month loans over the whole rollup and dividing by the DDAs we happen
    # to have would put loans in the numerator whose accounts are missing from the
    # denominator, and inflate every client's comparison against it.
    inc = [r for r in records
           if r["metrics"]["peer_comparable"] and not r["cancelled"]]
    peer["cohort_dda_clients"] = len(inc)
    peer["cohort_dda_accounts"] = sum(r["metrics"]["dda_accounts"] for r in inc)
    peer["cohort_window_loans"] = sum(r["metrics"]["window_loans"] for r in inc)
    peer["loans_per_1k_dda"] = (
        peer["cohort_window_loans"] / peer["cohort_dda_accounts"] * 1000
        if peer["cohort_dda_accounts"] else None)
    (out_dir / "peer_benchmark.json").write_text(
        json.dumps(peer, indent=2), encoding="utf-8")

    no_dda = [f"{r['client_id']} {r['client_name']}" for r in records
              if r["metrics"]["dda_accounts"] is None and not r["cancelled"]]
    if no_dda:
        flags.append(f"{len(no_dda)} client(s) have no DDA count, so no loans-per-DDA "
                     f"rate is shown for them (stated on the slide, never zeroed): "
                     + ", ".join(no_dda))
    short = [f"{r['client_id']} {r['client_name']} ({r['metrics']['window_months']}mo)"
             for r in records
             if r["metrics"]["dda_accounts"] is not None
             and not r["metrics"]["peer_comparable"] and not r["cancelled"]]
    if short:
        flags.append(f"{len(short)} client(s) have under 12 completed months, so they "
                     f"carry a rate over a shorter window and are kept out of the "
                     f"peer comparison: " + ", ".join(short))

    for rec in records:
        rec["metrics"]["peer"] = peer
        (out_dir / f"{rec['client_id']}_cashplease.json").write_text(
            json.dumps(rec, indent=2), encoding="utf-8")

    (out_dir / "index.json").write_text(json.dumps({
        "source_file": wb_path.name,
        "dda_sent": dda.get("sent"),
        "report_generated": roll["report_generated"],
        "clients": index,
        "flags": flags,
    }, indent=2), encoding="utf-8")

    print(f"{len(index)} client packs -> {out_dir}")
    for f in flags:
        print("  flag:", f)


if __name__ == "__main__":
    main()
