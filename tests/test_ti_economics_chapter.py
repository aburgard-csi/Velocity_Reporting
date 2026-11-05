"""The Economics chapter (build/ars_pipeline/ti/chapters/economics.py, ti/deck/economics_inline.py).

v5's five economics slides, lifted from its build function: every slide is drawn or stated, in v5's
order; the P&L tiles switch to the guarantee's math only while a deferred balance is live, and a
cleared guarantee reverts them to the workbook's billed figures (James, 2026-08-22); a guarantee
status wider than its tile steps down in size instead of wrapping; and a client with no workbook
or tracker gets each slide stated. These replace v5's deck-harness tests for the same slides.
"""
import pytest
from pptx import Presentation

from ti.chapters import economics as C


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
    return " ".join(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame)


WB = {"wb_source": "9999-2026.09-Test Bank-Workbook_v2_1_0.xlsx", "wb_found": "9999-2026.09-Test Bank-Workbook_v2_1_0.xlsx",
      "wb_profit_ltd": 687635, "wb_revenue_ltd": 989840, "wb_costs_ltd": -302204,
      "wb_profit_month": 31630, "wb_revenue_month": 40729,
      "wb_waves": [[f"W{i}", 5000 + i, 3.0, 2900 + i, 170] for i in range(12)],
      "wb_wave_revenue": [["Jan26", {"Jan26": 100.0}], ["Feb26", {"Jan26": 80.0, "Feb26": 120.0}]]}
GT = {"gt_source": "9999 Test Bank Deferred expense tracking.xlsx", "gt_latest_month": "2026-08",
      "gt_months": [["2026-07", 80000.0, 36000.0, 36000.0, 0.0, 140861.51],
                    ["2026-08", 81000.0, 36000.0, 36000.0, 0.0, 140861.51]],
      "gt_revenue_ltd": 500000.0, "gt_charges_ltd": 480000.0, "gt_paid_ltd": 300000.0,
      "gt_deferred_balance": 140861.51, "gt_ratio_latest": 2.25, "gt_state": "drawing-down"}


def test_no_workbook_or_tracker_states_every_slide_in_order(tmp_path, monkeypatch):
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    slides = C.build(_Ctx(_prs(), {}, tmp_path))
    assert len(slides) == len(C.TITLES)
    for s, title in zip(slides, C.TITLES.values()):
        assert title in _text(s) and "Not shown for this client" in _text(s)


def test_a_live_balance_puts_the_pnl_on_guarantee_math(tmp_path, monkeypatch):
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    slides = C.build(_Ctx(_prs(), {**WB, **GT}, tmp_path))
    pnl, guar = _text(slides[0]), _text(slides[1])
    assert "Earned over fees paid" in pnl and "Program profit" not in pnl
    assert "Latest" in pnl and "of 12 offers shown" in pnl, "a long offer list is said in the footer"
    assert "Deferred balance" in guar and "Drawing Down" in guar


def test_a_cleared_guarantee_reverts_the_pnl_to_the_workbook(tmp_path, monkeypatch):
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    cleared = {**GT, "gt_deferred_balance": 0.0, "gt_state": "clear"}
    slides = C.build(_Ctx(_prs(), {**WB, **cleared}, tmp_path))
    assert "Program profit" in _text(slides[0]) and "Earned over fees paid" not in _text(slides[0])
    assert "Clear" in _text(slides[1]), "the guarantee slide still shows the history"


def test_a_wide_status_steps_down_instead_of_wrapping():
    from textfit import text_width_in
    from ti.deck import economics_inline as E
    from ti.deck.helpers import HEAD_FONT
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    texts = []
    h = {"NAVY": E.GREEN_D, "GREY": E.RED_D,
         "text": lambda *a, **k: texts.append((a[5], k.get("size")))}
    E._tile(h, s, 0.6, 2.0, 2.61, "Drawing Down", "Status", "through 2026-09")
    value, size = texts[0]
    assert size < 26 and text_width_in(value, size, HEAD_FONT, True) <= 2.61 - 0.2
