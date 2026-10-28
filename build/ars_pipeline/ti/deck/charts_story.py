# Ported from ARS v5 02-Scripts/ars/deck/charts_story.py at a491b5c (James Gilmore); logic unchanged.
"""Narrative renderers for the transaction-intelligence chapter.

The forms that open and close the chapter: size the problem (treemap),
characterise it (radar, bullet), and end on the deliverable rather than the
method (worklist, ledger). Mined from the sketch catalogs and approved in
lab/DESIGN/report-mockups/slides-txn-suite.html.

Conventions follow charts.py -- ``out`` last, a ``_*_fig`` returning
``(fig, meta)``, orange for the finding only.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from .charts import (FIG_W_FULL, FIG_W_RAIL, GREY, GRID, LIGHT, NAVY, ORANGE,
                     STEEL, TINT, _clean, _save, fit_text, plt)
from .labels import clip
from .charts_txn import _fmt_money

MUTED = "#9AA3AD"          # carries "cannot compete for it"


# ------------------------------------------------------------------ treemap

def _treemap_fig(rows: list, note: str):
    """Their external financial life as area. rows:
    [[label, value, sub, addressable]]. Only an ADDRESSABLE block is lit --
    lighting insurance would point the room at the one category the
    institution cannot sell."""
    rows = sorted(rows, key=lambda r: -r[1])
    shown, dropped = rows[:8], rows[8:]
    lit = next((i for i, r in enumerate(shown) if r[3]), -1)
    total = sum(r[1] for r in shown) or 1
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, 4.6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    x = y = 0.0
    rem_w = rem_h = 1.0
    horizontal = True
    drawn = 0
    for i, (label, val, sub, addressable) in enumerate(shown):
        share = val / total
        remaining = sum(r[1] for r in shown[i:]) / total or 1
        take = share / remaining
        if i == len(shown) - 1:
            w, h = rem_w, rem_h
        elif horizontal:
            w, h = rem_w * take, rem_h
        else:
            w, h = rem_w, rem_h * take
        if i == lit:
            color, fg = ORANGE, "white"
        elif not addressable:
            color, fg = MUTED, "white"
        else:
            color, fg = (NAVY, "white") if i % 2 else (STEEL, "white")
        ax.add_patch(plt.Rectangle((x, y), w, h, facecolor=color,
                                   edgecolor="white", linewidth=1.8))
        if w > 0.10 and h > 0.13:
            inner = w - 0.024                 # the block's width less its margins
            name = fit_text(ax, x + 0.012, y + h - 0.05, inner, label, 10.5, floor=8, max_lines=2,
                            fontweight="bold", color=fg, va="top")
            drop = 0.04 if len(name.get_text().splitlines()) > 1 else 0   # a two-line name pushes the figure down
            ax.text(x + 0.012, y + h - 0.115 - drop, _fmt_money(val), fontsize=13.5,
                    fontweight="bold", color=fg, va="top")
            if h > 0.24 + drop:
                fit_text(ax, x + 0.012, y + h - 0.175 - drop, inner,
                         sub if addressable else "non-addressable", 8.5, floor=7.5,
                         max_lines=2, color="#EEF2F6", va="top")
            drawn += 1
        if horizontal:
            x += w
            rem_w -= w
        else:
            y += h
            rem_h -= h
        horizontal = not horizontal
    cap = []
    if dropped:
        cap.append(f"{len(shown)} of {len(rows)} categories shown")
    if note:
        cap.append(note)
    if cap:
        ax.set_xlabel(" · ".join(cap), fontsize=9.5, color=GREY,
                      labelpad=8)
    return fig, {"blocks": len(shown), "labelled": drawn, "lit_index": lit,
                 "dropped": len(dropped)}


def treemap(rows: list, out: Path, note: str = "") -> Path:
    fig, _ = _treemap_fig(rows, note)
    return _save(fig, out)


# -------------------------------------------------------------------- radar

def _radar_fig(axes: list, a_vals: list, b_vals: list, a_lab: str,
               b_lab: str, raw: list):
    """Six measures as one outline per cohort. a_vals/b_vals are 0-1
    normalised for the shape; ``raw`` carries the real pair per axis and is
    what gets printed -- a normalised number on screen would read as a
    measurement it is not."""
    n = len(axes)
    # wrapped into 0-360: the axes that started at -90 and -30 fell outside the circle once the theta
    # range is the whole of it, so their names and points were not drawn (slide 39, 2026-10-27)
    ang = [((-90 + i * 360 / n) % 360) * math.pi / 180 for i in range(n)]
    fig = plt.figure(figsize=(FIG_W_FULL, 4.6))
    fig._ars_layout_authored = True
    ax = fig.add_axes([0.02, 0.06, 0.40, 0.88], polar=True)
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 1)
    ax.set_yticklabels([])
    ax.set_xticks(ang)
    ax.set_xticklabels(axes, fontsize=9.5, color=GREY)
    ax.grid(color=GRID)
    ax.spines["polar"].set_color(GRID)
    for vals, color, alpha in ((b_vals, TINT, 0.42), (a_vals, ORANGE, 0.38)):
        pts = list(vals) + [vals[0]]
        ax.plot(ang + [ang[0]], pts, color=color, lw=2.4)
        ax.fill(ang + [ang[0]], pts, color=color, alpha=alpha)
    # The whole circle, set AFTER the data: matplotlib 3.11 narrows a polar axes' theta range to the
    # plotted angles, which drew a quarter of the radar and threw the other axis names into the
    # legend column (slide 39, 2026-10-27).
    ax.set_thetalim(0, 2 * math.pi)
    ax.set_ylim(0, 1)
    ax.set_position([0.09, 0.10, 0.34, 0.80])   # room left of the circle for the names of its left-hand axes
    tx = fig.add_axes([0.48, 0.06, 0.50, 0.88])
    tx.axis("off")
    tx.set_xlim(0, 1)
    tx.set_ylim(0, 1)
    tx.plot([0.02], [0.95], marker="o", ms=9, color=ORANGE)
    tx.text(0.06, 0.95, a_lab, fontsize=11, fontweight="bold", color=ORANGE,
            va="center")
    tx.plot([0.02], [0.87], marker="o", ms=9, color=TINT)
    tx.text(0.06, 0.87, b_lab, fontsize=11, fontweight="bold", color=GREY,
            va="center")
    for i, label in enumerate(axes):
        yy = 0.74 - i * 0.115
        tx.text(0.02, yy, label, fontsize=10.5, color=NAVY, va="center")
        tx.text(1.0, yy, raw[i], fontsize=10.5, fontweight="bold",
                color=GREY, ha="right", va="center")
    return fig, {"axes": n, "series": 2, "raw_printed": len(raw)}


def radar(axes: list, a_vals: list, b_vals: list, a_lab: str, b_lab: str,
          raw: list, out: Path) -> Path:
    fig, _ = _radar_fig(axes, a_vals, b_vals, a_lab, b_lab, raw)
    return _save(fig, out)


# ------------------------------------------------------------------- bullet

def _bullet_fig(rows: list, book_label: str):
    """Actual against the book, with the observed spread behind it. A
    decorative band would imply a threshold nobody set.
    rows: [[label, actual, book, note]]."""
    peak = max(max(r[1], r[2]) for r in rows) * 1.15 or 1
    lo = min(r[1] for r in rows)
    hi = max(r[1] for r in rows)
    fig, ax = plt.subplots(figsize=(FIG_W_RAIL, 4.6))
    y = np.arange(len(rows))[::-1]
    below = 0
    for i, (label, act, book, note) in enumerate(rows):
        ax.barh(y[i], peak, height=0.62, color="#F2F5F8")
        ax.barh(y[i], hi - lo, left=lo, height=0.62, color="#E7ECF2")
        good = act >= book
        below += 0 if good else 1
        ax.barh(y[i], act, height=0.30, color=NAVY if good else ORANGE)
        ax.plot([book, book], [y[i] - 0.36, y[i] + 0.36], color=NAVY, lw=2.4)
        ax.text(peak * 1.02, y[i], note, va="center", fontsize=10.5,
                fontweight="bold", color=NAVY if good else ORANGE)
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=10.5, color=NAVY)
    ax.set_xlim(0, peak * 1.24)
    ax.get_xaxis().set_visible(False)
    ax.set_xlabel(f"the rule is {book_label}; the darker band is the spread "
                  f"across these groups", fontsize=9.5, color=GREY,
                  labelpad=8)
    ax.get_xaxis().set_visible(True)
    ax.set_xticks([])
    _clean(ax, bottom=False)
    return fig, {"rows": len(rows), "below_book": below,
                 "band": (lo, hi)}


def bullet(rows: list, book_label: str, out: Path) -> Path:
    fig, _ = _bullet_fig(rows, book_label)
    return _save(fig, out)


# ----------------------------------------------------------------- worklist

def _worklist_fig(header: list, rows: list):
    """A mock of the output the banker actually opens, not the method that
    produced it. rows: [[name, detail, value, hot]]."""
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, 4.5))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    rh = min(9.5, 86 / max(len(rows), 1))
    ax.add_patch(plt.Rectangle((0, 100 - rh), 100, rh, facecolor=NAVY))
    cols = (1.5, 28, 63, 87)
    for i, (c, x) in enumerate(zip(header, cols)):
        ax.text(x, 100 - rh / 2, str(c).upper(), fontsize=9,
                fontweight="bold", va="center",
                color="#E9C46A" if i == 0 else "white")
    hot_n = 0
    for i, (name, detail, value, hot) in enumerate(rows):
        yy = 100 - rh - (i + 1) * (rh + 0.9)
        ax.add_patch(plt.Rectangle((0, yy), 100, rh,
                                   facecolor="#FFF3E2" if hot else "#F8F8F8"))
        ax.add_patch(plt.Rectangle((0, yy), 0.5, rh,
                                   facecolor=ORANGE if hot else GRID))
        ax.text(cols[0], yy + rh / 2, name, fontsize=10.5,
                fontweight="bold" if hot else "normal", color=NAVY,
                va="center")
        ax.text(cols[1], yy + rh / 2, detail, fontsize=9.5, color=GREY,
                va="center")
        ax.text(cols[2], yy + rh / 2, value, fontsize=10.5,
                fontweight="bold", color=ORANGE if hot else NAVY, va="center")
        ax.text(cols[3], yy + rh / 2, "call first" if hot else "queue",
                fontsize=9.5, fontweight="bold",
                color=ORANGE if hot else MUTED, va="center")
        hot_n += 1 if hot else 0
    return fig, {"rows": len(rows), "flagged": hot_n}


def worklist(header: list, rows: list, out: Path) -> Path:
    fig, _ = _worklist_fig(header, rows)
    return _save(fig, out)


# ------------------------------------------------------------------- ledger

def _ledger_fig(rows: list, note: str):
    """One named row per counterparty: the name, a bar for its weight, its dollars -- the flagged
    rows in orange. rows: [[label, weight, dollars, flagged]].

    It used to draw twenty unnamed bars on the left and a separate block of the flagged names on
    the right, which lined up with nothing (2026-10-28)."""
    peak = max(r[1] for r in rows) or 1
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, 4.5))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    rh = min(4.2, 88 / max(len(rows), 1))
    size = 9 if len(rows) <= 12 else 8
    flagged = 0
    for i, (label, weight, dollars, flag) in enumerate(rows):
        yy = 94 - (i + 1) * rh
        mid = yy + rh * 0.33
        w = 46 * weight / peak
        ax.text(31, mid, clip(str(label).title(), 30), fontsize=size,
                fontweight="bold" if flag else "normal", color=NAVY if flag else GREY,
                ha="right", va="center")
        ax.add_patch(plt.Rectangle((33, yy), w, rh * 0.66,
                                   facecolor=ORANGE if flag else "#C9D3DC"))
        ax.text(33 + w + 1, mid, _fmt_money(dollars), fontsize=size,
                fontweight="bold" if flag else "normal", color=NAVY if flag else GREY,
                ha="left", va="center")
        flagged += bool(flag)
    if note:
        ax.text(0, 2, note, fontsize=9.5, color=GREY)
    return fig, {"rows": len(rows), "flagged": flagged}


def ledger(rows: list, out: Path, note: str = "") -> Path:
    fig, _ = _ledger_fig(rows, note)
    return _save(fig, out)
