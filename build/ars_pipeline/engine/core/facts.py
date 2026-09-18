"""The fact layer: every account-level quantity, derived once.

Before this module, tenure was derived from Date Opened in ten places, spend
recent/prior in five, Curr Bal / Avg Bal read in seven and months-quiet in
five. Ten derivations of one number are ten chances to drift, and the drift is
invisible because no layer ever holds two of them at the same time.

Nothing here aggregates. Every column is one row per account, on the source
frame's own index, so a condition is a boolean Series over this frame and two
conditions compose with `&` and no reindex.

    facts = build_facts(df, config, anchor)
    facts.frame["tenure_years"]
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .periods import Month, columns_for
from ..core.subsets import branch_names, has_debit, is_business, norm

# Account-shaped id columns, preferred first. "Acct Number" is the hashed id
# the transaction file joins on; "Acct ID" is the ODD's own key and the
# fallback when a client's extract omits the hash.
ID_COLUMNS = ("Acct Number", " Acct Number", "Acct ID", "Account Number")

# The window every lifecycle fact is measured against. Equal to
# ATTRITION_WINDOW_MONTHS in monthly_analysis/attrition.py; the two must stay
# equal or "closed in the window" means two different things.
LIFECYCLE_WINDOW_MONTHS = 12
DAYS_PER_YEAR = 365.2425

# Equal to the constants of the same name in monthly_analysis/retention.py.
RECENT_MONTHS = 3
PRIOR_MONTHS = 3
SLOPE_WINDOW = 6


@dataclass
class Facts:
    """Account-grain facts on the source frame's index."""

    frame: pd.DataFrame
    anchor: Month
    warnings: list[str] = field(default_factory=list)
    # Set by the caller once attrition has computed its hazard curve; None
    # when no bucket carried enough resolved accounts to name a peak.
    peak_tenure_band: tuple[float, float] | None = None
    # Share of accounts that actually matched a row in the deposits file.
    deposit_match_pct: float | None = None


def _account_id(df: pd.DataFrame, warn) -> pd.Series:
    for col in ID_COLUMNS:
        if col in df.columns:
            return norm(df[col]).str.replace(r"\.0$", "", regex=True)
    warn("no account id column (tried " + ", ".join(ID_COLUMNS) +
         "); falling back to the frame index")
    return pd.Series(df.index.astype(str), index=df.index)


def _identity(df: pd.DataFrame, config: dict, frame: pd.DataFrame, warn) -> None:
    frame["account_id"] = _account_id(df, warn)
    # No client file carries a member key today, so entity_id is the account.
    # It exists anyway: every rollup and every member-level condition is
    # written against it once, and lights up unchanged the day a CIF arrives.
    frame["entity_id"] = frame["account_id"]

    if "Branch" in df.columns:
        code = norm(df["Branch"])
        frame["branch_code"] = code
        frame["branch_name"] = branch_names(code, config.get("BranchMapping") or {})
    else:
        warn("no Branch column; branch facts unavailable")
        frame["branch_code"] = pd.Series(pd.NA, index=df.index, dtype="object")
        frame["branch_name"] = pd.Series(pd.NA, index=df.index, dtype="object")


def _lifecycle(df: pd.DataFrame, anchor: Month, frame: pd.DataFrame, warn) -> None:
    """Opened, closed, open-at-anchor, tenure, closed-in-window.

    Measured at the ANCHOR, never at today: re-running an old period must
    reproduce the figures that period produced.
    """
    end = pd.Timestamp(anchor.year, anchor.month, 1) + pd.offsets.MonthEnd(0)
    start_m = anchor.shift(-(LIFECYCLE_WINDOW_MONTHS - 1))
    start = pd.Timestamp(start_m.year, start_m.month, 1)

    opened = (pd.to_datetime(df["Date Opened"], errors="coerce")
              if "Date Opened" in df.columns
              else pd.Series(pd.NaT, index=df.index))
    if "Date Closed" in df.columns:
        closed = pd.to_datetime(df["Date Closed"], errors="coerce")
    else:
        warn("no Date Closed column; every account is treated as open")
        closed = pd.Series(pd.NaT, index=df.index)

    frame["opened"] = opened
    frame["closed"] = closed
    frame["is_open"] = closed.isna() | (closed > end)
    frame["closed_in_window"] = closed.between(start, end)
    frame["tenure_years"] = ((end - opened).dt.days / DAYS_PER_YEAR).round(2)


def _money(df: pd.DataFrame, frame: pd.DataFrame, warn) -> None:
    """Balances and their delta.

    balance_delta stays NaN when either side is absent. Returning 0.0 would
    claim the balance held steady, which is not what missing data means -- the
    same distinction _pct in attrition.py makes for an empty denominator.
    """
    for source, name in (("Curr Bal", "curr_bal"), ("Avg Bal", "avg_bal")):
        if source in df.columns:
            frame[name] = pd.to_numeric(df[source], errors="coerce")
        else:
            warn(f"no {source} column; {name} unavailable")
            frame[name] = pd.Series(np.nan, index=df.index)
    frame["balance_delta"] = frame["curr_bal"] - frame["avg_bal"]


def _consecutive_zeros(values: np.ndarray) -> np.ndarray:
    """Trailing zero-spend months per row, walking back from the newest.

    Trailing, not total: spend nine months ago does not make an account that
    has been silent since then any less silent.
    """
    counts = np.zeros(values.shape[0], dtype=int)
    running = np.ones(values.shape[0], dtype=bool)
    for i in range(values.shape[1] - 1, -1, -1):
        is_zero = values[:, i] <= 0
        counts = np.where(running & is_zero, counts + 1, counts)
        running = running & is_zero
    return counts


def _activity(df: pd.DataFrame, frame: pd.DataFrame, warn) -> None:
    """Spend trajectory: recent against prior, slope, and trailing silence.

    Ratios, not dollars. An absolute threshold flags a large account losing
    0.3% and ignores a small one losing 80%; a ratio means the same thing at
    every spend level.
    """
    null = pd.Series(np.nan, index=df.index)
    needed = RECENT_MONTHS + PRIOR_MONTHS
    spend_cols = columns_for(df.columns, "Spend")
    if len(spend_cols) < needed:
        warn(f"only {len(spend_cols)} monthly Spend columns; activity facts "
             f"need {needed}")
        for name in ("spend_recent", "spend_prior", "spend_ratio",
                     "spend_slope", "spend_slope_pct"):
            frame[name] = null
        frame["months_quiet"] = pd.Series(0, index=df.index, dtype=int)
        return

    matrix = df[spend_cols].apply(pd.to_numeric, errors="coerce").fillna(0).values
    recent = matrix[:, -RECENT_MONTHS:].mean(axis=1)
    prior = matrix[:, -needed:-RECENT_MONTHS].mean(axis=1)

    window = min(SLOPE_WINDOW, matrix.shape[1])
    trailing_m = matrix[:, -window:]
    x_centered = np.arange(window) - np.arange(window).mean()
    denom = float((x_centered ** 2).sum())
    slope = (((trailing_m - trailing_m.mean(axis=1, keepdims=True)) * x_centered)
             .sum(axis=1) / denom) if denom else np.zeros(len(df))

    frame["spend_recent"] = pd.Series(recent, index=df.index)
    frame["spend_prior"] = pd.Series(prior, index=df.index)
    # A zero prior is not a 100% decline, it is an unmeasurable one.
    frame["spend_ratio"] = pd.Series(
        np.divide(recent, prior, out=np.full(len(df), np.nan), where=prior > 0),
        index=df.index)
    frame["spend_slope"] = pd.Series(slope, index=df.index)
    frame["spend_slope_pct"] = pd.Series(
        np.divide(100 * slope, prior, out=np.zeros(len(df)), where=prior > 0),
        index=df.index)
    frame["months_quiet"] = pd.Series(_consecutive_zeros(matrix), index=df.index)


def _programme(df: pd.DataFrame, frame: pd.DataFrame) -> None:
    """Flags the ARS programme already defines. Imported, never re-derived --
    a second has-debit rule is how two chapters come to disagree."""
    frame["has_debit"] = has_debit(df)
    frame["is_business"] = is_business(df)
    for source, name in (("Prod Code", "prod_code"), ("Prod Desc", "prod_desc")):
        frame[name] = (norm(df[source]) if source in df.columns
                       else pd.Series("", index=df.index))
    # ICS is stamped either by the client's own column or by ics_sources.py
    # when it joins the DM and referral lists. Both spellings are accepted.
    for source in ("DM-REF Source", "ICS Account"):
        if source in df.columns:
            frame["ics_source"] = norm(df[source])
            return
    frame["ics_source"] = pd.Series("", index=df.index)


def build_facts(df: pd.DataFrame, config: dict, anchor: Month) -> Facts:
    """Derive every account-level fact once. Never aggregates."""
    warnings: list[str] = []

    def warn(message: str) -> None:
        warnings.append(message)

    frame = pd.DataFrame(index=df.index)
    _identity(df, config, frame, warn)
    _lifecycle(df, anchor, frame, warn)
    _money(df, frame, warn)
    _activity(df, frame, warn)
    _programme(df, frame)
    return Facts(frame=frame, anchor=anchor, warnings=warnings)


def attach_competitors(facts: Facts, rows) -> None:
    """Attach per-account competitor facts from the transaction pipeline.

    The ODD cannot see who else an account pays; only the transaction file
    can. So these columns are OPTIONAL: absent on an ODD-only run, present
    once the TXN pipeline joins. `available()` in the condition layer keys off
    exactly that, which is why an ODD-only run reports "Banking elsewhere" as
    not built instead of quietly scoring without it.

    Absent is not zero. A zero here means the join ran and found nothing --
    a measured finding. No column at all means we never looked.

    rows: [[acct, institution, dollars], ...] -- competition.py's own
    _competitor_accounts, so this layer never re-classifies an institution.
    """
    frame = facts.frame
    dollars = pd.Series(0.0, index=frame.index)
    institutions = pd.Series(0, index=frame.index, dtype=int)

    if rows is not None and len(rows):
        comp = pd.DataFrame(list(rows), columns=["acct", "institution", "dollars"])
        comp["acct"] = comp["acct"].astype(str).str.strip()
        agg = comp.groupby("acct").agg(
            dollars=("dollars", "sum"), institutions=("institution", "nunique"))
        key = frame["account_id"].astype(str)
        dollars = key.map(agg["dollars"]).fillna(0.0)
        institutions = key.map(agg["institutions"]).fillna(0).astype(int)

    frame["competitor_dollars"] = dollars
    frame["competitor_institutions"] = institutions


def deposit_windows(monthly: pd.DataFrame | None):
    """Per-account mean monthly inflow over the recent and the prior window,
    indexed by the upper-cased account key. (None, None) when the file does
    not cover both windows -- a ratio on a partial window is not a trend.

    Shared by the stressor facts and the balance chapter, so 'inflow
    declining' is one calculation wherever it is read.
    """
    if monthly is None or not len(monthly):
        return None, None
    wide = monthly.pivot(index="acct", columns="date", values="dep_amount")
    wide = wide.reindex(sorted(wide.columns), axis=1).fillna(0.0)
    if wide.shape[1] < RECENT_MONTHS + PRIOR_MONTHS:
        return None, None
    wide.index = wide.index.astype(str).str.strip().str.upper()
    recent = wide.iloc[:, -RECENT_MONTHS:].mean(axis=1)
    prior = wide.iloc[:, -(RECENT_MONTHS + PRIOR_MONTHS):-RECENT_MONTHS].mean(axis=1)
    return recent, prior


def inflow_ratio(recent: pd.Series, prior: pd.Series) -> pd.Series:
    """recent / prior, NaN where the prior is zero: an unmeasurable change
    is not a total collapse."""
    return pd.Series(np.where(prior > 0, recent / prior, np.nan),
                     index=recent.index)


def attach_deposits(facts: Facts, cadence: pd.DataFrame,
                    monthly: pd.DataFrame) -> None:
    """Attach per-account deposit facts from the rolling-365 deposits file.

    Optional, exactly like the competitor columns: absent on a run without the
    file, so `available()` reports the deposit conditions as not built rather
    than scoring without them.

    `probable_direct_deposit` is named for what it is. The source carries no
    flag, so a column called `direct_deposit` would be read as the core
    system's answer when it is our inference from rhythm and consistency.

    Deposit recent-vs-prior mirrors the spend windows so deceleration means
    the same thing on both series.
    """
    frame = facts.frame
    # Upper-cased on both sides. RALLY's deposits file carries the account hash
    # in upper-case hex; if the ODD spells the same hash in any other case the
    # join silently matches nothing, and every account then reads as having no
    # deposits -- which is indistinguishable from a finding.
    key = frame["account_id"].astype(str).str.strip().str.upper()

    if cadence is not None and len(cadence):
        c = cadence.set_index(cadence["acct"].astype(str).str.strip().str.upper())
        # astype(bool) before fillna: mapping an object-dtype column and then
        # filling triggers pandas' silent-downcasting deprecation.
        frame["probable_direct_deposit"] = key.map(
            c["probable_direct_deposit"]).astype("boolean").fillna(False).astype(bool)
        frame["deposit_amount_cv"] = key.map(c["amount_cv"])
        frame["deposit_median_amount"] = key.map(c["median_amount"])
        frame["deposit_n"] = key.map(c["n_deposits"]).fillna(0).astype(int)
    else:
        frame["probable_direct_deposit"] = False
        for name in ("deposit_amount_cv", "deposit_median_amount"):
            frame[name] = np.nan
        frame["deposit_n"] = 0

    recent, prior = deposit_windows(monthly)
    recent = key.map(recent) if recent is not None else pd.Series(np.nan, index=frame.index)
    prior = key.map(prior) if prior is not None else pd.Series(np.nan, index=frame.index)
    frame["deposit_recent"] = recent
    frame["deposit_prior"] = prior
    frame["deposit_ratio"] = inflow_ratio(recent, prior)

    # The match rate, recorded so a failed join can never pass for a finding.
    # Reporting how many accounts are in the FILE was not enough: RALLY's file
    # held millions of rows and still joined almost nothing.
    facts.deposit_match_pct = round(
        100 * float((frame["deposit_n"] > 0).mean()), 1) if len(frame) else 0.0
