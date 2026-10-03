"""Matching normalises both sides (#245). On 1776, $10.6M of finserv
descriptors sat in the review queue against $14.2M matched, and three of
the seven largest misses were the matcher, not the dictionary: a glued
asterisk, a state code between the pattern's tokens, and the abbreviated
spellings ACH descriptors use. The legacy notebook normalised both sides
before matching; v5 did not carry that across.

    python -m pytest tests/test_matcher_normalise.py -q
"""
import pathlib
import sys

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "build" / "ars_pipeline"), str(HERE.parent / "build")]
CONFIG_DIR = HERE.parent / "build" / "ars_pipeline" / "engine" / "config"

from engine.transaction_intelligence import competition, financial_services as fs  # noqa: E402


def _cat(spec, *cores):
    t = fs.classify_strings(pd.Index(list(cores)), spec)
    return [t.loc[c, "category"] for c in cores]


def test_normalize_core_applies_the_legacy_abbreviations():
    n = fs.normalize_core
    assert n("SESLOC FEDERAL CREDIT UNION") == "SESLOC FED CU"
    assert n("SESLOC FCU") == "SESLOC FED CU"
    assert n("AMERICAN RIVIERA BANK") == "AMERICAN RIVIERA BK"
    assert n("MONTECITO BANK & TRUST") == "MONTECITO BK TRUST"
    assert n("PROGRESSIVE *INSURANCE") == "PROGRESSIVE INS"
    assert n("NATL GEN INS*RECURRING") == "NATL GEN INS RECURRING"
    assert n("FIRST NATIONAL BANK") == "FIRST NATL BK"


def test_punctuation_glued_to_a_word_no_longer_defeats_the_match():
    spec = fs.load_patterns(CONFIG_DIR)
    assert _cat(spec, "PROGRESSIVE *INSURANCE") == ["Insurance"]
    assert _cat(spec, "NATL GEN INS*RECURRING") == ["Insurance"]


def test_a_short_token_between_pattern_words_is_allowed():
    """'AAA CA INSURANCE' is AAA Insurance with a state code in it. A real
    word in the gap is a different business and must not match."""
    spec = fs.load_patterns(CONFIG_DIR)
    assert _cat(spec, "AAA CA INSURANCE - R") == ["Insurance"]
    assert _cat(spec, "AAA TOWING INSURANCE") == [None]


def test_an_abbreviation_is_part_of_the_name_not_a_gap():
    """The dictionary holds ALLY FINANCIAL and ALLY PAYMENT. 'ALLY FINANCIAL
    PAYMENT' is Ally Financial; the gap rule must not skip FIN to reach the
    shorter pattern."""
    spec = fs.load_patterns(CONFIG_DIR)
    t = fs.classify_strings(pd.Index(["ALLY FINANCIAL PAYMENT 1234"]), spec)
    assert t.iloc[0]["provider"] == "ALLY FINANCIAL"


def test_the_1776_review_queue_names_are_in_the_dictionary():
    spec = fs.load_patterns(CONFIG_DIR)
    assert _cat(spec, "BRISTOL WEST INSURANCE", "FLEXIBLE FINANCE INC.",
                "FLEX FINANCE", "US TREAS TAX PYMT") == \
        ["Insurance", "Personal Loans", "Personal Loans", "Tax & Accounting"]


def test_a_bare_category_word_is_not_published_as_a_provider():
    spec = fs.load_patterns(CONFIG_DIR)
    t = fs.classify_strings(pd.Index(["BROKERAGE", "FIDELITY BROKERAGE"]), spec)
    assert t.loc["BROKERAGE", "category"] == "Investment/Brokerage"
    assert t.loc["BROKERAGE", "provider"] == fs.UNNAMED_PROVIDER
    assert t.loc["FIDELITY BROKERAGE", "provider"] == "FIDELITY BROKERAGE"


def test_false_positives_survive_normalisation():
    spec = fs.load_patterns(CONFIG_DIR)
    assert _cat(spec, "AAA AUTO PARTS", "CHASE CENTER") == [None, None]
