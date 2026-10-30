# Ported from ARS v5 02-Scripts/ars/deck/ics_slides.py at a491b5c (James Gilmore); logic unchanged.
"""The ICS chapter: behaviour only, from the ics_cmp_* comparison block
plus the ICS lens rows on the transaction sections. Approved mockup
DESIGN/report-mockups/slides-ics-chapter.html.

No interchange, no value, no payback: the ICS workbook owns that story,
and carrying both made the chapter hedge its own headlines.

Renders ONLY when the ICS source lists stamped the book (ics_cmp_bases
present with accounts on both sides) -- ARS-only clients never see it.
Appendix-first: the chapter lands behind the Appendix divider until
James promotes it. Every comparison names its base; immature cells and
missing pieces skip-report instead of rendering thin."""

from __future__ import annotations

from pathlib import Path

from . import charts



def _habit_base(q: dict) -> str:
    """What the dumbbell is measured over, said out loud.

    Every habit measure runs on accounts with twelve full months, and that
    gate is most of the book -- ICS openings start five months into the
    24-month window and then ramp. A base quietly becoming a third of its
    size is exactly the thing to print rather than imply (#87).
    """
    ics, non = q.get("ics_habit_base"), q.get("non_habit_base")
    if not ics or not non:
        return "matched cohorts"
    dropped = (q.get("ics_habit_excluded") or 0) + (q.get("non_habit_excluded") or 0)
    tail = f", {dropped:,} too new to score" if dropped else ""
    return f"{ics:,} ICS and {non:,} control with a full year{tail}"
def add_chapter(prs, h: dict, m: dict, charts_dir: Path,
                txn: dict | None = None) -> list[str]:
    skipped: list[str] = []
    txn = txn or {}

    def _lens(table, name):
        """One lens row from a transaction section's _by_lens table."""
        for r in (txn.get(table) or []):
            if r and r[0] == name:
                return r
        return None

    bases = m.get("ics_cmp_bases") or {}
    if not bases.get("ics") or not bases.get("non"):
        return ["ICS chapter (no stamped ICS accounts or no control)"]
    new, slide, chart = h["new"], h["slide"], h["chart"]
    _rail, _kpi, _text = h["rail"], h["kpi"], h["text"]
    _table = h["table"]
    _table = h["table"]
    _fit_picture, _kicker = h["fit_picture"], h["kicker"]
    MARGIN_L, CONTENT_W = h["MARGIN_L"], h.get("CONTENT_W", 11.5)
    # a rail claims the right ~3.4in of the slide, so any chart sharing a
    # slide with one has to stop short of it. Full CONTENT_W put the waffle
    # under its own rail and pushed the merchant categories under theirs.
    RAIL_W = 3.4
    CHART_W = CONTENT_W - RAIL_W
    money = h["money"]
    n_ics, n_non = bases["ics"], bases["non"]
    stamped = bases.get("stamped_total", n_ics)
    ooc = bases.get("out_of_coverage", 0)

    h["divider"](prs, new, "ICS acquisition",
                 "the accounts the program opened, against the book")

    # ---- 1. acquisition + split ------------------------------------------
    counts = m.get("ics_source_counts") or {}
    share = 100 * n_ics / (n_ics + n_non)
    head = f"ICS has opened {stamped:,} accounts on this file"
    sub = (f"{counts.get('REF', 0):,} referral and {counts.get('DM', 0):,} "
           f"direct mail; {n_ics:,} opened inside the file's coverage "
           f"drive every comparison"
           + (f", {ooc:,} predate it" if ooc else ""))
    s, top = slide((head, sub), "ICS acquisition")
    path = chart("ics_split", charts.composition,
                 [["ICS", n_ics], ["All other openings", n_non]],
                 highlight="ICS")
    if path:
        _fit_picture(s, path, MARGIN_L, top + 0.1, max_w=CONTENT_W - 3.0,
                     max_h=1.9)
    trend = m.get("ics_cmp_openings_monthly") or []
    if len(trend) >= 3:
        path = chart("ics_openings", charts.line_series, trend,
                     ylabel="ICS accounts opened")
        if path:
            _fit_picture(s, path, MARGIN_L, top + 2.15,
                         max_w=CONTENT_W - 3.0, max_h=2.9)
    src = {r[0]: r for r in (m.get("ics_cmp_source") or [])}
    rail = [(lab, f"{src[k][1]:,}",
             f"M1 {src[k][2]:.0f}%" if src[k][2] is not None else "")
            for k, lab in (("REF", "Referral"), ("DM", "Direct mail"))
            if k in src]
    if trend:
        peak = max(trend, key=lambda r: r[1])
        rail.append(("Peak month", peak[0], f"{peak[1]:,} opened"))
    rail.append(("Share", f"{share:.0f}%",
                 "of coverage-window openings"))
    if ooc:
        rail.append(("Pre-coverage", f"{ooc:,}",
                     "counted, not behavior-compared"))
    _rail(s, rail, top=top)
    _kicker(s)

    # ---- 2. activation ---------------------------------------------------
    t = m.get("ics_cmp_ttfs") or {}
    cum = m.get("ics_cmp_activation_cum") or []
    if cum and t.get("ics_median_mo") is not None:
        im, nm = t["ics_median_mo"], t.get("non_median_mo")
        m1 = next((r for r in cum if r[0] == 1), None)
        m12 = next((r for r in cum if r[0] == 12), None)
        if m1 and m1[1] is not None and m1[2] is not None:
            head = (f"{m1[1]:.0f}% of ICS accounts swipe in their first "
                    f"month, against {m1[2]:.0f}% of the rest")
            sub = (f"cumulative share that has ever swiped, measured only on "
                   f"accounts old enough to reach each milestone -- a "
                   f"{m1[1] - m1[2]:.0f}-point gap at month one")
            if m12 and m12[1] is not None and m12[2] is not None:
                sub += f", still {m12[1] - m12[2]:.0f} points at month twelve"
        elif nm and im < nm:
            head = (f"ICS accounts activate in {im:g} month"
                    f"{'s' if im != 1 else ''}; the book takes {nm:g}")
            sub = None
        else:
            head = f"ICS median time to first swipe: {im:g} months"
            sub = None
        s, top = slide((head, sub), "ICS activation")
        path = chart("ics_activation", charts.gap_area,
                     [r[0] for r in cum], [r[1] for r in cum],
                     [r[2] for r in cum], "ICS", "non-ICS",
                     ylabel="activated %")
        if path:
            _fit_picture(s, path, MARGIN_L, top + 0.1, max_w=CONTENT_W - 3.4,
                         max_h=3.4)
        # only buckets with a MEASURED value on both sides -- a None
        # (no matured base) must never print as a zero (James, round 1)
        buckets = [b for b in (t.get("buckets") or [])
                   if b[1] is not None and b[2] is not None]
        if len(buckets) >= 2:
            path = chart("ics_ttfs", charts.grouped_bars,
                         [b[0] for b in buckets],
                         [b[1] for b in buckets],
                         [b[2] for b in buckets], "ICS", "non-ICS",
                         fmt="{:.0f}%", size=(charts.FIG_W_FULL, 1.9))
            if path:
                _fit_picture(s, path, MARGIN_L, top + 3.55,
                             max_w=CHART_W, max_h=1.85)
        _rail(s, [("ICS median", f"{im:g} mo", "open to first swipe"),
                  ("Book median", f"{nm:g} mo" if nm is not None else "--",
                   "same-window non-ICS")], top=top)
        _kicker(s)
    else:
        skipped.append("ICS activation (no matured TTFS base)")


    # ---- 2b. the never-activated, as a hundred squares -------------------
    nev = next((b for b in (t.get("buckets") or []) if b[0] == "never"), None)
    if nev and nev[1] is not None and nev[2] is not None:
        one_in = round(100 / nev[1]) if nev[1] else 0
        ctrl_in = round(100 / nev[2]) if nev[2] else 0
        s_, top = slide(
            (f"One ICS account in {one_in} never swipes; across the book it "
             f"is one in {ctrl_in}",
             "each square is one account in a hundred -- the filled squares "
             "never recorded a single swipe in the observation window"),
            "ICS never activated")
        path = chart("ics_waffle", charts.waffle,
                     [("ICS accounts", nev[1], f"base {n_ics:,}"),
                      ("Same-window non-ICS", nev[2], f"base {n_non:,}")])
        if path:
            _fit_picture(s_, path, MARGIN_L, top + 0.1, max_w=CHART_W,
                         max_h=3.6)
        _rail(s_, [("ICS never swipes", f"{nev[1]:.1f}%", f"of {n_ics:,}"),
                   ("Control", f"{nev[2]:.1f}%", f"of {n_non:,}"),
                   ("Gap", f"{nev[2] - nev[1]:.1f} pts",
                    "fewer dead accounts")], top=top)
        _kicker(s_)

    # ---- 3. milestone heatmap --------------------------------------------
    grid = m.get("ics_cmp_milestones") or {}
    if grid.get("rows"):
        firsts = [r[2] for r in grid["rows"] if r[2] is not None]
        if firsts and min(firsts) >= 80:
            head = "Every ICS cohort crosses 80% activation by month one"
        elif firsts:
            head = (f"Every ICS cohort lands between {min(firsts):.0f}% and "
                    f"{max(firsts):.0f}% activated in month one")
        else:
            head = (f"ICS activation by opening cohort: "
                    f"{len(grid['rows'])} months")
        s, top = slide(
            (head, "activation by opening cohort and milestone; blank "
                   "cells are not yet mature, never projected"),
            "ICS cohorts")
        path = chart("ics_milestones", charts.milestone_heat, grid)
        if path:
            _fit_picture(s, path, MARGIN_L, top + 0.1, max_w=CONTENT_W,
                         max_h=4.8)
        _kicker(s)
    else:
        skipped.append("ICS cohorts (no milestone rows)")

    # ---- 3b. sustained activity (ics_activity_grid was orphaned) ---------
    grid_rows = [r for r in (m.get("ics_activity_grid") or []) if r[1] >= 200]
    thin = [r for r in (m.get("ics_activity_grid") or []) if r[1] < 200]
    if len(grid_rows) >= 6:
        first, last = grid_rows[0], grid_rows[-1]
        head = (f"About two ICS accounts in three swipe in any given month, "
                f"and it barely decays")
        sub = (f"{first[2]:.1f}% in month one, still {last[2]:.1f}% at month "
               f"{last[0]}; the share swiping in that month of their life, not "
               f"cumulative")
        if thin:
            sub += (f". Stops at month {last[0]} -- months {thin[0][0]}-"
                    f"{thin[-1][0]} rest on {thin[-1][1]}-{thin[0][1]} accounts")
        s_, top = slide((head, sub), "ICS sustained activity")
        path = chart("ics_monthly", charts.line_with_base,
                     [[f"M{r[0]}", r[1], r[2]] for r in grid_rows],
                     ylabel="% swiping that month")
        if path:
            _fit_picture(s_, path, MARGIN_L, top + 0.1,
                         max_w=CONTENT_W - 3.4, max_h=3.8)
        _rail(s_, [("Month one", f"{first[2]:.1f}%", f"{first[1]:,} accounts"),
                   ("Month twelve",
                    next((f"{r[2]:.1f}%" for r in grid_rows if r[0] == 12), "--"),
                    next((f"{r[1]:,} accounts" for r in grid_rows if r[0] == 12), "")),
                   ("Floor", "200 accounts", "thinner months decline")], top=top)
        _kicker(s_)
    else:
        skipped.append("ICS sustained activity (no month with a 200-account base)")

    # ---- 4. usage + balances ---------------------------------------------
    u = m.get("ics_cmp_usage") or {}
    if u.get("ics_mean_swipes") is not None \
            and u.get("non_mean_swipes") is not None:
        ratio = (u["ics_mean_swipes"] / u["non_mean_swipes"]
                 if u["non_mean_swipes"] else None)
        gap = ((u.get("ics_mean_spend") or 0)
               - (u.get("non_mean_spend") or 0))
        # per-swipe is the honest read when the swipe counts are level:
        # the whole spend gap collapses into ticket size
        ics_per = ((u.get("ics_mean_spend") or 0) / u["ics_mean_swipes"]
                   if u["ics_mean_swipes"] else None)
        non_per = ((u.get("non_mean_spend") or 0) / u["non_mean_swipes"]
                   if u["non_mean_swipes"] else None)
        if ratio and ratio >= 1.05:
            head = (f"An active ICS account swipes {ratio:.1f}x the book")
        elif ratio and ratio <= 0.95:
            head = (f"Active ICS accounts swipe {1 / ratio:.1f}x below "
                    f"the book")
        elif ics_per and non_per:
            head = (f"ICS accounts swipe as often and spend "
                    f"{money(ics_per)} a swipe against {money(non_per)}")
        else:
            head = "ICS and non-ICS accounts swipe in step"
        sub = (f"{u['ics_mean_swipes']:g} swipes and "
               f"{money(u.get('ics_mean_spend'))} a month per active "
               f"account against {u['non_mean_swipes']:g} and "
               f"{money(u.get('non_mean_spend'))} for same-window "
               f"non-ICS accounts")
        s, top = slide((head, sub), "ICS usage")
        path = chart("ics_usage", charts.pair_lines, u["months"],
                     u["ics_swipes"], u["non_swipes"], "ICS", "non-ICS",
                     ylabel="swipes / active acct / mo")
        if path:
            _fit_picture(s, path, MARGIN_L, top + 0.1, max_w=CONTENT_W - 3.4,
                         max_h=3.2)
        tiers = [r for r in (m.get("ics_cmp_balance_tiers") or [])
                 if r[1] is not None and r[2] is not None]
        if len(tiers) >= 2:
            path = chart("ics_balances", charts.grouped_bars,
                         [r[0] for r in tiers], [r[1] for r in tiers],
                         [r[2] for r in tiers], "ICS", "non-ICS",
                         fmt="{:.0f}%", size=(charts.FIG_W_FULL, 1.9))
            if path:
                _fit_picture(s, path, MARGIN_L, top + 3.5,
                             max_w=CHART_W, max_h=1.85)
        rail = []
        if abs(gap) > 0.5:
            rail.append(("Spend gap", f"{'+' if gap > 0 else '-'}"
                         f"{money(abs(gap))}/mo", "per active account"))
        if ics_per and non_per:
            rail.append(("Per swipe", money(ics_per),
                         f"vs {money(non_per)} -- the gap is ticket size"))
        d = m.get("ics_cmp_debit") or {}
        if d.get("ics_pct") is not None:
            rail.append(("Debit take", f"{d['ics_pct']:.0f}%",
                         f"vs non-ICS {d.get('non_pct', 0):.0f}%"))
        if rail:
            _rail(s, rail, top=top)
        _kicker(s)
    else:
        skipped.append("ICS usage (no active-month base)")

    # ---- 4b. the quality of an ICS account -------------------------------
    # The habit measures ARE the dumbbell; repeating them as KPI tiles put
    # a 3.2in chart on top of two rows of tiles and pushed the last one off
    # the 7.5in slide. Tiles now carry only what the dumbbell does not.
    q = m.get("ics_cmp_quality") or {}
    HABIT = (("ics_consistency_pct", "non_consistency_pct",
              # The old label read as a headcount and is not one: this is a
              # share of MONTHS, averaged across accounts (#87).
              "Share of first-year months with a swipe",
              "averaged across accounts, not a count of accounts"),
             ("ics_tier11_pct", "non_tier11_pct", "Reach 11+ swipes",
              "ever hit the 11-swipe tier"),
             ("ics_tier21_pct", "non_tier21_pct", "Reach 21+ swipes",
              "ever hit the 21-swipe tier"),
             ("ics_ramp_hold_pct", "non_ramp_hold_pct", "Ramp holds",
              "months 9-12 at or above months 1-3"),
             ("ics_new_high_pct", "non_new_high_pct", "Still setting highs",
              "new personal high after month six"))
    dumb = [[lab, q[ik], q[nk], note] for ik, nk, lab, note in HABIT
            if q.get(ik) is not None and q.get(nk) is not None]

    tiles = []
    def pair(ik, nk, fmt, label, note):
        iv, nv = q.get(ik), q.get(nk)
        if iv is not None and nv is not None:
            tiles.append((label, fmt.format(iv),
                          f"vs {fmt.format(nv)} non-ICS · {note}"))
    pair("ics_ars_response_pct", "non_ars_response_pct", "{:.0f}%",
         "Respond to offers", "of ever-mailed accounts (the ARS synergy)")
    pair("ics_rege_pct", "non_rege_pct", "{:.0f}%",
         "Reg E opted in", "pattern-classified election")
    d_ = m.get("ics_cmp_debit") or {}
    if d_.get("ics_pct") is not None and d_.get("non_pct") is not None:
        tiles.append(("Carries a debit card", f"{d_['ics_pct']:.0f}%",
                      f"vs {d_['non_pct']:.0f}% non-ICS · the card has to "
                      f"exist first"))

    if len(dumb) >= 3:
        lead = max(dumb, key=lambda r: r[1] - r[2])
        s2, top = slide(
            (f"ICS accounts are active in {dumb[0][1]:.0f}% of their "
             f"first-year months, against {dumb[0][2]:.0f}%",
             f"{len(dumb)} habit measures on {_habit_base(q)}, every one a "
             f"share of its own cohort against same-window non-ICS "
             f"openings; the widest is {lead[0].lower()} at "
             f"{lead[1] - lead[2]:.1f} points"),
            "ICS quality")
        path = chart("ics_habit", charts.dumbbell, dumb, "ICS", "non-ICS")
        if path:
            _fit_picture(s2, path, MARGIN_L, top + 0.05,
                         max_w=CONTENT_W - 3.4, max_h=3.3)
        if tiles:
            tw = (CONTENT_W - 0.4) / 3
            for j, (label, value, note) in enumerate(tiles[:3]):
                _kpi(s2, MARGIN_L + j * (tw + 0.2), top + 3.55, tw,
                     label, value, note)
        _kicker(s2)
    else:
        skipped.append("ICS quality (too few measured pairs)")

    # ---- 4c. closure hazard by tenure ------------------------------------
    hz = m.get("ics_cmp_hazard") or {}
    hz_rows = [(i[0], i[2], n[2]) for i, n in zip(hz.get("ics") or [],
                                                  hz.get("non") or [])
               if i[2] is not None and n[2] is not None]
    if len(hz_rows) >= 2:
        a, b = hz_rows[0][1], hz_rows[0][2]
        head = (f"ICS accounts leave less in their first six months"
                if a < b else
                f"ICS and the book leave at the same rate early")
        s_, top = slide(
            (head,
             "of the accounts that reached the start of each bucket and had "
             "time to live through it, the share that closed inside it -- "
             "exposure-matched on both arms"), "ICS closure hazard")
        haz_rows = [[i[0], i[2], i[1], n[2], n[1]]
                    for i, n in zip(hz.get("ics") or [], hz.get("non") or [])]
        path = chart("ics_hazard", charts.paired_hbars, haz_rows,
                     "ICS", "same-window non-ICS")
        if path:
            _fit_picture(s_, path, MARGIN_L, top + 0.1,
                         max_w=CONTENT_W - 3.4, max_h=3.8)
        rail = [(f"{r[0]}", f"{r[1]:.1f}%", f"vs {r[2]:.1f}% non-ICS")
                for r in hz_rows]
        declined = [i[0] for i in (hz.get("ics") or []) if i[2] is None]
        if declined:
            rail.append(("Declined", ", ".join(declined), "base below the floor"))
        _rail(s_, rail, top=top)
        _kicker(s_)
    else:
        skipped.append("ICS closure hazard (fewer than two measurable buckets)")

    # ---- 4d. first-year closure, split on whether the card was used -------
    fy = m.get("ics_cmp_firstyear_close") or {}
    fi, fn = fy.get("ics"), fy.get("non")
    if fi and fn and fi.get("never_used_pct") is not None \
            and fn.get("never_used_pct") is not None:
        used_share = 100 * fi["used_n"] / fi["n"]
        ctrl_share = 100 * fn["used_n"] / fn["n"]
        head = ("An ICS account that never used its card still outlives a "
                "control that never used its either")
        s_, top = slide(
            (head,
             f"first-year closure on the {fi['n']:,} ICS and {fn['n']:,} "
             f"control accounts old enough to have a first year, split by "
             f"whether the card was ever used"), "ICS first-year closure")
        path = chart("ics_firstyear", charts.grouped_bars,
                     ["Used the card", "Never used it"],
                     [fi["used_pct"], fi["never_used_pct"]],
                     [fn["used_pct"], fn["never_used_pct"]],
                     "ICS", "same-window non-ICS", fmt="{:,.1f}%")
        if path:
            _fit_picture(s_, path, MARGIN_L, top + 0.1,
                         max_w=CONTENT_W - 3.4, max_h=3.8)
        _rail(s_, [
            ("On the used side", f"{used_share:.0f}%",
             f"vs {ctrl_share:.0f}% of the control"),
            ("Never used, ICS", f"{fi['never_used_pct']:.1f}%",
             f"vs {fn['never_used_pct']:.1f}% non-ICS"),
            ("Used, ICS", f"{fi['used_pct']:.1f}%",
             f"vs {fn['used_pct']:.1f}% non-ICS")], top=top)
        _kicker(s_)
    else:
        skipped.append("ICS first-year closure (no matured 12-month base)")

    # ---- 5. branch quadrant ----------------------------------------------
    br = [r for r in (m.get("ics_cmp_branch") or [])
          if r[2] is not None and r[3] is not None]
    if len(br) >= 2:
        best = max(br, key=lambda r: r[2])
        worst = min(br, key=lambda r: r[2])
        head = (f"{best[0]} turns ICS accounts on at {best[2]:.0f}%; "
                f"{worst[0]} sits at {worst[2]:.0f}%")
        s, top = slide(
            (head, "each branch by month-one activation and 12-month "
                   "retention of its ICS accounts; branches with 25+ "
                   "ICS accounts"),
            "ICS by branch")
        path = chart("ics_quadrant", charts.branch_quadrant, br)
        if path:
            _fit_picture(s, path, MARGIN_L, top + 0.1, max_w=CONTENT_W,
                         max_h=4.7)
        _kicker(s)
    else:
        skipped.append("ICS by branch (fewer than 2 branches at 25+)")

    # ---- 5b. primacy: does the money go somewhere else? -------------------
    # comp_by_lens columns: lens,label,accounts,with_competitor,pct,
    #                       multi_banked_pct,dollars_per_acct,top_institution
    ci, cc = _lens("comp_by_lens", "ics"), _lens("comp_by_lens", "new_accounts")
    if ci and cc:
        head = (f"One ICS account in "
                f"{round(100 / ci[4]) if ci[4] else 0} moves money to another "
                f"institution")
        sub = (f"{ci[4]:.1f}% touch a competitor against {cc[4]:.1f}% of "
               f"accounts opened in the same twelve months -- but "
               f"${ci[6]:,.0f} an account against ${cc[6]:,.0f}. "
               f"Trying other institutions, not moving the relationship")
        s_, top = slide((head, sub), "ICS primacy")
        order = [("ics", "ICS accounts"), ("ics_ref", "ICS referral"),
                 ("ics_dm", "ICS direct mail"),
                 ("new_accounts", "Opened last 12 mo"),
                 ("all", "All accounts")]
        trows = []
        for key, lab in order:
            r = _lens("comp_by_lens", key)
            if r:
                trows.append([lab, f"{r[2]:,}", f"{r[3]:,}", f"{r[4]:.1f}%",
                              f"{r[5]:.1f}%", f"${r[6]:,.0f}",
                              str(r[7] or "--")])
        _table(s_, [["Cohort", "Accounts", "With competitor", "%",
                     "Multi-banked", "$ / acct", "Top"]] + trows,
               MARGIN_L, top + 0.15, CHART_W)
        # _text takes geometry first: (slide, left, top, width, height, text)
        _text(s_, MARGIN_L, top + 0.30 + 0.32 * (len(trows) + 1), CHART_W, 0.4,
              "a competitor is money moving out to one of the configured "
              "institutions; multi-banked is two or more of them", size=10.5)
        rail = [("Dollars out", f"${ci[6]:,.0f}",
                 f"per ICS account, vs ${cc[6]:,.0f}"),
                ("Top destination", str(ci[7] or "--"),
                 f"{ci[3]:,} of {ci[2]:,} ICS accounts")]
        dm, ref = _lens("comp_by_lens", "ics_dm"), _lens("comp_by_lens", "ics_ref")
        if dm and ref:
            rail.append(("Leakier channel",
                         "direct mail" if dm[4] > ref[4] else "referral",
                         f"{dm[4]:.1f}% DM vs {ref[4]:.1f}% referral"))
        _rail(s_, rail, top=top)
        _kicker(s_)
    else:
        skipped.append("ICS primacy (no competitor lens rows -- run the "
                       "transaction chapter with the ICS stamp present)")

    # ---- 5c. where the card actually gets used ---------------------------
    # mch_by_lens columns: lens,label,card_accounts,spend_per_acct,
    #                      txns_per_acct_per_mo,top_merchant
    mi, mc = _lens("mch_by_lens", "ics"), _lens("mch_by_lens", "new_accounts")
    if mi and mc and mc[4]:
        head = (f"ICS accounts transact {mi[4] / mc[4]:.1f} times as often as "
                f"other new accounts")
        sub = (f"{mi[4]:.1f} a month against {mc[4]:.1f}, on "
               f"{mi[2]:,} ICS card accounts -- and ${mi[3]:,.0f} a year "
               f"against ${mc[3]:,.0f}")
        s_, top = slide((head, sub), "ICS merchants")
        order = [("ics", "ICS accounts"), ("ics_ref", "ICS referral"),
                 ("ics_dm", "ICS direct mail"),
                 ("new_accounts", "Opened last 12 mo"),
                 ("all", "All accounts")]
        trows = []
        for key, lab in order:
            r = _lens("mch_by_lens", key)
            if not r:
                continue
            bh = _lens("beh_by_lens", key)
            trows.append([lab, f"{r[2]:,}", f"${r[3]:,.0f}", f"{r[4]:.1f}",
                          f"${bh[3]:,.2f}" if bh else "--",
                          str(r[5] or "--")])
        _table(s_, [["Cohort", "Card accounts", "$ / acct", "Txns / mo",
                     "Median ticket", "Top merchant"]] + trows,
               MARGIN_L, top + 0.15, CHART_W)
        # tier_bars renormalises over the rows it is handed, so passing the
        # top 8 of 11 inflated every share -- Other printed 27% against a
        # real 25.2%. Every category, and the shares are the true ones.
        cats = [[r[0], r[3]] for r in (txn.get("mch_by_category") or [])]
        if cats:
            path = chart("ics_categories", charts.tier_bars, cats,
                         size=(charts.FIG_W_FULL, 1.8))
            if path:
                _fit_picture(s_, path, MARGIN_L,
                             top + 0.15 + 0.32 * (len(trows) + 1) + 0.25,
                             max_w=CHART_W, max_h=1.75)
        rail = [("Txns a month", f"{mi[4]:.1f}", f"vs {mc[4]:.1f} other new"),
                ("Spend an account", f"${mi[3]:,.0f}", f"vs ${mc[3]:,.0f}"),
                ("Top merchant", str(mi[5] or "--"), "by transaction count")]
        bi = _lens("beh_by_lens", "ics")
        bc = _lens("beh_by_lens", "new_accounts")
        if bi and bc:
            rail.append(("Median ticket", f"${bi[3]:,.2f}",
                         f"vs ${bc[3]:,.2f} -- more trips, smaller baskets"))
        _rail(s_, rail, top=top)
        _kicker(s_)
    else:
        skipped.append("ICS merchants (no merchant lens rows)")


    # ---- 5d. the two channels, side by side ------------------------------
    src = {r[0]: r for r in (m.get("ics_cmp_source") or [])}
    if "REF" in src and "DM" in src:
        ref, dm = src["REF"], src["DM"]
        tot = (ref[1] or 0) + (dm[1] or 0)
        base = None
        m1r = next((r for r in (m.get("ics_cmp_activation_cum") or [])
                    if r[0] == 1), None)
        if m1r and m1r[2] is not None:
            base = m1r[2]
        head = (f"Referral activates at {ref[2]:.0f}%, direct mail at "
                f"{dm[2]:.0f}%")
        s_, top = slide(
            (head, f"referral is {100 * (ref[1] or 0) / tot:.0f}% of ICS "
                   f"volume and the wider margin; both clear the non-ICS "
                   f"baseline" if tot else head), "ICS channel")
        panels = []
        for name, r in (("Referral", ref), ("Direct mail", dm)):
            stats = [(f"{r[3]:.1f}%", "still open at 12 months")] \
                if r[3] is not None else []
            stats.append((f"{100 * (r[1] or 0) / tot:.0f}%",
                          "of all ICS volume") if tot else ("--", ""))
            panels.append((name, f"{r[1]:,} accounts", r[2], stats))
        path = chart("ics_channel", charts.split_panels, panels,
                     baseline=base,
                     baseline_label=(f"non-ICS baseline {base:.1f}%"
                                     if base else ""))
        if path:
            _fit_picture(s_, path, MARGIN_L, top + 0.1, max_w=CONTENT_W,
                         max_h=3.5)
        _kicker(s_)

    # ---- 5e. who the programme brings in ----------------------------------
    # The chapter could show ICS holding less money and never say why. These
    # are the explanation: a programme acquiring younger, newer, thinner
    # accounts reads exactly like that money column does.
    comp_rows = []
    for key, label in (("ics_cmp_tenure", "Tenure"),
                       ("ics_cmp_holder_age", "Account holder age"),
                       ("ics_cmp_product", "Product")):
        rows = m.get(key) or []
        if rows:
            comp_rows.append((key, label, rows))
    if comp_rows:
        key, label, rows = comp_rows[0]
        lead = max(rows, key=lambda r: (r[1] or 0) - (r[2] or 0))
        base = m.get(f"{key}_base") or []
        base_txt = (f"{base[0]:,} ICS and {base[1]:,} control carrying a value"
                    if len(base) == 2 else "both cohorts")
        s_, top = slide(
            (f"ICS skews to {lead[0].lower()} — {lead[1]:.0f}% against "
             f"{lead[2]:.0f}%",
             f"{label.lower()} against same-window non-ICS openings; "
             f"{base_txt}. This is why the money column runs low"),
            "ICS composition")
        # paired_hbars wants [label, a, a_n, b, b_n]; the base is the
        # cohort size, the same under every band (#245: three-field rows
        # raised IndexError and the slide was skipped)
        a_n, b_n = (base[0], base[1]) if len(base) == 2 else (0, 0)
        path = chart(f"ics_comp_{key}", charts.paired_hbars,
                     [[r[0], r[1], a_n, r[2], b_n] for r in rows],
                     "ICS", "non-ICS")
        if path:
            _fit_picture(s_, path, MARGIN_L, top + 0.1,
                         max_w=CONTENT_W - RAIL_W, max_h=4.4)
        rail = []
        biz = m.get("ics_cmp_business_pct")
        if biz and biz[0] is not None:
            rail.append(("Business", f"{biz[0]:.0f}%", f"vs {biz[1]:.0f}% book"))
        for other_key, other_label, other_rows in comp_rows[1:3]:
            top_row = max(other_rows, key=lambda r: r[1] or 0)
            rail.append((other_label, f"{top_row[1]:.0f}%",
                         f"{top_row[0]} — vs {top_row[2]:.0f}%"))
        if rail:
            _rail(s_, rail, top=top)
        _kicker(s_)
    else:
        skipped.append("ICS composition (no tenure, age or product cut)")

    # ---- 5f. activation personas ------------------------------------------
    personas = m.get("ics_cmp_personas") or []
    if personas:
        pbase = m.get("ics_cmp_personas_base") or []
        fast = next((r for r in personas if r[0] == "Fast activator"), None)
        never = next((r for r in personas if r[0] == "Never activated"), None)
        if fast and fast[1] is not None and fast[2] is not None:
            head = (f"{fast[1]:.0f}% of ICS accounts are fast activators, "
                    f"against {fast[2]:.0f}%")
        else:
            head = "How each cohort starts, four ways"
        sub = ("swiping in the opening month and still swiping at month "
               "three; an account too new to have reached month three is "
               "excluded, not counted as never activating")
        if len(pbase) == 2:
            sub += f" — {pbase[0]:,} ICS and {pbase[1]:,} control"
        s_, top = slide((head, sub), "ICS activation personas")
        a_n, b_n = (pbase[0], pbase[1]) if len(pbase) == 2 else (0, 0)
        path = chart("ics_personas", charts.paired_hbars,
                     [[r[0], r[1], a_n, r[2], b_n] for r in personas],
                     "ICS", "non-ICS")
        if path:
            _fit_picture(s_, path, MARGIN_L, top + 0.1,
                         max_w=CONTENT_W - RAIL_W, max_h=4.4)
        # The channel split is the funding question: DM and REF are the two
        # things the client can actually spend money on.
        crows = m.get("ics_personas_by_channel") or []
        cols = m.get("ics_personas_by_channel_columns") or []
        rail = []
        if crows and "Fast activator" in cols:
            fi, ni = cols.index("Fast activator"), cols.index("Never activated")
            for r in crows:
                rail.append((r[0], f"{r[fi]:.0f}% fast",
                             f"{r[ni]:.0f}% never — {r[1]:,} accounts"))
        if never and never[1] is not None:
            rail.append(("Never activated", f"{never[1]:.0f}%",
                         f"vs {never[2]:.0f}% of the book"))
        if rail:
            _rail(s_, rail, top=top)
        _kicker(s_)
    else:
        skipped.append("ICS personas (cohort too thin to classify)")

    # ---- 6. retention -----------------------------------------------------
    surv = m.get("ics_cmp_survival_curve") or {}
    i12 = surv.get("months", []).index(12) if 12 in surv.get("months", []) \
        else None
    if i12 is not None and surv["ics"][i12] is not None:
        s12, n12 = surv["ics"][i12], surv["non"][i12]
        head = f"ICS keeps {s12:.0f}% of its accounts at a year"
        sub = None
        if n12 is not None:
            pp = s12 - n12
            sub = (f"{abs(pp):.1f} points {'above' if pp >= 0 else 'below'} "
                   f"same-month non-ICS openings; bases "
                   f"{n_ics:,} ICS / {n_non:,} non-ICS")
        s, top = slide((head, sub), "ICS retention")
        path = chart("ics_survival", charts.pair_lines, surv["months"],
                     surv["ics"], surv["non"], "ICS", "non-ICS",
                     ylabel="% still open", pct=True)
        if path:
            _fit_picture(s, path, MARGIN_L, top + 0.1, max_w=CONTENT_W - 3.4,
                         max_h=3.4)
        cdur = [r for r in (m.get("ics_cmp_closure_duration") or []) if r[1]]
        if cdur:
            path = chart("ics_closures", charts.tier_bars, cdur,
                         size=(charts.FIG_W_FULL, 1.9))
            if path:
                _fit_picture(s, path, MARGIN_L, top + 3.55,
                             max_w=CHART_W, max_h=1.85)
        rail = []
        for source, n, m1, s12s in (m.get("ics_cmp_source") or []):
            if s12s is not None:
                rail.append((f"{source} at 12 mo", f"{s12s:.0f}%",
                             f"{n:,} accounts"))
        # the 6/12/24-month horizons against same-month non-ICS openings
        # were CSV-only (#245); an immature horizon reads n/a, never a guess
        for horizon, ics_pct, non_pct in (m.get("ics_survival") or []):
            rail.append((horizon, "n/a" if ics_pct is None else f"{ics_pct:.0f}%",
                         "not matured" if ics_pct is None else
                         (f"vs {non_pct:.0f}% non-ICS" if non_pct is not None else "ICS")))
        if rail:
            _rail(s, rail[:5], top=top)
        _kicker(s)
    else:
        skipped.append("ICS retention (no matured 12-month base)")

    # ---- 7. exec closer ---------------------------------------------------
    chips = []
    chips.append(["green" if share >= 10 else "amber",
                  f"{n_ics:,} accounts",
                  f"Acquisition: {share:.0f}% of the window's openings"])
    if t.get("ics_median_mo") is not None \
            and t.get("non_median_mo") is not None:
        faster = t["ics_median_mo"] <= t["non_median_mo"]
        chips.append(["green" if faster else "red",
                      f"{t['ics_median_mo']:g} vs {t['non_median_mo']:g} mo",
                      "Speed: median time to first swipe"])
    if u.get("ics_mean_swipes") is not None and u.get("non_mean_swipes"):
        r = u["ics_mean_swipes"] / u["non_mean_swipes"]
        chips.append(["green" if r >= 1 else "red", f"{r:.1f}x the book",
                      "Usage: swipes per active account"])
    if i12 is not None and surv["ics"][i12] is not None \
            and surv["non"][i12] is not None:
        pp = surv["ics"][i12] - surv["non"][i12]
        chips.append(["green" if pp >= 0 else "red",
                      f"{pp:+.1f} pts at 12 mo",
                      f"Retention: {surv['ics'][i12]:.0f}% still open"])
    m1c = next((r for r in (m.get("ics_cmp_activation_cum") or [])
                if r[0] == 1), None)
    if m1c and m1c[1] is not None and m1c[2] is not None:
        chips.append(["green" if m1c[1] >= m1c[2] else "red",
                      f"{m1c[1] - m1c[2]:+.0f} pts at M1",
                      f"Activation: {m1c[1]:.0f}% swipe in month one"])
    ci_ = _lens("comp_by_lens", "ics")
    cc_ = _lens("comp_by_lens", "new_accounts")
    if ci_ and cc_:
        chips.append(["green" if ci_[4] <= cc_[4] else "amber",
                      f"{ci_[4]:.1f}% vs {cc_[4]:.1f}%",
                      "Primacy: money moving to a competitor"])
    if q.get("ics_ars_response_pct") is not None \
            and q.get("non_ars_response_pct") is not None:
        ahead = q["ics_ars_response_pct"] >= q["non_ars_response_pct"]
        chips.append(["green" if ahead else "amber",
                      f"{q['ics_ars_response_pct']:.0f}% vs "
                      f"{q['non_ars_response_pct']:.0f}%",
                      "Synergy: ICS accounts respond to ARS offers"])
    if len(chips) >= 3:
        greens = sum(1 for c in chips if c[0] == "green")
        if m1c and m1c[1] is not None and m1c[2] is not None:
            # RPE: v5 wrote "{gap} points faster" for any sign, so a lower month-one rate read
            # as "-2 points faster" (1776, 2026.10); the gap is a rate, worded by its sign
            gap = round(m1c[1] - m1c[2])
            pace = (f"activates {gap} points more of them in month one" if gap > 0 else
                    f"activates {-gap} points fewer of them in month one" if gap < 0 else
                    "activates them in month one at the book's rate")
            head = f"ICS is {share:.0f}% of every account opened, and {pace}"
        elif greens == len(chips):
            head = (f"{len(chips)} measures, {greens} green: the program "
                    f"leads on every one")
        else:
            head = f"{greens} of {len(chips)} ICS measures run ahead of the book"
        s, top = slide(
            (head, f"{stamped:,} accounts stamped; every value against "
                   f"same-window non-ICS openings, detail on the chapter's "
                   f"own slides"),
            "ICS summary")
        path = chart("ics_chips", charts.rag_chips,
                     [[c[0], c[1], c[2]] for c in chips])
        if path:
            _fit_picture(s, path, MARGIN_L, top + 0.1, max_w=CONTENT_W,
                         max_h=4.6)
        _kicker(s)
    else:
        skipped.append("ICS summary (too few computed measures)")

    return skipped
