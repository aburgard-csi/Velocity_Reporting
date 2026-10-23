# Ported from ARS v5 02-Scripts/ars/transaction_intelligence/merchant_profiles.py at a491b5c (James Gilmore); logic unchanged.
"""Merchant profiles: who spends on the card, and how that is shifting.

merchants.py says where card spend goes. This module says which merchants
are rising or falling between two trailing windows, which MCC codes sit
behind the category roll-up, how many categories an account shops across,
and how card use differs by member age and account tenure (with how fast
a new account reaches its first swipe).

Legacy toolkit collapsed here (#258, group 3): merchant 06-09, 11, 13;
mcc_code 01-09, 13-14; general 11, 13-15, 21, 23-28 and the personal /
business mirrors. Same personal card base as merchants.py; the keys
continue the mch_* namespace.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .financial_services import _pct
from .lens import Lenses
from .merchants import MASKED_TOKEN, OTHER, _categorize, group_ranges
from .txn_common import ranked

GROWTH_WINDOW_MONTHS = 3
GROWTH_MOVERS = 5                    # biggest risers and biggest fallers shown
GROWTH_MIN_DOLLARS = 1_000           # legacy merchant/07: $1k in a window to be ranked
MOVE_PCT = 10.0                      # +/- 10% between windows counts as a move
TOP_MCC = 12
MIN_BAND_ACCOUNTS = 20
FIRST_SWIPE_GRACE_DAYS = 30          # days on file before "no swipe yet" means anything
AGE_BANDS = [(18, 26, "18-25"), (26, 36, "26-35"), (36, 46, "36-45"),
             (46, 56, "46-55"), (56, 65, "56-64"), (65, 200, "65+")]
TENURE_BANDS = [(0, 0.25, "< 3 mo"), (0.25, 1, "3-12 mo"), (1, 3, "1-3 yrs"),
                (3, 10, "3-10 yrs"), (10, 200, "10+ yrs")]
BREADTH_BANDS = [(0, 1, "none named"), (1, 2, "1"), (2, 4, "2-3"), (4, 6, "4-5"),
                 (6, 999, "6+")]
BREADTH_DEEP = 4
FIRST_SWIPE_BANDS = [(0, 8, "within 7 days"), (8, 31, "8-30 days"),
                     (31, 91, "31-90 days"), (91, 1e9, "90+ days")]
BAND_COLUMNS = ["band", "accounts", "spend_per_acct", "txns_per_acct_mo",
                "avg_ticket", "top_category"]


def _rows_frame(card: pd.DataFrame, spec: dict) -> pd.DataFrame:
    cats, _method, _cov = _categorize(card, spec, lambda _m: None)
    return pd.DataFrame({
        "acct": card["primary_account_num"].astype(str).to_numpy(),
        "key": card["merchant_key"].astype(str).to_numpy(),
        "amount": card["amount"].abs().to_numpy(),
        "cat": cats.to_numpy(),
        "m": card["transaction_date"].dt.to_period("M").to_numpy(),
        "date": card["transaction_date"].to_numpy()})


def _growth(rows: pd.DataFrame, months: list, K: str, warn) -> dict:
    w = GROWTH_WINDOW_MONTHS
    if len(months) < 2 * w:
        warn(f"merchant_profiles: {len(months)} months on file; rising and "
             f"falling needs {2 * w}")
        return {}
    recent, prior = months[-w:], months[-2 * w:-w]
    rec = rows[rows["m"].isin(recent)]
    r_d = rec.groupby("key")["amount"].sum()
    r_n = rec.groupby("key")["acct"].nunique()
    p_d = rows[rows["m"].isin(prior)].groupby("key")["amount"].sum()
    both = pd.DataFrame({"prior": p_d, "recent": r_d}).fillna(0.0)
    both = both[~both.index.str.match(MASKED_TOKEN)]
    lived = both[(both["prior"] > 0) & (both["recent"] > 0)
                 & ((both["prior"] >= GROWTH_MIN_DOLLARS)
                    | (both["recent"] >= GROWTH_MIN_DOLLARS))].copy()
    lived["change"] = lived["recent"] - lived["prior"]
    lived["pct"] = 100 * lived["change"] / lived["prior"]
    order = ranked(lived["change"])
    risers = [k for k in order.index[:GROWTH_MOVERS] if lived.loc[k, "change"] > 0]
    fallers = [k for k in order.index[::-1][:GROWTH_MOVERS] if lived.loc[k, "change"] < 0]
    table = [[str(k), int(r_n.get(k, 0)), round(float(lived.loc[k, "prior"])),
              round(float(lived.loc[k, "recent"])), round(float(lived.loc[k, "change"])),
              round(float(lived.loc[k, "pct"]), 1)]
             for k in risers + fallers[::-1]]
    book_p, book_r = float(both["prior"].sum()), float(both["recent"].sum())
    return {K + "growth": table,
            K + "growth_columns": ["merchant", "accounts_recent", "prior_dollars",
                                   "recent_dollars", "change_dollars", "change_pct"],
            K + "growth_window": (f"{recent[0].strftime('%b%y')}-{recent[-1].strftime('%b%y')} "
                                  f"against {prior[0].strftime('%b%y')}-{prior[-1].strftime('%b%y')}"),
            K + "growth_ranked_n": int(len(lived)),
            K + "growth_rising_n": int((lived["pct"] >= MOVE_PCT).sum()),
            K + "growth_falling_n": int((lived["pct"] <= -MOVE_PCT).sum()),
            K + "growth_book_pct": _pct(book_r - book_p, book_p)}


def _group_of(spec: dict):
    groups = [(name, group_ranges(entry))
              for name, entry in (spec.get("mcc_groups") or {}).items()]

    def lookup(code: int) -> str:
        return next((name for name, rng in groups
                     if any(lo <= code <= hi for lo, hi in rng)), OTHER)
    return lookup


def _mcc_codes(card: pd.DataFrame, spec: dict, K: str, warn) -> dict:
    if "mcc_code" not in card.columns:
        warn("merchant_profiles: no mcc_code column; the MCC table is skipped")
        return {}
    mcc = pd.to_numeric(card["mcc_code"], errors="coerce")
    coverage = _pct(int(mcc.notna().sum()), len(card))
    floor = spec.get("mcc_min_coverage_pct", 50)
    if coverage < floor:
        warn(f"merchant_profiles: MCC on {coverage}% of card rows; the MCC "
             f"table needs {floor}%; skipped")
        return {}
    ok = mcc.notna()
    per = pd.DataFrame({"code": mcc[ok].astype(int),
                        "amount": card["amount"].abs()[ok],
                        "acct": card["primary_account_num"].astype(str)[ok]}) \
        .groupby("code").agg(accounts=("acct", "nunique"), txns=("amount", "size"),
                             dollars=("amount", "sum"))
    per = per.sort_index().sort_values("dollars", ascending=False, kind="mergesort")
    total = float(per["dollars"].sum())
    name = _group_of(spec)
    rows = [[int(code), name(int(code)), int(r.accounts), int(r.txns),
             round(float(r.dollars)), round(float(r.dollars / r.txns), 2),
             _pct(float(r.dollars), total)]
            for code, r in per.head(TOP_MCC).iterrows()]
    return {K + "mcc_top": rows,
            K + "mcc_top_columns": ["mcc", "group", "accounts", "txns", "dollars",
                                    "avg_ticket", "pct_of_mcc_dollars"],
            K + "mcc_distinct": int(len(per)),
            K + "mcc_top5_share_pct": _pct(float(per["dollars"].head(5).sum()), total)}


def _breadth(per: pd.DataFrame, K: str) -> dict:
    n = len(per)
    bands = []
    for lo, hi, label in BREADTH_BANDS:
        sel = (per["named"] >= lo) & (per["named"] < hi)
        c = int(sel.sum())
        bands.append([label, c, _pct(c, n),
                      round(float(per.loc[sel, "spend"].mean())) if c else 0])
    return {K + "breadth_bands": bands,
            K + "breadth_bands_columns": ["categories", "accounts", "pct", "spend_per_acct"],
            K + "breadth_mean": round(float(per["named"].mean()), 1),
            K + "breadth_deep_pct": _pct(int((per["named"] >= BREADTH_DEEP).sum()), n)}


def _band_table(per: pd.DataFrame, values: pd.Series, bands, cat_dollars: pd.Series,
                n_months: int) -> list | None:
    v = pd.to_numeric(values.reindex(per.index), errors="coerce")
    if int(v.notna().sum()) < MIN_BAND_ACCOUNTS:
        return None
    table = []
    for lo, hi, label in bands:
        ids = v.index[(v >= lo) & (v < hi)]
        n = len(ids)
        if not n:
            continue
        p = per.loc[ids]
        spend, txns = float(p["spend"].sum()), int(p["txns"].sum())
        top = cat_dollars[cat_dollars.index.get_level_values(0).isin(ids)] \
            .groupby(level=1).sum()
        table.append([label, n, round(spend / n), round(txns / n / n_months, 1),
                      round(spend / txns, 2) if txns else 0.0,
                      str(ranked(top).index[0]) if len(top) else OTHER])
    return table


def _first_swipe(per: pd.DataFrame, attrs: pd.DataFrame, account_filter,
                 first_date, last_date, K: str, warn) -> dict:
    if "Date Opened" not in attrs.columns:
        return {}
    ids = attrs.index if account_filter is None \
        else attrs.index.intersection(pd.Index(account_filter).astype(str))
    opened = pd.to_datetime(attrs["Date Opened"], errors="coerce").reindex(ids)
    first_date, last_date = pd.Timestamp(first_date), pd.Timestamp(last_date)
    cutoff = last_date - pd.Timedelta(FIRST_SWIPE_GRACE_DAYS, "D")
    elig = opened[(opened >= first_date) & (opened <= cutoff)]
    n = len(elig)
    if n < MIN_BAND_ACCOUNTS:
        warn(f"merchant_profiles: {n} accounts opened inside the file's window; "
             f"time to first swipe needs {MIN_BAND_ACCOUNTS}")
        return {}
    first = pd.to_datetime(per["first"]).reindex(elig.index)
    days = (first - elig).dt.days.clip(lower=0)
    swiped = days.dropna()
    bands = [[label, int(((swiped >= lo) & (swiped < hi)).sum()),
              _pct(int(((swiped >= lo) & (swiped < hi)).sum()), n)]
             for lo, hi, label in FIRST_SWIPE_BANDS]
    never = n - len(swiped)
    bands.append(["no swipe yet", never, _pct(never, n)])
    return {K + "first_swipe_bands": bands,
            K + "first_swipe_bands_columns": ["band", "accounts", "pct"],
            K + "first_swipe_new_accounts": n,
            K + "first_swipe_median_days": int(swiped.median()) if len(swiped) else None,
            K + "first_swipe_within_30_pct": _pct(int((swiped <= 30).sum()), n),
            K + "first_swipe_window": (f"opened {first_date.strftime('%b%y')} - "
                                       f"{cutoff.strftime('%b%y')}, "
                                       f"{FIRST_SWIPE_GRACE_DAYS} days' grace")}


def compute(df: pd.DataFrame, lenses: Lenses | None, spec: dict, anchor_end: pd.Timestamp,
            warn, account_filter: pd.Index | None = None, key_prefix: str = "mch_",
            base_label: str = "all accounts") -> dict:
    out: dict = {}
    K = key_prefix
    typ = df["transaction_type"].astype(str).str.upper()
    is_card = typ.isin(["PIN", "SIG"]).to_numpy()
    acct_all = df["primary_account_num"].astype(str)
    in_base = acct_all.isin(account_filter).to_numpy() if account_filter is not None \
        else np.ones(len(df), dtype=bool)
    card = df[is_card & in_base]
    if card.empty:
        warn(f"merchant_profiles: no card rows for {base_label}; section skipped")
        return out
    rows = _rows_frame(card, spec)
    months = sorted(rows["m"].unique())
    n_months = max(len(months), 1)

    out.update(_growth(rows, months, K, warn))
    out.update(_mcc_codes(card, spec, K, warn))

    per = rows.groupby("acct").agg(spend=("amount", "sum"), txns=("amount", "size"),
                                   first=("date", "min"))
    named = rows[rows["cat"] != OTHER].groupby("acct")["cat"].nunique()
    per["named"] = named.reindex(per.index).fillna(0).astype(int)
    out.update(_breadth(per, K))

    if lenses is None:
        warn("merchant_profiles: no lenses; age, tenure and first-swipe cuts skipped")
        return out
    attrs = lenses.attrs
    cat_dollars = rows[rows["cat"] != OTHER].groupby(["acct", "cat"])["amount"].sum()
    for key, column, bands in (("by_age", "Account Holder Age", AGE_BANDS),
                               ("by_tenure", "tenure_years", TENURE_BANDS)):
        if column not in attrs.columns:
            warn(f"merchant_profiles: ODD has no {column}; {key} skipped")
            continue
        table = _band_table(per, attrs[column], bands, cat_dollars, n_months)
        if table is None:
            warn(f"merchant_profiles: fewer than {MIN_BAND_ACCOUNTS} card accounts "
                 f"carry {column}; {key} skipped")
            continue
        out[K + key] = table
        out[K + key + "_columns"] = BAND_COLUMNS
    out.update(_first_swipe(per, attrs, account_filter,
                            card["transaction_date"].min(), card["transaction_date"].max(),
                            K, warn))
    return out
