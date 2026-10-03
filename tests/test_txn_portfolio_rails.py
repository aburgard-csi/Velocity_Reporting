"""Portfolio block: the rails statement (P3) and the ODD join expectation (P6).

A card-only transaction file (1776, v5 #245) cannot show transfers to other institutions, so the
portfolio says which rails the file carries, once, and warns that competition and leakage are
card-rail only. The join to the ODD is expected at 95% or better (James, 2026-10-02): under that
the run says "partial join"; under the deposits gate (50%) it says the formats probably differ.

    python -m pytest tests/test_txn_portfolio_rails.py -q
"""
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build" / "ars_pipeline"), str(REPO / "build")]
from engine.transaction_intelligence import portfolio  # noqa: E402

HASH = "AB" * 20            # 40 characters: a hashed account


def _frame(types, accounts=None):
    n = len(types)
    accounts = accounts or [f"{HASH}{i:02d}" for i in range(n)]
    return pd.DataFrame({
        "transaction_date": pd.to_datetime(["2026-08-01"] * n),
        "primary_account_num": accounts,
        "transaction_type": types,
        "amount": [10.0] * n,
        "mcc_code": [""] * n,
        "merchant_name": ["SHOP"] * n,
        "merchant_key": ["SHOP"] * n,
        "merchant_id": [""] * n,
        "card_present": [""] * n,
    })


def test_rails_name_what_the_file_carries():
    m = portfolio.compute(_frame(["PIN", "SIG"]), None, lambda *_: None)
    assert m["txn_rails"] == ["card"]
    assert m["txn_rails_label"] == "card only"
    assert m["txn_transfer_rails"] is False

    m = portfolio.compute(_frame(["PIN", "ACH"]), None, lambda *_: None)
    assert m["txn_rails"] == ["card", "ACH"]
    assert m["txn_rails_label"] == "card + ACH"
    assert m["txn_transfer_rails"] is True

    m = portfolio.compute(_frame(["PIN", "ACH", "CHK"]), None, lambda *_: None)
    assert m["txn_rails_label"] == "card + ACH + check"


def test_a_card_only_feed_warns_that_every_figure_is_card_rail_only():
    warnings = []
    portfolio.compute(_frame(["PIN", "SIG", "PIN"]), None, warnings.append)
    assert any("card only" in w and "card-rail only" in w for w in warnings), warnings


def test_a_feed_with_transfers_does_not_warn_about_rails():
    warnings = []
    portfolio.compute(_frame(["PIN", "ACH", "CHK"]), None, warnings.append)
    assert not [w for w in warnings if w.startswith("rails:")], warnings


def _join(matched, total):
    accounts = [f"{HASH}{i:02d}" for i in range(total)]
    odd = pd.DataFrame({"Acct Number": accounts[:matched]})
    warnings = []
    m = portfolio.compute(_frame(["PIN"] * total, accounts), odd, warnings.append)
    return m, warnings


def test_a_join_at_or_over_95_is_quiet():
    m, warnings = _join(96, 100)
    assert m["txn_odd_match_pct"] == 96.0
    assert not [w for w in warnings if "join" in w or "match" in w], warnings


def test_a_join_under_95_says_partial_join():
    m, warnings = _join(80, 100)
    assert m["txn_odd_match_pct"] == 80.0
    assert any(w.startswith("partial join: 80.0%") and "95%" in w for w in warnings), warnings


def test_a_join_under_the_deposits_gate_says_formats_differ_not_partial():
    m, warnings = _join(30, 100)
    assert any("formats probably differ" in w for w in warnings), warnings
    assert not [w for w in warnings if w.startswith("partial join")], warnings
