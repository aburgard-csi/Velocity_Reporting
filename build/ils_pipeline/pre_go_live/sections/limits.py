# Ported from v5 02-Scripts/ils/pre_go_live/sections/limits.py at 7ba1e63. Logic unchanged; copied whole.
"""Limits (notebook A10-A12): zero-ILS-limit accounts by deposit activity
(who transacts but got nothing), the current core limit distribution, the
proposed ILS limit distribution on eligibles, and the eligible-with-NULL-
limit integrity drill-down."""

from __future__ import annotations

import pandas as pd

from ._cut import DEP_CT, ILS_LIMIT, INIT_LIMIT, cut, open_personal

DEP_BINS = [-0.1, 0.1, 1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 12.1, 24.1, float("inf")]
DEP_LABELS = ["0", "1", "2", "3", "4", "5", "6", "7-12", "13-24", "25+"]


def compute(df, bases, inputs, warn) -> dict:
    if ILS_LIMIT not in df.columns or "open" not in bases.masks:
        warn("limits: needs OD Limit (from ILS) and an open base; skipped")
        return {}
    m: dict = {}
    w = open_personal(df, bases).copy()
    eligible_codes = set(inputs["codes"].od_eligible)

    # ---- eligibility cross-check: do the proposed limits live where the
    # confirmed eligible codes say they should? If most accounts with a
    # proposed limit sit in OTHER OD codes, the code choice is probably
    # wrong for this client -- say so before anyone reads the tables.
    if "OD Status Code (from Core)" in w.columns:
        has_limit = pd.to_numeric(w[ILS_LIMIT], errors="coerce") > 0
        n_limit = int(has_limit.sum())
        if n_limit:
            outside = w[has_limit & ~w["OD Status Code (from Core)"].isin(eligible_codes)]
            share = len(outside) / n_limit
            m["pgl_proposed_outside_eligible"] = [len(outside), n_limit,
                                                  round(100 * share, 1)]
            if share > 0.5:
                top = outside["OD Status Code (from Core)"].value_counts().head(3)
                warn(f"{len(outside):,} of {n_limit:,} accounts with a proposed "
                     f"ILS limit ({share:.0%}) sit outside the confirmed eligible codes "
                     f"{sorted(eligible_codes)} -- mostly "
                     f"{', '.join(f'{k} ({v:,})' for k, v in top.items())}. "
                     f"Re-check which OD codes mean ILS-eligible for this client.")

    # ---- zero-limit x deposit activity (A10) -------------------------------
    if DEP_CT in w.columns:
        z = w[pd.to_numeric(w[ILS_LIMIT], errors="coerce") == 0].copy()
        if len(z):
            z["_bucket"] = pd.cut(pd.to_numeric(z[DEP_CT], errors="coerce").fillna(0),
                                  bins=DEP_BINS, labels=DEP_LABELS)
            rows, names = cut(z, "_bucket")
            elig = (z["OD Status Code (from Core)"].isin(eligible_codes)
                    if "OD Status Code (from Core)" in z.columns
                    else pd.Series(False, index=z.index))
            by_bucket = z[elig].groupby("_bucket", observed=True).size()
            rows = [r + [int(by_bucket.get(r[0], 0))] for r in rows]
            order = {lab: i for i, lab in enumerate(DEP_LABELS)}
            rows.sort(key=lambda r: order.get(str(r[0]), 99))
            m["pgl_zero_limit_by_deposit"] = rows
            m["pgl_zero_limit_by_deposit_columns"] = names + ["od_eligible_n"]
            m["pgl_zero_limit_accounts"] = int(len(z))

    # ---- current limit distribution (A11) ----------------------------------
    if INIT_LIMIT in w.columns:
        rows, names = cut(w, INIT_LIMIT, extras=[ILS_LIMIT])
        rows.sort(key=lambda r: (r[0] is None, r[0]))
        m["pgl_limit_dist_current"] = rows
        m["pgl_limit_dist_current_columns"] = names

    # ---- proposed distribution on eligibles (A12) + integrity (NULL) -------
    if "eligible" in bases.masks:
        e = df[bases["eligible"]].copy()
        if len(e):
            null_limit = int(pd.to_numeric(e[ILS_LIMIT], errors="coerce").isna().sum())
            m["pgl_eligible_null_limit"] = null_limit
            if null_limit:
                warn(f"{null_limit} eligible accounts with NULL OD Limit (from ILS) "
                     f"-- data integrity question for the client")
            e_known = e[pd.to_numeric(e[ILS_LIMIT], errors="coerce").notna()]
            rows, names = cut(e_known, ILS_LIMIT, extras=[DEP_CT])
            rows.sort(key=lambda r: (r[0] is None, r[0]))
            m["pgl_limit_dist_proposed"] = rows
            m["pgl_limit_dist_proposed_columns"] = names
            # Current limits on the SAME base, so current-vs-proposed charts
            # never compare different denominators.
            if INIT_LIMIT in e_known.columns:
                rows, names = cut(e_known, INIT_LIMIT)
                rows.sort(key=lambda r: (r[0] is None, r[0]))
                m["pgl_limit_dist_current_eligible"] = rows
                m["pgl_limit_dist_current_eligible_columns"] = names
    return m
