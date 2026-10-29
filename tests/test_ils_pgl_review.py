"""The Velocity PGL review's tables (build/ils_pipeline/pre_go_live/review.py, 2026-10-28).

Pinned on a hand-built frame with known answers: deleted rows are out of every base; each table has the
workbook's row shape and base; the OD-status tables carry Eligible / Ineligible subtotals on the confirmed
codes; pay ratio is paid / items; limit tiers follow the matrix's rounding step; Reg E by year rolls the
years before 2010 together and splits the newest year by month. (The full check, 134 of 134 figures,
ran against the 1616 working workbook, which is client data and stays out of the repo.)
"""
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build")]
from ils_pipeline.pre_go_live import review  # noqa: E402


def _df():
    rows = [
        # status, type, od, rege, change, items, paid, core, ils, deposit $, opened, deleted
        ("O", "PERSONAL", "ODP", "Y", "Same", 4, 4, 500, 500, 1000, "2008-03-01", None),
        ("O", "PERSONAL", "ODP", "N", "Score100Plus", 2, 1, 0, 300, 200, "2025-01-15", None),
        ("O", "PERSONAL", "CUST OPIN", None, "ScoreLess100", 0, 0, 500, 100, 50, "2025-02-10", None),
        ("O", "PERSONAL", "NOT ODP", "N", "Same", 6, 3, 0, 0, 0, "2015-06-01", None),
        ("O", "BUSINESS", "ODP", "Y", "Same", 1, 1, 1000, 1000, 9000, "2020-01-01", None),
        ("C", "PERSONAL", "ODP", "N", "Same", 9, 9, 0, 0, 0, "2001-01-01", None),
        ("O", "PERSONAL", "ODP", "Y", "Same", 50, 50, 500, 500, 0, "2025-03-01", "2026-01-01"),   # deleted
    ]
    cols = ["Account Status Code", "Personal_Business", "OD Status Code (from Core)", "Reg-E Opt-In Value",
            "UpOrDown from Initial OD Limit", "NSF OD Items since start date",
            "Paid NSF OD Items since start date", "Initial OD Limit (from Core)", "OD Limit (from ILS)",
            "Deposit Amount Last 33 days", "Open Date", "Deleted"]
    df = pd.DataFrame(rows, columns=cols)
    df["Open Date"] = pd.to_datetime(df["Open Date"])
    df["Deleted"] = pd.to_datetime(df["Deleted"])
    return df


CODES = {"open_status": ["O"], "od_eligible": ["ODP", "CUST OPIN"]}


def _t():
    return review.compute(_df(), CODES, {"sysv_matrix_rounding_step": 250})["pgl_review"]


def _rows(t, k):
    return {r[0].strip(): r for r in t[k]["rows"] + [t[k]["total"]]}


def test_deleted_rows_are_in_no_base():
    t = _t()
    assert t["status"]["base_n"] == 6 and _rows(t, "status")["O"][1] == 5


def test_the_od_table_has_eligible_and_ineligible_blocks_on_the_confirmed_codes():
    r = _rows(_t(), "personal_od")
    assert r["Eligible"][1] == 3 and r["ODP"][1] == 2 and r["CUST OPIN"][1] == 1
    assert r["Ineligible"][1] == 1 and r["NOT ODP"][3] == 6
    assert r["Grand Total"][1] == 4 and r["Grand Total"][3] == 12


def test_the_row_shape_and_pay_ratio():
    e = _rows(_t(), "personal_change")
    assert review.COLUMNS[6] == "pay_ratio"
    assert e["Score100Plus"][3:7] == [2, round(2 / 6, 4), 1, 0.5]
    assert e["Grand Total"][1] == 3


def test_limit_tiers_follow_the_matrix_rounding_step():
    tiers = {r[0]: r[1] for r in _t()["personal_tiers"]["rows"]}
    assert tiers == {0: 1, 250: 1, 500: 1}


def test_rege_by_year_rolls_up_before_2010_and_splits_the_newest_year():
    y = _rows(_t(), "rege_by_year")
    assert y["Pre-2010"][1:5] == [1, 0, 0, 1]
    assert y["Jan 2025"][1:5] == [0, 1, 0, 1] and y["Feb 2025"][3] == 1
    assert y["Grand Total"][4] == 3


def test_each_table_is_written_with_its_columns():
    out = review.compute(_df(), CODES)
    assert out["pgl_review_personal_od_columns"] == review.COLUMNS
    assert out["pgl_review_personal_tiers_columns"] == review.TIER_COLUMNS
    assert out["pgl_review_status"][-1][0] == "Grand Total"


def test_every_row_carries_the_median_deposit_beside_the_average():
    t = _t()
    assert review.COLUMNS[-1] == "median_deposit_dollars_33d"
    e = _rows(t, "personal_change")["Same"]          # deposits 1000 (eligible) and the NOT ODP row is out
    assert e[10] == e[13] == 1000.0
    bands = {b[0]: b for b in t["personal_tiers"]["bands"]}
    assert bands[250][2] == 1 and bands[500][2] == 2      # limits 100 | 300, 500
    assert bands[500][5] == 600.0                          # the median of its own accounts' deposits (200, 1000)
