# Ported from v5 02-Scripts/ils/pre_go_live/deck_charts.py at 7ba1e63. Logic unchanged; the one import reads ils_pipeline.deckkit.
"""Charts for the PGL deck, styled through deckkit (matplotlib, Agg)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from ils_pipeline import deckkit as dk


def _barh(rows, out: Path, colors=None, annotate=None, width=11.8, height=5.0):
    """Horizontal count bars from cut() rows: [group, accounts, pct, ...]."""
    rows = rows[::-1]
    labels = [str(r[0])[:26] for r in rows]
    counts = [r[1] for r in rows]
    fig, ax = plt.subplots(figsize=(width, height))
    y = np.arange(len(rows))
    ax.barh(y, counts, color=colors[::-1] if colors else dk.NAVY,
            height=0.62, edgecolor="white", linewidth=1.2)
    span = max(counts) if counts else 1
    for i, r in enumerate(rows):
        note = annotate(r) if annotate else f"{r[1]:,}   {r[2]:.1f}%"
        ax.text(r[1] + span * 0.02, y[i], note, va="center", fontsize=11.5,
                color=dk.NAVY)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=12.5, color=dk.NAVY)
    ax.set_xlim(0, span * 1.55)
    ax.get_xaxis().set_visible(False)
    dk.clean_axes(ax, bottom=False)
    return dk.save_chart(fig, out)


def status_mix(rows, out: Path):
    return _barh(rows[:8], out)


def od_status(rows, out: Path):
    """Eligible codes in navy, the rest grey."""
    colors = [dk.NAVY if r[-1] else dk.GREY for r in rows[:8]]
    return _barh(rows[:8], out, colors=colors,
                 annotate=lambda r: f"{r[1]:,}   {r[2]:.1f}%"
                 + ("   eligible" if r[-1] else ""))


TORNADO_BAR_HEIGHT = 0.58
TORNADO_LABEL_GAP = 0.015      # share of the widest arm between bar end and label
TORNADO_LEFT_ROOM = 1.35       # x-limits as multiples of the widest arm, so the
TORNADO_RIGHT_ROOM = 1.75      # end labels and the "same" column never collide
TORNADO_SAME_COLUMN = 1.72


def draw_score_tornado(ax, headline: dict) -> None:
    """Lower on the left, higher on the right, one row per base.

    Direction is the geometry, so there is no legend; the unchanged count is
    a note at the end of the row rather than a third bar (#191).
    """
    bases = [(k, v) for k, v in headline.items() if v.get("base")]
    y = np.arange(len(bases))
    down = [-v["down"] for _, v in bases]
    up = [v["up"] for _, v in bases]
    span = max([abs(d) for d in down] + up + [1])
    ax.barh(y, down, height=TORNADO_BAR_HEIGHT, color=dk.ORANGE, edgecolor="white")
    ax.barh(y, up, height=TORNADO_BAR_HEIGHT, color=dk.NAVY, edgecolor="white")
    ax.axvline(0, color=dk.NAVY, linewidth=1.4)
    gap = span * TORNADO_LABEL_GAP
    for i, (_, v) in enumerate(bases):
        if v["down"]:
            ax.text(down[i] - gap, y[i], f"{v['down']:,} lower", ha="right",
                    va="center", fontsize=11, color=dk.NAVY)
        if v["up"]:
            ax.text(up[i] + gap, y[i], f"{v['up']:,} higher", ha="left",
                    va="center", fontsize=11, color=dk.NAVY)
        ax.text(span * TORNADO_SAME_COLUMN, y[i], f"{v['same']:,} same",
                ha="right", va="center", fontsize=10.5, color=dk.GREY)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{k}\n({v['base']:,} accts)" for k, v in bases],
                       fontsize=12, color=dk.NAVY)
    ax.invert_yaxis()
    ax.set_xlim(-span * TORNADO_LEFT_ROOM, span * TORNADO_RIGHT_ROOM)
    ax.get_xaxis().set_visible(False)
    dk.clean_axes(ax, bottom=False)


def score_updown(headline: dict, out: Path):
    """The score slide: how many accounts move up or down under ILS, per base."""
    fig, ax = plt.subplots(figsize=(11.8, 4.8))
    draw_score_tornado(ax, headline)
    return dk.save_chart(fig, out)


def rege_trend(rows, out: Path):
    """Opt-in rate line over opened month (or quarter, when sparse),
    volume bars behind."""
    labels = [f"{r[0]}-{r[1]:02d}" if isinstance(r[1], int) else f"{r[0]} {r[1]}"
              for r in rows]
    opened = [r[4] for r in rows]
    rate = [r[5] for r in rows]
    fig, ax = plt.subplots(figsize=(11.8, 4.6))
    ax.bar(labels, opened, color=dk.GREY, alpha=0.35, label="accounts opened")
    ax2 = ax.twinx()
    ax2.plot(labels, rate, color=dk.NAVY, linewidth=2.4, marker="o",
             markersize=4, label="opt-in rate")
    ax2.set_ylim(0, max(rate + [1]) * 1.3)
    ax2.set_ylabel("opt-in %", fontsize=11, color=dk.NAVY)
    ax.tick_params(axis="x", rotation=60, labelsize=9)
    ax.set_ylabel("opened", fontsize=11, color=dk.GREY)
    dk.clean_axes(ax)
    for spine in ("top",):
        ax2.spines[spine].set_visible(False)
    return dk.save_chart(fig, out)


def limit_shift(current, proposed, out: Path, bucket=100):
    """Current core limits vs proposed ILS limits, $-bucketed, side by side."""
    def bucketed(rows):
        agg: dict = {}
        for r in rows:
            try:
                b = int(float(r[0]) // bucket) * bucket
            except (TypeError, ValueError):
                continue
            agg[b] = agg.get(b, 0) + r[1]
        return agg
    cur, prop = bucketed(current), bucketed(proposed)
    keys = sorted(set(cur) | set(prop))
    labels = [f"${k:,}" for k in keys]
    x = np.arange(len(keys))
    fig, ax = plt.subplots(figsize=(11.8, 4.8))
    ax.bar(x - 0.2, [cur.get(k, 0) for k in keys], 0.4, label="current (core)",
           color=dk.GREY, edgecolor="white")
    ax.bar(x + 0.2, [prop.get(k, 0) for k in keys], 0.4, label="proposed (ILS)",
           color=dk.NAVY, edgecolor="white")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10.5, rotation=30)
    ax.legend(frameon=False, fontsize=11)
    ax.get_yaxis().set_visible(False)
    for j, k in enumerate(keys):
        for dx, v in ((-0.2, cur.get(k, 0)), (0.2, prop.get(k, 0))):
            if v:
                ax.text(j + dx, v, f"{v:,}", ha="center", va="bottom",
                        fontsize=9.5, color=dk.NAVY)
    dk.clean_axes(ax)
    return dk.save_chart(fig, out)


def fee_scenarios(baseline: float, tier_rows, out: Path):
    """Baseline vs each tier scenario's modeled revenue."""
    names = ["Current (actual)"] + [r[0] for r in tier_rows]
    vals = [baseline] + [r[1] for r in tier_rows]
    colors = [dk.NAVY] + [dk.ORANGE if r[2] < 0 else dk.GREY for r in tier_rows]
    fig, ax = plt.subplots(figsize=(11.8, 4.8))
    y = np.arange(len(names))[::-1]
    ax.barh(y, vals, color=colors, height=0.6, edgecolor="white")
    span = max(vals) if vals else 1
    for i, (name, v) in enumerate(zip(names, vals)):
        delta = "" if i == 0 else f"   {vals[i] - baseline:+,.0f}"
        ax.text(v + span * 0.015, y[i], f"${v:,.0f}{delta}", va="center",
                fontsize=11.5, color=dk.NAVY)
    ax.set_yticks(y)
    ax.set_yticklabels([n[:30] for n in names], fontsize=12, color=dk.NAVY)
    ax.set_xlim(0, span * 1.45)
    ax.get_xaxis().set_visible(False)
    dk.clean_axes(ax, bottom=False)
    return dk.save_chart(fig, out)


def funnel(stages, out: Path):
    """Eligibility funnel: [label, count] top to bottom."""
    labels = [str(a)[:36] for a, _ in stages][::-1]
    counts = [b for _, b in stages][::-1]
    fig, ax = plt.subplots(figsize=(11.0, 4.6))
    y = np.arange(len(stages))
    colors = [dk.NAVY if i == 0 else dk.GREY for i in range(len(stages))][::-1]
    ax.barh(y, counts, color=colors, height=0.62, edgecolor="white", linewidth=1.2)
    span = max(counts) if counts else 1
    top_n = counts[-1] if counts else 0
    for i, c in enumerate(counts):
        share = f"   {100 * c / top_n:.1f}%" if top_n and i < len(counts) - 1 else ""
        ax.text(c + span * 0.015, y[i], f"{c:,}{share}", va="center",
                fontsize=12, color=dk.NAVY)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=12, color=dk.NAVY)
    ax.set_xlim(0, span * 1.35)
    ax.get_xaxis().set_visible(False)
    dk.clean_axes(ax, bottom=False)
    return dk.save_chart(fig, out)
