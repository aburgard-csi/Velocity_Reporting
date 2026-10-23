# Ported from ARS v5 02-Scripts/tests/test_mcc_mapping.py at a491b5c (James Gilmore); logic unchanged.
"""The MCC taxonomy in 0_Config/merchant_categories.json.

    python -m pytest tests/test_mcc_mapping.py -q

Two levels: every group belongs to a parent, and the keyword buckets carry
the same parents so a client without MCC lands in the same taxonomy as one
with it. Codes are deliberately allowed to be unmapped -- what is NOT
allowed is a code claimed by two groups, which silently depends on dict
order for the winner.
"""
import json
import pathlib
import sys

import pandas as pd
import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
CONFIG = __import__("ti.dictionaries", fromlist=["folder"]).folder()

from ti.transaction_intelligence import merchants                  # noqa: E402

# codes that must resolve, with the group each belongs to. Everyday spend and
# financial both -- the point of the taxonomy is that it covers the book, not
# just the financial slice.
EXPECTED = [
    (5411, "Grocery"), (5812, "Dining"), (5541, "Fuel"),
    (5999, "Retail"), (5712, "Home & garden"), (5912, "Pharmacy & health"),
    (7230, "Personal care"), (5995, "Pets & veterinary"),
    (5921, "Specialty retail"),
    (5521, "Auto — dealers"), (5533, "Auto — parts and service"),
    (7538, "Auto — parts and service"), (7523, "Auto — parking and tolls"),
    (7011, "Travel"), (7832, "Entertainment"), (5815, "Online & digital"),
    (5817, "Subscriptions"), (8220, "Education"),
    (4900, "Utilities & telecom"), (6300, "Insurance"),
    (9311, "Government & tax"), (8111, "Professional services"),
    (4829, "Wallets & P2P"), (6540, "Wallets & P2P"), (6011, "Cash access"),
    (6211, "Investments"), (6513, "Real estate"),
    (5933, "Pawn & alternative finance"),
    (8398, "Charity & membership"), (4214, "Freight & storage"),
]


@pytest.fixture(scope="module")
def spec():
    return merchants.load_categories(CONFIG)


def _index(spec):
    out = {}
    for name, entry in spec["mcc_groups"].items():
        for lo, hi in merchants.group_ranges(entry):
            for code in range(lo, hi + 1):
                out.setdefault(code, []).append(name)
    return out


def test_no_code_belongs_to_two_groups(spec):
    """Overlap makes the winner depend on dict order. The pre-existing config
    had 5735 in both Retail and Entertainment."""
    dupes = {c: g for c, g in _index(spec).items() if len(g) > 1}
    assert not dupes, f"codes claimed twice: {dupes}"


def test_every_group_has_a_parent(spec):
    for name, entry in spec["mcc_groups"].items():
        assert isinstance(entry, dict), f"{name}: expected the two-level shape"
        assert entry.get("parent"), f"{name}: no parent"
        assert entry.get("ranges"), f"{name}: no ranges"


def test_keyword_buckets_share_the_mcc_taxonomy(spec):
    groups = spec["mcc_groups"]
    for name, entry in spec["keyword_buckets"].items():
        assert name in groups, f"bucket {name!r} has no matching MCC group"
        assert entry["parent"] == groups[name]["parent"], \
            f"{name}: bucket and MCC group disagree about the parent"


@pytest.mark.parametrize("code,group", EXPECTED)
def test_known_codes_resolve(spec, code, group):
    assert _index(spec).get(code) == [group]


def test_parents_cover_everyday_and_financial(spec):
    parents = {e["parent"] for e in spec["mcc_groups"].values()}
    assert {"Everyday", "Auto", "Financial"} <= parents


def _card(codes):
    return pd.DataFrame({"mcc_code": codes,
                         "merchant_key": ["X"] * len(codes)})


def test_categorize_uses_mcc_and_reports_coverage(spec):
    card = _card([5411, 5812, 5533, 6540, 9311])
    cats, method, coverage = merchants._categorize(card, spec, lambda m: None)
    assert method == "mcc" and coverage == 100.0
    assert list(cats) == ["Grocery", "Dining", "Auto — parts and service",
                          "Wallets & P2P", "Government & tax"]


def test_unmapped_code_falls_to_other_not_a_guess(spec):
    """An unknown code must land in Other, never in the nearest group."""
    cats, _, _ = merchants._categorize(_card([9999]), spec, lambda m: None)
    assert list(cats) == [merchants.OTHER]


def test_older_bare_range_config_still_reads():
    """Back-compat: {group: [[lo, hi]]} predates the parent shape."""
    spec = {"mcc_min_coverage_pct": 50,
            "mcc_groups": {"Grocery": [[5411, 5411]]},
            "keyword_buckets": {}}
    cats, method, _ = merchants._categorize(_card([5411]), spec,
                                            lambda m: None)
    assert method == "mcc" and list(cats) == ["Grocery"]
    assert merchants.parents(spec)["Other"] == merchants.NO_PARENT
