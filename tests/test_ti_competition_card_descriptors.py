# Ported from ARS v5 02-Scripts/tests/test_competition_card_descriptors.py at a491b5c (James Gilmore); logic unchanged.
"""Competition on a card feed, with descriptors shaped the way acquirers
write them: NAME CITY ST (#261).

On 1776 the description cleaner cut the institution's name off before the
matcher saw it (a one-word city took the name's last word with it; CU, BK
and NA read as state codes), every payment-ecosystem row on the card rail
was discarded, the review queue was gated on a transfer rail the feed does
not carry, and 14 of 24 locals shipped one spelling. These tests hold the
fixes together, on descriptors that could be pasted from the file.

    python -m pytest tests/test_competition_card_descriptors.py -q
"""
import pathlib
import sys

import pandas as pd
import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.transaction_intelligence import competition, financial_services   # noqa: E402
from ti.transaction_intelligence.merchant import merchant_core, merchant_text  # noqa: E402
from test_ti_competition import ANCHOR, make_lenses                            # noqa: E402

CONFIG_DIR = __import__("ti.dictionaries", fromlist=["folder"]).folder()
CLIENT_CFG = {"LocalCompetitors": {
    "Sesloc Credit Union": ["SESLOC CREDIT UNION", "SESLOC CU", "SESLOC FCU"],
    "Mechanics Bank": ["MECHANICS BANK"],
    "Schoolsfirst Federal": ["SCHOOLSFIRST FEDERAL"],
    "Montecito Bank & Trust": ["MONTECITO BANK & TRUST"],
    "Star One Credit Union": ["STAR ONE CREDIT UNION"],
}}


def _card(acct, desc, amount=100.0, month=7):
    return (pd.Timestamp(2026, month, 15), acct, "SIG", amount,
            f"XX1234 PURCHASE-SIG 07/01 10:00 {desc} 69424885 0701")


def make_card_only_frame() -> pd.DataFrame:
    rows = [
        _card("A1", "SESLOC FCU ATASCADERO CA"),
        _card("A2", "MECHANICS BK LOMPOC CA"),
        _card("A3", "SCHOOLSFIRST CU TUSTIN CA"),          # variant not configured
        _card("A4", "MONTECITO BK LOMPOC CA"),              # TRUST not carried
        _card("A5", "STAR ONE CU"),                          # CU is not a state
        _card("A6", "VENMO NEW YORK NY", 40.0),
        _card("A6", "CASH APP OAKLAND CA", 25.0),
        _card("A7", "APPLE CASH 1INFINITELOOP CA", 30.0),
        _card("A7", "PAYPAL *EBAY SAN JOSE CA", 20.0),       # a purchase, not P2P
        _card("A8", "VANDENBERG BK LOMPOC CA", 60.0),        # not configured: review queue
        _card("A8", "WALMART HYANNIS MA", 55.0),
        _card("B1", "CHASE CREDIT CRD AUTOPAY", 250.0),
    ]
    return pd.DataFrame(rows, columns=["transaction_date", "primary_account_num",
                                       "transaction_type", "amount", "merchant_name"])


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    df, lenses = make_card_only_frame(), make_lenses()
    spec = competition.load_config(CONFIG_DIR, CLIENT_CFG)
    fin_spec = financial_services.load_patterns(CONFIG_DIR, CLIENT_CFG)
    fin_rows = financial_services.classify_rows(df, fin_spec)
    warnings = []
    m, out = competition.compute(df, lenses, spec, fin_rows, ANCHOR,
                                 tmp_path_factory.mktemp("lists"), warnings.append,
                                 account_filter=lenses.ids("personal"), key_prefix="comp_",
                                 base_label="personal accounts")
    return m, out, warnings


# ---- the cleaner ------------------------------------------------------------

def test_the_cleaner_keeps_the_depository_word_and_strips_the_city():
    got = merchant_core(pd.Series([
        "SESLOC FCU ATASCADERO CA", "MECHANICS BK LOMPOC CA",
        "MECHANICS BANK SANTA MARIA CA", "STAR ONE CU", "WELLS FARGO BANK NA",
        "WALMART HYANNIS MA", "PAYPAL EBAY US SAN JOSE CA"]))
    assert list(got) == ["SESLOC FCU", "MECHANICS BK", "MECHANICS BANK",
                         "STAR ONE CU", "WELLS FARGO BANK NA", "WALMART", "PAYPAL EBAY US"]


def test_the_matching_text_keeps_everything_after_the_prefix():
    got = merchant_text(pd.Series(["XX1234 PURCHASE-SIG 07/01 10:00 SESLOC FCU ATASCADERO CA 69424885 0701"]))
    assert list(got) == ["SESLOC FCU ATASCADERO CA"]


# ---- locals on one-word-city descriptors ------------------------------------

def test_every_local_is_found_on_a_one_word_city_descriptor(run):
    m, _, _ = run
    rows = {r[0]: r for r in m["comp_institutions"]}
    for name in ("Sesloc Credit Union", "Mechanics Bank", "Schoolsfirst Federal",
                 "Montecito Bank & Trust", "Star One Credit Union"):
        assert name in rows, f"{name} not matched; matched {sorted(rows)}"
    local = m["comp_local"]
    assert local["accounts"] == 5
    assert {r[0] for r in local["institutions"]} == set(CLIENT_CFG["LocalCompetitors"])


# ---- ecosystems on a card-only feed: separated, not discarded ---------------

def test_ecosystems_are_counted_on_the_card_rail_and_kept_apart(run):
    m, _, _ = run
    eco = {r[0]: r for r in m["comp_ecosystems"]}
    assert {"Venmo", "Cash App", "Apple Cash"} <= set(eco)
    assert "PayPal" not in eco                       # PAYPAL *EBAY is a purchase
    assert m["comp_ecosystem_accounts"] == 2         # A6, A7
    assert m["comp_ecosystem_dollars"] == 95
    # and they are not competitors
    assert "Venmo" not in {r[0] for r in m["comp_institutions"]}
    assert m["comp_with_competitor"] == 5            # the five locals only


def test_finserv_counts_p2p_on_the_card_rail_too():
    df = make_card_only_frame()
    fin_spec = financial_services.load_patterns(CONFIG_DIR, CLIENT_CFG)
    rows = financial_services.classify_rows(df, fin_spec)
    venmo = rows[df["merchant_name"].str.contains("VENMO")]
    assert (venmo["kind"] == "adjacency").all()
    paypal = rows[df["merchant_name"].str.contains(r"PAYPAL \*EBAY")]
    assert paypal["kind"].isna().all()


# ---- the review queue on a feed with no transfer rail -----------------------

def test_the_review_queue_runs_on_the_card_rail_when_there_is_no_other(run):
    m, _, _ = run
    queue = {r[0]: r for r in m.get("comp_review_queue", [])}
    assert any("VANDENBERG" in k for k in queue), m.get("comp_review_queue")


# ---- variants generated at load time ----------------------------------------

def test_load_config_generates_the_depository_variants():
    spec = competition.load_config(CONFIG_DIR, CLIENT_CFG)
    pats = {n: set(i["patterns"]) for n, i in spec["institutions"].items()}
    assert {"SCHOOLSFIRST CU", "SCHOOLSFIRST FCU", "SCHOOLSFIRST CREDIT UNION"} \
        <= pats["Schoolsfirst Federal"]
    assert {"MONTECITO BANK", "MONTECITO BK"} <= pats["Montecito Bank & Trust"]
    assert {"MECHANICS BK"} <= pats["Mechanics Bank"]
    assert {"STAR ONE CU", "STAR ONE FCU"} <= pats["Star One Credit Union"]
    for name, inst in spec["institutions"].items():
        if not inst.get("local"):
            continue
        for p in inst["patterns"]:
            assert len(p.split()) >= 2 or len(p) >= 5, f"{name}: bare stem {p!r}"


def test_variants_never_produce_a_bare_stem():
    assert "SESLOC" not in competition.depository_variants("Sesloc Credit Union")
    assert "FIRST" not in competition.depository_variants("First Bank")
    assert competition.depository_variants("Bay Commercial Finance") == {"BAY COMMERCIAL FINANCE"}
