"""Leakage and competitor use cut by member age, account age and branch (R5).

James, 2026-11-05: "it would be nice to have the age band lens, maybe branch
lens. account age lens". The by-lens tables answer "responders against the
book"; these answer "which members": the same payers, grouped by the holder's
age band, by how long the account has been open, and by branch.

One cut, two callers. financial_services hands in its leakage rows (one per
account x category) and writes fin_by_age_band / fin_by_tenure_band /
fin_by_branch; competition hands in its competitor rows (one per account x
institution) and writes comp_by_age_band / comp_by_tenure_band. Competition
already cuts by branch (comp_by_branch, its own basis and floor), so it does
not get a second branch table from here.

Basis, the same as both modules' by-lens and by-branch tables: every account
in the band that transacts in the window, personal and business alike, so
the financial-services row and the competitor row for one band divide by the
same accounts and read side by side. The bands are the card slides' cut
points (core.account_lenses.AGE_BANDS / TENURE_BANDS). A band thinner than
MIN_ACCOUNTS is left out and the run log says how many accounts that drops; a
family whose ODD column is absent writes nothing and the run log says so.

Rows: [band, accounts, paying, paying_pct, dollars_per_payer, top_<item>,
top_<item>_accounts]. Dollars are window totals, divided by the accounts that
pay; the top item is the one the most accounts in the band pay, ties broken
alphabetically.
"""

from __future__ import annotations

import pandas as pd

from ..core.account_lenses import BAND_FAMILIES, FAMILY_COLUMNS
from .txn_common import ranked

# A band row swings too hard below this; the same floor competition's
# by-branch table uses (MIN_ACCOUNTS_FOR_BRANCH).
MIN_ACCOUNTS = 50
# Branches are many; the cut keeps the largest by transacting accounts. Age
# and tenure bands are few and kept whole, in band order.
TOP_BRANCHES = 12

KEYS = {"age_band": "by_age_band", "tenure_band": "by_tenure_band", "branch": "by_branch"}
WHAT = {"age_band": "member age band", "tenure_band": "account-age band", "branch": "branch"}


def _pct(n, d) -> float:
    return round(100 * n / d, 1) if d else 0.0


def columns(item: str) -> list[str]:
    return ["band", "accounts", "paying", "paying_pct", "dollars_per_payer",
            f"top_{item}", f"top_{item}_accounts"]


def cut(groups: dict, txn_accounts: pd.Index, hits: pd.DataFrame, item: str,
        min_accounts: int | None = None, top: int | None = None) -> tuple[list, int]:
    """(rows, accounts left out) for one family.

    groups: {band: account ids} from Lenses.family. hits: one row per
    account x item with `acct`, `item` and `dollars`. Bands keep the
    family's order; with `top`, the largest bands by accounts are kept,
    largest first, and the ones past it count as left out.
    """
    floor = MIN_ACCOUNTS if min_accounts is None else min_accounts
    dollars = hits.groupby("acct")["dollars"].sum()
    payers_all = pd.Index(dollars.index.astype(str))
    rows, left_out = [], 0
    for value, ids_all in groups.items():
        ids = pd.Index(ids_all).astype(str).intersection(txn_accounts)
        if len(ids) < floor:
            left_out += len(ids)
            continue
        payers = payers_all.intersection(ids)
        sub = hits[hits["acct"].isin(payers)]
        leader = ranked(sub.groupby(item)["acct"].nunique())
        n_pay = len(payers)
        rows.append([str(value), len(ids), n_pay, _pct(n_pay, len(ids)),
                     round(float(dollars.reindex(payers).sum()) / n_pay) if n_pay else 0,
                     str(leader.index[0]) if len(leader) else None,
                     int(leader.iloc[0]) if len(leader) else 0])
    if top is not None:
        rows.sort(key=lambda r: (-r[1], r[0]))
        left_out += sum(r[1] for r in rows[top:])
        rows = rows[:top]
    return rows, left_out


def family_cuts(lenses, txn_accounts: pd.Index, hits: pd.DataFrame, item: str,
                key_prefix: str, families, warn, payer_noun: str) -> dict:
    """{prefix + by_<family>: rows, ..._columns, ..._basis} for each family.

    payer_noun says what a paying account pays ("an outside financial
    product", "a named competitor") for the basis and the run log.
    """
    out: dict = {}
    txn_accounts = pd.Index(txn_accounts).astype(str)
    hits = hits.assign(acct=hits["acct"].astype(str))
    for family in families:
        key = key_prefix + KEYS[family]
        groups = lenses.family(family)
        if not groups:
            cols = ((BAND_FAMILIES[family][0],) if family in BAND_FAMILIES
                    else FAMILY_COLUMNS.get(family, ()))
            warn(f"{key} unavailable: the ODD carries no usable "
                 f"{' / '.join(cols)}; the {WHAT[family]} cut is not drawn")
            continue
        rows, left_out = cut(groups, txn_accounts, hits, item,
                             top=TOP_BRANCHES if family == "branch" else None)
        if not rows:
            warn(f"{key} SUPPRESSED: no {WHAT[family]} carries {MIN_ACCOUNTS} "
                 f"transacting accounts")
            continue
        out[key] = rows
        out[key + "_columns"] = columns(item)
        basis = (f"transacting accounts per {WHAT[family]}, personal and business; "
                 f"paying = accounts paying {payer_noun} in the window; dollars "
                 f"per payer are window totals over the accounts that pay; top "
                 f"{item} is the one the most accounts in the band pay")
        if family == "branch":
            basis += (f"; the {TOP_BRANCHES} largest branches with at least "
                      f"{MIN_ACCOUNTS} transacting accounts")
        else:
            basis += f"; bands under {MIN_ACCOUNTS} transacting accounts are left out"
        out[key + "_basis"] = basis
        if left_out:
            warn(f"{key}: {left_out:,} transacting account(s) sit in "
                 f"{WHAT[family]}s left out of the table (under {MIN_ACCOUNTS}"
                 f"{' or past the largest ' + str(TOP_BRANCHES) if family == 'branch' else ''})")
    return out
