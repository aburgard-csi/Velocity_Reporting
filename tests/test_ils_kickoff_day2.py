"""The Day 2 analyses (build/ils_pipeline/kickoff/metrics/day2.py), ported from the ILS Kickoff Day 2 app.

What they compute on a small book, and the rule they were changed to follow on the way in: eligibility
and Reg E opt-in come from CodeConfig, never from a guess.

Every test runs under kickoff/_v5/compat.legacy_strings(), as the entry points do.
"""
import pandas as pd
import pytest

from ils_pipeline.kickoff.core import io
from ils_pipeline.kickoff.metrics import day2


@pytest.fixture(autouse=True)
def _v5_pandas():
    from ils_pipeline.kickoff._v5.compat import legacy_strings
    with legacy_strings():
        yield


def _book():
    """Six personal and three business open accounts, one closed personal one."""
    return pd.DataFrame({
        io.ACCT_NO: range(10),
        io.ACCOUNT_STATUS: ["O"] * 9 + ["C"],
        io.BUSINESS_FLAG: ["P"] * 6 + ["B"] * 3 + ["P"],
        io.STAT_CODE: ["A", "A", "A", "Z", "Z", "A", "A", "Z", "A", "A"],
        io.REG_E_FLAG: ["Y", "N", "Y", "Y", "N", "N", "Y", "N", "N", "Y"],
        io.TOTAL_ITEMS: [0, 3, 8, 15, 30, 60, 0, 5, 13, 2],
        io.PAID_ITEMS: [0, 3, 6, 10, 20, 30, 0, 5, 7, 2],
        io.OD_LIMIT: [500, 500, 1000, 1000, 1000, 500, 1500, 1500, 500, 500],
        io.DEPOSIT_COUNT: [0, 1, 2, 4, 8, 12, 3, 6, 11, 1],
        io.DEPOSIT_AMOUNT: [0.0, 100.0, 250.0, 900.0, 1800.0, 3000.0, 700.0, 4000.0, 9000.0, 50.0],
        io.SWIPES: [0, 5, 10, 20, 40, 2, 1, 0, 3, 9],
        io.OPEN_DATE: ["2019-03-01", "2020-05-02", "2024-01-15", "2025-06-30", "2025-07-01",
                       "2010-01-01", "2023-02-02", "2024-08-08", "2025-09-09", "2025-01-01"],
    })


def _codes(**kw):
    return io.CodeConfig(eligible_stat_codes=["A"], **kw)


def _value(table, measure):
    return table.set_index("Measure").loc[measure, "Value"]


def test_highlights_reads_users_concentration_pay_and_eligibility():
    p = io.personal_open(_book(), _codes())
    h = day2.highlights(p, _codes(rege_opt_in=["Y"]), "Personal")
    assert _value(h, "Open accounts") == 6
    assert _value(h, "Accounts with 1+ OD/NSF item") == 5
    # 116 items; 60 + 30 = 90 >= 75% of them, so two accounts carry three quarters.
    assert _value(h, "Accounts generating 75% of items") == 2
    assert _value(h, "Pay ratio") == round(69 / 116 * 100, 2)
    assert _value(h, "OD-eligible share") == round(4 / 6 * 100, 2)
    assert _value(h, "Reg E opt-in share") == 50.0
    # Account 3 opted in (Y) but sits on Stat Code Z: opted in, no limit.
    assert _value(h, "Reg E opt-ins not OD-eligible") == 1
    assert "'Z'" in h.set_index("Measure").loc["Reg E opt-ins not OD-eligible", "Read"]


def test_an_unconfirmed_opt_in_is_not_read_as_a_guess():
    """The Day 2 app took 'Y' as an opt-in unasked. 1842 carries only 'D'."""
    p = io.personal_open(_book(), _codes())
    h = day2.highlights(p, _codes(), "Personal")
    row = h.set_index("Measure").loc["Reg E opt-in share"]
    assert pd.isna(row["Value"]) and "not confirmed" in row["Read"]
    assert "Reg E opt-ins not OD-eligible" not in set(h["Measure"])
    assert day2.od_status_rege(p, _codes()) is None


def test_an_eligibility_rule_matching_every_account_is_called_not_meaningful():
    p = io.personal_open(_book(), _codes())
    h = day2.highlights(p, io.CodeConfig(eligible_stat_codes=["A", "Z"]), "Personal")
    assert "not meaningful" in h.set_index("Measure").loc["OD-eligible share", "Read"]


def test_od_status_for_reg_e_opt_ins_counts_only_opt_ins():
    p = io.personal_open(_book(), _codes())
    t = day2.od_status_rege(p, _codes(rege_opt_in=["Y"]))
    total = t[t.iloc[:, 0] == "Grand Total"].iloc[0]
    assert total["# of Accounts"] == 3 and total["Total OD/NSF Items"] == 23


def test_year_opened_counts_every_status_for_the_segment():
    t = day2.year_opened(_book(), _codes(), "P")
    total = t[t["Year Opened"] == "Grand Total"].iloc[0]
    assert (total["Open"], total["Not Open"], total["Total"]) == (6, 1, 7)
    row_2025 = t[t["Year Opened"] == "2025"].iloc[0]
    assert (row_2025["Open"], row_2025["Not Open"]) == (2, 1)
    # 2010 is exactly fifteen years back, so it is the first cohort shown and the "<2010" row is empty and dropped.
    assert t["Year Opened"].iloc[0] == "2010" and t["Open"].iloc[0] == 1
    older = day2.year_opened(_book(), _codes(), "P", first_year=2020)
    assert older["Year Opened"].iloc[0] == "<2020" and older["Total"].iloc[0] == 2


def test_reg_e_by_year_carries_a_rate_only_when_opt_in_is_confirmed():
    p = io.personal_open(_book(), _codes())
    t = day2.rege_by_year(p, _codes(rege_opt_in=["Y"]))
    total = t[t["Year Opened"] == "Grand Total"].iloc[0]
    assert total["# of Accounts"] == 6 and total["Reg E Y"] == 3 and total["% Opted In"] == 50.0
    assert "% Opted In" not in day2.rege_by_year(p, _codes()).columns


def test_without_an_open_date_the_year_tables_are_skipped():
    df = _book().drop(columns=[io.OPEN_DATE])
    assert day2.year_opened(df, _codes(), "P") is None
    assert day2.rege_by_year(io.personal_open(df, _codes()), _codes()) is None


@pytest.mark.parametrize("values, expected", [
    ([0.5, 0.6, 0.7, 0.8, 0.9, 0.95], "up"),
    ([0.95, 0.9, 0.8, 0.7, 0.6, 0.5], "down"),
    ([0.8, 0.81, 0.8, 0.79, 0.8, 0.8], "flat"),
])
def test_trend_reads_the_shape_across_the_bands(values, expected):
    t = pd.DataFrame({"NSF Bin": list("abcdef") + ["Grand Total"], "Pay Ratio": values + [0.0]})
    assert day2.trend(t, "Pay Ratio") == expected
