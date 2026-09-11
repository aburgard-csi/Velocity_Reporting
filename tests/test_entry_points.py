"""Every entry point resolves its own siblings, and can be imported without running.

Both rules come from `scripts/promote_month.py`, which on 2026-09-11 could not run
AND could not be tested:

  * its `sys.path` insert was `~/Projects/RetailPerformanceEngine/build`, and this
    repo sits at `C:\\Projects` — so it raised ModuleNotFoundError on import;
  * it then read `sys.argv[1]` at module scope and did the whole job there, so
    importing it RAN it and an IndexError was all you got without arguments.

The second is why the first went unnoticed for so long: nothing could import the
module to check anything about it, so its combined-deck detection also sat stale
against CashPlease without a test to say so. CLAUDE.md names this hazard for
`metrics_gen`; these are the entry points where it actually costs something.
"""
import ast
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Drivers a person or a scheduled task invokes. Library modules are not listed:
# `metrics_gen` deliberately runs on import and CLAUDE.md documents that.
ENTRY_POINTS = [
    "scripts/build_month.py",
    "scripts/promote_month.py",
    "scripts/deck_status.py",
    "scripts/watch_sources.py",
    "scripts/refresh_performance_dashboard.py",
    "scripts/build_cashplease.py",
    "validation/qa_all.py",
    "validation/validate_deck.py",
]


def _src(path):
    return open(os.path.join(REPO, path), encoding="utf-8").read()


@pytest.mark.parametrize("path", ENTRY_POINTS)
def test_no_home_relative_repo_path(path):
    """`expanduser` on a repo path bakes in one machine's layout.

    `RPE_DATA_ROOT` exists precisely so no path is written into code; a sibling
    module is resolved from `__file__`, which is true everywhere.
    """
    src = _src(path)
    assert "expanduser(\"~/Projects" not in src and "expanduser('~/Projects" not in src, \
        "%s resolves the repo through the home directory" % path


@pytest.mark.parametrize("path", ENTRY_POINTS)
def test_argv_is_not_read_at_module_scope(path):
    """Importing a driver must not RUN it.

    A module that reads sys.argv at import cannot be imported by a test, so none of
    its logic can be checked — and it fails with IndexError rather than a usage
    message when someone runs it with no arguments.
    """
    tree = ast.parse(_src(path))
    bad = []
    for node in tree.body:
        # Module scope only. `ast.walk` descends INTO a FunctionDef, so walking every
        # top-level node flagged the `sys.argv[1:] if argv is None else argv` that
        # belongs inside main() — which is the correct shape, not the defect.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Subscript)
                    and isinstance(sub.value, ast.Attribute)
                    and sub.value.attr == "argv"
                    and isinstance(sub.value.value, ast.Name)
                    and sub.value.value.id == "sys"):
                bad.append(getattr(node, "lineno", "?"))
    assert not bad, "%s indexes sys.argv at module scope (line %s)" % (path, bad[0])


@pytest.mark.parametrize("path", ENTRY_POINTS)
def test_has_a_main_guard(path):
    """So the module can be imported for its functions without side effects."""
    assert '__name__ == "__main__"' in _src(path) or "__name__ == '__main__'" in _src(path), \
        "%s has no __main__ guard" % path
