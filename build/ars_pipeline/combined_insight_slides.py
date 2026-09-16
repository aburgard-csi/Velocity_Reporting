#!/usr/bin/env python3
"""
combined_insight_slides.py — inserts the test-branch "James views" into a built ARS deck.

TEST BRANCH (test/james-aaron-combined, 2026-09-16). OPT-IN ONLY: build_ars_gen calls this
when RPE_JAMES_SLIDES=1, so the default monthly build is unchanged. Six slides, each placed by
TITLE next to the section it extends, each with a source note naming this client's extract:

  Revenue by Mailing                      after Mailing Response Summary
  Responders vs Mailed Non-Responders     after Responder Activity: Before vs After by Offer
  Card Account Health                     after NSF/OD Activity Over Time
  Take Rate and Reg E Opt-In by Branch    after Reg E Opt-In by Account Vintage
  Branch Scorecard                        after Take Rate and Reg E Opt-In by Branch
  ARS Scorecard                           before ARS Key Takeaways

Every movement or comparison word in a caption is chosen from the figures printed beside it
(Aaron's +/-2% band, CLAUDE.md); a view whose data is absent says so on the slide.

Public entry point
------------------
    add_insight_slides(prs, ci, M, B, ctx) -> [slides]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, os.pardir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pptx.util import Inches, Pt                                          # noqa: E402
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR                           # noqa: E402
from pptx.enum.shapes import MSO_SHAPE                                    # noqa: E402

from brand import (NAVY_RGB as NAVY, ORANGE_RGB as ORANGE, TICK_RGB as GREYT,   # noqa: E402
                   WHITE_RGB as WHITE, HEAD, BODY, TEAL, GOLD, usd_compact, _rgb)
import shapes as SH                                                       # noqa: E402
import combined_insights as CI                                            # noqa: E402
import insight_charts as IC                                               # noqa: E402

try:
    from textfit import text_width_in
except Exception:                                   # pragma: no cover
    text_width_in = None

TEAL_RGB, GOLD_RGB = _rgb(TEAL), _rgb(GOLD)
CAPTION_W_RAIL, CAPTION_W_FULL = 8.75, 10.6
BRANCH_TABLE_ROWS = 9          # branches shown before the roll-up row, at 16 pt rows


# ----------------------------------------------------------------- slide plumbing
def _find(prs, title):
    return next((s for s in prs.slides if SH.slide_title(s).startswith(title)), None)


def _new_slide(prs, anchor):
    return SH.blank_slide(prs, anchor or prs.slides[0])


def _place(prs, slide, after=None, before=None):
    """Move `slide` directly after the slide titled `after` (or before `before`). Raises when
    neither anchor exists — a view that lands at the end of the deck is a silent defect."""
    lst = prs.slides._sldIdLst
    src = SH.sldid_of(prs, slide)
    if after:
        a = _find(prs, after)
        if a is not None and a is not slide:
            lst.remove(src)
            SH.sldid_of(prs, a).addnext(src)
            return
    if before:
        b = _find(prs, before)
        if b is not None and b is not slide:
            lst.remove(src)
            SH.sldid_of(prs, b).addprevious(src)
            return
    raise RuntimeError(f"insight slide: no anchor slide {after or before!r} to place it by")


def _one_line(candidates, width_in, pt=16):
    """The first wording that fits one line at `pt` Calibri in `width_in` (measured against the
    bundled TTF, never eyeballed); the last candidate otherwise."""
    for c in candidates:
        if text_width_in is None or text_width_in(c, pt, "Calibri") <= width_in - 0.2:
            return c
    return candidates[-1]


def _header(s, title, pill, selection):
    SH.textbox(s, 0.5, 0.28, 9.6, 0.9, title, 26, NAVY, True, PP_ALIGN.LEFT, HEAD, MSO_ANCHOR.MIDDLE)
    SH.pill(s, pill)
    sel = _one_line(selection if isinstance(selection, (list, tuple)) else [selection], 12.3)
    SH.textbox(s, 0.5, 1.12, 12.3, 0.5, sel, 16, GREYT, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)


def _caption(s, text, width=CAPTION_W_RAIL, top=5.95, height=0.95):
    SH.textbox(s, 0.5, top, width, height, text, 16, GREYT, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)


def _picture(s, png, L, T, W, H):
    s.shapes.add_picture(png, Inches(L), Inches(T), Inches(W), Inches(H))


def _money_mo(v):
    return ("+" if v >= 0 else "−") + f"${abs(v):,}/mo"


def _and(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _pct(a, b):
    return 100.0 * (b - a) / a if a else 0.0


# ----------------------------------------------------------------- wording
def movement(subject, before, after, unit_fmt="${:,}"):
    """One sentence clause on Aaron's band: almost flat / rose (with %) / did not have an impact."""
    b, a = unit_fmt.format(before), unit_fmt.format(after)
    ch = _pct(before, after)
    if abs(ch) <= CI.BAND_PCT:
        return f"{subject} was almost flat, {b} to {a}"
    if ch > 0:
        return f"{subject} rose from {b} to {a} (+{ch:.0f}%)"
    return f"the mailings did not have an impact on {subject.lower()}, {b} to {a}"


def control_movement(before, after):
    """The control group is not a program measure, so a fall is stated as a fall."""
    ch = _pct(before, after)
    if abs(ch) <= CI.BAND_PCT:
        return f"Mailed non-responders were almost flat, ${before:,} to ${after:,}"
    if ch > 0:
        return f"Mailed non-responders rose from ${before:,} to ${after:,} (+{ch:.0f}%)"
    return f"Mailed non-responders fell from ${before:,} to ${after:,} ({ch:.0f}%)".replace("-", "−")


# ----------------------------------------------------------------- the six slides
def responder_control_slide(prs, ci, ctx):
    rc = ci["responder_control"]
    anchor = _find(prs, "Responder Activity: Before vs After")
    s = _new_slide(prs, anchor)
    n = len(rc.get("mailings") or [])
    if not rc.get("available"):
        _header(s, "Responders vs Mailed Non-Responders", f"{ctx['as_of_long']} Data",
                "Selection: personal accounts mailed by the program, responders and non-responders.")
        _caption(s, "No mailing in this extract has the 3 months before and 6 months after it that "
                    "the comparison needs, so it is not shown for this period.",
                 width=12.3, top=2.4, height=1.2)
        note_detail = "No mailing had a full window on both sides."
    else:
        r, c = rc["responders"], rc["control"]
        span = f"{rc['mailings'][0]} to {rc['mailings'][-1]}"
        _header(s, "Responders vs Mailed Non-Responders", f"{ctx['as_of_long']} Data", [
            f"Selection: personal accounts mailed in the {n} mailings from {span}; 3 months before vs the 6 after.",
            f"Selection: personal accounts mailed in {n} mailings, {span}.",
        ])
        png = os.path.join(ctx["assets"], "insight_responder_control.png")
        IC.responder_control_chart(png, rc, 8.7, 4.1)
        _picture(s, png, 0.5, 1.72, 8.7, 4.1)
        tiles = [(_money_mo(r["change"]), "Responders, spend a month", ORANGE),
                 (_money_mo(c["change"]), "Non-responders, spend a month", NAVY),
                 (_money_mo(rc["did"]), "Difference per responder", NAVY)]
        for i, (v, lab, fill) in enumerate(tiles):
            SH.shadow(SH.tile(s, 9.5, 1.75 + i * 1.4, 3.3, 1.25, v, lab, fill=fill))
        first = movement("Responders' monthly debit spend", r["before"], r["after"])
        first = first[0].upper() + first[1:]
        diff = rc["did"]
        # Two sentences, never "X more than Y" beside the control's own pair: the claim checker
        # reads a comparison against the nearest figures, which would be the control's.
        second = (f"{control_movement(c['before'], c['after'])}. The difference between the two "
                  f"groups is {'+' if diff >= 0 else '−'}${abs(diff):,} a month per responder.")
        _caption(s, f"{first}. {second}")
        note_detail = (
            f"Responders: {r['n']:,} account-mailing observations, ${r['before']:,} before and "
            f"${r['after']:,} after — the same cohort, windows and winsorizing as the Responder "
            f"Activity slide. Mailed non-responders: {c['n']:,} observations (mailed that drop, goal "
            f"not met), ${c['before']:,} before and ${c['after']:,} after. Difference in differences "
            f"= (responder after − before) − (non-responder after − before) = {_money_mo(diff)}. "
            f"Tiles: pooled per-account means over the 3 months before and the 6 months after each "
            f"mailing (mail month excluded), each group winsorized at mean + 3 SD of its pooled "
            f"before and after means. Chart: pooled mean monthly spend at each month from the "
            f"mailing, each account-month capped at the group's cap (responders ${r['cap']:,}, "
            f"non-responders ${c['cap']:,}), indexed to the group's own 3-month pre-mailing mean. "
            f"Per mailing (mailed / responders / non-responders): "
            + "; ".join(f"{x['m']} {x['mailed']:,} / {x['responders']:,} / {x['control']:,}"
                        for x in rc["counts"]) + ".")
    s.notes_slide.notes_text_frame.text = (
        f"Source: {ctx['odd_src']} — '<Mon> Mail', '<Mon> Resp' and monthly Sig $ + PIN $ fields; "
        f"personal accounts. {note_detail}")
    _place(prs, s, after="Responder Activity: Before vs After by Offer",
           before="Debit Card Review")
    return s


def branch_kpi_slide(prs, ci, ctx):
    bk = ci["branch_kpis"]
    tot = bk["total"]
    rows = [b for b in bk["branches"] if b["take"] is not None and b["rege"] is not None][:CI.KPI_BRANCHES]
    s = _new_slide(prs, _find(prs, "Reg E Opt-In by Account Vintage"))
    _header(s, "Take Rate and Reg E Opt-In by Branch", f"{ctx['as_of_long']} Data", [
        f"Selection: the {len(rows)} branches with the most ARS-eligible personal accounts, {ctx['as_of_long']}.",
        f"Selection: the {len(rows)} largest branches by eligible personal accounts."])
    png = os.path.join(ctx["assets"], "insight_branch_kpi.png")
    IC.branch_kpi_chart(png, [(b["branch"], b["eligible"], b["take"], b["rege"]) for b in rows],
                        tot["take"], tot["rege"], 12.3, 4.15)
    _picture(s, png, 0.5, 1.7, 12.3, 4.15)
    t_at = sum(1 for b in rows if CI.band(b["take"], tot["take"]) != "behind")
    r_at = sum(1 for b in rows if CI.band(b["rege"], tot["rege"]) != "behind")
    t_low = [b["branch"] for b in rows if CI.band(b["take"], tot["take"]) == "behind"]
    r_low = [b["branch"] for b in rows if CI.band(b["rege"], tot["rege"]) == "behind"]
    _caption(s, (f"Take rate is within 2% of the {tot['take']:.1f}% all-eligible rate or ahead of it "
                 f"at {t_at} of the {len(rows)} branches; Reg E opt-in is at {r_at} of {len(rows)} "
                 f"against {tot['rege']:.1f}%."
                 + (f" Branches behind on opt-in: {', '.join(r_low)}." if r_low else "")),
             width=CAPTION_W_FULL, top=5.95, height=0.95)
    s.notes_slide.notes_text_frame.text = (
        f"Source: {ctx['odd_src']} — Branch, Business?, Debit?, '{ctx['latest']} Elig', Stat Desc / "
        f"Stat Code and '{ctx['latest']} Reg E Desc'. Take rate = ARS-eligible personal accounts "
        f"holding a debit card / ARS-eligible personal accounts (the Program Overview definition; "
        f"all branches {tot['take']:.1f}%). Reg E opt-in = opted in / open personal debit-card "
        f"holders, election read by odd_rows.rege_label (all branches {tot['rege']:.1f}%). Branches "
        f"shown: the {len(rows)} with the most eligible accounts. 'Within 2%' is Aaron's band: a "
        f"branch rate within 2% of the program rate, relative. Behind on take rate: "
        f"{', '.join(t_low) or 'none'}; behind on opt-in: {', '.join(r_low) or 'none'}.")
    _place(prs, s, after="Reg E Opt-In by Account Vintage", before="ARS Key Takeaways")
    return s


def branch_scorecard_slide(prs, ci, ctx):
    bk = ci["branch_kpis"]
    shown = bk["branches"][:BRANCH_TABLE_ROWS]
    rest = bk["branches"][BRANCH_TABLE_ROWS:] + ([bk["other"]] if bk.get("other") else [])
    s = _new_slide(prs, _find(prs, "Reg E Opt-In by Account Vintage"))
    cw, fy = bk["closure_window"], bk["first_year_window"]
    _header(s, "Branch Scorecard", f"{ctx['as_of_long']} Data", [
        f"Selection: personal accounts, {ctx['as_of_long']}; the {len(shown)} branches with the most eligible accounts.",
        f"Selection: personal accounts; the {len(shown)} branches with the most eligible accounts."])
    f = lambda v: "–" if v is None else f"{v:.1f}%"
    data = [["Branch", "Eligible", "Take Rate", "Reg E Opt-In", "Closed, 12 Mo", "First-Year Closure"]]
    for b in shown:
        data.append([b["branch"], f"{b['eligible']:,}", f(b["take"]), f(b["rege"]),
                     f(b["closed12"]), f(b["first_year"])])
    if rest:
        n_rest = len(bk["branches"]) - len(shown) + bk.get("other_count", 0)
        o = CI.roll_up(f"All other branches ({n_rest})", rest)
        data.append([o["branch"], f"{o['eligible']:,}", f(o["take"]), f(o["rege"]),
                     f(o["closed12"]), f(o["first_year"])])
    t = bk["total"]
    data.append(["Total", f"{t['eligible']:,}", f(t["take"]), f(t["rege"]), f(t["closed12"]),
                 f(t["first_year"])])
    rh = 0.40
    SH.add_table(s, 0.5, 1.72, 12.3, rh * len(data), data, [3.0, 1.6, 1.7, 1.9, 2.0, 2.3],
                 highlight=(len(data) - 1,), fs=16)
    s.notes_slide.notes_text_frame.text = (
        f"Source: {ctx['odd_src']} — personal accounts (Business? = No) by Branch. Eligible = "
        f"'{ctx['latest']} Elig' = Yes. Take rate = eligible accounts holding a debit card / eligible. "
        f"Reg E opt-in = opted in / open personal debit-card holders. Closed, 12 Mo = personal "
        f"accounts with a Date Closed {cw[0]} – {cw[1]} / (open personal accounts + those closures). "
        f"First-year closure = accounts opened {fy[0]} – {fy[1]} that closed within 366 days of "
        f"opening (the First-Year Closure slide's cohort; a dash means the branch opened no "
        f"personal account in that window). Branches with fewer than {bk['min_eligible']} eligible "
        f"accounts are in the roll-up row with the branches not shown; the roll-up and Total are "
        f"recomputed from account counts, never averaged from branch rates.")
    _place(prs, s, after="Take Rate and Reg E Opt-In by Branch", before="ARS Key Takeaways")
    return s


def health_slide(prs, ci, ctx):
    hk = ci["account_health"]
    s = _new_slide(prs, _find(prs, "NSF/OD Activity"))
    if not hk.get("available"):
        _header(s, "Card Account Health", f"{ctx['as_of_long']} Data",
                "Selection: ARS-eligible personal accounts.")
        _caption(s, f"This extract carries {hk.get('months', 0)} months of card activity; the health "
                    f"view needs 6, so it is not shown for this period.", width=12.3, top=2.4, height=1.2)
        detail = "Fewer than 6 activity months."
    else:
        rw, pw = hk["recent_window"], hk["prior_window"]
        span = lambda w: f"{w[0].split()[0]}–{w[1]}"
        _header(s, "Card Account Health", f"{ctx['as_of_long']} Data", [
            f"Selection: ARS-eligible personal accounts ({hk['eligible']:,}); card spend {span(rw)} vs {span(pw)}.",
            f"Selection: ARS-eligible personal accounts ({hk['eligible']:,})."])
        png = os.path.join(ctx["assets"], "insight_health.png")
        IC.health_chart(png, hk["states"], 8.7, 4.1)
        _picture(s, png, 0.5, 1.72, 8.7, 4.1)
        st = {x[0]: x for x in hk["states"]}
        tiles = [(f"{hk['at_risk_pct_of_carded']:.1f}%", "Card holders at risk", ORANGE),
                 (f"{hk['at_risk']:,}", "Accounts at risk", NAVY),
                 (usd_compact(hk["at_risk_recent_monthly_spend"], 1), "Their card spend a month", NAVY)]
        for i, (v, lab, fill) in enumerate(tiles):
            SH.shadow(SH.tile(s, 9.5, 1.75 + i * 1.4, 3.3, 1.25, v, lab, fill=fill))
        _caption(s, (f"Of {hk['carded']:,} card holders, {hk['at_risk']:,} show falling or no card "
                     f"spend: {st['Declining'][1]:,} declining, {st['Cooling'][1]:,} cooling, "
                     f"{st['Dormant'][1]:,} dormant and {st['Never used'][1]:,} never used. Their "
                     f"spend was {usd_compact(hk['at_risk_prior_monthly_spend'], 1)} a month in "
                     f"{span(pw)}."))
        detail = (
            f"ARS-eligible personal accounts ('{ctx['latest']} Elig' = Yes, Business? = No): "
            f"{hk['eligible']:,}, of which {hk['carded']:,} hold a debit card. Monthly card spend = "
            f"Sig $ + PIN $. States, in order of precedence: No card (Debit? not Yes); Never used "
            f"(no card spend in any of the {hk['months']} months in the extract); Dormant (no spend "
            f"in each of {rw[0]} – {rw[1]}); Cooling (average spend {rw[0]} – {rw[1]} below 50% of "
            f"{pw[0]} – {pw[1]}); Declining (below 80%); Active (everything else). Ratios, not "
            f"dollar amounts, so the state means the same at every spend level. At risk = declining + "
            f"cooling + dormant + never used; their card spend {usd_compact(hk['at_risk_prior_monthly_spend'], 1)} "
            f"a month in {pw[0]} – {pw[1]} and {usd_compact(hk['at_risk_recent_monthly_spend'], 1)} "
            f"in {rw[0]} – {rw[1]}. Seasonal spending moves accounts between Active and Declining.")
    s.notes_slide.notes_text_frame.text = f"Source: {ctx['odd_src']} — {detail}"
    _place(prs, s, after="NSF/OD Activity", before="Reg E Review")
    return s


def wave_revenue_slide(prs, ci, ctx):
    wr = ci["wave_revenue"]
    s = _new_slide(prs, _find(prs, "Mailing Response Summary"))
    wb = wr.get("workbook") or ctx.get("wb_file") or "the ARS workbook"
    if not wr.get("available"):
        _header(s, "Revenue by Mailing", f"PTD · {ctx['data_month_short']}",
                "Selection: incremental revenue booked to each mailing.")
        _caption(s, f"Revenue by mailing is not available for this client: {wr.get('reason')}.",
                 width=12.3, top=2.4, height=1.2)
        detail = f"Not available: {wr.get('reason')}."
    else:
        waves = wr["waves"]
        # short month: "PTD · August 2026" wraps in the 2.35in pill at 16 pt (validate_deck REVIEW)
        _header(s, "Revenue by Mailing", f"PTD · {ctx['data_month_short']}", [
            f"Selection: incremental revenue booked to each of the {len(waves)} mailings, through {wr['through']}.",
            f"Selection: revenue booked to each mailing, through {wr['through']}."])
        png = os.path.join(ctx["assets"], "insight_wave_revenue.png")
        IC.wave_revenue_chart(png, waves, 12.3, 4.1)
        _picture(s, png, 0.5, 1.7, 12.3, 4.1)
        mature = [w for w in waves if w["months"] >= 6]
        lead = max(mature or waves, key=lambda w: w["per_month"])
        young = [w for w in waves if w["months"] < 6]
        _caption(s, (f"The {len(waves)} mailings have booked {usd_compact(wr['total'])} in incremental "
                     f"revenue through {wr['through']}. Among mailings with 6 or more months booked, "
                     f"{lead['m']} books the most per month, {usd_compact(lead['per_month'])} over "
                     f"{lead['months']} months"
                     + (f"; {_and([w['m'] for w in young])} "
                        f"{'is' if len(young) == 1 else 'are'} still accruing." if young else ".")),
                 width=CAPTION_W_FULL)
        ltd = ctx.get("ltd_revenue")
        rec = ""
        if ltd:
            gap = 100.0 * (wr["total"] - ltd) / ltd
            rec = (f" The mailing rows sum to {usd_compact(wr['total'])} against "
                   f"{usd_compact(ltd)} LTD incremental revenue on Executive Financials MM "
                   f"({gap:+.1f}%).")
        detail = (f"'{CI.ROLLUP_SHEET}' sheet, the Total Incremental Income row of each "
                  f"'<Month Year> Mailing' block, summed over every month booked; months not yet "
                  f"booked are absent, not zero. Per month booked = booked to date / months with a "
                  f"booked figure. Summary block total {usd_compact(wr['summary_total'] or 0)}.{rec} "
                  "Newer mailings carry fewer, earlier months, and revenue per responder is "
                  "typically highest in the first months, so per-month figures favour young mailings.")
    s.notes_slide.notes_text_frame.text = f"Source: ARS Workbook {ctx['id']} ({wb}) — {detail}"
    _place(prs, s, after="Mailing Response Summary", before="Debit Card Review")
    return s


STATUS = {"ahead": ("▲  Ahead", TEAL_RGB, WHITE), "level": ("◆  Within 2%", GOLD_RGB, NAVY),
          "behind": ("▼  Behind", ORANGE, WHITE)}


def scorecard_slide(prs, ci, ctx):
    rows = ci.get("scorecard") or []
    s = _new_slide(prs, _find(prs, "ARS Key Takeaways"))
    _header(s, "ARS Scorecard", f"{ctx['as_of_long']} Data", [
        "Selection: each measure against its own comparator; within 2% either way counts as level.",
        "Selection: each measure against its own comparator."])
    rh = 0.44
    data = [["Measure", "Value", "Compared with"]] + [[m, v, c] for m, v, c, _ in rows]
    top = 1.72
    SH.add_table(s, 2.55, top, 10.25, rh * len(data), data, [4.6, 1.75, 3.9], fs=16)
    for i, (_, _, _, state) in enumerate(rows, 1):
        label, fill, ink = STATUS[state]
        chip = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.5),
                                  Inches(top + i * rh + 0.05), Inches(1.9), Inches(rh - 0.10))
        chip.fill.solid(); chip.fill.fore_color.rgb = fill; chip.line.fill.background()
        tf = chip.text_frame; tf.margin_top = tf.margin_bottom = 0
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = label
        r.font.name = HEAD; r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = ink
        SH.shadow(chip)
    n = {k: sum(1 for x in rows if x[3] == k) for k in STATUS}
    _caption(s, f"{n['ahead']} of {len(rows)} measures ahead of their comparator, {n['level']} within "
                f"2% and {n['behind']} behind.", width=CAPTION_W_FULL, top=top + rh * len(data) + 0.12,
             height=0.45)
    s.notes_slide.notes_text_frame.text = (
        f"Source: {ctx['odd_src']}; {ctx['wb_src']} (Executive Financials MM profitability, "
        f"Swipe/Spend history); figures as shown elsewhere in this deck. Status: ahead / behind "
        f"when the value differs from its comparator by more than 2% of the comparator, else level "
        f"(Aaron's +/-2% band); for a change measured against zero the band is 2% of the baseline "
        f"(the non-responders' before spend for the responder difference, 2 points for a % change); "
        f"for first-year closure lower is better. Rows: "
        + "; ".join(f"{m}: {v} vs {c} ({st})" for m, v, c, st in rows) + ".")
    _place(prs, s, before="ARS Key Takeaways")
    return s


def add_insight_slides(prs, ci, ctx):
    """Build and place all six. `ctx`: id, name, odd_src, wb_src, wb_file, latest ('Aug26'),
    as_of_long ('August 2026'), data_month, ltd_revenue, assets."""
    made = [
        wave_revenue_slide(prs, ci, ctx),
        responder_control_slide(prs, ci, ctx),
        health_slide(prs, ci, ctx),
        branch_kpi_slide(prs, ci, ctx),
        branch_scorecard_slide(prs, ci, ctx),
    ]
    if ci.get("scorecard"):
        made.append(scorecard_slide(prs, ci, ctx))
    return made
