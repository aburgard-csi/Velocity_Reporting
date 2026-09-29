"""Where the balances sit (2026-09-21).

Deciles are a ranking, and the "barely swiping" count is a list a branch can work — so the
tests pin that the cut is by balance, that a book with no balances says so, and that an
account with no card is never counted as a card that is not being used.
"""
import os

import pytest

import combined_insights as CI
import insight_charts as IC
from odd_rows import accessors

MONTHS = ["Jun26", "Jul26", "Aug26"]
COLS = ["Business?", "Debit?", "Avg Bal", "Aug26 Elig"]
for _m in MONTHS:
    COLS += [f"{_m} Sig #", f"{_m} Sig $", f"{_m} PIN #", f"{_m} PIN $"]
H = {c: i for i, c in enumerate(COLS)}
ODD = accessors(H)


def row(bal, swipes=10, carded=True, elig=True):
    r = [""] * len(COLS)
    r[H["Business?"]] = "No"
    r[H["Debit?"]] = "Yes" if carded else "No"
    r[H["Avg Bal"]] = str(bal)
    r[H["Aug26 Elig"]] = "Yes" if elig else "No"
    for m in MONTHS:
        r[H[f"{m} Sig #"]] = str(swipes)
    return r


def bc(rows):
    return CI.balance_concentration(rows, ODD, MONTHS, "Aug26")


def test_the_top_decile_is_the_largest_balances():
    rows = [row(100 * i) for i in range(1, 101)]
    out = bc(rows)
    assert out["top_decile_accounts"] == 10
    assert out["top_decile_floor"] == 9100            # the 10th largest balance
    assert out["deciles"][0]["avg_balance"] > out["deciles"][-1]["avg_balance"]


def test_shares_are_of_the_whole_eligible_book():
    out = bc([row(1000), row(1000), row(2000)])
    assert sum(d["balance_share"] for d in out["deciles"]) == pytest.approx(100.0, abs=0.5)


def test_an_account_with_no_card_is_not_a_card_that_is_not_swiping():
    """The count is a call list. A no-card account belongs on the take-rate slide instead."""
    # 20 accounts, so the top decile holds the two largest: one carded, one not.
    rows = [row(10_000, swipes=0, carded=False), row(9_000, swipes=0, carded=True)]
    rows += [row(100 * i, swipes=20) for i in range(1, 19)]
    out = bc(rows)
    assert out["top_decile_accounts"] == 2
    assert out["quiet"] == 2
    assert out["quiet_carded"] == 1


def test_only_eligible_personal_accounts_are_ranked():
    out = bc([row(5000), row(999_999, elig=False)])
    assert out["accounts"] == 1


def test_a_book_with_no_balances_is_stated_not_ranked():
    out = bc([row(0), row(0)])
    assert out["available"] is False
    assert "no average balances" in out["reason"]


def test_the_chart_renders(tmp_path):
    out = bc([row(100 * i, swipes=i) for i in range(1, 51)])
    png = str(tmp_path / "bal.png")
    IC.balance_chart(png, out, 8.0, 4.0)
    assert os.path.getsize(png) > 5000


def test_the_slide_is_in_the_opt_in_set():
    import inspect
    import combined_insight_slides as CIS
    assert "balance_slide(prs, ci, ctx)" in inspect.getsource(CIS.add_insight_slides)


def test_the_quiet_threshold_reads_as_one_swipe_not_one_swipes():
    # 2026-09-29: the Where the Balances Sit caption read "fewer than 1 swipes a month".
    import combined_insight_slides as CIS
    assert CIS.per_month(1, "swipe") == "1 swipe a month"
    assert CIS.per_month(1.0, "swipe") == "1 swipe a month"
    assert CIS.per_month(3, "swipe") == "3 swipes a month"
    assert CIS.per_month(0, "swipe") == "0 swipes a month"
