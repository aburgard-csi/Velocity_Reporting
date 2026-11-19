# Ported from ARS v5 02-Scripts/ars/deck/txn_slides.py at a491b5c (James Gilmore); logic unchanged.
"""Transaction-intelligence chapter for the ODD deck.

Appended by deck.build when a txn_metrics.json exists for the same period.
Reads the fin_* / finb_* / txn_* keys written by transaction_intelligence and
uses the deck's own helpers (passed in as `h`) so styling is identical.

Eight slides: where the money goes; who they pay; responders vs control;
what leakers hold with us; P2P and fintech with the business footnote;
who competes for our members (named institutions, comp_* keys); how members
spend the card (mch_* / beh_*); engagement breadth (rel_*).
Every title is computed from the numbers, as headlines.py does elsewhere.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from . import charts, labels
from . import txn_cards as C
from . import txn_attrition as A
from . import txn_compete as P
from . import txn_leakage as L
from . import txn_value as V
from .labels import label as _label
from .charts_txn import TXT

TOP_CATEGORIES = 8
TOP_INSTITUTIONS = 10


def _accounts(n) -> str:
    """"1 account", "2 accounts" (RPE: v5 printed "1 accounts")."""
    return f"{n:,} account" + ("" if n == 1 else "s")


def _money(v) -> str:
    from .labels import money
    return money(v)


def lens_bars(rows: list, out: Path) -> Path:
    """External-product share by group: item comparison -> horizontal bars,
    responders in orange (Zelazny). Replaces the by-lens table."""
    rows = rows[::-1]
    tick_labels = [labels.clip(r[1], 24) for r in rows]
    pcts = [r[4] for r in rows]
    fig, ax = plt.subplots(figsize=(charts.FIG_W_RAIL, 4.9))
    y = np.arange(len(rows))
    colors = [charts.ORANGE if r[0] in ("responders", "mailed_nonresp")
              else charts.NAVY for r in rows]
    ax.barh(y, pcts, color=colors, height=0.6, edgecolor="white", linewidth=1.2)
    span = max(pcts) if pcts else 1
    for i, r in enumerate(rows):
        ax.text(r[4] + span * 0.015, y[i], f"{r[4]:.0f}%   {r[3]:,} of {r[2]:,}",
                va="center", fontsize=TXT, color=charts.NAVY)
    ax.set_yticks(y)
    ax.set_yticklabels(tick_labels, fontsize=TXT, color=charts.NAVY)
    ax.set_xlim(0, span * 1.65)
    ax.get_xaxis().set_visible(False)
    charts._clean(ax, bottom=False)
    return charts._save(fig, out)


def category_bars(rows: list, out: Path, top: int = TOP_CATEGORIES) -> Path:
    """Leakage dollars by category, horizontal, accounts annotated."""
    rows = [r for r in rows if r[6] == "leakage"][:top][::-1]
    tick_labels = [labels.clip(r[0], 24) for r in rows]
    dollars = [r[4] for r in rows]
    fig, ax = plt.subplots(figsize=(charts.FIG_W_RAIL, 5.2))
    y = np.arange(len(rows))
    muted = getattr(charts, "GREY", "#5A6670")
    colors = [charts.NAVY if r[7] else muted for r in rows]
    ax.barh(y, dollars, color=colors, height=0.6, edgecolor="white", linewidth=1.2)
    span = max(dollars) if dollars else 1
    for i, r in enumerate(rows):
        ax.text(r[4] + span * 0.02, y[i], f"{_money(r[4])}   {_accounts(r[1])}"
                f"{'' if r[7] else '   (non-addressable)'}",
                va="center", fontsize=TXT, color=charts.NAVY)
    ax.set_yticks(y)
    ax.set_yticklabels(tick_labels, fontsize=TXT, color=charts.NAVY)
    ax.set_xlim(0, span * 2.0)
    ax.get_xaxis().set_visible(False)
    charts._clean(ax, bottom=False)
    return charts._save(fig, out)


def institution_bars(rows: list, out: Path, top: int = TOP_INSTITUTIONS) -> Path:
    """Accounts per named competitor, horizontal; local banks/CUs in orange."""
    rows = rows[:top][::-1]
    tick_labels = [labels.clip(r[0], 26) for r in rows]
    accts = [r[2] for r in rows]
    fig, ax = plt.subplots(figsize=(charts.FIG_W_RAIL, 5.2))
    y = np.arange(len(rows))
    colors = [charts.ORANGE if r[1] == "Local Bank / CU" else charts.NAVY for r in rows]
    ax.barh(y, accts, color=colors, height=0.6, edgecolor="white", linewidth=1.2)
    span = max(accts) if accts else 1
    for i, r in enumerate(rows):
        prods = ", ".join(p for p in r[7][:2] if p != "Transfer / other")  # list-cap
        ax.text(r[2] + span * 0.02, y[i], f"{_accounts(r[2])}   {_money(r[5])}"
                + (f"   {prods}" if prods else ""), va="center", fontsize=TXT, color=charts.NAVY)
    ax.set_yticks(y)
    ax.set_yticklabels(tick_labels, fontsize=TXT, color=charts.NAVY)
    ax.set_xlim(0, span * 2.2)
    ax.get_xaxis().set_visible(False)
    charts._clean(ax, bottom=False)
    return charts._save(fig, out)


def _where_the_money_goes(h, t, base):
    return L.where_the_money_goes(h, t, base, category_bars)


def _how_members_spend(h, t, base):
    return C.how_members_spend(h, t, base, merchant_bars)


def _the_mcc_codes(h, t, base):
    return C.the_mcc_codes(h, t, base, merchant_bars)


# The chapter, in order. Module-level so a test can hold the order: the
# local field follows "who competes" because it answers the question that
# slide raises for every client whose locals never reach the top nine.
BUILDERS = [
    # the feed
    L.the_book_narrowed, C.how_the_money_moves, C.twelve_months,
    # leakage
    L.their_financial_life, _where_the_money_goes,
    L.where_the_leakage_goes, L.who_they_pay, L.insurance_by_line,
    L.how_long_it_has_run,
    L.started_and_stopped, L.how_deep, L.leakage_by_group,
    L.leakage_by_group_and_category, L.what_leakers_hold,
    L.how_the_leakage_builds, L.which_services_travel_together,
    L.still_within_reach,
    # competition
    P.who_competes, P.the_local_field, P.which_to_work_first,
    P.filed_growth_slide, P.where_the_field_sits, P.where_we_leak_by_branch,
    P.lose_and_leak_together, A.spend_before_closure, A.stresses_across_files,
    P.gaining_and_losing, P.who_leads_each_product,
    P.banks_against_ecosystems, P.where_the_outflow_goes,
    # the competition family (legacy 14-35, 66-67; #258)
    P.where_the_dollars_go, P.who_owns_the_relationship,
    P.how_much_of_the_wallet_has_left, P.is_the_competitor_money_still_moving,
    P.how_many_competitors_each_account_uses, P.winback_targets,
    P.depth_against_growth, P.the_payment_ecosystems_ranked, P.buy_now_pay_later,
    # the card
    _how_members_spend, C.card_spend_by_category, C.ticket_and_intensity,
    C.when_the_card_is_used, C.recurring_on_the_card,
    C.card_behaviour_by_lens, C.engagement_breadth,
    # merchants, MCC codes and the card book by holder (#258 group 3)
    C.merchants_rising_and_falling, C.new_and_faded_merchants, _the_mcc_codes,
    C.how_broadly_the_card_is_used, C.card_spend_by_member_age,
    C.card_use_by_account_tenure,
    # the routing mix and the relationship shape (#258 group 4)
    V.pin_or_signature, V.who_routes_pin, V.pin_heavy_accounts,
    V.where_pin_gets_pressed, V.channels_used_together,
    V.what_a_second_channel_is_worth,
    # what it all says
    C.responder_profile, C.every_group_against_the_book,
    C.what_the_banker_opens, C.dictionary_gaps,
]


def add_chapter(prs, h: dict, t: dict, charts_dir: Path) -> list[str]:
    """The transaction chapter, built to the approved catalog
    (lab/DESIGN/report-mockups/slides-txn-suite.html).

    Each builder draws one slide and returns None, or a string saying why it
    declined. A slide that cannot be drawn honestly says so rather than
    rendering an empty frame.
    """
    if not t.get("fin_by_category"):
        return ["transaction chapter (no fin_by_category)"]
    base = t.get("fin_base_label", "accounts")
    rails = t.get("txn_rails_label")
    h["divider"](prs, h["new"], "Transaction intelligence",
                 f"where {base} send money outside the institution"
                 + (f" · {rails} feed" if rails else "")
                 + ("" if t.get("txn_transfer_rails", True) else
                    ": ACH, check and bill pay are not in the file, so "
                    "transfers to other institutions are not visible here"))

    skipped: list[str] = []
    for build in BUILDERS:
        try:
            why = build(h, t, base)
        except Exception as exc:                       # one slide, not the deck
            name = getattr(build, "__name__", "txn slide")
            skipped.append(f"{name} ({type(exc).__name__}: {exc})")
            continue
        if why:
            skipped.append(why)
    return skipped


def merchant_bars(rows: list, out: Path, top: int = 10) -> Path:
    fig = _merchant_fig(rows, top)
    return charts._save(fig, out)


def _merchant_fig(rows: list, top: int = 10):
    """Card dollars per merchant, horizontal, avg ticket annotated.

    The slide's headline quotes a top-15 statistic, so a silent cap at ten
    bars reads as the whole story (#71). When the cap drops rows, the chart
    says what it is showing.
    """
    available = len(rows)
    rows = rows[:top][::-1]
    tick_labels = [labels.clip(labels.display_name(r[0]), 24) for r in rows]
    dollars = [r[3] for r in rows]
    fig, ax = plt.subplots(figsize=(charts.FIG_W_RAIL, 5.2))
    y = np.arange(len(rows))
    ax.barh(y, dollars, color=charts.NAVY, height=0.6, edgecolor="white", linewidth=1.2)
    span = max(dollars) if dollars else 1
    for i, r in enumerate(rows):
        # two dollar signs in one string put matplotlib into mathtext: the
        # annotation came out italic with its spaces dropped (#258 group 3)
        note = f"{_money(r[3])}   {_accounts(r[1])}   ${r[4]:,.0f} avg".replace("$", r"\$")
        ax.text(r[3] + span * 0.02, y[i], note, va="center", fontsize=TXT, color=charts.NAVY)
    ax.set_yticks(y)
    ax.set_yticklabels(tick_labels, fontsize=TXT, color=charts.NAVY)
    ax.set_xlim(0, span * 2.1)
    ax.get_xaxis().set_visible(False)
    charts._clean(ax, bottom=False)
    if available > len(rows):
        ax.set_xlabel(f"showing the top {len(rows)} of {available} merchants",
                      fontsize=TXT, color=charts.GREY, loc="left")
        ax.get_xaxis().set_visible(True)
        ax.set_xticks([])
    return fig


def _band_table(label: str, rows: list) -> list[list[str]]:
    """Band rows are [label, count, share%]. The slide printed the COUNT
    under a 'Share' header and dropped the share entirely (#73); it now
    carries both, and every header names the column beneath it."""
    body = [[label, "Accounts", "Share"]]
    for row in rows:
        share = f"{row[2]:.1f}%" if len(row) > 2 and row[2] is not None else "-"
        body.append([str(row[0]), f"{int(row[1]):,}", share])
    return body


