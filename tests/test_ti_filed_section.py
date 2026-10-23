"""The filed section as the cut runs it (build/ars_pipeline/ti/txn_sections.filed).

With no reference store it says so and adds nothing, as v5's run does; it never edits the
figures it is handed; and it returns only what it adds or changes. The filed maths itself is
covered by v5's own tests (test_ti_filed_*.py).
"""
import pandas as pd

from ti import txn_sections as T
from ti.context import Ctx


def _ctx():
    return Ctx(pd.DataFrame(), {}, None, None, client_id="9999")


def test_no_reference_store_is_stated_and_adds_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("TI_REFERENCE_DIR", str(tmp_path / "none"))
    monkeypatch.setenv("TI_MARKET_DIR", str(tmp_path / "market"))
    c = _ctx()
    metrics = {"comp_institutions": [["Chase", 10, 1000.0]]}
    assert T.filed(c, metrics) == {}
    assert any(w.startswith("filed: skipped") for w in c.warnings)


def test_the_figures_handed_in_are_never_edited(tmp_path, monkeypatch):
    import ti.core.filed.join as J
    monkeypatch.setenv("TI_REFERENCE_DIR", str(tmp_path))
    monkeypatch.setenv("TI_MARKET_DIR", str(tmp_path / "market"))
    monkeypatch.setattr(J, "require_cache", lambda _p: None)

    def fake_attach(m, _store, _book, _record):
        m["comp_institutions"][0].append("+filed")
        m["comp_filed"] = [["Chase", 3.1]]
    monkeypatch.setattr(J, "attach_filed", fake_attach)
    import ti.core.market.institutions as I
    monkeypatch.setattr(I, "load_book", lambda _p: None)
    c = _ctx()
    metrics = {"comp_institutions": [["Chase", 10, 1000.0]], "comp_other": 1}
    out = T.filed(c, metrics)
    assert metrics["comp_institutions"] == [["Chase", 10, 1000.0]]
    assert set(out) == {"comp_institutions", "comp_filed"}
