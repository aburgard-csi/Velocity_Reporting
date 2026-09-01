# PRD — one date vocabulary on every chart axis

Date: 2026-09-01
Owner: Aaron Burgard
Status: COMPLETE, 2026-09-01. All five phases shipped. Every time axis and every
window pill in all three programs renders `Jul'26`, and `tests/test_axis_gate.py`
fails the build if one does not. The two defects below are fixed.

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
| image17 Program Reach | `charts_gen.py:281` | `Jul'26` | `.replace(' 20',"'")` — already the target form |
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

**Month axes: `Jul'26`.** Three-letter month, ASCII apostrophe, two-digit year,
no space (Aaron, 2026-09-01). Unambiguous about the year, which `Jul` is not;
the narrowest of the forms that keep the year, which matters most on the 36-tick
axes; and already in use on Program Reach and Openings vs Closures.

**Year axes keep the 4-digit year** — `2024`, `2025`, `2026 YTD`, `Pre-2018`.
Reg E by Vintage and MRPC Annual Revenue are genuinely annual series. Stating
this in `STYLE.md` stops someone "standardizing" them into `'26` later.

**The year is never dropped.** Not on a 12-month window, not on a cohort grid,
not when the series happens to sit inside one calendar year. A form that
changes shape with the data is a form that is inconsistent by construction.

**Pills adopt the same token.** `07-2026` exists only because `Jul 2026`
overflowed the pill box. `Jul'26` is shorter still and removes a form for free.
The descriptive prefixes STYLE.md already mandates (`PTD ·`, `Avg:`,
`Trailing 12 months`) are unchanged.

**Density and rotation are derived, not typed per chart.** One helper decides
from the tick count: ≤8 ticks horizontal; 9–14 horizontal if `textfit`
measures them as fitting, else 30°; >14 thinned to ~12 ticks at 45°. The
newest month always carries a tick — `c_openings` already special-cases this
and every other series should.

## Plan

**Phase 0 — the two helpers. SHIPPED.** `periods.axis_label(token)` and
`axis_labels(tokens)`, pure-string, in `periods.py`: it already parses all four
month forms via `parse_month`, and `validate_deck.py` imports it without the
build tree, so matplotlib must stay out. The tick placement — thinning,
rotation, endpoint pinning — goes in a new `build/axis.py` beside `shapes.py`,
which all three programs can reach. `parse_month` returning `None` raises with
the field name; it never falls through to the raw string.

**Phase 1 — producers emit tokens. SHIPPED.** `metrics_gen`, `base_tab_extract`,
`extract_base_gen` and `ics_workbook_extract` each write an `axis_months` block
of ODD tokens beside the label series they already emit. Additive: no existing
key changed, so nothing breaks mid-migration.

`parse_month` gained the two forms the pipeline carries but could not read —
`Jul 26` (every `%b %y` series, and the ICS workbook) and `Jul'26` (so a rendered
tick round-trips). The VIP dashboards we do not control; their months are
normalized on read by `month_ticks`. **Whether every VIP export parses is still not
proven** — no VIP data was reachable from the machine this was written on, and
Phase 2 did not change that. The ICS referral trend and all four MRPC month
series now render through the parser, and an unreadable month raises naming the
field. Phase 2 added the first tests those charts have ever had, covering
`Jul 25`, `Jul 2025`, `Jul25` and `2025-07`; if VIP exports something else, the
first build after this fails loudly with the field and the value in the message,
and the fix is one line in `_TOKEN_FORMS`.

The base extractors emit their tokens at source from the workbook's own
datetimes. `metrics_gen` derives its from the series rows instead: several of
those loops skip a month, and a parallel list that can fall out of step with its
own rows is a worse bug than the parse it avoids. `take_branch_monthly` is the
exception — its labels are bare `%b` with no year to recover, so its tokens come
from the months themselves.

**Phase 2 — renderers convert, one program at a time. SHIPPED.** ARS was 8 call sites, ICS 4
covering 8 charts, MRPC 4. No layout drift resulted — the fingerprints read
geometry and every change is inside a PNG.

Two rules had to be corrected against what the pixels actually did:

*One knob, not two.* The tick cap and the thinning threshold started as separate
numbers, which made the cap inert for any series short enough to sit under the
threshold — exactly the fifteen-mailing case the cap existed for. The half-width
Before & After panels would have gone back to labelling every mailing. They are
now one number, `max_ticks`, defaulting to 14 and passed as 8 by those panels.

*Rotated labels collide on height, not width.* Falling through to 30 degrees
whenever the width test failed put the ICS per-account grid's 16pt labels on top
of one another: rotated ticks are parallel lines, and what separates them is
`track x sin(angle)` against the height of the type. The angle is now measured at
each step — flat, then 30, then 45 — instead of 30 being a catch-all.

Visible changes beyond the label form are listed in CHANGELOG under 2026-09-01.

**Phase 3 — pills. SHIPPED.** Four pills, not two: the survey missed the SM Monthly Summary
window and the Debit Usage average window, both also on `%m-%Y`. All four go
through `periods.axis_window()`, which lives there rather than in the builder so
it can be tested — the MM path the Lift Matrix and Debit Usage pills sit on is
not exercised by the golden deck, which builds the SM path.

Two defects surfaced in the rewrite. The Lift Matrix pill guarded on `"-" in`
the reformatted string, which really meant "did the reformat happen" — a test
that stops meaning that the moment the format has no dash in it, so a naive swap
would have silently fallen back to the raw workbook label. And the Debit Usage
pill stepped back two months with a hand-rolled `while _m < 1` loop instead of
`periods.shift`, which is the kind of hand-derived window CLAUDE.md bans.

`PTD ·` pills keep the full month. They name a point in time in prose, not a
window inside a narrow box, and STYLE.md mandates their form explicitly.

**Phase 4 — the gate. SHIPPED.** Per the standing rule, add the check that would have
caught it. `tests/test_axis_gate.py`. It intercepts `Figure.savefig`,
renders every month-axis chart in all three programs, and reads the ticks back
off the figures. The rule is: **any tick that NAMES a month must be in the one
form** — `periods.names_a_month` decides which ticks are in scope, so a branch
number or a swipe band is ignored while a bare `Jul` is caught. Verified in both
directions: reintroducing `m.split()[0]` fails it, naming the chart and the
ticks.

Two static checks sit beside it, because a runtime gate only covers charts a
fixture reaches: the retired slicing idioms may not reappear in any chart
module, and the builder may not format `%m-%Y`. Getting those to work took two
tries — a token scrubber that space-joins turns `m.split()[0]` into
`m . split ( ) [ 0 ]`, which no punctuation pattern matches, and dropping all
string literals makes the `%m-%Y` check pass for the wrong reason. They read
`ast.unparse` of the tree with docstrings stripped, so comments and docstrings
are gone and every other literal survives. Both were confirmed to fail on a
reintroduced defect.

The gate runs inside `qa_all.py`, which already runs `pytest tests/` as step 0.

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

## Decided

- **Axis token: `Jul'26`** — no space, ASCII apostrophe (Aaron, 2026-09-01).
- **Phase 2 ships all at once, not one program at a time** (Aaron, 2026-09-01).
  All three programs converted in a single commit, so no client's next deck can
  spell the month one way in its ARS section and another in its ICS section —
  which is the confusion this removes.

## Open

- Nothing blocking. Phase 3 (the two ARS window pills, `build_ars_gen.py:202`
  and `:1340`) and Phase 4 (the render-every-chart gate) remain.
