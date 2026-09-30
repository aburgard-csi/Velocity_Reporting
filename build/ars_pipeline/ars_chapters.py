#!/usr/bin/env python3
"""
ars_chapters.py — James's v5 ODD deck chapters (engine/deck/ars_deck.py: campaign, debit card,
Reg E, scorecard and takeaways, offer detail, new-account profile, deposits, attrition
warnings) drawn onto Aaron's template by Aaron's rules, opt-in (RPE_ANALYSIS_SLIDES=1).

The v5 body is verbatim; `chapter_base.Chapter` supplies its closures and `ars_layout` its
primitives. Each v5 chapter's main-path slides go before the Aaron section that follows the
same subject (campaign before "Debit Card Review", debit card before the transaction chapter,
Reg E and the synthesis before "ARS Key Takeaways"); everything else lands at the end of the
appendix under one divider per chapter. James's decided order (2026-09-30): campaign →
responder / debit → transaction → deposits.

    add_ars_chapters(prs, m, txn, ctx) -> (slides, inventory)
        ctx: as_of_long, assets, odd_src, client_name, out (the analysis evidence folder), cut
"""
import os
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(_HERE, os.pardir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from combined_insight_slides import _find                                               # noqa: E402
from chapter_base import Chapter, cut_from, summary_lines as _summary                   # noqa: E402
from engine.deck import ars_deck                                                        # noqa: E402

TI_DIVIDER = "Transaction Intelligence"

# v5 chapter (the divider title the body passes) -> the Aaron title its main slides go before.
ANCHORS = {
    "Eligibility and the base": ("Mailing Insights",),
    "Campaign performance": ("Debit Card Review",),
    "Debit card performance": (TI_DIVIDER, "Reg E Review"),
    "Reg E review": ("ARS Key Takeaways",),
    "Summary": ("ARS Key Takeaways",),
    "Offer detail": ("Debit Card Review",),
    "Appendix": ("ARS Key Takeaways",),
    "New account profile": ("ARS Key Takeaways",),
}
APPENDIX_TITLES = {
    "Eligibility and the base": ("Eligibility Detail", "Base • Swipe Tiers • Ticket"),
    "Campaign performance": ("Campaign Detail", "Response • Gain • Economics"),
    "Debit card performance": ("Debit Card Detail", "Take Rate • Branches • Attrition • Deposits"),
    "Reg E review": ("Reg E Detail", "Opt-In • Vintage • Branches"),
    "Summary": ("Summary Detail", "Scorecard • Takeaways • Lists"),
    "Offer detail": ("Offer Detail", "Every Mailing, Newest First"),
    "Appendix": ("Supporting Detail", "Lists • Reference"),
    "New account profile": ("Account Profile Detail", "New Accounts • Growth • Retention"),
}

# The v5 deck manifest's main path (0_Config/deck_manifest.json, 2026-09-30), less the
# transaction rows ti_chapter carries.
MAIN_CUT = ("The campaign hero", "The 2:1 guarantee", "Program P&L by offer", "What each offer has earned",
            "Where the month's revenue came from", "What an account earns as it climbs", "Per-offer summary",
            "Response and reach by offer", "The most recent mailer", "The most recent mailer trajectory",
            "The most recent offer", "What a response does to spend", "Operational KPIs",
            "Behavior by segment around the offer", "Responders versus control around the offer",
            "Key takeaways", "Scorecard")


class _OddChapters(Chapter):
    MAIN_CUT = MAIN_CUT
    PREFIX = "ars_"
    DEFAULT_CHAPTER = "Eligibility and the base"

    def __init__(self, prs, m, ctx):
        super().__init__(prs, ctx)
        self.m = m
        self.source = (f"Source: {ctx.get('odd_src') or 'the ODD extract'}; data through "
                       f"{m.get('data_month', 'n/a')}; figures from metrics.json "
                       f"(the v5 engine on the same file the deck reads).")

    def _selection(self):
        m = self.m
        tot, elig, month = m.get("n_total"), m.get("n_eligible"), m.get("data_month", "")
        if isinstance(elig, int) and isinstance(tot, int):
            return [f"Selection: {elig:,} eligible accounts of {tot:,} on file; ODD through {month}.",
                    f"Selection: {elig:,} eligible accounts; ODD through {month}."]
        return ["Selection: the ODD extract."]

    def anchor_for(self, chapter):
        for title in ANCHORS.get(chapter, ("ARS Key Takeaways",)):
            if _find(self.prs, title) is not None:
                return title
        return "Reg E Review"

    def appendix_title_for(self, chapter):
        return APPENDIX_TITLES.get(chapter, (f"{chapter} Detail", "Appendix"))


def add_ars_chapters(prs, m, txn, ctx):
    """Draw every v5 ODD slide the metrics support and place it. Returns ([slides], inventory)."""
    ch = _OddChapters(prs, m, ctx)
    out = Path(ctx.get("out") or ch.assets)
    skipped = ars_deck.add_chapters(prs, ch.helpers, m, txn, ch.assets, out)
    ch.flush()
    for why in skipped:
        ch.skip(why)
    ch.place(cut_from(ctx))
    return [s for s, _, _ in ch.slides], ch.inventory


def summary_lines(inventory):
    return _summary("ODD chapters", inventory)
