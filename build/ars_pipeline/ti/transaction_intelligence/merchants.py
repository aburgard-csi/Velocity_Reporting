# Ported from ARS v5 02-Scripts/ars/transaction_intelligence/merchants.py at a491b5c (James Gilmore); logic unchanged.
"""Merchants: where card spend actually goes.

financial_services and competition read the transfer rails; this section
reads the CARD rail -- top merchants, categories, what is new and what has
faded, and how spend differs by lens. Grouping is the derived merchant_key
(no hand-curated consolidation list). Categories come from MCC ranges when
the file populates MCC (1776), keyword buckets over the merchant key when it
does not (1615); the method used is always reported.

SPEC: SPEC-merchants.md. Keys: mch_* (personal base), mchb_* (business).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .financial_services import _pct
from .lens import Lenses
from ti.compat import str_values

TOP_MERCHANTS = 20
TOP_BY_LENS = 1
MATERIAL_SHARE = 0.0005          # a merchant matters when it holds >= 0.05% of card $
NEW_WINDOW_MONTHS = 3
# masked card/account refs some feeds (1441) carry as the description
# ('Xx5283 Purchase'); never a merchant, shared with merchant_profiles
MASKED_TOKEN = r"(?i)^x{1,2}\d+\b"


def load_categories(config_dir: Path) -> dict:
    return json.loads((config_dir / "merchant_categories.json").read_text(encoding="utf-8"))


def _keyword_regex(buckets: dict) -> list[tuple[str, re.Pattern]]:
    out = []
    for name, words in buckets.items():
        parts = [re.escape(w.strip()) for w in words if w.strip()]
        out.append((name, re.compile("|".join(parts))))
    return out


OTHER = "Other"
NO_PARENT = "Unmapped"


def group_ranges(entry) -> list:
    """A group is {"parent", "ranges"}; a bare list of ranges is the older
    shape and still reads, with no parent."""
    return entry["ranges"] if isinstance(entry, dict) else entry


def parents(spec: dict) -> dict:
    """group name -> parent, for every configured group and bucket."""
    out = {}
    for source in ("mcc_groups", "keyword_buckets"):
        for name, entry in (spec.get(source) or {}).items():
            if isinstance(entry, dict) and entry.get("parent"):
                out[name] = entry["parent"]
    out[OTHER] = NO_PARENT
    return out


def _categorize(card: pd.DataFrame, spec: dict, warn) -> tuple[pd.Series, str, float]:
    """Per-row category for card rows. Returns (categories, method, mcc_coverage_pct)."""
    mcc = pd.to_numeric(card["mcc_code"], errors="coerce") if "mcc_code" in card.columns \
        else pd.Series(np.nan, index=card.index)
    coverage = _pct(int(mcc.notna().sum()), len(card))
    if coverage >= spec.get("mcc_min_coverage_pct", 50):
        cats = pd.Series(OTHER, index=card.index, dtype=object)
        for name, entry in spec.get("mcc_groups", {}).items():
            mask = pd.Series(False, index=card.index)
            for lo, hi in group_ranges(entry):
                mask |= mcc.between(lo, hi)
            cats[mask] = name
        cats[mcc.isna()] = OTHER
        return cats, "mcc", coverage
    # keyword buckets over the distinct merchant keys only
    keys = str_values(card["merchant_key"])
    lookup = {}
    buckets = {n: (e["words"] if isinstance(e, dict) else e)
               for n, e in (spec.get("keyword_buckets") or {}).items()}
    rxs = _keyword_regex(buckets)
    for k in keys.unique():
        cat = next((name for name, rx in rxs if rx.search(k)), "Other")
        lookup[k] = cat
    if coverage:
        warn(f"merchants: MCC on only {coverage}% of card rows; keyword buckets used")
    return keys.map(lookup), "keywords", coverage


def compute(df: pd.DataFrame, lenses: Lenses | None, spec: dict, anchor_end: pd.Timestamp,
            warn, account_filter: pd.Index | None = None, key_prefix: str = "mch_",
            base_label: str = "all accounts") -> dict:
    out: dict = {}
    K = key_prefix
    typ = str_values(df["transaction_type"], lambda v: v.str.upper())
    is_card = typ.isin(["PIN", "SIG"]).to_numpy()
    if not is_card.any():
        warn("merchants: no card rows (PIN/SIG); section skipped")
        return out
    acct = df["primary_account_num"].astype(str)
    in_base = acct.isin(account_filter).to_numpy() if account_filter is not None \
        else np.ones(len(df), dtype=bool)
    card = df[is_card & in_base]
    if card.empty:
        warn(f"merchants: no card rows for {base_label}; section skipped")
        return out
    out[K + "base_label"] = base_label
    amt = card["amount"].abs()
    key = str_values(card["merchant_key"])
    total_spend = float(amt.sum())
    card_accts = card["primary_account_num"].astype(str)
    out[K + "card_accounts"] = int(card_accts.nunique())
    out[K + "card_spend"] = round(total_spend)

    # ---- 1. top merchants by card spend + concentration -----------------------
    g = pd.DataFrame({"key": key, "amount": amt, "acct": card_accts}).groupby("key", observed=True)
    per = g.agg(accounts=("acct", "nunique"), txns=("amount", "size"),
                dollars=("amount", "sum")).sort_values("dollars", ascending=False)
    # masked tokens are not merchants: some feeds (1441) carry the masked
    # card/account ref as the description ('Xx5283 Purchase') -- a key
    # that is a masked ref plus a generic word must never headline
    _masked = per.index.str.match(MASKED_TOKEN)
    if _masked.any():
        n_masked = int(_masked.sum())
        warn(f"merchants: {n_masked:,} masked description token(s) "
             f"excluded from merchant tables (they are account refs, "
             f"not merchants)")
        per = per[~_masked]
    per["avg_ticket"] = per["dollars"] / per["txns"]
    out[K + "distinct"] = len(per)
    rows = [[str(k), int(r.accounts), int(r.txns), round(float(r.dollars)),
             round(float(r.avg_ticket), 2), _pct(float(r.dollars), total_spend)]
            for k, r in per.head(TOP_MERCHANTS).iterrows()]
    out[K + "top"] = rows
    out[K + "top_columns"] = ["merchant", "accounts", "txns", "dollars", "avg_ticket", "pct_of_card_dollars"]
    out[K + "top15_share_pct"] = _pct(float(per["dollars"].head(15).sum()), total_spend)
    cum = per["dollars"].cumsum() / total_spend if total_spend else per["dollars"]
    out[K + "merchants_for_80pct"] = int((cum < 0.8).sum()) + 1 if len(per) else 0

    # ---- 2. categories ---------------------------------------------------------
    cats, method, coverage = _categorize(card, spec, warn)
    out[K + "category_method"] = method
    out[K + "mcc_coverage_pct"] = coverage
    cg = pd.DataFrame({"cat": cats, "amount": amt, "acct": card_accts}).groupby("cat", observed=True)
    par = parents(spec)
    crows = [[str(c), int(r["acct"].nunique()), int(len(r)), round(float(r["amount"].sum())),
              _pct(float(r["amount"].sum()), total_spend),
              par.get(str(c), NO_PARENT)] for c, r in cg]
    crows.sort(key=lambda r: -r[3])
    out[K + "by_category"] = crows
    out[K + "by_category_columns"] = ["category", "accounts", "txns", "dollars",
                                      "pct_of_card_dollars", "parent"]
    # the parent roll-up: what the chapter leads with before the detail
    pg: dict = {}
    for name, _n, txns, dollars, pct, parent in crows:
        row = pg.setdefault(parent, [parent, 0, 0, 0.0])
        row[1] += txns
        row[2] += dollars
        row[3] += pct
    prows = sorted(pg.values(), key=lambda r: -r[2])
    out[K + "by_parent"] = [[p, t, d, round(s, 1)] for p, t, d, s in prows]
    out[K + "by_parent_columns"] = ["parent", "txns", "dollars",
                                    "pct_of_card_dollars"]
    other = next((r for r in crows if r[0] == "Other"), None)
    if other and other[4] > 50:
        warn(f"merchants: {other[4]}% of card dollars uncategorised "
             f"({method}); the category table is context, not coverage")

    # ---- 3. new vs faded merchants --------------------------------------------
    month = card["transaction_date"].dt.to_period("M")
    months = sorted(month.unique())
    if len(months) > NEW_WINDOW_MONTHS:
        recent = set(months[-NEW_WINDOW_MONTHS:])
        material = per[per["dollars"] >= total_spend * MATERIAL_SHARE].index
        first = pd.DataFrame({"key": key, "m": month}).groupby("key", observed=True)["m"]
        fm, lm = first.min(), first.max()
        new = [k for k in material if fm.get(k) in recent]
        faded = [k for k in material if lm.get(k) not in recent]
        out[K + "new"] = [[k, round(float(per.loc[k, "dollars"])), int(per.loc[k, "accounts"])]
                          for k in sorted(new, key=lambda k: -per.loc[k, "dollars"])[:10]]
        out[K + "faded"] = [[k, round(float(per.loc[k, "dollars"])), int(per.loc[k, "accounts"])]
                            for k in sorted(faded, key=lambda k: -per.loc[k, "dollars"])[:10]]
        out[K + "new_faded_note"] = (f"material merchants (>= {MATERIAL_SHARE:.2%} of card $) "
                                     f"first/last seen inside the trailing {NEW_WINDOW_MONTHS} months")

    # ---- 4. by lens -------------------------------------------------------------
    if lenses is not None:
        all_card = df[is_card]
        a_acct = all_card["primary_account_num"].astype(str)
        a_amt = all_card["amount"].abs()
        a_key = str_values(all_card["merchant_key"])
        n_months = max(len(months), 1)
        by_lens = []
        for ln in lenses.names():
            ids = lenses.ids(ln)
            mask = a_acct.isin(ids)
            n = int(a_acct[mask].nunique())
            if not n:
                continue
            spend = float(a_amt[mask].sum())
            top = a_key[mask].groupby(a_key[mask]).size().sort_values(ascending=False)
            by_lens.append([ln, lenses.label(ln), n, round(spend / n),
                            round(float(mask.sum()) / n / n_months, 1),
                            str(top.index[0]) if len(top) else None])
        out[K + "by_lens"] = by_lens
        out[K + "by_lens_columns"] = ["lens", "label", "card_accounts", "spend_per_acct",
                                      "txns_per_acct_per_mo", "top_merchant"]
        by = {r[0]: r for r in by_lens}
        if "responders" in by and "mailed_nonresp" in by:
            out[K + "responder_spend_gap"] = round(by["responders"][3] - by["mailed_nonresp"][3])
    else:
        warn("merchants: no lenses; by-lens table skipped")

    # ---- 5. monthly trend -------------------------------------------------------
    mg = pd.DataFrame({"m": month, "amount": amt, "key": key}).groupby("m", observed=True)
    out[K + "monthly"] = [[str(m), int(r["key"].nunique()), round(float(r["amount"].sum()))]
                          for m, r in mg]
    out[K + "monthly_columns"] = ["month", "distinct_merchants", "card_dollars"]

    # ---- 6. ticket by merchant is carried in the top table (avg_ticket) ---------
    out[K + "ticket_note"] = "avg_ticket per merchant in " + K + "top"
    return out
