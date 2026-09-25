"""The second round of James's views (james_views.py, 2026-09-25).

One test group per view. The rows are synthetic and hand-built so each figure is known in
advance; the shipped synthetic ODD varies too little to prove a first swipe, a flip or a fade.
The last group pins that every view is in the opt-in set and renders, and that the tier rule
here agrees with metrics_gen's and combined_insights'.
"""
import datetime
import inspect
import os
import zipfile

import pytest

import combined_insights as CI
import james_views as JV
import james_view_charts as JC
import james_view_slides as JVS
from odd_rows import accessors, REGE_IN, REGE_OUT

MONTHS = []
_d = datetime.date(2024, 9, 1)
while _d <= datetime.date(2026, 8, 1):
    MONTHS.append(_d.strftime("%b%y"))
    _d = (_d.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
LATEST = MONTHS[-1]
MAIL = ["Mar26", "May26"]

COLS = ["Branch", "Business?", "Debit?", "Stat Desc", "Date Opened", "Date Closed", "Avg Bal",
        "Curr Bal", "Prod Desc", f"{LATEST} Elig"]
for _m in MONTHS:
    COLS += [f"{_m} Sig #", f"{_m} Sig $", f"{_m} PIN #", f"{_m} PIN $", f"{_m} MTD",
             f"{_m} Reg E Desc"]
for _m in MAIL:
    COLS += [f"{_m} Mail", f"{_m} Resp"]
H = {c: i for i, c in enumerate(COLS)}
ODD = accessors(H)


def row(swipes=10, ticket=40.0, carded=True, elig=True, open_=True, opened="01/15/2015",
        closed="", branch="1", avg=1000, cur=1000, nsf=0, rege="Opt-In", prod="Checking",
        per_month=None, mail=None, resp=None, rege_by_month=None):
    """One personal account. `per_month` overrides swipes month by month ({token: n})."""
    r = [""] * len(COLS)
    r[H["Branch"]] = branch
    r[H["Business?"]] = "No"
    r[H["Debit?"]] = "Yes" if carded else "No"
    r[H["Stat Desc"]] = "Open" if open_ else "Closed"
    r[H["Date Opened"]] = opened
    r[H["Date Closed"]] = closed
    r[H["Avg Bal"]] = str(avg)
    r[H["Curr Bal"]] = str(cur)
    r[H["Prod Desc"]] = prod
    r[H[f"{LATEST} Elig"]] = "Yes" if elig else "No"
    for m in MONTHS:
        n = (per_month or {}).get(m, swipes)
        r[H[f"{m} Sig #"]] = str(n)
        r[H[f"{m} Sig $"]] = f"{n * ticket:.2f}"
        r[H[f"{m} MTD"]] = str(nsf)
        r[H[f"{m} Reg E Desc"]] = (rege_by_month or {}).get(m, rege)
    for m in MAIL:
        r[H[f"{m} Mail"]] = (mail or {}).get(m, "")
        r[H[f"{m} Resp"]] = (resp or {}).get(m, "")
    return r


# ------------------------------------------------------------------ Reg E over time
def test_rege_trend_counts_elections_and_flips():
    early = {m: "Opt-Out" for m in MONTHS[:-12]}
    rows = [row(rege="Opt-In"), row(rege="Opt-Out"),
            row(rege="Opt-In", rege_by_month=early)]         # moved into opt-in in the year
    rt = JV.rege_trend(rows, ODD, MONTHS, H)
    assert rt["available"]
    assert rt["last"]["in_pct"] == pytest.approx(66.7, abs=0.1)
    assert rt["first"]["in_pct"] == pytest.approx(33.3, abs=0.1)
    assert (rt["to_in"], rt["from_in"]) == (1, 0)


def test_rege_trend_without_monthly_columns_says_so():
    rt = JV.rege_trend([row()], ODD, MONTHS, {})
    assert rt["available"] is False and "Reg E Desc" in rt["reason"]


def test_an_unmapped_election_is_reported_not_guessed():
    rt = JV.rege_trend([row(rege="Maybe Later")], ODD, MONTHS, H)
    assert "Maybe Later" in rt.get("unmapped", {}) or rt["available"] is False


# ------------------------------------------------------------------ repeat responses
def test_a_second_met_goal_is_a_repeat_and_a_higher_rung_climbs():
    rows = [row(mail={"Mar26": "NU", "May26": "TH-10"}, resp={"Mar26": "NU 5+", "May26": "TH-10"}),
            row(mail={"Mar26": "TH-10"}, resp={"Mar26": "NU 1-4"})]     # a partial is no response
    rr = JV.repeat_responses(rows, ODD, MAIL)
    assert (rr["first_time"], rr["repeat"]) == (1, 1)
    assert rr["moves"]["Up"] == 1
    assert rr["by_offer_number"][0]["mailed"] == 2 and rr["by_offer_number"][0]["responded"] == 1


def test_no_met_goal_is_stated():
    rr = JV.repeat_responses([row(mail={"Mar26": "NU"})], ODD, MAIL)
    assert rr["available"] is False


# ------------------------------------------------------------------ activation
def test_first_swipes_split_new_mailed_and_organic():
    quiet = {m: 0 for m in MONTHS[:-6]}          # first swipe six months before the end
    first = MONTHS[-6]
    mailed_first = row(per_month=quiet, mail={"May26": "NU"}) if first in ("May26", "Jun26") \
        else row(per_month=quiet, mail={"Mar26": "NU"})
    rows = [mailed_first,
            row(per_month=quiet),                                          # on its own
            row(per_month=quiet, opened="12/01/2025"),                      # new account
            row()]                                                          # always swiped
    a = JV.activation_split(rows, ODD, MONTHS, MAIL)
    assert (a["mailed"], a["organic"], a["new"]) == (1, 1, 1)
    assert a["program_pct"] == 50.0


def test_activation_needs_enough_months():
    a = JV.activation_split([row()], ODD, MONTHS[:10], MAIL)
    assert a["available"] is False


# ------------------------------------------------------------------ movement by group
def test_movement_groups_responders_apart():
    up = {m: 30 for m in MONTHS[-3:]}
    rows = [row(swipes=3, per_month=up, mail={"Mar26": "NU"}, resp={"Mar26": "NU 5+"}),
            row(swipes=3, mail={"Mar26": "NU"}),
            row(swipes=3)]
    mg = JV.movement_by_group(rows, ODD, MONTHS, MAIL, LATEST)
    g = {x["group"]: x for x in mg["groups"]}
    assert g["Responder"]["up"] == 100.0
    assert g["Mailed non-responder"]["same"] == 100.0
    assert g["Not mailed"]["accounts"] == 1


# ------------------------------------------------------------------ per-mailing control
def test_per_mailing_rows_are_thin_below_the_floor():
    rows = [row(mail={"Mar26": "NU"}, resp={"Mar26": "NU 5+"})] + [row(mail={"Mar26": "NU"})] * 6
    pm = JV.per_mailing_control(rows, ODD, MONTHS, MAIL)
    assert all(r["thin"] for r in pm["mailings"])
    assert pm["available"] is False


def test_per_mailing_net_is_responder_change_less_control_change():
    up = {m: 30 for m in MONTHS[MONTHS.index("Apr26"):]}
    rows = [row(swipes=5, per_month=up, mail={"Mar26": "NU"}, resp={"Mar26": "NU 5+"})] * 6 + \
           [row(swipes=5, mail={"Mar26": "NU"})] * 6
    pm = JV.per_mailing_control(rows, ODD, MONTHS, MAIL)
    r = next(x for x in pm["mailings"] if x["m"] == "Mar 2026")
    assert r["did"] == r["r_change"] - r["c_change"]
    assert r["did"] > 0


# ------------------------------------------------------------------ closures and warning
def test_closure_rate_by_product_uses_the_scorecard_definition():
    rows = [row(prod="A"), row(prod="A", open_=False, closed="03/10/2026"),
            row(prod="B"), row(prod="B", open_=False, closed="03/10/2020")]   # old closure: out
    wc = JV.where_accounts_close(rows, ODD, LATEST, min_branch=1)
    p = {x["name"]: x for x in wc["products"]}
    assert p["A"]["rate"] == 50.0 and p["B"]["rate"] == 0.0
    assert wc["total"]["at_risk"] == 3


def test_a_closer_that_lost_its_card_flag_still_counts_as_a_card_user():
    fade = {m: 1 for m in MONTHS[MONTHS.index("Feb26") - 3:]}
    rows = [row() for _ in range(5)] + \
           [row(carded=False, open_=False, closed="04/20/2026", per_month=fade)]
    mw = JV.months_of_warning(rows, ODD, MONTHS, LATEST)
    assert mw["closers"] == 1
    assert mw["warning"] is not None and mw["warning"] >= 1


def test_no_fade_is_reported_as_none_not_zero():
    rows = [row() for _ in range(5)] + [row(open_=False, closed="04/20/2026")]
    mw = JV.months_of_warning(rows, ODD, MONTHS, LATEST)
    assert mw["warning"] is None


# ------------------------------------------------------------------ stressors
def test_stress_conditions_stack():
    fading = {m: 0 for m in MONTHS[-3:]}
    rows = [row(per_month=fading, nsf=1, avg=1000, cur=100),   # all three
            row(nsf=1),                                         # overdrawing only
            row()]                                              # none
    st = JV.stressors(rows, ODD, MONTHS, MONTHS, LATEST)
    by = {x["n"]: x["accounts"] for x in st["by_count"]}
    assert (by[3], by[1], by[0]) == (1, 1, 1)
    assert st["multi"] == 1


# ------------------------------------------------------------------ card gaps
def test_cards_short_of_the_book_rate():
    rows = [row(branch="1")] * 50 + [row(branch="2")] * 25 + [row(branch="2", carded=False)] * 25
    cg = JV.card_gaps(rows, ODD, LATEST, min_branch=10)
    assert cg["take"] == 75.0
    g = {x["branch"]: x for x in cg["branches"]}
    assert g["2"]["short"] == round(50 * 0.75) - 25
    assert g["1"]["short"] == 0


# ------------------------------------------------------------------ value at workbook rates
def test_account_value_is_unavailable_without_a_workbook():
    av = JV.account_value([row()], ODD, MONTHS, LATEST, None)
    assert av["available"] is False and "workbook" in av["reason"]


def test_account_value_prices_spend_and_items_at_the_workbook_rates(monkeypatch):
    monkeypatch.setattr(JV, "_rates", lambda p: ({"ic_rate": 0.01, "nsf_fee": 30.0,
                                                  "sheet": "Actuals MM"}, None))
    rows = [row(swipes=10, ticket=10.0, nsf=1, rege="Opt-In"),
            row(carded=False, swipes=0, nsf=0, rege="")]
    av = JV.account_value(rows, ODD, MONTHS, LATEST, "wb.xlsx")
    card = av["groups"]["Card"]
    assert card["interchange"] == round(0.01 * 100 * 12)      # $100 a month x 12 x 1%
    assert card["fees"] == 30 * 12
    assert av["card_delta"] == card["total"] - av["groups"]["No card"]["total"]
    assert av["groups"][REGE_IN]["accounts"] == 1 and av["groups"][REGE_OUT]["accounts"] == 0
    assert av["optin_delta"] is None                           # no opted-out group to compare


def test_the_value_window_is_the_last_complete_months(monkeypatch):
    monkeypatch.setattr(JV, "_rates", lambda p: ({"ic_rate": 0.01, "nsf_fee": 30.0,
                                                  "sheet": "Actuals MM"}, None))
    av = JV.account_value([row()], ODD, MONTHS[:-1], LATEST, "wb.xlsx")
    assert av["window"][1] == "Jul 2026"


# ------------------------------------------------------------------ response worth
def test_response_worth_prices_the_pooled_difference():
    rc = {"available": True, "did": 400, "responders": {"n": 100}, "after_months": 6,
          "before_months": 3, "mailings": ["Mar 2026"]}
    import james_views
    orig = james_views._rates
    try:
        james_views._rates = lambda p: ({"ic_rate": 0.01, "nsf_fee": 30.0}, None)
        rv = JV.responder_value(rc, "wb.xlsx", {"ltd_revenue": 1000.0, "months": 12})
    finally:
        james_views._rates = orig
    assert rv["per_month"] == 4.0 and rv["per_year"] == 48.0
    assert rv["cohort_window"] == round(4.0 * 100 * 6)


# ------------------------------------------------------------------ mailing P&L
def test_mailing_pnl_reads_income_fees_and_responders(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = JV.ROLLUP_SHEET
    ws.append([None, "Summary", datetime.datetime(2026, 4, 1)])
    ws.append([None, 1, "Total Incremental Income", 10.0])
    ws.append([None, "March 2026 Mailing", datetime.datetime(2026, 4, 1), datetime.datetime(2026, 5, 1)])
    ws.append([None, "Incremental Revenue"])
    ws.append([None, 1, "Total Incremental Income", 300.0, 200.0])
    ws.append([None, 2, "Total Incremental Expense", 0, -100.0])
    ws.append([None, 3, "Number of Responders", 4, 0])
    p = tmp_path / "wb.xlsx"
    wb.save(p)
    pnl = JV.mailing_pnl(str(p))
    m = pnl["mailings"][0]
    assert (m["income"], m["fees"], m["responders"]) == (500.0, 100.0, 4)
    assert m["per_fee_dollar"] == 5.0 and m["per_responder"] == 125.0


def test_mailing_pnl_without_a_workbook_says_so():
    assert JV.mailing_pnl(None)["available"] is False


# ------------------------------------------------------------------ offer segments
def test_offer_segments_split_by_mail_code():
    rows = [row(mail={"Mar26": "NU"}, resp={"Mar26": "NU 5+"})] * 3 + [row(mail={"Mar26": "TH-10"})] * 2
    seg = JV.offer_segments(rows, ODD, MONTHS, MAIL)
    s = {x["segment"]: x for x in seg["segments"]}
    assert s["NU"]["rate"] == 100.0 and s["TH-10"]["rate"] == 0.0
    assert s["NU"]["did"] is None           # too few on each side to compare


# ------------------------------------------------------------------ cascade
def test_the_cascade_narrows_step_by_step():
    rows = [row(mail={"Mar26": "NU"}, resp={"Mar26": "NU 5+"}), row(mail={"Mar26": "NU"}),
            row(swipes=0), row(carded=False)]
    cc = JV.cascade(rows, ODD, MONTHS, MAIL, LATEST)
    vals = [v for _k, v in cc["steps"]]
    assert vals == [4, 3, 2, 2, 1]
    assert vals == sorted(vals, reverse=True)


# ------------------------------------------------------------------ card spend by merchant
def _txn_zip(tmp_path, lines):
    p = tmp_path / "1234_ODDD.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("1234-odd.csv", "x\n")
        z.writestr("1234_debit transaction file", "1234|header|x\n" + "\n".join(lines) + "\n")
    return str(p)


def test_merchant_groups_read_card_rails_only(tmp_path):
    p = _txn_zip(tmp_path, [
        "08/01/2026\tA\tSIG\t50.00\t5411\tNEW BERN NC\t\t",
        "08/02/2026\tA\tPIN\t25.00\t5812\tNEW BERN NC\t\t",
        "08/31/2026\tB\tACH\t900.00\t\tPAYROLL\t\t",
    ])
    mx = JV.card_spend_mix(p)
    g = {x["group"]: x for x in mx["groups"]}
    assert set(g) == {"Grocery", "Restaurants"}
    assert mx["spend"] == 75
    assert mx["rails"]["ACH"]["spend"] == 900
    assert mx["complete"] is True
    assert mx["home_state"] == "NC"


def test_no_transaction_file_is_stated(tmp_path):
    p = tmp_path / "x.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("x-odd.csv", "x\n")
    assert JV.card_spend_mix(str(p))["available"] is False


def test_mcc_groups():
    assert JV.mcc_group("5411") == "Grocery"
    assert JV.mcc_group("4829") == "Money transfer"
    assert JV.mcc_group("") == "Not coded"


# ------------------------------------------------------------------ wiring
def test_the_tier_rule_matches_the_other_two():
    for v in (0, 0.99, 1, 5.5, 6, 10.9, 15.9, 20.2, 25.99, 26, 80):
        assert JV.swipe_tier(v) == CI.swipe_tier(v), v


def test_every_view_is_in_the_opt_in_set():
    src = inspect.getsource(JVS.add_more_slides)
    for fn in ("pnl_slide", "segments_slide", "offer_number_slide", "per_mailing_slide",
               "response_worth_slide", "movement_slide", "activation_slide", "spend_mix_slide",
               "rails_slide", "card_gaps_slide", "value_slide", "ladder_slide", "stress_slide",
               "branch_value_slide", "rege_trend_slide", "cascade_slide", "close_slide",
               "warning_slide"):
        assert f"{fn}(prs, ci, ctx)" in src, fn
    import combined_insight_slides as CIS
    assert "JVS.add_more_slides(prs, ci, ctx)" in inspect.getsource(CIS.add_insight_slides)


def test_compute_runs_the_second_round():
    assert "JV.compute(" in inspect.getsource(CI.compute)


def test_the_monthly_reg_e_column_is_read():
    assert CI._MON_COL.match("Aug26 Reg E Desc")


def test_the_charts_render(tmp_path):
    rt = JV.rege_trend([row(), row(rege="Opt-Out")], ODD, MONTHS, H)
    JC.rege_trend_chart(str(tmp_path / "a.png"), rt)
    JC.offer_number_chart(str(tmp_path / "b.png"), [{"n": "1", "rate": 10.0}, {"n": "2", "rate": 8.0}])
    JC.activation_chart(str(tmp_path / "c.png"), {"new": 3, "mailed": 2, "organic": 1})
    JC.movement_chart(str(tmp_path / "d.png"), [{"group": "Responder", "accounts": 5, "up": 50.0,
                                                 "same": 30.0, "down": 20.0}])
    JC.stress_chart(str(tmp_path / "e.png"), {"by_count": [{"n": i, "accounts": 10 - i, "pct": 10.0}
                                                           for i in range(4)]})
    JC.cascade_chart(str(tmp_path / "f.png"), [["A", 10], ["B", 5]])
    JC.rails_chart(str(tmp_path / "g.png"), {"SIG": {"spend": 10}, "ACH": {"spend": 5}})
    for n in "abcdefg":
        assert os.path.getsize(tmp_path / f"{n}.png") > 3000
