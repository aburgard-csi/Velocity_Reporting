"""
The Campaign chapter: what the mailings did — reach and response by offer, the per-offer summary,
the ladder and NU conversion, what a response does to spend against a control, the counterfactual,
which offer earns its postage, over the ask, sustained activity, who responds, how accounts moved
between swipe tiers, the most recent mailer, the campaign hero and the two revenue frames (the
workbook's booked revenue against the difference-in-differences estimate), and an Offer detail
appendix, newest first.

Figures: v5's migration, mailer, mailer_detail, mailer_summary and cohort sections (with the ladder
cohort imports), in v5's order (`ti/odd_sections.py`). Slides: v5's campaign blocks, drawn inline in
v5's build and lifted into `ti/deck/campaign_inline.py`, in v5's build order; "Where the tiers moved"
is v5's `deck/migration_slides.tier_matrix`. A slide whose figures are missing is stated, not dropped.
The response groups are the ARS mailing's, so the chapter reads the same in both lens decks.

Sheila's 1798 slide review (2026-10-30) folded the chapter's repeats together: Program reach is a
funnel carrying the latest offer (group K); "What a response does to spend" carries both gain figures,
each with its window, on one responder-against-control chart (group L); "Where the tiers moved" is
the shaded tier matrix with responders against the unmailed (group N); and Offer detail opens with
one "Mailer summaries" table, a row per mailer, in place of a slide each (group P). The slides they
replace still draw, and are tossed in `ti/slides.json`.
"""
from pathlib import Path

from ti import cut, odd_sections
from ti.deck import combine

TITLES = {
    "program_reach": "Program reach",
    "response_reach": "Response and reach by offer",
    "per_offer": "Per-offer summary",
    "hero": "The campaign hero",
    "ladder_waves": "Ladder and NU conversion by offer",
    "segment_traj": "Segment trajectories",
    "penalty": "The penalty box",
    "counterfactual": "The counterfactual",
    "segments": "Which offer earns its postage",
    "dot_ask": "Transaction increase over the ask",
    "dot_segments": "Lift by response segment",
    "depth": "Depth of engagement — repeat responders",
    "activation": "Organic versus program activation",
    "cohort": "What a response does to spend",
    "sustained": "Sustained responder activity",
    "first_vs_repeat": "First-time versus repeat responders",
    "partial_convert": "Do partial responders convert?",
    "responder_profile": "Who responds — the profile",
    "tier_movement": "Tier movement by response status",
    "migration": "Swipe-tier migration",
    "tier_matrix": "Where the tiers moved",
    "latest_mailer": "The most recent mailer",
    "latest_trajectory": "The most recent mailer trajectory",
    "latest_offer": "The most recent offer",
    "revenue_frames": "Revenue frames",
    "offer_detail": "Offer detail",
}


# two one-chart slides as one (Aaron, 2026-11-02; ti/deck/combine.py)
COMBINED = (
    ("program_reach", "response_reach", "Reach and response",
     "How far the mailings reached, and how each offer responded",
     "Left: eligible accounts, ever mailed and responded. Right: each offer's response rate and the reach to date.",
     "reach_and_response"),
    ("depth", "first_vs_repeat", "Repeat responders",
     "Who responds again",
     "Left: how many responded once, twice and three times or more. Right: where first-time and repeat responders ended up.",
     "repeat_responders"),
)


def compute(ctx):
    out = {}
    for section in (odd_sections.migration, odd_sections.mailer, odd_sections.mailer_detail,
                    odd_sections.mailer_summary, odd_sections.cohort):
        out.update(section(ctx))
    return out


def stats(pack, _lens):
    m = pack.get("metrics") or {}
    out = []
    if m.get("latest_mailing") and m.get("latest_resprate") is not None:
        out.append((f"{m['latest_resprate']}%", f"responded to {m['latest_mailing']}"))
    if m.get("reach_total") is not None:
        out.append((f"{m['reach_total']:,}", "accounts the program has reached"))
    if m.get("ba_lift_net") is not None:
        from ti.deck.labels import money
        out.append((f"{money(m['ba_lift_net'])}/mo", "gain per responder, net of control"))
    return out[:3]


def build(ctx):
    from ti.deck import campaign_inline as S
    from ti.deck.helpers import Deck
    deck = Deck(ctx, "the ODD extract's own mail and response columns",
                Path(ctx.art_dir or ".") / "charts" / "campaign")
    builders, titles = combine.apply([getattr(S, name) for name in TITLES], TITLES, COMBINED)
    return deck.run(builders, titles, ctx.pack.get("metrics") or {})


CHAPTER = cut.Chapter("TI_CAMP", "Campaign", "Response · Gain · Ladder",
                      "What the mailings did, offer by offer", stats, build, compute)
