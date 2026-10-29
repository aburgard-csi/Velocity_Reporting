"""The pre-go-live deck's matrix chapter: Tim Barrett's matrix-validation readers, on the client's dump.

`load(folder)` parses the matrix validation export beside the extract with Tim's parser
(ils_pipeline/matrix_validation, copied unchanged) and `facts(S)` returns what the slides draw: account
types with their min/max limits, the OD status code mapping, the overrides in priority order, the factor
grids, the trend repositories and the tier steps.

One correction is made here, never in Tim's copy: the 2026-10 exports (1737 TNB, 1759 First Central)
misspell a banner as "ACCCOUNT TYPES AND MIN/MAX LIMITS", which his reader looks up by its right spelling,
so without it no account type is found (and no override or trigger with them).
"""
from __future__ import annotations

import re
from pathlib import Path

from ils_pipeline.matrix_validation import matrix_deck as M
from ils_pipeline.matrix_validation.matrix_report import parse

ALIASES = {"ACCCOUNT TYPES AND MIN/MAX LIMITS": "ACCOUNT TYPES AND MIN/MAX LIMITS"}
MATRIX_RX = re.compile(r"matrix.?validation", re.I)


def find(folder):
    """The matrix validation export beside the extract (.txt or .csv), newest name last, or None."""
    hits = sorted(p for p in Path(folder).iterdir()
                  if p.is_file() and p.suffix.lower() in (".txt", ".csv") and MATRIX_RX.search(p.name))
    return hits[-1] if hits else None


def load(folder):
    path = find(folder)
    if path is None:
        return None, None
    S = parse(str(path))
    for wrong, right in ALIASES.items():
        if wrong in S and right not in S:
            S[right] = S.pop(wrong)
    return S, path


def facts(S) -> dict:
    types, codes, settings = M.detect_types(S)
    cats = M.categories(S)
    return {
        "types": types,
        "codes": codes,
        "settings": settings,
        "od_mapping": M._section(S, "OD STATUS CODE MAPPING"),
        "overrides": M.overrides_by_type(S, types) if types else {},
        "grids": {c: M.range_grid(S, c, types) for c in cats} if types else {},
        "trends": M.trend_repositories(S),
        "triggers": M.trend_trigger_rows(S, types) if types else [],
        "tiers": M.tier_summary(S),
    }
