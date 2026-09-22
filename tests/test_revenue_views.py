"""The two revenue views taken from James's deck (his slides 5 and 6), 2026-09-21.

Slide 5 is each mailing's month-by-month build; slide 6 is where the newest month's revenue
came from. Both read the workbook's 'All Months Rollup MM' blocks, so the tests build those
blocks synthetically — round numbers, invented mailing months, no client.
"""
import datetime
import os

import pytest

import combined_insights as CI
import insight_charts as IC


def sheet(blocks, months):
    """Rows shaped like the rollup sheet: a label row carrying the month headers, then a
    'Total Incremental Income' row of figures. A month a mailing never booked is left blank,
    which is what the real sheet does and what the build has to respect."""
    hdr = [None, None, None] + [datetime.datetime(y, m, 1) for y, m in months]
    rows = []
    for label, vals in blocks:
        rows.append([None, label] + [None] + hdr[3:])
        # values sit under their month headers, at the same column indices
        rows.append([None, 1, "Total Incremental Income"] + list(vals))
    return rows


MONTHS = [(2026, 1), (2026, 2), (2026, 3), (2026, 4)]


def wave_of(rows, label):
    return next(w for w in rows if w["m"] == label)


@pytest.fixture
def wr(tmp_path, monkeypatch):
    """wave_revenue() over a synthetic sheet, without an xlsx on disk."""
    rows = sheet([("Summary", [300.0, 400.0, 500.0, 600.0]),
                  ("January 2026 Mailing", [100.0, 150.0, 200.0, 250.0]),
                  ("March 2026 Mailing", [None, None, 300.0, 350.0])], MONTHS)
    path = tmp_path / "wb.xlsx"
    path.write_text("not really a workbook", encoding="utf-8")

    class FakeWB:
        sheetnames = [CI.ROLLUP_SHEET]

        def __getitem__(self, _name):
            class WS:
                @staticmethod
                def iter_rows(values_only=True):
                    return iter(rows)
            return WS()

        def close(self):
            pass

    monkeypatch.setattr(CI, "openpyxl", type("M", (), {"load_workbook": staticmethod(
        lambda *a, **k: FakeWB())}), raising=False)
    import sys
    monkeypatch.setitem(sys.modules, "openpyxl",
                        type("M", (), {"load_workbook": staticmethod(lambda *a, **k: FakeWB())}))
    return CI.wave_revenue(str(path))


def test_the_build_is_measured_in_months_since_that_mailing(wr):
    jan = wave_of(wr["waves"], "Jan 2026")
    assert [p[0] for p in jan["build"]] == [0, 1, 2, 3]
    assert [p[2] for p in jan["build"]] == [100.0, 250.0, 450.0, 700.0]   # cumulative


def test_a_month_the_workbook_never_booked_leaves_a_gap_not_a_shifted_curve(wr):
    """March's mailing books nothing until its own month. Read by position, its first point
    would sit at age 0 of January — two mailings' curves would then be compared at ages
    neither of them is at."""
    mar = wave_of(wr["waves"], "Mar 2026")
    assert [p[0] for p in mar["build"]] == [0, 1]
    assert mar["build"][0][2] == 300.0


def test_this_months_split_is_the_newest_month_any_mailing_booked(wr):
    assert wr["latest_month"] == "2026-04"
    assert wr["latest_month_label"] == "Apr 2026"
    assert wr["by_mailing_latest"] == [("Mar 2026", 350.0, 2), ("Jan 2026", 250.0, 4)]
    assert wr["latest_total"] == 600.0


def test_the_split_is_reconciled_against_the_sheets_own_summary(wr):
    """The mailing rows and the Summary block should agree; the slide prints the gap when
    they do not, so the figure has to be carried here."""
    assert wr["summary_latest"] == 600.0
    assert wr["latest_total"] == wr["summary_latest"]


def test_a_mailing_with_no_booked_month_is_absent_from_the_split_not_zero(wr):
    assert all(v > 0 for _m, v, _n in wr["by_mailing_latest"])
    assert len(wr["by_mailing_latest"]) <= len(wr["waves"])


def test_the_build_chart_renders(tmp_path):
    waves = [{"m": "Jan 2025", "key": "2025-01", "revenue": 120000, "months": 12,
              "per_month": 10000, "build": [[i, 10000, 10000 * (i + 1)] for i in range(12)]},
             {"m": "Jul 2026", "key": "2026-07", "revenue": 60000, "months": 2,
              "per_month": 30000, "build": [[0, 30000, 30000], [1, 30000, 60000]]}]
    png = str(tmp_path / "build.png")
    IC.wave_build_chart(png, waves, 12.3, 4.0)
    assert os.path.getsize(png) > 5000


def test_the_month_split_chart_renders(tmp_path):
    png = str(tmp_path / "split.png")
    IC.month_split_chart(png, [("Mar 2026", 350.0, 2), ("Jan 2026", 250.0, 14)], 12.3, 3.5)
    assert os.path.getsize(png) > 5000


def test_both_slides_are_in_the_opt_in_set():
    import combined_insight_slides as CIS
    import inspect
    src = inspect.getsource(CIS.add_insight_slides)
    assert "wave_build_slide(prs, ci, ctx)" in src
    assert "month_split_slide(prs, ci, ctx)" in src
