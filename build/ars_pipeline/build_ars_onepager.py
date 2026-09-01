#!/usr/bin/env python3
"""
build_ars_onepager.py — ARS executive one-pager, 8.5 x 11 portrait.

Matches the established RPE One-Pager format (header, orange rule, navy section
bar, four KPI tiles with an orange hero, narrative lines, CSI | Velocity footer)
and adds charts with callouts.

This is a PRINT handout, not a projected deck slide. It deliberately does NOT
run restyle_fonts / fit_layout / validate_deck — those enforce the 13.33x7.5
deck contract (16 pt floor, slide numbers bottom-left, logo bottom-right) which
would destroy a letter-size portrait layout. Typography matches the reference
one-pager exactly: Montserrat 23/21/14/9.5/9, Calibri 12/10.5/9.5.

SM-path clients (e.g. 1038 Sugar River) take financials from base_tab_extract;
account profile and Reg E come from the ODD data pack.

Usage:
  python3 build_ars_onepager.py <base.json> <oddd_metrics.json> <template.pptx> \
      <assets_dir> <out.pptx>
"""
import datetime
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), _os.pardir))  # build/
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

# ---------------------------------------------------------------- palette
from rpe_env import use_font
import re
from periods import Period, parse_month
from brand import (
    CHART_FONT,
    NAVY_RGB as NAVY, ORANGE_RGB as ORANGE, PEACH_RGB as PEACH,
    TILE_RGB as TILE, WHITE_RGB as WHITE, TICK_RGB as GREYT,
    NAVY as NAVY_HEX, ORANGE as ORANGE_HEX, TICK as TICK_HEX, GRID as GRID_HEX,
    STEEL_SOFT, LIGHT,
    HEAD, BODY,
)

PAGE_W, PAGE_H = 8.5, 11.0
M = 0.45                                # left/right margin
CW = 7.60                               # content width


def _tb(slide, L, T, W, H, text, size, color, bold, align=PP_ALIGN.LEFT,
        font=BODY, anchor=MSO_ANCHOR.MIDDLE, space=None):
    box = slide.shapes.add_textbox(Inches(L), Inches(T), Inches(W), Inches(H))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0
    lines = [text] if isinstance(text, str) else text
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if space:
            p.line_spacing = space
        r = p.add_run()
        r.text = ln
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.name = font
        r.font.color.rgb = color
    return box


def _rect(slide, L, T, W, H, fill):
    sp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(L), Inches(T),
                                Inches(W), Inches(H))
    sp.fill.solid()
    sp.fill.fore_color.rgb = fill
    sp.line.fill.background()
    sp.shadow.inherit = False
    return sp


def _tile(slide, L, T, W, H, value, label, hero=False, vsize=21, lsize=9.5):
    """Boxes scale WITH the tile height — a fixed value-box height collides
    with the label on short tiles. Proportions mirror the reference one-pager
    (value 0.172H/0.469H, label 0.625H/0.328H)."""
    _rect(slide, L, T, W, H, ORANGE if hero else TILE)
    _tb(slide, L, T + H * 0.172, W, H * 0.469, value, vsize,
        WHITE if hero else NAVY, True, PP_ALIGN.CENTER, HEAD)
    _tb(slide, L + 0.06, T + H * 0.625, W - 0.12, H * 0.328, label, lsize,
        WHITE if hero else GREYT, False, PP_ALIGN.CENTER, BODY,
        MSO_ANCHOR.TOP)


def _section(slide, T, title, topics):
    _rect(slide, M, T, CW, 0.44, NAVY)
    _tb(slide, M + 0.18, T + 0.02, 4.26, 0.44, title, 14, WHITE, True,
        PP_ALIGN.LEFT, HEAD)
    _tb(slide, M + 4.18, T + 0.02, 3.24, 0.44, topics, 9.5, PEACH, True,
        PP_ALIGN.RIGHT, HEAD)


# ---------------------------------------------------------------- charts
def _prep():
    """Set the chart face, failing loudly if it is missing.

    This used to loop over ("Carlito", "Calibri", "DejaVu Sans") inside a
    try/except. Assigning rcParams["font.family"] NEVER raises for a missing
    family — matplotlib substitutes silently at draw time — so the loop always
    broke on the first entry and the fallback was unreachable. On a machine
    without Carlito every one-pager chart rendered in DejaVu and nothing said
    so. use_font checks availability up front, which is the whole reason it
    exists; the one-pager was the last renderer still bypassing it.
    """
    use_font(CHART_FONT)


def chart_revenue12(series, out_png, w=5.25, h=2.15):
    """12-month incremental revenue: navy bars, latest month orange."""
    _prep()
    labels = [m for m, _ in series]
    vals = [v / 1000.0 for _, v in series]
    fig = plt.figure(figsize=(w, h), dpi=300)
    ax = fig.add_axes([0.105, 0.155, 0.875, 0.79])
    colors = [NAVY_HEX] * len(vals)
    colors[-1] = ORANGE_HEX
    bars = ax.bar(range(len(vals)), vals, color=colors, width=0.70, zorder=3)
    top = max(vals)
    ax.set_ylim(0, top * 1.22)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + top * 0.035, f"{v:,.0f}",
                ha="center", va="bottom", fontsize=6.5, color=NAVY_HEX,
                fontweight="bold", zorder=4)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels([l[:3] + " '" + l[-2:] for l in labels], fontsize=6.5,
                       color=TICK_HEX)
    ax.set_yticks([0, 20, 40, 60])
    ax.set_yticklabels(["$0K", "$20K", "$40K", "$60K"], fontsize=6.5,
                       color=TICK_HEX)
    ax.tick_params(length=0)
    ax.grid(axis="y", color=GRID_HEX, linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(LIGHT)
    fig.savefig(out_png, dpi=300, facecolor="white")
    plt.close(fig)
    return out_png


def chart_spend36(series, out_png, w=5.25, h=2.15):
    """36-month debit spend ($M navy bars) + card base (orange line)."""
    _prep()
    labels = [r[0] for r in series]
    spend = [r[1] for r in series]
    cards = [r[2] for r in series]
    fig = plt.figure(figsize=(w, h), dpi=300)
    ax = fig.add_axes([0.105, 0.155, 0.79, 0.79])
    ax.bar(range(len(spend)), spend, color=NAVY_HEX, width=0.72, zorder=3)
    ax.set_ylim(0, max(spend) * 1.28)
    ax.set_yticks([0, 3, 6, 9])
    ax.set_yticklabels(["$0M", "$3M", "$6M", "$9M"], fontsize=6.5,
                       color=TICK_HEX)
    step = max(1, len(labels) // 6)
    idx = list(range(0, len(labels), step))
    ax.set_xticks(idx)
    ax.set_xticklabels([labels[i][:3] + " '" + labels[i][-2:] for i in idx],
                       fontsize=6.5, color=TICK_HEX)
    ax.tick_params(length=0)
    ax.grid(axis="y", color=GRID_HEX, linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)
    ax2 = ax.twinx()
    ax2.plot(range(len(cards)), cards, color=ORANGE_HEX, linewidth=1.8,
             zorder=5)
    ax2.set_ylim(min(cards) * 0.90, max(cards) * 1.06)
    ax2.set_yticks([min(cards), max(cards)])
    ax2.set_yticklabels([f"{min(cards):,}", f"{max(cards):,}"], fontsize=6.5,
                        color=ORANGE_HEX)
    ax2.tick_params(length=0)
    for a in (ax, ax2):
        for s in ("top", "right", "left"):
            a.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(LIGHT)
    fig.savefig(out_png, dpi=300, facecolor="white")
    plt.close(fig)
    return out_png


def chart_before_after(ra, out_png, w=5.25, h=1.82):
    """Responder debit spend, 3-month pre-mailing baseline vs after.
    Before = steel, After = orange, mean and median side by side."""
    _prep()
    groups = [("Mean", ra["ba_spend_before"], ra["ba_spend_after"]),
              ("Median", ra["ba_spend_med_before"], ra["ba_spend_med_after"])]
    fig = plt.figure(figsize=(w, h), dpi=300)
    ax = fig.add_axes([0.105, 0.13, 0.875, 0.74])
    top = max(max(b, a) for _, b, a in groups)
    for i, (lab, before, after) in enumerate(groups):
        for k, (v, col) in enumerate(((before, STEEL_SOFT), (after, ORANGE_HEX))):
            x = i + (k - 0.5) * 0.34
            ax.bar(x, v, color=col, width=0.31, zorder=3)
            ax.text(x, v + top * 0.045, f"${v:,.0f}", ha="center", va="bottom",
                    fontsize=7, color=NAVY_HEX, fontweight="bold", zorder=4)
    ax.set_ylim(0, top * 1.26)
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels([g[0] for g in groups], fontsize=7.5, color=TICK_HEX)
    ax.set_yticks([0, 500, 1000])
    ax.set_yticklabels(["$0", "$500", "$1,000"], fontsize=6.5, color=TICK_HEX)
    ax.tick_params(length=0)
    ax.grid(axis="y", color=GRID_HEX, linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(LIGHT)
    ax.bar(0, 0, color=STEEL_SOFT, label="3 months before mailing")
    ax.bar(0, 0, color=ORANGE_HEX, label="Every month after")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.20), ncol=2,
              frameon=False, fontsize=7, labelcolor=TICK_HEX,
              handlelength=1.1, columnspacing=1.4)
    fig.savefig(out_png, dpi=300, facecolor="white")
    plt.close(fig)
    return out_png


# ---------------------------------------------------------------- helpers
def money(v):
    a = abs(v)
    if a >= 1_000_000:
        return f"${v/1_000_000:,.2f}M"
    if a >= 1_000:
        return f"${v/1_000:,.0f}K"
    return f"${v:,.0f}"


def rege_counts(metrics):
    """Aaron's 1038 Reg E mapping: Failed to Respond + Revoked -> Default;
    Exempt + Ineligible -> excluded. Opt-in RATE is unaffected (Default is not
    in the IN/(IN+OUT) denominator)."""
    f = metrics["funnel"]
    opt_in, opt_out = f["regE_optin_accepted"], f["regE_optin_declined"]
    default = f.get("regE_no_response", 0)
    excluded = 0
    for k, n in (metrics.get("flags", {}).get("regE_unmapped", {}) or {}).items():
        kl = k.lower()
        if "failed to respond" in kl or "revoked" in kl:
            default += n
        elif "exempt" in kl or "ineligib" in kl:
            excluded += n
    rate = 100.0 * opt_in / (opt_in + opt_out) if (opt_in + opt_out) else 0.0
    return {"in": opt_in, "out": opt_out, "default": default,
            "excluded": excluded, "rate": rate}


def blank_page(prs):
    xml_slides = prs.slides._sldIdLst
    for sld in list(xml_slides):
        prs.part.drop_rel(sld.get(qn('r:id')))
        xml_slides.remove(sld)
    prs.slide_width = Inches(PAGE_W)
    prs.slide_height = Inches(PAGE_H)
    layout = next((l for l in prs.slide_layouts
                   if "blank" in (l.name or "").lower()), prs.slide_layouts[-1])
    s = prs.slides.add_slide(layout)
    for sh in list(s.shapes):
        sh._element.getparent().remove(sh._element)
    return s


def _reporting_month(out_path):
    """The month the report is PRESENTED, not the data month (STYLE.md:85).

    Resolution order, matching build_ars_gen's PRESENT_MONTH so a one-pager and
    its deck can never disagree:

      1. RPE_PERIOD / ARS_PERIOD;
      2. the <yyyy.mm> tag in the output filename;
    There is deliberately no third option. Not the wall clock: date.today() was
    the original bug, right only while a one-pager is built in the month it ships
    and silently wrong on every rebuild after. And not the Executive Summit's
    month either — a Summit runs a couple of times a year and only for attendees,
    while this is part of the MONTHLY client delivery (Aaron, 2026-08-29).
    """
    per = os.environ.get("RPE_PERIOD") or os.environ.get("ARS_PERIOD") or ""
    if not per:
        m = re.search(r"(\d{4})\.(\d{2})", os.path.basename(out_path or ""))
        per = f"{m.group(1)}.{m.group(2)}" if m else ""
    try:
        return datetime.date(int(per[:4]), int(per[5:7]), 1).strftime("%B %Y")
    except (ValueError, IndexError):
        raise SystemExit(
            "cannot resolve the reporting month — set RPE_PERIOD=YYYY.MM or name the "
            "output <id>-<yyyy.mm>-... (got %r)" % os.path.basename(out_path or ""))


# ---------------------------------------------------------------- build
def build(base, metrics, template, assets, out, ra=None):
    cid = str(metrics.get("client", "")).strip()
    name = base.get("client") or metrics.get("name")
    data_label = base.get("data_label", "")
    period = data_label.replace(" Data", "").strip()
    # STYLE.md draws a hard line between two months, and this header is the
    # first kind:
    #   reporting month = the month the report is PRESENTED (STYLE.md:85)
    #   data month      = what the period pills and PTD figures run through
    #                     (STYLE.md:44 — explicitly "NOT the report month")
    # So this is deliberately NOT the data month. It was date.today(), which is
    # right only while the one-pager is built in the month it ships; rebuilt
    # later it silently moves. Resolved the way build_ars_gen resolves
    # PRESENT_MONTH — from RPE_PERIOD, else the output filename's <yyyy.mm> —
    # and only then from the clock.
    report_month = _reporting_month(out)

    rg = rege_counts(metrics)
    f = metrics["funnel"]
    rev12 = base["monthly_rev_last12"]
    ss = base["swipespend_36"]
    sp0, sp1 = ss[0][1], ss[-1][1]
    cd0, cd1 = ss[0][2], ss[-1][2]
    spend_growth = 100.0 * (sp1 - sp0) / sp0
    best_m, best_v = max(rev12, key=lambda x: x[1])

    prs = Presentation(template)
    s = blank_page(prs)

    # ---- header
    _tb(s, M, 0.34, CW, 0.50, name, 23, NAVY, True, PP_ALIGN.LEFT, HEAD)
    _tb(s, M, 0.84, CW, 0.28,
        f"Retail Performance Engine  •  Executive Overview  •  {report_month}",
        12, GREYT, False, PP_ALIGN.LEFT, BODY)
    _rect(s, M, 1.16, CW, 0.04, ORANGE)

    # ---- section + headline tiles
    _section(s, 1.30, "Account Revenue Solution®",
             "Revenue  •  Debit Growth  •  Responder Activity")
    tiles = [
        (money(base["ltd_revenue"]), "Revenue, Program-to-Date", True),
        (money(base["ltd_profit"]), f"Net Profit to {name}", False),
        (f"{base['profitability']:,.2f} : 1", "Return on Program Cost", False),
        (f"{ra['reach_total']:,}", "Customers Reached", False),
    ]
    for i, (val, lab, hero) in enumerate(tiles):
        _tile(s, M + i * 1.935, 1.86, 1.80, 1.28, val, lab, hero)

    _tb(s, 0.47, 3.22, 7.56, 0.56,
        f"{base['mailings']} mailings over {base['months']} months have produced "
        f"{money(base['ltd_revenue'])} in revenue against "
        f"{money(abs(base['ltd_costs']))} in program cost — "
        f"${base['profitability']:,.2f} returned for every dollar spent. "
        f"{ra['depth_repeat_pct']}% of responders have come back for two or more "
        f"mailings. {f['enrolled']:,} accounts are enrolled against "
        f"{base['dco_eligible']:,} eligible, with Reg E opt-in at "
        f"{rg['rate']:.1f}%.",
        10.5, GREYT, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP, space=1.15)

    # ---- chart A: monthly incremental revenue, 12 months
    _tb(s, M, 3.90, 5.25, 0.24, "Monthly Incremental Revenue — Last 12 Months",
        11, NAVY, True, PP_ALIGN.LEFT, HEAD)
    s.shapes.add_picture(chart_revenue12(rev12,
                                         os.path.join(assets, "op_rev12.png")),
                         Inches(M), Inches(4.16), Inches(5.25), Inches(1.82))
    _tile(s, 5.90, 4.16, 2.15, 0.85, f"${base['monthly_rev_sum12']:,}",
          "Revenue, last 12 months", False, vsize=14, lsize=8)
    _tile(s, 5.90, 5.13, 2.15, 0.85, money(best_v),
          f"{best_m} — highest of the 12", False, vsize=14, lsize=8)

    # ---- chart B: debit spend + card base, 36 months
    _tb(s, M, 6.14, 5.25, 0.24, "Monthly Debit Spend & Card Base — 36 Months",
        11, NAVY, True, PP_ALIGN.LEFT, HEAD)
    s.shapes.add_picture(chart_spend36(ss,
                                       os.path.join(assets, "op_spend36.png")),
                         Inches(M), Inches(6.40), Inches(5.25), Inches(1.82))
    _tile(s, 5.90, 6.40, 2.15, 0.85, f"+{spend_growth:,.1f}%",
          f"Debit spend, ${sp0:,.1f}M → ${sp1:,.1f}M", True, vsize=14, lsize=8)
    _tile(s, 5.90, 7.37, 2.15, 0.85, f"{cd1:,}",
          f"Cards in force, up from {cd0:,}", False, vsize=14, lsize=8)

    # ---- chart C: responder activity before vs after
    _tb(s, M, 8.38, 5.25, 0.24,
        "Responder Debit Spend — Before vs After Mailing", 11, NAVY, True,
        PP_ALIGN.LEFT, HEAD)
    s.shapes.add_picture(chart_before_after(ra,
                                            os.path.join(assets, "op_ba.png")),
                         Inches(M), Inches(8.64), Inches(5.25), Inches(1.82))
    _tile(s, 5.90, 8.64, 2.15, 0.85, f"+{ra['ba_pct_mean']:,.0f}%",
          f"Responder spend, ${ra['ba_spend_before']:,} → "
          f"${ra['ba_spend_after']:,}", True, vsize=14, lsize=8)
    _tile(s, 5.90, 9.61, 2.15, 0.85, f"+{ra['dot_mean']:,.1f}",
          "Transactions over the ask, per month", False, vsize=14, lsize=8)

    # ---- footer
    _tb(s, M, 10.62, CW, 0.30, "CSI  •  Velocity Solutions", 9, NAVY, True,
        PP_ALIGN.RIGHT, HEAD)

    # ---- sources in the notes (this client only)
    odd = metrics.get("source_file", "")
    pull = odd.rsplit("(", 1)[-1].split(")")[0] if "(" in odd else ""
    notes = (
        f"Client: {cid} {name}. ARS executive one-pager (8.5x11 portrait "
        f"handout).\n"
        f"Selection: ARS-eligible checking accounts, program to date through "
        f"{period}.\n"
        f"Financials (SM revenue model — interchange + NSF computed on the "
        f"individual mailing tabs): {os.environ.get('ARS_WB_FILE', 'ARS workbook')}, "
        f"Executive Financials + All Months Rollup (Total Interchange Revenue + "
        f"Total NSF Revenue), {data_label}. Revenue-to-date "
        f"{base['ltd_revenue']:,.0f}; costs {base['ltd_costs']:,.0f}; "
        f"return {base['profitability']:.2f}:1.\n"
        f"12-month chart: {rev12[0][0]} – {rev12[-1][0]}, total "
        f"${base['monthly_rev_sum12']:,}.\n"
        f"36-month chart: Key Trends MM — total debit spend ($M) and "
        f"card-holding accounts, {ss[0][0]} – {ss[-1][0]}.\n"
        f"Responder before/after: ODD extract, method per "
        f"build/ars_pipeline/metrics_gen.py — eligible personal responders "
        f"across {ra['ba_n_mailings']} mature mailings; mean monthly debit "
        f"spend over the 3 months before each mailing vs every month after, "
        f"winsorized at 3 SD. Mean ${ra['ba_spend_before']:,} -> "
        f"${ra['ba_spend_after']:,} ({ra['ba_pct_mean']:+.1f}%); median "
        f"${ra['ba_spend_med_before']:,} -> ${ra['ba_spend_med_after']:,} "
        f"({ra['ba_pct_med']:+.1f}%). Transactions over the ask: swipes in the "
        f"month after the latest met-goal offer minus that offer's goal, mean "
        f"{ra['dot_mean']:+.1f} / median {ra['dot_median']:+.1f} across "
        f"{ra['dot_n']:,} responders. Customers reached {ra['reach_total']:,} "
        f"(~{ra['reach_perml']}/mailing); {ra['depth_repeat_pct']}% responded "
        f"to two or more mailings.\n"
        f"Eligible accounts: {os.environ.get('ARS_DCO_FILE', 'DCO file')} "
        f"(Eligible ARS Accounts = {base['dco_eligible']:,}).\n"
        f"Account profile and Reg E: ODD extract {odd}"
        + (f", pull stamp {pull}" if pull else "")
        + f", latest month {metrics.get('latest_month')}.\n"
        f"Reg E mapping (Aaron, 2026-07-24, 1038-specific): Failed to Respond + "
        f"Revoked -> Reg E Default ({rg['default']:,}); Exempt + Ineligible "
        f"excluded as not-applicable ({rg['excluded']:,}). Opt-in rate = "
        f"{rg['in']:,} / ({rg['in']:,} + {rg['out']:,}) = {rg['rate']:.1f}%.\n"
        f"Format note: print handout — deck rules for the 16 pt floor, slide "
        f"numbers and corner logo do not apply; typography matches the RPE "
        f"One-Pager reference."
    )
    s.notes_slide.notes_text_frame.text = notes

    prs.save(out)
    return out


if __name__ == "__main__":
    base_p, met_p, template, assets, out = sys.argv[1:6]
    resp_p = sys.argv[6] if len(sys.argv) > 6 else None
    os.makedirs(assets, exist_ok=True)
    build(json.load(open(base_p, encoding="utf-8")), json.load(open(met_p, encoding="utf-8")), template, assets,
          out, json.load(open(resp_p, encoding="utf-8")) if resp_p else None)
    print(f"wrote {out}")
