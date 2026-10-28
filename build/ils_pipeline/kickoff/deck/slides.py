# Ported from v5 02-Scripts/ils/kickoff_analysis/deck/slides.py at 7ba1e63. Logic unchanged; the one edit is the import of deckkit from kickoff/_v5/.
"""The ILS kickoff deck. Its own deck -- never a chapter in the ARS deck.

Same rule `pre_go_live/deck.py` states: one product, several deliverables,
each with its own story. Built on `deckkit`, the product-neutral facade, so
nothing here imports from `ars.deck` directly.

The manifest below IS the story order. Adding an analysis means adding one
entry to it -- name, section, and how the slide reads -- and nothing else in
this module changes.

A manifest entry whose analysis did not run is ABSENT from the deck, never
rendered empty. A slide with no chart says so on its own face rather than
presenting a table of digits as though a picture had been intended.
"""

from __future__ import annotations

from dataclasses import dataclass
import tempfile
from pathlib import Path

from ils_pipeline.kickoff._v5 import deckkit as dk

from . import forms

# ---------------------------------------------------------------------------
# The manifest. `key` matches the sheet name the run emits, which is what
# keeps the deck and the workbook from drifting apart -- a test fails if a
# sheet exists with no slide, or a slide with no sheet.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Slide:
    """One analysis's place in the story.

    There was a `headline` field here -- "what the slide asserts" -- and the
    renderer never read one of the nineteen. A headline has to carry the
    slide's NUMBER, so it can only be built where the numbers are, which is
    `forms.HEADLINES`. A field that looks authoritative and is never read is
    worse than no field: it is where nineteen careful headlines went while
    every slide printed the same generated sentence.
    """
    key: str            # the run's sheet name; the join between run and deck
    section: str        # divider it sits under


SECTIONS = ["The book", "Where the NSF activity is", "How it is configured"]

SLIDE_MANIFEST = [
    # ---- The book ----------------------------------------------------------
    Slide("Account Status Analysis", "The book"),
    Slide("Account Type Analysis", "The book"),
    Slide("Product Code Distribution", "The book"),
    Slide("Personal Deposit Analysis", "The book"),
    Slide("Business Deposit Analysis", "The book"),

    # ---- Where the NSF activity is -----------------------------------------
    Slide("NSF Stratification", "Where the NSF activity is"),
    Slide("NSF Stratification (Business)", "Where the NSF activity is"),
    Slide("NSF Pay Ratio", "Where the NSF activity is"),
    Slide("NSF Pay Ratio (Business)", "Where the NSF activity is"),
    Slide("NSF Strat w Deposits", "Where the NSF activity is"),
    Slide("NSF Strat w Deposits (Biz)", "Where the NSF activity is"),

    # ---- How it is configured ----------------------------------------------
    Slide("OD Status Stratification", "How it is configured"),
    Slide("OD Status Stratification (Biz)", "How it is configured"),
    Slide("OD Limit Stratification", "How it is configured"),
    Slide("OD Limit Stratification (Biz)", "How it is configured"),
    Slide("Reg E Summary", "How it is configured"),
    Slide("Reg E by OD Eligibility", "How it is configured"),
    Slide("Reg E by OD Eligibility (Biz)", "How it is configured"),
    Slide("Historical Reg E", "How it is configured"),
]

MANIFEST_KEYS = [s.key for s in SLIDE_MANIFEST]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

_MAX_TABLE_ROWS = 12


def _cell(value) -> str:
    """One table cell, for the no-chart fallback."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        if value != value:                       # NaN
            return ""
        return f"{value:,.1f}" if abs(value) >= 1 else f"{value:.2f}"
    return str(value)


def _rows(frame) -> list[list[str]]:
    """deckkit's table takes rows, header first -- not a DataFrame."""
    header = [str(c) for c in frame.columns]
    body = [[_cell(v) for v in row] for row in frame.itertuples(index=False)]
    return [header] + body


# THE CONTENT BAND. One band, named once, used by every layout.
#
# Before this, three layouts carried three different pairs of magic numbers
# (1.72/5.05, 1.9/4.4, 1.72/4.95) and none of them was the slide. The band
# runs from under the subtitle to the rail floor, and a chart is expected to
# FILL it -- charts.FIG_H_RAIL/FIG_H_FULL author each form at this aspect so
# that it can.
BAND_TOP = 1.72
BAND_BOTTOM = dk.RAIL_BOTTOM          # the grid, not a copy of it
BAND_H = BAND_BOTTOM - BAND_TOP       # 4.90


def _place(slide, chart, rail: bool) -> None:
    """The chart in the band, centred on whatever it cannot fill.

    A form that authors a shorter canvas than the band used to hang from the
    top and leave every spare inch in one lump at the bottom of the slide --
    which is what "too much white space" was. Whatever is left over is now
    split above and below, so a short chart reads as centred rather than as
    a slide someone stopped filling in.
    """
    from PIL import Image
    with Image.open(chart) as img:
        w, h = img.size
    field = (dk.RAIL_LEFT - dk.RAIL_GUTTER - dk.MARGIN_L) if rail else dk.CONTENT_W
    height = min(BAND_H, field / (w / h))
    dk.picture(slide, chart, top=BAND_TOP + (BAND_H - height) / 2,
               max_h=height, rail=rail)


def _slide(prs, new, spec: Slide, frame, panel) -> None:
    """One analysis, one slide, composed the way the house decks compose one.

    The first cut put a label in the title and the raw table beside the chart,
    which is a workbook tab with a picture stapled to it. The pattern in
    ars/deck/deposit_slides.py is: a headline that states the finding WITH its
    number, the chart in the main slot, three callout tiles down the right
    edge. The table stays in the workbook, which is where forty rows belong.
    """
    slide = new()
    layout = LAYOUTS.get(spec.key, "rail") if panel["chart"] else "rail"
    dk.title(slide, panel["headline"], panel["subtitle"])

    if layout == "full":
        _place(slide, Path(panel["chart"]), rail=False)
        return

    if layout == "hero" and panel["rail"]:
        # The card sits where the rail tiles sit. It used to be placed at
        # 0.7in while the picture was centred across a field starting at
        # 1.18in -- so the card printed ON TOP of its own chart, clipping its
        # label mid-word, on all three hero slides.
        value, label, note = _hero_number(panel)
        dk.kpi(slide, dk.RAIL_LEFT, BAND_TOP + 0.9, 2.55, label, value, note)
        _place(slide, Path(panel["chart"]), rail=True)
        return

    if panel["chart"]:
        # rail=True or the chart prints underneath the callout tiles. It
        # centred across the whole content field before, which is "chart and
        # data callouts overlap" -- four slides in one review.
        _place(slide, Path(panel["chart"]), rail=bool(panel["rail"]))
    else:
        # No chart is a fallback, not a layout. Say so, and show the table.
        dk.table(slide, _rows(frame.head(_MAX_TABLE_ROWS)), left=0.7, top=1.8,
                 width=9.2)

    if panel["rail"]:
        dk.rail(slide, panel["rail"], top=BAND_TOP + 0.08)


_APPENDIX_ROWS = 16

# Layout follows what the slide is FOR. One layout on nineteen slides is one
# template wearing nineteen headlines -- the same defect as one chart form on
# nineteen slides, a level up (James, 2026-09-09).
#
#   rail  chart plus three callout tiles. The default: a finding with
#         supporting numbers beside it.
#   full  full-bleed chart, no tiles. For a distribution whose shape IS the
#         point and whose bands are too many to summarise in three tiles.
#   hero  one number at slide scale, chart beneath. For a slide that exists
#         to say a single figure.
LAYOUTS = {
    "Product Code Distribution": "full",       # 24 bands; no three tiles help
    "Personal Deposit Analysis": "full",
    "Business Deposit Analysis": "full",
    "OD Limit Stratification": "full",
    "Historical Reg E": "full",
    "Account Type Analysis": "hero",           # one number: personal share
    "Reg E Summary": "hero",                   # one number: elected share
    "NSF Pay Ratio": "hero",                   # one number: the blended rate
}


def _hero_number(panel) -> tuple[str, str, str]:
    """The one figure this slide exists to say, pulled off the rail.

    Label and note come back SEPARATELY. Joined into one string they ran to
    "Pay rate — of 76,199 items presented" and clipped to "Pay rate — o" in
    a card built for a short label and a note of its own.
    """
    for label, value, note in panel["rail"]:
        if "%" in str(value):
            return str(value), str(label), str(note)
    label, value, note = panel["rail"][0]
    return str(value), str(label), str(note)


def _appendix(prs, new, analyses: dict) -> None:
    """The formatted table behind every slide, at the back.

    "That way the user can add them if he wants" (James, 2026-09-09). The
    front of the deck is charts because a table of digits is not a finding,
    but the numbers still have to be reachable without opening the workbook
    mid-meeting -- so they sit at the back, formatted, ready to be dragged
    forward or deleted.
    """
    dk.divider(prs, new, "Appendix")
    for spec in SLIDE_MANIFEST:
        frame = analyses.get(spec.key)
        if frame is None or getattr(frame, "empty", True):
            continue
        slide = new()
        shown = min(len(frame), _APPENDIX_ROWS)
        note = ("" if shown == len(frame)
                else f"first {shown} of {len(frame)} rows — the workbook has all")
        dk.title(slide, spec.key, note)
        dk.table(slide, _rows(frame.head(_APPENDIX_ROWS)), left=0.7, top=1.7,
                 width=12.0, size=10)


# The blanks only the person who pulled the extract can fill. Kept as data
# so the slide is a list of fields rather than a paragraph pretending to be
# one -- and so a field can be added without touching the layout.
_TO_COMPLETE = [
    ("Collected as of", "the date this extract was pulled"),
    ("Data covers", "first period  \u2014  last period"),
    ("Known exclusions", "anything deliberately left out of the file"),
]

_FIELD_RULE = "  " + "." * 78


def _provenance(new, client_id, period, analyses, source, csm) -> None:
    """Where the data came from, before anything is claimed about it.

    "The creator of the file will give some high-level information about the
    data -- this data was collected as of X date, the date ranges are X
    through Y" (James, 2026-09-09). What the run knows goes above the line;
    what only the person who pulled the extract knows goes below it, as an
    explicit blank rather than a silent absence.

    Composed rather than typed: it was a text block top-left with three tiles
    to its right and the bottom half of the slide empty, and the one thing
    that needed to be acted on -- the CSM name -- was a 9pt red orphan under
    the tiles that read as an error. The blanks are now fields on ruled
    lines, filling the band, and the name is the first of them.
    """
    slide = new()
    dk.title(slide, "The data behind this deck",
             f"{client_id} \u00b7 period {period}")

    left, width = dk.MARGIN_L, dk.CONTENT_W
    label_w, footer_h = 2.15, 0.34
    y = BAND_TOP

    # ---- what the run knows -------------------------------------------
    dk.text(slide, left, y, width, 0.24, "WHAT THIS RUN READ", size=10,
            bold=True, color=dk.SLIDE_GREY, font=dk.HEAD_FONT)
    y += 0.34
    known = [("Extract", Path(source).name if source else "not recorded"),
             ("Analyses run", f"{len(analyses)} \u2014 one workbook tab each"),
             ("Period", period)]
    for label, value in known:
        dk.text(slide, left, y, label_w, 0.28, label, size=12, bold=True,
                color=dk.SLIDE_GREY)
        # The filename in FULL. Truncated to 18 characters it read
        # "1842_OneTime Data_2", which looks like a broken string, and the
        # one fact this slide exists to record was the casualty.
        dk.text(slide, left + label_w, y, width - label_w, 0.28, value,
                size=12)
        y += 0.36

    y += 0.16
    dk.rule(slide, left, y, width)
    y += 0.34

    # ---- what only the person who pulled it knows ----------------------
    dk.text(slide, left, y, width, 0.24,
            "TO BE COMPLETED BY WHOEVER PULLED THIS FILE", size=10,
            bold=True, color=dk.SLIDE_RED, font=dk.HEAD_FONT)
    y += 0.34

    fields = list(_TO_COMPLETE) if csm else \
        [("Prepared by", "the CSM sending this deck")] + list(_TO_COMPLETE)
    if csm:
        fields.insert(0, ("Prepared by", csm))

    # The stack is solved against the band rather than stepped by a constant
    # and allowed to run off the bottom: the first draft overflowed to 6.82
    # and printed the closing line straight through "Known exclusions".
    floor = BAND_BOTTOM - footer_h - 0.12
    step = min(0.60, (floor - y) / max(len(fields), 1))
    for label, hint in fields:
        filled = csm and label == "Prepared by"
        dk.text(slide, left, y, label_w, 0.28, label, size=12, bold=True,
                color=dk.SLIDE_NAVY if filled else dk.SLIDE_RED)
        dk.text(slide, left + label_w, y, width - label_w, 0.28,
                hint if filled else _FIELD_RULE, size=12,
                color=dk.SLIDE_NAVY if filled else dk.SLIDE_GREY)
        if not filled:
            dk.text(slide, left + label_w, y + 0.25, width - label_w, 0.22,
                    hint, size=9, color=dk.SLIDE_GREY)
        y += step

    dk.text(slide, left, BAND_BOTTOM - footer_h, width, 0.3,
            "Every figure in this deck is as of the extract above and no "
            "later.", size=11, color=dk.SLIDE_GREY)


def build(client_id: str, period: str, analyses: dict, chart_files: dict,
          template: Path, out: Path, warnings=(), charts_dir: Path | None = None,
          codes=None, source: str = "", csm: str = "",
          appendix: bool = True) -> Path:
    """Write the kickoff deck.

    `analyses` and `chart_files` are keyed by the run's sheet names, so the
    deck renders exactly what the workbook contains and nothing it does not.
    An analysis the run skipped is absent here, which is the honest reading of
    a section that did not produce a number.
    """
    # A chart has to be written somewhere. With no charts_dir it used to be
    # Path("."), so every caller that omitted one -- the tests -- scattered
    # PNGs into the working directory, and 368 of them reached the repo.
    # A scratch directory that cleans itself up is the only safe default.
    with tempfile.TemporaryDirectory() as scratch:
        return _build(client_id, period, analyses, chart_files, template, out,
                      warnings, charts_dir or Path(scratch), codes, source,
                      csm, appendix)


def _build(client_id, period, analyses, chart_files, template, out, warnings,
           charts_dir, codes, source, csm, appendix) -> Path:
    prs, new = dk.open_template(template)

    # The cover was a title on a blank white slide. divider() is the designed
    # object this template already has -- full-bleed navy, corner bands, an
    # orange rule -- so the deck opens as something rather than as paper.
    dk.divider(prs, new, f"{client_id} · ILS kickoff")

    _provenance(new, client_id, period, analyses, source, csm)

    current_section = None
    for spec in SLIDE_MANIFEST:
        frame = analyses.get(spec.key)
        if frame is None or getattr(frame, "empty", True):
            continue
        if spec.section != current_section:
            dk.divider(prs, new, spec.section)
            current_section = spec.section
        # Its own chart form, drawn from the shared library. Falls back to
        # the run's own PNG, then to no chart at all.
        panel = forms.panel(spec.key, frame, charts_dir, codes)
        if panel is None:
            continue
        if panel["chart"] is None:
            existing = chart_files.get(spec.key) or []
            panel["chart"] = existing[0][0] if existing else None
        _slide(prs, new, spec, frame, panel)

    if appendix:
        _appendix(prs, new, analyses)

    if warnings:
        slide = new()
        dk.title(slide, "What this run could not account for",
                 "Read before presenting any number on the slides above")
        # Prose, not a rail: a rail takes (label, value, note) triples and
        # these are sentences. The point is that they are legible, on the
        # deck, in front of whoever is presenting it.
        body = "\n\n".join(f"\u2022  {w}" for w in list(warnings)[:8])
        dk.text(slide, 0.7, 1.7, 12.2, 5.0, body, size=13)

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    return out


def unslided(analyses: dict) -> list[str]:
    """Analyses the run produced that no manifest entry claims.

    The catalogue lesson from the deposit chapter: a thing that is computed
    and reaches no output is invisible, and invisible is where the wrong
    number lives. Adding an analysis without adding a slide should be a
    deliberate choice, not an oversight.
    """
    return sorted(set(analyses) - set(MANIFEST_KEYS))


def chartless() -> list[str]:
    """Manifest entries with no chart form mapped. Should be empty."""
    return [s.key for s in SLIDE_MANIFEST if s.key not in forms.FORMS]
