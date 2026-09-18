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
    return L
