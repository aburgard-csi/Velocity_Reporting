"""The ARS 2 : 1 revenue guarantee (Aaron, 2026-09-21).

The arithmetic is the point of these tests: a months-to-cover figure that ignores the
cost accruing over those same months would print a number no client will ever see come
true, and the caption must never describe a shortfall as room above the guarantee.

Synthetic clients, round numbers.
"""
import math

import pytest

import revenue_guarantee_slide as RG


def base(cost, revenue, monthly=None, months=24, cur_costs=None):
    """A base.json-shaped dict with only the keys the guarantee reads."""
    return {
        "ltd_costs": -cost,                       # the workbook carries cost negative
        "ltd_revenue": revenue,
        "months": months,
        "cur_costs": cur_costs,
        "monthly_rev_last12": monthly or [],
    }


def months(vals, start=1):
    labels = ["Jan 2026", "Feb 2026", "Mar 2026", "Apr 2026", "May 2026", "Jun 2026",
              "Jul 2026", "Aug 2026", "Sep 2026", "Oct 2026", "Nov 2026", "Dec 2026"]
    return list(zip(labels[start - 1:start - 1 + len(vals)], vals))


def test_the_minimum_is_twice_cost_and_the_ratio_is_recomputed():
    g = RG.guarantee(base(100_000, 570_000))
    assert g["minimum"] == 200_000
    assert g["ratio"] == pytest.approx(5.7)
    assert g["met"] is True
    assert g["surplus"] == 370_000
    assert g["gap"] is None


def test_a_short_program_reports_the_gap_not_a_surplus():
    g = RG.guarantee(base(100_000, 150_000))
    assert g["met"] is False
    assert g["gap"] == 50_000
    assert g["surplus"] is None
    cap = RG._caption(g)
    assert "short of the guaranteed minimum" in cap
    assert "above" not in cap


def test_months_to_cover_accrues_cost_over_the_same_months():
    # revenue $12k/mo, cost $4k/mo: each month closes 12k - 2*4k = 4k of a 50k gap.
    g = RG.guarantee(base(100_000, 150_000, monthly=months([12_000] * 12), cur_costs=4_000))
    assert g["run_rate"] == pytest.approx(12_000)
    assert g["monthly_cost"] == pytest.approx(4_000)
    assert g["months_to_cover"] == math.ceil(50_000 / 4_000) == 13
    # gap / run rate alone would have said 5 months — the number that ignores cost
    assert g["months_to_cover"] > math.ceil(50_000 / 12_000)


def test_a_gap_that_never_closes_says_so():
    # revenue $7k/mo against cost $4k/mo: the minimum rises $8k a month, faster than revenue
    g = RG.guarantee(base(100_000, 150_000, monthly=months([7_000] * 12), cur_costs=4_000))
    assert g["months_to_cover"] is None
    cap = RG._caption(g)
    assert "does not close" in cap
    assert "closes in about" not in cap


def test_monthly_cost_falls_back_to_the_program_to_date_average():
    g = RG.guarantee(base(96_000, 150_000, monthly=months([12_000] * 12), months=24))
    assert g["monthly_cost"] == pytest.approx(4_000)          # 96,000 / 24
    assert g["monthly_cost_from"] == "the program-to-date average monthly cost"


def test_the_run_rate_uses_complete_months_only_and_states_the_one_left_out():
    # eleven months at 12k, then a partial month far below half the median
    g = RG.guarantee(base(100_000, 150_000,
                          monthly=months([12_000] * 11 + [400]), cur_costs=4_000))
    assert g["run_months"] == 11
    assert g["run_rate"] == pytest.approx(12_000)
    assert g["left_out"] == ["Dec 2026"]
    assert "Dec 2026 left out: incomplete in this extract." in RG._caption(g)


def test_no_cost_booked_is_stated_never_zeroed():
    g = RG.guarantee(base(0, 0))
    assert g["measurable"] is False
    assert g["ratio"] is None and g["met"] is None
    cap = RG._caption(g)
    assert "no program cost to date" in cap
    assert "0 : 1" not in cap


def test_the_multiple_lives_in_one_place():
    assert RG.MULTIPLE == 2.0
    g = RG.guarantee(base(50_000, 80_000))
    assert g["minimum"] == RG.MULTIPLE * g["cost"]


def test_the_builder_inserts_it_after_financial_performance():
    import os
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "build", "ars_pipeline", "build_ars_gen.py"),
               encoding="utf-8").read()
    assert "revenue_guarantee_slide.add_revenue_guarantee_slide(" in src
    assert 'after_title="Financial Performance"' in src
    # its note is written by the module, so the generic note pass must skip it
    assert "_MODULE_NOTED.append(_rg_slide)" in src
