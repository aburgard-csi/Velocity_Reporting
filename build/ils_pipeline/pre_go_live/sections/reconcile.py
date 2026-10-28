# Ported from v5 02-Scripts/ils/pre_go_live/sections/reconcile.py at 7ba1e63. Logic unchanged; copied whole.
"""Reconciliation: does the extract agree with the ILS system's own numbers?

The integrity check is what the vendor's system says it holds; the extract
is what the engineer pulled. Before any story is told, the two must agree --
row for row where possible. Each check names both figures and the delta, so
"the data is wrong" becomes "THIS number disagrees by THIS much".

Declines with one warn when no integrity dump sits next to the extract.
Keys: pgl_reconcile_* .
"""

from __future__ import annotations

import pandas as pd

MATCH_TOLERANCE = 0          # exact by default; a row can carry its own


def _row(check, extract_v, system_v, tolerance=MATCH_TOLERANCE, note=""):
    ok = None
    if extract_v is not None and system_v is not None:
        ok = abs(extract_v - system_v) <= tolerance
    return [check, extract_v, system_v,
            None if extract_v is None or system_v is None else extract_v - system_v,
            ok, note]


def compute(df, bases, inputs, warn) -> dict:
    sysv = inputs.get("system") or {}
    if not sysv.get("sysv_accounts"):
        warn("reconcile: no integrity-check dump; extract-vs-system "
             "reconciliation skipped")
        return {}
    m: dict = {}
    rows: list[list] = []

    acct = {r[0]: r for r in sysv["sysv_accounts"]}
    sys_total = sum(r[1] or 0 for r in sysv["sysv_accounts"])
    sys_open = sum(r[2] or 0 for r in sysv["sysv_accounts"])
    sys_can_od = sum(r[4] or 0 for r in sysv["sysv_accounts"])
    sys_rege = sum(r[6] or 0 for r in sysv["sysv_accounts"])

    # df here is the LIVE book (deleted rows dropped before sections run).
    rows.append(_row("live accounts (extract minus deleted) vs ILS book",
                     len(df), sys_total))
    codes = inputs.get("codes")
    status = df.get("Account Status Code")
    if status is not None and codes and codes.open_status:
        n_open = int(status.isin(codes.open_status).sum())
        rows.append(_row(f"status {codes.open_status} vs ILS open/active",
                         n_open, sys_open))
    seg = df.get("Personal_Business")
    if seg is not None and "Personal" in acct:
        rows.append(_row("personal accounts vs ILS personal book",
                         int((seg == "PERSONAL").sum()), acct["Personal"][1]))

    od = df.get("OD Status Code (from Core)")
    if od is not None and codes and codes.od_eligible:
        n_elig = int(od.isin(codes.od_eligible).fillna(False)[
            status.isin(codes.open_status)].sum()) if status is not None else None
        rows.append(_row(f"core OD status {codes.od_eligible} on open accounts "
                         f"vs ILS 'can overdraft'", n_elig, sys_can_od))

    scorable = df.get("Eligible_For_Scoring")
    calc = sysv.get("sysv_calc_latest") or {}
    if scorable is not None and calc.get("accounts"):
        n_yes = int((scorable == "YES").sum())
        rows.append(_row("Eligible_For_Scoring = Yes vs accounts ILS "
                         "calculates daily", n_yes, calc["accounts"]))

    rege = df.get("Reg-E Opt-In Value")
    if rege is not None and codes and codes.rege_opt_in:
        n_y = int(rege.isin(codes.rege_opt_in).sum())
        rows.append(_row("Reg-E opted in (whole live book) vs ILS opt-in count",
                         n_y, sys_rege,
                         tolerance=max(5, round(0.01 * (sys_rege or 1))),
                         note="bases differ slightly (ILS counts per type)"))

    m["pgl_reconcile"] = rows
    m["pgl_reconcile_columns"] = ["check", "extract", "ils_system", "delta", "match", "note"]
    matches = [r for r in rows if r[4] is True]
    misses = [r for r in rows if r[4] is False]
    m["pgl_reconcile_matches"] = len(matches)
    m["pgl_reconcile_misses"] = len(misses)
    for r in misses:
        warn(f"reconcile MISMATCH: {r[0]} -- extract {r[1]:,} vs system {r[2]:,} "
             f"(delta {r[3]:+,})")

    # ---- structural findings the reconciliation surfaces ------------------
    findings = []
    unmapped = sysv.get("sysv_od_status_unmapped") or []
    if unmapped:
        total_unmapped = sum(n or 0 for _, n in unmapped)
        findings.append(f"{total_unmapped:,} accounts sit on OD status codes the ILS "
                        f"matrix has NO mapping for ({', '.join(f'{c} ({n:,})' for c, n in unmapped)}) "
                        f"-- they fall outside the daily calculation")
    exported = df.get("Exported Status Code (from ILS)")
    if exported is not None:
        vals = exported.dropna().astype(str).unique()
        if len(vals) == 1 and vals[0] in ("0", "0.0"):
            findings.append("Exported Status Code (from ILS) = 0 on every row: ILS "
                            "calculates daily but exports nothing to the core -- "
                            "true shadow mode, the core still runs its own limits")
    if "Deleted" in df.columns or (inputs.get("deleted_rows") or 0):
        n_del = inputs.get("deleted_rows") or 0
        sys_del = sysv.get("sysv_deleted_total")
        if n_del and sys_del:
            findings.append(f"{n_del:,} deleted-stamped rows in the extract; the dump's "
                            f"largest deletion batches account for {sys_del:,} "
                            f"({sysv.get('sysv_deleted_note', '')})")
    if findings:
        m["pgl_reconcile_findings"] = findings
    return m
