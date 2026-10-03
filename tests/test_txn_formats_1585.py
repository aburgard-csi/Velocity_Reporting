"""1585's monthlytransactions layout (issue #16, from the masked probe):

    line 1  pipe banner:  1585|2/2/2025 8:20:15 AM||30973|Monthly Transaction File|6.0.6.0
    line 2  'Report 1'
    line 3  TAB-delimited NAMED header row -- and the account column's header
            cell is a hash, not a name
    line 4+ tab-delimited data; NO Merchant Name column -- the description
            lives in Terminal Location 1 (city/phone in Terminal Location 2)

    python -m pytest tests/test_txn_formats_1585.py -q
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "build" / "ars_pipeline"), str(HERE.parent / "build")]

from engine.transaction_intelligence import loader  # noqa: E402

ACCT = "F123456789F1CA12345F1AE123456789D12EDC12"
HDR_HASH = "111B2E33DC444F55B6C77CF88ED999000BADEBC1"

HEADER = ("DDA Posting Date\t{h}\tTransaction Type\tTransaction Amount\t"
          "MCC Code\tTerminal Location 1\tTerminal Location 2\t"
          "Terminal ID Number\tMerchant ID Number\tInstitution\t"
          "Card Present Transaction\tDDA Tran Code").format(h=HDR_HASH)


def _write_1585(path):
    rows = [
        "1585|2/2/2025 8:20:15 AM||30973|Monthly Transaction File|6.0.6.0",
        "Report 1",
        HEADER,
        f"1/5/2025\t{ACCT}\tSIG\t12.34\t5411\tSQUARE PURCHASE  \t"
        f"WICKLIFFE\t\t\t3090\t\t101",
        f"1/6/2025\t{ACCT}\tSIG\t20.00\t5968\tPrime Video *ZD1KU2VN3\t"
        f"888-802-3080\t\t\t3090\t\t101",
    ]
    path.write_text("\n".join(rows) + "\n", encoding="latin-1")


def test_1585_named_header_layout_loads(tmp_path):
    raw = tmp_path / "1585_30973_[2025.02.02][08.20.15]_monthlytransactions.txt"
    _write_1585(raw)
    rpt = loader.LoadReport()
    frame = loader.read_file(raw, tmp_path / "_cache", rpt)
    assert len(frame) == 2
    assert frame["transaction_date"].notna().all()          # THE 2.86M-row bug
    assert frame["transaction_date"].iloc[0].month == 1
    assert set(frame["primary_account_num"]) == {ACCT}
    assert frame["amount"].tolist() == [12.34, 20.00]
    # no Merchant Name column: Terminal Location 1 is the description
    assert frame["merchant_name"].iloc[0] == "SQUARE PURCHASE"
    assert "Prime Video" in frame["merchant_name"].iloc[1]
    assert frame["mcc_code"].tolist() == ["5411", "5968"]


def test_1585_cached_after_first_read(tmp_path):
    raw = tmp_path / "1585_30973_[2025.02.02][08.20.15]_monthlytransactions.txt"
    _write_1585(raw)
    rpt = loader.LoadReport()
    loader.read_file(raw, tmp_path / "_cache", rpt)
    rpt2 = loader.LoadReport()
    frame = loader.read_file(raw, tmp_path / "_cache", rpt2)
    assert rpt2.cached == 1 and len(frame) == 2
    assert frame["transaction_date"].notna().all()


def test_1615_headerless_positional_layout_unchanged(tmp_path):
    raw = tmp_path / "1615_31004_[2026.04.05][07.16.16]_monthly_transactions_file_(debit).txt"
    rows = [
        "1615|4/5/2026 7:16:16 AM||31004|Monthly Transaction File|6.0.6.0",
        f"3/2/2026\t{ACCT}\tPIN\t45.00\t5411\tSTAR MARKET 100\t"
        f"BOSTON\tMA\tT1\tM1\t31004\tY\t205",
    ]
    raw.write_text("\n".join(rows) + "\n", encoding="latin-1")
    rpt = loader.LoadReport()
    frame = loader.read_file(raw, tmp_path / "_cache", rpt)
    assert len(frame) == 1
    assert frame["transaction_date"].notna().all()
    assert frame["merchant_name"].iloc[0] == "STAR MARKET 100"   # position 6
    assert frame["amount"].iloc[0] == 45.00


# ---------------------------------------------------------------------------
# NaN amounts (1585 run, issue #16): a row with a valid date but a blank
# amount must not kill financial_services / competition -- numpy sums do
# not skip NaN and round(nan) raises "cannot convert float NaN to integer".
# ---------------------------------------------------------------------------

def _nan_amount_frame():
    import pandas as pd
    from engine.transaction_intelligence.merchant import merchant_key
    df = pd.DataFrame({
        "transaction_date": pd.to_datetime(["2026-06-10"] * 4),
        "primary_account_num": ["A1", "A2", "A3", "A1"],
        "transaction_type": ["SIG", "SIG", "ACH", "ACH"],
        "amount": [20.0, None, 45.0, None],
        "mcc_code": ["5411"] * 4,
        "merchant_name": ["ROBINHOOD", "ROBINHOOD",
                          "CHASE CREDIT CRD PYMT", "CHASE CREDIT CRD PYMT"],
        "merchant_id": [""] * 4, "card_present": [""] * 4})
    df["merchant_key"] = merchant_key(df["merchant_name"])
    return df


def _tiny_lenses():
    import pandas as pd
    from engine.transaction_intelligence.lens import Lenses
    ids = pd.Index(["A1", "A2", "A3"])
    return Lenses(key_column="Acct ID", accounts=ids,
                  masks={"all": pd.Series(True, index=ids),
                         "personal": pd.Series(True, index=ids)},
                  attrs=pd.DataFrame({"Curr Bal": [1.0, 2.0, 3.0],
                                      "Avg Bal": [1.0, 2.0, 3.0]}, index=ids))


def test_fin_survives_nan_amounts():
    import pandas as pd
    from engine.transaction_intelligence import financial_services as fin
    CONFIG_DIR = HERE.parent / "build" / "ars_pipeline" / "engine" / "config"
    df, lenses = _nan_amount_frame(), _tiny_lenses()
    spec = fin.load_patterns(CONFIG_DIR, {"SelfNames": ["FCB"]})
    rows = fin.classify_rows(df, spec)
    m, _ = fin.compute(df, lenses, spec, pd.Timestamp("2026-06-30"), None,
                       lambda w: None, account_filter=lenses.ids("personal"),
                       key_prefix="fin_", base_label="p", classification=rows)
    # the NaN amount counts as $0, the row still counts as a transaction
    assert m["fin_leakage_dollars"] == 45
    cc = {r[0]: r for r in m["fin_by_category"]}["Credit Cards"]
    assert cc[3] == 2                                     # txns include the blank-amount row


def test_competition_survives_nan_amounts():
    import pandas as pd
    from engine.transaction_intelligence import competition
    CONFIG_DIR = HERE.parent / "build" / "ars_pipeline" / "engine" / "config"
    df, lenses = _nan_amount_frame(), _tiny_lenses()
    cspec = competition.load_config(CONFIG_DIR, {"SelfNames": ["FCB"]})
    m, _ = competition.compute(df, lenses, cspec, None, pd.Timestamp("2026-06-30"),
                               None, lambda w: None,
                               account_filter=lenses.ids("personal"),
                               key_prefix="comp_", base_label="p")
    # Chase $45 (ACH) + Robinhood $20 (card rail counts for competitors)
    assert m["comp_competitor_dollars"] == 65
    chase = {r[0]: r for r in m["comp_institutions"]}["Chase"]
    assert chase[4] == 2                                  # both txns counted
