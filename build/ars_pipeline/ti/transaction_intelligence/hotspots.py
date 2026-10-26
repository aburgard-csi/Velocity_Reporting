# Ported from ARS v5 02-Scripts/ars/transaction_intelligence/hotspots.py at a491b5c (James Gilmore); logic unchanged.
"""Attrition x competition, per branch: do we lose accounts where we leak money?

Both halves already existed and never shared an axis. attrition reported the
worst branch for closures; competition reported who takes the money. Nobody
could ask whether they are the same branch.

Neither number is recomputed here. Closure rates come from
attrition.branch_closure_rates -- the function the ARS chapter itself uses --
and leakage comes from competition's comp_by_branch rows. If this section
ever disagrees with either chapter that is a bug in the join, not two
opinions. overlay.py follows the same rule for deposit flight.

The correlation is RANK-based (Spearman). Branch counts are small and one
large branch would otherwise drag a Pearson coefficient on its own; ranks ask
the question actually being asked -- do the branches that lose the most
accounts also leak the most -- without assuming the relationship is linear.

Keys: hot_* .
"""

from __future__ import annotations

import pandas as pd

from ..monthly_analysis.attrition import branch_closure_rates

# A coefficient over four branches is a shape, not a finding.
MIN_BRANCHES_FOR_CORRELATION = 5
# Below this a branch's closure rate swings on one or two accounts.
MIN_AT_RISK = 100

STRENGTH = ((0.7, "strong"), (0.4, "moderate"), (0.2, "weak"))


def _spearman(a: list[float], b: list[float]) -> float | None:
    """Rank correlation, no scipy. None when either side is constant."""
    if len(a) < 3:
        return None
    ra = pd.Series(a).rank()
    rb = pd.Series(b).rank()
    if ra.nunique() < 2 or rb.nunique() < 2:
        return None
    return round(float(ra.corr(rb)), 2)


def _strength(rho: float) -> str:
    for cut, word in STRENGTH:
        if abs(rho) >= cut:
            return word
    return "no meaningful"


def compute(odd: pd.DataFrame | None, comp_branch_rows: list | None,
            anchor, branch_map: dict | None, warn) -> dict:
    """anchor is a core.periods.Month -- the same one attrition windows on."""
    out: dict = {}
    if odd is None:
        warn("hotspots: no ARS enrichment; attrition x competition overlay "
             "skipped")
        return out
    if not comp_branch_rows:
        warn("hotspots: competition produced no per-branch rows; attrition x "
             "competition overlay skipped")
        return out

    closure = branch_closure_rates(odd, anchor, branch_map,
                                   min_at_risk=MIN_AT_RISK)
    if not closure:
        warn(f"hotspots: no branch carries {MIN_AT_RISK} at-risk accounts, or "
             f"the ODD lacks Branch / Date Closed; attrition x competition "
             f"overlay skipped")
        return out

    leak = {str(r[0]): r for r in comp_branch_rows}
    rows = []
    for name, at_risk, closed, rate_pct, acct_years, rate_py in closure:
        match = leak.get(name)
        if match is None:
            continue
        rows.append([name, at_risk, closed, rate_py, match[1], match[3],
                     match[5], match[6]])
    if not rows:
        # The join is the whole point; say so loudly rather than emitting {}.
        warn(f"hotspots: no branch appears in BOTH the attrition and "
             f"competition tables ({len(closure)} attrition branch(es), "
             f"{len(leak)} competition branch(es)) -- the two axes are not "
             f"naming branches the same way")
        return out

    rows.sort(key=lambda r: -(r[3] or 0))
    out["hot_by_branch"] = rows
    out["hot_by_branch_columns"] = [
        "branch", "at_risk", "closed", "closure_per_account_year",
        "transacting_accounts", "leak_pct", "leak_dollars_per_account",
        "top_institution"]
    out["hot_by_branch_basis"] = (
        "closures per account-year at risk from the ARS attrition window, "
        "against competitor penetration among the branch's transacting "
        "accounts; both sides are the chapters' own figures")
    out["hot_branches_joined"] = len(rows)
    out["hot_branches_unjoined"] = len(closure) - len(rows)

    closure_rates = [r[3] for r in rows if r[3] is not None]
    leak_rates = [r[5] for r in rows if r[3] is not None]
    if len(rows) < MIN_BRANCHES_FOR_CORRELATION:
        warn(f"hotspots: {len(rows)} joined branch(es) is under "
             f"{MIN_BRANCHES_FOR_CORRELATION}; the per-branch table is "
             f"reported but no correlation is claimed")
    else:
        rho = _spearman(closure_rates, leak_rates)
        if rho is not None:
            out["hot_rank_correlation"] = rho
            out["hot_rank_correlation_n"] = len(closure_rates)
            out["hot_rank_correlation_basis"] = (
                f"Spearman rank correlation between closures per account-year "
                f"and competitor penetration, across {len(closure_rates)} "
                f"branches; {_strength(rho)} association")

    # The quadrant that matters: above the median on BOTH. Medians rather
    # than fixed cut-offs, so the split follows this client's own book.
    if len(rows) >= MIN_BRANCHES_FOR_CORRELATION and closure_rates:
        mid_close = float(pd.Series(closure_rates).median())
        mid_leak = float(pd.Series(leak_rates).median())
        both = [r[0] for r in rows
                if r[3] is not None and r[3] > mid_close and r[5] > mid_leak]
        out["hot_medians"] = [round(mid_close, 1), round(mid_leak, 1)]
        out["hot_both_above_median"] = both
        out["hot_both_above_median_note"] = (
            "branches losing accounts faster than the book AND leaking to "
            "competitors more than the book -- where retention spend and "
            "competitive response are the same action")
    return out
