# Ported from ARS v5 02-Scripts/tests/test_filed_sources.py at a491b5c (James Gilmore); logic unchanged.
"""The two new Filed pulls go through the same cache, floor and refresh rules as the rest."""
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from ti.core.market import sources  # noqa: E402


def test_fdic_financials_reads_cache_without_network(tmp_path, monkeypatch):
    rows = [{"CERT": 1, "REPDTE": "20260331", "ASSET": 100, "DEP": 80,
             "LNLSNET": 50, "ROA": 1.1, "EQV": 10.0, "NETINC": 2}] * 15_000
    (tmp_path / "fdic_financials.json").write_text(json.dumps(rows), encoding="utf-8")
    monkeypatch.setattr(sources, "_fetch", lambda url: pytest.fail(f"network touched: {url}"))
    out = sources.fdic_financials(tmp_path)
    assert len(out) == 15_000
    assert out[0]["DEP"] == 80


def test_fdic_financials_floor_stops_a_truncated_download(tmp_path, monkeypatch):
    monkeypatch.setattr(sources, "_fdic_pages", lambda endpoint, fields, filters="": [{"CERT": 1}] * 10)
    with pytest.raises(sources.SourceError):
        sources.fdic_financials(tmp_path, refresh=True)


def test_fdic_financials_requests_the_fields_and_window(tmp_path, monkeypatch):
    seen = {}

    def fake_pages(endpoint, fields, filters=""):
        seen.update(endpoint=endpoint, fields=fields, filters=filters)
        return [{"CERT": 1}] * 15_000

    monkeypatch.setattr(sources, "_fdic_pages", fake_pages)
    sources.fdic_financials(tmp_path, refresh=True, since="20250101")
    assert seen["endpoint"] == "financials"
    for f in ("CERT", "REPDTE", "ASSET", "DEP", "LNLSNET", "ROA", "EQV", "NETINC"):
        assert f in seen["fields"]
    assert "REPDTE:[20250101 TO *]" in seen["filters"]


def test_fdic_institutions_now_carry_the_regulator_fields(tmp_path, monkeypatch):
    seen = {}

    def fake_pages(endpoint, fields, filters=""):
        seen["fields"] = fields
        return [{"CERT": 1}] * 3_000

    monkeypatch.setattr(sources, "_fdic_pages", fake_pages)
    sources.fdic_institutions(tmp_path, refresh=True)
    for f in ("REGAGNT", "BKCLASS", "CHRTAGNT"):
        assert f in seen["fields"]


import io
import zipfile


def _ncua_zip(fs220_header: str, fs220_row: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("FOICU.txt", "CU_NUMBER,CU_NAME\n1,TEST FCU\n")
        zf.writestr("Credit Union Branch Information.txt", "CU_NUMBER,SiteId\n1,10\n")
        zf.writestr("TradeNames.txt", "CU_NUMBER,TradeName\n1,TEST\n")
        zf.writestr("FS220.txt", fs220_header + "\n" + fs220_row + "\n")
    return buf.getvalue()


def test_ncua_financials_keep_the_call_report_fields(tmp_path, monkeypatch):
    blob = _ncua_zip("CU_NUMBER,CYCLE_DATE,ACCT_010,ACCT_018,ACCT_025B,ACCT_997,ACCT_999",
                     "1,3/31/2026,1000,800,500,100,7")
    monkeypatch.setattr(sources, "_fetch", lambda url: blob)
    monkeypatch.setitem(sources.MIN_ROWS, "ncua_institutions", 1)
    monkeypatch.setitem(sources.MIN_ROWS, "ncua_branches", 1)
    monkeypatch.setitem(sources.MIN_ROWS, "ncua_financials", 1)
    fin = sources.ncua(tmp_path, refresh=True)["financials"]
    assert fin[0] == {"CU_NUMBER": "1", "CYCLE_DATE": "3/31/2026", "ACCT_010": "1000",
                      "ACCT_018": "800", "ACCT_025B": "500", "ACCT_997": "100"}


def test_ncua_financials_tolerate_a_missing_column(tmp_path, monkeypatch):
    blob = _ncua_zip("CU_NUMBER,CYCLE_DATE,ACCT_010", "1,3/31/2026,1000")
    monkeypatch.setattr(sources, "_fetch", lambda url: blob)
    for name in ("ncua_institutions", "ncua_branches", "ncua_financials"):
        monkeypatch.setitem(sources.MIN_ROWS, name, 1)
    fin = sources.ncua(tmp_path, refresh=True)["financials"]
    assert fin[0]["ACCT_018"] is None


def test_vintages_report_the_filed_files(tmp_path):
    (tmp_path / "fdic_financials.json").write_text("[]", encoding="utf-8")
    v = sources.vintages(tmp_path)
    assert "fdic_financials" in v["row_counts"]


def test_fdic_pages_encode_a_range_filter(monkeypatch):
    seen = []

    def fake_fetch(url):
        seen.append(url)
        return '{"data": [], "meta": {"total": 0}}'

    monkeypatch.setattr(sources, "_fetch", fake_fetch)
    sources._fdic_pages("financials", "CERT,REPDTE", filters="REPDTE:[20240101 TO *]")
    assert len(seen) == 1
    assert " " not in seen[0]
    assert "filters=REPDTE:%5B20240101%20TO%20*%5D" in seen[0]
