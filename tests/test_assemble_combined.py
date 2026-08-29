"""assemble_combined — section boundaries and shell uniqueness.

This file has churned four times in ~20 commits and every defect was found in a
delivered deck, not by a test:

  * a fixed-index ARS boundary pushed "Reg E Opt-In by Account Vintage" and
    "ARS Key Takeaways" AFTER the ICS section when the ARS deck grew;
  * an orphaned agenda badge survived on two-program decks;
  * the agenda described ICS sections that a referrals-only build omits.

It sits downstream of all three pipelines, so a break here corrupts every
multi-product client at once. The repo's own templates are used as the section
decks — they are real program shells, they ship in git, and they are exactly
what the builders populate.
"""
import os, subprocess, sys
import pytest
from pptx import Presentation

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(REPO, "templates")
ASSEMBLE = os.path.join(REPO, "build", "assemble_combined.py")

ARS_T = os.path.join(TPL, "ars_template.pptx")
ICS_T = os.path.join(TPL, "ics_template.pptx")
MRPC_T = os.path.join(TPL, "mrpc_template.pptx")

SHELL_ONCE = ["Agenda", "Questions & Discussion", "Contact Us"]
ARS_TAIL_TITLES = ["Reg E Opt-In by Account Vintage", "ARS Key Takeaways"]


def titles(prs):
    out = []
    for s in prs.slides:
        t = next((sh.text_frame.text.strip().split("\n")[0]
                  for sh in s.shapes
                  if sh.has_text_frame and sh.text_frame.text.strip()), "")
        out.append(t)
    return out


def build(tmp, **kw):
    out = os.path.join(tmp, "combined.pptx")
    cmd = [sys.executable, ASSEMBLE, "--ars", ARS_T, "--out", out]
    for flag, path in kw.items():
        if path:
            cmd += [f"--{flag}", path]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)
    assert r.returncode == 0, f"assemble failed:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}"
    return Presentation(out), r.stdout


@pytest.fixture(scope="module")
def all_three(tmp_path_factory):
    return build(str(tmp_path_factory.mktemp("all3")), ics=ICS_T, mrpc=MRPC_T)


@pytest.fixture(scope="module")
def ars_ics(tmp_path_factory):
    return build(str(tmp_path_factory.mktemp("arsics")), ics=ICS_T)


@pytest.fixture(scope="module")
def ars_mrpc(tmp_path_factory):
    return build(str(tmp_path_factory.mktemp("arsmrpc")), mrpc=MRPC_T)


# ARS alone is not a combined deck — assemble_combined rejects it by design
# ("a combined deck needs at least one of --ics / --mrpc besides --ars"), so the
# matrix is the three real multi-product shapes.
ALL_COMBOS = ["all_three", "ars_ics", "ars_mrpc"]


# --- every combination assembles ------------------------------------------
@pytest.mark.parametrize("combo", ALL_COMBOS)
def test_combination_assembles(combo, request):
    prs, _ = request.getfixturevalue(combo)
    assert len(prs.slides) > 20


@pytest.mark.parametrize("combo", ALL_COMBOS)
def test_shell_slides_appear_exactly_once(combo, request):
    """The combined deck carries ONE cover, agenda, Q&A and Contact — from ARS."""
    prs, _ = request.getfixturevalue(combo)
    ts = titles(prs)
    for want in SHELL_ONCE:
        n = sum(1 for t in ts if t.startswith(want))
        assert n == 1, f"{combo}: '{want}' appears {n} times, expected 1"


@pytest.mark.parametrize("combo", ALL_COMBOS)
def test_no_duplicate_part_names(combo, request):
    """Duplicated partnames corrupt the package silently."""
    prs, _ = request.getfixturevalue(combo)
    names = [p.partname for p in prs.part.package.iter_parts()]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"{combo}: duplicated parts {dupes}"


# --- the fixed-index boundary bug -----------------------------------------
def _first_non_ars_index(ts):
    """Index of the first slide belonging to a following program section."""
    for i, t in enumerate(ts):
        if t.startswith(("Invitation Checking", "The Power of Referrals",
                         "Performance of ICS", "ICS Revenue", "MRPC ",
                         "MyRewards")):
            return i
    return len(ts)


@pytest.mark.parametrize("combo", ["all_three", "ars_ics", "ars_mrpc"])
@pytest.mark.parametrize("title", ARS_TAIL_TITLES)
def test_ars_tail_slides_stay_inside_the_ars_section(combo, title, request):
    """These two were pushed AFTER the following section by the fixed-index boundary.

    A combined deck is SUPPOSED to have ICS/MRPC content after the ARS section —
    the defect was that these two ARS slides ended up on the wrong side of that
    boundary. So the assertion is that they come BEFORE the first non-ARS slide.
    """
    prs, _ = request.getfixturevalue(combo)
    ts = titles(prs)
    if title not in ts:
        pytest.skip(f"{title} not in this template")
    assert ts.index(title) < _first_non_ars_index(ts), \
        f"{combo}: '{title}' fell after the start of the next section"


def test_ars_boundary_is_resolved_by_title_not_index(all_three):
    """The log must name the title it matched, not silently fall back."""
    _, log = all_three
    assert "ARS Key Takeaways" in log
    assert "falling back to the fixed index" not in log


# --- section ordering -----------------------------------------------------
def test_section_order_is_ars_then_ics_then_mrpc(all_three):
    """MRPC is matched on its slide titles: unlike ICS it ships no divider slide."""
    prs, _ = all_three
    ts = titles(prs)
    ics = next((i for i, t in enumerate(ts) if t.startswith("Invitation Checking")), None)
    mrpc = next((i for i, t in enumerate(ts) if t.startswith("MRPC ")), None)
    assert ics is not None, "no ICS section found"
    assert mrpc is not None, "no MRPC section found"
    assert ics < mrpc, "ICS section must precede MRPC"


def test_contact_is_the_last_non_appendix_shell_slide(all_three):
    prs, _ = all_three
    ts = titles(prs)
    contact = next(i for i, t in enumerate(ts) if t.startswith("Contact Us"))
    qa = next(i for i, t in enumerate(ts) if t.startswith("Questions & Discussion"))
    assert qa < contact, "Q&A must precede Contact"


# --- every program gets a divider -----------------------------------------
PROGRAM_DIVIDER = {"ARS": "Account Revenue Solution",
                   "ICS": "Invitation Checking",
                   "MRPC": "MyRewards Premium Cards"}


@pytest.mark.parametrize("combo,programs", [
    ("all_three", ["ARS", "ICS", "MRPC"]),
    ("ars_ics", ["ARS", "ICS"]),
    ("ars_mrpc", ["ARS", "MRPC"]),
])
def test_every_present_program_has_a_divider(combo, programs, request):
    """Every program section opens with its divider.

    The templates are used as section decks here, and the MRPC template has no
    Executive Summit slide — so its divider sits at index 2, where the old
    positional rule (drop 1 and 2) deleted it. A BUILT deck always has a summit
    slide, so no delivered deck was affected; resolving by meaning makes the rule
    hold for both shapes (Aaron, 2026-08-29).
    """
    prs, _ = request.getfixturevalue(combo)
    ts = titles(prs)
    for prog in programs:
        want = PROGRAM_DIVIDER[prog]
        assert any(t.startswith(want) for t in ts), \
            f"{combo}: no {prog} divider slide"


def test_divider_precedes_its_programs_content(all_three):
    prs, _ = all_three
    ts = titles(prs)
    div = next(i for i, t in enumerate(ts) if t.startswith("MyRewards Premium Cards"))
    first = next(i for i, t in enumerate(ts) if t.startswith("MRPC "))
    assert div < first, "the MRPC divider must precede MRPC content"


def test_cover_and_divider_are_told_apart_by_text():
    """They share a title; the cover carries 'Executive Review', the divider does not."""
    import assemble_combined as ac
    prs = Presentation(MRPC_T)
    slides = list(prs.slides)
    assert ac._is_cover(slides[0]), "MRPC slide 1 is the cover"
    assert not ac._is_cover(slides[1]), "MRPC slide 2 is the divider, not the cover"
    assert not ac._is_summit(slides[1], 2), "MRPC has no Executive Summit slide"
    assert 2 in ac.section_slides(slides), "the MRPC divider must survive section_slides"


def test_ars_and_ics_still_drop_cover_and_summit():
    import assemble_combined as ac
    for tpl in (ARS_T, ICS_T):
        slides = list(Presentation(tpl).slides)
        keep = ac.section_slides(slides)
        assert 1 not in keep and 2 not in keep, f"{tpl}: cover/summit must be dropped"


# --- the agenda describes only what is present ----------------------------
def agenda_text(prs):
    for s in prs.slides:
        joined = " ".join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame)
        if joined.strip().startswith("Agenda"):
            return joined
    return ""


def test_agenda_names_all_three_programs(all_three):
    a = agenda_text(all_three[0])
    for want in ("Account Revenue Solution", "Invitation Checking", "MyRewards"):
        assert want in a, f"agenda omits {want}"


def test_agenda_omits_absent_programs(ars_ics):
    """A two-program deck must not advertise a section it does not contain."""
    a = agenda_text(ars_ics[0])
    assert "Invitation Checking" in a
    assert "MyRewards" not in a, "agenda names MRPC on an ARS+ICS deck"


def test_ars_alone_is_rejected(tmp_path):
    """A single-program deck is the program deck itself, not a combined one."""
    out = os.path.join(str(tmp_path), "x.pptx")
    r = subprocess.run([sys.executable, ASSEMBLE, "--ars", ARS_T, "--out", out],
                       capture_output=True, text=True, cwd=REPO)
    assert r.returncode != 0
    assert "at least one of" in (r.stderr + r.stdout)


# --- referrals-only ICS ---------------------------------------------------
def test_referrals_only_ics_agenda_omits_workbook_sections(tmp_path):
    """A referrals-only ICS build has no ROI/financial slides; the agenda must agree."""
    import assemble_combined as ac
    src = Presentation(ICS_T)
    trimmed = tmp_path / "ics_referrals_only.pptx"
    RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    # Mirror _ics_is_referrals_only exactly: it scans EVERY shape, not just the
    # first. Trimming by first-shape title alone left the phrase behind on other
    # shapes and the trimmed deck still read as a full build.
    def carries_workbook_text(sl):
        return any(sh.has_text_frame
                   and sh.text_frame.text.strip().startswith(ac.ICS_WORKBOOK_TITLES)
                   for sh in sl.shapes)
    drop = {i for i, sl in enumerate(src.slides) if carries_workbook_text(sl)}
    assert drop, "the ICS template carries no workbook slides to remove"
    lst = src.slides._sldIdLst
    for i, sldId in reversed(list(enumerate(list(lst)))):
        if i in drop:
            src.part.drop_rel(sldId.get(RID))
            lst.remove(sldId)
    src.save(str(trimmed))
    assert ac._ics_is_referrals_only(list(Presentation(str(trimmed)).slides)), \
        "trimmed deck should read as referrals-only"

    prs, _ = build(str(tmp_path), ics=str(trimmed))
    a = agenda_text(prs)
    assert "Referral trend" in a
    assert "ROI" not in a and "financial results" not in a, \
        "agenda describes ICS sections a referrals-only build omits"


# --- unit: the pure helpers ----------------------------------------------
def test_section_slides_drops_shell_and_leading_two():
    import assemble_combined as ac
    prs = Presentation(ICS_T)
    keep = ac.section_slides(list(prs.slides))
    assert 1 not in keep and 2 not in keep, "ICS cover/Summit must be dropped"
    kept_titles = [titles(prs)[i - 1] for i in keep]
    for bad in ac.SECTION_DROP_TITLES:
        assert not any(t.startswith(bad) for t in kept_titles), f"{bad} was kept"


def test_ics_referrals_only_detection():
    import assemble_combined as ac
    full = Presentation(ICS_T)
    assert ac._ics_is_referrals_only(list(full.slides)) is False, \
        "the full ICS template carries workbook slides"


def test_mrpc_shell_titles_describe_what_they_become():
    """The shell titled two slides "Revenue to ..." and two "Key Metrics".

    build_mrpc_gen retitles all four by position — Revenue by Year, Revenue by
    Month, Card Portfolio, Key Metrics — so client decks were always correct.
    But a shell that does not describe what it becomes reads as duplicate slides
    and hides a real duplicate if one ever appears.
    """
    ts = titles(Presentation(MRPC_T))
    for want in ("MRPC Revenue by Year", "MRPC Revenue by Month",
                 "MRPC Card Portfolio", "MRPC Key Metrics"):
        n = sum(1 for t in ts if t.startswith(want))
        assert n == 1, f"mrpc_template should carry exactly one {want!r} slide, found {n}"


# --- the figure sidecar must reach the deck that actually ships ------------
def _sidecar_for(deck):
    from figures import find_sidecar
    return find_sidecar(deck)


def test_combined_deck_gets_a_merged_sidecar(tmp_path, monkeypatch):
    """build_ars_gen names its sidecar after the ARS COMPONENT, but for a
    multi-product client that component is an intermediate — the deck that ships
    is the combined one. Without carrying it across, validate_deck's FAIL-grade
    figure check silently did not run on any combined deck."""
    import json, assemble_combined as ac, figures as F
    art = tmp_path / "artifacts"; art.mkdir()
    monkeypatch.setattr(F, "_artifacts_dir", lambda: str(art))

    ars = tmp_path / "1075-2026.08-ARS-Austin Bank ARS Results.pptx"
    ars.write_text("")
    (art / (ars.name + ".figures.json")).write_text(json.dumps({"figures": [
        {"measure": "responders_latest_mailing", "value": "3,560",
         "slide": "ARS Response", "note": ""}]}))

    out = tmp_path / "1075-2026.08-ARS-ICS-MRPC-Austin Bank Results.pptx"
    p = ac.merge_figure_sidecars(str(out), [("ARS", str(ars)), ("ICS", None), ("MRPC", None)])
    assert p and os.path.basename(p) == out.name + ".figures.json"
    rows = json.load(open(p))["figures"]
    assert [r["measure"] for r in rows] == ["ARS:responders_latest_mailing"]


def test_measures_are_namespaced_by_program(tmp_path, monkeypatch):
    """Two programs using one measure name is coincidence, not identity —
    pooling them unprefixed would invent a conflict between unrelated figures."""
    import json, assemble_combined as ac, figures as F
    art = tmp_path / "artifacts"; art.mkdir()
    monkeypatch.setattr(F, "_artifacts_dir", lambda: str(art))
    paths = []
    for prog, val in (("ARS", "100"), ("MRPC", "200")):
        d = tmp_path / f"1075-{prog}.pptx"; d.write_text("")
        (art / (d.name + ".figures.json")).write_text(json.dumps({"figures": [
            {"measure": "enrollments", "value": val, "slide": prog, "note": ""}]}))
        paths.append((prog, str(d)))
    out = tmp_path / "1075-combined.pptx"
    p = ac.merge_figure_sidecars(str(out), paths + [("ICS", None)])
    rows = json.load(open(p))["figures"]
    assert sorted(r["measure"] for r in rows) == ["ARS:enrollments", "MRPC:enrollments"]

    from figures import FigureLog
    assert FigureLog.load(p).conflicts() == [], "unrelated measures must not collide"


def test_no_sidecar_anywhere_yields_none(tmp_path, monkeypatch):
    import assemble_combined as ac, figures as F
    art = tmp_path / "artifacts"; art.mkdir()
    monkeypatch.setattr(F, "_artifacts_dir", lambda: str(art))
    d = tmp_path / "x.pptx"; d.write_text("")
    assert ac.merge_figure_sidecars(str(tmp_path/"c.pptx"), [("ARS", str(d))]) is None
