# Ported from v5 02-Scripts/ils/pre_go_live/loader.py at 7ba1e63. The folder lookup reads Inputs/ILS PGL/ (ils_pipeline/pgl_input.py). One RPE change (2026-10-28, CHANGELOG): find_extract never takes the vendor's MatrixValidation / IntegrityCheck dump as the extract.
"""PGL extract loader.

One CSV or Excel per delivery under 01-Data/ILS/{client}/, the date in the
filename (1737_TxNat_PreGL_20260807.csv). Newest wins; the others are
reported, never silently ignored. Columns are named, not positional; each
section declares what it needs and declines when it's absent, so the loader
keeps every column it finds.

Type rules follow the notebook (PGL v1, Cell 4): code-like fields stay
strings (leading zeros survive), upper-cased, blank -> NA; dates parsed;
everything money- or count-like coerced to numeric with NaN on failure;
literal "NULL" strings are missing values.
"""

from __future__ import annotations

import re
import warnings as _warnings
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

ILS_DIRS = ("ILS", "ils", "PGL", "pgl")
DATE_RE = re.compile(r"(20\d{6})")
EXTS = {".csv", ".xls", ".xlsx"}
# The vendor's two system dumps sit beside the extract and may be saved as .csv (1759 First Central,
# 2026-10: "1759_MatrixValidation_PGL2.csv", no date in the name). Read as an extract, the undated dump
# was dated by file time and won the "newest" race against the real one (RPE, 2026-10-28).
DUMP_RE = re.compile(r"matrix.?validation|integrity.?check", re.I)

CODE_COLUMNS = ["AcctNo", "Personal_Business", "Eligible_For_Scoring",
                "OD Status Code (from Core)", "Account Status Code",
                "Reg-E Opt-In Value", "YTDODItemsBucket", "OVERRIDE (from ILS)",
                "UpOrDown from Initial OD Limit"]
UPPER_COLUMNS = ["Personal_Business", "Eligible_For_Scoring",
                 "OD Status Code (from Core)", "Account Status Code",
                 "Reg-E Opt-In Value"]
DATE_COLUMNS = ["Open Date", "Last Update", "Limit Effective Date (from ILS)", "Deleted"]
NUMERIC_COLUMNS = ["YTDODItems", "NSF OD Items since start date",
                   "Paid NSF OD Items since start date", "Initial OD Limit (from Core)",
                   "OD Limit (from ILS)", "OD Limit (from ILS) 33 days ago",
                   "Average OD Limit (from ILS) last 33 days", "Deposit Count Last 33 days",
                   "Deposit Amount Last 33 days", "Days OD", "Debit Decline Count",
                   "Debit Decline Amount", "Min Debit Decline Amount",
                   "Max Debit Decline Amount", "DEPOSIT_TRENDING", "REPAYMENT_TRENDING",
                   "Rolling 12 Month NSFOD Items", "Rolling 12 Month NSFOD Fees",
                   "WINDFALL_TRENDING", "RDI Last 33 Days", "Strategic_Refunds",
                   "ACH Debit Amount", "CHK Debit Amount", "Misc Debit Amount"]
# 1737's full contract; the loader reports what is missing, never assumes.
COLUMNS_1737 = ['AcctNo', 'Personal_Business', 'Eligible_For_Scoring', 'YTDODItemsBucket', 'YTDODItems', 'NSF OD Items since start date', 'Paid NSF OD Items since start date', 'OD Status Code (from Core)', 'Initial OD Limit (from Core)', 'Exported Status Code (from ILS)', 'OD Limit (from ILS)', 'OD Limit (from ILS) 33 days ago', 'Average OD Limit (from ILS) last 33 days', 'UpOrDown from Initial OD Limit', 'Deposit Count Last 33 days', 'Deposit Amount Last 33 days', 'Open Date', 'Days OD', 'Reg-E Opt-In Value', 'Last Update', 'OVERRIDE (from ILS)', 'Limit Effective Date (from ILS)', 'Debit Decline Count', 'Debit Decline Amount', 'Min Debit Decline Amount', 'Max Debit Decline Amount', 'DEPOSIT_TRENDING', 'REPAYMENT_TRENDING', 'Accounts', 'Institution', 'HASHED_ACCT_NO', 'Account Status Code', 'Product Code', 'ACH Debit Amount', 'CHK Debit Amount', 'Misc Debit Amount', 'Rolling 12 Month NSFOD Items', 'Rolling 12 Month NSFOD Fees', 'WINDFALL_TRENDING', 'RDI Last 33 Days', 'Strategic_Refunds', 'Deleted']
EXPECTED_COLUMNS = len(COLUMNS_1737)


@dataclass
class Extract:
    path: Path
    date: pd.Timestamp
    others: list[Path] = field(default_factory=list)


def find_extract(data_root: Path, client_id: str) -> Extract:
    """Newest extract by the date in the filename; the rest in .others."""
    from ils_pipeline.pgl_input import ils_dirs as _ils_dirs
    folders = _ils_dirs(data_root, client_id)
    if not folders:
        raise FileNotFoundError(
            f"no PGL folder for {client_id}; looked under {data_root} for "
            f"ILS/{{month}}/{client_id} and {list(ILS_DIRS)}/{client_id}")
    folder = folders[0]           # newest month first; kept for messages
    dated = []
    for p in sorted(q for f in folders for q in f.iterdir()):
        if p.suffix.lower() not in EXTS or p.name.startswith("~") or DUMP_RE.search(p.name):
            continue
        m = DATE_RE.search(p.name)
        stamp = (pd.to_datetime(m.group(1), format="%Y%m%d", errors="coerce")
                 if m else None)
        if stamp is None or pd.isna(stamp):
            stamp = pd.Timestamp(p.stat().st_mtime, unit="s").normalize()
        dated.append((stamp, p))
    if not dated:
        raise FileNotFoundError(f"no CSV/Excel extract in {folder}")
    # Same filename-date twice (a re-download saved as "... (1).csv") is the
    # classic trap: break the tie by MODIFICATION time, so the file that
    # arrived last wins, never the alphabet.
    dated.sort(key=lambda t: (t[0], t[1].stat().st_mtime, t[1].name))
    newest = dated[-1]
    return Extract(path=newest[1], date=newest[0],
                   others=[p for _, p in dated[:-1]])


def load(path: Path, sheet=0) -> tuple[pd.DataFrame, list[str]]:
    """Read and standardize; returns (df, warnings)."""
    warns: list[str] = []
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig",
                         keep_default_na=False, na_values=["", "NULL", "NaN", "nan"])
    else:
        df = pd.read_excel(path, sheet_name=sheet, dtype=str)
        df = df.replace("NULL", pd.NA)
    df.columns = [str(c).strip() for c in df.columns]
    if len(df.columns) != EXPECTED_COLUMNS:
        warns.append(f"{len(df.columns)} columns found (1737's contract has "
                     f"{EXPECTED_COLUMNS}); sections decline for what's missing")
    for c in CODE_COLUMNS:
        if c in df.columns:
            df[c] = df[c].astype("string").str.strip().replace({"": pd.NA})
    for c in UPPER_COLUMNS:
        if c in df.columns:
            df[c] = df[c].str.upper()
    if "AcctNo" in df.columns:
        df["AcctNo"] = df["AcctNo"].str.replace(r"\.0$", "", regex=True)
        dup = int(df["AcctNo"].duplicated().sum())
        if dup:
            warns.append(f"{dup} duplicate AcctNo rows")
    for c in DATE_COLUMNS:
        if c in df.columns:
            raw = df[c].astype("string").str.strip().replace({"": pd.NA})
            with _warnings.catch_warnings():
                # Deleted carries Excel-mangled stamps ("02:27.7"); any parse
                # counts as a deletion marker, so dateutil fallback is fine.
                _warnings.simplefilter("ignore", UserWarning)
                df[c] = pd.to_datetime(raw, errors="coerce")
            if c == "Deleted":
                # A stamp too mangled to parse is still a deletion marker;
                # park it on a sentinel date so the row never counts as live.
                lost = raw.notna() & df[c].isna()
                if lost.any():
                    warns.append(f"{int(lost.sum())} Deleted stamps unparseable; "
                                 f"kept as deletions (sentinel 1900-01-01)")
                    df.loc[lost, c] = pd.Timestamp(1900, 1, 1)
    for c in NUMERIC_COLUMNS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df, warns
