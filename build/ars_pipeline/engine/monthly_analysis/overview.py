"""Book composition: what the account base is made of.

Two tables a CSM reads before any rate: accounts by status code (open vs
closed vs dormant, with the eligible flag), and the product mix of open
accounts split personal / business. Context, not findings -- they give the
denominators their shape.
"""

from __future__ import annotations

import pandas as pd

from ..core.subsets import Subsets, is_business, norm

TOP_PRODUCTS = 12


def _pct(n, d) -> float:
    return round(100 * n / d, 1) if d else 0.0


def compute(subsets: Subsets, config: dict, warn) -> dict:
    total = subsets.total
    out: dict = {}

    stat = norm(total.get("Stat Code"))
    if stat is not None:
        desc = norm(total.get("Stat Desc")) if "Stat Desc" in total.columns else None
        elig_codes = {str(s).strip().upper() for s in config.get("EligibleStatusCodes", [])}
        rows = []
        for code, idx in total.groupby(stat).groups.items():
            label = str(code) or "(blank)"
            if desc is not None:
                d = desc.loc[idx].mode()
                if len(d) and d.iloc[0]:
                    label = f"{code} {d.iloc[0]}"
            rows.append([label, len(idx), _pct(len(idx), len(total)),
                         str(code).upper() in elig_codes])
        rows.sort(key=lambda r: -r[1])
        out["stat_code_mix"] = rows

    open_accts = subsets.open_accounts
    prod = norm(open_accts.get("Prod Desc")) if "Prod Desc" in open_accts.columns \
        else norm(open_accts.get("Prod Code"))
    if prod is not None and len(open_accts):
        business = is_business(open_accts)
        elig_idx = subsets.eligible.index
        rows = []
        for code, idx in open_accts.groupby(prod).groups.items():
            n = len(idx)
            rows.append([str(code) or "(blank)", n, _pct(n, len(open_accts)),
                         _pct(int(business.loc[idx].sum()), n),
                         bool(idx.isin(elig_idx).any())])
        rows.sort(key=lambda r: -r[1])
        out["product_mix"] = rows[:TOP_PRODUCTS]
        out["product_mix_other_n"] = int(sum(r[1] for r in rows[TOP_PRODUCTS:]))
        out["product_mix_personal_pct"] = _pct(int((~business).sum()), len(open_accts))
    return out
