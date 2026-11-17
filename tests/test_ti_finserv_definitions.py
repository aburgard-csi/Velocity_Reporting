"""Financial-services definitions and coverage (fs-03): any vs addressable side by side with the
base, a coverage block, the full review queue file, and the build-log read-out."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build" / "ars_pipeline"))

from ti.transaction_intelligence import financial_services as F  # noqa: E402
from ti.transaction_intelligence import finserv_report  # noqa: E402
from ti.transaction_intelligence.lens import Lenses  # noqa: E402

DICT_DIR = ROOT / "build" / "ars_pipeline" / "ti" / "dictionaries"


@pytest.fixture(scope="module")
def spec():
    return F.load_patterns(DICT_DIR, {})


def _txn(transfers=False):
    rows = [
        ("a1", "AFFIRM INC", "SIG", 40.0, "2026-10-20"),          # leakage, addressable (BNPL)
        ("a1", "STATE FARM INS", "SIG", 120.0, "2026-10-02"),     # leakage, not addressable
        ("a2", "ADVANCE AMERICA", "SIG", 300.0, "2026-10-01"),    # leakage, addressable
        ("a3", "VENMO PAYMENT", "SIG", 25.0, "2026-10-25"),       # adjacency
        ("a4", "WM SUPERCENTER", "PIN", 80.0, "2026-10-25"),      # nothing
        ("a5", "ZZZ CREDIT UNION", "SIG", 60.0, "2026-10-12"),    # review queue candidate, unmatched
    ]
    df = pd.DataFrame(rows, columns=["primary_account_num", "merchant_name", "transaction_type",
                                     "amount", "transaction_date"])
    if transfers:
        df.loc[len(df)] = ["a1", "ACH DEBIT", "ACH", 500.0, "2026-10-05"]
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    return df


def _lenses():
    attrs = pd.DataFrame({"Mailable?": ["Yes"] * 5}, index=["a1", "a2", "a3", "a4", "a5"])
    return Lenses(key_column="Acct Number", accounts=attrs.index, masks={}, attrs=attrs)


def _run(spec, tmp, **kw):
    return F.compute(_txn(**kw), _lenses(), spec, pd.Timestamp("2026-10-31"), tmp, lambda m: None)


def test_definitions_put_any_and_addressable_side_by_side(spec, tmp_path):
    out, _ = _run(spec, tmp_path)
    d = out["fin_definitions"]
    assert d["base_accounts"] == 5 and d["file_accounts"] == 5
    assert d["any"]["accounts"] == 2 and d["addressable"]["accounts"] == 2    # a1 and a2
    assert d["any"]["dollars"] == 460 and d["addressable"]["dollars"] == 340
    assert d["adjacency"]["accounts"] == 1 and d["adjacency"]["dollars"] == 25


def test_definitions_agree_with_the_headline_figures(spec, tmp_path):
    out, _ = _run(spec, tmp_path)
    d = out["fin_definitions"]
    assert d["any"]["pct"] == out["fin_leaking_pct"]
    assert d["addressable"]["pct"] == out["fin_addressable_pct"]
    assert d["any"]["dollars"] == out["fin_leakage_dollars"]


def test_adjacency_is_never_inside_any(spec, tmp_path):
    out, _ = _run(spec, tmp_path)
    assert out["fin_definitions"]["any"]["accounts"] == out["fin_leaking_accounts"]


def test_coverage_counts_rows_and_dollars(spec, tmp_path):
    out, _ = _run(spec, tmp_path)
    c = out["fin_coverage"]
    assert c["rows"] == 6 and c["matched_rows"] == 4
    assert c["dollars"] == 625 and c["matched_dollars"] == 485
    assert c["matched_rows_pct"] == pytest.approx(66.7, abs=0.1)


def test_coverage_says_when_there_is_no_transfer_rail(spec, tmp_path):
    card_only, _ = _run(spec, tmp_path)
    with_transfers, _ = _run(spec, tmp_path, transfers=True)
    assert card_only["fin_coverage"]["wallet_share_available"] is False
    assert with_transfers["fin_coverage"]["wallet_share_available"] is True
    assert with_transfers["fin_coverage"]["transfer_rows"] == 1


def test_the_full_review_queue_is_written(spec, tmp_path):
    out, outputs = _run(spec, tmp_path)
    if "fin_review_queue" in out:
        f = pd.read_csv(outputs["finserv_review_queue"])
        assert list(f.columns) == ["descriptor", "txns", "dollars"]
        assert len(f) >= len(out["fin_review_queue"])


def test_no_lists_dir_no_review_file(spec):
    _, outputs = F.compute(_txn(), _lenses(), spec, pd.Timestamp("2026-10-31"), None, lambda m: None)
    assert "finserv_review_queue" not in outputs


def test_the_build_log_readout(spec, tmp_path):
    out, _ = _run(spec, tmp_path)
    text = "\n".join(finserv_report.lines(out))
    assert "any leakage" in text and "addressable" in text and "adjacency" in text and "coverage:" in text
    assert "no transfer rail" in text
