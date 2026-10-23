# Ported from ARS v5 02-Scripts/core/filed/growth.py at a491b5c (James Gilmore); logic unchanged.
"""Filed growth: the latest filed balances against the same point a year earlier."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from .store import Quarter

_MIN_DAYS, _MAX_DAYS, _YEAR = 270, 460, 365
_ONE_DECIMAL = Decimal("0.1")


@dataclass(frozen=True)
class FiledGrowth:
    latest_date: str
    prior_date: str
    deposits_latest: int
    deposits_prior: int
    growth_pct: float
    quarters_apart: int


def filed_growth(series: list[Quarter]) -> FiledGrowth | None:
    with_dep = [q for q in series if q.deposits is not None]
    if len(with_dep) < 2:
        return None
    latest = max(with_dep, key=lambda q: q.date)
    latest_d = date.fromisoformat(latest.date)
    candidates = []
    for q in with_dep:
        gap = (latest_d - date.fromisoformat(q.date)).days
        if _MIN_DAYS <= gap <= _MAX_DAYS:
            candidates.append((abs(gap - _YEAR), gap, q))
    if not candidates:
        return None
    _, gap, prior = min(candidates, key=lambda c: c[0])
    if prior.deposits in (None, 0):
        return None
    exact_pct = Decimal(latest.deposits - prior.deposits) * 100 / Decimal(prior.deposits)
    pct = float(exact_pct.quantize(_ONE_DECIMAL, rounding=ROUND_HALF_UP))
    return FiledGrowth(latest_date=latest.date, prior_date=prior.date,
                       deposits_latest=latest.deposits, deposits_prior=prior.deposits,
                       growth_pct=pct, quarters_apart=int(round(gap / 91.25)))
