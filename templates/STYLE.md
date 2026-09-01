# Deck Style Guide — all products (ARS / ICS / MRPC)

The single source of truth for how every client deck looks, so settings carry forward
across all builds and products. Referenced by `CLAUDE.md`. Based on Aaron's ARS build
notes (2026-07-10).

## Fonts (updated 2026-07-13 — role split)
Two fonts, assigned by role (Aaron, 2026-07-13 — reversed the brief "Montserrat everywhere"):

- **Montserrat** — **headings (slide titles)** and **callout boxes** (KPI/number tiles,
  pills, section chips, badges, tier callouts). Display elements only.
- **Calibri** — **subheadings**, **body text boxes**, **table cells**, captions,
  footnotes, page numbers. Anything that reads as prose or data detail.
- **Chart labels / legends / ticks** follow the body font: render charts in **Carlito**
  (the metric-compatible Calibri substitute available in the sandbox / on the client's
  machine). Chart renderers set `rcParams["font.family"]="Carlito"`.

**One shared enforcement.** Names are assigned by role in a single post-processor,
`build/restyle_fonts.py`, run **last** on every finished deck (all three programs) so the
policy is identical across ARS / ICS / MRPC. It infers role from the shape: AUTO_SHAPE with
text → Montserrat (callout/chip/badge); title placeholder → Montserrat; any other text box →
Montserrat if its largest run is ≥ 22 pt (or inherited-size text at the very top), else
Calibri; tables → Calibri. Build scripts should still set sensible fonts at creation, but the
post-processor has final say. **Always run it after building.**

- **Minimum font size: 16 pt.** The post-processor (and each pipeline's size pass) bumps any
  explicit run below 16 up to 16. **Exception:** a genuinely dense reference/data table that
  cannot fit its fixed content at 16 pt may stay smaller (e.g. the ICS "2026 New Releases"
  4-quarter grid) — skipped by the post-processor and noted.
- **Build-environment note:** **Montserrat** lives at `fonts/Montserrat/` and in `~/.fonts`
  (Cowork sandbox); **Carlito** ships with the sandbox (`crosextra`). Chart renderers register
  Carlito and floor tuned label sizes for readability (dense monthly x-axes may drop to ~13 pt
  and rotate rather than collide — chart labels are scaled images, not deck text).
- **Embed the fonts in the .pptx** so the deck renders on any machine (OOXML
  `p:embeddedFontLst`; python-pptx has no native embed).

## Date / period pills (top-right)
- **One format across all products: `PTD · {date}`** (Aaron, 2026-07-13). The middot `·`
  separates the "PTD" label from the period.
- **VIP-current slides** (data pulled live, current through the pull date) use the pull date
  with the day: **"PTD · {Month D, YYYY}"** (e.g. "PTD · July 13, 2026").
- **Workbook PTD slides** (figures program-to-date from a workbook ending at the last
  complete month) use the workbook month: **"PTD · {Workbook Month}"** (e.g. "PTD · June
  2026"), NOT the report/generation month.
- Genuine analysis-window pills that are NOT program-to-date (e.g. ARS "Trailing 12
  months …", "3-mo avg · …") keep their own descriptive label — do not relabel a window as PTD.
- Carry both dates in the data sheet: `data_pull` (YYYY-MM-DD) and `workbook_month`.

## Comparisons / benchmark slide
- Client-vs-Velocity comparison uses the **pill layout** (modeled on the CSI/Velocity ICS
  Review template): left column = **orange capsule pills** (Velocity Clients' Average),
  center = metric label, right = **navy capsule pills** ({Client} Data). Optional footnote
  (e.g. Non-ICS close rate). Velocity averages are program-wide benchmark constants.

## Per-account-per-month (cohort) metrics
- When a workbook tab is **cohort data by opening month** reporting **revenue only**
  (ICS "Monthly Detail"), per-account-per-month = **cohort revenue ÷ accounts opened ÷
  months open** (not ÷ cumulative accounts). Do not label revenue as spend or item counts.

## Executive Summit slide (all results decks)
- **Every results deck (ARS / ICS / MRPC) carries the Velocity Solutions Executive Summit
  slide immediately after the title slide.** Pristine asset: `build/assets/summit_slide.pptx`
  (trimmed from the Sugar River v20 base). Insert with
  `build/summit_slide.py:insert_summit_after_title(prs)` before the page-number pass; the
  builds already do this. ARS clones it from the base template.
- **This slide is exempt from the font policy.** It keeps its own dense typography
  (Montserrat / Montserrat SemiBold / Montserrat Medium at 9–14 pt, tight two-column
  spacing). `build/restyle_fonts.py` and each pipeline's size-floor pass skip it — never
  restyle or 16 pt-floor it.

## Closing slides (Aaron, 2026-07-24)
- **Agenda** after the section divider (numbered list; **all badges orange** — Aaron, 2026-07-13).
- **Every deck ends with a Contact Us slide** (navy contact card: name, role, phone, email,
  orange role line) and carries a **Questions & Discussion slide at the end of the primary
  material**. Builders add both idempotently (skipped if the template already carries them).
- **Decks with an Appendix (ARS):** order is Questions & Discussion → **Contact Us → Appendix**
  (Aaron 2026-07-24: the Appendix follows the Contact slide). Decks without an appendix
  (ICS / MRPC): Questions & Discussion → Contact Us last.

## Title slide
- **List only the products included in this build** — not every product the client has.
  (ARS+MRPC request → only ARS and MRPC on the cover.)
- Product name(s) in **white**.
- Client name, "Executive Review", and the reporting **month + year** in **orange**.
- **Reporting month = the month the report is generated, not the data month.**
  (Filename still uses the data/period month, e.g. `2026.07`.)

## Agenda
- Standalone product deck → lists that product's sections.
- Combined (ARS+ICS+MRPC) → lists each product section.

## Callout boxes
- Text centered **vertically and horizontally**.
- **Drop shadow — all callout boxes carry the same subtle shadow.** Soft, low-opacity,
  straight down: outer shadow `blurRad≈63500 EMU (~5pt)`, `dist≈38100 EMU (~3pt)`,
  `dir=5400000 (90°, down)`, black at `alpha≈28%`. Applied uniformly to every number
  callout and tier callout **and to the upper-right period/date pills** ("As of {date}",
  "PTD · {month}", "{month} Data") — Aaron, 2026-07-13, reversing the earlier chip
  exclusion. Not applied to chart backdrops. The MRPC builder (`build_mrpc_gen.add_shadow`)
  applies this; ICS `shadow()`, `product_mix_slide._shadow` match it.

## Pie / donut charts
- **Pie and donut charts are flat — no drop shadow** (Aaron, 2026-07-15, reversing the
  earlier raised-wedge treatment). Render wedges with no shadow so donuts read clean and
  consistent across all products. Do **not** apply `patheffects` wedge shadows or an OOXML
  picture `outerShdw` to donut/pie charts. (Drop shadows still apply to callout boxes, KPI/
  number tiles, agenda badges, and the period/date pills — see "Callout boxes".)
- **Callout boxes with a two-line label** (e.g. ARS "Overall Debit Swipes & Spend" and
  "NSF/OD Activity Over Time" right-rail callouts) must be **tall enough for the wrapped
  label** — ≥ ~1.55" box height with a ~0.7" label text box; the 1.4" default clips the
  second line (Aaron, 2026-07-13).
- On the **Key Metrics** slide the single most important metric is the **large** callout
  (e.g. MRPC → **Active Enrollments**); secondary totals (e.g. PTD enrollments) sit in the
  smaller upper tiles.

## Structure
- **Product Mix & ARS Eligibility slide** — **required on every ARS deck**, placed
  **immediately before Program Overview** (matches the Marine combined reference). Built by
  `build/product_mix_slide.py:add_product_mix_slide(prs, <clientid>_ODDD.zip, assets,
  before_title="Program Overview", renumber=True)` — reads the ODD for open accounts,
  ARS-eligibility (`<Mon><yy> Elig`), product mix, and business/personal split; extract the
  CSI/Velocity logo from an existing content slide into `assets/logo.png` first. Runs as the
  final ARS step (after build_gen/b, before restyle). It's a dense-table exception to the
  16 pt floor. `build_gen`-built decks that predated this (Austin 1075, True Sky 1676,
  CoastLife 1705) were back-filled 2026-07-13; combined ARS+ICS decks inherit it from the
  ARS section.

## Colors
`NAVY #00274C` · `ORANGE #F47A29` · `STEEL #9DB8CC` · `LIGHT #C9D6E3` · `TICK #5A6670`
· `GREY #B8C0CA`. Checking products highlight in orange; totals/summary bars in orange.

## Tables (all products)
Navy header row · **orange total row** · white grid lines · alternating white / light-gray
data rows · Calibri cells (`style_tables.py` applies this — keep it as the standard).
- **Debit Usage Segmentation by Swipe Tier** must include **% Accounts, % Swipes,
  % Spend, % NSFs** columns (as on the Marine FCU sample).

## Charts (all products)
- Fill the available **horizontal space**; keep balanced white space **above and below**.
- **No label collisions** — labels never sit on top of / under bars, lines, or connectors.
- **Consistent font sizes** across labels, legends, ticks. Calibri (Carlito) throughout.
- Leave clear separation between the **subheading and the chart** (don't crowd the top).
- **Render a chart at its slide box's aspect ratio** — the letterbox `DIM` (in `charts_gen.py`)
  must match the picture box on the slide, or the image stretches. (New Accounts by Product
  `image21` was 3.44:1 in a 2.13:1 box → stretched upward; fixed 2026-07-24 to 1660×780.)

## Debit take-rate by-branch charts (ARS, Aaron 2026-07-24)
The **Personal** (slide) and **Business** (slide) take-rate-by-branch charts must be the
**same size and layout** — both rendered by the shared `build/ars_pipeline/chart_lib.py`
`take_branch_chart()` (fixed 1383×540, y-axis 0–105, bar width 0.66, navy value labels), so
they can't drift. **Only the colors differ: Personal = orange bars / navy dashed average;
Business = navy bars / orange dashed average.** No embedded chart title (the caption below
labels it).

## Known per-chart fixes (from the Austin 1075 review, 2026-07-10)
Charts live in `build/ars_pipeline/charts_gen.py` unless noted.
- **New Accounts by Product** — "Individual HSA" renders as "Individual **H S A**"
  (acronym/title-case bug in `kickoff_lib.smart_titlecase` / ACR handling); fix so HSA
  stays intact. Switch font to Calibri.
- **First-Year Closure by Early Debit Use** — the 73% / 27% branch labels collide with the
  connector lines; offset labels off the lines.
- **Responder Activity: Before vs After (Mean)** and **(Median)** — widen both panels to
  fill the space; set label fonts to **size 12**.
- **12-Month Eligible Take Rate — Personal** — remove the on-chart "Avg %" label (it's in
  the callout).
- **12-Month Take Rate by Branch** — chart too close to the subheading; branch/axis fonts
  too small — add top margin, enlarge fonts.
- **Overall Debit Swipes & Spend** — make the chart taller.
- **NSF/OD Activity Over Time** — make the chart taller.
- **Reg E Opt-In by Account Vintage** — legend too close to the subheading; add spacing.


## Selection / methodology text
The **selection** (which population/accounts the slide covers) goes **on the slide face**,
as the subheading under the title, so the audience sees exactly what they are looking at.
The **data source(s)** — source file/tab, dashboard, ODD extract + pull date, and period —
go in the **speaker notes** (see CLAUDE.md "Data sources in slide notes"). Every slide still
carries a source line in its notes; the slide face shows the title, the selection subheading,
the chart, and the insight/callout. (Updated 2026-07-15, Aaron — selection on the slide,
source in the notes; reverses the earlier selection-in-notes rule.)

## Callout tiles
Big-number callout tiles: the number in **Montserrat**, text centered **v + h**. Match the
Key Metrics tile style consistently across slides (e.g. the Revenue slide's 2025 / Life-of-
Program tiles use the same treatment).

## Slide numbers (Aaron, 2026-07-24)
- **Font: Calibri 10 pt, bold, navy (`#00274C`) — every slide number, no exceptions.** They
  must all be the same size; do not let the 16 pt font-floor touch them (the ARS builder
  applies numbers in a final pass that runs *after* `restyle_fonts.py`).
- **Position: bottom-left, `left 0.45"`, `top 7.05"` (box `0.70" × 0.30"`)** on a 13.33×7.5 slide.
- **No slide number on: the title slide, the Executive Summit slide, and section-heading /
  closing cover slides** (Reg E Review, Mailing Insights, Appendix, Questions & Discussion, etc.).
- Numbered slides carry their ordinal (slide index + 1); unnumbered slides simply leave a gap.
- When trimming a combined deck to a standalone deck, renumber from the ordinal — don't keep
  the source deck's numbers.

## Logos (Aaron, 2026-07-24)
The CSI | Velocity Solutions lockup (`assets/logo.png`, transparent PNG) appears on **every
slide except the Executive Summit slide**, at one fixed position/size per slide type:
- **Data slides — bottom-right, identical on every slide: `left 11.28"`, `top 6.78"`, `1.70" × 0.54"`.**
- **Section-heading slides — top-left, identical on every one: `left 0.71"`, `top 0.66"`, `1.90" × 0.60"`**
  (sits on the slide's top-left white rounded card).
- **Title slide and closing cover (Questions & Discussion)** keep their **centered** lockup on
  the centered white card — left as-is.
- **Executive Summit slide: no CSI lockup** (it carries its own Summit branding; drop the
  corner CSI logo).
The ARS builder normalizes all of this in the final branding pass (re-inserts a known-good
logo so a broken image relationship can never blank a slide's logo, as happened on a data slide).

## MRPC enrollment chart
Single stacked chart with all tiers the client has: **Gold = orange, Platinum = gray,
Business = navy**. Partial (current, incomplete) month is hatched + faded. Add a callout
with the **last complete month** totals per tier + total. Include Business only if the
client has business enrollments.

The three tier **callout boxes** (right of the chart) are colored **Gold = navy,
Platinum = orange, Business = gray** — the Business box uses the same gray as the
Platinum bars in the chart. For consumer-only clients the Business box is dropped.

## MRPC bar charts (standard format)
On time-series bar charts (Enrollment Performance, Retention, Revenue by Month) the bars
are **navy with the last completed month in orange**. Any line overlaid on the bars
(Enrollments, Still-Active) is drawn **navy with a white casing** — `_overlay_line()` in
`mrpc_charts_gen.py`, one definition for all of them. Value labels that sit over the bars
(the Enrollments counts) are cased the same way — `_cased_text()` — because a month with no
accounts has no bar behind its label, and they clear the marker by a fixed offset in POINTS,
not by a fraction of the axis maximum.

**A mark is never drawn in the canvas color** (Aaron, 2026-09-01). These lines used to be
plain white on the assumption that they never left a navy bar. They do: every segment
crossing the gap between two bars, and any point that rises above a bar top, rendered
white-on-white. The MRPC Retention line was invisible for its whole length — markers only —
on the 2026.08 decks, and so was its legend swatch; the Enrollments labels lost five real
values on Capital Bank 1502 the same way. A casing removes the dependency on what happens to
sit behind a given mark; picking a different flat color only moves the failure.
`tests/test_chart_colors.py` fails the build if a renderer draws a line or a label white again.

White stays correct where the ground is guaranteed: marker faces with a colored ring, the
white pad that masks a line behind a label, the separator between stacked segments, and text
on an opaque navy/orange patch. The rule is about marks on the open canvas.

## MRPC Card Portfolio slide
Card billing has its own slide (before Key Metrics): a **donut by card type** — Platinum
($14.95/mo), Gold ($9.95/mo), Business Platinum ($19.95/mo), and **Multiple Cards**
(accounts holding more than one card). KPI tiles: total cards billed, monthly card
billing, avg fee/account, Platinum share. The **cross-sale %** (multi-card ÷ total) also
appears as a callout on the Key Metrics slide.

## ICS pipeline (data-driven)
ICS decks build from a per-client JSON via `build/ics_pipeline/` (`ics_charts_gen.py` +
`build_ics_gen.py`, static education slides from `templates/ics_template.pptx`). Referral data from the
VIP ICS Referral dashboard; performance/revenue/financial from the Invitation Checking
workbook. The **Monthly Detail** tab is cohort data by opening month and reports **revenue
only** — per-account-per-month = cohort revenue ÷ accounts opened ÷ months open. Referral
bars use the standard navy / last-complete-month-orange format (partial month hatched
steel); the goal line is dropped when the network goal dwarfs current volume. See the
`ics-deck` subagent for the schema and run steps.

## MRPC pipeline (data-driven)
MRPC decks build from a per-client JSON data sheet via `build/mrpc_pipeline/`
(`mrpc_charts_gen.py` renders charts, `build_mrpc_gen.py` builds the deck from
`mrpc_template.pptx`). VIP-pulled numbers go into `Inputs/VIP Data/MRPC/<id>-<Name>/<id>_mrpc.json` — never hand-edit
charts. See the `mrpc-deck` subagent for the schema and run steps.
## MRPC enrollment tier colors (Aaron, 2026-07-24 — callouts MATCH the bars)
**Gold = orange, Platinum = GRAY (steel #9DB8CC), Business = NAVY — in the chart bars AND
the tier callout boxes.** The Platinum callout text renders navy for contrast on the gray
card. (Supersedes the 2026-07-16 note that had Platinum/Business swapped.)


On the MRPC **Enrollments by Month** slide the tier colors are fixed and the
stacked-bar chart and the Gold/Platinum/Business callout tiles MUST match:

- **Gold — orange** (`#F47A29`)
- **Platinum — navy** (`#00274C`)
- **Business — steel** (`#9DB8CC`)

Applies to the chart series/legend (`mrpc_charts_gen.py`: `GOLDC`/`PLATC`/`BIZC`)
and the callout fills (`build_mrpc_gen.py` tier list). Business appears only when
`meta.has_business` is true.

## Reading at distance & per-slide handling (Aaron, 2026-07-24)

These decks are shown on a TV/projector and read from **15+ feet**. Rules:

- **Identify slides by TITLE, not slide number** — numbers shift when slides are added or
  removed. All per-slide handling below is keyed by title (the builder still swaps by find-
  string; when practical prefer title-based lookups over fixed `S[index]`).
- **Selection subtitles:** grey `#5A6670`, **16 pt**. If a subtitle is too long for its line,
  **shorten it / use abbreviations** rather than drop below 16 pt.
- **Dense tables & charts:** size the element as large as the slide allows (**fit to slide**).
  A **smaller font is allowed only when the element is already maxed** and still won't fit.
- **Top-right date/period pills:** must fit their box — if the label is long, **reduce the pill
  font** (to ~10 pt) or shorten the label; never let it overflow or collide with the title.
- **Charts:** the chart image aspect (`DIM` in `charts_gen.py`) must match its slide picture
  box or it stretches. Personal take-rate = orange bars, Business = navy bars, identical size.
- Every callout/tile/pill carries the standard drop shadow; donuts/pies stay flat.
- **No shape runs off the slide or collides with the slide number/logo.** The shared
  `build/fit_layout.py` pass (run by every builder before save) clears bottom footnotes
  from the number/logo, clamps off-slide shapes, and sets all slide numbers to 10 pt;
  `validation/validate_deck.py` FAILS the build if any collision/overflow remains.

### ARS deck — per-slide reference (by title)

**Front matter:** *Title* (centered lockup, no number) · *About the Summit* (own typography;
no CSI corner logo, no number) · *Agenda* (section list, orange badges).

**ARS section** — divider *Account Revenue Solution®*:
- *Product Mix & ARS Eligibility* — donut + two tables; dense-table exception to the 16 pt
  floor; built by `product_mix_slide.py`, placed before Program Overview.
- *Program Overview* — "<client> has run…" narrative + 5 KPI tiles; PTD pill.
- *ARS Financial Performance* — large PTD-Profitability callout + revenue/profit tiles.
- *ARS Lift Matrix* (MM) **or** *Monthly Summary — Last 12 Months* (SM) — lift table + revenue
  segmentation (MM) or a 12-month incremental-revenue bar (SM); window pill (shrink to fit).
- *Debit Usage Segmentation by Swipe Tier* — 9-column table (% Accounts/Swipes/Spend/NSFs); "Avg" pill.
- *Average Ticket by Swipe Segment* — two bar panels side by side.

**Mailing Insights** — divider: *Mailing Response Summary* (table) · *Mailing Response Ranking
by Tier* (stacked bars) · *ARS Response — <mailer>* (responders-by-tier bars) · *ARS Response —
<mailer> Movement* (first/improved/same/declined) · *Transaction Increase Over the Ask*
(histogram + tiles) · *Sustained Respondent Activity by Mailing* (bars) · *Responder Activity:
Before vs After (Mean)* and *(Median)* (paired bar panels).

**Debit Card Review** — divider: *12-Month Eligible Take Rate — Personal* (orange bars) &
*— Business* (navy bars), same size via `chart_lib` · *12-Month Take Rate by Branch* (wide
table) · *Overall Debit Swipes & Spend* (combo + tiles) · *NSF/OD Activity Over Time* (combo + tiles).

**Reg E Review** — divider: *Reg E Opt-In — All Personal Accounts* · *— Opened in Last 12
Months* (donut + branch bars) · *— by Account Vintage* (bars + line).

*ARS Key Takeaways* — 3-column summary + orange opportunity bar.
*Questions & Discussion* — closer (centered lockup, no number).
*Contact Us* — navy contact cards. **Contact precedes the Appendix.**

**Appendix** — divider *Appendix* → *Program Reach — Cumulative Responders* · *Depth of
Engagement — Repeat Responders* · *Responder Age Profile* · *Who Responds — Balance Profile* ·
divider *New Account Profile* · *New Accounts by Product* · *New Checking Balances vs. Existing
Book* · *Debit Card Penetration — New vs. Book* · *Debit Card Usage — New vs. Existing Book* ·
*New-Account Debit Adoption — Swipe Segmentation* · *New Account Profile — Summary* · *Account
Growth — Openings vs. Closures* · *Account Retention — Survival by Tenure* · *First-Year Closure
by Early Debit Use*.

## Per-slide geometry contract (Aaron, 2026-07-24)
Enforced by `build/ars_pipeline/slide_geometry.py` (run by the ARS builder before
`fit_layout`; runnable standalone on a template). By slide TITLE:
- **Reg E Opt-In donut slides** — the donut ends above its legend (donut ≤2.85").
- **Reg E Vintage / First-Year Closure / ARS Response Movement** — chart top ≥1.75"
  (below the two-line selection subtitle).
- **Who Responds** — the caption starts below the chart bottom.
- **Program Reach** — chart fills its space: (1.2, 1.8, 8.3 × 4.58) balanced against the right rail.
- **Account Growth & Account Retention** — identical chart geometry (1.0, 1.75, 8.4 × 4.38).
Other products: ICS revenue donut is FLAT (no ring shadow); ICS Financial Summary callout
block top = 1.85 (balances the selection text); Power of Referrals flavor text = 28 pt;
MRPC Key Metrics **Tier Mix** rows are dynamically sized to fill the card (3+ tiers,
`min(18, max(11, (1.45/rows)*72*0.62))` pt), label on top, cross-sale as the footer line.
`validate_deck.py` flags any text box overlapping a chart image as REVIEW (letterboxed
whitespace can make small overlaps benign — check visually).

## Data-size adaptation rules (Aaron, 2026-07-24 — from the client-deck survey)

Client data varies widely; every build adapts by rule, never ad hoc:

- **ARS ODD size.** Small/typical ODDs (<10 MB zip) pass the `.zip` straight through the
  pipeline. Large books (e.g. 271k-row Austin 1075) use the 2-stage `metrics_gen`
  checkpoint (`MG_DUMP`) and pre-extract the CSV once, passing the `.csv` to the builder.
- **Branch charts.** Take-rate/opt-in by branch shows the **largest 6–8 branches** with
  eligibility floors (≥40 eligible accounts personal, ≥15 new-account, ≥5 business). If
  fewer than 3 branches qualify, show all qualifying branches and say so in the caption.
- **Product mix.** Top 8 products by open accounts + an **"All other products (N)"** roll-up
  row — never a table that grows with the client's product count.
- **Monthly series.** Fixed windows (12-mo summary, 36-mo swipes & spend, 24-mo growth).
  Clients with shorter history render the months available (min 6) and the window pill
  states the actual span — never pad or extrapolate.
- **Reg E vocabulary.** Any non-blank value that doesn't map to `Opt In / Opt Out / Default`
  is surfaced in the pack `flags` — **ask before mapping** (Sugar River 1038 precedent:
  Failed to Respond/Revoked → Default; Exempt/Ineligible → excluded).
- **MRPC tiers.** Clients run 2–5 card tiers. The Key Metrics **Tier Mix** rows are
  dynamically sized (`min(18, max(11, (1.45/rows)·72·0.62))` pt) so 3 tiers fill the card
  and 5 still fit. Enrollment charts stack every tier the client has (Gold orange,
  Platinum gray, Business navy).
- **ICS partial data.** Several clients' JSON carries **null workbook sections** (VIP
  referrals only, no workbook refresh yet). Build ICS **only when both** the workbook data
  and VIP referral data are present; a null section is a missing-input error — stop and
  name the missing input. Never render a slide from null (no empty charts, no phantom 0%).
- **Captions & tables.** Bottom captions are auto-fitted by `fit_layout` (estimated line
  count keeps glyphs above the number band; width stops before right-rail tiles). Dense
  tables fit-to-slide first; a smaller font only when the element is already maxed.

## Slide-check additions (Aaron, 2026-07-24, round 2)
- **ARS Reg E donut slides** — left column stacks: donut (≤2.85", ends 4.45") → legend rows
  (4.60"+, 0.36" apart) → caption (5.85", est-lines fit). No legend/caption collisions.
- **ARS Product Mix** — the source line sits at the **bottom of the slide, centered**.
- **ARS take-rate slides (Personal/Business)** — chart horizontally centered; caption
  centered beneath it (both centered on the slide).
- **ARS Overall Debit Swipes & Spend + NSF/OD Activity** — equal-size charts, taller
  (target h 5.15", aspect-preserving; DIM 1740×1007 both).
- **MRPC Retention** — **Cancellations by Reason renders as RANKED HORIZONTAL BARS**
  (top reason navy, rest steel, % at bar ends, no legend) — a donut+legend scales poorly
  with 4–8 reasons; bars fit any reason count with no label collisions (Aaron 2026-07-24).
- **MRPC Revenue slides** — chart (0.4, 1.5, 7.55 × 4.85): taller, right edge clears the
  rail text.
- **MRPC Card Portfolio** — the billing donut is **not** boxed in a callout; pie at
  (0.35, 3.3, 6.2 × 2.69) clear of the Platinum Share card.
- Validator: caption-overflow check is **font-size- and alignment-aware** (estimates glyph
  runs; FAILs only when estimated text reaches the number/logo corners).

## Product section dividers — one canonical layout (Aaron, 2026-07-24)
All three product dividers (ARS / ICS / MRPC) use the identical layout:
- Full-bleed navy background; **white rounded logo card top-left** (0.55, 0.5, 2.22 × 0.92)
  with the CSI|Velocity lockup at (0.71, 0.66, 1.9 × 0.6).
- **Product name centered**, Montserrat bold 52 pt, box (0.7, 2.25, 11.9 × 2.4), middle-anchored.
- **Program benefits line below**, Montserrat bold 22 pt **orange**, centered, box (0.7, 5.05, 11.9 × 0.9):
  ARS "Program Performance Review" · ICS "Referrals · Account Performance · Revenue" ·
  MRPC "Enrollments · Retention · Revenue".
No slide number on dividers. The ICS builder generates this layout; the MRPC/ARS dividers are baked
in their templates.
