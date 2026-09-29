"""The transaction file joins the ODD through ONE reading of an account id (2026-09-29).

1441 FNB Alaska, first real-data run: 10,928,371 rows read, 0 accounts joined. Two causes,
both on the reader: the file names its account column "DDA Account", which the loader did
not know, so every account read as None; and the ODD id column was chosen by presence
("Acct Number" first) in three places, never by what actually matched. Now the loader knows
the 1441 header, txn_common.norm_accounts is the one spelling of an id on both sides, and
txn_common.odd_account_key picks the ODD column that matches the file, once, for every chapter.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build" / "ars_pipeline"), str(REPO / "build")]
from engine.transaction_intelligence import loader, txn_common as T  # noqa: E402

HASH_A = "EB03DF098E8BB1637CDD6BA5D55A69C48E559F32"
HASH_B = "B5B70DD484C90A225FFD71995492040631BB3B8B"

# The 1441 file's own first three lines (banner, named header, one row), tab-delimited.
BANNER = "1441|7/7/2025 11:23:42 AM|June 2025|16286|Transaction File|6.0.11.0"
HEADER = "\t".join(["Transaction Date", "DDA Account", "External Transaction Code", "Transaction Amount",
                    "MCC Code", "Description1", "Terminal Location 2", "Terminal ID Number",
                    "Merchant ID Number", "Institution Number", "Card Present Transaction",
                    "External Transaction Code"])
ROW = "\t".join(["6/17/2025", HASH_A, "CHK", "3000", "", "", "", "", "", "0", "", "52"])
ROW2 = "\t".join(["6/18/2025", HASH_B, "SIG", "42.10", "5411", "SAFEWAY 1234", "ANCHORAGE AK", "", "", "0", "Y", "12"])


def test_norm_accounts_is_one_spelling_on_both_sides():
    out = T.norm_accounts([" 000123.0 ", "123", "0", "", HASH_A.lower(), "00A1"])
    assert out.tolist() == ["123", "123", "0", "", HASH_A.lower(), "00A1"]


def test_the_1441_header_is_recognised_and_the_account_is_the_hash(tmp_path):
    p = tmp_path / "1441_16286_[2025.07.07][11.23.42]_debit card transaction monthly.csv"
    p.write_bytes(("\n".join([BANNER, HEADER, ROW, ROW2]) + "\n").encode("latin-1"))
    skip, delim, names = loader._sniff(p)
    assert (skip, delim) == (2, "\t")
    assert names[:6] == ["transaction_date", "primary_account_num", "transaction_type", "amount",
                         "mcc_code", "merchant_name"]
    assert names[-1] == "transaction_code" and names.count("transaction_type") == 1
    rpt = loader.LoadReport()
    df = loader.read_file(p, tmp_path / "cache", rpt)
    assert df["primary_account_num"].tolist() == [HASH_A, HASH_B]
    assert df["transaction_type"].tolist() == ["CHK", "SIG"]
    assert df["amount"].tolist() == [3000.0, 42.10]


def _odd(**cols):
    return pd.DataFrame(cols)


def test_the_odd_key_is_the_column_that_matches_the_file_not_the_first_present():
    odd = _odd(**{"Acct ID": ["5", "16"], " Acct Number": [HASH_B, HASH_A], "Branch": ["1", "1"]})
    key, ids, info = T.odd_account_key(odd, [HASH_A, HASH_B])
    assert key == " Acct Number" and ids.tolist() == [HASH_B, HASH_A]
    assert dict((c, m) for c, m in info["txn_odd_join_candidates"]) == {"Acct ID": 0, " Acct Number": 2}


def test_a_hash_column_under_another_name_is_found_when_the_file_is_hashed():
    odd = _odd(**{"Acct Number": ["5", "16"], "Acct Hash": [HASH_A, HASH_B]})
    key, _, _ = T.odd_account_key(odd, [HASH_A, HASH_B])
    assert key == "Acct Hash"


def test_leading_zeros_and_float_tails_do_not_break_a_numeric_join():
    odd = _odd(**{"Acct Number": ["0001234", "5678.0"]})
    key, ids, info = T.odd_account_key(odd, ["1234", "5678"])
    assert key == "Acct Number" and info["txn_odd_join_candidates"] == [["Acct Number", 2]]


def test_nothing_matching_is_said_not_hidden():
    notes = []
    odd = _odd(**{"Acct Number": ["1", "2"]})
    key, _, _ = T.odd_account_key(odd, [HASH_A], warn=notes.append)
    assert key == "Acct Number" and notes and "spell accounts differently" in notes[0]


def test_the_run_passes_one_key_to_every_chapter():
    src = (REPO / "build" / "ars_pipeline" / "engine" / "transaction_intelligence" / "run.py").read_text(encoding="utf-8")
    assert src.count("acct_key=acct_key") == 3          # portfolio, lens, leakage
    for mod in ("lens.py", "leakage.py", "portfolio.py"):
        text = (REPO / "build" / "ars_pipeline" / "engine" / "transaction_intelligence" / mod).read_text(encoding="utf-8")
        assert '"Acct Number" if "Acct Number" in' not in text and 'for c in ("Acct Number"' not in text, mod


def test_an_unknown_account_header_is_reported_not_read_as_none(tmp_path):
    p = tmp_path / "x_debit card transaction monthly.csv"
    hdr = HEADER.replace("DDA Account", "Cardholder Ref")
    p.write_bytes(("\n".join([BANNER, hdr, ROW]) + "\n").encode("latin-1"))
    rpt = loader.LoadReport()
    loader.read_file(p, tmp_path / "cache", rpt)
    assert any("no account column the loader knows" in w for w in rpt.warnings), rpt.warnings
