# Ported from ARS v5 02-Scripts/ars/transaction_intelligence/card_behavior.py at a491b5c (James Gilmore); logic unchanged.
"""Card behavior: how the card is used -- tickets, intensity, timing,
recurring charges, and the responder-vs-control cut the campaign work
promised (the "campaign TXN tail").

Everything here is the card rail. The type token and the HH:MM timestamp
live inside the raw description (XX1234 PURCHASE-RECUR 08/01 06:51 ...);
each block declines with a warn when its token is absent from the file.

SPEC: SPEC-card_behavior.md. Keys: beh_* (personal base).
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .financial_services import _pct
from .lens import Lenses
from ti.compat import str_values

TICKET_BANDS = [(0, 5, "< $5"), (5, 15, "$5-15"), (15, 30, "$15-30"), (30, 60, "$30-60"),
                (60, 120, "$60-120"), (120, 300, "$120-300"), (300, 1e18, "$300+")]
INTENSITY_BANDS = [(0, 1, "< 1"), (1, 5, "1-5"), (5, 10, "5-10"), (10, 20, "10-20"),
                   (20, 40, "20-40"), (40, 1e18, "40+")]
HOUR_BLOCKS = [(0, 6, "0-6"), (6, 9, "6-9"), (9, 12, "9-12"), (12, 15, "12-15"),
               (15, 18, "15-18"), (18, 21, "18-21"), (21, 24, "21-24")]
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
TOP_RECURRING = 12
TOP_ROUTED = 12

_TOKEN = re.compile(r"^\s*XX\d{3,6}\s+([A-Z]+(?:-[A-Z]+)?)\s+\d{2}/\d{2}\s+(\d{2}):\d{2}\s", re.I)


def _bands(values: pd.Series, bands) -> list[list]:
    rows = []
    n = len(values)
    for lo, hi, label in bands:
        c = int(((values >= lo) & (values < hi)).sum())
        rows.append([label, c, _pct(c, n)])
    return rows


def compute(df: pd.DataFrame, lenses: Lenses | None, anchor_end: pd.Timestamp, warn,
            account_filter: pd.Index | None = None, key_prefix: str = "beh_",
            base_label: str = "all accounts") -> dict:
    out: dict = {}
    K = key_prefix
    typ = str_values(df["transaction_type"], lambda v: v.str.upper())
    is_card = typ.isin(["PIN", "SIG"]).to_numpy()
    if not is_card.any():
        warn("card_behavior: no card rows (PIN/SIG); section skipped")
        return out
    acct_all = df["primary_account_num"].astype(str)
    in_base = acct_all.isin(account_filter).to_numpy() if account_filter is not None \
        else np.ones(len(df), dtype=bool)
    card = df[is_card & in_base]
    if card.empty:
        warn(f"card_behavior: no card rows for {base_label}; section skipped")
        return out
    out[K + "base_label"] = base_label
    amt = card["amount"].abs()
    acct = card["primary_account_num"].astype(str)
    month = card["transaction_date"].dt.to_period("M")
    n_months = max(int(month.nunique()), 1)

    # ---- 1. ticket distribution ------------------------------------------------
    out[K + "ticket_bands"] = _bands(amt, TICKET_BANDS)
    out[K + "ticket_mean"] = round(float(amt.mean()), 2)
    out[K + "ticket_median"] = round(float(amt.median()), 2)

    # ---- 2. intensity: card txns per active account per month -------------------
    per_acct_month = card.groupby([acct, month], observed=True).size()
    per_acct = per_acct_month.groupby(level=0).mean()
    out[K + "txns_per_active_acct_mo"] = round(float(per_acct.mean()), 1)
    out[K + "intensity_bands"] = _bands(per_acct, INTENSITY_BANDS)
    ma = card.assign(_a=acct).groupby(month, observed=True)["_a"].nunique()
    out[K + "active_accounts_monthly"] = [[str(m), int(v)] for m, v in ma.items()]
    md = amt.groupby(month, observed=True).sum()
    out[K + "card_dollars_monthly"] = [[str(m), round(float(v))]
                                       for m, v in md.items()]

    # ---- 3. when: weekday x hour-block heat -------------------------------------
    tok = card["merchant_name"].astype(str).str.extract(_TOKEN)
    hours = pd.to_numeric(tok[1], errors="coerce")
    if hours.notna().mean() >= 0.5:
        dow = card["transaction_date"].dt.dayofweek
        grid = []
        for d in range(7):
            row = []
            for lo, hi, _label in HOUR_BLOCKS:
                row.append(int(((dow == d) & (hours >= lo) & (hours < hi)).sum()))
            grid.append(row)
        out[K + "heat_grid"] = grid
        out[K + "heat_rows"] = WEEKDAYS
        out[K + "heat_cols"] = [label for _, _, label in HOUR_BLOCKS]
        flat = [(WEEKDAYS[d], HOUR_BLOCKS[b][2], grid[d][b]) for d in range(7)
                for b in range(len(HOUR_BLOCKS))]
        peak = max(flat, key=lambda r: r[2])
        out[K + "peak"] = [peak[0], peak[1], peak[2]]
    else:
        warn("card_behavior: no parseable HH:MM in descriptions; timing grid skipped")

    # ---- 4. recurring vs one-off -------------------------------------------------
    token = tok[0].astype(str).str.upper()
    if token.str.contains("RECUR", na=False).any():
        rec = token.str.contains("RECUR", na=False)
        out[K + "recurring_txn_pct"] = _pct(int(rec.sum()), len(card))
        out[K + "recurring_dollar_pct"] = _pct(float(amt[rec].sum()), float(amt.sum()))
        rec_accts = acct[rec].nunique()
        out[K + "accounts_with_recurring"] = int(rec_accts)
        out[K + "accounts_with_recurring_pct"] = _pct(int(rec_accts), int(acct.nunique()))
        top = pd.DataFrame({"key": str_values(card["merchant_key"])[rec], "amount": amt[rec],
                            "acct": acct[rec]}).groupby("key", observed=True) \
            .agg(accounts=("acct", "nunique"), txns=("amount", "size"), dollars=("amount", "sum")) \
            .sort_index().sort_values("accounts", ascending=False, kind="mergesort")
        out[K + "top_recurring"] = [[str(k), int(r.accounts), int(r.txns), round(float(r.dollars))]
                                    for k, r in top.head(TOP_RECURRING).iterrows()]
    else:
        warn("card_behavior: no RECUR token in descriptions; recurring split skipped")

    # ---- 5. responders vs control (the campaign TXN tail) -------------------------
    if lenses is not None:
        all_card = df[is_card]
        a_amt = all_card["amount"].abs()
        a_acct = all_card["primary_account_num"].astype(str)
        a_tok = all_card["merchant_name"].astype(str).str.extract(_TOKEN)[0].astype(str).str.upper()
        a_rec = a_tok.str.contains("RECUR", na=False)
        by_lens = []
        for ln in lenses.names():
            mask = a_acct.isin(lenses.ids(ln))
            n = int(a_acct[mask].nunique())
            if not n:
                continue
            vals = a_amt[mask]
            # all-blank amounts leave nothing to median: report None, and
            # never let numpy warn 'Mean of empty slice' on the all-NaN path
            med = round(float(vals.median()), 2) if vals.notna().any() else None
            by_lens.append([ln, lenses.label(ln), n, med,
                            round(float(mask.sum()) / n / n_months, 1),
                            _pct(int((mask & a_rec).sum()), int(mask.sum()))])
        out[K + "by_lens"] = by_lens
        out[K + "by_lens_columns"] = ["lens", "label", "card_accounts", "median_ticket",
                                      "txns_per_acct_per_mo", "recurring_txn_pct"]
        by = {r[0]: r for r in by_lens}
        r_, c_ = by.get("responders"), by.get("mailed_nonresp")
        if r_ and c_ and r_[3] is not None and c_[3] is not None:
            out[K + "responder_ticket_gap"] = round(r_[3] - c_[3], 2)
            out[K + "responder_intensity_gap"] = round(r_[4] - c_[4], 1)
    else:
        warn("card_behavior: no lenses; responder-vs-control skipped")

    # ---- 6. routing by merchant (only when both rails exist) ----------------------
    rails = set(typ[is_card & in_base].unique())
    if {"PIN", "SIG"} <= rails:
        t = typ[is_card & in_base]
        rt = pd.DataFrame({"key": str_values(card["merchant_key"]), "t": t.to_numpy(),
                           "amount": amt}).groupby("key", observed=True)
        rows = []
        for k, r in rt:
            n = len(r)
            pin = int((r["t"] == "PIN").sum())
            rows.append([str(k), n, _pct(pin, n), round(float(r["amount"].sum()))])
        rows.sort(key=lambda x: -x[3])
        out[K + "routing_by_merchant"] = rows[:TOP_ROUTED]
        out[K + "routing_columns"] = ["merchant", "txns", "pin_pct", "dollars"]
        out[K + "pin_share_pct"] = _pct(int((t == "PIN").sum()), len(t))
    else:
        warn("card_behavior: single card rail in the file; PIN/SIG-by-merchant skipped")
    return out
