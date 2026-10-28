"""The ILS kickoff workbook writer (build/ils_pipeline/kickoff/deck/report.py).

v5's workbook format tests (v5 tests/test_ils_kickoff.py at 7ba1e63, the two held back from the
loader stage), with the import rewritten.
"""
import pytest


@pytest.fixture(autouse=True)
def _v5_pandas():
    """v5's code under the pandas 2 string semantics it was written for (kickoff/_v5/compat.py)."""
    from ils_pipeline.kickoff._v5.compat import legacy_strings
    with legacy_strings():
        yield


def test_a_ratio_column_displays_as_a_percentage():
    """"Pay Ratio" printed 1.00 where the reader wanted 100%, while the
    "% of Items" column beside it was correct -- which made the
    inconsistency look deliberate (James, 2026-09-09)."""
    from openpyxl import Workbook

    from ils_pipeline.kickoff.deck.report import _apply_number_format
    cell = Workbook().active["A1"]
    _apply_number_format(cell, 1.0, "Pay Ratio")
    assert cell.number_format == "0.0%"
    assert cell.value == 1.0


def test_a_percent_column_is_left_alone():
    from openpyxl import Workbook

    from ils_pipeline.kickoff.deck.report import _apply_number_format
    cell = Workbook().active["A1"]
    _apply_number_format(cell, 4.02, "% of Accounts")
    assert cell.number_format == "0.0%"
