# Ported from v5 02-Scripts/ils/pre_go_live/sections/od_status.py at 7ba1e63. Logic unchanged; copied whole.
"""OD status distribution (notebook A3-A4): open personal and open business
accounts by the core's OD status code, the confirmed eligible codes flagged."""

from __future__ import annotations

from ._cut import DC_AMT, DC_CT, ILS_LIMIT, INIT_LIMIT, cut, open_business, open_personal

COL = "OD Status Code (from Core)"


def compute(df, bases, inputs, warn) -> dict:
    if COL not in df.columns or "open" not in bases.masks:
        warn("od_status: needs the OD status column and an open base; skipped")
        return {}
    eligible = set(inputs["codes"].od_eligible)
    m: dict = {}
    for key, pop in (("personal", open_personal(df, bases)),
                     ("business", open_business(df, bases))):
        if pop.empty:
            continue
        rows, names = cut(pop, COL, extras=[INIT_LIMIT, ILS_LIMIT, DC_CT, DC_AMT])
        rows = [r + [r[0] in eligible] for r in rows]
        m[f"pgl_od_status_{key}"] = rows
        m[f"pgl_od_status_{key}_columns"] = names + ["od_eligible"]
    return m
