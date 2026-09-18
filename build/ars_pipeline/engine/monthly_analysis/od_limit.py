"""Overdraft limits.

Two independent facts per account, never collapsed into one another:

    OD limit         -- the anchor-month `OD Limit` amount (blank / 0 / $)
    Reg E election   -- the Reg E column of record, via rege.classify

The ODD carries no OD-status column (`Elig` / `Prog` are ARS-program flags,
not overdraft), so OD eligibility is read from the limit itself:
blank = not OD-eligible, 0 = eligible with no limit, amount = limit granted.
That is an assumption about how the core populates the field and is named
in a warning on every run until confirmed per client.

Six things, in the order a CSM would say them: how many eligible accounts are
OD-eligible; how many of those carry a limit and what the limits are; how
many OD-eligible cardholders opted in; the two gaps (eligible but not opted
in, opted in with no limit); NSF/OD items per account; and the fee revenue
those items represent.

Bases: OD-eligible share and limits divide by Eligible. Opt-in, gaps, items
and revenue divide by Eligible Personal w/Debit that is OD-eligible, so they
reconcile with the Reg E section.

Items are paid + returned combined -- the ODD does not split them -- and are
priced at the client's NSF_OD_Fee, exactly as value.py does. No fee in config
means no revenue figures, not a default.
"""

from __future__ import annotations

import pandas as pd

from ..core.periods import columns_for
from ..core.subsets import Subsets, is_business
from . import rege as _rege
from .value import ITEMS_12, _rate, _twelve_month

TOP_LIMIT_VALUES = 6
# Above this, the core populates the limit for everyone and "OD-eligible" is
# 100% by construction -- the split that carries information is has-limit.
ELIGIBILITY_UNINFORMATIVE_PCT = 99.5


def _column(df: pd.DataFrame, anchor, suffix: str, warn) -> str | None:
    """Anchor-month column for `suffix`, else the latest by parsed date."""
    exact = f"{anchor.tag} {suffix}"
    if exact in df.columns:
        return exact
    cols = columns_for(df.columns, suffix)
    if cols:
        warn(f"no {suffix} column for {anchor.tag}; using {cols[-1]}")
        return cols[-1]
    return None


def _pct(part: int, whole: int) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def compute(subsets: Subsets, config: dict, warn) -> dict:
    base = subsets.eligible
    anchor = subsets.anchor
    if not len(base):
        return {}

    limit_col = _column(base, anchor, "OD Limit", warn)
    if limit_col is None:
        warn("no OD Limit columns in the ODD; overdraft section skipped")
        return {}

    # Coerced here, not in the transform: blank must stay blank.
    limit = pd.to_numeric(base[limit_col], errors="coerce")
    od_eligible = limit.notna()
    has_limit = limit > 0
    if not od_eligible.any():
        warn("every OD Limit is blank; the client may not populate limits")

    n_base, n_elig, n_limit = len(base), int(od_eligible.sum()), int(has_limit.sum())
    elig_pct = _pct(n_elig, n_base)
    eligibility_informative = elig_pct < ELIGIBILITY_UNINFORMATIVE_PCT
    if eligibility_informative:
        warn("OD eligibility read from the OD Limit column (blank = not "
             "eligible, 0 = eligible with no limit); the ODD has no OD status "
             "field -- confirm this is how the core populates it")
    else:
        warn(f"OD Limit is populated for {elig_pct}% of eligible accounts "
             f"({n_base - n_elig:,} blank); OD eligibility cannot be read from "
             f"this file, so the section reports has-limit vs no-limit only")
    business = is_business(base)
    out: dict = {
        "od_limit_column": limit_col,
        "od_base": n_base,
        "od_base_label": "Eligible",
        "od_eligible_n": n_elig,
        "od_eligible_pct": elig_pct,
        "od_eligibility_informative": eligibility_informative,
        "od_blank_n": n_base - n_elig,
        "od_with_limit_pct_of_eligible": _pct(n_limit, n_base),
        "od_eligible_personal_pct": _pct(int((od_eligible & ~business).sum()),
                                         int((~business).sum())),
        "od_eligible_business_pct": _pct(int((od_eligible & business).sum()),
                                         int(business.sum())),
        "od_with_limit_n": n_limit,
        "od_with_limit_pct": _pct(n_limit, n_elig),
    }

    # ---- 2. the limits the client actually uses -------------------------
    amounts = limit[has_limit]
    if len(amounts):
        counts = amounts.value_counts().head(TOP_LIMIT_VALUES)
        out["od_limit_values"] = [[float(v), int(c), _pct(int(c), n_limit)]
                                  for v, c in counts.items()]
        out["od_limit_other_n"] = n_limit - int(counts.sum())
        out["od_limit_other_pct"] = _pct(out["od_limit_other_n"], n_limit)
        out["od_limit_distinct_n"] = int(amounts.nunique())
        out["od_limit_mean"] = round(float(amounts.mean()), 2)
        out["od_limit_median"] = round(float(amounts.median()), 2)

    # ---- 3/4. opt-in and the two gaps, on the Reg E base ------------------
    pwd = subsets.personal_with_debit
    rege_col = _rege._column_of_record(subsets.total, anchor, warn)
    if rege_col is None or not len(pwd):
        return out
    pwd_elig = pwd[od_eligible.reindex(pwd.index, fill_value=False)]
    n_rege_base = len(pwd_elig)
    out["od_rege_base"] = n_rege_base
    out["od_rege_base_label"] = "Eligible Personal w/Debit, OD-eligible"
    if not n_rege_base:
        return out

    # rege.compute already reported unmapped Reg E values; stay quiet here.
    states = _rege.classify(pwd_elig[rege_col], config, lambda _m: None)
    opted = states == _rege.OPT_IN
    pwd_limit = pd.to_numeric(pwd_elig[limit_col], errors="coerce")
    out["od_optin_n"] = int(opted.sum())
    out["od_optin_pct"] = _pct(int(opted.sum()), n_rege_base)
    out["od_eligible_not_optin_n"] = int((~opted).sum())
    out["od_optin_no_limit_n"] = int((opted & ~(pwd_limit > 0)).sum())

    # ---- 5/6. items and fee revenue ---------------------------------------
    items = _twelve_month(pwd_elig, ITEMS_12, "MTD", warn, "NSF/OD items")
    if items is None:
        return out
    items_in, items_out = float(items[opted].sum()), float(items[~opted].sum())
    out["od_items_l12m"] = round(items_in + items_out)
    out["od_items_per_acct_optin"] = round(items_in / int(opted.sum()), 2) \
        if opted.any() else 0.0
    out["od_items_per_acct_not_optin"] = round(items_out / int((~opted).sum()), 2) \
        if (~opted).any() else 0.0

    fee = _rate(config, "NSF_OD_Fee")
    if fee is None:
        warn("NSF_OD_Fee missing; overdraft fee revenue not computed")
        return out
    total = (items_in + items_out) * fee
    out["od_fee_revenue_l12m"] = round(total, 2)
    out["od_fee_optin_share_pct"] = _pct(round(items_in * fee), round(total)) \
        if total else 0.0
    out["od_fee_per_acct_optin"] = round(out["od_items_per_acct_optin"] * fee, 2)
    out["od_fee_per_acct_not_optin"] = round(
        out["od_items_per_acct_not_optin"] * fee, 2)
    return out
