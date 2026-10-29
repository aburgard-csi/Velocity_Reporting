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


def _od_note(t, kind, all_codes=False):
    e, i = _get(t["rows"], "Eligible"), _get(t["rows"], "Ineligible")
    if all_codes and e:
        # od_eligible = ALL (pre_go_live/run.py): today's codes are not the go-live codes
        return (f"Every OD status is counted as eligible: the client moves accounts to their go-live codes by mass "
                f"maintenance the night before, so today's codes are not the ones ILS will read. {n_(e[1])} open "
                f"{kind} accounts; they presented {pct(e[4])} of the NSF/OD items.")
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


def _core_ils_slides(ctx, kind):
    """The core's limits against ILS's, on eligible accounts: the case that the current system is inefficient."""
    pack = ctx.pack
    cv = ((pack["metrics"].get("pgl_insights") or {}).get("core_vs_ils") or {}).get(kind) or {}
    if not cv:
        return []
    word = kind.title()
    src = _src(pack, f"open, eligible {kind} accounts' Initial OD Limit (from Core) against OD Limit (from ILS), "
                     f"with Deposit Amount Last 33 days; correlation is Pearson's, limit against deposits")
    out = []
    qq = cv["quintiles"]
    typ = cv["typical_core"]
    if qq:      # none on a base too small to split into fifths
        s = content(ctx, f"Core Limits vs ILS — {word}", "Does the limit follow the account's deposits?", src)
        chart(s, 0.6, 1.6, 7.4, 3.9, [f"{r[0]}\n(median {usd(r[2])})" for r in qq],
              [("Core limit today (average)", [r[3] for r in qq]), ("ILS limit (average)", [r[4] for r in qq])],
              fmt='$#,##0', title=f"Average limit by deposit level, eligible {kind} accounts", legend=True,
              colors=[_LABEL_RGB(), NAVY_RGB])
        lines = (f"Today {pct(cv['typical_core_share'], 0)} of eligible {kind} accounts sit at the same {usd(typ)} core "
                 f"limit, whatever they deposit: from the bottom fifth of depositors to the top fifth the average core "
                 f"limit moves {usd(qq[0][3])} to {usd(qq[-1][3])}. ILS sets {usd(qq[0][4])} to {usd(qq[-1][4])}.")
        textbox(s, 8.25, 1.75, 4.5, 2.6, lines, 13, NAVY_RGB, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
        if cv.get("corr_core") is not None and cv.get("corr_ils") is not None:
            tile(s, 8.25, 4.35, 2.15, 1.2, f"{cv['corr_core']:.2f}", "core limit follows deposits")
            tile(s, 10.6, 4.35, 2.15, 1.2, f"{cv['corr_ils']:.2f}", "ILS limit follows deposits")
        say(s, "Correlation runs from −1 to 1: 1 means the limit rises with deposits, 0 that it ignores them, below 0 "
               "that it falls as deposits rise. A limit that ignores deposits over-extends risky accounts and "
               "under-serves strong ones.", top=5.8, size=11, h=0.7)
        out.append(s)
    s2 =content(ctx, f"Where the Core Limit Misses — {word}", "Risk the core carries, and members it under-serves", src)
    on = lambda d, n: f"{usd(d)} on {accts(n)}" if n else "none"
    rows = [["", "Core limit today", "ILS limit"],
            [f"Accounts with no deposits in 33 days ({n_(cv['nodep_accounts'])})",
             on(cv["nodep_core_dollars"], cv["nodep_core_accounts"]),
             on(cv["nodep_ils_dollars"], cv["nodep_ils_accounts"])],
            [f"Depositors above the median ({usd(cv['deposit_median'])}) held at {usd(typ)} or less",
             accts(cv["held_accounts"]), f"average {usd(cv['held_ils_avg'])}"],
            ["Total limit extended", usd(cv["core_total"]), usd(cv["ils_total"])]]
    add_table(s2, 0.6, 1.65, 12.15, 1.7, rows, [5.6, 3.3, 3.25], fs=11.5)
    rr = cv["returned_raised"] / cv["returned"] if cv["returned"] else None
    dr = cv["declines_raised"] / cv["declines"] if cv["declines"] else None
    x = 0.6
    for value, label in ((pct(rr, 0), f"of returned items ({n_(cv['returned'])}) are on accounts ILS would raise"),
                         (pct(dr, 0), f"of debit declines ({n_(cv['declines'])}) are on accounts ILS would raise")):
        tile(s2, x, 3.55, 3.3, 1.35, value, label)
        x += 3.45
    bands = cv["matrix_bands"]
    mrows = [["Core today → ILS"] + bands] + [[b] + [n_(v) for v in row] for b, row in zip(bands, cv["matrix"])]
    add_table(s2, 7.55, 3.55, 5.2, 0.3 * len(mrows), mrows, [1.4] + [0.76] * len(bands), fs=8.5)
    say(s2, f"The core extends {usd(cv['nodep_core_dollars'])} of limit to accounts with no deposits; ILS extends "
            f"{usd(cv['nodep_ils_dollars'])}. The members the core under-serves are where the returned items and declines "
            f"sit: ILS limits follow the deposit relationship.", top=5.55, size=12, h=0.9)
    return out + [s2]


AGENDA_TOP, AGENDA_BOTTOM, AGENDA_BADGE = 1.45, 6.45, 0.44     # inches; the logo starts at 6.78


def _space_agenda(slide):
    """Nine rows at the shared set_agenda's pitch (0.47in) overlap its 0.62in badges into one orange bar,
    and the top-anchored headings sit above their centred numbers (James Gilmore, 2026-10-29: "agenda
    numbers are squished and touching"). Re-lay the rows here, PGL only: smaller badges spread over the
    band above the logo, each heading centred on its badge. assemble_combined.set_agenda stays as ARS uses it."""
    from pptx.util import Inches, Pt
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    badges = sorted((sh for sh in slide.shapes if sh.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE
                     and not sh.text_frame.text.strip()), key=lambda sh: sh.top)
    if len(badges) < 2:
        return
    nums = {(sh.left, sh.top): sh for sh in slide.shapes
            if sh.has_text_frame and sh.text_frame.text.strip().isdigit()}
    heads = sorted((sh for sh in slide.shapes if sh.has_text_frame and sh.text_frame.text.strip()
                    and sh.left > badges[0].left + badges[0].width and sh.top < Inches(6.7)
                    and sh.text_frame.text.strip() != "Agenda"), key=lambda sh: sh.top)
    rows = [(b, nums.get((b.left, b.top)), h) for b, h in zip(badges, heads)]
    pitch = (AGENDA_BOTTOM - AGENDA_BADGE - AGENDA_TOP) / (len(rows) - 1)
    size = Inches(AGENDA_BADGE)
    for i, (b, n, h) in enumerate(rows):
        top = Inches(AGENDA_TOP + i * pitch)
        for sh in (b, n):
            if sh is not None:
                sh.top, sh.width, sh.height = top, size, size
        if n is not None:
            n.text_frame.margin_top = n.text_frame.margin_bottom = 0
            for r in n.text_frame.paragraphs[0].runs:
                r.font.size = Pt(18)
        h.top, h.height = top, size
        h.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        h.text_frame.margin_top = h.text_frame.margin_bottom = 0
        h.left = b.left + size + Inches(0.25)


def _LABEL_RGB():
    import brand as _b
    return _b.LABEL_RGB


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
    say(s, _od_note(t["personal_od"], "personal", ctx.pack["metrics"].get("pgl_od_all")), top=6.05, size=12)
    out.append(s)
    s = content(ctx, "Personal — Change in Score", "Eligible personal accounts: what happens to each limit under ILS",
                _src(pack, "eligible personal accounts by UpOrDown from Initial OD Limit"))
    review_table(s, t["personal_change"], height=1.5)
    _share_chart(s, t["personal_change"])
    say(s, _change_note(t["personal_change"], "personal"), top=6.1, size=12, h=0.6)
    out.append(s)
    out.extend(_core_ils_slides(ctx, "personal"))
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
    say(s, _od_note(t["business_od"], "business", ctx.pack["metrics"].get("pgl_od_all")), top=6.05, size=12)
    out.append(s)
    s = content(ctx, "Business — Change in Score", "Eligible business accounts: what happens to each limit under ILS",
                _src(pack, "eligible business accounts by UpOrDown"))
    review_table(s, t["business_change"], height=1.5)
    _share_chart(s, t["business_change"])
    say(s, _change_note(t["business_change"], "business") +
        " All business accounts should be opted in to Reg E.", top=6.1, size=12, h=0.6)
    out.append(s)
    out.extend(_core_ils_slides(ctx, "business"))
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


def window_text(nt):
    """'Jul 1 – Oct 27, 2026: 119 days (3.9 months)' for the notice items' own window."""
    import datetime as _d
    a, b = _d.date.fromisoformat(nt["first"]), _d.date.fromisoformat(nt["last"])
    span = f"{a:%b} {a.day} – {b:%b} {b.day}, {b:%Y}" if a.year == b.year else f"{a:%b} {a.day}, {a:%Y} – {b:%b} {b.day}, {b:%Y}"
    return f"{span}: {nt['days']} days ({nt['days'] / 30.44:.1f} months)"


def window_pill(nt):
    import datetime as _d
    a, b = _d.date.fromisoformat(nt["first"]), _d.date.fromisoformat(nt["last"])
    return f"Notices {a.month}/{a.day}–{b.month}/{b.day}/{b:%y}"


def ch_program(ctx):
    pack, m = ctx.pack, ctx.pack["metrics"]
    nt0 = m.get("pgl_notices") or {}
    if nt0.get("baseline"):
        # every fee slide carries the notice items' window in its pill, not the extract's date
        ctx = ctx._replace(pill=window_pill(nt0))
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
    say(s, f"From the notice items ({window_text(nt)}): {usd(nt['revenue'])} in fees, an estimated "
           f"{usd(nt['revenue_annualized'])} a year. The most fees one account paid in one day: {nt['max_fees_one_day']}.",
        top=4.6, size=14, h=0.8)
    s2 = content(ctx, "Fee Revenue Baseline", f"First Notice File, {nt['days']} days of real notice items", src)
    rows = [["Category", "Items", "% of items", "Fee per item", "Revenue", "% of revenue"]] + [
        [r[0], n_(r[1]), pct(r[2]), f"${r[3]:,.2f}", usd(r[4]), pct(r[5])] for r in nt["baseline"]]
    add_table(s2, 0.6, 1.8, 10.0, 0.42 * len(rows), rows, [3.2, 1.3, 1.3, 1.4, 1.5, 1.3], fs=12,
              highlight=(len(rows) - 1,))
    tile(s2, 0.6, 4.2, 4.6, 1.3, usd(nt["revenue_annualized"]), f"a year, estimated from {nt['days']} days")
    textbox(s2, 5.45, 4.25, 7.3, 1.6, f"The notice items cover {window_text(nt)}, not a full year. Every yearly "
            f"figure in this chapter is those {nt['days']} days scaled to 365 (×{365 / nt['days']:.2f}) and assumes the "
            f"rest of the year looks like these months: seasonality (holidays, tax refunds) can move it either way. "
            f"The figures for the {nt['days']} days themselves are exact.", 12, NAVY_RGB, False, PP_ALIGN.LEFT, BODY,
            MSO_ANCHOR.TOP)
    out = [s, s2]
    if nt.get("by_type_detail"):
        out.append(_by_type_slide(ctx, nt, src))
    if nt.get("cap_curve"):
        out += [_cap_slide(ctx, nt, src), _de_minimis_slide(ctx, nt, src), _pricing_slide(ctx, nt, src)]
    return out


def _by_type_slide(ctx, nt, src):
    s = content(ctx, "Fees by Transaction Type", "Which kinds of item carry the NSF/OD fees",
                src + " Paid = PD (overdraft paid), returned = RT (NSF returned).")
    bt = [r for r in nt["by_type_detail"] if r[1]]
    names = {"ACH": "ACH", "CRD": "Card", "CHK": "Check", "OTH": "Other", "(blank)": "Blank"}
    chart(s, 0.6, 1.6, 6.0, 3.6, [names.get(r[0], r[0]) for r in bt],
          [("Paid", [r[2] for r in bt]), ("Returned", [r[3] for r in bt])], title="Notice items by type", legend=True)
    rows = [["Type", "Items", "Paid", "Returned", "Fees", "Fees a year (est.)", "Average item"]] + [
        [names.get(r[0], r[0]), n_(r[1]), n_(r[2]), n_(r[3]), usd(r[4]), usd(r[6]), usd(r[5])] for r in bt]
    add_table(s, 6.85, 1.75, 5.9, 0.36 * len(rows), rows, [1.0, 0.85, 0.8, 0.85, 0.9, 1.0, 0.95], fs=10)
    top = max(bt, key=lambda r: r[6]) if bt else None
    if top:
        say(s, f"{names.get(top[0], top[0])} items carry the most fees: {usd(top[6])} a year, "
               f"{pct(top[6] / nt['revenue_annualized']) if nt.get('revenue_annualized') else ''} of the total. "
               f"Card items are paid, never returned: that is the Reg E and debit decline conversation.", top=5.6, size=12, h=0.9)
    return s


def _curve_rows(curve, label):
    return [[label(r[0]), n_(r[1]), n_(r[2]), usd(r[4]), pct(r[5])] for r in curve]


def _cap_slide(ctx, nt, src):
    s = content(ctx, "Daily Fee Cap", f"How many fees an account pays in one day, and what each cap returns ({nt['days'] / 30.44:.1f} months of notices)",
                src + " A cap waives every fee past the Nth on one account in one day.")
    dist = nt["per_day_dist"]
    chart(s, 0.6, 1.6, 6.1, 3.0, [r[0] for r in dist], [("Account-days", [r[1] for r in dist])],
          title="Account-days by fees charged that day", highlight=tuple(i for i, r in enumerate(dist) if r[0] in ("4", "5", "6")))
    cc = nt["cap_curve"]
    chart(s, 6.85, 1.6, 5.9, 3.0, [str(r[0]) for r in cc], [("Waived a year (est.)", [r[4] for r in cc])], fmt='$#,##0',
          title="Fees returned to members a year (est.), by cap", highlight=tuple(i for i, r in enumerate(cc) if 4 <= r[0] <= 6))
    rows = [["Cap", "Fees waived", "Accounts helped", "Waived a year (est.)", "% of revenue"]] + \
        _curve_rows([r for r in cc if 3 <= r[0] <= 8], lambda c: f"{c} fees a day")
    add_table(s, 0.6, 4.75, 8.2, 0.26 * len(rows), rows, [2.0, 1.4, 1.6, 1.6, 1.4], fs=9.5,
              highlight=tuple(i for i, r in enumerate(rows) if r[0] in ("4 fees a day", "5 fees a day", "6 fees a day")))
    c4, c6 = next(r for r in cc if r[0] == 4), next(r for r in cc if r[0] == 6)
    one = dist[0][1] if dist else 0
    tot = sum(r[1] for r in dist) or 1
    textbox(s, 9.0, 4.8, 3.75, 1.5, f"{pct(one / tot, 0)} of fee days carry one fee. A 4–6 cap returns "
                f"an estimated {usd(c6[4])}–{usd(c4[4])} a year ({pct(c6[5])}–{pct(c4[5])} of fees) to the {n_(c6[2])}–{n_(c4[2])} "
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
    tx = [["Transaction de minimis", "Fees waived", "Accounts", "A year (est.)", "% of rev."]] + \
        _curve_rows(nt["txn_curve"], lambda x: f"${x} or less")
    bl = [["Balance de minimis", "Fees waived", "Accounts", "A year (est.)", "% of rev."]] + \
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
    rows = [["Daily cap · a year (est.)"] + [c[2] for c in cols]]
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
        chart(s, 0.6, 3.8, 7.6, 2.3, cats, [("Returned to members a year (est.)", [r[5] for r in guided])], fmt='$#,##0',
              title="Within Velocity guidance: returned to members a year (est.)")
        fee_txt = ""
        if od_fee:
            fee_txt = (f" Holding today's revenue would take an OD fee of ${od_fee * lo[8]:,.2f}–${od_fee * hi[8]:,.2f} "
                       f"instead of ${od_fee:,.2f}.")
        textbox(s, 8.45, 3.85, 4.3, 2.4, f"Velocity's guidance (orange) returns an estimated {usd(lo[5])}–{usd(hi[5])} a year to "
                f"members, {pct(lo[6])}–{pct(hi[6])} of fee revenue.{fee_txt} The CSM and the client choose the "
                f"structure; these are the trade-offs.", 12, NAVY_RGB, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
    return s


def ch_insights(ctx):
    pack = ctx.pack
    ins = pack["metrics"].get("pgl_insights") or {}
    if not ins:
        s = content(ctx, "Opportunities & Risks", "Run with confirmed codes to compute them",
                    "Source: no insights in this run.")
        todo(s, "a confirmed run (the insights need the codes).")
        return [s]
    out = []
    dc = ins.get("declines") or {}
    if dc:
        s = content(ctx, "Debit Decline Opportunity", "Declined debit card transactions on open personal accounts",
                    _src(pack, "open personal accounts' Debit Decline Count and Amount; " + dc["note"]))
        bl = dc["by_limit"]
        chart(s, 0.6, 1.6, 6.2, 3.2, [r[0] for r in bl], [("Declines", [r[3] for r in bl])],
              title="Declines by proposed ILS limit", highlight=(0,))
        rows = [["", "Accounts with declines", "Declines", "Declined $"]] + [[r[0], n_(r[1]), n_(r[2]), usd(r[3])]
                                                                           for r in dc["by_rege"]]
        add_table(s, 7.0, 1.75, 5.75, 0.4 * len(rows), rows, [2.2, 1.3, 1.0, 1.25], fs=10)
        sc_rows = [["If eligible accounts' declines were paid", "Declines paid", "Fee revenue"]] + [
            [label, n_(n), usd(dollars)] for label, n, dollars in dc["scenarios"]]
        add_table(s, 7.0, 3.1, 5.75, 0.38 * len(sc_rows), sc_rows, [2.75, 1.4, 1.6], fs=10.5,
                  highlight=(len(sc_rows) - 1,))
        say(s, f"{n_(dc['declines'])} declines ({usd(dc['decline_dollars'])}) on {n_(dc['with_declines'])} accounts. "
               f"{n_(dc['rege_targets'])} eligible accounts with declines are not opted in to Reg E — the debit decline "
               f"communication list. Paying a share of eligible accounts' {n_(dc['eligible_declines'])} declines at the "
               f"OD fee{(' of $' + format(dc['od_fee'], ',.2f')) if dc.get('od_fee') else ''} earns what the table shows, in the "
               f"extract's decline window.", top=5.05, size=12, h=1.3)
        out.append(s)
    cc = ins.get("concentration") or {}
    if cc:
        s = content(ctx, "Heavy Users", "How much of the NSF/OD activity the heaviest accounts carry",
                    _src(pack, "open accounts by NSF/OD items since import and Rolling 12 Month NSF/OD fees"))
        tops = cc["tops"]
        chart(s, 0.6, 1.6, 6.0, 3.5, [r[0] for r in tops],
              [("% of NSF/OD items", [r[2] for r in tops]), ("% of Rolling 12 fees", [r[3] for r in tops])],
              fmt='0%', title="Share carried by the heaviest accounts", legend=True)
        rows = [["YTD OD items", "Accounts", "Items*", "Rolling 12 fees"]] + [[r[0], n_(r[1]), n_(r[2]), usd(r[3])]
                                                                             for r in cc["buckets"]]
        add_table(s, 6.85, 1.75, 5.9, min(3.6, 0.32 * len(rows)), rows, [2.4, 1.1, 1.1, 1.3], fs=10)
        t5 = next((r for r in tops if r[0] == "Top 5%"), None)
        if t5:
            say(s, f"The top 5% of open accounts ({n_(t5[1])}) carry {pct(t5[2])} of NSF/OD items and {pct(t5[3])} of "
                   f"Rolling 12 fees. They are the Heavy Usage Letter and counseling population. " + FOOT,
                top=5.5, size=12, h=0.9)
        out.append(s)
    ov = ins.get("overrides") or {}
    if ov:
        s = content(ctx, "Overrides & Trending", "Where the ILS rules cut a limit before it is set",
                    _src(pack, "open, eligible personal accounts' OVERRIDE (from ILS) and trending fields"))
        rows = [["Override", "Accounts", "Avg core limit", "Avg ILS limit", "Items*"]] + [
            [r[0], n_(r[1]), usd(r[2]), usd(r[3]), n_(r[4])] for r in ov["rows"][:9]]
        add_table(s, 0.6, 1.7, 7.6, min(3.9, 0.33 * len(rows)), rows, [3.6, 1.0, 1.1, 1.1, 0.8], fs=9.5)
        tr = [r for r in ov["trending"] if r[1]]
        if tr:
            rows2 = [["Trend", "Accounts set", "Cut", "Raised", "Total cut"]] + [
                [r[0].replace(" Trending", ""), n_(r[1]), n_(r[2]), n_(r[3]), usd(r[4])] for r in tr]
            add_table(s, 8.45, 1.7, 4.3, 0.36 * len(rows2), rows2, [1.3, 0.8, 0.7, 0.7, 0.8], fs=9.5)
        say(s, f"{n_(ov['with_override'])} of {n_(ov['accounts'])} eligible accounts carry an override. Review each "
               f"override's effect on limits before go-live. " + FOOT, top=5.75, size=12, h=0.8)
        out.append(s)
    na = ins.get("new_accounts") or {}
    if na.get("rows"):
        s = content(ctx, "New Accounts", f"Open personal accounts by how long they have been open (as of {na['as_of']})",
                    _src(pack, "open personal accounts by Open Date against the extract date"))
        rows = [["Account age", "Accounts", "At $0", "% at $0", "Avg ILS limit", "Reg E opt-in", "Items*"]] + [
            [r[0], n_(r[1]), n_(r[2]), pct(r[3]), usd(r[4]), pct(r[5]), n_(r[6])] for r in na["rows"]]
        add_table(s, 0.6, 1.75, 12.15, 0.45 * len(rows), rows, [3.2, 1.3, 1.2, 1.2, 1.5, 1.4, 1.2], fs=11)
        chart(s, 0.6, 3.75, 7.0, 2.3, [r[0] for r in na["rows"]], [("% at a $0 limit", [r[3] for r in na["rows"]])],
              fmt='0%', title="Share at a $0 proposed limit", highlight=(0,))
        n0 = na["rows"][0]
        textbox(s, 7.9, 3.9, 4.85, 2.2, f"{n_(n0[1])} accounts opened in the last 90 days; {pct(n0[3])} get a $0 limit "
                f"while the age-of-account rules apply, and {pct(n0[5])} are opted in to Reg E. Onboarding is the moment "
                f"to ask for the opt-in.", 12, NAVY_RGB, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
        out.append(s)
    for kind, sc in (ins.get("second_chance") or {}).items():
        title = kind.title()
        s = content(ctx, f"{title} Accounts", f"Open {title} accounts by OD status, and their proposed limits",
                    _src(pack, f"open accounts with Personal_Business = {kind}"))
        review_table(s, sc["od"], fs=9.5, names=pack["od_names"], height=min(2.6, 0.33 * (len(sc["od"]["rows"]) + 2)))
        lim = sc["limits"]
        if lim:
            chart(s, 0.6, 4.2, 8.0, 1.9, [usd(t) for t, _ in lim][:14], [("Eligible accounts", [n for _, n in lim][:14])],
                  title=f"Eligible {title} accounts by proposed limit")
        textbox(s, 8.9, 4.3, 3.85, 1.8, f"{n_(sc['open'])} open {title} accounts, {n_(sc['eligible'])} eligible. They are "
                f"scored on their own matrix (see the ILS Matrix chapter) and sit outside the personal tables.",
                12, NAVY_RGB, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
        out.append(s)
    dd = ins.get("days_od") or {}
    if dd.get("rows"):
        s = content(ctx, "Days Overdrawn", "Open accounts by how many days they have been overdrawn",
                    _src(pack, "open accounts' Days OD"))
        r = dd["rows"]
        chart(s, 0.6, 1.6, 6.6, 3.8, [x[0] for x in r[1:]], [("Accounts", [x[1] for x in r[1:]])],
              title="Overdrawn accounts by days overdrawn", highlight=tuple(i for i, x in enumerate(r[1:]) if x[0].startswith(("30", "45"))))
        rows = [["Days overdrawn", "Accounts", "Items*", "Avg ILS limit"]] + [[x[0], n_(x[1]), n_(x[2]), usd(x[3])] for x in r]
        add_table(s, 7.45, 1.75, 5.3, 0.38 * len(rows), rows, [1.9, 1.1, 1.1, 1.2], fs=10.5)
        risk = sum(x[1] for x in r if x[0].startswith(("30", "45")))
        say(s, f"{accts(risk)} overdrawn 30 days or more (the longest {dd['max']} days): the repayment and charge-off "
               f"watch list, where the Days OD overrides take the limit away.", top=5.65, size=12, h=0.8)
        out.append(s)
    pr = ins.get("products")
    if pr and pr.get("rows"):
        s = content(ctx, "Product Mix", "Open accounts by product code", _src(pack, "open accounts by Product Code"))
        review_table(s, pr, fs=9.5)
        out.append(s)
    rv = ins.get("revenue_check") or {}
    if rv.get("r12_fees_open") is not None:
        s = content(ctx, "Fee Revenue Check", "The extract's Rolling 12 Month fees against the notice items",
                    _src(pack, "Rolling 12 Month NSFOD Fees and Items; the notice items annualized"))
        rows = [["Measure", "Value"], ["Rolling 12 Month NSF/OD fees, open accounts", usd(rv["r12_fees_open"])],
                ["Rolling 12 Month NSF/OD fees, every live account", usd(rv["r12_fees_live"])],
                ["Rolling 12 Month NSF/OD items, open accounts", n_(rv["r12_items_open"])]]
        if rv.get("notice_annualized"):
            rows.append([f"Notice items, {rv['notice_days']} days annualized", usd(rv["notice_annualized"])])
            rows.append(["Rolling 12 (open) against the notice items", pct(rv["gap_pct"])])
        add_table(s, 0.6, 1.8, 8.6, 0.45 * len(rows), rows, [6.0, 2.6], fs=12)
        if rv.get("gap_pct") is not None:
            say(s, f"The two revenue measures differ by {pct(abs(rv['gap_pct']))}. Agree which baseline prices the "
                   f"program before any fee scenario is quoted.", top=5.0, size=13, h=0.8)
        out.append(s)
    return out


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
    Chapter("PGL8", "Opportunities & Risks", "Declines, heavy users, overrides, new accounts and more",
            "Where the program can grow", ch_insights),
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
    _space_agenda(found["agenda"])
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
