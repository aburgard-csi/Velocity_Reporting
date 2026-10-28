"""PGL deck charts: the score slide is a tornado, not grouped bars (#191).

v5 tests/test_pgl_deck_charts.py, unchanged but for the import.
"""
import matplotlib
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from ils_pipeline.pre_go_live import deck_charts  # noqa: E402

# The shape score.compute() writes, with client 1737's real numbers.
HEADLINE = {
    "personal": {"up": 4501, "down": 4023, "same": 6449, "base": 14973},
    "business": {"up": 7, "down": 31, "same": 70, "base": 108},
    "eligible": {"up": 4501, "down": 4020, "same": 1115, "base": 9636},
    "opted_in": {"up": 1801, "down": 1454, "same": 790, "base": 4045},
}


@pytest.fixture
def ax():
    fig, ax = plt.subplots()
    yield ax
    plt.close(fig)


def _bar_widths(ax):
    return sorted(round(p.get_width()) for c in ax.containers for p in c)


def test_down_is_drawn_left_of_centre_and_up_right_of_it(ax):
    deck_charts.draw_score_tornado(ax, HEADLINE)
    widths = _bar_widths(ax)
    assert widths == sorted([-4023, 4501, -31, 7, -4020, 4501, -1454, 1801])


def test_direction_lives_in_the_geometry_so_there_is_no_legend(ax):
    deck_charts.draw_score_tornado(ax, HEADLINE)
    assert ax.get_legend() is None


def test_rows_are_labelled_with_base_and_account_count(ax):
    deck_charts.draw_score_tornado(ax, HEADLINE)
    labels = [t.get_text() for t in ax.get_yticklabels()]
    assert labels[0].startswith("personal")
    assert "14,973" in labels[0]
    assert len(labels) == 4


def test_same_count_survives_as_a_row_note_not_a_bar(ax):
    deck_charts.draw_score_tornado(ax, HEADLINE)
    texts = [t.get_text() for t in ax.texts]
    assert any("6,449" in t and "same" in t for t in texts)
    assert 6449 not in _bar_widths(ax)


def test_bases_without_accounts_are_skipped(ax):
    deck_charts.draw_score_tornado(
        ax, {"personal": HEADLINE["personal"],
             "business": {"up": 0, "down": 0, "same": 0, "base": 0}})
    assert len(ax.get_yticklabels()) == 1


def test_score_updown_still_writes_the_png(tmp_path):
    out = deck_charts.score_updown(HEADLINE, tmp_path / "pgl_score.png")
    assert out.exists() and out.stat().st_size > 0
