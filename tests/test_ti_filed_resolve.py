# Ported from ARS v5 02-Scripts/tests/test_filed_resolve.py at a491b5c (James Gilmore); logic unchanged.
import pathlib
import sys
from types import SimpleNamespace

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from ti.core.filed.resolve import resolve_name, normalise  # noqa: E402


def _book(*insts):
    return SimpleNamespace(institutions={k: SimpleNamespace(key=k, name=n, trade_names=tuple(t))
                                         for k, n, t in insts})


def test_normalise_collapses_the_usual_variants():
    assert normalise("The Cape Cod Five Cents Savings Bank") == normalise("CAPE COD FIVE CENTS SAVINGS BANK")
    assert normalise("Navy FCU") == normalise("Navy Federal Credit Union")


def test_radius_scan_wins_over_the_book():
    book = _book(("fdic:1", "SEAMENS BANK", ()), ("fdic:2", "SEAMENS BANK", ()))
    record = {"radius_scan": {"institutions": [{"key": "fdic:2", "name": "Seamens Bank"}]}}
    assert resolve_name("Seamens Bank", book, record) == "fdic:2"


def test_one_book_match_resolves_and_two_is_none():
    assert resolve_name("Chase", _book(("fdic:9", "JPMORGAN CHASE BANK", ("CHASE",))), None) == "fdic:9"
    two = _book(("fdic:1", "FIRST BANK", ()), ("fdic:2", "FIRST BANK", ()))
    assert resolve_name("First Bank", two, None) is None


def test_unknown_name_is_none():
    assert resolve_name("Venmo", _book(("fdic:9", "JPMORGAN CHASE BANK", ())), None) is None


def test_a_dotted_abbreviation_normalises_to_its_plain_form():
    assert normalise("Navy F.C.U.") == normalise("Navy FCU") == normalise("Navy Federal Credit Union")
    assert normalise("St. Mary's Bank") == normalise("St Marys Bank")
