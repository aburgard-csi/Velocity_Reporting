"""Transaction Intelligence chart labels (Aaron, 2026-10-28: "a lot of long overlapping numbers in
charts and labels"). One money grammar on bars, rails and axes; no label on a zero series; a count
printed as a count; bubble names that clear their neighbours with a leader line when they had to
move; a ledger with every row named; Pareto names wrapped, not cut; and a render-time report of
labels on bubbles or off the canvas, which the gate cannot see inside a chart image."""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build"), str(REPO / "build" / "ars_pipeline")]
from ti.deck import charts, charts_story, charts_txn, labels  # noqa: E402


# ---------------------------------------------------------------- one grammar
def test_money_has_a_billion_tier_and_a_count_is_a_count():
    assert labels.money(1_234_567_890) == "$1.2B"
    assert labels.money(79_340_378) == "$79.3M"
    assert labels.money(1644) == "$1.6K"
    assert labels.count(14150) == "14,150"
    assert labels.signed_count(14150) == "+14,150"
    assert labels.signed_count(-327) == "-327"
    assert labels.signed_count(0.2) == "0"


def test_axis_ticks_and_the_other_formatters_speak_the_same_grammar():
    assert charts._money_tick(2_500_000) == "$2.5M"           # was "$2.5m"
    assert charts._money_tick(750_000) == "$750K"
    assert charts_txn._fmt_money(5_091_694) == "$5.1M"
    from ti.deck import attrition_slides, deposit_slides
    assert attrition_slides._money(1_234_567) == "$1.2M"      # was "$1,234,567"
    assert deposit_slides._money(1_200_000_000) == "$1.2B"    # was "$1.2bn"


def test_the_waterfall_prints_dollars_not_a_k_pinned_on_a_full_figure(tmp_path):
    steps = [("Credit Cards", 79_340_378, "start"), ("P2P", 24_440_719, "up"),
             ("Insurance", 17_762_441, "up"), ("these three", 121_543_538, "end")]
    charts.waterfall_bridge(steps, tmp_path / "w.png")
    texts = _texts_of(lambda: charts.waterfall_bridge(steps, tmp_path / "w2.png"))
    assert "$79.3M" in texts and "+$24.4M" in texts and "$121.5M" in texts
    assert not any("K" in t and "," in t for t in texts)


def test_grouped_bars_take_the_grammar_and_skip_a_zero_series(tmp_path):
    texts = _texts_of(lambda: charts.grouped_bars(
        ["Walmart", "Venmo"], [0, 0], [5_091_694, 1_277_356], "PIN", "Signature",
        tmp_path / "g.png", fmt=labels.money))
    assert "$5.1M" in texts and "$1.3M" in texts
    assert "$0" not in texts and "0" not in texts


def test_momentum_prints_a_net_count_as_a_count(tmp_path):
    rows = [["Capital One", 14150, "$1.6K/acct", 14150, False], ["Chase", 8395, "$2.6K/acct", -40, False]]
    fig, info = charts._momentum_fig(rows, "", momentum_unit="")
    plt.close(fig)
    assert info["momentum_texts"] == ["↗ +14,150", "↘ −40"]
    fig, info = charts._momentum_fig(rows, "", momentum_unit="%")
    plt.close(fig)
    assert info["momentum_texts"][0] == "↗ +14150%"       # the unit stays the caller's


def test_a_money_axis_prints_money_and_never_a_scientific_offset():
    rows = [["Chase", 8395, 11.6, 21_887_042], ["Capital One", 14150, 19.5, 23_259_225],
            ["Citi", 5473, 7.5, 15_200_000]]
    fig, _ = charts._quadrant_fig(rows, "penetration", "spend", yfmt=labels.money)
    fig.canvas.draw()
    ax = fig.axes[0]
    ticks = [t.get_text() for t in ax.get_yticklabels() if t.get_text()]
    assert ticks and all(t.startswith("$") for t in ticks), ticks
    assert ax.yaxis.get_offset_text().get_text() == ""
    plt.close(fig)


# ---------------------------------------------------------------- bubble names
CLUSTER = [["3", 10, 47.8, 3100], ["24", 9, 48.9, 3000], ["6", 14, 49.1, 2900], ["41", 12, 49.3, 2700],
           ["39", 7, 47.9, 2500], ["26", 8, 48.6, 2300], ["9", 18, 49.4, 2200], ["25", 6, 47.9, 3900],
           ["20", 6, 47.8, 11600], ["47", 5, 62.2, 6200], ["11", 11, 51.9, 3900], ["14", 10, 52.3, 3700]]


def test_a_crowded_cluster_still_names_every_bubble_clear_of_the_others():
    fig, _ = charts._quadrant_fig(CLUSTER, "x", "y")
    ax = fig.axes[0]
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    names = {r[0] for r in CLUSTER}
    boxes = [t.get_window_extent(renderer) for t in ax.texts if t.get_text() in names]
    assert len(boxes) == len(CLUSTER)
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            assert not a.overlaps(b), "two names overlap"
    # a name that had to move out of the cluster has a leader line back to its bubble
    assert ax.lines, "no leader lines drawn for the names that moved"
    assert not charts._report_overlaps(fig, Path("cluster.png")), "a name still sits on a bubble"
    charts.RENDER_WARNINGS.clear()
    plt.close(fig)


def test_the_overlap_report_names_a_label_on_a_foreign_bubble_and_one_off_the_canvas():
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter([1, 2], [1, 1], s=[2000, 2000])
    ax.text(1, 1, "on the bubble", ha="center", va="center")
    ax.text(0, 1.9, "x" * 400, ha="left", va="center")        # runs off the right edge
    fig.canvas.draw()
    found = charts._report_overlaps(fig, Path("probe.png"))
    assert any("sits on a bubble" in m for m in found)
    assert any("runs off the canvas" in m for m in found)
    assert charts.RENDER_WARNINGS and charts.RENDER_WARNINGS[0].startswith("probe.png: ")
    charts.RENDER_WARNINGS.clear()
    plt.close(fig)


def test_a_chart_past_the_threshold_is_refused_not_shipped(tmp_path):
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter([1] * 8, [1] * 8, s=[2000] * 8)
    for i in range(charts.UNREADABLE_LABELS + 1):
        ax.text(1, 1, f"n{i}", ha="center", va="center")
    fig.canvas.draw()
    with pytest.raises(charts.ChartUnreadable):
        charts._report_overlaps(fig, Path("bad.png"))
    charts.RENDER_WARNINGS.clear()


# ---------------------------------------------------------------- ledger and Pareto
def test_the_ledger_names_every_row_beside_its_bar():
    rows = [[f"PROVIDER {i}", 100 - i, (100 - i) * 1000, i % 3 == 0] for i in range(20)]
    fig, info = charts_story._ledger_fig(rows, "7 of 20 are institutions")
    texts = [t.get_text() for t in fig.axes[0].texts]
    assert all(f"Provider {i}" in texts for i in range(20))
    assert info["flagged"] == 7
    plt.close(fig)


def test_pareto_names_wrap_instead_of_being_cut():
    rows = [["Capital One Mobile Payment", "", 11_000_000], ["Discover E-Payment", "", 5_300_000],
            ["Cash App", "", 15_500_000]]
    fig, _ = charts_txn._pareto_fig(rows, 0.8, "")
    ticks = [t.get_text() for t in fig.axes[0].get_xticklabels()]
    # wrapped at 11 since the labels went to 13pt (Sheila's 1798 slide review, 2026-10-30: chart
    # text under 12pt on the slide); still wrapped whole, never cut
    assert "Capital One\nMobile\nPayment" in ticks and "…" not in "".join(ticks)
    assert all(len(line) <= 11 for tick in ticks for line in tick.splitlines())
    plt.close(fig)


def _texts_of(render):
    """The text artists a renderer draws, read through the save hook."""
    seen = []
    real = charts._save

    def spy(fig, path):
        seen.extend(t.get_text() for ax in fig.axes for t in ax.texts)
        return real(fig, path)
    charts._save = spy
    try:
        render()
    finally:
        charts._save = real
    return seen


# ---------------------------------------------------------------- v5 month labels (Sheila, 1798, 2026-10-30)
@pytest.mark.parametrize("draw", [
    lambda out: charts.line_series([["Jan24", 1.0], ["Feb24", 2.0], ["Aug24", 3.0]], out, money=True),
    lambda out: charts.line_with_base([["Jan24", 100, 40.0], ["Feb24", 120, 42.0], ["Mar24", 90, 41.0]], out),
    lambda out: charts.grouped_bars(["Jan24", "Feb24"], [1, 2], [2, 3], "a", "b", out),
    lambda out: charts.response_reach_combo([["Jun24", 4.0], ["Jul24", 5.0]], [["Jun24", 10.0], ["Jul24", 18.0]], out),
    lambda out: charts.dual_series([["Jan24", 10, 5], ["Feb24", 12, 6]], out),
])
def test_v5_month_labels_draw_in_the_house_format_instead_of_failing(tmp_path, draw):
    """The packs label months as the ODD does ("Jan24"); the month-axis guard refused them and
    Deck.chart swallowed the error, so five charts (and the hero sparkline) were missing from 1798's
    deck while it validated 0 FAIL."""
    out = tmp_path / "c.png"
    draw(out)
    assert out.exists()
