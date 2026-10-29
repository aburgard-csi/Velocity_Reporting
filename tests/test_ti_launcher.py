"""The Transaction Intelligence build in the launcher and in CSM Sheila (Aaron, 2026-10-23): a
SEPARATE presentation from the approved Executive Review, with its own checks and button.

A TI deck in Outputs is never the period's RPE deck, an RPE build never archives one, the
checks name every dependency the cut reads, and the transaction-file count comes from file
names alone.
"""
import json
import os
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build"))
import ars_launcher as L                                         # noqa: E402
import ars_launcher_web as W                                     # noqa: E402
import rpe_env as R                                              # noqa: E402

ROW = {"client_id": "1441", "client_name": "FNB Alaska", "csm": "James Gilmore", "products": "ARS"}
ROSTER = [("1441", "FNB Alaska", "MM", ["ARS"]), ("1632", "WesBanco", None, ["ICS"]),
          ("1537", "Brooks Bank", "MM", ["ARS", "ICS"])]
TI_DECK = "1441-2026.10-TI-ARS-FNB Alaska Transaction Intelligence.pptx"
RPE_DECK = "1441-2026.10-ARS-FNB Alaska ARS Results.pptx"


def levels(checks):
    return [l for l, _ in checks]


def test_a_ti_deck_name_is_told_apart_from_a_program_deck():
    assert L.is_ti_deck(TI_DECK)
    assert L.is_ti_deck(Path("x") / TI_DECK)
    assert not L.is_ti_deck(RPE_DECK)
    assert not L.is_ti_deck("1441-2026.10-ARS-ICS-X Results.pptx")


def test_a_ti_deck_in_outputs_is_not_the_periods_rpe_deck(monkeypatch):
    """Otherwise the RPE build would ask "already in Outputs" over a Transaction Intelligence deck."""
    monkeypatch.setattr(R, "output_decks", lambda pat: [Path("out") / TI_DECK, Path("out") / RPE_DECK])
    assert L.decks_in_outputs("1441", "2026.10") == [RPE_DECK]
    assert L.ti_decks_in_outputs("1441", "2026.10") == [TI_DECK]


def test_an_rpe_build_never_archives_a_ti_deck(tmp_path, monkeypatch):
    out = tmp_path / "Outputs" / "James Gilmore"
    out.mkdir(parents=True)
    (out / TI_DECK).write_bytes(b"ti")
    other = "1441-2026.10-ARS-ICS-FNB Alaska Results.pptx"
    (out / other).write_bytes(b"old mix")
    monkeypatch.setattr(R, "output_decks", lambda pat: [out / TI_DECK, out / other])
    monkeypatch.setattr(R, "client_csm", lambda cid: "James Gilmore")
    new = tmp_path / RPE_DECK
    new.write_bytes(b"new")
    n = L.supersede_other_ars_decks("1441", str(new), tmp_path / "Outputs")
    assert n == 1
    assert (out / TI_DECK).is_file()                 # untouched
    assert not (out / other).exists()                # the other program mix was archived


def test_a_client_not_on_ars_stops_and_names_why():
    checks = L.ti_checks("1632", "2026.10", {"client_id": "1632", "client_name": "WesBanco", "csm": "Aaron Burgard"},
                         ROSTER)
    assert L.STOP in levels(checks)
    assert any("for ARS clients" in m for _, m in checks)


def test_an_unknown_client_stops():
    checks = L.ti_checks("9999", "2026.10", None, ROSTER)
    assert levels(checks) == [L.STOP]


def test_with_no_chapter_ported_there_is_nothing_to_build(monkeypatch):
    cut, *_ = L._ti_modules()
    monkeypatch.setattr(cut, "CHAPTERS", ())
    monkeypatch.setattr(L, "ti_decks_in_outputs", lambda cid, period: [])
    monkeypatch.setattr(L, "input_checks", lambda cid, period: [])
    checks = L.ti_checks("1441", "2026.10", ROW, ROSTER)
    assert any(l == L.STOP and "No chapter" in m for l, m in checks)


def test_decks_already_in_outputs_ask_and_skip_the_slow_checks(monkeypatch):
    monkeypatch.setattr(L, "ti_decks_in_outputs", lambda cid, period: [TI_DECK])
    called = []
    monkeypatch.setattr(L, "input_checks", lambda cid, period: called.append(cid) or [])
    checks = L.ti_checks("1441", "2026.10", ROW, ROSTER)
    assert L.ASK in levels(checks)
    assert called == []
    checks = L.ti_checks("1441", "2026.10", ROW, ROSTER, rebuild=True)
    assert L.ASK not in levels(checks) and called == ["1441"]


def _txn_root(tmp_path, names):
    d = tmp_path / "Txn Files" / "1441"
    d.mkdir(parents=True)
    for n in names:
        with zipfile.ZipFile(d / (n + ".zip"), "w") as z:
            z.writestr(n, b"1441|x|x|1|Monthly Transaction File|1\nrow\n")
    return tmp_path / "Txn Files"


def test_the_transaction_months_are_counted_from_file_names_without_opening_a_zip(tmp_path, monkeypatch):
    """A file dated in month M carries month M-1's data (v5's rule), and the window ends at the
    cycle's data month, the month before it: the 2026.10 cycle's window is Oct 25 to Sep 26, and
    the files are those dated Nov 25 to Oct 26."""
    root = _txn_root(tmp_path, [f"1441_1_[2026.{m:02d}.03][10.00.00]_monthlytran.csv" for m in range(1, 11)]
                     + ["1441_1_[2026.05.03][10.00.00]_deposits.csv",        # not a transaction file
                        "1441_1_[2025.06.03][10.00.00]_monthlytran.csv"])    # outside the window
    monkeypatch.setattr(R, "txn_files", lambda cid=None, root_=None: sorted((root / str(cid)).iterdir()))
    opened = []
    real = zipfile.ZipFile.__init__
    monkeypatch.setattr(zipfile.ZipFile, "__init__", lambda self, *a, **k: opened.append(a) or real(self, *a, **k))
    found, window = L.txn_months_on_hand("1441", "2026.10")
    assert opened == []
    assert len(window) == 12
    assert L._month_label(window[0]) == "Oct 25" and L._month_label(window[-1]) == "Sep 26"
    # files dated Jan..Oct 2026 carry Dec 25..Sep 26: ten months, Oct 25 and Nov 25 missing
    assert len(found) == 10
    assert {L._month_label(n) for n in window if n not in found} == {"Oct 25", "Nov 25"}


def test_the_checks_name_each_dependency(tmp_path, monkeypatch):
    cut, *_ = L._ti_modules()
    monkeypatch.setattr(cut, "CHAPTERS", (type("Ch", (), {"title": "Portfolio"})(),))
    monkeypatch.setattr(L, "ti_decks_in_outputs", lambda cid, period: [])
    monkeypatch.setattr(L, "input_checks", lambda cid, period: [(L.OK, "ODD extract: in Inputs (2026-10-07)")])
    monkeypatch.setattr(L, "code_table_clients", lambda: frozenset({"1441"}))
    monkeypatch.setattr(L, "txn_months_on_hand", lambda cid, period, months=12: (set(), list(range(2025 * 12 + 10, 2025 * 12 + 22))))
    monkeypatch.setattr(L._ti_modules()[3], "config_path", lambda: tmp_path / "none.json")
    checks = L.ti_checks("1441", "2026.10", ROW, ROSTER)
    text = " | ".join(m for _, m in checks)
    assert "Chapters: Portfolio; lenses: ARS" in text
    assert "ODD extract" in text and "ars_code_tables.json" in text
    assert any(l == L.WARN and "Transaction files: none" in m for l, m in checks)
    assert L.STOP not in levels(checks)
    # a client the code tables do not carry cannot be built
    monkeypatch.setattr(L, "code_table_clients", lambda: frozenset())
    assert any(l == L.STOP and "not in ars_code_tables.json" in m for l, m in L.ti_checks("1441", "2026.10", ROW, ROSTER))


def test_an_ics_client_reports_its_ics_lists(tmp_path, monkeypatch):
    cut, _, ti_lens, ti_config = L._ti_modules()
    monkeypatch.setattr(cut, "CHAPTERS", (type("Ch", (), {"title": "Portfolio"})(),))
    monkeypatch.setattr(L, "ti_decks_in_outputs", lambda cid, period: [])
    monkeypatch.setattr(L, "input_checks", lambda cid, period: [])
    monkeypatch.setattr(L, "code_table_clients", lambda: frozenset({"1537"}))
    monkeypatch.setattr(L, "txn_months_on_hand", lambda cid, period, months=12: (set(range(2025 * 12 + 10, 2025 * 12 + 22)), list(range(2025 * 12 + 10, 2025 * 12 + 22))))
    monkeypatch.setattr(ti_config, "config_path", lambda: tmp_path / "none.json")
    monkeypatch.setattr(ti_lens, "ics_list_files", lambda cid: {"DM": tmp_path / "1537-dm.xlsx", "REF": None})
    row = dict(ROW, client_id="1537", client_name="Brooks Bank")
    checks = L.ti_checks("1537", "2026.10", row, ROSTER)
    text = " | ".join(m for _, m in checks)
    assert "lenses: ARS and ICS" in text and "ICS lens: DM 1537-dm.xlsx" in text
    monkeypatch.setattr(ti_lens, "ics_list_files", lambda cid: {"DM": None, "REF": None})
    assert any(l == L.WARN and "only the ARS lens" in m for l, m in L.ti_checks("1537", "2026.10", row, ROSTER))


def test_the_code_tables_are_read_again_only_when_the_file_changes(tmp_path, monkeypatch):
    p = tmp_path / "ARS Settings" / "ars_code_tables.json"
    p.parent.mkdir()
    p.write_text(json.dumps({"status_codes": {"1441": {}}, "product_codes": {"1537": {}}}), encoding="utf-8")
    monkeypatch.setattr(R, "input_dir", lambda kind, create=True: tmp_path / "ARS Settings")
    L._CODE_TABLE_CLIENTS.clear()
    assert L.code_table_clients() == frozenset({"1441", "1537"})
    reads = []
    real = Path.read_text
    monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: reads.append(self.name) or real(self, *a, **k))
    L.code_table_clients()
    assert reads == []                                   # same size and mtime: not parsed again
    p.write_text(json.dumps({"status_codes": {"1441": {}, "1600": {"a": 1}}, "x": 1}), encoding="utf-8")
    os.utime(p, (p.stat().st_atime, p.stat().st_mtime + 5))
    assert L.code_table_clients() == frozenset({"1441", "1600"})
    p.unlink()
    assert L.code_table_clients() is None


def test_a_ti_deck_goes_to_outputs_and_supersedes_only_its_own_name(tmp_path, monkeypatch):
    out = tmp_path / "Outputs"
    dest = out / "James Gilmore"
    dest.mkdir(parents=True)
    (dest / TI_DECK).write_bytes(b"old ti")
    (dest / RPE_DECK).write_bytes(b"rpe")
    monkeypatch.setattr(R, "outputs", lambda: out)
    monkeypatch.setattr(R, "client_outputs", lambda cid, root=None: dest)
    monkeypatch.setattr(R, "client_csm", lambda cid: "James Gilmore")
    import promote_month as P
    monkeypatch.setattr(P, "same", lambda a, b: Path(a).read_bytes() == Path(b).read_bytes())   # the real one reads a .pptx
    new = tmp_path / TI_DECK
    new.write_bytes(b"new ti")
    lvl, msg = L.ti_to_outputs("1441", str(new), "FNB Alaska")
    assert lvl == L.OK and TI_DECK in msg
    assert (dest / TI_DECK).read_bytes() == b"new ti"
    assert (dest / RPE_DECK).read_bytes() == b"rpe"           # the RPE deck is not touched
    arch = list((dest / R.ARCHIVE_DIRNAME).rglob("*superseded*"))
    assert len(arch) == 1 and arch[0].read_bytes() == b"old ti"
    # identical again: nothing moves
    lvl, msg = L.ti_to_outputs("1441", str(new), "FNB Alaska")
    assert lvl == L.OK and "already identical" in msg
    assert len(list((dest / R.ARCHIVE_DIRNAME).rglob("*superseded*"))) == 1


def test_the_launcher_takes_ti_on_status_and_build(capsys):
    """`--ti` is accepted by both; a bad client number still stops first."""
    assert L.main(["status", "12", "--ti"]) == 2
    assert L.main(["build", "12", "--ti"]) == 2


# ------------------------------------------------------------------ Sheila
def test_sheila_runs_the_launcher_with_ti_for_a_ti_build():
    assert W.build_cmd("1441", False, False, "2026.10", ti=True)[-1] == "--ti"
    assert "--ti" not in W.build_cmd("1441", False, False, "2026.10")
    assert "--combined" not in W.build_cmd("1441", True, False, "2026.10", ti=True)
    job = W.Job("1441", False, ti=True)
    assert job.to_json()["ti"] is True and job.to_json()["combined"] is False


def test_the_status_carries_the_ti_block_for_an_ars_client_only(monkeypatch):
    import build_month as BM
    import deck_status as DS
    monkeypatch.setattr(W, "current_period", lambda: "2026.10")
    monkeypatch.setattr(L, "csm_list_row", lambda cid: dict(ROW, client_id=cid))
    monkeypatch.setattr(BM, "read_roster", lambda *a, **k: (ROSTER, []))
    monkeypatch.setattr(DS, "read_deliveries", lambda: {"sent": {}})
    monkeypatch.setattr(L, "cp_roster_row", lambda cid: None)
    monkeypatch.setattr(L, "all_checks", lambda *a, **k: [(L.OK, "fine")])
    monkeypatch.setattr(L, "program_availability", lambda *a, **k: {})
    monkeypatch.setattr(L, "ti_status", lambda cid, period, row, roster, sent: {
        "checks": [{"level": L.OK, "text": "Chapters: Portfolio"}], "state": "ready", "last": None, "decks": []})
    doc = W.compute_status("1441")
    assert doc["ti"]["state"] == "ready"
    assert W.compute_status("1632")["ti"] is None            # no ARS: no cut
    # a failing TI check never costs the RPE status
    monkeypatch.setattr(L, "ti_status", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    doc = W.compute_status("1441")
    assert doc["state"] == "ready" and doc["ti"]["state"] == "stop" and "boom" in doc["ti"]["checks"][0]["text"]


def test_the_list_keeps_ti_decks_apart_from_the_rpe_deck(tmp_path, monkeypatch):
    import build_month as BM
    import deck_status as DS
    monkeypatch.setattr(W, "current_period", lambda: "2026.10")
    monkeypatch.setattr(BM, "read_roster", lambda *a, **k: (ROSTER[:1], []))
    monkeypatch.setattr(BM, "read_cashplease_roster", lambda: [], raising=False)
    monkeypatch.setattr(DS, "read_deliveries", lambda: {"sent": {}})
    monkeypatch.setattr(R, "csm_list_file", lambda: None)
    monkeypatch.setattr(R, "output_decks", lambda pat: [Path("o") / TI_DECK])
    monkeypatch.setattr(W, "launcher_results", lambda period, cids: {})
    monkeypatch.setattr(W, "last_build_failed", lambda *a, **k: False)
    monkeypatch.setattr(W, "available_periods", lambda n=12: ["2026.10"])
    c = next(x for x in W.compute_clients()["clients"] if x["id"] == ROSTER[0][0])   # with the share on, ILS folders list other clients first
    assert c["decks"] == [] and c["ti_decks"] == [TI_DECK]
