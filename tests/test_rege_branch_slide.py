"""The Reg E by Branch table: one table up to 10 branches, two side by side past that.

1441 FNB Alaska has 27 branches; the single table showed 10 and rolled 17 into
"All other branches" (Aaron, 2026-11-02: show more branches).
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, os.pardir, "build"))
sys.path.insert(0, os.path.join(_HERE, os.pardir, "build", "ars_pipeline"))

import rege_branch_slide as R                                # noqa: E402


def _m(n):
    # (branch, in, out, none, accounts, pct), already sorted by rate as the metric is
    rows = [(str(i + 1), 10, 30, 0, 40, 25) for i in range(n)]
    ti = sum(r[1] for r in rows); to = sum(r[2] for r in rows)
    tn = sum(r[3] for r in rows); tt = sum(r[4] for r in rows)
    return {"rege_branch_table": rows, "rege_branch_table_total": [ti, to, tn, tt]}


def test_27_branches_are_all_listed_and_the_total_reconciles():
    left, right, shown, n = R._two_tables(_m(27))
    names = [r[0] for r in left[1:]] + [r[0] for r in right[1:-1]]
    assert shown == 27 and n == 27
    assert names == [str(i) for i in range(1, 28)]
    assert len(left) == R._LEFT_N + 1                       # header + 14
    assert right[-1][0] == "Total" and right[-1][4] == f"{27 * 40:,}"


def test_past_the_capacity_the_last_slot_rolls_up_the_rest():
    left, right, shown, n = R._two_tables(_m(31))
    assert n == 31 and shown == R._TWO_CAP - 1
    assert right[-2][0] == "All other branches (5)"
    assert right[-2][4] == f"{5 * 40:,}"


def test_both_tables_fit_the_rail():
    rows = R._LEFT_N + 1
    assert rows * R._TWO_ROW_H <= R._TBL_BOTTOM - R._TBL_TOP
    assert (R._RIGHT_N + 2) * R._TWO_ROW_H <= R._TBL_BOTTOM - R._TBL_TOP
