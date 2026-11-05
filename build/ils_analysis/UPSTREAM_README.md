# ILS Program Performance Review — Deck Builder

Adds ZAccounts and ZTrend analysis into the **CSI house review template** for an
ILS client, and drops each section at the right point inside it.

This consolidates three earlier tools into one:

| Was | Now |
|---|---|
| Matrix Deck Generator | the **ILS Matrix Validation** section |
| Deposit Score Validation Tool | the **Deposit Score** output-analysis and rule-logic sections |
| `deck_builder` (branch analysis) | the **Branch deposit behaviour** sections |

The template is the structure of the deliverable — it ships with the cover,
agenda, industry update, section dividers and back matter — so generated slides
are **inserted at their anchors**, not appended. Re-running against a deck you
already built replaces its generated slides rather than duplicating them.

Every slide is laid out natively for the template's 20 × 11.25 in canvas, on the
template's own branded layouts (`33_01 - BLANK` for content, `32_01 - BLANK` for
dividers, `3_01 - BLANK` for covers) and in the house type — 36 pt bold Source
Sans Pro in `#00274C`, with the CSI orange accent. Generated slides sit next to
the hand-built ones without reading as pasted-in.

Type is sized for the room, not for a laptop: 36 pt titles, 18 pt subtitles,
15 pt table body, 16 pt bullets, 42 pt KPI figures, 12–13 pt chart labels. Dense
tables shrink to fit their rows automatically, and long bullet blocks auto-shrink
rather than running over the footer (`fit_text_size` in `theme.py`) — PowerPoint's
own autofit only applies once a human edits the file, so generated overflow would
otherwise be silent.

---

## Use it (desktop app)

1. Double-click **`Generate ILS Program Review.bat`**.
2. Click **Browse…** next to **Client folder** and pick the client's analysis
   folder — e.g. `…\UCCU\Analysis\2026-9`.
   The ZAccounts, ZTrend, Matrix Validation and DBIC files fill in
   automatically, and the log says what it found and what it didn't.
3. Confirm **Organization reviewed** — the bank or credit union this deck is
   for. It is guessed from the folder path; check it, because it is written
   into every institution reference in the deck (see below).
4. Confirm the **Template** (it auto-locates a `*CSI Format*` / `*Program
   Analysis*` `.pptx` next to the app). **Check…** reports which institution
   name the template currently carries, before you build.
5. *(Optional)* On the **Sections** tab, double-click a row to turn it on or off
   and use **▲ / ▼** to reorder. On **Options** and **Branches**, adjust the
   knobs described below.
6. Click **Build Deck**, then **Open Deck**.

The output is auto-named
`<Client> - ILS Program Performance Review - <Month Year>.pptx` and saved beside
the ZAccounts file unless you set **Save to folder**.

## Use it (command line)

```bash
python -m ils_review.cli --from-folder "C:\...\UCCU\Analysis\2026-9" --client "Utah Community CU"
```

`--from-folder` finds the four inputs by filename and infers the client from the
path. Everything is overridable:

```bash
python -m ils_review.cli --client "Utah Community CU" --template "ILS Program Analysis - New CSI Format 2026.pptx" --zaccounts 1206_zaccounts_20260826.csv --ztrend 1206_Ztrend_20260826.csv --matrix 1206_MatrixValidation_20260826.txt
```

Useful flags — `--list-sections` prints the registry, `--dry-run` reports what
would build without writing a deck, `--sections` takes an ordered comma-separated
list, `--no-anchor` appends everything at the end instead, `--keep-existing`
skips the replace-previous-slides step, `--all-rows` paginates long tables
instead of capping them, `--replace-mrpc` relabels MRPC as CashPlease.

---

## Input files

| File | Required | What it unlocks |
|---|---|---|
| **ZAccounts** (`*zaccounts*.csv/.txt`) | yes | branch behaviour, growth, repayment segment, deposit score |
| **ZTrend** (`*ztrend*.csv/.txt`) | no | deposit volatility, the deposit-health box plot, notice-derived variables |
| **Matrix Validation** (`*matrixval*.txt`) | no | matrix validation, communication strategies, strategic refunds, deposit-score rule logic |
| **DBIC** (`*dbic*.txt`) | no | program health: calculation log, feed integrity, Reg E opt-in, fee collection, channel mix, override effectiveness |
| Deposit Score decision-tree image | no | renders as a logic slide alongside the per-rule table |

Column names are matched case-insensitively against known aliases, and only the
columns actually used are read — these extracts run 60–190 MB and 80+ columns,
and every section shares **one** load.

Both date styles in filenames work (`20260826` and `2026.8.26`); the snapshot
date comes from the filename, falling back to `lastupdate` / `max_notice_dt`.

### Nothing crashes on a partial run

A section whose inputs are missing is skipped and **the reason is written onto
the Data Notes slide**, so a partial deck is still usable and self-explaining.
Sections are also individually wrapped: one that raises is reported on that same
slide and the rest of the deck still builds.

Real examples seen in the wild, all handled:

- `Deposit_Score` present but **empty for every account** (common for clients
  whose matrix is limit-tiered rather than score-driven) → the output-analysis
  section is skipped with that stated.
- No Deposit Score sections in the matrix export → rule-logic slides skipped.
- Strategic Refunds configured but with no ranges/tiers/maximums → skipped.
- Rule text truncated at 256 chars by the export → flagged ⚠ with a footnote;
  re-export query 1822 with a wider column and it renders in full, no code change.
- Trend grids whose axis labels were truncated → reconstructed positionally and
  footnoted. **Factor values are always exact** — they sit in the last column,
  which is never truncated.

---

## What it builds

Sections, in default order. Each is toggleable and reorderable.

| Section | Slides |
|---|---|
| `branch_personal` / `branch_business` | executive overview (KPI cards + auto-written read), deposit intensity, engagement, volatility, overdraft activity, growth & activation, deposit-health box plot, repayment-trend segment |
| `scoring_personal` / `scoring_business` | **placeholder** predictor slides — see below |
| `deposit_score` | output distribution, risk categorisation, variables used, one alignment slide per variable, closure & charge-off, RDI cohort. Repeated per scored account type |
| `ds_logic` | logic overview, optional decision-tree image, per-rule conditions → score |
| `dbic` | program health & data integrity, calculation-log limit/override trend, Reg E opt-in & eligibility by type, notice items & fee collection, exception items by channel, daily feeds, granted limits & override effectiveness |
| `matrix` | section cover, account-type settings & OD status codes, override criteria, one slide per factor category, trending triggers, one slide per 2-D trend grid, tiers, limit notification, MRPC/CashPlease |
| `comm_strategies` | active strategies and their cadence |
| `strategic_refunds` | ranges, factors, tiers, daily maximums |
| `data_notes` | scope, branch classification, methodology, and everything that was skipped and why |

Ranked-branch charts are **native PowerPoint charts**, not images — the numbers
stay inspectable and editable when a client asks in the room. Categories are
passed ascending on purpose: PowerPoint plots the first category at the bottom,
so ascending puts the largest bar at the top.

### The ILS Scoring Summary section is placeholders, by design

The `Scoring Summary: <predictor>` slides (Days On Book, 33 Day Deposits, 33 Day
Deposit Count, Days OD, Windfall Ratio, ILS Limit) are currently emitted as
**correctly titled, correctly positioned placeholder slides** with the two drop
zones marked, because the computation is supplied separately and pasted in. The
deck comes out complete and in the right order.

To switch them on, implement one function — `compute_predictor` in
[`ils_review/scoring_summary.py`](ils_review/scoring_summary.py) — and return a
`PredictorResult`. Everything else already works and starts rendering real
slides the moment it returns data: the band table, the bubble chart with the
portfolio-average reference line, the section ordering and the anchoring.

The band edges and labels for all six predictors are already transcribed from
the house slides, so generated output will line up with the historical decks.
The agreed definitions are recorded there too, and are already stated on the
Data Notes slide:

- **Default** — a ZTrend notice where repayment took longer than
  `--default-days` (default **30**); a notice that never returned positive counts
  as a default.
- **Losses** — charge-off dollars attributed to the band.
- **Loss Rate** — Losses ÷ Collected Fees (verified against the house slides).
- **Default Rate** — defaulted notices ÷ notices in the band.

---

## The organization name goes everywhere

The template is a working copy of a previous client's review, so out of the box
it names *that* institution on the cover, on both section dividers and in
footers, and it carries an unfilled `BANK OR CU NAME` placeholder on the
partnership slide. Shipping either to a client is the sort of thing that gets
noticed in the first thirty seconds.

So **Organization reviewed** is not just a label for the generated slides. On
every build the app:

1. works out which institution the template currently names — the
   institution-shaped phrases (`… Bank`, `… Credit Union`, `… FCU`, `… Bancorp`,
   …) are counted and the most frequent one wins;
2. rewrites every occurrence of it to the organization being reviewed; and
3. fills the `BANK OR CU NAME` / `INSTITUTION NAME` style placeholders.

Details that matter:

- **Formatting survives.** PowerPoint splits a paragraph into runs at every
  formatting change, and the name is regularly split across them — the cover
  stores `['Horizon Bank', '  |  August ', '27', ', 2026']`. The replacement is
  run-aware, so the 40 pt bold name stays 40 pt bold.
- **Case and possessives** are handled: `HORIZON BANK` and `Horizon Bank's` both
  convert.
- **Third parties are left alone.** The industry-update slides mention SunTrust,
  Regions, Equity Bank and others; only the one detected incumbent is replaced.
- **Layouts and masters** are covered too, since a name there would surface on
  every slide using them.
- **It is idempotent** — re-running against an already-branded deck changes
  nothing, because the organization being reviewed is excluded from detection.
- **It never leaks the last client's name into the deliverable.** The Data Notes
  slide records that references were replaced, but not whose.

What was done is reported on the Data Notes slide, along with any remaining
fill-me placeholders the template still has (`CITY AND STATE`, `PRESENTER NAME`,
…), which are left for you rather than guessed at.

Controls: **Check…** next to the organization field previews what will be
replaced. On the Options tab, *Replace the institution name already in the
template* turns the pass off, and *Name currently in the template* forces the
incumbent when a template uses an unusual form. On the command line these are
`--no-rebrand` and `--template-org "Horizon Bank"`.

## The previous client's data slides are removed

Renaming the deck is only half the job. The template also carries ~23 slides of
the *previous* client's actual figures — pasted charts and tables (365-Day KPI
Rollup, Peer NSF/OD Fee Data, Collected Fee Trending, Eligibility Drilldowns,
Reg. E Opportunity, Branch Summary, …) plus their fee sheet, partnership
details, and observations.

Those are the dangerous ones: the numbers are burned into images, so the
rebrand pass cannot touch them. Left alone, the deck would show one
institution's chart under another's name. So by default they are **removed**,
and what went is listed on the Data Notes slide.

Slides are identified by **title** against `CLIENT_DATA_TITLES` in
`template.py` — title only, because the Agenda lists "Observations and
Recommended Actions" as a line item and a whole-slide match would delete the
agenda too. Generic industry and regulatory slides (CFPB, FDIC, class actions,
ILS-wide peer data), the section dividers and the back matter are all kept.

Three modes, via *Slides holding the PREVIOUS client's data* on the Options tab
or `--stale-data`:

| Mode | Effect |
|---|---|
| `remove` *(default)* | drop them entirely |
| `placeholder` | keep the slide and its title, clear the content, mark the drop zone |
| `keep` | leave them in place |

**`placeholder` is worth considering for a monthly cadence** — most of these
slides are produced outside this tool and pasted in each cycle, so an empty
titled slide preserves the running order and tells you what belongs there. A
blanked slide is marked in its notes and is **not** re-blanked on the next run,
so content you paste in survives a rebuild.

`keep` is an escape hatch only. On FNB Alaska it left 43 pasted images of
another bank's numbers in the deck.

## Confidentiality notice on the cover

Every build adds the standard CSI / Velocity confidentiality and trade-secret
notice to a text box at the foot of the cover slide, in the plain navy band
below the "Partnering for Success" block and clear of the artwork and the ILS
logo (8 pt white, at x 1.00 / y 10.20).

It is added **once** — a rebuild against an already-built deck, or a template
that already carries the notice, leaves it alone. The wording lives in
`CONFIDENTIALITY_NOTICE` in `theme.py`; `BuildConfig.cover_notice` overrides it
with your own text, and `""` (the Options tab checkbox, or `--no-cover-notice`)
skips it.

## Program health from the DBIC export

The DBIC (Daily Batch Integrity Check) file ships in every client folder and was
previously unused. It carries ~25 result sets with no section banners, so
[dbic.py](ils_review/dbic.py) identifies each one by its **column signature**
(a required subset, so a client whose export has extra columns still resolves).

Seven slides come out of it, and two of them replace numbers that are pasted in
by hand today:

- **Program health & data integrity** — nightly calculation success rate,
  accounts calculated, average granted limit, zero-limit share, and the
  data-integrity exception table (or a green "clean import" panel).
- **Calculation log trend** — average granted limit, accounts calculated,
  zero-limit accounts and overrides, one point per nightly run.
- **Eligibility & Reg E opt-in by account type** ← the Eligibility Drilldown data.
- **Notice items & fee collection** — fees assessed vs. available, i.e. the
  collection rate and the dollars forgone.
- **Exception items by channel** ← the Trends in Exception Items data.
- **Daily feeds** — deposits, overdrawn accounts, declines, with business-day
  feed-gap detection.
- **Granted limits & override effectiveness** — accounts by limit, plus what
  each override rule actually caught (measured account age and days overdrawn).

Daily charts plot **business days only**. Weekend rows are blank by design, and
a line chart renders each blank as a break — 61 days otherwise draws as nine
disconnected segments that read as erratic data rather than as a closed bank.
The weekend flags drive the feed-gap check instead.

Skips cleanly when no DBIC file is present (UCCU has none).

## Branch classification is automatic

Which branch codes are back-office vs. digital vs. physical retail used to be
eyeballed once per institution. It is now inferred, in this order:

1. explicit overrides (**Branches** tab, or `--exclude-branches` /
   `--digital-branches` / `--retail-branches`)
2. the branch **name**, matched against a digital vocabulary (Online, eBranch,
   ITM, Virtual, Remote…) and a back-office one (Corporate, Administration,
   Call Center, Collections, IT, Mortgage, Commercial…)
3. any single code holding **more than 20%** of open accounts — that is the
   core's default holding branch, never a real location, and leaving it in
   flattens every per-branch chart
4. codes with fewer than 25 open accounts, set aside as operational noise

For Utah Community CU this correctly finds all 27 physical branches, classifies
Online Account Opening and ITM Branch as digital, and holds out Corporate
(54% of open accounts), Administration, Call Center and 17 more. The
classification and the largest held-out units are stated on the Data Notes slide.

**Digital channels count as branches.** Only back-office codes are held out of
the branch metrics; online, virtual and e-service channels originate and hold
real accounts, so excluding them understates the portfolio and hides the
origination channel entirely. For Meritrust, Virtual Banking was the largest
single originator of 2025 personal accounts (1,865) and Internet Application
carries the highest deposit intensity ($8,079/account) — neither appeared at all
while digital was excluded. Pass `--exclude-digital` (or clear the checkbox on
the **Branches** tab) for a physical-branch-only view; the slide subtitles and
Data Notes state which scope was used.

Override only when the inference gets one wrong.

## Options worth knowing

| Option | Default | Effect |
|---|---|---|
| Replace previously generated slides | on | a re-run replaces rather than duplicates; **leave this on** |
| Replace the template's institution name | on | rewrites the previous client's name to the organization reviewed; **leave this on** |
| Place slides at section anchors | on | off appends everything at the end |
| Include digital channels in the branch metrics | on | off (`--exclude-digital`) gives a physical-branch-only view |
| Branches per personal / business chart | 25 / 20 | ranked by account count |
| Growth year | last full calendar year | the year the growth slide measures |
| Min notice observations for volatility | 8 | accounts below this get no CV estimate |
| Repayment days before a notice is a default | 30 | the Scoring Summary default definition |
| Show all rows | off | paginate long tables instead of capping them |

---

## How re-running works

Every generated slide is tagged with a marker in its **notes**. On the next run
the tagged slides are removed before rebuilding, so the deck can be regenerated
repeatedly without piling up duplicates. Slides left in the template by the
*older* tools carry no marker, so those are recognised by their text instead
(see `LEGACY_MARKERS` in `template.py`) — which is how a template still holding
the previous client's analysis gets cleaned out on first use.

This is verified: building the deck, then rebuilding using that output as the
template, produces the same slide count.

## Package layout

```
ils_review/
  theme.py            canvas, house palette/type, Deck object, slide primitives
  template.py         open the template, resolve layouts, tag / purge / anchor / place
  config.py           BuildConfig + the section registry (needs, anchors)
  ils_data.py         one column-selective load; branch classification
  branch_metrics.py   branch deposit-behaviour and overdraft metrics
  branch_slides.py    branch section slides
  charts.py           native PowerPoint charts + the matplotlib box plot / bubble chart
  matrix_report.py    Matrix Validation .txt parser (both export styles)
  matrix_data.py      matrix extraction + trend-grid inference
  matrix_slides.py    matrix validation slides
  dbic.py             DBIC parser + program-health metrics
  dbic_slides.py      program-health slides
  rebrand.py          detect the template's institution name and rewrite it
  ds_analysis.py      Deposit Score output analysis
  ds_charts.py        Deposit Score charts
  ds_slides.py        Deposit Score slides
  ds_logic.py         Deposit Score rule-logic slides
  scoring_summary.py  predictor registry + placeholders + the compute_predictor hook
  build.py            load -> build sections -> place -> save
  cli.py              command line
  gui.py              desktop app
```

## Requirements

Python 3.9+ with `python-pptx`, `pandas` and `matplotlib`. `tkinter` ships with
standard Python on Windows. `Generate ILS Program Review.bat` installs the three
packages on first run and gives a readable message if Python itself is missing.

```bash
pip install python-pptx pandas matplotlib
```

## Known limitations

- **The Scoring Summary section is placeholders** until `compute_predictor` is
  implemented (see above). This is deliberate, not an oversight.
- `RepaymentTrendCount33`, the intended direct trend-fire counter, has been empty
  in every extract seen. The repayment-trend slide uses
  `avgrepaymentrate is not null` as the working proxy and says which one it used.
- REV's export truncates several rule CALC strings at 256 characters, so those
  rules' assigned scores are genuinely unrecoverable and render as ⚠ rather than
  a guessed value. Re-exporting query 1822 with a wider CALC column fixes it with
  no code change.
- Stale-slide detection is title-based. A house data slide that gets renamed
  won't be recognised — add its title to `CLIENT_DATA_TITLES` in `template.py`.
  The Data Notes slide always lists what was removed, so a miss is visible.
- Anchors are matched on slide text, so a heavily re-cut template can miss one.
  A miss is not silent: the section is appended at the end with its own divider,
  and the miss is reported on the Data Notes slide.
- No automated test suite. Validation is end-to-end runs against two real client
  extracts with visual QA of the rendered slides, plus smoke, degradation and
  idempotency checks:
  - **Utah Community CU** (1206) — 41 generated slides in an 83-slide deck.
    Exercises branch behaviour, matrix validation, communication strategies, and
    the skip paths (empty `Deposit_Score`, no Deposit Score matrix sections, no
    strategic-refund ranges).
  - **REV Credit Union** — 65 generated slides in a 107-slide deck. Exercises the
    Deposit Score output analysis and rule logic against a genuinely populated
    score (49,166 scored accounts, 17 enabled rules, 3 account types), including
    alignment variables taken from the rules rather than the defaults.
  - **First National Bank Alaska** (FNB) — 46 generated slides in a 65-slide
    deck. Exercises three account types (`Personal`, `Business`, `Status40`), a
    client with no tier table, a 271-row trending model, the DBIC section, and
    the full stale-data removal: all 23 previous-client slides gone, zero
    residual references.
  - **First County Bank** (FCB) — 45 generated slides in a 64-slide deck.
    Exercises the DBIC section end to end (18 recognised sections, a clean
    integrity check, 44 nightly runs) and mixed-format branch codes.
