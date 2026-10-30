# Ported from ARS v5 02-Scripts/tests/test_finserv_cuts_slides.py at a491b5c (James Gilmore); logic unchanged.
"""The two financial-services cut slides (#258, group 2): each declines
with a reason on an empty book, registers under its catalogue id on a full
one, draws its chart for real, and sits in BUILDERS after the leakage build.

    python -m pytest tests/test_finserv_cuts_slides.py -q
"""
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.deck import txn_leakage as L, txn_slides                   # noqa: E402
from test_ti_hotspot_slides import _Harness                            # noqa: E402

FULL = {
    "fin_addressable_dollars": 8_400,
    "fin_category_pairs": [["Auto Loans", "Credit Cards", 41], ["Credit Cards", "Personal Loans", 17],
                           ["Auto Loans", "Personal Loans", 9], ["Credit Cards", "Student Loans", 6],
                           ["Auto Loans", "Mortgage/HELOC", 3]],
    "fin_category_pairs_columns": ["category_a", "category_b", "accounts"],
    "fin_reach": [["Credit Cards", 120, 90, 75.0, 5_000, 3_900],
                  ["Auto Loans", 40, 38, 95.0, 2_600, 2_500],
                  ["Personal Loans", 20, 10, 50.0, 800, 400],
                  ["Student Loans", 5, 0, 0.0, 300, 0]],
    "fin_reach_columns": ["category", "accounts", "reachable_accounts", "reachable_pct",
                          "dollars", "reachable_dollars"],
    "fin_reach_dollars": 6_800,
}
BASE = "transacting personal accounts"

SLIDES = [
    (L.which_services_travel_together, "Which services travel together", "fin_pairs"),
    (L.still_within_reach, "Still within reach", "fin_reach"),
]


@pytest.mark.parametrize("fn,title,_chart", SLIDES)
def test_declines_with_a_reason_on_an_empty_book(fn, title, _chart):
    h = _Harness()
    h["RIGHT_EDGE"] = 12.0
    why = fn(h, {}, BASE)
    assert isinstance(why, str) and why.startswith(title) and "(" in why
    assert h.slides == []


@pytest.mark.parametrize("fn,title,chart", SLIDES)
def test_registers_its_literal_id_and_names_the_number(fn, title, chart):
    h = _Harness()
    h["RIGHT_EDGE"] = 12.0
    assert fn(h, FULL, BASE) is None
    (headsub, got), = h.slides
    assert got == title
    assert "None" not in headsub[0] and "None" not in headsub[1]
    assert h.charts[0]["name"] == chart


def test_the_pair_grid_blanks_the_diagonal_and_mirrors_the_pairs():
    h = _Harness()
    h["RIGHT_EDGE"] = 12.0
    L.which_services_travel_together(h, FULL, BASE)
    grid = h.charts[0]["rows"]
    assert grid["rows"][0] == "Credit Cards"           # 41 + 17 + 6 shared, the heaviest
    i_auto = grid["rows"].index("Auto Loans")
    assert grid["cells"][0][0] is None
    assert grid["cells"][0][i_auto] == 41 and grid["cells"][i_auto][0] == 41
    assert "41 accounts hold both auto loans and credit cards" in h.slides[0][0][0]


def test_reach_ranks_live_dollars_and_drops_the_cold_category():
    h = _Harness()
    h["RIGHT_EDGE"] = 12.0
    L.still_within_reach(h, FULL, BASE)
    items = h.charts[0]["rows"]
    assert [i[0] for i in items] == ["Credit Cards", "Auto Loans", "Personal Loans"]
    assert items[0][1] == 3_900
    assert "$6.8K of the $8.4K addressable" in h.slides[0][0][0]
    labels = [r[0] for r in h.rails[0]]
    # "Relationships": the count is account-category pairs, and says so beside the unique-account
    # figure (Sheila's 1798 slide review, 2026-10-30: 13,983 against 11,669)
    assert labels == ["Within reach", "Relationships", "Gone cold", "Biggest"]
    assert h.rails[0][1][1] == "138" and h.rails[0][2][1] == "$1.6K"


def test_reach_declines_when_nothing_is_live():
    h = _Harness()
    h["RIGHT_EDGE"] = 12.0
    cold = dict(FULL, fin_reach=[["Student Loans", 5, 0, 0.0, 300, 0]], fin_reach_dollars=0)
    why = L.still_within_reach(h, cold, BASE)
    assert why == "Still within reach (no addressable relationship paid within 90 days)"


@pytest.mark.parametrize("fn,title,chart", SLIDES)
def test_draws_its_chart_for_real(tmp_path, fn, title, chart):
    h = _Harness()
    h["RIGHT_EDGE"] = 12.0
    h["chart"] = lambda name, f, *a, **k: f(*a, tmp_path / f"{name}.png", **k)
    assert fn(h, FULL, BASE) is None
    png = tmp_path / f"{chart}.png"
    assert png.exists() and png.stat().st_size > 5_000


def test_the_two_slides_follow_the_leakage_build_in_builders():
    names = [getattr(b, "__name__", "") for b in txn_slides.BUILDERS]
    start = names.index("how_the_leakage_builds") + 1
    assert names[start:start + 2] == ["which_services_travel_together", "still_within_reach"]
