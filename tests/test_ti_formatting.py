"""Transaction Intelligence formatting: the overlaps found on the 1075 Austin Bank deck (2026-10-27).

Titles that wrapped to three lines over their subtitle; treemap and block labels that ran into the
block beside them; bubble names stacked on bubbles and on each other; two dollar signs in one string
turning a label into italic mathtext; a dollar row and a percent row sharing one dumbbell axis; a
bar value label under the cumulative line; a radar that drew a quarter of itself.
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ("build", "build/ars_pipeline"):
    sys.path.insert(0, os.path.join(REPO, p))

from ti.deck import charts, charts_story, charts_txn, helpers as H  # noqa: E402


# ---------------------------------------------------------------- titles

SLIDE_9 = "60% of transacting personal accounts send $164.8M a year to other institutions' financial products"
SLIDE_53 = "48% of transacting personal accounts pay a named bank; 42% are inside a payment ecosystem"


def test_a_long_title_is_sized_to_two_lines_not_estimated_from_its_length():
    for title in (SLIDE_9, SLIDE_53):
        size, lines = H._fit(title)
        assert lines <= 2, (title, size, lines)
        assert size < 30
        # PowerPoint sets the face a little wider than the measure: at 5% wider it must still be two lines
        # (the character-count estimate said two lines for slide 9 and PowerPoint drew three)
        wider = len(H._wrap(title, H.TITLE_W / 1.05, size, H.HEAD_FONT, True))
        assert wider <= 2, (title, size, wider)


def test_a_short_title_keeps_one_big_line_and_the_fit_never_goes_below_20pt():
    assert H._fit("Twelve months of flow") == (30, 1)
    size, lines = H._fit("word " * 60)
    assert size == 20 and lines >= 3        # past the floor the lines are counted so the layout reserves them


def test_the_title_box_grows_with_the_lines_the_text_takes():
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    title, bottom = H._title(slide, "word " * 60, "a subtitle that adds a source and a base")
    box = next(sh for sh in slide.shapes if sh.has_text_frame and sh.text_frame.text.startswith("word"))
    assert box.height > Inches(1.05)
    assert bottom >= (box.top + box.height) / 914400


# ---------------------------------------------------------------- labels inside blocks

def _extent_in_data(ax, text):
    fig = ax.figure
    renderer = fig.canvas.get_renderer()
    bb = text.get_window_extent(renderer)
    (x0, _), (x1, _) = ax.transData.inverted().transform([(bb.x0, bb.y0), (bb.x1, bb.y1)])
    return abs(x1 - x0)


def test_fit_text_keeps_a_label_inside_its_block():
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    width = 0.13
    t = charts.fit_text(ax, 0.01, 0.9, width, "Online Banks / Savings", 10.5, floor=8,
                        fontweight="bold", va="top")
    assert _extent_in_data(ax, t) <= width
    assert t.get_fontsize() <= 10.5
    plt.close(fig)


def test_fit_text_wraps_a_sub_line_and_cuts_what_cannot_fit_at_the_floor():
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    t = charts.fit_text(ax, 0.01, 0.9, 0.2, "4.3% of transacting personal accounts · $835K", 9.5,
                        floor=8, max_lines=3, va="top")
    assert "\n" in t.get_text()
    assert _extent_in_data(ax, t) <= 0.2
    one = charts.fit_text(ax, 0.01, 0.5, 0.05, "Online Banks / Savings", 10, floor=8, va="top")
    assert one.get_text().endswith("…") and "\n" not in one.get_text()
    plt.close(fig)


def test_a_label_that_fits_is_left_exactly_as_written():
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    t = charts.fit_text(ax, 0.01, 0.9, 0.9, "Credit Cards", 10.5, floor=8, va="top")
    assert t.get_text() == "Credit Cards" and t.get_fontsize() == 10.5
    plt.close(fig)


# ---------------------------------------------------------------- bubble names

def test_bubble_names_do_not_overlap_each_other_or_the_other_bubbles():
    rows = [["Garrison", 5, 47.8, 3900], ["Bullard", 6, 47.9, 3100], ["Lufkin", 6, 48.7, 2800],
            ["Nacogdoches", 8, 49.0, 2700], ["Palestine", 14, 49.2, 2300], ["Emory", 5, 47.8, 2200],
            ["Whitehouse", 7, 51.6, 3800], ["Tyler South", 8, 52.1, 3700], ["Cypress Creek", 9, 62.2, 6100]]
    fig, _ = charts._quadrant_fig(rows, "x", "y")
    ax = fig.axes[0]
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    names = {r[0] for r in rows}
    boxes = [t.get_window_extent(renderer) for t in ax.texts if t.get_text() in names]
    assert len(boxes) == len(rows)
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            assert not a.overlaps(b)
    plt.close(fig)


# ---------------------------------------------------------------- dollar signs

def test_two_dollar_signs_in_one_label_print_as_text():
    fig, ax = plt.subplots()
    t = ax.text(0, 0, "$2,984 vs $6,044")
    charts._literal_dollars(fig)
    assert t.get_parse_math() is False and t.get_text() == "$2,984 vs $6,044"
    escaped = ax.text(0, 0, r"\$1 and \$2")          # a chart that escaped them by hand keeps working
    charts._literal_dollars(fig)
    assert escaped.get_text() == "$1 and $2"
    plt.close(fig)


# ---------------------------------------------------------------- dumbbell

def test_a_dumbbell_row_carries_its_own_unit_and_a_signed_change():
    assert charts._delta_text("+{:.1f}", -3.0) == "-3.0"
    assert charts._delta_text("+{:.1f}", 3.0) == "+3.0"
    assert charts._delta_text(lambda d: f"{d:+.0f}!", -2) == "-2!"
    rows = [["Share", 44.9, 40.9, "x", "{:.1f}%", "{:+.1f} pts"],
            ["Dollars", 2984, 6044, "y", lambda v: f"${v:,.0f}", lambda d: f"{d:+,.0f}"]]
    fig, _ = charts._dumbbell_fig(rows, "a", "b", own_scale=True)
    texts = [t.get_text() for t in fig.axes[0].texts]
    assert "44.9%" in texts and "$2,984" in texts and "-3,060" in texts and "+4.0 pts" in texts
    assert not any("%" in t and "2984" in t for t in texts)
    plt.close(fig)


# ---------------------------------------------------------------- pareto, radar, donut

def test_the_pareto_value_labels_sit_clear_of_the_cumulative_line():
    rows = [["A", "", 18.4e6], ["B", "", 15.5e6], ["C", "", 11.0e6], ["D", "", 10.1e6], ["E", "", 9.9e6]]
    fig, _ = charts_txn._pareto_fig(rows, 0.8, "")
    fig.canvas.draw()
    ax2 = fig.axes[1]
    line = ax2.lines[0]
    peak = 18.4e6
    cum = line.get_ydata()
    values = [t for t in ax2.texts if t.get_text().startswith("$")]
    assert len(values) == len(rows)           # drawn on the line's axes, above it
    for t in values:
        x, y = t.get_position()
        i = round(x)
        line_y = cum[i] * peak
        assert not (y - 0.03 * peak <= line_y <= y + 0.09 * peak), (t.get_text(), y, line_y)
    plt.close(fig)


def test_the_radar_draws_every_axis_of_the_circle():
    names = ["leakage", "external $", "competitor", "multi-banked", "card spend", "swipes/mo"]
    fig, meta = charts_story._radar_fig(names, [.9, .5, .95, .85, 1, 1], [.8, 1, .9, .9, .5, .4], "a", "b",
                                        ["1"] * 6)
    ax = fig.axes[0]
    fig.canvas.draw()
    assert ax.get_thetamin() == 0 and round(ax.get_thetamax()) == 360
    assert all(0 <= a <= 2 * 3.1416 for a in ax.get_xticks())
    assert len([t for t in ax.get_xticklabels() if t.get_text()]) == 6
    plt.close(fig)


def test_a_donut_label_on_the_left_is_set_to_the_left_of_its_leader(tmp_path, monkeypatch):
    seen = []
    real_save = charts._save
    monkeypatch.setattr(charts, "_save", lambda fig, path: seen.append(fig) or real_save(fig, path))
    charts.donut([["Digital Bank / Fintech", 3623], ["Card Issuer", 17851], ["National Bank", 25942],
                  ["Brokerage / Wealth", 2940]], tmp_path / "donut.png")
    notes = {t.get_text().split("\n")[0]: t for t in seen[0].axes[0].texts if "\n" in t.get_text()}
    assert notes["National Bank"].get_ha() == "right"      # at the lower left
    assert notes["Card Issuer"].get_ha() == "left"         # at the right
