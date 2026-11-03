"""Live Review's peer comparisons: the arithmetic, the small-pool suppression, the like-period rule, and above all that
no other client is identifiable anywhere in the model or the page.

Synthetic clients only: 9999 is the client; 7001-7009 and the names below are invented peers.
"""
import json
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "scripts"), os.path.join(REPO, "build"), os.path.join(REPO, "build", "ars_pipeline")]

from review_page import peer_pool, peers, registry               # noqa: E402
from review_page.page import render_page                         # noqa: E402
from review_page.trace import Tracer, audit                      # noqa: E402

from test_live_review import CID, PERIOD                         # noqa: E402

PEER_IDS = [str(7000 + i) for i in range(1, 10)]
PEER_NAMES = [f"Zephyrville Peer {i} Credit Union" for i in range(1, 10)]


# ----------------------------------------------------------------- the arithmetic
def test_ordinals():
    got = [peers.ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 23, 101, 111, 112)]
    assert got == ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "23rd", "101st", "111th", "112th"]


def test_quantiles_interpolate():
    assert peers.quantile([1, 2, 3, 4, 5], 0.5) == 3
    assert peers.quantile([1, 2, 3, 4], 0.5) == 2.5
    assert peers.quantile([10, 20, 30, 40, 50], 0.25) == 20
    assert peers.quantile([10, 20, 30, 40, 50], 0.75) == 40
    assert peers.quantile([7], 0.9) == 7


def test_percentile_rank_counts_half_of_a_tie():
    assert peers.percentile_rank(5, [1, 2, 3, 4]) == 100.0
    assert peers.percentile_rank(0, [1, 2, 3, 4]) == 0.0
    assert peers.percentile_rank(3, [1, 2, 3, 4]) == pytest.approx(100 * (2 + 0.5) / 4)


def test_rank_is_among_the_client_and_its_peers_and_ties_share_the_better_rank():
    assert peers.rank_among(124, [53, 60, 70, 80, 90], True) == 1
    assert peers.rank_among(60, [53, 60, 70, 80, 90], True) == 4
    assert peers.rank_among(0.9, [1.6, 1.0, 2.0, 3.0, 0.5], False) == 2     # lower is better: one peer is lower
    assert peers.rank_among(5, [5, 5, 5, 5, 5], True) == 1


def test_the_two_percent_band_is_almost_flat():
    assert peers.relation(101.9, 100)[0] == "flat" and peers.relation(98.1, 100)[0] == "flat"
    assert peers.relation(102.0, 100)[0] == "flat"
    assert peers.relation(102.1, 100)[0] == "above" and peers.relation(97.9, 100)[0] == "below"
    c = {"rank": 3, "total": 14, "median": 50.0, "relation": "flat", "diff": 0.5}
    assert peers.rank_phrase(c, "ICS") == "3rd of 14 ICS clients"
    assert peers.relation_phrase(c, lambda v: f"{v:.0f}") == "almost flat against the peer median (50)"
    c2 = dict(c, relation="above", diff=12.34)
    assert peers.relation_phrase(c2, lambda v: f"{v:.0f}") == "12.3% above the peer median (50)"


# ----------------------------------------------------------------- the pool, and what it may show
SPEC = {"key": "m", "label": "Referrals as a share of goal", "fmt": "pct0", "higher": True}


def _pool(n_peers, client=100.0, with_series=False):
    peers_rows = [{"point": {"m": 40.0 + 10 * i}, "series": {"m": {"Aug 2026": 40.0 + 10 * i, "Sep 2026": 45.0 + 10 * i}}} for i in range(n_peers)]
    me = {"point": {"m": client}, "series": {"m": {"Aug 2026": client - 5, "Sep 2026": client}}}
    return {"n_pool": n_peers, "me": me, "peers": peers_rows, "pull": "2026-10-27 to 2026-10-27"}


def test_fewer_than_five_other_clients_is_stated_and_nothing_is_compared():
    t = Tracer()
    scr = peers.peers_screen(t, "ICS", "ICS", _pool(4), [dict(SPEC)])
    assert scr["blocks"][0]["t"] == "statement" and "Not enough peers" in scr["blocks"][0]["title"]
    assert not any(b["t"] == "peerstrip" for b in scr["blocks"])
    assert audit({"screens": [scr]}, t) == []


def test_five_other_clients_is_enough_and_the_comparison_is_made():
    t = Tracer()
    scr = peers.peers_screen(t, "ICS", "ICS", _pool(5), [dict(SPEC)])
    strip = scr["blocks"][1] if scr["blocks"][0].get("lead") else scr["blocks"][0]
    assert strip["t"] == "peerstrip" and strip["n"] == 5 and len(strip["dots"]) == 5
    assert "1st of 6 ICS clients" in scr["headline"]
    assert audit({"screens": [scr]}, t) == []


def test_a_metric_with_fewer_than_five_peers_with_current_data_is_left_out_and_said_so():
    t = Tracer()
    c = _pool(8)
    for r in c["peers"][:5]:
        r["point"]["k"] = 10.0               # only three peers have a value for the second metric
    for r in c["peers"][5:]:
        r["point"]["k"] = 12.0
    c["peers"][4]["point"].pop("k")
    c["peers"][3]["point"].pop("k")
    c["peers"][2]["point"].pop("k")
    c["peers"][5]["point"].pop("k")           # four peers left with a value
    c["me"]["point"]["k"] = 11.0
    scr = peers.peers_screen(t, "ICS", "ICS", c, [dict(SPEC), {"key": "k", "label": "Second measure", "fmt": "dec1", "higher": True}])
    assert any("Second measure: fewer than 5 peers have current data" in n for n in scr["notes"])


def test_a_program_where_no_metric_has_enough_peers_says_so_plainly():
    t = Tracer()
    c = _pool(8)
    for r in c["peers"]:
        r["point"].pop("m")
    scr = peers.peers_screen(t, "ICS", "ICS", c, [dict(SPEC)])
    assert scr["blocks"][0]["t"] == "statement" and "too few peers have current data" in scr["headline"]


# ----------------------------------------------------------------- like periods
def test_the_comparison_month_is_the_clients_latest_when_enough_peers_have_it():
    me = {"Aug 2026": 80.0, "Sep 2026": 90.0}
    ps = [{"Aug 2026": 50.0 + i, "Sep 2026": 60.0 + i} for i in range(6)]
    month, cv, vals, fell, out = peers.align_month(me, ps)
    assert (month, cv, fell, out) == ("Sep 2026", 90.0, False, 0) and len(vals) == 6


def test_it_falls_back_to_the_latest_month_enough_peers_share_and_says_so():
    me = {"Aug 2026": 80.0, "Sep 2026": 90.0, "Oct 2026": 95.0}
    ps = [{"Aug 2026": 50.0 + i, "Sep 2026": 60.0 + i, **({"Oct 2026": 70.0} if i < 3 else {})} for i in range(7)]
    month, cv, vals, fell, out = peers.align_month(me, ps)
    assert month == "Sep 2026" and cv == 90.0 and fell is True and len(vals) == 7


def test_a_peer_with_no_value_for_the_month_is_counted_as_left_out_not_zeroed():
    me = {"Sep 2026": 90.0}
    ps = [{"Sep 2026": 60.0 + i} for i in range(6)] + [{"Aug 2026": 10.0}, {}]
    month, cv, vals, fell, out = peers.align_month(me, ps)
    assert month == "Sep 2026" and len(vals) == 6 and out == 2 and 0 not in vals


def test_no_month_that_enough_peers_share_means_no_comparison():
    assert peers.align_month({"Sep 2026": 90.0}, [{"Sep 2026": 60.0}] * 4) is None


def test_a_month_in_progress_is_not_in_the_ics_series(monkeypatch, tmp_path):
    import peer_data as PD
    monkeypatch.setattr(peer_pool, "_vip_ids", lambda program: [CID, *PEER_IDS[:6]])
    monkeypatch.setattr(peer_pool, "_dda", lambda ctx: {})
    monkeypatch.setattr(PD, "ics_section", lambda cid, c: {"trend": {"months": ["Aug 26", "Sep 26"], "referrals": [8, 9], "goal": [10, 10]}, "data_pull": "2026-10-27"})
    from review_page.common import Ctx
    coll = peer_pool.collect_ics(Ctx(client=CID, period=PERIOD, root=tmp_path))
    assert list(coll["me"]["series"]["pct_goal"]) == ["Aug 2026", "Sep 2026"] and coll["n_pool"] == 6   # trend is already complete-month (peer_data.complete_trend)


# ----------------------------------------------------------------- privacy: nothing identifies another client
def _fake_ics(monkeypatch, tmp_path, n_peers=7):
    import peer_data as PD
    import rpe_env
    ids = [CID, *PEER_IDS[:n_peers]]
    names = {cid: (f"Test Bank" if cid == CID else PEER_NAMES[i - 1]) for i, cid in enumerate(ids)}
    monkeypatch.setattr(peer_pool, "_vip_ids", lambda program: ids)
    monkeypatch.setattr(peer_pool, "_dda", lambda ctx: {})
    vals = {cid: (124.0 if cid == CID else 40.0 + 7 * i) for i, cid in enumerate(ids)}

    def section(cid, c):
        pct = vals[cid]
        return {"client_name": names[cid], "workbook": f"{cid}-2026.08-{names[cid]}-Invitation Checking Workbook v1.7.1.xlsx",
                "trend": {"months": ["Jul 26", "Aug 26", "Sep 26"], "referrals": [pct * 0.1, pct * 0.1, pct * 0.1], "goal": [10, 10, 10]},
                "data_pull": "2026-10-27", "monthly_goal": 10, "ptd": 5000, "ytd": 900, "prev_month": {"label": "September", "value": 9}}
    monkeypatch.setattr(PD, "ics_section", section)
    sheet = {"meta": {"client_name": "Test Bank", "workbook": "9999-2026.08-x-Invitation Checking Workbook v1.7.1.xlsx", "program_start": "2018-12", "vip_source": "VIP", "data_pull": "2026-10-27"},
             "referrals": {"program_to_date": 700, "year_to_date": 90, "previous_month": {"label": "September", "value": 9}, "month_to_date": {"label": "October", "value": 5, "partial": True},
                           "monthly_goal": 8, "prev_month_vs_goal_pct": 112,
                           "trend": {"months": ["Aug 26", "Sep 26", "Oct 26"], "referrals": [7, 9, 5], "goal": [8, 8, 8], "partial_last": True},
                           "by_branch": {"branches": [{"name": "North", "referrals": 40, "goal": 30}]}}}
    f = tmp_path / "9999_ics.json"
    f.write_text(json.dumps(sheet), encoding="utf-8")
    monkeypatch.setattr(rpe_env, "resolve_client_json", lambda cid, prog: f)
    return ids, names


def test_no_other_client_is_identifiable_in_the_model_or_the_page(monkeypatch, tmp_path):
    ids, names = _fake_ics(monkeypatch, tmp_path)
    model, _t, problems = registry.build_model(CID, PERIOD, root=tmp_path, programs=["ics"])
    assert problems == []
    ics = model["programs"][0]
    ps = next(s for s in ics["screens"] if s["id"] == "peers")
    assert any(b["t"] == "peerstrip" or b["t"] == "variants" for b in ps["blocks"])
    blob = json.dumps(model) + render_page(model, "tok")
    for cid in ids[1:]:
        assert cid not in blob, f"peer id {cid} is on the page"
    for nm in names.values():
        if nm != "Test Bank":
            assert nm not in blob and nm.split()[0] not in blob, f"peer name {nm} is on the page"
    assert "Zephyrville" not in blob


def test_the_page_carries_the_peers_values_and_nothing_that_keys_them(monkeypatch, tmp_path):
    ids, _names = _fake_ics(monkeypatch, tmp_path)
    model, _t, _p = registry.build_model(CID, PERIOD, root=tmp_path, programs=["ics"])
    ps = next(s for s in model["programs"][0]["screens"] if s["id"] == "peers")

    def strips(bs):
        for b in bs:
            if b["t"] == "variants":
                for o in b["options"]:
                    yield from strips(o["blocks"])
            elif b["t"] == "peerstrip":
                yield b
    for st in strips(ps["blocks"]):
        assert isinstance(st["dots"], list) and all(isinstance(v, float) for v in st["dots"])
        assert set(st) >= {"client", "median", "q1", "q3", "dots", "n"} and not any(k in st for k in ("ids", "names", "clients", "peers"))
        assert st["n"] == len(st["dots"]) == 7


def test_the_sources_say_how_peers_are_defined_without_naming_any(monkeypatch, tmp_path):
    ids, names = _fake_ics(monkeypatch, tmp_path)
    model, _t, _p = registry.build_model(CID, PERIOD, root=tmp_path, programs=["ics"])
    ps = next(s for s in model["programs"][0]["screens"] if s["id"] == "peers")
    txt = " ".join(x["text"] for x in ps["sources"]) + " ".join(ps["notes"])
    assert "all other clients on ICS with current data, n = 7" in txt
    assert not any(cid in txt for cid in ids[1:])


def test_cashplease_peers_read_the_packs_and_expose_none_of_them(tmp_path):
    packs = tmp_path / "cashplease" / "packs"
    packs.mkdir(parents=True)

    def pack(cid, name, per_1k, dda=1000):
        months = [{"period_month": f"2026-{m:02d}", "loans": 10 + m, "principal": 100.0, "interest": 1.0, "funded": 1, "paid_off": 1, "overdue": 0, "charged_off": 0} for m in range(1, 10)]
        return {"client_id": cid, "client_name": name, "source_file": "w.xlsx", "report_generated": "10/12/2026 8:00:00 AM", "charge_off_pct": 0.04, "cancelled": None,
                "status": {}, "total": {"principal": 10.0, "interest": 3.0, "loans": 550}, "monthly": months,
                "metrics": {"total_loans": 550, "pct_loans_overdue": 0.01, "peer_comparable": True, "loans_per_1k_dda": per_1k, "dda_accounts": dda}}
    (packs / f"{CID}_cashplease.json").write_text(json.dumps(pack(CID, "Test Bank", 40.0)), encoding="utf-8")
    for i, (cid, nm) in enumerate(zip(PEER_IDS[:6], PEER_NAMES[:6])):
        (packs / f"{cid}_cashplease.json").write_text(json.dumps(pack(cid, nm, 20.0 + 3 * i)), encoding="utf-8")
    from review_page.common import Ctx
    ctx = Ctx(client=CID, period=PERIOD, root=tmp_path)
    coll = peer_pool.collect_cashplease(ctx)
    assert coll["n_pool"] == 6 and all(set(p) == {"point", "series"} for p in coll["peers"])
    t = Tracer()
    scr = peers.peers_screen(t, "CashPlease", "CashPlease", coll, peer_pool.CP_METRICS, trend="per_1k_month", pull_dates=coll["pull"])
    blob = json.dumps(scr)
    assert not any(cid in blob for cid in PEER_IDS) and "Zephyrville" not in blob
    assert audit({"screens": [scr]}, t) == []


def test_the_combined_view_gets_a_how_you_compare_screen_and_the_story_gets_two_optional_sections(monkeypatch, tmp_path):
    from test_live_review import make_pack
    from test_live_review_story import make_companion, make_ti
    _fake_ics(monkeypatch, tmp_path)
    make_pack(tmp_path)
    make_companion(tmp_path)
    make_ti(tmp_path)
    model, _t, problems = registry.build_model(CID, PERIOD, root=tmp_path, programs=["ars", "analysis", "ti", "ics"])
    assert problems == []
    cmp_screen = next(s for s in model["combined"]["screens"] if s["id"] == "compare")
    assert cmp_screen["blocks"][0]["cards"][0]["open"] == "ics:peers"
    ids = [s["id"] for s in model["story"]["sections"]]
    assert ids[-2:] == ["others", "compare"]
    assert [r["ref"] for r in model["story"]["sections"][-1]["screens"]] == ["ics:peers"]      # only the programs the client has
    assert "others" not in [s["id"] for s in registry.build_model(CID, PERIOD, root=tmp_path, programs=["ars", "analysis", "ti"])[0]["story"]["sections"]]


# ----------------------------------------------------------------- the shared reader
def test_the_dashboard_and_live_review_read_each_program_through_one_module():
    import peer_data
    import refresh_performance_dashboard as P
    for name in ("ics_section", "mrpc_section", "cp_section", "complete_trend"):
        assert getattr(P, name) is getattr(peer_data, name)
    assert peer_data.wb_period("1539-2026.08-Marine FCU-Invitation Checking Workbook v1.7.1.xlsx") == "2026.08"
    assert peer_data.complete_trend({"months": ["Jul 26", "Aug 26", "Sep 26"], "referrals": [3, 4, 1], "goal": [5, 5, 5], "partial_last": True})["months"] == ["Jul 26", "Aug 26"]
