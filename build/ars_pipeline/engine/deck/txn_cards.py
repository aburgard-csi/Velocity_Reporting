"""Card spend, behaviour, relationship and the closing narrative slides."""
from __future__ import annotations

from . import charts, charts_story as CS, charts_txn as CT, labels
from .txn_common import RAIL_EDGE, money

CARD_RAILS = {"PIN", "SIG"}
# (metric key, column, full label, short axis label, is_percent)
RADAR_AXES = [("fin_by_lens", 4, "addressable leakage %", "leakage", True),
              ("fin_by_lens", 5, "external $ per account", "external $", False),
              ("comp_by_lens", 4, "competitor penetration %", "competitor", True),
              ("comp_by_lens", 5, "multi-banked %", "multi-banked", True),
              ("mch_by_lens", 3, "card spend per account", "card spend", False),
              ("mch_by_lens", 4, "swipes per month", "swipes/mo", False)]


def _pair(t, key, a="responders", b="mailed_nonresp"):
    by = {r[0]: r for r in (t.get(key) or [])}
    return by.get(a), by.get(b)


def how_the_money_moves(h, t, base):
    """The marimekko: width is share of transactions, height is share of
    dollars. The rail that carries the money is the tall thin one."""
    ch = t.get("txn_by_channel") or []
    if len(ch) < 2:
        return "How the money moves (txn_by_channel too thin)"
    xfer = [r for r in ch if r[0] not in CARD_RAILS]
    tot_n = sum(r[1] for r in ch) or 1
    tot_d = sum(r[3] for r in ch) or 1
    n_pct = sum(r[1] for r in xfer) / tot_n * 100
    d_pct = sum(r[3] for r in xfer) / tot_d * 100
    if xfer and d_pct - n_pct >= 8:
        head = (f"ACH and check are {n_pct:.0f}% of transactions and "
                f"{d_pct:.0f}% of the dollars")
    else:
        head = "Where the volume is, and where the dollars are"
    s, top = h["slide"]((head,
        "column width is share of transactions, height is share of dollars"),
        "How the money moves")
    rows = [[r[0], r[1], r[3]] for r in ch]
    path = h["chart"]("txn_marimekko", CT.marimekko, rows)
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


def twelve_months(h, t, base):
    tm, mm = t.get("txn_monthly") or [], t.get("mch_monthly") or []
    if len(tm) < 3 or len(mm) < 3:
        return "Twelve months of flow (monthly series too short)"
    n = min(len(tm), len(mm))
    s, top = h["slide"]((
        f"{t.get('txn_months_covered', 0)} months on file, "
        f"{money(t.get('txn_spend_total'))} moved across "
        f"{t.get('txn_accounts', 0):,} accounts",
        "total transaction dollars against card dollars, both indexed to the "
        "first month so the two shapes are comparable"),
        "Twelve months of flow")
    series = [[tm[i][0][-5:], tm[i][3], mm[i][2]] for i in range(n)]
    path = h["chart"]("txn_monthly", charts.dual_series, series,
                      "all dollars", "card dollars")
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


def how_members_spend(h, t, base, merchant_bars):
    mtop = t.get("mch_top") or []
    if not mtop:
        return "How members spend (no mch_top)"
    m1 = mtop[0]
    s, top = h["slide"]((
        f"{str(m1[0]).title()} leads card spend at {money(m1[3])} across "
        f"{m1[1]:,} accounts — the top 15 merchants take "
        f"{t.get('mch_top15_share_pct', 0):.0f}% of card dollars",
        f"{t.get('mch_distinct', 0):,} distinct merchants; categories by "
        f"{t.get('mch_category_method')} (MCC on "
        f"{t.get('mch_mcc_coverage_pct', 0):.0f}% of card rows)"),
        "How members spend")
    items = [("Card spend", money(t.get("mch_card_spend")),
              f"{t.get('mch_card_accounts', 0):,} card accounts"),
             ("Concentration", f"{t.get('mch_merchants_for_80pct', 0):,}",
              "merchants make 80% of card dollars")]
    if t.get("beh_ticket_median") is not None:
        items.append(("Median ticket", f"${t['beh_ticket_median']:.2f}",
                      f"{t.get('beh_txns_per_active_acct_mo', 0)} "
                      f"txns/active acct/mo"))
    right = h["rail"](s, items, top=top)
    path = h["chart"]("mch_top", merchant_bars, mtop)
    if path:
        h["chart_left"](s, path, top, right)


def card_spend_by_category(h, t, base):
    """Now a two-level taxonomy, so lead with the roll-up."""
    par = t.get("mch_by_parent") or []
    cats = t.get("mch_by_category") or []
    rows = par or [[r[0], r[2], r[4]] for r in cats]
    if not rows:
        return "Card spend by category (no mch_by_category)"
    top_row = rows[0]
    s, top = h["slide"]((
        f"{top_row[0]} takes {top_row[-1]:.0f}% of card dollars",
        f"grouped by {t.get('mch_category_method')} — MCC on "
        f"{t.get('mch_mcc_coverage_pct', 0):.0f}% of card rows; the detail "
        f"sits in the appendix"), "Card spend by category")
    tier = [[labels.clip(r[0], 22), r[-2], r[-1]] for r in rows]
    path = h["chart"]("mch_parents", charts.tier_bars, tier, value_idx=2,
                      label="dollars", share=False, fmt="{:,.1f}%")
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


def ticket_and_intensity(h, t, base):
    tb, ib = t.get("beh_ticket_bands") or [], t.get("beh_intensity_bands") or []
    if not (tb and ib):
        return "Ticket and intensity (no behaviour bands)"
    tpk, ipk = max(tb, key=lambda r: r[2]), max(ib, key=lambda r: r[2])
    s, top = h["slide"]((
        f"The typical swipe is {tpk[0]} and the typical account swipes "
        f"{ipk[0]} times a month",
        "what a card transaction looks like, and how often it happens"),
        "Ticket and intensity")
    panels = [("Ticket size", f"of swipes are {tpk[0]}", tpk[2],
               [(f"${t.get('beh_ticket_median', 0):.2f}", "median ticket"),
                (f"{tb[-1][2]:.1f}%", f"above {tb[-1][0]}")]),
              ("Intensity", f"of accounts swipe {ipk[0]} a month", ipk[2],
               [(f"{t.get('beh_txns_per_active_acct_mo', 0)}",
                 "swipes per active account"),
                (f"{t.get('beh_recurring_txn_pct', 0):.0f}%",
                 "of swipes are recurring")])]
    path = h["chart"]("beh_bands", charts.split_panels, panels)
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


def when_the_card_is_used(h, t, base):
    grid, rows, cols = (t.get("beh_heat_grid"), t.get("beh_heat_rows"),
                        t.get("beh_heat_cols"))
    if not (grid and rows and cols):
        return "When the card gets used (no beh_heat_grid)"
    live = sum(1 for r in grid for v in r if v)
    if live <= len(cols):
        return ("When the card gets used (heat grid degenerate — no parseable "
                "timestamps)")
    peak = t.get("beh_peak") or []
    s, top = h["slide"]((
        f"The busiest block is {peak[0]} {peak[1]}" if peak else
        "When the card gets used",
        "weekday against hour block — descriptive colour, not a KPI"),
        "When the card gets used")
    path = h["chart"]("beh_heat", CT.heat_matrix,
                      {"rows": rows, "cols": cols, "cells": grid},
                      fmt="{:,.0f}")
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


def recurring_on_the_card(h, t, base):
    rc = t.get("beh_top_recurring") or []
    if not rc:
        return "Recurring payments on the card (no beh_top_recurring)"
    s, top = h["slide"]((
        f"{t.get('beh_accounts_with_recurring_pct', 0):.0f}% of accounts "
        f"carry a subscription on the card",
        "the counterparties riding the card every month, by how many "
        "accounts they reach"), "Recurring payments on the card")
    # tier_bars, not branch_bars (same v5 defect as who_leads_each_product, 2026-09-30)
    rows = [[f"{labels.clip(str(r[0]).title(), 18)}\n{money(r[3])}", r[1]]
            for r in rc[:9]]
    path = h["chart"]("beh_recurring", charts.tier_bars, rows, value_idx=1,
                      share=False, fmt="{:,.0f}", label="accounts")
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


def card_behaviour_by_lens(h, t, base):
    r_, c_ = _pair(t, "beh_by_lens")
    if not (r_ and c_) or r_[3] is None or c_[3] is None:
        return "Card behaviour by lens (no responder/control pair)"
    s, top = h["slide"]((
        "The campaign tail, measured on the card itself",
        "responders against mailed non-responders on ticket, frequency and "
        "recurring share"), "Card behaviour by lens")
    dumb = [["Median ticket", r_[3], c_[3], f"${r_[3]:.2f} vs ${c_[3]:.2f}"],
            ["Swipes per account per month", r_[4], c_[4],
             f"{r_[4]} vs {c_[4]}"],
            ["Recurring share of swipes", r_[5], c_[5],
             f"{r_[5]:.1f}% vs {c_[5]:.1f}%"]]
    path = h["chart"]("beh_by_lens", charts.dumbbell, dumb, "responders",
                      "mailed non-responders")
    if path:
        h["chart_left"](s, path, top, RAIL_EDGE)


def engagement_breadth(h, t, base):
    """Breadth cannot be measured on a card-only feed; say so rather than
    reporting 100% single-channel as if it were behaviour."""
    br = t.get("rel_breadth") or []
    rails = {r[0] for r in (t.get("txn_by_channel") or [])}
    if not br:
        return "Engagement breadth (no rel_breadth)"
    if rails and not (rails - CARD_RAILS):
        return (f"Engagement breadth (feed carries only "
                f"{'/'.join(sorted(rails))} — breadth is an artefact of the "
                f"extract, not a finding)")
    s, top = h["slide"]((
        f"{t.get('rel_single_channel_pct', 0):.0f}% of transacting accounts "
        f"touch us through a single channel — a mean of "
        f"{t.get('rel_breadth_mean', 0)} channels out of 4",
        "channels are card, ACH, check and P2P"), "Engagement breadth")
    items = [("Primary-like", f"{t.get('rel_primary_like_n', 0):,}",
              f"{t.get('rel_primary_like_pct', 0):.0f}% with 2+ channels and "
              f"10+ txns/mo"),
             ("Recurring billers", f"{t.get('rel_billers_mean', 0)}",
              "per account, mean")]
    db = t.get("rel_depth_by_breadth") or []
    if db:
        items.append(("Depth by breadth", f"{db[-1][2]} txn/mo",
                      f"at {db[-1][0]} channels vs {db[0][2]} at {db[0][0]}"))
    right = h["rail"](s, items, top=top)
    rows = [[f"{r[0]} channel" + ("s" if r[0] > 1 else ""), r[1]]
            for r in br if r[1]]
    path = h["chart"]("rel_breadth", charts.composition, rows)
    if path:
        h["chart_left"](s, path, top, right)


def responder_profile(h, t, base):
    """Six measures as one outline; the column beside it carries the real
    numbers, because a normalised value on screen reads as a measurement."""
    axes, short, a_v, b_v, raw = [], [], [], [], []
    for key, idx, label, brief, is_pct in RADAR_AXES:
        r_, c_ = _pair(t, key)
        if not (r_ and c_) or idx >= len(r_) or idx >= len(c_):
            continue
        av, bv = r_[idx], c_[idx]
        if av is None or bv is None:
            continue
        peak = max(float(av), float(bv)) * 1.18 or 1
        axes.append(label)
        short.append(brief)
        a_v.append(float(av) / peak)
        b_v.append(float(bv) / peak)
        if is_pct:
            raw.append(f"{float(av):.1f}%  vs  {float(bv):.1f}%")
        else:
            fmt = (lambda v: money(v) if v > 200 else f"{v:g}")
            raw.append(f"{fmt(float(av))}  vs  {fmt(float(bv))}")
    if len(axes) < 4:
        return "The responder profile (fewer than four measurable axes)"
    s, top = h["slide"]((
        "Responders are not just busier — they are broader, and they bank in "
        "more places",
        "six measures on one outline, each scaled to the larger of the two "
        "cohorts; the column carries the real numbers"),
        "The responder profile")
    path = h["chart"]("txn_radar", CS.radar, short, a_v, b_v, "responders",
                      "mailed non-responders", raw)
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


def every_group_against_the_book(h, t, base):
    cbl = t.get("comp_by_lens") or []
    book = next((r for r in cbl if r[0] == "all"), None)
    rows = [r for r in cbl if r[0] != "all"][:6]
    if not (book and rows):
        return "Every group against the book (no comp_by_lens)"
    over = [r for r in rows if r[4] > book[4]]
    head = (f"{over[0][1]} run at {over[0][4]:.0f}% competitor penetration "
            f"against a book of {book[4]:.0f}%" if over else
            f"Every group sits at or below the book's {book[4]:.0f}% "
            f"competitor penetration")
    s, top = h["slide"]((head,
        f"the bar is the group, the rule is the book average across "
        f"{book[2]:,} accounts; orange is below it"),
        "Every group against the book")
    bul = [[f"{labels.clip(r[1], 26)}  ({r[2]:,})", r[4], book[4],
            f"{r[4] - book[4]:+.1f} pts"] for r in rows]
    path = h["chart"]("comp_bullet", CS.bullet, bul,
                      f"the book average, {book[4]:.0f}%")
    if path:
        h["chart_left"](s, path, top, RAIL_EDGE)


def what_the_banker_opens(h, t, base):
    prof = t.get("fin_leakers_profile") or []
    ranked = sorted(prof, key=lambda r: -(r[3] or 0))[:7]
    if not ranked:
        return "What the banker actually opens (no fin_leakers_profile)"
    s, top = h["slide"]((
        "The chapter ends in a list with names on it, not a chart",
        "one row per addressable category — the CSVs under lists/ carry the "
        "accounts themselves, sorted for outreach"),
        "What the banker actually opens")
    rows = [[labels.clip(r[0], 26),
             f"{r[1]:,} accounts · {r[4]} yrs · {r[5]:.0f}% responders",
             money(r[3]), i < 2] for i, r in enumerate(ranked)]
    path = h["chart"]("fin_worklist", CS.worklist,
                      ["category", "who is in it", "held with us", ""], rows)
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


def dictionary_gaps(h, t, base):
    """A depository token means the counterparty is an institution -- a
    LocalCompetitors candidate. Everything else is a product for the finserv
    dictionary. Splitting the queue that way is the CSM's next action."""
    pool = t.get("fin_review_queue") or t.get("fin_unmatched_top") or []
    if not pool:
        return "What the dictionary does not know yet (no fin_review_queue)"
    toks = {"BANK", "BK", "CU", "FCU", "UNION", "BANCORP", "SAVINGS",
            "TRUST", "FSB"}

    def is_institution(name):
        return bool(toks & set(str(name).upper().replace("*", " ").split()))

    rows = [[r[0], r[2], r[2], is_institution(r[0])] for r in pool[:20]]
    named = [r for r in rows if r[3]]
    head = (f"{len(named)} unclassified counterparties are named institutions "
            f"— {str(named[0][0]).title()} among them" if named else
            f"{str(pool[0][0]).title()} moves {money(pool[0][2])} a year and "
            f"is not in any dictionary yet")
    s, top = h["slide"]((head,
        "orange is a depository name — those are LocalCompetitors "
        "candidates; the rest are products for the finserv dictionary"),
        "What the dictionary does not know yet")
    note = (f"{len(named)} of {len(rows)} are institutions · "
            f"{money(t.get('fin_review_queue_dollars'))} behind the queue")
    path = h["chart"]("fin_ledger", CS.ledger, rows, note=note)
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])
