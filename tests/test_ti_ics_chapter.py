# Ported from ARS v5 02-Scripts/tests/test_ics_chapter.py at a491b5c (James Gilmore); logic unchanged.
"""The ICS deck chapter: which slides build, and what never appears.

    python -m pytest tests/test_ics_chapter.py -q

The chapter is behaviour-only by decision (James, 2026-08-26): the ICS
workbook owns interchange, value and payback, and carrying both made the
chapter hedge its own headlines. That is asserted here, not just intended.
"""
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.deck import ics_slides                                    # noqa: E402


class _Shape:
    pass


def _helpers(built):
    def slide(hs, sid):
        head, sub = hs if isinstance(hs, tuple) else (hs, None)
        built.append({"id": sid, "head": head, "sub": sub})
        return _Shape(), 1.0
    noop = lambda *a, **k: None                                    # noqa: E731
    return {"new": lambda *a, **k: _Shape(), "slide": slide,
            "chart": lambda *a, **k: None, "divider": noop, "rail": noop,
            "table": noop, "kpi": noop, "text": noop, "chart_left": noop,
            "money": lambda v: f"${v:,.0f}", "kicker": noop,
            "fit_picture": noop, "MARGIN_L": 0.5, "RIGHT_EDGE": 12.0,
            "CONTENT_W": 11.5}


BASE = {
    "ics_cmp_bases": {"ics": 2000, "non": 7000, "stamped_total": 2010,
                      "out_of_coverage": 10},
    "ics_source_counts": {"DM": 400, "REF": 1610},
    "ics_cmp_openings_monthly": [["Jan25", 100], ["Feb25", 120], ["Mar25", 140]],
    "ics_cmp_activation_cum": [[1, 73.0, 58.0], [12, 85.0, 75.0]],
    "ics_cmp_ttfs": {"ics_median_mo": 0, "non_median_mo": 0,
                     "buckets": [["same month", 55.0, 41.0],
                                 ["never", 14.0, 24.0]]},
    "ics_activity_grid": [[o, 900 - o * 20, 68.0 - o] for o in range(1, 13)],
    "ics_cmp_hazard": {"columns": ["tenure", "reached_and_resolved",
                                   "closed_in_bucket_pct"],
                       "ics": [["0-6 mo", 1400, 4.8], ["6-12 mo", 700, 5.8],
                               ["12-18 mo", 17, None]],
                       "non": [["0-6 mo", 5500, 6.1], ["6-12 mo", 3600, 5.7],
                               ["12-18 mo", 1700, 5.4]]},
    "ics_cmp_firstyear_close": {
        "ics": {"n": 726, "used_n": 625, "used_pct": 9.9,
                "never_used_n": 101, "never_used_pct": 13.9},
        "non": {"n": 3952, "used_n": 3038, "used_pct": 10.7,
                "never_used_n": 914, "never_used_pct": 20.4}},
}

TXN = {
    "comp_by_lens": [
        ["ics", "ICS accounts", 1948, 237, 12.2, 19.0, 475, "Chase"],
        ["ics_dm", "ICS direct mail", 261, 39, 14.9, 25.6, 514, "Chase"],
        ["ics_ref", "ICS referral", 1689, 198, 11.7, 17.7, 468, "Chase"],
        ["new_accounts", "Opened last 12 mo", 3704, 342, 9.2, 18.1, 632, "Chase"]],
    "mch_by_lens": [
        ["ics", "ICS accounts", 1948, 6197, 14.2, "WAL MART"],
        ["new_accounts", "Opened last 12 mo", 3704, 5426, 9.5, "WAL MART"]],
    "mch_by_category": [["Grocery", 1, 2, 3, 16.6], ["Dining", 1, 2, 3, 13.1]],
    "beh_by_lens": [["ics", "ICS accounts", 1948, 18.02, 14.2, 0.0],
                    ["new_accounts", "Opened last 12 mo", 3704, 20.39, 9.5, 0.0]],
}


def _run(m=None, txn=None):
    built = []
    skipped = ics_slides.add_chapter(None, _helpers(built), m or dict(BASE),
                                     pathlib.Path("/tmp"), txn=txn)
    return built, skipped


def _ids(built):
    return [b["id"] for b in built]


def test_retention_rail_shows_the_survival_horizons():
    """ics_survival (6/12/24 mo vs same-month non-ICS) was CSV-only (#245)."""
    m = dict(BASE)
    m["ics_cmp_survival_curve"] = {"months": [2, 12], "ics": [98.0, 91.0], "non": [97.0, 88.0]}
    m["ics_survival"] = [["6 mo", 95.0, 93.0], ["12 mo", 91.0, 88.0], ["24 mo", None, 80.0]]
    m["ics_survival_columns"] = ["horizon", "ics_pct", "non_ics_pct"]
    built, rails = [], []
    h = _helpers(built)
    h["rail"] = lambda s, items, **k: rails.append(items)
    ics_slides.add_chapter(None, h, m, pathlib.Path("/tmp"), txn=None)
    flat = " ".join(str(x) for items in rails for item in items for x in item)
    assert "6 mo" in flat and "95" in flat and "24 mo" in flat and "n/a" in flat


def test_lifecycle_columns_key_follows_the_csv_convention():
    import inspect
    from ti.monthly_analysis import lifecycle_ics
    src = inspect.getsource(lifecycle_ics)
    assert "life_ramp_ics_columns" in src and "life_ramp_columns_ics" not in src


def test_the_new_behaviour_slides_build():
    built, _ = _run(txn=TXN)
    for wanted in ("ICS sustained activity", "ICS closure hazard",
                   "ICS first-year closure", "ICS primacy", "ICS merchants"):
        assert wanted in _ids(built), f"{wanted} missing from {_ids(built)}"


def test_transaction_slides_decline_without_the_ics_lens():
    """No ICS lens rows -> primacy and merchants skip-report, never render
    against the wrong cohort."""
    built, skipped = _run(txn={})
    assert "ICS primacy" not in _ids(built)
    assert "ICS merchants" not in _ids(built)
    assert any("primacy" in s for s in skipped)
    assert any("merchants" in s for s in skipped)


def test_chapter_never_mentions_value_or_payback():
    built, _ = _run(txn=TXN)
    blob = " ".join(f"{b['head']} {b['sub'] or ''}" for b in built).lower()
    for banned in ("interchange", "payback", "icrate", "value to date"):
        assert banned not in blob, f"{banned!r} leaked into the chapter"


def test_activation_headline_leads_with_the_gap_not_the_median():
    """Both cohorts have a 0-month median, so the old headline led with the
    one activation number showing no difference."""
    built, _ = _run(txn=TXN)
    head = next(b["head"] for b in built if b["id"] == "ICS activation")
    assert "73%" in head and "58%" in head
    assert "median" not in head.lower()


def test_hazard_declines_a_thin_bucket_rather_than_plotting_it():
    built, _ = _run(txn=TXN)
    haz = next(b for b in built if b["id"] == "ICS closure hazard")
    assert "12-18" not in (haz["sub"] or "")   # base of 17 never reaches a bar


def test_sustained_activity_reads_the_orphaned_activity_grid():
    """ics_activity_grid was computed every run and read by nothing."""
    built, _ = _run(txn=TXN)
    assert "ICS sustained activity" in _ids(built)
    m = dict(BASE); m.pop("ics_activity_grid")
    built2, skipped2 = _run(m=m, txn=TXN)
    assert "ICS sustained activity" not in _ids(built2)
    assert any("sustained activity" in s for s in skipped2)


def test_primacy_and_merchants_render_a_table_not_a_two_bar_chart():
    """Regression: both slides were built with charts.grouped_bars, which
    kept two numbers of thirty and hid the DM-vs-REF split entirely -- the
    finding the slide exists for. They render the house table now.
    """
    built, tables = [], []
    h = _helpers(built)
    h["table"] = lambda slide, rows, *a, **k: tables.append(rows)
    ics_slides.add_chapter(None, h, dict(BASE), pathlib.Path("/tmp"), txn=TXN)
    assert len(tables) >= 2, "primacy and merchants both need a table"
    primacy = tables[0]
    assert primacy[0][0] == "Cohort"                 # header row
    labels = [r[0] for r in primacy[1:]]
    # every ICS channel is a row, so the split is on the slide itself
    assert "ICS referral" in labels and "ICS direct mail" in labels
    assert labels[0] == "ICS accounts"               # subject leads


def test_merchant_categories_keep_their_real_shares():
    """tier_bars renormalises over the rows it gets. Passing the top 8 of 11
    inflated every share -- Other printed 27% against a real 25.2%."""
    calls = []
    built = []
    h = _helpers(built)
    h["chart"] = lambda name, fn, *a, **k: (
        calls.append((name, a)) or None)
    ics_slides.add_chapter(None, h, dict(BASE), pathlib.Path("/tmp"), txn=TXN)
    cats = next(a[0] for n, a in calls if n == "ics_categories")
    assert len(cats) == len(TXN["mch_by_category"]), "every category, not a top-N"


