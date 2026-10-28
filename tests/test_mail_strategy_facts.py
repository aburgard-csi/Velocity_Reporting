"""The figures behind Delivery Call Notes (Aaron, 2026-10-28): one wording for every comparison, complete months only."""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ("scripts", "build"):
    sys.path.insert(0, os.path.join(REPO, p))
import mail_strategy_facts as F  # noqa: E402


def test_the_comparison_is_consistent_within_the_band_and_names_a_direction_outside_it():
    assert F.comparison("Sep 26", 38, 41, "referrals") == \
        "Sep 26: 38 referrals, consistent with the prior 6-month average of 41."
    assert F.comparison("Sep 26", 290, 367, "referrals") == \
        "Sep 26: 290 referrals, lower than the prior 6-month average of 367 (-21%)."
    assert F.comparison("Sep 26", 23, 13, "referrals") == \
        "Sep 26: 23 referrals, higher than the prior 6-month average of 13 (+77%)."
    # exactly on the edge is still consistent
    assert "consistent with" in F.comparison("Sep 26", 80, 100, "loans")
    assert "no prior 6-month average" in F.comparison("Sep 26", 5, None, "loans")


def test_the_usual_level_is_the_six_months_before_the_last_and_needs_three():
    assert F.usual_level([1, 2, 3, 4, 5, 6, 7, 99]) == 4.5          # 2..7, not the last
    assert F.usual_level([10, 20, 30, 99]) == 20
    assert F.usual_level([10, 20, 99]) is None


def test_the_month_in_progress_is_dropped_before_comparing():
    months = ["2026-07", "2026-08", "2026-09", "2026-10"]
    assert F.complete_series(months, [1, 2, 3, 4], partial_last=True) == (months[:3], [1, 2, 3])
    assert F.complete_series(months, [1, 2, 3, 4], generated="2026-10-26") == (months[:3], [1, 2, 3])
    assert F.complete_series(months, [1, 2, 3, 4]) == (months, [1, 2, 3, 4])


def test_ics_uses_the_vip_trend_and_drops_the_partial_last_month():
    sheet = {"referrals": {"trend": {
        "months": ["Mar 26", "Apr 26", "May 26", "Jun 26", "Jul 26", "Aug 26", "Sep 26", "Oct 26"],
        "referrals": [379, 324, 361, 423, 363, 351, 290, 227], "partial_last": True}}}
    assert F.ics_line(sheet) == "Sep 26: 290 referrals, lower than the prior 6-month average of 367 (-21%)."
    assert F.ics_line({}) is None


def test_mrpc_counts_primary_and_joint_cardholders_per_month():
    rows = [{"month": m, "primary": p, "joint": j} for m, p, j in [
        ("2026-03", 249, 71), ("2026-04", 247, 70), ("2026-05", 240, 64), ("2026-06", 230, 77),
        ("2026-07", 252, 72), ("2026-08", 235, 79), ("2026-09", 191, 75)]]
    assert F.mrpc_line(rows) == "Sep 26: 266 enrollments, consistent with the prior 6-month average of 314."


def test_cashplease_loans_skip_the_month_the_report_was_generated_in():
    pack = {"report_generated": "10/26/2026 9:25:47 AM", "monthly": [
        {"period_month": m, "loans": n} for m, n in [
            ("2026-10", 3), ("2026-09", 20), ("2026-08", 21), ("2026-07", 21), ("2026-06", 19),
            ("2026-05", 20), ("2026-04", 22), ("2026-03", 19)]]}
    assert F.cp_line(pack) == "Sep 26: 20 loans, consistent with the prior 6-month average of 20."


def test_profitability_is_mentioned_only_below_three_to_one():
    assert F.profitability_phrase(2.1513) == "Profitability 2.15:1, below 3:1."
    assert F.profitability_phrase(3.0) is None
    assert F.profitability_phrase(5.77) is None
    assert F.profitability_phrase(None) is None


def test_the_last_send_is_the_newest_recorded_for_the_client():
    sent = {"1537|2026.08": {"sent_at": "2026-09-01"}, "1537|2026.09": {"sent_at": "2026-09-11"},
            "1075|2026.10": {"sent_at": "2026-10-12"}, "15370|2026.10": {"sent_at": "2026-10-20"}}
    assert F.last_sent(sent, "1537") == ("2026-09-11", "2026.09")
    assert F.last_sent(sent, "1075") == ("2026-10-12", "2026.10")
    assert F.last_sent(sent, "9999") is None


def test_the_tool_rejects_a_bad_client_number(capsys):
    assert F.main(["12x"]) == 2


def test_the_skill_names_a_tool_that_exists_and_keeps_its_two_stops():
    import re
    skill = os.path.join(REPO, ".claude", "skills", "mail-strategy-notes", "SKILL.md")
    text = open(skill, encoding="utf-8").read()
    head = re.match(r"---\nname: ([\w-]+)\ndescription: (.+)\n---\n", text)
    assert head and head.group(1) == "mail-strategy-notes"
    for path in re.findall(r"scripts/\w+\.py", text):
        assert os.path.isfile(os.path.join(REPO, path)), path
    assert text.count("**STOP") >= 2                          # a table before filling, a yes before Submit
    assert "hidden iframe" in text and "ILS" in text
