# Ported from ARS v5 02-Scripts/ars/transaction_intelligence/interchange.py at a491b5c (James Gilmore); logic unchanged.
"""Interchange: the PIN / signature routing mix as the transaction file shows it.

Signature transactions earn materially more interchange than PIN, so the
routing mix is a lever that needs no new accounts and no new spend. This
block reads the mix straight off the card rows (transaction_type PIN or
SIG), per month, per account, per merchant and per group. It does NOT price
it: the ARS run's value section owns priced revenue (ICRate is per client
and 1100 has none), so nothing here contradicts it. Legacy interchange/02-09
priced on hardcoded Durbin rates; the mix is the part that is observed.

Keys: ic_* on the personal card base. The whole block declines when the
file carries one rail (1615 is SIG-only): routing is then an artefact of
the extract, not behaviour.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .financial_services import _pct
from .lens import Lenses
from .merchant_profiles import AGE_BANDS
from ti.compat import str_values

SIG_GOAL = 60.0                      # legacy 04: the share of card $ on signature to aim for
SIG_RISK = 40.0                      # legacy 09: a product below this looks PIN-defaulted
PIN_HEAVY_SIG_MAX = 20.0             # legacy 06: 80%+ of an account's card $ on PIN
SHIFT_PP = 1.0                       # legacy 03: first-3 vs last-3 month move that counts
MIN_GROUP_ACCOUNTS = 10              # legacy 07/09: smallest group shown
TOP_MERCHANTS = 10
TOP_PRODUCTS = 10
MIX_BANDS = [(0, 20, "0-20%"), (20, 40, "20-40%"), (40, 60, "40-60%"),
             (60, 80, "60-80%"), (80, 101, "80-100%")]
GROUP_COLUMNS = ["group", "accounts", "sig_pct", "dollars"]


def _mix(frame: pd.DataFrame) -> list:
    """[accounts, sig share of dollars, dollars] for a slice of card rows."""
    pin = float(frame.loc[~frame["sig"], "amount"].sum())
    sig = float(frame.loc[frame["sig"], "amount"].sum())
    return [int(frame["acct"].nunique()), _pct(sig, pin + sig), round(pin + sig)]


def _by_attr(frame: pd.DataFrame, values: pd.Series, bands: list | None) -> list:
    """SIG share by an ODD attribute: banded when `bands` is given, else by
    value. Groups under MIN_GROUP_ACCOUNTS are dropped, not shown small."""
    v = values.reindex(frame["acct"].to_numpy())
    rows = []
    if bands:
        num = pd.to_numeric(v, errors="coerce").to_numpy()
        for lo, hi, label in bands:
            sub = frame[(num >= lo) & (num < hi)]
            if sub["acct"].nunique() >= MIN_GROUP_ACCOUNTS:
                rows.append([label, *_mix(sub)])
        return rows
    lab = v.astype(str).str.strip().to_numpy()
    for value in pd.unique(lab):
        if value in ("", "nan", "None"):
            continue
        sub = frame[lab == value]
        if sub["acct"].nunique() >= MIN_GROUP_ACCOUNTS:
            rows.append([value[:30], *_mix(sub)])
    rows.sort(key=lambda r: -r[3])
    return rows


def compute(df: pd.DataFrame, lenses: Lenses | None, anchor_end: pd.Timestamp, warn,
            account_filter: pd.Index | None = None, key_prefix: str = "ic_",
            base_label: str = "all accounts") -> dict:
    out: dict = {}
    K = key_prefix
    typ = str_values(df["transaction_type"], lambda v: v.str.upper())
    is_card = typ.isin(["PIN", "SIG"]).to_numpy()
    acct_all = df["primary_account_num"].astype(str)
    in_base = acct_all.isin(account_filter).to_numpy() if account_filter is not None \
        else np.ones(len(df), dtype=bool)
    card = df[is_card & in_base]
    if card.empty:
        warn(f"interchange: no card rows for {base_label}; section skipped")
        return out
    out[K + "base_label"] = base_label
    rails = sorted(typ[is_card & in_base].unique())
    out[K + "rails"] = rails
    out[K + "routing_available"] = len(rails) == 2
    frame = pd.DataFrame({
        "acct": card["primary_account_num"].astype(str).to_numpy(),
        "sig": (typ[is_card & in_base] == "SIG").to_numpy(),
        "amount": card["amount"].abs().to_numpy(),
        "key": str_values(card["merchant_key"]).to_numpy(),
        "month": card["transaction_date"].dt.to_period("M").astype(str).to_numpy()})
    n_months = max(int(frame["month"].nunique()), 1)
    accounts, sig_pct, spend = _mix(frame)
    out[K + "card_accounts"] = accounts
    out[K + "card_spend"] = spend
    if not out[K + "routing_available"]:
        warn(f"interchange: the file carries one card rail ({rails[0]}); the "
             f"PIN/SIG mix is an artefact of the extract and is not reported")
        return out

    # ---- 1. the mix and its tickets ------------------------------------------------
    pin_n, sig_n = int((~frame["sig"]).sum()), int(frame["sig"].sum())
    out[K + "sig_share_pct"] = sig_pct
    out[K + "sig_share_of_swipes_pct"] = _pct(sig_n, pin_n + sig_n)
    out[K + "pin_ticket"] = round(float(frame.loc[~frame["sig"], "amount"].mean()), 2)
    out[K + "sig_ticket"] = round(float(frame.loc[frame["sig"], "amount"].mean()), 2)
    out[K + "sig_vs_goal_pp"] = round(sig_pct - SIG_GOAL, 1)

    # ---- 2. month by month ---------------------------------------------------------
    monthly = []
    for m, g in frame.groupby("month", sort=True):
        pin = float(g.loc[~g["sig"], "amount"].sum())
        sig = float(g.loc[g["sig"], "amount"].sum())
        monthly.append([m, round(pin), round(sig), _pct(sig, pin + sig), int(g["acct"].nunique())])
    out[K + "monthly"] = monthly
    out[K + "monthly_columns"] = ["month", "pin_dollars", "sig_dollars", "sig_pct", "accounts"]
    if len(monthly) >= 3:
        ratios = [r[3] for r in monthly]
        shift = float(np.mean(ratios[-3:]) - np.mean(ratios[:3]))
        out[K + "sig_shift_pp"] = round(shift, 1)
        out[K + "sig_direction"] = ("improving" if shift > SHIFT_PP
                                    else "declining" if shift < -SHIFT_PP else "stable")

    # ---- 3. accounts by their own mix; PIN-heavy -------------------------------------
    per = frame.groupby(["acct", "sig"])["amount"].sum().unstack(fill_value=0.0)
    per = per.reindex(columns=[False, True], fill_value=0.0)
    per.columns = ["pin", "sig"]
    per["total"] = per["pin"] + per["sig"]
    per = per[per["total"] > 0]
    per["sig_pct"] = 100 * per["sig"] / per["total"]
    mix = []
    for lo, hi, label in MIX_BANDS:
        sub = per[(per["sig_pct"] >= lo) & (per["sig_pct"] < hi)]
        mix.append([label, len(sub), _pct(len(sub), len(per)), round(float(sub["total"].sum()))])
    out[K + "account_mix"] = mix
    out[K + "account_mix_columns"] = ["sig_share_band", "accounts", "pct", "dollars"]
    heavy = per[per["sig_pct"] <= PIN_HEAVY_SIG_MAX]
    out[K + "pin_heavy_n"] = len(heavy)
    out[K + "pin_heavy_pct"] = _pct(len(heavy), len(per))
    out[K + "pin_heavy_spend"] = round(float(heavy["total"].sum()))
    out[K + "pin_heavy_spend_pct"] = _pct(float(heavy["total"].sum()), spend)
    out[K + "pin_heavy_spend_per_acct_mo"] = (
        round(float(heavy["total"].mean()) / n_months) if len(heavy) else 0)

    # ---- 4. by merchant: observed routing, not the legacy imputation ----------------
    by_m = frame.groupby("key")
    rows = []
    for k, g in by_m:
        pin = float(g.loc[~g["sig"], "amount"].sum())
        sig = float(g.loc[g["sig"], "amount"].sum())
        rows.append([str(k), len(g), round(pin), round(sig), _pct(sig, pin + sig)])
    rows.sort(key=lambda r: -(r[2] + r[3]))
    out[K + "by_merchant"] = rows[:TOP_MERCHANTS]
    out[K + "by_merchant_columns"] = ["merchant", "txns", "pin_dollars", "sig_dollars", "sig_pct"]

    # ---- 5. by group: lens, holder age, product ---------------------------------------
    if lenses is None:
        warn("interchange: no lenses; by-lens, age and product cuts skipped")
        return out
    by_lens = []
    for ln in lenses.names():
        sub = frame[frame["acct"].isin(lenses.ids(ln).astype(str))]
        if sub["acct"].nunique() >= MIN_GROUP_ACCOUNTS:
            by_lens.append([ln, lenses.label(ln), *_mix(sub)])
    out[K + "by_lens"] = by_lens
    out[K + "by_lens_columns"] = ["lens", "label", "accounts", "sig_pct", "dollars"]
    attrs = lenses.attrs
    if "Account Holder Age" in attrs.columns:
        out[K + "by_age"] = _by_attr(frame, attrs["Account Holder Age"], AGE_BANDS)
        out[K + "by_age_columns"] = GROUP_COLUMNS
    else:
        warn("interchange: ODD has no Account Holder Age; by_age skipped")
    prod_col = next((c for c in ("Prod Desc", "Prod Code") if c in attrs.columns), None)
    if prod_col:
        products = _by_attr(frame, attrs[prod_col], None)[:TOP_PRODUCTS]
        out[K + "by_product"] = products
        out[K + "by_product_columns"] = GROUP_COLUMNS
        out[K + "pin_default_products"] = [r for r in products if r[2] < SIG_RISK][:5]
    else:
        warn("interchange: ODD has no Prod Desc / Prod Code; by_product skipped")
    return out
