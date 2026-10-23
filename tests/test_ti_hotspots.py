# Ported from ARS v5 02-Scripts/tests/test_hotspots.py at a491b5c (James Gilmore); logic unchanged.
"""Attrition x competition per branch -- the join, and what it refuses to claim.

    python -m pytest tests/test_hotspots.py -q

Both halves existed and never shared an axis, so nobody could ask whether the
branch we lose accounts at is also the branch we leak money at.

The risk in a section like this is not arithmetic, it is overclaiming: a
coefficient over four branches is a shape, not a finding, and a join that
silently matches nothing would read as "no relationship" when it actually
means the two tables name branches differently. Both are pinned here.
"""
import pathlib
import sys

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.core.periods import Month                       # noqa: E402
from ti.transaction_intelligence import hotspots        # noqa: E402

ANCHOR = Month(2026, 8)


def _odd(spec):
    """spec: {branch: (n_open, n_closed_in_window)} -> an ODD-shaped frame."""
    branch, opened, closed = [], [], []
    for name, (n_open, n_closed) in spec.items():
        for _ in range(n_open):
            branch.append(name); opened.append("2015-01-01"); closed.append(None)
        for _ in range(n_closed):
            branch.append(name); opened.append("2015-01-01"); closed.append("2026-03-15")
    return pd.DataFrame({"Branch": branch, "Date Opened": opened,
                         "Date Closed": closed})


def _comp(spec):
    """spec: {branch: leak_pct} -> competition's comp_by_branch rows."""
    return [[name, 200, int(2 * pct), pct, 50_000, 250, "Big National"]
            for name, pct in spec.items()]


def _run(odd, comp_rows):
    warnings = []
    out = hotspots.compute(odd, comp_rows, ANCHOR, None, warnings.append)
    return out, warnings


# six branches whose closure rate and leakage move together
ALIGNED_ODD = {"A": (400, 60), "B": (400, 50), "C": (400, 40),
               "D": (400, 30), "E": (400, 20), "F": (400, 10)}
ALIGNED_LEAK = {"A": 40.0, "B": 34.0, "C": 28.0,
                "D": 22.0, "E": 16.0, "F": 10.0}


def test_the_two_chapters_join_on_branch():
    out, _ = _run(_odd(ALIGNED_ODD), _comp(ALIGNED_LEAK))
    rows = out["hot_by_branch"]
    assert len(rows) == 6
    assert out["hot_branches_joined"] == 6
    assert out["hot_branches_unjoined"] == 0
    assert out["hot_by_branch_columns"][0] == "branch"


def test_a_real_association_is_found_and_named():
    out, _ = _run(_odd(ALIGNED_ODD), _comp(ALIGNED_LEAK))
    assert out["hot_rank_correlation"] > 0.9, out.get("hot_rank_correlation")
    assert "strong" in out["hot_rank_correlation_basis"]
    assert out["hot_rank_correlation_n"] == 6


def test_an_inverse_association_is_reported_as_such():
    """Where we lose accounts is NOT where we leak -- a real, different answer."""
    inverse = {"A": 10.0, "B": 16.0, "C": 22.0,
               "D": 28.0, "E": 34.0, "F": 40.0}
    out, _ = _run(_odd(ALIGNED_ODD), _comp(inverse))
    assert out["hot_rank_correlation"] < -0.9, out.get("hot_rank_correlation")


def test_no_correlation_is_claimed_on_too_few_branches():
    """Four branches is a shape, not a finding. The table still prints."""
    thin = {k: v for k, v in list(ALIGNED_ODD.items())[:4]}
    out, warnings = _run(_odd(thin), _comp(
        {k: ALIGNED_LEAK[k] for k in thin}))
    assert out["hot_by_branch"], "the per-branch table should still be reported"
    assert "hot_rank_correlation" not in out
    assert any("no correlation is claimed" in w for w in warnings), warnings


def test_a_join_that_matches_nothing_says_so_rather_than_reading_as_no_effect():
    """The failure that would look like a finding: two tables naming branches
    differently produce an empty overlay, which must not read as 'no link'."""
    out, warnings = _run(_odd(ALIGNED_ODD),
                         _comp({"Harbor": 40.0, "Main Street": 10.0}))
    assert "hot_by_branch" not in out
    assert any("not naming branches the same way" in w for w in warnings), warnings


def test_the_both_above_median_quadrant_is_the_actionable_one():
    out, _ = _run(_odd(ALIGNED_ODD), _comp(ALIGNED_LEAK))
    both = out["hot_both_above_median"]
    assert set(both) == {"A", "B", "C"}, both
    assert len(out["hot_medians"]) == 2


def test_missing_inputs_decline_rather_than_emitting_an_empty_section():
    for odd, comp in ((None, _comp(ALIGNED_LEAK)),
                      (_odd(ALIGNED_ODD), None),
                      (_odd(ALIGNED_ODD), [])):
        out, warnings = _run(odd, comp)
        assert out == {}, out
        assert warnings, "declining silently hides why the section is absent"


def test_neither_side_is_recomputed_here():
    """Leak figures must pass through from competition untouched -- if this
    section ever disagrees with the competition chapter it is a join bug."""
    comp_rows = _comp(ALIGNED_LEAK)
    out, _ = _run(_odd(ALIGNED_ODD), comp_rows)
    by_name = {r[0]: r for r in out["hot_by_branch"]}
    for row in comp_rows:
        name, accounts, _with, pct, _dollars, per_acct, top = row
        assert by_name[name][4] == accounts
        assert by_name[name][5] == pct
        assert by_name[name][6] == per_acct
        assert by_name[name][7] == top
