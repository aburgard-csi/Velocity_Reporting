# Ported from ARS v5 02-Scripts/ars/deck/txn_leakage.py at a491b5c (James Gilmore); logic unchanged.
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
    # RPE: every band is UNIQUE accounts, and says so -- "Still within reach" counts
    # account-category pairs, and 11,669 against 13,983 read as two answers to one question
    # (Sheila's 1798 slide review, 2026-10-30)
    stages = [["Transacting accounts", t.get("txn_accounts") or total, 0, 0],
              [labels.clip(str(base).capitalize(), 34), total, 0, 0],
              ["Pay an outside financial product", leak, 0, 0],
              ["In a category we offer (addressable)",
               t.get("fin_addressable_accounts") or 0, 0, 0],
              ["Paid it in the last 90 days",
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
        "unique accounts, each counted once however many categories it pays; "
        "each band is a real filter"),
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
    """RPE: the one slide for the leakage total. "Their financial life", "Where the leakage goes"
    and "How the leakage builds" said the same total three more times (Sheila's 1798 slide review,
    2026-10-30, group A); this slide now carries the top categories and the addressable callout."""
    cat = t.get("fin_by_category")
    head = (f"{t.get('fin_leaking_pct', 0):.0f}% of {base} send "
            f"{money(t.get('fin_leakage_dollars'))} a year to other "
            f"institutions' financial products")
    share = t.get("fin_leakage_pct_of_transfer_dollars")
    sub = ((f"{share:.0f}% of all ACH and check dollars; " if share is not None
            else "card rails only, transfers to other institutions are not in this file; ")
           + f"{t.get('fin_addressable_accounts', 0):,} accounts in addressable "
             f"categories, {money(t.get('fin_addressable_dollars'))}")
    s, top = h["slide"]((head, sub), "Where the money goes")
    right = h["rail"](s, [
        ("Leaking", f"{t.get('fin_leaking_accounts', 0):,}",
         f"of {t.get('fin_accounts_total', 0):,} {base}"),
        ("Per year", money(t.get("fin_leakage_dollars")),
         "to external financial products"),
        ("Addressable", money(t.get("fin_addressable_dollars")),
         "in categories the institution offers"),
        _top_categories_item(t),
    ], top=top)
    path = h["chart"]("fin_categories", category_bars, cat)
    if path:
        h["chart_left"](s, path, top, right)


def _top_categories_item(t):
    """The rail tile that replaces "How the leakage builds": the biggest leakage categories'
    share of the total."""
    cat = sorted((r for r in (t.get("fin_by_category") or []) if r[6] == "leakage"),
                 key=lambda r: -r[4])[:6]
    if len(cat) < 2:
        return ("Two or more", f"{t.get('fin_multi_category_pct', 0):.0f}%",
                "of leakers, in 2+ categories")
    return (f"Top {_count_word(len(cat)).lower()}", money(sum(r[4] for r in cat)),
            f"of {money(t.get('fin_leakage_dollars'))}, by category")


def where_the_leakage_goes(h, t, base):
    """flow_ribbons on the leakage flow -- built and tested since #74 phase 2
    and never called by a slide until now."""
    # RPE: leakage categories only -- fin_by_category also carries the adjacency rows (payment
    # apps), which fin_leakage_dollars, the headline's total, does not count
    cat = [r for r in (t.get("fin_by_category") or []) if r[6] == "leakage"]
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
    """The Pareto that replaces the three-column provider table.

    RPE: financial-product categories only. v5 ranked the payment-app rows too, so Cash App's
    $78.1M of P2P flow led a slide that sits beside a $49.6M financial-product total (Sheila's
    1798 slide review, 2026-10-30); the payment apps have their own slide in Competition."""
    provs = t.get("fin_top_providers") or {}
    kind = {r[0]: r[6] for r in (t.get("fin_by_category") or [])}
    flat = []
    for cat, rows in provs.items():
        if kind.get(cat, "leakage") != "leakage":
            continue
        for r in rows:
            if str(r[0]).startswith("("):          # "(unnamed)" is not a provider
                continue
            flat.append([r[0], cat, r[2]])
    flat.sort(key=lambda r: -r[2])
    flat = flat[:10]
    if not flat:
        return "Who they pay (no fin_top_providers)"
    top = flat[0]
    s, y = h["slide"]((
        f"{labels.display_name(top[0])} alone takes {money(top[2])} of the "
        f"{money(t.get('fin_leakage_dollars'))} paid to outside financial products",
        "named providers by dollars, financial products only; payment apps "
        "are P2P flow, shown in Competition"), "Who they pay")
    rows = [[labels.clip(labels.display_name(r[0]), 28), labels.clip(r[1], 18), r[2]]
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
    pts = "{:+.1f} pts"
    dollars = lambda d: ("+" if d >= 0 else "") + money(d)
    dumb = [["Accounts in addressable categories", r_[4], c_[4],
             f"{r_[3]:,} vs {c_[3]:,}", "{:.1f}%", pts],
            ["Dollars per addressable account", r_[5], c_[5],
             f"${r_[5]:,} vs ${c_[5]:,}", money, dollars],
            ["P2P or fintech use", r_[7], c_[7],
             f"{r_[6]:,} vs {c_[6]:,} accounts", "{:.1f}%", pts]]
    path = h["chart"]("fin_by_lens", charts.dumbbell, dumb, "responders",
                      "mailed non-responders", own_scale=True)
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
            "cols": [labels.clip(c, 24) for c in cats],
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


# ---- leakage by member age, account age and branch (R5) ---------------------------------------
# James, 2026-11-05: "it would be nice to have the age band lens, maybe branch lens. account age
# lens". fin_by_* rows (transaction_intelligence/band_lenses.py): [band, accounts, paying,
# paying_pct, dollars_per_payer, top_category, top_category_accounts]. The competitor share comes
# from comp_by_age_band / comp_by_tenure_band (same row shape, same accounts per band) or, for
# branches, from competition's own comp_by_branch ([branch, accounts, with_competitor, pct, ...,
# top_institution]), which divides by the same transacting accounts.
BAND_CHART_MAX = 8


def _lead_band(rows):
    """The band with the highest leaking share, and every band tied with it."""
    best = max(r[3] for r in rows)
    tied = [r for r in rows if r[3] == best]
    return max(tied, key=lambda r: r[1]), tied


def _leakage_by_band(h, t, key, comp_key, comp_pct_idx, comp_top_idx, comp_n_idx, title,
                     who, unit, chart_name, rows=None, scope=""):
    """`who` is the headline's lead-in to a band name ("Members aged ", "" for a branch)."""
    rows = rows if rows is not None else (t.get(key) or [])
    if len(rows) < 2:
        return f"{title} (fewer than two {key} rows)"
    comp = {r[0]: r for r in (t.get(comp_key) or [])}
    lead, tied = _lead_band(rows)
    plural = f"{unit}{'es' if unit == 'branch' else 's'}"
    if len(tied) > 2:
        head = (f"{_count_word(len(tied))} {plural} tie for the most leakage — "
                f"{lead[3]:.0f}% of accounts in each pay an outside financial product")
    elif len(tied) == 2:
        head = (f"{who}{tied[0][0]} and {tied[1][0]} leak the most — {lead[3]:.0f}% "
                f"of accounts in each pay an outside financial product")
    else:
        head = (f"{who}{lead[0]} {'leaks' if unit == 'branch' else 'leak'} the most — "
                f"{lead[3]:.0f}% {'of its accounts ' if unit == 'branch' else ''}"
                f"pay an outside financial product")
    sub = (f"share of transacting accounts in each {unit}{scope} paying an outside financial "
           f"product and a named competitor; {money(lead[4])} of leakage per leaking account "
           f"in {lead[0]} over the window")
    if not comp:
        sub += " (no competitor cut for this client)"
    s, top = h["slide"]((head, sub), title)
    items = [("Accounts", f"{sum(r[1] for r in rows):,}", f"transacting, across {len(rows)} {plural}"),
             ("Most leakage", labels.clip(lead[0], 18),
              f"{money(lead[4])} per leaking account, window total")]
    if lead[5]:
        items.append(("Top product", labels.clip(lead[5], 18),
                      f"{lead[6]:,} accounts in {lead[0]}"))
    c = comp.get(lead[0])
    if c and c[comp_top_idx]:
        n = c[comp_n_idx] if comp_n_idx is not None else None
        items.append(("Top competitor", labels.clip(c[comp_top_idx], 18),
                      f"{n:,} accounts in {lead[0]}" if n is not None
                      else f"most accounts in {lead[0]}"))
    right = h["rail"](s, items, top=top)
    path = h["chart"](chart_name, charts.grouped_bars,
                      [labels.clip(r[0], 12) for r in rows],
                      [r[3] for r in rows],
                      [(comp[r[0]][comp_pct_idx] if r[0] in comp else 0) for r in rows],
                      "outside financial product", "named competitor", fmt="{:.0f}%")
    if path:
        h["chart_left"](s, path, top, right)


def leakage_by_member_age(h, t, base):
    return _leakage_by_band(h, t, "fin_by_age_band", "comp_by_age_band", 3, 5, 6,
                            "Leakage by member age", "Members aged ", "age band",
                            "fin_by_age_band")


def leakage_by_account_tenure(h, t, base):
    return _leakage_by_band(h, t, "fin_by_tenure_band", "comp_by_tenure_band", 3, 5, 6,
                            "Leakage by account tenure", "Accounts open ",
                            "tenure band", "fin_by_tenure_band")


def leakage_by_branch(h, t, base):
    """The largest branches by transacting accounts; comp_by_branch supplies the competitor share
    on the same accounts (it is competition's table, not a second branch cut)."""
    rows = sorted(t.get("fin_by_branch") or [], key=lambda r: (-r[1], r[0]))
    shown = rows[:BAND_CHART_MAX]
    scope = f" (the {len(shown)} largest)" if len(rows) > len(shown) else ""
    return _leakage_by_band(h, t, "fin_by_branch", "comp_by_branch", 3, 6, None,
                            "Leakage by branch", "", "branch", "fin_by_branch",
                            rows=shown, scope=scope)


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
                      ylabel="median tenure, years", xfmt=money)
    if path:
        h["chart_left"](s, path, top, RAIL_EDGE)


def _count_word(n):
    return {3: "Three", 4: "Four", 5: "Five", 6: "Six"}.get(n, str(n))


def how_the_leakage_builds(h, t, base):
    """concept 09, drawn with waterfall_bridge so the total must reconcile."""
    # RPE: v5 sorted every category, adjacency (payment apps) included, so for 1776 the six
    # summed to $45.1M "of the $22.9M that leaves" -- fin_leakage_dollars counts leakage only
    cat = sorted((r for r in (t.get("fin_by_category") or []) if r[6] == "leakage"),
                 key=lambda r: -r[4])[:6]
    if len(cat) < 3:
        return "How the leakage builds (too few categories)"
    steps = [[labels.clip(cat[0][0], 28), float(cat[0][4]), "start"]]
    for r in cat[1:]:
        steps.append([labels.clip(r[0], 28), float(r[4]), "up"])
    steps.append([f"these {_count_word(len(cat)).lower()}", float(sum(r[4] for r in cat)), "end"])
    s, top = h["slide"]((
        f"{_count_word(len(cat))} categories carry {money(sum(r[4] for r in cat))} of the "
        f"{money(t.get('fin_leakage_dollars'))} that leaves",
        "category by category up to the total — the number is built in "
        "front of the room, not asserted"), "How the leakage builds")
    path = h["chart"]("fin_build", charts.waterfall_bridge, steps)
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


PAIR_GRID_CATEGORIES = 7


def which_services_travel_together(h, t, base):
    """Legacy 13: the co-occurrence grid. Which external products the same
    account holds together -- the bundle a retention offer should carry."""
    pairs = t.get("fin_category_pairs") or []
    if not pairs:
        return "Which services travel together (no fin_category_pairs)"
    weight: dict = {}
    for a, b, n in pairs:
        weight[a] = weight.get(a, 0) + n
        weight[b] = weight.get(b, 0) + n
    cats = sorted(weight, key=lambda c: (-weight[c], c))[:PAIR_GRID_CATEGORIES]
    shared = {(a, b): n for a, b, n in pairs}
    cells = [[None if r == c else shared.get((r, c), shared.get((c, r), 0))
              for c in cats] for r in cats]
    a, b, n = pairs[0]
    s, top = h["slide"]((
        f"{n:,} accounts hold both {a.lower()} and {b.lower()} elsewhere — "
        f"the products that leave together",
        f"accounts shared by each pair of external categories, among {base} "
        f"in two or more; the diagonal is blank by design"),
        "Which services travel together")
    grid = {"rows": [labels.clip(c, 18) for c in cats],
            "cols": [labels.clip(c, 24) for c in cats], "cells": cells}
    path = h["chart"]("fin_pairs", CT.heat_matrix, grid, fmt="{:,.0f}",
                      note=f"{len(pairs)} pairs seen; the {len(cats)} most "
                           f"shared categories shown")
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


def still_within_reach(h, t, base):
    """Legacy 18: the opportunity. Addressable dollars whose relationship is
    active or cooling -- paid within 90 days -- ranked by category."""
    reach = t.get("fin_reach") or []
    if not reach:
        return "Still within reach (no fin_reach)"
    live = [r for r in reach if r[5] > 0]
    if not live:
        return "Still within reach (no addressable relationship paid within 90 days)"
    reach_d = t.get("fin_reach_dollars") or 0
    addr_d = t.get("fin_addressable_dollars") or 0
    n_live = sum(r[2] for r in reach)
    n_all = sum(r[1] for r in reach)
    top_r = live[0]
    s, top = h["slide"]((
        f"{money(reach_d)} of the {money(addr_d)} addressable is still "
        f"moving — paid within the last 90 days",
        f"addressable categories only, among {base}; a relationship is one "
        f"account in one category, so an account in two counts twice"), "Still within reach")
    # RPE: 13,983 here is account-category PAIRS; "The book, narrowed" counts the same accounts
    # once each (11,669). Each figure now names its base (Sheila's 1798 slide review, 2026-10-30).
    uniq = t.get("fin_addressable_active_accounts")
    right = h["rail"](s, [
        ("Within reach", money(reach_d), "active or cooling, addressable"),
        ("Relationships", f"{n_live:,}",
         (f"{uniq:,} unique accounts" if uniq else f"of {n_all:,} addressable")
         + ", paid in 90 days"),
        ("Gone cold", money(addr_d - reach_d), "dormant or lapsed"),
        ("Biggest", labels.clip(top_r[0], 20),
         f"{money(top_r[5])} · {top_r[3]:.0f}% of its accounts live"),
    ], top=top)
    items = [[labels.clip(r[0], 18), r[5]] for r in live[:8]]
    path = h["chart"]("fin_reach", charts.value_waterfall, items)
    if path:
        h["chart_left"](s, path, top, right)
