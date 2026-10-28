#!/usr/bin/env python3
"""
build_cp_gen.py — build one client's CashPlease deck from its data pack.

TEN slides: cover, Executive Summit, agenda, then the five CashPlease slides
(divider, Program Overview, Loan Volume by Month, Loan Portfolio by Status, Peer
Comparison), then Questions & Discussion and Contact Us. That is the shape of an
ARS / ICS / MRPC single-product deck, because a single-product client gets a
single-product deck (Aaron, 2026-09-01).

A multi-product client's CashPlease slides go into their combined deck instead, and
this same output is what feeds it: `assemble_combined.section_slides()` keeps a
program's section by dropping the cover, Summit, agenda, Q&A and Contact, leaving the
divider and four content slides. The cover carries the "Executive Review" line and the
divider carries the benefits line, which is exactly what lets those two be told apart.

Style comes from the Retail Performance Engine's shared layer — `brand`, `shapes`,
`periods`, `fit_layout` — so a CashPlease slide matches the slides around it. The
package starts from the RPE `templates/cashplease_template.pptx` shell (2026-09-02; it
was `ars_template.pptx` before that): the theme, the slide masters, the embedded
Montserrat/Calibri faces and the five shell slides, found by MEANING (cover, Summit,
agenda, Questions, Contact). Every other shell slide is dropped from `sldIdLst` and
then physically removed with the repo's `strip_dead.py`, because leaving orphaned
slide parts in the package is the defect that made the 2026.08 ICS decks unopenable
while linting clean (CLAUDE.md, validation gate rule 3). Any shell carrying those
five slides works, which is how the shell re-materializes itself from a synthetic
Union Financial pack (RPE `templates/TEMPLATES.md`).

A client with a production settings record (`Inputs/Product Settings/<id>_cp_settings.json`,
passed as the optional fourth argument) also gets a CashPlease Program Settings slide
after the Program Overview — eleven slides, six in the section (Aaron, 2026-09-14).

Usage:
    python build_cp_gen.py <pack.json> <cashplease_template.pptx> <out.pptx> [<settings.json>]
"""
import copy
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
for p in (BUILD, BUILD / "ars_pipeline", HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.text.text import _Paragraph

from brand import (NAVY_RGB, ORANGE_RGB, WHITE_RGB, TICK_RGB, LABEL_RGB,
                   HEAD, BODY)
from shapes import textbox, pill, tile, add_table, fit_picture, shadow, sldid_of
import cp_charts

SLIDE_W, SLIDE_H = 13.333, 7.5
# Three terms, matching the other dividers' shape (STYLE.md "Product section
# dividers"): ARS "Mailings · Debit Card · Reg E", ICS "Referrals · Account
# Performance · Revenue", MRPC "Enrollments · Retention · Revenue". "Portfolio
# Status" rather than "Portfolio Health" — it names the slide it points at, and
# "healthy" is on the banned-word list for exactly the register it belongs to.
BENEFITS = "Loan Volume · Portfolio Status · Peer Comparison"

# The cohort is described by its TAB count, which is what the rollup actually sums.
# It is not the number of clients this pipeline builds decks for — the rollup also
# carries an internal test tab and any cancelled client's data.
#
# Keep this SHORT. `fit_layout` parks a bottom caption in a fixed band sized by its
# line count — top = 7.00 - 0.08 - 0.26*lines — so every extra wrapped line pushes
# the caption 0.26" further UP into the slide's content. A four-line footnote is what
# put this text on top of the Peer Comparison pills. At 11 pt across 12.1" a line
# holds roughly 155 characters; two lines is the budget.
COHORT_NOTE = ("Cohort: the workbook's all-clients rollup — {total_loans:,} "
               "CashPlease loans across all {cohort_tabs} tabs, {client} included.")

# Loans per 1,000 DDAs runs on a NARROWER cohort than every other peer figure, and
# saying so is not optional. The rollup covers all 73 tabs; the DDA rate can only
# cover clients that have both a DDA count and a full 12-month window — 51 of them.
# One footnote describing the rollup while a row on the same slide is measured
# against a different population would be wrong on the face of the slide.
DDA_COHORT_NOTE = (" The DDA rate uses a narrower cohort: the {cohort_dda_clients} "
                   "clients with a DDA count and a full 12 months.")


# ------------------------------------------------------------------ formatting
def money(v, cents=False):
    return f"${v:,.2f}" if cents else f"${v:,.0f}"


def money_short(v):
    if abs(v) >= 1_000_000:
        return f"${v/1_000_000:.1f}M"
    if abs(v) >= 1_000:
        return f"${v/1_000:.0f}K"
    return f"${v:,.0f}"


def pct(v, dp=1):
    return f"{v*100:.{dp}f}%"


def _short_date(iso):
    """'2026-08-30' -> 'Aug 30'. The date a partial month runs THROUGH."""
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%b %-d")
    except (ValueError, TypeError):
        try:
            return datetime.strptime(iso, "%Y-%m-%d").strftime("%b %d").replace(" 0", " ")
        except (ValueError, TypeError):
            return iso


def month_label(iso):
    """'2026-07-31' -> 'July 2026'. Returns the token unchanged if unparseable."""
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%B %Y")
    except (ValueError, TypeError):
        return iso


def _gen_date(report_generated):
    try:
        return datetime.strptime(report_generated.split()[0], "%m/%d/%Y")
    except (ValueError, IndexError):
        return None


def cover_label(report_generated):
    """'8/30/2026 7:27:43 AM' -> 'August 2026' — month and year, like every other deck.

    The COVER and the Questions slide carry a month (Aaron, 2026-09-01), so a CashPlease
    deck reads the same as an ARS/ICS/MRPC one on the slides an audience sees first. The
    exact pull date still appears on every content slide's PTD pill and in the notes, so
    nothing is lost — only the cover stops being the one deck with a different format.
    """
    d = _gen_date(report_generated)
    return d.strftime("%B %Y") if d else report_generated


def pull_label(report_generated):
    """'8/30/2026 7:27:43 AM' -> 'August 30, 2026'.

    The PILL keeps the day: the workbook is a weekly snapshot current through its
    generation timestamp, which is the VIP-current form in templates/STYLE.md ("Date /
    period pills"). Only the cover and Questions slides use the month.
    """
    try:
        return datetime.strptime(report_generated.split()[0], "%m/%d/%Y") \
                       .strftime("%B %-d, %Y")
    except (ValueError, IndexError):
        try:
            return datetime.strptime(report_generated.split()[0], "%m/%d/%Y") \
                           .strftime("%B %d, %Y").replace(" 0", " ")
        except (ValueError, IndexError):
            return report_generated


def movement(now, prev, noun):
    """Derive the verb from the figures — never write it as a constant.

    templates/STYLE.md "+/-2% band": within +/-2% is almost flat; otherwise state the
    direction WITH the figures behind it. A hardcoded verb is how six 2026.08 decks
    shipped 'ticket holds through response' over declines of 5.2% to 8.6%.
    """
    if not prev:
        return f"{noun} totalled {now:,} in the most recent complete month."
    change = (now - prev) / prev
    if abs(change) <= 0.02:
        return (f"{noun} were almost flat month over month — {prev:,} to {now:,} "
                f"({change:+.1%}).")
    direction = "rose" if change > 0 else "fell"
    return (f"{noun} {direction} from {prev:,} to {now:,} month over month "
            f"({change:+.1%}).")


def against_peer(label, client, peer, kind="rate"):
    """One comparison sentence carrying both figures, so the claim is checkable.

    The gap between two RATES is measured in percentage POINTS, not percent: 2.58%
    against 4.67% is 2.09 points apart, and calling that "2.1% below" states a
    different — and wrong — quantity.
    """
    fmt = {"rate": lambda v: pct(v, 2),
           "index": lambda v: f"{v:.1f}"}.get(kind, money)
    if peer == 0:
        return f"{label}: {fmt(client)}."
    diff = client - peer
    if abs(diff) <= abs(peer) * 0.02:
        return (f"{label} is in line with the CashPlease client average — "
                f"{fmt(client)} against {fmt(peer)}.")
    word = "above" if diff > 0 else "below"
    gap = {"rate": f"{abs(diff)*100:.2f} points",
           "index": f"{abs(diff):.1f}"}.get(kind, money(abs(diff)))
    return (f"{label} is {gap} {word} the CashPlease client average — "
            f"{fmt(client)} against {fmt(peer)}.")


def dda_note(d, m):
    """The audit trail for the loans-per-DDA rate, for the speaker notes.

    Says where the denominator came from, how old it is, and what the workbook's own
    L8 is and why it is not on the slide.
    """
    l8 = d.get("pct_active_accounts_with_loans")
    unused = (f"The workbook also reports 'Percentage of Active Accounts with Loans' "
              f"(L8) as {pct(l8, 2) if l8 is not None else 'n/a'}. It is NOT used: an "
              f"account can take more than one CashPlease loan, so a loan count over "
              f"an account base does not give the share of accounts that borrowed, and "
              f"the workbook does not state its denominator (Aaron, 2026-09-01).")
    if m["loans_per_1k_dda"] is None:
        return (f"No loans-per-DDA rate is shown — {m['dda_missing_reason']}. " + unused)
    age = ""
    if m["dda_last_updated"]:
        age = f", last imported {m['dda_last_updated']}"
        if m["dda_stale_days"] is not None and m["dda_stale_days"] > 45:
            age += (f" — {m['dda_stale_days']} days before this workbook, so the "
                    f"denominator trails the numerator")
    return (f"Loans per 1,000 DDAs = loans booked over the last {m['window_months']} "
            f"completed months ({m['window_loans']:,}) divided by "
            f"{m['dda_accounts']:,} DDA accounts, x 1,000. The DDA count is from the "
            f"'ILS Management Server DDA Count' report sent {d.get('dda_sent')}"
            f"{age}. " + unused)


def rate_sentence(m, peer, client):
    """The loans-per-DDA line, saying exactly what it can and no more.

    Named, not "this client" (Aaron, 2026-09-02). The deck is FOR that client and is
    read in a room with them in it; a sentence whose subject is "this client" reads as
    a template that was never filled in.
    """
    if m["loans_per_1k_dda"] is None:
        return ("Loans per 1,000 DDAs is not shown: "
                + (m["dda_missing_reason"] or "no DDA count is available") + ".")
    own = (f"{client} booked {m['window_loans']:,} loans over "
           f"{m['window_months']} month{'s' if m['window_months'] != 1 else ''} "
           f"against {m['dda_accounts']:,} DDA accounts — "
           f"{m['loans_per_1k_dda']:.1f} per 1,000.")
    if not m["peer_comparable"]:
        return (own + " It is not compared with the cohort, whose rate covers a full "
                      "12 months.")
    return own + " " + against_peer("That rate", m["loans_per_1k_dda"],
                                    peer["loans_per_1k_dda"], "index")


# ------------------------------------------------------------------ slide frame
def _layout(prs, name="BLANK"):
    for master in prs.slide_masters:
        for lay in master.slide_layouts:
            if lay.name == name:
                return lay
    for master in prs.slide_masters:
        for lay in master.slide_layouts:
            if lay.name == "BLANK":
                return lay
    raise SystemExit("no BLANK layout in the template shell")


def new_slide(prs):
    s = prs.slides.add_slide(_layout(prs))
    for sh in list(s.shapes):
        sh._element.getparent().remove(sh._element)
    return s


def notes(slide, text):
    """Every slide names its data source — CLAUDE.md, hard requirement."""
    slide.notes_slide.notes_text_frame.text = text


def head(slide, title, selection, pill_text):
    """Title, then the selection subheading UNDER it — not touching it.

    The title box ran 0.40..1.06 with the subheading opening at 1.04, so the two
    frames overlapped by 0.02". Invisible at 0.02", but it is the same defect that
    becomes visible the moment a title wraps, so the gap is explicit here.
    """
    textbox(slide, 0.6, 0.38, 9.3, 0.62, title, 30, NAVY_RGB, True,
            PP_ALIGN.LEFT, HEAD, MSO_ANCHOR.MIDDLE)
    textbox(slide, 0.62, 1.06, 9.6, 0.46, selection, 16, TICK_RGB, False,
            PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
    # Wider than the shapes.pill default (2.35"): "PTD · September 13, 2026" is 2.16" of
    # Montserrat 12pt and wrapped onto two lines in 2.15" usable (2026.09 modules,
    # Aaron 2026-09-17). Grows leftward into the gap after the 9.9"-wide title.
    pill(slide, pill_text, L=10.15, W=2.70)


CLIENT = [None, None]       # (client id, assets dir) for the data-slide logo


def logo(slide, L, T, W, H):
    # The client's logo bottom-right, the lockup where there is none (Aaron, 2026-10-02).
    from shapes import data_logo as _data_logo
    path = BUILD / "assets" / "logo.png"
    if _data_logo(slide, client_id=CLIENT[0], assets_dir=CLIENT[1],
                  lockup=str(path) if path.exists() else None, box=(L, T, W, H)):
        return
    if path.exists():
        fit_picture(slide, str(path), L, T, W, H)


def capsule(slide, L, T, W, H, text, fill, size=14):
    sp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                Inches(L), Inches(T), Inches(W), Inches(H))
    sp.fill.solid(); sp.fill.fore_color.rgb = fill; sp.line.fill.background()
    sp.shadow.inherit = False
    tf = sp.text_frame; tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = text
    r.font.size = Pt(size); r.font.bold = True; r.font.name = HEAD
    r.font.color.rgb = WHITE_RGB
    shadow(sp)
    return sp


def callout(slide, L, T, W, H, value, label, fill=NAVY_RGB):
    sp = tile(slide, L, T, W, H, value, label, fill=fill)
    shadow(sp)
    return sp


# ------------------------------------------------------------------ the shell
AGENDA_DETAIL_CP = "Loan volume, portfolio status & peer comparison"


def _settext(shape, text):
    """Replace a shape's text, keeping the first run's formatting."""
    tf = shape.text_frame
    p = tf.paragraphs[0]
    if not p.runs:
        p.add_run()
    p.runs[0].text = text
    for r in p.runs[1:]:
        r.text = ""
    for extra in tf.paragraphs[1:]:
        extra._p.getparent().remove(extra._p)


def _set_lines(shape, lines):
    """Replace a text frame's paragraphs, keeping the first one's formatting.

    `_settext` collapses a frame to a single paragraph. The cover's client/period box is
    two lines in every template, so it needs its paragraphs kept rather than merged.
    """
    tf = shape.text_frame
    p0 = tf.paragraphs[0]
    for extra in tf.paragraphs[1:]:
        extra._p.getparent().remove(extra._p)
    if not p0.runs:
        p0.add_run()
    p0.runs[0].text = lines[0]
    for r in p0.runs[1:]:
        r.text = ""
    for line in lines[1:]:
        np = copy.deepcopy(p0._p)
        p0._p.getparent().append(np)
        par = _Paragraph(np, tf)
        par.runs[0].text = line
        for r in par.runs[1:]:
            r.text = ""


def _title_of(slide):
    return next((sh.text_frame.text.strip().split("\n")[0] for sh in slide.shapes
                 if sh.has_text_frame and sh.text_frame.text.strip()), "")


def adapt_shell(prs, d):
    """Find the ARS shell slides by MEANING and rewrite them for CashPlease.

    Resolved by meaning, never by index (CLAUDE.md) — `_is_cover` and `_is_summit` are
    imported from `assemble_combined` rather than reimplemented, so the cover/divider
    distinction stays in one place. The cover is the slide carrying the "Executive
    Review" line; the divider carries the benefits line instead, which is exactly why
    the CashPlease divider survives `section_slides()` when this deck becomes a section.
    """
    import assemble_combined as ac

    found = {}
    for n, s in enumerate(prs.slides, 1):
        title = _title_of(s)
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
        raise SystemExit(f"{sorted(missing)} not found in the template shell — it "
                         f"changed. Resolve by meaning, do not fall back to indexes.")

    label = cover_label(d["report_generated"])

    # Cover: the product line, then the client and period line.
    #
    # The separator is U+2022 BULLET, which is what every template uses. A CashPlease
    # deck briefly used U+00B7 MIDDLE DOT, and `assemble_combined._period()` finds a
    # section's reporting period by splitting the cover on the bullet — so the CP
    # section of a combined deck reported its period as "?".
    #
    # The client name keeps its own line, as in the shell: the box is two paragraphs and
    # collapsing it to one changes the cover's shape.
    # Drawn by the shared cover module (build/cover_divider.py, 2026-10-02): the client's
    # logo, the month, the client, the one product chip. The month label is the workbook's
    # own, as before, and still sits in the "Executive Review  •  <label>" line the
    # combiner and validator read.
    import cover_divider as CD
    CD.draw_cover(found["cover"], [CD.PRODUCT_CP], d["client_name"], label,
                  client_logo=CD.client_logo_for(d["client_id"], str(_art_dir_for(d))))

    # Agenda: one product row plus Questions. `set_agenda` REMOVES the unused rows and
    # their orphan badge circles — blanking them reads as a section that failed to
    # render, and a leftover circle reads as an empty bullet (Wellworth 1549).
    ac.PRODUCT_NAME.setdefault("CP", "CashPlease®")
    ac.AGENDA_DETAIL.setdefault("CP", AGENDA_DETAIL_CP)
    ac.set_agenda(found["agenda"], ["CP"])

    # Questions & Discussion carries the client and period too.
    for sh in found["questions"].shapes:
        if sh.has_text_frame and "Union Financial" in sh.text_frame.text:
            _settext(sh, f"{d['client_name']}  •  {label}")
    CD.redraw_closing_in_place(found["questions"])     # the brand template's closing style, keeping that line

    fill_contact(found["contact"], d["client_id"])

    notes(found["cover"],
          f"Source: {d['source_file']}, tab '{d['sheet_name']}' (report generated "
          f"{d['report_generated']}). Cover for client {d['client_id']} "
          f"{d['client_name']}. No figures. The period label is the workbook's own "
          f"generation date ({label}) rather than a month: CashPlease is a weekly "
          f"snapshot and always uses the most recent workbook (Aaron, 2026-09-01), so "
          f"a month label would misstate what the figures cover.")
    return found


def fill_contact(slide, client_id):
    """Rewrite the shell's Contact Us card with the client's managing CSM (Aaron, 2026-09-16).

    The template card carries static text for one CSM; `shapes.fill_contact_card` finds its
    four lines by position inside the card, replaces them, drops the phone line when the CSM
    has none, and writes the source note.
    """
    import rpe_env
    from shapes import fill_contact_card
    contact = rpe_env.csm_contact(client_id)
    fill_contact_card(slide, contact)
    return contact


# ------------------------------------------------------------------ the slides
def _art_dir_for(d):
    """Where a build's working files go — the trimmed client logo lands beside the charts.
    `main` records its art_dir on the pack under `_art_dir`; a caller without one gets the
    temp folder, and a missing folder only costs the cover its client logo."""
    p = d.get("_art_dir") or os.environ.get("CP_ARTIFACTS")
    return Path(p) if p else None


def slide_divider(prs, d):
    """The CashPlease section divider in the shared left-aligned layout
    (build/cover_divider.py, 2026-10-02), carrying three program-to-date figures."""
    import cover_divider as CD
    m = d["metrics"]
    stats = [(f"{m['total_loans']:,}", "loans booked, program to date"),
             (money_short(m["total_principal"]), "principal advanced")]
    if m.get("loans_per_1k_dda") is not None:
        stats.append((f"{m['loans_per_1k_dda']:.1f}", "loans per 1,000 DDAs, last 12 months"))
    else:
        stats.append((money_short(m["total_interest"]), "interest earned"))
    s = new_slide(prs)
    CD.draw_divider(s, CD.PRODUCT_CP, BENEFITS, stats=stats,
                    note=f"Section divider. Figures from the workbook rollup for client "
                         f"{d['client_id']} {d['client_name']}: loans booked, principal advanced, "
                         f"and loans per 1,000 DDAs (or interest earned when no DDA count is on hand).")
    return s


def slide_overview(prs, d, pill_text, art_dir):
    m, peer = d["metrics"], d["metrics"]["peer"]
    s = new_slide(prs)
    head(s, "CashPlease Program Overview",
         f"All CashPlease loans booked by {d['client_name']}, program to date.",
         pill_text)

    # The fifth tile used to read "Active accounts with a loan" off the workbook's L8.
    # That claim cannot be made: an account can take more than one CashPlease loan, so
    # loans over an account base is not the share of accounts that borrowed (Aaron,
    # 2026-09-01). It is now a rate this pipeline defines and can defend.
    if m["loans_per_1k_dda"] is None:
        # "Not available" is 2.58in of Montserrat 28pt in a 2.00in tile — it wraps and
        # collides, which the RPE gate catches. The tile carries a short marker and the
        # reason goes in the body text and the notes, where there is room to say it.
        rate_tile = ("n/a", "Loans per 1,000 DDAs — no DDA count")
    else:
        rate_tile = (f"{m['loans_per_1k_dda']:.1f}",
                     f"Loans per 1,000 DDAs, last "
                     f"{m['window_months']} month{'s' if m['window_months'] != 1 else ''}")
    tiles = [
        (f"{m['total_loans']:,}", "Loans booked"),
        (money_short(m["total_principal"]), "Principal advanced"),
        (money_short(m["total_interest"]), "Interest earned"),
        (f"{m['active_loans']:,}", "Loans currently funded"),
        rate_tile,
    ]
    L, W, GAP, T, H = 0.62, 2.30, 0.15, 1.78, 1.32
    OV_DROP = 0.25
    for i, (val, lab) in enumerate(tiles):
        callout(s, L + i * (W + GAP), T, W, H, val, lab)

    months = list(reversed(d["monthly"]))
    if months:
        png = str(Path(art_dir) / f"{d['client_id']}_cp_cumulative.png")
        # The chart is drawn at its box's size, so its fonts are on-slide points
        # (Aaron, 2026-10-02) — one tuple feeds both the renderer and the placement.
        box = (7.40, 2.80)
        cp_charts.cumulative_growth_chart(
            png, [r["period_month"] for r in months], [r["loans"] for r in months],
            box=box)
        # Everything below the callouts sits 1/4" lower than it did, for white space under
        # the navy tiles (Aaron, 2026-09-17): OV_DROP.
        fit_picture(s, png, 0.62, 3.42 + OV_DROP, *box)
        textbox(s, 0.62, 3.14 + OV_DROP, 7.40, 0.30, "Cumulative loans booked, by month",
                13, TICK_RGB, True, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
    else:
        textbox(s, 0.62, 3.42 + OV_DROP, 7.40, 2.80,
                "No completed month in the workbook yet, so there is no growth "
                "curve to draw. It appears here once the first month closes.",
                16, NAVY_RGB, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)

    lines = [
        f"Average loan size is {money(m['avg_loan_size'])}, with "
        f"{money(m['avg_interest_per_loan'])} of interest per loan.",
        "",
        rate_sentence(m, peer, d["client_name"]),
        "",
        against_peer("The charge-off rate", m["charge_off_pct"],
                     peer["charge_off_pct"], "rate"),
    ]
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                             Inches(8.25), Inches(3.14 + OV_DROP), Inches(4.47), Inches(3.08))
    box.fill.solid(); box.fill.fore_color.rgb = WHITE_RGB
    box.line.color.rgb = LABEL_RGB; box.line.width = Pt(1)
    box.shadow.inherit = False; shadow(box)
    textbox(s, 8.45, 3.30 + OV_DROP, 4.07, 2.76, lines, 13, NAVY_RGB, False,
            PP_ALIGN.LEFT, BODY, MSO_ANCHOR.MIDDLE)

    cohort_note = COHORT_NOTE.format(client=d["client_name"], **peer)
    if m["loans_per_1k_dda"] is not None:
        cohort_note += DDA_COHORT_NOTE.format(client=d["client_name"], **peer)
    textbox(s, 0.62, 6.36 + OV_DROP, 12.1, 0.40, cohort_note,
            11, TICK_RGB, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)

    notes(s, f"Source: {d['source_file']}, tab '{d['sheet_name']}' "
             f"(report generated {d['report_generated']}). Selection: every "
             f"CashPlease loan booked for client {d['client_id']} program to date. "
             f"Charge-off % is taken as reported on the tab (L9); it is not "
             f"derivable from the tab's own totals. Peer values from the 'All Clients Summary - Loans' tab. "
             + dda_note(d, m) + " "
             f"The curve is the running total of the completed-month roll-up rows, "
             f"all {len(d['monthly'])} of them; axis labels are sampled so a long "
             f"axis stays readable, but every month is plotted.")
    return s


# ------------------------------------------------------------------ program settings
# The CashPlease page of the Velocity Product Settings Power BI app, one client's record
# (Aaron, 2026-09-14). The record also carries fields that must never reach a client:
# the free-text Loan Notes (internal — WesBanco's reads "Declined Best Practices"), the
# contract type, core, CSM, pricing and the regulator address. Speaker notes ship inside
# the .pptx, so "internal" means off the slide AND out of the notes. Only the fields
# named in SETTINGS_SHOWN are ever read into the deck; anything else is ignored by
# construction rather than filtered out, so a new internal field cannot leak.
SETTINGS_SHOWN = (
    "Customer #", "Record Type", "_source",
    "CP - Loan Calculation", "Loan Minimum", "Loan Maximum", "Loan Payment Structure",
    "Interest (Easy, Std)", "Interest (Manual, Std)",
    "Interest (Easy, MLA)", "Interest (Manual, MLA)",
    "Prepaid Finance (Easy, Std)", "Prepaid Finance (Manual, Std)",
    "Prepaid Finance (Easy, MLA)", "Prepaid Finance (Manual, MLA)",
    "Application Fee (Std)", "Application Fee (MLA)", "Year Base for Loan",
    "Allowed to Originate", "Minimum Age for Loan",
    "Loan Waiting Period for New Accounts", "Limit User's 1st Loan to Min",
    "Loan Cool Off Period", "Volume Cap", "Email Reminders (Days in Advance)",
    "End of Month Payments",
    "URL", "Soft Launch", "Full Launch", "Loan Processing Time", "Online Banking Vendor",
)
NOT_RECORDED = "Not recorded"


def load_settings(path, client_id):
    """Read a settings record, refusing one that belongs to another client or program."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if str(raw.get("Customer #", "")).strip() != str(client_id):
        raise SystemExit(f"{path}: Customer # is {raw.get('Customer #')!r}, not "
                         f"{client_id} — refusing another client's settings.")
    if str(raw.get("Record Type", "")).strip() != "CashPlease":
        raise SystemExit(f"{path}: Record Type is {raw.get('Record Type')!r}, not "
                         f"'CashPlease'.")
    if not str(raw.get("_source", "")).strip():
        raise SystemExit(f"{path}: no _source — a slide cannot ship without its source.")
    return {k: str(raw.get(k, "") or "").strip() for k in SETTINGS_SHOWN}


def settings_as_of(S):
    """'... data updated 9/14/26 11:35 AM CST' -> datetime, or None."""
    m = re.search(r"updated\s+(\d{1,2}/\d{1,2}/\d{2,4})", S["_source"])
    if not m:
        return None
    for fmt in ("%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(m.group(1), fmt)
        except ValueError:
            pass
    return None


def _long_date(dt):
    return f"{dt.strftime('%B')} {dt.day}, {dt.year}"


def _us_date(v):
    """'12/12/2023' -> 'Dec 12, 2023'; anything else unchanged."""
    try:
        dt = datetime.strptime(v, "%m/%d/%Y")
    except ValueError:
        return v
    return f"{dt.strftime('%b')} {dt.day}, {dt.year}"


def _as_pct(v):
    """'17' -> '17%'. Only a bare number gets the sign: the app also records charges as
    '$20', 'N/A' or '6% / $25 max', and appending to those shipped 'N/A%' and
    '$20% standard' on the 2026.09 modules (Aaron, 2026-09-17)."""
    return f"{v}%" if re.fullmatch(r"\d+(?:\.\d+)?", v.strip()) else v


def _as_charge(v):
    """A prepaid finance charge: a bare number is a percent, no charge reads 'None',
    anything else ('$20', '6% / $25 max') is shown as recorded."""
    none = ("N/A", "NA", "NONE", "0", "0%", "$0", "$0.00")
    return "None" if v.strip().upper() in none else _as_pct(v)


def _as_fee(v):
    return "None" if v.upper() in ("N/A", "NA", "NONE", "0", "$0", "$0.00") else v


def _lower_units(v):
    """'90 Days' -> '90 days'. Power BI title-cases units mid-sentence."""
    return re.sub(r"\b(Days?|Months?|Weeks?)\b", lambda m: m.group(0).lower(), v)


def _sentence_case_lead(v):
    """'ALL account holders…' -> 'All account holders…'. Only a shouted first word."""
    head, _, rest = v.partition(" ")
    if len(head) >= 3 and head.isalpha() and head.isupper():
        head = head.capitalize()
    return f"{head} {rest}".strip()


def _by_loan_type(S, field, fmt):
    """One value when every loan type agrees; otherwise standard and MLA side by side.

    The app records Easy/Manual × Standard/MLA separately. They agree for every client
    seen so far, and a row reading '17% · 17% · 17% · 17%' would say nothing four times.
    """
    keys = ("Easy, Std", "Manual, Std", "Easy, MLA", "Manual, MLA")
    vals = {k: S[f"{field} ({k})"] for k in keys if S.get(f"{field} ({k})")}
    if not vals:
        return NOT_RECORDED
    if len(set(vals.values())) == 1:
        one = fmt(next(iter(vals.values())))
        return one if one == "None" else f"{one} (standard & MLA)"
    std = {vals[k] for k in keys[:2] if k in vals}
    mla = {vals[k] for k in keys[2:] if k in vals}
    if len(std) == 1 and len(mla) == 1:
        return f"{fmt(std.pop())} standard · {fmt(mla.pop())} MLA"
    return " · ".join(f"{fmt(v)} {k.replace(', ', ' ')}" for k, v in vals.items())


def _yes_no(v):
    return {"true": "Yes", "false": "No"}.get(v.lower(), NOT_RECORDED if not v else v)


def settings_rows(S):
    """(loan terms, eligibility & controls, program line) from a loaded record.

    A blank field reads "Not recorded" — stated, never guessed at and never left as an
    empty cell that looks like a rendering failure.
    """
    def val(v, fmt=lambda x: x):
        return fmt(v) if v else NOT_RECORDED

    fees = {S["Application Fee (Std)"], S["Application Fee (MLA)"]} - {""}
    if not fees:
        app_fee = NOT_RECORDED
    elif len(fees) == 1:
        app_fee = _as_fee(fees.pop())
    else:
        app_fee = (f"{_as_fee(S['Application Fee (Std)'])} standard · "
                   f"{_as_fee(S['Application Fee (MLA)'])} MLA")

    reminder = S["Email Reminders (Days in Advance)"]
    cap = S["Volume Cap"]
    # "Standard - No more than 3 loans…": the leading word is the app's option name,
    # the rest is what the option does. The client needs the second half.
    if " - " in cap:
        cap = cap.split(" - ", 1)[1]

    terms = [
        ["Loan terms", "Setting"],
        ["Loan amount", val(S["CP - Loan Calculation"])],
        ["Minimum loan", val(S["Loan Minimum"])],
        ["Maximum loan", val(S["Loan Maximum"])],
        ["Repayment", val(S["Loan Payment Structure"])],
        ["Interest rate", _by_loan_type(S, "Interest", _as_pct)],
        ["Prepaid finance charge", _by_loan_type(S, "Prepaid Finance", _as_charge)],
        ["Application fee", app_fee],
        ["Year base", val(S["Year Base for Loan"])],
    ]
    controls = [
        ["Eligibility & controls", "Setting"],
        ["Eligible borrowers", val(S["Allowed to Originate"], _sentence_case_lead)],
        ["Minimum age", val(S["Minimum Age for Loan"])],
        ["New-account waiting period",
         val(S["Loan Waiting Period for New Accounts"], _lower_units)],
        ["First loan limited to minimum", _yes_no(S["Limit User's 1st Loan to Min"])],
        ["Cool-off between loans", val(S["Loan Cool Off Period"], _lower_units)],
        ["Volume cap", val(cap)],
        ["Payment reminder email",
         f"{reminder} days before due" if reminder else NOT_RECORDED],
        ["End-of-month payments", val(S["End of Month Payments"])],
    ]
    program = []
    if S["URL"]:
        program.append(re.sub(r"^https?://", "", S["URL"]).rstrip("/"))
    if S["Soft Launch"]:
        program.append(f"Soft launch {_us_date(S['Soft Launch'])}")
    if S["Full Launch"]:
        program.append(f"Full launch {_us_date(S['Full Launch'])}")
    if S["Loan Processing Time"]:
        program.append(f"Loan processing: {S['Loan Processing Time']}")
    if S["Online Banking Vendor"]:
        program.append(f"Online banking: {S['Online Banking Vendor'].replace(' - ', ' – ')}")
    return terms, controls, program


def slide_settings(prs, d, S, settings_name):
    """The client's CashPlease configuration: loan terms beside eligibility and controls.

    Current production settings only. Recommendations to change them belong to the
    client's ops meeting, not to a results review, and are never on this slide.
    """
    as_of = settings_as_of(S)
    s = new_slide(prs)
    head(s, "CashPlease Program Settings",
         f"{d['client_name']}'s production CashPlease settings"
         + (f", as recorded {_long_date(as_of)}." if as_of else "."),
         # Short month: "As of September 14, 2026" wraps to two lines in the 2.35" pill.
         f"As of {as_of.strftime('%b')} {as_of.day}, {as_of.year}" if as_of
         else "Current settings")

    terms, controls, program = settings_rows(S)
    T, H, W, GAP = 1.72, 4.05, 5.98, 0.14
    add_table(s, 0.62, T, W, H, terms, [2.15, 3.83], fs=12)
    add_table(s, 0.62 + W + GAP, T, W, H, controls, [2.45, 3.53], fs=12)
    if program:
        textbox(s, 0.62, 6.02, 12.1, 0.40, "     ·     ".join(program),
                12, TICK_RGB, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)

    interest = "; ".join(f"{k}: {S[k]}" for k in SETTINGS_SHOWN
                         if k.startswith(("Interest (", "Prepaid Finance (",
                                          "Application Fee (")) and S[k])
    notes(s, f"Source: {S['_source']} — client {d['client_id']} {d['client_name']} "
             f"(file {settings_name}). Selection: the one production settings record "
             f"for this client; it is configuration as of that date, not a period's "
             f"figures, so it is not dated to the workbook beside it. Values as recorded: "
             f"{interest}. Loan calculation: {S['CP - Loan Calculation'] or 'blank'}. "
             f"Allowed to originate: {S['Allowed to Originate'] or 'blank'}. Volume cap: "
             f"{S['Volume Cap'] or 'blank'}. 'None' for an application fee is the app's "
             f"N/A. 'Not recorded' marks a field that is blank in the app.")
    return s


def slide_volume(prs, d, pill_text, art_dir):
    """Loans booked by month. The partial month is a bar too, marked as partial.

    It used to be a sentence beside the chart, kept off the axis so a part-month bar
    could not read as a collapse in volume. It is plotted now (Aaron, 2026-09-02) and
    that risk is handled by the treatment — hollow, hatched, orange-edged, annotated
    with the date it runs to — which says "not finished" on the chart itself rather
    than in prose the reader has to find.
    """
    s = new_slide(prs)
    months = list(reversed(d["monthly"]))[-12:]     # oldest first
    daily = d["daily"]

    partial = None
    if daily:
        newest = daily[0]["period"]                 # daily rows are newest first
        partial = {
            "period_month": newest[:7],
            "loans": sum(r["loans"] for r in daily),
            "principal": sum(r["principal"] for r in daily),
            "through": _short_date(newest),
        }

    if not months and not partial:
        head(s, "CashPlease Loan Volume by Month",
             f"No loans booked by {d['client_name']} in this workbook.", pill_text)
        textbox(s, 0.90, 2.20, 11.5, 1.10,
                "The workbook carries no month roll-up and no daily rows for this "
                "client, so there is nothing to plot. This is stated rather than "
                "drawn as an empty chart.",
                16, NAVY_RGB, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
        notes(s, f"Source: {d['source_file']}, tab '{d['sheet_name']}' (report "
                 f"generated {d['report_generated']}). No rows in the 'Created Date' "
                 f"series at all. Nothing is zeroed.")
        return s

    if months:
        sub = (f"Loans booked per completed month, most recent "
               f"{len(months)} month{'s' if len(months) != 1 else ''}"
               + (f", plus the partial month to {partial['through']}." if partial
                  else "."))
    else:
        sub = (f"No completed month in the workbook yet — the bar is the current "
               f"partial month, to {partial['through']}.")
    head(s, "CashPlease Loan Volume by Month", sub, pill_text)

    png = str(Path(art_dir) / f"{d['client_id']}_cp_volume.png")
    cp_charts.monthly_volume_chart(
        png,
        [r["period_month"] for r in months],
        [r["loans"] for r in months],
        [r["principal"] for r in months],
        partial=partial, box=(8.50, 4.71))
    fit_picture(s, png, 0.72, 1.72, 8.50, 4.71)

    if months:
        latest = months[-1]
        callout(s, 9.55, 1.90, 3.16, 1.35, f"{latest['loans']:,}",
                f"Loans booked in {month_label(latest['period'])}")
        callout(s, 9.55, 3.50, 3.16, 1.35, money_short(latest["principal"]),
                f"Principal advanced in {month_label(latest['period'])}",
                fill=ORANGE_RGB)
    if partial:
        y = 5.10 if months else 1.90
        callout(s, 9.55, y, 3.16, 1.35, f"{partial['loans']:,}",
                f"Booked so far in {month_label(partial['period_month'] + '-01')}",
                fill=ORANGE_RGB if not months else NAVY_RGB)

    notes(s, f"Source: {d['source_file']}, tab '{d['sheet_name']}', the "
             f"'Created Date' series (report generated {d['report_generated']}). "
             f"Selection: completed-month roll-up rows (labelled '*' on the tab), most "
             f"recent {len(months)} of {len(d['monthly'])} present"
             + (f", plus the {len(daily)} daily rows of the current month summed into "
                f"one PARTIAL bar through {partial['through']}." if partial else ".")
             + f" The partial bar is drawn hollow and hatched with its through-date on "
               f"the chart so it cannot be read as a finished month. Bars are loan "
               f"counts (left axis); the teal line is principal advanced (right axis).")
    return s


def slide_status(prs, d, pill_text, art_dir):
    m = d["metrics"]
    s = new_slide(prs)
    head(s, "CashPlease Loan Portfolio by Status",
         f"Every loan booked by {d['client_name']} program to date, by current status.",
         pill_text)

    total = d["total"]["loans"] or 1
    rows = [["Status", "Loans", "% of Loans", "Principal", "Interest"]]
    for label, v in d["status"].items():
        rows.append([label, f"{v['loans']:,}", pct(v["loans"] / total),
                     money(v["principal"]), money(v["interest"])])
    rows.append(["TOTAL", f"{d['total']['loans']:,}", "100.0%",
                 money(d["total"]["principal"]), money(d["total"]["interest"])])

    add_table(s, 0.62, 1.72, 7.30, 4.05, rows, [1.5, 0.8, 0.9, 1.2, 1.1],
              highlight=(len(rows) - 1,), fs=11)

    callout(s, 8.20, 1.80, 2.20, 1.30, f"{m['active_loans']:,}", "Loans funded")
    callout(s, 10.52, 1.80, 2.20, 1.30, money_short(m["active_principal"]),
            "Principal outstanding", fill=ORANGE_RGB)

    png = str(Path(art_dir) / f"{d['client_id']}_cp_status.png")
    cp_charts.status_mix_chart(png, list(d["status"].keys()),
                               [v["loans"] for v in d["status"].values()],
                               box=(4.52, 2.52))
    fit_picture(s, png, 8.20, 3.24, 4.52, 2.52)

    textbox(s, 0.62, 5.90, 7.30, 0.62,
            f"{pct(m['pct_loans_paid_off'])} of loans booked have been paid off; "
            f"{pct(m['pct_loans_overdue'])} are overdue and "
            f"{pct(m['pct_loans_charged_off'])} charged off.",
            14, NAVY_RGB, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)

    notes(s, f"Source: {d['source_file']}, tab '{d['sheet_name']}', the 'Loans By "
             f"Status' block, rows Pending through Closed plus TOTAL (report "
             f"generated {d['report_generated']}). Selection: all loans booked "
             f"program to date. Percentages are each status's loan count over the "
             f"TOTAL loan count on the same block. The charge-off % reported on the "
             f"tab (L9) is a different measure and is shown on the Peer Comparison "
             f"slide, not derived here.")
    return s


def slide_peer(prs, d, pill_text, art_dir):
    """Pills on the left, the same comparison as an index chart on the right.

    The pill block used to run the full slide width and end at 6.70", leaving the
    footnote nowhere to go: fit_layout pulled it up off the bottom edge and dropped
    it straight onto the last row of capsules. Narrowing the block buys the footnote
    its own band AND makes room for the chart, so the fix and the addition are the
    same change.
    """
    m, peer = d["metrics"], d["metrics"]["peer"]
    s = new_slide(prs)
    head(s, "CashPlease Peer Comparison",
         f"{d['client_name']} against the all-accounts cohort of every "
         f"CashPlease client.", pill_text)

    rows = []
    # Only a client with a DDA count AND a full 12-month window earns this row. Without
    # the count there is no rate; without the window the comparison is against tenure.
    if m["peer_comparable"]:
        # The window goes on its own line: at 13 pt the label wrapped inside the parenthesis,
        # "(12" / "mo)" (Aaron, 2026-10-28). The chart re-wraps the label itself.
        rows.append(("Loans per 1,000 DDAs\n(12 mo)", peer["loans_per_1k_dda"],
                     m["loans_per_1k_dda"], lambda v: f"{v:.1f}"))
    rows += [
        ("Charge-off rate", peer["charge_off_pct"], m["charge_off_pct"],
         lambda v: pct(v, 2)),
        ("Average loan size", peer["avg_loan_size"], m["avg_loan_size"], money),
        ("Average interest per loan", peer["avg_interest_per_loan"],
         m["avg_interest_per_loan"], money),
        ("Loans paid off", peer["pct_loans_paid_off"], m["pct_loans_paid_off"], pct),
    ]

    textbox(s, 0.70, 1.54, 1.62, 0.40, "Cohort", 11,
            TICK_RGB, True, PP_ALIGN.CENTER, BODY, MSO_ANCHOR.MIDDLE)
    # Wider and a point smaller than the pill column it sits over, because it carries a
    # client NAME — "Altamaha Bank and Trust Company" is 31 characters and will not fit
    # a 1.62" box on one line. The extra width runs into empty space above the metric
    # labels, not over any shape.
    textbox(s, 4.16, 1.54, 3.02, 0.40, d["client_name"], 11,
            TICK_RGB, True, PP_ALIGN.CENTER, BODY, MSO_ANCHOR.MIDDLE)

    T, H, GAP = 1.98, 0.66, 0.18
    for i, (label, pv, cv, fmt) in enumerate(rows):
        y = T + i * (H + GAP)
        capsule(s, 0.70, y, 1.62, H, fmt(pv), ORANGE_RGB, size=13)
        textbox(s, 2.42, y, 2.34, H, label.split("\n"), 13, NAVY_RGB, False,
                PP_ALIGN.CENTER, BODY, MSO_ANCHOR.MIDDLE)
        capsule(s, 4.86, y, 1.62, H, fmt(cv), NAVY_RGB, size=13)

    png = str(Path(art_dir) / f"{d['client_id']}_cp_peer.png")
    cp_charts.peer_index_chart(
        png, [r[0].replace("\n", " ") for r in rows],
        [(r[2] / r[1] * 100) if r[1] else 0.0 for r in rows],
        box=(5.75, 4.02))
    fit_picture(s, png, 6.95, 1.98, 5.75, 4.02)
    textbox(s, 6.95, 1.54, 5.75, 0.40,
            f"{d['client_name']} relative to the cohort", 11,
            TICK_RGB, True, PP_ALIGN.CENTER, BODY, MSO_ANCHOR.MIDDLE)

    # The cohort's make-up is in the notes with the rest of the methodology (Aaron, 2026-10-28:
    # the footnote stating it came off the face). What stays on the face is a row that is
    # absent, and why: a silently missing row reads as an oversight; a stated one reads as a
    # limit of the data.
    cohort = (COHORT_NOTE.format(client=d["client_name"], **peer)
              + DDA_COHORT_NOTE.format(client=d["client_name"], **peer)
              + " The index reads each figure against the cohort's, so 100 is it.")
    why = ""
    if m["loans_per_1k_dda"] is None:
        why = ("Loans per 1,000 DDAs is not shown: "
               + (m["dda_missing_reason"] or "no DDA count is available") + ".")
    elif not m["peer_comparable"]:
        why = (f"Loans per 1,000 DDAs is not compared: {d['client_name']} has "
               f"{m['window_months']} completed months, not the cohort's 12.")
    if why:
        textbox(s, 0.62, 6.18, 12.1, 0.56, why, 11, TICK_RGB, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)

    notes(s, f"Source: {d['source_file']} — client figures from tab "
             f"'{d['sheet_name']}', peer figures from tab 'All Clients Summary - "
             f"Loans' (report generated {d['report_generated']}). Selection: the "
             f"all-accounts cohort is the rollup tab, verified at extract time to "
             f"equal the sum of all {peer['cohort_tabs']} client tabs. It includes "
             f"{d['client_name']} (it is not adjusted to exclude them) and it also "
             f"includes "
             f"tabs no deck is built for — the internal 'enterpoints' test tab and "
             f"any cancelled client — so the cohort is stated as a tab count, never "
             f"as a client count. 'Charge-off rate' is a reported value (L9) on "
             f"both tabs and is not derivable from the tabs' own totals. "
             + dda_note(d, m) +
             f" Average loan size and average interest per "
             f"loan are the cohort's total principal / total interest divided by its "
             f"loan count. The index chart plots client / cohort x 100 for each "
             f"row shown; bars are one colour and the reference line carries the "
             f"accent, because 'above' is not 'better' for the charge-off rate. "
             + cohort)
    return s


# ------------------------------------------------------------------ assembly
def main():
    if len(sys.argv) not in (4, 5):
        raise SystemExit(__doc__.strip())
    pack_path, template, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    d = json.loads(pack_path.read_text(encoding="utf-8"))
    settings_path = Path(sys.argv[4]) if len(sys.argv) == 5 else None
    S = load_settings(settings_path, d["client_id"]) if settings_path else None

    if d.get("cancelled"):
        raise SystemExit(f"{d['client_id']} {d['client_name']}: {d['cancelled']} — "
                         f"not built. Leftover data is not a signal to build "
                         f"(CLAUDE.md).")

    art_dir = Path(os.environ.get("CP_ARTIFACTS", pack_path.parent.parent / "figures"))
    art_dir.mkdir(parents=True, exist_ok=True)
    d["_art_dir"] = str(art_dir)          # for the cover's trimmed client logo
    # ...and for the data-slide mark, which is this client's logo (Aaron, 2026-10-02).
    CLIENT[0], CLIENT[1] = d["client_id"], str(art_dir)

    prs = Presentation(str(template))
    shell = list(prs.slides._sldIdLst)          # the template's own slides

    # A single-product client gets a single-product DECK, formatted like an ARS / ICS /
    # MRPC one — cover, Executive Summit, agenda, divider, content, Questions, Contact
    # (Aaron, 2026-09-01: "single product clients get single product decks, including
    # cashplease"). The five CashPlease slides are the same either way; the shell is what
    # makes it a deck.
    #
    # This also makes the deck composable for free. `assemble_combined.section_slides()`
    # keeps a program's section by dropping the cover, Summit, agenda, Q&A and Contact —
    # so feeding this deck to the combined builder yields exactly the divider plus the
    # four content slides, which is the CashPlease section. That is how ARS, ICS and MRPC
    # already work, and it is why the shell is adapted here rather than stripped.
    keep = adapt_shell(prs, d)

    pill_text = f"PTD · {pull_label(d['report_generated'])}"
    # Program Settings follows the Overview when the client has a settings record on
    # file (Inputs/Product Settings/, resolved by scripts/build_cashplease.py). A client
    # without one gets no settings slide rather than a slide of "Not recorded" — the
    # build prints which clients those are, so the gap is visible, not silent.
    made = [slide_divider(prs, d),
            slide_overview(prs, d, pill_text, art_dir)]
    if S is not None:
        made.append(slide_settings(prs, d, S, settings_path.name))
    made += [slide_volume(prs, d, pill_text, art_dir),
             slide_status(prs, d, pill_text, art_dir),
             slide_peer(prs, d, pill_text, art_dir)]

    lst = prs.slides._sldIdLst
    order = [sldid_of(prs, s) for s in
             ([keep["cover"], keep["summit"], keep["agenda"]] + made
              + [keep["questions"], keep["contact"]])]
    for el in list(lst):
        lst.remove(el)
    for el in order:
        lst.append(el)
    want = 5 + len(made)
    assert len(list(lst)) == want, f"single-product deck should be {want} slides, got {len(list(lst))}"
    assert len({id(e) for e in lst}) == want, "a slide is referenced twice"

    # Slide numbers, last — the order the ARS builder uses, so nothing downstream
    # resizes them. STYLE.md: numbers on content slides, none on the cover, the Summit,
    # a section divider or a closing cover. `assemble_combined.renumber` preserves each
    # slide's numbered/unnumbered status and renumbers sequentially, so the four content
    # slides have to declare themselves numbered by carrying a box at all.
    import assemble_combined as ac
    for s in made[1:]:                       # made[0] is the divider — never numbered
        tb = s.shapes.add_textbox(*[Inches(v) for v in ac.NUM_LTWH])
        r = tb.text_frame.paragraphs[0].add_run()
        r.text = "0"                         # value is rewritten by renumber()
        r.font.name = BODY
        r.font.size = Pt(ac.NUM_PT)
        r.font.bold = True
        r.font.color.rgb = NAVY_RGB

    # Same Summit slide as every other program, from build/assets/summit_slide.pptx
    # rather than this shell's own copy (Aaron, 2026-09-11).
    import summit_slide
    summit_slide.insert_summit_after_title(prs)

    import fit_layout
    fit_layout.fit(prs)
    ac.renumber(prs)

    out.parent.mkdir(parents=True, exist_ok=True)
    # The pre-strip deck goes in a scratch dir removed however this block ends; it used to be
    # unlinked only on success, so a failed strip left it in %TEMP% (2026-09-16).
    with tempfile.TemporaryDirectory(prefix="cp_full_") as scratch:
        tmp = Path(scratch) / f"{out.stem}.__full.pptx"
        prs.save(str(tmp))

        # Physically drop the shell's orphaned slide parts and now-unused media. Leaving
        # them in the package is what made the 2026.08 ICS decks unopenable.
        subprocess.run([sys.executable, str(BUILD / "strip_dead.py"),
                        str(tmp), str(out)], check=True)
    print(f"built {out} -> {len(list(prs.slides._sldIdLst))} slides ({d['client_id']} {d['client_name']})")


if __name__ == "__main__":
    main()
