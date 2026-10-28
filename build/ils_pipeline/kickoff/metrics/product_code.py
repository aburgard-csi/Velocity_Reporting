# Ported from v5 02-Scripts/ils/kickoff_analysis/metrics/product_code.py at 7ba1e63. Logic unchanged; no edits (its only import is the relative ..core.io).
"""Product Code distribution.

Not an eligibility signal in ILS (confirmed) -- just a useful count/%
breakdown of accounts by product for the kickoff conversation.
"""

from __future__ import annotations

import pandas as pd

from ..core.io import ACCT_NO, PRODUCT_CODE
from ._common import append_grand_total


def compute(df: pd.DataFrame) -> pd.DataFrame:
    summary = df.groupby(PRODUCT_CODE, dropna=False).agg(**{
        "# of Accounts": (ACCT_NO, "count"),
    }).reset_index()
    summary[PRODUCT_CODE] = summary[PRODUCT_CODE].fillna("(blank)")

    total = summary["# of Accounts"].sum()
    summary["% of Accounts"] = (summary["# of Accounts"] / total * 100).round(2)
    summary = summary.sort_values("# of Accounts", ascending=False).reset_index(drop=True)

    return append_grand_total(summary, PRODUCT_CODE, {
        "# of Accounts": total,
        "% of Accounts": 100.0,
    })
