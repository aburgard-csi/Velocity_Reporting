# Ported from ARS v5 02-Scripts/tests/test_deposits.py at a491b5c (James Gilmore); logic unchanged.
"""The deposits file: rolling 365 days, Acct Number | Date | Dep Count | Dep Amount."""
import pathlib
import sys

import numpy as np
import pandas as pd
import pytest


from ti.core import deposits as D


def _rows(acct, start, n, every, amount, jitter=0.0, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        amt = amount * (1 + jitter * float(rng.normal()))
        out.append([acct, pd.Timestamp(start) + pd.to_timedelta(every * i, unit="D"),
                    1, round(amt, 2)])
    return out


def _frame(rows):
    return pd.DataFrame(rows, columns=["acct", "date", "dep_count", "dep_amount"])


# ---- loading --------------------------------------------------------------

def test_headers_are_matched_case_and_spacing_insensitively(tmp_path):
    path = tmp_path / "1441_deposits_365.csv"
    path.write_text("Acct Number,Date,Dep Count,Dep Amount\n"
                    "A1,2026-01-15,1,1200.00\n"
                    "A1,2026-01-31,1,1200.00\n")
    rep = D.LoadReport()
    frame = D.load(path, tmp_path / "_cache", rep)
    assert list(frame.columns) == ["acct", "date", "dep_count", "dep_amount"]
    assert rep.rows == 2 and rep.accounts == 1


def test_the_second_read_comes_from_the_parquet_cache(tmp_path):
    """Eight million rows is a one-time cost, not a per-run one."""
    path = tmp_path / "deposits.csv"
    path.write_text("Acct Number,Date,Dep Count,Dep Amount\nA1,2026-01-15,1,10\n")
    cache = tmp_path / "_cache"
    first, second = D.LoadReport(), D.LoadReport()
    D.load(path, cache, first)
    D.load(path, cache, second)
    assert not first.cached and second.cached


def test_unparseable_dates_and_amounts_are_dropped_not_zeroed(tmp_path):
    path = tmp_path / "deposits.csv"
    path.write_text("Acct Number,Date,Dep Count,Dep Amount\n"
                    "A1,2026-01-15,1,100\nA2,not-a-date,1,100\nA3,2026-01-15,1,\n")
    rep = D.LoadReport()
    frame = D.load(path, None, rep)
    assert rep.rows == 1, "a zero-amount deposit is not the same as no deposit"


def test_a_file_missing_a_required_column_warns_and_returns_empty(tmp_path):
    path = tmp_path / "deposits.csv"
    path.write_text("Acct Number,Widgets\nA1,3\n")
    rep = D.LoadReport()
    frame = D.load(path, None, rep)
    assert frame.empty and any("date" in w for w in rep.warnings)


def test_monthly_rolls_daily_rows_up_to_the_grain_the_curves_need():
    frame = _frame(_rows("A1", "2026-01-05", 6, 5, 100.0))
    out = D.monthly(frame)
    assert set(out.columns) == {"acct", "date", "dep_count", "dep_amount"}
    assert len(out) == 1 and out["dep_amount"].iloc[0] == 600.0


# ---- cadence --------------------------------------------------------------

def test_a_fortnightly_consistent_deposit_is_flagged_probable():
    frame = _frame(_rows("PAYROLL", "2026-01-02", 12, 14, 1500.0, jitter=0.01))
    row = D.cadence(frame).iloc[0]
    assert bool(row["probable_direct_deposit"])
    assert 13 <= row["median_gap_days"] <= 15


def test_a_monthly_consistent_deposit_is_flagged_probable():
    frame = _frame(_rows("PAYROLL", "2026-01-02", 8, 30, 3000.0, jitter=0.01))
    assert bool(D.cadence(frame).iloc[0]["probable_direct_deposit"])


def test_erratic_amounts_on_a_regular_rhythm_are_not_flagged():
    """Rhythm alone is not payroll. A gig worker paid weekly-ish at wildly
    different amounts is not a direct deposit."""
    frame = _frame(_rows("GIG", "2026-01-02", 12, 14, 1500.0, jitter=0.9, seed=3))
    assert not bool(D.cadence(frame).iloc[0]["probable_direct_deposit"])


def test_too_few_deposits_are_not_flagged_however_regular():
    frame = _frame(_rows("SPARSE", "2026-01-02", 3, 14, 1500.0))
    assert not bool(D.cadence(frame).iloc[0]["probable_direct_deposit"])


def test_a_single_deposit_leaves_consistency_unknown_not_perfect():
    frame = _frame(_rows("ONE", "2026-01-02", 1, 14, 1500.0))
    assert pd.isna(D.cadence(frame).iloc[0]["amount_cv"])


# ---- windfalls ------------------------------------------------------------

def test_a_windfall_is_relative_to_the_account_not_the_book():
    small = _rows("SMALL", "2026-01-02", 10, 14, 100.0)
    small.append(["SMALL", pd.Timestamp("2026-06-01"), 1, 900.0])
    big = _rows("BIG", "2026-01-02", 10, 14, 5000.0)
    out = D.windfalls(_frame(small + big)).set_index("acct")
    assert out.loc["SMALL", "n_windfalls"] == 1
    assert out.loc["BIG", "n_windfalls"] == 0, \
        "a large routine deposit is not a windfall"


# ---- graceful behaviour when the client sent no file ----------------------

def test_find_file_returns_none_when_nothing_matches(tmp_path):
    (tmp_path / "ars_data").mkdir()
    (tmp_path / "ars_data" / "something_else.csv").write_text("a,b\n1,2\n")
    assert D.find_file(tmp_path, "1441") is None


def test_find_file_locates_the_file_wherever_it_landed(tmp_path):
    """The folder convention has moved before; a file that exists but is not
    found reads exactly like a file that was never delivered."""
    nested = tmp_path / "ars_data" / "1441"
    nested.mkdir(parents=True)
    target = nested / "1441_deposits_rolling365.csv"
    target.write_text("Acct Number,Date,Dep Count,Dep Amount\nA1,2026-01-01,1,5\n")
    assert D.find_file(tmp_path, "1441") == target


def test_the_newest_file_wins_when_a_client_is_re_sent(tmp_path):
    import os
    import time

    base = tmp_path / "ars_data"
    base.mkdir()
    old = base / "deposits_v1.csv"
    new = base / "deposits_v2.csv"
    for p in (old, new):
        p.write_text("Acct Number,Date,Dep Count,Dep Amount\nA1,2026-01-01,1,5\n")
    os.utime(old, (time.time() - 6000, time.time() - 6000))
    assert D.find_file(tmp_path, "1441") == new


def test_a_run_without_the_file_still_reports_the_deposit_conditions_as_skipped():
    """The absence must be visible on the output, not silently score fewer."""
    from ti.core.conditions import CONDITIONS

    labels = {c.label for c in CONDITIONS.values()}
    assert "Deposits slowing" in labels
    # "No recurring deposit" is deliberately NOT a scoring condition: payroll
    # lands in one account per member, so at account grain it flagged 97.3% of
    # RALLY's book. Same objection as "only one product relationship".
    assert "No recurring deposit" not in labels


def test_the_txn_loader_refuses_a_deposits_file_in_its_folder(tmp_path):
    """The rolling-365 deposits file lands beside the TRAN files often enough
    that the loader must not take it. "tran" is a substring match, so a name
    like 1441_tran_deposits_365.csv would otherwise be parsed positionally as
    8M rows of transactions -- producing garbage rather than an error."""
    from ti.transaction_intelligence import loader

    folder = tmp_path / "Txn Files" / "1441"
    folder.mkdir(parents=True)
    (folder / "1441_31004_[2026.04.05][07.16.16]_monthly_transactions_file.txt") \
        .write_text("x")
    (folder / "1441_tran_deposits_rolling365.csv").write_text("x")

    rpt = loader.LoadReport()
    found = loader.discover([folder], months=12, anchor=None, rpt=rpt)
    names = [p.name for p in found]
    assert any("transactions_file" in n for n in names)
    assert not any("deposits" in n for n in names), \
        "the deposits extract must not be read as a transaction file"
    assert any("deposits" in s for s in rpt.skipped), "the skip must be reported"


def test_the_real_rally_header_shape_loads(tmp_path):
    """The extract RALLY actually sends:

        hashed_account,DEPOSIT_AMOUNT,DEPOSIT_DATE

    Underscore separators, an all-caps spelling, no Dep Count column, and the
    account keyed by its HASH. Normalising whitespace but not underscores left
    every column unmapped, so the file parsed to 0 rows and 'No recurring
    deposit' fired on all 81,081 accounts of a real book.
    """
    path = tmp_path / "Rally_8-1-25to7-31-26_Deposits.csv"
    path.write_text(
        "hashed_account,DEPOSIT_AMOUNT,DEPOSIT_DATE\n"
        "042263353EB53C9EC1BE8263EABB9BD2F7F89738,500.00,2025-08-12 00:00:00.000\n"
        "E86E85087DE30FDEE6EED3FC1B29DB6C9724E7F5,1076.08,2025-08-12 00:00:00.000\n"
        "042263353EB53C9EC1BE8263EABB9BD2F7F89738,500.00,2025-08-26 00:00:00.000\n")
    rep = D.LoadReport()
    frame = D.load(path, None, rep)
    assert rep.rows == 3, f"expected 3 rows, got {rep.rows}: {rep.warnings}"
    assert rep.accounts == 2
    assert frame["dep_amount"].sum() == pytest.approx(2076.08)
    assert frame["dep_count"].eq(1).all(), "absent Dep Count defaults to 1"
    assert frame["acct"].iloc[0].startswith("042263353E")


def test_the_txn_loader_reads_rallys_unbracketed_file_dates(tmp_path):
    """RALLY sends `1100_507_combined transaction_9-8-25.txt`. The bracketed
    [YYYY.MM.DD] form is the core's own; twelve of RALLY's files were skipped
    as undated, which emptied the entire transaction chapter."""
    from ti.transaction_intelligence import loader

    cases = {
        "1100_507_combined  transaction_9-8-25.txt": (2025, 9, 8),
        "1100_507_combined transaction_10-7-25.txt": (2025, 10, 7),
        "1100_507_combined transaction_1-5-26.txt": (2026, 1, 5),
        "1615_31004_[2026.04.05][07.16.16]_monthly_transactions.txt": (2026, 4, 5),
    }
    for name, expected in cases.items():
        got = loader.file_date(tmp_path / name)
        assert got is not None, f"{name} read as undated"
        assert (got.year, got.month, got.day) == expected, f"{name} -> {got}"


def test_a_file_with_no_date_at_all_is_still_undated(tmp_path):
    from ti.transaction_intelligence import loader

    assert loader.file_date(tmp_path / "1100_transactions.txt") is None


def test_a_weekly_payroll_is_recognised():
    """Hourly staff are commonly paid weekly. Omitting a 7-day cadence made
    98.2% of RALLY's book read as having no recurring deposit -- a rule that
    could not see a whole class of payroll, not a fact about the credit union."""
    frame = _frame(_rows("WEEKLY", "2026-01-02", 40, 7, 900.0, jitter=0.03))
    assert bool(D.cadence(frame).iloc[0]["probable_direct_deposit"])


def test_pay_that_varies_with_hours_is_still_recognised():
    """A CV floor of 0.15 demanded a salary accurate to +/-15% every period."""
    frame = _frame(_rows("HOURLY", "2026-01-02", 26, 14, 1200.0, jitter=0.18,
                         seed=5))
    row = D.cadence(frame).iloc[0]
    assert row["amount_cv"] > 0.10
    assert bool(row["probable_direct_deposit"])


def test_the_join_reports_its_match_rate_and_ignores_case():
    """RALLY's file joined almost nothing and the only visible symptom was
    'no recurring deposit' on 97% of accounts -- indistinguishable from a
    finding. The match rate is now recorded, and both sides are upper-cased so
    a hash spelled in a different case still joins."""
    from ti.core.facts import attach_deposits, build_facts
    from ti.core.periods import Month

    odd = pd.DataFrame({"Acct Number": ["abc123", "DEF456", "ghi789"]})
    facts = build_facts(odd, {}, Month.from_tag("Jul26"))
    cadence = pd.DataFrame({
        "acct": ["ABC123", "def456"],          # opposite case on both
        "n_deposits": [12, 12], "median_gap_days": [14.0, 14.0],
        "amount_cv": [0.02, 0.02], "median_amount": [1500.0, 1200.0],
        "probable_direct_deposit": [True, True]})
    attach_deposits(facts, cadence, None)

    assert facts.deposit_match_pct == pytest.approx(66.7, abs=0.1)
    assert facts.frame["probable_direct_deposit"].tolist() == [True, True, False]


def test_a_join_that_matches_nothing_reports_zero_not_silence():
    from ti.core.facts import attach_deposits, build_facts
    from ti.core.periods import Month

    facts = build_facts(pd.DataFrame({"Acct Number": ["A1", "A2"]}), {},
                        Month.from_tag("Jul26"))
    attach_deposits(facts, pd.DataFrame({
        "acct": ["ZZZ"], "n_deposits": [12], "median_gap_days": [14.0],
        "amount_cv": [0.02], "median_amount": [100.0],
        "probable_direct_deposit": [True]}), None)
    assert facts.deposit_match_pct == 0.0


def _short(cached_rows: int, source_lines: int, skip: int = 1) -> bool:
    """The loader's own test: does the cache account for its source file."""
    from ti.transaction_intelligence import loader as L

    return L.is_short(cached_rows, source_lines, skip)


def test_rallys_short_caches_are_all_caught():
    """The real numbers. Nine files of 4.8-5.5m lines cached at 1,500,004."""
    for lines in (5_284_659, 4_867_303, 5_005_077, 4_848_236, 4_801_590,
                  5_533_492, 5_239_689, 5_426_070, 5_547_561):
        assert _short(1_500_004, lines), f"{lines:,} -> 1,500,004 not caught"


def test_a_chunk_multiple_test_would_have_missed_them():
    """Why the first version of this guard failed. 1,500,004 is four rows past
    a chunk boundary, so a modulo test printed the shortfall and did nothing."""
    from ti.transaction_intelligence import loader as L

    assert 1_500_004 % L.CHUNK_ROWS != 0


def test_a_healthy_cache_is_not_flagged():
    """The three good RALLY files, and the banner-line gap on the 1441 book."""
    for cached, lines in ((5_108_088, 5_108_089), (5_151_002, 5_151_002),
                          (5_254_788, 5_254_788), (23_668, 23_669),
                          (19_926, 19_927)):
        assert not _short(cached, lines), f"{cached:,}/{lines:,} false positive"


def test_a_tiny_file_cannot_trip_the_guard():
    """A five-line fixture with a three-line banner reads two rows. Without an
    absolute floor that is a 40% shortfall, and the guard ate a passing test."""
    assert not _short(2, 5, skip=3)
    assert not _short(0, 1, skip=1)
