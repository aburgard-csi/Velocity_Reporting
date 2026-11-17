"""What changed since the prior month, the triggers, and the portfolio row
(ti/transaction_intelligence/competition_layers_compare.py, ti_build.py --prior-pack).

Synthetic figures only.

    python -m pytest tests/test_ti_competition_layers_compare.py -q
"""
import inspect
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "build" / "ars_pipeline"))

from ti.transaction_intelligence import competition_layers as CL  # noqa: E402
from ti.transaction_intelligence import competition_layers_compare as C  # noqa: E402

CFG = CL.settings({})


def _figs(tiers, insts, cov):
    return {"cl_tiers": [{"tier": t, "accounts": a, "pct": p, "dollars": a * 100} for t, a, p in tiers],
            "cl_institutions": [{"inst": n, "tier": t, "accounts": a} for n, t, a in insts], "cl_coverage": {"pct": cov}}


PRIOR = _figs([("National", 90, 9.0), ("Local", 30, 3.0), ("Digital", 10, 1.0)], [("Alpha", "National", 60), ("Beta", "Local", 30), ("Gone", "Local", 12)], 97.0)
NOW = _figs([("National", 100, 9.2), ("Local", 20, 2.0), ("Regional (district)", 8, 0.8)],
            [("Alpha", "National", 62), ("Beta", "Local", 20), ("Newcomer", "Regional (district)", 55), ("Tiny", "Local", 4)], 93.5)


def test_tiers_and_institutions_are_compared_by_name_and_sorted_by_the_size_of_the_move():
    c = C.compare(NOW, PRIOR, CFG, "2026.10")
    assert c["prior_period"] == "2026.10"
    by = {r["tier"]: r for r in c["tiers"]}
    assert by["Local"]["change_points"] == -1.0 and by["Digital"]["pct_now"] == 0.0 and by["Regional (district)"]["pct_prior"] == 0.0
    assert [r["tier"] for r in c["tiers"]][0] in ("Local", "Digital")                 # the biggest moves first
    inst = {r["inst"]: r for r in c["institutions"]}
    assert inst["Newcomer"]["status"] == "new this month" and inst["Newcomer"]["change"] == 55
    assert inst["Gone"]["status"] == "not seen this month" and inst["Gone"]["change"] == -12
    assert inst["Alpha"]["status"] == "continuing" and inst["Alpha"]["change"] == 2
    assert c["coverage"] == {"now": 93.5, "prior": 97.0}


def test_triggers_fire_on_a_new_institution_a_tier_share_move_and_low_coverage():
    c = C.compare(NOW, PRIOR, CFG, "2026.10")
    kinds = [(r["trigger"], r["subject"]) for r in c["triggers"]]
    assert ("New institution over the threshold", "Newcomer") in kinds
    assert ("Tier share moved", "Local") in kinds and ("Tier share moved", "Digital") in kinds
    assert ("Coverage below the floor", "coverage") in kinds
    assert not any(s == "Tiny" for _t, s in kinds), "four accounts is under the threshold"
    assert not any(t == "Tier share moved" and s == "National" for t, s in kinds), "0.2 points is under 0.3"


def test_the_thresholds_are_the_clients_to_set():
    loose = CL.settings({"CompetitionLayers": {"trigger_new_accounts": 500, "trigger_share_points": 5.0, "coverage_floor": 50.0}})
    assert C.compare(NOW, PRIOR, loose, None)["triggers"] == []


def test_nothing_is_compared_when_either_month_has_no_layers():
    assert C.compare({}, PRIOR, CFG) == {} and C.compare(NOW, {"cl_tiers": []}, CFG) == {}


def test_the_portfolio_row_carries_reach_tiers_and_groups_and_no_client_identifier():
    figs = dict(NOW, cl_any={"accounts": 150, "pct": 15.0, "dollars": 9_000, "by_group": {"responders": {"pct": 13.4}, "not_mailed": {"pct": 20.2}}},
                cl_base={"accounts": 1000}, cl_scope={"client_type": "Credit Union"})
    row = C.portfolio_row(figs)
    assert row["accounts"] == 1000 and row["any_pct"] == 15.0 and row["institutions_placed"] == 4 and row["coverage_pct"] == 93.5
    assert row["tier_pct_regional"] == 0.8 and row["group_pct_not_mailed"] == 20.2 and row["client_type"] == "Credit Union"
    assert not any("id" == k or k.endswith("_id") or "name" in k for k in row)
    assert C.portfolio_row({}) == {}


def test_the_build_takes_a_prior_pack_and_refuses_a_pack_from_another_client():
    import ti_build
    assert "prior_pack" in inspect.signature(ti_build.compute_pack).parameters
    src = pathlib.Path(ti_build.__file__).read_text(encoding="utf-8")
    assert '"--prior-pack"' in src and "is for client" in src
    json.dumps(C.compare(NOW, PRIOR, CFG, "2026.10"))                      # the comparison goes into the pack as JSON
