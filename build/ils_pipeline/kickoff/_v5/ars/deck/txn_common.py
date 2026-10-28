# Ported from v5 02-Scripts/ars/deck/txn_common.py at 7ba1e63. Logic unchanged; no edits. Here only because the kickoff deck's deckkit facade imports it (v5 layout kept below kickoff/_v5/ so its relative imports hold).
"""Shared helpers for the transaction-chapter slide modules."""
from __future__ import annotations

from . import labels

# A rail claims the right ~3.4in of the slide (ics_slides.py:42-45), so a
# chart sharing a slide with one has to stop short of it.
RAIL_EDGE = 9.90


def money(v) -> str:
    return labels.money(v) if v is not None else "n/a"


def pct_rows(rows, idx):
    return [r[idx] for r in rows]


def rail_or_full(h, has_rail: bool) -> float:
    return RAIL_EDGE if has_rail else h["RIGHT_EDGE"]
