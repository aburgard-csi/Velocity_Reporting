"""The TI transaction window (build/ars_pipeline/ti/window.py): the last N COMPLETED months
before the cycle, through the last day of the previous month, whatever the files or the ODD
carry. Pinned: the bounds, N's precedence and validation, the early-run warning, rows outside
the window left out, an empty month warned, and slide copy that says the real window.
"""
import datetime as dt
import os
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ("build", "build/ars_pipeline"):
    sys.path.insert(0, os.path.join(REPO, p))

import ti_build  # noqa: E402
from ti import window  # noqa: E402
from ti.deck import labels  # noqa: E402
from ti.transaction_intelligence.loader import LoadReport  # noqa: E402


def test_the_window_ends_with_the_previous_month():
    assert window.end_month("2026.11") == pd.Timestamp("2026-10-01")
    assert window.end_month("2026.01") == pd.Timestamp("2025-12-01")
    assert window.bounds("2026.11", 12) == (pd.Timestamp("2025-11-01"), pd.Timestamp("2026-11-01"))
    assert window.bounds("2026.11", 1) == (pd.Timestamp("2026-10-01"), pd.Timestamp("2026-11-01"))
    assert window.bounds("2026.03", 3) == (pd.Timestamp("2025-12-01"), pd.Timestamp("2026-03-01"))
    assert len(window.month_starts("2026.11", 18)) == 18


def test_describe_names_the_months():
    d = window.describe("2026.11", 6)
    assert d == {"txn_window_months": 6, "txn_window_start": "2026-05-01",
                 "txn_window_end": "2026-10-31",
                 "txn_window_label": "last 6 months (May 2026 to Oct 2026)"}


def test_n_precedence_and_validation(monkeypatch):
    monkeypatch.delenv(window.ENV_KEY, raising=False)
    assert window.months_for({}) == 12
    assert window.months_for({"TxnWindowMonths": "6"}) == 6
    monkeypatch.setenv(window.ENV_KEY, "3")
    assert window.months_for({"TxnWindowMonths": 6}) == 3
    assert window.months_for({"TxnWindowMonths": 6}, override=1) == 1
    with pytest.raises(ValueError):
        window.months_for({}, override=0)
    monkeypatch.setenv(window.ENV_KEY, "twelve")
    with pytest.raises(ValueError):
        window.months_for({})


def test_a_run_before_the_4th_is_warned():
    assert window.early_run_warning("2026.11", dt.date(2026, 11, 3))
    assert window.early_run_warning("2026.11", dt.date(2026, 11, 4)) is None
    assert window.early_run_warning("2026.10", dt.date(2026, 11, 2)) is None   # a past cycle


def test_slide_words_follow_the_window():
    assert labels.window({"txn_window_months": 12}) == "in the last 12 months"
    assert labels.window({"txn_window_months": 3}, prefix="over") == "over the last 3 months"
    assert labels.window({"txn_window_months": 1}, prefix="") == "last month"
    assert labels.window({"txn_months_covered": 9}) == "in the last 9 months"
    assert labels.window({}) == "in the last 12 months"
    assert labels.window_title({"txn_window_months": 6}) == "Last 6 months"


def _ctx():
    anchor = SimpleNamespace(year=2026, month=10, iso="2026-10")
    return SimpleNamespace(client_id="9999", anchor=anchor, frame=pd.DataFrame(), config={},
                           txn=None, txn_report=None, anchor_ts=None, lenses=None, txn_window=None)


def _attach(monkeypatch, rows, months, period="2026.11"):
    import rpe_env
    from ti import txn_stage
    from ti.transaction_intelligence import lens
    seen = {}

    def load(cid, n, anchor, log=print):
        seen["anchor"], seen["months"] = anchor, n
        return rows.copy(), LoadReport(rows=len(rows))
    monkeypatch.setattr(rpe_env, "txn_files", lambda cid: ["one.csv"])
    monkeypatch.setattr(txn_stage, "load", load)
    monkeypatch.setattr(lens, "build", lambda *a, **k: "lenses")
    warnings = []
    ctx = ti_build.attach_txn(_ctx(), warnings, months=months, period=period)
    return ctx, warnings, seen


def test_rows_outside_the_window_are_left_out(monkeypatch):
    rows = pd.DataFrame({"transaction_date": pd.to_datetime(
        ["2026-07-31", "2026-08-01", "2026-09-15", "2026-10-31", "2026-11-02"]),
        "amount": [1, 2, 3, 4, 5]})
    ctx, warnings, seen = _attach(monkeypatch, rows, months=3)
    assert seen == {"anchor": pd.Timestamp("2026-10-31"), "months": 3}
    assert ctx.txn["amount"].tolist() == [2, 3, 4]
    assert ctx.txn_window["txn_window_end"] == "2026-10-31"
    assert ctx.txn_window["txn_window_missing"] == []
    assert any("2 transaction row(s)" in w for w in warnings)


def test_a_month_with_no_rows_is_named(monkeypatch):
    rows = pd.DataFrame({"transaction_date": pd.to_datetime(["2026-08-10", "2026-10-10"]),
                         "amount": [1, 2]})
    ctx, warnings, _ = _attach(monkeypatch, rows, months=3)
    assert ctx.txn_window["txn_window_missing"] == ["Sep 2026"]
    assert any("no transaction rows for Sep 2026" in w for w in warnings)


def test_the_window_follows_the_cycle_not_the_odd(monkeypatch):
    rows = pd.DataFrame({"transaction_date": pd.to_datetime(["2026-11-10"]), "amount": [1]})
    ctx, warnings, seen = _attach(monkeypatch, rows, months=1, period="2026.12")
    assert seen["anchor"] == pd.Timestamp("2026-11-30")
    assert any("the ODD runs to 2026-10" in w for w in warnings)
    assert len(ctx.txn) == 1


def test_odd_months_after_the_window_are_left_out():
    from ti.core.odd_transform import transform_odd
    raw = pd.DataFrame({"Acct Number": ["1", "2"]})
    for mon in ("Aug26", "Sep26", "Oct26", "Nov26"):
        for suf in ("PIN $", "Sig $", "PIN #", "Sig #"):
            raw[f"{mon} {suf}"] = [1.0, 2.0]
    raw["Dec26 Mail"] = ["A", "B"]                                    # the mail track runs ahead, kept
    out, rpt = transform_odd(raw, end_month=pd.Timestamp("2026-10-01"))
    assert rpt.data_month == pd.Timestamp("2026-10-01")
    assert not any(c.startswith("Nov26") for c in out.columns) and "Dec26 Mail" in out.columns
    assert out["last 3-mon spend"].tolist() == [6.0, 12.0]          # Aug..Oct, not Sep..Nov
    assert any("4 month column(s) dated after Oct 2026" in w for w in rpt.warnings)
    # an ODD that stops short of the window end is named
    _, short = transform_odd(raw, end_month=pd.Timestamp("2026-12-01"))
    assert any("newest month is Nov 2026, not Dec 2026" in w for w in short.warnings)


def test_the_launcher_checks_the_clients_own_n(monkeypatch, tmp_path):
    sys.path.insert(0, os.path.join(REPO, "scripts"))
    import ars_launcher as L
    ti_config = L._ti_modules()[3]
    monkeypatch.delenv(window.ENV_KEY, raising=False)
    cfg = tmp_path / "clients_config.json"
    cfg.write_text('{"1441": {"TxnWindowMonths": 3}}', encoding="utf-8")
    monkeypatch.setattr(ti_config, "config_path", lambda: cfg)
    assert L.txn_window_months("1441") == 3
    monkeypatch.setattr(L.R, "txn_files", lambda cid: [])
    _, months = L.txn_months_on_hand("1441", "2026.11")
    assert [L._month_label(n) for n in months] == ["Aug 26", "Sep 26", "Oct 26"]
    cfg.write_text('{"1441": {"TxnWindowMonths": "0"}}', encoding="utf-8")
    with pytest.raises(ValueError):
        L.txn_window_months("1441")
