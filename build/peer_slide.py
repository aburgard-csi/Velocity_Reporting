#!/usr/bin/env python3
"""peer_slide.py — the "How You Compare" slide each Executive Review deck carries (Aaron, 2026-11-03).

Each program deck (ARS, ICS, MRPC, CashPlease) carries these slides, drawn by the program's builder and placed by title,
NEVER more than two comparisons a slide (Aaron, 2026-11-22: "Don't put more than 2 peer comparison charts on a slide"): the
measures come in pairs (GROUPS), one slide per pair. It shows the client against every other client on the program: for
each metric a strip plot (one dot per other client, the median, the
middle half of the peers and the client's own mark), the client's rank ("6th of 38 ARS clients") and one plain sentence
against the peer median. The figures are Live Review's: `peer_compare.for_deck` runs the same collectors, metric lists and
arithmetic, so the deck and the page cannot disagree.

NOBODY IS IDENTIFIED. A printed deck is forwarded, so unlike Live Review (where a dot's hover gives that peer's client
number) a deck slide carries no client number, name, logo or CSM of another client: `for_deck` strips them before this module
sees anything, and the speaker notes say so. `tests/test_peer_slide.py` reads the finished file for them.

TOO FEW PEERS. A metric with fewer than five other clients having current data is not drawn, and a slide none of whose
measures can be drawn is not added at all (Aaron, 2026-11-22: "skip a slide if it doesn't have data"); each skipped slide
is printed to the build log and named in the notes of the comparison slides that are drawn. Nothing is zeroed. A failure to
READ the peers' figures is different: that one slide is drawn and says so, and `validate_deck.peer_slide_findings` FAILs the
deck, so it cannot ship quietly.

ARS IS COMPARED ON WHAT THE CLIENT CONTROLS (Aaron, 2026-11-22: "For ARS peer comparisons, don't compare program results.
Compare things the customer controls, like Reg E, account growth, debit card take rate."): Reg E opt-in, debit card take
rate, account growth and retention. Response rates, responder spend, tier movement and ARS revenue are never ranked.

Public entry points
-------------------
    GROUPS[program]                        [(title label, [keys])], at most MAX_PER_SLIDE keys each, one slide per group
    METRICS[program]                       every key the program's slides show, in order
    title_for(program, label=None)         "How You Compare — Reg E Opt-In" ("How You Compare — ARS Clients" with no label)
    render_strips(items, out_png, w_in, h_in)
    add_peer_slide(prs, program, ...) -> [slides]   (empty when no group has data)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import peer_compare as PC                                    # noqa: E402

WHO = {"ARS": "ARS", "ICS": "ICS", "MRPC": "MRPC", "CP": "CashPlease"}
MAX_PER_SLIDE = 2
# The slides each program's deck carries, in order: (title label, the measures on it). Never more than MAX_PER_SLIDE measures
# a slide; tests/test_peer_slide.py checks every group and that every title fits its box on one line.
GROUPS = {
    "ARS": [("Reg E Opt-In", ["rege_pct", "rege_new_pct"]),
            ("Debit Card Take Rate", ["take_all", "take_new_pct"]),
            ("Accounts Gained & Kept", ["acct_growth", "ret_1yr"])],
    "ICS": [("ICS Referrals and Revenue", ["per_1k", "rev_total"]),
            ("ICS Revenue by Source", ["rev_interchange", "rev_nsf_od"]),
            ("ICS Spread on Deposits", ["rev_spread"])],
    "MRPC": [("MRPC Enrollments", ["enroll_12_per_1k", "pct_goal"]),
             ("MRPC Cardholder Activity", ["still_active", "take_active"])],
    "CP": [("CashPlease Loan Volume", ["per_1k"]),
           ("CashPlease Repayment", ["overdue", "charge_off"])],
}
# Every measure each program's slides show, in order (a subset of Live Review's).
METRICS = {p: [k for _label, keys in g for k in keys] for p, g in GROUPS.items()}
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
    "take_all": "ARS-eligible personal accounts holding a debit card, the whole book",
    "acct_growth": "personal accounts opened minus closed over the last 12 complete months, as a share of the personal accounts open at the start of them",
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


def title_for(program, label=None):
    """The slide title: "How You Compare — <the group's label>", or "How You Compare — <program> Clients" for the one slide
    that says the comparison could not be drawn."""
    return f"How You Compare — {label}" if label else f"How You Compare — {WHO[program]} Clients"


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
             "Wording follows the +/-2% rule: within 2% of the median is almost flat. A rate's gap from the median is stated "
             "in percentage points, any other measure's in percent of the median."]
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
                   anchor_slide=None, brand=None, log=None):
    """Draw the program's comparison slides, place them by title and return them as a list, in deck order.

    One slide per GROUPS entry, two measures at most; a group none of whose measures can be drawn adds no slide (printed to
    the build log, and named in the notes of the slides that are drawn). The list is empty when no group has data.
    `keys` limits the measures (tests). A failure to READ the peers' figures adds ONE slide that says so (and fails the gate).

    `client_source` is the sentence naming the client's own sources for the notes ("ODD extract ..., ARS workbook ...");
    `own` the packs the build already holds (see peer_pool.PeerCtx); `evaluation` a ready `peer_compare.for_deck` result (tests).
    Placement: `before_title` or `after_title`, a title prefix, resolved at run time; with neither the slides stay at the end of
    the deck and `anchor_slide` (any slide of the deck) supplies their layout, for a builder that orders its own slides.
    `brand` is "std" (the logo and a number box, `std_brand`) or a function called last with each slide, for a builder whose logo
    and number are drawn per slide; ARS and CashPlease add theirs in their own passes."""
    log = log or (lambda m: print(m, flush=True))
    who = WHO[program]
    err = None
    ev = evaluation
    if ev is None:
        try:
            ev = _evaluate(program, client_id, period, root, own, keys)
        except Exception as e:                                # the peers' figures could not be read: say so on a slide
            err = f"{type(e).__name__}: {e}"
            print(f"!! peer slide ({program}): the other clients' figures could not be read - {err}", file=sys.stderr)
            ev = {"program": program, "who": who, "n_pool": 0, "pull": None, "items": [], "left": [], "notes": [], "unavailable": None}
    anchor = anchor_slide or next((x for x in prs.slides if SH_title(x).startswith(before_title or after_title or "-")), None)
    if anchor is None:
        raise SystemExit(f"peer slide: no '{before_title or after_title}' slide to place it by")
    ctx = {"client_id": client_id, "client_name": client_name, "client_source": client_source, "extra": extra}
    if err:
        s = _frame(prs, anchor, title_for(program), pill, "The comparison could not be drawn for this build.")
        msg = ("The peer comparison could not be drawn for this build: the other clients' figures could not be read. "
               "Rebuild this deck when the shares are reachable.")
        _say(s, msg)
        s.notes_slide.notes_text_frame.text = notes_text(program, ev, ctx) + f"\nThe other clients' figures could not be read for this build ({err})."
        made = [s]
    else:
        wanted = keys or METRICS[program]
        by_key = {it["spec"]["key"]: it for it in ev["items"]}
        groups = [(label, [k for k in ks if k in wanted]) for label, ks in GROUPS[program]]
        groups = [(label, ks) for label, ks in groups if ks]
        drawn, skipped = [], []
        for label, ks in groups:
            items = [by_key[k] for k in ks if k in by_key]
            if items:
                drawn.append((label, ks, items))
            else:
                skipped.append(label)
        if ev.get("unavailable"):
            log(f"peer slides ({program}): none added - {ev['unavailable']}")
        for label in skipped:
            log(f"peer slide skipped ({program}): '{title_for(program, label)}' has no measure with {PC.MIN_PEERS} other clients' current data")
        made = []
        for label, ks, items in drawn:
            s = _frame(prs, anchor, title_for(program, label), pill,
                       f"{client_name} against the other {who} clients with current data: one dot per client, none named.")
            _draw(s, items, who, os.path.join(assets_dir, f"peers_{program.lower()}_{_slug(label)}.png"))
            labels = [_spec_label(program, k) for k in ks]
            left_here = [x for x in ev.get("left") or [] if any(x.startswith(lbl + ":") for lbl in labels)]
            ev_g = dict(ev, items=items, left=left_here)
            note = notes_text(program, ev_g, ctx)
            if skipped:
                note += ("\nNot added (no measure with " + str(PC.MIN_PEERS) + " other clients' current data): "
                         + "; ".join(title_for(program, l) for l in skipped) + ".")
            s.notes_slide.notes_text_frame.text = note
            made.append(s)
    if before_title or after_title:
        prev = None
        for s in made:
            if prev is None:
                _place(prs, s, before_title, after_title)
            else:
                _after(prs, s, prev)
            prev = s
    for s in made:
        if brand == "std":
            std_brand(s, client_id, assets_dir)
        elif brand:
            brand(s)
    return made


def SH_title(slide):
    import shapes as SH
    return SH.slide_title(slide)


def _spec_label(program, key):
    from review_page import peer_pool as PP
    return next((m["label"] for m in PP.PROGRAMS[program][1] if m["key"] == key), key)


def _slug(label):
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in label).strip("_")


def _after(prs, slide, prev):
    import shapes as SH
    lst = prs.slides._sldIdLst
    src = SH.sldid_of(prs, slide)
    lst.remove(src)
    SH.sldid_of(prs, prev).addnext(src)


def _say(s, msg):
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from brand import NAVY_RGB, BODY
    import shapes as SH
    SH.textbox(s, 0.7, 2.3, 11.8, 2.0, msg, 22, NAVY_RGB, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)


def _draw(s, items, who, png):
    """Two strips at most, with the rank and the plain sentence beside each, and the peer count under them."""
    from pptx.util import Inches
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from brand import TICK_RGB, ORANGE_RGB, BODY
    import shapes as SH
    assert len(items) <= MAX_PER_SLIDE, "never more than two comparisons a slide"
    n_items = len(items)
    row_h = min(ROW_MAX, (BAND_BOTTOM - CHART[1] - 0.42) / n_items)
    h = row_h * n_items + 0.42
    render_strips(items, png, CHART[2], h, "This client")
    s.shapes.add_picture(png, Inches(CHART[0]), Inches(CHART[1]), Inches(CHART[2]), Inches(h))
    for k, it in enumerate(items):
        rank, rel = _tail(it, who)
        top = CHART[1] + k * row_h + 0.2
        SH.textbox(s, TEXT_X, top, TEXT_W, 0.4, rank, 18, ORANGE_RGB, True, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
        SH.textbox(s, TEXT_X, top + 0.38, TEXT_W, 0.55, rel[0].upper() + rel[1:] + ".", 16, TICK_RGB, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
    ns = sorted({i["c"]["n"] for i in items})
    cap = (f"Peers: {ns[0]} other {who} clients per measure" if len(ns) == 1
           else f"Peers: {ns[0]} to {ns[-1]} other {who} clients per measure")
    SH.textbox(s, 0.5, 6.42, 10.5, 0.4, cap + "; a measure needs five with current data.", 16, TICK_RGB, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)


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
