# Ported from ARS v5 02-Scripts/ars/monthly_analysis/rege.py at a491b5c (James Gilmore); logic unchanged.
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

OPT_IN, OPT_OUT, DEFAULT, BLANK = "Opt In", "Opt Out", "Default", "No election"

# Fallback patterns, used only for values the config doesn't name. Cores word
# this differently: "Opt-In Accepted" / "Opt-In Declined" / "No Response
# Recevied" (sic) in one, "Y" / "N" / "D" in another.
_OUT_RE = re.compile(r"declin|opt.?out|refus|\bn\b|\bno\b", re.I)
_IN_RE = re.compile(r"accept|opt.?in|\by\b|\byes\b", re.I)
_DEF_RE = re.compile(r"default|no.?response|no.?elect|recevied|\bd\b", re.I)

ACCOUNT_AGE_BANDS = [(0, 1, "< 1 yr"), (1, 2, "1-2 yr"), (2, 3, "2-3 yr"),
                     (3, 5, "3-5 yr"), (5, 10, "5-10 yr"), (10, 200, "10+ yr")]
HOLDER_AGE_BANDS = [(18, 25, "18-24"), (25, 35, "25-34"), (35, 45, "35-44"),
                    (45, 55, "45-54"), (55, 65, "55-64"), (65, 120, "65+")]


def _code_key(value) -> str:
    """A code's identity, free of how the extract spells a number.

    One core delivers a Reg E code as "1", another as "1.0", and the config
    carries whichever spelling the client's code sheet happened to hold.
    Matching on the literal string means a config rebuild that drops a
    hand-added "1.0" silently stops classifying those rows -- they fall
    through to pattern matching and the opt-in rate undercounts. The variant
    is defensive, and RegEOptInCode is a CODE_SHEET_FIELD, so a rebuild
    wipes it (#174).

    Non-numeric codes -- "Y", "OPT IN" -- are returned unchanged.
    """
    v = str(value).strip().upper()
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return str(int(f)) if f == int(f) else str(f)


def classify(values: pd.Series, config: dict, warn) -> pd.Series:
    """Map raw Reg E values to the four canonical states."""
    literal_in = {str(c).strip().upper() for c in config.get("RegEOptInCode", [])}
    opt_in = {_code_key(c) for c in config.get("RegEOptInCode", [])}
    opt_out = {_code_key(c) for c in config.get("RegEOptOutCode", [])}
    default = {_code_key(c) for c in config.get("RegEDefaultCode", [])}

    raw = norm(values)
    upper = raw.str.upper()
    keyed = upper.map(_code_key)
    out = pd.Series(BLANK, index=values.index, dtype=object)

    out[keyed.isin(opt_in) & (upper != "")] = OPT_IN
    if opt_out:
        out[keyed.isin(opt_out)] = OPT_OUT
    if default:
        out[keyed.isin(default)] = DEFAULT

    # Matching on identity rather than spelling can only ADD matches that a
    # literal comparison missed. Say how many, so the opt-in rate never moves
    # without the run reporting why it moved.
    recovered = int(((keyed.isin(opt_in)) & (~upper.isin(literal_in))
                     & (upper != "")).sum())
    if recovered:
        warn(f"Reg E: {recovered:,} row(s) matched an opt-in code by value "
             f"rather than by spelling (the file writes it one way, "
             f"clients_config another). They were previously unclassified and "
             f"the opt-in rate rises by that much")

    # Anything still unclassified and non-blank: pattern match, then report.
    # Masks must stay on the FULL index -- filtering to a subset and combining
    # with a full-index mask silently evaluates to False everywhere.
    unresolved = (out == BLANK) & (upper != "")
    if unresolved.any():
        def matches(pattern) -> pd.Series:
            m = upper.str.contains(pattern, na=False)
            return m.reindex(out.index, fill_value=False)

        out[unresolved & matches(_DEF_RE)] = DEFAULT
        still = (out == BLANK) & (upper != "")
        out[still & matches(_OUT_RE)] = OPT_OUT
        still = (out == BLANK) & (upper != "")
        out[still & matches(_IN_RE)] = OPT_IN

        inferred = sorted(set(upper[unresolved].unique()))
        unmatched = sorted(set(upper[(out == BLANK) & (upper != "")].unique()))
        if unmatched:
            warn(f"Reg E values matched no rule, counted as no-election: "
                 f"{unmatched[:8]}")
        resolved_by_pattern = [v for v in inferred if v not in unmatched]
        if resolved_by_pattern:
            warn(f"Reg E values classified by pattern, not config: "
                 f"{resolved_by_pattern[:8]}. Add RegEOptOutCode / "
                 f"RegEDefaultCode to clients_config.json to make this explicit.")
    return out


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
    for suffix in ("Reg E Code", "Reg E Desc"):
        exact = f"{anchor.tag} {suffix}"
        if exact in df.columns:
            return exact
    for suffix in ("Reg E Code", "Reg E Desc"):
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

    states = classify(base[col], config, warn)
    counts = states.value_counts()

    out = {
        "rege_column": col,
        "rege_base": "Eligible Personal w/Debit",
        "rege_pool": len(base),
        "rege_in": int(counts.get(OPT_IN, 0)),
        "rege_out": int(counts.get(OPT_OUT, 0)),
        "rege_default": int(counts.get(DEFAULT, 0)),
        "rege_no": int(counts.get(BLANK, 0)),
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
