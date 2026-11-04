"""
Branch-level deposit-behaviour and overdraft metrics.

Carried over from the branch-analysis tool (3Rivers / Clearview / Broadview /
RBFCU reviews), reworked to take the shared loaded frame and to be generic in
account type rather than having Personal and Business paths.

Every function returns a tidy per-branch DataFrame with an `n` column (open
accounts at that branch), so `top_branches` can rank consistently.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from .ils_data import num, open_accounts

# ── selection ───────────────────────────────────────────────────────────────


def top_branches(df, value_col, n, *, ascending_for_chart=True):
    """Top `n` branches by account count, re-sorted for chart rendering.

    PowerPoint (and Excel) bar charts plot the first category at the bottom, so
    values are returned ascending — that puts the largest bar at the top, which
    is how every deck in this series is read.
    """
    top = df.sort_values("n", ascending=False).head(n)
    top = top.dropna(subset=[value_col])
    top = top.sort_values(value_col, ascending=ascending_for_chart)
    return top["branchname"].tolist(), top[value_col].tolist()


def _presented_item(df):
    """Presented a fee-triggering item: paid-into-overdraft or returned, 365d."""
    pd_365 = num(df.get("PD_365")).fillna(0) if "PD_365" in df else pd.Series(0.0, index=df.index)
    rt_365 = num(df.get("RT_365")).fillna(0) if "RT_365" in df else pd.Series(0.0, index=df.index)
    return (pd_365 + rt_365) > 0


# ── deposit intensity & engagement ──────────────────────────────────────────
def deposit_intensity_engagement(za, accttype):
    """Per-branch average 33-day deposit per account, and % with no deposit."""
    sub = open_accounts(za, accttype).copy()
    sub["DepAmt33"] = num(sub["DepAmt33"]) if "DepAmt33" in sub else np.nan
    g = sub.groupby(["branch", "branchname"], observed=True).agg(
        n=("acctid", "count"),
        total_dep33=("DepAmt33", lambda s: s.fillna(0).sum()),
        null_dep33=("DepAmt33", lambda s: s.isna().sum()),
    ).reset_index()
    g["avg_dep_per_acct"] = (g["total_dep33"] / g["n"]).round(2)
    g["pct_no_deposit"] = (g["null_dep33"] / g["n"] * 100).round(1)
    return g.sort_values("n", ascending=False)


# ── overdraft / NSF activity ────────────────────────────────────────────────
def overdraft_activity(za, accttype):
    """Per-branch OD/NSF activity among accounts that presented an item.

    avg_fee_per_user   fees collected from presenting accounts / presenting accounts
    pct_presented      presenting accounts / all open accounts at the branch
    """
    sub = open_accounts(za, accttype).copy()
    sub["CollectedFees365"] = num(sub.get("CollectedFees365")).fillna(0) \
        if "CollectedFees365" in sub else 0.0
    sub["presented"] = _presented_item(sub)

    total = sub.groupby(["branch", "branchname"], observed=True).size().reset_index(name="n")
    qual = sub[sub["presented"]]
    n_pres = qual.groupby(["branch", "branchname"], observed=True).size() \
                 .reset_index(name="n_presented")
    fees = qual.groupby(["branch", "branchname"], observed=True)["CollectedFees365"].sum() \
               .reset_index(name="fee_income")

    g = (total.merge(n_pres, on=["branch", "branchname"], how="left")
              .merge(fees, on=["branch", "branchname"], how="left"))
    g["n_presented"] = g["n_presented"].fillna(0).astype(int)
    g["fee_income"] = g["fee_income"].fillna(0.0)
    g["pct_presented"] = (g["n_presented"] / g["n"] * 100).round(1)
    g["avg_fee_per_user"] = np.where(g["n_presented"] > 0,
                                     (g["fee_income"] / g["n_presented"]).round(2), np.nan)
    return g.sort_values("n", ascending=False)


# ── deposit volatility (needs ztrend) ───────────────────────────────────────
def account_level_cv(ztrend, min_periods=8):
    """Per-account coefficient of variation of the rolling 33-day deposit total."""
    if ztrend is None or "deptotal33" not in ztrend.columns:
        return None
    stats = ztrend.groupby("acctid")["deptotal33"].agg(["count", "mean", "std"]).reset_index()
    stats = stats[(stats["count"] >= min_periods) & (stats["mean"] > 0)]
    stats["cv"] = stats["std"] / stats["mean"]
    return stats[["acctid", "cv", "count"]]


def deposit_volatility(za, ztrend, accttype, min_periods=8, *, cv=None):
    """Per-branch median CV among accounts with enough history to compute one."""
    cv = cv if cv is not None else account_level_cv(ztrend, min_periods)
    if cv is None or cv.empty:
        return None
    merged = open_accounts(za, accttype).merge(cv, on="acctid", how="inner")
    if merged.empty:
        return None
    g = merged.groupby(["branch", "branchname"], observed=True).agg(
        n=("acctid", "count"),
        median_cv=("cv", "median"),
    ).reset_index()
    g["median_cv"] = g["median_cv"].round(3)
    return g.sort_values("n", ascending=False)


# ── account growth & deposit activation ─────────────────────────────────────
def account_growth(za, year, accttype="Personal"):
    """New accounts opened in `year` and the share that funded (deposited since)."""
    df = za
    opened = df[df["in_branch_scope"] & (df["accttype"] == accttype)
                & (df["opendate"] >= f"{year}-01-01")
                & (df["opendate"] <= f"{year}-12-31")].copy()
    if opened.empty:
        return None
    opened["depCount365"] = num(opened.get("depCount365")).fillna(0) \
        if "depCount365" in opened else 0
    opened["made_deposit"] = opened["depCount365"] > 0
    opened["still_open"] = opened["acctstatus"].astype(str).str.upper() == "O"

    g = opened.groupby(["branch", "branchname"], observed=True).agg(
        new_accounts=("acctid", "count"),
        made_deposit=("made_deposit", "sum"),
        still_open=("still_open", "sum"),
    ).reset_index()
    g["n"] = g["new_accounts"]
    g["pct_made_deposit"] = (g["made_deposit"] / g["new_accounts"] * 100).round(1)
    g["pct_still_open"] = (g["still_open"] / g["new_accounts"] * 100).round(1)
    return g.sort_values("new_accounts", ascending=False)


def latest_full_year(za, snapshot):
    """The most recent calendar year with a full year of openings behind it."""
    if "opendate" not in za.columns:
        return snapshot.year - 1
    years = za["opendate"].dt.year.dropna()
    if years.empty:
        return snapshot.year - 1
    return int(min(snapshot.year - 1, years.max()))


# ── deposit-health tiers (box-plot input; needs ztrend) ─────────────────────
@dataclass
class DepositHealthTiers:
    labels: list
    fee_arrays: list
    ns: list
    means: list
    medians: list


def deposit_health_tiers(za, ztrend, accttype="Personal", min_periods=8, *, cv=None):
    """OD fee distribution split by no-deposit activity and volatility tercile."""
    cv = cv if cv is not None else account_level_cv(ztrend, min_periods)
    if cv is None or cv.empty:
        return None
    sub = open_accounts(za, accttype).copy()
    sub["CollectedFees365"] = num(sub.get("CollectedFees365")).fillna(0) \
        if "CollectedFees365" in sub else 0.0
    sub["DepAmt33"] = num(sub["DepAmt33"]) if "DepAmt33" in sub else np.nan

    merged = sub.merge(cv, on="acctid", how="left")
    no_dep = merged["DepAmt33"].isna()
    withcv = merged[merged["cv"].notna()].copy()
    if len(withcv) < 30:
        return None
    try:
        withcv["vol_tier"] = pd.qcut(withcv["cv"], 3, labels=["low", "mod", "high"])
    except ValueError:
        return None

    groups = [
        ("No deposit activity", merged.loc[no_dep, "CollectedFees365"].values),
        ("High volatility (erratic)", withcv.loc[withcv["vol_tier"] == "high", "CollectedFees365"].values),
        ("Moderate volatility", withcv.loc[withcv["vol_tier"] == "mod", "CollectedFees365"].values),
        ("Low volatility (stable)", withcv.loc[withcv["vol_tier"] == "low", "CollectedFees365"].values),
    ]
    labels = [g[0] for g in groups]
    arrays = [np.asarray(g[1], dtype=float) for g in groups]
    return DepositHealthTiers(
        labels=labels, fee_arrays=arrays, ns=[len(a) for a in arrays],
        means=[float(np.mean(a)) if len(a) else 0.0 for a in arrays],
        medians=[float(np.median(a)) if len(a) else 0.0 for a in arrays],
    )


# ── repayment-trend segment ─────────────────────────────────────────────────
@dataclass
class RepaymentSegment:
    n_item_active: int
    n_qualifying: int
    pct_of_item_active: float
    band_labels: list
    band_counts: list
    median_repayment_days: Optional[float]
    pct_within_10_days: Optional[float]
    median_od_limit: Optional[float]
    median_negative_balance: Optional[float]
    pct_negative_balance: Optional[float]
    direct_field_populated: bool


def repayment_trend_segment(za, accttype="Personal"):
    """Accounts with item activity and a computable repayment rate.

    `avgrepaymentrate is not null` is the working proxy for a trend fire:
    RepaymentTrendCount33, the intended direct counter, has been empty in every
    extract seen. The proxy vs. direct status is reported so the slide can say
    which one it used.
    """
    sub = open_accounts(za, accttype).copy()
    if "avgrepaymentrate" not in sub.columns or "items365" not in sub.columns:
        return None
    items = num(sub["items365"]).fillna(0)
    rate = num(sub["avgrepaymentrate"])
    item_active = sub[items > 0]
    if item_active.empty:
        return None
    qual = item_active[num(item_active["avgrepaymentrate"]).notna()]
    if qual.empty:
        return None

    q_rate = num(qual["avgrepaymentrate"])
    bins = [-np.inf, 3, 7, 14, 30, np.inf]
    labels = ["≤ 3", "4–7", "8–14", "15–30", "30 +"]
    banded = pd.cut(q_rate, bins=bins, labels=labels)
    counts = [int((banded == l).sum()) for l in labels]

    odl = num(qual.get("ODLimit")) if "ODLimit" in qual else pd.Series(dtype=float)
    bal_col = "AvgCollectedBalance" if "AvgCollectedBalance" in qual else "balance"
    bal = num(qual.get(bal_col)) if bal_col in qual else pd.Series(dtype=float)
    neg = bal[bal < 0]

    direct = False
    if "RepaymentTrendCount33" in za.columns:
        direct = bool(num(za["RepaymentTrendCount33"]).fillna(0).gt(0).any())

    return RepaymentSegment(
        n_item_active=len(item_active),
        n_qualifying=len(qual),
        pct_of_item_active=round(len(qual) / len(item_active) * 100, 1),
        band_labels=labels,
        band_counts=counts,
        median_repayment_days=float(q_rate.median()) if q_rate.notna().any() else None,
        pct_within_10_days=round(float((q_rate <= 10).mean() * 100), 1)
        if q_rate.notna().any() else None,
        median_od_limit=float(odl.median()) if len(odl) and odl.notna().any() else None,
        median_negative_balance=float(neg.median()) if len(neg) else None,
        pct_negative_balance=round(float((bal < 0).mean() * 100), 1)
        if len(bal) and bal.notna().any() else None,
        direct_field_populated=direct,
    )


# ── portfolio roll-up (KPI cards) ───────────────────────────────────────────
def portfolio_summary(za, accttype):
    sub = open_accounts(za, accttype).copy()
    if sub.empty:
        return None
    dep = num(sub["DepAmt33"]) if "DepAmt33" in sub else pd.Series(dtype=float)
    fees = num(sub.get("CollectedFees365")).fillna(0) if "CollectedFees365" in sub \
        else pd.Series(0.0, index=sub.index)
    presented = _presented_item(sub)
    users = fees[presented]
    odl = num(sub.get("ODLimit")) if "ODLimit" in sub else pd.Series(dtype=float)
    return {
        "n_open": int(len(sub)),
        "n_branches": int(sub["branch"].nunique()),
        "avg_dep_per_acct": float(dep.fillna(0).mean()) if len(dep) else 0.0,
        "pct_no_deposit": round(float(dep.isna().mean() * 100), 1) if len(dep) else 0.0,
        "pct_presented": round(float(presented.mean() * 100), 1),
        "n_presented": int(presented.sum()),
        "fee_income": float(fees.sum()),
        "avg_fee_per_user": float(users.mean()) if len(users) else None,
        "median_od_limit": float(odl.median()) if len(odl) and odl.notna().any() else None,
    }
