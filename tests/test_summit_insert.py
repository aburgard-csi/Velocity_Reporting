"""insert_summit_after_title — one Summit slide, cloned from one asset.

Until 2026-09-11 there were two renderings of this slide: ICS and MRPC decks got a
flat JPG of it, ARS and CashPlease carried the real one baked into their template
shells. Replacing the Summit meant editing three templates AND re-exporting an
image, which needs PowerPoint or LibreOffice — so it could not be done from the
pipeline, and every 2026.09 deck went out advertising a Summit that had already
happened. Every program now clones `build/assets/summit_slide.pptx`, which is also
the file `summit_date()` reads.
"""
import collections
import os
import sys
import warnings
import zipfile

import pytest
from pptx import Presentation
from pptx.util import Inches

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build"))
import summit_slide as S  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _deck(n_slides=4):
    """A minimal deck with a title slide and some content."""
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]
    for _ in range(n_slides):
        prs.slides.add_slide(blank)
    return prs


def test_the_asset_is_committed():
    """Present on disk AND tracked by git.

    "Is the file there" is not the check that was needed. `.gitignore` carries a
    blanket `*.pptx` with exceptions only for the template folders, so the asset
    could never be committed — which is why it was absent for the whole life of
    the repo, `summit_date()` returned None, and the reporting-month fallback was
    dead. A checkout on another machine would have had the file missing again
    while this test passed locally (2026-09-11).
    """
    import subprocess
    rel = "build/assets/summit_slide.pptx"
    assert os.path.isfile(os.path.join(REPO, rel)), "%s is missing" % rel
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", rel],
                             cwd=REPO, capture_output=True, text=True)
    assert tracked.returncode == 0, (
        "%s is not tracked by git — check .gitignore's *.pptx exceptions" % rel)


def test_insert_puts_the_summit_at_index_one():
    prs = _deck()
    assert S.insert_summit_after_title(prs) is True
    txt = " ".join(sh.text_frame.text for sh in prs.slides[1].shapes if sh.has_text_frame)
    assert "Executive Summit" in txt


def test_insert_does_not_change_the_slide_count_when_one_is_already_there():
    """Content is replaced in place. Slides are ADDED and reordered, never deleted:
    freeing a partname makes python-pptx hand that number to a later slide and the
    package references parts twice (the unopenable 2026.08 ICS decks)."""
    prs = _deck()
    S.insert_summit_after_title(prs)
    n = len(prs.slides._sldIdLst)
    S.insert_summit_after_title(prs)
    assert len(prs.slides._sldIdLst) == n


def test_saving_writes_no_duplicate_zip_entries(tmp_path):
    """The defect this test exists for: relating the ASSET's image Part into another
    deck carries its partname with it, so /ppt/media/imageN.png is written twice and
    the package is malformed while every text and geometry rule still passes. Images
    are re-added from their bytes instead, which assigns a free partname.
    """
    prs = _deck()
    S.insert_summit_after_title(prs)
    S.insert_summit_after_title(prs)
    out = tmp_path / "deck.pptx"
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)   # zipfile's "Duplicate name:" warning
        prs.save(str(out))
    names = [i.filename for i in zipfile.ZipFile(str(out)).infolist()]
    dupes = [n for n, c in collections.Counter(names).items() if c > 1]
    assert not dupes, "duplicate parts in the package: %s" % dupes


def test_every_picture_resolves_to_a_relationship(tmp_path):
    """A cloned <p:pic> keeps the SOURCE deck's r:embed. Left unremapped it points at
    a different part or none, and the slide opens with a red X where the logo was."""
    prs = _deck()
    S.insert_summit_after_title(prs)
    out = tmp_path / "deck.pptx"
    prs.save(str(out))
    slide = Presentation(str(out)).slides[1]
    key = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
    seen = 0
    for sh in slide.shapes:
        for node in sh._element.iter():      # .iter(): the photos sit inside a <p:grpSp>
            rid = node.get(key)
            if rid:
                seen += 1
                assert rid in slide.part.rels, "dangling image relationship %s" % rid
    assert seen, "the Summit slide should carry pictures"


@pytest.mark.parametrize("path", [
    "build/ars_pipeline/build_ars_gen.py",
    "build/ics_pipeline/build_ics_gen.py",
    "build/mrpc_pipeline/build_mrpc_gen.py",
    "build/cashplease_pipeline/build_cp_gen.py",
])
def test_every_builder_takes_the_summit_from_the_asset(path):
    """ARS and CashPlease used to take it from their own template shells, which is
    how their decks kept the old Summit while ICS and MRPC got a new one."""
    src = open(os.path.join(REPO, path), encoding="utf-8").read()
    assert "insert_summit_after_title(" in src, \
        "%s does not insert the shared Summit slide" % path


def test_the_summit_slide_carries_a_source_note():
    """CLAUDE.md: no slide ships without a source line in its notes.

    While this slide was a flat picture it carried no TEXT, so the validator's
    data-slide rule never reached it. The moment it became the real slide, all six
    ICS-only and MRPC-only decks failed on a missing note (2026-09-11) — the rule
    had always applied, the old shape just hid it.
    """
    prs = _deck()
    S.insert_summit_after_title(prs)
    slide = prs.slides[1]
    assert slide.has_notes_slide
    note = slide.notes_slide.notes_text_frame.text
    assert "summit_slide.pptx" in note, note
    assert note.lower().startswith("source"), note


def test_the_note_names_the_summit_on_the_slide():
    """Derived from the slide's own date line, not written as a constant — a note
    naming last Summit's city is the stale caption this pipeline keeps re-learning."""
    prs = _deck()
    S.insert_summit_after_title(prs)
    note = prs.slides[1].notes_slide.notes_text_frame.text
    shown = [" ".join(sh.text_frame.text.split()) for sh in prs.slides[1].shapes
             if sh.has_text_frame and S._SUMMIT_DATE_RE.search(" ".join(sh.text_frame.text.split()))]
    assert shown, "the Summit slide should print a date"
    assert shown[0] in note, "note %r does not name %r" % (note, shown[0])
