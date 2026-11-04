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


def add_matrix_detail_slides(dk, cfg, S, settings, *, section, fr=None, only=None):
    """The full prep-deck layout, one dense slide per account type, for the APPENDIX. -> notes."""
    notes = []
    mx_name = os.path.basename(str(cfg.matrix_path)) if cfg.matrix_path else "matrix validation extract"
    pull = ""
    if fr is not None and fr.loaded.file_date is not None:
        pull = f", extract pulled {fr.loaded.file_date:%Y-%m-%d}"
    types = [t for t in ("Personal", "Business") if t in dk.types] + [t for t in dk.types if t not in ("Personal", "Business")]
    for t in (only or types):
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
        sl = dk.content(f"Appendix: matrix detail, every factor and override — {t}",
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
            cy = ty + 0.42 + (i // 2) * 0.55
            chip = sl.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(cx), Inches(cy), Inches(cw2), Inches(0.50))
            chip.fill.solid()
            chip.fill.fore_color.rgb = brand.NAVY_RGB if on else brand.ROWALT_RGB
            chip.line.fill.background()
            shapes.shadow(chip)
            shapes.textbox(sl, cx, cy + 0.01, cw2, 0.27, lab, 12, brand.WHITE_RGB if on else brand.TICK_RGB, True,
                           PP_ALIGN.CENTER, brand.HEAD)
            shapes.textbox(sl, cx, cy + 0.27, cw2, 0.21, "On" if on else "Off", 11,
                           brand.PEACH_RGB if on else brand.TICK_RGB, False, PP_ALIGN.CENTER, brand.BODY)
        msg = ("Override enabled / pending flags and trend switches are not in the matrix validation extract; "
               "every override exported is listed.")
        if both:
            msg = "Deposit Regularity and Windfall both read as On in the extract; a matrix runs one of them. Check the matrix. " + msg
            notes.append(f"Matrix {t}: Deposit Regularity and Windfall trending both read as on in the extract (a matrix runs one of them).")
        shapes.textbox(sl, rx, ty + 0.42 + 1.12, rw, 0.42, msg, 11, brand.TICK_RGB, False, PP_ALIGN.LEFT, brand.BODY, MSO_ANCHOR.TOP)
        from . import client_slides as CS
        CS.say_first(sl, f"This is the full {t.lower()} matrix on one page, for reference; the next slides show it in plain terms.")
    return notes


# ═════════════════════ the readable matrix: two slides per account type ═════════════════════
def _num(f):
    """'-$500' -> -500.0, '$1,400' -> 1400.0."""
    s = str(f).strip()
    neg = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    try:
        v = float(re.sub(r"[^0-9.]", "", s))
    except ValueError:
        return 0.0
    return -v if neg else v


def _card_big(slide, x, y, w, h, value, label, hot=False):
    sh = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = brand.ORANGE_RGB if hot else brand.ROWALT_RGB
    sh.line.fill.background()
    shapes.shadow(sh)
    ink = brand.WHITE_RGB if hot else brand.NAVY_RGB
    shapes.textbox(slide, x, y + 0.06, w, h * 0.55, value, 26, ink, True, PP_ALIGN.CENTER, brand.HEAD, MSO_ANCHOR.MIDDLE)
    shapes.textbox(slide, x, y + h * 0.60, w, h * 0.34, label, 14, ink if hot else brand.TICK_RGB, False,
                   PP_ALIGN.CENTER, brand.BODY, MSO_ANCHOR.TOP)


def factor_summary(rows):
    """What a factor table says in three facts: where it starts, where it peaks, where it ends."""
    vals = [_num(f) for _, f in rows]
    peak_i = max(range(len(vals)), key=lambda i: (vals[i], -i))
    first_i = 0
    last_i = len(rows) - 1
    return {"first": (rows[first_i][0], rows[first_i][1]), "peak": (rows[peak_i][0], rows[peak_i][1]),
            "last": (rows[last_i][0], rows[last_i][1]), "negative": sum(1 for v in vals if v < 0), "bands": len(rows)}


def factor_caption(cat, rows):
    fs = factor_summary(rows)
    f0, p, l = fs["first"], fs["peak"], fs["last"]
    txt = f"Starts at {f0[1]} for {f0[0]}."
    if p[0] != f0[0]:
        txt += f" Reaches {p[1]} at {p[0]}."
    if l[0] != p[0] and l[1] != p[1]:
        txt += f" Ends at {l[1]} for {l[0]}."
    elif l[0] != p[0]:
        txt += f" Stays at {l[1]} through {l[0]}."
    return txt


def _factor_chart(dk, cat, rows, key, size=(3.95, 2.75)):
    """A bar per band, orange where the factor takes limit away, with the first, highest and last band named."""
    from . import r_common as R
    import numpy as np
    vals = [_num(f) for _, f in rows]
    fs = factor_summary(rows)
    fig, ax = R.new_fig(*size)
    cols = [R.ORANGE if v < 0 else R.NAVY for v in vals]
    ax.bar(range(len(vals)), vals, color=cols, width=0.72)
    ax.axhline(0, color=R.MUTED, linewidth=0.8)
    pk = max(range(len(vals)), key=lambda i: (vals[i], -i))
    marks = {0: rows[0], pk: rows[pk], len(vals) - 1: rows[-1]}
    span = (max(vals) - min(min(vals), 0)) or 1.0
    for i, (band, f) in sorted(marks.items()):
        v = vals[i]
        ax.annotate(f.replace("$", r"\$"), (i, v), xytext=(0, 4 if v >= 0 else -14), textcoords="offset points", ha="center",
                    fontsize=12, color=R.NAVY, fontweight="bold")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.set_ylim(min(min(vals), 0) - span * 0.18, max(vals) + span * 0.20)
    ax.set_xlabel(f"{len(vals)} bands, lowest to highest", fontsize=11, color=R.TICK)
    fig.tight_layout()
    return R.save(fig, dk.chart_dir, key)


def _src_line(dk, cfg, fr, t, s, code, mod, mx_name, pull, what):
    return (f"Source: {mx_name} (ILS matrix validation query 1822{pull}), client {cfg.client_id} {cfg.client_name}, "
            f"matrix {code} ({t}), matrix modified {mod}: {what}. Not in the extract: override enabled / pending flags, trend on/off "
            f"switches, the 'Default' limit flag. Trend on = grid present with a non-zero factor.")


def add_matrix_prep_slides(dk, cfg, S, settings, *, section, fr=None):
    """Per account type: (1) limits and how each scoring factor works, (2) overrides and trends On / Off. Both are
    legible at 12 pt and above. The dense prep-deck page, with every factor band, goes to the appendix. -> notes."""
    from . import client_slides as CS
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
        # ── 1: limits and scoring
        facs = factor_tables(S, t)
        src1 = _src_line(dk, cfg, fr, t, s, code, mod, mx_name, pull, "sections ACCOUNT TYPES AND MIN/MAX LIMITS, RANGES AND FACTORS")
        sl = dk.content(f"{t} matrix: limits and how the score is built",
                        f"{t} matrix ({code}), matrix validation query, modified {mod}. The score adds one factor per measure.",
                        section=section, source=src1)
        cards = _limits(s)
        cw = (CS.FULL_W - 4 * 0.14) / 5
        for i, (lab, val, hot) in enumerate(cards):
            _card_big(sl, LEFT + i * (cw + 0.14), 1.75, cw, 0.95, val, lab, hot)
        if facs:
            n = len(facs)
            gw = (CS.FULL_W - (n - 1) * 0.2) / n
            for i, (cat, rows) in enumerate(facs):
                x = LEFT + i * (gw + 0.2)
                head = {"Actual Monthly Deposits": "Monthly deposits ($)", "Actual Monthly Deposit Count": "Monthly deposit count"}.get(cat, cat)
                shapes.textbox(sl, x, 2.85, gw, 0.34, head, 15, brand.NAVY_RGB, True, PP_ALIGN.LEFT, brand.HEAD, MSO_ANCHOR.TOP)
                png = _factor_chart(dk, cat, rows, f"matrix_{t.lower()}_factor_{i + 1}", size=(gw, 2.55))
                shapes.fit_picture(sl, png, x, 3.2, gw, 2.55)
                shapes.textbox(sl, x, 5.80, gw, 0.85, factor_caption(cat, rows), 13, brand.TICK_RGB, False, PP_ALIGN.LEFT,
                               brand.BODY, MSO_ANCHOR.TOP)
            skipped = [c for c in MD.categories(S) if c not in [f[0] for f in facs]]
            if skipped:
                notes.append(f"Matrix {t}: factor table(s) with every band at $0 left off the slide: {', '.join(skipped)}.")
        else:
            shapes.textbox(sl, LEFT, 2.9, CS.FULL_W, 0.5, "No scoring factors with a non-zero value in the extract.", 16,
                           brand.TICK_RGB, False, PP_ALIGN.LEFT, brand.BODY)
        CS.say_first(sl, f"The {t.lower()} limit is the sum of these factors, held between the minimum and the maximum.")
        # ── 2: overrides and trends
        ovr = override_rows(MD.overrides_by_type(S, [t])[t])
        states = trend_states(S, t)
        both = check_trends(states, t)
        src2 = _src_line(dk, cfg, fr, t, s, code, mod, mx_name, pull, "sections OVERRIDES, TRENDS")
        s2 = dk.content(f"{t} matrix: overrides and trends",
                        f"{t} matrix ({code}), matrix validation query, modified {mod}. Overrides apply after the score is added up.",
                        section=section, source=src2)
        lw = 7.7
        _bar(s2, LEFT, 1.75, lw, "Overrides", "Applied after scoring")
        cap_rows = 11
        if ovr:
            shown = ovr[:cap_rows]
            rh = min(0.36, 4.0 / (len(shown) + 1))
            rows = [[o["n"], ("   " if o["sub"] else "") + o["text"], o["ret"], o["stop"]] for o in shown]
            _small_table(s2, LEFT, 2.20, [0.45, lw - 0.45 - 1.7 - 0.8, 1.7, 0.8], rows, ["#", "Override", "Returns", "Stop"], rh, 13,
                         [PP_ALIGN.CENTER, PP_ALIGN.LEFT, PP_ALIGN.LEFT, PP_ALIGN.CENTER])
            if len(ovr) > cap_rows:
                shapes.textbox(s2, LEFT, 2.25 + rh * (len(shown) + 1), lw, 0.3,
                               f"and {len(ovr) - cap_rows} more rows in the appendix matrix page", 12, brand.TICK_RGB, False, PP_ALIGN.LEFT, brand.BODY)
        else:
            shapes.textbox(s2, LEFT, 2.25, lw, 0.4, "No overrides in the extract.", 16, brand.TICK_RGB, False, PP_ALIGN.LEFT, brand.BODY)
        rx = LEFT + lw + 0.35
        rw = RIGHT - rx
        _bar(s2, rx, 1.75, rw, "Trends", "On or Off")
        chw = (rw - 0.14) / 2
        for i, (lab, on) in enumerate(states):
            cx = rx + (i % 2) * (chw + 0.14)
            cy = 2.25 + (i // 2) * 1.10
            chip = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(cx), Inches(cy), Inches(chw), Inches(0.98))
            chip.fill.solid()
            chip.fill.fore_color.rgb = brand.NAVY_RGB if on else brand.ROWALT_RGB
            chip.line.fill.background()
            shapes.shadow(chip)
            shapes.textbox(s2, cx, cy + 0.08, chw, 0.45, lab, 13, brand.WHITE_RGB if on else brand.TICK_RGB, True,
                           PP_ALIGN.CENTER, brand.HEAD, MSO_ANCHOR.MIDDLE)
            shapes.textbox(s2, cx, cy + 0.56, chw, 0.35, "On" if on else "Off", 16,
                           brand.PEACH_RGB if on else brand.TICK_RGB, True, PP_ALIGN.CENTER, brand.BODY, MSO_ANCHOR.TOP)
        msg = ("The extract lists each override's rule, the value it returns and the Stop flag; whether an override is enabled or "
               "pending, and the trend switches, are not in it.")
        if both:
            msg = "Deposit Regularity and Windfall both read as On; a matrix runs one of them, so check the matrix. " + msg
            notes.append(f"Matrix {t}: Deposit Regularity and Windfall trending both read as on in the extract (a matrix runs one of them).")
        shapes.textbox(s2, rx, 4.55, rw, 1.9, msg, 13, brand.TICK_RGB, False, PP_ALIGN.LEFT, brand.BODY, MSO_ANCHOR.TOP)
        CS.say_first(s2, f"After the score is added up, these rules can lower or remove the {t.lower()} limit; the trends are shown only as On or Off.")
    dk.defer(lambda: add_matrix_detail_slides(dk, cfg, S, settings, section="appendix", fr=fr))
    return notes
