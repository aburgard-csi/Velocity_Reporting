"""Peer tables: ICS revenue per account per month from the workbooks, and the ARS rows read from the data packs.

Synthetic data only: 9999 is the client, 7001-7009 the invented peers. Nothing here needs the share.
"""
import json
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "build"), os.path.join(REPO, "build", "ars_pipeline"),
                os.path.join(REPO, "build", "ics_pipeline"), os.path.join(REPO, "scripts")]

import peer_compare as PC                                        # noqa: E402
import peer_tables as PT                                         # noqa: E402
from review_page import peer_pool                                # noqa: E402


# ----------------------------------------------------------------- ICS
def _mdf(n=12, opened=100, ic=50.0, sp=30.0, nsf=20.0, other=5.0):
    return {"months": [f"M{i}" for i in range(n)], "accounts_opened": [opened] * n,
            "interchange": [ic] * n, "spread": [sp] * n, "nsf_od": [nsf] * n, "other_fees": [other] * n}


def test_ics_revenue_is_the_decks_arithmetic():
    mdf = _mdf()
    v = PT.ics_revenue(mdf)
    am = sum(100 * (12 - i) for i in range(12))                       # build_ics_gen: accounts_opened[i] * (n - i)
    assert v["account_months"] == am
    assert v["rev_total"] == pytest.approx((12 * (50 + 30 + 20 + 5)) / am)
    assert v["rev_interchange"] == pytest.approx(12 * 50 / am)
    assert v["rev_nsf_od"] == pytest.approx(12 * 25 / am)             # NSF/OD and other fees are the deck's one bucket
    assert v["rev_spread"] == pytest.approx(12 * 30 / am)


def test_ics_revenue_matches_the_deck_chart_module_on_a_twelve_cohort_sheet():
    import ics_charts_gen as CH
    mdf = _mdf()
    d = {"monthly_detail": {k: mdf[k] for k in ("months", "accounts_opened")}}
    assert PT.ics_revenue(mdf)["account_months"] == CH.acct_months(d)


def test_ics_revenue_leaves_out_a_source_the_workbook_never_filled():
    v = PT.ics_revenue(_mdf(ic=0.0))
    assert "rev_interchange" not in v and "rev_total" in v
    assert PT.ics_revenue(_mdf(ic=0, sp=0, nsf=0, other=0)).get("rev_total") is None


def test_ics_revenue_needs_enough_account_months():
    assert PT.ics_revenue(_mdf(n=3, opened=10)) is None
    assert PT.ics_revenue({}) is None


def test_newest_workbook_per_client(tmp_path):
    for n in ("1111-2026.08-A-Invitation Checking Workbook v1.7.1.xlsx", "1111-2026.10-A-Invitation Checking Workbook v1.7.1.xlsx",
              "1111-2026.10-A-Invitation Checking Workbook v1.7.2.xlsx", "~$1111-2026.10-A.xlsx", "2222-2026.09-B-Workbook.xlsx", "notes.xlsx"):
        (tmp_path / n).write_bytes(b"x")
    got = PT.newest_ics_workbooks(tmp_path)
    assert os.path.basename(got["1111"][1]).endswith("v1.7.2.xlsx") and got["1111"][0] == "2026.10"
    assert set(got) == {"1111", "2222"}


def test_workbook_rows_are_cached_until_the_file_changes(tmp_path):
    wb = tmp_path / "wb"
    wb.mkdir()
    f = wb / "1111-2026.10-A-Workbook.xlsx"
    f.write_bytes(b"one")
    calls = []

    def read(path):
        calls.append(path)
        return _mdf(), "2026-09"

    cache = tmp_path / "cache"
    a = PT.ics_revenue_rows(folder=wb, cache=cache, read=read)
    b = PT.ics_revenue_rows(folder=wb, cache=cache, read=read)
    assert len(calls) == 1 and a == b and a["1111"]["month"] == "2026-09"
    f.write_bytes(b"changed and longer")
    PT.ics_revenue_rows(folder=wb, cache=cache, read=read)
    assert len(calls) == 2
    assert PT.ics_revenue_rows(folder=wb, cache=cache, read=read, refresh=False)["1111"]["period"] == "2026.10"


def test_an_unreadable_workbook_is_a_client_with_no_row(tmp_path):
    wb = tmp_path / "wb"
    wb.mkdir()
    (wb / "1111-2026.10-A-Workbook.xlsx").write_bytes(b"x")

    def read(path):
        raise SystemExit("ERROR: no dated month columns")

    assert PT.ics_revenue_rows(folder=wb, cache=tmp_path / "c", read=read) == {}


def _ics_ctx(tmp_path, client="9999", period="2026.10"):
    wb = tmp_path / "wb"
    wb.mkdir(exist_ok=True)
    return peer_pool.PeerCtx(client, period, root=tmp_path / "ba", ics_dir=wb)


def test_ics_peers_carry_revenue_and_the_client_needs_a_workbook_for_the_period(tmp_path, monkeypatch):
    ctx = _ics_ctx(tmp_path)
    for i, cid in enumerate(["9999"] + [str(7000 + k) for k in range(1, 8)]):
        per = "2026.10" if cid != "9999" else "2026.08"          # the client's workbook is two months old: not current
        (ctx.ics_dir / f"{cid}-{per}-X-Workbook.xlsx").write_bytes(b"x" * (i + 1))
    monkeypatch.setattr(PT, "_read_workbook", lambda path: (_mdf(ic=40.0 + 5 * int(os.path.basename(str(path))[3]) ), "2026-09"))
    monkeypatch.setattr(peer_pool, "_vip_ids", lambda program: [])
    monkeypatch.setattr(peer_pool, "referrals_by_month", lambda: ({}, None))
    coll = peer_pool.collect_ics(ctx)
    assert coll["n_pool"] == 7
    assert "rev_total" not in coll["me"]["point"]                    # a carried-forward figure is not shown for the client
    assert all("rev_total" in p["point"] for p in coll["peers"])
    ev = PC.evaluate(coll, peer_pool.ICS_METRICS, "ICS")
    assert any("this client has no current figure" in x for x in ev["left"])


def test_ics_peer_with_an_old_workbook_is_left_out(tmp_path, monkeypatch):
    ctx = _ics_ctx(tmp_path)
    for cid, per in (("9999", "2026.10"), ("7001", "2026.10"), ("7002", "2026.05")):
        (ctx.ics_dir / f"{cid}-{per}-X-Workbook.xlsx").write_bytes(b"x" + cid.encode())
    monkeypatch.setattr(PT, "_read_workbook", lambda path: (_mdf(), "2026-09"))
    monkeypatch.setattr(peer_pool, "_vip_ids", lambda program: [])
    monkeypatch.setattr(peer_pool, "referrals_by_month", lambda: ({}, None))
    coll = peer_pool.collect_ics(ctx)
    ids = {p["id"] for p in coll["peers"] if "rev_total" in p["point"]}
    assert ids == {"7001"}


# ----------------------------------------------------------------- ARS
def pack(resp=10.0, sent=5000, activity="Sep 2026", gain=(500, 1000), movement=(100, 300, 400, 200), **kw):
    m = {"activity_month": activity,
         "mail_summary": [["Aug 2026", sent, round(sent * resp / 100), 3.0, 14.0, resp],
                          ["Jun 2026", sent, round(sent * resp / 100), 3.0, 14.0, resp + 1],
                          ["Jun 2025", sent, round(sent * resp / 100), 3.0, 14.0, 99.0]],      # outside the 12 months
         "ba_spend_before": gain[0], "ba_spend_after": gain[1], "ba_before_months": 3, "ba_after_months": 6, "ba_n_mailings": 4,
         "movement": [["First Response", movement[0]], ["Improved", movement[1]], ["Same", movement[2]], ["Declined", movement[3]]],
         "swipe_tier_total": [10000, 250000, 12000000, 400], "rege_pct": 28.0, "rege_pool": 9000, "rege_new_pct": 35.0, "rege_new_pool": 800,
         "take_new_pct": 90.0, "take_new_total": 700, "book_active_pct": 75.0, "ret_1yr": 85.0, "n_eligible": 10000}
    m.update(kw)
    return m


def test_ars_metrics_read_the_decks_own_figures():
    r = PT.ars_metrics(pack(), {"monthly_rev_last12": [[f"M{i}", 1.0] for i in range(11)] + [["Sep 2026", 1.0]], "monthly_rev_avg12": 20000})
    p = r["point"]
    assert p["resp_12m"] == pytest.approx(100.0 * (2 * 500) / 10000)                 # two mailings inside the window, pooled
    assert p["spend_gain"] == pytest.approx(100.0) and p["spend_after"] == 1000
    assert p["moved_up"] == pytest.approx(100.0 * 300 / 900)                         # Improved / (Improved + Same + Declined)
    assert p["swipes_per_acct"] == 25.0 and p["spend_per_acct"] == 1200.0
    assert p["rev_per_1k"] == pytest.approx(2000.0) and r["rev_month"] == "Sep 2026"
    assert r["series"]["resp_rate"]["Aug 2026"] == 10.0 and r["activity"] == "Sep 2026"


def test_ars_before_after_counts_only_on_the_three_and_six_month_windows():
    assert "spend_gain" not in PT.ars_metrics(pack(ba_after_months=3))["point"]
    assert "spend_gain" not in PT.ars_metrics(pack(gain=(0, 900)))["point"]


def test_ars_small_samples_are_not_rates():
    p = PT.ars_metrics(pack(sent=300))["point"]
    assert "resp_12m" not in p
    assert PT.ars_metrics(pack(sent=300))["series"]["resp_rate"] == {}
    assert "moved_up" not in PT.ars_metrics(pack(movement=(0, 10, 20, 10)))["point"]
    assert "rege_new_pct" not in PT.ars_metrics(pack(rege_new_pool=50))["point"]


def _write(root, period, cid, m, base=None):
    d = root / "launcher" / period / cid
    d.mkdir(parents=True)
    (d / "metrics.json").write_text(json.dumps(m), encoding="utf-8")
    if base is not None:
        (d / "base.json").write_text(json.dumps(base), encoding="utf-8")


def test_the_newest_pack_at_or_before_the_period_is_the_clients_row(tmp_path):
    _write(tmp_path, "2026.09", "7001", pack(resp=8.0))
    _write(tmp_path, "2026.10", "7001", pack(resp=9.0))
    _write(tmp_path, "2026.11", "7001", pack(resp=11.0))
    assert PT.ars_rows(tmp_path, "2026.10")["7001"]["pack_period"] == "2026.10"
    assert PT.ars_rows(tmp_path)["7001"]["pack_period"] == "2026.11"
    assert PT.ars_rows(tmp_path, "2026.08") == {}


def test_collect_ars_snapshots_need_the_clients_extract_month(tmp_path):
    for i in range(1, 8):
        _write(tmp_path, "2026.10", str(7000 + i), pack(resp=5.0 + i, activity="Sep 2026" if i != 7 else "Aug 2026"))
    ctx = peer_pool.PeerCtx("9999", "2026.10", tmp_path, own={"metrics": pack(resp=9.0)})
    coll = peer_pool.collect_ars(ctx)
    assert coll["n_pool"] == 7 and coll["me"]["point"]["resp_12m"] == pytest.approx(9.0)
    stale = next(p for p in coll["peers"] if p["id"] == "7007")
    assert stale["point"] == {} and stale["series"]["resp_rate"]               # its by-mailing series still aligns by month
    ev = PC.evaluate(coll, peer_pool.ARS_METRICS, "ARS")
    byk = {i["spec"]["key"]: i["c"] for i in ev["items"]}
    assert byk["resp_12m"]["n"] == 6 and byk["resp_12m"]["total"] == 7
    assert byk["resp_rate"]["n"] == 7                                          # Aug 2026 mailing: all seven peers


def test_collect_ars_with_too_few_peers_says_so(tmp_path):
    for i in range(1, 4):
        _write(tmp_path, "2026.10", str(7000 + i), pack())
    coll = peer_pool.collect_ars(peer_pool.PeerCtx("9999", "2026.10", tmp_path, own={"metrics": pack()}))
    ev = PC.evaluate(coll, peer_pool.ARS_METRICS, "ARS")
    assert ev["items"] == [] and "at least 5 other clients on ARS" in ev["unavailable"]
