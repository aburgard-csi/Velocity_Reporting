# Ported from ARS v5 02-Scripts/ars/transaction_intelligence/leakage.py at a491b5c (James Gilmore); logic unchanged.
"""Competitor leakage in event time: does it rise before an account closes?

The pre-closure question the ODD cannot answer. The ODD sees an account go
quiet; only the transaction file sees who it started paying instead.

Same alignment as monthly_analysis/lifecycle.py -- each account on a clock
starting at its own close date -- applied to competitor dollars rather than
card spend. The institutions come from competition.py's classification; this
module never decides what counts as a competitor.

What the curve measures: mean competitor dollars per account per month
(named competitor institutions only -- payment apps and buy-now-pay-later are
not competitors and are not in it), each closer aligned to its own close date.
These are RAW dollars, not a share of the account's spend. A closing account
winds down, so its raw dollars tend to fall into closure; that biases the
curve AGAINST a finding rather than towards one. The signal is the closers
running materially ABOVE the still-open control over the same calendar
months (leak_divergence_month).

Depth: transaction files carry the trailing 12 completed months, sometimes
fewer. Under six months the section declines rather than publishing a curve
too short to mean what it appears to mean.

Keys: leak_* .
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.periods import Month
from ..monthly_analysis import lifecycle as L
from .lens import account_ids

MIN_CURVE_BASE = 50


def _monthly(txn: pd.DataFrame) -> pd.DataFrame:
    """Competitor dollars per account per month."""
    frame = txn.copy()
    frame["month"] = pd.to_datetime(frame["date"], errors="coerce") \
        .dt.to_period("M").dt.to_timestamp()
    return frame.groupby(["acct", "month"], as_index=False)["dollars"].sum()


def compute(odd: pd.DataFrame | None, txn: pd.DataFrame | None,
            anchor: Month, warn) -> dict:
    """anchor is the Month the ODD chapter used."""
    out: dict = {}
    if odd is None or txn is None or not len(txn):
        warn("leakage: no ODD enrichment or no competitor transactions; "
             "pre-closure leakage curve skipped")
        return out

    monthly = _monthly(txn)
    months_present = sorted(monthly["month"].dropna().unique())
    depth = len(months_present)
    out["leak_depth_months"] = depth
    window = L.choose_window(depth)
    if window is None:
        warn(f"leakage: only {depth} month(s) of competitor transactions; a "
             f"pre-closure curve needs at least {L.MIN_DEPTH}. Nothing "
             f"emitted rather than a curve too short to read.")
        return out
    out["leak_window"] = window

    wide = monthly.pivot(index="acct", columns="month", values="dollars") \
                  .reindex(columns=months_present).fillna(0.0)
    months = [Month(pd.Timestamp(m).year, pd.Timestamp(m).month)
              for m in months_present]

    ids = account_ids(odd)       # same key as the lenses: a float-read "12345.0" still joins
    if ids is None:
        warn("leakage: ODD carries no account id; curve skipped")
        return out
    closed = (pd.to_datetime(odd["Date Closed"], errors="coerce")
              if "Date Closed" in odd.columns
              else pd.Series(pd.NaT, index=odd.index))

    matrix = wide.reindex(ids).fillna(0.0).values
    closers = closed.notna().to_numpy()
    if int(closers.sum()) < MIN_CURVE_BASE:
        warn(f"leakage: fewer than {MIN_CURVE_BASE} closed accounts appear in "
             f"the transaction file; pre-closure leakage curve not drawn")
        return out

    aligned = L.align(matrix[closers], months, closed[closers], window,
                      "backward")
    out["leak_curve"] = L.curve(aligned)
    out["leak_curve_columns"] = ["offset_months", "n", "mean_competitor_dollars",
                                 "total", "pct_with_any"]
    out["leak_curve_basis"] = (
        "competitor dollars by month before the account's own close date, "
        "offset 0 being the closing month")

    # Control: still-open accounts over the SAME calendar months as the
    # closers. Anchoring them at the ODD's data month instead was a real bug:
    # the transaction file may end earlier, so the control's near offsets fell
    # outside the data entirely and the two curves compared different months.
    # The closers' median close month puts both on the same span.
    open_idx = ~closers
    if int(open_idx.sum()) >= MIN_CURVE_BASE:
        pivot = closed[closers].median()
        control_event = pd.Series(
            pd.Timestamp(pivot.year, pivot.month, 1),
            index=np.arange(int(open_idx.sum())))
        ctrl = L.align(matrix[open_idx], months, control_event, window,
                       "backward")
        out["leak_control"] = L.curve(ctrl)
        out["leak_control_basis"] = (
            "still-open accounts over the same calendar months, pivoted on "
            "the closers' median close month")
        # Leakage RISING before closure is the signal, so the test is
        # inverted: closers materially ABOVE control, not below.
        rise = L.divergence_month(out["leak_curve"], out["leak_control"],
                                  direction="above")
        out["leak_divergence_month"] = rise
        out["leak_divergence_note"] = (
            f"competitor spend among closing accounts ran materially above "
            f"still-open accounts from {rise} month(s) before closure onward"
            if rise is not None else
            "no sustained rise in competitor spend before closure")
    return out
