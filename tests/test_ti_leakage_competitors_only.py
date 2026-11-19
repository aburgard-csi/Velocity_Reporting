"""The pre-closure leakage curve ("Competitor spend before closure") reads
named competitors only, and joins the ODD with the same account key as the
lenses.

    python -m pytest tests/test_ti_leakage_competitors_only.py -q
"""
import pathlib
import sys

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.transaction_intelligence import competition, financial_services, leakage  # noqa: E402
from ti.transaction_intelligence.lens import account_ids                           # noqa: E402
from test_ti_competition import ANCHOR, CLIENT_CFG, CONFIG_DIR, make_lenses       # noqa: E402
from test_ti_competition_family import make_frame                                 # noqa: E402
from test_ti_stressors_txn import ANCHOR as MONTH, _odd_for_txn, _txn             # noqa: E402


def test_the_curve_feed_carries_competitors_not_payment_apps(tmp_path):
    df, lenses = make_frame(), make_lenses()
    spec = competition.load_config(CONFIG_DIR, CLIENT_CFG)
    fin_rows = financial_services.classify_rows(df, financial_services.load_patterns(CONFIG_DIR, CLIENT_CFG))
    m, _ = competition.compute(df, lenses, spec, fin_rows, ANCHOR, tmp_path, lambda *a: None,
                               account_filter=lenses.ids("personal"), key_prefix="comp_",
                               base_label="personal accounts")
    monthly = m["_competitor_monthly"]
    # A5 pays only Venmo and Affirm: a payment app and a BNPL lender, neither a competitor
    assert "A5" not in set(monthly["acct"])
    assert {"A1", "A4", "A7"} <= set(monthly["acct"])
    # every dollar in the feed is a competitor dollar
    a1 = df[(df["primary_account_num"] == "A1") & df["merchant_name"].str.startswith("CHASE")]
    assert monthly[monthly["acct"] == "A1"]["dollars"].sum() == a1["amount"].abs().sum()


def test_account_ids_strip_a_float_read_id():
    odd = pd.DataFrame({"Acct Number": [" 1000.0", "1001", "A7.0x"]})
    assert account_ids(odd).tolist() == ["1000", "1001", "A7.0x"]
    assert account_ids(pd.DataFrame({"x": [1]})) is None


def test_a_float_read_odd_id_still_joins_the_curve():
    txn = _txn()
    txn["acct"] = txn["acct"].str[1:].astype(int).add(1000).astype(str)       # "1000", "1001", ...
    odd = _odd_for_txn()
    odd["Acct Number"] = odd["Acct Number"].str[1:].astype(int).add(1000).astype(float)  # 1000.0 ...
    out = leakage.compute(odd, txn, MONTH, lambda m: None)
    assert out["leak_divergence_month"] is not None, \
        "a float-read ODD id must join the transaction file's account number"
