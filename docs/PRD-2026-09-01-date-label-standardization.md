# PRD — one date vocabulary on every chart axis

Date: 2026-09-01
Owner: Aaron Burgard
Status: Proposed. Nothing implemented.

---

## Problem

Nine distinct forms of "July 2026" are rendered on chart axes across the three
programs. Every one is produced by a different piece of string surgery in a
different file, and no two charts on the same slide are guaranteed to agree.

Feed `Jul 2026` (or the pack's `Jul 26`) through each renderer and this is what
lands on the slide:

| Chart | File | Rendered tick | How it is derived |
| --- | --- | --- | --- |
| image5 Monthly Incremental Revenue | `charts_gen.py:57` | `Jul` | `m.split()[0]` — **year discarded** |
| image9 Sustained Response | `charts_gen.py:119` | `Jul '26` | `f"{a} '{b[2:]}"` |
| image10/31 Before & After | `charts_gen.py:196,140` | `Jul26` | `a + b[2:]` |
| image12 Swipes & Spend (36 mo) | `charts_gen.py:235` | `Jul26` | `a + b[2:]` |
| image17 Program Reach | `charts_gen.py:281` | `Jul'26` | `.replace(' 20',"'")` |
| image26 Openings vs Closures | `charts_gen.py:377` | `Jul'26` | `.replace(' ',"'")` |
| image29 NSF/OD Trend | `charts_gen.py:413` | `Jul26` | `c[:3]+c[-2:]` |
| image30 Reg E by Vintage | `charts_gen.py:423` | `2026`, `Pre-2018` | year axis (correct, but a fourth vocabulary) |
| ICS Referral Trend | `ics_charts_gen.py:46` | *whatever VIP wrote* | passed through unvalidated |
| ICS Monthly Detail (6 charts) | `ics_charts_gen.py:111,121` | `Jul 26` | `%b %y` from the workbook |
| ICS per-account grid | `ics_charts_gen.py:134` | `Jul` | `mm.split()[0]` — **year discarded** |
| MRPC Enrollments / Performance / Retention / Revenue | `mrpc_charts_gen.py:92,159,174,234` | *whatever VIP wrote* | passed through unvalidated |
| MRPC Annual Revenue | `mrpc_charts_gen.py:205` | `2025`, `2026 YTD` | year axis |
| ARS window pills | `build_ars_gen.py:202,1340` | `07-2026` | `%m-%Y`, to fit the pill box |

Three consequences, in order of how much they cost:

**A combined deck contradicts itself.** ARS section reads `Jul26`, the ICS
section beside it reads `Jul 26`, the MRPC section reads whatever the VIP
dashboard exported that month. Same client, same deck, same month, three
spellings. `assemble_combined.py` cannot fix this — by the time it runs the
labels are pixels inside a PNG.

**Two charts drop the year entirely.** image5 renders a rolling 12-month window,
which always crosses a year boundary, as `Aug Sep Oct Nov Dec Jan Feb …` with
nothing saying which January. The ICS per-account-per-month grid does the same
to a cohort series that routinely spans `Nov 25 → Jul 26` — and that chart's
whole point is that older cohorts have had longer to earn.

**Six charts re-derive a label by slicing a string.** `c[:3]+c[-2:]` is correct
only while the upstream pack keeps emitting `%b %y`. Nothing enforces that, and
`metrics_gen.py` already emits three different forms (`%b %Y` at line 78,
`%b %y` at 536 and 656, bare `%b` at 522). The renderer and the producer agree
by coincidence, restated in seven places.

### Why the existing guardrails do not catch it

They are all aimed elsewhere, and each stops one step short:

- `brand.py` consolidated color. `periods.py` consolidated the *prose* date
  phrases — pills, captions, spans. Axis tick labels are the one date surface
  neither owns, and `periods.py` is imported by exactly zero chart renderers.
- `validate_deck.period_findings` reads paragraphs. A tick label is inside a
  PNG; the validator cannot see it and never will.
- `qa_all.py` layout drift fingerprints geometry, not glyphs.
- The swap gate fires when a swap matches *nothing*. Every one of these labels
  renders successfully. They are just spelled differently.

So the check has to live at the producer. There is no deck-side rule that can
reach these.

## Success criteria

1. Every time axis in every program renders one token form, and a combined deck
   spells the month identically in all three sections.
2. No chart drops the year.
3. No renderer derives a label by slicing a string. Series carry a machine
   token; the renderer formats it.
4. A VIP or workbook month the pipeline cannot parse stops the build and names
   the field — it is never passed through to a slide unread.
5. `pytest tests/` fails if any renderer emits a tick outside the vocabulary.

## The standard

**Month axes: `Jul '26`.** Three-letter month, space, apostrophe, two-digit
year. Unambiguous about the year, which `Jul` is not; compact enough for a
36-tick axis, which `Jul 2026` is not; and already the closest thing to a
plurality among the nine forms in use.

**Year axes keep the 4-digit year** — `2024`, `2025`, `2026 YTD`, `Pre-2018`.
Reg E by Vintage and MRPC Annual Revenue are genuinely annual series. Stating
this in `STYLE.md` stops someone "standardizing" them into `'26` later.

**The year is never dropped.** Not on a 12-month window, not on a cohort grid,
not when the series happens to sit inside one calendar year. A form that
changes shape with the data is a form that is inconsistent by construction.

**Pills adopt the same token.** `07-2026` exists only because `Jul 2026`
overflowed the pill box. `Jul '26` is the same seven characters as `07-2026`
and removes a form for free. The descriptive prefixes STYLE.md already
mandates (`PTD ·`, `Avg:`, `Trailing 12 months`) are unchanged.

**Density and rotation are derived, not typed per chart.** One helper decides
from the tick count: ≤8 ticks horizontal; 9–14 horizontal if `textfit`
measures them as fitting, else 30°; >14 thinned to ~12 ticks at 45°. The
newest month always carries a tick — `c_openings` already special-cases this
and every other series should.

## Plan

**Phase 0 — the two helpers.** `periods.axis_label(token)` and
`axis_labels(tokens)`, pure-string, in `periods.py`: it already parses all four
month forms via `parse_month`, and `validate_deck.py` imports it without the
build tree, so matplotlib must stay out. The tick placement — thinning,
rotation, endpoint pinning — goes in a new `build/axis.py` beside `shapes.py`,
which all three programs can reach. `parse_month` returning `None` raises with
the field name; it never falls through to the raw string.

**Phase 1 — producers emit tokens.** `metrics_gen`, `base_tab_extract`,
`extract_base_gen` and `ics_workbook_extract` add a token series (`Jul26`,
`Period.token()`) alongside the label series they already write. Additive, so
nothing breaks mid-migration. The VIP dashboards we do not control, so their
months are normalized on read through `parse_month` — which is the reason this
phase is cheap: the parser already accepts every form VIP has produced.

**Phase 2 — renderers convert, one program at a time.** ARS is 7 charts, ICS 3
call sites covering 8 charts, MRPC 4. Run `qa_all.py` after each program and
`--snapshot` the intended drift; the fingerprints will move, and moving them
one program at a time is what keeps the drift readable.

**Phase 3 — pills.** `build_ars_gen.py:202` and `:1340`, plus the STYLE.md
section.

**Phase 4 — the gate.** Per the standing rule, add the check that would have
caught it. A validator rule cannot read a PNG, so the test renders every chart
from the existing synthetic fixtures (`tests/fixtures/make_odd.py`,
`make_base.py`) and asserts every x-tick text matches `^[A-Z][a-z]{2} '\d{2}$`
or the year form. `tests/test_mrpc_charts.py` and the golden-deck test already
establish the pattern.

Phases 0–1 are additive and land together. Phase 2 is the only one that changes
a shipped deck's face, and it is reversible per program.

## Two defects found while surveying

Both are month literals typed into logic, which is the same root cause one
layer down. Neither is a chart-label problem, but both surfaced here and both
ship silently.

**`metrics_gen.py:540` — `nsf_yoy` is hardcoded to `Jun 25`.**

```python
jun25 = next((x for x in nsf_series if x[0]=='Jun 25'), None); jun26 = nsf_series[-1]
M['nsf_yoy'] = round(100*(jun26[1]-jun25[1])/jun25[1]) if jun25 else 0
```

It compares the literal June-2025 row against the *last* row of the series, so
it is a year-over-year figure only for a June-2026 deck. A July-2026 deck
reports a 13-month change labelled YoY. A client whose NSF series starts after
June 2025 gets `None`, and the slide renders `0%` — a phantom zero, which
CLAUDE.md bans outright. It reaches the slide through `set_exact`
(`build_ars_gen.py:838`), so the swap gate passes. Fix: take the row 12 months
back from the series end via `Period.window(13)`.

**`metrics_gen.py:491` — Reg E vintage years stop at 2026.**

```python
years = ['Pre-2018'] + [str(y) for y in range(2018, 2027)]
```

An account opened in January 2027 is bucketed under key `'2027'`, which is not
in `years`, so it is counted and then silently dropped from the chart. Fix:
derive the upper bound from the snapshot month.

## Open

- `Jul '26` uses the ASCII apostrophe. A typographic `’` is the correct mark for
  a client-facing deck and both bundled faces carry it; it is one constant in
  `periods.py` either way. Aaron's call.
- Whether Phase 2 ships across a month boundary or all at once. Shipping it
  mid-month means one client's August deck and September deck spell the month
  differently, which is the exact confusion this removes.
