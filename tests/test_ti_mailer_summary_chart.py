# Ported from ARS v5 02-Scripts/tests/test_mailer_summary_chart.py at a491b5c (James Gilmore); logic unchanged.
"""The mailer summary panel -- donut, per-tier rate bars, Inside the Numbers
(issue #80, James's legacy slide 1)."""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.deck import charts  # noqa: E402

SUMMARY = {
    "mailed": 18735, "responded": 2093, "rate": 11.2,
    "tiers": ["NU 5+", "TH-10", "TH-15", "TH-20", "TH-25"],
    "by_tier": {
        "NU 5+": {"mailed": 7919, "responded": 252, "rate": 3.2, "share": 12.0},
        "TH-10": {"mailed": 5406, "responded": 550, "rate": 10.2, "share": 26.3},
        "TH-15": {"mailed": 2278, "responded": 466, "rate": 20.5, "share": 22.3},
        "TH-20": {"mailed": 1758, "responded": 418, "rate": 23.8, "share": 20.0},
        "TH-25": {"mailed": 1374, "responded": 407, "rate": 29.6, "share": 19.4},
    },
    "mailed_unassigned": 0,
    "inside": {"new_account_pct": 20.0, "age_60_plus_pct": 29.0,
               "rege_optin_pct": 24.0, "first_time_pct": 61.0,
               "first_time_n": 1277, "repeat_n": 816, "moved_up_n": 384,
               "moved_up_denominator": 816, "moved_up_pct": 47.0},
}


def test_summary_panel_renders(tmp_path):
    out = charts.mailer_summary_panel(SUMMARY, tmp_path / "s.png")
    assert out.exists() and out.stat().st_size > 5000


def test_panel_survives_a_withheld_stat(tmp_path):
    """A wave with no repeat responders has no ladder rate. The panel must
    print that it is not available, not crash and not print 0%."""
    thin = {**SUMMARY, "inside": {**SUMMARY["inside"], "repeat_n": 0,
                                  "moved_up_n": 0, "moved_up_denominator": 0,
                                  "moved_up_pct": None}}
    out = charts.mailer_summary_panel(thin, tmp_path / "t.png")
    assert out.exists()


def test_panel_blocks_share_one_band(tmp_path):
    """James (2026-08-24): the donut, the rate bars and Inside the Numbers
    must line up, not sit at three different heights."""
    fig, axes = charts._mailer_summary_fig(SUMMARY)
    tops = {name: round(ax.get_position().y1, 3) for name, ax in axes.items()}
    bottoms = {name: round(ax.get_position().y0, 3) for name, ax in axes.items()}
    assert max(tops.values()) - min(tops.values()) < 0.01, tops
    assert max(bottoms.values()) - min(bottoms.values()) < 0.01, bottoms


def test_donut_labels_are_readable_on_their_own_wedge():
    """The share label sits ON the wedge, so a navy label on the navy tier
    is invisible -- which is how TH-20's 20% vanished from the first render."""
    import matplotlib.colors as mcolors
    fig, axes = charts._mailer_summary_fig(SUMMARY)
    wedges = [p for p in axes["donut"].patches if hasattr(p, "theta1")]
    labels = [t for t in axes["donut"].texts if t.get_text().endswith("%")]
    assert len(labels) == len(wedges), (len(labels), len(wedges))
    for wedge, label in zip(wedges, labels):
        fill = mcolors.to_rgb(wedge.get_facecolor())
        text = mcolors.to_rgb(label.get_color())
        lum = lambda c: 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
        contrast = abs(lum(fill) - lum(text))
        assert contrast > 0.25, (
            f"{label.get_text()} on {mcolors.to_hex(fill)} has contrast {contrast:.2f}")


def test_panel_carries_the_ladder_key():
    """The donut's fills only mean something if the page says what the ramp
    is. The approved mockup carries a swatch per tier under the donut."""
    fig, _ = charts._mailer_summary_fig(SUMMARY)
    labels = {t.get_text() for t in fig.texts}
    assert "THE LADDER, LOW TO HIGH" in labels, sorted(labels)
    for tier in SUMMARY["tiers"]:
        assert tier in labels, f"{tier} missing from the ladder key"
    swatches = [p for p in fig.patches if hasattr(p, "get_width")]
    assert len(swatches) >= len(SUMMARY["tiers"]), len(swatches)


def test_panel_reports_mailed_that_carry_no_tier():
    """When part of the wave cannot be placed in a tier the slide has to say
    so -- the tier rows are then a subset, not the whole mailing."""
    partial = {**SUMMARY, "mailed": 24000, "mailed_assigned": 18735,
               "mailed_unassigned": 5265}
    fig, _ = charts._mailer_summary_fig(partial)
    blob = " ".join(t.get_text() for t in fig.texts)
    assert "5,265" in blob, blob


def test_section_headers_share_one_baseline():
    """James (2026-08-24): the rendered panel is 'not as sharp and aligned'
    as the approved HTML. The three column headers sit on one line there."""
    fig, _ = charts._mailer_summary_fig(SUMMARY)
    fig.canvas.draw()
    wanted = {"RESPONSE SHARE", "RESPONSE RATE BY TIER", "INSIDE THE NUMBERS"}
    found = {}
    for text in list(fig.texts) + [a.title for a in fig.axes]:
        if text.get_text() in wanted:
            found[text.get_text()] = round(text.get_window_extent().y0, 1)
    assert wanted <= set(found), sorted(found)
    spread = max(found.values()) - min(found.values())
    assert spread < 1.5, found


def test_panel_rules_off_the_headline_trio():
    """The HTML separates the trio from the three columns with a navy rule;
    without it the numbers float."""
    fig, _ = charts._mailer_summary_fig(SUMMARY)
    from matplotlib.lines import Line2D
    candidates = [a for a in list(fig.lines) + list(fig.artists)
                  if isinstance(a, Line2D)]
    rules = [ln for ln in candidates
             if abs(ln.get_ydata()[0] - ln.get_ydata()[-1]) < 1e-9]
    assert rules, "no horizontal rule under the headline trio"
    # and it must sit between the trio and the column headers
    y = rules[0].get_ydata()[0]
    assert 0.82 < y < 0.87, y
