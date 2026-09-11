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

| ID | Client | Build | Loans | Ships as | Note |
| --- | --- | --- | --- | --- | --- |
| 1131 | People's Bank AL | yes | 10,507 | standalone module | |
| 1658 | Truliant FCU | **no** | 8,296 | — | cancelled |
| 1734 | Altamaha Bank and Trust Company | yes | 646 | ICS-CP | |

## Something else
| 9999 | Not a CashPlease client | yes | | | |
"""


def test_cashplease_roster_reads_build_yes_rows_only():
    assert P.cashplease_roster(ROSTER) == {"1131": "People's Bank AL",
                                           "1734": "Altamaha Bank and Trust Company"}


def test_cashplease_roster_absent_is_empty():
    assert P.cashplease_roster("# nothing here") == {}


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
