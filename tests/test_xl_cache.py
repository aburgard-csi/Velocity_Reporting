"""xl_cache gives the same cell values as openpyxl's own read-only access, from one read of each sheet."""
import os
import sys

import openpyxl

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "build", "ars_pipeline"))
import xl_cache  # noqa: E402


def _book(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data"
    for r in range(1, 12):
        for c in range(1, 6):
            if (r + c) % 3:                      # leave gaps, as the ARS workbooks do
                ws.cell(r, c, f"r{r}c{c}")
    ws["E11"] = 42
    wb.create_sheet("Empty")
    p = tmp_path / "book.xlsx"
    wb.save(p)
    return str(p)


def test_every_cell_matches_openpyxl(tmp_path):
    p = _book(tmp_path)
    plain = openpyxl.load_workbook(p, read_only=True, data_only=True)["Data"]
    cached = xl_cache.load(p)["Data"]
    assert cached.max_row == plain.max_row and cached.max_column == plain.max_column
    for r in range(1, plain.max_row + 3):          # past the edge too
        for c in range(1, plain.max_column + 3):
            assert cached.cell(r, c).value == plain.cell(r, c).value, (r, c)


def test_sheetnames_membership_and_iter_rows(tmp_path):
    p = _book(tmp_path)
    wb = xl_cache.load(p)
    assert wb.sheetnames == ["Data", "Empty"] and "Data" in wb and "Nope" not in wb
    plain = list(openpyxl.load_workbook(p, read_only=True, data_only=True)["Data"].iter_rows(values_only=True))
    assert [tuple(r) for r in wb["Data"].iter_rows(values_only=True)] == [tuple(r) for r in plain]
    assert wb["Empty"].cell(1, 1).value is None
    wb.close()


def test_a_sheet_is_read_once(tmp_path, monkeypatch):
    p = _book(tmp_path)
    wb = xl_cache.load(p)
    ws = wb["Data"]
    calls = []
    real = ws._ws.iter_rows
    monkeypatch.setattr(ws._ws, "iter_rows", lambda *a, **k: calls.append(1) or real(*a, **k))
    for _ in range(50):
        ws.cell(3, 3)
    assert len(calls) == 1
