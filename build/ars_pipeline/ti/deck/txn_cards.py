# Ported from ARS v5 02-Scripts/ars/deck/txn_cards.py at a491b5c (James Gilmore); logic unchanged.
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
    # labels as keywords: the harness appends the output path after the
    # positionals, so a positional label would land in `out` (#245, 1776)
    path = h["chart"]("txn_monthly", charts.dual_series, series,
                      l1="all dollars", l2="card dollars")
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


def _key(name) -> str:
    return "".join(ch for ch in str(name).upper() if ch.isalnum())


def payment_app_names(t) -> set:
    """The payment apps the competition chapter ranks (comp_ecosystems), as name keys."""
    return {_key(r[0]) for r in (t.get("comp_ecosystems") or [])}


def how_members_spend(h, t, base, merchant_bars):
    mtop = t.get("mch_top") or []
    if not mtop:
        return None
    # RPE: lead with the biggest merchant that is not a payment app. Cash App's card-funded P2P
    # led this slide at $78.3M beside a $49.6M leakage total; it is one figure, on the payment-app
    # slide (Sheila's 1798 slide review, 2026-10-30, group B). Its bar stays in the chart.
    apps = payment_app_names(t)
    shops = [r for r in mtop if _key(r[0]) not in apps]
    m1 = shops[0] if shops else mtop[0]
    app_note = (f"; {labels.display_name(mtop[0][0])} at {money(mtop[0][3])} is card-funded P2P, "
                f"shown with the payment apps" if shops and m1 is not mtop[0] else "")
    s, top = h["slide"]((
        f"{labels.display_name(m1[0])} leads card spend at {money(m1[3])} across "
        f"{m1[1]:,} accounts — the top 15 merchants take "
        f"{t.get('mch_top15_share_pct', 0):.0f}% of card dollars",
        f"{t.get('mch_distinct', 0):,} distinct merchants" + app_note),
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
    # RPE: the top MCC codes ride on this slide's rail; "The MCC codes behind the categories"
    # was a second card-mix slide (Sheila's 1798 slide review, 2026-10-30, group C)
    mcc = t.get("mch_mcc_top") or []
    cov = t.get("mch_mcc_coverage_pct") or 0
    head = f"{top_row[0]} takes {top_row[-1]:.0f}% of card dollars"
    if mcc:
        head += f"; MCC {mcc[0][0]} ({str(mcc[0][1]).lower()}) alone takes {mcc[0][6]:.0f}%"
    sub = (f"grouped by {t.get('mch_category_method')}; MCC on {cov:.0f}% of card rows"
           + (f", the top five codes take {t.get('mch_mcc_top5_share_pct', 0):.0f}% of coded "
              f"card dollars" if mcc else ""))
    s, top = h["slide"]((head, sub), "Card spend by category")
    right = h["RIGHT_EDGE"]
    if mcc:
        items = [(f"MCC {r[0]}", f"{r[6]:.0f}%", f"{labels.clip(str(r[1]), 18)} · {money(r[4])}")
                 for r in mcc[:4]]
        items.append(("Top five codes", f"{t.get('mch_mcc_top5_share_pct', 0):.0f}%",
                      f"of coded card dollars; {t.get('mch_mcc_distinct', 0):,} codes"))
        right = h["rail"](s, items, top=top)
    tier = [[labels.clip(r[0], 22), r[-2], r[-1]] for r in rows]
    path = h["chart"]("mch_parents", charts.tier_bars, tier, value_idx=2,
                      label="dollars", share=False, fmt="{:,.1f}%")
    if path:
        h["chart_left"](s, path, top, right)


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


def _weekend_is_empty(grid, rows):
    """True when Saturday and Sunday carry nothing while the weekdays do: the file's date is
    the posting date, which moves weekend activity onto Monday (issue #88)."""
    wk = [i for i, r in enumerate(rows) if str(r)[:3].lower() in ("sat", "sun")]
    if not wk and len(rows) == 7:
        wk = [5, 6]
    if not wk:
        return False
    weekend = sum(v or 0 for i in wk for v in grid[i])
    weekdays = sum(v or 0 for i, r in enumerate(grid) if i not in wk for v in r)
    return weekend == 0 and weekdays > 0


def when_the_card_is_used(h, t, base):
    grid, rows, cols = (t.get("beh_heat_grid"), t.get("beh_heat_rows"),
                        t.get("beh_heat_cols"))
    if not (grid and rows and cols):
        return None
    live = sum(1 for r in grid for v in r if v)
    if live <= len(cols):
        return ("When the card gets used (heat grid degenerate — no parseable "
                "timestamps)")
    peak = t.get("beh_peak") or []
    if _weekend_is_empty(grid, rows):
        # the date is the posting date: weekend swipes post on Monday, so Monday's weight and
        # the empty weekend are the calendar, not the members' habit
        s, top = h["slide"]((
            "When the card posts: weekend activity appears on Monday",
            "posting dates, not transaction dates; weekday against hour block — "
            "descriptive colour, not a KPI"),
            "When the card gets used")
    else:
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
        return None
    s, top = h["slide"]((
        f"{t.get('beh_accounts_with_recurring_pct', 0):.0f}% of accounts "
        f"carry a subscription on the card",
        "the counterparties riding the card every month, by how many "
        "accounts they reach"), "Recurring payments on the card")
    rows = [[labels.clip(labels.display_name(r[0]), 24), r[1], money(r[3])]
            for r in rc[:9]]
    path = h["chart"]("beh_recurring", charts.branch_bars, rows,
                      portfolio=0, show_n=False)
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
    ticket = lambda d: ("+" if d >= 0 else "-") + f"${abs(d):.2f}"
    dumb = [["Median ticket", r_[3], c_[3], f"${r_[3]:.2f} vs ${c_[3]:.2f}",
             "${:.2f}", ticket],
            ["Swipes per account per month", r_[4], c_[4],
             f"{r_[4]} vs {c_[4]}", "{:.1f}", "{:+.1f}"],
            ["Recurring share of swipes", r_[5], c_[5],
             f"{r_[5]:.1f}% vs {c_[5]:.1f}%", "{:.1f}%", "{:+.1f} pts"]]
    path = h["chart"]("beh_by_lens", charts.dumbbell, dumb, "responders",
                      "mailed non-responders", own_scale=True)
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
        f"touch us through a single channel — mean breadth "
        f"{t.get('rel_breadth_mean', 0)} of 4",
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
    # RPE: the one responder-against-the-rest slide. "Leakage by group" drew three of these six
    # measures again and "Every group against the book" the competitor rate by group; the not-
    # mailed comparison it made rides in the subtitle (Sheila's 1798 slide review, 2026-10-30,
    # group E)
    by = {r[0]: r for r in (t.get("comp_by_lens") or [])}
    book, nm = by.get("all"), by.get("not_mailed")
    sub = ("six measures, each scaled to the larger of the two groups; the column carries "
           "the real numbers")
    if book and nm and nm[4] is not None and book[4] is not None:
        sub += (f"; accounts never mailed run at {nm[4]:.0f}% competitor penetration "
                f"against a book of {book[4]:.0f}%")
    s, top = h["slide"]((
        "Responders are not just busier — they are broader, and they bank in "
        "more places", sub),
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
        return None
    toks = {"BANK", "BK", "CU", "FCU", "UNION", "BANCORP", "SAVINGS",
            "TRUST", "FSB"}

    def is_institution(name):
        return bool(toks & set(str(name).upper().replace("*", " ").split()))

    # RPE: twelve rows, so the names print at slide size (Sheila's 1798 slide review, 2026-10-30)
    rows = [[r[0], r[2], r[2], is_institution(r[0])] for r in pool[:12]]
    named = [r for r in rows if r[3]]
    if len(named) == 1:
        # "1 unclassified counterparties are" shipped on 1798 (Sheila's review, 2026-10-30)
        head = (f"One unclassified counterparty is a named institution: "
                f"{labels.display_name(named[0][0])}")
    elif named:
        head = (f"{len(named)} unclassified counterparties are named institutions "
                f"— {labels.display_name(named[0][0])} among them")
    else:
        head = (f"{labels.display_name(pool[0][0])} moves {money(pool[0][2])} a year and "
                f"is not in any dictionary yet")
    s, top = h["slide"]((head,
        "orange is a depository name — those are LocalCompetitors "
        "candidates; the rest are products for the finserv dictionary"),
        "What the dictionary does not know yet")
    note = (f"{len(named)} of {len(rows)} " + ("is an institution" if len(named) == 1
                                                  else "are institutions") + " · "
            f"{money(t.get('fin_review_queue_dollars'))} behind the queue")
    path = h["chart"]("fin_ledger", CS.ledger, rows, note=note)
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


# ---- merchants, MCC codes and the card book by holder (#258 group 3) --------
# Legacy merchant 06-09, 11, 13; mcc_code 01-09, 13-14; general 11, 13-15,
# 21, 23-28 and the personal / business mirrors, collapsed to six questions.

def _title(name) -> str:
    """RPE: labels.display_name, never str.title() ("Circlek", "Lowe'S", "Wal Mart" on 1798,
    Sheila's slide review, 2026-10-30)."""
    return labels.display_name(name)


def _merge_by_name(rows):
    """mch_growth rows [merchant, accounts_recent, prior, recent, change, pct] with one display name
    combined: a merchant whose descriptor changed inside the window ("CIRCLE K" -> "CIRCLEK" on 1798)
    otherwise reads as one merchant up $4.6M and another down $4.7M. Dollars add; the accounts are
    the larger of the two, since the same account can sit under both descriptors. Returns the rows,
    names in display case, and the names that were combined. RPE addition, not in v5."""
    out, seen, merged = [], {}, []
    for r in rows:
        name = _title(r[0])
        if name in seen:
            m = seen[name]
            m[1] = max(m[1], r[1])
            m[2] += r[2]
            m[3] += r[3]
            m[4] = m[3] - m[2]
            m[5] = (m[4] / m[2] * 100) if m[2] else 0.0
            if name not in merged:
                merged.append(name)
            continue
        m = [name, r[1], r[2], r[3], r[4], r[5]]
        seen[name] = m
        out.append(m)
    return out, merged


def merchants_rising_and_falling(h, t, base):
    """Two trailing windows per merchant on one connector: the recent
    window is the subject dot, the prior window the tint."""
    rows = t.get("mch_growth") or []
    if not rows:
        return "Merchants rising and falling (no mch_growth)"
    rows, merged = _merge_by_name(rows)
    risers = sorted((r for r in rows if r[4] > 0), key=lambda r: -r[4])
    fallers = sorted((r for r in rows if r[4] < 0), key=lambda r: r[4])
    if risers and fallers:
        head = (f"{_title(risers[0][0])} is up {money(risers[0][4])} window over "
                f"window; {_title(fallers[0][0])} is down {money(-fallers[0][4])}")
    elif risers:
        head = f"{_title(risers[0][0])} is up {money(risers[0][4])} window over window"
    else:
        head = f"{_title(fallers[0][0])} is down {money(-fallers[0][4])} window over window"
    s, top = h["slide"]((head,
        f"card dollars {t.get('mch_growth_window')}, {base}; merchants moving "
        f"$1k+ in a window, the biggest risers and fallers by dollars"),
        "Merchants rising and falling")
    items = [("Book", f"{t.get('mch_growth_book_pct', 0):+.1f}%",
              "card dollars, window over window"),
             ("Rising", f"{t.get('mch_growth_rising_n', 0):,}",
              f"of {t.get('mch_growth_ranked_n', 0):,} merchants up 10% or more"),
             ("Falling", f"{t.get('mch_growth_falling_n', 0):,}", "down 10% or more")]
    right = h["rail"](s, items, top=top)
    # RPE: a diverging bar, gains right and falls left, in place of v5's dumbbell (Sheila's 1798
    # slide review, 2026-10-30: "shows magnitude and sign together")
    bars = [[labels.clip(r[0], 20), r[4], f"{r[5]:+.0f}%"]
            for r in risers[:5] + fallers[:5][::-1]]
    note = (f"{', '.join(merged)}: descriptors that changed in the window, combined"
            if merged else "change in card dollars, recent window against the prior one")
    path = h["chart"]("mch_growth", CT.diverging_bars, bars, note=note)
    if path:
        h["chart_left"](s, path, top, right)


def new_and_faded_merchants(h, t, base):
    """Material merchants first or last seen inside the trailing window;
    orange is new, navy has faded. The bar is card dollars."""
    new, faded = t.get("mch_new") or [], t.get("mch_faded") or []
    if not (new or faded):
        return "New and faded merchants (no mch_new / mch_faded)"
    if new:
        head = (f"{_title(new[0][0])} is the biggest merchant new to the card, "
                f"{money(new[0][1])} across {new[0][2]:,} accounts")
    else:
        head = (f"No material merchant is new to the card; "
                f"{_title(faded[0][0])} has faded")
    note = (t.get("mch_new_faded_note")
            or "material merchants first or last seen inside the trailing window")
    s, top = h["slide"]((head, f"{note}; {len(new)} new, {len(faded)} faded"),
                        "New and faded merchants")
    rows = [[labels.clip(_title(r[0]), 24), r[1], f"new · {r[2]:,} accounts", None, True]
            for r in new[:6]]
    rows += [[labels.clip(_title(r[0]), 24), r[1], f"faded · {r[2]:,} accounts", None, False]
             for r in faded[:6]]
    path = h["chart"]("mch_new_faded", charts.momentum_bars, rows,
                      headers=("MERCHANT · CARD DOLLARS", "STATUS", ""),
                      mark_label="new")
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


def the_mcc_codes(h, t, base, merchant_bars):
    """The raw codes under the category roll-up. Declines by name when the
    feed carries no MCC (1100: 0% populated) instead of drawing nothing."""
    rows = t.get("mch_mcc_top") or []
    cov = t.get("mch_mcc_coverage_pct")
    if not rows:
        if cov is not None:
            return (f"The MCC codes behind the categories (MCC on {cov:.0f}% of "
                    f"card rows; the feed does not carry it)")
        return "The MCC codes behind the categories (no mch_mcc_top)"
    lead = rows[0]
    s, top = h["slide"]((
        f"MCC {lead[0]} ({lead[1]}) takes {lead[6]:.0f}% of coded card dollars; "
        f"the top five codes take {t.get('mch_mcc_top5_share_pct', 0):.0f}%",
        f"{t.get('mch_mcc_distinct', 0):,} distinct codes on {cov or 0:.0f}% of "
        f"card rows, {base}; each code is shown with the category it rolls into"),
        "The MCC codes behind the categories")
    items = [("Coded", f"{cov or 0:.0f}%", "of card rows carry an MCC"),
             ("Codes", f"{t.get('mch_mcc_distinct', 0):,}", "distinct MCC codes"),
             ("Top five", f"{t.get('mch_mcc_top5_share_pct', 0):.0f}%",
              "of coded card dollars")]
    right = h["rail"](s, items, top=top)
    bars = [[f"{r[0]} {r[1]}", r[2], r[3], r[4], r[5], r[6]] for r in rows]
    path = h["chart"]("mch_mcc", merchant_bars, bars, top=12)
    if path:
        h["chart_left"](s, path, top, right)


def how_broadly_the_card_is_used(h, t, base):
    bands = t.get("mch_breadth_bands") or []
    if not bands:
        return "How broadly the card is used (no mch_breadth_bands)"
    s, top = h["slide"]((
        f"{t.get('mch_breadth_deep_pct', 0):.0f}% of card accounts shop across four "
        f"or more categories; the mean is {t.get('mch_breadth_mean', 0)}",
        f"named categories per card account, {base} (grouped by "
        f"{t.get('mch_category_method')}, MCC on {t.get('mch_mcc_coverage_pct', 0):.0f}% "
        f"of card rows); the rail shows that breadth pays"),
        "How broadly the card is used")
    items = [(f"{b[0]} categor{'y' if b[0] == '1' else 'ies'}", money(b[3]),
              f"per account · {b[1]:,} accounts") for b in bands if b[1]][:5]
    right = h["rail"](s, items, top=top)
    path = h["chart"]("mch_breadth", charts.tier_bars, [[b[0], b[1]] for b in bands])
    if path:
        h["chart_left"](s, path, top, right)


def _band_copy(rows, base, who, extra_head=""):
    """Band rows: [band, accounts, spend_per_acct, txns_per_acct_mo,
    avg_ticket, top_category]. The headline names the band that spends most."""
    lead = max(rows, key=lambda r: r[2])
    return (f"{who} {lead[0]} spend the most on the card, {money(lead[2])} per account"
            + extra_head,
            f"card dollars per account, {base}")


def _band_rail_and_chart(h, s, top, key, rows, extra_items=()):
    lead = max(rows, key=lambda r: r[2])
    busiest = max(rows, key=lambda r: r[3])
    items = [("Busiest", busiest[0], f"{busiest[3]} swipes per account a month"),
             ("Top category", labels.clip(lead[5], 18),
              f"for {lead[0]} · ${lead[4]:,.0f} average ticket")]
    if not extra_items:
        items.insert(0, ("Accounts", f"{sum(r[1] for r in rows):,}", "card accounts in a band"))
    right = h["rail"](s, items + list(extra_items), top=top)
    path = h["chart"](key, charts.tier_bars, [[r[0], r[2]] for r in rows],
                      share=False, fmt="${:,.0f}")
    if path:
        h["chart_left"](s, path, top, right)


def card_spend_by_member_age(h, t, base):
    rows = t.get("mch_by_age") or []
    if not rows:
        return "Card spend by member age (no mch_by_age)"
    s, top = h["slide"](_band_copy(rows, base, "Members aged"),
                        "Card spend by member age")
    _band_rail_and_chart(h, s, top, "mch_by_age", rows)


def card_use_by_account_tenure(h, t, base):
    rows = t.get("mch_by_tenure") or []
    if not rows:
        return "Card use by account tenure (no mch_by_tenure)"
    # RPE: 102 words on 1798; the first-swipe figures stay on the rail and leave the headline,
    # and the rail drops to four tiles (Sheila's 1798 slide review, 2026-10-30: too dense)
    extra = []
    fs = t.get("mch_first_swipe_bands") or []
    med = t.get("mch_first_swipe_median_days")
    if fs and med is not None:
        extra = [("First swipe", f"{med} days",
                  f"median, {t.get('mch_first_swipe_new_accounts', 0):,} new accounts"),
                 ("Within 30 days", f"{t.get('mch_first_swipe_within_30_pct', 0):.0f}%",
                  "of new accounts swipe")]
    s, top = h["slide"](_band_copy(rows, base, "Accounts"),
                        "Card use by account tenure")
    _band_rail_and_chart(h, s, top, "mch_by_tenure", rows, extra)
