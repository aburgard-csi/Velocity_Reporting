# Ported from ARS v5 02-Scripts/tests/test_competition.py at a491b5c (James Gilmore); logic unchanged.
# Not yet here (it reads the competition slide builder, ported with the chapter slides): test_the_slide_names_the_multi_banked_base.
"""competition section: named institutions, penetration, multi-banked, by lens.

    python -m pytest tests/test_competition.py -q

A hand-built frame where every answer is known: two nationals, a captive,
a local bank from client config, an ecosystem on both rails, a stopped
relationship, a new one, a bank-looking unmatched name, a business account.
"""
import pathlib
import sys

import pandas as pd
import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
CONFIG_DIR = __import__("ti.dictionaries", fromlist=["folder"]).folder()

from ti.transaction_intelligence import competition, financial_services  # noqa: E402
from ti.transaction_intelligence.lens import Lenses                      # noqa: E402

ANCHOR = pd.Timestamp("2026-07-31")
CLIENT_CFG = {"LocalCompetitors": {"Cape Cod Five": ["CAPE COD FIVE", "CAPE COD 5"]}}


def _rows(acct, desc, typ, months, amount=100.0):
    return [(pd.Timestamp(2026, m, 15) if m > 0 else pd.Timestamp(2025, 12 + m, 15),
             acct, typ, amount, desc) for m in months]


def make_frame() -> pd.DataFrame:
    r = []
    r += _rows("A1", "CHASE CREDIT CRD CHECK PYMT 000000000006182", "ACH", range(1, 8))
    r += _rows("A1", "CAPITAL ONE ONLINE PMT 123456789", "ACH", range(1, 8), 250.0)
    r += _rows("A2", "CAPITAL ONE ONLINE PMT 123456790", "ACH", [-4, -3, -2])      # Aug-Oct 2025: stopped
    r += _rows("A3", "VW CREDIT LOAN PMT 555555555", "ACH", [6, 7], 400.0)        # new relationship
    r += _rows("A4", "CAPE COD FIVE LOAN PAYMT 777777777", "ACH", range(1, 8))   # local competitor
    r += _rows("A5", "VENMO PAYMENT 888888888", "ACH", range(1, 8), 40.0)         # ecosystem, transfer rail
    r += _rows("A5", "XX1234 PURCHASE-SIG 07/01 10:00 PAYPAL *EBAY SAN JOSE CA 69424885 0701", "SIG", [7], 20.0)
    r += _rows("A6", "DISCOVERY CHANNEL STORE 99999999", "ACH", [7], 30.0)        # must not match Discover
    r += _rows("A7", "SEAMENS BANK LOAN PMT 123123123", "ACH", range(1, 8))      # unmatched, bank-looking
    r += _rows("A7", "EVERSOURCE WEB PAY 444444444", "ACH", range(1, 8))
    r += _rows("A8", "XX9999 PURCHASE-SIG 07/02 11:00 WALMART HYANNIS MA 12345678 0702", "SIG", [7], 55.0)
    r += _rows("B1", "VW CREDIT FLOORPLAN 321321321", "ACH", range(1, 8), 250_000.0)
    df = pd.DataFrame(r, columns=["transaction_date", "primary_account_num", "transaction_type",
                                  "amount", "merchant_name"])
    return df


def make_lenses() -> Lenses:
    ids = pd.Index([f"A{i}" for i in range(1, 9)] + ["B1"])
    def mask(members):
        return pd.Series([i in members for i in ids], index=ids)
    masks = {"all": pd.Series(True, index=ids),
             "responders": mask({"A1", "A3", "A5"}),
             "mailed_nonresp": mask({"A2", "A4", "A7", "A8"}),
             "not_mailed": mask({"A6", "B1"}),
             "business": mask({"B1"}), "personal": ~mask({"B1"}),
             "recently_inactive": mask({"A2", "A7"})}
    attrs = pd.DataFrame({"Curr Bal": [1000.0 * (i + 1) for i in range(len(ids))],
                          "Response Grouping": ["SO-SR"] * 9}, index=ids)
    return Lenses(key_column="Acct ID", accounts=ids, masks=masks, attrs=attrs)


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    df, lenses = make_frame(), make_lenses()
    spec = competition.load_config(CONFIG_DIR, CLIENT_CFG)
    fin_spec = financial_services.load_patterns(CONFIG_DIR, CLIENT_CFG)
    fin_rows = financial_services.classify_rows(df, fin_spec)
    warnings = []
    lists_dir = tmp_path_factory.mktemp("lists")
    m, out = competition.compute(df, lenses, spec, fin_rows, ANCHOR, lists_dir, warnings.append,
                                 account_filter=lenses.ids("personal"), key_prefix="comp_",
                                 base_label="personal accounts")
    return m, out, warnings


def test_penetration_counts_competitors_not_ecosystems(run):
    m, _, _ = run
    assert m["comp_accounts_total"] == 8                      # A1..A8 transact; B1 is business
    assert m["comp_with_competitor"] == 4                     # A1 A2 A3 A4
    assert m["comp_with_competitor_pct"] == 50.0
    assert m["comp_competitors_per_account"][:3] == [[0, 4], [1, 3], [2, 1]]
    assert m["comp_multi_banked_pct"] == 25.0


def test_institutions_table_names_tiers_and_local(run):
    m, _, _ = run
    rows = {r[0]: r for r in m["comp_institutions"]}
    cols = m["comp_institutions_columns"]
    assert {"Chase", "Capital One", "VW Credit", "Cape Cod Five"} <= set(rows)
    assert rows["Capital One"][cols.index("accounts")] == 2
    assert rows["Cape Cod Five"][cols.index("tier")] == "Local Bank / CU"
    assert rows["Chase"][cols.index("products")][0] == "Credit Cards"
    assert "Discover" not in rows                             # DISCOVERY is not DISCOVER
    tiers = {r[0]: r for r in m["comp_by_tier"]}
    assert tiers["National Bank"][2] == 2
    assert tiers["Captive Auto Finance"][2] == 1
    assert tiers["Local Bank / CU"][2] == 1


def test_ecosystems_are_separate_and_transfer_rail_only(run):
    m, _, _ = run
    eco = {r[0]: r for r in m["comp_ecosystems"]}
    assert eco["Venmo"][1] == 1
    assert "PayPal" not in eco                                # card purchase = merchant spend
    assert m["comp_ecosystem_accounts"] == 1


def test_momentum_new_and_stopped(run):
    m, _, _ = run
    mom = {r[0]: r for r in m["comp_momentum"]}
    assert mom["VW Credit"][1] == 1 and mom["VW Credit"][2] == 0
    assert mom["Capital One"][2] == 1


def test_by_lens_and_at_risk(run):
    m, _, _ = run
    bl = {r[0]: r for r in m["comp_by_lens"]}
    assert bl["responders"][3] == 2 and bl["responders"][4] == 66.7
    assert bl["mailed_nonresp"][3] == 2 and bl["mailed_nonresp"][4] == 50.0
    assert m["comp_responder_gap_pp"] == 16.7
    assert m["comp_at_risk"] == {"accounts": 2, "with_competitor": 1, "pct": 50.0}


def test_local_block_review_queue_and_lists(run):
    m, out, _ = run
    assert m["comp_local"]["configured"] == ["Cape Cod Five"]
    assert m["comp_local"]["accounts"] == 1
    assert any(s.startswith("SEAMENS BANK") for s, _, _ in m["comp_review_queue"])
    lists = out["competition_lists"]
    at_risk = pd.read_csv(lists["at_risk"])
    assert list(at_risk["acct"]) == ["A2"]
    multi = pd.read_csv(lists["multi_banked"])
    assert list(multi["acct"]) == ["A1"]


def test_business_base_is_separate():
    df, lenses = make_frame(), make_lenses()
    spec = competition.load_config(CONFIG_DIR, CLIENT_CFG)
    m, _ = competition.compute(df, None, spec, None, ANCHOR, None, lambda _m: None,
                               account_filter=lenses.ids("business"), key_prefix="compb_",
                               base_label="business accounts")
    rows = {r[0]: r for r in m["compb_institutions"]}
    assert set(rows) == {"VW Credit"}
    assert m["compb_competitor_dollars"] == 7 * 250_000


def test_local_competitors_accepts_plain_list():
    spec = competition.load_config(CONFIG_DIR, {"LocalCompetitors": ["Seamen's Bank", "Eastern Bank"]})
    assert spec["institutions"]["Seamen's Bank"]["tier"] == "Local Bank / CU"
    assert "SEAMEN'S BANK" in spec["institutions"]["Seamen's Bank"]["patterns"]


# ---------------------------------------------------------------------------
# regional competitors (per-client, seeded from the legacy Fed-district lists)
# ---------------------------------------------------------------------------

def test_load_config_regional_competitors():
    spec = competition.load_config(CONFIG_DIR, {
        "LocalCompetitors": {"Cape Cod Five": ["CAPE COD FIVE"]},
        "RegionalCompetitors": {"Northrim Bank": ["NORTHRIM BANK", "NORTHRIM"]},
    })
    inst = spec["institutions"]["Northrim Bank"]
    assert inst["tier"] == "Regional Bank"
    assert "NORTHRIM" in inst["patterns"]
    assert spec["tiers"]["Regional Bank"]["kind"] == "competitor"
    assert "Northrim Bank" in spec.get("regional_names", [])
    # locals unaffected, regional not counted as local
    assert "Cape Cod Five" not in spec.get("regional_names", [])
    assert "Northrim Bank" not in spec["local_names"]


def test_load_config_regional_list_form():
    spec = competition.load_config(CONFIG_DIR, {"RegionalCompetitors": ["Glacier Bank"]})
    assert spec["institutions"]["Glacier Bank"]["tier"] == "Regional Bank"


def test_the_two_penetration_denominators_are_published():
    """with_competitor_pct is over the whole base; multi_banked_pct is over
    the accounts that already have a competitor. They print side by side, so
    a reader must not have to infer which is which -- attrition_base already
    sets this habit."""
    import inspect

    from ti.transaction_intelligence import competition as comp

    src = inspect.getsource(comp)
    assert '"multi_banked_base"' in src
    assert '"with_competitor_base"' in src


def comp_slide_path():
    import pathlib
    return (pathlib.Path(__file__).resolve().parents[1]
            / "ars" / "deck" / "txn_compete.py")


def test_an_unconfigured_local_layer_warns():
    """1214, 1763 and 1795 carry no LocalCompetitors. The chapter still
    renders off the national and district layers, so without a warning an
    unconfigured input reads as a quiet market."""
    import pandas as pd

    from ti.transaction_intelligence import competition as comp

    warnings = []
    df = pd.DataFrame({
        "merchant_name": ["CHASE CREDIT CRD"],
        "transaction_type": ["ACH"],
        "amount": [100.0],
        "primary_account_num": ["1"],
        "post_date": pd.to_datetime(["2026-08-01"]),
    })
    spec = {"institutions": {}, "tiers": {}, "local_names": [],
            "regional_names": [], "false_positives": []}
    comp.compute(df, None, spec, None, pd.Timestamp("2026-08-31"), None,
                 warnings.append)
    assert any("no LocalCompetitors configured" in w for w in warnings), warnings
