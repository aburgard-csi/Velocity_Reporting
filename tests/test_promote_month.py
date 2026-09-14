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


# --- the archive: a folder per client, newest per period and kind -----------------
# Aaron, 2026-09-14: "in the archive, only keep the last deck created for each individual
# period per client, and organize them into folders per client." Older decks are MOVED to
# a review folder, never deleted — the share has no Recycle Bin — and PDFs never move.
@pytest.mark.parametrize("name,expect", [
    ("1038-2026.09-ARS-Sugar River Bank ARS Results (superseded 2026-09-11-2).pptx",
     ("1038", "2026.09", ("ARS",), "Sugar River Bank", "pptx")),
    ("1509-2026.09-ARS-ICS-Texas Bay Credit Union Results.pptx",
     ("1509", "2026.09", ("ARS", "ICS"), "Texas Bay Credit Union", "pptx")),
    ("1539-2026.09-CP-Marine Federal Credit Union CashPlease Module (superseded 2026-09-14).pdf",
     ("1539", "2026.09", ("CP",), "Marine Federal Credit Union", "pdf")),
])
def test_archive_names_are_parsed(name, expect):
    i = P.parse_deck_name(name)
    assert (i["client_id"], i["period"], i["tags"], i["client"], i["ext"]) == expect
    assert P.parse_deck_name("notes.txt") is None


def test_a_superseded_deck_is_archived_in_its_clients_folder(tmp_path):
    out = _outputs(tmp_path)
    name = "1038-2026.09-ARS-Sugar River Bank ARS Results.pptx"
    _deck(out / name, "old")
    src = _stage(tmp_path, "1038", name, _deck(tmp_path / "new.pptx", "new"))
    n, _ = P.promote_one(str(src), out, out / "Archive", "2026-09-14", apply=True, log=lambda *_: None)
    assert n == 1
    folder = out / "Archive" / "1038 Sugar River Bank"
    assert [p.name for p in folder.iterdir()] == [
        "1038-2026.09-ARS-Sugar River Bank ARS Results (superseded 2026-09-14).pptx"]
    assert not any(p.is_file() for p in (out / "Archive").iterdir()), "nothing flat in Archive/"


def test_an_existing_client_folder_is_reused_whatever_its_name(tmp_path):
    """Delivery names differ by program ("Marine FCU" vs "Marine Federal Credit Union");
    the id is the key, so one client never splits across two folders."""
    out = _outputs(tmp_path)
    (out / "Archive" / "1539 Marine FCU").mkdir()
    name = "1539-2026.09-CP-Marine Federal Credit Union CashPlease Module.pptx"
    _deck(out / name, "old")
    src = _stage(tmp_path, "1539", name, _deck(tmp_path / "new.pptx", "new"))
    P.promote_one(str(src), out, out / "Archive", "2026-09-14", apply=True, log=lambda *_: None)
    assert sorted(d.name for d in (out / "Archive").iterdir()) == ["1539 Marine FCU"]
    assert len(list((out / "Archive" / "1539 Marine FCU").iterdir())) == 1


def test_only_the_newest_deck_per_period_and_kind_is_kept(tmp_path):
    folder = tmp_path / "Archive" / "1204 First State Bank"
    folder.mkdir(parents=True)
    review = tmp_path / "Archive" / P.REVIEW_DIRNAME
    base = "1204-2026.09-ARS-First State Bank - Michigan ARS Results"
    files = {
        base + " (superseded 2026-09-09).pptx": 100,
        base + " (superseded 2026-09-10).pptx": 200,
        base + " (superseded 2026-09-11).pptx": 300,      # newest of Sept ARS: kept
        base + " (superseded 2026-09-10).pdf": 150,       # a PDF: never moved
        "1204-2026.08-ARS-First State Bank - Michigan ARS Results (superseded 2026-09-04).pptx": 50,
        "1204-2026.09-CP-First State CashPlease Module (superseded 2026-09-10).pptx": 120,  # other kind
    }
    for nm, t in files.items():
        (folder / nm).write_bytes(b"x")
        os.utime(folder / nm, (t, t))
    moves = P.tidy_client_archive(folder, review, apply=True, log=lambda *_: None)
    assert sorted(s.name for s, _ in moves) == sorted([base + " (superseded 2026-09-09).pptx",
                                                      base + " (superseded 2026-09-10).pptx"])
    assert sorted(p.name for p in folder.iterdir()) == sorted([
        base + " (superseded 2026-09-11).pptx", base + " (superseded 2026-09-10).pdf",
        "1204-2026.08-ARS-First State Bank - Michigan ARS Results (superseded 2026-09-04).pptx",
        "1204-2026.09-CP-First State CashPlease Module (superseded 2026-09-10).pptx"])
    assert sorted(p.name for p in (review / folder.name).iterdir()) == sorted(s.name for s, _ in moves)


def test_promotion_tidies_older_decks_of_the_same_period_after_delivering(tmp_path):
    out = _outputs(tmp_path)
    name = "1038-2026.09-ARS-Sugar River Bank ARS Results.pptx"
    folder = out / "Archive" / "1038 Sugar River Bank"
    folder.mkdir()
    old = folder / "1038-2026.09-ARS-Sugar River Bank ARS Results (superseded 2026-09-10).pptx"
    _deck(old, "oldest")
    os.utime(old, (1000, 1000))
    _deck(out / name, "live")
    src = _stage(tmp_path, "1038", name, _deck(tmp_path / "new.pptx", "new"))
    P.promote_one(str(src), out, out / "Archive", "2026-09-14", apply=True, log=lambda *_: None)
    assert [p.name for p in folder.iterdir()] == [
        "1038-2026.09-ARS-Sugar River Bank ARS Results (superseded 2026-09-14).pptx"]
    assert (out / "Archive" / P.REVIEW_DIRNAME / "1038 Sugar River Bank" / old.name).exists()
    assert "new" in Presentation(str(out / name)).slides[0].shapes[0].text_frame.text
