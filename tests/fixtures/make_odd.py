#!/usr/bin/env python3
"""
make_odd.py — generate a small, deterministic, synthetic ODD extract.

The repo had no tests because every fix was verified by rebuilding a real client
deck and eyeballing it. That needs a real ODDD (40-95 MB, real member data, and
only in the pipeline data root). This writes an 800-row ODD with the same SHAPE — 4-row
preamble, header on row 5, the full month-column grid — carrying nothing but
invented values, so it can live in git and run anywhere.

Rows are laid out to cover the cases that have actually broken:
  * blank `Business?` (the ticket_calc/metrics_gen denominator divergence)
  * blank `Stat Desc` with a populated `Stat Code` (the 1549 Wellworth bug)
  * every lifecycle wording variant classify_status has to disambiguate
  * Reg E wording from two different cores
  * accounts at every swipe tier, including 0 and 26+
  * responders and non-responders across several mailings

Regenerate with:  python3 tests/fixtures/make_odd.py tests/fixtures/synthetic_odd.csv

Partial final month (2026-09-17). `--partial-nsf` keeps the NSF/OD items of only one
row in 40 in the latest month — the shape of Marine FCU 1539's 2026.09 extract, whose
August held 390 NSF/OD items against 19,451 in July while its swipes were whole.
`--partial-activity` does the same to that month's swipes and spend. Both are applied
AFTER every random draw, so the default fixture stays byte-identical.
"""
import csv, datetime, random, sys

SEED = 20260829          # fixed: the fixture must be byte-identical every run
N_MONTHS = 36
N_ROWS = 800
LATEST = datetime.date(2026, 7, 1)

BASE_COLS = ["5", "Acct ID", "Acct Number", "Acct Mask", "Branch", "Mailable?",
             "Prod Code", "Prod Desc", "Business?", "Stat Code", "Stat Desc",
             "DOB", "Date Opened", "Date Closed", "Avg Bal", "Curr Bal", "Debit?"]

PRODUCTS = [("CK01", "Bonus Checking", False), ("CK02", "Regular Checking", False),
            ("CK03", "Cash Back Checking", False), ("CB01", "Business Checking", True),
            ("SV01", "Savings", False)]
ELIGIBLE_PRODUCTS = {"CK01", "CK02", "CK03", "CB01"}

# (Stat Code, Stat Desc) pairs — deliberately including the blank-description
# rows that classify_status has to resolve from the code alone.
STATUSES = [("O", "Open"), ("A", "Active"), ("C", "Closed"), ("X", "Charged Off"),
            ("O", ""), ("C", ""), ("X", ""),                    # code-only rows
            ("O", "Dormant"), ("O", "Inactive"), ("O", "Frozen"),
            ("O", "New This Cycle"), ("O", "Pending Activation"),
            ("C", "Purge at Yearend"), ("C", "Pending Closeout"),
            ("O", "Manually Controlled")]                        # explicit Other

# Two cores' Reg E vocabularies, plus blank and the "Opted In" wording metrics_gen once misread
# (2026-09-16). Unmapped wording now stops metrics_gen; test_classifiers covers it directly.
REGE = ["Opt-In Accepted", "Opt-In Declined", "No Response Recevied",
        "Reg E Opt In", "Reg E Opt Out", "Reg E Default", "", "Opted In"]

# Business? — the blank is the point of this fixture.
BUSINESS = ["No", "No", "No", "No", "Yes", ""]

MAIL_CODES = ["NU", "TH-10", "TH-15", "TH-20", "TH-25"]
RESP_CODES = ["NU 5+", "TH-10", "TH-15", "TH-20", "TH-25"]


def months(n, latest):
    out, y, m = [], latest.year, latest.month
    for _ in range(n):
        out.append(f"{datetime.date(y, m, 1):%b}{str(y)[2:]}")
        m -= 1
        if m == 0:
            m = 12; y -= 1
    return list(reversed(out))


PARTIAL_KEEP = 40   # a partial month keeps one row in this many


def build(path, partial_nsf=False, partial_activity=False):
    rng = random.Random(SEED)
    ms = months(N_MONTHS, LATEST)
    latest = ms[-1]
    # every other month carries a mailing, as the real extracts do
    mail_months = [m for i, m in enumerate(ms) if i >= 12 and i % 2 == 0]

    hdr = list(BASE_COLS)
    for m in ms:
        hdr += [f"{m} Sig #", f"{m} Sig $", f"{m} PIN #", f"{m} PIN $",
                f"{m} MTD", f"{m} YTD", f"{m} Reg E Code", f"{m} Reg E Desc",
                f"{m} OD Limit"]
        if m in mail_months:
            hdr += [f"{m} Mail", f"{m} Resp"]
    hdr += [f"{latest} Elig", f"{latest} Prog"]

    # Row construction is in two parts. The first COVERAGE_ROWS rows walk every
    # special case explicitly, so a classifier case can never be dropped by
    # chance. The rest are drawn from the seeded RNG.
    #
    # Attributes are NOT keyed off `i % k` any more. Doing that silently couples
    # them: `Business?` cycled mod 6 and the open-year cycled mod 6, so the only
    # two year-buckets landing in the retention window were exactly the two
    # non-personal buckets, and the cohort came out empty every time.
    coverage = [(st, rg, bz)
                for st in STATUSES
                for rg in (REGE[0], REGE[3], REGE[6], REGE[7])
                for bz in ("No", "Yes", "")]
    rows = []
    for i in range(N_ROWS):
        if i < len(coverage):
            (stat_code, stat_desc), rege, biz = coverage[i]
            code, desc, is_biz = PRODUCTS[i % len(PRODUCTS)]
        else:
            code, desc, is_biz = rng.choice(PRODUCTS)
            stat_code, stat_desc = rng.choices(
                STATUSES, weights=[6, 6, 2, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1])[0]
            rege = rng.choice(REGE)
            biz = rng.choices(["No", "Yes", ""], weights=[88, 10, 2])[0]
        if is_biz:
            biz = "Yes"
        has_card = rng.random() < 0.86

        band = rng.choices(range(7), weights=[20, 18, 12, 11, 10, 9, 20])[0]
        lo, hi = [(0, 0), (1, 5), (6, 10), (11, 15), (16, 20), (21, 25), (26, 60)][band]

        # Open dates span the full history, with a guaranteed share inside the
        # trailing 12 months (new-account cohort) and inside the 24-month
        # retention vintage window.
        roll = rng.random()
        if roll < 0.30:                       # opened in the trailing 12 months
            back = rng.randint(0, 11)
        elif roll < 0.55:                     # opened in the retention window
            back = rng.randint(12, 35)
        else:                                 # older book
            back = rng.randint(36, 96)
        _m = LATEST.month - back
        _y = LATEST.year
        while _m <= 0:
            _m += 12; _y -= 1
        opened = datetime.date(_y, _m, rng.randint(1, 28))

        closed = ""
        if stat_code in ("C", "X"):
            _cm = LATEST.month - rng.randint(0, 23)
            _cy = LATEST.year
            while _cm <= 0:
                _cm += 12; _cy -= 1
            _cd = datetime.date(_cy, _cm, rng.randint(1, 28))
            if _cd > opened:
                closed = f"{_cd:%m/%d/%Y}"

        r = {
            "5": str(i + 1),
            "Acct ID": f"A{100000+i}",
            "Acct Number": f"{9000000+i}",
            "Acct Mask": f"****{1000+i}",
            # Three branches, not eight. metrics_gen drops a branch with fewer
            # than 15 accounts in the new-account cohort, so eight branches over
            # 800 rows left every per-branch table empty and the Reg E and
            # take-rate charts had nothing to draw.
            "Branch": str(rng.randint(1, 3)),
            "Mailable?": "No" if rng.random() < 0.08 else "Yes",
            "Prod Code": code, "Prod Desc": desc,
            "Business?": biz,
            "Stat Code": stat_code, "Stat Desc": stat_desc,
            "DOB": f"{datetime.date(rng.randint(1945, 2004), rng.randint(1,12), rng.randint(1,28)):%m/%d/%Y}",
            "Date Opened": f"{opened:%m/%d/%Y}",
            "Date Closed": closed,
            "Avg Bal": f"{rng.uniform(50, 9000):.2f}",
            "Curr Bal": f"{rng.uniform(50, 9000):.2f}",
            "Debit?": "Yes" if has_card else "No",
        }
        ytd = 0                     # NSF/OD items, calendar-year to date
        for mi, m in enumerate(ms):
            sw = rng.randint(lo, hi) if has_card else 0
            sig = sw // 2; pin = sw - sig
            sig_d = sig * rng.uniform(18, 55)
            pin_d = pin * rng.uniform(12, 40)
            if partial_activity and m == latest and i % PARTIAL_KEEP:
                sig = pin = 0; sig_d = pin_d = 0.0
            r[f"{m} Sig #"] = str(sig)
            r[f"{m} PIN #"] = str(pin)
            r[f"{m} Sig $"] = f"{sig_d:.2f}"
            r[f"{m} PIN $"] = f"{pin_d:.2f}"
            # MTD/YTD are NSF/OD ITEM COUNTS, not dollars — integers, with a
            # smoothly decaying 0/1/2/3/... frequency, matching every real
            # extract (see odd_rows.nsf and tests/test_nsf_is_items.py). The
            # fixture used to write '35.00'/'70.00', which looked like two
            # $35 fees and taught the wrong meaning.
            nsf_items = rng.choice([0, 0, 0, 0, 1, 1, 1, 2, 2, 3, 4, 6, 9])
            if partial_nsf and m == latest and i % PARTIAL_KEEP:
                nsf_items = 0
            r[f"{m} MTD"] = str(nsf_items)
            # YTD is the calendar-year cumulative of MTD, so it is an integer
            # of the same unit and never smaller than the month's own count.
            ytd = nsf_items if m.startswith("Jan") else ytd + nsf_items
            r[f"{m} YTD"] = str(ytd)
            r[f"{m} Reg E Code"] = "1" if rege else ""
            r[f"{m} Reg E Desc"] = rege
            r[f"{m} OD Limit"] = str(rng.choice([0, 500, 750]))
            if m in mail_months:
                # Only accounts on an ARS-eligible PRODUCT are ever mailed. The
                # current-snapshot `Elig` flag is deliberately NOT used here — an
                # account can have been mailed while eligible and have closed
                # since — but mailing an ineligible product never happens, and
                # allowing it produced more responders than eligible accounts.
                mailed = code in ELIGIBLE_PRODUCTS and rng.random() < 0.62
                r[f"{m} Mail"] = rng.choice(MAIL_CODES) if mailed else ""
                # ~1 mailing in 6 draws a response. Drawn, not derived from the
                # mailed test — a rule keyed off the same counter can select
                # exactly the UNMAILED rows and yield zero responders.
                r[f"{m} Resp"] = rng.choice(RESP_CODES) if (mailed and rng.random() < 0.17) else ""
        r[f"{latest} Elig"] = "Yes" if (code in ELIGIBLE_PRODUCTS and stat_code in ("O", "A")) else "No"
        r[f"{latest} Prog"] = "Yes" if rng.random() < 0.72 else "No"
        rows.append([r.get(c, "") for c in hdr])

    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Synthetic ODD extract — generated by tests/fixtures/make_odd.py"])
        w.writerow(["NOT REAL MEMBER DATA. Every value is invented."])
        w.writerow([f"Months: {ms[0]}..{ms[-1]}", f"Rows: {N_ROWS}", f"Seed: {SEED}"])
        w.writerow([])
        w.writerow(hdr)
        w.writerows(rows)
    return hdr, ms, rows


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = args[0] if args else "synthetic_odd.csv"
    hdr, ms, rows = build(out, partial_nsf="--partial-nsf" in sys.argv,
                          partial_activity="--partial-activity" in sys.argv)
    print(f"wrote {out}\n  rows {len(rows)}  cols {len(hdr)}  months {ms[0]}..{ms[-1]}")
