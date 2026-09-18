"""Every module of the ported analysis engine imports under build/ars_pipeline/engine (2026-09-18).

The engine came from v5 as one package with relative imports. An import that only fails
when a section is first called is a section that silently reports "failed:" in a warning
list, so every module is imported here, eagerly, by name.
"""
import importlib
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
ENGINE = REPO / "build" / "ars_pipeline" / "engine"
sys.path[:0] = [str(REPO / "build" / "ars_pipeline"), str(REPO / "build")]

MODULES = sorted(
    "engine." + ".".join(p.relative_to(ENGINE).with_suffix("").parts)
    for p in ENGINE.rglob("*.py")
    if p.name != "__init__.py" and "__pycache__" not in p.parts
)


def test_the_engine_has_its_parts():
    names = set(MODULES)
    for must in ("engine.core.subsets", "engine.core.periods", "engine.core.odd_transform",
                 "engine.monthly_analysis.metrics", "engine.monthly_analysis.rege",
                 "engine.transaction_intelligence.loader", "engine.text.labels"):
        assert must in names, must
    assert not any(m.endswith((".ics", ".ics_sources", ".deposit_behaviour", ".run_v5")) for m in names)


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name):
    importlib.import_module(name)


def test_the_section_registry_has_no_ics_or_deposit_entry():
    from engine.monthly_analysis import metrics
    names = [n for n, _ in metrics.SECTIONS]
    assert "ics" not in names and "deposit_behaviour" not in names
    assert names[0] == "extract_check" and "rege" in names and "value" in names


def test_debit_and_business_are_odd_rows_readings():
    pd = pytest.importorskip("pandas")
    from engine.core import subsets
    df = pd.DataFrame({"Debit?": ["Yes", "YES", "No", "", "Y"], "Business?": ["No", "Yes", "", "yes", "B"]})
    assert list(subsets.has_debit(df)) == [True, True, False, False, False]      # "Y" is not a reading
    assert list(subsets.is_business(df)) == [False, True, False, True, False]     # "B" is not a reading


def test_no_module_carries_its_own_flag_or_rege_wording():
    """The engine reads through odd_rows; a second copy of a rule is the defect this branch exists for."""
    bad = []
    for p in ENGINE.rglob("*.py"):
        src = p.read_text(encoding="utf-8")
        if "DEBIT_TRUE" in src or "BUSINESS_TRUE" in src:
            bad.append(f"{p.name}: DEBIT_TRUE/BUSINESS_TRUE")
        if p.name == "rege.py" and ("_OUT_RE" in src or "_IN_RE" in src or "_DEF_RE" in src):
            bad.append(f"{p.name}: its own Reg E wording rule")
    assert not bad, bad
