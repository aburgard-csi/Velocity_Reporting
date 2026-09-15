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
    archived = list((tmp_path / "Outputs" / "Archive").rglob("*superseded*"))
    assert len(archived) == 1 and text_of(archived[0]) == "first build"


def test_bad_arguments_stop_with_a_plain_message(capsys):
    assert L.main(["status", "abc"]) == 2
    assert "not a client number" in capsys.readouterr().out
    assert L.main(["status", "1441", "--period", "Sept"]) == 2
