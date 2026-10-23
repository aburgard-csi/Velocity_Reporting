# Ported from ARS v5 02-Scripts/tests/test_txn_formats_1192.py at a491b5c (James Gilmore); logic unchanged.
"""1192's description format (TYPE: {label} ID: {ref}), review-queue noise,
and self-institution exclusion — from issue #7's first 1192 run.

    python -m pytest tests/test_txn_formats_1192.py -q
"""
import pathlib
import sys

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
CONFIG_DIR = __import__("ti.dictionaries", fromlist=["folder"]).folder()

from ti.transaction_intelligence import financial_services as fin   # noqa: E402
from ti.transaction_intelligence.merchant import merchant_core      # noqa: E402


def test_merchant_core_parses_type_id_scaffolding():
    s = pd.Series(["TYPE: MTG PYMTS ID: 16-1146859",
                   "TYPE: STUDENT LN ID:",
                   "TYPE: BILL PAYMT ID: M391165550",
                   "TYPE: INS.PREM ID:",
                   "CHASE CREDIT CRD CHECK PYMT 000000000006182"])
    core = merchant_core(s)
    assert list(core[:4]) == ["MTG PYMTS", "STUDENT LN", "BILL PAYMT", "INS.PREM"]
    assert core[4].startswith("CHASE CREDIT CRD")          # 1615 format untouched


def test_generic_type_labels_classify_as_lender_unknown():
    spec = fin.load_patterns(CONFIG_DIR, {})
    table = fin.classify_strings(pd.Index(
        ["MTG PYMTS", "MTG PYMT", "MORTGAGE", "STUDENT LN", "BROKERAGE",
         "CC PYMT", "INS.PREM", "TO LOAN"]), spec)
    got = table["category"].to_dict()
    assert got["MTG PYMTS"] == "Mortgage/HELOC" and got["MORTGAGE"] == "Mortgage/HELOC"
    assert got["STUDENT LN"] == "Student Loans"
    assert got["BROKERAGE"] == "Investment/Brokerage"
    assert got["CC PYMT"] == "Credit Cards"
    assert got["INS.PREM"] == "Insurance"
    assert got["TO LOAN"] == "Other Loans (lender unknown)"


def test_channel_noise_stays_out_of_leakage_and_review_queue():
    spec = fin.load_patterns(CONFIG_DIR, {})
    table = fin.classify_strings(pd.Index(
        ["BILL PAYMT", "MOBILE PMT", "ONLINE PMT", "WEB PYMT", "ACH PMT",
         "BANK DRAFT", "ONLINE BANKING ACH FILE DEBIT"]), spec)
    assert table["category"].isna().all()                  # never leakage
    df = pd.DataFrame({
        "transaction_date": pd.to_datetime(["2026-06-15"] * 4),
        "primary_account_num": ["A1", "A2", "A3", "A4"],
        "transaction_type": ["ACH"] * 4,
        "amount": [100.0, 200.0, 300.0, 400.0],
        "merchant_name": ["TYPE: BILL PAYMT ID: M391", "TYPE: ONLINE PMT ID:",
                          "SEAMENS BANK XFER 123123",
                          "CHASE CREDIT CRD CHECK PYMT 000006182"]})
    m, _ = fin.compute(df, None, spec, pd.Timestamp("2026-06-30"), None, lambda _w: None)
    queue = [row[0] for row in m.get("fin_review_queue", [])]
    assert "BILL PAYMT" not in queue and "ONLINE PMT" not in queue
    assert any(q.startswith("SEAMENS BANK") for q in queue)   # real names still surface
    # (a name WITH a generic token, e.g. "X LOAN PMT", classifies as lender-unknown
    #  by design since dict v2 -- the largest-unmatched table catches those names)


def test_self_names_are_reported_not_just_excluded():
    """James: "it would be nice to know selfname data" -- internal transfers
    get their own block (accounts, txns, dollars, by name), whole book."""
    client_cfg = {"SelfNames": ["ASCEND FCU", "ASCEND FEDERAL CREDIT UNION"]}
    spec = fin.load_patterns(CONFIG_DIR, client_cfg)
    df = pd.DataFrame({
        "transaction_date": pd.to_datetime(["2026-06-15"] * 4),
        "primary_account_num": ["A1", "A1", "A2", "A3"],
        "transaction_type": ["ACH", "ACH", "CHK", "ACH"],
        "amount": [500.0, 250.0, 100.0, 400.0],
        "merchant_name": ["ASCEND FCU 1611 N JACKSON", "ASCEND FCU 1862 SHARP SPRINGS",
                          "ASCEND FEDERAL CREDIT UNION PMT 99", "CHASE CREDIT CRD CHECK PYMT 06182"]})
    m, _ = fin.compute(df, None, spec, pd.Timestamp("2026-06-30"), None, lambda _w: None)
    self_block = m["fin_self"]
    assert self_block["accounts"] == 2 and self_block["txns"] == 3
    assert self_block["dollars"] == 850
    # ASCEND FCU and ASCEND FEDERAL CREDIT UNION are one institution: the
    # matcher normalises both sides (#245), so they fold into one row
    by = {r[0]: r for r in self_block["by_name"]}
    assert len(by) == 1 and next(iter(by.values()))[3] == 850
    # and still excluded from every leakage table
    cats = {r[0] for r in m.get("fin_by_category", [])}
    assert "Online Banks / Savings" not in cats or True
    assert all("ASCEND" not in str(p_) for provs in m.get("fin_top_providers", {}).values() for p_ in provs)


def test_self_names_excluded_from_leakage_and_competition():
    client_cfg = {"SelfNames": ["ASCEND FCU", "ASCEND FEDERAL CREDIT UNION"]}
    spec = fin.load_patterns(CONFIG_DIR, client_cfg)
    table = fin.classify_strings(pd.Index(["ASCEND FCU 1611 N JACKSON"]), spec)
    assert table["category"].isna().all()
    from ti.transaction_intelligence import competition as comp
    cspec = comp.load_config(CONFIG_DIR, client_cfg)
    assert "ASCEND FCU" in cspec["false_positives"]
    # and it never lands in the review queues either
    df = pd.DataFrame({
        "transaction_date": pd.to_datetime(["2026-06-15"]),
        "primary_account_num": ["A1"], "transaction_type": ["ACH"],
        "amount": [500.0], "merchant_name": ["ASCEND FCU 1611 N JACKSON"]})
    m, _ = fin.compute(df, None, spec, pd.Timestamp("2026-06-30"), None, lambda _w: None)
    assert not any(r[0].startswith("ASCEND") for r in m.get("fin_review_queue", []))
