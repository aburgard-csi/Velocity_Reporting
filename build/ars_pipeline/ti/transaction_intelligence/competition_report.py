# Ported from ARS v5 02-Scripts/ars/transaction_intelligence/competition_report.py at a491b5c (James Gilmore); logic unchanged.
"""COMPETITION block of the transaction report (text), from comp_* metrics."""

from __future__ import annotations

from pathlib import Path


def lines(m: dict, outputs: dict | None = None, prefix: str = "comp_") -> list[str]:
    P = prefix
    if not m.get(P + "accounts_total"):
        return []
    L: list[str] = []
    A = L.append
    A("")
    A("=" * 60)
    A(f"COMPETITION   base: {m.get(P + 'base_label')}   {m.get(P + 'institutions_configured')} institutions "
      f"configured, {m.get(P + 'institutions_n', 0)} seen; matched {m.get(P + 'matched_rows', 0):,} rows")
    A("-" * 60)
    share = m.get(P + "competitor_pct_of_transfer_dollars")
    A(f"  {m.get(P + 'with_competitor', 0):,} of {m.get(P + 'accounts_total', 0):,} accounts "
      f"({m.get(P + 'with_competitor_pct')}%) pay a named competitor   "
      f"${m.get(P + 'competitor_dollars', 0):,}  "
      + (f"= {share}% of ACH+check $" if share is not None
         else "(card rails only -- transfers to other institutions are not in the file)"))
    dist = m.get(P + "competitors_per_account") or []
    if dist:
        A("  competitors per account: " + "   ".join(f"{'3+' if i == 3 else k}: {v:,}" for i, (k, v) in enumerate(dist))
          + f"   multi-banked {m.get(P + 'multi_banked', 0):,} ({m.get(P + 'multi_banked_pct')}% of those with any)")
    if m.get(P + "by_tier"):
        A("")
        A(f"    {'tier':<30}{'insts':>6}{'accts':>9}{'% accts':>8}{'$':>15}")
        for tier, n_i, n, pct, d in m[P + "by_tier"]:
            A(f"    {tier[:29]:<30}{n_i:>6}{n:>9,}{pct:>7.1f}%{d:>15,}")
    if m.get(P + "institutions"):
        A("")
        A(f"    {'institution':<26}{'tier':<24}{'accts':>7}{'%':>6}{'$':>14}{'$/acct':>9}{'new':>5}{'stop':>5}  products")
        for r in m[P + "institutions"][:20]:
            A(f"    {r[0][:25]:<26}{r[1][:23]:<24}{r[2]:>7,}{r[3]:>5.1f}%{r[5]:>14,}{r[6]:>9,}{r[8]:>5}{r[9]:>5}  "
              + ", ".join(r[7][:3]))
    mom = m.get(P + "momentum") or []
    if mom:
        gain = [r for r in mom if r[3] > 0][:5]
        lose = [r for r in sorted(mom, key=lambda r: r[3]) if r[3] < 0][:5]
        if gain:
            A("  gaining (new relationships in 90d minus stopped): " +
              "  ".join(f"{r[0]} +{r[3]}" for r in gain))
        if lose:
            A("  losing:  " + "  ".join(f"{r[0]} {r[3]}" for r in lose))
    bl = m.get(P + "by_lens") or []
    if bl:
        A("")
        A(f"    {'by lens':<24}{'accts':>9}{'w/ comp':>9}{'%':>7}{'multi%':>8}{'$/acct':>9}  top")
        for ln, label, n, w, pct, mp, dpa, top in bl:
            A(f"    {label[:23]:<24}{n:>9,}{w:>9,}{pct:>6.1f}%{mp:>7.1f}%{dpa:>9,}  {top or ''}")
        if m.get(P + "responder_gap_pp") is not None:
            A(f"  responders minus mailed non-responders: {m[P + 'responder_gap_pp']:+.1f} pts with a competitor")
    for key, label in ((P + "at_risk", "recently inactive AND paying a competitor"),
                       (P + "new_accounts", "opened last 12 mo AND paying a competitor")):
        v = m.get(key)
        if v and v.get("accounts"):
            A(f"  {label:<44}{v['with_competitor']:>8,} of {v['accounts']:,}  ({v['pct']}%)")
    loc = m.get(P + "local") or {}
    A("")
    if loc.get("configured"):
        A(f"  LOCAL COMPETITORS ({len(loc['configured'])} configured)   {loc.get('accounts', 0):,} accounts "
          f"({loc.get('pct')}%)   ${loc.get('dollars', 0):,}")
        for name, n, d, prods in loc.get("institutions", []):
            A(f"    {name[:30]:<32}{n:>7,}{d:>14,}  " + ", ".join(prods[:3]))
        missing = sorted(set(loc["configured"]) - {r[0] for r in loc.get("institutions", [])})
        if missing:
            A("    not seen in the window: " + ", ".join(missing))
    else:
        A("  LOCAL COMPETITORS: none configured -- add LocalCompetitors to clients_config.json "
          "(the review queue below is where to look for names)")
    wallet = m.get(P + "wallet_tiers") or []
    if wallet:
        A("")
        A("  SHARE OF WALLET   competitor $ over the account's own $, accounts with a competitor")
        for tier, n, pct, d, mean_share in wallet:
            A(f"    {tier:<26}{n:>8,}{pct:>7.1f}%{d:>14,}   mean share {mean_share}%")
    threat = m.get(P + "threat") or []
    if threat:
        A("")
        A(f"  THREAT SCORE   {m.get(P + 'threat_basis', '')}")
        A(f"    {'institution':<26}{'score':>7}{'accts':>8}{'$':>14}{'growth':>9}")
        for name, score, n, d, g in threat[:8]:
            A(f"    {str(name)[:25]:<26}{score:>7.1f}{n:>8,}{d:>14,}{g:>8.1f}%")
    eco = m.get(P + "ecosystems") or []
    if eco:
        A("")
        A(f"  PAYMENT ECOSYSTEMS (P2P and wallets; apart from competitors and BNPL)   "
          f"{m.get(P + 'ecosystem_accounts', 0):,} accounts   "
          f"${m.get(P + 'ecosystem_dollars', 0):,}")
        A("    " + "   ".join(f"{r[0]} {r[1]:,} accts ${r[3]:,}" for r in eco[:8]))
    # the competition family (legacy 14-35, 66-67; #258)
    eng = m.get(P + "engagement") or []
    if eng:
        A("")
        A(f"  ENGAGEMENT DEPTH   share of the account's transactions at the competitor   "
          f"{m.get(P + 'engagement_heavy_n', 0):,} accounts heavy (half or more) somewhere   "
          f"avg share {m.get(P + 'engagement_avg_share_pct', 0)}%")
        A(f"    {'institution':<26}{'accts':>7}{'light':>7}{'moderate':>10}{'heavy':>7}{'avg %':>8}")
        for r in eng[:10]:
            A(f"    {str(r[0])[:25]:<26}{r[1]:>7,}{r[2]:>7,}{r[3]:>10,}{r[4]:>7,}{r[5]:>8.1f}")
    wal = m.get(P + "wallet_by_institution") or []
    if wal:
        A("")
        A(f"  WALLET SHARE BY COMPETITOR   competitor $ over the account's own $, institutions with "
          f"{m.get(P + 'wallet_min_accounts', 0)}+ accounts   {m.get(P + 'wallet_high_exposure_n', 0)} over a fifth heavy")
        A(f"    {'institution':<26}{'accts':>7}{'CU-focus':>10}{'balanced':>10}{'heavy':>7}{'heavy %':>9}")
        for r in wal[:10]:
            A(f"    {str(r[0])[:25]:<26}{r[1]:>7,}{r[2]:>10,}{r[3]:>10,}{r[4]:>7,}{r[5]:>9.1f}")
    rb = m.get(P + "recency_bands") or []
    if rb and m.get(P + "recency_pairs"):
        A("")
        A(f"  RECENCY   days since each account-competitor pair last moved money   "
          f"{m.get(P + 'recency_pairs', 0):,} pairs   {m.get(P + 'recency_active_pct', 0)}% active in 30 days   "
          f"{m.get(P + 'recency_dormant_pairs', 0):,} dormant 180+")
        A("    " + "   ".join(f"{r[0]} {r[1]:,} ({r[2]}%)" for r in rb))
    bb = m.get(P + "breadth_bands") or []
    if bb:
        A("")
        A(f"  COMPETITORS PER ACCOUNT   banks and lenders only   no competitor "
          f"{m.get(P + 'breadth_no_competitor', 0):,} ({m.get(P + 'breadth_no_competitor_pct', 0)}% of the book)   "
          f"two or more {m.get(P + 'breadth_shopping', 0):,}   six or more {m.get(P + 'breadth_deep', 0):,}")
        A("    " + "   ".join(f"{r[0]}: {r[1]:,} ({r[2]}% of active)" for r in bb))
    wb = m.get(P + "winback") or []
    if wb:
        A("")
        A(f"  WINBACK   volume fell, {m.get(P + 'winback_window', '')}, {m.get(P + 'winback_min_accounts', 0)}+ accounts   "
          f"{m.get(P + 'winback_accounts', 0):,} accounts across {len(wb)} competitors")
        for r in wb[:8]:
            A(f"    {str(r[0])[:25]:<26}{r[1]:>7,} accts   {r[2]:>7,} vs {r[3]:<7,} txns   {r[4]:>+7.1f}%   score {r[5]:.0f}")
    b = m.get(P + "bnpl") or {}
    if b.get("providers"):
        A("")
        A(f"  BUY NOW PAY LATER   {b.get('pct', 0)}% reach ({b.get('accounts', 0):,} accounts)   "
          f"${b.get('dollars', 0):,} over {b.get('months', 0)} months   ${b.get('per_acct_month', 0):,} per account a month"
          + ("   SIGNAL: 10%+ reach, revolving credit displaced" if (b.get("pct") or 0) >= 10 else ""))
        A("    " + "   ".join(f"{r[0]} {r[1]:,} accts ${r[3]:,}" for r in b["providers"][:6]))
        if b.get("stacked_accounts") is not None:
            A(f"    repeat ({b.get('repeat_months', 3)}+ months) {b.get('repeat_accounts', 0):,} "
              f"({b.get('repeat_pct', 0)}%)   two or more providers {b.get('stacked_accounts', 0):,} "
              f"({b.get('stacked_pct', 0)}%)   median payment ${b.get('median_ticket', 0):,}")
        if b.get("merchants"):
            A(f"    merchant named on {b.get('merchant_named_pct', 0)}% of BNPL dollars, "
              f"{b.get('merchants_n', 0):,} merchants:   "
              + "   ".join(f"{r[0]} {r[1]:,} accts ${r[4]:,} ({r[5]})" for r in b["merchants"][:6]))
    rq = m.get(P + "review_queue") or []
    if rq:
        A("")
        A(f"  REVIEW QUEUE   bank-looking counterparties no institution matched   ${m.get(P + 'review_queue_dollars', 0):,}")
        for s_, c, d in rq[:12]:
            A(f"    {s_[:48]:<50}{c:>8,}{d:>14,}")
    if m.get("compb_institutions") and P == "comp_":
        A("")
        A(f"  BUSINESS ACCOUNTS (separate)   {m.get('compb_accounts_total', 0):,} transacting; "
          f"{m.get('compb_with_competitor', 0):,} with a competitor ({m.get('compb_with_competitor_pct')}%)   "
          f"${m.get('compb_competitor_dollars', 0):,}")
        for r in m["compb_institutions"][:6]:
            A(f"    {r[0][:25]:<26}{r[2]:>7,}{r[5]:>15,}  " + ", ".join(r[7][:2]))
    lists = (outputs or {}).get("competition_lists")
    if lists:
        A("")
        A(f"  action lists: {', '.join(lists)} under {Path(next(iter(lists.values()))).parent}")
    return L
