"""The `competition_layers` section of ti/txn_sections.py: its wiring, not the analyses (those are tested directly).

Aaron's review of PR 175: the `cl_parts` shared key, the call into the analysis module and the write-back into
`cl_institutions` were exercised by no test; the other tests call `compute()` directly. This runs the section itself
on a small synthetic context.

    python -m pytest tests/test_ti_competition_layers_section.py -q
"""
import json
import pathlib
import sys

import pandas as pd
import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import ti.txn_sections as T  # noqa: E402
from ti.context import Ctx  # noqa: E402
from test_ti_competition_layers import CONFIG, RECORD, make_book  # noqa: E402

ROWS = [("A1", "SIG", "2026-03-05", -100.0, "OBP* MAPLE LEAF FCU"), ("A1", "SIG", "2026-10-20", -100.0, "MAPLE LEAF FCU"),
        ("A1", "PIN", "2026-10-21", -800.0, "CORNER GROCER"), ("A2", "SIG", "2026-06-10", -200.0, "RIVERBEND BANK #12"),
        ("A2", "SIG", "2026-07-01", -300.0, "CORNER GROCER"), ("A3", "SIG", "2026-09-15", -50.0, "CHASE CREDIT CRD"),
        ("A3", "SIG", "2026-10-26", -400.0, "CORNER GROCER")]


class _Lenses:
    key_column = "Acct"

    def __init__(self):
        self.groups = {"responders": ["A1"], "mailed_nonresp": ["A2"], "not_mailed": ["A3"],
                       "personal": ["A1", "A2", "A3"], "business": []}
        self.masks = dict(self.groups)

    def names(self):
        return list(self.groups)

    def ids(self, name):
        return pd.Index(self.groups[name])


def _ctx(tmp_path, monkeypatch, with_rows=True):
    monkeypatch.setattr(T, "reference_dir", lambda: tmp_path)
    monkeypatch.setattr(T, "market_dir", lambda: tmp_path)
    monkeypatch.setattr(T, "_BOOKS", {})
    import ti.core.filed.join as J
    import ti.core.market.institutions as I
    monkeypatch.setattr(J, "require_cache", lambda cache: None)
    monkeypatch.setattr(I, "load_book", lambda cache: make_book())
    (tmp_path / "9999.json").write_text(json.dumps(RECORD), encoding="utf-8")
    df = pd.DataFrame(ROWS, columns=["primary_account_num", "transaction_type", "transaction_date", "amount", "merchant_name"])
    frame = pd.DataFrame({"Acct": ["A1", "A2", "A3"], "Branch": [3.0, 3.0, 4.0], "Date Closed": [None, "08/15/2026", None]})
    ctx = Ctx(frame, dict(CONFIG), None, None, client_id="9999")
    ctx.txn, ctx.anchor_ts, ctx.lenses = df, pd.Timestamp("2026-10-31"), _Lenses()
    if with_rows:
        ctx.shared["fin_rows"] = pd.DataFrame({"core": df["merchant_name"], "is_card": df["transaction_type"].isin(["PIN", "SIG"])}, index=df.index)
    return ctx


def test_the_section_runs_the_figures_and_the_analyses_and_writes_the_pack_keys(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch)
    out = T.competition_layers(ctx)
    for k in ("cl_any", "cl_tiers", "cl_institutions", "cl_trend", "cl_movement", "cl_tier_movement", "cl_depth_tiers",
              "cl_depth_institutions", "cl_multi", "cl_recency", "cl_distance", "cl_winback", "cl_attrition", "cl_branches",
              "cl_map", "cl_portfolio_row"):
        assert k in out, k
    assert not [k for k in out if k.startswith("_cl_")], "the hand-offs are never written to the pack"
    json.dumps(out)                                                    # the whole section goes into the pack as JSON


def test_the_hand_off_is_left_on_the_context_for_later_sections(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch)
    T.competition_layers(ctx)
    sub, matched, active, sets = ctx.shared["cl_parts"]
    assert len(sub) == 7 and set(matched["inst"]) == {"Maple Leaf", "Riverbend Bank", "Chase"}      # the card rows of the base, matched
    assert active == {"A1", "A2", "A3"} and set(sets) >= {"responders", "mailed_nonresp", "not_mailed"}


def test_each_institution_row_carries_its_movement_and_depth_beside_its_reach(tmp_path, monkeypatch):
    out = T.competition_layers(_ctx(tmp_path, monkeypatch))
    rows = {r["inst"]: r for r in out["cl_institutions"]}
    maple = rows["Maple Leaf"]
    assert maple["accounts"] == 1 and maple["new_90"] == 0 and maple["live_30"] == 1                  # written back from cl_movement
    assert {"heavy", "mid", "median_share_pct"} <= set(maple)                                        # written back from cl_depth_institutions
    mv = {r["inst"]: r for r in out["cl_movement"]}
    assert maple["live_30"] == mv["Maple Leaf"]["live_30"]
    assert out["cl_portfolio_row"]["accounts"] == 3 and "client_id" not in out["cl_portfolio_row"]


def test_with_no_classification_the_section_adds_nothing(tmp_path, monkeypatch):
    assert T.competition_layers(_ctx(tmp_path, monkeypatch, with_rows=False)) == {}


def test_with_no_reference_store_the_section_says_so_and_adds_nothing(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch)
    import ti.core.filed.join as J

    from ti.core.market import SourceError

    def refuse(cache):
        raise SourceError("no reference store on hand")
    monkeypatch.setattr(J, "require_cache", refuse)
    assert T.competition_layers(ctx) == {}
    assert any("reference store is not available" in w for w in ctx.warnings)        # the build goes on, the layers are stated absent
