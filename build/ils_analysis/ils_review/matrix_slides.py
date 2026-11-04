"""
ILS Matrix Validation slides, laid out natively for the 20 x 11.25 in canvas.

The content is the same set the Matrix Deck Generator produced — account-type
settings, OD status codes, override criteria, factor grids, trending triggers
and grids, tiers, and the optional components — but the geometry is written for
the real template canvas rather than scaled up from a 10 x 5.625 in design.

What the extra room buys, beyond legibility: the OD status-code table shows all
its rows instead of the first 12, factor grids no longer shrink to 5.5 pt in
wide trend matrices, and the tier narrative sits beside its table instead of
underneath it.
"""
from __future__ import annotations

from pptx.enum.text import PP_ALIGN

from . import matrix_data as MD
from . import theme as T

# Table geometry inside the content band.
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


def _cap(rows, y, *, per=0.235):
    """(rows that fit, number left out). A table cannot shrink without limit on the RPE canvas, so a long
    list stops where the content band ends and the slide says how many rows the matrix export holds."""
    k = int((T.REAL_BOTTOM - 0.10 - T.Y(y) - 0.45) / per)
    k = max(k, 6)
    return (rows[:k], len(rows) - k) if len(rows) > k else (rows, 0)


def _tbl(dk, slide, y, widths, n_rows, *, row_h=None, head_h=HEAD_H, x=X, w=W):
    rh = row_h if row_h is not None else _fits(n_rows, y, head_h=head_h)
    return dk.table(slide, x, y, w, widths, n_rows, row_h=rh, header_h=head_h)


def _fs(row_h, cap=15.0):
    """Font size that stays inside a given row height."""
    return max(8.0, min(cap, row_h * 30))


# ═════════════════════════════ section cover ════════════════════════════════
def slide_cover(dk, settings, *, section):
    parts = []
    for t in dk.types:
        s = settings.get(t, {})
        code = dk.codes.get(t, "")
        mx = MD._num(s.get("Max"))
        label = f"{t} ({code}" + (f", max ${mx:,.0f})" if mx is not None else ")")
        parts.append(label)
    n = len(dk.types)
    dk.cover(dk.client, "ILS Overdraft Matrix Validation",
             f"{n} account-type matri{'x' if n == 1 else 'ces'}:  " + "  •  ".join(parts)
             + f"\nConfiguration snapshot as of {dk.date_str}",
             section=section)


# ═════════════════════════════ settings + codes ═════════════════════════════
def slide_settings(dk, S, settings, *, section):
    slide = dk.content("Account-Type Settings & OD Status Codes",
                       "Matrix limits, tiering and eligibility for the configured account types",
                       section=section)
    y = T.CONTENT_TOP
    T.band_label(slide, X, y, W, "  ACCOUNT-TYPE MATRIX CONFIGURATION")
    y += 0.50

    cols = ["Account Type", "Matrix\nCode", "Calc?", "Min", "Max", "Enabled?",
            "Tiered\nLimits", "Matrix Modified", "Custom Inclusion Criteria"]
    widths = [2.7, 1.1, 1.0, 1.1, 1.25, 1.3, 1.2, 2.3, 6.6]
    tbl = _tbl(dk, slide, y, widths, len(dk.types) + 1, row_h=0.46)
    for c, h in enumerate(cols):
        T.head_cell(tbl.cell(0, c), h, 14,
                    align=PP_ALIGN.LEFT if c in (0, 8) else PP_ALIGN.CENTER)
    for ri, t in enumerate(dk.types, 1):
        r = settings.get(t, {})
        tc = dk.colors.get(t, T.NAVY)
        mx = MD._num(r.get("Max"))
        mn = MD._num(r.get("Min"))
        T.cell(tbl.cell(ri, 0), t, 15, bold=True, color=T.WHITE, bg=tc, align=PP_ALIGN.LEFT)
        T.cell(tbl.cell(ri, 1), dk.codes.get(t, ""), 15, bold=True, color=T.WHITE, bg=tc)
        T.cell(tbl.cell(ri, 2), r.get("Calc?", ""), 15)
        T.cell(tbl.cell(ri, 3), f"${mn:,.0f}" if mn is not None else r.get("Min", ""), 15)
        T.cell(tbl.cell(ri, 4), f"${mx:,.0f}" if mx is not None else r.get("Max", ""), 15,
               bold=True, color=T.GREEN)
        T.cell(tbl.cell(ri, 5), r.get("Enabled?", ""), 15, color=T.GREEN)
        T.cell(tbl.cell(ri, 6), r.get("Tiered Limits", ""), 15, color=T.GREEN)
        T.cell(tbl.cell(ri, 7), str(r.get("Matrix Modified Date", ""))[:10], 14)
        crit = str(r.get("Custom Inclusion Criteria", "")).strip()
        T.cell(tbl.cell(ri, 8), crit if MD._live(crit) else "—", 12.5, align=PP_ALIGN.LEFT)

    y += 0.46 * len(dk.types) + HEAD_H + 0.45

    od = MD.section(S, "OD STATUS CODE MAPPING")
    if od:
        od_all = od
        od, od_hidden = _cap(od, y + 0.50)
        T.band_label(slide, X, y, W, f"  OD STATUS CODE MAPPING ({len(od_all)}; {len(od)} shown)" if od_hidden
                     else "  OD STATUS CODE MAPPING")
        y += 0.50
        cols2 = ["Status Code", "Description", "ILS Calc", "Can Overdraft",
                 dk.term("MRPC Elig."), dk.term("MRPC Loan Elig.")]
        widths2 = [2.5, 7.2, 2.2, 2.6, 2.2, 2.4]
        rh = _fits(len(od) + 1, y)
        tbl2 = _tbl(dk, slide, y, widths2, len(od) + 1, row_h=rh)
        fs = _fs(rh, 14)
        for c, h in enumerate(cols2):
            T.head_cell(tbl2.cell(0, c), h, 14,
                        align=PP_ALIGN.LEFT if c in (0, 1) else PP_ALIGN.CENTER)
        for ri, r in enumerate(od, 1):
            bg = T.zebra(ri - 1)
            can_od = MD.is_true(r.get("CAN_OVERDRAFT"))
            calc = MD.is_true(r.get("ILS_CALC"))
            T.cell(tbl2.cell(ri, 0), r.get("STATUS_CODE", "") or "—", fs, bg=bg,
                   align=PP_ALIGN.LEFT, bold=True)
            T.cell(tbl2.cell(ri, 1), r.get("DESCRIPTION", ""), fs, bg=bg, align=PP_ALIGN.LEFT)
            T.cell(tbl2.cell(ri, 2), MD.yesno(calc), fs, bg=bg,
                   color=T.GREEN if calc else T.GRAY)
            T.cell(tbl2.cell(ri, 3), MD.yesno(can_od), fs, bg=bg, bold=True,
                   color=T.GREEN if can_od else T.RED)
            for ci, key in ((4, "MRPC_Eligible"), (5, "MRPC_Loan_Eligible")):
                v = MD.is_true(r.get(key))
                T.cell(tbl2.cell(ri, ci), MD.yesno(v), fs, bg=bg,
                       color=T.GREEN if v else T.GRAY)
    return slide


# ═════════════════════════════ overrides ════════════════════════════════════
def slide_overrides(dk, S, *, section):
    slide = dk.content("Override Criteria — " + " · ".join(dk.types),
                       "Rules applied to the scored intermediate limit, in order. Values may be "
                       "points, percentages, or absolute caps.",
                       section=section)
    ov = MD.overrides_by_type(S, dk.types)
    n = max(1, len(dk.types))
    gap = 0.35
    cw = (W - gap * (n - 1)) / n
    y = T.CONTENT_TOP
    for k, t in enumerate(dk.types):
        x = X + k * (cw + gap)
        tc = dk.colors.get(t, T.NAVY)
        T.band_label(slide, x, y, cw, f"  {t.upper()} ({dk.codes.get(t, '')})", bg=tc)
        rows = ov.get(t, [])
        if not rows:
            T.note(slide, x + 0.05, y + 0.6, cw - 0.1,
                   "No override rules configured for this account type.")
            continue
        rh = _fits(len(rows) + 1, y + 0.50)
        fs = _fs(rh, 14)
        tbl = dk.table(slide, x, y + 0.50, cw,
                       [cw * 0.70, cw * 0.20, cw * 0.10], len(rows) + 1,
                       row_h=rh, header_h=HEAD_H)
        for c, h in enumerate(["Override Criteria", "Value", "Stop"]):
            T.head_cell(tbl.cell(0, c), h, 14, bg=tc,
                        align=PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER)
        for ri, r in enumerate(rows, 1):
            bg = T.zebra(ri - 1)
            crit = str(r.get("Override Criteria", "")).replace("[", "").replace("]", "")
            val = str(r.get("Override Value", "")).replace("ACCOUNTS.", "")
            T.cell(tbl.cell(ri, 0), dk.term(crit), fs, bg=bg, align=PP_ALIGN.LEFT)
            # fmt_factor also normalises the export's "-0" to "0"
            T.cell(tbl.cell(ri, 1), MD.fmt_factor(val), fs, bg=bg, bold=True,
                   color=MD.factor_color(val))
            T.cell(tbl.cell(ri, 2), "Y" if MD.is_true(r.get("Stop Process")) else "",
                   fs, bg=bg, bold=True, color=T.RED)
    return slide


# ═════════════════════════════ factor grids ═════════════════════════════════
def _category_grid(dk, slide, S, category, y, *, height_rows=None):
    """The N-type factor grid for one category. Returns the data rendered."""
    data = MD.range_grid(S, category, dk.types)
    if not data:
        return data
    n = max(1, len(dk.types))
    type_w = min(3.2, (W - 5.0) / n)
    label_w = W - type_w * n
    rows = height_rows or len(data)
    rh = _fits(rows + 1, y)
    fs = _fs(rh, 15)
    tbl = dk.table(slide, X, y, W, [label_w] + [type_w] * n, len(data) + 1,
                   row_h=rh, header_h=HEAD_H)
    T.head_cell(tbl.cell(0, 0), category, 15, align=PP_ALIGN.LEFT)
    for ci, t in enumerate(dk.types, 1):
        T.head_cell(tbl.cell(0, ci), f"{t} ({dk.codes.get(t, '')})", 14,
                    bg=dk.colors.get(t, T.NAVY))
    for ri, row in enumerate(data, 1):
        bg = T.zebra(ri - 1)
        T.cell(tbl.cell(ri, 0), row["label"], fs, bg=bg, align=PP_ALIGN.LEFT)
        for ci, t in enumerate(dk.types, 1):
            v = row.get(t, "—")
            T.cell(tbl.cell(ri, ci), MD.fmt_factor(v), fs, bg=bg, bold=True,
                   color=MD.factor_color(v))
    return data


def slide_category(dk, S, category, title, subtitle, *, section, note=None):
    slide = dk.content(title, subtitle, section=section)
    data = MD.range_grid(S, category, dk.types)
    y = T.CONTENT_TOP
    T.band_label(slide, X, y, W,
                 f"  {category.upper()} — POINTS BY RANGE ({len(data)} ranges)")
    _category_grid(dk, slide, S, category, y + 0.50)

    zt = MD.zero_types(data, dk.types)
    auto = ""
    if zt and len(zt) < len(dk.types):
        verb = "carries" if len(zt) == 1 else "carry"
        auto = (f"{', '.join(zt)} {verb} 0 points across all {category.lower()} ranges "
                f"— not scored on this variable.")
    text = " ".join(x for x in (note, auto) if x)
    if text:
        T.footnote(slide, text)
    return slide


def slide_age_declines(dk, S, *, section):
    slide = dk.content("Matrix Variables — Age of Account & Monthly Debit Declines",
                       "Points added to or subtracted from the scored limit by account age",
                       section=section)
    age = MD.range_grid(S, "Age of Account", dk.types)
    y = T.CONTENT_TOP
    T.band_label(slide, X, y, W,
                 f"  AGE OF ACCOUNT — POINTS BY AGE ({len(age)} ranges)")

    notes = []
    dd = MD.range_grid(S, "Monthly Debit Declines", dk.types)
    if dd:
        if MD.all_zero(dd, dk.types):
            notes.append("Monthly Debit Declines: every range factor is 0 for every account "
                         "type — debit-decline scoring is configured but inactive.")
        else:
            nz = [t for t in dk.types if t not in MD.zero_types(dd, dk.types)]
            notes.append(f"Monthly Debit Declines: active scoring for {', '.join(nz)}.")
    zt_age = MD.zero_types(age, dk.types)
    if zt_age:
        verb = "carries" if len(zt_age) == 1 else "carry"
        notes.append(f"{', '.join(zt_age)} {verb} 0 points for Age of Account.")

    note_h = 0.90 if notes else 0.0
    rows_budget = None
    if notes:
        # leave room for the note block under the table
        avail = T.CONTENT_BOTTOM - (y + 0.50) - note_h
        rows_budget = max(4, int((avail - HEAD_H) / 0.30))
    _category_grid(dk, slide, S, "Age of Account", y + 0.50,
                   height_rows=rows_budget)
    if notes:
        T.bullets(slide, X, T.CONTENT_BOTTOM - note_h + 0.10, W, note_h, notes, 15,
                  bullet_color=T.MUTED, color=T.SUBTLE)
    return slide


# ═════════════════════════════ trending ═════════════════════════════════════
def slide_trend_triggers(dk, S, oned_repos, *, section):
    """Trigger thresholds per account type x repository, plus 1-D factor tables."""
    slide = dk.content("Trending Adjustments — Triggers & Repayment",
                       "Trigger minimums that arm each trend. Negative factors reduce the "
                       "scored limit.",
                       section=section)
    rows = MD.trend_trigger_rows(S, dk.types)
    y = T.CONTENT_TOP

    fields = [("dep_cnt", "Min Dep\nCount"), ("dep_amt", "Min Dep\nAmount"),
              ("od_cnt", "Min OD\nCount")]
    fields = [(k, h) for k, h in fields if any(r[k] != "—" for r in rows)]
    cols = ["Account Type", "Repository"] + [h for _, h in fields]
    widths = [2.8, 5.4] + [2.0] * len(fields)
    table_w = min(W, sum(widths) * 1.0)

    T.band_label(slide, X, y, table_w, "  TRENDING TRIGGER THRESHOLDS")
    y += 0.50
    if rows:
        rh = min(0.40, max(0.26, (T.CONTENT_H * 0.45 - HEAD_H) / max(1, len(rows))))
        tbl = dk.table(slide, X, y, table_w, widths, len(rows) + 1,
                       row_h=rh, header_h=HEAD_H)
        fs = _fs(rh, 15)
        for c, h in enumerate(cols):
            T.head_cell(tbl.cell(0, c), h, 14,
                        align=PP_ALIGN.LEFT if c < 2 else PP_ALIGN.CENTER)
        for ri, r in enumerate(rows, 1):
            bg = T.zebra(ri - 1)
            T.cell(tbl.cell(ri, 0), r["type"], fs, bold=True, color=T.WHITE,
                   bg=dk.colors.get(r["type"], T.NAVY), align=PP_ALIGN.LEFT)
            T.cell(tbl.cell(ri, 1), r["repo"], fs, bg=bg, align=PP_ALIGN.LEFT)
            for ci, (k, _) in enumerate(fields, 2):
                val = r[k]
                if k == "dep_amt" and val != "—":
                    val = f"${val}"
                T.cell(tbl.cell(ri, ci), val, fs, bg=bg)
        y += HEAD_H + rh * len(rows) + 0.55
    else:
        T.note(slide, X, y, W, "No trending repositories configured.")
        y += 0.5

    # 1-D repositories (usually OD Repayment) as compact factor tables, side by side
    side_x = X
    side_w = 6.0
    for repo in oned_repos:
        st = MD.trend_structure(S, repo)
        if not st["dims"]:
            continue
        cap, labels = st["dims"][0]
        if side_x + side_w > X + W:
            break
        T.band_label(slide, side_x, y, side_w, f"  {repo.upper()} — FACTORS")
        rh = _fits(len(labels) + 1, y + 0.50)
        tbl = dk.table(slide, side_x, y + 0.50, side_w, [4.2, 1.8], len(labels) + 1,
                       row_h=rh, header_h=HEAD_H)
        fs = _fs(rh, 14)
        T.head_cell(tbl.cell(0, 0), cap, 14, align=PP_ALIGN.LEFT)
        T.head_cell(tbl.cell(0, 1), "Factor", 14)
        for ri, lb in enumerate(labels, 1):
            bg = T.zebra(ri - 1)
            f = st["factors"].get((lb,), "—")
            T.cell(tbl.cell(ri, 0), lb, fs, bg=bg, align=PP_ALIGN.LEFT)
            T.cell(tbl.cell(ri, 1), MD.fmt_factor(f), fs, bg=bg, bold=True,
                   color=MD.factor_color(f))
        side_x += side_w + 0.45
    return slide


def slide_trend_grid(dk, S, repo, st, *, section):
    """One 2-D trend factor grid."""
    shared = ("shared across account types" if st["shared"]
              else "differs by account type — showing the first type")
    slide = dk.content(f"Trending — {repo}",
                       f"Factor grid ({shared}). Negative factors reduce the scored limit.",
                       section=section)
    (capA, labsA), (capB, labsB) = st["dims"][0], st["dims"][1]
    # orient so the dimension with more buckets runs down the rows
    if len(labsA) >= len(labsB):
        row_cap, rows_l, col_cap, cols_l, swap = capA, labsA, capB, labsB, False
    else:
        row_cap, rows_l, col_cap, cols_l, swap = capB, labsB, capA, labsA, True

    def fac(rl, cl):
        return st["factors"].get((cl, rl) if swap else (rl, cl), "—")

    def short(c, n):
        c = str(c).replace(" / ", " ÷ ")
        return c if len(c) <= n else c[:n - 1] + "…"

    y = T.CONTENT_TOP
    T.band_label(slide, X, y, W,
                 f"  ROWS: {short(row_cap, 70)}     ·     COLUMNS: {short(col_cap, 55)}")
    y += 0.50

    label_w = 3.4
    cw = (W - label_w) / max(1, len(cols_l))
    n_rows = len(rows_l) + 1
    rh = _fits(n_rows, y)
    fs = _fs(rh, 12 if len(cols_l) <= 9 else (11 if len(cols_l) <= 12 else 11.5))
    tbl = dk.table(slide, X, y, W, [label_w] + [cw] * len(cols_l), n_rows,
                   row_h=rh, header_h=HEAD_H)
    T.head_cell(tbl.cell(0, 0), short(row_cap, 46), fs, align=PP_ALIGN.LEFT)
    for c, cl in enumerate(cols_l, 1):
        T.head_cell(tbl.cell(0, c), cl, fs)
    for r, rl in enumerate(rows_l, 1):
        bg = T.zebra(r - 1)
        T.cell(tbl.cell(r, 0), rl, fs, bold=True, bg=bg, align=PP_ALIGN.LEFT)
        for c, cl in enumerate(cols_l, 1):
            v = fac(rl, cl)
            T.cell(tbl.cell(r, c), MD.fmt_factor(v), fs, bold=True, bg=bg,
                   color=MD.factor_color(v))
    if st.get("truncated"):
        T.footnote(slide,
                   "Note: some range labels were reconstructed positionally because the "
                   "source export truncated the long rule text. Factor values are exact — "
                   "they sit in the last column, which is never truncated.")
    return slide


# ═════════════════════════════ tiers ════════════════════════════════════════
def slide_tiers(dk, S, settings, *, section):
    slide = dk.content("Tiered Limits & Rounding",
                       "The scored limit is snapped to a tier ceiling before override rules run",
                       section=section)
    ts = MD.tier_summary(S)
    owners = [t for t in dk.types if t in ts]
    y = T.CONTENT_TOP

    T.band_label(slide, X, y, 11.4, "  TIER TABLE SUMMARY BY MATRIX CODE")
    cols = ["Matrix", "Code", "# Tiers", "Score Bands", "Score Range", "Max Limit"]
    widths = [2.6, 1.2, 1.5, 2.4, 2.4, 1.9]
    if owners:
        tbl = dk.table(slide, X, y + 0.50, 11.4, widths, len(owners) + 1,
                       row_h=0.46, header_h=HEAD_H)
        for c, h in enumerate(cols):
            T.head_cell(tbl.cell(0, c), h, 15, align=PP_ALIGN.LEFT if c == 0
                        else PP_ALIGN.CENTER)
        for ri, t in enumerate(owners, 1):
            d = ts[t]
            tc = dk.colors.get(t, T.NAVY)
            band = (f"${d['band_w']:,.2f} uniform" if d["band_w"] is not None else "Variable")
            T.cell(tbl.cell(ri, 0), t, 15, bold=True, color=T.WHITE, bg=tc, align=PP_ALIGN.LEFT)
            T.cell(tbl.cell(ri, 1), dk.codes.get(t, d["code"]), 15, bold=True,
                   color=T.WHITE, bg=tc)
            T.cell(tbl.cell(ri, 2), f"{d['n']}", 15)
            T.cell(tbl.cell(ri, 3), band, 15)
            T.cell(tbl.cell(ri, 4), f"${d['score_min']:,.0f} – ${d['score_max']:,.0f}", 15)
            T.cell(tbl.cell(ri, 5), f"${d['max_limit']:,.0f}", 16, bold=True, color=T.GREEN)
    else:
        T.note(slide, X, y + 0.50, 11.4, "No tier table found in this export.")

    # narrative beside the table
    nx = X + 11.4 + 0.5
    nw = T.SLIDE_W - nx - X
    T.band_label(slide, nx, y, nw, "  HOW TIERING WORKS")
    lines = ["Each account's scored intermediate limit is mapped up to the nearest tier "
             "ceiling; that tier's Limit Value becomes the granted limit, before override "
             "rules run."]
    for t in owners:
        d = ts[t]
        band = (f"uniform ${d['band_w']:,.2f} score bands" if d["band_w"] is not None
                else "variable-width score bands")
        lines.append(f"{t} (Matrix {dk.codes.get(t, d['code'])}) uses {d['n']} tiers "
                     f"({band}), scores ${d['score_min']:,.0f}–${d['score_max']:,.0f}, "
                     f"max limit ${d['max_limit']:,.0f}.")
    for t in dk.types:
        if t in ts:
            continue
        code = dk.codes.get(t, "")
        owner = next((o for o in owners if dk.codes.get(o, ts[o]["code"]) == code), None)
        mx = MD._num(settings.get(t, {}).get("Max"))
        cap = f"${mx:,.0f}" if mx is not None else "its account-type maximum"
        if owner:
            lines.append(f"{t} shares the {owner} (Matrix {code}) tier table; its granted "
                         f"limit is capped at {cap}.")
    T.bullets(slide, nx + 0.05, y + 0.62, nw - 0.1, T.CONTENT_BOTTOM - y - 0.7, lines, 15)
    return slide


# ═════════════════════════════ optional sections ════════════════════════════
def slide_limit_notification(dk, settings, *, section):
    slide = dk.content("Limit Notification Settings",
                       "How and when members are notified of a limit change",
                       section=section)
    y = T.CONTENT_TOP
    T.band_label(slide, X, y, W, "  LIMIT NOTIFICATION BY ACCOUNT TYPE")
    cols = ["Account Type"] + [label for _, label in MD.LN_FIELDS]
    widths = [3.0] + [(W - 3.0) / len(MD.LN_FIELDS)] * len(MD.LN_FIELDS)
    tbl = dk.table(slide, X, y + 0.50, W, widths, len(dk.types) + 1,
                   row_h=0.46, header_h=HEAD_H)
    for c, h in enumerate(cols):
        T.head_cell(tbl.cell(0, c), h, 14, align=PP_ALIGN.LEFT if c == 0
                    else PP_ALIGN.CENTER)
    for ri, t in enumerate(dk.types, 1):
        r = settings.get(t, {})
        T.cell(tbl.cell(ri, 0), t, 15, bold=True, color=T.WHITE,
               bg=dk.colors.get(t, T.NAVY), align=PP_ALIGN.LEFT)
        for ci, (key, _) in enumerate(MD.LN_FIELDS, 1):
            col = MD.find_col(r, key) or key
            v = str(r.get(col, "")).strip()
            T.cell(tbl.cell(ri, ci), v if MD._live(v) else "—", 14)
    return slide


def slide_cashplease(dk, settings, *, section):
    label = "CashPlease" if dk.relabel_mrpc else "MRPC / CashPlease"
    slide = dk.content(f"{label} Settings",
                       "Small-dollar loan eligibility and maximums by account type",
                       section=section)
    y = T.CONTENT_TOP
    T.band_label(slide, X, y, 12.0, f"  {label.upper()} CONFIGURATION")
    keys = [("Max %", "Max %"), ("Max $", "Max $"), ("Elig", "Eligible")]
    cols = ["Account Type"] + [h for _, h in keys]
    widths = [3.4, 2.9, 2.9, 2.8]
    tbl = dk.table(slide, X, y + 0.50, 12.0, widths, len(dk.types) + 1,
                   row_h=0.46, header_h=HEAD_H)
    for c, h in enumerate(cols):
        T.head_cell(tbl.cell(0, c), h, 15, align=PP_ALIGN.LEFT if c == 0
                    else PP_ALIGN.CENTER)
    for ri, t in enumerate(dk.types, 1):
        r = settings.get(t, {})
        T.cell(tbl.cell(ri, 0), t, 15, bold=True, color=T.WHITE,
               bg=dk.colors.get(t, T.NAVY), align=PP_ALIGN.LEFT)
        for ci, (needle, _) in enumerate(keys, 1):
            col = (MD.find_col(r, f"CashPlease {needle}") or
                   MD.find_col(r, f"MRPC {needle}"))
            v = str(r.get(col, "")).strip() if col else ""
            T.cell(tbl.cell(ri, ci), v if MD._live(v) else "—", 15)
    return slide


def slides_comm_strategies(dk, S, *, section, show_all=False):
    rows = MD.section(S, "COMMUNICATION STRATEGIES")
    active = MD.active_comm_strategies(S)
    if not rows:
        return []
    out = []
    for page_rows, page_no, pages in MD.paginate(active or rows, MD.ROWS_PER_SLIDE, show_all):
        sub = f"{len(active)} of {len(rows)} strategies active — member outreach cadence"
        if pages > 1:
            sub += f"  ·  page {page_no} of {pages}"
        slide = dk.content("Communication Strategies", sub, section=section)
        y = T.CONTENT_TOP
        T.band_label(slide, X, y, W, "  ACTIVE STRATEGIES")
        cols = ["Strategy", "Group", "Type", "Priority", "Repeat", "Remove",
                "Clear on\npositive bal."]
        widths = [7.2, 3.2, 1.9, 1.8, 1.6, 1.7, 2.4]
        rh = _fits(len(page_rows) + 1, y + 0.50)
        tbl = dk.table(slide, X, y + 0.50, W, widths, len(page_rows) + 1,
                       row_h=rh, header_h=HEAD_H)
        fs = _fs(rh, 14)
        for c, h in enumerate(cols):
            T.head_cell(tbl.cell(0, c), h, 14, align=PP_ALIGN.LEFT if c == 0
                        else PP_ALIGN.CENTER)
        for ri, r in enumerate(page_rows, 1):
            bg = T.zebra(ri - 1)
            rop = MD.is_true(r.get("RemoveOnPositiveBalance"))
            T.cell(tbl.cell(ri, 0), dk.term(r.get("STRATEGY_NAME", "")), fs, bg=bg,
                   align=PP_ALIGN.LEFT)
            T.cell(tbl.cell(ri, 1), r.get("STRATEGY_GROUP", "") or "—", fs, bg=bg)
            T.cell(tbl.cell(ri, 2), r.get("COMMUNICATION_TYPE_ID", "") or "—", fs, bg=bg)
            T.cell(tbl.cell(ri, 3), r.get("STRATEGY_PRIORITY", "") or "—", fs, bg=bg)
            T.cell(tbl.cell(ri, 4), r.get("THRESHOLD_REPEAT", "") or "—", fs, bg=bg)
            T.cell(tbl.cell(ri, 5), r.get("THRESHOLD_REMOVE", "") or "—", fs, bg=bg)
            T.cell(tbl.cell(ri, 6), MD.yesno(rop), fs, bg=bg,
                   color=T.GREEN if rop else T.GRAY)
        if not show_all and len(active or rows) > len(page_rows):
            T.footnote(slide,
                       f"Showing {len(page_rows)} of {len(active or rows)} strategies — "
                       f"enable 'show all rows' to paginate the full list.")
        out.append(slide)
    return out


def slides_strategic_refunds(dk, S, *, section, show_all=False):
    rf = MD.section(S, "STRATEGIC REFUNDS RANGES AND FACTORS")
    tiers = MD.section(S, "STRATEGIC REFUNDS TIERS")
    daily = MD.section(S, "STRATEGIC REFUNDS DAILY MAX")
    if not (rf or tiers or daily):
        return []
    slide = dk.content("Strategic Refunds",
                       "Refund scoring ranges, tiers and daily maximums", section=section)
    y = T.CONTENT_TOP
    rf_all, tiers_all = rf, tiers
    if rf:
        rf, rf_hidden = _cap(rf, y + 0.50)
    if tiers:
        tiers, tiers_hidden = _cap(tiers, y + 0.50)
    if rf:
        T.band_label(slide, X, y, 9.2, f"  RANGES AND FACTORS ({len(rf_all)}; {len(rf)} shown)" if rf_hidden else f"  RANGES AND FACTORS ({len(rf)})")
        rh = _fits(len(rf) + 1, y + 0.50)
        tbl = dk.table(slide, X, y + 0.50, 9.2, [5.8, 2.6, 1.2], len(rf) + 1,
                       row_h=rh, header_h=HEAD_H)
        fs = _fs(rh, 14)
        for c, h in enumerate(["Category", "Range", "Factor"]):
            T.head_cell(tbl.cell(0, c), h, 14, align=PP_ALIGN.LEFT if c < 2
                        else PP_ALIGN.CENTER)
        for ri, r in enumerate(rf, 1):
            bg = T.zebra(ri - 1)
            v = r.get("Factor", "")
            T.cell(tbl.cell(ri, 0), r.get("Category", ""), fs, bg=bg, align=PP_ALIGN.LEFT)
            T.cell(tbl.cell(ri, 1), MD.clean_range(r.get("Range", "")), fs, bg=bg,
                   align=PP_ALIGN.LEFT)
            T.cell(tbl.cell(ri, 2), MD.fmt_factor(v), fs, bg=bg, bold=True,
                   color=MD.factor_color(v))
    rx = X + 9.2 + 0.5
    rw = T.SLIDE_W - rx - X
    if tiers:
        T.band_label(slide, rx, y, rw, f"  REFUND TIERS ({len(tiers_all)}; {len(tiers)} shown)" if tiers_hidden else f"  REFUND TIERS ({len(tiers)})")
        rh = _fits(len(tiers) + 1, y + 0.50)
        tbl = dk.table(slide, rx, y + 0.50, rw, [2.6, 3.0, 3.0], len(tiers) + 1,
                       row_h=rh, header_h=HEAD_H)
        fs = _fs(rh, 14)
        for c, h in enumerate(["Refund ID", "Lower Bound", "Upper Bound"]):
            T.head_cell(tbl.cell(0, c), h, 14)
        for ri, r in enumerate(tiers, 1):
            bg = T.zebra(ri - 1)
            T.cell(tbl.cell(ri, 0), r.get("REFUND_ID", ""), fs, bg=bg)
            T.cell(tbl.cell(ri, 1), MD.fmt_money(r.get("MIN_LOWER_BOUND", "")), fs, bg=bg)
            T.cell(tbl.cell(ri, 2), MD.fmt_money(r.get("MAX_UPPER_BOUND", "")), fs, bg=bg)
    if daily:
        parts = []
        for r in daily:
            parts.append(f"Refund {r.get('REFUND_ID', '—')}: "
                         f"{MD.fmt_money(r.get('DAILY_STRATEGIC_USD', ''))} / day, "
                         f"{r.get('DAILY_STRATEGIC_QTY', '—')} items")
        T.footnote(slide, "Daily maximums — " + "   ·   ".join(parts))
    return [slide]


# ═════════════════════════════ orchestration ════════════════════════════════
# Categories that get their own dedicated slide, in deck order.
CATEGORY_SLIDES = [
    ("Actual Monthly Deposit Count", "Matrix Variable — Actual Monthly Deposit Count",
     "Points by number of deposits in the month; negative factors reduce the scored limit"),
    ("Actual Monthly Deposits", "Matrix Variable — Actual Monthly Deposit Dollars",
     "Points by total monthly deposit dollars"),
]
HANDLED_CATEGORIES = {"Actual Monthly Deposit Count", "Actual Monthly Deposits",
                      "Age of Account", "Monthly Debit Declines"}


def add_matrix_slides(dk, S, settings, *, section, show_all_rows=False, cover=True):
    """Core matrix-validation slides. Returns notes."""
    notes = []
    if cover:
        slide_cover(dk, settings, section=section)
    slide_settings(dk, S, settings, section=section)
    if MD.section(S, "OVERRIDES"):
        slide_overrides(dk, S, section=section)

    for cat, title, sub in CATEGORY_SLIDES:
        if MD.range_grid(S, cat, dk.types):
            slide_category(dk, S, cat, title, sub, section=section)
    if MD.range_grid(S, "Age of Account", dk.types):
        slide_age_declines(dk, S, section=section)

    # any additional factor category found in the file gets its own slide
    for cat in MD.categories(S):
        if cat in HANDLED_CATEGORIES:
            continue
        data = MD.range_grid(S, cat, dk.types)
        if not data:
            continue
        slide_category(dk, S, cat, f"Matrix Variable — {cat}",
                       "Points by range; negative factors reduce the scored limit",
                       section=section)

    # trending: 1-D repos share the trigger slide, 2-D repos get their own
    repos = MD.trend_repositories(S)
    structures = {r: MD.trend_structure(S, r) for r in repos}
    oned = [r for r in repos if len(structures[r]["dims"]) == 1]
    twod = [r for r in repos if len(structures[r]["dims"]) >= 2]
    if repos:
        slide_trend_triggers(dk, S, oned, section=section)
        for r in twod:
            slide_trend_grid(dk, S, r, structures[r], section=section)
        if any(structures[r].get("truncated") for r in twod):
            notes.append("At least one trend grid had range labels reconstructed "
                         "positionally because the export truncated the rule text; "
                         "re-export query 1822 with a wider Calculation column to "
                         "render them verbatim.")

    if MD.section(S, "TIERS AND ROUNDING"):
        slide_tiers(dk, S, settings, section=section)
    if MD.has_limit_notification(settings):
        slide_limit_notification(dk, settings, section=section)
    if MD.has_cashplease(settings):
        slide_cashplease(dk, settings, section=section)
    return notes
