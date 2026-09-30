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
from . import txn_compete as P
from . import txn_leakage as L
from .labels import label as _label

TOP_CATEGORIES = 8
TOP_INSTITUTIONS = 10


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
                va="center", fontsize=11.5, color=charts.NAVY)
    ax.set_yticks(y)
    ax.set_yticklabels(tick_labels, fontsize=12.5, color=charts.NAVY)
    ax.set_xlim(0, span * 1.45)
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
        ax.text(r[4] + span * 0.02, y[i], f"{_money(r[4])}   {r[1]:,} accounts"
                f"{'' if r[7] else '   (non-addressable)'}",
                va="center", fontsize=11, color=charts.NAVY)
    ax.set_yticks(y)
    ax.set_yticklabels(tick_labels, fontsize=12.5, color=charts.NAVY)
    ax.set_xlim(0, span * 1.7)
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
        ax.text(r[2] + span * 0.02, y[i], f"{r[2]:,} accounts   {_money(r[5])}"
                + (f"   {prods}" if prods else ""), va="center", fontsize=11, color=charts.NAVY)
    ax.set_yticks(y)
    ax.set_yticklabels(tick_labels, fontsize=12.5, color=charts.NAVY)
    ax.set_xlim(0, span * 1.9)
    ax.get_xaxis().set_visible(False)
    charts._clean(ax, bottom=False)
    return charts._save(fig, out)


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
    h["divider"](prs, h["new"], "Transaction intelligence",
                 f"where {base} send money outside the institution")

    builders = [
        # the feed
        L.the_book_narrowed, C.how_the_money_moves, C.twelve_months,
        # leakage
        L.their_financial_life,
        lambda h_, t_, b: L.where_the_money_goes(h_, t_, b, category_bars),
        L.where_the_leakage_goes, L.who_they_pay, L.how_long_it_has_run,
        L.started_and_stopped, L.how_deep, L.leakage_by_group,
        L.leakage_by_group_and_category, L.what_leakers_hold,
        L.how_the_leakage_builds,
        # competition
        P.who_competes, P.which_to_work_first, P.where_the_field_sits,
        P.where_we_leak_by_branch, P.lose_and_leak_together,
        P.gaining_and_losing, P.who_leads_each_product,
        P.banks_against_ecosystems, P.where_the_outflow_goes,
        # the card
        lambda h_, t_, b: C.how_members_spend(h_, t_, b, merchant_bars),
        C.card_spend_by_category, C.ticket_and_intensity,
        C.when_the_card_is_used, C.recurring_on_the_card,
        C.card_behaviour_by_lens, C.engagement_breadth,
        # what it all says
        C.responder_profile, C.every_group_against_the_book,
        C.what_the_banker_opens, C.dictionary_gaps,
    ]
    skipped: list[str] = []
    for build in builders:
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
    tick_labels = [labels.clip(r[0], 24).title() for r in rows]
    dollars = [r[3] for r in rows]
    fig, ax = plt.subplots(figsize=(charts.FIG_W_RAIL, 5.2))
    y = np.arange(len(rows))
    ax.barh(y, dollars, color=charts.NAVY, height=0.6, edgecolor="white", linewidth=1.2)
    span = max(dollars) if dollars else 1
    for i, r in enumerate(rows):
        ax.text(r[3] + span * 0.02, y[i], f"{_money(r[3])}   {r[1]:,} accounts   ${r[4]:,.0f} avg",
                va="center", fontsize=11, color=charts.NAVY)
    ax.set_yticks(y)
    ax.set_yticklabels(tick_labels, fontsize=12.5, color=charts.NAVY)
    ax.set_xlim(0, span * 1.8)
    ax.get_xaxis().set_visible(False)
    charts._clean(ax, bottom=False)
    if available > len(rows):
        ax.set_xlabel(f"showing the top {len(rows)} of {available} merchants",
                      fontsize=10, color=charts.GREY, loc="left")
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


