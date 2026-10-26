# Ported from ARS v5 02-Scripts/tests/test_interchange_txn.py at a491b5c (James Gilmore); logic unchanged.
"""The PIN / signature routing block (ic_*) and the channel-pair grid
(rel_channel_pairs), every value counted by hand on a small frame.

    python -m pytest tests/test_interchange_txn.py -q
"""
import pathlib
import sys

import pandas as pd
import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.transaction_intelligence import interchange, relationship   # noqa: E402
from ti.transaction_intelligence.lens import Lenses                 # noqa: E402

ANCHOR = pd.Timestamp("2026-04-30")
COLS = ["primary_account_num", "transaction_date", "transaction_type", "amount",
        "merchant_key", "merchant_name"]


def _row(acct, month, typ, amount, merchant):
    return (acct, pd.Timestamp(2026, month, 15), typ, -amount, merchant,
            f"XX1234 PURCHASE-{typ} {merchant}")


def make_frame() -> pd.DataFrame:
    rows = [_row("A1", m, "PIN", 100.0, "WALMART") for m in (1, 2, 3)]
    rows.append(_row("A1", 3, "SIG", 50.0, "AMAZON"))
    rows += [_row("A2", m, "SIG", 200.0, "AMAZON") for m in (1, 2, 3, 4)]
    rows += [_row("A3", 2, "PIN", 100.0, "WALMART"), _row("A3", 2, "SIG", 100.0, "COSTCO")]
    rows.append(_row("A4", 4, "PIN", 60.0, "COSTCO"))
    rows.append(_row("B1", 1, "SIG", 1000.0, "AMAZON"))            # business: outside the base
    rows.append(_row("A5", 1, "ACH", 500.0, "LANDLORD"))           # not a card row
    return pd.DataFrame(rows, columns=COLS)


def make_lenses() -> Lenses:
    ids = pd.Index(["A1", "A2", "A3", "A4", "A5", "B1"])

    def mask(members):
        return pd.Series([i in members for i in ids], index=ids)
    masks = {"responders": mask({"A1", "A2"}), "mailed_nonresp": mask({"A3", "A4"}),
             "personal": ~mask({"B1"}), "business": mask({"B1"})}
    attrs = pd.DataFrame({"Account Holder Age": [30, 70, 30, 45, 50, 40],
                          "Prod Desc": ["Free Checking", "Free Checking", "Premier",
                                        "Premier", "Premier", "Business"]}, index=ids)
    return Lenses(key_column="Acct ID", accounts=ids, masks=masks, attrs=attrs)


@pytest.fixture
def out(monkeypatch):
    monkeypatch.setattr(interchange, "MIN_GROUP_ACCOUNTS", 1)
    lenses = make_lenses()
    return interchange.compute(make_frame(), lenses, ANCHOR, lambda _m: None,
                               account_filter=lenses.ids("personal"),
                               base_label="transacting personal accounts")


def test_the_mix_and_the_tickets_are_counted_by_hand(out):
    assert out["ic_routing_available"] is True and out["ic_rails"] == ["PIN", "SIG"]
    assert out["ic_card_accounts"] == 4 and out["ic_card_spend"] == 1410
    assert out["ic_sig_share_pct"] == 67.4                    # 950 of 1,410
    assert out["ic_sig_share_of_swipes_pct"] == 54.5          # 6 of 11
    assert out["ic_pin_ticket"] == 92.0 and out["ic_sig_ticket"] == 158.33
    assert out["ic_sig_vs_goal_pp"] == 7.4


def test_the_monthly_share_and_its_direction(out):
    assert out["ic_monthly"] == [["2026-01", 100, 200, 66.7, 2], ["2026-02", 200, 300, 60.0, 3],
                                 ["2026-03", 100, 250, 71.4, 2], ["2026-04", 60, 200, 76.9, 2]]
    assert out["ic_sig_shift_pp"] == 3.4 and out["ic_sig_direction"] == "improving"


def test_accounts_by_their_own_mix_and_the_pin_heavy_block(out):
    mix = {r[0]: r[1:] for r in out["ic_account_mix"]}
    assert mix["0-20%"] == [2, 50.0, 410]                     # A1 at 14.3%, A4 at 0%
    assert mix["40-60%"] == [1, 25.0, 200] and mix["80-100%"] == [1, 25.0, 800]
    assert mix["20-40%"][0] == 0 and mix["60-80%"][0] == 0
    assert out["ic_pin_heavy_n"] == 2 and out["ic_pin_heavy_pct"] == 50.0
    assert out["ic_pin_heavy_spend"] == 410 and out["ic_pin_heavy_spend_pct"] == 29.1
    assert out["ic_pin_heavy_spend_per_acct_mo"] == 51       # 410 / 2 accounts / 4 months


def test_routing_by_merchant_is_observed_not_imputed(out):
    assert out["ic_by_merchant"] == [["AMAZON", 5, 0, 850, 100.0],
                                     ["WALMART", 4, 400, 0, 0.0],
                                     ["COSTCO", 2, 60, 100, 62.5]]


def test_the_group_cuts(out):
    by = {r[0]: r[2:] for r in out["ic_by_lens"]}
    assert by["responders"] == [2, 73.9, 1150] and by["mailed_nonresp"] == [2, 38.5, 260]
    assert "business" not in by                              # nothing in the personal base
    assert out["ic_by_age"] == [["26-35", 2, 27.3, 550], ["36-45", 1, 0.0, 60],
                                ["65+", 1, 100.0, 800]]
    assert out["ic_by_product"] == [["Free Checking", 2, 73.9, 1150], ["Premier", 2, 38.5, 260]]
    assert out["ic_pin_default_products"] == [["Premier", 2, 38.5, 260]]


def test_a_single_rail_file_declines_the_whole_mix():
    df = make_frame()
    df = df[df["transaction_type"] != "PIN"]
    warnings = []
    out = interchange.compute(df, None, ANCHOR, warnings.append)
    assert out["ic_routing_available"] is False and out["ic_rails"] == ["SIG"]
    assert "ic_sig_share_pct" not in out and "ic_monthly" not in out
    assert any("one card rail" in w for w in warnings)


def test_small_groups_are_dropped_not_shown_small():
    lenses = make_lenses()
    out = interchange.compute(make_frame(), lenses, ANCHOR, lambda _m: None,
                              account_filter=lenses.ids("personal"))
    assert out["ic_by_lens"] == [] and out["ic_by_age"] == [] and out["ic_by_product"] == []


def _rel_row(acct, typ, merchant):
    return (acct, pd.Timestamp(2026, 1, 15), typ, -50.0, merchant, merchant)


def test_channel_pairs_and_the_next_channel_by_hand():
    rows = [_rel_row("R1", "PIN", "WALMART"), _rel_row("R1", "ACH", "LANDLORD"),
            _rel_row("R2", "SIG", "AMAZON"), _rel_row("R2", "ACH", "LANDLORD"),
            _rel_row("R2", "CHK", "CHECK 101"), _rel_row("R3", "PIN", "WALMART"),
            _rel_row("R4", "ACH", "LANDLORD"), _rel_row("R5", "SIG", "AMAZON")]
    out = relationship.compute(pd.DataFrame(rows, columns=COLS), None, None, ANCHOR,
                               lambda _m: None)
    grid = out["rel_channel_pairs"]
    assert grid["rows"] == ["card", "ACH", "CHK"] and grid["cols"] == grid["rows"]
    assert grid["cells"] == [[None, 50.0, 25.0], [66.7, None, 33.3], [100.0, 100.0, None]]
    assert out["rel_next_channel"] == [["card", 2, "ACH", 50.0], ["ACH", 1, "card", 66.7],
                                       ["CHK", 0, "card", 100.0]]


def test_channel_pairs_decline_on_a_single_rail():
    rows = [_rel_row("R1", "PIN", "WALMART"), _rel_row("R2", "SIG", "AMAZON")]
    out = relationship.compute(pd.DataFrame(rows, columns=COLS), None, None, ANCHOR,
                               lambda _m: None)
    assert out["rel_single_rail"] is True
    assert out["rel_channel_pairs"] is None and out["rel_next_channel"] == []
