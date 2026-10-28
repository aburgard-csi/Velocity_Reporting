# Ported from v5 02-Scripts/ils/kickoff_analysis/metrics/business_split.py at 7ba1e63. Logic unchanged; no edits (its only import is the relative ..core.io).
"""Analysis 2: Business vs Personal (Open Accounts)."""

from __future__ import annotations

import pandas as pd

from ..core.io import (
    ACCT_NO, ACCOUNT_STATUS, BUSINESS_FLAG, TOTAL_ITEMS, PAID_ITEMS,
    DEPOSIT_COUNT, DEPOSIT_AMOUNT, CodeConfig,
)
from ._common import append_grand_total


def compute(df: pd.DataFrame, codes: CodeConfig) -> pd.DataFrame:
    df_open = df[df[ACCOUNT_STATUS] == codes.open_status_code].copy()

    agg = {
        "# of Accounts": (ACCT_NO, "count"),
        "# of Items": (TOTAL_ITEMS, "sum"),
        "# of Paid Items": (PAID_ITEMS, "sum"),
    }
    has_deps_cnt = DEPOSIT_COUNT in df_open.columns
    has_deps_amt = DEPOSIT_AMOUNT in df_open.columns
    if has_deps_cnt:
        agg["Avg # of Deposits"] = (DEPOSIT_COUNT, "mean")
        agg["Med # of Deposits"] = (DEPOSIT_COUNT, "median")
    if has_deps_amt:
        agg["Avg $$ Deposits"] = (DEPOSIT_AMOUNT, "mean")
        agg["Med $$ Deposits"] = (DEPOSIT_AMOUNT, "median")

    summary = (
        df_open.groupby(BUSINESS_FLAG, dropna=False)
        .agg(**agg)
        .reset_index()
    )
    summary[BUSINESS_FLAG] = summary[BUSINESS_FLAG].fillna("Unknown")

    tot_accts = summary["# of Accounts"].sum()
    tot_items = summary["# of Items"].sum()
    tot_paid = summary["# of Paid Items"].sum()

    summary["% of Accounts"] = summary["# of Accounts"] / max(tot_accts, 1) * 100
    summary["% of Items"] = summary["# of Items"] / max(tot_items, 1) * 100
    summary["% Pay Rate"] = (
        summary["# of Paid Items"] / summary["# of Items"].replace({0: pd.NA})
    ).fillna(0)

    cols = [BUSINESS_FLAG, "# of Accounts", "% of Accounts", "# of Items",
            "% of Items", "# of Paid Items", "% Pay Rate"]
    if has_deps_cnt:
        cols += ["Avg # of Deposits", "Med # of Deposits"]
    if has_deps_amt:
        cols += ["Avg $$ Deposits", "Med $$ Deposits"]
    summary = summary[cols]

    grand = {
        "# of Accounts": tot_accts,
        "% of Accounts": 100.0 if tot_accts else 0.0,
        "# of Items": tot_items,
        "% of Items": 100.0 if tot_items else 0.0,
        "# of Paid Items": tot_paid,
        "% Pay Rate": (tot_paid / tot_items) if tot_items else 0.0,
    }
    if has_deps_cnt:
        grand["Avg # of Deposits"] = df_open[DEPOSIT_COUNT].mean()
        grand["Med # of Deposits"] = df_open[DEPOSIT_COUNT].median()
    if has_deps_amt:
        grand["Avg $$ Deposits"] = df_open[DEPOSIT_AMOUNT].mean()
        grand["Med $$ Deposits"] = df_open[DEPOSIT_AMOUNT].median()

    return append_grand_total(summary, BUSINESS_FLAG, grand)
