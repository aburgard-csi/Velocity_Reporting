"""Which chapters and slides go in the deck (build/ars_pipeline/ti/selection.py, ti/slides.json).

Every key in slides.json names a real chapter or a slide the cut draws (a typo would silently do
nothing); a tossed slide is left out of the deck with no stated page; a `*` key covers the slides
named per offer; and a tossed chapter loses its divider and agenda row.
"""
import ast
import fnmatch
import glob
import json
import os

from pptx import Presentation

from ti import cut, selection
from ti.chapters import ALL
from ti.deck.helpers import Deck

HERE = os.path.dirname(os.path.abspath(__file__))
SLIDES = os.path.join(HERE, "..", "build", "ars_pipeline", "ti", "slides.json")


def _drawn_titles():
    """Every fixed title the cut's builders pass to slide(), and every builder title map."""
    found = set()
    for f in glob.glob(os.path.join(HERE, "..", "build", "ars_pipeline", "ti", "deck", "*.py")):
        for n in ast.walk(ast.parse(open(f, encoding="utf-8").read())):
            if isinstance(n, ast.Call) and len(n.args) >= 2 and isinstance(n.args[1], ast.Constant):
                fn = n.func
                name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", None)
                if isinstance(fn, ast.Subscript) and isinstance(fn.slice, ast.Constant):
                    name = fn.slice.value
                if name == "slide" and isinstance(n.args[1].value, str):
                    found.add(n.args[1].value)
    return found


def test_every_key_names_a_real_chapter_or_slide_and_every_slide_is_listed():
    data = json.load(open(SLIDES, encoding="utf-8"))
    assert set(data["chapters"]) == {ch.title for ch in ALL}
    drawn = _drawn_titles()
    from ti.chapters import attrition, campaign, deposits, economics, ics, value
    import ti.chapters_txn as T
    # the topic of a pair drawn as one slide (ti/deck/combine.py) is named by the chapter's COMBINED
    combined = {pair[2] for pairs in (T.TI_COMBINED, T.COMP_COMBINED, attrition.COMBINED, deposits.COMBINED,
                                      campaign.COMBINED, economics.COMBINED) for pair in pairs}
    titled = (set(T.TITLES.values()) | set(attrition.TITLES.values()) | set(deposits.TITLES.values())
              | set(ics.ORDER) | set(economics.TITLES.values()) | set(value.TITLES.values())
              | set(campaign.TITLES.values()) | drawn | combined)
    for key in data["slides"]:
        assert key in titled or ("*" in key and any(fnmatch.fnmatchcase(t, key) for t in
                                 ["Mailer Jun26 summary", "Offer Jun26 by segment",
                                  "Jun26: responders versus their segment"])), f"{key!r} names no slide"
    listed = set(data["slides"])
    missing = [t for t in drawn if t not in listed and not any("*" in k and fnmatch.fnmatchcase(t, k) for k in listed)]
    assert not missing, f"drawn but not listed in slides.json: {missing}"
    assert set(data["slides"].values()) <= {"keep", "toss"}


def _write(tmp_path, chapters=None, slides=None):
    p = tmp_path / "slides.json"
    p.write_text(json.dumps({"chapters": chapters or {}, "slides": slides or {}}), encoding="utf-8")
    return str(p)


def test_a_tossed_slide_is_left_out_and_a_star_covers_per_offer_slides(tmp_path, monkeypatch):
    monkeypatch.setenv("TI_SLIDES", _write(tmp_path, slides={"Who they pay": "toss",
                                                             "Mailer * summary": "toss"}))
    assert not selection.slide_kept("Who they pay")
    assert not selection.slide_kept("Mailer Jun26 summary")
    assert selection.slide_kept("Where the money goes"), "an unlisted slide is kept"

    class _Ctx:
        prs = Presentation(os.path.join(HERE, "..", "templates", "ars_template.pptx"))
        pack = {"client_id": "9999", "client_name": "Test Bank", "sources": {"odd": "x"}, "metrics": {}}
        lens = type("L", (), {"label": "ARS lens"})()
        pill, art_dir = "September 2026 Data", str(tmp_path)

    deck = Deck(_Ctx(), "the ODD extract", tmp_path / "charts")

    def who_they_pay(h, t):
        return "no fin_top_providers"

    def where_the_money_goes(h, t):
        h["slide"](("Card spend sits with three groups", None), "Where the money goes")

    slides = deck.run([who_they_pay, where_the_money_goes],
                      {"who_they_pay": "Who they pay", "where_the_money_goes": "Where the money goes"}, {})
    assert [deck.topics[id(s)] for s in slides] == ["Where the money goes"], "no stated page for a toss"


def test_a_tossed_chapter_loses_its_divider_and_agenda_row(tmp_path, monkeypatch):
    monkeypatch.setenv("TI_SLIDES", _write(tmp_path, chapters={"Economics": "toss"}))
    assert not selection.chapter_kept("Economics") and selection.chapter_kept("Value")
    kept = [ch.title for ch in ALL if selection.chapter_kept(ch.title)]
    assert "Economics" not in kept and len(kept) == len(cut.CHAPTERS) - 1


def test_a_value_other_than_keep_or_toss_stops_the_build(tmp_path, monkeypatch):
    monkeypatch.setenv("TI_SLIDES", _write(tmp_path, slides={"Who they pay": "maybe"}))
    try:
        selection.slide_kept("Who they pay")
    except SystemExit as exc:
        assert "keep" in str(exc) and "maybe" in str(exc)
    else:
        raise AssertionError("an unknown state must stop the build")
