"""build_month — the monthly roster driver.

clients.md's own rule is "this file decides what gets built, not the presence of
a data file". A driver carrying its own list would be a second answer to that
question, so the roster is parsed from the file — and parsed by SECTION, because
a row's meaning comes from the heading it sits under, not its column count.
"""
import os
import pytest
from build_month import read_roster, deck_tag, deck_name

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


def test_1732_is_not_built(roster):
    """Confirmed not an RPE client at all (Aaron, 2026-08-30). It was named as
    ICS-only on 2026-08-28 and no data for it ever existed here. The assertion
    stays: it was on a list once, and a roster edit that reintroduced it would
    otherwise build a client that does not exist."""
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
    # CashPlease as a SECTION comes from the CashPlease roster's "Ships as" column (2026-10-12):
    # build_month never read it, so 1632 and 1734 built as plain ICS decks.
    ("1632", ["ICS", "CP"]),
    ("1734", ["ICS", "CP"]),
    ("1539", ["ARS", "ICS", "MRPC", "CP"]),
    ("1542", ["ARS", "MRPC", "CP"]),
])
def test_program_shape(cid, expected, roster):
    got = next(r[3] for r in roster if r[0] == cid)
    assert got == expected


def test_a_standalone_cashplease_client_is_not_added_to_the_roster(roster):
    """1131 ships a standalone CashPlease module (build_cashplease.py), not a section."""
    assert "1131" not in ids(roster)


def test_cancelled_program_is_dropped_but_the_client_stays(roster):
    """CoastLife 1705 keeps ARS; only its ICS section stopped."""
    assert next(r[3] for r in roster if r[0] == "1705") == ["ARS"]


@pytest.mark.parametrize("progs,tag", [
    (["ARS"], "ARS"),
    (["ARS", "ICS"], "ARS-ICS"),
    (["ARS", "ICS-REFERRALS"], "ARS-ICS"),
    (["ARS", "ICS", "MRPC"], "ARS-ICS-MRPC"),
    (["ICS", "CP"], "ICS-CP"),
    (["ICS-REFERRALS", "MRPC"], "ICS-MRPC"),
])
def test_deck_tag(progs, tag):
    assert deck_tag(progs) == tag


def test_mm_sm_path_is_read(roster):
    paths = {r[0]: r[2] for r in roster}
    assert paths["1038"] == "SM" and paths["1204"] == "MM"


# --- deck naming ---------------------------------------------------------
def test_the_roster_decides_the_deck_name(roster):
    """clients.md decides, not the workbook and not the previous filename.

    1204's workbook says "First State Bank-MI" and its 2026.08 deck shipped as
    "FSB Michigan"; the client is "First State Bank - Michigan" (Aaron,
    2026-08-29). Renaming a client is a delivery decision, so it lives in the
    roster where such decisions are recorded.
    """
    assert deck_name("1204", "First State Bank - Michigan") == "First State Bank - Michigan"
    got = next(r[1] for r in roster if r[0] == "1204")
    assert got == "First State Bank - Michigan"


@pytest.mark.parametrize("cid,name", [
    ("1509", "Texas Bay Credit Union"),
    ("1537", "Brooks Bank"),
    ("1705", "CoastLife Credit Union"),
    ("1218", "Ideal Credit Union"),
    ("1632", "WesBanco"),
    ("1734", "Altamaha Bank and Trust Company"),
])
def test_roster_names_match_what_is_delivered(cid, name, roster):
    """The roster was carrying short forms that had never reached a deck. They
    are aligned so making the roster authoritative renames only 1204.

    1537 is the exception that proves the rule: FNBT Chickasha REBRANDED to
    Brooks Bank on 2026-08-31 (Aaron), so the roster deliberately no longer
    matches the name on its 2026.08 deck. Decks already shipped are not reissued
    — the roster names what the NEXT build delivers. Match 1537 by id; its name
    is not stable across periods.
    """
    assert next(r[1] for r in roster if r[0] == cid) == name


def test_clients_build_at_once_and_report_in_roster_order(tmp_path, monkeypatch, capsys):
    # 2026-09-25: `--jobs` builds several clients at once; the results file keeps roster order.
    import json, threading, time
    import build_month as BM
    roster = [("1001", "A", "MM", ["ARS"]), ("1002", "B", "MM", ["ARS"]), ("1003", "C", "SM", ["ARS"])]
    monkeypatch.setattr(BM, "read_roster", lambda *a, **k: (roster, []))
    live, peak, lock = [0], [0], threading.Lock()

    def fake_build(cid, name, mmsm, progs, period, stage):
        with lock:
            live[0] += 1; peak[0] = max(peak[0], live[0])
        time.sleep(0.3 if cid == "1001" else 0.05)          # the first finishes last
        with lock:
            live[0] -= 1
        return None, {"DELIVERABLE": f"{cid}.pptx"}
    monkeypatch.setattr(BM, "build_client", fake_build)
    monkeypatch.setattr(BM, "validate", lambda deck, base=None: "0 FAIL, 0 REVIEW")
    monkeypatch.setattr(BM.sys, "argv", ["build_month.py", "2026.09", str(tmp_path), "--jobs", "3"])
    assert BM.main() == 0
    assert peak[0] == 3
    assert [r[0] for r in json.load(open(tmp_path / "_results.json", encoding="utf-8"))] == ["1001", "1002", "1003"]
