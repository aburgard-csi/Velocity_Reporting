# Ported from ARS v5 02-Scripts/tests/test_competition_part2.py at a491b5c (James Gilmore); logic unchanged.
"""The two competition analyses the audit listed as lost (#245, Part 2 item 6):
share-of-wallet tiers per account, and the threat score with a growth term.

    python -m pytest tests/test_competition_part2.py -q
"""
import pathlib
import sys

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
CONFIG_DIR = __import__("ti.dictionaries", fromlist=["folder"]).folder()

from ti.transaction_intelligence import competition, competition_report, financial_services  # noqa: E402
from test_ti_competition import ANCHOR, CLIENT_CFG, make_frame, make_lenses  # noqa: E402


def _run(tmp_path):
    df, lenses = make_frame(), make_lenses()
    spec = competition.load_config(CONFIG_DIR, CLIENT_CFG)
    fin_rows = financial_services.classify_rows(df, financial_services.load_patterns(CONFIG_DIR, CLIENT_CFG))
    m, _ = competition.compute(df, lenses, spec, fin_rows, ANCHOR, tmp_path, lambda *_: None,
                               account_filter=lenses.ids("personal"), key_prefix="comp_",
                               base_label="personal accounts")
    return m


def test_wallet_tiers_partition_the_accounts_with_a_competitor(tmp_path):
    m = _run(tmp_path)
    tiers = m["comp_wallet_tiers"]
    assert [r[0] for r in tiers] == ["Heavy (over 50%)", "Balanced (25-50%)", "CU-focused (under 25%)"]
    assert sum(r[1] for r in tiers) == m["comp_with_competitor"]
    assert m["comp_wallet_tiers_columns"] == ["tier", "accounts", "pct_of_with_competitor",
                                               "competitor_dollars", "mean_share_pct"]
    # A1 sends every transfer dollar to Chase and Capital One: heavy
    assert tiers[0][1] >= 1


def test_threat_score_ranks_institutions_on_penetration_spend_and_growth(tmp_path):
    m = _run(tmp_path)
    threat = m["comp_threat"]
    assert m["comp_threat_columns"] == ["institution", "score", "accounts", "dollars", "growth_pct"]
    scores = [r[1] for r in threat]
    assert scores == sorted(scores, reverse=True) and all(0 <= s <= 100 for s in scores)
    assert "Capital One" in {r[0] for r in threat}
    text = "\n".join(competition_report.lines(m, {}))
    assert "SHARE OF WALLET" in text and "THREAT SCORE" in text
