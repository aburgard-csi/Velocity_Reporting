#!/usr/bin/env python3
"""
ti_charts.py — the one chart form the Transaction Intelligence chapter uses: ranked
horizontal bars, drawn to the slide's picture box (never bbox "tight"), in the brand
palette. The name carries "chart" because tests/test_chart_colors.py reads every such
module for its palette. Conventions are insight_charts': `_fig`, `_spines`, `_save`.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(_HERE, os.pardir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from insight_charts import _fig, _spines, _save, _money        # noqa: E402
from brand import NAVY, ORANGE, TICK, GRID                       # noqa: E402

MAX_BARS = 10


def ranked_bars(out, rows, kind="money", w_in=8.7, h_in=4.1, highlight_first=True):
    """rows: [(label, value), ...] already ranked. kind: 'money' | 'pct' | 'count'."""
    rows = [(str(l)[:28], float(v or 0)) for l, v in rows][:MAX_BARS]
    fig, ax = _fig(w_in, h_in)
    labels = [r[0] for r in rows][::-1]
    values = [r[1] for r in rows][::-1]
    colors = [NAVY] * len(values)
    if highlight_first and values:
        colors[-1] = ORANGE
    ax.barh(range(len(values)), values, color=colors, height=0.62)
    ax.set_yticks(range(len(values)))
    ax.set_yticklabels(labels, fontsize=10, color=TICK)
    ax.xaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    fmt = {"money": _money, "pct": lambda v: f"{v:.1f}%", "count": lambda v: f"{v:,.0f}"}[kind]
    span = max(values) if values else 1.0
    for i, v in enumerate(values):
        ax.text(v + span * 0.01, i, fmt(v), va="center", fontsize=9, color=TICK)
    ax.set_xlim(0, span * 1.18 if span else 1)
    ax.set_xticks([])
    _spines(ax)
    fig.subplots_adjust(left=0.30, right=0.98, top=0.97, bottom=0.05)
    return _save(fig, out)
