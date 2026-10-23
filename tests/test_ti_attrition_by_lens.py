# Ported from ARS v5 02-Scripts/tests/test_attrition_by_lens.py at a491b5c (James Gilmore); logic unchanged.
"""Attrition, cut by the same account lenses the transaction chapter uses.

    python -m pytest tests/test_attrition_by_lens.py -q

Two things this pins.

One definition. monthly_analysis runs before transaction_intelligence and
writes the frame it reads, so each half used to carry its own copy of "is
this an ICS account" -- and they drifted, leaving the transaction chapter
reporting an ICS cut over zero accounts. Both now read
core/account_lenses, and this asserts they agree.

One honest rate. A programme that opened most of its accounts recently is
exposed for less of the window, so a raw closure share flatters it for being
young. ICS on 1776 averages under eight months of maturity against a book
measured over twelve. The cut therefore reports closures per account-year at
risk, the same basis the headline was fixed to use.
"""
import pathlib
import sys

import pandas as pd
import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.core import account_lenses  # noqa: E402
from ti.core.periods import Month  # noqa: E402
from ti.monthly_analysis import attrition  # noqa: E402

ANCHOR = Month(2026, 8)


class _Subsets:
    def __init__(self, df, anchor):
        self.total = df
        self.anchor = anchor


def _book(rows):
    """rows of (opened, closed, ics) -- dates as 'YYYY-MM-DD' or None."""
    return pd.DataFrame({
        "Date Opened": [r[0] for r in rows],
        "Date Closed": [r[1] for r in rows],
        "ICS Account": [r[2] for r in rows],
    })


def _run(df):
    warnings = []
    out = attrition.compute(_Subsets(df, ANCHOR), {}, warnings.append)
    return out, warnings


def _lens(out, name):
    return next((r for r in out.get("attrition_by_lens", [])
                 if r[0] == name), None)


def test_the_ics_lens_is_reported_and_counts_the_stamped_accounts():
    rows = ([("2015-01-01", None, "Yes")] * 140
            + [("2015-01-01", "2026-03-15", "Yes")] * 10
            + [("2015-01-01", None, "No")] * 190
            + [("2015-01-01", "2026-03-15", "No")] * 10)
    out, _ = _run(_book(rows))

    ics = _lens(out, "ics")
    assert ics is not None, "no ICS row in the attrition lens cut"
    assert ics[2] == 150, ics          # at risk
    assert ics[3] == 10, ics           # closed


def test_a_young_lens_is_not_flattered_by_a_raw_share():
    """The whole reason the cut reports per account-year.

    ICS here opened one month before the window closed and lost 5 of 100.
    Counting accounts calls that 5%; counting exposure says the rate is far
    higher, because those accounts were barely at risk.
    """
    rows = ([("2026-08-01", None, "Yes")] * 95
            + [("2026-08-01", "2026-08-20", "Yes")] * 5
            + [("2015-01-01", None, "No")] * 285
            + [("2015-01-01", "2026-03-15", "No")] * 15)
    out, _ = _run(_book(rows))

    ics = _lens(out, "ics")
    assert ics is not None
    raw, per_year = ics[4], ics[6]
    assert raw == pytest.approx(5.0, abs=0.3)
    assert per_year > raw * 3, (
        f"a lens exposed for one month reads {per_year}% per account-year "
        f"against a {raw}% raw share -- the exposure correction did not fire")


def test_a_stable_lens_reads_the_same_either_way():
    """Which is what makes the gap above meaningful rather than arithmetic."""
    rows = ([("2015-01-01", None, "Yes")] * 190
            + [("2015-01-01", "2026-03-15", "Yes")] * 10
            + [("2015-01-01", None, "No")] * 200)
    out, _ = _run(_book(rows))

    ics = _lens(out, "ics")
    assert ics[6] == pytest.approx(ics[4], abs=0.4)


def test_the_cut_publishes_its_columns_and_its_basis():
    rows = ([("2015-01-01", None, "Yes")] * 195
            + [("2015-01-01", "2026-03-15", "Yes")] * 5
            + [("2015-01-01", None, "No")] * 200)
    out, _ = _run(_book(rows))

    assert out["attrition_by_lens_columns"][0] == "lens"
    assert "account-year" in out["attrition_by_lens_basis"]
    assert "rate_per_account_year" in out["attrition_by_lens_columns"]


def test_a_thin_lens_is_not_reported():
    """Below the floor a lens row swings too hard to mean anything, and the
    run says the cut was dropped rather than printing a rate off a handful."""
    rows = ([("2015-01-01", None, "Yes")] * 19
            + [("2015-01-01", "2026-03-15", "Yes")] * 1
            + [("2015-01-01", None, "No")] * 20)
    out, warnings = _run(_book(rows))

    assert "attrition_by_lens" not in out
    assert any("by lens" in w for w in warnings), warnings


def test_attrition_and_the_transaction_layer_agree_on_who_is_ics():
    """The drift that left the transaction chapter with no ICS cut at all.

    A client stamped through DM-REF Source rather than ICS Account must be
    seen by BOTH halves -- attrition reads core/account_lenses, and so does
    transaction_intelligence/lens.
    """
    df = pd.DataFrame({
        "Date Opened": ["2015-01-01"] * 400,
        "Date Closed": ([None] * 145 + ["2026-03-15"] * 5) + ([None] * 250),
        "DM-REF Source": (["REF"] * 150) + ([""] * 250),
    })
    out, _ = _run(df)

    ics = _lens(out, "ics")
    assert ics is not None, "a DM-REF-stamped client has no ICS attrition row"
    assert ics[2] == 150

    shared = account_lenses.masks_for(df, pd.Timestamp("2026-08-31"))
    assert int(shared["ics"].sum()) == 150
    assert int(shared["ics_ref"].sum()) == 150
