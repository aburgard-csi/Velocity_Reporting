"""CSM Sheila's Lift Matrix tab (Aaron, 2026-09-25): the calculated matrix at editable rates, and the file
for Bradford saved under the deck naming convention in the client's Outputs folder."""
import json
import os
import sys

import openpyxl
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "scripts"), os.path.join(REPO, "build")]
import ars_launcher_web as W  # noqa: E402


@pytest.fixture
def lift(tmp_path, monkeypatch, odd_csv):
    """Client 9999 with the synthetic ODD, no workbook, and every folder under tmp_path."""
    out = tmp_path / "Outputs" / "Aaron Burgard"
    out.mkdir(parents=True)
    monkeypatch.setattr(W, "_odd_path", lambda cid: W.Path(odd_csv))
    monkeypatch.setattr(W, "_lift_dir", lambda: tmp_path)
    monkeypatch.setattr(W, "_lift_workbook", lambda cid: (None, None))
    monkeypatch.setattr(W, "_roster_entry", lambda cid: (cid, "Union Financial", "MM", ["ARS"]))
    monkeypatch.setattr(W.L, "csm_list_row", lambda cid: {"csm": "Aaron Burgard"})
    monkeypatch.setattr(W.L, "cycle_period", lambda: "2026.09")
    monkeypatch.setattr(W.R, "client_outputs", lambda cid, create=False: out)
    # A queued scan is recorded, not run: the tests run W._run_scan themselves, and a real background
    # scan racing that one made the suite flaky.
    monkeypatch.setattr(W, "_lm_pool", type("Pool", (), {"submit": lambda self, fn, *a: None})())
    W._lm_scans.clear()
    return out


def test_the_odd_is_read_once_and_kept_against_that_landing(lift, tmp_path):
    doc = W.lift_client_doc("9999")
    assert doc["scan_state"] in ("queued", "scanning", "ready")
    W._run_scan("9999")                              # what the background worker runs
    assert W.lift_cached_scan("9999") is not None
    doc = W.lift_client_doc("9999")
    assert doc["scan_state"] == "ready"
    # No workbook: 60 BP and 80% by default, and no NSF/OD fee is guessed.
    assert doc["rates"] == {"ic_rate": 0.006, "nsf_fee": None, "collection": 0.8}
    assert "calculated" not in doc
    # A different ODD landing is a different scan.
    data = json.loads((tmp_path / "9999.json").read_text(encoding="utf-8"))
    data["key"]["mtime"] -= 1
    (tmp_path / "9999.json").write_text(json.dumps(data), encoding="utf-8")
    assert W.lift_cached_scan("9999") is None


def test_edited_rates_are_applied_and_bad_ones_refused(lift):
    W._run_scan("9999")
    doc = W.lift_client_doc("9999", {"ic_rate": "0.0085", "nsf_fee": "35", "collection": "0.9"})
    assert doc["rates"] == {"ic_rate": 0.0085, "nsf_fee": 35.0, "collection": 0.9}
    s = doc["segments"]["6-10"]
    got = next(r for r in doc["calculated"]["segments"] if r["segment"] == "6-10")
    assert got["dda"] == round(0.0085 * s["spend"] + 35 * s["items"] * 0.9, 2)
    with pytest.raises(ValueError):
        W.lift_client_doc("9999", {"nsf_fee": "35", "collection": "80"})   # 80 is not a share


def test_the_file_downloads_only_once_approved_at_those_rates(lift, tmp_path):
    # Aaron, 2026-09-25: "when the matrix is approved it'll allow you to download the file".
    import io
    W._run_scan("9999")
    assert W.lift_approve("9999", {})[0] == 400                      # no fee yet: nothing to approve
    assert W.lift_download("9999", {"nsf_fee": "30"})[0] == 409      # not approved
    code, body = W.lift_approve("9999", {"nsf_fee": "30"})
    assert code == 200 and body["file_name"] == "9999-2026.09-ARS-Union Financial ARS Lift Matrix.xlsx"
    assert W.lift_client_doc("9999", {"nsf_fee": "30"})["approved"]["rates"]["nsf_fee"] == 30.0
    code, data, name = W.lift_download("9999", {"nsf_fee": "30"})
    assert code == 200 and name == body["file_name"]
    ws = openpyxl.load_workbook(io.BytesIO(data)).active
    assert ws["A5"].value == "NH" and ws["A18"].value == "Baseline Segment"
    # A rate changed after approval needs approving again.
    assert W.lift_download("9999", {"nsf_fee": "31"})[0] == 409
    rec = json.loads((tmp_path / "9999-2026.09-approved.json").read_text(encoding="utf-8"))
    assert rec["rates"]["nsf_fee"] == 30.0 and rec["odd"]["odd"]
    assert not list(lift.iterdir())                                  # nothing written to Outputs


def test_the_lift_endpoints_check_the_client_number(monkeypatch):
    import threading
    import http.client
    srv = W.make_server(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        for method, path, body in (("GET", "/api/lift/client?client=12;x", None),
                                   ("POST", "/api/lift/approve", {"client": "../x"}),
                                   ("POST", "/api/lift/download", {"client": "1;x"}),
                                   ("POST", "/api/lift/rescan", {"client": ""})):
            c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=10)
            c.request(method, path, body=json.dumps(body) if body else None,
                      headers={"X-Token": W.TOKEN, "Content-Type": "application/json"})
            assert c.getresponse().status == 400
            c.close()
    finally:
        srv.shutdown()


def test_an_sm_client_is_shown_but_never_scanned_or_saved(lift, monkeypatch):
    # Aaron, 2026-09-25: "Austin and Sugar River are on the SM model that doesn't use the lift matrix."
    monkeypatch.setattr(W, "_roster_entry", lambda cid: (cid, "Austin Bank", "SM", ["ARS"]))
    queued = []
    monkeypatch.setattr(W, "lift_queue_scan", lambda cid, force=False: queued.append(cid))
    assert W.lift_client_doc("1075")["scan_state"] == "sm"
    assert W.lift_approve("1075", {"nsf_fee": "30"})[0] == 400
    assert W.lift_download("1075", {"nsf_fee": "30"})[0] == 400
    assert queued == [] and not list(lift.iterdir())
