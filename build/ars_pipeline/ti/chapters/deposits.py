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
from ti.deck import combine

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
    # R7 (2026-11-05): the daily series, and what is spent in the days after a deposit
    "daily_deposits": "Deposits, day by day",
    "deposit_timing": "What is spent after a deposit",
    "deposit_overlay_first": "Deposits against the most deposit-timed category",
    "deposit_overlay_second": "Deposits against the second most deposit-timed category",
    "deposit_overlay_bnpl": "Deposits against buy now, pay later",
}


# two one-chart slides as one (Aaron, 2026-11-02; ti/deck/combine.py)
COMBINED = (
    ("recurring_credits", "income_shape", "How members are paid",
     "How members are paid, and how steady it is",
     "Left: how regular each member's pay rhythm is. Right: how much total inflow varies month to month.",
     "how_members_are_paid"),
    ("credits_stopped", "deposit_milestones", "When the pay stops",
     "When the pay stops",
     "Left: members whose regular credit stopped, by month. Right: how long since money last arrived.",
     "when_pay_stops"),
)


def compute(ctx):
    out = odd_sections.balance(ctx)
    out.update(odd_sections.deposit_behaviour(ctx))
    try:                                          # R7's figures never take the chapter's own down
        out.update(odd_sections.deposit_daily(ctx))
    except Exception as exc:
        ctx.warn(f"deposit daily: figures not computed ({type(exc).__name__}: {exc})")
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
    builders, titles = combine.apply([getattr(S, name) for name in TITLES], TITLES, COMBINED)
    return deck.run(builders, titles, ctx.pack.get("metrics") or {})


CHAPTER = cut.Chapter("TI_DEP", "Deposits", "Paydays · Income · Primacy",
                      "How money arrives: paydays, income, primacy", stats, build, compute)
