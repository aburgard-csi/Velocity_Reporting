"""Render an AnalysisResult as something a CSM can read.

The console summary shows status and warnings. This shows the numbers, grouped
the way the deck is, so figures can be sanity-checked before anything ships.
"""

from __future__ import annotations

from typing import Any

from ..core.deposits import MIN_MATCH_PCT


PIN_HEAVY_DISPLAY = 80
SIG_RISK_DISPLAY = 40


def _n(v: Any, width: int = 0) -> str:
    if v is None:
        return "--"
    if isinstance(v, float):
        return f"{v:,.1f}".rjust(width)
    if isinstance(v, int):
        return f"{v:,}".rjust(width)
    return str(v).rjust(width)


def _line(label: str, value: Any, suffix: str = "") -> str:
    return f"  {label:<28} {_n(value, 12)}{suffix}"


def _rate_cell(pct: Any, width: int = 8) -> str:
    """A rate column, or a dash where there was nobody to measure.

    attrition._pct returns None for an empty denominator so a structural zero
    cannot be read as a measured one. The row still prints: n and closed are
    real information either way.
    """
    return f"{pct:>{width - 1}.1f}%" if pct is not None else f"{'--':>{width}}"


def _rule(title: str) -> str:
    return f"\n{title}\n" + "-" * 60


def report(result, top_branches: int = 8) -> str:
    """Full metrics report as text."""
    m = result.metrics
    if not m:
        L = [f"{result.client_id}  {result.analysis}  status: {result.status.upper()}",
             "no metrics computed -- why:"]
        L += [f"  ERROR  {e}" for e in (result.errors or [])] or ["  (no error recorded)"]
        L += [f"  WARN   {w}" for w in (result.warnings or [])[:6]]
        return "\n".join(L)

    L: list[str] = []
    A = L.append

    A("=" * 60)
    A(f"{result.client_id}  {result.client_name or ''}".strip())
    A(f"period {result.period}   data through {result.data_month}   "
      f"({result.duration_s or 0:.0f}s)")
    A("=" * 60)

    if m.get("gt_deferred_balance") is not None:
        A(_rule("2:1 GUARANTEE   (deferral tracker: "
                + str(m.get("gt_source", "?")) + ")"))
        A(_line("status", str(m.get("gt_state", "?")),
                f"  through {m.get('gt_latest_month', '?')}"))
        A(_line("revenue, tracked to date", f"${m.get('gt_revenue_ltd', 0):,.0f}"))
        A(_line("fees paid / billed",
                f"${m.get('gt_paid_ltd', 0):,.0f} / "
                f"${m.get('gt_charges_ltd', 0):,.0f}"))
        A(_line("deferred balance", f"${m.get('gt_deferred_balance', 0):,.0f}",
                "  forgiven at contract end unless drawn down"))
        if m.get("gt_ratio_latest") is not None:
            A(_line("latest month revenue vs billing",
                    f"{m['gt_ratio_latest']:.2f}x", "  releases at 2.00x"))
        for mth, rev, charges, paid, deferred, running in \
                (m.get("gt_months") or [])[-3:]:
            A(f"    {mth:<9}${rev:>10,.0f} rev ${paid:>10,.0f} paid "
              f"${deferred:>10,.0f} deferred ${running:>11,.0f} running")
        A("    the client pays half of revenue while under the 2x mark;")
        A("    with a tracker present, this math IS the client's economics")
        A("")

    if m.get("wb_profit_ltd") is not None:
        A(_rule("PROGRAM P&L   (ARS Workbook: " + str(m.get("wb_source", "?")) + ")"))
        A(_line("program revenue, LTD", f"${m.get('wb_revenue_ltd', 0):,}"))
        A(_line("program fees, LTD", f"${abs(m.get('wb_costs_ltd') or 0):,}"))
        A(_line("program profit, LTD", f"${m['wb_profit_ltd']:,}"))
        if m.get("wb_months_in_program"):
            A(_line("months in program / mailings",
                    f"{m['wb_months_in_program']} / {m.get('wb_mailings_to_date', '?')}"))
        if m.get("wb_profit_month") is not None:
            A(_line("latest month profit", f"${m['wb_profit_month']:,}"))
        if m.get("wb_responders_latest"):
            mo, nresp = m["wb_responders_latest"]
            A(_line("program responders (workbook)", f"{nresp:,} in {mo}",
                    "  all active mailings combined -- NOT one offer's count"))
        waves = m.get("wb_waves") or []
        for tag, mailed, resp, cum, *_rest in waves[-4:]:
            A(f"    {tag:<8}{(f'{mailed:,}' if mailed else '-'):>9} mailed"
              f"{(f'{resp}%' if resp is not None else '-'):>8}"
              f"{(f'${cum:,}' if cum is not None else '-'):>13} window rev")
        A("")
        # the two revenue frames, bridged (issue #40): booked ledger
        # revenue and DiD estimates never tie by design -- say so where
        # both are on the page
        ba = m.get("ba_lift_net")
        if ba is not None:
            A(_rule("REVENUE FRAMES   booked vs incremental (never tie by design)"))
            A(_line("booked, LTD (workbook ledger)",
                    f"${m.get('wb_revenue_ltd', 0):,}",
                    "  gross, all revenue types incl. NSF/OD"))
            A(_line("DiD lift per responder-month", f"${ba:,.0f}",
                    "  spend, net of control"))
            ic = m.get("segment_ic_rate")
            if ic:
                A(_line(f"as interchange (IC {ic})", f"${ba * ic:,.2f}",
                        "  per responder-month"))
            A("    why: fee income is booked-only; gross vs net of control;")
            A("    cumulative window vs monthly run rate; different denominators")
            A("")

    points = m.get("syn_talking_points") or []
    card = m.get("syn_scorecard") or []
    opps = m.get("syn_opportunities") or []
    if points or card or opps:
        A(_rule("SUMMARY   what to say, and where it comes from"))
        for p_ in points:
            A(f"  - {p_}")
        if card:
            counts = m.get("syn_scorecard_counts") or {}
            A("")
            A(f"  scorecard   {counts.get('green', 0)} green  {counts.get('amber', 0)} amber  "
              f"{counts.get('red', 0)} red   (each metric vs its own comparator)")
            for metric, value, unit, comparator, delta, rag in card:
                d = f"{delta:>+7.1f}" if delta is not None else f"{'':>7}"
                A(f"    {rag:<6}{metric:<42}{value:>9}{unit:<6}{d}  {comparator}")
        if opps:
            A("")
            A("  opportunity map   ranked by $/yr; items overlap, not additive")
            A(f"    {'':<68}{'accounts':>9}{'$/yr':>12}")
            for o in opps[:8]:
                val = f"{o['value']:>12,}" if o["kind"] != "count" else f"{'':>12}"
                tag = "" if o["kind"] == "revenue" else f"  ({o['kind']})"
                A(f"    {o['label'][:66]:<68}{o['n']:>9,}{val}{tag}")
        w1, w2 = m.get("syn_whatif_dctr_plus5"), m.get("syn_whatif_rege_plus5")
        if w1 or w2:
            A("")
            if w1:
                A(f"  what if take rate rose {w1['pts']:.0f} pts: "
                  f"{w1['cards']:,} cards, ${w1['value']:,}/yr")
            if w2:
                A(f"  what if Reg E opt-in rose {w2['pts']:.0f} pts: "
                  f"{w2['optins']:,} opt-ins, ${w2['value']:,}/yr")
        bs = m.get("syn_branch_scorecard") or []
        if bs:
            A("")
            A("  branch scorecard")
            A(f"    {'branch':<18}{'elig':>7}{'take':>7}{'Reg E':>7}{'$/acct':>8}{'close':>7}{'1st-yr':>7}")
            fm = lambda v, w, p=1: (f"{v:>{w}.{p}f}" if isinstance(v, (int, float)) else f"{'-':>{w}}")
            for name, elig, take, rege, val, close, fy in bs[:12]:
                A(f"    {str(name)[:17]:<18}{elig:>7,}{fm(take,7)}{fm(rege,7)}{fm(val,8,0)}{fm(close,7)}{fm(fy,7)}")

    A(_rule("POPULATION"))
    A(_line("total accounts", m.get("n_total")))
    A(_line("open", m.get("n_open")))
    A(_line("eligible", m.get("n_eligible")))
    A(_line("eligible personal", m.get("n_eligible_personal")))
    A(_line("eligible business", m.get("n_eligible_business")))
    A(_line("eligible w/debit", m.get("n_eligible_with_debit")))
    A(_line("eligible personal w/debit", m.get("n_personal_with_debit")))
    if m.get("n_total") and m.get("n_eligible"):
        A(_line("eligibility rate",
                round(100 * m["n_eligible"] / m["n_total"], 1), " %"))

    funnel = m.get("eligibility_funnel") or []
    if funnel:
        A(_rule("ELIGIBILITY FUNNEL"))
        A(f"    {'stage':<24}{'accounts':>10}{'of total':>10}{'drop':>8}")
        for label, count, pct, drop in funnel:
            d = f"{drop:>7.1f}%" if drop else " " * 8
            A(f"    {label:<24}{count:>10,}{pct:>9.1f}%{d}")
        if m.get("biggest_dropoff"):
            A(f"    biggest drop: {m['biggest_dropoff'][0]} "
              f"({m['biggest_dropoff'][1]}%)")

    stat_mix = m.get("stat_code_mix") or []
    if stat_mix:
        A(_rule("BOOK COMPOSITION"))
        A(f"    {'status':<30}{'accounts':>10}{'share':>8}  eligible")
        for label, n, pct, elig_flag in stat_mix[:10]:
            A(f"    {str(label)[:28]:<30}{n:>10,}{pct:>7.1f}%  {'yes' if elig_flag else '-'}")
    prod_mix = m.get("product_mix") or []
    if prod_mix:
        A("")
        A(f"  open accounts by product   personal {m.get('product_mix_personal_pct', 0)}%")
        A(f"    {'product':<30}{'accounts':>10}{'share':>8}{'business':>10}  eligible")
        for label, n, pct, biz, elig_flag in prod_mix:
            A(f"    {str(label)[:28]:<30}{n:>10,}{pct:>7.1f}%{biz:>9.1f}%  {'yes' if elig_flag else '-'}")
        if m.get("product_mix_other_n"):
            A(f"    {'other':<30}{m['product_mix_other_n']:>10,}")

    A(_rule("DEBIT CARD TAKE RATE   base: eligible"))
    A(_line("overall (eligible)", m.get("dctr_overall"), " %"))
    A(_line("all open (reference)", m.get("dctr_open"), " %"))
    A(_line("  eligible advantage", m.get("dctr_open_vs_eligible_pp"), " pts"))
    A(_line("L12M (eligible)", m.get("dctr_l12m"), " %"))
    A(_line("  vs historical", m.get("dctr_l12m_vs_hist_pp"), " pts"))
    A(_line("personal", m.get("dctr_personal"), " %"))
    A(_line("business", m.get("dctr_business"), " %"))
    if m.get("dctr_branch_best"):
        b, w_ = m["dctr_branch_best"], m["dctr_branch_worst"]
        A("")
        A(f"  best  {b[0]:<20}{b[1]:>7.1f}%  (n={b[2]:,})")
        A(f"  worst {w_[0]:<20}{w_[1]:>7.1f}%  (n={w_[2]:,})")
        A(_line("  spread", m.get("dctr_branch_spread_pp"), " pts"))
    branches = m.get("take_branch") or []
    if branches:
        A("")
        A(f"  by branch (top {top_branches} by size)")
        A(f"    {'branch':<26}{'cards':>8}{'elig':>9}{'rate':>8}")
        for name, cards, elig, pct in branches[:top_branches]:
            A(f"    {str(name)[:26]:<26}{cards:>8,}{elig:>9,}{pct:>7.1f}%")
        if len(branches) > top_branches:
            A(f"    ... {len(branches) - top_branches} more")

    for key, title, cols in (
        ("dctr_holder_age", "  take rate by holder age", ("band", "accts", "cards", "rate")),
        ("dctr_account_age", "  take rate by account age", ("band", "accts", "cards", "rate")),
        ("dctr_balance", "  take rate by balance", ("band", "accts", "cards", "rate")),
    ):
        rows = m.get(key) or []
        if rows:
            A("")
            A(title)
            A(f"    {cols[0]:<18}{cols[1]:>10}{cols[2]:>9}{cols[3]:>8}")
            for label, n, cards_, pct in rows:
                A(f"    {label:<18}{n:>10,}{cards_:>9,}{pct:>7.1f}%")

    season = m.get("dctr_seasonality") or []
    if season:
        A("")
        A(f"  take rate by month opened (all years)   spread {m.get('dctr_seasonality_spread_pp')} pts")
        A("    " + "".join(f"{r[0]:>6}" for r in season))
        A("    " + "".join(f"{r[3]:>5.0f}%" for r in season))
    bm = m.get("dctr_branch_monthly") or []
    if bm:
        tags = m.get("dctr_monthly_months") or []
        A("")
        A("  L12M take rate by branch x month opened (top branches)")
        A(f"    {'branch':<16}{'n':>6}" + "".join(f"{t:>7}" for t in tags))
        fmt = lambda v: f"{v:>6.0f}%" if v is not None else f"{'-':>7}"
        for row in bm:
            A(f"    {str(row[0])[:15]:<16}{row[1]:>6,}" + "".join(fmt(v) for v in row[2:]))
        tot = m.get("dctr_monthly_totals") or []
        if tot:
            A(f"    {'all branches':<16}{'':>6}" + "".join(fmt(v) for v in tot))

    summary = m.get("dctr_summary") or []
    if summary:
        A("")
        A("  summary")
        A(f"    {'base':<20}{'total':>10}{'w/debit':>10}{'rate':>8}")
        for label, total_, wd, _wo, pct in summary:
            A(f"    {label:<20}{total_:>10,}{wd:>10,}{pct:>7.1f}%")

    tiers = m.get("swipe_tier") or []
    if tiers:
        A(_rule(f"SWIPE SEGMENTATION   window: "
                f"{', '.join(m.get('swipe_window', []))}"))
        A(f"    {'tier':<18}{'accounts':>10}{'share':>8}{'spend':>14}")
        total = sum(r[1] for r in tiers) or 1
        for label, count, spend, swipes, items in tiers:
            A(f"    {label:<18}{count:>10,}{100*count/total:>7.1f}%{spend:>14,}")

    A(_rule("REG E   base: eligible personal w/debit"))
    A(f"  column of record: {m.get('rege_column')}")
    A("  base = eligible -> personal -> holds a debit card")
    A(_line("base accounts", m.get("rege_pool")))
    A(_line("opted in", m.get("rege_in")))
    A(_line("opted out", m.get("rege_out")))
    A(_line("default", m.get("rege_default")))
    A(_line("no election / blank", m.get("rege_no")))
    A(_line("opt-in, all base", m.get("rege_pct"), " %"))
    A(_line("opt-in, of elected", m.get("rege_pct_of_elected"), " %"))
    A(_line("L12M opt-in", m.get("rege_l12m_pct"), " %"))
    A(_line("  vs historical", m.get("rege_l12m_vs_hist_pp"), " pts"))
    A(_line("24-mo slope", m.get("rege_trend_slope_pp_per_mo"), " pp/mo"))
    if m.get("rege_branch_best"):
        b, w_ = m["rege_branch_best"], m["rege_branch_worst"]
        A("")
        A(f"  best  {b[0]:<20}{b[1]:>7.1f}%  (n={b[2]:,})")
        A(f"  worst {w_[0]:<20}{w_[1]:>7.1f}%  (n={w_[2]:,})")
    vintage = m.get("rege_vintage") or []
    if vintage:
        A("")
        A("  by account vintage")
        for row in vintage[-8:]:
            year, n, pct = row[0], row[1], row[-1]
            A(f"    {year:<26}{n:>8,}{pct:>7.1f}%")

    if m.get("od_eligible_n") is not None:
        A(_rule("OVERDRAFT LIMITS   base: eligible"))
        A(f"  column of record: {m.get('od_limit_column')}")
        if m.get("od_eligibility_informative"):
            A("  blank = not OD-eligible, 0 = eligible with no limit")
            A(_line("OD-eligible", m.get("od_eligible_n")))
            A(_line("  of eligible", m.get("od_eligible_pct"), " %"))
            A(_line("  personal / business",
                    f"{m.get('od_eligible_personal_pct')} / "
                    f"{m.get('od_eligible_business_pct')}", " %"))
            A(_line("with a limit", m.get("od_with_limit_n")))
            A(_line("  of OD-eligible", m.get("od_with_limit_pct"), " %"))
        else:
            A(f"  limit populated for all eligible accounts "
              f"({m.get('od_blank_n', 0):,} blank); eligibility not readable here")
            A(_line("with a limit", m.get("od_with_limit_n")))
            A(_line("  of eligible", m.get("od_with_limit_pct_of_eligible"), " %"))
        A(_line("mean / median limit",
                f"{m.get('od_limit_mean', 0):,.0f} / {m.get('od_limit_median', 0):,.0f}",
                " $"))
        for amount, count, pct in (m.get("od_limit_values") or []):
            A(f"    ${amount:<12,.0f}{count:>10,}{pct:>7.1f}%")
        if m.get("od_limit_other_n"):
            A(f"    {'other (' + str(m.get('od_limit_distinct_n', 0) - len(m.get('od_limit_values') or [])) + ' values)':<13}"
              f"{m['od_limit_other_n']:>10,}{m['od_limit_other_pct']:>7.1f}%")
        if m.get("od_rege_base"):
            A("")
            A("  cardholders (eligible personal w/debit, OD-eligible)")
            A(_line("base", m.get("od_rege_base")))
            A(_line("opted in", m.get("od_optin_n")))
            A(_line("  of base", m.get("od_optin_pct"), " %"))
            A(_line("not opted in", m.get("od_eligible_not_optin_n")))
            A(_line("opted in, no limit", m.get("od_optin_no_limit_n")))
            A(_line("12-mo items/acct, opted in",
                    m.get("od_items_per_acct_optin")))
            A(_line("12-mo items/acct, not opted",
                    m.get("od_items_per_acct_not_optin")))
            if m.get("od_fee_revenue_l12m") is not None:
                A(_line("fee revenue, 12 mo",
                        round(m.get("od_fee_revenue_l12m")), " $"))
                A(_line("  from opted-in accounts",
                        m.get("od_fee_optin_share_pct"), " %"))

    if m.get("mig_base"):
        A(_rule(f"SWIPE-TIER MIGRATION   {m.get('mig_first')} -> {m.get('mig_latest')}"))
        A(f"  tier = trailing-3 swipes; base = eligible cardholders open at "
          f"{m.get('mig_first')}")
        A(f"  excluded: {m.get('mig_excluded_no_card_n', 0):,} without a card, "
          f"{m.get('mig_excluded_opened_since_n', 0):,} opened since {m.get('mig_first')}")
        A(_line("base", m.get("mig_base")))
        A(_line("moved up", m.get("mig_up_n")))
        A(_line("  of base", m.get("mig_up_pct"), " %"))
        A(_line("same tier", m.get("mig_same_pct"), " %"))
        A(_line("moved down", m.get("mig_down_pct"), " %"))
        A(_line("net tier steps / acct", m.get("mig_net_steps")))
        A(_line("non-users then, swiping now", m.get("mig_entered_use_n")))
        A(_line("  of non-users then", m.get("mig_entered_use_pct"), " %"))
        A("")
        A(f"    {'tier':<12}{'then':>8}{'now':>8}{'then %':>8}{'now %':>8}")
        for (t, n1, p1), (_, n2, p2) in zip(m.get("mig_dist_first", []),
                                           m.get("mig_dist_latest", [])):
            A(f"    {t:<12}{n1:>8,}{n2:>8,}{p1:>7.1f}%{p2:>7.1f}%")
        groups = m.get("mig_by_group") or []
        if groups:
            A("")
            A(f"    {'by response status':<22}{'n':>8}{'up':>7}{'same':>7}{'down':>7}{'net':>7}")
            for g, n_, up, same, down, net in groups:
                A(f"    {g:<22}{n_:>8,}{up:>6.1f}%{same:>6.1f}%{down:>6.1f}%{net:>+7.2f}")
            if m.get("mig_responder_up_advantage_pp") is not None:
                A(_line("responder up-rate advantage",
                        m.get("mig_responder_up_advantage_pp"), " pts"))

    A(_rule("MAILER"))
    A(_line("latest completed", m.get("latest_mailing")))
    A(_line("  mailed", m.get("latest_mailed")))
    A(_line("  responders", m.get("latest_responders")))
    A(_line("  response rate", m.get("latest_resprate"), " %"))
    if m.get("in_flight_mailings"):
        A(f"  in flight (no responses yet): "
          f"{', '.join(m['in_flight_mailings'])}")
    A(_line("mean rate, all offers", m.get("resprate_mean"), " %"))
    A(_line("trend per offer", m.get("resprate_slope_pp_per_wave"), " pp"))
    A(_line("total responders", m.get("reach_total")))
    A(_line("reach of eligible", m.get("reach"), " %"))
    A(_line("reach of mailed", m.get("reach_of_mailed"), " %"))
    A(_line("repeat responders", m.get("depth_repeat")))
    A(_line("  as % of responders", m.get("depth_repeat_pct"), " %"))
    if m.get("activation_l12m_n") is not None:
        A(_line("first swipe in L12M", m.get("activation_l12m_n")))
        A(_line("  new accounts (onboarding)", m.get("activation_new_account_n")))
        A(_line("  existing accounts", m.get("activation_existing_n")))
        A(_line("    mailed on/before it", m.get("activation_program_n")))
        A(_line("    never mailed (organic)", m.get("activation_organic_n")))
        A(_line("    program share", m.get("activation_program_pct"), " %"))
    if m.get("responder_spend_share_pct") is not None:
        A(_line("responders: % of eligible", m.get("responder_share_of_eligible_pct"), " %"))
        A(_line("responders: % of L12M spend", m.get("responder_spend_share_pct"), " %"))
    campaigns = m.get("campaign_rates") or []
    if campaigns:
        A("")
        A(f"    {'campaign':<18}{'mailed':>10}{'resp':>9}{'rate':>8}")
        for tag, mailed, resp, pct in campaigns:
            A(f"    {tag:<18}{mailed:>10,}{resp:>9,}{pct:>7.1f}%")

    tiers_seen = m.get("response_tiers_observed") or []
    if tiers_seen:
        A("")
        A(f"  response tiers observed: {', '.join(tiers_seen)}")

    tc = m.get("transition_counts") or {}
    if tc:
        A("")
        A(f"  offer transition {' -> '.join(m.get('transition_window', []))}")
        A(f"    {'responded prior offer only':<30}{tc['responded_prior_only']:>8,}")
        A(f"    {'responded current offer only':<30}{tc['responded_current_only']:>8,}")
        A(f"    {'responded both':<30}{tc['responded_both']:>8,}")
        if m.get("responded_consecutive_waves") is not None:
            A(f"    {'responded in back-to-back offers':<30}"
              f"{m['responded_consecutive_waves']:>8,}  (all waves)")

    tm = m.get("transition_matrix") or {}
    if tm.get("rows"):
        A("")
        A("    tier transition (rows = prior wave, cols = current)")
        cols = tm["columns"]
        A("      " + "".join(f"{c[:8]:>10}" for c in [""] + cols))
        for row in tm["rows"]:
            A("      " + f"{str(row[0])[:8]:>10}"
              + "".join(f"{v:>10,}" for v in row[1:]))

    groups = m.get("group_transitions") or []
    if groups:
        A("")
        A("    group movement (NU 5+ and TH are responses; NU 1-4 is tracked)")
        for label, n in groups:
            flag = "  <- not possible by design" if (
                label in ("NU -> NU", "TH -> TH") and n) else ""
            A(f"    {label:<24}{n:>10,}{flag}")

    profile = m.get("responder_profile") or {}
    if profile:
        A("")
        A(f"  responder vs non-responder")
        A(f"    {'metric':<24}{'resp':>12}{'non':>12}")
        for key, label in (("balance_median", "median balance"),
                           ("holder_age_median", "median holder age"),
                           ("debit_pct", "debit %"),
                           ("spend_per_mo", "spend/mo")):
            if key in profile:
                r_, n_ = profile[key]
                A(f"    {label:<24}{r_:>12,}{n_:>12,}")

    offsets = m.get("cohort_offsets") or []
    if offsets:
        A(_rule("COHORT TRAJECTORY   aligned to mail month (0)"))
        n = m.get("cohort_n", {})
        A(f"  pooled across {len(m.get('cohort_waves', []))} waves  |  "
          f"responders {n.get('responders', 0):,}  "
          f"mailed non-resp {n.get('mailed_nonresp', 0):,}  "
          f"not mailed {n.get('not_mailed', 0):,}")

        spend = m.get("cohort_spend", {})
        idx = m.get("cohort_indexed", {})
        # Full lookback in its own block -- the combo chart cannot show this
        # much history, but the long view is where the selection dip shows up.
        show = [o for o in offsets if -6 <= o <= 12]
        wide = [o for o in offsets if o < -6]
        bw = m.get("baseline_windows", {})
        if bw:
            A(f"  baselines: program (offer sizing) {bw.get('program')}  |  "
              f"measurement {bw.get('measurement')}")
        if m.get("selection_dip_pct") is not None:
            A(f"  selection dip: trailing-3 spend is "
              f"{m['selection_dip_pct']:+.1f}% vs the 12-month normal "
              f"(${m.get('selection_dip_abs', 0):+,.0f}/mo)")

        if wide:
            A("")
            A(f"  extended lookback ({min(wide):+} to -7), avg monthly spend")
            A("    offset " + "".join(f"{o:>+7}" for o in wide))
            for key, label in (("responders", "responder"),
                               ("mailed_nonresp", "mailed non-r"),
                               ("not_mailed", "not mailed")):
                vals = (m.get("cohort_spend") or {}).get(key) or []
                cells = "".join(
                    f"{vals[offsets.index(o)]:>7,.0f}"
                    if offsets.index(o) < len(vals)
                    and vals[offsets.index(o)] is not None
                    else f"{'--':>7}" for o in wide)
                A(f"    {label:<10}" + cells)
        A("")
        A("  average monthly spend ($)")
        A("    offset " + "".join(f"{o:>+7}" for o in show))
        for key, label in (("responders", "responder"),
                           ("mailed_nonresp", "mailed non-r"),
                           ("not_mailed", "not mailed")):
            vals = spend.get(key) or []
            cells = "".join(
                f"{vals[offsets.index(o)]:>7,.0f}"
                if offsets.index(o) < len(vals) and vals[offsets.index(o)] is not None
                else f"{'--':>7}" for o in show)
            A(f"    {label:<10}" + cells)

        if idx:
            A("")
            A("  indexed to each cohort's own pre-mail baseline (= 100)")
            A("    offset " + "".join(f"{o:>+7}" for o in show))
            for key, label in (("responders", "responder"),
                               ("mailed_nonresp", "mailed non-r"),
                               ("not_mailed", "not mailed")):
                vals = idx.get(key) or []
                cells = "".join(
                    f"{vals[offsets.index(o)]:>7,.0f}"
                    if offsets.index(o) < len(vals) and vals[offsets.index(o)] is not None
                    else f"{'--':>7}" for o in show)
                A(f"    {label:<10}" + cells)

        A("    'not mailed' is context, not a control -- the mailer targets low")
        A("    spenders, so that group is a structurally different population.")

        lift = m.get("cohort_lift") or []
        if lift:
            A("")
            A("  lift by horizon   ($/month, averaged over the window)")
            A(f"    {'horizon':<10}{'resp':>9}{'non-resp':>10}{'not mail':>10}"
              f"{'vs non-r':>10}{'%':>8}{'DiD':>9}")
            for row in lift:
                A(f"    +{row['horizon_months']:<9}"
                  f"{row['responders'] or 0:>9,.0f}"
                  f"{row['mailed_nonresp'] or 0:>10,.0f}"
                  f"{row['not_mailed'] or 0:>10,.0f}"
                  f"{row['vs_nonresp_abs'] or 0:>10,.0f}"
                  f"{row['vs_nonresp_pct'] or 0:>7.0f}%"
                  f"{row['diff_in_diff'] or 0:>9,.0f}")
            A("    DiD = (responder change) - (control change)")

        tiers = m.get("cohort_by_tier") or []
        if tiers:
            A("")
            A("  by response tier")
            A(f"    {'tier':<12}{'grp':>5}{'n':>8}{'pre':>9}"
              + "".join(f"{'+' + str(h):>9}" for h in (1, 3, 6, 12))
              + f"{'lift12':>9}")
            for row in tiers:
                cells = "".join(
                    f"{row.get('post_' + str(h)) or 0:>9,.0f}" for h in (1, 3, 6, 12))
                A(f"    {row['tier'][:10]:<12}{row['group']:>5}{row['n']:>8,}"
                  f"{row['pre_spend'] or 0:>9,.0f}{cells}"
                  f"{row.get('lift_12_pct') or 0:>8.0f}%")

        seg_sum = m.get("segment_summary") or []
        if seg_sum:
            A("")
            A(f"  segment cohorts   segment from: {m.get('segment_source')}")
            A(f"    {'segment':<12}{'offered':>9}{'resp':>8}{'rate':>7}"
              f"{'r pre':>8}{'r post':>8}{'r del':>8}"
              f"{'n pre':>8}{'n post':>8}{'n del':>8}{'DiD':>8}{'ctrl%':>7}")
            for row in seg_sum:
                A(f"    {str(row['segment'])[:10]:<12}"
                  f"{row.get('offered_n', 0):>9,}{row.get('resp_n', 0):>8,}"
                  f"{row.get('response_rate', 0):>6.1f}%"
                  f"{row.get('resp_pre', 0):>8,.0f}{row.get('resp_post', 0):>8,.0f}"
                  f"{row.get('resp_delta', 0):>+8,.0f}"
                  f"{row.get('non_pre', 0):>8,.0f}{row.get('non_post', 0):>8,.0f}"
                  f"{row.get('non_delta', 0):>+8,.0f}"
                  f"{row.get('did', 0):>+8,.0f}"
                  f"{row.get('did_from_control_pct', 0):>6.0f}%")
            eff = [r for r in seg_sum if r.get("mailings_per_response")]
            if eff:
                A("")
                A(f"    {'segment':<12}{'mail/resp':>11}{'DiD/1k mailed':>15}"
                  f"{'IC/1k mailed':>15}{'IC/resp/mo':>13}")
                for row in eff:
                    A(f"    {str(row['segment'])[:10]:<12}"
                      f"{row['mailings_per_response']:>11,.1f}"
                      f"{row['did_per_1000_mailed']:>14,}$"
                      f"{row.get('ic_per_1000_mailed', 0):>14,.0f}$"
                      f"{row.get('ic_per_response_mo', 0):>12,.2f}$")
                A("    DiD/1k = spend swing per 1,000 pieces mailed; "
                  "IC = interchange earned on it")

            pw = m.get("segment_pre_window") or []
            A(f"    pre = months {min(pw) if pw else '?'}..{max(pw) if pw else '?'}"
              f" (before the selection window), post = +1..+6, $/acct/month")
            A("    ctrl% = share of DiD from the control declining, "
              "not responders rising")
            n_panels = len(m.get("segment_cohorts") or [])
            A(f"    {n_panels} wave x segment x status series available for charting")

        if m.get("ladder_repeat") is not None:
            A("")
            A("  response ladder (all waves from the second on)")
            A(f"    {'first-time responders':<28}{m.get('ladder_first_time', 0):>10,}")
            A(f"    {'repeat responders':<28}{m.get('ladder_repeat', 0):>10,}"
              f"   ({m.get('ladder_repeat_pct', 0)}%)")
            A("    movement vs each account's best prior tier")
            for label, n in (m.get("ladder_movement") or []):
                A(f"      {label:<26}{n:>10,}")

        if m.get("nu_partial_ever"):
            A("")
            A("  NU 1-4 conversion (tracked activity that fell short)")
            A(f"    {'ever recorded NU 1-4':<28}{m['nu_partial_ever']:>10,}")
            A(f"    {'later reached NU 5+ or TH':<28}"
              f"{m.get('nu_converted_ever', 0):>10,}"
              f"   ({m.get('nu_conversion_pct', 0)}%)")
            A(f"    {'never converted':<28}{m.get('nu_never_converted', 0):>10,}")

        if m.get("counterfactual_gap_total") is not None:
            A("")
            A("  counterfactual: portfolio spend without responder activation")
            A(f"    non-responder change ratio applied: "
              f"{m.get('counterfactual_ratio')}")
            A(f"    {'gap, latest month':<28}"
              f"${m.get('counterfactual_gap_latest', 0):>12,}")
            A(f"    {'gap, cumulative':<28}"
              f"${m.get('counterfactual_gap_total', 0):>12,}  (spend)")
            if m.get("counterfactual_ic_total"):
                A(f"    {'  interchange earned on it':<28}"
                  f"${m['counterfactual_ic_total']:>12,}")
                A(f"    {'  latest month':<28}"
                  f"${m.get('counterfactual_ic_latest', 0):>12,}")
            A("    the gap is customer SPEND; the institution earns "
              "interchange on it")

        if m.get("penalty_box_violations") is not None:
            v = m["penalty_box_violations"]
            A("")
            A(f"  penalty box ({m.get('penalty_box_waves')} mailers / 6 months): "
              + (f"{v:,} same-tier repeats inside the window"
                 if v else "clean -- no same-tier repeats inside the window"))

    if m.get("ba_spend_before") is not None:
        A(_rule("RESPONDER SPEND   before vs after"))
        A(_line("mean before", m.get("ba_spend_before"), " $/mo"))
        A(_line("mean after", m.get("ba_spend_after"), " $/mo"))
        A(_line("control before", m.get("ba_control_before"), " $/mo"))
        A(_line("control after", m.get("ba_control_after"), " $/mo"))
        A(_line("net lift vs control", m.get("ba_lift_net"), " $/mo"))
        A(_line("lift", m.get("ba_lift_pct"), " %"))

    ages = m.get("age") or []
    if ages:
        A(_rule(f"HOLDER AGE   base: {_n(m.get('age_base'))}"))
        A(f"    {'band':<18}{'accounts':>10}{'w/card':>9}{'rate':>8}")
        for label, n, cards, pct in ages:
            A(f"    {label:<18}{n:>10,}{cards:>9,}{pct:>7.0f}%")

    if m.get("new_total"):
        A(_rule(f"NEW ACCOUNTS   {' to '.join(m.get('new_window', []))}"))
        A(_line("opened", m.get("new_total")))
        A(_line("still open", m.get("new_stillopen_pct"), " %"))
        A(_line("checking", m.get("new_checking_pct"), " %"))
        A(_line("new checking w/debit", m.get("new_chk_debit_pct"), " %"))
        A(_line("book checking w/debit", m.get("open_chk_debit_pct"), " %"))
        A(_line("  penetration gap", m.get("debit_pen_gap"), " pts"))

    if m.get("new_card_n"):
        A(_rule(f"CARD ACTIVITY   month: {m.get('activity_month')}"))
        A(_line("new cardholders", m.get("new_card_n")))
        A(_line("  active this month", m.get("new_active_pct"), " %"))
        A(_line("  ever swiped", m.get("new_ever_swiped_pct"), " %"))
        A(_line("book active this month", m.get("book_active_pct"), " %"))
        A(_line("spend/active, new", m.get("new_spend_active"), " $"))
        A(_line("spend/active, book", m.get("book_spend_active"), " $"))

    if m.get("open_24") is not None:
        A(_rule("RETENTION   trailing 24 months"))
        A(_line("opened", m.get("open_24")))
        A(_line("closed", m.get("close_24")))
        A(_line("net", m.get("net_24")))
        A(_line("median life of closed", m.get("median_closed_life"), " yrs"))

    dctr_leaks = m.get("dctr_leaks") or []
    rege_leaks = m.get("rege_leaks") or []
    if dctr_leaks or rege_leaks:
        A(_rule("LEAKS   where volume sits but the outcome does not follow"))
        A("  ranked by accounts lost = segment size x gap to portfolio rate")

        for title, leaks_, portfolio, total in (
            ("DEBIT CARD", dctr_leaks, m.get("dctr_overall"), m.get("dctr_leak_total")),
            ("REG E OPT-IN", rege_leaks, m.get("rege_pct"), m.get("rege_leak_total")),
        ):
            if not leaks_:
                continue
            A("")
            A(f"  {title}   portfolio {portfolio}%")
            A(f"    {'segment':<24}{'accts':>8}{'rate':>7}{'gap':>7}"
              f"{'lost':>7}{'vol%':>7}{'out%':>7}")
            for k in leaks_[:5]:
                A(f"    {k['segment'][:22]:<24}{k['n']:>8,}{k['rate']:>6.1f}%"
                  f"{k['gap_pp']:>6.1f}p{k['accounts_lost']:>7,}"
                  f"{k['share_of_volume']:>6.1f}%{k['share_of_outcome']:>6.1f}%")
            if total:
                A(f"    top 3 together: {total:,} accounts")

        gap = m.get("dctr_business_gap")
        if gap:
            A("")
            A(f"  business accounts: {gap['n']:,} at {gap['rate']}% "
              f"({gap['gap_pp']} pts below portfolio) = {gap['accounts_lost']:,} cards")

        opp = m.get("rege_default_opportunity")
        if opp:
            A("")
            A(f"  Reg E default bucket: {opp['n']:,} accounts "
              f"({opp['pct_of_base']}% of base) have made no election.")
            A(f"    at the elected opt-in rate that is {opp['at_elected_rate']:,} "
              f"additional opt-ins.")

        div = m.get("branch_divergence") or []
        if div:
            A("")
            A("  strong on cards, weak on opt-ins (process, not customers)")
            A(f"    {'branch':<24}{'accts':>8}{'card%':>8}{'regE%':>8}")
            for name, n, d, r, _dg, _rg in div:
                A(f"    {name[:22]:<24}{n:>8,}{d:>7.1f}%{r:>7.1f}%")

    if m.get("attrition_rate") is not None:
        A(_rule(f"ATTRITION   {' to '.join(m.get('attrition_window', []))}"))
        A(_line("at risk", m.get("attrition_at_risk")))
        A(_line("closed", m.get("attrition_closed")))
        A(_line("closure rate", m.get("attrition_rate"), " %"))
        # Both bases are printed while the change beds in: counting accounts
        # gives an account opened in the final month a full unit of
        # denominator, which understates the rate on a growing book.
        if m.get("attrition_rate_exposure") is not None:
            A(_line("closure rate, per account-year at risk",
                    m.get("attrition_rate_exposure"), " %"))
            A(_line("  exposure", m.get("attrition_exposure_years"),
                    " account-years"))
        A(_line("opened", m.get("attrition_opened")))
        A(_line("net", m.get("attrition_net")))
        A(_line("median life of closed", m.get("attrition_median_life"), " yrs"))
        A(_line("closed in first year", m.get("attrition_first_year_pct"), " %"))
        A("")
        A(f"  retention lift")
        A(f"    {'cohort':<24}{'accts':>10}{'closed%':>10}")
        debit_ok = m.get("attrition_debit_lift_valid") is not False
        cohorts = [
            ("mailer responder", "attrition_resp_n", "attrition_resp_rate"),
            ("non-responder", "attrition_nonresp_n", "attrition_nonresp_rate"),
            ("personal", "attrition_personal_n", "attrition_personal_rate"),
            ("business", "attrition_business_n", "attrition_business_rate"),
        ]
        if debit_ok:
            cohorts = [("with debit", "attrition_debit_n", "attrition_debit_rate"),
                       ("no debit", "attrition_nodebit_n", "attrition_nodebit_rate"),
                       ] + cohorts
        for label, nk, rk in cohorts:
            if m.get(nk) is None:
                continue
            # The count can exist while the rate does not: _pct returns None
            # for an empty denominator on purpose, so a structural zero is
            # never mistaken for a measured one. The cohort still gets a line,
            # because "these accounts exist and the rate is unmeasurable" is
            # information, and dropping the row would hide them entirely.
            rate = m.get(rk)
            A(f"    {label:<24}{m[nk]:>10,}"
              + (f"{rate:>9.1f}%" if rate is not None else f"{'n/a':>10}"))
        if m.get("attrition_debit_lift_valid") is False:
            A(f"    with / without debit   SUPPRESSED -- Debit? is cleared on")
            A(f"    closure ({m.get('attrition_debit_closed_share')}% of closed hold a card"
              f" vs {m.get('attrition_debit_open_share')}% of open), so the")
            A(f"    comparison would measure closure against itself.")
        elif m.get("attrition_debit_lift_pp") is not None:
            A(_line("  debit lift", m.get("attrition_debit_lift_pp"), " pts"))
        if m.get("attrition_mailer_lift_pp") is not None:
            A(_line("  mailer lift", m.get("attrition_mailer_lift_pp"), " pts"))
        if m.get("attrition_balance_valid") is False:
            A("")
            A("  closure rate by balance   SUPPRESSED -- see warnings")
        for key, title in (("attrition_by_tenure", "  closure rate by tenure"),
                           ("attrition_by_balance", "  closure rate by balance"),
                           ("attrition_ars_vs_non", "  closure rate, ARS-eligible product vs other"),
                           ("attrition_first_year_by_branch",
                            "  first-year closures by branch (opened in window, 30+)")):
            rows = m.get(key) or []
            if rows:
                A("")
                A(title)
                first_col = "opened" if key == "attrition_first_year_by_branch" else "at risk"
                A(f"    {'band':<18}{first_col:>10}{'closed':>9}{'rate':>8}")
                for label, n, c, pct in rows:
                    # pct is None where the band holds nobody: printing 0.0%
                    # would read as "nobody leaves from here" rather than
                    # "nobody is here".
                    A(f"    {str(label)[:22]:<22}{n:>8,}{c:>9,}"
                      f"{_rate_cell(pct)}")
        if m.get("attrition_ars_gap_pp") is not None:
            A(_line("  eligible product minus other", m.get("attrition_ars_gap_pp"), " pts"))
        if m.get("attrition_branch_worst"):
            w_, b_ = m["attrition_branch_worst"], m["attrition_branch_best"]
            A("")
            A(f"  highest {w_[0]:<20}{w_[1]:>7.1f}%  (n={w_[2]:,})")
            A(f"  lowest  {b_[0]:<20}{b_[1]:>7.1f}%  (n={b_[2]:,})")
        if m.get("attrition_revenue_lost"):
            A(_line("annual interchange lost", m.get("attrition_revenue_lost"), " $"))

    if m.get("balance_n"):
        A(_rule(f"DEPOSITS   base: {m.get('balance_base')} "
                f"({m['balance_n']:,} accounts)"))
        A(_line("total deposits", m.get("deposits_total"), " $"))
        A(_line("mean balance", m.get("balance_mean"), " $"))
        A(_line("median balance", m.get("balance_median"), " $"))
        A(_line("zero balance", m.get("balance_zero_n")))
        A(_line("  as % of eligible", m.get("balance_zero_pct"), " %"))
        if m.get("balance_top10_threshold"):
            A(_line("top 10% threshold", m.get("balance_top10_threshold"), " $"))
            A(_line("  their share of deposits", m.get("balance_top10_share"), " %"))

        bands = m.get("balance_bands") or []
        if bands:
            A("")
            A(f"    {'band':<14}{'accounts':>10}{'of accts':>10}"
              f"{'deposits':>16}{'of deps':>10}")
            for label, n, apct, deps, dpct in bands:
                A(f"    {label:<14}{n:>10,}{apct:>9.1f}%"
                  f"{deps:>16,}{dpct:>9.1f}%")

        if m.get("flight_risk_n") is not None:
            A("")
            basis = m.get("flight_risk_basis") or "balance proxy"
            A(f"  deposit flight risk (>= ${m.get('flight_risk_threshold', 0):,} "
              + ("and inflow falling)" if basis == "inflow"
                 else "and below own average)"))
            A(f"    basis: {basis}")
            A(_line("  accounts", m.get("flight_risk_n")))
            if basis == "inflow":
                A(_line("  on the balance proxy", m.get("flight_risk_proxy_n")))
                A("    the proxy is what this line read before the deposits "
                  "file; the gap is the size of the change")
            A(_line("  deposits held", m.get("flight_risk_deposits"), " $"))
            A(_line("  already declined", m.get("flight_risk_decline"), " $"))
            A(_line("  share of high-balance", m.get("flight_risk_share_of_high"), " %"))
            if m.get("flight_responder_advantage_pp") is not None:
                A(f"    responders declining "
                  f"{m.get('flight_responder_declining_pct')}% vs "
                  f"non-responders {m.get('flight_nonresponder_declining_pct')}%"
                  f"  ({m['flight_responder_advantage_pp']:+.1f} pts)")

        if m.get("sleeping_giants_n"):
            A("")
            A("  sleeping giants: above-median balance, below-median card spend")
            A(_line("  accounts", m.get("sleeping_giants_n")))
            A(_line("  deposits held", m.get("sleeping_giants_deposits"), " $"))
            A(_line("  of those, hold a card", m.get("sleeping_giants_debit_pct"), " %"))
            A(_line("  ideal members (both high)", m.get("ideal_members_n")))
            A(_line("  of those, hold a card", m.get("ideal_members_debit_pct"), " %"))

        pfi = m.get("pfi_tiers") or []
        if pfi:
            A("")
            A(f"  PFI score ({' + '.join(m.get('pfi_components', []))}, "
              f"max {m.get('pfi_max_score')})")
            A(f"    {'tier':<14}{'accounts':>10}{'of accts':>10}"
              f"{'deposits':>16}{'of deps':>9}{'card%':>8}")
            for label, n, apct, deps, dpct, card in pfi:
                A(f"    {label:<14}{n:>10,}{apct:>9.1f}%"
                  f"{deps:>16,}{dpct:>8.0f}%{card:>7.1f}%")

        ties = m.get("balance_vs_ars") or []
        if ties:
            A("")
            A("  balance band vs ARS program")
            A(f"    {'band':<14}{'accts':>9}{'take':>8}{'mailed':>9}{'resp':>8}")
            for row in ties:
                A(f"    {row['band']:<14}{row['n']:>9,}"
                  f"{row.get('take_rate', 0):>7.1f}%"
                  f"{row.get('mailed', 0):>9,}"
                  f"{row.get('response_rate', 0):>7.1f}%")

    if m.get("retention_n"):
        A(_rule(f"RETENTION HEALTH   spend trajectory   "
                f"({' to '.join(m.get('retention_window', []))})"))
        A(_line("at risk", m.get("retention_at_risk_n")))
        A(_line("  of eligible", m.get("retention_at_risk_pct"), " %"))
        A(_line("annual spend at risk", m.get("retention_spend_at_risk"), " $"))

        rows = m.get("retention_health") or []
        if rows:
            A("")
            A(f"  cardholders {m.get('retention_carded_n', 0):,}   "
              f"no card {m.get('retention_no_card_n', 0):,}   "
              f"at-risk share of cardholders "
              f"{m.get('retention_at_risk_of_carded_pct', 0)}%")
            A("")
            A(f"    {'status':<16}{'accounts':>10}{'share':>8}"
              f"{'recent $':>11}{'prior $':>11}{'card%':>8}")
            for status, n, share, rec, pri, card in rows:
                A(f"    {status:<16}{n:>10,}{share:>7.1f}%"
                  f"{rec:>11,.0f}{pri:>11,.0f}{card:>7.1f}%")
            A("    recent = last 3 months, prior = the 3 before that, $/acct/month")

        if m.get("retention_high_risk_n") is not None:
            A("")
            A("  early warning (2+ signals: steep slope, quiet months, "
              "collapse vs prior)")
            A(_line("  high-risk accounts", m.get("retention_high_risk_n")))
            A(_line("  annual spend at stake", m.get("retention_high_risk_spend"), " $"))
            A(_line("  of those, hold a card", m.get("retention_high_risk_debit_pct"), " %"))

        for key, title in (("retention_by_tenure", "  at-risk rate by tenure"),
                           ("retention_by_age", "  at-risk rate by holder age"),
                           ("retention_by_balance", "  at-risk rate by balance"),
                           ("retention_by_product", "  at-risk rate by product (100+)"),
                           ("retention_by_response", "  at-risk rate by mailer status")):
            rows = m.get(key) or []
            if rows:
                A("")
                A(title)
                A(f"    {'group':<24}{'accts':>9}{'at risk':>10}{'spend/yr':>14}")
                for label, n, pct_, spend in rows:
                    A(f"    {str(label)[:22]:<24}{n:>9,}{pct_:>9.1f}%{spend:>14,}")
        prog = m.get("dormancy_progression") or []
        if prog:
            A("")
            A("  months without spend, carded accounts")
            A("    " + "".join(f"{r[0]:>9}" for r in prog))
            A("    " + "".join(f"{r[2]:>8.1f}%" for r in prog))

        if m.get("retention_responder_advantage_pp") is not None:
            A("")
            A(f"  responders are {m['retention_responder_advantage_pp']:+.1f} pts "
              f"less likely to be at risk than mailed non-responders")
        if m.get("reactivation_target_n"):
            A(f"  reactivation list: {m['reactivation_target_n']:,} dormant "
              f"cardholders already on the mailing file "
              f"(${m.get('reactivation_target_prior_spend', 0):,}/yr prior spend)")

    if m.get("ic_total_spend") and m.get("ic_routing_available") is False:
        A(_rule(f"INTERCHANGE   ({' to '.join(m.get('ic_window', []))})"))
        A(_line("total card spend", m.get("ic_total_spend"), " $"))
        A(_line("interchange, annualized", m.get("ic_current_annual"), " $"))
        A("  PIN/SIG routing analysis does not apply: this file reports all")
        A("  card spend on one side of the split. See warnings.")

    elif m.get("ic_total_spend"):
        A(_rule(f"INTERCHANGE   PIN vs signature routing   "
                f"({' to '.join(m.get('ic_window', []))})"))
        A(f"  rates {m.get('ic_rate_source')}: PIN {m.get('ic_pin_rate', 0):.4%}"
          f"  SIG {m.get('ic_sig_rate', 0):.4%}"
          f"  (premium {m.get('ic_sig_premium')}x)")
        A(_line("total card spend", m.get("ic_total_spend"), " $"))
        A(_line("  PIN", m.get("ic_pin_spend"), " $"))
        A(_line("  SIG", m.get("ic_sig_spend"), " $"))
        A(_line("SIG ratio (of dollars)", m.get("ic_sig_ratio"), " %"))
        A(_line("  vs 60% goal", m.get("ic_sig_vs_goal_pp"), " pts"))
        if m.get("ic_sig_direction"):
            A(f"    trend: {m['ic_sig_direction']} "
              f"({m.get('ic_sig_shift_pp'):+.1f} pts first 3 mo to last 3 mo, "
              f"{m.get('ic_sig_slope_pp_per_mo'):+.3f} pp/mo)")
        A(_line("interchange, annualized", m.get("ic_current_annual"), " $"))
        if m.get("ic_pin_ticket"):
            A(_line("avg PIN ticket", m.get("ic_pin_ticket"), " $"))
            A(_line("avg SIG ticket", m.get("ic_sig_ticket"), " $"))

        scenarios = m.get("ic_scenarios") or []
        if scenarios:
            A("")
            A("  routing shift scenarios (annualized)")
            A(f"    {'scenario':<24}{'interchange':>14}{'gain':>12}{'SIG ratio':>12}")
            for label, ic, gain, ratio in scenarios:
                A(f"    {label:<24}{ic:>14,}{gain:>+12,}{ratio:>11.1f}%")

        if m.get("ic_pin_heavy_n"):
            A("")
            A(f"  PIN-heavy accounts (>= {int(PIN_HEAVY_DISPLAY)}% of dollars via PIN)")
            A(_line("  accounts", m.get("ic_pin_heavy_n")))
            A(_line("  of active", m.get("ic_pin_heavy_pct"), " %"))
            A(_line("  their spend", m.get("ic_pin_heavy_spend"), " $"))
            A(_line("  their opportunity", m.get("ic_pin_heavy_opportunity"), " $/yr"))

        for key, title in (("ic_by_type", "  SIG ratio by account type"),
                           ("ic_by_age", "  SIG ratio by holder age"),
                           ("ic_by_response", "  SIG ratio by mailer status")):
            rows = m.get(key) or []
            if rows:
                A("")
                A(title)
                A(f"    {'group':<24}{'accts':>9}{'SIG%':>8}{'spend':>14}")
                for label, n, ratio, spend in rows:
                    A(f"    {str(label)[:22]:<24}{n:>9,}{ratio:>7.1f}%{spend:>14,}")

        pin_default = m.get("ic_pin_default_products") or []
        if pin_default:
            A("")
            A(f"  products below {int(SIG_RISK_DISPLAY)}% SIG "
              f"-- may default to PIN routing")
            A(f"    {'product':<32}{'accts':>8}{'SIG%':>8}{'opportunity':>14}")
            for label, n, ratio, spend, opp in pin_default:
                A(f"    {str(label)[:30]:<32}{n:>8,}{ratio:>7.1f}%{opp:>14,}")

    # ---- deposit behaviour ------------------------------------------------
    # Distinct from the DEPOSITS section above, which is balance.py reading
    # Curr Bal against Avg Bal. This one reads the deposits FILE: actual
    # credits, dated, so a decline can be placed in a month.
    if m.get("dep_match_pct") is not None:
        A(_rule(f"DEPOSIT BEHAVIOUR   base: {m.get('dep_base')} "
                f"({m.get('dep_n', 0):,} accounts)"))
        A(f"  file: {m.get('dep_file_rows', 0):,} rows, "
          f"{m.get('dep_file_accounts', 0):,} accounts, "
          f"{m.get('dep_file_months', 0)} months "
          f"({m.get('dep_first_date')} to {m.get('dep_last_date')})")
        A("")
        # The join first, and loudly. Every figure under it is meaningless if
        # this is near zero, however healthy the rest of the section reads.
        A(_line("accounts matched", m.get("dep_matched_n")))
        A(_line("  match rate", m.get("dep_match_pct"), " %"))
        A(_line("  in base, no deposits", m.get("dep_in_book_not_file")))
        if m.get("dep_in_file_not_base") is not None:
            A(_line("  in file, outside the base", m.get("dep_in_file_not_base")))
            A("    expected: the file is institution-wide, the base is not")
        # The one that can actually mean something.
        if m.get("dep_in_file_not_odd") is not None:
            A(_line("  in file, NOT in the ODD", m.get("dep_in_file_not_odd")))
            A(_line("  file accounts the ODD knows",
                    m.get("dep_file_found_in_odd_pct"), " %"))
            A("    should be near 100; below it the account key is suspect")
        if (m.get("dep_match_pct") or 0) < MIN_MATCH_PCT:
            A(f"  READ THIS FIRST: under {MIN_MATCH_PCT:g}% of the book "
              "matched the deposits file. Treat every number below as "
              "unproven until the account key is confirmed.")
        A("")
        # The two tests an account has to pass, printed BEFORE the verdict so
        # a low rate can be read rather than just doubted.
        mix = m.get("dep_cadence_mix") or []
        if mix:
            A("  deposit rhythm   fortnightly and semi-monthly are one band:")
            A("                   a median gap cannot separate them")
            A(f"    {'rhythm':<30}{'accounts':>10}{'of matched':>12}")
            for label, n, pct in mix:
                A(f"    {str(label)[:28]:<30}{n:>10,}{_rate_cell(pct, 12)}")
            A("")
        mixn = m.get("dep_streams_mix") or []
        if mixn:
            A("  distinct recurring streams   an account can have two jobs")
            A(f"    {'streams':<26}{'accounts':>10}{'share':>10}")
            for label, cnt, pct in mixn:
                A(f"    {str(label)[:24]:<26}{cnt:>10,}{_rate_cell(pct, 10)}")
            A("")
        cvs = m.get("dep_consistency") or []
        if cvs:
            A(f"  amount consistency   recurring needs CV <= "
              f"{m.get('dep_recurring_cv_threshold')}")
            A(f"    {'band':<30}{'accounts':>10}{'of matched':>12}")
            for label, n, pct in cvs:
                A(f"    {str(label)[:28]:<30}{n:>10,}{_rate_cell(pct, 12)}")
            A("")
        if m.get("dep_recurring_n") is not None:
            A(_line("probable direct deposit", m.get("dep_recurring_n")))
            A(_line("  of matched accounts", m.get("dep_recurring_pct"), " %"))
            A(_line("  median amount", m.get("dep_median_amount"), " $"))
        if m.get("dep_stopped_n") is not None:
            A(_line("recurring credit stopped", m.get("dep_stopped_n")))
            A(_line("  of matched accounts", m.get("dep_stopped_pct"), " %"))
        if m.get("dep_windfall_accounts") is not None:
            A(_line("accounts with a windfall", m.get("dep_windfall_accounts")))
            A(_line("  windfall dollars", m.get("dep_windfall_dollars"), " $"))
        if m.get("dep_declines_dated_n") is not None:
            A(_line("inflow declines dated", m.get("dep_declines_dated_n")))
            A(_line("  of matched accounts", m.get("dep_declines_dated_pct"), " %"))
        if m.get("dep_idle_n") is not None:
            A(_line("idle cash", m.get("dep_idle_n")))
            A(f"    balance >= ${m.get('dep_idle_balance_floor', 0):,} with no "
              f"inflow for {m.get('dep_idle_quiet_days')} days")
            A(_line("  balance sitting idle", m.get("dep_idle_dollars"), " $"))
        if m.get("dep_inflow_to_balance_median") is not None:
            A(_line("median inflow / balance", m.get("dep_inflow_to_balance_median")))

        if m.get("dep_falling_and_slowing_n") is not None:
            A("")
            A(_line("balance falling AND inflow slowing",
                    m.get("dep_falling_and_slowing_n")))
            A(_line("  balance held there", m.get("dep_falling_and_slowing_dollars"), " $"))
            A(_line("  balance falling only", m.get("dep_falling_only_n")))
            A(_line("  inflow slowing only", m.get("dep_slowing_only_n")))
            A("    the overlap is the finding: either alone is a good month "
              "or a bad one, both is a member leaving")
        if m.get("dep_net_flow_positive_n") is not None:
            A("")
            A(_line("net flow positive", m.get("dep_net_flow_positive_n")))
            A(_line("  of the base", m.get("dep_net_flow_positive_pct"), " %"))
            A(_line("  median net flow", m.get("dep_net_flow_median"), " $"))
            A("    inflow minus card spend; cash and transfers are in "
              "neither, so this is a direction, not a balance")

        health = m.get("dep_inflow_health") or []
        if health:
            A("")
            A("  inflow health   retention.py's thresholds, read on credits")
            A(f"    {'class':<16}{'accounts':>10}{'of base':>10}")
            for label, n, pct in health:
                A(f"    {str(label)[:14]:<16}{n:>10,}{_rate_cell(pct)}")

        curve = m.get("dep_decline_by_month") or []
        if curve:
            A("")
            A("  when inflow turned   the month the step down happened")
            A(f"    {'month':<10}{'accounts':>10}{'before':>14}{'after':>14}")
            for month, n, before, after in curve:
                A(f"    {str(month):<10}{n:>10,}{before:>14,}{after:>14,}")

        for key, title in (
                ("dep_quiet_bands", "when money last arrived"),
                ("dep_gap_bands", "longest gap between credits"),
                ("dep_onset_months", "time to first deposit after opening")):
            rows = m.get(key) or []
            if rows:
                A("")
                A(f"  {title}")
                A(f"    {'band':<26}{'accounts':>10}{'share':>10}")
                for label, cnt, pct in rows:
                    A(f"    {str(label)[:24]:<26}{cnt:>10,}{_rate_cell(pct, 10)}")
        if m.get("dep_annual_inflow_median") is not None:
            A("")
            A(_line("annual inflow, median", m.get("dep_annual_inflow_median"), " $"))
            A(_line("  90th percentile", m.get("dep_annual_inflow_p90"), " $"))
            A(_line("  largest credit, median", m.get("dep_largest_deposit_median"), " $"))
            A("    a proxy for income, and only that -- the file carries "
              "credits, not earnings")

        for key, title in (
                ("dep_volatility_bands", "income steadiness   month to month"),
                ("dep_pay_change", "pay changes   on the dominant stream"),
                ("dep_payday_weekday", "payday   the weekday pay lands")):
            rows = m.get(key) or []
            if rows:
                A("")
                A(f"  {title}")
                A(f"    {'band':<26}{'accounts':>10}{'share':>10}")
                for label, cnt, pct in rows:
                    A(f"    {str(label)[:24]:<26}{cnt:>10,}{_rate_cell(pct, 10)}")
        if m.get("dep_refund_n") is not None:
            A("")
            A(_line("probable tax refunds", m.get("dep_refund_n")))
            A(_line("  median refund", m.get("dep_refund_median"), " $"))
            A(_line("  total", m.get("dep_refund_dollars"), " $"))
            A(f"    {m.get('dep_refund_note')}")
        if m.get("dep_lump_sum_n") is not None:
            A(_line("one credit is half the year", m.get("dep_lump_sum_n")))
            A("    a savings vehicle, not a wage")

        for key, title, cols in (
                ("dep_od_by_rhythm", "overdrafts by how members are paid",
                 ("income", "accounts", "overdrafting", "%")),
                ("dep_od_limit_by_income", "overdraft limits against income",
                 ("limit", "accounts", "paid here", "%")),
                ("dep_buffer_bands", "buffer   days of spending in the balance",
                 ("band", "accounts", "share", "")),
                ("dep_persona_features", "persona feature columns",
                 ("feature", "accounts", "measured", "median"))):
            rows = m.get(key) or []
            if rows:
                A("")
                A(f"  {title}")
                A(f"    {cols[0]:<26}{cols[1]:>10}{cols[2]:>12}{cols[3]:>8}")
                for row in rows[:8]:
                    c2 = f"{row[2]:,}" if len(row) > 2 and isinstance(row[2], (int, float)) else ""
                    c3 = (f"{row[3]:.1f}" if len(row) > 3
                          and isinstance(row[3], (int, float)) else "")
                    A(f"    {str(row[0])[:24]:<26}{row[1]:>10,}{c2:>12}{c3:>8}")
        if m.get("dep_primacy_n") is not None:
            A("")
            A(_line("bank here first", m.get("dep_primacy_n")))
            A(_line("  of the base", m.get("dep_primacy_pct"), " %"))
            A(_line("  balance they hold", m.get("dep_primacy_dollars"), " $"))
        if m.get("dep_employer_cohorts_n") is not None:
            A("")
            A(_line("employer cohorts inferred", m.get("dep_employer_cohorts_n")))
            A(_line("  accounts covered", m.get("dep_employer_covered_n")))
            A(f"    {m.get('dep_employer_note')}")
        if m.get("dep_reconciled_pct") is not None:
            A("")
            A(_line("balance reconciles", m.get("dep_reconciled_pct"), " %"))
            A(_line("  median residual", m.get("dep_reconcile_residual_median"), " $"))

        risk = m.get("dep_risk_signals") or []
        if risk:
            A("")
            A("  risk signals   deposits against the balance proxy")
            A(f"    {'signal':<44}{'accounts':>10}")
            for label, cnt, _pc in risk:
                A(f"    {str(label)[:42]:<44}{cnt:>10,}")
            A(f"    {m.get('dep_risk_note', '')[:100]}")

        vint = m.get("dep_inflow_by_vintage") or []
        if vint:
            A("")
            A("  inflow by tenure   does a new member ever start funding")
            A(f"    {'tenure':<20}{'accounts':>10}{'median inflow':>16}")
            for label, cnt, med in vint:
                A(f"    {str(label)[:18]:<20}{cnt:>10,}{med:>16,.0f}")

        for key, title, head in (
                ("dep_inflow_by_age", "inflow against spend, by holder age",
                 ("age", "accounts", "inflow", "spend")),
                ("dep_inflow_by_branch", "inflow against spend, by branch",
                 ("branch", "accounts", "inflow", "spend")),
                ("dep_responder_inflow", "do responders deposit more",
                 ("cohort", "accounts", "median inflow", "")),
                ("dep_ics_inflow", "do ICS accounts deposit more",
                 ("cohort", "accounts", "median inflow", ""))):
            rows = m.get(key) or []
            if rows:
                A("")
                A(f"  {title}")
                A(f"    {head[0]:<22}{head[1]:>10}{head[2]:>16}{head[3]:>14}")
                for row in rows:
                    last = f"{row[3]:,.0f}" if len(row) > 3 else ""
                    A(f"    {str(row[0])[:20]:<22}{row[1]:>10,}"
                      f"{row[2]:>16,.0f}{last:>14}")
        for note_key in ("dep_responder_note", "dep_ics_note"):
            if m.get(note_key):
                A(f"    {m[note_key][:104]}")
        if m.get("dep_income_loss_n") is not None:
            A("")
            A(_line("members who lost income", m.get("dep_income_loss_n")))
            A(f"    {(m.get('dep_income_loss_note') or '')[:104]}")

        if m.get("dep_competition_skipped"):
            A("")
            A(f"  deposits against competition   NOT BUILT")
            A(f"    the transaction load was short in "
              f"{m.get('dep_txn_short_months')} month(s); a figure drawn on a "
              f"partial file is wrong, not merely small")
        else:
            pair = m.get("dep_vs_card_spend") or []
            if pair:
                A("")
                A("  inflow against card spend")
                for label, dollars in pair:
                    A(f"    {str(label)[:28]:<30}{dollars:>16,}")
                A(f"    {(m.get('dep_net_position_note') or '')[:100]}")
            if m.get("dep_competitor_reach") is not None:
                A(_line("named competitors seen", m.get("dep_competitor_reach")))
                A(f"    {(m.get('dep_competitor_note') or '')[:100]}")

        conc = m.get("dep_concentration") or []
        if conc:
            A("")
            A("  inflow concentration   of depositing accounts, not the book")
            A(f"    {'slice':<10}{'accounts':>10}{'dollars':>16}{'of inflow':>11}")
            for label, n, dollars, pct in conc:
                A(f"    {str(label):<10}{n:>10,}{dollars:>16,}{_rate_cell(pct)}")

        dist = m.get("dep_distribution") or []
        if dist:
            A("")
            A("  annual inflow by decile")
            A(f"    {'decile':>8}{'accounts':>10}{'floor':>14}{'median':>14}")
            for dec, cnt, floor, med in dist:
                A(f"    {dec:>8}{cnt:>10,}{floor:>14,}{med:>14,}")

        seas = m.get("dep_seasonality") or []
        if seas:
            A("")
            A("  seasonality   each month against the 12-month average")
            A(f"    {'month':<10}{'dollars':>16}{'vs average':>12}")
            for mo, dollars, idx in seas:
                A(f"    {str(mo):<10}{dollars:>16,}{idx:>11.0f}%")

        book = m.get("dep_book_monthly") or []
        if book:
            A("")
            A(f"  monthly inflow   {len(book)} month(s)")
            A(f"    {'month':<10}{'depositing':>12}{'dollars':>16}")
            for month, n, dollars in book:
                A(f"    {str(month):<10}{n:>12,}{dollars:>16,}")

    if m.get("value_debit_delta") is not None or m.get("value_rege_delta") is not None:
        A(_rule("VALUE   revenue per account, trailing 12 months"))
        A(f"  interchange {m.get('value_ic_rate')} of spend  +  "
          f"NSF/OD ${m.get('value_nsf_fee')} per item")

        if m.get("value_debit_delta") is not None:
            A("")
            A("  A DEBIT CARD   base: eligible personal")
            A(f"    {'':<22}{'with card':>12}{'without':>12}{'delta':>12}")
            for label, key in (("interchange", "ic"), ("NSF/OD fees", "nsf"),
                               ("total revenue", "total")):
                A(f"    {label:<22}"
                  f"{m.get('value_debit_' + key + '_with', 0):>12,.2f}"
                  f"{m.get('value_debit_' + key + '_without', 0):>12,.2f}"
                  f"{m.get('value_debit_delta' if key == 'total' else 'value_debit_delta_' + key, 0):>+12,.2f}")
            A(f"    {'accounts':<22}"
              f"{m.get('value_debit_n_with', 0):>12,}"
              f"{m.get('value_debit_n_without', 0):>12,}")
            A("")
            A(f"    a card is worth ${m.get('value_debit_delta', 0):,.2f} "
              f"per account per year")
            A(f"    {m.get('value_debit_n_without', 0):,} eligible personal "
              f"accounts do not have one")
            A(f"      convert at historical {m.get('value_debit_hist_rate')}%"
              f"  ->  ${m.get('value_debit_pot_hist', 0):>12,}")
            A(f"      convert at L12M {m.get('value_debit_l12m_rate')}%"
              f"        ->  ${m.get('value_debit_pot_l12m', 0):>12,}")
            A(f"      convert all (ceiling)"
              f"          ->  ${m.get('value_debit_pot_full', 0):>12,}")

        ages = m.get("value_by_account_age") or []
        if ages:
            A("")
            A(f"  value by account age   portfolio "
              f"${m.get('value_portfolio_per_acct', 0):,.2f}/acct "
              f"at {m.get('value_portfolio_take')}% take")
            A(f"    {'tenure':<10}{'accts':>8}{'take':>7}{'IC/acct':>10}"
              f"{'NSF/acct':>10}{'$/acct':>10}{'vs port':>9}"
              f"{'penetr':>9}{'intens':>9}")
            for row in ages:
                A(f"    {row['group']:<10}{row['n']:>8,}{row['take_rate']:>6.1f}%"
                  f"{row['ic_per_acct']:>10,.0f}{row['nsf_per_acct']:>10,.0f}"
                  f"{row['value_per_acct']:>10,.0f}{row['gap']:>+9,.0f}"
                  f"{row['from_penetration']:>+9,.0f}{row['from_intensity']:>+9,.0f}")
            A("    IC and NSF shown separately: a tenure effect on spend can be")
            A("    invisible in the total when fee revenue dominates.")
            step = m.get("value_age_biggest_step")
            if step:
                A(f"    biggest step: {step['from']} -> {step['to']}  "
                  f"{step['step']:+,.0f}/acct ({step['step_pct']:+.0f}%)")

        resp_rows = m.get("value_by_response") or []
        if resp_rows:
            A("")
            A("  value by mailer status   (all eligible personal)")
            A(f"    {'group':<24}{'accts':>8}{'take':>7}{'IC/acct':>9}"
              f"{'NSF/acct':>10}{'$/acct':>9}{'penetr':>9}{'intens':>9}")
            for row in resp_rows:
                A(f"    {str(row['group'])[:22]:<24}{row['n']:>8,}"
                  f"{row['take_rate']:>6.1f}%{row['ic_per_acct']:>9,.0f}"
                  f"{row['nsf_per_acct']:>10,.0f}{row['value_per_acct']:>9,.0f}"
                  f"{row['from_penetration']:>+9,.0f}"
                  f"{row['from_intensity']:>+9,.0f}")

        carded_rows = m.get("value_by_response_carded") or []
        if carded_rows:
            A("")
            A(f"  cardholders only   portfolio "
              f"${m.get('value_carded_portfolio_per_acct', 0):,.0f}/acct")
            A("    (responding requires a card, so this removes the tautology)")
            A(f"    {'group':<24}{'accts':>8}{'IC/acct':>10}"
              f"{'NSF/acct':>11}{'$/acct':>10}{'vs port':>10}")
            for row in carded_rows:
                A(f"    {str(row['group'])[:22]:<24}{row['n']:>8,}"
                  f"{row['ic_per_acct']:>10,.0f}{row['nsf_per_acct']:>11,.0f}"
                  f"{row['value_per_acct']:>10,.0f}{row['gap']:>+10,.0f}")
            if m.get("value_responder_premium") is not None:
                A("")
                A(f"    responder premium vs mailed non-responder: "
                  f"${m['value_responder_premium']:,.0f}/yr")
                A(f"      interchange ${m.get('value_responder_premium_ic', 0):,.0f}"
                  f"   NSF/OD ${m.get('value_responder_premium_nsf', 0):,.0f}")
        branches = m.get("value_by_branch") or []
        if branches:
            A("")
            A("  value by branch   (top and bottom 6 by $/acct)")
            A(f"    {'branch':<20}{'accts':>8}{'take':>7}{'IC/acct':>9}"
              f"{'NSF/acct':>10}{'$/acct':>9}{'vs port':>9}"
              f"{'penetr':>9}{'intens':>9}")
            if len(branches) <= 12:
                show = branches
            else:
                show = branches[:6] + [None] + branches[-6:]
            for row in show:
                if row is None:
                    A(f"    {'...':<20}")
                    continue
                A(f"    {str(row['group'])[:18]:<20}{row['n']:>8,}"
                  f"{row['take_rate']:>6.1f}%{row['ic_per_acct']:>9,.0f}"
                  f"{row['nsf_per_acct']:>10,.0f}{row['value_per_acct']:>9,.0f}"
                  f"{row['gap']:>+9,.0f}{row['from_penetration']:>+9,.0f}"
                  f"{row['from_intensity']:>+9,.0f}")
            if m.get("value_branch_spread"):
                A(f"    spread best to worst: "
                  f"${m['value_branch_spread']:,.0f}/acct")
            share = m.get("value_branch_penetration_share")
            if share is not None:
                A(f"    {share:.0f}% of branch variation comes from penetration "
                  f"(what a branch controls),")
                A(f"    {100 - share:.0f}% from intensity (who its customers are)")

        if m.get("value_rege_delta") is not None:
            A("")
            A("  A REG E OPT-IN   base: eligible personal w/debit")
            A(f"    {'':<22}{'opted in':>12}{'not opted':>12}{'delta':>12}")
            for label, key in (("interchange", "ic"), ("NSF/OD fees", "nsf"),
                               ("total revenue", "total")):
                A(f"    {label:<22}"
                  f"{m.get('value_rege_' + key + '_with', 0):>12,.2f}"
                  f"{m.get('value_rege_' + key + '_without', 0):>12,.2f}"
                  f"{m.get('value_rege_delta' if key == 'total' else 'value_rege_delta_' + key, 0):>+12,.2f}")
            A(f"    {'accounts':<22}"
              f"{m.get('value_rege_n_with', 0):>12,}"
              f"{m.get('value_rege_n_without', 0):>12,}")
            A("")
            A(f"    an opt-in is worth ${m.get('value_rege_delta', 0):,.2f} "
              f"per account per year")
            A(f"      convert at current {m.get('value_rege_current_rate')}%"
              f"     ->  ${m.get('value_rege_pot_current', 0):>12,}")
            A(f"      convert at elected {m.get('value_rege_elected_rate')}%"
              f"     ->  ${m.get('value_rege_pot_elected', 0):>12,}")
            A(f"      convert all (ceiling)"
              f"          ->  ${m.get('value_rege_pot_full', 0):>12,}")

        if m.get("dctr_leak_value") or m.get("rege_leak_value"):
            A("")
            A("  priced leaks")
            if m.get("dctr_leak_value"):
                A(f"    top 3 debit leaks   {m['dctr_leak_total']:,} cards"
                  f"  =  ${m['dctr_leak_value']:,}/yr")
            if m.get("dctr_business_value"):
                A(f"    business gap        "
                  f"{m['dctr_business_gap']['accounts_lost']:,} cards"
                  f"  =  ${m['dctr_business_value']:,}/yr")
            if m.get("rege_leak_value"):
                A(f"    top 3 Reg E leaks   {m['rege_leak_total']:,} opt-ins"
                  f"  =  ${m['rege_leak_value']:,}/yr")
            if m.get("rege_default_value"):
                A(f"    Reg E default pool  "
                  f"{m['rege_default_opportunity']['at_elected_rate']:,} opt-ins"
                  f"  =  ${m['rege_default_value']:,}/yr")

    if result.warnings:
        A(_rule(f"WARNINGS ({len(result.warnings)})"))
        for w in result.warnings:
            A(f"  - {w}")

    A("")
    return "\n".join(L)
