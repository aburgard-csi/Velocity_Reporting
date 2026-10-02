#!/usr/bin/env python3
"""
cp_charts.py — CashPlease chart renderers.

Styling comes from the Retail Performance Engine's shared layer so a CashPlease
slide sitting inside an ILS review deck matches the ARS/ICS/MRPC decks beside it:
`brand` for the palette, `periods.mon_yy` / `AXIS_ROTATION` / `AXIS_HA` for the one
month-label format (templates/STYLE.md "Month labels on chart axes"), and
`chart_lib._letterbox` so the saved PNG matches its picture box exactly rather than
stretching to fill it.

Every renderer takes its target pixel size from the caller, and the caller passes the
size that matches the slide's picture box. A chart rendered at one aspect and placed
in a box of another is the stretch defect in STYLE.md ("Charts").

Every renderer takes that box in INCHES (`box`) and draws its figure at exactly that
size (Aaron, 2026-10-02). The figures used to be drawn 8-11" wide and shrunk into boxes
of 4.5-8.5", so a 10-11 pt label landed on the slide at 5-7 pt beside 11-14 pt table
text. Drawn at the box's own size, a font size here IS its size on the slide, and the
pixel size follows from the box (`_px`), so the aspect cannot drift from it either.
"""
import os
import textwrap
import sys

# `build/` for the shared layer and `build/ars_pipeline/` for `chart_lib`. Neither is a
# package, so this is the same sys.path idiom `chart_lib.py` itself uses.
_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(_HERE, os.pardir), os.path.join(_HERE, os.pardir, "ars_pipeline")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from brand import (NAVY, ORANGE, TICK, GRID, MUTED, LIGHT, STEEL_SOFT, TEAL,
                   CHART_FONT)
from periods import mon_yy, AXIS_ROTATION, AXIS_HA

# `_letterbox` lives in ars_pipeline but is not ARS logic — it letterboxes a rendered
# PNG to its slide box so the image cannot stretch. It is a shared chart primitive that
# happens to sit in an ARS folder, and it is one of the seams the top-level deck-builder
# refactor pulls on (MIGRATION.md 1a). Importing it is not "running ARS logic while
# building CashPlease"; re-implementing it would be the actual mistake.
from chart_lib import _letterbox

plt.rcParams["font.family"] = CHART_FONT

# `_letterbox` saves at 200 dpi; a target at the same density is pasted 1:1, not resampled.
PX_PER_IN = 200

# On-slide point sizes. The figure is drawn at its box's size, so these are what the
# reader sees: axis and category labels at 12 pt, value labels a point larger and bold.
AXIS_PT = 12
LABEL_PT = 12
VALUE_PT = 13


def _px(box):
    """Target pixel size for a box given in inches (width, height)."""
    return round(box[0] * PX_PER_IN), round(box[1] * PX_PER_IN)


def _money(v):
    if abs(v) >= 1_000_000:
        return f"${v/1_000_000:.1f}M"
    if abs(v) >= 1_000:
        return f"${v/1_000:.0f}K"
    return f"${v:,.0f}"


def _thin(labels, keep=12):
    """Blank out labels so a long axis stays readable.

    A 33-month axis cannot seat 33 angled MMM'YY labels. Thinning keeps the axis
    honest — every point is still plotted, only the LABELS are sampled — where
    dropping months would change the shape of the line.
    """
    if len(labels) <= keep:
        return labels
    step = max(1, round(len(labels) / keep))
    return [lb if (len(labels) - 1 - i) % step == 0 else ""
            for i, lb in enumerate(labels)]


def _frame(ax, size=AXIS_PT):
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.xaxis.grid(False)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(MUTED)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(axis="both", labelsize=size, colors=TICK, length=0)


def monthly_volume_chart(out_png, months, counts, principal, partial=None,
                         box=(8.50, 4.71)):
    """Loans booked per completed month (navy bars) with principal advanced (line).

    The line is TEAL, not navy: a navy line over navy bars is invisible, and
    brand.TEAL is the colour chosen for exactly this case — it clears 3:1 contrast
    against both the bars and the white background (brand.py).
    """
    # The partial month IS plotted (Aaron, 2026-09-02), where it used to be reported as
    # a bare count beside the chart. The reason it was kept off — a part-month bar reads
    # as a collapse in volume — is handled by the house TREATMENT for exactly this case
    # (templates/STYLE.md): the standard navy bars with the last COMPLETE month orange,
    # and the partial month "hatched steel" — STEEL_SOFT at alpha 0.42 with a '//' hatch
    # and a white edge, matching `mrpc_charts_gen.py` line for line. Its value label is
    # TICK grey rather than white, as MRPC's is, and it is annotated with the date it
    # runs through so it cannot be mistaken for a finished month.
    months = list(months)
    counts = list(counts)
    principal = list(principal)
    if partial:
        months.append(partial["period_month"])
        counts.append(partial["loans"])
        principal.append(partial["principal"])

    fig, ax = plt.subplots(figsize=box)
    n_full = len(counts) - (1 if partial else 0)
    colors = [NAVY] * n_full
    if colors:
        colors[-1] = ORANGE
    bars = ax.bar(range(n_full), counts[:n_full], color=colors, width=0.66,
                  label="Loans booked", zorder=2)
    if partial:
        pb = ax.bar([n_full], [counts[-1]], width=0.66, color=STEEL_SOFT, alpha=0.42,
                    hatch="//", edgecolor="white", linewidth=0.5, zorder=2,
                    label=f"{mon_yy(partial['period_month'])} (partial, to "
                          f"{partial['through']})")
        bars = list(bars) + list(pb)

    top = max(counts) if counts else 1
    # Value labels sit INSIDE the bar, near its base. Above the bar they collide with
    # the principal line, which crosses the same band — STYLE.md forbids a label
    # sitting on a line. A bar too short to hold its own label gets none.
    if len(counts) <= 14:
        for i, (b, v) in enumerate(zip(bars, counts)):
            if v < top * 0.16:
                continue
            # A faded partial bar cannot carry white text; MRPC uses TICK for the
            # partial month's label for the same reason.
            is_partial = partial and i == len(counts) - 1
            ax.text(b.get_x() + b.get_width() / 2, top * 0.035, f"{v:,}",
                    ha="center", va="bottom", fontsize=LABEL_PT,
                    color=TICK if is_partial else "white",
                    weight="bold", zorder=4)
    if partial:
        pbar = bars[-1]
        ax.annotate(f"to {partial['through']}",
                    (pbar.get_x() + pbar.get_width() / 2, counts[-1]),
                    textcoords="offset points", xytext=(0, 7),
                    ha="center", fontsize=AXIS_PT, color=TICK, zorder=4)

    ax.set_xticks(range(len(months)))
    ax.set_xticklabels(_thin([mon_yy(m) for m in months]),
                       rotation=AXIS_ROTATION, ha=AXIS_HA, fontsize=AXIS_PT, color=TICK)
    ax.set_ylim(0, top * 1.16)
    _frame(ax)

    ax2 = ax.twinx()
    # The line stops at the last COMPLETE month (Aaron, 2026-09-17: "don't draw trend lines
    # over partial months"). A part-month point reads as a collapse however the bar beneath
    # it is hatched; the partial month keeps its hatched bar and its count, not a point.
    ax2.plot(range(n_full), principal[:n_full], color=TEAL, linewidth=2.4,
             marker="o", markersize=4, zorder=3, label="Principal advanced")
    ax2.set_ylim(0, (max(principal) if principal else 1) * 1.20)
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: _money(v)))
    ax2.tick_params(axis="y", labelsize=AXIS_PT, colors=TEAL, length=0)
    for side in ("top", "left", "right"):
        ax2.spines[side].set_visible(False)
    ax2.grid(False)

    # Legend ABOVE the plot area, not inside it: an upper-left legend sits exactly
    # where the tallest bars and the line already are.
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="lower left", bbox_to_anchor=(0, 1.01, 1, 0.12),
              mode="expand", frameon=False, fontsize=AXIS_PT, labelcolor=TICK,
              ncol=len(l1 + l2), borderaxespad=0)

    fig.tight_layout()
    _letterbox(fig, out_png, *_px(box))
    return out_png


def cumulative_growth_chart(out_png, months, counts, box=(7.40, 2.80)):
    """Cumulative loans booked since the program started — the adoption curve."""
    cum, run = [], 0
    for c in counts:
        run += c
        cum.append(run)

    fig, ax = plt.subplots(figsize=box)
    ax.fill_between(range(len(cum)), cum, color=LIGHT, alpha=0.65, zorder=2)
    ax.plot(range(len(cum)), cum, color=NAVY, linewidth=2.4, zorder=3)
    if cum:
        ax.plot([len(cum) - 1], [cum[-1]], marker="o", markersize=7,
                color=ORANGE, zorder=4)
        ax.annotate(f"{cum[-1]:,}", (len(cum) - 1, cum[-1]),
                    textcoords="offset points", xytext=(-6, 10),
                    ha="right", fontsize=VALUE_PT + 1, color=NAVY, weight="bold")

    ax.set_xticks(range(len(months)))
    ax.set_xticklabels(_thin([mon_yy(m) for m in months]),
                       rotation=AXIS_ROTATION, ha=AXIS_HA, fontsize=AXIS_PT, color=TICK)
    ax.set_ylim(0, (max(cum) if cum else 1) * 1.18)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v):,}"))
    _frame(ax)
    fig.tight_layout()
    _letterbox(fig, out_png, *_px(box))
    return out_png


def status_mix_chart(out_png, labels, counts, box=(4.52, 2.52)):
    """Loans by status as ranked horizontal bars.

    Ranked bars rather than a donut: the status set runs to seven categories and a
    donut needs a legend to carry that many, which reads poorly at 15 feet (the same
    reason MRPC's Cancellations by Reason moved to bars — templates/STYLE.md v6).
    Statuses with no loans are dropped; a row of zero-length bars is noise.
    """
    pairs = [(lb, c) for lb, c in zip(labels, counts) if c > 0]
    pairs.sort(key=lambda p: p[1])
    labels = [p[0] for p in pairs]
    counts = [p[1] for p in pairs]

    fig, ax = plt.subplots(figsize=box)
    colors = [ORANGE if lb in ("Funded", "Overdue") else NAVY for lb in labels]
    bars = ax.barh(range(len(counts)), counts, color=colors, height=0.62)

    top = max(counts) if counts else 1
    total = sum(counts) or 1
    for b, v in zip(bars, counts):
        ax.text(v + top * 0.02, b.get_y() + b.get_height() / 2,
                f"{v:,}  ({v/total:.1%})", va="center", ha="left",
                fontsize=LABEL_PT, color=NAVY)

    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=LABEL_PT, color=TICK)
    # Room right of the longest bar for its "6,005  (88.7%)" label, which at 12 pt on a
    # 4.5" box takes about a third of the plot width.
    ax.set_xlim(0, top * 1.62)
    ax.set_xticks([])
    for side in ("top", "right", "bottom"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(MUTED)
    ax.tick_params(axis="y", length=0)
    fig.tight_layout()
    _letterbox(fig, out_png, *_px(box))
    return out_png


def peer_index_chart(out_png, labels, ratios, box=(5.75, 4.02), wrap=18):
    """Client measured against the cohort, cohort = 100.

    One axis for metrics that do not share a unit (rates and dollars), which a
    grouped bar chart cannot do honestly. Bars are one colour and the reference line
    carries the accent: colouring "above" and "below" differently would assert that
    higher is better, which is false for the charge-off rate.
    """
    # Metric labels wrap rather than shrink: "Loans per 1,000 DDAs (12 mo)" at 12 pt is
    # wider on one line than a third of the box.
    labels = [textwrap.fill(lb, wrap) for lb in labels]
    fig, ax = plt.subplots(figsize=box)
    y = list(range(len(labels)))
    ax.barh(y, ratios, color=NAVY, height=0.5, zorder=2)
    ax.axvline(100, color=ORANGE, linewidth=2.2, zorder=3)

    top = max(ratios + [100]) if ratios else 100
    xmax = top * 1.22
    # Value labels go in a right-aligned column, not at each bar's end. Trailing the
    # bar puts a label wherever the bar happens to stop — and a bar near the index of
    # 100 lands its label on the reference line (WesBanco's "96" did exactly that).
    for i, v in zip(y, ratios):
        ax.text(xmax, i, f"{v:.0f}", va="center", ha="right",
                fontsize=VALUE_PT, color=NAVY, weight="bold")

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=LABEL_PT, color=TICK)
    ax.set_ylim(len(labels) - 0.5, -0.9)     # inverted, with headroom for the caption
    ax.set_xlim(0, xmax)
    ax.set_xticks([])
    ax.text(100, 1.0, "cohort = 100", transform=ax.get_xaxis_transform(),
            ha="center", va="bottom", fontsize=AXIS_PT, color=ORANGE)
    for side in ("top", "right", "bottom"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(MUTED)
    ax.tick_params(axis="y", length=0)
    fig.tight_layout()
    _letterbox(fig, out_png, *_px(box))
    return out_png
