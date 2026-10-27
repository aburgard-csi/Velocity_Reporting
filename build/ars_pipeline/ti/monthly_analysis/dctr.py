# Ported from ARS v5 02-Scripts/ars/monthly_analysis/dctr.py at a491b5c (James Gilmore); logic unchanged.
"""Debit Card Take Rate.

Every rate here is `has_debit(base) / len(base)` where `base` is a named
subset. The base is stamped on each result so a wrong denominator is visible
rather than silent -- the failure this guards against is a 30% figure and an
80% figure for the same client, differing only in what they divided by.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.periods import trailing
from ..core.subsets import Subsets, has_debit, is_business, norm, num_col

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

ACCOUNT_AGE_BANDS = [(0, 1, "< 1 yr"), (1, 2, "1-2 yr"), (2, 3, "2-3 yr"),
                     (3, 5, "3-5 yr"), (5, 10, "5-10 yr"), (10, 200, "10+ yr")]
HOLDER_AGE_BANDS = [(18, 25, "18-24"), (25, 35, "25-34"), (35, 45, "35-44"),
                    (45, 55, "45-54"), (55, 65, "55-64"), (65, 120, "65+")]
BALANCE_BANDS = [(-1e18, 0, "<= $0"), (0, 500, "$0-500"), (500, 1000, "$500-1k"),
                 (1000, 2500, "$1k-2.5k"), (2500, 5000, "$2.5k-5k"),
                 (5000, 10000, "$5k-10k"), (10000, 1e18, "$10k+")]


def rate(df: pd.DataFrame) -> float:
    """Take rate for a base, as a percentage."""
    if not len(df):
        return 0.0
    return round(100 * float(has_debit(df).mean()), 1)


def _split(df: pd.DataFrame) -> tuple[int, int]:
    with_debit = int(has_debit(df).sum())
    return with_debit, len(df) - with_debit


def _by_band(df: pd.DataFrame, values: pd.Series, bands) -> list[list]:
    rows = []
    for low, high, label in bands:
        mask = (values >= low) & (values < high)
        seg = df[mask.reindex(df.index, fill_value=False)]
        cards, _ = _split(seg)
        rows.append([label, len(seg), cards, rate(seg)])
    return rows


def compute(subsets: Subsets, config: dict, warn) -> dict:
    """All DCTR cuts. Returns the metrics dict."""
    elig = subsets.eligible
    out: dict = {}

    # ---- DCTR-1 / DCTR-2 / DCTR-3: the three headline rates -----------
    cards, nocards = _split(elig)
    out["dctr_overall"] = rate(elig)
    out["dctr_overall_base"] = "Eligible"
    out["dctr_cards"] = cards
    out["dctr_nocards"] = nocards
    out["take_hist_pct"] = out["dctr_overall"]          # legacy key name

    # DCTR-2 is the methodology slide: the same numerator on Open, to show
    # why Eligible is the right base. 'Open' is whitelisted here only.
    out["dctr_open"] = rate(subsets.open_accounts)
    out["dctr_open_base"] = "Open"
    out["dctr_open_vs_eligible_pp"] = round(out["dctr_overall"] - out["dctr_open"], 1)

    l12m = subsets.l12m_eligible
    l12m_cards, l12m_nocards = _split(l12m)
    out["dctr_l12m"] = rate(l12m)
    out["dctr_l12m_base"] = "Eligible L12M"
    out["take_new_total"] = len(l12m)
    out["take_new_cards"] = l12m_cards
    out["take_new_nocard"] = l12m_nocards
    out["take_new_pct"] = out["dctr_l12m"]
    out["dctr_l12m_vs_hist_pp"] = round(out["dctr_l12m"] - out["dctr_overall"], 1)

    # ---- DCTR-4..7: personal vs business, historical and L12M ---------
    out["dctr_personal"] = rate(subsets.eligible_personal)
    out["dctr_business"] = rate(subsets.eligible_business)
    out["n_dctr_personal"] = len(subsets.eligible_personal)
    out["n_dctr_business"] = len(subsets.eligible_business)

    biz = is_business(l12m)
    out["dctr_personal_l12m"] = rate(l12m[~biz])
    out["dctr_business_l12m"] = rate(l12m[biz])
    out["dctr_personal_trend_pp"] = round(
        out["dctr_personal_l12m"] - out["dctr_personal"], 1)
    out["dctr_business_trend_pp"] = round(
        out["dctr_business_l12m"] - out["dctr_business"], 1)

    # ---- A7.7 / A7.8: the funnel to a debit card ----------------------
    out["dctr_funnel"] = [
        ["Total", len(subsets.total)],
        ["Open", len(subsets.open_accounts)],
        ["Eligible", len(elig)],
        ["With debit", cards],
    ]
    out["dctr_funnel_through_pct"] = round(
        100 * cards / len(subsets.total), 1) if len(subsets.total) else 0.0

    out["dctr_funnel_l12m"] = [
        ["Open L12M", len(subsets.l12m_open)],
        ["Eligible L12M", len(l12m)],
        ["With debit L12M", l12m_cards],
    ]

    # ---- A7.9: eligible vs non-eligible, L12M -------------------------
    non_elig_l12m = subsets.l12m_open.drop(index=l12m.index, errors="ignore")
    out["dctr_noneligible_l12m"] = rate(non_elig_l12m)
    out["n_noneligible_l12m"] = len(non_elig_l12m)

    # ---- DCTR-9 / A7.10: by branch, historical and L12M ---------------
    branch_map = config.get("BranchMapping", {}) or {}
    branch = norm(elig.get("Branch"))
    if branch is not None:
        # group by DISPLAY NAME, never raw code: several codes may share
        # one name (1226, issue #47) and a branch must be ONE row
        from ..core.subsets import branch_names
        branch_l12m = norm(l12m.get("Branch"))
        l12m_rates = {}
        if branch_l12m is not None:
            for name, group in l12m.groupby(
                    branch_names(branch_l12m, branch_map)):
                l12m_rates[str(name)] = rate(group)

        rows = []
        for name, group in elig.groupby(branch_names(branch, branch_map)):
            name = str(name)
            cards_b, _ = _split(group)
            hist = rate(group)
            recent = l12m_rates.get(name)
            rows.append([name, cards_b, len(group), hist, recent,
                         round(recent - hist, 1) if recent is not None else None])
        rows.sort(key=lambda r: -r[2])
        out["take_branch"] = [[r[0], r[1], r[2], r[3]] for r in rows]
        out["dctr_branch_trend"] = rows

        rated = [r for r in rows if r[2] >= 25]
        if rated:
            best = max(rated, key=lambda r: r[3])
            worst = min(rated, key=lambda r: r[3])
            out["dctr_branch_best"] = [best[0], best[3], best[2]]
            out["dctr_branch_worst"] = [worst[0], worst[3], worst[2]]
            out["dctr_branch_spread_pp"] = round(best[3] - worst[3], 1)
        else:
            warn("no branch has 25+ eligible accounts; best/worst suppressed")

        unmapped = sorted({str(c) for c in branch.unique()} - set(branch_map))
        if unmapped and branch_map:
            warn(f"branch codes not in BranchMapping: {unmapped[:10]}")

    # ---- DCTR-10 / A7.12: by account age ------------------------------
    opened = pd.to_datetime(elig.get("Date Opened"), errors="coerce")
    if opened is not None and opened.notna().any():
        anchor_ts = pd.Timestamp(subsets.anchor.year, subsets.anchor.month, 1) \
            + pd.offsets.MonthEnd(0)
        age_years = (anchor_ts - opened).dt.days / 365.2425
        out["dctr_account_age"] = _by_band(elig, age_years, ACCOUNT_AGE_BANDS)

        # A7.15 vintage curve: take rate by year opened
        vintage = []
        for year, group in elig.groupby(opened.dt.year):
            if pd.isna(year):
                continue
            cards_v, _ = _split(group)
            vintage.append([int(year), len(group), cards_v, rate(group)])
        out["dctr_vintage"] = sorted(vintage)

        # Seasonality: take rate by calendar month of opening, all years.
        season = []
        for mon, group in elig.groupby(opened.dt.month):
            if pd.isna(mon):
                continue
            cards_s, _ = _split(group)
            season.append([MONTH_NAMES[int(mon) - 1], len(group), cards_s, rate(group)])
        if season:
            out["dctr_seasonality"] = season
            top = max(season, key=lambda r: r[3]); low = min(season, key=lambda r: r[3])
            out["dctr_seasonality_spread_pp"] = round(top[3] - low[3], 1)

        # Branch x month-opened take rate over the last 12 months, for the
        # branches that open the most accounts. Columns = months, rows =
        # branches, plus a totals row (DECK-GAP: take_branch_monthly).
        if branch is not None and len(l12m):
            months = trailing(subsets.anchor, 12)
            tags = [mo.tag for mo in months]
            l12m_open_month = pd.to_datetime(l12m.get("Date Opened"), errors="coerce")
            l12m_branch = norm(l12m.get("Branch"))
            month_key = l12m_open_month.dt.year * 100 + l12m_open_month.dt.month
            keys = [mo.year * 100 + mo.month for mo in months]
            top_branches = [r[0] for r in sorted(rows, key=lambda r: -r[2])[:8]]
            name_of = lambda code: branch_map.get(str(code), str(code) or "(blank)")
            matrix = []
            for code, group in l12m.groupby(l12m_branch):
                name = name_of(code)
                if name not in top_branches:
                    continue
                cells = []
                for k in keys:
                    sub = group[month_key.loc[group.index] == k]
                    cells.append(rate(sub) if len(sub) else None)
                matrix.append([name, len(group)] + cells)
            matrix.sort(key=lambda r: -r[1])
            totals = []
            for k in keys:
                sub = l12m[month_key == k]
                totals.append(rate(sub) if len(sub) else None)
            out["dctr_monthly_months"] = tags
            out["dctr_branch_monthly"] = matrix
            out["dctr_monthly_totals"] = totals

    # ---- DCTR-11 / A7.11: by holder age -------------------------------
    if "Account Holder Age" in elig.columns:
        holder = pd.to_numeric(elig["Account Holder Age"], errors="coerce")
        valid = holder.between(18, 120)
        out["dctr_holder_age"] = _by_band(elig[valid], holder[valid], HOLDER_AGE_BANDS)
        out["dctr_holder_age_base"] = int(valid.sum())
        excluded = int((~valid).sum())
        if excluded:
            warn(f"holder age: {excluded:,} outside 18-120 excluded from age cuts")

    # ---- DCTR-12: by balance ------------------------------------------
    balance = num_col(elig, "Avg Bal")
    if balance is None or balance.isna().all():
        balance = num_col(elig, "Curr Bal")
    if balance is not None and balance.notna().any():
        out["dctr_balance"] = _by_band(elig, balance, BALANCE_BANDS)

    # ---- DCTR-13: holder age x balance crosstab -----------------------
    if "Account Holder Age" in elig.columns and balance is not None:
        holder = pd.to_numeric(elig["Account Holder Age"], errors="coerce")
        rows = []
        for lo_a, hi_a, age_label in HOLDER_AGE_BANDS:
            age_mask = holder.between(lo_a, hi_a - 0.001)
            row = [age_label]
            for lo_b, hi_b, _ in BALANCE_BANDS:
                cell = elig[age_mask & (balance >= lo_b) & (balance < hi_b)]
                row.append(rate(cell) if len(cell) >= 10 else None)
            rows.append(row)
        out["dctr_holder_balance"] = {
            "columns": [b[2] for b in BALANCE_BANDS],
            "rows": rows,
        }

    # ---- DCTR-8: the summary table every other slide checks against ---
    out["dctr_summary"] = [
        ["All open", len(subsets.open_accounts), *_split(subsets.open_accounts),
         rate(subsets.open_accounts)],
        ["Eligible", len(elig), cards, nocards, out["dctr_overall"]],
        ["Eligible personal", len(subsets.eligible_personal),
         *_split(subsets.eligible_personal), out["dctr_personal"]],
        ["Eligible business", len(subsets.eligible_business),
         *_split(subsets.eligible_business), out["dctr_business"]],
        ["Eligible L12M", len(l12m), l12m_cards, l12m_nocards, out["dctr_l12m"]],
    ]
    return out
