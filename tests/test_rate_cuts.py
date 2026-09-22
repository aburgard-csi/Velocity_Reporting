"""Where a rate lags — take rate and Reg E opt-in cut by tenure, age, balance and product.

James's deck asks "where does opt-in lag?"; ours only ever showed the book rate and a branch
chart. These tests pin the two things that make the cuts safe to read: a band the ODD cannot
place is NEVER folded into a real band, and the cut totals are the deck's own program rates.
"""
import datetime

import pytest

import combined_insights as CI
from odd_rows import accessors


@pytest.fixture(scope="module")
def cuts(odd_csv):
    d = CI.read_odd(odd_csv)
    return CI.rate_cuts(d["rows"], accessors(d["H"]), d["latest"])


def test_the_cut_totals_are_the_decks_own_program_rates(cuts, metrics):
    """If these drift apart, the slide says one thing and the Reg E slide beside it another."""
    assert cuts["take_all"] == pytest.approx(metrics["take_hist_pct"], abs=0.1)
    assert cuts["rege_all"] == pytest.approx(metrics["rege_pct"], abs=0.1)
    assert cuts["rege_pool"] == metrics["rege_pool"]


def test_every_cut_reports_the_same_population(cuts):
    for name, rows in cuts["cuts"].items():
        assert sum(b["eligible"] for b in rows) == cuts["eligible"], name
        assert sum(b["rege_pool"] for b in rows) == cuts["rege_pool"], name


def test_a_value_the_extract_does_not_carry_is_its_own_band():
    """A blank DOB read as age 0 would put the whole book in the youngest band — the failure
    mode CLAUDE.md's "stated, never zeroed" rule exists for."""
    assert CI._band(None, CI.AGE_BANDS) is None
    assert CI._band(None, CI.BALANCE_BANDS) is None
    assert CI._band(0.0, CI.BALANCE_BANDS) == "$0"          # a real zero balance is a real band


@pytest.mark.parametrize("months, want", [
    (0, "Under 1 year"), (11, "Under 1 year"), (12, "1 to 3 years"), (59, "3 to 5 years"),
    (60, "5 to 10 years"), (119, "5 to 10 years"), (120, "10 years or more"), (600, "10 years or more"),
])
def test_tenure_bands_have_no_gap_and_no_overlap(months, want):
    assert CI._band(months, CI.TENURE_BANDS) == want


def test_a_band_too_small_to_read_is_never_called_a_pocket():
    data = {"cuts": {"Age": [{"band": "18 to 24", "eligible": 4, "take": 0.0, "rege_pool": 4,
                              "rege": 0.0},
                             {"band": "65 or older", "eligible": 900, "take": 70.0,
                              "rege_pool": 900, "rege": 20.0}]},
            "take_all": 85.0, "rege_all": 40.0}
    got = CI.lagging(data, "take", floor=25)
    assert [d["band"] for d in got] == ["65 or older"]       # the 4-account band is left out


def test_not_on_file_is_a_data_gap_not_a_coaching_pocket():
    data = {"cuts": {"Age": [{"band": CI.NOT_ON_FILE, "eligible": 500, "take": 10.0,
                              "rege_pool": 500, "rege": 5.0},
                             {"band": "35 to 49", "eligible": 500, "take": 80.0,
                              "rege_pool": 500, "rege": 30.0}]},
            "take_all": 85.0, "rege_all": 40.0}
    assert [d["band"] for d in CI.lagging(data, "take")] == ["35 to 49"]


def test_pockets_are_ranked_by_how_far_below_the_book_they_sit():
    data = {"cuts": {"Age": [{"band": "a", "eligible": 100, "take": 60.0, "rege_pool": 100, "rege": 1},
                             {"band": "b", "eligible": 100, "take": 30.0, "rege_pool": 100, "rege": 1},
                             {"band": "c", "eligible": 100, "take": 95.0, "rege_pool": 100, "rege": 1}]},
            "take_all": 85.0, "rege_all": 40.0}
    got = CI.lagging(data, "take")
    assert [d["band"] for d in got] == ["b", "a", "c"][:len(got)]
    assert got[0]["gap"] == -55.0


def test_products_beyond_the_top_few_roll_up_rather_than_vanish(cuts):
    rows = cuts["cuts"]["Product"]
    assert len(rows) <= CI.TOP_PRODUCTS + 1
    rolled = [b for b in rows if b["band"].startswith("All other products")]
    assert sum(b["eligible"] for b in rows) == cuts["eligible"]
    if rolled:
        assert rolled[0]["eligible"] >= 0


def test_the_slides_are_in_the_opt_in_set():
    import inspect
    import combined_insight_slides as CIS
    src = inspect.getsource(CIS.add_insight_slides)
    assert "take_cuts_slide(prs, ci, ctx)" in src
    assert "rege_cuts_slide(prs, ci, ctx)" in src
