# Ported from v5 02-Scripts/ils/pre_go_live/sections/_cut.py at 7ba1e63. Logic unchanged; copied whole.
"""The one groupby every PGL table is a variation of.

The notebook repeated this block sixteen times with different filters and
group columns; here it is once. A cut takes a population (already masked to
its base), groups it, and returns rows of
    [group, accounts, pct_of_base, items, paid, pay_rate_pct, ...means/sums]
with the base's size as the denominator, stated by the caller."""

from __future__ import annotations

import numpy as np
import pandas as pd

ITEMS = "NSF OD Items since start date"
PAID = "Paid NSF OD Items since start date"
INIT_LIMIT = "Initial OD Limit (from Core)"
ILS_LIMIT = "OD Limit (from ILS)"
DEP_CT = "Deposit Count Last 33 days"
DEP_AMT = "Deposit Amount Last 33 days"
DC_CT = "Debit Decline Count"
DC_AMT = "Debit Decline Amount"

# column -> aggregation; order fixes the row layout
EXTRAS = {INIT_LIMIT: "mean", ILS_LIMIT: "mean", DEP_CT: "mean",
          DEP_AMT: "mean", DC_CT: "sum", DC_AMT: "sum"}


def _pct(n, d) -> float:
    return round(100 * n / d, 1) if d else 0.0


def cut(w: pd.DataFrame, group_col: str, extras: list[str] = (),
        blank: str = "<BLANK>") -> tuple[list[list], list[str]]:
    """Returns (rows, column_names). rows sorted by accounts desc."""
    total = len(w)
    g = w.copy()
    grp = g[group_col]
    if isinstance(grp.dtype, pd.CategoricalDtype):
        grp = grp.astype(str).replace("nan", blank)
    elif grp.dtype.kind not in "if":
        grp = grp.fillna(blank).astype(str)
    g["_g"] = grp
    items = pd.to_numeric(g.get(ITEMS), errors="coerce").fillna(0) if ITEMS in g else None
    paid = pd.to_numeric(g.get(PAID), errors="coerce").fillna(0) if PAID in g else None
    rows = []
    for key, part in g.groupby("_g", dropna=False, observed=True):
        idx = part.index
        row = [key if not isinstance(key, float) or key != int(key) else
               (int(key) if not np.isnan(key) else key),
               len(part), _pct(len(part), total)]
        if items is not None and paid is not None:
            it, pa = float(items.loc[idx].sum()), float(paid.loc[idx].sum())
            row += [round(it), round(pa), _pct(pa, it)]
        else:
            row += [None, None, None]
        for c in extras:
            if c not in part.columns:
                row.append(None)
            elif EXTRAS.get(c) == "sum":
                row.append(round(float(pd.to_numeric(part[c], errors="coerce").fillna(0).sum())))
            else:
                v = pd.to_numeric(part[c], errors="coerce")
                row.append(round(float(v.mean()), 1) if v.notna().any() else None)
        rows.append(row)
    rows.sort(key=lambda r: -r[1])
    names = ["group", "accounts", "pct", "items", "paid", "pay_rate_pct"] + list(extras)
    return rows, names


def open_personal(df: pd.DataFrame, bases) -> pd.DataFrame:
    return df[bases["open"] & bases["personal"]]


def open_business(df: pd.DataFrame, bases) -> pd.DataFrame:
    return df[bases["open"] & bases["business"]]
