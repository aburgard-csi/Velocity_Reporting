# Ported from ARS v5 02-Scripts/tests/test_ic_rate_tolerance.py at a491b5c (James Gilmore); logic unchanged.
"""The ICRate check must not warn over rounding (#115).

`workbook.read` rounded the interchange rate to four decimals and the run
compared it to config at one part in a billion, so 0.01038 in config
against 0.0104 from the sheet read as "ICRate mismatch -- update it if the
fee changed". Five of twelve ARS clients carried that false instruction.

    python -m pytest tests/test_ic_rate_tolerance.py -q
"""
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from ti import workbook                                           # noqa: E402
from test_ti_workbook import _make_wb                                 # noqa: E402


@pytest.mark.parametrize("config_value, sheet_value", [
    ("0.01038", 0.0104),
    (".010593", 0.0106),
    (".00692", 0.0069),
    (".008061", 0.0081),
    ("0.008712", 0.0087),
])
def test_a_rate_that_differs_only_by_rounding_agrees(config_value, sheet_value):
    assert workbook.rates_agree(config_value, sheet_value)


def test_a_rate_that_actually_changed_does_not_agree():
    assert not workbook.rates_agree("0.0062", 0.0071)


def test_a_fee_that_moved_by_a_dollar_does_not_agree():
    assert not workbook.rates_agree("27", 28.0)


def test_the_reader_keeps_the_interchange_rate_past_four_decimals(tmp_path):
    import openpyxl
    path = _make_wb(tmp_path / "1780-Workbook_v2.xlsx")
    wb = openpyxl.load_workbook(path)
    ws = wb["Actuals MM"]
    for row in ws.iter_rows():
        if row[2].value == "Interchange Rate":
            row[3].value = 0.010593
            row[4].value = 0.010593
    wb.save(path)
    m = workbook.read(path, lambda _msg: None)
    assert m["wb_ic_rate"] == 0.010593
