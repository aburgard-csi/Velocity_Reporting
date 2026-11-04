"""Cindy Draper's review of KEMBA CU 1195's ICS deck (2026-11-03): the cohort charts show EVERY cohort from the
program's start with the early ones called out, and direct mail and branch referrals are told apart.

What is pinned here:

  * the count split is the workbook's accounts opened less the direct-mail list's, never below zero;
  * the referral export stands in for the VIP referral data (and its rows are read with or without a BOM);
  * the ODD scan joins both lists by account hash, and interchange by channel is printed only when the
    workbook's interchange is one stable rate times the ODD's spend;
  * a month the ODD carries no debit dollars for is named, not counted as zero spend;
  * the slides exist only where their data does, and say so where it does not.

Every figure and every account hash is synthetic.
"""
import csv
import datetime as dt
import hashlib
import json
import os
import zipfile

import pytest

import build_ics_gen as G
import ics_channel_split as CS
import ics_charts_gen as CH
import ics_local_sheet as L
import rpe_env as R
from test_ics_local_sheet import (NAME, PERIOD, CID, REPO, root, _sheet, _build_deck, _titles,  # noqa: F401 (fixture)
                                  write_referrals, write_charts, write_workbook, write_direct_mail,
                                  referral_file, charts_file, workbook_file, dm_file, kind_dir)


def H(n):
    """A 40-hex account hash, the shape of the real lists."""
    return hashlib.sha1(f"acct-{n}".encode()).hexdigest().upper()


# ------------------------------------------------------------------ the count split
def test_the_split_is_the_workbooks_accounts_less_direct_mail():
    months = ["Dec 22", "Jan 23", "Feb 23"]
    dm = [(H(1), dt.date(2023, 1, 5), "1"), (H(2), dt.date(2023, 1, 9), "1"), (H(3), dt.date(2023, 2, 1), "2")]
    cs = CS.cohort_split(months, [2, 10, 4], dm)
    assert cs["direct_mail"] == [0, 2, 1] and cs["referral"] == [2, 8, 3]
    assert cs["dm_outside"] == 0 and cs["over"] == []


def test_a_list_that_exceeds_the_workbook_never_makes_a_negative_referral_count():
    cs = CS.cohort_split(["Jan 23"], [1], [(H(i), dt.date(2023, 1, 2), "") for i in range(3)])
    assert cs["referral"] == [0] and cs["over"] == ["Jan 23"]


def test_a_list_account_outside_the_cohorts_is_counted_apart():
    cs = CS.cohort_split(["Jan 23"], [5], [(H(1), dt.date(2022, 1, 2), ""), (H(2), dt.date(2023, 1, 2), "")])
    assert cs["direct_mail"] == [1] and cs["dm_outside"] == 1


def write_dm_with_hashes(path, accounts):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    for _ in range(8):
        ws.append([])
    ws.append([None, "# of Accounts", "Branch Number", None, "Name Line 1", "Account Mask", "Open Date", None, "Account Number"])
    for i, (h, d, br) in enumerate(accounts, 1):
        ws.append([None, i, br, None, f"Holder {i}", "****0000", d, None, h])
    wb.save(path)


def test_the_direct_mail_list_is_read_by_header(tmp_path):
    p = tmp_path / "dm.xlsx"
    write_dm_with_hashes(p, [(H(1), dt.datetime(2023, 4, 29), 55), (H(2), "9/28/2026", 1), ("not-a-hash", dt.datetime(2023, 5, 3), 6)])
    rows, bad = CS.read_dm_accounts(p)
    assert [(h, d, b) for h, d, b in rows] == [(H(1), dt.date(2023, 4, 29), "55"), (H(2), dt.date(2026, 9, 28), "1"),
                                                ("", dt.date(2023, 5, 3), "6")] and bad == 0


# ------------------------------------------------------------------ the referral export
EXPORT_HEAD = ["client_id", "client_name", "corporation_id", "primarydda", "issue_date", "branch_number", "branch_name",
               "account_found", "name1", "date_opened", "has_debitcard", "rege_response", "total_spend", "total_fees",
               "total_svcchg", "total_othchg", "total_nsf", "balance_period", "balance_average", "balance_current"]


def write_export(path, rows, bom=False):
    with open(path, "w", encoding=("utf-8-sig" if bom else "utf-8"), newline="") as fh:
        w = csv.writer(fh)
        w.writerow(EXPORT_HEAD)
        for r in rows:
            w.writerow(r)


def exp_row(cid, n, issue, branch=("10", "Harborview"), found="N", opened="NULL"):
    return [cid, "X", "1", H(n), issue, branch[0], branch[1], found, "NULL", opened, "1", "NULL",
            "0.00", "0.00", "0.00", "0.00", "0.00", "2026-08-01", "NULL", "NULL"]


def test_the_export_is_read_for_one_client_with_a_later_file_replacing_an_earlier_row(tmp_path):
    a, b = tmp_path / "ics_referrals.csv", tmp_path / "ics_referrals 2026-11-03.csv"
    write_export(a, [exp_row("9901", 1, "2026-08-02 10:00:00.000"), exp_row("9902", 2, "2026-08-02 10:00:00.000"),
                     exp_row("9901", 3, "2026-08-05 09:00:00.000", found="N")])
    write_export(b, [exp_row("9901", 3, "2026-08-05 09:00:00.000", found="Y", opened="2026-08-05"),
                     exp_row("9901", 4, "2026-09-01 09:00:00.000", branch=("20", "Hilltop"))], bom=True)   # a BOM, as the landings carry
    files = CS.referral_export_files(str(tmp_path))
    assert [os.path.basename(f) for f in files] == ["ics_referrals.csv", "ics_referrals 2026-11-03.csv"]
    rows = CS.read_referral_export(files, "9901")
    assert len(rows) == 3                                        # 9902 is another client; the shared referral is one row
    assert {r["primarydda"] for r in rows} == {H(1), H(3), H(4)}
    ev = CS.referral_events(rows)
    assert sorted(e[0] for e in ev) == [dt.date(2026, 8, 2), dt.date(2026, 8, 5), dt.date(2026, 9, 1)]
    assert {e[1] for e in ev} == {"10", "20"}
    assert CS.referral_branch_names(rows) == {"10": "Harborview", "20": "Hilltop"}
    assert CS.referral_matched_accounts(rows) == {H(3): dt.date(2026, 8, 5)}


def _export_for_the_fixture(root):
    """An export carrying CID's referrals for every fixture month (write_referrals' counts)."""
    rows, n = [], 0
    for i, (y, m) in enumerate(__import__("test_ics_local_sheet")._months()):
        for k in range(i + 1):
            n += 1
            rows.append(exp_row(CID, n, f"{y}-{m:02d}-{1 + (k % 27):02d} 10:00:00.000", branch=(["10", "20", "30"][k % 3], f"Branch {k % 3}")))
    write_export(kind_dir(root, L.REFERRAL_KIND) / "ics_referrals.csv", rows, bom=True)
    return n


def test_a_client_with_only_export_rows_gets_its_referral_slides_from_the_export(root, tmp_path):
    """The export reproduces the VIP table for KEMBA (831 year to date at 2026-10-13, Whitehall 128): where there
    is no VIP sheet and no per-client file it is the referral source, not the workbook's accounts-opened row."""
    n = _export_for_the_fixture(root)
    write_workbook(workbook_file(root, PERIOD))
    write_charts(charts_file(root))
    av = L.available(CID, PERIOD, NAME)
    assert av["shape"] == "full" and av["referrals"].endswith("ics_referrals.csv")
    d = _sheet(root, tmp_path)
    assert d["referrals"]["program_to_date"] == n == sum(range(1, 15))
    assert "all-clients ICS referral export" in d["meta"]["referral_source"]
    assert d["_provenance"]["shape"] == "full"
    # a client the export does not carry still builds the workbook-only shape
    assert L.find_referral_export("0000") is None


def test_the_export_names_branches_the_goals_tab_does_not(root, tmp_path):
    _export_for_the_fixture(root)
    write_workbook(workbook_file(root, PERIOD))
    write_charts(charts_file(root))                              # names branches 10 and 20 only
    names = {b["number"]: b["name"] for b in _sheet(root, tmp_path)["referrals"]["by_branch"]["branches"]}
    assert names["10"] == "Harborview" and names["30"] == "Branch 2"


# ------------------------------------------------------------------ the ODD
MONTHS = ["Oct23", "Nov23", "Dec23", "Jan24", "Apr24", "May24"]            # Feb/Mar 24 carry no debit dollars


def write_odd(path, rows, gap=True):
    """A zip holding one ODD csv shaped like the data team's: banner rows, then the header. `rows` are dicts."""
    months = MONTHS
    hdr = ["5", "Acct ID", " Acct Number", "Acct Mask", "Branch", "Prod Code", "Prod Desc", "Business?", "Stat Code", "Stat Desc",
           "DOB", "Date Opened", "Date Closed"]
    for mth in months:
        hdr += [f"{mth} Sig #", f"{mth} Sig $", f"{mth} PIN #", f"{mth} PIN $"]
    lines = ["1,Sample Harbor CU - OD Data Dump", "2,Data Period: Oct23 to May24", "3, ", "4, "]
    out = [",".join(hdr)]
    for i, r in enumerate(rows, 1):
        cells = [str(i), str(i), r["hash"], "m", "1", r.get("code", "1200"), r.get("prod", "Hassle Free"),
                 "Yes" if r.get("biz") else "No", "A", "OPEN", r.get("dob", ""), r["opened"], r.get("closed", "")]
        for k, _ in enumerate(months):
            sp = r["spend"][k]
            cells += ["1", f"{sp[0]:.2f}", "1", f"{sp[1]:.2f}"]
        out.append(",".join(cells))
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("9901-2026-09-Sample Harbor CU-ODD (Oct23 forward) (100926_082626)_V2_1_1.csv", "\n".join(lines + out) + "\n")
        z.writestr("9901_30607_combined.txt", "a transaction member that must never be read as the ODD\n")


def _odd_rows():
    z = (0.0, 0.0)
    rows = [
        # direct mail: one in the window from Oct 23, one closed in Dec 23
        dict(hash=H(1), opened="10/05/2023", dob="03/01/1990", spend=[(100, 0)] * 6),
        dict(hash=H(2), opened="10/20/2023", closed="12/10/2023", dob="01/01/1950", spend=[(50, 0), (50, 0), z, z, z, z]),
        # branch referral
        dict(hash=H(3), opened="10/12/2023", dob="05/05/1985", prod="Elements Checking", code="1250", spend=[(200, 50)] * 6),
        dict(hash=H(4), opened="11/02/2023", dob="07/07/1960", spend=[z, (100, 0), (100, 0), (100, 0), (100, 0), (100, 0)]),
        dict(hash=H(5), opened="01/09/2024", biz=True, dob="01/01/2015", prod="Business Value Checking", code="1300", spend=[z, z, z, (10, 0), (10, 0), (10, 0)]),
    ]
    return rows


def test_scan_odd_joins_by_hash_and_reads_only_the_odd_member(tmp_path):
    zp = tmp_path / "9901_ODDD.zip"
    write_odd(zp, _odd_rows() + [dict(hash=H(99), opened="10/01/2023", spend=[(5, 0)] * 6)])      # H(99) is on no list
    scan = CS.scan_odd(zp, {H(1): "dm", H(2): "dm", H(3): "ref", H(4): "ref", H(5): "ref"})
    assert scan["months"] == ["2023-10", "2023-11", "2023-12", "2024-01", "2024-04", "2024-05"]
    assert scan["stamp"] == "100926_082626" and scan["rows"] == 6
    assert [a["hash"] for a in scan["accounts"]] == [H(1), H(2), H(3), H(4), H(5)]
    a3 = scan["accounts"][2]
    assert a3["group"] == "ref" and a3["spend"][0] == 250.0 and a3["product"] == "Elements Checking" and a3["code"] == "1250"
    assert scan["accounts"][1]["closed"] == "2023-12-10" and scan["accounts"][4]["business"] is True


def test_a_month_with_no_debit_columns_is_named_not_zeroed():
    assert CS.gap_months(["2023-10", "2023-11", "2024-01", "2024-04"]) == ["2023-12", "2024-02", "2024-03"]
    assert CS.gap_months(["2026-04", "2026-09"]) == ["2026-05", "2026-06", "2026-07", "2026-08"]
    assert CS.gap_months([]) == []


def test_exposure_counts_an_account_in_every_month_it_was_open(tmp_path):
    zp = tmp_path / "z.zip"
    write_odd(zp, _odd_rows())
    scan = CS.scan_odd(zp, {H(1): "dm", H(2): "dm", H(3): "ref", H(4): "ref", H(5): "ref"})
    ex = CS.exposure_by_year(scan, 0.01)
    y23, y24 = ex["years"]
    assert (y23["label"], y23["months"]) == ("2023", 3) and (y24["label"], y24["months"]) == ("2024", 3)
    # direct mail in 2023: H1 open all three months ($100 each); H2 open Oct-Dec (closed 12/10 - open in December)
    dm = y23["dm"]
    assert dm["account_months"] == 3 + 3 and round(dm["spend"], 2) == 300 + 100
    assert dm["interchange"] == pytest.approx(4.0) and dm["pam"] == pytest.approx(4.0 / 6)
    # referral in 2023: H3 three months, H4 opened Nov (two months, and it spends in both)
    assert y23["ref"]["account_months"] == 3 + 2
    assert y23["ref"]["active"] == 3 + 2 and dm["active"] == 3 + 2      # H2's Dec spend is 0
    # the all-months fold reads every observed month once
    assert ex["all"]["months"] == 6 and ex["all"]["dm"]["account_months"] == y23["dm"]["account_months"] + y24["dm"]["account_months"]


def test_the_implied_rate_is_accepted_only_when_it_is_stable():
    months = ["Oct 23", "Nov 23", "Dec 23"]
    spend = {"dm": [100.0, 0.0, 50.0], "ref": [900.0, 1000.0, 450.0], "dm_n": [1, 0, 1], "ref_n": [9, 10, 4]}
    ic = [9.0, 9.0, 4.5]                                         # 0.9% of every cohort's spend
    r = CS.implied_rate(months, ic, [10, 10, 5], spend, (2023, 10))
    assert r["rate"] == pytest.approx(0.009) and r["cohorts_used"] == 3
    assert CS.implied_rate(months, [9.0, 9.0, 9.0], [10, 10, 5], spend, (2023, 10)) is None      # a cohort 2x off the pooled rate
    # a cohort the ODD barely covers is not used
    assert CS.implied_rate(months, [9.0, 9.0, 4.5], [10, 10, 50], spend, (2023, 10))["cohorts_used"] == 2
    # nothing opened inside the window: no rate
    assert CS.implied_rate(months, ic, [10, 10, 5], spend, (2024, 1)) is None


def test_age_leaves_business_rows_and_bad_dates_out(tmp_path):
    zp = tmp_path / "z.zip"
    write_odd(zp, _odd_rows() + [dict(hash=H(6), opened="11/01/2023", dob="", spend=[(1, 0)] * 6),
                                 dict(hash=H(7), opened="11/01/2023", dob="01/01/2099", spend=[(1, 0)] * 6)])
    scan = CS.scan_odd(zp, {H(i): ("dm" if i < 3 else "ref") for i in range(1, 8)})
    ag = CS.age_profile(scan, dt.date(2024, 5, 31))
    assert ag["excluded"] == {"business": 1, "no_dob": 1, "implausible": 1}
    assert ag["n"] == 4 and sum(ag["counts"].values()) == 4
    assert ag["counts"]["25-34"] == 1 and ag["counts"]["35-44"] == 1 and ag["counts"]["55+"] == 2
    assert ag["share_44_or_younger"] == pytest.approx(0.5)
    assert CS.BENCHMARK_AGES == (("Fintech Customer", 35), ("Bank Customer", 50), ("Credit Union", 53))


def test_the_product_mix_counts_every_account_found_including_closed(tmp_path):
    zp = tmp_path / "z.zip"
    write_odd(zp, _odd_rows())
    scan = CS.scan_odd(zp, {H(i): ("dm" if i < 3 else "ref") for i in range(1, 6)})
    mix = {p["product"]: p for p in CS.product_mix(scan)}
    assert mix["Hassle Free"]["direct_mail"] == 2 and mix["Hassle Free"]["referral"] == 1 and mix["Hassle Free"]["total"] == 3
    assert mix["Elements Checking"]["referral"] == 1 and mix["Business Value Checking"]["total"] == 1
    assert CS.product_mix(scan)[0]["product"] == "Hassle Free"


# ------------------------------------------------------------------ compute() end to end
def _full_sheet_inputs(root, tmp_path, months=24, first=(2024, 9), dm_start=(2025, 3)):
    """A workbook with `months` cohorts, a direct-mail list, an export and an ODD, all synthetic and consistent:
    the workbook's interchange is exactly 0.9% of the ODD's spend for the accounts of each cohort."""
    write_workbook(workbook_file(root, PERIOD), months=months, first=first)
    write_charts(charts_file(root))
    return None


def test_compute_returns_none_without_a_direct_mail_list(root, tmp_path):
    write_workbook(workbook_file(root, PERIOD), months=15, first=(2025, 6))
    write_charts(charts_file(root))
    _export_for_the_fixture(root)
    d = _sheet(root, tmp_path)
    assert CS.compute(d) is None


def test_compute_without_an_odd_gives_the_counts_and_says_why_not_more(root, tmp_path):
    write_workbook(workbook_file(root, PERIOD), months=15, first=(2025, 6))
    write_charts(charts_file(root))
    _export_for_the_fixture(root)
    write_dm_with_hashes(dm_file(root), [(H(900 + i), dt.datetime(2026, 7, 1 + i), "10") for i in range(3)])
    d = _sheet(root, tmp_path)
    b = CS.compute(d)
    assert b["totals"]["direct_mail"] == 3 and b["totals"]["accounts"] == sum(d["monthly_detail_full"]["accounts_opened"])
    assert b["totals"]["referral"] == b["totals"]["accounts"] - 3
    assert b["odd"] is None and "No ODD extract" in b["odd_note"]
    assert b["dm_first_month"] == "Jul 26" and b["overlap"] == 0


# ------------------------------------------------------------------ the charts: every cohort, the early ones called out
def _full_md(n):
    ms = []
    y, m = 2022, 12
    for _ in range(n):
        ms.append(dt.date(y, m, 1).strftime("%b %y"))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return {"months": ms, "accounts_opened": [10 + i for i in range(n)], "cumulative_accounts": [sum(10 + j for j in range(i + 1)) for i in range(n)],
            "avg_balance": [900.0] * n, "spread": [100.0] * n, "interchange": [(n - i) * 10.0 for i in range(n)],
            "nsf_od": [50.0] * n, "other_fees": [5.0] * n, "profit_contribution": [(n - i) * 10.0 + 155 for i in range(n)],
            "total_expense": [20.0] * n, "profit_to_date": [0.0] * n}


def test_the_charts_read_the_full_tab_when_the_sheet_has_it():
    d = {"monthly_detail": {"months": ["Jul 26"], "accounts_opened": [1], "nsf_od": [0], "other_fees": [0]}, "monthly_detail_full": _full_md(46)}
    c = CH.cohorts(d)
    assert len(c["months"]) == 46 and CH.is_all_cohorts(d) and c["nsf_other"][0] == 55.0
    assert CH._months_open(d)[0] == 46 and CH._months_open(d)[-1] == 1
    d2 = {"monthly_detail": {"months": ["Mar 26", "Apr 26"], "accounts_opened": [4, 5], "nsf_od": [1, 1], "other_fees": [1, 1]}}
    assert len(CH.cohorts(d2)["months"]) == 2 and not CH.is_all_cohorts(d2) and not CH.has_early_split(d2)


def test_program_years_are_twelve_cohorts_from_the_start_and_the_last_may_be_short():
    assert CH.program_years(46) == [(0, 11), (12, 23), (24, 35), (36, 45)]
    assert CH.program_years(12) == [(0, 11)] and CH.program_years(5) == [(0, 4)]


def test_early_stats_are_the_first_twelve_cohorts():
    d = {"monthly_detail_full": _full_md(30), "monthly_detail": {}}
    es = CH.early_stats(d, ["interchange"])
    inter = d["monthly_detail_full"]["interchange"]
    assert es["revenue"] == sum(inter[:12]) and es["total"] == sum(inter) and es["share"] == pytest.approx(sum(inter[:12]) / sum(inter))
    assert es["accounts"] == sum(range(10, 22)) and (es["first"], es["last"]) == ("Dec 22", "Nov 23")
    mo = CH._months_open(d)
    assert es["per_acct_month"] == pytest.approx(sum(inter[:12]) / sum((10 + i) * mo[i] for i in range(12)))
    assert CH.early_stats({"monthly_detail_full": _full_md(12), "monthly_detail": {}}, ["interchange"]) is None   # nothing beyond the first year
    both = CH.early_stats(d, ["nsf_od", "other_fees"])
    assert both["revenue"] == 12 * 55.0


def test_a_long_program_draws_every_cohort_without_a_label_outside_the_axis_format(tmp_path):
    d = {"monthly_detail": {}, "monthly_detail_full": _full_md(46)}
    for key, per in (("interchange", False), ("interchange", True), ("nsf_other", False)):
        CH._monthly_bar(d, key, str(tmp_path / f"{key}{per}.png"), per)
        assert (tmp_path / f"{key}{per}.png").stat().st_size > 5000
    CH.c_composition(d, str(tmp_path / "comp.png"))
    CH.c_bucket_compare(d, str(tmp_path / "bucket.png"))
    assert (tmp_path / "comp.png").exists() and (tmp_path / "bucket.png").exists()
    yv = CH.year_group_values(d, "interchange", False)
    assert len(yv) == 4 and yv[0] == sum(d["monthly_detail_full"]["interchange"][:12])


# ------------------------------------------------------------------ the deck
def _deck_with_cohorts(root, tmp_path, *, dm=False, months=24, first=(2024, 9)):
    write_workbook(workbook_file(root, PERIOD), months=months, first=first, generated="9/9/2026 8:00:00 AM")
    write_charts(charts_file(root))
    write_referrals(referral_file(root))
    if dm:
        write_dm_with_hashes(dm_file(root), [(H(700 + i), dt.datetime(2025, 3 + (i % 6), 1 + i), "10") for i in range(9)])
    d = _sheet(root, tmp_path)
    return d, *_build_deck(root, tmp_path, d)


def _text(prs):
    return " ".join(sh.text_frame.text for s in prs.slides for sh in s.shapes if sh.has_text_frame)


def test_a_long_program_shows_program_years_the_early_year_and_every_cohort(root, tmp_path):
    from validate_deck import package_findings
    d, out, prs = _deck_with_cohorts(root, tmp_path)
    assert package_findings(out) == []
    ts = _titles(prs)
    assert "Program Results by Opening Year" in ts and "Program Results by Month Opened" not in ts
    s = prs.slides[ts.index("Program Results by Opening Year")]
    tbl = next(sh for sh in s.shapes if sh.has_table).table
    head = [c.text for c in tbl.rows[0].cells]
    assert head[:3] == ["Opened", "Year 1", "Year 2"] and head[-1] == "Program to Date"
    assert "Account Profit Contribution" in [r.cells[0].text for r in tbl.rows]
    # year 1 (the early referrals) has the orange header cell, the others navy
    from pptx.dml.color import RGBColor
    import brand
    assert tbl.cell(0, 1).fill.fore_color.rgb == RGBColor.from_string(brand.ORANGE.lstrip("#"))
    assert tbl.cell(0, 2).fill.fore_color.rgb == RGBColor.from_string(brand.NAVY.lstrip("#"))
    txt = _text(prs)
    assert "have earned $" in txt and "first 12 months" in txt
    # the cohort charts name every cohort and carry the early-year tile
    assert "all 24 cohorts (Sep'24 – Aug'26)" in txt and "Year 1 interchange" in txt and "Year 1 / acct / month" in txt
    notes = s.notes_slide.notes_text_frame.text
    assert "program years of 12 cohorts" in notes and "orange header" in notes


def test_a_young_program_keeps_the_month_table_and_no_early_tile(root, tmp_path):
    write_workbook(workbook_file(root, PERIOD), months=9)
    write_charts(charts_file(root))
    write_referrals(referral_file(root))
    d = _sheet(root, tmp_path)
    out, prs = _build_deck(root, tmp_path, d)
    ts = _titles(prs)
    assert "Program Results by Opening Year" in ts       # the full tab is on the sheet, so even nine cohorts group by year
    assert "Year 1 interchange" not in _text(prs)         # no cohort beyond the first twelve to set it against


def test_the_appendix_has_a_page_per_program_year_and_rows_under_bands(root, tmp_path):
    d, out, prs = _deck_with_cohorts(root, tmp_path, dm=True)
    ts = _titles(prs)
    pages = [t for t in ts if t.startswith("Appendix: Monthly Detail")]
    assert pages == ["Appendix: Monthly Detail (1 of 2)", "Appendix: Monthly Detail (2 of 2)"]      # 24 cohorts = two program years
    s = prs.slides[ts.index(pages[0])]
    tbl = next(sh for sh in s.shapes if sh.has_table).table
    first_col = [r.cells[0].text for r in tbl.rows]
    assert first_col[0] == "Month Opened" and len(tbl.columns) == 13        # label + twelve cohorts
    bands = [t for t in first_col if t in ("ACCOUNTS", "REVENUE", "EXPENSE & PROFIT")]
    assert bands == ["ACCOUNTS", "REVENUE", "EXPENSE & PROFIT"]
    assert first_col.index("ACCOUNTS") < first_col.index("Accounts Opened") < first_col.index("REVENUE") < first_col.index("Interchange Income") < first_col.index("EXPENSE & PROFIT") < first_col.index("Total Expense")
    assert "  from direct mail" in first_col and "  from branch referrals" in first_col          # the split rows, with a list
    assert "Year 1 · " in "".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)


def test_without_a_direct_mail_list_there_are_no_split_rows_or_slides(root, tmp_path):
    d, out, prs = _deck_with_cohorts(root, tmp_path, dm=False)
    ts = _titles(prs)
    assert "Direct Mail and Branch Referral Accounts" not in ts and "Interchange by Channel" not in ts
    s = prs.slides[ts.index("Appendix: Monthly Detail (1 of 2)")]
    first_col = [r.cells[0].text for sh in s.shapes if sh.has_table for r in sh.table.rows]
    assert "  from direct mail" not in first_col


def test_with_a_direct_mail_list_the_deck_shows_the_split(root, tmp_path):
    d, out, prs = _deck_with_cohorts(root, tmp_path, dm=True)
    ts = _titles(prs)
    i = ts.index("Direct Mail and Branch Referral Accounts")
    s = prs.slides[i]
    txt = " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame).replace("\n", " ")
    tot = sum(d["monthly_detail_full"]["accounts_opened"])
    assert f"{tot:,}" in txt and "Branch referral" in txt and "Direct mail" in txt
    n = s.notes_slide.notes_text_frame.text
    assert "less the direct-mail accounts" in n and "derived" in n and "measured" in n and CID in n
    # no ODD, so no interchange slide, and the Program Results table carries the split rows
    assert "Interchange by Channel" not in ts and "Age Demographics" not in ts
    t = prs.slides[ts.index("Program Results by Opening Year")]
    cells = [r.cells[0].text.strip() for sh in t.shapes if sh.has_table for r in sh.table.rows]
    assert "from direct mail" in cells and "from branch referrals" in cells
    # the agenda names the split; the divider does not repeat the referral slide
    agenda = " ".join(sh.text_frame.text for sh in prs.slides[ts.index("Agenda")].shapes if sh.has_text_frame)
    assert "Direct Mail Split" in agenda


# ------------------------------------------------------------------ branches
def test_every_branch_is_listed_and_a_long_list_collapses_its_smallest(root, tmp_path):
    write_referrals(referral_file(root))
    write_charts(charts_file(root))
    d = _sheet(root, tmp_path)
    for n_branches, expect_other in ((8, False), (20, True)):
        bl = [{"name": f"Branch {i:02d}", "number": str(i), "referrals": 100 - i, "goal": 120} for i in range(n_branches)]
        d["referrals"]["by_branch"]["branches"] = bl
        out, prs = _build_deck(root, tmp_path, d, referrals_only=True)
        s = prs.slides[_titles(prs).index("Results by Branch – Year to Date")]
        first = [r.cells[0].text for sh in s.shapes if sh.has_table for r in sh.table.rows]
        assert first[-1] == f"All {n_branches} Branches"
        listed = [t for t in first if t.startswith("Branch ")]
        if expect_other:
            assert len(listed) == 13 and first[-2] == "All other branches (7)"
        else:
            assert len(listed) == n_branches          # the old table stopped at the top eight
        total = [r.cells[1].text for sh in s.shapes if sh.has_table for r in sh.table.rows][-1]
        assert total == str(sum(b["referrals"] for b in bl))
