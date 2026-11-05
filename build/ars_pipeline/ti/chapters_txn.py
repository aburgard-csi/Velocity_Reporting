"""
chapters_txn.py — the Transaction Intelligence and Competition chapters of the cut.

Compute: the Transaction Intelligence chapter runs v5's whole transaction sequence once, in v5's
order (`ti/txn_sections.py`); the Competition chapter reads what that left, so its compute adds
nothing. A client with no transaction window computes nothing here and says so.

Build: each chapter is v5's slide builders (`ti/deck/txn_slides.BUILDERS`, split by chapter in
v5's own order) drawn through the RPE helper bundle (`ti/deck/helpers.py`). A builder that
declines becomes a stated slide under its own title, which the frame then hides for that client
(Sheila's 1798 review, 2026-10-30). A client with no transaction figures at all gets ONE stated
slide per chapter, so both chapters are hidden whole.

Lenses: the slides that walk v5's lens list (`lenses` in the figures) show, in the ICS lens deck,
all accounts plus the ICS groups; in the ARS lens deck they are drawn exactly as v5 draws them.
The responder-against-control slides compare that one pair in both decks.

v5's two cross-source attrition slides (`txn_attrition`) belong to the Attrition chapter and are
exported here as ATTRITION_BUILDERS / ATTRITION_TITLES for it.
"""
import time
from pathlib import Path

from ti import cut, txn_sections as T
from ti.deck import labels
from ti.deck import txn_attrition as A
from ti.deck import txn_cards as C
from ti.deck import txn_compete as P
from ti.deck import txn_leakage as L
from ti.deck import txn_slides as S
from ti.deck import txn_value as V
from ti.deck.combine import apply as _combine
from ti.deck.helpers import Deck

TI_BUILDERS = [
    L.the_book_narrowed, C.how_the_money_moves, C.twelve_months,
    L.their_financial_life, S._where_the_money_goes, L.where_the_leakage_goes, L.who_they_pay,
    L.insurance_by_line, L.how_long_it_has_run, L.started_and_stopped, L.how_deep, L.leakage_by_group,
    L.leakage_by_group_and_category, L.what_leakers_hold, L.how_the_leakage_builds,
    L.which_services_travel_together, L.still_within_reach,
    S._how_members_spend, C.card_spend_by_category, C.ticket_and_intensity, C.when_the_card_is_used,
    C.recurring_on_the_card, C.card_behaviour_by_lens, C.engagement_breadth,
    C.merchants_rising_and_falling, C.new_and_faded_merchants, S._the_mcc_codes,
    C.how_broadly_the_card_is_used, C.card_spend_by_member_age, C.card_use_by_account_tenure,
    V.pin_or_signature, V.who_routes_pin, V.pin_heavy_accounts, V.where_pin_gets_pressed,
    V.channels_used_together, V.what_a_second_channel_is_worth,
    C.responder_profile, C.every_group_against_the_book, C.what_the_banker_opens, C.dictionary_gaps,
]
COMP_BUILDERS = [
    P.who_competes, P.the_local_field, P.which_to_work_first, P.filed_growth_slide,
    P.where_the_field_sits, P.where_we_leak_by_branch, P.lose_and_leak_together,
    P.gaining_and_losing, P.who_leads_each_product, P.banks_against_ecosystems,
    P.where_the_outflow_goes, P.where_the_dollars_go, P.who_owns_the_relationship,
    P.how_much_of_the_wallet_has_left, P.is_the_competitor_money_still_moving,
    P.how_many_competitors_each_account_uses, P.winback_targets, P.depth_against_growth,
    P.the_payment_ecosystems_ranked, P.buy_now_pay_later,
]
ATTRITION_BUILDERS = [A.spend_before_closure, A.stresses_across_files]

# v5's slide titles, for a builder that declines (read from v5's deck at a491b5c)
TITLES = {
    "the_book_narrowed": "The book, narrowed", "how_the_money_moves": "How the money moves",
    "twelve_months": "Twelve months of flow", "their_financial_life": "Their financial life",
    "_where_the_money_goes": "Where the money goes", "where_the_leakage_goes": "Where the leakage goes",
    "who_they_pay": "Who they pay", "insurance_by_line": "Insurance by line",
    "how_long_it_has_run": "How long the relationship has run",
    "started_and_stopped": "Started and stopped", "how_deep": "How deep the leakage runs",
    "leakage_by_group": "Leakage by group",
    "leakage_by_group_and_category": "Leakage by group and category",
    "what_leakers_hold": "What leakers hold with us", "how_the_leakage_builds": "How the leakage builds",
    "which_services_travel_together": "Which services travel together",
    "still_within_reach": "Still within reach", "_how_members_spend": "How members spend",
    "card_spend_by_category": "Card spend by category", "ticket_and_intensity": "Ticket and intensity",
    "when_the_card_is_used": "When the card gets used",
    "recurring_on_the_card": "Recurring payments on the card",
    "card_behaviour_by_lens": "Card behaviour by lens", "engagement_breadth": "Engagement breadth",
    "merchants_rising_and_falling": "Merchants rising and falling",
    "new_and_faded_merchants": "New and faded merchants",
    "_the_mcc_codes": "The MCC codes behind the categories",
    "how_broadly_the_card_is_used": "How broadly the card is used",
    "card_spend_by_member_age": "Card spend by member age",
    "card_use_by_account_tenure": "Card use by account tenure", "pin_or_signature": "PIN or signature",
    "who_routes_pin": "Who routes PIN", "pin_heavy_accounts": "PIN-heavy accounts",
    "where_pin_gets_pressed": "Where PIN gets pressed", "channels_used_together": "Channels used together",
    "what_a_second_channel_is_worth": "What a second channel is worth",
    "responder_profile": "The responder profile",
    "every_group_against_the_book": "Every group against the book",
    "what_the_banker_opens": "What the banker actually opens",
    "dictionary_gaps": "What the dictionary does not know yet",
    "who_competes": "Who competes for our members", "the_local_field": "The local field",
    "which_to_work_first": "Which competitors to work first", "filed_growth_slide": "Filed growth",
    "where_the_field_sits": "Where the field sits", "where_we_leak_by_branch": "Where we leak, by branch",
    "lose_and_leak_together": "Where we lose and where we leak",
    "gaining_and_losing": "Gaining and losing", "who_leads_each_product": "Who leads each product",
    "banks_against_ecosystems": "Banks against the ecosystems",
    "where_the_outflow_goes": "Where the outflow goes", "where_the_dollars_go": "Where the dollars go",
    "who_owns_the_relationship": "Who owns the relationship",
    "how_much_of_the_wallet_has_left": "How much of the wallet has left",
    "is_the_competitor_money_still_moving": "Is the competitor money still moving",
    "how_many_competitors_each_account_uses": "How many competitors each account uses",
    "winback_targets": "Winback targets", "depth_against_growth": "Depth against growth",
    "the_payment_ecosystems_ranked": "The payment ecosystems, ranked",
    "buy_now_pay_later": "Buy now, pay later",
    "spend_before_closure": "Competitor spend before closure",
    "stresses_across_files": "Stresses across both files",
}
ATTRITION_TITLES = {k: TITLES[k] for k in ("spend_before_closure", "stresses_across_files")}

# Two one-chart slides drawn as one, two charts side by side (Aaron, 2026-11-02; ti/deck/combine.py).
# (first builder, second builder, topic, headline, subtitle, name). Each part still draws as it
# always did when the other is declined for the client or the pair cannot share a slide.
TI_COMBINED = (
    ("how_long_it_has_run", "started_and_stopped", "How external relationships age and turn over",
     "How external relationships age and turn over",
     "Left: how recently each category's relationship moved money. Right: new against stopped in the last 90 days.",
     "relationships_age_and_turnover"),
    ("card_spend_by_member_age", "card_use_by_account_tenure", "Card spend by age and by tenure",
     "Who spends on the card, by age and by tenure",
     "Card dollars per account, by the holder's age band and by how long the account has been open.",
     "card_spend_by_age_and_tenure"),
    ("merchants_rising_and_falling", "new_and_faded_merchants", "Merchants moving in and out",
     "Merchants moving in and out of the card",
     "Left: the biggest risers and fallers by dollars. Right: merchants new to the card and merchants that faded.",
     "merchants_moving"),
)
TI_COMBINED += (
    ("_how_members_spend", "card_spend_by_category", "Where card dollars go",
     "Where card dollars go, by merchant and by category",
     "Left: the merchants with the most card spend. Right: card spend by category.",
     "card_dollars_by_merchant_and_category"),
    ("pin_or_signature", "pin_heavy_accounts", "PIN and signature",
     "How card dollars route, and who leans on PIN",
     "Left: the signature share of card dollars over time. Right: the merchants with the most PIN dollars.",
     "pin_and_signature"),
)
COMP_COMBINED = (
    ("where_the_dollars_go", "who_owns_the_relationship", "What competitors take and how much they own",
     "What competitors take, and how much of the account they own",
     "Left: dollars a year to each named competitor. Right: the share of an account's transactions each one takes.",
     "competitor_dollars_and_ownership"),
    ("the_payment_ecosystems_ranked", "buy_now_pay_later", "Payment apps and buy now, pay later",
     "Payment apps and buy now, pay later",
     "Left: members by payment ecosystem. Right: members carrying buy-now-pay-later balances, by provider.",
     "ecosystems_and_bnpl"),
)
# what the chapters draw: v5's builders (TI_BUILDERS, COMP_BUILDERS, which parity and the tests walk) with
# the pairs above drawn as one, and the titles a declined combined slide is stated under
TI_DRAWN, DRAWN_TITLES = _combine(TI_BUILDERS, TITLES, TI_COMBINED)
COMP_DRAWN, DRAWN_TITLES = _combine(COMP_BUILDERS, DRAWN_TITLES, COMP_COMBINED)

SOURCE = "the ODD extract and the monthly debit-card transaction files"


# ------------------------------------------------------------------ compute
def _lap(name, t):
    """One section's seconds and the process's memory after it, to the build log (James Gilmore, 2026-10-29:
    1798's 23.6M rows took most of an hour and ran out of memory, and nothing said where)."""
    try:
        import psutil
        mem = f", {psutil.Process().memory_info().rss / 2**30:.1f} GB in use"
    except Exception:                             # psutil is not a requirement; the time alone still says where
        mem = ""
    print(f"[time] transaction section {name}: {time.perf_counter() - t:,.1f} s{mem}", flush=True)


def compute_all(ctx):
    """v5's transaction run, in v5's order, once for both chapters and both lenses."""
    if ctx.txn is None:
        return {}
    out = {}
    for section in (T.portfolio, T.financial_services, T.competition, T.merchants,
                    T.merchant_profiles, T.mapping_audit, T.card_behavior, T.interchange,
                    T.relationship, T.overlay, T.leakage, T.stressors_txn):
        t = time.perf_counter()
        try:
            out.update(section(ctx) or {})
        except Exception as exc:                  # one section, never the chapter (v5's rule)
            ctx.warn(f"{section.__name__} failed: {type(exc).__name__}: {exc}")
        _lap(section.__name__, t)
    def hotspots(c):                              # reads comp_by_branch from the figures so far
        return T.hotspots(c, out)

    for section in (hotspots, T.family_tables):   # v5's order: hotspots, then the family tables
        try:
            out.update(section(ctx) or {})
        except Exception as exc:
            ctx.warn(f"{section.__name__} failed: {type(exc).__name__}: {exc}")
    out.update(T.filed(ctx, out))
    # v5's run hands the transaction figures to the ODD sections as config["_txn"]
    # (monthly_analysis/metrics.py: config = dict(config, _txn=txn)); the deposits section reads
    # them for "What arrives against what leaves". This chapter computes first in deck order.
    ctx.config = dict(ctx.config, _txn=out)
    return out


# ------------------------------------------------------------------ build
def lens_view(figures, ln):
    """The figures one lens deck draws from: in the ICS deck the lens list is all accounts plus
    the ICS groups; in the ARS deck it is v5's own list."""
    if ln.key != "ics" or not figures.get("lenses"):
        return figures
    keep = ("all",) + tuple(ln.groups)
    return dict(figures, lenses=[r for r in figures["lenses"] if r[0] in keep])


def _build(ctx, builders, chapter_title, art):
    m = ctx.pack.get("metrics") or {}
    d = Deck(ctx, SOURCE, Path(ctx.art_dir or ".") / art)
    if not m.get("fin_by_category"):
        # a file on hand that names nobody says so (1038, RPE matching fixes 2026-11-05)
        d.declined(chapter_title, m.get("fin_declined") or
                   "the transaction files for this period are not on hand, so "
                   "this chapter cannot be computed")
        return list(d.slides)
    t = lens_view(m, ctx.lens)
    return d.run(builders, DRAWN_TITLES, t, m.get("fin_base_label") or "transacting accounts")


def _money(v):
    return labels.money(v) if v is not None else "n/a"


def _ti_stats(pack, _ln):
    m = pack.get("metrics") or {}
    if not m.get("fin_by_category"):
        return []
    return [(f"{m.get('fin_leaking_pct', 0)}%", "of personal accounts pay an outside provider"),
            (_money(m.get("fin_leakage_dollars")), "sent to outside providers, 12 months"),
            (f"{m.get('txn_accounts', 0):,}", "accounts in the transaction file")]


def _comp_stats(pack, _ln):
    m = pack.get("metrics") or {}
    if not m.get("comp_institutions"):
        return []
    return [(f"{m.get('comp_with_competitor_pct', 0)}%", "of personal accounts pay a competitor"),
            (_money(m.get("comp_competitor_dollars")), "sent to competitors, 12 months"),
            (f"{len(m.get('comp_institutions') or []):,}", "competing institutions seen")]


TI_CHAPTER = cut.Chapter(
    "TI_TXN", "Transaction Intelligence", "Money Movement · Leakage · Card Use",
    "Where members' money goes outside the institution, and how they use the card",
    _ti_stats, lambda ctx: _build(ctx, TI_DRAWN, "Transaction Intelligence", "charts_txn"),
    compute_all)
COMP_CHAPTER = cut.Chapter(
    "TI_COMP", "Competition", "Competitors · Wallet Share · Winback",
    "Which institutions and payment ecosystems compete for members, and who to win back",
    _comp_stats, lambda ctx: _build(ctx, COMP_DRAWN, "Competition", "charts_comp"),
    lambda ctx: {})

# registered in deck order by ti/chapters/__init__.py (transaction_intelligence, competition)
CHAPTERS = (TI_CHAPTER, COMP_CHAPTER)
