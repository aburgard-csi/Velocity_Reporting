"""Financial-services dictionary v7 (fs-07): names read from 1798's October 2026 review queue."""
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


def _cat(spec, s):
    return F.classify_strings(pd.Index([s]), spec).loc[s]["category"]


@pytest.mark.parametrize("descriptor,category", [
    ("WORLD FINANCE - LOANS", "Payday / Small-Dollar Loans"),
    ("PNM*SUN LOANS", "Payday / Small-Dollar Loans"),
    ("SECURITY-FIN", None),                                     # bare and ambiguous: still unmatched
    ("SECURITY FINANCE", "Payday / Small-Dollar Loans"),
    ("OPC*REPUBLIC FINANCE", "Payday / Small-Dollar Loans"),
    ("REGIONAL ACCEPTANCE #0123", "Payday / Small-Dollar Loans"),
    ("SNAP FINANCE", "Buy Now Pay Later"),
    ("FRED LOYA INSURANCE", "Insurance"),
    ("FIC*FOREMOST INSURANCE", "Insurance"),
    ("TRANSAK*TRUST WALLET", "Crypto/Digital Assets"),
    ("BILT - MORTGAGE", "Mortgage/HELOC"),
    ("STELLANTIS FINANCIAL S", "Auto Loans"),
])
def test_the_review_queue_names_now_match(spec, descriptor, category):
    got = _cat(spec, descriptor)
    assert (got is None or pd.isna(got)) if category is None else got == category


@pytest.mark.parametrize("descriptor", [
    "WORLD MARKET", "SUN VALLEY HARDWARE", "SECURITY STORAGE", "REPUBLIC SERVICES", "REGIONAL MEDICAL CENTER",
    "SNAP FITNESS", "HEIGHTS BAKERY", "TRUST PROPERTIES",
])
def test_lookalike_businesses_stay_unmatched(spec, descriptor):
    got = _cat(spec, descriptor)
    assert got is None or pd.isna(got)


def test_still_no_pattern_in_two_categories(spec):
    seen = defaultdict(set)
    for cat, c in spec["categories"].items():
        for p in c["patterns"]:
            seen[p.upper().strip()].add(cat)
    assert not {p: c for p, c in seen.items() if len(c) > 1}
