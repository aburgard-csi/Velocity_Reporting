"""The ILS cards on Sheila's client page (scripts/ils_ui.py, scripts/ils_runs.py; James Gilmore, 2026-10-28).

Pinned: the cards are spliced into the client page beside the other presentations, with an ILS Review card
marked Coming soon, and the splice refuses a page whose anchors moved; a client with an ILS folder is in
Sheila's list; step 1 returns the field summary and computes nothing; step 2 is refused until the required
codes are typed; the codes a run was confirmed with are kept for the next one; reveal opens nothing outside
Build Artifacts/ils.
"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "scripts"), str(REPO / "build")]
import ils_runs  # noqa: E402
import ils_ui  # noqa: E402

KICKOFF = ("AcctNo,Items,Paid Annualized,Returned Annualized,ODCode,Business,OPStatus\n"
           "1,5,4,1,0,P,O\n2,0,0,0,0,B,O\n3,3,2,1,0,P,C\n")


@pytest.fixture
def root(tmp_path, monkeypatch):
    for d in ("Inputs", "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir()
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    d = tmp_path / "Inputs" / "ILS Kickoff" / "1840"
    d.mkdir(parents=True)
    (d / "1840_OneTimeData_20260915.csv").write_text(KICKOFF, encoding="utf-8")
    (tmp_path / "Inputs" / "ILS PGL" / "1737").mkdir(parents=True)
    return tmp_path


def test_the_cards_sit_on_the_client_page_with_ils_review_coming_soon():
    import ars_launcher_web as W
    assert '${companionPanel(s)}<div id="ilscards"></div>${aside}' in W.PAGE
    assert "ilsCards(s.client);" in W.PAGE
    assert "ILS Review" in W.PAGE and "Coming soon" in W.PAGE
    assert 'id="tab-ils"' not in W.PAGE          # the cards are on the client page, not a tab


def test_a_moved_anchor_refuses_the_splice():
    with pytest.raises(RuntimeError, match="ILS cards could not be added"):
        ils_ui.install("<style></style><script></script>")


def test_a_client_with_an_ils_folder_is_listed(root):
    assert ils_runs.landed_clients() == {"1737", "1840"}


def test_the_client_doc_says_what_has_landed(root):
    d = ils_runs.client_doc("1840")
    k, p = d["kinds"]["kickoff"], d["kinds"]["pgl"]
    assert k["extract"] == "1840_OneTimeData_20260915.csv" and k["period"] == "2026-09"
    assert p["exists"] is False and p["extract"] is None
    assert ils_runs.client_doc("1737")["kinds"]["pgl"]["exists"] is True


def test_step_two_needs_the_required_codes(root):
    code, doc = ils_runs.start({"kind": "kickoff", "client": "1840", "codes": {"personal_code": "P"}})
    assert code == 400 and "business_code" in doc["error"]
    assert ils_runs.start({"kind": "ils", "client": "1840"})[0] == 400
    assert ils_runs.start({"kind": "kickoff", "client": "18x0"})[0] == 400
    code, doc = ils_runs.start({"kind": "kickoff", "client": "1840", "period": "Sep 2026",
                                "codes": {"personal_code": "P", "business_code": "B", "open_code": "O",
                                          "eligible_stat_codes": "0"}})
    assert code == 400 and "YYYY-MM" in doc["error"]


def test_step_one_is_the_field_summary_and_computes_nothing(root):
    j = ils_runs.IlsJob("kickoff", "1840", {"analysis": "kickoff", "client": "1840", "period": "2026-09"})
    j.run()
    out = j.to_json()
    assert out["ok"] and out["needs_codes"] and out["step"] == 1
    text = "\n".join(out["lines"])
    assert "step 1 of 2" in text and "Business Flag" in text
    assert not (root / "Build Artifacts" / "ils" / "kickoff" / "1840").exists()


def test_the_confirmed_codes_are_kept_for_the_next_run(root):
    codes = {"personal_code": "P", "business_code": "B", "open_code": "O", "eligible_stat_codes": "0"}
    ils_runs.save_codes("kickoff", "1840", codes, ils_runs._extract("kickoff", "1840"), {"period": "2026-09"})
    saved = ils_runs.client_doc("1840")["kinds"]["kickoff"]["saved"]
    assert saved["codes"] == codes and saved["extract"] == "1840_OneTimeData_20260915.csv"
    assert json.loads((root / "Build Artifacts" / "ils" / "kickoff" / "1840" / "confirmed_codes.json")
                      .read_text(encoding="utf-8"))["options"] == {"period": "2026-09"}


def test_reveal_opens_nothing_outside_the_ils_outputs(root):
    outside = root / "Inputs" / "ILS Kickoff" / "1840" / "1840_OneTimeData_20260915.csv"
    assert ils_runs.reveal(str(outside))[0] == 403
    assert ils_runs.reveal(str(root / "Build Artifacts" / "ils" / "nope.pptx"))[0] == 403


def test_the_deck_inputs_are_saved_per_client_and_go_to_the_build(root):
    code, doc = ils_runs.save_inputs({"client": "1737", "key_dates": "Matrix approval | 7/28/2026\n\nGo live | 9/1/2026",
                                      "program": {"od_fee": "$27", "nsf_fee": "$15"},
                                      "data_notes": "Codes 2 and 3 need descriptions.",
                                      "od_descriptions": "3 = Bankruptcy\nno separator here"})
    assert code == 200
    saved = ils_runs.client_doc("1737")["kinds"]["pgl"]["inputs"]
    assert saved["key_dates"] == [["Matrix approval", "7/28/2026"], ["Go live", "9/1/2026"]]
    assert saved["program"]["od_fee"] == "$27" and saved["od_descriptions"] == {"3": "Bankruptcy"}
    assert ils_runs.save_inputs({"client": "17x7"})[0] == 400


def test_the_page_script_parses(tmp_path):
    """A line break written into a JS string literal broke the whole page once (2026-10-28)."""
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    import ars_launcher_web as W
    js = W.PAGE[W.PAGE.rindex("<script>") + 8:W.PAGE.rindex("</script>")]
    f = tmp_path / "page.js"
    f.write_text(js, encoding="utf-8")
    r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-600:]


def test_a_finished_deck_is_delivered_to_the_csms_ils_folder_and_the_ars_readers_never_see_it(root, monkeypatch):
    # James Gilmore, 2026-10-29: "the decks should be going in the respective output folders"
    import ils_job
    import ars_launcher as L
    import rpe_env as R
    monkeypatch.setattr(R, "client_csm", lambda cid: "James Gilmore")
    run_dir = root / "Build Artifacts" / "ils" / "PGL" / "1737" / "20261029"
    run_dir.mkdir(parents=True)
    built = run_dir / "1737 ILS Program Analysis - PGL Review 20261029.pptx"
    built.write_bytes(b"first")
    dest = ils_job.deliver("pgl", "1737", built, "2026.10", "Texas National Bank")
    assert dest == (root / "Outputs" / "James Gilmore" / "ILS"
                    / "1737-2026.10-ILS-PGL-Texas National Bank ILS Pre-Go-Live Review.pptx")
    assert built.exists() and dest.read_bytes() == b"first"            # copied: the run keeps its own
    built.write_bytes(b"second")
    ils_job.deliver("pgl", "1737", built, "2026.10", "Texas National Bank")
    archived = list((dest.parent / "_Archive").glob("*(superseded *).pptx"))
    assert dest.read_bytes() == b"second" and [p.read_bytes() for p in archived] == [b"first"]   # never deleted
    # the ARS rebuild check, the In Outputs chip and deck readiness read <id>-<period>-*.pptx in the CSM folder
    assert R.output_decks("1737-2026.10-*.pptx") == [] and L.decks_in_outputs("1737", "2026.10") == []
    last = ils_runs.last_output("pgl", "1737")
    assert last["deck"] == str(dest) and last["folder"] == str(run_dir)
    monkeypatch.setattr(ils_runs.subprocess, "Popen", lambda *a, **k: None)
    assert ils_runs.reveal(str(dest))[0] == 200                         # the card's "open the deck"
    assert ils_runs.reveal(str(root / "Outputs" / "James Gilmore" / "notes.txt"))[0] == 403


def test_the_cards_fold_under_one_line_opened_only_when_a_kind_has_something():
    """The pre-go-live and kickoff reports are made once per client, so the cards only said "No extract yet"
    for almost every client (Aaron, 2026-10-29). They sit under a dropdown, closed unless a kind has an
    extract, a run in progress or a deck built, and a CSM's open state survives the status redraw."""
    import ars_launcher_web as W
    draw = W.PAGE[W.PAGE.index("function ilsDraw()"):W.PAGE.index("// The deck's CSM inputs")]
    assert '<details class="ilsfold"${open ? " open" : ""}>' in draw
    assert "const open = was ? was.open : ilsActive();" in draw
    active = W.PAGE[W.PAGE.index("function ilsActive()"):W.PAGE.index("function ilsDraw()")]
    assert "c.extract || c.last || (c.job && !c.job.done)" in active
    assert "one-time reports, not set up for this client" in W.PAGE
    assert "details.ilsfold>summary" in W.PAGE
