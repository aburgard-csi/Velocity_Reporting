# Ported from ARS v5 02-Scripts/ars/deck/build.py at a491b5c (James Gilmore); logic unchanged.
"""
economics_inline.py — the five economics slides v5 draws inline in `ars/deck/build.py`: Program P&L
by offer, The 2:1 guarantee, Where the month's revenue came from, What each offer has earned, and
What an account earns as it climbs.

Each is lifted out of the build function as a builder with the house signature `(h, m)`, returning
None when drawn or the reason when declined (v5's `skip(...)` reason), so the Economics chapter calls
it like any ported builder. The bodies are v5's line for line; only the closures they called
(`slide`, `chart`, `_kpi`, `_table`, `_text`, `_fit_picture`, `_row_budget`, `_kicker`) are reached
through the helper bundle `h`, and v5's `_tile` (the guarantee's stat tiles) is carried here.
"""
from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.util import Inches

from . import charts, headlines
from .helpers import HEAD_FONT
from .labels import money as _money

GREEN_D = RGBColor(0x1E, 0x6E, 0x5E)   # semantic good (tiles, v5 issue #41)
RED_D = RGBColor(0xC0, 0x39, 0x2B)     # semantic weak


def _tile(h, slide, left, top, width, value, label, note=None, rule=None):
    """Dashboard stat tile (v5 `_tile`, issue #41): a coloured top rule, the number, its base
    label, a note. No box -- the rule carries the state."""
    from pptx.enum.shapes import MSO_SHAPE
    rule = rule or h["NAVY"]
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left),
                                 Inches(top), Inches(width), Inches(0.035))
    bar.fill.solid(); bar.fill.fore_color.rgb = rule
    bar.line.fill.background(); bar.shadow.inherit = False
    # RPE: a value wider than the tile steps its size down rather than wrap into the label below
    # (v5 drew 26pt always; "Drawing Down" overran a 2.6in tile, validate_deck FAIL, 1776)
    from textfit import text_width_in
    size = 26
    while size > 16 and text_width_in(str(value), size, HEAD_FONT, True) > width - 0.2:
        size -= 1
    h["text"](slide, left, top + 0.10, width, 0.55, value, size=size, bold=True,
              font=HEAD_FONT, color=rule if rule in (RED_D, GREEN_D) else h["NAVY"])
    h["text"](slide, left, top + 0.68, width, 0.28, label, size=12, bold=True)
    if note:
        h["text"](slide, left, top + 0.96, width, 0.28, note, size=10, color=h["GREY"])


def program_pnl(h, m) -> str | None:
    """Program P&L by wave: the ARS Workbook, finally on a slide (v5 build.py)."""
    if not (m.get("wb_profit_ltd") is not None or m.get("wb_waves")):
        return "wb_waves (run with an ARS Workbook present)"
    MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY = (h["MARGIN_L"], h["CONTENT_W"], h["NAVY"],
                                               h["ORANGE"], h["GREY"])
    s, top = h["slide"](headlines.pnl(m), "Program P&L by offer")
    kw = (CONTENT_W - 0.6) / 4
    if (m.get("gt_deferred_balance") or 0) > 1 \
            and m.get("gt_state") != "clear":
        # guarantee math (issue #42): what the client actually pays,
        # only while a balance is LIVE -- a cleared guarantee reverts
        # to the workbook's billed economics
        tiles = [("Earned over fees paid",
                  _money((m.get("gt_revenue_ltd") or 0)
                         - (m.get("gt_paid_ltd") or 0)),
                  "guarantee math, to date"),
                 ("Program revenue", _money(m.get("gt_revenue_ltd")),
                  "deferral tracker, to date"),
                 ("Fees paid", _money(m.get("gt_paid_ltd")),
                  f"of {_money(m.get('gt_charges_ltd'))} billed"),
                 ("Deferred", _money(m.get("gt_deferred_balance")),
                  "forgiven at contract end")]
    else:
        tiles = [("Program profit", _money(m.get("wb_profit_ltd")),
                  "life to date"),
                 ("Program revenue", _money(m.get("wb_revenue_ltd")),
                  "life to date"),
                 ("Program fees", _money(abs(m.get("wb_costs_ltd") or 0)),
                  "life to date"),
                 ("This month", _money(m.get("wb_profit_month")),
                  f"of {_money(m.get('wb_revenue_month'))} revenue")]
    for i, (label, value, note) in enumerate(tiles):
        h["kpi"](s, MARGIN_L + i * (kw + 0.2), top + 0.05, kw, label, value,
                 note, accent=ORANGE if i == 0 else NAVY)
    waves = m.get("wb_waves") or []
    if waves:
        t_top = top + 1.95
        rows = [["Offer", "Mailed", "Response", "Rev to date"]]
        shown = waves[-h["row_budget"](t_top, 10):]
        # rows carry 5 fields since goal_met_responders was added;
        # *_ tolerates both that and any older 4-field metrics.json
        for tag, mailed, resp, cum, *_ in shown:
            rows.append([str(tag),
                         f"{mailed:,}" if mailed is not None else "-",
                         f"{resp}%" if resp is not None else "-",
                         _money(cum)])
        h["table"](s, rows, MARGIN_L, t_top, 8.6,
                   col_widths=[2.0, 2.2, 2.1, 2.3], size=10.5)
    # RPE: "latest n of N offers" joins the footer rather than sitting under the table, where a
    # full table put it on the footer line (validate_deck FAIL, 1776: 6 of 9 offers)
    shown_note = (f"Latest {len(shown)} of {len(waves)} offers shown. "
                  if waves and len(waves) > len(shown) else "")
    h["text"](s, MARGIN_L + 0.02, 6.42, CONTENT_W, 0.3,
              f"{shown_note}Booked frame: {m.get('wb_source', 'ARS Workbook')}, the "
              f"program's own ledger, gross and all revenue types. Rev "
              f"to date is the wave's own To Date column, life of the "
              f"offer. Not comparable to DiD estimates: see Revenue "
              f"frames.", size=9.5, color=GREY)
    h["kicker"](s)
    return None


def guarantee(h, m) -> str | None:
    """The 2:1 guarantee, right after the executive financial slide (James, 2026-08-22); renders
    only when a tracker exists (v5 build.py)."""
    gtm = m.get("gt_months") or []
    if not gtm:
        return "gt_months (run with a deferral tracker present)"
    MARGIN_L, CONTENT_W, NAVY, GREY = h["MARGIN_L"], h["CONTENT_W"], h["NAVY"], h["GREY"]
    s, top = h["slide"](headlines.guarantee(m), "The 2:1 guarantee")
    kw = (CONTENT_W - 0.9) / 4
    state = str(m.get("gt_state", "")).replace("-", " ")
    tiles = [(_money(m.get("gt_deferred_balance")), "Deferred balance",
              "forgiven at contract end", RED_D
              if m.get("gt_state") == "in-guarantee" else NAVY),
             (_money(m.get("gt_paid_ltd")), "Fees paid",
              f"of {_money(m.get('gt_charges_ltd'))} billed", NAVY),
             (f"{m.get('gt_ratio_latest', 0):.2f}x",
              "Revenue vs billing, latest",
              "guarantee releases at 2.00x", NAVY),
             (state.title() or "-", "Status",
              f"through {m.get('gt_latest_month', '')}",
              GREEN_D if m.get("gt_state") == "clear" else NAVY)]
    for i, (value, label, note, rule) in enumerate(tiles):
        _tile(h, s, MARGIN_L + i * (kw + 0.3), top + 0.05, kw, value, label,
              note, rule=rule)
    rows = [["Month", "Revenue", "Charges", "Paid", "Deferred",
             "Running"]]
    for mth, rev, charges, paid, deferred, running in gtm[-9:]:
        rows.append([mth, _money(rev), _money(charges), _money(paid),
                     _money(deferred), _money(running)])
    h["table"](s, rows, MARGIN_L, top + 1.55, CONTENT_W,
               col_widths=[2.1, 2.0, 2.0, 2.0, 2.0, 1.9], size=10)
    h["text"](s, MARGIN_L + 0.02, 6.42, CONTENT_W, 0.3,
              f"Source: {m.get('gt_source', 'deferral tracker')}. While "
              f"revenue runs under 2x the charges the client pays half of "
              f"revenue; the rest defers, draws down above the mark, and "
              f"is forgiven at contract end.", size=9.5, color=GREY)
    h["kicker"](s)
    return None


def wave_mix(h, m) -> str | None:
    """The rollup matrix as the month's make-up (v5 build.py, issue #85). Booked frame."""
    wave_rows = m.get("wb_wave_revenue") or []
    if len(wave_rows) < 2:
        return "wb_wave_revenue (run with an ARS Workbook present)"
    wb_src = m.get("wb_source", "ARS Workbook")
    MARGIN_L, CONTENT_W = h["MARGIN_L"], h["CONTENT_W"]
    s, top = h["slide"](headlines.wave_mix(m),
                        "Where the month's revenue came from")
    path = h["chart"]("wave_composition", charts.wave_composition, wave_rows)
    if path:
        h["fit_picture"](s, path, MARGIN_L, top + 0.1,
                         max_w=CONTENT_W, max_h=6.3 - (top + 0.1))
    h["text"](s, MARGIN_L + 0.02, 6.42, CONTENT_W, 0.3,
              f"Booked frame: {wb_src}, All Months Rollup. Each column is "
              f"that month's revenue split by every offer that earned in "
              f"it, oldest pale at the base to newest dark on top. Not "
              f"comparable to DiD estimates: see Revenue frames.",
              size=9.5, color=h["GREY"])
    h["kicker"](s)
    return None


def wave_totals(h, m) -> str | None:
    """The rollup matrix as each offer's life earnings (v5 build.py, issue #85). Booked frame."""
    wave_rows = m.get("wb_wave_revenue") or []
    if len(wave_rows) < 2:
        return "wb_wave_revenue (run with an ARS Workbook present)"
    wb_src = m.get("wb_source", "ARS Workbook")
    MARGIN_L, CONTENT_W = h["MARGIN_L"], h["CONTENT_W"]
    s, top = h["slide"](headlines.wave_totals(m),
                        "What each offer has earned")
    path = h["chart"]("wave_totals", charts.wave_totals, wave_rows)
    if path:
        h["fit_picture"](s, path, MARGIN_L, top + 0.1,
                         max_w=CONTENT_W, max_h=6.3 - (top + 0.1))
    h["text"](s, MARGIN_L + 0.02, 6.42, CONTENT_W, 0.3,
              f"Booked frame: {wb_src}, All Months Rollup — each column "
              f"is one offer, banded by the month that earned it, and the "
              f"total ties to Rev to date on Program P&L by offer. Offers "
              f"are not the same age: the months each has had ride under "
              f"its label. Not comparable to DiD estimates: see Revenue "
              f"frames.", size=9.5, color=h["GREY"])
    h["kicker"](s)
    return None


def lift_matrix(h, m) -> str | None:
    """The workbook rate card (Lift Matrix MM), quoted for the window it is good for; the unit
    comes from the sheet's caption, never from us (v5 build.py)."""
    lift_pair = headlines.lift_matrix(m)
    if not lift_pair:
        if m.get("wb_found"):
            return (f"the booked frame is empty: workbook "
                    f"{m['wb_found']} gave up no Lift Matrix MM")
        return "wb_lift_rows"
    MARGIN_L, CONTENT_W = h["MARGIN_L"], h["CONTENT_W"]
    s, top = h["slide"](lift_pair, "What an account earns as it climbs")
    wb_src = m.get("wb_source", "ARS Workbook")
    path = h["chart"]("lift_matrix", charts.lift_matrix_heat,
                      {"cols": m["wb_lift_cols"], "rows": m["wb_lift_rows"],
                       "money": "$" in str(m.get("wb_lift_caption") or "$")})
    if path:
        h["fit_picture"](s, path, MARGIN_L, top + 0.1,
                         max_w=CONTENT_W, max_h=6.3 - (top + 0.1))
    caption = m.get("wb_lift_caption")
    unit = (f'the sheet states the figure as "{caption}"' if caption
            else "the sheet states no unit, so the figures are shown "
                 "as the workbook carries them")
    window = (f", {m['wb_lift_window']}" if m.get("wb_lift_window")
              else "")
    stale = (f" The sheet's data month is "
             f"{m.get('wb_lift_data_month')}, past the window's end: "
             f"these rates are stale, not current."
             if m.get("wb_lift_stale") else "")
    h["text"](s, MARGIN_L + 0.02, 6.42, CONTENT_W, 0.3,
              f"Booked frame: {wb_src}, Lift Matrix MM{window}. Each row is "
              f"the band an account started in, each column the band it "
              f"reached; {unit}.{stale}", size=9.5, color=h["GREY"])
    h["kicker"](s)
    return None
