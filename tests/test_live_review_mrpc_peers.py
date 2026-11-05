"""Live Review's MRPC peer comparison uses every client in the weekly, not just the VIP sheets.

Aaron, 2026-11-03: "we must have more than 6 MRPC clients". The weekly (MRPCEnrollmentSummary) has a tab for each of about 26
clients with monthly enrollments and the open accounts with a debit card; the goal-based measure needs a VIP sheet, this one does not.
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "scripts"), os.path.join(REPO, "build"), os.path.join(REPO, "build", "ars_pipeline"), os.path.join(REPO, "tests")]

from review_page import peer_pool   # noqa: E402

CID = "9999"


class FakeWeekly:
    def __init__(self, clients):
        self._c = clients
        self.tabs = list(clients)

    def client(self, cid):
        return self._c[cid]


def tab(open_debit, per_month, last="2026-09", months=24, active=0.3):
    y, m = int(last[:4]), int(last[5:7])
    out = []
    for i in range(months):
        yy, mm = divmod(y * 12 + (m - 1) - i, 12)
        out.append({"month": "%04d-%02d" % (yy, mm + 1), "platinum": per_month, "gold": 0, "business": 0})
    return {"monthly": list(reversed(out)), "open_with_debit": open_debit, "all_cardholders": 1000, "active_cardholders": int(1000 * active),
            "take_rate_active": 0.1, "report_generated": "11/1/2026 10:01:45 AM"}


def make(monkeypatch, clients):
    wk = FakeWeekly(clients)
    monkeypatch.setattr(peer_pool, "_weekly", lambda: wk)
    monkeypatch.setattr(peer_pool, "_vip_ids", lambda program: [])
    import peer_data as PD
    monkeypatch.setattr(PD, "mrpc_section", lambda cid, w: {})

    class Ctx:
        client = CID
        root = None
    return peer_pool.collect_mrpc(Ctx)


def test_every_current_weekly_client_is_a_peer_without_a_vip_sheet(monkeypatch):
    clients = {CID: tab(40000, 30)}
    for i in range(1, 9):
        clients["70%02d" % i] = tab(30000 + 1000 * i, 10 + i)
    coll = make(monkeypatch, clients)
    assert coll["n_pool"] == 8
    assert all("enroll_12_per_1k" in p["point"] for p in coll["peers"])
    assert coll["me"]["point"]["enroll_12_per_1k"] == 1000.0 * 12 * 30 / 40000


def test_a_client_whose_weekly_series_stopped_is_not_a_current_peer(monkeypatch):
    clients = {CID: tab(40000, 30), "7001": tab(30000, 10), "7002": tab(30000, 10, last="2020-06")}
    coll = make(monkeypatch, clients)
    assert [p["id"] for p in coll["peers"]] == ["7001"]            # 7002 last enrolled in 2020: not a current client


def test_the_comparison_leads_with_the_measure_that_needs_no_goal():
    assert peer_pool.MRPC_METRICS[0]["key"] == "enroll_12_per_1k" and peer_pool.MRPC_METRICS[0]["month"] is False
    assert any(m["key"] == "pct_goal" for m in peer_pool.MRPC_METRICS)       # the goal-based view stays for the clients that have a sheet
