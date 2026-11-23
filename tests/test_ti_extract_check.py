# Ported from ARS v5 02-Scripts/tests/test_ti_extract_check.py at a491b5c (James Gilmore); logic unchanged.
"""The extract check: does the file have the shape every section assumes?

    python -m pytest tests/test_ti_extract_check.py -q

Nothing in v5 validated the extract. A file delivered with a month missing,
with Swipes and Spend covering different windows, or with an account
appearing twice produced numbers that were wrong in ways no section could
detect -- every downstream metric simply computed over whatever arrived.

Two properties matter equally. It has to CATCH each shape, and it has to stay
quiet on a clean file: a check that cries wolf on every run is one nobody
reads, and these warnings sit in a log a CSM scans.
"""
import pathlib
import sys
from types import SimpleNamespace

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.core.periods import Month                      # noqa: E402
from ti.monthly_analysis import extract_check          # noqa: E402

ANCHOR = Month(2026, 7)
MONTHS = ["Feb26", "Mar26", "Apr26", "May26", "Jun26", "Jul26"]


def _book(swipe_months=None, spend_months=None, ids=None, n=6):
    swipe_months = MONTHS if swipe_months is None else swipe_months
    spend_months = MONTHS if spend_months is None else spend_months
    data = {"Acct ID": ids or list(range(1, n + 1))}
    for t in swipe_months:
        data[f"{t} Swipes"] = [1.0] * n
    for t in spend_months:
        data[f"{t} Spend"] = [10.0] * n
    return pd.DataFrame(data)


def _run(df):
    warnings = []
    out = extract_check.compute(SimpleNamespace(total=df, anchor=ANCHOR),
                                {}, warnings.append)
    return out, warnings


def test_a_clean_file_reports_its_shape_and_says_nothing_else():
    out, warnings = _run(_book())
    assert out["extract_rows"] == 6
    assert out["extract_swipes_months"] == 6
    assert out["extract_paired_aligned"] is True
    assert out["extract_duplicate_rows"] == 0
    assert out["extract_swipes_span"] == ["Feb26", "Jul26"]
    assert warnings == [], warnings


def test_a_gap_inside_the_range_is_found_not_inferred_from_a_count():
    """Five columns spanning six months is a gap, but a count alone cannot
    tell that from a five-month file."""
    holed = [m for m in MONTHS if m != "Apr26"]
    out, warnings = _run(_book(swipe_months=holed, spend_months=holed))

    assert out["extract_swipes_missing_months"] == ["Apr26"]
    assert out["extract_swipes_span"] == ["Feb26", "Jul26"]
    assert any("read as zero activity" in w for w in warnings), warnings


def test_a_shorter_file_is_not_mistaken_for_a_gap():
    """The other half of the above: a genuinely shorter window is fine."""
    short = ["May26", "Jun26", "Jul26"]
    out, warnings = _run(_book(swipe_months=short, spend_months=short))
    assert "extract_swipes_missing_months" not in out
    assert warnings == [], warnings


def test_misaligned_swipes_and_spend_are_named_on_both_sides():
    """Spend-per-swipe across these months divides one window by another."""
    out, warnings = _run(_book(swipe_months=MONTHS,
                               spend_months=MONTHS[:-1] + ["Aug26"]))
    assert out["extract_paired_aligned"] is False
    assert out["extract_swipes_only_months"] == ["Jul26"]
    assert out["extract_spend_only_months"] == ["Aug26"]
    assert any("do not cover the same months" in w for w in warnings), warnings


def test_a_duplicated_account_is_counted_and_called_out():
    out, warnings = _run(_book(ids=[1, 2, 3, 3, 4, 5]))
    assert out["extract_duplicate_rows"] == 2
    assert out["extract_distinct_accounts"] == 5
    assert any("more than once" in w for w in warnings), warnings


def test_an_anchor_with_no_column_is_reported():
    """Every trailing window would silently end a month early."""
    without = [m for m in MONTHS if m != "Jul26"]
    out, warnings = _run(_book(swipe_months=without, spend_months=without))
    assert out["extract_anchor_missing_from"] == ["Swipes", "Spend"]
    assert any("is not the anchor" in w for w in warnings), warnings


def test_a_file_with_no_monthly_series_declines_loudly():
    out, warnings = _run(pd.DataFrame({"Acct ID": [1, 2, 3]}))
    assert out["extract_rows"] == 3
    assert any("no monthly Swipes or Spend" in w for w in warnings), warnings


def test_a_missing_id_column_is_reported_rather_than_assumed_clean():
    df = _book()
    df = df.drop(columns=["Acct ID"])
    out, warnings = _run(df)
    assert out["extract_id_column"] is None
    assert "extract_duplicate_rows" not in out
    assert any("duplicate accounts cannot be detected" in w for w in warnings)
