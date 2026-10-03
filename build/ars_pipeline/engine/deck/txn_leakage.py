"""Leakage slides for the transaction chapter.

Built to the approved catalog (lab/DESIGN/report-mockups/slides-txn-suite
.html). Every function takes the helpers dict from deck.build and the txn
metrics, draws one slide, and returns nothing; the caller collects skips.
"""
from __future__ import annotations

from . import charts, charts_story as CS, charts_txn as CT, labels
from .txn_common import RAIL_EDGE, money, pct_rows, rail_or_full

RECENCY_BANDS = [("active", charts.GREEN), ("cooling", "#F0A23C"),
                 ("dormant", charts.STEEL), ("lapsed", charts.LIGHT)]


def the_book_narrowed(h, t, base):
    """concept 15 -- each band is a real filter, not a funnel metaphor."""
    total, leak = t.get("fin_accounts_total"), t.get("fin_leaking_accounts")
    if not (total and leak):
        return "The book, narrowed (no fin_accounts_total)"
    stages = [["Transacting accounts", t.get("txn_accounts") or total, 0, 0],
              [f"The base", total, 0, 0],
              ["Pay an external product", leak, 0, 0],
              ["In an addressable category",
               t.get("fin_addressable_accounts") or 0, 0, 0],
              ["Active or cooling",
               t.get("fin_addressable_active_accounts") or 0, 0, 0]]
    stages = [s for s in stages if s[1]]
    if len(stages) < 4:
        return "The book, narrowed (too few stages)"
    for i in range(1, len(stages)):
        prev = stages[i - 1][1] or 1
        stages[i][3] = round((1 - stages[i][1] / prev) * 100, 1)
    end, start = stages[-1][1], stages[0][1]
    s, top = h["slide"]((
        f"{end:,} accounts are addressable and still warm — "
        f"{end / start * 100:.0f}% of everyone who transacted",
        "each band is a real filter; every step names the rule that cut it"),
        "The book, narrowed")
    path = h["chart"]("txn_funnel", charts.funnel, stages)
    if path:
        h["chart_left"](s, path, top, RAIL_EDGE)


def their_financial_life(h, t, base):
    """concept 02 -- only an addressable block is ever lit."""
    cat = t.get("fin_by_category") or []
    if not cat:
        return "Their financial life (no fin_by_category)"
    addr = [r for r in cat if r[7]]
    big = max(addr, key=lambda r: r[4]) if addr else None
    head = (f"{money(t.get('fin_leakage_dollars'))} a year of financial "
            f"products, and {big[0].lower()} is the biggest one we could "
            f"actually compete for") if big else \
        f"{money(t.get('fin_leakage_dollars'))} of financial products a year"
    s, top = h["slide"]((head,
        "every external category as area; grey is non-addressable — "
        "insurance and tax are not products the institution sells"),
        "Their financial life")
    rows = [[r[0], r[4], f"{r[1]:,} accts · {money(r[5])}/acct",
             bool(r[7])] for r in cat]
    note = (f"{money(t.get('fin_addressable_dollars'))} addressable of "
            f"{money(t.get('fin_leakage_dollars'))}")
    path = h["chart"]("fin_treemap", CS.treemap, rows, note=note)
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


def where_the_money_goes(h, t, base, category_bars):
    cat = t.get("fin_by_category")
    head = (f"{t.get('fin_leaking_pct', 0):.0f}% of {base} send "
            f"{money(t.get('fin_leakage_dollars'))} a year to other "
            f"institutions' financial products")
    sub = (f"{t.get('fin_leakage_pct_of_transfer_dollars', 0):.0f}% of all "
           f"ACH and check dollars; "
           f"{t.get('fin_addressable_accounts', 0):,} accounts in addressable "
           f"categories, {money(t.get('fin_addressable_dollars'))}")
    s, top = h["slide"]((head, sub), "Where the money goes")
    right = h["rail"](s, [
        ("Leaking", f"{t.get('fin_leaking_accounts', 0):,}",
         f"of {t.get('fin_accounts_total', 0):,} {base}"),
        ("Leakage", money(t.get("fin_leakage_dollars")),
         "per year, to external financial products"),
        ("Addressable", money(t.get("fin_addressable_dollars")),
         f"{t.get('fin_addressable_active_accounts', 0):,} active or cooling"),
        ("Two or more", f"{t.get('fin_multi_category_pct', 0):.0f}%",
         "of leakers, in 2+ categories"),
    ], top=top)
    path = h["chart"]("fin_categories", category_bars, cat)
    if path:
        h["chart_left"](s, path, top, right)


def where_the_leakage_goes(h, t, base):
    """flow_ribbons on the leakage flow -- built and tested since #74 phase 2
    and never called by a slide until now."""
    cat = t.get("fin_by_category") or []
    if len(cat) < 3:
        return "Where the leakage goes (too few categories)"
    s, top = h["slide"]((
        f"{money(t.get('fin_leakage_dollars'))} leaves every year, and the "
        f"top categories carry most of it",
        "the accounts on the left, the products their money reaches on the "
        "right; ribbon width is dollars"), "Where the leakage goes")
    source = {"count": f"{t.get('fin_leaking_accounts', 0):,}",
              "count_label": base,
              "held": f"{money(t.get('fin_leakage_dollars'))} out",
              "drain": f"{money(t.get('fin_addressable_dollars'))} addressable"}
    dests = [[r[0], f"{r[1]:,} accounts · {money(r[5])} per account", r[4]]
             for r in cat[:5]]
    path = h["chart"]("fin_flow", charts.flow_ribbons, source, dests)
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


def who_they_pay(h, t, base):
    """The Pareto that replaces the three-column provider table."""
    provs = t.get("fin_top_providers") or {}
    flat = []
    for cat, rows in provs.items():
        for r in rows:
            flat.append([r[0], cat, r[2]])
    flat.sort(key=lambda r: -r[2])
    flat = flat[:10]
    if not flat:
        return "Who they pay (no fin_top_providers)"
    top = flat[0]
    s, y = h["slide"]((
        f"{str(top[0]).title()} alone takes {money(top[2])} of the external "
        f"spend",
        "named providers by dollars, with the cumulative line and the 80% "
        "rule"), "Who they pay")
    rows = [[labels.clip(str(r[0]).title(), 16), labels.clip(r[1], 18), r[2]]
            for r in flat]
    note = labels.coverage_note(len(flat), sum(len(v) for v in provs.values()),
                                "providers")
    path = h["chart"]("fin_pareto", CT.pareto, rows, note=note or "")
    if path:
        h["chart_left"](s, path, y, h["RIGHT_EDGE"])


def how_long_it_has_run(h, t, base):
    rec = t.get("fin_recency") or []
    if not rec:
        return "How long the relationship has run (no fin_recency)"
    s, top = h["slide"]((
        "Most external relationships are not new — they are habits the "
        "institution never saw start",
        "each category as one bar: active within 30 days, cooling to 90, "
        "dormant to a year, lapsed beyond it"),
        "How long the relationship has run")
    path = h["chart"]("fin_recency", CT.band_stack, rec[:9], RECENCY_BANDS)
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


def started_and_stopped(h, t, base):
    nrs = t.get("fin_new_recurring_stopped") or []
    if not nrs:
        return "Started and stopped (no fin_new_recurring_stopped)"
    rows = sorted(nrs, key=lambda r: -(r[1] - r[3]))[:8]
    s, top = h["slide"]((
        "Where external relationships form faster than they are dropped",
        "new relationships in the last 90 days against those that stopped, "
        "per category, off a centre line"), "Started and stopped")
    path = h["chart"]("fin_tornado", CT.tornado,
                      [[r[0], r[3], r[1]] for r in rows])
    if path:
        h["chart_left"](s, path, top, RAIL_EDGE)


def how_deep(h, t, base):
    mc = t.get("fin_multi_category") or []
    if not mc:
        return "How deep the leakage runs (no fin_multi_category)"
    s, top = h["slide"]((
        f"{t.get('fin_multi_category_pct', 0):.0f}% of leakers pay for two or "
        f"more external categories",
        "the depth of the external relationship, not its existence"),
        "How deep the leakage runs")
    rows = [[f"{r[0]} categories", r[1]] for r in mc[-5:]]
    path = h["chart"]("fin_depth", charts.composition, rows)
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


def leakage_by_group(h, t, base):
    rows = t.get("fin_by_lens") or []
    by = {r[0]: r for r in rows}
    r_, c_ = by.get("responders"), by.get("mailed_nonresp")
    if not (r_ and c_):
        return "Leakage by group (no responder/control pair)"
    s, top = h["slide"]((
        "Your most engaged members are also the most multi-banked — the "
        "recapture list writes itself",
        "responders against mailed non-responders on every measure the "
        "section computes"), "Leakage by group")
    dumb = [["Accounts in addressable categories", r_[4], c_[4],
             f"{r_[3]:,} vs {c_[3]:,}"],
            ["Dollars per addressable account", r_[5], c_[5],
             f"${r_[5]:,} vs ${c_[5]:,}"],
            ["P2P or fintech use", r_[7], c_[7],
             f"{r_[6]:,} vs {c_[6]:,} accounts"]]
    path = h["chart"]("fin_by_lens", charts.dumbbell, dumb, "responders",
                      "mailed non-responders")
    if path:
        h["chart_left"](s, path, top, RAIL_EDGE)


def leakage_by_group_and_category(h, t, base):
    flc = t.get("fin_by_lens_category") or []
    lenses = t.get("lenses") or []
    if not (flc and lenses):
        return "Leakage by group and category (no fin_by_lens_category)"
    order = [r[0] for r in lenses][:7]
    label = {r[0]: r[1] for r in lenses}
    cats = []
    for r in flc:
        if r[1] not in cats:
            cats.append(r[1])
    cats = cats[:7]
    look = {(r[0], r[1]): r[3] for r in flc}
    grid = {"rows": [label.get(x, x) for x in order],
            "cols": [labels.clip(c, 13) for c in cats],
            "cells": [[look.get((x, c)) for c in cats] for x in order]}
    s, top = h["slide"]((
        "Which groups leak where — the two cuts the chapter reports "
        "separately, crossed",
        "share of each group holding a product in each category; blank means "
        "the group was not measured there"),
        "Leakage by group and category")
    path = h["chart"]("fin_heat", CT.heat_matrix, grid)
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


def what_leakers_hold(h, t, base):
    prof = t.get("fin_leakers_profile") or []
    rows = [r for r in prof if r[2] is not None and r[4] is not None][:9]
    if len(rows) < 2:
        return "What leakers hold with us (fin_leakers_profile too thin)"
    big = max(rows, key=lambda r: r[3] or 0)
    s, top = h["slide"]((
        f"Accounts paying an external {big[0].lower()} still hold "
        f"{money(big[3])} with us",
        "balance held here against tenure; bubble is accounts, crosshairs "
        "are the medians"), "What leakers hold with us")
    quad = [[labels.clip(r[0], 20), r[1], r[2], r[4]] for r in rows]
    path = h["chart"]("fin_quadrant", charts.branch_quadrant, quad,
                      bubble_label="bubble = accounts in the category",
                      xlabel="median balance held with us",
                      ylabel="median tenure, years")
    if path:
        h["chart_left"](s, path, top, RAIL_EDGE)


def how_the_leakage_builds(h, t, base):
    """concept 09, drawn with waterfall_bridge so the total must reconcile."""
    cat = sorted((t.get("fin_by_category") or []), key=lambda r: -r[4])[:6]
    if len(cat) < 3:
        return "How the leakage builds (too few categories)"
    steps = [[labels.clip(cat[0][0], 16), float(cat[0][4]), "start"]]
    for r in cat[1:]:
        steps.append([labels.clip(r[0], 16), float(r[4]), "up"])
    steps.append(["these six", float(sum(r[4] for r in cat)), "end"])
    s, top = h["slide"]((
        f"Six categories carry {money(sum(r[4] for r in cat))} of the "
        f"{money(t.get('fin_leakage_dollars'))} that leaves",
        "category by category up to the total — the number is built in "
        "front of the room, not asserted"), "How the leakage builds")
    path = h["chart"]("fin_build", charts.waterfall_bridge, steps)
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])
