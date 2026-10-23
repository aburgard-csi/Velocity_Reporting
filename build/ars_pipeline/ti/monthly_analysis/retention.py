# Ported from ARS v5 02-Scripts/ars/monthly_analysis/retention.py at a491b5c (James Gilmore); logic unchanged.
"""Retention: account health before closure.

Attrition asks whether an account closed. This asks whether it is on the way
out -- spend fading, months going quiet -- which is the window where anything
can still be done about it.

Health is classified from the spend trajectory:

    Dormant    3+ consecutive months with no spend
    Cooling    recent spend below half of the prior period
    Declining  recent spend below 80% of the prior period
    Active     everything else

RATIO, NOT DOLLARS. The legacy classifier used `spend_slope < -5`: five
dollars a month, absolute. On a book spanning $20/mo to $5,000/mo that flags
a large account losing 0.3% and ignores a small one losing 80%. Ratios are
scale-free, so a segment's health means the same thing at every spend level.
The slope is still computed and reported -- it is a useful early-warning
signal, just not a good classifier.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.periods import Month, columns_for
from ..core.subsets import Subsets, has_debit, norm, num_col

RECENT_MONTHS = 3
PRIOR_MONTHS = 3
DORMANT_ZERO_MONTHS = 3
COOLING_RATIO = 0.50
DECLINING_RATIO = 0.80
GROWING_RATIO = 1.10      # the legacy attrition_txn "Growing" line, both axes
SLOPE_WINDOW = 6

HEALTH_ORDER = ["Active", "Declining", "Cooling", "Dormant",
                "Never activated", "No card"]
# "No card" is not at risk of card attrition -- it has no card to lose.
AT_RISK = ["Declining", "Cooling", "Dormant", "Never activated"]

AGE_BANDS = [(18, 25, "18-24"), (25, 35, "25-34"), (35, 45, "35-44"),
             (45, 55, "45-54"), (55, 65, "55-64"), (65, 120, "65+")]


def _pct(n, d, digits=1) -> float:
    return round(100 * n / d, digits) if d else 0.0


def _consecutive_zeros(values: np.ndarray) -> np.ndarray:
    """Count trailing zero months per row, walking backwards from the end."""
    n_months = values.shape[1]
    counts = np.zeros(values.shape[0], dtype=int)
    still_running = np.ones(values.shape[0], dtype=bool)
    for i in range(n_months - 1, -1, -1):
        is_zero = values[:, i] <= 0
        counts = np.where(still_running & is_zero, counts + 1, counts)
        still_running = still_running & is_zero
    return counts


def classify_health(recent: pd.Series, prior: pd.Series,
                    months_quiet: pd.Series, carded: pd.Series,
                    swipe_ratio: pd.Series | None = None) -> pd.Series:
    """Where an account sits on the spend trajectory.

    Extracted from compute() so other layers join THIS classification rather
    than re-deriving one that drifts -- the habit overlay.py already follows
    by importing balance.flight_mask.

    RATIO, NOT DOLLARS. `spend_slope < -5` flags a large account losing 0.3%
    and ignores a small one losing 80%. Ratios mean the same thing at every
    spend level.

    An account with no card was never going to have card spend. Calling it
    dormant conflates "stopped using it" with "never had one" and inflates the
    at-risk rate by the whole non-carded population -- on a book where a third
    have no card, that is the difference between a 64% headline and a real one.
    """
    live = prior > 0
    ratio = pd.Series(0.0, index=recent.index)
    ratio[live] = recent[live] / prior[live]
    never_spent = (~live) & (recent <= 0)

    health = pd.Series("Active", index=recent.index, dtype=object)
    health[live & (ratio < DECLINING_RATIO)] = "Declining"
    health[live & (ratio < COOLING_RATIO)] = "Cooling"
    # EITHER axis, as the legacy attrition_txn tiers did (#245): an account
    # swiping a fifth as often on the same dollars is disengaging, and spend
    # alone cannot see it. Swipes can only demote, never promote.
    # Cooling stays a spend judgement: the legacy tiers had no swipe-only
    # cooling class and a swipe collapse on steady dollars is "Declining".
    if swipe_ratio is not None:
        sw = swipe_ratio.reindex(recent.index)
        swipe_down = live & sw.notna() & (sw < DECLINING_RATIO)
        health[(health == "Active") & swipe_down] = "Declining"
    health[months_quiet >= DORMANT_ZERO_MONTHS] = "Dormant"
    health[never_spent] = "Dormant"
    health[~carded] = "No card"
    # A cardholder that never spent is a real finding: issued, never activated.
    health[carded & never_spent] = "Never activated"
    return health


def at_risk_mask(health: pd.Series) -> pd.Series:
    """The at-risk cut of the classification. "No card" is excluded -- it has
    no card to lose."""
    return health.isin(AT_RISK)


def compute(subsets: Subsets, config: dict, warn) -> dict:
    base = subsets.eligible
    spend_cols = columns_for(base.columns, "Spend")
    if len(spend_cols) < RECENT_MONTHS + PRIOR_MONTHS:
        warn(f"only {len(spend_cols)} monthly Spend columns; retention health "
             f"needs {RECENT_MONTHS + PRIOR_MONTHS}")
        return {}

    matrix = base[spend_cols].apply(pd.to_numeric, errors="coerce").fillna(0).values
    recent = matrix[:, -RECENT_MONTHS:].mean(axis=1)
    prior = matrix[:, -(RECENT_MONTHS + PRIOR_MONTHS):-RECENT_MONTHS].mean(axis=1)
    zeros = _consecutive_zeros(matrix)

    window = min(SLOPE_WINDOW, matrix.shape[1])
    trailing = matrix[:, -window:]
    x = np.arange(window)
    x_centered = x - x.mean()
    denom = float((x_centered ** 2).sum())
    slope = (((trailing - trailing.mean(axis=1, keepdims=True)) * x_centered).sum(axis=1)
             / denom) if denom else np.zeros(len(base))

    recent_s = pd.Series(recent, index=base.index)
    prior_s = pd.Series(prior, index=base.index)
    zeros_s = pd.Series(zeros, index=base.index)
    slope_s = pd.Series(slope, index=base.index)

    # Slope relative to the account's own prior level -- comparable across
    # a book that spans three orders of magnitude.
    slope_pct = pd.Series(0.0, index=base.index)
    live = prior_s > 0
    slope_pct[live] = slope_s[live] / prior_s[live] * 100

    ratio = pd.Series(np.nan, index=base.index)
    ratio[live] = recent_s[live] / prior_s[live]

    # ---- swipe velocity: the second axis ---------------------------------
    swipe_cols = columns_for(base.columns, "Swipes")
    swipe_ratio = None
    if len(swipe_cols) >= RECENT_MONTHS + PRIOR_MONTHS:
        smatrix = base[swipe_cols].apply(pd.to_numeric, errors="coerce").fillna(0).values
        s_recent = pd.Series(smatrix[:, -RECENT_MONTHS:].mean(axis=1), index=base.index)
        s_prior = pd.Series(
            smatrix[:, -(RECENT_MONTHS + PRIOR_MONTHS):-RECENT_MONTHS].mean(axis=1),
            index=base.index)
        swipe_ratio = pd.Series(np.nan, index=base.index)
        s_live = s_prior > 0
        swipe_ratio[s_live] = s_recent[s_live] / s_prior[s_live]
    else:
        warn(f"only {len(swipe_cols)} monthly Swipes columns; health classes "
             f"read spend alone and the velocity axes are not built")

    carded = has_debit(base)
    health = classify_health(recent_s, prior_s, zeros_s, carded, swipe_ratio)
    at_risk = at_risk_mask(health)
    out: dict = {
        "retention_base": "Eligible",
        "retention_n": len(base),
        "retention_carded_n": int(carded.sum()),
        "retention_no_card_n": int((~carded).sum()),
        "retention_at_risk_of_carded_pct": _pct(
            int(at_risk.sum()), int(carded.sum())),
        "retention_window": [Month.from_tag(spend_cols[0].split()[0]).tag,
                             Month.from_tag(spend_cols[-1].split()[0]).tag],
        "retention_at_risk_n": int(at_risk.sum()),
        "retention_at_risk_pct": _pct(int(at_risk.sum()), len(base)),
    }

    rows = []
    for status in HEALTH_ORDER:
        mask = health == status
        n = int(mask.sum())
        rows.append([
            status, n, _pct(n, len(base)),
            round(float(recent_s[mask].mean()), 2) if n else 0.0,
            round(float(prior_s[mask].mean()), 2) if n else 0.0,
            _pct(int(has_debit(base[mask]).sum()), n),
        ])
    out["retention_health"] = rows

    # Annualized spend sitting in each bucket -- what disengagement costs.
    out["retention_spend_at_risk"] = round(
        float(prior_s[at_risk].sum()) * 12)
    out["retention_spend_active"] = round(
        float(recent_s[health == "Active"].sum()) * 12)
    dormant = health == "Dormant"
    out["retention_spend_dormant_prior"] = round(float(prior_s[dormant].sum()) * 12)

    # ---- early warning: high prior spend, steep decline ------------------
    if live.any():
        median_prior = float(prior_s[live].median())
        signals = pd.Series(0, index=base.index)
        signals += (slope_pct < -10).astype(int)
        signals += (zeros_s >= 2).astype(int)
        signals += ((prior_s > median_prior) & (recent_s < prior_s * 0.3)).astype(int)
        high_risk = at_risk & (signals >= 2)
        out["retention_signal_median_prior"] = round(median_prior, 2)
        out["retention_high_risk_n"] = int(high_risk.sum())
        out["retention_high_risk_spend"] = round(
            float(prior_s[high_risk].sum()) * 12)
        out["retention_high_risk_debit_pct"] = _pct(
            int(has_debit(base[high_risk]).sum()), int(high_risk.sum()))

    # ---- spend-velocity tiers (the legacy attrition_txn cut) --------------
    # The health model says WHERE an account sits; velocity says which way it
    # is moving and what spend rides on it. Tiers over recent/prior ratio for
    # accounts that had prior spend; dollars are prior spend annualized.
    had_prior = prior_s > 0
    vel = pd.Series(None, index=base.index, dtype=object)
    vel[had_prior & (recent_s <= 0)] = "Stopped"
    vel[had_prior & (recent_s > 0) & (ratio < 0.4)] = "Steep decline"
    vel[had_prior & (ratio >= 0.4) & (ratio < 0.75)] = "Slipping"
    vel[had_prior & (ratio >= 0.75) & (ratio < 1.25)] = "Stable"
    vel[had_prior & (ratio >= 1.25)] = "Growing"
    vrows = []
    for label in ("Growing", "Stable", "Slipping", "Steep decline", "Stopped"):
        mask = vel == label
        n = int(mask.sum())
        vrows.append([label, n, _pct(n, int(had_prior.sum())),
                      round(float(prior_s[mask].sum()) * 12)])
    out["retention_velocity"] = vrows
    out["retention_velocity_columns"] = ["tier", "accounts", "pct_of_prior_spenders",
                                         "prior_spend_annualized"]
    falling = vel.isin(["Slipping", "Steep decline", "Stopped"])
    out["retention_velocity_falling_n"] = int(falling.sum())
    out["retention_velocity_falling_spend"] = round(float(prior_s[falling].sum()) * 12)

    # ---- the two axes together (legacy 04_velocity_scatter) ---------------
    # Where spend and swipes disagree is the finding: fewer visits on the
    # same dollars is a habit breaking; smaller tickets on the same visits
    # is a wallet shrinking. Only accounts with a prior on both axes.
    if swipe_ratio is not None:
        both = had_prior & swipe_ratio.notna()
        spend_down = ratio < DECLINING_RATIO
        swipes_down = swipe_ratio < DECLINING_RATIO
        spend_up = ratio >= GROWING_RATIO
        swipes_up = swipe_ratio >= GROWING_RATIO
        quadrants = [
            ("Growing on both", both & spend_up & swipes_up),
            ("Smaller tickets, same visits", both & spend_down & ~swipes_down),
            ("Fewer visits, same dollars", both & swipes_down & ~spend_down),
            ("Disengaging on both", both & spend_down & swipes_down),
        ]
        named = pd.Series(False, index=base.index)
        arows = []
        for label, mask in quadrants:
            named |= mask
            arows.append([label, int(mask.sum()), _pct(int(mask.sum()), int(both.sum())),
                          round(float(prior_s[mask].sum()) * 12)])
        steady = both & ~named
        arows.append(["Steady", int(steady.sum()), _pct(int(steady.sum()), int(both.sum())),
                      round(float(prior_s[steady].sum()) * 12)])
        out["retention_axes"] = arows
        out["retention_axes_columns"] = ["quadrant", "accounts", "pct_of_prior_spenders",
                                         "prior_spend_annualized"]
        out["retention_axes_base"] = int(both.sum())
        out["retention_swipe_only_decline_n"] = int((both & swipes_down & ~spend_down).sum())

    # ---- who is at risk --------------------------------------------------
    def risk_row(label: str, mask: pd.Series) -> list:
        n = int(mask.sum())
        return [label, n, _pct(int((mask & at_risk).sum()), n),
                round(float(prior_s[mask & at_risk].sum()) * 12)]

    if "Account Holder Age" in base.columns:
        age = pd.to_numeric(base["Account Holder Age"], errors="coerce")
        age_rows = []
        for low, high, label in AGE_BANDS:
            mask = age.between(low, high - 0.001)
            if int(mask.sum()) >= 25:
                age_rows.append(risk_row(label, mask))
        out["retention_by_age"] = age_rows

    opened = pd.to_datetime(base.get("Date Opened"), errors="coerce")
    if opened is not None and opened.notna().any():
        anchor = pd.Timestamp(subsets.anchor.year, subsets.anchor.month, 1) \
            + pd.offsets.MonthEnd(0)
        tenure = (anchor - opened).dt.days / 365.2425
        tenure_rows = []
        for low, high, label in [(0, 1, "< 1 yr"), (1, 3, "1-3 yr"),
                                 (3, 5, "3-5 yr"), (5, 10, "5-10 yr"),
                                 (10, 200, "10+ yr")]:
            mask = tenure.between(low, high - 0.001)
            if int(mask.sum()) >= 25:
                tenure_rows.append(risk_row(label, mask))
        out["retention_by_tenure"] = tenure_rows

    balance = num_col(base, "Curr Bal")
    if balance is not None and balance.notna().any():
        out["retention_by_balance"] = [
            risk_row(label, mask) for label, mask in (
                ("<= $0", balance <= 0),
                ("$1-1K", (balance > 0) & (balance < 1_000)),
                ("$1K-5K", (balance >= 1_000) & (balance < 5_000)),
                ("$5K-25K", (balance >= 5_000) & (balance < 25_000)),
                ("$25K+", balance >= 25_000),
            ) if int(mask.sum()) >= 25
        ]

    prod = norm(base.get("Prod Desc")) if "Prod Desc" in base.columns \
        else norm(base.get("Prod Code"))
    if prod is not None:
        prod_rows = []
        for code, idx in base.groupby(prod).groups.items():
            mask = pd.Series(base.index.isin(idx), index=base.index)
            if int(mask.sum()) >= 100:
                prod_rows.append(risk_row(str(code) or "(blank)", mask))
        prod_rows.sort(key=lambda r: -r[1])
        out["retention_by_product"] = prod_rows[:10]

    # ---- by engagement tier (legacy retention/03, #245) ----------------------
    # Are the heaviest cardholders leaving faster than the peripheral ones?
    # The ODD's own swipe tier is the engagement tier the legacy cut used.
    if "SwipeCat3" in base.columns:
        tier = norm(base["SwipeCat3"])
        tier_rows = []
        for label, idx in base.groupby(tier).groups.items():
            mask = pd.Series(base.index.isin(idx), index=base.index)
            if int(mask.sum()) >= 25 and str(label):
                tier_rows.append(risk_row(str(label), mask))
        tier_rows.sort(key=lambda r: -r[1])
        out["retention_by_swipe_tier"] = tier_rows

    # How long have carded accounts been silent? Consecutive zero-spend
    # months ending at the data month, as a distribution.
    prog = []
    for label, lo, hi in (("active", 0, 0), ("1 mo", 1, 1), ("2 mo", 2, 2),
                          ("3 mo", 3, 3), ("4-6 mo", 4, 6), ("7-12 mo", 7, 12),
                          ("13+ mo", 13, 10_000)):
        mask = carded & (zeros_s >= lo) & (zeros_s <= hi)
        prog.append([label, int(mask.sum()), _pct(int(mask.sum()), int(carded.sum()))])
    out["dormancy_progression"] = prog

    # ---- ARS takeaways ---------------------------------------------------
    if "# of Responses" in base.columns:
        responded = base["# of Responses"] > 0
        offered = base["# of Offers"] > 0
        out["retention_by_response"] = [
            risk_row("Responder", offered & responded),
            risk_row("Mailed non-responder", offered & ~responded),
            risk_row("Not mailed", ~offered),
        ]
        r_risk = _pct(int((offered & responded & at_risk).sum()),
                      int((offered & responded).sum()))
        n_risk = _pct(int((offered & ~responded & at_risk).sum()),
                      int((offered & ~responded).sum()))
        out["retention_responder_advantage_pp"] = round(n_risk - r_risk, 1)

        # Dormant cardholders who were mailed and never responded: the
        # reactivation list, already addressable through the program.
        target = dormant & has_debit(base) & offered & ~responded
        out["reactivation_target_n"] = int(target.sum())
        out["reactivation_target_prior_spend"] = round(
            float(prior_s[target].sum()) * 12)

    return out
