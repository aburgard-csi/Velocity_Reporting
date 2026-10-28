# Ported from v5 02-Scripts/ils/kickoff_analysis/metrics/od_status.py at 7ba1e63. Logic unchanged; no edits (its only import is the relative ..core.io).
"""Slide 11: OD/NSF Summary by Stat Code (personal and business)."""

from __future__ import annotations

import pandas as pd

from ..core.io import ACCT_NO, STAT_CODE, TOTAL_ITEMS, PAID_ITEMS
from ._common import append_grand_total, safe_ratio


def compute(segment_df: pd.DataFrame) -> pd.DataFrame:
    """segment_df: pre-filtered to open + personal/business."""
    summary = segment_df.groupby(STAT_CODE).agg(**{
        "# of Accounts": (ACCT_NO, "count"),
        "Total OD/NSF Items": (TOTAL_ITEMS, "sum"),
        "# of Items Paid": (PAID_ITEMS, "sum"),
    }).reset_index()

    summary["% of Accounts"] = summary["# of Accounts"] / summary["# of Accounts"].sum() * 100
    summary["% of Items Presented"] = (
        summary["Total OD/NSF Items"] / summary["Total OD/NSF Items"].sum() * 100
    )
    summary["Pay Ratio"] = safe_ratio(summary["# of Items Paid"], summary["Total OD/NSF Items"])

    total_items = summary["Total OD/NSF Items"].sum()
    total_paid = summary["# of Items Paid"].sum()
    summary["# of Accounts"] = summary["# of Accounts"].astype(int)

    summary = append_grand_total(summary, STAT_CODE, {
        "# of Accounts": summary["# of Accounts"].sum(),
        "% of Accounts": 100.0,
        "Total OD/NSF Items": total_items,
        "% of Items Presented": 100.0,
        "# of Items Paid": total_paid,
        "Pay Ratio": total_paid / total_items if total_items else 0,
    })

    return summary[[
        STAT_CODE, "# of Accounts", "% of Accounts",
        "Total OD/NSF Items", "% of Items Presented", "# of Items Paid", "Pay Ratio",
    ]]
