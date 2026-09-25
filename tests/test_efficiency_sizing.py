"""Revenue per 1,000 offers, and the +5-point sizing (2026-09-21).

The efficiency view joins two files with different owners — offer counts from the ODD,
booked revenue from the workbook — so the tests are mostly about what happens when a mailing
appears in one and not the other. The sizing tests are about not inventing money.
"""
import pytest

import combined_insights as CI
from odd_rows import accessors

MAILMONTHS = ["Mar26", "Jun26"]
COLS = ["Business?", "Debit?", "Mar26 Mail", "Jun26 Mail"]
H = {c: i for i, c in enumerate(COLS)}
ODD = accessors(H)


def row(mar="", jun=""):
    r = [""] * len(COLS)
    r[H["Business?"]] = "No"
    r[H["Mar26 Mail"]] = mar
    r[H["Jun26 Mail"]] = jun
    return r


def wave(entries):
    return {"available": True,
            "waves": [{"m": m, "key": k, "revenue": rev, "months": mo, "per_month": 0,
                       "build": [], "by_month": {}}
                      for m, k, rev, mo in entries]}


ROWS = [row(mar="TH-10"), row(mar="NU"), row(mar="TH-10", jun="TH-15"), row()]


def test_offers_are_accounts_carrying_a_code_that_month():
    assert CI.offers_by_month(ROWS, ODD, MAILMONTHS) == {"Mar26": 3, "Jun26": 1}


def test_revenue_per_thousand_uses_that_mailings_own_offer_count():
    eff = CI.offer_efficiency(ROWS, ODD, MAILMONTHS,
                              wave([("Mar 2026", "2026-03", 300.0, 6)]))
    assert eff["mailings"][0]["per_1k"] == pytest.approx(100_000.0)     # 300 / 3 * 1000


def test_a_mailing_the_extract_has_no_offers_for_is_reported_not_divided():
    """The two halves come from different files. Dividing a workbook mailing by another
    month's offer count would be silently wrong, and wrong in a plausible-looking way."""
    eff = CI.offer_efficiency(ROWS, ODD, MAILMONTHS,
                              wave([("Mar 2026", "2026-03", 300.0, 6),
                                    ("Jan 2020", "2020-01", 999.0, 60)]))
    assert [m["month"] for m in eff["mailings"]] == ["Mar 2026"]
    assert eff["unmatched_revenue"] == ["Jan 2020"]


def test_offers_with_no_booked_revenue_are_reported_too():
    eff = CI.offer_efficiency(ROWS, ODD, MAILMONTHS,
                              wave([("Mar 2026", "2026-03", 300.0, 6)]))
    assert eff["unmatched_offers"] == ["Jun 2026"]


def test_no_workbook_means_no_view_rather_than_a_guess():
    eff = CI.offer_efficiency(ROWS, ODD, MAILMONTHS,
                              {"available": False, "reason": "no ARS workbook was found"})
    assert eff["available"] is False and "workbook" in eff["reason"]


# ------------------------------------------------------------------ sizing
BOOK = {"available": True, "eligible": 10_000, "take_all": 80.0,
        "rege_pool": 8_000, "rege_all": 30.0}


def test_the_account_figures_are_exact_arithmetic():
    sz = CI.sizing(BOOK, {"months": 100, "ltd_revenue": 8_000_000})
    assert sz["take_accounts"] == 500          # 5% of 10,000 eligible
    assert sz["rege_accounts"] == 400          # 5% of the 8,000 card holders
    assert sz["take_headroom"] == 20.0


def test_the_money_uses_the_programs_own_revenue_per_card():
    sz = CI.sizing(BOOK, {"months": 100, "ltd_revenue": 8_000_000})
    assert sz["cards"] == 8_000                # 80% of 10,000
    assert sz["per_card_month"] == pytest.approx(10.0)      # 8M / 100 months / 8,000 cards
    assert sz["take_annual"] == 60_000                      # 500 cards x $10 x 12


def test_no_workbook_revenue_means_accounts_only_and_no_money():
    """A sizing slide that prints a dollar figure it cannot support is worse than one that
    prints none."""
    sz = CI.sizing(BOOK, {})
    assert sz["take_accounts"] == 500
    assert sz["per_card_month"] is None and sz["take_annual"] is None


def test_an_empty_book_is_not_sized():
    assert CI.sizing({"available": False}, {"months": 10, "ltd_revenue": 1})["available"] is False


def test_the_reg_e_what_if_never_carries_a_dollar_figure():
    """The ODD carries NSF/OD items but no fee dollars, so any money on the opt-in side
    would be invented. Pinned because it is exactly the number someone will ask for."""
    sz = CI.sizing(BOOK, {"months": 100, "ltd_revenue": 8_000_000})
    assert not any(k.startswith("rege") and k.endswith(("annual", "value", "money"))
                   for k in sz)


def test_both_slides_are_in_the_opt_in_set():
    import inspect
    import combined_insight_slides as CIS
    src = inspect.getsource(CIS.add_insight_slides)
    assert "efficiency_slide(prs, ci, ctx)" in src
    assert "sizing_slide(prs, ci, ctx)" in src
