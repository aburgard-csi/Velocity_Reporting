#!/usr/bin/env python3
"""
revenue_guarantee_slide.py — the ARS "Revenue Guarantee" slide, inserted directly
after "Financial Performance" for a client who is NOT comfortably clear of the guarantee.

ARS carries a 2 : 1 revenue guarantee: the program returns at least twice what it costs.
That commitment used to appear only as an adjective inside one bullet on Financial
Performance — "Profitability of 5.7 : 1 is well above the 2 : 1 threshold" — so the
guaranteed minimum itself was never a figure on any slide, and a reader could not see how
much room a client has above it, or how far a young program is below it.

Who gets the slide (Aaron, 2026-09-22)
--------------------------------------
Only clients **under 3 : 1**. A client at 5.7 : 1 does not need a slide to be told the
guarantee holds — the Financial Performance bullet already says so, and a whole slide about
a floor they cleared years ago invites a question nobody was asking. Below 3 : 1 the
guarantee is a live conversation: either the program is young and closing on it, or it is
not, and both are worth showing. `should_build()` is the one place that rule lives.

Where the figures come from (Aaron, 2026-09-22)
-----------------------------------------------
The **Actuals tab**, month by month, read by `actuals_tab` and carried in `base.json` by
both extractors — not the Executive Financials roll-up this slide first used. A guarantee is
a statement about revenue against cost over the life of the program, and only the months
show whether a client is closing on it or drifting away from it. The month the program met its
guarantee is where cumulative revenue first covers twice cumulative cost. Falls back to the roll-up totals when a workbook carries no Actuals tab,
and the notes say which was used.

The slide is a P&L (Aaron, 2026-10-02)
-------------------------------------
"Redo this slide as a typical P&L, but keep the callout for profitability." The left of the
slide is the program's P&L from the same Actuals tab: incremental revenue, each cost line the
sheet carries (labels taken from the sheet - MM and SM shapes differ), total costs and
incremental profit, for the last complete month and the program to date. A cost line that is
zero for the whole program is left off and named in the notes. The right is the callout: the
profitability ratio, and the gap to (or room above) the 2 : 1 guaranteed minimum. The
cumulative-lines chart this replaced is gone. Without an Actuals tab the P&L falls back to the
Executive Financials program-to-date totals: revenue, total costs and profit only.

Below the guarantee
-------------------
The slide names the gap and how long it would take to close at the program's own recent run
rate. Closing a gap is not "gap / monthly revenue": cost keeps accruing too, so each month
adds revenue `r` and raises the minimum by `2c`. The gap closes at

    months = ceil( (2*cost - revenue) / (r - 2*c) )

and only when `r > 2*c`. When it is not, the honest answer is that the gap does not close at
the current run rate, and the slide says exactly that rather than printing a number that
assumes costs stop. `r` and `c` are the mean of the last 12 COMPLETE months of the Actuals
series (CLAUDE.md: comparisons use complete months only); a month left out is stated on the
slide face, not only in the notes.

A client with no cost booked yet cannot be measured against a multiple of it. That is stated
in a sentence (CLAUDE.md: missing source data is stated, never zeroed) — no 0 : 1 is drawn.

Public entry points
-------------------
    should_build(B)                      -> bool
    add_revenue_guarantee_slide(prs, B, assets_dir, month_label, ...)
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pptx.util import Inches
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

from brand import usd_compact
import month_complete as _MC

from product_mix_slide import (
    _tb, _pill, _tile, _blank_slide, _slide_title, _sldid_of, _renumber,
    NAVY, ORANGE, GREYT, HEAD, BODY,
)

try:
    from textfit import text_width_in
except Exception:                                   # pragma: no cover
    text_width_in = None

# The multiple the program is sold on. One place, so a slide, a sentence and a test cannot
# drift apart if it is ever renegotiated.
MULTIPLE = 2.0
# Above this, the guarantee is not a live question and the slide is not built.
SHOW_BELOW = 3.0
RUN_MONTHS = 12
_RUNRATE_MEASURE = "monthly incremental revenue"
# Callout geometry, and the label width a wording has to fit. PowerPoint applies 0.1in of
# margin each side that python-pptx reports as None, and restyle_fonts floors label runs at
# 16pt - so a wording is measured at what is DRAWN, not at what it is authored as. Three
# labels escaped their tiles onto the slide behind them before this was measured at all.
TILE_W, LABEL_PT = 4.05, 16
LABEL_USABLE = TILE_W - 0.1 - 0.2
# The vertical stack (Aaron, 2026-10-02): the subtitle and caption are measured at the size
# they are DRAWN (16pt, restyle_fonts' floor) and each element is placed under the one above
# it, because a subtitle that wrapped at a fixed top ran into the row below it.
TEXT_PT, TEXT_W, LINE_IN = 16, 12.3, 0.29
SUB_T, GAP_SUB, GAP_CAPTION = 1.08, 0.24, 0.30
CONTENT_BOTTOM, MAX_DROP = 6.62, 0.45
# Side by side and centred since the P&L left this slide (Aaron, 2026-10-02): two tiles of
# TILE_W with CALLOUT_GAP between them, centred on the 13.333in slide.
CALLOUT_GAP, CALLOUT_H = 0.40, 1.55
CALLOUT_L = (13.333 - (2 * TILE_W + CALLOUT_GAP)) / 2
# Carlito measures ~3% narrower than PowerPoint draws Calibri: a subtitle measured at
# 11.88in of a 12.1in line still wrapped. Wrap against a line this much shorter.
WRAP_SLACK = 0.45


def _fits(text):
    if text_width_in is None:
        return True
    return text_width_in(text, LABEL_PT, "Calibri", False) <= LABEL_USABLE


def _lines(text, width=TEXT_W - 0.2 - WRAP_SLACK, pt=TEXT_PT):
    """How many lines `text` wraps to in a box `width` wide, word by word, at `pt`."""
    if text_width_in is None:
        return max(1, math.ceil(len(text) * pt / 72.0 * 0.5 / width))
    n, cur = 1, ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and text_width_in(trial, pt, "Calibri", False) > width:
            n, cur = n + 1, word
        else:
            cur = trial
    return n


def _text_h(text):
    """Height of a wrapped 16pt text box: its lines plus PowerPoint's 0.05in margins."""
    return _lines(text) * LINE_IN + 0.1


def _n(count, singular, plural=None):
    """"1 month", "13 months" — a client with one mailing or one month is a real client."""
    return f"{count:,} {singular if count == 1 else (plural or singular + 's')}"


def _label(*candidates):
    """The first wording that fits one line inside a tile; the shortest otherwise."""
    for c in candidates:
        if _fits(c):
            return c
    return min(candidates, key=len)


def should_build(B, threshold=SHOW_BELOW):
    """True when this client's profitability is below `threshold` (Aaron, 2026-09-22).

    Read from `ratio_of`, the one ratio every slide states, so the slide appears exactly
    when the divider and the overview bullet say something below 3 : 1 — a client cannot
    see "5.7 : 1" on one slide and a guarantee slide on the next.
    """
    r = ratio_of(B)
    return r is not None and r < threshold


def ratio_of(B):
    """THE program-to-date revenue-to-cost ratio, or None when there is no cost to divide by.

    The Actuals series first — the P&L's own rows are its sums, and the Profitability cell
    under them must be those two cells divided — then the Executive Financials roll-up that
    `guarantee` falls back to, then a bare `profitability` from base.json. It used to prefer
    base.json's `profitability` (the roll-up) while the P&L divided the Actuals sums, so a
    workbook whose two tabs differ by a hair printed 3.5 : 1 on the divider over a P&L that
    read 3.4 : 1 (the golden deck, caught by `validate_deck.ptd_ratio_findings`, 2026-10-12).
    """
    g = guarantee(B)
    if g["ratio"] is not None:
        return g["ratio"]
    p = B.get("profitability")
    return float(p) if isinstance(p, (int, float)) and p else None


def _series(B):
    """(months, source) — the Actuals months, else nothing."""
    a = B.get("actuals") or {}
    if a.get("available") and a.get("months"):
        return a["months"], a
    return [], {}


def guarantee(B):
    """The guarantee as numbers — pure, so the arithmetic is testable without pptx."""
    months, act = _series(B)
    if months:
        revenue = round(sum(m[1] for m in months), 2)
        cost = round(sum(m[2] for m in months), 2)
        source = "actuals"
    else:
        cost = abs(B.get("ltd_costs") or 0)
        revenue = B.get("ltd_revenue") or 0
        source = "rollup"
    out = {
        "source": source,
        "sheet": act.get("sheet"),
        "months": months,
        "cost": cost,
        "revenue": revenue,
        "minimum": MULTIPLE * cost,
        "measurable": bool(cost),
        "ratio": None, "met": None, "surplus": None, "gap": None,
        "months_to_cover": None, "run_rate": None, "monthly_cost": None,
        "monthly_cost_from": None, "run_months": 0, "left_out": [],
        "met_month": None, "total_column": act.get("total_column"),
        "lines": act.get("lines") or [],
        "window": act.get("window"),
    }
    if not cost:
        return out

    out["ratio"] = revenue / cost
    out["met"] = revenue >= out["minimum"]

    # The month the program first covered twice its cost, from the cumulative lines. A
    # program can meet the guarantee, slip back under it and meet it again; this is the
    # LATEST crossing, because the earlier ones are history the client has already banked.
    if months:
        cr = cc = 0.0
        crossed = None
        for label, rev, cst in months:
            cr += rev
            cc += cst
            if cr >= MULTIPLE * cc and cc:
                crossed = crossed or label
            else:
                crossed = None
        out["met_month"] = crossed

    if out["met"]:
        out["surplus"] = revenue - out["minimum"]
        return out

    out["gap"] = out["minimum"] - revenue

    # Run rates over COMPLETE months only, from the Actuals series where there is one.
    if months:
        rows, res = _MC.complete_rows(months, 1, _RUNRATE_MEASURE, min_volume=0)
        out["left_out"] = _MC.excluded_months(res)
        tail = rows[-RUN_MONTHS:]
        if tail:
            out["run_months"] = len(tail)
            out["run_rate"] = sum(m[1] for m in tail) / len(tail)
            out["monthly_cost"] = sum(m[2] for m in tail) / len(tail)
            out["monthly_cost_from"] = f"the last {len(tail)} complete months of Actuals"
    else:
        rows, res = _MC.complete_rows(B.get("monthly_rev_last12") or [], 1,
                                      _RUNRATE_MEASURE, min_volume=0)
        out["left_out"] = _MC.excluded_months(res)
        vals = [v for _m, v in rows if v is not None]
        if vals:
            out["run_months"] = len(vals)
            out["run_rate"] = sum(vals) / len(vals)
        n_months = B.get("months") or 0
        if B.get("cur_costs"):
            out["monthly_cost"] = abs(B["cur_costs"])
            out["monthly_cost_from"] = "this month's program cost"
        elif n_months:
            out["monthly_cost"] = cost / n_months
            out["monthly_cost_from"] = "the program-to-date average monthly cost"

    if out["run_rate"] is None or out["monthly_cost"] is None:
        return out
    denom = out["run_rate"] - MULTIPLE * out["monthly_cost"]
    if denom > 0:
        out["months_to_cover"] = int(math.ceil(out["gap"] / denom))
    return out


def pnl(g):
    """The P&L the slide tabulates - pure, so it is testable without pptx.

    {"columns": [...], "rows": [(label, [values], kind)], "dropped": [labels]}. Costs are
    POSITIVE here and shown in parentheses on the slide; `kind` is "revenue", "line",
    "total" or "profit". The month column is the last COMPLETE month of the Actuals series
    (CLAUDE.md: complete months only); a month left out is named by `_caption`.

    Three columns where there is an Actuals series: that month, the YEAR to date, and the
    program to date (Aaron, 2026-10-02). Year to date is the complete months of the last
    complete month's own calendar year, up to and including it — on a 97-month program the
    month beside the lifetime total says nothing about how this year is running.
    """
    months = g["months"]
    if not months:
        return {"columns": ["Program to date"], "dropped": [],
                "rows": [("Incremental revenue", [g["revenue"]], "revenue"),
                         ("Total costs", [g["cost"]], "total"),
                         ("Incremental profit", [g["revenue"] - g["cost"]], "profit"),
                         ("Profitability",
                          [g["revenue"] / g["cost"] if g["cost"] else None], "ratio")]}

    rows, _res = _MC.complete_rows(months, 1, _RUNRATE_MEASURE, min_volume=0)
    last = rows[-1][0] if rows else None
    i = next((k for k, m in enumerate(months) if m[0] == last), None)

    # The complete months of that month's own year, up to it. A label is "Aug 2026", so the
    # year is its last word; a month the Actuals tab does not carry simply is not summed.
    ytd = []
    if i is not None:
        year = str(months[i][0]).split()[-1]
        ytd = [k for k in range(i + 1) if str(months[k][0]).split()[-1] == year]

    def cols(pick, ptd_val):
        """pick(k) -> the value at month k. Month, year to date, program to date."""
        if i is None:
            return [ptd_val]
        return [pick(i), round(sum(pick(k) for k in ytd), 2), ptd_val]

    out = [("Incremental revenue", cols(lambda k: months[k][1], g["revenue"]), "revenue")]
    dropped, kept = [], []
    for label, vals in g.get("lines") or []:
        if not any(vals):
            dropped.append(label)
            continue
        kept.append((label, vals))
    # ONE cost line is its own total (Aaron, 2026-10-02): "if we have just one fee line, we
    # don't need that and a total line". Marine carries only a Respondent Fee, so the itemised
    # row and Total costs were the same three figures twice. The surviving row keeps the fee's
    # NAME — which "Total costs" does not say — and is styled as the total.
    if len(kept) == 1:
        label, vals = kept[0]
        out.append((label, cols(lambda k, v=vals: v[k], round(sum(vals), 2)), "total"))
    else:
        for label, vals in kept:
            out.append((label, cols(lambda k, v=vals: v[k], round(sum(vals), 2)), "line"))
        out.append(("Total costs", cols(lambda k: months[k][2], g["cost"]), "total"))
    out.append(("Incremental profit",
                cols(lambda k: months[k][1] - months[k][2],
                     round(g["revenue"] - g["cost"], 2)), "profit"))
    # Revenue over cost, COLUMN BY COLUMN (Aaron, 2026-10-02). The program ratio is the only
    # one the deck states anywhere; the year's is a different number and often a more useful
    # one. A column with no cost has no ratio — a dash, never infinity and never zero, which
    # would read as a program returning nothing.
    rev_row = out[0][1]
    cost_row = next(v for l, v, k in out if k == "total")
    out.append(("Profitability",
                [(r / c if c else None) for r, c in zip(rev_row, cost_row)], "ratio"))
    return {"columns": ([last, "Year to date"] if i is not None else []) + ["Program to date"],
            "rows": out, "dropped": dropped}


def ratio_text(v):
    """THE way a profitability ratio is printed, everywhere in the deck: "5.4 : 1", from the
    UNROUNDED quotient. The ARS divider used to format base.json's two-decimal value and
    printed 2.1 : 1 under a P&L that printed 2.2 : 1 from the same figures (True Sky,
    2026-10-12); one formatter on one unrounded number is how the slides agree."""
    if v is None:
        return "\u2014"
    return f"{v:.1f} : 1"


def money(v, kind):
    """$1,484,350 for revenue and profit, a loss in parentheses; a cost in parentheses, and
    a negative cost (a discount) as a plain credit. A ratio reads "5.4 : 1"."""
    if v is None:
        return "\u2014"
    if kind == "ratio":
        return ratio_text(v)
    txt = f"${abs(v):,.0f}"
    if kind in ("line", "total"):
        return txt if v < 0 else f"({txt})"
    return f"({txt})" if v < 0 else txt


def _caption(g):
    """The sentence under the P&L — derived from the figures beside it, never fixed."""
    if not g["measurable"]:
        return ("The workbook carries no program cost to date, so revenue cannot be "
                "measured against a multiple of it. The guarantee is reported once costs "
                "are booked.")
    ratio = f"{g['ratio']:.1f} : 1"
    if g["met"]:
        line = (f"Revenue to date is {ratio} against program cost — "
                f"{usd_compact(g['surplus'])} above the guaranteed minimum of "
                f"{usd_compact(g['minimum'])}.")
        if g.get("met_month"):
            line += f" The program has covered twice its cost since {g['met_month']}."
        return line

    line = (f"Revenue to date is {ratio} against program cost, {usd_compact(g['gap'])} short "
            f"of the guaranteed minimum of {usd_compact(g['minimum'])}. ")
    if g["months_to_cover"] is not None:
        line += (f"At the last {_n(g['run_months'], 'complete month')} — ${g['run_rate']:,.0f} "
                 f"of revenue a month against ${g['monthly_cost']:,.0f} of cost — the gap "
                 f"closes in about {_n(g['months_to_cover'], 'month')}.")
    elif g["run_rate"] is not None and g["monthly_cost"] is not None:
        line += (f"At the last {_n(g['run_months'], 'complete month')} of revenue, "
                 f"${g['run_rate']:,.0f} a month, the gap does not close: cost raises the "
                 f"minimum by ${MULTIPLE * g['monthly_cost']:,.0f} over the same month.")
    else:
        line += "The workbook carries no complete month of revenue to read a run rate from."
    if g["left_out"]:
        line += " " + ", ".join(g["left_out"]) + " left out: incomplete in this extract."
    return line


def add_revenue_guarantee_slide(prs, B, assets_dir, month_label,
                                after_title="Financial Performance", renumber=True,
                                wb_src="ARS workbook", tab=""):
    """Build the Revenue Guarantee slide. Returns (slide, guarantee dict)."""
    g = guarantee(B)

    anchor = _anchor(prs, after_title)
    s = _blank_slide(prs, anchor)

    _tb(s, 0.5, 0.28, 9.6, 0.9, "Revenue Guarantee", 26, NAVY, True,
        PP_ALIGN.LEFT, HEAD, MSO_ANCHOR.MIDDLE)
    _pill(s, f"{month_label} Data")
    subtitle = ("Account Revenue Solution® returns at least twice its program cost. "
                "Where this program stands against that minimum.")
    sub_h = _text_h(subtitle)
    _tb(s, 0.5, SUB_T, TEXT_W, sub_h, subtitle, TEXT_PT, GREYT, False,
        PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
    top = SUB_T + sub_h + GAP_SUB

    # The callouts are the slide now, so the block is their height plus whatever sits
    # under them; centred in the space above the logo, never pushed off the subtitle by
    # more than MAX_DROP.
    caption = _caption(g)
    block = (CALLOUT_H + (0.4 if g["measurable"] else 0.0)
             + GAP_CAPTION + _text_h(caption))
    top += min(MAX_DROP, max(0.0, (CONTENT_BOTTOM - top - block) / 2))

    # The profitability callout, and where that leaves the guarantee.
    prof = _label("Profitability, to date", "Profitability")
    if not g["measurable"]:
        callouts = [("\u2014", prof, ORANGE),
                    ("\u2014", _label("Not measurable yet"), NAVY)]
    elif g["met"]:
        callouts = [(f"{g['ratio']:.1f} : 1", prof, ORANGE),
                    (usd_compact(g["surplus"]),
                     _label("Above the 2 : 1 guarantee", "Above the guarantee"), NAVY)]
    else:
        callouts = [(f"{g['ratio']:.1f} : 1", prof, ORANGE),
                    (usd_compact(g["gap"]),
                     _label("Short of the 2 : 1 guarantee", "Short of the guarantee"), NAVY)]
    for k, (v, lab, fill) in enumerate(callouts):
        _tile(s, CALLOUT_L + k * (TILE_W + CALLOUT_GAP), top, TILE_W, CALLOUT_H,
              v, lab, fill=fill)
    t = top + CALLOUT_H
    if g["measurable"]:
        _tb(s, CALLOUT_L, t + 0.08, 2 * TILE_W + CALLOUT_GAP, 0.4,
            f"Guaranteed minimum: {usd_compact(g['minimum'])}",
            TEXT_PT, GREYT, False, PP_ALIGN.CENTER, BODY, MSO_ANCHOR.TOP)
        t += 0.4

    cap_t = t + GAP_CAPTION
    _tb(s, 0.5, cap_t, TEXT_W, _text_h(caption), caption, TEXT_PT, NAVY, False,
        PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)

    s.notes_slide.notes_text_frame.text = _notes_text(g, B, wb_src, tab, month_label)

    logo = os.path.join(assets_dir, "logo.png")
    if os.path.exists(logo):
        s.shapes.add_picture(logo, Inches(11.28), Inches(6.78), Inches(1.70), Inches(0.54))

    # Added at the end, then moved: a slide is only ever ADDED and reordered, never deleted,
    # or python-pptx hands its freed partname to a later slide (CLAUDE.md).
    sid, tid = _sldid_of(prs, s), _sldid_of(prs, anchor)
    if sid is None or tid is None:
        raise SystemExit("Revenue Guarantee: could not place the slide after its anchor")
    prs.slides._sldIdLst.remove(sid); tid.addnext(sid)
    if renumber:
        _renumber(prs)
    return s, g


def _anchor(prs, after_title):
    """The slide this one follows, matched on its title CONTAINING after_title.

    Contains, not startswith: the shell titles the slide "ARS Financial Performance", and a
    startswith match on "Financial Performance" found nothing and quietly fell back to a
    different position — the silent no-op CLAUDE.md's swap gate exists to stop.
    """
    want = after_title.lower()
    for s in prs.slides:
        if want in _slide_title(s).lower():
            return s
    raise SystemExit("Revenue Guarantee: no slide titled like %r to follow. Titles: %s"
                     % (after_title, [_slide_title(s) for s in prs.slides][:12]))


def _notes_text(g, B, wb_src, tab, month_label):
    src = (f"{wb_src} — '{g['sheet']}' tab: Total Marginal Revenues, each cost line and Total Cost, by month"
           if g["source"] == "actuals" else
           f"{wb_src} — Executive Financials{tab}, program-to-date column (this workbook "
           f"carries no Actuals tab)")
    note = (f"Source: {src}. Selection: the program to date through {month_label}"
            + (f" ({g['window'][0]} to {g['window'][1]})." if g.get("window") else ".")
            + f" Guarantee = {MULTIPLE:.0f} x program cost ({usd_compact(g['cost'])} \u2192 "
              f"{usd_compact(g['minimum'])}); revenue {usd_compact(g['revenue'])}.")
    if g["measurable"]:
        note += f" Ratio {g['ratio']:.2f} : 1"
        wb_prof = B.get("profitability")
        if wb_prof is not None and abs(round(g["ratio"], 2) - wb_prof) >= 0.01:
            note += f" (Executive Financials reads {wb_prof:.2f} : 1)"
        note += "."
    if g.get("total_column") is not None and abs(g["total_column"] - g["revenue"]) >= 1:
        note += (f" The tab's own total column reads {usd_compact(g['total_column'])} against "
                 f"{usd_compact(g['revenue'])} summed from its months — worth reconciling.")
    if g["gap"] is not None:
        note += (f" Gap {usd_compact(g['gap'])}. Run rate: the last {g['run_months']} complete "
                 f"months")
        note += (f" = ${g['run_rate']:,.0f} revenue and ${g['monthly_cost']:,.0f} cost a month"
                 if g["run_rate"] is not None and g["monthly_cost"] is not None
                 else " — not available")
        note += (f". Months to cover = ceil(gap / (run rate \u2212 {MULTIPLE:.0f} x monthly "
                 f"cost)), which accrues cost over the same months: "
                 f"{g['months_to_cover'] if g['months_to_cover'] is not None else 'does not close at this run rate'}.")
        if g["left_out"]:
            note += " Left out as incomplete: " + ", ".join(g["left_out"]) + "."
    # The P&L itself is the ARS Profit & Loss slide, from these same figures
    # (Aaron, 2026-10-02) — this slide no longer tabulates it, so the notes point there
    # rather than describing a table that is not on the slide.
    note += (" The itemised P&L behind these figures is the ARS Profit & Loss slide, built "
             "from the same Actuals months.")
    note += ("\n\nREVIEW — WHAT THIS ASSUMES:"
             "\n  !! The slide is built only for clients under "
             f"{SHOW_BELOW:.0f} : 1 (Aaron, 2026-09-22). A client comfortably clear of the "
             "guarantee does not get it at all, so its absence is not a data problem."
             "\n  !! Months to cover is an ESTIMATE at the current run rate, not a forecast: "
             "it holds revenue and cost flat at their recent levels for every month of the "
             "count."
             "\n  !! Cost is the workbook's Total Cost, which is what the client is billed. "
             "It is not CSI's cost of running the program."
             "\n  !! The crossing month is the LATEST one: a program that met the guarantee, "
             "slipped under it and met it again reads from the most recent crossing.")
    return note
