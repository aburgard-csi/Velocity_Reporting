# Ported from ARS v5 02-Scripts/tests/test_competition_family.py at a491b5c (James Gilmore); logic unchanged.
"""The competition family, group 1 of the legacy rebuild (#258): the metrics
behind nine slides, on a book small enough to count by hand.

Legacy 17 engagement depth (share of an account's TRANSACTIONS at a
competitor), 20-22 wallet share per competitor (share of its DOLLARS),
27 recency of every account-competitor pair, 35 how many competitors each
account uses, 16 winback (competitors whose volume fell, last three months
against the three before), 14 depth against growth, 66-67 BNPL.

    python -m pytest tests/test_competition_family.py -q
"""
import pathlib
import sys

import pandas as pd
import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.transaction_intelligence import competition, financial_services   # noqa: E402
from test_ti_competition import ANCHOR, CLIENT_CFG, CONFIG_DIR, _rows, make_lenses  # noqa: E402

CHASE, CAPONE = "CHASE CREDIT CRD AUTOPAY 000000000006182", "CAPITAL ONE ONLINE PMT 123456789"
CAPECOD, DISCOVER = "CAPE COD FIVE LOAN PAYMT 777777777", "DISCOVER E-PAYMENT 555555555"
WALMART = "WALMART SUPERCENTER 4444444444"


def make_frame() -> pd.DataFrame:
    r = []
    r += _rows("A1", CHASE, "ACH", range(1, 8))                       # 7 txns, heavy at Chase
    r += _rows("A1", WALMART, "ACH", range(1, 4))
    r += _rows("A2", CAPONE, "ACH", [-4, -3])                          # Aug, Sep 2025: dormant
    r += _rows("A2", WALMART, "ACH", [-1, *range(1, 8)])
    r += _rows("A3", CHASE, "ACH", [7], 30.0)                          # one light touch, recent
    r += _rows("A3", WALMART, "ACH", [-2, -1, *range(1, 8)])
    r += _rows("A4", CAPECOD, "ACH", range(1, 8))                      # heavy at the local
    r += _rows("A4", CHASE, "ACH", [7], 20.0)
    r += _rows("A5", "VENMO PAYMENT 888888888", "ACH", range(1, 8), 40.0)   # ecosystem only
    r += _rows("A5", "AFFIRM PAYMENT 999999999", "ACH", [6, 7], 50.0)       # BNPL
    r += _rows("A5", WALMART, "ACH", [7])
    r += _rows("A6", WALMART, "ACH", [7])                              # no competitor at all
    for desc in (CHASE, CAPONE, CAPECOD, DISCOVER):                     # A7 uses four
        r += _rows("A7", desc, "ACH", [7])
    r += _rows("A7", WALMART, "ACH", range(4, 8))
    r += _rows("A8", CAPONE, "ACH", [2, 3, 4, 6])                      # 3 prior, 1 recent: declining
    r += _rows("B1", "VW CREDIT FLOORPLAN 321321321", "ACH", range(1, 8), 250_000.0)
    return pd.DataFrame(r, columns=["transaction_date", "primary_account_num",
                                    "transaction_type", "amount", "merchant_name"])


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    mp = pytest.MonkeyPatch()                     # module-scoped, undone at the end
    mp.setattr(competition, "MIN_WINBACK_ACCOUNTS", 1)   # three accounts here, not 25
    mp.setattr(competition, "MIN_WALLET_ACCOUNTS", 1)
    df, lenses = make_frame(), make_lenses()
    spec = competition.load_config(CONFIG_DIR, CLIENT_CFG)
    fin_rows = financial_services.classify_rows(df, financial_services.load_patterns(CONFIG_DIR, CLIENT_CFG))
    m, _ = competition.compute(df, lenses, spec, fin_rows, ANCHOR,
                               tmp_path_factory.mktemp("lists"), lambda *a: None,
                               account_filter=lenses.ids("personal"), key_prefix="comp_",
                               base_label="personal accounts")
    yield m
    mp.undo()


def test_engagement_depth_tiers_share_of_transactions(run):
    rows = {r[0]: r for r in run["comp_engagement"]}
    cols = run["comp_engagement_columns"]
    assert cols == ["institution", "accounts", "light", "moderate", "heavy", "avg_share_pct"]
    chase = rows["Chase"]
    assert chase[1:5] == [4, 3, 0, 1]                       # A1 heavy; A3, A4, A7 light
    assert chase[5] == pytest.approx(26.25, abs=0.06)     # (70 + 10 + 12.5 + 12.5) / 4
    assert rows["Capital One"][1:5] == [3, 1, 1, 1]         # A7 light, A2 moderate, A8 heavy
    assert run["comp_engagement_heavy_n"] == 3               # A1 at Chase, A4 at Cape Cod, A8 at Capital One
    assert [r[0] for r in run["comp_engagement"]][:2] == ["Chase", "Capital One"]


def test_wallet_share_per_institution_tiers_share_of_dollars(run):
    rows = {r[0]: r for r in run["comp_wallet_by_institution"]}
    assert run["comp_wallet_by_institution_columns"] == [
        "institution", "accounts", "cu_focused", "balanced", "heavy", "heavy_pct"]
    assert rows["Chase"][1:] == [4, 3, 0, 1, 25.0]
    assert rows["Cape Cod Five"][1:] == [2, 1, 0, 1, 50.0]
    assert rows["Capital One"][1:] == [3, 2, 0, 1, 33.3]     # A8 spends nowhere else


def test_recency_bands_count_account_competitor_pairs(run):
    bands = {r[0]: r for r in run["comp_recency_bands"]}
    assert [r[0] for r in run["comp_recency_bands"]] == [
        "Last 30 days", "31-90 days", "91-180 days", "180+ days"]
    assert bands["Last 30 days"][1] == 8
    assert bands["31-90 days"][1] == 1                       # A8 at Capital One, June
    assert bands["180+ days"][1] == 1                        # A2 at Capital One, last September
    assert run["comp_recency_pairs"] == 10
    assert run["comp_recency_active_pct"] == 80.0
    assert run["comp_recency_dormant_pairs"] == 1


def test_breadth_bands_and_the_no_competitor_share(run):
    bands = {r[0]: r for r in run["comp_breadth_bands"]}
    assert [r[0] for r in run["comp_breadth_bands"]] == ["1", "2-3", "4-5", "6+"]
    assert bands["1"][1] == 4 and bands["2-3"][1] == 1 and bands["4-5"][1] == 1
    assert bands["6+"][1] == 0
    assert bands["1"][2] == 66.7                             # of the six with any competitor
    assert bands["1"][3] == 50.0                             # of the eight in the book
    assert run["comp_breadth_no_competitor"] == 2            # A5 (ecosystems only), A6
    assert run["comp_breadth_no_competitor_pct"] == 25.0
    assert run["comp_breadth_shopping"] == 2                 # two or more: A4, A7


def test_winback_names_the_competitor_whose_volume_fell(run):
    rows = {r[0]: r for r in run["comp_winback"]}
    assert run["comp_winback_columns"] == [
        "institution", "accounts", "recent_txns", "prior_txns", "txn_growth_pct", "score"]
    assert list(rows) == ["Capital One"]
    assert rows["Capital One"][1:5] == [3, 2, 3, -33.3]
    assert run["comp_winback_accounts"] == 3
    assert "May" in run["comp_winback_window"] and "Feb" in run["comp_winback_window"]


def test_depth_against_growth_per_institution(run):
    rows = {r[0]: r for r in run["comp_depth_growth"]}
    assert run["comp_depth_growth_columns"] == ["institution", "accounts", "txns_per_acct", "growth_pct"]
    assert rows["Chase"][1:] == [4, 2.5, 50.0]               # 10 txns over 4 accounts; $450 recent vs $300 prior
    assert rows["Capital One"][3] == -33.3


def test_bnpl_reads_the_flagged_ecosystems(run):
    b = run["comp_bnpl"]
    assert b["accounts"] == 1 and b["pct"] == 12.5 and b["dollars"] == 100
    assert b["months"] == 11                                  # Aug-Nov 2025 and Jan-Jul 2026 carry rows
    assert b["per_acct_month"] == 9.09
    assert b["providers"][0][:2] == ["Affirm", 1]
    assert "Venmo" not in {r[0] for r in b["providers"]}
