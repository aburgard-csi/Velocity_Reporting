# Ported from v5 02-Scripts/ils/kickoff_analysis/deck/charts.py at 7ba1e63. Logic unchanged; no edits (the workbook's matplotlib charts).
"""Chart renderers for the ILS Kickoff deck.

The notebook had ~9 matplotlib cells that were all one of five patterns
repeated with different data. Consolidated into one function per pattern
so each analysis module's caller just supplies data, not styling code.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# NOTHING here sets a global rcParam. Every function below already passes
# figsize, dpi and bbox_inches to its own savefig call, so these four lines
# changed nothing for this module -- and run.py imports it, so they applied
# to the WHOLE process. `savefig.bbox = "tight"` in particular cropped every
# shared chart form to its ink at save time, which is the one thing
# ars/deck/charts._save exists to prevent:
#
#     "Layout is tightened INSIDE the authored canvas -- never cropped to
#      content (bbox_inches='tight' shrank figures unpredictably, so the
#      same renderer landed at different on-slide type sizes)."
#
# The authored 8.8x4.6 canvas came out at whatever shape its ink happened to
# be, _fit_picture sized from that aspect, and the chart landed two inches
# short of the field it was given. That is "the chart does not fill even the
# space it has", and it was set from here.


def bar_with_line(categories, bar_values, line_values, bar_label: str, line_label: str,
                   title: str, out_path: str) -> str:
    """Bar chart (left axis) + line chart (right axis, e.g. a ratio %)."""
    fig, ax1 = plt.subplots(figsize=(10, 6))

    bars = ax1.bar(categories, bar_values, color="#4472C4", width=0.6, label=bar_label, alpha=0.8)
    ax1.set_ylabel(bar_label, color="#4472C4", fontsize=12, fontweight="bold")
    ax1.tick_params(axis="y", labelcolor="#4472C4")
    ax1.grid(axis="y", alpha=0.3, linestyle="--")

    max_bar = max(bar_values) if len(bar_values) else 1
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax1.text(bar.get_x() + bar.get_width() / 2, height + max_bar * 0.01,
                      f"{int(height):,}", ha="center", va="bottom", fontsize=10,
                      fontweight="bold", color="#4472C4")

    ax2 = ax1.twinx()
    ax2.plot(categories, line_values, color="#C00000", marker="o", markersize=8,
              linewidth=2.5, label=line_label)
    ax2.set_ylabel(line_label, color="#C00000", fontsize=12, fontweight="bold")
    ax2.tick_params(axis="y", labelcolor="#C00000")
    ax2.set_ylim(0, max(line_values, default=0) * 1.15 + 10)

    for i, v in enumerate(line_values):
        ax2.text(i, v + 2, f"{v:.1f}%", ha="center", va="bottom", fontsize=10,
                  fontweight="bold", color="#C00000")

    plt.title(title, fontsize=14, fontweight="bold", pad=20)
    if len(categories) > 4:
        ax1.set_xticklabels(categories, rotation=45, ha="right")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="lower left", frameon=True,
               fancybox=True, shadow=True)

    plt.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out_path


# RPE cases labels (navy core, white stroke) rather than drawing them in the canvas
# colour (tests/test_chart_colors.py); v5 drew these white inside the bars.
from matplotlib import patheffects as _pe
import brand as _brand
_NAVY = _brand.NAVY
_CASED = [_pe.withStroke(linewidth=3, foreground="white")]


def stacked_percentage_bar(categories, pct_a, pct_b, label_a: str, label_b: str,
                            title: str, ylabel: str, out_path: str) -> str:
    """Two-part stacked bar summing to 100% per category (e.g. Paid vs Returned)."""
    fig, ax = plt.subplots(figsize=(10, 6))

    bars_a = ax.bar(categories, pct_a, label=label_a, color="#70AD47", alpha=0.8)
    ax.bar(categories, pct_b, bottom=pct_a, label=label_b, color="#C00000", alpha=0.8)

    for i, (a, b) in enumerate(zip(pct_a, pct_b)):
        if a > 10:
            ax.text(i, a / 2, f"{a:.1f}%", ha="center", va="center", color=_NAVY, fontweight="bold",
                    path_effects=_CASED)
        if b > 10:
            ax.text(i, a + b / 2, f"{b:.1f}%", ha="center", va="center", color=_NAVY, fontweight="bold",
                    path_effects=_CASED)

    ax.set_ylabel(ylabel, fontsize=12, fontweight="bold")
    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0f}%"))
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)
    if len(categories) > 4:
        plt.xticks(rotation=45, ha="right")
    ax.legend(loc="upper right", frameon=True, fancybox=True, shadow=True)
    ax.axhline(y=50, color="gray", linestyle="--", alpha=0.5, linewidth=1)

    plt.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out_path


def horizontal_share(categories, pct_values, counts, title: str, xlabel: str, out_path: str) -> str:
    """Horizontal bar chart showing each category's share of a total, sorted ascending."""
    order = np.argsort(pct_values)
    categories = [categories[i] for i in order]
    pct_values = [pct_values[i] for i in order]
    counts = [counts[i] for i in order]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(categories, pct_values, color="#4472C4", alpha=0.8, edgecolor="navy", linewidth=1)

    max_val = max(pct_values, default=1)
    for bar, value in zip(bars, pct_values):
        intensity = value / max_val if max_val else 0
        bar.set_facecolor(plt.cm.Blues(0.3 + 0.7 * intensity))

    for i, (value, count) in enumerate(zip(pct_values, counts)):
        label_x = value + 0.5 if value < 5 else value / 2
        color = "black" if value < 5 else "white"
        ax.text(label_x, i, f"{value:.1f}%", va="center",
                ha="left" if value < 5 else "center", fontweight="bold", fontsize=11, color=color)
        ax.text(-1, i, f"({int(count):,} items)", va="center", ha="right", fontsize=9, color="gray")

    ax.set_xlabel(xlabel, fontsize=12, fontweight="bold")
    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)
    ax.set_xlim(-5, max_val + 5)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0f}%" if x >= 0 else ""))
    ax.grid(axis="x", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out_path


def grouped_bar(categories, series_a, series_b, label_a: str, label_b: str,
                 title: str, xlabel: str, ylabel: str, out_path: str) -> str:
    """Two side-by-side bars per category (e.g. % of Accounts vs % of Items)."""
    x = np.arange(len(categories))
    width = 0.35
    fig, ax = plt.subplots(figsize=(10, 6))

    bars1 = ax.bar(x - width / 2, series_a, width, label=label_a, color="#4472C4",
                    alpha=0.8, edgecolor="navy", linewidth=1)
    bars2 = ax.bar(x + width / 2, series_b, width, label=label_b, color="#70AD47",
                    alpha=0.8, edgecolor="darkgreen", linewidth=1)

    ax.set_ylabel(ylabel, fontsize=12, fontweight="bold")
    ax.set_xlabel(xlabel, fontsize=12, fontweight="bold")
    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(categories, rotation=45 if len(categories) > 3 else 0, ha="right")

    max_val = max(max(series_a, default=0), max(series_b, default=0))
    ax.set_ylim(0, max_val * 1.15 if max_val else 1)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0f}%"))
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)

    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.annotate(f"{height:.1f}%", xy=(bar.get_x() + bar.get_width() / 2, height),
                            xytext=(0, 3), textcoords="offset points", ha="center", va="bottom",
                            fontsize=10, fontweight="bold")

    ax.legend(loc="upper right", frameon=True, fancybox=True, shadow=True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out_path


def distribution_bar(bin_labels, pct_values, counts, mean_value: float, mean_label: str,
                      title: str, xlabel: str, out_path: str) -> str:
    """Single-series distribution bar chart with a mean-value annotation."""
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(bin_labels, pct_values, color="#4472C4", alpha=0.8, edgecolor="navy", linewidth=1)

    colors = plt.cm.Blues(np.linspace(0.4, 0.9, len(bars)))
    for bar, color in zip(bars, colors):
        bar.set_facecolor(color)

    for i, (pct, count) in enumerate(zip(pct_values, counts)):
        ax.text(i, pct + 0.5, f"{pct:.1f}%", ha="center", va="bottom", fontweight="bold", fontsize=11)
        ax.text(i, pct + 2, f"({count:,})", ha="center", va="bottom", fontsize=9, color="gray")

    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)
    ax.set_xlabel(xlabel, fontsize=12, fontweight="bold")
    ax.set_ylabel("Percentage of Accounts", fontsize=12, fontweight="bold")
    ax.set_ylim(0, max(pct_values, default=1) * 1.2)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0f}%"))
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ax.text(len(bin_labels) - 1, max(pct_values, default=1) * 1.1, f"{mean_label}: {mean_value:.1f}",
            ha="right", fontsize=10, style="italic", color="red")

    plt.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out_path
