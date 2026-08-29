"""build_month — the monthly roster driver.

clients.md's own rule is "this file decides what gets built, not the presence of
a data file". A driver carrying its own list would be a second answer to that
question, so the roster is parsed from the file — and parsed by SECTION, because
a row's meaning comes from the heading it sits under, not its column count.
"""
import os
import pytest
from build_month import read_roster, deck_tag, deck_name, delivered_names, _NAME_RX

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def roster():
    return read_roster()[0]


@pytest.fixture(scope="module")
def skipped():
    return read_roster()[1]


def ids(rows):
    return {r[0] for r in rows}


# --- the roster is read, not assumed -------------------------------------
def test_active_clients_are_found(roster):
    assert ids(roster) >= {"1038", "1075", "1204", "1509", "1537",
                           "1539", "1549", "1676", "1705"}


def test_ics_only_clients_are_found(roster):
    """These sit in a FOUR-column table; a column-count parser missed all three."""
    assert ids(roster) >= {"1632", "1734", "1738"}


def test_mrpc_only_clients_are_found(roster):
    assert ids(roster) >= {"1218", "1477", "1502"}


@pytest.mark.parametrize("cid,reason", [
    ("1437", "no further reviews"),
    ("1174", "off the books"),
    ("1658", "no RPE at all"),
])
def test_stopped_clients_are_not_built(cid, reason, roster):
    assert cid not in ids(roster), f"{cid} should not build — {reason}"


def test_unknown_client_1732_is_not_built(roster):
    """clients.md lists it as an unresolved gap; nothing is built until confirmed."""
    assert "1732" not in ids(roster)


def test_stopped_clients_are_reported_not_silently_dropped(skipped):
    """An unbuilt roster line is exactly what clients.md exists to prevent."""
    assert {"1437", "1174", "1658"} <= ids(skipped)


# --- program shapes ------------------------------------------------------
@pytest.mark.parametrize("cid,expected", [
    ("1038", ["ARS"]),
    ("1075", ["ARS", "ICS", "MRPC"]),
    ("1705", ["ARS"]),                       # ICS cancelled 2026-08-28
    ("1549", ["ARS", "ICS-REFERRALS"]),      # live before its first workbook
    ("1218", ["MRPC"]),
    ("1738", ["ICS-REFERRALS"]),             # no workbook on file
])
def test_program_shape(cid, expected, roster):
    got = next(r[3] for r in roster if r[0] == cid)
    assert got == expected


def test_cancelled_program_is_dropped_but_the_client_stays(roster):
    """CoastLife 1705 keeps ARS; only its ICS section stopped."""
    assert next(r[3] for r in roster if r[0] == "1705") == ["ARS"]


@pytest.mark.parametrize("progs,tag", [
    (["ARS"], "ARS"),
    (["ARS", "ICS"], "ARS-ICS"),
    (["ARS", "ICS-REFERRALS"], "ARS-ICS"),
    (["ARS", "ICS", "MRPC"], "ARS-ICS-MRPC"),
])
def test_deck_tag(progs, tag):
    assert deck_tag(progs) == tag


def test_mm_sm_path_is_read(roster):
    paths = {r[0]: r[2] for r in roster}
    assert paths["1038"] == "SM" and paths["1204"] == "MM"


# --- deck naming ---------------------------------------------------------
@pytest.mark.parametrize("filename,cid,name", [
    ("1204-2026.08-ARS-FSB Michigan ARS Results", "1204", "FSB Michigan"),
    ("1075-2026.08-ARS-ICS-MRPC-Austin Bank Results", "1075", "Austin Bank"),
    ("1632-2026.08-ICS-WesBanco ICS Results", "1632", "WesBanco"),
    ("1676-2026.08-ARS-ICS-True Sky CU Results (superseded 2026-08-29)",
     "1676", "True Sky CU"),
])
def test_deck_name_is_read_back_from_a_filename(filename, cid, name):
    m = _NAME_RX.match(filename)
    assert m and m.group(1) == cid and m.group(2).strip() == name


def test_delivered_name_wins_over_the_roster_name():
    """1204 ships as "FSB Michigan" while its workbook says "First State
    Bank-MI", and 1509 ships as "Texas Bay Credit Union" while clients.md says
    "Texas Bay CU". Renaming a client's deck is a delivery decision."""
    n, src = deck_name("1204", "FSB Michigan", {"1204": "FSB Michigan"})
    assert (n, src) == ("FSB Michigan", "delivered")
    n, src = deck_name("1509", "Texas Bay CU", {"1509": "Texas Bay Credit Union"})
    assert (n, src) == ("Texas Bay Credit Union", "delivered")


def test_a_new_client_falls_back_to_the_roster_name():
    n, src = deck_name("9999", "Brand New Bank", {})
    assert (n, src) == ("Brand New Bank", "clients.md")
