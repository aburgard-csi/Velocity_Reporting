# Ported from v5 02-Scripts/ils/kickoff_analysis/metrics/_common.py at 7ba1e63. Logic unchanged; no edits.
"""Shared helpers used across analysis modules.

The notebook re-pasted a `resolve_col()` helper and hand-rolled a Grand
Total row into nearly every one of its ~15 analysis cells. Since core/io.py
now canonicalizes columns once at load time, that per-cell alias resolution
is gone; this module replaces the repeated Grand-Total-row boilerplate.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

NSF_BINS = [-1, 0, 6, 12, 24, 36, 48, float("inf")]
NSF_LABELS = ["0", "1–6", "7–12", "13–24", "25–36", "37–48", "49+"]

DEPOSIT_BINS = [-1, 0, 1, 2, 5, 10, float("inf")]
DEPOSIT_LABELS = ["0", "1", "2", "3–5", "6–10", "10+"]


def safe_ratio(numerator: pd.Series, denominator: pd.Series, decimals: int = 4) -> pd.Series:
    """Elementwise numerator/denominator, 0 where denominator is 0."""
    return np.where(denominator > 0, (numerator / denominator).round(decimals), 0)


def append_grand_total(table: pd.DataFrame, label_col: str, grand_total_row: dict) -> pd.DataFrame:
    """Append a Grand Total row (as a dict of column -> value) to a table."""
    grand_total_row = {label_col: "Grand Total", **{k: v for k, v in grand_total_row.items() if k != label_col}}
    return pd.concat([table, pd.DataFrame([grand_total_row])], ignore_index=True)
