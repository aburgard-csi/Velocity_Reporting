"""
The Economics chapter: what the program has earned and what it costs the client — the program P&L
by offer, the 2:1 guarantee, where the month's revenue came from, what each offer has earned, and
what an account earns as it climbs the swipe bands.

Figures: the client's ARS Workbook (`ti/workbook_input.py`, `wb_*`) and 2:1 deferral tracker
(`ti/deferred_input.py`, `gt_*`), read before the chapters run (`ti_build.compute_pack`), so this
chapter computes nothing of its own. Slides: v5's five economics slides, drawn inline in v5's build
and lifted into `ti/deck/economics_inline.py`, in v5's main-path order with the guarantee right after
the P&L (James, 2026-08-22). A client with no workbook or tracker gets each slide stated, not
dropped. The chapter describes the whole program, so it reads the same in the ARS and ICS lens decks.
Program P&L is the one economics slide (Sheila's 1798 slide review, 2026-10-30, group M): with the
DiD estimate on hand it sets booked revenue against it in a two-column table, which is why the
campaign hero and Revenue frames are tossed in `ti/slides.json`.
"""
from pathlib import Path

from ti import cut

TITLES = {
    "program_pnl": "Program P&L by offer",
    "guarantee": "The 2:1 guarantee",
    "wave_mix": "Where the month's revenue came from",
    "wave_totals": "What each offer has earned",
    "lift_matrix": "What an account earns as it climbs",
}


def compute(_ctx):
    return {}


def stats(pack, _lens):
    from ti.deck.labels import money
    m = pack.get("metrics") or {}
    out = []
    if m.get("wb_revenue_ltd") is not None:
        out.append((money(m["wb_revenue_ltd"]), "program revenue, life to date"))
    if m.get("wb_profit_ltd") is not None:
        out.append((money(m["wb_profit_ltd"]), "program profit, life to date"))
    if (m.get("gt_deferred_balance") or 0) > 1 and m.get("gt_state") != "clear":
        out.append((money(m["gt_deferred_balance"]), "deferred under the 2:1 guarantee"))
    return out[:3]


def build(ctx):
    from ti.deck import economics_inline as S
    from ti.deck.helpers import Deck
    deck = Deck(ctx, "the client's ARS Workbook (Inputs/ARS Workbooks) and 2:1 deferral tracker "
                     "(Inputs/Deferred Billing)",
                Path(ctx.art_dir or ".") / "charts" / "economics")
    builders = [getattr(S, name) for name in TITLES]
    return deck.run(builders, TITLES, ctx.pack.get("metrics") or {})


CHAPTER = cut.Chapter("TI_ECON", "Economics", "Revenue · Fees · Guarantee",
                      "What the program has earned, and what it costs", stats, build, compute)
