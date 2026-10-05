"""Which accounts a Lift Matrix is valued on (Aaron, 2026-10-05).

"For Lift Matrix builds we're only building the values based on Personal accounts. Default
to all accounts and add a variable at the top to do Personal, Business, or Both."

The default is BOTH, which is what the module already did — ARS eligibility and holding a
debit card were the only account filters, and business accounts were added on 2026-09-25.
What is new is that it is a choice, stated at the top, and recorded in the result so a
matrix can never be read without knowing what it was valued on.
"""
import types

import pytest

import lift_values as L


def row(business):
    """A row stand-in: only `Business?` matters here."""
    return types.SimpleNamespace(business=business)


class FakeOdd:
    """The row vocabulary's personal/business, which read the client's own Business? column."""
    @staticmethod
    def personal(r):
        return r.business == "No"

    @staticmethod
    def business(r):
        return r.business == "Yes"


PERSONAL, BUSINESS, BLANK = row("No"), row("Yes"), row("")


def test_the_default_is_every_account():
    """The default must not narrow what the module already valued."""
    assert L.POPULATION == "both"
    for r in (PERSONAL, BUSINESS, BLANK):
        assert L.in_population(FakeOdd, r) is True


@pytest.mark.parametrize("choice, keeps, drops", [
    ("personal", [PERSONAL], [BUSINESS, BLANK]),
    ("business", [BUSINESS], [PERSONAL, BLANK]),
    ("both", [PERSONAL, BUSINESS, BLANK], []),
])
def test_each_setting_keeps_what_it_says(choice, keeps, drops):
    for r in keeps:
        assert L.in_population(FakeOdd, r, choice), choice
    for r in drops:
        assert not L.in_population(FakeOdd, r, choice), choice


def test_a_blank_business_flag_is_neither_personal_nor_business():
    """It is not guessed at: valued under "both", left out of the other two. The ODD carries
    accounts whose Business? is empty, and calling one personal would put it in a matrix the
    client would read as consumer-only."""
    assert L.in_population(FakeOdd, BLANK, "both")
    assert not L.in_population(FakeOdd, BLANK, "personal")
    assert not L.in_population(FakeOdd, BLANK, "business")


def test_a_setting_that_is_not_one_of_the_three_stops_the_build():
    """A typo must not quietly value every account: the matrix goes to Bradford."""
    with pytest.raises(SystemExit) as e:
        L.in_population(FakeOdd, PERSONAL, "consumer")
    assert "must be one of" in str(e.value)


def test_the_choice_is_spelled_out_for_the_file_and_the_tab():
    assert set(L.POPULATIONS) == {"both", "personal", "business"}
    assert L.POPULATION in L.POPULATIONS


def test_scan_takes_the_population_as_an_argument():
    """Sheila and build_lift_matrix can ask for one without editing the module."""
    import inspect
    assert "population" in inspect.signature(L.scan).parameters
