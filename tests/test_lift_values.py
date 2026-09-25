"""lift_values — a client's ARS Lift Matrix valued from its own ODD (Aaron, 2026-09-25).

Pins the method: ARS-eligible card-holding accounts, consumer and business, swipe averages rounded DOWN into
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


def test_every_eligible_card_holding_account_is_valued_business_included(odd_rows_raw, scan):
    # Aaron, 2026-09-25: "include business accounts, but base the calculation only on ARS eligible accounts".
    hdr, rows = odd_rows_raw
    H = {h: i for i, h in enumerate(hdr)}
    odd = accessors(H)
    latest = [h.split()[0] for h in hdr if h.endswith(" Sig #")][-1]
    valued = [r for r in rows if len(r) >= len(hdr) and odd.hascard(r)
              and r[H[f"{latest} Elig"]].strip() == "Yes"]
    want = len(valued)
    assert scan["population"] == want
    assert sum(scan["segments"][s]["n"] for s in LV.SEGMENTS) == want
    assert math.isclose(sum(s["dist"] for s in scan["segments"].values()), 1.0)
    # business accounts are in, and counted as such
    assert scan["counts"]["business"] == sum(1 for r in valued if odd.business(r)) > 0
    assert scan["counts"]["consumer"] == sum(1 for r in valued if odd.personal(r)) > 0
    assert (scan["counts"]["consumer"] + scan["counts"]["business"]
            + scan["counts"].get("business? blank", 0)) == want
    # an ineligible account is never valued, card or not
    assert scan["counts"]["not eligible"] == sum(
        1 for r in rows if len(r) >= len(hdr) and r[H[f"{latest} Elig"]].strip() != "Yes")


def test_nh_is_valued_on_the_eligible_accounts_with_no_card(odd_rows_raw, scan):
    # Aaron, 2026-09-25: "with the ODD we should be able to calculate an independent NH value".
    hdr, rows = odd_rows_raw
    H = {h: i for i, h in enumerate(hdr)}
    odd = accessors(H)
    latest = [h.split()[0] for h in hdr if h.endswith(" Sig #")][-1]
    nh = sum(1 for r in rows if len(r) >= len(hdr) and not odd.hascard(r)
             and r[H[f"{latest} Elig"]].strip() == "Yes")
    assert nh and scan["segments"]["NH"]["n"] == nh == scan["counts"]["no card"]
    assert scan["segments"]["NH"]["dist"] == 0
    v = {r["segment"]: r for r in LV.values(scan, 0.006, 25, 0.8)["segments"]}
    g = scan["segments"]["NH"]
    assert not v["NH"]["from_nu"]
    assert v["NH"]["dda"] == round(0.006 * g["spend"] + 25 * g["items"] * 0.8, 2)
    # a client with no card-less eligible account falls back to NU's value, and says so
    bare = dict(scan, segments=dict(scan["segments"], NH=dict(g, n=0)))
    v = {r["segment"]: r for r in LV.values(bare, 0.006, 25, 0.8)["segments"]}
    assert v["NH"]["from_nu"] and v["NH"]["dda"] == v["NU"]["dda"]


def test_the_window_is_complete_months_only(scan):
    assert len(scan["window"]) == LV.VAL_MONTHS
    assert scan["segments"]["NU"]["n"] >= 0


def test_winsorizing_caps_and_never_raises_a_mean(scan):
    for s in scan["segments"].values():
        assert s["spend"] <= s["spend_raw"] + 1e-9
        assert s["items"] <= s["items_raw"] + 1e-9


def test_every_offered_outlier_cap_is_valued_and_a_higher_cap_trims_less(scan):
    # Aaron, 2026-09-25: the 99th percentile as a variable. Each option is precomputed, so choosing one
    # never re-reads the ODD; the default is WINSOR_PCT, and 1.0 is no cap at all.
    assert set(scan["by_cap"]) == {LV.cap_key(p) for p in LV.WINSOR_OPTIONS}
    assert scan["segments"] == scan["by_cap"][LV.cap_key(LV.WINSOR_PCT)]
    for s in LV.SEGMENTS:
        spend = [scan["by_cap"][LV.cap_key(p)][s]["spend"] for p in LV.WINSOR_OPTIONS]
        assert spend == sorted(spend)
        assert scan["by_cap"]["1"][s]["spend"] == pytest.approx(scan["by_cap"]["1"][s]["spend_raw"])
    lo, hi = LV.values(scan, 0.006, 25, 0.8, 0.95), LV.values(scan, 0.006, 25, 0.8, 1.0)
    assert sum(r["dda"] for r in lo["segments"]) <= sum(r["dda"] for r in hi["segments"])
    assert LV.cap_label(0.975) == "97.5th percentile" and LV.cap_label(1.0) == "no cap"


def test_no_fee_column_means_the_fee_comes_from_the_workbook(scan):
    assert scan["fee"] is None
    d = LV.default_rates(scan, {"ic_rate": 0.0085, "nsf_fee": 35.0, "sheet": "Actuals MM"})
    assert (d["ic_rate"], d["nsf_fee"], d["collection"]) == (0.0085, 35.0, 1.00)
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
    assert ws["B5"].value == 0 and ws["C5"].value == dda["NH"]         # NH: its own value, 0 distribution
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


def test_the_workbook_lift_grid_is_read_as_written(tmp_path):
    path = _workbook(tmp_path / "wb.xlsx")
    wb = openpyxl.load_workbook(path)
    lm = wb["Lift Matrix MM"]
    for j, c in enumerate(LV.CURRENTS, start=3):
        lm.cell(11, j, c)
    lm["B12"], lm["C12"], lm["H12"] = "NU", 5.22, 26.42
    lm["B13"], lm["D13"] = "1-5", 7.3
    wb.save(path)
    grid = LV.read_workbook(path)["matrix"]["grid"]
    assert grid["NU"] == {"1-5": 5.22, "26 Plus": 26.42} and grid["1-5"] == {"6-10": 7.3}


def test_build_lift_matrix_is_a_wrapper_over_lift_values(odd_csv, tmp_path):
    # Aaron, 2026-09-25: "retire build_lift_matrix.py and have it use lift_values". A hand run and
    # Sheila must give the same file.
    import build_lift_matrix
    assert not hasattr(build_lift_matrix, "compute"), "the old valuation is retired"
    assert build_lift_matrix.main([odd_csv, "9999", "Union Financial", "2026.09", str(tmp_path),
                                   "--nsf-fee", "30"]) == 0
    got = openpyxl.load_workbook(tmp_path / "9999-2026.09-ARS-Union Financial ARS Lift Matrix.xlsx").active
    want = LV.values(LV.scan(odd_csv), LV.DEFAULT_IC_RATE, 30.0, LV.DEFAULT_COLLECTION)
    assert [got[f"C{r}"].value for r in range(5, 13)] == [x["dda"] for x in want["segments"]]
    with pytest.raises(SystemExit, match="--nsf-fee"):
        build_lift_matrix.main([odd_csv, "9999", "Union Financial", "2026.09", str(tmp_path)])
