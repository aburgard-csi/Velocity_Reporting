<!-- Ported from v5 02-Scripts/ils/kickoff_analysis/README.md at 7ba1e63, unchanged. It describes v5: in RPE the input is Inputs/ILS Kickoff/<id>/, the output Build Artifacts/ils/kickoff/<id>/<period>/ (never Outputs), and the run is `cd build; python -m ils_pipeline.kickoff.run <id> <yyyy-mm>` or ils_pipeline/kickoff_input.run_kickoff (see kickoff_input.py). The tests are tests/test_ils_kickoff_*.py. -->
# ILS Kickoff Analysis

The kickoff conversation, from one extract: how the book is made up, where
the NSF activity sits, and how overdraft is configured. Produces a 19-tab
workbook and, on request, a 45-slide deck.

Its own deliverable. Never a chapter of an ARS deck, never paired with ARS
data.

---

## Run it

```powershell
cd 02-Scripts
python -m ils.kickoff_analysis.run {client} {period} --data-root "..\01-Data\ILS" --deck
```

`period` is `YYYY-MM`. At a terminal it asks for the client's codes before
computing anything (below). Without `--deck` you get the workbook only.

| flag | |
|---|---|
| `--deck` | also build the deck. Off by default |
| `--output-dir` | default `03-Output/ILS/{period}/{client}`. A folder naming a **different** client is refused |
| `--use-defaults` | skip the prompt and accept the defaults. Say so on purpose |
| `--personal-code` `--business-code` `--open-code` | the raw values in this client's file |
| `--eligible-stat-codes` | comma-separated. Which Stat Code means OD-eligible |
| `--rege-opt-in` | comma-separated Reg E Flag value(s) meaning the member opted in |

Passing any code flag turns the prompt off.

### Input

```
{data_root}\{period}\{client}\{client}_OneTimeData_*.csv     (or .xlsx)
```

Newest by the date in the filename wins, so a corrected extract supersedes
the one it replaces. An undated file sorts below every dated one.

### Output

| | |
|---|---|
| `{client} - ILS Kickoff Report Data-{MON}{YY}.xlsx` | 19 tabs, one per analysis, formatted |
| `{client} - ILS Kickoff {period}.pptx` | with `--deck`: cover, provenance, 3 section dividers, 19 analysis slides, an appendix table per analysis, and a warnings slide when the run has warnings |

---

## The codes are the client's answer, not ours

The run asks five questions before it computes anything, and prints what it
used. The defaults came from one notebook for one client: on 1840 the Reg E
rule matched 0 of 4,559 accounts because nobody was asked, and the run said
so only after the workbook had been written.

**Reg E opt-in is a separate question from OD eligibility.** Only opt-in is
asked; everything else counts as opted out. Asking for the complement made
the operator enumerate a list they do not think in.

`rege_opt_in` is **deliberately empty by default**. `"Y" means opted in` is a
guess that happens to hold on some clients — 1842 carries only `D` and no
yeses. An unconfirmed mapping is reported, never guessed.

There is **no config file for ILS**, in either engine. Codes are per-run
inputs recorded in the run's own output, because every core spells them
differently and a wrong guess poisons every count.

---

## What the run refuses to do

Each of these was a wrong number on a slide before it was a rule.

| | |
|---|---|
| **Present a pay rate it cannot stand behind** | If paid equals total across the whole book, `pay_rate_warnings` fires *before any table is computed* and names the unmapped columns that may hold the real total. On 1842, `Total Items` is mismapped at source, so every pay rate reads 100% and none of them is presentable. That is a client conversation, not a code fix |
| **Present a split that is not a split** | If the OD-eligibility rule matches all or none of the accounts, the Reg E slides are kept **off the deck** and left in the workbook, where someone can look at why |
| **Silently drop an account** | `segment_warnings` reports any open account in neither segment, and names the unmatched values |
| **Guess what an item column holds** | `item_column_relationships` prints what the extract's item columns actually contain, so the next run tells you which case the client is in |
| **Render an analysis that did not run** | A manifest entry with no data is absent from the deck, never rendered empty |

---

## Layout

| | |
|---|---|
| `core/io.py` | loading, column canonicalisation, `CodeConfig`, every warning |
| `metrics/` | one module per analysis family. Takes a pre-filtered segment, returns a table |
| `deck/slides.py` | the slide manifest, the three layouts, the content band, the appendix, provenance |
| `deck/forms.py` | one chart form per analysis, the captions, the headlines, the rail tiles |
| `deck/report.py` | the Excel workbook |
| `deck/charts.py` | the five legacy notebook renderers, still used for the workbook's embedded charts |
| `run.py` | the entry point and the order the story is told in |

Chart forms come from the shared library through `deckkit`, never from
`ars.deck` directly. **Look at `00-Instructions/chart-catalog.html` before
choosing a form** — it renders every form through the live function, and it
is how you find out what units a form prints before you hand it yours.

### The manifest is the story order

`deck/slides.py: SLIDE_MANIFEST`. Adding an analysis means adding one entry —
key, section — and nothing else in that module changes.

`key` matches the sheet name the run emits, which is what keeps the deck and
the workbook from drifting: a test fails if a sheet exists with no slide, or
a slide with no sheet.

It carries **no headline**. A headline states the slide's finding *with its
number*, so it can only be built where the numbers are, in
`forms.HEADLINES` — one per slide, and a personal/business pair may share
one because they ask the same question of a different segment. The field
that used to sit here declared "what the slide asserts" on all nineteen
entries and was read by nothing.

### The three layouts

Assigned by what the slide is *for* (`deck/slides.py: LAYOUTS`). One layout on
nineteen slides is one template wearing nineteen headlines.

| | | |
|---|---:|---|
| `rail` | 11 | chart plus three callout tiles — a finding with its supporting numbers beside it |
| `full` | 5 | full-bleed chart — a distribution whose shape is the point, with too many bands for three tiles |
| `hero` | 3 | one number at slide scale, chart beneath |

All three place their chart against **one content band**, `BAND_TOP` to
`BAND_BOTTOM`, taken from the shared grid rather than copied from it. A form
is authored at the aspect of the slot it lands in (`charts.FIG_W_RAIL` /
`FIG_H_RAIL`, `FIG_W_FULL` / `FIG_H_FULL`) so that it fills that band and its
type is the size it was drawn at.

---

## Checking a change to the deck

**Render it and look at it.** Not the geometry, not the element counts, not
the tests — all three were green while the deck printed `$74` over a 74% pay
rate and put its caption on top of the axis labels.

```bash
/opt/homebrew/bin/soffice --headless --convert-to pdf --outdir <dir> <deck>.pptx
```

Three minutes for 45 slides on the Mac, then read the PDF. Windows: open the
deck.

The suite covers what a chart *says* as well as where it sits — every string
a form draws is captured at `_save` and checked against the vocabulary of
other products, because six shared forms were hardcoded to the ARS deck's
units and the ILS deck fed them ILS numbers.

```powershell
python -m pytest tests/test_ils_kickoff.py tests/test_ils_kickoff_deck.py -q
```

---

## Day 2 analyses (RPE addition, 2026-10-28)

`metrics/day2.py`, ported from the ILS Kickoff Day 2 app, the analysis only. Six tabs after the
nineteen above, each a workbook tab and a deck slide under the "Day 2 read-out" section: Day 2
Highlights, Day 2 OD Status Reg E In (+ Biz), Day 2 Year Opened (+ Biz), Day 2 Reg E by Year Opened.
They use the same `CodeConfig` as every other tab and never guess a code.

| Slide | Form (`deck/forms.py`) | Headline states |
|---|---|---|
| Day 2 Highlights | `rag_chips`, full width: one chip per measure that has a target in `day2.py` | personal OD/NSF user share against the CFPB 27% |
| Day 2 OD Status Reg E In | `rate_bars`: pay rate by OD status, opt-ins under each | opt-ins and the status most sit on |
| Day 2 OD Status Reg E In (Biz) | `donut` | the same, business |
| Day 2 Year Opened | `tier_bars`: % no longer open by year opened | share of the book no longer open; the cohort that lost the most accounts |
| Day 2 Year Opened (Biz) | `grouped_bars`: open against not open | the same, business |
| Day 2 Reg E by Year Opened | `vintage_line`: opt-in rate by year against the whole book | newest cohort's opt-in rate against the oldest; no rate without a confirmed opt-in value |

Chip colours read each measure against `day2.py`'s own constants (CFPB 27%, pay ratio 90%,
eligibility 80% floor / 90% preferred); no threshold is new. Tests: `tests/test_ils_kickoff_day2.py`.

---

## Open

- `Reg E by OD Eligibility` is a cross-tab drawn with `funnel`, which is a
  form for successive narrowing. The rows do not nest.
- Four of James's slide notes are still open (#187): the title slide, what
  "account files" means on the provenance slide, and the waffle axis.
