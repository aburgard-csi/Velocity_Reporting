#!/usr/bin/env python3
"""
sustained_split_slide.py — TEST slide: sustained responder activity by mailing, split into the
Non-User and Threshold offer segments (Aaron, 2026-10-02: "create a test slide showing Non
User sustained usage and Threshold sustained usage split out").

OPT-IN ONLY. build_ars_gen adds it when RPE_TEST_SLIDES=1 (or RPE_JAMES_SLIDES=1, the review
copy), directly after "Sustained Respondent Activity by Mailing", which stays exactly as it
was. The monthly build and the golden deck's slide count are unchanged.

The figures are metrics_gen's M['sustained_split'], computed by sustained_split.by_mailing in
the same pass as the existing slide's bars, so the definition is the same by construction and
the segments reconcile with the total (checked here; a mismatch stops the build).

  * a mailing with no month after it yet (post window 0) reads 100% by definition for every
    segment, so it is LEFT OUT of the chart and stated in the caption and the notes;
  * a segment with fewer than sustained_split.SMALL_N responders is drawn hatched and
    listed in the notes, never hidden.

Public entry points
-------------------
    chart(out_png, rows, w_in, h_in)
    caption_text(rows)
    add_sustained_split_slide(prs, M, ctx) -> slide
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, os.pardir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import sustained_split as SS                                              # noqa: E402

TITLE = "Sustained Activity: Non-User vs Threshold"
ANCHOR = "Sustained Respondent Activity by Mailing"
CHART_BOX = (0.5, 1.62, 12.3, 4.15)       # L, T, W, H inches; the PNG is drawn at W x H
CAPTION_BOX = (0.5, 5.86, 10.6, 1.0)
DPI = 200


def _n(count, singular, plural=None):
    return f"{count:,} {singular if count == 1 else (plural or singular + 's')}"


def mature(rows):
    return [e for e in rows if e["post"]]


def pending(rows):
    return [e for e in rows if not e["post"]]


def small_segments(rows):
    """[(mailing label, segment, n)] for every charted segment under SS.SMALL_N responders."""
    return [(e["m"], s, e[s]["n"]) for e in mature(rows) for s in SS.SEGMENTS
            if e[s]["n"] < SS.SMALL_N]


def check_reconciles(rows):
    """NU + TH + OTHER must equal the total, in responders and in those sustained."""
    bad = [e["m"] for e in rows
           if sum(e[k]["n"] for k in ("NU", "TH", "OTHER")) != e["all"]["n"]
           or sum(e[k]["ok"] for k in ("NU", "TH", "OTHER")) != e["all"]["ok"]]
    if bad:
        raise SystemExit("sustained split: the Non-User / Threshold segments do not add up to "
                         "the total for " + ", ".join(bad))


# ----------------------------------------------------------------- chart
def chart(out, rows, w_in=CHART_BOX[2], h_in=CHART_BOX[3]):
    """Grouped columns per mailing: Non-User navy, Threshold orange, each labelled with its
    share. A segment under SMALL_N responders is hatched; a segment with no responders draws
    no bar and is marked with a dash. Drawn at the picture box's own size, so 12 pt here is
    12 pt on the slide."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    import periods
    from rpe_env import use_font
    from brand import NAVY, ORANGE, TICK, MUTED, CHART_FONT

    periods.install_month_axis_guard()
    use_font(CHART_FONT)
    rows = mature(rows)
    fig, ax = plt.subplots(figsize=(w_in, h_in))
    fig.subplots_adjust(left=0.02, right=0.99, top=0.88, bottom=0.19)
    x = list(range(len(rows)))
    w = 0.38
    colours = {"NU": NAVY, "TH": ORANGE}
    for k, off in (("NU", -w / 2), ("TH", w / 2)):
        for xi, e in zip(x, rows):
            c = e[k]
            if not c["n"]:
                ax.text(xi + off, 1.5, "–", ha="center", va="bottom", color=TICK, fontsize=12)
                continue
            small = c["n"] < SS.SMALL_N
            ax.bar(xi + off, c["pct"], w, color=colours[k], alpha=0.45 if small else 1.0,
                   hatch="//" if small else None, edgecolor="white", linewidth=0.6)
            ax.text(xi + off, c["pct"] + 1.5, f"{c['pct']:.0f}%", ha="center", va="bottom",
                    color=NAVY, fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(periods.axis_months([e["m"] for e in rows]), fontsize=12,
                       rotation=periods.AXIS_ROTATION, ha=periods.AXIS_HA, color=NAVY)
    top = max([e[k]["pct"] for e in rows for k in SS.SEGMENTS if e[k]["n"]] + [10])
    ax.set_ylim(0, min(top * 1.18, 118))
    ax.set_xlim(-0.6, len(rows) - 0.4)
    ax.get_yaxis().set_visible(False)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=TICK, length=0)
    handles = [Patch(facecolor=NAVY, label="Non-User (NU) responders"),
               Patch(facecolor=ORANGE, label="Threshold (TH) responders")]
    if small_segments(rows):
        handles.append(Patch(facecolor=MUTED, alpha=0.6, hatch="//", edgecolor="white",
                             label=f"Hatched: fewer than {SS.SMALL_N} responders"))
    fig.legend(handles=handles, loc="upper center", ncol=len(handles), frameon=False,
               fontsize=13, bbox_to_anchor=(0.5, 1.0))
    fig.savefig(out, dpi=DPI, facecolor="white")
    plt.close(fig)
    return out


# ----------------------------------------------------------------- wording
def caption_text(rows):
    """Derived from the figures on the slide: the pooled share for each segment over the
    mailings that have a month after them, and the mailing left out, by name."""
    m = mature(rows)
    parts = []
    if m:
        nu, th = SS.pooled(m, "NU"), SS.pooled(m, "TH")
        segs = []
        for name, p in (("Non-User", nu), ("Threshold", th)):
            if p["n"]:
                # rounded once, from the counts (not from the 1-dp share: 44.497 -> 44.5 -> "44")
                segs.append(f"{100 * p['ok'] / p['n']:.0f}% of {name} responses "
                            f"({p['ok']:,} of {p['n']:,})")
            else:
                segs.append(f"no {name} responses")
        parts.append(f"Across the {_n(len(m), 'mailing')} with a month after them, "
                     f"{segs[0]} and {segs[1]} still meet the ask they responded to.")
    for e in pending(rows):
        parts.append(f"{e['m']} is left out: no month after it yet, so every responder reads "
                     f"100% by definition ({e['NU']['n']:,} Non-User, "
                     f"{e['TH']['n']:,} Threshold).")
    return " ".join(parts)


def notes_text(rows, M, ctx):
    m = mature(rows)
    lines = [
        "TEST SLIDE — opt-in (RPE_TEST_SLIDES=1 or RPE_JAMES_SLIDES=1); not part of the monthly build.",
        "",
        f"Source: {ctx['odd_src']} — per-mailing '<Mon> Mail' (the offer sent) and '<Mon> Resp' "
        f"(the result), and monthly Sig # + PIN # swipes.",
        "",
        "Selection: personal accounts whose '<Mon> Resp' reached a goal tier (NU 5+, TH-10 to "
        "TH-25) for each of the latest 12 mailings that have a month after them in the extract; "
        "current eligibility is not required, so a responder who has since closed still counts, "
        "as on the Sustained Respondent Activity slide. Segment = the offer sent for that "
        "mailing: 'NU' = Non-User (no prior debit usage, asked to start), 'TH-nn' = Threshold "
        "(an existing user asked to reach nn swipes); a blank offer falls back to the result "
        "('NU 5+' / 'TH-nn').",
        "",
        "Method: the same definition as the Sustained Respondent Activity slide, from the same "
        "computation (sustained_split.by_mailing). The response month is the month after the "
        "mailing; a responder is sustained when their average monthly swipes over every complete "
        "month from mailing + 2 onward are at or above the ask attached to that mailing. A "
        "mailing with no such month yet reads 100% by definition and is left off the chart. "
        "Pooled shares in the caption count responses, so a repeat responder counts once per "
        "mailing.",
    ]
    try:
        import month_complete as MC
        ex = MC.excluded_sentence((M.get("month_completeness") or {}).get("activity"))
        if ex:
            lines += ["", "Complete months only: " + ex]
    except Exception:                                   # pragma: no cover
        pass
    lines += ["", "Responders by mailing (sustained / responders, share; post-window months):"]
    for e in rows:
        cells = []
        for k in SS.SEGMENTS:
            c = e[k]
            flag = " [small]" if c["n"] and c["n"] < SS.SMALL_N and e["post"] else ""
            cells.append(f"{SS.SEGMENT_NAMES[k]} {c['ok']:,}/{c['n']:,}"
                         + (f" = {c['pct']:.1f}%" if c["pct"] is not None else "") + flag)
        other = f"; other offer codes {e['OTHER']['n']:,}" if e["OTHER"]["n"] else ""
        win = (f"{e['post']} month{'s' if e['post'] != 1 else ''}" if e["post"]
               else "no month after it yet - 100% by definition, not charted")
        lines.append(f"  {e['m']}: {cells[0]}; {cells[1]}{other}; total "
                     f"{e['all']['ok']:,}/{e['all']['n']:,} = {e['all']['pct']:.1f}% ({win})")
    small = small_segments(rows)
    if small:
        lines += ["", f"!! Small segments (fewer than {SS.SMALL_N} responders, hatched on the "
                      f"chart; read the share with care): "
                  + "; ".join(f"{mm} {SS.SEGMENT_NAMES[s]} ({n})" for mm, s, n in small)]
    other = sum(e["OTHER"]["n"] for e in rows)
    if other:
        lines += ["", f"!! {other:,} responses carry an offer code that is neither NU nor TH-*; "
                      f"they are in the total and in neither segment."]
    else:
        lines += ["", "ok Every response is in one of the two segments; NU + TH equals the "
                      "total on the Sustained Respondent Activity slide for every mailing."]
    if m:
        nu, th = SS.pooled(m, "NU"), SS.pooled(m, "TH")
        lines += ["", "Pooled over the charted mailings: "
                  + "; ".join(f"{SS.SEGMENT_NAMES[k]} {p['ok']:,}/{p['n']:,}"
                              + (f" = {p['pct']:.1f}%" if p["pct"] is not None else "")
                              for k, p in (("NU", nu), ("TH", th)))]
    return "\n".join(lines)


# ----------------------------------------------------------------- slide
def add_sustained_split_slide(prs, M, ctx):
    """Add the test slide after ANCHOR and return it. ctx needs odd_src, as_of_long, assets."""
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from brand import NAVY_RGB, TICK_RGB, HEAD, BODY
    import shapes as SH

    rows = M.get("sustained_split")
    if rows is None:
        raise SystemExit("sustained split slide: metrics.json has no 'sustained_split' — "
                         "rebuild metrics with the current metrics_gen")
    check_reconciles(rows)
    anchor = next((s for s in prs.slides if SH.slide_title(s).startswith(ANCHOR)), None)
    if anchor is None:
        raise SystemExit(f"sustained split slide: no '{ANCHOR}' slide to place it after")
    s = SH.blank_slide(prs, anchor)
    SH.textbox(s, 0.5, 0.28, 9.6, 0.9, TITLE, 26, NAVY_RGB, True, PP_ALIGN.LEFT, HEAD,
               MSO_ANCHOR.MIDDLE)
    SH.pill(s, f"{ctx['as_of_long']} Data")
    SH.textbox(s, 0.5, 1.12, 12.3, 0.45,
               "Selection: ARS responders by mailing, by the offer they were sent. Share still "
               "meeting their ask in the months after the mailing.",
               16, TICK_RGB, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
    if mature(rows):
        L, T, W, H = CHART_BOX
        png = os.path.join(ctx["assets"], "sustained_split.png")
        chart(png, rows, W, H)
        from pptx.util import Inches
        s.shapes.add_picture(png, Inches(L), Inches(T), Inches(W), Inches(H))
        L, T, W, H = CAPTION_BOX
        SH.textbox(s, L, T, W, H, caption_text(rows), 16, TICK_RGB, False, PP_ALIGN.LEFT,
                   BODY, MSO_ANCHOR.TOP)
    else:
        SH.textbox(s, 0.5, 2.4, 12.3, 1.4,
                   "No mailing in this extract has a month after its response month yet, so "
                   "sustained activity cannot be split by segment for this period. "
                   + caption_text(rows), 16, TICK_RGB, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
    s.notes_slide.notes_text_frame.text = notes_text(rows, M, ctx)
    lst = prs.slides._sldIdLst
    src = SH.sldid_of(prs, s)
    lst.remove(src)
    SH.sldid_of(prs, anchor).addnext(src)
    return s
