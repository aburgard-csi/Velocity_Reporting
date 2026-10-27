# Ported from ARS v5 02-Scripts/tests/test_workbook.py at a491b5c (James Gilmore); logic unchanged.
"""ARS Workbook reader (wb_*) -- structures from the real 1585 workbook.

    python -m pytest tests/test_workbook.py -q
"""
import datetime
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti import workbook                                           # noqa: E402

import pytest  # noqa: E402

# RPE: the reader ports in G7-01; these tests exercise code that ports later (or is not migrated).
# Each is skipped under the stage that brings its code, so it switches back on when that lands.
_LATER = {
    "test_pnl_slide_renders_from_wb_keys": "tests/test_ti_economics_chapter.py (v5's whole-deck harness, test_deck_layout, is not ported)",
    "test_lift_matrix_slide_renders_on_the_main_path": "tests/test_ti_economics_chapter.py (v5's whole-deck harness, test_deck_layout, is not ported)",
    "test_lift_matrix_slide_skips_and_names_the_workbook": "tests/test_ti_economics_chapter.py (v5's whole-deck harness, test_deck_layout, is not ported)",
    "test_revenue_frames_bridge_renders_and_labels_both_frames": "G9-07 (shared campaign slides)",
    "test_revenue_frames_skips_without_did": "G9-07 (shared campaign slides)",
    "test_hero_declines_when_a_workbook_was_found_but_gave_no_profit": "G9-07 (shared campaign slides)",
    "test_hero_keeps_the_odd_frame_when_the_client_has_no_workbook": "G9-07 (shared campaign slides)",
    "test_value_survives_an_empty_eligible_base": "G8-03 (value)",
    "test_report_revenue_frames_block": "v5's text report, which is not migrated",
}


def _later(fn):
    return pytest.mark.skip(reason=f"see {_LATER[fn.__name__]}")(fn)


def _make_wb(path, stub=False, variants=False, rollup=False, lift=False):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Executive Financials MM"
    mark = "January 2007" if stub else "July 2026 Data"
    ws.append(["", "Account Revenue Solution"])
    ws.append(["", mark])
    ws.append(["", "", "Months in the Program:", 36])
    ws.append(["", "", "Mailings to date:", 18])
    ws.append(["", 1, "Total Incremental Revenue", 40729, 0,
               2810 if rollup else 989840, 0])
    ws.append(["", 6, "Total Costs", -9099, 0, -302204, 0])
    ws.append(["", 7, "Incremental Profit", 31630, 0, 687635, 0])

    ws = wb.create_sheet("Actuals MM")
    ws.append(["", mark])
    ws.append(["", "Actual Monthly Results", "",
               datetime.date(2025, 8, 1), datetime.date(2025, 9, 1)])
    ws.append(["", 1, "Total Marginal Revenue", 100, 200])
    ws.append(["", 6, "Total Cost", -50, -60])
    ws.append(["", 7, "Incremental Profit", 50, 140])
    ws.append(["", "", "Interchange Rate", 0.0065, 0.0065])
    ws.append(["", "", "NSF Fee", 27, 28])   # fee moved mid-program

    ws = wb.create_sheet("Mailing Jan 2026")
    ws.append(["", mark])
    ws.append(["Nonuser (Zero swipes in window)", "", 2599])
    ws.append(["", "Swipes: 5+", 74])
    ws.append(["", "Response", 0.03])
    ws.append(["", "Total Nonuser Revenue:", 842, 900])
    ws.append(["", "Cumulative Profit:", 842, 1742])
    ws.append(["Threshold (1-20 swipes)", "", 3062])
    ws.append(["", "Swipes: 10+", 109])
    ws.append(["", "Response", 0.07])
    ws.append(["", "Mailed: Goal of 15 swipes", 648])
    ws.append(["", "Swipes: 15+", 40])
    ws.append(["", "Cumulative Profit:", 500, 1200])
    # REAL shape (CoastHills Apr 2025): the monthly series runs left to
    # right, then Annualized and To Date sit under LABELLED columns past
    # column J -- exactly where the old max_col=10 window stopped looking.
    ws.append(["Financial Summary"] + [None] * 11 + ["Annualized", "To Date"])
    ws.append(["", "Total Revenue:", 500, 400, 300, 200, 150, 120, 100, 90,
               80, 70, 5000, 2010])

    if variants:
        # Feb-2026 shape: Annualized, but NO To Date column anywhere.
        ws = wb.create_sheet("Mailing Mar 2026")
        ws.append(["", mark])
        ws.append(["Nonuser (Zero swipes in window)", "", 1000])
        ws.append(["", "Swipes: 5+", 20])
        ws.append(["Threshold (1-20 swipes)", "", 2000])
        ws.append(["", "Swipes: 10+", 30])
        ws.append(["Financial Summary"] + [None] * 11 + ["Annualized"])
        ws.append(["", "Total Revenue:", 300, 250, 200, 150, 100,
                   None, None, None, None, None, 4800])

        # Apr-2026 shape: a duplicate Swipes panel ABOVE the Nonuser anchor.
        ws = wb.create_sheet("Mailing May 2026")
        ws.append(["", mark])
        ws.append(["", "", "Swipes: 5+", 40, 1500, 0.0267])
        ws.append(["", "", "Swipes: 10+", 60, 2500, 0.024])
        ws.append(["Nonuser (Zero swipes in window)", "", 1500])
        ws.append(["", "Swipes: 5+", 40])
        ws.append(["Threshold (1-20 swipes)", "", 2500])
        ws.append(["", "Swipes: 10+", 60])
        ws.append(["Financial Summary"] + [None] * 11
                  + ["Annualized", "To Date"])
        ws.append(["", "Total Revenue:", 100, 90, 80, None, None, None,
                   None, None, None, None, 1000, 270])

    if rollup:
        # Second wave, so the rollup has two sections to reconcile against.
        ws = wb.create_sheet("Mailing Feb 2026")
        ws.append(["", mark])
        ws.append(["Nonuser (Zero swipes in window)", "", 1200])
        ws.append(["", "Swipes: 5+", 30])
        ws.append(["Threshold (1-20 swipes)", "", 1800])
        ws.append(["", "Swipes: 10+", 45])
        ws.append(["Financial Summary"] + [None] * 11
                  + ["Annualized", "To Date"])
        ws.append(["", "Total Revenue:", 500, 300, None, None, None, None,
                   None, None, None, None, 3200, 800])

        # REAL shape (CoastHills): a Summary section, then one section per
        # wave, each with its own month header row and a Total Incremental
        # Income row. Wave rows sum to Summary; Summary sums to the P&L.
        months = [datetime.date(2026, 1, 1), datetime.date(2026, 2, 1),
                  datetime.date(2026, 3, 1)]
        ws = wb.create_sheet("All Months Rollup MM")
        ws.append(["", "Account Revenue Solution"])
        ws.append(["", mark])
        ws.append([])
        ws.append(["", "Summary", "", ""] + months)
        ws.append(["", 1, "Total Incremental Income", "", 1000, 1100, 710])
        ws.append(["", 2, "Total Incremental Expense", "", 0, 0, 0])
        ws.append(["", 3, "Number of Responders", "", 500, 300, 0])
        ws.append([])
        ws.append(["", "January 2026 Mailing", "", ""] + months)
        ws.append(["", "Incremental Revenue"])
        ws.append(["", 1, "Total Incremental Income", "", 1000, 600, 410])
        ws.append(["", 2, "Total Incremental Expense", "", 0, 0, 0])
        ws.append(["", 3, "Number of Responders", "", 500, 0, 0])
        ws.append([])
        ws.append(["", "February 2026 Mailing", "", ""] + months)
        ws.append(["", "Incremental Revenue"])
        ws.append(["", 1, "Total Incremental Income", "", None, 500, 300])
        ws.append(["", 2, "Total Incremental Expense", "", None, 0, 0])
        ws.append(["", 3, "Number of Responders", "", None, 300, 0])

    if lift:
        # REAL shape (from the pre-v5 extractor build/ars_pipeline/extract_lift.py,
        # retired 2026-09-10, written against live workbooks): a Baseline Segment anchor in column B with the
        # swipe bands across C..H, the window dates above it, and the data
        # month in B6. "stale" pushes the data month past End Date.
        ws = wb.create_sheet("Lift Matrix MM")
        ws.append(["", "Account Revenue Solution"])
        ws.append([])
        ws.append(["", "Revenue per account per month ($)"])
        ws.append(["", "Start Date", datetime.datetime(2025, 8, 1)])
        ws.append(["", "End Date", datetime.datetime(2026, 7, 1)])
        ws.append(["", "October 2026" if lift == "stale" else "July 2026"])
        ws.append([])
        ws.append(["", "Baseline Segment", "1-5", "6-10", "11-15",
                   "16-20", "21-25", "26 Plus"])
        for seg, base in (("Non-user", 4.10), ("1-5", 6.40), ("6-10", 9.20),
                          ("11-15", 12.80), ("16-20", 17.30),
                          ("21-25", 21.90)):
            ws.append(["", seg] + [round(base + 2.1 * i, 2)
                                   for i in range(6)])

    wb.save(path)
    return path


def test_reads_pnl_series_waves_and_economics(tmp_path):
    path = _make_wb(tmp_path / "1585-Workbook_v2.xlsx")
    warnings = []
    m = workbook.read(path, warnings.append)
    assert m["wb_profit_ltd"] == 687635
    assert m["wb_revenue_ltd"] == 989840
    assert m["wb_costs_ltd"] == -302204
    assert m["wb_months_in_program"] == 36 and m["wb_mailings_to_date"] == 18
    assert m["wb_monthly"][0] == ["2025-08", 100, -50, 50]
    assert m["wb_ic_rate"] == 0.0065
    assert m["wb_nsf_fee"] == 28.0          # LAST value: the fee that is true TODAY
    (tag, mailed, resp, cum, goal_met), = m["wb_waves"]
    assert tag == "Jan26" and mailed == 2599 + 3062
    assert goal_met == 74 + 109 + 40        # EVERY swipe-goal tier (the 639 lesson)
    assert m["wb_wave_tiers"]["Jan26"] == {"NU5": 74, "TH10": 109, "TH15": 40}
    assert resp == round(100 * 223 / 5661, 1)   # computed across all tiers
    assert cum == 2010                      # the To Date COLUMN, found by its
                                            # header -- never the last numeric
                                            # that happens to be in range
    assert not warnings


def test_template_stub_declines_loudly(tmp_path):
    path = _make_wb(tmp_path / "stub.xlsx", stub=True)
    warnings = []
    m = workbook.read(path, warnings.append)
    assert not any(k.startswith("wb_") and k != "wb_source" for k in m)
    assert warnings and "template" in warnings[0]


def test_find_workbook_canonical_first(tmp_path):
    a = tmp_path / "2026-08" / "1585"
    a.mkdir(parents=True)
    f = a / "1585-2026.08-CLIENT-Workbook_v2_1_0.xlsx"
    f.write_text("x")
    assert workbook.find_workbook(tmp_path, "1585", "2026-08") == f
    assert workbook.find_workbook(tmp_path, "9999", "2026-08") is None


@_later
def test_pnl_slide_renders_from_wb_keys():
    sys.path.insert(0, str(HERE))
    from test_ti_deck_layout import _build_fixture, _wave3_metrics
    mm = _wave3_metrics()
    mm.update({"wb_profit_ltd": 687635, "wb_revenue_ltd": 989840,
               "wb_costs_ltd": -302204, "wb_profit_month": 31630,
               "wb_revenue_month": 40729, "wb_months_in_program": 36,
               "wb_mailings_to_date": 18, "wb_source": "wbk.xlsx",
               # REAL shape: 5 elements (goal_met_responders appended by
               # the tier-reconciliation work). A 4-element fixture let the
               # deck's 4-value unpack pass tests while real data crashed.
               "wb_waves": [["Jan26", 5661, 3.0, 2942, 170],
                            ["Mar26", 5300, 4.1, 2100, 217]]})
    d = _build_fixture(mm)
    text = d.storyboard.read_text(encoding="utf-8")
    main, _, appendix = text.partition("— Appendix")
    # Supporting Financials (slot 2 of James's 12-slide cut, #62): the
    # P&L slide is MAIN again; it must render, never in the gaps
    assert "Every fee dollar has returned $3.28 in revenue" in main
    assert "Program P&L" not in text.partition("Not rendered")[2]
    # hero upgrades to the workbook number, on the main path
    assert "program profit" in main


@_later
def test_revenue_frames_bridge_renders_and_labels_both_frames():
    """Issue #40: booked (workbook) and incremental (DiD) never tie by
    design -- the deck must carry the bridge slide and frame the P&L as
    'program revenue', never 'incremental'."""
    sys.path.insert(0, str(HERE))
    from test_ti_deck_layout import _build_fixture, _wave3_metrics
    mm = _wave3_metrics()
    mm.update({"wb_profit_ltd": 687635, "wb_revenue_ltd": 989840,
               "wb_costs_ltd": -302204, "wb_profit_month": 31630,
               "wb_revenue_month": 40729, "wb_months_in_program": 36,
               "wb_mailings_to_date": 18, "wb_source": "wbk.xlsx",
               "wb_waves": [["Jan26", 5661, 3.0, 2942, 170]]})
    d = _build_fixture(mm)
    text = d.storyboard.read_text(encoding="utf-8")
    rendered = text.split("Not rendered")[0]
    assert "Booked revenue and the DiD estimate answer different questions" \
        in rendered
    assert "Revenue frames" not in text.partition("Not rendered")[2]
    # the P&L never says 'incremental' anywhere on the deck path
    assert "incremental" not in rendered.lower()


@_later
def test_revenue_frames_skips_without_did():
    sys.path.insert(0, str(HERE))
    from test_ti_deck_layout import _build_fixture, _wave3_metrics
    mm = _wave3_metrics()
    mm.pop("ba_lift_net", None)
    mm.update({"wb_profit_ltd": 687635, "wb_revenue_ltd": 989840,
               "wb_costs_ltd": -302204,
               "wb_waves": [["Jan26", 5661, 3.0, 2942, 170]]})
    d = _build_fixture(mm)
    text = d.storyboard.read_text(encoding="utf-8")
    gaps = text.partition("Not rendered")[2]
    assert "Revenue frames" in gaps


@_later
def test_report_revenue_frames_block():
    """The written report carries the same bridge, in the same frames."""
    from ti.monthly_analysis.report import report
    from types import SimpleNamespace
    m = {"wb_profit_ltd": 687635, "wb_revenue_ltd": 989840,
         "wb_costs_ltd": -302204, "wb_months_in_program": 36,
         "wb_mailings_to_date": 18, "wb_source": "wbk.xlsx",
         "ba_lift_net": 982, "segment_ic_rate": 0.0065,
         "wb_waves": [["Jan26", 5661, 3.0, 2942, 170]]}
    r = SimpleNamespace(client_id="1585", client_name="X", period="2026-08",
                        data_month="2026-07", duration_s=1.0, metrics=m,
                        warnings=[], errors=[], outputs={})
    text = report(r)
    assert "REVENUE FRAMES" in text
    assert "program revenue, LTD" in text
    assert "never tie by design" in text
    assert "$6.38" in text          # 982 x 0.0065, per responder-month
    assert "incremental revenue" not in text


@_later
def test_value_survives_an_empty_eligible_base():
    """1780 (#47 run 2): zero eligible accounts made value.compute throw
    ZeroDivisionError instead of declining gracefully. Empty base ->
    warnings and partial keys, never a crash."""
    import pandas as pd
    from ti.core.periods import Month
    from ti.core.subsets import Subsets
    from ti.monthly_analysis import value

    cols = {"Acct ID": [], "Debit?": [], "Business?": []}
    for t in ("Jun26", "Jul26"):
        cols[f"{t} Spend"] = []
        cols[f"{t} MTD"] = []
    empty = pd.DataFrame(cols)
    subs = Subsets(total=empty, open_accounts=empty, eligible=empty,
                   eligible_personal=empty, eligible_business=empty,
                   eligible_with_debit=empty, personal_with_debit=empty,
                   l12m_open=empty, l12m_eligible=empty, responders=empty,
                   non_responders=empty, anchor=Month(2026, 7))
    warns = []
    m = value.compute(subs, {"ICRate": "0.0076", "NSF_OD_Fee": "30"},
                      warns.append)
    assert isinstance(m, dict)          # no exception is the test
    assert any("carded and non-carded" in w for w in warns)


def _waves(path):
    """{tag: (mailed, response_pct, cumulative_revenue, goal_met)}"""
    warnings = []
    m = workbook.read(path, warnings.append)
    return {w[0]: tuple(w[1:]) for w in m["wb_waves"]}, m, warnings


def test_cumulative_revenue_reads_the_to_date_column_past_column_j(tmp_path):
    """A wave with a long history pushes To Date well past column J. The
    reader must find that column by its header, not take the last numeric
    it happens to see -- which lands on a mid-series MONTH."""
    waves, _m, _w = _waves(_make_wb(tmp_path / "wide.xlsx"))
    assert waves["Jan26"][2] == 2010          # not 70, the tenth month


def test_cumulative_revenue_sums_months_when_the_sheet_has_no_to_date(tmp_path):
    """Some waves ship Annualized with no To Date column at all. The
    annualized figure is a projection, NOT revenue to date -- the reader
    sums the month cells left of it instead."""
    waves, _m, _w = _waves(_make_wb(tmp_path / "notd.xlsx", variants=True))
    assert waves["Mar26"][2] == 1000          # not 4800, the annualization


def test_duplicate_swipes_panel_does_not_double_goal_met(tmp_path):
    """Some Mailing sheets repeat the tier counts in a summary panel above
    the Nonuser anchor. Counting both doubles every responder figure and
    the response rate with it."""
    waves, m, _w = _waves(_make_wb(tmp_path / "dupe.xlsx", variants=True))
    mailed, resp_pct, _cum, goal_met = waves["May26"]
    assert m["wb_wave_tiers"]["May26"] == {"NU5": 40, "TH10": 60}
    assert goal_met == 100                    # not 200
    assert mailed == 4000
    assert resp_pct == 2.5                    # not 5.0


def test_rollup_yields_the_wave_by_month_revenue_matrix(tmp_path):
    """All Months Rollup MM carries one section per wave: revenue by month,
    which is the program's booked decay curve and the composition of every
    month's revenue. The reader stopped at row 12 and never saw it."""
    warnings = []
    m = workbook.read(_make_wb(tmp_path / "roll.xlsx", rollup=True),
                      warnings.append)
    assert m["wb_wave_revenue_columns"] == ["wave", "month", "revenue"]
    by = {(w, mo): v for w, mo, v in m["wb_wave_revenue"]}
    assert by[("Jan26", "2026-01")] == 1000
    assert by[("Jan26", "2026-03")] == 410
    assert by[("Feb26", "2026-02")] == 500
    # a wave has no row before it mailed -- blank is not zero revenue
    assert ("Feb26", "2026-01") not in by
    assert m["wb_rollup_total_ltd"] == 2810
    assert not warnings


def test_rollup_wave_rows_reconcile_to_the_summary_row(tmp_path):
    """The Summary row is the sum of the wave rows, month by month. If it
    is not, the sheet is mid-edit or a section was missed -- say so."""
    import openpyxl
    path = _make_wb(tmp_path / "bad.xlsx", rollup=True)
    wb = openpyxl.load_workbook(path)
    ws = wb["All Months Rollup MM"]
    for row in ws.iter_rows():
        if row[1].value == "Summary":
            ws.cell(row=row[0].row + 1, column=5).value = 4000   # was 1000
            break
    wb.save(path)

    warnings = []
    workbook.read(path, warnings.append)
    assert any("2026-01" in w and "Summary" in w for w in warnings), warnings


def test_rollup_reconciles_each_wave_against_its_mailing_sheet(tmp_path):
    """The wave's rollup row and its Mailing sheet To Date are two
    independent paths to the same number. Divergence is the signal that
    caught the column-read defect in the first place."""
    import openpyxl
    path = _make_wb(tmp_path / "wave.xlsx", rollup=True)
    wb = openpyxl.load_workbook(path)
    ws = wb["Mailing Feb 2026"]
    for row in ws.iter_rows():
        if row[1].value == "Total Revenue:":
            ws.cell(row=row[0].row, column=14).value = 9999      # was 800
            break
    wb.save(path)

    warnings = []
    workbook.read(path, warnings.append)
    assert any("Feb26" in w and "To Date" in w for w in warnings), warnings


@_later
def test_hero_declines_when_a_workbook_was_found_but_gave_no_profit():
    """Issue #40's frame rule reaches the hero (James, 2026-08-31): a
    client that HAS a workbook must not have slide two quietly become the
    ODD's control-anchored figure when that workbook will not open. The
    booked slot skips, the way Program P&L and the rollups already do."""
    sys.path.insert(0, str(HERE))
    from test_ti_deck_layout import _build_fixture, _wave3_metrics
    mm = _wave3_metrics()
    mm["wb_found"] = "1217-2026.08-Pioneer FCU-Workbook_v2_1_0.xlsx"
    d = _build_fixture(mm)
    text = d.storyboard.read_text(encoding="utf-8")
    rendered, _, gaps = text.partition("Not rendered")
    assert "The campaign hero" in gaps
    assert "no-mail line" not in rendered
    assert "workbook" in gaps.partition("The campaign hero")[2].splitlines()[0]


@_later
def test_hero_keeps_the_odd_frame_when_the_client_has_no_workbook():
    """The counterfactual opener is for clients with no ARS Workbook at
    all -- they keep their hero. Only a workbook that WAS found and did
    not read suppresses it."""
    sys.path.insert(0, str(HERE))
    from test_ti_deck_layout import _build_fixture, _wave3_metrics
    mm = _wave3_metrics()
    mm.pop("wb_found", None)
    d = _build_fixture(mm)
    text = d.storyboard.read_text(encoding="utf-8")
    assert "no-mail line" in text.partition("Not rendered")[0]


def test_hero_headline_never_switches_frames_under_a_found_workbook():
    from ti.deck import headlines
    m = {"counterfactual_gap_total": 12000, "ba_lift_net": 40.0}
    assert headlines.hero(m) is not None, "no workbook: the ODD frame stands"
    assert headlines.hero({**m, "wb_found": "wbk.xlsx"}) is None
    booked = {**m, "wb_found": "wbk.xlsx", "wb_profit_ltd": 687635}
    head, _sub = headlines.hero(booked)
    assert "program profit" in head


def test_lift_matrix_reads_the_current_window_grid(tmp_path):
    path = _make_wb(tmp_path / "lift.xlsx", lift=True)
    warnings = []
    m = workbook.read(path, warnings.append)
    assert m["wb_lift_cols"] == ["1-5", "6-10", "11-15", "16-20", "21-25",
                                 "26 Plus"]
    assert [r[0] for r in m["wb_lift_rows"]] == [
        "Non-user", "1-5", "6-10", "11-15", "16-20", "21-25"]
    assert m["wb_lift_rows"][0][1:] == [4.1, 6.2, 8.3, 10.4, 12.5, 14.6]
    assert m["wb_lift_window"] == "Aug 2025 to Jul 2026"
    assert m["wb_lift_caption"] == "Revenue per account per month ($)"
    assert m["wb_lift_stale"] is False


def test_lift_matrix_flags_a_window_the_data_has_outrun(tmp_path):
    """A rate card is only good for its window: October data against a
    window that ended in July is stale, and the slide must say so."""
    path = _make_wb(tmp_path / "stale.xlsx", lift="stale")
    warnings = []
    m = workbook.read(path, warnings.append)
    assert m["wb_lift_stale"] is True
    assert any("Lift Matrix" in w and "stale" in w.lower() for w in warnings), \
        warnings


def test_lift_matrix_is_silent_when_the_sheet_is_absent(tmp_path):
    path = _make_wb(tmp_path / "nolift.xlsx")
    m = workbook.read(path, [].append)
    assert not any(k.startswith("wb_lift") for k in m)


@_later
def test_lift_matrix_slide_renders_on_the_main_path():
    sys.path.insert(0, str(HERE))
    from test_ti_deck_layout import _build_fixture, _wave3_metrics
    mm = _wave3_metrics()
    mm.update({
        "wb_source": "wbk.xlsx",
        "wb_lift_cols": ["1-5", "6-10", "11-15", "16-20", "21-25", "26 Plus"],
        "wb_lift_rows": [["Non-user", 4.1, 6.2, 8.3, 10.4, 12.5, 14.6],
                         ["1-5", 6.4, 8.5, 10.6, 12.7, 14.8, 16.9]],
        "wb_lift_window": "Aug 2025 to Jul 2026",
        "wb_lift_caption": "Revenue per account per month ($)",
        "wb_lift_stale": False,
    })
    d = _build_fixture(mm)
    text = d.storyboard.read_text(encoding="utf-8")
    rendered, _, gaps = text.partition("Not rendered")
    assert "What an account earns as it climbs" not in gaps
    # the storyboard's rendered section carries HEADLINES, not slide ids
    assert "Every segment climbs, $4.10 to $16.90 a month" in rendered


@_later
def test_lift_matrix_slide_skips_and_names_the_workbook():
    sys.path.insert(0, str(HERE))
    from test_ti_deck_layout import _build_fixture, _wave3_metrics
    mm = _wave3_metrics()
    mm["wb_found"] = "1217-2026.08-Pioneer FCU-Workbook_v2_1_0.xlsx"
    d = _build_fixture(mm)
    gaps = d.storyboard.read_text(encoding="utf-8").partition("Not rendered")[2]
    assert "What an account earns as it climbs" in gaps
