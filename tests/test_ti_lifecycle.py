# Ported from ARS v5 02-Scripts/tests/test_lifecycle.py at a491b5c (James Gilmore); logic unchanged.
"""Event-time alignment: each account on a clock starting at its own event."""
import pathlib
import sys

import numpy as np
import pandas as pd


from ti.core.periods import Month
from ti.monthly_analysis import lifecycle as L

ANCHOR = Month.from_tag("Jul26")


def _series(n_months=16, anchor=ANCHOR):
    """Month tags oldest -> newest, ending at the anchor."""
    return [anchor.shift(-i) for i in range(n_months - 1, -1, -1)]


# ---- the depth rule -------------------------------------------------------

def test_twelve_or_more_months_caps_at_twelve():
    assert L.choose_window(16) == 12
    assert L.choose_window(12) == 12


def test_six_to_eleven_months_caps_at_six():
    assert L.choose_window(11) == 6
    assert L.choose_window(6) == 6


def test_under_six_months_exits_rather_than_reporting_something_shallow():
    """A three-month curve is not a small version of a twelve-month one; it is
    a different claim. The section declines instead."""
    assert L.choose_window(5) is None
    assert L.choose_window(0) is None


# ---- alignment ------------------------------------------------------------

def test_forward_alignment_puts_the_open_month_at_offset_zero():
    months = _series(6)
    # one account opened at index 2 (the third month), spending 0,0,10,20,30,40
    matrix = np.array([[0, 0, 10, 20, 30, 40]], dtype=float)
    event = pd.Series([pd.Timestamp(months[2].year, months[2].month, 1)])
    aligned = L.align(matrix, months, event, window=3, direction="forward")
    assert list(aligned[0]) == [10, 20, 30, 40]


def test_backward_alignment_puts_the_close_month_at_offset_zero():
    months = _series(6)
    # closed at index 4; the months before it are 10,20,30,40
    matrix = np.array([[10, 20, 30, 40, 5, 0]], dtype=float)
    event = pd.Series([pd.Timestamp(months[4].year, months[4].month, 1)])
    aligned = L.align(matrix, months, event, window=3, direction="backward")
    # offset 0 is the close month, then 1,2,3 months BEFORE it
    assert list(aligned[0]) == [5, 40, 30, 20]


def test_offsets_outside_the_column_span_are_nan_not_zero():
    """An account whose history predates the file has unknown spend, not none.
    Zero would drag every mean toward the floor."""
    months = _series(4)
    matrix = np.array([[10, 20, 30, 40]], dtype=float)
    event = pd.Series([pd.Timestamp(months[1].year, months[1].month, 1)])
    aligned = L.align(matrix, months, event, window=3, direction="backward")
    assert aligned[0][0] == 20
    assert aligned[0][1] == 10
    assert np.isnan(aligned[0][2]), "reaching before the file must be NaN"


def test_an_account_with_no_event_date_is_all_nan():
    months = _series(4)
    matrix = np.array([[10, 20, 30, 40]], dtype=float)
    aligned = L.align(matrix, months, pd.Series([pd.NaT]), window=2,
                      direction="forward")
    assert np.isnan(aligned[0]).all()


# ---- the ragged curve -----------------------------------------------------

def test_curve_reports_a_base_at_every_offset():
    aligned = np.array([[10.0, 20.0, 30.0],
                        [12.0, 22.0, np.nan],
                        [14.0, np.nan, np.nan]])
    rows = L.curve(aligned, min_cohort=1)
    assert [r[0] for r in rows] == [0, 1, 2]
    assert [r[1] for r in rows] == [3, 2, 1], "base must thin with depth"


def test_offsets_below_the_minimum_cohort_report_none_not_an_average():
    """Two accounts averaged into a confident-looking line is the failure this
    prevents -- the habit ics.py already follows with SURVIVAL_MIN_BASE."""
    aligned = np.array([[10.0, 20.0, 30.0],
                        [12.0, 22.0, np.nan],
                        [14.0, np.nan, np.nan]])
    rows = L.curve(aligned, min_cohort=2)
    assert rows[2][1] == 1
    assert rows[2][2] is None, "a 1-account mean must not be published"


def test_curve_carries_the_share_that_were_active():
    aligned = np.array([[10.0, 0.0], [0.0, 0.0], [5.0, 5.0]])
    rows = L.curve(aligned, min_cohort=1)
    assert rows[0][4] == round(100 * 2 / 3, 1)
    assert rows[1][4] == round(100 * 1 / 3, 1)


# ---- tenure buckets -------------------------------------------------------

def test_the_first_year_is_resolved_month_by_month():
    """Most closures land in year one and a young programme's whole cohort
    sits there. A single 0-12 mo band hides the detail where it is needed."""
    labels = [b[2] for b in L.TENURE_BUCKETS]
    assert labels[:12] == [f"month {i}" for i in range(1, 13)]
    assert labels[12:] == ["1-3 yr", "3-5 yr", "5-10 yr", "10+ yr"]


def test_bucket_of_resolves_within_the_first_year():
    assert L.bucket_of(0.0) == "month 1"
    assert L.bucket_of(1 / 12) == "month 2"
    assert L.bucket_of(11.9 / 12) == "month 12"


def test_bucket_of_widens_after_the_first_year():
    assert L.bucket_of(1.0) == "1-3 yr"
    assert L.bucket_of(4.9) == "3-5 yr"
    assert L.bucket_of(7.0) == "5-10 yr"
    assert L.bucket_of(10.0) == "10+ yr"


def test_unknown_tenure_is_not_quietly_called_new():
    """Guessing would load month 1 with every unparseable open date -- the
    band a young-programme comparison reads most closely."""
    assert L.bucket_of(float("nan")) is None
    assert L.bucket_of(None) is None


# ---- divergence: how many months of warning ------------------------------

def test_divergence_is_the_earliest_sustained_separation():
    """Offsets run 0 (the close month) outward. The answer is the FURTHEST
    offset from which the gap holds all the way in -- that is the warning."""
    closers = [[0, 90, 10.0, None, None], [1, 90, 20.0, None, None],
               [2, 90, 40.0, None, None], [3, 90, 95.0, None, None]]
    control = [[0, 90, 100.0, None, None], [1, 90, 100.0, None, None],
               [2, 90, 100.0, None, None], [3, 90, 100.0, None, None]]
    assert L.divergence_month(closers, control, ratio=0.8) == 2


def test_a_single_dip_does_not_count_as_divergence():
    """One month below the line is noise. The gap must hold from there in."""
    closers = [[0, 90, 100.0, None, None], [1, 90, 50.0, None, None],
               [2, 90, 100.0, None, None]]
    control = [[0, 90, 100.0, None, None], [1, 90, 100.0, None, None],
               [2, 90, 100.0, None, None]]
    assert L.divergence_month(closers, control, ratio=0.8) is None


def test_divergence_is_none_when_a_needed_offset_was_suppressed():
    """A None mean is unknown, not equal. It cannot support a claim."""
    closers = [[0, 90, 10.0, None, None], [1, 5, None, None, None]]
    control = [[0, 90, 100.0, None, None], [1, 90, 100.0, None, None]]
    assert L.divergence_month(closers, control, ratio=0.8) == 0


def test_no_separation_returns_none_not_zero():
    same = [[0, 90, 100.0, None, None], [1, 90, 100.0, None, None]]
    assert L.divergence_month(same, same, ratio=0.8) is None


# ---- end to end: does the detector fire on a book that IS declining? ------

class _Subsets:
    """Minimal stand-in: the section reads .total and .anchor only."""

    def __init__(self, frame, anchor):
        self.total, self.anchor = frame, anchor


def _book(n_closed=120, n_open=300, decline_from=4):
    """Closers fade over the `decline_from` months before their close date;
    open accounts hold steady. Built so the divergence is a known answer."""
    months = [ANCHOR.shift(-i) for i in range(15, -1, -1)]
    rows, opened, closed = [], [], []
    close_idx = len(months) - 5
    close_at = months[close_idx]                      # everyone closes 4 months back
    close_idx = months.index(close_at)
    for i in range(n_closed):
        series = []
        for j in range(len(months)):
            before = close_idx - j             # months before closing
            if 0 <= before < decline_from:
                series.append(100.0 * (before + 1) / (decline_from + 1))
            elif j > close_idx:
                series.append(0.0)
            else:
                series.append(100.0)
        rows.append(series)
        opened.append(pd.Timestamp(2015, 1, 1))
        closed.append(pd.Timestamp(close_at.year, close_at.month, 15))
    for i in range(n_open):
        rows.append([100.0] * len(months))
        opened.append(pd.Timestamp(2015, 1, 1))
        closed.append(pd.NaT)

    frame = pd.DataFrame(rows, columns=[f"{m.tag} Spend" for m in months])
    frame["Date Opened"] = opened
    frame["Date Closed"] = closed
    for m in months:
        frame[f"{m.tag} Swipes"] = 1.0
    return frame


def test_the_detector_fires_on_a_book_that_really_declines():
    from ti.monthly_analysis import lifecycle_report as R

    out = R.compute(_Subsets(_book(), ANCHOR), {}, lambda m: None)
    assert out["life_divergence_month"] is not None, \
        "a manufactured 4-month fade must be detected"
    assert out["life_divergence_month"] >= 1


def test_it_reports_no_divergence_on_a_book_that_does_not_decline():
    """The other half of the same claim: no false positive on a flat book."""
    from ti.monthly_analysis import lifecycle_report as R

    out = R.compute(_Subsets(_book(decline_from=0), ANCHOR), {}, lambda m: None)
    assert out["life_divergence_month"] is None


def test_a_shallow_file_declines_the_section_rather_than_shortening_it():
    from ti.monthly_analysis import lifecycle_report as R

    frame = _book()
    keep = [c for c in frame.columns if not str(c).endswith("Spend")]
    spend = [c for c in frame.columns if str(c).endswith("Spend")][-4:]
    warned = []
    out = R.compute(_Subsets(frame[keep + spend], ANCHOR), {}, warned.append)
    assert "life_window" not in out
    assert out["life_exit_reason"]
    assert any("at least" in w for w in warned)


def test_divergence_can_look_for_a_rise_as_well_as_a_fall():
    """Leakage climbing before closure is the same shape, inverted."""
    risers = [[0, 90, 400.0, None, None], [1, 90, 300.0, None, None],
              [2, 90, 105.0, None, None]]
    flat = [[0, 90, 100.0, None, None], [1, 90, 100.0, None, None],
            [2, 90, 100.0, None, None]]
    assert L.divergence_month(risers, flat, ratio=0.8, direction="above") == 1
    assert L.divergence_month(risers, flat, ratio=0.8, direction="below") is None


# ---- deposits in event time ----------------------------------------------

def _deposit_monthly(accts, months, closers, close_idx, fade_from=3):
    """Monthly deposits: closers fade in the months up to THEIR close month.

    close_idx is the position of the close month in `months`. Fading the tail
    of the series instead was my first attempt and measured nothing -- the
    accounts close four months before the series ends, so the fade sat
    entirely after closure where no pre-closure offset can see it.
    """
    rows = []
    for a in accts:
        for j, m in enumerate(months):
            before = close_idx - j
            fading = a in closers and 0 <= before < fade_from
            amt = 250.0 * (before + 1) if fading else 1000.0
            rows.append([a, m, 1, amt])
    return pd.DataFrame(rows, columns=["acct", "date", "dep_count", "dep_amount"])


def test_deposit_decline_is_measured_on_the_same_clock_as_spend():
    from ti.monthly_analysis import lifecycle_report as R

    n_close, n_open = 120, 300
    accts = [f"A{i}" for i in range(n_close + n_open)]
    closers = set(accts[:n_close])
    months = [pd.Timestamp(m.year, m.month, 1)
              for m in [ANCHOR.shift(-i) for i in range(11, -1, -1)]]
    close_idx = len(months) - 5
    close_at = months[close_idx]

    frame = pd.DataFrame({
        "Acct Number": accts,
        "Date Opened": [pd.Timestamp(2015, 1, 1)] * len(accts),
        "Date Closed": [close_at + pd.to_timedelta(14, unit="D") if a in closers
                        else pd.NaT for a in accts],
    })
    for m in [ANCHOR.shift(-i) for i in range(15, -1, -1)]:
        frame[f"{m.tag} Spend"] = 100.0
        frame[f"{m.tag} Swipes"] = 1.0

    config = {"_deposit_monthly": _deposit_monthly(accts, months, closers,
                                                   close_idx)}
    out = R.compute(_Subsets(frame, ANCHOR), config, lambda m: None)

    assert out.get("life_deposit_decline"), "deposit curve not produced"
    assert out.get("life_deposit_divergence_month") is not None, \
        "a manufactured deposit fade before closure must be detected"


def test_no_deposits_file_means_no_deposit_curve_and_no_pretence():
    from ti.monthly_analysis import lifecycle_report as R

    out = R.compute(_Subsets(_book(), ANCHOR), {}, lambda m: None)
    assert "life_deposit_decline" not in out


# ---- the ICS case: matched on vintage ------------------------------------

def _ics_book(n_ics=120, n_non=200, ics_lift=1.4):
    """ICS accounts opened recently and spending more; non-ICS split between
    the same vintage and a much older cohort that must be excluded."""
    months = [ANCHOR.shift(-i) for i in range(15, -1, -1)]
    recent, ancient = pd.Timestamp(2025, 9, 1), pd.Timestamp(2012, 1, 1)
    rows, opened, source = [], [], []
    for i in range(n_ics):
        rows.append([100.0 * ics_lift] * len(months))
        opened.append(recent); source.append("DM")
    for i in range(n_non):
        rows.append([100.0] * len(months))
        opened.append(recent); source.append("")
    for i in range(300):                       # the old book: must not count
        rows.append([500.0] * len(months))
        opened.append(ancient); source.append("")
    frame = pd.DataFrame(rows, columns=[f"{m.tag} Spend" for m in months])
    frame["Date Opened"] = opened
    frame["Date Closed"] = pd.NaT
    frame["DM-REF Source"] = source
    for m in months:
        frame[f"{m.tag} Swipes"] = 1.0
    return frame


def test_the_ics_comparison_excludes_the_older_book():
    """ICS accounts are recent because the programme is young. Comparing them
    against a book of ten-year accounts credits ICS for being new."""
    from ti.monthly_analysis import lifecycle_report as R

    out = R.compute(_Subsets(_ics_book(), ANCHOR), {}, lambda m: None)
    assert out["life_non_n"] == 200, \
        "the 300 ancient accounts must be outside the shared vintage window"
    assert out["life_ics_n"] == 120


def test_ics_lift_is_reported_per_month_since_opening():
    from ti.monthly_analysis import lifecycle_report as R

    out = R.compute(_Subsets(_ics_book(ics_lift=1.4), ANCHOR), {},
                    lambda m: None)
    lifts = [v for _, v in out["life_ramp_ics_lift_pct"] if v is not None]
    assert lifts, "no lift computed"
    assert all(abs(v - 40.0) < 1.0 for v in lifts), \
        f"a 1.4x book should read as ~40% lift, got {lifts[:4]}"


def test_a_thin_ics_cohort_is_declined_not_drawn():
    from ti.monthly_analysis import lifecycle_report as R

    warned = []
    out = R.compute(_Subsets(_ics_book(n_ics=10), ANCHOR), {}, warned.append)
    assert "life_ramp_ics" not in out
    assert any("ICS account" in w for w in warned)
