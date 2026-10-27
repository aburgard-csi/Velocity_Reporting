# Ported from ARS v5 02-Scripts/ars/guarantee.py at a491b5c (James Gilmore); logic unchanged.
"""The 2:1 guarantee deferral tracker (issues #42/#43).

`{client id} {name} ARS Deferred expense tracking.xlsx` -- one sheet:

    Program Month | ARS Revenue for Month | Velocity Charges for Mo |
    Amount Paid by {client} | Amount Deferred for Month | Amount Deferred Running

The file's own math IS the guarantee (James, 2026-08-22): while revenue
runs under 2x the charges, the client pays half of revenue and the rest
of the charge defers; the running balance draws down when revenue
exceeds the mark and is forgiven at contract end. The reader reads the
columns and verifies the arithmetic -- it never re-derives policy.

When a tracker exists, its math is the client's economics; when it
doesn't, the workbook's billed figures stand (James's rule).
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

TRACKER_GLOB = "*Deferred*.xls*"
_TOL = 1.0                      # dollars of slack per arithmetic check


def find_tracker(data_root: Path, client_id: str, period: str) -> Path | None:
    """The client's deferral tracker, canonical layout first."""
    for base in (data_root / "ARS" / period / str(client_id),
                 data_root / period / str(client_id),
                 data_root / str(client_id)):
        if base.is_dir():
            hits = sorted(p for p in base.glob(TRACKER_GLOB)
                          if not p.name.startswith("~$"))
            if hits:
                return hits[-1]
    return None


def _month(v) -> str | None:
    if isinstance(v, (date, datetime)):
        return f"{v.year}-{v.month:02d}"
    return None


def read(path: Path, warn) -> dict:
    """Parse the tracker into gt_* metrics, verifying its arithmetic."""
    import zipfile

    import openpyxl

    try:
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    except zipfile.BadZipFile:
        warn(f"deferral tracker {path.name} is not a readable xlsx -- "
             f"usually Excel's ~$ lock stub or a partial copy. Delete it "
             f"from 01-Data, close Excel on the source, and re-fetch "
             f"(fetch now skips ~$ stubs). Workbook math stands this run.")
        return {}
    except PermissionError:
        warn(f"deferral tracker {path.name} is locked (open in Excel, or "
             f"OneDrive still syncing) -- close it and re-run; guarantee "
             f"slide skipped, workbook math stands this run")
        return {}
    ws = wb.worksheets[0]
    months: list[list] = []
    for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 400),
                            max_col=6):
        vals = [c.value for c in row]
        mth = _month(vals[0])
        if mth is None:
            continue                      # title / header / blank rows
        nums = []
        for v in vals[1:6]:
            try:
                nums.append(round(float(v), 2))
            except (TypeError, ValueError):
                nums.append(None)
        if any(v is None for v in nums):
            warn(f"deferral tracker: {mth} has a blank/non-numeric cell; "
                 f"row skipped")
            continue
        months.append([mth] + nums)
    wb.close()
    if not months:
        warn(f"deferral tracker {path.name}: no month rows recognized; "
             f"tracker ignored, workbook math stands")
        return {}

    # ---- verify the file's own arithmetic ------------------------------
    prev_running = 0.0
    for mth, rev, charges, paid, deferred, running in months:
        if abs((paid + deferred) - charges) > _TOL:
            warn(f"deferral tracker: {mth} paid {paid:,.2f} + deferred "
                 f"{deferred:,.2f} != charges {charges:,.2f}")
        if abs((prev_running + deferred) - running) > _TOL:
            warn(f"deferral tracker: {mth} running balance does not tie "
                 f"({prev_running:,.2f} + {deferred:,.2f} != "
                 f"{running:,.2f})")
        if deferred > _TOL and rev > 0 and abs(paid * 2 - rev) > _TOL:
            warn(f"deferral tracker: {mth} pays {paid:,.2f} against "
                 f"{rev:,.2f} revenue -- not the half-of-revenue "
                 f"guarantee math; confirm the sheet")
        prev_running = running

    last = months[-1]
    balance = last[5]
    if balance <= _TOL:
        state = "clear"
    elif len(months) >= 2 and last[5] < months[-2][5] - _TOL:
        state = "drawing-down"
    else:
        state = "in-guarantee"

    out = {
        "gt_source": path.name,
        "gt_months": months,
        "gt_months_n": len(months),
        "gt_latest_month": last[0],
        "gt_revenue_ltd": round(sum(m[1] for m in months), 2),
        "gt_charges_ltd": round(sum(m[2] for m in months), 2),
        "gt_paid_ltd": round(sum(m[3] for m in months), 2),
        "gt_deferred_balance": balance,
        "gt_state": state,
    }
    if last[2]:
        out["gt_ratio_latest"] = round(last[1] / last[2], 2)
    return out
