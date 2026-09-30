#!/usr/bin/env python3
"""
ti_slides.py — the nine-slide Transaction Intelligence chapter, opt-in (RPE_ANALYSIS_SLIDES=1).

Built from txn_metrics.json (build/ars_pipeline/engine/transaction_intelligence, run by
run_analysis.py on the client's Inputs/Txn Files/), the way the James views are built: from
scratch with shapes.py on the anchor slide's layout, placed by TITLE at the end of the debit
section (before "Reg E Review"), each with its own source note, every tile recorded in the
figure sidecar so one measure cannot carry two values. A client whose files carry no rows
for a view gets that view with a sentence saying so; nothing is zeroed and no slide is
dropped. The nine views are James's Transaction Intelligence chapter, by name.

    add_ti_slides(prs, txn, ctx) -> [slides]     ctx: as_of_long, txn_src, assets
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(_HERE, os.pardir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from combined_insight_slides import (_find, _new_slide, _place, _header, _caption,   # noqa: E402
                                     _picture, SH, NAVY, ORANGE, usd_compact)
import figures as _figs                                                              # noqa: E402
import ti_charts                                                                     # noqa: E402

ANCHOR_BEFORE = "Reg E Review"
ANCHOR_AFTER = "Debit Card Review"
PILL = "{as_of} Data"


def _rows(txn, key, li, vi, n=10):
    """(label, number) pairs from a list-of-rows metric; anything that is not a labelled
    numeric row is left out rather than drawn as a zero. `key` may be dotted
    ("comp_local.institutions") for a list inside a dict, and a dict of lists keyed by
    category (fin_top_providers) is flattened and ranked by the value column. 1441
    (2026-09-30): three of nine views drew empty because the key or the shape was wrong here,
    while the engine had the numbers."""
    v = txn
    for part in key.split("."):
        v = v.get(part) if isinstance(v, dict) else None
    if isinstance(v, dict):
        v = [r for rows in v.values() if isinstance(rows, list) for r in rows]
    out = []
    for r in (v or []):
        if (isinstance(r, (list, tuple)) and len(r) > max(li, vi)
                and isinstance(r[vi], (int, float)) and not isinstance(r[vi], bool)):
            out.append((r[li], r[vi]))
    out.sort(key=lambda t: -t[1])
    return out[:n]


def _money(v):
    return usd_compact(v, 1) if v is not None else "n/a"


def _pct(v):
    return f"{v:.1f}%" if isinstance(v, (int, float)) else "n/a"


def _n(v):
    return f"{v:,}" if isinstance(v, (int, float)) else "n/a"


# title, chart rows (key, label idx, value idx, kind), tiles [(key, label, fmt)], caption, detail
VIEWS = [
    ("How the money moves", ("txn_by_channel", 0, 3, "money"),
     [("txn_accounts", "Transacting accounts", _n), ("txn_spend_total", "Dollars in the window", _money),
      ("txn_per_account", "Transactions per account", _n)],
     "Dollars by channel over the window: card (PIN and signature), ACH and check. Transactions per account are a monthly average.",
     "Every row of the monthly transaction files in the window, by transaction type."),
    ("Where the money goes", ("fin_by_category", 0, 2, "money"),
     [("fin_leaking_pct", "Accounts paying elsewhere", _pct),
      ("fin_leakage_dollars", "Dollars to outside products", _money),
      ("fin_addressable_dollars", "Of which addressable", _money)],
     "Money leaving for someone else's financial products, by category. P2P and wallets are adjacent flows, not leakage.",
     "Name-based detection against the financial services dictionary, per client additions included."),
    ("Their financial life", ("fin_top_providers", 0, 2, "money"),
     [("fin_accounts_total", "Transacting personal accounts", _n),
      ("fin_leaking_accounts", "With an outside product", _n),
      ("fin_addressable_pct", "Addressable share", _pct)],
     "The named providers our account holders pay, ranked by dollars.",
     "Providers matched by name in the payee field; unmatched large payees are listed in fin_unmatched_top."),
    ("Who they pay", ("rel_by_channel", 0, 1, "count"),
     [("rel_primary_like_pct", "Primary-like activity", _pct), ("rel_single_channel_pct", "Single-channel accounts", _pct),
      ("rel_breadth_mean", "Channels per account", _n)],
     "Channels used per account, and how many accounts look primary: two or more channels and ten or more transactions a month.",
     "rel_* section: channel breadth, recurring billers, depth by breadth."),
    ("What leakers hold with us", ("ovl_destinations", 0, 2, "money"),
     [("ovl_flight_n", "Accounts with falling deposits", _n), ("ovl_flight_deposits", "Their balances", _money),
      ("ovl_named_destination_deposits", "With a named destination", _money)],
     "Where the declining balances actually go: the flight-risk accounts joined to their competitor and leakage rows.",
     "Overlay of balance.flight_mask (the ODD) on the competitor rows (the transaction file); nothing is reclassified."),
    ("Who competes for our account holders", ("comp_institutions", 0, 2, "money"),
     [("comp_with_competitor_pct", "Accounts banking elsewhere", _pct), ("comp_competitor_dollars", "Dollars to competitors", _money),
      ("comp_accounts_total", "Transacting personal accounts", _n)],
     "Named institutions holding a relationship with our account holders, ranked by dollars.",
     "Competitors from the shared dictionary plus the client's local and regional lists."),
    ("Which competitors to work first", ("comp_local.institutions", 0, 2, "money"),
     [("comp_multi_banked_pct", "Multi-banked accounts", _pct), ("comp_institutions_n", "Competitors detected", _n),
      ("hot_both_above_median", "Branches above median", _n)],
     "Local competitors first: the ones a branch can answer. Momentum says who is growing.",
     "comp_local and the attrition-by-competition hotspots per branch."),
    ("Where the outflow goes", ("txn_top_ach_chk", 0, 2, "money"),
     [("leak_depth_months", "Months of history", _n), ("leak_divergence_month", "Months before close it diverges", _n),
      ("txn_top15_share_pct", "Top-15 payee share", _pct)],
     "The largest ACH and check payees, ranked by dollars.",
     "ACH and check rows only; card spend is on the next slide."),
    ("How account holders spend", ("mch_top", 0, 3, "money"),
     [("mch_card_accounts", "Card-active accounts", _n), ("mch_card_spend", "Card spend", _money),
      ("mch_merchants_for_80pct", "Merchants for 80% of spend", _n)],
     "The card rail: top merchants by dollars, with the category method the file supports.",
     "Categories from MCC when the file carries it, keyword buckets otherwise (mch_category_method)."),
]


def _tile(s, i, value, label, slide_title):
    fill = ORANGE if i == 0 else NAVY
    SH.shadow(SH.tile(s, 9.5, 1.75 + i * 1.4, 3.3, 1.25, value, label, fill=fill))
    _figs.log.record(f"TI: {label}", value, slide_title)


def add_ti_slides(prs, txn, ctx):
    """Build and place the nine views, in order, before ANCHOR_BEFORE. Returns the slides."""
    made = []
    src = ctx.get("txn_src") or "the client's transaction files"
    files = ", ".join(txn.get("txn_files_loaded") or [])[:300]
    for k, (title, (key, li, vi, kind), tiles, caption, detail) in enumerate(VIEWS, 1):
        s = _new_slide(prs, _find(prs, ANCHOR_AFTER))
        rows = _rows(txn, key, li, vi)
        # The base is the personal count when the ODD join gave one, else every transacting
        # account, and the label says which (1441: the line said "personal" over the all-accounts figure).
        personal, every = txn.get("fin_accounts_total"), txn.get("txn_accounts")
        base, base_label = ((personal, "transacting personal accounts") if isinstance(personal, int) and personal
                            else (every, "transacting accounts"))
        _header(s, title, PILL.format(as_of=ctx["as_of_long"]), [
            f"Selection: {base_label} ({base:,}); {txn.get('txn_window_months', 12)}-month window "
            f"ending {txn.get('txn_anchor', '')}." if isinstance(base, int) else "Selection: transacting accounts.",
            "Selection: transacting accounts."])
        if rows:
            png = os.path.join(ctx["assets"], f"ti_{k:02d}.png")
            ti_charts.ranked_bars(png, rows, kind=kind)
            _picture(s, png, 0.5, 1.72, 8.7, 4.1)
            _caption(s, caption)
        else:
            _caption(s, f"The transaction files in this window carry no rows for this view ({key}); "
                        f"it is not shown for this period.", width=8.7, top=2.4, height=1.2)
        for i, (tk, label, fmt) in enumerate(tiles):
            _tile(s, i, fmt(txn.get(tk)), label, title)
        s.notes_slide.notes_text_frame.text = (
            f"Source: {src} — {files or 'no files'} ({txn.get('txn_rows', 0):,} rows, "
            f"{txn.get('txn_months_covered', 0)} month(s)); ODD join {txn.get('txn_odd_match_pct', 'n/a')}% "
            f"on {txn.get('txn_odd_join_key', 'n/a')}. {detail}")
        _place(prs, s, before=ANCHOR_BEFORE)
        made.append(s)
    return made
