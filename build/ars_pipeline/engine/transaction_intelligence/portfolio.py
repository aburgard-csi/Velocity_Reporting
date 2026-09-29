"""Portfolio block: the first look at a client's transaction file.

Six things, before any section: what was loaded (files, rows, months, and
how the months line up with the ODD); volume by channel (PIN / SIG / ACH /
CHK); active accounts and transactions per account; the ODD join rate;
top merchants by transactions; the monthly series.

Amounts are signed as delivered. The share of negative rows is reported;
nothing is flipped.
"""

from __future__ import annotations

from .txn_common import ranked, norm_accounts, odd_account_key

import pandas as pd

from ..core.deposits import MIN_MATCH_PCT

TOP_MERCHANTS = 15
CHANNELS = ["PIN", "SIG", "ACH", "CHK"]


def _pct(n, d) -> float:
    return round(100 * n / d, 1) if d else 0.0


def compute(df: pd.DataFrame, odd: pd.DataFrame | None, warn, acct_key=None) -> dict:
    out: dict = {}
    if df.empty:
        return out
    n = len(df)
    out["txn_rows"] = n
    first, last = df["transaction_date"].min(), df["transaction_date"].max()
    out["txn_first_date"] = first.strftime("%Y-%m-%d")
    out["txn_last_date"] = last.strftime("%Y-%m-%d")
    out["txn_months_covered"] = int(df["transaction_date"].dt.to_period("M").nunique())
    out["txn_negative_amount_pct"] = _pct(int((df["amount"] < 0).sum()), n)
    out["txn_amount_missing_pct"] = _pct(int(df["amount"].isna().sum()), n)

    # ---- by channel -------------------------------------------------------
    typ = df["transaction_type"].astype(str).str.upper().str.strip()
    seen = sorted(typ.unique())
    unknown = [t for t in seen if t not in CHANNELS]
    if unknown:
        warn(f"transaction types outside PIN/SIG/ACH/CHK: {unknown[:6]}")
    amt = df["amount"].abs()
    rows = []
    for ch in CHANNELS + unknown:
        mask = typ == ch
        c = int(mask.sum())
        if not c:
            continue
        a = float(amt[mask].sum())
        rows.append([ch, c, _pct(c, n), round(a), round(a / c, 2)])
    out["txn_by_channel"] = rows
    out["txn_spend_total"] = round(float(amt.sum()))
    card = typ.isin(["PIN", "SIG"])
    out["txn_card_rows"] = int(card.sum())
    out["txn_card_spend"] = round(float(amt[card].sum()))
    pin, sig = float(amt[typ == "PIN"].sum()), float(amt[typ == "SIG"].sum())
    out["txn_sig_share_pct"] = _pct(sig, pin + sig)

    # ---- feed facts: MCC coverage and the two unexplained positional fields --
    mcc = df["mcc_code"].astype(str).str.strip()
    out["txn_mcc_coverage_pct"] = _pct(int((mcc[card] != "") .sum() - int((mcc[card] == "nan").sum())), int(card.sum()))
    for col, key in (("merchant_id", "txn_field9_values"), ("card_present", "txn_field11_values")):
        if col in df.columns:
            vc = df[col].astype(str).str.strip().replace({"nan": ""}).value_counts().head(8)
            out[key] = [[v, int(c)] for v, c in vc.items()]
            out[key.replace("_values", "_distinct")] = int(df[col].nunique(dropna=True))

    # ---- accounts ---------------------------------------------------------
    acct = df["primary_account_num"].astype(str)
    out["txn_accounts"] = int(acct.nunique())
    out["txn_per_account"] = round(n / out["txn_accounts"], 1) if out["txn_accounts"] else 0
    out["txn_card_accounts"] = int(acct[card].nunique())
    hashed = acct.str.len() >= 32
    out["txn_account_hashed_pct"] = _pct(int(hashed.sum()), n)

    # ---- ODD join: can transaction accounts be found in the ODD? ------------
    if odd is not None:
        key, ids, info = odd_account_key(odd, acct.unique(), warn)
        if acct_key is not None and acct_key in odd.columns and acct_key != key:
            key, ids = acct_key, norm_accounts(odd[acct_key])   # the run's one choice wins
        out.update(info)
        if key is not None:
            odd_keys = set(ids)
            txn_keys = pd.Index(acct.unique())
            matched = int(txn_keys.isin(odd_keys).sum())
            out["txn_odd_join_key"] = key
            out["txn_odd_accounts_matched"] = matched
            out["txn_odd_match_pct"] = _pct(matched, len(txn_keys))
            if out["txn_odd_match_pct"] < MIN_MATCH_PCT:
                warn(f"only {out['txn_odd_match_pct']}% of transaction accounts match "
                     f"the ODD on '{key}'; account formats probably differ "
                     f"({out['txn_account_hashed_pct']}% of rows carry a hashed account)")
        else:
            warn("ODD has no Acct Number / Acct ID column; join rate not measured")

    # ---- merchants ----------------------------------------------------------
    merch = df["merchant_key"].astype(str) if "merchant_key" in df.columns \
        else df["merchant_name"].astype(str).str.upper()
    n_card = int(card.sum())
    counts = merch[card].value_counts()
    out["txn_top_merchants"] = [[name, int(c), _pct(int(c), n_card)]
                                for name, c in counts.head(TOP_MERCHANTS).items()]
    out["txn_merchants_distinct"] = int(len(counts))
    out["txn_top15_share_pct"] = _pct(int(counts.head(TOP_MERCHANTS).sum()), n_card)
    # how many merchants carry 80% of card transactions
    cum = counts.cumsum() / max(n_card, 1)
    out["txn_merchants_for_80pct"] = int((cum < 0.80).sum() + 1) if n_card else 0
    # ACH / CHK counterparties: who money goes to outside the card
    other = typ.isin(["ACH", "CHK"])
    if other.any():
        oc = ranked(merch[other].value_counts()).head(TOP_MERCHANTS)
        out["txn_top_ach_chk"] = [[name, int(c), round(float(amt[other][merch[other] == name].sum()))]
                                  for name, c in oc.items()]

    # ---- monthly series -------------------------------------------------------
    month = df["transaction_date"].dt.to_period("M")
    grp = df.groupby(month, observed=True)
    series = []
    for per, g in grp:
        t = g["transaction_type"].astype(str).str.upper()
        series.append([str(per), len(g), int(g["primary_account_num"].nunique()),
                       round(float(g["amount"].abs().sum())),
                       int(t.isin(["PIN", "SIG"]).sum())])
    out["txn_monthly"] = series
    return out
