# Ported from ARS v5 02-Scripts/tests/test_part2_cuts.py at a491b5c (James Gilmore); logic unchanged.
"""Two cuts the legacy scripts had and v5 lacked (#245, Part 2 item 5):
at-risk by engagement (swipe) tier, and the ICS programme against the
status code.

    python -m pytest tests/test_part2_cuts.py -q
"""
import pathlib
import sys

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.monthly_analysis import retention  # noqa: E402
from test_ti_retention_axes import _Subsets, _frame  # noqa: E402


def test_at_risk_rate_by_swipe_tier():
    falling = [300, 300, 300, 100, 100, 100]
    steady = [300] * 6
    rows = [(falling, [12] * 6)] * 30 + [(steady, [12] * 6)] * 30
    df = _frame(rows)
    df["SwipeCat3"] = ["41+ Swipes"] * 30 + ["1-5 Swipes"] * 30
    out = retention.compute(_Subsets(df), {}, lambda *_: None)
    by = {r[0]: r for r in out["retention_by_swipe_tier"]}
    assert by["41+ Swipes"][1] == 30 and by["41+ Swipes"][2] == 100.0
    assert by["1-5 Swipes"][2] == 0.0


def test_ics_stat_code_against_the_programme():
    from ti.monthly_analysis import ics
    n = 60
    df = pd.DataFrame({
        "ICS Account": ["Yes"] * 20 + ["No"] * 40,
        "Stat Code": ["O"] * 15 + ["C"] * 5 + ["O"] * 38 + ["C"] * 2,
        "Date Opened": ["2026-03-15"] * n,
    })

    class _S:
        total = df
        from ti.core.periods import Month
        anchor = Month(2026, 8)

    out = ics.compute(_S(), {}, lambda *_: None)
    by = {r[0]: r for r in out["ics_cmp_stat_code"]}
    assert by["C"][1:] == [5, 25.0, 2, 5.0]
    assert out["ics_cmp_stat_code_columns"][0] == "stat_code"
