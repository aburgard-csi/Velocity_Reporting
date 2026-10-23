"""
The ICS accounts chapter: the accounts the ICS programme opened, found in the ODD by joining the
direct-mail and referral lists (`ti/lens.py`), against the rest of the book — acquisition,
activation, cohorts, sustained activity, usage, quality, closure, branches, primacy, merchants,
channel, composition, personas, retention. Nothing else in this repo reads ICS accounts from the
ODD (the ICS program decks read the VIP sheets and workbooks).

Figures: v5's ICS section (`ti/odd_sections.ics`). Slides: v5's ICS chapter
(`ti/deck/ics_slides.add_chapter`), which draws every slide in one pass and returns the ones it
skipped as "<title> (<reason>)". Each skip is drawn as a stated slide under its own title, and the
chapter is put back in v5's order. A client with no ICS accounts on its lists gets one stated
slide. Primacy and merchants read the transaction chapter's lens rows and are stated until that
chapter is in the build. The chapter reads the same in both lens decks.
"""
import re
from pathlib import Path

from ti import cut, odd_sections

ORDER = ("ICS acquisition", "ICS activation", "ICS never activated", "ICS cohorts",
         "ICS sustained activity", "ICS usage", "ICS quality", "ICS closure hazard",
         "ICS first-year closure", "ICS by branch", "ICS primacy", "ICS merchants", "ICS channel",
         "ICS composition", "ICS activation personas", "ICS retention", "ICS summary")
ALIASES = {"ICS personas": "ICS activation personas"}


def compute(ctx):
    return odd_sections.ics(ctx)


def stats(pack, _lens):
    m = pack.get("metrics") or {}
    bases = m.get("ics_cmp_bases") or {}
    out = []
    if bases.get("stamped_total") or bases.get("ics"):
        out.append((f"{bases.get('stamped_total', bases.get('ics')):,}", "ICS accounts found in the ODD"))
    return out


def build(ctx):
    from ti.deck import ics_slides as S
    from ti.deck.helpers import Deck
    deck = Deck(ctx, "the ODD extract joined to the client's ICS direct-mail and referral lists",
                Path(ctx.art_dir or ".") / "charts" / "ics")
    m = ctx.pack.get("metrics") or {}
    skipped = S.add_chapter(ctx.prs, deck.helpers(), m, deck.charts_dir, txn=m)
    for line in skipped:
        hit = re.match(r"^(.*?) \((.*)\)$", line, re.S)
        title, reason = (hit.group(1), hit.group(2)) if hit else (line, "")
        if title == "ICS chapter":
            deck.declined("ICS accounts", f"{reason}; the ICS chapter needs ICS accounts found in "
                                          f"this extract")
            continue
        deck.declined(ALIASES.get(title, title), reason or "not available")
    # v5 leaves some slides out WITHOUT reporting a skip (ICS channel when there are no channel
    # rows); every slide the chapter carries is drawn or stated, never missing (CLAUDE.md)
    if "ICS accounts" not in deck.topics.values():
        made = set(deck.topics.values())
        for topic in ORDER:
            if topic not in made:
                deck.declined(topic, "the figures it needs are not in this client's files")
    rank = {t: i for i, t in enumerate(ORDER)}
    return sorted(deck.slides, key=lambda s: rank.get(deck.topics.get(id(s)), len(ORDER)))


CHAPTER = cut.Chapter("TI_ICS", "ICS Accounts", "Activation · Usage · Retention",
                      "The ICS accounts in the ODD against the rest of the book", stats, build, compute)
