# Ported from v5 02-Scripts/ils/pre_go_live/sections/rege.py at 7ba1e63. Logic unchanged; copied whole.
"""Reg-E opt-in (notebook A7, A9, A13): the opt-in mix on open personal /
business / eligible bases, and the opt-in rate of newly opened accounts by
month (trend over the last 24 months of openings)."""

from __future__ import annotations

import pandas as pd

from ._cut import DC_CT, DEP_AMT, DEP_CT, ILS_LIMIT, INIT_LIMIT, cut, open_business, open_personal

COL = "Reg-E Opt-In Value"
TREND_MONTHS = 24
SPARSE_BELOW = 10   # mean openings/month under this -> quarterly grain


def _pct(n, d) -> float:
    return round(100 * n / d, 1) if d else 0.0


def compute(df, bases, inputs, warn) -> dict:
    if COL not in df.columns:
        warn("rege: no Reg-E column; section skipped")
        return {}
    codes = inputs["codes"]
    yes = set(codes.rege_opt_in)
    m: dict = {}
    pops = {"personal": open_personal(df, bases), "business": open_business(df, bases)}
    if "eligible" in bases.masks:
        pops["eligible"] = df[bases["eligible"]]
    for key, pop in pops.items():
        if pop.empty:
            continue
        rows, names = cut(pop, COL, extras=[INIT_LIMIT, ILS_LIMIT, DEP_CT, DEP_AMT, DC_CT])
        m[f"pgl_rege_{key}"] = rows
        m[f"pgl_rege_{key}_columns"] = names
        m[f"pgl_rege_optin_rate_{key}"] = _pct(int(pop[COL].isin(yes).sum()), len(pop))

    if "Open Date" in df.columns:
        w = open_personal(df, bases)
        opened = pd.to_datetime(w["Open Date"], errors="coerce")
        t = pd.DataFrame({"y": opened.dt.year, "m": opened.dt.month,
                          "q": opened.dt.quarter,
                          "yes": w[COL].isin(yes)}).dropna(subset=["y"])
        # A monthly line needs monthly volume; below ~10 openings a month the
        # honest grain is quarterly.
        months = t.groupby(["y", "m"]).size()
        grain = "month" if (len(months) and months.mean() >= SPARSE_BELOW) else "quarter"
        group = ["y", "m"] if grain == "month" else ["y", "q"]
        rows = []
        for keys_, part in t.groupby(group):
            n, k = len(part), int(part["yes"].sum())
            period = int(keys_[1]) if grain == "month" else f"Q{int(keys_[1])}"
            rows.append([int(keys_[0]), period, n - k, k, n, _pct(k, n)])
        rows.sort(key=lambda r: (r[0], str(r[1])))
        m["pgl_rege_trend"] = rows[-TREND_MONTHS:]
        m["pgl_rege_trend_grain"] = grain
        m["pgl_rege_trend_columns"] = ["year", grain, "other", "opted_in", "opened", "optin_rate_pct"]
    return m
