# Ported from ARS v5 02-Scripts/tests/test_filed_growth.py at a491b5c (James Gilmore); logic unchanged.
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from ti.core.filed.store import Quarter  # noqa: E402
from ti.core.filed.growth import filed_growth  # noqa: E402


def _q(date, dep):
    return Quarter(date=date, assets=None, deposits=dep, loans=None, net_worth=None, roa=None)


def test_a_clean_year_gives_the_growth_and_four_quarters_apart():
    g = filed_growth([_q("2025-03-31", 700), _q("2025-06-30", 720), _q("2025-09-30", 740),
                      _q("2025-12-31", 760), _q("2026-03-31", 800)])
    assert g.deposits_latest == 800 and g.deposits_prior == 700
    assert g.growth_pct == 14.3
    assert g.quarters_apart == 4 and g.prior_date == "2025-03-31"


def test_a_ragged_store_still_pairs_the_nearest_year():
    g = filed_growth([_q("2025-06-30", 700), _q("2026-03-31", 770)])
    assert g.quarters_apart == 3 and g.growth_pct == 10.0


def test_too_short_a_series_is_none():
    assert filed_growth([_q("2026-03-31", 800)]) is None
    assert filed_growth([_q("2025-12-31", 700), _q("2026-03-31", 800)]) is None


def test_null_deposits_are_skipped_not_zero():
    g = filed_growth([_q("2025-03-31", 700), _q("2026-03-31", None), _q("2025-12-31", 760)])
    assert g is not None
    assert (g.latest_date, g.prior_date) == ("2025-12-31", "2025-03-31")
    assert g.growth_pct == 8.6
    assert g.quarters_apart == 3


def test_an_exact_half_rounds_up_not_to_even():
    g = filed_growth([_q("2025-03-31", 400), _q("2026-03-31", 457)])
    assert g.growth_pct == 14.3
    g = filed_growth([_q("2025-03-31", 400), _q("2026-03-31", 343)])
    assert g.growth_pct == -14.3
