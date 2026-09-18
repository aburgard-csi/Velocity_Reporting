"""Named conditions: one definition each, on a declared base.

Before this module, five of the six at-risk definitions were local variables
inside the function that computed them -- retention's health and high_risk,
attrition's hazard-peak band, ics's survival curves. Only balance.flight_mask
was module-level, which is exactly why overlay.py could reuse it and nothing
could reuse the others. That is not an aggregation gap, it is a visibility
gap, and this is the fix.

A condition is a boolean Series over a Facts frame. Each declares:

    base          the population it is meaningful on, in denominator-law terms
    requires      the fact columns it needs, so a run can report what it could
                  not build instead of silently scoring on fewer signals
    nests_within  another condition it implies, so a count never scores one
                  behaviour twice

Every predicate here DELEGATES to the chapter that owns the definition. This
layer holds no opinions of its own; if it ever disagrees with a chapter that
is a bug in the delegation, not two defensible readings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from .facts import Facts


@dataclass(frozen=True)
class Condition:
    """One named predicate over the fact frame."""

    name: str
    label: str
    base: str
    fn: Callable[[Facts], pd.Series]
    requires: tuple[str, ...]
    nests_within: str | None = None


def _balance_flight(facts: Facts) -> pd.Series:
    """Deposit flight, THE definition -- imported from the chapter that owns
    it so this layer can never hold a second opinion.

    On the account's own inflow once the deposits file is attached; on the
    balance proxy until then. The chapter decides, this layer hands it what
    it has.
    """
    from ..monthly_analysis.balance import flight_mask

    frame = facts.frame
    ratio = frame["deposit_ratio"] if "deposit_ratio" in frame.columns else None
    if ratio is not None and not ratio.notna().any():
        ratio = None
    return flight_mask(frame["curr_bal"].fillna(0), frame["avg_bal"], ratio)


def _retention_at_risk(facts: Facts) -> pd.Series:
    """Declining, Cooling, Dormant or Never activated -- the chapter's own
    classification, imported rather than re-derived."""
    from ..monthly_analysis.retention import at_risk_mask, classify_health

    health = classify_health(
        facts.frame["spend_recent"], facts.frame["spend_prior"],
        facts.frame["months_quiet"], facts.frame["has_debit"])
    return at_risk_mask(health)


def _gone_quiet(facts: Facts) -> pd.Series:
    """No spend for three consecutive months, counting back from the anchor."""
    from ..monthly_analysis.retention import DORMANT_ZERO_MONTHS

    return facts.frame["months_quiet"] >= DORMANT_ZERO_MONTHS


def _hazard_peak_tenure(facts: Facts) -> pd.Series:
    """Sitting in the tenure band where this book's closures actually peak.

    The band comes from the chapter's own hazard curve, so this can never
    disagree with the table attrition.py prints. When no bucket carried enough
    resolved accounts to name a peak, nothing is flagged -- an unnamed peak
    must mean nobody, never everybody.
    """
    if facts.peak_tenure_band is None:
        return pd.Series(False, index=facts.frame.index)
    low, high = facts.peak_tenure_band
    months = facts.frame["tenure_years"] * 12
    return (months >= low) & (months < high)


def _competitor_carrying(facts: Facts) -> pd.Series:
    """Paying a named competitor institution.

    Only the transaction file can see this, so the fact columns are attached
    by the TXN pipeline and absent on an ODD-only run -- where `available()`
    then reports this condition as not built rather than scoring without it.
    The institutions come from competition.py's own classification; this layer
    never decides what counts as a competitor.
    """
    return facts.frame["competitor_dollars"] > 0


# "No recurring deposit" is NOT registered as a scoring condition.
#
# Charles named it in #175 and it is a real stressor -- about a MEMBER. Payroll
# lands in one account per member, so on RALLY's book of 329,691 accounts most
# accounts legitimately have no recurring deposit: they are the savings, the
# second checking, the certificate. Scored at account grain the condition was
# true of 97.3% of the base, and the saturation guard rightly refused it.
#
# This is the same objection that keeps "only one product relationship" out of
# the registry: both are member-level questions and the ODD carries no member
# key. Computing them at account level and labelling them "member" would be
# silently wrong on every multi-account member.
#
# probable_direct_deposit is still derived and still travels in the roster --
# it is genuinely useful beside an account -- it just cannot carry a point in
# a count until a CIF arrives. See docs/.../lifecycle-event-time-design.md.


def _deposit_decelerating(facts: Facts) -> pd.Series:
    """Deposits over the recent months running below the prior months.

    Same ratio and the same windows as the spend health condition, so
    "declining" means one thing across both series.
    """
    from ..monthly_analysis.retention import DECLINING_RATIO

    return facts.frame["deposit_ratio"] < DECLINING_RATIO


CONDITIONS: dict[str, Condition] = {
    c.name: c for c in (
        Condition(
            name="retention_at_risk",
            label="Spend health declining",
            base="Eligible",
            fn=_retention_at_risk,
            requires=("spend_recent", "spend_prior", "months_quiet", "has_debit"),
        ),
        Condition(
            name="balance_flight",
            label="Deposits leaving",
            base="Eligible",
            fn=_balance_flight,
            requires=("curr_bal", "avg_bal"),
            # On the inflow basis every flight account IS a decelerating
            # account with a high balance. The nesting only collapses when
            # both are available, which is exactly when the basis is inflow.
            nests_within="deposit_decelerating",
        ),
        Condition(
            name="gone_quiet",
            label="Gone quiet",
            base="Eligible",
            fn=_gone_quiet,
            requires=("months_quiet",),
            # Three silent months makes an account Dormant, which is at risk.
            # Scoring both would give one behaviour two points.
            nests_within="retention_at_risk",
        ),
        Condition(
            name="competitor_carrying",
            label="Banking elsewhere",
            base="Transacting",
            fn=_competitor_carrying,
            requires=("competitor_dollars",),
        ),
        Condition(
            name="deposit_decelerating",
            label="Deposits slowing",
            base="Eligible",
            fn=_deposit_decelerating,
            requires=("deposit_ratio",),
        ),
        Condition(
            name="hazard_peak_tenure",
            label="In the hazard-peak tenure band",
            base="Open at anchor",
            fn=_hazard_peak_tenure,
            requires=("tenure_years",),
        ),
    )
}


def available(facts: Facts) -> list[str]:
    """Conditions whose inputs are all present and not entirely null.

    Reported rather than assumed: a count of "2 of 3" is a different finding
    from "2 of 6", and a reader who cannot see which is comparing two clients
    that are not comparable.
    """
    names = []
    for name, cond in CONDITIONS.items():
        cols = [c for c in cond.requires if c in facts.frame.columns]
        if len(cols) == len(cond.requires) and \
                all(facts.frame[c].notna().any() for c in cols):
            names.append(name)
    return names


def evaluate(facts: Facts, names: list[str] | None = None) -> pd.DataFrame:
    """One boolean column per condition, on the facts frame's index."""
    wanted = names if names is not None else available(facts)
    out = pd.DataFrame(index=facts.frame.index)
    for name in wanted:
        out[name] = CONDITIONS[name].fn(facts).fillna(False).astype(bool)
    return out
