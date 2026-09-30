"""James's v5 transaction chapter drawn by Aaron's rules, opt-in (RPE_ANALYSIS_SLIDES=1) (2026-09-30).

The 34 v5 builders (engine/deck/txn_*.py) draw through ti_chapter's helpers onto the ARS
template shell. On the synthetic ODD plus a small zipped transaction file: every builder is
accounted for in the inventory (drawn, or skipped with the data reason); the main path sits
before "Reg E Review" under a cloned section divider and the rest lands in the appendix under
its own; every drawn slide has a source note; every tile is in the sidecar once; the deck
passes the validator's text, geometry, collision, overflow, autofit and source rules at 0 FAIL
after restyle_fonts has floored it to 16pt; a bank never reads "members".
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

# The fixture cannot produce every input the chapter reads; each of these declines for a
# stated data reason and is listed in the inventory as skipped, never dropped silently.
CORE = {"How the money moves", "Where the money goes", "Their financial life", "Who they pay",
        "Who competes for our members", "How members spend", "The book, narrowed",
        "How deep the leakage runs", "Where the field sits", "Card spend by category",
        "Who leads each product", "The responder profile", "What the banker actually opens"}


def _txn(odd_csv, tmp, overrides=None):
    pd = pytest.importorskip("pandas")
    import run_analysis as RA
    ids = pd.read_csv(odd_csv, skiprows=4, dtype=str, usecols=["Acct Number"])["Acct Number"].dropna().tolist()[:120]
    txn_dir = _write_txn_zip(tmp / "Txn Files" / "1441", ids)
    RA.run(odd_csv, "1441", "2026.08", out_dir=tmp / "out", txn=True, txn_dirs=[txn_dir], tables=None,
           overrides=overrides or {"LocalCompetitors": {"Capital One": ["CAPITAL ONE"]}})
    return json.loads((tmp / "out" / "txn_metrics.json").read_text(encoding="utf-8"))


def _build(txn, tmp, client_name="Synthetic Bank", cut=None):
    from pptx import Presentation
    import figures
    import restyle_fonts
    import ti_chapter
    prs = Presentation(str(REPO / "templates" / "ars_template.pptx"))
    n_before = len(prs.slides)
    (tmp / "assets").mkdir(exist_ok=True)
    figures.log.__init__()
    ctx = {"as_of_long": "July 2026", "assets": str(tmp / "assets"), "txn_src": "Inputs/Txn Files/1441/",
           "client_name": client_name}
    if cut:
        ctx["cut"] = cut
    made, inventory = ti_chapter.add_ti_chapter(prs, txn, ctx)
    out = tmp / "with_chapter.pptx"
    prs.save(str(out))
    restyle_fonts.restyle(str(out))
    return {"prs": prs, "path": out, "made": made, "inventory": inventory, "n_before": n_before,
            "log": figures.log}


@pytest.fixture(scope="module")
def chapter(odd_csv, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("ti")
    return _build(_txn(odd_csv, tmp), tmp)


def _title(s):
    return next((sh.text_frame.text.strip().split("\n")[0] for sh in s.shapes
                 if sh.has_text_frame and sh.text_frame.text.strip()), "")


def test_every_v5_builder_is_accounted_for(chapter):
    import ti_chapter
    inv = chapter["inventory"]
    assert len(inv) == ti_chapter.BUILDERS
    drawn = {e["v5_title"] for e in inv if e["status"] == "drawn"}
    assert CORE <= drawn, CORE - drawn
    for e in inv:
        if e["status"] != "drawn":
            assert e["reason"], e


def test_main_path_sits_before_reg_e_and_the_rest_in_the_appendix(chapter):
    import ti_chapter
    prs = chapter["prs"]
    titles = [_title(s) for s in prs.slides]
    div = titles.index(ti_chapter.MAIN_TITLE)
    reg_e = next(i for i, t in enumerate(titles) if t.startswith("Reg E Review"))
    appx = titles.index(ti_chapter.APPX_TITLE)
    main_drawn = [ti_chapter.title_case(e["v5_title"].replace("members", "account holders"))
                  for e in chapter["inventory"] if e["cut"] == "main" and e["status"] == "drawn"]
    assert titles[div + 1:reg_e] == main_drawn
    assert appx > reg_e and appx == len(titles) - 1 - (len(chapter["made"]) - len(main_drawn) - 2)
    assert len(prs.slides) == chapter["n_before"] + len(chapter["made"])


def test_a_bank_never_reads_members(chapter):
    for s in chapter["made"]:
        text = " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame).lower()
        assert "member" not in text, _title(s)


def test_a_credit_union_keeps_members(odd_csv, tmp_path):
    import ti_chapter
    assert ti_chapter.member_term("CoastLife Credit Union") == "members"
    assert ti_chapter.member_term("Alaska Air Group FCU") == "members"
    assert ti_chapter.member_term("FNB Alaska") == "account holders"
    assert ti_chapter.wording("Who competes for our members", "members") == "Who competes for our members"


def test_every_drawn_slide_has_a_source_note_and_a_caption(chapter):
    import ti_chapter
    for s in chapter["made"]:
        t = _title(s)
        if t in (ti_chapter.MAIN_TITLE, ti_chapter.APPX_TITLE):
            continue
        note = s.notes_slide.notes_text_frame.text
        assert note.startswith("Source: Inputs/Txn Files/1441/") and "Monthly Transaction File" in note, t
        assert "Chart:" in note, t


def test_every_tile_is_in_the_sidecar_once(chapter):
    assert chapter["log"].conflicts() == []
    assert len(chapter["log"]) > 0


def test_the_deck_passes_the_validator_after_the_16pt_floor(chapter):
    from pptx import Presentation
    import validate_deck as V
    prs = Presentation(str(chapter["path"]))
    made_titles = {_title(s) for s in chapter["made"]}
    ours = {i for i, s in enumerate(prs.slides, 1) if _title(s) in made_titles}
    rules = [V.single_line_overflow_findings, V.geometry_findings, V.text_collision_findings,
             V.autofit_findings, V.text_rule_findings, V.pill_wrap_findings]
    fails = [f for rule in rules for f in rule(prs) if f[0] == "FAIL" and f[1] in ours]
    fails += [f for f in V.source_note_findings(str(chapter["path"]), prs) if f[0] == "FAIL" and f[1] in ours]
    assert fails == []


def test_the_dividers_are_the_templates_own_section_slide(chapter):
    import ti_chapter
    prs = chapter["prs"]
    like = next(s for s in prs.slides if _title(s).startswith("Debit Card Review"))
    for want in (ti_chapter.MAIN_TITLE, ti_chapter.APPX_TITLE):
        s = next(s for s in prs.slides if _title(s) == want)
        assert len(s.shapes) == len(like.shapes)
        assert max(r.font.size.pt for sh in s.shapes if sh.has_text_frame
                   for p in sh.text_frame.paragraphs for r in p.runs if r.font.size) >= 44


def test_cut_main_keeps_the_main_path_only(odd_csv, tmp_path):
    import ti_chapter
    built = _build(_txn(odd_csv, tmp_path), tmp_path, cut="main")
    titles = [_title(s) for s in built["prs"].slides]
    assert ti_chapter.APPX_TITLE not in titles
    assert all(e["cut"] == "main" or e["status"] != "drawn" for e in built["inventory"])
    assert len(built["prs"].slides) == built["n_before"] + len(built["made"])


def test_no_financial_rows_is_stated_on_one_slide(tmp_path):
    import ti_chapter
    built = _build({"txn_accounts": 100, "txn_rows": 0}, tmp_path)
    assert len(built["made"]) == 1
    assert built["inventory"][0]["status"] == "no data"
    text = " ".join(sh.text_frame.text for sh in built["made"][0].shapes if sh.has_text_frame)
    assert "no financial-services rows" in text


def test_rail_lines_are_measured_at_the_floor(tmp_path):
    """A long label keeps its note off the tile; a short one keeps it on; a label that fits no
    line is clipped visibly and given in full in the notes."""
    from pptx import Presentation
    import shapes as SH
    import ti_layout as L
    prs = Presentation(str(REPO / "templates" / "ars_template.pptx"))
    s = SH.blank_slide(prs, prs.slides[0])
    items = [("Leaking", "51,698", "of 52,025 transacting personal accounts"),
             ("Accounts in addressable categories with a competitor", "12", "note"),
             ("A label so long that it cannot possibly fit two lines of a tile at sixteen points wide", "1", "")]
    _, detail = L.rail_tiles(s, items)
    assert any(d.startswith("Leaking:") for d in detail)
    assert any(d.startswith("A label so long") for d in detail)
    texts = [sh.text_frame.text for sh in s.shapes if sh.has_text_frame]
    assert any(t.endswith("…") for t in texts)


def test_the_slides_are_opt_in():
    src = (REPO / "build" / "ars_pipeline" / "build_ars_gen.py").read_text(encoding="utf-8")
    assert 'os.environ.get("RPE_ANALYSIS_SLIDES") == "1"' in src
    assert "_MODULE_NOTED.extend(_made)" in src


def test_the_golden_deck_passes_the_gate_with_the_chapter_on():
    """The real proof: the golden chain with both flags on — build_ars_gen runs the engine,
    reconciles, adds the chapter, and test_golden_deck's own assertions (0 FAIL, sidecar
    without conflicts) hold."""
    env = dict(os.environ, RPE_ANALYSIS="1", RPE_ANALYSIS_SLIDES="1")
    r = subprocess.run([sys.executable, "-m", "pytest", str(REPO / "tests" / "test_golden_deck.py"), "-q",
                        "-p", "no:cacheprovider", "-k", "validate or sidecar or slide_count or charts"],
                       cwd=str(REPO), env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-1000:]
