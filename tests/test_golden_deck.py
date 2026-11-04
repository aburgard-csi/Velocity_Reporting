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


def sh(cmd, cwd=None, stdout_to=None, env=None):
    if stdout_to:
        with open(stdout_to, "w", encoding="utf-8") as out:
            r = subprocess.run([str(c) for c in cmd], stdout=out,
                               stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", cwd=cwd, env=env)
    else:
        r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd, env=env)
    assert r.returncode == 0, (
        f"{os.path.basename(str(cmd[1]))} failed:\n{(r.stderr or '')[-2500:]}")
    return r


@pytest.fixture(scope="module")
def deck(tmp_path_factory, odd_csv):
    """Build one ARS deck from fixtures and hand back its parts."""
    return _build(tmp_path_factory.mktemp("golden"), odd_csv)


@pytest.fixture(scope="module")
def partial_deck(tmp_path_factory):
    """The same deck on an ODD whose final month carries a partial NSF/OD column — the
    Marine FCU 1539 2026.09 shape (Aaron, 2026-09-17)."""
    w = tmp_path_factory.mktemp("golden_partial")
    odd = w / "partial_odd.csv"
    sh([PY, os.path.join(FIXTURES, "make_odd.py"), str(odd), "--partial-nsf"])
    return _build(w, str(odd))


def _build(w, odd_csv):
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
    # The Contact Us card names the client's managing CSM (rpe_env.csm_contact), and 9999 is
    # on no real list: point the lookup at a synthetic list and contact row.
    (w / "csm_list.csv").write_text(f"client_id,client_name,csm\n{CLIENT},{NAME},Test CSM\n", encoding="utf-8")
    (w / "csm_contacts.csv").write_text("csm,title,company,address,office,cell,email,source\n"
                                        "Test CSM,Client Service Manager,CSI,,,(555) 010-0001,"
                                        "Test.CSM@example.com,synthetic\n", encoding="utf-8")
    env = dict(os.environ, RPE_CSM_LIST=str(w / "csm_list.csv"), RPE_CSM_CONTACTS=str(w / "csm_contacts.csv"))
    # The builder's own output is kept: it is where decisions like "revenue guarantee slide
    # skipped" are stated, and a test that reads them beats one that infers them.
    sh([PY, f"{ARSP}/build_ars_gen.py", os.path.join(REPO, "templates/ars_template.pptx"),
        str(metrics), str(base), str(lift), str(oddd / "oddd_metrics.json"),
        str(charts), str(out), odd_csv], env=env, stdout_to=str(w / "build.log"))
    sh([PY, os.path.join(REPO, "build/restyle_fonts.py"), str(out)])
    return dict(path=str(out), dir=w, base=str(base), metrics=str(metrics),
                charts=charts, prs=Presentation(str(out)))


def titles_of(slide):
    return next((sh.text_frame.text.strip().split("\n")[0] for sh in slide.shapes
                 if sh.has_text_frame and sh.text_frame.text.strip()), "")


def _build_titles(d):
    return [titles_of(s) for s in d["prs"].slides]


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
    """50 for an SM-path ARS deck (2026-11-02: the branch tables moved to the Appendix — the Take Rate by
    Branch table left the main deck, and the golden client's one page each of Take Rate by Branch, Reg E
    Opt-In by Branch and Reg E New Accounts by Branch follow the divider: -1 + 1 + 1 + 0 = one more than
    before, the all-accounts Reg E page being new). The golden client runs at 5.75 : 1, so it does NOT get a
    Revenue Guarantee slide — that one is built only below 3 : 1 (Aaron, 2026-09-22). ARS
    Financial Performance is the P&L since 2026-10-02, drawn over the template's slide of
    that name rather than added beside it, so the count did not move. If this moves,
    assemble_combined's section boundary is the next thing to check — adding two slides
    broke it before."""
    assert len(deck["prs"].slides) == 51


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
                        deck["path"], deck["base"]], capture_output=True, text=True, encoding="utf-8", errors="replace")
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


def test_contact_card_names_the_managing_csm(deck):
    """Aaron, 2026-09-16: the Contact Us card always shows the client's managing CSM."""
    s = next(s for s in deck["prs"].slides
             if any(sh.has_text_frame and sh.text_frame.text.strip() == "Contact Us" for sh in s.shapes))
    text = [sh.text_frame.text for sh in s.shapes if sh.has_text_frame]
    assert "Test CSM" in text and "555-010-0001" in text and "test.csm@example.com" in text
    assert "managing CSM Test CSM" in s.notes_slide.notes_text_frame.text


# --- the closing slide carries the cover's month (Aaron, 2026-09-17) ------
def test_questions_slide_carries_the_reporting_month(deck):
    """Every 2026.09 ARS deck read "<Client>  •  July 2026" on Questions & Discussion
    under a September cover: the builder swapped only the client name there."""
    s = next(s for s in deck["prs"].slides if titles_of(s).startswith("Questions & Discussion"))
    lines = [p.text for sh in s.shapes if sh.has_text_frame for p in sh.text_frame.paragraphs]
    assert f"{NAME}  \u2022  August 2026" in lines, lines
    sys.path.insert(0, os.path.join(REPO, "validation"))
    import validate_deck
    assert validate_deck.closing_month_findings(deck["prs"]) == []


# --- complete months only (Aaron, 2026-09-17) -----------------------------
def _slide(prs, title):
    return next(s for s in prs.slides if titles_of(s).startswith(title))


def _text(s):
    return " ".join(" ".join(sh.text_frame.text.split()) for sh in s.shapes if sh.has_text_frame)


def test_partial_month_deck_still_passes_its_gate(partial_deck):
    r = subprocess.run([PY, os.path.join(REPO, "validation/validate_deck.py"),
                        partial_deck["path"], partial_deck["base"]],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    line = next((l for l in r.stdout.splitlines() if "FAIL," in l), "")
    assert line.strip().startswith("0 FAIL"), \
        "\n".join(l for l in r.stdout.splitlines() if "[FAIL" in l) or line


def test_nsf_slide_compares_complete_months_and_says_what_was_left_out(partial_deck):
    s = _slide(partial_deck["prs"], "NSF/OD Activity")
    t = _text(s)
    assert "(Jan\u2013Jun 25 \u2192 Jan\u2013Jun 26)" in t, t        # YTD vs prior YTD (2026-10-12)
    assert "Items YTD YoY" in t and "Jul 2" not in t.split("Items YTD YoY")[1][:40], t
    assert "NSF/OD items (June 2026)" in t and "NSF/OD (June 2026)" in t, t
    assert "Jul 2026 left out: incomplete in this extract." in t, t
    notes = s.notes_slide.notes_text_frame.text
    assert "Jul 2026 is left out as incomplete in this extract" in notes, notes
    assert "Items YTD YoY compares Jan\u2013Jun 25 (" in notes and ") to Jan\u2013Jun 26 (" in notes, notes
    assert len(partial_deck["prs"].slides) == 51, "a partial month never drops a slide"


def test_spend_yoy_is_year_to_date_too(deck):
    """Aaron, 2026-10-12: "did you also update the YoY comparison for debit card spend?"
    The Swipes & Spend tile follows the NSF/OD rule: YTD against the prior YTD, caption
    naming both windows, sums in the notes."""
    import re
    s = _slide(deck["prs"], "Overall Debit Swipes")
    t = _text(s)
    assert "Spend YTD YoY (" in t and "Spend YoY (" not in t, t
    assert re.search(r"\(Jan–[A-Z][a-z]{2} \d\d → Jan–[A-Z][a-z]{2} \d\d\)", t), t
    notes = s.notes_slide.notes_text_frame.text
    assert "Spend YTD YoY compares Jan–" in notes and "year to date through the last complete month" in notes, notes


def test_nsf_slide_on_complete_data_says_nothing_was_left_out(deck):
    s = _slide(deck["prs"], "NSF/OD Activity")
    assert "left out" not in _text(s)
    assert "(Jan\u2013Jul 25 \u2192 Jan\u2013Jul 26)" in _text(s)      # YTD vs prior YTD (2026-10-12)


def test_a_comfortable_client_gets_no_revenue_guarantee_slide(deck):
    """The golden client is at 5.75 : 1. Its guarantee slide is absent BY RULE, not by
    failure (Aaron, 2026-09-22: only build it under 3 : 1), and the build log says so."""
    assert not any(t.startswith("Revenue Guarantee") for t in titles(deck["prs"]))
    log = (deck["dir"] / "build.log").read_text(encoding="utf-8", errors="replace")
    assert "revenue guarantee slide skipped" in log


def test_every_slide_of_the_golden_deck_is_in_the_slide_inventory(deck):
    """The Slide Review's ARS list is build/slide_inventory.py, the shell plus the builder's additions, never
    a deck (Aaron, 2026-10-29). The golden deck is the builder's own output: every slide it carries must be
    on that list, or the inventory has drifted from the builder."""
    sys.path.insert(0, os.path.join(REPO, "build"))
    sys.path.insert(0, os.path.join(REPO, "scripts"))
    import slide_inventory as SI
    import slide_votes as SV
    import re

    def same(t):
        # the inventory names a month and a window as placeholders; the builder writes the client's own
        t = SV.norm_title(t, NAME)
        t = re.sub(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* #", "<month>", t)
        return t
    listed = [same(r["title"]) for r in SI.inventory()["ARS"]]
    missing = []
    for s in deck["prs"].slides:
        first = SV._first_line(s)
        if not first or SV._is_shared(s, first) or SV._divider_program(s, first) or first.lower() == "appendix":
            continue
        built = same(first)
        if not any(built == t or built.startswith(t + " ") for t in listed):      # "Reg E Opt-In by Branch — Last 12 Months"
            missing.append(first)
    assert not missing, f"built but not in the inventory: {missing}"
