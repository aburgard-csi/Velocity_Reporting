"""The ILS kickoff extract (build/ils_pipeline/kickoff_input.py, kickoff/core/io.py).

v5's loader tests (v5 tests/test_ils_kickoff.py at 7ba1e63, every test of core/io.py; the run,
reg_e and deck/report tests arrive with their own stages) on the RPE input folder
`Inputs/ILS Kickoff/<id>/`, plus the RPE-side lookup: one folder per client, never scanned.
"""
import pathlib

import pandas as pd
import pytest

import rpe_env
from ils_pipeline import kickoff_input
from ils_pipeline.kickoff.core import io


@pytest.fixture
def root(tmp_path, monkeypatch):
    for d in ("Inputs", "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir(parents=True)
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    return tmp_path


# ---- v5's loader tests --------------------------------------------------

def _book(flags, statuses=None):
    n = len(flags)
    return pd.DataFrame({
        io.ACCT_NO: range(n),
        io.ACCOUNT_STATUS: statuses or ["O"] * n,
        io.BUSINESS_FLAG: flags,
        io.STAT_CODE: ["ODP Account"] * n,
        io.TOTAL_ITEMS: [1] * n,
        io.PAID_ITEMS: [1] * n,
    })


# ---- 1. the split must account for the open book ------------------------

def test_the_segments_account_for_every_open_account():
    df = _book(["P", "P", "B"])
    codes = io.CodeConfig()
    assert not io.segment_warnings(df, codes), "a clean book warned"


def test_an_open_account_in_neither_segment_is_reported():
    """The notebook's old convention, arriving at the new code."""
    df = _book(["P", "P", "B", "", "Personal", "b"])
    warnings = io.segment_warnings(df, io.CodeConfig())
    assert warnings, "three unclassified accounts passed silently"
    text = " ".join(warnings)
    assert "3" in text, f"the count of dropped accounts is not named: {text}"
    for value in ("Personal", "b"):
        assert value in text, f"the unmatched value {value!r} is not named: {text}"


def test_a_closed_account_is_not_counted_as_dropped():
    """Closed accounts are out of scope by design, not by accident."""
    df = _book(["P", "B", "Personal"], statuses=["O", "O", "C"])
    assert not io.segment_warnings(df, io.CodeConfig())


def test_the_warning_follows_the_configured_codes():
    """A client on the old convention configures it and the warning clears."""
    df = _book(["Personal", "Business"])
    codes = io.CodeConfig(personal_code="Personal", business_code="Business")
    assert not io.segment_warnings(df, codes)


# ---- 2. the newest extract wins -----------------------------------------

def _extracts(tmp_path, *names):
    # v5: tmp_path / "2026-09" / "1842". RPE: Inputs/ILS Kickoff/1842/, no month folder.
    d = rpe_env.input_dir("ILS Kickoff", create=False) / "1842"
    d.mkdir(parents=True)
    for name in names:
        (d / name).write_text("x", encoding="utf-8")
    return rpe_env.input_dir("ILS Kickoff", create=False)


@pytest.mark.usefixtures("root")
def test_the_newest_extract_wins(tmp_path):
    root = _extracts(tmp_path, "1842_OneTimeData_20260901.xlsx",
                     "1842_OneTimeData_20261001.xlsx")
    picked = io.resolve_data_file(root, "1842", "2026-09")
    assert picked.name == "1842_OneTimeData_20261001.xlsx"


@pytest.mark.usefixtures("root")
def test_the_date_beats_the_file_extension(tmp_path):
    """A stale csv must not outrank a current xlsx."""
    root = _extracts(tmp_path, "1842_OneTimeData_20260901.csv",
                     "1842_OneTimeData_20261001.xlsx")
    assert io.resolve_data_file(root, "1842", "2026-09").name.endswith("20261001.xlsx")


@pytest.mark.usefixtures("root")
def test_an_undated_file_is_still_found(tmp_path):
    root = _extracts(tmp_path, "1842_OneTimeData.xlsx")
    assert io.resolve_data_file(root, "1842", "2026-09").name == "1842_OneTimeData.xlsx"


@pytest.mark.usefixtures("root")
def test_a_dated_extract_outranks_an_undated_one(tmp_path):
    root = _extracts(tmp_path, "1842_OneTimeData.xlsx",
                     "1842_OneTimeData_20261001.xlsx")
    assert io.resolve_data_file(root, "1842", "2026-09").name.endswith("20261001.xlsx")


# ---- 3. colliding spellings are refused by name -------------------------

def test_two_spellings_of_one_column_are_refused_by_name():
    df = pd.DataFrame({"Business?": ["P"], "Business Flag": ["P"], "AcctNo": [1]})
    with pytest.raises(ValueError) as exc:
        io.to_canonical(df)
    message = str(exc.value)
    assert "Business?" in message and "Business Flag" in message, message


def test_one_spelling_is_fine():
    df = pd.DataFrame({"Business?": ["P"], "AcctNo": [1]})
    out, _, _ = io.to_canonical(df)
    assert io.BUSINESS_FLAG in out.columns
    assert len(out.columns) == len(set(out.columns))


# ---- 5. one client's output never lands in another's folder -------------
#
# Ran 1840 with --output-dir ...\2026-09\1842 and the run wrote
# "1840 - ILS Kickoff Report Data-SEP26.xlsx" into 1842's folder without a
# word. Two clients' files in one directory is the worst outcome this tool
# has; the filename carrying the right id is not a defence, because the
# folder is what anyone browses by.

def test_an_output_folder_naming_another_client_is_refused(tmp_path):
    wrong = tmp_path / "03-Output" / "ILS" / "2026-09" / "1842"
    with pytest.raises(ValueError) as exc:
        io.check_output_dir("1840", wrong)
    message = str(exc.value)
    assert "1840" in message and "1842" in message, message


def test_the_client_s_own_folder_is_accepted(tmp_path):
    right = tmp_path / "03-Output" / "ILS" / "2026-09" / "1840"
    assert io.check_output_dir("1840", right) == right


def test_a_folder_that_names_no_client_is_accepted(tmp_path):
    """A scratch path is the operator's business; a wrong client id is not."""
    scratch = tmp_path / "somewhere" / "else"
    assert io.check_output_dir("1840", scratch) == scratch


def test_the_period_folder_is_not_mistaken_for_a_client(tmp_path):
    """2026-09 contains digits; only a bare four-digit segment is an id."""
    right = tmp_path / "ILS" / "2026-09" / "1840"
    assert io.check_output_dir("1840", right) == right


def test_a_default_output_dir_is_derived_from_the_client_and_period(tmp_path):
    out = io.default_output_dir(tmp_path, "1840", "2026-09")
    assert out.parts[-2:] == ("2026-09", "1840")


# ---- 6. the codes are a question, not a default -------------------------

def test_the_field_summary_names_every_code_column():
    df = _book(["P", "B", "Personal"])
    summary = io.field_summary(df)
    assert set(summary) >= {io.BUSINESS_FLAG, io.ACCOUNT_STATUS, io.STAT_CODE}


def test_the_field_summary_counts_the_values():
    df = _book(["P", "P", "B"])
    assert io.field_summary(df)[io.BUSINESS_FLAG] == [["P", 2], ["B", 1]]


def test_an_absent_column_is_absent_not_empty():
    """A column that is not there and a column with no values are different
    answers, and only one of them is a data problem."""
    df = _book(["P"]).drop(columns=[io.STAT_CODE])
    assert io.field_summary(df)[io.STAT_CODE] is None


def test_the_text_summary_keeps_opt_in_and_eligibility_apart():
    """Eligibility is the OD Status code. Reg E opt-in is a separate variable
    the member sets. Calling the cross-tab "Reg E eligibility" conflated two
    things (James, 2026-09-09)."""
    text = io.summarise_fields(_book(["P", "B"]))
    assert "Never choose them yourself" in text
    assert "OD-eligible" in text
    assert "Reg-E eligible" not in text, "opt-in and eligibility conflated again"


# ---- 9. Reg E opt-in is its own mapping ---------------------------------
#
# The run asks which Stat Code means OD-eligible and never asks which Reg E
# Flag value means opted in. 1842 carries only 'D'; 1840 will carry yeses.
# Reading 'Y' as opted-in is a guess that happens to work on one client --
# the same class of guess as ODP Account.

def _rege_book(flags):
    n = len(flags)
    return pd.DataFrame({
        io.ACCT_NO: range(n), io.ACCOUNT_STATUS: ["O"] * n,
        io.BUSINESS_FLAG: ["P"] * n, io.STAT_CODE: ["0"] * n,
        io.REG_E_FLAG: flags, io.TOTAL_ITEMS: [1] * n, io.PAID_ITEMS: [1] * n,
    })


def test_the_config_carries_an_opt_in_mapping():
    codes = io.CodeConfig(rege_opt_in=["Y"], rege_opt_out=["D", "N"])
    assert codes.rege_opt_in == ["Y"] and "D" in codes.rege_opt_out


def test_unmapped_values_default_to_unconfirmed_not_to_a_guess():
    """'Y' meaning opted in is a guess that happens to work on one client."""
    assert io.CodeConfig().rege_opt_in == []


def test_an_unconfirmed_mapping_is_reported():
    warnings = io.rege_warnings(_rege_book(["Y", "D", "D"]), io.CodeConfig())
    assert warnings and "not confirmed" in warnings[0].lower()


def test_a_confirmed_mapping_that_covers_the_column_is_silent():
    codes = io.CodeConfig(rege_opt_in=["Y"], rege_opt_out=["D"])
    assert io.rege_warnings(_rege_book(["Y", "D", "D"]), codes) == []


def test_opt_in_alone_is_enough():
    """"I really only care about opted in. Everything else is opted out"
    (James, 2026-09-09). Asking for the complement made the operator
    enumerate a list they do not think in, and every value they forgot
    became an account counted as neither."""
    codes = io.CodeConfig(rege_opt_in=["Y"])
    assert io.rege_warnings(_rege_book(["Y", "D", "X", "X"]), codes) == []


def test_unmapped_columns_say_what_they_hold():
    """"Unmapped columns kept as-is" states a fact and leaves a question."""
    df = _rege_book(["Y", "D"])
    df["Return Item Fee YTD"] = [120.0, 80.0]
    detail = io._unmapped_detail(df, ["Return Item Fee YTD"])
    assert "200" in detail, detail
    assert "NO analysis reads" in detail


def test_opt_in_and_eligibility_stay_separate_in_the_config():
    codes = io.CodeConfig(eligible_stat_codes=["0"], rege_opt_in=["Y"])
    assert codes.eligible_stat_codes == ["0"]
    assert codes.rege_opt_in == ["Y"]


# ---- 10. the real item total, and fees kept apart from items ------------

def test_the_waiver_excluded_columns_are_the_total_when_present():
    """OD Items (No Waivers) + NSF Items (No Waivers) is the presented total
    (James, 2026-09-09). Total Items had resolved to the paid column on 1840,
    which is why every pay rate read 100%."""
    df = pd.DataFrame({io.OD_ITEMS: [3, 4], io.NSF_ITEMS: [2, 1],
                       io.TOTAL_ITEMS: [99, 99]})
    total, source = io.true_item_total(df)
    assert total.sum() == 10
    assert io.OD_ITEMS in source and io.NSF_ITEMS in source


def test_total_items_is_the_fallback_not_the_preference():
    df = pd.DataFrame({io.TOTAL_ITEMS: [5, 5]})
    total, source = io.true_item_total(df)
    assert total.sum() == 10 and source == io.TOTAL_ITEMS


def test_a_hundred_percent_on_the_real_total_is_a_finding_not_a_bug():
    """Once the right denominator is used, 100% stops being a symptom."""
    df = pd.DataFrame({io.OD_ITEMS: [3], io.NSF_ITEMS: [2], io.PAID_ITEMS: [5]})
    w = io.pay_rate_warnings(df, [])
    assert w and "not a column mix-up" in w[0]


def test_fees_are_reported_apart_from_items():
    """A fee is not an item. A rate dividing one by the other is nonsense."""
    df = pd.DataFrame({io.PAID_FEE_YTD: [90.0], io.RETURN_FEE_YTD: [60.0]})
    fees = io.fee_income(df)
    assert fees["paid item fees, YTD"] == 90
    assert fees["returned item fees, YTD"] == 60


# ---- 11. measure the assumption instead of carrying it ------------------

def test_the_run_reports_what_the_item_columns_actually_are():
    """OD Items is paid, NSF Items is returned, and the two sum to the
    total -- the working understanding, unconfirmed (James, 2026-09-09).
    Exactly the kind of assumption that produced a 100% pay rate, so the
    run measures it rather than carrying it."""
    df = pd.DataFrame({io.OD_ITEMS: [3, 4], io.NSF_ITEMS: [2, 1],
                       io.PAID_ITEMS: [3, 4], io.RETURNED_ITEMS: [2, 1],
                       io.TOTAL_ITEMS: [5, 5]})
    report = io.item_column_relationships(df)[0]
    assert "OD Items == Paid Items exactly" in report
    assert "NSF Items == Returned Items exactly" in report


def test_a_mismatch_is_stated_with_the_gap():
    df = pd.DataFrame({io.OD_ITEMS: [3], io.NSF_ITEMS: [2],
                       io.PAID_ITEMS: [3], io.RETURNED_ITEMS: [9]})
    report = io.item_column_relationships(df)[0]
    assert "differ by" in report


def test_nothing_is_claimed_when_the_columns_are_absent():
    assert io.item_column_relationships(pd.DataFrame({io.TOTAL_ITEMS: [1]})) == []


def test_lyr_is_not_called_last_year():
    """Last year or last rolling twelve is unconfirmed. Naming it a calendar
    year would be a guess printed as a fact."""
    fees = io.fee_income(pd.DataFrame({io.PAID_FEE_LYR: [10.0]}))
    assert "prior period (LYR)" in list(fees)[0]


# ---- RPE side -------------------------------------------------------------

CSV = ("AcctNo,Acct Stat,Business?,Stat Code,Prod Code,Total Items,Paid Items,Returned Items,"
       "OD Limit,Reg E Flag,Return Item Fee YTD,Branch\n"
       "001,O,P,ODP Account,10,3,3,0,500,Y,0,Main\n"
       "002,O,B,ODP Account,20,5,4,1,1000,D,27,Main\n"
       "003,C,P,None,10,abc,0,0,0,D,0,East\n")


def write_csv(root, client_id, name, text=CSV):
    d = root / "Inputs" / "ILS Kickoff" / client_id
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text("﻿" + text, encoding="utf-8")
    return p


def test_the_loader_reads_and_canonicalizes_the_client_s_extract(root):
    write_csv(root, "1842", "1842_OneTimeData_20261001.csv")
    df, warnings = kickoff_input.load("1842", "2026-10")
    assert {io.ACCT_NO, io.ACCOUNT_STATUS, io.BUSINESS_FLAG, io.STAT_CODE,
            io.PRODUCT_CODE, io.REG_E_FLAG, io.RETURN_FEE_YTD} <= set(df.columns)
    assert pd.isna(df[io.TOTAL_ITEMS].iloc[2])                  # "abc" coerced, not kept as text
    assert df[io.RETURN_FEE_YTD].sum() == 27
    assert df.attrs["client_id"] == "1842" and df.attrs["period"] == "2026-10"
    assert pathlib.Path(df.attrs["source_path"]) == (
        root / "Inputs" / "ILS Kickoff" / "1842" / "1842_OneTimeData_20261001.csv")
    assert len(warnings) == 1 and "Branch" in warnings[0]        # the one column nothing reads


def test_a_missing_required_column_is_refused_by_name(root):
    write_csv(root, "1842", "1842_OneTimeData_20261001.csv", "AcctNo,Acct Stat\n001,O\n")
    with pytest.raises(KeyError, match="Business Flag"):
        kickoff_input.load("1842", "2026-10")


def test_a_missing_folder_names_the_kickoff_input(root):
    with pytest.raises(FileNotFoundError, match="ILS Kickoff"):
        kickoff_input.find_extract("9999", "2026-10")


def test_a_client_reads_only_its_own_folder(root):
    write_csv(root, "1842", "1842_OneTimeData_20261001.csv")
    write_csv(root, "18420", "18420_OneTimeData_20991231.csv")       # newer, another client
    write_csv(root, "1840", "1842_OneTimeData_20991231.csv")         # 1842's name, 1840's folder
    picked = kickoff_input.find_extract("1842", "2026-10")
    assert picked.parent.name == "1842"
    assert picked.name == "1842_OneTimeData_20261001.csv"
    df, _ = kickoff_input.load("1842", "2026-10")
    assert pathlib.Path(df.attrs["source_path"]) == picked


def test_the_folder_is_never_scanned_or_created(root):
    assert rpe_env.INPUT_KIND_DIRS["ILS Kickoff"] == "ILS Kickoff"
    assert "ILS Kickoff" in rpe_env.NOT_SCANNED_KINDS
    assert "ILS Kickoff" not in rpe_env._scanned_dirnames()
    assert all("ILS Kickoff" not in str(d) for d in rpe_env.report_dirs())
    kickoff_input.folder("4242")
    assert not (root / "Inputs" / "ILS Kickoff").exists()
