#!/usr/bin/env python3
"""
insight_charts.py — renderers for the test-branch views from combined_insights.py.

TEST BRANCH (test/james-aaron-combined). Four charts, each drawn at the aspect of the picture
box its slide places it in (STYLE.md: "render at the picture box's aspect"), in the house
style: brand.py palette, Carlito via rpe_env.use_font, MMM'YY month labels through
periods.axis_months with the month-axis guard installed, and no mark in the canvas colour
(tests/test_chart_colors.py reads this file because its name carries "chart").

  responder_control_chart  indexed monthly spend around the mailing, responders vs control
  branch_kpi_chart         take rate and Reg E opt-in per branch as grouped columns
  health_chart             carded eligible accounts by card-spend state
  wave_revenue_chart       each mailing's booked revenue to date, with revenue per month booked
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
from matplotlib.lines import Line2D                                      # noqa: E402
from matplotlib.patches import Patch                                     # noqa: E402

from brand import (NAVY, ORANGE, TICK, MUTED, GRID, TEAL, STEEL,        # noqa: E402
                   STEEL_SOFT, CHART_FONT, ROWALT)
import periods                                                           # noqa: E402
from rpe_env import use_font                                             # noqa: E402

periods.install_month_axis_guard()
DPI = 200
HALO = dict(boxstyle="square,pad=0.12", facecolor="white", edgecolor="none")


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
    """Saved at the figure's own size — never bbox 'tight', which changes the aspect the
    slide's picture box was sized for."""
    fig.savefig(out, dpi=DPI, facecolor="white")
    plt.close(fig)
    return out


def _money(v):
    a = abs(v)
    s = f"${a/1e6:.1f}M" if a >= 1e6 else (f"${a/1e3:.0f}K" if a >= 1e3 else f"${a:,.0f}")
    return ("−" if v < 0 else "") + s


# ----------------------------------------------------------------- responders vs control
def responder_control_chart(out, rc, w_in=8.7, h_in=4.1):
    """Two indexed lines around the mail month: responders orange, mailed non-responders navy.

    Index 100 is each group's own pre-mailing average, so a group spending $300 and one
    spending $550 before the mailing start from the same line and only the change is compared.
    """
    fig, ax = _fig(w_in, h_in)
    fig.subplots_adjust(left=0.09, right=0.80, top=0.93, bottom=0.14)
    r = rc["responders"]["trajectory"]
    c = rc["control"]["trajectory"]
    xs = [o for o, _ in r]
    ax.axvspan(-0.5, 0.5, color=ROWALT, zorder=0)
    ax.axhline(100, color=MUTED, lw=1.2, ls=(0, (4, 3)), zorder=1)
    ax.plot(xs, [v for _, v in c], color=NAVY, lw=2.6, marker="o", ms=5, mfc="white",
            mec=NAVY, mew=1.8, zorder=4)
    ax.plot(xs, [v for _, v in r], color=ORANGE, lw=2.6, marker="o", ms=5, mfc="white",
            mec=ORANGE, mew=1.8, zorder=5)
    top = max(v for _, v in r + c)
    low = min(v for _, v in r + c)
    ax.set_ylim(min(80, low - 8), top * 1.10)
    ax.set_xlim(xs[0] - 0.4, xs[-1] + 0.4)
    ax.set_xticks(xs)
    ax.set_xticklabels([("Mail" if o == 0 else f"{o:+d}".replace("-", "−")) for o in xs],
                       fontsize=12, color=NAVY)
    ax.set_xlabel("Months from the mailing", fontsize=12, color=TICK)
    ax.set_ylabel("Monthly spend index (before = 100)", fontsize=12, color=TICK)
    ax.tick_params(axis="y", labelsize=11)
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    _spines(ax, left=True)
    # End labels in the right margin; pushed apart when the two lines finish close together.
    ly_r, ly_c = r[-1][1], c[-1][1]
    gap = (ax.get_ylim()[1] - ax.get_ylim()[0]) * 0.09
    if abs(ly_r - ly_c) < gap:
        mid = (ly_r + ly_c) / 2
        ly_r, ly_c = (mid + gap / 2, mid - gap / 2) if ly_r >= ly_c else (mid - gap / 2, mid + gap / 2)
    ax.annotate(f"Responders\n{r[-1][1]:.0f}", xy=(xs[-1], r[-1][1]), xytext=(xs[-1] + 0.55, ly_r),
                textcoords="data", color=ORANGE, fontsize=12, fontweight="bold", va="center",
                annotation_clip=False)
    ax.annotate(f"Non-responders\n{c[-1][1]:.0f}", xy=(xs[-1], c[-1][1]),
                xytext=(xs[-1] + 0.55, ly_c), textcoords="data", color=NAVY, fontsize=12,
                fontweight="bold", va="center", annotation_clip=False)
    return _save(fig, out)


# ----------------------------------------------------------------- branch KPIs
def branch_kpi_chart(out, rows, take_book, rege_book, w_in=12.3, h_in=4.15):
    """Grouped columns per branch: take rate navy, Reg E opt-in orange, each labelled; the
    two program rates as dashed lines drawn BEHIND the bars, so neither line is ever drawn
    over a bar of its own colour. `rows` = [(branch, eligible, take, rege)], largest first."""
    fig, ax = _fig(w_in, h_in)
    fig.subplots_adjust(left=0.02, right=0.99, top=0.84, bottom=0.17)
    w = 0.36
    x = list(range(len(rows)))
    ax.axhline(take_book, color=NAVY, lw=1.3, ls=(0, (5, 4)), zorder=1)
    ax.axhline(rege_book, color=ORANGE, lw=1.3, ls=(0, (5, 4)), zorder=1)
    for i, (_, _, take, rege) in enumerate(rows):
        ax.bar(i - w / 2, take, width=w, color=NAVY, zorder=2)
        ax.bar(i + w / 2, rege, width=w, color=ORANGE, zorder=2)
        ax.text(i - w / 2, take + 1.2, f"{take:.1f}%", ha="center", va="bottom", fontsize=11,
                color=NAVY, fontweight="bold", bbox=HALO, zorder=5)
        ax.text(i + w / 2, rege + 1.2, f"{rege:.1f}%", ha="center", va="bottom", fontsize=11,
                color=NAVY, fontweight="bold", bbox=HALO, zorder=5)
    ax.set_ylim(0, min(112, max([r[2] for r in rows] + [r[3] for r in rows]) * 1.16))
    ax.get_yaxis().set_visible(False)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{b}\n{n:,}" for b, n, _, _ in rows], fontsize=12, color=NAVY)
    ax.set_xlabel("Branch  ·  ARS-eligible personal accounts", fontsize=12, color=TICK)
    _spines(ax)
    handles = [Patch(color=NAVY), Patch(color=ORANGE),
               Line2D([], [], color=NAVY, lw=1.3, ls=(0, (5, 4))),
               Line2D([], [], color=ORANGE, lw=1.3, ls=(0, (5, 4)))]
    labels = ["Take rate", "Reg E opt-in", f"All eligible: take rate {take_book:.1f}%",
              f"All card holders: opt-in {rege_book:.1f}%"]
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, fontsize=12,
               bbox_to_anchor=(0.5, 0.995), labelcolor=TICK)
    return _save(fig, out)


# ----------------------------------------------------------------- account health
HEALTH_COLORS = {"Active": NAVY, "Declining": ORANGE, "Cooling": ORANGE, "Dormant": ORANGE,
                 "Never used": ORANGE, "No card": STEEL}


def health_chart(out, states, w_in=8.7, h_in=4.1):
    """Horizontal bars, one per state in the order the states run from use to no use.
    At-risk states orange, active navy, no card steel; count and share at the bar end."""
    fig, ax = _fig(w_in, h_in)
    fig.subplots_adjust(left=0.15, right=0.97, top=0.97, bottom=0.05)
    names = [s[0] for s in states]
    counts = [s[1] for s in states]
    y = list(range(len(states)))[::-1]
    ax.barh(y, counts, color=[HEALTH_COLORS.get(n, NAVY) for n in names], height=0.62, zorder=2)
    mx = max(counts) or 1
    for yi, (n, cnt, pct, *_rest) in zip(y, states):
        ax.text(cnt + mx * 0.012, yi, f"{cnt:,}  ·  {pct:.1f}%", va="center", ha="left",
                fontsize=13, color=NAVY, fontweight="bold")
    ax.set_xlim(0, mx * 1.30)
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=13, color=NAVY)
    ax.get_xaxis().set_visible(False)
    _spines(ax, left=True)
    ax.spines["bottom"].set_visible(False)
    return _save(fig, out)


# ----------------------------------------------------------------- revenue by mailing
def wave_revenue_chart(out, waves, w_in=12.3, h_in=4.1, young_months=6):
    """Bars: each mailing's booked incremental revenue to date (navy; a mailing with fewer
    than `young_months` months booked is hatched STEEL_SOFT — still accruing, like the partial
    month on the house time series). TEAL line on the right axis: revenue per month booked,
    which is what makes a 95-month-old mailing and a 5-month-old one comparable."""
    fig, ax = _fig(w_in, h_in)
    fig.subplots_adjust(left=0.07, right=0.92, top=0.88, bottom=0.22)
    x = list(range(len(waves)))
    rev = [w["revenue"] for w in waves]
    per = [w["per_month"] for w in waves]
    for i, w in enumerate(waves):
        if w["months"] < young_months:
            ax.bar(i, w["revenue"], width=0.68, color=STEEL_SOFT, alpha=0.42, hatch="//",
                   edgecolor="white", zorder=2)
        else:
            ax.bar(i, w["revenue"], width=0.68, color=NAVY, zorder=2)
    ax.set_ylim(0, max(rev) * 1.12)
    ax.yaxis.set_major_formatter(lambda v, _p: _money(v))
    ax.tick_params(axis="y", labelsize=11)
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    ax.set_ylabel("Booked to date (bars)", fontsize=12, color=TICK)
    labels = periods.axis_months([w["m"] for w in waves])
    stride = 1 if len(waves) <= 24 else 2
    keep = {i for i in x if (len(x) - 1 - i) % stride == 0}      # the newest is always labelled
    ax.set_xticks(x)
    ax.set_xticklabels([lab if i in keep else "" for i, lab in enumerate(labels)],
                       rotation=periods.AXIS_ROTATION, ha=periods.AXIS_HA, fontsize=11,
                       color=NAVY)
    ax.set_xlim(-0.7, len(x) - 0.3)
    _spines(ax, left=True)
    ax2 = ax.twinx()
    ax2.plot(x, per, color=TEAL, lw=2.4, marker="o", ms=4, mfc="white", mec=TEAL, mew=1.6,
             zorder=6)
    ax2.set_ylim(0, max(per) * 1.18)
    ax2.yaxis.set_major_formatter(lambda v, _p: _money(v))
    ax2.tick_params(colors=TICK, length=0, labelsize=11)
    ax2.set_ylabel("Per month booked (line)", fontsize=12, color=TICK)
    for sp in ("top", "left"):
        ax2.spines[sp].set_visible(False)
    ax2.spines["right"].set_color(MUTED)
    handles = [Patch(color=NAVY), Patch(facecolor=STEEL_SOFT, alpha=0.42, hatch="//",
                                        edgecolor="white"),
               Line2D([], [], color=TEAL, lw=2.4, marker="o", mfc="white", mec=TEAL)]
    fig.legend(handles, ["Booked to date", f"Fewer than {young_months} months booked",
                         "Booked per month since the mailing"],
               loc="upper center", ncol=3, frameon=False, fontsize=12,
               bbox_to_anchor=(0.5, 0.995), labelcolor=TICK)
    return _save(fig, out)
