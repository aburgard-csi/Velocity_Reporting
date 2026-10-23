"""A ported v5 table never runs off an RPE slide (build/ars_pipeline/ti/deck/helpers.py).

1615's closure-hazard table under a two-line headline ended at 7.65in on a 7.5in slide: v5's
slides had the same arithmetic and no check. The table now tightens its rows to stay above the
logo band, keeping every row, and an ordinary table is unchanged.
"""
from pptx import Presentation
from pptx.util import Emu, Inches

from ti.deck import helpers as H


def _slide():
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    return prs.slides.add_slide(prs.slide_layouts[6])


def _bottom(shape):
    return Emu(shape.top + shape.height).inches


def test_a_table_that_would_overflow_tightens_and_keeps_every_row():
    rows = [["Tenure", "At risk", "Closed", "Hazard"]] + [[f"band {i}", "1,000", "100", "10.0%"] for i in range(7)]
    shape = H._table(_slide(), rows, H.MARGIN_L, 5.55, 9.0)
    assert len(shape.table.rows) == 8, "no row is dropped"
    assert _bottom(shape) <= H.CONTENT_FLOOR + 0.01


def test_a_table_that_fits_is_unchanged():
    rows = [["A", "B"], ["x", "1"], ["y", "2"]]
    shape = H._table(_slide(), rows, H.MARGIN_L, 2.0, 6.0)
    assert all(abs(Emu(r.height).inches - 0.3) < 0.001 for r in shape.table.rows)
