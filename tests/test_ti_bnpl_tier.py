"""Buy now, pay later is its own tier in the competitor dictionary (kind
bnpl), reported apart from competitors AND from the payment ecosystems, and
it names the same providers as the financial-services BNPL category.

    python -m pytest tests/test_ti_bnpl_tier.py -q
"""
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti import dictionaries                                     # noqa: E402
from ti.transaction_intelligence import competition, financial_services, mapping_audit  # noqa: E402
from test_ti_competition_family import make_frame              # noqa: E402
from test_ti_competition import ANCHOR, CLIENT_CFG, CONFIG_DIR, make_lenses  # noqa: E402

TIER = "Buy Now, Pay Later"


def _json(name):
    return json.loads((pathlib.Path(dictionaries.folder()) / name).read_text(encoding="utf-8"))


def test_the_tier_is_declared_with_its_own_kind():
    comp = _json("competitors.json")
    assert comp["tiers"][TIER] == {"kind": "bnpl"}
    bnpl = {n for n, i in comp["institutions"].items() if i["tier"] == TIER}
    assert {"Affirm", "Klarna", "Afterpay", "Sezzle", "Zip"} <= bnpl
    assert not any(i.get("bnpl") for i in comp["institutions"].values())   # no flag left behind
    assert not any(i["tier"] == "Payment Ecosystem" for n, i in comp["institutions"].items()
                   if n in bnpl)


def test_same_providers_as_the_finserv_category():
    comp = _json("competitors.json")
    fin = _json("financial_services_patterns.json")
    comp_p = {p for i in comp["institutions"].values() if i["tier"] == TIER for p in i["patterns"]}
    assert comp_p == set(fin["categories"]["Buy Now Pay Later"]["patterns"])


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    df, lenses = make_frame(), make_lenses()
    spec = competition.load_config(CONFIG_DIR, CLIENT_CFG)
    fin_rows = financial_services.classify_rows(df, financial_services.load_patterns(CONFIG_DIR, CLIENT_CFG))
    m, _ = competition.compute(df, lenses, spec, fin_rows, ANCHOR,
                               tmp_path_factory.mktemp("lists"), lambda *a: None,
                               account_filter=lenses.ids("personal"), key_prefix="comp_",
                               base_label="personal accounts")
    return m, spec


def test_bnpl_is_apart_from_the_ecosystems_and_the_competitors(run):
    m, _ = run
    assert [r[0] for r in m["comp_ecosystems"]] == ["Venmo"]
    assert m["comp_ecosystem_dollars"] == 280                 # Venmo only; Affirm's $100 is not here
    assert [r[0] for r in m["comp_bnpl"]["providers"]] == ["Affirm"]
    assert m["comp_bnpl"]["dollars"] == 100
    assert "Affirm" not in {r[0] for r in m["comp_institutions"]}
    assert TIER not in {r[0] for r in m["comp_by_tier"]}


def test_paypal_credit_is_bnpl_not_p2p():
    spec = competition.load_config(CONFIG_DIR, CLIENT_CFG)
    import pandas as pd
    t = competition._classify(pd.Index(["PAYPAL CREDIT PAYMENT 123456", "PAYPAL INST XFER 99",
                                        "UPLIFT DESK AUSTIN TX", "UPLIFT INC PMT"]), spec)
    assert t.loc["PAYPAL CREDIT PAYMENT 123456", "category"] == "PayPal Credit"
    assert t.loc["PAYPAL CREDIT PAYMENT 123456", "kind"] == "bnpl"
    assert t.loc["PAYPAL INST XFER 99", "category"] == "PayPal"
    assert pd.isna(t.loc["UPLIFT DESK AUSTIN TX", "category"])   # the standing desk, not the lender
    assert t.loc["UPLIFT INC PMT", "category"] == "Uplift"


def test_mapping_audit_reads_kind_not_the_tier_name():
    spec = competition.load_config(CONFIG_DIR, CLIENT_CFG)
    fin = {"categories": {"X": {"kind": "adjacency", "patterns": ["AFFIRM", "CHASE"]}}}
    rows = mapping_audit.conflicts(fin, spec, {})
    flagged = {r[0] for r in rows}
    assert "AFFIRM" not in flagged and "CHASE" in flagged
