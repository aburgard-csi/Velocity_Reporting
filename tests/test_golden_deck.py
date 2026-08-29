"""A whole ARS deck, built from fixtures, in one test.

Every other test here checks a piece. This runs the real chain end to end —
oddd_optimize, metrics_gen, charts_gen, build_ars_gen, restyle_fonts — on the
synthetic ODD and a synthetic workbook extract, so a regression anywhere in the
pipeline surfaces in seconds instead of in a seven-minute run over fifteen real
clients.

No client data is involved: both fixtures are invented and generated on demand.

The assertions are deliberately structural, not a hash of the output. A hash
would fail on every intended change and teach people to re-baseline it without
looking. What is pinned is what must not silently move — the deck builds at all,
it has the expected shape, its own validator passes it, and its provenance
sidecar is emitted.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys

import pytest
from pptx import Presentation

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(REPO, "tests", "fixtures")
ARSP = os.path.join(REPO, "build", "ars_pipeline")
PY = sys.executable
CLIENT, PERIOD = "9999", "2026.08"
NAME = "Union Financial"


def sh(cmd, cwd=None, stdout_to=None):
    if stdout_to:
        with open(stdout_to, "w") as out:
            r = subprocess.run([str(c) for c in cmd], stdout=out,
                               stderr=subprocess.PIPE, text=True, cwd=cwd)
    else:
        r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, cwd=cwd)
    assert r.returncode == 0, (
        f"{os.path.basename(str(cmd[1]))} failed:\n{(r.stderr or '')[-2500:]}")
    return r


@pytest.fixture(scope="module")
def deck(tmp_path_factory, odd_csv):
    """Build one ARS deck from fixtures and hand back its parts."""
    w = tmp_path_factory.mktemp("golden")
    charts = w / "charts"; charts.mkdir()
    base, lift = w / "base.json", w / "lift.json"
    metrics, oddd = w / "metrics.json", w / "oddd"

    sh([PY, os.path.join(FIXTURES, "make_base.py"), odd_csv, str(base)])
    lift.write_text("{}")                       # SM path: no Lift Matrix
    sh([PY, os.path.join(REPO, "scripts/oddd_optimize.py"), "--input", odd_csv,
        "--out", str(oddd), "--client", CLIENT, "--name", NAME])
    sh([PY, f"{ARSP}/metrics_gen.py", odd_csv, str(metrics)])
    sh([PY, f"{ARSP}/charts_gen.py", str(metrics), str(base), str(charts)])

    out = w / f"{CLIENT}-{PERIOD}-ARS-{NAME} ARS Results.pptx"
    sh([PY, f"{ARSP}/build_ars_gen.py", os.path.join(REPO, "templates/ars_template.pptx"),
        str(metrics), str(base), str(lift), str(oddd / "oddd_metrics.json"),
        str(charts), str(out), odd_csv])
    sh([PY, os.path.join(REPO, "build/restyle_fonts.py"), str(out)])
    return dict(path=str(out), dir=w, base=str(base), metrics=str(metrics),
                charts=charts, prs=Presentation(str(out)))


def titles(prs):
    return [next((sh.text_frame.text.strip().split("\n")[0] for sh in s.shapes
                  if sh.has_text_frame and sh.text_frame.text.strip()), "")
            for s in prs.slides]


# --- it builds ------------------------------------------------------------
def test_the_chain_produces_a_deck(deck):
    assert os.path.getsize(deck["path"]) > 500_000


def test_all_charts_render(deck):
    assert len(list(deck["charts"].iterdir())) == 28


def test_slide_count(deck):
    """49 for an SM-path ARS deck. If this moves, assemble_combined's section
    boundary is the next thing to check — adding two slides broke it before."""
    assert len(deck["prs"].slides) == 49


# --- it has the right shape ----------------------------------------------
@pytest.mark.parametrize("title", [
    "Product Mix & ARS Eligibility", "Excluded Accounts", "Program Overview",
    "ARS Financial Performance", "Monthly Summary — Last 12 Months",
    "Mailing Response Summary", "Reg E Opt-In by Account Vintage",
    "ARS Key Takeaways", "Questions & Discussion", "Contact Us", "Appendix",
])
def test_expected_slide_is_present(title, deck):
    assert any(t.startswith(title) for t in titles(deck["prs"])), f"missing: {title}"


def test_every_deck_carries_the_summit_slide(deck):
    """Confirmed by Aaron 2026-08-29: every results deck carries it."""
    joined = " ".join(" ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
                      for s in deck["prs"].slides)
    assert "Executive Summit" in joined


def test_no_slide_is_untitled(deck):
    blank = [i for i, t in enumerate(titles(deck["prs"]), 1) if not t]
    assert not blank, f"untitled slides: {blank}"


# --- the deck's own gate passes ------------------------------------------
def test_validate_deck_passes(deck):
    r = subprocess.run([PY, os.path.join(REPO, "validation/validate_deck.py"),
                        deck["path"], deck["base"]], capture_output=True, text=True)
    line = next((l for l in r.stdout.splitlines() if "FAIL," in l), "")
    assert line.strip().startswith("0 FAIL"), \
        "\n".join(l for l in r.stdout.splitlines() if "[FAIL" in l) or line


def test_the_figure_sidecar_is_emitted(deck):
    sys.path.insert(0, os.path.join(REPO, "build"))
    from figures import find_sidecar, FigureLog
    p = find_sidecar(deck["path"])
    assert p, "no figures.json beside the deck"
    log = FigureLog.load(p)
    assert len(log) and log.conflicts() == []


# --- no client data leaked into a fixture build --------------------------
@pytest.mark.parametrize("name", ["CoastLife", "Wellworth", "Marine", "Sugar River",
                                  "Austin", "Texas Bay", "Chickasha", "True Sky"])
def test_no_real_client_name_appears(name, deck):
    """The fixtures are invented; a real client's name here means the template
    or a builder default leaked one in."""
    prs = deck["prs"]
    joined = " ".join(" ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
                      for s in prs.slides)
    notes = " ".join(s.notes_slide.notes_text_frame.text
                     for s in prs.slides if s.has_notes_slide)
    assert name not in joined + notes
