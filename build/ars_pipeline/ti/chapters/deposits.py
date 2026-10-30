"""
The Deposits chapter: how money arrives — who is paid here, who stopped, income type, tax refunds,
who overdrafts by how they are paid, who banks here first, and what arrives against what leaves.

Figures: v5's balance and deposit-behaviour sections (`ti/odd_sections.py`), on the client's own
deposits extract (`ti/deposits_input.py`). Slides: v5's eleven deposit builders
(`ti/deck/deposit_slides.py`), drawn through `ti/deck/helpers.py`. A client with no deposits file
has every slide decline through `Deck.declined` ("no deposits file", from `deposit_slides._gate`),
never a drawn placeholder of its own, so the frame's rule for declined slides applies to all eleven
and a chapter with nothing to show can go as a whole (Sheila's 1798 review, 2026-10-30: twelve
"Not shown" pages). The chapter describes the whole book, so it reads the same in the ARS and ICS
lens decks (James, 2026-10-23: both lens decks full).
"""
from pathlib import Path

from ti import cut, odd_sections

TITLES = {
    "deposit_overview": "What deposits look like",
    "recurring_credits": "Who is paid here",
    "credits_stopped": "Who stopped being paid here",
    "deposit_milestones": "When money last arrived",
    "deposit_spread": "Where the deposits sit",
    "falling_and_slowing": "Balance falling and inflow slowing",
    "income_shape": "What kind of income",
    "tax_refunds": "Tax refunds",
    "overdraft_and_income": "Who overdrafts, by how they are paid",
    "deposit_primacy": "Who banks here first",
    "inflow_against_outflow": "What arrives against what leaves",
}


def compute(ctx):
    out = odd_sections.balance(ctx)
    out.update(odd_sections.deposit_behaviour(ctx))
    return out


def stats(pack, _lens):
    m = pack.get("metrics") or {}
    out = []
    if m.get("dep_n"):
        out.append((f"{m['dep_n']:,}", "accounts in the deposits file"))
    if m.get("dep_match_pct") is not None:
        out.append((f"{m['dep_match_pct']}%", "matched to the book"))
    return out


def build(ctx):
    from ti.deck import deposit_slides as S
    from ti.deck.helpers import Deck
    deck = Deck(ctx, "the client's deposits extract (Inputs/Deposits) and the ODD extract",
                Path(ctx.art_dir or ".") / "charts" / "deposits")
    builders = [getattr(S, name) for name in TITLES]
    return deck.run(builders, TITLES, ctx.pack.get("metrics") or {})


CHAPTER = cut.Chapter("TI_DEP", "Deposits", "Paydays · Income · Primacy",
                      "How money arrives: paydays, income, primacy", stats, build, compute)
