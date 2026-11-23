"""Financial-services mail lists (fs-02): one list per category, one master, a blank CIF column,
the ODD's Mailable? flag, and the build setting lists_dir."""
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


def _txn():
    rows = [
        # acct, merchant, type, amount, date
        ("a1", "AFFIRM INC", "SIG", 40.0, "2026-10-20"),
        ("a1", "STATE FARM INS", "SIG", 120.0, "2026-10-02"),
        ("a2", "ADVANCE AMERICA", "SIG", 300.0, "2026-09-01"),
        ("a3", "VENMO PAYMENT", "SIG", 25.0, "2026-10-25"),
        ("a4", "WM SUPERCENTER", "PIN", 80.0, "2026-10-25"),
    ]
    df = pd.DataFrame(rows, columns=["primary_account_num", "merchant_name", "transaction_type",
                                     "amount", "transaction_date"])
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    return df


def _lenses():
    attrs = pd.DataFrame({"Mailable?": ["Yes", "No", "Yes"], "Branch": ["1", "2", "3"]},
                         index=["a1", "a2", "a3"])           # a4 is not in the ODD
    return Lenses(key_column="Acct Number", accounts=attrs.index, masks={}, attrs=attrs)


@pytest.fixture(scope="module")
def built(spec, tmp_path_factory):
    d = tmp_path_factory.mktemp("lists")
    out, outputs = F.compute(_txn(), _lenses(), spec, pd.Timestamp("2026-10-31"), d, lambda m: None)
    return d, out, outputs


def test_a_list_exists_for_every_category(spec, built):
    d, _, outputs = built
    assert set(outputs["finserv_lists"]) == set(spec["categories"])
    for name in spec["categories"]:
        assert (d / F._list_file(name)).is_file()


def test_an_empty_category_still_gets_its_header(built):
    d, _, _ = built
    f = pd.read_csv(d / F._list_file("Treasury/Bonds"))
    assert len(f) == 0 and "acct" in f.columns and "cif" in f.columns


def test_master_rows_equal_the_sum_of_the_lists(spec, built):
    d, _, outputs = built
    total = sum(len(pd.read_csv(p)) for p in outputs["finserv_lists"].values())
    master = pd.read_csv(outputs["finserv_master"])
    assert len(master) == total and total > 0


def test_no_account_twice_in_a_category(built):
    _, _, outputs = built
    m = pd.read_csv(outputs["finserv_master"])
    assert not m.duplicated(["acct_id", "list_type"]).any()


def test_master_columns_and_blank_cif(built):
    _, _, outputs = built
    m = pd.read_csv(outputs["finserv_master"], dtype=str, keep_default_na=False)
    assert list(m.columns) == F.MASTER_COLUMNS
    assert (m["cif"] == "").all()
    assert set(m["kind"]) <= {"leakage", "adjacency"}


def test_mailable_comes_from_the_odd_and_unknown_when_absent(built):
    _, _, outputs = built
    m = pd.read_csv(outputs["finserv_master"], dtype=str, keep_default_na=False)
    by = m.set_index("acct_id")["mailable"].to_dict()
    assert by["a1"] == "Yes" and by["a2"] == "No"
    assert "a4" not in by                                # a card purchase at Walmart is not leakage


def test_addressable_flag_follows_the_dictionary(spec, built):
    _, _, outputs = built
    m = pd.read_csv(outputs["finserv_master"], dtype=str, keep_default_na=False)
    for _, r in m.iterrows():
        want = "yes" if spec["categories"][r["list_type"]].get("addressable") else "no"
        assert r["addressable"] == want


def test_a_crosswalk_fills_the_cif(spec, tmp_path):
    cif = pd.Series({"a1": "C-1001", "a2": "C-1002"})
    _, outputs = F.compute(_txn(), _lenses(), spec, pd.Timestamp("2026-10-31"), tmp_path,
                           lambda m: None, cif_map=cif)
    m = pd.read_csv(outputs["finserv_master"], dtype=str, keep_default_na=False)
    got = m.groupby("acct_id")["cif"].agg(lambda s: set(s)).to_dict()      # a1 is in two categories
    assert got["a1"] == {"C-1001"} and got["a2"] == {"C-1002"} and got["a3"] == {""}


def test_an_account_missing_from_the_odd_is_unknown_not_blank(spec, tmp_path):
    attrs = pd.DataFrame({"Mailable?": ["Yes"]}, index=["a1"])
    lenses = Lenses(key_column="Acct Number", accounts=attrs.index, masks={}, attrs=attrs)
    _, outputs = F.compute(_txn(), lenses, spec, pd.Timestamp("2026-10-31"), tmp_path, lambda m: None)
    m = pd.read_csv(outputs["finserv_master"], dtype=str, keep_default_na=False).set_index("acct_id")
    assert m.loc["a3", "mailable"] == F.MAILABLE_UNKNOWN


def test_no_lists_dir_writes_nothing(spec):
    _, outputs = F.compute(_txn(), _lenses(), spec, pd.Timestamp("2026-10-31"), None, lambda m: None)
    assert "finserv_master" not in outputs and "finserv_lists" not in outputs


def test_the_build_sets_lists_dir():
    src = (ROOT / "build" / "ars_pipeline" / "ti_build.py").read_text(encoding="utf-8")
    assert 'ctx.shared["lists_dir"]' in src and 'lists_dir=out / "lists"' in src
