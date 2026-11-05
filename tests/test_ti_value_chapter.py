"""The Value chapter (build/ars_pipeline/ti/chapters/value.py, ti/deck/value_inline.py).

v5's six value slides, lifted from its build function: every slide is drawn or stated, in v5's
order, and the card slide spells out the conversion math. Its compute runs v5's sections, then the
leak post-passes on what they returned.
"""
from pptx import Presentation

from ti.chapters import value as C


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


def test_no_value_figures_states_every_slide_in_order(tmp_path, monkeypatch):
    # every slide the register keeps: group Q (Sheila's 1798 review, 2026-10-30) tosses two of the
    # six in ti/slides.json, and a tossed slide is left out, not stated
    from ti import selection
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    slides = C.build(_Ctx(_prs(), {}, tmp_path))
    kept = [t for t in C.TITLES.values() if selection.slide_kept(t)]
    assert len(slides) == len(kept)
    for s, title in zip(slides, kept):
        assert title in _text(s) and "Not shown for this client" in _text(s)


def test_the_card_slide_spells_out_the_conversion_math(tmp_path, monkeypatch):
    monkeypatch.setenv("RPE_DATA_ROOT", str(tmp_path))
    m = {"value_debit_delta": 183.49, "value_rege_delta": 177.84, "value_debit_n_without": 10000,
         "value_rege_n_without": 20000, "take_new_pct": 50.0, "rege_pct": 21.0,
         "value_per_card": 183.49, "value_per_optin": 177.84}
    slides = C.build(_Ctx(_prs(), m, tmp_path))
    card = _text(slides[0])
    assert "CONVERSION MATH" in card and "5,000 new cards" in card
    # cut to "if 21.0% also opt in" when the slide was held to 60 words (Sheila's 1798 review)
    assert "more a year if 21.0% also opt in" in card


def test_compute_runs_the_sections_then_the_leaks_on_their_figures(monkeypatch):
    from ti import odd_sections as O
    calls = []
    for name in ("dctr", "rege", "interchange_odd", "value"):
        monkeypatch.setattr(O, name, lambda ctx, name=name: (calls.append(name), {f"{name}_x": 1})[1])
    monkeypatch.setattr(O, "leaks", lambda ctx, figs: (calls.append(("leaks", sorted(figs))), {"leaks_x": 1})[1])
    out = C.compute(object())
    assert calls[:4] == ["dctr", "rege", "interchange_odd", "value"]
    assert calls[4] == ("leaks", ["dctr_x", "interchange_odd_x", "rege_x", "value_x"])
    assert out["leaks_x"] == 1
