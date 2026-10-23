# Ported from ARS v5 02-Scripts/core/deposits/__init__.py at a491b5c (James Gilmore); logic unchanged.
"""The deposits file: rolling 365 days, one row per account per deposit day.

    Acct Number | Date | Dep Count | Dep Amount

What this unblocks, from issue #175: deposit regularity, windfall deposits,
deposit acceleration and deceleration, and a PROBABLE direct-deposit label.

Deposits are CREDITS, which the transaction extract does not carry. That is
why four of the nine stressors were unbuildable until this file existed.

Split into a package so each concern stays readable on its own:

    load        discovery, header mapping, the parquet cache
    behaviour   per-account rhythm, consistency, windfalls
    trend       the monthly grain
    catalogue   the registry of analyses this module could carry

Every public name the products already import stays importable from here, so
`from ti.core.deposits import ...` and `ars.core.deposits`'s star import are
unchanged by the split.
"""

from __future__ import annotations

from .behaviour import (CADENCE_TARGETS, MIN_DEPOSITS_FOR_CADENCE,
                        RECURRING_CV, WINDFALL_MULTIPLE, cadence, windfalls)
from .load import (CACHE_VERSION, CHUNK_ROWS, COLUMN_MAP, KEEP, MIN_MATCH_PCT,
                   NAME_RE, SEARCH_DIRS, LoadReport, find_file, load)
from .trend import monthly

__all__ = [
    # load
    "CACHE_VERSION", "CHUNK_ROWS", "COLUMN_MAP", "KEEP", "MIN_MATCH_PCT",
    "NAME_RE", "SEARCH_DIRS", "LoadReport", "find_file", "load",
    # behaviour
    "CADENCE_TARGETS", "MIN_DEPOSITS_FOR_CADENCE", "RECURRING_CV",
    "WINDFALL_MULTIPLE", "cadence", "windfalls",
    # trend
    "monthly",
]
