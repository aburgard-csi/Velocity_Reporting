"""promote_month — picking the deck, seeing a change, and moving files safely.

Every test here exists because of something that happened on 2026-09-11:

  * the combined-deck picker was three hardcoded pairs written before CashPlease,
    so an ICS-CP deck matched none of them;
  * `same()` compared text and images only, so recolouring the Summit banner read
    as "unchanged" and the rebuilt deck was silently not delivered;
  * a deck open in PowerPoint raised PermissionError, aborted the whole run at the
    first client, and left that client's PDF archived while its deck stayed live;
  * `main()` resolved its destination from `rpe_env.outputs()` and ignored what the
    caller asked for, so a test aimed at a temp folder wrote into the real one and
    delivered one client's deck under another client's filename.
"""
import hashlib
import os
import shutil
import sys

import pytest
from pptx import Presentation
from pptx.util import Inches

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "build"))
import promote_month as P  # noqa: E402


# --- which deck ships --------------------------------------------------------
@pytest.mark.parametrize("name,tags", [
    ("1632-2026.09-ICS-CP-WesBanco Results.pptx", ("ICS", "CP")),
    ("1539-2026.09-ARS-ICS-MRPC-CP-Marine FCU Results.pptx", ("ARS", "ICS", "MRPC", "CP")),
    ("1509-2026.09-ARS-ICS-Texas Bay Credit Union Results.pptx", ("ARS", "ICS")),
    ("1038-2026.09-ARS-Sugar River Bank ARS Results.pptx", ("ARS",)),
    ("1131-2026.09-CP-Peoples Bank of Alabama CashPlease Module.pptx", ("CP",)),
    ("not-a-deck.pptx", ()),
])
def test_program_tags_come_from_the_filename_convention(name, tags):
    """CashPlease made the old literal list ("ARS-ICS","ARS-MRPC","ICS-MRPC") wrong."""
    assert P.program_tags(name) == tags


def _deck(path, text="Union Financial", fill=None):
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    s = prs.slides.add_slide(prs.slide_layouts[6])
    tb = s.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(1))
    tb.text_frame.text = text
    if fill is not None:
        from pptx.enum.shapes import MSO_SHAPE
        from pptx.dml.color import RGBColor
        sh = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(2), Inches(3), Inches(3), Inches(1))
        sh.fill.solid()
        sh.fill.fore_color.rgb = RGBColor.from_string(fill)
    prs.save(str(path))
    return str(path)


def test_a_colour_change_is_not_unchanged(tmp_path):
    """The defect: the Summit banner went navy, every figure and image stayed
    identical, and same() said "unchanged" so the deck never shipped."""
    a = _deck(tmp_path / "a.pptx", fill="4472C4")
    b = _deck(tmp_path / "b.pptx", fill="00274C")
    assert P.same(a, a) is True
    assert P.same(a, b) is False


def test_identical_decks_are_still_unchanged(tmp_path):
    """The opposite error would re-archive every deck on every run, burying the
    copies that matter. Zip bytes differ per build and are deliberately not read."""
    a = _deck(tmp_path / "a.pptx", fill="00274C")
    b = _deck(tmp_path / "b.pptx", fill="00274C")
    assert P.same(a, b) is True


# --- moving files ------------------------------------------------------------
def _stage(tmp_path, cid, name, content):
    d = tmp_path / "stage" / cid
    d.mkdir(parents=True)
    shutil.copy2(content, d / name)
    return d / name


def _outputs(tmp_path):
    out = tmp_path / "Outputs"
    (out / "Archive").mkdir(parents=True)
    return out


def test_a_blocked_deck_leaves_outputs_exactly_as_it_found_it(tmp_path, monkeypatch):
    """All or nothing. It used to archive each match in turn, so a lock part way
    left the PDF in Archive/ and the superseded deck still live."""
    out = _outputs(tmp_path)
    name = "1038-2026.09-ARS-Sugar River Bank ARS Results.pptx"
    live = _deck(out / name, "Sugar River")
    pdf = out / (name[:-5] + ".pdf")
    pdf.write_bytes(b"%PDF hand-made before sending\n")
    src = _stage(tmp_path, "1038", name, _deck(tmp_path / "new.pptx", "Sugar River v2"))

    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in out.iterdir() if p.is_file()}

    real_move = shutil.move
    monkeypatch.setattr(shutil, "move", lambda s, d, *a, **k: (
        (_ for _ in ()).throw(PermissionError(32, "in use")) if str(s).endswith(".pptx")
        else real_move(s, d, *a, **k)))

    with pytest.raises(OSError):
        P.promote_one(str(src), out, out / "Archive", "2026-09-11", apply=True,
                      log=lambda *_: None)

    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
             for p in out.iterdir() if p.is_file()}
    assert before == after, "a failed promotion must not leave Outputs half-moved"
    assert list((out / "Archive").iterdir()) == [], "and must not orphan a copy in Archive"


def test_one_blocked_client_does_not_stop_the_others(tmp_path, monkeypatch):
    """A single deck open in PowerPoint aborted the run at the first client and
    nothing was delivered. It is reported, the run continues, the exit code carries it."""
    out = _outputs(tmp_path)
    n1 = "1038-2026.09-ARS-Sugar River Bank ARS Results.pptx"
    n2 = "1204-2026.09-ARS-First State Bank - Michigan ARS Results.pptx"
    _deck(out / n1, "Sugar River")
    _deck(out / n2, "First State")
    _stage(tmp_path, "1038", n1, _deck(tmp_path / "a.pptx", "Sugar River v2"))
    _stage(tmp_path, "1204", n2, _deck(tmp_path / "b.pptx", "First State v2"))

    real_move = shutil.move
    monkeypatch.setattr(shutil, "move", lambda s, d, *a, **k: (
        (_ for _ in ()).throw(PermissionError(32, "in use")) if "1038" in str(s)
        else real_move(s, d, *a, **k)))

    rc = P.main([str(tmp_path / "stage"), "--apply", "--outputs", str(out)])
    assert rc == 1, "a blocked client must be carried in the exit code"
    assert "Sugar River" in Presentation(str(out / n1)).slides[0].shapes[0].text_frame.text
    assert "First State v2" in Presentation(str(out / n2)).slides[0].shapes[0].text_frame.text


def test_main_writes_where_it_is_told(tmp_path):
    """main() used to resolve Outputs from rpe_env and ignore the caller, so a test
    pointed at a temp folder wrote into the LIVE one and delivered one client's deck
    under another client's filename (2026-09-11). The destination is a parameter."""
    import rpe_env as R
    real = R.outputs()
    before = sorted(p.name for p in real.iterdir() if p.is_file())

    out = _outputs(tmp_path)
    name = "1038-2026.09-ARS-Sugar River Bank ARS Results.pptx"
    _deck(out / name, "old")
    _stage(tmp_path, "1038", name, _deck(tmp_path / "new.pptx", "new"))

    P.main([str(tmp_path / "stage"), "--apply", "--outputs", str(out)])

    assert "new" in Presentation(str(out / name)).slides[0].shapes[0].text_frame.text
    assert sorted(p.name for p in real.iterdir() if p.is_file()) == before, \
        "the real Outputs folder must not be touched when --outputs is given"
