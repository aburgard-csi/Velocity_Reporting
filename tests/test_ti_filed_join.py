# Ported from ARS v5 02-Scripts/tests/test_filed_join.py at a491b5c (James Gilmore); logic unchanged.
import pathlib
import sys
from types import SimpleNamespace

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from ti.core.filed.join import REQUIRED_CACHE, attach_filed, require_cache, split_unresolved  # noqa: E402
from ti.core.filed.store import Quarter  # noqa: E402
from ti.core.market.sources import SourceError  # noqa: E402


class _Store:
    def __init__(self, series, regs):
        self._s, self._r = series, regs
    def series(self, key):
        return self._s.get(key, [])
    def regulator(self, key):
        return self._r.get(key)


def _q(date, dep):
    return Quarter(date=date, assets=None, deposits=dep, loans=None, net_worth=None, roa=None)


def _metrics():
    return {"comp_institutions": [
        ["Chase", "National Bank", 120, 8.0, 900, 250_000, 2083, ["Credit Cards"], 5, 2],
        ["Seamens Bank", "Local Bank / CU", 40, 2.7, 300, 90_000, 2250, [], 1, 0],
        ["Venmo", "Payment Ecosystem", 300, 20.0, 5000, 60_000, 200, [], 9, 3],
    ]}


def test_rows_carry_the_growth_and_are_ordered_by_dollars():
    book = SimpleNamespace(institutions={
        "fdic:9": SimpleNamespace(key="fdic:9", name="JPMORGAN CHASE BANK", trade_names=("CHASE",)),
        "fdic:2": SimpleNamespace(key="fdic:2", name="SEAMENS BANK", trade_names=()),
    })
    store = _Store({"fdic:9": [_q("2025-03-31", 1_000), _q("2026-03-31", 1_100)],
                    "fdic:2": [_q("2025-03-31", 500), _q("2026-03-31", 450)]},
                   {"fdic:9": "OCC", "fdic:2": "FDIC"})
    m = _metrics()
    attach_filed(m, store, book, None)
    assert [r[0] for r in m["comp_filed"]] == ["Chase", "Seamens Bank"]
    chase = dict(zip(m["comp_filed_columns"], m["comp_filed"][0]))
    assert chase["key"] == "fdic:9" and chase["regulator"] == "OCC"
    assert chase["growth_pct"] == 10.0 and chase["accounts"] == 120
    assert m["comp_filed_unresolved"] == ["Venmo"]


def test_a_key_with_no_year_of_filings_is_reported_not_rendered():
    book = SimpleNamespace(institutions={
        "fdic:9": SimpleNamespace(key="fdic:9", name="JPMORGAN CHASE BANK", trade_names=("CHASE",))})
    store = _Store({"fdic:9": [_q("2026-03-31", 1_100)]}, {})
    m = {"comp_institutions": [_metrics()["comp_institutions"][0]]}
    attach_filed(m, store, book, None)
    assert m["comp_filed"] == []
    assert m["comp_filed_unresolved"] == ["Chase (no year of filings)"]


def test_no_competition_keys_is_a_no_op():
    m = {}
    attach_filed(m, _Store({}, {}), SimpleNamespace(institutions={}), None)
    assert "comp_filed" not in m


def test_require_cache_raises_when_any_file_is_missing(tmp_path):
    with pytest.raises(SourceError) as exc:
        require_cache(tmp_path)
    assert any(name in str(exc.value) for name in REQUIRED_CACHE)


def test_require_cache_passes_when_all_files_present(tmp_path):
    for name in REQUIRED_CACHE:
        (tmp_path / f"{name}.json").write_text("[]", encoding="utf-8")
    require_cache(tmp_path)


def test_equal_dollars_break_the_tie_by_name():
    book = SimpleNamespace(institutions={
        "fdic:1": SimpleNamespace(key="fdic:1", name="ZETA BANK", trade_names=()),
        "fdic:2": SimpleNamespace(key="fdic:2", name="ALPHA BANK", trade_names=())})
    store = _Store({"fdic:1": [_q("2025-03-31", 500), _q("2026-03-31", 550)],
                    "fdic:2": [_q("2025-03-31", 500), _q("2026-03-31", 550)]},
                   {"fdic:1": "OCC", "fdic:2": "OCC"})
    m = {"comp_institutions": [
        ["Zeta Bank", "National Bank", 50, 5.0, 100, 100_000, 1000, [], 1, 0],
        ["Alpha Bank", "National Bank", 60, 6.0, 100, 100_000, 1000, [], 1, 0],
    ]}
    attach_filed(m, store, book, None)
    assert [r[0] for r in m["comp_filed"]] == ["Alpha Bank", "Zeta Bank"]


def test_split_unresolved_separates_no_record_from_short_series():
    assert split_unresolved(["A", "B (no year of filings)", "C"]) == (["A", "C"], ["B"])
