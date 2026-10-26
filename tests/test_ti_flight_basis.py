# Ported from ARS v5 02-Scripts/tests/test_flight_basis.py at a491b5c (James Gilmore); logic unchanged.
"""Deposit flight on the deposits file, not on a balance proxy.

    python -m pytest tests/test_flight_basis.py -q

balance.py admits its own limit: `Curr Bal - Avg Bal` is a trend proxy, not
a time series. Once the deposits file is present the chapter has the real
series, and 'flight' means the credits are falling. The proxy count is still
emitted beside it, every run, so the size of the change is never a guess.
"""
import pathlib
import sys

import pandas as pd


from ti.core.periods import Month
from ti.core.subsets import build_subsets
from ti.monthly_analysis import balance
from ti.core.deposits import monthly

ANCHOR = Month.from_tag("Jul26")


def _odd(n=6):
    return pd.DataFrame({
        "Acct Number": [f"A{i}" for i in range(n)],
        "Debit?": ["Yes"] * n,
        "Curr Bal": [30_000.0] * n,
        "Avg Bal": [35_000.0 if i % 2 == 0 else 25_000.0 for i in range(n)],
        **{f"{m}26 Spend": [100.0] * n
           for m in ("Feb", "Mar", "Apr", "May", "Jun", "Jul")},
    })


def _deposits(n=6):
    rows = []
    for i in range(n):
        for k in range(6):
            amount = 900.0 if (k < 3 or i % 3) else 300.0
            rows.append([f"A{i}", pd.Timestamp("2026-02-15") + pd.DateOffset(months=k),
                         1, amount])
    return pd.DataFrame(rows, columns=["acct", "date", "dep_count", "dep_amount"])


def test_without_the_file_flight_is_the_balance_proxy_and_says_so():
    out = balance.compute(build_subsets(_odd(), {}, ANCHOR), {}, lambda m: None)
    assert out["flight_risk_basis"] == "balance proxy"
    assert out["flight_risk_n"] == 3 == out["flight_risk_proxy_n"]


def test_with_the_file_flight_is_real_inflow_decline_and_the_proxy_is_kept():
    raw = _deposits()
    out = balance.compute(build_subsets(_odd(), {}, ANCHOR),
                          {"_deposit_raw": raw, "_deposit_monthly": monthly(raw)},
                          lambda m: None)
    assert out["flight_risk_basis"] == "inflow"
    # A0 and A3 are paid less; both hold a high balance.
    assert out["flight_risk_n"] == 2
    assert out["flight_risk_proxy_n"] == 3
