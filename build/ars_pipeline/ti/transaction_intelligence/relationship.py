# Ported from ARS v5 02-Scripts/ars/transaction_intelligence/relationship.py at a491b5c (James Gilmore); logic unchanged.
"""Relationship: engagement breadth per account.

The legacy section counted products per account; a one-row-per-account ODD
makes that moot. The honest replacement is CHANNEL breadth from the
transaction file -- card, ACH, check, P2P -- plus recurring billers, which
anchor a relationship harder than any single purchase. The primary-like
block is the activity component the balance/PFI story waits on.

SPEC: SPEC-relationship.md. Keys: rel_* (personal base).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .financial_services import _pct
from .lens import Lenses
from ti.compat import str_values

CHANNELS = ["card", "ACH", "CHK", "P2P"]
BILLER_BANDS = [(0, 1, "0"), (1, 2, "1"), (2, 4, "2-3"), (4, 7, "4-6"), (7, 1e18, "7+")]
PRIMARY_MIN_CHANNELS = 2
PRIMARY_MIN_TXNS_MO = 10


def _channel(df: pd.DataFrame, fin_rows: pd.DataFrame | None) -> pd.Series:
    typ = str_values(df["transaction_type"], lambda v: v.str.upper())
    ch = pd.Series("other", index=df.index, dtype=object)
    ch[typ.isin(["PIN", "SIG"])] = "card"
    ch[typ == "ACH"] = "ACH"
    ch[typ == "CHK"] = "CHK"
    if fin_rows is not None and "category" in fin_rows.columns:
        p2p = (fin_rows["category"].astype(str) == "P2P Transfers") & ~fin_rows["is_card"]
        ch[p2p.to_numpy()] = "P2P"
    return ch


def _channel_pairs(used: pd.DataFrame, single_counts: pd.Series, K: str) -> dict:
    """Legacy relationship/05 and 09 on channels instead of products: of the
    accounts on channel A, the share also on channel B; and for the accounts
    on A alone, the channel their multi-channel peers most often add."""
    holders = {c: set(used.loc[used["channel"] == c, "acct"]) for c in CHANNELS}
    present = [c for c in CHANNELS if holders[c]]
    if len(present) < 2:
        return {K + "channel_pairs": None, K + "next_channel": []}
    cells = [[None if a == b else _pct(len(holders[a] & holders[b]), len(holders[a]))
              for b in present] for a in present]
    nxt = []
    for a in present:
        multi = {o: len(holders[a] & holders[o]) for o in present if o != a}
        best = max(multi, key=multi.get)
        nxt.append([a, int(single_counts.get(a, 0)), best,
                    _pct(multi[best], len(holders[a])) if multi[best] else 0.0])
    return {K + "channel_pairs": {"rows": present, "cols": present, "cells": cells},
            K + "next_channel": nxt,
            K + "next_channel_columns": ["channel", "single_channel_accounts",
                                         "next_channel", "peers_also_on_it_pct"]}


def compute(df: pd.DataFrame, lenses: Lenses | None, fin_rows: pd.DataFrame | None,
            anchor_end: pd.Timestamp, warn, account_filter: pd.Index | None = None,
            key_prefix: str = "rel_", base_label: str = "all accounts") -> dict:
    out: dict = {}
    K = key_prefix
    if df.empty:
        warn("relationship: empty frame; section skipped")
        return out
    channel_all = _channel(df, fin_rows)
    acct_all = df["primary_account_num"].astype(str)
    in_base = acct_all.isin(account_filter).to_numpy() if account_filter is not None \
        else np.ones(len(df), dtype=bool)
    sub = df[in_base]
    if sub.empty:
        warn(f"relationship: no rows for {base_label}; section skipped")
        return out
    out[K + "base_label"] = base_label
    acct = acct_all[in_base]
    channel = channel_all[in_base]
    month = sub["transaction_date"].dt.to_period("M")
    n_months = max(int(month.nunique()), 1)
    frame = pd.DataFrame({"acct": acct.to_numpy(), "channel": channel.to_numpy(),
                          "amount": sub["amount"].abs().to_numpy(),
                          "key": str_values(sub["merchant_key"]).to_numpy()})

    # ---- 1. channel breadth ------------------------------------------------------
    used = frame[frame["channel"].isin(CHANNELS)]
    breadth = used.groupby("acct")["channel"].nunique()
    total = int(frame["acct"].nunique())
    out[K + "accounts_total"] = total
    # A file that carries one rail cannot measure breadth: every account
    # is single-channel by construction, not by behaviour (1776, #245).
    rails_in_file = int(channel_all[channel_all.isin(CHANNELS)].nunique())
    out[K + "single_rail"] = rails_in_file <= 1
    if out[K + "single_rail"]:
        warn(f"relationship: the file carries one rail; channel breadth and "
             f"single-channel share are not measurable and are not reported")
        out[K + "breadth"] = []
        out[K + "breadth_mean"] = None
    else:
        dist = breadth.value_counts()
        out[K + "breadth"] = [[int(b), int(dist.get(b, 0)), _pct(int(dist.get(b, 0)), total)]
                              for b in range(1, len(CHANNELS) + 1)]
        out[K + "breadth_mean"] = round(float(breadth.mean()), 2) if len(breadth) else 0.0
    per_channel = used.groupby("channel")["acct"].nunique()
    out[K + "by_channel"] = [[c, int(per_channel.get(c, 0)), _pct(int(per_channel.get(c, 0)), total)]
                             for c in CHANNELS]

    # ---- 2. single-channel accounts ----------------------------------------------
    if out[K + "single_rail"]:
        out[K + "single_channel"] = None
        out[K + "single_channel_pct"] = None
        out[K + "single_channel_mix"] = []
        out[K + "channel_pairs"] = None
        out[K + "next_channel"] = []
    else:
        single_ids = breadth.index[breadth == 1]
        out[K + "single_channel"] = len(single_ids)
        out[K + "single_channel_pct"] = _pct(len(single_ids), total)
        only = used[used["acct"].isin(single_ids)].groupby("acct")["channel"].first()
        oc = only.value_counts()
        out[K + "single_channel_mix"] = [[c, int(oc.get(c, 0))] for c in CHANNELS if oc.get(c, 0)]
        out.update(_channel_pairs(used, oc, K))

    # ---- 3. recurring billers per account ------------------------------------------
    # ACH/CHK counterparties seen in 3+ distinct months + RECUR card merchants.
    tf_mask = channel.isin(["ACH", "CHK", "P2P"]).to_numpy()
    tf = pd.DataFrame({"acct": acct.to_numpy()[tf_mask], "key": frame["key"].to_numpy()[tf_mask],
                       "m": month.to_numpy()[tf_mask]})
    months_per = tf.groupby(["acct", "key"], observed=True)["m"].nunique()
    billers = months_per[months_per >= 3].groupby(level=0).size()
    rec_tok = sub["merchant_name"].astype(str).str.contains("PURCHASE-RECUR", case=False, na=False)
    card_rec = pd.DataFrame({"acct": acct[rec_tok].to_numpy(),
                             "key": frame["key"].to_numpy()[rec_tok.to_numpy()]})
    card_billers = card_rec.groupby("acct")["key"].nunique() if len(card_rec) else pd.Series(dtype=int)
    all_billers = billers.add(card_billers, fill_value=0).astype(int) if len(card_billers) else billers
    per_acct_billers = all_billers.reindex(pd.Index(frame["acct"].unique())).fillna(0)
    rows = []
    for lo, hi, label in BILLER_BANDS:
        c = int(((per_acct_billers >= lo) & (per_acct_billers < hi)).sum())
        rows.append([label, c, _pct(c, total)])
    out[K + "billers_bands"] = rows
    out[K + "billers_mean"] = round(float(per_acct_billers.mean()), 1)

    # ---- 4. depth x breadth ---------------------------------------------------------
    txns_per = frame.groupby("acct").size()
    dollars_per = frame.groupby("acct")["amount"].sum()
    depth = []
    for b in (range(1, len(CHANNELS) + 1) if not out[K + "single_rail"] else ()):
        ids = breadth.index[breadth == b]
        if not len(ids):
            continue
        depth.append([int(b), len(ids), round(float(txns_per.loc[ids].mean()) / n_months, 1),
                      round(float(dollars_per.loc[ids].mean()) / n_months)])
    out[K + "depth_by_breadth"] = depth
    out[K + "depth_by_breadth_columns"] = ["channels", "accounts", "txns_per_mo", "dollars_per_mo"]

    # ---- 5. by lens ------------------------------------------------------------------
    if lenses is not None:
        a_frame = pd.DataFrame({"acct": acct_all.to_numpy(), "channel": channel_all.to_numpy()})
        a_used = a_frame[a_frame["channel"].isin(CHANNELS)]
        a_breadth = a_used.groupby("acct")["channel"].nunique()
        by_lens = []
        for ln in lenses.names():
            ids = pd.Index(a_breadth.index).intersection(lenses.ids(ln))
            if not len(ids):
                continue
            b = a_breadth.loc[ids]
            by_lens.append([ln, lenses.label(ln), len(ids), round(float(b.mean()), 2),
                            _pct(int((b == 1).sum()), len(ids))])
        out[K + "by_lens"] = by_lens
        out[K + "by_lens_columns"] = ["lens", "label", "accounts", "mean_breadth", "single_channel_pct"]
        by = {r[0]: r for r in by_lens}
        if "responders" in by and "mailed_nonresp" in by:
            out[K + "responder_breadth_gap"] = round(by["responders"][3] - by["mailed_nonresp"][3], 2)
    else:
        warn("relationship: no lenses; by-lens table skipped")

    # ---- 6. primary-like activity -----------------------------------------------------
    active_enough = txns_per / n_months >= PRIMARY_MIN_TXNS_MO
    broad_enough = breadth.reindex(txns_per.index).fillna(0) >= PRIMARY_MIN_CHANNELS
    primary = active_enough & broad_enough
    out[K + "primary_like_n"] = int(primary.sum())
    out[K + "primary_like_pct"] = _pct(int(primary.sum()), total)
    out[K + "primary_like_note"] = (f"{PRIMARY_MIN_CHANNELS}+ channels and >= "
                                    f"{PRIMARY_MIN_TXNS_MO} txns/mo; the activity component "
                                    f"of a PFI read (no credits in the feed, so no "
                                    f"direct-deposit component)")
    return out
