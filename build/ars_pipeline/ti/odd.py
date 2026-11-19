"""
odd.py — the Transaction Intelligence cut's ODD frame.

The client's ODD extract, read with its header row DETECTED and transformed exactly as the
ARS v5 engine does (`ti/core/odd_transform.py`), so every ported analysis sees the frame it
was written against and its figures can be checked against v5's.

The extract is the one every ARS build reads: `Inputs/ODDD/<id>_ODDD.zip`, its ODD member
chosen and extracted once per process by `rpe_env.extract_odd_csv` (a transaction member
beside it is never read as the ODD). The preamble above the header is not a fixed length,
so the header is the first of the first 25 lines carrying at least three of the anchor
columns, as in v5.

Import-safe: nothing here reads the share until a function is called.
"""
import csv
from pathlib import Path

import pandas as pd

from ti.core.odd_transform import transform_odd
from ti.core.periods import data_month

ANCHORS = ("Acct ID", "Acct Number", "Prod Code", "Stat Code", "Branch")
HEADER_SCAN = 25


def odd_zip(client_id) -> Path:
    """`Inputs/ODDD/<id>_ODDD.zip`. Raises with a plain sentence when it is not there."""
    import rpe_env
    p = rpe_env.input_dir("ODDD", create=False) / f"{client_id}_ODDD.zip"
    if not p.is_file():
        raise SystemExit(f"client {client_id}: no ODD extract at {p}")
    return p


def header_row(path) -> int:
    """Index of the header line: the first of the first 25 carrying 3+ anchor columns."""
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
        for i, row in enumerate(csv.reader(fh)):
            if i >= HEADER_SCAN:
                break
            if sum(a in {str(v).strip() for v in row} for a in ANCHORS) >= 3:
                return i
    raise ValueError(f"no header row in the first {HEADER_SCAN} lines of {Path(path).name}")


def read_raw(path) -> pd.DataFrame:
    """The ODD csv as read by v5: header detected, a leading unnamed column dropped."""
    df = pd.read_csv(path, skiprows=header_row(path), low_memory=False,
                     encoding="utf-8-sig", encoding_errors="replace")
    first = str(df.columns[0])
    if first.startswith("Unnamed") or not first.strip():
        df = df.drop(columns=df.columns[0])
    return df


def load(path, end_month=None):
    """(frame, report) for an ODD csv path: read, then v5's transform. `report.errors`
    non-empty means the frame must not be used; `report.warnings` are stated, not hidden.
    `end_month`: the window's last completed month (ti/window.py); later months are left out."""
    return transform_odd(read_raw(path), end_month=end_month)


def load_client(client_id, end_month=None):
    """(frame, report, source) for a client's current ODD extract."""
    import rpe_env
    z = odd_zip(client_id)
    csv_path = rpe_env.extract_odd_csv(z)       # the ARS build's own cache and scratch prefix
    frame, report = load(csv_path, end_month=end_month)
    return frame, report, f"{z.name} / {Path(csv_path).name}"


def frame_data_month(frame):
    """The newest month carried by the frame's transaction columns (v5's data month)."""
    return data_month(frame.columns)
