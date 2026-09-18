"""The stressor count, across both sources: ODD conditions plus competitors.

monthly_analysis/stressors.py runs in the ODD pipeline, which cannot see a
transaction -- so it reports "Banking elsewhere" as a condition it could not
build. This module runs where BOTH frames exist and supplies it.

Nothing is recomputed. The ODD facts come from core.facts, the conditions from
core.conditions, the count from monthly_analysis.stressors, and the competitor
rows are competition.py's own per-account output -- the same rows overlay.py
consumes. This module only joins them, which is the rule hotspots.py already
follows for closures against leakage.

Keys: stress_txn_* . Kept distinct from the ODD run's stress_* so the two are
never mistaken for each other: they sit on different bases and count a
different number of conditions.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..core.conditions import CONDITIONS
from ..core.facts import attach_competitors, build_facts
from ..monthly_analysis.attrition import hazard_rows, peak_band
from ..monthly_analysis.stressors import count_stressors

BASE_LABEL = "Open at anchor, transacting join"


def compute(odd: pd.DataFrame | None, competitor_rows, anchor,
            config: dict, lists_dir: Path | None, warn) -> tuple[dict, dict]:
    """anchor is a core.periods.Month -- the same one the ODD chapter used."""
    out: dict = {}
    outputs: dict = {}
    if odd is None:
        warn("stressors_txn: no ARS enrichment (run the ODD analysis first); "
             "cross-source stressor count skipped")
        return out, outputs
    if competitor_rows is None or not len(competitor_rows):
        warn("stressors_txn: competition produced no per-account rows; "
             "cross-source stressor count skipped")
        return out, outputs

    facts = build_facts(odd, config or {}, anchor)
    end = pd.Timestamp(anchor.year, anchor.month, 1) + pd.offsets.MonthEnd(0)
    facts.peak_tenure_band = peak_band(
        hazard_rows(facts.frame["opened"], facts.frame["closed"], end))
    attach_competitors(facts, competitor_rows)

    facts.frame = facts.frame[facts.frame["is_open"]]
    if not len(facts.frame):
        warn("stressors_txn: no accounts open at the anchor; section skipped")
        return out, outputs

    frame = count_stressors(facts)
    names = [n for n in CONDITIONS if n in frame.columns]
    skipped = [CONDITIONS[n].label for n in CONDITIONS if n not in names]

    out["stress_txn_base"] = BASE_LABEL
    out["stress_txn_n"] = int(len(frame))
    out["stress_txn_available"] = [CONDITIONS[n].label for n in names]
    out["stress_txn_skipped"] = skipped

    rows = []
    for value in sorted(frame["count"].unique()):
        cut = frame[frame["count"] == value]
        rows.append([int(value), int(len(cut)),
                     round(100 * len(cut) / len(frame), 1),
                     round(float(cut["curr_bal"].fillna(0).sum()))])
    out["stress_txn_by_count"] = rows
    out["stress_txn_by_count_columns"] = ["stressors", "accounts",
                                          "pct_of_base", "deposits"]

    multi = frame[frame["count"] >= 2]
    out["stress_txn_2plus_n"] = int(len(multi))
    out["stress_txn_2plus_pct"] = round(100 * len(multi) / len(frame), 1)
    out["stress_txn_2plus_deposits"] = round(
        float(multi["curr_bal"].fillna(0).sum()))
    out["stress_txn_2plus_competitor_dollars"] = round(
        float(multi["competitor_dollars"].fillna(0).sum()))

    if lists_dir is not None:
        lists_dir = Path(lists_dir)
        lists_dir.mkdir(parents=True, exist_ok=True)
        path = lists_dir / "stressors_cross_source.csv"
        frame.sort_values(["count", "curr_bal"], ascending=[False, False]) \
             .to_csv(path, index=False)
        outputs["stressor_roster_txn"] = str(path)
    return out, outputs
