"""The month-axis guard: a calendar month never reaches an axis un-formatted.

Five ARS charts drew months in four different formats — "Feb24", "Sep '23",
"Jun" (year discarded) and "Sep 2023" — while the standard has been MMM'YY
since 2026-09-01. None of them called a formatter, so nothing could have
noticed: the label is a runtime value built by string-slicing. The guard checks
where the label is actually drawn, and these tests pin it (Aaron, 2026-09-08).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "build"))

import matplotlib                                        # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                          # noqa: E402

import periods as P                                      # noqa: E402

P.install_month_axis_guard()


@pytest.fixture
def ax():
    fig, a = plt.subplots()
    yield a
    plt.close(fig)


HOUSE = ["Feb'24", "Mar'24", "Apr'24"]

# every form the charts actually produced, and produced wrongly
BAD = ["Feb24",          # before/after panels: "Feb 2024" sliced
       "Sep '23",        # sustained
       "Jun 2026",       # ranking y-axis, and what lbl() hands over
       "Jun 25",         # the VIP series form
       "2026-07"]        # sort-key form


@pytest.mark.parametrize("bad", BAD)
def test_unformatted_month_fails_the_render(ax, bad):
    with pytest.raises(P.MonthAxisError) as e:
        ax.set_xticklabels([bad])
    assert P.mon_yy(bad) in str(e.value)


@pytest.mark.parametrize("bad", BAD)
def test_the_y_axis_is_guarded_too(ax, bad):
    """c_ranking puts its months down the side, so x-only would have missed it."""
    with pytest.raises(P.MonthAxisError):
        ax.set_yticklabels([bad])


def test_house_format_passes(ax):
    ax.set_xticks(range(len(HOUSE)))
    ax.set_xticklabels(HOUSE)
    assert [t.get_text() for t in ax.get_xticklabels()] == HOUSE


def test_axis_months_output_always_passes(ax):
    """The formatter and the guard must agree, or a correct chart cannot render."""
    ax.set_xticks(range(len(BAD)))
    ax.set_xticklabels(P.axis_months(BAD))


@pytest.mark.parametrize("cats", [
    ["NU 5+", "TH-10", "TH-25"],            # offer tiers
    ["1-5", "6-10", "26+"],                 # swipe bands
    ["18-24", "25-34", "65+"],              # age bands
    ["6mo", "1yr", "3yr"],                  # survival milestones
    ["2024", "2025", "2026 YTD"],           # MRPC revenue years
    ["New", "Open book"],
    ["Responded once", "Twice", "3+ times"],
    ["43", "1", "17"],                      # branch numbers
    ["Spread on Deposits", "NSF / OD Fees"],
])
def test_non_month_categories_pass_through(ax, cats):
    """The guard must not fire on the many axes that are not months at all."""
    ax.set_xticks(range(len(cats)))
    ax.set_xticklabels(cats)
    assert [t.get_text() for t in ax.get_xticklabels()] == cats


def test_guard_is_idempotent(ax):
    """Two chart modules imported in one process must not stack wrappers."""
    for _ in range(3):
        P.install_month_axis_guard()
    ax.set_xticks([0])
    with pytest.raises(P.MonthAxisError):
        ax.set_xticklabels(["Feb24"])
    ax.set_xticklabels(["Feb'24"])


def test_matplotlib_text_objects_are_read(ax):
    """set_xticklabels accepts Text as well as str; the guard must see both."""
    ax.set_xticks([0])
    ax.set_xticklabels(["Feb'24"])
    with pytest.raises(P.MonthAxisError):
        ax.set_xticklabels(ax.get_xticklabels() + [matplotlib.text.Text(0, 0, "Feb24")])
