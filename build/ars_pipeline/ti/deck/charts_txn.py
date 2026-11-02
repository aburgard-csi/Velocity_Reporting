# Ported from ARS v5 02-Scripts/ars/deck/charts_txn.py at a491b5c (James Gilmore); logic unchanged.
"""Data-shape renderers for the transaction-intelligence chapter.

Forms the approved catalog (lab/DESIGN/report-mockups/slides-txn-suite.html)
introduced and charts.py did not already carry. Palette and conventions come
from charts.py: author at the width of the slot you land in, expose a
``_*_fig`` returning ``(fig, meta)`` so structure is assertable without
pixel-reading, and take ``out`` as the last positional argument.

Orange marks the finding, never the field.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .charts import (FIG_W_FULL, FIG_W_RAIL, GREEN, GREY, GRID, LIGHT, NAVY,
                     ORANGE, RED, STEEL, TINT, _clean, _save, plt)

# amber sequential ramp, light -> dark, one hue (matches the mockup)
RAMP = ["#FDF3E3", "#FADCB4", "#F6C078", "#F0A23C", "#D9820E"]
BLANK = "#F2F4F7"
# The smallest type any of these charts draws, in figure points. The charts land on the slide at
# roughly 0.92x (rail width) to 1.05x (full width), so 13pt here reads as 12pt or more on the slide
# (Sheila's 1798 slide review, 2026-10-30: chart labels at 9.5-10pt). RPE addition, not in v5.
TXT = 13


def _fmt_money(v) -> str:
    """The deck's one money grammar (labels.money); this was a second copy of it (2026-10-28)."""
    from .labels import money
    return money(v)


# ---------------------------------------------------------------- marimekko

def _marimekko_fig(rows: list, width_label: str, height_label: str):
    """Column width = share of one measure, height = share of another. The
    channel that is rare but carries the money is a tall thin block, which a
    pair of bar charts cannot say. rows: [[label, width_value, height_value]].
    """
    total_w = sum(r[1] for r in rows) or 1
    total_h = sum(r[2] for r in rows) or 1
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, 4.4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.16)
    ax.axis("off")
    gap = 0.008
    span = 1 - gap * (len(rows) - 1)
    tallest = max(r[2] for r in rows) / total_h or 1
    x, meta = 0.0, []
    for i, (label, wv, hv) in enumerate(rows):
        ws, hs = wv / total_w, hv / total_h
        w = span * ws
        h = (hs / tallest) * 0.80
        lit = hs > ws * 1.15          # carries more money than volume
        color = ORANGE if lit else (NAVY if i % 2 == 0 else STEEL)
        ax.add_patch(plt.Rectangle((x, 0.16), w, h, facecolor=color,
                                   edgecolor="white", linewidth=1.4))
        cx = min(max(x + w / 2, 0.045), 0.955)
        ax.text(cx, 0.16 + h + 0.022, f"{hs * 100:.0f}% {height_label}",
                ha="center", fontsize=TXT, fontweight="bold",
                color=ORANGE if lit else NAVY)
        ax.text(cx, 0.095, label, ha="center", fontsize=TXT,
                fontweight="bold", color=NAVY)
        ax.text(cx, 0.025, f"{ws * 100:.0f}% {width_label}", ha="center",
                fontsize=TXT, color=GREY)
        meta.append({"label": label, "width_share": ws, "height_share": hs,
                     "lit": lit})
        x += w + gap
    return fig, {"columns": meta,
                 "width_shares_sum": sum(m["width_share"] for m in meta)}


def marimekko(rows: list, out: Path, width_label: str = "of transactions",
              height_label: str = "of dollars") -> Path:
    fig, _ = _marimekko_fig(rows, width_label, height_label)
    return _save(fig, out)


# ------------------------------------------------------------------- pareto

def _pareto_fig(rows: list, threshold: float, note: str):
    """Bars plus the cumulative line and the 80% rule -- how few
    counterparties account for most of the money. rows: [[label, sub, value]].
    """
    total = sum(r[2] for r in rows) or 1
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, 4.5))
    xs = np.arange(len(rows))
    vals = [r[2] for r in rows]
    ax.bar(xs, vals, width=0.62, color=ORANGE,
           alpha=0.95, edgecolor="white", linewidth=1.2)
    # A name wraps to two lines rather than being cut ("Capital One Mob…", 2026-10-28): the
    # caller clips at 28, this wraps at 14, upright under its own bar.
    import textwrap
    ax.set_xticks(xs)
    ax.set_xticklabels([textwrap.fill(str(r[0]), 11, break_long_words=False) for r in rows],
                       fontsize=TXT, color=NAVY)
    ax.set_ylim(0, max(vals) * 1.30)
    ax.get_yaxis().set_visible(False)
    cum = np.cumsum(vals) / total
    ax2 = ax.twinx()
    ax2.plot(xs, cum, color=NAVY, lw=2.6, marker="o", ms=5,
             markerfacecolor="white", markeredgewidth=2, markeredgecolor=NAVY)
    # The values are drawn on the line's own axes, in the bars' coordinates, with a white halo: drawn on
    # the bars' axes the cumulative line ran across the fourth label ("$10.1M", slide 11, 2026-10-27).
    from matplotlib import patheffects
    peak = max(vals)
    for x, v, c in zip(xs, vals, cum):
        y = v + peak * 0.03
        line_y = c * peak            # the line's height in the bars' units (both axes run to 1.30 x the peak)
        if y - peak * 0.03 <= line_y <= y + peak * 0.09:
            y = line_y + peak * 0.045        # the line passes through the label: stand it above the line
        ax2.text(x, y, _fmt_money(v), ha="center",
                 fontsize=TXT, fontweight="bold", color=NAVY, transform=ax.transData,
                 path_effects=[patheffects.withStroke(linewidth=3.5, foreground="white")],
                 zorder=5)
    ax2.set_ylim(0, 1.30)
    ax2.get_yaxis().set_visible(False)
    ax2.axhline(threshold, color=ORANGE, lw=1.5, ls="--")
    ax2.text(len(rows) - 0.4, threshold + 0.03,
             f"{threshold * 100:.0f}% of the dollars", ha="right",
             fontsize=TXT, fontweight="bold", color=ORANGE)
    for s in ("top", "right", "left"):
        ax2.spines[s].set_visible(False)
    _clean(ax)
    if note:
        ax.set_xlabel(note, fontsize=TXT, color=GREY, labelpad=10)
    crossed = int(np.argmax(cum >= threshold)) + 1 if (cum >= threshold).any() \
        else None
    return fig, {"bars": len(rows), "cumulative": list(cum),
                 "reaches_threshold_at": crossed}


def pareto(rows: list, out: Path, threshold: float = 0.8,
           note: str = "") -> Path:
    fig, _ = _pareto_fig(rows, threshold, note)
    return _save(fig, out)


# ------------------------------------------------------------------ tornado

def _tornado_fig(rows: list, left_label: str, right_label: str):
    """Two opposed measures around a centre line, so net direction reads
    without arithmetic. rows: [[label, left_value, right_value]]."""
    peak = max(max(r[1], r[2]) for r in rows) or 1
    fig, ax = plt.subplots(figsize=(FIG_W_RAIL, 4.6))
    y = np.arange(len(rows))[::-1]
    ax.barh(y, [-r[1] for r in rows], height=0.6, color=ORANGE,
            edgecolor="white", linewidth=1.2)
    ax.barh(y, [r[2] for r in rows], height=0.6, color=GREEN,
            edgecolor="white", linewidth=1.2)
    for i, r in enumerate(rows):
        ax.text(-r[1] - peak * 0.02, y[i], f"{r[1]:,}", va="center",
                ha="right", fontsize=TXT, fontweight="bold", color=ORANGE)
        ax.text(r[2] + peak * 0.02, y[i], f"{r[2]:,}", va="center",
                fontsize=TXT, fontweight="bold", color=GREEN)
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=TXT, color=NAVY)
    ax.set_xlim(-peak * 1.35, peak * 1.35)
    ax.axvline(0, color=NAVY, lw=1.4)
    ax.get_xaxis().set_visible(False)
    ax.text(-peak * 1.3, len(rows) - 0.3, left_label.upper(), fontsize=TXT,
            fontweight="bold", color=ORANGE)
    ax.text(peak * 1.3, len(rows) - 0.3, right_label.upper(), ha="right",
            fontsize=TXT, fontweight="bold", color=GREEN)
    _clean(ax, bottom=False)
    nets = [r[2] - r[1] for r in rows]
    return fig, {"rows": len(rows), "nets": nets,
                 "sorted_by_net": nets == sorted(nets, reverse=True)}


def tornado(rows: list, out: Path, left_label: str = "stopped",
            right_label: str = "new") -> Path:
    fig, _ = _tornado_fig(rows, left_label, right_label)
    return _save(fig, out)


# --------------------------------------------------------------- band stack

def _band_stack_fig(rows: list, bands: list, note: str):
    """One 100% bar per row split into n named bands -- a lifecycle across
    many categories without a single number on screen.
    rows: [[label, v1..vn]]; bands: [(name, color), ...]."""
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, 4.6))
    y = np.arange(len(rows))[::-1]
    drawn = 0
    for ri, row in enumerate(rows):
        vals = row[1:1 + len(bands)]
        total = sum(vals) or 1
        left = 0.0
        for (name, color), v in zip(bands, vals):
            share = v / total
            ax.barh(y[ri], share, left=left, height=0.62, color=color,
                    edgecolor="white", linewidth=1.1)
            if share > 0.09:
                ax.text(left + share / 2, y[ri], f"{share * 100:.0f}%",
                        ha="center", va="center", fontsize=TXT,
                        fontweight="bold",
                        color="white" if color in (NAVY, STEEL) else NAVY)
                drawn += 1
            left += share
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=TXT, color=NAVY)
    ax.set_xlim(0, 1)
    ax.get_xaxis().set_visible(False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for _, c in bands]
    ax.legend(handles, [n for n, _ in bands], loc="upper center",
              bbox_to_anchor=(0.5, 1.10), ncol=len(bands), frameon=False,
              fontsize=TXT)
    if note:
        ax.set_xlabel(note, fontsize=TXT, color=GREY, labelpad=8)
    _clean(ax, bottom=False)
    return fig, {"rows": len(rows), "bands": len(bands),
                 "labels_drawn": drawn}


def band_stack(rows: list, bands: list, out: Path, note: str = "") -> Path:
    fig, _ = _band_stack_fig(rows, bands, note)
    return _save(fig, out)


# -------------------------------------------------------------- heat matrix

def _heat_matrix_fig(grid: dict, fmt: str, note: str):
    """Rows x columns on one sequential ramp, blank where nothing was
    measured. Generalises the ICS milestone heat, which hardcodes a 70-95%
    ramp and a percent format. grid: {"rows": [label, ...], "cols": [...],
    "cells": [[v|None, ...], ...]}."""
    rows, cols, cells = grid["rows"], grid["cols"], grid["cells"]
    flat = [v for r in cells for v in r if v is not None]
    lo, hi = (min(flat), max(flat)) if flat else (0, 1)
    height = min(5.0, max(2.6, 0.52 * len(rows) + 1.4))
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, height))
    ax.set_xlim(0, len(cols))
    ax.set_ylim(0, len(rows))
    ax.axis("off")
    cell_fs = TXT
    for ci, c in enumerate(cols):
        import textwrap
        ax.text(ci + 0.5, len(rows) + 0.12, textwrap.fill(str(c), 12, break_long_words=False),
                ha="center", va="bottom", fontsize=TXT,
                fontweight="bold", color=NAVY)
    drawn = blank = 0
    for ri, label in enumerate(rows):
        yy = len(rows) - 1 - ri
        ax.text(-0.12, yy + 0.5, str(label), ha="right", va="center",
                fontsize=TXT, color=GREY)
        for ci in range(len(cols)):
            v = cells[ri][ci] if ci < len(cells[ri]) else None
            if v is None:
                ax.add_patch(plt.Rectangle((ci + 0.03, yy + 0.06), 0.94, 0.88,
                                           facecolor=BLANK,
                                           edgecolor="white"))
                blank += 1
                continue
            t = 0.0 if hi == lo else (v - lo) / (hi - lo)
            color = RAMP[min(int(t * len(RAMP)), len(RAMP) - 1)]
            ax.add_patch(plt.Rectangle((ci + 0.03, yy + 0.06), 0.94, 0.88,
                                       facecolor=color, edgecolor="white"))
            ax.text(ci + 0.5, yy + 0.5, fmt.format(v), ha="center",
                    va="center", fontsize=cell_fs, fontweight="bold",
                    color="white" if t > 0.72 else NAVY)
            drawn += 1
    if note:
        ax.text(0, -0.55, note, fontsize=TXT, color=GREY)
        ax.set_ylim(-0.9, len(rows) + 0.4)
    return fig, {"cells_drawn": drawn, "cells_blank": blank,
                 "rows": len(rows), "cols": len(cols)}


def heat_matrix(grid: dict, out: Path, fmt: str = "{:.0f}%",
                note: str = "") -> Path:
    fig, _ = _heat_matrix_fig(grid, fmt, note)
    return _save(fig, out)


# ---------------------------------------------------------------- diverging
# RPE addition, not in v5 (Sheila's 1798 slide review, 2026-10-30: "diverging bar of top 10 gainers
# and losers window over window").

def _diverging_fig(rows: list, note: str, fmt):
    """Signed changes off a centre line: gains to the right in navy, falls to the left in orange,
    each name on the opposite side of the line from its bar so it never sits on top of it.
    rows: [[label, change, detail]], drawn top to bottom as given."""
    vals = [float(r[1]) for r in rows]
    peak = max((abs(v) for v in vals), default=1) or 1
    fig, ax = plt.subplots(figsize=(FIG_W_RAIL, max(3.2, 0.48 * len(rows) + 1.0)))
    y = np.arange(len(rows))[::-1]
    for i, (label, v, detail) in enumerate(rows):
        v = float(v)
        color = NAVY if v >= 0 else ORANGE
        ax.barh(y[i], v, height=0.62, color=color, edgecolor="white", linewidth=1.2)
        side = 1 if v >= 0 else -1
        ax.text(v + side * peak * 0.03, y[i], fmt(v), va="center",
                ha="left" if side > 0 else "right", fontsize=TXT, fontweight="bold", color=color)
        name = f"{label}  ·  {detail}" if detail else str(label)
        ax.text(-side * peak * 0.03, y[i], name, va="center",
                ha="right" if side > 0 else "left", fontsize=TXT, color=NAVY)
    ax.axvline(0, color=NAVY, lw=1.4)
    ax.set_xlim(-peak * 1.9, peak * 1.9)
    ax.set_ylim(-0.7, len(rows) - 0.3)
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)
    if note:
        ax.set_xlabel(note, fontsize=TXT, color=GREY, labelpad=8)
        ax.get_xaxis().set_visible(True)
        ax.set_xticks([])
    _clean(ax, bottom=False)
    return fig, {"rows": len(rows), "up": sum(1 for v in vals if v >= 0),
                 "down": sum(1 for v in vals if v < 0)}


def diverging_bars(rows: list, out: Path, note: str = "", fmt=None) -> Path:
    def signed(v):
        return ("+" if v >= 0 else "-") + _fmt_money(abs(v))
    fig, _ = _diverging_fig(rows, note, fmt or signed)
    return _save(fig, out)


# --------------------------------------------------------------- kind bars
# RPE addition, not in v5 (Sheila's 1798 slide review, 2026-10-30: split Cash App's flow from the
# financial-product total so $78M never reads as part of the $49.6M).

def _kind_bars_fig(rows: list, kinds: dict, note: str):
    """Dollars per named service, coloured by what kind of flow it is, with a legend naming each
    kind. rows: [[label, dollars, accounts, kind]]; kinds: {kind: (legend text, colour)}."""
    rows = rows[::-1]
    fig, ax = plt.subplots(figsize=(FIG_W_RAIL, max(3.4, 0.5 * len(rows) + 1.3)))
    y = np.arange(len(rows))
    vals = [float(r[1]) for r in rows]
    span = max(vals) if vals else 1
    for i, (label, v, accts, kind) in enumerate(rows):
        color = kinds.get(kind, ("", NAVY))[1]
        ax.barh(y[i], v, height=0.6, color=color, edgecolor="white", linewidth=1.2)
        acc = f"   {accts:,} accounts" if accts is not None else ""
        ax.text(v + span * 0.02, y[i], f"{_fmt_money(v)}{acc}", va="center",
                fontsize=TXT, color=NAVY)
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=TXT, color=NAVY)
    ax.set_xlim(0, span * 1.75)
    ax.get_xaxis().set_visible(False)
    used = [k for k in kinds if any(r[3] == k for r in rows)]
    handles = [plt.Rectangle((0, 0), 1, 1, color=kinds[k][1]) for k in used]
    ax.legend(handles, [kinds[k][0] for k in used], loc="lower right", frameon=False,
              fontsize=TXT)
    if note:
        ax.set_xlabel(note, fontsize=TXT, color=GREY, labelpad=8)
        ax.get_xaxis().set_visible(True)
        ax.set_xticks([])
    _clean(ax, bottom=False)
    return fig, {"rows": len(rows), "kinds": used}


def kind_bars(rows: list, kinds: dict, out: Path, note: str = "") -> Path:
    fig, _ = _kind_bars_fig(rows, kinds, note)
    return _save(fig, out)
