# Ported from v5 02-Scripts/ils/pre_go_live/sections/summary.py at 7ba1e63. Logic unchanged; copied whole.
"""The summary: what a reader needs before any table -- the eligibility
funnel, the limit exposure in dollars, who is active at $0, and computed
headline sentences. Runs on df + bases alone so it never depends on another
section's output."""

from __future__ import annotations

import pandas as pd

from ._cut import DEP_CT, ILS_LIMIT, INIT_LIMIT


def _pct(n, d) -> float:
    return round(100 * n / d, 1) if d else 0.0


def compute(df, bases, inputs, warn) -> dict:
    m: dict = {}
    n_rows = len(df)
    masks = bases.masks
    funnel = [["rows", n_rows, "rows in the extract"]]   # deleted rows already excluded
    for key, label in (("open", "open accounts"), ("personal", "open personal"),
                       ("eligible", "eligible (confirmed OD codes)")):
        if key in masks:
            base = masks[key] if key != "personal" else masks["open"] & masks["personal"]
            funnel.append([key, int(base.sum()), label])
    prop = pd.to_numeric(df.get(ILS_LIMIT), errors="coerce") if ILS_LIMIT in df.columns else None
    if prop is not None and "eligible" in masks:
        has_prop = (prop > 0) & masks["eligible"]
        funnel.append(["proposed_limit", int(has_prop.sum()), "eligible with a proposed limit > $0"])
    m["pgl_funnel"] = funnel
    m["pgl_funnel_columns"] = ["stage", "accounts", "label"]

    # ---- exposure: the dollars, on ONE base (eligible) ---------------------
    if prop is not None and "eligible" in masks and INIT_LIMIT in df.columns:
        e = df[masks["eligible"]]
        pe = pd.to_numeric(e[ILS_LIMIT], errors="coerce")
        ce = pd.to_numeric(e[INIT_LIMIT], errors="coerce")
        known = pe.notna()
        if known.any():
            cur, new = float(ce[known].fillna(0).sum()), float(pe[known].sum())
            m["pgl_exposure"] = {
                "base": "eligible accounts with a known proposed limit",
                "accounts": int(known.sum()),
                "current_total": round(cur), "proposed_total": round(new),
                "delta": round(new - cur),
                "delta_pct": _pct(new - cur, cur) if cur else None,
                "median_current": round(float(ce[known].median()), 1),
                "median_proposed": round(float(pe[known].median()), 1),
                "p90_proposed": round(float(pe[known].quantile(0.9)), 1)}

    # ---- deposit-active accounts left at $0 --------------------------------
    if prop is not None and DEP_CT in df.columns and "open" in masks and "personal" in masks:
        op = masks["open"] & masks["personal"]
        dep = pd.to_numeric(df[DEP_CT], errors="coerce").fillna(0)
        m["pgl_zero_limit_active"] = int(((prop == 0) & (dep >= 2) & op).sum())

    # ---- computed headlines ------------------------------------------------
    H: list[str] = []
    f = {r[0]: r[1] for r in funnel}
    if "eligible" in f and "open" in f:
        H.append(f"{f['eligible']:,} of {f['open']:,} open accounts are eligible "
                 f"under the confirmed OD codes"
                 + (f"; {f['proposed_limit']:,} carry a proposed limit above $0"
                    if "proposed_limit" in f else ""))
    ex = m.get("pgl_exposure")
    if ex:
        H.append(f"limit exposure on eligibles moves ${ex['current_total']:,} -> "
                 f"${ex['proposed_total']:,} ({ex['delta']:+,}"
                 + (f", {ex['delta_pct']:+.1f}%" if ex.get("delta_pct") is not None else "")
                 + f"); median ${ex['median_current']:,.0f} -> ${ex['median_proposed']:,.0f}")
    za = m.get("pgl_zero_limit_active")
    if za:
        H.append(f"{za:,} deposit-active open personal accounts sit at a $0 proposed limit")
    m["pgl_headlines"] = H
    return m
