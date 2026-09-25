"""Swipe tier migration and the PIN/signature mix (2026-09-21).

Both are new views on data the ODD already carried. The rows here are synthetic and built by
hand so that each account's movement is known in advance — the shipped fixture holds activity
that barely varies, which cannot prove a migration matrix either way.
"""
import os

import pytest

import combined_insights as CI
import insight_charts as IC
from odd_rows import accessors

# 16 months: the migration view compares two three-month windows twelve months apart, so an
# extract shorter than 15 months cannot answer it at all (and says so — see the test below).
MONTHS = ["May25", "Jun25", "Jul25", "Aug25", "Sep25", "Oct25", "Nov25", "Dec25", "Jan26",
          "Feb26", "Mar26", "Apr26", "May26", "Jun26", "Jul26", "Aug26"]
COLS = ["Business?", "Debit?", "Aug26 Elig"]
for _m in MONTHS:
    COLS += [f"{_m} Sig #", f"{_m} Sig $", f"{_m} PIN #", f"{_m} PIN $", f"{_m} MTD"]
H = {c: i for i, c in enumerate(COLS)}
ODD = accessors(H)
SM = MONTHS


def row(then_swipes, now_swipes, pin_share=0.5, ticket=40.0, carded=True, elig=True):
    """One account: the `then` level everywhere except the three most recent months, which
    carry the `now` level — exactly the two windows the migration view reads."""
    r = [""] * len(COLS)
    r[H["Business?"]] = "No"
    r[H["Debit?"]] = "Yes" if carded else "No"
    r[H["Aug26 Elig"]] = "Yes" if elig else "No"
    then_w, now_w = MONTHS[-15:-12], MONTHS[-3:]
    for m in MONTHS:
        n = now_swipes if m in now_w else then_swipes
        pin_n = round(n * pin_share)
        sig_n = n - pin_n
        r[H[f"{m} Sig #"]] = str(sig_n)
        r[H[f"{m} PIN #"]] = str(pin_n)
        r[H[f"{m} Sig $"]] = f"{sig_n * ticket:.2f}"
        r[H[f"{m} PIN $"]] = f"{pin_n * ticket / 2:.2f}"     # a cheaper PIN ticket
    return r


# ------------------------------------------------------------------ migration
def test_an_account_that_climbs_is_counted_as_climbing():
    rows = [row(3, 30), row(30, 3), row(8, 8)]
    mig = CI.tier_migration(rows, ODD, SM, "Aug26")
    assert (mig["moved_up"], mig["moved_down"], mig["same"]) == (1, 1, 1)
    assert mig["accounts"] == 3


def test_the_matrix_rows_are_where_accounts_started():
    mig = CI.tier_migration([row(3, 30)], ODD, SM, "Aug26")
    by = {r[0]: r[1:] for r in mig["matrix"]}
    assert by["1-5"][mig["tiers"].index("26+")] == 1
    assert sum(sum(r[1:]) for r in mig["matrix"]) == mig["accounts"]


def test_only_eligible_card_holders_are_in_the_matrix():
    rows = [row(3, 30), row(3, 30, carded=False), row(3, 30, elig=False)]
    assert CI.tier_migration(rows, ODD, SM, "Aug26")["accounts"] == 1


def test_a_short_extract_says_so_rather_than_comparing_what_it_has():
    short = MONTHS[-6:]
    mig = CI.tier_migration([row(3, 30)], ODD, short, "Aug26")
    assert mig["available"] is False
    assert mig["months"] == 6 and mig["needs"] == 15


def test_an_average_between_two_bands_lands_in_the_lower_one():
    """The defect this view would otherwise have inherited from metrics_gen: inclusive
    integer bands tested against a mean sent 5.5 swipes to the '26+' catch-all."""
    assert CI.swipe_tier(5.5) == "1-5"
    assert CI.swipe_tier(25.9) == "21-25"
    assert CI.swipe_tier(26.0) == "26+"
    assert CI.swipe_tier(0.4) == "Non-User"


def test_the_migration_chart_renders(tmp_path):
    mig = CI.tier_migration([row(3, 30), row(30, 3), row(8, 8)], ODD, SM, "Aug26")
    png = str(tmp_path / "mig.png")
    IC.migration_chart(png, mig, 8.0, 4.0)
    assert os.path.getsize(png) > 5000


# ------------------------------------------------------------------ routing
def test_the_pin_share_is_of_transaction_count_and_the_dollar_share_is_separate():
    """The two differ whenever the tickets differ, which is the point of the slide — a book
    can be half PIN by count and a third PIN by dollars."""
    mix = CI.routing_mix([row(10, 10, pin_share=0.5, ticket=40.0)], ODD, SM, months=12)
    assert mix["pin_share"] == pytest.approx(50.0, abs=0.1)
    assert mix["pin_share_usd"] == pytest.approx(33.3, abs=0.2)
    assert mix["sig_ticket"] == pytest.approx(40.0, abs=0.01)
    assert mix["pin_ticket"] == pytest.approx(20.0, abs=0.01)


def test_a_book_with_no_transactions_is_reported_not_zeroed():
    mix = CI.routing_mix([row(0, 0)], ODD, SM, months=12)
    assert mix["available"] is False


def test_the_series_is_one_row_per_month_in_the_window():
    mix = CI.routing_mix([row(10, 10)], ODD, SM, months=12)
    assert len(mix["series"]) == 12
    assert mix["window"] == [mix["series"][0]["month"], mix["series"][-1]["month"]]


def test_the_routing_chart_renders(tmp_path):
    mix = CI.routing_mix([row(10, 20)], ODD, SM, months=12)
    png = str(tmp_path / "route.png")
    IC.routing_chart(png, mix, 8.0, 4.0)
    assert os.path.getsize(png) > 5000


def test_both_slides_are_in_the_opt_in_set():
    import inspect
    import combined_insight_slides as CIS
    src = inspect.getsource(CIS.add_insight_slides)
    assert "migration_slide(prs, ci, ctx)" in src
    assert "routing_slide(prs, ci, ctx)" in src
