"""Product Mix and Excluded Accounts count ONE population, and its pieces sum.

The two slides sit next to each other and used to count different books: Product
Mix every account excluding closed, Excluded Accounts the strictly-OPEN subset. On
1549 that put 71,466 on slide 5 and 66,462 on slide 6, with two eligible counts two
apart — numbers a reader cannot add up (Aaron, 2026-10-02).

Nothing could have caught it. No test covered either extractor, and the synthetic
ODD could not have shown it anyway: its `Elig` flag is only ever "Yes" on a status
code of O or A, so it has no eligible dormant account and the two readings agree on
it by construction. Real cores disagree — 2 such accounts on 1549, 147 on 1204, 324
on 1509 — so the ODD written here carries one.
"""
import csv
import os

import pytest

import excluded_accounts_slide as excl
import product_mix_slide as mix

HDR = ["Acct ID", "Prod Code", "Prod Desc", "Business?", "Stat Code", "Stat Desc",
       "Debit?", "Avg Bal", "Mailable?", "Aug26 Elig"]


def row(acct, prod, desc, stat_desc, elig, debit="Yes", stat_code="O", biz="No"):
    return [acct, prod, desc, biz, stat_code, stat_desc, debit, "100", "Yes", elig]


@pytest.fixture(scope="module")
def odd(tmp_path_factory):
    """A book with one of each case the two slides have to agree about."""
    rows = [
        # open, eligible product, carded -> eligible
        *[row(f"a{i}", "10", "Simply Free Checking", "Open", "Yes") for i in range(20)],
        # open, eligible product, no debit card -> excluded, "no debit card"
        *[row(f"b{i}", "10", "Simply Free Checking", "Open", "No", debit="No") for i in range(5)],
        # open, a product no eligible account carries -> excluded, "product not in ARS"
        *[row(f"c{i}", "24", "Gunny Savings", "Open", "No") for i in range(7)],
        # DORMANT and NOT eligible -> excluded, "account not open"
        *[row(f"d{i}", "10", "Simply Free Checking", "Dormant", "No", stat_code="D") for i in range(4)],
        # DORMANT and eligible even so — the case that broke the two slides apart
        *[row(f"e{i}", "10", "Simply Free Checking", "Dormant", "Yes", stat_code="D") for i in range(3)],
        # closed, and charged off: outside the population on BOTH slides
        *[row(f"f{i}", "10", "Simply Free Checking", "Closed", "No", stat_code="C") for i in range(9)],
        # closed and STILL flagged eligible by the core: counted by neither slide.
        # Reading the eligible tile off the whole extract instead of the live book
        # put this account on the slide, one above Product Mix's count.
        row("f9", "10", "Simply Free Checking", "Closed", "Yes", stat_code="C"),
        *[row(f"g{i}", "10", "Simply Free Checking", "Charge-Off", "No", stat_code="X") for i in range(2)],
    ]
    p = tmp_path_factory.mktemp("pop") / "9999_ODDD.csv"
    with open(p, "w", newline="", encoding="latin-1") as fh:
        w = csv.writer(fh)
        w.writerow(HDR)
        w.writerows(rows)
    return str(p)


@pytest.fixture(scope="module")
def pair(odd):
    return mix.extract_product_mix(odd), excl.extract_exclusions(odd)


def test_both_slides_count_the_same_book(pair):
    m, x = pair
    # 20 + 5 + 7 + 4 + 3 = 39 accounts excluding closed; the 12 closed and
    # charged-off rows are outside both slides.
    assert m["open_total"] == x["open_total"] == 39
    assert x["closed"] == 12


def test_both_slides_count_the_same_eligible_accounts(pair):
    m, x = pair
    # 20 open + 3 dormant-but-eligible. Reading eligibility off the status instead
    # of the flag would make this 20 here and 23 on Product Mix.
    assert m["elig_total"] == x["elig_total"] == 23
    assert x["elig_other"] == 3       # named in the notes, counted in the tile


def test_outside_ars_and_eligible_sum_to_the_book(pair):
    _, x = pair
    assert x["excluded_total"] + x["elig_total"] == x["open_total"]


def test_every_excluded_account_lands_in_exactly_one_reason(pair):
    _, x = pair
    reasons = (x["n_status_excluded"], x["n_prod_excluded"],
               x["n_no_debit"], x["n_unexplained"])
    assert reasons == (4, 7, 5, 0)
    assert sum(reasons) == x["excluded_total"] == 16


def test_status_is_the_first_reason_that_applies(pair):
    """A dormant account on an excluded product is counted as not open, once.

    With product first it would land in "product not in ARS" instead, and the
    product bar would move for a reason that has nothing to do with the product.
    """
    _, x = pair
    assert x["n_prod_excluded"] == 7          # the 7 open Gunny Savings rows only
    assert x["open_only"] == 32               # 39 excl. closed, less the 7 dormant
