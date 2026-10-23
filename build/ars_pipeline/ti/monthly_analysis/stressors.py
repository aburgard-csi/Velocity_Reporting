# Ported from ARS v5 02-Scripts/ars/monthly_analysis/stressors.py at a491b5c (James Gilmore); logic unchanged.
"""The stressor count: how many named conditions an account trips at once.

Charles Baker's point in #175 was that two or more CONCURRENT stressors is the
cut worth acting on, not any single warning. retention.py already proved the
pattern on three of its own spend signals (`signals >= 2`); this generalises it
to every registered condition.

The count is a summary, never a substitute. Every raw value that produced a
flag travels beside it, in the frame and in the CSV, because a rank nobody can
reproduce is a rank nobody will act on. Delete this module and every chapter
below it still reports exactly what it reported before.

Nested conditions collapse: gone_quiet implies retention_at_risk, so an
account silent for three months scores one point for the one behaviour.

Base: accounts open at the anchor -- the only ones anything can still be done
about. Closed accounts are the outcome a calibration report would measure
against, not a population to score.

Keys: stress_* .
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..core.conditions import CONDITIONS, available, evaluate
from ..core.facts import Facts, build_facts
from .attrition import hazard_rows, peak_band

BASE_LABEL = "Open at anchor"

# A condition true of almost every account carries no information: it cannot
# separate anyone from anyone. In practice it means a join failed and the
# predicate defaulted, which is exactly how an empty deposits file made "No
# recurring deposit" fire on all 81,081 accounts of a real book. Refused and
# named, rather than counted.
SATURATION_PCT = 95.0

# Raw values carried alongside every flag. None of these is a threshold; they
# are the numbers a person needs in order to believe the flag.
# Each is included only when present, so an ODD-only run simply carries fewer
# columns rather than failing -- the competitor pair is attached by the TXN
# pipeline and absent otherwise.
RAW_COLUMNS = ("account_id", "entity_id", "branch_name", "prod_desc",
               "tenure_years", "curr_bal", "avg_bal", "balance_delta",
               "spend_recent", "spend_prior", "spend_ratio", "months_quiet",
               "competitor_dollars", "competitor_institutions")


def count_stressors(facts: Facts) -> pd.DataFrame:
    """One row per account: every flag, every raw value, the count and names."""
    names = available(facts)
    flags = evaluate(facts, names)

    # Collapse nesting: a condition that implies another adds no point when
    # its parent already fired.
    scored = flags.copy()
    for name in names:
        parent = CONDITIONS[name].nests_within
        if parent and parent in scored.columns:
            scored[name] = scored[name] & ~flags[parent]

    out = facts.frame[[c for c in RAW_COLUMNS if c in facts.frame.columns]].copy()
    for name in names:
        out[name] = flags[name]
    out["count"] = scored[names].sum(axis=1).astype(int) if names else 0
    out["available"] = len(names)
    out["names"] = ["; ".join(CONDITIONS[n].label for n in names if row[n])
                    for _, row in flags.iterrows()]
    return out


def write_roster(frame: pd.DataFrame, lists_dir) -> str:
    """The ranked list: most concurrent stressors first, dollars as the
    tie-break. Written beside the competition and flight-risk lists a branch
    already works from."""
    lists_dir = Path(lists_dir)
    lists_dir.mkdir(parents=True, exist_ok=True)
    ordered = frame.sort_values(["count", "curr_bal"], ascending=[False, False])
    path = lists_dir / "stressors.csv"
    ordered.to_csv(path, index=False)
    return str(path)


def compute(subsets, config: dict, warn) -> dict:
    """Section contract: (subsets, config, warn) -> dict of stress_* keys."""
    base = subsets.eligible
    if not len(base):
        return {}

    facts = build_facts(base, config, subsets.anchor)
    for message in facts.warnings:
        warn(f"stressors: {message}")

    # run.py stashes the loaded deposits here when the client sent the file.
    # Absent, the deposit conditions simply report as not built.
    cadence = config.get("_deposit_cadence")
    if cadence is not None:
        from ..core.facts import attach_deposits

        attach_deposits(facts, cadence, config.get("_deposit_monthly"))
        matched = facts.deposit_match_pct
        if matched is not None and matched < 5.0:
            warn(f"stressors: the deposits file joined only {matched}% of "
                 f"accounts. The account key does not line up -- deposit "
                 f"conditions would read as 'nobody has a recurring deposit' "
                 f"across the whole book. Check the ODD's account id against "
                 f"the file's hashed_account.")
        out_match = matched

    # The hazard-peak condition places an account in the band THIS book's
    # closures actually peak in, so it needs the chapter's own curve. Derived
    # from attrition's own function rather than a second copy of the bucket
    # arithmetic; None when no bucket named a peak, and the condition then
    # flags nobody rather than everybody.
    end = pd.Timestamp(subsets.anchor.year, subsets.anchor.month, 1) \
        + pd.offsets.MonthEnd(0)
    facts.peak_tenure_band = peak_band(
        hazard_rows(facts.frame["opened"], facts.frame["closed"], end))

    facts.frame = facts.frame[facts.frame["is_open"]]
    if not len(facts.frame):
        warn("stressors: no accounts open at the anchor; section skipped")
        return {}

    saturated = []
    for name in available(facts):
        share = 100 * float(evaluate(facts, [name])[name].mean())
        if share >= SATURATION_PCT:
            saturated.append((name, share))
    if saturated:
        for name, share in saturated:
            warn(f"stressors: '{CONDITIONS[name].label}' is true of "
                 f"{share:.1f}% of the base, at or above the "
                 f"{SATURATION_PCT}% saturation floor. A condition that flags "
                 f"nearly everyone cannot separate anyone; this is a failed "
                 f"join or a defaulted predicate, not a finding. Excluded.")
        facts.frame = facts.frame.drop(
            columns=[c for n, _ in saturated for c in CONDITIONS[n].requires
                     if c in facts.frame.columns], errors="ignore")

    frame = count_stressors(facts)
    names = [n for n in CONDITIONS if n in frame.columns]
    skipped = [CONDITIONS[n].label for n in CONDITIONS if n not in names]

    out: dict = {
        "stress_base": BASE_LABEL,
        "stress_n": int(len(frame)),
        "stress_available": [CONDITIONS[n].label for n in names],
        "stress_skipped": skipped,
        "stress_deposit_match_pct": out_match if cadence is not None else None,
        "stress_saturated": [[CONDITIONS[n].label, round(s, 1)]
                             for n, s in saturated],
    }
    if skipped:
        warn(f"stressors: {len(skipped)} condition(s) not buildable from this "
             f"client's files ({', '.join(skipped)}); the count reads "
             f"'n of {len(names)} available' and is not comparable to a client "
             f"scored on a different set")

    rows = []
    for value in sorted(frame["count"].unique()):
        cut = frame[frame["count"] == value]
        rows.append([int(value), int(len(cut)),
                     round(100 * len(cut) / len(frame), 1),
                     round(float(cut["curr_bal"].fillna(0).sum()))])
    out["stress_by_count"] = rows
    out["stress_by_count_columns"] = ["stressors", "accounts", "pct_of_base",
                                      "deposits"]

    multi = frame[frame["count"] >= 2]
    out["stress_2plus_n"] = int(len(multi))
    out["stress_2plus_pct"] = round(100 * len(multi) / len(frame), 1)
    out["stress_2plus_deposits"] = round(float(multi["curr_bal"].fillna(0).sum()))

    # Handed to run.py, which owns every path. Popped the moment it arrives,
    # so a DataFrame never reaches leaks, synthesis or the JSON encoder.
    out["_stress_frame"] = frame
    return out
