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
    assert "T.competition_layers, T.institution_view" in src      # after the layers: it reads their matches


# ---------------------------------------------------------------- the registry path (fs-09)
def _layer_sub(df, rows, inst_by_core):
    """What competition_layers.classify_cards returns for these rows: one row per card transaction."""
    mask = rows["is_card"].to_numpy()
    sub = pd.DataFrame({"acct": df["primary_account_num"].astype(str)[mask].to_numpy(),
                        "amt": df["amount"].abs()[mask].to_numpy(), "core": rows["core"][mask].to_numpy()})
    sub["inst"] = sub["core"].map(lambda c: inst_by_core.get(c, (None, None))[0])
    sub["tier"] = sub["core"].map(lambda c: inst_by_core.get(c, (None, None))[1])
    return sub


def _registry_case():
    df = _txn()
    rows = F.classify_rows(df, F.load_patterns(DICT_DIR, CLIENT))
    by_core = {}
    for core in rows["core"].unique():
        if "NUSENDA" in core:
            by_core[core] = ("Nusenda Credit Union", "Local")
        elif "CHASE" in core:
            by_core[core] = ("Chase", "National")
    return df, rows, by_core


def test_the_registry_names_the_institution_and_its_tier():
    df, rows, by_core = _registry_case()
    out = IV.compute_from_layers(df, rows, _layer_sub(df, rows, by_core))
    assert out["fininst_source"] == "registry"
    assert any(r[1] == "Nusenda Credit Union" and r[2] == "Local" for r in out["fininst_matrix"])
    assert any(r[1] == "Chase" and r[2] == "National" for r in out["fininst_matrix"])


def test_an_ambiguous_name_is_not_named():
    df, rows, by_core = _registry_case()
    by_core = {c: (i, IV.UNRESOLVED) for c, (i, t) in by_core.items()}
    out = IV.compute_from_layers(df, rows, _layer_sub(df, rows, by_core))
    assert out["fininst_named_accounts"] == 0
    assert all(r[2] == 0 for r in out["fininst_by_category"])


def test_rows_that_do_not_line_up_say_nothing():
    df, rows, by_core = _registry_case()
    sub = _layer_sub(df, rows, by_core).iloc[:-1]
    assert IV.compute_from_layers(df, rows, sub) == {}


def test_the_registry_path_is_still_a_cross_tab_not_a_new_total():
    df, rows, by_core = _registry_case()
    out = IV.compute_from_layers(df, rows, _layer_sub(df, rows, by_core))
    for cat, _n, _h, _p, dollars, named_dollars in out["fininst_by_category"]:
        assert named_dollars <= dollars
        assert sum(r[4] for r in out["fininst_matrix"] if r[0] == cat) == named_dollars


def test_the_configured_path_says_so(built):
    out, _ = built
    assert out["fininst_source"] == "configured"


def test_the_section_prefers_the_registry_and_falls_back(monkeypatch):
    import types
    from ti import txn_sections as T
    df, rows, by_core = _registry_case()
    ctx = types.SimpleNamespace(txn=df, shared={"fin_rows": rows, "comp_spec": C.load_config(DICT_DIR, CLIENT),
                                                "personal": None, "business": None, "base_label": "x"})
    monkeypatch.setattr(T, "base_accounts", lambda c: (None, None, "x"))
    assert T.institution_view(ctx)["fininst_source"] == "configured"           # no layers ran
    ctx.shared["cl_parts"] = (_layer_sub(df, rows, by_core), None, None, None)
    assert T.institution_view(ctx)["fininst_source"] == "registry"
    ctx.shared["cl_parts"] = (_layer_sub(df, rows, by_core).iloc[:-1], None, None, None)
    assert T.institution_view(ctx)["fininst_source"] == "configured"           # misaligned: fall back
