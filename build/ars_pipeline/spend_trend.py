#!/usr/bin/env python3
"""
spend_trend.py — debit spend per cardholder, per card in use and per ARS-eligible account,
month by month, with a like-for-like comparison of the months both years share.

Aaron, 2026-10-12, on Brooks Bank: the Spend YTD YoY tile read n/a because the workbook's spend
series starts in February 2025, so January 2025 is missing and the year-to-date windows cannot
be matched. "How are they trending on spend per cardholder? how are they trending on spend per
eligible account? Is there a good story we can tell there?" There is, and this module is the
one place its arithmetic lives:

  * `per_card(rows)` — the workbook's Key Trends: monthly spend ($M) over accounts with a card.
    The official figure; the one to quote.
  * `windows(labels)` — the like-for-like windows: the months of this year to date that the
    prior year ALSO carries. A series that starts in Feb 2025 compares Feb–Sep 2025 with
    Feb–Sep 2026; a full series compares Jan–Sep with Jan–Sep; a series with no prior-year
    month at all has no comparison (None, stated — never a partial window passed off as a
    year, and never a month-to-month substitute).
  * `from_odd(zip_path, through)` — the ODD extract's per-account monthly Sig $ + PIN $, for
    the shape of the growth: cards in use (personal accounts with a card that spent anything
    in the month), spend per card in use, and spend per ARS-eligible account (today's eligible
    personal book, open in the month). The ODD is today's book, so months before an account's
    opening or after its closing are not in it: its history understates earlier months, which
    is why the workbook's figure is the headline and these describe the shape.
  * `movement(prior, current)` — the sentence, under the +/-2% band (CLAUDE.md: within the band
    "almost flat"; positive, the figures and the %; negative, "did not have an impact").

Import-safe: nothing runs on import.
"""
import csv
import datetime as dt
import io
import re
import zipfile

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_LABEL_RX = re.compile(r"^([A-Z][a-z]{2})\s*'?(\d{2}|\d{4})$")
FLAT_BAND = 2.0             # +/-2%: "almost flat" (Aaron, 2026-08-31)


def month_key(label):
    """'Feb 2025' | 'Feb25' | "Feb'25" -> date(2025, 2, 1); None if it is not a month."""
    m = _LABEL_RX.match((label or "").strip())
    if not m or m.group(1) not in MONTH_ABBR:
        return None
    yy = int(m.group(2))
    return dt.date(yy if yy > 99 else 2000 + yy, MONTH_ABBR.index(m.group(1)) + 1, 1)


def month_label(d):
    return f"{MONTH_ABBR[d.month - 1]} {d.year}"


# ----------------------------------------------------------------- the workbook series
def per_card(rows):
    """[(label, spend_M, cards, dollars per card)] from Key Trends rows (label, $M spend, cards),
    skipping a month with no spend or no card count."""
    out = []
    for label, spend, cards in rows:
        if spend is None or not cards:
            continue
        out.append((label, float(spend), int(cards), float(spend) * 1e6 / int(cards)))
    return out


# ----------------------------------------------------------------- like-for-like windows
def windows(labels):
    """{prior: [labels], current: [labels], prior_name, current_name} or None.

    The current window runs from January of the latest month's year — or from the series'
    first month if the series begins inside the PRIOR year after January — through the latest
    month; the prior window is the same calendar months a year earlier. Both must be complete
    in `labels`, else None."""
    keys = [month_key(x) for x in labels]
    if not keys or any(k is None for k in keys):
        return None
    have = {k for k in keys}
    last, first = max(keys), min(keys)
    y, m = last.year, last.month
    if first.year > y - 1 or (first.year == y - 1 and first.month > m):
        return None                                   # no prior-year month to compare with
    start = first.month if first.year == y - 1 else 1
    cur = [dt.date(y, k, 1) for k in range(start, m + 1)]
    prior = [dt.date(y - 1, k, 1) for k in range(start, m + 1)]
    if any(d not in have for d in cur + prior):
        return None

    def name(ds):
        a, b = ds[0], ds[-1]
        span = MONTH_ABBR[b.month - 1] if a == b else f"{MONTH_ABBR[a.month - 1]}–{MONTH_ABBR[b.month - 1]}"
        return f"{span} {b.year % 100:02d}"
    return {"prior": [month_label(d) for d in prior], "current": [month_label(d) for d in cur],
            "prior_name": name(prior), "current_name": name(cur), "months": len(cur)}


def window_average(series, labels):
    """Mean of `series` ({label: value}) over `labels`; None if any is missing."""
    vals = [series.get(x) for x in labels]
    if not vals or any(v is None for v in vals):
        return None
    return sum(vals) / len(vals)


def compare(series, win):
    """{prior, current, pct} for a {label: value} series over the windows, or None."""
    if not win:
        return None
    a, b = window_average(series, win["prior"]), window_average(series, win["current"])
    if a is None or b is None or not a:
        return None
    return {"prior": a, "current": b, "pct": 100.0 * (b - a) / a}


# ----------------------------------------------------------------- wording
def movement(what, cmp, fmt="${:,.0f}", unit=" a month"):
    """One sentence that agrees with the figures beside it (CLAUDE.md, the +/-2% band)."""
    if not cmp:
        return f"{what}: no like-for-like comparison — the series does not reach a year back."
    a, b, p = fmt.format(cmp["prior"]), fmt.format(cmp["current"]), cmp["pct"]
    if abs(p) <= FLAT_BAND:
        return f"{what} was almost flat: {a} to {b}{unit} ({p:+.1f}%)."
    if p > 0:
        return f"{what} rose from {a} to {b}{unit} ({p:+.1f}%)."
    return f"The program did not have an impact on {what[0].lower() + what[1:]}: {a} to {b}{unit} ({p:+.1f}%)."


# ----------------------------------------------------------------- the ODD extract
def _yes(v):
    return (v or "").strip().lower() in ("yes", "y", "true", "1")


def _num(v):
    v = (v or "").replace("\x00", "").replace(",", "").replace("$", "").strip()
    try:
        return float(v) if v not in ("", "-") else 0.0
    except ValueError:
        return 0.0


def _date(v):
    v = (v or "").strip()
    for f in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return dt.datetime.strptime(v, f).date()
        except ValueError:
            pass
    return None


def _open_csv(zip_path):
    z = zipfile.ZipFile(zip_path)
    name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
    return name, csv.reader(io.TextIOWrapper(z.open(name), encoding="latin-1", newline=""))


def from_odd(zip_path, through=None):
    """Monthly cards in use, spend per card in use and spend per eligible account from the ODD.

    `through` (a month label) caps the months at the last COMPLETE one the caller decided on;
    the ODD's final month is often partial. Returns a dict of parallel lists plus snapshots."""
    member, rdr = _open_csv(zip_path)
    hdr = None
    for row in rdr:
        if any(c.strip() == "Debit?" for c in row):
            hdr = [h.strip() for h in row]
            break
    if hdr is None:
        raise SystemExit(f"spend trend: no header row with 'Debit?' in {member}")
    H = {h: i for i, h in enumerate(hdr)}
    months = sorted({h[:-6] for h in hdr if h.endswith(" Sig $") and month_key(h[:-6])}, key=month_key)
    cap = month_key(through) if through else None
    if cap:
        months = [m for m in months if month_key(m) <= cap]
    elig_col = next((h for h in hdr if h.endswith(" Elig")), None)
    need = ["Debit?", "Business?", "Date Opened", "Date Closed"]
    missing = [c for c in need if c not in H] + ([] if elig_col else ["<Mon> Elig"])
    if missing:
        raise SystemExit(f"spend trend: {member} lacks {', '.join(missing)}")
    sig = {m: H[f"{m} Sig $"] for m in months}
    pin = {m: H.get(f"{m} PIN $") for m in months}
    ends = {}
    for m in months:
        d = month_key(m)
        ends[m] = (d, (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1))
    card_spend = {m: 0.0 for m in months}; card_active = {m: 0 for m in months}
    elig_spend = {m: 0.0 for m in months}; elig_open = {m: 0 for m in months}; elig_active = {m: 0 for m in months}
    n_card = n_elig = 0
    for r in rdr:
        if len(r) < len(hdr):
            continue
        personal = not _yes(r[H["Business?"]])
        if not personal:
            continue
        hascard, iselig = _yes(r[H["Debit?"]]), _yes(r[H[elig_col]])
        if hascard:
            n_card += 1
        if iselig:
            n_elig += 1
        if not (hascard or iselig):
            continue
        opened, closed = _date(r[H["Date Opened"]]), _date(r[H["Date Closed"]])
        for m in months:
            s = _num(r[sig[m]]) + (_num(r[pin[m]]) if pin[m] is not None else 0.0)
            if hascard:
                card_spend[m] += s
                if s > 0:
                    card_active[m] += 1
            if iselig:
                start, end = ends[m]
                if (opened is None or opened <= end) and (closed is None or closed > start):
                    elig_open[m] += 1
                    elig_spend[m] += s
                    if s > 0:
                        elig_active[m] += 1
    labels = [month_label(month_key(m)) for m in months]
    return {
        "source_member": member,
        "months": labels,
        "cards_in_use": [card_active[m] for m in months],
        "spend_per_card_in_use": [card_spend[m] / card_active[m] if card_active[m] else None for m in months],
        "eligible_open": [elig_open[m] for m in months],
        "spend_per_eligible": [elig_spend[m] / elig_open[m] if elig_open[m] else None for m in months],
        "eligible_active_share": [100.0 * elig_active[m] / elig_open[m] if elig_open[m] else None for m in months],
        "cards_snapshot": n_card, "eligible_snapshot": n_elig, "eligible_column": elig_col,
    }


def compute(swipespend_rows, odd_zip=None, through=None):
    """Everything the slides need, from the workbook rows (and the ODD when given)."""
    pc = per_card(swipespend_rows)
    labels = [x[0] for x in pc]
    win = windows(labels)
    per_card_series = {x[0]: x[3] for x in pc}
    out = {"per_card": pc, "windows": win,
           "per_card_cmp": compare(per_card_series, win),
           "cards_cmp": compare({x[0]: x[2] for x in pc}, win),
           "spend_cmp": compare({x[0]: x[1] for x in pc}, win),
           "odd": None}
    if odd_zip:
        o = from_odd(odd_zip, through or (labels[-1] if labels else None))
        out["odd"] = o
        for key in ("cards_in_use", "spend_per_card_in_use", "spend_per_eligible"):
            out[key + "_cmp"] = compare(dict(zip(o["months"], o[key])), win)
    return out
