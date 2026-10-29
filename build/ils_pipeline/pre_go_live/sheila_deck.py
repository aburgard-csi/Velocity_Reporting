"""The ILS pre-go-live review deck in Sheila's format (RPE, 2026-10-28).

James Gilmore, 2026-10-28: "i want the format, look and feel in Sheila template. but i want the analysis
and insight from velocity." The content follows the Velocity PGL review (Tim Barrett's template, James's
First Central and Merchants decks, the 1616 pivot workbook): the partnership, the data review, personal
accounts, business accounts, the ILS matrix, program structure and fees, and the summary. The look is
Sheila's: the ARS template shell (cover, Executive Summit, agenda, Questions & Discussion, Contact Us,
found by meaning as the Transaction Intelligence deck finds them), cover_divider's cover and section
dividers, and the Transaction Intelligence frame for every content slide (title, selection line, data
pill, client logo, slide number), with every table drawn by shapes.add_table.

Every content slide's notes name its source. A slide whose input only the CSM can give (key dates, the
current program's fees, the data notes, an OD code's description) is drawn with a "to be completed"
line rather than left out, so the gap is visible in the deck the CSM reviews.

    build(metrics, client_id, client_name, out_path, inputs=None, art_dir=None) -> out_path
"""
from __future__ import annotations

import datetime as _dt
import subprocess
import sys
import tempfile
from collections import namedtuple
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parents[1]
REPO = BUILD.parent
for p in (BUILD, BUILD / "ars_pipeline"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from pptx import Presentation                       # noqa: E402
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN     # noqa: E402

import cover_divider as CD                          # noqa: E402
from brand import BODY, NAVY_RGB, TICK_RGB          # noqa: E402
from shapes import add_table, sldid_of, textbox, tile   # noqa: E402

TEMPLATE = REPO / "templates" / "ars_template.pptx"
PRODUCT = "ILS Pre-Go-Live Review"
COVER_LINE = "ILS Program Analysis"
Ctx = namedtuple("Ctx", "prs pack pill art_dir")
Chapter = namedtuple("Chapter", "code title agenda benefits build")

COLS = ["", "Accounts", "% of accts", "NSF/OD items*", "% of items", "Paid items", "Pay ratio",
        "Avg core limit", "Avg ILS limit", "Avg deposits (33d)", "Avg deposit $ (33d)", "Median deposit $ (33d)"]
COLW = [2.2, 0.95, 0.85, 1.0, 0.85, 0.9, 0.8, 1.0, 1.0, 0.95, 1.05, 1.1]
FOOT = "* NSF/OD items since the ILS import began."


# ------------------------------------------------------------------ formatting
def n_(v):
    return "–" if v is None else f"{v:,.0f}"


def pct(v, d=1):
    return "–" if v is None else f"{100 * v:.{d}f}%"


def usd(v):
    return "–" if v is None else (f"−${-v:,.0f}" if v < 0 else f"${v:,.0f}")


def accts(v):
    return f"{n_(v)} account" + ("" if v == 1 else "s")


def dec(v):
    return "–" if v is None else f"{v:,.1f}"


def _row_cells(r, names=None):
    label = str(r[0]).strip()
    shown = label.title() if label.isupper() and len(label) > 3 else label
    if names and label.upper() in names:
        shown = f"{label} · {names[label.upper()]}"
    return [shown,
            n_(r[1]), pct(r[2]), n_(r[3]), pct(r[4]), n_(r[5]), pct(r[6], 0), usd(r[7]), usd(r[8]),
            dec(r[9]), usd(r[10]), usd(r[13] if len(r) > 13 else None)]


# ------------------------------------------------------------------ frame
def chart(slide, L, T, W, H, cats, series, title=None, fmt='#,##0', highlight=(), colors=None, legend=False):
    """A native PowerPoint column chart: navy bars, orange for the highlighted categories, labels on the bars."""
    from pptx.chart.data import CategoryChartData
    from pptx.dml.color import RGBColor
    from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
    from pptx.util import Inches, Pt
    import brand as _b
    cd = CategoryChartData()
    cd.categories = [str(c) for c in cats]
    for name, values in series:
        cd.add_series(name, [v if v is not None else 0 for v in values])
    gf = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(L), Inches(T), Inches(W), Inches(H), cd)
    ch = gf.chart
    ch.font.name = BODY
    ch.font.size = Pt(10)
    ch.font.color.rgb = NAVY_RGB
    ch.has_title = bool(title)
    if title:
        ch.chart_title.text_frame.text = title
        tp = ch.chart_title.text_frame.paragraphs[0]
        tp.runs[0].font.size = Pt(12)
        tp.runs[0].font.bold = True
        tp.runs[0].font.color.rgb = NAVY_RGB
        tp.runs[0].font.name = BODY
    ch.has_legend = legend
    if legend:
        ch.legend.position = XL_LEGEND_POSITION.BOTTOM
        ch.legend.include_in_layout = False
    va = ch.value_axis
    va.has_major_gridlines = False
    va.visible = False
    ca = ch.category_axis
    ca.tick_labels.font.size = Pt(9.5)
    ca.format.line.color.rgb = _b.LABEL_RGB
    palette = colors or [NAVY_RGB, _b.LABEL_RGB, _b.ORANGE_RGB]
    plot = ch.plots[0]
    plot.gap_width = 60
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format = fmt
    dl.number_format_is_linked = False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size = Pt(9)
    for i, ser in enumerate(plot.series):
        ser.format.fill.solid()
        ser.format.fill.fore_color.rgb = palette[i % len(palette)]
        if i == 0:
            for j in highlight:
                pt = ser.points[j]
                pt.format.fill.solid()
                pt.format.fill.fore_color.rgb = _b.ORANGE_RGB
    return gf


def _frame():
    from ti import frame
    return frame


def content(ctx, title, selection, note):
    f = _frame()
    s = f.content_slide(ctx, title, selection)
    f.notes(s, note)
    return s


def say(slide, text, top=6.2, size=13, color=None, h=0.55):
    textbox(slide, 0.62, top, 11.4, h, text, size, color or NAVY_RGB, False, PP_ALIGN.LEFT, BODY,
            MSO_ANCHOR.TOP)


def todo(slide, what, top=2.0):
    """A line saying what the CSM still has to supply, so the gap shows in review."""
    say(slide, f"To be completed by the CSM: {what}", top=top, size=16, color=TICK_RGB, h=0.9)


def review_table(slide, t, top=1.75, height=None, fs=10, highlight=None, names=None):
    rows = [COLS] + [_row_cells(r, names) for r in t["rows"]] + [_row_cells(t["total"])]
    hi = highlight if highlight is not None else tuple(i for i, r in enumerate(rows) if i and r[0] in
                                                       ("Eligible", "Ineligible", "Grand Total"))
    h = height or min(4.2, 0.33 * len(rows))
    add_table(slide, 0.6, top, 12.15, h, rows, COLW, highlight=hi, fs=fs)
    return top + h


def _src(pack, what):
    return (f"Source: the ILS pre-go-live extract {pack['extract']} for client {pack['client_id']} "
            f"{pack['client_name']}, deleted-stamped rows out; {what}. Codes used: {pack['codes_line']}.")


def _get(rows, label):
    return next((r for r in rows if str(r[0]).strip().upper() == label.upper()), None)


# ------------------------------------------------------------------ chapters
def ch_partnership(ctx):
    pack, inp = ctx.pack, ctx.pack["inputs"]
    s1 = content(ctx, "Key Decisions and Dates", "ILS integration — project plan milestones",
                 "Source: the CSM's project plan, entered on the Sheila card. No figures from the extract.")
    dates = inp.get("key_dates") or []
    if dates:
        add_table(s1, 0.6, 1.75, 8.0, 0.38 * (len(dates) + 1), [["Milestone", "Date"]] + [list(d) for d in dates],
                  [6.0, 2.0], fs=12)
    else:
        todo(s1, "the milestone dates (program disclosures, PGL discussion, matrix approval, go-live).")
    s2 = content(ctx, "Current Program Key Details", "Integration preparation with current processes",
                 "Source: the client's current program, entered by the CSM on the Sheila card.")
    prog = inp.get("program") or {}
    keys = [("od_fee", "Current OD (paid) fee"), ("nsf_fee", "Current NSF (return) fee"),
            ("de_minimis_balance", "De minimis balance amount"), ("de_minimis_txn", "De minimis transaction amount"),
            ("sustained_fee", "Sustained (continuous) OD fee"), ("stop_payment_fee", "Stop payment fee"),
            ("daily_cap", "Daily fee cap")]
    if any(prog.get(k) for k, _ in keys):
        add_table(s2, 0.6, 1.75, 8.0, 0.4 * (len(keys) + 1),
                  [["Program detail", "Today"]] + [[lbl, str(prog.get(k) or "TBD")] for k, lbl in keys], [5.5, 2.5], fs=12)
    else:
        todo(s2, "the current OD and NSF fees, de minimis amounts, sustained OD fee, stop payment fee and daily cap.")
    return [s1, s2]


def ch_data(ctx):
    pack, m, t = ctx.pack, ctx.pack["metrics"], ctx.pack["review"]
    out = []
    s = content(ctx, "PGL Data Analysis", f"ILS extracted data as of {pack['extract_date_long']}",
                _src(pack, "the reconciliation against the vendor's integrity check") )
    rc = [r for r in (m.get("pgl_reconcile") or []) if isinstance(r, (list, tuple))]
    if rc:
        rows = [["Check", "Extract", "ILS system", "Delta"]] + [[str(r[0])[:70], n_(r[1]), n_(r[2]), f"{r[3]:+,}" if r[3] is not None else "–"] for r in rc[:7]]
        add_table(s, 0.6, 1.75, 9.6, 0.36 * len(rows), rows, [6.0, 1.2, 1.2, 1.2], fs=11)
    notes = (pack["inputs"].get("data_notes") or "").strip()
    if notes:
        say(s, "Notes on data: " + notes, top=5.0, size=13, h=1.3)
    else:
        say(s, "To be completed by the CSM: notes on the data (date range, codes still needing descriptions, "
               "First Notice File observations).", top=5.0, size=13, color=TICK_RGB, h=1.0)
    out.append(s)

    st = t["status"]
    s = content(ctx, "All Accounts by Status", "Rating criteria for overdraft limits — ILS account data collected",
                _src(pack, "every live account by Account Status"))
    review_table(s, st)
    o = _get(st["rows"], pack["open_code"])
    if o:
        say(s, f"{pct(o[2])} of accounts are open (status {pack['open_code']}) and they presented {pct(o[4])} of "
               f"the NSF/OD items since import. " + FOOT, top=6.1, size=12)
    out.append(s)

    ty = t["type"]
    s = content(ctx, "Open Accounts by Type", "Rating criteria for overdraft limits — all open accounts",
                _src(pack, "open accounts by Personal_Business"))
    review_table(s, ty)
    p = _get(ty["rows"], "PERSONAL")
    if p:
        say(s, f"Personal accounts are {pct(p[2])} of the open book and {pct(p[4])} of its NSF/OD items. "
               f"We'll dive into personal accounts first.", top=6.1, size=13)
    out.append(s)
    return out


def _od_note(t, kind):
    e, i = _get(t["rows"], "Eligible"), _get(t["rows"], "Ineligible")
    if not e:
        return f"No open {kind} account is on a confirmed OD-eligible status."
    text = (f"{pct(e[2])} of open {kind} accounts ({n_(e[1])}) are eligible to receive a limit out of ILS; "
            f"they presented {pct(e[4])} of the NSF/OD items.")
    if i and i[2] and i[2] > 0.2:
        text += (f" {n_(i[1])} sit on ineligible OD statuses — consider plans to maintain eligible accounts "
                 f"into an eligible status.")
    return text


def _change_note(t, kind):
    up, same = _get(t["rows"], "Score100Plus"), _get(t["rows"], "Same")
    if not (up or same):
        return ""
    share = (up[2] if up else 0) + (same[2] if same else 0)
    items = (up[4] if up else 0) + (same[4] if same else 0)
    return (f"Most eligible {kind} accounts ({pct(share, 0)}) will have larger or the same limits, and they "
            f"presented {pct(items, 0)} of the item volume. Increased limits should improve the debit decline "
            f"capture rate.")


def _share_chart(slide, t):
    rows = [r for r in t["rows"]]
    if rows:
        chart(slide, 0.6, 3.45, 12.1, 2.55, [str(r[0]) for r in rows],
              [("% of accounts", [r[2] for r in rows]), ("% of NSF/OD items", [r[4] for r in rows])],
              fmt='0%', legend=True)


def _tiers_slide(ctx, t, kind):
    tt = t[f"{kind}_tiers"]
    s = content(ctx, f"Proposed Limits — {kind.title()}", f"Eligible {kind} accounts by proposed limit",
                _src(ctx.pack, f"eligible {kind} accounts by OD Limit (from ILS) in the matrix's ${tt['step']:,.0f} steps"))
    rows = tt["rows"]
    if not rows:
        todo(s, "no eligible account carries a proposed limit.")
        return s
    data = [["Proposed limit", "Accounts", "% of accts", "Avg deposit $", "Median deposit $"]]
    labels, counts = [], []
    for hi, lo, n, share, avg, med in tt.get("bands") or []:
        labels.append("$0" if hi == 0 else f"${hi:,}")
        counts.append(n)
        data.append(["$0" if hi == 0 else f"${lo + 1:,}–${hi:,}", n_(n), pct(share), usd(avg), usd(med)])
    zero = next((r for r in rows if r[0] == 0), None)
    mx = rows[-1]
    chart(s, 0.6, 1.65, 6.6, 4.3, labels, [("Accounts", counts)], title="Eligible accounts by proposed limit (band top)",
          highlight=tuple(i for i in (0, len(labels) - 1) if labels))
    add_table(s, 7.45, 1.75, 5.3, min(4.2, 0.3 * len(data)), data, [1.6, 1.0, 0.9, 1.0, 1.1], fs=9.5)
    if zero and len(zero) > 4:
        data_med = (f"; medians {usd(mx[4])} and {usd(zero[4])}")
    else:
        data_med = ""
    if zero:
        say(s, f"{accts(mx[1])} {'reaches' if mx[1] == 1 else 'reach'} the ${mx[0]:,.0f} maximum and average "
               f"{usd(mx[3])} in deposits over 33 days; {accts(zero[1])} {'gets' if zero[1] == 1 else 'get'} $0 and "
               f"average {usd(zero[3])}{data_med}. The limit follows the deposit relationship.",
            top=6.15, size=12)
    return s


def ch_personal(ctx):
    t, pack = ctx.pack["review"], ctx.pack
    out = []
    s = content(ctx, "Personal Accounts — OD Codes", "Open personal accounts by OD status",
                _src(pack, "open personal accounts by OD Status Code (from Core), Eligible on the confirmed codes"))
    review_table(s, t["personal_od"], fs=9.5, names=pack["od_names"])
    say(s, _od_note(t["personal_od"], "personal"), top=6.05, size=12)
    out.append(s)
    s = content(ctx, "Personal — Change in Score", "Eligible personal accounts: what happens to each limit under ILS",
                _src(pack, "eligible personal accounts by UpOrDown from Initial OD Limit"))
    review_table(s, t["personal_change"], height=1.5)
    _share_chart(s, t["personal_change"])
    say(s, _change_note(t["personal_change"], "personal"), top=6.1, size=12, h=0.6)
    out.append(s)
    out.append(_tiers_slide(ctx, t, "personal"))
    s = content(ctx, "Reg E Opt In", "Eligible personal accounts: opted in, opted out and blank",
                _src(pack, "eligible personal accounts by Reg-E Opt-In Value"))
    review_table(s, t["rege"])
    y = _get(t["rege"]["rows"], "Y")
    if y:
        say(s, f"{pct(y[2])} of eligible personal accounts are opted in to Reg E, and they presented "
               f"{pct(y[4])} of the NSF/OD items.", top=5.4, size=13)
    out.append(s)
    s = content(ctx, "Reg E Opted In — Limits", "Change in score for eligible personal accounts opted in to Reg E",
                _src(pack, "eligible personal accounts with Reg E Y, by UpOrDown"))
    review_table(s, t["rege_y_change"])
    up = _get(t["rege_y_change"]["rows"], "Score100Plus")
    if up:
        say(s, f"{pct(up[2], 0)} of Reg E opted-in accounts will have larger limits out of ILS (average limit "
               f"{usd(up[8])}). Increased limits should capture a significant portion of their debit declines.",
            top=5.4, size=13, h=0.9)
    out.append(s)
    yr = t["rege_by_year"]
    s = content(ctx, "Reg E Opt In by Year Opened", "Eligible personal accounts, opt-in rate by year the account opened",
                _src(pack, "eligible personal accounts by Open Date and Reg-E Opt-In Value"))
    years = [r for r in yr["rows"] if str(r[0]) == "Pre-2010" or str(r[0]).isdigit()]
    months = [r for r in yr["rows"] if r not in years]
    if years:
        chart(s, 0.6, 1.65, 7.9, 4.2, [r[0] for r in years], [("Opt-in rate", [r[5] for r in years])], fmt='0%',
              title="Reg E opt-in rate by year the account opened", highlight=(len(years) - 1,))
    rows = [["Opened", "Opted in", "Accounts", "Opt-in rate"]] + [[r[0], n_(r[1]), n_(r[4]), pct(r[5])] for r in months] + \
           [[yr["total"][0], n_(yr["total"][1]), n_(yr["total"][4]), pct(yr["total"][5])]]
    add_table(s, 8.75, 1.75, 4.0, min(4.2, 0.28 * len(rows)), rows, [1.4, 0.9, 0.9, 0.9], fs=9, highlight=(len(rows) - 1,))
    if years:
        old, new = years[0], years[-1]
        say(s, f"Accounts opened {old[0]} opted in at {pct(old[5])}; accounts opened in {new[0]} at {pct(new[5])}. "
               f"New-account onboarding is where the Reg E opportunity is.", top=6.1, size=12)
    out.append(s)
    return out


def ch_business(ctx):
    t, pack = ctx.pack["review"], ctx.pack
    out = []
    s = content(ctx, "Business Accounts — OD Codes", "Open business accounts by OD status",
                _src(pack, "open business accounts by OD Status Code (from Core)"))
    review_table(s, t["business_od"], fs=9.5, names=pack["od_names"])
    say(s, _od_note(t["business_od"], "business"), top=6.05, size=12)
    out.append(s)
    s = content(ctx, "Business — Change in Score", "Eligible business accounts: what happens to each limit under ILS",
                _src(pack, "eligible business accounts by UpOrDown"))
    review_table(s, t["business_change"], height=1.5)
    _share_chart(s, t["business_change"])
    say(s, _change_note(t["business_change"], "business") +
        " All business accounts should be opted in to Reg E.", top=6.1, size=12, h=0.6)
    out.append(s)
    out.append(_tiers_slide(ctx, t, "business"))
    return out


def ch_matrix(ctx):
    mx, pack = ctx.pack.get("matrix"), ctx.pack
    if not mx or not mx.get("types"):
        s = content(ctx, "ILS Matrix Parameters", "From the ILS matrix validation export",
                    "Source: no matrix validation export beside the extract; nothing to draw.")
        todo(s, "the vendor's matrix validation export (land it in the client's PGL zip or folder).")
        return [s]
    src = f"Source: the ILS matrix validation export {pack['matrix_file']}, read with Tim Barrett's parser."
    out = []
    s = content(ctx, "Reminder for Matrix Parameters", "What sets and alters an ILS overdraft limit", src + " Static text.")
    say(s, "Factors driving limits up: age of account; number of deposits per month; dollars of deposits per month.\n"
           "Factors reducing limits: overrides for new accounts without deposits, days overdrawn, and debit declines.\n"
           "Trending adjusts limits as deposit regularity, windfall deposits and overdraft repayment build history.",
        top=1.8, size=16, h=3.2)
    out.append(s)
    s = content(ctx, "Matrix Settings & OD Codes", "Matrix minimum / maximum limits and the OD status mapping", src)
    rows = [["Account type", "Code", "Min", "Max", "Enabled", "Last modified"]] + [
        [tt, mx["codes"].get(tt, ""), usd(_f(st.get("Min"))), usd(_f(st.get("Max"))), st.get("Enabled?", ""),
         str(st.get("Matrix Modified Date", ""))[:10]] for tt, st in mx["settings"].items()]
    add_table(s, 0.6, 1.7, 7.4, 0.36 * len(rows), rows, [2.2, 0.8, 1.0, 1.0, 1.0, 1.4], fs=11)
    od = mx.get("od_mapping") or []
    seen = pack.get("od_counts") or {}
    if od:
        rows2 = [["OD status", "Description", "ILS calc", "Can overdraft", "Accounts"]] + [
            [r.get("STATUS_CODE", ""), r.get("DESCRIPTION", ""), "Yes" if M_true(r.get("ILS_CALC")) else "No",
             "Yes" if M_true(r.get("CAN_OVERDRAFT")) else "No", n_(seen.get(str(r.get("STATUS_CODE", "")).upper()))]
            for r in od]
        top = 1.8 + 0.36 * len(rows)
        add_table(s, 0.6, top, 9.4, min(6.6 - top, 0.3 * len(rows2)), rows2, [1.3, 3.0, 1.2, 1.5, 1.3], fs=10)
    out.append(s)
    for typ, ov in list(mx["overrides"].items())[:3]:
        s = content(ctx, f"Overrides — {typ}", "Applied in priority order; a stop ends the chain", src)
        rows = [["#", "Criteria", "Value", "Stop"]] + [
            [o.get("Order Index", ""), o.get("Override Criteria", ""), o.get("Override Value", ""),
             "Stop" if M_true(o.get("Stop Process")) else ""] for o in ov[:14]]
        add_table(s, 0.6, 1.7, 12.1, min(4.6, 0.32 * len(rows)), rows, [0.6, 8.6, 1.6, 1.0], fs=10)
        out.append(s)
    for cat, grid in list(mx["grids"].items())[:3]:
        if not grid:
            continue
        s = content(ctx, cat, "Rating criteria: limit factor by range, per account type", src)
        types = mx["types"]
        rows = [["Range"] + types] + [[g.get("label", "")] + [str(g.get(tt, "")) for tt in types] for g in grid[:16]]
        add_table(s, 0.6, 1.7, 2.5 + 1.6 * len(types), min(4.7, 0.27 * len(rows)), rows,
                  [2.5] + [1.6] * len(types), fs=9.5)
        out.append(s)
    trig = mx.get("triggers") or []
    if trig:
        s = content(ctx, "Trending Triggers", "Events needed to begin trending, per account type", src)
        rows = [["Account type", "Trend", "Deposits", "Deposit $", "OD events"]] + [
            [r.get("type", ""), r.get("repo", ""), str(r.get("dep_cnt", "")), str(r.get("dep_amt", "")),
             str(r.get("od_cnt", ""))] for r in trig[:12]]
        add_table(s, 0.6, 1.7, 10.0, 0.34 * len(rows), rows, [2.0, 3.6, 1.4, 1.4, 1.6], fs=10.5)
        out.append(s)
    return out


def ch_program(ctx):
    pack, m = ctx.pack, ctx.pack["metrics"]
    s = content(ctx, "Program Structure", "Daily fee cap, de minimis waivers and pricing",
                "Source: Velocity best practice (static), and the client's current fees entered by the CSM.")
    say(s, "Daily fee cap — Velocity recommends 4–6 fees per day.\n"
           "De minimis waivers — Velocity recommends a $2 transaction de minimis and a $5–$10 balance de minimis.\n"
           "Pricing — three pricing scenarios, each modeled on the client's current fee.", top=1.8, size=16, h=2.6)
    nt = m.get("pgl_notices") or {}
    if not nt.get("baseline"):
        say(s, "To be completed by the CSM: the raw overdraft notice items (the First Notice File) in the client's "
               "PGL zip, which price the fee baseline, the daily cap and de minimis.", top=4.6, size=14,
            color=TICK_RGB, h=0.9)
        return [s]
    src = (f"Source: the raw overdraft notice items {nt['file']} for client {pack['client_id']} "
           f"{pack['client_name']}, {nt['first']} to {nt['last']} ({nt['days']} days, {nt['items']:,} items on "
           f"{nt['accounts']:,} accounts); fees as assessed; annualized at 365 / {nt['days']} days.")
    say(s, f"From the notice items: {usd(nt['revenue'])} in fees over {nt['days']} days, about "
           f"{usd(nt['revenue_annualized'])} a year. The most fees one account paid in one day: {nt['max_fees_one_day']}.",
        top=4.6, size=14, h=0.8)
    s2 = content(ctx, "Fee Revenue Baseline", f"First Notice File, {nt['days']} days of real notice items", src)
    rows = [["Category", "Items", "% of items", "Fee per item", "Revenue", "% of revenue"]] + [
        [r[0], n_(r[1]), pct(r[2]), f"${r[3]:,.2f}", usd(r[4]), pct(r[5])] for r in nt["baseline"]]
    add_table(s2, 0.6, 1.8, 10.0, 0.42 * len(rows), rows, [3.2, 1.3, 1.3, 1.4, 1.5, 1.3], fs=12,
              highlight=(len(rows) - 1,))
    tile(s2, 0.6, 4.2, 4.6, 1.3, usd(nt["revenue_annualized"]), "annualized fee revenue from the notice items")
    out = [s, s2]
    if nt.get("cap_curve"):
        out += [_cap_slide(ctx, nt, src), _de_minimis_slide(ctx, nt, src), _pricing_slide(ctx, nt, src)]
    return out


def _curve_rows(curve, label):
    return [[label(r[0]), n_(r[1]), n_(r[2]), usd(r[4]), pct(r[5])] for r in curve]


def _cap_slide(ctx, nt, src):
    s = content(ctx, "Daily Fee Cap", f"How many fees an account pays in one day, and what each cap returns ({nt['days']} days)",
                src + " A cap waives every fee past the Nth on one account in one day.")
    dist = nt["per_day_dist"]
    chart(s, 0.6, 1.6, 6.1, 3.0, [r[0] for r in dist], [("Account-days", [r[1] for r in dist])],
          title="Account-days by fees charged that day", highlight=tuple(i for i, r in enumerate(dist) if r[0] in ("4", "5", "6")))
    cc = nt["cap_curve"]
    chart(s, 6.85, 1.6, 5.9, 3.0, [str(r[0]) for r in cc], [("Waived a year", [r[4] for r in cc])], fmt='$#,##0',
          title="Fees returned to members a year, by cap", highlight=tuple(i for i, r in enumerate(cc) if 4 <= r[0] <= 6))
    rows = [["Cap", "Fees waived", "Accounts helped", "Waived a year", "% of revenue"]] + \
        _curve_rows([r for r in cc if 3 <= r[0] <= 8], lambda c: f"{c} fees a day")
    add_table(s, 0.6, 4.75, 8.2, 0.26 * len(rows), rows, [2.0, 1.4, 1.6, 1.6, 1.4], fs=9.5,
              highlight=tuple(i for i, r in enumerate(rows) if r[0] in ("4 fees a day", "5 fees a day", "6 fees a day")))
    c4, c6 = next(r for r in cc if r[0] == 4), next(r for r in cc if r[0] == 6)
    one = dist[0][1] if dist else 0
    tot = sum(r[1] for r in dist) or 1
    textbox(s, 9.0, 4.8, 3.75, 1.5, f"{pct(one / tot, 0)} of fee days carry one fee. A 4–6 cap returns "
                f"{usd(c6[4])}–{usd(c4[4])} a year ({pct(c6[5])}–{pct(c4[5])} of fees) to the {n_(c6[2])}–{n_(c4[2])} "
                f"accounts hit hardest.", 12, NAVY_RGB, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
    return s


def _de_minimis_slide(ctx, nt, src):
    s = content(ctx, "De Minimis Waivers", "Small items and small overdrafts: what a waiver would return",
                src + " A transaction de minimis waives the fee on an item of $X or less; a balance de minimis waives it "
                      "when the item leaves the account overdrawn by $X or less.")
    ab, bb = nt["amount_bands"], nt["balance_bands"]
    chart(s, 0.6, 1.6, 6.1, 2.9, [r[0] for r in ab], [("Fee items", [r[1] for r in ab])],
          title="Fee items by item amount", highlight=(0,))
    chart(s, 6.85, 1.6, 5.9, 2.9, [r[0] for r in bb], [("Fee items", [r[1] for r in bb])],
          title="Fee items by how far overdrawn", highlight=(0, 1))
    tx = [["Transaction de minimis", "Fees waived", "Accounts", "Waived a year", "% of rev."]] + \
        _curve_rows(nt["txn_curve"], lambda x: f"${x} or less")
    bl = [["Balance de minimis", "Fees waived", "Accounts", "Waived a year", "% of rev."]] + \
        _curve_rows(nt["bal_curve"], lambda x: f"${x} or less")
    add_table(s, 0.6, 4.65, 6.1, 0.24 * len(tx), tx, [1.9, 1.0, 1.0, 1.2, 0.9], fs=9,
              highlight=tuple(i for i, r in enumerate(tx) if r[0] == "$2 or less"))
    add_table(s, 6.85, 4.65, 5.9, 0.24 * len(bl), bl, [1.8, 1.0, 1.0, 1.2, 0.9], fs=9,
              highlight=tuple(i for i, r in enumerate(bl) if r[0] in ("$5 or less", "$10 or less")))
    if nt.get("outliers"):
        textbox(s, 0.62, 6.35, 11.4, 0.4, f"{nt['outliers']} items carry an ending balance beyond ±$9,999 (down to "
                f"{usd(nt['outlier_min_balance'])}); confirm them before quoting the balance de minimis.",
                10, TICK_RGB, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
    return s


def _pricing_slide(ctx, nt, src):
    """The cap and the de minimis together, and the OD fee that would hold today's revenue."""
    pack = ctx.pack
    s = content(ctx, "Finding the Right Structure", "The cap and de minimis together, and the fee that holds revenue",
                src + " Applied together: a de minimis item is not charged, so it does not count toward the day's cap. "
                      "The fee that holds revenue scales today's fees by the revenue each structure keeps.")
    od_fee = (nt.get("fee_per_item") or {}).get("PD")
    cols = [(0, 0, "No de minimis"), (0, 5, "$5 balance"), (0, 10, "$10 balance"), (2, 0, "$2 transaction"),
            (2, 5, "$2 txn + $5 bal"), (2, 10, "$2 txn + $10 bal")]
    by = {(r[1], r[2], r[3]): r for r in nt["grid"]}
    rows = [["Daily cap"] + [c[2] for c in cols]]
    hi_cells = []
    for i, cap in enumerate((0, 4, 5, 6), 1):
        line = ["No cap" if not cap else f"{cap} fees a day"]
        for j, (tx, bal, _) in enumerate(cols, 1):
            r = by.get((cap, tx, bal))
            line.append("–" if not r else (f"{usd(r[5])}  ({pct(r[6])})" if r[5] else "today"))
            if r and r[9]:
                hi_cells.append((i, j))
        rows.append(line)
    gf = add_table(s, 0.6, 1.7, 12.15, 1.9, rows, [1.6, 1.75, 1.75, 1.75, 1.75, 1.8, 1.8], fs=10.5)
    from pptx.dml.color import RGBColor  # noqa: F401
    import brand as _b
    for i, j in hi_cells:
        c = gf.table.cell(i, j)
        c.fill.solid()
        c.fill.fore_color.rgb = _b.ORANGE_RGB
        for p in c.text_frame.paragraphs:
            for run in p.runs:
                run.font.color.rgb = _b.WHITE_RGB if hasattr(_b, "WHITE_RGB") else NAVY_RGB
                run.font.bold = True
    guided = sorted((r for r in nt["grid"] if r[9]), key=lambda r: r[5])
    if guided:
        lo, hi = guided[0], guided[-1]
        cats = [r[0].replace(" transaction", " txn").replace(" balance", " bal") for r in guided]
        chart(s, 0.6, 3.8, 7.6, 2.3, cats, [("Returned to members a year", [r[5] for r in guided])], fmt='$#,##0',
              title="Within Velocity guidance: returned to members a year")
        fee_txt = ""
        if od_fee:
            fee_txt = (f" Holding today's revenue would take an OD fee of ${od_fee * lo[8]:,.2f}–${od_fee * hi[8]:,.2f} "
                       f"instead of ${od_fee:,.2f}.")
        textbox(s, 8.45, 3.85, 4.3, 2.4, f"Velocity's guidance (orange) returns {usd(lo[5])}–{usd(hi[5])} a year to "
                f"members, {pct(lo[6])}–{pct(hi[6])} of fee revenue.{fee_txt} The CSM and the client choose the "
                f"structure; these are the trade-offs.", 12, NAVY_RGB, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
    return s


def ch_summary(ctx):
    t, pack = ctx.pack["review"], ctx.pack
    s = content(ctx, "Summary", "What the pre-go-live data says", _src(pack, "the review tables in this deck"))
    e = _get(t["personal_od"]["rows"], "Eligible")
    up = _get(t["personal_change"]["rows"], "Score100Plus")
    y = _get(t["rege"]["rows"], "Y")
    x = 0.6
    for value, label in ((pct(e[2], 0) if e else "–", "of open personal accounts are eligible for an ILS limit"),
                         (pct(up[2], 0) if up else "–", "of eligible personal accounts get a larger limit"),
                         (pct(y[2], 0) if y else "–", "of eligible personal accounts are opted in to Reg E")):
        tile(s, x, 1.9, 3.85, 1.5, value, label)
        x += 4.05
    say(s, "Opportunities: review the ineligible accounts with strong deposit relationships for return to the "
           "program; use the debit decline communication strategies to grow Reg E opt-ins; confirm the matrix "
           "parameters and overrides before go-live.", top=3.9, size=14, h=1.6)
    return [s]


def od_names(matrix, inputs):
    """An OD code's description: the CSM's (the card) first, then the matrix's where it is a real one
    (not the code repeated, not "blank")."""
    names = {}
    for r in (matrix or {}).get("od_mapping") or []:
        code, desc = str(r.get("STATUS_CODE", "")).strip().upper(), str(r.get("DESCRIPTION", "")).strip()
        if code and desc and desc.upper() not in (code, "BLANK", "NULL", ""):
            names[code] = desc
    for code, desc in ((inputs or {}).get("od_descriptions") or {}).items():
        if str(desc).strip():
            names[str(code).strip().upper()] = str(desc).strip()
    return names


def M_true(v):
    return str(v).strip().upper() in ("1", "Y", "YES", "TRUE")


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


CHAPTERS = [
    Chapter("PGL1", "Partnership", "Key decisions, dates and the current program", "Where the integration stands",
            ch_partnership),
    Chapter("PGL2", "PGL Data Review", "The extract, reconciled to the ILS system", "Is the data sound", ch_data),
    Chapter("PGL3", "Personal Accounts", "Eligibility, limits under ILS and Reg E", "Who gets a limit", ch_personal),
    Chapter("PGL4", "Business Accounts", "Eligibility and limits under ILS", "Business book under ILS", ch_business),
    Chapter("PGL5", "ILS Matrix", "Settings, overrides, factors and trending", "How limits are set", ch_matrix),
    Chapter("PGL6", "Program Structure & Fees", "Fee cap, de minimis and pricing", "Program design", ch_program),
    Chapter("PGL7", "Summary & Recommendations", "What the data says and what to do next", "Next steps", ch_summary),
]


# ------------------------------------------------------------------ the shell
def _title(slide):
    return next((sh.text_frame.text.strip().split("\n")[0] for sh in slide.shapes
                 if sh.has_text_frame and sh.text_frame.text.strip()), "")


def _shell(prs, pack, art_dir):
    import assemble_combined as ac
    found = {}
    for n, s in enumerate(prs.slides, 1):
        title = _title(s)
        if "cover" not in found and ac._is_cover(s):
            found["cover"] = s
        elif "summit" not in found and ac._is_summit(s, n):
            found["summit"] = s
        elif "agenda" not in found and title.startswith("Agenda"):
            found["agenda"] = s
        elif "questions" not in found and title.startswith("Questions & Discussion"):
            found["questions"] = s
        elif "contact" not in found and title.startswith("Contact Us"):
            found["contact"] = s
    missing = {"cover", "summit", "agenda", "questions", "contact"} - set(found)
    if missing:
        raise SystemExit(f"{sorted(missing)} not found in the template shell — it changed.")
    cid, name = pack["client_id"], pack["client_name"]
    CD.draw_cover(found["cover"], [PRODUCT], name, pack["extract_date_long"],
                  client_logo=CD.client_logo_for(cid, art_dir),
                  note=f"Source: the ILS pre-go-live extract {pack['extract']} for client {cid} {name}. Cover. No figures.")
    # cover_divider writes "Executive Review  •  <month>"; this deck is the Velocity ILS Program Analysis
    for sh in found["cover"].shapes:
        if sh.has_text_frame:
            for para in sh.text_frame.paragraphs:
                for run in para.runs:
                    if run.text.startswith("Executive Review"):
                        run.text = run.text.replace("Executive Review", COVER_LINE, 1)
    for ch in CHAPTERS:
        ac.PRODUCT_NAME.setdefault(ch.code, ch.title)
    ac.set_agenda(found["agenda"], [ch.code for ch in CHAPTERS], detail_overrides={ch.code: ch.agenda for ch in CHAPTERS})
    import build_ti_gen as G
    G._agenda_headings_only(found["agenda"], CHAPTERS)
    found["agenda"].notes_slide.notes_text_frame.text = "Source: the ILS pre-go-live review's chapter list (static). No figures."
    G._set_closing_line(found["questions"], f"{name}  •  {pack['extract_date_long']}")
    CD.redraw_closing_in_place(found["questions"])
    import rpe_env
    from shapes import fill_contact_card
    try:
        fill_contact_card(found["contact"], rpe_env.csm_contact(cid))
    except (SystemExit, Exception) as exc:
        # a pre-go-live client may not be on the Client CSM List yet. The shell's card holds another
        # CSM's details, so it is overwritten with a placeholder rather than left naming the wrong person.
        pack.setdefault("warnings", []).append(f"Contact Us card: {exc}")
        fill_contact_card(found["contact"], {"name": "CSM to be confirmed", "role": "Client Service Manager",
                                             "phone": "", "email": f"add client {cid} to the Client CSM List"})
    return found


def build(metrics, client_id, client_name, out_path, inputs=None, art_dir=None, codes=None, extract=None,
          extract_date=None, matrix=None, matrix_file=None):
    """Draw the deck into `out_path` and return it."""
    review_t = metrics.get("pgl_review")
    if not review_t:
        raise SystemExit("the run carries no review tables (pgl_review): run it with confirmed codes first")
    codes = codes or metrics.get("pgl_codes_used") or {}
    ed = extract_date or _dt.date.today()
    if isinstance(ed, str):
        ed = _dt.date.fromisoformat(ed[:10])
    od_counts = {}
    for k in ("personal_od", "business_od"):
        for r in review_t[k]["rows"]:
            lbl = str(r[0]).strip().upper()
            if lbl not in ("ELIGIBLE", "INELIGIBLE"):
                od_counts[lbl] = od_counts.get(lbl, 0) + r[1]
    pack = {"client_id": str(client_id), "client_name": client_name or str(client_id), "metrics": metrics,
            "review": review_t, "inputs": inputs or {}, "extract": extract or metrics.get("pgl_extract", ""),
            "extract_date_long": f"{ed:%B} {ed.day}, {ed:%Y}",
            "open_code": ", ".join(codes.get("open_status") or []) or "O",
            "codes_line": "; ".join(f"{k} {', '.join(v) if isinstance(v, list) else v}" for k, v in codes.items()),
            "matrix": matrix, "matrix_file": matrix_file or "", "od_counts": od_counts,
            "od_names": od_names(matrix, inputs)}
    prs = Presentation(str(TEMPLATE))
    keep = _shell(prs, pack, art_dir)
    ctx = Ctx(prs, pack, f"Data {ed:%m/%d/%Y}", art_dir)
    f = _frame()
    body = []
    for ch in CHAPTERS:
        d = f.new_slide(prs)
        CD.draw_divider(d, ch.title, ch.benefits,
                        note=f"Section divider. Source: the ILS pre-go-live extract {pack['extract']} for client "
                             f"{client_id} {pack['client_name']}; figures as on the chapter's slides.")
        body.append(d)
        body.extend(ch.build(ctx))
    order = [keep["cover"], keep["summit"], keep["agenda"]] + body + [keep["questions"], keep["contact"]]
    lst = prs.slides._sldIdLst
    ids = [sldid_of(prs, s) for s in order]
    for el in list(lst):
        lst.remove(el)
    for el in ids:
        lst.append(el)
    import summit_slide
    summit_slide.insert_summit_after_title(prs)
    import fit_layout
    fit_layout.fit(prs)
    import assemble_combined as ac
    ac.renumber(prs)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pgl_full_") as scratch:
        tmp = Path(scratch) / f"{out.stem}.__full.pptx"
        prs.save(str(tmp))
        subprocess.run([sys.executable, str(BUILD / "strip_dead.py"), str(tmp), str(out)], check=True)
    return out
