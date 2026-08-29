"""odd_rows — the shared ODD vocabulary.

These pin the definition that had drifted between metrics_gen and ticket_calc:
a blank `Business?` is NEITHER personal nor business.
"""
import pytest
from odd_rows import accessors, OPEN_STATUSES, CLOSED_STATUSES

H = {"Business?": 0, "Debit?": 1, "Stat Desc": 2,
     "Jul26 Sig #": 3, "Jul26 PIN #": 4, "Jul26 Sig $": 5, "Jul26 PIN $": 6,
     "Jul26 MTD": 7}


def row(business="No", debit="Yes", stat="Open",
        sig_n="0", pin_n="0", sig_d="0", pin_d="0", mtd="0"):
    return [business, debit, stat, sig_n, pin_n, sig_d, pin_d, mtd]


@pytest.fixture
def odd():
    return accessors(H)


# --- the divergence this module exists to prevent -------------------------
@pytest.mark.parametrize("value,personal,business", [
    ("No",  True,  False),
    ("Yes", False, True),
    ("",    False, False),      # blank is NEITHER — the whole point
    ("   ", False, False),
    ("no",  True,  False),      # case-insensitive
    ("YES", False, True),
])
def test_business_flag_is_three_way(odd, value, personal, business):
    r = row(business=value)
    assert odd.personal(r) is personal
    assert odd.business(r) is business


def test_blank_business_is_in_neither_bucket(odd):
    """A blank must not be counted twice, nor land in both denominators."""
    r = row(business="")
    assert not (odd.personal(r) or odd.business(r))


# --- numeric coercion -----------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    ("1,234", 1234.0), ("$45.50", 45.5), ("", 0.0), ("-", 0.0),
    ("  12  ", 12.0), ("garbage", 0.0), ("0", 0.0), ("3.5", 3.5),
])
def test_fnum_coercion(odd, raw, expected):
    assert odd.fnum(row(sig_n=raw), "Jul26 Sig #") == expected


def test_fnum_missing_column_is_zero_not_keyerror(odd):
    assert odd.fnum(row(), "Nov99 Sig #") == 0.0


def test_g_missing_column_is_blank(odd):
    assert odd.g(row(), "No Such Column") == ""


def test_g_handles_short_row(odd):
    assert odd.g(["No"], "Jul26 Sig #") == ""


# --- derived measures -----------------------------------------------------
def test_swipes_sums_signature_and_pin(odd):
    assert odd.swipes(row(sig_n="7", pin_n="5"), "Jul26") == 12.0


def test_spend_sums_signature_and_pin(odd):
    assert odd.spend(row(sig_d="10.25", pin_d="4.75"), "Jul26") == 15.0


def test_nsf_reads_the_mtd_column(odd):
    assert odd.nsf(row(mtd="35"), "Jul26") == 35.0


def test_hascard(odd):
    assert odd.hascard(row(debit="Yes"))
    assert odd.hascard(row(debit="yes"))
    assert not odd.hascard(row(debit="No"))
    assert not odd.hascard(row(debit=""))


# --- status ---------------------------------------------------------------
@pytest.mark.parametrize("stat", sorted(OPEN_STATUSES))
def test_open_statuses_are_open(odd, stat):
    assert odd.isopen(row(stat=stat))


@pytest.mark.parametrize("stat", sorted(CLOSED_STATUSES))
def test_closed_statuses_are_not_open(odd, stat):
    assert not odd.isopen(row(stat=stat))


def test_open_and_closed_vocabularies_do_not_overlap():
    assert not (OPEN_STATUSES & CLOSED_STATUSES)
