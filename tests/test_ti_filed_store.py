# Ported from ARS v5 02-Scripts/tests/test_filed_store.py at a491b5c (James Gilmore); logic unchanged.
"""The Filed store turns two regulators' cache files into one quarterly series per key."""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from ti.core.filed.store import FiledStore  # noqa: E402


def _cache(tmp_path):
    (tmp_path / "fdic_financials.json").write_text(json.dumps([
        {"CERT": 12, "REPDTE": "20250331", "ASSET": 900_000, "DEP": 700_000, "LNLSNET": 500_000, "ROA": 0.9, "EQV": 9.0, "NETINC": 2_000},
        {"CERT": 12, "REPDTE": "20260331", "ASSET": 1_000_000, "DEP": 800_000, "LNLSNET": 520_000, "ROA": 1.1, "EQV": 10.0, "NETINC": 2_500},
    ]), encoding="utf-8")
    (tmp_path / "fdic_institutions.json").write_text(json.dumps([
        {"CERT": 12, "NAME": "FIRST TEST BANK", "REGAGNT": "OCC", "BKCLASS": "N", "CHRTAGNT": "OCC"},
    ]), encoding="utf-8")
    (tmp_path / "ncua_financials.json").write_text(json.dumps([
        {"CU_NUMBER": "7", "CYCLE_DATE": "3/31/2025", "ACCT_010": "400000", "ACCT_018": "350000", "ACCT_025B": "200000", "ACCT_997": "40000"},
        {"CU_NUMBER": "7", "CYCLE_DATE": "3/31/2026", "ACCT_010": "440000", "ACCT_018": "380000", "ACCT_025B": "230000", "ACCT_997": "44000"},
    ]), encoding="utf-8")
    (tmp_path / "ncua_institutions.json").write_text(json.dumps([
        {"CU_NUMBER": "7", "CU_NAME": "TEST FCU", "CU_TYPE": "1", "CharterState": "CA"},
    ]), encoding="utf-8")
    return tmp_path


def test_fdic_series_is_oldest_first_in_dollars(tmp_path):
    s = FiledStore(_cache(tmp_path)).series("fdic:12")
    assert [q.date for q in s] == ["2025-03-31", "2026-03-31"]
    assert s[-1].deposits == 800_000_000     # FDIC reports thousands
    assert s[-1].roa == 1.1


def test_ncua_series_parses_the_slash_date_and_dollars(tmp_path):
    s = FiledStore(_cache(tmp_path)).series("ncua:7")
    assert s[0].date == "2025-03-31"
    assert s[-1].deposits == 380_000        # NCUA reports dollars
    assert s[-1].roa is None


def test_unknown_key_is_empty_not_an_error(tmp_path):
    assert FiledStore(_cache(tmp_path)).series("fdic:999") == []


def test_regulator_comes_from_the_widened_pull(tmp_path):
    store = FiledStore(_cache(tmp_path))
    assert store.regulator("fdic:12") == "OCC"
    assert store.regulator("ncua:7") == "NCUA"


def test_missing_cache_file_gives_an_empty_store(tmp_path):
    store = FiledStore(tmp_path)
    assert store.keys() == set()


def _cache_with_bad_rows(tmp_path):
    (tmp_path / "fdic_financials.json").write_text(json.dumps([
        {"REPDTE": "20250331", "ASSET": 900_000, "DEP": 700_000, "LNLSNET": 500_000},        # no CERT
        {"CERT": "abc", "REPDTE": "20250331", "ASSET": 900_000, "DEP": 700_000, "LNLSNET": 500_000},  # CERT doesn't parse
        {"CERT": 12, "ASSET": 900_000, "DEP": 700_000, "LNLSNET": 500_000},                  # no REPDTE
        {"CERT": 12, "REPDTE": "20250331", "ASSET": 900_000, "DEP": 700_000, "LNLSNET": 500_000},
    ]), encoding="utf-8")
    (tmp_path / "ncua_financials.json").write_text(json.dumps([
        {"CYCLE_DATE": "3/31/2025", "ACCT_010": "400000", "ACCT_018": "350000", "ACCT_025B": "200000"},  # no CU_NUMBER
        {"CU_NUMBER": "7", "CYCLE_DATE": "3/31/2025", "ACCT_010": "400000", "ACCT_018": "350000", "ACCT_025B": "200000"},
    ]), encoding="utf-8")
    return tmp_path


def test_rows_with_no_institution_key_or_no_date_are_skipped(tmp_path):
    store = FiledStore(_cache_with_bad_rows(tmp_path))
    assert not any(key.endswith(":None") for key in store.keys())
    assert store.series("fdic:12") != []
    assert store.series("ncua:7") != []
