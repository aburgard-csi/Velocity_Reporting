#!/usr/bin/env python3
"""
branch_appendix_slides.py — the ARS branch-detail tables, in the Appendix.

Aaron, 2026-11-02: "in the executive review deck for branch data around debit cards and Reg E, I
want the full branch performance in the appendix. We don't need the branch detail in the main
deck, just the charts." The main deck keeps the charts (the take-rate-by-branch bars on the two
Take Rate slides, the opt-in-by-branch bars on the two Reg E slides). The tables behind them move
here, one family per measure, as many pages as the branches need so none is left out:

    Appendix: Take Rate by Branch (k of n)          new ARS-eligible personal accounts, cards by month opened
    Appendix: Reg E Opt-In by Branch (k of n)       all open personal debit-card holders
    Appendix: Reg E New Accounts by Branch (k of n) accounts opened in the last 12 months, by election

A branch the metric leaves out (under 15 new accounts, or under 40 holders) is not dropped: the
remainder is one "All other branches" row, worked out against the program figure, so every table
ends on a Total that is the number the chart slides state.

Tables run at 12 pt (the 16 pt floor cannot seat 15 rows); `restyle_fonts` keeps them there by the
table's shape name, `BRANCH_DETAIL_TABLE`. Everything else on the slide keeps the floor.

Slides are added after the Appendix divider and are never removed once added. Their notes carry the
source and the cohort (`BODY_NOTES`, read by build_ars_gen's per-slide source pass).

Public entry point
------------------
    add_branch_appendix(prs, M, assets_dir, month_label, window_pill, window_text) -> [slides]
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pptx.util import Inches
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

from product_mix_slide import (
    _tb, _pill, _add_table, _blank_slide, _slide_title, _sldid_of, _renumber,
    NAVY, GREYT, HEAD, BODY,
)
import chart_lib
from textfit import fits_one_line, text_width_in

BRANCH_DETAIL_TABLE = "Branch Detail Table"      # the shape name restyle_fonts leaves at 12 pt
TABLE_PT = 12
_TOP, _ROW_H, _BOTTOM = 1.80, 0.28, 6.55          # 16 rows of 0.28in: a header and 15 lines
MAX_ROWS = int((_BOTTOM - _TOP) / _ROW_H + 1e-6)
_SUB_W = 12.3                                    # the subtitle's box, inches
_SUB_FIT = 11.7                                  # what a 16 pt line may measure: the box less its insets and PowerPoint's wrap margin

# slide title -> the notes body for build_ars_gen's source pass ("Source: <the client's ODD extract> — " is put in front)
BODY_NOTES = {}


# ----------------------------------------------------------------------------- rows
def _pct(n, d):
    return round(100 * n / d) if d else 0


def paginate(body, total, cap=MAX_ROWS):
    """Split `body` rows plus the `total` row into pages of at most cap-1 lines (a header takes
    one row), as evenly as it goes. -> a list of (lines, has_total)."""
    lines = list(body) + [total]
    room = cap - 1
    pages = max(1, math.ceil(len(lines) / room))
    per = math.ceil(len(lines) / pages)
    return [lines[i * per:(i + 1) * per] for i in range(pages)]


def take_rows(M):
    """(header, body rows, total row, n_other_flag). Branches in branch-number order, as the chart
    draws them; the remainder against the program totals is 'All other branches'."""
    months = list(M.get("take_months") or [])
    num_of = {v: k for k, v in (M.get("branch_name_of") or {}).items()}
    src = chart_lib.branch_order(M.get("take_branch_monthly") or [],
                                 key=lambda r: num_of.get(r[0], r[0]))
    k = len(months)
    body = [[str(r[0])] + [str(x) for x in r[1:1 + k]]
            + [f"{r[-3]:,}", f"{r[-2]:,}", f"{r[-1]}%"] for r in src]
    cards, elig = int(M.get("take_new_cards") or 0), int(M.get("take_new_total") or 0)
    col_tot = list(M.get("take_col_totals") or [])
    rem_cards = cards - sum(r[-3] for r in src)
    rem_elig = elig - sum(r[-2] for r in src)
    rem_cols = [col_tot[j] - sum(r[1 + j] for r in src) for j in range(k)] if len(col_tot) == k else None
    other = False
    if rem_elig > 0 and rem_cards >= 0 and rem_cols is not None and all(c >= 0 for c in rem_cols):
        body.append(["All other branches"] + [str(c) for c in rem_cols]
                    + [f"{rem_cards:,}", f"{rem_elig:,}", f"{_pct(rem_cards, rem_elig)}%"])
        other = True
    elif rem_elig != 0:
        print("!! branch appendix: take-rate branch rows do not reconcile to the program total "
              f"({elig:,} accounts against {sum(r[-2] for r in src):,} in the rows) — no remainder row")
    total = (["Total"] + [str(x) for x in col_tot]
             + [f"{cards:,}", f"{elig:,}", f"{_pct(cards, elig)}%"])
    header = ["Branch"] + months + ["Cards", "Elig", "Take%"]
    return header, body, total, other


def rege_all_rows(M):
    """All open personal debit-card holders: (branch, in, holders, pct), rate first as the metric
    sorts them; branches under 40 holders are the remainder against the program figure."""
    src = M.get("rege_branch") or []
    body = [[str(b), f"{i:,}", f"{t:,}", f"{p}%"] for b, i, t, p in src]
    pool, p_in = int(M.get("rege_pool") or 0), int(M.get("rege_in") or 0)
    rem_t, rem_i = pool - sum(r[2] for r in src), p_in - sum(r[1] for r in src)
    other = False
    if rem_t > 0 and rem_i >= 0:
        body.append(["All other branches", f"{rem_i:,}", f"{rem_t:,}", f"{_pct(rem_i, rem_t)}%"])
        other = True
    elif rem_t != 0:
        print("!! branch appendix: Reg E branch rows do not reconcile to the program holders — no remainder row")
    total = ["Total", f"{p_in:,}", f"{pool:,}", f"{_pct(p_in, pool)}%"]
    return ["Branch", "Opted In", "Holders", "Opt-In %"], body, total, other


def rege_new_rows(M):
    """Accounts opened in the last 12 months: (branch, in, out, no election, accounts, pct)."""
    src = M.get("rege_branch_table") or []
    body = [[str(b), f"{i:,}", f"{o:,}", f"{n:,}", f"{t:,}", f"{p}%"] for b, i, o, n, t, p in src]
    pool = int(M.get("rege_new_pool") or 0)
    p_in, p_out, p_no = (int(M.get(k) or 0) for k in ("rege_new_in", "rege_new_out", "rege_new_no"))
    rem = [pool - sum(r[4] for r in src), p_in - sum(r[1] for r in src),
           p_out - sum(r[2] for r in src), p_no - sum(r[3] for r in src)]
    other = False
    if rem[0] > 0 and min(rem) >= 0:
        body.append(["All other branches", f"{rem[1]:,}", f"{rem[2]:,}", f"{rem[3]:,}",
                     f"{rem[0]:,}", f"{_pct(rem[1], rem[0])}%"])
        other = True
    elif rem[0] != 0:
        print("!! branch appendix: Reg E new-account branch rows do not reconcile to the cohort — no remainder row")
    total = ["Total", f"{p_in:,}", f"{p_out:,}", f"{p_no:,}", f"{pool:,}", f"{_pct(p_in, pool)}%"]
    return ["Branch", "Opted In", "Opted Out", "No Election", "Accounts", "Opt-In %"], body, total, other


# ----------------------------------------------------------------------------- slides
def _widths(header, rows, first_min=1.7, other=0.0):
    """Column widths in inches: the first fits its longest label (measured, not eyeballed), the rest share
    what is left. -> (widths, table width)."""
    need = max(text_width_in(str(r[0]), TABLE_PT, "Carlito", True) for r in [header] + rows) + 0.3
    first = max(first_min, need)
    n = len(header) - 1
    each = 0.95 if n <= 5 else 0.78
    each = max(each, max(text_width_in(h, TABLE_PT, "Carlito", True) for h in header[1:]) + 0.3)
    return [first] + [each] * n, first + each * n


def _one_line(candidates, pt=16):
    for c in candidates:
        if fits_one_line(c, _SUB_FIT, pt, "Carlito"):
            return c
    return candidates[-1]


def _page(prs, template, title, pill, subtitle, header, lines, has_total, other_note, logo, widths_hint):
    s = _blank_slide(prs, template)
    _tb(s, 0.5, 0.28, 9.5, 0.9, title, 24, NAVY, True, PP_ALIGN.LEFT, HEAD, MSO_ANCHOR.MIDDLE)   # 24 pt: the longest title measures 8.5in of the 9.3in box
    # "September 2026 Data" needs 2.65in with its margins at the 16 pt restyle_fonts raises it to; PowerPoint
    # wrapped it inside the template's 2.35in (and the 2.50in the final pass widens to). Right edge stays at 12.85.
    sp = _pill(s, pill)
    sp.left, sp.width = Inches(10.0), Inches(2.85)
    _tb(s, 0.5, 1.12, _SUB_W, 0.5, subtitle, 16, GREYT, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
    data = [header] + lines
    colw, w = widths_hint
    h = _ROW_H * len(data)
    gf = _add_table(s, (13.333 - w) / 2 if w < 12.0 else 0.5, _TOP, w, h, data, colw,
                    highlight=((len(data) - 1,) if has_total else ()), fs=TABLE_PT)
    gf.name = BRANCH_DETAIL_TABLE
    if other_note:
        _tb(s, 0.5, 6.58, 10.4, 0.32, other_note, 16, GREYT, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
    if logo:
        s.shapes.add_picture(logo, Inches(11.28), Inches(6.78), Inches(1.70), Inches(0.54))
    return s


def _family(prs, template, name, pill, subtitles, body_note, header, body, total, other, other_note,
            logo, M, first_min=1.7):
    pages = paginate(body, total)
    n = len(pages)
    colw = _widths(header, body + [total], first_min)
    made = []
    for k, lines in enumerate(pages, 1):
        title = f"Appendix: {name} ({k} of {n})"
        sl = _page(prs, template, title, pill, _one_line(subtitles), header, lines,
                   has_total=(k == n), other_note=(other_note if other else ""), logo=logo,
                   widths_hint=colw)
        listed = [r[0] for r in lines if r[0] != "Total"]
        BODY_NOTES[title] = (f"{body_note} Page {k} of {n}: {len(listed)} line{'s' if len(listed) != 1 else ''}"
                             f" ({listed[0]} to {listed[-1]}). Every branch the metric reports is listed; "
                             f"the Total is the program figure shown on the chart slides.")
        made.append(sl)
    return made


def add_branch_appendix(prs, M, assets_dir, month_label, window_pill, window_text, renumber=True):
    """Add the branch-detail pages after the Appendix divider. -> the slides added (empty when the
    deck has no Appendix divider or no branch data to list)."""
    divider = next((sl for sl in prs.slides if _slide_title(sl).strip().lower() == "appendix"), None)
    if divider is None:
        print("!! branch appendix: no Appendix divider in the deck — tables not added")
        return []
    # a content slide's layout, not the divider's
    content = next((sl for sl in prs.slides if _slide_title(sl).startswith("Reg E Opt-In by Account Vintage")),
                   divider)
    logo = os.path.join(assets_dir, "logo.png")
    logo = logo if os.path.exists(logo) else None
    made = []

    if M.get("take_branch_monthly"):
        header, body, total, other = take_rows(M)
        made += _family(
            prs, content, "Take Rate by Branch", window_pill,
            [f"Selection: new ARS-eligible personal accounts opened {window_text}; monthly columns count those "
             f"holding a debit card.",
             f"New ARS-eligible personal accounts opened {window_text}; debit cards by month opened."],
            f"Debit cards held on ARS-eligible personal accounts "
            f"opened {window_text}, by branch and month opened. Branches with at least 15 such accounts are "
            f"listed; the rest are one row, and the Total is every such account. Monthly columns run "
            f"{(M.get('take_months') or ['?'])[0]} to {(M.get('take_months') or ['?'])[-1]}, the months of "
            f"activity this extract carries.",
            header, body, total, other,
            "Branches with under 15 new accounts are grouped as All other branches.", logo, M)
    else:
        print("!! branch appendix: no branch has 15+ new ARS-eligible personal accounts — take-rate pages skipped")

    if M.get("rege_branch"):
        header, body, total, other = rege_all_rows(M)
        made += _family(
            prs, content, "Reg E Opt-In by Branch", f"{month_label} Data",
            [f"Selection: all open personal accounts holding a debit card ({int(M.get('rege_pool') or 0):,}), "
             f"by branch.",
             "Selection: all open personal debit-card holders, by branch."],
            f"Reg E election field on open personal accounts "
            f"holding a debit card ({int(M.get('rege_pool') or 0):,}). Branches with at least 40 holders are "
            f"listed; the rest are one row, and the Total is every holder.",
            header, body, total, other,
            "Branches with under 40 holders are grouped as All other branches.", logo, M)
    else:
        print("!! branch appendix: no branch has 40+ debit-card holders — Reg E pages skipped")

    if M.get("rege_branch_table"):
        header, body, total, other = rege_new_rows(M)
        win = M.get("rege_new_window") or []
        when = ("in the last 12 months" if len(win) == 3 and win[2] >= 12
                else (f"{win[0]} – {win[1]}" if len(win) == 3 else "recently"))
        made += _family(
            prs, content, "Reg E New Accounts by Branch", f"{month_label} Data",
            [f"Selection: personal debit-card accounts opened {when} and still open, by Reg E election.",
             f"Selection: debit-card accounts opened {when}, still open, by Reg E election."],
            f"Reg E election field. Cohort: personal debit-card "
            f"holders OPENED {when}, still open ({int(M.get('rege_new_pool') or 0):,} accounts; program opt-in "
            f"{M.get('rege_new_pct', 0)}%). Branches with at least 15 such accounts are listed; the rest are "
            f"one row, and the Total is the whole cohort. No election means we do not hold the customer's "
            f"decision, not that they were never asked.",
            header, body, total, other,
            "Branches with under 15 new accounts are grouped as All other branches.", logo, M)
    else:
        print("!! branch appendix: no branch opened 15+ personal card accounts — Reg E new-account pages skipped")

    # Placed in order after the divider; each page after the one before it.
    lst = prs.slides._sldIdLst
    anchor = _sldid_of(prs, divider)
    for sl in made:
        el = _sldid_of(prs, sl)
        lst.remove(el)
        anchor.addnext(el)
        anchor = el
    if renumber:
        _renumber(prs)
    return made
