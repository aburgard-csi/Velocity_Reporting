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
from odd_rows import accessors, rege_label, open_odd, REGE_IN, REGE_OUT  # noqa: E402

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
    carry), or of a plain CSV. The member is odd_rows.odd_member's decision, the same one
    metrics_gen makes, because it is the same function."""
    try:
        return open_odd(path)[0]
    except FileNotFoundError as e:
        raise SystemExit(f"ERROR: {e}")


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
        static = {f"{latest} Elig", "Debit?", "Stat Desc", "Stat Code", "Business?",
                  f"{latest} Reg E Desc", "Branch", "Date Opened", "Date Closed"}
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
        if odd.iselig(r):
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
        if not (personal(r) and odd.iselig(r)):
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
        "states": [[s, n[s], round(100 * n[s] / total, 1) if total else 0.0,
                    round(recent_spend[s]), round(prior_spend[s])] for s in HEALTH_ORDER],
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
        waves.append({"m": d.strftime("%b %Y"), "key": d.strftime("%Y-%m"),
                      "revenue": round(sum(booked.values()), 2),
                      "months": len(booked),
                      "per_month": round(sum(booked.values()) / len(booked), 2) if booked else 0.0})
    waves.sort(key=lambda w: w["key"])
    if not waves:
        return {"available": False, "workbook": os.path.basename(str(workbook_path)),
                "reason": f"the '{ROLLUP_SHEET}' sheet carries no readable mailing sections"}
    rolled = sum(w["revenue"] for w in waves)
    through = max((k for w in sections.values() for k in w), default=None)
    return {"available": True, "workbook": os.path.basename(str(workbook_path)),
            "waves": waves, "total": round(rolled, 2),
            "summary_total": round(sum(summary.values()), 2) if summary else None,
            "through": (datetime.datetime.strptime(through, "%Y-%m").strftime("%b %Y")
                        if through else None)}


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
    if t.get("first_year") is not None and t.get("closed12") is not None:
        add("First-year closure rate", t["first_year"], f"{t['first_year']:.1f}%",
            t["closed12"], f"{t['closed12']:.1f}% all accounts, last 12 months", higher=False)
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
