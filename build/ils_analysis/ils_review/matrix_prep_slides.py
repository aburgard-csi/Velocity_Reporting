"""
The matrix slides: ONE slide per account type, Matrix Parameters and Overrides together.

NEW in the RPE port; replaces the analysis team's multi-page matrix section (settings, OD status
codes, override criteria, factor grids, trend grids, tiers, strategic refunds, ...). Aaron (2026-11-04):
"I like the matrix slides we do for the ILS prep decks better than what you produced here. Everything
should fit on 2 slides and be pulled from the matrix validation query."

The layout is the ILS prep deck's (`~/.claude/skills/ils-prep-deck/reference/build_deck.py`
`slide_parameters` + `slide_overrides`), drawn with RPE's brand.py / shapes.py:

  * a min / max limit block (the maximum in orange);
  * the scoring factor tables, an all-zero table left out;
  * the override list, each rule's sub-conditions attached to it;
  * the four trends as On / Off chips only (no grids, bands or thresholds; Deposit Regularity and
    Windfall are alternatives and never both on);
  * a note bar saying what the extract does not carry.

EVERY figure comes from the client's MATRIX VALIDATION extract (query 1822), never the matrix
parameters document, and the slide's speaker note names the file and pull date. What the extract does
not carry is stated on the slide, not invented:

  * an override's Enabled / Pending flag (the extract lists the overrides in force, with Stop Process);
  * a trend's on/off switch: the extract lists a trend's factor grid only when it is configured, so a
    trend is ON when its grid is present with a non-zero factor and OFF when it is absent or all
    zero (the prep deck's own rule: "off when its grid is greyed out or absent");
  * the prep deck's "Default" limit flag.

Type is 8-12 pt: the factor tables are the declared dense-table exception (STYLE.md section 9).
"""
from __future__ import annotations

import os
import re

import brand
import shapes
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches

from . import matrix_data as MD
from . import theme as T

LEFT, RIGHT = 0.50, 12.833
TOP = 1.70

# (display label, substrings that identify the repository name in the extract)
TRENDS = (("Deposit Regularity", ("regularity",)), ("OD Repayment", ("repayment",)),
          ("Windfall Deposit", ("windfall",)), ("Cash Flow", ("cash flow", "cashflow")))
FACTORS = (("Age of Account", "Age of Account"), ("Actual Monthly Deposits", "Monthly Dep $"),
           ("Actual Monthly Deposit Count", "# of Deposits"), ("Monthly Debit Declines", "Debit Declines"))


def _money(v):
    n = MD._num(v)
    return f"${n:,.0f}" if n is not None else str(v).strip()


def _factor(v):
    n = MD._num(v)
    if n is None:
        return str(v).strip()
    if n == 0:
        return "$0"
    return f"-${abs(n):,.0f}" if n < 0 else f"${n:,.0f}"


def _tidy_range(label):
    s = re.sub(r"\s+", " ", MD.clean_range(label)).strip()
    s = re.sub(r"\$\s+", "$", s)
    s = s.replace(" to ", " to ")
    return s


# ── overrides ───────────────────────────────────────────────────────────────
def _cond(text):
    """'[Age of Account] BETWEEN 31 AND 124' -> 'Age of Account 31-124'; '[Days OD] >= 22' -> 'Days OD >= 22'."""
    s = re.sub(r"\[ACCOUNTS\]\.", "", text, flags=re.I)
    s = re.sub(r"\[([^\]]+)\]", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"BETWEEN\s+(-?\d+)\s+AND\s+(-?\d+)", r"\1-\2", s, flags=re.I)
    s = s.replace("IntermediateODLimit", "Scored limit")
    return s


def _ret(v):
    s = str(v).strip()
    if s.endswith("%"):
        return s
    n = MD._num(s)
    return _money(s) if n is not None else s


def override_rows(rows):
    """Extract overrides -> display rows [{n, text, ret, stop, sub}], sub-conditions attached to their rule.

    A criterion `A AND B` is a rule A with sub-condition B; consecutive overrides sharing A are one parent
    rule with several sub-rows, each carrying its own return value (as the prep deck shows them)."""
    out, last_parent = [], None
    for k, r in enumerate(rows, 1):
        crit = str(r.get("Override Criteria", "")).strip()
        parts = re.split(r"\s+AND\s+(?=\[)", crit)
        stop = "Y" if MD.is_true(r.get("Stop Process")) else ""
        if len(parts) == 1:
            out.append({"n": str(k), "text": _cond(crit), "ret": _ret(r.get("Override Value", "")), "stop": stop, "sub": False})
            last_parent = None
            continue
        parent = _cond(parts[0])
        if parent != last_parent:
            out.append({"n": str(k), "text": parent, "ret": "", "stop": "", "sub": False})
            last_parent = parent
        out.append({"n": "", "text": "& " + _cond(" AND ".join(parts[1:])), "ret": _ret(r.get("Override Value", "")),
                    "stop": stop, "sub": True})
    return out


# ── factors, trends ─────────────────────────────────────────────────────────
def factor_tables(S, acct_type):
    """[(caption, [(band, factor), ...])] for the factor categories with a non-zero factor, in order."""
    out = []
    for cat in MD.categories(S):
        rows = []
        for g in MD.range_grid(S, cat, [acct_type]):
            if acct_type in g:
                rows.append((_tidy_range(g["label"]), _factor(g[acct_type])))
        if not rows or all(f in ("$0", "") for _, f in rows):
            continue                                   # an all-zero table tells the client nothing
        out.append((cat, rows))
    return out


def trend_states(S, acct_type):
    """[(label, on)] for the four trends. On = the trend's grid is in the extract with a non-zero factor."""
    reps = {}
    for r in MD.section(S, "TRENDS"):
        if r.get("Account Type") != acct_type:
            continue
        reps.setdefault((r.get("Repository Name") or "").lower(), []).append(MD._num(r.get("Factor")) or 0.0)
    out = []
    for label, keys in TRENDS:
        on = any(any(k in name for k in keys) and any(f != 0 for f in vals) for name, vals in reps.items())
        out.append((label, on))
    return out


def check_trends(states, where):
    on = {l for l, o in states if o}
    return ("Deposit Regularity" in on and "Windfall Deposit" in on)


# ── drawing ─────────────────────────────────────────────────────────────────
def _bar(slide, x, y, w, left, right=""):
    sh = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(0.36))
    sh.fill.solid()
    sh.fill.fore_color.rgb = brand.NAVY_RGB
    sh.line.fill.background()
    sh.shadow.inherit = False
    shapes.textbox(slide, x + 0.10, y, w * 0.62, 0.36, left, 14, brand.WHITE_RGB, True, PP_ALIGN.LEFT, brand.HEAD)
    if right:
        shapes.textbox(slide, x + w * 0.5, y, w * 0.5 - 0.10, 0.36, right, 12, brand.PEACH_RGB, True, PP_ALIGN.RIGHT, brand.HEAD)


def _card(slide, x, y, w, h, value, label, hot=False):
    sh = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = brand.ORANGE_RGB if hot else brand.ROWALT_RGB
    sh.line.fill.background()
    shapes.shadow(sh)
    ink = brand.WHITE_RGB if hot else brand.NAVY_RGB
    shapes.textbox(slide, x, y + 0.03, w, h * 0.55, value, 20, ink, True, PP_ALIGN.CENTER, brand.HEAD)
    shapes.textbox(slide, x, y + h * 0.56, w, h * 0.38, label, 12, ink if hot else brand.TICK_RGB, False,
                   PP_ALIGN.CENTER, brand.BODY, MSO_ANCHOR.TOP)


def _small_table(slide, x, y, colw, rows, heads, row_h, fs, aligns=None):
    data = [heads] + [list(r) for r in rows]
    gf = shapes.add_table(slide, x, y, sum(colw), row_h * len(data), data, colw, fs=fs)
    tb = gf.table
    for i in range(len(data)):
        tb.rows[i].height = int(row_h * 914400)
        for j in range(len(heads)):
            c = tb.cell(i, j)
            c.margin_top = c.margin_bottom = 0
            for p in c.text_frame.paragraphs:
                if aligns:
                    p.alignment = aligns[j]
                for r in p.runs:
                    r.font.size = T.Pt(fs)
    return gf


def _limits(settings_row):
    s = settings_row
    custom = str(s.get("Custom Inclusion Criteria", "")).strip()
    return [("Calculate Limits", MD.yesno(s.get("Calc?")), False),
            ("Min. Limit", _money(s.get("Min", "")), False),
            ("Max Limit", _money(s.get("Max", "")), True),
            ("Tiered Limits", MD.yesno(s.get("Tiered Limits")), False),
            ("Custom Inclusion", custom if MD._live(custom) else "None", False)]


def add_matrix_prep_slides(dk, cfg, S, settings, *, section, fr=None):
    """Two slides, Personal then Business (the extract's own account types otherwise). -> notes."""
    notes = []
    mx_name = os.path.basename(str(cfg.matrix_path)) if cfg.matrix_path else "matrix validation extract"
    pull = ""
    if fr is not None and fr.loaded.file_date is not None:
        pull = f", extract pulled {fr.loaded.file_date:%Y-%m-%d}"
    types = [t for t in ("Personal", "Business") if t in dk.types] + [t for t in dk.types if t not in ("Personal", "Business")]
    for t in types:
        s = settings.get(t, {})
        code = dk.codes.get(t, "")
        mod = str(s.get("Matrix Modified Date", ""))[:10]
        states = trend_states(S, t)
        both = check_trends(states, t)
        ovr = override_rows(MD.overrides_by_type(S, [t])[t])
        facs = factor_tables(S, t)
        src = (f"Source: {mx_name} (ILS matrix validation query 1822{pull}), client {cfg.client_id} {cfg.client_name}, "
               f"matrix {code} ({t}), matrix modified {mod}: sections ACCOUNT TYPES AND MIN/MAX LIMITS, RANGES AND FACTORS, "
               f"OVERRIDES, TRENDS. Not in the extract: override enabled / pending flags, trend on/off switches, the 'Default' limit flag. "
               f"Trend on = grid present with a non-zero factor.")
        sl = dk.content(f"Matrix Parameters and Overrides — {t}",
                        f"{t} matrix ({code}), matrix validation query, modified {mod}.", section=section, source=src)
        # ── limits
        _bar(sl, LEFT, TOP, 7.75, "Matrix Minimum / Maximum Limits", "Prior to overrides")
        cards = _limits(s)
        cw = (7.75 - 4 * 0.12) / 5
        for i, (lab, val, hot) in enumerate(cards):
            _card(sl, LEFT + i * (cw + 0.12), 2.12, cw, 0.66, val, lab, hot)
        # ── factors
        _bar(sl, LEFT, 2.88, 7.75, "Scoring Factors", "OD limit contribution by band")
        top = 3.30
        if facs:
            widths = {"Age of Account": [1.55, 0.95], "Actual Monthly Deposits": [1.55, 0.95], "Actual Monthly Deposit Count": [1.05, 0.9]}
            tot = sum(sum(widths.get(c, [1.4, 0.9])) for c, _ in facs) + 0.12 * (len(facs) - 1)
            scale = 7.75 / tot
            x = LEFT
            tallest = max(len(r) for _, r in facs) + 1
            row_h = min(0.2, (6.70 - top) / tallest)
            for cat, rows in facs:
                cwid = [w * scale for w in widths.get(cat, [1.4, 0.9])]
                head = {"Actual Monthly Deposits": "Deposits $", "Actual Monthly Deposit Count": "Deposits #"}.get(cat, cat)
                _small_table(sl, x, top, cwid, rows, [head, "Factor"], row_h, 8,
                             [PP_ALIGN.LEFT, PP_ALIGN.RIGHT])
                x += sum(cwid) + 0.12 * scale
            skipped = [c for c in MD.categories(S) if c not in [f[0] for f in facs]]
            if skipped:
                notes.append(f"Matrix {t}: factor table(s) with every band at $0 left off the slide: {', '.join(skipped)}.")
        else:
            shapes.textbox(sl, LEFT, top, 7.75, 0.5, "No scoring factors with a non-zero value in the extract.", 14,
                           brand.TICK_RGB, False, PP_ALIGN.LEFT, brand.BODY)
        # ── overrides
        rx, rw = 8.50, RIGHT - 8.50
        _bar(sl, rx, TOP, rw, "Overrides", "Applied after scoring")
        if ovr:
            n = len(ovr) + 1
            rh = min(0.30, 2.55 / n)
            fs = 12 if rh >= 0.28 else (11 if rh >= 0.25 else 10)
            rows = [[o["n"], ("   " if o["sub"] else "") + o["text"], o["ret"], o["stop"]] for o in ovr]
            _small_table(sl, rx, 2.12, [0.32, rw - 0.32 - 0.95 - 0.5, 0.95, 0.5], rows, ["#", "Override", "Returns", "Stop"], rh, fs,
                         [PP_ALIGN.CENTER, PP_ALIGN.LEFT, PP_ALIGN.LEFT, PP_ALIGN.CENTER])
            ob = 2.12 + rh * n
        else:
            shapes.textbox(sl, rx, 2.12, rw, 0.4, "No overrides in the extract.", 14, brand.TICK_RGB, False, PP_ALIGN.LEFT, brand.BODY)
            ob = 2.55
        # ── trends: On / Off chips only
        ty = max(ob + 0.08, 4.15)
        _bar(sl, rx, ty, rw, "Trend Settings", "On or Off only")
        cw2 = (rw - 0.12) / 2
        for i, (lab, on) in enumerate(states):
            cx = rx + (i % 2) * (cw2 + 0.12)
            cy = ty + 0.44 + (i // 2) * 0.66
            chip = sl.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(cx), Inches(cy), Inches(cw2), Inches(0.58))
            chip.fill.solid()
            chip.fill.fore_color.rgb = brand.NAVY_RGB if on else brand.ROWALT_RGB
            chip.line.fill.background()
            shapes.shadow(chip)
            shapes.textbox(sl, cx, cy + 0.02, cw2, 0.30, lab, 13, brand.WHITE_RGB if on else brand.TICK_RGB, True,
                           PP_ALIGN.CENTER, brand.HEAD)
            shapes.textbox(sl, cx, cy + 0.32, cw2, 0.24, "On" if on else "Off", 12,
                           brand.PEACH_RGB if on else brand.TICK_RGB, False, PP_ALIGN.CENTER, brand.BODY)
        msg = ("Not in the matrix validation extract: override enabled or pending flags, trend switches. "
               "Every override exported is listed; a trend is On when its grid is in the extract.")
        if both:
            msg = "Deposit Regularity and Windfall both read as On in the extract; a matrix runs one of them. Check the matrix. " + msg
            notes.append(f"Matrix {t}: Deposit Regularity and Windfall trending both read as on in the extract (a matrix runs one of them).")
        shapes.textbox(sl, rx, ty + 0.44 + 1.34, rw, 0.55, msg, 11, brand.TICK_RGB, False, PP_ALIGN.LEFT, brand.BODY, MSO_ANCHOR.TOP)
    return notes
