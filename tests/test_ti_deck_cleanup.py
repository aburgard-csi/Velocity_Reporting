"""The small fixes of the Transaction Intelligence deck cleanup (Aaron, 2026-11-02), pinned. Synthetic figures.

* the attrition-by-branch chart draws the branches the headline and footnote already rate (150+ accounts at
  risk): a branch of one account that closed read 100% and set the scale for twelve real ones;
* ti/slides.json lists every slide it tosses with a reason, and every combined slide it carries.
"""
import json
import os

from ti.deck import attrition_inline as I

HERE = os.path.dirname(__file__)
SLIDES = os.path.join(HERE, "..", "build", "ars_pipeline", "ti", "slides.json")


ROWS = [["Santa Maria", 10856, 728, 6.7], ["Lompoc", 10319, 652, 6.3], ["Grand Ave", 1335, 127, 9.5],
        ["Lending Center", 35, 14, 40.0], ["14", 1, 1, 100.0]]


def test_the_branch_chart_leaves_out_branches_too_small_to_rank():
    assert [r[0] for r in I._rated(ROWS)] == ["Santa Maria", "Lompoc", "Grand Ave"]


def test_with_fewer_than_three_rated_branches_every_branch_is_drawn_as_before():
    two = [ROWS[0], ROWS[1], ROWS[3], ROWS[4]]
    assert I._rated(two) == two


def test_the_floor_is_the_one_the_headline_names():
    from ti.monthly_analysis.attrition import MIN_AT_RISK_FOR_BRANCH_RANK
    assert MIN_AT_RISK_FOR_BRANCH_RANK == 150
    at_floor = [["a", 150, 1, 1.0], ["b", 149, 1, 1.0], ["c", 500, 1, 1.0], ["d", 900, 1, 1.0]]
    assert [r[0] for r in I._rated(at_floor)] == ["a", "c", "d"]


def test_every_toss_of_the_cleanup_has_a_reason_and_every_combined_slide_is_listed():
    data = json.load(open(SLIDES, encoding="utf-8"))
    why = data["_tossed_2026-11-02"]
    assert why and all(data["slides"][t] == "toss" for t in why)
    assert all(reason.strip() for reason in why.values())
    for title, parts in data["_combined_2026-11-02"]["pairs"].items():
        assert data["slides"][title] == "keep"
        assert len(parts) == 2 and all(p in data["slides"] for p in parts)
