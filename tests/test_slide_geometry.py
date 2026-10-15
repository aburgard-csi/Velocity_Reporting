"""slide_geometry — one per-title layout contract for all three programs.

CLAUDE.md rule 2: a layout defect is fixed in the geometry contract, never by
hand-editing a deck. Only ARS had a contract, which is why ICS and MRPC layout
fixes kept arriving as one-off per-deck commits. The module is now at build/
level and every builder calls it.
"""
import os
import re
import pytest
from pptx import Presentation
from pptx.util import Inches
import slide_geometry as sg

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(REPO, "templates")
NUDGE = Inches(0.5)   # enough to move a shape out of every rule's target


def geometry(prs):
    return [[(sh.shape_id, sh.left, sh.top, sh.width, sh.height) for sh in s.shapes]
            for s in prs.slides]


def changed_slides(name):
    """Slides a rule acts on, measured from a DELIBERATELY WRONG starting geometry.

    This used to load the shell and count what `apply()` moved, which silently
    depended on the shells being non-conformant. On 2026-09-11 the contract was
    applied to `ars_template.pptx` and saved — the shells had never had it, so
    they failed rules every built deck passed — and this read 0 and called it
    "an ARS rule stopped matching". A conformant shell is the goal, not a defect.

    Nudging every shape first separates the two questions. What it asks now is
    whether the rules still FIRE — which is what the canary was ever for — and
    the answer no longer moves when a shell is brought up to date.
    """
    p = Presentation(os.path.join(TPL, f"{name}_template.pptx"))
    for s in p.slides:
        for sh in s.shapes:
            if sh.left is not None:
                sh.left = sh.left + NUDGE
            if sh.top is not None:
                sh.top = sh.top + NUDGE
    before = geometry(p)
    sg.apply(p)
    return sum(1 for a, b in zip(before, geometry(p)) if a != b)


def test_contract_acts_on_ars():
    """If this goes to zero, an ARS rule stopped matching its slide."""
    assert changed_slides("ars") > 0


def test_the_ars_shell_already_satisfies_the_contract():
    """The shipped shell is what the gate validates, and the builders apply the
    contract — so a shell that needs it is a shell that fails rules no built deck
    fails. That is exactly how the reworded Reg E sentence left both shells at
    1 FAIL while every deck passed (2026-09-11). Applying it must be a no-op."""
    p = Presentation(os.path.join(TPL, "ars_template.pptx"))
    before = geometry(p)
    sg.apply(p)
    assert geometry(p) == before, "ars_template.pptx is behind the geometry contract"


def test_the_before_after_charts_run_the_full_width():
    """Aaron, 2026-10-15 (Brooks Bank): "both charts could be wider on this slide". Both
    before/after pairs get the full 12.3in width, centered, at the image's own aspect, or the
    4.0in height cap when the image is squarer (the shell's placeholder is)."""
    p = Presentation(os.path.join(TPL, "ars_template.pptx"))
    seen = 0
    for s in p.slides:
        for sh in s.shapes:
            if sh.left is not None:
                sh.left = sh.left + NUDGE
                sh.top = sh.top + NUDGE
    sg.apply(p)
    for s in p.slides:
        t = next((sh.text_frame.text.strip().split("\n")[0] for sh in s.shapes
                  if sh.has_text_frame and sh.text_frame.text.strip()), "")
        if not t.startswith("Responder Activity: Before vs After"):
            continue
        seen += 1
        pic = [sh for sh in s.shapes if sh.shape_type == 13 and sh.width > Inches(3)][0]
        w, h = pic.width / 914400, pic.height / 914400
        assert abs(pic.top / 914400 - 2.0) < 0.01
        assert abs(w - 12.3) < 0.01 or abs(h - 4.0) < 0.01
        assert abs((pic.left / 914400) + w / 2 - 13.333 / 2) < 0.02, "centered"
        assert h <= 4.0 + 1e-6 and pic.top / 914400 + h < 6.14
    assert seen == 2


@pytest.mark.parametrize("program", ["ics", "mrpc"])
def test_contract_is_inert_on_other_programs_today(program):
    """Every rule is keyed on an ARS title, so ICS/MRPC are untouched.

    This is not a rule that they MUST stay untouched — it records that the seam
    is safe to call. When an ICS or MRPC rule is added, update this test rather
    than routing around the contract.

    Checked against perturbed geometry too, so it says "no rule fires here",
    not merely "these shells happen to be in the right place already".
    """
    assert changed_slides(program) == 0


def test_apply_is_idempotent():
    """Running the contract twice must not drift the geometry."""
    p = Presentation(os.path.join(TPL, "ars_template.pptx"))
    sg.apply(p)
    once = geometry(p)
    sg.apply(p)
    assert geometry(p) == once


@pytest.mark.parametrize("path", [
    "build/ars_pipeline/build_ars_gen.py",
    "build/ics_pipeline/build_ics_gen.py",
    "build/mrpc_pipeline/build_mrpc_gen.py",
])
def test_every_builder_calls_the_contract(path):
    src = open(os.path.join(REPO, path), encoding="utf-8").read()
    assert re.search(r"slide_geometry[.\s]*\n?\s*.*apply\(", src) or \
           "slide_geometry.apply(" in src, f"{path} does not apply the geometry contract"


@pytest.mark.parametrize("path", [
    "build/ics_pipeline/build_ics_gen.py",
    "build/mrpc_pipeline/build_mrpc_gen.py",
])
def test_contract_runs_before_fit_layout(path):
    """fit_layout clamps what the contract positions, so order matters."""
    src = open(os.path.join(REPO, path), encoding="utf-8").read()
    assert src.index("slide_geometry.apply(") < src.index("fit_layout.fit(")


def test_there_is_only_one_geometry_module():
    """A second copy would give 'fix the contract' two places to be fixed."""
    hits = []
    for root, _, files in os.walk(os.path.join(REPO, "build")):
        for f in files:
            if f == "slide_geometry.py":
                hits.append(os.path.join(root, f))
    assert len(hits) == 1, f"more than one geometry contract: {hits}"
