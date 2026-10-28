# Ported from ARS v5 02-Scripts/ars/monthly_analysis/extract_check.py at a491b5c (James Gilmore); logic unchanged.
"""Extract validation: is this file shaped the way every other section assumes?

Ported from the legacy toolkit's only reconciliation cell (ICS_cohort/24).
Nothing in v5 checked the extract at all, so a file delivered with a month
missing, with Swipes and Spend covering different months, or with an account
appearing twice, produced numbers that were wrong in ways no section could
detect -- every downstream metric simply computed over whatever arrived.

None of this suppresses a section. It reports what the file IS, and warns
when the shape would quietly distort a figure somewhere else:

  - a month inside the covered range with no Swipes column reads as a month
    of zero activity, which is not the same as a month that did not happen
  - Swipes and Spend covering different months makes spend-per-swipe a ratio
    of two different windows
  - a duplicated account id double-counts in every headcount in the run

Keys: extract_* .
"""

from __future__ import annotations

import pandas as pd

from ..core.periods import Month, columns_for
from ..core.subsets import Subsets

# The paired monthly series every behaviour metric divides one by the other.
PAIRED_SUFFIXES = ("Swipes", "Spend")
ID_COLUMNS = ("Acct Number", "Acct ID")


def _tags(columns, suffix: str) -> list[str]:
    return [c.split()[0] for c in columns_for(columns, suffix)]


def _span(tags: list[str]) -> list[str]:
    """Every month tag from the first to the last, so a gap is visible as an
    absence rather than inferred from a count."""
    if not tags:
        return []
    months = sorted((Month.from_tag(t) for t in tags),
                    key=lambda m: (m.year, m.month))
    first, last = months[0], months[-1]
    out, cur = [], first
    while (cur.year, cur.month) <= (last.year, last.month):
        out.append(cur.tag)
        cur = cur.shift(1)
    return out


def compute(subsets: Subsets, config: dict, warn) -> dict:
    df = subsets.total
    out: dict = {"extract_rows": len(df)}

    present = {s: _tags(df.columns, s) for s in PAIRED_SUFFIXES}
    for suffix, tags in present.items():
        out[f"extract_{suffix.lower()}_months"] = len(tags)
    if not present["Swipes"] and not present["Spend"]:
        warn("extract check: the file carries no monthly Swipes or Spend "
             "columns; every behaviour metric in this run is unavailable")
        return out

    # ---- the two series must cover the same months ----------------------
    swipe_set, spend_set = set(present["Swipes"]), set(present["Spend"])
    only_swipe = sorted(swipe_set - spend_set)
    only_spend = sorted(spend_set - swipe_set)
    out["extract_paired_aligned"] = not (only_swipe or only_spend)
    if only_swipe or only_spend:
        out["extract_swipes_only_months"] = only_swipe
        out["extract_spend_only_months"] = only_spend
        warn(f"extract check: Swipes and Spend do not cover the same months "
             f"(swipes only: {', '.join(only_swipe) or 'none'}; spend only: "
             f"{', '.join(only_spend) or 'none'}). Any per-swipe or "
             f"per-dollar ratio spanning those months divides one window by "
             f"another")

    # ---- gaps inside the covered range ----------------------------------
    for suffix, tags in present.items():
        if not tags:
            continue
        expected = _span(tags)
        missing = [t for t in expected if t not in set(tags)]
        out[f"extract_{suffix.lower()}_span"] = [expected[0], expected[-1]]
        if missing:
            out[f"extract_{suffix.lower()}_missing_months"] = missing
            warn(f"extract check: {len(missing)} month(s) inside the "
                 f"{suffix} range carry no column "
                 f"({', '.join(missing[:6])}{'...' if len(missing) > 6 else ''}). "
                 f"Those months read as zero activity, which is not the same "
                 f"as a month that did not happen")

    # ---- duplicate account ids ------------------------------------------
    id_col = next((c for c in ID_COLUMNS if c in df.columns), None)
    out["extract_id_column"] = id_col
    if id_col is None:
        warn(f"extract check: no {' / '.join(ID_COLUMNS)} column, so "
             f"duplicate accounts cannot be detected")
    else:
        ids = df[id_col].astype(str).str.strip()
        dup_mask = ids.duplicated(keep=False)
        n_dup_rows = int(dup_mask.sum())
        out["extract_duplicate_rows"] = n_dup_rows
        out["extract_distinct_accounts"] = int(ids.nunique())
        if n_dup_rows:
            n_ids = int(ids[dup_mask].nunique())
            warn(f"extract check: {n_dup_rows:,} row(s) share "
                 f"{n_ids:,} account id(s). Every headcount in this run "
                 f"counts those accounts more than once")

    # ---- the anchor's own month must be present -------------------------
    anchor_tag = subsets.anchor.tag
    out["extract_anchor"] = anchor_tag
    absent = [s for s, tags in present.items() if tags and anchor_tag not in tags]
    if absent:
        out["extract_anchor_missing_from"] = absent
        warn(f"extract check: the anchor month {anchor_tag} has no "
             f"{' or '.join(absent)} column, so the newest month in every "
             f"trailing window is not the anchor")
    return out
