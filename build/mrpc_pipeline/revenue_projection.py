#!/usr/bin/env python3
"""revenue_projection.py — the projected full year on MRPC Revenue by Year.

Aaron, 2026-10-02: "Add a revenue projection here based on the trajectory from the
past 6 months."

METHOD (one, so the slide, the chart and the notes cannot disagree):

1. Input is `revenue.by_month` AFTER `build_mrpc_gen.complete_series` has trimmed it
   to complete months (CLAUDE.md, "Comparisons use complete months only"). Nothing
   here re-judges completeness.
2. The window is the LAST `WINDOW` (6) complete months. Fewer than 6 and there is no
   projection: the result says so and the slide states it.
3. Trajectory = an ordinary least-squares straight line through those 6 monthly
   revenue figures (x = 0..5). The slope is dollars per month.
4. Each remaining month of the calendar year — from the month after the last complete
   month through December — is the line extended to that month. A month the line
   would put below $0 is floored at $0, and the floor is reported (`floored`).
5. Projected full year = the VIP year-to-date actual (`revenue.annual`'s "<year> YTD"
   bar) + the sum of the projected months. The YTD bar must run through the same
   month the monthly series ends on, in the same year; otherwise the two do not join
   and there is no projection.
6. The comparison to the prior full year follows the +/-2% band (CLAUDE.md,
   "Describing movement"): within 2% -> "almost flat", above -> "up N%", below ->
   "N% below", each with both figures. The verb is derived, never written.

It is a projection, not a result: it assumes the 6-month line holds for the rest of
the year. Every string this module writes says "projected".

IMPORT-SAFE: no file, sys.argv or month constant is read here.
"""
from __future__ import annotations

import datetime

WINDOW = 6          # complete months the line is fitted through
BAND_PCT = 2.0      # +/- band inside which a change reads "almost flat"

_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_FULL = ["January", "February", "March", "April", "May", "June", "July", "August",
         "September", "October", "November", "December"]


def _month_start(token):
    import re
    t = " ".join(str(token or "").split())
    m = re.match(r"^([A-Za-z]{3})[A-Za-z]*\.?\s*'?(\d{2}|\d{4})$", t)
    if not m or m.group(1).title() not in _MON:
        return None
    y = int(m.group(2))
    return datetime.date(y if y > 99 else 2000 + y, _MON.index(m.group(1).title()) + 1, 1)


def _month_index(name):
    n = str(name or "").strip()[:3].title()
    return _MON.index(n) + 1 if n in _MON else None


def money(v):
    """$90.2K at a thousand and up, $950 below — the Revenue slides' own format."""
    return f"${v / 1000:,.1f}K" if abs(v) >= 1000 else f"${v:,.0f}"


def _ols(ys):
    n = len(ys)
    xs = list(range(n))
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return slope, my - slope * mx


def band_phrase(projected, prior, prior_label):
    """'up 10.6% on 2025's $81.6K' / 'almost flat with 2025's $81.6K' / '3.1% below ...'."""
    if not prior:
        return None, None
    pct = (projected - prior) / prior * 100
    if abs(pct) <= BAND_PCT:
        return pct, f"almost flat with {prior_label}'s {money(prior)} ({pct:+.1f}%)"
    if pct > 0:
        return pct, f"up {pct:.1f}% on {prior_label}'s {money(prior)}"
    return pct, f"{abs(pct):.1f}% below {prior_label}'s {money(prior)}"


def project_year(months, values, ytd_amount, ytd_through, year, prior_amount=None,
                 prior_label=None, window=WINDOW):
    """Project the calendar year from the trend of the last `window` complete months.

    months / values  the complete monthly series ("Dec 25", ...), oldest first
    ytd_amount       the year-to-date actual for `year`
    ytd_through      the month the YTD runs through ("May")
    year             the calendar year projected (int)
    prior_amount     the prior full year, for the band comparison (optional)

    Returns a dict. `ok` False carries `reason`; `ok` True carries the window, the
    line, each projected month, the remainder, the full year and the comparison.
    """
    months, values = list(months or []), [float(v) for v in (values or [])]
    out = {"ok": False, "window": window, "year": year, "ytd_amount": ytd_amount,
           "ytd_through": ytd_through}
    if len(values) < window or len(months) != len(values):
        out["reason"] = (f"a {year} projection needs {window} complete months of revenue; "
                         f"{len(values)} are on hand")
        return out
    win_m, win_v = months[-window:], values[-window:]
    last = _month_start(win_m[-1])
    thr = _month_index(ytd_through)
    if last is None or thr is None:
        out["reason"] = f"the monthly series end ({win_m[-1]}) or YTD month ({ytd_through}) is unreadable"
        return out
    if last.year != year or last.month != thr:
        out["reason"] = (f"the {year} YTD runs through {ytd_through} but the complete monthly "
                         f"series ends {_MON[last.month - 1]} {last.year}; they do not join")
        return out
    slope, intercept = _ols(win_v)
    proj, floored = [], []
    for k, mo in enumerate(range(last.month + 1, 13), start=1):
        v = intercept + slope * (window - 1 + k)
        lab = f"{_MON[mo - 1]} {year}"
        if v < 0:
            floored.append(lab)
            v = 0.0
        proj.append((lab, v))
    remainder = sum(v for _, v in proj)
    full = ytd_amount + remainder
    out.update({
        "ok": True, "window_months": win_m, "window_values": win_v,
        "slope": slope, "intercept": intercept, "projected_months": proj,
        "floored": floored, "remainder": remainder, "full_year": full,
        "through_full": _FULL[thr - 1],
    })
    pct, phrase = band_phrase(full, prior_amount, prior_label or str(year - 1))
    out["vs_prior_pct"], out["vs_prior_phrase"] = pct, phrase
    return out


def _span(a, b):
    da, db = _month_start(a), _month_start(b)
    return f"{_MON[da.month - 1]} {da.year}–{_MON[db.month - 1]} {db.year}"


def caption(p):
    """The slide sentence. Every figure the claim rests on is in it."""
    if not p["ok"]:
        return f"No {p['year']} projection: {p['reason']}."
    rest = ""
    if p["projected_months"]:
        first, lastm = p["projected_months"][0][0], p["projected_months"][-1][0]
        rest = (f" plus {money(p['remainder'])} projected for "
                f"{first.split()[0]}–{lastm.split()[0]}" if first != lastm else
                f" plus {money(p['remainder'])} projected for {first.split()[0]}")
    s = (f"At the trend of the last {p['window']} complete months "
         f"({_span(p['window_months'][0], p['window_months'][-1])}), {p['year']} is projected at "
         f"{money(p['full_year'])}: {money(p['ytd_amount'])} actual through {p['through_full']}{rest}")
    if p.get("vs_prior_phrase"):
        s += f", {p['vs_prior_phrase']}"
    return s + "."


def notes(p, as_of=None):
    """The speaker-notes paragraph: method, window, figures, slope, assumption."""
    if not p["ok"]:
        return f"Projection: none. {p['reason'][0].upper()}{p['reason'][1:]}."
    win = "; ".join(f"{m} ${v:,.2f}" for m, v in zip(p["window_months"], p["window_values"]))
    pm = "; ".join(f"{m} ${v:,.2f}" for m, v in p["projected_months"])
    s = (f"Projection (method: build/mrpc_pipeline/revenue_projection.py): ordinary least-squares "
         f"straight line through the last {p['window']} complete months of VIP Revenue by Month "
         f"({win}); slope {'+' if p['slope'] >= 0 else '−'}${abs(p['slope']):,.2f} per month. "
         f"The line is extended to each remaining month of {p['year']} ({pm}) = "
         f"${p['remainder']:,.2f}, added to the {p['year']} YTD actual ${p['ytd_amount']:,.2f} "
         f"(through {p['through_full']}) for a projected {p['year']} of ${p['full_year']:,.2f}. ")
    if p.get("vs_prior_pct") is not None:
        s += f"Against the prior full year: {p['vs_prior_pct']:+.1f}% (+/-2% band wording). "
    if p["floored"]:
        s += f"Floored at $0 (the line went negative): {', '.join(p['floored'])}. "
    if as_of:
        s += (f"The monthly series ends {p['window_months'][-1]} while the data was pulled "
              f"{as_of}; months after it that have ended but are not yet reported are "
              f"projected, not actual. ")
    s += (f"This is a projection, not a result: it assumes the {p['window']}-month trend holds "
          f"for the rest of the year.")
    return s
