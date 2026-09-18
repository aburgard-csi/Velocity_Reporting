"""Monthly Analysis metrics -- orchestrator.

Ported from v5 without the ICS and deposit sections (not in this branch).

Scope: subsets, DCTR, Reg E, mail/response. Attrition, value, insights and
TXN are separate modules, not yet built.

One rule governs every calculator: NO MONTH LITERAL IN EXECUTABLE CODE.
Windows derive from the anchor, which is read from the data.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ..core.periods import Month, data_month, trailing
from ..core.subsets import Subsets, build_subsets, has_debit
from . import dctr as _dctr
from . import mailer as _mailer
from . import mailer_detail as _mailer_detail
from . import mailer_summary as _mailer_summary
from . import profile as _profile
from . import attrition as _attrition
from . import balance as _balance
from . import interchange as _interchange
from . import retention as _retention
from . import cohort as _cohort
from . import leaks as _leaks
from . import rege as _rege
from . import od_limit as _od_limit
from . import migration as _migration
from . import extract_check as _extract_check
from . import overview as _overview
from . import lifecycle_report as _lifecycle
from . import stressors as _stressors
from . import synthesis as _synthesis
from . import value as _value

# extract_check runs FIRST: it reports the shape every section below
# assumes, so a warning about a missing month or a duplicated account
# appears before the figures that would be distorted by it.
SECTIONS = [("extract_check", _extract_check.compute), ("overview", _overview.compute), ("dctr", _dctr.compute), ("rege", _rege.compute), ("od_limit", _od_limit.compute), ("migration", _migration.compute),
            ("mailer", _mailer.compute), ("mailer_detail", _mailer_detail.compute), ("mailer_summary", _mailer_summary.compute), ("cohort", _cohort.compute), ("profile", _profile.compute), ("attrition", _attrition.compute), ("balance", _balance.compute), ("interchange", _interchange.compute), ("retention", _retention.compute), ("stressors", _stressors.compute), ("lifecycle", _lifecycle.compute),
            ("value", _value.compute)]


def compute(df: pd.DataFrame, config: dict, anchor: Month | None = None,
            txn: dict | None = None) -> tuple[dict[str, Any], list[str]]:
    """Compute all in-scope metrics. Returns (metrics, warnings). `txn` is a
    prior transaction run's txn_metrics.json for the same period; synthesis
    reads it for the TXN opportunity and scorecard items."""
    warnings: list[str] = []

    def warn(message: str) -> None:
        warnings.append(message)

    resolved = anchor or data_month(df.columns)
    if resolved is None:
        return {}, ["no month-tagged transaction columns; nothing computed"]

    subsets = build_subsets(df, config, resolved)
    warnings.extend(subsets.warnings)

    metrics: dict[str, Any] = {
        "data_month": resolved.iso,
        "anchor_tag": resolved.tag,
        "l12m_start": subsets.l12m_start.strftime("%Y-%m") if subsets.l12m_start is not None else None,
        **subsets.sizes(),
        "eligibility_funnel": [
            [s.label, s.count, s.pct_of_total, s.dropoff_pct] for s in subsets.funnel
        ],
    }
    if metrics["n_total"]:
        metrics["eligibility_rate"] = round(
            100 * metrics["n_eligible"] / metrics["n_total"], 1)
    if subsets.funnel:
        drops = [s for s in subsets.funnel[1:] if s.dropoff_pct]
        if drops:
            worst = max(drops, key=lambda s: s.dropoff_pct)
            metrics["biggest_dropoff"] = [worst.label, worst.dropoff_pct]

    # G and O need the transaction chapter's own output. It already arrives
    # here; it simply was not reaching the sections. Stashed the same way
    # run.py stashes the deposits frame, and popped by nobody -- it is a dict,
    # so the JSON encoder does not care.
    if txn:
        config = dict(config, _txn=txn)

    for name, fn in SECTIONS:
        try:
            metrics.update(fn(subsets, config, warn))
        except Exception as exc:
            warn(f"{name} failed: {type(exc).__name__}: {exc}")

    # Leaks run last: they read the other sections' tables rather than the
    # frame, so every rate they compare against is already computed.
    try:
        metrics.update(_leaks.compute(metrics, config, warn))
    except Exception as exc:
        warn(f"leaks failed: {type(exc).__name__}: {exc}")

    # Price the leaks once both the leak table and the per-unit values exist.
    try:
        metrics.update(_value.apply_to_leaks(metrics))
    except Exception as exc:
        warn(f"leak pricing failed: {type(exc).__name__}: {exc}")

    # Synthesis reads metrics only and must see everything above. TXN keys
    # ride alongside (ODD keys win a collision); syn_* is all it returns.
    try:
        seen = {**txn, **metrics} if txn else metrics
        if txn and txn.get("txn_anchor") and txn.get("txn_anchor") != metrics.get("data_month"):
            warn(f"txn metrics anchored to {txn.get('txn_anchor')}, ODD data month "
                 f"{metrics.get('data_month')}; synthesis TXN items may be stale")
        metrics.update(_synthesis.compute(seen, config, warn))
    except Exception as exc:
        warn(f"synthesis failed: {type(exc).__name__}: {exc}")

    return metrics, warnings
