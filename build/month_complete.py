#!/usr/bin/env python3
"""
month_complete.py — is this month complete? One definition, for every program.

Standing rule (Aaron, 2026-09-17): "Don't calculate YoY or comparisons on partial
months, only use complete months."

THE DEFECT BEHIND IT. Marine FCU 1539's 2026.09 NSF/OD slide said "-98% Items YoY
(Aug 25 -> Aug 26)". The ODD extract was pulled 09/04/26, so August had ended, and
its swipe and spend columns were whole (1,104,224 swipes against 1,103,258 in July).
But its `Aug26 MTD` column held 390 NSF/OD items on 290 accounts, against 19,451 on
4,480 in July: the NSF/OD half of the month simply was not in the file. A comparison
cannot tell a half-loaded month from a real collapse, so it reported the collapse.
The same scan of every 2026.09 extract found 1774 in the same state (5% of its usual
NSF/OD items) — and nothing else below 51%.

So completeness is judged PER MEASURE, from two independent signals:

1. **The calendar.** A month cannot be complete in data pulled before it ended. The
   ODD extract names its pull stamp in the member file name — "...(090426_134750)..."
   is 09/04/26 — and a weekly report carries its generation date. `month_ended()` is
   that rule: the month is complete only when the as-of date is on or after the first
   day of the following month. No as-of date, no verdict from this rule.

2. **The activity.** A month whose total for a measure is BELOW HALF the median of the
   six months before it is incomplete for that measure (`PARTIAL_SHARE`,
   `BASELINE_MONTHS`). Evidence for the numbers, from every ODD extract on hand on
   2026-09-17 (83 clients, the trailing three months of each): the two partial months
   read 2% and 5% of their baseline (NSF/OD accounts 7% and 12%); every other month of
   swipes, spend, NSF/OD items and NSF/OD accounts read 51% or more (1800's July NSF/OD
   items, a real dip one month before a normal August), and all but two read 71% or
   more. Half sits between the two groups. A six-month median rather than the prior month keeps one
   seasonal month (February, December) from being the yardstick.

   Only TRAILING months are judged: the check walks back from the newest month while
   the month is below half its own baseline, and stops at the first month that is not.
   A dip in the middle of a series is data, not an unfinished extract. It walks back
   at most `MAX_TRAILING` months: a fall that holds for three months or more is a real
   change (a client that stops charging NSF fees), and hiding it would be the opposite
   error. Fewer than `MIN_BASELINE` baseline months, or a baseline median below
   `MIN_VOLUME`, and there is nothing to judge against — the month is treated as
   complete. The volume floor is what keeps the rule off small counts: an MRPC client
   enrolling 2-6 cards a month has months of 0 that are real, and a ratio on numbers
   that small is noise. It is a COUNT floor: a caller passing an already-scaled series
   (the workbook's spend in $M) passes `min_volume=0`.

WHAT A CALLER DOES WITH IT. Every comparison — YoY, month over month, a "latest month"
tile, the end of a trend, a trailing window — uses the last complete month of the
measures it reads. An excluded month is never zeroed and its slide is never dropped:
the slide or its notes say which month was left out and why (`excluded_sentence`).
Aaron's +/-2% movement wording is untouched: it describes the comparison, this module
only decides which months the comparison may use.

IMPORT-SAFE. Nothing here reads a file, sys.argv or a month constant.
"""
from __future__ import annotations

import datetime
import re
import statistics

PARTIAL_SHARE = 0.5
BASELINE_MONTHS = 6
MIN_BASELINE = 3
MAX_TRAILING = 2
MIN_VOLUME = 50

_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def month_start(token):
    """'Aug26' / 'Aug 26' / 'Aug 2026' / 'August 2026' / '2026-08' / '2026-08-31' / date
    -> date(2026, 8, 1), or None."""
    if isinstance(token, datetime.datetime):
        return token.date().replace(day=1)
    if isinstance(token, datetime.date):
        return token.replace(day=1)
    t = " ".join(str(token or "").split())
    iso = re.match(r"^(\d{4})-(\d{2})(?:-\d{2})?$", t)
    if iso:
        mo = int(iso.group(2))
        return datetime.date(int(iso.group(1)), mo, 1) if 1 <= mo <= 12 else None
    m = re.match(r"^([A-Za-z]{3})[A-Za-z]*\.?\s*'?(\d{2}|\d{4})$", t)
    if not m or m.group(1).title() not in _MON:
        return None
    y = int(m.group(2))
    return datetime.date(y if y > 99 else 2000 + y, _MON.index(m.group(1).title()) + 1, 1)


def label(token):
    """'Aug26' -> 'Aug 2026' (the as-of form the decks print)."""
    d = month_start(token)
    return f"{_MON[d.month - 1]} {d.year}" if d else str(token)


def month_ended(token, as_of):
    """True when `as_of` falls on or after the first day of the month after `token`.

    None when either side is unknown — the calendar rule then gives no verdict.
    """
    d = month_start(token)
    if d is None or as_of is None:
        return None
    if isinstance(as_of, datetime.datetime):
        as_of = as_of.date()
    nxt = datetime.date(d.year + (d.month // 12), d.month % 12 + 1, 1)
    return as_of >= nxt


def report_date(stamp):
    """'9/13/2026 8:06:12 AM' (a weekly report's generation stamp) -> date, or None."""
    m = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})", str(stamp or ""))
    if not m:
        return None
    try:
        return datetime.date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
    except ValueError:
        return None


def pull_date(name):
    """The pull date an ODD extract's file name carries, or None.

    The data team stamps the member file "(MMDDYY_HHMMSS)":
    "1539-2026-09-Marine FCU-ODD  (Sep23 forward) (090426_134750)_V2_1_1.csv" -> 2026-09-04.
    """
    m = re.search(r"\((\d{6})_\d{6}\)", str(name or ""))
    if not m:
        return None
    try:
        return datetime.datetime.strptime(m.group(1), "%m%d%y").date()
    except ValueError:
        return None


def assess(tokens, values, as_of=None, measure="", min_volume=MIN_VOLUME):
    """Which trailing months of one measure are incomplete.

    `tokens` the months, oldest first ('Aug26', 'Aug 26', dates — anything month_start reads)
    `values` that measure's total for each month, same order (None = not carried)
    `as_of`  the date the data was pulled or generated, when known

    Returns a JSON-safe dict:
        {"measure", "last_complete" (a token from `tokens`, or None),
         "complete" (count of leading months usable), "excluded": [
             {"month", "value", "baseline", "reason": "pulled"|"activity"}]}
    `excluded` is oldest first. Every comparison takes tokens[:complete].
    """
    tokens = list(tokens)
    vals = [None if v is None else float(v) for v in values]
    end = len(tokens)
    excluded = []
    # 1. the calendar: a month that had not ended when the data was pulled
    while end > 0 and month_ended(tokens[end - 1], as_of) is False:
        end -= 1
        excluded.append({"month": str(tokens[end]), "value": _num(vals[end]),
                         "baseline": None, "reason": "pulled",
                         "as_of": as_of.isoformat() if hasattr(as_of, "isoformat") else str(as_of)})
    # 2. the activity: a trailing month below half its own six-month baseline
    walked = 0
    while end > 0 and walked < MAX_TRAILING:
        i = end - 1
        if vals[i] is None:
            break
        base = [v for v in vals[max(0, i - BASELINE_MONTHS):i] if v is not None]
        if len(base) < MIN_BASELINE:
            break
        med = statistics.median(base)
        if med <= 0 or med < min_volume or vals[i] >= PARTIAL_SHARE * med:
            break
        excluded.append({"month": str(tokens[i]), "value": _num(vals[i]),
                         "baseline": _num(med), "reason": "activity"})
        end -= 1
        walked += 1
    excluded.reverse()
    return {"measure": measure, "last_complete": str(tokens[end - 1]) if end else None,
            "complete": end, "excluded": excluded}


def combine(*results):
    """The months complete in EVERY given measure — for a computation that reads several.

    Returns the same shape as assess(): the shortest `complete`, and every exclusion.
    """
    results = [r for r in results if r]
    if not results:
        return {"measure": "", "last_complete": None, "complete": 0, "excluded": []}
    short = min(results, key=lambda r: r["complete"])
    seen, excl = set(), []
    for r in results:
        for e in r["excluded"]:
            e = dict(e, measure=e.get("measure") or r["measure"])
            k = (e["month"], e["measure"])
            if k not in seen:
                seen.add(k)
                excl.append(e)
    return {"measure": " + ".join(r["measure"] for r in results if r["measure"]),
            "last_complete": short["last_complete"], "complete": short["complete"],
            "excluded": excl}


def _num(v):
    if v is None:
        return None
    return int(round(v)) if abs(v - round(v)) < 1e-9 or abs(v) >= 100 else round(v, 2)


def excluded_sentence(result, fmt=None):
    """One plain sentence per excluded month, naming the month and why, or "" when none was.

    "Aug 2026 is left out as incomplete in this extract: 390 NSF/OD items and 290 accounts
    with NSF/OD, against six-month medians of 18,695 and 4,238."
    """
    fmt = fmt or (lambda v: f"{v:,}")
    by_month = {}
    for e in (result or {}).get("excluded", []):
        by_month.setdefault(e["month"], []).append(e)
    parts = []
    for month in sorted(by_month, key=lambda t: month_start(t) or datetime.date.min):
        es = by_month[month]
        mon = label(month)
        pulled = [e for e in es if e["reason"] == "pulled"]
        if pulled:
            parts.append(f"{mon} is left out: the data was pulled {pulled[0].get('as_of')}, "
                         f"before the month ended.")
            continue
        what = " and ".join(f"{fmt(e['value'])} {e.get('measure') or 'activity'}" for e in es)
        base = " and ".join(fmt(e["baseline"]) for e in es)
        parts.append(f"{mon} is left out as incomplete in this extract: {what}, against "
                     f"{'a six-month median' if len(es) == 1 else 'six-month medians'} of {base}.")
    return " ".join(parts)


def odd_completeness(rows, odd, months, as_of=None):
    """Completeness of an ODD extract's trailing months, per measure family.

    `rows`   the extract's rows; `odd` an odd_rows.accessors namespace
    `months` the extract's month tokens, oldest first ('Aug26')
    `as_of`  the pull date (pull_date() of the member file name), when known

    Only the months the rule can reach are summed — the last BASELINE_MONTHS +
    MAX_TRAILING — in one pass. Returns
        {"pull_date", "activity": swipes+spend, "nsf": NSF/OD items+accounts,
         "all": every measure}
    each in assess()'s shape, with `complete` counted over the FULL `months` list,
    so `months[:r["complete"]]` is the usable series.

    metrics_gen (every ODD slide) and ticket_calc (Average Ticket) both call this, so
    the swipe-tier window and the ticket window can never disagree about which months
    are complete.
    """
    months = list(months)
    tail = months[-(BASELINE_MONTHS + MAX_TRAILING):]
    off = len(months) - len(tail)
    sw = [0.0] * len(tail); sp = [0.0] * len(tail)
    ni = [0.0] * len(tail); na = [0] * len(tail)
    swipes, spend, nsf = odd.swipes, odd.spend, odd.nsf
    for r in rows:
        for j, m in enumerate(tail):
            sw[j] += swipes(r, m)
            sp[j] += spend(r, m)
            v = nsf(r, m)
            if v:
                ni[j] += v
                if v > 0:
                    na[j] += 1

    def full(res):
        res = dict(res)
        res["complete"] = off + res["complete"]
        res["last_complete"] = months[res["complete"] - 1] if res["complete"] else None
        return res

    activity = combine(assess(tail, sw, as_of, "debit swipes"),
                       assess(tail, sp, as_of, "debit spend"))
    nsf_res = combine(assess(tail, ni, as_of, "NSF/OD items"),
                      assess(tail, na, as_of, "accounts with NSF/OD"))
    activity["measure"], nsf_res["measure"] = "debit activity", "NSF/OD activity"
    both = combine(activity, nsf_res)
    return {"pull_date": as_of.isoformat() if as_of else None,
            "activity": full(activity), "nsf": full(nsf_res), "all": full(both)}


def complete_rows(rows, value_index=1, measure="", as_of=None, month_index=0, min_volume=MIN_VOLUME):
    """(complete rows, assess() result) for a monthly series of rows, oldest first.

    For a series that is already aggregated — the ARS workbook's Key Trends
    (`swipespend_36`: [month, spend $M, cards]) — rather than an ODD. A row whose value
    is None is not a month the rule can judge and is left where it is.
    """
    rows = list(rows or [])
    res = assess([r[month_index] for r in rows], [r[value_index] for r in rows], as_of, measure, min_volume)
    return rows[:res["complete"]], res


def excluded_months(result):
    """['Aug 2026', ...] — the excluded months as the decks print them."""
    out = []
    for e in (result or {}).get("excluded", []):
        if label(e["month"]) not in out:
            out.append(label(e["month"]))
    return out


def drop_empty_partial_month(block, values_key, partial_key="partial_last"):
    """Remove the latest month from a monthly series when it is a partial month with nothing in it.

    A chart of a month that has only just begun (the pull is dated the 1st) draws a bar of 0 beside
    a full-height bar for every month before it, which reads as a collapse (Aaron, 2026-10-06:
    "if the latest incomplete month is 0 referrals, don't show that bar"; MRPC enrollments the
    same). Every list in `block` as long as the month list is trimmed together and `partial_key` is
    cleared, so the "last complete month" colouring, the title's month count and the caption all
    follow. A partial month with ANY activity stays, hatched, as before; so does a complete month at
    0, which is a real result. -> the dropped month's token, or None when nothing was dropped.
    """
    if not block or not block.get(partial_key):
        return None
    values = block.get(values_key) or []
    months = block.get("months") or []
    if not values or not months or len(values) != len(months) or len(months) < 2:
        return None
    if values[-1] not in (0, 0.0):
        return None
    n = len(months)
    dropped = months[-1]
    for k, v in list(block.items()):
        if isinstance(v, list) and len(v) == n:
            block[k] = v[:-1]
    block[partial_key] = False
    return dropped
