# Ported from ARS v5 02-Scripts/ars/deck/charts.py at a491b5c (James Gilmore); logic unchanged; the palette
# and chart face are RPE's (brand.py, rpe_env.use_font).
"""Chart renderers for the ODD-only deck.

Charts are PNGs, not native pptx charts, so a slide never carries chart
XML that PowerPoint restyles on open; the picture is the contract.

Palette and typography follow the CSI brand -- navy and orange, with
Montserrat for chart labels. Nothing
here reads a metric by name; each function takes plain values so a chart can
be tested without running the pipeline.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.ticker as mticker
import numpy as np

import brand
import periods as _rpe_periods
import rpe_env

# a calendar month drawn on an axis outside MMM'YY fails the render, as in every RPE chart module
_rpe_periods.install_month_axis_guard()


def _axis_labels(labels) -> list:
    """Category labels for an axis, every calendar month in the house MMM'YY form.

    v5's packs label months as the ODD does ("Jan24"); the guard above refuses those, and the
    chart was declined and silently left off the slide (five blank charts on 1798, Sheila's slide
    review, 2026-10-30). A label that is not a month passes through unchanged."""
    return _rpe_periods.axis_months(["" if l is None else str(l) for l in labels])

# CSI Velocity brand. These are the canonical values, matching
# RPE-Workflow's ars_engine/core/brand.py -- the module that declares itself the
# single source of truth for colour. Five of these had drifted: GREY was one hex
# digit off, GRID was a near-miss, RED was a brick (#C0392B) rather than CSI
# Red. Charts built from a drifted palette look almost right, which is why it
# went unnoticed through every deck that shipped --
# test_palette_matches_csi_brand pins them now.
NAVY = brand.NAVY
ORANGE = brand.ORANGE
# CSI brand tokens the chart layer was missing. GOLD is the measured
# quantity -- the filled portion of a thing -- and LINE is the empty part of
# a track. Their absence is why these charts read thinner than the brand
# sketches: every bar sat on bare white with orange as the only accent, so
# "one accent per chart" had to mean "one colour per chart".
GOLD = brand.GOLD
LINE = brand.GRID
NEUTRAL = brand.MUTED
# Steel deepened 7B9BB8 -> 5E84A6 and a TINT added for light data fills
# (dataviz review, 2026-08-22): the old light tint sat at 1.37:1 against
# the surface -- near-invisible as a wedge or segment. LIGHT remains for
# non-data uses (icon strokes); TINT carries data. Palette validated:
# CVD dE >= 15.7 on every adjacent pair, steel now clears 3:1. The brand
# module's own steel (#7BA0C4) does not clear 3:1 on white, so the
# validated value stands and is the one deliberate departure from brand.py.
#
# ICON_STROKE was LIGHT until 2026-08-25 (#73). At 1.40:1 against the white
# slide the structural stroke was invisible: only the orange accent survived,
# so the mailing envelope read as an empty box outline and members as a lone
# dot. Steel carries the structure at 3.94:1; orange stays the accent.
STEEL = brand.SLATE       # brand.STEEL fails 3:1 on white (see above); SLATE clears it
LIGHT = brand.LABEL
TINT = brand.STEEL_SOFT
GREY = brand.TICK
GRID = brand.GRID
RED = "#EB2A2E"       # no brand token: the RAG red (v5 value)
GREEN = "#2A9D8F"     # no brand equivalent: the RAG green and positive deltas

ICON_STROKE = STEEL   # see the palette note above (#73)

DPI = 150   # 200 was ~2x slower for no visible gain at slide size

# Author each figure at the width of the slot it lands in, so type on the
# slide is the size it was authored at (DESIGN/ spec). Rail slot ~9.28in
# (chart left of the callout rail); full slot ~12in.
FIG_W_RAIL = 8.8
FIG_W_FULL = 11.5
# ...and at the HEIGHT of that slot too. A form that authors a 3.4in canvas
# for a 4.90in band lands an inch and a half short and leaves the spare in
# one lump at the bottom of the slide -- which is what "too much white
# space" was. These are the two content bands of ars/deck/build's grid,
# expressed as the canvas that fills them:
#
#     rail   8.69 x 4.90in   (RAIL_LEFT - RAIL_GUTTER - MARGIN_L, band)
#     full  11.53 x 4.90in   (CONTENT_W, band)
#
# build.py imports this module, so these cannot be imported from the grid
# without a cycle. test_ils_kickoff_deck asserts they still match it.
_BAND_H = 4.90
FIG_H_RAIL = round(FIG_W_RAIL * (_BAND_H / 8.69), 2)     # 4.96
FIG_H_FULL = round(FIG_W_FULL * (_BAND_H / 11.53), 2)    # 4.89

# Type floor (Sheila's 1798 slide review, 2026-10-30: chart labels read at 9-10pt). A figure is drawn
# at FIG_W_* and placed by the slide helpers a little narrower than it was authored: on 1798's deck
# the median chart landed at 0.94x and most between 0.81x and 1.05x. So every piece of chart text is
# authored at CHART_MIN_PT or more, which lands at about 12pt on the slide at the typical scale
# (12 / PLACED_SCALE). _save applies it to every text on the figure, ticks, legends and captions
# included, except a label fit_text sized to the block that holds it.
PLACED_SCALE = 0.92
CHART_MIN_PT = round(12 / PLACED_SCALE, 1)               # 13.0


# RPE: the chart face is brand.CHART_FONT through rpe_env.use_font, which raises rather
# than substitute; DejaVu Sans stays as the per-glyph fallback v5 relied on for the arrows.
BRAND_FONT = brand.CHART_FONT
rpe_env.use_font(BRAND_FONT)
plt.rcParams.update({"font.family": [BRAND_FONT, "DejaVu Sans"], "font.size": CHART_MIN_PT})


def _track(ax, xs, height, width=0.86, horizontal=False):
    """The empty part of the bar, drawn behind it.

    Every bar in the brand sketches sits in a light track: the eye reads the
    proportion without hunting for an axis, and the chart has a floor instead
    of floating on white. Drawn under everything (zorder 0) so nothing else
    has to know about it.
    """
    if horizontal:
        ax.barh(xs, [height] * len(xs), height=width, color=LINE, zorder=0)
    else:
        ax.bar(xs, [height] * len(xs), width=width, color=LINE, zorder=0)


_PENDING_CAPTION = None


def set_caption(text: str | None) -> None:
    """Caption the NEXT chart saved, then forget it.

    Every form calls _save() and none of them knows about captions, so the
    caption is applied there -- the same lever _declutter already uses to
    reach all eighty-odd forms without editing any of them. Cleared on save
    so it can never leak onto the following chart.
    """
    global _PENDING_CAPTION
    _PENDING_CAPTION = text


def caption(ax, text: str) -> None:
    """The slate line under a chart: "biweekly, fourteen months".

    Every sketch in the brand set carries one. It says what the reader is
    looking at in the concrete -- the unit, the window, the population --
    which the headline above states as a finding and the axis cannot say at
    all. Without it a chart is a shape with numbers on it.
    """
    ax.figure.text(0.012, 0.015, text, fontsize=CHART_MIN_PT, color=GREY,
                   fontweight="bold", ha="left", va="bottom")


def callout(ax, x, text: str, color=ORANGE) -> None:
    """A labelled vertical rule ON the chart: STOPPED, CD OFFER FIRES.

    The moment the chart is about, named where it happens. A reader should
    not have to infer which bar is the point from a headline six inches
    away.
    """
    ax.axvline(x, color=color, lw=2.2, zorder=3)
    top = ax.get_ylim()[1]
    ax.text(x, top * 0.98, f" {text.upper()}", color=color, fontsize=8.5,
            fontweight="800", ha="left", va="top", zorder=4)


def _clean(ax, left=False, bottom=True):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_visible(left)
    ax.spines["bottom"].set_visible(bottom)
    ax.spines["bottom"].set_color("#B8C0CA")
    ax.tick_params(colors=GREY, length=0)
    ax.set_axisbelow(True)


def fit_text(ax, x, y, width, text, fontsize, floor=7.5, max_lines=1, **kw):
    """ax.text() that stays inside `width` (data units): the label a block holds must not run over the
    block beside it (slides 8 and 63, 2026-10-27). One line steps the size down to `floor`; with
    max_lines > 1 the words wrap at the size given first, then it steps down. What still does not fit
    at the floor is cut with an ellipsis, so a label is never clipped by the neighbour drawn after it.

    Measured on the figure as it stands; tight_layout runs later and can move the axes a few percent,
    so the width is held to 94% of what the caller offers."""
    fig = ax.figure
    renderer = fig.canvas.get_renderer()
    inv = ax.transData.inverted()
    limit = width * 0.94

    def extent(artist):
        bb = artist.get_window_extent(renderer)
        (x0, _), (x1, _) = inv.transform([(bb.x0, bb.y0), (bb.x1, bb.y1)])
        return abs(x1 - x0)

    def wrapped(size, n):
        probe = ax.text(x, y, "", fontsize=size, **kw)
        lines, cur = [], ""
        for word in str(text).split():
            trial = f"{cur} {word}".strip()
            probe.set_text(trial)
            if cur and extent(probe) > limit:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        lines.append(cur)
        ok = len(lines) <= n
        for ln in lines:
            probe.set_text(ln)
            ok = ok and extent(probe) <= limit
        probe.remove()
        return "\n".join(lines), ok

    size = fontsize
    while True:
        body, ok = wrapped(size, max_lines)
        if ok or size <= floor:
            break
        size = max(floor, size - 0.5)
    if not ok:                       # at the floor and still wide: cut the last line, never overrun
        lines = body.split("\n")[:max_lines]
        probe = ax.text(x, y, lines[-1], fontsize=size, **kw)
        while len(lines[-1]) > 4 and extent(probe) > limit:
            lines[-1] = lines[-1][:-1].rstrip()
            probe.set_text(lines[-1] + "\u2026")
        probe.remove()
        lines[-1] += "\u2026"
        body = "\n".join(lines)
    artist = ax.text(x, y, body, fontsize=size, **kw)
    artist._ars_fitted = True        # sized to its block: the type floor leaves it alone
    return artist


def place_point_labels(ax, pts, areas_pt2, names, fontsize=11, color=None):
    """Name each bubble of a scatter beside it, never on another bubble or another name.

    Every label used to sit a fixed 14 points above its bubble's centre: inside a large bubble, on top
    of its neighbour's, over the next label (slides 17, 46, 49, 50 and 61, 2026-10-27). Here each
    point, largest bubble first, tries eight places around its own bubble (above, below, right, left,
    then the four corners) and keeps the one that overlaps least with the labels already placed, the
    other bubbles and the edge of the plot; the first of equals wins, so a clear chart reads as it did.
    `pts` are data coordinates, `areas_pt2` the scatter's `s` for each point."""
    from matplotlib.transforms import Bbox
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    k = fig.dpi / 72.0
    disp = ax.transData.transform(pts)
    radii = [(a ** 0.5) / 2.0 * k for a in areas_pt2]
    axbb = ax.get_window_extent(renderer)
    discs = [Bbox([[x - r, y - r], [x + r, y + r]]) for (x, y), r in zip(disp, radii)]
    placed = []
    probe = ax.text(0, 0, "", fontsize=fontsize, fontweight="bold")

    def overlap(a, b):
        w = min(a.x1, b.x1) - max(a.x0, b.x0)
        h = min(a.y1, b.y1) - max(a.y0, b.y0)
        return w * h if w > 0 and h > 0 else 0.0

    for i in sorted(range(len(pts)), key=lambda j: -radii[j]):
        probe.set_text(str(names[i]))
        tb = probe.get_window_extent(renderer)
        w, h = tb.width, tb.height
        x, y = disp[i]
        around = []                                      # (anchor x, anchor y, ha, va) of the text
        # Beside the bubble first, then one and two labels further out: a cluster of seven
        # overlapping branches (the branch quadrants, 2026-10-28) needs the far ring, and a name
        # that had to move out gets a leader line back to its bubble.
        for ring in (1.0, 1.9, 2.9):
            gap = (radii[i] + 4 * k) * ring
            around += [
                (x, y + gap, "center", "bottom", ring), (x, y - gap, "center", "top", ring),
                (x + gap, y, "left", "center", ring), (x - gap, y, "right", "center", ring),
                (x + gap * 0.75, y + gap * 0.75, "left", "bottom", ring),
                (x - gap * 0.75, y + gap * 0.75, "right", "bottom", ring),
                (x + gap * 0.75, y - gap * 0.75, "left", "top", ring),
                (x - gap * 0.75, y - gap * 0.75, "right", "top", ring)]
        best = None
        for n, (ax_, ay_, ha, va, ring) in enumerate(around):
            x0 = ax_ - (w / 2 if ha == "center" else 0 if ha == "left" else w)
            y0 = ay_ - (h / 2 if va == "center" else 0 if va == "bottom" else h)
            box = Bbox([[x0, y0], [x0 + w, y0 + h]])
            score = sum(overlap(box, o) for o in placed)
            score += sum(overlap(box, d) for j, d in enumerate(discs) if j != i)
            score += (box.width * box.height - overlap(box, axbb)) * 4      # the part outside the plot
            if best is None or score < best[0] - 1e-9:
                best = (score, ax_, ay_, ha, va, box, ring)
            if score == 0:
                break
        _, ax_, ay_, ha, va, box, ring = best
        placed.append(box)
        inv = ax.transData.inverted().transform((ax_, ay_))
        t = ax.text(inv[0], inv[1], str(names[i]), ha=ha, va=va, fontsize=fontsize,
                    fontweight="bold", color=color or NAVY, zorder=4)
        t._ars_keep = True            # placed on the real picture: the declutter pass leaves it
        if ring > 1.0:
            # from the bubble's edge towards the name, under the bubble so it never crosses it
            dx, dy = ax_ - x, ay_ - y
            d = (dx * dx + dy * dy) ** 0.5 or 1.0
            ex, ey = x + dx / d * radii[i], y + dy / d * radii[i]
            p0 = ax.transData.inverted().transform((ex, ey))
            ax.plot([p0[0], inv[0]], [p0[1], inv[1]], color=GREY, lw=0.8, zorder=2,
                    solid_capstyle="round")
    probe.remove()


def _declutter(fig) -> int:
    """Drop data labels that would print on top of another label.

    168 label-placement sites exist across the chart layer and exactly one
    of them measures whether the label fits (_label_if_it_fits); five more
    re-implement the idea against fixed thresholds that hold only at the
    figure size they were written for. Rather than repair 168 call sites,
    the check runs once here, on the laid-out figure, where the true pixel
    extents are finally known and where every chart already passes through.

    Only artists added with ax.text() are considered. Tick labels, titles
    and legends are laid out by matplotlib and are not ours to remove.

    A bigger label wins its space first, then earlier draw order: a callout
    outranks a value label, and among equals the first one placed keeps its
    position. Dropping rather than nudging is deliberate and matches the
    rule _label_if_it_fits already applies to a segment too narrow to hold
    its text -- a moved label points at the wrong mark, which is a worse
    failure than an absent one.

    Returns the number of labels removed. A figure that lays out its own
    labels can opt out with fig._ars_no_declutter = True.
    """
    if getattr(fig, "_ars_no_declutter", False):
        return 0
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    # A legend is laid out by matplotlib and is never ours to remove, but it
    # occupies space a value label must not print into (#82, slide 46: a bar
    # label crowding the legend swatch). Seeding the kept list with it makes
    # the legend win by construction.
    kept_fixed = []
    for ax in fig.axes:
        legend = ax.get_legend()
        if legend is not None and legend.get_visible():
            try:
                kept_fixed.append(legend.get_window_extent(renderer))
            except (AttributeError, RuntimeError):
                pass

    candidates = []
    for ax in fig.axes:
        for order, artist in enumerate(ax.texts):
            if not artist.get_visible() or not artist.get_text().strip():
                continue
            if getattr(artist, "_ars_keep", False):
                continue
            candidates.append((-artist.get_fontsize(), order, artist))
    candidates.sort(key=lambda c: (c[0], c[1]))

    kept, removed = list(kept_fixed), 0
    for _size, _order, artist in candidates:
        box = artist.get_window_extent(renderer).expanded(1.0, 1.0)
        if any(box.overlaps(other) for other in kept):
            artist.remove()
            removed += 1
        else:
            kept.append(box)
    return removed


_CAPTION_PT = CHART_MIN_PT     # was 9 (Sheila's 1798 review, 2026-10-30)
_CAPTION_PAD_IN = 0.10          # clear air between tick labels and the slate


def _caption_band(fig, text: str, laid_out: bool) -> None:
    """Carve a strip off the bottom of the figure and write the caption in it.

    Measured, not guessed: the strip is the caption's own type height plus a
    fixed pad, expressed as a fraction of THIS figure -- so it holds at any
    canvas size rather than at the one it was written for.
    """
    band_in = _CAPTION_PT / 72.0 + _CAPTION_PAD_IN
    band = band_in / fig.get_figheight()
    if laid_out:
        fig.subplots_adjust(bottom=fig.subplotpars.bottom + band)
    fig.text(0.012, band * 0.28, text, fontsize=_CAPTION_PT, color=GREY,
             fontweight="bold", ha="left", va="bottom")


def _literal_dollars(fig) -> None:
    """Every `$` on a figure prints as a `$`. Two dollar signs in one string put matplotlib into
    mathtext, which set "$2,984 vs $6,044" in italics with its spaces gone (slide 15, 2026-10-27). A
    chart that escaped them by hand keeps working: the backslash is taken out as math parsing is
    turned off."""
    from matplotlib.text import Text
    for t in fig.findobj(Text):
        s = t.get_text()
        if "$" in s:
            t.set_parse_math(False)
            t.set_text(s.replace("\\$", "$"))


def _type_floor(fig) -> int:
    """Raise every text on the figure below CHART_MIN_PT to it; returns how many it raised.

    One lever for every form, as _declutter is: some 170 sites set a fontsize between 6.8 and 12,
    written for figures placed at full size, and the slide places them smaller. A label fit_text
    sized to its block (`_ars_fitted`) keeps its size: it is already the largest that fits there."""
    from matplotlib.text import Text
    raised = 0
    for t in fig.findobj(Text):
        if getattr(t, "_ars_fitted", False) or not t.get_text().strip():
            continue
        if t.get_fontsize() < CHART_MIN_PT:
            t.set_fontsize(CHART_MIN_PT)
            raised += 1
    # ticks matplotlib makes later (a numeric axis) take rcParams' font.size, which is CHART_MIN_PT
    return raised


def _untangle_ticks(fig) -> bool:
    """Horizontal x tick labels that now run into each other are angled (the house AXIS_ROTATION),
    never shrunk back under the floor. Returns True when any axis was changed."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    changed = False
    for ax in fig.axes:
        labels = [t for t in ax.get_xticklabels() if t.get_visible() and t.get_text().strip()]
        if len(labels) < 2 or any(t.get_rotation() for t in labels):
            continue
        boxes = sorted((t.get_window_extent(renderer) for t in labels), key=lambda b: b.x0)
        if any(a.x1 + 2 > b.x0 for a, b in zip(boxes, boxes[1:])):
            for t in labels:
                t.set_rotation(_rpe_periods.AXIS_ROTATION)
                t.set_ha(_rpe_periods.AXIS_HA)
                t.set_rotation_mode("anchor")
            changed = True
    return changed


def _save(fig, path: Path) -> Path:
    """Layout is tightened INSIDE the authored canvas -- never cropped to
    content (bbox_inches='tight' shrank figures unpredictably, so the same
    renderer landed at different on-slide type sizes).

    Also the one place a caption can be applied to every form: see
    set_caption().
    """
    global _PENDING_CAPTION
    caption_text, _PENDING_CAPTION = _PENDING_CAPTION, None
    path.parent.mkdir(parents=True, exist_ok=True)
    laid_out = False
    _type_floor(fig)
    try:
        # figures with manually placed axes (add_axes) author their own
        # layout; tight_layout would warn and shift them. So do figures that
        # reserved a margin for figure-level text -- tight_layout does not
        # see fig.text and would lay the panels straight over it.
        if getattr(fig, "_ars_layout_authored", False):
            pass
        elif all(ax.get_subplotspec() is not None for ax in fig.axes):
            fig.tight_layout(pad=0.5)
            laid_out = True
            if _untangle_ticks(fig):
                fig.tight_layout(pad=0.5)
    except Exception:
        pass

    # The caption goes on AFTER the layout, never before. It used to be
    # written first and the margin reserved with subplots_adjust -- and then
    # tight_layout ran, recomputed that same margin from the tick labels
    # alone, and discarded the reservation. The caption landed on top of the
    # band names on ten slides of the kickoff deck.
    #
    # tight_layout leaves the axes' bottom exactly where the tick labels
    # need it, so the band the caption needs is carved out BELOW that, by
    # pushing the axes up by the caption's own height.
    if caption_text:
        _caption_band(fig, caption_text, laid_out)
    # After layout, before the render: extents are only true once the axes
    # have their final size.
    _literal_dollars(fig)
    _declutter(fig)
    _report_overlaps(fig, path)
    fig.savefig(path, dpi=DPI, facecolor="white")
    plt.close(fig)
    return path


# The gate reads a deck through python-pptx and cannot see inside a chart image, which is how
# branch numbers on top of bubbles and names off the edge of the canvas shipped (Aaron,
# 2026-10-28). So the check runs here, on the laid-out figure: every label is measured against
# the bubbles it does not belong to and against the canvas. A chart with a few is reported
# (RENDER_WARNINGS, drained into the build's warnings); one past UNREADABLE_LABELS is refused,
# so the slide states the chart could not be drawn rather than carrying it.
RENDER_WARNINGS: list = []
UNREADABLE_LABELS = 6


class ChartUnreadable(Exception):
    pass


def _report_overlaps(fig, path) -> list:
    from matplotlib.collections import PathCollection
    renderer = fig.canvas.get_renderer()
    fw, fh = fig.bbox.width, fig.bbox.height
    k = fig.dpi / 72.0
    found = []
    for ax in fig.axes:
        discs = []
        for coll in ax.collections:
            if not isinstance(coll, PathCollection):
                continue
            offsets = ax.transData.transform(coll.get_offsets())
            sizes = coll.get_sizes()
            for j, (cx, cy) in enumerate(offsets):
                r = (float(sizes[j % len(sizes)]) ** 0.5) / 2.0 * k if len(sizes) else 0.0
                discs.append((cx, cy, r))
        for t in ax.texts:
            s = t.get_text().strip()
            if not s or not t.get_visible():
                continue
            bb = t.get_window_extent(renderer)
            if bb.width <= 0 or bb.height <= 0:
                continue
            if bb.x0 < -1 or bb.y0 < -1 or bb.x1 > fw + 1 or bb.y1 > fh + 1:
                found.append(f"label '{s}' runs off the canvas")
                continue
            own = getattr(t, "_ars_bubble", None)
            for j, (cx, cy, r) in enumerate(discs):
                if j == own or r <= 0:
                    continue
                # the part of the label inside the bubble's square, against the label's area
                w = min(bb.x1, cx + r) - max(bb.x0, cx - r)
                h = min(bb.y1, cy + r) - max(bb.y0, cy - r)
                if w > 0 and h > 0 and (w * h) / (bb.width * bb.height) > 0.3:
                    found.append(f"label '{s}' sits on a bubble")
                    break
    if found:
        name = Path(path).name
        RENDER_WARNINGS.extend(f"{name}: {m}" for m in found)
        if len(found) > UNREADABLE_LABELS:
            plt.close(fig)
            raise ChartUnreadable(f"{len(found)} labels overlap or run off the chart; "
                                  f"first: {found[0]}")
    return found


def funnel(stages: list, out: Path, drop_fmt: str = "-{:.1f}%") -> Path:
    """Eligibility funnel: horizontal bars with drop-off called out.

    The fourth element of a stage is the drop. It printed as "-{n:.1f}%"
    whatever it held, so a caller passing a COUNT got "-2276.0%", and a
    stage that grew rather than shrank got a double minus. A drop is only
    a drop when it is positive; anything else is not called out at all."""
    labels = [s[0] for s in stages]
    counts = [s[1] for s in stages]
    drops = [s[3] for s in stages]

    fig, ax = plt.subplots(figsize=(FIG_W_RAIL, FIG_H_RAIL))
    y = np.arange(len(labels))[::-1]
    colors = [NAVY] + [STEEL] * (len(labels) - 1)
    ax.barh(y, counts, color=colors, height=0.62, edgecolor="white", linewidth=1.4)

    span = max(counts) if counts else 1
    for i, (count, drop) in enumerate(zip(counts, drops)):
        text = f"{count:,.0f}"
        if drop and drop > 0:
            text += "    " + drop_fmt.format(drop)
        ax.text(count + span * 0.015, y[i], text, va="center", fontsize=13,
                fontweight="bold", color=NAVY)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=13, color=NAVY)
    ax.set_xlim(0, span * 1.22)
    ax.get_xaxis().set_visible(False)
    _clean(ax, bottom=False)
    return _save(fig, out)


def _label_if_it_fits(ax, x, y, text, share, color, fontsize=12):
    """Draw a segment label only when the segment is wide enough for it.

    The old rule -- print whenever the share cleared 5% -- put a five-
    character label into a segment narrower than the text, so adjacent
    labels overprinted each other (#72). The width is MEASURED, not
    estimated, so it holds at any figure size. The shares always sum to
    100, so a dropped label stays derivable from the ones that render.
    """
    artist = ax.text(x, y, text, ha="center", va="center", fontsize=fontsize,
                     fontweight="bold", color=color)
    ax.figure.canvas.draw()
    renderer = ax.figure.canvas.get_renderer()
    needed = artist.get_window_extent(renderer).width
    axis_px = ax.get_window_extent().width
    if needed + 6 > share * axis_px:
        artist.remove()
        return False
    return True


def stacked_movement(rows: list, out: Path) -> Path:
    """Tier movement by response status (James, issue #41, image spec):
    one 100% bar per group -- moved up (green), same tier (light), moved
    down (red) -- with the share printed inside each segment."""
    rows = [r for r in rows if r[1]]
    fig, ax = plt.subplots(figsize=(FIG_W_RAIL, 3.9))
    y = list(range(len(rows)))[::-1]
    parts = [(2, GREEN, "Moved up"), (3, TINT, "Same tier"),
             (4, RED, "Moved down")]
    for yi, r in zip(y, rows):
        left = 0.0
        for idx, color, _lab in parts:
            share = (r[idx] or 0) / 100.0
            ax.barh([yi], [share], left=left, color=color, height=0.55,
                    edgecolor="white", linewidth=1.5)
            if share > 0:
                _label_if_it_fits(
                    ax, left + share / 2, yi, f"{r[idx]:.1f}%", share,
                    color="white" if color != TINT else NAVY)
            left += share
    ax.set_yticks(y)
    ax.set_yticklabels([f"{r[0]}\n{r[1]:,} account" + ("" if r[1] == 1 else "s") for r in rows],
                       fontsize=12, color=NAVY)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for _, c, _l in parts]
    ax.legend(handles, [l for _, _c, l in parts], ncol=3, frameon=False,
              loc="upper center", bbox_to_anchor=(0.5, 1.14), fontsize=11)
    ax.set_xlim(0, 1)
    ax.get_xaxis().set_visible(False)
    _clean(ax, bottom=False)
    return _save(fig, out)


def rate_bars(rows: list, out: Path, mark_weakest: bool = True,
              show_n: bool = True) -> Path:
    """A rate by band: [[label, n, _, rate], ...]. The weakest band is
    the finding, so it carries the red; counts sit under the labels
    (James, issue #41: 'number of accounts at the base of each column')."""
    rows = [r for r in rows if r[1]]
    labels = [str(r[0]) for r in rows]
    ns = [r[1] for r in rows]
    rates = [r[3] for r in rows]
    weakest = rates.index(min(rates)) if (rows and mark_weakest) else -1
    fig, ax = plt.subplots(figsize=(FIG_W_RAIL, FIG_H_RAIL))
    colors = [RED if i == weakest else GOLD for i in range(len(rows))]
    _track(ax, range(len(rows)), max(rates) if rates else 0, width=0.6)
    bars = ax.bar(range(len(rows)), rates, color=colors, width=0.6, zorder=2)
    scale = max(rates) or 1
    for bar, r in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2, r + scale * 0.03,
                f"{r:.1f}%", ha="center", fontsize=12, fontweight="bold",
                color=NAVY)
    ax.set_xticks(range(len(rows)))
    ticks = [f"{l}\n{n_:,}" if show_n else l for l, n_ in zip(labels, ns)]
    ax.set_xticklabels(_axis_labels(ticks), fontsize=11, color=NAVY)
    ax.set_ylim(0, scale * 1.18)
    ax.get_yaxis().set_visible(False)
    _clean(ax)
    return _save(fig, out)


def _branch_fig(rows: list, portfolio: float, top: int = 12,
                fmt: str | None = None, show_n: bool = False):
    """Totals INSIDE the columns (white); best bar carries the orange
    accent; below-portfolio bars in steel; the portfolio is a band, not a
    whisper. Past 12 branches the chart flips HORIZONTAL (James, issue
    #43): names stay readable on the y-axis and every bar is wide."""
    rows = sorted(rows, key=lambda r: -r[3])[:top]
    if len(rows) > 12:
        return _branch_fig_h(rows, portfolio, fmt, show_n)
    from .labels import clip as _clip
    labels = [_clip(r[0], 18) for r in rows]
    if show_n:
        labels = [f"{l}\n{(r[2] or 0):,}" for l, r in zip(labels, rows)]
    rates = [r[3] for r in rows]
    val = (fmt.format if fmt else "{:.1f}%".format)
    scale = max(rates + [portfolio]) or 1

    fig, ax = plt.subplots(figsize=(FIG_W_FULL, 4.9))
    band_h = scale * 0.045
    ax.axhspan(portfolio - band_h, portfolio + band_h, color="#F2F5F8",
               zorder=0)
    # Bars run high to low, so the last bar is the one nearest the band and the caption sat on it
    # (branch 14, 2026-10-28). The band is given room past the last bar and the caption sits in it.
    ax.set_xlim(-0.6, len(rows) + 1.7)
    ax.text(len(rows) - 0.3, portfolio, f"portfolio {val(portfolio)}", ha="left", va="center",
            fontsize=11.5, color=GREY, style="italic")
    colors = [ORANGE if i == 0 else (NAVY if v >= portfolio else STEEL)
              for i, v in enumerate(rates)]
    bars = ax.bar(range(len(rows)), rates, color=colors, width=0.62,
                  zorder=2)
    for bar, rate in zip(bars, rates):
        inside = rate > scale * 0.18
        ax.text(bar.get_x() + bar.get_width() / 2,
                rate - scale * 0.05 if inside else rate + scale * 0.03,
                val(rate), ha="center", fontsize=11.5, fontweight="bold",
                color="white" if inside else NAVY, zorder=3)
    rot = 0 if len(rows) <= 9 else 28
    ax.set_xticks(range(len(rows)))
    ax.set_xticklabels(_axis_labels(labels), fontsize=11, rotation=rot,
                       ha="center" if rot == 0 else "right", color=NAVY)
    ax.set_ylim(0, scale * 1.14)
    ax.get_yaxis().set_visible(False)
    _clean(ax)
    return fig


def _branch_fig_h(rows: list, portfolio: float, fmt: str | None,
                  show_n: bool):
    from .labels import clip as _clip
    labels = [_clip(r[0], 20) + (f"  ·  {(r[2] or 0):,}" if show_n else "")
              for r in rows]
    rates = [r[3] for r in rows]
    val = (fmt.format if fmt else "{:.1f}%".format)
    scale = max(rates + [portfolio]) or 1
    fig, ax = plt.subplots(figsize=(FIG_W_FULL,
                                    max(3.6, 0.32 * len(rows) + 0.8)))
    y = list(range(len(rows)))[::-1]
    colors = [ORANGE if i == 0 else (NAVY if v >= portfolio else STEEL)
              for i, v in enumerate(rates)]
    ax.barh(y, rates, color=colors, height=0.66)
    ax.axvline(portfolio, color=GREY, lw=1.2, ls="--", alpha=0.7)
    ax.text(portfolio - scale * 0.01, len(rows) - 0.2,
            f"portfolio {val(portfolio)} ", fontsize=10.5, color=GREY,
            style="italic", va="bottom", ha="right")
    for yi, v in zip(y, rates):
        inside = v > scale * 0.16
        ax.text(v - scale * 0.012 if inside else v + scale * 0.012, yi,
                val(v), va="center", fontsize=10.5, fontweight="bold",
                ha="right" if inside else "left",
                color="white" if inside else NAVY)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10.5, color=NAVY)
    ax.set_xlim(0, scale * 1.12)
    ax.get_xaxis().set_visible(False)
    _clean(ax, bottom=False)
    return fig


def branch_bars(rows: list, portfolio: float, out: Path, top: int = 12,
                fmt: str | None = None, show_n: bool = False) -> Path:
    return _save(_branch_fig(rows, portfolio, top, fmt, show_n), out)


def response_reach_combo(rate_rows: list, cum_rows: list, out: Path) -> Path:
    """James's 6+7 combo (issue #43): response rate per offer as columns,
    cumulative reach of the eligible base as the line -- both percent, one
    axis."""
    keys = [str(r[0]) for r in rate_rows]
    rates = [r[1] for r in rate_rows]
    cum = {str(r[0]): r[1] for r in cum_rows}
    line = [cum.get(l) for l in keys]
    labels = _axis_labels(keys)
    fig, ax = plt.subplots(figsize=(FIG_W_RAIL, 4.8))
    bars = ax.bar(range(len(labels)), rates, color=NAVY, width=0.6,
                  label="response rate")
    scale = max([v for v in rates + [x for x in line if x is not None]] or [1])
    for bar, v in zip(bars, rates):
        # the cumulative-reach line climbs through these labels whenever
        # reach outruns the response rate (#72, slide 4) -- halo them so the
        # line breaks around the number rather than through it
        ax.text(bar.get_x() + bar.get_width() / 2, v + scale * 0.02,
                f"{v:.1f}%", ha="center", fontsize=10.5, fontweight="bold",
                color=NAVY,
                bbox=dict(facecolor="white", edgecolor="none", pad=0.9,
                          alpha=0.9))
    xs = [i for i, v in enumerate(line) if v is not None]
    ys = [line[i] for i in xs]
    if xs:
        ax.plot(xs, ys, color=ORANGE, lw=2.6, marker="o", ms=4,
                label="cumulative reach")
        ax.annotate(f"{ys[-1]:.1f}% reached", (xs[-1], ys[-1]),
                    xytext=(-8, 10), textcoords="offset points",
                    ha="right", fontsize=11, fontweight="bold", color=NAVY)
    rot = 0 if len(labels) <= 9 else 30
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=10.5, rotation=rot,
                       ha="center" if rot == 0 else "right", color=NAVY)
    ax.set_ylim(0, scale * 1.2)
    ax.get_yaxis().set_visible(False)
    ax.legend(frameon=False, loc="upper left", fontsize=10.5)
    _clean(ax)
    return _save(fig, out)


def gap_pairs(rows: list, out: Path) -> Path:
    """Where branches diverge (issue #43): per branch, the card gap and
    the Reg E gap vs the book, as paired horizontal bars off one zero
    line. rows: [[name, n, card_gap_pts, rege_gap_pts], ...]"""
    rows = rows[:12]
    from .labels import clip as _clip
    labels = [f"{_clip(r[0], 18)}  ·  {(r[1] or 0):,}" for r in rows]
    fig, ax = plt.subplots(figsize=(FIG_W_RAIL,
                                    max(3.6, 0.42 * len(rows) + 1.0)))
    y = np.arange(len(rows))[::-1]
    h = 0.34
    ax.barh(y + h / 2 + 0.02, [r[2] for r in rows], height=h, color=NAVY,
            label="card take vs book")
    ax.barh(y - h / 2 - 0.02, [r[3] for r in rows], height=h, color=ORANGE,
            label="Reg E vs book")
    span = max(abs(v) for r in rows for v in (r[2], r[3])) or 1
    for yi, r in zip(y, rows):
        for off, v in ((h / 2 + 0.02, r[2]), (-h / 2 - 0.02, r[3])):
            ax.text(v + (span * 0.03 if v >= 0 else -span * 0.03), yi + off,
                    f"{v:+.1f}", va="center", fontsize=9.5,
                    ha="left" if v >= 0 else "right", color=NAVY)
    ax.axvline(0, color=GREY, lw=1.2)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10.5, color=NAVY)
    ax.set_xlim(-span * 1.25, span * 1.25)
    ax.get_xaxis().set_visible(False)
    ax.legend(frameon=False, loc="lower right", fontsize=10, ncol=1)
    _clean(ax, bottom=False)
    return _save(fig, out)


def cohort_trajectory(offsets: list, series: dict, out: Path,
                      indexed: bool = True) -> Path:
    """Spend by month relative to the mail month, one line per cohort."""
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, 5.2))
    style = [
        ("responders", NAVY, 3.0, "o"),
        ("mailed_nonresp", ORANGE, 2.4, "s"),
        ("not_mailed", STEEL, 2.0, "^"),
    ]
    pretty = {"responders": "Responders",
              "mailed_nonresp": "Mailed, no response",
              "not_mailed": "Not mailed"}

    for key, color, width, marker in style:
        values = series.get(key) or []
        if not values:
            continue
        xs = [o for o, v in zip(offsets, values) if v is not None]
        ys = [v for v in values if v is not None]
        ax.plot(xs, ys, color=color, linewidth=width, marker=marker,
                markersize=5, markevery=2, label=pretty[key], zorder=3)

    ax.axvline(0, color=NAVY, lw=1.4, ls="--", alpha=0.55)
    ax.text(0.3, ax.get_ylim()[1] * 0.97, "mail month", fontsize=11,
            color=GREY, style="italic", va="top")
    if indexed:
        ax.axhline(100, color=GRID, lw=1.2)
        ax.set_ylabel("indexed to own pre-mail baseline (=100)",
                      fontsize=12.5, color=NAVY)
    else:
        ax.set_ylabel("avg monthly spend ($)", fontsize=12.5, color=NAVY)
        ax.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))

    ax.set_xlabel("months from mail", fontsize=12.5, color=NAVY)
    ax.legend(fontsize=11.5, frameon=False, loc="upper left")
    ax.yaxis.grid(True, color=GRID, linewidth=0.7)
    _clean(ax, left=True)
    return _save(fig, out)


def segment_efficiency(rows: list, out: Path) -> Path:
    """Response rate vs interchange per 1,000 mailed, one dot per offer
    segment (bubble = mailed volume). Correlation grammar: a scatter says
    "do the segments that respond also pay?" -- twin-axis bars could not."""
    rates = [r.get("response_rate", 0) for r in rows]
    per_k = [r.get("ic_per_1000_mailed", 0) or 0 for r in rows]
    mailed = [r.get("mailed", 0) or 0 for r in rows]
    max_m = max(mailed) if any(mailed) else 1

    fig, ax = plt.subplots(figsize=(FIG_W_FULL, 5.2))
    sizes = [300 + 2200 * (v / max_m) for v in mailed]
    ax.scatter(rates, per_k, s=sizes, color=NAVY, alpha=0.75, zorder=3,
               edgecolor="white", linewidth=2)
    for i, (r, x_, y_) in enumerate(zip(rows, rates, per_k)):
        # stagger: co-located dots otherwise overprint their labels
        ax.annotate(str(r["segment"]), (x_, y_), textcoords="offset points",
                    xytext=(0, 14 + 12 * (i % 3)), ha="center", fontsize=12,
                    fontweight="bold", color=NAVY)
    ax.ticklabel_format(axis="y", style="plain", useOffset=False)
    if rates and per_k:
        ax.axvline(sum(rates) / len(rates), ls="--", color=GREY, lw=1.2)
        ax.axhline(sum(per_k) / len(per_k), ls="--", color=GREY, lw=1.2)
    ax.set_xlabel("response rate (%)", fontsize=12.5, color=NAVY)
    ax.set_ylabel("interchange / 1,000 mailed ($)", fontsize=12.5, color=NAVY)
    ax.margins(0.18)
    _clean(ax, left=True)
    ax.text(0.99, 0.02, "bubble = accounts mailed", transform=ax.transAxes,
            ha="right", fontsize=10.5, color=GREY, style="italic")
    return _save(fig, out)


def leak_bars(rows: list, out: Path, unit: str = "cards", top: int = 6) -> Path:
    """Leaks ranked by accounts lost, annotated with volume vs outcome share."""
    rows = rows[:top][::-1]
    from .labels import clip as _clip
    labels = [_clip(r["segment"], 22) for r in rows]
    lost = [r["accounts_lost"] for r in rows]

    fig, ax = plt.subplots(figsize=(FIG_W_FULL, 5.2))
    y = np.arange(len(rows))
    ax.barh(y, lost, color=ORANGE, height=0.6, edgecolor="white", linewidth=1.2)

    span = max(lost) if lost else 1
    for i, row in enumerate(rows):
        ax.text(row["accounts_lost"] + span * 0.02, y[i],
                f"{row['accounts_lost']:,} {unit}   "
                f"{row['share_of_volume']:.1f}% of volume -> "
                f"{row['share_of_outcome']:.1f}% of outcome",
                va="center", fontsize=11, color=NAVY)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=12.5, color=NAVY)
    ax.set_xlim(0, span * 1.75)
    ax.get_xaxis().set_visible(False)
    _clean(ax, bottom=False)
    return _save(fig, out)


def health_bars(rows: list, out: Path) -> Path:
    """Account health distribution, at-risk states highlighted."""
    at_risk = {"Declining", "Cooling", "Dormant", "Never activated"}
    labels = [r[0] for r in rows]
    counts = [r[1] for r in rows]
    colors = [ORANGE if lab in at_risk else (TINT if lab == "No card" else GOLD)
              for lab in labels]

    fig, ax = plt.subplots(figsize=(FIG_W_RAIL, FIG_H_RAIL))
    _track(ax, range(len(rows)), max(counts) if counts else 0, width=0.62)
    bars = ax.bar(range(len(rows)), counts, color=colors, width=0.62, zorder=2)
    total = sum(counts) or 1
    for bar, n in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, n + max(counts) * 0.02,
                f"{n:,}\n{100*n/total:.1f}%", ha="center", fontsize=11,
                fontweight="bold", color=NAVY)

    ax.set_xticks(range(len(rows)))
    ax.set_xticklabels(_axis_labels(labels), fontsize=12, color=NAVY)
    ax.set_ylim(0, max(counts) * 1.2)
    ax.get_yaxis().set_visible(False)
    _clean(ax)
    return _save(fig, out)


def value_waterfall(items: list, out: Path) -> Path:
    """Recapture opportunity, largest first."""
    labels = [i[0] for i in items]
    values = [i[1] for i in items]

    fig, ax = plt.subplots(figsize=(FIG_W_RAIL, 4.8))
    y = np.arange(len(items))[::-1]
    ax.barh(y, values, color=[NAVY if v >= 0 else RED for v in values],
            height=0.6, edgecolor="white", linewidth=1.2)

    span = max(values) if values else 1
    for i, v in enumerate(values):
        ax.text(v + span * 0.02, y[i], f"${v:,.0f}", va="center",
                fontsize=13, fontweight="bold", color=NAVY)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=12.5, color=NAVY)
    ax.set_xlim(0, span * 1.35)
    ax.get_xaxis().set_visible(False)
    _clean(ax, bottom=False)
    return _save(fig, out)


def rege_split(opted, opted_out, default, blank, out: Path) -> Path:
    """Reg E election as ONE 100% stacked bar -- segments labeled inside
    when they fit, tiny segments called out above the bar.

    Authored at the RAIL slot: the only deck that places it puts it on a
    `hero` slide, whose chart field stops before the KPI card."""
    parts = [("Opt in", opted, NAVY, "white"),
             ("Opt out", opted_out, STEEL, "white"),
             ("Default", default, ORANGE, "white"),
             ("No election", blank, TINT, NAVY)]
    total = sum(v for _l, v, _c, _t in parts) or 1
    fig, ax = plt.subplots(figsize=(FIG_W_RAIL, FIG_H_RAIL))
    x = 0.0
    for label, v, color, txt in parts:
        if not v:
            continue
        w = v / total
        ax.barh(0, w, left=x, height=0.80, color=color)
        pct = 100 * v / total
        # {v:,} on a float count printed "5,093.0 accounts" on the deck
        text = f"{label}\n{v:,.0f} ({pct:.0f}%)"
        if pct >= 8:
            ax.text(x + w / 2, 0, text, ha="center", va="center",
                    fontsize=12.5, fontweight="bold", color=txt)
        else:
            ax.text(x + w / 2, 0.46, text, ha="center", va="bottom",
                    fontsize=10.5, fontweight="bold", color=NAVY)
        x += w
    ax.set_xlim(0, 1)
    # as composition: the bar is over half the axes, not a third of them
    ax.set_ylim(-0.52, 0.92)
    ax.axis("off")
    return _save(fig, out)


def _vintage_fig(rows: list, portfolio: float):
    """Opt-in rate by year opened -- ONE axis. Rates are the bars (totals
    inside), the portfolio is a band, account counts live in the tick
    labels instead of a second hidden scale."""
    years = [f"{r[0]}\nn={r[1]:,}" for r in rows]
    rates = [r[-1] for r in rows]
    scale = max(rates + [portfolio]) or 1

    fig, ax = plt.subplots(figsize=(FIG_W_RAIL, 4.6))
    band_h = scale * 0.045
    ax.axhspan(portfolio - band_h, portfolio + band_h, color="#F2F5F8",
               zorder=0)
    ax.text(len(rows) - 0.42, portfolio + band_h + scale * 0.02,
            f"portfolio {portfolio:.1f}%", ha="right", fontsize=11,
            color=GREY, style="italic")
    colors = [NAVY if v >= portfolio else STEEL for v in rates]
    bars = ax.bar(range(len(rows)), rates, color=colors, width=0.6, zorder=2)
    for bar, v in zip(bars, rates):
        inside = v > scale * 0.18
        ax.text(bar.get_x() + bar.get_width() / 2,
                v - scale * 0.055 if inside else v + scale * 0.03,
                f"{v:.0f}%", ha="center", fontsize=11.5, fontweight="bold",
                color="white" if inside else NAVY, zorder=3)
    ax.set_xticks(range(len(rows)))
    ax.set_xticklabels(years, fontsize=10.5, color=NAVY)
    ax.set_ylim(0, scale * 1.16)
    ax.get_yaxis().set_visible(False)
    _clean(ax)
    return fig


def vintage_line(rows: list, portfolio: float, out: Path) -> Path:
    return _save(_vintage_fig(rows, portfolio), out)


def tier_bars(rows: list, out: Path, value_idx: int = 1, size=None,
              label: str = "accounts", share: bool = True,
              fmt: str = "{:,.0f}") -> Path:
    """Accounts by swipe tier, non-users called out. `share=False` drops the
    percent-of-total annotation for values that are already rates."""
    rows = [r for r in rows if r[1] > 0]
    labels = [r[0] for r in rows]
    vals = [r[value_idx] for r in rows]
    # GOLD is the measured quantity; ORANGE stays the one thing being called
    # out. Every bar navy made the chart one colour and left the accent with
    # nothing to contrast against.
    colors = [ORANGE if l in ("No card", "Non-user") else GOLD for l in labels]

    fig, ax = plt.subplots(figsize=(size or (FIG_W_RAIL, FIG_H_RAIL)))
    _track(ax, range(len(rows)), max(vals) if vals else 0, width=0.64)
    bars = ax.bar(range(len(rows)), vals, color=colors, width=0.64, zorder=2)
    total = sum(vals) or 1
    for bar, v in zip(bars, vals):
        note = fmt.format(v) + (f"\n{100*v/total:.0f}%" if share else "")
        ax.text(bar.get_x() + bar.get_width()/2, v + max(vals)*0.02,
                note, ha="center", fontsize=11,
                fontweight="bold", color=NAVY)
    ax.set_xticks(range(len(rows)))
    ax.set_xticklabels(_axis_labels(labels), fontsize=12, color=NAVY)
    ax.set_ylim(0, max(vals)*1.22)
    ax.get_yaxis().set_visible(False)
    _clean(ax)
    return _save(fig, out)


def donut(rows: list, out: Path, center_label: str | None = None,
          center_value: str | None = None) -> Path:
    """Share-of-whole as a donut: [[label, value], ...]. The LAST row is
    the emphasized one (orange); earlier rows step from light to navy.
    Built for the depth slide (issue #28) -- less blue, different form."""
    rows = [r for r in rows if r[1] and r[1] > 0]
    labels = [r[0] for r in rows]
    vals = [r[1] for r in rows]
    total = sum(vals) or 1
    ramp = [TINT, STEEL, NAVY]
    colors = [ramp[min(i, len(ramp) - 1)] for i in range(len(rows))]
    colors[-1] = ORANGE
    fig, ax = plt.subplots(figsize=(FIG_W_RAIL, FIG_H_RAIL))
    wedges, _ = ax.pie(vals, colors=colors, startangle=90,
                       counterclock=False,
                       wedgeprops={"width": 0.42, "edgecolor": "white",
                                   "linewidth": 2})
    for w, lab, v in zip(wedges, labels, vals):
        ang = (w.theta1 + w.theta2) / 2
        x = np.cos(np.deg2rad(ang)); y = np.sin(np.deg2rad(ang))
        # a label on the left sits to the LEFT of its leader and one on the right to the right: a centred
        # label under a long name ran back over the ring (slide 48, 2026-10-27)
        side = "left" if x > 0.25 else "right" if x < -0.25 else "center"
        ax.annotate(f"{lab}\n{v:,.0f} · {100*v/total:.0f}%",
                    xy=(x * 0.79, y * 0.79), xytext=(x * 1.16, y * 1.16),
                    ha=side, va="center", fontsize=12, color=NAVY,
                    arrowprops={"arrowstyle": "-", "color": GREY, "lw": 0.8})
    if center_value:
        ax.text(0, 0.10, center_value, ha="center", va="center",
                fontsize=26, fontweight="bold", color=NAVY)
    if center_label:
        ax.text(0, -0.18, center_label, ha="center", va="center",
                fontsize=12, color=GREY)
    ax.set(aspect="equal")
    return _save(fig, out)


def composition(rows: list, out: Path, highlight: str | None = None,
                size=None) -> Path:
    """One horizontal 100% bar: [[label, value], ...]. `highlight` names
    the orange segment; the rest step light-to-steel. Built for the
    activation slide (issue #28) -- a different form from the bar charts
    around it, and far less blue.

    `size` because this is the one form the ILS deck uses in TWO slots --
    full-bleed for Product Code's 24 bands, rail-width for the Reg E
    business split -- and a canvas authored for one lands wrong in the
    other."""
    rows = [r for r in rows if r[1] and r[1] > 0]
    total = sum(r[1] for r in rows) or 1
    fig, ax = plt.subplots(figsize=(size or (FIG_W_RAIL, FIG_H_RAIL)))
    left = 0.0
    ramp = [TINT, STEEL, NAVY]
    ri = 0
    for lab, v in rows:
        if highlight and lab == highlight:
            color = ORANGE
        else:
            color = ramp[min(ri, len(ramp) - 1)]
            ri += 1
        share = v / total
        ax.barh([0], [share], left=left, color=color, height=0.72,
                edgecolor="white", linewidth=2)
        dark = color in (NAVY, ORANGE)
        if share >= 0.09:
            ax.text(left + share / 2, 0, f"{100*share:.0f}%",
                    ha="center", va="center", fontsize=15, fontweight="bold",
                    color="white" if dark else NAVY)
        cx = left + share / 2
        ha = "center"
        if cx > 0.92:
            cx, ha = 1.0, "right"
        elif cx < 0.08:
            cx, ha = 0.0, "left"
        ax.text(cx, 0.46, f"{lab}\n{v:,.0f}", ha=ha,
                va="bottom", fontsize=12, color=NAVY)
        left += share
    # The bar is 0.72 of a 1.42 range rather than 0.42 of 1.70: half the
    # axes instead of a quarter. On the 4.90in band the old proportions put
    # a one-inch bar in the middle of four inches of white.
    # top margin is the label row and no more: 0.96 left an inch and a half
    # of nothing between the subtitle and the first band name
    ax.set_xlim(0, 1); ax.set_ylim(-0.46, 0.70)
    ax.axis("off")
    return _save(fig, out)


def ticket_bars(rows: list, blended: float, out: Path,
                value_fmt: str = "${:,.0f}",
                xlabel: str = "monthly swipe tier") -> Path:
    """A per-band measure against the blended figure for the whole population.

    Built for average ticket by swipe tier, so it printed a dollar sign and
    named its x axis after swipes. The ILS kickoff deck feeds it PAY RATES,
    and the deck went to a client reading "$74" over a 74% band and "monthly
    swipe tier" under OD/NSF bands. A unit is the caller's fact, never the
    form's -- the form draws bars against a line."""
    labels = [r[0] for r in rows]
    vals = [r[2] for r in rows]
    fig, ax = plt.subplots(figsize=(FIG_W_RAIL, FIG_H_RAIL))
    bars = ax.bar(range(len(rows)), vals, color=NAVY, width=0.6)
    if bars: bars[-1].set_color(ORANGE)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x()+bar.get_width()/2, v+max(vals)*0.025,
                value_fmt.format(v),
                ha="center", fontsize=12, fontweight="bold", color=NAVY)
    ax.axhline(blended, ls="--", color=ORANGE, lw=2)
    # x=0.02 is a DATA coordinate, and bar 0 spans -0.3 to 0.3, so the
    # blended label sat on the first bar by construction (#82, slide 44).
    # Put it over the bar with the most room under the line instead; when
    # every bar clears it, use the headroom set_ylim reserves above the
    # tallest, where no bar can reach.
    room = [(blended - v, i) for i, v in enumerate(vals) if v < blended]
    if room:
        _gap, slot = max(room)
        label_x, label_y, align = slot, blended + max(vals) * 0.03, "center"
    else:
        label_x, label_y, align = len(vals) - 0.5, max(vals) * 1.12, "right"
    ax.text(label_x, label_y, f"blended {value_fmt.format(blended)}",
            fontsize=11.5, color=ORANGE, fontweight="bold", ha=align)
    ax.set_xticks(range(len(rows)))
    ax.set_xticklabels(_axis_labels(labels), fontsize=12.5, color=NAVY)
    ax.set_ylim(0, max(vals)*1.2)
    ax.get_yaxis().set_visible(False)
    ax.set_xlabel(xlabel, fontsize=12, color=GREY)
    _clean(ax)
    return _save(fig, out)


def _dual_fig(series: list, l1="Spend", l2="Swipes"):
    """Two measures, ONE axis: both indexed to the first month = 100, so
    the frame compares trajectories instead of hiding two scales."""
    labels = _axis_labels([r[0] for r in series])

    def _index(vals):
        base = next((v for v in vals if v), None) or 1
        return [100 * v / base for v in vals]

    a = _index([r[1] for r in series])
    b = _index([r[2] for r in series])
    fig, ax = plt.subplots(figsize=(FIG_W_RAIL, 4.8))
    ax.axhline(100, color=GRID, lw=1.4)
    ax.plot(range(len(series)), a, color=ORANGE, lw=2.6, marker="o",
            markersize=5, markerfacecolor="white", markeredgecolor=ORANGE)
    ax.plot(range(len(series)), b, color=STEEL, lw=2.4, ls="--")
    ax.text(len(series) - 0.85, a[-1], f"  {l1} {a[-1]:.0f}", fontsize=11.5,
            fontweight="bold", color=ORANGE, va="center")
    ax.text(len(series) - 0.85, b[-1], f"  {l2} {b[-1]:.0f}", fontsize=11.5,
            fontweight="bold", color=STEEL, va="center")
    ax.set_ylabel("indexed, first month = 100", fontsize=11.5, color=NAVY)
    step = max(1, len(labels)//12)
    ax.set_xticks(range(0, len(labels), step))
    ax.set_xticklabels(labels[::step], fontsize=11, rotation=45, ha="right",
                       color=NAVY)
    ax.yaxis.grid(True, color=GRID, lw=0.7)
    _clean(ax, left=True)
    return fig


def dual_series(series: list, out: Path, l1="Spend", l2="Swipes") -> Path:
    return _save(_dual_fig(series, l1, l2), out)


def _money_tick(v, _pos=None) -> str:
    """$2.5M / $750K / $900 -- an axis in the deck's one money grammar (labels.money), so a tick
    and the label beside it never spell the same figure two ways (2026-10-28)."""
    from .labels import money
    return money(v)


def _line_series_fig(series: list, ylabel="", pct=False,
                     highlight_zero=False, money=False):
    """`money=True` formats the axis in dollars. Without it matplotlib
    prints a bare 1e6 above the axis, which is what the deposit deck's
    first real render showed over twelve months of inflow."""
    labels = _axis_labels([r[0] for r in series])
    vals = [r[1] for r in series]
    fig, ax = plt.subplots(figsize=(FIG_W_RAIL, FIG_H_RAIL))
    ax.plot(range(len(series)), vals, color=NAVY, lw=3, marker="o",
            markersize=6, markerfacecolor="white", markeredgewidth=2,
            markeredgecolor=NAVY)
    if highlight_zero:
        ax.axhline(0, color=GREY, lw=1.4, ls="--")
    ax.fill_between(range(len(series)), vals, color=NAVY, alpha=0.07)
    step = max(1, len(labels)//14)
    ax.set_xticks(range(0, len(labels), step))
    ax.set_xticklabels(labels[::step], fontsize=10.5, rotation=45, ha="right",
                       color=NAVY)
    if ylabel: ax.set_ylabel(ylabel, fontsize=12, color=NAVY)
    if pct:
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"{v:,.0f}%"))
    elif money:
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(_money_tick))
    ax.yaxis.grid(True, color=GRID, lw=0.7)
    _clean(ax, left=True)
    return fig, {"points": len(series)}


def line_series(series: list, out: Path, ylabel="", pct=False,
                highlight_zero=False, money=False) -> Path:
    fig, _ = _line_series_fig(series, ylabel, pct, highlight_zero, money)
    return _save(fig, out)


def histogram(bins: list, out: Path, mean=None, median=None,
              xlabel: str = "swipes above the account's own prior run rate"
              ) -> Path:
    """Counts per band. The axis names whatever the bands measure -- the
    swipe-lift wording is this form's origin, not its subject: the ILS deck
    banded DEPOSITS PER MONTH and printed the swipe sentence under them."""
    # Both markers label themselves with it, so it cannot live inside the
    # `mean` branch: a caller passing only `median` hit UnboundLocalError.
    from .labels import signed as _signed

    xs = [b[0] for b in bins]
    ys = [b[1] for b in bins]
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, FIG_H_FULL))
    _track(ax, range(len(xs)), max(ys) if ys else 0, width=0.86)
    ax.bar(xs, ys, color=GOLD, width=0.86, zorder=2)
    if mean is not None:
        ax.axvline(mean, color=ORANGE, lw=2.4, ls="--")
        ax.text(mean+0.6, max(ys)*0.92, f"mean {_signed(mean)}", color=ORANGE,
                fontsize=12, fontweight="bold")
    if median is not None:
        ax.axvline(median, color=STEEL, lw=2, ls=":")
        ax.text(median+0.6, max(ys)*0.78, f"median {_signed(median)}",
                color=STEEL,
                fontsize=11.5)
    ax.set_xlabel(xlabel, fontsize=12, color=GREY)
    if xs and xs[0] == -1:
        # the leftmost bin is 'fell below own baseline', not a number
        # skip the 0 tick: at rail width, "fell" and "0" sit one bar
        # apart and render as "fell0" (M4 sweep, slide 51)
        ticks = [-1] + [t for t in range(5, 41, 5)]
        ax.set_xticks(ticks)
        ax.set_xticklabels(["fell"] + [str(t) if t < 40 else "40+"
                                       for t in ticks[1:]])
    ax.get_yaxis().set_visible(False)
    _clean(ax)
    return _save(fig, out)


def _grouped_on_ax(ax, labels, a_vals, b_vals, a_lab, b_lab,
                   fmt="{:,.0f}", legend=True, label_size=12):
    """Two bars per label on a prepared axis; the shared body of
    grouped_bars and the twin-panel profile figure."""
    x = np.arange(len(labels)); w = 0.38
    if len(labels) == 1:
        w = 0.16                      # two giant slabs otherwise
        ax.set_xlim(-0.9, 0.9)
    _track(ax, x, max(list(a_vals) + list(b_vals) or [0]), width=w * 2.1)
    b1 = ax.bar(x-w/2, a_vals, w, color=NAVY, label=a_lab, zorder=2)
    b2 = ax.bar(x+w/2, b_vals, w, color=GOLD, label=b_lab, zorder=2)
    top = max(list(a_vals)+list(b_vals)) or 1
    for bars in (b1,b2):
        for bar in bars:
            if not bar.get_height():
                continue          # a zero series gets no label: ten "$0"s said nothing (2026-10-28)
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+top*0.025,
                    _fmt(fmt, bar.get_height()), ha="center", fontsize=11,
                    fontweight="bold", color=NAVY)
    ax.set_xticks(x); ax.set_xticklabels(_axis_labels(labels), fontsize=label_size, color=NAVY)
    ax.set_ylim(0, top*1.2)
    ax.get_yaxis().set_visible(False)
    # Above the axes, not inside it (#72). An upper-right legend sits exactly
    # where the tallest bar's value label lands whenever the tallest pair is
    # on the right, which is how slide 60 hid its '579'.
    if legend:
        ax.legend(fontsize=11.5, frameon=False, loc="lower right",
                  bbox_to_anchor=(1, 1.01), ncol=2)
    _clean(ax)


def grouped_bars(labels, a_vals, b_vals, a_lab, b_lab, out: Path,
                 size=None,
                 fmt="{:,.0f}") -> Path:
    fig, ax = plt.subplots(figsize=(size or (FIG_W_RAIL, FIG_H_RAIL)))
    _grouped_on_ax(ax, labels, a_vals, b_vals, a_lab, b_lab, fmt=fmt)
    return _save(fig, out)


PROFILE_PANELS = (("age", "By holder age"), ("balance", "By balance band"))


def _profile_twins_fig(age_rows: list, bal_rows: list):
    """Who responds, by holder age and by balance band, side by side.
    rows per side: [[band, eligible, responded], ...]. A side with no
    rows is left out rather than drawn empty (#53 P1)."""
    sides = [(key, title, rows) for (key, title), rows in
             zip(PROFILE_PANELS, (age_rows, bal_rows)) if rows]
    fig, axes = plt.subplots(1, max(len(sides), 1),
                             figsize=(FIG_W_RAIL, FIG_H_RAIL), squeeze=False)
    bars = []
    for i, (ax, (key, title, rows)) in enumerate(zip(axes[0], sides)):
        _grouped_on_ax(ax, [r[0] for r in rows], [r[1] for r in rows],
                       [r[2] for r in rows], "eligible", "responded",
                       legend=(i == len(sides) - 1), label_size=10.5)
        # the caption sits under the bands: the legend lives above the
        # right-hand panel and a title there collides with it
        ax.set_xlabel(title, fontsize=12, fontweight="bold", color=NAVY,
                      labelpad=10)
        bars.append(len(rows) * 2)
    fig.tight_layout(w_pad=2.0)
    return fig, {"panels": [s[0] for s in sides], "bars": bars}


def profile_twins(age_rows: list, bal_rows: list, out: Path) -> Path:
    fig, _ = _profile_twins_fig(age_rows, bal_rows)
    return _save(fig, out)


def _openings_fig(rows: list):
    """Openings up, closures down, running net as a line -- all account
    counts, ONE axis."""
    labels = _axis_labels([r[0] for r in rows])
    opens = [r[1] for r in rows]
    closes = [-r[2] for r in rows]
    net = [r[3] for r in rows]
    fig, ax = plt.subplots(figsize=(FIG_W_RAIL, 4.8))
    ax.bar(range(len(rows)), opens, color=NAVY, width=0.66, label="opened")
    ax.bar(range(len(rows)), closes, color=ORANGE, width=0.66, label="closed")
    ax.axhline(0, color=GREY, lw=1.2)
    ax.plot(range(len(rows)), net, color=STEEL, lw=2.4, marker="o",
            markersize=4, label="running net")
    ax.text(len(rows) - 0.8, net[-1], f"  net {net[-1]:+,}", fontsize=11,
            fontweight="bold", color=STEEL, va="center")
    step = max(1, len(labels)//12)
    ax.set_xticks(range(0, len(labels), step))
    ax.set_xticklabels(labels[::step], fontsize=11, rotation=45, ha="right",
                       color=NAVY)
    ax.legend(fontsize=11, frameon=False, loc="upper left", ncols=3)
    _clean(ax, left=True)
    return fig


def openings_chart(rows: list, out: Path) -> Path:
    return _save(_openings_fig(rows), out)


# ---------------------------------------------------------------------------
# the owned icon set (DESIGN/ spec): 8 line icons drawn as vectors, cached
# as transparent PNGs, used on KPI tiles. Strokes in LIGHT so they read on
# navy; one orange accent stroke each. No clip-art, no emojis.
# ---------------------------------------------------------------------------

ICON_KINDS = ("mailing", "lift", "value", "shield", "card", "branch",
              "members", "target")


def icon(kind: str, out: Path) -> Path:
    import matplotlib.lines as ml
    import matplotlib.patches as mp
    fig = plt.figure(figsize=(0.5, 0.5), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 44); ax.set_ylim(0, 44)
    ax.invert_yaxis(); ax.axis("off")
    lw, C, A = 2.6, ICON_STROKE, ORANGE
    add, seg = ax.add_patch, ax.add_line

    if kind == "mailing":
        add(mp.FancyBboxPatch((5, 11), 34, 22, boxstyle="round,pad=0,rounding_size=2",
                              fill=False, edgecolor=C, lw=lw))
        seg(ml.Line2D([5, 22, 39], [13, 26, 13], color=A, lw=lw))
    elif kind == "lift":
        seg(ml.Line2D([6, 16, 24, 38], [34, 24, 29, 12], color=C, lw=lw))
        seg(ml.Line2D([29, 38, 38], [12, 12, 21], color=A, lw=lw))
    elif kind == "value":
        add(mp.Circle((22, 22), 16, fill=False, edgecolor=C, lw=lw))
        ax.text(22, 23, "$", ha="center", va="center", fontsize=11,
                fontweight="bold", color=A)
    elif kind == "shield":
        seg(ml.Line2D([22, 35, 35, 22, 9, 9, 22], [5, 10, 20, 39, 20, 10, 5],
                      color=C, lw=lw))
        seg(ml.Line2D([15, 20, 29], [22, 27, 17], color=A, lw=lw))
    elif kind == "card":
        add(mp.FancyBboxPatch((5, 10), 34, 24, boxstyle="round,pad=0,rounding_size=3",
                              fill=False, edgecolor=C, lw=lw))
        seg(ml.Line2D([5, 39], [17, 17], color=A, lw=lw + 1.2))
        seg(ml.Line2D([10, 22], [27, 27], color=C, lw=lw))
    elif kind == "branch":
        for x0, h in ((8, 8), (19, 16), (30, 24)):
            add(mp.Rectangle((x0, 36 - h), 6, h, fill=False, edgecolor=C, lw=lw))
        seg(ml.Line2D([5, 39], [36, 36], color=A, lw=lw))
    elif kind == "members":
        add(mp.Circle((17, 16), 6, fill=False, edgecolor=C, lw=lw))
        seg(ml.Line2D([6, 6.5, 28], [36, 30, 36], color=C, lw=lw))
        add(mp.Circle((33, 14), 4, fill=False, edgecolor=A, lw=lw))
    elif kind == "target":
        add(mp.Circle((22, 22), 16, fill=False, edgecolor=C, lw=lw))
        add(mp.Circle((22, 22), 9, fill=False, edgecolor=A, lw=lw))
        add(mp.Circle((22, 22), 2.5, color=A))
    else:
        raise ValueError(f"unknown icon kind {kind!r}")

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, transparent=True)
    plt.close(fig)
    return out


def combo_lines(detail: dict, out: Path) -> Path:
    fig, _ = _combo_fig(detail)
    return _save(fig, out)


def _combo_fig(detail: dict):
    """One offer's behavior by segment: swipes (top) and spend (bottom)
    per mailed account, months relative to the mail month. One y-axis per
    panel; the mail month is the orange line. On the long window the
    x-axis labels every 6th month -- 49 ticks is soup."""
    offsets = detail["offsets"]
    segments = detail["segments"]
    # navy-anchored ramp, oldest habit (No card/Non-user) warmest
    ramp = ["#C0392B", "#E8862E", "#8A6118", "#2A9D8F",
            "#4E7EAE", "#12406E", "#5A6B7C", "#8896A6", "#B3BEC9"]
    colors = {s: ramp[i % len(ramp)] for i, s in enumerate(segments)}
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(FIG_W_FULL, 5.6),
                                   sharex=True)
    for ax, series, label in ((ax1, detail["swipes"], "swipes / acct"),
                              (ax2, detail["spend"], "$ / acct")):
        for s in segments:
            ax.plot(offsets, series[s], color=colors[s], lw=2.0,
                    label=f"{s}  ({detail['counts'][s]:,})")
        ax.axvline(0, color=ORANGE, lw=1.8, ls="--", alpha=0.85)
        ax.set_ylabel(label, fontsize=11, color=GREY)
        _clean(ax)
    ax1.legend(loc="lower left", bbox_to_anchor=(0, 1.02), fontsize=9,
               ncol=min(len(segments), 5), frameon=False)
    ax2.set_xlabel("months relative to the mail month", fontsize=11,
                   color=GREY)
    if len(offsets) > 20:
        ticks = [o for o in offsets if o % 6 == 0]
    else:
        ticks = list(offsets)
    ax2.set_xticks(ticks)
    fig.subplots_adjust(hspace=0.12)
    return fig, {"ticks": ticks}


def ops_kpi_columns(rows: list, take_book: float, rege_book: float,
                    out: Path) -> Path:
    """The Operational KPIs slide's chart (#62, James's slot 5): grouped
    columns per branch -- take rate (navy) and Reg E opt-in (orange) as
    ACTUAL rates side by side, each metric's book rate as a dashed
    reference line, below-book value labels in red, eligible-account
    count under every branch name. rows: [[branch, n, take, rege], ...]
    (caller caps at 8 and states coverage)."""
    rows = [r for r in rows if r[1]]
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, 4.2))
    idx = range(len(rows))
    w = 0.34
    scale = max([r[2] for r in rows] + [take_book]) or 1
    for i, (name, n_e, take, rege) in enumerate(rows):
        ax.bar(i - w / 2, take, width=w, color=NAVY)
        ax.bar(i + w / 2, rege, width=w, color=ORANGE)
        # A branch AT its book rate puts the dashed reference line straight
        # through the digits, and no anchor avoids that (#72). The halo lets
        # the line break around the number instead.
        halo = dict(facecolor="white", edgecolor="none", pad=0.9, alpha=0.9)
        ax.text(i - w / 2, take + scale * .02, f"{take:.1f}%", ha="center",
                fontsize=10.5, fontweight="bold", bbox=halo,
                color=RED if take < take_book else NAVY)
        ax.text(i + w / 2, rege + scale * .02, f"{rege:.1f}%", ha="center",
                fontsize=10.5, fontweight="bold", bbox=halo,
                color=RED if rege < rege_book else NAVY)
    ax.axhline(take_book, color=NAVY, linestyle=(0, (5, 4)), linewidth=1.1)
    ax.axhline(rege_book, color=ORANGE, linestyle=(0, (5, 4)), linewidth=1.1)
    # The reference captions get their own lane ABOVE the axes (#72). Inside
    # the plot there is no safe anchor: at the right edge they sat under the
    # last branch's value labels (slide 6 printed '49.6%' through 'book Reg E
    # 49.0%'), and at the left edge they sit under the first branch's. Out of
    # the plot they cannot collide with a bar label at all.
    import matplotlib.lines as _ml
    book_handles = [
        _ml.Line2D([], [], color=NAVY, linestyle=(0, (5, 4)), linewidth=1.1),
        _ml.Line2D([], [], color=ORANGE, linestyle=(0, (5, 4)), linewidth=1.1),
    ]
    ax.legend(book_handles,
              [f"book take {take_book:.1f}%", f"book Reg E {rege_book:.1f}%"],
              loc="lower right", bbox_to_anchor=(1, 1.01), ncol=2,
              frameon=False, fontsize=9.5)
    ax.set_xticks(list(idx))
    ax.set_xticklabels([f"{r[0]}\n{r[1]:,}" for r in rows], fontsize=10.5,
                       color=NAVY)
    ax.set_ylim(0, scale * 1.18)
    ax.get_yaxis().set_visible(False)
    _clean(ax)
    return _save(fig, out)


TIER_RAMP = [ORANGE, NAVY, STEEL, TINT, "#7FA65A", GREY]


def trajectory_lines(offsets: list, by_tier: dict, control: list,
                     out: Path, ylabel: str = "") -> Path:
    """James's lines (#62): per-segment responder trajectories around the
    mail month (offset 0 marked), pooled control dashed grey. X spans
    whatever the data covers (-12 .. +36 by design)."""
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, 4.3))
    for i, (tier, series) in enumerate(sorted(by_tier.items())):
        color = TIER_RAMP[i % len(TIER_RAMP)]
        pts = [(o, v) for o, v in zip(offsets, series) if v is not None]
        if len(pts) < 2:
            continue
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=color,
                linewidth=2.2)
        ax.annotate(str(tier), xy=pts[-1], xytext=(4, 0),
                    textcoords="offset points", fontsize=10, color=color,
                    fontweight="bold", va="center")
    if control:
        pts = [(o, v) for o, v in zip(offsets, control) if v is not None]
        if len(pts) >= 2:
            ax.plot([p[0] for p in pts], [p[1] for p in pts], color=GREY,
                    linewidth=1.8, linestyle=(0, (5, 4)))
            ax.annotate("control", xy=pts[-1], xytext=(4, 0),
                        textcoords="offset points", fontsize=10,
                        color=GREY, va="center")
    ax.axvline(0, color=ORANGE, linewidth=1.2, linestyle=(0, (3, 3)))
    ax.text(0, ax.get_ylim()[1], " mail", fontsize=9.5, color=ORANGE,
            va="top")
    ax.set_xlabel("months from the mail", fontsize=10, color=GREY)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10, color=GREY)
    _clean(ax, left=True)
    return _save(fig, out)


# ---------------------------------------------------------------------------
# The six v4 forms (deck build queue; mockup:
# ars/lab/DESIGN/report-mockups/deck-12-preview-v5.html). Shared vocabulary:
# 45-degree angle-cut marks, Montserrat-weight numbers via fontweight, the
# second measured layer (ratio track / ask-vs-delivered / momentum arrows).
# Each renderer keeps the module contract: plain values in, PNG out, and a
# ``_*_fig`` helper returning (fig, meta) so structure is testable without
# reading pixels.
# ---------------------------------------------------------------------------

AMBER = "#B8860B"

_RAG = {
    "green": {"glyph": "▲", "color": GREEN, "bg": "#F7F8FA"},
    "amber": {"glyph": "■", "color": AMBER, "bg": "#FBF7EC"},
    "red":   {"glyph": "▼", "color": RED,   "bg": "#FDF3F1"},
}


def _cap(ax, x0, x1, y, depth, color, up=True):
    """The 45-degree angle-cut cap: a translucent trapezoid on a bar end."""
    inset = min(depth, (x1 - x0) * 0.16)
    y2 = y + depth if up else y - depth
    ax.add_patch(plt.Polygon(
        [(x0, y), (x1, y), (x1 - inset, y2), (x0 + inset, y2)],
        closed=True, facecolor=color, alpha=0.35, edgecolor="none"))


def _hbar_cut(ax, y0, y1, length, color):
    """Horizontal bar with the right end cut at 45 degrees."""
    cut = min((y1 - y0) * 1.0, length * 0.08)
    ax.add_patch(plt.Polygon(
        [(0, y0), (length, y0), (length - cut, y1), (0, y1)],
        closed=True, facecolor=color, edgecolor="none"))


def _block_cut(ax, x, y, w, h, color):
    """Rectangle with the bottom-left corner cut at 45 degrees."""
    c = min(w, h) * 0.18
    ax.add_patch(plt.Polygon(
        [(x + c, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y + c)],
        closed=True, facecolor=color, edgecolor="none"))


def _waterfall_fig(steps: list, ratio: dict | None):
    """Bridge waterfall. steps: [[label, value, kind], ...] with kind in
    start/down/up/end; the end bar must equal the running total (measured
    history -- a bridge that doesn't reconcile is a wrong chart, not a
    style choice). ratio: optional mini ratio-track panel dict with
    points/target/target_label/current_label."""
    kinds = {"start", "down", "up", "end"}
    for label, value, kind in steps:
        if kind not in kinds:
            raise ValueError(f"unknown waterfall kind {kind!r} on {label!r}")
    running = 0.0
    segments = []
    for label, value, kind in steps:
        if kind == "start":
            running = value
            segments.append((label, 0.0, float(value)))
        elif kind in ("down", "up"):
            lo, hi = sorted((running, running + value))
            segments.append((label, float(lo), float(hi)))
            running += value
        else:                                            # end
            if abs(value - running) > max(0.01, abs(running) * 1e-6):
                raise ValueError(
                    f"end step {label!r} = {value} but the bridge lands on "
                    f"{running:.2f}")
            segments.append((label, 0.0, float(running)))

    fig = plt.figure(figsize=(FIG_W_FULL, 4.4))
    main_w = 0.78 if ratio else 0.97
    ax = fig.add_axes([0.02, 0.10, main_w - 0.02, 0.82])
    colors = {"start": NAVY, "down": RED, "up": ORANGE, "end": GREEN}
    span = max(t for _, _, t in segments) - min(b for _, b, _ in segments)
    w = 0.62
    prev_top = None
    for i, ((label, value, kind), (_, bottom, top)) in enumerate(
            zip(steps, segments)):
        color = colors[kind]
        ax.add_patch(plt.Rectangle((i - w / 2, bottom), w, top - bottom,
                                   facecolor=color, edgecolor="none"))
        cap_y = top if kind != "down" else bottom
        _cap(ax, i - w / 2, i + w / 2, cap_y, span * 0.045, color,
             up=(kind != "down"))
        # The values are dollars. This printed "$79,340,378.0K" (a K pinned on a full figure,
        # 2026-10-28); the deck's one grammar gives "$79.3M" / "+$24.4M".
        from .labels import money
        if kind == "start" or kind == "end":
            text = money(value)
        else:
            sign = "−" if value < 0 else "+"
            text = f"{sign}{money(abs(value))}"
        ax.text(i, top + span * 0.05, text, ha="center", va="bottom",
                fontsize=12, fontweight="bold", color=color)
        if prev_top is not None:
            level = segments[i - 1][2] if steps[i - 1][2] != "down" \
                else segments[i - 1][1]
            ax.plot([i - 1 + w / 2, i - w / 2], [level, level],
                    color=TINT, linestyle=(0, (4, 3)), linewidth=1.1)
        prev_top = top
        # A long category name wraps rather than being cut ("Investment/Brok…", 2026-10-28)
        import textwrap
        ax.text(i, min(b for _, b, _ in segments) - span * 0.06,
                textwrap.fill(str(label), 16, break_long_words=False),
                ha="center", va="top", fontsize=11, color=GREY)
    lo = min(b for _, b, _ in segments)
    hi = max(t for _, _, t in segments)
    ax.set_xlim(-0.6, len(steps) - 0.4)
    ax.set_ylim(lo - span * 0.18, hi + span * 0.20)
    if lo < 0:
        ax.axhline(0, color="#B8C0CA", linewidth=1.0)
    ax.axis("off")

    ratio_drawn = False
    if ratio:
        axr = fig.add_axes([main_w + 0.02, 0.16, 0.95 - main_w, 0.60])
        pts = ratio["points"]
        axr.plot(range(len(pts)), pts, color=ORANGE, linewidth=2.2)
        axr.plot(len(pts) - 1, pts[-1], "o", color=ORANGE, markersize=5)
        axr.axhline(ratio["target"], color=GREEN, linestyle=(0, (4, 3)),
                    linewidth=1.2)
        axr.text(0, ratio["target"], ratio.get("target_label", ""),
                 fontsize=9, color=GREEN, va="bottom")
        axr.annotate(ratio.get("current_label", ""),
                     xy=(len(pts) - 1, pts[-1]), xytext=(0, 6),
                     textcoords="offset points", ha="right", fontsize=11,
                     fontweight="bold", color=ORANGE)
        axr.set_title("RATIO TRACK", fontsize=10, fontweight="bold",
                      color=NAVY, loc="left")
        axr.axis("off")
        ratio_drawn = True

    return fig, {"segments": segments, "ratio_drawn": ratio_drawn}


def waterfall_bridge(steps: list, out: Path, ratio: dict | None = None) -> Path:
    fig, _ = _waterfall_fig(steps, ratio)
    return _save(fig, out)


def _category_blocks_fig(rows: list):
    """Angle-cut category blocks: a hero block (first row) plus up to four
    supporting blocks. rows: [[name, value_label, subline, trend], ...]."""
    rows = rows[:5]
    fig, ax = plt.subplots(figsize=(FIG_W_RAIL, FIG_H_RAIL))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    palette = [(NAVY, "white"), (STEEL, "white"), (ORANGE, "white"),
               (TINT, NAVY), (GRID, NAVY)]
    # hero spans the left; the rest tile a 2x2 grid on the right
    cells = [(0, 0, 44, 100)] + [
        (47, 52, 25, 48), (74, 52, 26, 48), (47, 0, 25, 48), (74, 0, 26, 48)]
    for (name, value, sub, trend), (x, y, w, h), (bg, fgc) in zip(
            rows, cells, palette):
        _block_cut(ax, x, y, w, h, bg)
        inner = w * 0.88                     # the block's own width, less its two margins
        fit_text(ax, x + w * 0.06, y + h - 6, inner, f"{name} · {value}",
                 13 if h > 60 else 11.5, floor=9, fontweight="bold", color=fgc, va="top")
        fit_text(ax, x + w * 0.06, y + h - 16 - (4 if h > 60 else 0), inner, sub,
                 9.5, floor=8, max_lines=3, color=fgc, va="top", alpha=0.9)
        cut = min(w, h) * 0.18
        ax.text(x + cut + 1.2, y + 4, trend, fontsize=9.5, fontweight="bold",
                color=fgc, va="bottom")
    return fig, {"blocks": len(rows), "hero": rows[0][0] if rows else None}


def category_blocks(rows: list, out: Path, note: str = "") -> Path:
    fig, _ = _category_blocks_fig(rows)
    if note:
        ax = fig.axes[0]
        ax.set_ylim(-13, 100)
        ax.text(0, -6, note, fontsize=10, color=GREY, va="top")
    return _save(fig, out)


MOMENTUM_HEADERS = ("INSTITUTION \u00b7 REACH", "DEPTH", "MOMENTUM")


def _momentum_fig(rows: list, footnote: str, headers=None,
                  mark_label: str = "local", momentum_unit: str = "%"):
    """A ranked list: a bar (angle-cut), a second column, a movement column.
    rows: [[name, count, depth_label, momentum_pct|None, marked], ...]; the
    marked row's bar is orange. Growth is the red signal; decline is green;
    None is flat.

    Built for ranked COMPETITORS, and its vocabulary said so from inside:
    three hardcoded headers, and "\u00b7 local" appended to the marked row.
    The ILS kickoff deck ranks overdraft-limit bands with it, and the slide
    read "5,629 \u00b7 local" under a header saying "INSTITUTION \u00b7 REACH".
    Both are the caller's words now.

    A momentum column where every row is None is a column of "\u2192 flat"
    that says nothing, so it is not drawn at all."""
    headers = headers or MOMENTUM_HEADERS
    show_momentum = any(r[3] is not None for r in rows) and len(headers) > 2 \
        and headers[2]
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, FIG_H_FULL))
    names, bar_colors, momentum_texts = [], [], []
    max_n = max(r[1] for r in rows) or 1
    bar_span = 58.0
    for i, (name, count, depth, momentum, local) in enumerate(rows):
        y = len(rows) - 1 - i
        color = ORANGE if local else NAVY
        names.append(name)
        bar_colors.append(color)
        length = count / max_n * bar_span
        _hbar_cut(ax, y + 0.24, y + 0.66, length, color)
        ax.text(-1.2, y + 0.45, name, ha="right", va="center", fontsize=11,
                fontweight="bold", color=color)
        suffix = f" \u00b7 {mark_label}" if (local and mark_label) else ""
        ax.text(length + 1.0, y + 0.45, f"{count:,}" + suffix,
                va="center", fontsize=11, fontweight="bold", color=NAVY)
        ax.text(74, y + 0.45, depth, va="center", fontsize=10.5, color=GREY)
        # The unit is the caller's: "%" for a rate of change, "" for a net count of accounts, which
        # printed as "+14150%" when the column was handed net new accounts (2026-10-28).
        if momentum is None:
            mtext, mcolor = "→ flat", GREY
        elif momentum_unit == "%":
            mtext, mcolor = (f"↗ +{momentum:g}%", RED) if momentum > 0 else (f"↘ −{abs(momentum):g}%", GREEN)
        else:
            mtext, mcolor = (f"↗ +{momentum:,.0f}", RED) if momentum > 0 else (f"↘ −{abs(momentum):,.0f}", GREEN)
        momentum_texts.append(mtext)
        if show_momentum:
            ax.text(86, y + 0.45, mtext, va="center", fontsize=10.5,
                    fontweight="bold", color=mcolor)
    columns = [(0, headers[0]), (74, headers[1])]
    if show_momentum:
        columns.append((86, headers[2]))
    for x, header in columns:
        if not header:
            continue
        ax.text(x, len(rows) + 0.28, header, fontsize=9, fontweight="bold",
                color=GREY)
    if footnote:
        ax.text(0, -0.42, footnote, fontsize=9, color=GREY)
    ax.set_xlim(-16, 100)
    ax.set_ylim(-0.6, len(rows) + 0.7)
    ax.axis("off")
    return fig, {"names": names, "bar_colors": bar_colors,
                 "momentum_texts": momentum_texts}


def momentum_bars(rows: list, out: Path, footnote: str = "", headers=None,
                  mark_label: str = "local", momentum_unit: str = "%") -> Path:
    fig, _ = _momentum_fig(rows, footnote, headers, mark_label, momentum_unit)
    return _save(fig, out)


def _flow_fig(source: dict, dests: list, footnote: str):
    """Flow ribbons from one source block to named destinations, ribbon
    width proportional to value, biggest drain first. source:
    {count, count_label, held, drain}; dests: [[name, sub, value], ...]."""
    dests = sorted(dests, key=lambda d: -d[2])
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, 4.2))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    _block_cut(ax, 2, 8, 17, 84, NAVY)
    ax.text(10.5, 74, source.get("count", ""), ha="center", fontsize=17,
            fontweight="bold", color="white")
    ax.text(10.5, 64, source.get("count_label", ""), ha="center",
            fontsize=10.5, color=LIGHT)
    ax.text(10.5, 50, source.get("held", ""), ha="center", fontsize=11.5,
            fontweight="bold", color="white")
    ax.text(10.5, 40, source.get("drain", ""), ha="center", fontsize=11.5,
            fontweight="bold", color="#F8B195")

    total = sum(d[2] for d in dests) or 1
    ribbon_colors = [ORANGE, STEEL, TINT, LIGHT, GRID]
    usable = 76.0
    y_src = 88.0
    y_dst = 92.0
    gap = 3.2
    widths = []
    x0, x1 = 19, 52
    for i, (name, sub, value) in enumerate(dests):
        wgt = value / total * (usable - gap * (len(dests) - 1))
        widths.append(wgt)
        src_top, src_bot = y_src, y_src - wgt
        dst_top, dst_bot = y_dst, y_dst - wgt
        from matplotlib.path import Path as MplPath
        import matplotlib.patches as mpatches
        mid = (x0 + x1) / 2
        verts = [(x0, src_top), (mid, src_top), (mid, dst_top), (x1, dst_top),
                 (x1, dst_bot), (mid, dst_bot), (mid, src_bot), (x0, src_bot),
                 (x0, src_top)]
        codes = [MplPath.MOVETO, MplPath.CURVE4, MplPath.CURVE4,
                 MplPath.CURVE4, MplPath.LINETO, MplPath.CURVE4,
                 MplPath.CURVE4, MplPath.CURVE4, MplPath.CLOSEPOLY]
        ax.add_patch(mpatches.PathPatch(
            MplPath(verts, codes),
            facecolor=ribbon_colors[i % len(ribbon_colors)],
            edgecolor="none", alpha=0.92))
        ax.text(x1 + 1.5, (dst_top + dst_bot) / 2 + 1.2, name, fontsize=11.5,
                fontweight="bold",
                color=ORANGE if i == 0 else (GREY if i == len(dests) - 1
                                             else NAVY))
        ax.text(x1 + 1.5, (dst_top + dst_bot) / 2 - 2.6, sub, fontsize=9.5,
                color=GREY)
        y_src = src_bot - gap * 0.6
        y_dst = dst_bot - gap
    if footnote:
        ax.text(2, 1, footnote, fontsize=9, color=GREY)
    return fig, {"ribbons": len(dests), "ribbon_widths": widths}


def flow_ribbons(source: dict, dests: list, out: Path,
                 footnote: str = "") -> Path:
    fig, _ = _flow_fig(source, dests, footnote)
    return _save(fig, out)


def _rag_fig(rows: list, story: str | None):
    """RAG status chips in a two-column grid; a glyph on every chip, never
    color alone. rows: [[status, tag, text], ...] with status in
    green/amber/red."""
    for status, _, _ in rows:
        if status not in _RAG:
            raise ValueError(f"unknown RAG status {status!r}")
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, 4.2))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    n_rows = (len(rows) + 1) // 2
    chip_h = min(26.0, (86.0 if story else 96.0) / max(n_rows, 1) - 4)
    glyphs = []
    for i, (status, tag, text) in enumerate(rows):
        spec = _RAG[status]
        glyphs.append(spec["glyph"])
        col, r = i % 2, i // 2
        x = 1 + col * 50.5
        y_top = (96 if not story else 92) - r * (chip_h + 4)
        y = y_top - chip_h
        _block_cut(ax, x, y, 48, chip_h, spec["bg"])
        ax.add_patch(plt.Rectangle((x, y), 1.1, chip_h,
                                   facecolor=spec["color"], edgecolor="none"))
        ax.text(x + 3, y + chip_h - 4.5, f"{spec['glyph']} "
                f"{status.upper()} · {tag}", fontsize=9,
                fontweight="bold", color=spec["color"], va="top")
        ax.text(x + 3, y + 4.5, text, fontsize=10.5, fontweight="bold",
                color=NAVY, va="bottom")
    if story:
        ax.text(1, 1, story, fontsize=10.5, color=GREY, va="bottom")
    return fig, {"chips": len(rows), "glyphs": glyphs}


def rag_chips(rows: list, out: Path, story: str | None = None) -> Path:
    fig, _ = _rag_fig(rows, story)
    return _save(fig, out)


# ---------------------------------------------------------------------------
# ICS chapter renderers (#74 phase 2; approved mockup slides-ics.html).
# ---------------------------------------------------------------------------

def _milestone_fig(grid: dict):
    """The milestone heatmap: opening cohorts x M1..M24 activation, navy
    ramp; immature cells stay blank (measured history, never projected)."""
    cols, rows = grid["cols"], grid["rows"]
    height = min(5.0, max(2.6, 0.62 * len(rows) + 1.2))
    cell_fs = 10 if len(rows) <= 12 else 7.5
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, height))
    ax.set_xlim(0, len(cols) + 1.6)
    ax.set_ylim(0, len(rows) + 1)
    ax.axis("off")
    drawn = blank = 0
    for ci, c in enumerate(cols):
        ax.text(ci + 0.5, len(rows) + 0.45, c, ha="center", fontsize=11,
                fontweight="bold", color=NAVY)
    ax.text(len(cols) + 0.55, len(rows) + 0.45, "n", fontsize=11,
            fontweight="bold", color=NAVY)
    for ri, row in enumerate(rows):
        label, n, cells = row[0], row[1], row[2:]
        y = len(rows) - 1 - ri
        ax.text(-0.12, y + 0.5, str(label), ha="right", va="center",
                fontsize=min(10.5, cell_fs + 1.5), color=GREY)
        ax.text(len(cols) + 0.55, y + 0.5, f"{n:,}", va="center",
                fontsize=10, color=GREY)
        for ci, v in enumerate(cells):
            if v is None:
                ax.add_patch(plt.Rectangle((ci + 0.03, y + 0.06), 0.94, 0.88,
                                           facecolor="#F2F4F7",
                                           edgecolor="white"))
                blank += 1
                continue
            t = max(0.0, min(1.0, (v - 70) / 25))
            color = tuple((a + (b - a) * t) / 255 for a, b in
                          zip((207, 219, 232), (0, 39, 76)))
            ax.add_patch(plt.Rectangle((ci + 0.03, y + 0.06), 0.94, 0.88,
                                       facecolor=color, edgecolor="white"))
            ax.text(ci + 0.5, y + 0.5, f"{v:.0f}%", ha="center", va="center",
                    fontsize=cell_fs, fontweight="bold",
                    color="white" if t > 0.55 else NAVY)
            drawn += 1
    return fig, {"cells_drawn": drawn, "cells_blank": blank}


def milestone_heat(grid: dict, out: Path) -> Path:
    fig, _ = _milestone_fig(grid)
    return _save(fig, out)


def _lift_matrix_fig(grid: dict):
    """The workbook's rate card: baseline segment down the side, swipe band
    across the top, the sheet's own rate in each cell. The ramp is scaled
    to THIS matrix's own range -- a rate card's numbers mean nothing on an
    absolute scale, only relative to the card they sit on."""
    cols, rows = grid["cols"], grid["rows"]
    money = grid.get("money", True)
    vals = [v for row in rows for v in row[1:] if isinstance(v, (int, float))]
    lo, hi = (min(vals), max(vals)) if vals else (0.0, 1.0)
    span = (hi - lo) or 1.0
    height = min(5.0, max(2.6, 0.62 * len(rows) + 1.2))
    cell_fs = 10 if len(rows) <= 8 else 8
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, height))
    ax.set_xlim(-0.05, len(cols) + 0.1)
    ax.set_ylim(0, len(rows) + 1)
    ax.axis("off")
    for ci, c in enumerate(cols):
        ax.text(ci + 0.5, len(rows) + 0.45, str(c), ha="center", fontsize=11,
                fontweight="bold", color=NAVY)
    for ri, row in enumerate(rows):
        label, cells = row[0], row[1:]
        y = len(rows) - 1 - ri
        ax.text(-0.12, y + 0.5, str(label), ha="right", va="center",
                fontsize=min(10.5, cell_fs + 1.5), color=GREY)
        for ci, v in enumerate(cells[:len(cols)]):
            if not isinstance(v, (int, float)):
                ax.add_patch(plt.Rectangle((ci + 0.03, y + 0.06), 0.94, 0.88,
                                           facecolor="#F2F4F7",
                                           edgecolor="white"))
                continue
            t = max(0.0, min(1.0, (v - lo) / span))
            color = tuple((a + (b - a) * t) / 255 for a, b in
                          zip((207, 219, 232), (0, 39, 76)))
            ax.add_patch(plt.Rectangle((ci + 0.03, y + 0.06), 0.94, 0.88,
                                       facecolor=color, edgecolor="white"))
            ax.text(ci + 0.5, y + 0.5,
                    f"${v:,.2f}" if money else f"{v:,.2f}",
                    ha="center", va="center", fontsize=cell_fs,
                    fontweight="bold", color="white" if t > 0.55 else NAVY)
    return fig


def lift_matrix_heat(grid: dict, out: Path) -> Path:
    return _save(_lift_matrix_fig(grid), out)




# ---------------------------------------------------------------- ICS forms
# Ported from the approved mockup (DESIGN/report-mockups/slides-ics-chapter
# .html). The FORMS come from the mockup; the PALETTE stays the deck's, so
# the chapter does not clash with the hundred slides around it.

def _gap_area_fig(xs, a, b, a_lab, b_lab, ylabel="", annotate_first=True):
    """Two cumulative curves with the space between them filled -- the lift
    IS the area, and a bare pair of lines throws that away."""
    fig, ax = plt.subplots(figsize=(FIG_W_RAIL, 4.4))
    ax.fill_between(xs, a, b, where=[x >= y for x, y in zip(a, b)],
                    color=ORANGE, alpha=0.12, interpolate=True, zorder=1)
    ax.plot(xs, b, color=TINT, lw=2.6, marker="o", markersize=6,
            markerfacecolor="white", markeredgewidth=2, markeredgecolor=TINT,
            zorder=2)
    ax.plot(xs, a, color=ORANGE, lw=3.0, marker="o", markersize=6.5,
            markerfacecolor="white", markeredgewidth=2.4,
            markeredgecolor=ORANGE, zorder=3)
    ax.text(xs[-1] + 0.25, a[-1], f"{a_lab} {a[-1]:.0f}%", color=ORANGE,
            fontsize=11, fontweight="bold", va="center")
    ax.text(xs[-1] + 0.25, b[-1], f"{b_lab} {b[-1]:.0f}%", color=GREY,
            fontsize=11, fontweight="bold", va="center")
    if annotate_first and len(xs) > 1:
        x0 = xs[0]
        ax.annotate("", xy=(x0, a[0]), xytext=(x0, b[0]),
                    arrowprops=dict(arrowstyle="<->", color=ORANGE, lw=1.6))
        ax.text(x0 + 0.18, (a[0] + b[0]) / 2, f"+{a[0] - b[0]:.1f}pp",
                color=ORANGE, fontsize=11, fontweight="bold", va="center")
    ax.set_xlim(xs[0] - 0.4, xs[-1] + 2.6)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"M{x}" for x in xs], fontsize=10, color=GREY)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10, color=GREY)
    _clean(ax, left=True)
    return fig, {"points": len(xs)}


def gap_area(xs, a, b, a_lab, b_lab, out: Path, ylabel="",
             annotate_first=True) -> Path:
    fig, _ = _gap_area_fig(xs, a, b, a_lab, b_lab, ylabel, annotate_first)
    return _save(fig, out)


def _waffle_fig(panels: list):
    """Hundred-square proportion, one grid per panel. Proportion without a
    percentage sign, and impossible to misread.
    panels: [(label, pct, base_label), ...]
    """
    fig, axes = plt.subplots(1, len(panels), figsize=(FIG_W_RAIL, FIG_H_RAIL))
    if len(panels) == 1:
        axes = [axes]
    for ax, (label, pct, base), colour in zip(
            axes, panels, [ORANGE, STEEL, TINT]):
        ax.set_xlim(-0.5, 10.5)
        ax.set_ylim(-2.6, 10.9)
        ax.axis("off")
        ax.set_aspect("equal", adjustable="box")   # squares, not rectangles
        filled = int(round(pct))
        for i in range(100):
            r, c = divmod(i, 10)
            ax.add_patch(plt.Rectangle((c, 9 - r), 0.82, 0.82,
                                       facecolor=colour if i < filled else GRID,
                                       edgecolor="none"))
        ax.text(0, 10.5, label.upper(), fontsize=9.5, fontweight="bold",
                color=NAVY)
        ax.text(0, -1.1, f"{pct:.1f}%", fontsize=21, fontweight="bold",
                color=colour, va="top")
        ax.text(3.0, -1.35, base, fontsize=9.5, color=GREY, va="top")
    fig.tight_layout()
    return fig, {"panels": len(panels)}


def waffle(panels: list, out: Path) -> Path:
    fig, _ = _waffle_fig(panels)
    return _save(fig, out)


def _fmt(spec, v) -> str:
    return spec(v) if callable(spec) else spec.format(v)


def _delta_text(spec, d) -> str:
    """A signed change: "+4.0" or "-4.0", never "+-4.0"."""
    if callable(spec):
        return spec(d)
    if spec.startswith("+") and d < 0:
        return "-" + spec[1:].format(abs(d))
    return spec.format(d)


def _dumbbell_fig(rows: list, a_lab: str, b_lab: str, note_idx=None,
                  value_fmt: str = "{:.1f}%", delta_fmt: str = "+{:.1f}",
                  delta_color: str = GREEN, height: float | None = None,
                  own_scale: bool = False):
    """rows: [[label, a_value, b_value, sub], ...] -- a connector per row
    with the subject dot on top. Six measures read at once; six paired bars
    would be twelve bars. `height` lets a one-row comparison draw at a
    height that fits one row instead of floating in a six-row figure.

    A row may carry its own value and change formats as a 5th and 6th item (a str or a callable),
    and `own_scale` puts each row's two dots on a scale of their own: a dollar row and a percent row
    on one shared axis printed "2984.0%" and left the percent rows' dots on top of each other
    (slide 15, 2026-10-27). The change printed beside each row is what carries the size."""
    fig, ax = plt.subplots(figsize=(FIG_W_RAIL, height or FIG_H_RAIL))

    def plotted(a, b):
        if not own_scale:
            return a, b
        if a == b:
            return 0.5, 0.5
        return (0.75, 0.25) if a > b else (0.25, 0.75)

    vals = [v for r in rows for v in plotted(r[1], r[2])]
    lo, hi = min(vals), max(vals)
    pad = 0.12 if own_scale else max(4.0, (hi - lo) * 0.18)
    data_lo, data_hi = lo - pad, hi + pad * 2.4
    gutter = (data_hi - data_lo) * 0.62      # labels live here, marks never do
    ax.set_xlim(data_lo - gutter, data_hi)
    ax.set_ylim(-0.8, len(rows) - 0.2)
    label_x = data_lo - gutter * 0.97
    for i, row in enumerate(rows):
        label, a, b = row[0], row[1], row[2]
        vf = row[4] if len(row) > 4 and row[4] else value_fmt
        df = row[5] if len(row) > 5 and row[5] else delta_fmt
        pa, pb = plotted(a, b)
        y = len(rows) - 1 - i
        ax.plot([pb, pa], [y, y], color=GRID, lw=5, solid_capstyle="round",
                zorder=1)
        ax.scatter([pb], [y], s=110, color=TINT, zorder=2,
                   edgecolors="white", linewidths=1.6)
        ax.scatter([pa], [y], s=150, color=ORANGE, zorder=3,
                   edgecolors="white", linewidths=1.8)
        ax.text(max(pa, pb) + pad * 0.24, y, _fmt(vf, a), fontsize=11,
                fontweight="bold", color=NAVY, va="center")
        # the delta is its own right-aligned column: floating it off the
        # value ran the two together on the widest rows
        ax.text(data_hi, y, _delta_text(df, a - b), fontsize=10,
                fontweight="bold", color=delta_color, va="center", ha="right")
        ax.text(label_x, y + 0.16, label, fontsize=11, color=NAVY,
                va="center", ha="left", fontweight="bold")
        if len(row) > 3 and row[3]:
            ax.text(label_x, y - 0.22, row[3], fontsize=8.5,
                    color=GREY, va="center", ha="left")
    ax.scatter([], [], s=150, color=ORANGE, label=a_lab)
    ax.scatter([], [], s=110, color=TINT, label=b_lab)
    ax.legend(loc="lower right", frameon=False, fontsize=10, ncol=2)
    ax.set_yticks([])
    ax.set_xticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    fig.tight_layout()
    return fig, {"rows": len(rows)}


def dumbbell(rows: list, a_lab: str, b_lab: str, out: Path,
             value_fmt: str = "{:.1f}%", delta_fmt: str = "+{:.1f}",
             delta_color: str = GREEN, height: float | None = None,
             own_scale: bool = False) -> Path:
    """Two measures per row on one connector. The unit is the caller's: this
    printed a percent sign on whatever it was handed, so the ILS deck showed
    2,768 presented items as "2768.0%"."""
    fig, _ = _dumbbell_fig(rows, a_lab, b_lab, value_fmt=value_fmt,
                           delta_fmt=delta_fmt, delta_color=delta_color,
                           height=height, own_scale=own_scale)
    return _save(fig, out)


def _paired_hbars_fig(rows: list, a_lab: str, b_lab: str, unit="%"):
    """rows: [[label, a_val, a_n, b_val, b_n], ...] -- two bars per row with
    the base under each. A value declines (None) rather than plotting."""
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, FIG_H_FULL))
    vals = [v for r in rows for v in (r[1], r[3]) if v is not None]
    hi = max(vals) if vals else 1.0
    ax.set_xlim(0, hi * 1.42)
    ax.set_ylim(-0.6, len(rows))
    for i, (label, av, an, bv, bn) in enumerate(rows):
        y = len(rows) - 1 - i
        for j, (v, n, colour) in enumerate(((av, an, ORANGE), (bv, bn, TINT))):
            yy = y + (0.20 if j == 0 else -0.06)
            if v is None:
                ax.text(0.01 * hi, yy + 0.02,
                        f"declined -- {n:,} accounts have lived this long",
                        fontsize=9.5, color=GREY, va="center")
                continue
            ax.add_patch(plt.Rectangle((0, yy - 0.10), v, 0.22,
                                       facecolor=colour, edgecolor="none"))
            ax.text(v + hi * 0.02, yy, f"{v:.1f}{unit}", fontsize=10.5,
                    fontweight="bold", color=NAVY, va="center")
            ax.text(v + hi * 0.13, yy, f"n={n:,}", fontsize=9, color=GREY,
                    va="center")
        ax.text(0, y + 0.52, label, fontsize=11.5, fontweight="bold",
                color=NAVY, va="center")
    ax.add_patch(plt.Rectangle((0, 0), 0, 0, facecolor=ORANGE, label=a_lab))
    ax.add_patch(plt.Rectangle((0, 0), 0, 0, facecolor=TINT, label=b_lab))
    ax.legend(loc="lower right", frameon=False, fontsize=10, ncol=2)
    ax.set_yticks([]); ax.set_xticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    fig.tight_layout()
    return fig, {"rows": len(rows)}


def paired_hbars(rows: list, a_lab: str, b_lab: str, out: Path,
                 unit="%") -> Path:
    fig, _ = _paired_hbars_fig(rows, a_lab, b_lab, unit)
    return _save(fig, out)


MAX_MONTH_TICKS = 12      # a month axis names at most this many months (Sheila, 1798, 2026-10-30)


def _tick_step(n: int, most: int = MAX_MONTH_TICKS) -> int:
    """Every Nth label so that at most `most` are drawn: 33 months -> every 3rd (11 labels)."""
    return max(1, -(-n // most))


def _highlight_index(rows, highlight):
    """The row indexes `highlight` names: a row label (as given or in MMM'YY), an index, or a list of either."""
    if highlight is None:
        return set()
    wanted = highlight if isinstance(highlight, (list, tuple, set)) else [highlight]
    labels = [str(r[0]) for r in rows]
    house = _axis_labels(labels)
    out = set()
    for w in wanted:
        if isinstance(w, int) and not isinstance(w, bool):
            if -len(rows) <= w < len(rows):
                out.add(w % len(rows))
            continue
        for i, (raw, hm) in enumerate(zip(labels, house)):
            if str(w) in (raw, hm) or _rpe_periods.mon_yy(str(w)) == hm:
                out.add(i)
    return out


def _line_with_base_fig(rows: list, ylabel="", highlight=None):
    """rows: [[label, base_n, pct], ...] -- the rate as a line, the base it
    rests on as grey columns behind it. The base is the honest part.

    `highlight` (a row label, an index, or a list of them) marks one cohort: a filled orange
    point, its base column in the accent tint, its value always printed and its tick label kept
    and set bold. With many months only every Nth tick is labelled, at most MAX_MONTH_TICKS (33
    months ran together on 1798's slide 34, 2026-10-30)."""
    xs = list(range(len(rows)))
    pcts = [r[2] for r in rows]
    bases = [r[1] for r in rows]
    fig, ax = plt.subplots(figsize=(FIG_W_RAIL, 4.3))
    lo, hi = min(pcts), max(pcts)
    span = max(hi - lo, 4.0)
    ax.set_ylim(lo - span * 1.35, hi + span * 0.35)
    mx = max(bases) or 1
    floor = lo - span * 1.35
    marked = _highlight_index(rows, highlight)
    for x, b in zip(xs, bases):
        ax.add_patch(plt.Rectangle((x - 0.34, floor), 0.68,
                                   (b / mx) * span * 0.62,
                                   facecolor=TINT if x in marked else GRID, edgecolor="none", zorder=1))
    ax.plot(xs, pcts, color=ORANGE, lw=3, marker="o", markersize=6.5,
            markerfacecolor="white", markeredgewidth=2.4,
            markeredgecolor=ORANGE, zorder=3)
    for i in sorted(marked):
        ax.plot([xs[i]], [pcts[i]], marker="o", markersize=11, color=ORANGE,
                markeredgecolor=NAVY, markeredgewidth=2, zorder=4)
    for i in sorted({0, len(xs) // 2, len(xs) - 1} | marked):
        t = ax.text(xs[i], pcts[i] + span * 0.10, f"{pcts[i]:.0f}%", fontsize=13 if i in marked else 10.5,
                    fontweight="bold", color=ORANGE if i in marked else NAVY, ha="center")
        if i in marked:
            t._ars_keep = True        # the highlighted value is never decluttered away
    step = _tick_step(len(xs))
    shown = sorted(set(range(len(xs) - 1, -1, -step)) | marked)    # anchored on the latest month
    labels = _axis_labels([r[0] for r in rows])
    ax.set_xticks([xs[i] for i in shown])
    ticks = ax.set_xticklabels([labels[i] for i in shown], fontsize=9, color=GREY)
    for i, t in zip(shown, ticks):
        if i in marked:
            t.set_color(ORANGE)
            t.set_fontweight("bold")
    ax.text(xs[-1], floor + span * 0.66, "grey = accounts observed",
            fontsize=9, color=GREY, ha="right")
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10, color=GREY)
    _clean(ax, left=True)
    return fig, {"points": len(rows)}


def line_with_base(rows: list, out: Path, ylabel="", highlight=None) -> Path:
    fig, _ = _line_with_base_fig(rows, ylabel, highlight)
    return _save(fig, out)


def _split_panels_fig(panels: list, baseline=None, baseline_label=""):
    """One big number per panel with a share bar and two supporting stats.
    panels: [(title, sub, pct, [(value, label), ...]), ...]"""
    fig, axes = plt.subplots(1, len(panels), figsize=(FIG_W_RAIL, FIG_H_RAIL))
    if len(panels) == 1:
        axes = [axes]
    for ax, (title, sub, pct, stats), colour in zip(
            axes, panels, [ORANGE, STEEL, TINT]):
        ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")
        ax.add_patch(plt.Rectangle((0, 96), 100, 2.2, facecolor=colour,
                                   edgecolor="none"))
        ax.text(0, 86, title, fontsize=15, fontweight="bold", color=NAVY)
        ax.text(0, 78, sub, fontsize=10, color=GREY)
        ax.text(0, 56, f"{pct:.1f}%", fontsize=32, fontweight="bold",
                color=colour)
        ax.add_patch(plt.Rectangle((0, 44), 100, 6, facecolor=GRID,
                                   edgecolor="none"))
        ax.add_patch(plt.Rectangle((0, 44), pct, 6, facecolor=colour,
                                   edgecolor="none"))
        if baseline is not None:
            ax.plot([baseline, baseline], [41, 53], color=NAVY, lw=2)
            ax.text(baseline + 1.5, 34, baseline_label, fontsize=8.5,
                    fontweight="bold", color=NAVY)
        for k, (val, lab) in enumerate(stats):
            ax.text(0, 22 - k * 13, val, fontsize=15, fontweight="bold",
                    color=NAVY)
            ax.text(26, 22 - k * 13, lab, fontsize=10, color=GREY)
    fig.tight_layout()
    return fig, {"panels": len(panels)}


def split_panels(panels: list, out: Path, baseline=None,
                 baseline_label="") -> Path:
    fig, _ = _split_panels_fig(panels, baseline, baseline_label)
    return _save(fig, out)


def _pair_lines_fig(xs: list, a: list, b: list, a_label: str, b_label: str,
                    ylabel: str = "", pct: bool = False,
                    xlabel: str = "months since open"):
    """The chapter's two-cohort comparison line: ICS solid orange,
    control dashed tint; endpoint labels, one axis."""
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, 4.0))
    pa = [(x, v) for x, v in zip(xs, a) if v is not None]
    pb = [(x, v) for x, v in zip(xs, b) if v is not None]
    for pts, color, lw, style, label in (
            (pa, ORANGE, 3.0, "-", a_label),
            (pb, TINT, 2.2, (0, (6, 4)), b_label)):
        if len(pts) < 2:
            continue
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=color,
                linewidth=lw, linestyle=style)
        v = pts[-1][1]
        end = f"{label} {v:.0f}%" if pct else f"{label} {v:,.0f}"
        ax.annotate(end, xy=pts[-1], xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=11,
                    fontweight="bold", color=color if color != TINT else GREY)
    ax.set_xlabel(xlabel, fontsize=10.5, color=GREY)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10.5, color=GREY)
    ax.margins(x=0.12)
    _clean(ax, left=True)
    return fig, {"series": 2}


def pair_lines(xs: list, a: list, b: list, a_label: str, b_label: str,
               out: Path, ylabel: str = "", pct: bool = False,
               xlabel: str = "months since open") -> Path:
    fig, _ = _pair_lines_fig(xs, a, b, a_label, b_label, ylabel=ylabel,
                             pct=pct, xlabel=xlabel)
    return _save(fig, out)


def _quadrant_fig(rows: list, xlabel: str, ylabel: str, quads=None,
                  bubble_label="bubble = ICS accounts opened there", xfmt=None, yfmt=None,
                  size_idx: int = 1):
    """Branch quadrant: x/y per branch, bubble = volume, dashed medians.
    rows: [[name, n, x, y, ...], ...] (None-valued rows dropped).

    `size_idx` picks the field the bubble is sized by (default 1, the volume); a row may carry
    more fields after y, e.g. 90-day net adds at index 4 with size_idx=4. A negative value is
    sized by its magnitude and drawn in orange, so a shrinking branch reads as one (2026-10-30)."""
    rows = [r for r in rows if r[2] is not None and r[3] is not None]
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, 4.6))
    xs = [r[2] for r in rows]
    ys = [r[3] for r in rows]

    def mag(r):
        v = r[size_idx] if len(r) > size_idx else None
        return abs(float(v)) if v is not None else 0.0

    max_n = max((mag(r) for r in rows), default=1) or 1
    sizes = [300 + 1900 * mag(r) / max_n for r in rows]
    colors = [ORANGE if (len(r) > size_idx and r[size_idx] is not None and float(r[size_idx]) < 0)
              else NAVY for r in rows]
    ax.scatter(xs, ys, s=sizes, color=colors, alpha=0.8, zorder=3,
               edgecolor="white", linewidth=2)
    medians = False
    mx = my = None
    if len(rows) >= 2:
        sx, sy = sorted(xs), sorted(ys)
        mx, my = sx[len(sx) // 2], sy[len(sy) // 2]
        ax.axvline(mx, ls="--", color=TINT, lw=1.2)
        ax.axhline(my, ls="--", color=TINT, lw=1.2)
        medians = True
    ax.set_xlabel(xlabel, fontsize=11, color=NAVY)
    ax.set_ylabel(ylabel, fontsize=11, color=NAVY)
    ax.margins(0.18)
    _clean(ax, left=True)
    # An axis prints its own unit: a money axis in the deck's grammar ($2.5M), any other plain --
    # never a "1e7" offset over "Spend outside the client" (2026-10-28).
    ax.ticklabel_format(axis="both", style="plain", useOffset=False)
    if xfmt is not None:
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: xfmt(v)))
    if yfmt is not None:
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: yfmt(v)))
    ax.text(0.99, 0.02, bubble_label, transform=ax.transAxes, ha="right",
            fontsize=10, color=GREY, style="italic")
    if rows:
        fig.tight_layout()          # the axes' final size, so the names are placed on the real picture
        place_point_labels(ax, list(zip(xs, ys)), sizes, [r[0] for r in rows])
    if quads and mx is not None:
        # the legacy threat quadrant (13_threat_quadrant, 32_material_threats):
        # naming the corners is what turns a scatter into a priority call
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        tl, tr, bl, br = quads
        ax.add_patch(plt.Rectangle((mx, my), x1 - mx, y1 - my,
                                   facecolor="#FFF3E2", zorder=0))
        for text, xx, yy, ha, va, col in (
                (tl, x0, y1, "left", "top", "#C3CCD6"),
                (tr, x1, y1, "right", "top", ORANGE),
                (bl, x0, y0, "left", "bottom", "#C3CCD6"),
                (br, x1, y0, "right", "bottom", "#C3CCD6")):
            ax.text(xx, yy, text.upper(), ha=ha, va=va, fontsize=9.5,
                    fontweight="bold", color=col, zorder=1)
    return fig, {"points": len(rows), "medians_drawn": medians,
                 "quadrants_named": bool(quads and mx is not None)}


def branch_quadrant(rows: list, out: Path, quads=None,
                    bubble_label="bubble = ICS accounts opened there",
                    xlabel: str = "month-one activation %",
                    ylabel: str = "12-mo retention %", xfmt=None, yfmt=None,
                    size_idx: int = 1) -> Path:
    fig, _ = _quadrant_fig(rows, xlabel, ylabel, quads, bubble_label, xfmt=xfmt, yfmt=yfmt,
                           size_idx=size_idx)
    return _save(fig, out)


def _seg_resp_fig(detail: dict):
    """The legacy per-mailer grid (28_segment_combo_lines): 2 rows
    (spend / swipes) x one column per challenge segment; each panel is
    that segment's responders (orange, solid) vs its own non-responders
    (grey, dashed). Mail month at offset 0."""
    offsets = detail["offsets"]
    segs = detail["segments"]
    n = max(len(segs), 1)
    fig, axes = plt.subplots(2, n, figsize=(FIG_W_FULL, 4.6), sharex=True,
                             squeeze=False)
    for ci, seg in enumerate(segs):
        d = detail["data"][seg]
        for ri, key in ((0, "spend"), (1, "swipes")):
            ax = axes[ri][ci]
            ax.plot(offsets, d[key]["Responders"], color=ORANGE, lw=2.2)
            ax.plot(offsets, d[key]["Non-responders"], color=GREY, lw=1.6,
                    linestyle=(0, (5, 4)))
            ax.axvline(0, color=ORANGE, lw=1.0, ls=(0, (2, 3)), alpha=0.7)
            _clean(ax)
            ax.tick_params(labelsize=7.5)
            if ci == 0:
                ax.set_ylabel("$ / acct" if ri == 0 else "swipes / acct",
                              fontsize=9, color=GREY)
        axes[0][ci].set_title(
            f"{seg}\n{d['counts']['Responders']:,} vs "
            f"{d['counts']['Non-responders']:,}",
            fontsize=9.5, fontweight="bold", color=NAVY)
    # Lay the panels out FIRST, keeping the bottom strip clear, then write
    # the caption into that strip. Doing it the other way round let
    # tight_layout reclaim the margin and drop the panels onto the caption.
    fig.tight_layout(pad=0.5, rect=(0, 0.075, 1, 1))
    fig.subplots_adjust(hspace=0.15, wspace=0.3)
    fig.text(0.5, 0.022, "months relative to the mail month · orange = "
             "responders, dashed grey = the segment's own non-responders",
             ha="center", va="center", fontsize=9, color=GREY)
    fig._ars_layout_authored = True
    return fig, {"panels": 2 * len(segs), "segments": list(segs)}


def segment_resp_grid(detail: dict, out: Path) -> Path:
    fig, _ = _seg_resp_fig(detail)
    return _save(fig, out)


# ---- the per-mailer summary panel (issue #80, James's legacy slide 1) ----
# Donut of response share, per-tier response rate bars, and the fixed five
# "Inside the Numbers" stats. The three blocks are placed with add_axes on a
# single shared band so they line up -- James called out the misalignment
# when the blocks were laid out independently.
# The three data blocks share one band; the ladder key and the coverage note
# hang below the donut column, which is the layout James approved on the
# mockup. Keeping the key out of the axes leaves the band alignment intact.
_SUMMARY_Y0, _SUMMARY_Y1 = 0.17, 0.79


def _tier_ramp(tiers: list[str]) -> dict[str, str]:
    """The fill ramp IS the ladder: light at the bottom rung, orange at the
    top, so colour carries the challenge level rather than decorating."""
    ramp = [LIGHT, TINT, STEEL, NAVY, ORANGE]
    if len(tiers) <= len(ramp):
        step = ramp[len(ramp) - len(tiers):]
    else:
        step = [ramp[min(i * len(ramp) // len(tiers), len(ramp) - 1)]
                for i in range(len(tiers))]
    return dict(zip(tiers, step))


def _readable_on(fill) -> str:
    """White on a dark fill, navy on a light one.

    The share label sits ON its wedge, so its colour has to come from what
    is behind it -- a fixed navy label vanished entirely on the navy tier.
    """
    red, green, blue = mcolors.to_rgb(fill)
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return "#FFFFFF" if luminance < 0.6 else NAVY


def _ladder_key(fig, tiers, colours, left, bottom, width):
    """Swatch per tier under the donut, weakest to strongest."""
    fig.text(left, bottom + 0.105, "THE LADDER, LOW TO HIGH", fontsize=7.5,
             fontweight="bold", color=GREY)
    slot = width / len(tiers)
    for i, tier in enumerate(tiers):
        x = left + i * slot
        fig.patches.append(plt.Rectangle(
            (x, bottom + 0.045), slot * 0.86, 0.038, transform=fig.transFigure,
            facecolor=colours[tier], edgecolor="none", figure=fig))
        fig.text(x + slot * 0.43, bottom, tier, fontsize=6.8, color=NAVY,
                 ha="center")


def _mailer_summary_fig(summary: dict):
    tiers = list(summary["tiers"])
    by_tier = summary["by_tier"]
    inside = summary["inside"]
    colours = _tier_ramp(tiers)

    fig_w, fig_h = FIG_W_FULL, 4.75
    fig = plt.figure(figsize=(fig_w, fig_h))
    height = _SUMMARY_Y1 - _SUMMARY_Y0
    # A pie forces aspect="equal", which shrinks a non-square axes and drops
    # the donut off the shared band. Authoring its box square in FIGURE
    # inches makes the aspect a no-op, so all three blocks keep the band.
    donut_w = height * fig_h / fig_w
    col_donut, col_bars, col_stats = 0.045, 0.35, 0.65
    ax_donut = fig.add_axes([col_donut, _SUMMARY_Y0, donut_w, height])
    ax_bars = fig.add_axes([col_bars, _SUMMARY_Y0, 0.25, height])
    ax_stats = fig.add_axes([col_stats, _SUMMARY_Y0, 0.33, height])

    # ---- the headline trio ------------------------------------------------
    for x, value, label in ((0.045, f"{summary['mailed']:,}", "mailed"),
                            (0.175, f"{summary['responded']:,}", "responded"),
                            (0.295, f"{summary['rate']:.1f}%", "response rate")):
        fig.text(x, 0.925, value, fontsize=18, fontweight="bold", color=NAVY)
        fig.text(x, 0.878, label, fontsize=8.5, color=GREY)

    # the rule the HTML carries: it separates the trio from the three columns
    fig.add_artist(plt.Line2D([0.045, 0.98], [0.855, 0.855], color=NAVY,
                              lw=1.1, transform=fig.transFigure))

    # one baseline for all three headers -- authored here rather than as axes
    # titles, whose offset follows each axes and drifts them apart
    for x, header in ((col_donut, "RESPONSE SHARE"),
                      (col_bars, "RESPONSE RATE BY TIER"),
                      (col_stats, "INSIDE THE NUMBERS")):
        fig.text(x, 0.815, header, fontsize=8, fontweight="bold", color=GREY)

    # ---- response share ---------------------------------------------------
    shares = [by_tier[t]["responded"] for t in tiers]
    wedges, _labels, autotexts = ax_donut.pie(
        shares, colors=[colours[t] for t in tiers],
        startangle=90, counterclock=False,
        wedgeprops={"width": 0.44, "edgecolor": "white", "linewidth": 1.2},
        autopct=lambda p: f"{p:.0f}%" if p >= 6 else "",
        pctdistance=0.78,
        textprops={"fontsize": 8.5, "fontweight": "bold"})
    for wedge, autotext in zip(wedges, autotexts):
        autotext.set_color(_readable_on(wedge.get_facecolor()))
    ax_donut.text(0, 0.06, f"{summary['responded']:,}", ha="center",
                  fontsize=14, fontweight="bold", color=NAVY)
    ax_donut.text(0, -0.16, "responders", ha="center", fontsize=8, color=GREY)
    ax_donut.set_aspect("equal")

    _ladder_key(fig, tiers, colours, 0.045, 0.055, donut_w)

    # the part of the wave that carries no tier is stated, never absorbed
    unplaced = summary.get("mailed_unassigned", 0)
    if unplaced:
        fig.text(0.045, 0.015,
                 f"{unplaced:,} of {summary['mailed']:,} mailed carry no "
                 f"challenge tier and are counted in none of the tier rows",
                 fontsize=7, color=GREY)

    # ---- response rate by tier -------------------------------------------
    ypos = np.arange(len(tiers))[::-1]
    rates = [by_tier[t]["rate"] for t in tiers]
    span = max(rates) if max(rates) else 1.0
    ax_bars.barh(ypos, rates, height=0.5, color=[colours[t] for t in tiers])
    for y, tier, rate in zip(ypos, tiers, rates):
        d = by_tier[tier]
        ax_bars.text(rate + span * 0.04, y, f"{d['responded']:,}/{d['mailed']:,}",
                     va="center", fontsize=7.5, color=GREY)
        # the rate reads down a clean right-hand column, as on the mockup
        ax_bars.text(span * 1.72, y, f"{rate:.1f}%", ha="right", va="center",
                     fontsize=9, fontweight="bold", color=NAVY)
    ax_bars.set_yticks(ypos)
    ax_bars.set_yticklabels(tiers, fontsize=8.5, fontweight="bold", color=NAVY)
    ax_bars.set_xlim(0, span * 1.75)
    ax_bars.set_xticks([])
    for side in ("top", "right", "bottom", "left"):
        ax_bars.spines[side].set_visible(False)
    ax_bars.tick_params(length=0)

    # ---- inside the numbers ----------------------------------------------
    rows = [
        (inside.get("new_account_pct"), "of responders opened in the last 2 years"),
        (inside.get("age_60_plus_pct"), "of responders are aged 60 or over"),
        (inside.get("rege_optin_pct"), "of responders opted in to Reg E"),
        (inside.get("first_time_pct"), "were responding for the first time"),
        (inside.get("moved_up_pct"), "of repeat responders moved up a tier"),
    ]
    ax_stats.set_xlim(0, 1)
    ax_stats.set_ylim(0, 1)
    ax_stats.axis("off")
    for i, (value, label) in enumerate(rows):
        y = 0.92 - i * 0.215
        is_ladder = i == len(rows) - 1
        if value is None:
            ax_stats.text(0.0, y, "n/a", fontsize=11, fontweight="bold",
                          color=GREY, va="center")
            missing = "repeat responders" if is_ladder else "data"
            ax_stats.text(0.18, y, f"{label} (no {missing} yet)",
                          fontsize=8, color=GREY, va="center")
            continue
        ax_stats.text(0.0, y, f"{value:.0f}%", fontsize=13, fontweight="bold",
                      color=ORANGE if is_ladder else NAVY, va="center")
        ax_stats.text(0.18, y, label, fontsize=8.5, color=NAVY, va="center")

    return fig, {"donut": ax_donut, "bars": ax_bars, "stats": ax_stats}


def mailer_summary_panel(summary: dict, out: Path) -> Path:
    fig, _ = _mailer_summary_fig(summary)
    return _save(fig, out)


# ---- wave revenue: the All Months Rollup matrix (issue #85) ----------
_MON = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _month_label(iso: str) -> str:
    """RPE house format, MMM'YY (periods.mon_yy); v5 drew 'Sep 25'."""
    import periods
    return periods.mon_yy(f"{_MON[int(iso[5:7]) - 1]} {iso[:4]}")


def _wave_bands(rows):
    """``[[wave, month, revenue]]`` -> ``(months, {wave: [v per month]})``,
    waves oldest-first so the stack builds the way the program did.

    Every offer keeps its own band. An earlier cut folded the oldest into
    one to stay inside a five-colour categorical palette, which hid offers
    that are still paying -- see ``_seq_ramp`` for what replaced it.
    """
    tags, months = [], []
    for tag, month, _v in rows:
        if tag not in tags:
            tags.append(tag)
        if month not in months:
            months.append(month)
    months.sort()
    at = {m: i for i, m in enumerate(months)}
    series = {t: [0.0] * len(months) for t in tags}
    for tag, month, value in rows:
        series[tag][at[month]] += value
    return months, series


def _composition_fig(rows):
    months, series = _wave_bands(rows)
    fig, ax = plt.subplots(figsize=(FIG_W_FULL, 5.4))
    bottom = [0.0] * len(months)
    for (band, vals), color in zip(series.items(), _seq_ramp(len(series))):
        ax.bar(range(len(months)), vals, bottom=bottom, width=0.72,
               color=color, edgecolor="white", linewidth=1.1, label=band,
               zorder=3)
        bottom = [b + v for b, v in zip(bottom, vals)]
    top = max(bottom) if bottom else 0
    for x, total in enumerate(bottom):
        ax.text(x, total + top * 0.018, f"${total/1000:,.0f}k", ha="center",
                fontsize=9.5, fontweight="bold", color=NAVY, zorder=4)
    ax.set_ylim(0, top * 1.12 or 1)
    ax.set_xticks(range(len(months)))
    ax.set_xticklabels([_month_label(m) for m in months], rotation=45,
                       ha="right", fontsize=10.5, color=NAVY)
    ax.set_ylabel("booked revenue", fontsize=12.5, color=NAVY)
    ax.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda v, _: f"${v/1000:,.0f}k"))
    ax.legend(fontsize=10.5, frameon=False, ncol=min(len(series), 8),
              loc="lower center", bbox_to_anchor=(0.5, 1.01),
              title="revenue by the offer that earned it — oldest pale, "
                    "newest dark", title_fontsize=10.5)
    ax.yaxis.grid(True, color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)
    _clean(ax, left=True)
    return fig, series


def wave_composition(rows: list, out: Path) -> Path:
    """Each month's booked revenue, split by the offer that earned it."""
    fig, _ = _composition_fig(rows)
    return _save(fig, out)


def _seq_ramp(n: int) -> list:
    """A sequential light-to-navy ramp, n steps.

    Both axes of this table are ORDERED -- months run forward, and so do
    the offers that mailed. Ordered things take a ramp, not n categorical
    hues: the reader is meant to see the early ones as the pale mass at
    the base and the recent ones as the dark bands on top, not to identify
    the seventh by its colour. Fifteen categorical colours would be
    fifteen colours nobody can name, and folding the overflow away hid
    offers that were still earning.
    """
    ramp = mcolors.LinearSegmentedColormap.from_list(
        "csi_months", [LIGHT, TINT, STEEL, NAVY])
    return [ramp(i / max(n - 1, 1)) for i in range(n)]


def _totals_fig(rows):
    """One column per offer, stacked by the months that built it.

    Chronological, not ranked by size, so the column order matches the
    P&L table beside it -- and because ranking would quietly imply the
    oldest offer is the best when it has simply had the most months. The
    age rides under each label for the same reason.
    """
    by_wave: dict = {}
    months: list = []
    for tag, month, value in rows:
        by_wave.setdefault(tag, {})[month] = value
        if month not in months:
            months.append(month)
    months.sort()
    bars = [[tag, sum(s.values()), len(s)] for tag, s in by_wave.items()]
    tags = list(by_wave)

    fig, ax = plt.subplots(figsize=(FIG_W_FULL, 5.2))
    bottom = [0.0] * len(tags)
    for month, color in zip(months, _seq_ramp(len(months))):
        values = [by_wave[t].get(month, 0.0) for t in tags]
        ax.bar(range(len(tags)), values, bottom=bottom, width=0.66,
               color=color, edgecolor="white", linewidth=0.7, zorder=3)
        bottom = [b + v for b, v in zip(bottom, values)]
    top = max(bottom) if bottom else 0
    for i, total in enumerate(bottom):
        ax.text(i, total + top * 0.022, f"${total/1000:,.0f}k", ha="center",
                fontsize=12, fontweight="bold", color=NAVY, zorder=4)
    ax.set_ylim(0, top * 1.13 or 1)
    ax.set_xticks(range(len(tags)))
    ax.set_xticklabels([f"{b[0]}\n{b[2]} mo" for b in bars], fontsize=11.5,
                       color=NAVY)
    for label in ax.get_xticklabels():
        label.set_linespacing(1.6)
    ax.set_ylabel("booked revenue to date", fontsize=12.5, color=NAVY)
    ax.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda v, _: f"${v/1000:,.0f}k"))
    if months:
        ax.set_xlabel(f"each offer stacked by the month it earned in — "
                      f"{_month_label(months[0])} pale at the base to "
                      f"{_month_label(months[-1])} dark on top",
                      fontsize=11.5, color=GREY)
    ax.yaxis.grid(True, color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)
    _clean(ax, left=True)
    return fig, bars


def wave_totals(rows: list, out: Path) -> Path:
    """What each offer has booked to date, and the months that built it."""
    fig, _ = _totals_fig(rows)
    return _save(fig, out)
