"""Financial services x named institution (fs-05): the product a named bank or credit union holds."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build" / "ars_pipeline"))

from ti.transaction_intelligence import competition as C  # noqa: E402
from ti.transaction_intelligence import financial_services as F  # noqa: E402
from ti.transaction_intelligence import institution_view as IV  # noqa: E402

DICT_DIR = ROOT / "build" / "ars_pipeline" / "ti" / "dictionaries"
CLIENT = {"LocalCompetitors": {"Nusenda Credit Union": ["NUSENDA CREDIT UNION", "NUSENDA CU", "NUSENDA FCU"]}}


def _txn():
    rows = [
        ("a1", "NUSENDA CU AUTO LOAN", "SIG", 400.0),     # product: auto loan; institution: Nusenda (local)
        ("a2", "NUSENDA CU LOAN PMT", "SIG", 250.0),      # generic loan at Nusenda
        ("a3", "CHASE AUTO", "SIG", 300.0),               # auto loan at a national bank
        ("a4", "AFFIRM INC", "SIG", 40.0),                # leakage, not a depository
        ("a5", "WM SUPERCENTER", "PIN", 80.0),            # nothing
        ("a1", "NUSENDA CU AUTO LOAN", "SIG", 400.0),     # same account, same pair: one account
    ]
    df = pd.DataFrame(rows, columns=["primary_account_num", "merchant_name", "transaction_type", "amount"])
    df["transaction_date"] = pd.Timestamp("2026-10-10")
    return df


@pytest.fixture(scope="module")
def built():
    df = _txn()
    fin_spec = F.load_patterns(DICT_DIR, CLIENT)
    rows = F.classify_rows(df, fin_spec)
    comp_spec = C.load_config(DICT_DIR, CLIENT)
    return IV.compute(df, rows, comp_spec), rows


def test_a_loan_at_a_local_credit_union_is_named(built):
    out, _ = built
    pairs = {(r[0], r[1]): r for r in out["fininst_matrix"]}
    assert any(inst == "Nusenda Credit Union" for _cat, inst in pairs)


def test_a_loan_at_a_national_bank_is_named(built):
    out, _ = built
    assert any(r[1] == "Chase" and r[0] == "Auto Loans" for r in out["fininst_matrix"])


def test_a_non_depository_is_not_named(built):
    out, _ = built
    assert not any("AFFIRM" in str(r[1]).upper() for r in out["fininst_matrix"])
    bnpl = next(r for r in out["fininst_by_category"] if r[0] == "Buy Now Pay Later")
    assert bnpl[2] == 0


def test_an_account_is_counted_once_per_pair(built):
    out, _ = built
    row = next(r for r in out["fininst_matrix"] if r[1] == "Nusenda Credit Union" and r[0] == "Auto Loans")
    assert row[3] == 1 and row[4] == 800                 # a1 twice: one account, $800


def test_by_category_shares(built):
    out, _ = built
    auto = next(r for r in out["fininst_by_category"] if r[0] == "Auto Loans")
    assert auto[1] == 2 and auto[2] == 2 and auto[3] == 100.0


def test_the_note_states_both_views_are_never_added(built):
    out, _ = built
    assert "never added" in out["fininst_note"]


def test_the_view_is_a_cross_tab_not_a_new_total(built):
    """Every pair's dollars are already inside the category's dollars: nothing is added on top."""
    out, _ = built
    for cat, _n, _h, _p, dollars, named_dollars in out["fininst_by_category"]:
        assert named_dollars <= dollars
        assert sum(r[4] for r in out["fininst_matrix"] if r[0] == cat) == named_dollars


def test_no_leakage_returns_nothing():
    df = _txn().iloc[[4]].reset_index(drop=True)
    fin_spec = F.load_patterns(DICT_DIR, CLIENT)
    out = IV.compute(df, F.classify_rows(df, fin_spec), C.load_config(DICT_DIR, CLIENT))
    assert out == {}


def test_the_section_is_registered_after_competition():
    src = (ROOT / "build" / "ars_pipeline" / "ti" / "chapters_txn.py").read_text(encoding="utf-8")
    assert "T.competition, T.institution_view" in src
