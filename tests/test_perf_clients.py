"""perf_clients — who the performance page lists and which programs it shows.

  * Current = filed reports this cycle on the reports share; the newest non-empty month.
  * An unreadable share is None, never an empty answer, and the saved list stands in.
  * Programs for a non-roster client are inferred, and a DCO alone infers nothing.
"""
import json

import openpyxl

import perf_clients as C


def _quiet(*_a):
    pass


def _share(tmp_path, files):
    root = tmp_path / "share"
    for rel in files:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")
    return str(root)


def test_report_names_give_id_kind_and_name():
    assert C.parse_report_name("1537-2026.09-Brooks Bank-DCO v2_2.xlsx") == ("1537", "DCO", "Brooks Bank")
    assert C.parse_report_name("1204-2026.09-First State Bank-MI-Workbook_v2_1_0.xlsx") == \
        ("1204", "WORKBOOK", "First State Bank-MI")
    assert C.parse_report_name("1075-2026.09-MRPC-Austin-MRPCPM_Analysis_v10.xlsx") == ("1075", "MRPCPM", "Austin")
    assert C.parse_report_name("1075-2026.08-Austin-Invitation Checking Workbook v1.7.1.xlsx")[1] == "ICS WORKBOOK"
    assert C.parse_report_name("~$1537-2026.09-Brooks Bank-DCO.xlsx") is None
    assert C.parse_report_name("readme.txt") is None


def test_current_clients_are_the_newest_month_with_files(tmp_path):
    root = _share(tmp_path, ["2026.08/Aaron Burgard/1204-2026.08-First State Bank-MI-DCO.xlsx",
                             "2026.09/Daniel Wood/1095-2026.09-Landmark Bank-DCO.xlsx",
                             "2026.09/Daniel Wood/1095-2026.09-Landmark Bank-Workbook_v2.xlsx",
                             "2026.10/Aaron Burgard/1038-2026.10-Sugar River-DCO.xlsx"])   # after the cycle
    folder, got = C.share_reports(root, "2026.09", log=_quiet)
    assert folder == "2026.09"
    assert got == {"1095": {"csm": "Daniel Wood", "name": "Landmark Bank", "kinds": ["DCO", "WORKBOOK"]}}


def test_an_empty_new_month_falls_back_to_the_last_month_with_files(tmp_path):
    root = _share(tmp_path, ["2026.08/Aaron Burgard/1204-2026.08-First State Bank-MI-DCO.xlsx"])
    (tmp_path / "share" / "2026.09" / "Aaron Burgard").mkdir(parents=True)
    folder, got = C.share_reports(root, "2026.09", log=_quiet)
    assert folder == "2026.08" and list(got) == ["1204"]


def test_an_unreachable_share_uses_the_saved_list(tmp_path):
    root = _share(tmp_path, ["2026.09/Aaron Burgard/1204-2026.09-First State Bank-MI-DCO.xlsx"])
    work = tmp_path / "work"
    work.mkdir()
    live, folder = C.current_clients("2026.09", work, root, log=_quiet)
    assert list(live) == ["1204"] and folder == "2026.09"
    assert json.loads((work / "current.json").read_text())["clients"]["1204"]["name"] == "First State Bank-MI"
    said = []
    saved, folder = C.current_clients("2026.09", work, str(tmp_path / "offline"), log=said.append)
    assert saved == live and folder == "2026.09"
    assert any("not reachable" in s for s in said)
    assert C.share_reports(str(tmp_path / "offline"), "2026.09", log=_quiet) is None


def test_programs_are_inferred_and_a_dco_alone_implies_none():
    assert C.infer_programs("1095", ["DCO"]) == []
    assert C.infer_programs("1095", ["DCO", "WORKBOOK"]) == ["ARS"]
    assert C.infer_programs("1095", ["DCO", "MRPCPM"], cp_ids={"1095"}) == ["MRPC", "CP"]
    assert C.infer_programs("1095", [], mrpc_tabs={"1095"}, has_ics_sheet=True) == ["ICS", "MRPC"]


def _workbook(tmp_path, name, header):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Executive Financials MM"
    ws["A1"] = "Account Revenue Solution Financial Performance"
    ws["A2"] = header
    p = tmp_path / name
    wb.save(p)
    return str(p)


def test_path_is_detected_the_way_clients_md_was_set(tmp_path):
    assert C.detect_path(_workbook(tmp_path, "mm.xlsx", "First State Bank-MI")) == "MM"
    assert C.detect_path(_workbook(tmp_path, "sm.xlsx", "Bank Name")) == "SM"
    assert C.detect_path(str(tmp_path / "missing.xlsx")) is None
