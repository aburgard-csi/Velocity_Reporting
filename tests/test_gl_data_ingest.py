"""The GL data table: clients' emailed GL spreadsheets and NSF performance tracking workbooks, one JSON table, originals archived.

Aaron, 2026-11-03: "These should be added to a JSON table in this folder to cover all clients. The original files can be archived."
Synthetic clients and workbooks only.
"""
import datetime
import json
import os
import sys

import openpyxl
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "scripts"), os.path.join(REPO, "build")]

import gl_data_ingest as G   # noqa: E402


@pytest.fixture(autouse=True)
def names(monkeypatch):
    monkeypatch.setattr(G, "client_names", lambda: {"9001": "Test Bank", "9002": "Sample CU"})


def monthly_gl(path, months=6):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Test Bank GL", "IC", "NSF", "Total NII", "Debit Card Spend", "IC Rate", None, None, "Sum of IC"])
    for i in range(months):
        d = datetime.datetime(2026, 1 + i, 1)
        ws.append([d, 1000 + i, 500 + i, 1500 + 2 * i, 2_000_000 + i, 0.005, 2.0 + i, None, "pivot" if i == 0 else None])
    wb.save(path)


def tracking(path, template=False, cycles=5, formulas=False):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Instructions"
    ws.append(["This workbook tracks overdraft income."])
    for sheet, scale in (("All Accounts", 1), ("Personal Accounts", 0.8)):
        s = wb.create_sheet(sheet)
        s.append([None])
        s.append(["General Ledger Data"] + [datetime.datetime(2025, 1 + i, 11) for i in range(cycles)])
        s.append(["All DDA Accounts"])
        for label, base in (("Gross/Potential NSF Income (Item)", 100000), ("Waivers", 5000), ("Refunds (minus Charge Offs)", 3000)):
            s.append([label] + [(base if template else base + 1000 * i) * scale for i in range(cycles)] if not template else [label, base * scale])
        if not template:
            s.append(["Net NSF Income"] + (["=B4-B5-B6"] * cycles if formulas else [90000 + 1000 * i for i in range(cycles)]))
    wb.save(path)


def test_a_monthly_gl_sheet_is_read_as_a_series_per_measure(tmp_path):
    monthly_gl(tmp_path / "Test Bank GL.xlsx")
    (tmp_path / "aliases.json").write_text(json.dumps({"test bank": "9001"}))
    r = G.run(tmp_path)
    assert r["placed"] == [("Test Bank GL.xlsx", "9001", "Test Bank", "monthly_gl")]
    t = json.loads((tmp_path / "gl_data.json").read_text())
    s = t["clients"]["9001"]["sources"][0]
    cols = s["series"]["columns"]
    assert list(cols) == ["interchange_income", "nsf_income", "total_nii", "debit_card_spend", "ic_rate", "col_g"]
    assert cols["interchange_income"][:2] == [1000, 1001] and s["series"]["dates"][0] == "2026-01-01"
    assert "pivot" not in json.dumps(t) and s["series"]["unlabeled_columns"] == ["col_g"]       # the pivot beside the data is not data
    assert s["quality"]["months"] == 6


def test_a_tracking_workbook_keeps_every_line_and_gathers_the_key_ones(tmp_path, monkeypatch):
    tracking(tmp_path / "9002 NSF tracking.xlsx")
    os.makedirs(tmp_path / "x", exist_ok=True)
    tracking(tmp_path / "x" / "formulas.xlsx", formulas=True)
    real = G._open
    monkeypatch.setattr(G, "_open", lambda path, data_only: real(path if data_only else tmp_path / "x" / "formulas.xlsx", data_only))
    r = G.run(tmp_path)
    assert r["placed"][0][1:] == ("9002", "Sample CU", "nsf_tracking")                          # a leading client number needs no alias
    s = json.loads((tmp_path / "gl_data.json").read_text())["clients"]["9002"]["sources"][0]
    assert [x["scope"] for x in s["sheets"]] == ["all", "personal"]
    lines = {ln["label"]: ln for ln in s["sheets"][0]["lines"]}
    assert lines["Gross/Potential NSF Income (Item)"]["kind"] == "input" and lines["Gross/Potential NSF Income (Item)"]["group"] == "All DDA Accounts"
    assert lines["Net NSF Income"]["kind"] == "formula"                                         # calculated, not typed in
    std = s["standard"]["all"]
    assert set(std) >= {"gross_nsf_income", "waivers", "refunds"} and std["gross_nsf_income"]["2025-01-11"] == 100000
    assert s["standard"]["personal"]["gross_nsf_income"]["2025-01-11"] == 80000


def test_the_blank_template_is_left_alone_and_a_file_with_no_client_is_kept_unassigned(tmp_path):
    tracking(tmp_path / "template.xlsx", template=True)
    tracking(tmp_path / "Mystery.xlsx")
    r = G.run(tmp_path, archive=True)
    left = dict(r["left"])
    assert "blank NSF/OD Performance Tracking template" in left["template.xlsx"]
    assert "no alias" in left["Mystery.xlsx"] and "unassigned" in left["Mystery.xlsx"]
    assert (tmp_path / "template.xlsx").exists() and (tmp_path / "Mystery.xlsx").exists()        # neither is archived: nothing to archive them under
    t = json.loads((tmp_path / "gl_data.json").read_text())
    assert [s["file"] for s in t["unassigned"]] == ["Mystery.xlsx"] and t["clients"] == {}


def test_archiving_moves_the_original_only_after_its_figures_are_in_the_table(tmp_path):
    monthly_gl(tmp_path / "Test Bank GL.xlsx")
    (tmp_path / "aliases.json").write_text(json.dumps({"test bank": "9001"}))
    G.run(tmp_path)
    assert (tmp_path / "Test Bank GL.xlsx").exists()                                            # no --archive: nothing moves
    r = G.run(tmp_path, archive=True)
    assert not (tmp_path / "Test Bank GL.xlsx").exists()
    moved = tmp_path / "_Archive" / "9001 Test Bank" / "Test Bank GL.xlsx"
    assert moved.is_file() and r["archived"] == [("Test Bank GL.xlsx", "_Archive/9001 Test Bank/Test Bank GL.xlsx")]
    s = json.loads((tmp_path / "gl_data.json").read_text())["clients"]["9001"]["sources"][0]
    assert s["archived_to"] == "_Archive/9001 Test Bank/Test Bank GL.xlsx" and len(s["sha256"]) == 64


def test_a_second_year_is_added_beside_the_first_and_a_resend_replaces_it(tmp_path):
    (tmp_path / "aliases.json").write_text(json.dumps({"test bank": "9001"}))
    monthly_gl(tmp_path / "Test Bank GL 2025.xlsx", months=3)
    G.run(tmp_path)
    monthly_gl(tmp_path / "Test Bank GL 2026.xlsx", months=5)
    G.run(tmp_path)
    t = json.loads((tmp_path / "gl_data.json").read_text())
    assert [s["file"] for s in t["clients"]["9001"]["sources"]] == ["Test Bank GL 2025.xlsx", "Test Bank GL 2026.xlsx"]
    monthly_gl(tmp_path / "Test Bank GL 2026.xlsx", months=6)                                   # the same file, sent again with a month more
    G.run(tmp_path)
    s = json.loads((tmp_path / "gl_data.json").read_text())["clients"]["9001"]["sources"]
    assert len(s) == 2 and s[1]["quality"]["months"] == 6


def test_a_file_that_is_neither_shape_is_reported_not_guessed_at(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.append(["just", "some", "text"])
    wb.save(tmp_path / "Other.xlsx")
    r = G.run(tmp_path)
    assert dict(r["left"])["Other.xlsx"].startswith("neither a monthly GL sheet")


def test_the_folder_is_a_known_input_kind():
    import rpe_env
    assert rpe_env.INPUT_KIND_DIRS["GL Data"] == "GL Data" and "GL Data" in rpe_env.NOT_SCANNED_KINDS
