"""The ARS 2 : 1 revenue guarantee (Aaron, 2026-09-21; reworked 2026-09-22).

Two rules from Aaron shape this: the figures come from the workbook's **Actuals tab**, month
by month, and the slide is built **only for clients under 3 : 1** — a client comfortably
clear of the guarantee does not need a slide about a floor they cleared years ago.

The arithmetic is the point of these tests: a months-to-cover figure that ignores the cost
accruing over those same months would print a date no client will ever see come true, and
the caption must never describe a shortfall as room above the guarantee.

Synthetic clients, round numbers.
"""
import math

import pytest

import revenue_guarantee_slide as RG


def months(n, rev, cost, start=(2025, 1)):
    """n months of flat revenue and cost, oldest first, as the Actuals reader returns them."""
    names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    out, y, m = [], start[0], start[1] - 1
    for _ in range(n):
        out.append([f"{names[m]} {y}", rev, cost])
        m += 1
        if m == 12:
            m, y = 0, y + 1
    return out


def base(month_rows=None, profitability=None, **kw):
    B = dict(kw)
    if month_rows is not None:
        B["actuals"] = {"available": True, "sheet": "Actuals MM", "months": month_rows,
                        "window": [month_rows[0][0], month_rows[-1][0]], "total_column": None}
    if profitability is not None:
        B["profitability"] = profitability
    return B


# ------------------------------------------------------------------ who gets the slide
@pytest.mark.parametrize("ratio, built", [
    (1.58, True), (2.99, True), (3.0, False), (3.01, False), (5.72, False)])
def test_only_a_client_under_three_to_one_gets_the_slide(ratio, built):
    assert RG.should_build(base(profitability=ratio)) is built


def test_the_gate_reads_the_ratio_the_deck_itself_states():
    """A client cannot see "5.7 : 1" on Financial Performance and a guarantee slide on the
    next one, so the gate reads the same figure that bullet does."""
    B = base(months(24, 9_000, 1_000), profitability=5.72)
    assert RG.ratio_of(B) == 5.72
    assert RG.should_build(B) is False


def test_without_a_stated_ratio_the_gate_falls_back_to_the_actuals():
    B = base(months(24, 9_000, 5_000))
    assert RG.ratio_of(B) == pytest.approx(1.8)
    assert RG.should_build(B) is True


def test_a_client_with_no_cost_is_not_measured_and_not_built():
    assert RG.should_build(base(months(6, 1_000, 0))) is False


# ------------------------------------------------------------------ the figures
def test_the_figures_come_from_the_actuals_months():
    g = RG.guarantee(base(months(12, 10_000, 2_000)))
    assert g["source"] == "actuals" and g["sheet"] == "Actuals MM"
    assert (g["revenue"], g["cost"], g["minimum"]) == (120_000, 24_000, 48_000)
    assert g["ratio"] == pytest.approx(5.0)
    assert g["met"] is True and g["surplus"] == 72_000


def test_it_falls_back_to_the_rollup_when_a_workbook_has_no_actuals_tab():
    g = RG.guarantee({"ltd_revenue": 150_000, "ltd_costs": -100_000, "months": 24})
    assert g["source"] == "rollup"
    assert (g["revenue"], g["cost"]) == (150_000, 100_000)
    assert g["gap"] == 50_000


def test_a_short_program_reports_the_gap_not_a_surplus():
    g = RG.guarantee(base(months(12, 12_000, 8_000)))
    assert g["met"] is False
    assert g["gap"] == 48_000 and g["surplus"] is None
    cap = RG._caption(g)
    assert "short of the guaranteed minimum" in cap and "above" not in cap


def lean_then_good(lean=24, good=12):
    """A program that started badly and is now earning: short of the guarantee overall, with
    a recent run rate that closes the gap. Flat-good months alone would be ABOVE 2 : 1 and
    the guarantee would be met, which answers a different question."""
    return (months(lean, 1_000, 5_000)
            + months(good, 12_000, 4_000, start=(2027, 1)))


def test_months_to_cover_accrues_cost_over_the_same_months():
    # recent months: $12k of revenue against $4k of cost, so each closes 12k - 2*4k = 4k
    g = RG.guarantee(base(lean_then_good()))
    assert g["met"] is False
    assert g["run_rate"] == pytest.approx(12_000)
    assert g["monthly_cost"] == pytest.approx(4_000)
    assert g["months_to_cover"] == math.ceil(g["gap"] / 4_000)
    # gap / run rate alone would have said a third of that — the number that ignores cost
    assert g["months_to_cover"] > math.ceil(g["gap"] / 12_000)


def test_a_gap_that_never_closes_says_so():
    # $7k of revenue a month against $4k of cost: the minimum rises $8k over the same month
    g = RG.guarantee(base(months(24, 7_000, 4_000)))
    assert g["months_to_cover"] is None
    cap = RG._caption(g)
    assert "does not close" in cap and "closes in about" not in cap


def test_the_run_rate_reads_the_last_twelve_complete_months():
    rows = months(24, 1_000, 5_000) + months(12, 8_000, 4_000, start=(2027, 1))
    rows[-6:] = [[m[0], 16_000, 4_000] for m in rows[-6:]]     # a recent step up
    g = RG.guarantee(base(rows))
    assert g["met"] is False
    assert g["run_months"] == 12
    assert g["run_rate"] == pytest.approx((6 * 8_000 + 6 * 16_000) / 12)
    # the 24 lean months before the window are in the TOTALS but not in the run rate
    assert g["revenue"] == 24 * 1_000 + 6 * 8_000 + 6 * 16_000


def test_a_partial_final_month_is_left_out_and_stated():
    rows = months(24, 1_000, 5_000) + months(12, 12_000, 4_000, start=(2027, 1))
    rows[-1][1] = 200                                          # the month the pull cut short
    g = RG.guarantee(base(rows))
    assert g["left_out"] == [rows[-1][0]]
    assert f"{rows[-1][0]} left out: incomplete in this extract." in RG._caption(g)


def test_the_crossing_month_is_the_latest_one():
    """A program can meet the guarantee, slip under it and meet it again. The earlier
    crossings are history the client has already banked."""
    rows = (months(6, 10_000, 1_000)
            + months(6, 1_000, 20_000, start=(2025, 7))
            + months(12, 40_000, 1_000, start=(2026, 1)))
    g = RG.guarantee(base(rows))
    assert g["met"] is True
    assert g["met_month"] is not None and g["met_month"].endswith("2026")


def test_no_cost_booked_is_stated_never_zeroed():
    g = RG.guarantee(base(months(6, 0, 0)))
    assert g["measurable"] is False
    assert g["ratio"] is None and g["met"] is None
    cap = RG._caption(g)
    assert "no program cost to date" in cap and "0 : 1" not in cap


def test_the_multiple_and_the_threshold_live_in_one_place():
    assert (RG.MULTIPLE, RG.SHOW_BELOW) == (2.0, 3.0)
    g = RG.guarantee(base(months(6, 5_000, 1_000)))
    assert g["minimum"] == RG.MULTIPLE * g["cost"]


# ------------------------------------------------------------------ the slide
def test_every_tile_label_fits_inside_its_tile():
    """Three labels wrapped out of their tiles onto the slide behind them, on a deck the
    gate passed at 0 FAIL. A label is measured at what is DRAWN — 16pt after restyle_fonts,
    inside PowerPoint's own margins — not at what it is authored as."""
    for label in ("Program cost, to date", "Guaranteed minimum", "Revenue, to date",
                  "Short of the guarantee", "Above the guarantee", "Not measurable yet"):
        assert RG._fits(label), label


def test_the_chart_renders_from_months_and_from_totals(tmp_path):
    import os
    lines = RG.render_chart(RG.guarantee(base(months(24, 10_000, 3_000))), str(tmp_path))
    assert os.path.getsize(lines) > 5000
    bars = RG.render_chart(RG.guarantee({"ltd_revenue": 9.0, "ltd_costs": -4.0}), str(tmp_path))
    assert os.path.getsize(bars) > 3000


def test_the_builder_gates_on_should_build():
    import os
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "build", "ars_pipeline", "build_ars_gen.py"),
               encoding="utf-8").read()
    assert "if revenue_guarantee_slide.should_build(B):" in src
    assert 'after_title="Financial Performance"' in src
    assert "_MODULE_NOTED.append(_rg_slide)" in src       # its note is its own


def test_the_guarantee_slide_is_on_every_ars_deck_under_three_to_one():
    """Aaron, 2026-09-25: "I do still want the two-to-one guarantee slide included for clients less
    than three-to-one, period." It is not one of the opt-in James views."""
    import os
    src = open(os.path.join(os.path.dirname(RG.__file__), "build_ars_gen.py"), encoding="utf-8").read()
    block = src[src.index("import revenue_guarantee_slide"):src.index("_S2 = list(prs.slides)")]
    assert "RPE_JAMES_SLIDES" not in block
    assert "if revenue_guarantee_slide.should_build(B):" in block
    assert RG.SHOW_BELOW == 3.0
