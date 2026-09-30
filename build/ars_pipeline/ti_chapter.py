#!/usr/bin/env python3
"""
ti_chapter.py — James's v5 transaction chapter (engine/deck/txn_*.py: 34 slides) drawn onto
Aaron's template by Aaron's rules, opt-in (RPE_ANALYSIS_SLIDES=1).

The v5 chapter modules draw through a dict of seven helpers (new, slide, chart, chart_left,
rail, divider, RIGHT_EDGE); `chapter_base.Chapter` supplies them on Aaron's grid. The data
and the chart forms are James's; the slide is Aaron's.

Placement (James, 2026-09-30, "I need to see everything created, then whittle"): the v5 main
path (MAIN_CUT) goes into the deck before "Reg E Review" under a "Transaction Intelligence"
divider; every other slide is still built and lands at the end of the appendix under its own
divider. RPE_ANALYSIS_CUT=main keeps the main path only. Nothing is dropped silently: a
builder that declines is listed with its reason in the inventory the build writes.

    add_ti_chapter(prs, txn, ctx) -> (slides, inventory)
        ctx: as_of_long, assets, txn_src, client_name, cut (optional)
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(_HERE, os.pardir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ti_layout as L                                                                      # noqa: E402
from chapter_base import (Chapter, member_term, wording, title_case, parse_skip, cut_from,  # noqa: E402,F401
                          summary_lines as _summary)
from engine.deck import txn_slides                                                         # noqa: E402

ANCHOR_BEFORE = "Reg E Review"
CHAPTER = "Transaction intelligence"
MAIN_TITLE, MAIN_SUB = "Transaction Intelligence", "Where the Money Goes • Competition • Card Spend"
APPX_TITLE, APPX_SUB = "Transaction Intelligence Detail", "Leakage • Competition • Card Behaviour"
BUILDERS = 34                             # txn_slides.add_chapter's builder list

# The v5 deck manifest's main path, transaction rows (0_Config/deck_manifest.json, 2026-09-30),
# keyed by the v5 slide label the builders pass as `fallback`.
MAIN_CUT = ("How the money moves", "Where the money goes", "Their financial life", "Who they pay",
            "What leakers hold with us", "Who competes for our members",
            "Which competitors to work first", "Where the outflow goes", "How members spend",
            "The responder profile", "What the banker actually opens")


class _TxnChapter(Chapter):
    MAIN_CUT = MAIN_CUT
    PREFIX = "ti_"
    DEFAULT_CHAPTER = CHAPTER

    def __init__(self, prs, txn, ctx):
        super().__init__(prs, ctx)
        self.m = self.txn = txn
        files = ", ".join(txn.get("txn_files_loaded") or [])[:300] or "no files"
        self.source = (f"Source: {ctx.get('txn_src') or 'the client transaction files'} — {files} "
                       f"({txn.get('txn_rows', 0):,} rows, {txn.get('txn_months_covered', 0)} month(s)); "
                       f"ODD join {txn.get('txn_odd_match_pct', 'n/a')}% on {txn.get('txn_odd_join_key', 'n/a')}; "
                       f"figures from txn_metrics.json.")

    def divider(self, *args, **kw):
        self.flush()
        self.chapter_now[0] = CHAPTER
        return None

    def _selection(self):
        t = self.txn
        personal, every = t.get("fin_accounts_total"), t.get("txn_accounts")
        base, label = ((personal, "transacting personal accounts") if isinstance(personal, int) and personal
                       else (every, "transacting accounts"))
        if not isinstance(base, int):
            return ["Selection: transacting accounts."]
        return [f"Selection: {label} ({base:,}); {t.get('txn_window_months', 12)}-month window "
                f"ending {t.get('txn_anchor', '')}.", f"Selection: {label} ({base:,})."]

    def anchor_for(self, chapter):
        return ANCHOR_BEFORE

    def main_divider_for(self, chapter):
        return (MAIN_TITLE, MAIN_SUB)

    def appendix_title_for(self, chapter):
        return (APPX_TITLE, APPX_SUB)


def add_ti_chapter(prs, txn, ctx):
    """Build every v5 transaction slide the data supports, place the main path before
    "Reg E Review" and the rest in the appendix. Returns ([slides], inventory)."""
    ch = _TxnChapter(prs, txn, ctx)
    if not txn.get("fin_by_category"):
        s, _ = ch.slide(("The transaction files in this window carry no financial-services rows, "
                         "so the chapter is not drawn for this period",
                         "check the files under Inputs/Txn Files and the financial services dictionary"),
                        "Transaction intelligence")
        ch.flush()
        ch.finalize()
        L.move_before(prs, s, ch.anchor)
        ch.inventory[0]["status"] = "no data"
        ch.inventory[0]["cut"] = "main"
        return [s], ch.inventory
    skipped = txn_slides.add_chapter(prs, ch.helpers, txn, ch.assets)
    ch.flush()
    for why in skipped:
        ch.skip(why)
    ch.place(cut_from(ctx))
    return [s for s, _, _ in ch.slides], ch.inventory


def summary_lines(inventory):
    return _summary("transaction chapter", inventory)
