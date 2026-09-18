"""Reg E opt-in.

Base is ALWAYS Eligible Personal w/Debit. Reg E is consumer-only by
regulation, and the opt-in governs ATM / one-time debit overdraft, so the
population that can meaningfully opt in is personal accounts holding a card.

Three states, not two. An account that never made an election is not the same
as one that declined -- 1441's file carries Y, D and N, and treating D as a
decline understates the opt-in rate and overstates active refusal.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from ..core.periods import Month, columns_for, split_tag, trailing
from ..core.subsets import Subsets, norm

OPT_IN, OPT_OUT, DEFAULT, BLANK, UNMAPPED = "Opt In", "Opt Out", "Default", "No election", "Unmapped"

ACCOUNT_AGE_BANDS = [(0, 1, "< 1 yr"), (1, 2, "1-2 yr"), (2, 3, "2-3 yr"),
                     (3, 5, "3-5 yr"), (5, 10, "5-10 yr"), (10, 200, "10+ yr")]
HOLDER_AGE_BANDS = [(18, 25, "18-24"), (25, 35, "25-34"), (35, 45, "35-44"),
                    (45, 55, "45-54"), (55, 65, "55-64"), (65, 120, "65+")]


def classify(values: pd.Series, config: dict, warn, codes: pd.Series | None = None) -> pd.Series:
    """Map raw Reg E cells to the four canonical states through odd_rows.rege_state: the
    description's wording first (the deck's own reading), then the client's configured
    code sets when the wording is blank or unmapped. Wording nothing covers is reported
    as a POSSIBLE DATA ISSUE and kept as its own state, never folded into a rate."""
    from odd_rows import rege_state_series, REGE_IN, REGE_OUT, REGE_DEFAULT
    states = rege_state_series(codes, values, config)
    unmapped = states.isna()
    if unmapped.any():
        seen = sorted(str(v) for v in pd.Series(values)[unmapped].astype(str).str.strip().unique())[:8]
        warn(f"POSSIBLE DATA ISSUE: {int(unmapped.sum()):,} Reg E cells carry wording no mapping "
             f"covers ({', '.join(seen)}); counted as unmapped, not as any election")
    label = {REGE_IN: OPT_IN, REGE_OUT: OPT_OUT, REGE_DEFAULT: DEFAULT, "": BLANK}
    out = states.map(lambda s: UNMAPPED if s is None else label.get(s, BLANK))
    return out.astype(object)


def _rate(states: pd.Series) -> float:
    """Opt-in as a share of the whole base, including no-election."""
    if not len(states):
        return 0.0
    return round(100 * float((states == OPT_IN).mean()), 1)


def _elected_rate(states: pd.Series) -> float:
    """Opt-in as a share of accounts that made any election."""
    elected = states.isin([OPT_IN, OPT_OUT])
    if not elected.sum():
        return 0.0
    return round(100 * float((states[elected] == OPT_IN).mean()), 1)


def _column_of_record(df: pd.DataFrame, anchor: Month, warn) -> str | None:
    """Latest Reg E column BY PARSED DATE, never alphabetically.

    Alphabetical ordering puts Sep before Oct and was a live bug in the
    legacy pipeline.
    """
    for suffix in ("Reg E Desc", "Reg E Code"):
        exact = f"{anchor.tag} {suffix}"
        if exact in df.columns:
            return exact
    for suffix in ("Reg E Desc", "Reg E Code"):
        cols = columns_for(df.columns, suffix)
        if cols:
            warn(f"no Reg E column for {anchor.tag}; using {cols[-1]}")
            return cols[-1]
    return None


def _by_band(states: pd.Series, values: pd.Series, bands) -> list[list]:
    rows = []
    for low, high, label in bands:
        mask = (values >= low) & (values < high)
        seg = states[mask.reindex(states.index, fill_value=False)]
        rows.append([label, len(seg), int((seg == OPT_IN).sum()), _rate(seg)])
    return rows


def compute(subsets: Subsets, config: dict, warn) -> dict:
    base = subsets.personal_with_debit
    if not len(base):
        warn("Reg E base (eligible personal w/debit) is empty; section skipped")
        return {}

    col = _column_of_record(subsets.total, subsets.anchor, warn)
    if col is None:
        warn("no Reg E columns; section skipped")
        return {}

    code_col = col.replace("Reg E Desc", "Reg E Code")
    codes = base[code_col] if code_col != col and code_col in base.columns else None
    states = classify(base[col], config, warn, codes=codes)
    counts = states.value_counts()

    out = {
        "rege_column": col,
        "rege_base": "Eligible Personal w/Debit",
        "rege_pool": len(base),
        "rege_in": int(counts.get(OPT_IN, 0)),
        "rege_out": int(counts.get(OPT_OUT, 0)),
        "rege_default": int(counts.get(DEFAULT, 0)),
        "rege_no": int(counts.get(BLANK, 0)),
        "rege_unmapped": int(counts.get(UNMAPPED, 0)),
        "rege_pct": _rate(states),
        "rege_pct_of_elected": _elected_rate(states),
    }

    # ---- A8.1: L12M rate ----------------------------------------------
    opened = pd.to_datetime(base.get("Date Opened"), errors="coerce")
    if opened is not None and opened.notna().any():
        recent = opened >= subsets.l12m_start
        out["rege_l12m_pool"] = int(recent.sum())
        out["rege_l12m_pct"] = _rate(states[recent])
        out["rege_l12m_vs_hist_pp"] = round(
            out["rege_l12m_pct"] - out["rege_pct"], 1)

        # ---- A8.2: by vintage -----------------------------------------
        vintage = []
        for year, group in base.groupby(opened.dt.year):
            if pd.isna(year):
                continue
            seg = states.reindex(group.index)
            vintage.append([int(year), len(group),
                            int((seg == OPT_IN).sum()), _rate(seg)])
        out["rege_vintage"] = sorted(vintage)
        out["rege_vintage_pool"] = len(base)

        # ---- A8.3: monthly, last 12 open-months -----------------------
        monthly = []
        for m in trailing(subsets.anchor, 12):
            start = pd.Timestamp(m.year, m.month, 1)
            end = start + pd.offsets.MonthEnd(0)
            seg = states[(opened >= start) & (opened <= end)]
            if len(seg):
                monthly.append([m.tag, len(seg),
                                int((seg == OPT_IN).sum()), _rate(seg)])
        out["rege_monthly"] = monthly

        # ---- A8.12: 24-month trend + slope ----------------------------
        trend = []
        for m in trailing(subsets.anchor, 24):
            start = pd.Timestamp(m.year, m.month, 1)
            end = start + pd.offsets.MonthEnd(0)
            seg = states[(opened >= start) & (opened <= end)]
            if len(seg) >= 5:
                trend.append([m.tag, len(seg), _rate(seg)])
        out["rege_trend_24m"] = trend
        if len(trend) >= 3:
            y = np.array([t[2] for t in trend], dtype=float)
            slope = float(np.polyfit(np.arange(len(y)), y, 1)[0])
            out["rege_trend_slope_pp_per_mo"] = round(slope, 2)

        # ---- A8.5: by account age -------------------------------------
        anchor_ts = pd.Timestamp(subsets.anchor.year, subsets.anchor.month, 1) \
            + pd.offsets.MonthEnd(0)
        age_years = (anchor_ts - opened).dt.days / 365.2425
        out["rege_account_age"] = _by_band(states, age_years, ACCOUNT_AGE_BANDS)

    # ---- A8.6: by holder age ------------------------------------------
    if "Account Holder Age" in base.columns:
        holder = pd.to_numeric(base["Account Holder Age"], errors="coerce")
        valid = holder.between(18, 120)
        out["rege_holder_age"] = _by_band(states[valid], holder[valid],
                                          HOLDER_AGE_BANDS)

    # ---- A8.4: by branch ----------------------------------------------
    branch_map = config.get("BranchMapping", {}) or {}
    branch = norm(base.get("Branch"))
    if branch is not None:
        # by display name -- codes sharing a name merge to one row (#47)
        from ..core.subsets import branch_names
        rows = []
        for name, group in base.groupby(branch_names(branch, branch_map)):
            seg = states.reindex(group.index)
            rows.append([str(name),
                         int((seg == OPT_IN).sum()), len(group), _rate(seg)])
        rows.sort(key=lambda r: -r[2])
        out["rege_branch"] = rows
        rated = [r for r in rows if r[2] >= 25]
        if rated:
            best = max(rated, key=lambda r: r[3])
            worst = min(rated, key=lambda r: r[3])
            out["rege_branch_best"] = [best[0], best[3], best[2]]
            out["rege_branch_worst"] = [worst[0], worst[3], worst[2]]
            out["rege_branch_spread_pp"] = round(best[3] - worst[3], 1)

    # ---- A8.7: by product ---------------------------------------------
    prod = norm(base.get("Prod Desc"))
    if prod is None:
        prod = norm(base.get("Prod Code"))
    if prod is not None:
        rows = []
        for code, group in base.groupby(prod):
            seg = states.reindex(group.index)
            rows.append([str(code) or "(blank)", len(group),
                         int((seg == OPT_IN).sum()), _rate(seg)])
        rows.sort(key=lambda r: -r[1])
        out["rege_product"] = rows[:15]

    # ---- A8.10 / A8.11: the funnel ------------------------------------
    out["rege_funnel"] = [
        ["Open", len(subsets.open_accounts)],
        ["Eligible", len(subsets.eligible)],
        ["Eligible w/debit", len(subsets.eligible_with_debit)],
        ["Personal w/debit", len(base)],
        ["Opted in", out["rege_in"]],
    ]
    return out
