# Ported from v5 02-Scripts/ils/kickoff_analysis/metrics/account_status.py at 7ba1e63. Logic unchanged; no edits (its only import is the relative ..core.io).
"""Analysis 1: Account Status Summary (all accounts, not filtered to open)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.io import ACCT_NO, ACCOUNT_STATUS, TOTAL_ITEMS, PAID_ITEMS
from ._common import append_grand_total


def compute(df: pd.DataFrame) -> pd.DataFrame:
    summary = df.groupby(ACCOUNT_STATUS).agg(**{
        "# of Accounts": (ACCT_NO, "count"),
        "# of Items": (TOTAL_ITEMS, "sum"),
        "# of Items Paid": (PAID_ITEMS, "sum"),
    }).reset_index()

    summary["% of Accounts"] = (summary["# of Accounts"] / summary["# of Accounts"].sum() * 100).round(2)
    summary["% of Items"] = (summary["# of Items"] / summary["# of Items"].sum() * 100).round(2)
    summary["Pay Ratio"] = np.where(
        summary["# of Items"] > 0,
        (summary["# of Items Paid"] / summary["# of Items"]).round(2),
        0,
    )

    total_items = summary["# of Items"].sum()
    total_paid = summary["# of Items Paid"].sum()
    summary = append_grand_total(summary, ACCOUNT_STATUS, {
        "# of Accounts": summary["# of Accounts"].sum(),
        "# of Items": total_items,
        "# of Items Paid": total_paid,
        "% of Accounts": 100.0,
        "% of Items": 100.0,
        "Pay Ratio": round(total_paid / total_items, 2) if total_items else 0,
    })

    return summary[[
        ACCOUNT_STATUS, "# of Accounts", "% of Accounts",
        "# of Items", "% of Items", "# of Items Paid", "Pay Ratio",
    ]]
