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
    import chart_lib
    _ticks, _tsize = chart_lib.branch_tick_labels([r[0] for r in rows], [r[1] for r in rows],
                                                  w_in * 0.97 / max(1, len(rows)), pt=12, min_pt=9)
    ax.set_xticklabels(_ticks, fontsize=_tsize, color=NAVY)
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
    for yi, row in zip(y, states):
        cnt, pct = row[1], row[2]
        # index 5 is the share of CARD HOLDERS, present for every state but "No card",
        # which has no card-holder denominator and is labelled as a share of eligible.
        of_carded = row[5] if len(row) > 5 else None
        txt = (f"{cnt:,}  ·  {of_carded:.1f}%" if of_carded is not None
               else f"{cnt:,}  ·  {pct:.1f}% of eligible")
        ax.text(cnt + mx * 0.012, yi, txt, va="center", ha="left",
                fontsize=13, color=NAVY, fontweight="bold")
    ax.set_xlim(0, mx * 1.44)
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
    # The line carries MATURE mailings only (Aaron, 2026-09-21). Revenue per responder is
    # highest in a mailing's first months, so a 2-month-old mailing peaks the line and reads
    # as the best offer the client ever ran; the caption already limited itself to 6+ months
    # while the line did not, which is the sort of disagreement between a chart and its own
    # caption nobody catches on the call.
    mature_x = [i for i in x if waves[i]["months"] >= young_months]
    mature_per = [per[i] for i in mature_x]
    if mature_per:
        ax2.plot(mature_x, mature_per, color=TEAL, lw=2.4, marker="o", ms=4, mfc="white",
                 mec=TEAL, mew=1.6, zorder=6)
    ax2.set_ylim(0, (max(mature_per) if mature_per else max(per)) * 1.18)
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
                         f"Booked per month ({young_months}+ months only)"],
               loc="upper center", ncol=3, frameon=False, fontsize=12,
               bbox_to_anchor=(0.5, 0.995), labelcolor=TICK)
    return _save(fig, out)


# ----------------------------------------------------------------- revenue build by mailing
def wave_build_chart(out, waves, w_in=12.3, h_in=4.0, named=5):
    """Cumulative booked revenue against MONTHS SINCE THE MAILING, one line per mailing.

    James's slide 5 ("the Apr25 offer has returned $274K to date") reads each offer's
    month-by-month build; our Revenue by Mailing showed only the endpoint, so two mailings
    that ended in the same place looked identical however differently they got there.

    Every mailing is drawn on one x-axis of AGE, not of calendar months, which is the only
    way a 2019 mailing and a 2026 one are comparable. The `named` most recent are coloured
    and labelled; the rest are the grey band they belong to.
    """
    fig, ax = _fig(w_in, h_in)
    fig.subplots_adjust(left=0.07, right=0.80, top=0.93, bottom=0.14)
    ramp = [ORANGE, NAVY, TEAL, STEEL, MUTED]
    recent = waves[-named:] if named else []
    recent_keys = {w["key"] for w in recent}
    for w in waves:
        if not w.get("build"):
            continue
        xs = [p[0] for p in w["build"]]
        ys = [p[2] for p in w["build"]]
        if w["key"] in recent_keys:
            continue
        ax.plot(xs, ys, color=STEEL_SOFT, lw=1.1, alpha=0.55, zorder=2)
    handles = []
    for i, w in enumerate(recent):
        if not w.get("build"):
            continue
        c = ramp[i % len(ramp)]
        xs = [p[0] for p in w["build"]]
        ys = [p[2] for p in w["build"]]
        ax.plot(xs, ys, color=c, lw=2.4, zorder=5)
        ax.plot(xs[-1:], ys[-1:], marker="o", ms=5, mfc="white", mec=c, mew=1.8, zorder=6)
        handles.append(Line2D([], [], color=c, lw=2.4,
                              label=f"{w['m']}  ·  {_money(ys[-1])} over {w['months']} mo"))
    if any(w.get("build") for w in waves if w["key"] not in recent_keys):
        handles.append(Line2D([], [], color=STEEL_SOFT, lw=1.1, label="Earlier mailings"))
    ax.set_xlabel("Months since the mailing", fontsize=12, color=TICK)
    ax.set_ylabel("Booked, cumulative", fontsize=12, color=TICK)
    ax.yaxis.set_major_formatter(lambda v, _p: _money(v))
    ax.tick_params(labelsize=11)
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)
    _spines(ax, left=True)
    if handles:
        ax.legend(handles=handles, loc="center left", bbox_to_anchor=(1.01, 0.5),
                  frameon=False, fontsize=11.5, labelcolor=TICK, handlelength=1.6)
    return _save(fig, out)


# ----------------------------------------------------------------- this month, by mailing
def month_split_chart(out, rows, w_in=12.3, h_in=3.6, young_months=6):
    """Bars: what each mailing booked in the newest month, largest first.

    James's slide 6 ("8 offers earned together: $100K booked in the month") answers a
    question our deck never did — a client sees one revenue figure for the month and cannot
    tell whether it came from the offer they just paid for or from one that ran in 2019.
    """
    fig, ax = _fig(w_in, h_in)
    fig.subplots_adjust(left=0.06, right=0.98, top=0.90, bottom=0.26)
    x = list(range(len(rows)))
    vals = [v for _m, v, _n in rows]
    colors = [ORANGE if n < young_months else NAVY for _m, _v, n in rows]
    ax.bar(x, vals, width=0.66, color=colors, zorder=2)
    mx = max(vals) if vals else 1
    for i, v in zip(x, vals):
        ax.text(i, v + mx * 0.02, _money(v), ha="center", va="bottom", fontsize=11.5,
                color=NAVY, fontweight="bold")
    ax.set_xticks(x)
    # House month format, via periods.axis_months — the axis guard raises on "Mar 2026".
    ax.set_xticklabels(periods.axis_months([m for m, _v, _n in rows]),
                       rotation=periods.AXIS_ROTATION, ha=periods.AXIS_HA, fontsize=11,
                       color=NAVY)
    ax.set_ylim(0, mx * 1.18)
    ax.yaxis.set_major_formatter(lambda v, _p: _money(v))
    ax.tick_params(axis="y", labelsize=11)
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    ax.set_ylabel("Booked this month", fontsize=12, color=TICK)
    _spines(ax, left=True)
    if any(n < young_months for _m, _v, n in rows):
        ax.legend(handles=[Patch(color=NAVY, label=f"{young_months}+ months booked"),
                           Patch(color=ORANGE, label=f"Fewer than {young_months} months booked")],
                  loc="upper right", frameon=False, fontsize=11.5, labelcolor=TICK)
    return _save(fig, out)


# ----------------------------------------------------------------- where a rate lags
def cut_panel_chart(out, cuts, measure, book, w_in=12.3, h_in=3.9, min_band=25):
    """Four small multiples — tenure, age, balance, product — each a rate per band against
    the book's own rate (the dashed line). James shows "where opt-in lags" as pockets; the
    panels keep every band visible, so a reader sees the shape, not only the worst three.

    A band below `min_band` accounts is drawn in the light grey that means "too few to read",
    and a band the ODD could not place ("Not on file") keeps its row rather than vanishing.
    """
    names = [n for n in ("Tenure", "Age", "Balance", "Product") if cuts.get(n)]
    fig, axes = plt.subplots(1, len(names), figsize=(w_in, h_in))
    use_font(CHART_FONT)
    if len(names) == 1:
        axes = [axes]
    fig.subplots_adjust(left=0.085, right=0.99, top=0.90, bottom=0.14, wspace=0.62)
    pool_key = "eligible" if measure == "take" else "rege_pool"
    for ax, name in zip(axes, names):
        rows = [b for b in cuts[name] if b[measure] is not None]
        y = list(range(len(rows)))[::-1]
        vals = [b[measure] for b in rows]
        colors = [(ROWALT if b[pool_key] < min_band else
                   (ORANGE if book is not None and b[measure] < book else NAVY)) for b in rows]
        ax.barh(y, vals, color=colors, height=0.66, zorder=3)
        top = max(vals + ([book] if book else [])) * 1.38 or 1
        for yi, b in zip(y, rows):
            ax.text(b[measure] + top * 0.02, yi, f"{b[measure]:.0f}%", va="center", ha="left",
                    fontsize=10.5, color=NAVY, fontweight="bold")
        if book is not None:
            ax.axvline(book, color=TICK, lw=1.2, ls=(0, (3, 3)), zorder=4)
        ax.set_yticks(y)
        # Escape the dollar signs: matplotlib reads $...$ as mathtext, and "$1 to $499"
        # rendered as italic algebra ("1to499") until this was caught in a render.
        ax.set_yticklabels([_clip(b["band"], 22).replace("$", r"\$") for b in rows],
                           fontsize=10.5, color=NAVY)
        ax.set_xlim(0, top)
        ax.get_xaxis().set_visible(False)
        ax.set_title(name, fontsize=12.5, color=TICK, pad=6)
        _spines(ax)
        ax.spines["bottom"].set_visible(False)
    fig.legend(handles=[Patch(color=NAVY, label="At or above the book"),
                        Patch(color=ORANGE, label="Below the book"),
                        Patch(color=ROWALT, label=f"Fewer than {min_band} accounts"),
                        Line2D([], [], color=TICK, lw=1.2, ls=(0, (3, 3)),
                               label=f"Book {book:.1f}%" if book is not None else "Book")],
               loc="lower center", ncol=4, frameon=False, fontsize=11, labelcolor=TICK,
               bbox_to_anchor=(0.5, -0.01))
    return _save(fig, out)


def _clip(s, n):
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"
