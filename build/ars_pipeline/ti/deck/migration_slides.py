# Ported from ARS v5 02-Scripts/ars/deck/migration_slides.py at a491b5c (James Gilmore); logic unchanged.
"""Where the swipe tiers moved: the then-by-now matrix migration.py has
computed since it landed and nothing drew (#245). A table, not a heat
map: the cells are account counts and the reader wants the numbers.

RPE (Sheila's 1798 slide review, 2026-10-30, combine group N): four slides told swipe-tier movement
(108, 124, 125, 126). This one carries it: the counts stay, each cell shaded by its share of the row
(a transition heatmap the reader can still read numbers off), and the rail sets responders against
the unmailed and the mailed non-responders, with the repeat responses' ladder beside them."""
from __future__ import annotations

from pptx.dml.color import RGBColor

from .attrition_slides import DEFAULT_MARGIN_L
from .txn_common import RAIL_EDGE

# white to a light steel: navy text stays readable on the darkest cell
_HEAT_LO, _HEAT_HI = (0xFF, 0xFF, 0xFF), (0x9F, 0xB6, 0xCE)


def _heat(share: float) -> RGBColor:
    k = max(0.0, min(1.0, share))
    return RGBColor(*(round(lo + (hi - lo) * k) for lo, hi in zip(_HEAT_LO, _HEAT_HI)))


def tier_matrix(h, t) -> str | None:
    matrix = t.get("mig_matrix") or []
    tiers = t.get("mig_tiers") or []
    if not matrix or not tiers:
        return "Where the tiers moved (missing mig_matrix)"
    up, down, same = (t.get("mig_up_pct") or 0), (t.get("mig_down_pct") or 0), \
        (t.get("mig_same_pct") or 0)
    groups = {r[0]: r for r in (t.get("mig_by_group") or [])}
    resp, notm, mnr = (groups.get("Responder"), groups.get("Not mailed"),
                       groups.get("Mailed non-responder"))
    window = (f", {t['mig_first']} to {t['mig_latest']}"
              if t.get("mig_first") and t.get("mig_latest") else "")
    if resp and notm and notm[2]:
        head = (f"Responders move up a swipe tier at {resp[2]:.0f}%, "
                f"{resp[2] / notm[2]:.1f}x the unmailed rate")
        sub = (f"all cardholders: {up:.0f}% up, {same:.0f}% same, {down:.0f}% down{window}; "
               f"rows are the tier then, columns the tier now")
    else:
        head = (f"{up:.0f}% of cardholders moved up a swipe tier in a year, "
                f"{down:.0f}% moved down")
        sub = ("rows are the tier a year ago, columns the tier now; each cell is "
               "accounts. The diagonal stayed put")
    slide, top = h["slide"]((head, sub), "Where the tiers moved")
    table = [["Then → now"] + [str(c) for c in tiers]]
    shares = {}
    for r, (label, row) in enumerate(zip(tiers, matrix), start=1):
        table.append([str(label)] + [f"{int(v):,}" for v in row])
        total = sum(row) or 1
        for c, v in enumerate(row, start=1):
            shares[(r, c)] = v / total
    left = h.get("MARGIN_L", DEFAULT_MARGIN_L)
    h["table"](slide, table, left, top + 0.1, RAIL_EDGE - left,
               cell_fill=lambda r, c: _heat(shares[(r, c)]) if (r, c) in shares else None)
    items = []
    if resp:
        items.append(("Responders up", f"{resp[2]:.0f}%", f"of {resp[1]:,} accounts"))
    if notm:
        items.append(("Not mailed up", f"{notm[2]:.0f}%", f"of {notm[1]:,} accounts"))
    if mnr:
        items.append(("Mailed, no response", f"{mnr[2]:.0f}%", "moved up"))
    items.append(("All cardholders", f"{up:.0f}% up", f"{down:.0f}% down"))
    ladder = dict(t.get("ladder_movement") or [])
    moves = sum(ladder.values())
    if moves:
        items.append(("Repeat responses", f"{100 * ladder.get('Up', 0) / moves:.0f}% up",
                      "vs their best prior tier"))
    h["rail"](slide, items, top=top)
    return None
