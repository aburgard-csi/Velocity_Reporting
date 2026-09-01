"""axis — which ticks appear on a month axis, and at what angle.

`periods` decides what a tick says; this decides how many there are. Both halves
were open-coded per chart before: seven ARS renderers each picked their own
thinning step and rotation, so the same 36-month series read at one density on
one slide and another density on the next.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pytest

from axis import DENSE_AT, MAX_TICKS, month_ticks, rotation_for, tick_indices
from periods import MONTH_ABBR, is_axis_label


def months(n, start=(2023, 9)):
    """`n` consecutive ODD month tokens."""
    y, m = start
    out = []
    for _ in range(n):
        out.append(f"{MONTH_ABBR[m - 1]}{y % 100:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def drawn(n, width_in=8.0, pt=9, **kw):
    """Render an axis and read back what actually landed on it."""
    fig, ax = plt.subplots(figsize=(width_in, 3))
    month_ticks(ax, np.arange(n), months(n), pt=pt, **kw)
    ticks = [t.get_text() for t in ax.get_xticklabels()]
    rot = ax.get_xticklabels()[0].get_rotation() if ticks else 0
    plt.close(fig)
    return ticks, rot


# --- which ticks ----------------------------------------------------------
@pytest.mark.parametrize("n", [1, 2, 6, 9, 12, 14, 15, 24, 36, 37, 60])
def test_the_newest_point_always_carries_a_tick(n):
    """The endpoint is the headline number on the growth and reach charts.

    It used to be labelled only when the thinning step happened to land on it.
    """
    assert tick_indices(n)[-1] == n - 1


@pytest.mark.parametrize("n", [15, 24, 36, 37, 60])
def test_a_dense_series_is_thinned(n):
    idx = tick_indices(n)
    assert len(idx) <= MAX_TICKS + 1, f"{n} points left {len(idx)} ticks"
    assert len(idx) >= 6, f"{n} points thinned down to {len(idx)} ticks"


@pytest.mark.parametrize("n", range(1, DENSE_AT + 1))
def test_a_short_series_labels_every_point(n):
    assert tick_indices(n) == list(range(n))


def test_the_endpoint_never_crowds_its_neighbour():
    """Appending it blindly put two labels a hair apart; inside half a step it
    replaces the neighbour instead."""
    for n in range(15, 80):
        idx = tick_indices(n)
        gaps = [b - a for a, b in zip(idx, idx[1:])]
        assert min(gaps) > max(gaps) / 2, f"n={n} ticks bunch at the end: {idx}"


def test_indices_are_ordered_and_unique():
    for n in range(1, 80):
        idx = tick_indices(n)
        assert idx == sorted(set(idx)), f"n={n} -> {idx}"


# --- what angle -----------------------------------------------------------
def test_a_handful_of_ticks_stays_horizontal():
    _, rot = drawn(6)
    assert rot == 0


def test_a_dense_series_reads_at_45():
    _, rot = drawn(36)
    assert rot == 45


def test_a_middling_series_rotates_only_when_it_has_to():
    """Same 12 months, two widths. The narrow one rotates; the wide one does not."""
    _, narrow = drawn(12, width_in=4.0)
    _, wide = drawn(12, width_in=14.0)
    assert narrow == 30 and wide == 0


def test_rotation_is_measured_not_counted():
    """Bigger type in the same box is what tips it over, not the tick count."""
    assert rotation_for(["May'24"] * 12, 12, 6.0, 9) == 0
    assert rotation_for(["May'24"] * 12, 12, 6.0, 16) == 30


# --- end to end -----------------------------------------------------------
@pytest.mark.parametrize("n", [6, 12, 24, 36])
def test_every_rendered_tick_is_in_the_standard_vocabulary(n):
    ticks, _ = drawn(n)
    assert ticks and all(is_axis_label(t) for t in ticks), ticks


def test_month_ticks_takes_any_form_the_pipeline_carries():
    """ARS packs carry "%b %Y" and "%b %y"; the ICS workbook carries "%b %y";
    VIP exports whatever it exports. All land on the same axis."""
    fig, ax = plt.subplots(figsize=(8, 3))
    month_ticks(ax, np.arange(4), ["Sep 2025", "Oct 25", "Nov25", "2025-12"])
    assert [t.get_text() for t in ax.get_xticklabels()] == \
        ["Sep'25", "Oct'25", "Nov'25", "Dec'25"]
    plt.close(fig)


def test_an_unreadable_month_stops_the_chart():
    fig, ax = plt.subplots(figsize=(8, 3))
    with pytest.raises(ValueError) as e:
        month_ticks(ax, np.arange(3), ["Sep25", "Oct25", "n/a"],
                    field="enrollments_by_month.months")
    assert "enrollments_by_month.months[2]" in str(e.value)
    plt.close(fig)


def test_month_ticks_returns_the_full_series_not_just_the_shown_ones():
    """Callers reuse it for a partial-month legend rather than formatting twice."""
    fig, ax = plt.subplots(figsize=(8, 3))
    labels = month_ticks(ax, np.arange(36), months(36))
    plt.close(fig)
    assert len(labels) == 36 and labels[-1] == "Aug'26"
