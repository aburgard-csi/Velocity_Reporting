"""The analyses on the layered competition figures (ti/transaction_intelligence/competition_layers_modules.py).
Synthetic matched card rows only: each analysis is pinned to figures worked out by hand.

    python -m pytest tests/test_ti_competition_layers_modules.py -q
"""
import pathlib
import sys

import pandas as pd
import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from ti.transaction_intelligence import competition_layers as CL  # noqa: E402
from ti.transaction_intelligence import competition_layers_modules as M  # noqa: E402
from test_ti_competition_layers import make_book  # noqa: E402

END = pd.Timestamp("2026-10-31")
ROWS = [  # acct, date, amount, rail, institution, tier
    ("A", "2026-03-05", 100.0, "SIG", "Maple", CL.LOCAL), ("A", "2026-10-20", 100.0, "SIG", "Maple", CL.LOCAL),
    ("A", "2026-10-21", 800.0, "PIN", None, None), ("A", "2026-10-22", 30.0, "SIG", "Chase", CL.NATIONAL),
    ("B", "2026-06-10", 200.0, "SIG", "Maple", CL.LOCAL), ("B", "2026-07-01", 300.0, "SIG", None, None),
    ("C", "2026-09-15", 50.0, "SIG", "Chase", CL.NATIONAL), ("C", "2026-10-25", 50.0, "SIG", "Chase", CL.NATIONAL),
    ("C", "2026-10-26", 400.0, "SIG", None, None)]
SETS = {"g1": {"A", "B"}, "g2": {"C"}}


def _sub():
    d = pd.DataFrame(ROWS, columns=["acct", "date", "amt", "type", "inst", "tier"])
    d["date"] = pd.to_datetime(d["date"])
    d["core"], d["key"], d["ambig"] = d["inst"], None, False
    return d


@pytest.fixture()
def sub():
    return _sub()


@pytest.fixture()
def matched(sub):
    return sub[sub["inst"].notna()]


def test_the_trend_reconciles_to_the_card_dollars_and_reads_pin_and_competitor_share(sub):
    rows = M.trend(sub, SETS)
    whole = [r for r in rows if r["group"] == "all"]
    assert sum(r["dollars"] for r in whole) == round(sub["amt"].sum())
    assert [r["month"] for r in whole] == ["2026-03", "2026-06", "2026-07", "2026-09", "2026-10"]
    oct_ = next(r for r in whole if r["month"] == "2026-10")
    assert oct_["active"] == 2 and oct_["dollars"] == 100 + 800 + 30 + 50 + 400
    assert oct_["pin_pct"] == round(800 / 1380 * 100, 1) and oct_["competitor_dollars"] == 100 + 30 + 50
    g1 = [r for r in rows if r["group"] == "g1"]
    assert sum(r["dollars"] for r in g1) == round(sub[sub["acct"].isin(SETS["g1"])]["amt"].sum())


def test_movement_counts_new_stopped_and_live_relationships(matched):
    inst, tiers = M.movement(matched, END)
    by = {r["inst"]: r for r in inst}
    assert by["Maple"] == {"inst": "Maple", "tier": CL.LOCAL, "relationships": 2, "new_90": 0, "stopped_90": 1, "live_30": 1}
    assert by["Chase"]["relationships"] == 2 and by["Chase"]["new_90"] == 2 and by["Chase"]["stopped_90"] == 0
    assert {r["tier"]: r["net_90"] for r in tiers} == {CL.LOCAL: -1, CL.NATIONAL: 2}


def test_depth_bands_split_relationships_by_the_share_of_the_accounts_card_dollars(sub, matched):
    total = sub.groupby("acct")["amt"].sum()
    tiers, inst = M.depth(matched, total)
    local = next(r for r in tiers if r["tier"] == CL.LOCAL)
    assert (local["under 5%"], local["5-20%"], local["20%+"], local["relationships"]) == (0, 1, 1, 2)      # 200/1030, 200/500
    nat = next(r for r in tiers if r["tier"] == CL.NATIONAL)
    assert (nat["under 5%"], nat["20%+"], nat["heavy_pct"]) == (1, 1, 50.0)                               # 30/1030, 100/500
    assert {r["inst"]: r["heavy"] for r in inst} == {"Maple": 1, "Chase": 1}


def test_institutions_per_account_cover_every_active_account(matched):
    rows = M.multi(matched, {"A", "B", "C"}, SETS)
    whole = {r["institutions"]: r["pct"] for r in rows if r["group"] == "all"}
    assert whole == {"0": 0.0, "1": 66.7, "2": 33.3, "3+": 0.0}
    assert sum(r["accounts"] for r in rows if r["group"] == "g1") == 2


def test_recency_bands_by_when_each_relationship_was_last_paid(matched):
    rows = {r["tier"]: r for r in M.recency(matched, END)}
    assert rows[CL.LOCAL]["live (30d)"] == 1 and rows[CL.LOCAL]["quiet (91-180d)"] == 1
    assert rows[CL.NATIONAL]["live (30d)"] == 2 and rows[CL.NATIONAL]["relationships"] == 2


def test_distance_bands_hold_every_institution_once():
    rows = [{"inst": "a", "accounts": 5, "dollars": 100, "nearest_mi": 1.0}, {"inst": "b", "accounts": 2, "dollars": 50, "nearest_mi": 40.0},
            {"inst": "c", "accounts": 9, "dollars": 900, "nearest_mi": None}]
    out = {r["band"]: r for r in M.distance(rows)}
    assert out["0-5 mi"]["dollars"] == 100 and out["25-50 mi"]["relationships"] == 2 and out["no branch near"]["dollars"] == 900
    assert sum(r["institutions"] for r in out.values()) == 3


def test_winback_counts_heavy_live_relationships_only_in_the_nearby_tiers(matched):
    assert M.winback(matched, pd.Series({"A": 500.0, "B": 500.0, "C": 500.0}), SETS, END) == [
        {"inst": "Maple", "tier": CL.LOCAL, "heavy_live": 1, "live": 1, "accounts": 2, "by_group": {"g1": 1, "g2": 0}}]
    assert M.winback(matched, matched.groupby("acct")["amt"].sum() * 100, SETS, END) == []      # nobody is heavy


def test_attrition_compares_closure_of_accounts_that_paid_a_competitor_with_those_that_did_not(matched):
    closed = pd.Series([pd.Timestamp("2026-08-15")], index=["B"])
    rows = {r["exposed_to"]: r for r in M.attrition(matched, {"A", "B", "C"}, closed, END - pd.DateOffset(months=6), END)}
    any_ = rows["ANY depository competitor"]
    assert (any_["exposed"], any_["closed"], any_["unexposed"], any_["unexposed_closure_pct"]) == (1, 0, 2, 50.0)
    assert any_["relative_risk"] == 0.0


def test_branch_labels_never_carry_a_decimal_and_a_missing_branch_is_named():
    assert [M.branch_label(v) for v in (309.0, "309.0", "309", 3, float("nan"), None, "nan", "Main")] == \
        ["309", "309", "309", "3", "(no branch)", "(no branch)", "(no branch)", "Main"]


def test_the_branch_table_reads_competitor_share_and_closure_per_branch(matched):
    branch = pd.Series(["3.0", "3.0", float("nan")], index=["A", "B", "C"])
    closed = pd.Series([pd.Timestamp("2026-08-15")], index=["B"])
    rows = M.branches(matched, {"A", "B", "C"}, branch, closed, END, min_accounts=1)
    by = {r["branch"]: r for r in rows}
    assert set(by) == {"3", "(no branch)"}
    assert by["3"]["accounts"] == 2 and by["3"]["any_pct"] == 100.0 and by["3"]["closed_12m"] == 1 and by["3"]["closure_pct"] == 50.0
    assert by["(no branch)"]["national_pct"] == 100.0


def test_nearby_branches_carry_the_tier_of_the_institution_the_card_spending_shows():
    pts = [(35.00, -100.00), (35.05, -100.05)]
    got = M.nearby(make_book(), pts, 25.0, {"Maple Leaf": CL.LOCAL})
    by = {r[2]: r[3] for r in got}
    assert by["Maple Leaf"] == CL.LOCAL and by["Riverbend Bank"] is None and "Lakeshore Bank" not in by


class _Lenses:
    key_column = "Acct"


def test_compute_returns_every_analysis_and_says_what_it_could_not_compute(sub, matched):
    parts = (sub, matched, {"A", "B", "C"}, SETS)
    inst_rows = [{"inst": "Maple", "tier": CL.LOCAL, "accounts": 2, "dollars": 400, "nearest_mi": 1.2}]
    frame = pd.DataFrame({"Acct": ["A", "B", "C"], "Branch": [3.0, 3.0, 4.0],
                          "Date Closed": [None, "08/15/2026", None]})
    figs, warns = M.compute(parts, frame, _Lenses(), END, make_book(), [(35.0, -100.0)], 25.0, inst_rows)
    assert not warns
    for k in ("cl_trend", "cl_movement", "cl_tier_movement", "cl_depth_tiers", "cl_depth_institutions", "cl_multi", "cl_recency",
              "cl_distance", "cl_winback", "cl_attrition", "cl_branches", "cl_map"):
        assert k in figs, k
    assert figs["cl_map"]["client"] == [[35.0, -100.0]] and figs["cl_map"]["radius"] == 25.0
    figs2, warns2 = M.compute(parts, pd.DataFrame({"Acct": ["A"]}), _Lenses(), END, None, [], 25.0, inst_rows)
    assert "cl_attrition" not in figs2 and "cl_branches" not in figs2 and "cl_map" not in figs2
    assert any("Date Closed" in w for w in warns2)


def test_nothing_matched_says_so():
    figs, warns = M.compute((_sub(), _sub().iloc[0:0], set(), {}), None, _Lenses(), END, None, [], 25.0, [])
    assert figs == {} and "no institution matched" in warns[0]
