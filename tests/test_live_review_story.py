"""Live Review's storyline: the Companion views and the Transaction Intelligence screens, the sections that
order them, and the "run this first" state for a view whose data is not on this machine.

Synthetic packs only (an invented client 9999); nothing reads the share.
"""
import json
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "scripts"), os.path.join(REPO, "build"), os.path.join(REPO, "build", "ars_pipeline")]

import review_page                                            # noqa: E402
from review_page import registry                              # noqa: E402
from review_page.page import render_page                      # noqa: E402

from test_live_review import CID, PERIOD, make_pack           # noqa: E402


def make_companion(root):
    cdir = root / "launcher" / PERIOD / CID / "companion" / CID
    cdir.mkdir(parents=True)
    ci = {
        "latest": "Sep26", "latest_label": "Sep 2026",
        "wave_revenue": {"available": True, "waves": [{"m": "Mar 2026", "key": "2026-03", "revenue": 16700.0, "months": 6},
                                                      {"m": "Jul 2026", "key": "2026-07", "revenue": 19200.0, "months": 2}],
                         "latest_month_label": "Sep 2026", "latest_total": 36000.0,
                         "by_mailing_latest": [["Jul 2026", 19200.0, 2], ["Mar 2026", 16800.0, 6]]},
        "offer_efficiency": {"available": True, "mailings": [
            {"month": "Mar 2026", "offers": 13000, "revenue": 16700.0, "months": 6, "per_1k": 1284.0, "per_1k_month": 214.0},
            {"month": "Jul 2026", "offers": 14000, "revenue": 19200.0, "months": 2, "per_1k": 1371.0, "per_1k_month": 685.0}]},
        "responder_control": {"available": True, "before_months": 3, "after_months": 6, "did": 400,
                              "responders": {"n": 1000, "before": 500, "after": 950, "change": 450, "change_pct": 90.0},
                              "control": {"n": 9000, "before": 300, "after": 330, "change": 30, "change_pct": 10.0}},
        "responder_by_tier": {"available": True, "rows": [{"tier": "Non-User", "responders": 100, "control": 900, "resp_before": 30,
                                                           "resp_after": 500, "control_before": 20, "control_after": 25}]},
        "branch_kpis": {"branches": [{"branch": "17", "eligible": 500, "take": 90.0, "rege": 35.0, "closed12": 7.0, "first_year": 19.0},
                                     {"branch": "2", "eligible": 400, "take": 85.0, "rege": 12.0, "closed12": 9.0, "first_year": 21.0}],
                        "other": {}, "other_count": 3,
                        "total": {"eligible": 900, "take": 88.0, "rege": 25.0, "closed12": 8.0, "first_year": 20.0},
                        "closure_window": ["Oct 2025", "Sep 2026"]},
        "tier_migration": {"available": True, "tiers": ["Non-User", "1-5"], "matrix": [["Non-User", 80, 20], ["1-5", 10, 90]],
                           "moved_up": 20, "same": 170, "moved_down": 10, "pct_up": 10.0, "pct_down": 5.0, "span": 12,
                           "then_window": ["Jul 2025", "Sep 2025"], "now_window": ["Jul 2026", "Sep 2026"]},
        "sizing": {"available": True, "points": 5.0, "take_now": 88.0, "take_accounts": 45, "take_headroom": 12.0, "rege_now": 25.0,
                   "rege_accounts": 40, "per_card_month": 3.0, "take_annual": 1620},
    }
    (cdir / "combined_insights.json").write_text(json.dumps(ci), encoding="utf-8")


def make_ti(root, txn=False):
    d = root / "launcher" / PERIOD / CID / "ti"
    d.mkdir(parents=True)
    m = {
        "txn_rows": 5 if txn else 0,
        "attrition_rate": 7.8, "attrition_closed": 5919, "attrition_opened": 7956, "attrition_net": 2037,
        "attrition_window": ["2025-10", "2026-09"],
        "attrition_by_branch": [["17", 11000, 900, 8.0], ["2", 6200, 450, 7.3]],
        "attrition_branch_worst": ["2", 17.2, 493], "attrition_branch_best": ["17", 2.3, 435],
        "flight_risk_deposits": 44852048, "flight_risk_n": 612, "flight_risk_threshold": 25000,
        "stress_2plus_n": 3023, "stress_2plus_deposits": 39646481, "sleeping_giants_n": 9310, "sleeping_giants_deposits": 176609693,
        "stress_by_count": [[0, 18808, 26.8, 79376815], [1, 48272, 68.9, 179789926], [2, 3017, 4.3, 39304091]],
        "value_per_card": 309.3, "value_per_optin": 191.03, "value_debit_total_with": 315.92, "value_debit_total_without": 6.62,
        "value_rege_total_with": 200.0, "value_rege_total_without": 9.0,
        "value_debit_current_revenue": 11322466, "value_debit_pot_full": 10366808,
        "value_rege_current_revenue": 11100478, "value_rege_pot_full": 4734105,
        "value_by_branch": [{"group": "16", "n": 207, "take_rate": 65.7, "value_per_acct": 364.85},
                            {"group": "25", "n": 90, "take_rate": 3.3, "value_per_acct": 4.74}],
        "value_branch_best": {"group": "16"}, "value_branch_worst": {"group": "25"}, "value_branch_spread": 360.11,
    }
    if txn:
        m.update({"comp_institutions": [["Chase", "National Bank", 2106, 5.5, 8453, 691588, 328.0, ["x"], 418, 150]],
                  "comp_with_competitor_pct": 18.2, "comp_competitor_dollars": 6106543,
                  "fin_by_category": [["Insurance", 7266, 19.1, 46201, 10640087, 1464, "leakage", False, None, 100.0]],
                  "fin_leaking_pct": 36.0, "fin_leaking_accounts": 13690, "fin_leakage_dollars": 22880401})
    (d / "ti_pack.json").write_text(json.dumps({"client_id": CID, "metrics": m, "sources": {"odd": "x.csv"}}), encoding="utf-8")


def build(root, programs):
    return registry.build_model(CID, PERIOD, root=root, programs=list(programs))


def test_the_storyline_runs_through_every_section_and_every_ref_resolves(tmp_path):
    make_pack(tmp_path)
    make_companion(tmp_path)
    make_ti(tmp_path)
    model, _t, problems = build(tmp_path, ("ars", "analysis", "ti"))
    assert problems == []
    story = model["story"]
    assert [s["id"] for s in story["sections"]] == ["program", "revenue", "branches", "members", "competition", "attrition", "worth"]
    assert 14 <= sum(len(s["screens"]) for s in story["sections"]) <= 20
    progs = {e["key"]: {s["id"] for s in e["screens"]} for e in model["programs"]}
    for sec in story["sections"]:
        for r in sec["screens"]:
            assert r["id"] in progs[r["prog"]] or r["ref"] in story["stubs"], r["ref"]


def test_a_view_with_no_data_is_a_run_this_first_state_never_an_empty_chart(tmp_path):
    make_pack(tmp_path)
    make_companion(tmp_path)
    make_ti(tmp_path, txn=False)          # Marine's case: a TI pack with no transaction files and no deposits extract
    model, _t, _p = build(tmp_path, ("ars", "analysis", "ti"))
    ti = next(e for e in model["programs"] if e["key"] == "ti")
    comp = next(s for s in ti["screens"] if s["id"] == "competition")
    assert comp["blocks"][0]["t"] == "needs" and "transaction files" in comp["blocks"][0]["fix"]
    dep = next(s for s in ti["screens"] if s["id"] == "deposits")
    assert dep["blocks"][0]["t"] == "needs" and "Inputs/Deposits" in dep["blocks"][0]["fix"]


def test_with_transaction_files_the_competition_screen_names_the_leader(tmp_path):
    make_pack(tmp_path)
    make_companion(tmp_path)
    make_ti(tmp_path, txn=True)
    model, _t, problems = build(tmp_path, ("ars", "analysis", "ti"))
    assert problems == []
    ti = next(e for e in model["programs"] if e["key"] == "ti")
    comp = next(s for s in ti["screens"] if s["id"] == "competition")
    assert "Chase" in comp["headline"] and comp["blocks"][0]["t"] == "drill"


def test_missing_programs_leave_the_story_standing_with_stubs(tmp_path):
    make_pack(tmp_path)                    # no Companion pack, no TI pack
    model, _t, problems = build(tmp_path, ("ars", "analysis", "ti"))
    assert problems == []
    stubs = model["story"]["stubs"]
    assert "analysis:waves" in stubs and "ti:attrition" in stubs
    assert stubs["ti:attrition"]["blocks"][0]["t"] == "needs"
    assert "Transaction Intelligence build" in stubs["ti:attrition"]["blocks"][0]["fix"]


def test_unmapped_branches_read_as_branch_numbers_never_a_naked_digit(tmp_path):
    make_pack(tmp_path)
    make_companion(tmp_path)
    make_ti(tmp_path)
    model, _t, _p = build(tmp_path, ("ars", "analysis", "ti"))
    sc = next(s for e in model["programs"] if e["key"] == "analysis" for s in e["screens"] if s["id"] == "scorecard")
    assert "Branch 2" in sc["headline"] and "Branch 17" in sc["headline"]


def test_the_control_is_described_by_the_two_percent_band(tmp_path):
    make_pack(tmp_path)
    make_companion(tmp_path)
    model, _t, _p = build(tmp_path, ("ars", "analysis"))
    resp = next(s for e in model["programs"] if e["key"] == "analysis" for s in e["screens"] if s["id"] == "response")
    assert "rose 10.0%" in resp["headline"]            # 10% is outside the band, so it is stated, not "almost flat"


def test_the_product_name_is_one_constant_the_page_reads():
    assert review_page.PRODUCT_NAME == "Live Review"
    html = render_page({"product": review_page.PRODUCT_NAME, "client": {"id": "1", "name": "X"}, "programs": []}, "t")
    assert "<title>Live Review</title>" in html
