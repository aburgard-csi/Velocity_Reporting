---
name: summit-one-pager
description: Build an Executive Summit ARS one-pager (8.5x11 print handout) for a client who is ATTENDING a Summit. Use only when Aaron asks for a Summit one-pager for named attendees. Never run on a schedule, never for the whole roster, and never choose the metrics yourself - Aaron decides which story each attendee sees. Gathers the figures, shows them neutrally, asks, then builds and hands over the file.
---

# Executive Summit one-pager

CLAUDE.md, "Executive Summit one-pagers - NOT a canned deliverable": the one-pager is hand-built, per attendee, and
the point is to show THAT attendee their strongest metrics at THAT Summit. Which metrics is Aaron's judgement; there is no
correct set to automate toward. This skill is the checklist around that judgement, not a way around it.

## Do not

- Build one for a client Aaron has not named, or "the full roster so they are ready". Ask which attendees need one.
- Add it to `scripts/build_month.py` or any schedule. The monthly reviews are every client, every month, no curation.
- Rank, highlight or drop figures because they "look best". Present them in a fixed order and let Aaron choose.
- Build for a client with no ARS (the one-pager is ARS-only), or whose ARS deck for the period has not been built.
- Put the file in `Outputs/` (finished decks only) or send it to anyone. Save it under `Build Artifacts/summit/<yyyy.mm>/`
  and give Aaron the path (SendUserFile if he is remote).

## 1. Confirm what is being built

Ask, in one message, for anything not already said: **which attendees** (client ids), **which Summit** (the month it is
presented in sets the header: `RPE_PERIOD`, not the data month), and **the data period** to use. If the client is on the Summit list but has
no ARS (`clients.md`), say so and skip it.

## 2. Check the inputs exist

For each attendee, the ARS build for the period must already have written its data pack. `python scripts/ars_launcher.py status <id>`
names what is missing; if no ARS deck exists for the period, build it first (`build <id>`), and tell Aaron.

```
<RPE_DATA_ROOT>\Build Artifacts\launcher\<yyyy.mm>\<id>\base.json            # workbook financials
<RPE_DATA_ROOT>\Build Artifacts\launcher\<yyyy.mm>\<id>\oddd\oddd_metrics.json
<RPE_DATA_ROOT>\Inputs\ODDD\<id>_ODDD.zip                                    # for the responder measure
```

(Open the `*_launcher_result.json` beside them if a name differs; resolve paths through `rpe_env`, never hardcode.)

## 3. Gather the figures, show them, ask

```
.venv/Scripts/python build/ars_pipeline/responder_activity.py "<ODDD.zip>" <scratch>/<id>_resp.json
```

The responder before/after is `before_after.compute`, the same function the monthly deck uses: if the figure here and the client's
deck disagree, that is a defect to report, not to pick between.

Then show Aaron, per attendee, a plain table of what the one-pager prints, in the page's own order, no ranking and no
adjectives: revenue program to date; net profit; return on program cost; customers reached and repeat-responder share;
mailings and months; accounts enrolled vs eligible; Reg E opt-in rate; last-12-month revenue and best month; 36-month debit spend change
and cards in force; responder spend before vs after; transactions over the ask. Mark any figure that is missing or from an incomplete
month (`month_complete`), stated rather than zeroed. Comparisons use complete months only, and the +/-2% band words apply
to any sentence you write (almost flat / state the increase / did not have an impact).

Ask: **"This is the page as `build_ars_onepager.py` lays it out today. Right story for <client>, or what should change?"**
The layout is fixed in code (four tiles, three charts). If Aaron wants a different set of metrics, a tile swapped or a figure left
off, that is an edit to `build_ars_onepager.py`: propose the change, make it on a branch with a test, and let him review it. Never edit it
on the way to a deliverable and never leave it changed for the next attendee.

## 4. Build

Only after Aaron has said the figures are right:

```
$env:RPE_PERIOD = "<yyyy.mm of the Summit>"
.venv/Scripts/python build/ars_pipeline/build_ars_onepager.py <base.json> <oddd_metrics.json> templates/ars_template.pptx `
    <scratch>/assets "<RPE_DATA_ROOT>\Build Artifacts\summit\<yyyy.mm>\<id>-<yyyy.mm>-Summit One-Pager-<Client>.pptx" <id>_resp.json
```

It deliberately skips `restyle_fonts`, `fit_layout` and `validate_deck` (print page, not the 13.33 x 7.5 deck contract). So
check by hand: open the file and look at it (render it, do not trust the code), confirm the header month is the Summit month, the
client name and logo are the attendee's, and the notes carry the client's own sources and no other client's (grep for the reference
client: zero hits). Report what you checked and what you did not.

## 5. Hand over

Give Aaron the file path, the figures it printed, and anything unusual (an incomplete month left out, a stated gap). Do not mark
anything delivered or sent. If a figure surprised you, say so plainly and let him decide.

## Gotchas

- `RPE_PERIOD` (or the output file name's `<yyyy.mm>`) sets the header month. Without it the build stops rather than use the clock.
- A Summit is a couple of times a year and the date lives on `build/assets/summit_slide.pptx`; that slide is unrelated to the one-pager.
- Never import `metrics_gen` (it reads `sys.argv` at import and RUNS). `before_after` and `odd_rows` are the import-safe pieces.
