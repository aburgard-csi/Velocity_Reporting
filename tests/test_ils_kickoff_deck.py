# Ported from v5 02-Scripts/tests/test_ils_kickoff_deck.py at 7ba1e63. Tests unchanged; edits: imports from ils_pipeline.kickoff (and its _v5/ copies of core, ars.deck, deckkit), the run.py path, no sys.path insert (tests/conftest.py puts build/ on it), and the autouse legacy_strings() fixture.
"""The ILS kickoff deck: the manifest and the workbook must not drift.

The deposit chapter's lesson, applied before it can happen here: an analysis
that is computed and reaches no output is invisible, and invisible is where a
wrong number lives. Adding an analysis without adding a slide has to be a
deliberate choice, so the run reports it.

    python -m pytest tests/test_ils_kickoff_deck.py -q
"""
import pathlib
import sys

import pandas as pd
import pytest

HERE = pathlib.Path(__file__).resolve().parent

from ils_pipeline.kickoff.deck import slides  # noqa: E402
from ils_pipeline.kickoff._v5.core import layout

TEMPLATE = layout.TEMPLATE


@pytest.fixture(autouse=True)
def _v5_pandas():
    """RPE: v5's code under the pandas 2 string semantics it was written for (kickoff/_v5/compat.py)."""
    from ils_pipeline.kickoff._v5.compat import legacy_strings
    with legacy_strings():
        yield


def _frame(n=3):
    return pd.DataFrame({"Band": [f"b{i}" for i in range(n)],
                         "Accounts": range(n), "Share": [0.1] * n})


def _analyses(keys=None):
    return {k: _frame() for k in (keys or slides.MANIFEST_KEYS)}


# ---- the manifest is the contract ---------------------------------------

def test_every_manifest_key_is_unique():
    assert len(slides.MANIFEST_KEYS) == len(set(slides.MANIFEST_KEYS))


def test_the_manifest_covers_every_analysis_the_run_emits():
    """The join between run.py and the deck is the sheet name."""
    import re
    src = (HERE.parent / "build" / "ils_pipeline" / "kickoff" / "run.py").read_text(encoding="utf-8")
    emitted = set(re.findall(r'emit\(report_path,\s*"([^"]+)"', src))
    missing = emitted - set(slides.MANIFEST_KEYS) - set(slides.WORKBOOK_ONLY)
    assert not missing, f"analyses emitted with no slide: {sorted(missing)}"


def test_a_workbook_only_sheet_is_not_also_a_slide():
    assert not set(slides.WORKBOOK_ONLY) & set(slides.MANIFEST_KEYS)


def test_a_slide_with_no_analysis_is_reported_not_rendered():
    stranded = slides.unslided({"Some New Analysis": _frame()})
    assert stranded == ["Some New Analysis"]


def test_a_full_run_strands_nothing():
    assert slides.unslided(_analyses()) == []


def test_every_slide_sits_under_a_named_section():
    for spec in slides.SLIDE_MANIFEST:
        assert spec.section in slides.SECTIONS, spec.key


# ---- it actually builds --------------------------------------------------

@pytest.mark.skipif(not TEMPLATE.exists(), reason="deck template not present")
def test_a_deck_is_written_and_opens(tmp_path):
    out = tmp_path / "kickoff.pptx"
    slides.build("1842", "2026-09", _analyses(), {}, TEMPLATE, out)
    assert out.exists() and out.stat().st_size > 0

    from pptx import Presentation
    prs = Presentation(str(out))
    # cover + provenance + 3 dividers + 19 analyses
    # cover + provenance + 3 dividers + 19, then appendix divider + 19
    n = len(slides.MANIFEST_KEYS)
    assert len(prs.slides) == 2 + len(slides.SECTIONS) + n + 1 + n


@pytest.mark.skipif(not TEMPLATE.exists(), reason="deck template not present")
def test_an_analysis_that_did_not_run_is_absent_not_empty(tmp_path):
    out = tmp_path / "partial.pptx"
    some = _analyses(slides.MANIFEST_KEYS[:4])
    slides.build("1842", "2026-09", some, {}, TEMPLATE, out)

    from pptx import Presentation
    prs = Presentation(str(out))
    # cover + provenance + 1 divider (all four in the first section) + 4
    assert len(prs.slides) == 2 + 1 + 4 + 1 + 4


@pytest.mark.skipif(not TEMPLATE.exists(), reason="deck template not present")
def test_an_empty_table_does_not_become_a_slide(tmp_path):
    out = tmp_path / "empty.pptx"
    a = _analyses(slides.MANIFEST_KEYS[:2])
    a[slides.MANIFEST_KEYS[1]] = pd.DataFrame()
    slides.build("1842", "2026-09", a, {}, TEMPLATE, out)

    from pptx import Presentation
    assert len(Presentation(str(out)).slides) == 2 + 1 + 1 + 1 + 1


@pytest.mark.skipif(not TEMPLATE.exists(), reason="deck template not present")
def test_the_warnings_reach_the_deck(tmp_path):
    """A run that could not account for its input says so ON the deck."""
    out = tmp_path / "warned.pptx"
    slides.build("1842", "2026-09", _analyses(slides.MANIFEST_KEYS[:1]), {},
                 TEMPLATE, out, warnings=["3 of 6 open accounts are in neither segment"])

    from pptx import Presentation
    text = " ".join(sh.text_frame.text for s in Presentation(str(out)).slides
                    for sh in s.shapes if sh.has_text_frame)
    assert "could not account for" in text
    assert "neither segment" in text


# ---- the charts, which are the point of a deck --------------------------

def test_every_slide_has_a_chart_form():
    """A deck of tables is a workbook with worse formatting."""
    assert slides.chartless() == []


def test_no_two_slides_use_the_same_chart_form():
    """The deposit deck's rule. A reader who sees the same picture twice
    stops reading the second one."""
    from ils_pipeline.kickoff.deck import forms
    names = [name for _, name in forms.FORMS.values()]
    assert len(names) == len(set(names)), \
        f"repeated form: {sorted({n for n in names if names.count(n) > 1})}"


def test_the_forms_cover_the_manifest_exactly():
    from ils_pipeline.kickoff.deck import forms
    assert set(forms.FORMS) == set(slides.MANIFEST_KEYS)


def test_a_chart_that_cannot_be_drawn_loses_the_picture_not_the_slide(tmp_path):
    """A malformed chart must never take the deck down mid-run."""
    from ils_pipeline.kickoff.deck import forms
    broken = pd.DataFrame({"Nothing": ["a"], "Useless": [1]})
    assert forms.render("Account Status Analysis", broken, tmp_path) is None


@pytest.mark.skipif(not TEMPLATE.exists(), reason="deck template not present")
def test_the_deck_carries_pictures_not_only_tables(tmp_path):
    out = tmp_path / "charted.pptx"
    slides.build("1842", "2026-09", _analyses(), {}, TEMPLATE, out,
                 charts_dir=tmp_path)
    from pptx import Presentation
    prs = Presentation(str(out))
    pictures = sum(1 for s in prs.slides for sh in s.shapes
                   if sh.shape_type == 13)          # PICTURE
    assert pictures >= 10, f"only {pictures} slides carried a chart"


# ---- the chart must not print under the callout tiles -------------------

def test_a_chart_beside_a_rail_stops_before_the_tiles():
    """"Chart and data callouts overlap" -- four slides in one review.
    _picture centred across the whole content field while _rail sat at
    10.15in, so any chart wider than ~9in printed underneath the tiles."""
    from ils_pipeline.kickoff._v5.ars.deck.build import CONTENT_W, MARGIN_L, RAIL_GUTTER, RAIL_LEFT

    with_rail = RAIL_LEFT - RAIL_GUTTER - MARGIN_L
    assert with_rail < CONTENT_W, "the rail field must be narrower"
    assert MARGIN_L + with_rail <= RAIL_LEFT, "the chart field reaches the tiles"


def test_picture_takes_a_rail_flag():
    import inspect

    from ils_pipeline.kickoff._v5.ars.deck.build import _picture
    assert "rail" in inspect.signature(_picture).parameters


def test_no_deposit_chart_label_carries_a_decimal():
    """"The floats can be no decimals." False precision at arm's length."""
    import inspect

    from ils_pipeline.kickoff.deck import forms
    src = inspect.getsource(forms)
    assert '{:,.1f}' not in src, "a chart label still formats to one decimal"


def test_the_deck_opens_with_a_designed_cover_not_a_blank():
    """"It's just a white thing right now." The cover uses divider(), the
    designed navy object this template already has."""
    import inspect
    src = inspect.getsource(slides._build)
    assert "dk.divider(prs, new," in src


def _slide_text(path, index):
    """Every string on one rendered slide."""
    from pptx import Presentation
    said = []
    for shape in Presentation(str(path)).slides[index].shapes:
        if shape.has_text_frame and shape.text_frame.text.strip():
            said.append(shape.text_frame.text)
    return said


@pytest.mark.skipif(not TEMPLATE.exists(), reason="deck template not present")
def test_a_provenance_slide_states_what_the_run_cannot_know(tmp_path):
    """Collected-as-of and the date range are the file creator's to fill in.
    Printed as an explicit blank rather than left silently absent.

    Read off the RENDERED slide, not out of the function's source: the same
    strings scraped from source passed while the slide itself put them in a
    paragraph with the bottom half of the page empty."""
    out = tmp_path / "prov.pptx"
    slides.build("1842", "2026-09", _analyses(), {}, TEMPLATE, out,
                 source="/x/1842_OneTimeData_20260901.csv", appendix=False)
    said = " ".join(_slide_text(out, 1))
    for field in ("Collected as of", "Data covers", "Known exclusions"):
        assert field in said, f"{field} is not on the provenance slide"


@pytest.mark.skipif(not TEMPLATE.exists(), reason="deck template not present")
def test_the_extract_filename_is_never_truncated(tmp_path):
    """It was cut to 18 characters and printed "1842_OneTime Data_2" -- which
    reads as a broken string, and is the one fact this slide exists for."""
    out = tmp_path / "prov.pptx"
    name = "1842_OneTimeData_20260901.csv"
    slides.build("1842", "2026-09", _analyses(), {}, TEMPLATE, out,
                 source=f"/some/where/{name}", appendix=False)
    assert name in " ".join(_slide_text(out, 1))


@pytest.mark.skipif(not TEMPLATE.exists(), reason="deck template not present")
def test_the_name_to_fill_in_is_a_field_not_an_orphan(tmp_path):
    """`{CSM NAME} to be replaced` sat under the tiles at 9pt and read as an
    error rather than an instruction. It is the first blank to fill."""
    out = tmp_path / "prov.pptx"
    slides.build("1842", "2026-09", _analyses(), {}, TEMPLATE, out,
                 appendix=False)
    said = " ".join(_slide_text(out, 1))
    assert "Prepared by" in said
    assert "to be replaced" not in said


@pytest.mark.skipif(not TEMPLATE.exists(), reason="deck template not present")
def test_a_named_csm_leaves_no_blank_to_fill(tmp_path):
    out = tmp_path / "prov.pptx"
    slides.build("1842", "2026-09", _analyses(), {}, TEMPLATE, out,
                 csm="A Person", appendix=False)
    said = " ".join(_slide_text(out, 1))
    assert "Prepared by A Person" in said
    assert "the CSM sending this deck" not in said


def test_building_a_deck_writes_nothing_to_the_working_directory(tmp_path,
                                                                 monkeypatch):
    """368 chart PNGs reached the repo because charts_dir defaulted to
    Path("."). A build with no charts_dir must still leave the cwd alone."""
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.iterdir())
    slides.build("1840", "2026-09", _analyses(), {}, TEMPLATE,
                 tmp_path / "out" / "d.pptx")
    stray = {p for p in tmp_path.iterdir()} - before - {tmp_path / "out"}
    assert not stray, f"the build littered the working directory: {stray}"


def _tables(path):
    from pptx import Presentation
    return sum(1 for slide in Presentation(str(path)).slides
               for shape in slide.shapes if shape.has_table)


def test_the_appendix_adds_exactly_one_table_per_analysis(tmp_path):
    """"So the user can add them if he wants." Charts at the front because a
    table of digits is not a finding; the numbers at the back, formatted,
    ready to drag forward or delete.

    Counted as a difference, not an absolute: a main slide whose chart could
    not be drawn falls back to its own table, and that is correct.
    """
    with_ap = tmp_path / "with.pptx"
    without = tmp_path / "without.pptx"
    slides.build("1842", "2026-09", _analyses(), {}, TEMPLATE, with_ap,
                 charts_dir=tmp_path)
    slides.build("1842", "2026-09", _analyses(), {}, TEMPLATE, without,
                 charts_dir=tmp_path, appendix=False)
    assert _tables(with_ap) - _tables(without) == len(slides.MANIFEST_KEYS)


# ---- layout follows what the slide is for -------------------------------

def test_the_deck_uses_more_than_one_layout():
    """One layout on nineteen slides is one template wearing nineteen
    headlines -- the same defect as one chart form, a level up."""
    used = {slides.LAYOUTS.get(k, "rail") for k in slides.MANIFEST_KEYS}
    assert len(used) >= 3, used


def test_every_layout_name_is_one_the_renderer_knows():
    assert set(slides.LAYOUTS.values()) <= {"full", "hero"}


def test_a_slide_with_no_chart_falls_back_to_the_rail_layout(tmp_path):
    """full and hero both assume a chart. Without one they would render an
    empty page, so the fallback is the layout that can show a table."""
    out = tmp_path / "nochart.pptx"
    keys = [k for k in slides.MANIFEST_KEYS if slides.LAYOUTS.get(k) == "full"]
    slides.build("1842", "2026-09", _analyses(keys[:1]), {}, TEMPLATE, out)
    from pptx import Presentation
    prs = Presentation(str(out))
    assert any(sh.has_table for s in prs.slides for sh in s.shapes)


def test_the_hero_number_comes_off_the_rail_not_from_thin_air():
    panel = {"rail": [("Accounts", "5,396", "in this cut"),
                      ("Pay rate", "81%", "of 1,479 items")]}
    value, label, note = slides._hero_number(panel)
    assert value == "81%" and "Pay rate" in label


def test_the_hero_label_does_not_swallow_the_note():
    """Joined into one string they ran to "Pay rate - of 76,199 items
    presented" and the card clipped it to "Pay rate - o"."""
    panel = {"rail": [("Pay rate", "73%", "of 76,199 items presented")]}
    value, label, note = slides._hero_number(panel)
    assert label == "Pay rate", label
    assert note == "of 76,199 items presented", note


def test_the_hero_card_does_not_sit_on_its_own_chart():
    """The card was placed at 0.7in and the picture centred across a field
    starting at 1.18in, so it printed on top of the donut on all three hero
    slides. The card belongs where the rail tiles belong."""
    import inspect
    from ils_pipeline.kickoff._v5.ars.deck.build import RAIL_GUTTER, RAIL_LEFT
    src = inspect.getsource(slides._slide)
    assert "dk.kpi(slide, dk.RAIL_LEFT" in src, \
        "the hero card is placed at a literal again"
    # and the chart field must stop before it
    assert "_place(slide, Path(panel[\"chart\"]), rail=True)" in src


def test_every_layout_fills_the_same_named_band():
    """Three layouts carried three different pairs of magic numbers and none
    of them was the slide."""
    import inspect
    src = inspect.getsource(slides._slide)
    for stale in ("5.05", "4.95", "4.4", "1.9,"):
        assert stale not in src, f"a magic band number survives: {stale}"
    assert slides.BAND_H == slides.BAND_BOTTOM - slides.BAND_TOP


def test_the_band_matches_the_grid_it_claims_to_come_from():
    """BAND_BOTTOM is ars.deck.build's rail floor. If the grid moves and this
    does not, every chart on the deck is placed against a stale number."""
    from ils_pipeline.kickoff._v5.ars.deck.build import RAIL_BOTTOM
    assert slides.BAND_BOTTOM == RAIL_BOTTOM


def test_a_form_is_authored_at_the_aspect_of_the_slot_it_lands_in():
    """The canvas constants exist so a chart FILLS its band. If they drift
    from the grid, every chart lands short again and the bottom third of the
    slide goes white."""
    from ils_pipeline.kickoff._v5.ars.deck import charts
    from ils_pipeline.kickoff._v5.ars.deck.build import CONTENT_W, MARGIN_L, RAIL_GUTTER, RAIL_LEFT
    rail_field = RAIL_LEFT - RAIL_GUTTER - MARGIN_L
    assert abs(charts.FIG_W_RAIL / charts.FIG_H_RAIL
               - rail_field / slides.BAND_H) < 0.02
    assert abs(charts.FIG_W_FULL / charts.FIG_H_FULL
               - CONTENT_W / slides.BAND_H) < 0.02


# ---------------------------------------------------------------------------
# What a chart SAYS, not where it sits.
#
# The suite was green -- 44 slides, 19 charts, 0 overlapping the rail -- while
# the deck printed "$74" over a 74% pay-rate band, "2768.0%" over a count of
# 2,768 items, "-2276.0%" between two cross-tab cells, and "monthly swipe
# tier" under OD/NSF bands. Every one of those came from a SHARED form whose
# unit and axis wording were written for the ARS deck and hardcoded, and no
# test read a single word a chart draws.
#
# These tests read the words.
# ---------------------------------------------------------------------------

def _drawn(monkeypatch, call):
    """Every string a form draws, captured at the one hook they all pass."""
    from ils_pipeline.kickoff._v5.ars.deck import charts as ars_charts
    said = []
    real_save = ars_charts._save

    def spy(fig, path):
        for ax in fig.axes:
            said.extend(t.get_text() for t in ax.texts)
            said.extend([ax.get_xlabel(), ax.get_ylabel()])
            # Ticks on a hidden axis are laid out but never drawn; counting
            # them reads matplotlib's defaults as though the chart said them.
            if ax.axison and ax.get_xaxis().get_visible():
                said.extend(t.get_text() for t in ax.get_xticklabels())
            if ax.axison and ax.get_yaxis().get_visible():
                said.extend(t.get_text() for t in ax.get_yticklabels())
        said.extend(t.get_text() for t in fig.texts)
        return real_save(fig, path)

    monkeypatch.setattr(ars_charts, "_save", spy)
    call()
    return [s for s in said if s and s.strip()]


# Words that belong to another product's subject. A chart on the ILS kickoff
# deck talks about accounts, items, deposits and OD/NSF bands -- never swipes,
# tickets or merchants.
# "institution", "reach" and "momentum" are momentum_bars' column headers;
# "· local" is the suffix it appends to the row it marks. All three printed
# on the OD Limit slide, over overdraft-limit bands.
_FOREIGN = ("swipe", "ticket", "merchant", "interchange", "run rate",
            "institution", "reach", "momentum", "competitor", "\u00b7 local")


def _ils_frames():
    """One plausible frame per analysis, with the columns each adapter reads."""
    bands = ["0", "1-6", "7-12", "13-24"]
    base = pd.DataFrame({
        "Band": bands,
        "# of Accounts": [800, 400, 200, 100],
        "Accounts": [800, 400, 200, 100],
        "% of Accounts": [53.3, 26.7, 13.3, 6.7],
        "Total OD/NSF Items": [0, 1200, 900, 700],
        "# of Items Paid": [0, 890, 640, 500],
        "% of Items Presented": [0.0, 42.9, 32.1, 25.0],
        "Pay Ratio": [0.0, 0.74, 0.71, 0.71],
        "Avg # of Deposits": [0.0, 1.0, 4.0, 7.0],
        "Med # of Deposits": [0.0, 1.0, 4.0, 7.0],
        "Avg $$ Dep/Month": [0.0, 2800.0, 2900.0, 3100.0],
    })
    return {k: base for k in slides.MANIFEST_KEYS}


@pytest.mark.parametrize("key", sorted(_ils_frames()))
def test_no_ils_chart_speaks_another_products_language(key, tmp_path,
                                                       monkeypatch):
    """`histogram` labelled its axis "swipes above the account's own prior
    run rate" and `ticket_bars` "monthly swipe tier". Both went to a client
    on a deck about overdraft items."""
    from ils_pipeline.kickoff.deck import forms
    frame = _ils_frames()[key]
    said = _drawn(monkeypatch, lambda: forms.render(key, frame, tmp_path))
    offenders = [s for s in said
                 if any(w in s.lower() for w in _FOREIGN)]
    assert not offenders, f"{key} says {offenders}"


def test_a_pay_ratio_is_never_drawn_as_money(tmp_path, monkeypatch):
    """ticket_bars printed "$74" and "blended $73" over pay-rate bands."""
    from ils_pipeline.kickoff.deck import forms
    frame = _ils_frames()["NSF Pay Ratio"]
    said = _drawn(monkeypatch,
                  lambda: forms.render("NSF Pay Ratio", frame, tmp_path))
    assert not [s for s in said if "$" in s], \
        f"a pay ratio drawn in dollars: {[s for s in said if '$' in s]}"
    assert any("%" in s for s in said), "the pay rate lost its unit entirely"


def test_a_count_of_items_is_never_drawn_as_a_percentage(tmp_path, monkeypatch):
    """dumbbell printed "2768.0%" over 2,768 presented items."""
    from ils_pipeline.kickoff.deck import forms
    frame = _ils_frames()["NSF Pay Ratio (Business)"]
    said = _drawn(monkeypatch, lambda: forms.render(
        "NSF Pay Ratio (Business)", frame, tmp_path))
    assert "1,200" in said, f"the item count is not drawn as a count: {said}"
    assert not [s for s in said if s.rstrip("%").replace(",", "").replace(
        ".", "").isdigit() and s.endswith("%")], \
        f"an item count carries a percent sign: {said}"


def test_no_chart_states_a_drop_off_the_table_does_not_have(tmp_path,
                                                            monkeypatch):
    """The Reg E eligibility table is a cross-tab, not a funnel. Passing the
    difference between consecutive rows as a drop printed "-2276.0%"."""
    from ils_pipeline.kickoff.deck import forms
    frame = _ils_frames()["Reg E by OD Eligibility"]
    said = _drawn(monkeypatch, lambda: forms.render(
        "Reg E by OD Eligibility", frame, tmp_path))
    assert not [s for s in said if "%" in s], \
        f"a drop-off asserted between cross-tab cells: {said}"


def test_a_count_of_accounts_is_drawn_as_a_whole_number(tmp_path, monkeypatch):
    """rege_split took float counts and printed "5,093.0 (30%)"."""
    from ils_pipeline.kickoff.deck import forms
    frame = _ils_frames()["Reg E Summary"]
    said = _drawn(monkeypatch,
                  lambda: forms.render("Reg E Summary", frame, tmp_path))
    assert not [s for s in said if ".0 (" in s or s.endswith(".0")], \
        f"a count of accounts carries a decimal: {said}"


# ---- the labels a row is keyed by ---------------------------------------

def test_a_two_key_table_labels_every_row(tmp_path):
    """`Reg E by OD Eligibility` is keyed by Eligibility THEN Reg E Flag, and
    pandas leaves the outer key blank on all but the first row of each group.
    Reading column 0 alone gave two band names and four empty strings -- and
    a headline asserting 26% of accounts sat in the band called ""."""
    from ils_pipeline.kickoff.deck import forms
    frame = pd.DataFrame({
        "Eligibility": ["Eligible", "", "", "Ineligible", "", ""],
        "Reg E Flag": ["D", "N", "Y", "D", "N", "Y"],
        "# of Accounts": [2246, 4522, 2778, 1789, 3609, 2315],
    })
    labels = forms._labels(frame)
    assert all(l.strip() for l in labels), f"a row has no label: {labels}"
    assert labels[1] == "Eligible · N", labels
    assert labels[5] == "Ineligible · Y", labels


def test_a_single_key_table_is_untouched():
    from ils_pipeline.kickoff.deck import forms
    frame = pd.DataFrame({"Account Status": ["C", "D", "O"],
                          "# of Accounts": [1, 2, 3]})
    assert forms._labels(frame) == ["C", "D", "O"]


# ---- the codes a run was told the meaning of ----------------------------

def test_a_confirmed_code_is_spoken_as_a_word(tmp_path):
    """`88% of them in "O"` is not a sentence anyone reads out in a client
    meeting. The run is TOLD which code means open."""
    from ils_pipeline.kickoff.core.io import CodeConfig
    from ils_pipeline.kickoff.deck import forms
    frame = pd.DataFrame({"Account Status": ["C", "O"],
                          "# of Accounts": [10, 90],
                          "Pay Ratio": [0.7, 0.7]})
    panel = forms.panel("Account Status Analysis", frame, tmp_path,
                        CodeConfig())
    tiles = " ".join(f"{l} {v} {n}" for l, v, n in panel["rail"])
    assert "Open" in tiles, tiles
    assert '\u201cO\u201d' not in panel["headline"], panel["headline"]


def test_an_unconfirmed_code_is_left_exactly_as_it_is(tmp_path):
    """Reg E flags are the codes the run refuses to guess at. Naming them
    here would be the same guess, one layer along."""
    from ils_pipeline.kickoff.core.io import CodeConfig
    from ils_pipeline.kickoff.deck import forms
    frame = pd.DataFrame({"Reg E Flag": ["D", "N", "Y"],
                          "# of Accounts": [10, 20, 70]})
    panel = forms.panel("Reg E Summary", frame, tmp_path, CodeConfig())
    # the codes reach the slide exactly as the file spells them...
    assert forms._labels(forms._body(frame)) == ["D", "N", "Y"]
    # ...and nothing on the slide claims to know what any of them means
    said = panel["headline"] + " " + panel["subtitle"]
    # It may SAY the words while explaining that nobody has confirmed them.
    # What it must never do is claim a rate.
    assert "have opted in" not in said, said
    assert "confirmed" in said.lower(), said


def _boxes(path, index):
    """(left, top, right, bottom, text) for every text shape on one slide."""
    from pptx import Presentation
    from pptx.util import Emu
    out = []
    for sh in Presentation(str(path)).slides[index].shapes:
        if not sh.has_text_frame or not sh.text_frame.text.strip():
            continue
        l, t = Emu(sh.left).inches, Emu(sh.top).inches
        out.append((l, t, l + Emu(sh.width).inches,
                    t + Emu(sh.height).inches, sh.text_frame.text))
    return out


@pytest.mark.skipif(not TEMPLATE.exists(), reason="deck template not present")
def test_nothing_on_the_provenance_slide_prints_over_anything_else(tmp_path):
    """The field stack was stepped by a constant and ran to 6.82in on a band
    that ends at 6.62 -- so the closing line printed straight through
    "Known exclusions". It is solved against the band now."""
    out = tmp_path / "prov.pptx"
    slides.build("1842", "2026-09", _analyses(), {}, TEMPLATE, out,
                 source="/x/1842_OneTimeData_20260901.csv", appendix=False)
    boxes = _boxes(out, 1)
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            overlap_x = min(a[2], b[2]) - max(a[0], b[0]) > 0.05
            overlap_y = min(a[3], b[3]) - max(a[1], b[1]) > 0.05
            assert not (overlap_x and overlap_y), \
                f"{a[4]!r} prints over {b[4]!r}"


@pytest.mark.skipif(not TEMPLATE.exists(), reason="deck template not present")
def test_the_provenance_slide_stays_inside_the_slide(tmp_path):
    out = tmp_path / "prov.pptx"
    slides.build("1842", "2026-09", _analyses(), {}, TEMPLATE, out,
                 appendix=False)
    for box in _boxes(out, 1):
        assert box[3] <= dk_slide_h() + 0.01, f"{box[4]!r} runs off the slide"


def dk_slide_h():
    from ils_pipeline.kickoff._v5 import deckkit as dk
    return dk.SLIDE_H


# ---------------------------------------------------------------------------
# One headline per slide, and none of them dead.
# ---------------------------------------------------------------------------

def test_the_manifest_carries_no_field_the_renderer_never_reads():
    """`Slide.headline` declared "what the slide asserts" on all nineteen
    entries and was read by nothing -- which is where nineteen careful
    headlines went while every slide printed the same generated sentence."""
    import dataclasses
    fields = {f.name for f in dataclasses.fields(slides.Slide)}
    assert fields == {"key", "section"}, fields


def test_the_deck_does_not_say_one_sentence_nineteen_times():
    """Fifteen of nineteen called one function, so the deck said the same
    sentence in different nouns -- the chart-form defect a level up.

    Compared with the digits stripped, because it is the SENTENCE that was
    repeated, not the numbers. A personal/business pair may share one: they
    ask the same question of a different segment, which is the only sharing
    that is honest."""
    import re
    from ils_pipeline.kickoff.core.io import CodeConfig
    from ils_pipeline.kickoff.deck import forms
    codes = CodeConfig(rege_opt_in=["Y"])
    shapes = {}
    for key in slides.MANIFEST_KEYS:
        b = forms._body(forms._spoken(key, _headline_frame(key), codes))
        shape = re.sub(r"[\d,.$%]+", "#", forms.HEADLINES[key](b, codes)[0])
        shapes.setdefault(shape, []).append(key)
    assert len(shapes) >= 11, \
        f"only {len(shapes)} distinct headlines across 19 slides: {shapes}"
    over = {k: v for k, v in shapes.items() if len(v) > 2}
    assert not over, f"more than a personal/business pair share a sentence: {over}"


def test_every_headline_states_a_number():
    """A headline states the finding with its number, not the field list."""
    import re
    from ils_pipeline.kickoff.core.io import CodeConfig
    from ils_pipeline.kickoff.deck import forms
    codes = CodeConfig(rege_opt_in=["Y"])
    for key in slides.MANIFEST_KEYS:
        b = forms._body(forms._spoken(key, _headline_frame(key), codes))
        headline = forms.HEADLINES[key](b, codes)[0]
        assert re.search(r"\d", headline), f"{key}: {headline!r} has no number"


def test_a_reg_e_headline_claims_no_opt_in_rate_without_a_mapping():
    """An opt-in rate is a claim about a mapping nobody confirmed. The run
    refuses to guess it; so must the sentence on the slide."""
    from ils_pipeline.kickoff.core.io import CodeConfig
    from ils_pipeline.kickoff.deck import forms
    frame = _headline_frame("Reg E Summary")
    b = forms._body(frame)
    headline, subtitle = forms.HEADLINES["Reg E Summary"](b, CodeConfig())
    assert "opted in" not in headline, headline
    assert "confirmed" in (headline + subtitle).lower()

    told = CodeConfig(rege_opt_in=["Y"])
    headline, _ = forms.HEADLINES["Reg E Summary"](b, told)
    assert "opted in" in headline, headline


def _headline_frame(key):
    """A frame shaped like the one this analysis emits."""
    labels = {"Account Status Analysis": ("Account Status", ["C", "O"]),
              "Account Type Analysis": ("Business Flag", ["B", "P"]),
              "Reg E Summary": ("Reg E Flag", ["N", "Y"]),
              "Historical Reg E": ("Reg E Flag", ["N", "Y"])}
    if key in ("Reg E by OD Eligibility", "Reg E by OD Eligibility (Biz)"):
        return pd.DataFrame({
            "Eligibility": ["Eligible", "", "Ineligible", ""],
            "Reg E Flag": ["N", "Y", "N", "Y"],
            "# of Accounts": [400, 200, 300, 100],
            "% of Accounts": [40.0, 20.0, 30.0, 10.0]})
    col, vals = labels.get(key, ("Band", ["0", "1-6"]))
    return pd.DataFrame({
        col: vals,
        "# of Accounts": [600, 400], "Accounts": [600, 400],
        "% of Accounts": [60.0, 40.0],
        "Total OD/NSF Items": [0, 900], "# of Items Paid": [0, 650],
        "Pay Ratio": [0.0, 0.72],
        "Avg $$ Dep/Month": [2800.0, 3400.0]})
