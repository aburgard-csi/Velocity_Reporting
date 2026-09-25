"""lift_values — a client's ARS Lift Matrix valued from its own ODD (Aaron, 2026-09-25).

Pins the method: consumer card-holding eligible accounts only, swipe averages rounded DOWN into
their band, per-segment winsorizing, the NSF/OD fee taken as the MOST COMMON per-item fee when the
ODD carries `Fees1`, the rate defaults (workbook, else 60 BP / no fee), and the file Bradford loads.
"""
import csv
import datetime
import math

import openpyxl
import pytest

import lift_values as LV
from odd_rows import accessors


def test_swipe_averages_round_down_into_their_band():
    assert LV.segment(0.99) == "NU"
    assert LV.segment(1) == "1-5"
    assert LV.segment(5.99) == "1-5"
    assert LV.segment(10.5) == "6-10"
    assert LV.segment(25.99) == "21-25"
    assert LV.segment(26) == "26 Plus"


@pytest.fixture(scope="module")
def scan(odd_csv):
    return LV.scan(odd_csv)


def test_only_consumer_card_holding_eligible_accounts_are_valued(odd_rows_raw, scan):
    hdr, rows = odd_rows_raw
    H = {h: i for i, h in enumerate(hdr)}
    odd = accessors(H)
    latest = [h.split()[0] for h in hdr if h.endswith(" Sig #")][-1]
    want = sum(1 for r in rows if len(r) >= len(hdr) and odd.personal(r) and odd.hascard(r)
               and r[H[f"{latest} Elig"]].strip() == "Yes")
    assert scan["population"] == want
    assert sum(s["n"] for s in scan["segments"].values()) == want
    assert math.isclose(sum(s["dist"] for s in scan["segments"].values()), 1.0)
    # blank Business? is not consumer (odd_rows.personal), so business AND blanks are left out
    assert scan["counts"]["not consumer"] == sum(
        1 for r in rows if len(r) >= len(hdr) and r[H["Business?"]].strip().lower() != "no")


def test_the_window_is_complete_months_only(scan):
    assert len(scan["window"]) == LV.VAL_MONTHS
    assert scan["segments"]["NU"]["n"] >= 0


def test_winsorizing_caps_and_never_raises_a_mean(scan):
    for s in scan["segments"].values():
        assert s["spend"] <= s["spend_raw"] + 1e-9
        assert s["items"] <= s["items_raw"] + 1e-9


def test_no_fee_column_means_the_fee_comes_from_the_workbook(scan):
    assert scan["fee"] is None
    d = LV.default_rates(scan, {"ic_rate": 0.0085, "nsf_fee": 35.0, "sheet": "Actuals MM"})
    assert (d["ic_rate"], d["nsf_fee"], d["collection"]) == (0.0085, 35.0, 0.80)
    assert "workbook" in d["nsf_source"]


def test_defaults_without_a_workbook_are_60bp_and_no_fee(scan):
    d = LV.default_rates(scan, {})
    assert d["ic_rate"] == 0.006
    assert d["nsf_fee"] is None          # never guessed: Sheila asks for it


def _with_fees(src, dst, dated, fee_for):
    """Copy the fixture, adding NSF/OD fee columns: one per month (`dated`) or one undated `Fees1`."""
    with open(src, encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    hdr = [c.strip() for c in rows[4]]
    months = [h.split()[0] for h in hdr if h.endswith(" Sig #")]
    mtd = {m: hdr.index(f"{m} MTD") for m in months}
    add = [f"{m} Fees1" for m in months] if dated else ["Fees1"]
    rows[4] = rows[4] + add
    for n, r in enumerate(rows[5:]):
        if dated:
            r += [str(float(r[mtd[m]] or 0) * fee_for(n)) for m in months]
        else:
            r += [str(float(r[mtd[months[-1]]] or 0) * fee_for(n))]
    with open(dst, "w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(rows)
    return str(dst)


@pytest.mark.parametrize("dated", [True, False])
def test_a_tiered_fee_is_valued_at_the_most_common_one(odd_csv, tmp_path, dated):
    # Every fifth account pays $35, the rest $30: the fee most items are charged is $30.
    path = _with_fees(odd_csv, tmp_path / "fees.csv", dated, lambda n: 35.0 if n % 5 == 0 else 30.0)
    s = LV.scan(path)
    assert s["fee"]["value"] == 30.0
    assert [v["fee"] for v in s["fee"]["values"]][:2] == [30.0, 35.0]
    d = LV.default_rates(s, {"nsf_fee": 25.0, "ic_rate": 0.007, "sheet": "Actuals MM"})
    assert d["nsf_fee"] == 30.0 and "ODD" in d["nsf_source"]       # the ODD wins over the workbook


def test_the_matrix_is_the_difference_of_the_rounded_values(scan):
    v = LV.values(scan, 0.006, 25.0, 0.8)
    dda = {r["segment"]: r["dda"] for r in v["segments"]}
    for b, row in v["matrix"].items():
        for c, lift in row.items():
            assert lift == round(dda[c] - dda[b], 2)
    assert list(v["matrix"]) == LV.BASELINES
    assert list(v["matrix"]["NU"]) == LV.CURRENTS
    assert list(v["matrix"]["16-20"]) == ["21-25", "26 Plus"]
    s = scan["segments"]["1-5"]
    assert dda["1-5"] == round(0.006 * s["spend"] + 25.0 * s["items"] * 0.8, 2)


def test_the_file_bradford_loads_keeps_his_layout(scan, tmp_path):
    v = LV.values(scan, 0.006, 25.0, 0.8)
    out = LV.write_xlsx(v, str(tmp_path / "lm.xlsx"))
    ws = openpyxl.load_workbook(out).active
    assert ws.title == "Sheet1"
    assert (ws["A1"].value, ws["A2"].value, ws["A16"].value) == (
        "Interchange and NSF", "Revenue Segmentation", "Monthly Incremental Revenue Lift")
    assert [ws[f"A{r}"].value for r in range(4, 13)] == ["Segments", "NH"] + LV.SEGMENTS
    dda = {r["segment"]: r["dda"] for r in v["segments"]}
    assert ws["B5"].value == 0 and ws["C5"].value == dda["NU"]         # NH carries NU's value
    assert ws["C12"].value == dda["26 Plus"] and ws["B6"].number_format == "0%"
    assert [ws.cell(18, c).value for c in range(1, 8)] == ["Baseline Segment"] + LV.CURRENTS
    assert [ws.cell(r, 1).value for r in range(19, 24)] == LV.BASELINES
    assert ws["G19"].value == v["matrix"]["NU"]["26 Plus"] and ws["B20"].value is None
    assert {str(r) for r in ws.merged_cells.ranges} == {"A1:C1", "A2:C3", "A16:C17", "D16:G17"}


def test_the_file_name_follows_the_deck_convention():
    assert (LV.out_name("1705", "2026.09", "CoastLife Credit Union")
            == "1705-2026.09-ARS-CoastLife Credit Union ARS Lift Matrix.xlsx")


def _workbook(path):
    wb = openpyxl.Workbook()
    a = wb.active
    a.title = "Actuals MM"
    a["B24"] = "Key Assumptions"
    a["B25"], a["D25"], a["E25"] = "Interchange Rate", 0.006, 0.0071
    a["B26"], a["D26"], a["E26"] = "NSF Fee", 30, 32
    lm = wb.create_sheet("Lift Matrix MM")
    lm["B6"] = "August 2026 Data"
    lm["B8"], lm["C8"] = "Start Date", datetime.datetime(2026, 1, 1)
    lm["B9"], lm["C9"] = "End Date", datetime.datetime(2026, 12, 1)
    lm["B11"] = "Baseline Segment"
    lm["J11"], lm["K11"], lm["L11"] = "Segments", "Distribution", "DDA Value"
    for i, (s, d) in enumerate([("NH", 0), ("NU", .2), ("1-5", .1), ("26+", .4)], start=12):
        lm.cell(i, 10, s), lm.cell(i, 11, d), lm.cell(i, 12, 1.5 + i)
    wb.save(path)
    return str(path)


def test_the_workbook_gives_its_newest_rates_and_current_matrix(tmp_path):
    got = LV.read_workbook(_workbook(tmp_path / "wb.xlsx"))
    assert got["assumptions"] == {"ic_rate": 0.0071, "nsf_fee": 32.0, "sheet": "Actuals MM"}
    m = got["matrix"]
    assert m["in_window"] and not m["data_past_end"]
    assert m["segments"]["NU"]["dda"] == 14.5
    assert m["segments"]["26 Plus"]["dda"] == 16.5        # '26+' read as the segment it is
