"""James's v5 ODD deck chapters drawn by Aaron's rules, opt-in (RPE_ANALYSIS_SLIDES=1) (2026-09-30).

The v5 slide body (engine/deck/ars_deck.py, verbatim) draws through ars_layout's primitives
and chapter_base's closures onto the ARS template shell. On the synthetic ODD plus a small
zipped transaction file: every v5 slide is in the inventory, drawn or skipped with its data
reason; the main path sits at its Aaron anchor and the rest in the appendix under one divider
per chapter; every drawn slide has a source note; the sidecar has no conflicts; the deck
passes the validator's text, geometry, collision, overflow, autofit, table and source rules
at 0 FAIL after the 16pt floor; no banned word survives; a table that grew at 16pt pushes
what follows it down instead of under it.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build" / "ars_pipeline"), str(REPO / "build"), str(REPO / "validation")]
from test_run_analysis import _write_txn_zip  # noqa: E402

# Drawn on the fixture. The rest decline for stated data reasons the fixture cannot meet
# (no ARS workbook, no deferral tracker, no deposits file, too few branches).
CORE = {"The campaign hero", "Program reach", "Response and reach by offer", "Per-offer summary",
        "What a response does to spend", "Responders versus control around the offer",
        "Debit card take rate", "Operational KPIs", "Take rate by branch", "Branch scorecard",
        "Reg E opt-in", "Reg E opt-in by branch", "Scorecard", "The most recent mailer",
        "Account health", "Eligible population"}
# Drawn, but with nothing to show on the fixture: the slide says so in its caption band.
EMPTY_ON_FIXTURE = {"Key takeaways"}
EXPECTED_TOTAL = 103        # v5 labels the fixture run touches, drawn or skipped


def _metrics(odd_csv, tmp):
    pd = pytest.importorskip("pandas")
    import run_analysis as RA
    ids = pd.read_csv(odd_csv, skiprows=4, dtype=str, usecols=["Acct Number"])["Acct Number"].dropna().tolist()[:120]
    txn_dir = _write_txn_zip(tmp / "Txn Files" / "1441", ids)
    RA.run(odd_csv, "1441", "2026.08", out_dir=tmp / "out", txn=True, txn_dirs=[txn_dir], tables=None,
           overrides={"LocalCompetitors": {"Capital One": ["CAPITAL ONE"]}})
    m = json.loads((tmp / "out" / "metrics.json").read_text(encoding="utf-8"))
    txn = json.loads((tmp / "out" / "txn_metrics.json").read_text(encoding="utf-8"))
    return m, txn


def _build(m, txn, tmp, client_name="Synthetic Bank", cut=None, with_ti=True):
    from pptx import Presentation
    import figures
    import restyle_fonts
    import ars_chapters
    import ti_chapter
    prs = Presentation(str(REPO / "templates" / "ars_template.pptx"))
    n_before = len(prs.slides)
    (tmp / "assets").mkdir(exist_ok=True)
    figures.log.__init__()
    ctx = {"as_of_long": "July 2026", "assets": str(tmp / "assets"), "txn_src": "Inputs/Txn Files/1441/",
           "odd_src": "ODD extract 1441 Synthetic Bank", "client_name": client_name, "out": str(tmp / "out")}
    if cut:
        ctx["cut"] = cut
    ti_made = ti_chapter.add_ti_chapter(prs, txn, ctx)[0] if with_ti else []
    made, inventory = ars_chapters.add_ars_chapters(prs, m, txn, ctx)
    out = tmp / "with_chapters.pptx"
    prs.save(str(out))
    restyle_fonts.restyle(str(out))
    return {"prs": prs, "path": out, "made": made, "ti_made": ti_made, "inventory": inventory,
            "n_before": n_before, "log": figures.log}


@pytest.fixture(scope="module")
def chapters(odd_csv, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("odd")
    m, txn = _metrics(odd_csv, tmp)
    return _build(m, txn, tmp)


def _title(s):
    return next((sh.text_frame.text.strip().split("\n")[0] for sh in s.shapes
                 if sh.has_text_frame and sh.text_frame.text.strip()), "")


def test_every_v5_slide_is_accounted_for(chapters):
    inv = chapters["inventory"]
    assert len(inv) == EXPECTED_TOTAL, len(inv)
    drawn = {e["v5_title"] for e in inv if e["status"] == "drawn"}
    assert CORE <= drawn, CORE - drawn
    for e in inv:
        if e["status"] != "drawn":
            assert e["reason"] or e["status"] == "drawn empty", e
    assert {e["v5_title"] for e in inv if e["status"] == "drawn empty"} == EMPTY_ON_FIXTURE
    assert not [e for e in inv if e["status"] == "drawn without chart"], \
        [e["v5_title"] for e in inv if e["status"] == "drawn without chart"]


def test_main_path_sits_at_its_anchor_and_the_rest_in_the_appendix(chapters):
    import ars_chapters
    prs = chapters["prs"]
    titles = [_title(s) for s in prs.slides]
    debit = next(i for i, t in enumerate(titles) if t.startswith("Debit Card Review"))
    hero = titles.index("The Campaign Hero")
    assert hero < debit, "the campaign main path goes before Aaron's debit section"
    kpis = titles.index("Operational KPIs")
    ti = titles.index("Transaction Intelligence")
    assert kpis < ti < next(i for i, t in enumerate(titles) if t.startswith("Reg E Review"))
    takeaways = next(i for i, t in enumerate(titles) if t.startswith("ARS Key Takeaways"))
    assert titles.index("Scorecard") < takeaways
    appendix = next(i for i, t in enumerate(titles) if t == "Appendix")
    for chapter, (title, _) in ars_chapters.APPENDIX_TITLES.items():
        if any(e["chapter"] == chapter and e["cut"] == "appendix" and e["status"].startswith("drawn")
               for e in chapters["inventory"]):
            assert titles.index(title) > appendix, title
    assert len(prs.slides) == chapters["n_before"] + len(chapters["made"]) + len(chapters["ti_made"])


def test_every_drawn_slide_has_a_source_note(chapters):
    import ars_chapters
    dividers = {t for t, _ in ars_chapters.APPENDIX_TITLES.values()}
    for s in chapters["made"]:
        t = _title(s)
        if t in dividers:
            continue
        note = s.notes_slide.notes_text_frame.text
        assert note.startswith("Source: ODD extract 1441 Synthetic Bank"), t


def test_the_sidecar_has_no_conflicts(chapters):
    assert chapters["log"].conflicts() == []


def test_the_deck_passes_the_validator_after_the_16pt_floor(chapters):
    from pptx import Presentation
    import validate_deck as V
    prs = Presentation(str(chapters["path"]))
    made_titles = {_title(s) for s in chapters["made"]}
    ours = {i for i, s in enumerate(prs.slides, 1) if _title(s) in made_titles}
    rules = [V.single_line_overflow_findings, V.geometry_findings, V.text_collision_findings,
             V.autofit_findings, V.text_rule_findings, V.pill_wrap_findings, V.claim_consistency_findings, V.table_label_fit_findings]
    fails = [f for rule in rules for f in rule(prs) if f[0] == "FAIL" and f[1] in ours]
    fails += [f for f in V.source_note_findings(str(chapters["path"]), prs) if f[0] == "FAIL" and f[1] in ours]
    assert fails == []


def test_no_banned_word_survives_the_house_words_pass(chapters):
    import validate_deck as V
    for s in chapters["made"]:
        text = " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame).lower()
        for w in V.BANNED:
            assert w not in text.split() and f" {w} " not in f" {text} ", (_title(s), w)


def test_what_follows_a_table_is_pushed_below_it(tmp_path):
    """v5 positions a KPI strip from its 0.32in rows; at 16pt the rows are taller, and the
    Per-offer Summary shipped its note over its tiles on the first fixture run."""
    from pptx import Presentation
    from pptx.util import Emu
    import ars_layout as A
    prs = Presentation(str(REPO / "templates" / "ars_template.pptx"))
    s = prs.slides.add_slide(prs.slide_layouts[6])
    rows = [["Offer", "Mailed", "Resp"]] + [[f"Wave {i}", "1,000", "100"] for i in range(8)]
    A._table(s, rows, 0.5, 1.72, 12.2, col_widths=[4, 4, 4], size=10)
    A._text(s, 0.52, 1.72 + 0.32 * 9 + 0.05, 12.2, 0.28, "latest 8 of 12 offers", size=10)
    A._kpi(s, 0.5, 1.72 + 0.32 * 9 + 0.4, 2.8, "Net gain", "$3/mo", "vs control")
    table = next(sh for sh in s.shapes if sh.has_table)
    table_bottom = Emu(table.top).inches + Emu(table.height).inches
    tile = next(sh for sh in s.shapes if sh.shape_type == 1)
    tile_top = Emu(tile.top).inches
    note = next((sh for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.startswith("latest")), None)
    assert tile_top >= table_bottom - 0.06
    if note is not None:                                   # drawn: below the table, clear of the tile
        assert Emu(note.top).inches >= table_bottom - 0.06
        assert Emu(note.top).inches + Emu(note.height).inches <= tile_top + 0.06
    else:                                                  # or yielded to the speaker note
        import ti_layout as L
        assert any(n.startswith("latest") for n in L.NOTES.get(id(s), []))


def test_cut_main_keeps_the_main_path_only(odd_csv, tmp_path):
    import ars_chapters
    m, txn = _metrics(odd_csv, tmp_path)
    built = _build(m, txn, tmp_path, cut="main", with_ti=False)
    titles = [_title(s) for s in built["prs"].slides]
    assert not any(t in titles for t, _ in ars_chapters.APPENDIX_TITLES.values())
    assert all(e["cut"] == "main" or e["status"] != "drawn" for e in built["inventory"])


def test_the_slides_are_opt_in():
    src = (REPO / "build" / "ars_pipeline" / "build_ars_gen.py").read_text(encoding="utf-8")
    assert 'os.environ.get("RPE_ANALYSIS_SLIDES") == "1"' in src
    assert "add_ars_chapters" in src and "_MODULE_NOTED.extend(_made2)" in src


def test_the_golden_deck_passes_the_gate_with_the_chapters_on():
    """The golden chain with both flags on: build_ars_gen runs the engine, reconciles, adds the
    chapters, and test_golden_deck's validator and sidecar assertions hold. The slide-count
    tests there pin the DEFAULT deck and run without the flags."""
    env = dict(os.environ, RPE_ANALYSIS="1", RPE_ANALYSIS_SLIDES="1")
    r = subprocess.run([sys.executable, "-m", "pytest", str(REPO / "tests" / "test_golden_deck.py"), "-q",
                        "-p", "no:cacheprovider", "-k", "validate or sidecar"],
                       cwd=str(REPO), env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-1000:]
