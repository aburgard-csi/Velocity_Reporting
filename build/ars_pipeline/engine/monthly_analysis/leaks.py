"""Leak analysis: where does volume sit, and where does the outcome not follow?

A leak is a segment holding a large share of the eligible population but a
smaller share of the outcome -- cards issued, opt-ins captured. The question
it answers is "60% of eligible accounts sit at these branches but only 40% of
the cards; what is that costing?"

Ranked by ACCOUNTS LOST, not by percentage gap. A 40-point gap on 200
accounts is noise. A 16-point gap on 4,928 accounts is the finding. Sorting
by rate alone surfaces small segments and buries the real opportunity.

    accounts_lost = n * (portfolio_rate - segment_rate) / 100
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

# A segment smaller than this is excluded: rates on tiny cells are unstable
# and would crowd out the segments that actually move the number.
MIN_SEGMENT_N = 150


@dataclass
class Leak:
    dimension: str          # "branch", "holder age", ...
    segment: str            # "South Center"
    n: int                  # eligible accounts in the segment
    hits: int               # cards / opt-ins in the segment
    rate: float             # segment rate, %
    portfolio_rate: float   # the benchmark, %
    gap_pp: float           # portfolio - segment, percentage points
    accounts_lost: int      # n * gap / 100 -- the ranking key
    share_of_volume: float  # segment n as % of total base
    share_of_outcome: float # segment hits as % of total hits
    share_gap_pp: float     # volume share - outcome share

    def as_row(self) -> list:
        return [self.dimension, self.segment, self.n, self.rate,
                self.gap_pp, self.accounts_lost,
                self.share_of_volume, self.share_of_outcome]


def find_leaks(
    dimension: str,
    rows: list,
    portfolio_rate: float,
    total_n: int,
    total_hits: int,
    label_i: int = 0,
    n_i: int = 1,
    hits_i: int = 2,
    rate_i: int = 3,
    min_n: int = MIN_SEGMENT_N,
) -> list[Leak]:
    """Turn a [label, n, hits, rate] table into ranked leaks.

    Index arguments exist because the metric tables are not uniformly shaped:
    the branch table is [name, cards, eligible, rate] while the age tables are
    [band, n, cards, rate].
    """
    leaks: list[Leak] = []
    for row in rows:
        try:
            label = str(row[label_i])
            n = int(row[n_i])
            hits = int(row[hits_i])
            rate = float(row[rate_i])
        except (IndexError, TypeError, ValueError):
            continue
        if n < min_n:
            continue

        gap = round(portfolio_rate - rate, 1)
        if gap <= 0:
            continue

        leaks.append(Leak(
            dimension=dimension,
            segment=label,
            n=n,
            hits=hits,
            rate=rate,
            portfolio_rate=portfolio_rate,
            gap_pp=gap,
            accounts_lost=int(round(n * gap / 100)),
            share_of_volume=round(100 * n / total_n, 1) if total_n else 0.0,
            share_of_outcome=round(100 * hits / total_hits, 1) if total_hits else 0.0,
            share_gap_pp=round((100 * n / total_n) - (100 * hits / total_hits), 1)
            if total_n and total_hits else 0.0,
        ))

    return sorted(leaks, key=lambda leak: -leak.accounts_lost)


def compute(metrics: dict, config: dict, warn) -> dict:
    """Find leaks across every dimension available, for DCTR and Reg E."""
    out: dict = {}

    # ---- Debit card take rate -----------------------------------------
    portfolio = metrics.get("dctr_overall")
    total_n = metrics.get("n_eligible")
    total_hits = metrics.get("dctr_cards")

    if portfolio and total_n and total_hits:
        found: list[Leak] = []

        # branch table is [name, cards, eligible, rate] -- note the order
        found += find_leaks("branch", metrics.get("take_branch") or [],
                            portfolio, total_n, total_hits,
                            n_i=2, hits_i=1)
        for key, label in (("dctr_holder_age", "holder age"),
                           ("dctr_account_age", "account age"),
                           ("dctr_balance", "balance")):
            found += find_leaks(label, metrics.get(key) or [],
                                portfolio, total_n, total_hits)

        found.sort(key=lambda leak: -leak.accounts_lost)
        out["dctr_leaks"] = [asdict(leak) for leak in found[:10]]
        out["dctr_leaks_top3"] = [leak.as_row() for leak in found[:3]]
        out["dctr_leak_total"] = sum(leak.accounts_lost for leak in found[:3])

        # Business is a population, not a leak within one -- call it out
        # separately so it doesn't get buried among branch rows.
        biz_n = metrics.get("n_dctr_business")
        biz_rate = metrics.get("dctr_business")
        if biz_n and biz_rate is not None and biz_rate < portfolio:
            out["dctr_business_gap"] = {
                "n": biz_n,
                "rate": biz_rate,
                "gap_pp": round(portfolio - biz_rate, 1),
                "accounts_lost": int(round(biz_n * (portfolio - biz_rate) / 100)),
            }

    # ---- Reg E ---------------------------------------------------------
    rege_portfolio = metrics.get("rege_pct")
    rege_n = metrics.get("rege_pool")
    rege_hits = metrics.get("rege_in")

    if rege_portfolio and rege_n and rege_hits:
        found = []
        # rege_branch is [name, opted_in, total, rate]
        found += find_leaks("branch", metrics.get("rege_branch") or [],
                            rege_portfolio, rege_n, rege_hits,
                            n_i=2, hits_i=1)
        for key, label in (("rege_holder_age", "holder age"),
                           ("rege_account_age", "account age")):
            found += find_leaks(label, metrics.get(key) or [],
                                rege_portfolio, rege_n, rege_hits)
        # rege_product is [name, n, opted_in, rate]
        found += find_leaks("product", metrics.get("rege_product") or [],
                            rege_portfolio, rege_n, rege_hits)

        found.sort(key=lambda leak: -leak.accounts_lost)
        out["rege_leaks"] = [asdict(leak) for leak in found[:10]]
        out["rege_leaks_top3"] = [leak.as_row() for leak in found[:3]]
        out["rege_leak_total"] = sum(leak.accounts_lost for leak in found[:3])

        # The Default bucket is not a refusal -- it is an unanswered
        # question, and it is usually the largest single opportunity.
        default_n = metrics.get("rege_default")
        if default_n:
            out["rege_default_opportunity"] = {
                "n": default_n,
                "pct_of_base": round(100 * default_n / rege_n, 1),
                "at_elected_rate": int(round(
                    default_n * (metrics.get("rege_pct_of_elected") or 0) / 100)),
            }

    # ---- Cross-signal: strong on one, weak on the other -----------------
    # A branch that issues cards well but captures no opt-ins is a process
    # difference, not a customer difference.
    dctr_by_branch = {r[0]: r[3] for r in (metrics.get("take_branch") or [])
                      if len(r) > 3}
    rege_by_branch = {r[0]: r[3] for r in (metrics.get("rege_branch") or [])
                      if len(r) > 3}
    rege_size = {r[0]: r[2] for r in (metrics.get("rege_branch") or [])
                 if len(r) > 2}

    divergent = []
    for name in set(dctr_by_branch) & set(rege_by_branch):
        if rege_size.get(name, 0) < MIN_SEGMENT_N:
            continue
        d_gap = dctr_by_branch[name] - (portfolio or 0)
        r_gap = rege_by_branch[name] - (rege_portfolio or 0)
        if d_gap > 5 and r_gap < -3:
            divergent.append([name, rege_size[name], dctr_by_branch[name],
                              rege_by_branch[name], round(d_gap, 1),
                              round(r_gap, 1)])
    if divergent:
        divergent.sort(key=lambda r: r[5])
        out["branch_divergence"] = divergent[:5]

    return out
