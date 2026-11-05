"""The deposits file at the daily grain, and what leaves an account in the days after money arrives.

R7 (James, 2026-11-05): "we should have daily [deposit] amounts (aggregate count and amount), we
could tie up with large txns around bnpl or something", then "i meant daily deposit amounts (the
daily aggregate amount)", and "r7 daily deposit amount could be overlayed with any and all spend
categories".

Two halves, both pure functions of plain frames so each can be tested on synthetic rows:

    daily / weekday / day_of_month / top_days
        The deposits file summed per calendar day: deposits, dollars, distinct accounts. Every
        calendar day between the file's first and last date is a row, a day with nothing posted
        included as zero, so an average day is an average CALENDAR day (weekends and holidays in).

    timing
        For accounts in BOTH files: the share of each outflow category's dollars spent 0-3 days
        after one of the account's own deposits, against the share that would fall there if the
        account spent evenly across the days it was observed. Expected share per account = days
        within 0-3 days after a deposit / days observed; a category's expected share is that,
        weighted by each account's dollars in the category. Ratio = actual / expected: 1.0 is no
        timing at all, 1.5 is half again as much spent in the window as an even spread would put
        there.

"Large" is the account's own: a transaction above that account's 90th percentile outflow
amount (strictly above, so an account whose outflows are mostly one repeated amount does not mark
them all large), for accounts with at least LARGE_MIN_TXNS outflows in the window (fewer and the
percentile is two or three transactions). One fixed dollar threshold would mark every outflow of a business
account and none of a student's.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WINDOW_DAYS = 3            # 0-3 days after a deposit: the deposit day and the three after it
MAX_DAYS = 366             # the daily series stored in the pack, at most
LARGE_PCTL = 0.90
LARGE_MIN_TXNS = 10
LARGE = "Large transactions"
ALL = "All outflows"
BNPL = "Buy Now Pay Later"
# A category's ratio is reported only on this base. Below it the ratio is a handful of accounts'
# paydays, not a pattern.
MIN_ACCOUNTS = 30
MIN_TXNS = 200
# Daily series kept in the pack: the categories that pass the base above, the largest by dollars,
# at most this many (plus All outflows, Large transactions and BNPL whenever they pass).
MAX_CATEGORIES = 20
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def key(series) -> pd.Series:
    """Account ids compared as text: trimmed, a float's '.0' dropped, upper case."""
    return series.astype(str).str.strip().str.replace(r"\.0$", "", regex=True).str.upper()


# ------------------------------------------------------------------ the daily series
def daily(raw: pd.DataFrame) -> pd.DataFrame:
    """date, deposits, dollars, accounts: one row per calendar day, the last MAX_DAYS days of the
    file. Credits only (a non-positive amount is a reversal, not a deposit)."""
    cols = ["date", "deposits", "dollars", "accounts"]
    if raw is None or not len(raw):
        return pd.DataFrame(columns=cols)
    r = raw[pd.to_numeric(raw["dep_amount"], errors="coerce") > 0]
    if not len(r):
        return pd.DataFrame(columns=cols)
    day = pd.to_datetime(r["date"]).dt.normalize()
    count = (pd.to_numeric(r["dep_count"], errors="coerce").fillna(1)
             if "dep_count" in r.columns else pd.Series(1, index=r.index))
    g = pd.DataFrame({"date": day, "deposits": count, "dollars": r["dep_amount"].astype(float),
                      "acct": r["acct"]}).groupby("date").agg(
        deposits=("deposits", "sum"), dollars=("dollars", "sum"), accounts=("acct", "nunique"))
    days = pd.date_range(g.index.min(), g.index.max(), freq="D")
    g = g.reindex(days, fill_value=0).tail(MAX_DAYS)
    g.index.name = "date"
    out = g.reset_index()
    out["deposits"] = out["deposits"].round().astype(int)
    out["accounts"] = out["accounts"].astype(int)
    return out[cols]


def rows(d: pd.DataFrame) -> list:
    """The pack's form: [[yyyy-mm-dd, deposits, dollars, accounts], ...]."""
    return [[t.strftime("%Y-%m-%d"), int(n), round(float(v)), int(a)]
            for t, n, v, a in zip(d["date"], d["deposits"], d["dollars"], d["accounts"])]


def summary(d: pd.DataFrame) -> dict:
    if not len(d):
        return {}
    return {"days": int(len(d)), "active_days": int((d["dollars"] > 0).sum()),
            "first": d["date"].iloc[0].strftime("%Y-%m-%d"),
            "last": d["date"].iloc[-1].strftime("%Y-%m-%d"),
            "avg_dollars": round(float(d["dollars"].mean())),
            "median_dollars": round(float(d["dollars"].median())),
            "avg_deposits": round(float(d["deposits"].mean()), 1),
            "median_deposits": round(float(d["deposits"].median()), 1),
            "total_dollars": round(float(d["dollars"].sum()))}


def _pattern(d: pd.DataFrame, by: pd.Series, labels) -> list:
    avg = float(d["dollars"].mean()) or 1.0
    g = d.groupby(by.values).agg(days=("dollars", "size"), deposits=("deposits", "mean"),
                                 dollars=("dollars", "mean"))
    return [[labels(k), int(r.days), round(float(r.deposits), 1), round(float(r.dollars)),
             round(100 * float(r.dollars) / avg, 1)] for k, r in g.iterrows()]


def weekday(d: pd.DataFrame) -> list:
    """[weekday, days, avg deposits, avg dollars, % of the average day], Monday first."""
    if not len(d):
        return []
    return _pattern(d, d["date"].dt.dayofweek, lambda k: WEEKDAYS[int(k)])


def day_of_month(d: pd.DataFrame) -> list:
    """[day of month, days, avg deposits, avg dollars, % of the average day], 1 to 31."""
    if not len(d):
        return []
    return _pattern(d, d["date"].dt.day, int)


def top_days(d: pd.DataFrame, n: int = 10) -> list:
    """[date, weekday, deposits, dollars, accounts], the n biggest days by dollars."""
    if not len(d):
        return []
    top = d.nlargest(n, "dollars")
    return [[t.strftime("%Y-%m-%d"), WEEKDAYS[t.dayofweek], int(c), round(float(v)), int(a)]
            for t, c, v, a in zip(top["date"], top["deposits"], top["dollars"], top["accounts"])]


# ------------------------------------------------------------------ deposit-to-outflow timing
FAMILIES = ["all", "card", "financial services", "size"]


def _keyed(series) -> tuple:
    """(row codes, unique normalised keys): `key` run on the distinct ids only, never on every row
    (a transaction file runs to tens of millions of rows; 1798's took most of an hour)."""
    codes, uniq = pd.factorize(pd.Series(series).to_numpy(), sort=False)
    k = key(pd.Series(uniq, dtype=object)) if len(uniq) else pd.Series([], dtype=object)
    kc, kuniq = pd.factorize(k.to_numpy(), sort=False)
    rows = np.where(codes >= 0, kc[np.clip(codes, 0, None)] if len(kc) else -1, -1)
    return rows.astype(np.int64), pd.Index(kuniq)


def _aligned(cat: pd.Series, index) -> np.ndarray:
    if cat.index.equals(index):
        return cat.to_numpy(object)
    return cat.reindex(index).to_numpy(object)


def flows(txn: pd.DataFrame, card_category: pd.Series | None,
          fin_category: pd.Series | None) -> pd.DataFrame:
    """One row per (transaction, category it counts in): acct, date, amount, category, family,
    acct / category / family as categoricals.

    Every transaction counts in "All outflows"; a card row also in its merchant category (MCC, or
    keywords when MCC is thin); any row in its financial-services category (BNPL among them).
    A card BNPL purchase therefore counts in both families, as it should: the overlay asks of each
    category on its own. "Other" card spend is left out (it names nothing). "Large transactions" is
    a category with no rows here; `_large` fills it on the rows a figure is drawn from."""
    if not txn.index.is_unique:
        txn = txn.reset_index(drop=True)
    acct_codes, accts = _keyed(txn["primary_account_num"])
    date = pd.to_datetime(txn["transaction_date"], errors="coerce").dt.normalize().to_numpy()
    amount = pd.to_numeric(txn["amount"], errors="coerce").abs().to_numpy(float)
    ok = (acct_codes >= 0) & ~np.isnan(amount) & (amount > 0) & ~pd.isna(date)
    names, fams = [ALL, LARGE], [0, 3]
    rows, cats = [np.flatnonzero(ok)], [np.zeros(int(ok.sum()), np.int32)]
    card_names: set = set()
    for fam, cat in (("card", card_category), ("financial services", fin_category)):
        if cat is None:
            continue
        vals = _aligned(cat, txn.index)
        keep = ok & ~pd.isna(vals)
        keep &= vals.astype(str) != "Other"
        if not keep.any():
            continue
        c, u = pd.factorize(vals[keep].astype(str), sort=True)
        u = [str(x) for x in u]
        if fam == "card":
            card_names = set(u)
        else:
            # one name, one series: a financial-services category spelled like a card one is told apart
            u = [f"{x} (financial services)" if x in card_names else x for x in u]
        rows.append(np.flatnonzero(keep))
        cats.append(c.astype(np.int32) + len(names))
        names += u
        fams += [FAMILIES.index(fam)] * len(u)
    r = np.concatenate(rows)
    code = np.concatenate(cats)
    return pd.DataFrame({
        "acct": pd.Categorical.from_codes(acct_codes[r], categories=accts),
        "date": date[r], "amount": amount[r],
        "category": pd.Categorical.from_codes(code, categories=names),
        "family": pd.Categorical.from_codes(np.asarray(fams)[code], categories=FAMILIES)})


def _large(f: pd.DataFrame) -> pd.DataFrame:
    """The All-outflows rows above their own account's 90th percentile, as "Large transactions"."""
    a = f[(f["category"] == ALL).to_numpy()]
    if not len(a):
        return a
    codes = a["acct"].cat.codes.to_numpy()
    grp = a["amount"].groupby(codes)
    n = grp.size().reindex(codes).to_numpy()
    p = grp.quantile(LARGE_PCTL).reindex(codes).to_numpy()
    big = a[(n >= LARGE_MIN_TXNS) & (a["amount"].to_numpy() > p)].copy()
    big["category"] = pd.Categorical.from_codes(
        np.full(len(big), list(f["category"].cat.categories).index(LARGE)),
        categories=f["category"].cat.categories)
    big["family"] = pd.Categorical.from_codes(np.full(len(big), FAMILIES.index("size")),
                                              categories=FAMILIES)
    return big


def timing(raw: pd.DataFrame, f: pd.DataFrame) -> dict:
    """The deposit-timing table, for the accounts in both files, on the days both files cover.

    Returns {} when no account is in both or the two files share no days, else:
        rows        [category, family, accounts, txns, dollars, pct_dollars_in_window,
                     pct_expected, ratio, shown], ratio None where the base is under the floor
        accounts    accounts in both files
        start, end  the days both files cover
        expected    the book's share of account-days within the window (unweighted)
    """
    if raw is None or not len(raw) or f is None or not len(f):
        return {}
    amt_d = pd.to_numeric(raw["dep_amount"], errors="coerce").to_numpy(float)
    date_d = pd.to_datetime(raw["date"], errors="coerce").dt.normalize().to_numpy()
    d_rows, d_keys = _keyed(raw["acct"])
    cats = f["acct"].cat.categories
    pos = cats.get_indexer(d_keys)                       # each deposit key's place among f's accounts
    d_acct = np.where(d_rows >= 0, pos[np.clip(d_rows, 0, None)] if len(pos) else -1, -1)
    good = (amt_d > 0) & (d_acct >= 0) & ~pd.isna(date_d)
    f_acct = f["acct"].cat.codes.to_numpy()
    common = np.intersect1d(np.unique(d_acct[good]), np.unique(f_acct[f_acct >= 0]))
    if not len(common):
        return {}
    start = max(pd.Timestamp(date_d[good].min()), pd.Timestamp(f["date"].min()))
    end = min(pd.Timestamp(date_d[good].max()), pd.Timestamp(f["date"].max()))
    if end < start:
        return {}
    span = int((end - start).days) + 1
    lookup = np.full(len(cats), -1, np.int64)
    lookup[common] = np.arange(len(common))
    epoch = np.datetime64(start - pd.Timedelta(days=WINDOW_DAYS), "ns")

    d_day = ((date_d - epoch) // np.timedelta64(1, "D")).astype(np.int64)
    sel = good & (lookup[np.clip(d_acct, 0, None)] >= 0) & (d_day >= 0) & (d_day <= span + WINDOW_DAYS - 1)
    d_code = lookup[d_acct[sel]]
    width = span + 2 * WINDOW_DAYS + 2
    covered = np.unique(np.concatenate([d_code * width + d_day[sel] + k for k in range(WINDOW_DAYS + 1)]))
    # covered account-days inside [start, end] only, per account: the expected share's numerator
    c_day = covered % width
    inside = (c_day >= WINDOW_DAYS) & (c_day < WINDOW_DAYS + span)
    per_acct = np.bincount((covered[inside] // width).astype(np.int64), minlength=len(common))
    frac = per_acct / span

    f_code_all = np.where(f_acct >= 0, lookup[np.clip(f_acct, 0, None)], -1)
    dates = f["date"].to_numpy()
    in_g = (f_code_all >= 0) & (dates >= np.datetime64(start, "ns")) & (dates <= np.datetime64(end, "ns"))
    g = f[in_g]
    if not len(g):
        return {}
    g = pd.concat([g, _large(g)], ignore_index=True)
    g_code = lookup[g["acct"].cat.codes.to_numpy()]
    g_key = g_code * width + ((g["date"].to_numpy() - epoch) // np.timedelta64(1, "D")).astype(np.int64)
    hit = np.isin(g_key, covered)
    amt = g["amount"].to_numpy(float)
    work = pd.DataFrame({"category": g["category"], "family": g["family"],
                         "code": g_code, "amt": amt, "in_amt": np.where(hit, amt, 0.0),
                         "exp_amt": amt * frac[g_code]})
    agg = work.groupby(["category", "family"], sort=False, observed=True).agg(
        accounts=("code", "nunique"), txns=("amt", "size"), dollars=("amt", "sum"),
        in_dollars=("in_amt", "sum"), exp_dollars=("exp_amt", "sum"))
    out = []
    for (cat, fam), r in agg.iterrows():
        if not r.dollars:
            continue
        actual = 100 * r.in_dollars / r.dollars
        expected = 100 * r.exp_dollars / r.dollars
        shown = bool(r.accounts >= MIN_ACCOUNTS and r.txns >= MIN_TXNS and expected > 0)
        out.append([str(cat), str(fam), int(r.accounts), int(r.txns), round(float(r.dollars)),
                    round(float(actual), 1), round(float(expected), 1),
                    round(float(actual / expected), 2) if shown else None, shown])
    out.sort(key=lambda r: (not r[8], -(r[7] or 0), -r[4]))
    return {"rows": out, "accounts": int(len(common)),
            "start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d"),
            "expected": round(float(100 * frac.mean()), 1)}


def category_daily(f: pd.DataFrame, keep: list, start, end) -> dict:
    """{category: [[yyyy-mm-dd, txns, dollars], ...]} for the categories in `keep`, the days in
    [start, end] with activity only. Book-wide (every account in the transaction file), so it is
    read against the book-wide deposit series."""
    if f is None or not len(f) or not keep:
        return {}
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    g = f[(f["date"] >= start) & (f["date"] <= end)]
    big = _large(g) if LARGE in keep else g.iloc[0:0]
    g = pd.concat([g[g["category"].isin(keep).to_numpy()], big], ignore_index=True)
    if not len(g):
        return {}
    agg = g.groupby(["category", "date"], observed=True).agg(txns=("amount", "size"),
                                                         dollars=("amount", "sum"))
    out: dict = {}
    for (cat, day), r in agg.iterrows():
        if r.txns:
            out.setdefault(str(cat), []).append([day.strftime("%Y-%m-%d"), int(r.txns),
                                            round(float(r.dollars))])
    return {c: out[c] for c in keep if c in out}


def kept_categories(rows_: list) -> list:
    """The categories whose daily series go in the pack: those whose ratio is shown, All outflows,
    Large transactions and BNPL first, then the rest by dollars, MAX_CATEGORIES in all."""
    shown = [r for r in rows_ if r[8]]
    first = [r[0] for r in shown if r[0] in (ALL, LARGE, BNPL)]
    rest = [r[0] for r in sorted(shown, key=lambda r: -r[4]) if r[0] not in first]
    seen, out = set(), []
    for c in first + rest:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out[:MAX_CATEGORIES]
