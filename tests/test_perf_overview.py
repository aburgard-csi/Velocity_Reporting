"""perf_overview — the Client overview figures, read from a client's ODD with the deck's rules.

  * Open is "not closed" (the Product Mix slide's book); a blank Business? is neither side.
  * Swipes are personal-only; NSF/OD items count every account; both average three months.
  * Openings and closings are personal, inside the 12 months ending with the snapshot month.
  * The ODD member is chosen by name over a larger transaction CSV in the same zip.
"""
import csv
import io
import zipfile

import perf_overview as O

MONTHS = ["Jun26", "Jul26", "Aug26"]
COLS = (["Acct ID", "Business?", "Stat Desc", "Stat Code", "Debit?", "Date Opened", "Date Closed",
         "Prod Desc", "Aug26 Elig"]
        + [f"{m} {k}" for m in MONTHS for k in ("Sig #", "PIN #", "Sig $", "PIN $", "MTD")])


def _row(acct, business, desc, code, opened="", closed="", sig=(0, 0, 0), pin=(0, 0, 0), mtd=(0, 0, 0)):
    r = [acct, business, desc, code, "Yes", opened, closed, "Checking", "Yes"]
    for i in range(3):
        r += [str(sig[i]), str(pin[i]), "0", "0", str(mtd[i])]
    return r


ROWS = [
    _row("1", "No", "Open", "O", opened="10/15/2025", sig=(10, 10, 10), pin=(2, 2, 2), mtd=(1, 0, 2)),   # personal, opened in window
    _row("2", "No", "Closed", "C", opened="01/05/2020", closed="03/10/2026", sig=(3, 0, 0)),              # personal, closed in window
    _row("3", "Yes", "Open", "O", sig=(50, 50, 50), mtd=(3, 3, 3)),                                        # business: not in swipes
    _row("4", "", "Open", "O", mtd=(0, 3, 0)),                                                             # blank Business?: total only
    _row("5", "No", "Dormant", "", opened="07/01/2025"),                                                   # dormant is not closed; opened before window
    _row("6", "No", "", "C", closed="08/31/2026"),                                                         # Stat Code fallback: closed, last day in window
    _row("7", "No", "Open", "O", opened="09/01/2026"),                                                     # opened after the snapshot month
]


def _zip(tmp_path):
    buf = io.StringIO()
    w = csv.writer(buf)
    for _ in range(4):
        w.writerow(["report banner"])
    w.writerow(COLS)
    w.writerows(ROWS)
    p = tmp_path / "1204_ODDD.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("1204-2026-09-Test-ODD.csv", buf.getvalue())
        zf.writestr("1204-transactions.csv", "x," * 50000)          # larger decoy: must not be read
    return p


def test_overview_uses_the_decks_definitions(tmp_path):
    ov = O.read_overview(_zip(tmp_path))
    assert ov["month"] == "Aug26" and ov["month_label"] == "Aug 2026"
    assert ov["window12"] == ["Sep 2025", "Aug 2026"]
    assert ov["accounts"] == 7
    # not closed: 1, 3, 4, 5, 7 -> business 3; personal 1, 5, 7; other 4
    assert (ov["open_total"], ov["open_business"], ov["open_personal"], ov["open_other"]) == (5, 1, 3, 1)
    # personal swipes Jun-Aug: acct 1 = 36, acct 2 = 3 -> 39 / 3 = 13 per month
    assert ov["personal_swipes_3mo_avg"] == 13
    assert ov["swipes_per_open_personal"] == 4.3
    # NSF/OD items, every account: 3 + 9 + 3 = 15 / 3 = 5
    assert ov["nsf_items_3mo_avg"] == 5
    # opened in Sep 2025-Aug 2026: acct 1 only; closed: acct 2 (Mar 2026) and 6 (Aug 31 2026)
    assert (ov["personal_opened_12"], ov["personal_closed_12"]) == (1, 2)


def test_the_odd_member_wins_over_a_larger_transaction_csv(tmp_path):
    with zipfile.ZipFile(_zip(tmp_path)) as zf:
        assert O.odd_member(zf) == "1204-2026-09-Test-ODD.csv"


def test_results_are_cached_per_extract_and_a_missing_one_is_stated(tmp_path, monkeypatch):
    z = _zip(tmp_path)
    said = []
    got = O.client_overviews(["1204", "1002"], tmp_path / "cache", log=said.append,
                             path_for=lambda cid: z if cid == "1204" else tmp_path / "none.zip")
    assert got["1002"] == {"missing": "no ODD extract in Inputs"}
    assert got["1204"]["open_total"] == 5
    monkeypatch.setattr(O, "read_overview", lambda p: (_ for _ in ()).throw(AssertionError("re-read")))
    again = O.client_overviews(["1204"], tmp_path / "cache", log=said.append, path_for=lambda cid: z)
    assert again["1204"] == got["1204"], "an unchanged extract is served from the cache"


def test_an_unreadable_extract_is_reported_not_raised(tmp_path):
    bad = tmp_path / "bad_ODDD.zip"
    bad.write_bytes(b"not a zip")
    got = O.client_overviews(["9999"], tmp_path / "cache", log=lambda *a: None, path_for=lambda cid: bad)
    assert got["9999"]["missing"].startswith("ODD extract could not be read")


def test_open_counts_match_the_product_mix_slide(tmp_path):
    """The overview's open book IS the Product Mix slide's, checked against that slide's own
    extractor so the two cannot drift. Verified on real 2026.09 extracts too (1204, 1549)."""
    from product_mix_slide import extract_product_mix
    z = _zip(tmp_path)
    pm = extract_product_mix(str(z))
    ov = O.read_overview(z)
    assert (pm["open_total"], pm["biz"], pm["per"], pm["other"]) == \
        (ov["open_total"], ov["open_business"], ov["open_personal"], ov["open_other"])
