"""
Slides from the DBIC (Daily Batch Integrity Check) export.

Seven slides covering what the other exports can't show: whether the nightly
ILS calculation is actually running clean, whether the data feeding it is
intact, how much of the fee opportunity is being collected, and where the
exception volume comes from.

Two of these — Reg E opt-in / eligibility by account type, and exception items
by channel — are the numbers behind house slides that are pasted in by hand
today, so they now come straight out of the export.
"""
from __future__ import annotations

import re

from pptx.enum.text import PP_ALIGN

from . import charts as C
from . import theme as T
from .ils_data import count, money, pct

X = 0.42
W = T.SLIDE_W - 2 * X


def _fmt_date(d):
    return d.strftime("%m/%d") if d is not None else "—"


def _group_digits(text):
    """Thousands-separate bare long integers in note text carried over verbatim.

    The export writes advisories like "There are 216532935 calculated limits
    before 06/22/2026" — unreadable on a slide. Only runs of 5+ digits with no
    adjacent digit, slash, comma or period are touched, so dates and already
    formatted figures are left alone.
    """
    return re.sub(r"(?<![\d/.,])\d{5,}(?![\d/.,])",
                  lambda m: f"{int(m.group()):,}", str(text))


def _fmt_override_value(v):
    """Override limit value, with the export's '-0' normalised to '0'."""
    s = str(v or "").strip()
    if not s:
        return "—"
    try:
        f = float(s)
    except ValueError:
        return s
    return "0" if f == 0 else f"{f:,.0f}"


def _delta(a, b, *, money_fmt=False, dp=0):
    """A signed change string, or '—' when either end is missing."""
    if a is None or b is None:
        return "—"
    diff = b - a
    sign = "+" if diff > 0 else ""
    body = (f"${abs(diff):,.0f}" if money_fmt else f"{abs(diff):,.{dp}f}")
    return f"{'−' if diff < 0 else sign}{body}"


def add_dbic_section(dk, d, *, section, divider=False, progress=None):
    """Every DBIC slide. Returns notes."""
    say = progress or (lambda m: None)
    if not d.available:
        return ["The DBIC export could not be parsed — no recognised sections, so the "
                "program-health slides were skipped."]
    notes = []

    if divider:
        dk.divider("Program Health\n& Data Integrity",
                   eyebrow=f"{dk.client} — Daily Batch Integrity Check",
                   blurb="Nightly calculation health, feed integrity, eligibility, "
                         "and fee collection from the DBIC export.",
                   section=section)

    say("  DBIC: program health…")
    _health(dk, d, section=section)
    if d.calc and d.calc.n_runs:
        _limit_trend(dk, d, section=section)
    else:
        notes.append("The DBIC export carries no ILS calculation run log, so the limit "
                     "trend slide was skipped.")
    if d.elig and d.elig.rows:
        _eligibility(dk, d, section=section)
    else:
        notes.append("The DBIC export carries no opt-in/eligibility table, so that "
                     "slide was skipped.")
    if d.notices and d.notices.dates:
        _fees(dk, d, section=section)
    if d.channels and d.channels[1]:
        _channels(dk, d, section=section)
    if d.deposits and d.deposits.dates:
        _feeds(dk, d, section=section)
    if d.limits.get("by_limit"):
        _limits(dk, d, section=section)

    # surface the data-quality findings as deck notes too
    if d.errors:
        total = sum(g["n"] for g in d.errors)
        notes.append(f"The DBIC data-integrity check reported {total} exception(s) "
                     f"across {len(d.errors)} distinct condition(s) — see the Program "
                     f"Health slide. These are import-side data issues to clear with "
                     f"the core.")
    if d.calc and d.calc.errors:
        notes.append(f"{len(d.calc.errors)} nightly ILS calculation run(s) reported an "
                     f"error message in the DBIC log.")
    return notes


# ── 1. program health ───────────────────────────────────────────────────────
def _health(dk, d, *, section):
    c, e = d.calc, d.elig
    window = ""
    if c and c.first and c.last:
        window = f"  ·  calculation log {_fmt_date(c.first)}–{_fmt_date(c.last)}"
    slide = dk.content("ILS program health & data integrity",
                       f"From the Daily Batch Integrity Check export{window}",
                       section=section)

    n_err = sum(g["n"] for g in d.errors)
    cards = [
        (pct(c.success_rate) if c and c.success_rate is not None else "—",
         "Calculation success rate",
         f"{c.n_runs} nightly run(s) in the log" if c else "no run log"),
        (count(c.accounts[-1]) if c and c.accounts and c.accounts[-1] else "—",
         "Accounts calculated", "Most recent nightly run"),
        (money(c.avg_limit[-1]) if c and c.avg_limit and c.avg_limit[-1] else "—",
         "Average granted limit",
         _delta(c.avg_limit[0], c.avg_limit[-1], money_fmt=True) + " over the window"
         if c and c.avg_limit else ""),
        (pct(c.zero_limit_pct) if c and c.zero_limit_pct is not None else "—",
         "Granted a zero limit",
         f"{count(c.zero_limit[-1])} accounts" if c and c.zero_limit else ""),
        (count(n_err) if n_err else "None",
         "Data integrity exceptions",
         "Clean import" if not n_err else f"{len(d.errors)} distinct condition(s)"),
    ]
    T.kpi_cards(slide, T.MARGIN_L, T.CONTENT_TOP + 0.05, T.CONTENT_W, 2.25, cards,
                accent=T.GREEN if not n_err else T.CORAL)

    y = T.CONTENT_TOP + 2.55
    lw = 11.6
    T.band_label(slide, X, y, lw, "  DATA INTEGRITY CHECK")
    if d.errors:
        # The export packs multi-column checks into one pipe-joined value; without
        # the spaces the cell wraps mid-identifier.
        rows = [[g["desc"][:120], g["table"] or "—",
                 ", ".join(sorted(g["columns"])[:3]).replace("|", ", ") or "—",
                 count(g["n"])]
                for g in d.errors[:9]]
        rh = min(0.52, max(0.30, (T.CONTENT_BOTTOM - y - 0.6) / max(1, len(rows))))
        tbl = dk.table(slide, X, y + 0.50, lw, [6.4, 1.8, 2.0, 1.4], len(rows) + 1,
                       row_h=rh)
        T.fill_table(tbl, ["Condition", "Table", "Column", "Rows"], rows,
                     size=min(14, rh * 24),
                     align=[PP_ALIGN.LEFT, PP_ALIGN.LEFT, PP_ALIGN.LEFT,
                            PP_ALIGN.RIGHT])
    else:
        box = T.rect(slide, X, y + 0.50, lw, 1.15, T.BAND,
                     line=T.GREEN, line_w=1.0)
        T.textbox(slide, X + 0.35, y + 0.78, lw - 0.7, 0.6,
                  "No data integrity exceptions — every checked field passed on this "
                  "import.", 14, bold=True, color=T.GREEN)

    # advisories + housekeeping on the right
    rx = X + lw + 0.5
    rw = T.SLIDE_W - rx - X
    T.band_label(slide, rx, y, rw, "  OPERATIONAL NOTES")
    items = []
    if c and c.median_runtime_min is not None:
        items.append(f"Median nightly calculation runtime {c.median_runtime_min:.1f} "
                     f"minutes across {c.n_runs} runs.")
    if c and c.overrides and c.overrides[-1] is not None:
        items.append(f"{count(c.overrides[-1])} override(s) applied in the latest run.")
    if e and e.optin_rate is not None:
        items.append(f"Reg E opt-in stands at {pct(e.optin_rate)} of "
                     f"{count(e.total_accts)} accounts on file.")
    for n in d.notes[:4]:
        items.append(_group_digits(n))
    if d.deleted:
        biggest = max(d.deleted, key=lambda t: t[1])
        items.append(f"{count(biggest[1])} accounts carry the largest single "
                     f"deleted-flag batch in the history table.")
    T.bullets(slide, rx + 0.05, y + 0.62, rw - 0.1, T.CONTENT_BOTTOM - y - 0.70,
              items, 12)
    return slide


# ── 2. limit & calculation trend ────────────────────────────────────────────
def _limit_trend(dk, d, *, section):
    c = d.calc
    slide = dk.content("ILS calculation log — limit and override trend",
                       f"One point per nightly run, {_fmt_date(c.first)}–"
                       f"{_fmt_date(c.last)}. The average granted limit is the engine's "
                       f"own figure, not a recomputation.",
                       section=section)
    labels = [_fmt_date(x) for x in c.dates]
    tick = max(1, len(labels) // 12)
    y = T.CONTENT_TOP + 0.05
    h = T.CONTENT_H - 0.15

    T.textbox(slide, X, y, 9.3, 0.34, "Average granted limit ($)", 16,
              bold=True, color=T.NAVY)
    C.line(slide, X, y + 0.38, 9.3, h - 0.38, labels,
           [("Average limit", c.avg_limit, T.NAVY)],
           number_format='"$"#,##0', legend=False, tick_every=tick)

    rx = X + 9.6
    T.textbox(slide, rx, y, 9.3, 0.34,
              "Accounts calculated, zero-limit accounts, and overrides", 13,
              bold=True, color=T.NAVY)
    C.line(slide, rx, y + 0.38, 9.3, h - 0.38, labels, [
        ("Accounts calculated", c.accounts, T.BLUE_2),
        ("Zero limit", c.zero_limit, T.CORAL),
        ("Overrides applied", c.overrides, T.ORANGE),
    ], number_format="#,##0", tick_every=tick)

    bits = []
    t = c.trend(c.avg_limit)
    if t:
        bits.append(f"Average limit moved {_delta(t[0], t[1], money_fmt=True)} "
                    f"({money(t[0])} → {money(t[1])}).")
    t = c.trend(c.accounts)
    if t:
        bits.append(f"Accounts calculated {_delta(t[0], t[1])}.")
    if c.zero_limit_pct is not None:
        bits.append(f"{pct(c.zero_limit_pct)} of calculated accounts currently "
                    f"receive a zero limit.")
    if bits:
        T.footnote(slide, "  ".join(bits))
    return slide


# ── 3. eligibility & Reg E ──────────────────────────────────────────────────
def _eligibility(dk, d, *, section):
    e = d.elig
    slide = dk.content("Eligibility & Reg E opt-in by account type",
                       "Straight from the DBIC export: accounts on file, open/active, "
                       "ILS-eligible, and opted in to Reg E.",
                       section=section)
    y = T.CONTENT_TOP
    lw = 11.4
    T.band_label(slide, X, y, lw, "  ACCOUNTS, ELIGIBILITY AND OPT-IN")
    headers = ["Account Type", "Total Accts", "Open/Active", "Open %",
               "ILS Eligible", "Eligible %", "Reg E Opt-In", "Opt-In %"]
    rows = []
    for r in sorted(e.rows, key=lambda r: -(r["total"] or 0)):
        rows.append([r["type"], count(r["total"]), count(r["open"]),
                     pct(r["open_pct"]), count(r["eligible"]),
                     pct(r["eligible_pct"]), count(r["optin"]),
                     pct(r["optin_pct"])])
    rows.append(["All types", count(e.total_accts), count(e.total_open),
                 "—", count(e.total_eligible), pct(e.eligible_rate),
                 count(e.total_optin), pct(e.optin_rate)])
    tbl = dk.table(slide, X, y + 0.50, lw, [2.4, 1.5, 1.5, 1.1, 1.5, 1.2, 1.5, 1.1],
                   len(rows) + 1, row_h=0.48)
    T.fill_table(tbl, headers, rows, size=14,
                 align=[PP_ALIGN.LEFT] + [PP_ALIGN.RIGHT] * 7)
    last = len(rows)
    for j in range(len(headers)):
        cell = tbl.cell(last, j)
        cell.fill.solid()
        cell.fill.fore_color.rgb = T.BAND
        for p in cell.text_frame.paragraphs:
            for run in p.runs:
                run.font.bold = True

    # opt-in vs eligibility chart
    cy = y + 0.50 + 0.48 * len(rows) + 0.44 + 0.35
    types = [r["type"] for r in e.rows]
    if types and cy < T.CONTENT_BOTTOM - 1.0:
        T.textbox(slide, X, cy, lw, 0.34, "Open, eligible and opted-in rates by type",
                  13, bold=True, color=T.NAVY)
        C.grouped_column(
            slide, X, cy + 0.38, lw, T.CONTENT_BOTTOM - cy - 0.42, types, [
                ("Open %", [r["open_pct"] for r in e.rows], T.BLUE_2),
                ("Eligible %", [r["eligible_pct"] for r in e.rows], T.TEAL),
                ("Reg E opt-in %", [r["optin_pct"] for r in e.rows], T.ORANGE),
            ], number_format='0"%"')

    rx = X + lw + 0.5
    rw = T.SLIDE_W - rx - X
    T.band_label(slide, rx, y, rw, "  READ")
    items = []
    per = {r["type"]: r for r in e.rows}
    lowest = min((r for r in e.rows if r["optin_pct"] is not None),
                 key=lambda r: r["optin_pct"], default=None)
    highest = max((r for r in e.rows if r["optin_pct"] is not None),
                  key=lambda r: r["optin_pct"], default=None)
    if lowest is not None and highest is not None and lowest is not highest:
        items.append(f"{highest['type']} opt-in runs {pct(highest['optin_pct'])} against "
                     f"{lowest['type']} at {pct(lowest['optin_pct'])} — a "
                     f"{abs((highest['optin_pct'] or 0) - (lowest['optin_pct'] or 0)):.0f} "
                     f"point gap, and the clearest Reg E opportunity in the portfolio.")
    # Against accounts on file, matching the export's own opt-in denominator —
    # opt-in counts are not restricted to open accounts and can exceed them.
    if lowest is not None and lowest["total"] and lowest["optin"]:
        gap = int(lowest["total"] - lowest["optin"])
        if gap > 0:
            items.append(f"{count(gap)} {lowest['type']} accounts on file are not opted "
                         f"in; at the current opt-in rate every point of improvement is "
                         f"about {count(round(lowest['total'] / 100))} accounts.")
    for r in e.rows:
        if r["eligible_pct"] is not None and r["eligible_pct"] < 90:
            items.append(f"{r['type']} ILS eligibility is {pct(r['eligible_pct'])} — "
                         f"{count((r['total'] or 0) - (r['eligible'] or 0))} accounts sit "
                         f"outside the matrix, worth checking against the OD status "
                         f"codes and product mapping.")
    if d.status_codes:
        items.append(f"{len(d.status_codes)} OD status code(s) carry account counts in "
                     f"this export; the matrix section lists their calc/eligibility "
                     f"flags.")
    T.bullets(slide, rx + 0.05, y + 0.62, rw - 0.1, T.CONTENT_BOTTOM - y - 0.70,
              items, 12)
    return slide


# ── 4. fee collection ───────────────────────────────────────────────────────
def _fees(dk, d, *, section):
    n, f = d.notices, d.fees
    slide = dk.content("Notice items & fee collection",
                       f"Daily NSF/OD notice items over {len(n.dates)} days, with fees "
                       f"assessed against fees available.",
                       section=section)
    cards = [
        (pct(f["collection_rate"]), "Fee collection rate",
         "Assessed ÷ possible over the window"),
        (money(f["fees_assessed"]), "Fees assessed",
         f"of {money(f['fees_possible'])} possible"),
        (money(f["forgone"]), "Fees not collected",
         "Waived, refunded or below threshold"),
        (pct(f["pay_ratio"]), "Pay ratio",
         f"{count(f['paid_items'])} of {count(f['items'])} items paid"),
        (count(n.mean_business("Account_Count")), "Accounts per business day",
         "Presenting a notice item"),
    ]
    T.kpi_cards(slide, T.MARGIN_L, T.CONTENT_TOP + 0.05, T.CONTENT_W, 2.25, cards)

    y = T.CONTENT_TOP + 2.55
    h = T.CONTENT_BOTTOM - y
    bdates, bvals = n.business_only("Possible_Fees", "Fees_Assessed")
    labels = [_fmt_date(x) for x in bdates]
    tick = max(1, len(labels) // 12)
    T.textbox(slide, X, y, 12.6, 0.34,
              "Fees assessed vs. fees possible, per business day", 13,
              bold=True, color=T.NAVY)
    C.line(slide, X, y + 0.38, 12.6, h - 0.42, labels, [
        ("Fees possible", bvals["Possible_Fees"], T.RULE),
        ("Fees assessed", bvals["Fees_Assessed"], T.NAVY),
    ], number_format='"$"#,##0', tick_every=tick)

    rx = X + 12.9
    rw = T.SLIDE_W - rx - X
    T.band_label(slide, rx, y, rw, "  READ")
    items = []
    if f["collection_rate"] is not None:
        if f["collection_rate"] < 85:
            verdict = ("a material gap between the fees the program could assess and "
                       "what it actually collected")
        elif f["collection_rate"] >= 99.5:
            verdict = ("the whole available fee opportunity being assessed — no waiver, "
                       "refund or de minimis reduction is reaching the numbers in this "
                       "window")
        else:
            verdict = "close to full collection of the available fee opportunity"
        items.append(f"A {pct(f['collection_rate'])} collection rate is {verdict}.")
    if f["forgone"] > 0:
        items.append(f"{money(f['forgone'])} of assessable fees were not collected over "
                     f"the window — check waiver settings, refund strategies and "
                     f"de minimis thresholds before reading this as leakage.")
    if f["pay_ratio"] is not None:
        items.append(f"{pct(f['pay_ratio'])} of presented items were paid rather than "
                     f"returned, which is what the ILS limit is there to enable.")
    per_day = n.mean_business("Item_Count")
    if per_day:
        items.append(f"{count(per_day)} notice items on an average business day, across "
                     f"{count(n.mean_business('Account_Count'))} accounts.")
    T.bullets(slide, rx + 0.05, y + 0.62, rw - 0.1, h - 0.70, items, 15)
    return slide


# ── 5. channel mix ──────────────────────────────────────────────────────────
def _channels(dk, d, *, section):
    mix, totals = d.channels
    slide = dk.content("Exception items by channel",
                       "Paid and returned items over the trailing 60 days, split by "
                       "presentment channel and account type.",
                       section=section)
    chans = sorted(totals, key=lambda c: -totals[c])
    types = sorted({t for (t, _) in mix})
    y = T.CONTENT_TOP + 0.05
    h = T.CONTENT_H * 0.62

    series = []
    palette = [T.NAVY, T.TEAL, T.PURPLE, T.BLUE_2, T.GREEN]
    for i, t in enumerate(types):
        for kind, shade in (("PD", palette[i % len(palette)]),
                            ("RT", T.CORAL if i == 0 else T.ORANGE)):
            row = mix.get((t, kind))
            if not row or not any(row.get(c) for c in chans):
                continue
            series.append((f"{t} — {'paid' if kind == 'PD' else 'returned'}",
                           [row.get(c, 0) for c in chans], shade))
    if series:
        T.textbox(slide, X, y, W, 0.34, "Items by channel", 16, bold=True, color=T.NAVY)
        C.grouped_column(slide, X, y + 0.38, W, h - 0.38, chans, series,
                         number_format="#,##0")

    ty = y + h + 0.30
    headers = ["Account Type", "Paid / Returned"] + chans + ["Total"]
    rows = []
    for t in types:
        for kind in ("PD", "RT"):
            row = mix.get((t, kind))
            if not row:
                continue
            vals = [row.get(c, 0) for c in chans]
            rows.append([t, "Paid" if kind == "PD" else "Returned"]
                        + [count(v) if v else "—" for v in vals]
                        + [count(sum(vals))])
    if rows and ty < T.CONTENT_BOTTOM - 0.6:
        widths = [2.2, 2.0] + [1.35] * len(chans) + [1.5]
        rh = min(0.44, max(0.28, (T.CONTENT_BOTTOM - ty - 0.5) / max(1, len(rows))))
        tbl = dk.table(slide, X, ty, W, widths, len(rows) + 1, row_h=rh)
        T.fill_table(tbl, headers, rows, size=min(14, rh * 26),
                     align=[PP_ALIGN.LEFT, PP_ALIGN.LEFT]
                     + [PP_ALIGN.RIGHT] * (len(chans) + 1))
    top = chans[0] if chans else None
    if top:
        share = totals[top] / (sum(totals.values()) or 1) * 100
        T.footnote(slide, f"{top} is the largest exception channel at "
                          f"{pct(share)} of all items in the window. Channels with no "
                          f"activity are omitted.")
    return slide


# ── 6. daily feeds ──────────────────────────────────────────────────────────
def _feeds(dk, d, *, section):
    dep, od, dec = d.deposits, d.od, d.declines
    slide = dk.content("Daily data feeds — deposits, overdrafts and declines",
                       f"{len(dep.dates)} days of feed activity. Weekends are expected "
                       f"to be zero; a zero on a business day is a feed gap.",
                       section=section)
    gaps = dep.zero_business_days("DepositCount")
    cards = [
        (count(dep.mean_business("DepositCount")), "Deposits per business day",
         money(dep.mean_business("DepositSum")) + " per day"),
        (count(dep.series.get("Accounts w/o a Deposit in the last 20 days", [None])[-1]),
         "No deposit in 20 days", "Most recent day in the feed"),
        (count(od.mean_business("Account_Count")) if od.dates else "—",
         "Accounts overdrawn / day", "Business-day average"),
        (count(dec.total("Decline_Count")) if dec.dates else "—",
         "Debit declines in window",
         f"avg {money(dec.mean_business('Average_Tran_Amount'))} per attempt"
         if dec.dates else ""),
        ("None" if not gaps else count(len(gaps)), "Business-day feed gaps",
         "Days with no deposits reported"),
    ]
    T.kpi_cards(slide, T.MARGIN_L, T.CONTENT_TOP + 0.05, T.CONTENT_W, 2.25, cards,
                accent=T.GREEN if not gaps else T.CORAL)

    y = T.CONTENT_TOP + 2.55
    h = T.CONTENT_BOTTOM - y
    NODEP = "Accounts w/o a Deposit in the last 20 days"
    bdates, bvals = dep.business_only("DepositCount", NODEP)
    labels = [_fmt_date(x) for x in bdates]
    tick = max(1, len(labels) // 12)
    T.textbox(slide, X, y, 9.3, 0.34, "Deposits per business day", 16, bold=True,
              color=T.NAVY)
    C.line(slide, X, y + 0.38, 9.3, h - 0.42, labels,
           [("Deposits", bvals["DepositCount"], T.NAVY)],
           number_format="#,##0", legend=False, tick_every=tick)

    rx = X + 9.6
    T.textbox(slide, rx, y, 9.3, 0.34,
              "Accounts with no deposit in the last 20 days", 13, bold=True,
              color=T.NAVY)
    C.line(slide, rx, y + 0.38, 9.3, h - 0.42, labels,
           [("No deposit in 20 days", bvals[NODEP], T.CORAL)],
           number_format="#,##0", legend=False, tick_every=tick)

    if gaps:
        T.footnote(slide, "Business days with no deposit feed: "
                          + ", ".join(g.strftime("%m/%d") for g in gaps[:12])
                          + ". Confirm these against the core's processing calendar "
                            "before treating them as missed loads.")
    return slide


# ── 7. granted limits & overrides ───────────────────────────────────────────
def _limits(dk, d, *, section):
    L = d.limits
    slide = dk.content("Granted limits & override effectiveness",
                       f"Accounts by granted ILS limit ({L['n_distinct']} distinct "
                       f"values) and what each override rule actually did.",
                       section=section)
    y = T.CONTENT_TOP + 0.05
    lw = 10.4
    chart = L["chart"]
    if chart:
        T.textbox(slide, X, y, lw, 0.34,
                  "Accounts by granted limit (largest buckets)", 13, bold=True,
                  color=T.NAVY)
        labels = [f"${int(k):,}" for k, _ in chart]
        vals = [v for _, v in chart]
        colors = [T.CORAL if k == 0 else T.NAVY for k, _ in chart]
        C.column(slide, X, y + 0.38, lw, T.CONTENT_H - 0.5, labels, vals,
                 series_name="Accounts", number_format="#,##0", colors=colors,
                 cat_size=12)

    rx = X + lw + 0.45
    rw = T.SLIDE_W - rx - X
    T.band_label(slide, rx, y, rw, "  OVERRIDE EFFECTIVENESS")
    rows = []
    for r in d.overrides[:10]:
        # The export gives no account type, and the same rule text is configured
        # per type — so the rule id is what distinguishes otherwise identical rows.
        rows.append([r["id"] or "—", r["calc"][:42] or "—",
                     _fmt_override_value(r["value"]), count(r["count"]),
                     money(r["avg_limit"]),
                     count(r["avg_age"]) if r["avg_age"] is not None else "—",
                     count(r["avg_days_od"]) if r["avg_days_od"] is not None else "—"])
    if rows:
        rh = min(0.46, max(0.28, (T.CONTENT_BOTTOM - y - 1.4) / max(1, len(rows))))
        tbl = dk.table(slide, rx, y + 0.50, rw,
                       [0.7, 3.0, 0.9, 1.0, 1.2, 1.0, 0.9], len(rows) + 1, row_h=rh)
        T.fill_table(tbl, ["ID", "Override rule", "Value", "Accts", "Avg limit",
                           "Avg age (d)", "Days OD"], rows,
                     size=min(13, rh * 24),
                     align=[PP_ALIGN.RIGHT, PP_ALIGN.LEFT] + [PP_ALIGN.RIGHT] * 5)
    else:
        T.note(slide, rx, y + 0.55, rw, "No override activity reported in this export.")

    T.footnote(slide, f"{count(L['zero_limit'])} accounts ({pct(L['zero_pct'])}) are "
                      f"granted a zero limit — the coral bar. Override 'Avg age' and "
                      f"'Days OD' are the actual measured values for the accounts each "
                      f"rule caught, so a rule can be checked against the population it "
                      f"was written for.")
    return slide
