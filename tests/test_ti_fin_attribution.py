# Ported from ARS v5 02-Scripts/tests/test_fin_attribution.py at a491b5c (James Gilmore); logic unchanged.
"""Attribution: a named lender must beat a generic loan descriptor.

    python -m pytest tests/test_fin_attribution.py -q

classify_strings picked the LONGEST matched text, and the catch-all
"Other Loans (lender unknown)" holds descriptors longer than most lender
names -- LOAN PAYMENT (12), LOAN PAYMT (10), LOAN PMT (8) against AVANT (5).
So five of sixteen real descriptions filed as unknown, and because `provider`
is the matched text, the generic string then propagated into
fin_top_providers where a lender name belongs. On 1776 that read as Personal
Loans at 2 accounts / $92 while "Other Loans (lender unknown)" was the
third-largest category with LOAN PMT and LOAN PAYMT as its top "providers".

Length was standing in for specificity. It is not the same thing.
"""
import pathlib
import sys

import pandas as pd
import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
CONFIG_DIR = __import__("ti.dictionaries", fromlist=["folder"]).folder()

from ti.transaction_intelligence import competition, financial_services  # noqa: E402

CATCH_ALL = "Other Loans (lender unknown)"


@pytest.fixture(scope="module")
def spec():
    return financial_services.load_patterns(CONFIG_DIR, {})


def _row(spec, core):
    return financial_services.classify_strings(pd.Index([core]), spec).loc[core]


@pytest.mark.parametrize("core,category,provider", [
    ("AVANT LOAN PAYMT", "Personal Loans", "AVANT"),
    ("OPORTUN LOAN PYMT", "Personal Loans", "OPORTUN"),
    ("ACHIEVE LOAN PMT", "Personal Loans", "ACHIEVE"),
])
def test_named_lender_beats_the_generic_descriptor(spec, core, category, provider):
    got = _row(spec, core)
    assert got["category"] == category, f"{core} filed as {got['category']}"
    assert got["provider"] == provider


@pytest.mark.parametrize("core,provider", [
    ("SCHWAB LOAN SERV", "SCHWAB"),
    ("ACORNS LOAN PMT", "ACORNS"),
])
def test_the_provider_is_the_institution_not_the_generic_string(spec, core, provider):
    """These two land outside Personal Loans -- Schwab and Acorns are
    configured as brokerages -- but the provider must still name the
    institution. A provider column reading LOAN SERV is the defect."""
    got = _row(spec, core)
    assert got["provider"] == provider
    assert got["category"] != CATCH_ALL


def test_a_descriptor_with_no_lender_still_reaches_the_catch_all(spec):
    """The catch-all is real and stays reachable: the fix changes which
    string wins, not which categories exist."""
    got = _row(spec, "ACH LOAN PMT 8842")
    assert got["category"] == CATCH_ALL


def test_longest_match_still_decides_between_two_named_categories(spec):
    """Specificity only outranks length across the fallback boundary. Among
    named categories the longer, more specific pattern still wins."""
    got = _row(spec, "AMERICAN EXPRESS BUSINESS LOAN")
    assert got["category"] == "Business Loans"


def test_competition_is_untouched_by_the_fallback_rule(spec):
    """classify_strings is shared with competition. No competitor spec marks
    a category fallback, so every competitor result must be unchanged."""
    cspec = competition._as_category_spec(
        competition.load_config(CONFIG_DIR, {}))
    assert not any(c.get("fallback") for c in cspec["categories"].values())
    cores = pd.Index(["AVANT PERSONAL LOAN", "NAVY FCU TRANSFER",
                      "CHASE CREDIT CRD AUTOPAY", "SOFI BANK DEPOSIT"])
    got = financial_services.classify_strings(cores, cspec)
    assert got.loc["NAVY FCU TRANSFER", "category"] == "Navy Federal"
    assert got.loc["CHASE CREDIT CRD AUTOPAY", "category"] == "Chase"
    assert got.loc["SOFI BANK DEPOSIT", "category"] == "SoFi"
