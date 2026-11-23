"""The "How You Compare" deck slides: what they draw, where they go, what they must never carry, and the gate behind them.

Since 2026-11-22 (Aaron): never more than two comparisons a slide ("Don't put more than 2 peer comparison charts on a
slide"), a slide with no data is not added ("skip a slide if it doesn't have data"), and ARS is compared only on what the
client controls ("don't compare program results").
"""
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "build"), os.path.join(REPO, "validation"), os.path.join(REPO, "scripts")]

from pptx import Presentation                                    # noqa: E402

import peer_compare as PC                                        # noqa: E402
import peer_slide as PS                                          # noqa: E402
import shapes as SH                                              # noqa: E402
import validate_deck as vd                                       # noqa: E402
from review_page import peer_pool as PP                          # noqa: E402

PEER_IDS = [str(1700 + i) for i in range(1, 12)]
SPEC = {m["key"]: m for m in PP.ARS_METRICS}
# Reg E (both measures) and the whole-book take rate have peers; new-account take rate, growth and retention do not.
HAVE = ("rege_pct", "rege_new_pct", "take_all")


def evaluation(n_peers=11, have=HAVE):
    peers = [{"id": PEER_IDS[i], "point": {k: 40.0 + i + j for j, k in enumerate(have)}, "series": {}} for i in range(n_peers)]
    coll = {"n_pool": n_peers, "me": {"point": {k: 45.5 for k in have}, "series": {}}, "peers": peers, "pull": "2026-10-01"}
    ev = PC.evaluate(coll, [SPEC[k] for k in PS.METRICS["ARS"]], "ARS")
    ev["items"] = [PC.anonymous(i) for i in ev["items"]]
    ev.update(program="ARS", who="ARS", pull="2026-10-01")
    return ev


def deck():
    return Presentation(os.path.join(REPO, "templates", "ars_template.pptx"))


def add(prs, tmp_path, ev=None, **kw):
    return PS.add_peer_slide(prs, "ARS", "9999", "Union Test Bank", "Sep 2026 Data", str(tmp_path),
                             "Client figures: ODD extract 9999 Union Test Bank; ARS workbook 9999.", before_title="ARS Key Takeaways",
                             evaluation=ev or evaluation(), log=lambda m: None, **kw)


def face(slide):
    return " ".join(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame)


def pictures(slide):
    return [sh for sh in slide.shapes if sh.shape_type == 13]


def test_one_slide_per_pair_in_order_before_the_takeaways(tmp_path):
    prs = deck()
    made = add(prs, tmp_path)
    titles = [SH.slide_title(x) for x in prs.slides]
    want = [PS.title_for("ARS", "Reg E Opt-In"), PS.title_for("ARS", "Debit Card Take Rate")]
    assert [SH.slide_title(s) for s in made] == want
    i = titles.index(want[0])
    assert titles[i:i + 2] == want and titles[i + 2].startswith("ARS Key Takeaways")
    assert want[0] == "How You Compare — Reg E Opt-In"
    for s in made:
        assert len(pictures(s)) == 1, "the strip plot is one picture"
        assert "Union Test Bank" in face(s) and "none named" in face(s)
    assert face(made[0]).count("of 12 ARS clients") == 2             # two ranks: Reg E, both measures
    assert face(made[1]).count("of 12 ARS clients") == 1             # the new-account take rate has no peers


def test_never_more_than_two_comparisons_a_slide():
    for program, groups in PS.GROUPS.items():
        for label, keys in groups:
            assert 1 <= len(keys) <= PS.MAX_PER_SLIDE == 2, (program, label)
        flat = [k for _l, ks in groups for k in ks]
        assert len(flat) == len(set(flat)) and flat == PS.METRICS[program]


def test_every_title_fits_on_one_line():
    import textfit
    for program, groups in PS.GROUPS.items():
        for label, _keys in groups + [(None, [])]:
            t = PS.title_for(program, label)
            assert textfit.fits_one_line(t, 9.4, 26, bold=True), t


def test_a_pair_with_no_data_adds_no_slide_and_the_drawn_slides_say_so(tmp_path):
    made = add(deck(), tmp_path)
    skipped = PS.title_for("ARS", "Accounts Gained & Kept")
    assert skipped not in [SH.slide_title(s) for s in made]
    for s in made:
        assert skipped in s.notes_slide.notes_text_frame.text


def test_too_few_peers_adds_no_slide(tmp_path):
    ev = {"program": "ARS", "who": "ARS", "n_pool": 3, "pull": None, "items": [], "left": [], "notes": [],
          "unavailable": "A comparison needs at least 5 other clients on ARS; this book has 3."}
    prs = deck()
    n = len(prs.slides)
    seen = []
    assert PS.add_peer_slide(prs, "ARS", "9999", "Union Test Bank", "Sep 2026 Data", str(tmp_path), "Client figures: x.",
                             before_title="ARS Key Takeaways", evaluation=ev, log=seen.append) == []
    assert len(prs.slides) == n and vd.peer_slide_findings(prs) == []
    assert any("none added" in m for m in seen)                       # said in the build log, never silent


def test_no_client_number_or_name_reaches_the_face_or_the_notes(tmp_path):
    for s in add(deck(), tmp_path):
        notes = s.notes_slide.notes_text_frame.text
        for pid in PEER_IDS:
            assert pid not in face(s) and pid not in notes


def test_notes_carry_a_source_line_naming_the_client(tmp_path):
    first = add(deck(), tmp_path)[0]
    notes = first.notes_slide.notes_text_frame.text
    assert notes.startswith("Source: peer comparison for client 9999 Union Test Bank")
    assert "ODD extract 9999" in notes and "CoastLife" not in notes and "1705" not in notes
    assert "Reg E opt-in, open personal accounts:" in notes and "middle half" in notes


def test_an_unreadable_peer_pool_is_stated_and_fails_the_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(PS, "_evaluate", lambda *a, **k: (_ for _ in ()).throw(OSError("the share is not reachable")))
    prs = deck()
    made = PS.add_peer_slide(prs, "ARS", "9999", "Union Test Bank", "Sep 2026 Data", str(tmp_path), "Client figures: x.",
                             before_title="ARS Key Takeaways", log=lambda m: None)
    assert len(made) == 1 and "could not be drawn" in face(made[0])
    out = vd.peer_slide_findings(prs)
    assert [f[0] for f in out] == ["FAIL"] and "could not be drawn" in out[0][2]


def test_the_gate_fails_a_peer_slide_that_names_a_client(tmp_path):
    prs = deck()
    s = add(prs, tmp_path)[0]
    assert vd.peer_slide_findings(prs) == []
    s.notes_slide.notes_text_frame.text += " Peer client 1705 had no data."
    assert any("client 1705" in f[2] for f in vd.peer_slide_findings(prs))
    s.notes_slide.notes_text_frame.text = s.notes_slide.notes_text_frame.text.replace(" Peer client 1705 had no data.", "")
    assert vd.peer_slide_findings(prs) == []


def test_ars_compares_only_what_the_client_controls():
    """Aaron, 2026-11-22: "For ARS peer comparisons, don't compare program results. Compare things the customer controls,
    like Reg E, account growth, debit card take rate." Live Review, the decks and the peer reference all read this list."""
    keys = {m["key"] for m in PP.ARS_METRICS}
    assert not keys & set(PP.ARS_PROGRAM_RESULTS)
    assert {"rege_pct", "take_all", "take_new_pct", "acct_growth"} <= keys
    assert set(PS.METRICS["ARS"]) <= keys
    sys.path.insert(0, REPO)
    from sheila_mcp import reports as SR
    fields = {f for _l, f, _h in SR.KPIS.values()}
    assert not fields & {"latest_resprate", "depth_repeat_pct", "new_active_pct", "book_active_pct"}


def test_every_programs_metrics_exist_in_the_shared_lists():
    for prog, keys in PS.METRICS.items():
        have = {m["key"] for m in PP.PROGRAMS[prog][1]}
        assert set(keys) <= have, (prog, set(keys) - have)
        assert PS.WHO[prog] == PP.PROGRAMS[prog][2]
    for prog, keys in PS.METRICS.items():
        for k in keys:
            assert PS._def(prog, k), (prog, k)


def test_the_strip_plot_renders_every_row(tmp_path):
    ev = evaluation()
    out = PS.render_strips(ev["items"][:2], str(tmp_path / "s.png"), 7.75, 3.0)
    from PIL import Image
    with Image.open(out) as im:
        assert im.size == (int(7.75 * 200), int(3.0 * 200))
