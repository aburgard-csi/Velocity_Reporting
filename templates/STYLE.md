# Deck Style Guide — ARS · ICS · MRPC

The single source of truth for how every client deck looks. If a deck disagrees with this
file, the deck is wrong.

**Read this before building.** Most of it is enforced automatically (see
[Enforcement](#8-enforcement)) — but the checks catch what has already gone wrong, and this
explains what to do instead.

**Contents**

1. [Foundations](#1-foundations) — colour, type
2. [Anatomy of a slide](#2-anatomy-of-a-slide) — the parts every slide has
3. [The two months](#3-the-two-months) — reporting vs data
4. [Elements](#4-elements) — callouts, tables, charts
5. [Deck structure](#5-deck-structure) — front matter, sections, closing
6. [Per-product rules](#6-per-product-rules) — ARS, ICS, MRPC
7. [Adapting to the client's data](#7-adapting-to-the-clients-data)
8. [Enforcement](#8-enforcement) — what runs, and what it blocks
9. [Appendix: ARS slide reference](#appendix-ars-slide-reference)

---

## 1. Foundations

### Colour

Defined once in `build/brand.py`. Never write a hex literal in a builder or chart renderer —
import the name.

| Name | Hex | Used for |
| --- | --- | --- |
| `NAVY` | `#00274C` | Titles, tiles, bars, table headers |
| `ORANGE` | `#F47A29` | The accent: current period, highlighted row, pills, total row |
| `WHITE` | `#FFFFFF` | Text on navy |
| `TICK` | `#5A6670` | Axis ticks, body-text grey |
| `LABEL` | `#CFDBE8` | Light label on navy, neutral bar |
| `ROWALT` | `#EEF2F7` | Alternating table row |
| `GRID` | `#E4EAF1` | Chart gridlines |
| `MUTED` | `#B8C0CA` | Axis spines |
| `HAIRLINE` | `#D9DEE5` | Lightest axis spine |
| `STEEL` | `#7B9BB8` | ARS secondary series |
| `STEEL_SOFT` | `#9DB8CC` | ICS + MRPC secondary (MRPC Platinum) |
| `LIGHT` | `#C9D6E3` | ICS + MRPC tertiary |
| `GOLD` | `#E7A93B` | ARS Gold-tier series |
| `SLATE` | `#5A7590` | MRPC fourth categorical series |

Two greys named `STEEL` exist because ARS and ICS/MRPC drew different ones. They are kept
apart rather than merged, so no chart silently restyles. Checking products highlight in
orange; totals and summary bars are orange.

### Type

Two faces, assigned by role — not by taste.

- **Montserrat** — slide titles and display elements: KPI tiles, callout boxes, pills,
  section chips, badges, tier callouts.
- **Calibri** — everything that reads as prose or detail: subheadings, body text, table
  cells, captions, footnotes, slide numbers.
- **Charts render in Carlito**, the metric-compatible Calibri substitute, so chart text
  matches body text. Renderers call `rpe_env.use_font("Carlito")`, which *raises* if the
  face is missing rather than letting matplotlib silently substitute one.

**Minimum size 16 pt.** Anything below is bumped up. One exception: a genuinely dense
reference table that cannot fit its fixed content at 16 pt (the ICS "2026 New Releases"
grid, ARS "Product Mix"). Those are skipped deliberately and noted in the code.

Fonts are **committed to the repo** (`fonts/`) and embedded in the `.pptx`, so a deck renders
identically on any machine and cannot drift with an OS font install.

**Roles are applied by one post-processor,** `build/restyle_fonts.py`, run last on every
deck in all three programs. Builders should still set sensible fonts at creation, but the
post-processor has the final say. Two things it deliberately does not touch: the Executive
Summit slide, and slide numbers.

---

## 2. Anatomy of a slide

Every data slide carries these, in this order down the page:

| Part | Rule |
| --- | --- |
| **Title** | Montserrat, navy. Slides are identified by title, never by number — numbers shift when a slide is added. |
| **Selection subtitle** | Grey `#5A6670`, 16 pt. States *which population* the slide covers, so the audience knows what they are looking at. Too long? Shorten it — never drop below 16 pt. |
| **Period pill** | Top-right. See [The two months](#3-the-two-months). Must fit its box: reduce the pill font (to ~10 pt) or shorten the label, never overflow into the title. |
| **Body** | Chart, table, or tiles. Fills the horizontal space with balanced white space above and below. |
| **Caption / insight** | Bottom. Auto-fitted so glyphs stay clear of the number and logo band. |
| **Source** | In the **speaker notes**, never on the slide face. |
| **Slide number** | Bottom-left, Calibri 10 pt bold navy, at `0.45" × 7.05"` (box `0.70 × 0.30`). |
| **Logo** | Bottom-right, `11.28" × 6.78"`, `1.70 × 0.54`. |

### Selection on the slide, source in the notes

The **selection** goes on the slide face as the subtitle — the audience needs it. The
**source** (file, tab, dashboard, ODD extract + pull date, period) goes in the speaker
notes. Every slide carries a source line in its notes; this is a hard requirement, because
it is what makes a figure auditable back to its origin.

### Slide numbers and logos

Numbers appear on data slides only. **No number** on: the title slide, the Executive Summit
slide, section dividers, and closing covers (Questions & Discussion, Appendix divider).
Unnumbered slides simply leave a gap in the sequence. When trimming a combined deck to a
standalone one, renumber from the ordinal — never keep the source deck's numbers.

The CSI | Velocity lockup appears on every slide **except** the Executive Summit slide,
which carries its own branding:

- **Data slides** — bottom-right, `11.28, 6.78, 1.70 × 0.54`
- **Section dividers** — top-left on the white rounded card, `0.71, 0.66, 1.90 × 0.60`
- **Title and Questions & Discussion** — centred lockup on the centred white card

---

## 3. The two months

A deck reports two different months and they are easy to invert. Getting this wrong is one
of the most common defects in this pipeline.

| | Which month | Where it appears |
| --- | --- | --- |
| **Reporting month** | The month the report is **presented** | Title slide: "Executive Review • {Month YYYY}" |
| **Data month** | The month the **figures** run through | Period pills, PTD figures, captions |

The reporting month comes from the period tag (`ARS_PERIOD`/`RPE_PERIOD`, or the `<yyyy.mm>`
in the output filename). It is **never** taken from the clock: that is right only while a
deck is built in the month it ships, and silently wrong on every rebuild after.

**Period pill formats — one convention across all products:**

- `PTD · {date}` — the middot separates the label from the period.
- **VIP-current slides** (live data, current through the pull) use the pull date with the
  day: `PTD · July 13, 2026`.
- **Workbook PTD slides** use the workbook month: `PTD · June 2026`.
- A genuine analysis window that is *not* program-to-date keeps its own descriptive label
  ("Trailing 12 months …", "3-mo avg · …"). Do not relabel a window as PTD.

Carry both dates in the data sheet: `data_pull` (YYYY-MM-DD) and `workbook_month`.

---

## 4. Elements

### Callout boxes and tiles

- Text centred **vertically and horizontally**. The number in Montserrat.
- On a Key Metrics slide, the single most important metric is the **large** callout
  (MRPC → Active Enrollments); secondary totals sit in the smaller tiles.
- A two-line label needs a taller box — ≥ ~1.55" with a ~0.7" label box. The 1.4" default
  clips the second line.

**Drop shadow — every callout carries the same one.** Soft, low-opacity, straight down:
`blurRad ≈ 63500 EMU (~5 pt)`, `dist ≈ 38100 EMU (~3 pt)`, `dir = 5400000` (90°, down),
black at ~28% alpha. Applies to number callouts, tier callouts, KPI tiles, agenda badges and
the top-right period pills. Not to chart backdrops.

### Pie and donut charts

**Flat — no drop shadow.** No `patheffects` wedge shadows, no OOXML picture shadow. Donuts
read clean and consistent this way. (Shadows still apply to callouts, tiles, badges and
pills — the rule above.)

### Tables

Navy header row · **orange total row** · white grid lines · alternating white / light-grey
data rows · Calibri cells.

Dense tables **fit to slide first**. A smaller font is allowed only once the element is
already at maximum size and still will not fit.

### Charts

- Fill the available **horizontal space**; keep balanced white space above and below.
- **No label collisions.** Labels never sit on top of bars, lines or connectors. Where a
  value label crosses a reference line, give it a white halo so the line passes behind it.
- **Consistent font sizes** across labels, legends and ticks.
- Leave clear separation between the subtitle and the top of the chart.
- **Render at the slide box's aspect ratio.** The `DIM` entry in `charts_gen.py` must match
  the picture box on the slide, or the image stretches.
- Dense axes may drop to ~13 pt and rotate rather than collide — chart labels are scaled
  images, not deck text, so they are exempt from the 16 pt floor.
- **Thin a crowded axis by striding**, and keep the newest period labelled — but never place
  two ticks adjacent when the stride is wider than one.

### Reading at distance

These decks are shown on a TV or projector and read from **15+ feet**. When in doubt, make
the element bigger, not the font smaller.

---

## 5. Deck structure

### Front matter

1. **Title slide** — product name(s) in white; client name, "Executive Review" and the
   reporting month in orange. **List only the products in this build**, not every product
   the client has. No slide number.
2. **Executive Summit slide** — see below.
3. **Agenda** — numbered list, **all badges orange**. A standalone deck lists that product's
   sections; a combined deck lists each product section. An unused row is **removed**, not
   blanked: an empty numbered row reads as a section that failed to render.

### Executive Summit slide

**Every results deck carries it**, immediately after the title slide. It is a separate
delivery from the monthly reviews — a Summit runs a couple of times a year and only for
attendees — but the slide ships in every deck.

**This slide is exempt from the font policy.** It keeps its own dense typography
(Montserrat / SemiBold / Medium at 9–14 pt, tight two-column spacing). `restyle_fonts.py`
and every size-floor pass skip it. Never restyle or 16 pt-floor it, and it carries no CSI
corner logo and no slide number.

The asset is replaced by hand before each Summit. `build/summit_slide.py` reads the date off
the slide itself rather than hardcoding it, and warns when the slide still names a Summit
that has passed.

### Section dividers

All three product dividers use one identical layout:

- Full-bleed navy; **white rounded logo card top-left** (`0.55, 0.5, 2.22 × 0.92`) with the
  lockup at `0.71, 0.66, 1.9 × 0.6`.
- **Product name centred**, Montserrat bold 52 pt, box `0.7, 2.25, 11.9 × 2.4`.
- **Benefits line below**, Montserrat bold 22 pt **orange**, centred, box `0.7, 5.05, 11.9 × 0.9`:
  ARS "Mailings · Debit Card · Reg E" · ICS "Referrals · Account Performance · Revenue" ·
  MRPC "Enrollments · Retention · Revenue".

No slide number on dividers.

### Closing

Every deck ends with a **Contact Us** slide (navy contact card: name, role, phone, email,
orange role line), preceded by **Questions & Discussion**.

- **With an appendix (ARS):** Questions & Discussion → **Contact Us → Appendix**.
- **Without one (ICS / MRPC):** Questions & Discussion → Contact Us last.

Builders add both idempotently — skipped if the template already carries them.

---

## 6. Per-product rules

### ARS

**Product Mix & ARS Eligibility is required on every ARS deck**, immediately before Program
Overview. It reads the ODD for open accounts, eligibility, product mix and the
business/personal split. Dense-table exception to the 16 pt floor.

**Excluded Accounts** follows it and explains **open accounts only**. A closed or
charged-off account is outside ARS by definition and explains nothing; a dormant account is
a different question. Reasons are product code, no debit card, and an account-level
remainder. Closed and dormant counts are named in the source note, so the scope is stated
rather than implied. The tiles reconcile: open = open-and-excluded + open-and-eligible.

**Take-rate by branch — Personal and Business must be the same size and layout.** Both come
from one renderer (`chart_lib.take_branch_chart`, fixed 1383 × 540, y-axis 0–105, bar width
0.66) so they cannot drift. **Only the colours differ: Personal = orange bars / navy dashed
average; Business = navy bars / orange dashed average.** No embedded chart title — the
caption labels it.

**Debit Usage Segmentation by Swipe Tier** must include **% Accounts, % Swipes, % Spend,
% NSFs**.

**Monthly Summary — Last 12 Months** — navy bars with an orange dashed average. The average
label sits **just above** the line, not centred on it.

### ICS

Builds from a per-client JSON (`Inputs/VIP Data/ICS/<id>-<Name>/`). Referral data comes from
the VIP dashboard; performance, revenue and financial detail from the Invitation Checking
workbook.

**Financial detail ships only when the workbook is for the deck's own period.** On a
mismatch the section falls back to the referrals-only shape and the divider drops to
"Referrals". Never carry an older workbook's figures forward, re-date them, or zero them.

**Comparisons slide** — pill layout: left column **orange capsules** (Velocity Clients'
Average), centre the metric label, right **navy capsules** ({Client} Data). Velocity averages
are program-wide constants.

> **Both sides of a row use one precision.** Average Life of Account prints one decimal on
> both — "6.9 Years" against "7.0 Years", never "6.9" against "7.05". A row whose purpose is
> comparing a pair must not print the pair two ways.

Column headers grow **upward** for a long client name rather than shrinking — the font floor
would undo a shrink anyway.

**Per-account-per-month metrics.** When a workbook tab is cohort data by opening month
reporting **revenue only** (Monthly Detail), per-account-per-month = cohort revenue ÷
accounts opened ÷ months open — not ÷ cumulative accounts. Do not label revenue as spend.

Referral bars use navy with the last complete month orange (partial month hatched steel).
The goal line is dropped when the network goal dwarfs current volume.

### MRPC

Builds from a per-client JSON (`Inputs/VIP Data/MRPC/<id>-<Name>/`). Never hand-edit charts.

**Tier colours — the chart bars and the tier callouts MATCH:**

| Tier | Colour |
| --- | --- |
| **Gold** | `ORANGE #F47A29` |
| **Platinum** | `STEEL_SOFT #9DB8CC` (grey) |
| **Business** | `NAVY #00274C` |

Platinum callout text renders navy for contrast on the grey card. Business appears only when
`meta.has_business` is true.

**Enrollments by Month** — one stacked chart with every tier the client has. The partial
current month is hatched and faded. A callout carries the last **complete** month's totals
per tier.

**Time-series bar charts** (Enrollment Performance, Retention, Revenue by Month) — navy bars
with the last completed month in orange. A line overlaid on the bars (Enrollments,
Still-Active) is **navy with a white casing** — `_overlay_line()` in `mrpc_charts_gen.py`,
one definition for all of them. Value labels sitting over the bars are cased the same way
(`_cased_text()`), because a month with no accounts has no bar behind its label, and they
clear the marker by a fixed offset in **points**, not a fraction of the axis maximum.

> **A mark is never drawn in the canvas colour.** These lines used to be plain white, on the
> assumption they never left a navy bar. They do — every segment crossing the gap between two
> bars, and any point above a bar top, rendered white-on-white. The Retention line was
> invisible for its whole length on the 2026.08 decks, markers only, and so was its legend
> swatch; the Enrollments labels lost five real values on Capital Bank 1502 the same way. A
> casing removes the dependency on what sits behind a mark — picking a different flat colour
> only moves the failure. `tests/test_chart_colors.py` fails the build if a renderer draws a
> line or label white again.

White stays correct where the ground is guaranteed: marker faces with a coloured ring, the
pad that masks a line behind a label, the separator between stacked segments, and text on an
opaque navy or orange patch. The rule is about marks on the open canvas.

**Cancellations by Reason** renders as **ranked horizontal bars** (top reason navy, rest
steel, % at bar ends, no legend). A donut plus legend scales poorly across 4–8 reasons.

**Card Portfolio** has its own slide before Key Metrics: a donut by card type — Platinum
($14.95/mo), Gold ($9.95/mo), Business Platinum ($19.95/mo), Multiple Cards. KPI tiles: total
cards billed, monthly billing, average fee per account, Platinum share. The cross-sale %
also appears on Key Metrics.

A channel count that VIP will not surface is recorded as `null`, **not zero** — the bar draws
at zero and is labelled `n/a`. A genuine zero is labelled `0`. Those are different facts.

---

## 7. Adapting to the client's data

Client data varies widely. Every build adapts **by rule**, never ad hoc.

| | Rule |
| --- | --- |
| **Branch charts** | Show the largest 6–8 branches, with eligibility floors: ≥40 eligible accounts (personal), ≥15 (new-account), ≥5 (business). Fewer than 3 qualify → show all that do and say so in the caption. |
| **Product mix** | Top 8 products by open accounts plus an "All other products (N)" roll-up. Never a table that grows with the client's product count. |
| **Monthly series** | Fixed windows (12-mo summary, 36-mo swipes & spend, 24-mo growth). Shorter history renders the months available (min 6) and the pill states the real span. Never pad or extrapolate. |
| **MRPC tiers** | Clients run 2–5 tiers. Key Metrics Tier Mix rows size dynamically so 3 tiers fill the card and 5 still fit. |
| **Reg E vocabulary** | Any non-blank value that does not map to Opt In / Opt Out / Default is surfaced in the pack's `flags`. **Ask before mapping — do not guess.** |
| **ICS partial data** | A null workbook section is a missing input, not a zero. Build referrals-only or stop and name what is missing. Never render a slide from null. |

**Missing source data is stated, never zeroed.** If a field the deck needs is absent, the
builder writes a plain sentence saying so and flags it. It does not render 0%, does not draw
an empty chart, and does not drop the slide.

---

## 8. Enforcement

Most of this guide is checked automatically. The checks run in this order:

| Stage | What it does |
| --- | --- |
| `slide_geometry.py` | Per-title geometry contract — donut heights, chart tops, caption clearance. Run by the builders before layout fit. |
| `fit_layout.py` | Clears bottom captions from the number/logo band, clamps off-slide shapes, sets slide numbers to 10 pt. |
| `restyle_fonts.py` | Assigns font roles and the 16 pt floor. **Run last.** |
| `validate_deck.py` | The pre-ship lint gate. **0 FAIL to ship.** |
| `qa_all.py` | The full gate: unit tests, every template, package integrity, a render smoke test, and layout-drift detection. |

**Three rules learned the hard way:**

1. **Box geometry is not glyph geometry.** Text overflows its box silently. The validator
   estimates rendered glyph runs, font-size- and alignment-aware.
2. **LibreOffice renders are not PowerPoint.** PowerPoint's autofit shrink is invisible in a
   LibreOffice render, so never trust nominal font sizes on template-inherited frames.
3. **python-pptx is not the file.** It enumerates a duplicated slide reference as two real
   slides. Seven decks once passed at 0 FAIL while being unopenable. Package integrity and
   "does it actually open" are checked directly.

**When a defect gets through the gate, add the check that would have caught it.** Fixing only
the instance guarantees the next one ships too.

**Fix the builder, never the deck.** A layout or number defect is corrected in the builder,
the geometry contract or the template shell, then rebuilt. Editing a delivered deck fixes one
client and leaves the rest broken.

---

## Appendix: ARS slide reference

By title, in order. Section dividers in **bold**.

**Front matter** — *Title* · *About the Summit* · *Agenda*

**Account Revenue Solution®**
*Product Mix & ARS Eligibility* (donut + tables) · *Excluded Accounts* (reason bars + excluded
products) · *Program Overview* (narrative + 5 KPI tiles) · *ARS Financial Performance*
(profitability callout + tiles) · *ARS Lift Matrix* (MM) **or** *Monthly Summary — Last 12
Months* (SM) · *Debit Usage Segmentation by Swipe Tier* (9-column table) · *Average Ticket by
Swipe Segment* (two bar panels)

**Mailing Insights**
*Mailing Response Summary* · *Mailing Response Ranking by Tier* · *ARS Response — {mailer}* ·
*ARS Response — {mailer} Movement* · *Transaction Increase Over the Ask* · *Sustained
Respondent Activity by Mailing* · *Responder Activity: Before vs After (Mean)* · *… by Offer*

**Debit Card Review**
*12-Month Eligible Take Rate — Personal* (orange bars) · *— Business* (navy bars) ·
*12-Month Take Rate by Branch* · *Overall Debit Swipes & Spend* · *NSF/OD Activity Over Time*

**Reg E Review**
*Reg E Opt-In — All Personal Accounts* · *— Opened in Last 12 Months* · *Reg E Opt-In by
Branch — Last 12 Months* · *Reg E Opt-In by Account Vintage*

Product Mix, Excluded Accounts and Reg E Opt-In by Branch are **inserted by the builder**,
not carried in the template shell — so they appear in a built deck but not in
`ars_template.pptx`.

**Closing** — *ARS Key Takeaways* · *Questions & Discussion* · *Contact Us*

**Appendix**
*Program Reach* · *Depth of Engagement* · *Responder Age Profile* · *Who Responds — Balance
Profile* · **New Account Profile** · *New Accounts by Product* · *New Checking Balances vs.
Existing Book* · *Debit Card Penetration — New vs. Book* · *Debit Card Usage* ·
*New-Account Debit Adoption* · *New Account Profile — Summary* · *Account Growth* ·
*Account Retention — Survival by Tenure* · *First-Year Closure by Early Debit Use*

### Geometry contract

Enforced by `build/slide_geometry.py`, keyed by title:

- **Reg E donut slides** — donut ends above its legend (≤ 2.85").
- **Reg E Vintage / First-Year Closure / ARS Response Movement** — chart top ≥ 1.75", below
  the two-line subtitle.
- **Who Responds** — caption starts below the chart.
- **Program Reach** — chart fills its space, balanced against the right rail.
- **Account Growth / Account Retention** — identical chart geometry.

Other products: the ICS revenue donut is flat; the ICS Financial Summary callout block starts
at 1.85"; MRPC Key Metrics Tier Mix rows size to fill the card.
