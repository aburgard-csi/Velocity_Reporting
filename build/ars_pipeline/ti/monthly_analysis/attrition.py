# Ported from ARS v5 02-Scripts/ars/monthly_analysis/attrition.py at a491b5c (James Gilmore); logic unchanged.
"""Attrition: who leaves, when, and what it costs.

Attrition is measured on closures within a window, against the population
that was open at the start of that window -- not against accounts present in
today's file, which would undercount by excluding everything that already
left.

The retention-lift calculations (debit, mailer) are the ones other sections
consume: they are the bridge from "we issued more cards" to "we kept more
accounts".
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core import account_lenses
from ..core.periods import Month, columns_for, trailing
from ..core.subsets import Subsets, branch_names, has_debit, norm

TENURE_BANDS = [(0, 1, "< 1 yr"), (1, 2, "1-2 yr"), (2, 3, "2-3 yr"),
                (3, 5, "3-5 yr"), (5, 10, "5-10 yr"), (10, 200, "10+ yr")]
# Tenure buckets the closure hazard is measured over, in MONTHS. At module
# level so a per-account "in the peak band" mask can be built from the same
# boundaries this chapter prints -- the alternative is a second copy that
# drifts, which is how five of the six at-risk definitions came to disagree.
HAZARD_BUCKETS = [(0, 6, "0-6 mo"), (6, 12, "6-12 mo"), (12, 24, "1-2 yr"),
                  (24, 36, "2-3 yr"), (36, 60, "3-5 yr"), (60, 120, "5-10 yr")]

BALANCE_BANDS = [(-1e18, 0, "< $0"), (0, 500, "$0-500"), (500, 1000, "$500-1k"),
                 (1000, 2500, "$1k-2.5k"), (2500, 5000, "$2.5k-5k"),
                 (5000, 10000, "$5k-10k"), (10000, 1e18, "$10k+")]

# Cut-offs that decide what this section prints. They were inline numbers,
# which meant two clients with different book shapes got different sections
# and nothing in the output said which cut-off had applied. The module's
# suppression warnings already model the right habit -- say what was dropped
# and why -- so each one carries its reason here, and the two that suppress a
# whole section now warn as the balance cut does.
MIN_MONTHS_FOR_SLOPE = 3          # a line through fewer points is noise
COHORT_MONTHS = 24                # open-month cohorts shown, newest last
MIN_RESOLVED_FOR_PEAK = 50        # naming the peak hazard bucket
MIN_AT_RISK_FOR_BRANCH_RANK = 150 # a small branch swings too hard to rank
MIN_AT_RISK_FOR_PRODUCT = 100     # a product row worth printing
MIN_AT_RISK_FOR_LENS = 100        # a lens row worth printing
MIN_OPENED_FOR_FIRST_YEAR = 30    # first-year close needs a real cohort
MIN_BALANCE_COVERAGE_PCT = 60     # below this the balance cut is not real
MAX_DEBIT_SHARE_GAP_PP = 25       # above this the Debit? flag is cleared on close


def hazard_rows(opened: pd.Series, closed: pd.Series,
                end: pd.Timestamp) -> list[list]:
    """Closure hazard by tenure bucket, over each account's whole life.

    Of the accounts that REACHED a bucket, what share closed inside it?
    Censored accounts still inside a bucket have not had the full exposure, so
    only accounts that either closed in it or lived past it are counted --
    otherwise a young book dilutes every rate.

    Extracted so the condition layer can place an account in the peak band
    using THIS curve rather than a second copy of the bucket arithmetic.
    """
    life_m = (closed.fillna(end) - opened).dt.days / 30.44
    valid = life_m.notna() & (life_m >= 0)
    is_closed = closed.notna()
    rows = []
    for low, high, label in HAZARD_BUCKETS:
        entered = valid & (life_m >= low)
        resolved = entered & (is_closed | (life_m >= high))
        closed_in = resolved & is_closed & (life_m < high)
        n = int(resolved.sum())
        rows.append([label, n, int(closed_in.sum()),
                     _pct(int(closed_in.sum()), n)])
    return rows


def peak_band(rows: list[list]) -> tuple[float, float] | None:
    """The hazard rows' worst bucket, as (low_months, high_months).

    None when no bucket clears MIN_RESOLVED_FOR_PEAK: a bucket with fewer
    resolved accounts than that swings on one or two closures, and naming it
    the peak reports noise as a finding.
    """
    peaks = [r for r in rows
             if r[1] >= MIN_RESOLVED_FOR_PEAK and r[3] is not None]
    if not peaks:
        return None
    label = max(peaks, key=lambda r: r[3])[0]
    for low, high, name in HAZARD_BUCKETS:
        if name == label:
            return (low, high)
    return None


def _pct(n, d, digits=1) -> float | None:
    """A rate, or None when there is nobody to measure.

    Returning 0.0 for an empty denominator made a structural zero
    indistinguishable from a measured one: a balance band with no accounts in
    it printed "0.0%", which reads as nobody leaves from here rather than
    nobody is here. Every row carries n alongside, so the renderer keeps all
    the information it had and gains the distinction.
    """
    return round(100 * n / d, digits) if d else None


def _lift(worse, better, digits=1) -> float | None:
    """The gap between two rates, or None when either side was not measured.

    A lift of 0.0pp claims the two cohorts behave identically, which is not
    what an empty cohort means.
    """
    if worse is None or better is None:
        return None
    return round(worse - better, digits)


def _window(anchor: Month, months: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    start_m = anchor.shift(-(months - 1))
    start = pd.Timestamp(start_m.year, start_m.month, 1)
    end = pd.Timestamp(anchor.year, anchor.month, 1) + pd.offsets.MonthEnd(0)
    return start, end


ATTRITION_WINDOW_MONTHS = 12


def branch_closure_rates(df: pd.DataFrame, anchor: Month,
                         branch_map: dict | None = None,
                         min_at_risk: int = 1) -> list[list]:
    """Per-branch closure on the section's own window and exposure basis.

    Extracted so the hotspot overlay joins the SAME numbers this chapter
    prints instead of recomputing them and drifting apart -- the habit
    overlay.py already follows by importing balance.flight_mask rather than
    re-deriving it.

    Rows: [branch, at_risk, closed, rate_pct, account_years,
           rate_per_account_year]. Empty when the frame carries no Branch or
    no usable dates.
    """
    if "Branch" not in df.columns:
        return []
    opened = pd.to_datetime(df.get("Date Opened"), errors="coerce")
    closed = pd.to_datetime(df.get("Date Closed"), errors="coerce") \
        if "Date Closed" in df.columns else None
    if opened is None or opened.isna().all() or closed is None or closed.isna().all():
        return []

    start, end = _window(anchor, ATTRITION_WINDOW_MONTHS)
    existed = opened <= end
    closed_in_window = existed & closed.between(start, end)
    at_risk = existed & (closed.isna() | (closed >= start))

    entered = opened.where(opened > start, start)
    exited = closed.fillna(end).where(closed.fillna(end) < end, end)
    days = (exited - entered).dt.days.add(1).clip(lower=0)

    named = branch_names(norm(df["Branch"]), branch_map or {})
    rows = []
    for name, idx in df.groupby(named).groups.items():
        band = at_risk.reindex(idx, fill_value=False)
        n = int(band.sum())
        if n < min_at_risk:
            continue
        c = int((closed_in_window.reindex(idx, fill_value=False) & band).sum())
        yrs = float(days.reindex(idx, fill_value=0)[band].sum()) / 365.2425
        rows.append([str(name), n, c, _pct(c, n), round(yrs, 1),
                     round(100 * c / yrs, 1) if yrs else None])
    rows.sort(key=lambda r: -r[1])
    return rows


def compute(subsets: Subsets, config: dict, warn) -> dict:
    df = subsets.total
    opened = pd.to_datetime(df.get("Date Opened"), errors="coerce") \
        if "Date Opened" in df.columns else None
    closed = pd.to_datetime(df.get("Date Closed"), errors="coerce") \
        if "Date Closed" in df.columns else None

    if closed is None or closed.isna().all():
        warn("no Date Closed values; attrition section skipped")
        return {}
    if opened is None or opened.isna().all():
        warn("no Date Opened; attrition section skipped")
        return {}

    start, end = _window(subsets.anchor, 12)

    # Denominator: accounts that existed at the start of the window. An
    # account opened mid-window is at risk for part of it, so it counts.
    existed = opened <= end
    closed_in_window = existed & closed.between(start, end)
    at_risk = existed & (closed.isna() | (closed >= start))

    n_at_risk = int(at_risk.sum())
    n_closed = int(closed_in_window.sum())

    # Exposure: the days each at-risk account actually spent inside the
    # window. Counting accounts instead gives an account opened in the final
    # month one month of risk and a full unit of denominator, which dilutes
    # the rate on a growing book -- the faster the growth, the larger the
    # understatement. The hazard curve below already censors on the same
    # principle; this brings the headline into line with it.
    entered = opened.where(opened > start, start)
    exited = closed.fillna(end).where(closed.fillna(end) < end, end)
    days = (exited - entered).dt.days.add(1).clip(lower=0)
    exposure_years = float(days[at_risk].sum()) / 365.2425

    out = {
        "attrition_window": [start.strftime("%Y-%m"), end.strftime("%Y-%m")],
        "attrition_at_risk": n_at_risk,
        "attrition_closed": n_closed,
        "attrition_rate": _pct(n_closed, n_at_risk),
        "attrition_base": "Open at window start + opened during",
        "attrition_exposure_years": round(exposure_years, 1),
        "attrition_rate_exposure": (round(100 * n_closed / exposure_years, 1)
                                    if exposure_years else None),
        "attrition_rate_exposure_basis": (
            "closures per account-year at risk; an account opened mid-window "
            "contributes only the part of the year it was actually exposed"),
    }

    opened_in_window = existed & opened.between(start, end)
    out["attrition_opened"] = int(opened_in_window.sum())
    out["attrition_net"] = out["attrition_opened"] - n_closed
    out["attrition_growth_rate"] = _pct(out["attrition_net"], n_at_risk)

    # ---- A9.12: monthly closure velocity -------------------------------
    velocity = []
    for m in trailing(subsets.anchor, 24):
        m_start = pd.Timestamp(m.year, m.month, 1)
        m_end = m_start + pd.offsets.MonthEnd(0)
        velocity.append([
            m.tag,
            int((opened.between(m_start, m_end)).sum()),
            int((closed.between(m_start, m_end)).sum()),
        ])
    out["attrition_velocity"] = velocity
    recent = [v[2] for v in velocity[-12:]]
    if len(recent) >= MIN_MONTHS_FOR_SLOPE:
        slope = float(np.polyfit(np.arange(len(recent)), np.array(recent), 1)[0])
        out["attrition_velocity_slope"] = round(slope, 2)

    # ---- A9.0b: cohort survival by open month ---------------------------
    # The legacy table the rebuild dropped: for each month of openings, how
    # many are still open at the anchor. Months with no openings are absent
    # rather than zero rows, so a young client's table is short, not padded.
    cohort_rows = []
    for m in trailing(subsets.anchor, COHORT_MONTHS):
        m_start = pd.Timestamp(m.year, m.month, 1)
        m_end = m_start + pd.offsets.MonthEnd(0)
        cohort = opened.between(m_start, m_end)
        n = int(cohort.sum())
        if not n:
            continue
        gone = int((cohort & closed.notna() & (closed <= end)).sum())
        cohort_rows.append([m.tag, n, n - gone, gone, _pct(n - gone, n)])
    out["attrition_cohort_survival"] = cohort_rows
    out["attrition_cohort_survival_columns"] = [
        "open_month", "opened", "still_open", "closed", "survival_pct"]

    # First-year rate of a cohort that has had a full year: accounts opened
    # in the twelve months ending one year before the anchor.
    fy_end = end - pd.DateOffset(years=1)
    fy_start = fy_end - pd.DateOffset(years=1) + pd.Timedelta(days=1)
    fy_cohort = opened.between(fy_start, fy_end)
    fy_base = int(fy_cohort.sum())
    fy_closed = int((fy_cohort & closed.notna()
                     & ((closed - opened).dt.days < 365)).sum())
    out["attrition_cohort_first_year_base"] = fy_base
    out["attrition_cohort_first_year_rate"] = _pct(fy_closed, fy_base) if fy_base else None

    # Of the window's closures, how many were seasoned accounts (opened
    # before the window) rather than the window's own cohort.
    seasoned = closed_in_window & (opened < start)
    out["attrition_closures_seasoned_pct"] = (_pct(int(seasoned.sum()), n_closed)
                                              if n_closed else None)

    # ---- A9.2: how long accounts survive before closing ----------------
    life = ((closed - opened).dt.days / 365.2425)
    closed_life = life[closed_in_window & life.notna() & (life >= 0)]
    if len(closed_life):
        out["attrition_median_life"] = round(float(closed_life.median()), 1)
        out["attrition_mean_life"] = round(float(closed_life.mean()), 1)
        out["attrition_first_year_pct"] = _pct(
            int((closed_life < 1).sum()), len(closed_life))
        buckets = []
        for low, high, label in TENURE_BANDS:
            buckets.append([label, int(((closed_life >= low) &
                                        (closed_life < high)).sum())])
        out["attrition_life_dist"] = buckets
        # In months, for the first year (legacy A9.2, #245): where inside the
        # first year the closures cluster is what the yearly bands hide.
        months = (closed - opened).dt.days / 30.44
        closed_months = months[closed_in_window & months.notna() & (months >= 0)]
        mrows = []
        for low, high, label in ((0, 1, "< 1 mo"), (1, 3, "1-3 mo"), (3, 6, "3-6 mo"),
                                 (6, 12, "6-12 mo"), (12, 1e9, "12+ mo")):
            n = int(((closed_months >= low) & (closed_months < high)).sum())
            mrows.append([label, n, _pct(n, len(closed_months))])
        out["attrition_life_dist_months"] = mrows
        out["attrition_life_dist_months_columns"] = ["band", "closed", "pct_of_closed"]

    # ---- A9.7: closure rate by tenure ----------------------------------
    tenure = (end - opened).dt.days / 365.2425
    rows = []
    for low, high, label in TENURE_BANDS:
        band = at_risk & tenure.between(low, high - 0.001)
        n = int(band.sum())
        c = int((band & closed_in_window).sum())
        rows.append([label, n, c, _pct(c, n)])
    out["attrition_by_tenure"] = rows

    # ---- closure hazard by tenure (whole-history) -----------------------
    # Of the accounts that REACHED a tenure bucket, what share closed inside
    # it? Unlike the window rate above, this reads every account's full life,
    # so the shape (early cliff vs late drift) is what the legacy section
    # showed. Buckets in months since opening.
    hrows = hazard_rows(opened, closed, end)
    out["attrition_hazard"] = hrows
    out["attrition_hazard_columns"] = ["tenure", "reached_and_resolved", "closed_in_bucket", "hazard_pct"]
    peaks = [r for r in hrows
             if r[1] >= MIN_RESOLVED_FOR_PEAK and r[3] is not None]
    if peaks:
        peak = max(peaks, key=lambda r: r[3])
        out["attrition_hazard_peak"] = [peak[0], peak[3]]
        out["attrition_hazard_peak_months"] = list(peak_band(hrows) or ())
    elif any(r[1] for r in hrows):
        warn(f"attrition hazard peak not named: no tenure bucket reached "
             f"{MIN_RESOLVED_FOR_PEAK} resolved accounts, so the shape is "
             f"shown without a called-out peak")

    # ---- A9.8: by balance ----------------------------------------------
    # GUARD: a closed account's balance is zero by definition, so segmenting
    # closures by CURRENT balance piles every closure into the lowest band
    # and drops the rest as null. Prefer Avg Bal, and verify that closures
    # actually spread across bands before reporting.
    balance = pd.to_numeric(df["Avg Bal"], errors="coerce") \
        if "Avg Bal" in df.columns else None
    balance_source = "Avg Bal"
    if balance is None or balance.isna().all():
        balance = pd.to_numeric(df["Curr Bal"], errors="coerce") \
            if "Curr Bal" in df.columns else None
        balance_source = "Curr Bal"

    if balance is not None and balance.notna().any():
        rows = []
        for low, high, label in BALANCE_BANDS:
            band = at_risk & (balance >= low) & (balance < high)
            n = int(band.sum())
            c = int((band & closed_in_window).sum())
            rows.append([label, n, c, _pct(c, n)])

        counted = sum(r[2] for r in rows)
        bands_with_closures = sum(1 for r in rows if r[2] > 0)
        coverage = _pct(counted, n_closed, 0)

        if (bands_with_closures <= 1 or coverage is None
                or coverage < MIN_BALANCE_COVERAGE_PCT):
            warn(
                f"attrition by balance SUPPRESSED: only {counted:,} of "
                f"{n_closed:,} closures ({coverage}%) land in a balance band, "
                f"across {bands_with_closures} band(s). {balance_source} is "
                f"zeroed or cleared when an account closes, so balance at "
                f"closure is not recoverable from this file."
            )
            out["attrition_balance_valid"] = False
        else:
            out["attrition_by_balance"] = rows
            out["attrition_balance_source"] = balance_source
            out["attrition_balance_valid"] = True

    # ---- A9.4: by branch ------------------------------------------------
    branch_map = config.get("BranchMapping", {}) or {}
    branch = norm(df.get("Branch"))
    if branch is not None:
        # by display name -- codes sharing a name merge to one row (#47)
        from ..core.subsets import branch_names
        named = branch_names(branch, branch_map)
        rows = []
        for name, idx in df.groupby(named).groups.items():
            band = at_risk.reindex(idx, fill_value=False)
            n = int(band.sum())
            if not n:
                continue
            c = int((closed_in_window.reindex(idx, fill_value=False) & band).sum())
            rows.append([str(name), n, c, _pct(c, n)])
        rows.sort(key=lambda r: -r[1])
        out["attrition_by_branch"] = rows
        # Same window, same exposure basis as the headline -- kept in its own
        # key so the positional shape of attrition_by_branch does not move
        # under the surfaces already reading it.
        exposure_rows = branch_closure_rates(df, subsets.anchor, branch_map)
        if exposure_rows:
            out["attrition_branch_exposure"] = exposure_rows
            out["attrition_branch_exposure_columns"] = [
                "branch", "at_risk", "closed", "rate_pct", "account_years",
                "rate_per_account_year"]
        rated = [r for r in rows
                 if r[1] >= MIN_AT_RISK_FOR_BRANCH_RANK and r[3] is not None]
        if not rated and rows:
            warn(f"attrition best/worst branch not named: no branch carries "
                 f"{MIN_AT_RISK_FOR_BRANCH_RANK} at-risk accounts "
                 f"(largest is {max(r[1] for r in rows):,}). The per-branch "
                 f"table is still reported.")
        if rated:
            worst = max(rated, key=lambda r: r[3])
            best = min(rated, key=lambda r: r[3])
            out["attrition_branch_worst"] = [worst[0], worst[3], worst[1]]
            out["attrition_branch_best"] = [best[0], best[3], best[1]]

    # ---- A9.4b: by account lens -----------------------------------------
    # ICS, responders, MRPC and the rest, on the SAME definitions the
    # transaction chapter uses (core/account_lenses), so "ICS" means one
    # thing across the whole run.
    #
    # Reported per ACCOUNT-YEAR at risk, not as a raw share. A programme that
    # opened most of its accounts recently is exposed for less of the window,
    # and a raw closure rate would flatter it for being young -- the same
    # exposure trap the headline rate above was fixed for. On 1776 the ICS
    # cohort averages under eight months of maturity against a book measured
    # over twelve, so the raw and exposure rates are not interchangeable.
    lens_masks = account_lenses.masks_for(df, end, warn=lambda *_a: None)
    rows = []
    for name in account_lenses.ordered_names(lens_masks):
        band = at_risk & lens_masks[name].reindex(df.index, fill_value=False)
        n = int(band.sum())
        if n < MIN_AT_RISK_FOR_LENS:
            continue
        c = int((closed_in_window & band).sum())
        yrs = float(days[band].sum()) / 365.2425
        rows.append([name, account_lenses.label(name), n, c, _pct(c, n),
                     round(yrs, 1),
                     round(100 * c / yrs, 1) if yrs else None])
    if rows:
        out["attrition_by_lens"] = rows
        out["attrition_by_lens_columns"] = [
            "lens", "label", "at_risk", "closed", "rate_pct",
            "exposure_years", "rate_per_account_year"]
        out["attrition_by_lens_basis"] = (
            "closures per account-year at risk; lenses share one definition "
            "with the transaction chapter")
        lens_names = {r[0] for r in rows}
        if "ics" in lens_names and "all" in lens_names:
            ics_r = next(r for r in rows if r[0] == "ics")
            all_r = next(r for r in rows if r[0] == "all")
            if ics_r[6] is not None and all_r[6] is not None:
                out["attrition_ics_vs_book_pp"] = round(ics_r[6] - all_r[6], 1)
    else:
        warn(f"attrition by lens: no lens carries {MIN_AT_RISK_FOR_LENS} "
             f"at-risk accounts; the cut is not reported")

    # ---- A9.5: by product ----------------------------------------------
    prod = norm(df.get("Prod Desc"))
    if prod is None:
        prod = norm(df.get("Prod Code"))
    if prod is not None:
        rows = []
        for code, idx in df.groupby(prod).groups.items():
            band = at_risk.reindex(idx, fill_value=False)
            n = int(band.sum())
            if n < MIN_AT_RISK_FOR_PRODUCT:
                continue
            c = int((closed_in_window.reindex(idx, fill_value=False) & band).sum())
            rows.append([str(code) or "(blank)", n, c, _pct(c, n)])
        rows.sort(key=lambda r: -r[1])
        if not rows and prod.notna().any():
            warn(f"attrition by product SUPPRESSED: no product reaches "
                 f"{MIN_AT_RISK_FOR_PRODUCT} at-risk accounts")
        out["attrition_by_product"] = rows[:15]

    # ---- ARS-eligible product vs not: does the program base close less? --
    # By PRODUCT, not by subsets.eligible (which requires open, so closed
    # accounts could never count as eligible and the rate would read 0).
    elig_prod = {str(p).strip().upper() for p in config.get("EligibleProductCodes", [])}
    prod_code = norm(df.get("Prod Code"))
    if elig_prod and prod_code is not None:
        elig_mask = prod_code.str.upper().isin(elig_prod)
        rows = []
        for label, band in (("ARS-eligible product", elig_mask),
                            ("Other products", ~elig_mask)):
            n = int((at_risk & band).sum())
            c = int((closed_in_window & band).sum())
            rows.append([label, n, c, _pct(c, n)])
        out["attrition_ars_vs_non"] = rows
        out["attrition_ars_gap_pp"] = _lift(rows[0][3], rows[1][3])

    # ---- first-year close rate by branch (accounts opened in the window) ----
    if branch is not None:
        fy_rows = []
        for name, idx in df.groupby(named).groups.items():
            o = opened_in_window.reindex(idx, fill_value=False)
            n = int(o.sum())
            if n < MIN_OPENED_FOR_FIRST_YEAR:
                continue
            c = int((o & closed_in_window.reindex(idx, fill_value=False)).sum())
            fy_rows.append([str(name), n, c, _pct(c, n)])
        fy_rows.sort(key=lambda r: -(r[3] if r[3] is not None else -1))
        if not fy_rows:
            warn(f"attrition first-year close by branch SUPPRESSED: no branch "
                 f"opened {MIN_OPENED_FOR_FIRST_YEAR} accounts in the window")
        out["attrition_first_year_by_branch"] = fy_rows

    # ---- A9.9: debit retention lift -------------------------------------
    # GUARD: Debit? is CURRENT state. If the core clears the flag when an
    # account closes, the "no debit" cohort is largely made of closed
    # accounts and the lift is circular -- closure explaining itself. Detect
    # that before reporting anything.
    carded = has_debit(df)
    closed_carded_share = (
        float(carded[closed_in_window].mean() * 100) if n_closed else 0.0
    )
    open_carded_share = (
        float(carded[at_risk & ~closed_in_window].mean() * 100)
        if int((at_risk & ~closed_in_window).sum()) else 0.0
    )
    out["attrition_debit_closed_share"] = round(closed_carded_share, 1)
    out["attrition_debit_open_share"] = round(open_carded_share, 1)

    # A card is not usually surrendered on closure. If closed accounts hold
    # cards at a far lower rate than open ones, the flag is being cleared.
    contaminated = ((open_carded_share - closed_carded_share)
                    > MAX_DEBIT_SHARE_GAP_PP)

    for label, mask, key in (("debit", carded, "debit"),
                             ("no debit", ~carded, "nodebit")):
        band = at_risk & mask
        n = int(band.sum())
        c = int((band & closed_in_window).sum())
        out[f"attrition_{key}_n"] = n
        out[f"attrition_{key}_rate"] = _pct(c, n)

    if contaminated:
        out["attrition_debit_lift_valid"] = False
        out["attrition_debit_lift_pp"] = None
        warn(
            f"debit retention lift SUPPRESSED: {closed_carded_share:.0f}% of "
            f"closed accounts show a debit card vs {open_carded_share:.0f}% of "
            f"open ones. The core appears to clear Debit? on closure, so the "
            f"comparison measures closure against itself. Needs a debit flag "
            f"that survives closure, or a point-in-time snapshot."
        )
    else:
        out["attrition_debit_lift_valid"] = True
        out["attrition_debit_lift_pp"] = _lift(
            out["attrition_nodebit_rate"], out["attrition_debit_rate"])

    # ---- A9.10: mailer retention lift ------------------------------------
    # Mail/response history is historical, not current state, so it does not
    # suffer the same contamination.
    if "# of Responses" in df.columns:
        responded = df["# of Responses"] > 0
        offered = df["# of Offers"] > 0
        for label, mask in (("resp", offered & responded),
                            ("nonresp", offered & ~responded)):
            band = at_risk & mask
            n = int(band.sum())
            c = int((band & closed_in_window).sum())
            out[f"attrition_{label}_n"] = n
            out[f"attrition_{label}_rate"] = _pct(c, n)
        out["attrition_mailer_lift_pp"] = _lift(
            out["attrition_nonresp_rate"], out["attrition_resp_rate"])
        # The legacy three-way split (#245): never-mailed accounts are the
        # control that isolates the programme from the selection, which
        # responders-vs-mailed-non-responders cannot do on its own.
        for label, mask in (("mailed", offered), ("nevermailed", ~offered)):
            band = at_risk & mask
            n = int(band.sum())
            c = int((band & closed_in_window).sum())
            out[f"attrition_{label}_n"] = n
            out[f"attrition_{label}_rate"] = _pct(c, n)
        out["attrition_mailed_vs_nevermailed_pp"] = _lift(
            out["attrition_mailed_rate"], out["attrition_nevermailed_rate"])

    # ---- A9.6: personal vs business --------------------------------------
    from ..core.subsets import is_business

    biz = is_business(df)
    for label, mask in (("personal", ~biz), ("business", biz)):
        band = at_risk & mask
        n = int(band.sum())
        c = int((band & closed_in_window).sum())
        out[f"attrition_{label}_n"] = n
        out[f"attrition_{label}_rate"] = _pct(c, n)

    # ---- A9.11: revenue impact -------------------------------------------
    ic_raw = str(config.get("ICRate", "")).strip()
    spend_cols = columns_for(df.columns, "Spend")[-12:]
    if ic_raw and spend_cols:
        try:
            ic_rate = float(ic_raw)
            annual = df[spend_cols].sum(axis=1) * (12 / len(spend_cols))
            lost = annual[closed_in_window].sum() * ic_rate
            out["attrition_revenue_lost"] = round(float(lost))
            out["attrition_revenue_per_closed"] = round(
                float(lost) / n_closed, 2) if n_closed else 0.0
        except ValueError:
            warn(f"ICRate {ic_raw!r} is not numeric; revenue impact skipped")
    return out
