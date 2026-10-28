# Ported from the ILS Kickoff Day 2 app (M:\JBerkowitz\ILS Kickoff Day 2 app\ils_kickoff\metrics.py and narrative.py, v1.0), the analysis only. Rewritten to this pipeline's conventions: canonical columns from ..core.io, segments pre-filtered by CodeConfig, and no guessed codes.
"""Day 2 analyses: what the Day 2 report-out deck reads off the one-time file
that the kickoff workbook did not.

  - highlights:      the numbers the Day 2 `Note:` lines are built from --
                     user share against the CFPB benchmark, how few accounts
                     carry 75% of the items, pay ratio against target and its
                     shape across the NSF bands, OD-eligible share against the
                     80% floor, Reg E opt-in against the user base, and the
                     opt-ins that are not on an eligible code
  - od_status_rege:  the OD status table, scoped to Reg E opt-ins
  - year_opened:     accounts by year opened, open vs not open (churn by cohort)
  - rege_by_year:    Reg E flag mix and opt-in rate by year opened

The Day 2 app guessed what it was not told: an OD status containing "activ"
was eligible, a Reg E value of "Y" or "1" was an opt-in, and when nothing
matched, the largest code was assumed eligible. Here eligibility is
codes.eligible_stat_codes and opt-in is codes.rege_opt_in, exactly as the rest
of the kickoff run, and a measure that needs an unconfirmed code is left blank
and says why rather than reading a guess.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.io import (
    ACCT_NO, ACCOUNT_STATUS, BUSINESS_FLAG, DEPOSIT_AMOUNT, OPEN_DATE,
    PAID_ITEMS, REG_E_FLAG, STAT_CODE, TOTAL_ITEMS, CodeConfig,
)
from . import nsf_strat, od_status
from ._common import append_grand_total

# Referenced, not recomputed: the house decks compare against these.
CFPB_USER_RATE = 0.27        # 2012 CFPB study, larger banks and credit unions
ELIGIBILITY_TARGET = 0.80
ELIGIBILITY_PREFERRED = 0.90
PAY_RATIO_TARGET = 0.90

YEARS_SHOWN = 15             # cohorts older than this share one "<year" row


# ---- helpers --------------------------------------------------------------

def _opted_in(d: pd.DataFrame, codes: CodeConfig) -> pd.Series:
    return d[REG_E_FLAG].astype(str).isin([str(v) for v in codes.rege_opt_in])


def trend(table: pd.DataFrame, column: str, *, floor: float = 0.12) -> str:
    """'up' | 'down' | 'flat' across the NSF bands, ignoring the Grand Total.

    Compares the mean of the bottom third of bands with the top third rather
    than fitting a line: the bands are ordinal, not numeric, and '49+' is
    open-ended.
    """
    if table is None or column not in table.columns:
        return "flat"
    vals = [v for v in table[table.iloc[:, 0] != "Grand Total"][column].tolist()
            if pd.notna(v)]
    if len(vals) < 4:
        return "flat"
    k = max(1, len(vals) // 3)
    lo, hi = sum(vals[:k]) / k, sum(vals[-k:]) / k
    if not lo:
        return "up" if hi else "flat"
    change = (hi - lo) / abs(lo)
    return "up" if change > floor else "down" if change < -floor else "flat"


def _benchmark(share: float) -> str:
    ratio = share / CFPB_USER_RATE
    if ratio >= 1.15:
        return "higher than the CFPB 2012 study"
    if ratio >= 0.95:
        return "in line with the CFPB 2012 study"
    if ratio >= 0.6:
        return "slightly lower than the CFPB 2012 study"
    return f"about {ratio:.0%} of the CFPB 2012 study"


def _years(d: pd.DataFrame, first_year: int | None):
    """(binned year Series, cutoff, last year) for rows with a parseable Open Date, or None."""
    if OPEN_DATE not in d.columns or not len(d):
        return None
    years = pd.to_datetime(d[OPEN_DATE], errors="coerce").dt.year.dropna().astype(int)
    if not len(years):
        return None
    last = int(years.max())
    cutoff = first_year or max(int(years.min()), last - YEARS_SHOWN)
    return years.where(years >= cutoff, cutoff - 1), cutoff, last


def _label(y: int, cutoff: int) -> str:
    return f"<{cutoff}" if y == cutoff - 1 else str(y)


# ---- the analyses ---------------------------------------------------------

def highlights(segment_df: pd.DataFrame, codes: CodeConfig, segment: str) -> pd.DataFrame:
    """One row per Day 2 finding for one segment: Segment | Measure | Value | Unit | Benchmark | Read.

    segment_df: pre-filtered to open + personal (or business).
    Percentages are 0-100, as everywhere else in the workbook.
    """
    rows: list[dict] = []

    def add(measure, value, unit, benchmark="", read=""):
        rows.append({"Segment": segment, "Measure": measure,
                     "Value": None if value is None else round(float(value), 2),
                     "Unit": unit, "Benchmark": benchmark, "Read": read})

    d = segment_df
    n = len(d)
    add("Open accounts", n, "accounts")
    if not n:
        return pd.DataFrame(rows)

    items = d[TOTAL_ITEMS].fillna(0)
    total_items = float(items.sum())
    users = int((items > 0).sum())
    user_share = users / n
    add("Accounts with 1+ OD/NSF item", users, "accounts")
    add("OD/NSF user share", user_share * 100, "%", f"{CFPB_USER_RATE:.0%} (CFPB 2012)",
        _benchmark(user_share))

    if total_items:
        # Concentration: how few accounts generate 75% of all items.
        cum = np.cumsum(np.sort(items.values)[::-1]) / total_items
        k = int(np.searchsorted(cum, 0.75) + 1)
        add("Accounts generating 75% of items", k, "accounts")
        add("Share of accounts generating 75% of items", k / n * 100, "%", "",
            "Manage the frequent users of overdraft liquidity")

        pay = float(d[PAID_ITEMS].fillna(0).sum()) / total_items
        level = "high" if pay >= 0.85 else "moderate" if pay >= 0.65 else "low"
        add("Pay ratio", pay * 100, "%", f"{PAY_RATIO_TARGET:.0%}+ with dynamic limits",
            f"{level} across the base of accounts")

        strat = nsf_strat.compute(d, level="pay_ratio")
        shape = trend(strat, "Pay Ratio")
        add("Pay ratio across NSF bands", None, "trend", "rises with usage",
            {"up": "rises with usage -- the heaviest users are the ones being paid",
             "down": "falls as usage rises -- limits are not tracking ability to repay",
             "flat": "flat across the bands"}[shape])
        if DEPOSIT_AMOUNT in d.columns:
            full = nsf_strat.compute(d, level="full")
            dep = trend(full, "Avg $$ Dep/Month")
            add("Deposits across NSF bands", None, "trend", "rises with usage",
                {"up": "deposits rise with overdraft usage, as expected",
                 "down": "deposits fall as usage rises -- the usual relationship is inverted",
                 "flat": "no deposit lift with usage -- often a small frequent-user "
                         "population skewing the averages"}[dep])

    eligible = codes.is_eligible(d[STAT_CODE])
    share = float(eligible.mean())
    if share >= ELIGIBILITY_PREFERRED:
        read = "where we want it"
    elif share >= ELIGIBILITY_TARGET:
        read = "above the 80% floor, short of the 90% preferred"
    else:
        read = "below the 80% floor"
    if eligible.all() or not eligible.any():
        read = (f"Stat Code(s) {codes.eligible_stat_codes} matched "
                f"{'every' if eligible.all() else 'no'} account -- not meaningful until confirmed")
    add("OD-eligible share", share * 100, "%",
        f"{ELIGIBILITY_TARGET:.0%} floor, {ELIGIBILITY_PREFERRED:.0%} preferred", read)

    if not codes.rege_opt_in:
        add("Reg E opt-in share", None, "%", "", "Reg E opt-in value not confirmed -- not computed")
        return pd.DataFrame(rows)
    opted = _opted_in(d, codes)
    rege_share = float(opted.mean())
    if segment.lower().startswith("bus"):
        rege_read = "not required for business, but opting in removes the debit-card exclusion"
    else:
        rege_read = f"{'behind' if rege_share < user_share else 'ahead of'} the OD/NSF user share"
    add("Reg E opt-in share", rege_share * 100, "%", "", rege_read)

    stranded = d[opted & ~eligible]
    top = stranded[STAT_CODE].astype(str).value_counts()
    add("Reg E opt-ins not OD-eligible", len(stranded), "accounts", "0",
        (f"opted in but receiving no limit; most are Stat Code '{top.index[0]}' ({top.iloc[0]:,})"
         if len(stranded) else "opt-in and eligibility are aligned"))
    return pd.DataFrame(rows)


def od_status_rege(segment_df: pd.DataFrame, codes: CodeConfig) -> pd.DataFrame | None:
    """The OD status table over the segment's Reg E opt-ins. None when opt-in is unconfirmed or matches nobody."""
    if not codes.rege_opt_in:
        return None
    d = segment_df[_opted_in(segment_df, codes)]
    if not len(d):
        return None
    return od_status.compute(d)


def year_opened(df: pd.DataFrame, codes: CodeConfig, business_code: str,
                first_year: int | None = None) -> pd.DataFrame | None:
    """Accounts by year opened, open vs not open, for one segment across every status.

    Deliberately not scoped to open accounts: the point is the ratio between
    the two, which is how a book of recently opened accounts churning out shows up.
    """
    d = df[df[BUSINESS_FLAG] == business_code]
    got = _years(d, first_year)
    if got is None:
        return None
    binned, cutoff, last = got
    is_open = (d.loc[binned.index, ACCOUNT_STATUS] == codes.open_status_code)

    rows = []
    for y in range(cutoff - 1, last + 1):
        m = binned == y
        n_open, n_not = int((m & is_open).sum()), int((m & ~is_open).sum())
        if n_open + n_not == 0 and y == cutoff - 1:
            continue
        rows.append({"Year Opened": _label(y, cutoff), "Open": n_open, "Not Open": n_not,
                     "Total": n_open + n_not,
                     "% Not Open": round(n_not / (n_open + n_not) * 100, 2) if n_open + n_not else 0.0})
    table = pd.DataFrame(rows)
    n_open, n_not = int(is_open.sum()), int((~is_open).sum())
    return append_grand_total(table, "Year Opened", {
        "Open": n_open, "Not Open": n_not, "Total": n_open + n_not,
        "% Not Open": round(n_not / (n_open + n_not) * 100, 2) if n_open + n_not else 0.0,
    })


def rege_by_year(segment_df: pd.DataFrame, codes: CodeConfig,
                 first_year: int | None = None) -> pd.DataFrame | None:
    """Reg E flag counts and opt-in rate by year opened. segment_df: open + one segment.

    The "% Opted In" column is present only when codes.rege_opt_in is confirmed.
    """
    got = _years(segment_df, first_year)
    if got is None:
        return None
    binned, cutoff, last = got
    d = segment_df.loc[binned.index]
    flags = d[REG_E_FLAG].astype(str)
    values = sorted(flags.unique())
    opted = _opted_in(d, codes) if codes.rege_opt_in else None

    rows = []
    for y in range(cutoff - 1, last + 1):
        m = binned == y
        n = int(m.sum())
        if not n and y == cutoff - 1:
            continue
        row = {"Year Opened": _label(y, cutoff), "# of Accounts": n}
        for v in values:
            row[f"Reg E {v}"] = int((m & (flags == v)).sum())
        if opted is not None:
            row["% Opted In"] = round(int((m & opted).sum()) / n * 100, 2) if n else 0.0
        rows.append(row)

    grand = {"# of Accounts": len(d), **{f"Reg E {v}": int((flags == v).sum()) for v in values}}
    if opted is not None:
        grand["% Opted In"] = round(float(opted.mean()) * 100, 2) if len(d) else 0.0
    return append_grand_total(pd.DataFrame(rows), "Year Opened", grand)
