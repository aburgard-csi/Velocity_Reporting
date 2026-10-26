# Ported from ARS v5 02-Scripts/tests/test_migration_matrix_slide.py at a491b5c (James Gilmore); logic unchanged.
"""The migration matrix is computed on every run and drawn nowhere (#245)."""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.deck import migration_slides as P            # noqa: E402
from test_ti_attrition_slides import _Harness            # noqa: E402


def test_matrix_slide_tables_then_by_now_tiers():
    h = _Harness()
    t = {"mig_tiers": ["Non-user", "1-5", "6-10", "11+"],
         "mig_matrix": [[500, 40, 10, 2], [60, 300, 50, 8], [5, 40, 200, 60], [1, 4, 30, 400]],
         "mig_up_pct": 12.0, "mig_down_pct": 9.0, "mig_same_pct": 79.0}
    assert P.tier_matrix(h, t) is None
    assert h.tables[-1][1][0] == "Non-user" and h.tables[-1][1][1] == "500"
    assert "12" in h.text() and "Non-user" in h.text()


def test_matrix_slide_skips_without_the_matrix():
    h = _Harness()
    assert P.tier_matrix(h, {}) and not h.slides
