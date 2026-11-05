#!/usr/bin/env python3
"""peer_slide.py — the "How You Compare" slide each Executive Review deck carries (Aaron, 2026-11-03).

One slide per program deck (ARS, ICS, MRPC, CashPlease), drawn by the program's builder and placed by title. It shows the
client against every other client on the program: for each metric a strip plot (one dot per other client, the median, the
middle half of the peers and the client's own mark), the client's rank ("6th of 38 ARS clients") and one plain sentence
against the peer median. The figures are Live Review's: `peer_compare.for_deck` runs the same collectors, metric lists and
arithmetic, so the deck and the page cannot disagree.

NOBODY IS IDENTIFIED. A printed deck is forwarded, so unlike Live Review (where a dot's hover gives that peer's client
number) a deck slide carries no client number, name, logo or CSM of another client: `for_deck` strips them before this module
sees anything, and the speaker notes say so. `tests/test_peer_slide.py` reads the finished file for them.

TOO FEW PEERS. A metric with fewer than five other clients having current data is not drawn; when no metric qualifies the
slide says so in a sentence (the slide is never dropped, and nothing is zeroed). A failure to READ the peers' figures is
stated on the slide too, and `validate_deck.peer_slide_findings` FAILs the deck, so it cannot ship quietly.

Public entry points
-------------------
    METRICS[program]                       the keys each program's slide shows, in order
    title_for(program)                     "How You Compare — ARS Clients"
    render_strips(items, out_png, w_in, h_in)
    add_peer_slide(prs, program, ...) -> slide
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import peer_compare as PC                                    # noqa: E402

WHO = {"ARS": "ARS", "ICS": "ICS", "MRPC": "MRPC", "CP": "CashPlease"}
# The metrics each program's slide shows, in order (a subset of Live Review's: five rows is what the slide seats).
METRICS = {
    "ARS": ["resp_12m", "spend_gain", "moved_up", "spend_per_acct", "rege_pct"],
    "ICS": ["per_1k", "rev_total", "rev_interchange", "rev_nsf_od", "rev_spread"],
    "MRPC": ["enroll_12_per_1k", "still_active", "take_active", "pct_goal"],
    "CP": ["per_1k", "overdue", "charge_off"],
}
# What each metric is, in the words of the deck's notes (the "how it is measured" line).
DEFS = {
    "resp_12m": "responders over personal-account offers sent, the mailings of the 12 months to the data month (the Mailing Response Summary's arithmetic, pooled)",
    "resp_rate": "responders over personal-account offers sent, by mailing month",
    "spend_gain": "responders' monthly debit spend, the 3 months before a mailing against the 6 months after, pooled over mailings (the Responder Activity slides' measure); only clients built on those windows",
    "spend_after": "responders' monthly debit spend in the 6 months after a mailing",
    "moved_up": "of repeat responders to the latest mailing, the share who reached a higher swipe-goal tier than in their previous response",
    "swipes_per_acct": "3-month average monthly debit swipes per ARS-eligible account",
    "spend_per_acct": "3-month average monthly debit spend per ARS-eligible account",
    "rege_pct": "open personal debit-card accounts with a Reg E opt-in",
    "rege_new_pct": "Reg E opt-in among accounts opened in the last 12 months",
    "take_new_pct": "new ARS-eligible accounts holding a debit card",
    "active_cards": "open personal card holders swiping in the month",
    "ret_1yr": "accounts still open one year after opening (survival estimate)",
    "rev_per_1k": "the ARS workbook's incremental revenue, monthly average of the last 12 months, per 1,000 eligible accounts",
    "per_1k": None,           # program-specific, see _def()
    "rev_total": "revenue over account-months across every opening-month cohort, program to date (the ICS Revenue per Account per Month slide's arithmetic)",
    "rev_interchange": "interchange revenue over account-months, program to date",
    "rev_nsf_od": "NSF/OD and other fee revenue over account-months, program to date",
    "rev_spread": "spread-on-deposits revenue over account-months, program to date",
    "pct_goal": "enrollments as a share of the monthly goal",
    "enroll_12_per_1k": "enrollments in the last 12 months per 1,000 open debit-card accounts (MRPCEnrollmentSummary weekly)",
    "enroll_per_1k": "enrollments in the month per 1,000 open debit-card accounts",
    "still_active": "enrolled cardholders still active (MRPCEnrollmentSummary weekly)",
    "take_active": "take rate among active accounts (MRPCEnrollmentSummary weekly)",
    "overdue": "share of loans booked that are overdue (CashPlease Summary)",
    "charge_off": "charge-off rate as reported on the client's CashPlease Summary tab",
}


def title_for(program):
    return f"How You Compare — {WHO[program]} Clients"


def _def(program, key):
    if key == "per_1k":
        return {"ICS": "referrals in the month per 1,000 DDAs (the all-clients referral file and the ILS DDA count)",
                "CP": "loans in the last 12 months per 1,000 DDAs (CashPlease Summary and the ILS DDA count)"}.get(program, "per 1,000 DDAs")
    return DEFS.get(key, key)


# ----------------------------------------------------------------- the strip plots
def _jitter(i, n):
    """A fixed vertical offset in [-0.5, 0.5] for the i-th dot, so neighbouring dots do not sit on one another."""
    return (((i * 0.6180339887) % 1.0) - 0.5)


def render_strips(items, out_png, w_in, h_in, client_label="This client"):
    """One image, one strip per item: peers as dots, the middle half shaded, the median ticked, the client in orange."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    import rpe_env
    from brand import NAVY, ORANGE, TICK, LABEL, STEEL, GRID
    rpe_env.use_font("Carlito")
    n = len(items)
    legend_h = 0.42
    row_h = (h_in - legend_h) / max(n, 1)
    fig = plt.figure(figsize=(w_in, h_in))
    for k, it in enumerate(items):
        c, spec = it["c"], it["spec"]
        f = PC.formatter(spec["fmt"])
        top = 1 - (k * row_h) / h_in
        ax = fig.add_axes([0.03, top - row_h / h_in + 0.02 / h_in * 4, 0.94, (row_h - 0.12) / h_in])
        vals = list(c["dots"]) + [c["client"]]
        lo, hi = min(vals), max(vals)
        span = (hi - lo) or max(abs(hi), 1.0)
        pad = span * 0.07
        ax.set_xlim(lo - pad, hi + pad)
        ax.set_ylim(-1.5, 3.4)
        ax.axis("off")
        ax.plot([lo, hi], [0, 0], color=GRID, lw=2, zorder=1, solid_capstyle="round")
        ax.add_patch(Rectangle((c["q1"], -0.45), max(c["q3"] - c["q1"], span * 0.004), 0.9, facecolor=LABEL, edgecolor="none", zorder=2))
        order = sorted(range(len(c["dots"])), key=lambda i: c["dots"][i])
        ax.scatter([c["dots"][i] for i in order], [_jitter(j, len(order)) * 0.62 for j in range(len(order))],
                   s=70, color=STEEL, alpha=0.9, edgecolors="white", linewidths=0.8, zorder=3)
        ax.plot([c["median"]] * 2, [-0.62, 0.62], color=NAVY, lw=3.2, zorder=4, solid_capstyle="butt")
        ax.scatter([c["client"]], [0], s=330, color=ORANGE, edgecolors="white", linewidths=2.2, zorder=5)
        ax.text(c["client"], 0.5, f(c["client"]), ha="center", va="bottom", fontsize=17, fontweight="bold", color=ORANGE, zorder=6)
        label = spec["label"] + (f" ({it['month']})" if it.get("month") else "")
        ax.text(lo - pad, 3.4, label, ha="left", va="top", fontsize=15, fontweight="bold", color=NAVY)
        ax.text(c["median"], -0.78, f"median {f(c['median'])}", ha="center", va="top", fontsize=12.5, color=TICK)
        for v, ha in ((lo, "left"), (hi, "right")):
            if abs(v - c["median"]) > span * 0.2:
                ax.text(v, -0.78, f(v), ha=ha, va="top", fontsize=12.5, color=TICK)
    # the key, once, under the last strip
    kx = fig.add_axes([0.03, 0.0, 0.94, legend_h / h_in])
    kx.set_xlim(0, 1)
    kx.set_ylim(0, 1)
    kx.axis("off")
    kx.scatter([0.015], [0.5], s=70, color=STEEL, edgecolors="white", linewidths=0.8)
    kx.text(0.035, 0.5, "Another client", va="center", fontsize=13, color=TICK)
    kx.add_patch(Rectangle((0.255, 0.22), 0.045, 0.56, facecolor=LABEL, edgecolor="none"))
    kx.text(0.31, 0.5, "Middle half of the others", va="center", fontsize=13, color=TICK)
    kx.plot([0.605, 0.605], [0.18, 0.82], color=NAVY, lw=3.2, solid_capstyle="butt")
    kx.text(0.62, 0.5, "Median", va="center", fontsize=13, color=TICK)
    kx.scatter([0.74], [0.5], s=150, color=ORANGE, edgecolors="white", linewidths=1.6)
    kx.text(0.76, 0.5, client_label, va="center", fontsize=13, color=TICK)
    fig.savefig(out_png, dpi=200, facecolor="white")
    plt.close(fig)
    return out_png


# ----------------------------------------------------------------- the slide
ROW_MAX = 1.3           # inches a strip row may take
CHART = (0.5, 1.62, 7.75)
TEXT_X, TEXT_W = 8.5, 4.4
BAND_BOTTOM = 6.3


def _frame(prs, template_slide, title, pill, selection):
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from brand import NAVY_RGB, TICK_RGB, HEAD, BODY
    import shapes as SH
    s = SH.blank_slide(prs, template_slide)
    SH.textbox(s, 0.5, 0.28, 9.6, 0.9, title, 26, NAVY_RGB, True, PP_ALIGN.LEFT, HEAD, MSO_ANCHOR.MIDDLE)
    SH.pill(s, pill, L=9.85, W=3.0)
    SH.textbox(s, 0.5, 1.06, 12.2, 0.4, selection, 16, TICK_RGB, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
    return s


def _place(prs, slide, before_title=None, after_title=None):
    import shapes as SH
    lst = prs.slides._sldIdLst
    src = SH.sldid_of(prs, slide)
    target = None
    for s in prs.slides:
        if s is slide:
            continue
        t = SH.slide_title(s)
        if (before_title and t.startswith(before_title)) or (after_title and t.startswith(after_title)):
            target = s
            break
    if target is None:
        raise SystemExit(f"peer slide: no '{before_title or after_title}' slide to place it by")
    lst.remove(src)
    tgt = SH.sldid_of(prs, target)
    (tgt.addprevious if before_title else tgt.addnext)(src)


def _tail(item, who):
    f = PC.formatter(item["spec"]["fmt"])
    c = item["c"]
    return f"{PC.rank_phrase(c, who)}", f"{PC.relation_phrase(c, f)}"


def notes_text(program, ev, ctx):
    who = ev["who"]
    lines = [f"Source: peer comparison for client {ctx['client_id']} {ctx['client_name']} against the other {who} clients. "
             f"{ctx['client_source']} Peers: every other {who} client with current data, n = {ev['n_pool']} on the program"
             + (f" ({ev['pull']})" if ev.get("pull") else "") + "; read by build/peer_compare.py from the same per-client sheets "
             "and data packs Live Review reads, so the two show the same figures. No other client is named or numbered on this slide.",
             f"Selection: each strip is one measure; a dot is one other client, the shaded band is the middle half of them, the line is "
             f"their median, the orange mark is {ctx['client_name']}. The rank counts {ctx['client_name']} among the clients with a figure. "
             f"A measure with fewer than {PC.MIN_PEERS} other clients having current data is not shown. "
             "Wording follows the +/-2% rule: within 2% of the median is almost flat."]
    for it in ev["items"]:
        c = it["c"]
        f = PC.formatter(it["spec"]["fmt"])
        lines.append(f"{it['spec']['label']}{' (' + it['month'] + ')' if it['month'] else ''}: {_def(program, it['spec']['key'])}. "
                     f"{ctx['client_name']} {f(c['client'])}; peers n = {c['n']}, median {f(c['median'])}, middle half {f(c['q1'])} to {f(c['q3'])}, "
                     f"range {f(c['min'])} to {f(c['max'])}.")
        lines.extend(it.get("notes") or [])
    if ev.get("left"):
        lines.append("Left out: " + "; ".join(ev["left"]) + ".")
    lines.extend(ev.get("notes") or [])
    if ctx.get("extra"):
        lines.append(ctx["extra"])
    return "\n".join(lines)


def add_peer_slide(prs, program, client_id, client_name, pill, assets_dir, client_source,
                   before_title=None, after_title=None, period=None, own=None, root=None, keys=None, extra=None, evaluation=None,
                   anchor_slide=None, brand=None):
    """Draw the slide, place it by title and return it.

    `client_source` is the sentence naming the client's own sources for the notes ("ODD extract ..., ARS workbook ...");
    `own` the packs the build already holds (see peer_pool.PeerCtx); `evaluation` a ready `peer_compare.for_deck` result (tests).
    Placement: `before_title` or `after_title`, a title prefix, resolved at run time; with neither the slide stays at the end of
    the deck and `anchor_slide` (any slide of the deck) supplies its layout, for a builder that orders its own slides.
    `brand` is "std" (the logo and a number box, `std_brand`) or a function called last with the slide, for a builder whose logo and
    number are drawn per slide; ARS and CashPlease add theirs in their own passes."""
    from pptx.util import Inches
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from brand import NAVY_RGB, TICK_RGB, ORANGE_RGB, BODY
    import shapes as SH

    who = WHO[program]
    err = None
    ev = evaluation
    if ev is None:
        try:
            ev = _evaluate(program, client_id, period, root, own, keys)
        except Exception as e:                                # the peers' figures could not be read: say so on the slide
            err = f"{type(e).__name__}: {e}"
            print(f"!! peer slide ({program}): the other clients' figures could not be read - {err}", file=sys.stderr)
            ev = {"program": program, "who": who, "n_pool": 0, "pull": None, "items": [], "left": [], "notes": [], "unavailable": None}
    anchor = anchor_slide or next((x for x in prs.slides if SH.slide_title(x).startswith(before_title or after_title or "-")), None)
    if anchor is None:
        raise SystemExit(f"peer slide: no '{before_title or after_title}' slide to place it by")
    n_items = len(ev["items"])
    if err:
        selection = f"The comparison could not be drawn for this build."
    elif n_items:
        selection = (f"{client_name} against the other {who} clients with current data: one dot per client, none named.")
    else:
        selection = f"{client_name} is not compared with other {who} clients on this slide."
    s = _frame(prs, anchor, title_for(program), pill, selection)
    ctx = {"client_id": client_id, "client_name": client_name, "client_source": client_source, "extra": extra}
    if n_items:
        row_h = min(ROW_MAX, (BAND_BOTTOM - CHART[1] - 0.42) / n_items)
        h = row_h * n_items + 0.42
        png = os.path.join(assets_dir, f"peers_{program.lower()}.png")
        render_strips(ev["items"], png, CHART[2], h, "This client")
        s.shapes.add_picture(png, Inches(CHART[0]), Inches(CHART[1]), Inches(CHART[2]), Inches(h))
        for k, it in enumerate(ev["items"]):
            rank, rel = _tail(it, who)
            top = CHART[1] + k * row_h + 0.2
            SH.textbox(s, TEXT_X, top, TEXT_W, 0.4, rank, 18, ORANGE_RGB, True, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
            SH.textbox(s, TEXT_X, top + 0.38, TEXT_W, 0.55, rel[0].upper() + rel[1:] + ".", 16, TICK_RGB, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
        ns = sorted({i["c"]["n"] for i in ev["items"]})
        cap = (f"Peers: {ns[0]} other {who} clients per measure" if len(ns) == 1
               else f"Peers: {ns[0]} to {ns[-1]} other {who} clients per measure")
        SH.textbox(s, 0.5, 6.42, 10.5, 0.4, cap + "; a measure needs five with current data.", 16, TICK_RGB, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
    else:
        if err:
            msg = ("The peer comparison could not be drawn for this build: the other clients' figures could not be read. "
                   "Rebuild this deck when the shares are reachable.")
        else:
            msg = ev.get("unavailable") or f"No measure has {PC.MIN_PEERS} other {who} clients with current data yet."
        SH.textbox(s, 0.7, 2.3, 11.8, 2.0, msg, 22, NAVY_RGB, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
    note = notes_text(program, ev, ctx)
    if err:
        note += f"\nThe other clients' figures could not be read for this build ({err})."
    s.notes_slide.notes_text_frame.text = note
    if before_title or after_title:
        _place(prs, s, before_title, after_title)
    if brand == "std":
        std_brand(s, client_id, assets_dir)
    elif brand:
        brand(s)
    return s


def std_brand(slide, client_id, assets_dir):
    """The bottom-right mark (the client's logo, else the CSI lockup) and a slide-number box (its text is rewritten by the
    builder's renumber pass), for a builder that draws them per slide."""
    from pptx.util import Inches, Pt
    from brand import NAVY_RGB, BODY
    import shapes as SH
    lockup = os.path.join(HERE, "assets", "logo.png")
    SH.data_logo(slide, client_id=client_id, assets_dir=assets_dir, lockup=lockup if os.path.exists(lockup) else None)
    tb = slide.shapes.add_textbox(Inches(0.45), Inches(7.05), Inches(0.70), Inches(0.30))
    r = tb.text_frame.paragraphs[0].add_run()
    r.text = "0"
    r.font.name = BODY
    r.font.size = Pt(10)
    r.font.bold = True
    r.font.color.rgb = NAVY_RGB


def _evaluate(program, client_id, period, root, own, keys):
    from review_page import peer_pool as PP
    collect, metrics, label = PP.PROGRAMS[program]
    ctx = PP.PeerCtx(client=str(client_id), period=period, root=root, own=own)
    coll = collect(ctx)
    by = {m["key"]: m for m in metrics}
    chosen = [by[k] for k in (keys or METRICS[program]) if k in by]
    ev = PC.evaluate(coll, chosen, WHO[program])
    ev["items"] = [PC.anonymous(i) for i in ev["items"]]
    ev.update(program=program, who=WHO[program], pull=coll.get("pull"))
    return ev
