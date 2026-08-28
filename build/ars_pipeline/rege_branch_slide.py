#!/usr/bin/env python3
"""
rege_branch_slide.py — the ARS "Reg E Opt-In by Branch" table slide.

Slides 27/28 already chart the opt-in RATE by branch. A rate alone doesn't say how
many customers sit behind it, and it hides the split between an explicit opt-out and
not having given us one (no election) — which are different coaching problems. This
slide puts the three elections and the branch's population in a table (Aaron,
2026-08-28).

Cohort is accounts opened in the trailing 12 months, not the whole book (Aaron,
2026-08-28): the all-vintages view is dominated by decades of legacy elections and says
nothing about how branches are asking today. The heading states the window ACTUALLY
used — an extract carrying fewer than twelve activity months yields a shorter one
(Wellworth's is Mar-Jul 2026), and claiming "Last 12 Months" over five would be false.

Inserted after the last Reg E branch chart slide, before "Reg E Opt-In by Account
Vintage".

Rows are sized to the space on the slide rather than a fixed N, and the table always
carries a Total line so it reconciles against the program figure on slide 27.

Public entry point
------------------
    add_rege_branch_slide(prs, M, assets_dir, after_title="Reg E Opt-In — Opened")
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pptx.util import Inches
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

from product_mix_slide import (
    _tb, _pill, _tile, _add_table, _blank_slide, _slide_title, _sldid_of,
    _move_before, _renumber, NAVY, ORANGE, GREYT, HEAD, BODY,
)

# geometry — same rail as the other ARS table slides
_TBL_TOP, _ROW_H, _TBL_BOTTOM = 2.62, 0.32, 6.60


def _rows(M, max_body):
    src = M.get("rege_branch_table") or []
    shown = src[:max_body]
    rows = [["Branch", "Opted In", "Opted Out", "No Election", "Accounts", "Opt-In %"]]
    for b, i, o, n, tot, pct in shown:
        rows.append([str(b), f"{i:,}", f"{o:,}", f"{n:,}", f"{tot:,}", f"{pct}%"])
    rest = src[max_body:]
    if rest:
        ri = sum(x[1] for x in rest); ro = sum(x[2] for x in rest)
        rn = sum(x[3] for x in rest); rt = sum(x[4] for x in rest)
        rows.append([f"All other branches ({len(rest)})", f"{ri:,}", f"{ro:,}",
                     f"{rn:,}", f"{rt:,}", f"{round(100*ri/rt) if rt else 0}%"])
    ti, to, tn, tt = M.get("rege_branch_table_total") or [0, 0, 0, 0]
    rows.append(["Total (branches shown)", f"{ti:,}", f"{to:,}", f"{tn:,}", f"{tt:,}",
                 f"{round(100*ti/tt) if tt else 0}%"])
    return rows, (len(rows) - 1,), len(shown), len(src)


def add_rege_branch_slide(prs, M, assets_dir, month_label,
                          after_title="Reg E Opt-In — Opened",
                          before_title="Reg E Opt-In by Account Vintage",
                          renumber=True):
    """Build the Reg E by Branch table slide. Returns (slide, n_branches) or
    (None, 0) when the client has no branch large enough to report."""
    if not M.get("rege_branch_table"):
        print("!! reg-e-by-branch: no branch opened 15+ personal card accounts in the "
              "window — slide skipped rather than shipped empty")
        return None, 0

    anchor = next((s for s in prs.slides if _slide_title(s).startswith(after_title)), None)
    template = anchor or next((s for s in prs.slides
                               if _slide_title(s).startswith(before_title)), prs.slides[0])
    s = _blank_slide(prs, template)

    max_body = int((_TBL_BOTTOM - _TBL_TOP) / _ROW_H) - 2   # header + Total
    rows, highlight, nshown, ntotal = _rows(M, max_body)

    win = M.get("rege_new_window") or []
    if len(win) == 3 and win[2] >= 12:
        head, when = "Reg E Opt-In by Branch — Last 12 Months", "in the last 12 months"
    elif len(win) == 3:
        # fewer than 12 activity months in the extract: name the real window
        head, when = "Reg E Opt-In by Branch — New Accounts", f"{win[0]} – {win[1]}"
    else:
        head, when = "Reg E Opt-In by Branch", "recently"
    _tb(s, 0.5, 0.28, 9.6, 0.9, head, 26, NAVY, True,
        PP_ALIGN.LEFT, HEAD, MSO_ANCHOR.MIDDLE)
    _pill(s, f"{month_label} Data")
    # measured at 16pt Calibri against 12.10in of usable box: restyle_fonts floors every
    # run at 16pt, and a longer wording ran to 13.44in and wrapped onto the tiles below
    # (CLAUDE.md rule 2 — box geometry is not glyph geometry)
    # "no election means the customer was never asked" asserted something the data
    # cannot show and put it on the branch. No election means only that we do not hold
    # their decision — they may well have been asked (Aaron, 2026-08-28). The exact
    # wording "didn't give us their decision" measures 12.30in against 12.10in of box
    # and wraps onto the tiles, so this is the closest phrasing that fits on one line.
    _tb(s, 0.5, 1.12, 12.3, 0.5,
        f"Accounts opened {when} and still open. Opted out is a decision; "
        f"no election means the customer hasn't given us one.",
        14, GREYT, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)

    # Tiles read off the SAME population as the table. Using the program-wide
    # rege_in / rege_no here put 6,198 in a tile above a table totalling 6,194 — the
    # 4-account gap is the sub-40-holder branches, and two populations on one slide
    # reads as an arithmetic error (Aaron, 2026-08-28).
    pool = M.get("rege_pool", 0)
    ti, to, tn, tt = M.get("rege_branch_table_total") or [0, 0, 0, 0]
    # every label measured at 16pt Calibri against 2.55in of usable tile — the fuller
    # wordings ("Branches reported (40+ holders)" 2.84in, "Branches (15+ new accounts)"
    # 2.58in) both wrapped and spilled below the tile
    tiles = [(f"{round(100*ti/tt) if tt else 0}%", "Opt-in rate, new accounts", ORANGE),
             (f"{ti:,}", "Opted in", NAVY),
             (f"{tn:,}", "No election on file", NAVY),
             (f"{ntotal}", "Branches (15+ new)", NAVY)]
    for i, (v, l, f) in enumerate(tiles):
        _tile(s, 0.56 + i * 3.12, 1.66, 2.85, 0.84, v, l, fill=f)

    h = min(_ROW_H * len(rows), _TBL_BOTTOM - _TBL_TOP)
    _add_table(s, 0.5, _TBL_TOP, 12.3, h, rows, [1.7, 0.8, 0.8, 0.9, 0.8, 0.8],
               highlight=highlight, fs=11)

    s.notes_slide.notes_text_frame.text = (
        f"Source: client ODD, {month_label} snapshot — Reg E election field. Cohort: "
        f"personal debit-card holders OPENED {when}, still open "
        f"({M.get('rege_new_pool', 0):,} accounts; program opt-in "
        f"{M.get('rege_new_pct', 0)}%). Branches with at least 15 such accounts "
        f"({nshown} of {ntotal} shown). Total covers the reported branches only, so it "
        f"is below the full new-account pool where small branches are excluded. The "
        f"all-vintages book ({pool:,} holders) is on the preceding chart slides.")

    logo = os.path.join(assets_dir, "logo.png")
    if os.path.exists(logo):
        s.shapes.add_picture(logo, Inches(11.28), Inches(6.78), Inches(1.70), Inches(0.54))

    if anchor is not None:
        sid, tid = _sldid_of(prs, s), _sldid_of(prs, anchor)
        if sid is not None and tid is not None:
            prs.slides._sldIdLst.remove(sid); tid.addnext(sid)
    else:
        _move_before(prs, s, before_title)
    if renumber:
        _renumber(prs)
    return s, nshown
