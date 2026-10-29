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

    outliers = d[d["balance"].abs() > OUTLIER]
    out = {"file": path.name, "first": str(first.date()), "last": str(last.date()), "days": days,
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
