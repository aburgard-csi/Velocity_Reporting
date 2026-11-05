"""Sheila's 1798 FirstLight FCU slide review (2026-10-30), the Transaction Intelligence and
Competition chapters: merchant casing, one figure for Cash App, each count naming its base, the
combined slides, and chart type at slide size.

    python -m pytest tests/test_ti_review_1798_b.py -q
"""
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from matplotlib.text import Text                                       # noqa: E402

from ti.deck import charts, charts_story as CS, charts_txn as CT      # noqa: E402
from ti.deck import txn_cards as C, txn_compete as P, txn_leakage as L  # noqa: E402
from ti.deck import txn_slides                                          # noqa: E402
from test_ti_hotspot_slides import _Harness                            # noqa: E402

BASE = "transacting personal accounts"


def _h():
    h = _Harness()
    h["RIGHT_EDGE"] = 12.73
    return h


# ---------------------------------------------------------------- 11,669 against 13,983

FUNNEL = {"txn_accounts": 67_658, "fin_accounts_total": 63_944, "fin_leaking_accounts": 26_719,
          "fin_addressable_accounts": 18_454, "fin_addressable_active_accounts": 11_669}


def test_the_funnel_says_its_bands_are_unique_accounts():
    h = _h()
    L.the_book_narrowed(h, FUNNEL, BASE)
    (head, sub), title = h.slides[0]
    assert title == "The book, narrowed" and head.startswith("11,669 accounts")
    assert "unique accounts" in sub
    stages = h.charts[0]["rows"]
    assert [s[0] for s in stages] == ["Transacting accounts", "Transacting personal accounts",
                                      "Pay an outside financial product",
                                      "In a category we offer (addressable)",
                                      "Paid it in the last 90 days"]


def test_still_within_reach_names_pairs_beside_unique_accounts():
    t = dict(FUNNEL, fin_reach=[["Buy Now Pay Later", 11_295, 7_430, 65.8, 13_798_618, 12_111_661],
                                ["Credit Cards", 5_795, 2_933, 50.6, 5_632_728, 4_380_955]],
             fin_reach_dollars=16_492_616, fin_addressable_dollars=19_431_346)
    h = _h()
    L.still_within_reach(h, t, BASE)
    (_, sub), _ = h.slides[0]
    assert "an account in two counts twice" in sub
    assert h.rails[0][1] == ("Relationships", "10,363", "11,669 unique accounts, paid in 90 days")


# ---------------------------------------------------------------- Cash App: one figure

CATS = [["Insurance", 12_143, 19.0, 76_474, 14_872_771, 1_225, "leakage", False, None, 100.0],
        ["Buy Now Pay Later", 11_295, 17.7, 306_513, 13_798_618, 1_222, "leakage", True, None, 100.0],
        ["P2P Transfers", 32_170, 50.3, 1_321_317, 100_159_671, 3_113, "adjacency", False, None, 100.0]]
PROVIDERS = {"Insurance": [["STATE FARM INS", 3_445, 4_598_713]],
             "Buy Now Pay Later": [["AFFIRM", 6_804, 7_196_944], ["(unnamed)", 10, 900_000]],
             "P2P Transfers": [["CASH APP", 28_459, 78_143_006]]}
# comp_ecosystems is P2P and wallets only; BNPL is its own tier and arrives in comp_bnpl
ECO = [["Cash App", 28_478, 44.5, 78_316_482], ["Apple Cash", 14_184, 22.2, 21_942_706]]


def test_who_they_pay_ranks_financial_products_only():
    h = _h()
    L.who_they_pay(h, {"fin_top_providers": PROVIDERS, "fin_by_category": CATS,
                       "fin_leakage_dollars": 49_620_425}, BASE)
    (head, _), _ = h.slides[0]
    assert head == "Affirm alone takes $7.2M of the $49.6M paid to outside financial products"
    names = [r[0] for r in h.charts[0]["rows"]]
    assert names == ["Affirm", "State Farm Ins"] and "Cash App" not in names


def test_the_payment_app_slide_splits_p2p_from_products():
    t = {"comp_ecosystems": ECO, "comp_ecosystem_accounts": 35_204, "comp_accounts_total": 63_944,
         "comp_ecosystem_dollars": 123_660_283, "fin_leakage_dollars": 49_620_425,
         "comp_bnpl": {"providers": [["Klarna", 6_854, 10.7, 5_740_835, 69.8],
                                     ["Affirm", 6_817, 10.7, 7_203_574, 88.06]]}}
    h = _h()
    P.the_payment_ecosystems_ranked(h, t, BASE)
    (head, sub), _ = h.slides[0]
    assert "Cash App reaches 28,478 and moves $78.3M a year" in head
    assert "not a financial product" in sub and "$49.6M" in sub
    rail = dict((r[0], r[1]) for r in h.rails[0])
    assert rail["P2P and wallets"] == "$100.3M" and rail["Buy now, pay later"] == "$12.9M"
    assert [r[3] for r in h.charts[0]["rows"]] == ["p2p", "p2p", "bnpl", "bnpl"]


def test_how_members_spend_leads_with_a_shop_not_a_payment_app():
    t = {"mch_top": [["CASH APP", 28_479, 1_054_845, 78_321_155, 74.25, 7.5],
                     ["WAL MART", 48_674, 908_481, 50_164_054, 55.22, 4.8]],
         "comp_ecosystems": ECO, "mch_top15_share_pct": 30, "mch_distinct": 386_001,
         "mch_card_spend": 1.0e9, "mch_card_accounts": 63_944}
    h = _h()
    C.how_members_spend(h, t, BASE, txn_slides.merchant_bars)
    (head, sub), _ = h.slides[0]
    assert head.startswith("Walmart leads card spend at $50.2M")
    assert "Cash App at $78.3M is card-funded P2P" in sub


# ---------------------------------------------------------------- casing and grammar

def test_one_unclassified_institution_is_singular():
    t = {"fin_review_queue": [["MOUNTAIN AMERICA CU", 549, 252_973], ["SNAP FINANCE", 1_500, 328_253]],
         "fin_review_queue_dollars": 581_226}
    h = _h()
    C.dictionary_gaps(h, t, BASE)
    (head, _), _ = h.slides[0]
    assert head == "One unclassified counterparty is a named institution: Mountain America CU"
    assert h.charts[0]["kw"]["note"].startswith("1 of 2 is an institution")


def test_no_builder_title_cases_a_merchant():
    deck = HERE.parent / "build" / "ars_pipeline" / "ti" / "deck"
    for name in ("txn_cards.py", "txn_leakage.py", "txn_value.py", "txn_slides.py",
                 "txn_compete.py", "charts_story.py", "charts_txn.py"):
        code = [ln for ln in (deck / name).read_text(encoding="utf-8").splitlines()
                if not ln.lstrip().startswith(("#", '"""')) and "str.title()" not in ln]
        assert not any(".title()" in ln for ln in code), name


# ---------------------------------------------------------------- combined slides

INST = [["Synchrony", "Card Issuer", 3_147, 4.9, 19_687, 3_388_421, 1_077, ["Credit Cards", "Transfer / other"], 375, 381],
        ["Citi", "National Bank", 2_217, 3.5, 11_613, 2_126_934, 959, ["Transfer / other"], 270, 285],
        ["Credit One", "Card Issuer", 1_316, 2.1, 6_331, 998_682, 759, ["Credit Cards"], 219, 139]]


def test_one_competitor_slide_carries_reach_breadth_apps_and_the_leader():
    t = {"comp_institutions": INST, "comp_institutions_n": 79, "comp_accounts_total": 63_944,
         "comp_with_competitor": 12_636, "comp_with_competitor_pct": 19.8, "comp_multi_banked": 3_104,
         "comp_competitor_dollars": 20_900_000, "comp_ecosystem_accounts": 35_204}
    h = _h()
    P.who_competes(h, t, BASE)
    (head, _), title = h.slides[0]
    assert title == "Who competes for our members"
    assert head == ("20% of transacting personal accounts pay a named competitor — Synchrony "
                    "reaches 3,147 and takes $3.4M a year")
    assert [r[0] for r in h.rails[0]] == ["With a competitor", "Two or more", "Per year",
                                         "In a payment app", "Top competitor"]
    assert h.rails[0][4][2] == "5% of accounts, leads credit cards"
    assert h.charts[0]["name"] == "comp_quadrant"


def test_card_mix_carries_the_top_codes_on_its_rail():
    t = {"mch_by_parent": [["Everyday", 16_499_209, 590_951_055, 56.5]],
         "mch_mcc_top": [[5411, "Grocery", 55_676, 2_806_605, 139_380_560, 49.66, 13.3],
                         [4829, "Wallets & P2P", 34_448, 1_266_101, 111_886_999, 88.37, 10.7]],
         "mch_mcc_top5_share_pct": 40.0, "mch_mcc_distinct": 481, "mch_mcc_coverage_pct": 100.0,
         "mch_category_method": "mcc"}
    h = _h()
    C.card_spend_by_category(h, t, BASE)
    (head, _), _ = h.slides[0]
    assert head == "Everyday takes 56% of card dollars; MCC 5411 (grocery) alone takes 13%"
    assert [r[0] for r in h.rails[0]] == ["MCC 5411", "MCC 4829", "Top five codes"]


def test_concentration_slide_carries_the_wallet_tile():
    t = {"comp_engagement": [["Synchrony", 3_147, 3_071, 46, 30, 3.4], ["USAA", 954, 914, 18, 22, 4.5]],
         "comp_engagement_heavy_n": 140, "comp_engagement_avg_share_pct": 3.0,
         "comp_wallet_by_institution": [["Synchrony", 3_147, 2_934, 141, 72, 2.3],
                                        ["USAA", 954, 860, 52, 42, 4.4]]}
    h = _h()
    P.who_owns_the_relationship(h, t, BASE)
    assert h.rails[0][-1] == ("Over half their spend", "USAA", "4% of its 954 accounts")


def test_responder_profile_states_the_not_mailed_gap():
    t = {"fin_by_lens": [["responders", "R", 23_087, 5_550, 24.0, 1_398, 10_297, 44.6],
                         ["mailed_nonresp", "M", 13_718, 1_644, 12.0, 1_246, 3_623, 26.4]],
         "comp_by_lens": [["all", "All", 66_232, 12_897, 19.5, 24.6, 1_666, "S"],
                          ["responders", "R", 23_087, 4_081, 17.7, 21.1, 1_423, "S"],
                          ["mailed_nonresp", "M", 13_718, 1_300, 9.5, 19.5, 1_539, "S"],
                          ["not_mailed", "N", 29_427, 7_516, 25.5, 27.4, 1_820, "S"]],
         "mch_by_lens": [["responders", "R", 1, 12_000, 18.9], ["mailed_nonresp", "M", 1, 4_800, 6.5]]}
    h = _h()
    C.responder_profile(h, t, BASE)
    (_, sub), _ = h.slides[0]
    assert sub.endswith("accounts never mailed run at 26% competitor penetration against a book of 20%")


# ---------------------------------------------------------------- chart type at slide size

def _sizes(fig):
    return [t.get_fontsize() for t in fig.findobj(Text) if t.get_text().strip()]


FIGS = [
    lambda: CT._marimekko_fig([["PIN", 22, 21], ["SIG", 78, 79]], "of transactions", "of dollars"),
    lambda: CT._pareto_fig([["Affirm", "BNPL", 7.2e6], ["State Farm", "Ins", 4.6e6]], 0.8, "note"),
    lambda: CT._tornado_fig([["A", 3, 9], ["B", 5, 2]], "stopped", "new"),
    lambda: CT._band_stack_fig([["A", 80, 15, 5], ["B", 50, 30, 20]],
                               [("x", charts.TINT), ("y", charts.ORANGE), ("z", charts.RED)], "note"),
    lambda: CT._heat_matrix_fig({"rows": ["a", "b"], "cols": ["c", "d"], "cells": [[1, None], [2, 3]]},
                                "{:.0f}", "note"),
    lambda: CT._diverging_fig([["Up", 3e6, "+39%"], ["Down", -1e6, "-12%"]], "note", str),
    lambda: CT._kind_bars_fig([["Cash App", 7.8e7, 28_478, "p2p"], ["Affirm", 7.2e6, 6_817, "bnpl"]],
                              {"p2p": ("P2P", charts.NAVY), "bnpl": ("BNPL", charts.ORANGE)}, "note"),
    lambda: CS._treemap_fig([["Insurance", 14.9e6, "x", False], ["BNPL", 13.8e6, "y", True],
                             ["Loans", 6.5e6, "z", True]], "note"),
    lambda: CS._radar_fig(["a", "b", "c", "d"], [1, .8, .6, .9], [.5, .4, .7, .3], "r", "m",
                          ["1 vs 2"] * 4),
    lambda: CS._bullet_fig([["A", 20, 18, "+2"], ["B", 15, 18, "-3"]], "the book"),
    lambda: CS._worklist_fig(["a", "b", "c", ""], [["n", "d", "$1", True]] * 12),
    lambda: CS._ledger_fig([["MOUNTAIN AMERICA CU", 5, 5, True], ["SNAP", 3, 3, False]], "note"),
    lambda: (txn_slides._merchant_fig([["WAL MART", 10, 1, 50e6, 55.0]] * 12), None),
]


@pytest.mark.parametrize("make", FIGS)
def test_chart_text_is_at_least_13pt_at_figure_size(make):
    """13pt in the figure lands at 12pt or more on the slide (rail charts are placed at about 0.92x;
    Sheila's 1798 slide review, 2026-10-30, found chart labels at 9.5-10pt)."""
    import matplotlib.pyplot as plt
    fig, _ = make()
    try:
        assert min(_sizes(fig)) >= CT.TXT
    finally:
        plt.close(fig)


def test_worklist_keeps_twelve_rows_inside_the_frame():
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    fig, _ = CS._worklist_fig(["a", "b", "c", ""], [["n", "d", "$1", False]] * 12)
    try:
        ys = [p.get_y() for p in fig.axes[0].patches if isinstance(p, Rectangle)]
        assert min(ys) >= 0
    finally:
        plt.close(fig)
