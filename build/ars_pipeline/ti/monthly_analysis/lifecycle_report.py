# Ported from ARS v5 02-Scripts/ars/monthly_analysis/lifecycle_report.py at a491b5c (James Gilmore); logic unchanged.
"""The lifecycle section: ramp at opening, decline into closure, and controls.

Alignment and curve arithmetic live in lifecycle.py. This module decides WHICH
accounts go into which curve, supplies the control, and emits the keys.

The control is the point. A closing account transacts less; compared against
nothing, "closing accounts spend less before closing" is circular. Every
decline curve is measured against still-open accounts in the SAME tenure
bucket, so neither tenure nor seasonality can explain the gap.

Base: the whole file. An account that closed still closed, and excluding it
would leave the section measuring only the accounts that stayed -- the same
reasoning attrition.py gives for windowing on the whole frame.

Keys: life_* .
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.periods import Month, columns_for, split_tag
from . import lifecycle as L

# A curve needs this many accounts at offset 0 before it is worth drawing at
# all; individual offsets thin out from there and self-suppress.
MIN_CURVE_BASE = 50
SERIES = ("Spend", "Swipes")


def _months_of(columns) -> list[Month]:
    """The Month behind each monthly column, chronological."""
    out = []
    for col in columns:
        parsed = split_tag(col)
        if parsed:
            out.append(parsed[0])
    return out


def _matrix(df: pd.DataFrame, columns) -> np.ndarray:
    return df[columns].apply(pd.to_numeric, errors="coerce").fillna(0).values


def _tenure_years(df: pd.DataFrame, anchor: Month) -> pd.Series:
    end = pd.Timestamp(anchor.year, anchor.month, 1) + pd.offsets.MonthEnd(0)
    opened = pd.to_datetime(df.get("Date Opened"), errors="coerce")
    return (end - opened).dt.days / 365.2425


def _curves(df, columns, months, event, window, direction, min_base):
    """One curve per series, or {} when the cohort is too small to draw."""
    if int(event.notna().sum()) < min_base:
        return {}
    out = {}
    for suffix in SERIES:
        cols = [c for c in columns if str(c).endswith(suffix)]
        if not cols:
            continue
        aligned = L.align(_matrix(df, cols), months, event, window, direction)
        out[suffix.lower()] = L.curve(aligned)
    return out


def _deposit_matrix(monthly, ids: pd.Series):
    """Deposits as an accounts x months matrix on the ODD's own row order.

    Returns (matrix, months) or (None, None). Accounts absent from the
    deposits file get zeros: the file covers everybody, so no row means no
    deposit rather than no data.
    """
    if monthly is None or not len(monthly):
        return None, None
    wide = monthly.pivot(index="acct", columns="date", values="dep_amount")
    wide = wide.reindex(sorted(wide.columns), axis=1).fillna(0.0)
    months = [Month(pd.Timestamp(c).year, pd.Timestamp(c).month)
              for c in wide.columns]
    return wide.reindex(ids).fillna(0.0).values, months


def _deposit_curves(config, ids, closed, anchor, window, out, warn) -> None:
    """The decline curve again, on deposits rather than card spend.

    Worth its own curve rather than a second series on the spend one: people
    stop routing pay somewhere before they stop swiping there, so the two are
    expected to diverge at different offsets, and the gap between them is
    itself the finding.
    """
    matrix, months = _deposit_matrix(config.get("_deposit_monthly"), ids)
    if matrix is None:
        return
    depth = len(months)
    dep_window = L.choose_window(depth)
    if dep_window is None:
        warn(f"lifecycle: deposits cover only {depth} month(s); a deposit "
             f"curve needs at least {L.MIN_DEPTH}")
        return
    dep_window = min(dep_window, window)
    out["life_deposit_depth_months"] = depth

    closers = closed.notna().to_numpy()
    if int(closers.sum()) < MIN_CURVE_BASE:
        return
    aligned = L.align(matrix[closers], months, closed[closers], dep_window,
                      "backward")
    out["life_deposit_decline"] = L.curve(aligned)
    out["life_deposit_decline_basis"] = (
        "deposit dollars by month before the account's own close date")

    open_idx = ~closers
    if int(open_idx.sum()) < MIN_CURVE_BASE:
        return
    pivot = closed[closers].median()
    control_event = pd.Series(pd.Timestamp(pivot.year, pivot.month, 1),
                              index=np.arange(int(open_idx.sum())))
    ctrl = L.align(matrix[open_idx], months, control_event, dep_window,
                   "backward")
    out["life_deposit_control"] = L.curve(ctrl)
    warning = L.divergence_month(out["life_deposit_decline"],
                                 out["life_deposit_control"])
    out["life_deposit_divergence_month"] = warning
    spend_warning = out.get("life_divergence_month")
    if warning is not None and spend_warning is not None:
        out["life_deposit_lead_months"] = warning - spend_warning
        out["life_deposit_lead_note"] = (
            f"deposits gave {abs(warning - spend_warning)} month(s) "
            f"{'more' if warning > spend_warning else 'less'} warning than "
            f"card spend on this book")


def compute(subsets, config: dict, warn) -> dict:
    """Section contract: (subsets, config, warn) -> dict of life_* keys."""
    df = subsets.total
    anchor = subsets.anchor
    if df is None or not len(df):
        return {}

    spend_cols = columns_for(df.columns, "Spend")
    depth = len(spend_cols)
    window = L.choose_window(depth)
    out: dict = {"life_depth_months": depth}
    if window is None:
        reason = (f"only {depth} monthly Spend column(s); a lifecycle curve "
                  f"needs at least {L.MIN_DEPTH}. Nothing emitted rather than "
                  f"a curve too short to mean what it appears to mean.")
        out["life_exit_reason"] = reason
        warn(f"lifecycle: {reason}")
        return out
    out["life_window"] = window
    out["life_min_cohort"] = L.MIN_COHORT

    months = _months_of(spend_cols)
    opened = pd.to_datetime(df.get("Date Opened"), errors="coerce")
    closed = (pd.to_datetime(df["Date Closed"], errors="coerce")
              if "Date Closed" in df.columns
              else pd.Series(pd.NaT, index=df.index))
    tenure = _tenure_years(df, anchor)
    buckets = tenure.map(L.bucket_of)

    # ---- onboarding ramp -------------------------------------------------
    ramp = _curves(df, spend_cols + columns_for(df.columns, "Swipes"), months,
                   opened, window, "forward", MIN_CURVE_BASE)
    if ramp:
        out["life_ramp"] = ramp.get("spend")
        out["life_ramp_swipes"] = ramp.get("swipes")
        out["life_ramp_columns"] = ["offset_months", "n", "mean", "total",
                                    "pct_active"]
        out["life_ramp_basis"] = (
            "months since the account's own open date; the base thins with "
            "depth because only accounts opened early enough in the file "
            "reach the later offsets")
    else:
        warn(f"lifecycle: fewer than {MIN_CURVE_BASE} accounts carry an open "
             f"date; onboarding ramp not drawn")

    from . import lifecycle_ics

    lifecycle_ics.compare(df, opened, closed, spend_cols, months,
                          window, out, warn)

    # ---- pre-closure decline, against a same-bucket control --------------
    if not closed.notna().any():
        warn("lifecycle: no Date Closed values; pre-closure decline skipped")
        return out

    all_cols = spend_cols + columns_for(df.columns, "Swipes")
    closers = _curves(df[closed.notna()], all_cols, months,
                      closed[closed.notna()], window, "backward", MIN_CURVE_BASE)
    if not closers:
        warn(f"lifecycle: fewer than {MIN_CURVE_BASE} closed accounts; "
             f"pre-closure decline not drawn")
        return out

    out["life_decline"] = closers.get("spend")
    out["life_decline_swipes"] = closers.get("swipes")
    out["life_decline_columns"] = out.get("life_ramp_columns") or [
        "offset_months", "n", "mean", "total", "pct_active"]
    out["life_decline_basis"] = (
        "months before the account's own close date, offset 0 being the "
        "closing month")

    # Control: still-open accounts, measured backward from the anchor over the
    # same offsets. Same calendar months, so seasonality cannot explain a gap.
    open_mask = closed.isna()
    anchor_ts = pd.Timestamp(anchor.year, anchor.month, 1)
    control_event = pd.Series(anchor_ts, index=df.index[open_mask])
    control = _curves(df[open_mask], all_cols, months, control_event,
                      window, "backward", MIN_CURVE_BASE)
    if control:
        out["life_control"] = control.get("spend")
        out["life_control_basis"] = (
            "still-open accounts over the same calendar months, so neither "
            "seasonality nor the book's trend can explain the gap")
        months_of_warning = L.divergence_month(out["life_decline"],
                                               out["life_control"])
        out["life_divergence_month"] = months_of_warning
        out["life_divergence_ratio"] = L.DIVERGENCE_RATIO
        out["life_divergence_note"] = (
            f"closing accounts sat below {int(100 * L.DIVERGENCE_RATIO)}% of "
            f"still-open accounts from {months_of_warning} month(s) before "
            f"closure onward" if months_of_warning is not None else
            "no sustained separation from the control before closure")

    # ---- per tenure bucket ----------------------------------------------
    by_bucket = []
    for _, _, label in L.TENURE_BUCKETS:
        band = closed.notna() & (buckets == label)
        n = int(band.sum())
        if n < MIN_CURVE_BASE:
            by_bucket.append([label, n, None])
            continue
        cur = _curves(df[band], spend_cols, months, closed[band], window,
                      "backward", MIN_CURVE_BASE)
        ctrl = _curves(df[open_mask & (buckets == label)], spend_cols, months,
                       pd.Series(anchor_ts, index=df.index[open_mask & (buckets == label)]),
                       window, "backward", MIN_CURVE_BASE)
        div = (L.divergence_month(cur["spend"], ctrl["spend"])
               if cur.get("spend") and ctrl.get("spend") else None)
        by_bucket.append([label, n, div])
    out["life_divergence_by_tenure"] = by_bucket
    out["life_divergence_by_tenure_columns"] = ["tenure", "closed_n",
                                                "months_of_warning"]

    # ---- deposits, when the client sent the file -------------------------
    ids = df.get("Acct Number", df.get("Acct ID"))
    if ids is not None:
        _deposit_curves(config, ids.astype(str).str.strip(), closed, anchor,
                        window, out, warn)
    return out
