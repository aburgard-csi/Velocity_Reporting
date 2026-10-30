"""The Key Performance Metrics page builder in .claude/skills/summit-one-pager (Aaron, 2026-10-30).

A synthetic client only: no logo, no data root, no real figures. It pins what Aaron asked for on the Fort Lauderdale pages: a border on
the logo badge, a note on every page that names its sources, the contact line from the spec (never another CSM's card), and section
spacing that does not depend on how many bullets a section has.
"""
import importlib.util
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(REPO, ".claude", "skills", "summit-one-pager")


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SKILL, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


NOTES = ("Client 9999 Test Bank. Verified 2026-10-30. ICS: VIP 9999_ics.json pulled 2026-10-27, referrals Jan-Sep 2026 vs Jan-Sep 2025 "
         "(complete months only). ILS: review dated 2026-01-01, slide 1. Positive results only.")


def spec(**kw):
    s = {"id": "9999", "name": "Test Bank", "contact": "For more information, contact your Client Service Manager, Test CSM, t@example.com",
         "measure": True, "accurate": True,
         "band": {"title": "ROI & Year-over-Year Growth", "chip": "Jan–Sep 2026 vs Jan–Sep 2025",
                  "tiles": [["1.0 : 1", "a"], ["2", "b"], ["3", "c"], ["4", "d"]]},
         "sections": [
             {"title": "Alpha|®| (AL)", "chip": "since 2020", "bullets": ["One short line.", "A second line that is long enough to wrap onto a second line of the page "
                                                                          "because it keeps going well past the width of the text box.", "Third."]},
             {"title": "Beta|®| (BE)", "chip": "since 2021", "bullets": ["Only one."]},
             {"title": "Gamma|®| (GA)", "chip": "since 2022", "bullets": ["Two.", "Lines."]}],
         "notes": NOTES}
    s.update(kw)
    return s


def build(tmp_path, **kw):
    from pptx import Presentation
    page = load("kpm_page")
    out = str(tmp_path / "t.pptx")
    page.build(spec(**kw), out)
    return Presentation(out)


def test_the_page_is_one_slide_with_the_sources_in_its_notes(tmp_path):
    prs = build(tmp_path)
    assert len(prs.slides) == 1
    assert "Verified 2026-10-30" in prs.slides[0].notes_slide.notes_text_frame.text


def test_a_page_with_no_sources_in_its_notes_is_refused(tmp_path):
    page = load("kpm_page")
    with pytest.raises(SystemExit):
        page.build(spec(notes="Positive results only."), str(tmp_path / "t.pptx"))


def test_the_logo_badge_has_a_border(tmp_path):
    s = build(tmp_path).slides[0]
    badge = [sh for sh in s.shapes if sh.shape_type == 1 and sh.width > 1900000 and sh.top < 700000][0]
    assert badge.line.width > 0 and str(badge.line.color.rgb) == "00274C"


def test_the_contact_line_is_the_specs_not_a_hardcoded_csm(tmp_path):
    texts = [sh.text_frame.text for sh in build(tmp_path).slides[0].shapes if sh.has_text_frame]
    assert any("Test CSM, t@example.com" in t for t in texts)
    assert not any("Aaron Burgard" in t for t in texts)


def test_gaps_between_sections_are_equal_whatever_the_bullet_count(tmp_path):
    s = build(tmp_path).slides[0]
    heads = sorted(sh.top for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.startswith(("Alpha", "Beta", "Gamma")))
    bodies = sorted((sh.top, sh.top + sh.height) for sh in s.shapes
                    if sh.has_text_frame and sh.text_frame.text.startswith(("One short", "Only one", "Two.")))
    gaps = [heads[i + 1] - bodies[i][1] for i in range(len(heads) - 1)]
    assert max(gaps) - min(gaps) < 20000, gaps    # EMU: within about 0.02 in


def test_the_yoy_chart_is_drawn_to_the_slot_size(tmp_path):
    charts = load("kpm_charts")
    out = tmp_path / "c.png"
    charts.yoy(str(out), "Year-over-year change", [["A (Jan–Sep)", 12.0], ["B (Jan–Sep)", 5.5]])
    from PIL import Image
    assert Image.open(out).size == (int(charts.W * 300), int(charts.H * 300))


def test_a_section_can_carry_its_own_chart_beside_its_bullets(tmp_path):
    from PIL import Image
    png = tmp_path / "c.png"
    Image.new("RGB", (1089, 465), "white").save(png)
    s = spec()
    s["sections"][1]["chart"] = str(png)
    s["sections"][1]["chart_w"] = 3.0
    from pptx import Presentation
    page = load("kpm_page")
    out = str(tmp_path / "t.pptx")
    page.build(s, out)
    shapes = list(Presentation(out).slides[0].shapes)
    pics = [sh for sh in shapes if sh.shape_type == 13 and sh.width == int(3.0 * 914400)]
    assert len(pics) == 1 and pics[0].left + pics[0].width == int((0.5 + 7.5) * 914400)   # flush with the right edge of the page body
    body = [sh for sh in shapes if sh.has_text_frame and sh.text_frame.text.startswith("Only one")][0]
    assert body.width < int(7.5 * 914400) - pics[0].width    # the bullets narrowed to make room
