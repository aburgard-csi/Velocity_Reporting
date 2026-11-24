"""The shared deck table style (build/table_style.py; Aaron, 2026-11-24: "go ahead as shown").

Navy header kept; no zebra and no grid, one thin rule under each body row; figures right-aligned with their header;
the orange total row and any other deliberate colour kept; a status column reads as pills; two-line cells.
"""
import os
import sys

from pptx import Presentation
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO, "build")]

import brand                                                      # noqa: E402
import shapes as SH                                               # noqa: E402
import table_style as TS                                          # noqa: E402

DATA = [["Branch", "Accounts", "Take rate", "Status"],
        ["Main St", "1,204", "71.5%", "Above"],
        ["Riverside", "980", "64.2%", "Below"],
        ["All other branches", "n/a", "58.0%", "Almost flat"],
        ["Total", "2,184", "68.1%", ""]]


def _slide():
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    return prs, prs.slides.add_slide(prs.slide_layouts[6])


def _borders(cell):
    tcPr = cell._tc.find(qn("a:tcPr"))
    out = {}
    for tag in ("lnL", "lnR", "lnT", "lnB"):
        ln = tcPr.find(qn("a:" + tag))
        out[tag] = None if ln is None or ln.find(qn("a:noFill")) is not None else ln.find(".//" + qn("a:srgbClr")).get("val")
    return out


def test_add_table_draws_the_shared_style():
    prs, s = _slide()
    tb = SH.add_table(s, 0.5, 1.5, 8, 2.5, DATA, [3, 1, 1, 1.4], highlight=(4,), fs=12).table
    rows = list(tb.rows)
    assert all(TS.fill_of(c) == TS.NAVY for c in rows[0].cells)                       # navy header kept
    assert all(TS.fill_of(c) == brand.ORANGE.lstrip("#").upper() for c in rows[4].cells)   # total row kept
    for r in rows[1:4]:
        for j, c in enumerate(r.cells):
            if j != 3:
                assert TS.fill_of(c) is None, "no zebra"
            assert _borders(c) == {"lnL": None, "lnR": None, "lnT": None, "lnB": TS.RULE}, "one rule under the row"
    figs = [rows[1].cells[j].text_frame.paragraphs[0].alignment for j in range(3)]
    assert figs == [PP_ALIGN.LEFT, PP_ALIGN.RIGHT, PP_ALIGN.RIGHT]                    # text left, figures right
    assert rows[0].cells[1].text_frame.paragraphs[0].alignment == PP_ALIGN.RIGHT     # and their header


def test_a_status_column_reads_as_pills_and_an_unknown_word_is_left():
    prs, s = _slide()
    tb = SH.add_table(s, 0.5, 1.5, 8, 2.5, DATA, [3, 1, 1, 1.4], highlight=(4,), fs=12).table
    rows = list(tb.rows)
    assert TS.fill_of(rows[1].cells[3]) == TS.PILL["good"][0]
    assert TS.fill_of(rows[2].cells[3]) == TS.PILL["attention"][0]
    assert TS.fill_of(rows[3].cells[3]) == TS.PILL["neutral"][0]
    assert rows[1].cells[3].text_frame.paragraphs[0].runs[0].font.bold


def test_a_cell_can_carry_a_second_line_and_an_explicit_pill():
    prs, s = _slide()
    data = [["Branch", "Reg E"], [{"text": "3", "sub": "Main St"}, {"text": "28.0%", "pill": "good"}]]
    tb = SH.add_table(s, 0.5, 1.5, 6, 1.2, data, [2, 1], fs=14).table
    c = tb.cell(1, 0)
    paras = c.text_frame.paragraphs
    assert [p.text for p in paras] == ["3", "Main St"] and paras[0].runs[0].font.bold
    assert paras[1].runs[0].font.size.pt < paras[0].runs[0].font.size.pt
    assert TS.fill_of(tb.cell(1, 1)) == TS.PILL["good"][0]


def test_an_old_style_table_is_restyled_and_restyling_twice_changes_nothing():
    prs, s = _slide()
    gf = s.shapes.add_table(4, 3, Inches(0.5), Inches(1.5), Inches(8), Inches(2))
    tb = gf.table
    vals = [["Mailing", "Offers", "Response %"], ["Sep 2026", "13,248", "11.3%"], ["Jul 2026", "14,032", "Pending"],
            ["Mar 2026", "13,682", "14.6%"]]
    for i, row in enumerate(vals):
        for j, v in enumerate(row):
            tb.cell(i, j).text = v
            TS.set_fill(tb.cell(i, j), TS.NAVY if i == 0 else ("F2F5F8" if i % 2 else "FFFFFF"))   # retired-grey-ok
    from lxml import etree
    first = TS.restyle_deck(prs)
    xml1 = etree.tostring(gf._element)
    TS.restyle_deck(prs)
    assert first == 1 and etree.tostring(gf._element) == xml1
    assert all(TS.fill_of(c) is None for r in list(tb.rows)[1:] for c in r.cells)
    assert tb.cell(2, 2).text_frame.paragraphs[0].alignment == PP_ALIGN.RIGHT   # "Pending" sits with its figures


def test_a_deliberate_colour_is_kept():
    prs, s = _slide()
    tb = s.shapes.add_table(3, 2, Inches(0.5), Inches(1.5), Inches(6), Inches(1.5)).table
    for i in range(3):
        for j in range(2):
            tb.cell(i, j).text = "Quarter 1" if i == 1 else "x"
            TS.set_fill(tb.cell(i, j), TS.NAVY if i in (0, 1) else "FFFFFF")
    TS.restyle_table(tb)
    assert TS.fill_of(tb.cell(1, 0)) == TS.NAVY                                     # a navy band row stays


def test_every_builder_runs_it_through_the_layout_pass():
    import inspect
    import fit_layout
    assert "table_style.restyle_deck(prs)" in inspect.getsource(fit_layout.fit)
