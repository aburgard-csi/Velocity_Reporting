# Ported from ARS v5 02-Scripts/tests/test_fin_single_token_context.py at a491b5c (James Gilmore); logic unchanged.
"""A single-token pattern needs financial context around it.

    python -m pytest tests/test_fin_single_token_context.py -q

161 of the 863 finserv patterns are one bare token, and the only guard was a
55-entry false_positives denylist -- which by construction only catches what
somebody already noticed. Twenty realistic merchant descriptors were put
through the live matcher and seventeen came back as financial services:
MERRILL GARDENS is a senior-living chain, MARCUS THEATRES is a cinema.

A wordlist cannot separate the safe tokens from the unsafe ones: ANTHEM and
CURRENT are ordinary English, but MERRILL, MARCUS, VARO and AMICA are not,
and all six over-match. So the rule is uniform and matches the one
repair_competitors already applies on the competition side -- a lone token
is not enough on its own. It still matches when the descriptor carries
financial context, or when the token stands alone.
"""
import json
import pathlib
import sys

import pandas as pd
import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.transaction_intelligence import financial_services as fs  # noqa: E402

from ti import dictionaries  # noqa: E402
CONFIG = dictionaries.folder()   # RPE: the dictionaries live with the code


@pytest.fixture(scope="module")
def spec():
    return fs.load_patterns(CONFIG)


def _category(spec, descriptor):
    return fs.classify_strings(pd.Index([descriptor]), spec).loc[descriptor, "category"]


# ---------------------------------------------------------------------------
# must NOT match -- ordinary businesses that happen to carry the token
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("descriptor", [
    "MERRILL GARDENS",             # senior living
    "MARCUS THEATRES",             # cinemas
    "REGIONS RESTAURANT",
    "ANTHEM SPORTS BAR",
    "AMICA MUTUAL PIZZA",
    "KRAKEN BURGERS",
    "GEMINI PIZZA",
    "UPLIFT DESK CO",
    "AFFIRM WELLNESS SPA",
    "DAVE AND BUSTERS",
    "STEP UP FITNESS",
    "ALBERT LEA SENIOR CTR",
    "CHIME BELL PLANTATION",
    "VARO FARMS",
    "SPLITIT CAFE",
    "PERPAY LAUNDRY",
])
def test_an_ordinary_business_is_not_a_financial_service(spec, descriptor):
    got = _category(spec, descriptor)
    assert pd.isna(got), f"{descriptor} reads as {got!r}"


# ---------------------------------------------------------------------------
# must STILL match -- the real thing, in the shapes a statement prints
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("descriptor,category", [
    ("AFFIRM PAYMENT", "Buy Now Pay Later"),
    ("CHIME TRANSFER", "Fintech / Neobanks"),
    ("DAVE INC", "Fintech / Neobanks"),
    ("PROSPER LOAN PMT", "Personal Loans"),
    ("UPSTART LOAN PAYMENT", "Personal Loans"),
    ("KRAKEN CRYPTO PURCHASE", "Crypto/Digital Assets"),
    ("ANTHEM INSURANCE PREMIUM", "Insurance"),
    ("MERRILL LYNCH", "Investment/Brokerage"),
    ("VANGUARD FUNDS", "Investment/Brokerage"),
    ("FIDELITY INVESTMENTS", "Investment/Brokerage"),
])
def test_the_real_provider_still_matches(spec, descriptor, category):
    assert _category(spec, descriptor) == category


def test_a_bare_token_alone_is_still_a_match(spec):
    """A descriptor that is only the provider's name has no context to carry."""
    assert _category(spec, "COINBASE") == "Crypto/Digital Assets"
    assert _category(spec, "CHIME") == "Fintech / Neobanks"


def test_a_corporate_tail_does_not_count_as_other_words(spec):
    assert _category(spec, "COINBASE INC") == "Crypto/Digital Assets"


@pytest.mark.parametrize("descriptor,category", [
    ("CENLAR FSB", "Mortgage/HELOC"),
    ("ROCKET MORTGAGE", "Mortgage/HELOC"),
    ("AMICA MUTUAL INS", "Insurance"),
    ("SCHWAB ADVISORS", "Investment/Brokerage"),
    ("VANGUARD IRA", "Investment/Brokerage"),
    ("PENNYMAC LOAN SERVICES", "Mortgage/HELOC"),
])
def test_depository_and_product_abbreviations_count_as_context(spec, descriptor, category):
    """FSB, IRA, ADVISORS and the rest are financial context as surely as
    PAYMENT is. CENLAR FSB was the one false negative the first draft of the
    context list produced."""
    assert _category(spec, descriptor) == category


def test_a_multi_token_pattern_is_unaffected(spec):
    """The rule applies only to lone tokens; longer patterns are specific
    enough on their own and must not be weakened."""
    assert _category(spec, "AMERICAN EXPRESS BUSINESS LOAN") is not None
