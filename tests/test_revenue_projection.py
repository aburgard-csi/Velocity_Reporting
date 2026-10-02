"""The projected year on MRPC Revenue by Year (Aaron, 2026-10-02: "Add a revenue projection
here based on the trajectory from the past 6 months").

The method is a straight line through the last 6 complete months, extended to December and
added to the year-to-date actual. These pin the arithmetic, the refusals (too few months, a YTD
that does not join the monthly series), the $0 floor, and the +/-2% band wording against the
prior year. Synthetic figures only.
"""
import pytest

import revenue_projection as RPJ


MONTHS = ["Dec 25", "Jan 26", "Feb 26", "Mar 26", "Apr 26", "May 26"]


def test_a_flat_trend_projects_the_same_figure_each_remaining_month():
    p = RPJ.project_year(MONTHS, [1_000] * 6, 5_000, "May", 2026, 12_000)
    assert p["ok"]
    assert [m for m, _v in p["projected_months"]] == [
        "Jun 2026", "Jul 2026", "Aug 2026", "Sep 2026", "Oct 2026", "Nov 2026", "Dec 2026"]
    assert p["slope"] == pytest.approx(0)
    assert p["remainder"] == pytest.approx(7_000)
    assert p["full_year"] == pytest.approx(12_000)
    assert "almost flat" in p["vs_prior_phrase"]


def test_a_rising_trend_extends_the_line_not_the_average():
    p = RPJ.project_year(MONTHS, [100, 200, 300, 400, 500, 600], 2_100, "May", 2026)
    assert p["slope"] == pytest.approx(100)
    assert [v for _m, v in p["projected_months"]][:2] == pytest.approx([700, 800])
    assert p["remainder"] == pytest.approx(sum(range(700, 1400, 100)))


def test_a_line_that_goes_negative_is_floored_and_says_so():
    p = RPJ.project_year(MONTHS, [600, 500, 400, 300, 200, 100], 2_100, "May", 2026)
    assert min(v for _m, v in p["projected_months"]) == 0
    assert p["floored"] and p["floored"][0] == "Jul 2026"   # Jun lands on exactly $0
    assert "Floored at $0" in RPJ.notes(p)


def test_fewer_than_six_complete_months_gives_no_projection():
    p = RPJ.project_year(MONTHS[1:], [1_000] * 5, 5_000, "May", 2026)
    assert not p["ok"] and "6 complete months" in p["reason"]
    assert RPJ.caption(p).startswith("No 2026 projection")


def test_a_ytd_that_does_not_end_with_the_monthly_series_is_refused():
    """Adding a YTD through April to months projected from June would double-count May."""
    p = RPJ.project_year(MONTHS, [1_000] * 6, 4_000, "Apr", 2026)
    assert not p["ok"] and "do not join" in p["reason"]


@pytest.mark.parametrize("full, prior, word", [
    (10_150, 10_000, "almost flat"), (11_000, 10_000, "up 10.0%"), (9_000, 10_000, "10.0% below")])
def test_the_comparison_to_last_year_follows_the_two_percent_band(full, prior, word):
    _pct, phrase = RPJ.band_phrase(full, prior, "2025")
    assert word in phrase


def test_every_string_says_it_is_a_projection():
    p = RPJ.project_year(MONTHS, [1_000] * 6, 5_000, "May", 2026, 12_000)
    assert "projected" in RPJ.caption(p)
    assert "projection, not a result" in RPJ.notes(p, as_of="2026-10-01")
    assert "projected, not actual" in RPJ.notes(p, as_of="2026-10-01")
