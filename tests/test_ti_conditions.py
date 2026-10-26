# Ported from ARS v5 02-Scripts/tests/test_conditions.py at a491b5c (James Gilmore); logic unchanged.
"""Named conditions: one definition each, on a declared base."""
import pathlib
import sys

import pandas as pd


from ti.core.conditions import CONDITIONS, available, evaluate
from ti.core.facts import build_facts
from ti.core.periods import Month

ANCHOR = Month.from_tag("Jul26")


def _odd():
    return pd.DataFrame({
        "Acct Number": ["FLIGHT", "QUIET", "FINE"],
        "Debit?": ["Yes", "Yes", "Yes"],
        "Curr Bal": [9000.0, 400.0, 9000.0],
        "Avg Bal": [12000.0, 400.0, 8000.0],
        "Jul26 Spend": [50.0, 0.0, 120.0],
        "Feb26 Spend": [60.0, 90.0, 100.0],
        "Mar26 Spend": [60.0, 90.0, 100.0],
        "Apr26 Spend": [60.0, 0.0, 100.0],
        "May26 Spend": [50.0, 0.0, 110.0],
        "Jun26 Spend": [50.0, 0.0, 130.0],
    })


def test_every_condition_declares_a_base():
    """The three-bases problem is a labelling failure. No condition ships
    without saying which population it was measured on."""
    assert CONDITIONS, "registry is empty"
    for name, cond in CONDITIONS.items():
        assert cond.base, f"{name} declares no base"
        assert cond.label, f"{name} has no plain-language label"


def test_evaluate_returns_booleans_on_the_facts_index():
    facts = build_facts(_odd(), {}, ANCHOR)
    result = evaluate(facts)
    assert list(result.index) == list(facts.frame.index)
    for col in result.columns:
        assert result[col].dtype == bool, f"{col} is not boolean"


def test_balance_flight_agrees_with_the_chapter_that_owns_it():
    """conditions must not hold a second opinion about deposit flight."""
    from ti.monthly_analysis.balance import flight_mask

    facts = build_facts(_odd(), {}, ANCHOR)
    expected = flight_mask(facts.frame["curr_bal"].fillna(0),
                           facts.frame["avg_bal"])
    got = evaluate(facts, ["balance_flight"])["balance_flight"]
    assert list(got) == list(expected)


def test_available_reports_only_conditions_whose_inputs_exist():
    bare = build_facts(pd.DataFrame({"Acct Number": ["A1"]}), {}, ANCHOR)
    assert "balance_flight" not in available(bare), "no balances present"


def test_nesting_is_declared_not_discovered():
    """Two conditions where one implies the other must say so, or a count
    gives the same behaviour two points."""
    for name, cond in CONDITIONS.items():
        if cond.nests_within:
            assert cond.nests_within in CONDITIONS, \
                f"{name} nests within unknown condition {cond.nests_within}"


# ---- task 8: retention health promoted out of local scope -----------------

def test_classify_health_is_importable_and_ratio_based():
    """A large account losing 0.3% must not outrank a small one losing 80%."""
    from ti.monthly_analysis.retention import classify_health

    health = classify_health(
        pd.Series([100.0, 20.0, 0.0, 500.0]),
        pd.Series([100.0, 100.0, 100.0, 5000.0]),
        pd.Series([0, 0, 3, 0]),
        pd.Series([True, True, True, True]))
    assert list(health) == ["Active", "Cooling", "Dormant", "Cooling"]


def test_gone_quiet_declares_that_it_nests_inside_retention_at_risk():
    """Three silent months makes an account Dormant, which is at risk.
    Counting both gives one behaviour two points."""
    assert CONDITIONS["gone_quiet"].nests_within == "retention_at_risk"


def test_retention_at_risk_is_registered_and_has_a_base():
    assert CONDITIONS["retention_at_risk"].base == "Eligible"


# ---- task 9: the hazard-peak band -----------------------------------------

def test_peak_band_needs_a_real_cohort_before_naming_a_peak():
    """A bucket with a handful of resolved accounts is noise, not a peak."""
    from ti.monthly_analysis.attrition import MIN_RESOLVED_FOR_PEAK, peak_band

    assert peak_band([["0-6 mo", MIN_RESOLVED_FOR_PEAK - 1, 5, 90.0]]) is None


def test_peak_band_returns_the_bucket_with_the_highest_hazard():
    from ti.monthly_analysis.attrition import MIN_RESOLVED_FOR_PEAK, peak_band

    n = MIN_RESOLVED_FOR_PEAK + 10
    rows = [["0-6 mo", n, 5, 4.0], ["6-12 mo", n, 30, 22.0], ["1-2 yr", n, 8, 6.0]]
    assert peak_band(rows) == (6, 12)


def test_hazard_peak_tenure_is_registered():
    assert "hazard_peak_tenure" in CONDITIONS
    assert CONDITIONS["hazard_peak_tenure"].base == "Open at anchor"


def test_hazard_peak_flags_nobody_when_no_peak_was_named():
    """No named peak must mean no flag, never every account."""
    facts = build_facts(_odd(), {}, ANCHOR)
    facts.peak_tenure_band = None
    assert not evaluate(facts, ["hazard_peak_tenure"])["hazard_peak_tenure"].any()


# ---- deposit conditions (present only when the deposits file was loaded) ---

def test_deposit_conditions_are_unavailable_without_the_file():
    """An ODD-only run must report them as not built, never score without them."""
    facts = build_facts(_odd(), {}, ANCHOR)
    names = available(facts)
    assert "deposit_decelerating" not in names


def test_deposit_conditions_light_up_once_the_file_is_attached():
    from ti.core.facts import attach_deposits

    facts = build_facts(_odd(), {}, ANCHOR)
    cadence = pd.DataFrame({
        "acct": ["FLIGHT", "QUIET", "FINE"],
        "n_deposits": [12, 2, 12],
        "median_gap_days": [14.0, 90.0, 14.0],
        "amount_cv": [0.02, 0.9, 0.02],
        "median_amount": [1500.0, 40.0, 1500.0],
        "probable_direct_deposit": [True, False, True]})
    months = pd.date_range("2026-02-01", periods=6, freq="MS")
    monthly = pd.DataFrame(
        [["FLIGHT", m, 1, 1000.0 if i < 3 else 200.0] for i, m in enumerate(months)]
        + [["FINE", m, 1, 1000.0] for m in months],
        columns=["acct", "date", "dep_count", "dep_amount"])
    attach_deposits(facts, cadence, monthly)

    assert "deposit_decelerating" in available(facts)
    flags = evaluate(facts, ["deposit_decelerating"])
    assert bool(flags["deposit_decelerating"].iloc[0]), "FLIGHT's deposits halved"
    # the fact is still derived and still travels in the roster
    assert facts.frame["probable_direct_deposit"].iloc[0]


def test_no_recurring_deposit_is_not_a_scoring_condition():
    """Payroll lands in ONE account per member, so at account grain the
    condition was true of 97.3% of RALLY's base. Same objection that keeps
    "only one product relationship" out: a member-level question asked of
    account-level data. The fact stays; the point does not."""
    assert "no_direct_deposit" not in CONDITIONS


def _deposits_for(accts, amounts_by_month):
    """A deposits frame: one credit per month per account, amounts given as
    six values (three prior months, three recent)."""
    rows = []
    for acct, amounts in zip(accts, amounts_by_month):
        for k, amount in enumerate(amounts):
            rows.append([acct, pd.Timestamp("2026-02-15") + pd.DateOffset(months=k),
                         1, float(amount)])
    return pd.DataFrame(rows, columns=["acct", "date", "dep_count", "dep_amount"])


def test_flight_mask_reads_real_inflow_when_it_is_given():
    """The balance proxy says 'current below average'. Given the account's
    own inflow ratio, flight means the credits are falling, and a balance
    that dipped while pay kept landing is not flight."""
    from ti.monthly_analysis.balance import flight_mask

    current = pd.Series([30_000.0, 30_000.0, 30_000.0, 5_000.0])
    average = pd.Series([35_000.0, 25_000.0, 35_000.0, 9_000.0])
    ratio = pd.Series([1.0, 0.5, float("nan"), 0.5])
    got = flight_mask(current, average, inflow_ratio=ratio)
    # dipped but still paid: no. paid less, balance up: yes. unknown inflow:
    # no. paid less but small balance: no.
    assert list(got) == [False, True, False, False]
    assert list(flight_mask(current, average)) == [True, False, True, False]


def test_balance_flight_uses_inflow_once_deposits_are_attached():
    from ti.core.deposits import cadence, monthly
    from ti.core.facts import attach_deposits
    from ti.monthly_analysis.balance import flight_mask

    odd = _odd()
    odd["Curr Bal"] = [30_000.0, 30_000.0, 30_000.0]
    odd["Avg Bal"] = [35_000.0, 25_000.0, 35_000.0]
    raw = _deposits_for(["FLIGHT", "QUIET", "FINE"],
                        [[900, 900, 900, 900, 900, 900],
                         [900, 900, 900, 300, 300, 300],
                         [900, 900, 900, 900, 900, 900]])
    facts = build_facts(odd, {}, ANCHOR)
    attach_deposits(facts, cadence(raw), monthly(raw))
    got = evaluate(facts, ["balance_flight"])["balance_flight"]
    expected = flight_mask(facts.frame["curr_bal"].fillna(0),
                           facts.frame["avg_bal"],
                           inflow_ratio=facts.frame["deposit_ratio"])
    assert list(got) == list(expected) == [False, True, False]


def test_balance_flight_nests_within_deposit_deceleration():
    """On the inflow basis every flight account is a decelerating account
    with a high balance. Scoring both would give one behaviour two points."""
    assert CONDITIONS["balance_flight"].nests_within == "deposit_decelerating"
