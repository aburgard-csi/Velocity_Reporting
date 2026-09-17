"""No trend line is drawn over a partial month (Aaron, 2026-09-17).

The CashPlease "Loan Volume by Month" chart hatched the part-month bar but ran the principal
line into it, where it read as a collapse ($9K in August to about $4K for Sep 1-11).
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
from matplotlib.axes import Axes

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "build", "cashplease_pipeline"))


def test_cashplease_principal_line_stops_at_the_last_complete_month(tmp_path, monkeypatch):
    import cp_charts
    drawn = []
    real = Axes.plot

    def spy(self, *a, **k):
        if k.get("label") == "Principal advanced":
            drawn.append(list(a[1]))
        return real(self, *a, **k)

    monkeypatch.setattr(Axes, "plot", spy)
    months = ["2026-06", "2026-07", "2026-08"]
    cp_charts.monthly_volume_chart(str(tmp_path / "v.png"), months, [14, 15, 16], [9000, 8000, 9100],
                                   partial={"period_month": "2026-09", "loans": 6,
                                            "principal": 3600, "through": "Sep 11"})
    assert drawn == [[9000, 8000, 9100]]


def test_the_ics_section_intro_line_skips_a_partial_month():
    src = open(os.path.join(REPO, "build", "ics_pipeline", "ics_charts_gen.py"), encoding="utf-8").read()
    body = src.split("def c_perf_intro", 1)[1].split("\ndef ", 1)[0]
    assert "partial_last" in body and "cum[:-1]" in body
