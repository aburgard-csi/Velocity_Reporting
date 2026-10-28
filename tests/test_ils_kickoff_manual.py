# Ported from v5 02-Scripts/tests/test_ils_kickoff_manual.py at 7ba1e63. Tests unchanged; edits: imports from ils_pipeline.kickoff, no sys.path insert, and the page/generator paths (neither is ported, so the module skips).
"""The CSM manual must describe the deck the code actually builds.

    python -m pytest tests/test_ils_kickoff_manual.py -q

00-Instructions/ils-kickoff.html is generated from the live slide manifest
by tools/build_ils_kickoff_manual.py. The failure this guards against is the
one the kickoff README had for months: it promised no PowerPoint output and
said the engine had never been run against a real extract, long after both
were false. A manual that describes the wrong product is worse than none.
"""
import pathlib
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[0]

# RPE: v5's manual page and its generator are not ported (the page is v5's CSM manual and the
# generator writes it into v5's 00-Instructions/). Until one is, these resolve to nothing in this
# checkout and the module skips, exactly as v5's does before its page is generated.
PAGE = REPO / "docs" / "ils" / "ils-kickoff.html"
GENERATOR = REPO / "scripts" / "build_ils_kickoff_manual.py"

pytestmark = pytest.mark.skipif(not PAGE.exists(),
                                reason="manual not generated yet")


def _page() -> str:
    return PAGE.read_text(encoding="utf-8")


def test_every_analysis_the_deck_builds_is_named_in_the_manual():
    from ils_pipeline.kickoff.deck import slides
    page = _page()
    for spec in slides.SLIDE_MANIFEST:
        assert spec.key in page, f"{spec.key} is on the deck but not in the manual"


def test_every_section_is_named():
    from ils_pipeline.kickoff.deck import slides
    page = _page()
    for section in slides.SECTIONS:
        assert section in page, f"section {section!r} missing from the manual"


def test_the_manual_names_every_question_the_run_asks():
    """A CSM who is not warned about the Reg E question guesses at it, which
    is exactly how a wrong number reached a client."""
    page = _page()
    for term in ("Personal account code", "Business account code",
                 "Open status code", "Stat Code", "Reg E opt-in"):
        assert term in page, f"the manual does not mention {term!r}"


def test_the_manual_says_the_reg_e_default_is_deliberately_empty():
    from ils_pipeline.kickoff.core.io import CodeConfig
    assert CodeConfig().rege_opt_in == [], \
        "the default changed; the manual says there is none"
    assert "no default" in _page()


def test_the_manual_is_not_hand_edited():
    """Regenerating must be a no-op. If this fails, someone edited the HTML
    instead of the generator and their change is one run away from being
    lost."""
    before = _page()
    subprocess.run([sys.executable, str(GENERATOR)], check=True,
                   capture_output=True)
    assert _page() == before, (
        "00-Instructions/ils-kickoff.html differs from what its generator "
        "produces. Edit tools/build_ils_kickoff_manual.py and re-run it.")


def test_the_manual_promises_the_files_the_run_actually_writes():
    page = _page()
    assert "ILS Kickoff Report Data" in page
    assert "ILS Kickoff {period}.pptx" in page or "ILS Kickoff" in page
    assert "03-Output" in page
