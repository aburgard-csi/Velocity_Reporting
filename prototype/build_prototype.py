#!/usr/bin/env python3
"""
build_prototype.py — a TEST-ONLY prototype of the redesigned Executive Review.

Builds the deck described in docs/STYLE-PROPOSAL-2026-10-02.md from the Marine FCU
2026.09 figures already on hand (the launcher's metrics/base/lift packs and the VIP
sheets), so the look can be judged on real numbers before any builder changes.

It is deliberately standalone: nothing in build/, templates/ or validation/ is
touched, and the output goes to the session scratchpad, never to Outputs/.
Only build/brand.py (the palette) and build/rpe_env.py (fonts, logo) are imported.

    .venv/Scripts/python prototype/build_prototype.py <data_dir> <out.pptx>
"""
import json
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "build"))
import brand  # noqa: E402
import rpe_env  # noqa: E402

# ----------------------------------------------------------------- palette / type
NAVY, ORANGE, TICK, TILE, ROWALT = brand.NAVY, brand.ORANGE, brand.TICK, brand.TILE, brand.ROWALT
STEEL, STEEL_SOFT, LIGHT, HAIRLINE, MUTED, PEACH, TEAL = (
    brand.STEEL, brand.STEEL_SOFT, brand.LIGHT, brand.HAIRLINE, brand.MUTED, brand.PEACH, brand.TEAL)
WHITE = "#FFFFFF"
PEACH_TINT = "#FDE8D8"   # 30% PEACH on white — a tint, not a new palette entry

HERO = "Montserrat ExtraBold"
HEAD = "Montserrat SemiBold"
KICK = "Montserrat"       # bold run
BODY = "Calibri"
CHART = "Carlito"

def rgb(hx):
    return RGBColor.from_string(hx.lstrip("#"))

# ----------------------------------------------------------------- grid
SW, SH = 13.333, 7.5
MARGIN, GUTTER, NCOL = 0.5, 0.2, 12
COLW = (SW - 2 * MARGIN - (NCOL - 1) * GUTTER) / NCOL

def span(c0, n):
    """x, w in inches for columns c0 .. c0+n-1 (0-based)."""
    return MARGIN + c0 * (COLW + GUTTER), n * COLW + (n - 1) * GUTTER

Y_KICK, Y_HEAD, Y_BAND, Y_BAND_END, Y_FOOT = 0.45, 0.95, 2.15, 6.75, 7.02

# ----------------------------------------------------------------- pptx primitives
def _no_shadow(shape):
    shape.shadow.inherit = False

def tb(slide, x, y, w, h, text, size=16, font=BODY, color=NAVY, bold=False,
       align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, italic=False, spacing=None, wrap=True):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = wrap
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    lines = text if isinstance(text, list) else [text]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if spacing:
            p.line_spacing = spacing
        runs = line if isinstance(line, list) else [(line, {})]
        for seg in runs:
            txt, st = seg if isinstance(seg, tuple) else (seg, {})
            r = p.add_run()
            r.text = txt
            f = r.font
            f.name = st.get("font", font)
            f.size = Pt(st.get("size", size))
            f.bold = st.get("bold", bold)
            f.italic = st.get("italic", italic)
            f.color.rgb = rgb(st.get("color", color))
    return box

def rect(slide, x, y, w, h, fill=TILE, radius=0.1, line=None, line_w=1.0):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
                                 Inches(x), Inches(y), Inches(w), Inches(h))
    if radius:
        shp.adjustments[0] = min(0.5, radius / min(w, h))
    if fill:
        shp.fill.solid(); shp.fill.fore_color.rgb = rgb(fill)
    else:
        shp.fill.background()
    if line:
        shp.line.color.rgb = rgb(line); shp.line.width = Pt(line_w)
    else:
        shp.line.fill.background()
    _no_shadow(shp)
    return shp

def hline(slide, x, y, w, color=HAIRLINE, weight=0.75):
    ln = slide.shapes.add_connector(1, Inches(x), Inches(y), Inches(x + w), Inches(y))
    ln.line.color.rgb = rgb(color); ln.line.width = Pt(weight)
    return ln

def pic(slide, path, x, y, w=None, h=None):
    kw = {}
    if w: kw["width"] = Inches(w)
    if h: kw["height"] = Inches(h)
    return slide.shapes.add_picture(str(path), Inches(x), Inches(y), **kw)

def navy_bg(slide):
    bg = slide.background.fill
    bg.solid(); bg.fore_color.rgb = rgb(NAVY)

def tile_bg(slide):
    bg = slide.background.fill
    bg.solid(); bg.fore_color.rgb = rgb(TILE)

# ----------------------------------------------------------------- components
def chip(slide, x, y, text, w=None, dark=False):
    w = w or (0.11 * len(text) + 0.45)
    r = rect(slide, x, y, w, 0.32, fill=(WHITE if dark else None), radius=0.16,
             line=(None if dark else NAVY), line_w=1.0)
    tb(slide, x, y, w, 0.32, text, size=11, font=KICK, bold=True, color=NAVY,
       align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    return w

def kicker_row(slide, kicker, period, dark=False):
    col = WHITE if dark else TICK
    tb(slide, MARGIN, Y_KICK, 6, 0.3, kicker.upper(), size=11, font=KICK, bold=True, color=col,
       anchor=MSO_ANCHOR.MIDDLE)
    if period:
        w = 0.11 * len(period) + 0.45
        chip(slide, SW - MARGIN - w, Y_KICK - 0.01, period, w=w, dark=dark)

def headline(slide, text, dark=False, size=None, w=12.33):
    """Two lines, never three: the size steps down with length (≈62 chars per line at 28 pt)."""
    if size is None:
        n = len(text)
        size = 28 if n <= 105 else 25 if n <= 124 else 23 if n <= 140 else 21
    tb(slide, MARGIN, Y_HEAD, w, 1.1, text, size=size, font=HEAD, color=(WHITE if dark else NAVY),
       anchor=MSO_ANCHOR.TOP, spacing=1.05)

def footer(slide, n, selection="", client="Marine FCU", month="September 2026", dark=False):
    col = "#9DB8CC" if dark else TICK
    parts = [p for p in (selection, client, f"Executive Review · {month}") if p]
    tb(slide, MARGIN, Y_FOOT, 10.6, 0.3, "   ·   ".join(parts), size=10, font=BODY, color=col,
       anchor=MSO_ANCHOR.MIDDLE)
    tb(slide, 11.1, Y_FOOT, 0.5, 0.3, str(n), size=10, font=BODY, color=col, bold=True,
       align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)
    lockup(slide, SW - MARGIN - 1.1, Y_FOOT - 0.02, 1.1, dark)

def lockup(slide, x, y, w, dark=False):
    if dark:
        rect(slide, x - 0.1, y - 0.07, w + 0.2, w * 158 / 498 + 0.14, fill=WHITE, radius=0.08)
    pic(slide, REPO / "build" / "assets" / "logo.png", x, y, w=w)

def delta(slide, x, y, w, pct, ref, up_is_good=True, size=13):
    """A delta chip: ▲ in orange when the move is positive, ▼ / ≈ in grey otherwise."""
    if abs(pct) < 2:
        txt, col = f"≈  flat vs {ref}", TICK
    elif pct > 0:
        txt, col = f"▲  {pct:+.1f}% vs {ref}", ORANGE
    else:
        txt, col = f"▼  {pct:+.1f}% vs {ref}", TICK
    tb(slide, x, y, w, 0.3, txt, size=size, font=BODY, color=col, bold=True, anchor=MSO_ANCHOR.MIDDLE)

def hero_cell(slide, x, y, w, h, value, label, sub=None, navy=True, vsize=84, dpct=None, dref=None):
    """Laid out from the bottom up: sub/delta line, label, then the value fills what is left."""
    fill = NAVY if navy else TILE
    rect(slide, x, y, w, h, fill=fill, radius=0.12)
    vc = WHITE if navy else NAVY
    lc = "#CFDBE8" if navy else TICK
    pad = 0.3
    block = 0.42 + (0.5 if (sub or dpct is not None) else 0)
    y_label = y + h - pad - block
    tb(slide, x + pad, y + pad, w - 2 * pad, max(0.5, y_label - y - pad - 0.05), value, size=vsize, font=HERO,
       color=vc, anchor=MSO_ANCHOR.BOTTOM, wrap=False)
    tb(slide, x + pad, y_label, w - 2 * pad, 0.42, label, size=16, font=BODY, color=lc)
    if dpct is not None:
        delta(slide, x + pad, y_label + 0.45, w - 2 * pad, dpct, dref)
    elif sub:
        tb(slide, x + pad, y_label + 0.45, w - 2 * pad, 0.5, sub, size=13, font=BODY, color=lc)

def stat_cell(slide, x, y, w, h, value, label, dpct=None, dref=None, vsize=32, spark=None, orange=False):
    rect(slide, x, y, w, h, fill=TILE, radius=0.1)
    pad = 0.2
    vh = vsize / 72 * 1.25
    tb(slide, x + pad, y + pad - 0.04, w - 2 * pad, vh, value, size=vsize, font=HERO,
       color=(ORANGE if orange else NAVY), anchor=MSO_ANCHOR.TOP, wrap=False)
    y_label = y + pad + vh - 0.02
    tb(slide, x + pad, y_label, w - 2 * pad, 0.3, label, size=13, font=BODY, color=TICK)
    if dpct is not None:
        delta(slide, x + pad, y_label + 0.3, w - 2 * pad, dpct, dref, size=12)
    if spark:
        pic(slide, spark, x + w - pad - 1.3, y + pad + 0.02, w=1.3)

def action_card(slide, x, y, w, h, n, title, body, figure):
    rect(slide, x, y, w, h, fill=WHITE, radius=0.12)
    rect(slide, x + 0.3, y + 0.3, 0.42, 0.42, fill=ORANGE, radius=0.21)
    tb(slide, x + 0.3, y + 0.3, 0.42, 0.42, str(n), size=15, font=KICK, bold=True, color=WHITE,
       align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    tb(slide, x + 0.3, y + 0.9, w - 0.6, 0.9, title, size=19, font=HEAD, color=NAVY, spacing=1.05)
    tb(slide, x + 0.3, y + 1.85, w - 0.6, h - 2.9, body, size=14, font=BODY, color=TICK, spacing=1.1)
    tb(slide, x + 0.3, y + h - 0.95, w - 0.6, 0.65, figure, size=13, font=BODY, color=NAVY, bold=True,
       anchor=MSO_ANCHOR.BOTTOM)

def flat_table(slide, x, y, w, rows, col_w, highlight=None, size=13, row_h=0.36, align=None):
    """Navy header text over a navy rule, zebra rows, right-aligned numbers, one tinted row."""
    nrow, ncol = len(rows), len(rows[0])
    shp = slide.shapes.add_table(nrow, ncol, Inches(x), Inches(y), Inches(w), Inches(row_h * nrow))
    tbl = shp.table
    # no table style: strip the style id so no borders/banding are inherited
    tblPr = tbl._tbl.tblPr
    for sid in tblPr.findall(qn("a:tableStyleId")):
        tblPr.remove(sid)
    sid = tblPr.makeelement(qn("a:tableStyleId"), {})
    sid.text = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"   # No Style, No Grid
    tblPr.append(sid)
    tblPr.set("firstRow", "0"); tblPr.set("bandRow", "0")
    for j, cw in enumerate(col_w):
        tbl.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        tbl.rows[i].height = Inches(row_h)
        for j, val in enumerate(row):
            c = tbl.cell(i, j)
            c.margin_left = c.margin_right = Inches(0.08)
            c.margin_top = c.margin_bottom = Inches(0.03)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            if i == 0:
                c.fill.background()
            elif highlight is not None and i == highlight:
                c.fill.solid(); c.fill.fore_color.rgb = rgb(PEACH_TINT)
            elif i % 2 == 0:
                c.fill.solid(); c.fill.fore_color.rgb = rgb(ROWALT)
            else:
                c.fill.background()
            tf = c.text_frame
            p = tf.paragraphs[0]
            p.text = ""
            r = p.add_run(); r.text = str(val)
            r.font.name = BODY; r.font.size = Pt(size)
            r.font.bold = (i == 0) or (highlight is not None and i == highlight)
            r.font.color.rgb = rgb(NAVY)
            a = (align[j] if align else (PP_ALIGN.LEFT if j == 0 else PP_ALIGN.RIGHT))
            p.alignment = a
    # kill every cell border (the default table style draws them)
    for i in range(nrow):
        for j in range(ncol):
            tcPr = tbl.cell(i, j)._tc.get_or_add_tcPr()
            for k, side in enumerate(("a:lnL", "a:lnR", "a:lnT", "a:lnB")):   # schema order
                for old in tcPr.findall(qn(side)):
                    tcPr.remove(old)
                ln = tcPr.makeelement(qn(side), {"w": "0"})
                ln.append(ln.makeelement(qn("a:noFill"), {}))
                tcPr.insert(k, ln)
    hline(slide, x, y + row_h, w, color=NAVY, weight=1.5)
    return shp

def progress_track(slide, programs, current, y=6.55, dark=True):
    x0, w = MARGIN, SW - 2 * MARGIN
    hline(slide, x0, y + 0.35, w, color=("#3D5A7A" if dark else HAIRLINE), weight=1)
    seg = w / len(programs)
    for i, p in enumerate(programs):
        on = (p == current)
        col = ORANGE if on else ("#9DB8CC" if dark else MUTED)
        tb(slide, x0 + i * seg, y, seg, 0.3, p.upper(), size=11, font=KICK, bold=True, color=col)
        if on:
            hline(slide, x0 + i * seg, y + 0.35, seg, color=ORANGE, weight=3)

# ----------------------------------------------------------------- charts
def chart_setup():
    rpe_env.register_bundled_fonts()
    for fam in (CHART, "Montserrat"):
        if fam not in set(font_manager.get_font_names()):
            raise SystemExit(f"font {fam} not registered")
    plt.rcParams.update({
        "font.family": CHART, "font.size": 12, "axes.edgecolor": HAIRLINE, "axes.linewidth": 0.8,
        "xtick.color": TICK, "ytick.color": TICK, "axes.labelcolor": TICK,
        "figure.facecolor": "none", "axes.facecolor": "none", "savefig.facecolor": "none",
    })

def clean_axes(ax, left=False, bottom=True):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_visible(left)
    ax.spines["bottom"].set_visible(bottom)
    ax.tick_params(length=0)
    if not left:
        ax.set_yticks([])
    ax.grid(False)

def save(fig, path):
    fig.savefig(path, dpi=200, bbox_inches=None, pad_inches=0, transparent=True)
    plt.close(fig)

def mon_yy(label):
    """'Sep 2023' / 'Sep 23' / 'Sep23' -> Sep'23"""
    m = label[:3]
    y = label.strip()[-2:]
    return f"{m}'{y}"

def c_bars(path, labels, values, w, h, highlight=-1, hatched=None, fmt="{:,.0f}", ann=None,
           every=1, avg=None, avg_label=None, goal=None, goal_label=None, ymax=None, label_all=True):
    fig, ax = plt.subplots(figsize=(w, h))
    n = len(values)
    cols = [NAVY] * n
    if highlight is not None and highlight != -1:
        cols[highlight] = ORANGE
    bars = ax.bar(range(n), values, color=cols, width=0.72, zorder=3)
    if hatched is not None:
        bars[hatched].set_facecolor(STEEL_SOFT); bars[hatched].set_alpha(0.42)
        bars[hatched].set_hatch("//"); bars[hatched].set_edgecolor(WHITE)
    clean_axes(ax)
    ax.set_xticks(range(0, n, every))
    ax.set_xticklabels([mon_yy(l) for l in labels[::every]], rotation=45 if n > 14 else 0,
                       ha="right" if n > 14 else "center", fontsize=11)
    top = (ymax or max(values)) * 1.18
    ax.set_ylim(0, top)
    if label_all or n <= 16:
        for i, v in enumerate(values):
            if v == 0:
                continue
            ax.text(i, v + top * 0.015, fmt.format(v), ha="center", va="bottom", fontsize=11,
                    color=(ORANGE if i == highlight else NAVY), fontweight=("bold" if i == highlight else "normal"))
    elif not ann:
        i = highlight
        ax.text(i, values[i] + top * 0.015, fmt.format(values[i]), ha="center", va="bottom", fontsize=12,
                color=ORANGE, fontweight="bold")
    if avg is not None:
        ax.axhline(avg, color=NAVY, lw=1, ls=(0, (4, 3)), zorder=4)
        ax.set_xlim(-0.6, n + 3.2)
        ax.text(n + 0.1, avg, avg_label, ha="left", va="center", fontsize=11, color=NAVY, zorder=6,
                bbox=dict(facecolor=WHITE, edgecolor="none", pad=1.5))
    if goal is not None:
        ax.plot(range(n), goal, color=TICK, lw=1.2, ls=(0, (4, 3)), zorder=4)
        ax.text(n - 0.6, goal[-1] - top * 0.02, goal_label, ha="right", va="top", fontsize=11, color=TICK)
    if ann:
        i, text = ann
        ax.annotate(text, xy=(i, values[i]), xytext=(i - 0.6, values[i] + top * 0.14), ha="right",
                    fontsize=12, color=ORANGE, fontweight="bold", fontfamily="Montserrat",
                    arrowprops=dict(arrowstyle="-", color=ORANGE, lw=0.75))
    fig.subplots_adjust(left=0.01, right=0.99, top=0.97, bottom=0.2 if n > 14 else 0.12)
    save(fig, path)

def c_hbars(path, names, rates, counts, w, h, highlight_name=None, fmt="{:.0f}%", count_label="cards",
            xmax=None):
    fig, ax = plt.subplots(figsize=(w, h))
    n = len(names)
    ys = list(range(n))[::-1]
    cols = [ORANGE if nm == highlight_name else NAVY for nm in names]
    ax.barh(ys, rates, color=cols, height=0.62, zorder=3)
    clean_axes(ax, bottom=False)
    ax.set_xticks([])
    xm = xmax or max(rates) * 1.25
    ax.set_xlim(0, xm)
    ax.set_ylim(-0.6, n + 0.15)
    for y, nm, r, c in zip(ys, names, rates, counts):
        col = ORANGE if nm == highlight_name else NAVY
        ax.text(-xm * 0.015, y, nm, ha="right", va="center", fontsize=12, color=col,
                fontweight=("bold" if nm == highlight_name else "normal"))
        ax.text(r + xm * 0.012, y, fmt.format(r), ha="left", va="center", fontsize=12, color=col,
                fontweight="bold")
        ax.text(xm, y, (c if isinstance(c, str) else f"{c:,}"), ha="right", va="center", fontsize=11, color=TICK)
    ax.text(xm, n - 0.45, count_label, ha="right", va="bottom", fontsize=10, color=TICK)
    fig.subplots_adjust(left=0.2, right=0.99, top=0.99, bottom=0.02)
    save(fig, path)

def c_spark(path, values, w=1.3, h=0.42):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.plot(range(len(values)), values, color=NAVY, lw=1.2)
    ax.plot([len(values) - 1], [values[-1]], "o", color=ORANGE, ms=4)
    ax.axis("off")
    fig.subplots_adjust(left=0.02, right=0.95, top=0.9, bottom=0.1)
    save(fig, path)

def c_grouped(path, labels, before, after, w, h, fmt="${:,.0f}"):
    fig, ax = plt.subplots(figsize=(w, h))
    n = len(labels); xs = range(n); bw = 0.38
    ax.bar([x - bw / 2 for x in xs], before, bw, color=STEEL_SOFT, zorder=3)
    ax.bar([x + bw / 2 for x in xs], after, bw, color=NAVY, zorder=3)
    clean_axes(ax)
    ax.set_xticks(list(xs)); ax.set_xticklabels([mon_yy(l) for l in labels], fontsize=11)
    top = max(after) * 1.2; ax.set_ylim(0, top)
    for x, b, a in zip(xs, before, after):
        ax.text(x - bw / 2, b + top * 0.015, fmt.format(b), ha="center", va="bottom", fontsize=10, color=TICK)
        ax.text(x + bw / 2, a + top * 0.015, fmt.format(a), ha="center", va="bottom", fontsize=10, color=NAVY)
    ax.add_patch(plt.Rectangle((-0.45, top * 0.925), 0.18, top * 0.045, color=STEEL_SOFT, clip_on=False))
    ax.text(-0.15, top * 0.95, "before: 3-month baseline", color=TICK, fontsize=11, va="center")
    ax.add_patch(plt.Rectangle((2.45, top * 0.925), 0.18, top * 0.045, color=NAVY, clip_on=False))
    ax.text(2.75, top * 0.95, "after: the 6 months following the mailing", color=NAVY, fontsize=11, va="center")
    fig.subplots_adjust(left=0.01, right=0.99, top=0.95, bottom=0.12)
    save(fig, path)

def c_stacked(path, labels, series, colors, names, w, h, hatched_last=True):
    fig, ax = plt.subplots(figsize=(w, h))
    n = len(labels); bottom = [0] * n
    bars_by = []
    for vals, col in zip(series, colors):
        b = ax.bar(range(n), vals, bottom=bottom, color=col, width=0.72, zorder=3)
        bars_by.append(b)
        bottom = [bo + v for bo, v in zip(bottom, vals)]
    if hatched_last:
        for b in bars_by:
            b[-1].set_alpha(0.42); b[-1].set_hatch("//"); b[-1].set_edgecolor(WHITE)
    clean_axes(ax)
    ax.set_xticks(range(n)); ax.set_xticklabels([mon_yy(l) for l in labels], rotation=45, ha="right", fontsize=11)
    top = max(bottom) * 1.2; ax.set_ylim(0, top)
    for i, t in enumerate(bottom):
        col = ORANGE if i == n - 2 else NAVY
        ax.text(i, t + top * 0.015, f"{t:,}", ha="center", va="bottom", fontsize=11, color=col,
                fontweight=("bold" if i == n - 2 else "normal"))
    # direct labels on the last complete bar
    i = n - 2; acc = 0
    for vals, col, nm in zip(series, colors, names):
        ax.text(i + 0.5, acc + vals[i] / 2, nm, ha="left", va="center", fontsize=11, color=col, fontweight="bold")
        acc += vals[i]
    fig.subplots_adjust(left=0.01, right=0.93, top=0.97, bottom=0.2)
    save(fig, path)

def c_heat(path, rows, cols, matrix, w, h, example=(1, 2)):
    import numpy as np
    fig, ax = plt.subplots(figsize=(w, h))
    vals = [v for r in matrix for v in r if v is not None]
    vmin, vmax = min(vals), max(vals)
    ramp = brand.COLD_RAMP[::-1]
    for i, r in enumerate(matrix):
        for j, v in enumerate(r):
            if v is None:
                ax.text(j + 0.5, i + 0.5, "—", ha="center", va="center", color=MUTED, fontsize=12)
                continue
            t = (v - vmin) / (vmax - vmin)
            col = ramp[int(t * (len(ramp) - 1))]
            ax.add_patch(plt.Rectangle((j + 0.04, i + 0.04), 0.92, 0.92, color=col))
            dark = t > 0.45
            ax.text(j + 0.5, i + 0.5, f"${v:.2f}", ha="center", va="center", fontsize=12,
                    color=(WHITE if dark else NAVY), fontweight="bold")
    ei, ej = example
    ax.add_patch(plt.Rectangle((ej + 0.04, ei + 0.04), 0.92, 0.92, fill=False, ec=ORANGE, lw=2.5))
    ax.set_xlim(0, len(cols)); ax.set_ylim(len(rows), 0)
    ax.set_xticks([j + 0.5 for j in range(len(cols))]); ax.set_xticklabels(cols, fontsize=12, color=NAVY)
    ax.xaxis.tick_top()
    ax.set_yticks([i + 0.5 for i in range(len(rows))]); ax.set_yticklabels(rows, fontsize=12, color=NAVY)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    ax.text(-0.1, -0.35, "from ↓   to →", ha="right", va="center", fontsize=10, color=TICK)
    fig.subplots_adjust(left=0.14, right=0.99, top=0.9, bottom=0.02)
    save(fig, path)

def c_paired(path, labels, cohort, client, w, h, fmts):
    """Peer comparison: two dots per metric on a normalised scale, index 100 = cohort."""
    fig, ax = plt.subplots(figsize=(w, h))
    n = len(labels); ys = list(range(n))[::-1]
    for y, lab, co, cl, f in zip(ys, labels, cohort, client, fmts):
        idx = cl / co * 100
        ax.plot([0, 300], [y, y], color=HAIRLINE, lw=1, zorder=1)
        ax.plot([100], [y], "o", color=MUTED, ms=9, zorder=3)
        ax.plot([min(idx, 290)], [y], "o", color=(ORANGE if idx >= 100 else NAVY), ms=11, zorder=4)
        ax.text(-8, y, lab, ha="right", va="center", fontsize=12, color=NAVY)
        ax.text(min(idx, 290) + 8, y, f.format(cl), ha="left", va="center", fontsize=12, color=NAVY, fontweight="bold")
        ax.text(100, y + 0.33, f.format(co), ha="center", va="bottom", fontsize=10, color=TICK)
    ax.axvline(100, color=MUTED, lw=1, ls=(0, (3, 3)))
    ax.text(100, -0.75, "client average = 100", ha="center", fontsize=10, color=TICK)
    ax.set_xlim(0, 300); ax.set_ylim(-1, n)
    ax.axis("off")
    fig.subplots_adjust(left=0.3, right=0.97, top=0.97, bottom=0.03)
    save(fig, path)

# ----------------------------------------------------------------- the deck
def build(data_dir: Path, out: Path):
    chart_setup()
    cd = out.parent / "charts"; cd.mkdir(parents=True, exist_ok=True)
    m = json.load(open(data_dir / "metrics.json", encoding="utf-8"))
    b = json.load(open(data_dir / "base.json", encoding="utf-8"))
    lf = json.load(open(data_dir / "lift.json", encoding="utf-8"))
    ics = json.load(open(data_dir / "1539_ics.json", encoding="utf-8"))
    mr = json.load(open(data_dir / "1539_mrpc.json", encoding="utf-8"))
    client_logo = data_dir / "logo_trim_1539.png.png"

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(SW), Inches(SH)
    blank = prs.slide_layouts[6]
    n_slide = [0]

    def new(dark=False, tile=False):
        s = prs.slides.add_slide(blank)
        if dark: navy_bg(s)
        if tile: tile_bg(s)
        n_slide[0] += 1
        return s

    def notes(slide, text):
        slide.notes_slide.notes_text_frame.text = text

    # ---- derived figures ------------------------------------------------------
    ss = b["swipespend_36"]                       # [month, spend $M, accounts w/ card]
    spend_now, spend_yr = ss[-1][1], ss[-13][1]
    spend_yoy = (spend_now / spend_yr - 1) * 100
    cards_now, cards_36 = ss[-1][2], ss[0][2]
    cards_36_pct = (cards_now / cards_36 - 1) * 100
    ltd_rev, ltd_cost, ltd_profit = b["ltd_revenue"], -b["ltd_costs"], b["ltd_profit"]
    cur_rev, cur_profit = b["cur_revenue"], b["cur_profit"]
    # the production definition (revenue_guarantee_slide.guarantee): ratio = revenue / cost,
    # guaranteed minimum = 2 x cost, surplus = revenue - minimum
    ratio = ltd_rev / ltd_cost
    guaranteed_min = 2 * ltd_cost
    surplus = ltd_rev - guaranteed_min
    lines = {name: sum(vals) for name, vals in b["actuals"]["lines"]}
    ms = m["mail_summary"]                        # newest first
    resp_rates = [r[5] for r in ms][::-1]; resp_labels = [r[0] for r in ms][::-1]
    trailing_resp = m["mail_summary_total"][4]
    ba = m["before_after"]
    nsf = m["nsf_series"]
    take = sorted(m["take_branch"], key=lambda r: -r[2])[:12]
    rege = [r for r in m["rege_branch"] if not r[0].isdigit()]
    rege = sorted(rege, key=lambda r: -r[2])[:12]
    rege_sorted = sorted(rege, key=lambda r: -r[3])
    take_sorted = sorted(take, key=lambda r: -r[3])
    ref = ics["referrals"]; tr = ref["trend"]
    ics_br = ref["by_branch"]["branches"]
    ics_total_ytd = ref["year_to_date"]
    top5 = sorted(ics_br, key=lambda r: -r["referrals"])[:5]
    top5_pct = sum(r["referrals"] for r in top5) / ics_total_ytd * 100
    en = mr["enrollments_by_month"]
    rev = mr["revenue"]["by_month"]

    # ---- charts ----------------------------------------------------------------
    c_spark(cd / "sp_rev.png", [v for _, v in b["monthly_rev_last12"]])
    c_spark(cd / "sp_ics.png", tr["referrals"][-13:-1])
    c_spark(cd / "sp_mrpc.png", en["totals"][-13:-1])
    c_spark(cd / "sp_cp.png", [1, 1, 1])  # no monthly series on hand; a flat placeholder, labelled on the slide
    bw, bh = span(0, 8)[1], 3.9
    c_bars(cd / "resp.png", resp_labels, resp_rates, bw, bh, highlight=len(resp_rates) - 1, fmt="{:.1f}%",
           avg=trailing_resp, avg_label=f"12-mailing avg {trailing_resp:.1f}%", ymax=22)
    c_grouped(cd / "ba.png", [r["m"] for r in ba], [r["sb_mean"] for r in ba], [r["sa_mean"] for r in ba], bw, bh)
    c_bars(cd / "spend.png", [r[0] for r in ss], [r[1] for r in ss], bw, bh, highlight=len(ss) - 1,
           fmt="${:.1f}M", every=3, label_all=False, ann=(len(ss) - 1, f"${spend_now:.1f}M, {spend_yoy:+.1f}% vs Aug'25"))
    nsf_labels = [r[0] for r in nsf] + ["Aug 26"]; nsf_vals = [r[1] for r in nsf] + [m["nsf_excluded"][0][1]]
    c_bars(cd / "nsf.png", nsf_labels, nsf_vals, bw, bh, highlight=len(nsf) - 1, hatched=len(nsf), fmt="{:,}",
           every=3, label_all=False, ann=(len(nsf) - 1, f"19,451 in Jul'26, +{m['nsf_yoy']}% vs Jul'25"))
    c_hbars(cd / "take.png", [r[0] for r in take_sorted], [r[3] for r in take_sorted], [r[2] for r in take_sorted],
            span(0, 8)[1], 4.3, highlight_name="Call Center", count_label="accounts opened", xmax=118)
    c_hbars(cd / "rege.png", [r[0] for r in rege_sorted], [r[3] for r in rege_sorted], [r[2] for r in rege_sorted],
            span(0, 8)[1], 4.3, highlight_name="Call Center", count_label="card holders", xmax=62)
    tier = {"NU": "Non-User", "NH": "No card", "26 Plus": "26+"}
    c_heat(cd / "lift.png", [tier.get(r[0], r[0]) for r in lf["matrix_rows"]], [tier.get(c, c) for c in lf["matrix_cols"]],
           [r[1:] for r in lf["matrix_rows"]], span(0, 7)[1], 3.9)
    seg_names = [tier.get(r[0], r[0]) for r in lf["revseg"]]; seg_val = [r[2] for r in lf["revseg"]]; seg_sh = [r[1] * 100 for r in lf["revseg"]]
    c_hbars(cd / "segval.png", seg_names, seg_val, [f"{s:.0f}%" for s in seg_sh], span(0, 5)[1], 3.9,
            highlight_name="26+", fmt="${:.2f}", count_label="share of cards", xmax=40)
    c_bars(cd / "ics.png", tr["months"], tr["referrals"], bw, bh, highlight=len(tr["months"]) - 2,
           hatched=len(tr["months"]) - 1, goal=tr["goal"], goal_label="goal 80 / month", ymax=150)
    ib = sorted([r for r in ics_br if r.get("goal")], key=lambda r: -r["referrals"])[:12]
    c_hbars(cd / "icsbr.png", [r["name"].replace(" Branch", "") for r in ib],
            [r["referrals"] / r["goal"] * 100 for r in ib], [r["referrals"] for r in ib], span(0, 8)[1], 4.3,
            highlight_name="Corporate", count_label="referrals YTD", xmax=210)
    c_stacked(cd / "mrpc.png", en["months"], [en["platinum"], en["gold"]], [STEEL_SOFT, ORANGE], ["Platinum", "Gold"], bw, bh)
    c_bars(cd / "mrev.png", rev["months"], rev["revenue"], bw, bh, highlight=len(rev["months"]) - 1, fmt="${:,.0f}", ymax=9500)
    cp_labels = ["Loans per 1,000 DDAs", "Loans paid off", "Average loan size", "Interest per loan", "Charge-off rate"]
    cp_cohort = [17.0, 82.7, 569, 34, 6.29]; cp_client = [39.6, 88.6, 403, 12, 4.94]
    c_paired(cd / "cp.png", cp_labels, cp_cohort, cp_client, span(0, 7)[1], 3.6,
             ["{:.1f}", "{:.1f}%", "${:,.0f}", "${:,.0f}", "{:.2f}%"])

    SRC_ODD = "Source: 1539 Marine FCU ODD extract, pulled 09/04/26 (Aug 2026 data), via the 2026.09 launcher data pack."
    SRC_WB = "Source: ARS Workbook 1539 — Marine FCU, Executive Financials MM / Actuals MM, data through Aug 2026."
    SRC_VIP_ICS = "Source: VIP ICS Referral Data dashboard for Marine FCU (1539), pulled 2026-10-01."
    SRC_VIP_MRPC = "Source: VIP MyRewards Premium Cards dashboards for Marine FCU (1539), pulled 2026-10-01."
    SRC_CP = "Source: CashPlease Summary workbook (Bradford Sanders), generated 2026-09-27; figures as shipped in the 2026.09 deck."

    # ================================================================ 1 cover
    s = new(dark=True)
    rect(s, MARGIN, 0.5, 2.9, 1.0, fill=WHITE, radius=0.1)
    lw, lh = rpe_env.fit_box(client_logo, 2.5, 0.7)
    pic(s, client_logo, MARGIN + (2.9 - lw) / 2, 0.5 + (1.0 - lh) / 2, w=lw)
    tb(s, MARGIN, 2.4, 12, 0.4, "EXECUTIVE REVIEW", size=14, font=KICK, bold=True, color="#9DB8CC")
    tb(s, MARGIN, 2.8, 12, 1.5, "September 2026", size=84, font=HERO, color=WHITE)
    tb(s, MARGIN, 4.35, 12, 0.7, "Marine FCU", size=32, font=HEAD, color=ORANGE)
    x = MARGIN
    for prod in ("Account Revenue Solution®", "Invitation Checking® System", "MyRewards Premium Cards®", "CashPlease®"):
        w = 0.105 * len(prod) + 0.5
        rect(s, x, 5.35, w, 0.36, fill=None, radius=0.18, line="#9DB8CC")
        tb(s, x, 5.35, w, 0.36, prod, size=12, font=KICK, bold=True, color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        x += w + 0.15
    lockup(s, SW - MARGIN - 1.6, 6.5, 1.6, dark=True)
    tb(s, MARGIN, 6.75, 8, 0.3, "Prepared by Aaron Burgard, Client Service Manager   ·   TEST PROTOTYPE — not a client deliverable",
       size=10, font=BODY, color="#9DB8CC")
    notes(s, "Prototype cover. The Executive Summit slide follows the cover unchanged in production; it is omitted here.")

    # ================================================================ 2 executive summary
    s = new()
    kicker_row(s, "Executive summary", "SEP 2026")
    headline(s, f"ARS is returning {ratio:.1f} : 1, referrals are above goal every month this year, "
                "MRPC enrolled 93 in September, and CashPlease lends at twice the client average.")
    y, h = Y_BAND + 0.1, 2.2
    cells = [
        ("ARS", f"{ratio:.1f} : 1", "revenue to fees, PTD", f"${ltd_profit/1e6:.2f}M profit on ${ltd_cost/1e6:.2f}M of fees", cd / "sp_rev.png", "12-month revenue"),
        ("ICS", f"{ref['prev_month_vs_goal_pct']}%", "September vs goal", f"{ref['previous_month']['value']} referrals; {ics_total_ytd} year to date", cd / "sp_ics.png", "12-month referrals"),
        ("MRPC", f"{en['last_complete']['gold'] + en['last_complete']['platinum']}", "enrollments in September", f"{mr['key_metrics']['enrollments_trailing_12']:,} in the last 12 months", cd / "sp_mrpc.png", "12-month enrollments"),
        ("CASHPLEASE", "39.6", "loans per 1,000 DDAs", "client average 17.0; 6,831 loans booked", None, ""),
    ]
    for i, (k, v, lab, sub, spark, sl) in enumerate(cells):
        x, w = span(i * 3, 3)
        rect(s, x, y, w, h, fill=TILE, radius=0.12)
        tb(s, x + 0.25, y + 0.2, w - 0.5, 0.3, k, size=11, font=KICK, bold=True, color=TICK)
        tb(s, x + 0.25, y + 0.45, w - 0.5, 0.9, v, size=44, font=HERO, color=NAVY, anchor=MSO_ANCHOR.MIDDLE, wrap=False)
        tb(s, x + 0.25, y + 1.3, w - 0.5, 0.3, lab, size=14, font=BODY, color=NAVY, bold=True)
        tb(s, x + 0.25, y + 1.58, w - 0.5, 0.55, sub, size=12, font=BODY, color=TICK)
        if spark:
            pic(s, spark, x + w - 0.25 - 1.1, y + 0.18, w=1.1)
            tb(s, x + w - 0.25 - 1.3, y + 0.56, 1.3, 0.22, sl, size=9, font=BODY, color=TICK, align=PP_ALIGN.RIGHT)
    y2 = y + h + 0.2; h2 = Y_BAND_END - y2
    x, w = span(0, 6)
    rect(s, x, y2, w, h2, fill=TILE, radius=0.12)
    tb(s, x + 0.25, y2 + 0.2, w - 0.5, 0.3, "WHAT CHANGED THIS MONTH", size=11, font=KICK, bold=True, color=TICK)
    tb(s, x + 0.25, y2 + 0.55, w - 0.5, h2 - 0.7, [
        f"•  Debit spend was ${spend_now:.1f}M in August, {spend_yoy:+.1f}% on a year ago; card-holding accounts {cards_36_pct:+.1f}% over 36 months.",
        f"•  The July mailing drew {ms[0][2]:,} responders ({ms[0][5]:.1f}%); the September mailing of {m['mail_in_progress'][0][1]:,} is in progress.",
        f"•  NSF/OD items were up {m['nsf_yoy']}% on a year ago in July; August is left out as incomplete in this extract.",
    ], size=13, font=BODY, color=NAVY, spacing=1.15)
    x, w = span(6, 6)
    rect(s, x, y2, w, h2, fill=NAVY, radius=0.12)
    tb(s, x + 0.25, y2 + 0.2, w - 0.5, 0.3, "WHAT WE RECOMMEND", size=11, font=KICK, bold=True, color=ORANGE)
    tb(s, x + 0.25, y2 + 0.55, w - 0.5, h2 - 0.7, [
        "1.  Reg E coaching at Call Center and Digital: 13% and 17% opt-in against 29% program-wide, on 3,662 card holders.",
        "2.  Card issuance at account opening in the Call Center: 81% take rate against 91% elsewhere.",
        "3.  Keep the Non-User offer in every mailing: those responders went from $31 to $567 a month.",
    ], size=13, font=BODY, color=WHITE, spacing=1.15)
    footer(s, n_slide[0], "")
    notes(s, SRC_WB + " " + SRC_ODD + " " + SRC_VIP_ICS + " " + SRC_VIP_MRPC + " " + SRC_CP)

    # ================================================================ 3 ARS divider
    def divider(name, benefits, stats, current):
        s = new(dark=True)
        tb(s, MARGIN, 0.5, 8, 0.3, "SECTION", size=11, font=KICK, bold=True, color="#9DB8CC")
        tb(s, MARGIN, 1.15, 12.3, 1.0, name, size=52, font=HERO, color=WHITE, wrap=False)
        tb(s, MARGIN, 2.3, 12.3, 0.5, benefits, size=18, font=HEAD, color=ORANGE)
        for i, (v, lab) in enumerate(stats):
            x, w = span(i * 4, 4)
            tb(s, x, 3.7, w, 0.9, v, size=40, font=HERO, color=WHITE)
            tb(s, x, 4.6, w, 0.4, lab, size=14, font=BODY, color="#CFDBE8")
        progress_track(s, ["Account Revenue Solution", "Invitation Checking", "CashPlease", "MyRewards Premium Cards"], current)
        lockup(s, SW - MARGIN - 1.1, 0.42, 1.1, dark=True)
        return s
    s = divider("Account Revenue Solution®", "Mailings · Debit Card · Reg E",
                [(f"{ratio:.1f} : 1", "profitability, program to date"),
                 (f"${ltd_profit/1e6:.2f}M", "incremental profit, program to date"),
                 (f"{ms[0][5]:.1f}%", f"response to the {ms[0][0]} mailing")], "Account Revenue Solution")
    notes(s, SRC_WB)

    # ================================================================ 4 ARS result
    s = new()
    kicker_row(s, "ARS · Financial performance", "PTD · AUG 2026")
    headline(s, f"ARS has returned ${ltd_rev/1e6:.2f}M in revenue on ${ltd_cost/1e6:.2f}M of fees, {ratio:.1f} : 1, "
                f"${surplus/1e6:.2f}M above the 2 : 1 guaranteed minimum.")
    x, w = span(0, 4)
    hero_cell(s, x, Y_BAND, w, Y_BAND_END - Y_BAND, f"{ratio:.1f} : 1", "revenue to fees, program to date",
              sub=f"{b['months']} months · {b['mailings']} mailings · since 2018", vsize=64)
    x, w = span(4, 8)
    tb(s, x, Y_BAND, w, 0.3, "Program P&L", size=13, font=KICK, bold=True, color=TICK)
    rows = [["", "August 2026", "Program to date"],
            ["Incremental revenue", f"${cur_rev:,.0f}", f"${ltd_rev:,.0f}"],
            ["Respondent fees", "$0", f"−${lines.get('Respondent Fee', 0):,.0f}"],
            ["Incremental profit", f"${cur_profit:,.0f}", f"${ltd_profit:,.0f}"],
            ["Guaranteed minimum revenue, 2 × fees", "", f"${guaranteed_min:,.0f}"],
            ["Revenue above the guarantee", "", f"${surplus:,.0f}"]]
    flat_table(s, x, Y_BAND + 0.35, w, rows, [w * 0.46, w * 0.25, w * 0.29], highlight=5, size=14, row_h=0.42)
    tb(s, x, Y_BAND + 0.35 + 0.42 * 6 + 0.25, w, 0.9,
       "Fees are billed on mailing response, so months without a mailing carry no cost. "
       "The guarantee is that revenue reaches twice the fees over the life of the program.", size=13, font=BODY, color=TICK)
    footer(s, n_slide[0], "Selection: all ARS incremental revenue and fees, Aug 2018 – Aug 2026")
    notes(s, SRC_WB + " Fee lines summed from the Actuals MM tab; the guarantee surplus is profit less twice the fees.")

    # ================================================================ 5 the book
    s = new()
    kicker_row(s, "ARS · Product mix and eligibility", "AUG 2026 DATA")
    headline(s, "37,629 of 71,466 accounts are ARS-eligible; five savings and credit products hold 22,473 "
                "the program does not mail.")
    x, w = span(0, 4)
    hero_cell(s, x, Y_BAND, w, 2.9, "53%", "of accounts are ARS-eligible", navy=True, vsize=64,
              sub="4 of 9 products carry the program")
    x, w = span(0, 2); stat_cell(s, x, Y_BAND + 3.05, w, Y_BAND_END - Y_BAND - 3.05, "71,466", "accounts, excl. closed", vsize=24)
    x, w = span(2, 2); stat_cell(s, x, Y_BAND + 3.05, w, Y_BAND_END - Y_BAND - 3.05, "33,837", "outside ARS", vsize=24)
    x, w = span(4, 8)
    tb(s, x, Y_BAND, w, 0.3, "Products and eligibility", size=13, font=KICK, bold=True, color=TICK)
    rows = [["Product", "Accounts", "ARS-eligible"],
            ["Simply Free Checking", "43,339", "35,849"], ["Business Checking", "978", "771"],
            ["Gunny Checking", "768", "649"], ["Organization Checking", "466", "360"],
            ["Secondary Savings Share", "15,472", "—"], ["Gunny Savings", "5,516", "—"],
            ["Money Market", "4,173", "—"], ["Credit Builder, Lottery Checking", "754", "—"],
            ["Total", "71,466", "37,629"]]
    flat_table(s, x, Y_BAND + 0.35, w, rows, [w * 0.5, w * 0.25, w * 0.25], highlight=9, size=13, row_h=0.38)
    footer(s, n_slide[0], "Selection: deposit accounts on file excluding closed; eligibility is the program flag")
    notes(s, SRC_ODD + " Product Mix and Excluded Accounts figures as shipped in the 2026.09 deck.")

    # ================================================================ 6 response
    s = new()
    kicker_row(s, "ARS · Mailing response", "LAST 12 MAILINGS")
    lo, hi = min(resp_rates), max(resp_rates)
    headline(s, f"Response has held between {lo:.0f}% and {hi:.0f}% across the last twelve mailings; "
                f"{ms[0][0]} came in at {ms[0][5]:.1f}% with {ms[0][2]:,} responders.")
    x, w = span(0, 8)
    pic(s, cd / "resp.png", x, Y_BAND, w=w)
    tb(s, x, Y_BAND + bh + 0.05, w, 0.3, "Response rate by mailing, responders ÷ offers sent", size=11, font=BODY, color=TICK)
    x, w = span(8, 4)
    stat_cell(s, x, Y_BAND, w, 1.4, f"{ms[0][2]:,}", f"responders, {ms[0][0]} mailing")
    stat_cell(s, x, Y_BAND + 1.55, w, 1.4, f"{ms[0][4]:.1f}%", "response, Threshold offer (light users, 1-20 swipes)")
    stat_cell(s, x, Y_BAND + 3.1, w, 1.4, f"{m['mail_in_progress'][0][1]:,}", f"offers in the {m['mail_in_progress'][0][0]} mailing, in progress")
    footer(s, n_slide[0], "Selection: the 12 most recent of the program's 38 mailings")
    notes(s, SRC_ODD + " Mailing Response Summary rows; the full table is in the appendix.")

    # ================================================================ 7 before / after
    s = new()
    kicker_row(s, "ARS · Responder activity", "9 MAILINGS · DEC 2023 – NOV 2025")
    gain = (m["ba_spend_after"] / m["ba_spend_before"] - 1) * 100
    headline(s, f"Responders raised monthly debit spend from ${m['ba_spend_before']:,} to ${m['ba_spend_after']:,}, "
                f"up {gain:.0f}%, and held it for six months after each mailing.")
    x, w = span(0, 4)
    hero_cell(s, x, Y_BAND, w, 2.6, f"+{gain:.0f}%", "monthly debit spend per responder", navy=True, vsize=64,
              sub=f"3 months before vs 6 months after; mean, {m['ba_n_mailings']} mailings")
    stat_cell(s, x, Y_BAND + 2.75, w, 1.85, f"{m['ba_nsf_before']:.2f} → {m['ba_nsf_after']:.2f}",
              "NSF/OD items per responder per month, +28%", vsize=26)
    x, w = span(4, 8)
    pic(s, cd / "ba.png", x, Y_BAND, w=w)
    tb(s, x, Y_BAND + bh + 0.05, w, 0.3, "Mean monthly debit spend per responder, before and after each mailing; spend winsorized at 3 SD",
       size=11, font=BODY, color=TICK)
    footer(s, n_slide[0], "Selection: ARS mailing responders, 3-month baseline vs the 6 months after the mailing")
    notes(s, SRC_ODD + " before_after block of the data pack (build/ars_pipeline/before_after.py).")

    # ================================================================ 8 lift matrix
    s = new()
    kicker_row(s, "ARS · Revenue Lift Matrix", "AUG 2026 – JUL 2027 WINDOW")
    headline(s, "A 1-5 swipe account that reaches 11-15 adds $12.26 a month; the 26+ tier is 39% of card "
                "accounts and earns $28.66 each.")
    x, w = span(0, 7)
    tb(s, x, Y_BAND, w, 0.3, "Monthly revenue added per account, from starting tier to tier now", size=13, font=KICK, bold=True, color=TICK)
    pic(s, cd / "lift.png", x, Y_BAND + 0.35, w=w)
    x, w = span(7, 5)
    tb(s, x, Y_BAND, w, 0.3, "Monthly value per card account, by tier", size=13, font=KICK, bold=True, color=TICK)
    pic(s, cd / "segval.png", x, Y_BAND + 0.35, w=w)
    footer(s, n_slide[0], "Selection: card accounts by 3-month average swipes; workbook Lift Matrix MM")
    notes(s, SRC_WB + " Lift Matrix MM tab and Revenue Segmentation block.")

    # ================================================================ 9 swipes & spend
    s = new()
    kicker_row(s, "ARS · Debit card review", "SEP 2023 – AUG 2026")
    headline(s, f"Debit spend was ${spend_now:.1f}M in August, {spend_yoy:+.1f}% on a year ago, "
                f"on {cards_now:,} card-holding accounts.")
    x, w = span(0, 8)
    pic(s, cd / "spend.png", x, Y_BAND, w=w)
    tb(s, x, Y_BAND + bh + 0.05, w, 0.3, "Monthly debit spend, $M, all card-holding accounts; last complete month in orange", size=11, font=BODY, color=TICK)
    x, w = span(8, 4)
    stat_cell(s, x, Y_BAND, w, 1.4, f"${spend_now:.1f}M", "debit spend, August 2026", dpct=spend_yoy, dref="Aug'25")
    stat_cell(s, x, Y_BAND + 1.55, w, 1.4, f"{cards_now:,}", "accounts with a card", dpct=cards_36_pct, dref="Sep'23")
    stat_cell(s, x, Y_BAND + 3.1, w, 1.4, f"${spend_now*1e6/cards_now:,.0f}", "spend per card account, August")
    footer(s, n_slide[0], "Selection: all debit-card-holding accounts, program-wide, monthly totals")
    notes(s, SRC_WB + " Key Trends spend and card counts (swipespend_36).")

    # ================================================================ 10 NSF/OD
    s = new()
    kicker_row(s, "ARS · NSF/OD activity", "NOV 2023 – JUL 2026")
    headline(s, f"NSF/OD items rose {m['nsf_yoy']}% on a year ago, to {m['nsf_last_items']:,} in July. "
                f"August is left out: the extract was pulled on the 4th.")
    x, w = span(0, 8)
    pic(s, cd / "nsf.png", x, Y_BAND, w=w)
    tb(s, x, Y_BAND + bh + 0.05, w, 0.3, "NSF/OD items per month; the hatched August bar is the 390 items in the extract, not a month",
       size=11, font=BODY, color=TICK)
    x, w = span(8, 4)
    stat_cell(s, x, Y_BAND, w, 1.4, f"{m['nsf_last_items']:,}", "NSF/OD items, July 2026", dpct=m["nsf_yoy"], dref="Jul'25")
    stat_cell(s, x, Y_BAND + 1.55, w, 1.4, f"{m['nsf_last_accts']:,}", "accounts with an item, July")
    stat_cell(s, x, Y_BAND + 3.1, w, 1.4, f"{m['nsf_last_items']/m['nsf_last_accts']:.1f}", "items per account with activity")
    footer(s, n_slide[0], "Selection: all accounts, program-wide; complete months only")
    notes(s, SRC_ODD + " " + m["nsf_excluded_note"])

    # ================================================================ 11 take rate
    s = new()
    kicker_row(s, "ARS · Debit card take rate", "SEP 2025 – AUG 2026")
    headline(s, f"{m['take_new_pct']:.1f}% of eligible personal accounts opened this year took a card; "
                f"the Call Center, at 81%, is the one large branch under 90%.")
    x, w = span(0, 8)
    pic(s, cd / "take.png", x, Y_BAND, w=w)
    tb(s, x, Y_BAND + 4.35, w, 0.3, "Take rate by branch, 12 largest by accounts opened; the count is accounts opened", size=11, font=BODY, color=TICK)
    x, w = span(8, 4)
    hero_cell(s, x, Y_BAND, w, 2.4, f"{m['take_new_pct']:.1f}%", "take rate, new personal accounts", navy=True, vsize=56)
    stat_cell(s, x, Y_BAND + 2.55, w, 1.0, f"{m['take_new_nocard']:,}", f"of {m['take_new_total']:,} new accounts have no card", vsize=22)
    stat_cell(s, x, Y_BAND + 3.65, w, 0.95, f"{m['take_hist_pct']:.1f}%", "take rate, all eligible accounts", vsize=22)
    footer(s, n_slide[0], "Selection: ARS-eligible personal accounts opened Sep 2025 – Aug 2026")
    notes(s, SRC_ODD + " take_branch block.")

    # ================================================================ 12 Reg E
    s = new()
    kicker_row(s, "ARS · Reg E review", "AUG 2026 DATA")
    cc = next(r for r in rege if r[0] == "Call Center")
    headline(s, f"{m['rege_pct']:.1f}% of personal card holders are opted in; the Call Center's {cc[2]:,} "
                f"card holders sit at {cc[3]}%, the lowest of the large branches.")
    x, w = span(0, 8)
    pic(s, cd / "rege.png", x, Y_BAND, w=w)
    tb(s, x, Y_BAND + 4.35, w, 0.3, "Opt-in rate by branch, 12 largest by card holders; the count is card-holding personal accounts", size=11, font=BODY, color=TICK)
    x, w = span(8, 4)
    hero_cell(s, x, Y_BAND, w, 2.4, f"{m['rege_pct']:.1f}%", "opted in, all personal card holders", navy=True, vsize=56)
    stat_cell(s, x, Y_BAND + 2.55, w, 1.0, f"{m['rege_in']:,}", f"opted in of {m['rege_pool']:,} card holders", vsize=22)
    stat_cell(s, x, Y_BAND + 3.65, w, 0.95, f"{m['rege_new_pct']:.1f}%", "opt-in, accounts opened this year", vsize=22)
    footer(s, n_slide[0], "Selection: open personal accounts with a debit card; branches with 40+ eligible accounts")
    notes(s, SRC_ODD + " rege_branch block.")

    # ================================================================ 13 recommend (ARS)
    s = new(tile=True)
    kicker_row(s, "ARS · What we recommend", "SEP 2026")
    headline(s, "Three things the August data points at, each with the figure behind it.")
    cards = [
        ("Coach Reg E at the Call Center and Digital",
         "Both open accounts at volume and both sit far below the program opt-in. Scripting the election at card issuance is the one lever that reaches every new account.",
         "13% and 17% opt-in vs 29.3% program-wide · 3,662 card holders"),
        ("Issue the card at opening in the Call Center",
         "The Call Center opened 660 eligible accounts in the last year and 125 of them have no card. Every other large branch is at 90% or above.",
         "81% take rate vs 91.0% overall · 125 accounts without a card"),
        ("Keep the Non-User offer in every mailing",
         "Non-User responders are few but the change is large: $31 a month before the offer, $567 after. The Threshold offer moves $614 to $1,050.",
         "1,557 Non-User responder-observations · +$536 a month each"),
    ]
    for i, (t, bdy, fig) in enumerate(cards):
        x, w = span(i * 4, 4)
        action_card(s, x, Y_BAND, w, Y_BAND_END - Y_BAND, i + 1, t, bdy, fig)
    footer(s, n_slide[0], "")
    notes(s, SRC_ODD + " Figures from the Reg E, take-rate and before/after blocks on the preceding slides.")

    # ================================================================ 14 ICS divider
    s = divider("Invitation Checking® System", "Referrals · Account Performance · Revenue",
                [(f"{ref['program_to_date']:,}", "referrals, program to date"),
                 (f"{ics_total_ytd:,}", "referrals, 2026 year to date"),
                 (f"{ref['prev_month_vs_goal_pct']}%", "September against the monthly goal")], "Invitation Checking")
    notes(s, SRC_VIP_ICS)

    # ================================================================ 15 ICS referrals
    s = new()
    kicker_row(s, "ICS · Referrals", "PTD · OCT 1, 2026")
    headline(s, f"September brought {ref['previous_month']['value']} referrals, {ref['prev_month_vs_goal_pct']}% of the "
                f"{ref['monthly_goal']}-a-month goal; every month of 2026 has finished above it.")
    x, w = span(0, 8)
    pic(s, cd / "ics.png", x, Y_BAND, w=w)
    tb(s, x, Y_BAND + bh + 0.05, w, 0.3, "Checking referrals logged by branch staff, by month; October is the 1st of the month", size=11, font=BODY, color=TICK)
    x, w = span(8, 4)
    hero_cell(s, x, Y_BAND, w, 2.4, f"{ref['prev_month_vs_goal_pct']}%", "of goal in September", navy=True, vsize=56)
    stat_cell(s, x, Y_BAND + 2.55, w, 1.0, f"{ics_total_ytd:,}", "referrals year to date", vsize=22)
    stat_cell(s, x, Y_BAND + 3.65, w, 0.95, f"{max(tr['referrals']):,}", "program high, June 2026", vsize=22)
    footer(s, n_slide[0], "Selection: checking referrals logged by branch staff, Aug 2025 – Oct 2026")
    notes(s, SRC_VIP_ICS + " Workbook-driven ICS sections are omitted: the newest workbook (2026.08) is not for this period.")

    # ================================================================ 16 ICS branches
    s = new()
    kicker_row(s, "ICS · Results by branch", "YTD · OCT 1, 2026")
    headline(s, f"Fifteen of twenty branches logged a referral this year and the top five produced {top5_pct:.0f}% of them; "
                f"Corporate leads with {top5[0]['referrals']}.")
    x, w = span(0, 8)
    pic(s, cd / "icsbr.png", x, Y_BAND, w=w)
    tb(s, x, Y_BAND + 4.35, w, 0.3, "Referrals year to date as a share of each branch's goal to date; 12 largest by referrals", size=11, font=BODY, color=TICK)
    x, w = span(8, 4)
    hero_cell(s, x, Y_BAND, w, 2.4, "133%", "of goal, all branches, year to date", navy=True, vsize=56)
    stat_cell(s, x, Y_BAND + 2.55, w, 1.0, "15 of 20", "branches with a referral this year", vsize=22)
    stat_cell(s, x, Y_BAND + 3.65, w, 0.95, "5", "branches with none", vsize=22)
    footer(s, n_slide[0], "Selection: referrals by issuing branch, 2026 year to date, against pro-rated branch goals")
    notes(s, SRC_VIP_ICS + " Results by Branch, all-branch pace 133% (956 vs 720 pro-rated).")

    # ================================================================ 17 CP divider + overview
    s = divider("CashPlease®", "Loan Volume · Portfolio Status · Peer Comparison",
                [("6,831", "loans booked, program to date"), ("$2.8M", "principal advanced"),
                 ("39.6", "loans per 1,000 DDAs, last 12 months")], "CashPlease")
    notes(s, SRC_CP)
    s = new()
    kicker_row(s, "CashPlease · Peer comparison", "PTD · SEP 27, 2026")
    headline(s, "Marine FCU lends 39.6 loans per 1,000 DDAs against a client average of 17.0: "
                "smaller loans, more paid off, fewer charged off.")
    x, w = span(0, 7)
    pic(s, cd / "cp.png", x, Y_BAND + 0.2, w=w)
    tb(s, x, Y_BAND + 3.9, w, 0.3, "Marine FCU (large dot) against the all-clients cohort (small dot) on an index where the cohort is 100",
       size=11, font=BODY, color=TICK)
    x, w = span(7, 5)
    hero_cell(s, x, Y_BAND, w, 2.4, "39.6", "loans per 1,000 DDAs, last 12 months", navy=True, vsize=60,
              sub="1,556 loans against 39,289 DDA accounts")
    x, w = span(7, 2.5); stat_cell(s, x, Y_BAND + 2.55, w, 1.0, "$79K", "interest earned, PTD", vsize=22)
    x, w = span(9.5, 2.5); stat_cell(s, x, Y_BAND + 2.55, w, 1.0, "394", "loans funded today", vsize=22)
    x, w = span(7, 5); stat_cell(s, x, Y_BAND + 3.65, w, 0.95, "4.94%", "charge-off rate, 1.35 points under the cohort's 6.29%", vsize=22)
    footer(s, n_slide[0], "Cohort: the workbook's all-clients rollup; the DDA rate uses the 51 clients with a DDA count and a full 12 months")
    notes(s, SRC_CP)

    # ================================================================ 19 MRPC divider + enrollments
    s = divider("MyRewards Premium Cards®", "Enrollments · Retention · Revenue",
                [("7,942", "cardholders enrolled, program to date"),
                 (f"{en['last_complete']['gold'] + en['last_complete']['platinum']}", "enrollments in September"),
                 ("19.1%", "of open debit accounts enrolled")], "MyRewards Premium Cards")
    notes(s, SRC_VIP_MRPC)
    s = new()
    kicker_row(s, "MRPC · Enrollments", "AS OF OCT 1, 2026")
    lc = en["last_complete"]; tot = lc["gold"] + lc["platinum"]
    headline(s, f"{tot} enrollments in September, {lc['platinum']} Platinum and {lc['gold']} Gold; "
                f"{mr['key_metrics']['enrollments_trailing_12']:,} over the last twelve months.")
    x, w = span(0, 8)
    pic(s, cd / "mrpc.png", x, Y_BAND, w=w)
    tb(s, x, Y_BAND + bh + 0.05, w, 0.3, "Gold and Platinum enrollments by month; October is a partial month", size=11, font=BODY, color=TICK)
    x, w = span(8, 4)
    stat_cell(s, x, Y_BAND, w, 1.4, f"{lc['platinum']}", "Platinum, September")
    stat_cell(s, x, Y_BAND + 1.55, w, 1.4, f"{lc['gold']}", "Gold, September", orange=True)
    stat_cell(s, x, Y_BAND + 3.1, w, 1.4, f"{mr['key_metrics']['active_enrollments']:,}", "active enrollments")
    footer(s, n_slide[0], "Selection: personal Gold and Platinum enrollments, Aug 2025 – Oct 2026")
    notes(s, SRC_VIP_MRPC + " enrollments_by_month.")

    # ================================================================ 21 MRPC revenue
    s = new()
    kicker_row(s, "MRPC · Revenue to Marine FCU", "JUN 2025 – MAY 2026")
    avg = sum(rev["revenue"]) / len(rev["revenue"])
    headline(s, f"MRPC pays Marine FCU about ${avg/1e3:.1f}K a month, ${sum(rev['revenue'])/1e3:.1f}K over the "
                f"twelve months to May, ahead of 2025's ${mr['revenue']['year_2025']/1e3:.1f}K.")
    x, w = span(0, 8)
    pic(s, cd / "mrev.png", x, Y_BAND, w=w)
    tb(s, x, Y_BAND + bh + 0.05, w, 0.3, "Monthly revenue to the credit union; the VIP revenue dashboard ends at May 2026", size=11, font=BODY, color=TICK)
    x, w = span(8, 4)
    stat_cell(s, x, Y_BAND, w, 1.4, f"${avg:,.0f}", "average monthly revenue, 12 months")
    stat_cell(s, x, Y_BAND + 1.55, w, 1.4, f"${mr['revenue']['year_2025']:,.0f}", "2025 revenue")
    stat_cell(s, x, Y_BAND + 3.1, w, 1.4, f"${mr['revenue']['life_of_program']:,.0f}", "life of program")
    footer(s, n_slide[0], "Selection: revenue to the FI by month, Jun 2025 – May 2026 (the dashboard's latest month)")
    notes(s, SRC_VIP_MRPC + " revenue.by_month; not refreshed past May 2026 at the VIP source.")

    # ================================================================ 22 closing
    s = new(dark=True)
    tb(s, MARGIN, 1.4, 12.3, 1.2, "Questions & Discussion", size=60, font=HERO, color=WHITE)
    tb(s, MARGIN, 2.65, 12.3, 0.5, "Marine FCU  ·  September 2026", size=18, font=HEAD, color=ORANGE)
    x, w = span(7, 5)
    rect(s, x, 4.0, w, 2.2, fill=WHITE, radius=0.12)
    tb(s, x + 0.35, 4.3, w - 0.7, 0.5, "Aaron Burgard", size=24, font=HEAD, color=NAVY)
    tb(s, x + 0.35, 4.8, w - 0.7, 0.35, "Client Service Manager", size=14, font=BODY, color=ORANGE, bold=True)
    tb(s, x + 0.35, 5.3, w - 0.7, 0.35, "910-617-1984", size=14, font=BODY, color=NAVY)
    tb(s, x + 0.35, 5.65, w - 0.7, 0.35, "aaron.burgard@csiweb.com", size=14, font=BODY, color=NAVY)
    lockup(s, MARGIN, 5.6, 1.6, dark=True)
    notes(s, "Contact card from CSM Contacts.csv in production (rpe_env.csm_contact).")

    # ================================================================ 23 appendix
    s = divider("Appendix", "Mailing detail · Responder profiles · ICS resources", [], "")
    s = new()
    kicker_row(s, "Appendix · Mailing response summary", "LAST 12 MAILINGS")
    headline(s, f"Twelve mailings, {m['mail_summary_total'][0]:,} offers, {m['mail_summary_total'][1]:,} responders: "
                f"{trailing_resp:.1f}% response overall, {m['mail_summary_total'][3]:.1f}% to the Threshold offer.")
    rows = [["Mailing", "Offers sent", "Responders", "Non-User offer", "Threshold offer", "All offers"]]
    rows.append([f"{m['mail_in_progress'][0][0]} (in progress)", f"{m['mail_in_progress'][0][1]:,}", "pending", "pending", "pending", "pending"])
    for r in ms:
        rows.append([r[0], f"{r[1]:,}", f"{r[2]:,}", f"{r[3]:.1f}%", f"{r[4]:.1f}%", f"{r[5]:.1f}%"])
    t = m["mail_summary_total"]
    rows.append(["Trailing 12 mailings", f"{t[0]:,}", f"{t[1]:,}", f"{t[2]:.1f}%", f"{t[3]:.1f}%", f"{t[4]:.1f}%"])
    x, w = span(0, 12)
    flat_table(s, x, Y_BAND - 0.1, w, rows, [w * 0.3] + [w * 0.14] * 5, highlight=len(rows) - 1, size=12, row_h=0.3)
    footer(s, n_slide[0], "Selection: the 12 most recent of the program's 38 mailings")
    notes(s, SRC_ODD + " Mailing Response Summary. Response rates by offer cohort: Non-User (NU 5+) and Threshold, the light users averaging 1-20 swipes a month who qualify for usage campaigns.")

    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    print(f"wrote {out} ({n_slide[0]} slides)")


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]))
