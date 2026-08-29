"""oddd_optimize classifiers — status and Reg E normalization.

These are four lines of table-driven logic that decide how tens of thousands of
accounts are bucketed, and they have been wrong in production twice:

  * 2026-08-28 — 1549 Wellworth fills `Stat Code` (O/C/X) and leaves `Stat Desc`
    BLANK on every non-open account. classify_status read only the description,
    so 18,274 of 50,218 rows came back "Other".
  * 2026-07-25 — core lifecycle wording ("Purge at Yearend", "Pending Closeout",
    "New This Cycle", "Pending Activation") matched none of the generic patterns.

Ordering matters as much as the patterns: "inactive" must beat "active", and the
lifecycle phrases must run before the generic ones ("closeout" must not be read
as "closed" by a substring test that fires first).
"""
import pandas as pd
import pytest
from oddd_optimize import (classify_rege, classify_status, STAT_CODE_MAP,
                           STATUS_BUCKETS, REGE_IN, REGE_OUT, REGE_DEFAULT)


def S(*vals):
    return pd.Series(list(vals), dtype="object")


def status(descs, codes=None):
    return list(classify_status(S(*descs), S(*codes) if codes else None))


# --- description-driven ---------------------------------------------------
@pytest.mark.parametrize("desc,expected", [
    ("Open", "Open"), ("Active", "Open"), ("open", "Open"),
    ("Closed", "Closed"), ("closd", "Closed"),
    ("Dormant", "Dormant"), ("Inactive", "Inactive"),
    ("Frozen", "Frozen"), ("Freeze", "Frozen"),
    ("Charged Off", "Charged Off"), ("Charge Off", "Charged Off"),
    ("charge-off", "Charged Off"), ("chargeoff", "Charged Off"),
    # core lifecycle wording (Aaron 2026-07-25)
    ("Purge at Yearend", "Closed"), ("Purge at Year End", "Closed"),
    ("Pending Closeout", "Closed"), ("Pending Close Out", "Closed"),
    ("New This Cycle", "Open"), ("Pending Activation", "Open"),
])
def test_status_from_description(desc, expected):
    assert status([desc]) == [expected]


def test_inactive_beats_active():
    """'Inactive' contains 'active'; the specific rule must run first."""
    assert status(["Inactive"]) == ["Inactive"]


def test_closeout_is_not_read_as_closed_by_accident():
    """Both land on Closed, but via the lifecycle rule, not the generic one."""
    assert status(["Pending Closeout"]) == ["Closed"]


def test_activation_is_not_read_as_active_generically():
    assert status(["Pending Activation"]) == ["Open"]


def test_unknown_description_falls_to_other():
    assert status(["Zorbulated"]) == ["Other"]


def test_blank_with_no_code_is_other():
    assert status([""]) == ["Other"]


# --- the 1549 Wellworth regression ---------------------------------------
@pytest.mark.parametrize("code,expected", sorted(STAT_CODE_MAP.items()))
def test_blank_description_resolves_from_code(code, expected):
    assert status([""], [code]) == [expected]


def test_blank_description_lowercase_code_still_resolves():
    assert status([""], ["o"]) == ["Open"]


def test_blank_description_unmapped_code_stays_other():
    """Never guessed at — the caller's unmapped pass surfaces it instead."""
    assert status([""], ["Q"]) == ["Other"]


def test_description_wins_over_code():
    """The code is a fallback for a BLANK description, not an override."""
    assert status(["Dormant"], ["C"]) == ["Dormant"]
    assert status(["Closed"], ["O"]) == ["Closed"]


def test_mixed_population_resolves_both_ways():
    out = status(["Open", "", "", "Dormant", ""], ["O", "C", "X", "O", "O"])
    assert out == ["Open", "Closed", "Charged Off", "Dormant", "Open"]


def test_every_result_is_a_declared_bucket():
    out = status(["Open", "", "Zorbulated", "Purge at Yearend", "Frozen"],
                 ["O", "X", "", ""] + [""])
    assert set(out) <= set(STATUS_BUCKETS)


# --- Reg E ----------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    # Marine wording
    ("Opt-In Accepted", REGE_IN),
    ("Opt-In Declined", REGE_OUT),
    ("No Response Recevied", REGE_DEFAULT),     # the core's own misspelling
    # Austin wording
    ("Reg E Opt In", REGE_IN),
    ("Reg E Opt Out", REGE_OUT),
    ("Reg E Default", REGE_DEFAULT),
    # spacing / casing / hyphen variants
    ("opted in", REGE_IN), ("OPTED OUT", REGE_OUT),
    ("opt  in", REGE_IN), ("optin", REGE_IN), ("optout", REGE_OUT),
    ("No Election", REGE_DEFAULT), ("no response", REGE_DEFAULT),
])
def test_rege_normalizes_both_cores(raw, expected):
    assert list(classify_rege(S(raw))) == [expected]


def test_rege_blank_stays_blank():
    """Blank = not applicable (closed/business) and is excluded, not defaulted."""
    assert list(classify_rege(S("", "   "))) == ["", ""]


def test_rege_unknown_passes_through_unchanged():
    """An unmatched non-blank is surfaced verbatim so Aaron is ASKED, not guessed at."""
    assert list(classify_rege(S("Undetermined"))) == ["Undetermined"]


def test_rege_declined_wins_over_a_string_containing_both():
    assert list(classify_rege(S("Opt-In Declined"))) == [REGE_OUT]
