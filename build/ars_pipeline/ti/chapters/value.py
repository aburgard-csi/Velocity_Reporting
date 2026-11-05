"""
The Value chapter: what a debit card and a Reg E opt-in are worth, how value climbs with tenure, how
it differs by branch and response group, and where cards and opt-ins leak.

Figures: v5's dctr, rege, interchange and value sections, then its leaks and `apply_to_leaks`
post-passes, in v5's order (`ti/odd_sections.py`), priced at the client's ICRate / NSF_OD_Fee, filled
from the workbook when the config leaves them blank (`ti/workbook_input.py`). Slides: v5's six value
slides, drawn inline in v5's build and lifted into `ti/deck/value_inline.py`. A slide whose figures
are missing is stated, not dropped. The chapter describes the whole book, so it reads the same in
the ARS and ICS lens decks.
"""
from pathlib import Path

from ti import cut, odd_sections

# Group Q (Sheila's 1798 slide review, 2026-10-30): value per account went from four slides to two.
# "The value ladder" is value by tenure; "Where cards do not follow volume" carries the card gaps
# with the branch value spread and the widest card / Reg E divergence on its rail. These two are
# then tossed in `ti/slides.json` (the register is the only place a slide is dropped for every
# client); their builders stay, so a reviewed change can bring either back.
GROUP_Q_TOSS = ("Value per account by branch", "Where branches diverge")

TITLES = {
    "card_and_optin": "What a card and an opt-in earn",
    "value_ladder": "The value ladder",
    "branch_value": "Value per account by branch",
    "responder_value": "What a responder is worth",
    "leaks": "Where cards do not follow volume",
    "divergence": "Where branches diverge",
}


def compute(ctx):
    out = {}
    for section in (odd_sections.dctr, odd_sections.rege, odd_sections.interchange_odd,
                    odd_sections.value):
        out.update(section(ctx))
    out.update(odd_sections.leaks(ctx, out))
    return out


def stats(pack, _lens):
    from ti.deck.labels import money
    m = pack.get("metrics") or {}
    out = []
    if m.get("value_per_card") is not None:
        out.append((money(m["value_per_card"]), "a year per debit card"))
    if m.get("value_per_optin") is not None:
        out.append((money(m["value_per_optin"]), "a year per Reg E opt-in"))
    if m.get("dctr_leak_value") is not None:
        out.append((money(m["dctr_leak_value"]), "a year in the three widest card gaps"))
    return out[:3]


def build(ctx):
    from ti.deck import value_inline as S
    from ti.deck.helpers import Deck
    deck = Deck(ctx, "the ODD extract, priced at the client's interchange rate and NSF fee",
                Path(ctx.art_dir or ".") / "charts" / "value")
    builders = [getattr(S, name) for name in TITLES]
    return deck.run(builders, TITLES, ctx.pack.get("metrics") or {})


CHAPTER = cut.Chapter("TI_VAL", "Value", "Cards · Opt-ins · Leaks",
                      "What a card and an opt-in are worth, and where they leak", stats, build, compute)
