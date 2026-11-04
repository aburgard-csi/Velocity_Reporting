"""
Matplotlib charts for the Deposit Score section.

These are images rather than native PowerPoint charts because they carry
composition-plus-overlay structure (a 100% stacked score mix with a mean-score
line on a secondary axis) that PowerPoint's chart model handles badly. Figure
sizes are set for the 20 x 11.25 in canvas at 200 dpi.

PROVENANCE: the analysis team's `ds_charts.py`. Restyled for the RPE canvas: Carlito via
`rpe_env.use_font`, the brand navy / greys, figure sizes scaled by FIG (the picture boxes are
about two thirds the old size, and chart text stays at its own point size so it reads at
10-14 pt on the slide).
"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                       # noqa: E402
from matplotlib.patches import Patch     # noqa: E402

from .ds_analysis import SCORE_COLORS, SCORE_LABEL  # noqa: E402

from . import theme as T                  # noqa: E402  (puts build/ on sys.path)
import rpe_env                            # noqa: E402

rpe_env.use_font(T.brand.CHART_FONT)
NAVY = T.HEX["navy"]
GRAYTX = T.HEX["subtle"]
GRID = T.HEX["grid"]
FIG = 0.68

plt.rcParams.update({
    "font.size": 11,
    "axes.edgecolor": T.HEX["muted"],
    "axes.linewidth": 0.8,
    "figure.dpi": 200,
})


def _fs(w, h):
    return (w * FIG, h * FIG)


def _save(fig, path):
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def _despine(ax, keep=("left", "bottom")):
    for s in ("top", "right", "left", "bottom"):
        if s not in keep:
            ax.spines[s].set_visible(False)


def score_distribution(dist, scope_label, path):
    fig, ax = plt.subplots(figsize=_fs(11.0, 5.4))
    keys = [1, 2, 3, 4, 5, 0]
    vals = [dist.get(k, 0) for k in keys]
    total = sum(vals) or 1
    bars = ax.bar([SCORE_LABEL[k] for k in keys], vals,
                  color=[SCORE_COLORS[k] for k in keys], edgecolor="white")
    for b, v in zip(bars, vals):
        ax.annotate(f"{v:,}\n{v / total * 100:.1f}%",
                    (b.get_x() + b.get_width() / 2, v), ha="center", va="bottom",
                    fontsize=11, color=GRAYTX)
    ax.set_ylabel("Accounts")
    ax.set_xlabel("Deposit Score")
    ax.set_title(f"Deposit Score distribution — {scope_label}", color=NAVY,
                 fontweight="bold", fontsize=14)
    ax.margins(y=0.20)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    _despine(ax)
    return _save(fig, path)


def score_by_type(by_type, types, path):
    fig, ax = plt.subplots(figsize=_fs(11.0, 5.4))
    keys = [1, 2, 3, 4, 5, 0]
    x = np.arange(len(types))
    w = 0.8 / len(keys)
    for i, k in enumerate(keys):
        vals = []
        for t in types:
            d = by_type.get(t, {})
            tot = sum(d.values()) or 1
            vals.append(d.get(k, 0) / tot * 100)
        ax.bar(x + i * w, vals, w, color=SCORE_COLORS[k], label=SCORE_LABEL[k],
               edgecolor="white")
    ax.set_xticks(x + 0.4 - w / 2)
    ax.set_xticklabels(types)
    ax.set_ylabel("% of accounts in type")
    ax.set_title("Deposit Score composition by account type", color=NAVY,
                 fontweight="bold", fontsize=14)
    ax.legend(title="Score", ncol=6, fontsize=10, title_fontsize=10,
              loc="upper center", bbox_to_anchor=(0.5, -0.10), frameon=False)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    _despine(ax)
    return _save(fig, path)


def rate_by_score(rates, title, ylabel, path, *, order=(1, 2, 3, 4, 5, 0), fmt="{:.1f}%"):
    fig, ax = plt.subplots(figsize=_fs(7.6, 5.0))
    keys = [k for k in order if k in rates]
    vals = [rates[k] for k in keys]
    bars = ax.bar([SCORE_LABEL[k] for k in keys], vals,
                  color=[SCORE_COLORS[k] for k in keys], edgecolor="white")
    for b, v in zip(bars, vals):
        ax.annotate(fmt.format(v), (b.get_x() + b.get_width() / 2, v),
                    ha="center", va="bottom", fontsize=11, color=GRAYTX)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Deposit Score")
    ax.set_title(title, color=NAVY, fontweight="bold", fontsize=13)
    ax.margins(y=0.20)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    _despine(ax)
    return _save(fig, path)


def risk_bands(bands, path):
    """Horizontal 100% stacked bar of the portfolio across risk bands."""
    order = ["Lower risk (3–5)", "Higher risk (1–2)", "Unscored"]
    cols = {"Lower risk (3–5)": SCORE_COLORS[5], "Higher risk (1–2)": SCORE_COLORS[2],
            "Unscored": SCORE_COLORS[0]}
    total = sum(bands.get(k, {}).get("n", 0) for k in order) or 1
    fig, ax = plt.subplots(figsize=_fs(11.0, 1.9))
    left = 0
    for k in order:
        n = bands.get(k, {}).get("n", 0)
        pct = n / total * 100
        if pct <= 0:
            continue
        ax.barh(0, pct, left=left, color=cols[k], edgecolor="white")
        if pct > 6:
            ax.annotate(f"{k.split(' (')[0]}\n{pct:.0f}%", (left + pct / 2, 0),
                        ha="center", va="center", fontsize=11, color="white",
                        fontweight="bold")
        left += pct
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.5, 0.5)
    ax.axis("off")
    ax.set_title("Portfolio by risk band", color=NAVY, fontweight="bold",
                 fontsize=13, loc="left")
    return _save(fig, path)


def rdi_score_mix(dist, path):
    fig, ax = plt.subplots(figsize=_fs(7.4, 4.8))
    keys = [1, 2, 3, 4, 5]
    vals = [dist.get(k, 0) for k in keys]
    total = sum(vals) or 1
    bars = ax.bar([str(k) for k in keys], vals,
                  color=[SCORE_COLORS[k] for k in keys], edgecolor="white")
    for b, v in zip(bars, vals):
        if v:
            ax.annotate(f"{v:,}\n{v / total * 100:.0f}%",
                        (b.get_x() + b.get_width() / 2, v), ha="center", va="bottom",
                        fontsize=11, color=GRAYTX)
    ax.set_ylabel("RDI accounts")
    ax.set_xlabel("Deposit Score")
    ax.set_title("Deposit Score among accounts with RDI", color=NAVY,
                 fontweight="bold", fontsize=13)
    ax.margins(y=0.2)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    _despine(ax)
    return _save(fig, path)


def alignment(banded, path):
    """100%-stacked score mix across a variable's bands, plus a mean-score line."""
    labels = banded.band_labels
    keys = [1, 2, 3, 4, 5]           # not-scored excluded from the 100% stack
    fig, ax = plt.subplots(figsize=_fs(12.6, 6.0))
    x = np.arange(len(labels))
    totals = np.array([sum(banded.comp[b].get(k, 0) for k in keys) or 1 for b in labels],
                      dtype=float)
    bottoms = np.zeros(len(labels))
    for k in keys:
        vals = np.array([banded.comp[b].get(k, 0) for b in labels]) / totals * 100
        ax.bar(x, vals, bottom=bottoms, color=SCORE_COLORS[k], label=str(k),
               edgecolor="white", width=0.72)
        bottoms += vals
    ax.set_xticks(x)
    ax.set_xticklabels([str(l) for l in labels], rotation=16, ha="right", fontsize=11)
    ax.set_ylabel("Score mix (%)")
    ax.set_ylim(0, 100)
    ax.set_title(f"Deposit Score vs {banded.name}", color=NAVY, fontweight="bold",
                 fontsize=14)

    ax2 = ax.twinx()
    means = [banded.mean_score.get(b, np.nan) for b in labels]
    ax2.plot(x, means, color=NAVY, marker="o", linewidth=2.2, markersize=6, zorder=5)
    ax2.set_ylim(1, 5)
    ax2.set_ylabel("Mean score", color=NAVY)
    ax2.tick_params(axis="y", colors=NAVY)

    for xi, b in zip(x, labels):
        n = sum(banded.comp[b].get(k, 0) for k in [1, 2, 3, 4, 5, 0])
        ax.annotate(f"n={n:,}", (xi, 0), (0, -38), textcoords="offset points",
                    ha="center", va="top", fontsize=9.5, color=GRAYTX)

    handles = [Patch(facecolor=SCORE_COLORS[k], label=str(k)) for k in keys]
    handles.append(plt.Line2D([0], [0], color=NAVY, marker="o", label="Mean"))
    ax.legend(handles=handles, ncol=6, fontsize=10, loc="upper center",
              bbox_to_anchor=(0.5, -0.22), frameon=False, title="Score")
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    _despine(ax, keep=("left", "bottom", "right"))
    return _save(fig, path)


def render_all(A, img_dir):
    """Render every chart the Deposit Score slides need. Returns A.charts."""
    A.charts["score_dist"] = score_distribution(
        A.overall_dist, A.overall_scope_label, os.path.join(img_dir, "score_dist.png"))

    order_types = [t for t in ("Personal", "Business") if t in A.by_type_dist]
    order_types += [t for t in A.by_type_dist if t not in order_types]
    if len(order_types) > 1:
        A.charts["score_by_type"] = score_by_type(
            A.by_type_dist, order_types, os.path.join(img_dir, "score_by_type.png"))

    for i, b in enumerate(A.variables):
        b.chart = alignment(b, os.path.join(img_dir, f"align_{i}.png"))
        A.charts[f"align_{i}"] = b.chart

    if A.risk_rows:
        A.charts["chargeoff_by_score"] = rate_by_score(
            {r["score"]: r["co_rate"] for r in A.risk_rows},
            "Charge-off rate by Deposit Score", "% of accounts charged off",
            os.path.join(img_dir, "chargeoff_by_score.png"))
        A.charts["closure_by_score"] = rate_by_score(
            {r["score"]: r["notopen_rate"] for r in A.risk_rows},
            "Closed / inactive rate by Deposit Score", "% not currently open",
            os.path.join(img_dir, "closure_by_score.png"))
        A.charts["risk_bands"] = risk_bands(
            A.risk_bands, os.path.join(img_dir, "risk_bands.png"))

    if A.rdi:
        A.charts["rdi_scoremix"] = rdi_score_mix(
            A.rdi["dist"], os.path.join(img_dir, "rdi_scoremix.png"))
    return A.charts
