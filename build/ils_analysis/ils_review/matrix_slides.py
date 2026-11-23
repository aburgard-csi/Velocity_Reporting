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
    # One line per active strategy, in large type: the name, then its group and how often it repeats. The
    # type, priority and removal threshold are in the extract and the speaker notes, not on the slide.
    import shapes
    from pptx.enum.text import MSO_ANCHOR
    lines = []
    for r in active:
        name = str(dk.term(r.get("STRATEGY_NAME", ""))).strip() or "Unnamed strategy"
        rep = str(r.get("THRESHOLD_REPEAT", "") or "").strip()
        try:
            rep_n = float(rep)
        except ValueError:
            rep_n = None
        bits = [f"repeats every {rep} days"] if rep_n and rep_n > 0 else []
        lines.append(name + ("  ·  " + "  ·  ".join(bits) if bits else ""))
    cap = 9
    shown = lines[:cap]
    if len(lines) > cap:
        shown.append(f"and {len(lines) - cap} more active strategies (see the matrix validation extract)")
    slide = dk.content(f"{len(active)} communication strateg{'y is' if len(active) == 1 else 'ies are'} active",
                       "Member outreach strategies switched on in the matrix validation extract; inactive strategies are not shown.",
                       section=section)
    shapes.textbox(slide, X, 1.80, 12.33, 0.45, "ACTIVE STRATEGIES", 14, T.NAVY, True, PP_ALIGN.LEFT, T.HEAD, MSO_ANCHOR.TOP)
    T.bullets_real(slide, 0.50, 2.30, 12.33, 4.2, shown, size=20, min_size=16)
    detail = "; ".join(f"{str(r.get('STRATEGY_NAME', '')).strip()}: type {r.get('COMMUNICATION_TYPE_ID', '') or 'n/a'}, priority "
                       f"{r.get('STRATEGY_PRIORITY', '') or 'n/a'}, repeat {r.get('THRESHOLD_REPEAT', '') or 'n/a'}, "
                       f"remove {r.get('THRESHOLD_REMOVE', '') or 'n/a'}" for r in active)
    slide.notes_slide.notes_text_frame.text = ("Say first: these are the member messages ILS is sending today.\n"
                                               + slide.notes_slide.notes_text_frame.text + "\nDetail: " + detail)
    return [slide]
