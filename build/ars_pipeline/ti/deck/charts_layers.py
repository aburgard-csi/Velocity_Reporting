"""
charts_layers.py — the figures of the Competition layers slides, drawn in the cut's chart layer
(`ti/deck/charts.py`: brand palette, type floor, `_save`). New to RPE; not a v5 port.

Every function takes its rows first and the output path second, as the chart layer's forms do, and returns the
path. A tier keeps one colour on every slide, so a reader finds Local or National by colour alone.
"""
from __future__ import annotations

import math

import numpy as np
from matplotlib import patheffects as _pe

from .charts import (FIG_H_FULL, FIG_H_RAIL, FIG_W_FULL, FIG_W_RAIL, GOLD, GREEN, GREY, LINE, NAVY, ORANGE, STEEL,
                     TINT, _save, plt)

TIER_COLOR = {"National": NAVY, "Digital": GREEN, "Local": ORANGE, "Local (25-50 mi)": "#F6A98A",
              "Regional (district)": GOLD, "State": STEEL, "Other (outside district)": GREY,
              "Card-issuing banks (review)": "#8E6BBF", "Unresolved (ambiguous)": LINE}
GROUP_COLOR = {"responders": NAVY, "mailed_nonresp": GOLD, "mailed_nonresp_nu1_4": "#F6A98A",
               "mailed_nonresp_none": ORANGE, "not_mailed": GREEN, "ics": NAVY, "ics_dm": GREEN, "ics_ref": GOLD,
               "not_ics": GREY}


_CASED = [_pe.withStroke(linewidth=3, foreground="white")]      # navy core + white stroke: a label reads on a bar and on the canvas


def tier_color(t):
    return TIER_COLOR.get(t, GREY)


def _frame(ax, grid="x"):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(LINE)
    ax.tick_params(length=0, colors=NAVY)
    ax.grid(axis=grid, color=LINE, lw=0.8, zorder=0)
    ax.set_axisbelow(True)


def hbar(rows: list, out, xlabel="", fmt="{:,.0f}", full=False):
    """Horizontal bars, one colour each: [[label, value, color or tier], ...] in the order drawn, top first."""
    rows = [r for r in rows if r[1] is not None]
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, FIG_H_FULL) if full else (FIG_W_RAIL, FIG_H_RAIL))
    ys = np.arange(len(rows))[::-1]
    vals = [float(r[1]) for r in rows]
    ax.barh(ys, vals, color=[tier_color(r[2]) if len(r) > 2 and r[2] in TIER_COLOR else (r[2] if len(r) > 2 else NAVY)
                             for r in rows], height=0.7, zorder=2)
    top = max(vals) if vals else 1
    for y, v in zip(ys, vals):
        ax.text(v + top * 0.012, y, fmt.format(v), va="center", ha="left", color=NAVY)
    ax.set_yticks(ys)
    ax.set_yticklabels([str(r[0]) for r in rows])
    ax.set_xlim(0, top * 1.16)
    ax.set_xlabel(xlabel, color=GREY)
    _frame(ax)
    ax.xaxis.set_visible(False)
    return _save(fig, out)


def hbar_stacked(labels: list, series: dict, out, colors: dict, fmt="{:,.0f}", full=False, label_min=0.0):
    """Stacked horizontal bars: labels top first; series {name: [values]}; negative values draw left of zero."""
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, FIG_H_FULL) if full else (FIG_W_RAIL, FIG_H_RAIL))
    ys = np.arange(len(labels))[::-1]
    pos, neg = np.zeros(len(labels)), np.zeros(len(labels))
    for name, vals in series.items():
        v = np.array([0.0 if x is None else float(x) for x in vals])
        left = np.where(v >= 0, pos, neg)
        ax.barh(ys, v, left=left, color=colors.get(name, STEEL), height=0.7, label=name, zorder=2)
        for y, a, b in zip(ys, v, left):
            if abs(a) >= max(label_min, 1e-9) and abs(a) > 0:
                ax.text(b + a / 2, y, fmt.format(abs(a)), ha="center", va="center", color=NAVY, fontsize=11, path_effects=_CASED)
        pos = np.where(v >= 0, pos + v, pos)
        neg = np.where(v < 0, neg + v, neg)
    ax.axvline(0, color=NAVY, lw=1)
    ax.set_yticks(ys)
    ax.set_yticklabels(labels)
    _frame(ax)
    ax.xaxis.set_visible(False)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.16), ncol=len(series), frameon=False)
    return _save(fig, out)


def columns(labels: list, series: dict, out, colors: dict, stacked=False, fmt="{:,.0f}", ylabel="", full=True):
    """Vertical columns, clustered or stacked: labels along the axis; series {name: [values]}."""
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, FIG_H_FULL) if full else (FIG_W_RAIL, FIG_H_RAIL))
    n, k = len(labels), len(series)
    x = np.arange(n)
    w = 0.74 if stacked else 0.8 / max(k, 1)
    bottom = np.zeros(n)
    for i, (name, vals) in enumerate(series.items()):
        v = np.array([0.0 if q is None else float(q) for q in vals])
        xs = x if stacked else x - 0.4 + w * (i + 0.5)
        ax.bar(xs, v, w, bottom=bottom if stacked else None, color=colors.get(name, STEEL), label=name, zorder=2)
        if not stacked:
            for xx, q in zip(xs, v):
                if q:
                    ax.text(xx, q, fmt.format(q), ha="center", va="bottom", fontsize=10, color=NAVY)
        if stacked:
            bottom = bottom + v
    ax.set_xticks(x)
    ax.set_xticklabels([str(s) for s in labels])
    ax.set_ylabel(ylabel, color=GREY)
    _frame(ax, "y")
    if k > 1:
        ax.legend(loc="upper right", frameon=False, ncol=min(k, 4))
    return _save(fig, out)


def lines(months: list, series: dict, out, colors: dict, fmt="{:,.0f}", ylabel=""):
    """One line per series over the months: series {name: [values]}; months as 'YYYY-MM'."""
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, FIG_H_FULL))
    x = np.arange(len(months))
    for name, vals in series.items():
        ax.plot(x, [np.nan if v is None else v for v in vals], marker="o", lw=2.6, ms=5, color=colors.get(name, STEEL), label=name, zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels(_month_labels(months))
    ax.set_ylabel(ylabel, color=GREY)
    _frame(ax, "y")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=min(len(series), 3), frameon=False)
    return _save(fig, out)


def _month_labels(months):
    names = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    out = []
    for m in months:
        y, mo = str(m).split("-")
        out.append(f"{names[int(mo) - 1]}'{y[2:]}")
    return out


def heat(rows: list, cols: list, out, fmt="{:.1f}%"):
    """A colour-scaled table: rows [[label, v1, v2, ...]]; cols the column names after the label."""
    labels = [r[0] for r in rows]
    mat = np.array([[np.nan if v is None else float(v) for v in r[1:]] for r in rows])
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, FIG_H_FULL))
    top = float(np.nanmax(mat)) if mat.size else 1
    ax.imshow(np.nan_to_num(mat), cmap="Oranges", aspect="auto", vmin=0, vmax=max(top, 1e-9))
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(cols)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            if not np.isnan(mat[i, j]):
                ax.text(j, i, fmt.format(mat[i, j]), ha="center", va="center", color=NAVY, path_effects=_CASED)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0, colors=NAVY)
    return _save(fig, out)


def bubble(rows: list, out, xlabel="", ylabel="", color=ORANGE, label_top=7):
    """[[label, x, y, size], ...]: across = x, up = y, area = size; the biggest few are named."""
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, FIG_H_FULL))
    xs, ys = [float(r[1]) for r in rows], [float(r[2]) for r in rows]
    big = max((float(r[3]) for r in rows), default=1.0) or 1.0
    sizes = [max(40.0, float(r[3]) / big * 700) for r in rows]
    ax.scatter(xs, ys, s=sizes, color=color, alpha=0.65, edgecolor="white", zorder=3)
    for i in sorted(range(len(rows)), key=lambda q: -float(rows[q][3]))[:label_top]:
        # the label starts at the bubble's edge, and the chart layer is told which bubble it belongs to
        note = ax.annotate(str(rows[i][0]), (xs[i], ys[i]), xytext=(sizes[i] ** 0.5 / 2 + 5, 0), textcoords="offset points",
                           va="center", color=NAVY)
        note._ars_bubble = i
    ax.set_xlabel(xlabel, color=GREY)
    ax.set_ylabel(ylabel, color=GREY)
    ax.margins(0.12)
    _frame(ax, "both")
    return _save(fig, out)


def donut_tiers(rows: list, out, center_value="", center_label=""):
    """Tier shares of the dollars: [[tier, value], ...]; each tier in its own colour, small ones grouped by the caller."""
    rows = [r for r in rows if r[1] and r[1] > 0]
    fig, ax = plt.subplots(figsize=(FIG_W_RAIL, FIG_H_RAIL))
    total = sum(r[1] for r in rows) or 1
    wedges, _ = ax.pie([r[1] for r in rows], colors=[tier_color(r[0]) for r in rows], startangle=90, counterclock=False,
                       wedgeprops={"width": 0.42, "edgecolor": "white", "linewidth": 2})
    for w, r in zip(wedges, rows):
        share = r[1] / total
        if share < 0.04:
            continue
        ang = math.radians((w.theta1 + w.theta2) / 2)
        ax.text(math.cos(ang) * 0.79, math.sin(ang) * 0.79, f"{share:.0%}", ha="center", va="center", color=NAVY, fontsize=13, fontweight="bold", path_effects=_CASED)
    ax.legend(wedges, [r[0] for r in rows], loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False)
    if center_value:
        ax.text(0, 0.1, center_value, ha="center", va="center", fontsize=24, fontweight="bold", color=NAVY)
    if center_label:
        ax.text(0, -0.18, center_label, ha="center", va="center", fontsize=12, color=GREY)
    ax.set(aspect="equal")
    return _save(fig, out)


def branch_map(figures: dict, out, client_label="client branches"):
    """The client's branches (stars) and every competitor branch within the local radius, coloured by tier when
    the institution appears in the card spending, grey when it does not. Rings at 5, 10 and the radius."""
    pts, near, radius = figures["client"], figures["branches"], figures["radius"]
    la = float(np.mean([p[0] for p in pts]))
    lo = float(np.mean([p[1] for p in pts]))
    k = math.cos(math.radians(la))
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, FIG_H_FULL))
    th = np.linspace(0, 2 * math.pi, 200)
    for r in sorted({5.0, 10.0, float(radius)}):
        ax.plot(lo + (r / 69.0 / k) * np.cos(th), la + (r / 69.0) * np.sin(th), color=LINE, lw=1, ls="--", zorder=1)
        ax.text(lo + (r / 69.0 / k) * 0.71, la + (r / 69.0) * 0.71, f"{r:g} mi", color=GREY, fontsize=11)
    unseen = [b for b in near if not b[3]]
    ax.scatter([b[1] for b in unseen], [b[0] for b in unseen], s=26, color=LINE, zorder=2,
               label=f"Not seen in card spending ({len(unseen)})")
    for t in TIER_COLOR:
        g = [b for b in near if b[3] == t]
        if g:
            ax.scatter([b[1] for b in g], [b[0] for b in g], s=54, color=tier_color(t), edgecolor="white", linewidth=0.6, zorder=3, label=f"{t} ({len(g)})")
    ax.scatter([p[1] for p in pts], [p[0] for p in pts], s=260, marker="*", color=NAVY, edgecolor="white", linewidth=0.8, zorder=4,
               label=f"{len(pts)} {client_label}")
    ax.set_aspect(1 / k)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False)
    return _save(fig, out)
