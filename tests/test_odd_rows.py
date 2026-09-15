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


# Stat Desc case and the Stat Code fallback (2026-09-14). isopen was case-sensitive and never
# read the code, so 1637 ('open'), 1680 ('ACTIVE'), 1759 ('OPEN/ACTIVE') and 1743/1746/1815
# (blank Stat Desc, code A/O) had no open account at all, while status_class and the pack
# classifier beside it read them correctly.
HC = dict(H, **{"Stat Code": 8})


def crow(stat="", code=""):
    return row(stat=stat) + [code]


@pytest.mark.parametrize("stat", ["open", "ACTIVE", "OPEN/ACTIVE", "inactive", "DORMANT", "Open - Restricted"])
def test_open_wording_is_read_in_any_case(stat):
    assert accessors(HC).isopen(crow(stat=stat))


@pytest.mark.parametrize("stat", ["closed", "CLOSED", "CHARGEOFF", "Account Closed"])
def test_closed_wording_is_not_open_in_any_case(stat):
    assert not accessors(HC).isopen(crow(stat=stat))


@pytest.mark.parametrize("code,is_open", [("A", True), ("O", True), ("a", True),
                                          ("C", False), ("X", False),
                                          ("D", False), ("I", False), ("0", False), ("", False)])
def test_a_blank_description_falls_back_to_the_confirmed_codes_only(code, is_open):
    """O / A = Open are Aaron-confirmed (STAT_CODE_MAP). An unmapped code is not guessed open."""
    assert accessors(HC).isopen(crow(stat="", code=code)) is is_open


def test_the_description_wins_over_the_code():
    assert not accessors(HC).isopen(crow(stat="Closed", code="A"))
    assert accessors(HC).isopen(crow(stat="Open", code="C"))


def test_no_stat_code_column_leaves_a_blank_description_not_open(odd):
    assert not odd.isopen(row(stat=""))


# --- the optimised accessors must behave exactly like the originals -----------
# odd_rows is the ONE vocabulary shared by metrics_gen, the slide builders and
# responder_activity, and it exists because three separate implementations of it
# drifted. The accessors were made cheaper on 2026-09-11 (constant columns bound
# once, per-month column indices cached, fnum trying float() first); these pin the
# equivalence against a literal transcription of the pre-optimisation code, since
# "it still runs" would not have caught a changed edge case.
import pytest as _pytest

_H = {"Business?": 0, "Debit?": 1, "Stat Desc": 2,
      "Jul26 Sig #": 3, "Jul26 PIN #": 4, "Jul26 Sig $": 5, "Jul26 PIN $": 6,
      "Jul26 MTD": 7, "Bal": 8}

# Every shape a real ODD cell has come in, plus the ones that broke something once.
_CELLS = ["", " ", "0", "1234", " 1234 ", "-", "1,234", "$50", "$1,234.56", "12.5",
          "-3", "1e5", "abc", "  ", "0.0", "00012", "1 234", "--", "(500)", "12,",
          ",5", "$", "1.2.3", "\t7\t"]


def _ref_g(r, name):
    """The original g(), transcribed."""
    i = _H.get(name)
    return r[i].strip() if i is not None and i < len(r) else ""


def _ref_fnum(r, name):
    """The original fnum(), transcribed."""
    v = _ref_g(r, name).replace(",", "").replace("$", "")
    if v in ("", "-"):
        return 0.0
    try:
        return float(v)
    except ValueError:
        return 0.0


@_pytest.mark.parametrize("cell", _CELLS)
def test_g_and_fnum_match_the_originals(cell):
    A = accessors(_H)
    row = [cell] * 9
    for name in list(_H) + ["Missing Col"]:
        assert A.g(row, name) == _ref_g(row, name), (cell, name)
        assert A.fnum(row, name) == _ref_fnum(row, name), (cell, name)


@_pytest.mark.parametrize("cell", _CELLS)
def test_month_helpers_match_their_original_composition(cell):
    """swipes/spend/nsf used to build the column name with an f-string on every
    call; they read a cached index now. Same sums, including for an absent month."""
    A = accessors(_H)
    row = [cell] * 9
    assert A.swipes(row, "Jul26") == _ref_fnum(row, "Jul26 Sig #") + _ref_fnum(row, "Jul26 PIN #")
    assert A.spend(row, "Jul26") == _ref_fnum(row, "Jul26 Sig $") + _ref_fnum(row, "Jul26 PIN $")
    assert A.nsf(row, "Jul26") == _ref_fnum(row, "Jul26 MTD")
    assert A.swipes(row, "Nov99") == 0.0      # month not in the header map at all


@_pytest.mark.parametrize("cell", ["Yes", "yes", "YES", "No", "no", "", " no ", "Maybe"])
def test_flags_match_the_originals(cell):
    """These bind their column index once instead of looking it up per row."""
    A = accessors(_H)
    row = [cell, cell, cell]
    assert A.personal(row) == (_ref_g(row, "Business?").lower() == "no")
    assert A.business(row) == (_ref_g(row, "Business?").lower() == "yes")
    assert A.hascard(row) == (_ref_g(row, "Debit?").lower() == "yes")


def test_short_and_empty_rows_are_tolerated():
    """A truncated row must not raise: the ODD does ship ragged lines."""
    A = accessors(_H)
    for row in (["Yes"], []):
        A.g(row, "Bal"); A.fnum(row, "Bal")
        A.swipes(row, "Jul26"); A.spend(row, "Jul26"); A.nsf(row, "Jul26")
        A.personal(row); A.business(row); A.hascard(row); A.isopen(row)


def test_a_missing_header_map_entry_is_not_an_error():
    A = accessors({})
    r = ["x", "y", "z"]
    assert A.g(r, "Bal") == "" and A.fnum(r, "Bal") == 0.0
    assert A.swipes(r, "Jul26") == 0.0 and A.personal(r) is False
