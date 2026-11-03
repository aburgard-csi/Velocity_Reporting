"""The Contact Us card names the client's MANAGING CSM, on every deck (Aaron, 2026-09-16).

"James's name would go on the contact card. The contact card should always show the
managing CSM." Every builder used to print Aaron Burgard's card, so a James Gilmore client
(1776 CoastHills CU) would have been told to call Aaron.

`rpe_env.csm_contact` is the one lookup: the client's CSM from Client CSM List.csv, their
card from CSM Contacts.csv. No CSM, or a CSM with no row, stops the build with a sentence —
the card never falls back to another CSM.

Every contact here is synthetic: invented names, 555 numbers, example.com addresses.
"""
import os
import re

import pytest

import rpe_env as R

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONTACTS = (
    "csm,title,company,address,office,cell,email,source\n"
    'Pat Cell,Client Service Manager,CSI,"1 Main St, Town, KY 00000",(555) 010-0001,(555) 010-0002,Pat.Cell@Example.com,test\n'
    'Kim Office,Senior Client Service Manager,CSI,"1 Main St",(555) 010-0003 ext. 42,,kim.office@example.com,test\n'
    "Lee Nophone,Client Service Manager,CSI,,,,LEE.NOPHONE@EXAMPLE.COM,test\n"
    "Row Noemail,Client Service Manager,CSI,,,(555) 010-0004,,test\n"
)
CSM_LIST = (
    "client_id,client_name,csm\n"
    "9001,Cell Bank,Pat Cell\n"
    "9002,Office Bank,Kim Office\n"
    "9003,No Phone Bank,Lee Nophone\n"
    "9004,Unlisted CSM Bank,Someone Unlisted\n"
    "9005,No Email Bank,Row Noemail\n"
)


@pytest.fixture
def root(tmp_path, monkeypatch):
    (tmp_path / R.CSM_LIST_NAME).write_text(CSM_LIST, encoding="utf-8")
    (tmp_path / R.CSM_CONTACTS_NAME).write_text(CONTACTS, encoding="utf-8")
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("RPE_CSM_LIST", raising=False)
    monkeypatch.delenv("RPE_CSM_CONTACTS", raising=False)
    return tmp_path


def test_the_ics_program_contact_is_read_by_name(root):
    """Standalone ICS decks add the ICS program contact beside the CSM (Aaron, 2026-09-16)."""
    with open(root / R.CSM_CONTACTS_NAME, "a", encoding="utf-8") as fh:
        fh.write(f"{R.ICS_PROGRAM_CONTACT},ICS Program Manager,CSI,,(555) 010-0009,,program@example.com,test\n")
    c = R.contact_by_name(R.ICS_PROGRAM_CONTACT)
    assert c["name"] == R.ICS_PROGRAM_CONTACT and c["phone"] == "555-010-0009"
    src = open(os.path.join(REPO, "build", "ics_pipeline", "build_ics_gen.py"), encoding="utf-8").read()
    assert "ICS_PROGRAM_CONTACT" in src and "_program_contact" in src


def test_cell_is_preferred_and_formatted(root):
    c = R.csm_contact("9001")
    assert c == {"name": "Pat Cell", "role": "Client Service Manager",
                 "phone": "555-010-0002", "email": "pat.cell@example.com"}


def test_office_with_extension_when_no_cell(root):
    c = R.csm_contact(9002)
    assert c["phone"] == "555-010-0003 ext. 42"
    assert c["role"] == "Senior Client Service Manager"


def test_no_phone_is_blank_not_a_dash(root):
    c = R.csm_contact("9003")
    assert c["phone"] == "" and c["email"] == "lee.nophone@example.com"


@pytest.mark.parametrize("raw, want", [
    ("(555) 010-0002", "555-010-0002"),
    ("555.010.0002", "555-010-0002"),
    ("1 (555) 010-0002", "555-010-0002"),
    ("(555) 010-0003 ext. 42", "555-010-0003 ext. 42"),
    ("(555) 010-0003 Ext 42", "555-010-0003 ext. 42"),
    ("", ""),
])
def test_phone_format(raw, want):
    assert R.format_phone(raw) == want


def test_unknown_client_raises(root):
    with pytest.raises(SystemExit, match="no managing CSM"):
        R.csm_contact("1234")


def test_csm_without_a_contact_row_raises(root):
    with pytest.raises(SystemExit, match="Someone Unlisted"):
        R.csm_contact("9004")


def test_csm_without_an_email_raises(root):
    with pytest.raises(SystemExit, match="email"):
        R.csm_contact("9005")


def test_missing_contacts_file_raises(root):
    (root / R.CSM_CONTACTS_NAME).unlink()
    with pytest.raises(SystemExit, match="CSM Contacts.csv"):
        R.csm_contact("9001")


def test_file_overrides_are_honoured(tmp_path, monkeypatch):
    """A subprocess build (the golden deck) points the lookup at synthetic files."""
    lst, con = tmp_path / "list.csv", tmp_path / "contacts.csv"
    lst.write_text(CSM_LIST, encoding="utf-8")
    con.write_text(CONTACTS, encoding="utf-8")
    monkeypatch.setenv("RPE_CSM_LIST", str(lst))
    monkeypatch.setenv("RPE_CSM_CONTACTS", str(con))
    assert R.csm_contact("9001")["name"] == "Pat Cell"


# ------------------------------------------------------------------ no hardcoded card
BUILDERS = ("build/ars_pipeline/build_ars_gen.py", "build/mrpc_pipeline/build_mrpc_gen.py",
            "build/ics_pipeline/build_ics_gen.py", "build/ics_pipeline/ics_workbook_extract.py",
            "build/ics_pipeline/ics_local_sheet.py", "build/cashplease_pipeline/build_cp_gen.py")


def test_no_builder_hardcodes_a_contact():
    """No file under build/ carries a person's contact details. The card is looked up."""
    hits = []
    for dirpath, _, files in os.walk(os.path.join(REPO, "build")):
        for f in files:
            if not f.endswith(".py"):
                continue
            p = os.path.join(dirpath, f)
            # Comments may name a person (history notes do); code and strings may not.
            text = "\n".join(ln for ln in open(p, encoding="utf-8").read().splitlines()
                             if not ln.lstrip().startswith("#"))
            for needle in ("Aaron Burgard", "aaron.burgard@csiweb.com", "@csiweb.com", "910-617-1984"):
                if needle.lower() in text.lower():
                    hits.append(f"{os.path.relpath(p, REPO)}: {needle}")
            if re.search(r"\b\d{3}-\d{3}-\d{4}\b", text):
                hits.append(f"{os.path.relpath(p, REPO)}: a phone number")
    assert not hits, hits


@pytest.mark.parametrize("path", BUILDERS[:3] + BUILDERS[-1:])
def test_every_builder_uses_the_lookup(path):
    text = open(os.path.join(REPO, path), encoding="utf-8").read()
    assert "csm_contact(" in text, f"{path} does not resolve the managing CSM's card"


# ------------------------------------------------------------------ CashPlease shell card
def test_cashplease_shell_card_is_replaced(root):
    """The CashPlease template's Contact slide carries a static card; the builder rewrites it
    with the managing CSM and drops the phone line when there is none."""
    import sys
    sys.path.insert(0, os.path.join(REPO, "build", "cashplease_pipeline"))
    import build_cp_gen as G
    from pptx import Presentation
    prs = Presentation(os.path.join(REPO, "templates", "cashplease_template.pptx"))
    slide = next(s for s in prs.slides if G._title_of(s).startswith("Contact Us"))
    template_text = " ".join(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame)

    G.fill_contact(slide, "9003")
    text = [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame]
    joined = " ".join(text)
    assert "Lee Nophone" in joined and "lee.nophone@example.com" in joined
    assert not re.search(r"\d{3}-\d{3}-\d{4}", joined), "the template's phone line survived"
    for word in template_text.split():
        if "@" in word:
            assert word not in joined, "the template's email survived"
    assert "CSM Contacts.csv" in slide.notes_slide.notes_text_frame.text

    prs = Presentation(os.path.join(REPO, "templates", "cashplease_template.pptx"))
    slide = next(s for s in prs.slides if G._title_of(s).startswith("Contact Us"))
    G.fill_contact(slide, "9001")
    joined = " ".join(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame)
    assert "Pat Cell" in joined and "555-010-0002" in joined and "pat.cell@example.com" in joined


@pytest.mark.parametrize("template", ["ars_template.pptx", "mrpc_template.pptx", "cashplease_template.pptx"])
@pytest.mark.parametrize("cid, has_phone", [("9001", True), ("9003", False)])
def test_shell_contact_slides_are_rewritten(root, template, cid, has_phone):
    """The ARS, MRPC and CashPlease shells each CARRY a Contact Us slide with one CSM's static
    card; ARS and MRPC skipped adding their own, so that static card shipped on every deck.
    The shared filler redraws the whole slide (`shapes.draw_contact_slide`: the Questions & Discussion
    gradient, the CSI logo, the contact centred) with the managing CSM's lines."""
    from pptx import Presentation
    import shapes
    prs = Presentation(os.path.join(REPO, "templates", template))
    slide = shapes.find_contact_slide(prs)
    assert slide is not None
    c = R.csm_contact(cid)
    shapes.fill_contact_slide(slide, c)
    lines = {sh.name: sh.text_frame.text for sh in slide.shapes
             if sh.name in ("Contact name", "Contact role", "Contact phone", "Contact email")}
    assert lines["Contact name"] == c["name"] and lines["Contact role"] == c["role"]
    assert lines["Contact email"] == c["email"]
    if has_phone:
        assert lines["Contact phone"] == c["phone"]
    else:                                           # no phone on file: no phone row, no blank, no dash
        assert "Contact phone" not in lines
        assert not any(re.search(r"\d{3}-\d{3}-\d{4}", t) for t in lines.values())
    assert not any("csiweb" in t.lower() for t in lines.values()), "the shell's static card survived"
    assert slide.notes_slide.notes_text_frame.text == shapes.contact_card_note(c)
