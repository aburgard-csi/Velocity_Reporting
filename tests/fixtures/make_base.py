#!/usr/bin/env python3
"""
make_base.py — a synthetic ARS base.json to pair with the synthetic ODD.

The ODD fixture covers the ODD-driven half of a deck. The other half comes from
the client's workbook: revenue, profit, mailing counts, the 12-month revenue
series and the 36-month swipes/spend tail. This invents those, so a deck can be
built end to end from fixtures alone with no client data anywhere.

Derived from the ODD fixture where the two must agree — `months` and the series
labels come from the same month grid — because a deck built from two fixtures
that disagree would fail the validator for the wrong reason.

Regenerate with:  python3 tests/fixtures/make_base.py <odd.csv> <out.json>
"""
import csv, datetime, json, random, re, sys

SEED = 20260829
CLIENT = "Union Financial"          # the dummy client the templates ship with


def months_from_odd(path):
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.reader(fh):
            if any(str(c).strip() == "Acct ID" for c in row):
                hdr = [str(c).strip() for c in row]
                break
        else:
            raise SystemExit("no 'Acct ID' header row in the ODD fixture")
    ms = [m.group(1) for m in
          (re.match(r"^([A-Z][a-z]{2}\d{2}) Sig #$", h) for h in hdr) if m]
    return sorted(ms, key=lambda t: datetime.datetime.strptime(t, "%b%y"))


def build(odd_csv, out):
    rng = random.Random(SEED)
    ms = months_from_odd(odd_csv)
    mail_months = ms[-24:]
    latest = datetime.datetime.strptime(ms[-1], "%b%y")

    rev12 = [(datetime.datetime.strptime(m, "%b%y").strftime("%b %Y"),
              round(rng.uniform(24000, 38000), 2)) for m in ms[-12:]]
    # Shapes copied from a real extract, not guessed: labels are "Mon YYYY",
    # spend is in MILLIONS, and mailings_recent carries two RATES per mailing
    # (NU and threshold), not a recipient count. A fixture whose shape differs
    # fails the chart code for the wrong reason.
    swipes36 = [(datetime.datetime.strptime(m, "%b%y").strftime("%b %Y"),
                 round(rng.uniform(9.5, 13.5), 2), rng.randint(9000, 14000))
                for m in ms[-36:]]
    mail12 = [(datetime.datetime.strptime(m, "%b%y").strftime("%b %Y"),
               round(rng.uniform(0.012, 0.028), 6), round(rng.uniform(0.09, 0.21), 6))
              for m in ms[-12:] if m in mail_months][:12]

    ltd_rev = round(sum(v for _, v in rev12) * 3.1, 2)
    ltd_cost = round(-ltd_rev * 0.29, 2)
    d = {
        "client": CLIENT,
        "data_label": f"{latest:%B %Y} Data",
        "months": len(ms) + 14,          # the program predates the ODD window
        "mailings": 25,
        "cur_revenue": rev12[-1][1],
        "ltd_revenue": ltd_rev,
        "cur_profit": round(rev12[-1][1] * 0.82, 2),
        "ltd_profit": round(ltd_rev + ltd_cost, 2),
        "ltd_costs": ltd_cost,
        "ltd_plan_profit": 0,
        "profitability": round(ltd_rev / abs(ltd_cost), 2),
        "monthly_rev_last12": rev12,
        "monthly_rev_sum12": round(sum(v for _, v in rev12)),
        "monthly_rev_avg12": round(sum(v for _, v in rev12) / 12),
        "swipespend_36": swipes36,
        "mailings_recent": mail12,
        "dco_eligible": 9800,
    }
    json.dump(d, open(out, "w"), indent=1)
    return d


if __name__ == "__main__":
    odd = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/synthetic_odd.csv"
    out = sys.argv[2] if len(sys.argv) > 2 else "tests/fixtures/synthetic_base.json"
    d = build(odd, out)
    print(f"wrote {out}\n  client {d['client']}  {d['data_label']}  "
          f"{d['months']} months  {d['mailings']} mailings")
