# Ported from ARS v5 02-Scripts/core/deposits/behaviour.py at a491b5c (James Gilmore); logic unchanged.
"""Per-account deposit behaviour: rhythm, amount consistency, and windfalls.

There is no direct-deposit flag in the source. A recurring amount on a
fortnightly or monthly cadence is evidence, not a fact, and nothing here emits
a field called `direct_deposit` -- whoever opens the CSV in six months will
read that as the core system's own answer. It is `probable_direct_deposit`,
and the cadence evidence travels beside it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# A fortnightly or monthly rhythm, with the tolerance a real payroll shows:
# a deposit lands early when the date falls on a weekend or holiday.
# Weekly, fortnightly, semi-monthly, monthly. WEEKLY WAS MISSING, and hourly
# staff are commonly paid weekly -- on RALLY's book 98.2% of accounts came back
# with "no recurring deposit", which is not a finding about a credit union, it
# is a rule that could not see a whole class of payroll.
CADENCE_TARGETS = ((7, 2), (14, 3), (15, 3), (30, 4))
# Amounts this consistent are a recurring payment rather than a coincidence.
# Coefficient of variation, so it is scale-free -- a $400 payroll and a $9,000
# one are judged the same way.
# Real pay moves with overtime, hours and bonuses. 0.15 demanded a salary
# accurate to +/-15% every period, which excludes most hourly earners; 0.25
# still means an amount that clearly repeats rather than one that happens to
# recur.
RECURRING_CV = 0.25
MIN_DEPOSITS_FOR_CADENCE = 4
# A deposit this many times the account's own median is a windfall for THAT
# account: a $5,000 deposit is unremarkable on some books and an event on others.
WINDFALL_MULTIPLE = 5.0


def cadence(frame: pd.DataFrame) -> pd.DataFrame:
    """Per account: deposit rhythm, amount consistency, and a probable label.

    Returns acct, n_deposits, median_gap_days, amount_cv, median_amount,
    probable_direct_deposit.

    PROBABLE, never certain. The source carries no direct-deposit flag, so the
    strongest honest claim is "deposits arrive on a payroll-shaped rhythm at a
    consistent amount". A column named direct_deposit would be read as the
    core system's own answer; this one cannot be.
    """
    cols = ["acct", "n_deposits", "median_gap_days", "amount_cv",
            "median_amount", "probable_direct_deposit"]
    if not len(frame):
        return pd.DataFrame(columns=cols)

    ordered = frame.sort_values(["acct", "date"])
    gaps = ordered.groupby("acct")["date"].diff().dt.days

    stats = ordered.assign(gap=gaps).groupby("acct").agg(
        n_deposits=("dep_amount", "size"),
        median_gap_days=("gap", "median"),
        median_amount=("dep_amount", "median"),
        mean_amount=("dep_amount", "mean"),
        sd_amount=("dep_amount", "std"),
    ).reset_index()

    # Scale-free consistency. A zero mean cannot produce a ratio, and an
    # account with one deposit has no spread to measure -- both stay NaN
    # rather than being called perfectly consistent.
    stats["amount_cv"] = np.where(
        stats["mean_amount"] > 0,
        stats["sd_amount"] / stats["mean_amount"].replace(0, np.nan),
        np.nan)

    rhythmic = pd.Series(False, index=stats.index)
    for target, tolerance in CADENCE_TARGETS:
        rhythmic |= (stats["median_gap_days"] - target).abs() <= tolerance
    stats["probable_direct_deposit"] = (
        rhythmic
        & (stats["n_deposits"] >= MIN_DEPOSITS_FOR_CADENCE)
        & (stats["amount_cv"] <= RECURRING_CV))
    return stats[cols]


# The gap bands a payroll actually lands in, as LABELS rather than as the bare
# tolerances `cadence()` tests against.
#
# Fortnightly and semi-monthly are deliberately ONE band. 14 +/- 3 covers
# 11-17 days and 15 +/- 3 covers 12-18; they overlap almost completely, and a
# median gap cannot separate "every two weeks" from "twice a month". Reporting
# them apart would invent a distinction the data does not carry.
CADENCE_BANDS = (
    ("weekly", 5, 9),
    ("fortnightly or semi-monthly", 11, 18),
    ("monthly", 26, 34),
)
# Consistency bands either side of RECURRING_CV, so a reader can see WHICH
# test an account failed: the rhythm or the amount.
CV_BANDS = (
    ("very steady (<= 0.10)", 0.0, 0.10),
    ("steady (0.10 - 0.25)", 0.10, RECURRING_CV),
    ("variable (0.25 - 0.50)", RECURRING_CV, 0.50),
    ("erratic (> 0.50)", 0.50, float("inf")),
)


def cadence_band(gaps: pd.Series, n_deposits: pd.Series) -> pd.Series:
    """Label each account's rhythm, or say why it has none.

    `cadence()` answers yes/no. This answers which band -- the evidence behind
    the verdict. Without it a "probable direct deposit" rate is a conclusion
    with nothing under it, and an implausible rate cannot be diagnosed: a low
    number means something different if accounts are arrhythmic than if they
    are rhythmic but their amounts move.
    """
    out = pd.Series("irregular", index=gaps.index, dtype=object)
    for label, low, high in CADENCE_BANDS:
        out[gaps.between(low, high)] = label
    out[n_deposits < MIN_DEPOSITS_FOR_CADENCE] = "too few deposits"
    out[gaps.isna()] = "too few deposits"
    return out


def cv_band(cv: pd.Series) -> pd.Series:
    """Label amount consistency against the threshold cadence() applies."""
    out = pd.Series("not measurable", index=cv.index, dtype=object)
    for label, low, high in CV_BANDS:
        out[(cv >= low) & (cv < high)] = label
    return out


def milestones(frame: pd.DataFrame, asof: pd.Timestamp) -> pd.DataFrame:
    """Per account: the dated events in its deposit life.

    Returns acct, first_deposit, last_deposit, days_since_last,
    longest_gap_days, n_deposits, total_dollars.

    `asof` is the anchor, never today: re-running an old period has to
    reproduce that period's figures, so "days since last" is measured from the
    month the data ends, not from whenever the script happens to run.
    """
    cols = ["acct", "first_deposit", "last_deposit", "days_since_last",
            "longest_gap_days", "n_deposits", "total_dollars"]
    if not len(frame):
        return pd.DataFrame(columns=cols)

    ordered = frame.sort_values(["acct", "date"])
    gaps = ordered.groupby("acct")["date"].diff().dt.days
    out = ordered.assign(gap=gaps).groupby("acct").agg(
        first_deposit=("date", "min"),
        last_deposit=("date", "max"),
        longest_gap_days=("gap", "max"),
        n_deposits=("dep_amount", "size"),
        total_dollars=("dep_amount", "sum"),
    ).reset_index()
    out["days_since_last"] = (asof - out["last_deposit"]).dt.days
    out["total_dollars"] = out["total_dollars"].round(2)
    return out[cols]


# Three missed cycles, judged against the account's OWN rhythm. A fortnightly
# payroll silent for six weeks has stopped; a monthly one silent for six weeks
# has missed once. A single book-wide day count cannot tell those apart.
STOPPED_GAP_MULTIPLE = 3


def stopped(frame: pd.DataFrame, asof: pd.Timestamp) -> pd.DataFrame:
    """Per account: did an established recurring credit stop.

    Returns acct, median_gap_days, days_since_last, cycles_missed,
    recurring_stopped.

    Only accounts that HAD a rhythm can stop having one. An account that never
    deposited regularly is not flagged -- it has nothing to lose, and flagging
    it is how "no recurring deposit" came to fire on 98.2% of a real book.
    """
    cols = ["acct", "median_gap_days", "days_since_last", "cycles_missed",
            "recurring_stopped", "last_deposit"]
    if not len(frame):
        return pd.DataFrame(columns=cols)

    rhythm = cadence(frame)
    marks = milestones(frame, asof)
    out = rhythm.merge(marks[["acct", "days_since_last", "last_deposit"]],
                       on="acct", how="left")

    had_rhythm = pd.Series(False, index=out.index)
    for target, tolerance in CADENCE_TARGETS:
        had_rhythm |= (out["median_gap_days"] - target).abs() <= tolerance
    had_rhythm &= out["n_deposits"] >= MIN_DEPOSITS_FOR_CADENCE

    gap = out["median_gap_days"].replace(0, np.nan)
    out["cycles_missed"] = (out["days_since_last"] / gap).round(1)
    out["recurring_stopped"] = (
        had_rhythm & (out["cycles_missed"] >= STOPPED_GAP_MULTIPLE)).fillna(False)
    return out[cols]


def windfalls(frame: pd.DataFrame,
              reference: pd.Series | None = None) -> pd.DataFrame:
    """Per account: deposits far above that account's own usual credit.

    Relative to the account, never to the book. A $5,000 deposit is a Tuesday
    on one book and an event on another; only the account's own history says
    which.

    `reference` is the per-account usual credit to judge against, indexed by
    acct -- the dominant stream's median when the caller has it. Without it
    the whole-account median stands, and on a real book that median is a
    small transfer: RALLY read 57% of accounts as having a 5x windfall.
    Accounts absent from `reference` fall back to their own median.
    """
    cols = ["acct", "n_windfalls", "windfall_dollars", "largest_deposit"]
    if not len(frame):
        return pd.DataFrame(columns=cols)
    median = frame.groupby("acct")["dep_amount"].transform("median")
    if reference is not None and len(reference):
        usual = frame["acct"].map(reference)
        median = usual.where(usual.notna() & (usual > 0), median)
    flagged = frame[(median > 0) &
                    (frame["dep_amount"] >= median * WINDFALL_MULTIPLE)]
    out = flagged.groupby("acct").agg(
        n_windfalls=("dep_amount", "size"),
        windfall_dollars=("dep_amount", "sum")).reset_index()
    largest = frame.groupby("acct")["dep_amount"].max().rename("largest_deposit")
    return out.merge(largest, on="acct", how="right").fillna(
        {"n_windfalls": 0, "windfall_dollars": 0.0})[cols]
