# Ported from ARS v5 02-Scripts/tests/test_workbook_provenance.py at a491b5c (James Gilmore); logic unchanged.
"""Which reader produced this figure?

    python -m pytest tests/test_workbook_provenance.py -q

#88 changed how each wave's revenue to date was read, and the old reader was
wrong by -93% to +140% on six of 1776's eight waves. #89 then asks which
shipped decks carried the bad column -- and nothing recorded it, so the
answer depended on whoever remembered the merge date.

The reader now stamps its version onto every result, so the question is
answerable from a deck's own metrics. Bumped when the way a figure is READ
changes, not when the workbook format does.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti import workbook  # noqa: E402


def test_the_reader_declares_a_version():
    assert isinstance(workbook.READER_VERSION, int)
    assert workbook.READER_VERSION >= 2, (
        "version 1 is the reader that shipped the wrong Rev to date")


def test_the_version_is_stamped_where_the_revenue_is_read():
    import inspect

    src = inspect.getsource(workbook)
    stamp = src.index('out["wb_reader_version"]')
    revenue = src.index('out["wb_revenue_ltd"]')
    assert stamp < revenue, (
        "the stamp must be set on the same path that reads the revenue, or a "
        "result can carry figures with no provenance")


def test_the_constant_says_what_each_version_meant():
    src = pathlib.Path(workbook.__file__).read_text()
    block = src[src.index("READER_VERSION") - 700:src.index("READER_VERSION")]
    assert "#88" in block and "Annualized" in block, (
        "a bare version number tells a later reader nothing")
