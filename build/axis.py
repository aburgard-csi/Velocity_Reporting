#!/usr/bin/env python3
"""
axis.py — the month axis, drawn the same way by all three programs.

`periods.axis_label` decides what a tick SAYS. This decides which ticks appear
and at what angle, because that was the second half of the same problem: seven
renderers each picked their own thinning step and rotation, so two charts on
facing slides showed the same 36-month series at different densities.

The rules are derived from the tick count, never typed per chart:

  * up to 8 ticks   — horizontal
  * 9 to 14 ticks   — horizontal if the widest label fits its track; else 30
                      degrees if that clears the collision, else 45
  * a thinned axis  — 45 degrees, the angle STYLE.md already gives the 36-month
                      combo charts

One knob decides both: `max_ticks`, the most ticks an axis may carry. Above it
the series is thinned and reads at 45; at or below it every point is labelled and
the angle is measured. A chart with less room says so by passing a lower cap —
the before/after panels are half-width and cap at 8, which is the tuning Aaron
made after Sugar River's fifteen mailings rendered as overlapping mush
(2026-08-28). An earlier draft kept the cap and the thinning threshold as two
separate numbers, and the cap was then inert for any series short enough to sit
under the threshold: exactly the fifteen-mailing case it existed for.

and the newest point always carries a tick. That last one is not cosmetic: the
endpoint is the headline number on the growth and reach charts, and it used to be
labelled only when the thinning step happened to land on it. `c_openings` already
special-cased it; every series gets it here.

Fit is measured against the bundled TTFs through `textfit`, at the size the tick
will actually render. Box geometry is not glyph geometry (CLAUDE.md rule 2).

    from axis import month_ticks
    month_ticks(ax, x, M["axis_months"]["nsf_series"], pt=9)
"""
from __future__ import annotations

import math

import textfit
from periods import axis_labels

DEFAULT_FAMILY = "Carlito"      # every chart in the pipeline renders Calibri-metric
MAX_TICKS = 14                  # the most ticks an axis carries before thinning
_GAP_IN = 0.06                  # whitespace between neighbouring HORIZONTAL ticks
_LINE_GAP_IN = 0.02             # whitespace between neighbouring ROTATED ticks


def axes_width_in(ax):
    """Width of the axes in inches, without needing a draw."""
    try:
        fig = ax.get_figure()
        return fig.get_size_inches()[0] * ax.get_position().width
    except Exception:
        return None


def tick_indices(n, max_ticks=MAX_TICKS):
    """Which of `n` positions carry a label. The last one always does."""
    if n <= 0:
        return []
    step = 1 if n <= max_ticks else math.ceil(n / max_ticks)
    idx = list(range(0, n, step))
    last = n - 1
    if idx[-1] != last:
        # Appending the endpoint blindly puts it a hair from its neighbour and the
        # two labels collide. Inside half a step it REPLACES that neighbour.
        if last - idx[-1] <= step / 2:
            idx[-1] = last
        else:
            idx.append(last)
    return idx


def rotation_for(shown, width_in, pt, family=DEFAULT_FAMILY, thinned=False):
    """0, 30 or 45 degrees, decided by measuring the collision each one leaves.

    Horizontal and rotated labels collide in different directions, so they are
    two different measurements. Flat, a label collides when it is WIDER than its
    track. Rotated, the labels are parallel lines and width stops mattering: they
    collide when the PERPENDICULAR distance between neighbours, track * sin(a),
    is less than the height of the type. Testing width and then falling through
    to 30 degrees as a catch-all is what put the ICS per-account grid's 16pt
    labels on top of each other at 30 degrees, where they need 45.
    """
    if thinned:
        return 45
    if len(shown) <= 8 or not width_in or not shown:
        return 0 if len(shown) <= 8 else 30
    track = width_in / len(shown)
    widest = max(textfit.text_width_in(t, pt, family) for t in shown)
    if widest + _GAP_IN <= track:
        return 0
    line_h = pt / 72.0
    if track * math.sin(math.radians(30)) >= line_h + _LINE_GAP_IN:
        return 30
    return 45


def month_ticks(ax, x, months, *, field="months", pt=9, family=DEFAULT_FAMILY,
                color=None, max_ticks=MAX_TICKS):
    """Label `ax`'s x axis with the standard month token.

    `months` may be in any form the pipeline carries — ODD tokens, "%b %Y",
    "%b %y", or a VIP dashboard's export. One it cannot read raises, naming
    `field`. Returns the full label series, so a caller that also needs the
    newest month by name (a partial-month legend, say) reuses it rather than
    formatting a second time.
    """
    labels = axis_labels(months, field=field)
    idx = tick_indices(len(labels), max_ticks)
    shown = [labels[i] for i in idx]
    rot = rotation_for(shown, axes_width_in(ax), pt, family,
                       thinned=len(labels) > max_ticks)
    kw = {"fontsize": pt, "rotation": rot}
    if rot:
        kw["ha"] = "right"
    if color:
        kw["color"] = color
    ax.set_xticks([x[i] for i in idx])
    ax.set_xticklabels(shown, **kw)
    return labels
