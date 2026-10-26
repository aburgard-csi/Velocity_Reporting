# Ported from ARS v5 02-Scripts/tests/test_response_populations.py at a491b5c (James Gilmore); logic unchanged.
"""Four response totals, four different populations, and no slide said which.

    python -m pytest tests/test_response_populations.py -q

responses_total counts response EVENTS across the whole file -- an account
that answered two offers counts twice. reach_total counts unique ACCOUNTS
among the currently eligible. Reading one against the other is two drops at
once (events -> accounts, whole file -> eligible) and nothing separated them,
which is what made 15,000 / 12,000 / 13,000 / 12,000 irreconcilable on the
1776 deck.

Eligibility is read as of today, so an account that demonstrably responded
and has since closed or become ineligible is counted in responses_total and
in no reach, depth or age figure at all.
"""
import pathlib
import sys

import pandas as pd
import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.monthly_analysis import mailer  # noqa: E402


def test_depth_sums_to_reach_by_construction():
    """Both count eligible rows off the same '# of Responses' column, so the
    two can only disagree through a fractional response count. Nothing
    guarded this and the deck showed 13,000 against 12,000."""
    responses = pd.Series([0, 1, 1, 2, 3, 5, 0, 1])
    reach = int((responses > 0).sum())
    depth = [int((responses == 1).sum()),
             int((responses == 2).sum()),
             int((responses >= 3).sum())]
    assert sum(depth) == reach


def test_a_fractional_response_count_is_the_only_way_they_diverge():
    responses = pd.Series([0.5, 1, 2, 4])
    reach = int((responses > 0).sum())
    depth = [int((responses == 1).sum()),
             int((responses == 2).sum()),
             int((responses >= 3).sum())]
    assert sum(depth) < reach, "0 < n < 1 pushes depth down, never up"


def test_the_whole_file_rung_exists():
    """responses_total -> reach_total_whole_file is events becoming accounts;
    reach_total_whole_file -> reach_total is whole file becoming eligible.
    Without the middle rung the ladder cannot be read."""
    import inspect

    src = inspect.getsource(mailer)
    assert '"reach_total_whole_file"' in src
    assert '"reach_ineligible_responders"' in src


def test_a_responder_the_age_bands_cannot_place_is_reported():
    import inspect

    src = inspect.getsource(mailer)
    assert '"response_account_age_unplaced"' in src
    assert "land in no " in src, "the warning must say how many and why"


def test_every_reach_figure_carries_its_unit():
    import inspect

    src = inspect.getsource(mailer)
    assert '"reach_total_unit"' in src
    assert '"reach_base"' in src


# ---------------------------------------------------------------------------
# the slide has to say which population it is standing on
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="v5's deck code: ports with G9-07 (the campaign hero slide)")
def test_the_hero_caption_names_both_drops():
    """The tile prints responses_total (events, whole file) and captioned it
    with reach_total (accounts, eligible) -- two populations, two units, one
    tile, no labels. That is what made 15,000 / 12,000 irreconcilable."""
    from ti.deck.build import _responses_caption

    m = {"reach_total_whole_file": 12500, "reach_total": 12000}
    caption = _responses_caption(m, lambda k, d=None: m.get(k, d))
    assert "response events" in caption
    assert "12,500 accounts" in caption
    assert "12,000 still eligible" in caption


@pytest.mark.skip(reason="v5's deck code: ports with G9-07 (the campaign hero slide)")
def test_the_caption_degrades_when_the_middle_rung_is_absent():
    """Older metrics files have no reach_total_whole_file; the caption must
    still say what the number is rather than crash or mislead."""
    from ti.deck.build import _responses_caption

    m = {"reach_total": 12000}
    caption = _responses_caption(m, lambda k, d=None: m.get(k, d))
    assert "response events" in caption
    assert "unique eligible accounts" in caption


@pytest.mark.skip(reason="v5's deck code: ports with G9-06 (Program reach, Campaign chapter)")
def test_the_responded_tile_names_its_base():
    """'counted once each' says the unit but not the population."""
    import inspect

    from ti.deck import build

    src = inspect.getsource(build)
    assert '"counted once each"' not in src
    assert 'f"unique accounts, {str(m.get(\'reach_base\') or \'eligible\').lower()}"' in src
