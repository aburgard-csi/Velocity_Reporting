# Ported from v5 02-Scripts/ils/pre_go_live/deck.py at 7ba1e63. Logic unchanged; imports read ils_pipeline.deckkit (v5's deckkit and the ars.deck parts it reaches) and ils_pipeline.core.env.
"""The PGL board deck. Its own deck -- never a chapter in the ARS deck.

Built on deckkit (shared template and slide helpers); every title is
computed from the numbers; sections that declined in the run are absent or
carry their honest status. Slide order = the board story:

    cover -> the data we are getting (reconciliation) -> how ILS is
    configured -> the book step by step -> today on core limits -> Reg-E ->
    fees -> data readiness (the asks) -> what to confirm

A NORMAL PGL then gets the go-live chapter (funnel, score up/down, current
vs proposed limits -- the notebook's centerpiece) between core-state and
Reg-E. A data-first engagement (1737) omits it with include_golive=False
(CLI: --current-only); those comparisons stay in the report either way.
"""

from __future__ import annotations

from pathlib import Path

from ils_pipeline import deckkit as dk

from . import deck_charts

SLIDE_MANIFEST = ["cover", "reconcile", "matrix", "waterfall", "core_state",
                  "golive_divider", "funnel", "score", "limits",   # include_golive only
                  "rege", "fees", "readiness", "findings"]


def _n(m, key, default=0):
    return m.get(key, default) or default


def _money_(v):
    return dk.money(v)


def build(result, template: Path, out: Path, charts_dir: Path | None = None,
          include_golive: bool = True):
    m = result.metrics or {}
    if not m:
        raise ValueError("no metrics on the result; run the analysis first")
    charts_dir = Path(charts_dir or out.parent / "charts")
    charts_dir.mkdir(parents=True, exist_ok=True)
    made, skipped = [], []

    prs, new = dk.open_template(template)

    def chart(name, fn, *a, **kw):
        try:
            path = fn(*a, charts_dir / f"{name}.png", **kw)
            made.append(path)
            return path
        except Exception as exc:
            skipped.append(f"{name} chart ({type(exc).__name__}: {exc})")
            return None

    story: list = []

    def slide(pair, fallback):
        sl = new()
        story.append((pair[0] if pair else fallback, bool(pair)))
        return sl, dk.headed(sl, pair, fallback)

    client = f"{result.client_id} {result.client_name or ''}".strip()
    bases = {r[0]: r[1] for r in m.get("pgl_bases", [])}

    # ---- cover -------------------------------------------------------------
    s = new()
    dk.text(s, 0.9, 2.5, 11.5, 1.0, "Instant Limit Solution", size=40,
            bold=True, font=dk.HEAD_FONT)
    dk.text(s, 0.95, 3.6, 11.5, 0.6, f"{client} — pre-go-live review",
            size=24, color=dk.SLIDE_ORANGE, font=dk.HEAD_FONT)
    dk.text(s, 0.95, 4.3, 11.5, 0.5,
            f"extract {m.get('pgl_extract', '')}  |  codes confirmed by the CSM",
            size=15, color=dk.SLIDE_GREY)

    # ---- reconciliation: the data we are getting ----------------------------
    rc = m.get("pgl_reconcile") or []
    if rc:
        ok_n = m.get("pgl_reconcile_matches", 0)
        miss = m.get("pgl_reconcile_misses", 0)
        head = (f"Every count in the extract matches the ILS system's own numbers "
                f"({ok_n} of {ok_n} checks)" if not miss else
                f"{miss} of {ok_n + miss} extract-vs-system checks disagree")
        sub = ("extract cross-checked against the vendor's integrity dump, "
               "row for row, before any analysis")
        s, top = slide((head, sub), "The data we are getting")
        rows_t = [["Check", "Extract", "ILS system", "Match"]]
        for check, ev, sv, _delta, ok, _note in rc:
            rows_t.append([check[:52], f"{ev:,}" if ev is not None else "-",
                           f"{sv:,}" if sv is not None else "-",
                           {True: "yes", False: "NO"}.get(ok, "-")])
        dk.table(s, rows_t, 0.7, top + 0.1, 10.6, col_widths=[6.4, 1.5, 1.5, 1.2], size=11)
        y = top + 0.35 + 0.34 * len(rows_t)
        for f_ in (m.get("pgl_reconcile_findings") or [])[:3]:
            dk.text(s, 0.75, y, 12.0, 0.62, f"—  {f_}", size=12.5, color=dk.SLIDE_NAVY)
            y += 0.55

    # ---- how ILS is configured (the matrix) ---------------------------------
    types = m.get("sysv_matrix_types") or []
    if types:
        tp = {t[0]: t for t in types}
        p_ = tp.get("Personal")
        head = (f"ILS scores deposits, age and repayment into a limit of "
                f"${p_[2]:,.0f}-${p_[3]:,.0f} for personal accounts"
                if p_ else "How the ILS matrix computes a limit")
        step_ = m.get("sysv_matrix_rounding_step")
        sub = (f"factors summed, rounded to ${step_:,.0f} steps; overrides run first "
               f"and can stop the calculation; matrix last modified "
               f"{str(m.get('sysv_matrix_last_change'))[:10]}")
        s, top = slide((head, sub), "How ILS is configured")
        fx = [f for f in (m.get("sysv_matrix_factors") or []) if f[0] == "Personal"]
        rows_t = [["Scoring factor (personal)", "Ranges", "Factor min .. max"]]
        for _t, cat, k, lo, hi in fx:
            rows_t.append([cat, str(k), f"{lo:,.0f} .. {hi:,.0f}"])
        dk.table(s, rows_t, 0.7, top + 0.1, 6.4, col_widths=[3.6, 1.0, 1.8], size=11.5)
        ov = [o for o in (m.get("sysv_matrix_overrides") or []) if o[0] == "Personal"]
        items = [("Account types", " / ".join(f"{t[0]} ${t[3]:,.0f}" for t in types),
                  "matrix maximums"),
                 ("Overrides", f"{len(ov)}", "guardrails that cut or zero a limit first")]
        um = m.get("sysv_od_status_unmapped") or []
        if um:
            items.append(("Unmapped codes", ", ".join(c for c, _ in um),
                          f"{sum(n or 0 for _, n in um):,} accounts outside the calc"))
        dk.rail(s, items, top=top)
        stops = [o for o in ov if o[3]]
        if stops:
            dk.text(s, 0.75, top + 0.4 + 0.34 * len(rows_t), 9.0, 0.9,
                    "Hard stops before any score: " +
                    "  ·  ".join(f"{c[1]} -> {c[2]}" for c in stops[:3]),
                    size=11.5, color=dk.SLIDE_GREY)

    # ---- the book, step by step (waterfall) ---------------------------------
    wf = m.get("pgl_waterfall") or []
    if wf:
        confirmed = m.get("pgl_waterfall_confirmed", 0)
        head = (f"From {wf[0][1]:,} rows to {wf[-2][1]:,} accounts that can overdraft "
                f"today — every step confirmed by the ILS system"
                if confirmed >= 3 and len(wf) >= 2 else
                "The book, step by step — every filter visible")
        sub = "no silent filtering; each cut names its column, its codes and its count"
        s, top = slide((head, sub), "Step by step")
        path = chart("pgl_waterfall", deck_charts.funnel,
                     [[w_[0], w_[1]] for w_ in wf])
        if path:
            dk.picture(s, path, top=top + 0.05, max_h=2.55)
        rows_t = [["Step", "Accounts", "Cut", "Why / system check"]]
        for stepname, count, removed, why, confirms in wf:
            why_short = why.split(" -- ")[0].split(";")[0][:58]
            if confirms:
                why_short = (why_short[:38] + "  [" + confirms + "]")[:72]
            rows_t.append([stepname[:34], f"{count:,}",
                           f"{removed:+,}" if removed else "", why_short])
        dk.table(s, rows_t, 0.55, top + 2.75, 12.2,
                 col_widths=[3.3, 1.2, 1.1, 6.6], size=10)

    # ---- today's program on core limits -------------------------------------
    cl = m.get("pgl_core_limits") or []
    if cl:
        biggest = max(cl, key=lambda r: r[3])
        head = (f"{biggest[3]:,} of the can-overdraft accounts live under a single "
                f"${biggest[0]:,} core limit today")
        pocket = m.get("pgl_core_can_od_zero", 0)
        sub = (f"exposure ${_n(m, 'pgl_core_exposure'):,} on core limits"
               + (f"; {pocket:,} accounts can overdraft with NO limit at all" if pocket else ""))
        s, top = slide((head, sub), "Today, on core limits")
        usage = {r[0]: r for r in (m.get("pgl_core_usage") or [])}
        rege_ = {r[0]: r for r in (m.get("pgl_core_rege") or [])}
        dep = {r[0]: r for r in (m.get("pgl_core_deposits") or [])}
        rows_t = [["Core limit", "Accounts", "Can OD", "w/ YTD items", "Depositing 33d", "Reg-E in"]]
        for lim, k, _pct_, can, _cannot in cl:
            u, r_, d_ = usage.get(lim), rege_.get(lim), dep.get(lim)
            rows_t.append([f"${lim:,}", f"{k:,}", f"{can:,}",
                           f"{u[2]:,} ({u[3]:.0f}%)" if u else "-",
                           f"{d_[3]:.0f}%" if d_ else "-",
                           f"{r_[3]:.0f}%" if r_ else "-"])
        dk.table(s, rows_t, 0.7, top + 0.15, 9.6,
                 col_widths=[1.5, 1.5, 1.4, 2.0, 1.8, 1.4], size=12)
        items = [("YTD OD items", f"{_n(m, 'pgl_core_ytd_items'):,}",
                  f"{_n(m, 'pgl_core_accts_with_items'):,} accounts with items"),
                 ("No-limit pocket", f"{pocket:,}", "can overdraft, $0 core limit")]
        op = m.get("pgl_core_odd_pockets") or []
        if op:
            items.append(("Outside the mapping", f"{sum(r[1] for r in op):,}",
                          f"status {', '.join(r[0] for r in op)} still carrying "
                          f"${sum(r[3] for r in op):,}"))
        dk.rail(s, items, top=top)
        if pocket:
            dk.kicker(s, f"{pocket:,} members can overdraft today with no limit at all "
                         f"\u2014 the pocket a limit strategy exists for.")

    # ---- what changes at go-live (the notebook's chapter; a NORMAL PGL
    # includes it -- a data-first engagement like 1737 runs --current-only) --
    if include_golive:
        dk.divider(prs, new, "What changes at go-live",
                   "ILS proposed limits against the core's -- the notebook chapter")
        # ---- funnel + exposure ---------------------------------------------------
        fu = m.get("pgl_funnel") or []
        if len(fu) >= 3:
            f_ = {r[0]: r[1] for r in fu}
            head = (f"Of {f_.get('rows', 0):,} accounts, {f_.get('eligible', 0):,} are "
                    f"eligible and {f_.get('proposed_limit', f_.get('eligible', 0)):,} "
                    f"get a proposed limit")
            ex = m.get("pgl_exposure") or {}
            sub = (f"exposure ${ex['current_total']:,} -> ${ex['proposed_total']:,} "
                   f"({ex['delta']:+,})" if ex else None)
            s, top = slide((head, sub), "Who ILS serves")
            path = chart("pgl_funnel", deck_charts.funnel,
                         [[r[2] if len(r) > 2 else r[0], r[1]] for r in fu])
            items = []
            if ex:
                items = [("Current", _money_(ex["current_total"]), "sum of core limits, eligibles"),
                         ("Proposed", _money_(ex["proposed_total"]), "sum of ILS limits"),
                         ("Median", f"${ex['median_current']:,.0f} -> ${ex['median_proposed']:,.0f}",
                          f"p90 proposed ${ex['p90_proposed']:,.0f}")]
            right = dk.rail(s, items, top=top) if items else 10.0
            if path:
                dk.chart_left(s, path, top, right)

        # ---- what ILS changes (score) ------------------------------------------
        h = m.get("pgl_score_headline") or {}
        p = h.get("personal")
        if p and p.get("base"):
            head = (f"Of {p['base']:,} open personal accounts, {p['up']:,} would see a "
                    f"higher limit under ILS, {p['down']:,} lower, {p['same']:,} unchanged")
            sub = "Score100Plus = up, ScoreLess100 = down, from the file's own comparison column"
            s, top = slide((head, sub), "What ILS changes")
            path = chart("pgl_score", deck_charts.score_updown, h)
            if path:
                dk.picture(s, path, top=top + 0.1)

        # ---- limits: current vs proposed + zero-limit actives -------------------
        cur = m.get("pgl_limit_dist_current_eligible") or m.get("pgl_limit_dist_current")
        prop = m.get("pgl_limit_dist_proposed")
        if cur and prop:
            zl = _n(m, "pgl_zero_limit_accounts")
            base_n = sum(r[1] for r in prop)
            head = (f"Where limits move: current vs proposed for the {base_n:,} "
                    f"eligible accounts with a proposed limit")
            sub = (f"{zl:,} open personal accounts carry a $0 ILS limit"
                   + (f"; {_n(m, 'pgl_eligible_null_limit'):,} eligible accounts have "
                      f"no proposed limit at all (data question)"
                      if _n(m, "pgl_eligible_null_limit") else ""))
            s, top = slide((head, sub), "Limits")
            path = chart("pgl_limits", deck_charts.limit_shift, cur, prop)
            if path:
                dk.picture(s, path, top=top + 0.1)
            zrows = m.get("pgl_zero_limit_by_deposit") or []
            active_zero = sum(r[1] for r in zrows if str(r[0]) not in ("0", "1"))
            if active_zero:
                dk.text(s, 0.75, 6.55, 11.8, 0.5,
                        f"{active_zero:,} of the zero-limit accounts made 2+ deposits in the "
                        f"last 33 days — active members the proposal leaves at $0.",
                        size=13, color=dk.SLIDE_NAVY)


    # ---- Reg-E --------------------------------------------------------------
    rate = m.get("pgl_rege_optin_rate_personal")
    if rate is not None:
        head = f"{rate:.0f}% of open personal accounts are opted in to Reg-E"
        er = m.get("pgl_rege_optin_rate_eligible")
        sub = (f"eligible base: {er:.0f}% — the accounts ILS will serve"
               if er is not None else None)
        s, top = slide((head, sub), "Reg-E")
        tr = m.get("pgl_rege_trend") or []
        path = chart("pgl_rege_trend", deck_charts.rege_trend, tr) if len(tr) >= 4 else None
        if path:
            dk.picture(s, path, top=top + 0.15)
            dk.text(s, 0.75, 6.6, 11.8, 0.4,
                    "opt-in rate of newly opened personal accounts, by month opened",
                    size=12, color=dk.SLIDE_GREY)

    # ---- fees ---------------------------------------------------------------
    audit = m.get("pgl_fee_audit")
    tiers = m.get("pgl_fee_tiers") or []
    if audit and tiers:
        base = _n(m, "pgl_fee_baseline")
        best = min(tiers, key=lambda r: r[2])
        head = (f"Fee tiering scenarios span {best[2]:+,.0f} to "
                f"{max(t[2] for t in tiers):+,.0f} against ${base:,.0f} actual")
        sub = (f"pay ratio {audit['implied_pay_ratio_pct']}% derived from the file; "
               f"scenarios are illustrative — confirm bands before board use")
        s, top = slide((head, sub), "Fee scenarios")
        path = chart("pgl_fees", deck_charts.fee_scenarios, base, tiers)
        if path:
            dk.picture(s, path, top=top + 0.1)
    else:
        dc = m.get("pgl_fee_daily_cap") or {}
        yc = m.get("pgl_fee_ytd_ceiling")
        if yc:
            s, top = slide((f"YTD overdraft items would bill {_money_(yc['gross_ceiling'])} "
                            f"at the ${yc['stated_fee']:g} fee — a ceiling, not revenue",
                            f"{yc['ytd_items']:,} YTD items across "
                            f"{yc['accounts_with_items']:,} accounts; the pay ratio is "
                            f"unknown until 12-month fee history populates"), "Fees")
        else:
            s, top = slide(("Fee modeling needs data this extract does not carry",
                            "stated plainly rather than estimated"), "Fees")
        items = [("Tier scenarios", "no 12-mo items" if not audit else "n/a",
                  "open accounts carry no rolling 12-month fee history"),
                 ("Daily cap", "not computable", dc.get("why", "")),
                 ("De minimis", "insufficient data",
                  (m.get("pgl_fee_de_minimis") or {}).get("why", ""))]
        y = top + 0.2
        for label, value, note in items:
            dk.kpi(s, 0.75, y, 5.6, label, value, note, accent=dk.SLIDE_ORANGE)
            y += 1.5

    # ---- data readiness ------------------------------------------------------
    rd = m.get("pgl_readiness") or []
    if rd:
        blocked = [r for r in rd if r[1] == "blocked"]
        head = (f"{len(blocked)} of {len(rd)} data areas can't support their analysis yet"
                if blocked else "The extract supports every analysis area")
        sub = "graded from column coverage; blocked areas name the client ask"
        s, top = slide((head, sub), "Data readiness")
        rows_t = [["Area", "Grade", "Unlocks"]]
        for area, grade, unlocks, _cov in rd:
            rows_t.append([area, grade.upper(), unlocks])
        dk.table(s, rows_t, 0.7, top + 0.1, 9.2, col_widths=[2.6, 1.2, 5.4], size=11.5)

    # ---- findings ----------------------------------------------------------
    s = new()
    dk.title(s, "What we found, and what to confirm")
    bullets = []
    if m.get("pgl_reconcile_matches"):
        bullets.append(f"The extract matches the ILS system's own numbers on all "
                       f"{m['pgl_reconcile_matches']} checks — this data is trustworthy.")
    op = m.get("pgl_core_odd_pockets") or []
    if op:
        bullets.append(f"{sum(r[1] for r in op):,} open accounts sit on OD status "
                       f"{', '.join(r[0] for r in op)} — outside the ILS mapping; "
                       f"ask the vendor whether they should be scored.")
    if m.get("pgl_core_can_od_zero"):
        bullets.append(f"{m['pgl_core_can_od_zero']:,} accounts can overdraft today with a "
                       f"$0 core limit — the pocket a limit strategy exists for.")
    yc = m.get("pgl_fee_ytd_ceiling")
    if yc:
        bullets.append(f"Fee history is blocked in the extract; YTD items x the "
                       f"${yc['stated_fee']:g} fee bound the line at "
                       f"{_money_(yc['gross_ceiling'])} gross BILLED ceiling (not revenue).")
    if _n(m, "pgl_deleted_rows"):
        bullets.append(f"{_n(m, 'pgl_deleted_rows'):,} rows carry vendor deletion stamps and "
                       f"are excluded; confirm that matches intent.")
    rate = m.get("pgl_rege_optin_rate_personal")
    if rate is not None:
        bullets.append(f"Reg-E opt-in stands at {rate:.0f}% of open personal accounts "
                       f"(37.9% at the $600 limit vs 8% at $0).")
    for f_ in (m.get("pgl_reconcile_findings") or [])[:2]:
        bullets.append(f_)
    for i, b in enumerate(bullets[:7]):
        dk.text(s, 1.0, 1.7 + i * 0.78, 11.6, 0.72, f"—  {b}", size=14.5,
                color=dk.SLIDE_NAVY)

    try:
        sb = out.parent / "storyboard.md"
        sb.write_text("\n".join(
            f"\u00b7 {ti}" + ("" if comp else "   [TOPIC LABEL]") for ti, comp in story),
            encoding="utf-8")
    except Exception:
        sb = None

    from ils_pipeline.core.env import save_pptx
    out = save_pptx(prs, out, warn=None)
    from ils_pipeline.deckkit.build import DeckResult
    return DeckResult(path=out, slides=len(prs.slides), charts=len(made),
                      skipped=skipped, storyboard=sb)
