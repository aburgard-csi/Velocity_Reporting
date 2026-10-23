# Ported from ARS v5 02-Scripts/ars/transaction_intelligence/lens.py at a491b5c (James Gilmore); logic unchanged.
"""Lenses: account masks built from the ODD enrichment.

Every transaction section takes the same set of lenses and reports its
headline figures per lens, so "financial services for ARS responders" is the
same section with a different mask -- not a separate folder of code.

Built-ins (when the ODD columns exist):
    all, responders, mailed_nonresp, not_mailed, business, personal,
    new_accounts (opened in the last 12 months), recently_inactive
    (no spend in the last 3 months, spend in the 9 before), ics with its
    ics_dm / ics_ref channel split, and mrpc.

The ICS lens reads EITHER "ICS Account" or "DM-REF Source" (the column
ics_sources.py stamps from the DM and referral lists) -- see ics_masks().
Families (one mask per value, from the ODD attribute): branch, product
    (Prod Desc, falling back to Prod Code), swipe_tier (SwipeCat3).
    `Lenses.family("branch")` -> {value: account ids}; a family whose column
    is absent from the ODD returns {}.

Accounts are keyed by the ODD "Acct Number" (the hashed id the transaction
file uses); "Acct ID" is the fallback.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..core.account_lenses import (EXTRA, FAMILY_COLUMNS, ICS_FLAG_COLUMN,
                                  ICS_SOURCE_COLUMN, LABELS, PROGRAM_FLAGS,
                                  STANDARD, YES_VALUES, family_of, ics_masks,
                                  ics_warning, masks_for)
from ..core.subsets import branch_names, norm

# STANDARD, EXTRA, LABELS, YES_VALUES, PROGRAM_FLAGS, FAMILY_COLUMNS and
# ics_masks now live in core/account_lenses.py so monthly_analysis -- which
# runs BEFORE this layer and writes the frame it reads -- shares one
# definition of every cut. Re-exported above; import them from here or
# from core, they are the same objects.


@dataclass
class Lenses:
    key_column: str
    accounts: pd.Index                 # every ODD account id
    masks: dict                        # name -> pd.Series[bool] indexed by account id
    attrs: pd.DataFrame                # per-account attributes for profiles / lists

    def names(self) -> list[str]:
        return [n for n in STANDARD + EXTRA if n in self.masks]

    def label(self, name: str) -> str:
        return LABELS.get(name, name)

    def ids(self, name: str) -> pd.Index:
        m = self.masks[name]
        return m.index[m.to_numpy()]

    def family(self, name: str) -> dict:
        """{value: account ids} for a mask family (branch / product /
        swipe_tier). Empty dict when the ODD lacks the column."""
        return family_of(self.attrs, name)


def family_table(df: pd.DataFrame, lenses: "Lenses", family: str, top: int = 15) -> list[list]:
    """Accounts / txns / dollars per family value, largest first.

    Rows: [value, accounts, txns, dollars]. Empty list when the family is
    unavailable -- callers decline with a warn.
    """
    groups = lenses.family(family)
    if not groups:
        return []
    acct = df["primary_account_num"].astype(str)
    amt = df["amount"].abs()
    rows = []
    for value, ids in groups.items():
        mask = acct.isin(ids)
        n = int(acct[mask].nunique())
        if not n:
            continue
        rows.append([value, n, int(mask.sum()), round(float(amt[mask].sum()))])
    rows.sort(key=lambda r: -r[1])
    return rows[:top]


def _key(odd: pd.DataFrame) -> str | None:
    for c in ("Acct Number", " Acct Number", "Acct ID"):
        if c in odd.columns:
            return c
    return None


def build(odd: pd.DataFrame, anchor_end: pd.Timestamp, warn,
          branch_map: dict | None = None) -> Lenses | None:
    key = _key(odd)
    if key is None:
        warn("ODD has no Acct Number / Acct ID; lenses unavailable")
        return None
    ids = odd[key].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    df = odd.copy()
    df.index = ids
    df = df[~df.index.duplicated(keep="first")]
    # One definition, shared with monthly_analysis. This layer only supplies
    # the account-id index the transaction file joins on.
    masks = masks_for(df, anchor_end, warn)
    note = ics_warning(masks)
    if note:
        warn(note)

    keep = [c for c in ("Curr Bal", "Avg Bal", "Date Opened", "Branch", "Prod Desc", "Prod Code",
                        "Business?", "Debit?", "Response Grouping", "Account Holder Age",
                        "SwipeCat3", "last 12-mon spend") if c in df.columns]
    attrs = df[keep].copy()
    if "Date Opened" in attrs.columns:
        od = pd.to_datetime(attrs["Date Opened"], errors="coerce")
        attrs["tenure_years"] = ((anchor_end - od).dt.days / 365.2425).round(1)
    if "Branch" in attrs.columns:
        # One branch axis for the whole run: attrition groups by the mapped
        # display name, so anything that wants to sit beside it must too.
        attrs["Branch Name"] = branch_names(attrs["Branch"], branch_map or {})
    return Lenses(key_column=key, accounts=df.index, masks=masks, attrs=attrs)
