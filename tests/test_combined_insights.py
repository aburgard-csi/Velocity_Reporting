"""The test-branch views taken from James Gilmore's deck (test/james-aaron-combined).

combined_insights computes them; these tests pin that the responder side of the control
comparison IS the Responder Activity slide's figure, that the branch Total reconciles to the
deck's own program rates, and that every status/word comes from Aaron's +/-2% band.
"""
import datetime
import os

import pytest

import before_after as BA
import combined_insights as CI
import combined_insight_slides as CIS
from odd_rows import accessors

# ------------------------------------------------------------------ synthetic rows
MONTHS = ["Jan25", "Feb25", "Mar25", "Apr25", "May25", "Jun25", "Jul25",
          "Aug25", "Sep25", "Oct25", "Nov25", "Dec25", "Jan26", "Feb26"]
COLS = ["Business?", "Debit?", "Feb26 Elig"]
for _m in MONTHS:
    COLS += [f"{_m} Sig $", f"{_m} PIN $", f"{_m} Sig #", f"{_m} PIN #", f"{_m} Mail", f"{_m} Resp"]
H = {c: i for i, c in enumerate(COLS)}
ODD = accessors(H)


def row(before, after, mail="Apr25", resp="TH-10", mailed=True):
    r = [""] * len(COLS)
    r[H["Business?"]] = "No"
    r[H["Debit?"]] = "Yes"
    i = MONTHS.index(mail)
    for j, m in enumerate(MONTHS):
        r[H[f"{m} Sig $"]] = str(before if j < i else after)
    if mailed:
        r[H[f"{mail} Mail"]] = "TH-10"
    r[H[f"{mail} Resp"]] = resp
    return r


def test_the_control_is_mailed_non_responders_and_the_difference_is_arithmetic():
    rows = ([row(100, 200) for _ in range(10)]                 # responders +100
            + [row(300, 250, resp="") for _ in range(20)]      # mailed, no response: -50
            + [row(900, 900, resp="", mailed=False) for _ in range(20)])   # never mailed
    rc = CI.responder_control(rows, ODD, MONTHS, ["Apr25"])
    assert rc["available"]
    assert (rc["responders"]["before"], rc["responders"]["after"]) == (100, 200)
    assert (rc["control"]["before"], rc["control"]["after"]) == (300, 250)
    assert rc["control"]["n"] == 20                            # the never-mailed are not control
    assert rc["did"] == 150
    # indexed to each group's own baseline
    assert dict(rc["responders"]["trajectory"])[1] == 200.0
    assert dict(rc["control"]["trajectory"])[-1] == 100.0


def test_the_responder_side_reproduces_before_after(odd_csv):
    d = CI.read_odd(odd_csv)
    odd = accessors(d["H"])
    nextm = {d["smonths"][i]: d["smonths"][i + 1] for i in range(len(d["smonths"]) - 1)}
    mature = [m for m in d["mailmonths"] if m in nextm]
    rc = CI.responder_control(d["rows"], odd, d["smonths"], mature)
    ba = BA.compute(d["rows"], odd, d["smonths"], mature)
    assert rc["available"]
    assert (rc["responders"]["before"], rc["responders"]["after"]) == \
        (ba["ba_spend_before"], ba["ba_spend_after"])


def test_no_full_window_is_reported_not_zeroed():
    rows = [row(100, 200, mail="Feb26") for _ in range(10)]
    rc = CI.responder_control(rows, ODD, MONTHS, [])
    assert rc["available"] is False


# ------------------------------------------------------------------ branch KPIs
def test_branch_total_reconciles_to_the_decks_program_rates(odd_csv, metrics):
    d = CI.read_odd(odd_csv)
    bk = CI.branch_kpis(d["rows"], accessors(d["H"]), d["smonths"], d["latest"], min_eligible=1)
    t = bk["total"]
    assert t["eligible"] == metrics["n_eligible"]
    assert t["take"] == metrics["take_hist_pct"]
    assert t["rege"] == metrics["rege_pct"]
    assert t["first_year"] == metrics["bayes_prior"]
    # a roll-up of every branch is the total, recomputed from counts
    everything = bk["branches"] + ([bk["other"]] if bk["other"] else [])
    assert CI.roll_up("x", everything)["take"] == t["take"]


def test_roll_up_weights_by_accounts_not_by_branch():
    big = CI.branch_rates("a", dict.fromkeys(CI._COUNT_KEYS, 0) | {"elig": 1000, "cards": 900})
    small = CI.branch_rates("b", dict.fromkeys(CI._COUNT_KEYS, 0) | {"elig": 10, "cards": 1})
    assert CI.roll_up("both", [big, small])["take"] == round(100 * 901 / 1010, 1)


# ------------------------------------------------------------------ account health
@pytest.mark.parametrize("series,carded,want", [
    ([0] * 12, False, "No card"),
    ([0] * 12, True, "Never used"),
    ([50] * 9 + [0, 0, 0], True, "Dormant"),
    ([100] * 9 + [40, 40, 40], True, "Cooling"),
    ([100] * 9 + [70, 70, 70], True, "Declining"),
    ([100] * 9 + [85, 85, 85], True, "Active"),
    ([0] * 9 + [10, 10, 10], True, "Active"),       # use that started recently is not a decline
])
def test_health_states(series, carded, want):
    assert CI.classify_health(series, carded) == want


def test_health_covers_every_eligible_account(odd_csv, metrics):
    d = CI.read_odd(odd_csv)
    hk = CI.account_health(d["rows"], accessors(d["H"]), d["smonths"], d["latest"])
    assert hk["eligible"] == metrics["n_eligible"]
    assert sum(s[1] for s in hk["states"]) == hk["eligible"]
    assert hk["at_risk"] == sum(s[1] for s in hk["states"] if s[0] in CI.AT_RISK)


# ------------------------------------------------------------------ revenue by mailing
def test_rollup_sections_reads_each_mailing_and_leaves_unbooked_months_absent():
    d1, d2 = datetime.datetime(2026, 4, 1), datetime.datetime(2026, 5, 1)
    rows = [[None, "Summary", None, None, d1, d2],
            [None, 1, "Total Incremental Income", None, 100.0, 150.0],
            [None, "March 2026 Mailing", None, None, d1, d2],
            [None, "Incremental Revenue"],
            [None, 1, "Total Incremental Income", None, 100.0, 90.0],
            [None, "April 2026 Mailing", None, None, d1, d2],
            [None, "Incremental Revenue"],
            [None, 1, "Total Incremental Income", None, None, 60.0]]
    s = CI.rollup_sections(rows)
    assert s["March 2026 Mailing"] == {"2026-04": 100.0, "2026-05": 90.0}
    assert s["April 2026 Mailing"] == {"2026-05": 60.0}           # absent, not zero
    assert sum(s["Summary"].values()) == 250.0


def test_a_missing_workbook_is_stated(tmp_path):
    out = CI.wave_revenue(tmp_path / "nope.xlsx")
    assert out["available"] is False and out["reason"]


# ------------------------------------------------------------------ the +/-2% band
@pytest.mark.parametrize("value,comp,higher,want", [
    (91.3, 91.3, True, "level"), (93.0, 91.3, True, "level"), (94.0, 91.3, True, "ahead"),
    (80.0, 91.3, True, "behind"), (20.0, 15.0, False, "behind"), (10.0, 15.0, False, "ahead"),
])
def test_band(value, comp, higher, want):
    assert CI.band(value, comp, higher) == want


def test_band_against_zero_uses_the_scale():
    assert CI.band(5, 0, scale=900) == "level"
    assert CI.band(443, 0, scale=295) == "ahead"


def test_scorecard_statuses_follow_the_band():
    M = {"take_new_total": 10, "take_new_pct": 80.0, "take_hist_pct": 90.0,
         "rege_new_pool": 10, "rege_new_pct": 30.0, "rege_pct": 29.8}
    rows = CI.scorecard(M, {}, {"available": False}, {}, {})
    assert [r[3] for r in rows] == ["behind", "level"]


# ------------------------------------------------------------------ wording
def test_movement_words_follow_the_figures():
    assert "almost flat" in CIS.movement("Spend", 295, 300)
    assert "rose from $550 to $999 (+82%)" in CIS.movement("Spend", 550, 999)
    assert "did not have an impact" in CIS.movement("Spend", 600, 500)
    assert "fell from $300 to $250" in CIS.control_movement(300, 250)
    assert "rose" in CIS.control_movement(295, 301)            # +2.03% is outside the band


def test_the_slides_are_opt_in():
    src = open(os.path.join(os.path.dirname(CI.__file__), "build_ars_gen.py"), encoding="utf-8").read()
    assert 'os.environ.get("RPE_JAMES_SLIDES") == "1"' in src


def test_scorecard_names_need_most_numbers_to_resolve():
    """Branch Scorecard: names beside numbers (Aaron, 2026-09-17), but only when most of the shown
    numbers have a name, so a client whose ODD numbers branches differently is not mislabelled."""
    import branch_names as BN
    import combined_insight_slides as CIS
    row = lambda n, nm, src: dict(client_id="9001", client_name="", branch_number=n, branch_name=nm,
                                  source=src, source_file="f", first_seen="", last_seen="")
    data = [row("01", "Main", BN.SRC_CHARTS), row("4", "Gum Branch", BN.SRC_REFERRALS)]
    names, src = CIS.scorecard_branch_names("9001", ["1", "4", "7"], rows=data)
    assert names == {"1": "Main", "4": "Gum Branch"}
    assert src["1"].startswith(BN.SRC_CHARTS) and src["4"].startswith(BN.SRC_REFERRALS)
    assert CIS.scorecard_branch_names("9001", ["1", "7", "8"], rows=data) == ({}, {})
