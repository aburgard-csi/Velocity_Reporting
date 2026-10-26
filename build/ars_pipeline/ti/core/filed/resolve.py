# Ported from ARS v5 02-Scripts/core/filed/resolve.py at a491b5c (James Gilmore); logic unchanged.
"""A competitor's display name to its Filed key, or None. Never a guess."""
from __future__ import annotations

import re

_ELIDE = re.compile(r"[.']+")
_DROP = re.compile(r"[^A-Z0-9 ]+")
_SPACES = re.compile(r"\s+")
_SYNONYMS = (("FEDERAL CREDIT UNION", "FCU"), ("CREDIT UNION", "CU"),
             ("NATIONAL ASSOCIATION", "NA"), ("SAVINGS BANK", "SB"))


def normalise(name: str) -> str:
    s = _ELIDE.sub("", str(name).upper())
    s = _DROP.sub(" ", s)
    s = _SPACES.sub(" ", s).strip()
    if s.startswith("THE "):
        s = s[4:]
    for long, short in _SYNONYMS:
        s = s.replace(long, short)
    return s


def resolve_name(name: str, book, market_record: dict | None) -> str | None:
    target = normalise(name)
    if not target:
        return None
    scan = ((market_record or {}).get("radius_scan") or {}).get("institutions") or []
    for row in scan:
        if normalise(row.get("name", "")) == target and row.get("key"):
            return row["key"]
    hits = set()
    for inst in getattr(book, "institutions", {}).values():
        names = [inst.name, *getattr(inst, "trade_names", ())]
        if any(normalise(n) == target for n in names):
            hits.add(inst.key)
    return next(iter(hits)) if len(hits) == 1 else None
