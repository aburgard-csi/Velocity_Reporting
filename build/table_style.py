"""The table style every deck shares (Aaron, 2026-11-24: "go ahead as shown").

Brought over from his Mission Control page (the Aaron Design System), adapted for slides read from across a room:

  * the NAVY header row stays (white bold text): it anchors the brand and reads from 15 feet;
  * body rows: no alternating grey and no grid lines; ONE thin rule (brand.LABEL) under each row;
  * a deliberate colour is kept: the orange total / highlighted row, a navy band row, a heat cell;
  * figure columns are RIGHT-aligned together with their header, so digits and decimals line up; text stays left;
  * a status word in a status column ("Leading", "Status", "vs peers") reads as a pill: a tinted cell with the word in
    bold colour, never colour alone (`PILL`);
  * `two_line` puts a bold label over a smaller grey line in one cell (a branch number over its name).

`restyle_deck(prs)` is run by `fit_layout.fit`, which every builder calls before saving, so ARS, ICS, MRPC, CashPlease,
the Companion and Transaction Intelligence decks, the combined deck and the ILS decks Sheila builds all match.
`shapes.add_table` draws new tables this way directly. Idempotent: restyling a restyled table changes nothing.
"""
import re

from lxml import etree
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Pt

import brand

_hex = lambda c: c.lstrip("#").upper()
NAVY = _hex(brand.NAVY)
RULE = _hex(brand.LABEL)                 # the row rule: the brand grey closest to the approved render
RULE_W = 9525                            # 0.75 pt
# Fills that were only ever zebra striping (or a white cell): cleared. Any other fill is a deliberate colour and stays.
# The retired greys are listed because template shells and older tables still carry them as stripes; they are read
# here to be REMOVED, never drawn.
ZEBRA = {_hex(brand.ROWALT), "ECF0F4", "F2F5F8", "FFFFFF", "F2F2F2", "F5F5F5", "EDEDED"}   # retired-grey-ok
# A figure: a number with its unit or sign, a ratio ("2.2 : 1") or a change ("+3.1 pts").
NUM = re.compile(r"^\s*[\(\-−–+]?\s*[$€£]?\s*\d[\d.,]*\s*(%|x|pts?|k|m|bn|bp|bps)?\)?"
                 r"(\s*:\s*1)?\s*$", re.I)
PLACEHOLDER = re.compile(r"^\s*(n/?a|—|-|–|pending|tbd|\*)?\s*$", re.I)
STATUS_HEAD = re.compile(r"(?i)\b(lead(ing)?|status|verdict|vs\.?\s*(the\s*)?(peers|median)|against peers)\b")
# A status word -> its tone. Unknown words are left as they are.
STATUS = {"keep": "good", "above": "good", "above the median": "good", "on track": "good", "met": "good",
          "delete": "attention", "below": "attention", "below the median": "attention", "at risk": "attention",
          "behind": "attention", "not met": "attention",
          "appendix": "neutral", "almost flat": "neutral", "flat": "neutral", "in line": "neutral"}
PILL = {"good": (_hex(brand.LABEL), NAVY), "attention": (_hex(brand.PEACH), _hex(brand.ORANGE)),
        "neutral": (_hex(brand.ROWALT), _hex(brand.TICK))}
_ORDER = ["a:lnL", "a:lnR", "a:lnT", "a:lnB", "a:lnTlToBr", "a:lnBlToTr", "a:cell3D", "a:noFill", "a:solidFill",
          "a:gradFill", "a:blipFill", "a:pattFill", "a:grpFill", "a:headers", "a:extLst"]
_RANK = {qn(t): i for i, t in enumerate(_ORDER)}


# ----------------------------------------------------------------- cell XML
def fill_of(cell):
    """The cell's solid fill as 'RRGGBB', 'SCHEME' for a theme colour, or None for no fill."""
    tcPr = cell._tc.find(qn("a:tcPr"))
    s = tcPr.find(qn("a:solidFill")) if tcPr is not None else None
    if s is None:
        return None
    c = s.find(qn("a:srgbClr"))
    return c.get("val").upper() if c is not None else "SCHEME"


def _tidy(tcPr):
    kids = sorted(list(tcPr), key=lambda e: _RANK.get(e.tag, 99))       # the schema's child order
    for k in kids:
        tcPr.remove(k)
    for k in kids:
        tcPr.append(k)


def set_fill(cell, hexval):
    tcPr = cell._tc.get_or_add_tcPr()
    for tag in ("a:solidFill", "a:noFill", "a:gradFill", "a:pattFill", "a:blipFill", "a:grpFill"):
        for e in tcPr.findall(qn(tag)):
            tcPr.remove(e)
    f = etree.SubElement(tcPr, qn("a:solidFill") if hexval else qn("a:noFill"))
    if hexval:
        etree.SubElement(f, qn("a:srgbClr")).set("val", hexval)
    _tidy(tcPr)


def _line(tag, color):
    ln = etree.Element(qn(tag))
    if color:
        ln.set("w", str(RULE_W))
        sf = etree.SubElement(ln, qn("a:solidFill"))
        etree.SubElement(sf, qn("a:srgbClr")).set("val", color)
    else:
        ln.set("w", "0")
        etree.SubElement(ln, qn("a:noFill"))
    return ln


def set_rule(cell, bottom):
    """No left, right or top line; a thin rule along the bottom when `bottom` (a colour), else none."""
    tcPr = cell._tc.get_or_add_tcPr()
    for tag in ("a:lnL", "a:lnR", "a:lnT", "a:lnB", "a:lnTlToBr", "a:lnBlToTr"):
        for e in tcPr.findall(qn(tag)):
            tcPr.remove(e)
    for tag in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
        tcPr.append(_line(tag, bottom if tag == "a:lnB" else None))
    _tidy(tcPr)


def _align(cell, how):
    for p in cell.text_frame.paragraphs:
        p.alignment = how


def text(cell):
    return cell.text_frame.text.strip()


# ----------------------------------------------------------------- one table
def header_rows(rows):
    """1 when the first row is the navy header, else 0."""
    return 1 if rows and all((fill_of(c) or "") == NAVY for c in rows[0].cells) else 0


def figure_columns(rows, header):
    """Columns whose filled body cells are mostly figures (placeholders such as n/a or Pending are not counted)."""
    ncol = len(rows[0].cells) if rows else 0
    out = []
    for j in range(ncol):
        vals = [text(r.cells[j]).split("\n")[0] for r in rows[header:]]
        vals = [v for v in vals if not PLACEHOLDER.match(v)]
        out.append(bool(vals) and sum(1 for v in vals if NUM.match(v)) >= 0.7 * len(vals))
    return out


def pill(cell, tone):
    bg, fg = PILL[tone]
    set_fill(cell, bg)
    for p in cell.text_frame.paragraphs:
        for r in p.runs:
            r.font.bold = True
            r.font.color.rgb = RGBColor.from_string(fg)


def restyle_table(tbl):
    """Apply the shared style to one python-pptx table. Returns (header rows, figure columns)."""
    rows = list(tbl.rows)
    if not rows:
        return 0, []
    tblPr = tbl._tbl.tblPr
    for a in ("bandRow", "bandCol", "firstRow", "lastRow"):           # the table style's own banding is off
        if tblPr.get(a) is not None:
            tblPr.set(a, "0")
    header = header_rows(rows)
    figures = figure_columns(rows, header)
    status = [j for j in range(len(figures)) if header and STATUS_HEAD.search(text(rows[0].cells[j]))]
    for i, r in enumerate(rows):
        for j, c in enumerate(r.cells):
            if i < header:
                set_rule(c, None)
                _align(c, PP_ALIGN.RIGHT if figures[j] else PP_ALIGN.LEFT)
                continue
            f = fill_of(c)
            if f is None or f in ZEBRA:
                set_fill(c, None)
            set_rule(c, RULE)
            _align(c, PP_ALIGN.RIGHT if figures[j] else PP_ALIGN.LEFT)
            if j in status:
                tone = STATUS.get(text(c).lower())
                if tone:
                    pill(c, tone)
    return header, figures


def restyle_deck(prs):
    """Every table in the deck. Returns the number restyled."""
    n = 0
    for s in prs.slides:
        for sh in s.shapes:
            if getattr(sh, "has_table", False) and sh.has_table:
                restyle_table(sh.table)
                n += 1
    return n


def two_line(cell, main, sub, size, sub_size=None, color=None):
    """A bold label with a smaller grey line under it, in one cell (a branch number over its name)."""
    tf = cell.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = str(main)
    r.font.bold = True
    r.font.size = Pt(size)
    if color is not None:
        r.font.color.rgb = color
    p2 = tf.add_paragraph()
    r2 = p2.add_run()
    r2.text = str(sub)
    r2.font.size = Pt(sub_size or max(8, size - 3))
    r2.font.color.rgb = RGBColor.from_string(_hex(brand.TICK))
    return cell
