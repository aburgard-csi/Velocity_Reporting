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

Usage:
    python build_cp_gen.py <pack.json> <cashplease_template.pptx> <out.pptx>
"""
import copy
import json
import os
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
    pill(slide, pill_text)


def logo(slide, L, T, W, H):
    path = BUILD / "assets" / "logo.png"
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
    for sh in found["cover"].shapes:
        if not sh.has_text_frame:
            continue
        txt = sh.text_frame.text.strip()
        if txt == ac.PRODUCT_NAME["ARS"]:
            _settext(sh, "CashPlease®")
        elif "Executive Review" in txt:
            _set_lines(sh, [d["client_name"], f"Executive Review  •  {label}"])

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

    notes(found["cover"],
          f"Source: {d['source_file']}, tab '{d['sheet_name']}' (report generated "
          f"{d['report_generated']}). Cover for client {d['client_id']} "
          f"{d['client_name']}. No figures. The period label is the workbook's own "
          f"generation date ({label}) rather than a month: CashPlease is a weekly "
          f"snapshot and always uses the most recent workbook (Aaron, 2026-09-01), so "
          f"a month label would misstate what the figures cover.")
    return found


# ------------------------------------------------------------------ the slides
def slide_divider(prs, d):
    s = new_slide(prs)
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0,
                            Inches(SLIDE_W), Inches(SLIDE_H))
    bg.fill.solid(); bg.fill.fore_color.rgb = NAVY_RGB
    bg.line.fill.background(); bg.shadow.inherit = False

    card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                              Inches(0.55), Inches(0.5), Inches(2.22), Inches(0.92))
    card.fill.solid(); card.fill.fore_color.rgb = WHITE_RGB
    card.line.fill.background(); card.shadow.inherit = False
    logo(s, 0.71, 0.66, 1.9, 0.6)

    textbox(s, 0.7, 2.25, 11.9, 2.4, "CashPlease®", 52, WHITE_RGB, True,
            PP_ALIGN.CENTER, HEAD, MSO_ANCHOR.MIDDLE)
    textbox(s, 0.7, 5.05, 11.9, 0.9, BENEFITS, 22, ORANGE_RGB, True,
            PP_ALIGN.CENTER, HEAD, MSO_ANCHOR.MIDDLE)
    notes(s, f"Section divider. No figures. Client {d['client_id']} "
             f"{d['client_name']}.")
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
    for i, (val, lab) in enumerate(tiles):
        callout(s, L + i * (W + GAP), T, W, H, val, lab)

    months = list(reversed(d["monthly"]))
    if months:
        png = str(Path(art_dir) / f"{d['client_id']}_cp_cumulative.png")
        cp_charts.cumulative_growth_chart(
            png, [r["period_month"] for r in months], [r["loans"] for r in months])
        fit_picture(s, png, 0.62, 3.42, 7.40, 2.80)
        textbox(s, 0.62, 3.14, 7.40, 0.30, "Cumulative loans booked, by month",
                13, TICK_RGB, True, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)
    else:
        textbox(s, 0.62, 3.42, 7.40, 2.80,
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
                             Inches(8.25), Inches(3.14), Inches(4.47), Inches(3.08))
    box.fill.solid(); box.fill.fore_color.rgb = WHITE_RGB
    box.line.color.rgb = LABEL_RGB; box.line.width = Pt(1)
    box.shadow.inherit = False; shadow(box)
    textbox(s, 8.45, 3.30, 4.07, 2.76, lines, 13, NAVY_RGB, False,
            PP_ALIGN.LEFT, BODY, MSO_ANCHOR.MIDDLE)

    cohort_note = COHORT_NOTE.format(client=d["client_name"], **peer)
    if m["loans_per_1k_dda"] is not None:
        cohort_note += DDA_COHORT_NOTE.format(client=d["client_name"], **peer)
    textbox(s, 0.62, 6.36, 12.1, 0.40, cohort_note,
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
        partial=partial)
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
                               [v["loans"] for v in d["status"].values()])
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
        rows.append(("Loans per 1,000 DDAs (12 mo)", peer["loans_per_1k_dda"],
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
        textbox(s, 2.42, y, 2.34, H, label, 13, NAVY_RGB, False,
                PP_ALIGN.CENTER, BODY, MSO_ANCHOR.MIDDLE)
        capsule(s, 4.86, y, 1.62, H, fmt(cv), NAVY_RGB, size=13)

    png = str(Path(art_dir) / f"{d['client_id']}_cp_peer.png")
    cp_charts.peer_index_chart(
        png, [r[0] for r in rows],
        [(r[2] / r[1] * 100) if r[1] else 0.0 for r in rows])
    fit_picture(s, png, 6.95, 1.98, 5.75, 4.02)
    textbox(s, 6.95, 1.54, 5.75, 0.40,
            f"{d['client_name']} relative to the cohort", 11,
            TICK_RGB, True, PP_ALIGN.CENTER, BODY, MSO_ANCHOR.MIDDLE)

    # Two lines. The derivation of each figure is in the notes, where the rest of the
    # methodology already lives; what has to be on the face is the SELECTION — plus,
    # when a row is absent, why it is absent. A silently missing row reads as an
    # oversight; a stated one reads as a limit of the data.
    if m["loans_per_1k_dda"] is None:
        why = (" Loans per 1,000 DDAs is not shown: "
               + (m["dda_missing_reason"] or "no DDA count is available") + ".")
    elif not m["peer_comparable"]:
        why = (f" Loans per 1,000 DDAs is not compared: {d['client_name']} has "
               f"{m['window_months']} completed months, not the cohort's 12.")
    else:
        why = (DDA_COHORT_NOTE.format(client=d["client_name"], **peer)
               + " The index reads each figure against the cohort's, so 100 is it.")
    textbox(s, 0.62, 6.18, 12.1, 0.56, COHORT_NOTE.format(client=d["client_name"], **peer) + why,
            11, TICK_RGB, False, PP_ALIGN.LEFT, BODY, MSO_ANCHOR.TOP)

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
             f"accent, because 'above' is not 'better' for the charge-off rate.")
    return s


# ------------------------------------------------------------------ assembly
def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__.strip())
    pack_path, template, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    d = json.loads(pack_path.read_text(encoding="utf-8"))

    if d.get("cancelled"):
        raise SystemExit(f"{d['client_id']} {d['client_name']}: {d['cancelled']} — "
                         f"not built. Leftover data is not a signal to build "
                         f"(CLAUDE.md).")

    art_dir = Path(os.environ.get("CP_ARTIFACTS", pack_path.parent.parent / "figures"))
    art_dir.mkdir(parents=True, exist_ok=True)

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
    made = [slide_divider(prs, d),
            slide_overview(prs, d, pill_text, art_dir),
            slide_volume(prs, d, pill_text, art_dir),
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
    assert len(list(lst)) == 10, f"single-product deck should be 10 slides, got {len(list(lst))}"
    assert len({id(e) for e in lst}) == 10, "a slide is referenced twice"

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
    tmp = Path(tempfile.gettempdir()) / f"{out.stem}.__full.pptx"
    prs.save(str(tmp))

    # Physically drop the shell's orphaned slide parts and now-unused media. Leaving
    # them in the package is what made the 2026.08 ICS decks unopenable.
    subprocess.run([sys.executable, str(BUILD / "strip_dead.py"),
                    str(tmp), str(out)], check=True)
    tmp.unlink(missing_ok=True)
    print(f"built {out} -> {len(list(prs.slides._sldIdLst))} slides ({d['client_id']} {d['client_name']})")


if __name__ == "__main__":
    main()
