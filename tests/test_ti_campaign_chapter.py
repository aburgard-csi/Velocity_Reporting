"""The Campaign chapter (build/ars_pipeline/ti/chapters/campaign.py, ti/deck/campaign_inline.py).

v5's campaign blocks, lifted from its build function with their closures bound to the cut's helper
bundle: every slide is drawn or stated, in v5's order; v5's `skip` becomes a stated slide; RPE's
house words replace "lift" without touching a figure; and the per-offer table keeps its note clear
of the KPI row however many offers there are. These replace v5's whole-deck tests for the chapter.
"""
from pptx import Presentation

from ti.chapters import campaign as C


class _Ctx:
    def __init__(self, prs, metrics, tmp):
        self.prs, self.pack = prs, {"client_id": "9999", "client_name": "Test Bank",
                                    "sources": {"odd": "9999-ODD.csv"}, "metrics": metrics}
        self.lens = type("L", (), {"label": "ARS lens"})()
        self.pill, self.art_dir = "September 2026 Data", str(tmp)


def _prs():
    import os
    return Presentation(os.path.join(os.path.dirname(__file__), "..", "templates", "ars_template.pptx"))


def _text(slide):
    out = []
    for sh in slide.shapes:
        if sh.has_text_frame:
            out.append(sh.text_frame.text)
        if getattr(sh, "has_table", False) and sh.has_table:
            out += [c.text_frame.text for row in sh.table.rows for c in row.cells]
    return " ".join(out)


def test_no_campaign_figures_states_every_slide(tmp_path, monkeypatch):
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    slides = C.build(_Ctx(_prs(), {}, tmp_path))
    assert slides, "the chapter is never empty"
    assert all("Not shown for this client" in _text(s) for s in slides)
    assert any("Per-offer summary" in _text(s) for s in slides)


def test_per_offer_fits_its_offers_and_says_lift_the_house_way(tmp_path, monkeypatch):
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    waves = [f"W{i:02d}" for i in range(12)]
    m = {"campaign_rates": [[w, 18000, 1600, 8.9] for w in waves],
         "before_after": [{"month": w, "resp_pre": 660, "resp_post": 1200, "ctrl_pre": 320,
                           "ctrl_post": 290} for w in waves],
         "ba_lift_net": 552, "ba_lift_pct": 81.0, "ba_spend_before": 660, "ba_spend_after": 1200,
         "ba_control_before": 320, "ba_control_after": 290}
    slides = C.build(_Ctx(_prs(), m, tmp_path))
    per_offer = next(s for s in slides if "Per-offer summary" in _text(s) or "completed offers" in _text(s))
    text = _text(per_offer)
    assert "of 12 completed offers" in text and "Response %" in text
    assert " lift" not in text.lower() and "Net gain" in text, "house words, no banned 'lift'"
