# Ported from v5 02-Scripts/ils/kickoff_analysis/metrics/od_limit.py at 7ba1e63. Logic unchanged; no edits (its only import is the relative ..core.io).
"""Slide 9: OD Limit Stratification (personal and business).

Note: the notebook's business-account version of this cell referenced
df["Business?"] and df["Acct Stat"] == "0" instead of the canonical
"Business Flag" / "Account Status" == "O" used everywhere else in the
notebook -- a typo. Fixed here since both segments now share one function.
"""

from __future__ import annotations

import pandas as pd

from ..core.io import (
    ACCT_NO, TOTAL_ITEMS, PAID_ITEMS, OD_LIMIT, DEPOSIT_COUNT,
    DEPOSIT_AMOUNT, SWIPES,
)
from ._common import append_grand_total, safe_ratio


def compute(segment_df: pd.DataFrame) -> pd.DataFrame:
    """segment_df: pre-filtered to open + personal (or business)."""
    d = segment_df[segment_df[OD_LIMIT].notna()].copy()

    agg = {
        "# of Accounts": (ACCT_NO, "count"),
        "Total OD/NSF Items": (TOTAL_ITEMS, "sum"),
        "# of Items Paid": (PAID_ITEMS, "sum"),
    }
    has_deps_cnt = DEPOSIT_COUNT in d.columns
    has_deps_amt = DEPOSIT_AMOUNT in d.columns
    has_swipes = SWIPES in d.columns
    if has_deps_cnt:
        agg["Avg # Dep/Month"] = (DEPOSIT_COUNT, "mean")
    if has_deps_amt:
        agg["Avg $$ Dep/Month"] = (DEPOSIT_AMOUNT, "mean")
    if has_swipes:
        agg["Average of Swipes"] = (SWIPES, "mean")

    summary = d.groupby(OD_LIMIT).agg(**agg).reset_index()

    summary["% of Accounts"] = summary["# of Accounts"] / summary["# of Accounts"].sum() * 100
    summary["% of Items"] = summary["Total OD/NSF Items"] / summary["Total OD/NSF Items"].sum() * 100
    summary["Pay Ratio"] = safe_ratio(summary["# of Items Paid"], summary["Total OD/NSF Items"])

    grand = {
        "# of Accounts": summary["# of Accounts"].sum(),
        "% of Accounts": 100.0,
        "Total OD/NSF Items": summary["Total OD/NSF Items"].sum(),
        "% of Items": 100.0,
        "# of Items Paid": summary["# of Items Paid"].sum(),
        "Pay Ratio": (
            summary["# of Items Paid"].sum() / summary["Total OD/NSF Items"].sum()
            if summary["Total OD/NSF Items"].sum() else 0
        ),
    }
    if has_deps_cnt:
        grand["Avg # Dep/Month"] = d[DEPOSIT_COUNT].mean()
    if has_deps_amt:
        grand["Avg $$ Dep/Month"] = d[DEPOSIT_AMOUNT].mean()
    if has_swipes:
        grand["Average of Swipes"] = d[SWIPES].mean()

    return append_grand_total(summary, OD_LIMIT, grand)
