"""merge_review: the ILS prep slides go into the analysis deck as hidden context after the cover, and the matrix
slides go in visible at the start of each account type's risk analysis (Aaron, 2026-11-20). Synthetic decks only."""
import pathlib
import sys

from pptx import Presentation
from pptx.util import Inches, Pt

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build" / "ils_analysis"))
sys.path.insert(0, str(ROOT / "validation"))

import merge_review as M  # noqa: E402


def _deck(path, slides, numbered=True):
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    for i, (head, body) in enumerate(slides, 1):
        s = prs.slides.add_slide(prs.slide_layouts[6])
        s.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(10), Inches(0.8)).text_frame.text = head
        s.shapes.add_textbox(Inches(0.5), Inches(1.2), Inches(10), Inches(0.5)).text_frame.text = body
        if numbered:
            tb = s.shapes.add_textbox(Inches(0.45), Inches(7.0), Inches(0.5), Inches(0.3))
            tb.text_frame.text = str(i)
            tb.text_frame.paragraphs[0].runs[0].font.size = Pt(10)
    prs.save(path)
    return path


ILS = [("Georgia Example CU", "ILS Program Analysis"), ("Agenda", "ILS Program Analysis"),
       ("Program Performance", ""), ("Scoring summary — limit distribution and heat map", "Open personal accounts"),
       ("Scoring Summary: Days On Book", "Personal accounts"), ("Thank You", ""),
       ("Appendix and Matrix Validation", ""), ("Appendix: data notes and methodology", "")]
PREP = [("Previous Review Recap", "Example CU"), ("Program Detail", "Example CU"),
        ("Matrix Parameters", "Personal Accounts  •  Intelligent Limit System  •  Example CU"),
        ("Matrix Overrides", "Personal Accounts  •  Intelligent Limit System  •  Example CU"),
        ("Matrix Parameters", "Business Accounts  •  Intelligent Limit System  •  Example CU"),
        ("Matrix Overrides", "Business Accounts  •  Intelligent Limit System  •  Example CU")]


def _number(s):
    for sh in s.shapes:
        if sh.has_text_frame and sh.top > Inches(6.8) and sh.text_frame.text.strip().isdigit():
            return int(sh.text_frame.text)
    return None


def test_prep_slides_are_hidden_after_the_cover_and_matrix_slides_open_the_risk_analysis(tmp_path):
    ils = _deck(tmp_path / "ils.pptx", ILS)
    prep = _deck(tmp_path / "prep.pptx", PREP, numbered=False)
    out = tmp_path / "out.pptx"
    r = M.merge(str(ils), str(prep), str(out))
    prs = Presentation(str(out))
    rows = [(M.title(s), M.is_hidden(s), M.account_type(s)) for s in prs.slides]
    assert [t for t, *_ in rows] == [
        "Georgia Example CU", "Previous Review Recap", "Program Detail", "Agenda", "Program Performance",
        "Matrix Parameters", "Matrix Overrides", "Scoring summary — limit distribution and heat map",
        "Scoring Summary: Days On Book", "Thank You", "Appendix and Matrix Validation", "Matrix Parameters",
        "Matrix Overrides", "Appendix: data notes and methodology"]
    assert [h for _, h, _ in rows] == [False, True, True] + [False] * 11
    assert rows[5][2] == rows[6][2] == "Personal" and rows[11][2] == rows[12][2] == "Business"
    assert r["hidden"] == 2 and "before 'Scoring summary" in r["matrix"]["Personal"]
    assert "Appendix divider" in r["matrix"]["Business"]
    # a page number is the slide's place among the VISIBLE slides; the hidden ones keep no place in the count (the
    # matrix slides count but carry no number of their own, as the prep build designs them)
    visible = [s for s in prs.slides if not M.is_hidden(s)]
    pairs = [(k, _number(s)) for k, s in enumerate(visible, 1) if _number(s) is not None]
    assert pairs and all(k == n for k, n in pairs), pairs


def test_a_business_risk_section_takes_the_business_matrix_slides(tmp_path):
    ils_rows = ILS[:5] + [("Scoring Summary: Days On Book", "Business accounts")] + ILS[5:]
    ils = _deck(tmp_path / "ils.pptx", ils_rows)
    prep = _deck(tmp_path / "prep.pptx", PREP, numbered=False)
    out = tmp_path / "out.pptx"
    r = M.merge(str(ils), str(prep), str(out))
    titles = [(M.title(s), M.account_type(s)) for s in Presentation(str(out)).slides]
    i = titles.index(("Scoring Summary: Days On Book", "Business"))
    assert titles[i - 2:i] == [("Matrix Parameters", "Business"), ("Matrix Overrides", "Business")]
    assert "before 'Scoring Summary: Days On Book'" in r["matrix"]["Business"]


def test_the_merged_package_is_sound(tmp_path):
    import validate_deck
    ils = _deck(tmp_path / "ils.pptx", ILS)
    prep = _deck(tmp_path / "prep.pptx", PREP, numbered=False)
    out = tmp_path / "out.pptx"
    M.merge(str(ils), str(prep), str(out))
    assert not [f for f in validate_deck.package_findings(str(out)) if f[0] == "FAIL"]
