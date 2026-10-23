# Ported from ARS v5 02-Scripts/core/filed/join.py at a491b5c (James Gilmore); logic unchanged.
"""Attach Filed facts to the competitors a client's members pay (comp_institutions)."""
from __future__ import annotations

from pathlib import Path

from .growth import filed_growth
from .resolve import resolve_name

COLUMNS = ["institution", "key", "regulator", "accounts", "pct_of_accounts", "dollars",
           "deposits_latest", "deposits_prior", "growth_pct", "latest_date", "quarters_apart"]

_SHORT_SERIES_SUFFIX = " (no year of filings)"

REQUIRED_CACHE = ("fdic_institutions", "fdic_locations", "fdic_financials",
                  "ncua_institutions", "ncua_branches", "ncua_trade_names",
                  "ncua_financials", "zip_centroids")


def require_cache(cache: Path) -> None:
    """Raise before anything that would download. The transaction run never fetches."""
    from ti.core.market.sources import SourceError
    missing = [n for n in REQUIRED_CACHE if not (cache / f"{n}.json").exists()]
    if missing:
        raise SourceError(
            f"reference cache incomplete at {cache}: missing {', '.join(missing)}; "
            "run the market build first")


def attach_filed(metrics: dict, store, book, market_record: dict | None) -> None:
    rows = metrics.get("comp_institutions")
    if not rows:
        return
    out, unresolved = [], []
    for r in rows:
        name, accounts, pct, dollars = r[0], r[2], r[3], r[5]
        key = resolve_name(name, book, market_record)
        if key is None:
            unresolved.append(name)
            continue
        g = filed_growth(store.series(key))
        if g is None:
            unresolved.append(f"{name}{_SHORT_SERIES_SUFFIX}")
            continue
        out.append([name, key, store.regulator(key), accounts, pct, dollars,
                    g.deposits_latest, g.deposits_prior, g.growth_pct,
                    g.latest_date, g.quarters_apart])
    out.sort(key=lambda row: (-row[5], row[0]))
    metrics["comp_filed_columns"] = list(COLUMNS)
    metrics["comp_filed"] = out
    metrics["comp_filed_unresolved"] = unresolved


def split_unresolved(names: list[str]) -> tuple[list[str], list[str]]:
    """comp_filed_unresolved into names with no regulator record and names with a short series."""
    no_record, short_series = [], []
    for name in names:
        if name.endswith(_SHORT_SERIES_SUFFIX):
            short_series.append(name[:-len(_SHORT_SERIES_SUFFIX)])
        else:
            no_record.append(name)
    return no_record, short_series
