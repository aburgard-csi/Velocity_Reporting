"""The slides that need the ODD join (interchange by channel, age, product) and the ones that must survive
its absence. The ODD block is built from a synthetic extract through the real scan and exposure functions;
only the file lookups are replaced.

Every figure and account hash is synthetic.
"""
import datetime as dt

import build_ics_gen as G
import ics_channel_split as CS
import ics_local_sheet as L
from test_ics_local_sheet import (root, _sheet, _build_deck, _titles,  # noqa: F401 (fixture)
                                  write_referrals, write_charts, write_workbook,
                                  referral_file, charts_file, workbook_file, dm_file, PERIOD, CID)
from test_ics_channel_split import (H, write_odd, _odd_rows, write_dm_with_hashes, _deck_with_cohorts, _text)


def _odd_block(tmp_path, split, rate=True):
    zp = tmp_path / "9901_ODDD.zip"
    write_odd(zp, _odd_rows())
    scan = CS.scan_odd(zp, {H(1): "dm", H(2): "dm", H(3): "ref", H(4): "ref", H(5): "ref"})
    split = dict(split)
    rt = {"rate": 0.009, "rate_min": 0.00899, "rate_max": 0.00901, "cohorts_used": 12} if rate else None
    split["odd"] = {"file": "9901_ODDD.zip", "member": scan["member"], "stamp": scan["stamp"], "first_month": "2023-10",
                    "last_month": "2024-05", "as_of": "2024-05-31", "gap_months": CS.gap_months(scan["months"]),
                    "matched": {"direct_mail": 2, "referral": 3, "dm_list": 2, "referral_list": 3}, "cached": False,
                    "rate": rt, "interchange": CS.exposure_by_year(scan, 0.009) if rate else None,
                    "age": CS.age_profile(scan, dt.date(2024, 5, 31)), "products": CS.product_mix(scan)}
    return split


def _inputs(root, tmp_path):
    write_workbook(workbook_file(root, PERIOD), months=24, first=(2024, 9))
    write_charts(charts_file(root))
    write_referrals(referral_file(root))
    write_dm_with_hashes(dm_file(root), [(H(700 + i), dt.datetime(2025, 3 + (i % 6), 1 + i), "10") for i in range(9)])
    return _sheet(root, tmp_path)


def test_the_odd_slides_exist_where_the_odd_join_was_made(root, tmp_path, monkeypatch):
    d = _inputs(root, tmp_path)
    real = CS.compute(d, use_odd=False)
    monkeypatch.setattr(G.CS, "compute", lambda dd, **k: _odd_block(tmp_path, real))
    out, prs = _build_deck(root, tmp_path, d)
    ts = _titles(prs)
    assert (ts.index("Interchange by Channel") < ts.index("ICS Financial Summary") < ts.index("Age Demographics")
            < ts.index("ICS Accounts by Product Type") < ts.index("Comparisons"))
    ic = prs.slides[ts.index("Interchange by Channel")]
    txt = " ".join(sh.text_frame.text for sh in ic.shapes if sh.has_text_frame).replace("\n", " ")
    assert "Spread, NSF/OD and other fees are not split by channel" in txt      # the one plain sentence
    n = ic.notes_slide.notes_text_frame.text
    assert "0.900%" in n and "Feb'24, Mar'24" in n and "left out of every figure" in n and "NOT split" in n
    ag = prs.slides[ts.index("Age Demographics")]
    atxt = " ".join(sh.text_frame.text for sh in ag.shapes if sh.has_text_frame).replace("\n", " ")
    assert "Fintech Customer: 35" in atxt and "Bank Customer: 50" in atxt and "Credit Union: 53" in atxt
    assert "supplied by the ICS program team" in ag.notes_slide.notes_text_frame.text
    prod = prs.slides[ts.index("ICS Accounts by Product Type")]
    assert "Hassle Free" in " ".join(c.text for sh in prod.shapes if sh.has_table for r in sh.table.rows for c in r.cells)
    agenda = " ".join(sh.text_frame.text for sh in prs.slides[ts.index("Agenda")].shapes if sh.has_text_frame)
    assert "Financial Summary & Account Mix" in agenda


def test_an_unstable_rate_gives_no_interchange_slide_but_keeps_the_rest(root, tmp_path, monkeypatch):
    d = _inputs(root, tmp_path)
    real = CS.compute(d, use_odd=False)
    monkeypatch.setattr(G.CS, "compute", lambda dd, **k: _odd_block(tmp_path, real, rate=False))
    out, prs = _build_deck(root, tmp_path, d)
    ts = _titles(prs)
    assert "Interchange by Channel" not in ts and "Age Demographics" in ts and "Direct Mail and Branch Referral Accounts" in ts


def test_a_failing_split_never_stops_the_deck(root, tmp_path, monkeypatch, capsys):
    write_workbook(workbook_file(root, PERIOD), months=15, first=(2025, 6))
    write_charts(charts_file(root))
    write_referrals(referral_file(root))
    d = _sheet(root, tmp_path)

    def boom(*a, **k):
        raise OSError("share unreachable")
    monkeypatch.setattr(G.CS, "compute", boom)
    out, prs = _build_deck(root, tmp_path, d)
    assert "Direct Mail and Branch Referral Accounts" not in _titles(prs)
    assert "split NOT made" in capsys.readouterr().err


def test_the_export_is_used_only_when_it_reaches_the_month_before_the_deck(root):
    """A client whose export rows stop earlier would make `referral_sections` refuse to build, where the
    workbook-only shape (or nothing) built before: it falls through to that."""
    from test_ics_channel_split import write_export, exp_row
    from test_ics_local_sheet import kind_dir
    write_export(kind_dir(root, L.REFERRAL_KIND) / "ics_referrals.csv",
                 [exp_row(CID, 1, "2026-06-30 10:00:00.000"), exp_row("9902", 2, "2026-08-30 10:00:00.000")])
    assert L.find_referral_export(CID) is not None                       # no period: the client has rows
    assert L.find_referral_export(CID, "2026.07") is not None             # June is the month before July
    assert L.find_referral_export(CID, "2026.08") is None                 # July is missing: not current
    assert L.find_referral_export("9902", "2026.09") is not None


def test_the_export_alone_does_not_put_an_ics_section_in_front_of_a_client_that_had_none(root):
    """The export upgrades the workbook-only shape to the full one. A client with export rows and NO workbook for
    the period had no buildable ICS section before and still has none (a roster pass found fourteen)."""
    from test_ics_channel_split import write_export, exp_row
    from test_ics_local_sheet import kind_dir
    write_export(kind_dir(root, L.REFERRAL_KIND) / "ics_referrals.csv", [exp_row(CID, 1, "2026-08-30 10:00:00.000")])
    av = L.available(CID, PERIOD, "Sample Harbor CU")
    assert av["ok"] is False and av["shape"] is None and av["referrals"] is None
    write_workbook(workbook_file(root, PERIOD))
    assert L.available(CID, PERIOD, "Sample Harbor CU")["shape"] == "full"
    # a stale export falls through to the workbook-only shape
    write_export(kind_dir(root, L.REFERRAL_KIND) / "ics_referrals.csv",
                 [exp_row(CID, 1, "2026-05-30 10:00:00.000"), exp_row(CID, 2, "2026-05-29 10:00:00.000")])   # another size: the lookup is cached by file version
    assert L.available(CID, PERIOD, "Sample Harbor CU")["shape"] == L.WORKBOOK_ONLY


def test_a_one_month_direct_mail_list_makes_no_split(root, tmp_path, capsys):
    """Brooks Bank 1537's list is "Opened in Sep 2026": taken for the whole program it would call every earlier
    month's accounts branch referrals. Only a program-to-date list (banner `Period: PTD`, else PTD in the name)
    splits."""
    assert CS.dm_list_is_program_to_date("x/1537-DM New Accounts Opened PTD.xlsx", None)
    assert CS.dm_list_is_program_to_date("x/anything.xlsx", "PTD") and not CS.dm_list_is_program_to_date("x/PTD.xlsx", "September 2026")
    assert not CS.dm_list_is_program_to_date("x/1537-DM New Accounts Opened in Sep 2026.xlsx", None)
    d = _inputs(root, tmp_path)
    # the same list, re-labelled by its banner as one month
    import openpyxl
    p = dm_file(root)
    wb = openpyxl.load_workbook(p)
    wb.active.cell(1, 3, "Period: September 2026")
    wb.save(p)
    assert CS.compute(d, use_odd=False) is None
    assert "not a program-to-date list" in capsys.readouterr().out


def test_the_divider_of_a_full_deck_does_not_repeat_the_referral_slide(root, tmp_path):
    d, out, prs = _deck_with_cohorts(root, tmp_path)
    div = " ".join(sh.text_frame.text for sh in prs.slides[2].shapes if sh.has_text_frame)
    assert "profit contribution, program to date" in div and "referrals, program to date" not in div
    # a referrals-only deck has no other figures and keeps the referral ones
    out2, prs2 = _build_deck(root, tmp_path, d, referrals_only=True)
    div2 = " ".join(sh.text_frame.text for sh in prs2.slides[2].shapes if sh.has_text_frame)
    assert "referrals, program to date" in div2
