# Ported from v5 02-Scripts/ars/deck/migration_slides.py at 7ba1e63. Logic unchanged; no edits. Here only because the kickoff deck's deckkit facade imports it (v5 layout kept below kickoff/_v5/ so its relative imports hold).
"""Where the swipe tiers moved: the then-by-now matrix migration.py has
computed since it landed and nothing drew (#245). A table, not a heat
map: the cells are account counts and the reader wants the numbers."""
from __future__ import annotations

from .attrition_slides import DEFAULT_MARGIN_L
from .txn_common import RAIL_EDGE


def tier_matrix(h, t) -> str | None:
    matrix = t.get("mig_matrix") or []
    tiers = t.get("mig_tiers") or []
    if not matrix or not tiers:
        return "Where the tiers moved (missing mig_matrix)"
    up, down, same = (t.get("mig_up_pct") or 0), (t.get("mig_down_pct") or 0), \
        (t.get("mig_same_pct") or 0)
    head = (f"{up:.0f}% of cardholders moved up a swipe tier in a year, "
            f"{down:.0f}% moved down")
    sub = ("rows are the tier a year ago, columns the tier now; each cell is "
           "accounts. The diagonal stayed put")
    slide, top = h["slide"]((head, sub), "Where the tiers moved")
    table = [["A year ago → now"] + [str(c) for c in tiers]]
    for label, row in zip(tiers, matrix):
        table.append([str(label)] + [f"{int(v):,}" for v in row])
    left = h.get("MARGIN_L", DEFAULT_MARGIN_L)
    h["table"](slide, table, left, top, RAIL_EDGE - left)
    h["rail"](slide, [("Moved up", f"{up:.0f}%", "of cardholders"),
                      ("Stayed", f"{same:.0f}%", "same tier"),
                      ("Moved down", f"{down:.0f}%", "of cardholders")], top=top)
    return None
