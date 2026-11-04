"""
Communication Strategies slide, from the matrix validation extract.

PROVENANCE: the analysis team's `matrix_slides.py`. Its account-type settings, OD status code, override,
factor-grid, trend, tier and strategic-refund slides are gone: the matrix is now two slides, one per
account type (`matrix_prep_slides.py`, the ILS prep deck's layout, from the same extract), and strategic
refunds are not shown (Aaron, 2026-11-04). What is left is the communication strategies list, and only
the ACTIVE strategies are listed: an inactive one is left out entirely, and when none is active the
slide says so in one line.
"""
from __future__ import annotations

from pptx.enum.text import PP_ALIGN

from . import matrix_data as MD
from . import theme as T

X = 0.42
W = T.SLIDE_W - 2 * X            # 19.16
ROW_H = 0.46
HEAD_H = 0.54


def _fits(n_rows, y, row_h=ROW_H, head_h=HEAD_H):
    """Row height that keeps `n_rows` inside the content band from `y`."""
    avail = T.CONTENT_BOTTOM - y - head_h
    if n_rows <= 1:
        return row_h
    return max(0.20, min(row_h, avail / (n_rows - 1)))


def _fs(row_h, cap=15.0):
    """Font size that stays inside a given row height."""
    return max(8.0, min(cap, row_h * 30))


def slides_comm_strategies(dk, S, *, section, show_all=False):
    """Active communication strategies only. A list with none active says "None active" in one line."""
    rows = MD.section(S, "COMMUNICATION STRATEGIES")
    if not rows:
        return []
    active = MD.active_comm_strategies(S)
    if not active:
        slide = dk.content("Communication Strategies", "None active in the matrix validation extract.",
                           section=section)
        T.textbox(slide, X, T.CONTENT_TOP, W, 0.6, "None active", 20, color=T.NAVY, bold=True)
        return [slide]
    out = []
    for page_rows, page_no, pages in MD.paginate(active, MD.ROWS_PER_SLIDE, show_all):
        sub = f"{len(active)} active strategies — member outreach cadence"
        if pages > 1:
            sub += f"  ·  page {page_no} of {pages}"
        slide = dk.content("Communication Strategies", sub, section=section)
        y = T.CONTENT_TOP
        T.band_label(slide, X, y, W, "  ACTIVE STRATEGIES")
        cols = ["Strategy", "Group", "Type", "Priority", "Repeat", "Remove"]
        widths = [8.2, 3.2, 1.9, 1.8, 1.8, 1.8]
        rh = _fits(len(page_rows) + 1, y + 0.50)
        tbl = dk.table(slide, X, y + 0.50, W, widths, len(page_rows) + 1, row_h=rh, header_h=HEAD_H)
        fs = _fs(rh, 14)
        for c, h in enumerate(cols):
            T.head_cell(tbl.cell(0, c), h, 14, align=PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER)
        for ri, r in enumerate(page_rows, 1):
            bg = T.zebra(ri - 1)
            T.cell(tbl.cell(ri, 0), dk.term(r.get("STRATEGY_NAME", "")), fs, bg=bg, align=PP_ALIGN.LEFT)
            T.cell(tbl.cell(ri, 1), r.get("STRATEGY_GROUP", "") or "—", fs, bg=bg)
            T.cell(tbl.cell(ri, 2), r.get("COMMUNICATION_TYPE_ID", "") or "—", fs, bg=bg)
            T.cell(tbl.cell(ri, 3), r.get("STRATEGY_PRIORITY", "") or "—", fs, bg=bg)
            T.cell(tbl.cell(ri, 4), r.get("THRESHOLD_REPEAT", "") or "—", fs, bg=bg)
            T.cell(tbl.cell(ri, 5), r.get("THRESHOLD_REMOVE", "") or "—", fs, bg=bg)
        out.append(slide)
    return out
