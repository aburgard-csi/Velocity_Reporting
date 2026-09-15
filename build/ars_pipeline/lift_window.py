"""The Lift Matrix MM window, and whether a workbook's data month falls inside it — one definition.

Read by `extract_lift.py` (the deck's lift.json) and by `scripts/ars_launcher.py`, whose pre-build
check stops a build on an expired matrix (Aaron, 2026-09-15: "Add the lift matrix date check to the
build criteria"). It used to live only inside extract_lift, which runs as a script, so nothing could
check the window before a build without running the extractor. Import-safe.

A matrix is expired when the workbook's data month is after the window's End Date: the per-segment
revenue it carries was set for an earlier window and no longer applies.
"""
import datetime as _dt
import re as _re

SHEET = "Lift Matrix MM"


def _ml(v):
    return v.strftime("%b %Y") if isinstance(v, _dt.datetime) else v


def _label_date(label):
    """'August 2026 Data' -> datetime(2026, 8, 1); None when the label names no month."""
    m = _re.match(r"([A-Za-z]+)\s+(\d{4})", str(label))
    if not m:
        return None
    try:
        return _dt.datetime.strptime(m.group(1)[:3] + " " + m.group(2), "%b %Y")
    except ValueError:
        return None


def header_row(ws):
    """The 'Baseline Segment' header row of the current matrix block, or None."""
    for r in range(8, 22):
        if ws.cell(r, 2).value == "Baseline Segment":
            return r
    return None


def window(ws, hdr_r=None):
    """Window dates, data month and validity from a 'Lift Matrix MM' sheet."""
    hdr_r = hdr_r or header_row(ws)
    sd = ed = None
    if hdr_r:
        for r in range(max(1, hdr_r - 8), hdr_r):
            if ws.cell(r, 2).value == "Start Date":
                sd = ws.cell(r, 3).value
            if ws.cell(r, 2).value == "End Date":
                ed = ws.cell(r, 3).value
    dd = _label_date(ws.cell(6, 2).value)
    dated = isinstance(sd, _dt.datetime) and isinstance(ed, _dt.datetime)
    return {
        "window": f"{_ml(sd)} – {_ml(ed)}" if sd and ed else "",
        "data_date": _ml(dd),
        "window_start": _ml(sd),
        "window_end": _ml(ed),
        "data_past_end": bool(dd and dated and dd > ed),
        "in_window": bool(dd and dated and sd <= dd <= ed),
    }


def workbook_window(path):
    """window() for a workbook file; None when it has no 'Lift Matrix MM' sheet (an SM workbook)."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        if SHEET not in wb.sheetnames:
            return None
        return window(wb[SHEET])
    finally:
        wb.close()
