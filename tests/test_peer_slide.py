"""The "How You Compare" deck slide: what it draws, where it goes, what it must never carry, and the gate behind it."""
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

PEER_IDS = [str(1700 + i) for i in range(1, 12)]
SPECS = {"resp_12m": {"key": "resp_12m", "label": "Mailing response rate, last 12 months", "fmt": "pct1", "higher": True, "month": False},
         "spend_gain": {"key": "spend_gain", "label": "Responder debit spend, change after a mailing", "fmt": "pct0", "higher": True, "month": False}}


def evaluation(n_peers=11, with_ids=True):
    peers = [{"id": PEER_IDS[i], "point": {"resp_12m": 6.0 + i, "spend_gain": 60.0 + 3 * i}, "series": {}} for i in range(n_peers)]
    coll = {"n_pool": n_peers, "me": {"point": {"resp_12m": 12.5, "spend_gain": 80.0}, "series": {}}, "peers": peers, "pull": "2026-10-01"}
    ev = PC.evaluate(coll, list(SPECS.values()), "ARS")
    ev["items"] = [PC.anonymous(i) for i in ev["items"]]
    ev.update(program="ARS", who="ARS", pull="2026-10-01")
    return ev


def deck():
    return Presentation(os.path.join(REPO, "templates", "ars_template.pptx"))


def add(prs, tmp_path, ev=None, **kw):
    return PS.add_peer_slide(prs, "ARS", "9999", "Union Test Bank", "Sep 2026 Data", str(tmp_path),
                             "Client figures: ODD extract 9999 Union Test Bank; ARS workbook 9999.", before_title="ARS Key Takeaways",
                             evaluation=ev or evaluation(), **kw)


def face(slide):
    return " ".join(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame)


def test_the_slide_is_placed_by_title_and_drawn(tmp_path):
    prs = deck()
    s = add(prs, tmp_path)
    titles = [SH.slide_title(x) for x in prs.slides]
    i = titles.index(PS.title_for("ARS"))
    assert titles[i + 1].startswith("ARS Key Takeaways") and PS.title_for("ARS") == "How You Compare — ARS Clients"
    assert any(sh.shape_type == 13 for sh in s.shapes), "the strip plot is a picture"
    text = face(s)
    assert "5th of 12 ARS clients" in text
    assert "Union Test Bank" in text and "none named" in text


def test_no_client_number_or_name_reaches_the_face_or_the_notes(tmp_path):
    s = add(deck(), tmp_path)
    notes = s.notes_slide.notes_text_frame.text
    for pid in PEER_IDS:
        assert pid not in face(s) and pid not in notes


def test_notes_carry_a_source_line_naming_the_client(tmp_path):
    notes = add(deck(), tmp_path).notes_slide.notes_text_frame.text
    assert notes.startswith("Source: peer comparison for client 9999 Union Test Bank")
    assert "ODD extract 9999" in notes and "CoastLife" not in notes and "1705" not in notes
    assert "Mailing response rate, last 12 months:" in notes and "middle half" in notes


def test_too_few_peers_is_stated_not_drawn(tmp_path):
    ev = {"program": "ARS", "who": "ARS", "n_pool": 3, "pull": None, "items": [], "left": [], "notes": [],
          "unavailable": "A comparison needs at least 5 other clients on ARS; this book has 3. Nothing is shown rather than a comparison a reader could trace to one client."}
    prs = deck()
    s = add(prs, tmp_path, ev=ev)
    assert "at least 5 other clients on ARS" in face(s) and not any(sh.shape_type == 13 for sh in s.shapes)
    assert vd.peer_slide_findings(prs) == []


def test_an_unreadable_peer_pool_is_stated_and_fails_the_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(PS, "_evaluate", lambda *a, **k: (_ for _ in ()).throw(OSError("the share is not reachable")))
    prs = deck()
    s = PS.add_peer_slide(prs, "ARS", "9999", "Union Test Bank", "Sep 2026 Data", str(tmp_path), "Client figures: x.", before_title="ARS Key Takeaways")
    assert "could not be drawn" in face(s)
    out = vd.peer_slide_findings(prs)
    assert [f[0] for f in out] == ["FAIL"] and "could not be drawn" in out[0][2]


def test_the_gate_fails_a_peer_slide_that_names_a_client(tmp_path):
    prs = deck()
    s = add(prs, tmp_path)
    assert vd.peer_slide_findings(prs) == []
    s.notes_slide.notes_text_frame.text += " Peer client 1705 had no data."
    assert any("client 1705" in f[2] for f in vd.peer_slide_findings(prs))
    s.notes_slide.notes_text_frame.text = s.notes_slide.notes_text_frame.text.replace(" Peer client 1705 had no data.", "")
    assert vd.peer_slide_findings(prs) == []


def test_every_programs_metrics_exist_in_the_shared_lists():
    from review_page import peer_pool
    for prog, keys in PS.METRICS.items():
        have = {m["key"] for m in peer_pool.PROGRAMS[prog][1]}
        assert set(keys) <= have, (prog, set(keys) - have)
        assert PS.WHO[prog] == peer_pool.PROGRAMS[prog][2]
    for prog, keys in PS.METRICS.items():
        for k in keys:
            assert PS._def(prog, k), (prog, k)


def test_the_strip_plot_renders_every_row(tmp_path):
    ev = evaluation()
    out = PS.render_strips(ev["items"], str(tmp_path / "s.png"), 7.75, 4.0)
    from PIL import Image
    with Image.open(out) as im:
        assert im.size == (int(7.75 * 200), int(4.0 * 200))
