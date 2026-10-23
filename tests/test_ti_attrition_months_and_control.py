# Ported from ARS v5 02-Scripts/tests/test_attrition_months_and_control.py at a491b5c (James Gilmore); logic unchanged.
"""Closure duration in months (legacy A9.2) and the never-mailed control in
mailer retention (legacy A9.10), both lost in the rebuild (#245).

    python -m pytest tests/test_attrition_months_and_control.py -q
"""
import pathlib
import sys

import pandas as pd
import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.core.periods import Month  # noqa: E402
from ti.monthly_analysis import attrition  # noqa: E402
from test_ti_attrition_exposure import _Subsets, _book  # noqa: E402


def test_closure_duration_in_months_shows_where_in_the_first_year_they_leave():
    rows = ([("2026-05-01", "2026-05-20")] * 2      # under a month
            + [("2026-03-01", "2026-05-01")] * 3    # 1-3 months
            + [("2025-12-01", "2026-05-01")] * 1    # 3-6 months
            + [("2025-07-01", "2026-05-01")] * 1    # 6-12 months
            + [("2015-01-01", "2026-05-01")] * 3    # over a year
            + [("2015-01-01", None)] * 10)
    out = attrition.compute(_Subsets(_book(rows), Month(2026, 8)), {}, lambda *_: None)
    dist = {r[0]: r[1] for r in out["attrition_life_dist_months"]}
    assert dist == {"< 1 mo": 2, "1-3 mo": 3, "3-6 mo": 1, "6-12 mo": 1, "12+ mo": 3}
    assert out["attrition_life_dist_months_columns"] == ["band", "closed", "pct_of_closed"]


def test_never_mailed_is_its_own_cohort_in_mailer_retention():
    df = _book([("2015-01-01", None)] * 60 + [("2015-01-01", "2026-03-01")] * 10)
    # 40 never mailed (2 closed), 30 mailed (8 closed): 5% vs 26.7%
    df["# of Offers"] = [0] * 38 + [3] * 22 + [0] * 2 + [3] * 8
    df["# of Responses"] = [0] * 70
    out = attrition.compute(_Subsets(df, Month(2026, 8)), {}, lambda *_: None)
    assert out["attrition_nevermailed_n"] == 40
    assert out["attrition_nevermailed_rate"] == pytest.approx(5.0)
    assert out["attrition_mailed_vs_nevermailed_pp"] == pytest.approx(26.7 - 5.0, abs=0.2)
