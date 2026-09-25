"""Overdraft limits against the Reg E election (2026-09-21).

The deck reports the election and, separately, NSF/OD volume; this puts them on one slide.
Two things have to hold: the population is the Reg E slides' own population, so the groups
reconcile with them, and a Reg E value the classifier cannot map is left OUT and reported
rather than quietly dropped into a group.
"""
import os

import pytest

import combined_insights as CI
import insight_charts as IC
from odd_rows import accessors, REGE_IN, REGE_OUT, REGE_DEFAULT

MONTHS = ["Jun26", "Jul26", "Aug26"]
COLS = ["Business?", "Debit?", "Stat Desc", "Aug26 Reg E Desc"]
for _m in MONTHS:
    COLS += [f"{_m} Sig #", f"{_m} Sig $", f"{_m} PIN #", f"{_m} PIN $", f"{_m} MTD",
             f"{_m} OD Limit"]
H = {c: i for i, c in enumerate(COLS)}
ODD = accessors(H)


def row(rege="Reg E Opt In", limit=500, items=(0, 0, 0), carded=True, open_=True):
    r = [""] * len(COLS)
    r[H["Business?"]] = "No"
    r[H["Debit?"]] = "Yes" if carded else "No"
    r[H["Stat Desc"]] = "Open" if open_ else "Closed"
    r[H["Aug26 Reg E Desc"]] = rege
    for m, n in zip(MONTHS, items):
        r[H[f"{m} MTD"]] = str(n)
        r[H[f"{m} OD Limit"]] = str(limit)
    return r


def groups(od):
    return {g["election"]: g for g in od["groups"]}


def test_items_are_a_monthly_average_over_the_window():
    od = CI.overdraft_limits([row(items=(3, 0, 0))], ODD, MONTHS, "Aug26")
    assert groups(od)[REGE_IN]["items_per_account"] == pytest.approx(1.0)


def test_limit_coverage_counts_a_limit_above_zero_only():
    rows = [row(limit=0), row(limit=250), row(limit=1000)]
    g = groups(CI.overdraft_limits(rows, ODD, MONTHS, "Aug26"))[REGE_IN]
    assert (g["with_limit"], g["accounts"]) == (2, 3)
    assert g["with_limit_pct"] == pytest.approx(66.7, abs=0.1)
    assert g["avg_limit"] == 625            # the average of those that HAVE one, not of all


def test_the_population_is_open_personal_card_holders():
    rows = [row(), row(carded=False), row(open_=False)]
    assert CI.overdraft_limits(rows, ODD, MONTHS, "Aug26")["accounts"] == 1


def test_each_election_is_counted_under_its_standardized_label():
    rows = [row(rege="Opt-In Accepted"), row(rege="Opt-In Declined"), row(rege="D")]
    g = groups(CI.overdraft_limits(rows, ODD, MONTHS, "Aug26"))
    assert (g[REGE_IN]["accounts"], g[REGE_OUT]["accounts"], g[REGE_DEFAULT]["accounts"]) == (1, 1, 1)


def test_an_unmappable_election_is_reported_not_folded_into_a_group():
    """CLAUDE.md: an unmapped value is surfaced and Aaron decides — never guessed into the
    nearest bucket, where it would move a rate nobody could explain."""
    rows = [row(rege="Opt-In Accepted"), row(rege="Tracking Type 56 Does Not Exist")]
    od = CI.overdraft_limits(rows, ODD, MONTHS, "Aug26")
    assert od["accounts"] == 1
    assert od["unmapped"] == {"Tracking Type 56 Does Not Exist": 1}


def test_a_book_with_no_limits_at_all_says_so_rather_than_reading_as_zero():
    od = CI.overdraft_limits([row(limit=0)], ODD, MONTHS, "Aug26")
    assert od["carries_limits"] is False
    assert groups(od)[REGE_IN]["avg_limit"] is None


def test_the_chart_renders(tmp_path):
    od = CI.overdraft_limits([row(), row(rege="Reg E Opt Out", items=(1, 1, 1))],
                             ODD, MONTHS, "Aug26")
    png = str(tmp_path / "od.png")
    IC.overdraft_chart(png, od, 8.0, 4.0)
    assert os.path.getsize(png) > 5000


def test_the_monthly_columns_it_needs_are_in_read_odds_projection():
    """odd.nsf() and odd.od_limit() read MTD and OD Limit. They were not in read_odd's
    column projection, so every figure on this slide came back 0.0 — a slide of zeros that
    read as a client with no overdrafts rather than a reader with no columns."""
    assert CI._MON_COL.match("Aug26 MTD")
    assert CI._MON_COL.match("Aug26 OD Limit")


def test_the_slide_is_in_the_opt_in_set():
    import inspect
    import combined_insight_slides as CIS
    assert "overdraft_slide(prs, ci, ctx)" in inspect.getsource(CIS.add_insight_slides)
