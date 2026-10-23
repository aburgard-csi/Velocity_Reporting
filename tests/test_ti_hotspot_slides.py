# Ported from ARS v5 02-Scripts/tests/test_hotspot_slides.py at a491b5c (James Gilmore); logic unchanged.
"""The two branch slides: where we leak, and where losing meets leaking.

    python -m pytest tests/test_hotspot_slides.py -q

The smoke fixture carries no competitor rows and no closures, so neither
slide renders there -- and neither does any of the competition chapter
around them. That makes a full-deck build a poor test of these: it cannot
distinguish "correctly skipped" from "silently broken".

So they are exercised directly against the shapes hotspots.py and
competition.py actually emit, with a stub harness that records what the
slide asked for. What matters is that the quadrant receives rows in the
[name, bubble, x, y] order the chart expects -- transposing x and y would
produce a plausible, wrong picture that no test of the metrics would catch.
"""
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.deck import txn_compete as P  # noqa: E402


class _Harness(dict):
    """Records every slide, chart and rail the builder asks for."""

    def __init__(self):
        super().__init__()
        self.slides, self.charts, self.rails = [], [], []
        self["slide"] = self._slide
        self["chart"] = self._chart
        self["chart_left"] = lambda *a, **k: None
        self["rail"] = self._rail

    def _slide(self, headsub, title):
        self.slides.append((headsub, title))
        return object(), 1.5

    def _chart(self, name, fn, *args, **kwargs):
        self.charts.append({"name": name, "fn": fn.__name__,
                            "rows": args[0] if args else None, "kw": kwargs})
        return None                      # no file written in the test

    def _rail(self, _s, rows, **_k):
        self.rails.append(rows)


# comp_by_branch: [branch, accounts, with_competitor, pct, dollars,
#                  dollars_per_account, top_institution]
COMP_ROWS = [
    ["Harbor", 900, 360, 40.0, 220_000, 244, "Big National"],
    ["Main Street", 1200, 300, 25.0, 180_000, 150, "Cape Cod Five"],
    ["Oak Park", 400, 60, 15.0, 30_000, 75, "Big National"],
]

# hot_by_branch: [branch, at_risk, closed, closure_per_account_year,
#                 transacting_accounts, leak_pct, leak_$/acct, top_institution]
HOT_ROWS = [
    ["Harbor", 1000, 140, 14.2, 900, 40.0, 244, "Big National"],
    ["Main Street", 1400, 110, 8.0, 1200, 25.0, 150, "Cape Cod Five"],
    ["Oak Park", 500, 20, 4.1, 400, 15.0, 75, "Big National"],
]


def _run(fn, metrics):
    h = _Harness()
    skipped = fn(h, metrics, "transacting accounts")
    return h, skipped


# --------------------------------------------------------------- leak slide

def test_the_leak_slide_leads_with_the_worst_branch():
    h, skipped = _run(P.where_we_leak_by_branch, {"comp_by_branch": COMP_ROWS})
    assert skipped is None, skipped
    (head, sub), title = h.slides[0]
    assert "Harbor" in head and "40" in head, head
    assert "Big National" in sub, sub
    assert title == "Where we leak, by branch"


def test_the_leak_quadrant_gets_rows_in_the_order_the_chart_expects():
    """[name, bubble, x, y]. Transposing x and y draws a plausible lie."""
    h, _ = _run(P.where_we_leak_by_branch, {"comp_by_branch": COMP_ROWS})
    rows = h.charts[0]["rows"]
    assert rows[0][0] == "Harbor"
    assert rows[0][1] == 900                  # bubble = transacting accounts
    assert rows[0][2] == 40.0                 # x = leak %
    assert rows[0][3] == 244                  # y = dollars per account
    assert h.charts[0]["kw"]["xlabel"].startswith("accounts paying")


def test_the_leak_slide_skips_below_two_branches():
    _h, skipped = _run(P.where_we_leak_by_branch,
                       {"comp_by_branch": COMP_ROWS[:1]})
    assert skipped and "fewer than two" in skipped


# ------------------------------------------------------------ hotspot slide

def test_a_positive_correlation_says_the_same_branches():
    h, skipped = _run(P.lose_and_leak_together, {
        "hot_by_branch": HOT_ROWS, "hot_rank_correlation": 1.0,
        "hot_both_above_median": ["Harbor"]})
    assert skipped is None, skipped
    (head, sub), title = h.slides[0]
    assert "the same branches" in head, head
    assert "+1.00" in head, head
    assert "Harbor" in sub
    assert title == "Where we lose and where we leak"


def test_a_negative_correlation_says_different_branches():
    h, _ = _run(P.lose_and_leak_together, {
        "hot_by_branch": HOT_ROWS, "hot_rank_correlation": -0.9})
    (head, _sub), _t = h.slides[0]
    assert "different branches" in head, head


def test_a_weak_correlation_is_not_dressed_up_as_a_finding():
    h, _ = _run(P.lose_and_leak_together, {
        "hot_by_branch": HOT_ROWS, "hot_rank_correlation": 0.1})
    (head, _sub), _t = h.slides[0]
    assert "same branches" not in head and "different branches" not in head
    assert "branch by branch" in head, head


def test_the_hotspot_quadrant_puts_leakage_on_x_and_closures_on_y():
    h, _ = _run(P.lose_and_leak_together, {
        "hot_by_branch": HOT_ROWS, "hot_rank_correlation": 1.0})
    chart = h.charts[0]
    rows = chart["rows"]
    assert rows[0] == ["Harbor", 900, 40.0, 14.2]
    assert "competitor" in chart["kw"]["xlabel"]
    assert "closures" in chart["kw"]["ylabel"]
    assert "losing and leaking" in chart["kw"]["quads"]


def test_the_hotspot_slide_skips_when_the_join_produced_nothing():
    _h, skipped = _run(P.lose_and_leak_together, {"hot_by_branch": []})
    assert skipped and "did not join" in skipped


def test_a_branch_with_no_closure_rate_is_kept_off_the_chart():
    """None means not measurable, which is not the same as zero."""
    rows = [r[:] for r in HOT_ROWS]
    rows[1][3] = None
    h, _ = _run(P.lose_and_leak_together, {
        "hot_by_branch": rows, "hot_rank_correlation": 0.8})
    plotted = [r[0] for r in h.charts[0]["rows"]]
    assert "Main Street" not in plotted, plotted
    assert plotted == ["Harbor", "Oak Park"]
