#!/usr/bin/env python3
"""
pnl_slide.py — ARS Financial Performance, on EVERY ARS deck (Aaron, 2026-10-02).

"i wanted a P&L slide that makes it easier to see the full financial picture."

It REPLACES the template's five-tile slide of the same name. Those tiles stated revenue
and profit, this month and program to date, over a profitability ratio, and could not show
where the money went: Marine FCU's read $144,999 of revenue and $144,999 of profit for
August, identical, because August carried no respondent fee at all. Nothing on the slide
said so, and a reader was left to assume a rounding error.

So this slide is the program's P&L from the workbook's Actuals tab — incremental
revenue, each cost line the tab itemises, total costs and incremental profit — in
three columns: the last COMPLETE month, that month's year to date, and the program to
date. The year column is the one the tiles have no room for: on a 97-month program a
single month beside the lifetime total says nothing about how this year is running.

The figures come from `revenue_guarantee_slide.pnl`, which is where the Actuals tab is
read and the complete-month rule applied, so the P&L on this slide and the guarantee
arithmetic on that one cannot disagree. That slide no longer tabulates the P&L itself
— it appears only below 3 : 1, and a deck must not carry the same table twice.

    add_pnl_slide(prs, B, assets_dir, month_label, ...)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from pptx.util import Inches
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

from product_mix_slide import (
    _tb, _pill, _blank_slide, _slide_title, _sldid_of, _renumber,
    NAVY, ORANGE, GREYT, HEAD, BODY,
    _NAVY_HX, _ORANGE_HX, _TICK_HX, _GREY_HX,
)
from shapes import add_table as _add_table, fit_picture as _fit_picture
from rpe_env import use_font
import periods as _P
import month_complete as _MC
import revenue_guarantee_slide as _RG

# The slide KEEPS the name the deck has always used for its financial slide (Aaron,
# 2026-10-02) — this format replaces that slide rather than joining it.
TITLE = "ARS Financial Performance"
# Full width: the three-column table is 12.3in and has the slide to itself, which is why
# it is here and not beside the guarantee callouts, where only two columns fit.
TABLE_L, TABLE_W, ROW_H = 0.5, 12.3, 0.46
ROW_MIN = 0.33
LABEL_W, COL_W = 4.2, 2.7
TEXT_PT, TEXT_W = _RG.TEXT_PT, _RG.TEXT_W
SUB_T, GAP_SUB, GAP_CAPTION = _RG.SUB_T, _RG.GAP_SUB, _RG.GAP_CAPTION
CONTENT_BOTTOM = _RG.CONTENT_BOTTOM
# More drop than the guarantee slide allows itself: that one has callouts down the right
# filling the space, and this is a four-row table alone on the slide. Capped rather than
# free-centred so a program with many cost lines still starts near the subtitle.
MAX_DROP = 0.95

# One line at the size it is DRAWN (16pt): two lines pushed the chart into the logo band.
SUBTITLE = ("From the workbook's Actuals tab: the last complete month, the year, and the "
            "program to date.")
# The chart strip under the table. Bounded, never placed by width alone.
CHART_L, CHART_W, GAP_CHART = 0.5, 12.3, 0.20
# The strip is sized from the room the table and the caption leave, between these bounds,
# and the figure is RENDERED at that height so it always runs the full width. A constant
# height left white space under a captionless slide and shrank the chart off the table's
# left edge when a caption ran to two lines.
CHART_MIN_H, CHART_MAX_H, CHART_FLOOR = 1.05, 2.50, 6.74
# The ceiling went 2.05 -> 2.50 when a lone fee line stopped needing a Total costs row
# (Aaron, 2026-10-02): one row fewer freed half an inch the strip was not taking.
CHART_MONTHS = 12


def caption(P, g):
    """The sentence under the table — derived from the figures, never fixed, often empty.

    ONE line, because the chart below is sized from what the caption leaves.

    It does NOT explain a month that carried no program cost (Aaron, 2026-10-02). That
    sentence was here first, on the reasoning that identical revenue and profit look like
    an error: the table shows the $0 cost line, and the chart shows the month as a bar with
    no orange in it, so the deck says it twice without the sentence saying it a third time.

    A month left out as incomplete is different and stays: nothing else on the slide says
    a month is missing (CLAUDE.md — a left-out month is STATED, never silently dropped).
    """
    bits = []
    if g.get("left_out"):
        bits.append(f"{g['left_out']} is left out: incomplete in this extract.")
    return " ".join(bits)




def chart_series(g, n=CHART_MONTHS):
    """(labels, revenue, cost) for the last `n` COMPLETE months, oldest first.

    The same months the P&L reads, so the bar on the right of the chart is the figure in
    the month column of the table. An incomplete trailing month is not charted at all —
    charting it draws a collapse that is an artefact of the pull date (CLAUDE.md).
    """
    months = g.get("months") or []
    if not months:
        return [], [], []
    rows, _res = _MC.complete_rows(months, 1, _RG._RUNRATE_MEASURE, min_volume=0)
    last = rows[-1][0] if rows else None
    i = next((k for k, m in enumerate(months) if m[0] == last), None)
    if i is None:
        return [], [], []
    lo = max(0, i - n + 1)
    window = months[lo:i + 1]
    return ([m[0] for m in window], [float(m[1] or 0) for m in window],
            [float(m[2] or 0) for m in window])


def render_chart(g, assets_dir, height, n=CHART_MONTHS):
    """Each month's revenue as a bar, split into cost and profit. -> png path, or None.

    Stacked rather than grouped: the bar's HEIGHT is that month's incremental revenue, so
    the chart and the table's revenue row are the same quantity, and the orange is the part
    of it that went on program cost. A month with no cost has no orange — which is exactly
    what the caption says in words about Marine's August.
    """
    labels, rev, cost = chart_series(g, n)
    if len(labels) < 2:
        return None
    use_font("Carlito")
    _P.install_month_axis_guard()
    profit = [r - c for r, c in zip(rev, cost)]

    fig = plt.figure(figsize=(CHART_W, height))
    # Margins in INCHES, converted, because the strip's height varies with what the table
    # and caption leave: an axes-relative legend anchor that cleared the top at 1.38in was
    # clipped against the table above at 2.05in. 0.30in for the legend band, 0.46in for the
    # rotated month labels.
    top_band, bottom_band = 0.30 / height, 0.46 / height
    ax = fig.add_axes([0.038, bottom_band, 0.952, 1 - bottom_band - top_band])
    x = range(len(labels))
    # White edges separate the stacked segments (STYLE.md).
    ax.bar(x, profit, color=_NAVY_HX, width=0.62, edgecolor="white", linewidth=0.6,
           label="Incremental profit")
    ax.bar(x, cost, bottom=profit, color=_ORANGE_HX, width=0.62, edgecolor="white",
           linewidth=0.6, label="Program cost")
    ax.set_xticks(list(x))
    ax.set_xticklabels(_P.axis_months(labels), fontsize=9, color=_TICK_HX,
                       rotation=45, ha="right")
    ax.tick_params(axis="x", length=0, pad=1)
    ax.tick_params(axis="y", labelsize=9, colors=_TICK_HX, length=0)
    ax.yaxis.set_major_formatter(FuncFormatter(
        lambda v, _p: f"${v/1000:,.0f}K" if v else "$0"))
    ax.set_axisbelow(True)
    ax.grid(axis="y", color=_GREY_HX, linewidth=0.7)
    for side in ("top", "right", "bottom"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(_GREY_HX)
    # Sat on the reserved band directly above the axes, whatever the strip's height.
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.005), ncol=2, frameon=False,
              fontsize=9.5, labelcolor=_TICK_HX, handlelength=1.1, columnspacing=1.2)
    out = os.path.join(assets_dir, "pnl_months.png")
    os.makedirs(assets_dir, exist_ok=True)
    fig.savefig(out, dpi=300, facecolor="white")
    plt.close(fig)
    return out


def _anchor(prs, after_title):
    for s in prs.slides:
        if after_title.lower() in (_slide_title(s) or "").lower():
            return s
    raise SystemExit(f"{TITLE}: no slide whose title contains {after_title!r} to follow")


def _empty(slide):
    """Strip every shape off a slide, keeping the slide itself.

    The slide part, its partname and its place in the deck all survive — which is the
    point. Its relationships survive too, so an image the template put here stays in the
    package though nothing draws it; that is a few unused bytes, against a freed partname
    being handed to the next slide added (CLAUDE.md) and taking another slide's part out.
    """
    for sh in list(slide.shapes):
        sh._element.getparent().remove(sh._element)
    return slide


def notes_text(P, g, B, wb_src, tab, month_label):
    cols = " / ".join(P["columns"])
    # A lone cost line is emitted as the TOTAL row under its own name (there is no separate
    # "Total costs" row then), so the notes read both kinds or they would say a client with
    # one fee has no itemised cost at all.
    lines = [l for l, _v, k in P["rows"] if k == "line"] or             [l for l, _v, k in P["rows"] if k == "total" and l != "Total costs"]
    return (
        f"Source: {wb_src}{(' — ' + tab) if tab else ''}, the Actuals tab, read by "
        f"actuals_tab.py and carried in base.json. Columns: {cols}. "
        f"Reporting month {month_label}; the month column is the last COMPLETE month of the "
        f"Actuals series (CLAUDE.md: comparisons use complete months only)"
        + (f", and {g['left_out']} is left out as incomplete" if g.get("left_out") else "")
        + ". "
        f"Cost lines shown: {', '.join(lines) if lines else 'none — the tab itemises no cost'}"
        + (f". Left off because the program has never been charged them: "
           f"{', '.join(P['dropped'])}" if P["dropped"] else "")
        + ". Costs are shown in parentheses; a negative cost is a discount and reads as a "
        f"credit. Program to date totals every month of the tab, so they match ARS "
        f"Financial Performance's PTD tiles. The same figures drive the Revenue Guarantee "
        f"slide where one is built."
    )


def add_pnl_slide(prs, B, assets_dir, month_label, after_title="Financial Performance",
                  renumber=True, wb_src="ARS workbook", tab=""):
    """Build the ARS Profit & Loss slide after Financial Performance. -> (slide, pnl)."""
    g = _RG.guarantee(B)
    P = _RG.pnl(g)

    # REPLACE the template's slide of this name where there is one, in place; only build a
    # new slide when a deck has none (Aaron, 2026-10-02).
    anchor = _anchor(prs, after_title)
    existing = next((x for x in prs.slides
                     if (_slide_title(x) or "").strip().lower() == TITLE.lower()), None)
    s = _empty(existing) if existing is not None else _blank_slide(prs, anchor)

    _tb(s, 0.5, 0.28, 9.6, 0.9, TITLE, 26, NAVY, True,
        PP_ALIGN.LEFT, HEAD, MSO_ANCHOR.MIDDLE)
    _pill(s, f"PTD · {month_label}")

    sub_h = _RG._text_h(SUBTITLE)
    _tb(s, 0.5, SUB_T, TEXT_W, sub_h, SUBTITLE, TEXT_PT, GREYT, False,
        PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
    top = SUB_T + sub_h + GAP_SUB

    cap = caption(P, g)
    # Rows tighten for a program with many cost lines (Austin Bank carries nine) so the table ends
    # above the logo band instead of running off the slide at 8.15in (2026.10). ROW_MIN is one 16pt
    # line plus the cell's 2pt top and bottom margins; a table that still does not fit at ROW_MIN
    # is left for the validator to report rather than shrunk below the type floor.
    n_rows = len(P["rows"]) + 1
    cap_h = GAP_CAPTION + _RG._text_h(cap) if cap else 0
    row_h = min(ROW_H, max(ROW_MIN, (CONTENT_BOTTOM - top - cap_h) / n_rows))
    table_h = row_h * n_rows
    # Table, then any caption, then the chart strip in whatever is left above the logo
    # band. Measured BEFORE the chart is rendered, so the figure is drawn at the height it
    # will occupy and never scaled down to fit.
    block = table_h + (GAP_CAPTION + _RG._text_h(cap) if cap else 0)
    room = CHART_FLOOR - (top + block + GAP_CHART)
    chart_h = min(CHART_MAX_H, room)
    chart = render_chart(g, assets_dir, chart_h) if chart_h >= CHART_MIN_H else None
    if chart is None:
        # No room for a readable strip: centre the table as it was before there was a chart.
        top += min(MAX_DROP, max(0.0, (CONTENT_BOTTOM - top - block) / 2))

    data = [[""] + P["columns"]]
    for label, vals, kind in P["rows"]:
        data.append([("    " + label) if kind == "line" else label]
                    + [_RG.money(v, kind) for v in vals])
    n = len(P["columns"])
    # Orange goes on the PROFIT row, not on whichever row happens to be last: Profitability
    # follows it, and a derived ratio is not the line a reader should be drawn to first.
    profit_at = next((k for k, (_l, _v, kind) in enumerate(P["rows"], start=1)
                      if kind == "profit"), len(data) - 1)
    tb = _add_table(s, TABLE_L, top, TABLE_W, table_h, data,
                    [LABEL_W] + [COL_W] * n,
                    highlight=(profit_at,), fs=TEXT_PT).table
    for i, row in enumerate(data):
        kind = P["rows"][i - 1][2] if i else "head"
        for j in range(n + 1):
            para = tb.cell(i, j).text_frame.paragraphs[0]
            if j:
                para.alignment = PP_ALIGN.RIGHT
            if kind in ("total", "ratio"):
                for r in para.runs:
                    r.font.bold = True

    below = top + table_h
    if cap:
        _tb(s, 0.5, below + GAP_CAPTION, TEXT_W, _RG._text_h(cap), cap,
            TEXT_PT, NAVY, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
        below += GAP_CAPTION + _RG._text_h(cap)
    if chart is not None:
        # In a BOX, at the height it was rendered for: bounded, never placed by width.
        _fit_picture(s, chart, CHART_L, below + GAP_CHART, CHART_W, chart_h)

    s.notes_slide.notes_text_frame.text = notes_text(P, g, B, wb_src, tab, month_label)

    logo = os.path.join(assets_dir, "logo.png")
    if os.path.exists(logo):
        s.shapes.add_picture(logo, Inches(11.28), Inches(6.78), Inches(1.70), Inches(0.54))

    if existing is None:
        # Added at the end, then moved: a slide is only ever ADDED and reordered, never
        # deleted, or python-pptx hands its freed partname to a later slide (CLAUDE.md).
        sid, tid = _sldid_of(prs, s), _sldid_of(prs, anchor)
        if sid is None or tid is None:
            raise SystemExit(f"{TITLE}: could not place the slide after its anchor")
        prs.slides._sldIdLst.remove(sid)
        tid.addnext(sid)
        if renumber:
            _renumber(prs)
    return s, P
