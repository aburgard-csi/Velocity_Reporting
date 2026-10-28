# Ported from v5 02-Scripts/ils/pre_go_live/sections/fees.py at 7ba1e63. Logic unchanged; copied whole.
"""Fees (notebook A14-A16). Population: ALL open accounts, as the notebook
scopes it (personal + business; the fee sees no segments).

The one modeling assumption, derived not assumed: the implied pay ratio =
(12-month actual fees / 12-month items) / the client's stated fee. Estimated
paid items per account = items x ratio; each tier scenario reprices those.
Baseline is the real reported 12-month fee total -- never modeled.

Daily cap (A15) and de minimis (A16) are NOT computable from a PGL extract
(no day-level timing, no balance at transaction); the section says exactly
that instead of inventing a number."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ITEMS = "Rolling 12 Month NSFOD Items"
FEES = "Rolling 12 Month NSFOD Fees"


def load_tiers(config_dir: Path) -> dict:
    return json.loads((Path(config_dir) / "ils_fee_tiers.json").read_text(encoding="utf-8"))


def fee_for_account(n_items: float, tiers: list[dict]) -> float:
    if n_items is None or n_items <= 0:
        return 0.0
    total = 0.0
    for t in tiers:
        lo = t["min_item"]
        hi = t["max_item"] if t["max_item"] is not None else n_items
        if n_items < lo:
            continue
        total += max(0.0, min(n_items, hi) - lo + 1) * t["fee"]
    return total


def compute(df, bases, inputs, warn) -> dict:
    m: dict = {}
    if "open" not in bases.masks:
        warn("fees: no open base; section skipped")
        return m
    fee = inputs.get("fee")
    for col in (ITEMS, FEES):
        if col not in df.columns:
            warn(f"fees: no {col!r} column; section skipped")
            return m
    m["pgl_fee_daily_cap"] = {
        "status": "NOT COMPUTABLE from a PGL extract",
        "why": "no day-by-day item timing per account",
        "needs": "daily transaction-level extract (account, date, NSF/OD item flag)"}
    m["pgl_fee_de_minimis"] = {
        "status": "INSUFFICIENT DATA in a PGL extract",
        "why": "no balance-at-transaction or transaction-size field",
        "needs": "revisit once transaction-level data is available"}
    if fee is None:
        warn("fees: supply the client's current NSF/OD fee to model tier "
             "scenarios (no default; the notebook's $27 was one client's)")
        return m
    fee = float(fee)

    w = df[bases["open"]].copy()
    items = pd.to_numeric(w[ITEMS], errors="coerce").fillna(0)
    fees_actual = pd.to_numeric(w[FEES], errors="coerce").fillna(0)
    total_items = float(items.sum())
    total_fees = float(fees_actual.sum())
    if total_items <= 0:
        warn("fees: no 12-month items in the file; scenarios skipped")
        # Fallback while fee history is blocked: YTD items ARE populated on
        # some extracts (1737: 31k items). At the stated fee that is a GROSS
        # BILLED CEILING -- the Paid columns are empty, so the pay ratio is
        # unknown and this is never revenue. Labeled as exactly that.
        ytd = pd.to_numeric(w.get("YTDODItems"), errors="coerce").fillna(0) \
            if "YTDODItems" in w.columns else None
        if ytd is not None and float(ytd.sum()) > 0:
            m["pgl_fee_ytd_ceiling"] = {
                "ytd_items": round(float(ytd.sum())),
                "accounts_with_items": int((ytd > 0).sum()),
                "stated_fee": fee,
                "gross_ceiling": round(float(ytd.sum()) * fee),
                "note": ("YTD items x stated fee = gross BILLED ceiling, not "
                         "revenue -- pay ratio unknown until the 12-month fee "
                         "history columns populate")}
        return m
    blended = total_fees / total_items
    ratio = blended / fee
    est_paid = items * ratio
    m["pgl_fee_audit"] = {
        "population_open_accounts": int(len(w)),
        "items_12mo": round(total_items),
        "fees_12mo": round(total_fees),
        "blended_per_item": round(blended, 2),
        "stated_fee": fee,
        "implied_pay_ratio_pct": round(100 * ratio, 1),
        "est_paid_items": round(float(est_paid.sum())),
        "reconstructed_fees": round(float(est_paid.sum()) * fee),
        "note": ("baseline is the real reported fee total; the one assumption "
                 "is the pay ratio, derived from the file and applied uniformly")}
    if ratio > 1:
        warn(f"fees: implied pay ratio {ratio:.0%} exceeds 100% -- the stated "
             f"fee looks lower than the blended $/item; confirm the fee")
    m["pgl_fee_baseline"] = round(total_fees)

    spec = inputs.get("tiers")
    designed_for = None
    if not spec:
        loaded = load_tiers(inputs["config_dir"]) if inputs.get("config_dir") else None
        if loaded:
            spec = loaded["tiers"]
            designed_for = loaded.get("designed_for_fee")
    if not spec:
        warn("fees: no tier scenarios supplied or configured; baseline only")
        return m
    if designed_for is not None and fee != designed_for:
        warn(f"fees: the named tiers were designed around a ${designed_for} fee; "
             f"this client's is ${fee:g} -- confirm the bands before the board")
    rows = []
    for name, tiers in spec.items():
        modeled = float(est_paid.apply(lambda n: fee_for_account(n, tiers)).sum())
        delta = modeled - total_fees
        rows.append([name, round(modeled), round(delta),
                     round(100 * delta / total_fees, 1) if total_fees else None,
                     tiers])
    m["pgl_fee_tiers"] = rows
    m["pgl_fee_tiers_columns"] = ["scenario", "modeled_revenue", "delta_vs_baseline",
                                  "delta_pct", "bands"]
    m["pgl_fee_tiers_note"] = "illustrative -- confirm bands before any board use"
    return m
