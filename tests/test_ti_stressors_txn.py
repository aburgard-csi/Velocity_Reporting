# Ported from ARS v5 02-Scripts/tests/test_stressors_txn.py at a491b5c (James Gilmore); logic unchanged.
"""The TXN-side stressor count: the ODD conditions plus banking elsewhere.

stressors.py runs in the ODD pipeline, which cannot see a transaction. This
module runs where both frames exist -- the same join hotspots.py makes -- so
the count finally spans both sources instead of one.
"""
import pathlib
import sys

import pandas as pd


from ti.core.periods import Month
from ti.transaction_intelligence import stressors_txn as P

ANCHOR = Month.from_tag("Jul26")


def _odd():
    return pd.DataFrame({
        "Acct Number": ["A1", "A2", "A3"],
        "Debit?": ["Yes", "Yes", "Yes"],
        "Date Opened": ["2019-01-15"] * 3,
        "Curr Bal": [40000.0, 500.0, 40000.0],
        "Avg Bal": [55000.0, 500.0, 30000.0],
        "Jul26 Spend": [0.0, 100.0, 120.0],
        "Feb26 Spend": [90.0, 100.0, 100.0],
        "Mar26 Spend": [90.0, 100.0, 100.0],
        "Apr26 Spend": [0.0, 100.0, 100.0],
        "May26 Spend": [0.0, 100.0, 110.0],
        "Jun26 Spend": [0.0, 100.0, 130.0],
    })


COMP = [["A1", "BIG BANK", 900.0], ["A3", "OTHER CU", 120.0]]


def test_declines_without_the_odd_rather_than_guessing():
    warned = []
    out, _ = P.compute(None, COMP, ANCHOR, {}, None, warned.append)
    assert out == {}
    assert any("ODD" in w for w in warned)


def test_declines_without_competitor_rows():
    warned = []
    out, _ = P.compute(_odd(), None, ANCHOR, {}, None, warned.append)
    assert out == {}
    # The warning names competition.py -- the module that produced nothing --
    # rather than the abstract noun, so a reader knows where to look.
    assert any("competition" in w.lower() for w in warned)


def test_banking_elsewhere_is_built_here_not_skipped():
    """The whole point: the condition the ODD run had to skip is available."""
    out, _ = P.compute(_odd(), COMP, ANCHOR, {}, None, lambda m: None)
    assert "Banking elsewhere" in out["stress_txn_available"]
    assert "Banking elsewhere" not in out.get("stress_txn_skipped", [])


def test_the_txn_count_can_exceed_the_odd_count():
    """A1 trips flight, spend health and now banking elsewhere."""
    out, _ = P.compute(_odd(), COMP, ANCHOR, {}, None, lambda m: None)
    assert out["stress_txn_2plus_n"] >= 1
    assert max(r[0] for r in out["stress_txn_by_count"]) >= 2


def test_it_declares_its_base_and_its_source():
    out, _ = P.compute(_odd(), COMP, ANCHOR, {}, None, lambda m: None)
    assert out["stress_txn_base"] == "Open at anchor, transacting join"


def test_writes_an_enriched_roster(tmp_path):
    out, outputs = P.compute(_odd(), COMP, ANCHOR, {}, tmp_path, lambda m: None)
    path = pathlib.Path(outputs["stressor_roster_txn"])
    written = pd.read_csv(path)
    assert "competitor_dollars" in written.columns
    assert "competitor_institutions" in written.columns
    assert list(written["count"]) == sorted(written["count"], reverse=True)


# ---- leakage in event time: did competitors rise before closure? ----------

def _txn(n_acct=160, close_at="2026-03-15", rise_from=3):
    """Transactions for closers whose competitor spend RISES in the months
    before closing, and for open accounts that stay flat."""
    import numpy as np

    rows = []
    close = pd.Timestamp(close_at)
    for i in range(n_acct):
        closing = i % 2 == 0
        for back in range(12):
            month = close - pd.DateOffset(months=back)
            if closing and back < rise_from:
                amount = 400.0
            else:
                amount = 100.0
            rows.append([f"A{i}", month, "BIG BANK", amount])
    return pd.DataFrame(rows, columns=["acct", "date", "institution", "dollars"])


def _odd_for_txn(n_acct=160, close_at="2026-03-15"):
    rows = {"Acct Number": [f"A{i}" for i in range(n_acct)],
            "Date Opened": [pd.Timestamp(2015, 1, 1)] * n_acct,
            "Date Closed": [pd.Timestamp(close_at) if i % 2 == 0 else pd.NaT
                            for i in range(n_acct)]}
    return pd.DataFrame(rows)


def test_leakage_curve_detects_a_rise_before_closure():
    from ti.transaction_intelligence import leakage

    out = leakage.compute(_odd_for_txn(), _txn(), ANCHOR, lambda m: None)
    assert out["leak_divergence_month"] is not None, \
        "a manufactured pre-closure rise in competitor spend must be detected"


def test_leakage_declines_when_the_files_are_too_shallow():
    from ti.transaction_intelligence import leakage

    shallow = _txn()
    shallow = shallow[shallow["date"] >= pd.Timestamp("2026-01-01")]
    warned = []
    out = leakage.compute(_odd_for_txn(), shallow, ANCHOR, warned.append)
    assert "leak_curve" not in out
    assert any("month" in w for w in warned)


def test_leakage_reports_its_depth_and_window():
    from ti.transaction_intelligence import leakage

    out = leakage.compute(_odd_for_txn(), _txn(), ANCHOR, lambda m: None)
    assert out["leak_depth_months"] >= 6
    assert out["leak_window"] in (6, 12)
