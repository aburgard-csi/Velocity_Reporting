"""R2 (James, 2026-11-05): insurance is addressable, and it is split by line -- auto, home,
life, health -- from the carrier the payment names. A multi-line carrier is "Auto & home",
never guessed as one; a payment that names no carrier is "Unspecified". Pinned: the
dictionary's subtypes are the category's own patterns, the figures add up, and the slide
lights only a known line.
"""
import pathlib
import sys

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti import dictionaries  # noqa: E402
from ti.deck import txn_leakage as L  # noqa: E402
from ti.transaction_intelligence import financial_services as fs  # noqa: E402
from ti.transaction_intelligence.merchant import merchant_key  # noqa: E402
from test_ti_hotspot_slides import _Harness  # noqa: E402

ANCHOR = pd.Timestamp("2026-10-31")


def test_insurance_is_addressable_and_every_subtype_pattern_is_its_own():
    spec = fs.load_patterns(dictionaries.folder())
    ins = spec["categories"]["Insurance"]
    assert ins["addressable"] is True
    listed = [p for pats in ins["subtypes"].values() for p in pats]
    assert len(listed) == len(set(listed)), "a pattern in two subtypes"
    assert set(listed) <= set(ins["patterns"])
    left = set(ins["patterns"]) - set(listed)
    assert left == {"INSURANCE", "INS PREM", "INS PREMIU", "INS PREMIUM", "INS.PREM"}
    assert "GEICO" in ins["subtypes"]["Auto"] and "STATE FARM" in ins["subtypes"]["Auto & home"]
    assert "METLIFE" in ins["subtypes"]["Life & annuity"] and "AETNA" in ins["subtypes"]["Health & dental"]


def _frame():
    rows = [("A1", "GEICO PMT 1234", 300.0), ("A1", "GEICO PMT 1234", 300.0),
            ("A2", "PROGRESSIVE INSURANCE", 200.0),
            ("A2", "NEW YORK LIFE INSURANCE", 150.0),
            ("A3", "STATE FARM INS", 400.0),
            ("A4", "AETNA HEALTH", 120.0),
            ("A5", "INS PREMIUM ACH", 80.0)]
    df = pd.DataFrame([(pd.Timestamp("2026-10-15"), a, "ACH", amt, d) for a, d, amt in rows],
                      columns=["transaction_date", "primary_account_num", "transaction_type",
                               "amount", "merchant_name"])
    df["mcc_code"] = None
    df["merchant_key"] = merchant_key(df["merchant_name"])
    return df


def test_insurance_is_split_by_line():
    spec = fs.load_patterns(dictionaries.folder(), {})
    m, _ = fs.compute(_frame(), None, spec, ANCHOR, None, lambda _m: None)
    rows = {r[0]: r for r in m["fin_subtypes"]["Insurance"]}
    assert set(rows) == {"Auto", "Auto & home", "Life & annuity", "Health & dental", "Unspecified"}
    assert rows["Auto"][1:5] == [2, 40.0, 3, 800]           # A1 and A2, of 5 insurance accounts
    assert rows["Auto & home"][4] == 400 and rows["Unspecified"][4] == 80
    assert sum(r[4] for r in rows.values()) == next(
        r[4] for r in m["fin_by_category"] if r[0] == "Insurance")
    assert m["fin_subtypes"]["Insurance"][-1][0] == "Unspecified"     # always last
    ins = next(r for r in m["fin_by_category"] if r[0] == "Insurance")
    assert ins[7] is True                                              # addressable


def test_the_slide_leads_with_a_known_line_and_greys_the_rest():
    t = {"fin_subtypes": {"Insurance": [
            ["Auto & home", 5_000, 41.0, 20_000, 4_000_000, 45.0, ["STATE FARM INS"]],
            ["Auto", 3_000, 25.0, 9_000, 2_500_000, 28.0, ["GEICO"]],
            ["Health & dental", 2_000, 16.0, 6_000, 1_500_000, 17.0, ["AETNA"]],
            ["Unspecified", 900, 7.0, 2_000, 900_000, 10.0, ["INS PREMIUM"]]]},
         "fin_subtypes_note": "note",
         "fin_by_category": [["Insurance", 12_143, 19.0, 37_000, 8_900_000, 733, "leakage", True, None, 100.0]]}
    h = _Harness()
    h["RIGHT_EDGE"] = 12.73
    L.insurance_by_line(h, t, "transacting personal accounts")
    (head, _), title = h.slides[0]
    assert title == "Insurance by line"
    assert head.startswith("Auto is the biggest single line: $2.5M from 3,000 accounts")
    bars = h.charts[0]["rows"]
    assert [b[3] for b in bars] == ["mixed", "line", "line", "mixed"]
    assert L.insurance_by_line(_Harness(), {}, "x").startswith("Insurance by line (")
