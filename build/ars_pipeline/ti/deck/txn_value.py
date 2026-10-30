# Ported from ARS v5 02-Scripts/ars/deck/txn_value.py at a491b5c (James Gilmore); logic unchanged.
"""The routing mix and the relationship shape (#258 group 4).

Four interchange slides read the ic_* block: the PIN / signature mix and
its trend, who routes PIN, the PIN-heavy accounts, and the merchants where
PIN gets pressed. None of them prices the mix -- the ARS value section owns
priced revenue -- so the headlines carry shares and dollars of spend, never
interchange dollars. Two relationship slides read the rel_* block: which
channels are used together and what a second channel is worth. "Product"
in the legacy scripts was the distinct product codes on a rewards extract,
which a one-row-per-account ODD cannot supply; here the unit is the channel
(card, ACH, check, P2P), and every subhead says so.
"""
from __future__ import annotations

from . import charts, charts_txn as CT, labels
from .txn_common import money

SIG_GOAL = 60.0
CHANNEL_NAMES = {"card": "Card", "ACH": "ACH", "CHK": "Check", "P2P": "P2P"}
NOT_PRICED = "shares of card dollars; the ARS value section prices the mix"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _channel_name(c: str) -> str:
    return CHANNEL_NAMES.get(c, c)


def _merchant(name) -> str:
    """RPE: a merchant as the slide prints it ("Walmart", never "Wal Mart"; Sheila's 1798 slide
    review, 2026-10-30)."""
    return labels.display_name(name)


def _month_label(period: str) -> str:
    """'2026-02' -> "Feb'26", RPE's house format (periods.mon_yy); a '26/02' tick reads as a day.

    RPE: v5's month keys ("Jan24") are taken too. Only the ISO form was, so 1798's "Jan24" went to
    the axis as-is, the month-axis guard refused the chart and "PIN or signature" shipped blank
    (Sheila's 1798 slide review, 2026-10-30, slide 34)."""
    import re
    import periods
    period = str(period)
    if re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", period):
        try:
            return periods.mon_yy(f"{MONTHS[int(period[5:7]) - 1]} {period[:4]}")
        except (ValueError, IndexError):
            return period
    return periods.mon_yy(period)


def pin_or_signature(h, t, base):
    """The mix month by month, as a share of card dollars on signature."""
    monthly = t.get("ic_monthly") or []
    if not t.get("ic_routing_available"):
        rails = t.get("ic_rails") or []
        return ("PIN or signature (file carries " + ("/".join(rails) if rails else "no card rows")
                + " only; the mix is an artefact of the extract)")
    if len(monthly) < 3:
        return "PIN or signature (fewer than three months of card rows)"
    share = t.get("ic_sig_share_pct") or 0
    direction = t.get("ic_sig_direction") or "stable"
    shift = t.get("ic_sig_shift_pp")
    verb = {"improving": "rising", "declining": "falling"}.get(direction, "flat")
    head = f"{share:.0f}% of card dollars route as signature, and the share is {verb}"
    if shift is not None and direction != "stable":
        head += f" {abs(shift):.1f} points"
    s, top = h["slide"]((head, f"{base}; {NOT_PRICED}; signature earns more per dollar "
                         f"than PIN, {SIG_GOAL:.0f}% is the working goal"), "PIN or signature")
    items = [("Signature", f"{share:.0f}%", "of card dollars"),
             ("Of swipes", f"{t.get('ic_sig_share_of_swipes_pct', 0):.0f}%", "route as signature")]
    # RPE: who routes PIN, by holder age, as one tile; "Who routes PIN" was its own slide
    # (Sheila's 1798 slide review, 2026-10-30, group D: four routing slides to two)
    ages = t.get("ic_by_age") or []
    if len(ages) >= 2:
        lo, hi = min(ages, key=lambda r: r[2]), max(ages, key=lambda r: r[2])
        items.append(("By holder age", f"{lo[2]:.0f}-{hi[2]:.0f}%",
                      f"signature, {lo[0]} lowest, {hi[0]} highest"))
    items += [("Average ticket", money(t.get("ic_pin_ticket") or 0),
               f"PIN, against {money(t.get('ic_sig_ticket') or 0)} signature"),
              ("Card dollars", money(t.get("ic_card_spend") or 0),
               f"{t.get('ic_card_accounts', 0):,} accounts")]
    right = h["rail"](s, items, top=top)
    # the share as a line on a tight axis, the month's card accounts as the
    # grey base behind it: on a 0-100 axis a three-point rise drew flat
    rows = [[_month_label(r[0]), r[4] if len(r) > 4 else 0, r[3]] for r in monthly]
    path = h["chart"]("ic_monthly", charts.line_with_base, rows,
                      ylabel="signature share of card $ (%)")
    if path:
        h["chart_left"](s, path, top, right)


def who_routes_pin(h, t, base):
    """Signature share by holder age, the PIN-defaulted products on the rail."""
    if not t.get("ic_routing_available"):
        return "Who routes PIN (no PIN/SIG mix in the file)"
    ages = t.get("ic_by_age") or []
    products = t.get("ic_by_product") or []
    if len(ages) < 2 and len(products) < 2:
        return "Who routes PIN (no age or product groups of 10+ card accounts)"
    rows = ages if len(ages) >= 2 else products
    axis = "holder age" if len(ages) >= 2 else "product"
    lo, hi = min(rows, key=lambda r: r[2]), max(rows, key=lambda r: r[2])
    head = (f"Signature routing runs from {lo[2]:.0f}% ({lo[0]}) to {hi[2]:.0f}% "
            f"({hi[0]}) by {axis}")
    s, top = h["slide"]((head, f"{base}; {NOT_PRICED}; groups under 10 accounts dropped"),
                        "Who routes PIN")
    items = []
    for r in (t.get("ic_pin_default_products") or [])[:3]:
        items.append((labels.clip(str(r[0]), 22), f"{r[2]:.0f}%",
                      f"signature; {r[1]:,} accounts, {money(r[3])} -- looks PIN-defaulted"))
    if not items:
        for r in products[:3]:
            items.append((labels.clip(str(r[0]), 22), f"{r[2]:.0f}%",
                          f"signature; {r[1]:,} accounts, {money(r[3])}"))
    for r in [x for x in (t.get("ic_by_lens") or []) if x[0] in ("responders", "mailed_nonresp")]:
        items.append((str(r[1]), f"{r[3]:.0f}%", f"signature; {r[2]:,} accounts"))
    right = h["rail"](s, items[:5], top=top) if items else h["RIGHT_EDGE"]
    path = h["chart"]("ic_by_group", charts.tier_bars,
                      [[labels.clip(str(r[0]), 14), r[1], r[2]] for r in rows],
                      value_idx=2, share=False, fmt="{:.0f}%", label="signature share")
    if path:
        h["chart_left"](s, path, top, right)


def pin_heavy_accounts(h, t, base):
    """Accounts banded by the share of their own card dollars on signature;
    the PIN-heavy block (80%+ on PIN) called out on the rail."""
    if not t.get("ic_routing_available"):
        return "PIN-heavy accounts (no PIN/SIG mix in the file)"
    mix = t.get("ic_account_mix") or []
    if not any(r[1] for r in mix):
        return "PIN-heavy accounts (no accounts with card dollars)"
    n, pct = t.get("ic_pin_heavy_n", 0), t.get("ic_pin_heavy_pct", 0) or 0
    # RPE: the merchants where PIN gets pressed are this slide's chart when the file has them;
    # "Where PIN gets pressed" was its own slide (Sheila's 1798 slide review, 2026-10-30, group D)
    merch = sorted(t.get("ic_by_merchant") or [], key=lambda r: -(r[2] + r[3]))[:6]
    pin_led = max(merch, key=lambda r: r[2]) if len(merch) >= 3 else None
    head = f"{n:,} accounts ({pct:.0f}%) put 80% or more of their card dollars through PIN"
    if pin_led:
        head += f"; {_merchant(pin_led[0])} carries the most PIN dollars"
    sub = (f"{base}; PIN and signature dollars at the top merchants, as the file records them; "
           f"{NOT_PRICED}" if pin_led else
           f"{base}; each account banded by its own signature share; {NOT_PRICED}")
    s, top = h["slide"]((head, sub), "PIN-heavy accounts")
    items = [("PIN-heavy", f"{n:,}", f"{pct:.0f}% of card accounts"),
             ("Their card dollars", money(t.get("ic_pin_heavy_spend") or 0),
              f"{t.get('ic_pin_heavy_spend_pct', 0):.0f}% of all card dollars"),
             ("Per account", money(t.get("ic_pin_heavy_spend_per_acct_mo") or 0), "a month")]
    if pin_led:
        items.append(("Most PIN dollars", labels.clip(_merchant(pin_led[0]), 18),
                      f"{money(pin_led[2])} at {100 - pin_led[4]:.0f}% PIN"))
    else:
        items.append(("All signature", f"{(mix[-1][1] if mix else 0):,}",
                      "accounts at 80-100% signature"))
    right = h["rail"](s, items, top=top)
    if pin_led:
        path = h["chart"]("ic_pin_merchants", charts.grouped_bars,
                          [labels.clip(_merchant(r[0]), 14) for r in merch],
                          [r[2] for r in merch], [r[3] for r in merch], "PIN", "Signature",
                          size=(charts.FIG_W_RAIL, charts.FIG_H_RAIL), fmt=labels.money)
    else:
        path = h["chart"]("ic_account_mix", charts.tier_bars, [[r[0], r[1]] for r in mix],
                          label="accounts")
    if path:
        h["chart_left"](s, path, top, right)


def where_pin_gets_pressed(h, t, base):
    """The largest card merchants with their PIN and signature dollars side
    by side: routing observed on the rows, not imputed from account means."""
    if not t.get("ic_routing_available"):
        return "Where PIN gets pressed (no PIN/SIG mix in the file)"
    rows = t.get("ic_by_merchant") or []
    if len(rows) < 3:
        return "Where PIN gets pressed (fewer than three card merchants)"
    pin_led = sorted(rows, key=lambda r: -r[2])[0]
    head = (f"{labels.clip(_merchant(pin_led[0]), 24)} carries the most PIN dollars, "
            f"{money(pin_led[2])} at {100 - pin_led[4]:.0f}% PIN")
    s, top = h["slide"]((head, f"{base}; the top {len(rows)} merchants by card dollars; "
                         f"PIN and signature dollars as the file records them"),
                        "Where PIN gets pressed")
    tick = [labels.clip(_merchant(r[0]), 16) for r in rows]
    path = h["chart"]("ic_by_merchant", charts.grouped_bars, tick,
                      [r[2] for r in rows], [r[3] for r in rows], "PIN", "Signature",
                      size=(charts.FIG_W_FULL, charts.FIG_H_FULL), fmt=labels.money)
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


def channels_used_together(h, t, base):
    """Of the accounts on one channel, the share also on each other; the
    single-channel accounts and their likely next channel on the rail."""
    if t.get("rel_single_rail"):
        return "Channels used together (feed carries one rail; breadth is an artefact of the extract)"
    grid = t.get("rel_channel_pairs")
    if not grid or len(grid.get("rows") or []) < 2:
        return "Channels used together (no rel_channel_pairs)"
    nxt = t.get("rel_next_channel") or []
    single = sorted(nxt, key=lambda r: -r[1])
    lead = single[0] if single and single[0][1] else None
    if lead:
        head = (f"{lead[1]:,} accounts use {_channel_name(lead[0]).lower()} alone; "
                f"their multi-channel peers most often add {_channel_name(lead[2])} "
                f"({lead[3]:.0f}%)")
    else:
        head = "Every transacting account uses more than one channel"
    s, top = h["slide"]((head, f"{base}; a cell is the share of accounts on the row channel "
                         f"also on the column channel; channels stand in for products, "
                         f"which the ODD cannot count"), "Channels used together")
    items = [(f"{_channel_name(r[0])} only", f"{r[1]:,}",
              f"peers add {_channel_name(r[2])} {r[3]:.0f}% of the time")
             for r in single if r[1]]
    right = h["rail"](s, items[:4], top=top) if items else h["RIGHT_EDGE"]
    shown = {"rows": [_channel_name(c) for c in grid["rows"]],
             "cols": [_channel_name(c) for c in grid["cols"]], "cells": grid["cells"]}
    path = h["chart"]("rel_channel_pairs", CT.heat_matrix, shown,
                      note="share of the row channel's accounts also on the column channel")
    if path:
        h["chart_left"](s, path, top, right)


def what_a_second_channel_is_worth(h, t, base):
    """Dollars a month by how many channels an account uses: the staircase
    legacy relationship/06 drew on products."""
    if t.get("rel_single_rail"):
        return "What a second channel is worth (feed carries one rail)"
    depth = t.get("rel_depth_by_breadth") or []
    if len(depth) < 2:
        return "What a second channel is worth (fewer than two breadth groups)"
    one, top_ = depth[0], depth[-1]
    mult = (top_[3] / one[3]) if one[3] else None
    head = (f"An account on {top_[0]} channels moves {money(top_[3])} a month against "
            f"{money(one[3])} on {one[0]}")
    if mult and mult >= 1.5:
        head += f", {mult:.1f}x"
    s, top = h["slide"]((head, f"{base}; mean dollars and transactions a month by channels "
                         f"used; channels are card, ACH, check and P2P"),
                        "What a second channel is worth")
    items = [(f"{r[0]} channel" + ("s" if r[0] > 1 else ""), f"{r[2]} txn/mo",
              f"{r[1]:,} accounts, {money(r[3])} a month") for r in depth]
    right = h["rail"](s, items[:5], top=top)
    rows = [[f"{r[0]} ch." if r[0] > 1 else "1 ch.", r[1], r[3]] for r in depth]
    path = h["chart"]("rel_depth", charts.tier_bars, rows, value_idx=2, share=False,
                      fmt="${:,.0f}", label="dollars a month")
    if path:
        h["chart_left"](s, path, top, right)
