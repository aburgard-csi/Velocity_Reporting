---
name: ars-deck
description: >-
  Build a client's ARS (Account Revenue Solution®) Executive Review deck. Use when a
  request names an ARS client and month, or asks for an ARS results/review deck. Runs
  monthly for every ARS client. Builds from the stripped `templates/ars_template.pptx`
  shell via `build/ars_pipeline/build_ars_gen.py`, adds the ARS Appendix as its final
  module, validates, and saves to the pipeline `Outputs/` folder. ARS is ODD-driven —
  this agent calls oddd-optimizer first.
tools: Bash, Read, Write, Glob, Grep
---

# ARS Deck Builder

You build one client's **ARS (Account Revenue Solution®)** Executive Review deck. Stay
inside ARS — do not pull ICS or MRPC logic. Read the root `CLAUDE.md` for shared
conventions (output folder, filename, validation, writing style).

**Visual style — read `templates/STYLE.md` before building** and follow it for every slide:
fonts (Montserrat headings/callouts, Calibri body/tables — run `build/restyle_fonts.py` last),
drop shadows on every callout, tile and pill (pies and donuts stay flat), table format (navy
header / orange total / Calibri cells), chart standards (fill the space, balanced whitespace,
no label collisions, `MMM'YY` axis months),
**selection on the slide / data source in the notes**, and sequential page numbering with clear
separation between bottom text and the page number. `templates/STYLE.md` is the single source
of truth for visual style.

## Cadence

Run **monthly** for every ARS client.

## Inputs (ODD-driven)

1. **Data pack (required first).** Ensure `oddd_pack.md` + `oddd_metrics.json` exist and
   are current for this client under `<clientid>-<Name>/`. If missing or stale, call the
   **oddd-optimizer** subagent before doing anything else. Never read a raw ODD CSV
   directly.
2. **ARS workbook** for financial performance — the Lift Matrix MM tab and
   `base_extract.json` (PTD revenue/profit, profitability ratio, mailing history).

## Two build paths — pick one per client

The deck differs only in the performance-detail slide; everything else is shared.

- **MM path (default).** Use when the client's ARS workbook has a populated **Lift Matrix
  MM tab**. Includes the **ARS Lift Matrix** slide (per-account monthly value by baseline
  vs current swipe tier) and the swipe-tier segmentation. This is the path for most
  clients (Marine 1539, Texas Bay 1509, First State 1204, CoastLife 1705, True Sky 1676).
- **SM path.** Use when there is no usable Lift Matrix MM tab. Substitute the **"Monthly
  Summary — Last 12 Months"** slide in that slot (e.g. Sugar River 1038).

Selection rule: MM if the workbook's Lift Matrix MM tab is populated and usable; SM
otherwise. Aaron may override the path explicitly — honor that.

## Template

Build from `templates/ars_template.pptx` — the stripped, styled per-program shell on the
"Union Financial" dummy client. `build_ars_gen.py` takes it as its first argument and
populates it; there is no clone-and-swap step against a client reference deck any more.
Section map and swap targets are in `templates/TEMPLATES.md`. The ARS deck = shared shell
slides + ARS section + ARS Appendix.

(CLAUDE.md's "Templates" paragraph still describes cloning the Marine 1539 reference. That
is stale — the builders take `templates/*_template.pptx`, as CLAUDE.md's own file listing
says. Follow the template shell.)

Build scripts (consolidated into `build/ars_pipeline/` on 2026-07-24): `oddd_optimize.py`
(in `scripts/`) → `metrics_gen.py` → `base_tab_extract.py` (SM) or `extract_base_gen.py` +
`extract_lift.py` (MM) → `charts_gen.py` → `build_ars_gen.py` → `validation/validate_deck.py`.
`build_ars_gen.py` is the single, client-agnostic assembler — it does the text/number/chart
swaps, product-mix insert, source notes, contact slide, and font restyle itself (the old
`build_gen`/`build_gen_b`/`build_swipepct`/`style_tables`/`swap_imgs` recipe is retired to
`archive/`). See `build/README.md`.

### Verified build recipe (client-agnostic; re-ran on Sugar River 1038 SM, 2026-07-24)

**MM vs SM detection from the workbook:** open the `Executive Financials MM` tab — if
its client cell (row 4, col 2) reads a real name it's **MM**; if it's the blank template
(`Bank Name` / `October 2007`) the client is **SM** and its real data is on the
non-suffixed tabs (`Executive Financials`, `All Months Rollup`, `Key Trends`,
`Mail Response Summary`). `build_ars_gen.py` also auto-detects: non-empty `lift.json`
`matrix_rows` = MM (Lift Matrix slot); `{}` = SM (Monthly Summary slot).

**Financials extractor differs by path:**
- MM → `build/ars_pipeline/extract_base_gen.py <workbook> base.json` (+ `extract_lift.py` → `lift.json`)
- SM → `build/ars_pipeline/base_tab_extract.py <workbook.xlsx> <DCO.xlsx> > base.json`, then `echo '{}' > lift.json`

**Full SM sequence (each step < 45s; needs `pip install pyarrow` on a fresh box). `ARS_WB_FILE`
names the workbook in the source notes:**
```
python3 build/ars_pipeline/base_tab_extract.py "<Workbook>.xlsx" "<DCO>.xlsx" > base.json
python3 scripts/oddd_optimize.py --input "<id>_ODDD.zip" --out oddd --client <id> --name "<Name>"   # oddd_pack.md + oddd_metrics.json; READ the flags block
python3 build/ars_pipeline/metrics_gen.py "<id>_ODDD.zip" metrics.json                               # ~5-45s
echo '{}' > lift.json                                                                                # SM trigger
python3 build/ars_pipeline/charts_gen.py metrics.json base.json charts/                              # 28 PNGs
export ARS_WB_FILE="<workbook basename>.xlsx"
python3 build/ars_pipeline/build_ars_gen.py templates/ars_template.pptx \
        metrics.json base.json lift.json oddd/oddd_metrics.json charts/ "<out>.pptx" "<id>_ODDD.zip"
python3 validation/validate_deck.py "<out>.pptx" base.json                                           # 0 FAIL to ship
```
`build_ars_gen.py` self-locates its helpers (`REF` = its own dir; `BUILDDIR` = `build/`);
override with `RPE_REF` / `RPE_BUILDDIR` if relocated. MM clients swap steps 1/4 for the
Lift-Matrix path (`extract_base_gen` + `extract_lift`, populated `lift.json`).

## Deck structure

Shell (title, about, agenda) → Program Overview → ARS Financial Performance →
**[MM: ARS Lift Matrix | SM: Monthly Summary — Last 12 Months]** → Debit Usage
Segmentation → Average Ticket → Mailing Insights (response summary, ranking, latest
mailer, movement, transaction increase, sustained activity, before/after mean & median) →
Debit Card Review (take rate personal/business/by branch, swipes & spend, NSF/OD) →
Reg E Review (all personal, last-12-mo, by vintage) → ARS Key Takeaways → Appendix.

**Never drop slides.** Keep the full section, Reg E included. If the ODD dump doesn't
carry Reg E (some cores don't send it), that does not mean skip the Reg E slides — source
the opt-in figures from the client's Reg E data (workbook / core file) and populate them,
or flag it for Aaron. Do not remove slides and do not print a phantom 0% opt-in.

## Appendix (final module — part of ARS, not a separate agent)

Build the **"Additional ARS Respondent Insights"** appendix from the raw ODD, using the
validated definitions (see the `rpe-deck-appendix` reference): cumulative responders,
repeat responders, responder age profile, balance profile, new-account profile (product,
balances vs book, debit penetration & usage, swipe segmentation), account growth
openings vs closures, retention/survival by tenure, first-year closure by early debit
use (label associational, not causal). Watch-out: current-state ODD fields on closed
accounts are 0/blank — do not ship survivorship artifacts.

## Steps

1. Confirm client + period; ensure the data pack exists (call oddd-optimizer if needed).
2. Choose MM vs SM path from the workbook.
3. Run `build_ars_gen.py templates/ars_template.pptx <metrics.json> <base.json>
   <lift.json> <oddd_metrics.json> <charts/> <out.pptx> <ODDD.zip>`. The output filename
   must carry `<id>-<yyyy.mm>-ARS-` or the builder cannot resolve the presentation month
   (or set `ARS_PERIOD=YYYY.MM`).
4. Build the Appendix module.
5. **Font policy** — run the shared post-processor last: `python3 build/restyle_fonts.py <deck.pptx>`
   (headings + callouts → Montserrat; subheadings, body, tables → Calibri; floors runs at
   16 pt). Charts already render in Carlito. See `templates/STYLE.md` "Fonts".
6. Run `validation/validate_deck.py <deck> <base.json>`; 0 FAIL to ship. Passing
   `base.json` switches on the data-vs-deck cross-check — do not omit it.
7. Save to the pipeline **`Outputs/`** folder (flat; the program tag in the filename is
   what distinguishes it) as `<clientid>-<yyyy.mm>-ARS-<Name> ARS Results.pptx`.
   **Do not deliver to Client Presentations or to a per-client folder** — that drop was
   retired 2026-07-25 (CLAUDE.md, "Output — ONE destination").
   For a multi-program client, hand this deck to `build/assemble_combined.py --ars <deck>`
   rather than delivering it on its own.
8. Report the path + headline figures (PTD profit, profitability ratio, take rate,
   response rate) and which path (MM/SM) you used.

- **Sources in notes.** Every slide records its data source(s) and selection/period in the
  slide's speaker notes before this deck is considered done (see CLAUDE.md).

## Client-specific handling (lives here, not in code)

The pipeline is client-agnostic — **no client names in file/folder names or as code defaults**
(the builder derives id/name from the data pack; there is no fallback client). Any per-client
deviation is documented here and applied at build time, not hardcoded:

- **MM vs SM** — per client, auto-detected from the workbook / `lift.json` (see the recipe above).
- **Sugar River Bank (1038) — Reg E value mapping.** Its ODD carries `Failed to Respond` +
  `Revoked` (→ **Reg E Default**) and `Exempt` + `Ineligible` (→ **excluded**). These are not in
  the shared classifier; re-apply/confirm each build (patch `metrics_gen.regd` + `oddd_optimize.classify_rege`).
  `oddd_optimize.py` surfaces any unmapped value in the pack `flags` block — confirm before building.
- **Austin Bank (1075) — big-ODD workarounds** (271k rows vs the 45s Cowork cap): run `metrics_gen`
  in its 2-stage checkpoint mode (`MG_DUMP=...`), and pre-extract the ODD CSV once and pass the
  `.csv` (not the `.zip`) to `build_ars_gen`. SM path.
- **First State Bank-MI (1204) — winsorized debit $** (extreme business accounts) — handled in the
  perf/metrics layer; no deck change.
- **Canandaigua (1437) — NOT the standard pipeline.** Its checking products (Essentials/Traditional/
  Optimum) have no "checking" keyword, so `metrics_gen` new-checking analysis is empty. Build a custom
  lift-matrix revenue calc as a one-off; do not force the standard ARS flow.

Reference deck is `templates/ars_reference_deck.pptx` (client-neutral filename). Stale per-client
data-pack caches are not kept in the repo — they go to `archive/` (the data pack is regenerated per build). `build_ars_gen.py`
  derives the note source strings per-client (ODD extract + pull stamp from `oddd_metrics.json`,
  workbook filename, client id/name) — pass `ARS_WB_FILE` (workbook basename) so the workbook
  note names the file, and it honors `ARS_ODD_SRC` / `ARS_WB_SRC` overrides. **Verify before
  delivery:** grep the built deck's notes for the reference client ("CoastLife" / "1705") — must
  be zero — and confirm the notes show THIS client's id, pull stamp, and SM vs MM tab wording.
  This defaulted to CoastLife 1705 and leaked into every deck's notes (fixed 2026-07-24); do not
  let it regress.

## Swap integrity (2026-07-25 — learned the hard way)
`build_ars_gen.py` now tracks every find-string; any that matches nothing aborts the build
with `MISS <needle>`. Three real defects were found this way and fixed:
1. **Appendix off-by-one** — the whole appendix block addressed `S[32]`–`S[45]` while the
   re-baked 47-slide template holds those slides at `S[33]`–`S[46]`. Every swap silently
   no-op'd, so slides 34–47 shipped the template client's numbers with correct client charts.
   Now resolved by TITLE via `SB("...")`, which raises when a title is missing.
2. **"Profit This Month" tile** — the builder searched for the revenue literal `$57,270` in
   the profit tile, whose literal is `$51,569`. Never matched; every deck showed the template's
   monthly profit.
3. **"Retained at 3 years" tile** — searched `82%`, literal is `72%`.
Any future template re-bake: re-run a client build and confirm `misses=0` before shipping.

## Clients whose extract lacks DOB
FNBT Chickasha (1537) has an entirely empty `DOB` column, so the Responder Age Profile has no
source. `metrics_gen` sets `age_missing` (no divide-by-zero, no 0%) and the builder states that
age isn't carried in the extract. Fix at source: re-pull the ODD with DOB, or source age from
core/VIP. Do not fabricate the band mix.
