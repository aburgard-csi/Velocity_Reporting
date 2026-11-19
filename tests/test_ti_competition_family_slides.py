# Ported from ARS v5 02-Scripts/tests/test_competition_family_slides.py at a491b5c (James Gilmore); logic unchanged.
"""The nine competition-family slides (#258, group 1): each declines with a
reason on an empty book, registers under its catalogue id on a full one,
and draws its chart for real so the row shape is proven, not stubbed.

    python -m pytest tests/test_competition_family_slides.py -q
"""
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.deck import txn_compete as P, txn_slides                  # noqa: E402
from test_ti_hotspot_slides import _Harness                            # noqa: E402

FULL = {
    "comp_accounts_total": 8, "comp_institutions_n": 4, "comp_competitor_dollars": 1_720,
    "txn_months_covered": 11,
    "comp_institutions": [
        ["Chase", "National Bank", 4, 50.0, 10, 850, 212, ["Credit Cards"], 2, 0],
        ["Capital One", "National Bank", 3, 37.5, 6, 600, 200, [], 0, 1],
        ["Cape Cod Five", "Local Bank / CU", 2, 25.0, 8, 800, 400, [], 1, 0],
        ["Discover", "Card Issuer", 1, 12.5, 1, 100, 100, [], 1, 0]],
    "comp_engagement": [["Chase", 4, 3, 0, 1, 26.2], ["Capital One", 3, 1, 1, 1, 44.2],
                        ["Cape Cod Five", 2, 1, 0, 1, 50.0]],
    "comp_engagement_heavy_n": 3, "comp_engagement_avg_share_pct": 36.1,
    "comp_wallet_by_institution": [["Chase", 4, 3, 0, 1, 25.0], ["Capital One", 3, 2, 0, 1, 33.3]],
    "comp_wallet_min_accounts": 1, "comp_wallet_high_exposure_n": 2,
    "comp_recency_bands": [["Last 30 days", 8, 80.0], ["31-90 days", 1, 10.0],
                           ["91-180 days", 0, 0.0], ["180+ days", 1, 10.0]],
    "comp_recency_pairs": 10, "comp_recency_active_pct": 80.0, "comp_recency_dormant_pairs": 1,
    "comp_breadth_bands": [["1", 4, 66.7, 50.0], ["2-3", 1, 16.7, 12.5], ["4-5", 1, 16.7, 12.5],
                           ["6+", 0, 0.0, 0.0]],
    "comp_breadth_no_competitor": 2, "comp_breadth_no_competitor_pct": 25.0,
    "comp_breadth_shopping": 2, "comp_breadth_deep": 0,
    "comp_winback": [["Capital One", 3, 2, 3, -33.3, 100.0]], "comp_winback_accounts": 3,
    "comp_winback_window": "May26 - Jul26 against Feb26 - Apr26", "comp_winback_min_accounts": 1,
    "comp_depth_growth": [["Chase", 4, 2.5, 50.0], ["Capital One", 3, 2.0, -33.3],
                          ["Cape Cod Five", 2, 4.0, 33.3]],
    "comp_ecosystems": [["Venmo", 1, 12.5, 280], ["Affirm", 1, 12.5, 100]],
    "comp_ecosystem_accounts": 1, "comp_ecosystem_dollars": 380,
    "comp_bnpl": {"accounts": 1, "pct": 12.5, "dollars": 100, "months": 11, "per_acct_month": 9.09,
                  "providers": [["Affirm", 1, 12.5, 100, 9.09]]},
}

SLIDES = [
    (P.where_the_dollars_go, "Where the dollars go", "comp_dollars"),
    (P.who_owns_the_relationship, "Who owns the relationship", "comp_engagement"),
    (P.how_much_of_the_wallet_has_left, "How much of the wallet has left", "comp_wallet_bands"),
    (P.is_the_competitor_money_still_moving, "Is the competitor money still moving", "comp_recency"),
    (P.how_many_competitors_each_account_uses, "How many competitors each account uses", "comp_breadth"),
    (P.winback_targets, "Winback targets", "comp_winback"),
    (P.depth_against_growth, "Depth against growth", "comp_depth_growth"),
    (P.the_payment_ecosystems_ranked, "The payment ecosystems, ranked", "comp_eco_ranked"),
    (P.buy_now_pay_later, "Buy now, pay later", "comp_bnpl"),
]


@pytest.mark.parametrize("build, slide_id, chart", SLIDES, ids=[s[1] for s in SLIDES])
def test_each_slide_declines_on_an_empty_book(build, slide_id, chart):
    why = build(_Harness(), {}, "personal accounts")
    assert why and why.startswith(slide_id) and "(" in why


@pytest.mark.parametrize("build, slide_id, chart", SLIDES, ids=[s[1] for s in SLIDES])
def test_each_slide_registers_its_id_and_draws_for_real(build, slide_id, chart, tmp_path):
    h = _Harness()
    h["RIGHT_EDGE"] = 12.0
    h["chart"] = lambda name, fn, *a, **k: fn(*a, tmp_path / f"{name}.png", **k)
    assert build(h, dict(FULL), "personal accounts") is None
    (head, sub), title = h.slides[-1]
    assert title == slide_id
    assert "None" not in head and "None" not in (sub or "")
    assert (tmp_path / f"{chart}.png").exists(), f"{slide_id}: chart not drawn"


def test_the_family_sits_after_where_the_outflow_goes_in_order():
    names = [getattr(b, "__name__", "") for b in txn_slides.BUILDERS]
    start = names.index("where_the_outflow_goes") + 1
    assert names[start:start + 9] == [
        "where_the_dollars_go", "who_owns_the_relationship", "how_much_of_the_wallet_has_left",
        "is_the_competitor_money_still_moving", "how_many_competitors_each_account_uses",
        "winback_targets", "depth_against_growth", "the_payment_ecosystems_ranked",
        "buy_now_pay_later"]


def test_bnpl_says_signal_only_at_ten_percent_reach():
    h = _Harness()
    t = dict(FULL, comp_bnpl=dict(FULL["comp_bnpl"], pct=4.0))
    P.buy_now_pay_later(h, t, "personal accounts")
    (_, sub), _ = h.slides[-1]
    assert "watching" in sub
    P.buy_now_pay_later(h, FULL, "personal accounts")
    (_, sub), _ = h.slides[-1]
    assert "displaced" in sub


def test_who_leads_each_product_prints_no_count_beside_a_category():
    # issue #87: comp_institutions has only whole-book reach, so a per-category count is wrong
    t = dict(FULL, comp_institutions=[
        ["Capital One", "National Bank", 14_150, 50.0, 10, 23_300_000, 212,
         ["Credit Cards", "Auto Loans", "Transfer / other"], 2, 0]])
    h = _Harness()
    P.who_leads_each_product(h, t, "base")
    (headline, sub), _title = h.slides[0]
    assert "14,150" not in headline and "14,150" not in sub
    assert h.charts[0]["fn"] == "leader_names"
