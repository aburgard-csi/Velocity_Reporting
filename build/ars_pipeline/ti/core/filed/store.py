# Ported from ARS v5 02-Scripts/core/filed/store.py at a491b5c (James Gilmore); logic unchanged.
"""The Filed store: cached regulator files to one quarterly series per key."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Quarter:
    date: str
    assets: int | None
    deposits: int | None
    loans: int | None
    net_worth: int | None
    roa: float | None


def _int(v, scale: int = 1) -> int | None:
    try:
        return int(round(float(v) * scale))
    except (TypeError, ValueError):
        return None


def _float(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _iso_from_fdic(repdte: str) -> str:
    return datetime.strptime(str(repdte), "%Y%m%d").strftime("%Y-%m-%d")


def _iso_from_ncua(cycle: str) -> str:
    return datetime.strptime(str(cycle).split(" ")[0], "%m/%d/%Y").strftime("%Y-%m-%d")


def _read(cache: Path, name: str) -> list[dict]:
    path = cache / f"{name}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


class FiledStore:
    """Series and regulator per key. Built once per run; cheap to hold."""

    def __init__(self, cache: Path):
        self._series: dict[str, list[Quarter]] = {}
        self._regulator: dict[str, str] = {}
        for row in _read(cache, "fdic_financials"):
            cert, repdte = _int(row.get("CERT")), row.get("REPDTE")
            if cert is None or repdte is None:
                continue
            key = f"fdic:{cert}"
            self._series.setdefault(key, []).append(Quarter(
                date=_iso_from_fdic(repdte),
                assets=_int(row.get("ASSET"), 1000),
                deposits=_int(row.get("DEP"), 1000),
                loans=_int(row.get("LNLSNET"), 1000),
                net_worth=None,
                roa=_float(row.get("ROA")),
            ))
        for row in _read(cache, "fdic_institutions"):
            reg, cert = row.get("REGAGNT"), _int(row.get("CERT"))
            if reg and cert is not None:
                self._regulator[f"fdic:{cert}"] = str(reg)
        for row in _read(cache, "ncua_financials"):
            cu_number, cycle_date = _int(row.get("CU_NUMBER")), row.get("CYCLE_DATE")
            if cu_number is None or cycle_date is None:
                continue
            key = f"ncua:{cu_number}"
            self._series.setdefault(key, []).append(Quarter(
                date=_iso_from_ncua(cycle_date),
                assets=_int(row.get("ACCT_010")),
                deposits=_int(row.get("ACCT_018")),
                loans=_int(row.get("ACCT_025B")),
                net_worth=_int(row.get("ACCT_997")),
                roa=None,
            ))
        for row in _read(cache, "ncua_institutions"):
            cu_number = _int(row.get("CU_NUMBER"))
            if cu_number is not None:
                self._regulator[f"ncua:{cu_number}"] = "NCUA"
        for key, qs in self._series.items():
            qs.sort(key=lambda q: q.date)

    def series(self, key: str) -> list[Quarter]:
        return list(self._series.get(key, []))

    def regulator(self, key: str) -> str | None:
        return self._regulator.get(key)

    def keys(self) -> set[str]:
        return set(self._series)
