"""refresh_performance_dashboard — the rules that decide whether the artifact is
republished, and what period it claims.

  * The period is the calendar month (Aaron, 2026-10-02), not the newest ARS
    workbook: the page read "2026.09" into October while workbooks were landing.
  * "Changed" means the figures moved. The generation date is excluded from the
    hash, or every daily rebuild would republish an identical page.
  * No dataset value can close the page's script tag.
"""
import json
import os

import pytest

import refresh_performance_dashboard as P


# ------------------------------------------------------------------ period
def test_default_period_is_the_calendar_month():
    import datetime as dt
    assert P.calendar_period(dt.date(2026, 10, 2)) == "2026.10"
    assert P.calendar_period(dt.date(2027, 1, 1)) == "2027.01"


def test_main_defaults_to_the_calendar_month_not_the_newest_workbook():
    import inspect
    src = inspect.getsource(P.main)
    assert "calendar_period()" in src and "derive_period(" not in src


def test_newest_ars_workbook_is_still_readable():
    names = [
        "1038-2026.08-Sugar River-Workbook_v2_1_0.xlsx",
        "1075-2026.09-Austin-Workbook_v2_1_0.xlsx",
        "1509-2026.09-Texas Bay-Invitation Checking Workbook v1.7.1.xlsx",   # ICS, ignored
        "1075-2026.10-Austin-DCO v2_2.xlsx",                                  # not a workbook
        "~$1204-2026.11-First State Bank-MI-Workbook_v2_1_0.xlsx",            # lock file
    ]
    assert P.derive_period("unused", names) == "2026.09"


def test_no_workbooks_means_no_period():
    assert P.derive_period("unused", ["1075-2026.08-Austin-DCO v2_2.xlsx"]) is None


# ------------------------------------------------------------------ roster
ROSTER = """
## Active clients
| 1038 | Sugar River Bank | SM | yes | — | — | ARS |

### CashPlease roster — BUILD ONLY THESE

| ID | Client | CSM | Build | Loans | Ships as | Note |
| --- | --- | --- | --- | --- | --- | --- |
| 1131 | People's Bank AL | Aaron Burgard | yes | 10,507 | standalone module | |
| 1658 | Truliant FCU | Aaron Burgard | **no** | 8,296 | — | cancelled |
| 1734 | Altamaha Bank and Trust Company | | yes | 646 | ICS-CP | |

## Something else
| 9999 | Not a CashPlease client | | yes | | | |
"""


def _roster_file(tmp_path, text):
    f = tmp_path / "clients.md"
    f.write_text(text, encoding="utf-8")
    return f


def test_cashplease_roster_reads_build_yes_rows_only(tmp_path):
    """Build is found by header, not position: the CSM column sits where Build used to."""
    assert P.cashplease_roster(_roster_file(tmp_path, ROSTER)) == {
        "1131": {"name": "People's Bank AL", "csm": "Aaron Burgard"},
        "1734": {"name": "Altamaha Bank and Trust Company", "csm": None}}


def test_cashplease_roster_absent_is_empty(tmp_path):
    assert P.cashplease_roster(_roster_file(tmp_path, "# nothing here")) == {}


# ------------------------------------------------------------------ render / hash
def test_render_injects_and_escapes_script_close():
    tpl = "<title>x</title><script>const DATA = __DATA__;</script>"
    html = P.render({"a": "</script><b>"}, tpl)
    assert "__DATA__" not in html
    assert "</script><b>" not in html.split("const DATA = ", 1)[1].split(";</script>")[0]
    assert r"<\/script>" in html


def test_render_refuses_a_template_without_the_placeholder():
    with pytest.raises(SystemExit):
        P.render({}, "<p>no slot</p>")


def test_hash_ignores_the_generation_date_but_not_figures():
    a = {"generated": "2026-09-08", "period": "2026.08", "clients": [{"id": "1", "x": 1}]}
    b = dict(a, generated="2026-09-09")
    c = dict(a, clients=[{"id": "1", "x": 2}])
    assert P.content_hash(a) == P.content_hash(b)
    assert P.content_hash(a) != P.content_hash(c)


def test_repo_template_has_the_slot_and_a_title():
    t = P.TEMPLATE.read_text(encoding="utf-8")
    assert t.count(P.PLACEHOLDER) == 1
    assert "<title>RPE Client Performance</title>" in t


# ------------------------------------------------------------------ state
def test_mark_published_refuses_before_a_build(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "out_dir", lambda: tmp_path)
    with pytest.raises(SystemExit):
        P.main(["--mark-published"])


def test_mark_published_records_the_built_hash(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(P, "out_dir", lambda: tmp_path)
    P.write_state(tmp_path / "state.json", {"hash": "abc123"})
    assert P.main(["--mark-published"]) == 0
    s = json.loads((tmp_path / "state.json").read_text())
    assert s["published_hash"] == "abc123" and s["published_at"]


# ------------------------------------------------------------------ newest per client
NAMES = [
    "1038-2026.08-Sugar River-Workbook_v2_1_0.xlsx",
    "1038-2026.09-Sugar River-Workbook_v2_1_0.xlsx",
    "1075-2026.08-Austin-Workbook_v2_1_0.xlsx",                       # no September yet
    "1075-2026.08-Austin-Invitation Checking Workbook v1.7.1.xlsx",   # ICS, never ARS
    "1075-2026.10-Austin-Workbook_v2_1_0.xlsx",                       # a month AHEAD of the cycle
    "~$1075-2026.09-Austin-Workbook_v2_1_0.xlsx",
]


def test_workbook_is_the_clients_newest_at_or_before_the_cycle():
    assert P.pick_workbook(NAMES, "1038", "2026.09") == ("2026.09", "1038-2026.09-Sugar River-Workbook_v2_1_0.xlsx")
    assert P.pick_workbook(NAMES, "1075", "2026.09") == ("2026.08", "1075-2026.08-Austin-Workbook_v2_1_0.xlsx")
    assert P.pick_workbook(NAMES, "1204", "2026.09") == (None, None)


def test_sidecar_and_deck_follow_the_same_rule():
    sc = ["1038-2026.07-ARS-Sugar River Bank ARS Results.pptx.figures.json",
          "1038-2026.08-ARS-Sugar River Bank ARS Results.pptx.figures.json",
          "1038-2026.08-ARS-ICS-Sugar River Bank Results.pptx.figures.json"]   # combined: not ARS-only
    assert P.pick_sidecar(sc, "1038", "2026.09")[1] == "1038-2026.08-ARS-Sugar River Bank ARS Results.pptx.figures.json"
    decks = ["1539-2026.07-ARS-ICS-MRPC-Marine FCU Results.pptx",
             "1539-2026.08-ARS-ICS-MRPC-Marine FCU Results.pptx",
             "1539-2026.08-CP-Marine Federal Credit Union CashPlease Module.pptx",
             "~$1539-2026.09-ARS-Marine FCU ARS Results.pptx"]
    assert P.newest_deck_period(decks, "1539", "2026.09") == "2026.08"
    assert P.newest_deck_period(decks, "1539", "2026.07") == "2026.07"
    assert P.newest_deck_period([], "1539", "2026.09") is None


def test_an_uncalculated_workbook_is_reported_not_zeroed():
    assert P.uncalculated({"months": 1, "ltd_revenue": 0, "cur_revenue": 0})
    assert P.uncalculated({"months": None, "ltd_revenue": None, "cur_revenue": None})
    assert not P.uncalculated({"months": 96, "ltd_revenue": 10677533.23, "cur_revenue": 154881.24})
    assert not P.uncalculated({"months": 1, "ltd_revenue": 0, "cur_revenue": 4200.0})   # a brand-new client


# ------------------------------------------------------------------ merge-sent
# A click on the artifact's "Mark sent" button parks a row in the artifact's own
# store; merge_sent is where that row becomes the record. deliveries.json stays
# the one ledger, so these rules matter more than the transport.
def _log(tmp_path, sent):
    (tmp_path / "deliveries.json").write_text(
        json.dumps({"version": 1, "sent": sent}), encoding="utf-8")
    return tmp_path


def _export(tmp_path, rows):
    d = tmp_path / "export"
    d.mkdir()
    for r in rows:
        (d / ("%s-%s.json" % (r.get("client_id", "x"), r.get("period", "y")))).write_text(
            json.dumps(r), encoding="utf-8")
    return d


def test_merge_sent_adds_a_page_recorded_send(tmp_path):
    ba = _log(tmp_path, {})
    src = _export(tmp_path, [{"client_id": "1204", "period": "2026.09",
                              "sent_at": "2026-09-11", "by": "artifact page"}])
    assert P.merge_sent(src, ba) == 1
    log = json.loads((ba / "deliveries.json").read_text())
    assert log["sent"]["1204|2026.09"]["sent_at"] == "2026-09-11"
    assert log["sent"]["1204|2026.09"]["client_id"] == "1204"


def test_merge_sent_never_rewrites_an_existing_entry(tmp_path):
    """deliveries.json wins: a date corrected by hand survives a stale page row."""
    ba = _log(tmp_path, {"1204|2026.09": {"client_id": "1204", "period": "2026.09",
                                          "sent_at": "2026-09-02", "note": "", "by": "aaron.burgard"}})
    src = _export(tmp_path, [{"client_id": "1204", "period": "2026.09", "sent_at": "2026-09-11"}])
    assert P.merge_sent(src, ba) == 0
    log = json.loads((ba / "deliveries.json").read_text())
    assert log["sent"]["1204|2026.09"]["sent_at"] == "2026-09-02"
    assert log["sent"]["1204|2026.09"]["by"] == "aaron.burgard"


@pytest.mark.parametrize("row", [
    {"client_id": "1204", "period": "2026.09", "sent_at": "9/11/2026"},   # not ISO
    {"client_id": "1204", "period": "September 2026", "sent_at": "2026-09-11"},
    {"client_id": "", "period": "2026.09", "sent_at": "2026-09-11"},
    {"client_id": "1204", "period": "2026.09"},                            # no date
])
def test_merge_sent_skips_a_malformed_row_rather_than_guessing(tmp_path, row):
    ba = _log(tmp_path, {})
    assert P.merge_sent(_export(tmp_path, [row]), ba) == 0
    assert json.loads((ba / "deliveries.json").read_text())["sent"] == {}


def test_merge_sent_reads_a_single_file_export(tmp_path):
    ba = _log(tmp_path, {})
    f = tmp_path / "rows.json"
    f.write_text(json.dumps([{"client_id": "1038", "period": "2026.08", "sent_at": "2026-09-11"},
                             {"client_id": "1075", "period": "2026.08", "sent_at": "2026-09-11"}]),
                 encoding="utf-8")
    assert P.merge_sent(f, ba) == 2


def test_merge_sent_leaves_a_damaged_log_alone(tmp_path):
    """Raising beats merging over it: a log read as empty invites sending twice."""
    (tmp_path / "deliveries.json").write_text("{ truncated", encoding="utf-8")
    src = _export(tmp_path, [{"client_id": "1204", "period": "2026.09", "sent_at": "2026-09-11"}])
    with pytest.raises(SystemExit):
        P.merge_sent(src, tmp_path)
    assert (tmp_path / "deliveries.json").read_text() == "{ truncated"


def test_merge_sent_creates_the_log_when_there_is_none(tmp_path):
    src = _export(tmp_path, [{"client_id": "1204", "period": "2026.09", "sent_at": "2026-09-11"}])
    assert P.merge_sent(src, tmp_path) == 1
    assert json.loads((tmp_path / "deliveries.json").read_text())["sent"]["1204|2026.09"]


# ------------------------------------------------------------------ undo from the page
# Clicking a sent date on the page (and confirming) writes an undo row naming the date it
# cancels (Aaron, 2026-09-14). It may only remove THAT date: an undo recorded before the
# send was re-recorded must not erase the newer one.
_LOGGED = {"1204|2026.09": {"client_id": "1204", "period": "2026.09",
                            "sent_at": "2026-09-11", "note": "", "by": "aaron.burgard"}}


def test_an_undo_removes_the_send_it_names(tmp_path):
    ba = _log(tmp_path, dict(_LOGGED))
    src = _export(tmp_path, [{"client_id": "1204", "period": "2026.09",
                              "unsent": True, "undo_of": "2026-09-11"}])
    assert P.merge_sent(src, ba) == 1
    assert "1204|2026.09" not in json.loads((ba / "deliveries.json").read_text())["sent"]


def test_a_stale_undo_never_erases_a_newer_send(tmp_path):
    ba = _log(tmp_path, dict(_LOGGED))
    src = _export(tmp_path, [{"client_id": "1204", "period": "2026.09",
                              "unsent": True, "undo_of": "2026-09-02"}])
    assert P.merge_sent(src, ba) == 0
    assert json.loads((ba / "deliveries.json").read_text())["sent"]["1204|2026.09"]["sent_at"] == "2026-09-11"


def test_an_undo_of_something_never_logged_changes_nothing(tmp_path):
    """A send recorded on the page and undone before any refresh leaves the log empty."""
    ba = _log(tmp_path, {})
    src = _export(tmp_path, [{"client_id": "1204", "period": "2026.09",
                              "unsent": True, "undo_of": "2026-09-14"}])
    assert P.merge_sent(src, ba) == 0
    assert json.loads((ba / "deliveries.json").read_text())["sent"] == {}


def test_marking_again_after_an_undo_replaces_the_logged_date(tmp_path):
    """Undo then Mark sent overwrites the undo row with a send naming the date it replaces."""
    ba = _log(tmp_path, dict(_LOGGED))
    src = _export(tmp_path, [{"client_id": "1204", "period": "2026.09",
                              "sent_at": "2026-09-14", "undo_of": "2026-09-11", "by": "artifact page"}])
    assert P.merge_sent(src, ba) == 1
    row = json.loads((ba / "deliveries.json").read_text())["sent"]["1204|2026.09"]
    assert row["sent_at"] == "2026-09-14" and row["by"] == "artifact page"


def test_a_replacement_naming_another_date_is_stale(tmp_path):
    ba = _log(tmp_path, dict(_LOGGED))
    src = _export(tmp_path, [{"client_id": "1204", "period": "2026.09",
                              "sent_at": "2026-09-14", "undo_of": "2026-09-02"}])
    assert P.merge_sent(src, ba) == 0
    assert json.loads((ba / "deliveries.json").read_text())["sent"]["1204|2026.09"]["sent_at"] == "2026-09-11"


@pytest.mark.parametrize("row", [
    {"client_id": "1204", "period": "2026.09", "unsent": True},                          # no date named
    {"client_id": "1204", "period": "2026.09", "unsent": True, "undo_of": "9/11/2026"},  # not ISO
    {"client_id": "1204", "period": "2026.09", "unsent": "yes", "undo_of": "2026-09-11"},  # not a real flag
])
def test_a_malformed_undo_is_skipped(tmp_path, row):
    ba = _log(tmp_path, dict(_LOGGED))
    assert P.merge_sent(_export(tmp_path, [row]), ba) == 0
    assert json.loads((ba / "deliveries.json").read_text())["sent"]["1204|2026.09"]["sent_at"] == "2026-09-11"


# ------------------------------------------------------------------ the button
def test_template_marks_sent_against_the_period_showing_not_the_cycle():
    """The log is keyed <client>|<period>; the button must use the same key, or a send
    would be recorded against a period the deck does not belong to. Since 2026-10-12 the
    period is the one the Build readiness picker shows, and the row is stamped with it."""
    t = P.TEMPLATE.read_text(encoding="utf-8")
    assert "const sentDoc = c => `${c.id}-${rPeriod}`" in t
    assert "period:v.P" in t and 'DB.doc("deliveries/"' in t


def test_template_cannot_mark_a_client_with_no_deck():
    """Sent is recorded, never inferred — and never for a deck that was not built for
    the period showing."""
    t = P.TEMPLATE.read_text(encoding="utf-8")
    assert "if (!v.built) return" in t


# ------------------------------------------------------------------ CSM
def _quiet(*_a):
    pass


def _share(tmp_path, files):
    root = tmp_path / "share"
    for rel in files:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")
    return str(root)


def test_csm_is_the_account_manager_folder_the_reports_land_in(tmp_path):
    root = _share(tmp_path, ["2026.09/Aaron Burgard/1204-2026.09-First State Bank-DCO.xlsx",
                             "2026.09/Daniel Wood/1095-2026.09-Workbook.xlsx",
                             "2026.09/Daniel Wood/readme.txt",
                             "OIS Pricing Reports/2010.02/9999-old.xlsx"])
    assert P.share_csms(root, "2026.09", log=_quiet) == {"1204": "Aaron Burgard",
                                                          "1095": "Daniel Wood"}


def test_the_newest_month_wins_and_a_late_landing_keeps_last_months_csm(tmp_path):
    root = _share(tmp_path, ["2026.08/Matt Lindsey/1805-2026.08-a.xlsx",
                             "2026.09/Jordan Berkowitz/1805-2026.09-a.xlsx",
                             "2026.08/Gregg Miller/1147-2026.08-a.xlsx",
                             "2026.10/Someone Else/1147-2026.10-a.xlsx",   # after the cycle
                             "2026.06/Old Owner/1200-2026.06-a.xlsx"])     # outside the window
    assert P.share_csms(root, "2026.09", log=_quiet) == {"1805": "Jordan Berkowitz",
                                                          "1147": "Gregg Miller"}


def test_an_unreachable_share_is_none_not_an_empty_answer(tmp_path):
    assert P.share_csms(str(tmp_path / "offline"), "2026.09", log=_quiet) is None


def test_csm_falls_back_to_the_last_share_answer_then_settings_then_nobody(tmp_path, monkeypatch):
    root = _share(tmp_path, ["2026.09/Aaron Burgard/1204-2026.09-a.xlsx"])
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setattr(P, "settings_csm", lambda cid: {"1131": "Aaron Burgard"}.get(cid))
    ids = ["1131", "1204", "1771"]
    assert P.csm_assignments(ids, "2026.09", work, root=root, log=_quiet, listed={}) == {
        "1131": "Aaron Burgard", "1204": "Aaron Burgard", "1771": None}
    # Off the VPN the share's last answer stands, so the page (and its hash) do not move.
    assert P.csm_assignments(ids, "2026.09", work, root=str(tmp_path / "offline"),
                             log=_quiet, listed={})["1204"] == "Aaron Burgard"


def test_the_share_outranks_the_roster_csm_column_and_a_disagreement_is_logged(tmp_path, monkeypatch):
    """The roster column fills in for clients the share never names (the CashPlease-only
    ones) and outranks the settings record; where the share names someone, it wins."""
    root = _share(tmp_path, ["2026.09/Aaron Burgard/1204-2026.09-a.xlsx"])
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setattr(P, "settings_csm", lambda cid: "From Settings")
    said = []
    got = P.csm_assignments(["1204", "1771", "1750"], "2026.09", work, root=root,
                            roster={"1204": "Daniel Wood", "1771": "Aaron Burgard"},
                            log=said.append, listed={})
    assert got == {"1204": "Aaron Burgard", "1771": "Aaron Burgard", "1750": "From Settings"}
    assert any("1204" in s and "Daniel Wood" in s for s in said)


def test_the_client_csm_list_outranks_the_share_and_a_disagreement_is_logged(tmp_path, monkeypatch):
    """Aaron, 2026-10-12: "point the dashboard CSM at the Client CSM List." Gregg Miller
    left on 2026-10-02 and the data team kept filing 1811, 1816 and 1817 under his folder,
    so the page listed him for ten days after the list had reassigned them."""
    root = _share(tmp_path, ["2026.09/Gregg Miller/1811-2026.09-a.xlsx",
                             "2026.09/Aaron Burgard/1204-2026.09-a.xlsx"])
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setattr(P, "settings_csm", lambda cid: None)
    said = []
    got = P.csm_assignments(["1811", "1204", "1771", "1088"], "2026.09", work, root=root,
                            roster={"1771": "Aaron Burgard"},
                            listed={"1811": "Max Willett", "1204": "Aaron Burgard", "1088": "Unassigned"},
                            log=said.append)
    assert got == {"1811": "Max Willett",         # the list, over the share's old folder
                   "1204": "Aaron Burgard",       # both agree
                   "1771": "Aaron Burgard",       # not on the list: the roster still fills in
                   "1088": "Unassigned"}          # the list's own label stands
    assert any("1811" in s and "Max Willett" in s and "Gregg Miller" in s for s in said)
    assert not any("1204" in s for s in said)


def test_csm_list_reads_the_file_and_skips_blank_rows(tmp_path):
    f = tmp_path / "Client CSM List.csv"
    f.write_text("﻿client_id,client_name,csm,csm_source\n1811, Dutch Point ,Max Willett,x\n"
                 "1816,Beginnings CU,,\n,no id,Aaron Burgard,\n", encoding="utf-8")
    assert P.csm_list(f) == {"1811": "Max Willett"}
    assert P.csm_list(tmp_path / "missing.csv") == {}


def test_settings_csm_reads_the_record_and_is_none_without_one(tmp_path, monkeypatch):
    rec = tmp_path / "1632_cp_settings.json"
    rec.write_text(json.dumps({"CSM": " Aaron Burgard "}))
    monkeypatch.setattr(P.R, "cp_settings_file", lambda cid: rec if cid == "1632" else None)
    assert P.settings_csm("1632") == "Aaron Burgard"
    assert P.settings_csm("1771") is None


# ------------------------------------------------------------------ every current client
def test_page_lists_current_clients_beyond_the_roster_but_not_stopped_ones(tmp_path, monkeypatch):
    root = _share(tmp_path, ["2026.09/Daniel Wood/1095-2026.09-Landmark Bank-DCO.xlsx",
                             "2026.09/Daniel Wood/1095-2026.09-Landmark Bank-Workbook_v2.xlsx",
                             "2026.09/Aaron Burgard/1204-2026.09-First State Bank-MI-DCO.xlsx",
                             "2026.09/Aaron Burgard/1437-2026.09-Canandaigua-DCO.xlsx",
                             "2026.09/Gregg Miller/1147-2026.09-Sutton-DCO.xlsx",
                             "2026.09/Gregg Miller/1156-2026.09-BancFirst-DCO.xlsx"])
    work = tmp_path / "work"
    work.mkdir()
    packs = tmp_path / "cp"
    packs.mkdir()
    (packs / "1147_cashplease.json").write_text("{}")
    monkeypatch.setattr(P, "roster_clients", lambda: {"1204": {
        "id": "1204", "name": "First State Bank - Michigan", "path": "MM", "programs": [],
        "roster_programs": ["ARS"]}})
    monkeypatch.setattr(P, "read_roster", lambda path: ([], [("1437", "Canandaigua National Bank", "cancelled / ending")]))
    monkeypatch.setattr(P, "reports_share", lambda: root)

    def no_sheet(cid, program):
        raise SystemExit("no VIP sheet for %s" % cid)
    monkeypatch.setattr(P.R, "resolve_client_json", no_sheet)
    weekly = type("Weekly", (), {"tabs": {}})()

    clients, folder = P.page_clients("2026.09", work, weekly, packs, log=_quiet, workbook_names=[])
    assert folder == "2026.09"
    assert sorted(clients) == ["1095", "1147", "1156", "1204"], "1437 is stopped in clients.md"
    assert clients["1204"]["programs_from"] == "clients.md" and clients["1204"]["roster_programs"] == ["ARS"]
    assert clients["1095"] == {"id": "1095", "name": "Landmark Bank", "path": None, "programs": [],
                               "roster_programs": ["ARS"], "programs_from": "data",
                               "share_kinds": ["DCO", "WORKBOOK"]}
    assert clients["1147"]["roster_programs"] == ["CP"]
    assert clients["1156"]["roster_programs"] == [], "a DCO alone implies no program"

    # Last month's workbook in Inputs keeps an inferred client on ARS, the way a roster
    # client without this month's workbook (1075 Austin Bank) shows last month's, tagged.
    # One that ended long ago does not come back.
    clients, _ = P.page_clients("2026.09", work, weekly, packs, log=_quiet, workbook_names=[
        "1147-2026.08-Sutton-Workbook_v2_1_0.xlsx", "1156-2026.03-BancFirst-Workbook_v2_1_0.xlsx"])
    assert clients["1147"]["roster_programs"] == ["ARS", "CP"]
    assert clients["1156"]["roster_programs"] == [], "a workbook six months old is not a current ARS client"


def test_months_before_counts_across_a_year_end():
    assert P.months_before("2026.09", "2026.07") == 2
    assert P.months_before("2026.01", "2025.12") == 1
    assert P.months_before("2026.09", "2026.10") == -1


def test_a_refused_workbook_is_labelled_in_the_extractors_words():
    """A workbook's own fault reads as the extractor's verdict, never "extract failed"."""
    assert P._flagged("Traceback...\nSystemExit\nUNEVALUATED WORKBOOK: 1192-2026.09-Ascend FCU-Workbook.xlsx carries no calculated values\n") \
        == "UNEVALUATED WORKBOOK: 1192-2026.09-Ascend FCU-Workbook.xlsx carries no calculated values"
    assert P._flagged("POSSIBLE DATA ISSUE: Key Trends month Aug 2026 is blank\n") \
        == "POSSIBLE DATA ISSUE: Key Trends month Aug 2026 is blank"
    assert P._flagged("TypeError: type NoneType doesn't define __round__ method") is None
    assert P._flagged("") is None


def test_the_odd_data_month_is_the_month_before_the_cycle():
    assert P.odd_data_month("2026.09") == "Aug26"
    assert P.odd_data_month("2026.01") == "Dec25"


def test_template_is_pure_ascii():
    """A literal em dash rendered as "â€”" on the page (Aaron, 2026-09-14): the CSM source line
    carried the UTF-8 character itself, and a copy read without a UTF-8 declaration mis-decodes
    it. Non-ASCII goes in as \\uXXXX inside the script and as an entity outside it."""
    raw = P.TEMPLATE.read_bytes()
    bad = sorted({b for b in raw if b > 126})
    assert not bad, "non-ASCII bytes in the template: %s" % [hex(b) for b in bad]


def test_trend_lines_drop_the_month_in_progress():
    """Aaron, 2026-09-14: ICS, MRPC and CashPlease trends show complete months only."""
    ics = P.complete_trend({"months": ["Jul 26", "Aug 26", "Sep 26"], "referrals": [363, 351, 37],
                            "goal": [331, 331, 331], "partial_last": True})
    assert ics == {"months": ["Jul 26", "Aug 26"], "referrals": [363, 351], "goal": [331, 331],
                   "partial_last": False}
    whole = {"months": ["Aug 26"], "referrals": [351], "goal": [331], "partial_last": False}
    assert P.complete_trend(whole) is whole, "a trend with no partial month is left alone"
    rows = [{"month": "2026-07"}, {"month": "2026-08"}, {"month": "2026-09"}]
    assert P.complete_months(rows, "9/13/2026 8:06:12 AM") == rows[:2]
    assert P.complete_months(rows, "10/1/2026 7:00:00 AM") == rows, "September had ended by October"
    assert P.complete_months(rows, "") == rows, "an unreadable stamp keeps every row"
    cp = [{"period_month": "2026-08"}, {"period_month": "2026-09"}]
    assert P.complete_months(cp, "9/13/2026 8:21:37 AM", key="period_month") == cp[:1]


def test_ars_revenue_to_csi_is_the_current_month_expense_as_a_positive_figure():
    assert P.csi_revenue({"cur_costs": -6077.98}) == 6077.98
    assert P.csi_revenue({"cur_costs": 0}) == 0
    assert P.csi_revenue({}) is None, "an extract without the key is not $0"


def test_built_decks_are_found_in_csm_folders_and_the_flat_folder(tmp_path, monkeypatch):
    """Outputs/ moves to Outputs/<CSM name>/ (2026-09-14); rpe_env.output_decks reads both
    layouts. Before that helper exists the flat glob gives the same answer."""
    out, ba = tmp_path / "Outputs", tmp_path / "ba"
    (out / "Aaron Burgard").mkdir(parents=True)
    ba.mkdir()
    (out / "Aaron Burgard" / "1204-2026.09-ARS-First State Bank - Michigan ARS Results.pptx").write_text("x")
    (out / "1204-2026.08-ARS-First State Bank - Michigan ARS Results.pptx").write_text("x")
    monkeypatch.setattr(P.R, "output_decks",
                        lambda pattern, root=None: sorted(p for p in out.rglob(pattern) if "Archive" not in p.parts),
                        raising=False)
    decks, sent, dp = P.decks_and_sent("1204", "2026.09", out, ba)
    assert dp == "2026.09" and decks == ["1204-2026.09-ARS-First State Bank - Michigan ARS Results.pptx"]
    monkeypatch.delattr(P.R, "output_decks", raising=False)
    decks, sent, dp = P.decks_and_sent("1204", "2026.09", out, ba)
    assert dp == "2026.08", "without the helper, only the flat folder is read"


def _cp_pack(folder, cid, loans, principal, interest, status, cancelled=None, dda=None, window=0, comparable=False):
    st = {k: {"loans": 0, "principal": 0.0, "interest": 0.0} for k in ("Overdue", "Charged Off", "Paid Off", "Funded")}
    for k, n in status.items():
        st[k]["loans"] = n
    (folder / ("%s_cashplease.json" % cid)).write_text(json.dumps({
        "client_id": cid, "cancelled": cancelled, "charge_off_pct": 0.05,
        "total": {"loans": loans, "principal": principal, "interest": interest}, "status": st,
        "metrics": {"peer_comparable": comparable, "dda_accounts": dda, "window_loans": window}}), encoding="utf-8")


def test_a_program_is_inactive_with_no_activity_in_six_complete_months():
    rows = [{"month": "2025-08", "loans": 4}, {"month": "2025-09", "loans": 2}, {"month": "2026-08", "loans": 0}]
    assert P.inactive_since(rows, "9/13/2026 8:21:37 AM", lambda r: r["loans"]) == "2025-09"
    rows.append({"month": "2026-03", "loans": 1})
    assert P.inactive_since(rows, "9/13/2026 8:21:37 AM", lambda r: r["loans"]) is None, "Mar 2026 is inside the window"
    assert P.inactive_since([{"month": "2026-09", "loans": 9}], "9/13/2026", lambda r: r["loans"]) == "",         "the month in progress does not count as activity"
    assert P.inactive_since(rows[:2], "", lambda r: r["loans"]) is None, "an unreadable stamp never hides a program"


def test_template_labels_the_current_peer_row_and_tags_inactive_programs():
    t = P.TEMPLATE.read_text(encoding="utf-8")
    assert "Current Velocity CashPlease clients" in t and "All Velocity CashPlease clients" not in t
    assert "no loans since " in t and "no enrollments since " in t


def test_template_has_no_subheading_under_the_title():
    """Aaron, 2026-09-14: remove the "85 clients, 5 CSMs, across four programs. Click a CSM..."
    line under the title."""
    t = P.TEMPLATE.read_text(encoding="utf-8")
    assert 'id="subline"' not in t and "across four programs" not in t


def test_template_declares_no_top_level_name_twice():
    """A repeated top-level `const`/`let` is a SyntaxError that blanks the whole page.

    It shipped past every string check here on 2026-09-14: the client marks were added as
    `const MARKS` beside the Mark sent code's `let MARKS`, and the page rendered only its
    filter rows. The check reads the one inline script's column-0 declarations.
    """
    import re
    t = P.TEMPLATE.read_text(encoding="utf-8")
    names = re.findall(r"^(?:const|let|var|function|async function)\s+([A-Za-z_$][\w$]*)", t, flags=re.M)
    dups = sorted({n for n in names if names.count(n) > 1})
    assert names and not dups, "declared more than once at top level: %s" % dups


def test_template_links_the_workflow_page_published_beside_it():
    """Published as workflow.html in the same artifact; it links back to index.html."""
    assert 'href="workflow.html"' in P.TEMPLATE.read_text(encoding="utf-8")
    w = (P.REPO / "scripts" / "perf_workflow.html").read_text(encoding="utf-8")
    assert "<title>" in w[:8000] and 'href="index.html"' in w

# ------------------------------------------------------------------ the Build readiness period
# Aaron, 2026-10-12: "an option to change the reporting period for the Build Readiness
# section. It should clear the Sent list and reset it for the current period." The page is
# static, so every period it can be switched to is built in full: its own readiness, the
# decks built FOR it, and the sends recorded AGAINST it - nothing carried over.
def test_readiness_periods_bracket_the_cycle_oldest_first():
    assert P.readiness_periods("2026.10") == ["2026.08", "2026.09", "2026.10", "2026.11"]
    assert P.readiness_periods("2026.01") == ["2025.11", "2025.12", "2026.01", "2026.02"]
    assert P.readiness_periods("2026.12", before=1, after=1) == ["2026.11", "2026.12", "2027.01"]


def test_period_views_carry_each_periods_own_decks_and_sends():
    names = ["1676-2026.09-ARS-ICS-True Sky CU Results.pptx",
             "1676-2026.10-ARS-ICS-True Sky CU Results.pptx",
             "1676-2026.10-ARS-True Sky CU ARS Results.pptx"]
    log = {"1676|2026.09": {"client_id": "1676", "period": "2026.09", "sent_at": "2026-09-16"},
           "1676|2026.08": {"client_id": "1676", "period": "2026.08", "sent_at": "2026-08-20"}}
    v = P.period_views("1676", names, log, ["2026.09", "2026.10", "2026.11"])
    assert v["2026.09"] == {"decks": [names[0]], "sent": "2026-09-16"}
    assert v["2026.10"] == {"decks": sorted(names[1:]), "sent": None}        # built, not yet sent
    assert v["2026.11"] == {"decks": [], "sent": None}                         # nothing for it yet
    # a malformed log entry reads as not sent, never as a date
    assert P.period_views("1676", names, {"1676|2026.10": "yes"}, ["2026.10"])["2026.10"]["sent"] is None


def test_the_page_switches_readiness_decks_and_sent_together():
    src = open(P.TEMPLATE, encoding="utf-8").read() if hasattr(P, "TEMPLATE") else \
        open(os.path.join(os.path.dirname(P.__file__), "perf_dashboard_template.html"), encoding="utf-8").read()
    assert 'id="rperiod"' in src and "DATA.readiness_periods" in src
    assert "function rv(c)" in src and "readiness_by_period" in src and "by_period" in src
    # Sent is keyed on the period showing, and a mark is stamped with that period
    assert "const sentDoc = c => `${c.id}-${rPeriod}`" in src
    assert "period:v.P" in src
    # the choice is shared through the artifact's store, with this browser's own as fallback
    assert 'DB.doc("settings/readiness_period")' in src and "rpe-dash-rperiod" in src


# ------------------------------------------------------------------ one CSM's clients
# Aaron, 2026-11-02: "limit that artifact to my own clients, since we now have Sheila." The page used to
# embed every CSM's clients and filter in the browser, so each client's figures were in the page for
# anyone who could open it. Now another CSM's client is not read and is not in the dataset at all.
import types as _types


def test_scope_defaults_to_aaron_and_is_set_by_flag_or_environment():
    assert P.scope_csm(None, env={}) == "Aaron Burgard"
    assert P.scope_csm(None, env={"RPE_DASH_CSM": " Daniel Wood "}) == "Daniel Wood"
    assert P.scope_csm("Max Willett", env={"RPE_DASH_CSM": "Daniel Wood"}) == "Max Willett", "the flag wins"


@pytest.mark.parametrize("bad", ["all", "ALL", "  "])
def test_there_is_no_all_csms_page(bad):
    with pytest.raises(SystemExit):
        P.scope_csm(bad, env={})


def test_in_scope_matches_the_name_case_insensitively_and_never_a_blank():
    assert P.in_scope("aaron burgard", "Aaron Burgard") and P.in_scope(" Aaron Burgard ", "Aaron Burgard")
    assert not P.in_scope(None, "Aaron Burgard") and not P.in_scope("", "Aaron Burgard")
    assert not P.in_scope("Jordan Berkowitz", "Aaron Burgard")


def _stub_build(monkeypatch, tmp_path, csm_map, programs):
    """build_dataset with every reader stubbed: it records which clients' sections were read."""
    names = {cid: "Client %s" % cid for cid in csm_map}
    all_clients = {cid: {"id": cid, "name": names[cid], "path": "SM", "programs": [],
                         "roster_programs": list(programs.get(cid, ["ARS"])), "programs_from": "clients.md"}
                   for cid in csm_map}
    read = []

    def sec(kind):
        def f(cid, *a, **k):
            read.append((kind, cid))
            return {"name_marker": names[cid]} if kind != "cp" else \
                {"monthly": [], "report_generated": "", "window_loans": 1, "total_loans": 1}
        return f

    monkeypatch.setattr(P.R, "inputs", lambda: tmp_path)
    monkeypatch.setattr(P.R, "outputs", lambda: tmp_path)
    monkeypatch.setattr(P.R, "build_artifacts", lambda: tmp_path)
    monkeypatch.setattr(P.R, "report_dirs", lambda: [tmp_path])
    monkeypatch.setattr(P, "MrpcWeekly", lambda reports: _types.SimpleNamespace(name=None, tabs=[], client=lambda cid: {}))
    monkeypatch.setattr(P, "cashplease_packs", lambda r, w: (None, None, None, "none in this test"))
    monkeypatch.setattr(P, "page_clients", lambda *a, **k: (all_clients, None))
    monkeypatch.setattr(P, "csm_assignments", lambda *a, **k: dict(csm_map))
    monkeypatch.setattr(P, "cashplease_roster", lambda *a, **k: {})
    monkeypatch.setattr(P, "ars_section", sec("ars"))
    monkeypatch.setattr(P, "ics_section", sec("ics"))
    monkeypatch.setattr(P, "mrpc_section", sec("mrpc"))
    monkeypatch.setattr(P, "cp_section", sec("cp"))
    monkeypatch.setattr(P, "decks_and_sent", lambda *a, **k: ([], None, None))
    monkeypatch.setattr(P, "deck_names", lambda *a, **k: [])
    monkeypatch.setattr(P, "read_sent_log", lambda *a, **k: {})
    monkeypatch.setattr(P, "readiness", lambda *a, **k: ({}, None))
    monkeypatch.setattr(P.PO, "client_overviews", lambda ids, *a, **k: {i: {"missing": "stub"} for i in ids})
    monkeypatch.setattr(P.ACT, "load", lambda: None)
    monkeypatch.setattr(P, "vip_pull_date", lambda p: None)
    return names, read


CSMS = {"1001": "Aaron Burgard", "1002": "aaron burgard", "1003": "Jordan Berkowitz", "1004": "Daniel Wood", "1005": None}
PROGS = {"1001": ["ARS", "ICS"], "1002": ["MRPC"], "1003": ["ARS", "ICS", "MRPC"], "1004": ["ARS"], "1005": ["ARS"]}


def test_another_csms_client_is_not_read_and_not_in_the_dataset(monkeypatch, tmp_path):
    names, read = _stub_build(monkeypatch, tmp_path, CSMS, PROGS)
    d = P.build_dataset("2026.11", tmp_path, log=lambda *a: None, csm_name="Aaron Burgard")
    assert [c["id"] for c in d["clients"]] == ["1001", "1002"]
    assert d["scope"] == {"csm": "Aaron Burgard", "clients": 2,
                          "programs": {"ARS": 1, "ICS": 1, "MRPC": 1, "CP": 0}}
    # nothing of anyone else's was extracted, and nothing identifying them is anywhere in the page's data
    assert {cid for _k, cid in read} == {"1001", "1002"}
    blob = json.dumps(d)
    for other in ("1003", "1004", "1005"):
        assert other not in blob and names[other] not in blob, other
    for other_csm in ("Jordan Berkowitz", "Daniel Wood"):
        assert other_csm not in blob
    page = P.render(d)
    assert "Client 1003" not in page and "Jordan Berkowitz" not in page


def test_a_client_no_csm_names_is_not_listed_under_a_guess(monkeypatch, tmp_path):
    _stub_build(monkeypatch, tmp_path, CSMS, PROGS)
    d = P.build_dataset("2026.11", tmp_path, log=lambda *a: None, csm_name="Aaron Burgard")
    assert "1005" not in [c["id"] for c in d["clients"]]


def test_a_csm_with_no_clients_stops_the_build_instead_of_publishing_an_empty_page(monkeypatch, tmp_path):
    _stub_build(monkeypatch, tmp_path, CSMS, PROGS)
    with pytest.raises(SystemExit, match="no client is assigned"):
        P.build_dataset("2026.11", tmp_path, log=lambda *a: None, csm_name="Nobody Here")


def test_the_scope_is_part_of_the_content_hash(monkeypatch, tmp_path):
    _stub_build(monkeypatch, tmp_path, CSMS, PROGS)
    a = P.build_dataset("2026.11", tmp_path, log=lambda *a: None, csm_name="Aaron Burgard")
    b = P.build_dataset("2026.11", tmp_path, log=lambda *a: None, csm_name="Jordan Berkowitz")
    assert P.content_hash(a) != P.content_hash(b)


def _cp_pack(tmp_path, cid, loans, principal, interest, status, dda=None, window=0, comparable=False, cancelled=None):
    d = {"total": {"loans": loans, "principal": principal, "interest": interest},
         "status": {k: {"loans": v} for k, v in {"Overdue": 0, "Charged Off": 0, "Paid Off": 0, **status}.items()},
         "metrics": {"peer_comparable": comparable, "dda_accounts": dda or 0, "window_loans": window}}
    if cancelled:
        d["cancelled"] = cancelled
    (tmp_path / ("%s_cashplease.json" % cid)).write_text(json.dumps(d), encoding="utf-8")


def test_the_cashplease_company_row_is_rates_and_averages_only(tmp_path):
    """Aaron, 2026-09-14: current clients only; 2026-11-02: no other CSM's volume on the page. The row
    still spans every CSM's current clients, so the sums it was built from do not leave current_peer."""
    _cp_pack(tmp_path, "1131", 100, 50000.0, 5000.0, {"Overdue": 5, "Charged Off": 10, "Paid Off": 80},
             dda=4000, window=40, comparable=True)
    _cp_pack(tmp_path, "1750", 300, 150000.0, 9000.0, {"Overdue": 3, "Charged Off": 30, "Paid Off": 250})
    _cp_pack(tmp_path, "1658", 999, 1.0, 1.0, {}, cancelled="2026-09-01")         # cancelled: out
    _cp_pack(tmp_path, "9999", 5000, 1.0, 1.0, {})                                  # not current: out
    peer = P.current_peer(tmp_path, ["1131", "1750", "1658"])
    assert peer["cohort_clients"] == 2
    assert peer["avg_loan_size"] == 500.0 and peer["avg_interest_per_loan"] == 35.0
    assert peer["pct_loans_overdue"] == 8 / 400 and peer["pct_loans_charged_off"] == 40 / 400
    assert peer["charge_off_pct"] is None and peer["pct_active_accounts_with_loans"] is None
    assert peer["loans_per_1k_dda"] == 10.0 and peer["cohort_dda_clients"] == 1
    for volume in ("total_loans", "total_principal", "cohort_dda_accounts", "cohort_window_loans"):
        assert volume not in peer, volume
    assert P.current_peer(tmp_path, []) is None


# ------------------------------------------------------------------ the Hub page
def _template():
    return P.TEMPLATE.read_text(encoding="utf-8")


def test_template_is_the_hub_frame():
    """Aaron, 2026-11-02: "rebuild the RPE Client Performance artifact in hub fashion"."""
    t = _template()
    assert 'class="side"' in t and 'id="fold"' in t and 'id="bottom"' in t, "sidebar that folds, bottom bar on phones"
    for view in ("overview", "ars", "ics", "mrpc", "cp", "roster", "actions"):
        assert '"%s"' % view in t, view
    assert 'href="workflow.html"' in t
    assert 'aria-label="Two stacked slides"' in t and "#1C2541" in t and "#15627E" in t, "the slide-stack corner mark"
    assert "#EEF3FA" in t and "#5FB3C9" in t, "its dark-mode colors"
    assert "--ground:#EDF1F7" in t and "--ground:#0B132B" in t
    assert t.count(':root:not([data-theme="light"])') == 1 and ':root[data-theme="dark"]{' in t
    assert 'name="claude:viewport-fit-sides"' in t
    assert "min-height:44px" in t, "44 px touch targets"


def test_template_uses_hub_colors_and_no_orange():
    t = _template().upper()
    for orange in ("#F47A29", "#F15D22", "#D97706", "#F79552", "#E8590C"):
        assert orange not in t, orange


def test_template_program_colors_are_the_validated_set():
    """Checked with the dataviz validate_palette script (2026-11-02): light on #FFFFFF, dark on #141D38."""
    t = _template()
    assert "--c-ars:#2F5FB5; --c-ics:#B5476B; --c-mrpc:#9A7B10; --c-cp:#8F4FB0;" in t
    assert "--c-ars:#5F86DB; --c-ics:#D0608F; --c-mrpc:#AB8A22; --c-cp:#A06CD0;" in t


def test_template_has_no_csm_or_product_filter_chips_because_the_page_is_one_csms():
    t = _template()
    for gone in ('id="csmchips"', "selCsms", "resetCsm", "selClients", 'id="progchips"'):
        assert gone not in t, gone
    assert "const SCOPE = DATA.scope" in t and "SCOPE.csm" in t
    assert 'id="q"' in t, "one find box filters the view"


def test_template_ranks_say_among_your_n_clients():
    t = _template()
    assert t.lower().count("among your ${ok.length}") == 4, "every ranking names its pool"


def test_template_shows_the_client_overview_and_tags_an_older_extract():
    t = _template()
    assert "function overviewTable(vis){" in t and "overviewTable(vis)" in t
    assert "const stale = DATA.odd_month && o.month !== DATA.odd_month;" in t, "an older extract is tagged"


def test_template_sorts_every_section_table_after_each_render():
    """Aaron, 2026-09-14: sort the product columns too, such as by loss rate."""
    t = _template()
    assert "function applySectionSorts(){" in t
    assert "  applySectionSorts();" in t, "the tables are rebuilt on every update, so the sort is re-applied"
    assert 'section class="card sect" data-sec=' in t, "each section keeps its own sort"
    assert 'first = b.dataset.num === "1" ? -1 : 1' in t, "a numeric column sorts highest first on the first click"
    assert 'rows.filter(r => r.classList.contains("peer")).forEach(r => body.appendChild(r));' in t


def test_template_leads_with_the_total_before_the_month():
    """Aaron, 2026-09-14: a total column, then the last-month figure; ARS revenue to CSI, never a $0 tile."""
    t = _template()
    assert "const csi = ars.filter(c=>c.ars.csi_revenue!=null);" in t, "no $0 tile when the figure is absent"
    assert 'kpi("ARS revenue to CSI"' in t
    assert t.index("<th>Revenue PTD</th><th>Profit PTD</th>") < t.index("<th>Incremental revenue")
    assert t.index("<th>Incremental revenue") < t.index("<th>Revenue to CSI")
    assert "<th>PTD</th><th>YTD</th><th>Last month</th>" in t
    assert "<th>Trailing 12</th><th>Enrollments${sub2(" in t, "MRPC trailing 12 before last month"
    assert t.index('kpi("Referrals, year to date"') < t.index("kpi(`Referrals in"), "YTD tile before last month"


def test_template_draws_its_charts_inline_with_a_hover_layer_and_a_table_view():
    t = _template()
    assert "function trendChart(" in t and 'class="trend"' in t and "data-trend=" in t
    assert 'data-rank="${p.k}:table"' in t and "function rankTable(" in t, "every ranking has a table view"
    assert "<script src" not in t, "no script is loaded: the page works offline"


def test_nothing_animates_but_the_loading_shimmer():
    t = _template()
    assert t.count("animation:") == 2 and "animation:sh 1.1s" in t and "animation:none!important" in t, "only the skeleton shimmer animates, and not under reduced motion"
    assert "prefers-reduced-motion:reduce" in t


def test_workflow_page_uses_hub_colors_and_links_back():
    w = (P.REPO / "scripts" / "perf_workflow.html").read_text(encoding="utf-8").upper()
    for old in ("#F47A29", "#F79552", "#00274C", "#0D9488", "#E7B84C"):
        assert old not in w, old
    assert "--BG:#EDF1F7" in w and "--BG:#0B132B" in w and 'HREF="INDEX.HTML"' in w
