#!/usr/bin/env python3
"""
revenue_guarantee_slide.py — the ARS "Revenue Guarantee" slide, inserted directly
after "Financial Performance".

ARS carries a 2 : 1 revenue guarantee: the program returns at least twice what it
costs. Until now that commitment appeared only as an adjective inside one bullet on
Financial Performance — "Profitability of 5.7 : 1 is well above the 2 : 1 threshold"
— so the guaranteed minimum itself was never a figure on any slide, and a reader
could not see how much room a client has above it, or how far a young program is
below it. This slide states the three numbers the guarantee is made of (Aaron,
2026-09-21): program cost to date, the guaranteed minimum (twice that cost), and
incremental revenue to date.

What it measures (Aaron, 2026-09-21)
------------------------------------
Program-to-date revenue against 2x program-to-date cost — the same two workbook
figures `profitability` is computed from, so this slide and the sentence on
Financial Performance can never disagree. `guarantee()` recomputes the ratio from
cost and revenue rather than reading `profitability`, and states the workbook's
value in the notes when the two round differently.

Below the guarantee
-------------------
The slide names the gap and how long it would take to close at the program's own
run rate. Closing a gap is not "gap / monthly revenue": cost keeps accruing too, so
each month adds revenue `r` and raises the minimum by `2c`. The gap closes at

    months = ceil( (2*cost - revenue) / (r - 2*c) )

and only when `r > 2*c`. When it is not, the honest answer is that the gap does not
close at the current run rate, and the slide says exactly that rather than printing
a number that assumes costs stop. `r` is the mean of the last 12 COMPLETE months of
incremental revenue (CLAUDE.md: comparisons use complete months only) and a month
left out is stated on the slide face, not only in the notes. `c` is the current
month's program cost, falling back to the program-to-date average when the workbook
does not carry one; which was used is in the notes.

A client with no cost booked yet cannot be measured against a multiple of it. That
is stated in a sentence (CLAUDE.md: missing source data is stated, never zeroed) —
the slide is not dropped and no 0 : 1 is drawn.

Public entry point
------------------
    add_revenue_guarantee_slide(prs, B, assets_dir, month_label,
                                after_title="Financial Performance")
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

from brand import usd_compact
from rpe_env import use_font
import month_complete as _MC

from product_mix_slide import (
    _tb, _pill, _tile, _fit_picture, _blank_slide, _slide_title,
    _sldid_of, _renumber,
    NAVY, ORANGE, GREYT, HEAD, BODY, _NAVY_HX, _ORANGE_HX, _TICK_HX,
)

# The multiple the program is sold on. One place, so a slide, a sentence and a test
# cannot drift apart if it is ever renegotiated.
MULTIPLE = 2.0

_RUNRATE_MEASURE = "monthly incremental revenue"


def guarantee(B):
    """The guarantee as numbers — pure, so the arithmetic is testable without pptx.

    Returns a dict. `measurable` is False when the workbook carries no program cost
    to date; every caller states that rather than dividing by it.
    """
    cost = abs(B.get("ltd_costs") or 0)
    revenue = B.get("ltd_revenue") or 0
    out = {
        "cost": cost,
        "revenue": revenue,
        "minimum": MULTIPLE * cost,
        "measurable": bool(cost),
        "ratio": None,
        "met": None,
        "surplus": None,
        "gap": None,
        "months_to_cover": None,
        "run_rate": None,
        "monthly_cost": None,
        "monthly_cost_from": None,
        "run_months": 0,
        "left_out": [],
    }
    if not cost:
        return out

    out["ratio"] = revenue / cost
    out["met"] = revenue >= out["minimum"]
    if out["met"]:
        out["surplus"] = revenue - out["minimum"]
        return out

    out["gap"] = out["minimum"] - revenue

    # Run rate over COMPLETE months only. A partial final month drags the mean down and
    # would overstate the months to cover — the same rule the spend and NSF/OD reads use.
    rows, res = _MC.complete_rows(B.get("monthly_rev_last12") or [], 1,
                                  _RUNRATE_MEASURE, min_volume=0)
    out["left_out"] = _MC.excluded_months(res)
    vals = [v for _, v in rows if v is not None]
    out["run_months"] = len(vals)
    if not vals:
        return out
    out["run_rate"] = sum(vals) / len(vals)

    months = B.get("months") or 0
    if B.get("cur_costs"):
        out["monthly_cost"] = abs(B["cur_costs"])
        out["monthly_cost_from"] = "this month's program cost"
    elif months:
        out["monthly_cost"] = cost / months
        out["monthly_cost_from"] = "the program-to-date average monthly cost"
    if out["monthly_cost"] is None:
        return out

    denom = out["run_rate"] - MULTIPLE * out["monthly_cost"]
    if denom > 0:
        out["months_to_cover"] = int(math.ceil(out["gap"] / denom))
    return out


def render_chart(g, assets_dir):
    """Two bars: the guaranteed minimum, and revenue to date. One scale, both labelled."""
    os.makedirs(assets_dir, exist_ok=True)
    use_font("Carlito")
    labels = ["Guaranteed minimum\n(2 x program cost)", "Incremental revenue\nto date"]
    vals = [g["minimum"], g["revenue"]]
    colors = [_TICK_HX, _ORANGE_HX if g["met"] else _NAVY_HX]

    fig = plt.figure(figsize=(12.3, 2.45))
    ax = fig.add_axes([0.17, 0.10, 0.80, 0.86])
    bars = ax.barh(labels, vals, height=0.52, color=colors)
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

    path = os.path.join(assets_dir, "rg_bars.png")
    fig.savefig(path, dpi=200, facecolor="white", bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    return path


def _caption(g):
    """The sentence under the chart — derived from the figures beside it, never fixed."""
    if not g["measurable"]:
        return ("The workbook carries no program cost to date, so revenue cannot be "
                "measured against a multiple of it. The guarantee is reported once "
                "costs are booked.")
    ratio = f"{g['ratio']:.1f} : 1"
    if g["met"]:
        return (f"Revenue to date is {ratio} against program cost — "
                f"{usd_compact(g['surplus'])} above the guaranteed minimum of "
                f"{usd_compact(g['minimum'])}.")

    line = (f"Revenue to date is {ratio} against program cost, "
            f"{usd_compact(g['gap'])} short of the guaranteed minimum of "
            f"{usd_compact(g['minimum'])}. ")
    if g["months_to_cover"] is not None:
        line += (f"At the last {g['run_months']} complete months' revenue of "
                 f"${g['run_rate']:,.0f} a month against program cost of "
                 f"${g['monthly_cost']:,.0f} a month, the gap closes in about "
                 f"{g['months_to_cover']} months.")
    elif g["run_rate"] is not None:
        line += (f"At the last {g['run_months']} complete months' revenue of "
                 f"${g['run_rate']:,.0f} a month, the gap does not close: program cost "
                 f"raises the guaranteed minimum by ${MULTIPLE * g['monthly_cost']:,.0f} "
                 f"over the same month.")
    else:
        line += "The workbook carries no complete month of revenue to read a run rate from."
    if g["left_out"]:
        line += (" " + ", ".join(g["left_out"]) +
                 " left out: incomplete in this extract.")
    return line


def _anchor(prs, after_title):
    """The slide this one follows, matched on its title CONTAINING after_title.

    Contains, not startswith: the shell titles the slide "ARS Financial Performance", and
    a startswith match on "Financial Performance" found nothing and quietly fell back to
    a different position — the silent no-op CLAUDE.md's swap gate exists to stop. A miss
    now raises and names what it did see.
    """
    want = after_title.lower()
    for s in prs.slides:
        if want in _slide_title(s).lower():
            return s
    raise SystemExit("Revenue Guarantee: no slide titled like %r to follow. Titles: %s"
                     % (after_title, [_slide_title(s) for s in prs.slides][:12]))


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
        "Account Revenue Solution® returns at least twice its program cost. "
        "Program-to-date revenue against that minimum.",
        14, GREYT, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)

    # Four tiles on the same rail as the other ARS tile slides. The fourth is the
    # headline — surplus in orange when the guarantee is met, the gap in navy when it
    # is not, so the slide reads the same way the figure does.
    if not g["measurable"]:
        tiles = [(usd_compact(g["cost"]), "Program cost, to date", NAVY),
                 ("—", "Guaranteed minimum", NAVY),
                 (usd_compact(g["revenue"]), "Incremental revenue, to date", NAVY),
                 ("—", "Not measurable this period", NAVY)]
    else:
        head = ((usd_compact(g["surplus"]), "Revenue above the guarantee", ORANGE)
                if g["met"] else
                (usd_compact(g["gap"]), "Short of the guarantee", NAVY))
        tiles = [(usd_compact(g["cost"]), "Program cost, to date", NAVY),
                 (usd_compact(g["minimum"]), "Guaranteed minimum (2 x cost)", NAVY),
                 (usd_compact(g["revenue"]), "Incremental revenue, to date", NAVY),
                 head]
    for i, (v, l, fill) in enumerate(tiles):
        _tile(s, 0.56 + i * 3.12, 1.66, 2.85, 0.84, v, l, fill=fill)

    bottom = 2.95
    if g["measurable"]:
        bottom = _fit_picture(s, render_chart(g, assets_dir), 0.5, 2.80, 12.3, 2.60)

    _tb(s, 0.5, bottom + 0.22, 12.3, 1.30, _caption(g), 15, NAVY, False,
        PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)

    wb_prof = B.get("profitability")
    note = (f"Source: {wb_src} — Executive Financials{tab}: Total Incremental Revenue and "
            f"Total Costs, program-to-date column. Selection: program to date through "
            f"{month_label}. Guarantee = {MULTIPLE:.0f} x program cost "
            f"({usd_compact(g['cost'])} → {usd_compact(g['minimum'])}); revenue "
            f"{usd_compact(g['revenue'])}.")
    if g["measurable"]:
        note += f" Ratio {g['ratio']:.2f} : 1"
        if wb_prof is not None and abs(round(g["ratio"], 2) - wb_prof) >= 0.01:
            note += f" (workbook profitability reads {wb_prof:.2f} : 1)"
        note += "."
    if g["gap"] is not None:
        note += (f" Gap {usd_compact(g['gap'])}. Run rate: mean of the last "
                 f"{g['run_months']} complete months of incremental revenue "
                 f"(All Months Rollup{tab})")
        note += (f" = ${g['run_rate']:,.0f}/month" if g["run_rate"] is not None
                 else " — no complete month available")
        if g["monthly_cost"] is not None:
            note += (f"; monthly cost ${g['monthly_cost']:,.0f} from "
                     f"{g['monthly_cost_from']}")
        note += (f". Months to cover = ceil(gap / (run rate − {MULTIPLE:.0f} x monthly "
                 f"cost)), which accrues cost over the same months: "
                 f"{g['months_to_cover'] if g['months_to_cover'] is not None else 'does not close at this run rate'}.")
        if g["left_out"]:
            excl = ", ".join(f"{m} {usd_compact(v)}"
                             for m, v in (B.get("monthly_rev_last12") or [])
                             if m in g["left_out"])
            note += f" Left out as incomplete: {excl or ', '.join(g['left_out'])}."
    s.notes_slide.notes_text_frame.text = note

    logo = os.path.join(assets_dir, "logo.png")
    if os.path.exists(logo):
        s.shapes.add_picture(logo, Inches(11.28), Inches(6.78), Inches(1.70), Inches(0.54))

    # Added at the end, then moved: a slide is only ever ADDED and reordered, never
    # deleted, or python-pptx hands its freed partname to a later slide (CLAUDE.md).
    sid, tid = _sldid_of(prs, s), _sldid_of(prs, anchor)
    if sid is None or tid is None:
        raise SystemExit("Revenue Guarantee: could not place the slide after its anchor")
    prs.slides._sldIdLst.remove(sid); tid.addnext(sid)
    if renumber:
        _renumber(prs)
    return s, g
