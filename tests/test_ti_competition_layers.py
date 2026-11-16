"""Banks and credit unions by layer and by group (ti/transaction_intelligence/competition_layers.py).

Synthetic institutions, branches, accounts and card rows only. The matcher is pinned on the
descriptions that matched wrongly or not at all in the lab runs: a power bill, a commissary, a pizza
place, a marketplace tag, an arena named after a bank; and on the real names a cut or tagged
description still has to find.

    python -m pytest tests/test_ti_competition_layers.py -q
"""
import pathlib
import sys

import pandas as pd
import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.core.market import BANK, CREDIT_UNION, Book, Branch, BranchIndex, Institution  # noqa: E402
from ti.transaction_intelligence import competition_layers as CL  # noqa: E402

CLIENT_BRANCHES = [{"lat": 35.00, "lon": -100.00}, {"lat": 35.05, "lon": -100.05}]
RECORD = {"profile": {"state": "TX"}, "branches": CLIENT_BRANCHES, "self_names": ["OWN CREDIT UNION"]}
CONFIG = {"FedDistrict": "11"}
SPEC = {"institutions": {"Chase": {"tier": "National Bank", "patterns": ["CHASE", "JPMORGAN CHASE"]},
                         "Ally": {"tier": "Digital Bank / Fintech Lender", "patterns": ["ALLY"]},
                         "Upstart": {"tier": "Digital Bank / Fintech Lender", "patterns": ["UPSTART"]},
                         "Acme Auto Finance": {"tier": "Captive Auto Finance", "patterns": ["ACME AUTO"]}},
        "false_positives": ["CHASE CENTER", "CHASE FIELD"]}


def _inst(key, name, kind, hq, branches):
    inst = Institution(key=key, name=name, fi_type=kind, city="", state=hq, zip_code="", assets_thousands=1000,
                       website=None)
    inst.branches = [Branch(inst_key=key, inst_name=name, fi_type=kind, name=f"{name} {i}", city="", state=st,
                            zip_code="", lat=lat, lon=lon, coord_source="exact") for i, (st, lat, lon) in enumerate(branches)]
    return inst


def make_book():
    insts = [
        _inst("cu1", "Maple Leaf", CREDIT_UNION, "TX", [("TX", 35.01, -100.01)]),                       # local
        _inst("b1", "Riverbend Bank", BANK, "TX", [("TX", 35.20, -100.20)]),                            # ~18 mi: local
        _inst("b2", "Prairie State Bank", BANK, "TX", [("TX", 35.60, -100.00)]),                        # ~41 mi
        _inst("cu2", "Plains Regional", CREDIT_UNION, "NM", [("NM", 34.00, -103.00)]),                  # district, far
        _inst("b3", "Lakeshore Bank", BANK, "OH", [("OH", 41.0, -82.0)]),                               # elsewhere
        _inst("b4", "Big National Bank, National Association", BANK, "NC",
              [(s, 30.0 + i, -80.0 - i) for i, s in enumerate("NC SC GA FL AL TN MS LA AR MO KS OK".split())]),
        _inst("h1", "First Heritage Bank", BANK, "TX", [("TX", 35.02, -100.00)]),                       # same name twice:
        _inst("h2", "First Heritage Bank", BANK, "OH", [("OH", 41.5, -82.5)]),                          #   one clearly nearer
        _inst("u1", "Union Savings Bank", BANK, "OH", [("OH", 41.2, -82.2)]),                           # same name twice:
        _inst("u2", "Union Savings Bank", BANK, "PA", [("PA", 40.0, -76.0)]),                           #   neither near
        _inst("i1", "Credit One Bank, National Association", BANK, "NV", [("NV", 36.0, -115.0)]),       # a card issuer
    ]
    branches = [b for i in insts for b in i.branches]
    return Book(institutions={i.key: i for i in insts}, branches=branches, index=BranchIndex(branches), unplaced=[])


@pytest.fixture(scope="module")
def built():
    cfg = CL.settings(CONFIG)
    return CL.build_matcher(make_book(), RECORD, CONFIG, SPEC, cfg)


@pytest.fixture(scope="module")
def matcher(built):
    return built[1]


def _name(matcher, text):
    hit = matcher.match(text)
    return hit[0] if hit else None


@pytest.mark.parametrize("text", [
    "ALABAMA POWER CO ONLINE PMT", "EAST BASE COMMISSARY", "FIVE STAR PIZZA 442", "SQ *MAPLE LEAF CU CAFE",
    "AUTOZONE 1380 5821 CU", "PHILLIPS 66 - CU", "RIVERBEND BANK ARENA", "RIVERBEND BANK CENTER CONC",
    "CHASE CENTER TICKETS", "OWN CREDIT UNION", "UPSTART LOAN PMT", "ACME AUTO FINANCE PMT"])
def test_the_look_alikes_and_the_out_of_scope_names_match_nothing(matcher, text):
    assert matcher.match(text) is None, text


@pytest.mark.parametrize("text, expect", [
    ("CU#MAPLE LEAF CREDIT UNIO", "Maple Leaf"), ("OBP* MAPLE LEAF FCU", "Maple Leaf"),
    ("MAPLE LEAF FEDERAL CREDIT UN", "Maple Leaf"), ("MAPLE LEAF FEDERAL CREDIT", "Maple Leaf"),
    ("RIVERBEND BANK #12 AMARILLO TX", "Riverbend Bank"), ("PLAINS REGIONAL CU LOAN PMT", "Plains Regional"),
    ("CHASE CREDIT CRD", "Chase"), ("ALLY AUTO ONLINE", "Ally")])
def test_cut_and_tagged_descriptions_find_their_institution(matcher, text, expect):
    assert _name(matcher, text) == expect


def test_a_credit_union_is_never_matched_on_a_bare_stem(matcher):
    assert matcher.match("MAPLE LEAF GARDEN CENTER") is None        # the stem alone, a venue word besides
    assert matcher.match("MAPLE LEAF") is None
    assert matcher.match("PLAINS REGIONAL AIRPORT") is None


def test_tiers_follow_the_footprint_distance_and_district(built):
    reg = built[0]
    tier = {r["name"]: r["tier"] for r in reg.values() if r["key"] != "h2"}
    assert tier["Maple Leaf"] == CL.LOCAL and tier["Riverbend Bank"] == CL.LOCAL
    assert tier["Prairie State Bank"] == CL.LOCAL_MARKET
    assert tier["Plains Regional"] == CL.REGIONAL                   # headquartered in the client's Fed district
    assert tier["Lakeshore Bank"] == CL.OTHER
    assert tier["Big National Bank, National Association"] == CL.NATIONAL      # branches in 10+ states
    assert tier["Credit One Bank, National Association"] == CL.CARD_ISSUER


def test_a_name_two_institutions_share_goes_to_the_clearly_nearer_one_else_stays_unresolved(matcher):
    near = matcher.match("FIRST HERITAGE BANK")
    assert near[0] == "First Heritage Bank" and near[2] == "h1" and near[3] is False
    far = matcher.match("UNION SAVINGS BANK")
    assert far[1] == CL.UNRESOLVED and far[3] is True


def test_dictionary_names_get_a_distance_from_the_registry_institution_they_name(built):
    reg, _m, foot, out_of_scope = built[0], built[1], built[2], built[3]
    assert "Upstart" in out_of_scope and "Acme Auto Finance" in out_of_scope and "Chase" not in out_of_scope
    assert foot == {} or all(set(v) == {"nearest_mi", "states"} for v in foot.values())


def test_a_configured_local_name_the_registry_lacks_becomes_an_institution_in_that_tier():
    cfg = CL.settings(CONFIG)
    config = dict(CONFIG, LocalCompetitors={"Harbor Light Credit Union": ["HARBOR LIGHT CU"]})
    reg, m, *_ = CL.build_matcher(make_book(), RECORD, config, SPEC, cfg)
    hit = m.match("HARBOR LIGHT CU PMT")
    assert hit is not None and hit[0] == "Harbor Light Credit Union" and hit[1] == CL.LOCAL
    assert reg["cfg:Harbor Light Credit Union"]["configured"] is True


# ---------------------------------------------------------------------------------------- the figures
class _Lenses:
    key_column = "Acct"

    def __init__(self, groups):
        self.groups = groups

    def names(self):
        return list(self.groups)

    def ids(self, name):
        return pd.Index(self.groups[name])


def _rows(spec):
    """spec: [(account, rail, date, amount, description)] -> (df, rows) as the section receives them."""
    df = pd.DataFrame(spec, columns=["primary_account_num", "transaction_type", "transaction_date", "amount", "merchant_name"])
    rows = pd.DataFrame({"core": df["merchant_name"], "is_card": df["transaction_type"].isin(["PIN", "SIG"])}, index=df.index)
    return df, rows


SPEC_ROWS = [
    ("A1", "SIG", "2026-05-10", -100.0, "CU#MAPLE LEAF CREDIT UNIO"), ("A1", "SIG", "2026-09-10", -50.0, "OBP* MAPLE LEAF FCU"),
    ("A1", "SIG", "2026-09-12", -20.0, "CORNER GROCER"), ("A1", "ACH", "2026-09-13", -999.0, "MAPLE LEAF FCU"),
    ("A2", "PIN", "2026-06-10", -200.0, "RIVERBEND BANK #12"), ("A2", "PIN", "2026-06-12", -30.0, "RIVERBEND BANK ARENA"),
    ("A3", "SIG", "2026-08-01", -300.0, "CHASE CREDIT CRD"), ("A3", "SIG", "2026-08-02", -40.0, "UNION SAVINGS BANK PMT"),
    ("A4", "SIG", "2026-07-05", -60.0, "PLAINS REGIONAL CU LOAN PMT"), ("A4", "SIG", "2026-07-06", -15.0, "ALLY AUTO ONLINE"),
    ("A4", "SIG", "2026-07-07", -25.0, "UPSTART LOAN PMT"), ("A4", "SIG", "2026-07-08", -9.0, "SMALLTOWN CREDIT UNION"),
    ("A5", "SIG", "2026-07-09", -12.0, "CORNER GROCER"),
]


@pytest.fixture(scope="module")
def figures():
    df, rows = _rows(SPEC_ROWS)
    frame = pd.DataFrame({"Acct": ["A1", "A2", "A3", "A4", "A5"], "Jun26 Resp": ["TH-10", "NU 1-4", None, None, None]})
    lenses = _Lenses({"responders": ["A1"], "mailed_nonresp": ["A2", "A3"], "not_mailed": ["A4", "A5"],
                      "personal": ["A1", "A2", "A3", "A4", "A5"]})
    warns = []
    out = CL.compute(df, rows, lenses, frame, CONFIG, pd.Timestamp("2026-10-31"), RECORD, make_book(), SPEC, warns.append,
                     base_ids={"A1", "A2", "A3", "A4", "A5"})
    return out, warns


def test_dollars_reconcile_and_only_the_card_rail_of_depository_institutions_is_counted(figures):
    out, warns = figures
    placed = sum(r["dollars"] for r in out["cl_tiers"])
    assert placed == out["cl_any"]["dollars"] == out["cl_coverage"]["placed_dollars"]
    assert placed == 100 + 50 + 200 + 300 + 40 + 60 + 15                    # no ACH row, no arena, no lender, no stem-only
    assert out["cl_base"]["accounts"] == 5
    assert any("ACH" in w for w in warns)                                    # the transfer rail is stated, not silently read


def test_accounts_do_not_add_across_tiers_and_the_any_row_is_de_duplicated(figures):
    out, _ = figures
    tier_accounts = sum(r["accounts"] for r in out["cl_tiers"])
    assert out["cl_any"]["accounts"] == 4 and tier_accounts >= out["cl_any"]["accounts"]
    assert out["cl_any"]["pct"] == 80.0


def test_groups_partition_the_base_and_the_near_responders_are_split_from_the_mailed_non_response(figures):
    out, _ = figures
    d = out["cl_base"]["groups"]
    assert d["responders"] == 1 and d["mailed_nonresp"] == 2 and d["not_mailed"] == 2
    assert d["mailed_nonresp_nu1_4"] == 1 and d["mailed_nonresp_none"] == 1
    assert d["mailed_nonresp_nu1_4"] + d["mailed_nonresp_none"] == d["mailed_nonresp"]
    assert out["cl_base"]["group_labels"]["mailed_nonresp_nu1_4"] == "Mailed, NU 1-4"
    assert out["cl_any"]["by_group"]["responders"]["pct"] == 100.0


def test_every_tier_row_carries_each_group_and_the_unresolved_name_is_left_unresolved(figures):
    out, _ = figures
    by_tier = {r["tier"]: r for r in out["cl_tiers"]}
    assert CL.UNRESOLVED in by_tier and by_tier[CL.UNRESOLVED]["dollars"] == 40
    for r in out["cl_tiers"]:
        assert set(r["by_group"]) == set(out["cl_base"]["groups"])
    names = {r["inst"]: r for r in out["cl_institutions"]}
    assert names["Maple Leaf"]["type"] == CREDIT_UNION and names["Maple Leaf"]["accounts"] == 1
    assert names["Maple Leaf"]["descriptors"] and names["Chase"]["tier"] == CL.NATIONAL
    assert "Upstart" not in names and "Acme Auto Finance" not in names


def test_the_unplaced_bank_like_text_is_listed_not_dropped(figures):
    out, _ = figures
    assert [r[0] for r in out["cl_review_queue"]] == ["SMALLTOWN CREDIT UNION"]
    cov = out["cl_coverage"]
    assert cov["review_dollars"] == 9 and cov["pct"] == round(cov["placed_dollars"] / (cov["placed_dollars"] + 9) * 100, 1)


def test_the_universe_counts_every_registry_institution_by_tier(figures):
    out, _ = figures
    assert sum(r["registry"] for r in out["cl_universe"]) == 11
    seen = {r["tier"]: r["seen"] for r in out["cl_universe"]}
    assert seen[CL.LOCAL] == 2 and seen[CL.REGIONAL] == 1


def test_no_market_record_says_so_and_places_no_local_tier():
    df, rows = _rows(SPEC_ROWS)
    warns = []
    out = CL.compute(df, rows, _Lenses({"personal": ["A1"]}), None, {}, pd.Timestamp("2026-10-31"), None, make_book(), SPEC,
                     warns.append, base_ids={"A1", "A2", "A3", "A4", "A5"})
    assert any("no market record" in w for w in warns)
    assert CL.LOCAL not in {r["tier"] for r in out["cl_tiers"]}


def test_no_reference_book_says_so_and_adds_nothing():
    df, rows = _rows(SPEC_ROWS)
    warns = []
    assert CL.compute(df, rows, None, None, CONFIG, None, RECORD, None, SPEC, warns.append, base_ids=None) == {}
    assert any("reference store" in w for w in warns)
