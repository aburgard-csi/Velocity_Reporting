# Ported from v5 02-Scripts/ars/deck/charts_txn.py at 7ba1e63. Logic unchanged; no edits. Here only because the kickoff deck's deckkit facade imports it (v5 layout kept below kickoff/_v5/ so its relative imports hold).
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


def _fmt_money(v) -> str:
    v = float(v)
    if abs(v) >= 1_000_000:
        return f"${v / 1_000_000:.1f}M"
    if abs(v) >= 1_000:
        return f"${v / 1_000:.0f}K"
    return f"${v:,.0f}"


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
        h = (hs / tallest) * 0.86
        lit = hs > ws * 1.15          # carries more money than volume
        color = ORANGE if lit else (NAVY if i % 2 == 0 else STEEL)
        ax.add_patch(plt.Rectangle((x, 0.10), w, h, facecolor=color,
                                   edgecolor="white", linewidth=1.4))
        cx = min(max(x + w / 2, 0.045), 0.955)
        ax.text(cx, 0.10 + h + 0.022, f"{hs * 100:.0f}% {height_label}",
                ha="center", fontsize=11.5, fontweight="bold",
                color=ORANGE if lit else NAVY)
        ax.text(cx, 0.062, label, ha="center", fontsize=12,
                fontweight="bold", color=NAVY)
        ax.text(cx, 0.018, f"{ws * 100:.0f}% {width_label}", ha="center",
                fontsize=10, color=GREY)
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
    ax.set_xticks(xs)
    ax.set_xticklabels([r[0] for r in rows], fontsize=10, color=NAVY,
                       rotation=30, ha="right")
    ax.set_ylim(0, max(vals) * 1.30)
    ax.get_yaxis().set_visible(False)
    for x, v in zip(xs, vals):
        ax.text(x, v + max(vals) * 0.03, _fmt_money(v), ha="center",
                fontsize=10, fontweight="bold", color=NAVY)

    cum = np.cumsum(vals) / total
    ax2 = ax.twinx()
    ax2.plot(xs, cum, color=NAVY, lw=2.6, marker="o", ms=5,
             markerfacecolor="white", markeredgewidth=2, markeredgecolor=NAVY)
    ax2.set_ylim(0, 1.30)
    ax2.get_yaxis().set_visible(False)
    ax2.axhline(threshold, color=ORANGE, lw=1.5, ls="--")
    ax2.text(len(rows) - 0.4, threshold + 0.03,
             f"{threshold * 100:.0f}% of the dollars", ha="right",
             fontsize=10.5, fontweight="bold", color=ORANGE)
    for s in ("top", "right", "left"):
        ax2.spines[s].set_visible(False)
    _clean(ax)
    if note:
        ax.set_xlabel(note, fontsize=10, color=GREY, labelpad=10)
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
                ha="right", fontsize=10.5, fontweight="bold", color=ORANGE)
        ax.text(r[2] + peak * 0.02, y[i], f"{r[2]:,}", va="center",
                fontsize=10.5, fontweight="bold", color=GREEN)
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=11, color=NAVY)
    ax.set_xlim(-peak * 1.35, peak * 1.35)
    ax.axvline(0, color=NAVY, lw=1.4)
    ax.get_xaxis().set_visible(False)
    ax.text(-peak * 1.3, len(rows) - 0.3, left_label.upper(), fontsize=10,
            fontweight="bold", color=ORANGE)
    ax.text(peak * 1.3, len(rows) - 0.3, right_label.upper(), ha="right",
            fontsize=10, fontweight="bold", color=GREEN)
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
            if share > 0.075:
                ax.text(left + share / 2, y[ri], f"{share * 100:.0f}%",
                        ha="center", va="center", fontsize=9.5,
                        fontweight="bold",
                        color="white" if color in (NAVY, STEEL) else NAVY)
                drawn += 1
            left += share
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=11, color=NAVY)
    ax.set_xlim(0, 1)
    ax.get_xaxis().set_visible(False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for _, c in bands]
    ax.legend(handles, [n for n, _ in bands], loc="upper center",
              bbox_to_anchor=(0.5, 1.10), ncol=len(bands), frameon=False,
              fontsize=10.5)
    if note:
        ax.set_xlabel(note, fontsize=10, color=GREY, labelpad=8)
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
    cell_fs = 9.5 if len(cols) <= 8 else 8
    for ci, c in enumerate(cols):
        ax.text(ci + 0.5, len(rows) + 0.12, str(c), ha="center", fontsize=10,
                fontweight="bold", color=NAVY)
    drawn = blank = 0
    for ri, label in enumerate(rows):
        yy = len(rows) - 1 - ri
        ax.text(-0.12, yy + 0.5, str(label), ha="right", va="center",
                fontsize=10.5, color=GREY)
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
        ax.text(0, -0.55, note, fontsize=9.5, color=GREY)
        ax.set_ylim(-0.9, len(rows) + 0.4)
    return fig, {"cells_drawn": drawn, "cells_blank": blank,
                 "rows": len(rows), "cols": len(cols)}


def heat_matrix(grid: dict, out: Path, fmt: str = "{:.0f}%",
                note: str = "") -> Path:
    fig, _ = _heat_matrix_fig(grid, fmt, note)
    return _save(fig, out)
