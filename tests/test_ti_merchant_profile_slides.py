# Ported from ARS v5 02-Scripts/tests/test_merchant_profile_slides.py at a491b5c (James Gilmore); logic unchanged.
"""The six merchant / MCC / holder slides (#258, group 3): each declines
with a reason on an empty book, registers under its catalogue id on a
full one, and draws its chart for real so the row shape is proven.

    python -m pytest tests/test_merchant_profile_slides.py -q
"""
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.deck import txn_cards as C, txn_slides                    # noqa: E402
from test_ti_hotspot_slides import _Harness                            # noqa: E402

FULL = {
    "mch_category_method": "mcc", "mch_mcc_coverage_pct": 98.4,
    "mch_growth": [["AMAZON", 812, 61_200, 98_400, 37_200, 60.8],
                   ["COSTCO", 240, 40_100, 52_300, 12_200, 30.4],
                   ["SHELL", 610, 71_000, 48_900, -22_100, -31.1],
                   ["TARGET", 190, 22_000, 14_500, -7_500, -34.1]],
    "mch_growth_window": "May26-Jul26 against Feb26-Apr26",
    "mch_growth_ranked_n": 140, "mch_growth_rising_n": 31, "mch_growth_falling_n": 22,
    "mch_growth_book_pct": 4.2,
    "mch_new": [["TEMU", 18_400, 210], ["DUTCH BROS", 6_100, 88]],
    "mch_faded": [["BED BATH", 9_900, 140]],
    "mch_new_faded_note": "material merchants (>= 0.05% of card $) first/last seen inside the trailing 3 months",
    "mch_mcc_top": [[5411, "Grocery", 2_100, 24_000, 610_000, 25.42, 22.1],
                    [5541, "Fuel", 1_800, 19_000, 420_000, 22.11, 15.2],
                    [5812, "Dining", 1_900, 31_000, 380_000, 12.26, 13.8],
                    [5999, "Retail", 1_200, 9_000, 210_000, 23.33, 7.6],
                    [4900, "Utilities", 700, 3_000, 190_000, 63.33, 6.9]],
    "mch_mcc_distinct": 412, "mch_mcc_top5_share_pct": 65.6,
    "mch_breadth_bands": [["none named", 120, 4.0, 210], ["1", 600, 20.0, 480],
                          ["2-3", 1_200, 40.0, 1_450], ["4-5", 800, 26.7, 3_900],
                          ["6+", 280, 9.3, 7_800]],
    "mch_breadth_mean": 3.1, "mch_breadth_deep_pct": 36.0,
    "mch_by_age": [["18-25", 300, 2_100, 9.4, 21.5, "Dining"], ["26-35", 700, 4_300, 14.2, 28.1, "Grocery"],
                   ["36-45", 800, 5_100, 15.0, 33.0, "Grocery"], ["46-55", 600, 4_800, 12.1, 38.4, "Grocery"],
                   ["56-64", 400, 3_600, 9.0, 41.2, "Grocery"], ["65+", 200, 2_400, 6.1, 39.9, "Grocery"]],
    "mch_by_age_columns": ["band", "accounts", "spend_per_acct", "txns_per_acct_mo", "avg_ticket", "top_category"],
    "mch_by_tenure": [["< 3 mo", 90, 900, 6.2, 19.0, "Dining"], ["3-12 mo", 310, 2_800, 11.4, 24.6, "Grocery"],
                      ["1-3 yrs", 700, 4_200, 13.9, 30.2, "Grocery"], ["3-10 yrs", 1_100, 4_900, 13.1, 34.8, "Grocery"],
                      ["10+ yrs", 800, 3_700, 8.8, 42.0, "Grocery"]],
    "mch_first_swipe_bands": [["within 7 days", 60, 30.0], ["8-30 days", 70, 35.0],
                              ["31-90 days", 30, 15.0], ["90+ days", 10, 5.0], ["no swipe yet", 30, 15.0]],
    "mch_first_swipe_new_accounts": 200, "mch_first_swipe_median_days": 12,
    "mch_first_swipe_within_30_pct": 65.0, "mch_first_swipe_window": "opened Aug25 - Jun26, 30 days' grace",
}

MCC = txn_slides._the_mcc_codes
SLIDES = [
    (C.merchants_rising_and_falling, "Merchants rising and falling", "mch_growth"),
    (C.new_and_faded_merchants, "New and faded merchants", "mch_new_faded"),
    (MCC, "The MCC codes behind the categories", "mch_mcc"),
    (C.how_broadly_the_card_is_used, "How broadly the card is used", "mch_breadth"),
    (C.card_spend_by_member_age, "Card spend by member age", "mch_by_age"),
    (C.card_use_by_account_tenure, "Card use by account tenure", "mch_by_tenure"),
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


def test_the_group_sits_after_engagement_breadth_in_order():
    names = [getattr(b, "__name__", "") for b in txn_slides.BUILDERS]
    start = names.index("engagement_breadth") + 1
    assert names[start:start + 6] == [
        "merchants_rising_and_falling", "new_and_faded_merchants", "_the_mcc_codes",
        "how_broadly_the_card_is_used", "card_spend_by_member_age",
        "card_use_by_account_tenure"]


def test_mcc_slide_declines_by_coverage_when_the_feed_carries_no_mcc():
    why = MCC(_Harness(), {"mch_mcc_coverage_pct": 0.0, "mch_top": [["X", 1, 1, 1, 1, 1]]},
              "personal accounts")
    assert why == ("The MCC codes behind the categories (MCC on 0% of card rows; "
                   "the feed does not carry it)")


def test_rising_and_falling_names_the_biggest_mover_each_way():
    h = _Harness()
    C.merchants_rising_and_falling(h, FULL, "personal accounts")
    (head, sub), _ = h.slides[-1]
    assert head == "Amazon is up $37K window over window; Shell is down $22K"
    assert "May26-Jul26 against Feb26-Apr26" in sub
    # a diverging bar of the change since Sheila's 1798 slide review (2026-10-30): risers first,
    # biggest gain at the top, fallers after with the biggest fall at the bottom
    rows = h.charts[-1]["rows"]
    assert rows[0] == ["Amazon", 37_200, "+61%"]
    assert [r[0] for r in rows] == ["Amazon", "Costco", "Target", "Shell"]


def test_rising_and_falling_combines_a_merchant_whose_descriptor_changed():
    """1798: "CIRCLE K" became "CIRCLEK" inside the window, and the slide read "Circlek is up
    $4.6M" beside a Circle K down $4.7M (Sheila's slide review, 2026-10-30)."""
    h = _Harness()
    t = dict(FULL, mch_growth=[["CIRCLEK", 26_449, 155_402, 4_749_540, 4_594_138, 2956.3],
                               ["WM SUPERCENTER", 33_539, 7_930_127, 11_047_585, 3_117_457, 39.3],
                               ["LOWE'S", 13_480, 2_197_831, 1_941_739, -256_092, -11.7],
                               ["CIRCLE K", 5_550, 4_962_961, 268_572, -4_694_389, -94.6]])
    C.merchants_rising_and_falling(h, t, "personal accounts")
    (head, _), _ = h.slides[-1]
    assert head.startswith("WM Supercenter is up $3.1M") and "Circlek" not in head
    rows = h.charts[-1]["rows"]
    assert [r[0] for r in rows] == ["WM Supercenter", "Circle K", "Lowe's"]
    assert rows[1][1] == 4_749_540 + 268_572 - 155_402 - 4_962_961
    assert "Circle K" in h.charts[-1]["kw"]["note"]


def test_new_and_faded_marks_the_new_rows_only():
    h = _Harness()
    C.new_and_faded_merchants(h, FULL, "personal accounts")
    rows = h.charts[-1]["rows"]
    assert [r[4] for r in rows] == [True, True, False]
    assert rows[2][2] == "faded · 140 accounts"


def test_merchant_bars_keep_their_dollar_signs_out_of_mathtext():
    """'$610K   2,100 accounts   $25 avg' has two dollar signs, which
    matplotlib reads as a math span: the note drew italic with its spaces
    gone, on the MCC slide and on 'How members spend' before it."""
    fig = txn_slides._merchant_fig([["5411 Grocery", 2_100, 24_000, 610_000, 25.42, 22.1]])
    notes = [t.get_text() for t in fig.axes[0].texts]
    assert notes == [r"\$610K   2,100 accounts   \$25 avg"]


def test_tenure_slide_carries_time_to_first_swipe_on_the_rail():
    h = _Harness()
    C.card_use_by_account_tenure(h, FULL, "personal accounts")
    (head, sub), _ = h.slides[-1]
    # 102 words on 1798 (Sheila's slide review, 2026-10-30: too dense): the first swipe left the
    # headline for the rail, and the rail is four tiles
    assert head == "Accounts 3-10 yrs spend the most on the card, $4.9K per account"
    assert sub == "card dollars per account, personal accounts"
    assert len(h.rails[-1]) == 4
    assert h.rails[-1][2] == ("First swipe", "12 days", "median, 200 new accounts")
    assert h.rails[-1][3] == ("Within 30 days", "65%", "of new accounts swipe")
    h = _Harness()
    C.card_use_by_account_tenure(h, {"mch_by_tenure": FULL["mch_by_tenure"]}, "personal accounts")
    assert len(h.rails[-1]) == 3
