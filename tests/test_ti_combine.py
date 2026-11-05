"""Two one-chart slides of the Transaction Intelligence cut drawn as one (ti/deck/combine.py; Aaron,
2026-11-02: "charts that can be combined into one slide"). Synthetic figures only.

* the pair is ONE slide, with a picture per panel, each panel captioned with its builder's own headline;
* every figure is authored for half a slide, at the width it lands at, and the module's sizes are put back;
* a pair that cannot share a slide is drawn as it always was, and says so in the build log;
* one half declined for the client: the other is drawn alone, the declined half recorded as declined;
* both declined: ONE decline, under the combined topic, with the reason said once;
* a negative bar (card spend on the deposits chapter) is drawn to the left of zero, not off the canvas.
"""
import os

import pytest
from pptx import Presentation

from ti.deck import charts, combine
from ti.deck.helpers import Deck


@pytest.fixture(autouse=True)
def _keep_every_slide(tmp_path, monkeypatch):
    monkeypatch.setenv("TI_SLIDES", str(tmp_path / "keep-all.json"))
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))


class _Ctx:
    def __init__(self, tmp):
        self.prs = Presentation(os.path.join(os.path.dirname(__file__), "..", "templates", "ars_template.pptx"))
        self.pack = {"client_id": "9999", "client_name": "Test Bank", "sources": {"odd": "9999-ODD.csv"},
                     "metrics": {}}
        self.lens = type("L", (), {"label": "ARS lens"})()
        self.pill, self.art_dir = "September 2026 Data", str(tmp)


ROWS = [["Alpha", 120.0], ["Beta", 80.0], ["Gamma", 30.0]]


def left_builder(h, t, base):
    if not t.get("left"):
        return "Left (no left)"
    s, top = h["slide"](("Left finding: Alpha leads", "the left subtitle"), "Left topic")
    h["rail"](s, [("Lead", "Alpha", "120")], top=top)
    path = h["chart"]("left_chart", charts.tier_bars, ROWS, share=False)
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


def right_builder(h, t, base):
    if not t.get("right"):
        return "Right (no right)"
    s, top = h["slide"](None, "Right topic")
    path = h["chart"]("right_chart", charts.tier_bars, ROWS, share=False)
    if path:
        h["chart_left"](s, path, top, h["RIGHT_EDGE"])


def table_builder(h, t, base):
    s, top = h["slide"](("A table slide", "x"), "Table topic")
    h["table"](s, [["a", "b"], ["1", "2"]], 0.6, top, 6.0)


def two_chart_builder(h, t, base):
    s, top = h["slide"](("Two charts", "x"), "Two-chart topic")
    h["chart"]("c1", charts.tier_bars, ROWS, share=False)
    h["chart"]("c2", charts.tier_bars, ROWS, share=False)


def _combined(a=left_builder, b=right_builder):
    return combine.combine("Both topic", "Both headline", "Both subtitle",
                           (a, "Left topic"), (b, getattr(b, "topic", "Right topic")), "both_builder")


def _run(tmp_path, builder, figures):
    d = Deck(_Ctx(tmp_path), "test", tmp_path / "charts")
    d.run([builder], {"both_builder": "Both topic"}, figures, "accounts")
    return d


def _pictures(slide):
    return [sh for sh in slide.shapes if sh.shape_type == 13]


def _text(slide):
    return " ".join(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame)


def test_a_pair_is_one_slide_with_a_picture_and_a_caption_per_panel(tmp_path):
    d = _run(tmp_path, _combined(), {"left": 1, "right": 1})
    assert len(d.slides) == 1 and not d.declines
    s = d.slides[0]
    assert d.topics[id(s)] == "Both topic"
    pics = [p for p in _pictures(s) if p.width > 3_000_000]     # the two panels, not the logo
    assert len(pics) == 2
    text = _text(s)
    assert "Both headline" in text and "Left finding: Alpha leads" in text and "Right topic" in text
    assert "Both topic" in s.notes_slide.notes_text_frame.text or "Left topic" in s.notes_slide.notes_text_frame.text
    assert "Source" in s.notes_slide.notes_text_frame.text


def test_the_panels_sit_side_by_side_inside_the_content_width(tmp_path):
    d = _run(tmp_path, _combined(), {"left": 1, "right": 1})
    panels = sorted((p for p in _pictures(d.slides[0]) if p.width > 3_000_000), key=lambda p: p.left)
    assert len(panels) == 2
    assert panels[0].left + panels[0].width <= panels[1].left
    assert panels[1].left + panels[1].width <= 12.73 * 914400 + 1


def test_the_figure_width_is_put_back_after_the_block():
    before = (charts.FIG_W_RAIL, charts.FIG_W_FULL, charts.FIG_H_RAIL, charts.FIG_H_FULL)
    import matplotlib.pyplot as plt
    real = plt.subplots
    with combine.half_width():
        assert charts.FIG_W_RAIL == charts.FIG_W_FULL == combine.HALF_FIG_W
        fig, _ = plt.subplots(figsize=(11.5, 5.2))          # taller than the band: drawn at the band
        assert fig.get_size_inches()[1] == combine.HALF_FIG_H
        plt.close(fig)
    assert (charts.FIG_W_RAIL, charts.FIG_W_FULL, charts.FIG_H_RAIL, charts.FIG_H_FULL) == before
    assert plt.subplots is real


def test_a_chart_is_authored_at_half_width(tmp_path):
    from PIL import Image
    d = _run(tmp_path, _combined(), {"left": 1, "right": 1})
    with Image.open(tmp_path / "charts" / "both_builder_0.png") as img:
        assert img.size[0] / charts.DPI == pytest.approx(combine.HALF_FIG_W, abs=0.01)


def test_a_half_that_declines_leaves_the_other_alone_and_is_recorded(tmp_path):
    d = _run(tmp_path, _combined(), {"left": 1})
    assert [d.topics[id(s)] for s in d.slides].count("Left topic") == 1
    assert "Both topic" not in [d.topics[id(s)] for s in d.slides]
    assert d.declines == [("Right topic", "no right")]


def test_both_declined_is_one_decline_with_the_reason_said_once(tmp_path):
    d = _run(tmp_path, _combined(), {})
    assert d.declines == [("Both topic", "no left; no right")]


def test_a_builder_that_draws_a_table_is_not_combined(tmp_path, capsys):
    d = _run(tmp_path, _combined(table_builder, right_builder), {"right": 1})
    topics = [d.topics[id(s)] for s in d.slides]
    assert "Table topic" in topics and "Right topic" in topics and "Both topic" not in topics
    assert "not combined" in capsys.readouterr().out


def test_a_builder_that_draws_two_charts_is_not_combined(tmp_path):
    d = _run(tmp_path, _combined(two_chart_builder, right_builder), {"right": 1})
    assert "Both topic" not in [d.topics[id(s)] for s in d.slides]


def test_apply_puts_the_pair_at_the_first_place_and_leaves_the_chapters_titles_alone():
    def a(h, t, b): ...
    def b(h, t, b_): ...
    def c(h, t, b_): ...
    titles = {"a": "A", "b": "B", "c": "C"}
    out, merged = combine.apply([a, b, c], titles, [("a", "b", "AB", "AB headline", "sub", "a_and_b")])
    assert [x.__name__ for x in out] == ["a_and_b", "c"]
    assert merged["a_and_b"] == "AB" and "a_and_b" not in titles
    # a pair whose builders are not in the list is left alone
    out2, _ = combine.apply([c], titles, [("a", "b", "AB", "h", "s", "a_and_b")])
    assert out2 == [c]


def test_every_combined_pair_of_the_cut_names_builders_its_chapter_carries():
    from ti import chapters_txn as X
    from ti.chapters import attrition, campaign, deposits
    from ti.deck import attrition_inline, attrition_slides, campaign_inline, deposit_slides
    names = {X.__name__: {b.__name__ for b in X.TI_BUILDERS + X.COMP_BUILDERS}}
    carried = {"chapters_txn": (X.TI_COMBINED + X.COMP_COMBINED, names[X.__name__]),
               "attrition": (attrition.COMBINED, {n for n in attrition.TITLES}),
               "deposits": (deposits.COMBINED, set(deposits.TITLES)),
               "campaign": (campaign.COMBINED, set(campaign.TITLES))}
    for chapter, (pairs, available) in carried.items():
        for first, second, topic, *_ in pairs:
            assert first in available and second in available, (chapter, first, second)
    del attrition_inline, attrition_slides, campaign_inline, deposit_slides


def test_a_negative_bar_is_drawn_left_of_zero(tmp_path):
    from PIL import Image
    import numpy as np
    path = charts.value_waterfall([["Inflow", 3_000_000.0], ["Card spend", -600_000.0], ["Net", 2_400_000.0]],
                                  tmp_path / "wf.png")
    with Image.open(path) as img:
        px = np.asarray(img.convert("RGB")).astype(int)
    red = (np.abs(px[..., 0] - 235) < 12) & (np.abs(px[..., 1] - 42) < 14) & (np.abs(px[..., 2] - 46) < 14)
    assert red.sum() > 400                       # the red card-spend bar is on the canvas
