"""The ARS Companion deck (Aaron, 2026-10-27): James Gilmore's analysis slides as a SEPARATE presentation,
built from the ARS pipeline with every opt-in view on and cut down to the slides those views added.

A COMP deck in Outputs is never the period's RPE deck, an RPE build never archives one, the cut keeps the
cover, the views, Questions and Contact and nothing else, and Sheila offers it as its own panel and button.
"""
import json
import os
import sys
from pathlib import Path

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ("scripts", "build", "build/ars_pipeline", "validation"):
    sys.path.insert(0, os.path.join(REPO, p))
import ars_launcher as L                                         # noqa: E402
import ars_launcher_web as W                                     # noqa: E402
import companion_deck as CD                                      # noqa: E402
import rpe_env as R                                              # noqa: E402

ROW = {"client_id": "1441", "client_name": "FNB Alaska", "csm": "James Gilmore", "products": "ARS"}
ROSTER = [("1441", "FNB Alaska", "MM", ["ARS"]), ("1632", "WesBanco", None, ["ICS"])]
COMP_DECK = "1441-2026.10-COMP-FNB Alaska ARS Companion.pptx"
RPE_DECK = "1441-2026.10-ARS-FNB Alaska ARS Results.pptx"
TI_DECK = "1441-2026.10-TI-ARS-FNB Alaska Transaction Intelligence.pptx"


def levels(checks):
    return [l for l, _ in checks]


# ------------------------------------------------------------------ naming
def test_a_companion_deck_name_is_told_apart_from_program_and_ti_decks():
    assert L.is_companion_deck(COMP_DECK)
    assert L.is_companion_deck(Path("x") / COMP_DECK)
    assert not L.is_companion_deck(RPE_DECK) and not L.is_companion_deck(TI_DECK)
    assert not L.is_ti_deck(COMP_DECK)
    assert L.companion_deck_name("1441", "2026.10", "FNB Alaska") == COMP_DECK


def test_a_companion_deck_in_outputs_is_not_the_periods_rpe_deck(monkeypatch):
    monkeypatch.setattr(R, "output_decks", lambda pat: [Path("o") / COMP_DECK, Path("o") / RPE_DECK, Path("o") / TI_DECK])
    assert L.decks_in_outputs("1441", "2026.10") == [RPE_DECK]
    assert L.companion_decks_in_outputs("1441", "2026.10") == [COMP_DECK]
    assert L.ti_decks_in_outputs("1441", "2026.10") == [TI_DECK]


def test_an_rpe_build_never_archives_a_companion_deck(tmp_path, monkeypatch):
    out = tmp_path / "Outputs" / "James Gilmore"
    out.mkdir(parents=True)
    (out / COMP_DECK).write_bytes(b"comp")
    other = "1441-2026.10-ARS-ICS-FNB Alaska Results.pptx"
    (out / other).write_bytes(b"old mix")
    monkeypatch.setattr(R, "output_decks", lambda pat: [out / COMP_DECK, out / other])
    monkeypatch.setattr(R, "client_csm", lambda cid: "James Gilmore")
    new = tmp_path / RPE_DECK
    new.write_bytes(b"new")
    assert L.supersede_other_ars_decks("1441", str(new), tmp_path / "Outputs") == 1
    assert (out / COMP_DECK).is_file() and not (out / other).exists()


# ------------------------------------------------------------------ checks
def test_a_client_not_on_ars_stops():
    checks = L.companion_checks("1632", "2026.10", dict(ROW, client_id="1632", client_name="WesBanco"), ROSTER)
    assert L.STOP in levels(checks) and any("for ARS clients" in m for _, m in checks)


def test_an_unknown_client_stops():
    assert L.STOP in levels(L.companion_checks("1441", "2026.10", None, ROSTER))


def test_a_client_whose_product_list_has_no_ars_stops(monkeypatch):
    monkeypatch.setattr(L, "input_checks", lambda *a: [])
    monkeypatch.setattr(L, "lift_checks", lambda *a: [])
    checks = L.companion_checks("1441", "2026.10", dict(ROW, products="ICS"), ROSTER)
    assert L.STOP in levels(checks) and any("Not an ARS client" in m for _, m in checks)


def test_a_deck_already_in_outputs_asks_and_skips_the_slow_checks(monkeypatch):
    monkeypatch.setattr(L, "companion_decks_in_outputs", lambda cid, period: [COMP_DECK])
    called = []
    monkeypatch.setattr(L, "input_checks", lambda cid, period: called.append("input") or [])
    monkeypatch.setattr(L, "lift_checks", lambda cid, period, roster: called.append("lift") or [])
    assert L.ASK in levels(L.companion_checks("1441", "2026.10", ROW, ROSTER)) and called == []
    checks = L.companion_checks("1441", "2026.10", ROW, ROSTER, rebuild=True)
    assert L.ASK not in levels(checks) and called == ["input", "lift"]


def test_a_ready_client_reads_the_ars_inputs_and_the_lift_matrix(monkeypatch):
    monkeypatch.setattr(L, "companion_decks_in_outputs", lambda cid, period: [])
    monkeypatch.setattr(L, "input_checks", lambda cid, period: [(L.OK, "ODD extract: 2026.10")])
    monkeypatch.setattr(L, "lift_checks", lambda cid, period, roster: [(L.OK, "Lift Matrix: in its window")])
    checks = L.companion_checks("1441", "2026.10", ROW, ROSTER)
    assert levels(checks).count(L.STOP) == 0
    assert any("ODD extract" in m for _, m in checks) and any(m.startswith("Lift Matrix") for _, m in checks)


def test_the_launcher_takes_companion_on_status_and_build():
    assert L.main(["status", "12", "--companion"]) == 2
    assert L.main(["build", "12", "--companion"]) == 2


# ------------------------------------------------------------------ the cut
def test_the_keep_plan_takes_the_cover_the_views_and_the_closing_slides():
    slides = [(256, "Acme CU"), (257, "Agenda"), (258, "Reach"), (259, "Revenue Build by Mailing"),
              (260, "Spend per Card"), (261, "Questions & Discussion"), (262, "Contact Us"), (263, "Appendix: Codes")]
    assert CD.keep_plan(slides, [259, 260]) == [0, 3, 4, 5, 6]
    assert CD.keep_plan(slides, []) == [0, 5, 6]


def _deck(tmp_path, titles):
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    for i, t in enumerate(titles):
        sl = prs.slides.add_slide(prs.slide_layouts[6])
        tb = sl.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(1))
        if i == 0:
            tf = tb.text_frame
            tf.text = "Acme Credit Union"
            tf.add_paragraph().add_run().text = "Executive Review  •  October 2026"
        else:
            tb.text_frame.text = t
        sl.notes_slide.notes_text_frame.text = f"Source: test {t}"
    path = tmp_path / "full.pptx"
    prs.save(path)
    return path, [s.slide_id for s in Presentation(path).slides]


def test_the_cut_keeps_only_the_views_and_retitles_the_cover(tmp_path):
    from pptx import Presentation
    titles = ["cover", "Agenda", "Reach", "Revenue Build by Mailing", "Spend per Card", "Questions & Discussion",
              "Contact Us", "Appendix"]
    full, ids = _deck(tmp_path, titles)
    sj = tmp_path / "companion_slides.json"
    sj.write_text(json.dumps({"slide_ids": [ids[3], ids[4]], "titles": [titles[3], titles[4]]}), encoding="utf-8")
    out = tmp_path / "out" / COMP_DECK
    assert CD.build(str(full), str(sj), str(out)) == 2
    kept = Presentation(out)
    assert [CD.title_of(s) for s in kept.slides][1:] == ["Revenue Build by Mailing", "Spend per Card",
                                                         "Questions & Discussion", "Contact Us"]
    cover = " ".join(sh.text_frame.text for sh in kept.slides[0].shapes if sh.has_text_frame)
    assert "Executive Review Analysis" in cover and "ompanion" not in cover and "October 2026" in cover
    assert [s.notes_slide.notes_text_frame.text for s in kept.slides][1] == "Source: test Revenue Build by Mailing"
    import validate_deck as V
    assert V.package_findings(str(out)) == []                 # no part is referenced twice or left dangling
    assert V._cover_client_and_month(kept) == ("Acme Credit Union", "October 2026")


def test_a_build_that_recorded_no_views_is_not_a_deck(tmp_path):
    full, ids = _deck(tmp_path, ["cover", "Reach", "Questions & Discussion"])
    sj = tmp_path / "companion_slides.json"
    sj.write_text(json.dumps({"slide_ids": [], "titles": []}), encoding="utf-8")
    with pytest.raises(SystemExit):
        CD.build(str(full), str(sj), str(tmp_path / "o.pptx"))
    sj.write_text(json.dumps({"slide_ids": [999999], "titles": ["x"]}), encoding="utf-8")
    with pytest.raises(SystemExit):
        CD.build(str(full), str(sj), str(tmp_path / "o.pptx"))


def test_build_ars_gen_records_the_slides_the_views_added():
    src = Path(REPO, "build", "ars_pipeline", "build_ars_gen.py").read_text(encoding="utf-8")
    assert "_companion_base = {_s.slide_id for _s in prs.slides}" in src
    assert 'os.environ.get("RPE_COMPANION") == "1"' in src and "companion_slides.json" in src
    # the ids are taken BEFORE the first opt-in view goes in and the record is written AFTER the last
    assert src.index("_companion_base =") < src.index('if os.environ.get("RPE_JAMES_SLIDES") == "1":')
    assert src.index('if os.environ.get("RPE_SPEND_SLIDES") == "1":') < src.index('os.environ.get("RPE_COMPANION") == "1"')
    assert set(L.COMPANION_ENV) == {"RPE_JAMES_SLIDES", "RPE_SPEND_SLIDES", "RPE_COMPANION"}


def test_a_companion_deck_goes_to_outputs_and_supersedes_only_its_own_name(tmp_path, monkeypatch):
    out = tmp_path / "Outputs"
    dest = out / "James Gilmore"
    dest.mkdir(parents=True)
    (dest / COMP_DECK).write_bytes(b"old")
    (dest / RPE_DECK).write_bytes(b"rpe")
    monkeypatch.setattr(R, "outputs", lambda: out)
    monkeypatch.setattr(R, "client_outputs", lambda cid, root=None: dest)
    monkeypatch.setattr(R, "client_csm", lambda cid: "James Gilmore")
    import promote_month as P
    monkeypatch.setattr(P, "same", lambda a, b: Path(a).read_bytes() == Path(b).read_bytes())
    new = tmp_path / COMP_DECK
    new.write_bytes(b"new")
    lvl, msg = L.ti_to_outputs("1441", str(new), "FNB Alaska")
    assert lvl == L.OK and (dest / COMP_DECK).read_bytes() == b"new" and (dest / RPE_DECK).read_bytes() == b"rpe"


# ------------------------------------------------------------------ Sheila
def test_sheila_runs_the_launcher_with_companion_for_a_companion_build():
    assert W.build_cmd("1441", False, False, "2026.10", companion=True)[-1] == "--companion"
    assert "--companion" not in W.build_cmd("1441", False, False, "2026.10")
    assert "--companion" not in W.build_cmd("1441", False, False, "2026.10", ti=True)
    job = W.Job("1441", False, companion=True)
    assert job.to_json()["companion"] is True and job.to_json()["ti"] is False


def test_the_status_carries_the_companion_block_for_an_ars_client_only(monkeypatch):
    import build_month as BM
    import deck_status as DS
    monkeypatch.setattr(W, "current_period", lambda: "2026.10")
    monkeypatch.setattr(L, "csm_list_row", lambda cid: dict(ROW, client_id=cid))
    monkeypatch.setattr(BM, "read_roster", lambda *a, **k: (ROSTER, []))
    monkeypatch.setattr(DS, "read_deliveries", lambda: {"sent": {}})
    monkeypatch.setattr(L, "cp_roster_row", lambda cid: None)
    monkeypatch.setattr(L, "all_checks", lambda *a, **k: [(L.OK, "fine")])
    monkeypatch.setattr(L, "program_availability", lambda *a, **k: {})
    monkeypatch.setattr(L, "ti_status", lambda *a: {"checks": [], "state": "ready", "last": None, "decks": []})
    monkeypatch.setattr(L, "companion_status", lambda cid, period, row, roster, sent: {
        "checks": [{"level": L.OK, "text": "fine"}], "state": "ready", "last": None, "decks": []})
    doc = W.compute_status("1441")
    assert doc["companion"]["state"] == "ready"
    assert W.compute_status("1632")["companion"] is None
    monkeypatch.setattr(L, "companion_status", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    doc = W.compute_status("1441")
    assert doc["state"] == "ready" and doc["companion"]["state"] == "stop" and "boom" in doc["companion"]["checks"][0]["text"]


def test_the_list_keeps_companion_decks_apart(tmp_path, monkeypatch):
    import build_month as BM
    import deck_status as DS
    monkeypatch.setattr(W, "current_period", lambda: "2026.10")
    monkeypatch.setattr(BM, "read_roster", lambda *a, **k: (ROSTER[:1], []))
    monkeypatch.setattr(BM, "read_cashplease_roster", lambda: [], raising=False)
    monkeypatch.setattr(DS, "read_deliveries", lambda: {"sent": {}})
    monkeypatch.setattr(R, "csm_list_file", lambda: None)
    monkeypatch.setattr(R, "output_decks", lambda pat: [Path("o") / COMP_DECK, Path("o") / TI_DECK])
    monkeypatch.setattr(W, "launcher_results", lambda period, cids: {})
    monkeypatch.setattr(W, "last_build_failed", lambda *a, **k: False)
    monkeypatch.setattr(W, "available_periods", lambda n=12: ["2026.10"])
    c = W.compute_clients()["clients"][0]
    assert c["decks"] == [] and c["ti_decks"] == [TI_DECK] and c["companion_decks"] == [COMP_DECK]


def test_the_page_has_a_companion_panel_button_and_job_box():
    page = W.PAGE
    assert "function companionPanel(s)" in page and "async function buildComp(s)" in page
    assert 'id="gocomp"' in page and 'id="jobcomp"' in page
    assert '"/api/build"' in page and "companion: true" in page
    assert "${tiPanel(s)}${companionPanel(s)}" in page
    # one build per client at a time: every button waits while any of them runs
    assert '["#go", "#go2", "#goti", "#gocomp"]' in page
    assert "Companion in Outputs" in page


def test_the_closing_slides_end_the_deck_even_when_a_view_follows_them_in_the_build(tmp_path):
    from pptx import Presentation
    titles = ["cover", "Reach", "Questions & Discussion", "Contact Us", "Appendix View"]
    full, ids = _deck(tmp_path, titles)
    sj = tmp_path / "companion_slides.json"
    sj.write_text(json.dumps({"slide_ids": [ids[1], ids[4]], "titles": [titles[1], titles[4]]}), encoding="utf-8")
    out = tmp_path / "o.pptx"
    CD.build(str(full), str(sj), str(out))
    assert [CD.title_of(s) for s in Presentation(out).slides][1:] == ["Reach", "Appendix View",
                                                                      "Questions & Discussion", "Contact Us"]


def test_the_companion_build_hands_its_flags_to_the_child_environment(tmp_path, monkeypatch):
    """build_month copies os.environ when it is imported, so the build process only ever sees what is put in
    _CHILD_ENV. The flags were set on os.environ instead, the views were never added, and the build died looking
    for companion_slides.json (Austin Bank, 2026-10-28)."""
    import argparse
    import build_month as BM
    monkeypatch.setattr(BM, "_CHILD_ENV", {"PYTHONIOENCODING": "utf-8"})
    seen = {}
    monkeypatch.setattr(BM, "build_client", lambda *a, **k: seen.update(BM._CHILD_ENV) or ("stub", {}))
    monkeypatch.setattr(L, "companion_checks", lambda *a, **k: [(L.OK, "fine")])
    work = tmp_path / "w"
    work.mkdir()
    a = argparse.Namespace(client="1441", rebuild=False)
    assert L.build_companion(a, BM, ROW, "2026.10", ROSTER, {}, work) == 1
    assert all(seen.get(k) == v for k, v in L.COMPANION_ENV.items())
