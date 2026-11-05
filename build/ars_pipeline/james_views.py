#!/usr/bin/env python3
"""
james_views.py — the figures behind the SECOND round of views taken from James Gilmore's deck.

OPT-IN, like everything in combined_insights: build_ars_gen reaches this only under
RPE_JAMES_SLIDES=1, through combined_insights.compute. Aaron, 2026-09-25: "work on
incorporating more of James's slides. We'll need to add in as many as possible and then we'll
edit down from the maximized copy." So this module errs toward including a view — but never
toward inventing a figure. A view whose data is absent returns {"available": False,
"reason": ...} and its slide says so.

The gap list is the "James vs Aaron Decks" comparison (2026-09-16/17) against James's slide
catalogue (z-legacy ars/deck/headlines.py), less what feature/james-deck-gaps already built.
Each function names the James slide it answers:

  rege_trend           Reg E elections month by month, and who changed election in a year
                       (James: rege 24-month trend; lab "opt-in flips")
  repeat_responses     first-time vs repeat responses, response by times mailed, and whether a
                       repeat response climbed a tier (ladder_waves)
  activation_split     first swipes in the last year: new accounts, existing accounts mailed
                       first, and existing accounts that started on their own (activation_split)
  movement_by_group    tier movement for responders, mailed non-responders and the unmailed
                       (tier_movement)
  per_mailing_control  responders vs mailed non-responders, mailing by mailing (per_mailer)
  where_accounts_close 12-month closure rate by product and by branch (attrition_branch)
  months_of_warning    card spend of closing accounts against still-open ones, by months
                       before the close (attrition_slides.months_of_warning)
  stressors            open eligible accounts by concurrent stress conditions
                       (attrition_slides.concurrent_stressors)
  card_gaps            where cards lag: branch share of eligible accounts vs share of cards
                       (leaks / no_card)
  account_value        what a card and an opt-in earn, and value by account age, at the
                       WORKBOOK's own interchange rate and NSF fee (value / value_ladder /
                       branch_value)
  responder_value      what a response is worth in interchange, and the booked-vs-estimate
                       frames (responder_value / counterfactual / revenue_frames)
  mailing_pnl          revenue per fee dollar and per responder, mailing by mailing (pnl)
  offer_segments       response and spend difference per 1,000 mailed, by offer segment
                       (segments / segment_traj)
  cascade              eligible -> carded -> active -> mailed -> responded -> booked (cascade)
  card_spend_mix       where card spend goes, by merchant category, from the one month of
                       transactions the ODD zip carries (charts_txn / card merchants)

Complete months only (CLAUDE.md, 2026-09-17): every activity window here reads the extract's
months through month_complete.odd_completeness — activity measures stop at the last month
complete for swipes and spend, NSF/OD measures at the last month complete for NSF/OD — and the
months left out ride along in the output so the slide can state them. Status snapshots (Reg E,
Elig, account status) read the snapshot month.

IMPORT-SAFE: nothing runs at import.
"""
import csv
import datetime
import io
import math
import os
import re
import statistics
import sys
import zipfile
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, os.pardir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import before_after as BA                                                # noqa: E402
import month_complete as MC                                              # noqa: E402
from odd_rows import rege_label, REGE_IN, REGE_OUT, REGE_DEFAULT          # noqa: E402

TIER_ORDER = ["Non-User", "1-5", "6-10", "11-15", "16-20", "21-25", "26+"]
_TIER_BANDS = [(1, 5, "1-5"), (6, 10, "6-10"), (11, 15, "11-15"), (16, 20, "16-20"),
               (21, 25, "21-25")]

# A response code's rung on the ladder (ODD '<Mon> Resp'). NU 1-4 is a partial: the account
# swiped but did not reach the goal, which before_after does not count as a response.
RESP_RANK = {"NU 5+": 0, "TH-10": 1, "TH-15": 2, "TH-20": 3, "TH-25": 4}

MIN_GROUP = 25            # a group below this is shown but never compared or ranked
ATTRITION_MIN = 150       # James: only branches with 150+ at-risk accounts are rated
WARNING_RATIO = 0.80      # James: "fading" = below 80% of still-open accounts, same months
WARNING_MONTHS = 12
STRESS_WINDOW = 3
DRAWDOWN = 0.50           # current balance below half the average balance


def mkey(token):
    return datetime.datetime.strptime(token, "%b%y")


def label(token):
    return BA.label(token)


def swipe_tier(avg):
    """Same rule as metrics_gen.tier and combined_insights.swipe_tier: the average is rounded
    DOWN into its segment (Aaron, 2026-09-22). A test pins the three against each other."""
    s = math.floor(avg)
    if s < 1:
        return "Non-User"
    for lo, hi, name in _TIER_BANDS:
        if lo <= s <= hi:
            return name
    return "26+"


def _parse_date(v, _cache={}):
    d = _cache.get(v, 0)
    if d != 0:
        return d
    out = None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%y"):
        try:
            out = datetime.datetime.strptime(v, fmt)
            break
        except (ValueError, TypeError):
            pass
    _cache[v] = out
    return out


def _month_token(dt):
    return dt.strftime("%b%y")


def _months_back(token, n):
    d = mkey(token)
    y, m = d.year, d.month - n
    while m <= 0:
        m += 12
        y -= 1
    return datetime.datetime(y, m, 1)


def _month_end(token):
    d = mkey(token)
    return (d.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)


def _pct(n, d, nd=1):
    return round(100.0 * n / d, nd) if d else None


# ============================================================== completeness
def odd_member(path):
    """The ODD member's file name inside a zip (the same choice read_odd makes), else the
    path's own name. The pull stamp in it is what month_complete reads."""
    if str(path).lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(path) as zf:
                csvs = [n for n in zf.namelist() if n.lower().endswith(".csv")]
                odd = [n for n in csvs if "-odd" in n.lower() or "_v2_" in n.lower()]
                if odd:
                    return odd[0]
                if csvs:
                    return max(csvs, key=lambda n: zf.getinfo(n).file_size)
        except (OSError, zipfile.BadZipFile):
            return None
    return os.path.basename(str(path))


def completeness(rows, odd, smonths, odd_path=None):
    """{'activity': [months], 'nsf': [months], 'both': [months], 'left_out': sentence,
    'result': odd_completeness(...)} — the months each kind of measure may read."""
    as_of = MC.pull_date(odd_member(odd_path)) if odd_path else None
    res = MC.odd_completeness(rows, odd, smonths, as_of)
    act = MC.usable_months(smonths, res["activity"])
    nsf = MC.usable_months(smonths, res["nsf"])
    both = MC.usable_months(smonths, res["all"])
    return {"activity": act, "nsf": nsf, "both": both,
            "left_out_activity": MC.excluded_sentence(res["activity"]),
            "left_out_nsf": MC.excluded_sentence(res["nsf"]),
            "left_out_all": MC.excluded_sentence(res["all"]),
            "pull_date": res.get("pull_date")}


# ============================================================== Reg E over time
REGE_TREND_MONTHS = 24


def rege_trend(rows, odd, smonths, H, months=REGE_TREND_MONTHS, span=12):
    """Opt-in share of personal card holders' elections, month by month, and who changed.

    The election is a STATUS, read from each month's '<Mon> Reg E Desc'. The population each
    month is personal accounts holding a debit card (the Debit? flag at the snapshot — the
    extract carries no monthly card flag) whose election that month maps to one of the three
    standard labels. Blank cells are not applicable (closed accounts, no election recorded).
    """
    g, personal, hascard = odd.g, odd.personal, odd.hascard
    window = [m for m in smonths[-months:]]
    have = [m for m in window if f"{m} Reg E Desc" in H]
    if not have:
        return {"available": False,
                "reason": "the extract carries no monthly Reg E Desc columns"}
    counts = {m: Counter() for m in have}
    unmapped = Counter()
    first, last = (have[-(span + 1)] if len(have) > span else have[0]), have[-1]
    flips = Counter()
    for r in rows:
        if not (personal(r) and hascard(r)):
            continue
        for m in have:
            v = g(r, f"{m} Reg E Desc")
            lab = rege_label(v)
            if lab is None:
                unmapped[v] += 1
                continue
            if lab:
                counts[m][lab] += 1
        a, b = rege_label(g(r, f"{first} Reg E Desc")), rege_label(g(r, f"{last} Reg E Desc"))
        if a and b:
            flips[(a, b)] += 1
    series = []
    for m in have:
        c = counts[m]
        tot = c[REGE_IN] + c[REGE_OUT] + c[REGE_DEFAULT]
        series.append({"month": label(m), "accounts": tot,
                       "in_pct": _pct(c[REGE_IN], tot), "out_pct": _pct(c[REGE_OUT], tot),
                       "default_pct": _pct(c[REGE_DEFAULT], tot)})
    live = [s for s in series if s["accounts"]]
    if not live:
        return {"available": False, "reason": "no personal card holder carries a readable "
                                              "Reg E election in any month"}
    both = sum(flips.values())
    to_in = flips[(REGE_OUT, REGE_IN)] + flips[(REGE_DEFAULT, REGE_IN)]
    from_in = flips[(REGE_IN, REGE_OUT)] + flips[(REGE_IN, REGE_DEFAULT)]
    return {
        "available": True, "series": live,
        "first": live[0], "last": live[-1],
        "flip_from": label(first), "flip_to": label(last),
        "flip_accounts": both,
        "to_in": to_in, "from_in": from_in,
        "stayed": sum(v for (a, b), v in flips.items() if a == b),
        "flips": [[a, b, v] for (a, b), v in sorted(flips.items(), key=lambda kv: -kv[1])],
        "unmapped": dict(unmapped.most_common(8)),
    }


# ============================================================== first-time vs repeat
def repeat_responses(rows, odd, mature):
    """Per mailing: offers, full responses, and how many of those accounts had responded to an
    earlier mailing in the extract. Plus response rate by the account's offer number, and for
    repeat responders whether this response sat on a higher rung than their best before.

    A response is a MET goal ('<Mon> Resp' in before_after.RESP_MET) — the same definition as
    every other responder figure in the deck. 'NU 1-4' is a partial and is not counted.
    """
    g, personal = odd.g, odd.personal
    per = {m: {"mailed": 0, "resp": 0, "first": 0, "repeat": 0} for m in mature}
    by_n = defaultdict(lambda: [0, 0])          # offer number -> [mailed, responded]
    moves = Counter()
    for r in rows:
        if not personal(r):
            continue
        n_offers, best = 0, None
        for m in mature:
            if not g(r, f"{m} Mail"):
                continue
            n_offers += 1
            code = g(r, f"{m} Resp")
            hit = code in BA.RESP_MET
            p = per[m]
            p["mailed"] += 1
            k = min(n_offers, 5)
            by_n[k][0] += 1
            if hit:
                p["resp"] += 1
                by_n[k][1] += 1
                rank = RESP_RANK.get(code)
                if best is None:
                    p["first"] += 1
                else:
                    p["repeat"] += 1
                    if rank is not None:
                        moves["Up" if rank > best else ("Same" if rank == best else "Down")] += 1
                if rank is not None:
                    best = rank if best is None else max(best, rank)
    mailings = [{"m": label(m), **v, "rate": _pct(v["resp"], v["mailed"])}
                for m, v in per.items() if v["mailed"]]
    if not mailings or not any(x["resp"] for x in mailings):
        return {"available": False, "reason": "no mailing in the extract has a met goal"}
    first = sum(x["first"] for x in mailings)
    repeat = sum(x["repeat"] for x in mailings)
    return {
        "available": True, "mailings": mailings,
        "first_time": first, "repeat": repeat,
        "repeat_pct": _pct(repeat, first + repeat),
        "by_offer_number": [{"n": ("5+" if k == 5 else str(k)), "mailed": v[0],
                             "responded": v[1], "rate": _pct(v[1], v[0])}
                            for k, v in sorted(by_n.items())],
        "moves": {k: moves.get(k, 0) for k in ("Up", "Same", "Down")},
        "moved_up_pct": _pct(moves.get("Up", 0), sum(moves.values())),
    }


# ============================================================== activation
ACTIVATION_LOOKBACK = 3   # months of zero swipes on file before a first swipe counts
MAIL_LEAD = 3             # an offer this many months before the first swipe (or that month)


def activation_split(rows, odd, act_months, mailmonths, window=12):
    """First swipes in the last `window` complete months, split three ways.

      new account       opened inside the window — onboarding, not the program's to claim
      mailed first      an existing account (opened before the window) with an offer in the
                        first-swipe month or the MAIL_LEAD months before it
      on its own        an existing account with no such offer

    A first swipe is the first month with a swipe, after at least ACTIVATION_LOOKBACK months
    on file with none — an account whose first month on file already swipes has no first swipe
    we can see.
    """
    if len(act_months) < window + ACTIVATION_LOOKBACK:
        return {"available": False, "months": len(act_months),
                "needs": window + ACTIVATION_LOOKBACK}
    g, personal, swipes = odd.g, odd.personal, odd.swipes
    W = act_months[-window:]
    w0 = mkey(W[0])
    idx = {m: i for i, m in enumerate(act_months)}
    mail_set = set(mailmonths)
    n = Counter()
    for r in rows:
        if not personal(r):
            continue
        first = None
        for i, m in enumerate(act_months):
            if swipes(r, m) > 0:
                first = i
                break
        if first is None or act_months[first] not in W or first < ACTIVATION_LOOKBACK:
            continue
        do = _parse_date(g(r, "Date Opened"))
        opened = datetime.datetime(do.year, do.month, 1) if do else None
        if opened is None:
            n["unknown"] += 1
            continue
        # months with zero swipes that the account was actually open for
        on_file = sum(1 for m in act_months[max(0, first - ACTIVATION_LOOKBACK):first]
                      if mkey(m) >= opened)
        if opened >= w0:
            n["new"] += 1
            continue
        if on_file < ACTIVATION_LOOKBACK:
            continue
        lead = act_months[max(0, first - MAIL_LEAD):first + 1]
        mailed = any(m in mail_set and g(r, f"{m} Mail") for m in lead)
        n["mailed" if mailed else "organic"] += 1
    existing = n["mailed"] + n["organic"]
    total = existing + n["new"]
    return {
        "available": bool(total),
        "window": [label(W[0]), label(W[-1])],
        "first_swipes": total, "new": n["new"], "mailed": n["mailed"],
        "organic": n["organic"], "existing": existing, "unknown_opened": n["unknown"],
        "program_pct": _pct(n["mailed"], existing),
    }


# ============================================================== tier movement by group
def movement_by_group(rows, odd, act_months, mature, latest, span=12, win=3):
    """Share of eligible personal card holders moving up, holding or dropping a swipe tier
    between a window a year ago and the latest window, by response status in between."""
    if len(act_months) < span + win:
        return {"available": False, "months": len(act_months), "needs": span + win}
    g, personal, hascard, swipes = odd.g, odd.personal, odd.hascard, odd.swipes
    elig_col = f"{latest} Elig"
    now_w, then_w = act_months[-win:], act_months[-(span + win):-span]
    between = [m for m in mature if mkey(then_w[-1]) <= mkey(m) < mkey(now_w[0])]
    rank = {t: i for i, t in enumerate(TIER_ORDER)}
    n = {k: Counter() for k in ("Responder", "Mailed non-responder", "Not mailed")}
    for r in rows:
        if not (personal(r) and hascard(r) and g(r, elig_col) == "Yes"):
            continue
        a = swipe_tier(sum(swipes(r, m) for m in then_w) / win)
        b = swipe_tier(sum(swipes(r, m) for m in now_w) / win)
        mailed = [m for m in between if g(r, f"{m} Mail")]
        resp = any(g(r, f"{m} Resp") in BA.RESP_MET for m in mailed)
        grp = "Responder" if resp else ("Mailed non-responder" if mailed else "Not mailed")
        mv = "up" if rank[b] > rank[a] else ("down" if rank[b] < rank[a] else "same")
        n[grp][mv] += 1
    out = []
    for grp, c in n.items():
        tot = sum(c.values())
        out.append({"group": grp, "accounts": tot, "up": _pct(c["up"], tot),
                    "same": _pct(c["same"], tot), "down": _pct(c["down"], tot),
                    "thin": tot < MIN_GROUP})
    return {"available": any(x["accounts"] for x in out), "groups": out,
            "mailings": [label(m) for m in between],
            "then_window": [label(then_w[0]), label(then_w[-1])],
            "now_window": [label(now_w[0]), label(now_w[-1])]}


# ============================================================== per-mailing control
def per_mailing_control(rows, odd, act_months, mature):
    """Responders vs mailed non-responders, one row per mailing — the pooled comparison on the
    Responders vs Mailed Non-Responders slide, unpooled. Same windows, cohorts and winsorizing
    (before_after), each mailing winsorized on its own."""
    g, spend, personal = odd.g, odd.spend, odd.personal
    mature = [m for m in mature if m in act_months]
    bw, aw, mailings = BA.windows(act_months, mature)
    pop = [r for r in rows if personal(r)]
    out = []
    for m in mailings:
        i = act_months.index(m)
        pre, post = act_months[i - bw:i], act_months[i + 1:i + 1 + aw]
        resp = [r for r in pop if g(r, f"{m} Resp") in BA.RESP_MET]
        ctrl = [r for r in pop if g(r, f"{m} Mail") and g(r, f"{m} Resp") not in BA.RESP_MET]
        row = {"m": label(m), "responders": len(resp), "control": len(ctrl)}
        if len(resp) < BA.MIN_RESPONDERS or len(ctrl) < BA.MIN_RESPONDERS:
            row["thin"] = True
            out.append(row)
            continue
        for key, cohort in (("r", resp), ("c", ctrl)):
            b = [statistics.mean(spend(x, t) for t in pre) for x in cohort]
            a = [statistics.mean(spend(x, t) for t in post) for x in cohort]
            wb_, wa_ = BA.wins_pair(b, a)
            row[key + "_before"] = round(statistics.mean(wb_))
            row[key + "_after"] = round(statistics.mean(wa_))
        row["r_change"] = row["r_after"] - row["r_before"]
        row["c_change"] = row["c_after"] - row["c_before"]
        row["did"] = row["r_change"] - row["c_change"]
        row["thin"] = False
        out.append(row)
    measured = [r for r in out if not r["thin"]]
    return {"available": bool(measured), "mailings": out,
            "before_months": bw, "after_months": aw,
            "positive": sum(1 for r in measured if r["did"] > 0),
            "measured": len(measured)}


# ============================================================== closures
TOP_PRODUCTS = 6


def where_accounts_close(rows, odd, latest, top_products=TOP_PRODUCTS, min_branch=ATTRITION_MIN):
    """12-month closure rate of personal accounts by product and by branch.

    Closure rate = personal accounts closed in the trailing 12 months / (open personal accounts
    + those closures) — the Branch Scorecard's definition, so the totals agree with it.
    """
    g, personal, isopen = odd.g, odd.personal, odd.isopen
    now = _month_end(latest)
    since = _months_back(latest, 11)
    prod, br = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    for r in rows:
        if not personal(r):
            continue
        op = isopen(r)
        dc = _parse_date(g(r, "Date Closed"))
        closed = (not op) and dc is not None and since <= dc <= now
        if not (op or closed):
            continue
        p = (g(r, "Prod Desc") or g(r, "Prod Code") or "").strip() or "Not on file"
        b = g(r, "Branch") or "(blank)"
        for d, k in ((prod, p), (br, b)):
            d[k][0] += 1
            d[k][1] += closed
    if not prod:
        return {"available": False, "reason": "no open or recently closed personal account"}

    def rows_of(d, keep):
        out, rest = [], [0, 0, 0]
        for k, (n, c) in sorted(d.items(), key=lambda kv: -kv[1][0]):
            if keep(k, n):
                out.append({"name": k, "at_risk": n, "closed": c, "rate": _pct(c, n)})
            else:
                rest[0] += n
                rest[1] += c
                rest[2] += 1
        if rest[2]:
            out.append({"name": f"All other ({rest[2]})", "at_risk": rest[0],
                        "closed": rest[1], "rate": _pct(rest[1], rest[0]), "rollup": True})
        return out

    top = {k for k, _v in sorted(prod.items(), key=lambda kv: -kv[1][0])[:top_products]}
    products = rows_of(prod, lambda k, n: k in top)
    branches = rows_of(br, lambda k, n: n >= min_branch)
    tot_n = sum(v[0] for v in prod.values())
    tot_c = sum(v[1] for v in prod.values())
    rated = [b for b in branches if not b.get("rollup")]
    return {
        "available": True, "products": products, "branches": branches,
        "total": {"at_risk": tot_n, "closed": tot_c, "rate": _pct(tot_c, tot_n)},
        "window": [since.strftime("%b %Y"), now.strftime("%b %Y")],
        "min_branch": min_branch,
        "branch_high": max(rated, key=lambda b: b["rate"]) if rated else None,
        "branch_low": min(rated, key=lambda b: b["rate"]) if rated else None,
    }


# ============================================================== months of warning
def months_of_warning(rows, odd, act_months, latest, months=WARNING_MONTHS, ratio=WARNING_RATIO):
    """Card spend of personal card holders that closed in the last 12 months, by months before
    the close, against still-open personal card holders in the SAME calendar months.

    Ratio at offset k = mean spend of closers k months before their close month / mean spend of
    open card holders in those same calendar months. The warning is the earliest offset from
    which the ratio stays below `ratio` all the way to the close.
    """
    g, personal, hascard, isopen, spend = odd.g, odd.personal, odd.hascard, odd.isopen, odd.spend
    idx = {m: i for i, m in enumerate(act_months)}
    open_sum, open_n = defaultdict(float), 0
    closers = []
    since = _months_back(latest, 11)
    for r in rows:
        if not personal(r):
            continue
        if isopen(r):
            if not hascard(r):
                continue
            open_n += 1
            for m in act_months[-(months + 12):]:
                open_sum[m] += spend(r, m)
            continue
        dc = _parse_date(g(r, "Date Closed"))
        if dc is None or dc < since:
            continue
        cm = _month_token(dc)
        if cm not in idx or idx[cm] < months:
            continue
        # The Debit? flag is read at the snapshot, and a closed account has usually lost its
        # card by then (on 1539 only 44 of the year's closers still carried the flag). A
        # closer counts as a card user when it spent on a card in the year before it closed.
        series = [spend(r, act_months[idx[cm] - k]) for k in range(1, months + 1)]
        if any(v > 0 for v in series):
            closers.append((idx[cm], series))
    if not closers or not open_n:
        return {"available": False, "closers": len(closers),
                "reason": "no personal card holder closed inside the complete months of this "
                          "extract with a year of history before it"}
    open_mean = {m: v / open_n for m, v in open_sum.items()}
    curve = []
    for k in range(1, months + 1):
        c = statistics.mean(s[k - 1] for _i, s in closers)
        comp = statistics.mean(open_mean.get(act_months[i - k], 0.0) for i, _s in closers)
        curve.append({"k": k, "closers": round(c), "open": round(comp),
                      "ratio": round(c / comp, 3) if comp else None})
    warning = None
    for k in range(1, months + 1):
        seg = [p["ratio"] for p in curve[:k]]
        if all(x is not None and x < ratio for x in seg):
            warning = k
        else:
            break
    return {"available": True, "closers": len(closers), "open_accounts": open_n,
            "window": [since.strftime("%b %Y"), label(act_months[-1])],
            "curve": curve, "warning": warning, "ratio": ratio}


# ============================================================== concurrent stressors
STRESS_NAMES = ["Card spend fading", "Overdrawing", "Balance drawn down"]


def stressors(rows, odd, act_months, nsf_months, latest, win=STRESS_WINDOW):
    """Open ARS-eligible personal accounts by how many stress conditions they trip at once.

      Card spend fading    carded; the last `win` complete months average below 80% of the
                           `win` before them, or no spend in all of the last `win` (used before)
      Overdrawing          at least one NSF/OD item in the last `win` months complete for NSF/OD
      Balance drawn down   current balance below half the average balance (Curr Bal vs Avg Bal)
    """
    if len(act_months) < 2 * win or len(nsf_months) < win:
        return {"available": False, "reason": "too few complete months for the windows"}
    g, personal, hascard, isopen, spend, nsf = (odd.g, odd.personal, odd.hascard, odd.isopen,
                                                odd.spend, odd.nsf)
    elig_col = f"{latest} Elig"
    rec, pri, nw = act_months[-win:], act_months[-2 * win:-win], nsf_months[-win:]
    by_count, combos = Counter(), Counter()
    held = defaultdict(float)
    have_bal = False
    base = 0
    for r in rows:
        if not (personal(r) and isopen(r) and g(r, elig_col) == "Yes"):
            continue
        base += 1
        flags = []
        if hascard(r):
            a = sum(spend(r, m) for m in rec) / win
            b = sum(spend(r, m) for m in pri) / win
            used_before = any(spend(r, m) > 0 for m in act_months[:-win])
            if (b > 0 and a < 0.8 * b) or (a <= 0 and used_before):
                flags.append(STRESS_NAMES[0])
        if any(nsf(r, m) > 0 for m in nw):
            flags.append(STRESS_NAMES[1])
        avg, cur = odd.fnum(r, "Avg Bal"), odd.fnum(r, "Curr Bal")
        if avg or cur:
            have_bal = True
        if avg > 0 and cur < DRAWDOWN * avg:
            flags.append(STRESS_NAMES[2])
        by_count[len(flags)] += 1
        if flags:
            combos[" + ".join(flags)] += 1
        held[len(flags)] += max(cur, 0.0)
    if not base:
        return {"available": False, "reason": "no open ARS-eligible personal account"}
    multi = sum(v for k, v in by_count.items() if k >= 2)
    return {
        "available": True, "base": base,
        "by_count": [{"n": k, "accounts": by_count.get(k, 0),
                      "pct": _pct(by_count.get(k, 0), base),
                      "balances": round(held.get(k, 0.0))} for k in range(0, 4)],
        "combos": [[k, v] for k, v in combos.most_common()],
        "multi": multi, "multi_pct": _pct(multi, base),
        "multi_balances": round(sum(v for k, v in held.items() if k >= 2)),
        "balances_carried": have_bal,
        "recent_window": [label(rec[0]), label(rec[-1])],
        "prior_window": [label(pri[0]), label(pri[-1])],
        "nsf_window": [label(nw[0]), label(nw[-1])],
    }


# ============================================================== where cards lag
def card_gaps(rows, odd, latest, n=3, min_branch=40):
    """Branch share of ARS-eligible personal accounts against branch share of the book's cards,
    and the cards each branch is short of the book's take rate."""
    g, personal, hascard = odd.g, odd.personal, odd.hascard
    elig_col = f"{latest} Elig"
    by = defaultdict(lambda: [0, 0])
    for r in rows:
        if personal(r) and g(r, elig_col) == "Yes":
            b = by[g(r, "Branch") or "(blank)"]
            b[0] += 1
            b[1] += hascard(r)
    elig = sum(v[0] for v in by.values())
    cards = sum(v[1] for v in by.values())
    if not elig:
        return {"available": False, "reason": "no ARS-eligible personal account"}
    book = cards / elig
    rows_out = []
    for k, (e, c) in by.items():
        short = max(0, round(e * book) - c)
        rows_out.append({"branch": k, "eligible": e, "cards": c, "no_card": e - c,
                         "take": _pct(c, e), "share_eligible": _pct(e, elig),
                         "share_cards": _pct(c, cards), "short": short})
    rated = [x for x in rows_out if x["eligible"] >= min_branch]
    gaps = sorted([x for x in rated if x["short"] > 0], key=lambda x: -x["short"])
    return {"available": True, "eligible": elig, "cards": cards, "no_card": elig - cards,
            "take": _pct(cards, elig), "branches": sorted(rows_out, key=lambda x: -x["no_card"]),
            "gaps": gaps[:n], "gap_cards": sum(x["short"] for x in gaps[:n]),
            "min_branch": min_branch}


# ============================================================== value of a card / opt-in
def _rates(workbook_path):
    if not workbook_path or not os.path.exists(str(workbook_path)):
        return None, "no ARS workbook was found for this period"
    try:
        import lift_values as LV
        a = LV.workbook_assumptions(str(workbook_path))
    except Exception as e:                                   # pragma: no cover
        return None, f"the workbook's Key Assumptions could not be read ({type(e).__name__})"
    if not a.get("ic_rate") or not a.get("nsf_fee"):
        missing = [k for k, v in (("Interchange Rate", a.get("ic_rate")),
                                  ("NSF Fee", a.get("nsf_fee"))) if not v]
        return None, ("the workbook carries no " + " or ".join(missing) +
                      " on its Actuals tab")
    return a, None


TENURE_BANDS = [(0, 12, "Under 1 year"), (12, 36, "1 to 3 years"), (36, 60, "3 to 5 years"),
                (60, 120, "5 to 10 years"), (120, None, "10 years or more")]


def account_value(rows, odd, both_months, latest, workbook_path, months=12, min_branch=40):
    """Annual value per account at the workbook's own rates:
        interchange = Interchange Rate x debit spend (Sig $ + PIN $)
        NSF/OD fees = NSF Fee x NSF/OD items (MTD), at 100% collection
    over the last `months` months complete for BOTH activity and NSF/OD. Card: carded vs
    cardless ARS-eligible personal accounts. Opt-in: opted-in vs opted-out open personal card
    holders. Ladder: eligible accounts by tenure. Branches: value per eligible account.
    """
    a, why = _rates(workbook_path)
    if a is None:
        return {"available": False, "reason": why}
    if len(both_months) < months:
        return {"available": False, "reason": f"only {len(both_months)} complete months"}
    ic, fee = a["ic_rate"], a["nsf_fee"]
    g, personal, hascard, isopen = odd.g, odd.personal, odd.hascard, odd.isopen
    W = both_months[-months:]
    now = _month_end(latest)
    elig_col, rege_col = f"{latest} Elig", f"{latest} Reg E Desc"
    grp = defaultdict(lambda: [0, 0.0, 0.0])       # n, interchange, fees
    ladder = defaultdict(lambda: [0, 0.0, 0.0])
    branch = defaultdict(lambda: [0, 0.0, 0.0, 0])  # n, ic, fees, cards

    def add(d, k, i, f):
        d[k][0] += 1
        d[k][1] += i
        d[k][2] += f

    for r in rows:
        if not personal(r):
            continue
        i_ = ic * sum(odd.spend(r, m) for m in W)
        f_ = fee * sum(odd.nsf(r, m) for m in W)
        carded = hascard(r)
        if g(r, elig_col) == "Yes":
            add(grp, "Card" if carded else "No card", i_, f_)
            do = _parse_date(g(r, "Date Opened"))
            ten = None
            if do:
                mo = (now.year - do.year) * 12 + (now.month - do.month)
                ten = next((lab for lo, hi, lab in TENURE_BANDS
                            if mo >= lo and (hi is None or mo < hi)), None)
            add(ladder, ten or "Not on file", i_, f_)
            b = branch[g(r, "Branch") or "(blank)"]
            b[0] += 1
            b[1] += i_
            b[2] += f_
            b[3] += carded
        if carded and isopen(r):
            lab = rege_label(g(r, rege_col))
            if lab in (REGE_IN, REGE_OUT, REGE_DEFAULT):
                add(grp, lab, i_, f_)

    def per(d, k):
        n, i_, f_ = d[k][0], d[k][1], d[k][2]
        return {"group": k, "accounts": n,
                "interchange": round(i_ / n) if n else None,
                "fees": round(f_ / n) if n else None,
                "total": round((i_ + f_) / n) if n else None}

    groups = {k: per(grp, k) for k in ("Card", "No card", REGE_IN, REGE_OUT, REGE_DEFAULT)}
    card_delta = (groups["Card"]["total"] - groups["No card"]["total"]
                  if groups["Card"]["accounts"] and groups["No card"]["accounts"] else None)
    optin_delta = (groups[REGE_IN]["total"] - groups[REGE_OUT]["total"]
                   if groups[REGE_IN]["accounts"] and groups[REGE_OUT]["accounts"] else None)
    order = [b[2] for b in TENURE_BANDS] + ["Not on file"]
    lad = [per(ladder, k) for k in order if ladder[k][0]]
    br = []
    for k, (n, i_, f_, c) in branch.items():
        if n >= min_branch:
            br.append({"branch": k, "eligible": n, "take": _pct(c, n),
                       "value": round((i_ + f_) / n)})
    br.sort(key=lambda x: -x["value"])
    return {
        "available": True, "ic_rate": ic, "nsf_fee": fee, "rate_sheet": a.get("sheet"),
        "window": [label(W[0]), label(W[-1])], "months": months,
        "groups": groups, "card_delta": card_delta, "optin_delta": optin_delta,
        "no_card_accounts": groups["No card"]["accounts"],
        "ladder": lad, "branches": br, "min_branch": min_branch,
    }


# ============================================================== what a response is worth
def responder_value(rc, workbook_path, B=None):
    """The pooled responder-vs-control spend difference (combined_insights.responder_control)
    priced at the workbook's own interchange rate, beside the workbook's booked revenue.
    Two frames, named, never blended (James, revenue_frames)."""
    if not rc or not rc.get("available"):
        return {"available": False, "reason": "the responder comparison is not available"}
    a, why = _rates(workbook_path)
    if a is None:
        return {"available": False, "reason": why}
    did = rc["did"]
    ic = a["ic_rate"]
    per_month = did * ic
    obs = rc["responders"]["n"]
    return {
        "available": True, "did": did, "ic_rate": ic,
        "per_month": round(per_month, 2), "per_year": round(per_month * 12, 2),
        "observations": obs,
        "cohort_month": round(per_month * obs),
        "cohort_window": round(per_month * obs * rc.get("after_months", 6)),
        "after_months": rc.get("after_months"), "before_months": rc.get("before_months"),
        "mailings": rc.get("mailings"),
        "booked_ltd": (B or {}).get("ltd_revenue"),
        "booked_months": (B or {}).get("months"),
    }


# ============================================================== revenue per fee dollar
ROLLUP_SHEET = "All Months Rollup MM"


def mailing_pnl(workbook_path):
    """Per mailing, from the workbook's rollup: booked income to date, the respondent fees
    booked against it, and the responders it was billed for."""
    if not workbook_path or not os.path.exists(str(workbook_path)):
        return {"available": False, "reason": "no ARS workbook was found for this period"}
    import openpyxl
    wb = openpyxl.load_workbook(str(workbook_path), read_only=True, data_only=True)
    try:
        if ROLLUP_SHEET not in wb.sheetnames:
            return {"available": False, "reason": f"the workbook has no '{ROLLUP_SHEET}' sheet"}
        rows = [list(r) for r in wb[ROLLUP_SHEET].iter_rows(values_only=True)]
    finally:
        wb.close()
    out = []
    for i, row in enumerate(rows):
        lab = row[1] if len(row) > 1 else None
        if not (isinstance(lab, str) and lab.strip().endswith("Mailing")):
            continue
        try:
            d = datetime.datetime.strptime(lab.replace("Mailing", "").strip(), "%B %Y")
        except ValueError:
            continue
        vals = {}
        for k in range(i + 1, min(i + 8, len(rows))):
            name = next((c for c in rows[k] if isinstance(c, str)), "") or ""
            nums = [c for c in rows[k] if isinstance(c, (int, float)) and not isinstance(c, bool)]
            for key, want in (("income", "total incremental income"),
                              ("expense", "total incremental expense"),
                              ("responders", "number of responders")):
                if want in name.lower():
                    # the leading row number is the first numeric cell
                    vals[key] = sum(nums[1:]) if nums and nums[0] in (1, 2, 3) else sum(nums)
        if "income" not in vals:
            continue
        inc, exp, resp = vals.get("income", 0.0), abs(vals.get("expense", 0.0)), vals.get("responders", 0)
        out.append({"m": d.strftime("%b %Y"), "key": d.strftime("%Y-%m"),
                    "income": round(inc, 2), "fees": round(exp, 2), "responders": int(resp),
                    "per_fee_dollar": round(inc / exp, 2) if exp else None,
                    "per_responder": round(inc / resp, 2) if resp else None})
    out.sort(key=lambda x: x["key"])
    if not out:
        return {"available": False, "reason": f"the '{ROLLUP_SHEET}' sheet carries no mailing blocks"}
    inc = sum(x["income"] for x in out)
    fees = sum(x["fees"] for x in out)
    resp = sum(x["responders"] for x in out)
    return {"available": True, "mailings": out, "income": round(inc, 2), "fees": round(fees, 2),
            "responders": resp, "per_fee_dollar": round(inc / fees, 2) if fees else None,
            "per_responder": round(inc / resp, 2) if resp else None,
            "unbilled": [x["m"] for x in out if not x["fees"]]}


# ============================================================== offer segments
def offer_segments(rows, odd, act_months, mature, ic_rate=None):
    """Per offer segment ('<Mon> Mail' code: NU, TH-10, ...), pooled over the measurable
    mailings: offers, met goals, response rate, and the responder-minus-control change in
    monthly spend per 1,000 offers — the before_after windows and winsorizing."""
    g, spend, personal = odd.g, odd.spend, odd.personal
    mature = [m for m in mature if m in act_months]
    bw, aw, mailings = BA.windows(act_months, mature)
    seg = defaultdict(lambda: {"mailed": 0, "resp": 0, "r": [[], []], "c": [[], []]})
    for r in rows:
        if not personal(r):
            continue
        for m in mailings:
            code = g(r, f"{m} Mail")
            if not code:
                continue
            i = act_months.index(m)
            pre, post = act_months[i - bw:i], act_months[i + 1:i + 1 + aw]
            s = seg[code]
            s["mailed"] += 1
            hit = g(r, f"{m} Resp") in BA.RESP_MET
            s["resp"] += hit
            k = "r" if hit else "c"
            s[k][0].append(statistics.mean(spend(r, t) for t in pre))
            s[k][1].append(statistics.mean(spend(r, t) for t in post))
    out = []
    for code, s in sorted(seg.items(), key=lambda kv: (kv[0] != "NU", kv[0])):
        row = {"segment": code, "mailed": s["mailed"], "responded": s["resp"],
               "rate": _pct(s["resp"], s["mailed"])}
        if len(s["r"][0]) >= BA.MIN_RESPONDERS and len(s["c"][0]) >= BA.MIN_RESPONDERS:
            rb, ra = BA.wins_pair(*s["r"])
            cb, ca = BA.wins_pair(*s["c"])
            did = (statistics.mean(ra) - statistics.mean(rb)) - (statistics.mean(ca) - statistics.mean(cb))
            row["did"] = round(did)
            row["did_per_1k"] = round(did * s["resp"] / s["mailed"] * 1000) if s["mailed"] else None
            row["ic_per_1k"] = round(row["did_per_1k"] * ic_rate) if (ic_rate and row["did_per_1k"] is not None) else None
        else:
            row["did"] = row["did_per_1k"] = row["ic_per_1k"] = None
        out.append(row)
    return {"available": bool(out), "segments": out, "mailings": [label(m) for m in mailings],
            "before_months": bw, "after_months": aw, "ic_rate": ic_rate}


# ============================================================== cascade
def cascade(rows, odd, act_months, mature, latest, B=None):
    """Eligible -> carded -> swiping in the last complete month -> ever offered -> ever met a
    goal, from the ODD; then the workbook's booked revenue to date. Every step is the count on
    the step above's population, so the funnel narrows honestly."""
    g, personal, hascard, swipes = odd.g, odd.personal, odd.hascard, odd.swipes
    elig_col = f"{latest} Elig"
    last = act_months[-1] if act_months else None
    n = Counter()
    for r in rows:
        if not (personal(r) and g(r, elig_col) == "Yes"):
            continue
        n["eligible"] += 1
        if not hascard(r):
            continue
        n["carded"] += 1
        if last and swipes(r, last) > 0:
            n["active"] += 1
        mailed = [m for m in mature if g(r, f"{m} Mail")]
        if mailed:
            n["mailed"] += 1
            if any(g(r, f"{m} Resp") in BA.RESP_MET for m in mailed):
                n["responded"] += 1
    if not n["eligible"]:
        return {"available": False, "reason": "no ARS-eligible personal account"}
    steps = [["ARS-eligible personal accounts", n["eligible"]],
             ["Holding a debit card", n["carded"]],
             [f"Swiping in {label(last)}" if last else "Swiping", n["active"]],
             ["Offered by a mailing in this extract", n["mailed"]],
             ["Met a mailing's goal", n["responded"]]]
    return {"available": True, "steps": steps, "last_month": label(last) if last else None,
            "booked_ltd": (B or {}).get("ltd_revenue"), "booked_months": (B or {}).get("months"),
            "mailings": len(mature)}


# ============================================================== card spend by merchant
# Coarse merchant groups from published Merchant Category Code ranges (ISO 18245). The grouping
# is OURS and deliberately coarse; James's version keys on his own MCC map and dictionaries,
# which are not on the share.
MCC_GROUPS = [
    ("Grocery", [(5411, 5411), (5422, 5422), (5441, 5451), (5462, 5462), (5499, 5499)]),
    ("Restaurants", [(5811, 5814)]),
    ("Fuel and auto", [(5511, 5599), (5983, 5983), (7511, 7549)]),
    ("Discount and department", [(5300, 5399), (5310, 5311), (5200, 5299)]),
    ("Online and digital", [(5815, 5818), (5960, 5969), (4816, 4816)]),
    ("Money transfer", [(4829, 4829), (6010, 6012), (6050, 6051), (6211, 6211), (6540, 6540)]),
    ("Bills and utilities", [(4812, 4814), (4899, 4900), (6300, 6399), (9311, 9311)]),
    ("Health", [(5912, 5912), (5975, 5976), (8011, 8099)]),
    ("Travel and transport", [(3000, 3999), (4011, 4789), (7011, 7011), (7512, 7512)]),
    ("Entertainment", [(7800, 7999), (5940, 5949)]),
    ("Other retail", [(5000, 5999)]),
    ("Services", [(7000, 8999)]),
    ("Government and other", [(9000, 9999)]),
]


def mcc_group(mcc):
    try:
        v = int(str(mcc).strip())
    except (TypeError, ValueError):
        return "Not coded"
    for name, spans in MCC_GROUPS:
        if any(lo <= v <= hi for lo, hi in spans):
            return name
    return "Other"


CARD_RAILS = ("SIG", "PIN")


def _txn_source(odd_path, client_id=None):
    """(opener, name) for the one month of card transactions: the ODD zip's own transaction
    member first, then the newest file in Inputs/Txn Files/<id>/."""
    if odd_path and str(odd_path).lower().endswith(".zip"):
        try:
            zf = zipfile.ZipFile(odd_path)
            names = [n for n in zf.namelist() if "transaction" in n.lower()]
            if names:
                n = names[0]
                return (lambda: io.TextIOWrapper(zf.open(n), encoding="latin-1",
                                                 errors="replace", newline="")), n
        except (OSError, zipfile.BadZipFile):
            pass
    if client_id:
        try:
            import rpe_env as R
            files = R.txn_files(client_id)
            if files:
                f = sorted(files, key=lambda p: p.stat().st_mtime)[-1]
                return (lambda: R.open_txn(f, "r", "latin-1")), f.name
        except Exception:                                    # pragma: no cover
            pass
    return None, None


def card_spend_mix(odd_path, client_id=None, max_rows=None):
    """Card spend and transactions by merchant group, one month, every card in the file.

    Layout read: date, account, rail (SIG/PIN), amount, MCC, location, ... tab-separated, with
    one header line. A line whose amount or date does not parse is counted and skipped.
    """
    opener, name = _txn_source(odd_path, client_id)
    if opener is None:
        return {"available": False,
                "reason": "no card transaction file for this client (none in the ODD zip, "
                          "none in Inputs/Txn Files)"}
    grp = defaultdict(lambda: [0, 0.0])
    states = Counter()
    rails = defaultdict(lambda: [0, 0.0])
    dmin = dmax = None
    bad = 0
    n = 0
    with opener() as fh:
        for k, line in enumerate(fh):
            if k == 0 and "\t" not in line:
                continue                       # the pipe-delimited header line
            parts = line.rstrip("\r\n").split("\t")
            if len(parts) < 5:
                bad += 1
                continue
            try:
                amt = float(parts[3].replace(",", "").strip())
                d = datetime.datetime.strptime(parts[0].strip(), "%m/%d/%Y")
            except ValueError:
                bad += 1
                continue
            n += 1
            rail = parts[2].strip().upper() or "?"
            rails[rail][0] += 1
            rails[rail][1] += amt
            dmin = d if dmin is None or d < dmin else dmin
            dmax = d if dmax is None or d > dmax else dmax
            if max_rows and n >= max_rows:
                break
            # The file is not card-only: 1539's carries ACH and check lines too, and those have
            # no merchant. Merchant groups read the two CARD rails only; the rail totals keep
            # every line, for the "how the money moves" view.
            if rail not in CARD_RAILS:
                continue
            gname = mcc_group(parts[4])
            grp[gname][0] += 1
            grp[gname][1] += amt
            loc = parts[5].strip() if len(parts) > 5 else ""
            m = re.search(r"\b([A-Z]{2})$", loc)
            if m:
                states[m.group(1)] += amt
    if not n:
        return {"available": False, "reason": f"{name} carries no readable transactions"}
    if not grp:
        return {"available": False,
                "reason": f"{name} carries no card (SIG or PIN) transactions",
                "rails": {k: {"txns": v[0], "spend": round(v[1])} for k, v in rails.items()}}
    tot_n = sum(v[0] for v in grp.values())
    tot_d = sum(v[1] for v in grp.values())
    groups = sorted(({"group": k, "txns": v[0], "spend": round(v[1]),
                      "share_spend": _pct(v[1], tot_d), "share_txns": _pct(v[0], tot_n),
                      "ticket": round(v[1] / v[0], 2) if v[0] else None}
                     for k, v in grp.items()), key=lambda x: -x["spend"])
    home, home_amt = (states.most_common(1)[0] if states else (None, 0))
    first, last = dmin, dmax
    month_end = (first.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)
    return {
        "available": True, "file": name, "txns": tot_n, "spend": round(tot_d),
        "ticket": round(tot_d / tot_n, 2) if tot_n else None,
        "groups": groups, "skipped": bad,
        "first_date": first.strftime("%m/%d/%Y"), "last_date": last.strftime("%m/%d/%Y"),
        "month": first.strftime("%b %Y"),
        "complete": last.date() >= month_end.date() - datetime.timedelta(days=1),
        "home_state": home, "home_share": _pct(home_amt, tot_d) if home else None,
        "rails": {k: {"txns": v[0], "spend": round(v[1])} for k, v in rails.items()},
    }


# ============================================================== entry point
def compute(d, odd, odd_path=None, workbook_path=None, M=None, B=None, ci=None, client_id=None):
    """Every view above, from the rows combined_insights.read_odd already holds."""
    rows, smonths, latest = d["rows"], d["smonths"], d["latest"]
    nextm = {smonths[i]: smonths[i + 1] for i in range(len(smonths) - 1)}
    mature = [m for m in d["mailmonths"] if m in nextm]
    cm = completeness(rows, odd, smonths, odd_path)
    act, nsf, both = cm["activity"], cm["nsf"], cm["both"]
    out = {"completeness": cm}
    out["rege_trend"] = rege_trend(rows, odd, smonths, d["H"])
    out["repeat_responses"] = repeat_responses(rows, odd, mature)
    out["activation_split"] = activation_split(rows, odd, act, d["mailmonths"])
    out["movement_by_group"] = movement_by_group(rows, odd, act, mature, latest)
    out["per_mailing_control"] = per_mailing_control(rows, odd, act, mature)
    out["where_accounts_close"] = where_accounts_close(rows, odd, latest)
    out["months_of_warning"] = months_of_warning(rows, odd, act, latest)
    out["stressors"] = stressors(rows, odd, act, nsf, latest)
    out["card_gaps"] = card_gaps(rows, odd, latest)
    out["account_value"] = account_value(rows, odd, both, latest, workbook_path)
    out["responder_value"] = responder_value((ci or {}).get("responder_control"),
                                             workbook_path, B)
    out["mailing_pnl"] = mailing_pnl(workbook_path)
    av = out["account_value"]
    out["offer_segments"] = offer_segments(rows, odd, act, mature,
                                           av.get("ic_rate") if av.get("available") else None)
    out["cascade"] = cascade(rows, odd, act, mature, latest, B)
    out["card_spend_mix"] = card_spend_mix(odd_path, client_id)
    return out
