#!/usr/bin/env python3
"""
spend_trend_slides.py — two slides on debit spend per cardholder, placed after "Overall Debit
Swipes & Spend" (Aaron, 2026-10-12: "add the new debit card spend slides to the Brooks deck.
We may include those permanently.").

OPT-IN for now: build_ars_gen adds them when RPE_SPEND_SLIDES=1. Flip the default when they
go into every deck. Every figure comes from spend_trend; nothing is computed here.

  1. "Debit Spend per Cardholder" — the workbook's monthly spend over accounts with a card,
     with the like-for-like windows marked and compared in the tiles.
  2. "Cards in Use and Spend per Card" — from the ODD: cards with any spend in the month, spend
     per card in use, and spend per ARS-eligible account, each compared over the same windows.

Public entry points
-------------------
    chart_per_card(out_png, ST, w_in, h_in)
    chart_odd(out_png, ST, w_in, h_in)
    add_spend_trend_slides(prs, ST, ctx) -> [slide, slide]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, os.pardir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import spend_trend as STM                                                 # noqa: E402

TITLE_1 = "Debit Spend per Cardholder"
TITLE_2 = "Cards in Use and Spend per Card"
ANCHOR = "Overall Debit Swipes & Spend"
CHART_BOX = (0.6, 1.60, 8.75, 5.35)        # the NSF/OD and Swipes slides' chart box
TILES = [(9.6, 1.60, 3.2, 1.60), (9.6, 3.25, 3.2, 1.60), (9.6, 4.90, 3.2, 1.60)]
DPI = 200


def _money(v):
    return "n/a" if v is None else f"${v:,.0f}"


def _pct(cmp):
    return "n/a" if not cmp else f"{cmp['pct']:+.0f}%"


# ----------------------------------------------------------------- charts
def _axes(fig, ax, months):
    import periods
    from brand import TICK, MUTED, GRID, HAIRLINE
    ax.set_xticks(range(len(months)))
    ax.set_xticklabels(periods.axis_months(months), fontsize=11, rotation=periods.AXIS_ROTATION,
                       ha=periods.AXIS_HA, color=TICK)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color(HAIRLINE); ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=TICK, length=0, labelsize=11)
    ax.yaxis.grid(True, color=GRID, linewidth=1); ax.set_axisbelow(True)


def _mark_windows(ax, months, win):
    """Underline the two compared windows at the top of the plot, each in its own colour."""
    from brand import STEEL, ORANGE
    if not win:
        return
    idx = {m: i for i, m in enumerate(months)}
    for labels, colour, name in ((win["prior"], STEEL, win["prior_name"]), (win["current"], ORANGE, win["current_name"])):
        ms = [m for m in labels if m in idx]
        if not ms:
            continue
        ax.plot([idx[ms[0]] - 0.4, idx[ms[-1]] + 0.4], [1.0, 1.0], color=colour, linewidth=4,
                transform=ax.get_xaxis_transform(), clip_on=False, solid_capstyle="butt")
        ax.text((idx[ms[0]] + idx[ms[-1]]) / 2, 1.03, name, ha="center", va="bottom", fontsize=11,
                color=colour, fontweight="bold", transform=ax.get_xaxis_transform())


def chart_per_card(out, ST, w_in=CHART_BOX[2], h_in=CHART_BOX[3]):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    import periods
    from rpe_env import use_font
    from brand import NAVY, TICK, CHART_FONT

    periods.install_month_axis_guard()
    use_font(CHART_FONT)
    plt.rcParams["text.parse_math"] = False
    pc = ST["per_card"]
    months, vals = [x[0] for x in pc], [x[3] for x in pc]
    fig, ax = plt.subplots(figsize=(w_in, h_in))
    fig.subplots_adjust(left=0.11, right=0.98, top=0.84, bottom=0.17)
    ax.plot(range(len(vals)), vals, color=NAVY, linewidth=2.4, marker="o", markersize=5)
    _axes(fig, ax, months)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:,.0f}"))
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) or hi * 0.1
    ax.set_ylim(lo - pad * 0.4, hi + pad * 0.35)
    for i in (0, len(vals) - 1):
        ax.text(i, vals[i] + pad * 0.08, f"${vals[i]:,.0f}", ha="center", va="bottom", fontsize=11, color=TICK)
    ax.set_ylabel("Debit spend per account with a card, per month", color=TICK, fontsize=11)
    _mark_windows(ax, months, ST["windows"])
    fig.savefig(out, dpi=DPI, facecolor="white")
    plt.close(fig)
    return out


def chart_odd(out, ST, w_in=CHART_BOX[2], h_in=CHART_BOX[3]):
    """Two panels, one axis each: cards in use (top) and spend per card in use (bottom)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    import periods
    from rpe_env import use_font
    from brand import NAVY, STEEL, TICK, CHART_FONT

    periods.install_month_axis_guard()
    use_font(CHART_FONT)
    plt.rcParams["text.parse_math"] = False
    o = ST["odd"]
    months = o["months"]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(w_in, h_in), sharex=True)
    fig.subplots_adjust(left=0.11, right=0.98, top=0.86, bottom=0.16, hspace=0.42)
    a1.plot(range(len(months)), o["cards_in_use"], color=STEEL, linewidth=2.4, marker="o", markersize=4)
    # The window underlines and their labels sit just above the top panel's plot area, so the
    # panel title is padded clear of them (it collided with "Feb–Sep 25" on Brooks's deck).
    a1.set_title("Cards in use (any spend in the month)", loc="left", fontsize=12, color=NAVY, fontweight="bold", pad=26)
    a1.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    v2 = [v if v is not None else float("nan") for v in o["spend_per_card_in_use"]]
    a2.plot(range(len(months)), v2, color=NAVY, linewidth=2.4, marker="o", markersize=4)
    a2.set_title("Spend per card in use, per month", loc="left", fontsize=12, color=NAVY, fontweight="bold")
    a2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:,.0f}"))
    for ax in (a1, a2):
        _axes(fig, ax, months)
    a1.tick_params(labelbottom=False)
    _mark_windows(a1, months, ST["windows"])
    fig.savefig(out, dpi=DPI, facecolor="white")
    plt.close(fig)
    return out


# ----------------------------------------------------------------- wording
def selection_1(ST):
    pc = ST["per_card"]
    return (f"Selection: all debit-card-holding accounts, program-wide. Monthly debit spend over accounts "
            f"with a card, {pc[0][0]} – {pc[-1][0]} ({len(pc)} months).")


def selection_2(ST):
    o = ST["odd"]
    return (f"Selection: personal accounts in the ODD extract, {o['months'][0]} – {o['months'][-1]}. "
            f"Cards in use = accounts with a card that spent in the month; eligible = today's ARS-eligible "
            f"accounts open in the month.")


def notes_1(ST, ctx):
    win, cmp = ST["windows"], ST["per_card_cmp"]
    lines = [
        "OPT-IN SLIDE (RPE_SPEND_SLIDES=1), 2026-10-12.",
        "",
        f"Source: {ctx['wb_src']} — Key Trends, monthly debit spend ($M) and accounts with a card; complete months only "
        f"(the same rows as the Overall Debit Swipes & Spend slide).",
        "",
        "Method: spend per cardholder = the month's debit spend over accounts with a card. The comparison is "
        "like for like: the months of this year to date that the prior year also carries, averaged, against the "
        "same months a year earlier"
        + (f" — {win['prior_name']} against {win['current_name']} ({win['months']} months each)." if win
           else ". This series does not reach a year back, so no comparison is made; none is substituted."),
        "",
        STM.movement("Spend per cardholder", cmp),
    ]
    if ST.get("spend_cmp") and ST.get("cards_cmp"):
        s, c = ST["spend_cmp"], ST["cards_cmp"]
        lines.append(f"Spend itself: ${s['prior']:.2f}M to ${s['current']:.2f}M a month on average ({s['pct']:+.1f}%); "
                     f"accounts with a card: {c['prior']:,.0f} to {c['current']:,.0f} ({c['pct']:+.1f}%).")
    lines += ["", "Month, spend $M, accounts with card, spend per cardholder:"]
    lines += [f"  {m}: ${s:.2f}M, {n:,}, ${v:,.0f}" for m, s, n, v in ST["per_card"]]
    return "\n".join(lines)


def notes_2(ST, ctx):
    o, win = ST["odd"], ST["windows"]
    lines = [
        "OPT-IN SLIDE (RPE_SPEND_SLIDES=1), 2026-10-12.",
        "",
        f"Source: {ctx['odd_src']} — per-account monthly Sig $ + PIN $, Debit?, Business?, {o['eligible_column']}, "
        f"Date Opened / Date Closed. Months capped at the last complete month of the workbook's spend series.",
        "",
        "Selection: personal accounts (Business? not Yes). Cards in use = accounts with a card (Debit? = Yes) that "
        "spent anything in the month; spend per card in use = their spend over their count. Eligible = accounts the "
        f"latest Elig column marks eligible ({o['eligible_snapshot']:,} today), counted in a month only when open in "
        "it (Date Opened on or before the month's end, Date Closed empty or after the month's start).",
        "",
        "Caveat: the ODD is today's book. An account that closed before the extract is not in it, so earlier months "
        "are understated and these series describe the SHAPE of the growth; the workbook's figure on the slide "
        "before this one is the one to quote.",
        "",
        STM.movement("Cards in use", ST.get("cards_in_use_cmp"), fmt="{:,.0f}", unit=" a month"),
        STM.movement("Spend per card in use", ST.get("spend_per_card_in_use_cmp")),
        STM.movement("Spend per eligible account", ST.get("spend_per_eligible_cmp")),
    ]
    if win:
        lines.append(f"Windows: {win['prior_name']} against {win['current_name']}.")
    lines += ["", "Month, cards in use, spend per card in use, eligible open, spend per eligible, share of eligible spending:"]
    for i, m in enumerate(o["months"]):
        lines.append(f"  {m}: {o['cards_in_use'][i]:,}, {_money(o['spend_per_card_in_use'][i])}, "
                     f"{o['eligible_open'][i]:,}, {_money(o['spend_per_eligible'][i])}, "
                     + ("n/a" if o["eligible_active_share"][i] is None else f"{o['eligible_active_share'][i]:.1f}%"))
    return "\n".join(lines)


# ----------------------------------------------------------------- slides
def _place_after(prs, slide, after):
    import shapes as SH
    lst = prs.slides._sldIdLst
    src = SH.sldid_of(prs, slide)
    lst.remove(src)
    SH.sldid_of(prs, after).addnext(src)


def _frame(prs, anchor, title, pill, selection):
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from brand import NAVY_RGB, TICK_RGB, HEAD, BODY
    import shapes as SH
    s = SH.blank_slide(prs, anchor)
    SH.textbox(s, 0.5, 0.28, 9.6, 0.9, title, 26, NAVY_RGB, True, PP_ALIGN.LEFT, HEAD, MSO_ANCHOR.MIDDLE)
    SH.pill(s, pill)
    SH.textbox(s, 0.5, 1.06, 12.2, 0.4, selection, 16, TICK_RGB, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
    return s


def _tiles(s, items):
    import shapes as SH
    for (L, T, W, H), (value, label) in zip(TILES, items):
        SH.tile(s, L, T, W, H, value, label)


def add_spend_trend_slides(prs, ST, ctx):
    """Add both slides after ANCHOR and return them. ctx needs wb_src, odd_src, as_of_long, assets."""
    from pptx.util import Inches
    import shapes as SH

    if not ST["per_card"]:
        raise SystemExit("spend trend slides: the workbook carries no complete month of spend")
    anchor = next((x for x in prs.slides if SH.slide_title(x).startswith(ANCHOR)), None)
    if anchor is None:
        raise SystemExit(f"spend trend slides: no '{ANCHOR}' slide to place them after")
    win, cmp = ST["windows"], ST["per_card_cmp"]
    pill = f"{ctx['as_of_long']} Data"

    s1 = _frame(prs, anchor, TITLE_1, pill, selection_1(ST))
    L, T, W, H = CHART_BOX
    png = os.path.join(ctx["assets"], "spend_per_card.png")
    chart_per_card(png, ST, W, H)
    s1.shapes.add_picture(png, Inches(L), Inches(T), Inches(W), Inches(H))
    if cmp:
        _tiles(s1, [(_money(cmp["current"]), f"Spend per cardholder\n({win['current_name']}, monthly avg)"),
                    (_money(cmp["prior"]), f"Spend per cardholder\n({win['prior_name']}, monthly avg)"),
                    (_pct(cmp), f"Change, like for like\n({win['prior_name']} → {win['current_name']})")])
    else:
        _tiles(s1, [(_money(ST["per_card"][-1][3]), f"Spend per cardholder\n({ST['per_card'][-1][0]})"),
                    ("n/a", "Like-for-like change\n(no prior year in the series)"),
                    (f"{ST['per_card'][-1][2]:,}", f"Accounts with a card\n({ST['per_card'][-1][0]})")])
    s1.notes_slide.notes_text_frame.text = notes_1(ST, ctx)
    _place_after(prs, s1, anchor)
    made = [s1]

    if ST.get("odd"):
        s2 = _frame(prs, anchor, TITLE_2, pill, selection_2(ST))
        png2 = os.path.join(ctx["assets"], "spend_cards_in_use.png")
        chart_odd(png2, ST, W, H)
        s2.shapes.add_picture(png2, Inches(L), Inches(T), Inches(W), Inches(H))
        tiles = []
        for key, label, fmt in (("cards_in_use_cmp", "Cards in use", "{:,.0f}"),
                                ("spend_per_card_in_use_cmp", "Spend per card in use", "${:,.0f}"),
                                ("spend_per_eligible_cmp", "Spend per eligible account", "${:,.0f}")):
            c = ST.get(key)
            if c:
                tiles.append((f"{c['pct']:+.0f}%", f"{label}\n({fmt.format(c['prior'])} → {fmt.format(c['current'])} a month)"))
            else:
                tiles.append(("n/a", f"{label}\n(no prior year to compare)"))
        _tiles(s2, tiles)
        s2.notes_slide.notes_text_frame.text = notes_2(ST, ctx)
        _place_after(prs, s2, s1)
        made.append(s2)
    return made
