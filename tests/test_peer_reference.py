"""The peer reference file (scripts/build_peer_reference.py): every peer figure in one dated file on the share.

Synthetic data only: 7001-7009 are invented clients and every name below is invented. Each test points RPE_DATA_ROOT at an
empty scratch root (Inputs, Outputs, Build Artifacts), as CI does.
"""
import csv
import datetime
import json
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "build"), os.path.join(REPO, "build", "ars_pipeline"),
                os.path.join(REPO, "build", "mrpc_pipeline"), os.path.join(REPO, "scripts")]

import build_peer_reference as BR                                # noqa: E402
import rpe_env                                                   # noqa: E402
from review_page import peer_pool as PP                          # noqa: E402

IDS = [str(7000 + i) for i in range(1, 10)]
NAMES = ["Zephyrville Savings", "Quillmont Credit Union", "Bramblecrest Bank", "Ostrander Federal", "Pellucid Trust",
         "Wrenfield Community", "Halvorsen Mutual", "Tamsin Valley Bank", "Ulverton Thrift"]
TODAY = datetime.date(2026, 11, 20)


@pytest.fixture
def root(tmp_path, monkeypatch):
    for d in ("Inputs", "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir()
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("RPE_PEER_TABLES_DIR", raising=False)
    PP._REFS.clear()
    PP._WEEKLY.clear()
    yield tmp_path
    PP._REFS.clear()
    PP._WEEKLY.clear()


def _rows(csv_path):
    with open(csv_path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ----------------------------------------------------------------- synthetic sources
def ars_packs(root, period="2026.10"):
    for i, cid in enumerate(IDS[:7]):
        d = root / "Build Artifacts" / "launcher" / period / cid
        d.mkdir(parents=True)
        m = {"activity_month": "Sep 2026", "month_completeness": {"pull_date": "2026-10-03"},
             "mail_summary": [["Mar26", 2000, 100 + 10 * i, 0, 0, 5.0 + i], ["Jun26", 2000, 120, 0, 0, 6.0]],
             "rege_pct": 40.0 + i, "rege_pool": 500, "book_active_pct": 60.0 + i, "ret_1yr": 85.0,
             "overall_take": 70.0 + i, "latest_resprate": 6.0, "take_new_pct": 80.0, "take_new_total": 50,
             "swipe_tier_total": [1000, 12000.0 + 100 * i, 400000.0]}
        (d / "metrics.json").write_text(json.dumps(m), encoding="utf-8")


def cp_packs(root):
    packs = root / "Build Artifacts" / "cashplease" / "packs"
    packs.mkdir(parents=True)
    for i, (cid, nm) in enumerate(zip(IDS[:6], NAMES)):
        months = [{"period_month": f"2026-{m:02d}", "loans": 10 + m} for m in range(1, 11)]
        d = {"client_id": cid, "client_name": nm, "source_file": "CashPleaseSummary 2026-11-17.xlsx",
             "report_generated": "11/17/2026 8:00:00 AM", "charge_off_pct": 0.04, "cancelled": None,
             "total": {"loans": 500}, "monthly": months,
             "metrics": {"peer_comparable": True, "loans_per_1k_dda": 20.0 + i, "dda_accounts": 1000,
                         "pct_loans_overdue": 0.01, "avg_loan_size": 400.0, "pct_loans_paid_off": 0.9,
                         "pct_loans_charged_off": 0.02}}
        (packs / f"{cid}_cashplease.json").write_text(json.dumps(d), encoding="utf-8")
    (packs / "peer_benchmark.json").write_text(json.dumps(
        {"cohort": "All Velocity CashPlease clients", "loans_per_1k_dda": 25.0, "charge_off_pct": 0.05,
         "avg_loan_size": 410.0, "avg_interest_per_loan": 30.0, "pct_loans_overdue": 0.02,
         "pct_loans_paid_off": 0.88, "pct_loans_charged_off": 0.03}), encoding="utf-8")
    ds = root / "Build Artifacts" / "perf_dashboard"
    ds.mkdir(parents=True)
    (ds / "dataset.json").write_text(json.dumps(
        {"generated": "2026-11-18 08:30", "cp_peer": {"cohort": "Current Velocity CashPlease clients",
                                                      "loans_per_1k_dda": 22.0, "charge_off_pct": None,
                                                      "avg_loan_size": 405.0, "pct_loans_overdue": 0.015}}),
        encoding="utf-8")


def rems_file(root):
    d = root / "Inputs" / "REMS"
    d.mkdir(parents=True)
    with open(d / "rems_responses 2026-11-03.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["client_id", "client_name", "response_year", "response_month", "num_responses", "num_opt_in"])
        for i, (cid, nm) in enumerate(zip(IDS[:6], NAMES)):
            for mo in range(1, 12):
                w.writerow([cid, nm, 2026, mo, 20, 5 + i])


class FakeWeekly:
    path = None

    def __init__(self, clients):
        self._c = clients
        self.tabs = list(clients)

    def client(self, cid):
        return self._c[cid]


def mrpc_weekly(monkeypatch):
    def tab(i):
        # A '*' roll-up for November, a month that had not ended when the weekly was generated on 11/17.
        months = [{"month": f"2026-{m:02d}", "platinum": 5 + i, "gold": 1, "business": 0} for m in range(1, 12)]
        return {"monthly": months, "open_with_debit": 2000, "all_cardholders": 1000, "active_cardholders": 300 + i,
                "take_rate_active": 0.1, "report_generated": "11/17/2026 10:01:45 AM"}
    wk = FakeWeekly({cid: tab(i) for i, cid in enumerate(IDS[:6])})
    monkeypatch.setattr(PP, "_weekly", lambda: wk)
    import peer_data as PD
    monkeypatch.setattr(PD, "mrpc_section", lambda cid, w: {})


def ics_sources(monkeypatch):
    import peer_data as PD
    monkeypatch.setattr(PP, "_vip_ids", lambda program: IDS[:3] if program == "ICS" else [])
    monkeypatch.setattr(PP, "_dda", lambda ctx: {cid: 1000 for cid in IDS})
    refs = {cid: {"2026-08": 4, "2026-09": 5, "2026-10": 6, "2026-11": 2} for cid in IDS[3:8]}
    monkeypatch.setattr(PP, "referrals_by_month", lambda: (refs, "2026-11-12"))
    monkeypatch.setattr(PD, "ics_section", lambda cid, c: {
        "trend": {"months": ["Aug 26", "Sep 26"], "referrals": [8, 9], "goal": [10, 10]}, "data_pull": "2026-10-27"})


# ----------------------------------------------------------------- the values are the consumers' values
def test_ars_rows_are_the_collectors_values_with_their_provenance(root):
    ars_packs(root)
    res = BR.compile_all("2026.10", ["ARS"], log=lambda *a: None)
    assert not res["failed"]
    coll = PP.collect_ars(PP.PeerCtx(client=BR.SENTINEL, period="2026.10"))
    want = {(p["id"], k): v for p in coll["peers"] for k, v in p["point"].items()}
    got = {(r["client_id"], r["metric_key"]): r["value"] for r in res["rows"] if r["period_basis"] != "month"
           and not r["metric_key"].startswith("metrics.")}
    assert got == pytest.approx(want) and len(got) >= 7 * 4
    r = next(r for r in res["rows"] if r["metric_key"] == "rege_pct" and r["client_id"] == IDS[0])
    assert r["period"] == "2026.09" and r["source_date"] == "2026-10-03" and r["month_complete"] == "n/a"
    assert r["source_file"] == f"Build Artifacts/launcher/2026.10/{IDS[0]}/metrics.json"
    assert "Live Review" in r["consumers"] and "How You Compare slide" in r["consumers"]
    resp = next(r for r in res["rows"] if r["metric_key"] == "resp_12m" and r["client_id"] == IDS[0])
    assert resp["period"] == "2026.09" and resp["month_complete"] == "yes"
    # Sheila in Claude's fields are recorded too, raw from the same packs.
    take = [r for r in res["rows"] if r["metric_key"] == "metrics.overall_take"]
    assert len(take) == 7 and "Sheila in Claude" in take[0]["consumers"]


def test_every_metric_a_peer_comparison_names_is_in_the_catalog(root):
    res = BR.compile_all("2026.10", ["ARS", "ICS", "MRPC", "CP", "REMS"], log=lambda *a: None)
    keys = {(e["program"], e["metric_key"]) for e in res["catalog"]}
    for program, (_c, metrics, _w) in PP.PROGRAMS.items():
        assert program in BR.COMPILERS, f"peer_pool has a program the reference does not compile: {program}"
        for spec in metrics:
            assert (program, spec["key"]) in keys
    import peer_slide
    for program, ks in peer_slide.METRICS.items():
        for k in ks:
            assert (program, k) in keys
    assert all(e["definition"] and e["unit"] and e["period_basis"] for e in res["catalog"])


def test_cashplease_rows_carry_no_name_and_the_cohorts_in_client_units(root):
    cp_packs(root)
    res = BR.compile_all("2026.11", ["CP"], log=lambda *a: None)
    blob = json.dumps(res["rows"])
    assert not any(nm in blob for nm in NAMES)
    over = next(r for r in res["rows"] if r["metric_key"] == "overdue" and r["client_id"] == IDS[0])
    assert over["value"] == pytest.approx(1.0) and over["source_file"] == "Inputs/CashPlease/CashPleaseSummary 2026-11-17.xlsx"
    assert over["source_date"] == "2026-11-17"
    per = next(r for r in res["rows"] if r["metric_key"] == "per_1k" and r["client_id"] == IDS[0])
    assert per["period"] == "2026.10" and per["month_complete"] == "yes"
    roll = {r["metric_key"]: r for r in res["rows"] if r["scope"] == "cohort" and r["segment"] == "all_tabs_rollup"}
    cur = {r["metric_key"]: r for r in res["rows"] if r["scope"] == "cohort" and r["segment"] == "current_clients"}
    assert roll["charge_off"]["value"] == pytest.approx(5.0) and roll["per_1k"]["value"] == pytest.approx(25.0)
    assert cur["per_1k"]["value"] == pytest.approx(22.0) and "charge_off" not in cur   # absent stays absent, never 0
    assert roll["per_1k"]["client_id"] == "" and cur["avg_loan"]["source_date"] == "2026-11-18"


def test_rems_rows_carry_no_name_and_name_the_window(root):
    rems_file(root)
    res = BR.compile_all("2026.11", ["REMS"], log=lambda *a: None)
    assert not any(nm in json.dumps(res["rows"]) for nm in NAMES)
    r = next(r for r in res["rows"] if r["metric_key"] == "pct_opt_in_12" and r["client_id"] == IDS[0])
    assert r["period"] == "2026.10" and r["value"] == pytest.approx(25.0) and r["month_complete"] == "yes"
    assert r["source_file"] == "Inputs/REMS/rems_responses 2026-11-03.csv"
    months = {r["period"] for r in res["rows"] if r["metric_key"] == "pct_opt_in"}
    assert "2026.11" not in months and "2026.10" in months


def test_a_month_that_had_not_ended_is_flagged_not_dropped(root, monkeypatch):
    mrpc_weekly(monkeypatch)
    res = BR.compile_all("2026.11", ["MRPC"], log=lambda *a: None)
    rows = [r for r in res["rows"] if r["metric_key"] == "enroll_per_1k" and r["client_id"] == IDS[0]]
    flag = {r["period"]: r["month_complete"] for r in rows}
    assert flag["2026.10"] == "yes" and flag["2026.11"] == "no"
    still = next(r for r in res["rows"] if r["metric_key"] == "still_active" and r["client_id"] == IDS[0])
    assert still["value"] == pytest.approx(30.0) and still["month_complete"] == "n/a"


def test_ics_per_1k_says_which_source_each_client_came_from(root, monkeypatch):
    ics_sources(monkeypatch)
    res = BR.compile_all("2026.11", ["ICS"], log=lambda *a: None)
    kinds = {r["client_id"]: r["source_kind"] for r in res["rows"] if r["metric_key"] == "per_1k"}
    assert kinds[IDS[0]].startswith("VIP ICS sheet") and kinds[IDS[4]].startswith("ICS referrals file")
    file_rows = [r for r in res["rows"] if r["metric_key"] == "per_1k" and r["client_id"] == IDS[4]]
    assert {r["period"] for r in file_rows} == {"2026.08", "2026.09", "2026.10"}   # November was in progress: not in the series
    assert all(r["month_complete"] == "yes" for r in file_rows)


def test_ils_rows_are_per_account_type(root):
    pytest.importorskip("pptx")
    try:
        from ils_review import peers_slides  # noqa: F401
    except Exception as exc:                               # the ILS package is changed on another branch; skip, never fail here
        pytest.skip(f"ils_review not importable: {exc}")
    d = root / "Build Artifacts" / "ils_analysis" / "peers"
    d.mkdir(parents=True)
    with open(d / "ils_peer_metrics.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["client_id", "accttype", "as_of", "open_accounts", "items365", "fees365", "users365", "source"])
        w.writerow([IDS[0], "Personal", "20260612", 1000, 2000, 50000.0, 150, "x.csv"])
        w.writerow([IDS[0], "Business", "20260612", 100, 50, 900.0, 10, "x.csv"])
    res = BR.compile_all("2026.11", ["ILS"], log=lambda *a: None)
    got = {(r["segment"], r["metric_key"]): r for r in res["rows"]}
    assert got[("personal", "items_per_1k")]["value"] == pytest.approx(2000.0)
    assert got[("business", "fees_per_acct")]["value"] == pytest.approx(9.0)
    assert got[("personal", "users_pct")]["period"] == "2026.06"


# ----------------------------------------------------------------- the file on the share
def test_dry_run_writes_nothing(root):
    ars_packs(root)
    assert BR.main(["--dry-run", "--programs", "ARS", "--period", "2026.10"], today=TODAY, log=lambda *a: None) == 0
    assert not (root / rpe_env.PEER_REFERENCE_DIRNAME).exists()


def test_write_is_dated_idempotent_and_never_touches_an_earlier_day(root):
    ars_packs(root)
    cp_packs(root)
    folder = root / rpe_env.PEER_REFERENCE_DIRNAME
    folder.mkdir()
    earlier = folder / "peer_metrics_2026-11-01.csv"
    earlier.write_text("an earlier compilation\n", encoding="utf-8")
    args = ["--programs", "ARS", "CP", "--period", "2026.10"]
    assert BR.main(args, today=TODAY, log=lambda *a: None) == 0
    dated = folder / "peer_metrics_2026-11-20.csv"
    latest = folder / BR.LATEST_NAME
    man = json.loads((folder / BR.MANIFEST_NAME).read_text(encoding="utf-8"))
    rows = _rows(dated)
    assert rows and list(rows[0]) == BR.COLUMNS and dated.read_bytes() == latest.read_bytes()
    assert man["dated_file"] == dated.name and man["rows"] == len(rows) and man["rows_by_program"]["CP"] > 0
    assert not any(nm in dated.read_text(encoding="utf-8") for nm in NAMES)
    stamp = dated.stat().st_mtime_ns
    assert BR.main(args, today=TODAY, log=lambda *a: None) == 0          # same day, same content: nothing rewritten
    assert dated.stat().st_mtime_ns == stamp
    assert BR.main(args, today=TODAY + datetime.timedelta(days=1), log=lambda *a: None) == 0
    assert (folder / "peer_metrics_2026-11-21.csv").exists() and dated.stat().st_mtime_ns == stamp
    assert earlier.read_text(encoding="utf-8") == "an earlier compilation\n"


def test_a_program_that_fails_stops_the_write_unless_partial_is_asked_for(root, monkeypatch):
    ars_packs(root)

    def boom(cat, period, notes):
        raise ValueError("synthetic failure")
    monkeypatch.setitem(BR.COMPILERS, "CP", boom)
    args = ["--programs", "ARS", "CP", "--period", "2026.10"]
    assert BR.main(args, today=TODAY, log=lambda *a: None) == 1
    assert not (root / rpe_env.PEER_REFERENCE_DIRNAME).exists()
    assert BR.main(args + ["--allow-partial"], today=TODAY, log=lambda *a: None) == 1
    man = json.loads((root / rpe_env.PEER_REFERENCE_DIRNAME / BR.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert "synthetic failure" in man["failed"]["CP"] and man["rows_by_program"]["ARS"] > 0
