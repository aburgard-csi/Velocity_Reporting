"""CSM Sheila's Data Issues tab and code-sheet links (Aaron, 2026-09-25): "build a new tab into Sheila with the data
issues identified for each client" and "create a link on the individual client pages that links to the code sheet
saved in the inputs folder"."""
import json
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "scripts"), os.path.join(REPO, "build")]
import ars_launcher_web as W  # noqa: E402


@pytest.fixture
def root(tmp_path, monkeypatch):
    ba, inputs = tmp_path / "Build Artifacts", tmp_path / "Inputs"
    (ba / "issue_pages").mkdir(parents=True)
    (ba / "perf_dashboard").mkdir(parents=True)
    (inputs / "Code Sheets").mkdir(parents=True)
    monkeypatch.setattr(W.R, "build_artifacts", lambda: ba)
    monkeypatch.setattr(W.R, "inputs", lambda: inputs)
    W._issues_cache.update(key=None, doc=None)
    W._code_sheets.update(key=None, map={})
    (ba / "issue_pages" / "gaps.json").write_text(json.dumps({
        "summary": {"generated": "2026-09-21 13:55"},
        "clients": [{"id": "1453", "name": "Connex CU", "csm": "James Gilmore"},
                    {"id": "1075", "name": "Austin Bank", "csm": "Aaron Burgard"}],
        "issues": [{"id": "1453", "name": "Connex CU", "csm": "James Gilmore", "program": "ARS", "severity": "warning",
                    "issue": "Workbook is flagged", "fix": "Check the Lift Matrix"},
                   {"id": "1453", "name": "Connex CU", "csm": "James Gilmore", "program": "MRPC", "severity": "blocker",
                    "issue": "No VIP MRPC client sheet", "fix": "Pull the sheet"}]}), encoding="utf-8")
    (ba / "perf_dashboard" / "dataset.json").write_text(json.dumps({
        "generated": "2026-09-25 10:14",
        "clients": [{"id": "1453", "name": "Connex CU", "csm": "James Gilmore",
                     "actions": {"lift_matrix": {"flag": "LM EXPIRED", "workbook": "1453-2026.09-Connex CU-Workbook.xlsx"},
                                 "codes": [{"label": "Product Codes not mapped", "values": [{"value": "PM", "accounts": 1, "open": 0}],
                                            "no_table": False, "eligibility": True}], "unchecked": []}},
                    {"id": "1075", "name": "Austin Bank", "csm": "Aaron Burgard", "actions": None}]}), encoding="utf-8")
    cs = inputs / "Code Sheets"
    (cs / "1453-Connex CU-260801_090000-ARS Client Codes v1_4.xls").write_bytes(b"old")
    (cs / "1453-Connex CU-260915_104629-ARS Client Codes v1_4.xls").write_bytes(b"new")
    (cs / "~$1453-Connex CU-260915_104629-ARS Client Codes v1_4.xls").write_bytes(b"lock")
    return tmp_path


def test_each_clients_issues_come_from_both_sources_with_their_dates(root):
    d = W.issues_doc()
    assert d["sources"] == {"issue_pages": "2026-09-21 13:55", "dashboard": "2026-09-25 10:14"}
    c = {e["id"]: e for e in d["clients"]}
    connex = c["1453"]
    assert [i["severity"] for i in connex["issues"]] == ["blocker", "warning"]     # blockers first
    assert connex["lift_matrix"]["flag"] == "LM EXPIRED" and connex["codes"][0]["label"] == "Product Codes not mapped"
    assert connex["count"] == 4
    assert c["1075"]["count"] == 0 and c["1075"]["code_sheet"] is None


def test_the_odd_pages_own_findings_reach_sheila(root):
    """2026-10-02: the ODD and Workbook Issues page's scans (Personal/Business flags, Mail Flags, the trial run,
    the Lift Matrix date window) were on the page only; Sheila's Data Issues tab never saw them."""
    (root / "Build Artifacts" / "issue_pages" / "odd_findings.json").write_text(json.dumps({
        "period": "2026.10", "generated": "2026-10-02 07:07",
        "findings": [
            {"id": "1075", "name": "Austin Bank", "csm": "Aaron Burgard", "program": "ARS", "severity": "decision",
             "issue": "Product codes with no Personal/Business flag: 65 of 19,933 accounts", "fix": "Correct the code sheet",
             "src": "business_flags"},
            {"id": "1453", "name": "Connex CU", "csm": "James Gilmore", "program": "ARS", "severity": "blocker",
             "issue": "Lift Matrix expired: window Jul 2025 - Jun 2026", "fix": "New Lift Matrix", "src": "lift_window"},
            {"id": "1802", "name": "New Client", "csm": "Daniel Wood", "program": "ARS", "severity": "gap",
             "issue": "Malformed or incomplete ODD extract: card months missing", "fix": "Data team", "src": "odd_extract"}]}),
        encoding="utf-8")
    c = {e["id"]: e for e in W.issues_doc()["clients"]}
    assert c["1075"]["count"] == 1 and c["1075"]["issues"][0]["issue"].startswith("Product codes with no")
    assert c["1453"]["count"] == 4                     # the dashboard's Lift Matrix flag already covers it
    assert c["1802"]["csm"] == "Daniel Wood" and c["1802"]["issues"][0]["severity"] == "gap"


def test_odd_findings_keep_only_what_gaps_json_does_not_carry():
    sys.path.insert(0, os.path.join(REPO, "scripts", "issue_pages"))
    import common as IC
    cats = {"prodflag": ("Product codes with no Personal/Business flag", "map", "Fix the code sheet"),
            "lm": ("Lift Matrix expired", "block", "New Lift Matrix")}
    doc = IC.odd_findings([{"id": "1075", "name": "Austin", "csm": "Aaron", "cat": "lm", "detail": "x", "src": "gaps"},
                           {"id": "1204", "name": "FSB", "csm": "Aaron", "cat": "prodflag", "detail": "65 accounts",
                            "src": "business_flags"}], cats, "2026.10", "2026-10-02 07:07")
    assert [f["id"] for f in doc["findings"]] == ["1204"]
    assert doc["findings"][0] == {"id": "1204", "name": "FSB", "csm": "Aaron", "program": "ARS", "severity": "decision",
                                  "category": "Product codes with no Personal/Business flag",
                                  "issue": "Product codes with no Personal/Business flag: 65 accounts",
                                  "fix": "Fix the code sheet", "src": "business_flags"}


def test_the_newest_code_sheet_is_linked_and_a_lock_file_never_is(root):
    assert W.issues_doc()["clients"][-1]["code_sheet"] == "1453-Connex CU-260915_104629-ARS Client Codes v1_4.xls"
    assert W.code_sheet("1453").name.startswith("1453-Connex CU-260915")


def test_a_code_sheet_opens_only_by_client_number(root, monkeypatch):
    opened = []
    monkeypatch.setattr(W.os, "startfile", lambda p: opened.append(("open", p)), raising=False)
    monkeypatch.setattr(W.subprocess, "Popen", lambda args, **kw: opened.append(("reveal", args[-1])))
    assert W.open_code_sheet("1453", "open")[0] == 200
    assert W.open_code_sheet("1453", "reveal")[0] == 200
    assert all(str(root / "Inputs" / "Code Sheets") in p and "260915" in p for _, p in opened)
    assert W.open_code_sheet("1075", "open")[0] == 404


def test_the_code_sheet_endpoint_checks_the_client_number(root):
    import http.client
    import threading
    srv = W.make_server(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        for body in ({"client": "..\\x"}, {"client": ""}):
            c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=10)
            c.request("POST", "/api/code-sheet", body=json.dumps(body),
                      headers={"X-Token": W.TOKEN, "Content-Type": "application/json"})
            assert c.getresponse().status == 400
            c.close()
        c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=10)
        c.request("GET", "/api/issues", headers={"X-Token": W.TOKEN})
        r = c.getresponse()
        assert r.status == 200 and len(json.loads(r.read())["clients"]) == 2
        c.close()
    finally:
        srv.shutdown()


def test_a_marked_item_stays_complete_until_a_new_workbook_arrives(root, monkeypatch):
    # Aaron, 2026-09-28: "They should stay marked complete until we see a new workbook for that client, and then
    # the status can be evaluated."
    wbdir = root / "Inputs" / "ARS Workbooks"
    wbdir.mkdir(parents=True)
    (wbdir / "1453-2026.08-Connex CU-Workbook_v2_1_0.xlsx").write_bytes(b"aug")
    W._wb_names.update(key=None, map={})
    W._done_cache.update(key=None, doc={})
    monkeypatch.setenv("USERNAME", "aaron.burgard")

    def connex():
        return next(e for e in W.issues_doc()["clients"] if e["id"] == "1453")
    first = connex()
    assert first["count"] == 4 and first["done_count"] == 0
    key = first["issues"][0]["key"]                                 # the MRPC blocker
    assert W.mark_issue("1453", key, True)[0] == 200
    c = connex()
    assert c["issues"][0]["done"]["by"] == "aaron.burgard" and c["count"] == 3 and c["done_count"] == 1
    assert "done" not in c["issues"][1]                             # only that item
    # the same workbook again changes nothing
    assert connex()["issues"][0].get("done")
    # a newer workbook for the client brings it back, saying when it was marked and what arrived
    (wbdir / "1453-2026.09-Connex CU-Workbook_v2_1_0.xlsx").write_bytes(b"sep")
    os.utime(wbdir, ns=(1, 1))                                      # make the folder's change visible at once
    W._wb_names.update(key=None, map={})
    c = connex()
    assert "done" not in c["issues"][0] and c["count"] == 4
    assert c["issues"][0]["reopened"]["new"] == ["1453-2026.09-Connex CU-Workbook_v2_1_0.xlsx"]
    # marking it again records the new workbook; Undo clears it
    assert W.mark_issue("1453", key, True)[0] == 200 and connex()["issues"][0].get("done")
    assert W.mark_issue("1453", key, False)[0] == 200
    c = connex()
    assert "done" not in c["issues"][0] and "reopened" not in c["issues"][0]


def test_only_a_current_item_can_be_marked(root):
    W._done_cache.update(key=None, doc={})
    assert W.mark_issue("1453", "0" * 16, True)[0] == 404
    assert W.mark_issue("9999", "0" * 16, True)[0] == 404
