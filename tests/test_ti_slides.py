"""Nine Transaction Intelligence slides, opt-in (RPE_ANALYSIS_SLIDES=1) (2026-09-18).

Built onto the ARS template shell from the synthetic ODD plus a small zipped transaction
file: nine titles present in order before "Reg E Review", every tile recorded once in the
figure sidecar, a source note on each, and no FAIL from the validator on any of the nine.
The default build is untouched: the golden deck's slide count is pinned elsewhere.
"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "build" / "ars_pipeline"), str(REPO / "build"), str(REPO / "validation")]
from test_run_analysis import _write_txn_zip  # noqa: E402

TITLES = ["How the money moves", "Where the money goes", "Their financial life", "Who they pay",
          "What leakers hold with us", "Who competes for our members", "Which competitors to work first",
          "Where the outflow goes", "How members spend"]


@pytest.fixture(scope="module")
def deck_with_ti(odd_csv, tmp_path_factory):
    pd = pytest.importorskip("pandas")
    from pptx import Presentation
    import run_analysis as RA
    import ti_slides
    import figures
    tmp = tmp_path_factory.mktemp("ti")
    ids = pd.read_csv(odd_csv, skiprows=4, dtype=str, usecols=["Acct Number"])["Acct Number"].dropna().tolist()[:120]
    txn_dir = _write_txn_zip(tmp / "Txn Files" / "1441", ids)
    r = RA.run(odd_csv, "1441", "2026.08", out_dir=tmp / "out", txn=True, txn_dirs=[txn_dir], tables=None)
    txn = json.loads((tmp / "out" / "txn_metrics.json").read_text(encoding="utf-8"))
    prs = Presentation(str(REPO / "templates" / "ars_template.pptx"))
    n_before = len(prs.slides)
    assets = tmp / "assets"
    assets.mkdir()
    figures.log.__init__()
    made = ti_slides.add_ti_slides(prs, txn, {"as_of_long": "July 2026", "assets": str(assets), "txn_src": "Inputs/Txn Files/1441/"})
    out = tmp / "with_ti.pptx"
    prs.save(str(out))
    return {"prs": prs, "path": out, "made": made, "n_before": n_before, "log": figures.log}


def _title(s):
    return next((sh.text_frame.text.strip().split("\n")[0] for sh in s.shapes
                 if sh.has_text_frame and sh.text_frame.text.strip()), "")


def test_nine_slides_in_order_before_reg_e_review(deck_with_ti):
    prs = deck_with_ti["prs"]
    assert len(prs.slides) == deck_with_ti["n_before"] + 9
    titles = [_title(s) for s in prs.slides]
    start = titles.index(TITLES[0])
    assert titles[start:start + 9] == TITLES
    assert titles[start + 9].startswith("Reg E Review")


def test_every_slide_has_a_source_note_naming_the_files(deck_with_ti):
    for s in deck_with_ti["made"]:
        note = s.notes_slide.notes_text_frame.text
        assert note.startswith("Source: Inputs/Txn Files/1441/") and "Monthly Transaction File" in note


def test_every_tile_is_in_the_sidecar_once(deck_with_ti):
    log = deck_with_ti["log"]
    assert log.conflicts() == []
    assert sum(1 for _ in log.entries()) == 27 if hasattr(log, "entries") else len(log) == 27


def test_the_golden_deck_passes_the_gate_with_the_nine_slides_on():
    """The real proof: the golden chain (oddd_optimize -> metrics_gen -> charts -> build_ars_gen
    -> validate_deck) with both flags on. build_ars_gen runs the engine, reconciles, adds the
    nine slides, and test_golden_deck's own assertions (0 FAIL, sidecar without conflicts) hold.
    A bare-template check is not enough: the validator's stale-caption rule keys on the
    template's slide positions, which inserting slides shifts."""
    import os
    import subprocess
    env = dict(os.environ, RPE_ANALYSIS="1", RPE_ANALYSIS_SLIDES="1")
    r = subprocess.run([sys.executable, "-m", "pytest", str(REPO / "tests" / "test_golden_deck.py"), "-q",
                        "-p", "no:cacheprovider", "-k", "validate or sidecar or slide_count or charts"],
                       cwd=str(REPO), env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-1000:]


def test_the_slides_are_opt_in():
    src = (REPO / "build" / "ars_pipeline" / "build_ars_gen.py").read_text(encoding="utf-8")
    assert 'os.environ.get("RPE_ANALYSIS_SLIDES") == "1"' in src
    assert "_MODULE_NOTED.extend(_made)" in src
