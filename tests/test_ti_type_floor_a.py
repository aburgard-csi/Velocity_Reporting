"""Text floors on the Transaction Intelligence slides and charts (Sheila's 1798 slide review,
2026-10-30: text at 9.5-10pt on 109 of 144 slides, month ticks running together on slide 34).

Subtitle 14pt (12pt at the least), rail and KPI labels and notes 12pt or more, table font 10pt or
more, and every piece of chart text authored at charts.CHART_MIN_PT, which lands at about 12pt at the
scale the slide places a chart."""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import pytest
from pptx import Presentation
from pptx.util import Inches

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build"), str(REPO / "build" / "ars_pipeline")]
from ti.deck import charts, helpers as H  # noqa: E402


def _slide():
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    return prs.slides.add_slide(prs.slide_layouts[6])


def _sizes(slide):
    return [r.font.size.pt for sh in slide.shapes if sh.has_text_frame
            for p in sh.text_frame.paragraphs for r in p.runs if r.font.size and r.text.strip()]


def test_a_short_subtitle_is_14pt_and_a_long_one_never_goes_under_12pt():
    assert H._fit_subtitle("Eligible card accounts, last 12 months", H.TITLE_W)[1] == 14
    long = " ".join(["a much longer subtitle that keeps on going"] * 8)
    text, pt, lines = H._fit_subtitle(long, H.TITLE_W)
    assert pt == 12 and lines == 2 and text.endswith("…")


@pytest.mark.parametrize("n", [3, 5])
def test_rail_labels_values_and_notes_are_12pt_or_more(n):
    s = _slide()
    items = [("Accounts paying externally elsewhere", "11,669", "of 63,944 transacting personal accounts")] * n
    H._rail(s, items, top=1.95)
    assert min(_sizes(s)) >= H.LABEL_MIN_PT


def test_kpi_label_and_note_are_12pt_even_on_a_compact_card():
    s = _slide()
    H._kpi(s, 0.7, 5.5, 3.71, "Responses", "34,598", "response events; 24,699 accounts, 22,191 still eligible")
    assert min(_sizes(s)) >= H.LABEL_MIN_PT


def test_every_chart_text_is_raised_to_the_floor_but_a_fitted_label_is_left(tmp_path):
    import matplotlib.pyplot as plt
    from matplotlib.text import Text
    fig, ax = plt.subplots(figsize=(charts.FIG_W_RAIL, charts.FIG_H_RAIL))
    ax.bar([0, 1], [1, 2])
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["a", "b"], fontsize=8)
    ax.text(0, 1, "small", fontsize=7)
    fitted = charts.fit_text(ax, 0, 0.5, 0.2, "a label far too long for its block", 9, floor=7.5)
    charts._type_floor(fig)
    small = [t for t in fig.findobj(Text) if t.get_text().strip() and t is not fitted
             and t.get_fontsize() < charts.CHART_MIN_PT]
    assert small == []
    assert fitted.get_fontsize() < charts.CHART_MIN_PT
    assert charts.CHART_MIN_PT * charts.PLACED_SCALE >= 11.9
    plt.close(fig)


def test_crowded_horizontal_ticks_are_angled_not_shrunk(tmp_path):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.bar(range(8), range(8))
    ax.set_xticks(range(8))
    ax.set_xticklabels([f"Category {i}" for i in range(8)])
    charts._type_floor(fig)
    fig.tight_layout()
    assert charts._untangle_ticks(fig)
    assert all(t.get_rotation() == 45 for t in ax.get_xticklabels())
    assert all(t.get_fontsize() >= charts.CHART_MIN_PT for t in ax.get_xticklabels())
    plt.close(fig)


def test_a_long_month_axis_names_at_most_twelve_months_and_keeps_the_highlight(tmp_path):
    months = [f"{m}{y}" for y in (24, 25, 26) for m in
              ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")][:33]
    rows = [[m, 100 + i, 90 - i * 0.5] for i, m in enumerate(months)]
    fig, _ = charts._line_with_base_fig(rows, highlight="Sep25")
    ax = fig.axes[0]
    labels = [t.get_text() for t in ax.get_xticklabels()]
    assert len(labels) <= charts.MAX_MONTH_TICKS + 1
    assert "Sep'25" in labels and labels[-1] == "Sep'26", "the highlight and the latest month are named"
    bold = [t.get_text() for t in ax.get_xticklabels() if t.get_fontweight() == "bold"]
    assert bold == ["Sep'25"]
    charts.line_with_base(rows, tmp_path / "c.png", highlight=20)
    assert (tmp_path / "c.png").exists()


def test_the_quadrant_bubble_can_be_sized_by_another_field(tmp_path):
    rows = [["A", 10, 1.0, 2.0, 500], ["B", 900, 2.0, 1.0, -50], ["C", 50, 3.0, 3.0, 5]]
    fig, _ = charts._quadrant_fig(rows, "x", "y", size_idx=4)
    sizes = list(fig.axes[0].collections[0].get_sizes())
    assert sizes[0] == max(sizes), "A has the most net adds"
    import matplotlib.pyplot as plt
    plt.close(fig)
    charts.branch_quadrant(rows, tmp_path / "q.png", size_idx=4)
    assert (tmp_path / "q.png").exists()
