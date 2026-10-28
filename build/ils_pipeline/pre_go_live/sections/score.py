# Ported from v5 02-Scripts/ils/pre_go_live/sections/score.py at 7ba1e63. Logic unchanged; copied whole.
"""Change in score (notebook A5-A6, A8): what happens to the limit when the
ILS proposal replaces the core's, cut by UpOrDown, on four named bases --
personal, business, eligible, opted-in."""

from __future__ import annotations

from ._cut import DC_CT, DEP_AMT, DEP_CT, ILS_LIMIT, INIT_LIMIT, cut

COL = "UpOrDown from Initial OD Limit"
UP, DOWN = "Score100Plus", "ScoreLess100"
BASES = [("personal", ("open", "personal")),
         ("business", ("open", "business")),
         ("eligible", ("eligible",)),
         ("opted_in", ("opted_in",))]


def compute(df, bases, inputs, warn) -> dict:
    if COL not in df.columns:
        warn("score: no UpOrDown column; section skipped")
        return {}
    m: dict = {}
    headline: dict = {}
    for key, needed in BASES:
        if any(n not in bases.masks for n in needed):
            continue
        mask = bases[needed[0]]
        for n in needed[1:]:
            mask = mask & bases[n]
        pop = df[mask]
        if pop.empty:
            continue
        rows, names = cut(pop, COL, extras=[INIT_LIMIT, ILS_LIMIT, DEP_CT, DEP_AMT, DC_CT])
        m[f"pgl_score_{key}"] = rows
        m[f"pgl_score_{key}_columns"] = names
        by = {r[0]: r[1] for r in rows}
        headline[key] = {"up": by.get(UP, 0), "down": by.get(DOWN, 0),
                         "same": by.get("Same", 0), "base": int(mask.sum())}
    m["pgl_score_headline"] = headline
    return m
