"""The first four-program combined deck (1539 Marine FCU, ARS-ICS-MRPC-CP, 2026-09-14)
failed the gate on two things no earlier combined deck could reach:

  * its cover listed four products in a box that seats three, and the lines drew over
    the client name beneath them;
  * its CashPlease source notes named "Marine Federal Credit Union" - the same client the
    cover calls "Marine FCU" - and the leak checks read that as another client's
    provenance, because both names are on the reference list as if they were two clients.
"""
import os
import sys

from pptx import Presentation
from pptx.util import Emu, Inches, Pt

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "build"))
sys.path.insert(0, os.path.join(REPO, "validation"))
import assemble_combined as AC  # noqa: E402
import validate_deck as vd  # noqa: E402


# --- the cover's product lines ------------------------------------------------
def _cover():
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    s = prs.slides.add_slide(prs.slide_layouts[6])
    box = s.shapes.add_textbox(Inches(0.8), Inches(2.7), Inches(11.7), Inches(2.0))
    run = box.text_frame.paragraphs[0].add_run()
    run.text = "Account Revenue Solution®"
    run.font.size = Pt(40)
    return s, box


def _sizes(box):
    return {r.font.size.pt for p in box.text_frame.paragraphs for r in p.runs if r.font.size}


def test_four_products_fit_the_cover_box():
    s, box = _cover()
    assert AC.set_title_products(s, ["ARS", "ICS", "CP", "MRPC"])
    assert len(box.text_frame.paragraphs) == 4
    (size,) = _sizes(box)
    assert size < 40, "four lines at the template's 40pt overflow the 2.0\" box"
    assert 4 * size * 1.2 <= Emu(box.height).pt, "the shrunk lines must fit the box"


def test_two_and_three_products_keep_the_template_size():
    """No existing combined deck may change: they all seat three lines or fewer."""
    for programs in (["ICS", "CP"], ["ARS", "ICS", "MRPC"]):
        s, box = _cover()
        assert AC.set_title_products(s, programs)
        assert _sizes(box) == {40.0}, programs


# --- one client, two names ----------------------------------------------------
def _deck(tmp_path, filename, cover_text, note):
    prs = Presentation()
    s0 = prs.slides.add_slide(prs.slide_layouts[6])
    s0.shapes.add_textbox(Inches(1), Inches(3), Inches(8), Inches(1)).text_frame.text = cover_text
    s1 = prs.slides.add_slide(prs.slide_layouts[6])
    s1.shapes.add_textbox(Inches(1), Inches(3), Inches(8), Inches(1)).text_frame.text = "Loans PTD 6,745"
    s1.notes_slide.notes_text_frame.text = note
    path = str(tmp_path / filename)
    prs.save(path)
    return path, Presentation(path)


def _names_flagged(findings):
    return [f for f in findings if "different client" in f[2]]


def test_a_clients_other_name_is_still_its_own(tmp_path):
    path, prs = _deck(tmp_path, "1539-2026.09-ARS-ICS-MRPC-CP-Marine FCU Results.pptx",
                      "Marine FCU\nExecutive Review",
                      "Source — CashPlease Summary weekly, Marine Federal Credit Union tab.")
    assert _names_flagged(vd.source_note_findings(path, prs)) == []


def test_the_alias_works_in_both_directions(tmp_path):
    path, prs = _deck(tmp_path, "1539-2026.09-CP-Marine Federal Credit Union CashPlease Module.pptx",
                      "Marine Federal Credit Union\nCashPlease",
                      "Source — Marine FCU ARS workbook.")
    assert _names_flagged(vd.source_note_findings(path, prs)) == []


def test_a_genuinely_different_client_still_fails(tmp_path):
    """The alias must not become a hole: True Sky's deck naming Marine is still a leak."""
    path, prs = _deck(tmp_path, "1676-2026.09-ARS-ICS-True Sky CU Results.pptx",
                      "True Sky CU\nExecutive Review",
                      "Source — CashPlease Summary weekly, Marine Federal Credit Union tab.")
    assert _names_flagged(vd.source_note_findings(path, prs)), \
        "a note naming another client must still FAIL"
