"""scripts/analysis_summary.py prints what the engine saw for one client, from the evidence
folder, without writing anything (2026-09-29: the work PC could not paste multi-line checks
into a window with a build running)."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import analysis_summary as S  # noqa: E402


def test_the_summary_names_the_join_the_warnings_and_the_reconciliation(tmp_path):
    f = tmp_path / "2026.09" / "1441"; f.mkdir(parents=True)
    (f / "txn_metrics.json").write_text(json.dumps({
        "txn_files_read": 11, "txn_rows": 10928371, "txn_odd_join_key": " Acct Number",
        "txn_odd_match_pct": 97.4, "txn_odd_join_candidates": [["Acct ID", 0], [" Acct Number", 31000]],
        "fin_leaking_pct": 12.5, "fin_by_category": [["x", 1]], "warnings": ["one warning"]}))
    (f / "metrics.json").write_text(json.dumps({"warnings": [], "gt_state": "deferring", "gt_deferred_balance": 3000.0}))
    (f / "report.md").write_text("# r\nall good\nPOSSIBLE DATA ISSUE: reg e wording\n")
    log = tmp_path / "build.log"
    log.write_text("stuff\nanalysis engine (RPE_ANALYSIS)\n  n_eligible   engine 100  deck 100  ok vs funnel\n")
    lines = S.summarise(f, log)
    text = "\n".join(lines)
    assert "txn_odd_match_pct" in text and "97.4" in text and "31000" in text
    assert "fin_leaking_pct" in text and "fin_by_category" not in text
    assert "one warning" in text and "POSSIBLE DATA ISSUE" in text and "ok vs funnel" in text
    assert "gt_deferred_balance" in text and "3000.0" in text


def test_a_missing_folder_is_stated(tmp_path):
    assert "NOT FOUND" in "\n".join(S.summarise(tmp_path / "nope"))
