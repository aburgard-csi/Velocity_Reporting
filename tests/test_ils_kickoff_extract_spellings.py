"""Two real kickoff extracts the v5 loader could not run (stage g12-05).

1840 FNB KY names its item counts "Paid Annualized" / "Returned Annualized": v5 refused the file
("Missing required column(s) ... ['Paid Items']"). 1842 carries Items / Paid / Returned blank on
every row and the counts only as "... # Calc" estimates from fees: v5 loaded it, read zero items
everywhere and failed in the deck on a 0/0 share. Synthetic rows, the real files' headers.
"""
import pytest

from ils_pipeline import kickoff_input
from ils_pipeline.kickoff.core import io


@pytest.fixture(autouse=True)
def _v5_pandas():
    from ils_pipeline.kickoff._v5.compat import legacy_strings
    with legacy_strings():
        yield


@pytest.fixture
def root(tmp_path, monkeypatch):
    for d in ("Inputs", "Outputs", "Build Artifacts"):
        (tmp_path / d).mkdir(parents=True)
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    return tmp_path


def _write(root, client_id, text):
    d = root / "Inputs" / "ILS Kickoff" / client_id
    d.mkdir(parents=True)
    (d / f"{client_id}_OneTimeData_20260901.csv").write_text(text, encoding="utf-8")


ANNUALIZED = ("AcctNo,Items,Paid Annualized,Returned Annualized,ODCode,Business,OPStatus\n"
              "1,5,4,1,0,P,O\n2,0,0,0,0,B,O\n3,3,2,1,0,P,C\n")

CALC = ("AcctNo,Items,Paid,Returned,overdraftLimit,ODCode,ProductCode,Business,opStatus,Rege,"
        "opendate,AvgColBal,deps_amt,deps,Paid Items # Calc,Returned Items # Calc,Swipes,TransAmt\n"
        "1,,,,500,0,0B,P,O,D,2019-03-04,1200,3000,4,2.5,1,20,800\n"
        "2,,,,0,0,B2,B,O,D,2020-01-02,5400,9000,9,0,0,3,90\n"
        "3,,,,250,0,0B,P,O,D,2021-07-16,300,700,2,1,2,11,260\n")


def test_annualized_columns_are_the_paid_and_returned_items(root):
    _write(root, "1840", ANNUALIZED)
    df, _ = kickoff_input.load("1840", "2026-09")
    assert df[io.PAID_ITEMS].tolist() == [4, 0, 2]
    assert df[io.RETURNED_ITEMS].tolist() == [1, 0, 1]
    assert (df[io.TOTAL_ITEMS] == df[io.PAID_ITEMS] + df[io.RETURNED_ITEMS]).all()


def test_blank_item_counts_still_give_the_field_summary_and_say_why(root):
    _write(root, "1842", CALC)
    df, warnings = kickoff_input.load("1842", "2026-09")
    text = " ".join(warnings)
    assert "blank on every row" in text and "Paid Items # Calc" in text
    assert "--items-from-calc" in text


def test_blank_item_counts_refuse_the_run(root):
    _write(root, "1842", CALC)
    df, _ = kickoff_input.load("1842", "2026-09")
    with pytest.raises(ValueError, match="blank on every row"):
        io.resolve_item_columns(df)


def test_the_calc_estimates_are_used_only_on_request_and_labelled(root):
    _write(root, "1842", CALC)
    df, _ = kickoff_input.load("1842", "2026-09")
    warnings = io.resolve_item_columns(df, items_from_calc=True)
    assert df[io.PAID_ITEMS].tolist() == [2.5, 0, 1]
    assert df[io.RETURNED_ITEMS].tolist() == [1, 0, 2]
    assert df[io.TOTAL_ITEMS].tolist() == [3.5, 0, 3]
    assert len(warnings) == 1 and warnings[0].startswith("ESTIMATED ITEM COUNTS")


def test_a_file_with_counted_items_is_untouched(root):
    _write(root, "1840", ANNUALIZED)
    df, _ = kickoff_input.load("1840", "2026-09")
    before = df.copy()
    assert io.resolve_item_columns(df, items_from_calc=True) == []
    assert df.equals(before)


def test_the_run_refuses_and_then_runs_with_the_flag(root):
    _write(root, "1842", CALC)
    refused = kickoff_input.run_kickoff("1842", "2026-09", open_code="O", eligible_stat_codes="0")
    assert "blank on every row" in refused
    done = kickoff_input.run_kickoff("1842", "2026-09", open_code="O", eligible_stat_codes="0",
                                     items_from_calc=True)
    assert "kickoff complete" in done and "ESTIMATED ITEM COUNTS" in done
