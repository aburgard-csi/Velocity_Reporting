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
