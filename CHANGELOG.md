# Changelog

Behavior changes to the deck pipelines. The point of this file is that a
reversal like the 2026-08-20 one below should be findable without reading an
80KB source file.

Record corrections and changes (Aaron, 2026-09-01): anything that changes a
number on a client-facing slide, changes where a number is sourced from, changes
what a slide claims, or changes what a slide RENDERS. A fix that moves no figure
still belongs here — the MRPC retention line below moved no figure and could not
be seen on any deck that carried it. Judging an entry by whether a number moved
is how a correction goes unrecorded.

Format: newest first, dated, with the reason — not just the change.

---

## Unreleased

### 2026-09-02 — CashPlease gets its own shell

`templates/cashplease_template.pptx`: a 10-slide Union Financial demo (cover, Summit,
one-row agenda, divider, the four CashPlease content slides, Questions, Contact),
materialized by running `build_cp_gen.py` on a synthetic pack for client 999 with
invented figures and a dummy source filename. Until now the CashPlease builder
started from `ars_template.pptx` as a bare shell and stripped 42 slides and 33 media
files on every build, and the CashPlease look had no template of record to diff
against. The shell now goes through the gate like the other three, and the layout
baseline carries it. `build_all_cp.py` points at it. Verified: the dummy pack and
1734 Altamaha both rebuild from the new shell at 0 FAIL, and an ICS-CP deck
assembles from the shells.

**No client-facing figure moves, nothing renders differently.** The five CashPlease
slides are built from the pack either way; the shell only supplies the theme,
masters, embedded fonts and the five shell slides it always did.

### 2026-09-02 — the style guide, the gate and its companions, cleaned up

`templates/STYLE.md` was rewritten as one document (this supersedes the 17:49 reorganization below, done in a parallel session and merged into it: its verified facts — Excluded Accounts open-only, the ICS one-decimal row, label halos and axis striding, the builder-inserted slides — are carried here) with a scope table (Executive
Reviews, the CashPlease module, the ILS review prep slides, the Summit one-pager),
an enforcement map naming the file behind every rule, and a dated decision log
replacing the per-date reversal notes that had accreted through the body. Stale
content went: the 2026-07-10 Austin per-chart to-do list (all fixed by 07-24),
`style_tables.py` and `kickoff_lib` (retired), `build_gen`/`build_gen_b`, the
two contradictory MRPC tier-color sections, and a divider line the shells never
carried ("Program Performance Review" — the ARS shell reads "Mailings · Debit Card ·
Reg E"). `templates/TEMPLATES.md` lost the superseded 67-slide Marine map and now
tables the three shells with their slide counts, plus the two families that have no
shell (CashPlease, ILS prep). `tests/test_style_doc.py` fails the suite if either
document cites a repo path that does not exist.

`validation/validate_deck.py` was restructured: every rule is a named function
listed in `RULES`, `run()` returns the findings, and the inline rules that lived in
`main()` are now `text_rule_findings`, `geometry_findings`, `autofit_findings`,
`mailing_table_findings`, `extract_findings` and `labelled_metric_findings`.
**Output is byte-identical** on all four templates and all seventeen 2026.08 decks
on Drive, checked by diff. One rule was added.

**Text drawn over text now FAILs.** Ported from the CashPlease project's `cp_qa.py`:
its Peer Comparison footnote was pulled up by `fit_layout` onto a row of capsule
pills and this validator returned 0 FAIL, because every overlap rule it had looked
for text over a CHART. The port compares estimated GLYPH boxes rather than frames —
per paragraph, at that paragraph's size, placed by alignment and vertical anchor.
A frame comparison flagged 109 places on the shipped decks (every ARS title box
overlaps the selection line's box by 0.10"; the ICS education titles sit in boxes
two inches tall; an ICS callout stacks 40 pt over 16 pt); the glyph comparison
flags none of them and still catches the 0.56" footnote. `tests/test_validate_deck.py`
carries both halves.

`validation/qa_all.py`: argparse, and the unit suite is no longer skipped quietly.
The Windows Store python has no pytest, so a gate started with plain `python`
reported PASS having run zero tests; it now prefers the repo `.venv` interpreter
for both pytest and the validator, and prints a banner when the suite could not run.

**Every MRPC and ICS deck renders differently, by two alpha points, and no figure
moves.** The callout drop shadow is now defined once, `shapes.shadow`, and the ARS,
ICS and MRPC builders import it. The ICS builder had its own copy at alpha 26%
against 28% everywhere else — a drift STYLE.md described as "matching".

Docstrings in `build/fit_layout.py`, `build/restyle_fonts.py` and
`build/slide_geometry.py` now state what the code does (the dense-table titles,
the geometry rules per title, the numbers `fit_layout` uses), and `build/README.md`
no longer lists the `data/` folders deleted 2026-08-29.

Not fixed, reported: `build/assets/summit_slide.pptx` is gitignored by the blanket
`*.pptx` rule and is absent on the Windows machine (no Drive `Inputs/Summit/`
either), so the four `tests/test_summit.py` cases fail here and every ICS/MRPC
build would. The asset needs committing (an ignore exception) or copying to Drive.


### 2026-09-02 — the ODD fixture regenerates when its generator changes

`conftest` only built the synthetic ODD when the file was missing, so pulling a change to
`make_odd.py` left a stale CSV in place. When MTD changed from fee dollars to NSF/OD item
counts, a cached fixture failed three correct tests with "non-integer MTD values" — pointing
at the tests rather than at the fixture. It now regenerates whenever the generator is newer
than the file.

### 2026-09-02 — STYLE.md reorganized, and three contradictions in it resolved

The style guide had accreted chronologically — thirty flat sections with headings like
"Slide-check additions (round 2)" — which reads as a changelog rather than something a
colleague can look something up in. Reorganized into eight numbered sections plus an
appendix, with a table of contents: foundations, slide anatomy, the two months, elements,
deck structure, per-product rules, adapting to client data, enforcement.

**The MRPC tier colours were stated three times and disagreed with each other**, and
`build_mrpc_gen.py`'s own docstring stated a fourth, superseded version. The code is the
truth — Gold = orange, Platinum = steel `#9DB8CC`, Business = navy, and the callouts MATCH
the bars. Stated once now, as a table, and the docstring is corrected.

The colour list also named `STEEL #9DB8CC`, but `brand.py` has `STEEL = #7B9BB8` (ARS) and
`STEEL_SOFT = #9DB8CC` (ICS/MRPC). The palette now matches `brand.py` name for name, so a
reader who copies a name gets the colour they read about.

Promoted two things to their own sections because they are the mistakes that actually
recur: **the two months** (reporting vs data, the distinction behind several defects) and
**enforcement** (what runs, in what order, and the three rules learned the hard way).

Dropped the nine "Known per-chart fixes (Austin 1075 review, 2026-07-10)" — one-off bug
reports rather than style rules, and the builders have moved past them. Added this week's
rules: Excluded Accounts is open-only, the ICS one-decimal comparison, chart striding and
label halos, and a note that Product Mix, Excluded Accounts and Reg E by Branch are
INSERTED by the builder, so they appear in a built deck but not in the template shell —
which is not obvious from opening the shell.

Divider lines, Reg E slide titles and Responder Activity titles were verified against the
templates and a built deck rather than carried over on trust.

### 2026-09-01 — MRPC Enrollment Performance was drawn from an invented denominator

`chart_perf` read `new_checking_approx`, a key **no client sheet has ever
carried**, and fell back to `enrollments / 0.11` — a guessed 11% penetration. The
real counts sit in `new_accounts` and the real goal in `goal`, present in every
sheet. Because the goal line was derived from those invented bars, every month's
goal was wrong too.

On Austin 1075 the fabrication drew 1,036 new accounts for a month that actually
had 873; on Marine 1539 it drew 236 where the truth was 341. **Figures move on
every MRPC deck.** There is no fallback now — absent keys raise, because a chart
that cannot be drawn from the client's data must not be drawn from a constant.

Enrollment counts also moved from the line to **above the bar**, matching
Retention (Aaron).

### 2026-09-01 — every MRPC deck shipped the template's enrollment sentence

The Enrollment-vs-Goal caption was resolved by POSITION: `txt_at(S[4], top=6.7)`
with a 0.15" tolerance, against a box that sits at **6.40"**. `txt_at` returned
`None`, the `if` fell through, and the caption was never swapped — silently, with
no swap gate in the MRPC builder to catch it. Austin, Ideal, Summit, Capital and
Marine all shipped the same sentence: *"averages ~55% of goal, peaking at 72% in
Feb 2026"* — Union Financial's numbers.

It would not have worked anyway: the replacement read `penetration_summary` from
the client sheet with a `''` default, and no sheet carries that key, so a caption
that DID match would have read "Enrollment penetration ."

Now resolved by CONTENT, derived from `pct_of_goal` (which is present), and it
raises if either the shape or the series is missing. Marine reads "averages 58%
of goal, peaking at 78% in Jun 26". Geometry drifts; the words do not.

### 2026-09-01 — the ICS 12-month close rate was the client's NON-ICS rate

The Comparisons row was inverted. `client` carried the client's **non-ICS**
close rate program-to-date, while the client's own **ICS** rate sat in the
*Velocity average* column — so the row compared a client against themselves and
labelled neither side correctly. It went unnoticed because the first client it
was checked against, CoastLife 1705, happened to have a 6.7% ICS rate identical
to the Velocity benchmark.

The Velocity average is a **constant**, like the 29% of openings and $1,828
lifetime value beside it, read off the template's "Velocity Clients' Average"
column: `VELOCITY_CLOSE_RATE_12M_PCT = 6.7`.

The footnote had its own defect: it says "your Non-ICS accounts' **12-month**
close rate" and was handed the program-to-date figure. **Figures move on every
ICS deck with a current workbook:**

| Client | Row was | Row now | Footnote was | now |
| --- | --- | --- | --- | --- |
| 1075 Austin | 5.4 vs 51.7 | 6.7 vs 5.4 | 51.7% | 6.5% |
| 1509 Texas Bay | 8.3 vs 44.5 | 6.7 vs 8.3 | 44.5% | 15.3% |
| 1539 Marine | 6.9 vs 35.5 | 6.7 vs 6.9 | 35.5% | 10.4% |
| 1734 Altamaha | 7.9 vs 13.8 | 6.7 vs 7.9 | 13.8% | 9.0% |

Austin's deck previously showed a 51.7% close rate for their ICS programme; it is
5.4%, against a 6.7% benchmark. The stored `benchmark` block is written by
`ics_workbook_extract`, so the client JSONs were re-extracted — the diff was
exactly these three fields on all four clients.

### 2026-09-01 — life-of-account metrics use Last 12 Months only

Program-to-date spans the whole programme and answers a different question: on
Austin it reports a 51.66% non-ICS close rate against 6.45% over the last year.
Mixing the two windows in one table compares figures that are not comparable, so
every metric off the *Life of Account Data* sheet now reads the **Last 12
Months** row (Aaron). *% of Total Openings* moves with it — Austin from 25% to
32% (3,609 of 11,109 openings).

### 2026-09-01 — "a program high" was asserted, not found

Two ICS captions declared a record without testing for one. The Power-of-
Referrals line called the PREVIOUS month a programme high unconditionally, and
the Referral Trend caption said the same of whatever sat at `[-2]`. Both were
**false on every client checked**: Marine's July was 103 against a June of 129,
Austin's July 363 against 423, Texas Bay's July 40 against a March of 73.

The claim is now earned or dropped, and scoped to what the data can support —
`trend` is a 14-month window, not the whole programme, so nothing there can prove
a *programme* high. Marine reads "July brought 103; the last 13 months peaked at
129 in Jun 26." This is also the "no superlatives or unsupported claims" rule in
CLAUDE.md.

### 2026-09-01 — canned claims that future data can falsify

An audit of every string the three builders write into a deck, bucketed by how it
goes stale: fully canned, fixed-index, and interpolated-but-unearned. Three MRPC
sentences asserted something no one had checked:

- *"Revenue has grown across the life of the program"* — Capital Bank 1502 peaked
  at $8.4K and has fallen for three years. Now tested against the annual series;
  1502 reads "Life-of-program revenue reached".
- *"Monthly MRPC revenue has held around $XK"* — 1502 swings ±15% around its
  mean. Now claims stability only within ±10%, else "has averaged". (The average
  also printed at `,.0f`, so a $669 mean rendered "$1K" beside a "$0.6K–$0.7K"
  range — an average outside its own range. One decimal now.)
- *"Platinum ($14.95/mo) is the most-held card"* — both the leader and the price
  were hardcoded. Both now come from `card_billing`, so a client whose Gold or
  Business Platinum book overtakes Platinum is not told otherwise.

### 2026-09-01 — the gate FAILs a slide whose text contradicts its own figures

`validate_deck.claim_consistency_findings` reads one sentence at a time and
matches each claim to its NEAREST figure pair: a stated percentage against that
pair, a movement or flatness word against the change, a comparative against the
ordering. Flatness is held to Aaron's ±2% band.

Getting it to FAIL rather than advise took three corrections, each found by
running it over shipped decks rather than invented examples: a COMPARISON is not
a MOVEMENT ("lower balances than non-responders, $924 vs $2,477" is correct, and
reading it as a change looks like a +168% rise — that failed six correct slides);
a sentence carries more than one claim (testing every claim against the FIRST
pair failed six more); and negation ("did not increase" is not an increase).

A rule that flagged claims with no supporting figure was **dropped**: it produced
156 findings across 20 files, almost all legitimate bullets whose evidence is the
chart on the slide. A rule that cries wolf 156 times is a rule nobody reads.

Separately, the validator was truncating its own output — findings quote slide
text, and printing an em dash to a pipe on Windows raised `UnicodeEncodeError`
part-way through the report, so the summary line landed and every finding after
it was lost. A gate that cannot say what failed is not a gate.

### 2026-09-01 — Average Ticket describes what the figures actually did

The caption hardcoded "ticket **holds** through response" — true of the
template's own $50→$50 example and of nothing else. It shipped over declines of
5.2% to 8.6% on six 2026.08 decks (1509, 1537, 1539, 1549, 1676, 1705). The same
sentence hardcoded "monthly swipes **rise**"; real clients do rise, so that never
showed on a delivered deck until the golden deck's synthetic ODD fell 3.0% and
said "rise" anyway. Both verbs now derive from the values they introduce, on the
±2% band, as does the chart title above the bars in `ticket_chart.py`.

The closing clause — "the gain is more transactions, not larger ones" — was
dropped (Aaron, 2026-09-01). The two movements are stated; the reader can draw
that themselves.

### 2026-09-01 — one month format on every chart axis, and one overlay-line color

**Axes.** Every month label is now `MMM'YY`, angled 45° — `periods.mon_yy()` /
`axis_months()`. Three formats were in service and none agreed: ARS drew
`Jun'25`, MRPC drew `Aug 25`, and the ICS quarter panels drew `Jul` —
`mm.split()[0]` threw the YEAR away, so a 14-month axis read Jan…Dec…Jan. Fixing
it exposed a gap in the shared parser: `parse_month` never handled `Jun 25` or
`Jun'25`, the pipeline's two commonest forms, so every VIP series fell through to
`None`.

**Overlay lines.** Three goes at this. The MRPC Retention line was drawn plain
WHITE on the assumption it never left a navy bar — it does, and the line was
invisible for its whole length on the 2026.08 decks, legend swatch included.
Then navy with a white casing, which was legible but rejected on looks. Now
**teal `#0D9488`**, which needs no stroke: 4.02:1 against navy and 3.74:1 against
white, both clear of WCAG's 3:1, and close to the best any flat color can manage
against those two extremes (3.88:1). Orange reference lines are left alone —
they already read at 5.5:1 on navy. `tests/test_chart_colors.py` still fails the
build if a mark is drawn in the canvas color.

### 2026-09-01 — ICS Billed Expense drops the account count

"Billed Expense for 6,785 Accounts" wrapped onto the value beneath it. The count
was already conditional on `fits_one_line`, which passed 6,785 and let it wrap
anyway; it is now dropped unconditionally (Aaron). The same figure is already on
the slide in the "ICS Accounts" callout.

### 2026-09-01 — the ODD's `<mon> MTD` column is NSF/OD ITEMS, not fee income

`odd_rows.nsf()` documented the `<mon> MTD` column as "NSF/OD fee income", while
every consumer read it as an item count: `charts_gen` titles it "NSF/OD Items",
`metrics_gen` names it `items12`/`nsf_last_items`, and `build_lift_matrix`
multiplies it BY a per-item NSF fee. Two descriptions of one column, with the
dollar reading only in prose.

Checked against the 2026.08 extracts for 1539, 1705, 1204, 1075, 1549 and 1218
(~580k account-months): every populated `MTD` cell is a non-negative INTEGER,
frequencies decay smoothly from 0 through 1, 2, 3, ..., no value carries cents,
and nothing clusters on a multiple of any fee amount. `<mon> YTD` is the
calendar-year cumulative of the same integers (19,552 of 19,573 sampled 1539
accounts reconcile exactly against Jan..Jul MTD). The ODD carries no OD-fee
dollar column at all — NSF revenue reaches the deck from the workbook's
"Total NSF Revenue" via `base_tab_extract`. ITEMS is correct.

**No client-facing figure moves.** Nothing on a slide was computed from the
dollar reading; every deck consumer already treated it as items, and no template
slide carries "fee income" wording. This is entirely about what the number is
called. Renamed and corrected:

- `odd_rows.nsf()` — docstring now states ITEM COUNT, with the evidence.
- `lift_extract` — `fee12` -> `items12`. A `.pkl` cached before today must be
  regenerated; `build_lift_matrix` now says so instead of raising `KeyError`
  inside the valuation.
- `oddd_optimize` — `od_fee_income_MTD` -> `nsf_od_items_MTD`,
  `od_fee_income_YTD` -> `nsf_od_items_YTD`,
  `top_branches_by_od_income_latest` -> `top_branches_by_nsf_od_items_latest`.
  These were formatted with a `$` in `oddd_pack.md`, including in the DERIVED
  block labelled "for Key Metrics slide" — a mislabelled dollar figure sitting
  where a deck author would reach for one. Now printed as counts, with a line
  saying NSF revenue is not in the ODD. Nothing outside the script read the old
  keys. MTD/YTD/PYTD moved from `money_fams` to `num_fams`; both paths take the
  same sum, so the totals are unchanged.
- `.claude/agents/oddd-optimizer.md` — the sanity-check and pack-contents wording.
- `tests/fixtures/make_odd.py` — the fixture wrote `MTD` as `35.00`/`70.00`, i.e.
  two $35 fees, teaching the wrong meaning to every test built on it. It now
  writes small integers, and `YTD` as their calendar-year cumulative.

Standing-rule check added: `tests/test_nsf_is_items.py` pins the meaning from
both ends — the fixture data must keep the shape of a count (integers, count-scale
magnitudes, YTD >= MTD), and no module that reads the column may describe it in
money terms again. The guard is itself tested against the exact lines the defect
shipped as.

Incidental, same commit: `oddd_optimize` wrote `oddd_pack.md` and
`oddd_metrics.json` with the platform default encoding, so it died on Windows
with `UnicodeEncodeError` on the arrow in "mailed -> responded". Both writes are
now `encoding="utf-8"`. This was blocking all 26 `test_golden_deck` tests on this
machine.

### 2026-08-30 — Average Life of Account prints one decimal on both sides

The ICS Comparisons row compared a pair at two precisions: the Velocity average
rendered "6.9 Years" against a client "6.21 Years". `cfmt`'s `years` format used
`{v:g}`, which prints the shortest form — so it also gave a client at exactly 7 a
bare "7 Years". Both sides go through the one formatter, so `{v:.1f}` fixes the
pair. Affects 1075 (7.66 -> 7.7), 1509 (7.05 -> 7.0), 1539 (7.24 -> 7.2) and 1734
(6.21 -> 6.2); those four decks were rebuilt and reissued, one value each and
nothing else touched.

1537, 1632 and 1676 have no Comparisons slide to fix — their workbooks are 2026.06
and 2026.07 against a 2026.08 deck, so their financial detail is suppressed by the
stale-workbook rule. Checked rather than assumed, since "the slide is missing" and
"the fix broke the slide" look the same from the outside.

### 2026-08-30 — promote_month.py, and its archive stamp comes from the clock

The staging-to-Outputs step is now a script in the repo rather than one written
per run. It archives whatever a deck supersedes, and leaves a deck alone when its
rendered content is identical to the delivered copy — a rebuild that changed
nothing should not churn the archive and bury the copies that matter.

Its date stamp was a literal, which dated four archives to the wrong day and
collided with the previous run, producing "-2" and "-3" suffixes. Now derived from
today; the four mis-stamped files were renamed.

### 2026-08-29 — a whole deck is built in the test suite

`tests/test_golden_deck.py` runs the real chain end to end — oddd_optimize,
metrics_gen, charts_gen, build_ars_gen, restyle_fonts — on the synthetic ODD and a
new synthetic workbook extract (`tests/fixtures/make_base.py`). A pipeline
regression now surfaces in **9 seconds** instead of in a seven-minute run across
fifteen real clients. No client data is involved; both fixtures are invented and
generated on demand.

Assertions are structural, not a hash: a hash fails on every intended change and
teaches people to re-baseline without looking. What is pinned is what must not
silently move — it builds, all 28 charts render, the slide count holds at 49, the
expected slides are present, its own validator passes it, the provenance sidecar
is emitted, and no real client's name appears anywhere in it.

Building it exposed the fixture's own limits: eight branches over 800 rows left
every per-branch cohort under metrics_gen's 15-account threshold, so the Reg E and
take-rate branch tables came out empty and their charts had nothing to draw. The
fixture now uses three branches and a larger new-account cohort.

### 2026-08-29 — the Summit slide may come from Drive

`build/assets/summit_slide.pptx` is replaced by hand before each Summit by whoever
prepares it, who should not need a commit to ship it. `Inputs/Summit/summit_slide.pptx`
now wins when present; the committed copy is the default, so the common path
touches no network and cannot drift.

Everything else stays in the repo deliberately. Fonts are committed precisely so
both machines render identically; the template shells are versioned build inputs
whose geometry `qa_all` diffs against a baseline every run. Moving those to a
streamed folder would trade fast-and-identical-everywhere for a consistency the
pipeline already has.

The optional lookup caught a latent bug on the way in: `rpe_env` raises
`SystemExit` when `RPE_DATA_ROOT` is unset, and `SystemExit` does not inherit from
`Exception` — so an `except Exception` around an OPTIONAL lookup would have killed
the build on a machine that had never configured Drive.

### 2026-08-29 — README

The repo had a one-line README. It now says what the pipeline builds, how to build
a month, where data lives, and what each companion file decides — `CLAUDE.md`,
`clients.md`, `CHANGELOG.md`, `STYLE.md`, `TEMPLATES.md`, the agent docs and the
PRD — so the split between them is discoverable without reading all six.

---


---

## 2026-08-29 — 2026.08 monthly delivery

Everything the 2026.08 client review decks were built with.

The monthly reviews and the Executive Summit are two different deliveries: the
reviews go to every active client each month, the Summit runs a couple of times a
year and only for attendees (Aaron, 2026-08-29). This heading is the monthly one.

### 2026-08-29 — clients.md decides a client's name, and 1204 is renamed

1204 is **First State Bank - Michigan** (Aaron). It shipped as "FSB Michigan" while its
workbook said "First State Bank-MI" — three names for one client, none of them agreeing.

The roster's `Client` column is now the delivery name: it goes in the filename AND
overrides what the workbook carries, so the cover and every source note match. Renaming a
client is a delivery decision, so it belongs in the file where such decisions are recorded,
not inferred from a previous filename (which is how "FSB Michigan" survived a cycle) or
read off a workbook nobody chose.

Six other roster entries carried short forms that had never reached a deck — "Texas Bay
CU", "CoastLife CU", "Ideal CU", "WesBanco Bank", "FNB&T Chickasha", "Altamaha Bank and
Trust". They are aligned to the delivered names, so making the roster authoritative renames
1204 and nothing else. 1204's 2026.08 deck was rebuilt and reissued; the old file is
archived as `(renamed 2026-08-29)`.

### 2026-08-29 — the Summit slide stays, and its date parser is ready for the next one

Confirmed: every results deck carries the Executive Summit slide (Aaron). The slide is
replaced by hand before each Summit — Ft. Lauderdale is next, in November — so
`summit_date()` reads the date off the slide rather than hardcoding it, and now accepts
abbreviated month names and a range that crosses a month boundary. A format it silently
missed would fall back to the previous Summit's date, which is worse than failing.
`summit_period()` warns when the slide still names a Summit that has passed.

### 2026-08-29 — Excluded Accounts explains OPEN accounts only

The slide answered "why is any account on file outside ARS", so its largest bar was the
closed book — an account that is closed is outside ARS by definition and explains nothing.
Dormant and inactive accounts were a second bar, which conflates "this account is not
active" with "this OPEN account is not eligible". Neither is a reason.

The population is now the open book. Reasons are product code, no debit card, and an
account-level remainder. The closed and dormant counts are still computed and named in the
source note, so the scope is stated rather than implied.

The tiles now reconcile — open accounts = open-and-excluded + open-and-eligible. The
eligible tile counts OPEN eligible accounts and says so; the whole-book figure includes
dormant accounts the core still flags eligible (147 on 1204), which left the three tiles
147 apart with nothing on the slide to explain the gap.

### 2026-08-29 — a slide module's own source note is no longer overwritten

`build_ars_gen`'s note pass wrote a title-keyword note onto every slide, including the ones
Product Mix and Excluded Accounts had already written for themselves — losing the
population, eligibility column and scope those modules actually know. It now skips slides
whose module wrote a note. Not "skip any slide that already has one": the template shell
carries stale dummy-client notes that must be replaced.

### 2026-08-29 — ICS and MRPC read the VIP store, and only the VIP store

`resolve_client_json` no longer falls back to `build/{ics,mrpc}_pipeline/data/`, and those
folders are deleted. They held copies that drifted: the Drive store carried 2026-08-29
pulls while the repo still had 2026-08-10, and a build reading the repo shipped month-old
figures that validated perfectly because they were internally consistent. Two stores for
one fact is the problem. Every active ICS and MRPC client was confirmed present in
`Inputs/VIP Data/` first; the only files that existed solely in the repo were two
`_PARTIAL` captures the store's README already records as not copied.

### 2026-08-29 — two chart collisions

*Monthly Summary — Last 12 Months.* The orange average label was drawn with `va='center'`
on the dashed average line, so the dash ran through the text. It now sits just above the
line. The same dash also struck through any bar label near the average — `$284K`, `$282K`
and `$298K` on Austin — so bar labels carry a white halo and the line passes behind them.

*Responder Activity: Before vs After by Offer.* The axis labels the newest mailing on top
of a strided tick list, and appended it blindly. Austin 1075 has ten mailings and a stride
of two, so ticks ran `... 8, 9` and "Nov25"/"Feb26" printed on top of each other. The
neighbouring tick is dropped rather than crowded.


---

### 2026-08-29 — the figure sidecar now reaches the deck that ships

`build_ars_gen` names its sidecar after the deck IT wrote — the ARS component. For a
multi-product client that component is an intermediate; the deck that ships is the
combined one. `validate_deck` looks for a sidecar named after the deck in front of it, so
the FAIL-grade figure check silently did not run on any combined deck.

`assemble_combined` now merges each section's sidecar onto the combined deck. Measures are
prefixed with their program (`ARS:responders_latest_mailing`): two programs using one
measure name is coincidence, not identity, and pooling them unprefixed would invent a
conflict between unrelated figures. Within a program the check is unchanged.

### 2026-08-29 — a multi-product client gets the combined deck only

Recorded because the archive shows both shapes historically: some cycles delivered a
client's per-program decks alongside the combined one. The per-program decks are
intermediates that feed `assemble_combined` — one client, one deck (Aaron, 2026-08-29).

### 2026-08-29 — ICS Comparisons header fits the client name

"Altamaha Bank and Trust Company Data" is 4.64in of Montserrat 16pt in a 3.7in box: it
wrapped onto the value below. Shrinking is not available — `enforce_min_font` floors every
run at `MIN_PT`, which its own comment warns about. The header band now grows upward and
anchors to its bottom edge, so the values never move; a name that fits keeps the original
geometry and anchor exactly, and no other client's deck changes.

### 2026-08-29 — a missing MRPC channel count is not the same fact as a zero

Re-running all 15 2026.08 decks crashed Marine 1539's MRPC build: `chart_channel`
plotted `counts["Paper"] = None` and died on `vals + max(vals)`.

A channel count can be absent for two reasons and the chart must not conflate them. The
client may genuinely have no enrolments on that channel — a real zero, and a normal
state. Or VIP may decline to surface the number: Marine's Paper bar is too small to
trigger a tooltip, and the sheet records `None` with the note "~3 implied by 0.04%".
Writing `0` there would be false precision; the share is not zero.

Both now draw a zero-length bar and only the LABEL differs — the count when known, `0`
when the share is also zero, `n/a` when the share is non-zero but the count was not
readable. The totals chart is kept either way. A first attempt fell back to the share
chart whenever any count was missing, which threw away three good counts because of one
and read a genuine zero as a gap.

Affects Marine 1539 only: slide 58's Paper bar is now labelled `n/a` rather than `0`.

### 2026-08-29 — figure provenance sidecar: a measure renders one value, or the build fails

The 2026-08-28 Wellworth defect — the Jun 2026 drop reading 1,077 on the mailing slides and
1,026 on Reach/Depth/Ranking/Sustained — got past two guards. The builder's swap gate fails a
build whose swap string matched NOTHING, but here both swaps landed; they just wrote
different numbers. And `validate_deck.figure_identity_findings` has to INFER from wording
whether two figures are the same measure, which misfires on legitimately different cuts
(personal vs business take rate), so it can only advise.

The builder does not have to infer. It knows which measure produced each number, so it now
says so: `set_exact`/`set_shape_text` take an optional `measure=`, and `build/figures.py`
records (measure, rendered value, slide) as the deck is written. Two consumers:

* **Build gate.** `conflicts()` runs before the phase that materializes the output file, and
  a measure carrying two values fails the build with exit 2, naming both values and the
  slides they landed on. Placement matters — at the final save it still exited 2, but a
  partly-built deck was already sitting at the delivery path.
* **`validate_deck.figure_sidecar_findings`** reads `<deck>.pptx.figures.json` and FAILs on
  the same conflict. This is the FAIL-grade counterpart to the inferred rule, which stays at
  REVIEW: here the builder named the measure, so a difference is arithmetic, not a guess.

Naming is opt-in and only worth doing where one measure reaches more than one slide. Five are
named today (`responders_latest_mailing` across three slides, `mailed_latest_mailing` across
two, plus `resprate_latest_mailing`, `reach_total`, `dot_n`). No deck changes: 1204 rebuilds
to 49 slides, 38 chart images byte-identical, 0 text differences. Only the ARS builder emits
a sidecar; a deck without one validates exactly as before.

The sidecar goes to `Build Artifacts/` under `RPE_DATA_ROOT`, named after its deck, NOT
beside it: `Outputs/` is the delivery folder and holds finished decks only. `validate_deck`
looks there first and then beside the deck, so anything built before the move still
validates. The `.A/.B/.C/.D` phase decks no longer go next to the output at all — they are written to a
temp directory and dropped through `atexit`. They used to land in the delivery folder and
were only removed on the happy path, so a build that died partway left four intermediate
decks there. Cleanup alone would not have been enough: the CSI mount allows creating and
copying but NOT deleting (`rm` returns "Operation not permitted"), so nothing written there
could ever be removed. Verified both ways: a clean build leaves the output folder holding
exactly one file, and a failed one leaves it empty.

### 2026-08-29 — build from the template shell, never from a client deck

CLAUDE.md contradicted itself: one paragraph said each program "clones-and-swaps from the
latest Marine FCU (1539) reference deck", while its own file listing and every builder said
the input is the stripped `templates/*_template.pptx` shell. The builders were right — that
is what `build_ars_gen.py` takes as argv[1].

Cloning a finished client deck carries that client's numbers, captions, branch names and
speaker notes into the next client's file. It is the mechanism behind the reference-leak
rule and behind `validate_deck.reference_leak_findings` existing at all: a figure that was
never swapped is indistinguishable from one that was. Corrected in CLAUDE.md,
`templates/TEMPLATES.md` and all three deck agents, which also still named the retired
Client Presentations drop as the delivery target.

### 2026-08-29 — MRPC template shell carried misleading slide titles

`mrpc_template.pptx` titled two slides "MRPC Revenue to Union Financial" and two "MRPC Key
Metrics". They are four DIFFERENT slides — `build_mrpc_gen` retitles them by position to
Revenue by Year, Revenue by Month, Card Portfolio and Key Metrics — so no client deck was
ever affected, and a real build validates at 0 FAIL with four distinct titles. But a shell
that does not describe what it becomes is a trap for the next person reading it, and it made
the deck look like it shipped duplicate slides. The shells now carry the titles the builder
produces, in both `mrpc_template.pptx` and the reference deck. Built output is unchanged,
verified by rebuilding 1075 (13 slides, 0 text differences).

`assemble_combined.section_slides` also stopped resolving the opening block by position. It
dropped indices 1 and 2 outright, assuming every deck opens with cover + Executive Summit;
that holds for a BUILT deck of any program (summit_slide.py inserts one), so no delivered
deck lost anything — but it is not true of the MRPC template shell, which has no summit
slide and whose divider sits at index 2. Slides are now identified by meaning, as CLAUDE.md
requires: the cover carries the "Executive Review" line, the divider carries the program's
benefits line. Verified to produce identical results to the old rule on a built deck.

### 2026-08-29 — the reporting month comes from the period, never the clock

`build_ars_gen`'s slide-1 note and the one-pager header both took `date.today()`. Correct
only while a deck is rebuilt in the month it ships; rebuild an August deck in October and
the note said October while the cover still said August.

Both now resolve the same way, so a one-pager and its deck cannot disagree: `ARS_PERIOD` /
`RPE_PERIOD`, then the `<yyyy.mm>` tag in the output filename, and nothing else. An
unresolvable period is a hard failure naming both ways to fix it.

There is deliberately no fallback. Not the clock, for the reason above. And not the
Executive Summit's month either — that was tried and reverted the same day: a Summit runs a
couple of times a year and only for attendees, while these are the MONTHLY reviews, so
deriving one from the other would be wrong ten months out of twelve (Aaron, 2026-08-29).
`summit_slide.summit_date()` still reads the date off the slide, but nothing in a builder
depends on it.

STYLE.md draws the distinction and it is easy to invert: the cover and one-pager header
carry the month the report is PRESENTED (STYLE.md:85), while the period pills and PTD
figures carry the DATA month (STYLE.md:44, explicitly "NOT the report/generation month").

### 2026-08-29 — superseded: two reporting months came from the wall clock

The slide-1 speaker note (`build_ars_gen.py`) and the one-pager header
(`build_ars_onepager.py`) both took `date.today()`. Correct only while a deck is rebuilt in
the month it ships; rebuild an August deck in October and the note said October while the
cover, which resolves `PRESENT_MONTH` properly, still said August.

Both now resolve the reporting month the same way — `ARS_PERIOD`/`RPE_PERIOD`, else the
`<yyyy.mm>` tag in the output filename — so a one-pager and its deck cannot disagree. Note
that STYLE.md draws a real distinction here and it is easy to get backwards: the cover and
one-pager header carry the month the report is PRESENTED (STYLE.md:85), while the period
pills and PTD figures carry the DATA month (STYLE.md:44). These are the first kind.

### 2026-08-29 — blank `Business?` counted two different ways in one deck

`ticket_calc.personal()` read `!= 'yes'` while `metrics_gen.personal()` read `== 'No'`, so an
account with a blank `Business?` cell was PERSONAL to one slide and BUSINESS to another in
the same deck. `product_mix_slide` had already settled the house rule by splitting the book
three ways — Yes, No, and everything else — so a blank is neither.

Both now import one definition from the new `build/ars_pipeline/odd_rows.py`. Blanks are
real: 1218 carries 271, 1204 carries 57, 1038 carries 2. No delivered deck moves — the blank
accounts in 1038 and 1204 have no trailing-quarter swipes, so `ticket_calc` skipped them
anyway, and 1218 ships no ARS deck. 1218's blended average ticket would move $44.87 -> $44.79.

### 2026-08-29 — validator gained three rules and the gate gained a test suite

Nearly every entry above this one is a wrong-number bug, but `validate_deck` was a text and
geometry linter. Added, with the calibration each needed to stay quiet on a correct deck:

* **figure identity** (REVIEW) — one labelled measure carrying two different values across
  slides, the shape of the Wellworth 1,077/1,026 split. Labels are discovered from the deck
  rather than hardcoded to four words. REVIEW, not FAIL: proving two renderings are the same
  measure needs a builder-emitted sidecar, and inference should not block a ship.
* **period consistency** — FAIL on a span whose stated month count contradicts its own
  endpoints, and on a caption naming a month after the data snapshot. REVIEW on an earlier
  month, which is sometimes correct (carried-forward ICS financials).
* **source-note provenance** — FAIL on a data slide with no note or no Source line, and on a
  note naming a different client. That last is the CoastLife-defaults defect;
  `reference_leak_findings` reads slide text only, so a leak in the NOTES was invisible.

`pytest tests/` (277 tests) now runs as step 0 of `qa_all.py` and a failure fails the gate,
because a classifier regression that mis-buckets 18,000 accounts still produces a deck that
passes every layout rule. The fixture is a synthetic 800-row ODD carrying no member data.

### 2026-08-29 — one source for the palette, the slide primitives and the date phrases

Not a behavior change — every rendered colour and every rebuilt deck is byte-identical,
verified by rebuilding 1204 (49 slides, 38 chart images matching, 0 text differences). Logged
because it changes where these are sourced from.

The palette had been re-declared in seven files under four naming conventions, and five
different greys were in service as "the light grey"; it now lives in `build/brand.py`. The
slide primitives lived inside `product_mix_slide.py` — a module about one slide — where ICS
and MRPC could not reach them; they now live in `build/shapes.py`. `slide_geometry.py` moved
to `build/` and all three builders call it, so the next ICS or MRPC layout fix lands in the
contract instead of in one deck. Date phrasing derives from `build/periods.py`; a literal
month is still fine when it is the month being described, but spans and counts are no longer
hand-computed. ICS/MRPC client sheets resolve through `rpe_env.resolve_client_json` under
`Inputs/VIP Data/<PROGRAM>/<id>-<Name>/`, indexed by that folder's `manifest.json`, so a
fresh checkout on the CSI machine is no longer missing them. The loose
`data/<id>_<program>.json` stubs in the repo are searched LAST: the README there records
them as superseded by the per-client folders, and they are an older pull — 1705's stub is
the 2026-07-13 capture against the folder's 2026-07-15, so an earlier search silently
returned the stale one.

### 2026-08-28 — orange KPI tile label read grey

`_tile` drew every tile label in GREYB (#CFDBE8), the muted grey picked for a NAVY tile.
Against ORANGE that pairing carries almost no contrast and the label reads as grey text on
the fill — Aaron flagged it on FNB&T 1537's Reg E Opt-In by Branch slide.

The label is now white on an orange tile and unchanged on navy. Affects every slide with an
orange tile: Reg E Opt-In by Branch, Excluded Accounts, Product Mix & ARS Eligibility, and
the swipe-tier movement slides.

### 2026-08-28 — Reg E new-account branch caption claimed a staffing effect

The caption under the by-branch chart on "Reg E Opt-In — Opened in Last 12 Months" read
"Lower-staffed branches lag; higher-touch branches lead on new-account opt-in." The ODD
carries no staffing count and no measure of customer contact, so neither half of that claim
could be shown from the data behind the chart. It was template text, so it shipped on every
ARS deck regardless of what a client's branches actually did.

It now states what the chart plots — "Dashed line = <rate> overall." — matching the sibling
caption on the all-accounts slide. Both templates are corrected and the builder also sweeps
the old sentence, so a re-seeded reference deck cannot reintroduce it silently.

### 2026-08-28 — "ODD" no longer appears on a slide face

The Mailing Response Summary subtitle ended "Offers sent and responders counted from the
ODD", naming an internal system on a client-facing page. Removed from all three variants of
the line — first mailing, trailing window, all mailings — so it is gone regardless of how
many mailings a client has. Slide 13's speaker notes still name the workbook, the ODD
extract, its pull stamp and the period, so the figures stay auditable. Verified across all
nine 2026.08 decks; that subtitle was the only on-slide mention.

### 2026-08-28 — ICS financial detail is absent when the workbook predates the deck

Replaces the carry-forward rule. A monthly build carried the last ICS workbook's financial
sections forward and stamped the DECK's period on them: 1537 FNB&T and 1676 True Sky both
showed "PTD · August 2026" over an ICS Financial Summary built from a 2026.06 and a 2026.07
workbook respectively.

The builder now resolves the newest ICS workbook for the client from
`Inputs/ARS & MRPC Reports/` and compares its period to the deck's. On a mismatch the
workbook-driven sections are ABSENT rather than re-dated, reusing the referrals-only path —
the section divider drops to "Referrals" and the agenda stops naming account value, ROI and
financial results. Referrals, Referral Trend, Results by Branch and the education slides are
unaffected.

2026.08 effect: 1075, 1509 and 1539 have current workbooks and keep their financial detail;
1537 and 1676 lose it (ICS section 28 → 14 slides); 1549 had no workbook and was already
referrals-only. The referrals-only log banner no longer claims "no ICS workbook has landed"
in this case, which was untrue when one landed and is merely older.

### 2026-08-28 — empty age chart no longer drawn; last n= notation removed

The Age Profile slide already wrote the right sentence when DOB is absent — "Date of birth is
not carried in this client's data extract" — and then drew the chart anyway: an empty axis
with a row of twelve zeros. Missing data is stated and never zeroed; only the text half of
that rule was implemented. The plot is removed, the statement takes its place, and the
Selection line no longer promises an age mix that is not shown. 1537 FNB&T is the case: the
DOB column is present and blank on all 29,852 rows, which is a data-sourcing question for
CSI, not a pipeline defect. The PNG is still generated — skipping it would leave the
template's image19 in place and display the REFERENCE client's age chart.

Separately, the two Selection captions still carrying "n=" (New-Account Debit Adoption,
First-Year Closure) now state their population as a bare parenthetical like every other
Selection line.

### 2026-08-28 — Before vs After by Offer chart was unreadable at mailing volume

Every mailing month was labelled with an "(n=…)" second line beneath it. At fifteen mailings
(Sugar River 1038) the axis rendered as overlapping mush and the per-bar dollar labels
overprinted each other. The axis now labels every Nth mailing capped at 8 ticks, always
including the newest; "(n=…)" moves to the speaker notes as NU / TH per mailing, so the count
behind each bar stays auditable rather than dropped; per-bar dollar labels are drawn only
below 8 mailings, above which the y-axis carries the scale.

Affects the seven 2026.08 clients with more than 8 mailings: 1038, 1075, 1204, 1509, 1539,
1676, 1705. Slide 19's Mean chart needed nothing — its rotated labels handle fifteen. Same
shape as the excluded-accounts footnote bug: correct on Wellworth's single mailing, wrong at
volume, and passed by the gate because nothing overflows a box.

### 2026-08-28 — clients.md decides what gets built, not the presence of a data file

Program membership was inferred from whether input files happened to exist. That is how
CoastLife 1705 kept producing an ICS section after cancelling — their ICS data was still on
disk. `clients.md` now records intent and is the authority; leftover program data and a
2026.08 DCO file are explicitly not signals to build.

Confirmed by Aaron the same day: PointBank 1174 off the books entirely; Truliant FCU 1658 has
no RPE at all; CoastLife 1705 ICS cancelled with ARS continuing; Canandaigua 1437 ends
2026-10-31 with no further reviews; 1218, 1477 and 1502 MRPC-only; 1632, 1734 and 1738
ICS-only. Building the roster surfaced that 1204 FSB Michigan had 2026.08 inputs and no deck.

### 2026-08-28 — Excluded Accounts footnote is measured, not assumed

The footnote block sits at 6.05in with the logo band starting at 6.78in, so it holds two
lines. Which observations exist varies by client — 1549 has no Mail column at all, 1537 has
all three and estimated five lines, which failed the gate. Lines are now measured at the 16pt
floor `restyle_fonts` enforces and truncated to what fits; every observation still goes to
the speaker notes, so nothing is lost, only moved. The mail-funnel sentence is shortened to
one line.

The stale-caption check also stopped flagging derived pills. It compared any
template-identical dated text and caught "PTD · June 2026" on four of CoastLife's ICS slides,
correct at the time because ICS financials carried forward. It now covers caption prose over
40 characters, which still guards all 21 real template captions and exempts three pill forms
that each have their own swap guard.

### 2026-08-28 — responder counts now agree across slides

The same mailing reported different responder counts on different slides: Wellworth
1549's Jun 2026 drop read 1,077 on the mailing slides and 1,026 on Program Reach,
Depth of Engagement, Ranking and Sustained.

Cause: those four counted a HISTORICAL mailing's responders through the CURRENT
eligibility snapshot (`<latest> Elig`), which drops anyone who responded and has since
closed or gone ineligible — 51 accounts on Wellworth. Slides 18/19 already used the
personal cohort for exactly this reason (2026-08-27); the rest now match.

Affects every ARS deck. Reach, depth and ranking figures rise.

### 2026-08-28 — sustained rate measured after the response month

Sustained compared the extract's trailing 3 months against the ask, for every mailing.
For a recent mailing that window includes months from before the customer responded, so
it reported attrition that had not happened.

A response is recorded in the month AFTER the offer — Wellworth confirms it: 44% of the
Jun 2026 responders cleared their ask in June, 100% in July. The window now starts at
mailing+2. A mailing with no month after its response month reads 100% by definition and
is drawn grey with the caption saying attrition cannot appear yet.

### 2026-08-28 — before/after is mean only, split by offer

The median twin (slide 19) is replaced by the same mean, split into Non-User and
Threshold respondents. The two offers ask for different behaviour and pooling them hid
which one moved. Grouping keys on `<mon> Mail`, as mail_summary does.

A Non-User's baseline is near zero, so its percentage change is meaningless (Wellworth
computes +9,018% off $13); below a $25 baseline the narrative states dollars instead.

### 2026-08-28 — Stat Code fallback in the shared status classifier

`classify_status` only ever read `Stat Desc`. 1549 Wellworth populates `Stat Code`
(O/C/X) and leaves `Stat Desc` BLANK on every non-open account, so 18,274 of 50,218 rows
classified as "Other". `oddd_optimize.STAT_CODE_MAP` now maps O/A -> Open, C -> Closed,
X -> Charged Off (Aaron-confirmed); the description still wins when it carries text.

Affects the account-status mix on any client whose core fills the code, not the label.

### 2026-08-28 — take-rate-by-branch table showed months twice

`set_table` trimmed surplus template ROWS but not COLUMNS, so a client with fewer
activity months than the template's eleven kept the reference client's remaining
columns. Wellworth's table carried a second Apr/May/Jun and a second Cards/Elig/Take%
block from Union Financial. Columns are now trimmed to the data and the width
re-spread. The table also fills the slide (10 branches, was a fixed 6).

### 2026-08-28 — stale month captions

A dozen template captions carried the reference client's month and no swap ever reached
them, so a Jul 2026 extract shipped "Monthly debit spend (June 2026)", "opt-in status as
of June 2026" and "Jul 2023 - Jun 2026 (36 months)" on a client with five months of data.
Point-in-time phrases and series spans are now derived. `validate_deck` FAILs any dated
caption still byte-identical to the template's, scoped to the template's own reporting
month so a genuinely fixed window (the Kaplan-Meier cohort) is not flagged.

### 2026-08-28 — ICS branch goals pro-rated

Branch goals in the VIP export are ANNUAL, but a program that started partway through the
year has not had a year to hit them. Wellworth began in May; its Main branch read 24
against a 204 annual goal (12%), which reports the calendar rather than the branch. The
goal is now pro-rated to the months the program has run — Main reads 24 of 68 (35%), and
the top-8 total moves from 14% to 41%. Falls back to the annual goal when the run length
cannot be derived.

### 2026-08-28 — Reg E "no election" wording, and the ICS branch selection line

"No election means the customer was never asked" asserted something the data cannot
show, and put it on the branch. No election means only that we do not hold their
decision — they may well have been asked. Now reads "no election means the customer
hasn't given us one" (the exact phrase "didn't give us their decision" measures 12.30in
against 12.10in of box and wraps onto the tiles).

The selection line was removed from ICS "Results by Branch – Year to Date": with the
callouts and the pro-rating note it ran to ~20in of text in a 9.68in box, wrapped, and
its box overlapped the table above and the logo band below. Selection, branch counts and
the pro-rating basis are all in the notes.

### 2026-08-28 — combined deck split the ARS section at a fixed index

`assemble_combined` kept "the first 30 slides" ahead of the ICS section. That is only
right while the ARS deck is exactly 47 slides. Adding Excluded Accounts and Reg E by
Branch made it 49, and the boundary cut two slides early: "Reg E Opt-In by Account
Vintage" and "ARS Key Takeaways" were pushed AFTER the ICS section. The boundary now
resolves by TITLE ("ARS Key Takeaways") — CLAUDE.md: never by index. It printed a note
about the count mismatch and carried on regardless; it now states where the section ends.

Also: the combined agenda described the ICS section as "Referral trend, account value,
ROI & financial results" even for a referrals-only build that contains none of those.
Detected from the slides actually copied, not from a flag.

### 2026-08-28 — Reg E by Branch is new accounts, not the whole book

The table was built on every open personal card holder — a view dominated by decades of
legacy elections that says nothing about how branches are asking today. It now uses the
same trailing-12-month cohort and >=15 threshold as the new-account chart beside it, and
reconciles to `rege_new_pct`. The heading states the window ACTUALLY used: an extract
carrying fewer than twelve activity months yields a shorter one (Wellworth's is
Mar-Jul 2026), and "Last 12 Months" over five would be false.

### 2026-08-28 — referrals-only ICS agenda listed absent sections

The section divider correctly dropped to "Referrals", but the agenda still listed
Performance of ICS Accounts, ICS Revenue & Revenue Detail, ICS Financial Summary and
Comparisons — four sections a referrals-only build deliberately OMITS. Wellworth 1549
shipped that way. Rows are now removed, not blanked, for the same reason
`assemble_combined` removes them: an empty numbered row reads as a section that failed
to render. A full workbook-driven build still lists all eight.

### 2026-08-28 — client logo on the Agenda slide (ARS + ICS)

Placed in the right-hand third, which is empty: the agenda's own text reaches at most
8.80in (measured against the bundled TTFs at the 16pt floor), so a logo from 9.30in
clears it. Sourced from `Inputs/Logos/<clientid>.png` via `rpe_env.client_logo`, cropped
to its ink by `trim_logo` and fitted by `fit_box`. Absent logo = slide built without it.

`trim_logo` also re-encodes any file python-pptx cannot embed: 1539.png is really a
WEBP, which PIL opens happily and `add_picture` then refuses outright. MRPC has no
agenda slide, so it is unchanged.

### New slides — Excluded Accounts (ARS), Reg E Opt-In by Branch (ARS)

Excluded Accounts follows Product Mix: the eligibility waterfall (status -> product code
-> debit card, each account counted once) plus the per-client excluded product codes,
derived as those with no eligible account. $0 balance and address quality are reported as
observations, NOT exclusions — neither predicts the `Elig` flag.

Reg E Opt-In by Branch is the table companion to the two Reg E branch charts, carrying
opted-in / opted-out / no-election per branch.


### 2026-08-27 — tier response rate denominators (shipped)

Landed in `metrics_gen.mail_summary` (`metrics_gen.py:184-199`): `nu_sent` and
`th_sent` split on `<mon> Mail`, each group is rated against its own base, the
trailing total pools each group's own recipients rather than averaging the
per-mailing rates, and an unknown offer code raises the warning the PRD asked
for. Verified 2026-08-29. The description of the defect follows, kept because
the reasoning is the reason the fix looks the way it does.

`NU 5+` and `Threshold Met` on the ARS Mailing Response Summary divided by total
accounts mailed instead of by each offer group's own mailed count. They are
shares of the whole file, not response rates, and they sum exactly to the
overall response rate — which is the tell.

The fix, agreed 2026-08-26: each offer group is rated against its own mailed
base. NU responders over NU recipients; TH responders over TH-10 through TH-25
recipients combined; overall responders over total offers sent. The three no
longer sum, because the denominators differ.

The ODD already carries what's needed. `<mon> Mail` holds the offer strategy per
account (`NU`, `TH-10`, `TH-15`, `TH-20`, `TH-25`) — `metrics_gen.OFFER_GOAL`
maps exactly those five values, and the dot-plot code already reads it that way.
`mail_summary` simply never split on it.

Grouping keys on what was mailed (`<mon> Mail`), not on how the account
responded (`<mon> Resp`). Those should agree, but if they ever don't, keying on
the response tier puts a responder in a group whose denominator doesn't contain
them, and the rate can exceed 100%.

Touches `metrics_gen.mail_summary`, the six-value row unpack in
`build_ars_gen.py`, the slide-12 subtitle, and the stale comment block described
in the 2026-08-20 entry.

Affects: all nine 2026.08 ARS decks. None had been sent when this was found.

CoastLife 1705 v3 was patched by hand on 2026-08-26 as a stopgap, sourcing the
rates from the workbook rather than the ODD. The generator fix has since landed,
so v3 is superseded — regenerate CoastLife rather than referring to it.

---

## 2026-08-20

### Mailing response moved from the workbook to the ODD

Slide 12 read tier response percentages out of the workbook while slide 14
computed the latest mailer from the ODD, and the two disagreed on the same drop
— 16.3% vs 10.7% on Wellworth 1549. Both now use one definition: offers sent =
personal accounts carrying a `<mon> Mail` value; responders = those whose
`<mon> Resp` reached a goal tier.

The rationale recorded in `build_ars_gen.py` states the workbook's denominator
is not the mailed population. That reasoning does not hold for every client —
CoastLife's workbook denominators reconstruct the mailed population exactly
(2,015 NU + 2,756 TH = 4,771 offers sent, Jun 2026). Wellworth has a single
mailing and no lift matrix, so it was a thin case to generalize from.

Single-sourcing to the ODD was still correct. The denominator was the separate
bug, unfixed here, and carried forward into every deck built after this date.

**Update the comment block in `build_ars_gen.py` when the Unreleased fix lands.**
It currently argues for behavior we are changing.

### Other fixes the same day

- Title-slide and PTD-pill months were never swapped; every 2026.08 ARS deck
  shipped the template's "July 2026" and "PTD · June 2026".
- Business take-rate branch chart had no bar cap while sharing the personal
  chart's geometry — 19 bars on 1549, 37 on 1075, x labels unreadable.
- The 2:1 profitability sentence was a template literal, so a client below the
  threshold shipped "0.2 : 1 is well above the 2 : 1 threshold".
- Mailing Response Summary carried the reference client's rows below a short
  client's data; `set_table(trim=True)` now drops them.

---

## 2026-07-25

- Slide resolution moved from indices to titles (`SB()`), which raises instead
  of silently no-opping. Index access is how the Appendix swaps went stale.
- Swap gate added: any find-string matching nothing fails the build. A miss
  would ship the reference client's numbers.
