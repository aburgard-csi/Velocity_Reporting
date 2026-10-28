# Ported from v5 02-Scripts/ils/pre_go_live/report.py at 7ba1e63. Logic unchanged; copied whole.
"""The written PGL report, from pgl_* metrics. Every table states its base;
every rate has its denominator on the same line."""

from __future__ import annotations


def _n(v):
    return f"{v:,}" if isinstance(v, (int, float)) and v is not None else "-"


def _table(A, rows, names, title, limit=15):
    if not rows:
        return
    A("")
    A(f"  {title}")
    head = f"    {'group':<26}{'accts':>8}{'%':>7}{'items':>9}{'paid':>8}{'pay%':>7}"
    A(head + "".join(f"{n[:12]:>13}" for n in names[6:]))
    for r in rows[:limit]:
        line = f"    {str(r[0])[:25]:<26}{_n(r[1]):>8}{r[2]:>6.1f}%{_n(r[3]):>9}{_n(r[4]):>8}"
        line += f"{r[5]:>6.1f}%" if r[5] is not None else f"{'-':>7}"
        for v in r[6:]:
            line += f"{_n(round(v) if isinstance(v, float) else v):>13}"
        A(line)


def report(result) -> str:
    m = result.metrics or {}
    L: list[str] = []
    A = L.append
    A("=" * 64)
    A(f"{result.client_id}  ILS PRE-GO-LIVE   extract {m.get('pgl_extract')}   "
      f"({result.duration_s or 0:.0f}s)")
    A("=" * 64)

    # ---- field summary (always present) -----------------------------------
    A(f"  {m.get('pgl_rows', 0):,} rows, {m.get('pgl_columns_n', 0)} columns   "
      f"duplicates {m.get('pgl_duplicate_accts', 0)}   deleted rows {m.get('pgl_deleted_rows', 0)}")
    for name, cols in m.get("pgl_column_groups", []):
        A(f"    {name:<20} {len(cols):>2}: " + ", ".join(c[:28] for c in cols[:6])
          + (" ..." if len(cols) > 6 else ""))
    db = m.get("pgl_deleted_breakdown")
    if db:
        A(f"  deleted-flagged rows: {db['rows']:,} ({db['note']})")
        A("    by status: " + "  ".join(f"{k}: {v:,}" for k, v in db.get("by_status", [])[:6])
          + "   by last-update year: " + "  ".join(f"{k}: {v:,}" for k, v in db.get("by_last_update_year", [])))
    rv = m.get("pgl_review_by_status")
    if rv:
        A("")
        A("  DATA REVIEW -- whole file, nothing excluded, sliced by Account Status")
        names = m.get("pgl_review_by_status_columns", [])
        A("    " + "".join(f"{n[:12]:>13}" for n in names))
        for r in rv:
            A("    " + "".join(f"{(v if v is not None else '-'):>13,}" if isinstance(v, (int, float)) else f"{str(v)[:12]:>13}" for v in r))
        xt = m.get("pgl_review_status_x_od") or []
        if xt:
            A("    status x OD status (top): " + "   ".join(f"{a}/{b}: {v:,}" for a, b, v in xt[:8]))

    # ---- what the ILS system says (matrix + integrity dumps) --------------
    sv_files = m.get("sysv_files") or []
    if sv_files:
        A("")
        A("  " + "=" * 58)
        A("  WHAT THE ILS SYSTEM SAYS   (" + ", ".join(sv_files) + ")")
        A("  " + "-" * 58)
        for t, code, lo, hi, enabled, modified in m.get("sysv_matrix_types", []):
            A(f"  matrix {t} ({code}): limits ${lo:,.0f}-${hi:,.0f}, enabled {enabled}, "
              f"last modified {str(modified)[:10]}")
        if m.get("sysv_matrix_rounding_step"):
            A(f"  limits rounded down to ${m['sysv_matrix_rounding_step']:,.0f} steps; "
              f"matrix changed {m.get('sysv_matrix_changes_n', 0)}x, "
              f"last {str(m.get('sysv_matrix_last_change'))[:10]}")
        sm = m.get("sysv_matrix_status_map") or []
        if sm:
            A("  OD status mapping: " + "   ".join(
                f"{c} (calc={ic}, can OD={co})" for c, ic, co in sm))
        fx = m.get("sysv_matrix_factors") or []
        if fx:
            A("  scoring factors (ranges, factor min..max):")
            for t, cat, k, lo, hi in fx:
                A(f"    {t[:8]:<9}{cat:<30}{k:>3} ranges   {lo:>7,.0f} .. {hi:>6,.0f}")
        ov = m.get("sysv_matrix_overrides") or []
        if ov:
            A("  overrides, in priority order (stop=1 ends the chain):")
            for t, crit, val, stop, order in ov:
                A(f"    {t[:8]:<9}{order}: {crit[:64]:<66} -> {val}"
                  + ("  [stop]" if stop else ""))
        acc = m.get("sysv_accounts") or []
        if acc:
            A("")
            A(f"    {'type':<10}{'total':>8}{'open':>8}{'open%':>7}{'can OD':>8}{'RegE in':>9}")
            for r in acc:
                A(f"    {r[0][:9]:<10}{r[1]:>8,}{r[2]:>8,}{r[3]:>6.1f}%{r[4]:>8,}{r[6]:>9,}")
        cl = m.get("sysv_calc_latest") or {}
        if cl:
            A(f"  daily calc (latest {str(cl.get('date'))[:10]}): {cl.get('accounts', 0):,} accounts, "
              f"avg limit ${cl.get('avg_limit', 0):,}, {cl.get('zero_limit', 0):,} at $0, "
              f"{cl.get('overrides', 0):,} overridden   ({m.get('sysv_calc_days', 0)} days of history)")
        il = m.get("sysv_ils_limits") or {}
        if il:
            A(f"  ILS shadow limits ({il.get('effective')}): {il.get('nonzero', 0):,} accounts > $0 "
              f"(${il.get('dollars', 0):,} total, avg ${il.get('avg', 0):,}, max ${il.get('max', 0):,.0f}); "
              f"{il.get('zero', 0):,} at $0")
        um = m.get("sysv_od_status_unmapped") or []
        if um:
            A("  ! OD status codes with NO matrix mapping: "
              + ", ".join(f"{c} ({n:,} accounts)" for c, n in um))
        dp, od_ = m.get("sysv_deposits") or {}, m.get("sysv_overdrafts") or {}
        if dp:
            A(f"  deposit feed: {dp.get('active_days', 0)} active days of {dp.get('days', 0)}, "
              f"~{dp.get('avg_daily_count', 0):,}/day (~${dp.get('avg_daily_dollars', 0):,}/day); "
              f"{dp.get('no_deposit_20d_latest', 0):,} accounts w/o a deposit in 20 days")
        if od_:
            A(f"  overdraft feed: ~{od_.get('avg_daily_accounts', 0):,} accounts OD per day, "
              f"peak {od_.get('peak_accounts', 0):,} on {od_.get('peak_date')}")

    if result.status == "needs_codes":
        A("")
        A("  CODES NEEDED -- distinct values (value | count):")
        for col, vals in m.get("pgl_code_values", []):
            A(f"    {col}")
            for v, k in vals:
                A(f"      {v:<28}{k:>10,}")
        s = m.get("pgl_suggested_codes") or {}
        if s:
            A("  suggested (confirm, never assumed): " +
              "  ".join(f"{k}={v}" for k, v in s.items()))
        A("  run again with open_status / od_eligible / rege_opt_in confirmed.")
        return "\n".join(L)

    A("  codes: " + "  ".join(f"{k}={v}" for k, v in (m.get("pgl_codes_used") or {}).items()))
    A("  bases: " + "  ".join(f"{r[0]} {r[1]:,}" for r in m.get("pgl_bases", [])))


    # ---- reconciliation ----------------------------------------------------
    rc = m.get("pgl_reconcile") or []
    if rc:
        A("")
        A("  RECONCILIATION -- extract vs the ILS system's own numbers")
        A(f"    {'check':<58}{'extract':>10}{'system':>10}{'delta':>8}  ok")
        for check, ev, sv, delta, ok, note in rc:
            mark = {True: "YES", False: "NO !"}.get(ok, "-")
            A(f"    {check[:57]:<58}{(f'{ev:,}' if ev is not None else '-'):>10}"
              f"{(f'{sv:,}' if sv is not None else '-'):>10}"
              f"{(f'{delta:+,}' if delta is not None else '-'):>8}  {mark}"
              + (f"   ({note})" if note else ""))
        for f_ in m.get("pgl_reconcile_findings", []):
            A(f"    ! {f_}")

    # ---- the waterfall ----------------------------------------------------
    wf = m.get("pgl_waterfall") or []
    if wf:
        A("")
        A("  THE BOOK, STEP BY STEP -- every filter visible")
        for stepname, count, removed, why, confirms in wf:
            A(f"    {stepname:<44}{count:>8,}"
              + (f"  ({removed:+,})" if removed else "        ")
              + (f"   {confirms}" if confirms else ""))
            A(f"        {why}")

    # ---- today, on core limits --------------------------------------------
    if m.get("pgl_core_limits"):
        A("")
        A(f"  TODAY'S PROGRAM ON CORE LIMITS   (base: {m.get('pgl_core_base', 0):,} open; "
          f"exposure ${m.get('pgl_core_exposure', 0):,} on can-overdraft accounts)")
        A(f"    {'core limit':>10}{'accounts':>10}{'%':>7}{'can OD':>8}{'cannot':>8}")
        for lim, k, pct, can, cannot in m["pgl_core_limits"]:
            A(f"    {f'${lim:,}':>10}{k:>10,}{pct:>6.1f}%{can:>8,}{cannot:>8,}")
        if m.get("pgl_core_can_od_zero"):
            A(f"    -> {m['pgl_core_can_od_zero']:,} accounts CAN overdraft but hold a $0 core "
              f"limit -- the pocket a limit strategy exists for")
        cu = m.get("pgl_core_usage") or []
        if cu:
            A(f"    {'core limit':>10}{'accounts':>10}{'w/ items':>10}{'%':>7}{'YTD items':>11}{'OD now':>8}")
            for lim, k, wi, pct, items, odn in cu:
                A(f"    {f'${lim:,}':>10}{k:>10,}{wi:>10,}{pct:>6.1f}%{items:>11,}"
                  + (f"{odn:>8,}" if odn is not None else f"{'-':>8}"))
        cd = m.get("pgl_core_deposits") or []
        if cd:
            A("    deposits (33d): " + "   ".join(
                f"${lim:,}: {pct:.0f}% active, med ${med:,}" for lim, k, a, pct, med in cd))
        cr = m.get("pgl_core_rege") or []
        if cr:
            A("    Reg-E opt-in: " + "   ".join(
                f"${lim:,}: {pct:.1f}%" for lim, k, o, pct in cr))
        op = m.get("pgl_core_odd_pockets") or []
        if op:
            A("    odd pockets (status outside the ILS mapping): " + "   ".join(
                f"{c}: {k:,} accts, {wl:,} w/ limit (${d:,})" for c, k, wl, d in op))

    # ---- SUMMARY -----------------------------------------------------------
    A("")
    A("  " + "=" * 58)
    A("  SUMMARY")
    A("  " + "-" * 58)
    for h_ in m.get("pgl_headlines", []):
        A(f"  * {h_}")
    hh = m.get("pgl_score_headline") or {}
    p = hh.get("personal")
    if p and p.get("base"):
        A(f"  * of {p['base']:,} open personal accounts, {p['up']:,} see a higher "
          f"limit under ILS, {p['down']:,} lower, {p['same']:,} unchanged")
    fu = m.get("pgl_funnel") or []
    if fu:
        A("")
        A("  funnel   " + "  ->  ".join(f"{r[2] if len(r) > 2 else r[0]}: {r[1]:,}" for r in fu))
    ex = m.get("pgl_exposure")
    if ex:
        A(f"  exposure ({ex['base']}, n={ex['accounts']:,}):")
        A(f"    current ${ex['current_total']:,}   proposed ${ex['proposed_total']:,}   "
          f"delta {ex['delta']:+,}" + (f" ({ex['delta_pct']:+.1f}%)" if ex.get("delta_pct") is not None else "")
          + f"   median ${ex['median_current']:,.0f} -> ${ex['median_proposed']:,.0f}   "
            f"p90 proposed ${ex['p90_proposed']:,.0f}")
    rd = m.get("pgl_readiness") or []
    if rd:
        A("")
        A("  DATA READINESS (what this extract can and cannot support)")
        for area, grade, unlocks, cov in rd:
            mark = {"ok": "OK ", "thin": "THIN", "blocked": "X  "}.get(grade, grade)
            worst = min((c for c in cov if c[1] is not None), key=lambda c: c[1], default=None)
            detail = "" if grade == "ok" or worst is None else                 f"   ({worst[0][:34]} {worst[1]}% populated)"
            A(f"    [{mark:<4}] {area:<22} -> {unlocks}{detail}")

    _table(A, m.get("pgl_status_rows"), m.get("pgl_status_columns", []),
           "ACCOUNT STATUS (whole file)")
    _table(A, m.get("pgl_open_by_type"), m.get("pgl_open_by_type_columns", []),
           "OPEN ACCOUNTS BY TYPE (base: open)")
    _table(A, m.get("pgl_od_status_personal"), m.get("pgl_od_status_personal_columns", []),
           "OD STATUS (base: open personal; True = confirmed eligible)")
    _table(A, m.get("pgl_od_status_business"), m.get("pgl_od_status_business_columns", []),
           "OD STATUS (base: open business)")
    for key in ("personal", "business", "eligible", "opted_in"):
        _table(A, m.get(f"pgl_score_{key}"), m.get(f"pgl_score_{key}_columns", []),
               f"CHANGE IN SCORE (base: {key})")
    for key in ("personal", "business", "eligible"):
        rows = m.get(f"pgl_rege_{key}")
        if rows:
            _table(A, rows, m.get(f"pgl_rege_{key}_columns", []),
                   f"REG-E (base: {key}; opt-in rate {m.get(f'pgl_rege_optin_rate_{key}')}%)")
    tr = m.get("pgl_rege_trend")
    if tr:
        A("")
        A("  REG-E OPT-IN BY OPEN MONTH (open personal; last rows)")
        A(f"    {'year':<6}{'mo':>3}{'opened':>8}{'opted in':>9}{'rate':>7}")
        for y, mo, other, k, n, rate in tr[-12:]:
            A(f"    {y:<6}{mo:>3}{n:>8,}{k:>9,}{rate:>6.1f}%")
    zl = m.get("pgl_zero_limit_by_deposit")
    if zl:
        _table(A, zl, m.get("pgl_zero_limit_by_deposit_columns", []),
               f"ZERO ILS LIMIT x DEPOSIT ACTIVITY (base: {m.get('pgl_zero_limit_accounts', 0):,} "
               f"open personal at $0)")
    _table(A, m.get("pgl_limit_dist_current"), m.get("pgl_limit_dist_current_columns", []),
           "CURRENT CORE LIMIT DISTRIBUTION (base: open personal)", limit=20)
    _table(A, m.get("pgl_limit_dist_proposed"), m.get("pgl_limit_dist_proposed_columns", []),
           "PROPOSED ILS LIMIT DISTRIBUTION (base: eligible)", limit=20)
    if m.get("pgl_eligible_null_limit"):
        A(f"  DATA INTEGRITY: {m['pgl_eligible_null_limit']:,} eligible accounts with NULL ILS limit")

    yc = m.get("pgl_fee_ytd_ceiling")
    if yc:
        A("")
        A(f"  FEES -- YTD gross ceiling (fee history blocked): {yc['ytd_items']:,} YTD items "
          f"x ${yc['stated_fee']:g} = ${yc['gross_ceiling']:,} BILLED CEILING, not revenue "
          f"({yc['accounts_with_items']:,} accounts with items; pay ratio unknown)")
    a = m.get("pgl_fee_audit")
    if a:
        A("")
        A("  FEES (base: all open accounts; 12-month actuals)")
        A(f"    items {a['items_12mo']:,}   fees ${a['fees_12mo']:,}   blended "
          f"${a['blended_per_item']}/item   stated ${a['stated_fee']:g}   "
          f"implied pay ratio {a['implied_pay_ratio_pct']}%")
        A(f"    baseline = real reported fees ${m.get('pgl_fee_baseline', 0):,} "
          f"(reconstruction check ${a['reconstructed_fees']:,})")
        for name, modeled, delta, dpct, bands in m.get("pgl_fee_tiers", []):
            bandtxt = ", ".join(
                f"{b['min_item']}-{b['max_item'] if b['max_item'] is not None else '+'} ${b['fee']:g}"
                for b in bands)
            A(f"    {name:<28}${modeled:>12,}   {delta:>+12,} ({dpct:+.1f}%)   [{bandtxt}]")
        if m.get("pgl_fee_tiers_note"):
            A(f"    NOTE: {m['pgl_fee_tiers_note']}")
    for key, label in (("pgl_fee_daily_cap", "DAILY FEE CAP"),
                       ("pgl_fee_de_minimis", "DE MINIMIS")):
        v = m.get(key)
        if v:
            A(f"    {label}: {v['status']} -- {v['why']}; needs: {v['needs']}")

    if result.warnings:
        A("")
        A(f"WARNINGS ({len(result.warnings)})")
        for w in result.warnings:
            A(f"  - {w}")
    return "\n".join(L)
