"""Three headline faults found reviewing 1776 CoastHills CU's 2026.10 deck (2026-10-26).

How the leakage builds summed payment-app (adjacency) categories into "of the $X that leaves",
which counts leakage only; the ICS summary wrote a lower month-one activation as "-2 points
faster"; and a doubled processor prefix keyed Walmart as "WAL WAL", a faded merchant of its own.
"""
import pandas as pd

from ti.deck import ics_slides, txn_leakage
from ti.transaction_intelligence import merchant

from test_ti_ics_chapter import BASE, TXN, _run


def _heads(fn, *args):
    got = []
    h = {"slide": lambda pair, title: (got.append(pair[0]), (None, 1.0))[1],
         "chart": lambda *a, **k: None, "chart_left": lambda *a, **k: None, "RIGHT_EDGE": 12.0}
    fn(h, *args)
    return got


def _cat(name, dollars, kind):
    return [name, 10, 1.0, 10, dollars, 100, kind, True, None, 0.0]


def test_the_leakage_build_sums_leakage_only_and_reconciles():
    t = {"fin_leakage_dollars": 600,
         "fin_by_category": [_cat("Payment apps", 5000, "adjacency"), _cat("Credit cards", 300, "leakage"),
                             _cat("Mortgage", 200, "leakage"), _cat("Insurance", 100, "leakage")]}
    head = _heads(txn_leakage.how_the_leakage_builds, t, "accounts")[0]
    assert head.startswith("Three categories carry $600 of the $600")


def test_where_the_leakage_goes_declines_rather_than_count_payment_apps():
    t = {"fin_leakage_dollars": 300,
         "fin_by_category": [_cat("Payment apps", 5000, "adjacency"), _cat("BNPL", 900, "adjacency"),
                             _cat("Credit cards", 300, "leakage")]}
    assert "too few" in txn_leakage.where_the_leakage_goes({}, t, "accounts")


def _summary(m1):
    m = dict(BASE, ics_cmp_activation_cum=[[1, *m1], [12, 85.0, 75.0]])
    built, _ = _run(m, txn=TXN)
    return next((b["head"] for b in built if b["id"] == "ICS summary"), None)


def test_ics_summary_words_the_activation_gap_by_its_sign():
    for m1, want in [((60.0, 62.0), "2 points fewer"), ((73.0, 58.0), "15 points more"),
                     ((60.0, 60.0), "at the book's rate")]:
        head = _summary(m1)
        assert head is not None, "the ICS summary did not build"
        assert want in head and "-" not in head and "faster" not in head, head


def test_a_doubled_prefix_keys_with_the_rest_of_the_merchant():
    k = merchant.merchant_key(pd.Series(["WAL Wal-Mart Super 210845", "WAL-MART #3650"]))
    assert list(k) == ["WAL MART", "WAL MART"]
