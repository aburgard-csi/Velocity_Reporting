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
show whether a client is closing on it or drifting away from it. The chart draws cumulative
revenue against twice cumulative cost; where those two lines cross is the month the program
met its guarantee. Falls back to the roll-up totals when a workbook carries no Actuals tab,
and the notes say which was used.

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

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pptx.util import Inches
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

from brand import usd_compact, GRID, TICK
from rpe_env import use_font
import month_complete as _MC

from product_mix_slide import (
    _tb, _pill, _tile, _fit_picture, _blank_slide, _slide_title,
    _sldid_of, _renumber,
    NAVY, ORANGE, GREYT, HEAD, BODY, _NAVY_HX, _ORANGE_HX, _TICK_HX,
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
# Tile geometry, and the label width a wording has to fit. PowerPoint applies 0.1in of
# margin each side that python-pptx reports as None, and restyle_fonts floors label runs at
# 16pt — so a wording is measured at what is DRAWN, not at what it is authored as. Three
# labels escaped their tiles onto the slide behind them before this was measured at all.
TILE_W, TILE_H, LABEL_PT = 2.85, 0.92, 16
LABEL_USABLE = TILE_W - 0.1 - 0.2


def _fits(text):
    if text_width_in is None:
        return True
    return text_width_in(text, LABEL_PT, "Calibri", False) <= LABEL_USABLE


def _label(*candidates):
    """The first wording that fits one line inside a tile; the shortest otherwise."""
    for c in candidates:
        if _fits(c):
            return c
    return min(candidates, key=len)


def should_build(B, threshold=SHOW_BELOW):
    """True when this client's profitability is below `threshold` (Aaron, 2026-09-22).

    Read from the deck's own stated ratio where there is one, so the slide appears exactly
    when the Financial Performance bullet says something below 3 : 1 — a client cannot see
    "5.7 : 1" on one slide and a guarantee slide on the next. Falls back to the Actuals
    ratio, then to revenue over cost.
    """
    r = ratio_of(B)
    return r is not None and r < threshold


def ratio_of(B):
    """The client's revenue-to-cost ratio, or None when there is no cost to divide by."""
    p = B.get("profitability")
    if isinstance(p, (int, float)) and p:
        return float(p)
    g = guarantee(B)
    return g["ratio"]


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


def render_chart(g, assets_dir):
    """Cumulative revenue against the guaranteed minimum, month by month.

    Two bars said what the totals were; the lines say whether the client is closing on the
    guarantee or drifting from it, which is the only question the slide exists to answer.
    Falls back to the two bars when there are no months to draw.
    """
    os.makedirs(assets_dir, exist_ok=True)
    use_font("Carlito")
    months = g["months"]
    path = os.path.join(assets_dir, "rg_lines.png")

    if not months:
        fig = plt.figure(figsize=(12.3, 2.3))
        ax = fig.add_axes([0.17, 0.10, 0.80, 0.86])
        vals = [g["minimum"], g["revenue"]]
        bars = ax.barh(["Guaranteed minimum\n(2 x program cost)", "Revenue to date"], vals,
                       height=0.5, color=[_TICK_HX, _ORANGE_HX if g["met"] else _NAVY_HX])
        top = max(vals) or 1
        for b, v in zip(bars, vals):
            ax.text(v + top * 0.012, b.get_y() + b.get_height() / 2, usd_compact(v),
                    va="center", ha="left", fontsize=15, fontweight="bold", color=_NAVY_HX)
        ax.set_xlim(0, top * 1.16)
        ax.invert_yaxis()
        ax.tick_params(axis="y", length=0, labelsize=13, colors=_TICK_HX)
        ax.set_xticks([])
        for side in ("top", "right", "bottom", "left"):
            ax.spines[side].set_visible(False)
        fig.savefig(path, dpi=200, facecolor="white", bbox_inches="tight", pad_inches=0.04)
        plt.close(fig)
        return path

    labels = [m[0] for m in months]
    cum_rev, cum_min = [], []
    r = c = 0.0
    for _lab, rev, cost in months:
        r += rev
        c += cost
        cum_rev.append(r)
        cum_min.append(MULTIPLE * c)

    fig = plt.figure(figsize=(12.3, 3.0))
    ax = fig.add_axes([0.07, 0.16, 0.86, 0.80])
    x = list(range(len(labels)))
    ax.fill_between(x, cum_min, cum_rev, where=[a >= b for a, b in zip(cum_rev, cum_min)],
                    color=_ORANGE_HX, alpha=0.16, interpolate=True, zorder=2)
    ax.fill_between(x, cum_min, cum_rev, where=[a < b for a, b in zip(cum_rev, cum_min)],
                    color=_NAVY_HX, alpha=0.10, interpolate=True, zorder=2)
    ax.plot(x, cum_min, color=_TICK_HX, lw=1.8, ls=(0, (4, 3)), zorder=4,
            label="Guaranteed minimum (2 x cost)")
    ax.plot(x, cum_rev, color=_ORANGE_HX, lw=2.6, zorder=5, label="Revenue")
    ax.plot(x[-1:], cum_rev[-1:], marker="o", ms=6, mfc="white", mec=_ORANGE_HX, mew=2,
            zorder=6)
    ax.set_ylim(0, max(max(cum_rev), max(cum_min)) * 1.12)
    ax.yaxis.set_major_formatter(lambda v, _p: usd_compact(v, 1) if v else "$0")
    ax.tick_params(axis="y", labelsize=11, colors=_TICK_HX)
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    step = max(1, len(labels) // 10)
    keep = list(range(len(labels) - 1, -1, -step))[::-1]
    ax.set_xticks(keep)
    ax.set_xticklabels([_short(labels[i]) for i in keep], fontsize=10.5, color=_NAVY_HX)
    ax.set_xlim(-0.5, len(labels) - 0.5)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("bottom", "left"):
        ax.spines[side].set_color("#B8C0CA")
    ax.legend(loc="upper left", frameon=False, fontsize=12, labelcolor=_TICK_HX)
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)
    return path


def _short(label):
    """'Jun 2026' -> "Jun'26", the house month format."""
    parts = label.split()
    return f"{parts[0]}'{parts[1][2:]}" if len(parts) == 2 else label


def _caption(g):
    """The sentence under the chart — derived from the figures beside it, never fixed."""
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
        line += (f"At the last {g['run_months']} complete months — ${g['run_rate']:,.0f} of "
                 f"revenue a month against ${g['monthly_cost']:,.0f} of cost — the gap closes "
                 f"in about {g['months_to_cover']} months.")
    elif g["run_rate"] is not None and g["monthly_cost"] is not None:
        line += (f"At the last {g['run_months']} complete months' revenue of "
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
    _tb(s, 0.5, 1.12, 12.3, 0.5,
        "Account Revenue Solution\u00ae returns at least twice its program cost. "
        "Revenue and cost since the program began, against that minimum.",
        14, GREYT, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)

    # Every label measured at what is DRAWN (16pt after restyle_fonts, inside PowerPoint's
    # own 0.1in margins), because three of them escaped their tiles when they were not.
    if not g["measurable"]:
        tiles = [(usd_compact(g["cost"]), _label("Program cost, to date", "Program cost"), NAVY),
                 ("\u2014", _label("Guaranteed minimum"), NAVY),
                 (usd_compact(g["revenue"]), _label("Revenue, to date"), NAVY),
                 ("\u2014", _label("Not measurable yet"), NAVY)]
    else:
        head = ((usd_compact(g["surplus"]), _label("Above the guarantee"), ORANGE)
                if g["met"] else
                (usd_compact(g["gap"]), _label("Short of the guarantee"), ORANGE))
        tiles = [(usd_compact(g["cost"]), _label("Program cost, to date", "Program cost"), NAVY),
                 (usd_compact(g["minimum"]), _label("Guaranteed minimum"), NAVY),
                 (usd_compact(g["revenue"]), _label("Revenue, to date"), NAVY),
                 head]
    for i, (v, lab, fill) in enumerate(tiles):
        _tile(s, 0.56 + i * 3.12, 1.66, TILE_W, TILE_H, v, lab, fill=fill)

    bottom = _fit_picture(s, render_chart(g, assets_dir), 0.5, 2.80, 12.3,
                          3.05 if g["months"] else 2.40)
    _tb(s, 0.5, bottom + 0.20, 12.3, 1.15, _caption(g), 15, NAVY, False,
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
    src = (f"{wb_src} — '{g['sheet']}' tab: Total Marginal Revenues and Total Cost, by month"
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
