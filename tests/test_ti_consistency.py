# Ported from ARS v5 02-Scripts/tests/test_consistency.py at a491b5c (James Gilmore); logic unchanged.
# v5's test_card_spend_reconciliation_warns_on_divergence is not ported: it checks run.py's
# ODD-vs-transaction card-spend reconciliation through v5's whole metrics harness, not this module.
"""The consistency audit: the same concept must carry ONE number everywhere
it appears. Every rule exists because two surfaces once disagreed on the
real 1585 deck (hero 12.4% vs table 11.4%; three responder counts; P&L
labels) -- James: 'fail safe if the numbers dont align'."""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.monthly_analysis import consistency  # noqa: E402


def clean_metrics():
    return {
        "campaign_rates": [["Mar26", 5864, 734, 12.5], ["May26", 5595, 639, 11.4]],
        "latest_mailing": "May26", "latest_mailed": 5595,
        "latest_responders": 639, "latest_resprate": 11.4,
        "resprate_mean": 12.0,
        "resprate_best": ["Mar26", 12.5], "resprate_worst": ["May26", 11.4],
        "reach_total": 3852, "depth": [1834, 1120, 898],
        "reach_cumulative": [["Mar26", 3400, 27.5], ["May26", 3852, 31.2]],
        "n_total": 44003, "n_eligible": 12347, "eligibility_rate": 28.1,
        "n_eligible_personal": 10510, "n_eligible_business": 1837,
        "wb_revenue_ltd": 989840, "wb_costs_ltd": -302204,
        "wb_profit_ltd": 687636,
        "value_by_response": [
            {"group": "Responder", "n": 3516, "take_rate": 98.0},
            {"group": "Mailed non-responder", "n": 2358, "take_rate": 95.0},
            {"group": "Not mailed", "n": 4636, "take_rate": 56.0}],
    }


def test_clean_metrics_pass():
    assert consistency.audit(clean_metrics()) == []


def test_hero_vs_table_divergence_is_caught():
    m = clean_metrics()
    m["latest_resprate"] = 12.4          # the actual 1585 bug
    m["latest_mailed"] = 4064
    m["latest_responders"] = 502
    v = consistency.audit(m)
    assert any("latest" in x for x in v)


def test_campaign_row_rate_must_recompute():
    m = clean_metrics()
    m["campaign_rates"][0][3] = 9.9      # 734/5864 is not 9.9%
    assert any("campaign_rates" in x for x in consistency.audit(m))


def test_mean_ties_to_the_rows():
    m = clean_metrics()
    m["resprate_mean"] = 10.0
    assert any("mean" in x.lower() for x in consistency.audit(m))


def test_depth_must_sum_to_reach():
    m = clean_metrics()
    m["depth"] = [1000, 1000, 1000]
    assert any("depth" in x for x in consistency.audit(m))


def test_cumulative_reach_ends_at_reach_total():
    m = clean_metrics()
    m["reach_cumulative"][-1][1] = 3516  # the OTHER responder count
    assert any("reach" in x for x in consistency.audit(m))


def test_eligible_split_must_sum():
    m = clean_metrics()
    m["n_eligible_business"] = 999
    assert any("personal + business" in x for x in consistency.audit(m))


def test_workbook_ledger_must_tie():
    m = clean_metrics()
    m["wb_profit_ltd"] = 700000
    assert any("workbook" in x.lower() for x in consistency.audit(m))


def test_value_groups_cannot_exceed_their_bases():
    m = clean_metrics()
    m["value_by_response"][0]["n"] = 4000  # more responders than reach_total
    assert any("value_by_response" in x for x in consistency.audit(m))


def test_absent_keys_are_not_violations():
    assert consistency.audit({}) == []
    assert consistency.audit({"campaign_rates": []}) == []


# ---------------------------------------------------------------------------
# Round 2: the former OPEN list, promoted (James: '05 Not yet guarded')
# ---------------------------------------------------------------------------

def rich_metrics():
    m = clean_metrics()
    m.update({
        "rege_l12m_pct": 34.0, "rege_pct": 34.8,
        "syn_scorecard": [
            ["Reg E opt-in, last 12 months", 34.0, "%", "vs historical 34.8%",
             -0.8, "amber"],
            ["Latest response rate", 11.4, "%", "vs mean of all waves 12.0%",
             -0.6, "amber"],
        ],
        "syn_opportunities": [
            {"label": "Top three debit leaks closed", "n": 1200,
             "value": 350000, "basis": "value_leak_top3", "kind": "revenue"},
            {"label": "Prose-based item", "n": 10, "value": 999,
             "basis": "fin Credit Cards dollars x ICRate", "kind": "revenue"},
        ],
        "value_leak_top3": 350000,
        "take_branch": [["Dresden", 400, 500, 81.0], ["Kevil", 300, 460, 65.0]],
        "dctr_branch_best": ["Dresden", 81.0, 500],
        "dctr_branch_worst": ["Kevil", 65.0, 460],
        "dctr_branch_spread_pp": 16.0,
        "rege_branch": [["Online", 210, 500, 42.0], ["Fancy Farm", 55, 250, 22.0]],
        "rege_branch_best": ["Online", 42.0, 500],
        "rege_branch_worst": ["Fancy Farm", 22.0, 250],
        "rege_branch_spread_pp": 20.0,
    })
    return m


def txn_metrics_fixture():
    return {
        "fin_accounts_total": 9100, "fin_leaking_accounts": 3458,
        "fin_leaking_pct": 38.0,
        "fin_by_category": [["Credit Cards", 1200, 13.2, 9000, 1200000, 1000,
                             "leakage", True, 55.0, 40.0]],
        "comp_accounts_total": 9100, "comp_with_competitor": 1274,
        "comp_with_competitor_pct": 14.0,
    }


def test_rich_metrics_pass():
    assert consistency.audit(rich_metrics(), txn_metrics_fixture()) == []


def test_scorecard_row_must_tie_to_its_source_key():
    m = rich_metrics()
    m["syn_scorecard"][0][1] = 40.0        # Reg E row drifts from rege_l12m_pct
    v = consistency.audit(m)
    assert any("scorecard" in x for x in v)


def test_scorecard_txn_row_ties_via_txn_dict():
    m = rich_metrics()
    m["syn_scorecard"].append(
        ["Personal accounts leaking to external financial products", 30.0,
         "%", "no responder comparator", None, "grey"])
    v = consistency.audit(m, txn_metrics_fixture())   # txn says 38.0
    assert any("scorecard" in x and "leaking" in x for x in v)


def test_opportunity_value_ties_to_its_basis_key():
    m = rich_metrics()
    m["syn_opportunities"][0]["value"] = 999999
    assert any("opportunit" in x for x in consistency.audit(m))


def test_prose_basis_is_skipped():
    m = rich_metrics()
    m["syn_opportunities"][1]["value"] = 123456   # basis is prose, no key
    assert consistency.audit(m, txn_metrics_fixture()) == []


def test_branch_callout_must_match_its_table():
    m = rich_metrics()
    m["dctr_branch_best"] = ["Dresden", 90.0, 500]     # table says 81.0
    assert any("dctr_branch_best" in x for x in consistency.audit(m))


def test_branch_spread_recomputes():
    m = rich_metrics()
    m["rege_branch_spread_pp"] = 11.6
    assert any("spread" in x for x in consistency.audit(m))


def test_txn_internal_pcts_and_per_acct_recompute():
    t = txn_metrics_fixture()
    t["fin_leaking_pct"] = 25.0            # 3458/9100 is 38.0
    assert any("fin_leaking_pct" in x for x in consistency.audit({}, t))
    t2 = txn_metrics_fixture()
    t2["fin_by_category"][0][5] = 500      # 1200000/1200 = 1000
    assert any("fin_by_category" in x for x in consistency.audit({}, t2))
    t3 = txn_metrics_fixture()
    t3["comp_with_competitor_pct"] = 5.0   # 1274/9100 is 14.0
    assert any("comp_with_competitor_pct" in x for x in consistency.audit({}, t3))


def test_responses_total_must_equal_the_offer_row_sum():
    m = clean_metrics()
    m["responses_total"] = 9999          # rows sum to 734+639
    assert any("responses_total" in x for x in consistency.audit(m))


def test_reach_cannot_exceed_responses():
    m = clean_metrics()
    m["responses_total"] = 1373
    m["reach_total"] = 1400              # unique > events is impossible
    m["depth"] = [700, 400, 300]
    m["reach_cumulative"][-1][1] = 1400
    m["value_by_response"] = []
    assert any("reach_total" in x and "responses_total" in x
               for x in consistency.audit(m))
