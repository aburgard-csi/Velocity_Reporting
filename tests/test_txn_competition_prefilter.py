"""Competition candidates are found on NORMALISED text, like the patterns (v5 competition.py:160).

The matcher normalises both sides (BANK -> BK, CREDIT UNION -> CU ...). The combined prefilter in
competition._classify used to search the RAW descriptor against normalised patterns, so
"BANK OF AMERICA ..." never reached the classifier. On 1441 that read $548M to named competitors
where a direct count of the same files gave $753M.

    python -m pytest tests/test_txn_competition_prefilter.py -q
"""
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build" / "ars_pipeline"), str(REPO / "build")]
from engine.transaction_intelligence import competition  # noqa: E402

CONFIG_DIR = REPO / "build" / "ars_pipeline" / "engine" / "config"


def _institutions(descriptors):
    spec = competition.load_config(CONFIG_DIR, {})
    table = competition._classify(pd.Index(descriptors), spec)
    return table["category"].to_dict()


def test_a_descriptor_spelled_out_reaches_the_classifier():
    got = _institutions(["BANK OF AMERICA ONLINE PMT", "CAPITAL ONE CREDIT CARD PAYMENT",
                         "FIRST NATIONAL BANK TRANSFER"])
    assert got["BANK OF AMERICA ONLINE PMT"] == "Bank of America", got
    assert got["CAPITAL ONE CREDIT CARD PAYMENT"] == "Capital One", got


def test_an_unrelated_descriptor_stays_unmatched():
    got = _institutions(["CHUGACH ELECTRIC BILL PAY", "SAFEWAY STORE 1234"])
    assert all(pd.isna(v) for v in got.values()), got


def test_the_review_queue_filter_normalises_too():
    """The review queue looks for bank-looking names no institution claimed; its token regex is
    normalised, so it must search normalised text as well."""
    src = (REPO / "build" / "ars_pipeline" / "engine" / "transaction_intelligence"
           / "competition.py").read_text(encoding="utf-8")
    assert "rx.search(normalize_core(s))" in src
    assert "irx.search(normalize_core(s))" in src
