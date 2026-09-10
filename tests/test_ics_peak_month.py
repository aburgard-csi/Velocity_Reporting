"""The referral peak: one answer, and a tie stated as a tie.

Two ICS slides face each other and both name the highest referral month. Each
called `max()` independently, and `max()` takes the FIRST maximum — so the first
time a month landed level with an earlier one, "The Power of Referrals" said
"August was the highest of the last 14 months at 52" while "Referral Trend" said
"peak 52 in Jul'26" (True Sky 1676, Aug 26 = Jul 26 = 52; Aaron, 2026-09-09).

Both captions now read `peak_month`, so they cannot diverge again.
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, os.pardir, "build"))
sys.path.insert(0, os.path.join(_HERE, os.pardir, "build", "ics_pipeline"))

from build_ics_gen import peak_month                      # noqa: E402


def test_a_clear_high_is_named():
    assert peak_month([8, 18, 14, 39, 20]) == (3, [])


def test_a_tie_names_the_latest_month_and_reports_the_tie():
    """True Sky's actual series: Jul 26 and Aug 26 both 52, August last."""
    values = [8, 18, 14, 7, 7, 16, 14, 20, 28, 40, 34, 39, 52, 52]
    i, tied = peak_month(values)
    assert i == 13            # Aug 26, the LATEST month at the high
    assert tied == [12]       # Jul 26, level with it


def test_three_way_tie_lists_every_earlier_month():
    i, tied = peak_month([5, 9, 3, 9, 9])
    assert i == 4 and tied == [1, 3]


def test_an_earlier_peak_is_not_displaced_by_a_lower_last_month():
    i, tied = peak_month([10, 52, 30])
    assert i == 1 and tied == []


def test_all_equal_months():
    i, tied = peak_month([7, 7, 7])
    assert i == 2 and tied == [0, 1]


def test_a_single_month():
    assert peak_month([12]) == (0, [])


def test_no_complete_month_yet():
    """A brand-new program whose only month is still partial — the caller drops
    the partial month, so this is reached with an empty series."""
    assert peak_month([]) == (None, [])


@pytest.mark.parametrize("values", [[0, 0], [0], [3, 0, 0]])
def test_zeroes_do_not_crash_or_report_a_false_high(values):
    i, tied = peak_month(values)
    assert i is not None and values[i] == max(values)


def test_both_captions_call_it():
    """The point of the function is that neither slide computes its own peak."""
    src = open(os.path.join(_HERE, os.pardir, "build", "ics_pipeline",
                            "build_ics_gen.py"), encoding="utf-8").read()
    body = src.split("def peak_month", 1)[1].split("def _goal_months_elapsed", 1)[1]
    assert body.count("peak_month(") == 2, "both referral captions must use it"
    assert "key=lambda k: _cv[k]" not in body
    assert "key=lambda k: _ccv[k]" not in body
