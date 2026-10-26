# Ported from ARS v5 02-Scripts/ars/transaction_intelligence/overlay.py at a491b5c (James Gilmore); logic unchanged.
"""Deposit-flight x competitor overlay: WHERE the declining deposits go.

The ODD sees deposits declining (balance.py's flight mask -- one definition,
imported, never re-derived); the transaction file sees the named
institutions and product categories those same accounts pay. This is the
first analysis that only exists because both live in one engine.

Inputs are the other sections' own outputs: the flight mask over the lens
attributes, competition's per-account institution rows, financial_services'
addressable rows. Nothing is re-classified here, so this section can never
disagree with the sections it joins.

Keys: ovl_* . One CSV action list. Declines with a warn when any input is
missing (no lenses, no balance columns, no competitor/finserv rows).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..monthly_analysis.balance import FLIGHT_RISK_THRESHOLD, flight_mask
from .financial_services import _pct
from .lens import Lenses

TOP_DESTINATIONS = 10


def compute(lenses: Lenses | None, competitor_rows: list | None,
            addressable_rows: list | None, lists_dir: Path | None, warn) -> tuple[dict, dict]:
    out: dict = {}
    outputs: dict = {}
    if lenses is None:
        warn("overlay: no lenses (run the ARS analysis first); "
             "deposit-flight overlay skipped")
        return out, outputs
    attrs = lenses.attrs
    if "Curr Bal" not in attrs.columns or "Avg Bal" not in attrs.columns:
        warn("overlay: ODD lacks Curr Bal / Avg Bal; deposit-flight overlay skipped")
        return out, outputs

    current = pd.to_numeric(attrs["Curr Bal"], errors="coerce").fillna(0)
    average = pd.to_numeric(attrs["Avg Bal"], errors="coerce")
    flight = flight_mask(current, average)
    flight_ids = pd.Index(attrs.index[flight])
    out["ovl_flight_threshold"] = FLIGHT_RISK_THRESHOLD
    # The transaction run never sees the deposits file, so this overlay is
    # still on the balance proxy. Said beside the count, not assumed.
    out["ovl_flight_basis"] = "balance proxy"
    out["ovl_flight_n"] = len(flight_ids)
    out["ovl_flight_deposits"] = round(float(current[flight].sum()))
    decline = (current - average.fillna(0))[flight]
    out["ovl_flight_decline"] = round(float(decline.abs().sum()))
    if not len(flight_ids):
        warn("overlay: no flight-risk accounts at the threshold; overlay empty")
        return out, outputs

    comp = pd.DataFrame(competitor_rows or [], columns=["acct", "institution", "dollars"])
    addr = pd.DataFrame(addressable_rows or [], columns=["acct", "category", "dollars"])
    if comp.empty and addr.empty:
        warn("overlay: no competitor or financial-services rows to join; "
             "run those sections first")
        return out, outputs
    comp["acct"] = comp["acct"].astype(str)
    addr["acct"] = addr["acct"].astype(str)

    # ---- flight x named competitor ----------------------------------------
    # per-account deposit decline (Curr vs own Avg), for the destination
    # aggregations and the list sort (triage 2026-08-21: the outreach story
    # is "members paying X are down $Y here", not just an account count)
    acct_decline = (average.fillna(0) - current).clip(lower=0)

    fc = comp[comp["acct"].isin(flight_ids)]
    fc_ids = pd.Index(fc["acct"].unique())
    out["ovl_flight_with_competitor"] = len(fc_ids)
    out["ovl_flight_with_competitor_pct"] = _pct(len(fc_ids), len(flight_ids))

    def _decline_for(group: pd.DataFrame) -> float:
        return float(acct_decline.reindex(group["acct"].unique()).fillna(0).sum())

    inst = fc.groupby("institution", observed=True).agg(
        accounts=("acct", "nunique"), dollars=("dollars", "sum")) \
        .sort_values("accounts", ascending=False)
    inst_decline = {i: _decline_for(g) for i, g in fc.groupby("institution", observed=True)}
    out["ovl_destinations"] = [[str(i), int(r.accounts), round(float(r.dollars)),
                                round(inst_decline.get(i, 0.0))]
                               for i, r in inst.head(TOP_DESTINATIONS).iterrows()]
    out["ovl_destinations_columns"] = ["institution", "flight_accounts",
                                       "external_dollars", "deposit_decline"]

    # ---- flight x addressable leakage -------------------------------------
    fa = addr[addr["acct"].isin(flight_ids)]
    fa_ids = pd.Index(fa["acct"].unique())
    out["ovl_flight_leaking"] = len(fa_ids)
    out["ovl_flight_leaking_pct"] = _pct(len(fa_ids), len(flight_ids))
    cats = fa.groupby("category", observed=True).agg(
        accounts=("acct", "nunique"), dollars=("dollars", "sum")) \
        .sort_values("dollars", ascending=False)
    cat_decline = {c: _decline_for(g) for c, g in fa.groupby("category", observed=True)}
    out["ovl_categories"] = [[str(c), int(r.accounts), round(float(r.dollars)),
                              round(cat_decline.get(c, 0.0))]
                             for c, r in cats.head(TOP_DESTINATIONS).iterrows()]
    out["ovl_categories_columns"] = ["category", "flight_accounts",
                                     "external_dollars", "deposit_decline"]

    # ---- the punchline: declining deposits with a named destination -------
    named_ids = fc_ids.union(fa_ids)
    named = flight_ids.intersection(named_ids)
    out["ovl_named_destination_n"] = len(named)
    out["ovl_named_destination_pct"] = _pct(len(named), len(flight_ids))
    out["ovl_named_destination_deposits"] = round(float(current.loc[named].sum()))
    out["ovl_named_destination_decline"] = round(
        float((current - average.fillna(0)).loc[named].abs().sum()))
    out["ovl_note"] = ("flight risk = balance.py's definition (Curr Bal >= "
                       f"${FLIGHT_RISK_THRESHOLD:,} and below its average), joined to "
                       "competition's and financial_services' own account rows -- "
                       "no re-derivation")

    # ---- the action list ----------------------------------------------------
    if lists_dir is not None and len(named):
        lists_dir.mkdir(parents=True, exist_ok=True)
        insts = fc.groupby("acct")["institution"] \
            .agg(lambda s_: "; ".join(sorted(set(s_))))
        catss = fa.groupby("acct")["category"] \
            .agg(lambda s_: "; ".join(sorted(set(s_))))
        ext = pd.concat([fc.groupby("acct")["dollars"].sum(),
                         fa.groupby("acct")["dollars"].sum()], axis=1) \
            .fillna(0).sum(axis=1)
        table = pd.DataFrame({
            "curr_bal": current.loc[named],
            "balance_decline": (current - average.fillna(0)).loc[named].round(0),
            "institutions": insts.reindex(named),
            "categories": catss.reindex(named),
            "external_dollars": ext.reindex(named).round(0),
        }).join(attrs[[c for c in ("Branch", "Prod Desc", "Response Grouping",
                                   "tenure_years") if c in attrs.columns]], how="left") \
            .sort_values("balance_decline", ascending=True)  # biggest decline first (most negative)
        path = lists_dir / "flight_risk_destinations.csv"
        table.rename_axis("acct").to_csv(path)
        outputs["overlay_list"] = str(path)
    return out, outputs
