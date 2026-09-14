"""refresh_performance_dashboard — the rules that decide whether the artifact is
republished, and what period it claims.

  * The period is the newest ARS workbook on Inputs/, not today's month: the page
    rolls forward when the workbooks are copied, not before.
  * "Changed" means the figures moved. The generation date is excluded from the
    hash, or every daily rebuild would republish an identical page.
  * No dataset value can close the page's script tag.
"""
import json

import pytest

import refresh_performance_dashboard as P


# ------------------------------------------------------------------ period
def test_period_is_the_newest_ars_workbook():
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
def test_template_marks_sent_against_the_deck_period_not_the_cycle():
    """The log is keyed <client>|<deck period>; the button must use the same key,
    or a send would be recorded against a period the deck does not belong to."""
    t = P.TEMPLATE.read_text(encoding="utf-8")
    assert "sentDoc = c => c.deck_period" in t
    assert 'DB.doc("deliveries/"' in t


def test_template_cannot_mark_a_client_with_no_deck():
    """Sent is recorded, never inferred — and never for a deck that was not built."""
    t = P.TEMPLATE.read_text(encoding="utf-8")
    assert "if (!c.decks.length) return" in t


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
    assert P.csm_assignments(ids, "2026.09", work, root=root, log=_quiet) == {
        "1131": "Aaron Burgard", "1204": "Aaron Burgard", "1771": None}
    # Off the VPN the share's last answer stands, so the page (and its hash) do not move.
    assert P.csm_assignments(ids, "2026.09", work, root=str(tmp_path / "offline"),
                             log=_quiet)["1204"] == "Aaron Burgard"


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
                            log=said.append)
    assert got == {"1204": "Aaron Burgard", "1771": "Aaron Burgard", "1750": "From Settings"}
    assert any("1204" in s and "Daniel Wood" in s for s in said)


def test_settings_csm_reads_the_record_and_is_none_without_one(tmp_path, monkeypatch):
    rec = tmp_path / "1632_cp_settings.json"
    rec.write_text(json.dumps({"CSM": " Aaron Burgard "}))
    monkeypatch.setattr(P.R, "cp_settings_file", lambda cid: rec if cid == "1632" else None)
    assert P.settings_csm("1632") == "Aaron Burgard"
    assert P.settings_csm("1771") is None


def test_template_filters_by_csm_and_never_assigns_a_default():
    """A client with no CSM is Unassigned on the page, never filed under a guess."""
    t = P.TEMPLATE.read_text(encoding="utf-8")
    assert 'id="csmchips"' in t
    assert "const csmOf = c => c.csm || UNASSIGNED" in t
    assert "inCsm(c) && selClients.has(c.id)" in t


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

    clients, folder = P.page_clients("2026.09", work, weekly, packs, log=_quiet)
    assert folder == "2026.09"
    assert sorted(clients) == ["1095", "1147", "1156", "1204"], "1437 is stopped in clients.md"
    assert clients["1204"]["programs_from"] == "clients.md" and clients["1204"]["roster_programs"] == ["ARS"]
    assert clients["1095"] == {"id": "1095", "name": "Landmark Bank", "path": None, "programs": [],
                               "roster_programs": ["ARS"], "programs_from": "data",
                               "share_kinds": ["DCO", "WORKBOOK"]}
    assert clients["1147"]["roster_programs"] == ["CP"]
    assert clients["1156"]["roster_programs"] == [], "a DCO alone implies no program"


def test_template_product_chips_isolate_from_all_like_the_other_filters():
    t = P.TEMPLATE.read_text(encoding="utf-8")
    assert "const all = selProgs.size===PROGS.length;" in t
    assert "if(e.shiftKey || e.altKey || all){ selProgs = new Set([k]); }" in t


def test_template_lists_a_client_with_no_program_data_under_all_products():
    t = P.TEMPLATE.read_text(encoding="utf-8")
    assert ("const inProducts = c => c.programs.length ? c.programs.some(k=>selProgs.has(k))"
            " : selProgs.size===PROGS.length;") in t
    assert "inCsm(c) && selClients.has(c.id) && inProducts(c)" in t
    assert 'c.programs_from === "data"' in t


def test_template_saves_all_as_all_so_new_clients_are_not_hidden():
    """A saved list of yesterday's "all" narrows today's page to yesterday's clients."""
    t = P.TEMPLATE.read_text(encoding="utf-8")
    assert 'const FILTER_KEY = "rpe-dash-filter-v2";' in t
    assert "set.size===n ? null : [...set]" in t
    assert 'localStorage.getItem("rpe-dash-filter")' not in t


def test_template_filters_allow_an_empty_selection():
    """Aaron, 2026-09-14: the last selected chip in a row can be clicked off too."""
    t = P.TEMPLATE.read_text(encoding="utf-8")
    for sel in ("selProgs", "selCsms", "selClients"):
        assert "if(%s.size>1)" % sel not in t, sel
    assert "if (!saved.length) return new Set();" in t, "an empty selection must survive a reload"
    assert "No CSM is selected." in t
    # the per-render reset that silently turned an empty client selection back into all
    assert "if (!clients.some(c=>inCsm(c) && selClients.has(c.id))) selClients" not in t


def test_template_chips_show_three_states_and_each_row_leads_with_all():
    """Aaron, 2026-09-14: white while the whole row is selected, blue on, light gray off."""
    t = P.TEMPLATE.read_text(encoding="utf-8")
    for token in ("--chip-all:#FFFFFF", "--chip-on:#245C8C", "--chip-off:#E9EDF1"):
        assert token in t, token
    assert ".chip{appearance:none;border:1px solid var(--hair);background:var(--chip-off);" in t
    assert "class=\"chip ${allM?'in':(selCsms.has(m)?'on':'')}\"" in t
    assert "class=\"chip ${allP?'in':(selProgs.has(p.k)?'on':'')}\"" in t
    assert "class=\"chip ${allC?'in':(selClients.has(c.id)?'on':'')}" in t
    for rid in ("resetCsm", "resetProg", "resetClient"):
        assert 'class="chip all" id="%s"' % rid in t, rid
    assert "persist(); renderChips(); markAllChips();" in t


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


def test_template_shows_the_client_overview_first_whatever_the_products():
    """Client-level figures, so the section is not gated on a product chip."""
    t = P.TEMPLATE.read_text(encoding="utf-8")
    assert "function secOverview(vis){" in t
    assert 'const html = [safe("Client overview",()=>secOverview(vis)),' in t
    assert "const stale = DATA.odd_month && o.month !== DATA.odd_month;" in t, "an older extract is tagged"


def test_template_sorts_every_section_table_after_each_render():
    """Aaron, 2026-09-14: sort the product columns too, such as by loss rate."""
    t = P.TEMPLATE.read_text(encoding="utf-8")
    assert "function applySectionSorts(){" in t
    assert "  applySectionSorts();" in t, "the tables are rebuilt on every update, so the sort is re-applied"
    assert 'data-sec="${esc(p.k || p.name)}"' in t, "each section keeps its own sort"
    assert 'first = b.dataset.num === "1" ? -1 : 1' in t, "a numeric column sorts highest first on the first click"
    assert 'rows.filter(r => r.classList.contains("peer")).forEach(r => body.appendChild(r));' in t


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


def test_template_leads_with_the_total_before_the_month():
    """Aaron, 2026-09-14: a total column, then the last-month figure; no ARS profit or revenue
    callouts, and ARS revenue to CSI shown instead."""
    t = P.TEMPLATE.read_text(encoding="utf-8")
    assert "incremental profit, program to date" not in t
    assert "revenue to CSI, ${csi[0].ars.data_label" in t
    assert "const csi = ars.filter(c=>c.ars.csi_revenue!=null);" in t, "no $0 tile when the figure is absent"
    assert t.index("<th>Revenue PTD</th><th>Profit PTD</th>") < t.index("<th>Incremental revenue")
    assert t.index("<th>Incremental revenue") < t.index("<th>Revenue to CSI")
    assert "<th>PTD</th><th>YTD</th><th>Last month</th>" in t
    assert "<th>Trailing 12</th><th>Enrollments<br>" in t, "MRPC trailing 12 before last month"
    ics_tiles = t[t.index("if(ics.length) tiles.push("):]
    assert ics_tiles.index("c.ics.ytd") < ics_tiles.index("c.ics.prev_month"), "YTD tile before last month"


def test_template_clients_row_folds_and_says_how_far_it_is_narrowed():
    """Aaron, 2026-09-14: make the Clients filter collapsible. Closed by default."""
    t = P.TEMPLATE.read_text(encoding="utf-8")
    assert 'id="toggleClients" aria-expanded="false" aria-controls="clientchips"' in t
    assert '<span class="chipset" id="clientchips" hidden></span>' in t, "closed on first load"
    assert "persist(); renderChips(); markAllChips(); renderClientFold();" in t
    assert "of ${scoped.length} selected)" in t


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
