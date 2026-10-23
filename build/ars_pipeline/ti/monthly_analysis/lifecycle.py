# Ported from ARS v5 02-Scripts/ars/monthly_analysis/lifecycle.py at a491b5c (James Gilmore); logic unchanged.
"""Lifecycle: what activity does around an account's own opening and closure.

Every other measure in this pipeline is anchored to the DATA MONTH. That is
correct for "how is the book doing" and wrong for "what does leaving look
like": retention.py compares an account's last three months against the three
before, both ending at the anchor, so an account that closed eight months ago
has both windows sitting in months when it was already gone. It scores Dormant
with zero spend and its actual decline is invisible.

This module gives every account a clock that starts at ITS OWN event.

    calendar time   Apr25 May25 Jun25 ... Jul26
    event time      m-12  m-11  m-10  ... m-0

Two lenses, one mechanism: forward from the open month (the onboarding ramp),
backward from the close month (the pre-closure decline).

THE CURVE IS RAGGED, DELIBERATELY. A full ODD carries 16 monthly columns, so a
twelve-month lookback only qualifies accounts that closed within the last four
-- two thirds of the attrition cohort discarded to buy depth nobody asked for.
Instead every offset reports its own base and thins with depth, and an offset
below MIN_COHORT returns None rather than an average over a handful. That is
the habit ics.py already follows with SURVIVAL_MIN_BASE.

Keys: life_* .
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.periods import Month

# The stated depth rule. Twelve months of data caps the curve at twelve
# offsets; six to eleven caps at six; below six the section declines rather
# than publishing a three-month curve, which is a different claim from a
# twelve-month one rather than a shorter version of it.
WINDOW_FULL = 12
WINDOW_SHORT = 6
MIN_DEPTH = 6

# Below this an offset's mean is one or two accounts wearing the authority of
# a line on a chart.
MIN_COHORT = 30

# Reporting cut and control frame, in MONTHS. The first year is resolved month
# by month, not collapsed: that is where most closures land, and where a young
# programme's whole cohort sits, so a single "0-12 mo" band hides the detail
# exactly where it is needed. After the first year the bands widen, and
# everything past ten years is one settled group -- the steady-state reference
# for what an account that is going nowhere looks like.
FIRST_YEAR_MONTHS = 12
TENURE_BUCKETS = (
    [(m, m + 1, f"month {m + 1}") for m in range(FIRST_YEAR_MONTHS)]
    + [(12, 36, "1-3 yr"), (36, 60, "3-5 yr"), (60, 120, "5-10 yr"),
       (120, 2400, "10+ yr")])
SETTLED_BUCKET = "10+ yr"
MONTHS_PER_YEAR = 12


def choose_window(depth_months: int) -> int | None:
    """How many offsets the data supports, or None to decline the section."""
    if depth_months >= WINDOW_FULL:
        return WINDOW_FULL
    if depth_months >= MIN_DEPTH:
        return WINDOW_SHORT
    return None


def bucket_of(tenure_years) -> str | None:
    """Which tenure bucket an account sits in, from tenure in YEARS.

    None when tenure is unknown -- unknown is not the same as new, and
    guessing would load month 1 with every account whose open date failed to
    parse, which is the band a young-programme comparison reads most closely.
    """
    if tenure_years is None or pd.isna(tenure_years):
        return None
    months = float(tenure_years) * MONTHS_PER_YEAR
    for low, high, label in TENURE_BUCKETS:
        if low <= months < high:
            return label
    return None


def first_year_buckets() -> list[str]:
    """The month-by-month labels, for a surface that wants only year one."""
    return [label for _, _, label in TENURE_BUCKETS[:FIRST_YEAR_MONTHS]]


def align(matrix: np.ndarray, months: list[Month], event: pd.Series,
          window: int, direction: str) -> np.ndarray:
    """Re-index each row so column 0 is that row's own event month.

    matrix   accounts x months, in CHRONOLOGICAL column order
    months   the Month for each column, same order
    event    one event date per row (open or close); NaT means no event
    window   how many offsets past the event month to carry
    direction 'forward' from opening, 'backward' from closure

    Returns accounts x (window + 1). Offsets that fall outside the file are
    NaN, never zero: an account whose history predates the extract has
    UNKNOWN spend, and zero would drag every mean toward the floor.
    """
    if direction not in ("forward", "backward"):
        raise ValueError(f"direction must be forward or backward, got {direction!r}")

    ordinals = np.array([m.year * 12 + (m.month - 1) for m in months])
    position = {int(o): i for i, o in enumerate(ordinals)}

    event = pd.to_datetime(event, errors="coerce")
    event_ord = (event.dt.year * 12 + (event.dt.month - 1)).to_numpy(dtype="float64")

    out = np.full((matrix.shape[0], window + 1), np.nan)
    step = 1 if direction == "forward" else -1
    for row in range(matrix.shape[0]):
        base = event_ord[row]
        if np.isnan(base):
            continue
        for offset in range(window + 1):
            col = position.get(int(base) + step * offset)
            if col is not None:
                out[row, offset] = matrix[row, col]
    return out


def curve(aligned: np.ndarray, min_cohort: int = MIN_COHORT) -> list[list]:
    """Mean and activity share per offset, with the base at each one.

    Rows: [offset, n, mean, total, pct_active]. `mean` is None below
    min_cohort -- the base is still reported, so a thin offset is visibly
    thin rather than absent.
    """
    rows = []
    for offset in range(aligned.shape[1]):
        column = aligned[:, offset]
        present = ~np.isnan(column)
        n = int(present.sum())
        if not n:
            rows.append([offset, 0, None, None, None])
            continue
        values = column[present]
        thin = n < min_cohort
        rows.append([
            offset, n,
            None if thin else round(float(values.mean()), 2),
            None if thin else round(float(values.sum())),
            None if thin else round(100 * float((values > 0).sum()) / n, 1),
        ])
    return rows


# An account is "diverging" once it sits below this share of its control. A
# ratio, not a dollar gap: an absolute threshold flags a large account losing
# 0.3% and misses a small one losing 80%.
DIVERGENCE_RATIO = 0.80


def divergence_month(closers: list[list], control: list[list],
                     ratio: float = DIVERGENCE_RATIO,
                     direction: str = "below") -> int | None:
    """The furthest offset from which closers stay below control all the way in.

    Offsets count outward from the event, so a return of 4 means the gap was
    already open four months before closure and never closed again -- four
    months of warning. A single dip does not qualify; the separation has to
    hold from that offset inward, or it is noise wearing a finding's clothes.

    direction is 'below' for a decline (spend fading before closure) and
    'above' for a rise (competitor leakage climbing before closure). The same
    ratio means the same factor either way: 0.8 is below four-fifths, or above
    five-quarters.

    None when there is no sustained separation, or when an offset needed to
    support the claim was suppressed for a thin cohort. A suppressed mean is
    unknown, not equal.
    """
    if direction not in ("below", "above"):
        raise ValueError(f"direction must be below or above, got {direction!r}")

    c = {r[0]: r[2] for r in closers}
    k = {r[0]: r[2] for r in control}
    furthest = None
    for offset in sorted(c):
        if c[offset] is None or k.get(offset) is None or not k[offset]:
            break
        separated = (c[offset] < k[offset] * ratio if direction == "below"
                     else c[offset] > k[offset] / ratio)
        if separated:
            furthest = offset
        else:
            break
    return furthest
