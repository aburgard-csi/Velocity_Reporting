"""R3 (James, 2026-11-04): "category summary slides / drill downs". One slide per leading
addressable category, from figures already in the pack. Pinned: which categories qualify, the
lens it over-indexes in (with a minimum base), the split by line when the category has one, and
the decline when nothing qualifies.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ti.deck import txn_leakage as L  # noqa: E402
from test_ti_hotspot_slides import _Harness  # noqa: E402

BASE = "transacting personal accounts"


def _cat(name, accts, dollars, kind="leakage", addressable=True):
    return [name, accts, accts / 640, accts * 5, dollars, round(dollars / accts), kind, addressable, None, 50.0]


T = {
    "fin_by_category": [
        _cat("Credit Cards", 5_000, 6_000_000), _cat("Auto Loans", 3_000, 9_000_000),
        _cat("Insurance", 12_000, 15_000_000), _cat("Tax & Accounting", 4_000, 2_000_000, addressable=False),
        _cat("Crypto/Digital Assets", 60, 900_000), _cat("P2P Transfers", 30_000, 70_000_000, kind="adjacency"),
        _cat("Mortgage/HELOC", 1_500, 8_000_000), _cat("Personal Loans", 900, 1_000_000),
        _cat("Student Loans", 700, 500_000)],
    "fin_top_providers": {"Auto Loans": [["(unnamed)", 400, 2_000_000], ["ALLY FINANCIAL", 900, 3_600_000],
                                         ["TOYOTA FINANCIAL", 500, 1_800_000]]},
    "fin_recency": [["Auto Loans", 1_800, 600, 300, 300]],
    "fin_new_recurring_stopped": [["Auto Loans", 250, 2_500, 250]],
    "fin_leakers_profile": [["Auto Loans", 3_000, 4_200, 9_000_000, 6.5, 12.0]],
    "fin_by_lens": [["all", "All accounts", 64_000], ["responders", "Responders", 5_000],
                    ["new_accounts", "Opened last 12 mo", 150]],
    "fin_by_lens_category": [["all", "Auto Loans", 3_000, 4.7], ["responders", "Auto Loans", 450, 9.0],
                             ["new_accounts", "Auto Loans", 30, 20.0]],
    "fin_subtypes": {"Insurance": [["Auto", 4_000, 33.0, 9_000, 6_000_000, 40.0, ["GEICO"]],
                                   ["Unspecified", 900, 7.5, 2_000, 900_000, 6.0, ["INS PREM"]]]},
}


def test_the_leading_addressable_categories_with_enough_accounts_qualify():
    names = [r[0] for r in L.drilldown_categories(T)]
    # by dollars; not tax (not addressable), P2P (adjacency) or crypto (60 accounts)
    assert names == ["Insurance", "Auto Loans", "Mortgage/HELOC", "Credit Cards", "Personal Loans"]


def test_a_drilldown_names_its_lead_provider_recency_and_the_lens_it_over_indexes_in():
    h = _Harness()
    h["RIGHT_EDGE"] = 12.73
    L.category_drilldowns(h, T, BASE)
    assert len(h.slides) == 5 and all(title == "Category drill-down" for _, title in h.slides)
    (head, sub), _ = h.slides[1]
    assert head == ("Auto Loans: 3,000 transacting personal accounts pay $9.0M, and Ally Financial "
                    "takes 40% of it")
    assert "80% paid in the last 90 days" in sub
    assert "250 started in the last 90 days, 250 stopped" in sub
    # new accounts over-index more (20%) but on a base of 150: too small to name
    assert "most over-represented in responders (9% against 5% of all accounts)" in sub
    rail = [r[0] for r in h.rails[1]]
    assert rail == ["Accounts", "Dollars", "Still paying", "Median balance with us", "Over-indexes in"]
    assert [b[0] for b in h.charts[1]["rows"]] == ["Ally Financial", "Toyota Financial"]   # "(unnamed)" left out


def test_a_category_split_by_line_draws_its_lines():
    h = _Harness()
    h["RIGHT_EDGE"] = 12.73
    L.category_drilldowns(h, T, BASE)
    assert [b[0] for b in h.charts[0]["rows"]] == ["Auto", "Unspecified"]


def test_nothing_qualifying_is_a_stated_decline():
    out = L.category_drilldowns(_Harness(), {"fin_by_category": [_cat("Crypto/Digital Assets", 60, 9)]}, BASE)
    assert out.startswith("Category drill-down (no addressable category with 100+")
