# Ported from v5 02-Scripts/ils/pre_go_live/sections/core_state.py at 7ba1e63. Logic unchanged; copied whole.
"""Today's overdraft program, on the CORE's limits.

The story's account-level chapter runs on `Initial OD Limit (from Core)` --
what members actually live under today -- never the ILS shadow limits
(those stay in the system view). A fixed-limit core program reads as a few
big buckets; each bucket gets its usage, deposits and Reg-E character.

Six things (base: open accounts):
  1. core limit distribution x can-overdraft status, exposure dollars
  2. the can-overdraft-with-$0 pocket (the accounts a limit program is FOR)
  3. OD usage today: Days OD, YTD items, by core limit
  4. deposit activity (last 33 days) by core limit
  5. Reg-E opt-in by core limit
  6. odd pockets: status codes outside the mapping that still carry limits

Keys: pgl_core_* .
"""

from __future__ import annotations

import pandas as pd

CORE = "Initial OD Limit (from Core)"
ODS = "OD Status Code (from Core)"
DEP_CT = "Deposit Count Last 33 days"
DEP_AMT = "Deposit Amount Last 33 days"


def _pct(n, d) -> float:
    return round(100 * n / d, 1) if d else 0.0


def compute(df, bases, inputs, warn) -> dict:
    if CORE not in df.columns:
        warn("core_state: no core limit column; section skipped")
        return {}
    codes = inputs.get("codes")
    open_mask = bases["open"] if "open" in bases.masks else pd.Series(True, index=df.index)
    w = df[open_mask]
    n = len(w)
    if not n:
        warn("core_state: no open accounts; section skipped")
        return {}
    m: dict = {"pgl_core_base": n}
    core = pd.to_numeric(w[CORE], errors="coerce").fillna(0)
    can_od = w[ODS].isin(codes.od_eligible).fillna(False) if (ODS in w.columns and codes
                                                              and codes.od_eligible) \
        else pd.Series(False, index=w.index)

    # ---- 1. distribution x can-overdraft ---------------------------------
    rows = []
    for lim in sorted(core.unique()):
        mask = core == lim
        rows.append([int(lim), int(mask.sum()), _pct(int(mask.sum()), n),
                     int((mask & can_od).sum()), int((mask & ~can_od).sum())])
    m["pgl_core_limits"] = rows
    m["pgl_core_limits_columns"] = ["core_limit", "accounts", "pct", "can_overdraft", "cannot"]
    m["pgl_core_exposure"] = round(float(core[can_od].sum()))
    m["pgl_core_exposure_note"] = "sum of core limits on can-overdraft accounts"

    # ---- 2. can overdraft, no limit --------------------------------------
    pocket = can_od & (core == 0)
    m["pgl_core_can_od_zero"] = int(pocket.sum())

    # ---- 3. OD usage by core limit ---------------------------------------
    ytd = pd.to_numeric(w.get("YTDODItems"), errors="coerce").fillna(0) \
        if "YTDODItems" in w.columns else None
    days = pd.to_numeric(w.get("Days OD"), errors="coerce").fillna(0) \
        if "Days OD" in w.columns else None
    if ytd is not None:
        rows = []
        for lim in sorted(core.unique()):
            mask = core == lim
            k = int(mask.sum())
            rows.append([int(lim), k, int((mask & (ytd > 0)).sum()),
                         _pct(int((mask & (ytd > 0)).sum()), k),
                         round(float(ytd[mask].sum())),
                         int((mask & (days > 0)).sum()) if days is not None else None])
        m["pgl_core_usage"] = rows
        m["pgl_core_usage_columns"] = ["core_limit", "accounts", "with_ytd_items",
                                       "pct_with_items", "ytd_items", "currently_od"]
        m["pgl_core_ytd_items"] = round(float(ytd.sum()))
        m["pgl_core_accts_with_items"] = int((ytd > 0).sum())

    # ---- 4. deposits by core limit ---------------------------------------
    if DEP_CT in w.columns:
        dep_ct = pd.to_numeric(w[DEP_CT], errors="coerce").fillna(0)
        dep_amt = pd.to_numeric(w.get(DEP_AMT), errors="coerce").fillna(0) \
            if DEP_AMT in w.columns else pd.Series(0.0, index=w.index)
        rows = []
        for lim in sorted(core.unique()):
            mask = core == lim
            k = int(mask.sum())
            active = mask & (dep_ct > 0)
            rows.append([int(lim), k, int(active.sum()), _pct(int(active.sum()), k),
                         round(float(dep_amt[active].median()) if active.any() else 0)])
        m["pgl_core_deposits"] = rows
        m["pgl_core_deposits_columns"] = ["core_limit", "accounts", "depositing_33d",
                                          "pct_depositing", "median_deposit_amt"]

    # ---- 5. Reg-E by core limit ------------------------------------------
    rege = w.get("Reg-E Opt-In Value")
    if rege is not None and codes and codes.rege_opt_in:
        opted = rege.isin(codes.rege_opt_in).fillna(False)
        rows = []
        for lim in sorted(core.unique()):
            mask = core == lim
            rows.append([int(lim), int(mask.sum()), int((mask & opted).sum()),
                         _pct(int((mask & opted).sum()), int(mask.sum()))])
        m["pgl_core_rege"] = rows
        m["pgl_core_rege_columns"] = ["core_limit", "accounts", "opted_in", "optin_pct"]

    # ---- 6. odd pockets ---------------------------------------------------
    sysv = inputs.get("system") or {}
    mapped = {r[0] for r in (sysv.get("sysv_matrix_status_map") or [])}
    if ODS in w.columns and mapped:
        # accept the mapped code as written OR zero-stripped ("001" vs "1")
        norm_mapped = mapped | {c.lstrip("0") or "0" for c in mapped}
        odd = w[~w[ODS].fillna("").astype(str).isin(norm_mapped) & w[ODS].notna()]
        if len(odd):
            rows = []
            for code, grp in odd.groupby(ODS, observed=True):
                c = pd.to_numeric(grp[CORE], errors="coerce").fillna(0)
                rows.append([str(code), len(grp), int((c > 0).sum()), round(float(c.sum()))])
            m["pgl_core_odd_pockets"] = rows
            m["pgl_core_odd_pockets_columns"] = ["od_status", "accounts",
                                                 "with_core_limit", "core_dollars"]
            warn(f"core_state: {len(odd):,} open accounts sit on OD status codes "
                 f"outside the ILS mapping ({', '.join(r[0] for r in rows)}); "
                 f"{sum(r[2] for r in rows):,} of them carry a core limit today")
    return m
