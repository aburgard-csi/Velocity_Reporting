# Ported from ARS v5 02-Scripts/ars/transaction_intelligence/sections_report.py at a491b5c (James Gilmore); logic unchanged.
"""Terminal report lines for merchants / card_behavior / relationship and
the family tables -- kept out of run.py the way competition_report is."""

from __future__ import annotations


def lines(m: dict) -> list[str]:
    L: list[str] = []
    A = L.append
    if m.get("mch_top"):
        A("")
        A("=" * 60)
        A(f"MERCHANTS   base: {m.get('mch_base_label')}   {m.get('mch_card_accounts', 0):,} card accounts   "
          f"${m.get('mch_card_spend', 0):,} card spend   {m.get('mch_distinct', 0):,} distinct "
          f"(top 15 = {m.get('mch_top15_share_pct')}%, {m.get('mch_merchants_for_80pct', 0):,} = 80%)")
        A("-" * 60)
        for name, accts, txns, d, ticket, pct in m["mch_top"][:12]:
            A(f"    {str(name)[:32]:<34}{accts:>8,}{txns:>10,}{d:>14,}{ticket:>9,.2f}{pct:>7.1f}%")
        A(f"  categories ({m.get('mch_category_method')}; MCC on {m.get('mch_mcc_coverage_pct')}% of card rows)")
        for row in (m.get("mch_by_category") or [])[:10]:
            c, accts, _txns, d, pct = row[0], row[1], row[2], row[3], row[4]
            parent = row[5] if len(row) > 5 else ""
            A(f"    {str(c)[:26]:<28}{accts:>8,}{d:>15,}{pct:>7.1f}%"
              f"   {parent}")
        par = m.get("mch_by_parent") or []
        if par:
            A("  rolled up")
            for name, _txns, d, pct in par:
                A(f"    {str(name)[:26]:<28}{d:>23,}{pct:>7.1f}%")
        for key, label in (("mch_new", "new merchants (last 3 mo)"), ("mch_faded", "faded merchants")):
            rows = m.get(key) or []
            if rows:
                A(f"  {label}: " + "  ".join(f"{r[0][:20]} (${r[1]:,})" for r in rows[:5]))
        bl = m.get("mch_by_lens") or []
        if bl:
            A(f"    {'by lens':<24}{'accts':>9}{'$/acct':>9}{'txn/mo':>8}  top merchant")
            for ln, label, n, spa, tpm, topm in bl:
                A(f"    {label[:23]:<24}{n:>9,}{spa:>9,}{tpm:>8}  {str(topm)[:24]}")
        L.extend(_profile_lines(m))
    if m.get("beh_ticket_bands"):
        A("")
        A("=" * 60)
        A(f"CARD BEHAVIOR   base: {m.get('beh_base_label')}   ticket mean ${m.get('beh_ticket_mean')} "
          f"median ${m.get('beh_ticket_median')}   {m.get('beh_txns_per_active_acct_mo')} txns/active acct/mo")
        A("-" * 60)
        A("    tickets   " + "  ".join(f"{b[0]} {b[2]}%" for b in m["beh_ticket_bands"]))
        A("    intensity " + "  ".join(f"{b[0]} {b[2]}%" for b in (m.get("beh_intensity_bands") or [])))
        if m.get("beh_peak"):
            p = m["beh_peak"]
            A(f"  busiest window: {p[0]} {p[1]}h ({p[2]:,} txns)")
        if m.get("beh_recurring_txn_pct") is not None:
            A(f"  recurring: {m['beh_recurring_txn_pct']}% of card txns, {m['beh_recurring_dollar_pct']}% of card $   "
              f"{m.get('beh_accounts_with_recurring', 0):,} accounts ({m.get('beh_accounts_with_recurring_pct')}%)")
            A("    " + "   ".join(f"{r[0][:18]} {r[1]:,} accts" for r in (m.get("beh_top_recurring") or [])[:6]))
        bl = m.get("beh_by_lens") or []
        if bl:
            A(f"    {'by lens':<24}{'accts':>9}{'med ticket':>11}{'txn/mo':>8}{'recur%':>8}")
            for ln, label, n, med, tpm, rec in bl:
                ms = f"{med:>11,.2f}" if med is not None else f"{'-':>11}"
                A(f"    {label[:23]:<24}{n:>9,}{ms}{tpm:>8}{rec:>7.1f}%")
            if m.get("beh_responder_ticket_gap") is not None:
                A(f"  responders vs mailed non-responders: {m['beh_responder_ticket_gap']:+.2f} ticket, "
                  f"{m.get('beh_responder_intensity_gap', 0):+.1f} txns/mo")
        if m.get("beh_routing_by_merchant"):
            A(f"  PIN share {m.get('beh_pin_share_pct')}%   by merchant: "
              + "  ".join(f"{r[0][:16]} {r[2]}%" for r in m["beh_routing_by_merchant"][:5]))
    if m.get("rel_single_rail"):
        A("")
        A("=" * 60)
        A(f"RELATIONSHIP   base: {m.get('rel_base_label')}   {m.get('rel_accounts_total', 0):,} accounts   "
          f"single-rail file: channel breadth is not measurable and is not reported")
        A("-" * 60)
    if m.get("rel_breadth"):
        A("")
        A("=" * 60)
        A(f"RELATIONSHIP   base: {m.get('rel_base_label')}   {m.get('rel_accounts_total', 0):,} accounts   "
          f"mean breadth {m.get('rel_breadth_mean')}   single-channel {m.get('rel_single_channel_pct')}%   "
          f"primary-like {m.get('rel_primary_like_n', 0):,} ({m.get('rel_primary_like_pct')}%)")
        A("-" * 60)
        A("    channels/acct  " + "  ".join(f"{r[0]}: {r[1]:,} ({r[2]}%)" for r in m["rel_breadth"]))
        A("    channel reach  " + "  ".join(f"{r[0]} {r[2]}%" for r in (m.get("rel_by_channel") or [])))
        if m.get("rel_single_channel_mix"):
            A("    single-channel mix  " + "  ".join(f"{r[0]}: {r[1]:,}" for r in m["rel_single_channel_mix"]))
        A("    billers/acct   " + "  ".join(f"{r[0]}: {r[2]}%" for r in (m.get("rel_billers_bands") or [])))
        db = m.get("rel_depth_by_breadth") or []
        if db:
            A("    depth by breadth  " + "  ".join(f"{r[0]}ch {r[2]} txn/mo ${r[3]}/mo" for r in db))
        bl = m.get("rel_by_lens") or []
        if bl:
            A(f"    {'by lens':<24}{'accts':>9}{'breadth':>9}{'single%':>9}")
            for ln, label, n, b, sc in bl:
                A(f"    {label[:23]:<24}{n:>9,}{b:>9}{sc:>8.1f}%")
        nx = m.get("rel_next_channel") or []
        if nx:
            A("    next channel   " + "  ".join(f"{r[0]} alone {r[1]:,} -> {r[2]} ({r[3]}%)" for r in nx))
    if m.get("ic_base_label"):
        A("")
        A("=" * 60)
        if not m.get("ic_routing_available"):
            A(f"INTERCHANGE MIX   base: {m.get('ic_base_label')}   file carries "
              f"{'/'.join(m.get('ic_rails') or [])} only; the PIN/SIG mix is not reported")
        else:
            A(f"INTERCHANGE MIX   base: {m.get('ic_base_label')}   {m.get('ic_card_accounts', 0):,} card accounts   "
              f"${m.get('ic_card_spend', 0):,} card $   signature {m.get('ic_sig_share_pct')}% of $, "
              f"{m.get('ic_sig_share_of_swipes_pct')}% of swipes   {m.get('ic_sig_direction', 'n/a')} "
              f"({m.get('ic_sig_shift_pp') or 0:+.1f}pp first 3 vs last 3 months)   "
              f"unpriced: the ARS value section owns interchange $")
            A(f"    tickets  PIN ${m.get('ic_pin_ticket')}  SIG ${m.get('ic_sig_ticket')}   "
              f"PIN-heavy (80%+ PIN) {m.get('ic_pin_heavy_n', 0):,} accts ({m.get('ic_pin_heavy_pct')}%) "
              f"${m.get('ic_pin_heavy_spend', 0):,} ({m.get('ic_pin_heavy_spend_pct')}% of card $)")
            A("    monthly  " + "  ".join(f"{r[0][2:]} {r[3]}%" for r in (m.get("ic_monthly") or [])))
            A("    by merchant  " + "  ".join(f"{r[0][:16]} {r[4]}% sig"
                                             for r in (m.get("ic_by_merchant") or [])[:6]))
            if m.get("ic_by_age"):
                A("    by age   " + "  ".join(f"{r[0]} {r[2]}%" for r in m["ic_by_age"]))
            if m.get("ic_by_product"):
                A("    by product   " + "  ".join(f"{r[0][:18]} {r[2]}%" for r in m["ic_by_product"][:6]))
            if m.get("ic_by_lens"):
                A("    by lens   " + "  ".join(f"{r[1][:18]} {r[3]}%" for r in m["ic_by_lens"]))
    if m.get("ovl_flight_n") is not None:
        A("")
        A("=" * 60)
        A(f"DEPOSIT FLIGHT x COMPETITOR   {m.get('ovl_flight_n', 0):,} flight-risk accounts "
          f"(>= ${m.get('ovl_flight_threshold', 0):,}, below their average)   "
          f"${m.get('ovl_flight_deposits', 0):,} deposits   ${m.get('ovl_flight_decline', 0):,} decline")
        A("-" * 60)
        if m.get("ovl_named_destination_n") is not None:
            A(f"  {m['ovl_named_destination_n']:,} of them ({m.get('ovl_named_destination_pct')}%) "
              f"have a NAMED destination: ${m.get('ovl_named_destination_deposits', 0):,} deposits "
              f"at stake, ${m.get('ovl_named_destination_decline', 0):,} already declining")
        if m.get("ovl_destinations"):
            A(f"    {'institution':<28}{'flight accts':>13}{'external $':>13}"
              f"{'declining $':>13}")
            for r in m["ovl_destinations"][:8]:
                dec = f"{r[3]:,}" if len(r) > 3 else "n/a"
                A(f"    {str(r[0])[:27]:<28}{r[1]:>13,}{r[2]:>13,}{dec:>13}")
        if m.get("ovl_categories"):
            A("    categories: " + "   ".join(
                f"{r[0]} {r[1]:,} accts ${r[2]:,}"
                + (f" (declining ${r[3]:,})" if len(r) > 3 else "")
                for r in m["ovl_categories"][:4]))
    fams = [(fam, m.get(f"txn_by_{fam}") or [])
            for fam in ("branch", "product", "swipe_tier")]
    if any(rows for _, rows in fams):
        win = m.get("txn_window_months")
        A("")
        A("=" * 60)
        A(f"TRANSACTION DOLLARS BY LENS   gross flow (in + out), all channels, "
          f"{win if win is not None else '?'}-month window -- NOT deposit balances")
        A("-" * 60)
        for fam, rows in fams:
            if rows:
                A(f"  by {fam.replace('_', ' ')}:  "
                  + "  ".join(f"{str(r[0])[:16]} {r[1]:,} accts ${r[3]:,}" for r in rows[:6]))
    # ---- the attrition analyses computed on every run and printed nowhere (#245)
    curve = m.get("leak_curve") or []
    if curve:
        cols = m.get("leak_curve_columns") or []
        i_off = cols.index("offset_months") if "offset_months" in cols else 0
        i_n = cols.index("n") if "n" in cols else 1
        i_mean = cols.index("mean_competitor_dollars") if "mean_competitor_dollars" in cols else 2
        ctrl = {r[i_off]: r for r in (m.get("leak_control") or [])}
        div = m.get("leak_divergence_month")
        A("")
        A("=" * 60)
        A("COMPETITOR SPEND BEFORE CLOSURE   mean competitor $ per account, month by month before close"
          + (f"   diverges {div} month(s) before close" if div is not None
             else "   no sustained divergence"))
        A("-" * 60)
        A(f"  control: {m.get('leak_control_basis') or 'still-open accounts'}")
        A(f"    {'months before':<15}{'closers':>9}{'$/acct':>10}{'control':>9}{'$/acct':>10}")
        def _d(v):
            return f"{v:>10,.0f}" if v is not None else f"{'--':>10}"
        for r in curve:
            c = ctrl.get(r[i_off])
            A(f"    {r[i_off]:<15}{r[i_n]:>9,}{_d(r[i_mean])}"
              + (f"{c[i_n]:>9,}{_d(c[i_mean])}" if c else f"{'--':>9}{'--':>10}"))
    st = m.get("stress_txn_by_count") or []
    if st:
        A("")
        A("=" * 60)
        A(f"STRESSORS ACROSS BOTH FILES   base: {m.get('stress_txn_base')}   "
          f"{m.get('stress_txn_n', 0):,} accounts")
        A("-" * 60)
        A("  conditions built: " + ", ".join(m.get("stress_txn_available") or [])
          + (("   not available: " + ", ".join(m["stress_txn_skipped"]))
             if m.get("stress_txn_skipped") else ""))
        for k, n, pct, dep in st:
            A(f"    {k} stressor(s){n:>10,}{pct:>7.1f}%   ${dep:,} deposits")
        A(f"  two or more: {m.get('stress_txn_2plus_n', 0):,} ({m.get('stress_txn_2plus_pct')}%)   "
          f"${m.get('stress_txn_2plus_deposits', 0):,} deposits   "
          f"${m.get('stress_txn_2plus_competitor_dollars', 0):,} to competitors")
    hot = m.get("hot_by_branch") or []
    if hot:
        A("")
        A("=" * 60)
        A(f"BRANCH HOTSPOTS   closures against competitor leakage, per branch   rank correlation "
          f"{m.get('hot_rank_correlation')} over {m.get('hot_rank_correlation_n', 0)} branches")
        A("-" * 60)
        A(f"    {'branch':<22}{'at risk':>9}{'closed':>8}{'/acct-yr':>9}{'leak %':>8}{'$/acct':>8}  top institution")
        for r in hot[:12]:
            A(f"    {str(r[0])[:21]:<22}{r[1]:>9,}{r[2]:>8,}{r[3]:>8.1f}%{r[5]:>7.1f}%{r[6]:>8,}  {r[7]}")
        both = m.get("hot_both_above_median") or []
        if both:
            A("  above the median on both: " + ", ".join(str(b) for b in both))
    return L


def _profile_lines(m: dict) -> list[str]:
    """merchant_profiles: rising and falling, the MCC codes, breadth, and the
    card book by holder age and tenure (#258 group 3)."""
    L: list[str] = []
    A = L.append
    growth = m.get("mch_growth") or []
    if growth:
        A(f"  rising and falling ({m.get('mch_growth_window')}): book "
          f"{m.get('mch_growth_book_pct', 0):+.1f}%   {m.get('mch_growth_rising_n', 0):,} up 10%+, "
          f"{m.get('mch_growth_falling_n', 0):,} down, of {m.get('mch_growth_ranked_n', 0):,} at $1k+")
        for name, n, prior, recent, change, pct in growth:
            A(f"    {str(name)[:28]:<30}{n:>7,}{prior:>12,}{recent:>12,}{change:>+12,}{pct:>+8.1f}%")
    for key, label in (("mch_new", "new merchants (last 3 mo)"), ("mch_faded", "faded merchants")):
        rows = m.get(key) or []
        if rows:
            A(f"  {label}: " + "  ".join(f"{r[0][:20]} (${r[1]:,})" for r in rows[:5]))
    mcc = m.get("mch_mcc_top") or []
    if mcc:
        A(f"  MCC codes: {m.get('mch_mcc_distinct', 0):,} distinct, top 5 = "
          f"{m.get('mch_mcc_top5_share_pct')}% of coded card $")
        for code, group, n, txns, d, ticket, pct in mcc[:8]:
            A(f"    {code:<6}{str(group)[:22]:<24}{n:>8,}{txns:>10,}{d:>14,}{ticket:>9,.2f}{pct:>7.1f}%")
    bb = m.get("mch_breadth_bands") or []
    if bb:
        A(f"  categories per account: mean {m.get('mch_breadth_mean')}, "
          f"{m.get('mch_breadth_deep_pct')}% at 4+   "
          + "  ".join(f"{b[0]}: {b[1]:,} (${b[3]:,}/acct)" for b in bb))
    for key, label in (("mch_by_age", "by holder age"), ("mch_by_tenure", "by account tenure")):
        rows = m.get(key) or []
        if rows:
            A(f"    {label:<18}{'accts':>9}{'$/acct':>9}{'txn/mo':>8}{'ticket':>9}  top category")
            for band, n, spa, tpm, ticket, cat in rows:
                A(f"    {band:<18}{n:>9,}{spa:>9,}{tpm:>8}{ticket:>9,.2f}  {str(cat)[:22]}")
    fs = m.get("mch_first_swipe_bands") or []
    if fs:
        A(f"  time to first swipe ({m.get('mch_first_swipe_window')}): "
          f"{m.get('mch_first_swipe_new_accounts', 0):,} accounts, median "
          f"{m.get('mch_first_swipe_median_days')} days, "
          f"{m.get('mch_first_swipe_within_30_pct')}% within 30   "
          + "  ".join(f"{b[0]} {b[2]}%" for b in fs))
    return L
