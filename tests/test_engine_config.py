"""The engine's client record is built from the ARS code tables and the workbook rate (2026-09-18).

A client absent from the tables gets a record whose funnel stages are skipped with a warning,
never zeros; a missing NSF fee is left absent, never invented; the Reg E code sets come from
the code table's wording through odd_rows.rege_label, the deck's own reading.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build" / "ars_pipeline"), str(REPO / "build")]
import engine_config as EC  # noqa: E402

TABLES = {
    "_source": {"extracted": "2026-09-15 08:00", "tables": ["product_codes", "rege_codes", "status_codes"]},
    "product_codes": {"1441": {
        "CHK": {"description": "Checking", "is_business": "0", "eligible_for_debit_card": "1", "actively_offered_product": "1"},
        "BCK": {"description": "Business Checking", "is_business": "1", "eligible_for_debit_card": "1", "actively_offered_product": "1"},
        "OLD": {"description": "Retired", "is_business": "0", "eligible_for_debit_card": "0", "actively_offered_product": "0"},
    }},
    "rege_codes": {"1441": {
        "Y": {"description": "Opted In", "optinstatus": "Yes"},
        "N": {"description": "Opted Out", "optinstatus": "No"},
        "D": {"description": "No Response Recevied", "optinstatus": None},
        "Q": {"description": "Pending", "optinstatus": "Maybe"},
    }},
    "status_codes": {"1441": {
        "O": {"description": "Open", "active": "1"},
        "A": {"description": "Active", "active": "True"},
        "C": {"description": "Closed", "active": "0"},
    }},
}


def test_a_client_in_the_tables_gets_its_code_sets():
    warns = []
    rec = EC.record_for("1441", TABLES, {"wb_ic_rate": 0.0064, "wb_nsf_fee": 32.0, "wb_found": "x.xlsx"},
                        name="FNB Alaska", warn=warns.append)
    assert rec["EligibleStatusCodes"] == ["A", "O"]
    assert rec["EligibleProductCodes"] == ["BCK", "CHK"]
    assert rec["BusinessProductCodes"] == ["BCK"]
    assert rec["RegEOptInCode"] == ["Y"] and rec["RegEOptOutCode"] == ["N"] and rec["RegEDefaultCode"] == ["D"]
    assert rec["ICRate"] == 0.0064 and rec["NSF_OD_Fee"] == 32.0
    assert rec["EligibleMailCode"] == "Yes" and rec["Products"] == ["ARS"] and rec["ClientName"] == "FNB Alaska"
    assert rec["_config_source"]["rate_source"] == "workbook"
    assert any("Q (Maybe)" in w for w in warns), warns          # unmapped wording is reported, not guessed


def test_a_client_absent_from_the_tables_skips_stages_with_warnings_not_zeros():
    warns = []
    rec = EC.record_for("9999", TABLES, None, warn=warns.append)
    assert "EligibleStatusCodes" not in rec and "EligibleProductCodes" not in rec
    assert "RegEOptInCode" not in rec
    assert rec["ICRate"] == EC.DEFAULT_RATE and "NSF_OD_Fee" not in rec
    assert rec["_config_source"]["rate_source"] == "default"
    joined = " ".join(warns)
    for must in ("status funnel stage is skipped", "product funnel stage is skipped",
                 "wording only", "default", "NSF pricing declines"):
        assert must in joined, (must, warns)


def test_no_tables_at_all_is_the_same_as_an_absent_client():
    rec = EC.record_for("1441", None, None)
    assert "EligibleStatusCodes" not in rec and rec["ICRate"] == EC.DEFAULT_RATE


def test_overrides_win_over_the_workbook():
    rec = EC.record_for("1441", TABLES, {"wb_ic_rate": 0.0064}, overrides={"ICRate": 0.0070, "NSF_OD_Fee": ""})
    assert rec["ICRate"] == 0.0070 and "NSF_OD_Fee" not in rec       # a blank override is not a value


def test_the_record_is_a_plain_dict_the_engine_can_inject_into():
    rec = EC.record_for("1441", TABLES)
    rec["_txn"] = {"txn_anchor": "2026-07"}
    assert isinstance(rec, dict) and rec["_txn"]["txn_anchor"] == "2026-07"


def test_the_engine_funnel_skips_a_missing_stage_rather_than_emptying_the_base():
    """core/subsets.build_subsets on a record with no code sets: every account stays in."""
    pd = __import__("pytest").importorskip("pandas")
    from engine.core.subsets import build_subsets
    from engine.core.periods import Month
    df = pd.DataFrame({"Stat Code": ["O", "O", "C"], "Prod Code": ["CHK", "OLD", "CHK"],
                       "Mailable?": ["Yes", "Yes", "Yes"], "Business?": ["No", "No", "No"],
                       "Debit?": ["Yes", "No", "Yes"], "Date Closed": [None, None, "1/1/2026"],
                       "Jul26 PIN $": [1, 0, 0], "Jul26 Sig $": [1, 0, 0]})
    bare = build_subsets(df, EC.record_for("9999", TABLES), Month(2026, 7))
    assert len(bare.eligible) == 2 and any("skipped" in w for w in bare.warnings)
    coded = build_subsets(df, EC.record_for("1441", TABLES), Month(2026, 7))
    assert len(coded.eligible) == 1                                   # OLD is not an offered product
