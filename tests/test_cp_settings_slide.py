"""CashPlease Program Settings slide (Aaron, 2026-09-14).

The settings record comes from the Velocity Product Settings Power BI app and carries
internal fields next to client-facing ones. Speaker notes ship inside the .pptx, so the
defect worth pinning is an internal field reaching the slide OR its notes. Synthetic
record throughout — Union Financial, id 999, invented values.
"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "build"))
sys.path.insert(0, str(REPO / "build" / "cashplease_pipeline"))
sys.path.insert(0, str(REPO / "scripts"))

import build_cp_gen as G
import rpe_env as R

INTERNAL = {
    "Loan Notes": "INTERNAL-LOAN-NOTE declined best practices",
    "Contract Type": "INTERNAL-CONTRACT",
    "CSM": "INTERNAL-CSM",
    "Core Product": "INTERNAL-CORE",
    "Applicable Agency": "INTERNAL-AGENCY",
    "Interface Pricing from Client": "INTERNAL-PRICING",
}


def record(**over):
    r = {
        "Customer #": "999", "Record Type": "CashPlease",
        "_source": "Velocity Product Settings Power BI app, CashPlease page, "
                   "data updated 9/14/26 11:35 AM CST",
        "URL": "https://www.unionfinancialcash.example", "Soft Launch": "10/25/2023",
        "Full Launch": "12/12/2023", "Loan Processing Time": "Near Real-Time",
        "Online Banking Vendor": "FIS - CeB",
        "CP - Loan Calculation": "40% of calculated limit (or min/max)",
        "Loan Minimum": "$150", "Loan Maximum": "$1,000",
        "Loan Payment Structure": "3 payments / 3 months",
        "Interest (Easy, Std)": "17", "Interest (Manual, Std)": "17",
        "Interest (Easy, MLA)": "17", "Interest (Manual, MLA)": "17",
        "Prepaid Finance (Easy, Std)": "3%", "Prepaid Finance (Manual, Std)": "3%",
        "Prepaid Finance (Easy, MLA)": "3%", "Prepaid Finance (Manual, MLA)": "3%",
        "Application Fee (Std)": "N/A", "Application Fee (MLA)": "N/A",
        "Year Base for Loan": "365/365",
        "Allowed to Originate": "ALL account holders on eligible account",
        "Minimum Age for Loan": "18", "Loan Waiting Period for New Accounts": "90 Days",
        "Limit User's 1st Loan to Min": "False", "Loan Cool Off Period": "3 Days",
        "Volume Cap": "Standard - No more than 3 loans in rolling 6-month period",
        "Email Reminders (Days in Advance)": "10",
        "End of Month Payments": "Same Day Every Month",
    }
    r.update(INTERNAL)
    r.update(over)
    return r


def load(tmp_path, **over):
    p = tmp_path / "999_cp_settings.json"
    p.write_text(json.dumps(record(**over)), encoding="utf-8")
    return G.load_settings(p, "999")


def rows(S):
    terms, controls, program = G.settings_rows(S)
    return dict(terms[1:]), dict(controls[1:]), program


def test_agreeing_loan_types_collapse_to_one_value(tmp_path):
    terms, controls, _ = rows(load(tmp_path))
    assert terms["Interest rate"] == "17% (standard & MLA)"
    assert terms["Prepaid finance charge"] == "3% (standard & MLA)"
    assert terms["Application fee"] == "None"
    assert controls["First loan limited to minimum"] == "No"
    assert controls["New-account waiting period"] == "90 days"
    assert controls["Eligible borrowers"] == "All account holders on eligible account"
    assert controls["Volume cap"] == "No more than 3 loans in rolling 6-month period"


def test_differing_standard_and_mla_are_both_shown(tmp_path):
    S = load(tmp_path, **{"Interest (Easy, MLA)": "18", "Interest (Manual, MLA)": "18"})
    assert rows(S)[0]["Interest rate"] == "17% standard · 18% MLA"


PREPAID = ("Prepaid Finance (Easy, Std)", "Prepaid Finance (Manual, Std)",
           "Prepaid Finance (Easy, MLA)", "Prepaid Finance (Manual, MLA)")


@pytest.mark.parametrize("std,mla,shown", [
    # The 2026.09 modules shipped "N/A%", "6% / $25 max%" and "$20% standard · $0% MLA"
    # (Aaron, 2026-09-17): the sign goes on a bare number only.
    ("N/A", "N/A", "None"),
    ("6% / $25 max", "6% / $25 max", "6% / $25 max (standard & MLA)"),
    ("$20", "$0", "$20 standard · None MLA"),
    ("4", "4", "4% (standard & MLA)"),
])
def test_a_prepaid_charge_gets_a_percent_sign_only_when_it_is_a_bare_number(
        tmp_path, std, mla, shown):
    over = dict(zip(PREPAID, (std, std, mla, mla)))
    assert rows(load(tmp_path, **over))[0]["Prepaid finance charge"] == shown


def test_four_differing_loan_types_keep_their_names_capitalised(tmp_path):
    S = load(tmp_path, **{"Interest (Easy, Std)": "22", "Interest (Manual, Std)": "23",
                          "Interest (Easy, MLA)": "22", "Interest (Manual, MLA)": "24"})
    assert rows(S)[0]["Interest rate"] == \
        "22% Easy Std · 23% Manual Std · 22% Easy MLA · 24% Manual MLA"


def test_the_content_slide_pill_holds_a_september_date(tmp_path):
    from pptx import Presentation
    sys.path.insert(0, str(REPO / "validation"))
    import validate_deck
    prs = Presentation(str(REPO / "templates" / "cashplease_template.pptx"))
    G.head(G.new_slide(prs), "CashPlease Peer Comparison", "Union Financial",
           "PTD · September 13, 2026")
    assert not [f for f in validate_deck.pill_wrap_findings(prs)
                if f[1] == len(prs.slides) and "date pill" in f[2]]


def test_a_blank_field_is_stated_not_left_empty(tmp_path):
    S = load(tmp_path, **{"Loan Maximum": "", "Limit User's 1st Loan to Min": ""})
    terms, controls, _ = rows(S)
    assert terms["Maximum loan"] == G.NOT_RECORDED
    assert controls["First loan limited to minimum"] == G.NOT_RECORDED


def test_program_line_dates_and_url(tmp_path):
    _, _, program = rows(load(tmp_path))
    assert program[0] == "www.unionfinancialcash.example"
    assert "Soft launch Oct 25, 2023" in program
    assert G.settings_as_of(load(tmp_path)).strftime("%Y-%m-%d") == "2026-09-14"


@pytest.mark.parametrize("over,msg", [
    ({"Customer #": "1632"}, "another client's"),
    ({"Record Type": "ILS"}, "Record Type"),
    ({"_source": ""}, "_source"),
])
def test_a_record_that_is_not_this_clients_cashplease_is_refused(tmp_path, over, msg):
    with pytest.raises(SystemExit, match=msg):
        load(tmp_path, **over)


def test_internal_fields_reach_neither_the_slide_nor_its_notes(tmp_path):
    from pptx import Presentation
    prs = Presentation(str(REPO / "templates" / "cashplease_template.pptx"))
    d = {"client_id": "999", "client_name": "Union Financial"}
    s = G.slide_settings(prs, d, load(tmp_path), "999_cp_settings.json")
    text = [s.notes_slide.notes_text_frame.text]
    for sh in s.shapes:
        if sh.has_table:
            text += [c.text for row in sh.table.rows for c in row.cells]
        elif sh.has_text_frame:
            text.append(sh.text_frame.text)
    blob = "\n".join(text)
    for value in INTERNAL.values():
        assert value not in blob
    assert "INTERNAL" not in blob
    assert s.notes_slide.notes_text_frame.text.startswith("Source: Velocity Product Settings")
    assert "999 Union Financial" in s.notes_slide.notes_text_frame.text


# Every case below was rendered through PowerPoint on 2026-09-14; the ratio is textfit's
# width over the usable width. PowerPoint wraps between 0.940 and 0.974.
@pytest.mark.parametrize("text,wraps", [
    ("As of September 14, 2026", True),     # 0.993 — the first build of this slide
    ("PTD · September 13, 2026", True),     # 1.003
    ("PTD · December 31, 2026", True),      # 0.974 — the narrowest that wrapped
    ("As of September 1, 2026", False),     # 0.940 — the widest that held
    ("PTD · February 28, 2026", False),     # 0.935
    ("As of Sep 14, 2026", False),          # 0.693
])
def test_a_wrapping_date_pill_is_reported(text, wraps):
    from pptx import Presentation
    from shapes import pill
    sys.path.insert(0, str(REPO / "validation"))
    import validate_deck
    prs = Presentation(str(REPO / "templates" / "cashplease_template.pptx"))
    s = G.new_slide(prs)
    pill(s, text)
    got = [f for f in validate_deck.pill_wrap_findings(prs)
           if f[1] == len(prs.slides) and "date pill" in f[2]]
    assert bool(got) is wraps
    assert all(f[0] == "REVIEW" for f in got)


def test_the_resolver_reads_the_product_settings_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "inputs", lambda: tmp_path)
    assert R.cp_settings_file("999") is None
    d = tmp_path / R.INPUT_KIND_DIRS["CP settings"]
    d.mkdir()
    (d / "999_cp_settings.json").write_text("{}", encoding="utf-8")
    assert R.cp_settings_file("999") == d / "999_cp_settings.json"


def test_settings_are_not_scanned_as_workbook_inputs(tmp_path):
    import watch_sources
    for name in R.INPUT_KIND_DIRS.values():
        (tmp_path / name).mkdir()
    scanned = {Path(p).name for p in watch_sources._report_dirs(str(tmp_path))}
    assert "Product Settings" not in scanned and "ODDD" not in scanned
    assert "Weekly Summaries" in scanned
