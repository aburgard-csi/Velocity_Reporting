"""lift_window: the Lift Matrix MM window and whether the data month is inside it (2026-09-15).

One definition for the deck (extract_lift) and the launcher's pre-build check. 1780 USF CU's
window ended Feb 2026 against Aug 2026 data, and nothing stopped its build.
"""
import datetime as dt
import os
import sys

import openpyxl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "build", "ars_pipeline"))
import lift_window as LW  # noqa: E402


def sheet(start, end, data_label="August 2026 Data"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = LW.SHEET
    ws.cell(6, 2, data_label)
    ws.cell(9, 2, "Start Date"); ws.cell(9, 3, start)
    ws.cell(10, 2, "End Date"); ws.cell(10, 3, end)
    ws.cell(14, 2, "Baseline Segment")
    return wb, ws


def test_data_past_the_end_date_is_expired():
    _, ws = sheet(dt.datetime(2025, 3, 1), dt.datetime(2026, 2, 1))
    w = LW.window(ws)
    assert w["window"] == "Mar 2025 – Feb 2026" and w["data_date"] == "Aug 2026"
    assert w["data_past_end"] and not w["in_window"]


def test_data_inside_the_window_is_current():
    _, ws = sheet(dt.datetime(2026, 5, 1), dt.datetime(2027, 4, 1))
    w = LW.window(ws)
    assert w["in_window"] and not w["data_past_end"]


def test_the_end_month_itself_is_still_current():
    _, ws = sheet(dt.datetime(2025, 9, 1), dt.datetime(2026, 8, 1))
    assert LW.window(ws)["in_window"]


def test_an_undated_matrix_is_neither_current_nor_expired():
    _, ws = sheet(None, None)
    w = LW.window(ws)
    assert w["window"] == "" and not w["in_window"] and not w["data_past_end"]


def test_a_workbook_without_the_tab_has_no_window(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.title = "Executive Financials"
    p = tmp_path / "sm.xlsx"
    wb.save(p)
    assert LW.workbook_window(str(p)) is None
    wb2, _ = sheet(dt.datetime(2025, 3, 1), dt.datetime(2026, 2, 1))
    p2 = tmp_path / "mm.xlsx"
    wb2.save(p2)
    assert LW.workbook_window(str(p2))["data_past_end"]
