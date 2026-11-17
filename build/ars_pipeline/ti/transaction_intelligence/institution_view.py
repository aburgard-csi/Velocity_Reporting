"""Financial services x named institution (fs-05): who holds the product the member pays for.

`financial_services` says what product leaves (an auto loan, a card); `competition` says which
institution it reaches. Both read the same rows. This crosses them, for depository institutions
only (national, regional and local banks and credit unions): "NUSENDA CU LOAN PMT" is an auto
or personal loan in one view and Nusenda in the other.

Rule (James, 2026-11): a payment to a named depository counts in BOTH views and is never summed
across them. Competition counts it as the institution (tier, proximity); Financial Services
counts it as the product. The tables here are a cross-tab of the two, not a third total.

Two ways to name the institution. When the Competition layers ran (`cl_parts` in the shared context), the
match is the registry's: every FDIC bank and NCUA credit union, matched on the card description, with
its tier (National, Digital, Local, Regional, State, Other, Card-issuing banks). Without them, it is the
competition configuration (the universal list plus the client's own regional and local names), and a
depository in neither is not found. Either way the share at a named institution is a floor: the files
are card rows, and an ambiguous name is left unplaced, never guessed. `fininst_source` says which.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .competition import _classify

DEPOSITORY_TIERS = ("National Bank", "Regional Bank", "Local Bank / CU")
TOP_PAIRS = 60
NOTE = ("counted in both Competition (as the institution) and Financial Services (as the product); "
        "the two views are never added; a floor: only institutions the match can name are counted")
UNRESOLVED = "Unresolved (ambiguous)"


def compute(df: pd.DataFrame, fin_rows: pd.DataFrame, comp_spec: dict,
            account_filter: pd.Index | None = None, key_prefix: str = "fininst_") -> dict:
    out: dict = {}
    if df.empty or fin_rows is None or not comp_spec:
        return out
    text = fin_rows["text"] if "text" in fin_rows else None
    if text is None:
        return out
    cat = fin_rows["category"]
    kind = fin_rows["kind"]
    acct = df["primary_account_num"].astype(str)
    in_base = acct.isin(account_filter).to_numpy() if account_filter is not None \
        else np.ones(len(df), dtype=bool)
    leak = (cat.notna() & (kind == "leakage")).to_numpy() & in_base
    if not leak.any():
        return out

    table = _classify(pd.Index(text.unique()), comp_spec)
    inst = text.map(table["category"])
    tier_of = {n: i.get("tier", "") for n, i in comp_spec["institutions"].items()}
    tier = inst.map(tier_of)
    named = leak & tier.isin(DEPOSITORY_TIERS).to_numpy()
    amt = np.nan_to_num(df["amount"].abs().to_numpy())

    rows = pd.DataFrame({"acct": acct.to_numpy()[leak], "category": cat.to_numpy()[leak],
                         "amount": amt[leak], "named": named[leak],
                         "institution": inst.to_numpy()[leak], "tier": tier.to_numpy()[leak]})
    out.update(_tables(rows, key_prefix))
    out[key_prefix + "source"] = "configured"
    return out


def _tables(rows: pd.DataFrame, key_prefix: str) -> dict:
    """The cross-tab from one row per leakage payment: acct, category, amount, named, institution, tier."""
    out: dict = {}
    by_cat = []
    for name, grp in rows.groupby("category", observed=True):
        n_acc = int(grp["acct"].nunique())
        hit = grp[grp["named"]]
        n_hit = int(hit["acct"].nunique())
        by_cat.append([name, n_acc, n_hit, round(100 * n_hit / n_acc, 1) if n_acc else 0.0,
                       round(float(grp["amount"].sum())), round(float(hit["amount"].sum()))])
    by_cat.sort(key=lambda r: -r[5])
    out[key_prefix + "by_category"] = by_cat
    out[key_prefix + "by_category_columns"] = ["category", "accounts", "accounts_at_named_depository",
                                               "pct_at_named_depository", "dollars",
                                               "dollars_at_named_depository"]

    pairs = rows[rows["named"]].groupby(["category", "institution", "tier"], observed=True).agg(
        accounts=("acct", "nunique"), dollars=("amount", "sum")).reset_index()
    pairs = pairs.sort_values("dollars", ascending=False).head(TOP_PAIRS)
    out[key_prefix + "matrix"] = [[r.category, r.institution, r.tier, int(r.accounts), round(float(r.dollars))]
                                  for r in pairs.itertuples()]
    out[key_prefix + "matrix_columns"] = ["category", "institution", "tier", "accounts", "dollars"]
    out[key_prefix + "named_accounts"] = int(rows.loc[rows["named"], "acct"].nunique())
    out[key_prefix + "note"] = NOTE
    return out


def compute_from_layers(df: pd.DataFrame, fin_rows: pd.DataFrame, sub: pd.DataFrame,
                        account_filter: pd.Index | None = None, key_prefix: str = "fininst_") -> dict:
    """The same cross-tab, with the institution named by the registry. `sub` is
    `competition_layers.classify_cards`: one row per card transaction of the base, in the order of the
    card rows of `df` that belong to the base, with its institution and tier. An institution the
    registry could not place (ambiguous) is not named."""
    if df.empty or fin_rows is None or sub is None or not len(sub):
        return {}
    acct = df["primary_account_num"].astype(str)
    in_base = acct.isin(account_filter).to_numpy() if account_filter is not None         else np.ones(len(df), dtype=bool)
    mask = fin_rows["is_card"].to_numpy() & in_base
    if int(mask.sum()) != len(sub):                      # the rows must line up exactly, or say nothing
        return {}
    cat = fin_rows["category"].to_numpy()[mask]
    kind = fin_rows["kind"].to_numpy()[mask]
    leak = pd.notna(cat) & (kind == "leakage")
    if not leak.any():
        return {}
    inst = sub["inst"].to_numpy()
    tier = sub["tier"].to_numpy()
    named = leak & pd.notna(inst) & (tier != UNRESOLVED)
    rows = pd.DataFrame({"acct": sub["acct"].to_numpy()[leak], "category": cat[leak],
                         "amount": sub["amt"].to_numpy()[leak], "named": named[leak],
                         "institution": inst[leak], "tier": tier[leak]})
    out = _tables(rows, key_prefix)
    out[key_prefix + "source"] = "registry"
    return out
