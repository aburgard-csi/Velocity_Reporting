# Ported from ARS v5 02-Scripts/tests/test_migration_monthly.py at a491b5c (James Gilmore); logic unchanged.
"""Monthly engagement migration (#245, legacy engagement/01 and 04): every
month, how many cardholders moved up or down a swipe tier, and the net.
The then/now snapshot said the book moved; this says when.

    python -m pytest tests/test_migration_monthly.py -q
"""
import pathlib
import sys

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.core.periods import Month          # noqa: E402
from ti.monthly_analysis import migration  # noqa: E402

MONTHS = 15
TAGS = [Month(2025, 6).shift(i).tag for i in range(MONTHS)]


class _Subsets:
    def __init__(self, df):
        self.eligible = df
        self.total = df


def _frame(rows):
    data = {"Debit?": ["Yes"] * len(rows), "Date Opened": ["2015-01-01"] * len(rows)}
    for i, tag in enumerate(TAGS):
        data[f"{tag} Swipes"] = [r[i] for r in rows]
    return pd.DataFrame(data)


def test_monthly_series_counts_ups_downs_and_net_each_month():
    riser = [0] * 7 + [60] * 8          # climbs through the tiers from month 8
    faller = [60] * 7 + [0] * 8         # falls from month 8
    steady = [20] * MONTHS
    out = migration.compute(_Subsets(_frame([riser, faller, steady])), {}, lambda *_: None)
    rows = out["mig_monthly"]
    assert out["mig_monthly_columns"] == ["month", "base", "up", "down", "net"]
    assert len(rows) == MONTHS - migration.WINDOW
    assert all(r[1] == 3 for r in rows)                       # three cardholders every month
    assert sum(r[2] for r in rows) >= 1 and sum(r[3] for r in rows) >= 1
    assert all(r[4] == r[2] - r[3] for r in rows)
    # nothing moves before the eighth month
    assert all(r[2] == 0 and r[3] == 0 for r in rows if r[0] in TAGS[:7])


def test_series_is_absent_when_the_snapshot_is():
    df = _frame([[20] * MONTHS])
    df = df[[c for c in df.columns if "Swipes" not in c or c.split()[0] in TAGS[:3]]]
    out = migration.compute(_Subsets(df), {}, lambda *_: None)
    assert "mig_monthly" not in out
