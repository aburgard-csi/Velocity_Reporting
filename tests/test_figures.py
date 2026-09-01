"""figures — the builder-emitted provenance sidecar.

The Wellworth defect (2026-08-28): the Jun 2026 drop's responder count rendered
1,077 on the mailing slides and 1,026 on Reach / Depth / Ranking / Sustained,
because those four counted a historical mailing's responders through the CURRENT
eligibility snapshot. Both text swaps landed, so the builder's swap gate — which
fails a build whose swap string matched NOTHING — saw nothing wrong.

The sidecar closes that: the builder names the measure as it writes each figure,
so "two slides disagree about one measure" becomes arithmetic instead of the
inference that keeps figure_identity_findings at REVIEW.
"""
import json
import os
import pytest
from types import SimpleNamespace as N
from figures import FigureLog, log, record, sidecar_path, find_sidecar, slide_title


def slide(title):
    return N(shapes=[N(has_text_frame=True, text_frame=N(text=title))])


@pytest.fixture
def fresh():
    return FigureLog()


# --- recording ------------------------------------------------------------
def test_records_measure_value_and_slide(fresh):
    fresh.record("responders_latest_mailing", "1,077", slide("Mailing Response Summary"))
    assert fresh.rows == [{"measure": "responders_latest_mailing", "value": "1,077",
                           "slide": "Mailing Response Summary", "note": ""}]


def test_unnamed_figures_are_not_recorded(fresh):
    """Naming is opt-in — only measures reaching more than one slide need it."""
    fresh.record(None, "1,077", slide("Anything"))
    fresh.record("", "1,077", slide("Anything"))
    assert len(fresh) == 0


def test_value_is_normalized_to_string(fresh):
    fresh.record("m", 1077, slide("S"))
    fresh.record("m", "  1077  ", slide("S"))
    assert {r["value"] for r in fresh.rows} == {"1077"}


def test_slide_title_takes_the_first_non_empty_line():
    assert slide_title(slide("Program Reach\nCumulative")) == "Program Reach"


def test_slide_title_survives_a_shapeless_slide():
    assert slide_title(N(shapes=[])) == ""


# --- the assertion the sidecar exists to make -----------------------------
def test_one_measure_two_values_is_a_conflict(fresh):
    fresh.record("responders_jun2026", "1,077", slide("Mailing Response Summary"))
    fresh.record("responders_jun2026", "1,026", slide("Program Reach"))
    c = fresh.conflicts()
    assert len(c) == 1
    measure, byval = c[0]
    assert measure == "responders_jun2026"
    assert set(byval) == {"1,077", "1,026"}
    assert byval["1,026"] == ["Program Reach"]


def test_one_measure_repeated_consistently_is_not_a_conflict(fresh):
    for s in ("Mailing Response Summary", "Program Reach", "Depth of Engagement"):
        fresh.record("responders_jun2026", "1,026", slide(s))
    assert fresh.conflicts() == []


def test_different_measures_sharing_a_value_are_not_compared(fresh):
    """reach_total and dot_n are both 3,629 on 1204 — different measures."""
    fresh.record("reach_total", "3,629", slide("Program Reach"))
    fresh.record("dot_n", "3,629", slide("Transaction Increase Over the Ask"))
    assert fresh.conflicts() == []


def test_conflicts_are_reported_per_measure(fresh):
    fresh.record("a", "1", slide("S1")); fresh.record("a", "2", slide("S2"))
    fresh.record("b", "3", slide("S1")); fresh.record("b", "4", slide("S2"))
    fresh.record("c", "5", slide("S1"))
    assert [m for m, _ in fresh.conflicts()] == ["a", "b"]


# --- round trip -----------------------------------------------------------
def test_dump_and_load_round_trip(fresh, tmp_path):
    fresh.record("m", "1,077", slide("S"), note="caption")
    p = fresh.dump(str(tmp_path / "deck.pptx.figures.json"))
    assert p and json.load(open(p, encoding="utf-8"))["figures"][0]["note"] == "caption"
    assert FigureLog.load(p).rows == fresh.rows


def test_dump_returns_none_rather_than_raising(fresh):
    """Bookkeeping must never be the reason a build dies."""
    fresh.record("m", "1", slide("S"))
    assert fresh.dump("/no/such/directory/deck.figures.json") is None


def test_sidecar_does_not_land_beside_the_deck():
    """Outputs/ is the delivery folder and holds finished decks only."""
    p = sidecar_path("/x/Outputs/deck.pptx")
    assert os.path.basename(p) == "deck.pptx.figures.json", "named after its deck"
    assert os.path.dirname(p) != "/x/Outputs", "must not sit next to the deck"


def test_sidecar_goes_to_the_build_artifacts_folder():
    import rpe_env
    assert os.path.dirname(sidecar_path("/x/Outputs/deck.pptx")) == str(rpe_env.build_artifacts())


def test_find_sidecar_returns_none_when_absent(tmp_path):
    assert find_sidecar(str(tmp_path / "no-such-deck-xyz.pptx")) is None


def test_find_sidecar_still_locates_a_legacy_sidecar(tmp_path):
    """Decks built before the move carry theirs beside the deck."""
    deck = tmp_path / "deck.pptx"
    (tmp_path / "deck.pptx.figures.json").write_text('{"figures": []}')
    assert find_sidecar(str(deck)) == str(tmp_path / "deck.pptx.figures.json")


def test_find_sidecar_prefers_the_artifacts_folder(tmp_path, monkeypatch):
    import figures as F
    art = tmp_path / "artifacts"; art.mkdir()
    monkeypatch.setattr(F, "_artifacts_dir", lambda: str(art))
    deck = tmp_path / "deck.pptx"
    (art / "deck.pptx.figures.json").write_text('{"figures": []}')
    (tmp_path / "deck.pptx.figures.json").write_text('{"figures": []}')
    assert F.find_sidecar(str(deck)) == str(art / "deck.pptx.figures.json")


# --- the shared default instance -----------------------------------------
def test_module_level_record_uses_the_default_log():
    before = len(log)
    record("test_measure_xyz", "1", slide("S"))
    assert len(log) == before + 1
    log.rows = [r for r in log.rows if r["measure"] != "test_measure_xyz"]

