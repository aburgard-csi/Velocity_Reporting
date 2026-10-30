"""The Campaign chapter (build/ars_pipeline/ti/chapters/campaign.py, ti/deck/campaign_inline.py).

v5's campaign blocks, lifted from its build function with their closures bound to the cut's helper
bundle: every slide is drawn or stated, in v5's order; v5's `skip` becomes a stated slide; RPE's
house words replace "lift" without touching a figure; and the per-offer table keeps its note clear
of the KPI row however many offers there are. These replace v5's whole-deck tests for the chapter.
"""
import pytest
from pptx import Presentation

from ti.chapters import campaign as C


@pytest.fixture(autouse=True)
def _keep_every_slide(tmp_path, monkeypatch):
    """These test the builders. Which slides ship is ti/slides.json's business (test_ti_selection):
    Sheila's 1798 review (2026-10-30) tosses several of these slides there (the hero, Per-offer
    summary, Revenue frames, The most recent mailer), and a toss must not read as a builder failing."""
    monkeypatch.setenv("TI_SLIDES", str(tmp_path / "keep-all.json"))


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


def test_the_hero_shows_guarantee_math_while_a_balance_is_live(tmp_path, monkeypatch):
    """v5's hero (James, 2026-08-22): earned over fees paid while a 2:1 balance is deferred, the
    workbook's profit otherwise; and Revenue frames sets the booked frame beside the estimate."""
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    base = {"campaign_rates": [["Jun26", 18000, 1600, 8.9], ["Aug26", 18379, 1607, 8.7]],
            "responses_total": 13461, "reach_total": 12911, "ba_lift_net": 552.0,
            "wb_profit_ltd": 408971, "wb_revenue_ltd": 1121691, "wb_costs_ltd": -712720,
            "wb_found": "1776-2026.10-CoastHills CU-Workbook_v2_1_0.xlsx", "segment_ic_rate": 0.0062}
    live = {**base, "gt_deferred_balance": 140861.51, "gt_state": "drawing-down",
            "gt_revenue_ltd": 900000.0, "gt_paid_ltd": 339000.0}
    slides = C.build(_Ctx(_prs(), live, tmp_path))
    texts = [_text(s) for s in slides]
    hero = next(t for t in texts if "earned over fees paid" in t)
    assert "$561K" in hero
    assert any("BOOKED: ARS WORKBOOK LEDGER" in t and "Gain per responder" in t for t in texts), \
        "Revenue frames draws both frames, in the house word"
    cleared = {**live, "gt_state": "clear", "gt_deferred_balance": 0.0}
    texts = [_text(s) for s in C.build(_Ctx(_prs(), cleared, tmp_path))]
    assert any("program profit, life to date" in t and "$409K" in t for t in texts)


def test_the_latest_mailer_chart_starts_below_a_two_line_headline(tmp_path, monkeypatch):
    """1798 FirstLight, 2026-10-29, slide 127: a headline long enough to wrap pushed the subtitle down,
    and the chart, placed at v5's fixed 1.55in, covered it."""
    from test_ti_mailer_summary_chart import SUMMARY
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    m = {"mailer_summary": {"Aug26": {**SUMMARY, "mailed": 22914, "responded": 2226, "rate": 9.7}}}
    slides = C.build(_Ctx(_prs(), m, tmp_path))
    s = next(s for s in slides if "Aug26 reached 22,914 accounts" in _text(s))
    sub = next(sh for sh in s.shapes if sh.has_text_frame and "challenge tier" in sh.text_frame.text)
    pic = next(sh for sh in s.shapes if sh.shape_type == 13)
    assert pic.top >= sub.top + sub.height, "the chart starts below the subtitle"
    assert pic.top + pic.height <= 6.95 * 914400, "and still ends above the footer"
