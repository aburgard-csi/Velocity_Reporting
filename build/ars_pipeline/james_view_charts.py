#!/usr/bin/env python3
"""
james_view_charts.py — renderers for the second round of James views (james_views.py).

OPT-IN with the rest of the James views (RPE_JAMES_SLIDES=1). Same house rules as
insight_charts: brand.py palette, Carlito through rpe_env.use_font, month labels through
periods.axis_months with the month-axis guard installed, each chart drawn at the aspect of the
picture box its slide gives it, and no mark in the canvas colour (tests/test_chart_colors.py
reads this file because its name carries "chart").
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, os.pardir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import matplotlib                                                        # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                          # noqa: E402

from brand import (NAVY, ORANGE, TICK, MUTED, GRID, TEAL, STEEL,        # noqa: E402
                   CHART_FONT, ROWALT)
import periods                                                           # noqa: E402
from rpe_env import use_font                                             # noqa: E402

periods.install_month_axis_guard()
DPI = 200


def _fig(w_in, h_in):
    use_font(CHART_FONT)
    return plt.subplots(figsize=(w_in, h_in))


def _spines(ax, left=False):
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.spines["left"].set_visible(left)
    if left:
        ax.spines["left"].set_color(MUTED)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=TICK, length=0)


def _save(fig, out):
    fig.savefig(out, dpi=DPI, facecolor="white")
    plt.close(fig)
    return out


def _money(v):
    a = abs(v)
    s = f"${a/1e6:.1f}M" if a >= 1e6 else (f"${a/1e3:.0f}K" if a >= 1e3 else f"${a:,.0f}")
    return ("−" if v < 0 else "") + s


def _month_ticks(ax, labels, fs=10.5):
    ax.set_xticks(list(range(len(labels))))
    ax.set_xticklabels(periods.axis_months(labels), rotation=periods.AXIS_ROTATION,
                       ha=periods.AXIS_HA, fontsize=fs, color=NAVY)


def _hbars(ax, labels, vals, fmt, color=NAVY, fs=11.5):
    y = list(range(len(vals)))[::-1]
    ax.barh(y, vals, color=color, height=0.62, zorder=3)
    top = (max(vals) if vals and max(vals) > 0 else 1) * 1.28
    for yi, v in zip(y, vals):
        ax.text(v + top * 0.015, yi, fmt(v), va="center", ha="left", fontsize=fs,
                color=NAVY, fontweight="bold")
    ax.set_xlim(0, top)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=fs, color=NAVY)
    ax.get_xaxis().set_visible(False)
    _spines(ax)
    ax.spines["bottom"].set_visible(False)


# ----------------------------------------------------------------- Reg E over time
def rege_trend_chart(out, rt, w_in=8.0, h_in=4.0):
    """Opt-in share of personal card holders' elections, month by month."""
    s = rt["series"]
    fig, ax = _fig(w_in, h_in)
    fig.subplots_adjust(left=0.10, right=0.97, top=0.92, bottom=0.20)
    x = list(range(len(s)))
    v = [p["in_pct"] for p in s]
    ax.plot(x, v, color=TEAL, lw=2.6, marker="o", ms=4, mfc="white", mec=TEAL, mew=1.6, zorder=5)
    lo, hi = min(v), max(v)
    pad = max(2.0, (hi - lo) * 0.5)
    ax.set_ylim(max(0, lo - pad), min(100, hi + pad))
    ax.yaxis.set_major_formatter(lambda t, _p: f"{t:.0f}%")
    ax.set_ylabel("Opted in, share of elections", fontsize=11.5, color=TICK)
    for i in (0, len(v) - 1):
        ax.annotate(f"{v[i]:.1f}%", (x[i], v[i]), textcoords="offset points", xytext=(0, 9),
                    ha="center", fontsize=11, color=NAVY, fontweight="bold")
    _month_ticks(ax, [p["month"] for p in s])
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    _spines(ax, left=True)
    return _save(fig, out)


# ----------------------------------------------------------------- response by offer number
def offer_number_chart(out, rows, w_in=8.0, h_in=4.0):
    """Response rate by the account's offer number: 1st offer, 2nd, ... 5th and later."""
    fig, ax = _fig(w_in, h_in)
    fig.subplots_adjust(left=0.10, right=0.97, top=0.90, bottom=0.17)
    x = list(range(len(rows)))
    vals = [r["rate"] or 0 for r in rows]
    ax.bar(x, vals, width=0.62, color=[ORANGE if i == 0 else NAVY for i in x], zorder=3)
    for i, v in zip(x, vals):
        ax.text(i, v + max(vals) * 0.02, f"{v:.1f}%", ha="center", va="bottom", fontsize=12,
                color=NAVY, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([f"Offer {r['n']}" for r in rows], fontsize=11.5, color=NAVY)
    ax.set_ylim(0, max(vals) * 1.2 if vals and max(vals) else 1)
    ax.yaxis.set_major_formatter(lambda t, _p: f"{t:.0f}%")
    ax.set_ylabel("Met the goal", fontsize=11.5, color=TICK)
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    _spines(ax, left=True)
    return _save(fig, out)


# ----------------------------------------------------------------- activation
def activation_chart(out, act, w_in=8.0, h_in=4.0):
    labels = ["New accounts", "Existing, mailed first", "Existing, on their own"]
    vals = [act["new"], act["mailed"], act["organic"]]
    fig, ax = _fig(w_in, h_in)
    fig.subplots_adjust(left=0.30, right=0.97, top=0.92, bottom=0.08)
    y = list(range(len(vals)))[::-1]
    colors = [STEEL, ORANGE, NAVY]
    ax.barh(y, vals, color=colors, height=0.6, zorder=3)
    top = (max(vals) or 1) * 1.25
    for yi, v in zip(y, vals):
        ax.text(v + top * 0.015, yi, f"{v:,}", va="center", ha="left", fontsize=12.5,
                color=NAVY, fontweight="bold")
    ax.set_xlim(0, top)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=12, color=NAVY)
    ax.get_xaxis().set_visible(False)
    _spines(ax)
    ax.spines["bottom"].set_visible(False)
    return _save(fig, out)


# ----------------------------------------------------------------- tier movement by group
def movement_chart(out, groups, w_in=8.0, h_in=4.0):
    """100% bars per response group: moved up a tier, held, dropped."""
    groups = [g for g in groups if g["accounts"]]
    fig, ax = _fig(w_in, h_in)
    fig.subplots_adjust(left=0.27, right=0.97, top=0.84, bottom=0.08)
    y = list(range(len(groups)))[::-1]
    left = [0.0] * len(groups)
    for key, color, name in (("up", ORANGE, "Moved up"), ("same", ROWALT, "Held"),
                             ("down", NAVY, "Dropped")):
        vals = [g[key] or 0 for g in groups]
        ax.barh(y, vals, left=left, color=color, height=0.6, zorder=3, label=name,
                edgecolor="white", linewidth=1.0)
        for yi, l0, v in zip(y, left, vals):
            if v >= 7:
                ax.text(l0 + v / 2, yi, f"{v:.0f}%", ha="center", va="center", fontsize=11.5,
                        color=NAVY if color == ROWALT else "#FFFFFF", fontweight="bold")
        left = [a + b for a, b in zip(left, vals)]
    ax.set_xlim(0, 100)
    ax.set_yticks(y)
    ax.set_yticklabels([g["group"] for g in groups], fontsize=12, color=NAVY)
    ax.get_xaxis().set_visible(False)
    _spines(ax)
    ax.spines["bottom"].set_visible(False)
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, 1.16), ncol=3, frameon=False,
              fontsize=11.5, labelcolor=TICK)
    return _save(fig, out)


# ----------------------------------------------------------------- per-mailing control
def per_mailing_chart(out, rows, w_in=12.3, h_in=3.6):
    rows = [r for r in rows if not r["thin"]]
    fig, ax = _fig(w_in, h_in)
    fig.subplots_adjust(left=0.07, right=0.99, top=0.88, bottom=0.22)
    x = list(range(len(rows)))
    w = 0.38
    ax.bar([i - w / 2 for i in x], [r["r_change"] for r in rows], width=w, color=ORANGE,
           label="Responders", zorder=3)
    ax.bar([i + w / 2 for i in x], [r["c_change"] for r in rows], width=w, color=STEEL,
           label="Mailed non-responders", zorder=3)
    ax.axhline(0, color=TICK, lw=1.0, zorder=4)
    for i, r in enumerate(rows):
        ax.text(i - w / 2, r["r_change"], f"+${r['r_change']:,}" if r["r_change"] >= 0
                else f"−${abs(r['r_change']):,}", ha="center", va="bottom", fontsize=9.5,
                color=NAVY)
    _month_ticks(ax, [r["m"] for r in rows], fs=10.5)
    ax.set_ylabel("Change in monthly spend", fontsize=11.5, color=TICK)
    ax.yaxis.set_major_formatter(lambda v, _p: ("−" if v < 0 else "") + _money(abs(v)))
    vals = [v for r in rows for v in (r["r_change"], r["c_change"])]
    ax.set_ylim(min(0, min(vals)) * 1.3 - 10, max(vals) * 1.18)
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    _spines(ax, left=True)
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, 1.16), ncol=2, frameon=False,
              fontsize=11.5, labelcolor=TICK)
    return _save(fig, out)


# ----------------------------------------------------------------- cumulative reach
def reach_chart(out, series, w_in=8.0, h_in=4.0):
    fig, ax = _fig(w_in, h_in)
    fig.subplots_adjust(left=0.11, right=0.97, top=0.88, bottom=0.20)
    x = list(range(len(series)))
    ax.bar(x, [s["reached"] for s in series], width=0.64, color=ROWALT, zorder=2,
           label="Offered, cumulative")
    ax.plot(x, [s["responded"] for s in series], color=TEAL, lw=2.6, marker="o", ms=4,
            mfc="white", mec=TEAL, mew=1.6, zorder=5, label="Met a goal, cumulative")
    _month_ticks(ax, [s["m"] for s in series])
    ax.yaxis.set_major_formatter(lambda v, _p: f"{v/1000:,.0f}K" if v >= 1000 else f"{v:,.0f}")
    ax.set_ylabel("Unique accounts", fontsize=11.5, color=TICK)
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    _spines(ax, left=True)
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, 1.14), ncol=2, frameon=False,
              fontsize=11.5, labelcolor=TICK)
    return _save(fig, out)


# ----------------------------------------------------------------- months of warning
def warning_chart(out, mw, w_in=8.0, h_in=4.0):
    curve = sorted(mw["curve"], key=lambda p: -p["k"])
    fig, ax = _fig(w_in, h_in)
    fig.subplots_adjust(left=0.11, right=0.97, top=0.88, bottom=0.16)
    x = [-p["k"] for p in curve]
    ax.plot(x, [p["open"] for p in curve], color=NAVY, lw=2.2, zorder=4,
            label="Still-open card holders, same months")
    ax.plot(x, [p["closers"] for p in curve], color=ORANGE, lw=2.6, marker="o", ms=4,
            mfc="white", mec=ORANGE, mew=1.6, zorder=5, label="Accounts that closed")
    ax.set_xticks(x)
    ax.set_xticklabels([str(v) for v in x], fontsize=10.5, color=NAVY)
    ax.set_xlabel("Months before the close", fontsize=11.5, color=TICK)
    ax.yaxis.set_major_formatter(lambda v, _p: _money(v))
    ax.set_ylabel("Card spend a month", fontsize=11.5, color=TICK)
    ax.set_ylim(0, max(max(p["open"] for p in curve), max(p["closers"] for p in curve)) * 1.2)
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    _spines(ax, left=True)
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, 1.14), ncol=2, frameon=False,
              fontsize=11, labelcolor=TICK)
    return _save(fig, out)


# ----------------------------------------------------------------- stressors
def stress_chart(out, st, w_in=8.0, h_in=4.0):
    rows = st["by_count"]
    fig, ax = _fig(w_in, h_in)
    fig.subplots_adjust(left=0.10, right=0.97, top=0.90, bottom=0.16)
    x = list(range(len(rows)))
    vals = [r["accounts"] for r in rows]
    ax.bar(x, vals, width=0.6, color=[STEEL, NAVY, ORANGE, ORANGE][:len(rows)], zorder=3)
    for i, r in zip(x, rows):
        ax.text(i, r["accounts"] + max(vals) * 0.02, f"{r['accounts']:,}\n{r['pct']:.1f}%",
                ha="center", va="bottom", fontsize=11, color=NAVY, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{r['n']} condition{'s' if r['n'] != 1 else ''}" for r in rows],
                       fontsize=11.5, color=NAVY)
    ax.set_ylim(0, max(vals) * 1.3)
    ax.yaxis.set_major_formatter(lambda v, _p: f"{v/1000:,.0f}K" if v >= 1000 else f"{v:,.0f}")
    ax.set_ylabel("Open eligible accounts", fontsize=11.5, color=TICK)
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    _spines(ax, left=True)
    return _save(fig, out)


# ----------------------------------------------------------------- value ladder
def ladder_chart(out, ladder, w_in=8.0, h_in=4.0):
    """Annual value per eligible account by tenure, split interchange / NSF/OD fees."""
    fig, ax = _fig(w_in, h_in)
    fig.subplots_adjust(left=0.10, right=0.97, top=0.86, bottom=0.17)
    x = list(range(len(ladder)))
    ic = [r["interchange"] or 0 for r in ladder]
    fee = [r["fees"] or 0 for r in ladder]
    ax.bar(x, ic, width=0.6, color=NAVY, zorder=3, label="Interchange")
    ax.bar(x, fee, width=0.6, bottom=ic, color=ORANGE, zorder=3, label="NSF/OD fees")
    for i, (a, b) in enumerate(zip(ic, fee)):
        ax.text(i, a + b + max(t + u for t, u in zip(ic, fee)) * 0.02, f"${a + b:,}",
                ha="center", va="bottom", fontsize=11.5, color=NAVY, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([r["group"] for r in ladder], fontsize=10.5, color=NAVY)
    ax.set_ylim(0, max(t + u for t, u in zip(ic, fee)) * 1.22)
    ax.yaxis.set_major_formatter(lambda v, _p: f"${v:,.0f}")
    ax.set_ylabel("A year, per eligible account", fontsize=11.5, color=TICK)
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    _spines(ax, left=True)
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, 1.15), ncol=2, frameon=False,
              fontsize=11.5, labelcolor=TICK)
    return _save(fig, out)


# ----------------------------------------------------------------- revenue per fee dollar
def pnl_chart(out, rows, w_in=12.3, h_in=3.5):
    fig, ax = _fig(w_in, h_in)
    fig.subplots_adjust(left=0.07, right=0.99, top=0.93, bottom=0.27)
    rows = [r for r in rows if r["per_fee_dollar"] is not None]
    x = list(range(len(rows)))
    vals = [r["per_fee_dollar"] for r in rows]
    med = sorted(vals)[len(vals) // 2] if vals else 0
    ax.bar(x, vals, width=0.66, color=[ORANGE if v >= med else NAVY for v in vals], zorder=2)
    ax.axhline(2.0, color=TICK, lw=1.2, ls=(0, (3, 3)), zorder=4)
    ax.text(len(x) - 0.4, 2.0, "  2 : 1", va="center", ha="left", fontsize=11, color=TICK)
    _month_ticks(ax, [r["m"] for r in rows], fs=9.5)
    ax.set_ylim(0, max(vals + [2.2]) * 1.15)
    ax.yaxis.set_major_formatter(lambda v, _p: f"${v:,.0f}")
    ax.set_ylabel("Booked per fee dollar", fontsize=11.5, color=TICK)
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    _spines(ax, left=True)
    return _save(fig, out)


# ----------------------------------------------------------------- cascade
def cascade_chart(out, steps, w_in=8.0, h_in=4.0):
    labels = [s[0] for s in steps]
    vals = [s[1] for s in steps]
    fig, ax = _fig(w_in, h_in)
    fig.subplots_adjust(left=0.40, right=0.97, top=0.95, bottom=0.05)
    _hbars(ax, labels, vals, lambda v: f"{v:,}", color=NAVY, fs=11.5)
    return _save(fig, out)


# ----------------------------------------------------------------- merchant groups
def spend_mix_chart(out, groups, w_in=8.0, h_in=4.0, n=10):
    """Share of card spend and of card transactions by merchant group."""
    groups = groups[:n]
    fig, ax = _fig(w_in, h_in)
    fig.subplots_adjust(left=0.30, right=0.97, top=0.88, bottom=0.06)
    y = list(range(len(groups)))[::-1]
    h = 0.38
    ax.barh([v + h / 2 for v in y], [g["share_spend"] for g in groups], height=h, color=NAVY,
            zorder=3, label="Share of card spend")
    ax.barh([v - h / 2 for v in y], [g["share_txns"] for g in groups], height=h, color=ORANGE,
            zorder=3, label="Share of card transactions")
    top = max(max(g["share_spend"] for g in groups), max(g["share_txns"] for g in groups)) * 1.22
    for v, gg in zip(y, groups):
        ax.text(gg["share_spend"] + top * 0.01, v + h / 2, f"{gg['share_spend']:.0f}%",
                va="center", fontsize=9.5, color=NAVY)
        ax.text(gg["share_txns"] + top * 0.01, v - h / 2, f"{gg['share_txns']:.0f}%",
                va="center", fontsize=9.5, color=NAVY)
    ax.set_xlim(0, top)
    ax.set_yticks(y)
    ax.set_yticklabels([g["group"] for g in groups], fontsize=11, color=NAVY)
    ax.get_xaxis().set_visible(False)
    _spines(ax)
    ax.spines["bottom"].set_visible(False)
    ax.legend(loc="upper left", bbox_to_anchor=(-0.02, 1.14), ncol=2, frameon=False,
              fontsize=11, labelcolor=TICK)
    return _save(fig, out)


# ----------------------------------------------------------------- how the money moves
RAIL_NAMES = {"SIG": "Card, signature", "PIN": "Card, PIN", "ACH": "ACH", "CHK": "Check"}


def rails_chart(out, rails, w_in=8.0, h_in=4.0):
    keys = sorted(rails, key=lambda k: -rails[k]["spend"])
    tot = sum(rails[k]["spend"] for k in keys) or 1
    fig, ax = _fig(w_in, h_in)
    fig.subplots_adjust(left=0.24, right=0.97, top=0.95, bottom=0.05)
    _hbars(ax, [RAIL_NAMES.get(k, k) for k in keys],
           [100.0 * rails[k]["spend"] / tot for k in keys], lambda v: f"{v:.0f}%",
           color=NAVY, fs=12)
    return _save(fig, out)
