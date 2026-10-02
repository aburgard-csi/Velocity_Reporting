"""The ARS launcher's rules — the ones that used to be applied by hand (2026-09-15)."""
import os
import sys
import time

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "scripts"), os.path.join(REPO, "build")]
import ars_launcher as L  # noqa: E402

ROSTER = [("1441", "FNB Alaska", "MM", ["ARS"]), ("1509", "Texas Bay Credit Union", "MM", ["ARS", "ICS"]),
          ("1632", "WesBanco", None, ["ICS"])]
ROW = {"client_id": "1441", "client_name": "FNB Alaska", "csm": "James Gilmore", "products": "ARS; ILS"}


def levels(checks):
    return [lvl for lvl, _ in checks]


def test_a_ready_ars_client_passes_the_rules():
    assert L.STOP not in levels(L.rule_checks("1441", "2026.09", ROW, ROSTER, {}))


def test_an_unknown_client_stops():
    assert levels(L.rule_checks("9999", "2026.09", {}, ROSTER, {})) == [L.STOP]


def test_a_client_without_the_ars_product_stops_even_if_clients_md_lists_it():
    row = dict(ROW, products="ICS; ILS")
    msgs = [m for l, m in L.rule_checks("1441", "2026.09", row, ROSTER, {}) if l == L.STOP]
    assert msgs and "Not an ARS client" in msgs[0]


def test_a_client_clients_md_does_not_list_for_ars_stops():
    row = {"client_id": "1632", "client_name": "WesBanco", "csm": "Aaron Burgard", "products": "ARS; ICS"}
    msgs = [m for l, m in L.rule_checks("1632", "2026.09", row, ROSTER, {}) if l == L.STOP]
    assert msgs and "clients.md" in msgs[0]


def test_a_sent_deck_asks_rather_than_stops():
    sent = {"1441|2026.09": {"sent_at": "2026-09-14"}}
    lv = levels(L.rule_checks("1441", "2026.09", ROW, ROSTER, sent))
    assert L.ASK in lv and L.STOP not in lv
    lv = levels(L.rule_checks("1441", "2026.09", ROW, ROSTER, sent, rebuild=True))
    assert L.ASK not in lv and L.STOP not in lv


def test_a_deck_already_in_outputs_asks_before_it_is_rebuilt():
    # FedChoice 1815 (2026-09-15): in Outputs, never marked sent, and the builder offered a plain build.
    deck = ["1815-2026.09-ARS-FedChoice FCU ARS Results.pptx"]
    checks = L.rule_checks("1441", "2026.09", ROW, ROSTER, {}, in_outputs=deck)
    asks = [m for l, m in checks if l == L.ASK]
    assert asks and "already in Outputs" in asks[0] and L.STOP not in levels(checks)
    checks = L.rule_checks("1441", "2026.09", ROW, ROSTER, {}, rebuild=True, in_outputs=deck)
    assert L.ASK not in levels(checks) and any("as asked" in m for l, m in checks if l == L.WARN)
    assert L.ASK not in levels(L.rule_checks("1441", "2026.09", ROW, ROSTER, {}, in_outputs=[]))


def test_the_ask_exit_code_is_the_one_the_launcher_bat_tests_first():
    bat = open(os.path.join(REPO, "scripts", "launchers", "Build ARS Deck.bat"), encoding="ascii").read()
    assert L.ASKED_EXIT == 3 and "if errorlevel 3 goto sent" in bat
    assert bat.index("if errorlevel 3") < bat.index("if errorlevel 1")
    assert "build %CID% --rebuild" in bat


def test_a_blank_product_list_warns_rather_than_stops():
    row = dict(ROW, products="")
    assert levels(L.rule_checks("1441", "2026.09", row, ROSTER, {})).count(L.STOP) == 0


def test_a_fresh_lock_stops_a_second_build(tmp_path):
    L.lock(tmp_path)
    with pytest.raises(SystemExit) as e:
        L.lock(tmp_path)
    assert "already building" in str(e.value)


def test_a_stale_lock_is_taken_over(tmp_path):
    p = L.lock(tmp_path)
    old = time.time() - (L.LOCK_STALE_HOURS + 1) * 3600
    os.utime(p, (old, old))
    assert L.lock(tmp_path).exists()


def test_build_log_command_lines_name_their_step():
    py = r"C:\Users\x\AppData\Local\RPE\Python\python.exe"
    assert L.step_of(f"$ {py} \\\\srv\\Tools\\RPE\\build\\ars_pipeline/metrics_gen.py a.zip m.json") \
        == "Computing the ODD metrics"
    assert L.step_of(f"$ {py} C:\\repo\\scripts/oddd_optimize.py --input 1441_ODDD.zip") == "Reading the ODD extract"
    assert L.step_of("OK 1441 FNB Alaska: 34,465 accts") is None
    assert L.step_of(f"$ {py} something_else.py") is None


def test_build_log_carries_each_command_line_before_its_output(tmp_path):
    import build_month as BM
    log = tmp_path / "build.log"
    BM.run([sys.executable, "-c", "import sys; print('child stdout'); print('child stderr', file=sys.stderr)"], str(log))
    text = log.read_text(encoding="utf-8")
    assert text.index("$ ") < text.index("child stdout") and text.index("$ ") < text.index("child stderr")


def test_aarons_multi_program_client_stops_before_the_build():
    # A clean build goes straight to Outputs, so a lone ARS deck must be refused up front.
    row = {"client_id": "1509", "client_name": "Texas Bay Credit Union", "csm": "Aaron Burgard", "products": "ARS; ICS"}
    msgs = [m for l, m in L.rule_checks("1509", "2026.09", row, ROSTER, {}) if l == L.STOP]
    assert msgs and "combined ARS-ICS" in msgs[0]
    other = dict(row, csm="James Gilmore")
    assert L.STOP not in levels(L.rule_checks("1509", "2026.09", other, ROSTER, {}))
    # a combined build is what's on offer for Aaron's multi-program clients (2026-09-16)
    assert L.STOP not in levels(L.rule_checks("1509", "2026.09", row, ROSTER, {}, combined=True))


def test_program_availability_prefers_vip_then_local_ics_files(monkeypatch):
    import rpe_env as R
    import types

    def resolve(cid, prog):
        if (cid, prog) == ("1509", "ics"):
            return "vip.json"
        raise SystemExit("no sheet")
    monkeypatch.setattr(R, "resolve_client_json", resolve)
    fake = types.SimpleNamespace(available=lambda cid, period: {"ok": cid == "1776", "reason": "ICS workbook and referral files"})
    monkeypatch.setitem(sys.modules, "ics_local_sheet", fake)
    # CashPlease comes from its own roster table and is tested below; this test is about
    # which ICS source wins.
    monkeypatch.setattr(L, "cashplease_availability", lambda cid: None)
    a = L.program_availability("1509", "2026.09", ["ARS", "ICS", "MRPC"])
    assert a == {"ICS": (True, "VIP ICS sheet"), "MRPC": (False, "no VIP MRPC sheet")}
    b = L.program_availability("1776", "2026.09", ["ARS", "ICS", "MRPC"])
    assert b["ICS"] == (True, "ICS workbook and referral files") and L.combined_programs(b) == ["ICS"]
    assert L.combined_programs(L.program_availability("1441", "2026.09", ["ARS"])) == []


# ------------------------------------------------------------------ CashPlease in the combined deck
def _cp_roster(monkeypatch, rows, workbook=True):
    import types, pathlib
    import build_month as BM
    monkeypatch.setattr(BM, "read_cashplease_roster", lambda *a, **k: rows)
    import rpe_env as R
    monkeypatch.setattr(R, "report_files",
                        lambda pat: [pathlib.Path("CashPleaseSummaryV1_260927_081811.xlsx")]
                        if workbook else [])


def _row(cid, build=True, ships_as="ARS-ICS-MRPC-CP section"):
    return {"client_id": cid, "client_name": "X", "build": build,
            "ships_as": ships_as, "csm": "Aaron Burgard", "note": ""}


def test_a_client_who_ships_cashplease_as_a_section_gets_it_in_the_combined_deck(monkeypatch):
    """1539 Marine's deck is ARS-ICS-MRPC-CP. A combined rebuild built ARS-ICS-MRPC and
    archived the four-product deck as "a different program mix", because CashPlease is not in
    clients.md's MAIN roster row — it has its own table (Aaron, 2026-10-02)."""
    _cp_roster(monkeypatch, [_row("1539")])
    ok, why = L.cashplease_availability("1539")
    assert ok and "CashPlease roster" in why


def test_a_standalone_cashplease_client_is_not_folded_into_a_combined_deck(monkeypatch):
    """A client whose slides ship inside a combined deck does not also get a module, and the
    reverse: a module client's slides do not join someone's combined deck (CLAUDE.md)."""
    _cp_roster(monkeypatch, [_row("1770", ships_as="standalone deck")])
    assert L.cashplease_availability("1770") is None


def test_a_roster_row_marked_no_build_is_not_offered(monkeypatch):
    _cp_roster(monkeypatch, [_row("1658", build=False)])
    assert L.cashplease_availability("1658") is None


def test_a_client_off_the_cashplease_roster_has_no_cashplease(monkeypatch):
    _cp_roster(monkeypatch, [_row("1539")])
    assert L.cashplease_availability("1075") is None


def test_no_weekly_workbook_is_reported_not_silently_dropped(monkeypatch):
    _cp_roster(monkeypatch, [_row("1539")], workbook=False)
    ok, why = L.cashplease_availability("1539")
    assert not ok and "no CashPleaseSummary workbook" in why


def test_cashplease_is_last_in_section_order():
    """The deck runs ARS, ICS, MRPC, CashPlease, and deck_tag names the file from this
    order — 1539's is ARS-ICS-MRPC-CP."""
    avail = {"ICS": (True, ""), "MRPC": (True, ""), "CP": (True, "")}
    assert L.combined_programs(avail) == ["ICS", "MRPC", "CP"]
    import build_month as BM
    assert BM.deck_tag(["ARS"] + L.combined_programs(avail)) == "ARS-ICS-MRPC-CP"


def test_combined_checks_stop_when_no_other_program_has_data(monkeypatch):
    monkeypatch.setattr(L, "program_availability", lambda cid, period, progs: {"MRPC": (False, "no VIP MRPC sheet")})
    checks = L.combined_checks("1509", "2026.09", ROSTER)
    assert L.STOP in levels(checks) and any("left out" in m for l, m in checks if l == L.WARN)
    monkeypatch.setattr(L, "program_availability", lambda cid, period, progs: {"ICS": (True, "VIP ICS sheet")})
    assert L.STOP not in levels(L.combined_checks("1509", "2026.09", ROSTER))


def test_a_different_program_mix_supersedes_the_other_deck_in_outputs(tmp_path, monkeypatch):
    import rpe_env as R
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(R, "client_csm", lambda cid: "James Gilmore")
    out = tmp_path / "Outputs"
    (out / "James Gilmore").mkdir(parents=True)
    ars_only = out / "James Gilmore" / "1776-2026.09-ARS-CoastHills CU ARS Results.pptx"
    ars_only.write_bytes(b"x")
    combined = tmp_path / "1776-2026.09-ARS-ICS-CoastHills CU Results.pptx"
    combined.write_bytes(b"y")
    assert L.supersede_other_ars_decks("1776", str(combined), out) == 1
    assert not ars_only.exists()
    archived = list((out / R.ARCHIVE_DIRNAME).rglob("*.pptx"))
    assert len(archived) == 1 and "(superseded" in archived[0].name


def test_a_clean_deck_goes_straight_to_outputs_and_archives_what_it_replaces(tmp_path, monkeypatch):
    import rpe_env as R
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    (tmp_path / "Outputs").mkdir()
    monkeypatch.setattr(R, "client_csm", lambda cid: "James Gilmore")
    work = tmp_path / "Build Artifacts" / "launcher" / "2026.09" / "1441"
    work.mkdir(parents=True)
    from pptx import Presentation
    from pptx.util import Inches

    def make_deck(path, text):
        # promote_month.same compares rendered content, so these must be real decks.
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1)).text_frame.text = text
        prs.save(str(path))

    def text_of(path):
        return next(sh.text_frame.text for sh in Presentation(str(path)).slides[0].shapes if sh.has_text_frame)

    deck = work / "1441-2026.09-ARS-FNB Alaska ARS Results.pptx"
    make_deck(deck, "first build")
    live = tmp_path / "Outputs" / "James Gilmore" / deck.name

    lvl, msg = L.to_outputs("1441", str(deck))
    assert lvl == L.OK and text_of(live) == "first build"

    lvl, msg = L.to_outputs("1441", str(deck))
    assert lvl == L.OK and "already identical" in msg

    make_deck(deck, "rebuilt")
    lvl, msg = L.to_outputs("1441", str(deck))
    assert lvl == L.OK and text_of(live) == "rebuilt"
    archived = list((tmp_path / "Outputs" / R.ARCHIVE_DIRNAME).rglob("*superseded*"))
    assert len(archived) == 1 and text_of(archived[0]) == "first build"


def test_the_client_is_named_from_clients_md_not_a_flagged_list_name():
    roster = ROSTER + [("1780", "USF CU", "MM", ["ARS", "MRPC"])]
    row = {"client_id": "1780", "client_name": "LM EXPIRED-USF CU / USF CU", "csm": "James Gilmore", "products": "ARS"}
    msgs = [m for _, m in L.rule_checks("1780", "2026.09", row, roster, {})]
    assert msgs[0].startswith("1780 USF CU (CSM")


def _lift(monkeypatch, workbook, window):
    import build_month as BM
    monkeypatch.setattr(BM, "ars_workbook", lambda dirs, cid, period: [workbook] if workbook else [])
    monkeypatch.setattr(L, "workbook_window", lambda path: window)


EXPIRED = {"window": "Mar 2025 – Feb 2026", "data_date": "Aug 2026", "data_past_end": True, "in_window": False}
CURRENT = {"window": "May 2026 – Apr 2027", "data_date": "Aug 2026", "data_past_end": False, "in_window": True}
MM_ROSTER = ROSTER + [("1780", "USF CU", "MM", ["ARS"]), ("1038", "Sugar River Bank", "SM", ["ARS"])]


def test_an_expired_lift_matrix_stops_the_build(monkeypatch):
    _lift(monkeypatch, r"x\1780-2026.09-USF CU-Workbook_v2_1_0.xlsx", EXPIRED)
    checks = L.lift_checks("1780", "2026.09", MM_ROSTER)
    assert levels(checks) == [L.STOP] and "Lift Matrix expired" in checks[0][1] and "Feb 2026" in checks[0][1]


def test_the_data_teams_filename_flag_stops_the_build_even_inside_the_window(monkeypatch):
    _lift(monkeypatch, r"x\1453-2026.09-Connex CU-Workbook_v2_1_0_LM EXPIRED.xlsx", CURRENT)
    checks = L.lift_checks("1780", "2026.09", MM_ROSTER)
    assert levels(checks) == [L.STOP] and "LM EXPIRED" in checks[0][1]


def test_a_current_lift_matrix_passes_and_sm_clients_are_not_checked(monkeypatch):
    _lift(monkeypatch, r"x\1780-2026.09-USF CU-Workbook_v2_1_0.xlsx", CURRENT)
    assert levels(L.lift_checks("1780", "2026.09", MM_ROSTER)) == [L.OK]
    assert L.lift_checks("1038", "2026.09", MM_ROSTER) == []
    _lift(monkeypatch, None, CURRENT)
    assert L.lift_checks("1780", "2026.09", MM_ROSTER) == [], "a missing workbook is input_checks' STOP"


def test_bad_arguments_stop_with_a_plain_message(capsys):
    assert L.main(["status", "abc"]) == 2
    assert "not a client number" in capsys.readouterr().out
    assert L.main(["status", "1441", "--period", "Sept"]) == 2
