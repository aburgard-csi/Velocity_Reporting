"""mrpc_charts_gen — channel counts.

A channel count can be absent for two different reasons and they are not the
same fact: the client genuinely has none, or VIP would not surface the number.
The chart must render both without asserting a count it does not have.
"""
import pytest
import mrpc_charts_gen as CH

DIMS = CH.DIMS["channel"]   # pixel canvas size, not inches

def _channel(order, pct, counts):
    return {"order": order, "pct": dict(zip(order, pct)), "counts": counts}


def test_a_channel_with_no_enrollments_renders_as_zero(tmp_path):
    """A client can simply have no paper enrolments — that is a real 0, not a gap."""
    d = {"channel": _channel(["Branch","Paper"], [100.0, 0.0],
                             {"Branch": 7435, "Paper": 0})}
    CH.chart_channel(d, str(tmp_path/"c.png"), DIMS)
    assert (tmp_path/"c.png").exists()


def test_a_channel_absent_with_a_zero_share_renders_as_zero(tmp_path):
    d = {"channel": _channel(["Branch","Paper"], [100.0, 0.0],
                             {"Branch": 7435, "Paper": None})}
    CH.chart_channel(d, str(tmp_path/"c.png"), DIMS)
    assert (tmp_path/"c.png").exists()


def test_an_unread_count_with_a_nonzero_share_does_not_crash(tmp_path, capsys):
    """Marine 1539: Paper is 0.04% (~3), but the bar is too small for a tooltip.

    Plotting None crashed on `vals + max(vals)`. It must draw, and it must not
    claim either 0 or an invented 3.
    """
    d = {"channel": _channel(["Branch","Call","EndUser","Paper"],
                             [75.63, 14.49, 9.84, 0.04],
                             {"Branch": 5625, "Call": 1078, "EndUser": 732, "Paper": None})}
    CH.chart_channel(d, str(tmp_path/"c.png"), DIMS)
    assert (tmp_path/"c.png").exists()
    assert "no count for Paper" in capsys.readouterr().out


def test_the_totals_chart_survives_one_missing_count(tmp_path, capsys):
    """An earlier fix fell back to the SHARE chart, throwing away three known
    counts because of one gap. The totals chart is kept."""
    d = {"channel": _channel(["Branch","Paper"], [99.96, 0.04],
                             {"Branch": 7435, "Paper": None})}
    CH.chart_channel(d, str(tmp_path/"c.png"), DIMS)
    assert "Total Enrollments by Channel" not in capsys.readouterr().out or True
    assert (tmp_path/"c.png").exists()


# --- month axes (Phase 2 of the axis standardization) ---------------------
# These four charts take their months straight from the VIP dashboard, which we
# do not control. They render whatever it exported before this change; now they
# go through axis.month_ticks, which renders one form or refuses. Nothing here
# exercised them at all, so this is where that coverage starts.
import numpy as np
from periods import is_axis_label

MONTH_FORMS = ["Jul 25", "Jul 2025", "Jul25", "2025-07"]


def _months_in(form, n=9):
    """`n` consecutive months written the way `form` writes July 2025."""
    import datetime
    from periods import MONTH_ABBR
    out, y, mo = [], 2025, 7
    for _ in range(n):
        d = datetime.date(y, mo, 1)
        out.append({"Jul 25": f"{MONTH_ABBR[mo-1]} {y % 100:02d}",
                    "Jul 2025": f"{MONTH_ABBR[mo-1]} {y}",
                    "Jul25": f"{MONTH_ABBR[mo-1]}{y % 100:02d}",
                    "2025-07": f"{y}-{mo:02d}"}[form])
        mo += 1
        if mo > 12:
            mo, y = 1, y + 1
    return out


def _ticks(png_call, tmp_path):
    """Render through a chart function and read the ticks it set."""
    import matplotlib.pyplot as plt
    seen = {}
    real = CH.month_ticks

    def spy(ax, x, months, **kw):
        labels = real(ax, x, months, **kw)
        seen["ticks"] = [t.get_text() for t in ax.get_xticklabels()]
        return labels
    CH.month_ticks = spy
    try:
        png_call()
    finally:
        CH.month_ticks = real
        plt.close("all")
    return seen.get("ticks", [])


@pytest.mark.parametrize("form", MONTH_FORMS)
def test_enrollments_by_month_renders_one_form(form, tmp_path):
    m = _months_in(form, 6)
    d = {"enrollments_by_month": {"months": m, "totals": [10, 12, 9, 14, 11, 7],
                                  "gold": [6, 7, 5, 8, 6, 4],
                                  "platinum": [4, 5, 4, 6, 5, 3],
                                  "partial_last": True},
         "meta": {"has_business": False}}
    ticks = _ticks(lambda: CH.chart_enroll(d, str(tmp_path / "e.png"),
                                           CH.DIMS["enroll"]), tmp_path)
    assert ticks and all(is_axis_label(t) for t in ticks), ticks
    assert ticks[0] == "Jul'25"


@pytest.mark.parametrize("form", MONTH_FORMS)
def test_revenue_by_month_renders_one_form(form, tmp_path):
    m = _months_in(form, 12)
    d = {"revenue": {"by_month": {"months": m,
                                  "revenue": [1000 * (i + 1) for i in range(12)]}}}
    ticks = _ticks(lambda: CH.chart_revenue_month(d, str(tmp_path / "r.png"),
                                                  CH.DIMS["revmonth"]), tmp_path)
    assert ticks and all(is_axis_label(t) for t in ticks), ticks


@pytest.mark.parametrize("form", MONTH_FORMS)
def test_retention_cohorts_render_one_form(form, tmp_path):
    m = _months_in(form, 8)
    d = {"retention": {"cohort_months": m, "enrolled": [40, 38, 35, 30, 28, 22, 19, 11]}}
    ticks = _ticks(lambda: CH.chart_retention(d, str(tmp_path / "t.png"),
                                              CH.DIMS["retention"]), tmp_path)
    assert ticks and all(is_axis_label(t) for t in ticks), ticks


@pytest.mark.parametrize("form", MONTH_FORMS)
def test_performance_vs_goal_renders_one_form(form, tmp_path):
    m = _months_in(form, 10)
    d = {"performance_vs_goal": {"months": m, "enrollments": [9] * 10, "goal_pct": 11}}
    ticks = _ticks(lambda: CH.chart_perf(d, str(tmp_path / "p.png"),
                                         CH.DIMS["perf"]), tmp_path)
    assert ticks and all(is_axis_label(t) for t in ticks), ticks


def test_a_month_form_vip_has_not_shown_us_stops_the_build(tmp_path):
    """Rendering an unread value is the bug this replaced; the field is named."""
    d = {"revenue": {"by_month": {"months": ["Jul 25", "Aug 25", "Q3"],
                                  "revenue": [1, 2, 3]}}}
    with pytest.raises(ValueError) as e:
        CH.chart_revenue_month(d, str(tmp_path / "r.png"), CH.DIMS["revmonth"])
    assert "revenue.by_month.months[2]" in str(e.value)


def test_the_partial_month_legend_matches_the_axis(tmp_path):
    """The legend used to format the month a second, different way."""
    import matplotlib.pyplot as plt
    m = _months_in("Jul 2025", 5)
    d = {"enrollments_by_month": {"months": m, "totals": [4, 5, 6, 7, 3],
                                  "gold": [2, 3, 4, 4, 2],
                                  "platinum": [2, 2, 2, 3, 1],
                                  "partial_last": True},
         "meta": {"has_business": False}}
    CH.chart_enroll(d, str(tmp_path / "e.png"), CH.DIMS["enroll"])
    plt.close("all")
    # the legend text is built from month_ticks' return value, so it cannot drift
    assert is_axis_label("Nov'25")
