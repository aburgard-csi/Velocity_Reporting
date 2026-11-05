"""The Transaction Intelligence and Competition chapters (build/ars_pipeline/ti/chapters_txn.py).

Pinned: the two chapters carry v5's 61 transaction builders less its two attrition slides, in v5's
order; every builder has a title for a stated slide; a client with no transaction figures has both
chapters hidden and no deck; the ICS lens narrows the lens list and the ARS lens leaves it as v5 drew it.
"""
import json
import os
import sys

import pytest
from pptx import Presentation

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ("build", "build/ars_pipeline", "validation"):
    sys.path.insert(0, os.path.join(REPO, p))

import build_ti_gen as G  # noqa: E402
import validate_deck as vd  # noqa: E402
from test_ti_shell import CLIENT, NAME, PACK, TEMPLATE, contacts  # noqa: E402,F401
from ti import chapters_txn as X  # noqa: E402
from ti import cut  # noqa: E402
from ti.deck import txn_slides  # noqa: E402


def test_the_chapters_carry_v5s_builders_in_v5s_order():
    v5 = [b.__name__ for b in txn_slides.BUILDERS]
    ours = [b.__name__ for b in X.TI_BUILDERS + X.COMP_BUILDERS + X.ATTRITION_BUILDERS]
    # v5's 61, plus the three R5 leakage cuts by member age, account age and branch (2026-11-05)
    assert sorted(ours) == sorted(v5) and len(v5) == 64
    for chapter in (X.TI_BUILDERS, X.COMP_BUILDERS):
        names = [b.__name__ for b in chapter]
        assert names == [n for n in v5 if n in names], "kept in v5's own order"
    assert len(X.TI_BUILDERS) == 42 and len(X.COMP_BUILDERS) == 20


def test_every_builder_has_a_title_for_a_stated_slide():
    for b in X.TI_BUILDERS + X.COMP_BUILDERS + X.ATTRITION_BUILDERS:
        assert X.TITLES.get(b.__name__), b.__name__


def test_the_chapters_are_registered_in_deck_order():
    assert [c.code for c in cut.CHAPTERS][:2] == ["TI_TXN", "TI_COMP"]


def test_ics_lens_narrows_the_lens_list_and_ars_leaves_it():
    m = {"lenses": [["all", "All", 9], ["responders", "R", 3], ["ics", "ICS", 2], ["ics_dm", "DM", 1]]}
    assert X.lens_view(m, cut.lens("ars")) is m
    assert [r[0] for r in X.lens_view(m, cut.lens("ics"))["lenses"]] == ["all", "ics", "ics_dm"]


def test_no_transaction_figures_hides_both_chapters_and_stops(tmp_path, contacts):
    """RPE (Sheila's 1798 slide review, 2026-10-30): a declined slide is hidden for the client and
    a chapter with nothing left is dropped. With no transaction files both chapters decline, so
    there is no deck to make: the build stops and says so, and the hidden list names both."""
    prs = Presentation(TEMPLATE)
    pack = dict(PACK, metrics={})
    with pytest.raises(SystemExit, match="was declined for client"):
        G.build(prs, pack, "ars", list(cut.CHAPTERS[:2]), art_dir=str(tmp_path))
    hidden = json.loads((tmp_path / "hidden_declined.json").read_text(encoding="utf-8"))["ars"]
    assert len(hidden) == 2, hidden
    assert all("transaction files for this period are not on hand" in h["reason"] for h in hidden)


def test_the_transaction_figures_reach_the_odd_sections_as_v5_hands_them_on(monkeypatch):
    """v5 passes the transaction figures to the ODD sections as config["_txn"]; the deposits
    section reads them for "What arrives against what leaves"."""
    import pandas as pd
    from ti.context import Ctx
    import ti.txn_sections as T

    c = Ctx(pd.DataFrame(), {"ClientID": "9999"}, None, None, client_id="9999")
    c.txn = pd.DataFrame({"x": [1]})
    for name in ("portfolio", "financial_services", "competition", "merchants", "merchant_profiles",
                 "mapping_audit", "card_behavior", "interchange", "relationship", "overlay",
                 "leakage", "stressors_txn", "hotspots", "family_tables"):
        monkeypatch.setattr(T, name, (lambda n: (lambda *_a: {f"{n}_figure": 1}))(name))
    monkeypatch.setattr(T, "filed", lambda _c, _m: {})
    out = X.compute_all(c)
    assert c.config["_txn"] is out and out["portfolio_figure"] == 1
    assert c.config["ClientID"] == "9999"
