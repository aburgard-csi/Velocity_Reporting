# Ported from ARS v5 02-Scripts/ars/deck/build.py at a491b5c (James Gilmore); logic unchanged.
"""
campaign_inline.py — the campaign slides v5 draws inline in `ars/deck/build.py`: reach, response by
offer, the per-offer summary, the ladder, segment trajectories, the penalty box, the counterfactual,
which offer earns its postage, over the ask, lift by segment, depth, activation, what a response
does to spend, sustained activity, first-time against repeat, partial responders, who responds,
tier movement, swipe-tier migration, the most recent mailer / trajectory / offer, and the
Offer detail appendix.

Each v5 block is lifted out of the build function as a builder with the house signature `(h, m)`,
its body v5's line for line (each docstring names the v5 lines). The closures those blocks called
are bound at the top of each builder by `_v5`: `slide`, `chart`, `_rail` and the rest through the
helper bundle `h`; `skip(title, *keys, reason=None)` draws the cut's stated slide, as v5 recorded
a skip (the frame hides it for that client); `register` (v5's provenance ledger) does nothing here; `n` is v5's lookup. One change,
marked where it is made: v5 drew six slides as `new()` + `register()` + `_title()`; the cut draws
a slide's title first and numbers it after, so the same headline and subtitle go through `slide()`.
"""
from __future__ import annotations

from pptx.util import Inches  # noqa: F401  (v5's blocks size shapes in inches)

import periods as _periods

from . import charts, headlines, labels, migration_slides  # noqa: F401
from .economics_inline import GREEN_D, RED_D, FOOT_PT, _tile as _tile_h, ic_pct  # noqa: F401
from .helpers import HEAD_FONT
from .labels import money as _money  # noqa: F401


def _month_axis(rows):
    """Rows whose first field is a month label, with that label in the house axis format (MMM'YY).

    RPE (Sheila's 1798 slide review, 2026-10-30): v5's "Jun24" labels failed the month-axis guard
    every RPE chart module installs, and the chart was refused and the slide shipped blank (slides
    105, 108 and 111, and the hero sparkline). `axis_months` leaves a label that is not a month as
    it is, and an already-formatted one unchanged, so a chart layer that formats them too is fine."""
    rows = [list(r) for r in rows]
    return [[lab, *r[1:]] for lab, r in zip(_periods.axis_months([str(r[0]) for r in rows]), rows)]


def _v5(h, m):
    """v5's build-function closures, bound to the cut's helper bundle (see the module docstring)."""
    def skip(title, *keys, reason=None):
        h["declined"](title, reason or ("missing " + ", ".join(keys)))

    def n(key, default=0):
        return m.get(key, default) or default

    def _kpi_flat(slide, left, top, width, label, value, note=None):
        """v5 `_kpi_flat`: a boxless KPI, label / value / note as plain text (issue #28)."""
        h["text"](slide, left, top, width, 0.28, label, size=11, bold=True,
                  color=h["GREY"], font=HEAD_FONT)
        h["text"](slide, left, top + 0.28, width, 0.5, value, size=20, bold=True,
                  font=HEAD_FONT)
        if note:
            h["text"](slide, left, top + 0.80, width, 0.28, note, size=FOOT_PT, color=h["GREY"])

    def _tile(slide, left, top, width, value, label, note=None, rule=None):
        _tile_h(h, slide, left, top, width, value, label, note, rule=rule)

    return (h["slide"], skip, h["chart"], n, lambda *_a, **_k: None, h["divider"], h["title"],
            h["rail"], h["chart_left"], h["picture"], h["fit_picture"], h["kpi"], _kpi_flat,
            h["table"], h["text"], _tile, h["kicker"], h["MARGIN_L"], h["CONTENT_W"], h["NAVY"],
            h["ORANGE"], h["GREY"])


def tier_matrix(h, m) -> str | None:
    """v5 build.py lines 2452-2455: Where the tiers moved (`deck/migration_slides.tier_matrix`)."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    _matrix_skip = migration_slides.tier_matrix(
        {"slide": slide, "table": _table, "rail": _rail, "MARGIN_L": MARGIN_L}, m)
    if _matrix_skip:
        skip(_matrix_skip, "mig_matrix")
    return None


def program_reach(h, m) -> str | None:
    """v5 build.py lines 1115-1157: Program reach."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    if m.get("reach_total") is not None and m.get("reach") is not None:
        # metric-first layout (James, issue #43 note on this slide): a
        # symmetric grid of the numbers with a brief line under each,
        # no chart competing with them
        s, top = slide(headlines.program_reach(m), "Program reach")
        # RPE (Sheila's 1798 slide review, 2026-10-30, combine group K): reach and the latest
        # offer's response were two slides (104, 127); one funnel, eligible > mailed > responded,
        # with the latest offer in the rail
        stages = [[label, n(key), 0, 0] for label, key in
                  (("Eligible", "n_eligible"), ("Ever mailed", "n_ever_mailed"),
                   ("Responded", "reach_total"))]
        stages = [st for st in stages if st[1]]
        if len(stages) >= 2:
            for i in range(1, len(stages)):
                stages[i][3] = round((1 - stages[i][1] / (stages[i - 1][1] or 1)) * 100, 1)
            base = str(m.get("reach_base") or "eligible").lower()
            items = []
            latest = str(m.get("latest_mailing") or "")
            row = next((c for c in reversed(m.get("campaign_rates") or [])
                        if str(c[0]) == latest), None)
            if row:
                items.append((f"Latest offer, {latest}", f"{row[2]:,}",
                              f"responded of {row[1]:,} mailed"))
            if m.get("latest_resprate") is not None:
                items.append(("Latest response", f"{n('latest_resprate')}%",
                              f"mean {n('resprate_mean')}%" if m.get("resprate_mean")
                              is not None else latest))
            items.append(("Reach", f"{n('reach')}%", f"of {base}"))
            if m.get("reach_of_mailed") is not None:
                items.append(("Of mailed", f"{n('reach_of_mailed')}%", "ever responded"))
            right = _rail(s, items, top=top)
            path = chart("reach_funnel", charts.funnel, stages)
            if path:
                _chart_left(s, path, top + 0.1, right, max_h=6.3 - (top + 0.1))
            if m.get("responder_spend_share_pct") is not None:
                _text(s, MARGIN_L + 0.02, 6.42, CONTENT_W, 0.3,
                      f"Responders carry {n('responder_spend_share_pct')}% of "
                      f"card spend from "
                      f"{n('responder_share_of_eligible_pct', n('reach')):.0f}% "
                      f"of accounts.", size=FOOT_PT, color=GREY)
            _kicker(s)
            return None
        tiles = [
            (f"{n('n_eligible'):,}", "Eligible accounts",
             "the base the program can reach", NAVY)
            if n("n_eligible") else None,
            (f"{n('n_ever_mailed'):,}", "Ever mailed",
             f"{100 * n('n_ever_mailed') / n('n_eligible'):.0f}% of eligible"
             if n("n_eligible") else "offered at least once", NAVY)
            if n("n_ever_mailed") else None,
            (f"{n('reach_total'):,}", "Responded",
             f"unique accounts, {str(m.get('reach_base') or 'eligible').lower()}",
             ORANGE),
            (f"{n('reach')}%", "Reach",
             f"of {str(m.get('reach_base') or 'eligible').lower()}", NAVY),
            (f"{n('reach_of_mailed')}%", "Of mailed",
             "ever responded", NAVY)
            if m.get("reach_of_mailed") is not None else None,
            (f"{n('reach_perml'):,.0f}", "Per offer",
             "new responders on average", NAVY)
            if m.get("reach_perml") is not None else None,
        ]
        tiles = [t for t in tiles if t][:6]
        cols = 3
        kw = (CONTENT_W - 0.6 * (cols - 1)) / cols
        for i, (value, label, note, rule) in enumerate(tiles):
            r_, c_ = divmod(i, cols)
            _tile(s, MARGIN_L + c_ * (kw + 0.6), top + 0.25 + r_ * 1.85,
                  kw, value, label, note, rule=rule)
        if m.get("responder_spend_share_pct") is not None:
            _text(s, MARGIN_L + 0.02, 6.42, CONTENT_W, 0.3,
                  f"Responders carry {n('responder_spend_share_pct')}% of "
                  f"card spend from "
                  f"{n('responder_share_of_eligible_pct', n('reach')):.0f}% "
                  f"of accounts.", size=10.5, color=GREY)
        _kicker(s)
    else:
        skip("Program reach", "reach")

    # ---- response rate and cumulative reach, one combo (issue #43) ------
    return None


def response_reach(h, m) -> str | None:
    """v5 build.py lines 1158-1185: Response and reach by offer."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    campaigns = m.get("campaign_rates") or []
    if campaigns:
        pair = headlines.waves(m)
        if pair:
            pair = (pair[0], "columns are each offer's response rate; the "
                             "line is cumulative reach of the eligible base")
        s, top = slide(pair, "Response and reach by offer")
        items = []
        best, worst = m.get("resprate_best"), m.get("resprate_worst")
        items.append(("Latest", f"{n('latest_resprate')}%",
                      str(m.get("latest_mailing", ""))))
        items.append(("Mean", f"{n('resprate_mean')}%", "all offers"))
        if best:
            items.append(("Highest", f"{best[1]:.1f}%", str(best[0])))
        if worst:
            items.append(("Lowest", f"{worst[1]:.1f}%", str(worst[0])))
        right = _rail(s, items, top=top)
        cum = [[r[0], r[2]] for r in (m.get("reach_cumulative") or [])]
        path = chart("resp_reach", charts.response_reach_combo,
                     _month_axis([[c[0], c[3]] for c in campaigns if c[3] is not None]),
                     _month_axis(cum))
        if path:
            _chart_left(s, path, top, right)
    else:
        skip("Response and reach by offer", "campaign_rates")

    # ---- per-offer summary: one table, response AND spend (issue #43:
    # James merged the per-mailer summary and the before/after slide) ----
    return None


def per_offer(h, m) -> str | None:
    """v5 build.py lines 1186-1269: Per-offer summary."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    campaigns = m.get("campaign_rates") or []
    ba_by = {str(e["month"]): e for e in (m.get("before_after") or [])}
    if campaigns:
        pair = headlines.before_after(m) or headlines.per_mailer(m)
        s, top = slide(pair, "Per-offer summary")
        in_flight = m.get("in_flight_mailings") or []
        wbw = {str(w[0]): w for w in (m.get("wb_waves") or [])}
        has_wb = bool(wbw)
        has_ba = bool(ba_by)
        # RPE: the unit sits in the header, so a row's one "%" (the response rate) is not read by the
        # validator's claim check as the change in the spend pair beside it (validate_deck FAIL, 1776)
        hdr = ["Offer", "Mailed", "Resp", "Response %"]
        if has_ba:
            hdr += ["Resp $/mo", "Ctrl $/mo"]
        if has_wb:
            hdr += ["Rev to date"]
        rows = [hdr]
        # RPE: as many offers as fit above the summary row and its note (v5 showed 7; on 1776 the
        # seventh pushed the note onto the KPI row): rows are 0.34in, the KPI row starts by 5.34
        fit = max(1, min(7, int((6.44 - 1.10 - 0.45 - (top + 0.1)) / 0.34) - 2))
        for tag, mailed, resp, rate in campaigns[-fit:]:
            row = [str(tag), f"{mailed:,}", f"{resp:,}", f"{rate}"]
            if has_ba:
                e = ba_by.get(str(tag))
                row += ([f"{_money(e['resp_pre'])} \u2192 {_money(e['resp_post'])}",
                         f"{_money(e['ctrl_pre'])} \u2192 {_money(e['ctrl_post'])}"]
                        if e else ["\u2013", "\u2013"])
            if has_wb:
                w = wbw.get(str(tag))
                row += [_money(w[3]) if w and w[3] is not None else "\u2013"]
            rows.append(row)
        # totals across ALL completed offers -- the visible tie to the
        # workbook's program responder count
        t_mailed = sum(c[1] for c in campaigns)
        t_resp = sum(c[2] for c in campaigns)
        total_row = ["All offers", f"{t_mailed:,}", f"{t_resp:,}",
                     f"{(100 * t_resp / t_mailed):.1f}" if t_mailed else "\u2013"]
        if has_ba:
            total_row += ["\u2013", "\u2013"]
        if has_wb:
            total_row += ["\u2013"]
        rows.append(total_row)
        ncol = len(hdr)
        widths = {4: [3.0, 3.0, 3.0, 3.1],
                  6: [1.9, 1.9, 1.7, 1.7, 2.5, 2.4],
                  5: [2.4, 2.4, 2.3, 2.3, 2.7],
                  7: [1.5, 1.5, 1.4, 1.4, 2.3, 2.3, 1.7]}
        _table(s, rows, MARGIN_L, top + 0.1, CONTENT_W,
               col_widths=widths.get(ncol), size=10.5)
        tbl_bottom = top + 0.1 + 0.34 * len(rows)
        # RPE (Sheila's 1798 review: 113 words on slide 106): the note keeps the window and drops
        # what the column headers already say
        note = (f"latest {min(fit, len(campaigns))} of {len(campaigns)} "
                f"completed offers; spend six months before each offer "
                f"against three after")
        if in_flight:
            note += f"; in flight: {', '.join(str(t) for t in in_flight[-2:])}"
        _text(s, MARGIN_L + 0.02, tbl_bottom + 0.08, CONTENT_W, 0.3,
              note + ".", size=FOOT_PT, color=GREY)
        kpis = []
        if m.get("ba_lift_net") is not None:
            kpis.append(("Net lift", f"{_money(m['ba_lift_net'])}/mo",
                         "vs control"))
        if m.get("ba_lift_pct") is not None:
            kpis.append(("Lift", f"{n('ba_lift_pct')}%", "responder spend"))
        if m.get("ba_spend_before") is not None:
            kpis.append(("Responders",
                         f"{_money(m['ba_spend_before'])} \u2192 "
                         f"{_money(m.get('ba_spend_after'))}", "pre to post"))
        if m.get("ba_control_before") is not None:
            kpis.append(("Control",
                         f"{_money(m['ba_control_before'])} \u2192 "
                         f"{_money(m.get('ba_control_after'))}", "pre to post"))
        if kpis:
            kw = (CONTENT_W - 0.3 * (len(kpis) - 1)) / len(kpis)
            # RPE: the row's note (k_top + 0.80, 0.28 tall) must end above the footer at 6.44; v5 let a
            # long offer table push it onto the footer (validate_deck FAIL on 1776)
            k_top = min(max(tbl_bottom + 0.55, 5.15), 6.44 - 1.10)
            for i, (label, value, note_) in enumerate(kpis):
                _kpi_flat(s, MARGIN_L + i * (kw + 0.3), k_top, kw,
                          label, value, note_)
            _text(s, MARGIN_L, min(k_top + 1.18, 6.44), CONTENT_W, 0.3,
                  "Control is mailed non-responders.", size=FOOT_PT, color=GREY)
        _kicker(s)
    else:
        skip("Per-offer summary", "campaign_rates")

    # ---- the response ladder and NU conversion, wave by wave ------------
    return None


def ladder_waves(h, m) -> str | None:
    """v5 build.py lines 1270-1304: Ladder and NU conversion by offer."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    lw = m.get("ladder_by_wave") or []
    if lw:
        s, top = slide(headlines.ladder_waves(m),
                       "Ladder and NU conversion by offer")
        items = []
        moves = dict(m.get("ladder_movement") or [])
        if moves:
            items.append(("Moved up", f"{moves.get('Up', 0):,}",
                          "repeat responses"))
            items.append(("Same / down",
                          f"{moves.get('Same', 0):,} / {moves.get('Down', 0):,}",
                          "repeat responses"))
        if m.get("ladder_repeat_pct") is not None:
            items.append(("Repeat share", f"{n('ladder_repeat_pct')}%",
                          "of all responses"))
        if m.get("nu_conversion_pct") is not None:
            items.append(("NU conversion", f"{n('nu_conversion_pct')}%",
                          f"{m.get('nu_converted_ever', 0):,} of "
                          f"{m.get('nu_partial_ever', 0):,} partials"))
        right = _rail(s, items, top=top)
        path = chart("ladder_waves", charts.grouped_bars,
                     _periods.axis_months([str(r["wave"]) for r in lw[-10:]]),
                     [r["first_time"] for r in lw[-10:]],
                     [r["repeat"] for r in lw[-10:]],
                     "first-time", "repeat")
        if path:
            _chart_left(s, path, top, right)
        # RPE (Sheila's 1798 review): v5's footnote here repeated the subtitle ("judged against each
        # account's best prior tier") and sat on the chart's month labels; dropped
        _kicker(s)
    else:
        skip("Ladder and NU conversion by offer", "ladder_by_wave")

    # ---- segment economics, pooled across waves -------------------------
    return None


def segment_traj(h, m) -> str | None:
    """v5 build.py lines 1305-1344: Segment trajectories."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    seg = [r for r in (m.get("segment_summary") or [])
           if r.get("did") is not None]
    if seg:
        s, top = slide(headlines.segment_traj(m), "Segment trajectories")
        items = []
        sbest = max(seg, key=lambda r: r.get("did_per_1000_mailed") or 0)
        items.append(("Best segment", str(sbest["segment"]),
                      f"{_money(sbest.get('did_per_1000_mailed'))}/1,000 mailed"))
        arrested = [r for r in seg if (r.get("did_from_control_pct") or 0) > 0]
        if arrested:
            worst_c = max(arrested,
                          key=lambda r: r.get("did_from_control_pct") or 0)
            items.append(("From control fall",
                          f"{worst_c['did_from_control_pct']:.0f}%",
                          f"of {worst_c['segment']}'s DiD"))
        if m.get("segment_ic_rate"):
            items.append(("IC rate", ic_pct(m["segment_ic_rate"]),
                          "applied to DiD"))
        right = _rail(s, items, top=top)
        rows = [["Segment", "Offered", "Resp", "Resp d/mo", "Ctrl d/mo",
                 "DiD/mo", "$/1,000"]]
        for r in sorted(seg,
                        key=lambda r: -(r.get("did_per_1000_mailed") or 0))[:9]:
            rows.append([str(r["segment"]), f"{r.get('offered_n', 0):,}",
                         f"{r.get('response_rate', 0):.1f}%",
                         _money(r.get("resp_delta")), _money(r.get("non_delta")),
                         _money(r.get("did")),
                         _money(r.get("did_per_1000_mailed"))])
        _table(s, rows, MARGIN_L, top + 0.1, right - MARGIN_L - 0.25,
               col_widths=[1.3, 1.15, 1.05, 1.35, 1.35, 1.2, 1.5], size=FOOT_PT)
        _text(s, MARGIN_L + 0.02, 6.42, CONTENT_W, 0.3,
              "Incremental frame: interchange only, net of control; where the control fell, "
              "part of each DiD is decline arrested. Not the workbook's booked revenue.",
              size=FOOT_PT, color=GREY)
        _kicker(s)
    else:
        skip("Segment trajectories", "segment_summary")

    # ---- the penalty box: a rule audit, rendered only when broken -------
    return None


def penalty(h, m) -> str | None:
    """v5 build.py lines 1345-1367: The penalty box."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    pbv = m.get("penalty_box_violations")
    if pbv:
        s, top = slide(headlines.penalty(m), "The penalty box")
        items = [("Violations", f"{pbv:,}",
                  f"within {m.get('penalty_box_waves', 0)} mailers")]
        right = _rail(s, items, top=top)
        rows = [["Tier", "Same-tier repeats"]]
        for tier, cnt in (m.get("penalty_box_by_tier") or [])[:8]:
            rows.append([str(tier), f"{cnt:,}"])
        _table(s, rows, MARGIN_L, top + 0.1, right - MARGIN_L - 0.25,
               col_widths=[4.0, 4.0], size=10.5)
        _text(s, MARGIN_L + 0.02, 6.44, CONTENT_W, 0.3,
              "The program forbids repeating a tier this soon; a "
                   "non-zero count is a suppression gap, not a finding "
                   "about customers.", size=FOOT_PT, color=GREY)
        _kicker(s)
    elif pbv == 0:
        skip("The penalty box",
             reason="penalty_box_violations 0 -- rule held")
    else:
        skip("The penalty box", "penalty_box_violations")

    # ---- what a responder is worth, group by group ----------------------
    return None


def counterfactual(h, m) -> str | None:
    """v5 build.py lines 1411-1439: The counterfactual."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    cf_a = m.get("counterfactual_actual") or []
    cf_w = m.get("counterfactual_without") or []
    if cf_a and cf_w:
        s, top = slide(headlines.counterfactual(m), "The counterfactual")
        items = []
        if m.get("counterfactual_gap_latest") is not None:
            items.append(("Latest month",
                          _money(m["counterfactual_gap_latest"]),
                          "above the line"))
        if m.get("counterfactual_gap_total") is not None:
            items.append(("Cumulative", _money(m["counterfactual_gap_total"]),
                          "across the window"))
        if m.get("counterfactual_ic_total") is not None:
            items.append(("Interchange", _money(m["counterfactual_ic_total"]),
                          "earned on the gap"))
        right = _rail(s, items, top=top)
        gap_rows = [[a[0], a[1] - w[1]] for a, w in zip(cf_a, cf_w)]
        path = chart("counterfactual", charts.line_series, _month_axis(gap_rows),
                     ylabel="$ above the no-program line",
                     highlight_zero=True, money=True)
        if path:
            # RPE: the chart ends above its footnote (v5's 4.9in ran the month labels under it, 1798)
            _chart_left(s, path, top, right, max_h=6.38 - top)
        _text(s, MARGIN_L + 0.02, 6.44, CONTENT_W, 0.3,
              "The line is responders' own pre-spend moved by the "
                   "control's trajectory -- a DiD view, not a before/after.", size=FOOT_PT, color=GREY)
        _kicker(s)
    else:
        skip("The counterfactual", "counterfactual_actual")
    return None


def segments(h, m) -> str | None:
    """v5 build.py lines 1440-1449: Which offer earns its postage."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    segs = m.get("segment_summary") or []
    if segs:
        s, top = slide(headlines.segments(m), "Which offer earns its postage")
        path = chart("segments", charts.segment_efficiency, segs)
        if path:
            _picture(s, path, top=top + 0.05, max_h=7.0 - top)

    else:
        skip("Which offer earns its postage", "segment_summary")
    return None


def dot_ask(h, m) -> str | None:
    """v5 build.py lines 1450-1473: Transaction increase over the ask."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    if m.get("dot_n"):
        s, top = slide(headlines.dot_ask(m), "Transaction increase over the ask")
        # "At +40" lives on the segment slide (its own column and the
        # headline); its rail spot carries the #39 beat rate when measured
        beat_tile = (("Beat prior high", f"{n('dot_beat_high_pct'):.0f}%",
                      "set a new personal high")
                     if m.get("dot_beat_high_pct") is not None
                     else ("At +40", f"{n('dot_tail40'):,}", "or more"))
        right = _rail(s, [
            ("Responders", f"{n('dot_n'):,}", "measured"),
            ("Mean", labels.signed(n('dot_mean'), '.1f'),
             "swipes above prior"),
            ("Median", labels.signed(n('dot_median'), '.1f'),
             "swipes above prior"),
            beat_tile,
            ("Fell", f"{n('dot_fell_n'):,}", "below own baseline")
            if m.get("dot_fell_n") is not None else None,
        ], top=top)
        path = chart("overask", charts.histogram, m.get("dot_hist") or [],
                     mean=m.get("dot_mean"), median=m.get("dot_median"))
        if path:
            _chart_left(s, path, top, right)

    # ---- who delivers the lift: the same cut per response tier ----------
    return None


def dot_segments(h, m) -> str | None:
    """v5 build.py lines 1474-1495: Lift by response segment."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    seg = m.get("dot_by_segment") or []
    if seg:
        s, top = slide(headlines.dot_segments(m), "Lift by response segment")
        rows = [["Tier", "Pairs", "Mean lift", "Median", "% increased",
                 "At +40", "Beat prior high"]]
        for r in seg[:6]:
            beat = (f"{r[6]:.0f}%" if len(r) > 6 and r[6] is not None
                    else "n/a")
            rows.append([str(r[0]), f"{r[1]:,}", f"{r[2]:+.1f}",
                         f"{r[3]:+.1f}", f"{r[4]:.0f}%", f"{r[5]:,}", beat])
        _table(s, rows, MARGIN_L, top + 0.15, 11.9,
               col_widths=[1.9, 1.5, 1.7, 1.5, 1.8, 1.5, 2.0], size=11)
        _text(s, MARGIN_L + 0.02, top + 0.15 + 0.34 * len(rows) + 0.25,
              10.5, 0.4,
              "Lift is each account's swipes over its own prior run rate; "
              "tier is the goal the response achieved. Beat prior high: "
              "share of pairs whose post-mail months set a new personal "
              "swipe high.",
              size=10.5, color=GREY)
    else:
        skip("Lift by response segment", "dot_by_segment")
    return None


def depth(h, m) -> str | None:
    """v5 build.py lines 1496-1526: Depth of engagement — repeat responders."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    if m.get("depth"):
        # metric-first (James, issue #43): the numbers across the top in
        # the clean tile grid, the donut centered below them
        s, top = slide(None, "Depth of engagement — repeat responders")
        d = m["depth"]
        tiles = [(f"{d[0]:,}", "Responded once", "took exactly one offer",
                  NAVY),
                 (f"{d[1]:,}", "Responded twice", "came back for a second",
                  NAVY),
                 (f"{d[2]:,}", "Three or more", "the habitual responders",
                  NAVY),
                 (f"{n('depth_repeat_pct')}%", "Repeat rate",
                  "of all responders", ORANGE)]
        kw = (CONTENT_W - 0.9) / 4
        for i, (value, label, note, rule) in enumerate(tiles):
            _tile(s, MARGIN_L + i * (kw + 0.3), top + 0.05, kw, value,
                  label, note, rule=rule)
        path = chart("depth", charts.donut,
                     [["Once", d[0]], ["Twice", d[1]], ["3 or more", d[2]]],
                     center_value=f"{n('depth_repeat_pct')}%",
                     center_label="responded again")
        if path:
            _fit_picture(s, path, 2.9, top + 1.6, max_w=7.4,
                         max_h=6.6 - (top + 1.6))
        _kicker(s)





    # ---- first swipes: onboarding, mail, or on their own ----------------
    return None


def activation(h, m) -> str | None:
    """v5 build.py lines 1527-1557: Organic versus program activation."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    if m.get("activation_l12m_n") is not None and             m.get("activation_existing_n") is not None:
        s, top = slide(headlines.activation_split(m),
                       "Organic versus program activation")
        tiles = [(f"{n('activation_l12m_n'):,}", "First swipes",
                  "last 12 months", NAVY)]
        if m.get("activation_program_pct") is not None:
            tiles.append((f"{n('activation_program_pct'):.0f}%",
                          "Program share", "of existing activations",
                          ORANGE))
        if m.get("activation_organic_n") is not None:
            tiles.append((f"{n('activation_organic_n'):,}", "Organic",
                          "swiped without ever being mailed", NAVY))
        kw = (CONTENT_W - 0.6 * (len(tiles) - 1)) / max(len(tiles), 1)
        for i, (value, label, note, rule) in enumerate(tiles):
            _tile(s, MARGIN_L + i * (kw + 0.6), top + 0.05, kw, value,
                  label, note, rule=rule)
        bars = [["New accounts", m.get("activation_new_account_n")],
                ["Mailed, then swiped", m.get("activation_program_n")],
                ["Organic", m.get("activation_organic_n")]]
        bars = [b for b in bars if b[1]]
        if bars:
            path = chart("activation", charts.composition, bars,
                         highlight="Mailed, then swiped")
            if path:
                _fit_picture(s, path, MARGIN_L, top + 1.75,
                             max_w=CONTENT_W, max_h=6.5 - (top + 1.75))
        _kicker(s)
    else:
        skip("Organic versus program activation", "activation_l12m_n")
    return None


def cohort(h, m) -> str | None:
    """v5 build.py lines 1558-1604: What a response does to spend."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    offsets = m.get("cohort_offsets") or []
    indexed = m.get("cohort_indexed") or {}
    if offsets and indexed:
        # RPE (Sheila's 1798 slide review, 2026-10-30, combine group L): six slides told the
        # responder gain with different numbers (106, 111, 117, 119, 120, 123), and $524/mo on one
        # read against $371/mo on another as a contradiction. They are two windows on one program:
        # this slide carries both, each named by its window, on responders' and the control's spend.
        rows = m.get("cohort_lift") or []
        later = next((r for r in rows if r.get("horizon_months") == 12), None)
        did12 = later.get("diff_in_diff") if later else None
        net = m.get("ba_lift_net")
        pair = headlines.cohort(m)
        parts = []
        if net is not None:
            # the window as the before/after headline names it (headlines.before_after)
            parts.append(f"{_money(net)}/mo net of control in the three months after mail")
        if did12 is not None:
            parts.append(f"{_money(did12)}/mo on the pooled cohort 12 months on")
        if pair and parts:
            pair = (pair[0], "; ".join(parts))
        s, top = slide(pair, "What a response does to spend")
        items = []
        if net is not None:
            items.append(("3 months after mail", f"{_money(net)}/mo", "vs the 6 months before"))
        if did12 is not None:
            items.append(("12 months on", f"{_money(did12)}/mo", "pooled cohort, net of control"))
        if m.get("counterfactual_gap_total") is not None:
            items.append(("Spend held", _money(m["counterfactual_gap_total"]),
                          "above the no-program line"))
        if m.get("sustained_months_above") is not None:
            items.append(("Above baseline", f"{m['sustained_months_above']} of 12",
                          "months after the mail"))
        right = _rail(s, items, top=top) if items else h["RIGHT_EDGE"]
        spend = m.get("cohort_spend") or {}
        # ---- James's lines (#62): the legacy combo, pooled + extended --
        seg_det = m.get("cohort_seg_detail") or {}
        if seg_det.get("segments"):
            sc_pair = headlines.seg_combo(m)
            s2, top2 = slide(sc_pair, "Behavior by segment around the offer")
            path2 = chart("seg_combo", charts.combo_lines, seg_det)
            if path2:
                _fit_picture(s2, path2, MARGIN_L, top2 + 0.05,
                             max_w=CONTENT_W, max_h=6.35 - (top2 + 0.05))
            _kicker(s2)
        else:
            skip("Behavior by segment around the offer", "cohort_seg_detail")

        # ---- the comps: responders vs control, spend by response tier --
        tiers_tr = m.get("cohort_spend_by_tier") or {}
        big = {t: s for t, s in tiers_tr.items()
               if (m.get("cohort_tier_n") or {}).get(t, 0) >= 50}
        tr_pair = headlines.trajectory(m, "spend")
        if big and tr_pair:
            s2, top2 = slide(tr_pair, "Responders versus control around the offer")
            ctrl = (m.get("cohort_spend") or {}).get("mailed_nonresp")
            path2 = chart("traj_spend", charts.trajectory_lines,
                          m.get("cohort_offsets") or [], big, ctrl,
                          ylabel="$ per account per month")
            if path2:
                _fit_picture(s2, path2, MARGIN_L, top2 + 0.1,
                             max_w=CONTENT_W, max_h=6.3 - (top2 + 0.1))
            bases = ", ".join(f"{t} {n_:,}" for t, n_ in sorted(
                (m.get("cohort_tier_n") or {}).items()) if t in big)
            _text(s2, MARGIN_L + 0.02, 6.5, CONTENT_W, 0.28,
                  f"Responder pairs per tier: {bases}; tiers under 50 "
                  f"pairs pooled out; control = mailed non-responders",
                  size=FOOT_PT, color=GREY)
            _kicker(s2)
        else:
            skip("Responders versus control around the offer",
                 "cohort_spend_by_tier")

        if spend.get("responders") and spend.get("mailed_nonresp"):
            path = chart("cohort", charts.cohort_trajectory, offsets,
                         {"responders": spend["responders"],
                          "mailed_nonresp": spend["mailed_nonresp"]}, indexed=False)
        else:
            path = chart("cohort", charts.cohort_trajectory, offsets, indexed,
                         indexed=True)
        if path:
            _chart_left(s, path, top + 0.05, right, max_h=6.3 - (top + 0.05))
        _text(s, MARGIN_L + 0.02, 6.42, CONTENT_W, 0.3,
              "Control is mailed accounts that did not respond. The two figures differ by "
              "window, not method: the gain is largest just after the mail.",
              size=FOOT_PT, color=GREY)
        _kicker(s)
    return None


def sustained(h, m) -> str | None:
    """v5 build.py lines 1605-1621: Sustained responder activity."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    if m.get("sustained_index"):
        s, top = slide(headlines.sustained(m), "Sustained responder activity")
        above = m.get("sustained_months_above")
        right = _rail(s, [
            ("Months above", f"{above}", "of 12 tracked"),
            ("At +6", f"{dict(m['sustained_index']).get(6, 0):+.0f}%",
             "vs own baseline"),
            ("At +12", f"{dict(m['sustained_index']).get(12, 0):+.0f}%",
             "vs own baseline"),
        ], top=top)
        path = chart("sustained", charts.line_series,
                     [[f"+{r[0]}", r[1]] for r in m["sustained_index"]],
                     ylabel="vs pre-mail baseline", pct=True,
                     highlight_zero=True)
        if path:
            _chart_left(s, path, top, right)
    return None


def first_vs_repeat(h, m) -> str | None:
    """v5 build.py lines 1622-1637: First-time versus repeat responders."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    if m.get("ladder_repeat") is not None:
        s, top = slide(None, "First-time versus repeat responders")
        mv = dict(m.get("ladder_movement") or [])
        right = _rail(s, [
            ("First-time", f"{n('ladder_first_time'):,}", "offers 2 onward"),
            ("Repeat", f"{n('ladder_repeat'):,}", f"{n('ladder_repeat_pct')}%"),
            ("Moved up", f"{mv.get('Up', 0):,}", "vs prior peak"),
            ("Moved down", f"{mv.get('Down', 0):,}", "vs prior peak"),
        ], top=top)
        path = chart("ladder", charts.tier_bars,
                     [["Moved up", mv.get("Up", 0)],
                      ["Same tier", mv.get("Same", 0)],
                      ["Moved down", mv.get("Down", 0)]])
        if path:
            _chart_left(s, path, top, right)
    return None


def partial_convert(h, m) -> str | None:
    """v5 build.py lines 1638-1653: Do partial responders convert?."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    if m.get("nu_partial_ever"):
        s, top = slide(None, "Do partial responders convert?")
        right = _rail(s, [
            ("Ever NU 1-4", f"{n('nu_partial_ever'):,}", "fell short"),
            ("Converted", f"{n('nu_converted_ever'):,}",
             f"{n('nu_conversion_pct')}%"),
            ("Never", f"{n('nu_never_converted'):,}", "still short"),
        ], top=top)
        path = chart("nuconv", charts.tier_bars,
                     [["Converted to NU 5+ or TH", n("nu_converted_ever")],
                      ["Never converted", n("nu_never_converted")]])
        if path:
            _chart_left(s, path, top, right)

    # Age and balance were twin slides: the same grouped-bar form, the same
    # rail, back to back. One slide, two panels (#53 P1).
    return None


def responder_profile(h, m) -> str | None:
    """v5 build.py lines 1673-1718: Who responds — the profile."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    prof = m.get("responder_profile") or {}
    prof_rows = {k: v for k, v in prof.items()
                 if not k.startswith("_") and isinstance(v, list)
                 and len(v) == 2}
    if prof_rows:
        s, top = slide(headlines.responder_profile(m),
                       "Who responds — the profile")
        items = []
        if m.get("depth_repeat_pct") is not None:
            items.append(("Repeat responders", f"{n('depth_repeat_pct')}%",
                          "responded 2+ times"))
        grouping = m.get("response_grouping") or {}
        if grouping:
            top_grp = max(grouping.items(), key=lambda kv: kv[1])
            items.append(("Largest group", labels.clip(top_grp[0], 16),
                          f"{top_grp[1]:,} responders"))
        right = _rail(s, items, top=top) if items else 12.35
        heads = {"balance_median": ("Median balance", _money),
                 "holder_age_median": ("Median holder age",
                                       lambda v: f"{v:.0f}"),
                 "debit_pct": ("Carry a debit card",
                               lambda v: f"{v:.0f}%"),
                 "spend_per_mo": ("Debit spend / month",
                                  lambda v: f"{_money(v)}/mo")}
        cols = [str(c).capitalize()
                for c in (prof.get("_columns")
                          or ["responders", "non-responders"])]
        rows = [[""] + cols[:2]]
        for key, pair in prof_rows.items():
            label, fmt = heads.get(key, (key.replace("_", " "), str))
            rows.append([label, fmt(pair[0]), fmt(pair[1])])
        table_w = min(right - MARGIN_L - 0.25, 7.2)
        _table(s, rows, MARGIN_L, top + 0.1, table_w,
               col_widths=[2.8, 2.2, 2.2], size=10.5)
        raa = m.get("response_account_age") or []
        if raa:
            y = top + 0.1 + 0.32 * len(rows) + 0.2
            path = chart("resp_acct_age", charts.grouped_bars,
                         [r[0] for r in raa], [r[1] for r in raa],
                         [r[2] for r in raa], "mailed", "responded")
            if path:
                _chart_left(s, path, y, right, max_h=7.0 - y - 0.3)
    else:
        skip("Who responds — the profile", "responder_profile")

    # ============ CHAPTER 3: debit card =================================
    return None


def tier_movement(h, m) -> str | None:
    """v5 build.py lines 1836-1850: Tier movement by response status."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    tm_pair = headlines.tier_movement(m)
    if tm_pair:
        s, top = slide(tm_pair, "Tier movement by response status")
        path = chart("tier_movement", charts.stacked_movement,
                     m.get("mig_by_group") or [])
        if path:
            _picture(s, path, top=top + 0.15, max_h=6.4 - top)
        _text(s, MARGIN_L + 0.02, 6.5, CONTENT_W, 0.28,
              "Movement compares each account's swipe tier in its first "
              "and latest window on file; bases differ by group and are "
              "printed on each bar.", size=FOOT_PT, color=GREY)
        _kicker(s)
    else:
        skip("Tier movement by response status", "mig_by_group")
    return None


def migration(h, m) -> str | None:
    """v5 build.py lines 2423-2451: Swipe-tier migration."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    if m.get("mig_base"):
        s, top = slide(headlines.migration(m), "Swipe-tier migration")
        right = _rail(s, [
            ("Moved up", f"{n('mig_up_pct')}%", f"{n('mig_up_n'):,} accounts"),
            ("Same tier", f"{n('mig_same_pct')}%", ""),
            ("Moved down", f"{n('mig_down_pct')}%", f"{n('mig_down_n'):,} accounts"),
            ("Started swiping", f"{n('mig_entered_use_n'):,}",
             f"{n('mig_entered_use_pct')}% of non-users then"),
        ], top=top)
        y = top + 0.1
        # RPE (Sheila's 1798 review): v5's footnote here repeated the subtitle's responder figures
        # and was drawn under the chart, which covered it; dropped
        _kicker(s)
        dist_first, dist_latest = m.get("mig_dist_first") or [], m.get("mig_dist_latest") or []
        if dist_first and dist_latest:
            path = chart("migration", charts.grouped_bars,
                         [r[0] for r in dist_first],
                         [r[2] for r in dist_first], [r[2] for r in dist_latest],
                         m.get("mig_first", "then"), m.get("mig_latest", "now"),
                         fmt="{:.0f}%")
            if path:
                _chart_left(s, path, y, right, max_h=7.0 - y - 0.3)

    else:
        skip("Swipe-tier migration", "mig_base")
    return None


def latest_mailer(h, m) -> str | None:
    """v5 build.py lines 2823-2838: The most recent mailer."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    ms = m.get("mailer_summary") or {}
    rd_all = m.get("mailer_resp_detail") or {}
    # "most recent with data" = the newest wave that can carry the whole
    # pair; fall back to the newest wave with a summary alone
    paired = [t for t in ms if t in rd_all]
    latest_pair = (paired or list(ms))[-1] if ms else None

    if latest_pair:
        d = ms[latest_pair]
        # RPE: v5 drew this as new() + register() + _title(); the cut draws the title first
        # and numbers after it, so the same headline and subtitle go through slide()
        s, top = slide((f"{latest_pair} reached {d['mailed']:,} accounts and "
                  f"{d['responded']:,} responded \u2014 {d['rate']:.1f}%",
               "response share and rate by challenge tier, and who the "
               "responders were"), "The most recent mailer")
        path = chart(f"mailsum_{latest_pair}", charts.mailer_summary_panel, d)
        # RPE (James Gilmore, 2026-10-29, 1798 slide 127): the picture starts at `top`, below wherever the
        # headline block ends; v5's fixed 1.55 put a two-line title's subtitle behind it
        if path:
            _fit_picture(s, path, MARGIN_L, top, max_w=CONTENT_W, max_h=4.85 - (top - 1.55))
        _kicker(s)
    else:
        skip("The most recent mailer", "mailer_summary")
    return None


def latest_trajectory(h, m) -> str | None:
    """v5 build.py lines 2839-2855: The most recent mailer trajectory."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    ms = m.get("mailer_summary") or {}
    rd_all = m.get("mailer_resp_detail") or {}
    # "most recent with data" = the newest wave that can carry the whole
    # pair; fall back to the newest wave with a summary alone
    paired = [t for t in ms if t in rd_all]
    latest_pair = (paired or list(ms))[-1] if ms else None

    if latest_pair and latest_pair in rd_all:
        rd = rd_all[latest_pair]
        nseg = len(rd["segments"])
        # RPE: v5 drew this as new() + register() + _title(); the cut draws the title first
        # and numbers after it, so the same headline and subtitle go through slide()
        s, top = slide((f"{latest_pair}: responders versus their own segment",
               f"{nseg} challenge segment{'s' if nseg != 1 else ''}; spend "
               f"(top) and swipes (bottom) per account, every month after "
               f"the mail the file carries"), "The most recent mailer trajectory")
        path = chart(f"mailtraj_{latest_pair}", charts.segment_resp_grid, rd)
        if path:
            _fit_picture(s, path, MARGIN_L, top, max_w=CONTENT_W, max_h=4.85 - (top - 1.55))
        _kicker(s)
    else:
        skip("The most recent mailer trajectory", "mailer_resp_detail")
    return None


def latest_offer(h, m) -> str | None:
    """v5 build.py lines 2856-2877: The most recent offer."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    md = m.get("mailer_detail") or {}
    # ---- the most recent offer (James, 2026-08-22: "add the most
    # recent mail") -- the latest completed wave's legacy combo, its own
    # stable slide id so the manifest can carry it in the main path
    if md:
        last_tag = list(md)[-1]
        d_last = md[last_tag]
        n_mailed_l = sum(d_last["counts"].values())
        # RPE: v5 drew this as new() + register() + _title(); the cut draws the title first
        # and numbers after it, so the same headline and subtitle go through slide()
        s, top = slide((f"The most recent offer: {last_tag} reached "
                  f"{n_mailed_l:,} accounts",
               "swipes (top) and spend (bottom) per mailed account by "
               "segment; the mail month is the orange line"), "The most recent offer")
        path = chart("combo_latest", charts.combo_lines, d_last)
        if path:
            _fit_picture(s, path, MARGIN_L, top, max_w=CONTENT_W,
                         max_h=4.85 - (top - 1.55))
        _kicker(s)
    else:
        skip("The most recent offer", "mailer_detail")
    return None


def offer_detail(h, m) -> str | None:
    """v5 build.py lines 2878-2934: Offer detail."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    ms = m.get("mailer_summary") or {}
    rd_all = m.get("mailer_resp_detail") or {}
    md = m.get("mailer_detail") or {}
    if ms or md:
        divider("Offer detail")
        # Newest first. The reader opens Offer detail looking for the most
        # recent mailing, and should not scroll a year back to reach it.
        # Render order only -- mailer_summary still WALKS waves oldest-first,
        # because its ladder history (first-time vs repeat, moved-up) is
        # measured against what came before.
        #
        # One block per offer (#53 P3): its summary, its behaviour by
        # segment, its responders against their segment. Three forms in
        # rotation, everything about one mailing on adjacent slides, and the
        # responders picture drawn once -- it was drawn twice per mailer
        # under two titles, byte for byte the same (#231).
        # RPE (Sheila's 1798 slide review, 2026-10-30, combine group P): v5 drew a summary slide per
        # mailer, twelve near-identical pages (131-142). One table now, one row per mailer, newest
        # first, every mailer included: the latest's own slide folds into Program reach (group K).
        if ms:
            _mailer_table(h, m, ms)
        detail_tags = list(md)[-12:]
        ordered = list(dict.fromkeys(list(ms) + list(md)))
        for tag in reversed(ordered):
            if tag not in detail_tags:
                continue
            d = md[tag]
            n_mailed = sum(d["counts"].values())
            # RPE: v5 drew this as new() + register() + _title(); the cut draws the title first
            # and numbers after it, so the same headline and subtitle go through slide()
            s, top = slide((f"{tag}: swipes and spend by segment",
                   f"{n_mailed:,} mailed accounts with a segment call; "
                   f"lines are per-account monthly averages"), f"Offer {tag} by segment")
            path = chart(f"combo_{tag}", charts.combo_lines, d)
            if path:
                _fit_picture(s, path, MARGIN_L, top,
                             max_w=CONTENT_W, max_h=5.5 - (top - 1.55))
            rd = rd_all.get(tag)
            if rd:
                nseg = len(rd["segments"])
                # RPE: v5 drew this as new() + register() + _title(); the cut draws the title first
                # and numbers after it, so the same headline and subtitle go through slide()
                s, top = slide((f"{tag}: responders versus their own segment",
                       f"{nseg} challenge segment{'s' if nseg != 1 else ''}, "
                       f"each responder group against its segment's "
                       f"non-responders; spend (top) and swipes (bottom) "
                       f"per account"), f"{tag}: responders versus their segment")
                path = chart(f"resp_{tag}", charts.segment_resp_grid, rd)
                if path:
                    _fit_picture(s, path, MARGIN_L, top,
                                 max_w=CONTENT_W, max_h=5.5 - (top - 1.55))
    return None



def _mailer_table(h, m, ms) -> None:
    """Every mailer on one appendix page: offer, mailed, responded, response rate, the share
    responding for the first time, and the workbook's revenue to date when a workbook is on hand."""
    tags = list(ms)
    wbw = {str(w[0]): w for w in (m.get("wb_waves") or [])}
    has_wb = any(t in wbw for t in tags)
    mailed = sum(ms[t]["mailed"] for t in tags)
    resp = sum(ms[t]["responded"] for t in tags)
    top_rate = max(ms[t]["rate"] for t in tags)
    best = [t for t in tags if ms[t]["rate"] == top_rate]
    best_s = " and ".join(best[:2]) + (f" and {len(best) - 2} more" if len(best) > 2 else "")
    # one headline line, so every mailer fits the table
    pair = (f"{len(tags)} mailer{'s' if len(tags) != 1 else ''}, the best responding at "
            f"{top_rate:.1f}%",
            f"best: {best_s}; {resp:,} responses from {mailed:,} pieces mailed"
            + (f", {100 * resp / mailed:.1f}% overall" if mailed else "") + "; newest first")
    s, top = h["slide"](pair, "Mailer summaries")
    # as many rows as end above the footnote (0.3in each, header included), newest first
    fit = max(1, int((6.38 - (top + 0.1)) / 0.3) - 1)
    shown = list(reversed(tags))[:fit]
    hdr = ["Offer", "Mailed", "Responded", "Response %", "First-time %"]
    if has_wb:
        hdr.append("Rev to date")
    rows = [hdr]
    for tag in shown:
        d = ms[tag]
        first = (d.get("inside") or {}).get("first_time_pct")
        row = [str(tag), f"{d['mailed']:,}", f"{d['responded']:,}", f"{d['rate']:.1f}",
               f"{first:.0f}" if first is not None else "\u2013"]
        if has_wb:
            w = wbw.get(str(tag))
            row.append(_money(w[3]) if w and w[3] is not None else "\u2013")
        rows.append(row)
    widths = [2.13, 2.0, 2.0, 2.0, 2.0, 2.0] if has_wb else [2.53, 2.4, 2.4, 2.4, 2.4]
    h["table"](s, rows, h["MARGIN_L"], top + 0.1, h["CONTENT_W"], col_widths=widths, size=11)
    note = ("Response % is responders over pieces mailed; first-time % is the share of "
            "responders answering an offer for the first time.")
    if len(shown) < len(tags):
        note = f"Newest {len(shown)} of {len(tags)} mailers. " + note
    if has_wb:
        note += " Rev to date: the ARS Workbook's To Date column."
    h["text"](s, h["MARGIN_L"] + 0.02, 6.42, h["CONTENT_W"], 0.3, note, size=FOOT_PT,
              color=h["GREY"])


def _responses_caption(m, n) -> str:
    """v5 build.py `_responses_caption`: the two drops between responses_total and reach_total, named.

    responses_total counts response EVENTS across the whole file -- an
    account that answered two offers counts twice. reach_total counts unique
    ACCOUNTS among the currently eligible. Captioning the first with the
    second made one tile carry two populations and two units, and four
    figures on the response story stopped reconciling (#86).
    """
    whole = m.get("reach_total_whole_file")
    if whole:
        return (f"response events; {whole:,} accounts, "
                f"{n('reach_total'):,} still eligible")
    return f"response events; {n('reach_total'):,} unique eligible accounts"


def hero(h, m) -> str | None:
    """v5 build.py lines 1006-1075: The campaign hero."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    RIGHT_EDGE = h["RIGHT_EDGE"]
    hero_pair = headlines.hero(m)
    if hero_pair:
        s, top = slide(hero_pair, "The campaign hero")
        # the oversized hero number (DESIGN/ spec) -- profit when the
        # workbook is present, the held-spend figure otherwise
        if (m.get("gt_deferred_balance") or 0) > 1 \
                and m.get("gt_state") != "clear":
            big = _money((m.get("gt_revenue_ltd") or 0)
                         - (m.get("gt_paid_ltd") or 0))
            big_note = "earned over fees paid (2:1 guarantee, deferral tracker)"
        elif m.get("wb_profit_ltd") is not None:
            big, big_note = _money(m["wb_profit_ltd"]), \
                "program profit, life to date (ARS Workbook)"
        elif m.get("counterfactual_gap_total") is not None:
            big, big_note = _money(m["counterfactual_gap_total"]), \
                "spend held above the no-mail line"
        else:
            big, big_note = _money(m.get("ba_lift_net")), \
                "per responder-month over control"
        _text(s, MARGIN_L, top - 0.05, 5.4, 1.1, big, size=54, bold=True,
              font=HEAD_FONT, color=NAVY)
        _text(s, MARGIN_L + 0.06, top + 0.98, 5.4, 0.35, big_note,
              size=12, color=GREY)
        camp = [c for c in (m.get("campaign_rates") or []) if c[3] is not None]
        if camp:
            path = chart("hero_spark", charts.line_series,
                         _month_axis([[str(c[0]), c[3]] for c in camp]),
                         ylabel="response %", pct=True)
            if path:
                _fit_picture(s, path, 6.3, top - 0.05,
                             max_w=RIGHT_EDGE - 6.3, max_h=2.4)
        tiles = [
            ("mailing", "Responses", f"{n('responses_total'):,}",
             _responses_caption(m, n))
            if m.get("responses_total") else None,
            ("lift", "Lift vs control",
             f"{_money(m['ba_lift_net'])}/mo", "difference-in-differences")
            if m.get("ba_lift_net") is not None else None,
            ("shield", "Retention edge",
             f"{labels.signed(n('attrition_mailer_lift_pp'), '.1f')} pts",
             "responders close less")
            if m.get("attrition_mailer_lift_pp") is not None else None,
        ]
        tiles = [t for t in tiles if t][:4]
        nt = max(len(tiles), 1)
        kw = (CONTENT_W - 0.2 * (nt - 1)) / nt
        strip_top = top + 2.75
        for i, (_kind, label, value, note) in enumerate(tiles):
            x = MARGIN_L + i * (kw + 0.2)
            # RPE (Sheila's 1798 slide review, 2026-10-30, slide 107): v5 set a line icon in the
            # card's corner, drawn in steel and orange; on the navy and orange cards it read as an
            # empty placeholder. The icon's colour is fixed in charts.icon, so the cards go without.
            _kpi(s, x, strip_top, kw, label, value, note,
                 accent=ORANGE if i == 0 else NAVY)
        _text(s, MARGIN_L + 0.02, 6.44, CONTENT_W, 0.3,
              "Where the control fell, the mailing's work was arresting "
                   "a decline \u2014 reported that way, every time.", size=FOOT_PT, color=GREY)
        _kicker(s)
    elif m.get("wb_found"):
        # the booked slot stayed empty on a client that HAS a workbook --
        # name the file, because the fix is on the file, not in the deck
        skip("The campaign hero",
             reason=(f"the booked frame is empty: workbook "
                     f"{m['wb_found']} did not read this run"))
    else:
        skip("The campaign hero", "counterfactual_gap_total")
    return None


def revenue_frames(h, m) -> str | None:
    """v5 build.py lines 2610-2658: Revenue frames."""
    (slide, skip, chart, n, register, divider, _title, _rail, _chart_left, _picture, _fit_picture,
     _kpi, _kpi_flat, _table, _text, _tile, _kicker, MARGIN_L, CONTENT_W, NAVY, ORANGE, GREY) = _v5(h, m)
    rf_pair = headlines.revenue_frames(m)
    if rf_pair:
        s, top = slide(rf_pair, "Revenue frames")
        ic_rate = m.get("segment_ic_rate")
        panel_w = (CONTENT_W - 0.9) / 2
        rx = MARGIN_L + panel_w + 0.9
        _text(s, MARGIN_L, top + 0.05, panel_w, 0.28,
              "BOOKED: ARS WORKBOOK LEDGER", size=11, bold=True, color=ORANGE,
              font=HEAD_FONT)
        _kpi_flat(s, MARGIN_L, top + 0.42, panel_w, "Program revenue",
                  _money(m.get("wb_revenue_ltd")), "life to date, gross")
        _kpi_flat(s, MARGIN_L, top + 1.62, panel_w, "Program profit",
                  _money(m.get("wb_profit_ltd")),
                  f"after {_money(abs(m.get('wb_costs_ltd') or 0))} fees")
        _text(s, MARGIN_L, top + 2.85, panel_w, 0.6,
              "All revenue types on goal-met responders, including NSF/OD "
              "fee income; includes spend the control would have produced.",
              size=FOOT_PT, color=GREY)
        _text(s, rx, top + 0.05, panel_w, 0.28,
              "INCREMENTAL: DiD ESTIMATE", size=11, bold=True, color=ORANGE,
              font=HEAD_FONT)
        _kpi_flat(s, rx, top + 0.42, panel_w, "Lift per responder",
                  f"{_money(m['ba_lift_net'])}/mo", "spend, net of control")
        if ic_rate:
            _kpi_flat(s, rx, top + 1.62, panel_w, "As interchange",
                      f"{_money(m['ba_lift_net'] * ic_rate)}/mo",
                      f"at a {ic_pct(ic_rate)} IC rate")
        _text(s, rx, top + 2.85, panel_w, 0.6,
              "Interchange only, a monthly run rate around each offer; "
              "credits nothing the control also did.",
              size=FOOT_PT, color=GREY)
        wedge_top = min(top + 3.55, 5.15)
        _text(s, MARGIN_L, wedge_top, CONTENT_W, 0.28,
              "Why they never tie", size=12, bold=True, font=HEAD_FONT)
        for i, line in enumerate([
                "Fee income sits only in the booked frame; DiD converts "
                "spend lift to interchange alone.",
                "Booked is gross; DiD subtracts the control, and part of "
                "each lift is decline arrested.",
                "Booked accumulates over the window; DiD is a run rate, "
                "and lift decays.",
                "Per-1,000-mailed pools every mailed account across "
                "offers; the ledger counts goal-met responders per offer."]):
            _text(s, MARGIN_L + 0.15, wedge_top + 0.32 + i * 0.30,
                  CONTENT_W - 0.3, 0.26, f"\u00b7  {line}", size=10.5,
                  color=GREY)
        _kicker(s)
    else:
        skip("Revenue frames", "wb_revenue_ltd + ba_lift_net")
    return None
