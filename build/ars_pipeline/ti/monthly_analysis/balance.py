# Ported from ARS v5 02-Scripts/ars/monthly_analysis/balance.py at a491b5c (James Gilmore); logic unchanged.
"""Deposit balance analysis, and how it ties to the ARS program.

Everything here comes from the ODD -- `Curr Bal`, `Avg Bal`, and the spend and
swipe totals the transform derives. The one piece that genuinely needs
transaction data is the competitor cross-reference, which stays in TXN.

Base is ELIGIBLE, not the whole file. Closed accounts carry a zeroed balance,
so running this over every row turns every closure into a "zero-balance
reactivation opportunity" -- on a 34k-row file with 10k closures that single
choice moves the headline by 30 points.

`bal_delta = Curr Bal - Avg Bal` is a trend proxy, not a time series: it says
where the account sits today relative to its own average, which is enough to
flag deposits draining but not enough to date the decline.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..core.subsets import Subsets, has_debit, norm, num_col

BANDS = [
    (-np.inf, 0.01, "$0"),
    (0.01, 1_000, "$1-1K"),
    (1_000, 5_000, "$1K-5K"),
    (5_000, 25_000, "$5K-25K"),
    (25_000, 100_000, "$25K-100K"),
    (100_000, np.inf, "$100K+"),
]
BAND_ORDER = [b[2] for b in BANDS]
BAND_SCORE = {"$0": 0, "$1-1K": 1, "$1K-5K": 2,
              "$5K-25K": 3, "$25K-100K": 4, "$100K+": 5}

FLIGHT_RISK_THRESHOLD = 25_000
PFI_TIERS = [(10, np.inf, "Primary"), (6, 9, "Secondary"),
             (3, 5, "Tertiary"), (0, 2, "Incidental")]


def flight_mask(current: pd.Series, average: pd.Series,
                inflow_ratio: pd.Series | None = None) -> pd.Series:
    """Deposit flight risk, THE definition. Shared with the conditions layer
    and the transaction overlay so 'flight risk' never means two things.

    A high-balance account whose CREDITS are falling: recent inflow under
    the prior window at retention.py's declining ratio, when the deposits
    file gives us the account's own inflow. Without it, the proxy the
    chapter always used: current balance below its average. The proxy
    cannot tell a member drawing down from a member no longer being paid;
    the inflow can, which is why the file replaces it the moment it exists.
    """
    high = current >= FLIGHT_RISK_THRESHOLD
    if inflow_ratio is None:
        delta = current - average.fillna(0)
        return high & (delta < 0)
    from .retention import DECLINING_RATIO

    falling = inflow_ratio.reindex(current.index) < DECLINING_RATIO
    return high & falling.fillna(False).astype(bool)


def _inflow_ratio_for(base: pd.DataFrame, config: dict) -> pd.Series | None:
    """The base's per-account inflow ratio from the run's deposits file, or
    None when the file is absent or too short to hold both windows."""
    from ..core.facts import ID_COLUMNS, deposit_windows, inflow_ratio

    recent, prior = deposit_windows(config.get("_deposit_monthly"))
    if recent is None:
        return None
    col = next((c for c in ID_COLUMNS if c in base.columns), None)
    if col is None:
        return None
    key = base[col].astype(str).str.strip().str.upper() \
        .str.replace(r"\.0$", "", regex=True)
    return inflow_ratio(key.map(recent), key.map(prior))


def _pct(n, d, digits=1) -> float:
    return round(100 * n / d, digits) if d else 0.0


def _band(values: pd.Series) -> pd.Series:
    edges = [b[0] for b in BANDS] + [np.inf]
    return pd.cut(values, bins=edges, labels=BAND_ORDER,
                  right=False, include_lowest=True).astype(object)


def compute(subsets: Subsets, config: dict, warn) -> dict:
    base = subsets.eligible
    if not len(base):
        return {}

    current = num_col(base, "Curr Bal")
    average = num_col(base, "Avg Bal")
    if current is None or current.isna().all():
        warn("no Curr Bal values; balance section skipped")
        return {}
    current = current.fillna(0)

    spend = num_col(base, "Total Spend")
    swipes = num_col(base, "Total Swipes")
    if spend is None:
        warn("frame is not enriched (no Total Spend); balance-vs-activity "
             "cuts skipped")

    out: dict = {
        "balance_base": "Eligible",
        "balance_n": len(base),
        "deposits_total": round(float(current.sum())),
        "balance_mean": round(float(current.mean()), 2),
        "balance_median": round(float(current.median()), 2),
    }

    zero = current <= 0
    out["balance_zero_n"] = int(zero.sum())
    out["balance_zero_pct"] = _pct(int(zero.sum()), len(base))

    # ---- bands and concentration ---------------------------------------
    bands = _band(current)
    rows = []
    total_deposits = float(current.sum())
    for label in BAND_ORDER:
        mask = bands == label
        n = int(mask.sum())
        deposits = float(current[mask].sum())
        rows.append([label, n, _pct(n, len(base)), round(deposits),
                     _pct(deposits, total_deposits)])
    out["balance_bands"] = rows

    positive = current[current > 0]
    if len(positive):
        threshold = float(positive.quantile(0.90))
        top_deposits = float(positive[positive >= threshold].sum())
        out["balance_top10_threshold"] = round(threshold)
        out["balance_top10_share"] = _pct(top_deposits, float(positive.sum()), 0)
        out["balance_top10_n"] = int((positive >= threshold).sum())

    # ---- deposit flight risk --------------------------------------------
    if average is not None and average.notna().any():
        delta = current - average.fillna(0)
        out["balance_delta_available"] = True
        high = current >= FLIGHT_RISK_THRESHOLD
        # The proxy count is kept beside the real one on every run: the
        # basis moved a published number, and the size of the move has to
        # be readable on the page it moved on, not reconstructed later.
        proxy = flight_mask(current, average)
        ratio = _inflow_ratio_for(base, config)
        declining = flight_mask(current, average, ratio) if ratio is not None else proxy
        out["flight_risk_basis"] = "inflow" if ratio is not None else "balance proxy"
        out["flight_risk_proxy_n"] = int(proxy.sum())
        out["flight_risk_threshold"] = FLIGHT_RISK_THRESHOLD
        out["flight_risk_n"] = int(declining.sum())
        out["flight_risk_deposits"] = round(float(current[declining].sum()))
        out["flight_risk_decline"] = round(float(delta[declining].abs().sum()))
        out["flight_risk_share_of_high"] = _pct(int(declining.sum()),
                                                int(high.sum()))
    else:
        delta = None
        out["balance_delta_available"] = False
        warn("no Avg Bal; deposit flight risk not computed")

    # ---- sleeping giants: high balance, low card usage -------------------
    # The direct bridge to ARS -- deposits already held, card revenue not.
    if spend is not None:
        active = (current > 0)
        med_bal = float(current[active].median())
        med_spend = float(spend[active].median())
        giants = active & (current >= med_bal) & (spend < med_spend)
        ideal = active & (current >= med_bal) & (spend >= med_spend)
        out["quadrant_median_balance"] = round(med_bal, 2)
        out["quadrant_median_spend"] = round(med_spend, 2)
        out["sleeping_giants_n"] = int(giants.sum())
        out["sleeping_giants_deposits"] = round(float(current[giants].sum()))
        out["sleeping_giants_debit_pct"] = _pct(
            int(has_debit(base[giants]).sum()), int(giants.sum()))
        out["ideal_members_n"] = int(ideal.sum())
        out["ideal_members_debit_pct"] = _pct(
            int(has_debit(base[ideal]).sum()), int(ideal.sum()))

    # ---- PFI score -------------------------------------------------------
    # Balance + activity + tenure. Product breadth is dropped: it needs one
    # row per product per holder, and the ODD is one row per account.
    score = bands.map(BAND_SCORE).fillna(0).astype(int)
    components = ["balance"]

    if swipes is not None and swipes.notna().any():
        pct_rank = swipes.rank(pct=True, method="min") * 100
        activity = pd.cut(pct_rank, bins=[-1, 10, 30, 50, 70, 90, 101],
                          labels=[0, 1, 2, 3, 4, 5]).astype(float).fillna(0)
        score = score + activity.astype(int)
        components.append("activity")

    age = num_col(base, "Account Age")
    if age is not None and age.notna().any():
        tenure = pd.cut(age.fillna(0), bins=[-1, 1, 3, 7, 999],
                        labels=[0, 1, 2, 3]).astype(float).fillna(0)
        score = score + tenure.astype(int)
        components.append("tenure")

    tier = pd.Series("Incidental", index=base.index, dtype=object)
    for low, high_, label in PFI_TIERS:
        tier[(score >= low) & (score <= high_)] = label

    pfi_rows = []
    for label in [t[2] for t in PFI_TIERS]:
        mask = tier == label
        n = int(mask.sum())
        pfi_rows.append([
            label, n, _pct(n, len(base)),
            round(float(current[mask].sum())),
            _pct(float(current[mask].sum()), total_deposits, 0),
            _pct(int(has_debit(base[mask]).sum()), n),
        ])
    out["pfi_components"] = components
    out["pfi_max_score"] = 5 + (5 if "activity" in components else 0) \
        + (3 if "tenure" in components else 0)
    out["pfi_tiers"] = pfi_rows
    if "activity" not in components or "tenure" not in components:
        warn(f"PFI score uses only {', '.join(components)}; tier thresholds "
             f"assume the full 0-13 scale and will skew low")

    # ---- ties back to the ARS program ------------------------------------
    # Balance band against take rate, Reg E opt-in and mailer response, so
    # the deposit view and the program view sit on the same axis.
    carded = has_debit(base)
    tie_rows = []
    responded = (base["# of Responses"] > 0) if "# of Responses" in base.columns else None
    offered = (base["# of Offers"] > 0) if "# of Offers" in base.columns else None

    for label in BAND_ORDER:
        mask = bands == label
        n = int(mask.sum())
        if not n:
            continue
        row = {"band": label, "n": n,
               "take_rate": _pct(int((mask & carded).sum()), n)}
        if responded is not None and offered is not None:
            mailed_n = int((mask & offered).sum())
            row["mailed"] = mailed_n
            row["response_rate"] = _pct(int((mask & responded).sum()), mailed_n)
        tie_rows.append(row)
    out["balance_vs_ars"] = tie_rows

    # Reg E on its own base (eligible personal w/debit), banded the same way.
    rege_base = subsets.personal_with_debit
    if len(rege_base) and "rege_state" not in out:
        rb = pd.to_numeric(rege_base.get("Curr Bal"), errors="coerce").fillna(0)
        rege_bands = _band(rb)
        out["rege_by_balance_band"] = [
            [label, int((rege_bands == label).sum())] for label in BAND_ORDER
        ]

    # Do responders hold their deposits better than non-responders?
    if delta is not None and responded is not None and offered is not None:
        for key, mask in (("responder", offered & responded),
                          ("nonresponder", offered & ~responded)):
            subset = mask & (current >= FLIGHT_RISK_THRESHOLD)
            n = int(subset.sum())
            if not n:
                continue
            out[f"flight_{key}_n"] = n
            out[f"flight_{key}_declining_pct"] = _pct(
                int((subset & (delta < 0)).sum()), n)
        if out.get("flight_responder_declining_pct") is not None \
                and out.get("flight_nonresponder_declining_pct") is not None:
            out["flight_responder_advantage_pp"] = round(
                out["flight_nonresponder_declining_pct"]
                - out["flight_responder_declining_pct"], 1)

    return out
