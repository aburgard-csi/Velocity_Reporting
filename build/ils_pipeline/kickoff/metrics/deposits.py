# Ported from v5 02-Scripts/ils/kickoff_analysis/metrics/deposits.py at 7ba1e63. Logic unchanged; no edits (its only import is the relative ..core.io).
"""Analyses 3 & 4: Deposit frequency distribution for open accounts.

The notebook had near-identical cells for personal (Analysis 3) and
business (Analysis 4) accounts. Consolidated into one function taking the
pre-filtered subset, called once per segment.
"""

from __future__ import annotations

import pandas as pd

from ..core.io import ACCT_NO, DEPOSIT_COUNT, DEPOSIT_AMOUNT
from ._common import DEPOSIT_BINS, DEPOSIT_LABELS, append_grand_total


def compute(segment_df: pd.DataFrame) -> pd.DataFrame:
    """segment_df should already be filtered to open + personal/business."""
    d = segment_df[segment_df[DEPOSIT_COUNT].notna()].copy()

    d["Deposit Bin"] = pd.cut(d[DEPOSIT_COUNT], bins=DEPOSIT_BINS, labels=DEPOSIT_LABELS)

    summary = d.groupby("Deposit Bin", observed=True).agg(
        Accounts=(ACCT_NO, "count"),
        **{"Avg $$ Deposits": (DEPOSIT_AMOUNT, "mean")},
        **{"Avg # of Deposits": (DEPOSIT_COUNT, "mean")},
        **{"Med # of Deposits": (DEPOSIT_COUNT, "median")},
    ).reset_index()

    summary["% of Accounts"] = (summary["Accounts"] / summary["Accounts"].sum() * 100).round(2)
    summary["Accounts"] = summary["Accounts"].astype(int)
    summary["Deposit Bin"] = summary["Deposit Bin"].astype(str)

    summary = summary[[
        "Deposit Bin", "Accounts", "% of Accounts",
        "Avg # of Deposits", "Med # of Deposits", "Avg $$ Deposits",
    ]]

    summary = append_grand_total(summary, "Deposit Bin", {
        "Accounts": summary["Accounts"].sum(),
        "% of Accounts": 100.0,
        "Avg # of Deposits": d[DEPOSIT_COUNT].mean(),
        "Med # of Deposits": d[DEPOSIT_COUNT].median(),
        "Avg $$ Deposits": d[DEPOSIT_AMOUNT].mean(),
    })

    return summary.round({
        "Avg # of Deposits": 2, "Med # of Deposits": 2, "Avg $$ Deposits": 2,
    })
