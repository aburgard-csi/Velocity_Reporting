# Ported from v5 02-Scripts/ils/kickoff_analysis/metrics/nsf_strat.py at 7ba1e63. Logic unchanged; no edits (its only import is the relative ..core.io).
"""Analyses 5-10: NSF/OD item stratification by item-count bin.

The notebook had six near-identical cells for this:
  5 / 6   personal / business, basic (accounts + items)
  7 / 8   personal / business, + pay ratio
  9 / 10  personal / business, + deposits/swipes/OD-limit metrics
    (10 was left empty in the notebook -- filled in here by mirroring 9,
     swapped to the business segment, per instruction)

Consolidated into one function with a `level` switch instead of six
copy-pasted cells, since the only real difference between them is which
extra columns get aggregated.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.io import (
    ACCT_NO, TOTAL_ITEMS, PAID_ITEMS, DEPOSIT_COUNT, DEPOSIT_AMOUNT,
    OD_LIMIT, SWIPES,
)
from ._common import NSF_BINS, NSF_LABELS, append_grand_total, safe_ratio


def compute(segment_df: pd.DataFrame, level: str = "basic") -> pd.DataFrame:
    """
    segment_df: pre-filtered to open + personal/business.
    level: "basic" (5/6), "pay_ratio" (7/8), or "full" (9/10).
    """
    d = segment_df[segment_df[TOTAL_ITEMS].notna()].copy()
    d["NSF Bin"] = pd.cut(d[TOTAL_ITEMS], bins=NSF_BINS, labels=NSF_LABELS)

    agg = {
        "# of Accounts": (ACCT_NO, "count"),
        "Total OD/NSF Items": (TOTAL_ITEMS, "sum"),
    }
    if level in ("pay_ratio", "full"):
        agg["# of Items Paid"] = (PAID_ITEMS, "sum")

    has_deps_cnt = has_deps_amt = has_od_limit = has_swipes = False
    if level == "full":
        has_deps_cnt = DEPOSIT_COUNT in d.columns
        has_deps_amt = DEPOSIT_AMOUNT in d.columns
        has_od_limit = OD_LIMIT in d.columns
        has_swipes = SWIPES in d.columns
        if has_deps_cnt:
            agg["Avg # Dep/Month"] = (DEPOSIT_COUNT, "mean")
        if has_deps_amt:
            agg["Avg $$ Dep/Month"] = (DEPOSIT_AMOUNT, "mean")
        if has_od_limit:
            agg["Average of OD Limit"] = (OD_LIMIT, "mean")
        if has_swipes:
            agg["Average of Swipes"] = (SWIPES, "mean")

    summary = d.groupby("NSF Bin", observed=True).agg(**agg).reset_index()
    summary["NSF Bin"] = summary["NSF Bin"].astype(str)

    total_accounts = summary["# of Accounts"].sum()
    total_items = summary["Total OD/NSF Items"].sum()
    summary["% of Accounts"] = (summary["# of Accounts"] / total_accounts * 100).round(2)
    summary["% of Items Presented"] = (summary["Total OD/NSF Items"] / total_items * 100).round(2)

    grand = {
        "# of Accounts": total_accounts,
        "% of Accounts": 100.0,
        "Total OD/NSF Items": total_items,
        "% of Items Presented": 100.0,
    }

    if level in ("pay_ratio", "full"):
        total_paid = summary["# of Items Paid"].sum()
        summary["Pay Ratio"] = safe_ratio(summary["# of Items Paid"], summary["Total OD/NSF Items"])
        summary["# of Items Paid"] = summary["# of Items Paid"].astype(int)
        grand["# of Items Paid"] = total_paid
        grand["Pay Ratio"] = round(total_paid / total_items, 4) if total_items else 0

    if level == "full":
        if has_deps_cnt:
            grand["Avg # Dep/Month"] = d[DEPOSIT_COUNT].mean()
        if has_deps_amt:
            grand["Avg $$ Dep/Month"] = d[DEPOSIT_AMOUNT].mean()
        if has_od_limit:
            grand["Average of OD Limit"] = d[OD_LIMIT].mean()
        if has_swipes:
            grand["Average of Swipes"] = d[SWIPES].mean()

    summary["# of Accounts"] = summary["# of Accounts"].astype(int)
    summary["Total OD/NSF Items"] = summary["Total OD/NSF Items"].astype(int)

    summary = append_grand_total(summary, "NSF Bin", grand)

    round_cols = [c for c in [
        "Avg # Dep/Month", "Avg $$ Dep/Month", "Average of OD Limit", "Average of Swipes",
    ] if c in summary.columns]
    if round_cols:
        summary = summary.round({c: 2 for c in round_cols})

    return summary
