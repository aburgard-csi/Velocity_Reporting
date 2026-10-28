# Ported from v5 02-Scripts/ils/pre_go_live/sections/waterfall.py at 7ba1e63. Logic unchanged; copied whole.
"""The filter waterfall: every step from file to base, shown, never silent.

James's rule for the PGL story: minimal filtering, and any filter that IS
applied gets its own visible step (and its own slide). Each step names the
column and codes that cut it, the count removed, and -- when the integrity
dump is present -- the ILS system figure that confirms the survivor count.

Keys: pgl_waterfall .
"""

from __future__ import annotations

import pandas as pd


def _confirm(count, system_value, label):
    if system_value is None:
        return None
    return f"= ILS {label} ({system_value:,})" if count == system_value else \
        f"ILS {label} says {system_value:,} (delta {count - system_value:+,})"


def compute(df, bases, inputs, warn) -> dict:
    codes = inputs.get("codes")
    sysv = inputs.get("system") or {}
    acct = sysv.get("sysv_accounts") or []
    sys_total = sum(r[1] or 0 for r in acct) if acct else None
    sys_open = sum(r[2] or 0 for r in acct) if acct else None
    sys_can_od = sum(r[4] or 0 for r in acct) if acct else None
    calc = (sysv.get("sysv_calc_latest") or {}).get("accounts")

    deleted = inputs.get("deleted_rows") or 0
    received = len(df) + deleted
    steps: list[list] = []

    def step(label, count, why, confirms=None):
        prev = steps[-1][1] if steps else received
        steps.append([label, count, count - prev if steps else 0, why, confirms])

    step("Rows received", received, "the extract as delivered",
         _confirm(received - deleted, sys_total, "book + deletions") if sys_total else None)
    if deleted:
        step("Live accounts", len(df),
         "rows with a Deleted stamp removed -- the vendor marked them deleted "
         "over time; every stamp is visible in the data review",
         _confirm(len(df), sys_total, "total book"))

    status = df.get("Account Status Code")
    if status is not None and codes and codes.open_status:
        m_open = status.isin(codes.open_status).fillna(False)
        gone = status[~m_open].value_counts()
        step(f"Open accounts (status {'/'.join(codes.open_status)})", int(m_open.sum()),
             "closed and inactive statuses removed: "
             + ", ".join(f"{k} ({v:,})" for k, v in gone.head(4).items()),
             _confirm(int(m_open.sum()), sys_open, "open/active"))
    else:
        m_open = pd.Series(True, index=df.index)

    scorable = df.get("Eligible_For_Scoring")
    if scorable is not None:
        m_scor = m_open & (scorable == "YES").fillna(False).astype(bool)
        od = df.get("OD Status Code (from Core)")
        gone_note = ""
        if od is not None:
            gone = od[(m_open & ~m_scor).astype(bool)].value_counts()
            gone_note = " (their OD status: " + ", ".join(
                f"{k} ({v:,})" for k, v in gone.head(4).items()) + ")"
        step("ILS calculates a limit", int(m_scor.sum()),
             "open accounts the ILS matrix scores daily; the rest sit on "
             "status codes the matrix does not map" + gone_note,
             _confirm(int(m_scor.sum()), calc, "daily calc"))

    od = df.get("OD Status Code (from Core)")
    if od is not None and codes and codes.od_eligible:
        m_can = m_open & od.isin(codes.od_eligible).fillna(False)
        step(f"Can overdraft today (core status {'/'.join(codes.od_eligible)})",
             int(m_can.sum()),
             "the core's own eligibility -- the accounts a limit means anything "
             "for right now",
             _confirm(int(m_can.sum()), sys_can_od, "can overdraft"))

    rege = df.get("Reg-E Opt-In Value")
    if rege is not None and codes and codes.rege_opt_in and status is not None:
        m_re = m_open & rege.isin(codes.rege_opt_in).fillna(False)
        step("Reg-E opted in (of open)", int(m_re.sum()),
             "covered for ATM / one-time debit overdraft fees", None)

    m: dict = {"pgl_waterfall": steps,
               "pgl_waterfall_columns": ["step", "accounts", "removed", "why", "system_confirms"]}
    confirmed = sum(1 for s in steps if s[4] and s[4].startswith("="))
    if confirmed:
        m["pgl_waterfall_confirmed"] = confirmed
    return m
