"""Responders against their own segment (2026-09-21).

The pooled control answers "did the mailings move spend" for the book. This splits it by the
tier each account sat in BEFORE the offer, which is the comparison James makes. The tests pin
the two things that make it honest: the tier is the pre-mailing tier, and a tier too thin to
compare is shown as thin rather than compared anyway.
"""
import pytest

import combined_insights as CI
import before_after as BA
from odd_rows import accessors

MONTHS = ["Jan25", "Feb25", "Mar25", "Apr25", "May25", "Jun25", "Jul25", "Aug25", "Sep25",
          "Oct25", "Nov25", "Dec25", "Jan26", "Feb26"]
MAIL = "Jun25"
COLS = ["Business?", "Debit?"]
for _m in MONTHS:
    COLS += [f"{_m} Sig #", f"{_m} Sig $", f"{_m} PIN #", f"{_m} PIN $"]
COLS += [f"{MAIL} Mail", f"{MAIL} Resp"]
H = {c: i for i, c in enumerate(COLS)}
ODD = accessors(H)


def row(swipes_before, spend_before, spend_after, responded, mailed=True):
    r = [""] * len(COLS)
    r[H["Business?"]] = "No"
    r[H["Debit?"]] = "Yes"
    i = MONTHS.index(MAIL)
    for k, m in enumerate(MONTHS):
        after = k > i
        r[H[f"{m} Sig #"]] = str(swipes_before)
        r[H[f"{m} Sig $"]] = f"{(spend_after if after else spend_before):.2f}"
    if mailed:
        r[H[f"{MAIL} Mail"]] = "TH-10"
        r[H[f"{MAIL} Resp"]] = "TH-10" if responded else ""
    return r


def cohort(n, **kw):
    return [row(**kw) for _ in range(n)]


def run(rows, min_cohort=5):
    return CI.responder_by_tier(rows, ODD, MONTHS, [MAIL], min_cohort=min_cohort)


def test_accounts_are_tiered_on_where_they_sat_before_the_mailing():
    """Tiering on today's swipes would sort accounts by the very thing the mailing is
    supposed to have changed, and every mailing would look like it created heavy users."""
    rows = (cohort(8, swipes_before=2, spend_before=100, spend_after=300, responded=True)
            + cohort(8, swipes_before=2, spend_before=100, spend_after=100, responded=False))
    out = run(rows)
    by = {r["tier"]: r for r in out["rows"]}
    assert by["1-5"]["thin"] is False
    assert by["1-5"]["responders"] == 8
    assert by["26+"]["thin"] is True        # nobody was a heavy user BEFORE the offer


def test_the_net_is_the_difference_of_the_two_changes():
    rows = (cohort(8, swipes_before=2, spend_before=100, spend_after=180, responded=True)
            + cohort(8, swipes_before=2, spend_before=100, spend_after=120, responded=False))
    r = {x["tier"]: x for x in run(rows)["rows"]}["1-5"]
    assert r["resp_change"] == 80
    assert r["control_change"] == 20
    assert r["net"] == 60


def test_a_tier_with_too_few_on_either_side_is_thin_not_compared():
    rows = (cohort(8, swipes_before=2, spend_before=100, spend_after=300, responded=True)
            + cohort(2, swipes_before=2, spend_before=100, spend_after=100, responded=False))
    r = {x["tier"]: x for x in run(rows)["rows"]}["1-5"]
    assert r["thin"] is True
    assert r["net"] is None


def test_every_tier_keeps_a_row_even_when_empty():
    out = run(cohort(8, swipes_before=2, spend_before=100, spend_after=180, responded=True)
              + cohort(8, swipes_before=2, spend_before=100, spend_after=100, responded=False))
    assert [r["tier"] for r in out["rows"]] == CI.TIER_ORDER


def test_the_control_is_mailed_non_responders_not_the_unmailed_book():
    rows = (cohort(8, swipes_before=2, spend_before=100, spend_after=180, responded=True)
            + cohort(8, swipes_before=2, spend_before=100, spend_after=100, responded=False)
            + cohort(50, swipes_before=2, spend_before=100, spend_after=999, responded=False,
                     mailed=False))
    r = {x["tier"]: x for x in run(rows)["rows"]}["1-5"]
    assert r["control"] == 8            # the 50 unmailed accounts are not a control


def test_a_mailing_with_too_few_responders_is_skipped_entirely():
    out = run(cohort(2, swipes_before=2, spend_before=100, spend_after=180, responded=True)
              + cohort(8, swipes_before=2, spend_before=100, spend_after=100, responded=False),
              min_cohort=5)
    assert out["mailings"] == []
    assert out["available"] is False


def test_the_windows_are_before_afters_own():
    """If these drift, this slide and Responders vs Mailed Non-Responders would describe the
    same mailings over different windows and disagree in print."""
    out = run(cohort(8, swipes_before=2, spend_before=100, spend_after=180, responded=True)
              + cohort(8, swipes_before=2, spend_before=100, spend_after=100, responded=False))
    bw, aw, _ = BA.windows(MONTHS, [MAIL])
    assert (out["before_months"], out["after_months"]) == (bw, aw)


def test_the_chart_renders(tmp_path):
    import os
    import insight_charts as IC
    out = run(cohort(8, swipes_before=2, spend_before=100, spend_after=180, responded=True)
              + cohort(8, swipes_before=2, spend_before=100, spend_after=100, responded=False))
    png = str(tmp_path / "bytier.png")
    IC.by_tier_chart(png, out["rows"], 8.0, 4.0)
    assert os.path.getsize(png) > 5000


def test_the_slide_is_in_the_opt_in_set():
    import inspect
    import combined_insight_slides as CIS
    assert "by_tier_slide(prs, ci, ctx)" in inspect.getsource(CIS.add_insight_slides)
