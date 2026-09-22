#!/usr/bin/env python3
"""
combined_insights.py — the figures behind the test-branch views taken from James Gilmore's deck.

TEST BRANCH (test/james-aaron-combined, 2026-09-16). Aaron: "create a test branch that combines
ideas from both my and James's decks, produce a sample." James's legacy ARS analysis
(z-legacy/02-Scripts/ars) carries several views our deck does not. The ones that need only the
ODD extract and the ARS workbook we already read are computed here:

  responder_control   Responders against MAILED NON-RESPONDERS around each mailing — a
                      difference in differences. Our Responder Activity slides show responders
                      before vs after only, so a market-wide rise or fall reads as the mailing's
                      doing. The mailed non-responder was chosen by the same targeting rule and
                      sent the same offer, so it is the control that separates the response from
                      the selection (James, monthly_analysis/cohort.py).
  branch_kpis         Take rate, Reg E opt-in, 12-month closure rate and first-year closure per
                      branch, on the SAME definitions as the deck's program figures, so the Total
                      row reconciles to Program Overview and the First-Year Closure slide.
  account_health      Carded ARS-eligible personal accounts by card-spend state: active,
                      declining, cooling, dormant, never used; plus no card
                      (James, monthly_analysis/retention.py — ratios, not dollars).
  wave_revenue        Each mailing's booked incremental revenue from the workbook's
                      "All Months Rollup MM" sheet (James, ars/workbook.py _rollup_sections).
  scorecard           Measures each against its own comparator, with a status derived from
                      Aaron's +/-2% band (James, monthly_analysis/synthesis.py scorecard).

IMPORT-SAFE, like before_after and odd_rows: nothing runs at import. The before/after windows,
cohort rules and winsorizing come from before_after.py, so the responder side of the comparison
is the SAME figure the Responder Activity slide prints — only the control is new.

CLI (for inspection; the builder imports `compute`):
    combined_insights.py <odd.zip|odd.csv> <out.json> [workbook.xlsx]
"""
import csv
import datetime
import io
import json
import os
import re
import statistics
import sys
import zipfile
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, os.pardir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import before_after as BA                                               # noqa: E402
from odd_rows import accessors, rege_label, REGE_IN, REGE_OUT           # noqa: E402

csv.field_size_limit(10 ** 7)

# Aaron's band (2026-08-31): inside +/-2% a measure is "almost flat"; the scorecard's middle
# status uses the same band so a word on one slide and a status on another cannot disagree.
BAND_PCT = 2.0

# account health (James, retention.py): recent 3 months against the 3 before them
HEALTH_RECENT, HEALTH_PRIOR = 3, 3
DORMANT_ZERO_MONTHS = 3
COOLING_RATIO, DECLINING_RATIO = 0.50, 0.80
HEALTH_ORDER = ["Active", "Declining", "Cooling", "Dormant", "Never used", "No card"]
AT_RISK = ("Declining", "Cooling", "Dormant", "Never used")

# branch views
KPI_BRANCHES = 8          # the grouped-column chart seats eight branches
MIN_BRANCH_ELIGIBLE = 40  # the deck's own Reg E branch floor (metrics_gen rege_branch)

_MON_COL = re.compile(r"^([A-Z][a-z]{2}\d{2}) (Sig #|PIN #|Sig \$|PIN \$|Mail|Resp)$")


def mkey(token):
    return datetime.datetime.strptime(token, "%b%y")


# ============================================================== reading the ODD
def _open_lines(path):
    """Decoded lines of the ODD member of a zip (never the transaction file some zips also
    carry — the same selection metrics_gen makes), or of a plain CSV."""
    if path.lower().endswith(".zip"):
        zf = zipfile.ZipFile(path)
        csvs = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not csvs:
            raise SystemExit(f"ERROR: no .csv inside {path}")
        odd = [n for n in csvs if "-odd" in n.lower() or "_v2_" in n.lower()]
        name = odd[0] if odd else max(csvs, key=lambda n: zf.getinfo(n).file_size)
        return io.TextIOWrapper(zf.open(name), encoding="latin-1", errors="replace", newline="")
    return open(path, encoding="latin-1", errors="replace", newline="")


def read_odd(path):
    """-> dict(H, rows, smonths, mailmonths, latest) with only the columns used here."""
    with _open_lines(path) as fh:
        rdr = csv.reader(line.replace("\x00", "") for line in fh)
        hdr = None
        for k, row in enumerate(rdr):
            if k == 4:
                hdr = [c.strip() for c in row]
                break
        if hdr is None:
            raise SystemExit(f"ERROR: {os.path.basename(path)} has no header row")
        smonths = sorted({m.group(1) for m in (re.match(r"^([A-Z][a-z]{2}\d{2}) Sig #$", c)
                                               for c in hdr) if m}, key=mkey)
        if not smonths:
            raise SystemExit('ERROR: no "<Mon><yy> Sig #" columns in the extract')
        latest = smonths[-1]
        mailmonths = sorted({m.group(1) for m in (re.match(r"^([A-Z][a-z]{2}\d{2}) Mail$", c)
                                                  for c in hdr) if m}, key=mkey)
        # DOB, Avg Bal and the product columns joined the projection for the rate-cut views
        # (2026-09-21). An extract that does not carry one of them is not an error: the cut
        # reports "Not on file" and the slide says so, which is how the age profile already
        # behaves when a client's DOB column is blank.
        static = {f"{latest} Elig", "Debit?", "Stat Desc", "Stat Code", "Business?",
                  f"{latest} Reg E Desc", "Branch", "Date Opened", "Date Closed",
                  "DOB", "Avg Bal", "Curr Bal", "Prod Code", "Prod Desc", "Mailable?"}
        need = [i for i, c in enumerate(hdr) if c in static or _MON_COL.match(c)]
        H = {hdr[i]: j for j, i in enumerate(need)}
        pad = max(need) + 1
        rows = []
        for row in rdr:
            if len(row) < pad:
                row = row + [""] * (pad - len(row))
            if "".join(row).strip():
                rows.append([row[i] for i in need])
    return {"H": H, "rows": rows, "smonths": smonths, "mailmonths": mailmonths,
            "latest": latest}


_DATE_CACHE = {}


def parse_date(v):
    d = _DATE_CACHE.get(v, 0)
    if d != 0:
        return d
    out = None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%y"):
        try:
            out = datetime.datetime.strptime(v, fmt)
            break
        except (ValueError, TypeError):
            pass
    _DATE_CACHE[v] = out
    return out


def month_end(token):
    d = mkey(token)
    return (d.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)


def months_back(token, n):
    """First day of the month n months before `token`'s month."""
    d = mkey(token)
    y, m = d.year, d.month - n
    while m <= 0:
        m += 12
        y -= 1
    return datetime.datetime(y, m, 1)


def pct_change(a, b):
    return 100.0 * (b - a) / a if a else 0.0


def band(value, comparator, higher_is_better=True, scale=None):
    """'ahead' | 'level' | 'behind' against a comparator, on Aaron's +/-2% band.

    The band is 2% of the comparator — or of `scale` where the comparator is zero (a change
    measured against no change), so a $3 move on a $900 baseline still reads as level.
    """
    ref = abs(scale if scale is not None else comparator)
    diff = value - comparator
    if ref == 0:
        state = "level" if diff == 0 else ("ahead" if diff > 0 else "behind")
    elif abs(diff) <= ref * BAND_PCT / 100.0:
        state = "level"
    else:
        state = "ahead" if diff > 0 else "behind"
    if not higher_is_better and state != "level":
        state = "behind" if state == "ahead" else "ahead"
    return state


# ============================================================== responders vs control
def responder_control(rows, odd, smonths, mature):
    """Responders and mailed non-responders around each mailing, pooled.

    Windows, mailings, the responder cohort, the minimum cohort size and the winsorizing are
    before_after's, so `responders` reproduces the Responder Activity slide's own
    `ba_spend_before` / `ba_spend_after`. The control is every personal account MAILED that
    drop that did not meet its goal.

    `trajectory` is the pooled mean monthly spend at each offset from the mail month, each
    account-month capped at its cohort's winsorizing cap, indexed to that cohort's own
    pre-mailing mean (100 = its baseline) so two groups starting at different spend levels are
    comparable on one axis.
    """
    g, spend, personal = odd.g, odd.spend, odd.personal
    bw, aw, mailings = BA.windows(smonths, mature)
    pop = [r for r in rows if personal(r)]
    pools = {"responders": [[], []], "control": [[], []]}
    per_offset = {"responders": defaultdict(list), "control": defaultdict(list)}
    used, counts = [], []
    for m in mailings:
        i = smonths.index(m)
        pre, post = smonths[i - bw:i], smonths[i + 1:i + 1 + aw]
        offsets = [(o - bw, smonths[i - bw + o]) for o in range(bw)] + [(0, m)] + \
                  [(o + 1, x) for o, x in enumerate(post)]
        # Responders exactly as before_after selects them (a met goal on that mailing), so the
        # responder side reproduces the Responder Activity slide; the control must have been
        # MAILED that drop and not met its goal.
        resp = [r for r in pop if g(r, f"{m} Resp") in BA.RESP_MET]
        mailed = [r for r in pop if g(r, f"{m} Mail")]
        ctrl = [r for r in mailed if g(r, f"{m} Resp") not in BA.RESP_MET]
        if len(resp) < BA.MIN_RESPONDERS:
            continue
        used.append(BA.label(m))
        counts.append({"m": BA.label(m), "mailed": len(mailed), "responders": len(resp),
                       "control": len(ctrl)})
        for key, cohort in (("responders", resp), ("control", ctrl)):
            if key == "control" and len(cohort) < BA.MIN_RESPONDERS:
                continue
            for r in cohort:
                pools[key][0].append(statistics.mean(spend(r, x) for x in pre))
                pools[key][1].append(statistics.mean(spend(r, x) for x in post))
                for o, x in offsets:
                    per_offset[key][o].append(spend(r, x))

    out = {"before_months": bw, "after_months": aw, "mailings": used, "counts": counts}
    if not used or not pools["control"][0]:
        out["available"] = False
        return out
    out["available"] = True
    for key in ("responders", "control"):
        b, a = pools[key]
        allv = b + a
        cap = statistics.mean(allv) + 3 * statistics.pstdev(allv)
        wb_, wa_ = BA.wins_pair(b, a)
        # Rounded FIRST: the slide prints whole dollars, and the movement word is chosen from
        # the figures the reader sees. $295 -> $301 is +2.03% and cannot be called "almost
        # flat" because the unrounded means happened to differ by 1.9%.
        before, after = round(statistics.mean(wb_)), round(statistics.mean(wa_))
        offs = sorted(per_offset[key])
        means = {o: statistics.mean(min(v, cap) for v in per_offset[key][o]) for o in offs}
        base = statistics.mean(means[o] for o in offs if o < 0)
        out[key] = {
            "n": len(b),                      # account-mailing observations
            "before": before, "after": after,
            "change": after - before,
            "change_pct": round(pct_change(before, after), 1),
            "cap": round(cap),
            "trajectory": [[o, round(100 * means[o] / base, 1) if base else None] for o in offs],
        }
    r, c = out["responders"], out["control"]
    out["did"] = round((r["after"] - r["before"]) - (c["after"] - c["before"]))
    return out


# ============================================================== branch KPIs
_COUNT_KEYS = ("elig", "cards", "rege_pool", "rege_in", "rege_out", "open", "closed12",
               "fy_n", "fy_closed")


def _sum_counts(counts):
    t = dict.fromkeys(_COUNT_KEYS, 0)
    for c in counts:
        for k in _COUNT_KEYS:
            t[k] += c[k]
    return t


def branch_rates(name, b):
    """Rates for one branch (or a roll-up) from its raw counts. The counts ride along so a
    slide that shows fewer branches can roll the rest up without re-reading the ODD."""
    denom_close = b["open"] + b["closed12"]
    return {
        "branch": name, "eligible": b["elig"],
        "take": round(100 * b["cards"] / b["elig"], 1) if b["elig"] else None,
        "rege": round(100 * b["rege_in"] / b["rege_pool"], 1) if b["rege_pool"] else None,
        "closed12": round(100 * b["closed12"] / denom_close, 1) if denom_close else None,
        "first_year": round(100 * b["fy_closed"] / b["fy_n"], 1) if b["fy_n"] else None,
        "counts": {k: b[k] for k in _COUNT_KEYS},
    }


def roll_up(name, rows):
    """One row from several branch rows, recomputed from their counts (never an average of
    rates, which would let a 60-account branch weigh as much as a 5,000-account one)."""
    return branch_rates(name, _sum_counts(r["counts"] for r in rows))


def branch_kpis(rows, odd, smonths, latest, min_eligible=MIN_BRANCH_ELIGIBLE):
    """Per branch, on the deck's own definitions (metrics_gen):

      eligible      personal accounts with `<latest> Elig` = Yes
      take rate     eligible accounts holding a debit card / eligible      (take_hist_pct)
      Reg E opt-in  opted in / open personal debit-card holders            (rege_pct)
      closed 12 mo  personal accounts closed in the trailing 12 months /
                    (open personal accounts + those closures)
      first-year    accounts opened 36 to 12 months before the snapshot that closed within
      closure       366 days of opening                                    (bayes_prior)

    Branches below `min_eligible` eligible accounts are rolled into one "All other branches"
    row rather than dropped, so the Total reconciles to the program figures.
    """
    g, personal, hascard, isopen = odd.g, odd.personal, odd.hascard, odd.isopen
    elig_col = f"{latest} Elig"
    rege_col = f"{latest} Reg E Desc"
    now = month_end(latest)
    close_from = months_back(latest, 11)
    fy_from, fy_to = months_back(latest, 35), months_back(latest, 11) - datetime.timedelta(days=1)

    by = defaultdict(lambda: dict.fromkeys(_COUNT_KEYS, 0))
    unmapped = defaultdict(int)
    for r in rows:
        if not personal(r):
            continue
        b = by[g(r, "Branch") or "(blank)"]
        op = isopen(r)
        if g(r, elig_col) == "Yes":
            b["elig"] += 1
            b["cards"] += hascard(r)
        if op:
            b["open"] += 1
            if hascard(r):
                lab = rege_label(g(r, rege_col))
                if lab is None:
                    unmapped[g(r, rege_col)] += 1
                b["rege_pool"] += 1
                b["rege_in"] += lab == REGE_IN
                b["rege_out"] += lab == REGE_OUT
        do = parse_date(g(r, "Date Opened"))
        dc = parse_date(g(r, "Date Closed"))
        if not op and dc and close_from <= dc <= now:
            b["closed12"] += 1
        if do and fy_from <= do <= fy_to:
            b["fy_n"] += 1
            if not op and dc and (dc - do).days <= 366:
                b["fy_closed"] += 1

    big = sorted(((k, v) for k, v in by.items() if v["elig"] >= min_eligible),
                 key=lambda kv: -kv[1]["elig"])
    small = [v for k, v in by.items() if v["elig"] < min_eligible]
    out = {
        "branches": [branch_rates(k, v) for k, v in big],
        "other": (branch_rates(f"All other branches ({len(small)})", _sum_counts(small))
                  if small else None),
        "other_count": len(small),
        "total": branch_rates("Total", _sum_counts(by.values())),
        "min_eligible": min_eligible,
        "closure_window": [close_from.strftime("%b %Y"), now.strftime("%b %Y")],
        "first_year_window": [fy_from.strftime("%b %Y"), fy_to.strftime("%b %Y")],
        "unmapped_rege": dict(unmapped),
    }
    return out


# ============================================================== account health
def classify_health(monthly_spend, carded):
    """One account's card-spend state from its monthly spend, oldest month first.

    Ratios, not dollars (James, retention.py): a $5 slide is nothing on a $3,000-a-month
    account and most of a $20-a-month one.
      No card     no debit card on the account
      Never used  carded, no card spend in any month of the extract
      Dormant     carded, no spend in each of the last 3 months (used before)
      Cooling     last 3 months average below half of the 3 before them
      Declining   last 3 months average below 80% of the 3 before them
      Active      everything else, including an account whose use started recently
    """
    if not carded:
        return "No card"
    if not any(v > 0 for v in monthly_spend):
        return "Never used"
    recent = monthly_spend[-HEALTH_RECENT:]
    prior = monthly_spend[-(HEALTH_RECENT + HEALTH_PRIOR):-HEALTH_RECENT]
    if len(recent) >= DORMANT_ZERO_MONTHS and all(v <= 0 for v in recent[-DORMANT_ZERO_MONTHS:]):
        return "Dormant"
    p = sum(prior) / len(prior) if prior else 0.0
    if p > 0:
        ratio = (sum(recent) / len(recent)) / p
        if ratio < COOLING_RATIO:
            return "Cooling"
        if ratio < DECLINING_RATIO:
            return "Declining"
    return "Active"


def account_health(rows, odd, smonths, latest):
    """ARS-eligible personal accounts at the snapshot, by card-spend state."""
    g, personal, hascard, spend = odd.g, odd.personal, odd.hascard, odd.spend
    if len(smonths) < HEALTH_RECENT + HEALTH_PRIOR:
        return {"available": False, "months": len(smonths)}
    elig_col = f"{latest} Elig"
    recent_m = smonths[-HEALTH_RECENT:]
    prior_m = smonths[-(HEALTH_RECENT + HEALTH_PRIOR):-HEALTH_RECENT]
    n = defaultdict(int)
    prior_spend = defaultdict(float)
    recent_spend = defaultdict(float)
    for r in rows:
        if not (personal(r) and g(r, elig_col) == "Yes"):
            continue
        carded = hascard(r)
        series = [spend(r, m) for m in smonths] if carded else []
        state = classify_health(series, carded)
        n[state] += 1
        if carded:
            prior_spend[state] += sum(spend(r, m) for m in prior_m) / len(prior_m)
            recent_spend[state] += sum(spend(r, m) for m in recent_m) / len(recent_m)
    total = sum(n.values())
    carded_n = total - n["No card"]
    at_risk = sum(n[s] for s in AT_RISK)
    return {
        "available": True,
        "eligible": total, "carded": carded_n,
        # Two shares per state, because the slide used to mix them: the tile read
        # "card holders at risk" (of carded) above bars whose percentages were of every
        # eligible account, so the numbers on one slide did not add up to each other
        # (Aaron, 2026-09-21). A card state is a share of CARD HOLDERS; "No card" can only
        # be a share of eligible accounts, and its bar now says so.
        "states": [[s, n[s], round(100 * n[s] / total, 1) if total else 0.0,
                    round(recent_spend[s]), round(prior_spend[s]),
                    (None if s == "No card" else
                     (round(100 * n[s] / carded_n, 1) if carded_n else 0.0))]
                   for s in HEALTH_ORDER],
        "at_risk": at_risk,
        "at_risk_pct_of_carded": round(100 * at_risk / carded_n, 1) if carded_n else 0.0,
        # monthly card spend these accounts carried in the 3 months BEFORE the recent window
        "at_risk_prior_monthly_spend": round(sum(prior_spend[s] for s in AT_RISK)),
        "at_risk_recent_monthly_spend": round(sum(recent_spend[s] for s in AT_RISK)),
        "recent_window": [BA.label(recent_m[0]), BA.label(recent_m[-1])],
        "prior_window": [BA.label(prior_m[0]), BA.label(prior_m[-1])],
        "months": len(smonths),
    }


# ============================================================== revenue by mailing
ROLLUP_SHEET = "All Months Rollup MM"


def rollup_sections(rows):
    """{section label: {'YYYY-MM': income}} for the Summary block and each '<Month Year>
    Mailing' block. A month with no cell had not happened for that mailing yet: absent, not 0."""
    out = {}
    for i, row in enumerate(rows):
        label = row[1] if len(row) > 1 else None
        if not isinstance(label, str):
            continue
        label = label.strip()
        if label != "Summary" and not label.endswith("Mailing"):
            continue
        months = [(j, c) for j, c in enumerate(row) if hasattr(c, "year")]
        if not months:
            continue
        income = None
        for k in range(i + 1, min(i + 8, len(rows))):
            if any(isinstance(c, str) and "Total Incremental Income" in c for c in rows[k] if c):
                income = rows[k]
                break
        if income is None:
            continue
        out[label] = {f"{c.year}-{c.month:02d}": float(income[j]) for j, c in months
                      if j < len(income) and isinstance(income[j], (int, float))}
    return out


def wave_revenue(workbook_path):
    """Each mailing's booked incremental revenue to date, oldest mailing first.

    Returns {"available": False, "reason": ...} when the workbook or its rollup sheet is absent
    (an SM client's workbook has no MM rollup) so the slide can say so plainly.
    """
    if not workbook_path or not os.path.exists(str(workbook_path)):
        return {"available": False, "reason": "no ARS workbook was found for this period"}
    import openpyxl
    wb = openpyxl.load_workbook(str(workbook_path), read_only=True, data_only=True)
    try:
        if ROLLUP_SHEET not in wb.sheetnames:
            return {"available": False, "workbook": os.path.basename(str(workbook_path)),
                    "reason": f"the workbook has no '{ROLLUP_SHEET}' sheet"}
        rows = [list(r) for r in wb[ROLLUP_SHEET].iter_rows(values_only=True)]
    finally:
        wb.close()
    sections = rollup_sections(rows)
    summary = sections.pop("Summary", {})
    waves = []
    for label, series in sections.items():
        try:
            d = datetime.datetime.strptime(label.replace("Mailing", "").strip(), "%B %Y")
        except ValueError:
            continue
        booked = {k: v for k, v in series.items()}
        # The month-by-month build, which is what James's slide 5 shows and ours did not:
        # [months since the mailing, that month's booked revenue, cumulative]. Age is
        # measured from the mailing's own month, not the position in the list, so a month
        # the workbook never booked leaves a GAP rather than pulling the curve left.
        run, build = 0.0, []
        for k in sorted(booked):
            y, mo = int(k[:4]), int(k[5:7])
            age = (y * 12 + mo) - (d.year * 12 + d.month)
            run += booked[k]
            build.append([age, round(booked[k], 2), round(run, 2)])
        waves.append({"m": d.strftime("%b %Y"), "key": d.strftime("%Y-%m"),
                      "revenue": round(sum(booked.values()), 2),
                      "months": len(booked),
                      "build": build,
                      "by_month": {k: round(v, 2) for k, v in booked.items()},
                      "per_month": round(sum(booked.values()) / len(booked), 2) if booked else 0.0})
    waves.sort(key=lambda w: w["key"])
    if not waves:
        return {"available": False, "workbook": os.path.basename(str(workbook_path)),
                "reason": f"the '{ROLLUP_SHEET}' sheet carries no readable mailing sections"}
    rolled = sum(w["revenue"] for w in waves)
    through = max((k for w in sections.values() for k in w), default=None)
    # Where THIS month's revenue came from, by mailing (James's slide 6). The month is the
    # newest one any mailing booked, which is not always the newest column on the sheet: a
    # mailing block can carry a trailing empty month.
    latest = max((k for w in waves for k in w["by_month"]), default=None)
    by_mailing_latest = sorted(
        ((w["m"], w["by_month"][latest], w["months"]) for w in waves if latest in w["by_month"]),
        key=lambda t: -t[1]) if latest else []
    return {"available": True, "workbook": os.path.basename(str(workbook_path)),
            "waves": waves, "total": round(rolled, 2),
            "summary_total": round(sum(summary.values()), 2) if summary else None,
            "latest_month": latest,
            "latest_month_label": (datetime.datetime.strptime(latest, "%Y-%m").strftime("%b %Y")
                                   if latest else None),
            "by_mailing_latest": by_mailing_latest,
            "latest_total": round(sum(v for _, v, _ in by_mailing_latest), 2),
            "summary_latest": round(summary.get(latest, 0.0), 2) if (summary and latest) else None,
            "through": (datetime.datetime.strptime(through, "%Y-%m").strftime("%b %Y")
                        if through else None)}



# ============================================================== where a rate lags
# James cuts take rate and Reg E opt-in by tenure, age, balance and product and shows where
# each one lags the book; our deck only ever showed the two program rates and a branch chart,
# so a client could see THAT opt-in was 29% and never where the 29% comes from.
#
# One pass computes both rates on every cut, because they read the same row and the ODD is
# large. Each cut's bands are fixed, not quantiles: a band that means something to a banker
# ("opened in the last year") survives a client whose distribution is nothing like the last
# client's, and quantile bands would silently redefine themselves per client.
MIN_BAND = 25           # a band below this is reported but never called a lagging pocket
TOP_PRODUCTS = 6        # products shown by population; the rest roll into one band

TENURE_BANDS = [(0, 12, "Under 1 year"), (12, 36, "1 to 3 years"), (36, 60, "3 to 5 years"),
                (60, 120, "5 to 10 years"), (120, None, "10 years or more")]
AGE_BANDS = [(18, 25, "18 to 24"), (25, 35, "25 to 34"), (35, 50, "35 to 49"),
             (50, 65, "50 to 64"), (65, None, "65 or older")]
BALANCE_BANDS = [(None, 1, "$0"), (1, 500, "$1 to $499"), (500, 2000, "$500 to $1,999"),
                 (2000, 5000, "$2,000 to $4,999"), (5000, None, "$5,000 or more")]
NOT_ON_FILE = "Not on file"


def _band(value, bands):
    """The band `value` falls in, or None when the ODD does not carry it. A missing value is
    NEVER folded into the lowest band — that is how a client with no DOB column reads as a
    book full of 18-year-olds (CLAUDE.md: missing data is stated, never zeroed)."""
    if value is None:
        return None
    for lo, hi, label in bands:
        if (lo is None or value >= lo) and (hi is None or value < hi):
            return label
    return None


def _months_between(then, now):
    return (now.year - then.year) * 12 + (now.month - then.month)


def rate_cuts(rows, odd, latest, top_products=TOP_PRODUCTS):
    """Take rate and Reg E opt-in by tenure, age, balance and product, in one pass.

    Definitions are the deck's own, so a cut's Total equals the figure on the program slides:
      take rate     eligible accounts holding a debit card / eligible personal accounts
      Reg E opt-in  opted in / open personal debit-card holders
    """
    g, personal, hascard, isopen = odd.g, odd.personal, odd.hascard, odd.isopen
    elig_col, rege_col = f"{latest} Elig", f"{latest} Reg E Desc"
    now = month_end(latest)

    cuts = {c: defaultdict(lambda: {"elig": 0, "cards": 0, "rege_pool": 0, "rege_in": 0})
            for c in ("Tenure", "Age", "Balance", "Product")}
    prod_n = defaultdict(int)
    missing = defaultdict(int)

    for r in rows:
        if not personal(r):
            continue
        elig = g(r, elig_col) == "Yes"
        carded = hascard(r)
        op = isopen(r)
        in_rege_pool = op and carded
        if not (elig or in_rege_pool):
            continue

        do = parse_date(g(r, "Date Opened"))
        tenure = _band(_months_between(do, now) if do else None, TENURE_BANDS)
        dob = parse_date(g(r, "DOB"))
        age = _band(((now - dob).days / 365.25) if dob else None, AGE_BANDS)
        bal = _band(odd.fnum(r, "Avg Bal"), BALANCE_BANDS)
        prod = (g(r, "Prod Desc") or g(r, "Prod Code") or "").strip() or None

        for name, key in (("Tenure", tenure), ("Age", age), ("Balance", bal),
                          ("Product", prod)):
            if key is None:
                missing[name] += 1
                key = NOT_ON_FILE
            b = cuts[name][key]
            if elig:
                b["elig"] += 1
                b["cards"] += carded
            if in_rege_pool:
                lab = rege_label(g(r, rege_col))
                b["rege_pool"] += 1
                b["rege_in"] += lab == REGE_IN
            if name == "Product":
                prod_n[key] += 1

    # Products: the biggest by population, the rest in one honest roll-up.
    keep = {p for p, _n in sorted(prod_n.items(), key=lambda kv: -kv[1])[:top_products]}
    rolled = {"elig": 0, "cards": 0, "rege_pool": 0, "rege_in": 0}
    n_rolled = 0
    for p in [p for p in list(cuts["Product"]) if p not in keep]:
        b = cuts["Product"].pop(p)
        n_rolled += 1
        for k in rolled:
            rolled[k] += b[k]
    if n_rolled:
        cuts["Product"][f"All other products ({n_rolled})"] = rolled

    def order(name, keys):
        if name == "Tenure":
            seq = [b[2] for b in TENURE_BANDS]
        elif name == "Age":
            seq = [b[2] for b in AGE_BANDS]
        elif name == "Balance":
            seq = [b[2] for b in BALANCE_BANDS]
        else:
            return sorted(keys, key=lambda k: -(cuts[name][k]["elig"] or 0))
        rank = {lab: i for i, lab in enumerate(seq)}
        return sorted(keys, key=lambda k: rank.get(k, len(seq)))

    out = {}
    for name, bands in cuts.items():
        rowsout = []
        for key in order(name, bands):
            b = bands[key]
            rowsout.append({
                "band": key,
                "eligible": b["elig"],
                "take": round(100 * b["cards"] / b["elig"], 1) if b["elig"] else None,
                "rege_pool": b["rege_pool"],
                "rege": round(100 * b["rege_in"] / b["rege_pool"], 1) if b["rege_pool"] else None,
            })
        out[name] = rowsout

    tot_elig = sum(b["elig"] for b in cuts["Tenure"].values())
    tot_cards = sum(b["cards"] for b in cuts["Tenure"].values())
    tot_pool = sum(b["rege_pool"] for b in cuts["Tenure"].values())
    tot_in = sum(b["rege_in"] for b in cuts["Tenure"].values())
    return {
        "available": bool(tot_elig or tot_pool),
        "cuts": out,
        "take_all": round(100 * tot_cards / tot_elig, 1) if tot_elig else None,
        "rege_all": round(100 * tot_in / tot_pool, 1) if tot_pool else None,
        "eligible": tot_elig, "rege_pool": tot_pool,
        "missing": dict(missing),
        "min_band": MIN_BAND,
    }


def lagging(cuts, measure, floor=MIN_BAND, n=3):
    """The bands furthest BELOW the book on `measure` ('take' or 'rege'), biggest gap first.

    A band under `floor` accounts is left out of the ranking, not out of the slide: a 4-account
    band at 0% is arithmetic, not a coaching problem. "Not on file" is never a pocket either —
    it is a data gap, and it is reported as one.
    """
    all_key = "take_all" if measure == "take" else "rege_all"
    book = cuts.get(all_key)
    if book is None:
        return []
    pool_key = "eligible" if measure == "take" else "rege_pool"
    out = []
    for name, bands in cuts["cuts"].items():
        for b in bands:
            if b["band"] == NOT_ON_FILE or b[measure] is None or b[pool_key] < floor:
                continue
            out.append({"cut": name, "band": b["band"], "value": b[measure],
                        "n": b[pool_key], "gap": round(b[measure] - book, 1)})
    return sorted(out, key=lambda d: d["gap"])[:n]


# ============================================================== swipe tier migration
# The deck shows the tier table as a snapshot and "movement" for the latest mailing's
# responders only. James reads migration across the whole book: who climbed, who slipped, and
# what that is worth. A snapshot cannot answer "are these accounts getting better or worse",
# and two clients with identical tier tables can be moving in opposite directions.
TIER_ORDER = ["Non-User", "1-5", "6-10", "11-15", "16-20", "21-25", "26+"]
TIER_BANDS = [(1, 6, "1-5"), (6, 11, "6-10"), (11, 16, "11-15"), (16, 21, "16-20"),
              (21, 26, "21-25")]
MIGRATION_WINDOW = 3      # months averaged at each end, the deck's own tier window
MIGRATION_SPAN = 12       # months between the two windows


def swipe_tier(avg):
    """The deck's tier for an average monthly swipe count — half-open bands, so an average
    between two bands lands in the lower one instead of falling through to '26+'
    (metrics_gen carried that defect until 2026-09-21)."""
    if avg < 1:
        return "Non-User"
    for lo, hi, name in TIER_BANDS:
        if lo <= avg < hi:
            return name
    return "26+"


def tier_migration(rows, odd, smonths, latest, span=MIGRATION_SPAN, win=MIGRATION_WINDOW):
    """Where eligible card holders sat a year ago against where they sit now.

    Both ends are `win`-month averages, the same window the tier table uses, so a single
    unusual month cannot move an account across the matrix on its own.
    """
    if len(smonths) < span + win:
        return {"available": False, "months": len(smonths),
                "needs": span + win}
    g, personal, hascard = odd.g, odd.personal, odd.hascard
    elig_col = f"{latest} Elig"
    now_w = smonths[-win:]
    then_w = smonths[-(span + win):-span]

    matrix = {a: {b: 0 for b in TIER_ORDER} for a in TIER_ORDER}
    spend_now = {"up": 0.0, "same": 0.0, "down": 0.0}
    n = {"up": 0, "same": 0, "down": 0}
    rank = {t: i for i, t in enumerate(TIER_ORDER)}
    for r in rows:
        if not (personal(r) and hascard(r) and g(r, elig_col) == "Yes"):
            continue
        a = swipe_tier(sum(odd.swipes(r, m) for m in then_w) / win)
        b = swipe_tier(sum(odd.swipes(r, m) for m in now_w) / win)
        matrix[a][b] += 1
        key = "up" if rank[b] > rank[a] else ("down" if rank[b] < rank[a] else "same")
        n[key] += 1
        spend_now[key] += sum(odd.spend(r, m) for m in now_w) / win
    total = sum(n.values())
    return {
        "available": bool(total),
        "accounts": total,
        "matrix": [[a] + [matrix[a][b] for b in TIER_ORDER] for a in TIER_ORDER],
        "tiers": TIER_ORDER,
        "moved_up": n["up"], "same": n["same"], "moved_down": n["down"],
        "pct_up": round(100 * n["up"] / total, 1) if total else None,
        "pct_down": round(100 * n["down"] / total, 1) if total else None,
        "spend_up": round(spend_now["up"] / n["up"]) if n["up"] else None,
        "spend_down": round(spend_now["down"] / n["down"]) if n["down"] else None,
        "spend_same": round(spend_now["same"] / n["same"]) if n["same"] else None,
        "now_window": [BA.label(now_w[0]), BA.label(now_w[-1])],
        "then_window": [BA.label(then_w[0]), BA.label(then_w[-1])],
        "span": span,
    }


# ============================================================== interchange routing
# Signature and PIN transactions earn the client different interchange, and the ODD carries
# them in separate columns that every existing measure adds together. James keeps the mix as
# a metric and never puts it in a deck; it belongs in one, because the mix moves with what
# the client's card does at the terminal and it is worth real money.
def routing_mix(rows, odd, smonths, months=12):
    """Signature vs PIN share of swipes and spend, by month, over the trailing `months`."""
    g, personal, hascard = odd.g, odd.personal, odd.hascard
    window = smonths[-months:]
    series = []
    for m in window:
        sc = sd = pc = pd = 0.0
        for r in rows:
            if not (personal(r) and hascard(r)):
                continue
            a, b, c, d = odd.routing(r, m)
            sc += a; sd += b; pc += c; pd += d
        swipes = sc + pc
        series.append({
            "month": BA.label(m),
            "sig_n": round(sc), "sig_usd": round(sd),
            "pin_n": round(pc), "pin_usd": round(pd),
            "pin_share": round(100 * pc / swipes, 1) if swipes else None,
            "sig_ticket": round(sd / sc, 2) if sc else None,
            "pin_ticket": round(pd / pc, 2) if pc else None,
        })
    live = [s for s in series if s["pin_share"] is not None]
    if not live:
        return {"available": False, "months": len(window)}
    tot_sig_n = sum(s["sig_n"] for s in series)
    tot_pin_n = sum(s["pin_n"] for s in series)
    tot_sig_d = sum(s["sig_usd"] for s in series)
    tot_pin_d = sum(s["pin_usd"] for s in series)
    swipes = tot_sig_n + tot_pin_n
    return {
        "available": True,
        "series": series,
        "window": [series[0]["month"], series[-1]["month"]],
        "pin_share": round(100 * tot_pin_n / swipes, 1) if swipes else None,
        "pin_share_usd": round(100 * tot_pin_d / (tot_sig_d + tot_pin_d), 1)
                         if (tot_sig_d + tot_pin_d) else None,
        "sig_ticket": round(tot_sig_d / tot_sig_n, 2) if tot_sig_n else None,
        "pin_ticket": round(tot_pin_d / tot_pin_n, 2) if tot_pin_n else None,
        "first_share": live[0]["pin_share"], "last_share": live[-1]["pin_share"],
    }

# ============================================================== scorecard
def scorecard(M, B, rc, hk, bk):
    """[[measure, value text, comparator text, status]] — each measure against its own comparator.

    Status comes from `band` (Aaron's +/-2%), never from a fixed threshold picked per measure.
    A measure whose inputs are absent is left off rather than shown as zero.
    """
    rows = []

    def add(measure, value, value_txt, comp, comp_txt, higher=True, scale=None):
        rows.append([measure, value_txt, comp_txt, band(value, comp, higher, scale)])

    if M.get("take_new_total"):
        add("Take rate, accounts opened in 12 months", M["take_new_pct"], f"{M['take_new_pct']:.1f}%",
            M["take_hist_pct"], f"{M['take_hist_pct']:.1f}% all eligible accounts")
    if M.get("rege_new_pool"):
        add("Reg E opt-in, accounts opened in 12 months", M["rege_new_pct"], f"{M['rege_new_pct']:.1f}%",
            M["rege_pct"], f"{M['rege_pct']:.1f}% all personal card holders")
    mst = M.get("mail_summary_total") or []
    if M.get("latest_mailed") and len(mst) == 5 and len(M.get("mail_summary") or []) > 1:
        add(f"Response, {M['latest_mailing']} mailing", M["latest_resprate"], f"{M['latest_resprate']:.1f}%",
            mst[4], f"{mst[4]:.1f}% trailing {len(M['mail_summary'])} mailings")
    if rc.get("available"):
        c = rc["control"]
        sign = "+" if rc["did"] >= 0 else "−"
        add("Responder spend change less non-responder change", rc["did"],
            f"{sign}${abs(rc['did']):,}/mo", 0, "$0 (no difference)", scale=c["before"])
    if B.get("profitability") is not None:
        add("Profitability ratio", B["profitability"], f"{B['profitability']:.1f} : 1", 2.0, "2 : 1 threshold")
    ss = B.get("swipespend_36") or []
    if len(ss) >= 2 and ss[0][2]:
        g_ = pct_change(ss[0][2], ss[-1][2])
        add(f"Card-holding accounts, {len(ss)}-month change", g_, f"{g_:+.1f}%", 0.0, "0% (no change)", scale=100)
        by = {x[0]: x[1] for x in ss}
        last = datetime.datetime.strptime(ss[-1][0], "%b %Y")
        yago = last.replace(year=last.year - 1).strftime("%b %Y")
        if by.get(yago):
            y_ = pct_change(by[yago], ss[-1][1])
            add("Monthly debit spend, year over year", y_, f"{y_:+.1f}%", 0.0,
                f"{yago} spend", scale=100)
    if M.get("close_24"):
        add("Personal openings vs closures, 24 months", M["open_24"], f"{M['open_24']:,} opened",
            M["close_24"], f"{M['close_24']:,} closed")
    t = bk.get("total") or {}
    # First-year closure was compared with closed12 — the 12-month closure rate of ALL
    # accounts. Two different rates on different populations (18.0% against 7.1% on Marine),
    # so "behind" was never a like-for-like reading (Aaron, 2026-09-21). Compared now with
    # the SAME measure at the median reporting branch: same definition, same window, a
    # population the client can act on. With fewer than three reporting branches there is no
    # median worth the name and the row is left off rather than compared to something else.
    fy_branches = sorted(b["first_year"] for b in (bk.get("branches") or [])
                         if b.get("first_year") is not None)
    if t.get("first_year") is not None and len(fy_branches) >= 3:
        med = statistics.median(fy_branches)
        add("First-year closure rate", t["first_year"], f"{t['first_year']:.1f}%",
            med, f"{med:.1f}% median branch", higher=False)
    return rows


# ============================================================== entry point
def compute(odd_path, workbook_path=None, M=None, B=None):
    """Everything the slides need, as one JSON-ready dict."""
    d = read_odd(odd_path)
    odd = accessors(d["H"])
    smonths, latest = d["smonths"], d["latest"]
    nextm = {smonths[i]: smonths[i + 1] for i in range(len(smonths) - 1)}
    mature = [m for m in d["mailmonths"] if m in nextm]
    out = {
        "latest": latest, "latest_label": BA.label(latest), "n_rows": len(d["rows"]),
        "responder_control": responder_control(d["rows"], odd, smonths, mature),
        "branch_kpis": branch_kpis(d["rows"], odd, smonths, latest),
        "account_health": account_health(d["rows"], odd, smonths, latest),
        "wave_revenue": wave_revenue(workbook_path),
        "rate_cuts": rate_cuts(d["rows"], odd, latest),
        "tier_migration": tier_migration(d["rows"], odd, smonths, latest),
        "routing_mix": routing_mix(d["rows"], odd, smonths),
    }
    if M is not None and B is not None:
        out["scorecard"] = scorecard(M, B, out["responder_control"], out["account_health"],
                                     out["branch_kpis"])
    return out


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) < 2:
        raise SystemExit(__doc__)
    out = compute(argv[0], argv[2] if len(argv) > 2 else None)
    with open(argv[1], "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print("wrote", argv[1])


if __name__ == "__main__":
    main()
