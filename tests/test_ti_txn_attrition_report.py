# Ported from ARS v5 02-Scripts/tests/test_txn_attrition_report.py at a491b5c (James Gilmore); logic unchanged.
"""Three attrition analyses the transaction run computes and never prints (#245)."""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.transaction_intelligence import sections_report as S   # noqa: E402

CURVE = {"leak_curve": [[-6, 210, 40.0, 8400, 12.0], [-3, 205, 65.0, 13325, 18.5],
                        [-1, 200, 91.0, 18200, 26.0]],
         "leak_curve_columns": ["offset_months", "n", "mean_competitor_dollars", "total",
                                "pct_with_any"],
         "leak_control": [[-6, 1280, 39.0, 49920, 11.8], [-3, 1280, 40.0, 51200, 12.0],
                          [-1, 1280, 41.0, 52480, 12.1]],
         "leak_divergence_month": 3,
         "leak_control_basis": "still-open accounts over the same calendar months"}
STRESS = {"stress_txn_base": "Open at anchor, transacting join", "stress_txn_n": 900,
          "stress_txn_by_count": [[0, 500, 55.6, 4_000_000], [1, 300, 33.3, 5_000_000],
                                  [2, 100, 11.1, 2_000_000]],
          "stress_txn_2plus_n": 100, "stress_txn_2plus_pct": 11.1,
          "stress_txn_2plus_deposits": 2_000_000, "stress_txn_2plus_competitor_dollars": 150_000,
          "stress_txn_available": ["Spend health declining", "Banking elsewhere"],
          "stress_txn_skipped": []}
HOT = {"hot_by_branch": [["Lompoc", 900, 60, 7.1, 800, 18.0, 640, "Chase"]],
       "hot_by_branch_columns": ["branch", "at_risk", "closed", "closure_per_account_year",
                                 "transacting_accounts", "leak_pct", "leak_dollars_per_account",
                                 "top_institution"],
       "hot_rank_correlation": 0.42, "hot_rank_correlation_n": 9,
       "hot_both_above_median": ["Lompoc"]}


def test_pre_closure_curve_prints_with_its_control_and_divergence():
    text = "\n".join(S.lines(CURVE))
    assert "COMPETITOR SPEND BEFORE CLOSURE" in text
    assert "3 month" in text and "91" in text and "same calendar months" in text


def test_cross_source_stressors_print():
    text = "\n".join(S.lines(STRESS))
    assert "STRESSORS ACROSS BOTH FILES" in text
    assert "Banking elsewhere" in text and "150,000" in text


def test_branch_hotspots_print():
    text = "\n".join(S.lines(HOT))
    assert "BRANCH HOTSPOTS" in text and "Lompoc" in text and "0.42" in text
