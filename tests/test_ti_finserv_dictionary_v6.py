"""Financial-services dictionary v6 (fs-01): one category per pattern, generic descriptors
publish as (unnamed), bank + product routing, the misses found on 1798, and the payday category."""
import json
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build" / "ars_pipeline"))

from ti.transaction_intelligence import financial_services as F  # noqa: E402

DICT_DIR = ROOT / "build" / "ars_pipeline" / "ti" / "dictionaries"


@pytest.fixture(scope="module")
def spec():
    return F.load_patterns(DICT_DIR, {})


def _classify(spec, strings):
    return F.classify_strings(pd.Index(strings), spec)


def test_no_pattern_sits_in_two_categories(spec):
    seen = defaultdict(set)
    for cat, c in spec["categories"].items():
        for p in c["patterns"]:
            seen[p.upper().strip()].add(cat)
    dups = {p: sorted(cats) for p, cats in seen.items() if len(cats) > 1}
    assert not dups, dups


@pytest.mark.parametrize("descriptor", ["GECU AUTO LOAN", "CARD PAYMENT", "LOAN PAYMENT", "INS PREMIUM"])
def test_generic_descriptor_is_never_the_provider(spec, descriptor):
    row = _classify(spec, [descriptor]).loc[descriptor]
    assert row["category"] is not None
    assert row["provider"] == F.UNNAMED_PROVIDER


def test_named_lender_still_publishes_its_name(spec):
    row = _classify(spec, ["ALLY FIN"]).loc["ALLY FIN"]
    assert row["category"] == "Auto Loans"
    assert row["provider"] == "ALLY FINANCIAL"


@pytest.mark.parametrize("descriptor,category", [
    ("WELLS FARGO AUTO", "Auto Loans"),
    ("PNC BANK AUTO", "Auto Loans"),
    ("WELLS FARGO MTG", "Mortgage/HELOC"),
    ("DISCOVER CARD", "Credit Cards"),
    ("CREDIT ONE", "Credit Cards"),
    ("LENDINGCLUB", "Personal Loans"),
    ("GOLDMAN SACHS BANK", "Online Banks / Savings"),
    ("DAVE COM", "Fintech / Neobanks"),
    ("CHECK INTO CASH", "Payday / Small-Dollar Loans"),
    ("ADVANCE AMERICA", "Payday / Small-Dollar Loans"),
    ("PLAIN GREEN", "Payday / Small-Dollar Loans"),
    ("SYNCHRONY BANK", "Credit Cards"),
    ("SALLIE MAE BANK", "Student Loans"),
    ("LOAN DEPOT", "Mortgage/HELOC"),
    ("EMPOWER RETIREMENT", "Retirement / 401k"),
])
def test_category_routing(spec, descriptor, category):
    assert _classify(spec, [descriptor]).loc[descriptor]["category"] == category


@pytest.mark.parametrize("descriptor", ["BANK OF NOWHERE AUTO PARTS", "STEP UP FITNESS", "DAVE AND BUSTERS"])
def test_noise_still_unmatched(spec, descriptor):
    assert _classify(spec, [descriptor]).loc[descriptor]["category"] in (None, float("nan")) or \
        pd.isna(_classify(spec, [descriptor]).loc[descriptor]["category"])


def test_payday_category_is_addressable_leakage(spec):
    c = spec["categories"]["Payday / Small-Dollar Loans"]
    assert c["kind"] == "leakage" and c["addressable"] is True
