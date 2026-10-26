"""The ICS accounts chapter (build/ars_pipeline/ti/chapters/ics.py) and the compact KPI card.

v5's ICS chapter returns the slides it skipped as "<title> (<reason>)" and leaves one out without a
word (ICS channel with no channel rows); here every slide is drawn or stated, in v5's order. A KPI
card placed low is drawn compact above the content floor instead of running to 7.15in.
"""
from pptx import Presentation
from pptx.util import Emu, Inches

from ti.chapters import ics as C
from ti.deck import helpers as H


class _Ctx:
    def __init__(self, prs, metrics, tmp):
        self.prs, self.pack = prs, {"client_id": "9999", "client_name": "Test Bank",
                                    "sources": {"odd": "9999-ODD.csv"}, "metrics": metrics}
        self.lens = type("L", (), {"label": "ARS lens"})()
        self.pill, self.art_dir = "September 2026 Data", str(tmp)


def _prs():
    return Presentation(__import__("os").path.join(__import__("os").path.dirname(__file__), "..",
                                                   "templates", "ars_template.pptx"))


def _titles(slides):
    out = []
    for s in slides:
        t = [sh.text_frame.text for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip()]
        out.append(t[0] if t else "")
    return out


def test_no_ics_accounts_is_one_stated_slide(tmp_path, monkeypatch):
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    slides = C.build(_Ctx(_prs(), {}, tmp_path))
    assert _titles(slides) == ["ICS accounts"]


def test_every_skip_and_silent_omission_is_stated_in_v5_order(tmp_path, monkeypatch):
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    from ti.deck import ics_slides

    def fake_add_chapter(prs, h, m, charts_dir, txn=None):
        h["slide"](("ICS has opened 10 accounts", None), "ICS acquisition")
        h["slide"](("ICS keeps 90%", None), "ICS retention")
        return ["ICS personas (cohort too thin to classify)", "ICS cohorts (no milestone rows)"]

    monkeypatch.setattr(ics_slides, "add_chapter", fake_add_chapter)
    slides = C.build(_Ctx(_prs(), {"ics_cmp_bases": {"ics": 10, "non": 90}}, tmp_path))
    topics = _titles(slides)
    assert len(slides) == len(C.ORDER), "every ICS slide is drawn or stated"
    assert topics[0] == "ICS has opened 10 accounts" and topics[3] == "ICS cohorts"
    assert "ICS activation personas" in topics and "ICS channel" in topics


def test_a_low_kpi_card_is_drawn_compact_above_the_floor():
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    H._kpi(s, 0.7, 5.5, 3.7, "Carries a debit card", "63%", "vs 54% non-ICS")
    card = s.shapes[0]
    assert Emu(card.top + card.height).inches <= H.CONTENT_FLOOR + 0.001
    H._kpi(s, 0.7, 2.0, 3.7, "Label", "1", "note")
    assert abs(Emu(s.shapes[4].height).inches - H.KPI_H) < 0.001, "a card with room is unchanged"


def test_a_compact_kpi_cards_value_never_runs_into_its_wrapped_note():
    """1776's ICS quality slide, 2026-10-23: the value box gave up height to a three-line note,
    and the 28pt value then spilled out of its box onto the note. The value is sized to its box."""
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "validation"))
    import validate_deck as vd
    tw = (H.CONTENT_W - 0.4) / 3
    for top in (4.6, 4.9, 5.1, 5.3, 5.5, 5.6):
        prs = Presentation()
        s = prs.slides.add_slide(prs.slide_layouts[6])
        H._kpi(s, 0.7, top, tw, "Carries a debit card", "75%",
               "vs 72% non-ICS · the card has to exist first")
        assert vd.text_collision_findings(prs) == [], top
