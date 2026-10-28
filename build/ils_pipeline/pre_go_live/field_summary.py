# Ported from v5 02-Scripts/ils/pre_go_live/field_summary.py at 7ba1e63. Logic unchanged; copied whole.
"""Field summary: always emitted, even before codes exist.

Both the data QA and the surface the codes are chosen from: column groups
with coverage, the code fields' distinct values with counts, duplicate and
Deleted checks, and suggestions where a value is unambiguous -- suggested,
never applied without confirmation.
"""

from __future__ import annotations

import pandas as pd

CODE_FIELDS = ["Account Status Code", "OD Status Code (from Core)",
               "Reg-E Opt-In Value", "Personal_Business", "Eligible_For_Scoring",
               "UpOrDown from Initial OD Limit", "YTDODItemsBucket"]
GROUPS = [
    ("identifiers", ["AcctNo", "HASHED_ACCT_NO", "Accounts", "Institution", "Product Code"]),
    ("segments & codes", ["Personal_Business", "Account Status Code",
                          "OD Status Code (from Core)", "Reg-E Opt-In Value",
                          "Eligible_For_Scoring", "OVERRIDE (from ILS)",
                          "Exported Status Code (from ILS)"]),
    ("limits & score", ["Initial OD Limit (from Core)", "OD Limit (from ILS)",
                        "OD Limit (from ILS) 33 days ago",
                        "Average OD Limit (from ILS) last 33 days",
                        "UpOrDown from Initial OD Limit", "Limit Effective Date (from ILS)"]),
    ("items & fees", ["YTDODItems", "YTDODItemsBucket", "NSF OD Items since start date",
                      "Paid NSF OD Items since start date", "Rolling 12 Month NSFOD Items",
                      "Rolling 12 Month NSFOD Fees", "Days OD", "RDI Last 33 Days",
                      "Strategic_Refunds"]),
    ("deposits & debits", ["Deposit Count Last 33 days", "Deposit Amount Last 33 days",
                           "Debit Decline Count", "Debit Decline Amount",
                           "Min Debit Decline Amount", "Max Debit Decline Amount",
                           "ACH Debit Amount", "CHK Debit Amount", "Misc Debit Amount"]),
    ("dates", ["Open Date", "Last Update", "Deleted"]),
    ("trending", ["DEPOSIT_TRENDING", "REPAYMENT_TRENDING", "WINDFALL_TRENDING"]),
]
MAX_VALUES = 15
OPEN_HINTS = {"O", "OPEN", "A", "ACTIVE"}
YES_HINTS = {"Y", "YES", "1", "TRUE", "OPT IN", "OPTIN"}
NO_HINTS = {"N", "NO", "0", "FALSE", "OPT OUT", "OPTOUT"}


def _pct(n, d) -> float:
    return round(100 * n / d, 1) if d else 0.0


def compute(df: pd.DataFrame, warn) -> dict:
    m: dict = {}
    n = len(df)
    m["pgl_rows"] = n
    m["pgl_columns_n"] = len(df.columns)
    grouped = set()
    groups_out = []
    for name, cols in GROUPS:
        present = [c for c in cols if c in df.columns]
        grouped.update(present)
        if present:
            groups_out.append([name, present])
    other = [c for c in df.columns if c not in grouped]
    if other:
        groups_out.append(["other", other])
    m["pgl_column_groups"] = groups_out
    m["pgl_coverage"] = [[c, _pct(int(df[c].notna().sum()), n)] for c in df.columns]
    low = [c for c, cov in m["pgl_coverage"] if cov < 50.0]
    if low:
        warn(f"{len(low)} columns under 50% populated (first 8): {low[:8]}")

    values = []
    for c in CODE_FIELDS:
        if c not in df.columns:
            continue
        vc = df[c].fillna("<BLANK>").value_counts()
        values.append([c, [[str(v), int(k)] for v, k in vc.head(MAX_VALUES).items()]])
        if len(vc) > MAX_VALUES:
            warn(f"{c}: {len(vc)} distinct values; showing top {MAX_VALUES}")
    m["pgl_code_values"] = values

    if "AcctNo" in df.columns:
        m["pgl_duplicate_accts"] = int(df["AcctNo"].duplicated().sum())
        m["pgl_blank_accts"] = int(df["AcctNo"].isna().sum())
    if "Deleted" in df.columns:
        deleted = df["Deleted"].notna()
        m["pgl_deleted_rows"] = int(deleted.sum())
        if deleted.any():
            b = {"rows": int(deleted.sum()),
                 "note": ("rows carrying a deletion timestamp; excluded from "
                          "analysis bases unless include_deleted -- meaning "
                          "unconfirmed, ask the vendor")}
            if "Account Status Code" in df.columns:
                b["by_status"] = [[str(k), int(v)] for k, v in
                                  df.loc[deleted, "Account Status Code"]
                                  .fillna("<BLANK>").value_counts().items()]
            if "Last Update" in df.columns:
                lu = df.loc[deleted, "Last Update"].dt.year
                b["by_last_update_year"] = [[int(k), int(v)] for k, v in
                                            lu.value_counts().sort_index().items()
                                            if pd.notna(k)]
            m["pgl_deleted_breakdown"] = b

    # ---- the broad review: EVERY row, sliced by the code fields -----------
    # The measures that discriminate open / active / on-program, so a legend
    # question (is C closed?) is answered by evidence, not by the label.
    m.update(data_review(df))

    # ---- suggestions: only the unambiguous; od_eligible is never guessed ----
    s: dict = {}
    if "Account Status Code" in df.columns:
        hit = sorted(set(df["Account Status Code"].dropna()) & OPEN_HINTS)
        if len(hit) == 1:
            s["open_status"] = hit
    if "Reg-E Opt-In Value" in df.columns:
        seen = set(df["Reg-E Opt-In Value"].dropna())
        yes, no = sorted(seen & YES_HINTS), sorted(seen & NO_HINTS)
        if len(yes) == 1:
            s["rege_opt_in"] = yes
        if len(no) == 1:
            s["rege_opt_out"] = no
    m["pgl_suggested_codes"] = s
    return m


REVIEW_MEASURES = [
    ("deleted", "Deleted", lambda c: c.notna()),
    ("opened_12mo", "Open Date", None),      # special-cased below
    ("ils_limit_gt0", "OD Limit (from ILS)", lambda c: pd.to_numeric(c, errors="coerce") > 0),
    ("deposits_gt0", "Deposit Count Last 33 days", lambda c: pd.to_numeric(c, errors="coerce") > 0),
    ("ytd_od_gt0", "YTDODItems", lambda c: pd.to_numeric(c, errors="coerce") > 0),
    ("rege_Y", "Reg-E Opt-In Value", lambda c: c.astype("string").str.upper() == "Y"),
]
REVIEW_AVGS = [("avg_init_limit", "Initial OD Limit (from Core)"),
               ("avg_ils_limit", "OD Limit (from ILS)")]


def data_review(df: pd.DataFrame) -> dict:
    """Whole-file slices by the code fields. Nothing excluded."""
    out: dict = {}
    if "Account Status Code" not in df.columns:
        return out
    status = df["Account Status Code"].fillna("<BLANK>").astype(str)
    opened = pd.to_datetime(df.get("Open Date"), errors="coerce") \
        if "Open Date" in df.columns else None
    recent = (opened >= (opened.max() - pd.DateOffset(months=12))) \
        if opened is not None and opened.notna().any() else None

    rows, names = [], ["status", "accounts"]
    first = True
    for st, idx in df.groupby(status).groups.items():
        part = df.loc[idx]
        row = [st, len(part)]
        for name, col, fn in REVIEW_MEASURES:
            if name == "opened_12mo":
                if recent is not None:
                    row.append(int(recent.loc[idx].sum()))
                    if first: names.append(name)
                continue
            if col in part.columns:
                row.append(int(fn(part[col]).sum()))
                if first: names.append(name)
        for name, col in REVIEW_AVGS:
            if col in part.columns:
                v = pd.to_numeric(part[col], errors="coerce")
                row.append(round(float(v.mean()), 0) if v.notna().any() else None)
                if first: names.append(name)
        first = False
        rows.append(row)
    rows.sort(key=lambda r: -r[1])
    out["pgl_review_by_status"] = rows
    out["pgl_review_by_status_columns"] = names

    if "OD Status Code (from Core)" in df.columns:
        od = df["OD Status Code (from Core)"].fillna("<BLANK>").astype(str)
        xt = [[a, b, int(v)] for (a, b), v in
              df.groupby([status, od]).size().items()]
        xt.sort(key=lambda r: -r[2])
        out["pgl_review_status_x_od"] = xt[:30]
        out["pgl_review_status_x_od_columns"] = ["status", "od_status", "accounts"]
    return out