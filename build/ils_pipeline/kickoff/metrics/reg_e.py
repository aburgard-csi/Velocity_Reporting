# Ported from v5 02-Scripts/ils/kickoff_analysis/metrics/reg_e.py at 7ba1e63. Logic unchanged; no edits (its only import is the relative ..core.io).
"""Slides 10-11: Reg E Distribution.

Three variants from the notebook, consolidated here:
  - simple:        # of Accounts by Reg E Flag
  - with_eligibility: same, split by Stat Code eligibility
  - annual:         full detail (items, pay ratio, deposits, OD limit, swipes)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.io import (
    ACCT_NO, STAT_CODE, TOTAL_ITEMS, PAID_ITEMS, DEPOSIT_COUNT,
    DEPOSIT_AMOUNT, OD_LIMIT, SWIPES, REG_E_FLAG, CodeConfig,
)
from ._common import append_grand_total, safe_ratio


def simple(segment_df: pd.DataFrame) -> pd.DataFrame:
    """segment_df: pre-filtered to open + personal (or business)."""
    summary = segment_df.groupby(REG_E_FLAG).agg(**{
        "# of Accounts": (ACCT_NO, "count"),
    }).reset_index()

    total = summary["# of Accounts"].sum()
    summary["% of Accounts"] = (summary["# of Accounts"] / total * 100).round(2)

    return append_grand_total(summary, REG_E_FLAG, {
        "# of Accounts": total,
        "% of Accounts": 100.0,
    })


def with_eligibility(segment_df: pd.DataFrame, codes: CodeConfig) -> tuple[pd.DataFrame, str | None]:
    """
    Reg E Flag distribution split by Stat Code eligibility.
    Reg E opt-in split by OD ELIGIBILITY -- two different things, and calling
    the cross-tab "Reg E eligibility" conflated them (James, 2026-09-09).
    Eligibility is the OD Status code; Reg E opt-in is a separate variable
    the member sets. pre_go_live had this right the whole time: --od-eligible
    and --rege-opt-in are separate arguments there.

    Returns (table, warning) -- warning is set if codes.eligible_stat_codes
    matched zero accounts, which usually means eligibility isn't actually
    determined by this column/value for this client and the resulting
    wholly ineligible split shouldn't be presented as meaningful.
    """
    d = segment_df.copy()
    is_eligible = codes.is_eligible(d[STAT_CODE])
    d["Eligibility"] = np.where(is_eligible, "Eligible", "Ineligible")

    warning = None
    if len(d) and is_eligible.all():
        # 1840: every one of 6,218 rows carried Stat Code '0'. Confirming
        # that '0' means eligible yields a fully eligible split that splits
        # nothing -- exactly as uninformative as 0%, and it warned on only
        # one of the two.
        warning = (
            f"OD eligibility rule (Stat Code) {codes.eligible_stat_codes} matched ALL "
            f"{len(d)} accounts, so this is not a split. Every account "
            f"carries the same Stat Code, which usually means eligibility is "
            f"determined by some other field for this client -- treat it as "
            f"not meaningful until confirmed.")
    elif is_eligible.sum() == 0 and len(d) > 0:
        observed = sorted(d[STAT_CODE].astype(str).unique())[:10]
        warning = (
            f"OD eligibility rule (Stat Code) {codes.eligible_stat_codes} matched 0 of {len(d)} accounts. "
            f"Observed Stat Code values include: {observed}. "
            f"Eligibility may not be determined by Stat Code for this client -- "
            f"treat this split as not meaningful until confirmed."
        )

    summary = d.groupby(["Eligibility", REG_E_FLAG]).agg(**{
        "# of Accounts": (ACCT_NO, "count"),
    }).reset_index()

    total = summary["# of Accounts"].sum()
    summary["% of Accounts"] = (summary["# of Accounts"] / total * 100).round(2)

    # Mimic a grouped pivot header: blank out repeated Eligibility labels.
    summary["Eligibility"] = summary["Eligibility"].mask(summary["Eligibility"].duplicated(), "")

    grand = pd.DataFrame([{
        "Eligibility": "Grand Total", REG_E_FLAG: "",
        "# of Accounts": total, "% of Accounts": 100.0,
    }])
    return pd.concat([summary, grand], ignore_index=True), warning


def annual(segment_df: pd.DataFrame) -> pd.DataFrame:
    """Full detail: items, pay ratio, deposits, OD limit, swipes by Reg E Flag."""
    d = segment_df

    agg = {
        "# of Accounts": (ACCT_NO, "count"),
        "Total OD/NSF Items": (TOTAL_ITEMS, "sum"),
        "Total NSF Items Paid": (PAID_ITEMS, "sum"),
    }
    has_deps_cnt = DEPOSIT_COUNT in d.columns
    has_deps_amt = DEPOSIT_AMOUNT in d.columns
    has_od_limit = OD_LIMIT in d.columns
    has_swipes = SWIPES in d.columns
    if has_deps_cnt:
        agg["Avg # Dep/Month"] = (DEPOSIT_COUNT, "mean")
    if has_deps_amt:
        agg["Avg $ Dep/Month"] = (DEPOSIT_AMOUNT, "mean")
    if has_od_limit:
        agg["Avg Overdraft Limit"] = (OD_LIMIT, "mean")
    if has_swipes:
        agg["Avg Debit Card Swipes"] = (SWIPES, "mean")

    summary = d.groupby(REG_E_FLAG).agg(**agg).reset_index()

    summary["% of Accounts"] = summary["# of Accounts"] / summary["# of Accounts"].sum() * 100
    summary["% of Items Presented"] = (
        summary["Total OD/NSF Items"] / summary["Total OD/NSF Items"].sum() * 100
    )
    summary["Pay Ratio"] = safe_ratio(summary["Total NSF Items Paid"], summary["Total OD/NSF Items"])

    cols = [REG_E_FLAG, "# of Accounts", "% of Accounts", "Total OD/NSF Items",
            "% of Items Presented", "Total NSF Items Paid", "Pay Ratio"]
    if has_deps_cnt:
        cols.append("Avg # Dep/Month")
    if has_deps_amt:
        cols.append("Avg $ Dep/Month")
    if has_od_limit:
        cols.append("Avg Overdraft Limit")
    if has_swipes:
        cols.append("Avg Debit Card Swipes")
    summary = summary[cols]

    total_items = summary["Total OD/NSF Items"].sum()
    total_paid = summary["Total NSF Items Paid"].sum()
    grand = {
        "# of Accounts": summary["# of Accounts"].sum(),
        "% of Accounts": 100.0,
        "Total OD/NSF Items": total_items,
        "% of Items Presented": 100.0,
        "Total NSF Items Paid": total_paid,
        "Pay Ratio": total_paid / total_items if total_items else 0,
    }
    if has_deps_cnt:
        grand["Avg # Dep/Month"] = d[DEPOSIT_COUNT].mean()
    if has_deps_amt:
        grand["Avg $ Dep/Month"] = d[DEPOSIT_AMOUNT].mean()
    if has_od_limit:
        grand["Avg Overdraft Limit"] = d[OD_LIMIT].mean()
    if has_swipes:
        grand["Avg Debit Card Swipes"] = d[SWIPES].mean()

    summary["# of Accounts"] = summary["# of Accounts"].astype(int)
    return append_grand_total(summary, REG_E_FLAG, grand)
