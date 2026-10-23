# Ported from ARS v5 02-Scripts/tests/test_facts.py at a491b5c (James Gilmore); logic unchanged.
"""The fact layer: every account-level quantity, derived once."""
import pathlib
import sys

import pandas as pd
import pytest


from ti.core.facts import build_facts
from ti.core.periods import Month

ANCHOR = Month.from_tag("Jul26")


def _odd():
    return pd.DataFrame({"Acct Number": ["A1", "A2", "A3"],
                         "Branch": ["1", "2", "1"]})


# ---- identity -------------------------------------------------------------

def test_frame_shares_the_source_index():
    """Facts are a view on the same accounts, so masks compose without reindexing."""
    df = _odd()
    assert list(build_facts(df, {}, ANCHOR).frame.index) == list(df.index)


def test_account_id_prefers_acct_number():
    facts = build_facts(_odd(), {}, ANCHOR)
    assert list(facts.frame["account_id"]) == ["A1", "A2", "A3"]


def test_entity_id_falls_back_to_account_when_no_member_key():
    """No client file carries a CIF today. entity_id exists anyway so member
    rollups are written once and simply produce 1:1 groups until one arrives."""
    facts = build_facts(_odd(), {}, ANCHOR)
    assert list(facts.frame["entity_id"]) == ["A1", "A2", "A3"]


def test_branch_name_uses_the_client_mapping():
    config = {"BranchMapping": {"1": "Riverside", "2": "Oak Park"}}
    facts = build_facts(_odd(), config, ANCHOR)
    assert list(facts.frame["branch_name"]) == ["Riverside", "Oak Park", "Riverside"]


def test_missing_branch_column_warns_and_does_not_raise():
    facts = build_facts(pd.DataFrame({"Acct Number": ["A1"]}), {}, ANCHOR)
    assert facts.frame["branch_name"].isna().all()
    assert any("Branch" in w for w in facts.warnings)


# ---- lifecycle ------------------------------------------------------------

def _lifecycle_odd():
    """Anchor Jul26, so the window is Aug25..Jul26 inclusive."""
    return pd.DataFrame({
        "Acct Number": ["OPEN", "CLOSED_IN", "CLOSED_BEFORE"],
        "Date Opened": ["2019-01-15", "2020-06-01", "2018-03-01"],
        "Date Closed": [None, "2026-03-10", "2024-02-01"],
    })


def test_is_open_is_measured_at_the_anchor_not_today():
    facts = build_facts(_lifecycle_odd(), {}, ANCHOR)
    assert list(facts.frame["is_open"]) == [True, False, False]


def test_closed_in_window_is_the_trailing_twelve_months():
    facts = build_facts(_lifecycle_odd(), {}, ANCHOR)
    assert list(facts.frame["closed_in_window"]) == [False, True, False]


def test_tenure_is_years_to_the_anchor_month_end():
    facts = build_facts(_lifecycle_odd(), {}, ANCHOR)
    assert facts.frame["tenure_years"].iloc[0] == pytest.approx(7.5, abs=0.1)


def test_missing_date_closed_means_every_account_is_open():
    df = pd.DataFrame({"Acct Number": ["A1"], "Date Opened": ["2020-01-01"]})
    facts = build_facts(df, {}, ANCHOR)
    assert bool(facts.frame["is_open"].iloc[0]) is True
    assert bool(facts.frame["closed_in_window"].iloc[0]) is False


# ---- money ----------------------------------------------------------------

def _money_odd():
    return pd.DataFrame({
        "Acct Number": ["FALLING", "RISING", "NO_AVG"],
        "Curr Bal": [4000.0, 900.0, 250.0],
        "Avg Bal": [6000.0, 500.0, None],
    })


def test_balance_delta_is_current_minus_average():
    frame = build_facts(_money_odd(), {}, ANCHOR).frame
    assert frame["balance_delta"].iloc[0] == pytest.approx(-2000.0)
    assert frame["balance_delta"].iloc[1] == pytest.approx(400.0)


def test_missing_average_leaves_delta_null_not_zero():
    """A zero delta claims the balance held steady. Absent data is not that."""
    assert pd.isna(build_facts(_money_odd(), {}, ANCHOR).frame["balance_delta"].iloc[2])


def test_missing_balance_columns_warn():
    facts = build_facts(pd.DataFrame({"Acct Number": ["A1"]}), {}, ANCHOR)
    assert facts.frame["curr_bal"].isna().all()
    assert any("Curr Bal" in w for w in facts.warnings)


# ---- activity -------------------------------------------------------------

def _spend_odd():
    """Six spend months ending at the anchor, deliberately out of column order
    so the chronological sort is exercised."""
    return pd.DataFrame({
        "Acct Number": ["STEADY", "HALVED", "DORMANT"],
        "Jul26 Spend": [100.0, 50.0, 0.0],
        "Feb26 Spend": [100.0, 100.0, 80.0],
        "Mar26 Spend": [100.0, 100.0, 80.0],
        "Apr26 Spend": [100.0, 100.0, 0.0],
        "May26 Spend": [100.0, 50.0, 0.0],
        "Jun26 Spend": [100.0, 50.0, 0.0],
    })


def test_recent_and_prior_use_chronological_months_not_column_order():
    frame = build_facts(_spend_odd(), {}, ANCHOR).frame
    assert frame["spend_recent"].iloc[1] == pytest.approx(50.0)
    assert frame["spend_prior"].iloc[1] == pytest.approx(100.0)


def test_spend_ratio_is_recent_over_prior():
    frame = build_facts(_spend_odd(), {}, ANCHOR).frame
    assert frame["spend_ratio"].iloc[1] == pytest.approx(0.5)


def test_spend_ratio_is_null_when_there_was_no_prior_spend():
    """Dividing by zero prior spend is not a 0% decline; it is unmeasurable."""
    df = _spend_odd()
    df.loc[3] = ["NEW", 40.0, 0.0, 0.0, 0.0, 0.0, 20.0]
    assert pd.isna(build_facts(df, {}, ANCHOR).frame["spend_ratio"].iloc[3])


def test_months_quiet_counts_trailing_zero_months_only():
    frame = build_facts(_spend_odd(), {}, ANCHOR).frame
    assert int(frame["months_quiet"].iloc[2]) == 4
    assert int(frame["months_quiet"].iloc[0]) == 0


def test_too_few_spend_months_warns_and_leaves_activity_null():
    df = pd.DataFrame({"Acct Number": ["A1"], "Jul26 Spend": [10.0]})
    facts = build_facts(df, {}, ANCHOR)
    assert pd.isna(facts.frame["spend_recent"].iloc[0])
    assert any("Spend" in w for w in facts.warnings)


# ---- programme ------------------------------------------------------------

def test_programme_flags_reuse_the_canonical_predicates():
    """has_debit must agree with core.subsets.has_debit -- one definition."""
    from ti.core.subsets import has_debit as canonical

    df = pd.DataFrame({
        "Acct Number": ["A1", "A2", "A3"],
        "Debit?": ["Yes", "N", "D"],
        "Business?": ["N", "Y", "N"],
        "Prod Code": ["301010110", "301020110", "301010110"],
        "Prod Desc": ["Free Checking", "Money Market", "Free Checking"],
    })
    frame = build_facts(df, {}, ANCHOR).frame
    assert list(frame["has_debit"]) == list(canonical(df))
    assert list(frame["is_business"]) == [False, True, False]
    assert frame["prod_desc"].iloc[1] == "Money Market"


def test_ics_source_is_empty_string_when_the_account_is_not_ics():
    df = pd.DataFrame({"Acct Number": ["A1", "A2"], "DM-REF Source": ["DM", ""]})
    assert list(build_facts(df, {}, ANCHOR).frame["ics_source"]) == ["DM", ""]


def test_absent_ics_column_gives_every_account_an_empty_source():
    facts = build_facts(pd.DataFrame({"Acct Number": ["A1"]}), {}, ANCHOR)
    assert facts.frame["ics_source"].iloc[0] == ""


# ---- optional competitor facts (attached by the TXN pipeline) -------------

def test_competitor_columns_are_absent_until_attached():
    """The ODD cannot see a competitor. Absent, not zero -- zero would claim
    the account banks nowhere else, which is a finding we have not made."""
    frame = build_facts(_odd(), {}, ANCHOR).frame
    assert "competitor_dollars" not in frame.columns


def test_attach_competitors_joins_on_account_id():
    from ti.core.facts import attach_competitors

    facts = build_facts(_odd(), {}, ANCHOR)
    attach_competitors(facts, [["A1", "BIG BANK", 400.0],
                               ["A1", "OTHER CU", 100.0],
                               ["A3", "BIG BANK", 50.0]])
    frame = facts.frame
    assert frame["competitor_dollars"].iloc[0] == pytest.approx(500.0)
    assert frame["competitor_institutions"].iloc[0] == 2
    assert frame["competitor_dollars"].iloc[1] == 0.0
    assert frame["competitor_institutions"].iloc[2] == 1


def test_attach_competitors_with_no_rows_still_creates_the_columns():
    """An empty transaction join is a measured zero, unlike an absent one."""
    from ti.core.facts import attach_competitors

    facts = build_facts(_odd(), {}, ANCHOR)
    attach_competitors(facts, [])
    assert (facts.frame["competitor_dollars"] == 0).all()
