"""ILS pre-go-live sections on a hand-built frame with known answers.

v5 tests/test_pgl_sections.py, unchanged but for the imports and v5's 0_Config, which is
ils_pipeline/config/ here (pgl_input.config_dir()).
"""
import pandas as pd
import pytest

from ils_pipeline import pgl_input

CONFIG_DIR = pgl_input.config_dir()

from ils_pipeline.pre_go_live import bases as bases_mod                       # noqa: E402
from ils_pipeline.pre_go_live.codes import Codes                              # noqa: E402
from ils_pipeline.pre_go_live.sections import (fees, limits, od_status, readiness,  # noqa: E402
                                      rege, score, status, summary)

C = Codes(open_status=["O"], od_eligible=["003", "005"], rege_opt_in=["Y"], rege_opt_out=["N"])


def frame() -> pd.DataFrame:
    cols = ["AcctNo", "Personal_Business", "Account Status Code",
            "OD Status Code (from Core)", "Reg-E Opt-In Value",
            "UpOrDown from Initial OD Limit", "Initial OD Limit (from Core)",
            "OD Limit (from ILS)", "NSF OD Items since start date",
            "Paid NSF OD Items since start date", "Rolling 12 Month NSFOD Items",
            "Rolling 12 Month NSFOD Fees", "Deposit Count Last 33 days",
            "Deposit Amount Last 33 days", "Debit Decline Count",
            "Debit Decline Amount", "Open Date"]
    rows = [
        ["A1", "PERSONAL", "O", "003", "Y", "Score100Plus", 600, 700, 10, 5, 12, 162, 5, 2500, 2, 40, "2024-03-15"],
        ["A2", "PERSONAL", "O", "003", "N", "ScoreLess100", 600, 300, 4, 2, 4, 54, 2, 800, 0, 0, "2024-05-20"],
        ["A3", "PERSONAL", "O", "005", "Y", "Same", 0, 0, 0, 0, 0, 0, 3, 900, 1, 25, "2023-01-10"],
        ["A4", "PERSONAL", "O", "000", None, "Same", 300, 0, 2, 1, 2, 27, 0, 0, 0, 0, "2022-07-04"],
        ["A5", "PERSONAL", "C", "003", "Y", "Unknown", 600, None, 9, 3, 9, 121, 1, 100, 0, 0, "2021-09-09"],
        ["B1", "BUSINESS", "O", "003", "N", "Same", 1000, 1200, 6, 3, 6, 81, 9, 9000, 1, 10, "2020-01-01"],
        ["A6", "PERSONAL", "O", "003", "Y", "Score100Plus", 600, 800, 8, 4, 8, 108, 6, 3000, 0, 0, "2024-03-25"],
    ]
    df = pd.DataFrame(rows, columns=cols)
    df["Open Date"] = pd.to_datetime(df["Open Date"])
    for c in ["Personal_Business", "Account Status Code", "OD Status Code (from Core)",
              "Reg-E Opt-In Value", "UpOrDown from Initial OD Limit", "AcctNo"]:
        df[c] = df[c].astype("string")
    return df


@pytest.fixture(scope="module")
def env():
    df = frame()
    b = bases_mod.build(df, C, lambda _m: None)
    return df, b


def test_status_covers_the_whole_file(env):
    df, b = env
    m = status.compute(df, b, {"codes": C}, lambda _m: None)
    rows = {r[0]: r for r in m["pgl_status_rows"]}
    assert rows["O"][1] == 6 and rows["C"][1] == 1
    assert rows["O"][4] == 15 and rows["O"][3] == 30          # paid, items
    assert rows["O"][5] == 50.0                                # pay rate %
    by_type = {r[0]: r for r in m["pgl_open_by_type"]}
    assert by_type["PERSONAL"][1] == 5 and by_type["BUSINESS"][1] == 1
    assert by_type["PERSONAL"][2] == 83.3


def test_od_status_personal_and_business(env):
    df, b = env
    m = od_status.compute(df, b, {"codes": C}, lambda _m: None)
    p = {r[0]: r for r in m["pgl_od_status_personal"]}
    assert p["003"][1] == 3 and p["005"][1] == 1 and p["000"][1] == 1
    assert p["003"][-1] is True and p["000"][-1] is False      # eligible flag
    biz = {r[0]: r for r in m["pgl_od_status_business"]}
    assert biz["003"][1] == 1


def test_score_by_base(env):
    df, b = env
    m = score.compute(df, b, {"codes": C}, lambda _m: None)
    pers = {r[0]: r for r in m["pgl_score_personal"]}
    assert pers["Score100Plus"][1] == 2 and pers["Same"][1] == 2
    elig = {r[0]: r for r in m["pgl_score_eligible"]}
    assert elig["Same"][1] == 1                                 # A4 (000) drops out
    assert m["pgl_score_headline"]["personal"]["up"] == 2
    assert m["pgl_score_headline"]["personal"]["down"] == 1


def test_rege_mix_and_trend(env):
    df, b = env
    m = rege.compute(df, b, {"codes": C}, lambda _m: None)
    p = {r[0]: r for r in m["pgl_rege_personal"]}
    assert p["Y"][1] == 3 and p["N"][1] == 1 and p["<BLANK>"][1] == 1
    assert m["pgl_rege_optin_rate_personal"] == 60.0            # 3 of 5
    trend = {(r[0], r[1]): r for r in m["pgl_rege_trend"]}
    assert trend[(2024, "Q1")][3] == 2 and trend[(2024, "Q1")][5] == 100.0   # A1+A6, both Y


def test_limits_zero_and_distributions(env):
    df, b = env
    m = limits.compute(df, b, {"codes": C}, lambda _m: None)
    zl = {r[0]: r for r in m["pgl_zero_limit_by_deposit"]}
    assert zl["0"][1] == 1 and zl["3"][1] == 1                  # A4, A3
    assert zl["3"][-1] == 1                                     # A3 eligible
    cur = {r[0]: r for r in m["pgl_limit_dist_current"]}
    assert cur[600][1] == 3 and cur[0][1] == 1
    prop = {r[0]: r for r in m["pgl_limit_dist_proposed"]}
    assert set(prop) == {0, 300, 700, 800}
    cur_e = {r[0]: r for r in m["pgl_limit_dist_current_eligible"]}
    assert cur_e[600][1] == 3 and cur_e[0][1] == 1              # same base as proposed
    assert sum(r[1] for r in m["pgl_limit_dist_current_eligible"]) == \
           sum(r[1] for r in m["pgl_limit_dist_proposed"])
    assert m["pgl_eligible_null_limit"] == 0


def test_limits_warns_when_proposed_mass_sits_outside_eligible_codes():
    """If most proposed-limit accounts are NOT in the confirmed eligible OD
    codes, the code choice is probably wrong -- the run must say so."""
    df = frame()
    # flip: proposed limits live on 000/001-style codes, eligibles get $0
    df.loc[df["OD Status Code (from Core)"].isin(["003", "005"]), "OD Limit (from ILS)"] = 0
    df.loc[df["AcctNo"] == "A4", "OD Limit (from ILS)"] = 900       # code 000
    b = bases_mod.build(df, C, lambda _m: None)
    warns = []
    limits.compute(df, b, {"codes": C}, warns.append)
    assert any("outside the confirmed eligible codes" in w for w in warns)


def test_limits_no_warning_when_proposed_matches_eligible(env):
    df, b = env
    warns = []
    limits.compute(df, b, {"codes": C}, warns.append)
    assert not any("outside the confirmed eligible codes" in w for w in warns)


def test_fees_tiering(env):
    df, b = env
    tiers = {"Test Tier": [{"min_item": 1, "max_item": 3, "fee": 20},
                           {"min_item": 4, "max_item": None, "fee": 27}]}
    m = fees.compute(df, b, {"codes": C, "fee": 27, "tiers": tiers}, lambda _m: None)
    a = m["pgl_fee_audit"]
    assert a["items_12mo"] == 32 and a["fees_12mo"] == 432
    assert a["implied_pay_ratio_pct"] == 50.0
    assert m["pgl_fee_baseline"] == 432
    t = {r[0]: r for r in m["pgl_fee_tiers"]}
    assert t["Test Tier"][1] == 348                             # modeled revenue
    assert t["Test Tier"][2] == -84                             # delta vs baseline
    assert m["pgl_fee_daily_cap"]["status"].startswith("NOT COMPUTABLE")
    assert m["pgl_fee_de_minimis"]["status"].startswith("INSUFFICIENT")


def test_fees_decline_without_fee(env):
    df, b = env
    warns = []
    m = fees.compute(df, b, {"codes": C, "fee": None, "tiers": {}}, warns.append)
    assert "pgl_fee_tiers" not in m and "pgl_fee_audit" not in m
    assert any("fee" in w for w in warns)


def test_default_tiers_load_from_config():
    spec = fees.load_tiers(CONFIG_DIR)
    assert set(spec["tiers"]) == {"Tier 1 (Modest Relief)", "Tier 2 (Moderate Relief)",
                                  "Tier 3 (Maximum Relief)"}
    assert spec["designed_for_fee"] == 27


def test_summary_funnel_and_exposure(env):
    df, b = env
    m = summary.compute(df, b, {"codes": C}, lambda _m: None)
    funnel = {r[0]: r[1] for r in m["pgl_funnel"]}
    assert funnel["rows"] == 7 and funnel["open"] == 6
    assert funnel["personal"] == 5 and funnel["eligible"] == 4
    assert funnel["proposed_limit"] == 3                      # A1 700, A2 300, A6 800 (A3=0)
    e = m["pgl_exposure"]
    assert e["current_total"] == 1800 and e["proposed_total"] == 1800   # 600*3+0 vs 700+300+0+800
    assert e["delta"] == 0
    assert e["median_proposed"] == 500.0                       # of 0,300,700,800
    assert m["pgl_zero_limit_active"] == 1                     # A3: ils=0, 3 deposits
    assert any("eligible" in h for h in m["pgl_headlines"])


def test_readiness_scorecard(env):
    df, b = env
    m = readiness.compute(df, b, {"codes": C}, lambda _m: None)
    grades = {r[0]: r[1] for r in m["pgl_readiness"]}
    assert grades["limits & score"] == "ok"
    assert grades["fee history (12-mo)"] == "ok"               # test frame has items+fees
    assert grades["debit declines"] in ("ok", "thin")
    df2 = df.copy()
    df2["Rolling 12 Month NSFOD Items"] = None
    df2["Rolling 12 Month NSFOD Fees"] = None
    m2 = readiness.compute(df2, b, {"codes": C}, lambda _m: None)
    grades2 = {r[0]: r[1] for r in m2["pgl_readiness"]}
    assert grades2["fee history (12-mo)"] == "blocked"


def test_rege_trend_collapses_to_quarters_when_sparse():
    df = frame()
    b = bases_mod.build(df, C, lambda _m: None)
    m = rege.compute(df, b, {"codes": C}, lambda _m: None)
    # 5 personal openings over ~4 years -> way under 10/month -> quarterly
    assert m["pgl_rege_trend_grain"] == "quarter"
    assert all(isinstance(r[1], str) and r[1].startswith("Q") for r in m["pgl_rege_trend"])
