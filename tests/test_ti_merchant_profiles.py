# Ported from ARS v5 02-Scripts/tests/test_merchant_profiles.py at a491b5c (James Gilmore); logic unchanged.
"""merchant_profiles: every value counted by hand on a small card frame
(#258 group 3 -- rising and falling, the MCC codes, category breadth,
card use by member age and account tenure, time to first swipe).

    python -m pytest tests/test_merchant_profiles.py -q
"""
import pathlib
import sys

import pandas as pd
import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.transaction_intelligence import merchant_profiles as MP, merchants   # noqa: E402
from ti.transaction_intelligence.lens import Lenses                            # noqa: E402

CONFIG_DIR = __import__("ti.dictionaries", fromlist=["folder"]).folder()
ANCHOR = pd.Timestamp("2026-07-31")


def _rows(acct, key, typ, mcc, months, amount):
    return [(pd.Timestamp(2026, m, 15), acct, typ, amount, key, key, mcc) for m in months]


def make_frame() -> pd.DataFrame:
    r = []
    r += _rows("A1", "WALMART", "SIG", "5411", range(1, 8), 500.0)     # flat: 1500 vs 1500
    r += _rows("A1", "CHIPOTLE", "SIG", "5812", range(2, 8), 50.0)     # under $1k both windows
    r += _rows("A2", "AMAZON", "SIG", "5999", [2, 3, 4], 200.0)        # 600 -> 1200: riser
    r += _rows("A2", "AMAZON", "SIG", "5999", [5, 6, 7], 400.0)
    r += _rows("A3", "SHELL", "PIN", "5541", [2, 3, 4], 600.0)         # 1800 -> 900: faller
    r += _rows("A3", "SHELL", "PIN", "5541", [5, 6, 7], 300.0)
    r += _rows("A4", "NETFLIX", "SIG", "1", [5, 6, 7], 10.0)           # new, unmapped MCC
    r += _rows("B1", "COSTCO", "SIG", "5411", range(1, 8), 5000.0)     # business: outside the base
    return pd.DataFrame(r, columns=["transaction_date", "primary_account_num", "transaction_type",
                                    "amount", "merchant_name", "merchant_key", "mcc_code"])


def make_lenses() -> Lenses:
    ids = pd.Index(["A1", "A2", "A3", "A4", "A5", "B1"])
    personal = pd.Series([True] * 5 + [False], index=ids)
    masks = {"all": pd.Series(True, index=ids), "personal": personal, "business": ~personal}
    attrs = pd.DataFrame({
        "Account Holder Age": [30, 70, 45, None, 22, 50],
        "tenure_years": [0.5, 5.0, 12.0, 0.1, 0.3, 8.0],
        "Date Opened": pd.to_datetime(["2020-01-01", "2026-02-01", "2026-07-01",
                                       "2026-05-01", "2026-03-01", "2015-01-01"]),
    }, index=ids)
    return Lenses(key_column="Acct ID", accounts=ids, masks=masks, attrs=attrs)


@pytest.fixture(scope="module")
def run(monkeypatch_module):
    monkeypatch_module.setattr(MP, "MIN_BAND_ACCOUNTS", 2)
    lenses = make_lenses()
    warnings = []
    m = MP.compute(make_frame(), lenses, merchants.load_categories(CONFIG_DIR), ANCHOR,
                   warnings.append, account_filter=lenses.ids("personal"),
                   key_prefix="mch_", base_label="personal accounts")
    return m, warnings


@pytest.fixture(scope="module")
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


def test_rising_and_falling_between_two_trailing_windows(run):
    m, _ = run
    assert m["mch_growth_window"] == "May26-Jul26 against Feb26-Apr26"
    assert m["mch_growth"] == [["AMAZON", 1, 600, 1200, 600, 100.0],
                               ["SHELL", 1, 1800, 900, -900, -50.0]]
    assert m["mch_growth_ranked_n"] == 3          # Walmart, Amazon, Shell reach $1k in a window
    assert m["mch_growth_rising_n"] == 1
    assert m["mch_growth_falling_n"] == 1
    assert m["mch_growth_book_pct"] == -6.7       # 3780 against 4050, Netflix and Chipotle included


def test_growth_declines_under_six_months():
    df = make_frame()
    df = df[df["transaction_date"] >= pd.Timestamp(2026, 3, 1)]
    warnings = []
    m = MP.compute(df, None, merchants.load_categories(CONFIG_DIR), ANCHOR, warnings.append)
    assert "mch_growth" not in m
    assert any("needs 6" in w for w in warnings)


def test_mcc_codes_ranked_by_dollars_with_their_group(run):
    m, _ = run
    assert m["mch_mcc_top"][:3] == [[5411, "Grocery", 1, 7, 3500, 500.0, 42.0],
                                    [5541, "Fuel", 1, 6, 2700, 450.0, 32.4],
                                    [5999, "Retail", 1, 6, 1800, 300.0, 21.6]]
    assert m["mch_mcc_top"][-1][:2] == [1, "Other"]
    assert m["mch_mcc_distinct"] == 5
    assert m["mch_mcc_top5_share_pct"] == 100.0
    assert not any(r[0] == 5411 and r[4] > 3500 for r in m["mch_mcc_top"])   # Costco stayed out


def test_mcc_table_declines_when_the_feed_carries_no_mcc():
    df = make_frame()
    df["mcc_code"] = ""
    warnings = []
    m = MP.compute(df, None, merchants.load_categories(CONFIG_DIR), ANCHOR, warnings.append)
    assert "mch_mcc_top" not in m
    assert any("MCC on 0.0% of card rows" in w for w in warnings)


def test_category_breadth_counts_named_categories_per_account(run):
    m, _ = run
    assert m["mch_breadth_bands"] == [["none named", 1, 25.0, 30], ["1", 2, 50.0, 2250],
                                      ["2-3", 1, 25.0, 3800], ["4-5", 0, 0.0, 0],
                                      ["6+", 0, 0.0, 0]]
    assert m["mch_breadth_mean"] == 1.0
    assert m["mch_breadth_deep_pct"] == 0.0


def test_card_use_by_member_age(run):
    m, _ = run
    assert m["mch_by_age_columns"] == MP.BAND_COLUMNS
    assert m["mch_by_age"] == [["26-35", 1, 3800, 1.9, 292.31, "Grocery"],
                               ["36-45", 1, 2700, 0.9, 450.0, "Fuel"],
                               ["65+", 1, 1800, 0.9, 300.0, "Retail"]]


def test_card_use_by_account_tenure(run):
    m, _ = run
    assert [r[0] for r in m["mch_by_tenure"]] == ["< 3 mo", "3-12 mo", "3-10 yrs", "10+ yrs"]
    assert m["mch_by_tenure"][0] == ["< 3 mo", 1, 30, 0.4, 10.0, "Other"]   # Netflix only


def test_time_to_first_swipe_for_accounts_opened_in_the_window(run):
    m, _ = run
    assert m["mch_first_swipe_new_accounts"] == 3        # A2, A4, A5; A3 opened after the grace cutoff
    assert m["mch_first_swipe_bands"] == [["within 7 days", 0, 0.0], ["8-30 days", 2, 66.7],
                                          ["31-90 days", 0, 0.0], ["90+ days", 0, 0.0],
                                          ["no swipe yet", 1, 33.3]]
    assert m["mch_first_swipe_median_days"] == 14
    assert m["mch_first_swipe_within_30_pct"] == 66.7
    assert m["mch_first_swipe_window"] == "opened Jan26 - Jun26, 30 days' grace"


def test_band_cuts_decline_without_lenses_or_enough_accounts(monkeypatch):
    monkeypatch.setattr(MP, "MIN_BAND_ACCOUNTS", 20)
    warnings = []
    m = MP.compute(make_frame(), None, merchants.load_categories(CONFIG_DIR), ANCHOR,
                   warnings.append)
    assert "mch_by_age" not in m and "mch_first_swipe_bands" not in m
    assert any("no lenses" in w for w in warnings)
    lenses = make_lenses()
    warnings = []
    m = MP.compute(make_frame(), lenses, merchants.load_categories(CONFIG_DIR), ANCHOR,
                   warnings.append, account_filter=lenses.ids("personal"))
    assert "mch_by_age" not in m                        # four aged accounts, floor is twenty
    assert any("fewer than 20" in w for w in warnings)


def test_no_card_rows_skips_the_section():
    df = make_frame()
    df["transaction_type"] = "ACH"
    warnings = []
    assert MP.compute(df, None, {}, ANCHOR, warnings.append) == {}
    assert warnings == ["merchant_profiles: no card rows for all accounts; section skipped"]
