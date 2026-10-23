"""
cut.py — what the Transaction Intelligence cut IS: its lenses, its chapters and its file name.

Lenses
    One deck per lens, from the same chapter code: every chapter takes the lens and splits
    its figures by the lens's groups. The ARS lens is for every ARS client; the ICS lens
    only for a client on ICS whose ICS accounts can be found in the ODD (the gate lands
    with the lens masks; a lens that cannot be built is stated, never rendered empty).

Chapters
    `CHAPTERS` is the deck order. It is empty until the first migrated chapter lands; each
    one appends itself here in its own pull request (transaction intelligence, competition,
    attrition, deposits — in that order). A chapter is:
        code     short key, also its agenda row ("TI_TXN")
        title    its divider title and agenda heading
        benefits the divider's orange line, three terms like every other divider
        agenda   the agenda row's detail line
        stats    f(pack, lens) -> up to three (value, label) pairs for the divider
        build    f(ctx) -> the chapter's content slides, in order (see build_ti_gen.Ctx)

File name
    <id>-<yyyy.mm>-TI-<LENS>-<Client> Transaction Intelligence.pptx
    "TI" sits where the program tags sit and is deliberately NOT one of them
    (`promote_month.PROGRAM_TAGS`): `parse_deck_name` returns None for it and
    `program_tags` returns (), so a TI deck can never be read as an ARS deck, supersede
    one, or be archived in its place. tests/test_ti_shell.py pins this.
"""
import re
from collections import namedtuple

Lens = namedtuple("Lens", "key tag label groups")

LENSES = {
    "ars": Lens("ars", "ARS", "ARS lens",
                ("Responders", "Mailed non-responders", "Not mailed")),
    "ics": Lens("ics", "ICS", "ICS lens",
                ("ICS direct mail", "ICS referral", "Not ICS")),
}

Chapter = namedtuple("Chapter", "code title benefits agenda stats build")

CHAPTERS = ()

CUT_NAME = "Transaction Intelligence"
FILE_TAG = "TI"


def lens(key):
    """The Lens for 'ars' / 'ics'. Anything else stops the build with a plain sentence."""
    k = str(key or "").strip().lower()
    if k not in LENSES:
        raise SystemExit(f"unknown lens {key!r}: the Transaction Intelligence cut has "
                         f"{', '.join(sorted(LENSES))}")
    return LENSES[k]


def deck_name(client_id, period, client_name, lens_key):
    """The cut's file name. `period` is the data month, yyyy.mm, as on every deck."""
    if not re.fullmatch(r"\d{4}\.\d{2}", str(period)):
        raise ValueError(f"period must be yyyy.mm, got {period!r}")
    client = re.sub(r'[<>:"/\\|?*]', "", str(client_name)).strip()
    return f"{client_id}-{period}-{FILE_TAG}-{lens(lens_key).tag}-{client} {CUT_NAME}.pptx"
