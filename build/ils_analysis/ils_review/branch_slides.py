"""
Branch deposit-behaviour slides, laid out natively for the 20 x 11.25 in canvas.

The previous version of these slides was designed for a 10 x 5.625 in deck and
pasted into the template at 2x, which left Calibri titles and half-size charts
next to the house slides. Here the geometry is written for the real canvas and
the type comes from the template, so the section reads as part of the deck.

The extra room is used rather than just scaled into: a full-width chart gets
~18.9 x 7.6 in, so charts carry 25 branches comfortably where the old deck
capped out around 12 before the labels collided.
"""
from __future__ import annotations

import os

from pptx.enum.text import PP_ALIGN

from . import branch_metrics as M
from . import charts as C
from . import theme as T
from .ils_data import count, money, pct

# Full-width chart box inside the content band.
CHART_X, CHART_W = 0.60, 18.80
CHART_Y = T.CONTENT_TOP + 0.10
CHART_H = T.CONTENT_BOTTOM - CHART_Y - 0.10

# Two-up chart boxes.
HALF_W = 9.20
HALF_L, HALF_R = 0.60, 10.20


def _rank_note(df, shown, label):
    total = len(df)
    if shown >= total:
        return f"All {total} branches with {label}s."
    return f"Top {shown} of {total} branches by {label} count."


# ── ranked bars: 60% chart, headline panel on the right ───────────────────────
BAR_W = 11.30                       # design inches: about 60% of the slide width
KEEP, MUTE = "navy", "steel"


def _short(name, n=22):
    t = str(name).strip()
    return t if len(t) <= n else t[:n - 1] + "."


def ranked_with_panel(dk, slide, df, col, top_n, *, series_name, fmt, fmtv, portfolio, port_label, lower,
                      higher_is_worse, number_format, unit):
    """A horizontal ranked bar chart at about 60% of the slide width and, on its right, the figures the
    chart is about: the portfolio figure, the highest and lowest branch and the spread between them, the
    three highest and three lowest branches with their account counts, and how much of the book the five
    largest branches hold. Only the three highest and three lowest bars carry colour; the rest are muted,
    so the slide is not a wall of one colour (Aaron, 2026-11-04). All figures are derived from `df`, the
    same table the chart is drawn from."""
    import shapes
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
    from . import client_slides as CS
    sel = (df.sort_values("n", ascending=False).head(top_n).dropna(subset=[col]).sort_values(col))
    if len(sel) < 4:
        C.bar(slide, CHART_X, CHART_Y, CHART_W, CHART_H, sel["branchname"].tolist(), sel[col].tolist(),
              series_name=series_name, color=T.NAVY, number_format=number_format)
        return sel
    k = 3
    hi_c, lo_c = (T.ORANGE, T.NAVY) if higher_is_worse else (T.NAVY, T.ORANGE)
    colors = [lo_c if i < k else hi_c if i >= len(sel) - k else T.STEEL_SOFT for i in range(len(sel))]
    C.bar(slide, CHART_X, CHART_Y, BAR_W, CHART_H, sel["branchname"].tolist(), sel[col].tolist(),
          series_name=series_name, color=T.STEEL_SOFT, number_format=number_format, colors=colors)
    hi, lo = sel.iloc[-1], sel.iloc[0]
    x0, w = 8.25, 12.833 - 8.25
    tw = (w - 0.15) / 2
    tiles = [(fmtv(portfolio), port_label),
             (f"{hi[col] / lo[col]:.1f}x" if lo[col] else "n/a", "Highest branch over lowest"),
             (fmtv(hi[col]), "Highest: " + _short(hi["branchname"], 16)),
             (fmtv(lo[col]), "Lowest: " + _short(lo["branchname"], 16))]
    for i, (v, lab) in enumerate(tiles):
        shapes.tile(slide, x0 + (i % 2) * (tw + 0.15), 1.75 + (i // 2) * 1.08, tw, 0.98, v, lab, small_label=True)
    top3 = sel.iloc[::-1].head(3)
    bot3 = sel.head(3)
    rows = [[_short(r["branchname"]), f"{int(r['n']):,}", fmtv(r[col])] for _, r in top3.iterrows()]
    rows += [[_short(r["branchname"]), f"{int(r['n']):,}", fmtv(r[col])] for _, r in bot3.iloc[::-1].iterrows()]
    T.band_real(slide, x0, 4.02, w, "THREE HIGHEST AND THREE LOWEST", h=0.34)
    CS.table(slide, {"headers": ["Branch", "Accounts", unit], "rows": rows}, x0, 4.42, w, 1.75, max_fs=12)
    big5 = sel.sort_values("n", ascending=False).head(5)["n"].sum()
    share = big5 / max(1, sel["n"].sum()) * 100
    above = int((sel[col] > portfolio).sum()) if portfolio is not None else 0
    T.bullets_real(slide, x0, 6.2, w, 0.55, [
        f"The five largest branches hold {share:.0f}% of the {lower} accounts shown; "
        f"{above} of {len(sel)} branches sit above the portfolio figure."], size=12, min_size=11)
    return sel


def add_branch_section(dk, cfg, loaded, accttype, *, section, cv=None, divider=False,
                       progress=None):
    """Build the whole branch section for one account type. Returns notes."""
    say = progress or (lambda m: None)
    za = loaded.zaccounts
    notes = []
    top_n = cfg.top_n_personal if accttype == "Personal" else cfg.top_n_business
    lower = accttype.lower()

    intensity = M.deposit_intensity_engagement(za, accttype)
    if intensity.empty:
        return [f"No open {lower} accounts found in the branch scope — branch "
                f"section skipped."]
    od = M.overdraft_activity(za, accttype)
    summary = M.portfolio_summary(za, accttype)
    vol = M.deposit_volatility(za, loaded.ztrend, accttype,
                               cfg.min_periods_for_volatility, cv=cv)
    year = cfg.growth_year or M.latest_full_year(za, loaded.snapshot)
    growth = M.account_growth(za, year, accttype)

    # ── divider (only when the template isn't already introducing us) ──────
    if divider:
        bits = ["deposit intensity", "engagement"]
        if vol is not None:
            bits.append("volatility")
        bits.append("overdraft activity")
        dk.divider(
            "Branch Overdraft and\nDeposit Behavior",
            eyebrow=f"{dk.client} — {accttype} Accounts",
            blurb=f"{', '.join(bits[:-1])} and {bits[-1]} by branch, "
                  f"across {summary['n_branches']} branches.",
            section=section,
        )

    # ── executive overview ─────────────────────────────────────────────────
    say(f"  {accttype}: executive overview…")
    _slide_overview(dk, cfg, loaded, accttype, summary, intensity, od, vol, growth,
                    year, section=section)

    # ── deposit intensity ──────────────────────────────────────────────────
    labels, values = M.top_branches(intensity, "avg_dep_per_acct", top_n)
    s = dk.content(f"{accttype} accounts — deposit intensity by branch",
                   f"Average 33-day deposit per open account.  "
                   f"{_rank_note(intensity, len(labels), lower + ' account')}",
                   section=section)
    ranked_with_panel(dk, s, intensity, "avg_dep_per_acct", top_n, series_name="Avg deposit / account",
                      fmt="", fmtv=lambda v: f"${v:,.0f}", portfolio=summary["avg_dep_per_acct"],
                      port_label="Portfolio average", lower=lower, higher_is_worse=False,
                      number_format='"$"#,##0', unit="Avg deposit")

    # ── engagement ─────────────────────────────────────────────────────────
    labels, values = M.top_branches(intensity, "pct_no_deposit", top_n)
    s = dk.content(f"{accttype} accounts — engagement by branch",
                   "Share of open accounts with no deposit activity in the trailing 33 days. "
                   "Higher is worse.",
                   section=section)
    ranked_with_panel(dk, s, intensity, "pct_no_deposit", top_n, series_name="No-deposit rate",
                      fmt="", fmtv=lambda v: f"{v:.1f}%", portfolio=summary["pct_no_deposit"],
                      port_label="Portfolio rate", lower=lower, higher_is_worse=True,
                      number_format='0.0"%"', unit="No-deposit")

    # ── volatility ─────────────────────────────────────────────────────────
    if vol is not None:
        labels, values = M.top_branches(vol, "median_cv", top_n)
        s = dk.content(f"{accttype} accounts — deposit volatility by branch",
                       f"Median coefficient of variation of each account's rolling 33-day "
                       f"deposit total, for accounts with "
                       f"{cfg.min_periods_for_volatility}+ observations. Higher is more erratic.",
                       section=section)
        ranked_with_panel(dk, s, vol, "median_cv", top_n, series_name="Median CV",
                          fmt="", fmtv=lambda v: f"{v:.2f}", portfolio=float(vol["median_cv"].median()),
                          port_label="Median across branches", lower=lower, higher_is_worse=True,
                          number_format="0.00", unit="Median CV")
    else:
        notes.append(f"Deposit volatility for {lower} accounts was skipped — "
                     f"no ZTrend file, or too few accounts with "
                     f"{cfg.min_periods_for_volatility}+ notice observations.")

    if getattr(cfg, "branch_core_only", True):
        return notes            # the story keeps the overview and the three ranked charts; the rest is in the full build
    # ── overdraft activity (two-up) ────────────────────────────────────────
    fee_labels, fee_values = M.top_branches(od, "avg_fee_per_user", top_n)
    pres_labels, pres_values = M.top_branches(od, "pct_presented", top_n)
    s = dk.content(f"{accttype} accounts — overdraft activity by branch",
                   '"Users" = an open account with at least one item paid into overdraft or '
                   'returned in the trailing 12 months.',
                   section=section)
    T.textbox(s, HALF_L, CHART_Y, HALF_W, 0.34,
              "Fees collected per user ($)", 13, bold=True, color=T.NAVY)
    C.bar(s, HALF_L, CHART_Y + 0.38, HALF_W, CHART_H - 0.38, fee_labels, fee_values,
          series_name="Avg fees / user", color=T.PURPLE, number_format='"$"#,##0')
    T.textbox(s, HALF_R, CHART_Y, HALF_W, 0.34,
              "Share of accounts that presented an item (%)", 13, bold=True, color=T.NAVY)
    C.bar(s, HALF_R, CHART_Y + 0.38, HALF_W, CHART_H - 0.38, pres_labels, pres_values,
          series_name="% presented", color=T.CORAL, number_format='0.0"%"')

    # ── growth & activation (two-up) ───────────────────────────────────────
    if growth is not None and len(growth):
        g_labels, g_values = M.top_branches(growth, "new_accounts", top_n)
        f_top = (growth.sort_values("new_accounts", ascending=False).head(top_n)
                 .sort_values("pct_made_deposit"))
        s = dk.content(f"{year} account growth & deposit activation",
                       f"New {lower} accounts opened in {year}, and the share that have made "
                       f"at least one deposit since.",
                       section=section)
        T.textbox(s, HALF_L, CHART_Y, HALF_W, 0.34,
                  f"New {lower} accounts opened, {year}", 13, bold=True, color=T.NAVY)
        C.bar(s, HALF_L, CHART_Y + 0.38, HALF_W, CHART_H - 0.38, g_labels, g_values,
              series_name=f"New accounts {year}", color=T.NAVY, number_format="#,##0")
        T.textbox(s, HALF_R, CHART_Y, HALF_W, 0.34,
                  "Share that made a deposit (%)", 13, bold=True, color=T.NAVY)
        C.bar(s, HALF_R, CHART_Y + 0.38, HALF_W, CHART_H - 0.38,
              f_top["branchname"].tolist(), f_top["pct_made_deposit"].tolist(),
              series_name="% funded", color=T.TEAL, number_format='0.0"%"')
    else:
        notes.append(f"{year} account growth for {lower} accounts was skipped — "
                     f"no accounts with an opendate in {year}.")

    # ── deposit-health tiers (box plot) ────────────────────────────────────
    tiers = M.deposit_health_tiers(za, loaded.ztrend, accttype,
                                   cfg.min_periods_for_volatility, cv=cv)
    if tiers is not None:
        say(f"  {accttype}: rendering deposit-health box plot…")
        img = C.deposit_health_boxplot(
            tiers, os.path.join(dk.chart_dir, f"health_{accttype}.png"))
        s = dk.content("Overdraft activity by deposit-health tier",
                       f"{accttype} accounts grouped by deposit engagement and deposit "
                       f"volatility. Outliers suppressed; diamond marks the mean.",
                       section=section)
        T.image(s, img, 0.60, CHART_Y, 12.60, CHART_H)
        T.band_label(s, 13.55, CHART_Y, 5.85, "HOW TO READ IT")
        T.bullets(s, 13.60, CHART_Y + 0.62, 5.80, CHART_H - 0.70, [
            "Volatility is the coefficient of variation of each account's rolling "
            "33-day deposit total; accounts are split into terciles of it.",
            "Accounts with no 33-day deposit activity are shown separately — they "
            "have no deposit stream to be volatile about.",
            "Compare the mean and median markers across tiers: if erratic depositors "
            "carry more fee activity than stable ones, deposit stability is the "
            "signal to act on, not deposit size.",
        ], 12.5)
    elif loaded.has_trend:
        notes.append(f"The {lower} deposit-health box plot was skipped — too few "
                     f"accounts with enough notice history to form volatility terciles.")

    # ── repayment-trend segment ────────────────────────────────────────────
    seg = M.repayment_trend_segment(za, accttype)
    if seg is not None:
        _slide_repayment(dk, seg, accttype, section=section)
    else:
        notes.append(f"The {lower} repayment-trend segment was skipped — "
                     f"avgrepaymentrate / items365 not populated in this export.")

    return notes


# ── individual slides ───────────────────────────────────────────────────────
def _slide_overview(dk, cfg, loaded, accttype, summary, intensity, od, vol, growth,
                    year, *, section):
    s = dk.content(f"{accttype} branch behaviour — executive overview",
                   f"Open {accttype.lower()} accounts across {summary['n_branches']} "
                   f"{'branches and digital channels' if cfg.include_digital else 'retail branches'}"
                   f", as of {dk.date_str}.",
                   section=section)

    cards = [
        (count(summary["n_open"]), f"Open {accttype.lower()} accounts",
         f"{money(summary['avg_dep_per_acct'])} avg 33-day deposit"),
        (pct(summary["pct_no_deposit"]), "No-deposit rate",
         "No deposit in the trailing 33 days"),
        (pct(summary["pct_presented"]), "Presented an item",
         f"{count(summary['n_presented'])} accounts, trailing 12mo"),
        (money(summary["avg_fee_per_user"]), "Fees per user",
         f"{money(summary['fee_income'])} collected in total"),
    ]
    if vol is not None:
        med = vol["median_cv"].median()
        cards.append((f"{med:.2f}", "Median deposit volatility",
                      "Coefficient of variation (CV)"))
    elif summary["median_od_limit"] is not None:
        cards.append((money(summary["median_od_limit"]), "Median ILS limit",
                      "Across open accounts"))
    T.kpi_cards(s, T.MARGIN_L, T.CONTENT_TOP + 0.05, T.CONTENT_W, 2.35, cards)

    y = T.CONTENT_TOP + 2.70
    obs = []
    hi = intensity.sort_values("avg_dep_per_acct", ascending=False).iloc[0]
    lo = intensity.sort_values("avg_dep_per_acct").iloc[0]
    obs.append(f"Deposit intensity ranges {money(lo['avg_dep_per_acct'])} "
               f"({lo['branchname']}) to {money(hi['avg_dep_per_acct'])} "
               f"({hi['branchname']}) per account across branches.")
    eng_hi = intensity.sort_values("pct_no_deposit", ascending=False).iloc[0]
    obs.append(f"No-deposit rates run {intensity['pct_no_deposit'].min():.1f}% to "
               f"{intensity['pct_no_deposit'].max():.1f}%; {eng_hi['branchname']} is "
               f"highest at {eng_hi['pct_no_deposit']:.1f}%.")
    od_hi = od.dropna(subset=["avg_fee_per_user"])
    if len(od_hi):
        od_hi = od_hi.sort_values("avg_fee_per_user", ascending=False).iloc[0]
        obs.append(f"{od_hi['branchname']} shows the highest fees per user at "
                   f"{money(od_hi['avg_fee_per_user'])}, with "
                   f"{od_hi['pct_presented']:.1f}% of its accounts presenting an item.")
    if growth is not None and len(growth):
        g = growth.iloc[0]
        total_new = int(growth["new_accounts"].sum())
        funded = growth["made_deposit"].sum() / max(1, total_new) * 100
        obs.append(f"{count(total_new)} {accttype.lower()} accounts opened in {year}, "
                   f"{funded:.1f}% of which have since made a deposit; "
                   f"{g['branchname']} led with {count(g['new_accounts'])}.")

    watch = []
    gap = intensity.copy()
    gap = gap[gap["n"] >= 100]
    if len(gap) >= 3:
        gap["rank_int"] = gap["avg_dep_per_acct"].rank(ascending=False)
        gap["rank_eng"] = gap["pct_no_deposit"].rank(ascending=False)
        gap["spread"] = gap["rank_eng"] - gap["rank_int"]
        w = gap.sort_values("spread", ascending=False).iloc[0]
        watch.append(f"{w['branchname']} pairs strong deposit intensity "
                     f"({money(w['avg_dep_per_acct'])}/account) with a high no-deposit rate "
                     f"({w['pct_no_deposit']:.1f}%) — a few large accounts may be masking a "
                     f"less-engaged base.")
    if vol is not None and len(vol) >= 3:
        v = vol.sort_values("median_cv", ascending=False).iloc[0]
        watch.append(f"{v['branchname']} carries the most erratic deposit behaviour "
                     f"(median CV {v['median_cv']:.2f}); check it against the fee-per-user "
                     f"ranking to see whether volatility is converting into fee activity.")
    if growth is not None and len(growth) >= 3:
        weak = growth[growth["new_accounts"] >= 25].sort_values("pct_made_deposit")
        if len(weak):
            w = weak.iloc[0]
            watch.append(f"{w['branchname']} funded only {w['pct_made_deposit']:.1f}% of its "
                         f"{count(w['new_accounts'])} new {year} accounts — an onboarding "
                         f"follow-up opportunity.")
    if not watch:
        watch.append("No branch stands out as an outlier on the measures above.")

    T.two_column_text(s, y, "WHAT THE DATA SHOWS", obs, "WHERE TO LOOK NEXT", watch,
                      size=16, h=T.CONTENT_BOTTOM - y)
    return s


def _slide_repayment(dk, seg, accttype, *, section):
    s = dk.content("Repayment trend — account segment analysis",
                   f"{accttype} accounts with item activity and a computable repayment rate, "
                   f"trailing 365 days.",
                   section=section)
    C.column(s, 0.60, T.CONTENT_TOP + 0.45, 11.90, T.CONTENT_H - 0.55,
             [f"{l} days" for l in seg.band_labels], seg.band_counts,
             series_name="Accounts", color=T.PURPLE, number_format="#,##0")
    T.textbox(s, 0.60, T.CONTENT_TOP + 0.05, 11.90, 0.34,
              "Accounts by repayment-rate band", 13, bold=True, color=T.NAVY)

    T.band_label(s, 12.85, T.CONTENT_TOP + 0.05, 6.55, "SEGMENT PROFILE")
    items = [
        f"{count(seg.n_qualifying)} {accttype.lower()} accounts qualify as trend-impacted — "
        f"{seg.pct_of_item_active}% of the {count(seg.n_item_active)} accounts with any item "
        f"activity in 365 days.",
    ]
    if seg.median_repayment_days is not None:
        items.append(f"Median repayment rate {seg.median_repayment_days:.1f} days; "
                     f"{seg.pct_within_10_days}% repay within 10 days.")
    if seg.median_od_limit is not None:
        items.append(f"Median current ILS limit for the segment: {money(seg.median_od_limit)}.")
    if seg.median_negative_balance is not None:
        items.append(f"{seg.pct_negative_balance}% carry a negative average collected "
                     f"balance, at a median of "
                     f"-{money(abs(seg.median_negative_balance))[1:]}.")
    items.append(
        "RepaymentTrendCount33 (the intended direct trend-fire counter) is populated in this "
        "extract." if seg.direct_field_populated else
        "RepaymentTrendCount33 (the intended direct trend-fire counter) is empty in this "
        "extract, as in every prior extract seen, so 'avgrepaymentrate is not null' is used "
        "as the working proxy for a trend fire."
    )
    T.bullets(s, 12.90, T.CONTENT_TOP + 0.67, 6.45, T.CONTENT_H - 0.75, items, 15)
    return s
