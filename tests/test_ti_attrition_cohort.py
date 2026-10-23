# Ported from ARS v5 02-Scripts/tests/test_attrition_cohort.py at a491b5c (James Gilmore); logic unchanged.
"""Cohort survival by open month (legacy A9.0b) and the first-year cohort rate.

    python -m pytest tests/test_attrition_cohort.py -q
"""
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.core.periods import Month  # noqa: E402
from ti.monthly_analysis import attrition  # noqa: E402
from test_ti_attrition_exposure import _Subsets, _book  # noqa: E402


def _run(rows):
    warnings = []
    out = attrition.compute(_Subsets(_book(rows), Month(2026, 8)), {}, warnings.append)
    return out, warnings


def test_each_open_month_reports_opened_still_open_closed_and_survival():
    rows = ([("2026-03-10", None)] * 8 + [("2026-03-20", "2026-06-01")] * 2   # Mar26: 10 opened, 2 closed
            + [("2026-05-05", None)] * 5)                                    # May26: 5 opened, 0 closed
    out, _ = _run(rows)
    by = {r[0]: r for r in out["attrition_cohort_survival"]}
    assert by["Mar26"][1:] == [10, 8, 2, 80.0]
    assert by["May26"][1:] == [5, 5, 0, 100.0]
    assert out["attrition_cohort_survival_columns"] == [
        "open_month", "opened", "still_open", "closed", "survival_pct"]


def test_months_with_no_openings_are_absent_not_zero_rows():
    # one seasoned closure so the section runs; it opened outside the
    # 24-month cohort window and adds no row
    out, _ = _run([("2026-03-10", None)] * 3 + [("2015-01-01", "2026-02-01")])
    tags = [r[0] for r in out["attrition_cohort_survival"]]
    assert tags == ["Mar26"]


def test_first_year_cohort_rate_only_counts_accounts_that_have_had_a_year():
    """Opened between Sep24 and Aug25: a full year has passed by Aug26.
    An account opened in Mar26 has not, so it is in no base."""
    rows = ([("2025-03-15", "2025-09-01")] * 3      # closed within its first year
            + [("2025-03-15", None)] * 7            # survived the year
            + [("2026-03-15", "2026-05-01")] * 4)   # too young to judge
    out, _ = _run(rows)
    assert out["attrition_cohort_first_year_base"] == 10
    assert out["attrition_cohort_first_year_rate"] == pytest.approx(30.0)


def test_seasoned_share_of_window_closures():
    rows = ([("2015-01-01", "2026-02-01")] * 6      # seasoned closures
            + [("2026-01-10", "2026-04-01")] * 4)   # cohort closures (opened in window)
    out, _ = _run(rows)
    assert out["attrition_closures_seasoned_pct"] == pytest.approx(60.0)
