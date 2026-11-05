"""R7 (2026-11-05): daily deposits, and what is spent in the days after a deposit.

ti/core/deposits/daily.py (the arithmetic), ti/monthly_analysis/deposit_daily.py (what is stated),
odd_sections.deposit_daily (the categories the Transaction Intelligence chapter uses) and the five
slides in ti/deck/deposit_slides.py, on synthetic frames only.
"""
import json
import os
import pathlib
import types

import numpy as np
import pandas as pd
import pytest

from ti.core.deposits import daily as D
from ti.monthly_analysis import deposit_daily as DD

START = pd.Timestamp("2025-08-01")       # a Friday
DAYS = 364
N = 60


def _deposits(n=N, every=14):
    """Every account paid $1,000 every other Friday, plus a $50 credit on the 15th."""
    rows = []
    for i in range(n):
        for k in range(0, DAYS, every):
            rows.append([f"A{i}", START + pd.Timedelta(days=k), 1, 1000.0])
        for m in pd.date_range(START, periods=12, freq="MS"):
            rows.append([f"A{i}", m + pd.Timedelta(days=14), 1, 50.0])
    return pd.DataFrame(rows, columns=["acct", "date", "dep_count", "dep_amount"])


def _txn(n=N):
    """Each account: a $40 grocery card purchase every day, and a $120 Affirm payment the day after
    each payday (BNPL, timed). Card rows carry MCC 5411 (grocery)."""
    rows = []
    for i in range(n):
        acct = f"A{i}"
        for k in range(DAYS):
            day = START + pd.Timedelta(days=k)
            rows.append([day, acct, "SIG", -40.0, "5411", "SAFEWAY #123", "SAFEWAY"])
            if k % 14 == 1:
                rows.append([day, acct, "ACH", -120.0, None, "AFFIRM INC PAYMENT", "AFFIRM INC PAYMENT"])
    return pd.DataFrame(rows, columns=["transaction_date", "primary_account_num", "transaction_type",
                                       "amount", "mcc_code", "merchant_name", "merchant_key"])


def _categories(txn):
    card = pd.Series(np.where(txn["transaction_type"] == "SIG", "Grocery", None), index=txn.index)
    fin = pd.Series(np.where(txn["merchant_name"].str.startswith("AFFIRM"), D.BNPL, None),
                    index=txn.index)
    return card.where(card.notna()), fin.where(fin.notna())


# ------------------------------------------------------------------ the daily series
def test_daily_counts_every_calendar_day_and_sums_count_amount_accounts():
    raw = _deposits()
    d = D.daily(raw)
    assert len(d) == (raw["date"].max() - raw["date"].min()).days + 1
    first = d.iloc[0]
    assert (first["deposits"], first["dollars"], first["accounts"]) == (N, N * 1000, N)
    assert d["dollars"].sum() == pytest.approx(raw["dep_amount"].sum())
    # a day with nothing posted is a zero row, not a missing one
    assert (d["dollars"] == 0).sum() > 0


def test_daily_keeps_at_most_366_days_and_drops_reversals():
    raw = pd.DataFrame({"acct": ["A", "A", "B"], "date": pd.to_datetime(["2024-01-01", "2025-06-30", "2025-06-30"]),
                        "dep_count": [1, 1, 1], "dep_amount": [10.0, 20.0, -5.0]})
    d = D.daily(raw)
    assert len(d) == D.MAX_DAYS
    assert d.iloc[-1]["dollars"] == 20 and d.iloc[-1]["accounts"] == 1


def test_summary_patterns_and_top_days():
    d = D.daily(_deposits())
    s = D.summary(d)
    assert s["avg_dollars"] == round(d["dollars"].mean())
    assert s["median_dollars"] == round(d["dollars"].median())
    wd = {r[0]: r for r in D.weekday(d)}
    assert max(wd.values(), key=lambda r: r[4])[0] == "Fri"
    dom = {r[0]: r for r in D.day_of_month(d)}
    assert dom[15][3] > 0 and len(dom) == 31
    top = D.top_days(d)
    assert len(top) == 10 and top[0][1] == "Fri" and top[0][3] >= N * 1000


# ------------------------------------------------------------------ deposit-to-outflow timing
def test_bnpl_paid_the_day_after_payday_is_timed_and_daily_groceries_are_not():
    raw, txn = _deposits(), _txn()
    card, fin = _categories(txn)
    t = D.timing(raw, D.flows(txn, card, fin))
    rows = {r[0]: r for r in t["rows"]}
    assert t["accounts"] == N
    bnpl, grocery, every = rows[D.BNPL], rows["Grocery"], rows[D.ALL]
    assert bnpl[5] == 100.0 and bnpl[7] > 2.5          # all of it within 0-3 days
    assert 0.9 <= grocery[7] <= 1.1                    # an even spread reads as an even spread
    assert grocery[6] == pytest.approx(bnpl[6], abs=0.1)
    assert every[8] and t["rows"][0][0] == D.BNPL      # ranked first
    # the expected share is the window's share of days: 4 days in 14, plus the 15th's credits
    assert 28 <= t["expected"] <= 45


def test_large_is_each_accounts_own_90th_percentile():
    raw, txn = _deposits(), _txn()
    card, fin = _categories(txn)
    rows = {r[0]: r for r in D.timing(raw, D.flows(txn, card, fin))["rows"]}
    large = rows[D.LARGE]
    # $120 BNPL payments (25 in the days both files cover) are the only ones above p90; groceries are all $40
    assert large[3] == N * 25 and large[5] == 100.0


def test_a_small_base_gets_no_ratio_and_the_base_is_stated():
    raw, txn = _deposits(n=10), _txn(n=10)
    card, fin = _categories(txn)
    rows = {r[0]: r for r in D.timing(raw, D.flows(txn, card, fin))["rows"]}
    assert rows[D.BNPL][2] == 10 and rows[D.BNPL][7] is None and rows[D.BNPL][8] is False


def test_no_common_account_or_no_common_days_is_empty():
    raw, txn = _deposits(), _txn()
    txn = txn.assign(primary_account_num="Z" + txn["primary_account_num"])
    assert D.timing(raw, D.flows(txn, None, None)) == {}
    txn2 = _txn().assign(transaction_date=pd.Timestamp("2030-01-01"))
    assert D.timing(raw, D.flows(txn2, None, None)) == {}


# ------------------------------------------------------------------ the section
def test_compute_without_deposits_is_empty_and_without_transactions_says_why():
    assert DD.compute({}, print) == {}
    warned = []
    out = DD.compute({"_deposit_raw": _deposits()}, warned.append)
    assert out["dep_daily"] and out["dep_daily_columns"] == ["date", "deposits", "dollars", "accounts"]
    assert out["dep_timing_skipped"] == "no transaction files for this period"
    assert "dep_timing" not in out
    assert all(len(r) == 4 for r in out["dep_daily"]) and len(out["dep_daily"]) <= 366
    for k in ("dep_daily_weekday", "dep_daily_dom", "dep_daily_top"):
        assert len(out[k][0]) == len(out[k + "_columns"])
    json.dumps(out)


def test_compute_with_both_files_stores_the_overlay_series_compactly():
    txn = _txn()
    card, fin = _categories(txn)
    out = DD.compute({"_deposit_raw": _deposits()}, print, txn=txn, card_category=card, fin_category=fin)
    assert len(out["dep_timing"][0]) == len(out["dep_timing_columns"])
    by = out["dep_daily_by_category"]
    assert set(by) >= {D.ALL, D.BNPL, "Grocery", D.LARGE}
    assert len(by["Grocery"]) <= 366 and by[D.BNPL][0][1] == N
    assert out["dep_timing_window_days"] == 3 and "90th percentile" in out["dep_timing_large_rule"]
    json.dumps(out)


def test_the_section_reads_the_ti_chapters_categories_from_the_real_dictionaries():
    """odd_sections.deposit_daily on a context: merchant categories from MCC, BNPL from the
    financial-services patterns (AFFIRM)."""
    from ti import odd_sections
    txn = _txn()
    ctx = types.SimpleNamespace(source_dir=None, config={"_deposit_raw": _deposits()}, shared={},
                                txn=txn, warnings=[])
    ctx.warn = ctx.warnings.append
    out = odd_sections.deposit_daily(ctx)
    rows = {r[0]: r for r in out["dep_timing"]}
    assert D.BNPL in rows and rows[D.BNPL][7] > 2.5
    assert any(r[1] == "card" for r in out["dep_timing"])


# ------------------------------------------------------------------ the slides
def _harness():
    seen = {"slide": [], "rail": [], "chart": [], "picture": []}

    def _slide(pair, fallback):
        seen["slide"].append((pair, fallback))
        return object(), 1.8

    def _chart(name, fn, *a, **k):
        seen["chart"].append((name, fn.__name__))
        return pathlib.Path(f"{name}.png")

    from ti.deck import charts
    return seen, {"slide": _slide, "chart": _chart, "charts": charts,
                  "rail": lambda *a, **k: seen["rail"].append(a[1]),
                  "picture": lambda *a, **k: seen["picture"].append((a, k))}


def _metrics(with_txn=True):
    txn = _txn()
    card, fin = _categories(txn)
    out = DD.compute({"_deposit_raw": _deposits()}, print, **(
        dict(txn=txn, card_category=card, fin_category=fin) if with_txn else {}))
    out.update({"dep_match_pct": 90.0, "dep_scored_n": 60})
    return out


def _builders():
    from ti.deck import deposit_slides as S
    return (S.daily_deposits, S.deposit_timing, S.deposit_overlay_first,
            S.deposit_overlay_second, S.deposit_overlay_bnpl)


def test_the_slides_draw_with_true_headlines():
    seen, h = _harness()
    t = _metrics()
    S = _builders()
    assert S[0](h, t) is None and S[1](h, t) is None and S[2](h, t) is None and S[4](h, t) is None
    # one ranked category besides BNPL (groceries; Large transactions is ranked too)
    heads = [p[0] for p, _ in seen["slide"]]
    assert heads[0].endswith("Fris bring %.1fx that" % (max(r[4] for r in t["dep_daily_weekday"]) / 100))
    assert heads[1].startswith(f"{D.BNPL}: 100% of its dollars go out within 3 days")
    assert "of Buy Now Pay Later dollars go out within 3 days" in heads[3]
    assert all(call[1].get("rail") is True for call in seen["picture"])
    assert [f for _, f in seen["chart"]][:2] == ["daily_columns", "dumbbell"]


def test_no_deposits_file_declines_every_new_slide_with_the_chapter_reason():
    seen, h = _harness()
    assert all(fn(h, {}) == f"{fn_title(fn)} (no deposits file)" for fn in _builders())
    assert not seen["slide"]


def fn_title(fn):
    from ti.chapters.deposits import TITLES
    return TITLES[fn.__name__]


def test_no_transaction_file_declines_the_timing_slides_with_the_reason_but_draws_the_daily_one():
    seen, h = _harness()
    t = _metrics(with_txn=False)
    S = _builders()
    assert S[0](h, t) is None
    for fn in S[1:]:
        assert fn(h, t).endswith("(no transaction files for this period)")
    assert len(seen["slide"]) == 1


def test_a_short_transaction_load_declines_the_timing_slides():
    seen, h = _harness()
    t = dict(_metrics(), dep_competition_skipped="short", dep_txn_short_months=3)
    assert all("short in 3 month(s)" in fn(h, t) for fn in _builders()[1:])


def test_the_charts_render(tmp_path):
    from ti.deck import charts
    t = _metrics()
    assert charts.daily_columns([[r[0], r[2]] for r in t["dep_daily"]], tmp_path / "a.png").is_file()
    spend = {r[0]: r[2] for r in t["dep_daily_by_category"][D.BNPL]}
    rows = [[r[0], r[2], spend.get(r[0], 0)] for r in t["dep_daily"][-91:]]
    assert charts.daily_overlay(rows, tmp_path / "b.png", l2="BNPL").is_file()


def test_the_slides_are_registered_and_kept():
    from ti.chapters import deposits
    reg = json.load(open(os.path.join(os.path.dirname(__file__), "..", "build", "ars_pipeline", "ti",
                                      "slides.json"), encoding="utf-8"))
    for fn in _builders():
        title = deposits.TITLES[fn.__name__]
        assert reg["slides"][title] == "keep" and title in reg["_by_chapter"]["Deposits"]
