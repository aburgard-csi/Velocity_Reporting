"""The fee chapter from the raw overdraft notice items (the First Notice File), RPE 2026-10-28.

James Gilmore, 2026-10-28: "i added 120 days of raw overdraft notice data in the 1759 zip". The PGL
extract alone cannot price a daily fee cap or a de minimis waiver (v5 declined both: "NOT COMPUTABLE from a
PGL extract"); the notice items can: every NSF/OD item with its account, date, amount, ending balance, fee
assessed and paid (PD) / returned (RT) status. From them, over the file's own window and annualized:

  fee baseline     items, % of items, fee per item, revenue and % of revenue, by paid / returned
  daily fee cap    the fees past the Nth on one account in one day, for N = 4, 5, 6 (Velocity: 4-6)
  de minimis       fees on items of $2 or less (transaction), and on items that leave the account
                   overdrawn by $5 / $10 or less (balance: ending balance from -X to below 0)

Each scenario is what would be waived if it alone were in place; they overlap, so they are not added.
An item's order within an account's day is its import id. Keys: pgl_notices.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

NOTICE_RX = re.compile(r"notice|(?<![a-z])fnf(?![a-z])", re.I)
CAPS = (4, 5, 6)
TXN_DE_MINIMIS = (2,)
BAL_DE_MINIMIS = (5, 10)
OUTLIER = 9999
COL = {"acct": "ILS Account ID", "amount": "NSF-Overdraft Item Amount", "date": "NSF-Overdraft Item Date",
       "balance": "NSF-Overdraft Item Ending Balance", "fee": "NSF-Overdraft Item Fee Assessed",
       "status": "NSF-Overdraft Item Status", "type": "NSF-Overdraft Item Transaction Type",
       "import": "NSF-Overdraft Item Import ID"}
LABEL = {"PD": "Paid (OD) items", "RT": "Returned (NSF) items"}


def find(folder):
    hits = sorted(p for p in Path(folder).iterdir()
                  if p.is_file() and p.suffix.lower() in (".csv", ".xlsx") and NOTICE_RX.search(p.name))
    return hits[-1] if hits else None


def _read(path):
    df = pd.read_csv(path, dtype=str) if path.suffix.lower() == ".csv" else pd.read_excel(path, dtype=str)
    missing = [c for c in COL.values() if c not in df.columns]
    if missing:
        raise ValueError(f"{path.name} lacks {missing}")
    out = pd.DataFrame({
        "acct": df[COL["acct"]].astype(str).str.strip(),
        "amount": pd.to_numeric(df[COL["amount"]], errors="coerce"),
        "date": pd.to_datetime(df[COL["date"]], format="%m/%d/%Y %I:%M:%S %p", errors="coerce"),
        "balance": pd.to_numeric(df[COL["balance"]], errors="coerce"),
        "fee": pd.to_numeric(df[COL["fee"]], errors="coerce").fillna(0.0),
        "status": df[COL["status"]].astype(str).str.strip().str.upper(),
        "type": df[COL["type"]].fillna("").astype(str).str.strip(),
        "import": pd.to_numeric(df[COL["import"]], errors="coerce"),
    })
    if out["date"].isna().all():                      # another date layout: let pandas infer it
        out["date"] = pd.to_datetime(df[COL["date"]], errors="coerce")
    return out


def _r(v, d=2):
    return round(float(v), d)


CAP_CURVE = range(1, 11)
TXN_CURVE = (1, 2, 3, 5, 10)
BAL_CURVE = (5, 10, 15, 20, 25, 50)
AMOUNT_BANDS = ((0, 2, "$2 or less"), (2, 5, "$2–$5"), (5, 10, "$5–$10"), (10, 25, "$10–$25"),
                (25, 50, "$25–$50"), (50, 100, "$50–$100"), (100, float("inf"), "Over $100"))
BALANCE_BANDS = ((5, "$5 or less"), (10, "$5–$10"), (25, "$10–$25"), (50, "$25–$50"), (100, "$50–$100"),
                 (500, "$100–$500"), (float("inf"), "Over $500"))
# The combined grid: each combination of a daily cap, a transaction and a balance de minimis, applied
# together to the same items (de minimis first: a waived item is not charged, so it does not count toward the
# day's cap). Velocity's guidance is a cap of 4-6 fees a day, a $2 transaction and a $5-$10 balance de minimis.
GRID_CAPS = (None, 4, 5, 6)
GRID_TXN = (0, 2)
GRID_BAL = (0, 5, 10)


def _pricing(charged, nth, per_day, total_fee, year):
    """The daily-cap and de minimis curves, and the combined grid with the fee that holds revenue."""
    def share(x):
        return _r(x / total_fee, 4) if total_fee else None

    days = per_day.value_counts().sort_index()
    fee_by_n = charged.assign(n=charged.groupby([charged["acct"], charged["date"].dt.date])["fee"].transform("size"))
    per_day_dist = []
    for n_, cnt in days.items():
        lbl = str(n_) if n_ < 10 else "10+"
        if per_day_dist and per_day_dist[-1][0] == "10+":
            per_day_dist[-1][1] += int(cnt)
            continue
        dollars = float(fee_by_n.loc[(fee_by_n["n"] >= 10) if n_ >= 10 else (fee_by_n["n"] == n_), "fee"].sum())
        per_day_dist.append([lbl, int(cnt), _r(dollars)])

    cap_curve = []
    for cap in CAP_CURVE:
        w = charged[nth > cap]
        cap_curve.append([cap, len(w), int(w["acct"].nunique()), _r(w["fee"].sum()), _r(w["fee"].sum() * year),
                          share(w["fee"].sum())])
    txn_curve = []
    for x in TXN_CURVE:
        w = charged[charged["amount"] <= x]
        txn_curve.append([x, len(w), int(w["acct"].nunique()), _r(w["fee"].sum()), _r(w["fee"].sum() * year),
                          share(w["fee"].sum())])
    bal_curve = []
    for x in BAL_CURVE:
        w = charged[(charged["balance"] >= -x) & (charged["balance"] < 0)]
        bal_curve.append([x, len(w), int(w["acct"].nunique()), _r(w["fee"].sum()), _r(w["fee"].sum() * year),
                          share(w["fee"].sum())])
    amount_bands = []
    for lo, hi, lbl in AMOUNT_BANDS:
        g = charged[(charged["amount"] > lo) & (charged["amount"] <= hi)] if lo else charged[charged["amount"] <= hi]
        amount_bands.append([lbl, len(g), _r(g["fee"].sum())])
    over = -charged["balance"]
    balance_bands, lo = [], 0
    for hi, lbl in BALANCE_BANDS:
        g = charged[(over > lo) & (over <= hi)]
        balance_bands.append([lbl, len(g), _r(g["fee"].sum())])
        lo = hi

    grid = []
    base_items = len(charged)
    for cap in GRID_CAPS:
        for tx in GRID_TXN:
            for bal in GRID_BAL:
                waive = pd.Series(False, index=charged.index)
                if tx:
                    waive |= charged["amount"] <= tx
                if bal:
                    waive |= (charged["balance"] >= -bal) & (charged["balance"] < 0)
                kept = charged[~waive]
                if cap:
                    k_nth = kept.groupby([kept["acct"], kept["date"].dt.date]).cumcount() + 1
                    kept = kept[k_nth <= cap]
                kept_fee = float(kept["fee"].sum())
                relief = total_fee - kept_fee
                # the uniform fee multiplier that brings the kept items back to today's revenue
                mult = (total_fee / kept_fee) if kept_fee else None
                name = ", ".join(p for p in (f"cap {cap}" if cap else "", f"${tx} transaction" if tx else "",
                                             f"${bal} balance" if bal else "") if p) or "Today (no cap, no de minimis)"
                guided = bool(cap and 4 <= cap <= 6 and tx == 2 and bal in (5, 10))
                grid.append([name, cap or 0, tx, bal, base_items - len(kept), _r(relief * year), share(relief),
                             _r(kept_fee * year), _r(mult, 4) if mult else None, guided])
    return {"per_day_dist": per_day_dist, "per_day_columns": ["fees_in_one_day", "account_days", "fee_dollars"],
            "cap_curve": cap_curve, "txn_curve": txn_curve, "bal_curve": bal_curve,
            "curve_columns": ["threshold", "fees_waived", "accounts_helped", "dollars_waived",
                              "dollars_waived_annualized", "pct_of_revenue"],
            "amount_bands": amount_bands, "balance_bands": balance_bands,
            "bands_columns": ["band", "fee_items", "fee_dollars"],
            "grid": grid, "grid_columns": ["structure", "cap", "txn_de_minimis", "balance_de_minimis", "fees_waived",
                                           "relief_annualized", "pct_of_revenue", "revenue_annualized",
                                           "revenue_neutral_multiplier", "within_velocity_guidance"]}


def compute(folder, warn=lambda m: None) -> dict:
    path = find(folder)
    if path is None:
        return {}
    try:
        d = _read(path)
    except Exception as exc:
        warn(f"notice file {path.name} not read ({type(exc).__name__}: {exc})")
        return {"pgl_notices": {"file": path.name, "error": f"{type(exc).__name__}: {exc}"}}
    d = d[d["date"].notna()]
    first, last = d["date"].min(), d["date"].max()
    days = int((last - first).days) + 1
    year = 365.0 / days if days else 0.0
    total_items, total_fee = len(d), float(d["fee"].sum())

    baseline = []
    for code in sorted(d["status"].unique()):
        g = d[d["status"] == code]
        charged = g[g["fee"] > 0]
        fee = float(g["fee"].sum())
        baseline.append([LABEL.get(code, code), len(g), _r(len(g) / total_items, 4) if total_items else None,
                         _r(charged["fee"].mean()) if len(charged) else 0.0, _r(fee),
                         _r(fee / total_fee, 4) if total_fee else None])
    baseline.append(["Total", total_items, 1.0, _r(d.loc[d["fee"] > 0, "fee"].mean()) if (d["fee"] > 0).any() else 0.0,
                     _r(total_fee), 1.0])

    charged = d[d["fee"] > 0].sort_values(["acct", "date", "import"])
    nth = charged.groupby([charged["acct"], charged["date"].dt.date]).cumcount() + 1
    per_day = charged.groupby([charged["acct"], charged["date"].dt.date]).size()
    scenarios = []
    for cap in CAPS:
        w = charged[nth > cap]
        scenarios.append([f"Daily fee cap of {cap}", len(w), _r(w["fee"].sum()), _r(w["fee"].sum() * year),
                          _r(w["fee"].sum() / total_fee, 4) if total_fee else None])
    for x in TXN_DE_MINIMIS:
        w = charged[charged["amount"] <= x]
        scenarios.append([f"Transaction de minimis ${x}", len(w), _r(w["fee"].sum()), _r(w["fee"].sum() * year),
                          _r(w["fee"].sum() / total_fee, 4) if total_fee else None])
    for x in BAL_DE_MINIMIS:
        w = charged[(charged["balance"] >= -x) & (charged["balance"] < 0)]
        scenarios.append([f"Balance de minimis ${x}", len(w), _r(w["fee"].sum()), _r(w["fee"].sum() * year),
                          _r(w["fee"].sum() / total_fee, 4) if total_fee else None])

    extra = _pricing(charged, nth, per_day, total_fee, year)

    outliers = d[d["balance"].abs() > OUTLIER]
    out = {**extra, "file": path.name, "first": str(first.date()), "last": str(last.date()), "days": days,
           "items": total_items, "accounts": int(d["acct"].nunique()), "revenue": _r(total_fee),
           "revenue_annualized": _r(total_fee * year),
           "fee_per_item": {code: _r(d.loc[(d["status"] == code) & (d["fee"] > 0), "fee"].median())
                            for code in d["status"].unique() if ((d["status"] == code) & (d["fee"] > 0)).any()},
           "baseline": baseline,
           "baseline_columns": ["category", "items", "pct_of_items", "fee_per_item", "revenue", "pct_of_revenue"],
           "scenarios": scenarios,
           "scenarios_columns": ["scenario", "fees_waived", "dollars_waived", "dollars_waived_annualized",
                                 "pct_of_revenue"],
           "max_fees_one_day": int(per_day.max()) if len(per_day) else 0,
           "by_type": [[t or "(blank)", int(n)] for t, n in d["type"].value_counts().items()],
           "outliers": int(len(outliers)), "outlier_min_balance": _r(outliers["balance"].min()) if len(outliers) else None}
    if len(outliers):
        warn(f"notice file: {len(outliers)} items with an ending balance beyond ±${OUTLIER:,} "
             f"(lowest {out['outlier_min_balance']:,}) — check them before quoting the balance de minimis")
    return {"pgl_notices": out}
