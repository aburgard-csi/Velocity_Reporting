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
    A(f"  {m.get(P + 'with_competitor', 0):,} of {m.get(P + 'accounts_total', 0):,} accounts "
      f"({m.get(P + 'with_competitor_pct')}%) pay a named competitor   "
      f"${m.get(P + 'competitor_dollars', 0):,}  = {m.get(P + 'competitor_pct_of_transfer_dollars')}% of ACH+check $")
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
    eco = m.get(P + "ecosystems") or []
    if eco:
        A("")
        A(f"  PAYMENT ECOSYSTEMS (apart; ACH/check only)   {m.get(P + 'ecosystem_accounts', 0):,} accounts   "
          f"${m.get(P + 'ecosystem_dollars', 0):,}")
        A("    " + "   ".join(f"{r[0]} {r[1]:,} accts ${r[3]:,}" for r in eco[:8]))
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
