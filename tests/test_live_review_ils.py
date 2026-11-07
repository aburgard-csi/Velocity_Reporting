"""Live Review's ILS section: the review PDF read into a pack, and the pack shown as pages.

Synthetic client 9999 only. The page strings below imitate the text layer of an ILS Program Analysis PDF (a table is one
run of words and figures), with invented numbers that reconcile the way a real review's do.
"""
import json
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "scripts"), os.path.join(REPO, "build"), os.path.join(REPO, "build", "ars_pipeline"), os.path.join(REPO, "tests")]

from review_page import ils_review_pack as R   # noqa: E402
from review_page import registry               # noqa: E402

CID, PERIOD = "9999", "2026.10"


def month_rows(year_from, count_base, fees_base):
    rows, y, m = [], year_from, 6
    for i in range(12):
        c, f, loss = count_base + 10 * i, fees_base + 1000 * i, 100 * i
        rows.append((y, m, c, 5 + i, 1.5, 28, 3500 + i, f, f // 28, f // (3500 + i), loss, round(100.0 * loss / f, 1)))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return rows


def month_text(rows):
    return " ".join(f"{y} {m:02d} {c:,} {cu} {d:.2f}% {bd} {a:,} ${f:,} ${pd:,} ${pa:,} ${loss:,} {lr}%" for y, m, c, cu, d, bd, a, f, pd, pa, loss, lr in rows)


def pages():
    p1, p2 = month_rows(2024, 9000, 200000), month_rows(2025, 9500, 150000)

    def tot(rows, i):
        return sum(r[i] for r in rows)
    ann = []
    for k, rows in ((1, p1), (2, p2)):
        f, loss = tot(rows, 7), tot(rows, 10)
        ann.append(f"{k} {tot(rows, 2):,} {tot(rows, 3):,} 1.50% 344 11,000 ${f:,} $9,000 $250 ${loss:,} {100.0 * loss / f:.1f}%")
    return [
        "Confidential ILS Program Analysis Partnering for Success Test Bank July 18, 2026",
        "FI DEMOGRAPHIC INFORMATION Test Bank • HQ: Springfield, OH • Asset Size: $1.0B • Branches: 9 • Active DDA Accounts: 12,000 • Primary Federal Regulator: NCUA "
        "• Core Provider: Acme • Core Product: Acme - Core • ILS® Go Live Date: 10/16/2017 • ILS® Version: 22.1 • Contract Start: 06/29/2017 • Contract End: 03/01/2029 • Data Analyzed Through: 06/25/2026",
        "Peer Comparison – Personal (All Account Types) Metric V1 V2 NAME TEST Personal COUNT 1 40 FI_TYPE CU CU MED.OFFICES 9 12 MED.ACTIVE.CHK 12,000 20,000 MED.USER.PER 30.0% 31.0% "
        "MED.ELIG.PER 90.0% 80.0% MED.REGE.PER 40.0% 30.0% MED.ITEMSxUS 16.052 13.333 MED.WF 0.9 0.92 USR.CHGOFF.PER 3.0% 7.0% MED.AVG.FEE $14 $23 • Eligible is strong • Charge-offs compare well",
        "Test Bank | Account Utilization HU ACCTS ACCTS.PR REGEY ELIG MED.DEPA365 PD.365 FEES.365 FEES.365.PR MED.FXD NON-USER 8,000 66.7% 25.0% 90.0% $30,000 NaN% $0 0.0% 0.000000 000 "
        "<= 6 ITEMS 2,000 16.7% 30.0% 80.0% $28,000 80.0% $100,000 10.0% N/A 7-23 ITEMS 1,200 10.0% 40.0% 75.0% $35,000 87.0% $300,000 30.0% 0.003415 168 "
        "HEAVY USER (24+) 800 6.7% 53.0% 70.0% $45,000 90.0% $600,00 0 60.0% 0.015289 460 TOTAL 12,000 100.0% 29.0% 86.0% $32,000 88.0% $1,000,000 100.0% N/A",
        "Mature Accounts (365+ Days Open) depAmt365cut ACCTS ACCTS.PR REGEY ELIG PD.365 MED.PD.OD.AM T FEES.365 FEES.365.PR ZERO DEPS 10 1.0% 40.0% 74.0% 2.0% $0 $100 0.0% "
        "<10k 590 59.0% 39.0% 58.0% 73.0% $63 $400,000 40.0% 10-25k 400 40.0% 37.0% 71.0% 88.0% $269 $599,900 60.0% TOTAL 1,000 100.0% 36.0% 77.0% 88.0% $396 $1,000,000 100.0%",
        "Period 1 Revenue: Test Bank YR MTH COUNT CURE DEFAULT.RT BIZ.DAYS ACCTS.W.OD C.FEES C.FEES.BIZDAY C.FEES.PER.ACCT LOSSES LOSS.RT " + month_text(p1),
        "Test Bank | YoY Monthly Summary (Period 2) YR MTH COUNT CURE DEFAULT.RT BIZ.DAYS ACCTS.W.OD C.FEES C.FEES.BIZDAY C.FEES.PER.ACCT LOSSES LOSS.RT " + month_text(p2),
        "Test Bank | Annual Comparison – All COMP365 COUNT CURE DEFAULT.RT BIZ.DAYS ACCTS.W.OD C.FEES C.FEES.BIZDAY C.FEES.PER.ACCT LOSSES LOSS.RT " + " ".join(ann) + " • Fee Change was in March 2025",
        "OD Risk Metrics – Personal (Global) GLOBAL RISK METRICS: 115 VELOCITY PEERS Institution Type N Active Chkg (Median) OD Rate (Median) Default Rate (Median) Fee Income (Median) Fees / Acct (Median) Loss Rate (Median) "
        "BANK 69 47,614 2.04 3.9% 3,787,784 $79.55 10.3% CU 46 47,140 2.98 2.7% 4,968,318 $105.39 8.3% TEST (9999) 1 12,000 3.11 1.4% 1,000,000 $71.08 7.8%",
        "OPPORTUNITY ANALYSIS 51Confidential and proprietary information • Revenue changed • Reg E compares strongly",
    ]


def test_the_reader_finds_every_table_and_reconciles_them():
    pack = R.parse(pages(), "9999-2026.07-ILS-Test Bank ILS Review.pdf", "9999")
    assert pack["client_name"] == "Test Bank" and pack["review_date"] == "2026-07-18"
    assert set(pack["pages"]) == {"institution", "peer_comparison", "utilization", "mature", "monthly", "annual", "risk", "opportunity"}
    assert pack["institution"]["active_dda"] == 12000 and pack["institution"]["data_through"] == "2026-06-25"
    assert pack["peer_comparison"]["peer_count"] == 40
    assert len(pack["monthly"]["period1"]) == 12 and len(pack["monthly"]["period2"]) == 12
    # "$600,00 0" is one figure cut in two by the text layer
    assert pack["utilization"]["rows"][-1]["fees_365"] == 600000
    assert pack["utilization"]["rows"][0]["paid_pct"] is None            # NaN% stays blank, never zero
    assert [r["group"] for r in pack["risk"]["global"]] == ["BANK", "CU", "this client"]


def test_a_table_that_does_not_add_up_stops_the_read():
    bad = pages()
    bad[3] = bad[3].replace("TOTAL 12,000", "TOTAL 12,001")
    with pytest.raises(R.ReviewReadError, match="do not add to the total"):
        R.parse(bad, "x.pdf", "9999")
    bad = pages()
    i = next(n for n, t in enumerate(bad) if "COMP365" in t)
    bad[i] = bad[i].replace("LOSS.RT 1 ", "LOSS.RT 1 9", 1)          # period 1's item count gains a digit: its months no longer add up
    with pytest.raises(R.ReviewReadError):
        R.parse(bad, "x.pdf", "9999")


def test_a_document_that_is_not_a_review_is_refused():
    with pytest.raises(R.ReviewReadError):
        R.parse(["Nothing here"], "x.pdf", "9999")


def test_the_client_number_comes_from_the_file_name():
    assert R.client_from_filename("C:/x/1539-2026.07-ILS-Marine FCU ILS Review.pdf") == "1539"
    assert R.client_from_filename("report.pdf") is None


@pytest.fixture
def pack_root(tmp_path):
    pack = R.parse(pages(), "9999-2026.07-ILS-Test Bank ILS Review.pdf", "9999")
    path = R.pack_path(pack["client_id"], tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pack), encoding="utf-8")
    return tmp_path


def build(root):
    return registry.build_model(CID, PERIOD, root=root, programs=["ils"])


def test_the_page_builds_and_every_figure_traces(pack_root):
    model, _t, problems = build(pack_root)
    assert problems == []
    ils = model["programs"][0]
    assert ils["key"] == "ils" and ils["state"] == "ready" and ils["label"] == "ILS"
    assert [s["id"] for s in ils["screens"]] == ["summary", "fees", "accounts", "peers"]
    assert ils["client_name"] == "Test Bank"
    assert "Test Bank collected" in ils["screens"][0]["headline"]


def test_a_fall_in_fees_is_stated_with_both_figures_and_no_cause(pack_root):
    model, _t, _p = build(pack_root)
    head = model["programs"][0]["screens"][0]["headline"]
    assert "below the" in head and "$" in head
    assert "did not have an impact" not in head


def test_every_screen_says_it_is_the_reviews_date_not_the_periods(pack_root):
    model, _t, _p = build(pack_root)
    for s in model["programs"][0]["screens"]:
        assert any("July 18, 2026 review" in n and "do not change with the period" in n for n in s["notes"])


def test_the_reviews_commentary_is_quoted_in_sources_not_restated(pack_root):
    model, _t, _p = build(pack_root)
    summary = model["programs"][0]["screens"][0]
    assert any("Fee Change was in March 2025" in s["text"] for s in summary["sources"])
    assert any("Opportunity analysis" in s["title"] and "Reg E compares strongly" in s["text"] for s in summary["sources"])


def test_a_client_with_no_review_pack_is_told_what_to_run(tmp_path):
    model, _t, _p = build(tmp_path)
    ils = model["programs"][0]
    assert ils["state"] == "missing" and "ils_review_pack.py" in ils["fix"]


def test_a_peer_row_says_points_for_a_rate_and_percent_for_a_count(pack_root):
    model, _t, _p = build(pack_root)
    peers = next(s for s in model["programs"][0]["screens"] if s["id"] == "peers")
    tbl = next(b for b in peers["blocks"] if b["t"] == "table" and b["id"] == "ils-peer")
    rows = {r["name"]: r for r in tbl["rows"]}
    assert rows["Eligible %"]["diff"] == "+10.0 pts"
    assert rows["Branches"]["diff"] == "25.0% lower"
    assert json.dumps(model)                                       # the model is plain JSON
