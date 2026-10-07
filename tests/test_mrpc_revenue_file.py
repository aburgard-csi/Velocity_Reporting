"""Accounting's "MRPC Revenue.xlsx" extends the MRPC revenue-by-month series (Aaron, 2026-10-06).

The VIP dashboard trails by months (Austin Bank's ended May 2026 in an October deck). The workbook carries
Apr to Aug 2026 per client; it replaces VIP from its first month on, the series is cut to 12 months, the YTD bar
follows, and a month at about twice the median is named, not smoothed.
"""
import datetime
import os
import sys

import openpyxl
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build", "mrpc_pipeline"))
import mrpc_revenue_file as MRF                                    # noqa: E402

MONTHS = [datetime.datetime(2026, m, d) for m, d in ((4, 30), (5, 31), (6, 30), (7, 31), (8, 31))]


def workbook(tmp_path, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Client"] + MONTHS + ["Grand Total"])
    for name, vals in rows:
        ws.append([name] + vals + [sum(v for v in vals if v)])
    ws.append(["Grand Total"] + [None] * 5 + [0])
    p = tmp_path / "MRPC Revenue.xlsx"
    wb.save(p)
    return p


def sheet():
    """A VIP sheet as it stands: Jun 25 to May 26, YTD through May."""
    months = ["Jun 25", "Jul 25", "Aug 25", "Sep 25", "Oct 25", "Nov 25", "Dec 25", "Jan 26", "Feb 26", "Mar 26",
              "Apr 26", "May 26"]
    rev = [100.0 + i for i in range(12)]
    return {"meta": {"client_id": "1075"},
            "revenue": {"life_of_program": 5000, "by_month": {"months": months, "revenue": rev},
                        "annual": [{"year": "2025", "amount": 1.0},
                                   {"year": "2026 YTD", "amount": sum(rev[7:]), "ytd_through": "May"}]}}


def test_the_workbook_replaces_vip_from_its_first_month_and_the_series_is_twelve_months(tmp_path):
    d = sheet()
    p = workbook(tmp_path, [("V1075-AUSTIN", [110.0, 111.0, 112.0, 113.0, 114.0])])
    info = MRF.apply(d, p)
    bm = d["revenue"]["by_month"]
    assert bm["months"] == ["Sep 25", "Oct 25", "Nov 25", "Dec 25", "Jan 26", "Feb 26", "Mar 26",
                            "Apr 26", "May 26", "Jun 26", "Jul 26", "Aug 26"]
    assert bm["revenue"][-5:] == [110.0, 111.0, 112.0, 113.0, 114.0]      # Apr and May are the workbook's
    assert bm["revenue"][:3] == [103.0, 104.0, 105.0]                       # earlier months stay VIP's
    assert info["replaced"] == ["Apr 26", "May 26"] and info["through"] == "Aug 26"


def test_the_ytd_bar_follows_the_extended_series(tmp_path):
    d = sheet()
    MRF.apply(d, workbook(tmp_path, [("V1075-AUSTIN", [110.0, 111.0, 112.0, 113.0, 114.0])]))
    ytd = d["revenue"]["annual"][1]
    jan_mar = 107.0 + 108.0 + 109.0
    assert ytd["amount"] == pytest.approx(jan_mar + 110 + 111 + 112 + 113 + 114)
    assert ytd["ytd_through"] == "Aug"


def test_life_of_program_moves_with_the_ytd_so_the_two_sources_do_not_stack(tmp_path):
    d = sheet()
    old_ytd = d["revenue"]["annual"][1]["amount"]
    MRF.apply(d, workbook(tmp_path, [("V1075-AUSTIN", [110.0, 111.0, 112.0, 113.0, 114.0])]))
    new_ytd = d["revenue"]["annual"][1]["amount"]
    assert d["revenue"]["life_of_program"] == round(5000 - old_ytd + new_ytd)
    assert isinstance(d["revenue"]["life_of_program"], int)


def test_a_client_without_a_ytd_bar_keeps_its_life_of_program(tmp_path):
    d = sheet()
    d["revenue"]["annual"] = [a for a in d["revenue"]["annual"] if "YTD" not in a["year"]]
    MRF.apply(d, workbook(tmp_path, [("V1075-AUSTIN", [110.0] * 5)]))
    assert d["revenue"]["life_of_program"] == 5000


def test_a_doubled_month_is_kept_and_named(tmp_path):
    d = sheet()
    info = MRF.apply(d, workbook(tmp_path, [("V1075-AUSTIN", [110.0, 220.0, 112.0, 113.0, 114.0])]))
    assert [x["month"] for x in info["doubled"]] == ["May 26"]
    assert 220.0 in d["revenue"]["by_month"]["revenue"]
    assert "May 26" in MRF.doubled_sentence(info) and "twice a normal month" in MRF.doubled_sentence(info)


def test_a_client_not_in_the_workbook_is_left_alone(tmp_path):
    d, before = sheet(), sheet()
    assert MRF.apply(d, workbook(tmp_path, [("V9999-OTHER", [1.0] * 5)])) is None
    assert d == before


def test_no_workbook_leaves_the_data_alone(tmp_path):
    d, before = sheet(), sheet()
    assert MRF.apply(d, tmp_path / "missing.xlsx") is None
    assert d == before


def test_months_before_a_client_started_are_dropped_not_zeroed(tmp_path):
    d = sheet()
    MRF.apply(d, workbook(tmp_path, [("V1075-AUSTIN", [None, None, 48.0, 40.5, 79.5])]))
    bm = d["revenue"]["by_month"]
    assert bm["months"][-3:] == ["Jun 26", "Jul 26", "Aug 26"]
    assert bm["revenue"][-3:] == [48.0, 40.5, 79.5]
    assert "Mar 26" in bm["months"]


def test_the_grand_total_row_is_not_a_client(tmp_path):
    p = workbook(tmp_path, [("V1075-AUSTIN", [1.0] * 5)])
    assert list(MRF.read(p)) == ["1075"]


def test_the_notes_say_where_the_months_came_from(tmp_path):
    d = sheet()
    info = MRF.apply(d, workbook(tmp_path, [("V1075-AUSTIN", [110.0] * 5)]))
    s = MRF.source_sentence(info)
    assert "through May 26" in s and "Apr 26 to Aug 26" in s and "MRPC Revenue.xlsx" in s
    assert MRF.source_sentence(None) == "VIP MRPC Revenue by Month"


def test_the_builder_applies_it_before_judging_complete_months():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = open(os.path.join(root, "build", "mrpc_pipeline", "build_mrpc_gen.py"), encoding="utf-8").read()
    assert src.index("MRF.apply(data)") < src.index("_left_out=complete_series(data)")
    assert "_file" in src and "blk_as_of" in src

def test_the_corrected_layout_with_title_rows_and_a_refunds_sheet_reads_the_same(tmp_path):
    """Accounting's corrected file (2026-10-07): two blank rows and a title above the header, a Grand Total
    row, and a second sheet of customer refunds. Austin's May there is VIP's own $33,302.75."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append([])
    ws.append([])
    ws.append(["MRPC Revenue Shares", "Revenue Month"])
    ws.append(["Client"] + MONTHS + ["Grand Total"])
    ws.append(["V1075-AUSTIN BANK"] + [33329.8, 33302.75, 35233.73, 35514.68, 33677.65] + [171058.61])
    ws.append(["Grand Total"] + [110300.71] * 5 + [559898.05])
    refunds = wb.create_sheet("Find Customer Refunds")
    refunds.append(["Customer Refund", "Company", "Customer/Sponsor"])
    refunds.append(["Customer Refund: CRF1000", "My Rewards, LLC", "V1637-OUACHITA"])
    p = tmp_path / "MRPC Revenue.xlsx"
    wb.save(p)
    rec = MRF.read(p)
    assert list(rec) == ["1075"]
    assert rec["1075"]["values"] == [33329.8, 33302.75, 35233.73, 35514.68, 33677.65]
    d = sheet()
    d["revenue"]["by_month"]["revenue"] = [32000.0 + 50 * i for i in range(12)]      # VIP's own scale
    info = MRF.apply(d, p)
    assert info["doubled"] == [], "VIP's May and Accounting's now agree: nothing to call out"
