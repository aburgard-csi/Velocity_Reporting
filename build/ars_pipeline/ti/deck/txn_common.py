# Ported from ARS v5 02-Scripts/ars/deck/txn_common.py at a491b5c (James Gilmore); logic unchanged.
"""Shared helpers for the transaction-chapter slide modules."""
from __future__ import annotations

from . import labels

# A rail claims the right ~3.4in of the slide (ics_slides.py:42-45), so a
# chart sharing a slide with one has to stop short of it.
RAIL_EDGE = 9.90


def money(v) -> str:
    """The deck's money grammar. "n/a" for a missing value is kept for the slides that still call
    it that way; a tile or cell with no value should be left out and stated instead (`absent_note`,
    Sheila's 1798 review, 2026-10-30)."""
    return labels.money(v) if v is not None else "n/a"


def absent_note(names, noun="bands") -> str:
    """The things a slide left out for want of a value, named briefly for a stated note: up to three
    by name, more as a count with the first and last ("12 bands, month 1 ... month 12")."""
    names = [str(n) for n in names if str(n)]
    if len(names) <= 3:
        return ", ".join(names)
    return f"{len(names)} {noun}, {names[0]} ... {names[-1]}"


def pct_rows(rows, idx):
    return [r[idx] for r in rows]


def rail_or_full(h, has_rail: bool) -> float:
    return RAIL_EDGE if has_rail else h["RIGHT_EDGE"]
