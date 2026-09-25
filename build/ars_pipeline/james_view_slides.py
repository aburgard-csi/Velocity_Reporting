#!/usr/bin/env python3
"""
james_view_slides.py — inserts the second round of James views (james_views.py) into a built
ARS deck. OPT-IN: combined_insight_slides.add_insight_slides calls add_more_slides, and that
runs only under RPE_JAMES_SLIDES=1.

Aaron, 2026-09-25: "add in as many as possible and then we'll edit down from the maximized
copy." These are REVIEW slides in the same sense as the first round: the speaker notes carry
the source, the method and the open issues in full (combined_insight_slides._notes), the slide
face carries figures and a caption whose words are chosen from those figures, and a view whose
data is absent says so on the slide rather than drawing zeros.

Every slide is placed by TITLE next to the section it extends; an anchor that is missing
raises (combined_insight_slides._place) rather than dropping the slide at the end of the deck.

Public entry point
------------------
    add_more_slides(prs, ci, ctx) -> [slides]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, os.pardir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from brand import NAVY_RGB as NAVY, ORANGE_RGB as ORANGE, usd_compact   # noqa: E402
import shapes as SH                                                       # noqa: E402
import combined_insight_slides as CIS                                     # noqa: E402
import james_views as JV                                                  # noqa: E402
import james_view_charts as JC                                            # noqa: E402

W_FULL = CIS.CAPTION_W_FULL


def _pill(ctx):
    return f"{ctx['as_of_long']} Data"


def _unavailable(prs, ctx, title, selection, reason, anchor_after, before=None, source=None):
    """The stated-not-zeroed slide: title, selection, one plain sentence, and the reason in the
    notes. The slide is kept so the gap is visible when the deck is edited down."""
    s = CIS._new_slide(prs, CIS._find(prs, anchor_after) or prs.slides[0])
    CIS._header(s, title, _pill(ctx), selection)
    CIS._caption(s, f"Not shown for this period: {reason}.", width=12.3, top=2.4, height=1.2)
    CIS._notes(s, source or ctx["odd_src"],
               issues=[f"Nothing on this slide is measured — {reason}."])
    CIS._place(prs, s, after=anchor_after, before=before)
    return s


def _tiles_rail(s, tiles, top=1.75, step=1.4, left=8.9, w=3.9, h=1.25):
    for i, (v, lab, fill) in enumerate(tiles):
        SH.shadow(SH.tile(s, left, top + i * step, w, h, v, lab, fill=fill))


def _tiles_row(s, tiles, top=5.3, h=0.95):
    for i, (v, lab, fill) in enumerate(tiles):
        SH.shadow(SH.tile(s, 0.5 + i * 4.2, top, 3.9, h, v, lab, fill=fill))


def _branch_label(ctx, numbers):
    names, _src = CIS.scorecard_branch_names(ctx["id"], numbers)
    return lambda n: (f"{n} {names[n]}" if names.get(n) and names[n] != n else str(n))


def _signed(v):
    return ("+" if v >= 0 else "−") + f"${abs(v):,}"


# ============================================================== revenue per fee dollar
def pnl_slide(prs, ci, ctx):
    more = ci["more"]
    p = more["mailing_pnl"]
    after = "Where This Month's Revenue Came From"
    src = f"ARS Workbook {ctx['id']} ({ctx['wb_file']}) — '{JV.ROLLUP_SHEET}'"
    if not p.get("available"):
        return _unavailable(prs, ctx, "Revenue per Fee Dollar by Mailing",
                            "Selection: each mailing's booked revenue against its fees.",
                            p.get("reason", "the workbook rollup is not available"), after,
                            before="Debit Card Review", source=src)
    rows = p["mailings"]
    s = CIS._new_slide(prs, CIS._find(prs, after))
    CIS._header(s, "Revenue per Fee Dollar by Mailing", f"PTD · {ctx['data_month_short']}", [
        f"Selection: {CIS._n(len(rows), 'mailing')}, booked revenue to date against the "
        f"respondent fees billed for each.",
        "Selection: booked revenue against fees, per mailing."])
    png = os.path.join(ctx["assets"], "james_pnl.png")
    JC.pnl_chart(png, rows, 12.3, 3.5)
    CIS._picture(s, png, 0.5, 1.70, 12.3, 3.5)
    _tiles_row(s, [(f"${p['per_fee_dollar']:,.2f}" if p["per_fee_dollar"] else "—",
                    "Booked per fee dollar, all", ORANGE),
                   (usd_compact(p["income"]), "Booked, all mailings", NAVY),
                   (f"${p['per_responder']:,.0f}" if p["per_responder"] else "—",
                    "Booked per responder", NAVY)], top=5.3)
    billed = [r for r in rows if r["per_fee_dollar"] is not None]
    lo = min(billed, key=lambda r: r["per_fee_dollar"]) if billed else None
    under = [r["m"] for r in billed if r["per_fee_dollar"] < 2.0]
    cap = (f"Across {CIS._n(len(rows), 'mailing')} the workbook books "
           f"{usd_compact(p['income'])} against {usd_compact(p['fees'])} in respondent fees, "
           f"${p['per_fee_dollar']:,.2f} per fee dollar.")
    if under:
        cap += (f" {CIS._n(len(under), 'mailing')} sit below 2 : 1 so far: "
                f"{CIS._and(under[:4])}{' and others' if len(under) > 4 else ''}.")
    elif lo:
        cap += f" Every billed mailing is at or above 2 : 1; the lowest is {lo['m']} at ${lo['per_fee_dollar']:,.2f}."
    CIS._caption(s, cap, width=W_FULL, top=6.35, height=0.9)
    CIS._notes(s, src,
               method=("Per '<Month Year> Mailing' block: Total Incremental Income summed across "
                       "every booked month = booked revenue to date; Total Incremental Expense "
                       "summed = the respondent fees billed (the sheet books them in the month "
                       "after the drop); Number of Responders summed = the responders billed. "
                       "Per fee dollar = income / fees. Dashed line = 2 : 1. Bars at or above the "
                       "median are orange."),
               issues=[
                   "AGE FAVOURS OLD MAILINGS. Income keeps booking for years while the fee is "
                   "billed once, so a recent mailing's ratio is young, not weak.",
                   (f"Mailings with no fee booked, left off the chart: {', '.join(p['unbilled'])}. "
                    "They may be too recent to have been billed.") if p.get("unbilled") else "",
                   "The workbook's attribution: where mailings overlap, revenue is split by the "
                   "sheet's own rules, not measured here.",
                   "James's P&L by offer also carries the deferral tracker (fees deferred while "
                   "under 2 : 1). That tracker is not on the share, so this is fees BILLED.",
               ])
    CIS._place(prs, s, after=after, before="Debit Card Review")
    return s


# ============================================================== offer segments
def segments_slide(prs, ci, ctx):
    seg = ci["more"]["offer_segments"]
    after = "Mailing Response Ranking by Tier"
    if not seg.get("available"):
        return _unavailable(prs, ctx, "Offer Segments per 1,000 Mailed",
                            "Selection: mailed personal accounts, by offer segment.",
                            "no mailing had a full window before and after it", after)
    rows = seg["segments"]
    s = CIS._new_slide(prs, CIS._find(prs, after))
    CIS._header(s, "Offer Segments per 1,000 Mailed", _pill(ctx), [
        f"Selection: personal accounts offered in {CIS._n(len(seg['mailings']), 'mailing')}, "
        f"{seg['mailings'][0]} to {seg['mailings'][-1]}, by offer segment.",
        "Selection: mailed personal accounts, by offer segment."])
    ic = seg.get("ic_rate")
    head = ["Offer segment", "Offered", "Met goal", "Response", "Spend change, net",
            "Net spend per 1,000 offers"] + (["Interchange per 1,000"] if ic else [])
    data = [head]
    for r in rows:
        row = [r["segment"], f"{r['mailed']:,}", f"{r['responded']:,}",
               f"{r['rate']:.1f}%" if r["rate"] is not None else "—",
               (_signed(r["did"]) + "/mo") if r["did"] is not None else "too few",
               (f"${r['did_per_1k']:,}/mo") if r["did_per_1k"] is not None else "—"]
        if ic:
            row.append(f"${r['ic_per_1k']:,}/mo" if r["ic_per_1k"] is not None else "—")
        data.append(row)
    widths = [1.6, 1.3, 1.3, 1.2, 1.9, 2.4] + ([2.2] if ic else [])
    SH.add_table(s, 0.5, 1.75, 12.3, 0.48 * len(data), data, widths, fs=13)
    measured = [r for r in rows if r["did_per_1k"] is not None]
    if measured:
        hi = max(measured, key=lambda r: r["did_per_1k"])
        lo = min(measured, key=lambda r: r["did_per_1k"])
        cap = (f"{hi['segment']} returns ${hi['did_per_1k']:,} a month in net spend per 1,000 "
               f"offers against ${lo['did_per_1k']:,} for {lo['segment']}; response runs "
               f"{hi['rate']:.1f}% against {lo['rate']:.1f}%, and the net change per responder "
               f"is {_signed(hi['did'])} against {_signed(lo['did'])}.")
    else:
        cap = "No segment had enough responders and non-responders to compare."
    CIS._caption(s, cap, width=W_FULL, top=5.6, height=1.2)
    CIS._notes(s, ctx["odd_src"] + (f"; interchange rate {ic:.2%} from {ctx['wb_src']}" if ic else ""),
               method=(f"Segment = the '<Mon> Mail' code on the account for that mailing. Pooled "
                       f"over {', '.join(seg['mailings'])}: offered = accounts carrying the code, "
                       f"met goal = '<Mon> Resp' in the program's met-goal codes. Net spend "
                       f"change per responder = (responder after − before) − (same segment's "
                       f"mailed non-responder after − before), {seg['before_months']} months "
                       f"before and {seg['after_months']} after, winsorized as before_after "
                       f"does. Per 1,000 offers = net change x responders / offered x 1,000."
                       + (" Interchange per 1,000 = that spend x the workbook's interchange rate."
                          if ic else "")),
               issues=[
                   "RESPONDERS SELECT THEMSELVES, within a segment as much as across the book.",
                   "Segments are not comparable populations: a TH-25 offer goes to accounts "
                   "already swiping, so its response rate says as much about who got it as "
                   "about the offer.",
                   "Interchange is spend x one blended rate; signature and PIN earn different "
                   "rates and this pipeline has no per-rail table." if ic else
                   "No interchange column: the workbook carries no Interchange Rate.",
               ])
    CIS._place(prs, s, after=after, before="Debit Card Review")
    return s


# ============================================================== response by offer number
def offer_number_slide(prs, ci, ctx):
    rr = ci["more"]["repeat_responses"]
    after = "Offer Segments per 1,000 Mailed"
    if not rr.get("available"):
        return _unavailable(prs, ctx, "Response by Offer Number",
                            "Selection: mailed personal accounts.",
                            rr.get("reason", "no mailing has a met goal"), after)
    s = CIS._new_slide(prs, CIS._find(prs, after))
    n = len(rr["mailings"])
    CIS._header(s, "Response by Offer Number", _pill(ctx), [
        f"Selection: personal accounts offered in the {CIS._n(n, 'mailing')} this extract "
        f"carries, by how many offers the account had received.",
        "Selection: mailed personal accounts, by offer number."])
    png = os.path.join(ctx["assets"], "james_offer_number.png")
    JC.offer_number_chart(png, rr["by_offer_number"], 8.0, 4.0)
    CIS._picture(s, png, 0.5, 1.70, 8.0, 4.0)
    mv = rr["moves"]
    _tiles_rail(s, [(f"{rr['repeat_pct']:.0f}%", "Of met goals were repeats", ORANGE),
                    (f"{rr['moved_up_pct']:.0f}%" if rr["moved_up_pct"] is not None else "—",
                     "Repeats that climbed a rung", NAVY),
                    (f"{rr['first_time']:,}", "First-time met goals", NAVY)])
    b = rr["by_offer_number"]
    cap = (f"First offers met the goal at {b[0]['rate']:.1f}% and offer {b[-1]['n']} at "
           f"{b[-1]['rate']:.1f}%. {rr['repeat']:,} of {rr['first_time'] + rr['repeat']:,} met "
           f"goals came from accounts that had met one before; {mv['Up']:,} of those climbed to "
           f"a higher goal than their best before.")
    CIS._caption(s, cap, width=W_FULL)
    CIS._notes(s, ctx["odd_src"],
               method=("For every personal account, the mailings are walked oldest first. Offer "
                       "number = how many offers the account had received including this one "
                       "(5 and later pooled). A met goal is '<Mon> Resp' in NU 5+ / TH-10 / "
                       "TH-15 / TH-20 / TH-25; NU 1-4 is a partial and is not counted. A repeat "
                       "is a met goal on an account with an earlier met goal in this extract. "
                       "Rung: NU 5+ < TH-10 < TH-15 < TH-20 < TH-25, compared with the "
                       "account's best earlier rung. Per mailing: "
                       + "; ".join(f"{x['m']} {x['mailed']:,} offered / {x['resp']:,} met "
                                   f"({x['repeat']:,} repeat)" for x in rr["mailings"]) + "."),
               issues=[
                   "The extract starts in the middle of the program. A 'first' met goal here "
                   "can be a repeat of one before the extract's first month, so repeats are "
                   "UNDER-counted and offer numbers start from the extract, not the program.",
                   "Offer number and account are tangled: accounts offered five times are the "
                   "ones that kept qualifying, so the falling rate is part fatigue and part "
                   "selection. Nothing here separates the two.",
                   "James also shows a 'penalty box' (a tier repeated inside the suppression "
                   "window). The suppression rule is not in any file this pipeline reads, so "
                   "that view is not built.",
               ])
    CIS._place(prs, s, after=after, before="Debit Card Review")
    return s


# ============================================================== per-mailing control
def per_mailing_slide(prs, ci, ctx):
    pm = ci["more"]["per_mailing_control"]
    after = "Responders vs Their Own Segment"
    if not pm.get("available"):
        return _unavailable(prs, ctx, "Responders vs Non-Responders by Mailing",
                            "Selection: personal accounts mailed by the program.",
                            "no mailing had a full window before and after it", after,
                            before="Debit Card Review")
    rows = [r for r in pm["mailings"] if not r["thin"]]
    s = CIS._new_slide(prs, CIS._find(prs, after))
    CIS._header(s, "Responders vs Non-Responders by Mailing", _pill(ctx), [
        f"Selection: personal accounts mailed in {CIS._n(len(rows), 'mailing')}; "
        f"{pm['before_months']} months before against the {pm['after_months']} after, per mailing.",
        "Selection: mailed personal accounts, one mailing at a time."])
    png = os.path.join(ctx["assets"], "james_per_mailing.png")
    JC.per_mailing_chart(png, pm["mailings"], 12.3, 3.6)
    CIS._picture(s, png, 0.5, 1.70, 12.3, 3.6)
    nets = [r["did"] for r in rows]
    hi = max(rows, key=lambda r: r["did"])
    lo = min(rows, key=lambda r: r["did"])
    _tiles_row(s, [(f"{pm['positive']} of {pm['measured']}", "Mailings with a positive net", ORANGE),
                   (_signed(hi["did"]) + "/mo", f"Net, {hi['m']}", NAVY),
                   (_signed(lo["did"]) + "/mo", f"Net, {lo['m']}", NAVY)], top=5.4, h=0.9)
    cap = (f"In {pm['positive']} of {pm['measured']} mailings responders' monthly spend moved "
           f"more than mailed non-responders' did; the net per responder runs from "
           f"{_signed(lo['did'])} ({lo['m']}) to {_signed(hi['did'])} ({hi['m']}).")
    CIS._caption(s, cap, width=W_FULL, top=6.4, height=0.85)
    CIS._notes(s, f"{ctx['odd_src']} — '<Mon> Mail', '<Mon> Resp' and monthly Sig $ + PIN $",
               method=("The pooled comparison on Responders vs Mailed Non-Responders, one mailing "
                       "at a time: same windows and cohorts (before_after), each group winsorized "
                       "per mailing at mean + 3 SD of its before and after means. Per mailing "
                       "(responders / non-responders, responder before→after, non-responder "
                       "before→after): "
                       + "; ".join(f"{r['m']} {r['responders']:,} / {r['control']:,}, "
                                   f"${r['r_before']:,}→${r['r_after']:,}, "
                                   f"${r['c_before']:,}→${r['c_after']:,}" for r in rows) + "."),
               issues=[
                   "RESPONDERS SELECT THEMSELVES; the net is an association, not the effect of "
                   "mailing a random account.",
                   "James runs 6 months before and 3 after and corrects for the dip before the "
                   "drop; these windows are 3 and 6, so the two are not comparable figure for "
                   "figure.",
                   (f"Mailings too thin to compare: {', '.join(r['m'] for r in pm['mailings'] if r['thin'])}."
                    if any(r["thin"] for r in pm["mailings"]) else ""),
                   f"Nets range {min(nets):,} to {max(nets):,}: read the spread before the "
                   "average.",
               ])
    CIS._place(prs, s, after=after, before="Debit Card Review")
    return s


# ============================================================== what a response is worth
def response_worth_slide(prs, ci, ctx):
    rv = ci["more"]["responder_value"]
    after = "Responders vs Non-Responders by Mailing"
    if not rv.get("available"):
        return _unavailable(prs, ctx, "What a Response Is Worth",
                            "Selection: responders against mailed non-responders.",
                            rv.get("reason", "the comparison is not available"), after,
                            before="Debit Card Review")
    s = CIS._new_slide(prs, CIS._find(prs, after))
    CIS._header(s, "What a Response Is Worth", _pill(ctx), [
        f"Selection: {CIS._n(len(rv['mailings']), 'mailing')}, {rv['mailings'][0]} to "
        f"{rv['mailings'][-1]}; interchange at the workbook's {rv['ic_rate']:.2%}.",
        "Selection: responders against mailed non-responders."])
    rows = [["", "Figure", "Where it comes from"],
            ["Net monthly spend per responder", _signed(rv["did"]),
             "Responders vs Mailed Non-Responders"],
            ["Interchange rate", f"{rv['ic_rate']:.2%}", "Workbook, Actuals MM"],
            ["Interchange a month, per responder", f"${rv['per_month']:,.2f}",
             "Spend x rate"],
            ["Interchange a year, per responder", f"${rv['per_year']:,.2f}", "x 12"],
            [f"Responses measured", f"{rv['observations']:,}",
             "Account-mailing pairs"],
            [f"Estimate over the {rv['after_months']}-month window",
             usd_compact(rv["cohort_window"]), "All measured responses"]]
    SH.add_table(s, 0.5, 1.75, 8.1, 3.6, rows, [3.4, 1.5, 3.2], fs=13)
    _tiles_rail(s, [(f"${rv['per_year']:,.0f}", "A year per response, est.", ORANGE),
                    (usd_compact(rv["booked_ltd"]) if rv.get("booked_ltd") else "—",
                     "Booked to date, workbook", NAVY),
                    (f"{rv['booked_months']}" if rv.get("booked_months") else "—",
                     "Months in the program", NAVY)])
    cap = (f"At the workbook's own interchange rate, the net {_signed(rv['did'])} a month per "
           f"responder is ${rv['per_month']:,.2f} a month in interchange, about "
           f"${rv['per_year']:,.0f} a year. That estimate and the workbook's "
           f"{usd_compact(rv['booked_ltd']) if rv.get('booked_ltd') else 'booked'} to date "
           f"answer different questions and are not meant to tie.")
    CIS._caption(s, cap, width=W_FULL, top=5.75, height=1.3)
    CIS._notes(s, f"{ctx['odd_src']}; {ctx['wb_src']} (Actuals MM Interchange Rate; booked revenue)",
               method=("Net monthly spend per responder = the pooled difference in differences "
                       "on Responders vs Mailed Non-Responders. Interchange = that spend x the "
                       "workbook's newest Interchange Rate. The window estimate multiplies the "
                       "monthly figure by the measured account-mailing pairs and the after-window "
                       "length. Booked to date is the workbook's program-to-date incremental "
                       "revenue."),
               issues=[
                   "TWO FRAMES, NEVER BLENDED (James, revenue_frames). The workbook books gross "
                   "program revenue by its own attribution; this is a difference-in-differences "
                   "estimate on the measured mailings only. Do not add them, and do not read a "
                   "gap between them as an error.",
                   "INTERCHANGE ONLY. No NSF/OD fee is priced here: the responder comparison "
                   "measures spend, not overdraft items.",
                   "RESPONDERS SELECT THEMSELVES, so the per-response figure is an association.",
                   "One blended interchange rate; signature and PIN earn different rates.",
               ])
    CIS._place(prs, s, after=after, before="Debit Card Review")
    return s


# ============================================================== tier movement by group
def movement_slide(prs, ci, ctx):
    mg = ci["more"]["movement_by_group"]
    after = "Swipe Tier Migration"
    if not mg.get("available"):
        return _unavailable(prs, ctx, "Tier Movement by Response",
                            "Selection: ARS-eligible personal card holders.",
                            f"the extract carries {mg.get('months', 0)} complete months and the "
                            f"view needs {mg.get('needs', 15)}", after)
    g = {x["group"]: x for x in mg["groups"]}
    s = CIS._new_slide(prs, CIS._find(prs, after))
    CIS._header(s, "Tier Movement by Response", _pill(ctx), [
        f"Selection: ARS-eligible personal card holders, {' to '.join(mg['then_window'])} against "
        f"{' to '.join(mg['now_window'])}, by response to the mailings between.",
        "Selection: eligible personal card holders, a year apart, by response."])
    png = os.path.join(ctx["assets"], "james_movement.png")
    JC.movement_chart(png, mg["groups"], 8.0, 4.0)
    CIS._picture(s, png, 0.5, 1.70, 8.0, 4.0)
    r, c, u = g["Responder"], g["Mailed non-responder"], g["Not mailed"]
    _tiles_rail(s, [(f"{r['up']:.0f}%" if r["up"] is not None else "—", "Responders moved up", ORANGE),
                    (f"{c['up']:.0f}%" if c["up"] is not None else "—", "Non-responders moved up", NAVY),
                    (f"{u['up']:.0f}%" if u["up"] is not None else "—", "Not mailed, moved up", NAVY)])
    cap = (f"{r['up']:.0f}% of the {r['accounts']:,} responders sit in a higher swipe tier than a "
           f"year ago, against {c['up']:.0f}% of {c['accounts']:,} mailed non-responders and "
           f"{u['up']:.0f}% of {u['accounts']:,} accounts not mailed in between.")
    CIS._caption(s, cap, width=W_FULL)
    CIS._notes(s, ctx["odd_src"],
               method=(f"Tiers as on Swipe Tier Migration (3-month average of Sig # + PIN #, "
                       f"rounded down into the band), {' to '.join(mg['then_window'])} and "
                       f"{' to '.join(mg['now_window'])}. Groups by the mailings between the two "
                       f"windows ({', '.join(mg['mailings']) or 'none'}): Responder = met a goal "
                       f"in at least one; Mailed non-responder = offered, never met; Not mailed = "
                       f"offered none of them."),
               issues=[
                   "The groups are not alike to begin with: the program mails accounts it "
                   "expects to move, so 'not mailed' includes the steady heavy users with "
                   "nowhere higher to go. The comparison is descriptive.",
                   "Met goals are defined by swiping more, so responders moving up is partly "
                   "the definition — the non-responder row is the one to read.",
                   "Only accounts eligible and carded at the snapshot are here; closures during "
                   "the year are not.",
               ])
    CIS._place(prs, s, after=after, before="Average Ticket")
    return s


# ============================================================== activation
def activation_slide(prs, ci, ctx):
    a = ci["more"]["activation_split"]
    after = "Tier Movement by Response"
    if not a.get("available"):
        return _unavailable(prs, ctx, "First Swipes: Program and Organic",
                            "Selection: personal accounts taking a first card swipe.",
                            "the extract is too short to see a first swipe after a quiet "
                            "stretch" if a.get("months") else "no first swipe in the window",
                            after)
    s = CIS._new_slide(prs, CIS._find(prs, after))
    CIS._header(s, "First Swipes: Program and Organic", _pill(ctx), [
        f"Selection: personal accounts whose first card swipe on file came {a['window'][0]} to "
        f"{a['window'][1]}.",
        "Selection: personal accounts taking a first swipe in the last year."])
    png = os.path.join(ctx["assets"], "james_activation.png")
    JC.activation_chart(png, a, 8.0, 4.0)
    CIS._picture(s, png, 0.5, 1.70, 8.0, 4.0)
    _tiles_rail(s, [(f"{a['program_pct']:.0f}%" if a["program_pct"] is not None else "—",
                     "Existing: mailed first", ORANGE),
                    (f"{a['existing']:,}", "Existing accounts started", NAVY),
                    (f"{a['new']:,}", "New accounts started", NAVY)])
    cap = (f"{a['first_swipes']:,} personal accounts made a first card swipe in the year; "
           f"{a['new']:,} were opened in that year. Of the {a['existing']:,} older accounts, "
           f"{a['mailed']:,} had an offer in the 3 months before and {a['organic']:,} started "
           f"with none.")
    CIS._caption(s, cap, width=W_FULL)
    CIS._notes(s, ctx["odd_src"],
               method=("First swipe = the first complete month with Sig # + PIN # above zero, "
                       f"after at least {JV.ACTIVATION_LOOKBACK} months open with none (an account "
                       "whose first month on file already swipes is left out — its first swipe "
                       "is before the extract). New = opened inside the window. Mailed first = an "
                       f"offer ('<Mon> Mail') in the first-swipe month or the {JV.MAIL_LEAD} "
                       "before it. " + (f"{a['unknown_opened']:,} accounts with no readable Date "
                                        "Opened are left out." if a.get("unknown_opened") else "")),
               issues=[
                   "MAILED FIRST IS NOT CAUSED BY THE MAIL. An account the program mails is one "
                   "it expects to move; some would have started anyway.",
                   "Organic includes accounts the program never offered to, which may be "
                   "outside its targeting rules.",
                   "James's version reads his own activation definition; the lookback and the "
                   "3-month mail lead here are ours.",
               ])
    CIS._place(prs, s, after=after, before="Average Ticket")
    return s


# ============================================================== card spend by merchant
def spend_mix_slide(prs, ci, ctx):
    mx = ci["more"]["card_spend_mix"]
    after = "PIN and Signature Mix"
    if not mx.get("available"):
        return _unavailable(prs, ctx, "Where Card Spend Goes",
                            "Selection: card transactions, one month.",
                            mx.get("reason", "no transaction file"), after)
    groups = [g for g in mx["groups"]]
    s = CIS._new_slide(prs, CIS._find(prs, after))
    CIS._header(s, "Where Card Spend Goes", f"{mx['month']} Data", [
        f"Selection: {mx['txns']:,} signature and PIN transactions, {mx['first_date']} to "
        f"{mx['last_date']}, every card in the file.",
        f"Selection: card transactions, {mx['month']}."])
    png = os.path.join(ctx["assets"], "james_spend_mix.png")
    JC.spend_mix_chart(png, groups, 8.0, 4.0)
    CIS._picture(s, png, 0.5, 1.70, 8.0, 4.0)
    mt = next((g for g in groups if g["group"] == "Money transfer"), None)
    _tiles_rail(s, [(usd_compact(mx["spend"]), f"Card spend, {mx['month']}", ORANGE),
                    (f"{mt['share_spend']:.0f}%" if mt else "—", "To money transfer", NAVY),
                    (f"{mx['home_share']:.0f}%" if mx.get("home_share") is not None else "—",
                     f"Spent in {mx['home_state']}" if mx.get("home_state") else "Home state", NAVY)])
    top = groups[0]
    cap = (f"{top['group']} takes {top['share_spend']:.0f}% of card dollars and "
           f"{top['share_txns']:.0f}% of card transactions. The average card transaction is "
           f"${mx['ticket']:,.2f}.")
    CIS._caption(s, cap, width=W_FULL)
    CIS._notes(s, f"{mx['file']} (the monthly transaction file carried in the client's ODD zip)",
               method=("SIG and PIN lines only; ACH and check lines have no merchant and are on "
                       "How the Money Moves. Merchant group = the transaction's Merchant Category "
                       "Code banded by published MCC ranges into our own coarse groups "
                       "(james_views.MCC_GROUPS). Location's trailing two letters read as the "
                       f"state. {mx['skipped']:,} unreadable lines skipped."),
               issues=[
                   "ONE MONTH. Nothing here is a trend, and a month with a holiday or a tax "
                   "refund reads differently.",
                   ("The file's last date is " + mx["last_date"] + ", before the month end — "
                    "treat the month as incomplete.") if not mx.get("complete") else "",
                   "The grouping is ours, not James's. He keys on his own MCC map plus keyword "
                   "and competitor dictionaries that are not on the share, so his outside-"
                   "product and competitor views are NOT reproduced.",
                   "Every card in the file, personal and business; the file is not joined to "
                   "the ODD here.",
                   "Money transfer mixes person-to-person apps with quasi-cash; it is not a "
                   "competitor measure.",
               ])
    CIS._place(prs, s, after=after, before="Mailing Insights")
    return s


def rails_slide(prs, ci, ctx):
    mx = ci["more"]["card_spend_mix"]
    rails = mx.get("rails") or {}
    after = "Where Card Spend Goes"
    if not rails:
        return _unavailable(prs, ctx, "How the Money Moves",
                            "Selection: transactions in the monthly file, by rail.",
                            mx.get("reason", "no transaction file"), after)
    s = CIS._new_slide(prs, CIS._find(prs, after))
    tot = sum(v["spend"] for v in rails.values())
    n = sum(v["txns"] for v in rails.values())
    month = mx.get("month", "")
    CIS._header(s, "How the Money Moves", f"{month} Data" if month else _pill(ctx), [
        f"Selection: {n:,} transactions in the monthly file, {mx.get('first_date', '')} to "
        f"{mx.get('last_date', '')}, by rail.",
        "Selection: transactions in the monthly file, by rail."])
    png = os.path.join(ctx["assets"], "james_rails.png")
    JC.rails_chart(png, rails, 8.0, 4.0)
    CIS._picture(s, png, 0.5, 1.70, 8.0, 4.0)
    card = sum(v["spend"] for k, v in rails.items() if k in JV.CARD_RAILS)
    card_n = sum(v["txns"] for k, v in rails.items() if k in JV.CARD_RAILS)
    _tiles_rail(s, [(usd_compact(tot), "Dollars in the file", ORANGE),
                    (f"{100.0 * card / tot:.0f}%" if tot else "—", "Of dollars on a card", NAVY),
                    (f"{100.0 * card_n / n:.0f}%" if n else "—", "Of transactions on a card", NAVY)])
    names = JC.RAIL_NAMES
    big = max(rails, key=lambda k: rails[k]["spend"])
    cap = (f"{names.get(big, big)} carries {100.0 * rails[big]['spend'] / tot:.0f}% of the "
           f"dollars in the file; cards carry {100.0 * card / tot:.0f}% of the dollars and "
           f"{100.0 * card_n / n:.0f}% of the transactions.")
    CIS._caption(s, cap, width=W_FULL)
    CIS._notes(s, f"{mx.get('file', 'monthly transaction file')}",
               method=("Every readable line of the file, summed by its rail column: SIG and PIN "
                       "are card; ACH and CHK are not. Per rail: "
                       + "; ".join(f"{names.get(k, k)} {v['txns']:,} lines, ${v['spend']:,}"
                                   for k, v in sorted(rails.items(), key=lambda kv: -kv[1]['spend']))
                       + "."),
               issues=[
                   "ONE MONTH, one client's feed. Most clients' files are card-only; where the "
                   "file carries no ACH or check lines this slide can only show the two card "
                   "rails.",
                   "Dollars are not direction-tagged in the columns read here, so this is "
                   "volume moved, not money in against money out. James's 'how the money "
                   "moves' view splits flows with his dictionaries, which are not on the share.",
               ])
    CIS._place(prs, s, after=after, before="Mailing Insights")
    return s


# ============================================================== where cards lag
def card_gaps_slide(prs, ci, ctx):
    cg = ci["more"]["card_gaps"]
    av = ci["more"]["account_value"]
    after = "12-Month Take Rate by Branch"
    if not cg.get("available"):
        return _unavailable(prs, ctx, "Where Cards Lag", "Selection: ARS-eligible personal accounts.",
                            cg.get("reason", "no eligible accounts"), after)
    s = CIS._new_slide(prs, CIS._find(prs, after))
    CIS._header(s, "Where Cards Lag", _pill(ctx), [
        f"Selection: {cg['eligible']:,} ARS-eligible personal accounts, {cg['no_card']:,} "
        f"without a debit card, by branch.",
        "Selection: ARS-eligible personal accounts without a card, by branch."])
    br = cg["branches"][:10]
    lab = _branch_label(ctx, [b["branch"] for b in br])
    data = [["Branch", "Eligible", "No card", "Take rate", "Share of eligible", "Share of cards",
             "Cards short of book"]]
    for b in br:
        data.append([lab(b["branch"]), f"{b['eligible']:,}", f"{b['no_card']:,}",
                     f"{b['take']:.1f}%", f"{b['share_eligible']:.1f}%",
                     f"{b['share_cards']:.1f}%", f"{b['short']:,}"])
    SH.add_table(s, 0.5, 1.72, 12.3, 0.36 * len(data), data, [3.0, 1.3, 1.2, 1.3, 1.8, 1.7, 2.0],
                 fs=12)
    per_card = None
    if av.get("available") and av.get("card_delta") is not None:
        per_card = av["card_delta"]
    gaps = cg["gaps"]
    cap = (f"The book's take rate is {cg['take']:.1f}%. ")
    if gaps:
        cap += (f"The three widest branch gaps — {CIS._and([lab(g['branch']) for g in gaps])} — "
                f"are {cg['gap_cards']:,} cards short of that rate")
        cap += (f"; at the {usd_compact(per_card)} a year a card-holding account earns over a "
                f"cardless one, about {usd_compact(per_card * cg['gap_cards'])} a year."
                if per_card else ".")
    else:
        cap += "No branch of 40 or more eligible accounts sits below it."
    top = 1.72 + 0.36 * len(data) + 0.25
    CIS._caption(s, cap, width=W_FULL, top=max(top, 5.7), height=1.2)
    CIS._notes(s, ctx["odd_src"] + (f"; {ctx['wb_src']} (rates)" if per_card else ""),
               method=("Eligible = personal accounts with '<latest> Elig' = Yes; card = Debit? on "
                       "the account. Branches listed by accounts without a card. Cards short = "
                       "eligible x the book's take rate − cards held, floored at zero, for "
                       f"branches with {cg['min_branch']} or more eligible accounts. Value per card "
                       "= the card-vs-cardless difference on What a Card and an Opt-In Earn."),
               issues=[
                   "A CARDLESS ACCOUNT IS NOT A LOST CARD. Some customers decline a card on "
                   "purpose; the gap is an upper bound on what asking could convert.",
                   "The dollar figure assumes a converted account earns what today's card "
                   "holders earn over today's cardless accounts. It will earn less: the "
                   "accounts without a card are the ones that did not want one.",
                   "Branch is the account's branch of record, not where it was opened or served.",
               ])
    CIS._place(prs, s, after=after, before="Reg E Review")
    return s


# ============================================================== account value
def value_slide(prs, ci, ctx):
    av = ci["more"]["account_value"]
    after = "Card Account Health"
    if not av.get("available"):
        return _unavailable(prs, ctx, "What a Card and an Opt-In Earn",
                            "Selection: ARS-eligible personal accounts and open card holders.",
                            av.get("reason", "the workbook's rates are not available"), after,
                            before="Reg E Review", source=f"{ctx['odd_src']}; {ctx['wb_src']}")
    g = av["groups"]
    s = CIS._new_slide(prs, CIS._find(prs, after))
    CIS._header(s, "What a Card and an Opt-In Earn", _pill(ctx), [
        f"Selection: {av['window'][0]} to {av['window'][1]}, at the workbook's {av['ic_rate']:.2%} "
        f"interchange and ${av['nsf_fee']:,.0f} NSF fee.",
        "Selection: a year of activity at the workbook's own rates."])

    def cell(x):
        return f"${x:,}" if x is not None else "—"
    rows = [["A year, per account", "Accounts", "Interchange", "NSF/OD fees", "Total"]]
    for k, name in (("Card", "Eligible, with a card"), ("No card", "Eligible, no card"),
                    (JV.REGE_IN, "Card holders, opted in"), (JV.REGE_OUT, "Card holders, opted out"),
                    (JV.REGE_DEFAULT, "Card holders, no election")):
        x = g[k]
        if not x["accounts"]:
            continue
        rows.append([name, f"{x['accounts']:,}", cell(x["interchange"]), cell(x["fees"]),
                     cell(x["total"])])
    SH.add_table(s, 0.5, 1.75, 8.1, 0.5 * len(rows), rows, [2.9, 1.3, 1.3, 1.3, 1.1], fs=13)
    _tiles_rail(s, [(f"${av['card_delta']:,}" if av["card_delta"] is not None else "—",
                     "A card, a year", ORANGE),
                    (f"${av['optin_delta']:,}" if av["optin_delta"] is not None else "—",
                     "An opt-in, a year", NAVY),
                    (f"{av['no_card_accounts']:,}", "Eligible without a card", NAVY)])
    cap = ""
    if av["card_delta"] is not None:
        cap += (f"An eligible account with a card earned {cell(g['Card']['total'])} a year against "
                f"{cell(g['No card']['total'])} without one, a difference of "
                f"${av['card_delta']:,}. ")
    if av["optin_delta"] is not None:
        cap += (f"An opted-in card holder earned {cell(g[JV.REGE_IN]['total'])} against "
                f"{cell(g[JV.REGE_OUT]['total'])} opted out.")
    CIS._caption(s, cap.strip(), width=W_FULL, top=5.75, height=1.3)
    CIS._notes(s, f"{ctx['odd_src']}; {ctx['wb_src']} ({av['rate_sheet']}: Interchange Rate, NSF Fee)",
               method=(f"Per account, {av['window'][0]} to {av['window'][1]} (the last 12 months "
                       f"complete for both card activity and NSF/OD): interchange = workbook "
                       f"Interchange Rate ({av['ic_rate']:.2%}) x Sig $ + PIN $; NSF/OD fees = "
                       f"workbook NSF Fee (${av['nsf_fee']:,.2f}) x the MTD NSF/OD item count, at "
                       f"100% collection (the Lift Matrix convention). Card groups: personal "
                       f"accounts with '<latest> Elig' = Yes, by Debit?. Opt-in groups: open "
                       f"personal card holders by the snapshot Reg E election."),
               issues=[
                   "100% COLLECTION IS AN ASSUMPTION. Fees charged are not fees collected; "
                   "charge-offs and waivers make the fee column an upper bound.",
                   "CORRELATION, NOT CAUSE. A card holder differs from a cardless account in "
                   "more than the card, and an opted-in account is one that overdraws; neither "
                   "difference is what converting one account would earn.",
                   "One blended interchange rate across signature and PIN.",
                   (lambda lo: f"Months left out as incomplete: {lo}" if lo else "")(
                       ci["more"]["completeness"].get("left_out_all")),
               ])
    CIS._place(prs, s, after=after, before="Reg E Review")
    return s


def ladder_slide(prs, ci, ctx):
    av = ci["more"]["account_value"]
    after = "What a Card and an Opt-In Earn"
    if not av.get("available") or not av.get("ladder"):
        return _unavailable(prs, ctx, "Value by Account Age",
                            "Selection: ARS-eligible personal accounts, by tenure.",
                            av.get("reason", "no tenure bands"), after, before="Reg E Review")
    lad = av["ladder"]
    s = CIS._new_slide(prs, CIS._find(prs, after))
    CIS._header(s, "Value by Account Age", _pill(ctx), [
        f"Selection: ARS-eligible personal accounts by tenure, {av['window'][0]} to "
        f"{av['window'][1]}, at the workbook's own rates.",
        "Selection: eligible personal accounts, by tenure."])
    png = os.path.join(ctx["assets"], "james_ladder.png")
    JC.ladder_chart(png, lad, 8.0, 4.0)
    CIS._picture(s, png, 0.5, 1.70, 8.0, 4.0)
    known = [r for r in lad if r["group"] != "Not on file"]
    steps = [(known[i], known[i + 1], known[i + 1]["total"] - known[i]["total"])
             for i in range(len(known) - 1)]
    big = max(steps, key=lambda t: t[2]) if steps else None
    _tiles_rail(s, [(f"${known[0]['total']:,}" if known else "—",
                     known[0]["group"] if known else "", ORANGE),
                    (f"${max(r['total'] for r in known):,}" if known else "—",
                     "Top band, a year", NAVY),
                    (f"+${big[2]:,}" if big and big[2] > 0 else "—", "Biggest step up", NAVY)])
    cap = " ".join(f"{r['group']}: ${r['total']:,}." for r in known)
    if big and big[2] > 0:
        cap = (f"The biggest step is from {big[0]['group'].lower()} to {big[1]['group'].lower()}, "
               f"${big[0]['total']:,} to ${big[1]['total']:,} a year. " + cap)
    CIS._caption(s, cap, width=W_FULL)
    CIS._notes(s, f"{ctx['odd_src']}; {ctx['wb_src']} (rates)",
               method=("As on What a Card and an Opt-In Earn, per eligible account, banded by "
                       "months from Date Opened to the snapshot. Per band: "
                       + "; ".join(f"{r['group']} {r['accounts']:,} accounts, interchange "
                                   f"${r['interchange']:,}, fees ${r['fees']:,}" for r in lad) + "."),
               issues=[
                   "A cross-section, not a path: today's 10-year accounts were opened into a "
                   "different book and fee schedule than today's new ones will age into.",
                   "Fees at 100% collection, one blended interchange rate.",
               ])
    CIS._place(prs, s, after=after, before="Reg E Review")
    return s


def branch_value_slide(prs, ci, ctx):
    av = ci["more"]["account_value"]
    wc = ci["more"]["where_accounts_close"]
    after = "Branch Scorecard"
    if not av.get("available") or not av.get("branches"):
        return _unavailable(prs, ctx, "Branch Value per Account",
                            "Selection: ARS-eligible personal accounts, by branch.",
                            av.get("reason", "no branch has enough eligible accounts"), after,
                            before="ARS Key Takeaways")
    br = av["branches"]
    close = {b["name"]: b for b in (wc.get("branches") or [])} if wc.get("available") else {}
    show = br[:5] + ([b for b in br[5:]][-5:] if len(br) > 10 else br[5:10])
    lab = _branch_label(ctx, [b["branch"] for b in show])
    s = CIS._new_slide(prs, CIS._find(prs, after))
    CIS._header(s, "Branch Value per Account", _pill(ctx), [
        f"Selection: branches with {av['min_branch']} or more ARS-eligible personal accounts, "
        f"{av['window'][0]} to {av['window'][1]}.",
        "Selection: eligible personal accounts, by branch."])
    data = [["Branch", "Eligible", "Take rate", "Value a year, per account", "Closed, 12 months"]]
    for b in show:
        c = close.get(b["branch"])
        data.append([lab(b["branch"]), f"{b['eligible']:,}", f"{b['take']:.1f}%",
                     f"${b['value']:,}", f"{c['rate']:.1f}%" if c else "—"])
    SH.add_table(s, 0.5, 1.72, 12.3, 0.38 * len(data), data, [3.4, 1.5, 1.6, 2.8, 2.2], fs=12)
    hi, lo = br[0], br[-1]
    cap = (f"Across {CIS._n(len(br), 'branch', 'branches')}, value per eligible account runs from "
           f"${lo['value']:,} a year at {lab(lo['branch'])} to ${hi['value']:,} at "
           f"{lab(hi['branch'])}.")
    top = 1.72 + 0.38 * len(data) + 0.25
    CIS._caption(s, cap, width=W_FULL, top=max(top, 5.9), height=0.9)
    CIS._notes(s, f"{ctx['odd_src']}; {ctx['wb_src']} (rates)",
               method=("Value = (interchange + NSF/OD fees) per eligible account a year, as on "
                       "What a Card and an Opt-In Earn. Shown: the five branches with the most "
                       "value per account and the five with the least (all when ten or fewer). "
                       "Closed, 12 months = the Where Accounts Close rate, blank for a branch "
                       f"under its {JV.ATTRITION_MIN}-account floor. All branches: "
                       + "; ".join(f"{b['branch']} ${b['value']:,}" for b in br) + "."),
               issues=[
                   "Value mixes interchange and fees; a branch high on value may simply serve "
                   "customers who overdraw more.",
                   "Small branches swing: a branch of 40 accounts moves with one customer.",
                   "Fees at 100% collection; one blended interchange rate.",
               ])
    CIS._place(prs, s, after=after, before="ARS Key Takeaways")
    return s


# ============================================================== Reg E over time
def rege_trend_slide(prs, ci, ctx):
    rt = ci["more"]["rege_trend"]
    after = "Reg E Opt-In — All Personal Accounts"
    if not rt.get("available"):
        return _unavailable(prs, ctx, "Reg E Elections Over Time",
                            "Selection: personal card holders' Reg E elections, by month.",
                            rt.get("reason", "no monthly elections"), after)
    s = CIS._new_slide(prs, CIS._find(prs, after))
    f, l = rt["first"], rt["last"]
    CIS._header(s, "Reg E Elections Over Time", _pill(ctx), [
        f"Selection: personal debit-card holders with a Reg E election, {f['month']} to "
        f"{l['month']}.",
        "Selection: personal card holders' elections, by month."])
    png = os.path.join(ctx["assets"], "james_rege_trend.png")
    JC.rege_trend_chart(png, rt, 8.0, 4.0)
    CIS._picture(s, png, 0.5, 1.70, 8.0, 4.0)
    _tiles_rail(s, [(f"{l['in_pct']:.1f}%", f"Opted in, {l['month']}", ORANGE),
                    (f"{rt['to_in']:,}", f"Opted in since {rt['flip_from']}", NAVY),
                    (f"{rt['from_in']:,}", f"Left opt-in since {rt['flip_from']}", NAVY)])
    ch = l["in_pct"] - f["in_pct"]
    # The months go AFTER the figures: the claim checker pairs a movement word with the nearest
    # numbers, and "Sep 2024" between the two shares read as a move from 2024 to 29.3.
    span = f"between {f['month']} and {l['month']}"
    if abs(ch) <= 2.0:
        move = (f"The opt-in share was almost flat, {f['in_pct']:.1f}% to {l['in_pct']:.1f}% "
                f"{span}")
    elif ch > 0:
        move = (f"The opt-in share rose from {f['in_pct']:.1f}% to {l['in_pct']:.1f}%, "
                f"{ch:.1f} points {span}")
    else:
        move = (f"The opt-in share was {f['in_pct']:.1f}% and then {l['in_pct']:.1f}% {span}")
    cap = (f"{move}. Between {rt['flip_from']} and {rt['flip_to']}, {rt['to_in']:,} card holders "
           f"moved into opt-in and {rt['from_in']:,} moved out of it.")
    CIS._caption(s, cap, width=W_FULL)
    CIS._notes(s, f"{ctx['odd_src']} — '<Mon> Reg E Desc' for each month",
               method=("Each month: personal accounts holding a debit card (Debit? at the "
                       "snapshot) whose election that month maps to Opt In / Opt Out / Default "
                       "through odd_rows.rege_label; blank cells are not applicable. Changes: "
                       f"the same accounts' elections in {rt['flip_from']} against "
                       f"{rt['flip_to']}, both readable. Largest transitions: "
                       + "; ".join(f"{a} → {b} {v:,}" for a, b, v in rt["flips"][:6]) + "."),
               issues=[
                   "The card flag is the SNAPSHOT's: an account that had a card two years ago "
                   "and closed it is not in the early months, so the base grows partly by "
                   "definition.",
                   ("Reg E values the classifier could not map, left out: "
                    + ", ".join(f"{k!r} ({v:,})" for k, v in rt["unmapped"].items())
                    + ". Ask Aaron how to map them.") if rt.get("unmapped") else "",
                   "James's lab reads flips after a fee month; that link is not made here — "
                   "a change of election is counted whatever prompted it.",
               ],
               checks=["Every non-blank Reg E value in the window mapped." if not rt.get("unmapped") else ""])
    CIS._place(prs, s, after=after, before="Take Rate and Reg E Opt-In by Branch")
    return s


# ============================================================== stressors
def stress_slide(prs, ci, ctx):
    st = ci["more"]["stressors"]
    after = "What a Card and an Opt-In Earn" if CIS._find(prs, "Value by Account Age") is None \
        else "Value by Account Age"
    if not st.get("available"):
        return _unavailable(prs, ctx, "Accounts Under Stress",
                            "Selection: open ARS-eligible personal accounts.",
                            st.get("reason", "no open eligible accounts"), after,
                            before="Reg E Review")
    s = CIS._new_slide(prs, CIS._find(prs, after))
    CIS._header(s, "Accounts Under Stress", _pill(ctx), [
        f"Selection: {st['base']:,} open ARS-eligible personal accounts, by how many of three "
        f"conditions they meet at once.",
        "Selection: open eligible personal accounts, by stress conditions."])
    png = os.path.join(ctx["assets"], "james_stress.png")
    JC.stress_chart(png, st, 8.0, 4.0)
    CIS._picture(s, png, 0.5, 1.70, 8.0, 4.0)
    _tiles_rail(s, [(f"{st['multi']:,}", "Two or more at once", ORANGE),
                    (f"{st['multi_pct']:.1f}%", "Of open eligible accounts", NAVY),
                    (usd_compact(st["multi_balances"]), "Balances they hold", NAVY)])
    combo = st["combos"][0] if st["combos"] else None
    cap = (f"{st['multi']:,} open eligible accounts meet two or more conditions at once, "
           f"holding {usd_compact(st['multi_balances'])} in current balances.")
    if combo:
        cap += f" The most common single pattern is {combo[0].lower()} ({combo[1]:,})."
    CIS._caption(s, cap, width=W_FULL)
    CIS._notes(s, ctx["odd_src"],
               method=(f"Conditions: {JV.STRESS_NAMES[0]} = a card holder whose card spend in "
                       f"{' to '.join(st['recent_window'])} averaged below 80% of "
                       f"{' to '.join(st['prior_window'])}, or was zero in all three after "
                       f"earlier use; {JV.STRESS_NAMES[1]} = at least one NSF/OD item in "
                       f"{' to '.join(st['nsf_window'])} (months complete for NSF/OD); "
                       f"{JV.STRESS_NAMES[2]} = Curr Bal below half of Avg Bal. Combinations: "
                       + "; ".join(f"{k} {v:,}" for k, v in st["combos"]) + "."),
               issues=[
                   "THESE ARE OUR THREE CONDITIONS. James's concurrent-stressor view reads more "
                   "(transaction-file flags such as banking elsewhere), which this pipeline "
                   "does not have for most clients.",
                   "Curr Bal is one day and Avg Bal an unstated period; a payroll landing the day "
                   "after the extract flips the balance condition.",
                   "A condition is not a prediction. The months-of-warning view is the check on "
                   "whether fading spend precedes closing on this book.",
                   "Account-level lists (James's stressors list) are deliberately not produced: "
                   "they carry balances and belong in Build Artifacts with an agreed delivery "
                   "process, not in a deck.",
                   (lambda lo: f"Months left out as incomplete: {lo}" if lo else "")(
                       ci["more"]["completeness"].get("left_out_nsf")),
               ])
    CIS._place(prs, s, after=after, before="Reg E Review")
    return s


# ============================================================== closures
def close_slide(prs, ci, ctx):
    wc = ci["more"]["where_accounts_close"]
    after = "First-Year Closure"
    if not wc.get("available"):
        return _unavailable(prs, ctx, "Where Accounts Close",
                            "Selection: personal accounts open or closed in the last 12 months.",
                            wc.get("reason", "no accounts"), after)
    s = CIS._new_slide(prs, CIS._find(prs, after))
    t = wc["total"]
    CIS._header(s, "Where Accounts Close", _pill(ctx), [
        f"Selection: {t['at_risk']:,} personal accounts open or closed {wc['window'][0]} to "
        f"{wc['window'][1]}, by product and by branch.",
        "Selection: personal accounts, 12-month closure rate."])
    pr = [["Product", "Accounts", "Closed", "Rate"]] + [
        [p["name"][:26], f"{p['at_risk']:,}", f"{p['closed']:,}", f"{p['rate']:.1f}%"]
        for p in wc["products"]]
    SH.add_table(s, 0.5, 1.72, 6.0, 0.4 * len(pr), pr, [2.8, 1.2, 1.0, 1.0], fs=12)
    rated = [b for b in wc["branches"] if not b.get("rollup")]
    rated.sort(key=lambda b: -b["rate"])
    show = rated[:4] + (rated[-4:] if len(rated) > 8 else rated[4:8])
    lab = _branch_label(ctx, [b["name"] for b in show])
    bt = [["Branch", "Accounts", "Rate"]] + [[lab(b["name"])[:24], f"{b['at_risk']:,}",
                                              f"{b['rate']:.1f}%"] for b in show]
    SH.add_table(s, 6.8, 1.72, 6.0, 0.4 * len(bt), bt, [3.2, 1.5, 1.3], fs=12)
    hi, lo = wc.get("branch_high"), wc.get("branch_low")
    cap = f"{t['rate']:.1f}% of personal accounts closed in the 12 months."
    if hi and lo:
        cap += (f" Among branches with {wc['min_branch']} or more accounts the rate runs from "
                f"{lo['rate']:.1f}% at {lab(lo['name']) if lo['name'] in [b['name'] for b in show] else lo['name']} "
                f"to {hi['rate']:.1f}% at {lab(hi['name']) if hi['name'] in [b['name'] for b in show] else hi['name']}.")
    top = 1.72 + 0.4 * max(len(pr), len(bt)) + 0.25
    CIS._caption(s, cap, width=W_FULL, top=max(top, 5.9), height=0.9)
    CIS._notes(s, ctx["odd_src"],
               method=("Closure rate = personal accounts closed (not open, Date Closed inside the "
                       "window) / (open personal accounts + those closures) — the Branch "
                       "Scorecard's definition. Products: the six with the most accounts, the rest "
                       f"rolled up. Branches: rated only at {wc['min_branch']}+ accounts (James's "
                       "floor); the four highest and four lowest shown. All rated branches: "
                       + "; ".join(f"{b['name']} {b['rate']:.1f}%" for b in rated) + "."),
               issues=[
                   "Every personal product is here, savings included — not only the ARS "
                   "checking products — so the total is not the Account Retention slide's figure.",
                   "A product closed by the client (a retired product converted into another) "
                   "reads as attrition.",
               ])
    CIS._place(prs, s, after=after)
    return s


def warning_slide(prs, ci, ctx):
    mw = ci["more"]["months_of_warning"]
    after = "Where Accounts Close"
    if not mw.get("available"):
        return _unavailable(prs, ctx, "Card Spend Before a Close",
                            "Selection: personal accounts that closed in the last 12 months.",
                            mw.get("reason", "no closers"), after)
    s = CIS._new_slide(prs, CIS._find(prs, after))
    CIS._header(s, "Card Spend Before a Close", _pill(ctx), [
        f"Selection: {mw['closers']:,} personal accounts that closed {mw['window'][0]} to "
        f"{mw['window'][1]} after card spend in the year before, against open card holders.",
        "Selection: closed personal card users against open card holders."])
    png = os.path.join(ctx["assets"], "james_warning.png")
    JC.warning_chart(png, mw, 8.0, 4.0)
    CIS._picture(s, png, 0.5, 1.70, 8.0, 4.0)
    c1 = next(p for p in mw["curve"] if p["k"] == 1)
    c12 = next(p for p in mw["curve"] if p["k"] == max(q["k"] for q in mw["curve"]))
    _tiles_rail(s, [(f"{mw['warning']}" if mw["warning"] else "None", "Months of fade detected", ORANGE),
                    (f"{100 * c1['ratio']:.0f}%" if c1["ratio"] else "—", "Of open spend, month before", NAVY),
                    (f"{mw['closers']:,}", "Closers measured", NAVY)])
    if mw["warning"]:
        head = (f"Closing accounts were spending below {100 * mw['ratio']:.0f}% of open card "
                f"holders from {mw['warning']} month{'s' if mw['warning'] != 1 else ''} before "
                f"they closed.")
    else:
        head = (f"No sustained fade shows before a close on this book: closing accounts did not "
                f"stay below {100 * mw['ratio']:.0f}% of open card holders' spend in the months "
                f"before closing.")
    cap = (f"{head} The month before the close they spent ${c1['closers']:,} against "
           f"${c1['open']:,}; {c12['k']} months before, ${c12['closers']:,} against ${c12['open']:,}.")
    CIS._caption(s, cap, width=W_FULL)
    CIS._notes(s, ctx["odd_src"],
               method=("Closers: personal accounts with Date Closed in the last 12 months whose "
                       "close month is a complete month of the extract with 12 months before it, "
                       "and with card spend in those 12 months (the Debit? flag is read at the "
                       "snapshot and a closed account has usually lost it). Comparison: the mean "
                       "card spend of open personal card holders in the SAME calendar months. "
                       f"Fade = the ratio below {mw['ratio']:.0%} in every month from the warning "
                       "month to the close. Ratios by months before: "
                       + "; ".join(f"-{p['k']} {p['ratio']:.2f}" for p in mw["curve"]
                                   if p["ratio"] is not None) + "."),
               issues=[
                   "Closers here are card USERS by spend; an account that closed without "
                   "ever swiping is not in the curve.",
                   "The open comparison is every open card holder, not a matched group; a "
                   "closer that was a light user all along reads as 'fading' from the start.",
                   "No fade is a finding, not a failure: the signal may be shorter than a month "
                   "or absent (James words it the same way).",
               ])
    CIS._place(prs, s, after=after)
    return s


# ============================================================== cascade
def cascade_slide(prs, ci, ctx):
    cc = ci["more"]["cascade"]
    before = "ARS Scorecard"
    anchor = CIS._find(prs, before) or CIS._find(prs, "ARS Key Takeaways")
    if not cc.get("available"):
        s = CIS._new_slide(prs, anchor)
        CIS._header(s, "Program Cascade", _pill(ctx), "Selection: ARS-eligible personal accounts.")
        CIS._caption(s, f"Not shown for this period: {cc.get('reason')}.", width=12.3, top=2.4)
        CIS._notes(s, ctx["odd_src"], issues=["Nothing on this slide is measured."])
        CIS._place(prs, s, before=before if CIS._find(prs, before) else "ARS Key Takeaways")
        return s
    s = CIS._new_slide(prs, anchor)
    CIS._header(s, "Program Cascade", _pill(ctx), [
        f"Selection: ARS-eligible personal accounts at {ctx['as_of_long']}, step by step; "
        f"{CIS._n(cc['mailings'], 'mailing')} in this extract.",
        "Selection: ARS-eligible personal accounts, step by step."])
    png = os.path.join(ctx["assets"], "james_cascade.png")
    JC.cascade_chart(png, cc["steps"], 8.0, 4.0)
    CIS._picture(s, png, 0.5, 1.70, 8.0, 4.0)
    st = cc["steps"]
    _tiles_rail(s, [(f"{100.0 * st[1][1] / st[0][1]:.1f}%", "Hold a card", ORANGE),
                    (f"{100.0 * st[2][1] / st[1][1]:.1f}%" if st[1][1] else "—",
                     "Of card holders swiping", NAVY),
                    (usd_compact(cc["booked_ltd"]) if cc.get("booked_ltd") else "—",
                     "Booked to date, workbook", NAVY)])
    cap = (f"Of {st[0][1]:,} eligible accounts, {st[1][1]:,} hold a card and {st[2][1]:,} "
           f"swiped in {cc['last_month']}; {st[3][1]:,} card holders were offered by a mailing in "
           f"this extract and {st[4][1]:,} met a goal.")
    CIS._caption(s, cap, width=W_FULL)
    CIS._notes(s, f"{ctx['odd_src']}; {ctx['wb_src']} (booked revenue)",
               method=("Each step counts the step above's accounts: eligible personal accounts "
                       "('<latest> Elig' = Yes) → with Debit? → with Sig # + PIN # above zero in "
                       "the last complete month → carrying an offer in any mailing of the extract "
                       "→ with a met goal on one of those offers. Booked to date is the "
                       "workbook's program-to-date incremental revenue, which is not a step of "
                       "the funnel and is shown beside it."),
               issues=[
                   "The mailing steps cover only the mailings this extract carries, not the "
                   "program's whole history.",
                   "James's cascade continues to card revenue and retention using his own "
                   "revenue model; ours stops at the counts and shows the workbook's figure "
                   "beside them rather than attributing it.",
               ])
    CIS._place(prs, s, before=before if CIS._find(prs, before) else "ARS Key Takeaways")
    return s


# ============================================================== entry point
def add_more_slides(prs, ci, ctx):
    """Build and place the second round. Order matters only where one new slide anchors
    another (Offer Segments before Response by Offer Number, and so on)."""
    if not ci.get("more"):
        return []
    made = [
        pnl_slide(prs, ci, ctx),
        segments_slide(prs, ci, ctx),
        offer_number_slide(prs, ci, ctx),
        per_mailing_slide(prs, ci, ctx),
        response_worth_slide(prs, ci, ctx),
        movement_slide(prs, ci, ctx),
        activation_slide(prs, ci, ctx),
        spend_mix_slide(prs, ci, ctx),
        rails_slide(prs, ci, ctx),
        card_gaps_slide(prs, ci, ctx),
        value_slide(prs, ci, ctx),
        ladder_slide(prs, ci, ctx),
        stress_slide(prs, ci, ctx),
        branch_value_slide(prs, ci, ctx),
        rege_trend_slide(prs, ci, ctx),
        cascade_slide(prs, ci, ctx),
        close_slide(prs, ci, ctx),
        warning_slide(prs, ci, ctx),
    ]
    return made
