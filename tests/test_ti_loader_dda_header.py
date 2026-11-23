"""The 6.0.11.0 transaction export: a named header whose account column is "DDA Account", whose
description is "Description1", and whose rail ("PIN", "ACH", "CHK") is the first "External Transaction Code"
(a second column of that name carries the numeric code). Before the header map knew these names every file
of such a client parsed with no account and no transaction type on any row, and the cut read no card rows.

Synthetic rows only.

    python -m pytest tests/test_ti_loader_dda_header.py -q
"""
import pathlib
import sys

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.transaction_intelligence import loader  # noqa: E402

HEADER = ("Transaction Date\tDDA Account\tExternal Transaction Code\tTransaction Amount\tMCC Code\tDescription1\t"
          "Terminal Location 2\tTerminal ID Number\tMerchant ID Number\tInstitution Number\t"
          "Card Present Transaction\tExternal Transaction Code")
ACCT_A, ACCT_B = "A" * 40, "B" * 40


def _row(date, acct, rail, amount, desc, code):
    return f"{date}\t{acct}\t{rail}\t{amount}\t5411\t{desc}\t \t \t \t0\t \t{code}"


def _file(tmp_path):
    p = tmp_path / "9999_1_[2026.10.06][20.39.56]_debit card transaction monthly.csv"
    lines = ["9999|10/6/2026 8:39:56 PM|September 2026|1|Monthly Transaction File|6.0.11.0", HEADER,
             _row("9/16/2026", ACCT_A, "PIN", "12.50", "CORNER GROCER", 42),
             _row("9/17/2026", ACCT_A, "ACH", "300.00", "EXAMPLE LOAN SERVICER PMT", 46),
             _row("9/18/2026", ACCT_B, "CHK", "75.25", "CHECK 1001", 52)]
    p.write_text("\n".join(lines) + "\n", encoding="latin-1")
    return p


def test_the_header_names_are_mapped_and_the_second_code_column_is_the_transaction_code(tmp_path):
    skip, delim, names = loader._sniff(_file(tmp_path))
    assert (skip, delim) == (2, "\t")
    assert names[1] == "primary_account_num"
    assert names[2] == "transaction_type"
    assert names[5] == "merchant_name"
    assert names[-1] == "transaction_code"
    assert names.count("transaction_type") == 1 and names.count("primary_account_num") == 1


def test_every_row_carries_its_account_rail_and_description(tmp_path):
    rpt = loader.LoadReport()
    df = loader.read_file(_file(tmp_path), tmp_path / "cache", rpt)
    assert len(df) == 3
    assert df["primary_account_num"].notna().all()
    assert set(df["transaction_type"]) == {"PIN", "ACH", "CHK"}
    assert "EXAMPLE LOAN SERVICER PMT" in set(df["merchant_name"])


def test_a_cached_parse_with_no_accounts_is_discarded_and_the_raw_file_read_again(tmp_path):
    p, cache = _file(tmp_path), tmp_path / "cache"
    loader.read_file(p, cache, loader.LoadReport())
    (cached,) = list(cache.glob("*.parquet"))
    poisoned = pd.read_parquet(cached)
    poisoned["primary_account_num"] = None            # what an older loader wrote for this layout
    poisoned.to_parquet(cached)
    rpt = loader.LoadReport()
    df = loader.read_file(p, cache, rpt)
    assert df["primary_account_num"].notna().all()
    assert any("no accounts" in w for w in rpt.warnings)


def test_a_layout_with_one_account_header_is_unchanged():
    names = loader._names_from_header(["Transaction Date", "Primary Account Number", "Transaction Type",
                                       "Transaction Amount", "MCC Code", "Merchant Name"])
    assert names == ["transaction_date", "primary_account_num", "transaction_type", "amount", "mcc_code",
                     "merchant_name"]
