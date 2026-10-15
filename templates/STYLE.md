# Deck Style Guide

The single source of truth for how every client-facing deck looks: the monthly
Executive Reviews (ARS, ICS, MRPC, CashPlease — single-product or combined), the
standalone CashPlease module, and the ILS review prep slides. Referenced by
`CLAUDE.md`; read it before building any deck. Writing rules (banned words, the
+/-2% band for describing movement, no unsupported claims) live in `CLAUDE.md`,
not here.

Every rule below names WHERE it is enforced. A rule with no enforcement is a wish,
and this guide has carried wishes before — the ICS shadow it said "matched" the
standard was two points lighter for six weeks. `tests/test_style_doc.py` checks
that every repo path cited here exists.

## 1. What this guide covers

| Deck family | Built by | Shell | Gate |
| --- | --- | --- | --- |
| **Executive Review** — ARS, ICS, MRPC single-product decks and the combined deck | `build/ars_pipeline/build_ars_gen.py`, `build/ics_pipeline/build_ics_gen.py`, `build/mrpc_pipeline/build_mrpc_gen.py`, `build/assemble_combined.py` | `templates/ars_template.pptx`, `templates/ics_template.pptx`, `templates/mrpc_template.pptx` | `validation/qa_all.py` (unit suite, `validation/validate_deck.py`, layout drift, render) |
| **CashPlease** — a 10-slide single-product deck, or the same five slides as a section of the combined deck | `C:\Projects\CashPlease\build\build_cp_gen.py` (staged to move into `build/cashplease_pipeline/`) | `templates/cashplease_template.pptx` (a 10-slide Union Financial demo; the builder keeps its shell slides and rebuilds the five CashPlease slides) | `validation/validate_deck.py`; `C:\Projects\CashPlease\build\cp_qa.py` until it is retired (its text-over-text rule is now in the validator) |
| **ILS review prep slides** — recap, matrix updates, program detail, fee schedule, matrix parameters/overrides | the `ils-prep-deck` skill: `~/.claude/skills/ils-prep-deck/reference/build_deck.py` | none; blank python-pptx, later inserted into the consultant's `.pptm` | render with `reference/render.ps1` and look — the RPE validator does not run on it (§9) |
| **Executive Summit one-pager** — hand-built, per attendee, never scheduled | `build/ars_pipeline/build_ars_onepager.py` | 8.5 x 11 print | deliberately none of the deck gates (it is not a 13.33 x 7.5 deck) |

All four use one palette and one pair of typefaces. The Executive Review and
CashPlease decks share one slide anatomy (§4). The ILS prep slides use the same
palette on a different anatomy because they land inside someone else's deck.

## 2. Enforcement map

| Rule | Enforced by | A miss is caught by |
| --- | --- | --- |
| Palette and type roles | `build/brand.py` — the ONE declaration; builders and chart renderers import it | `tests/test_brand.py` |
| Font by role, 16 pt floor | `build/restyle_fonts.py`, run last on every finished deck | `validation/validate_deck.py` overflow rules (a Montserrat label wider than its box) |
| Measured text width (never eyeballed) | `build/textfit.py` against the bundled `fonts/` | `single_line_overflow_findings` |
| Slide numbers, number/logo clearance, off-slide shapes | `build/fit_layout.py`, run by every builder before save | `geometry_findings` FAILs any survivor |
| Per-title chart/caption geometry | `build/slide_geometry.py`, run before `fit_layout` | `tests/test_slide_geometry.py`; layout drift in `validation/layout_baseline.json` |
| Callout / pill / tile / table primitives, the one drop shadow | `build/shapes.py` | `text_collision_findings` (text drawn over text) |
| Date phrases, spans, `MMM'YY` axis labels | `build/periods.py` | `period_findings`; `tests/test_periods.py` |
| A chart mark is never the canvas color | renderers | `tests/test_chart_colors.py` reads the renderers |
| Chart aspect matches its picture box | each renderer's `DIM` / `_letterbox` | look — a stretched PNG is invisible to a linter |
| Executive Summit slide, untouched | `build/summit_slide.py` | `tests/test_golden_deck.py` (every deck carries it) |
| Title lists only included products; agenda rows removed, never blanked | `build/assemble_combined.py` | `tests/test_assemble_combined.py` |
| One value per named measure | `build/figures.py` sidecar | `figure_sidecar_findings` |
| Package opens; slide parts referenced once | never delete-then-add a slide | `package_findings`; the `qa_all` render step |

`validation/qa_all.py` runs all of it. Run it after ANY change to `templates/`,
`build/` or `validation/`, and run it from the repo `.venv` (the Windows Store
python has no pytest; the gate now finds the venv itself and says loudly when the
unit suite could not run).

## 3. Palette and type

**Colors** — every value is a name in `build/brand.py`; never re-declare a hex.

| Name | Hex | Role |
| --- | --- | --- |
| `NAVY` | `#00274C` | titles, tiles, bars, table headers, slide numbers |
| `ORANGE` | `#F47A29` | the current period, the highlighted row, pills, totals, agenda badges |
| `TICK` | `#5A6670` | axis ticks, selection subtitles, body grey |
| `ROWALT` | `#EEF2F7` | alternating table rows |
| `GRID` / `HAIRLINE` / `MUTED` | `#E4EAF1` / `#D9DEE5` / `#B8C0CA` | gridlines, lightest spine, axis spine |
| `LABEL` / `LIGHT` | `#CFDBE8` / `#C9D6E3` | light label on navy; ICS + MRPC tertiary series |
| `STEEL` | `#7B9BB8` | ARS secondary series (ticket chart) |
| `STEEL_SOFT` | `#9DB8CC` | ICS + MRPC secondary series, the MRPC Platinum tier, the partial-month bar |
| `TEAL` | `#0D9488` | a line drawn over navy bars (MRPC Enrollments, Still Active) |
| `GOLD` / `SLATE` / `PEACH` / `TILE` | `#E7A93B` / `#5A7590` / `#F6B284` / `#ECF0F4` | ARS Gold tier; MRPC 4th series; one-pager section text; light card fill |

`STEEL` and `STEEL_SOFT` are both kept on purpose: ARS drew one and ICS/MRPC the
other, and collapsing them would silently restyle a chart. Which one wins is a
decision to record here, not a refactor.

**Type** — two faces, assigned by role (Aaron, 2026-07-13):

- **Montserrat** (`brand.HEAD`): slide titles, callouts, KPI tiles, pills, chips,
  badges, tier callouts, divider text. Display only.
- **Calibri** (`brand.BODY`): subheadings, body text, table cells, captions,
  footnotes, slide numbers. Charts render in **Carlito** (`brand.CHART_FONT`), the
  metric-compatible face, so chart text matches the body.
- `build/restyle_fonts.py` assigns the names by shape: an autoshape with text is
  a callout (Montserrat); a title placeholder is a heading; any other text box is
  a heading if its largest run is >= 22 pt or it is inherited-size text at the very
  top, else body; 12+ words is always body; tables are body.
- **Minimum 16 pt** for every explicit run — these decks are read from 15 feet.
  Exceptions, all in `restyle_fonts.py`: slides titled "2026 New Releases",
  "Product Mix", "Program Results by Month Opened", "Referred Accounts by Product"
  (dense tables that cannot fit at 16); MRPC decks (a deliberate 10-15 pt
  hierarchy); the Executive Summit slide (never touched); and the 12 pt label under
  the figure in the KPI tiles of "Product Mix & ARS Eligibility" and "Excluded
  Accounts", which carry the same callout subtext at the same size
  (`shapes.tile(small_label=True)`, `restyle_fonts.SMALL_TILE_LABEL`). A subtitle that is too
  long is shortened, not shrunk.
- Both faces are **embedded** in the shell (`p:embeddedFontLst`) so a deck renders
  the same on any machine; `rpe_env.use_font` RAISES rather than let matplotlib
  substitute.

## 4. Slide anatomy (13.333 x 7.5")

The Executive Review and CashPlease decks share this exactly.

| Element | Geometry | Style |
| --- | --- | --- |
| **Title** | (0.50, 0.28) 0.9" tall, ~9.6–12.3" wide | Montserrat bold 26–30 pt navy, top-anchored |
| **Selection subtitle** | (0.50, 1.12), full width | Calibri 16 pt `TICK` grey — WHAT population the slide covers, on the slide face |
| **Period pill** | upper right (ARS `shapes.pill`: 10.5, 0.34, 2.35 x 0.5; ICS 9.9, 0.34, 2.95 x 0.62) | orange capsule, white Montserrat bold, drop shadow; must fit — shorten the label or drop to ~10 pt, never overflow |
| **Content band** | ~1.6" to 6.9" | charts left, tile rail right where there is one |
| **Bottom caption** | starts >= 5.8" | `fit_layout` parks it above 7.00" by estimated line count |
| **Slide number** | (0.45, 7.05, 0.70 x 0.30) | Calibri 10 pt bold navy — every numbered slide identical |
| **Logo, data slides** | (11.28, 6.78, 1.70 x 0.54) | the CSI \| Velocity lockup, `build/assets/logo.png` |
| **Logo, dividers** | (0.71, 0.66, 1.90 x 0.60) on a white rounded card (0.55, 0.50, 2.22 x 0.92) | |

**Numbered:** content slides only, sequentially, from the ordinal. **Not numbered:**
the title, the Executive Summit, every full-bleed divider and closing cover
(`fit_layout` strips them). A trimmed or combined deck renumbers from scratch
(`assemble_combined.renumber`). **No logo** on the Summit slide; the title and
Questions covers keep their centered lockup.

**Selection on the slide, source in the notes.** The selection is the subtitle.
The data source — file, tab, dashboard, extract + pull stamp, period — goes in the
speaker notes of every data slide, naming THIS client (`source_note_findings` FAILs
a missing Source line or another client's provenance).

## 5. The shell

Every single-product deck carries its own shell; the combiner keeps exactly one of
each (`assemble_combined.section_slides` drops the rest).

- **Title slide (2026-10-02, `build/cover_divider.py`).** Full-bleed navy, left-aligned:
  the client's own logo (`Inputs/Logos/`, trimmed) on a white card top-left; the reporting
  month at 84 pt Montserrat ExtraBold white; under it one text frame with the client name
  (32 pt orange) and "Executive Review  •  <month>" (18 pt) — the line the combiner and
  validator read; the included products as outline chips (16 pt, wrapping to a second row
  for four); the lockup bottom-right on a white card. **Lists only the products in this
  build** — the combiner replaces the chips (`set_cover_products`). The first chip is the
  slide's title. Every builder draws it; the shells still carry the old centered cover and
  are redrawn at build time.
- **The two months.** The **reporting month** is when the deck is presented and
  appears once, on the title slide; it comes from the period tag (`ARS_PERIOD` /
  `RPE_PERIOD`, or the `<yyyy.mm>` in the output filename) and **never from the
  clock** — that is right only while a deck is built in the month it ships and
  silently wrong on every rebuild after. The **data month** is what the figures run
  through and appears in the pills, PTD figures and captions. Inverting them is one
  of the commonest defects in this pipeline; the data sheet carries both
  (`data_pull`, `workbook_month`).
- **Executive Summit slide**, immediately after the title, on every results deck.
  Pristine asset `summit_slide.pptx` under `build/assets/` (gitignored — pipeline
  `Inputs/Summit/` wins when present); `build/summit_slide.py` inserts it. Own dense
  typography (Montserrat 9–14 pt); no font floor, no restyle, no logo, no number.
- **Agenda.** Numbered rows, **orange** badge circles, section name plus one detail
  line, one row per product section plus Questions. A row for an absent product is
  REMOVED, not blanked (an empty numbered row reads as a section that failed). Up to
  four rows keep the template pitch; five re-space (1.60 / 2.54 / 3.48 / 4.41 / 5.35).
  A referrals-only ICS section gets the referrals-only detail line.
- **Section divider (2026-10-02, `build/cover_divider.py`)** — one layout for all four
  products and the ARS sub-sections: full-bleed navy, left-aligned; "SECTION" kicker
  (16 pt, `STEEL_SOFT`); the section name at 52 pt Montserrat ExtraBold white (stepping
  down to 36 when it will not fit one line); the benefits line 18 pt orange. ARS
  "Mailings · Debit Card · Reg E" · ICS "Referrals · Account Performance · Revenue"
  (referrals-only: "Referrals") · MRPC "Enrollments · Retention · Revenue" · CashPlease
  "Loan Volume · Portfolio Status · Peer Comparison". A **program** divider carries up to
  three headline figures at 40 pt with 16 pt labels (ARS: revenue to fees, profit PTD,
  latest response · ICS: referrals PTD, YTD, previous month vs goal · MRPC: enrollments
  PTD, last complete month, trailing 12 · CashPlease: loans booked, principal, loans per
  1,000 DDAs). In a **combined deck only**, a progress track along the bottom names every
  section (ARS · ICS · CASHPLEASE · MRPC) with the current one in orange —
  `assemble_combined.set_divider_tracks`; a standalone deck draws none. The lockup sits
  top-right. No number. The ARS builder redraws the shell's dividers in place; ICS, MRPC
  and CashPlease draw theirs. Nothing below the 16 pt floor and no shadow.
- **Questions & Discussion** ends the primary material; **Contact Us** (navy contact
  card: name, role, phone, email) follows it. The card is **the client's managing CSM**
  (Aaron, 2026-09-16), from `CSM Contacts.csv` via `rpe_env.csm_contact`; the line slots
  live in `build/shapes.py` (`contact_card_lines`, `fill_contact_card` for a shell's card).
  No phone on file: no phone line, and the other three are re-spaced. No CSM, or no row:
  the build stops — the card never names another CSM. **The ARS Appendix follows Contact**
  (Aaron, 2026-07-24). Decks without ARS have no appendix — never synthesise one.
- **Combined order:** shell (title, Summit, agenda) → ARS → ICS → MRPC → CashPlease
  sections → Questions → Contact → ARS Appendix. The first program present supplies
  the shell (`BASE_PRECEDENCE`: ARS, ICS, CP, MRPC — MRPC last because its deck has
  no agenda or Summit). Slides are only ever ADDED and reordered, never deleted.

## 6. Components

**Callouts, KPI tiles, pills, badges** (`build/shapes.py`). Text centered
vertically and horizontally; value in Montserrat, label in Calibri. Every one of
them — number tiles, tier callouts, agenda badges, the period pill — carries the
ONE drop shadow: `outerShdw blurRad=63500 dist=38100 dir=5400000`, black at
alpha 28%. `shapes.shadow` is the only definition; the ARS, ICS and MRPC builders
import it. Not on chart backdrops. A callout with a two-line label is >= ~1.55"
tall so the second line is not clipped.

**Tables** (`shapes.add_table`). Navy header row, white bold text; alternating
white / `ROWALT` rows; the highlighted or total row orange; Calibri cells; white
grid lines. The ARS Debit Usage Segmentation table carries % Accounts, % Swipes,
% Spend and % NSFs. Dense tables fit to slide first; a smaller font only when the
element is already maxed.

**Charts** (all renderers).

- Fill the horizontal space; balanced white space above and below; clear
  separation from the subtitle; no label collisions; consistent label sizes; Carlito.
  Where a value label crosses a reference line, give it a white halo so the line
  passes behind it. Thin a crowded axis by striding and keep the newest period
  labelled, but never leave two ticks adjacent when the stride is wider than one.
  Dense axes may drop to ~13 pt and rotate: chart labels are scaled images, exempt
  from the 16 pt floor.
- **Render at the picture box's aspect.** `DIM` in `build/ars_pipeline/charts_gen.py`
  (and each renderer's letterbox size) must match the slide box or the PNG stretches.
- **Month labels: `MMM'YY`, angled 45°, `ha="right"`** — `periods.mon_yy` /
  `periods.axis_months` (Aaron, 2026-09-01). Three formats were in service and the
  ICS quarter panels had thrown the year away. **Enforced at render time**
  (2026-09-08): every chart module calls `periods.install_month_axis_guard()`, and a
  month reaching either axis in any other format raises `MonthAxisError` and fails
  the build. It has to be checked where the label is DRAWN — the five ARS charts that
  never adopted the format built their labels by string-slicing, so they called no
  formatter for a lint to find, and shipped "Feb24", "Sep '23", "Sep 2023" and "Jun"
  (year discarded) for a week. Horizontal charts count: `c_ranking` puts its months
  down the y-axis, un-rotated but still `MMM'YY`.
- **Time series:** navy bars, the last COMPLETE month orange, the partial month
  hatched `STEEL_SOFT` at alpha 0.42 with `//`, white edge, value label in `TICK`,
  annotated with the date it runs through.
- **A mark is never drawn in the canvas color** (Aaron, 2026-09-01). A line over
  navy bars is `TEAL`: 4.02:1 on navy, 3.74:1 on white — clear of WCAG 3:1 on both
  grounds, which no other flat color manages, and which a white casing achieved at
  the cost of looks. Value labels sit ABOVE the bar, navy. White stays right where the
  ground is guaranteed: marker faces with a colored ring, the pad masking a line
  behind a label, separators between stacked segments, text on an opaque patch.
- **Pies and donuts are flat** — no wedge shadow, no picture `outerShdw`
  (Aaron, 2026-07-15). Callouts keep theirs.
- **Branch charts — volume in the bars, rate on the line** (Aaron, 2026-09-08). All
  four (personal take rate, business take rate, both Reg E) render through
  `chart_lib.branch_chart`: accounts set the bar height, the rate rides above on its
  own axis, and the count sits under the axis beneath its branch number, and **the rate labels sit in one band
  above the line**, not each above its own marker — riding the marker put them in the
  gap between the line and the bars, which closes exactly where a branch is both large
  and typical. A rate drawn
  without its denominator is not readable — a branch with 15 accounts stood as tall as
  one with 900 — and it hid the finding that matters most often: True Sky's largest
  branch is also its worst on Reg E opt-in. **No program-average line**: that figure is
  the donut (Reg E) or the tile (take rate) beside the chart, so a dashed rule was a
  third rendering of a number already twice on the slide, and the four captions no
  longer name one. The rate axis never prints a tick above 100%. Colours: orange bars /
  navy line (personal, Reg E), navy bars / **teal** line (business — a mark is never
  drawn in the canvas colour).
- **Branch charts** show the largest 12 branches above the eligibility floors
  (>= 40 eligible personal, >= 15 new-account, >= 5 business), **selected by accounts
  and ranked by rate, best to worst**; fewer than 3 qualifying → show all and say so
  in the caption. `chart_lib.BRANCH_CAP` is the cap and the renderer raises above it.
- **Comparisons / benchmark slide:** orange capsule pills = Velocity clients'
  average (left), navy capsule pills = this client (right), metric label between.

## 7. Program specifics

### ARS
- **Product Mix & ARS Eligibility** precedes Program Overview on every ARS deck
  (`build/ars_pipeline/product_mix_slide.py`): donut + two tables, top 8 products
  plus an "All other products (N)" roll-up, dense-table exception, source line
  bottom-center. **Excluded Accounts** follows it and explains **open accounts
  only** — a closed or charged-off account is outside ARS by definition and
  explains nothing; reasons are product code, no debit card and an account-level
  remainder, and the tiles reconcile (open = open-and-excluded + open-and-eligible).
  Product Mix, Excluded Accounts and Reg E Opt-In by Branch are **inserted by the
  builder** — they appear in a built deck but not in `templates/ars_template.pptx`.
- **Monthly Summary — Last 12 Months** (SM path): navy bars with an orange dashed
  average whose label sits just above the line, not centered on it.
- **ARS Revenue Lift Matrix** (MM path, `build/ars_pipeline/render_lift.py`, 2026-09-16): the
  matrix is a heat grid, starting tier down and tier now across, one `COLD_RAMP` navy ramp; an
  impossible move is a dash, never a blank or $0. Beside it, monthly value per card account by tier
  as bars with each tier's share of card accounts, the largest share in orange. The caption's worked
  example (1-5 → 11-15) is the cell outlined in orange — `render_lift.example_move` is the one
  definition both use. This slide carries **no selection line** (Aaron, 2026-09-16) — the exception to
  "selection on the slide": the chart titles inside the picture carry it.
- **Take-rate by branch, Personal and Business:** identical size and layout from
  `build/ars_pipeline/chart_lib.py`; Personal = orange bars / navy dashed average,
  Business = navy bars / orange dashed average; no embedded title. Since 2026-09-17
  the chart runs full width (0.5, 2.60, 12.3 x 3.70) under shorter tiles (1.30-2.35), the
  caption centered at 6.36, and the selection sentence lives in the notes (Aaron).
- **Overall Debit Swipes & Spend** and **NSF/OD Activity** charts are equal and
  taller, never wider than the tile rail.
- **Reg E donut slides** (All Personal, Opened in Last 12 Months), since 2026-09-17: donut,
  legend and opt-in sentence in one band (1.28-3.08), the branch chart full width beneath
  (0.5, 3.20, 12.3 x 3.10), caption centered at 6.36, selection sentence in the notes.
- **Branch charts carry branch NAMES** (Aaron, 2026-09-17) from `Inputs/Branch Names/`, shortened
  (`chart_lib.short_branch_name`: no parenthetical code, no trailing Branch/Office), wrapped to two
  lines and sized to the bar slot; a branch with no name keeps its number, and a client whose
  ODD ids mostly have no name keeps numbers throughout.
- **Average Ticket** and its caption derive their verbs from the figures (the
  +/-2% band in `CLAUDE.md`); the chart title follows (`build/ars_pipeline/ticket_chart.py`).
- Pills: "{Month YYYY} Data" for a snapshot slide; window pills ("Trailing 12
  months …") keep their own label — never relabel a window as PTD.
- Per-slide reference by title, front to back: Title · About the Summit · Agenda ·
  divider · Product Mix & ARS Eligibility · Excluded Accounts · Program Overview ·
  ARS Financial Performance · ARS Revenue Lift Matrix (MM) or Monthly Summary — Last 12
  Months (SM) · Debit Usage Segmentation by Swipe Tier · Average Ticket by Swipe
  Segment · Mailing Insights (divider, Response Summary, Ranking by Tier, ARS
  Response — <mailer> and Movement, Transaction Increase Over the Ask, Sustained
  Respondent Activity, Responder Activity Mean and Median) · Debit Card Review
  (divider, Take Rate Personal and Business, Take Rate by Branch, Swipes & Spend,
  NSF/OD) · Reg E Review (divider, All Personal Accounts, Opened in Last 12 Months,
  Reg E Opt-In by Branch — Last 12 Months, by Account Vintage) · ARS Key Takeaways · Questions ·
  Contact · Appendix (divider, Program Reach, Depth of Engagement, Responder Age
  Profile, Who Responds, New Account Profile divider and six profile slides,
  Account Growth, Account Retention, First-Year Closure).

### ICS
- Data-driven from the client JSON (`rpe_env.resolve_client_json`): referral slides
  from VIP, financial slides from the workbook, static education slides selected
  from the shell **by title**. **Workbook slides ship only when the workbook is
  for the deck's own period**; otherwise the referrals-only shape (`CLAUDE.md`).
- **Date pills:** VIP-current slides "PTD · {Month D, YYYY}"; workbook slides
  "PTD · {Workbook Month}" — the workbook's month, never the report month.
- Monthly Detail is cohort revenue by opening month: per-account-per-month =
  cohort revenue ÷ accounts opened ÷ months open. Life-of-account metrics read the
  **Last 12 Months** row. The Velocity 12-month close rate is a constant (6.7%).
- **Both sides of a comparison row use one precision** — "6.9 Years" against
  "7.0 Years", never "6.9" against "7.05". Column headers grow upward for a long
  client name rather than shrinking (the font floor would undo a shrink anyway).
- Referral bars: house time-series treatment; the goal line is dropped when the
  network goal dwarfs current volume. A "program high" is claimed only when the
  window proves it.
- **Direct Mail New Accounts** (2026-09-16) follows Results by Branch when the sheet
  carries a `direct_mail` block with accounts: house time-series chart left
  (`ics_charts_gen.c_direct_mail_trend`, canvas at the 8.05 x 4.95" box's aspect), two
  callouts (program-to-date, latest complete month) and a top-3 branch table right, pill
  "PTD · {last month}". Never added to referral figures; the notes say so.
- ICS revenue donut flat; Financial Summary callout block top = 1.85"; Power of
  Referrals flavor text 28 pt; billed-expense labels measured with `textfit`.

### MRPC
- **Enrollments by Month:** one stacked chart of every tier the client has —
  **Gold orange, Platinum `STEEL_SOFT`, Business navy** — with the tier callouts
  the SAME colors (Platinum text navy on the grey card). Business appears only when
  `meta.has_business`. Partial month hatched; a callout carries the last complete
  month's totals.
- **Enrollment Performance, Retention, Revenue by Month:** navy bars, last complete
  month orange, `TEAL` overlay lines, counts above the bars; drawn from the sheet's
  own `new_accounts` and `goal` — never a derived denominator.
- **Cancellations by Reason:** ranked horizontal bars (top reason navy, rest steel,
  % at bar ends, no legend) — a donut scales poorly with 4–8 reasons.
- **Program to Date** and **Current Program Status** (replaced Card Portfolio and Key
  Metrics, 2026-10-02): three navy tiles (36 pt figure, 16 pt label), a chart at lower left
  in a 6.3 x 3.2 box — a flat tier donut, or status bars with inactive in steel — and a navy
  callout at lower right (orange heading, white 16 pt lines). Selection line under the
  title names the weekly's date.
- MRPC keeps its 10–15 pt hierarchy; `restyle_fonts` sets names only.

### CashPlease
- **Five slides, built once, shipped two ways:** divider · CashPlease Program
  Overview · Loan Volume by Month · Loan Portfolio by Status · Peer Comparison. Alone
  they sit in a 10-slide single-product deck (shell + five + Questions + Contact);
  in a combined deck they are the section, via `--cashplease`. A client whose
  slides ship inside a combined deck does not also get a module.
- **Program Settings (2026-09-14):** a client with
  `Inputs/Product Settings/<id>_cp_settings.json` gets a sixth slide after the Overview —
  two tables (Loan terms · Eligibility & controls, `add_table` at 12 pt) over a one-line
  program strip (site, launch dates, processing, online banking). Production values only:
  recommendations belong to the ops meeting, and the record's internal fields (Loan
  Notes, contract, CSM, pricing) reach neither the slide nor its notes, which ship in
  the file. Pill "As of {Mon D, YYYY}" — the app's data-updated date, short month so it
  holds one line. A blank field reads "Not recorded". No record, no slide; the build
  lists those clients.
- Style comes from this repo's shared layer (`brand`, `shapes`, `periods`,
  `fit_layout`), so a CashPlease slide matches the slide beside it. Titles are
  Montserrat 30 pt at (0.6, 0.38); the selection line at (0.62, 1.06).
- **Pill:** "PTD · {Month D, YYYY}" — the weekly workbook's generation date, the
  VIP-current form, on every content slide. The cover and Questions slide carry the
  month. **Always the newest workbook** (by filename stamp, not mtime), so the
  section may be dated later than the ARS/ICS/MRPC sections beside it, and is never
  re-dated to match.
- Loan Volume by Month uses the house time-series treatment, partial month as a
  hatched bar annotated with its through-date. Never render the workbook's
  "Percentage of Active Accounts with Loans"; the rate is loans per 1,000 DDAs, and a
  slide carrying both cohorts (73-tab rollup, 51-client DDA rate) names both.
- Name the client — never "this client". Footnotes stay under two lines; a longer
  one is pushed up by `fit_layout` into the content (the defect behind
  `text_collision_findings`).

## 8. Data-size adaptation

Client data varies widely; every build adapts by rule, never ad hoc.

- **ODD size:** < 10 MB zips go straight through; large books use the two-stage
  `metrics_gen` checkpoint and a pre-extracted CSV.
- **Monthly series:** fixed windows (12-month summary, 36-month swipes & spend,
  24-month growth); shorter histories render what exists (min 6) and the pill states
  the actual span — never pad or extrapolate.
- **Reg E vocabulary:** an unmapped value is surfaced in the pack's `flags` — ask
  before mapping (`CLAUDE.md`).
- **MRPC tiers:** 2–5; the chart stacks all of them, the Tier Mix rows size themselves.
- **ICS partial data:** a null workbook section is a missing input — stop and name
  it (or build `--referrals-only` deliberately). Never render a slide from null.
- **Captions and tables:** bottom captions are auto-fitted; dense tables fit to
  slide first.

## 9. ILS review prep slides

Built by the `ils-prep-deck` skill for the annual ILS analysis review and inserted
into the consultant's macro-enabled review deck, so they follow the palette and
type above on the ILS template's anatomy — not §4:

- **Header:** title Montserrat 26 pt navy at (0.50, 0.30), subtitle Calibri 16 pt
  `TICK` beneath, the dual-brand lockup (`velocity-csi-lockup.png` from
  `Inputs/Logos/`) top-right at (10.98, 0.36) 1.85" wide, then a 0.05" orange rule
  at 1.26". One logo per slide: the slides are re-pointed at the deck's empty layout
  so the layout's own Velocity mark is not inherited.
- **Section bars:** navy rounded bars 0.46" tall, white Montserrat label left,
  `PEACH` (#F6B284) label right-aligned.
- **Cards and tables:** card grey `TILE` (#ECF0F4) for non-highlight cards and
  alternating rows; one orange highlight card (the maximum limit); table body ink
  `#3F3F3F` (the ILS template's, not a palette entry); negatives in orange.
- **Footer:** the ILS template's teal bar (`#1B7B8C` — the consultant deck's color,
  deliberately NOT `brand.TEAL`) at 7.36" and its 10 pt "Confidential and proprietary
  information" line, which is exempt from the floor. No RPE slide number, no
  bottom-right lockup: the host deck supplies its own furniture.
- **Type floor 16 pt** with the same dense-table exception, computed by `fit_rows`
  (a table that will not fit at 16 drops as far as 7.5). Trend chips shorten their
  label rather than shrink. No highlighting is carried from the matrix workbook.
- **Verify by rendering** (`reference/render.ps1`) and looking; the RPE validator
  is not run on these slides.

## 10. Per-slide geometry contract

`build/slide_geometry.py`, keyed by TITLE (never slide index), applied by every
builder before `fit_layout`. Today every rule is an ARS title: Overall Debit
Swipes / NSF/OD Activity (taller, not wider); 12-Month Eligible Take Rate
(full-width chart, short tiles, selection in notes); Product Mix (source bottom-center); Reg E Opt-In (top band + full-width chart); Reg E by
Account Vintage / First-Year Closure / ARS Response Movement (chart top >= 1.75");
Responder Activity: Before vs After, both slides (chart full width, 12.3 wide,
centered, top 2.0, height from the image's aspect and at most 4.0"; Aaron, 2026-10-15,
"both charts could be wider"); Transaction Increase (caption 1.45, 6.02, 8.4 x 0.95; chart <= 4.1" centered
between); Who Responds (caption below the chart); Program Reach (1.2, 1.8,
8.3 x 4.58); Account Growth and Account Retention (1.0, 1.75, 8.4 x 4.38). An ICS or
MRPC layout fix goes in the same file — one contract, not one commit per deck.

## 11. Decisions and reversals

| Date | Decision |
| --- | --- |
| 2026-07-13 | Fonts by role (reversed "Montserrat everywhere"); one pill format `PTD · {date}`; agenda badges all orange; shadows on pills too |
| 2026-07-15 | Pies and donuts flat; selection on the slide face, source in the notes (reversed selection-in-notes) |
| 2026-07-24 | Slide number 10 pt at (0.45, 7.05); logo positions fixed; Appendix after Contact; one divider layout; take-rate charts identical; Cancellations by Reason as ranked bars; MRPC tier colors match between chart and callouts (Platinum grey, Business navy — superseding a swapped 07-16 note); identify slides by title |
| 2026-08-27 | Referrals-only ICS builds; combined decks assembled, never blended |
| 2026-08-28 | ICS workbook slides only for the deck's own period |
| 2026-08-29 | Build from the shell, never from a client deck; shared layer at `build/` root |
| 2026-09-01 | `MMM'YY` on every axis; lines over navy bars are `TEAL` (a white casing was tried the same day and rejected on looks); MRPC enrollment counts above the bars; CashPlease is the fourth product |
| 2026-09-02 | CashPlease ships WITH ICS or another RPE product, never inserted into the ILS deck; one shadow definition (ICS 26% → 28%); text-over-text collisions FAIL the gate |
| 2026-10-02 | Cover and section dividers redrawn left-aligned by `build/cover_divider.py` (client logo, month at 84 pt, product chips; dividers carry the section's figures and, combined, a progress track); the rest of the redesign proposal (`docs/STYLE-PROPOSAL-2026-10-02.md`) is still a proposal |
