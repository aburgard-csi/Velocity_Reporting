"""
Charts, in the two forms the deck uses.

PROVENANCE: the analysis team's `charts.py`, restyled onto the RPE palette and type. Positions
of the native charts are DESIGN coordinates (see theme.py) and go through T.X / T.Y / T.W / T.H;
native chart text is Calibri at a role-based size; matplotlib figures use Carlito
(`rpe_env.use_font`, which raises rather than substitute a face) and the brand colours.

Native PowerPoint charts (`bar`, `column`) are used wherever possible: the underlying numbers
stay inspectable and editable in PowerPoint, which matters for a client deliverable that gets
questioned live in the room.

Matplotlib is used only where there is no clean native equivalent — the deposit-health box plot
and the predictor bubble charts here, and the charts in `r_charts.py` that replace the R
pictures. Those render to PNG at 200 dpi at the shape's own aspect and are placed as pictures.

Bar-chart categories are always passed in ascending order deliberately: PowerPoint plots the
first category at the bottom, so ascending puts the largest value at the top.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt              # noqa: E402
import matplotlib.transforms as mtransforms  # noqa: E402
import numpy as np                           # noqa: E402

from pptx.chart.data import CategoryChartData  # noqa: E402
from pptx.enum.chart import (XL_CHART_TYPE, XL_LABEL_POSITION,  # noqa: E402
                             XL_LEGEND_POSITION, XL_MARKER_STYLE)
from pptx.util import Inches, Pt              # noqa: E402

from . import theme as T                      # noqa: E402
import rpe_env                                # noqa: E402  (build/ is on sys.path via theme)

rpe_env.use_font(T.brand.CHART_FONT)
plt.rcParams.update({
    "font.size": 11,
    "axes.edgecolor": T.brand.MUTED,
    "axes.linewidth": 0.8,
    "figure.dpi": 200,
})

FONT = T.BODY


def _sz(design):
    """Native chart text size: role-based, never below 9 pt (axis text on a dense chart)."""
    return max(9.0, round(design * 0.72 * 2) / 2)


# ═══════════════════════════ native PowerPoint charts ═══════════════════════
def _style_axes(chart, *, cat_size=13, val_size=12, val_format=None):
    try:
        chart.category_axis.tick_labels.font.size = Pt(_sz(cat_size))
        chart.category_axis.tick_labels.font.name = FONT
        chart.category_axis.tick_labels.font.color.rgb = T.SUBTLE
        chart.category_axis.format.line.color.rgb = T.GRAY
    except (AttributeError, ValueError):
        pass
    try:
        chart.value_axis.tick_labels.font.size = Pt(_sz(val_size))
        chart.value_axis.tick_labels.font.name = FONT
        chart.value_axis.tick_labels.font.color.rgb = T.SUBTLE
        chart.value_axis.has_major_gridlines = True
        chart.value_axis.major_gridlines.format.line.color.rgb = T.RULE
        chart.value_axis.major_gridlines.format.line.width = Pt(0.75)
        chart.value_axis.format.line.fill.background()
        if val_format:
            chart.value_axis.tick_labels.number_format = val_format
            chart.value_axis.tick_labels.number_format_is_linked = False
    except (AttributeError, ValueError):
        pass


def _label_series(plot, number_format, size=12, position=None):
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format = number_format
    dl.number_format_is_linked = False
    dl.font.size = Pt(_sz(size))
    dl.font.name = FONT
    dl.font.color.rgb = T.NAVY
    if position is not None:
        try:
            dl.position = position
        except ValueError:
            pass


def _frame(slide, kind, x, y, w, h, cd):
    return slide.shapes.add_chart(kind, Inches(T.X(x)), Inches(T.Y(y)),
                                  Inches(T.W(w)), Inches(T.H(h)), cd)


def bar(slide, x, y, w, h, labels, values, *, series_name="Value", color=T.NAVY,
        number_format="#,##0", label_size=12, cat_size=13, data_labels=True):
    """Horizontal bar chart. `labels`/`values` ascending -> largest at top."""
    cd = CategoryChartData()
    cd.categories = list(labels)
    cd.add_series(series_name, list(values))
    chart = _frame(slide, XL_CHART_TYPE.BAR_CLUSTERED, x, y, w, h, cd).chart
    chart.has_legend = False
    chart.has_title = False
    chart.font.size = Pt(_sz(cat_size))
    chart.font.name = FONT
    plot = chart.plots[0]
    plot.gap_width = 45
    ser = plot.series[0]
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = color
    ser.format.line.fill.background()
    if data_labels:
        _label_series(plot, number_format, label_size, XL_LABEL_POSITION.OUTSIDE_END)
    _style_axes(chart, cat_size=cat_size, val_size=label_size, val_format=number_format)
    return chart


def column(slide, x, y, w, h, labels, values, *, series_name="Value", color=T.NAVY,
           number_format="#,##0", label_size=12, cat_size=13, colors=None):
    """Vertical column chart; `colors` gives per-point fills when supplied."""
    cd = CategoryChartData()
    cd.categories = list(labels)
    cd.add_series(series_name, list(values))
    chart = _frame(slide, XL_CHART_TYPE.COLUMN_CLUSTERED, x, y, w, h, cd).chart
    chart.has_legend = False
    chart.has_title = False
    chart.font.size = Pt(_sz(cat_size))
    chart.font.name = FONT
    plot = chart.plots[0]
    plot.gap_width = 60
    ser = plot.series[0]
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = color
    ser.format.line.fill.background()
    if colors:
        for i, c in enumerate(colors):
            if i < len(ser.points):
                ser.points[i].format.fill.solid()
                ser.points[i].format.fill.fore_color.rgb = c
    _label_series(plot, number_format, label_size, XL_LABEL_POSITION.OUTSIDE_END)
    _style_axes(chart, cat_size=cat_size, val_size=label_size, val_format=number_format)
    return chart


def _legend(chart):
    chart.has_legend = True
    chart.legend.position = XL_LEGEND_POSITION.BOTTOM
    chart.legend.include_in_layout = False
    chart.legend.font.size = Pt(_sz(12))
    chart.legend.font.name = FONT


def grouped_column(slide, x, y, w, h, labels, series, *, number_format="0.0",
                   label_size=11, cat_size=13, legend=True):
    """Clustered columns; `series` is a list of (name, values, color)."""
    cd = CategoryChartData()
    cd.categories = list(labels)
    for name, values, _ in series:
        cd.add_series(name, list(values))
    chart = _frame(slide, XL_CHART_TYPE.COLUMN_CLUSTERED, x, y, w, h, cd).chart
    chart.has_title = False
    chart.font.size = Pt(_sz(cat_size))
    chart.font.name = FONT
    if legend:
        _legend(chart)
    else:
        chart.has_legend = False
    plot = chart.plots[0]
    plot.gap_width = 70
    for i, (_, _, colr) in enumerate(series):
        s = plot.series[i]
        s.format.fill.solid()
        s.format.fill.fore_color.rgb = colr
        s.format.line.fill.background()
    _style_axes(chart, cat_size=cat_size, val_size=label_size, val_format=number_format)
    return chart


def line(slide, x, y, w, h, labels, series, *, number_format="#,##0",
         cat_size=11.5, legend=True, smooth=False, tick_every=None):
    """Line chart; `series` is a list of (name, values, color).

    Used for the DBIC daily feeds, which run 61 points — too many for readable columns.
    `tick_every` thins the category labels so the axis stays legible.
    """
    cd = CategoryChartData()
    cd.categories = list(labels)
    for name, values, _ in series:
        cd.add_series(name, list(values))
    chart = _frame(slide, XL_CHART_TYPE.LINE, x, y, w, h, cd).chart
    chart.has_title = False
    chart.font.size = Pt(_sz(cat_size))
    chart.font.name = FONT
    if legend and len(series) > 1:
        _legend(chart)
    else:
        chart.has_legend = False
    for i, (_, _, colr) in enumerate(series):
        s = chart.plots[0].series[i]
        s.format.line.color.rgb = colr
        s.format.line.width = Pt(2.0)
        s.smooth = smooth
        try:
            s.marker.style = XL_MARKER_STYLE.NONE
        except (AttributeError, ValueError):
            pass
    _style_axes(chart, cat_size=cat_size, val_size=12, val_format=number_format)
    if tick_every:
        try:
            chart.category_axis.tick_label_spacing = int(tick_every)
        except (AttributeError, ValueError):
            pass
    return chart


def stacked_bar_100(slide, x, y, w, h, labels, series, *, cat_size=13, legend=True):
    """100% stacked columns; `series` is a list of (name, values, color)."""
    cd = CategoryChartData()
    cd.categories = list(labels)
    for name, values, _ in series:
        cd.add_series(name, list(values))
    chart = _frame(slide, XL_CHART_TYPE.COLUMN_STACKED_100, x, y, w, h, cd).chart
    chart.has_title = False
    chart.font.size = Pt(_sz(cat_size))
    chart.font.name = FONT
    if legend:
        _legend(chart)
    else:
        chart.has_legend = False
    plot = chart.plots[0]
    plot.gap_width = 40
    for i, (_, _, colr) in enumerate(series):
        s = plot.series[i]
        s.format.fill.solid()
        s.format.fill.fore_color.rgb = colr
        s.format.line.fill.background()
    _style_axes(chart, cat_size=cat_size, val_size=12, val_format='0"%"')
    return chart


# ═══════════════════════════ matplotlib renders ═════════════════════════════
def _save(fig, path, facecolor="white"):
    fig.savefig(path, facecolor=facecolor, bbox_inches="tight")
    plt.close(fig)
    return path


def deposit_health_boxplot(tiers, out_path, *,
                           ylabel="OD/NSF fees collected per account, trailing 12mo ($)"):
    """Box plot of fee activity by deposit-health tier, at the 8.2 x 4.4 in picture box."""
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    colors = [(T.HEX["label"], T.HEX["slate"]), (T.HEX["orange"], T.HEX["navy"]),
              (T.HEX["gold"], T.HEX["navy"]), (T.HEX["steel_soft"], T.HEX["navy"])]
    bp = ax.boxplot(
        tiers.fee_arrays, tick_labels=tiers.labels, showmeans=True, whis=1.5,
        showfliers=False, patch_artist=True, widths=0.55,
        meanprops=dict(marker="D", markerfacecolor="white", markeredgecolor=T.HEX["navy"],
                       markersize=7, zorder=5),
        medianprops=dict(color=T.HEX["navy"], linewidth=2.2),
        whiskerprops=dict(color=T.HEX["slate"], linewidth=1.4),
        capprops=dict(color=T.HEX["slate"], linewidth=1.4),
        boxprops=dict(linewidth=1.4),
    )
    for patch, (fc, ec) in zip(bp["boxes"], colors[:len(tiers.labels)]):
        patch.set_facecolor(fc)
        patch.set_edgecolor(ec)

    ymax = 1000.0
    highs = []
    for arr in tiers.fee_arrays:
        if not len(arr):
            continue
        q1, q3 = np.percentile(arr, [25, 75])
        fence = q3 + 1.5 * (q3 - q1)
        within = arr[arr <= fence]
        highs.append(within.max() if len(within) else q3)
    if highs and max(highs) > 0:
        ymax = max(highs) * 1.15

    ax.set_ylabel(ylabel, fontsize=11, color=T.HEX["navy"])
    ax.set_ylim(0, ymax)
    ax.tick_params(axis="y", labelsize=11, colors=T.HEX["subtle"])
    ax.tick_params(axis="x", labelsize=11, colors=T.HEX["subtle"], pad=10)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(T.HEX["grid"])
    ax.spines["bottom"].set_color(T.HEX["grid"])
    ax.yaxis.grid(True, color=T.HEX["grid"], linewidth=0.9)
    ax.set_axisbelow(True)

    fig.subplots_adjust(bottom=0.22, top=0.97, left=0.10, right=0.98)
    trans = mtransforms.blended_transform_factory(ax.transData, ax.transAxes)
    for i, (mean, n) in enumerate(zip(tiers.means, tiers.ns), start=1):
        ax.annotate(f"mean ${mean:,.0f}   n={n:,}", xy=(i, -0.12), xycoords=trans,
                    ha="center", va="top", fontsize=10, color=T.HEX["subtle"],
                    annotation_clip=False)
    return _save(fig, out_path)


def predictor_bubble(bands, rates, counts, out_path, *, title, xlabel,
                     ylabel="% Default Rate", avg_line=None, figsize=(6.4, 4.6)):
    """Bubble scatter of default rate by predictor band, bubble area = # notices.

    One point per band, sized by notice volume, labelled with the notice count, with a dashed
    reference line at the portfolio average (the R chart's design, in the RPE palette).
    """
    fig, ax = plt.subplots(figsize=figsize)
    x = np.arange(len(bands))
    counts = np.asarray(counts, dtype=float)
    rates = np.asarray(rates, dtype=float)
    sizes = 30 + (counts / (counts.max() or 1)) * 700
    ax.scatter(x, rates, s=sizes, color=T.HEX["navy"], zorder=3, alpha=0.92)
    for xi, r, n in zip(x, rates, counts):
        ax.annotate(f"{int(n):,}", (xi, r), (0, 11), textcoords="offset points",
                    ha="center", fontsize=9, color=T.HEX["subtle"])
    if avg_line is not None:
        ax.axhline(avg_line, color=T.HEX["orange"], linestyle="--", linewidth=1.6, zorder=2)
        ax.annotate(f"All notices {avg_line:.2f}%", (len(bands) - 0.4, avg_line), (0, 5),
                    textcoords="offset points", ha="right", fontsize=9, color=T.HEX["orange"])
    ax.set_xticks(x)
    ax.set_xticklabels(bands, rotation=45, ha="right", fontsize=10, color=T.HEX["subtle"])
    ax.set_ylabel(ylabel, fontsize=11, color=T.HEX["subtle"])
    ax.set_xlabel(xlabel, fontsize=11, color=T.HEX["subtle"])
    ax.set_title(title, fontsize=11.5, color=T.HEX["navy"], loc="left", pad=14)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.tick_params(axis="y", labelsize=10, colors=T.HEX["subtle"])
    ax.set_ylim(bottom=0)
    ax.margins(x=0.04, y=0.22)
    ax.grid(True, color=T.HEX["grid"], linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(T.HEX["grid"])
    ax.spines["bottom"].set_color(T.HEX["muted"])
    fig.tight_layout()
    return _save(fig, out_path)
