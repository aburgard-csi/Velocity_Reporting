"""CSM action items: the Lift Matrix filename flag and codes a client's ARS code tables do not list."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import perf_actions as A  # noqa: E402


def test_lift_matrix_flag_reads_every_filename_form_the_data_team_uses():
    assert A.lift_matrix_flag("1453-2026.09-Connex CU-Workbook_v2_1_0_LM EXPIRED.xlsx") == "LM EXPIRED"
    assert A.lift_matrix_flag("1780-2026.09-LM EXPIRED-USF CU-Workbook_v2_1_0.xlsx") == "LM EXPIRED"
    assert A.lift_matrix_flag("1487-2026.09-Orsa CU-Workbook_v2_1_0_NEEDS LIFT MATRIX.xlsx") == "NEEDS LIFT MATRIX"
    assert A.lift_matrix_flag("1637-2026.09-Ouachita Valley FCU-Workbook_v2_1_0_NEW LIFT MATRIX NEEDED.xlsx") \
        == "NEW LIFT MATRIX NEEDED"
    assert A.lift_matrix_flag("1743-2026.08-Mid American CU-Workbook_v2_1_0_needs lift matrix.xlsx") == "needs lift matrix"
    assert A.lift_matrix_flag("1204-2026.09-FSB Michigan-Workbook_v2_1_0.xlsx") is None
    assert A.lift_matrix_flag(None) is None


def test_unmapped_lists_values_the_table_lacks_most_accounts_first():
    values = {"Opt Out": [8376, 5000, ""], "Opt In POS OD Limit": [2, 2, ""], "Zeta": [2, 0, ""]}
    table = {"Opt Out": {}, "Opt Out Re": {}}
    assert [r["value"] for r in A.unmapped(values, table)] == ["Opt In POS OD Limit", "Zeta"]
    assert A.unmapped(values, table)[0] == {"value": "Opt In POS OD Limit", "accounts": 2, "open": 2, "desc": ""}


def _overview(**codes):
    base = {"status": {"C": [10, 0, ""]}, "product": {"20111": [3, 3, "Kasasa"]}, "reg_e": {},
            "mail": {"Yes": [9, 9, ""], "No": [1, 0, ""]}, "reg_e_column": "Aug26 Reg E Code"}
    base.update(codes)
    return {"month": "Aug26", "codes": base}


TABLES = {"status_codes": {"1615": {"C": {}, "O": {}}}, "product_codes": {"1615": {"20100": {}}}, "rege_codes": {}}


def test_client_actions_count_the_lift_matrix_and_each_unmapped_kind():
    got = A.client_actions("1615", _overview(), TABLES, {"workbook": "1615-2026.09-X-Workbook_LM EXPIRED.xlsx"})
    assert got["lift_matrix"] == {"flag": "LM EXPIRED", "workbook": "1615-2026.09-X-Workbook_LM EXPIRED.xlsx"}
    assert [c["label"] for c in got["codes"]] == ["Product Codes not mapped"]
    assert got["codes"][0]["values"] == [{"value": "20111", "accounts": 3, "open": 3, "desc": "Kasasa"}]
    assert got["count"] == 2 and got["unchecked"] == []


def test_a_client_with_no_code_table_lists_every_value_and_says_so():
    got = A.client_actions("1615", _overview(reg_e={"Y": [5, 5, ""]}), TABLES, {})
    rege = [c for c in got["codes"] if c["kind"] == "reg_e"][0]
    assert rege["no_table"] is True and rege["values"][0]["value"] == "Y"


def test_a_product_code_with_no_personal_business_flag_is_listed_under_the_product_mapping():
    tables = {"status_codes": {}, "rege_codes": {},
              "product_codes": {"1615": {"20100": {"is_business": "0"}, "30100": {"is_business": None},
                                         "40100": {"is_business": "1"}}}}
    got = A.client_actions("1615", _overview(product={"20100": [9, 9, ""], "30100": [4, 3, "Club"],
                                                       "40100": [2, 2, ""], "55555": [1, 1, ""]}), tables, {})
    by = {c["kind"]: c for c in got["codes"]}
    assert by["pb_flag"]["label"] == "Product codes with no Personal/Business flag"
    assert [v["value"] for v in by["pb_flag"]["values"]] == ["30100"]
    assert [v["value"] for v in by["product"]["values"]] == ["55555"], "an unlisted code is not also a flag gap"


def test_mail_flag_is_anything_but_yes_or_no_and_eligibility_items_list_before_reg_e():
    tables = {"status_codes": {"1615": {}}, "product_codes": {"1615": {"20111": {"is_business": "0"}}},
              "rege_codes": {"1615": {"Opt Out": {}}}}
    got = A.client_actions("1615", _overview(mail={"Yes": [9, 9, ""], "": [3, 1, ""], "U": [2, 2, ""]},
                                             reg_e={"Opt In POS": [2, 2, ""]}), tables, {})
    assert [c["kind"] for c in got["codes"]] == ["status", "mail", "reg_e"]
    mail = got["codes"][1]
    assert mail["label"] == "Mail Flags not mapped" and [v["value"] for v in mail["values"]] == ["", "U"]
    assert [c["eligibility"] for c in got["codes"]] == [True, False, False], "Mail Flag decides mailing, not eligibility"


def test_what_cannot_be_checked_is_said_never_read_as_all_mapped():
    assert A.client_actions("1615", {"missing": "no ODD extract in Inputs"}, TABLES, {})["unchecked"] \
        == ["codes: no ODD extract in Inputs"]
    assert A.client_actions("1615", _overview(), None, {})["unchecked"] \
        == ["codes: no ARS database code tables in Inputs/ARS Settings"]
    assert "the ODD extract has no such column" in A.client_actions("1615", _overview(reg_e=None), TABLES, {})["unchecked"][0]
    assert A.client_actions("1615", {"month": "Aug26"}, TABLES, {})["count"] == 0
