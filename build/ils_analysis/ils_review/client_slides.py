"""
The "Client Analysis" slides: what the analysis team pastes into each client's deck every cycle from
R, Power BI and Excel, built here from the raw extracts.

NEW in the RPE port. Each `add_*` function builds the slides for one section of `config.SECTIONS`
and returns a list of notes (what was skipped and why) for the Data Notes slide. The figures come from
`r_fees`, `r_accounts` and `r_scoring`; this module only lays them out, on the RPE canvas in REAL
inches (13.333 x 7.5), through `build/shapes.py` and the theme primitives.

Every slide carries its selection on the face and its Source line in the speaker notes. A figure the
extracts cannot support is not drawn: the reason goes in the returned notes, and a labelled
placeholder slide is added only for the peer-fee slides, which belong in the deck whatever the
extract holds.
"""
from __future__ import annotations

import os

import shapes
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches

from . import r_accounts as RA
from . import r_common as R
from . import r_fees as RF
from . import r_scoring as RS
from . import scoring_summary as SS
from . import theme as T

BODY_T, BODY_B = 1.70, 6.72
LEFT, RIGHT = 0.50, 12.833
FULL_W = RIGHT - LEFT


def _fn(p):
    return os.path.basename(str(p)) if p else ""


def _src(cfg, fr, *kinds, extra=""):
    """The Source line: the extract file names and their pull stamp, the client, the as-of date."""
    names = {"za": _fn(cfg.zaccounts_path), "zt": _fn(cfg.ztrend_path), "dd": _fn(cfg.declines_path),
             "rf": _fn(cfg.refunds_path), "mx": _fn(cfg.matrix_path), "dbic": _fn(cfg.dbic_path)}
    files = ", ".join(names[k] for k in kinds if names.get(k))
    pull = fr.loaded.file_date.strftime("%Y-%m-%d") if fr.loaded.file_date is not None else "n/a"
    s = (f"{files} (ILS extract pulled {pull}; data as of {str(fr.asof)[:10]}), client "
         f"{cfg.client_id} {cfg.client_name}.")
    return f"Source: {s}{(' ' + extra) if extra else ''}"


def table(slide, tbl, L, T0, W, max_h, *, colw=None, highlight_last=False, first_w=None, max_fs=12):
    """A native table from a {"headers", "rows"} dict. Row height and font fit the box (STYLE.md: a dense
    table is the declared exception to the 16 pt floor, 10-12 pt here). Column widths come from the
    measured text (textfit) so no cell wraps and the table cannot grow past the box; header cells may
    wrap onto two lines. -> bottom edge in inches."""
    from textfit import text_width_in
    data = [tbl["headers"]] + [[str(c) for c in r] for r in tbl["rows"]]
    n, nc = len(data), len(data[0])
    row_h = min(0.42, max_h / (n - 1 + 1.75))
    fs = max_fs if row_h >= 0.34 else (11 if row_h >= 0.25 else 10)

    def need(fs_):
        out = []
        for j in range(nc):
            body = max((text_width_in(data[i][j], fs_, "Carlito", highlight_last and i == n - 1)
                        for i in range(1, n)), default=0.3)
            words = data[0][j].split() or [""]
            head = max(text_width_in(w_, fs_, "Carlito", True) for w_ in words)
            out.append(max(body, head) + 0.22)
        return out
    mins = need(fs)
    while sum(mins) > W and fs > 10:
        fs -= 1
        mins = need(fs)
    if sum(mins) > W:                                  # still too wide: scale and accept
        mins = [m * W / sum(mins) for m in mins]
    extra = (W - sum(mins))
    colw = [m + extra * m / sum(mins) for m in mins]
    wrap_head = any(text_width_in(data[0][j], fs, "Carlito", True) + 0.22 > colw[j] for j in range(nc))
    head_h = row_h * (1.75 if wrap_head else 1.0)
    hi = (n - 1,) if highlight_last else ()
    total = head_h + row_h * (n - 1)
    gf = shapes.add_table(slide, L, T0, W, total, data, colw, highlight=hi, fs=fs)
    tb = gf.table
    tb.rows[0].height = int(head_h * 914400)
    for i in range(1, n):
        tb.rows[i].height = int(row_h * 914400)
    gf.height = int(total * 914400)
    return T0 + total


def _picture(slide, res, L, T0, maxW, maxH):
    return shapes.fit_picture(slide, res.path, L, T0, maxW, maxH)


def _emit(dk, res, cfg, fr, *kinds):
    """Write the figure's sidecar JSON beside its PNG and record it in the deck's figure index."""
    R.write_sidecar(res, dk.chart_dir, source=_src(cfg, fr, *kinds), client_id=cfg.client_id, asof=fr.asof)
    dk.sidecars.append({"key": res.key, "title": res.title, "png": os.path.basename(res.path) if res.path else None,
                        "numbers": R._jsonable(res.numbers), "parity": R._jsonable(res.parity),
                        "notes": res.notes, "skipped": res.skipped or None})


def _parity_lines(res):
    return [f"{p['measure']}: ours {p['ours']:,.2f} vs deck {p['deck']:,.2f} ({p['status']})"
            for p in res.parity if p.get("deck") is not None]


def _skip(notes, res):
    if res is None:
        return True
    if not res.ok:
        notes.append(f"{res.title}: skipped — {res.skipped}.")
        return True
    return False


def _banner(slide, text):
    T.band_real(slide, LEFT, BODY_T, FULL_W, text)


# ═════════════════════════════ 365-day KPI rollup ═══════════════════════════
def say_first(slide, text):
    """The one sentence the presenter says first: it leads the speaker notes, ahead of the Source line."""
    slide.notes_slide.notes_text_frame.text = f"Say first: {text}\n" + slide.notes_slide.notes_text_frame.text


def caption(slide, text, *, T0=6.42, size=13, L=LEFT, W=10.3):
    """A 'how to read it' under the content, kept clear of the client's logo at the bottom right (10.3 in wide)."""
    shapes.textbox(slide, L, T0, W, 0.5, "How to read it: " + text, size, T.SUBTLE, False, PP_ALIGN.LEFT, T.BODY, MSO_ANCHOR.TOP)


def compact_money(v):
    """'$7,294,040' -> '$7.29M'; '$866,858.22' -> '$867K'; other text unchanged."""
    s = str(v).replace(",", "")
    if not s.startswith("$"):
        return str(v)
    try:
        n = float(s[1:])
    except ValueError:
        return str(v)
    if n >= 1e6:
        return f"${n / 1e6:.2f}M"
    if n >= 1e4:
        return f"${n / 1e3:.0f}K"
    return f"${n:,.0f}"


KPI_TILES = (("Collected fees, 365 days", "Collected Fees", True), ("Charge-offs, 365 days", "Charge-Off Amount", True),
             ("Loss rate", "Loss Rate", False), ("Open accounts", "Open Accts", False),
             ("NSF/OD users", "NSF/OD Users", False), ("Account growth", "Growth Rate", False))


def add_kpi_rollup(dk, cfg, fr, *, section, progress=None):
    """Six headline figures, Personal beside Business. The full 365-day table is an appendix slide."""
    notes = []
    res = RF.kpi_rollup(fr, dk.ref)
    if _skip(notes, res):
        return notes
    _emit(dk, res, cfg, fr, "za")
    tbl = res.tables["kpi"]
    cols = {h: j for j, h in enumerate(tbl["headers"])}
    rows = {r[0]: r for r in tbl["rows"]}
    types = [t for t in ("Personal", "Business") if t in cols]
    s = dk.content("Where the program stands: six figures", f"Personal and business accounts, trailing 365 days to {fr.asof:%B} {fr.asof.day}, {fr.asof.year}.",
                   section=section, source=_src(cfg, fr, "za", extra="Full 365-day table: appendix slide 'Appendix: 365-day KPI detail'."))
    gap = 0.20
    tw = (FULL_W - 2 * gap) / 3
    th = 2.05
    for i, (label, key, money_) in enumerate(KPI_TILES):
        if key not in rows:
            continue
        x = LEFT + (i % 3) * (tw + gap)
        y = BODY_T + 0.05 + (i // 3) * (th + gap)
        card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(tw), Inches(th))
        card.fill.solid()
        card.fill.fore_color.rgb = T.BAND
        card.line.fill.background()
        shapes.shadow(card)
        shapes.textbox(s, x + 0.1, y + 0.10, tw - 0.2, 0.36, label, 15, T.NAVY, True, PP_ALIGN.CENTER, T.HEAD, MSO_ANCHOR.TOP)
        cw = (tw - 0.2) / max(1, len(types))
        for k, t in enumerate(types):
            v = rows[key][cols[t]]
            v = compact_money(v) if money_ else v
            shapes.textbox(s, x + 0.1 + k * cw, y + 0.62, cw, 0.80, v, 30, T.NAVY, True, PP_ALIGN.CENTER, T.HEAD, MSO_ANCHOR.MIDDLE)
            shapes.textbox(s, x + 0.1 + k * cw, y + 1.45, cw, 0.30, t, 13, T.SUBTLE, False, PP_ALIGN.CENTER, T.BODY, MSO_ANCHOR.TOP)
    caption(s, "each tile shows Personal and Business side by side; loss rate is charge-off dollars over collected fees. "
               "The full table is in the appendix.", T0=6.40, size=12)
    say_first(s, "These six numbers are the size of the program and what it costs us in charge-offs.")
    dk.defer(lambda: _kpi_detail(dk, cfg, fr, res))
    return notes


def _kpi_detail(dk, cfg, fr, res):
    s = dk.content("Appendix: 365-day KPI detail", f"Business and personal accounts, trailing 365 days to {fr.asof:%B} {fr.asof.day}, {fr.asof.year}.",
                   section="appendix", source=_src(cfg, fr, "za"))
    table(s, res.tables["kpi"], LEFT, BODY_T, 8.0, BODY_B - BODY_T, first_w=3.6)
    T.band_real(s, 8.85, BODY_T, 3.98, "DEFINITIONS")
    T.bullets_real(s, 8.85, BODY_T + 0.5, 3.98, BODY_B - BODY_T - 0.55, [
        "Collected fees, charge-offs and refunds are the 365-day totals carried on each account.",
        "Loss rate is charge-off dollars divided by collected fees; refund % is refund dollars divided by collected fees.",
        "A user is an account with at least one NSF/OD item in 365 days.",
        "Open active accounts have a deposit in the last 240 days or an NSF/OD item in the last 365.",
    ], size=14)
    say_first(s, "Reference table behind the six headline figures.")
    return [s]


# ═════════════════════════════ fees, repayment ══════════════════════════════
def add_fee_trends(dk, cfg, fr, *, section, progress=None):
    say = progress or (lambda m: None)
    notes = []
    if not fr.has_trend:
        return ["Fee trending, paid versus returned items and items not repaid were skipped — no ZTrend file."]
    ref = dk.ref
    for t in ("Personal", "Business"):
        say(f"  fee trending — {t}…")
        res = RF.fees_daily(fr, t, dk.chart_dir, ref=ref)
        if _skip(notes, res):
            continue
        _emit(dk, res, cfg, fr, "zt")
        first, last = res.tables["monthly"]["rows"][0][0], res.tables["monthly"]["rows"][-1][0]
        s = dk.content(f"Collected fee trending — {t}", f"{t} accounts, daily collected NSF/OD fees, {res.numbers['first_day']} to "
                       f"{res.numbers['last_day']}; table {first} to {last}.", section=section,
                       source=_src(cfg, fr, "zt", "za", extra="Fees are CollectedFees summed by notice date; the 30-day line is an "
                                   "exponentially weighted moving average (span 30). Pay rate is paid items over items."))
        _picture(s, res, LEFT, BODY_T + 0.05, 7.8, 4.85)
        table(s, res.tables["monthly"], 8.45, BODY_T + 0.05, 4.38, BODY_B - BODY_T - 0.15)
        yoy = res.numbers.get("year_on_year")
        if yoy:
            T.bullets_real(s, LEFT, 6.30, 7.8, 0.40, [yoy["phrase"] + " (last complete month)."], size=14, min_size=12)
    res = RF.paid_vs_returned(fr, dk.chart_dir, ref=ref)
    if not _skip(notes, res):
        _emit(dk, res, cfg, fr, "zt")
        st = next(iter(res.numbers.values()))
        s = dk.content("Collected fees — paid vs. returned items",
                       f"Open and active DDA accounts, {st['first_month']} through {st['last_month']} (12 complete months).",
                       section=section, source=_src(cfg, fr, "zt", "za", extra="Paid = PD 1; returned = PD 0. Purchase power is "
                                                    "paid item dollars per fee dollar collected on paid items."))
        _picture(s, res, LEFT, BODY_T + 0.0, 7.0, 3.45)
        T.band_real(s, 8.0, BODY_T + 0.05, 4.83, "HOW TO READ IT")
        T.bullets_real(s, 8.0, BODY_T + 0.55, 4.83, 2.9, [
            "The first bar splits collected fee dollars between paid and returned items; the second splits item counts.",
            "Returned items carry the lower NSF fee, so the returned share of items runs above its share of fee dollars.",
        ], size=14)
        full = res.tables["summary"]
        keep = [j for j, h in enumerate(full["headers"]) if h in ("Account Type", "Collected Fees", "% Returned Fees", "% Returned Items", "Purchase Power x")]
        small = {"headers": [full["headers"][j] for j in keep], "rows": [[r[j] for j in keep] for r in full["rows"]]}
        table(s, small, LEFT, 5.3, FULL_W, 1.45, max_fs=14)
        say_first(s, "About a quarter of the fee dollars come from returned items; every column is in the figure's sidecar.")
    for t in (("Personal", "Business") if getattr(cfg, "include_not_repaid", False) else ()):
        res = RF.not_repaid(fr, t, dk.chart_dir, ref=ref)
        if _skip(notes, res):
            continue
        _emit(dk, res, cfg, fr, "zt", "za")
        s = dk.content(f"Percent of NSF/OD items not repaid — {t}",
                       f"{t} accounts, notices {res.numbers['window'][0]} to {res.numbers['window'][1]}; "
                       "a notice is not repaid when its account was later charged off.",
                       section=section, source=_src(cfg, fr, "zt", "za", extra="Window ends 60 days before the as-of date so each "
                                                    "notice has had time to resolve. " + " ".join(res.notes)))
        _picture(s, res, LEFT, BODY_T + 0.05, 7.8, 4.85)
        table(s, res.tables["monthly"], 8.45, BODY_T + 0.05, 4.38, BODY_B - BODY_T - 0.15)
        notes.append(f"Percent of items not repaid ({t}): the hand-built deck's definition comes from a charge-off table that is "
                     f"not in the extract, so these rates approximate it (see the figure sidecar).") if t == "Personal" else None
    return notes


def add_exception_items(dk, cfg, fr, *, section, progress=None):
    notes = []
    if not fr.has_trend:
        return ["Exception items by channel was skipped — no ZTrend file."]
    res_b = RF.exception_treemap(fr, "Business", dk.chart_dir, size=(6.0, 3.55))
    res_p = RF.exception_treemap(fr, "Personal", dk.chart_dir, size=(6.0, 3.55))
    if _skip(notes, res_b) & _skip(notes, res_p):
        return notes
    win = (res_p if res_p.ok else res_b).numbers["window"]
    s = dk.content("Trends in exception items", f"Item volume by channel, {win[0]} to {win[1]}; tile area is the item count and the "
                   "figure inside is the median item amount.", section=section,
                   source=_src(cfg, fr, "zt", "za", extra="Channel flags and Item_Amts from ZTrend; median item amounts are "
                                "per channel over the window."))
    for res, L, label in ((res_b, LEFT, "Business exception item volume by channel"),
                          (res_p, 6.833, "Personal exception item volume by channel")):
        if not res.ok:
            continue
        _emit(dk, res, cfg, fr, "zt")
        shapes.textbox(s, L, BODY_T + 0.02, 6.0, 0.4, label, 16, T.NAVY, True, PP_ALIGN.LEFT, T.BODY, MSO_ANCHOR.TOP)
        _picture(s, res, L, BODY_T + 0.5, 6.0, 3.6)
    shapes.textbox(s, LEFT, 6.35, FULL_W, 0.35, "Median item amounts are from the 365 days to the as-of date.", 12, T.SUBTLE, False,
                   PP_ALIGN.LEFT, T.BODY, MSO_ANCHOR.TOP)
    return notes


# ═════════════════════════════ eligibility ══════════════════════════════════
def add_eligibility(dk, cfg, fr, *, section, progress=None):
    notes = []
    for t in ("Personal", "Business"):
        res = RA.eligibility_chart(fr, t, dk.chart_dir)
        tabs = RA.eligibility_tables(fr, t, dk.ref)
        if _skip(notes, res) or tabs is None:
            continue
        res.tables.update({"codes": tabs["codes"], "segments": tabs["segments"]})
        res.parity += tabs["parity"]
        _emit(dk, res, cfg, fr, "za")
        codes = tabs["codes"]
        body = [r for r in codes["rows"] if r[0] != "Total"]
        total = next((r for r in codes["rows"] if r[0] == "Total"), None)
        hdr = codes["headers"]
        ci = {h: j for j, h in enumerate(hdr)}

        def n_(v):
            return int(str(v).replace(",", "").replace("$", "") or 0)
        top = body[:6]
        rest = body[6:]
        rows = [[("Blank (active)" if r[0] == "Blank" else r[0]), r[ci["Accounts"]], r[ci["Can Overdraft"]], r[ci["Users"]]] for r in top]
        if rest:
            rows.append([f"All other ({len(rest)} codes)", f"{sum(n_(r[ci['Accounts']]) for r in rest):,}",
                         f"{sum(n_(r[ci['Can Overdraft']]) for r in rest):,}", f"{sum(n_(r[ci['Users']]) for r in rest):,}"])
        if total:
            rows.append(["Total", total[ci["Accounts"]], total[ci["Can Overdraft"]], total[ci["Users"]]])
        users_total = n_(total[ci["Users"]]) if total else 0
        topr = max(body, key=lambda r: n_(r[ci["Users"]])) if body else None
        share = (n_(topr[ci["Users"]]) / users_total * 100) if topr and users_total else None
        which = "a blank status code" if topr and topr[0] == "Blank" else (f"status code {topr[0]}" if topr else "")
        title = (f"{share:.0f}% of {t.lower()} NSF/OD users hold accounts with {which}" if share is not None
                 else f"{t} accounts by overdraft status code")
        s = dk.content(title, f"Open {t.lower()} accounts with recent activity ({tabs['population']:,}), by overdraft status code.",
                       section=section,
                       source=_src(cfg, fr, "za", extra="Open active = deposit in the last 240 days or an NSF/OD item in the last "
                                   "365. Users are accounts with at least one NSF/OD item in 365 days. Every code is listed in "
                                   "'Appendix: every overdraft status code'."))
        _picture(s, res, LEFT, BODY_T + 0.05, 6.4, 4.5)
        table(s, {"headers": ["Status code", "Accounts", "Can overdraft", "NSF/OD users"], "rows": rows}, 7.1, BODY_T + 0.1, 5.73,
              BODY_B - BODY_T - 0.5, highlight_last=True, max_fs=14)
        caption(s, "each bar is a status code, split by 33-day deposits; a blank code means the account carries no status code.")
        say_first(s, "Most of our NSF/OD users sit on one status code; this is where the program's users are.")
        dk.defer(lambda t=t, tabs=tabs: _eligibility_detail(dk, cfg, fr, t, tabs, first=(t == "Personal")))
    return notes


def _eligibility_detail(dk, cfg, fr, t, tabs, first=True):
    """One appendix slide per account type: every status code, and the NSF/OD item segments below it."""
    s = dk.content(f"Appendix: every overdraft status code and item segment, {t.lower()}",
                   f"Open {t.lower()} accounts with recent activity ({tabs['population']:,}).", section="appendix",
                   source=_src(cfg, fr, "za", extra="Open active = deposit in the last 240 days or an NSF/OD item in the last 365."))
    table(s, tabs["codes"], LEFT, BODY_T, 6.1, BODY_B - BODY_T, highlight_last=True, max_fs=10)
    table(s, tabs["segments"], 6.85, BODY_T, 5.98, 3.0, highlight_last=True, max_fs=10)
    T.bullets_real(s, 6.85, 5.0, 5.98, 1.4, [
        "Reg E opt in and opt out are counted among the accounts that can overdraft.",
        "Accounts with no OD status code are listed as Blank."], size=12, min_size=11)
    say_first(s, "Reference tables behind the status code and heavy-user slides.")
    return [s]


# ═════════════════════════════ branch summary ═══════════════════════════════
def add_branch_summary(dk, cfg, fr, *, section, progress=None):
    notes = []
    t = "Personal"
    outs = RA.branch_bubbles(fr, t, dk.chart_dir)
    tabs = RA.branch_tables(fr, t)
    if tabs is None:
        return ["Branch summary was skipped — fewer than three branches meet the account minimum."]
    sub = f"Open {t.lower()} accounts with recent activity; branches with {tabs['min_accounts']}+ accounts ({tabs['branches']} branches). Bubble size is NSF/OD items in 365 days."
    pairs = (("branch_eligibility", "Eligibility and items per user", "eligible"),
             ("branch_regE", "Reg E opt-in and items per user", "items_per_user"))
    for k, ttl, tk in pairs:
        res = outs.get(k)
        if _skip(notes, res):
            continue
        _emit(dk, res, cfg, fr, "za")
        s = dk.content(f"Branch summary — {ttl}", sub, section=section,
                       source=_src(cfg, fr, "za", extra="Dashed lines mark the portfolio averages. Items per user = items in 365 days "
                                   "divided by accounts with at least one item."))
        _picture(s, res, LEFT, BODY_T + 0.05, 6.5, 4.9)
        T.band_real(s, 7.3, BODY_T + 0.05, 5.53, "TOP 10 BRANCHES: " + ("PERCENT ELIGIBLE" if tk == "eligible" else "ITEMS PER USER"))
        table(s, tabs[tk], 7.3, BODY_T + 0.55, 5.53, BODY_B - BODY_T - 0.6)
    res = RA.branch_opened_regE(fr, t, dk.chart_dir)
    if not _skip(notes, res):
        _emit(dk, res, cfg, fr, "za")
        s = dk.content("Branch summary — accounts opened and Reg E opt-in", f"Open {t.lower()} accounts by branch: opened in the last 365 days, "
                       "and Reg E opt-in among those opened in the last 90.", section=section,
                       source=_src(cfg, fr, "za"))
        _picture(s, res, LEFT, BODY_T + 0.05, FULL_W, 4.9)
    return notes


# ═════════════════════════════ Reg E drilldown ══════════════════════════════
def add_reg_e(dk, cfg, fr, *, section, progress=None):
    notes = []
    t = "Personal"
    tabs = RA.reg_e_tables(fr, t)
    if tabs is None:
        return ["Reg E drilldown was skipped — no open accounts."]
    dk.sidecars.append({"key": "reg_e_tables", "title": "Reg E by election and by year opened",
                        "tables": {"by_election": tabs["by_election"], "by_year": tabs["by_year"]}})
    be = tabs["by_election"]
    ci = {h: j for j, h in enumerate(be["headers"])}
    rows = {r[0]: r for r in be["rows"]}

    def n_(v):
        return float(str(v).replace(",", "").replace("$", "") or 0)
    tot = rows.get("Total")
    yes = rows.get("Y")
    # ── slide 1: opt-in by the year the account opened
    yrs = tabs["by_year"]["rows"]
    rates = [float(r[3].rstrip("%")) for r in yrs]
    ns = [n_(r[1]) for r in yrs]
    labels = [r[0] for r in yrs]
    if yrs:
        lo_i = min(range(len(rates)), key=lambda i: rates[i])
        hi_i = max(range(len(rates)), key=lambda i: rates[i])
        overall = sum(n_(r[2]) for r in yrs) / max(1.0, sum(ns)) * 100
        fig, ax = R.new_fig(7.8, 4.5)
        cols = [R.NAVY] * len(rates)
        cols[lo_i] = R.ORANGE
        ax.bar(range(len(rates)), rates, color=cols, width=0.66)
        for i, v in enumerate(rates):
            ax.text(i, v + max(rates) * 0.015, f"{v:.0f}%", ha="center", va="bottom", fontsize=9.5, color=R.NAVY, fontweight="bold")
        ax.set_xticks(range(len(rates)))
        ax.set_xticklabels(labels, rotation=60, ha="right", fontsize=9.5, color=R.TICK)
        R.style_axes(ax)
        ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
        ax.set_ylabel("Share opted in to Reg E", fontsize=10.5, color=R.TICK)
        ax.set_ylim(0, max(rates) * 1.18)
        fig.tight_layout()
        png = R.save(fig, dk.chart_dir, "reg_e_by_year_opened")
        s0 = dk.content(f"Reg E opt-in runs from {rates[lo_i]:.0f}% to {rates[hi_i]:.0f}% by the year the account opened",
                        f"Open {t.lower()} accounts by year opened: share with a Reg E opt-in, as of {fr.asof:%B} {fr.asof.day}, {fr.asof.year}.",
                        section=section, source=_src(cfg, fr, "za", extra="Reg E opt-in = RegEOptinvalue Y; all open accounts, not only active ones."))
        T.image_real(s0, png, LEFT, BODY_T + 0.05, 7.8, 4.55)
        _tiles_real(s0, [(f"{overall:.0f}%", "Opted in, all open accounts"), (f"{rates[hi_i]:.0f}%", f"Highest: {labels[hi_i]}"),
                         (f"{rates[lo_i]:.0f}%", f"Lowest (orange): {labels[lo_i]}")])
        caption(s0, "each bar is the share of accounts opened in that year that opted in to Reg E.", T0=6.35)
        say_first(s0, "Reg E opt-in is not the same for every group of accounts; look at which opening years are low.")
        dk.sidecars.append({"key": "reg_e_by_year_opened", "title": "Reg E opt-in by year opened", "png": "reg_e_by_year_opened.png",
                            "numbers": {"years": labels, "opt_in_pct": rates, "accounts": ns}})
    # ── slide 2: who is opted in, and what they bring in
    if tot and yes:
        share_a = n_(yes[ci["Accounts"]]) / n_(tot[ci["Accounts"]]) * 100
        share_f = n_(yes[ci["Collected Fees (365)"]]) / max(1.0, n_(tot[ci["Collected Fees (365)"]])) * 100
        rows2 = []
        names = {"Y": "Opted in (Y)", "N": "Opted out (N)", "D": "Default (D)", "Total": "Total"}
        for k in ("Y", "N", "D", "Total"):
            r = rows.get(k)
            if not r:
                continue
            fees_share = n_(r[ci["Collected Fees (365)"]]) / max(1.0, n_(tot[ci["Collected Fees (365)"]])) * 100
            rows2.append([names[k], r[ci["Accounts"]], f"{fees_share:.0f}%", r[ci["Fees / User"]], r[ci["Median ILS Limit"]]])
        s = dk.content(f"Opted-in accounts are {share_a:.0f}% of accounts and {share_f:.0f}% of fees",
                       f"Open {t.lower()} accounts with recent activity ({tabs['population']:,}) by Reg E election. D = default, N = opted out, Y = opted in.",
                       section=section, source=_src(cfg, fr, "za", extra="Election table: open accounts with recent activity; fees are CollectedFees365."))
        table(s, {"headers": ["Reg E election", "Accounts", "Share of fees", "Fees per user", "Median ILS limit"], "rows": rows2},
              LEFT, BODY_T + 0.2, FULL_W, 3.0, highlight_last=True, max_fs=16)
        caption(s, "fees per user is collected fees over accounts with at least one NSF/OD item; the median limit is the ILS limit in force.", T0=5.2)
        say_first(s, "Accounts that opted in to Reg E bring in more fees per user and hold higher limits.")
    return notes


def _tiles_real(slide, items, L=8.45, W=4.38, T0=1.80):
    h = 1.12
    for i, (v, lab) in enumerate(items[:3]):
        shapes.tile(slide, L, T0 + i * (h + 0.18), W, h, v, lab, small_label=True)




# ═════════════════════════════ debit declines ═══════════════════════════════
def add_debit_declines(dk, cfg, fr, *, section, progress=None):
    notes = []
    if fr.dd is None:
        return ["Debit declines were skipped — no DebitDecline file."]
    for t in ("Personal", "Business"):
        d = RA.debit_decline_tables(fr, t, dk.ref)
        if d is None or not d["segmentation"]["rows"]:
            notes.append(f"Debit declines ({t}): skipped — no open accounts with a decline in 365 days.")
            continue
        src = _src(cfg, fr, "za", "dd", extra="Segmentation: open accounts that can overdraft, have not opted in to Reg E and had at "
                   "least one decline in 365 days.")
        s = dk.content(f"Debit declines — {t} accounts that can overdraft",
                       f"Segmentation by declines in 365 days; open accounts, eligible for an ILS limit, not opted in to Reg E ({d['population']:,}).",
                       section=section, source=src)
        table(s, d["segmentation"], LEFT, BODY_T + 0.1, FULL_W, 3.9, highlight_last=True, max_fs=12)
        T.bullets_real(s, LEFT, 5.85, FULL_W, 0.8, [
            "All accounts above are open, can overdraft and have not opted in; each shows the NSF/OD items and fees it already generates."],
            size=14)
        if d["score_bands"] and d["score_bands"]["rows"]:
            s2 = dk.content(f"Debit declines — {t} accounts by ILS limit",
                            "Accounts with a debit decline in the decline file, by current ILS limit.", section=section,
                            source=_src(cfg, fr, "za", "dd", extra="Declines: DebitDecline file, joined to open accounts by account id."))
            table(s2, d["score_bands"], LEFT, BODY_T + 0.1, FULL_W, 4.8, max_fs=12)
    return notes


# ═════════════════════════════ scoring figures ═══════════════════════════════
def add_scoring_figures(dk, cfg, fr, *, section, progress=None):
    """The Scoring Summary slides that are not predictor tables (Personal accounts, as in the deck)."""
    notes = []
    t = "Personal"
    dist = RS.limit_distribution(fr, t, dk.chart_dir)
    heat = RS.odlimit_heatmap(fr, t, dk.chart_dir)
    if not (_skip(notes, dist) & _skip(notes, heat)):
        s = dk.content("Scoring summary — limit distribution and heat map",
                       f"Open {t.lower()} accounts: current ILS limit by user segment (left), and median limit by account age and 33-day deposits (right).",
                       section=section, source=_src(cfg, fr, "za"))
        for res, L, w in ((dist, LEFT, 6.1), (heat, 6.85, 5.98)):
            if res.ok:
                _emit(dk, res, cfg, fr, "za")
                _picture(s, res, L, BODY_T + 0.05, w, 4.95)
    ct = RS.notice_crosstab_heatmap(fr, t, dk.chart_dir)
    st = RS.strat_table(fr, t)
    if not _skip(notes, ct):
        _emit(dk, ct, cfg, fr, "zt", "za")
        s = dk.content("Scoring summary — notices by matrix position",
                       f"{t} accounts, notices {ct.numbers['window'][0]} to {ct.numbers['window'][1]}, by account age and 33-day deposits at the notice.",
                       section=section, source=_src(cfg, fr, "zt", "za", extra=" ".join(ct.notes)))
        _picture(s, ct, LEFT, BODY_T + 0.05, 7.3, 4.95)
        T.band_real(s, 8.1, BODY_T + 0.05, 4.73, "HOW TO READ IT")
        T.bullets_real(s, 8.1, BODY_T + 0.55, 4.73, 4.0, [
            "Each cell counts the notices that fired at that account age and 33-day deposit level.",
            "Notices concentrate where accounts are older and deposits run $3,001 to $6,000; the youngest accounts carry the fewest.",
            "Compare with the limit heat map: the limit rises along both axes.",
        ], size=14)
    if st and st["rows"]:
        s = dk.content("Scoring summary — limit band profile",
                       f"Open active {t.lower()} accounts that can overdraft ({st['population']:,}), by current ILS limit.", section=section,
                       source=_src(cfg, fr, "za", "zt", extra="NSF fees = fees on returned items; OD fees = fees on paid items, "
                                   "from ZTrend over 365 days."))
        table(s, {"headers": st["headers"], "rows": st["rows"]}, LEFT, BODY_T + 0.1, FULL_W, 4.6, max_fs=11)
    return notes


# ═════════════════════════════ peer placeholders ═════════════════════════════
def add_peer_data(dk, cfg, fr, *, section, progress=None):
    """Peer NSF / OD fee slides: the data is ILS-wide, not in this client's extracts, so each is a labelled placeholder."""
    for kind, title in (("NSF", "Peer NSF fee data"), ("OD", "Peer OD fee data")):
        SS.placeholder_slide(
            dk, title, f"ILS client median {kind} fee by open, active DDA segment and institution type (bank, credit union).",
            f"{title}: placeholder — peer data not in the client's extracts",
            f"In the hand-built deck this comes from a fee sheet that spans ILS clients, which is not part of {cfg.client_name}'s "
            "ZAccounts, ZTrend, DebitDecline or RefundHistory extracts. Supply the peer fee table and this slide builds from it.",
            section=section, source=f"Source: none yet. Placeholder for the ILS-wide peer fee sheet; client {cfg.client_id} {cfg.client_name}, "
            f"data as of {str(fr.asof)[:10]}.")
    return ["Peer NSF and OD fee slides are placeholders: the ILS-wide peer fee data is not in the client's extracts."]
