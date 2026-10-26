# Ported from ARS v5 02-Scripts/tests/test_retention_axes.py at a491b5c (James Gilmore); logic unchanged.
"""Swipe velocity joins the health classes (#245, legacy attrition_txn 01/04).

Legacy called an account Declining when EITHER spend or swipe velocity fell
under 0.8 of its pace. The v5 classes read spend alone, so fewer, larger
purchases and disengagement were indistinguishable.

    python -m pytest tests/test_retention_axes.py -q
"""
import pathlib
import sys

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.monthly_analysis import retention  # noqa: E402

TAGS = ["Mar26", "Apr26", "May26", "Jun26", "Jul26", "Aug26"]


class _Subsets:
    def __init__(self, df):
        self.eligible = df
        self.total = df


def _frame(rows):
    """rows: (spend six months, swipes six months)."""
    data = {"Debit?": ["Yes"] * len(rows)}
    for i, tag in enumerate(TAGS):
        data[f"{tag} Spend"] = [r[0][i] for r in rows]
        data[f"{tag} Swipes"] = [r[1][i] for r in rows]
    return pd.DataFrame(data)


def _run(rows):
    warnings = []
    return retention.compute(_Subsets(_frame(rows)), {}, warnings.append), warnings


def test_a_swipe_collapse_with_flat_spend_is_declining_not_active():
    flat_spend = [300, 300, 300, 300, 300, 300]
    out, _ = _run([(flat_spend, [12, 12, 12, 2, 2, 2]),       # fewer, larger purchases
                   (flat_spend, [12, 12, 12, 12, 12, 12])])   # steady
    by = {r[0]: r[1] for r in out["retention_health"]}
    assert by["Declining"] == 1 and by["Active"] == 1


def test_the_axes_table_counts_the_four_quadrants():
    up, down, flat = [100] * 3 + [150] * 3, [100] * 3 + [40] * 3, [100] * 6
    out, _ = _run([(up, [10] * 3 + [14] * 3),        # both up
                   (down, [10] * 6),                  # spend down, swipes flat
                   (flat, [10] * 3 + [3] * 3),        # swipes down, spend flat
                   (down, [10] * 3 + [3] * 3)])       # both down
    axes = {r[0]: r[1] for r in out["retention_axes"]}
    assert axes["Growing on both"] == 1
    assert axes["Smaller tickets, same visits"] == 1
    assert axes["Fewer visits, same dollars"] == 1
    assert axes["Disengaging on both"] == 1
    assert out["retention_axes_columns"] == ["quadrant", "accounts", "pct_of_prior_spenders",
                                             "prior_spend_annualized"]
    assert out["retention_swipe_only_decline_n"] == 1


def test_without_swipe_columns_the_classes_are_unchanged_and_the_axes_absent():
    df = _frame([([300] * 6, [12] * 6)])
    df = df[[c for c in df.columns if "Swipes" not in c]]
    warnings = []
    out = retention.compute(_Subsets(df), {}, warnings.append)
    assert "retention_axes" not in out
    assert any("Swipes" in w for w in warnings)
