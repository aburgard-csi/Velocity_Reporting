# Ported from ARS v5 02-Scripts/tests/test_competition_by_branch.py at a491b5c (James Gilmore); logic unchanged.
"""Competition, cut by branch -- the axis attrition already reports on.

    python -m pytest tests/test_competition_by_branch.py -q

`attrition_by_branch` and the competition section were both computed and
never shared an axis, so "does the branch we lose accounts at also leak
money, and to whom" could not be asked at all. This pins the branch cut and,
more importantly, that both sides group by the same thing.

That last part is the #47 trap. Several branch CODES can map to one display
NAME (1226 maps 14 keys onto fewer names). attrition groups by the mapped
name; if competition grouped by the raw code the two tables would not join,
and every name-keyed surface would collapse the duplicates arbitrarily.
"""
import pathlib
import sys

import pandas as pd
import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
CONFIG_DIR = __import__("ti.dictionaries", fromlist=["folder"]).folder()

import test_ti_competition as base                                           # noqa: E402
from ti.core.subsets import branch_names                                 # noqa: E402
from ti.transaction_intelligence import competition, financial_services  # noqa: E402
from ti.transaction_intelligence.lens import Lenses                      # noqa: E402

ANCHOR = pd.Timestamp("2026-07-31")


def _lenses_with_branches(codes, branch_map=None):
    """The shared fixture's lenses, plus a branch attribute per account."""
    lenses = base.make_lenses()
    ids = lenses.accounts
    attrs = lenses.attrs.copy()
    attrs["Branch"] = [codes[i] for i in ids]
    if branch_map is not None:
        attrs["Branch Name"] = branch_names(attrs["Branch"], branch_map)
    return Lenses(key_column=lenses.key_column, accounts=ids,
                  masks=lenses.masks, attrs=attrs)


def _run(lenses, min_accounts=1):
    df = base.make_frame()
    spec = competition.load_config(CONFIG_DIR, base.CLIENT_CFG)
    fin_spec = financial_services.load_patterns(CONFIG_DIR, base.CLIENT_CFG)
    fin_rows = financial_services.classify_rows(df, fin_spec)
    warnings = []
    original = competition.MIN_ACCOUNTS_FOR_BRANCH
    competition.MIN_ACCOUNTS_FOR_BRANCH = min_accounts
    try:
        m, _out = competition.compute(df, lenses, spec, fin_rows, ANCHOR, None,
                                      warnings.append, key_prefix="comp_")
    finally:
        competition.MIN_ACCOUNTS_FOR_BRANCH = original
    return m, warnings


ALL_ONE = {f"A{i}": "01" for i in range(1, 9)} | {"B1": "01"}


def test_the_branch_cut_is_reported_with_its_columns_and_basis():
    m, _ = _run(_lenses_with_branches(ALL_ONE))
    rows = m.get("comp_by_branch")
    assert rows, "no branch cut produced"
    assert m["comp_by_branch_columns"][0] == "branch"
    assert "like for like" in m["comp_by_branch_basis"]


def test_every_account_lands_in_exactly_one_branch_row():
    codes = {"A1": "01", "A2": "01", "A3": "01", "A4": "02", "A5": "02",
             "A6": "02", "A7": "03", "A8": "03", "B1": "03"}
    m, _ = _run(_lenses_with_branches(codes))
    rows = m["comp_by_branch"]
    assert sorted(r[0] for r in rows) == ["01", "02", "03"]
    # every transacting account counted once, nowhere twice
    assert sum(r[1] for r in rows) == 9


def test_codes_sharing_a_display_name_merge_to_one_row():
    """The #47 trap. Three codes, two names -> two rows, not three."""
    codes = {"A1": "01", "A2": "02", "A3": "03", "A4": "01", "A5": "02",
             "A6": "03", "A7": "01", "A8": "02", "B1": "03"}
    mapping = {"01": "Main Street", "02": "Main Street", "03": "Harbor"}
    m, _ = _run(_lenses_with_branches(codes, mapping))
    rows = m["comp_by_branch"]

    assert sorted(r[0] for r in rows) == ["Harbor", "Main Street"], rows
    main = next(r for r in rows if r[0] == "Main Street")
    assert main[1] == 6, "the two Main Street codes did not merge"


def test_the_branch_axis_joins_the_one_attrition_reports_on():
    """Both sides must name branches identically or the overlay cannot join."""
    codes = {"A1": "01", "A2": "01", "A3": "02", "A4": "02", "A5": "02",
             "A6": "02", "A7": "02", "A8": "02", "B1": "02"}
    mapping = {"01": "Main Street", "02": "Harbor"}
    m, _ = _run(_lenses_with_branches(codes, mapping))

    competition_names = {r[0] for r in m["comp_by_branch"]}
    attrition_names = set(branch_names(
        pd.Series(list(codes.values())), mapping).unique())
    assert competition_names <= attrition_names, (
        f"competition names {competition_names} are not a subset of the "
        f"attrition axis {attrition_names}")


def test_a_thin_branch_is_dropped_and_its_accounts_are_named():
    """Silently dropping them would read as 'every account is covered'."""
    codes = {"A1": "01", "A2": "01", "A3": "01", "A4": "01", "A5": "01",
             "A6": "01", "A7": "01", "A8": "01", "B1": "99"}
    m, warnings = _run(_lenses_with_branches(codes), min_accounts=5)
    rows = m["comp_by_branch"]

    assert [r[0] for r in rows] == ["01"], rows
    assert any("under 5" in w or "sit at branches" in w for w in warnings), warnings


def test_leakage_per_account_is_over_the_whole_branch():
    """Dividing by the competitor-carrying subset would make a branch with
    one heavy leaker look worse than one where everybody leaks a little."""
    m, _ = _run(_lenses_with_branches(ALL_ONE))
    row = m["comp_by_branch"][0]
    accounts, dollars, per_account = row[1], row[4], row[5]
    assert per_account == pytest.approx(round(dollars / accounts), abs=1)


# ------------------------------------------- which institutions each group pays

def test_each_lens_names_the_institutions_it_actually_pays():
    """The ranking was already computed and everything past position one was
    thrown away, so "who does ICS lose to, against the book" could not be
    asked -- only "how much".
    """
    m, _ = _run(_lenses_with_branches(ALL_ONE))
    rows = m.get("comp_institutions_by_lens")
    assert rows, "no per-lens institution ranking"

    by_lens = {r[0]: r for r in rows}
    assert "all" in by_lens
    entries = by_lens["all"][2:]
    assert entries, "the 'all' lens named no institutions"
    for inst, accounts, pct, dollars in entries:
        assert isinstance(inst, str) and inst
        assert accounts >= 1
        assert 0 <= pct <= 100
        assert dollars >= 0


def test_the_ranking_is_by_accounts_reached_not_dollars():
    """A single large payer should not outrank a name half the book pays."""
    m, _ = _run(_lenses_with_branches(ALL_ONE))
    entries = {r[0]: r[2:] for r in m["comp_institutions_by_lens"]}["all"]
    counts = [e[1] for e in entries]
    assert counts == sorted(counts, reverse=True), entries


def test_the_percentage_is_of_the_whole_group_not_of_its_leakers():
    """Otherwise every lens reads near 100% and the cut says nothing."""
    m, _ = _run(_lenses_with_branches(ALL_ONE))
    row = next(r for r in m["comp_institutions_by_lens"] if r[0] == "all")
    lens_row = next(r for r in m["comp_by_lens"] if r[0] == "all")
    accounts_in_lens = lens_row[2]
    for inst, n_acct, pct, _d in row[2:]:
        assert pct == pytest.approx(round(100 * n_acct / accounts_in_lens, 1),
                                    abs=0.2), (inst, n_acct, pct)


def test_the_basis_says_which_denominator_it_used():
    m, _ = _run(_lenses_with_branches(ALL_ONE))
    assert "not of its leakers" in m["comp_institutions_by_lens_basis"]
