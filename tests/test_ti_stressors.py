# Ported from ARS v5 02-Scripts/tests/test_stressors.py at a491b5c (James Gilmore); logic unchanged.
"""The stressor count: how many named conditions an account trips at once."""
import pathlib
import sys

import pandas as pd


from ti.core.conditions import CONDITIONS
from ti.core.facts import build_facts
from ti.core.periods import Month
from ti.monthly_analysis.stressors import compute, count_stressors, write_roster

ANCHOR = Month.from_tag("Jul26")


def _odd():
    return pd.DataFrame({
        "Acct Number": ["BOTH", "ONE", "NEITHER"],
        "Debit?": ["Yes", "Yes", "Yes"],
        "Date Opened": ["2019-01-15", "2019-01-15", "2019-01-15"],
        # Above balance.FLIGHT_RISK_THRESHOLD ($25k) for BOTH and NEITHER, so
        # the flight condition is genuinely exercised rather than filtered out
        # by the threshold before it is ever evaluated.
        "Curr Bal": [40000.0, 500.0, 40000.0],
        "Avg Bal": [55000.0, 500.0, 30000.0],
        "Jul26 Spend": [0.0, 100.0, 120.0],
        "Feb26 Spend": [90.0, 100.0, 100.0],
        "Mar26 Spend": [90.0, 100.0, 100.0],
        "Apr26 Spend": [0.0, 100.0, 100.0],
        "May26 Spend": [0.0, 100.0, 110.0],
        "Jun26 Spend": [0.0, 100.0, 130.0],
    })


def test_count_is_the_number_of_conditions_tripped():
    result = count_stressors(build_facts(_odd(), {}, ANCHOR))
    assert result["count"].iloc[0] >= 2
    assert result["count"].iloc[2] == 0


def test_nested_conditions_score_once_not_twice():
    """gone_quiet nests inside retention_at_risk. An account that is silent
    trips both, and must score one point for the one behaviour."""
    result = count_stressors(build_facts(_odd(), {}, ANCHOR))
    both = result.iloc[0]
    assert bool(both["gone_quiet"]) and bool(both["retention_at_risk"])
    tripped = sum(bool(both[n]) for n in CONDITIONS if n in result.columns)
    assert both["count"] < tripped, "nesting was not collapsed"


def test_names_column_lists_the_conditions_in_plain_language():
    result = count_stressors(build_facts(_odd(), {}, ANCHOR))
    assert "Deposits leaving" in result["names"].iloc[0]


def test_raw_values_travel_beside_every_flag():
    """The count means nothing without the numbers that produced it."""
    result = count_stressors(build_facts(_odd(), {}, ANCHOR))
    for col in ("curr_bal", "avg_bal", "balance_delta", "spend_recent",
                "spend_prior", "spend_ratio", "months_quiet", "tenure_years"):
        assert col in result.columns, f"{col} missing from the stressor frame"


# ---- the section ----------------------------------------------------------

def _subsets(df):
    from ti.core.subsets import build_subsets

    return build_subsets(df, {}, ANCHOR)


def test_section_declares_its_base_like_dctr_does():
    """No slide should have to guess which population a rate was taken on."""
    out = compute(_subsets(_odd()), {}, lambda m: None)
    assert out["stress_base"] == "Open at anchor"


def test_section_reports_what_it_could_not_build():
    bare = pd.DataFrame({"Acct Number": ["A1"], "Debit?": ["Yes"]})
    out = compute(_subsets(bare), {}, lambda m: None)
    assert out.get("stress_skipped"), "a run with no balances must say so"


def test_section_is_registered_in_the_orchestrator():
    # RPE: the cut runs its ODD sections from ti/odd_sections.py, not v5's metrics.SECTIONS
    from ti.odd_sections import PARITY

    assert "stressors" in PARITY


def test_section_never_leaves_a_dataframe_in_the_metrics():
    """A DataFrame in the metrics dict reaches leaks, synthesis and the JSON
    encoder, none of which want one. run.py pops it; nothing else may see it."""
    import json

    out = compute(_subsets(_odd()), {}, lambda m: None)
    frame = out.pop("_stress_frame", None)
    assert frame is not None, "the frame must be handed over under this key"
    json.dumps(out, default=str)


# ---- the roster -----------------------------------------------------------

def test_roster_sorts_by_count_then_dollars(tmp_path):
    frame = count_stressors(build_facts(_odd(), {}, ANCHOR))
    written = pd.read_csv(write_roster(frame, tmp_path))
    assert list(written["count"]) == sorted(written["count"], reverse=True)


def test_roster_carries_the_raw_values_not_just_the_score(tmp_path):
    frame = count_stressors(build_facts(_odd(), {}, ANCHOR))
    written = pd.read_csv(write_roster(frame, tmp_path))
    for col in ("curr_bal", "avg_bal", "balance_delta", "spend_ratio",
                "months_quiet", "names"):
        assert col in written.columns


def test_a_condition_true_of_nearly_everyone_is_refused_not_counted(monkeypatch):
    """RALLY's deposits condition was true of 97.3% of the base and produced
    59.9% of the book at 2+ stressors with no score-0 row at all -- a signal
    that cannot separate anyone, wearing the shape of a finding.

    Tested against a deliberately saturated condition rather than a real one,
    so the guard is exercised even after a saturating signal is removed from
    the registry.
    """
    from ti.core import conditions as C
    from ti.core.subsets import build_subsets

    always = C.Condition(
        name="always_true", label="Always true", base="Eligible",
        fn=lambda facts: pd.Series(True, index=facts.frame.index),
        requires=("account_id",))
    monkeypatch.setitem(C.CONDITIONS, "always_true", always)

    df = pd.concat([_odd()] * 40, ignore_index=True)
    warned = []
    out = compute(build_subsets(df, {}, ANCHOR), {}, warned.append)

    assert any("saturation" in w for w in warned), \
        f"the saturated condition must be named; got {warned}"
    assert "Always true" not in (out.get("stress_available") or [])
    assert ["Always true", 100.0] in (out.get("stress_saturated") or [])
