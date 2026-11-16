"""Terminal read-out of the financial-services definitions and coverage (fs-03), for the build log."""

from __future__ import annotations


def lines(m: dict, prefix: str = "fin_") -> list[str]:
    L: list[str] = []
    A = L.append
    d = m.get(prefix + "definitions")
    if d:
        A("")
        A("=" * 60)
        A(f"FINANCIAL SERVICES   base: {d['base_label']}   {d['base_accounts']:,} accounts "
          f"({d['file_accounts']:,} in the file)")
        A("-" * 60)
        for key, label in (("any", "any leakage"), ("addressable", "addressable"),
                           ("adjacency", "adjacency (apart)")):
            r = d[key]
            A(f"    {label:<20}{r['accounts']:>9,} accounts{r['pct']:>7.1f}%{r['dollars']:>14,} $")
    c = m.get(prefix + "coverage")
    if c:
        A(f"  coverage: {c['matched_rows_pct']}% of rows, {c['matched_dollars_pct']}% of dollars matched; "
          f"review queue ${c['review_queue_dollars']:,}; "
          + ("wallet share available" if c["wallet_share_available"]
             else "no transfer rail: wallet share unavailable"))
    return L
