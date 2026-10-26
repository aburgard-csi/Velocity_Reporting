# Ported from ARS v5 02-Scripts/tests/test_attrition_exposure.py at a491b5c (James Gilmore); logic unchanged.
"""The headline rate must account for how long each account was at risk.

    python -m pytest tests/test_attrition_exposure.py -q

The window rate counted every account equally in the denominator regardless
of exposure, so an account opened in the final month of a twelve-month window
carried one month of risk and a full unit of denominator. On a growing book
that dilutes the rate downward, and the faster the growth the larger the
understatement.

The hazard curve twenty lines below the headline already censors properly --
it drops accounts that have not had full exposure to a bucket. The correct
method was in the file; the headline did not use it.
"""
import pathlib
import sys

import pandas as pd
import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.core.periods import Month  # noqa: E402
from ti.monthly_analysis import attrition  # noqa: E402


class _Subsets:
    def __init__(self, df, anchor):
        self.total = df
        self.anchor = anchor


def _book(rows):
    """rows of (opened, closed) as 'YYYY-MM-DD' or None."""
    return pd.DataFrame({
        "Date Opened": [r[0] for r in rows],
        "Date Closed": [r[1] for r in rows],
    })


def _run(df):
    warnings = []
    out = attrition.compute(_Subsets(df, Month(2026, 8)), {}, warnings.append)
    return out, warnings


def test_a_young_account_does_not_carry_a_full_year_of_denominator():
    """100 accounts open all year with 10 closures, plus 100 opened in the
    final month with none. Counting accounts says 5.0%; counting exposure
    says the rate is nearly double, because half the book was barely at risk."""
    rows = ([("2020-01-01", None)] * 90
            + [("2020-01-01", "2026-03-15")] * 10      # closed in window
            + [("2026-08-01", None)] * 100)            # opened in the last month
    out, _ = _run(_book(rows))

    assert out["attrition_rate"] == pytest.approx(5.0, abs=0.2)
    assert out["attrition_rate_exposure"] > out["attrition_rate"] * 1.5
    assert out["attrition_exposure_years"] < 120     # not 200 account-years


def test_a_stable_book_reads_almost_the_same_either_way():
    """When every account is open for the whole window the two measures
    agree, which is what makes the gap above meaningful rather than an
    artefact of the new arithmetic."""
    rows = [("2015-01-01", None)] * 190 + [("2015-01-01", "2026-03-15")] * 10
    out, _ = _run(_book(rows))

    assert out["attrition_rate_exposure"] == pytest.approx(
        out["attrition_rate"], abs=0.3)


def test_both_figures_are_published_with_their_basis():
    rows = [("2015-01-01", None)] * 50 + [("2015-01-01", "2026-03-15")] * 5
    out, _ = _run(_book(rows))

    assert "attrition_rate" in out and "attrition_rate_exposure" in out
    assert out["attrition_base"]
    assert out["attrition_rate_exposure_basis"]
    assert out["attrition_exposure_years"] > 0


def test_exposure_is_never_negative():
    """An account closed before the window opens contributes nothing, and
    must not subtract."""
    rows = [("2015-01-01", "2019-01-01")] * 20 + [("2015-01-01", None)] * 80
    out, _ = _run(_book(rows))
    assert out["attrition_exposure_years"] > 0
