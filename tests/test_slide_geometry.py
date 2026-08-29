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
import slide_geometry as sg

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(REPO, "templates")


def geometry(prs):
    return [[(sh.shape_id, sh.left, sh.top, sh.width, sh.height) for sh in s.shapes]
            for s in prs.slides]


def changed_slides(name):
    p = Presentation(os.path.join(TPL, f"{name}_template.pptx"))
    before = geometry(p)
    sg.apply(p)
    return sum(1 for a, b in zip(before, geometry(p)) if a != b)


def test_contract_acts_on_ars():
    """If this goes to zero, an ARS rule stopped matching its slide."""
    assert changed_slides("ars") > 0


@pytest.mark.parametrize("program", ["ics", "mrpc"])
def test_contract_is_inert_on_other_programs_today(program):
    """Every rule is keyed on an ARS title, so ICS/MRPC are untouched.

    This is not a rule that they MUST stay untouched — it records that the seam
    is safe to call. When an ICS or MRPC rule is added, update this test rather
    than routing around the contract.
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
    src = open(os.path.join(REPO, path)).read()
    assert re.search(r"slide_geometry[.\s]*\n?\s*.*apply\(", src) or \
           "slide_geometry.apply(" in src, f"{path} does not apply the geometry contract"


@pytest.mark.parametrize("path", [
    "build/ics_pipeline/build_ics_gen.py",
    "build/mrpc_pipeline/build_mrpc_gen.py",
])
def test_contract_runs_before_fit_layout(path):
    """fit_layout clamps what the contract positions, so order matters."""
    src = open(os.path.join(REPO, path)).read()
    assert src.index("slide_geometry.apply(") < src.index("fit_layout.fit(")


def test_there_is_only_one_geometry_module():
    """A second copy would give 'fix the contract' two places to be fixed."""
    hits = []
    for root, _, files in os.walk(os.path.join(REPO, "build")):
        for f in files:
            if f == "slide_geometry.py":
                hits.append(os.path.join(root, f))
    assert len(hits) == 1, f"more than one geometry contract: {hits}"
