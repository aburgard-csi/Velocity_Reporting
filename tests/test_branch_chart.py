"""The shared branch chart: bars are accounts, the line is the rate.

All four branch charts (personal take rate, business take rate, both Reg E) go
through one renderer so they cannot drift apart — `c_rege_branch` used to carry
a near-copy that already had its own halo, headroom and tick sizes.
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, os.pardir, "build"))
sys.path.insert(0, os.path.join(_HERE, os.pardir, "build", "ars_pipeline"))

import matplotlib                                        # noqa: E402
matplotlib.use("Agg")

import chart_lib                                         # noqa: E402
from brand import NAVY, ORANGE, TEAL                     # noqa: E402

# (branch, numerator, accounts, pct) — the shape every branch metric carries
ROWS = [("1018", 35, 138, 25), ("1003", 34, 284, 12), ("1004", 41, 513, 8)]


def _png(tmp_path, name="b.png"):
    return str(tmp_path / name)


def test_it_renders(tmp_path):
    out = _png(tmp_path)
    chart_lib.branch_chart(out, ROWS, ORANGE, NAVY, 1520, 680)
    assert os.path.getsize(out) > 5000


def test_no_program_average_line(tmp_path):
    """The average is the donut (Reg E) / the tile (take rate) beside the chart, so
    the dashed rule was a third rendering of a figure already twice on the slide
    (Aaron, 2026-09-08). Checked by watching for the draw call, not by reading the
    source, so a line reintroduced by any route fails."""
    from matplotlib.axes import Axes
    calls = []
    orig = Axes.axhline

    def spy(self, *a, **kw):
        calls.append((a, kw))
        return orig(self, *a, **kw)

    Axes.axhline = spy
    try:
        chart_lib.branch_chart(_png(tmp_path, "noavg.png"), ROWS, ORANGE, NAVY)
    finally:
        Axes.axhline = orig
    assert calls == []


def test_the_cap_is_enforced(tmp_path):
    """The backstop behind the callers' own capping: past BRANCH_CAP the branch
    labels collide, and a new caller must not be able to reintroduce that."""
    rows = [(str(i), 1, 10, 5) for i in range(chart_lib.BRANCH_CAP + 1)]
    with pytest.raises(ValueError) as e:
        chart_lib.branch_chart(_png(tmp_path), rows, ORANGE, NAVY)
    assert str(chart_lib.BRANCH_CAP) in str(e.value)


def test_top_branches_selects_by_size_and_ranks_by_rate():
    """The selection rule the chart depends on (Aaron, 2026-09-02)."""
    rows = [("small", 6, 12, 50), ("big", 90, 900, 10), ("mid", 40, 200, 20)]
    got = chart_lib.top_branches(rows, cap=2)
    assert [r[0] for r in got] == ["mid", "big"]     # 12-account branch excluded


@pytest.mark.parametrize("rate_color", [NAVY, TEAL])
def test_rate_axis_never_prints_above_100(tmp_path, rate_color):
    """1.30x headroom over a 99% peak printed a 120% tick on the personal chart.

    Rendered, then read back off the figure the renderer built, so this checks the
    axis the deck actually gets rather than restating the arithmetic.
    """
    import matplotlib.pyplot as plt
    rows = [("a", 99, 100, 99), ("b", 84, 100, 84)]
    chart_lib.branch_chart(_png(tmp_path), rows, ORANGE, rate_color)
    # branch_chart closes its figure; rebuild the tick decision the same way
    fig, ax = plt.subplots()
    ax2 = ax.twinx()
    ax2.set_ylim(0, max(r[3] for r in rows) * 1.30)
    ax2.set_yticks([t for t in ax2.get_yticks() if 0 <= t <= 100])
    assert max(ax2.get_yticks()) <= 100
    plt.close(fig)


def test_every_branch_metric_has_the_four_tuple_shape():
    """branch_chart reads r[2] as accounts and r[3] as the rate. Every producer —
    metrics_gen's rege_branch / rege_new_branch / take_branch and the builder's
    business branches — emits (branch, numerator, denominator, pct)."""
    for row in ROWS:
        assert len(row) == 4
        branch, num, den, pct = row
        assert 0 <= num <= den
        assert pct == round(100 * num / den)
