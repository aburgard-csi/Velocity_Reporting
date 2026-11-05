"""A ported v5 table never runs off an RPE slide (build/ars_pipeline/ti/deck/helpers.py).

1615's closure-hazard table under a two-line headline ended at 7.65in on a 7.5in slide: v5's
slides had the same arithmetic and no check. The table now tightens its rows to stay above the
slide number's band, keeping every row, and an ordinary table is unchanged.
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
    rows = [["Tenure", "At risk", "Closed", "Hazard"]] + [[f"band {i}", "1,000", "100", "10.0%"] for i in range(5)]
    shape = H._table(_slide(), rows, H.MARGIN_L, 5.55, 9.0)
    assert len(shape.table.rows) == 6, "no row is dropped while the font can stay at 10pt or more"
    assert _bottom(shape) <= H.TABLE_FLOOR + 0.01, "the table stays above the slide number"


def test_a_table_too_long_for_10pt_sheds_rows_and_says_so_never_shrinks_under_10pt():
    """The font went down to 7pt (1798's closure-hazard table, Sheila's slide review, 2026-10-30);
    it now stops at TABLE_MIN_PT and the rows that do not fit are counted on the last row."""
    rows = [["Tenure", "At risk", "Closed", "Hazard"]] + [[f"band {i}", "1,000", "100", "10.0%"] for i in range(7)]
    shape = H._table(_slide(), rows, H.MARGIN_L, 5.55, 9.0)
    sizes = {r.font.size.pt for row in shape.table.rows for c in row.cells
             for p in c.text_frame.paragraphs for r in p.runs if r.font.size}
    assert min(sizes) >= H.TABLE_MIN_PT
    last = shape.table.cell(len(shape.table.rows) - 1, 0).text
    kept = len(shape.table.rows) - 2
    assert last == f"+ {7 - kept} more rows not shown"
    assert shape.table.cell(1, 0).text == "band 0", "the table keeps its first rows"
    assert _bottom(shape) <= H.TABLE_FLOOR + 0.01


def test_a_table_that_fits_is_unchanged():
    rows = [["A", "B"], ["x", "1"], ["y", "2"]]
    shape = H._table(_slide(), rows, H.MARGIN_L, 2.0, 6.0)
    assert all(abs(Emu(r.height).inches - 0.3) < 0.001 for r in shape.table.rows)


def test_a_compact_kpi_note_that_wraps_stays_inside_the_card_and_under_the_value():
    # 1776's ICS habits slide: fit_layout re-parked a compact card's note over its value
    import fit_layout
    s = _slide()
    H._kpi(s, 8.82, 5.62, 3.91, "Carries a debit card", "75%", "vs 72% non-ICS — the card has to exist first")
    fit_layout.fit(s.part.package.presentation_part.presentation)
    card, _label, value, note = list(s.shapes)
    assert _bottom(note) <= _bottom(card) + 0.001, "the note stays inside the card"
    assert _bottom(value) <= Emu(note.top).inches + 0.001, "the value ends where the note begins"
