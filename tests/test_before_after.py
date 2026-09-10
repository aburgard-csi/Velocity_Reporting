"""One before/after measure, shared by the deck and the Summit one-pager.

`responder_activity` (the one-pager) claimed in its own docstring to mirror
`metrics_gen` (the deck) and differed in four ways at once — cohort, after
window, winsorizing, and how the headline was pooled. Aaron, 2026-09-08: "the
Summits and the regular delivery decks should use the same logic."

These tests pin the shared function's decisions and, at the end, that both
entry points really do call it rather than carrying a copy.
"""
import os
import statistics
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, os.pardir, "build"))
sys.path.insert(0, os.path.join(_HERE, os.pardir, "build", "ars_pipeline"))

import before_after as BA                                # noqa: E402
from odd_rows import accessors                           # noqa: E402

MONTHS = ["Jan25", "Feb25", "Mar25", "Apr25", "May25", "Jun25", "Jul25",
          "Aug25", "Sep25", "Oct25", "Nov25", "Dec25", "Jan26", "Feb26"]

COLS = ["Business?", "Jun25 Elig"]
for _m in MONTHS:
    COLS += [f"{_m} Sig $", f"{_m} PIN $", f"{_m} Sig #", f"{_m} PIN #",
             f"{_m} MTD", f"{_m} Mail", f"{_m} Resp"]
H = {c: i for i, c in enumerate(COLS)}
ODD = accessors(H)


def row(spend_by_month, mail_month=None, offer="TH-10", nsf=0.0,
        business=False, elig="Yes"):
    r = [""] * len(COLS)
    r[H["Business?"]] = "Yes" if business else "No"
    r[H["Jun25 Elig"]] = elig
    for m in MONTHS:
        r[H[f"{m} Sig $"]] = str(spend_by_month.get(m, 0))
        r[H[f"{m} MTD"]] = str(nsf)
    if mail_month:
        r[H[f"{mail_month} Mail"]] = "NU" if offer == "NU 5+" else "TH-10"
        r[H[f"{mail_month} Resp"]] = offer
    return r


def cohort(n, before, after, mail="Apr25", offer="TH-10", **kw):
    """n identical responders: `before` a month before the mailing, `after` after."""
    i = MONTHS.index(mail)
    spend = {m: before for m in MONTHS[:i]}
    spend.update({m: after for m in MONTHS[i + 1:]})
    return [row(spend, mail, offer, **kw) for _ in range(n)]


def run(rows, mailings=("Apr25",), **kw):
    return BA.compute(rows, ODD, MONTHS, list(mailings), **kw)


# --------------------------------------------------------------- the windows

def test_the_default_window_is_three_before_and_six_after():
    out = run(cohort(10, 100, 200))
    assert (out["ba_before_months"], out["ba_after_months"]) == (3, 6)


def test_the_after_window_is_fixed_not_to_the_end_of_the_extract():
    """A responder who spends 200 for six months and then 800 forever must NOT
    have the later months pulled into 'after' — an old mailing would otherwise
    average many more months than a recent one and the bars stop comparing."""
    i = MONTHS.index("Apr25")
    spend = {m: 100 for m in MONTHS[:i]}
    spend.update({m: 200 for m in MONTHS[i + 1:i + 7]})
    spend.update({m: 800 for m in MONTHS[i + 7:]})
    out = run([row(spend, "Apr25") for _ in range(10)])
    assert out["ba_spend_after"] == 200


def test_a_short_program_shrinks_the_after_side_first():
    """Wellworth 1549: one mailing, one month of extract after it. The baseline
    is what the comparison is anchored to, so it gives ground last."""
    months = MONTHS[:5]                     # Jan..May25, mailing in Apr25
    out = BA.compute(cohort(10, 100, 200), ODD, months, ["Apr25"])
    assert (out["ba_before_months"], out["ba_after_months"]) == (3, 1)


def test_no_usable_mailing_warns_rather_than_inventing_a_window():
    seen = []
    out = BA.compute(cohort(10, 100, 200), ODD, MONTHS[:2], ["Feb25"],
                     on_warning=seen.append)
    assert out["before_after"] == [] and seen


# --------------------------------------------------------------- the cohort

def test_the_cohort_is_every_personal_responder_not_the_still_eligible():
    """A present-tense eligibility filter on a historical cohort is a
    survivorship filter: it drops exactly the accounts that closed or went
    quiet, which is what lifted Austin 1075 from +53% to +62%."""
    live = cohort(10, 100, 400)
    lapsed = cohort(10, 100, 100, elig="No")     # responded, since gone quiet
    out = run(live + lapsed)
    assert out["before_after"][0]["n"] == 20
    assert out["ba_spend_after"] == 250          # both cohorts, not just the live one


def test_business_accounts_are_excluded():
    out = run(cohort(10, 100, 400) + cohort(10, 100, 4000, business=True))
    assert out["before_after"][0]["n"] == 10


def test_a_mailing_under_five_responders_is_not_charted():
    assert run(cohort(4, 100, 400))["before_after"] == []
    assert run(cohort(5, 100, 400))["before_after"] != []


# --------------------------------------------------------------- winsorizing

def test_one_cap_spans_both_windows():
    """A separate cap per window let the cap itself move the delta."""
    a, b = [1, 1, 1, 100], [1, 1, 1, 1]
    ca, cb = BA.wins_pair(a, b)
    combined = statistics.mean(a + b) + 3 * statistics.pstdev(a + b)
    assert max(ca) == pytest.approx(min(100, combined))
    # the same cap governs the other window, whatever its own spread
    assert max(cb) <= combined


# --------------------------------------------------------------- the headline

def test_the_headline_pools_observations_rather_than_averaging_mailings():
    """A 100-responder mailing must outweigh a 10-responder one."""
    # Both mailings must fit the same window, or the ladder simply drops one and
    # the test would pass for the wrong reason.
    big = cohort(100, 100, 200, mail="Apr25")
    small = cohort(10, 100, 300, mail="Aug25")     # inside the 3 SD cap, so the
    out = run(big + small, mailings=("Apr25", "Aug25"))   # weighting is what shows
    assert len(out["before_after"]) == 2
    pooled = (100 * 200 + 10 * 300) / 110                 # 209
    assert out["ba_spend_after"] == pytest.approx(pooled, abs=1)
    mean_of_mailings = (200 + 300) / 2                    # 250 — the old answer
    assert out["ba_spend_after"] != pytest.approx(mean_of_mailings, abs=1)


def test_the_offer_split_keys_on_what_was_mailed():
    out = run(cohort(10, 100, 200, offer="NU 5+") + cohort(10, 500, 900))
    assert out["ba_split_headline"]["nu"]["n"] == 10
    assert out["ba_split_headline"]["nu"]["after"] == 200
    assert out["ba_split_headline"]["th"]["after"] == 900


def test_nsf_is_reported_and_not_winsorized():
    """The chart's NSF panel plots raw means, so the slide's NSF clause has to
    read the same raw means or the sentence and the panel disagree."""
    out = run(cohort(10, 100, 200, nsf=0.5))
    assert out["ba_nsf_before"] == 0.5 and out["ba_nsf_after"] == 0.5


def test_pct_change_survives_a_zero_baseline():
    assert BA.pct_change(0, 500) == 0
    assert BA.pct_change(100, 150) == 50.0
    assert BA.pct_change(100, 80) == -20.0


# --------------------------------------------- both entry points share it

def _src(rel):
    with open(os.path.join(_HERE, os.pardir, rel), encoding="utf-8") as fh:
        return fh.read()


@pytest.mark.parametrize("mod", ["build/ars_pipeline/metrics_gen.py",
                                 "build/ars_pipeline/responder_activity.py"])
def test_both_callers_use_the_shared_function(mod):
    src = _src(mod)
    assert "before_after" in src and ".compute(" in src


@pytest.mark.parametrize("mod", ["build/ars_pipeline/metrics_gen.py",
                                 "build/ars_pipeline/responder_activity.py"])
def test_neither_caller_keeps_its_own_copy(mod):
    """The specific idiom both copies used. A re-implementation that slices its
    own before/after windows out of `smonths` fails here."""
    src = _src(mod)
    assert "smonths[idx - 3:idx]" not in src
    assert "smonths[i-BA_B:i]" not in src
    assert "smonths[idx + 1:]" not in src
