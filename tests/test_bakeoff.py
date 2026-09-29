"""The slide bake-off pairs each of Aaron's slides with at most one v5 slide (2026-09-29).

Explicit pairs (scripts/bakeoff/pairs.json, start-of-title, case-insensitive) win; identical
titles pair next; everything else is listed unpaired so nothing is silently dropped.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts" / "bakeoff"))
import bakeoff_page as B  # noqa: E402

PAIRS = [("Transaction Increase Over the Ask", "Lift by response segment", "Lift matrix"),
         ("ARS Response —", "The most recent mailer", "Most recent mailer")]


def test_explicit_pairs_match_on_the_start_of_the_title_case_insensitively():
    aaron = [(1, "Agenda"), (2, "TRANSACTION INCREASE OVER THE ASK"), (3, "ARS Response — Apr 2026 Mailer")]
    james = [(1, "Lift by response segment"), (2, "The most recent mailer"), (3, "Tax refunds")]
    rows, left, right = B.pair_slides(aaron, james, PAIRS)
    assert [(t, a[0], j[0]) for t, a, j in rows] == [("Lift matrix", 2, 1), ("Most recent mailer", 3, 2)]
    assert left == [(1, "Agenda")] and right == [(3, "Tax refunds")]


def test_identical_titles_pair_after_the_explicit_list_and_each_slide_is_used_once():
    aaron = [(1, "Where the money goes"), (2, "Where the money goes")]
    james = [(1, "where the money goes")]
    rows, left, right = B.pair_slides(aaron, james, [])
    assert [(a[0], j[0]) for _, a, j in rows] == [(1, 1)]
    assert left == [(2, "Where the money goes")] and right == []


def test_the_shipped_pairs_file_is_well_formed_and_names_aarons_template_slides():
    pairs = B.load_pairs(REPO / "scripts" / "bakeoff" / "pairs.json")
    assert pairs and all(len(p) == 3 and all(isinstance(x, str) and x for x in p) for p in pairs)
    titles = [t for _, t in B.slide_titles(REPO / "templates" / "ars_template.pptx")]
    for a_prefix, _, _ in pairs:
        assert any(B._starts(t, a_prefix) for t in titles), f"{a_prefix!r} is not a template slide"


def test_the_page_lists_every_slide_and_no_missing_images(tmp_path):
    from pptx import Presentation
    for side, names in (("a", ["Agenda", "Transaction Increase Over the Ask"]), ("j", ["Lift by response segment"])):
        p = Presentation()
        for n in names:
            s = p.slides.add_slide(p.slide_layouts[5]); s.shapes.title.text = n
        p.save(tmp_path / f"{side}.pptx")
        (tmp_path / side).mkdir()
        for i in range(1, len(names) + 1):
            (tmp_path / side / f"slide-{i:02d}.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    B.main([str(tmp_path / "a.pptx"), str(tmp_path / "a"), str(tmp_path / "j.pptx"), str(tmp_path / "j"),
            str(tmp_path / "out"), "--pairs", str(REPO / "scripts" / "bakeoff" / "pairs.json")])
    page = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
    assert page.count("<section") == 1 and "Only in Aaron" in page and "Missing images" not in page
    assert (tmp_path / "out" / "aaron" / "slide-02.png").exists()
