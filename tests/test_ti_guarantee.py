# Ported from ARS v5 02-Scripts/tests/test_guarantee.py at a491b5c (James Gilmore); logic unchanged.
"""The 2:1 guarantee deferral tracker (issues #42/#43)."""
import pathlib
import sys

import openpyxl
import pytest

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent))

from ti import guarantee  # noqa: E402

# RPE: the reader ports in G7-02. These tests exercise code that ports later, stays in v5, or moved:
# v5 run.py's tracker checks live in ti/deferred_input.py here (tests/test_ti_deferred_input.py).
_LATER = {
    "test_deck_guarantee_surfaces": "tests/test_ti_economics_chapter.py (v5's whole-deck harness, test_deck_layout, is not ported)",
    "test_cleared_guarantee_reverts_to_workbook_economics": "tests/test_ti_economics_chapter.py (v5's whole-deck harness, test_deck_layout, is not ported)",
    "test_report_guarantee_block": "v5's text report, which is not migrated",
    "test_fetch_skips_lock_stubs": "v5's fetch tool, which stays in v5",
    "test_stale_tracker_warns_with_the_lag": "ti/deferred_input.review (tests/test_ti_deferred_input.py)",
    "test_missing_tracker_warns_instead_of_passing_silently":
        "ti/deferred_input.attach (tests/test_ti_deferred_input.py)",
}


def _later(fn):
    return pytest.mark.skip(reason=f"see {_LATER[fn.__name__]}")(fn)


def _tracker(path, rows, title="1441 First National Bank"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append([title])
    ws.append(["Program\nMonth", "ARS Revenue\nfor Month",
               "Velocity Charges\n for Mo", "Amount Paid by FNB Alask",
               "Amount Deferred for Mont", "= Amount Deferred\nRunnin"])
    from datetime import date
    for r in rows:
        ws.append([date(*r[0])] + list(r[1:]))
    wb.save(path)
    return path


GOOD = [
    ((2025, 8, 31), 0, 36841.0, 0, 36841.0, 36841.0),
    ((2025, 9, 30), 15508.5, 36765.4, 7754.25, 29011.15, 65852.15),
    ((2025, 10, 31), 13997.37, 36621.2, 6998.68, 29622.52, 95474.67),
]


def test_read_the_real_shape(tmp_path):
    p = _tracker(tmp_path / "1441 ARS Deferred expense tracking.xlsx", GOOD)
    warns = []
    m = guarantee.read(p, warns.append)
    assert m["gt_months_n"] == 3
    assert m["gt_latest_month"] == "2025-10"
    assert m["gt_deferred_balance"] == 95474.67
    assert m["gt_paid_ltd"] == pytest.approx(14752.93)
    assert m["gt_charges_ltd"] == pytest.approx(110227.6)
    assert m["gt_revenue_ltd"] == pytest.approx(29505.87)
    assert m["gt_state"] == "in-guarantee"
    assert m["gt_ratio_latest"] == pytest.approx(0.38, abs=0.01)
    assert not warns                     # the real math ties clean


def test_arithmetic_failsafes_warn(tmp_path):
    bad = [((2025, 8, 31), 10000.0, 30000.0, 4000.0, 25000.0, 26000.0)]
    # paid+deferred=29000 != charges 30000; running 26000 != 25000;
    # paid*2=8000 != revenue 10000
    p = _tracker(tmp_path / "x Deferred.xlsx", bad)
    warns = []
    guarantee.read(p, warns.append)
    joined = " ".join(warns)
    assert "!= charges" in joined
    assert "does not tie" in joined
    assert "half-of-revenue" in joined


def test_states(tmp_path):
    draw = GOOD + [((2025, 11, 30), 80000.0, 36000.0, 40000.0,
                    -4000.0, 91474.67)]
    p = _tracker(tmp_path / "d Deferred.xlsx", draw)
    m = guarantee.read(p, lambda _m: None)
    assert m["gt_state"] == "drawing-down"
    clear = [((2025, 8, 31), 80000.0, 36000.0, 36000.0, 0.0, 0.0)]
    p2 = _tracker(tmp_path / "c Deferred.xlsx", clear)
    m2 = guarantee.read(p2, lambda _m: None)
    assert m2["gt_state"] == "clear"


def test_find_tracker_canonical_first(tmp_path):
    a = tmp_path / "ARS" / "2026-08" / "1441"
    a.mkdir(parents=True)
    f = a / "1441 FNB ARS Deferred expense tracking.xlsx"
    f.write_text("x")
    assert guarantee.find_tracker(tmp_path, "1441", "2026-08") == f
    assert guarantee.find_tracker(tmp_path, "9999", "2026-08") is None


def test_empty_tracker_is_ignored_with_warning(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.append(["just a title"])
    p = tmp_path / "e Deferred.xlsx"
    wb.save(p)
    warns = []
    m = guarantee.read(p, warns.append)
    assert m == {}
    assert any("workbook math stands" in w for w in warns)


@_later
def test_deck_guarantee_surfaces(tmp_path):
    """Hero + P&L switch to guarantee math; the guarantee slide renders."""
    sys.path.insert(0, str(HERE))
    from test_ti_deck_layout import _build_fixture, _wave3_metrics
    mm = _wave3_metrics()
    mm.update({"wb_profit_ltd": -100078, "wb_revenue_ltd": 337207,
               "wb_costs_ltd": -437285,
               "wb_waves": [["Jan26", 5661, 3.0, 2942, 170]],
               "gt_source": "1441 tracker.xlsx",
               "gt_months": [["2026-06", 43408.43, 36367.8, 21704.21,
                              14663.59, 259697.23],
                             ["2026-07", 54806.15, 36416.8, 27403.07,
                              9013.73, 268710.96]],
               "gt_months_n": 12, "gt_latest_month": "2026-07",
               "gt_revenue_ltd": 337207.0, "gt_charges_ltd": 437285.0,
               "gt_paid_ltd": 168603.5, "gt_deferred_balance": 268710.96,
               "gt_state": "in-guarantee", "gt_ratio_latest": 1.5})
    d = _build_fixture(mm)
    text = d.storyboard.read_text(encoding="utf-8")
    rendered = text.split("Not rendered")[0]
    # the hero NEVER reads as a loss when the tracker exists (issue #32)
    assert "short of its fees" not in rendered
    assert "The 2:1 guarantee holds" in rendered
    assert "deferred" in rendered
    gaps = text.partition("Not rendered")[2]
    assert "The 2:1 guarantee" not in gaps


@_later
def test_report_guarantee_block():
    from ti.monthly_analysis.report import report
    from types import SimpleNamespace
    m = {"gt_source": "t.xlsx", "gt_state": "in-guarantee",
         "gt_latest_month": "2026-07", "gt_revenue_ltd": 337207.0,
         "gt_charges_ltd": 437285.0, "gt_paid_ltd": 168603.5,
         "gt_deferred_balance": 268710.96, "gt_ratio_latest": 1.5,
         "gt_months": [["2026-07", 54806.15, 36416.8, 27403.07,
                        9013.73, 268710.96]]}
    r = SimpleNamespace(client_id="1441", client_name="X", period="2026-08",
                        data_month="2026-07", duration_s=1.0, metrics=m,
                        warnings=[], errors=[], outputs={})
    text = report(r)
    assert "2:1 GUARANTEE" in text
    assert "$268,711" in text
    assert "forgiven at contract end" in text


def test_lock_stub_never_wins_and_bad_zip_is_friendly(tmp_path):
    """The work-PC failure (issue #43): Excel's ~$ lock stub matched the
    glob, sorted last, and read as BadZipFile. Stubs are now invisible to
    the finder, and a truly unreadable file degrades to workbook math
    with a plain warning."""
    a = tmp_path / "ARS" / "2026-08" / "1441"
    a.mkdir(parents=True)
    real = _tracker(a / "1441 ARS Deferred expense tracking.xlsx", GOOD)
    (a / "~$1441 ARS Deferred expense tracking.xlsx").write_bytes(b"\x00stub")
    assert guarantee.find_tracker(tmp_path, "1441", "2026-08") == real
    warns = []
    m = guarantee.read(a / "~$1441 ARS Deferred expense tracking.xlsx",
                       warns.append)
    assert m == {}
    assert any("Workbook math stands" in w for w in warns)


@_later
def test_fetch_skips_lock_stubs(tmp_path, capsys):
    sys.path.insert(0, str(HERE.parent / "tools"))
    import fetch_data
    root = tmp_path / "Rewards"
    sub = root / "1441 FNB Alaska" / "ARS deferred billing"
    sub.mkdir(parents=True)
    (sub / "1441 ARS Deferred expense tracking.xlsx").write_text("real")
    (sub / "~$1441 ARS Deferred expense tracking.xlsx").write_text("stub")
    dest = tmp_path / "01-Data"
    fetch_data.main(["2026-08", "--source", str(tmp_path / "no-dumps"),
                     "--deferred", str(root), "--dest", str(dest)])
    copied = [p.name for p in (dest / "ARS" / "2026-08" / "1441").iterdir()]
    assert copied == ["1441 ARS Deferred expense tracking.xlsx"]


@_later
def test_cleared_guarantee_reverts_to_workbook_economics(tmp_path):
    """James's exit-scenario (2026-08-22): once they are no longer in the
    2:1, the tracker stops updating and the workbook is the authority
    again. A cleared balance must NOT keep superseding the hero/P&L."""
    sys.path.insert(0, str(HERE))
    from test_ti_deck_layout import _build_fixture, _wave3_metrics
    mm = _wave3_metrics()
    mm.update({"wb_profit_ltd": 687635, "wb_revenue_ltd": 989840,
               "wb_costs_ltd": -302204,
               "wb_waves": [["Jan26", 5661, 3.0, 2942, 170]],
               "gt_source": "t.xlsx", "gt_months_n": 14,
               "gt_months": [["2026-07", 80000.0, 36000.0, 36000.0,
                              0.0, 0.0]],
               "gt_latest_month": "2026-07",
               "gt_revenue_ltd": 500000.0, "gt_charges_ltd": 480000.0,
               "gt_paid_ltd": 480000.0, "gt_deferred_balance": 0.0,
               "gt_state": "clear"})
    d = _build_fixture(mm)
    text = d.storyboard.read_text(encoding="utf-8")
    rendered = text.split("Not rendered")[0]
    # hero/P&L on WORKBOOK numbers again
    assert "The 2:1 guarantee holds" not in rendered
    assert "program profit" in rendered
    # the guarantee slide still renders the history (clear status)
    assert "The guarantee is clear" in rendered


@_later
def test_stale_tracker_warns_with_the_lag(tmp_path, monkeypatch):
    from ti import guarantee as _g
    import ti.monthly_analysis.run as _r
    # unit-check the lag arithmetic used in run.py
    dm, lm = "2026-08", "2026-02"
    lag = (int(dm[:4]) - int(lm[:4])) * 12 + int(dm[5:7]) - int(lm[5:7])
    assert lag == 6


def test_locked_tracker_degrades_with_a_plain_message(tmp_path, monkeypatch):
    """1615 (issue #19 log): the tracker was open in Excel and the run
    printed a raw PermissionError. Locked now reads like the workbook's
    locked case -- close it and re-run, workbook math stands."""
    import openpyxl as _o
    p = _tracker(tmp_path / "x Deferred.xlsx", GOOD)
    def _locked(*a, **k):
        raise PermissionError(13, "Permission denied", str(p))
    monkeypatch.setattr(_o, "load_workbook", _locked)
    warns = []
    m = guarantee.read(p, warns.append)
    assert m == {}
    assert any("locked (open in Excel" in w for w in warns)


@_later
def test_missing_tracker_warns_instead_of_passing_silently(tmp_path):
    """A missing tracker used to emit nothing: the run exited 0 and the deck
    built guarantee figures from billed workbook numbers instead of guarantee
    math. The workbook's own missing case has always warned; so must this."""
    from importlib import import_module
    _r = import_module("ars.monthly_analysis.run")
    warns = []
    m = _r._load_tracker(tmp_path, "1441", "2026-08", warns.append)
    assert m == {}
    assert any("guarantee" in w.lower() for w in warns), warns
    assert any("--deferred" in w for w in warns), warns
