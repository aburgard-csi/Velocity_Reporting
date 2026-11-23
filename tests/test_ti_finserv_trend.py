"""Financial-services monthly trend and products held (fs-04)."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build" / "ars_pipeline"))

from ti.transaction_intelligence import financial_services as F  # noqa: E402
from ti.transaction_intelligence.lens import Lenses  # noqa: E402

DICT_DIR = ROOT / "build" / "ars_pipeline" / "ti" / "dictionaries"


@pytest.fixture(scope="module")
def spec():
    return F.load_patterns(DICT_DIR, {})


def _txn(n_months):
    """Six accounts pay Affirm each month; the amount doubles in the last three months."""
    rows = []
    months = pd.period_range(end="2026-10", periods=n_months, freq="M")
    for i, p in enumerate(months):
        late = i >= n_months - 3
        for a in range(6):
            rows.append((f"a{a}", "AFFIRM INC", "SIG", 100.0 if late else 50.0, p.to_timestamp() + pd.Timedelta(days=9)))
        rows.append(("z", "WM SUPERCENTER", "PIN", 20.0, p.to_timestamp() + pd.Timedelta(days=3)))
    df = pd.DataFrame(rows, columns=["primary_account_num", "merchant_name", "transaction_type",
                                     "amount", "transaction_date"])
    return df


def _lenses(n=60):
    ids = [f"a{i}" for i in range(6)] + [f"p{i}" for i in range(n)] + ["z"]
    attrs = pd.DataFrame({"Mailable?": "Yes", "Prod Desc": "Basic Checking"}, index=ids)
    return Lenses(key_column="Acct Number", accounts=attrs.index, masks={}, attrs=attrs)


def _run(spec, n_months):
    return F.compute(_txn(n_months), _lenses(), spec, pd.Timestamp("2026-10-31"), None, lambda m: None)[0]


def test_months_and_series_cover_the_window(spec):
    out = _run(spec, 12)
    assert len(out["fin_months"]) == 12 and out["fin_months"][-1] == "2026-10"
    s = out["fin_monthly"]["Buy Now Pay Later"]
    assert len(s) == 12 and s[0][1] == 6 and s[0][2] == 300 and s[-1][2] == 600


def test_trend_is_last_three_against_prior_three(spec):
    out = _run(spec, 12)
    row = next(r for r in out["fin_trend"] if r[0] == "Buy Now Pay Later")
    assert row[1] == 1800 and row[2] == 900 and row[3] == 100.0


def test_peak_month_needs_a_year_of_data(spec):
    assert next(r for r in _run(spec, 12)["fin_trend"] if r[0] == "Buy Now Pay Later")[4] is not None
    assert next(r for r in _run(spec, 8)["fin_trend"] if r[0] == "Buy Now Pay Later")[4] is None


def test_under_six_months_gives_a_series_but_no_trend(spec):
    out = _run(spec, 4)
    assert "fin_monthly" in out and "fin_trend" not in out


def test_a_category_absent_in_a_month_reads_zero_not_missing(spec):
    df = _txn(12)
    df = df[~((df.merchant_name == "AFFIRM INC") & (df.transaction_date.dt.month == 6))]
    out = F.compute(df, _lenses(), spec, pd.Timestamp("2026-10-31"), None, lambda m: None)[0]
    s = dict((r[0], r) for r in out["fin_monthly"]["Buy Now Pay Later"])
    assert s["2026-06"] == ["2026-06", 0, 0]


def test_products_held_needs_twenty_leakers(spec):
    assert "fin_leakers_hold" in _run(spec, 12)            # 6 leakers: below the threshold
    assert _run(spec, 12)["fin_leakers_hold"] == []


def test_products_held_lists_the_top_products(spec):
    rows = [(f"b{i}", "AFFIRM INC", "SIG", 40.0, pd.Timestamp("2026-10-10")) for i in range(25)]
    df = pd.DataFrame(rows, columns=["primary_account_num", "merchant_name", "transaction_type",
                                     "amount", "transaction_date"])
    prod = ["Basic Checking"] * 15 + ["Premier Checking"] * 10
    attrs = pd.DataFrame({"Mailable?": "Yes", "Prod Desc": prod}, index=[f"b{i}" for i in range(25)])
    lens = Lenses(key_column="Acct Number", accounts=attrs.index, masks={}, attrs=attrs)
    out = F.compute(df, lens, spec, pd.Timestamp("2026-10-31"), None, lambda m: None)[0]
    cat, n, top = next(r for r in out["fin_leakers_hold"] if r[0] == "Buy Now Pay Later")
    assert n == 25 and top == [["Basic Checking", 15], ["Premier Checking", 10]]
