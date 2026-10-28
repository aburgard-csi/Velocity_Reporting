# Ported from v5 02-Scripts/ils/pre_go_live/sections/readiness.py at 7ba1e63. Logic unchanged; copied whole.
"""Readiness scorecard: can this extract support each analysis? Graded from
column coverage so 'the data is thin' is a slide, not an archaeology
exercise. ok = every required column usable; thin = under half populated;
blocked = a required column is absent or entirely empty."""

from __future__ import annotations

import pandas as pd

CHECKS = [
    ("book & status", ["Account Status Code", "Personal_Business"], "status / segments"),
    ("limits & score", ["Initial OD Limit (from Core)", "OD Limit (from ILS)",
                        "UpOrDown from Initial OD Limit"], "limit change story"),
    ("Reg-E", ["Reg-E Opt-In Value", "Open Date"], "opt-in mix and trend"),
    ("deposits (33-day)", ["Deposit Count Last 33 days", "Deposit Amount Last 33 days"],
     "zero-limit x activity"),
    ("fee history (12-mo)", ["Rolling 12 Month NSFOD Items", "Rolling 12 Month NSFOD Fees"],
     "fee tier scenarios"),
    ("items since start", ["NSF OD Items since start date",
                           "Paid NSF OD Items since start date"], "pay rates"),
    ("debit declines", ["Debit Decline Count", "Debit Decline Amount"], "decline story"),
    ("trending", ["DEPOSIT_TRENDING", "REPAYMENT_TRENDING"], "vendor trend scores"),
]
THIN_BELOW = 50.0


def compute(df, bases, inputs, warn) -> dict:
    rows = []
    for name, cols, unlocks in CHECKS:
        coverage = []
        for c in cols:
            if c not in df.columns:
                coverage.append((c, None))
                continue
            col = df[c]
            if col.dtype.kind in "ifM":
                nonnull = col.notna()
                # an all-zero numeric column carries no signal either
                if col.dtype.kind in "if":
                    nonnull = nonnull & (pd.to_numeric(col, errors="coerce").fillna(0) != 0)
                pct = 100 * nonnull.mean()
            else:
                pct = 100 * col.notna().mean()
            coverage.append((c, round(float(pct), 1)))
        pcts = [p for _, p in coverage]
        if any(p is None or p == 0.0 for p in pcts):
            grade = "blocked"
        elif min(pcts) < THIN_BELOW:
            grade = "thin"
        else:
            grade = "ok"
        rows.append([name, grade, unlocks,
                     [[c, p] for c, p in coverage]])
        if grade == "blocked":
            warn(f"readiness: {name} is blocked ({unlocks} unavailable) -- "
                 f"columns empty or missing: "
                 f"{[c for c, p in coverage if p is None or p == 0.0]}")
    out = {"pgl_readiness": rows,
           "pgl_readiness_columns": ["area", "grade", "unlocks", "column_coverage"]}
    out["pgl_readiness_blocked"] = [r[0] for r in rows if r[1] == "blocked"]
    return out
