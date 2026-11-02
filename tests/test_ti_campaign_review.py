"""Sheila's 1798 FirstLight slide review (2026-10-30), Campaign and Economics: the defects that slipped
past the gate, pinned so they cannot come back.

* v5's "Jun24" month labels failed the month-axis guard, the chart was refused and the slide shipped
  blank (slides 105, 108, 111 and the hero sparkline): every month chart here renders.
* "IC rate 0.0068" (slide 109) is a percent.
* the hero's KPI icons read as empty placeholders on the coloured cards (slide 107): none drawn.
* the twelve per-mailer summary slides (131-142) are one appendix table, a row per mailer.
* the combine groups: K (reach funnel with the latest offer), L (both gain figures on one chart,
  each with its window), M (one economics slide, booked against DiD as a two-column table),
  N (the tier matrix as a shaded table, responders against the unmailed).
* no footnote under 10.5pt on either chapter.
"""
import os

import pytest
from pptx import Presentation
from pptx.util import Emu

from ti.chapters import campaign as C, economics as E
from ti.deck import campaign_inline as CI, economics_inline as EI
from ti.deck.helpers import Deck


@pytest.fixture(autouse=True)
def _keep_every_slide(tmp_path, monkeypatch):
    # these test the builders; which slides ship is ti/slides.json's business (test_ti_selection)
    monkeypatch.setenv("TI_SLIDES", str(tmp_path / "keep-all.json"))
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))


class _Ctx:
    def __init__(self, prs, metrics, tmp):
        self.prs, self.pack = prs, {"client_id": "9999", "client_name": "Test Bank",
                                    "sources": {"odd": "9999-ODD.csv"}, "metrics": metrics}
        self.lens = type("L", (), {"label": "ARS lens"})()
        self.pill, self.art_dir = "September 2026 Data", str(tmp)


def _prs():
    return Presentation(os.path.join(os.path.dirname(__file__), "..", "templates", "ars_template.pptx"))


def _text(slide):
    out = []
    for sh in slide.shapes:
        if sh.has_text_frame:
            out.append(sh.text_frame.text)
        if getattr(sh, "has_table", False) and sh.has_table:
            out += [c.text_frame.text for row in sh.table.rows for c in row.cells]
    return " ".join(out)


def _run(mod, chapter, m, tmp):
    d = Deck(_Ctx(_prs(), m, tmp), "test", tmp / "charts")
    d.run([getattr(mod, n) for n in chapter.TITLES], chapter.TITLES, m)
    return d, {d.topics[id(s)]: s for s in d.slides}


WAVES = ["Jun24", "Aug24", "Oct24", "Dec24", "Feb25", "Apr25"]
M = {
    "campaign_rates": [[w, 20000, 2000 + i, 10.0 + i / 10] for i, w in enumerate(WAVES)],
    "reach_cumulative": [[w, 2000 * (i + 1), 2.0 * (i + 1)] for i, w in enumerate(WAVES)],
    "latest_mailing": "Apr25", "latest_resprate": 10.5, "resprate_mean": 10.25,
    "n_eligible": 89273, "n_ever_mailed": 42806, "reach_total": 22191, "reach": 24.9,
    "reach_of_mailed": 51.8, "responses_total": 34598,
    "ladder_by_wave": [{"wave": w, "first_time": 900, "repeat": 300} for w in WAVES],
    "ladder_movement": [["Up", 3855], ["Same", 3113], ["Down", 2440]],
    "counterfactual_actual": [[w, 1000.0 + i] for i, w in enumerate(WAVES)],
    "counterfactual_without": [[w, 900.0] for w in WAVES],
    "counterfactual_gap_total": 95082855,
    "ba_lift_net": 524, "ba_spend_before": 604, "ba_spend_after": 1099,
    "ba_control_before": 308, "ba_control_after": 279,
    "segment_ic_rate": 0.0068,
    "segment_summary": [{"segment": "TH-25", "did": 464, "did_per_1000_mailed": 121000,
                         "offered_n": 24350, "response_rate": 26.0, "resp_delta": 329,
                         "non_delta": -135, "did_from_control_pct": 29},
                        {"segment": "NU", "did": 454, "did_per_1000_mailed": 15000,
                         "offered_n": 118961, "response_rate": 3.4, "resp_delta": 440,
                         "non_delta": -14, "did_from_control_pct": 3}],
    "cohort_offsets": list(range(-3, 13)),
    "cohort_indexed": {"responders": [100.0] * 16, "mailed_nonresp": [100.0] * 16},
    "cohort_spend": {"responders": [600.0] * 3 + [1000.0] * 13,
                     "mailed_nonresp": [300.0] * 16},
    "cohort_lift": [{"horizon_months": 1, "diff_in_diff": 686.09},
                    {"horizon_months": 12, "diff_in_diff": 371.2}],
    "sustained_months_above": 12,
    "wb_profit_ltd": 1906679, "wb_revenue_ltd": 3310821, "wb_costs_ltd": -1404142,
    "wb_waves": [[w, 20000, 10.0, 300000 - i * 1000, 2000] for i, w in enumerate(WAVES)],
    "mig_tiers": ["Non-user", "1-5", "6+"],
    "mig_matrix": [[500, 40, 10], [60, 300, 50], [5, 40, 400]],
    "mig_up_pct": 25.1, "mig_down_pct": 19.8, "mig_same_pct": 55.2,
    "mig_by_group": [["Responder", 20369, 41.0, 30.0, 29.0, 0.46],
                     ["Mailed non-responder", 15648, 14.6, 65.4, 20.0, -0.19],
                     ["Not mailed", 23425, 18.2, 70.3, 11.5, 0.47]],
    "mailer_summary": {w: {"mailed": 20000, "responded": 2000 + i, "rate": 10.0 + i / 10,
                           "inside": {"first_time_pct": 100.0 - 5 * i}}
                       for i, w in enumerate(WAVES)},
}


def test_month_charts_render_with_v5_month_labels(tmp_path):
    d, slides = _run(CI, C, M, tmp_path)
    # (the latest-mailer panel wants a fuller summary than this fixture carries; not a month chart)
    failed = [x for x in d.declines if "chart failed" in x[1] and not x[0].startswith("mailsum_")]
    assert not failed, failed
    for topic in ("Response and reach by offer", "Ladder and NU conversion by offer",
                  "The counterfactual", "The campaign hero"):
        assert any(sh.shape_type == 13 for sh in slides[topic].shapes), f"{topic} has its chart"


def test_ic_rate_reads_as_a_percent(tmp_path):
    _d, slides = _run(CI, C, M, tmp_path)
    for topic in ("Segment trajectories", "Revenue frames"):
        text = _text(slides[topic])
        assert "0.68%" in text and "0.0068" not in text, topic


def test_hero_cards_carry_no_icons(tmp_path):
    _d, slides = _run(CI, C, M, tmp_path)
    pics = [sh for sh in slides["The campaign hero"].shapes if sh.shape_type == 13]
    assert len(pics) == 1, "the sparkline only"


def test_every_mailer_is_one_row_of_one_appendix_table(tmp_path):
    _d, slides = _run(CI, C, M, tmp_path)
    assert not any(t.startswith("Mailer ") and t.endswith(" summary") for t in slides)
    table = next(sh for sh in slides["Mailer summaries"].shapes
                 if getattr(sh, "has_table", False) and sh.has_table).table
    rows = [[c.text_frame.text for c in r.cells] for r in table.rows]
    assert rows[0] == ["Offer", "Mailed", "Responded", "Response %", "First-time %", "Rev to date"]
    assert [r[0] for r in rows[1:]] == list(reversed(WAVES)), "every mailer, newest first"
    assert rows[1][-1] == "$295K", "the workbook's revenue to date"


def test_program_reach_is_a_funnel_with_the_latest_offer(tmp_path):
    _d, slides = _run(CI, C, M, tmp_path)
    s = slides["Program reach"]
    assert any(sh.shape_type == 13 for sh in s.shapes)
    assert "Latest offer, Apr25" in _text(s) and "2,005" in _text(s)


def test_both_gain_figures_share_one_chart_each_with_its_window(tmp_path):
    _d, slides = _run(CI, C, M, tmp_path)
    text = _text(slides["What a response does to spend"])
    assert "$524/mo" in text and "three months after mail" in text
    assert "$371/mo" in text and "12 months" in text
    assert any(sh.shape_type == 13 for sh in slides["What a response does to spend"].shapes)


def test_tier_matrix_is_shaded_and_sets_responders_against_the_unmailed(tmp_path):
    _d, slides = _run(CI, C, M, tmp_path)
    s = slides["Where the tiers moved"]
    assert "Responders move up a swipe tier at 41%, 2.3x the unmailed rate" in _text(s)
    table = next(sh for sh in s.shapes if getattr(sh, "has_table", False) and sh.has_table).table
    diag, off = table.cell(1, 1).fill.fore_color.rgb, table.cell(1, 3).fill.fore_color.rgb
    assert diag != off, "the cells are shaded by their share of the row"


def test_pnl_sets_booked_against_did_as_a_two_column_table(tmp_path):
    _d, slides = _run(EI, E, M, tmp_path)
    text = _text(slides["Program P&L by offer"])
    assert "Booked: ARS Workbook" in text and "Incremental: DiD estimate" in text
    assert "What it answers" in text and "$2.36" in text and "0.68%" in text


@pytest.mark.parametrize("mod,chapter", [(CI, C), (EI, E)])
def test_no_footnote_under_10_5pt(tmp_path, mod, chapter):
    _d, slides = _run(mod, chapter, M, tmp_path)
    small = []
    for topic, s in slides.items():
        for sh in s.shapes:
            # the footnote band; the rail column's tile notes are the helper bundle's (its own floor)
            if (not sh.has_text_frame or sh.top < Emu(int(5.9 * 914400))
                    or sh.left >= Emu(int(10.0 * 914400)) or sh.text_frame.text.isdigit()):
                continue
            for p in sh.text_frame.paragraphs:
                for r in p.runs:
                    if r.font.size is not None and r.font.size.pt < 10.5:
                        small.append((topic, r.text[:40], r.font.size.pt))
    assert not small, small
