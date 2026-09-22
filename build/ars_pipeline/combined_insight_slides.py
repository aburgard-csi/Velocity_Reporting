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
import statistics
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
import branch_names as BN                                                 # noqa: E402

try:
    from textfit import text_width_in
except Exception:                                   # pragma: no cover
    text_width_in = None

TEAL_RGB, GOLD_RGB = _rgb(TEAL), _rgb(GOLD)
CAPTION_W_RAIL, CAPTION_W_FULL = 8.75, 10.6
BRANCH_TABLE_ROWS = 9          # branches shown before the roll-up row, at 16 pt rows
MIGRATION_W = CI.MIGRATION_WINDOW


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


def _notes(s, source, method=None, issues=(), caveats=()):
    """Write the slide's notes: source, how it is measured, then the open issues IN FULL.

    These views ship in a REVIEW deck, not to a client (Aaron, 2026-09-21: "you can be
    obvious about issues"), so anything known to be shaky is written on the slide's notes
    rather than kept in a commit message nobody opens next to the deck. A view with no open
    issue says so, because an empty section reads as "nobody looked".
    """
    parts = [f"Source: {source}"]
    if method:
        parts.append(f"Method: {method}")
    issues = [i for i in issues if i]
    if issues:
        parts.append("REVIEW — OPEN ISSUES:" + "".join("\n  !! " + i for i in issues))
    else:
        parts.append("REVIEW — OPEN ISSUES: none known. Figures and wording both derive "
                     "from the data on this slide.")
    if caveats:
        parts.append("Reading it: " + " ".join(caveats))
    s.notes_slide.notes_text_frame.text = "\n\n".join(parts)
    return s


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
    names, _src = scorecard_branch_names(ctx["id"], [b["branch"] for b in rows])
    lab = lambda n: names.get(n, n)
    IC.branch_kpi_chart(png, [(lab(b["branch"]), b["eligible"], b["take"], b["rege"]) for b in rows],
                        tot["take"], tot["rege"], 12.3, 4.15)
    _picture(s, png, 0.5, 1.7, 12.3, 4.15)
    t_at = sum(1 for b in rows if CI.band(b["take"], tot["take"]) != "behind")
    r_at = sum(1 for b in rows if CI.band(b["rege"], tot["rege"]) != "behind")
    t_low = [lab(b["branch"]) for b in rows if CI.band(b["take"], tot["take"]) == "behind"]
    r_low = [lab(b["branch"]) for b in rows if CI.band(b["rege"], tot["rege"]) == "behind"]
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


def scorecard_branch_names(client_id, numbers, rows=None):
    """({number: name}, {number: source}) for the scorecard, from Inputs/Branch Names.

    Aaron, 2026-09-17: "use Branch Names on the Branch Scorecard, but we also need to show the
    branch number here. This will help us translate branch numbers on other charts." Names are
    used only when most of the shown numbers resolve: a client whose ODD numbers branches
    differently from its Charts file and VIP (Texas Bay 1509) would otherwise get a name that
    matches by coincidence. Returns ({}, {}) then, and the table keeps numbers only.
    """
    try:
        rows = rows if rows is not None else BN.read_dataset()
    except Exception:
        return {}, {}
    names = BN.client_map(client_id, rows=rows)
    hit = {n: names[n] for n in numbers if n in names}
    if not numbers or len(hit) / len(numbers) < 0.5:
        return {}, {}
    src = {}
    for n, name in hit.items():
        for want in (BN.SRC_CHARTS, BN.SRC_REFERRALS):
            r = next((r for r in rows if r["client_id"] == str(client_id) and r["source"] == want
                      and BN._num(r["branch_number"]) == BN._num(n) and BN._same_name(r["branch_name"], name)), None)
            if r:
                src[n] = "%s (%s)" % (want, r["source_file"])
                break
    return hit, src


def branch_scorecard_slide(prs, ci, ctx):
    bk = ci["branch_kpis"]
    shown = bk["branches"][:BRANCH_TABLE_ROWS]
    names, name_src = scorecard_branch_names(ctx["id"], [b["branch"] for b in shown])
    rest = bk["branches"][BRANCH_TABLE_ROWS:] + ([bk["other"]] if bk.get("other") else [])
    s = _new_slide(prs, _find(prs, "Reg E Opt-In by Account Vintage"))
    cw, fy = bk["closure_window"], bk["first_year_window"]
    _header(s, "Branch Scorecard", f"{ctx['as_of_long']} Data", [
        f"Selection: personal accounts, {ctx['as_of_long']}; the {len(shown)} branches with the most eligible accounts.",
        f"Selection: personal accounts; the {len(shown)} branches with the most eligible accounts."])
    f = lambda v: "–" if v is None else f"{v:.1f}%"
    # With names: the number stays in its own column so the other branch charts, which print
    # numbers, can be read against this table.
    label = (lambda num, name: [num, name]) if names else (lambda num, name: [name or num])
    head = ["Branch #", "Branch"] if names else ["Branch"]
    data = [head + ["Eligible", "Take Rate", "Reg E Opt-In", "Closed, 12 Mo", "First-Year Closure"]]
    for b in shown:
        data.append(label(b["branch"], names.get(b["branch"], "–") if names else None)
                    + [f"{b['eligible']:,}", f(b["take"]), f(b["rege"]), f(b["closed12"]), f(b["first_year"])])
    if rest:
        n_rest = len(bk["branches"]) - len(shown) + bk.get("other_count", 0)
        o = CI.roll_up(f"All other branches ({n_rest})", rest)
        data.append(label("", o["branch"]) + [f"{o['eligible']:,}", f(o["take"]), f(o["rege"]),
                                            f(o["closed12"]), f(o["first_year"])])
    t = bk["total"]
    data.append(label("", "Total") + [f"{t['eligible']:,}", f(t["take"]), f(t["rege"]),
                                      f(t["closed12"]), f(t["first_year"])])
    rh = 0.40
    widths = ([1.15, 2.75, 1.35, 1.45, 1.7, 1.75, 2.15] if names
              else [3.0, 1.6, 1.7, 1.9, 2.0, 2.3])
    SH.add_table(s, 0.5, 1.72, 12.3, rh * len(data), data, widths,
                 highlight=(len(data) - 1,), fs=15 if names else 16)
    s.notes_slide.notes_text_frame.text = (
        f"Source: {ctx['odd_src']} — personal accounts (Business? = No) by Branch. Eligible = "
        f"'{ctx['latest']} Elig' = Yes. Take rate = eligible accounts holding a debit card / eligible. "
        f"Reg E opt-in = opted in / open personal debit-card holders. Closed, 12 Mo = personal "
        f"accounts with a Date Closed {cw[0]} – {cw[1]} / (open personal accounts + those closures). "
        f"First-year closure = accounts opened {fy[0]} – {fy[1]} that closed within 366 days of "
        f"opening (the First-Year Closure slide's cohort; a dash means the branch opened no "
        f"personal account in that window). Branches with fewer than {bk['min_eligible']} eligible "
        f"accounts are in the roll-up row with the branches not shown; the roll-up and Total are "
        f"recomputed from account counts, never averaged from branch rates. "
        + (("Branch names: Inputs/Branch Names/branch_names.csv — "
            + "; ".join(f"{n} {names[n]} from {name_src.get(n, 'the dataset')}" for n in names)
            + (". Not named: " + ", ".join(b["branch"] for b in shown if b["branch"] not in names)
               if any(b["branch"] not in names for b in shown) else "") + ".")
           if names else "Branch names: fewer than half of these branch numbers have a name in "
                         "Inputs/Branch Names/branch_names.csv, so the table shows numbers only."))
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
                     f"spend ({hk['at_risk_pct_of_carded']:.1f}%): {st['Declining'][1]:,} declining, "
                     f"{st['Cooling'][1]:,} cooling, {st['Dormant'][1]:,} dormant and "
                     f"{st['Never used'][1]:,} never used. Their spend was "
                     f"{usd_compact(hk['at_risk_prior_monthly_spend'], 1)} a month in {span(pw)}. "
                     f"Bar shares are of card holders; No card is of all "
                     f"{hk['eligible']:,} eligible accounts."))
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
            f"in {rw[0]} – {rw[1]}.")
    _notes(s, ctx["odd_src"], method=detail, issues=[
        "The 50% / 80% cut-offs between Cooling, Declining and Active are OURS. They were "
        "not checked against James's code, which has its own thresholds, so a state's "
        "population is not comparable to his figure for the same client.",
        "Seasonal spending moves accounts between Active and Declining with no change in "
        "behaviour: a client whose card spend peaks in December reads worse every January. "
        "No seasonal adjustment is applied.",
        "FIXED 2026-09-21 (was an open issue): the bars' shares were of every eligible "
        "account while the tile was of card holders. Card states are now shares of card "
        "holders and the No card bar says it is a share of eligible accounts.",
    ])
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
        _notes(s, f"{wb} — '{CI.ROLLUP_SHEET}'", method=detail, issues=[
            (f"The mailing rows sum to {usd_compact(wr['total'])} against "
             f"{usd_compact(ctx['ltd_revenue'])} program-to-date on Executive Financials MM "
             f"({100.0 * (wr['total'] - ctx['ltd_revenue']) / ctx['ltd_revenue']:+.1f}%). "
             "Reconcile before this goes anywhere near a client.")
            if ctx.get("ltd_revenue") else
            "No program-to-date revenue was passed in, so the mailing rows are not reconciled "
            "against Executive Financials MM.",
            "A mailing's revenue is what the WORKBOOK booked to it. Where two mailings overlap "
            "in a month, the split is the workbook's, not ours, and we do not re-derive it.",
            "FIXED 2026-09-21 (was an open issue): the per-month line ranked mailings with "
            f"1-5 booked months above mature ones. It now plots mailings with 6+ months only, "
            "which is what the caption always said.",
        ])
        _place(prs, s, after="Mailing Response Summary", before="Debit Card Review")
        return s
    _notes(s, f"ARS Workbook {ctx['id']} ({wb})", method=detail,
           issues=["The view is not available for this client, so nothing on this slide is "
                   "measured. " + str(wr.get("reason"))])
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


def wave_build_slide(prs, ci, ctx):
    """Each mailing's month-by-month build — James's slide 5, which we had no answer to."""
    wr = ci["wave_revenue"]
    s = _new_slide(prs, _find(prs, "Revenue by Mailing") or _find(prs, "Mailing Response Summary"))
    wb = wr.get("workbook") or ctx.get("wb_file") or "the ARS workbook"
    waves = [w for w in (wr.get("waves") or []) if w.get("build")]
    if not wr.get("available") or not waves:
        _header(s, "Revenue Build by Mailing", f"PTD · {ctx['data_month_short']}",
                "Selection: booked revenue by month since each mailing.")
        _caption(s, "The month-by-month build is not available for this client: "
                    f"{wr.get('reason', 'the workbook carries no mailing months')}.",
                 width=12.3, top=2.4, height=1.2)
        _notes(s, f"ARS Workbook {ctx['id']} ({wb})",
               issues=["Nothing on this slide is measured — the workbook carried no "
                       "month-by-month figures for any mailing."])
        _place(prs, s, after="Revenue by Mailing", before="Debit Card Review")
        return s

    _header(s, "Revenue Build by Mailing", f"PTD · {ctx['data_month_short']}", [
        f"Selection: cumulative booked revenue by month since each of the {len(waves)} mailings, "
        f"through {wr['through']}.",
        "Selection: cumulative booked revenue by month since each mailing."])
    png = os.path.join(ctx["assets"], "insight_wave_build.png")
    IC.wave_build_chart(png, waves, 12.3, 4.0)
    _picture(s, png, 0.5, 1.72, 12.3, 4.0)

    mature = [w for w in waves if w["months"] >= 6]

    def first6(w):
        """Share of a mailing's revenue booked within six months — the curve's shape in one
        number, derived from the points on the slide rather than asserted."""
        pts = [p for p in w["build"] if p[0] <= 6]
        return (pts[-1][2] / w["revenue"]) if pts and w["revenue"] else None

    shares = [f for f in (first6(w) for w in mature) if f is not None]
    newest = waves[-1]
    lead = max(mature, key=lambda w: w["revenue"]) if mature else newest
    cap = (f"{newest['m']} has booked {usd_compact(newest['revenue'])} over {newest['months']} "
           f"month{'s' if newest['months'] != 1 else ''}; {lead['m']} has booked the most of any "
           f"mailing with 6 or more months, {usd_compact(lead['revenue'])} over {lead['months']}.")
    if shares:
        med = statistics.median(shares) * 100
        cap += (f" Half of the mature mailings had booked {med:.0f}% or more of their revenue "
                f"within six months of the drop.")
    _caption(s, cap, width=CAPTION_W_FULL)

    _notes(s, f"ARS Workbook {ctx['id']} ({wb}) — '{CI.ROLLUP_SHEET}'",
           method=("Each '<Month Year> Mailing' block's Total Incremental Income row, read by "
                   "month and accumulated. The x axis is MONTHS SINCE THAT MAILING, computed "
                   "from the mailing's own month, so a month the workbook never booked leaves a "
                   "gap instead of pulling the curve left. The five most recent mailings are "
                   "coloured; earlier ones are the grey band."),
           issues=[
               "The curve is BOOKED revenue, which is the workbook's attribution of a month's "
               "income to a mailing. Where mailings overlap, that split is the workbook's and "
               "we do not re-derive it — two curves can therefore share the same dollar.",
               "A mailing's first point is its first BOOKED month, which is not always the "
               "month of the drop. Read the x axis as months since the mailing, not as the "
               "mailing's age in market.",
               "Curves are not adjusted for how many accounts each mailing reached, so a big "
               "drop and a small one sit on the same scale. Offers per mailing are on the "
               "Mailing Response Summary.",
           ])
    _place(prs, s, after="Revenue by Mailing", before="Debit Card Review")
    return s


def month_split_slide(prs, ci, ctx):
    """Where the newest month's revenue came from, by mailing — James's slide 6."""
    wr = ci["wave_revenue"]
    s = _new_slide(prs, _find(prs, "Revenue by Mailing") or _find(prs, "Mailing Response Summary"))
    wb = wr.get("workbook") or ctx.get("wb_file") or "the ARS workbook"
    rows = wr.get("by_mailing_latest") or []
    label = wr.get("latest_month_label")
    if not wr.get("available") or not rows:
        _header(s, "Where This Month's Revenue Came From", f"PTD · {ctx['data_month_short']}",
                "Selection: the newest booked month, split by mailing.")
        _caption(s, "The month's revenue cannot be split by mailing for this client: "
                    f"{wr.get('reason', 'no mailing booked a figure in the newest month')}.",
                 width=12.3, top=2.4, height=1.2)
        _notes(s, f"ARS Workbook {ctx['id']} ({wb})",
               issues=["Nothing on this slide is measured — no mailing booked revenue in the "
                       "newest month on the rollup sheet."])
        _place(prs, s, after="Revenue Build by Mailing", before="Debit Card Review")
        return s

    _header(s, "Where This Month's Revenue Came From", f"PTD · {ctx['data_month_short']}", [
        f"Selection: incremental revenue booked in {label}, by the mailing it is booked to.",
        f"Selection: revenue booked in {label}, by mailing."])
    png = os.path.join(ctx["assets"], "insight_month_split.png")
    IC.month_split_chart(png, rows, 12.3, 3.5)
    _picture(s, png, 0.5, 1.72, 12.3, 3.5)

    total = wr.get("latest_total") or 0.0
    top = rows[0]
    older = [r for r in rows if r[2] >= 12]
    tiles = [(usd_compact(total), f"Booked in {label}", ORANGE),
             (f"{len(rows)}", "Mailings still earning", NAVY),
             (f"{100.0 * sum(v for _m, v, n in older) / total:.0f}%" if total else "—",
              "From mailings 12+ months old", NAVY)]
    for i, (v, lab, fill) in enumerate(tiles):
        SH.shadow(SH.tile(s, 0.5 + i * 4.2, 5.35, 3.9, 1.0, v, lab, fill=fill))
    _caption(s, (f"{len(rows)} mailings booked revenue in {label}, {usd_compact(total)} together. "
                 f"The largest single contributor is the {top[0]} mailing at "
                 f"{usd_compact(top[1])} ({100.0 * top[1] / total:.0f}% of the month)."),
             width=CAPTION_W_FULL, top=6.45, height=0.7)

    rec = ""
    if wr.get("summary_latest"):
        gap = 100.0 * (total - wr["summary_latest"]) / wr["summary_latest"]
        rec = (f" The mailing rows sum to {usd_compact(total)} against "
               f"{usd_compact(wr['summary_latest'])} on the sheet's own Summary block "
               f"({gap:+.1f}%).")
    _notes(s, f"ARS Workbook {ctx['id']} ({wb}) — '{CI.ROLLUP_SHEET}'",
           method=(f"The newest month any mailing booked ({label}); each '<Month Year> Mailing' "
                   f"block's Total Incremental Income cell for that month, largest first. "
                   f"Bars are orange where the mailing has fewer than 6 booked months.{rec}"),
           issues=[
               f"{label} is the newest month the WORKBOOK has booked. It is not necessarily a "
               "complete month of activity, and it can be older than the ODD extract's month — "
               "check it against the cover month before reading it as 'this month'.",
               "The split is the workbook's attribution. A response booked to an older mailing "
               "may have been prompted by a newer one; nothing here can separate them.",
               "Mailings with no revenue booked in the month are absent from the chart rather "
               "than drawn at zero, so the bar count is 'mailings still earning', not all "
               "mailings the client has run.",
           ])
    _place(prs, s, after="Revenue Build by Mailing", before="Debit Card Review")
    return s


def _cut_slide(prs, ci, ctx, measure, title, after, before, png_name, subject, pool_word):
    """One rate, cut four ways, with the lagging pockets named. Shared by take rate and Reg E
    because the only differences are the measure, the population and the words."""
    rc = ci.get("rate_cuts") or {}
    s = _new_slide(prs, _find(prs, after) or prs.slides[0])
    book = rc.get("take_all" if measure == "take" else "rege_all")
    pool = rc.get("eligible" if measure == "take" else "rege_pool", 0)
    if not rc.get("available") or book is None:
        _header(s, title, f"{ctx['as_of_long']} Data", f"Selection: {subject}.")
        _caption(s, "This extract does not carry the columns the cuts need, so the view is "
                    "not shown for this period.", width=12.3, top=2.4, height=1.2)
        _notes(s, ctx["odd_src"], issues=["Nothing on this slide is measured — the extract "
                                          "carried no eligible population to cut."])
        _place(prs, s, after=after, before=before)
        return s

    _header(s, title, f"{ctx['as_of_long']} Data", [
        f"Selection: {subject} ({pool:,} {pool_word}), by tenure, age, balance and product.",
        f"Selection: {subject} ({pool:,} {pool_word})."])
    png = os.path.join(ctx["assets"], png_name)
    IC.cut_panel_chart(png, rc["cuts"], measure, book, 12.3, 3.9, rc.get("min_band", 25))
    _picture(s, png, 0.5, 1.68, 12.3, 3.9)

    lags = CI.lagging(rc, measure)
    tiles = [(f"{book:.1f}%", f"{'Take rate' if measure == 'take' else 'Opt-in'}, whole book",
              ORANGE)]
    for d in lags[:2]:
        tiles.append((f"{d['value']:.1f}%", _clip_label(f"{d['band']} ({d['cut'].lower()})"), NAVY))
    while len(tiles) < 3:
        tiles.append(("—", "No band below the book", NAVY))
    for i, (v, lab, fill) in enumerate(tiles):
        SH.shadow(SH.tile(s, 0.5 + i * 4.2, 5.70, 3.9, 0.95, v, lab, fill=fill))

    if lags:
        worst = lags[0]
        cap = (f"The widest gap is {worst['band'].lower()} ({worst['cut'].lower()}) at "
               f"{worst['value']:.1f}%, {abs(worst['gap']):.1f} points below the book's "
               f"{book:.1f}% across {worst['n']:,} {pool_word}.")
        if len(lags) > 1:
            cap += (" Then " + _and([f"{d['band'].lower()} ({abs(d['gap']):.1f} points)"
                                     for d in lags[1:]]) + ".")
    else:
        cap = (f"No band of {rc.get('min_band', 25)} accounts or more sits below the book's "
               f"{book:.1f}%.")
    _caption(s, cap, width=CAPTION_W_FULL, top=6.72, height=0.6)

    miss = rc.get("missing") or {}
    _notes(s, ctx["odd_src"],
           method=(f"{subject}. Bands are fixed, not quantiles: tenure from Date Opened, age "
                   f"from DOB, balance from Avg Bal, product from Prod Desc (the "
                   f"{CI.TOP_PRODUCTS} largest by population, the rest rolled into one row). "
                   f"Book rate {book:.1f}% over {pool:,} {pool_word}. A pocket is a band at "
                   f"least {rc.get('min_band', 25)} accounts wide, ranked by points below the "
                   f"book."),
           issues=[
               (f"Bands the extract could not place are shown as 'Not on file': "
                + ", ".join(f"{k} on {v:,} accounts" for k, v in sorted(miss.items()))
                + ". Those accounts are IN the book rate but cannot be attributed to a band, "
                  "so the bands do not sum to the book.") if miss else
               "Every account landed in a band on all four cuts.",
               "These are cross-sections at one snapshot, not causes. A product with a low "
               "rate may simply be sold at a branch that does not ask, and nothing here "
               "separates the two.",
               "The cuts are not independent: an older customer holds an older account and a "
               "larger balance, so the same pocket can appear three times under three names.",
               "Bands are ours, not James's. His cuts use his own boundaries, so a band's "
               "population is not comparable to his figure for the same client.",
           ])
    _place(prs, s, after=after, before=before)
    return s


def _clip_label(s, n=26):
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def take_cuts_slide(prs, ci, ctx):
    return _cut_slide(prs, ci, ctx, "take", "Where Take Rate Lags",
                      after="12-Month Eligible Take Rate", before="Reg E Review",
                      png_name="insight_take_cuts.png",
                      subject="ARS-eligible personal accounts",
                      pool_word="accounts")


def rege_cuts_slide(prs, ci, ctx):
    return _cut_slide(prs, ci, ctx, "rege", "Where Reg E Opt-In Lags",
                      after="Reg E Opt-In by Account Vintage",
                      before="Take Rate and Reg E Opt-In by Branch",
                      png_name="insight_rege_cuts.png",
                      subject="open personal accounts holding a debit card",
                      pool_word="card holders")


def migration_slide(prs, ci, ctx):
    """Where the book's card holders moved between swipe tiers over a year."""
    mig = ci.get("tier_migration") or {}
    s = _new_slide(prs, _find(prs, "Debit Usage Segmentation") or prs.slides[0])
    if not mig.get("available"):
        _header(s, "Swipe Tier Migration", f"{ctx['as_of_long']} Data",
                "Selection: ARS-eligible personal card holders.")
        _caption(s, f"This extract carries {mig.get('months', 0)} activity months; the migration "
                    f"view needs {mig.get('needs', 15)}, so it is not shown for this period.",
                 width=12.3, top=2.4, height=1.2)
        _notes(s, ctx["odd_src"], issues=["Nothing on this slide is measured — the extract is "
                                          "too short to compare two windows a year apart."])
        _place(prs, s, after="Debit Usage Segmentation", before="Average Ticket")
        return s

    _header(s, "Swipe Tier Migration", f"{ctx['as_of_long']} Data", [
        f"Selection: {mig['accounts']:,} ARS-eligible personal card holders, "
        f"{' to '.join(mig['then_window'])} against {' to '.join(mig['now_window'])}.",
        f"Selection: ARS-eligible personal card holders, a year apart."])
    png = os.path.join(ctx["assets"], "insight_migration.png")
    IC.migration_chart(png, mig, 8.0, 4.0)
    _picture(s, png, 0.5, 1.70, 8.0, 4.0)

    tiles = [(f"{mig['pct_up']:.0f}%", "Climbed a tier", ORANGE),
             (f"{mig['pct_down']:.0f}%", "Slipped a tier", NAVY),
             (f"${mig['spend_up']:,}" if mig["spend_up"] is not None else "—",
              "Monthly spend, climbers", NAVY)]
    for i, (v, lab, fill) in enumerate(tiles):
        SH.shadow(SH.tile(s, 8.9, 1.75 + i * 1.4, 3.9, 1.25, v, lab, fill=fill))

    gap = ""
    if mig["spend_up"] is not None and mig["spend_down"] is not None:
        gap = (f" Climbers now spend ${mig['spend_up']:,} a month against ${mig['spend_down']:,} "
               f"for accounts that slipped.")
    _caption(s, (f"{mig['moved_up']:,} of {mig['accounts']:,} card holders sit in a higher tier "
                 f"than a year ago and {mig['moved_down']:,} in a lower one; {mig['same']:,} "
                 f"have not moved.{gap}"), width=CAPTION_W_FULL)

    _notes(s, ctx["odd_src"],
           method=(f"ARS-eligible personal card holders at the snapshot. Each end is a "
                   f"{mig.get('span', 12)}-month-apart {MIGRATION_W}-month average of Sig # + PIN #, "
                   f"banded on the deck's own tiers. Rows are the tier a year ago, columns the "
                   f"tier now; the diagonal is bold. Spend figures are the average monthly "
                   f"Sig $ + PIN $ in the recent window."),
           issues=[
               "Only accounts open and eligible AT THE SNAPSHOT are in the matrix. Accounts "
               "closed during the year are not, so this reads better than the book actually "
               "did — attrition is on the Account Retention slides, not here.",
               "Tier boundaries are swipe counts, so a client whose customers spend more per "
               "swipe can slip tiers while spending more. Read it beside Average Ticket.",
               "A year apart is one comparison, not a trend: a seasonal book (tax refunds, "
               "tourism) can show migration that reverses next quarter.",
               "The window ends on the extract's last months, which may include an incomplete "
               "month. Nothing here applies the complete-month rule yet — that is the next "
               "thing to fix on this slide.",
           ])
    _place(prs, s, after="Debit Usage Segmentation", before="Average Ticket")
    return s


def routing_slide(prs, ci, ctx):
    """PIN versus signature — the mix, and what each rail's ticket looks like."""
    mix = ci.get("routing_mix") or {}
    s = _new_slide(prs, _find(prs, "Average Ticket") or prs.slides[0])
    if not mix.get("available"):
        _header(s, "PIN and Signature Mix", f"{ctx['as_of_long']} Data",
                "Selection: personal card holders' transactions.")
        _caption(s, "This extract carries no signature or PIN transactions to split, so the "
                    "view is not shown for this period.", width=12.3, top=2.4, height=1.2)
        _notes(s, ctx["odd_src"], issues=["Nothing on this slide is measured — no Sig # or "
                                          "PIN # columns carried a figure."])
        _place(prs, s, after="Average Ticket", before="Reg E Review")
        return s

    _header(s, "PIN and Signature Mix", f"{ctx['as_of_long']} Data", [
        f"Selection: personal card holders' transactions, {mix['window'][0]} to "
        f"{mix['window'][1]}.",
        f"Selection: personal card holders' transactions."])
    png = os.path.join(ctx["assets"], "insight_routing.png")
    IC.routing_chart(png, mix, 8.0, 4.0)
    _picture(s, png, 0.5, 1.70, 8.0, 4.0)

    tiles = [(f"{mix['pin_share']:.0f}%", "PIN share of swipes", ORANGE),
             (f"${mix['sig_ticket']:,.2f}", "Signature ticket", NAVY),
             (f"${mix['pin_ticket']:,.2f}", "PIN ticket", NAVY)]
    for i, (v, lab, fill) in enumerate(tiles):
        SH.shadow(SH.tile(s, 8.9, 1.75 + i * 1.4, 3.9, 1.25, v, lab, fill=fill))

    # A share moves in POINTS, and nobody at the client moved it: movement() would have
    # said "the mailings did not have an impact on the pin share of swipes", which is both
    # the wrong unit and the wrong subject.
    ch = mix["last_share"] - mix["first_share"]
    if abs(ch) <= CI.BAND_PCT:
        move = (f"It was almost flat across the window, {mix['first_share']:.1f}% to "
                f"{mix['last_share']:.1f}%")
    else:
        verb = "rose" if ch > 0 else "fell"
        move = (f"It {verb} from {mix['first_share']:.1f}% to {mix['last_share']:.1f}%, "
                f"{abs(ch):.1f} points")
    _caption(s, (f"{mix['pin_share']:.0f}% of swipes and {mix['pin_share_usd']:.0f}% of spend "
                 f"went over PIN across the window. {move}."),
             width=CAPTION_W_FULL)

    _notes(s, ctx["odd_src"],
           method=(f"Personal accounts holding a debit card. Per month: Sig # / Sig $ and "
                   f"PIN # / PIN $ summed across the book, {mix['window'][0]} to "
                   f"{mix['window'][1]}. Ticket = dollars / transactions on that rail. The "
                   f"line is PIN share of transaction COUNT; the spend share is in the "
                   f"caption because the two differ whenever the tickets differ."),
           issues=[
               "THE MIX IS NOT REVENUE. Signature and PIN earn different interchange, but the "
               "ODD carries no interchange rate and neither does this deck, so nothing here "
               "says what the mix is worth. Do not let the slide imply it.",
               "Routing is decided at the terminal by the merchant and the network, not by "
               "the client, so this is context for a conversation rather than something a "
               "branch can move.",
               "The window ends on the extract's last month, which may be incomplete; the "
               "final point can dip for that reason alone.",
               "James keeps this as a metric with interchange scenarios attached. Without his "
               "rate table, the scenarios are not reproduced here.",
           ])
    _place(prs, s, after="Average Ticket", before="Reg E Review")
    return s


def add_insight_slides(prs, ci, ctx):
    """Build and place all six. `ctx`: id, name, odd_src, wb_src, wb_file, latest ('Aug26'),
    as_of_long ('August 2026'), data_month, ltd_revenue, assets."""
    made = [
        wave_revenue_slide(prs, ci, ctx),
        wave_build_slide(prs, ci, ctx),
        month_split_slide(prs, ci, ctx),
        take_cuts_slide(prs, ci, ctx),
        rege_cuts_slide(prs, ci, ctx),
        migration_slide(prs, ci, ctx),
        routing_slide(prs, ci, ctx),
        responder_control_slide(prs, ci, ctx),
        health_slide(prs, ci, ctx),
        branch_kpi_slide(prs, ci, ctx),
        branch_scorecard_slide(prs, ci, ctx),
    ]
    if ci.get("scorecard"):
        made.append(scorecard_slide(prs, ci, ctx))
    return made
