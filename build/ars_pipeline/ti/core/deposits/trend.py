# Ported from ARS v5 02-Scripts/core/deposits/trend.py at a491b5c (James Gilmore); logic unchanged.
"""Deposit inflow over time: the monthly grain, and the shape of the change.

The one thing this file does that no existing chapter can is DATE a decline.
`balance.py` says so itself: `bal_delta = Curr Bal - Avg Bal` is a trend proxy,
"enough to flag deposits draining but not enough to date the decline". A real
monthly series can name the month inflow stepped down, which is what turns
"this account is draining" into "this account stopped being paid in March".
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# A step down to 60% of the prior run-rate is a change in circumstances, not a
# light month. Tighter than this fires on ordinary variation; looser only
# catches accounts that have already gone silent, by which point the balance
# has said it too.
DECLINE_RATIO = 0.6
# Both sides of the split need enough months to have a run-rate at all.
MIN_SIDE_MONTHS = 2
MIN_MONTHS_FOR_DECLINE = 6
# Book-level concentration is reported at these cuts.
CONCENTRATION_CUTS = (1, 5, 10, 25)


def monthly(frame: pd.DataFrame) -> pd.DataFrame:
    """Deposits per account per month: the grain the event-time curves need."""
    if not len(frame):
        return pd.DataFrame(columns=["acct", "date", "dep_count", "dep_amount"])
    out = frame.copy()
    out["date"] = out["date"].dt.to_period("M").dt.to_timestamp()
    return out.groupby(["acct", "date"], as_index=False)[
        ["dep_count", "dep_amount"]].sum()


def wide(monthly_frame: pd.DataFrame) -> pd.DataFrame:
    """Account x month inflow, oldest column first, gaps filled with zero.

    A month with no deposit is a real zero here, not missing data -- the
    account was open and nothing arrived. That is the whole signal.
    """
    if monthly_frame is None or not len(monthly_frame):
        return pd.DataFrame()
    out = monthly_frame.pivot(index="acct", columns="date", values="dep_amount")
    return out.reindex(sorted(out.columns), axis=1).fillna(0.0)


def decline_month(monthly_frame: pd.DataFrame) -> pd.DataFrame:
    """Per account: the month inflow stepped down, and the run-rates either side.

    Walks every split point and takes the SHARPEST qualifying one -- the split
    with the lowest forward/backward ratio, not the first split to clear the
    threshold.

    Taking the first one dates the decline too early, and not by a little: on
    a series that runs at 1000 for eight months then drops to 200, splitting
    at month four already gives a forward mean of 600, which clears a 0.6
    threshold exactly. The account is then reported as declining four months
    before anything happened to it. The sharpest split puts the date on the
    month the step actually occurred.

    Accounts with too few months, or no step at all, come back NaT rather than
    being assigned a month they never had.
    """
    cols = ["acct", "decline_month", "inflow_before", "inflow_after"]
    grid = wide(monthly_frame)
    if not len(grid) or grid.shape[1] < MIN_MONTHS_FOR_DECLINE:
        return pd.DataFrame(columns=cols)

    values = grid.to_numpy(dtype=float)
    months = list(grid.columns)
    n = values.shape[0]

    found = np.full(n, -1, dtype=int)
    before_at = np.full(n, np.nan)
    after_at = np.full(n, np.nan)
    best = np.full(n, np.inf)

    for split in range(MIN_SIDE_MONTHS, len(months) - MIN_SIDE_MONTHS + 1):
        before = values[:, :split].mean(axis=1)
        after = values[:, split:].mean(axis=1)
        ratio = np.divide(after, before, out=np.full(n, np.inf), where=before > 0)
        hit = (before > 0) & (ratio <= DECLINE_RATIO) & (ratio < best)
        best = np.where(hit, ratio, best)
        found = np.where(hit, split, found)
        before_at = np.where(hit, before, before_at)
        after_at = np.where(hit, after, after_at)

    stamps = pd.Series(
        [months[i] if i >= 0 else pd.NaT for i in found], index=grid.index)
    return pd.DataFrame({
        "acct": grid.index,
        "decline_month": stamps.values,
        "inflow_before": np.round(before_at, 2),
        "inflow_after": np.round(after_at, 2),
    })[cols].reset_index(drop=True)


def book_monthly(monthly_frame: pd.DataFrame) -> list:
    """Book-level inflow by month: [month, accounts_depositing, dollars]."""
    if monthly_frame is None or not len(monthly_frame):
        return []
    grouped = monthly_frame.groupby("date").agg(
        accounts=("acct", "nunique"), dollars=("dep_amount", "sum"))
    return [[d.strftime("%Y-%m"), int(r.accounts), round(float(r.dollars))]
            for d, r in grouped.sort_index().iterrows()]


def concentration(frame: pd.DataFrame) -> list:
    """Share of all inflow held by the top N% of depositing accounts.

    Depositing accounts, not the whole book: mixing in accounts the file never
    mentions would make the top slice look larger the worse the join got.
    """
    if frame is None or not len(frame):
        return []
    totals = frame.groupby("acct")["dep_amount"].sum().sort_values(ascending=False)
    grand = float(totals.sum())
    if grand <= 0:
        return []
    rows = []
    for cut in CONCENTRATION_CUTS:
        take = max(1, int(round(len(totals) * cut / 100)))
        share = float(totals.iloc[:take].sum())
        rows.append([f"top {cut}%", take, round(share),
                     round(100 * share / grand, 1)])
    return rows


def distribution(frame: pd.DataFrame) -> list:
    """Annual inflow per account by decile: [decile, accounts, floor, median].

    Deciles rather than a mean, because deposit books are long-tailed and a
    mean sits somewhere almost nobody is.
    """
    if frame is None or not len(frame):
        return []
    totals = frame.groupby("acct")["dep_amount"].sum()
    if not len(totals):
        return []
    labels = pd.qcut(totals.rank(method="first"), 10,
                     labels=list(range(1, 11)))
    rows = []
    for decile, group in totals.groupby(labels, observed=True):
        rows.append([int(decile), int(len(group)), round(float(group.min())),
                     round(float(group.median()))])
    return rows
