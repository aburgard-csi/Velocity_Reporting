#!/usr/bin/env python3
"""
axis.py — the month axis, drawn the same way by all three programs.

`periods.axis_label` decides what a tick SAYS. This decides which ticks appear
and at what angle, because that was the second half of the same problem: seven
renderers each picked their own thinning step and rotation, so two charts on
facing slides showed the same 36-month series at different densities.

The rules are derived from the tick count, never typed per chart:

  * up to 8 ticks        — horizontal
  * 9 to 14 ticks        — horizontal if they MEASURE as fitting, else 30 degrees
  * more than 14 points  — thinned to about 12 ticks, at 45 degrees

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
MAX_TICKS = 12                  # target for a thinned series
DENSE_AT = 14                   # above this many points the series is thinned
_GAP_IN = 0.06                  # whitespace demanded between neighbouring ticks


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
    step = 1 if n <= DENSE_AT else math.ceil(n / max_ticks)
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


def rotation_for(shown, total, width_in, pt, family=DEFAULT_FAMILY):
    """0, 30 or 45 degrees, decided by counting and measuring."""
    if total > DENSE_AT:
        return 45
    if len(shown) <= 8:
        return 0
    if width_in and shown:
        widest = max(textfit.text_width_in(t, pt, family) for t in shown)
        if widest + _GAP_IN <= width_in / len(shown):
            return 0
    return 30


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
    rot = rotation_for(shown, len(labels), axes_width_in(ax), pt, family)
    kw = {"fontsize": pt, "rotation": rot}
    if rot:
        kw["ha"] = "right"
    if color:
        kw["color"] = color
    ax.set_xticks([x[i] for i in idx])
    ax.set_xticklabels(shown, **kw)
    return labels
